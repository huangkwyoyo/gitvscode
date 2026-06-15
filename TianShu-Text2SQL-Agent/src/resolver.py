"""
TianShu DuckDB 连接器和契约加载器。

职责：
    1. 加载 TianShu contracts/ 目录中的 YAML 契约文件
    2. 建立 DuckDB 只读连接
    3. 动态发现可用表、列、指标（从 information_schema + meta.metric_definitions）
    4. 将契约中的静态规则与数据库中的动态状态合并为 Agent 可用的上下文

用法：
    resolver = TianShuResolver(config_path="config/tianshu_target.yml")
    context = resolver.build_context()  # 供 Prompt 渲染使用
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from .executor import execute_sql as _do_execute
from .ir import SQLResult
from .safety_policy_loader import load_forbidden_keywords

try:
    import duckdb
except ImportError:
    duckdb = None


@dataclass
class TableInfo:
    """表信息"""
    schema: str
    name: str
    columns: list[str] = field(default_factory=list)
    column_types: dict[str, str] = field(default_factory=dict)
    row_count: int = 0


@dataclass
class MetricInfo:
    """指标信息（从 meta.metric_definitions 或 metric_contract.yml 加载）"""
    name: str
    zh_name: str
    domain: str
    aggregation: str
    base_table: str
    unit: str
    g3_available: bool


@dataclass
class AgentContext:
    """
    Agent 运行时上下文。

    聚合了 TianShu 契约 + DuckDB 动态发现的全部信息，
    作为 Prompt 模板渲染的输入。

    offline 标志为 True 时表示：Resolver 初始化失败，上下文中的
    安全白名单均为空，Agent 必须禁止执行 SQL（防御深度）。
    """
    available_tables: list[TableInfo] = field(default_factory=list)
    available_metrics: list[MetricInfo] = field(default_factory=list)
    join_whitelist: list[tuple[str, str]] = field(default_factory=list)
    forbidden_patterns: list[str] = field(default_factory=list)
    forbidden_sql_keywords: list[str] = field(default_factory=list)
    dim_date_range: tuple[str, str] = ("1997-01-01", "2027-12-31")
    offline: bool = False  # 是否为离线模式（Resolver 初始化失败后为 True）


class TianShuResolver:
    """
    TianShu 数据仓库解析器。

    启动时：
        1. 读取 config/tianshu_target.yml 获取 TianShu 路径
        2. 加载 contracts/ 中的 YAML 契约文件
        3. 建立 DuckDB 只读连接
        4. 合并静态契约 + 动态 schema 为 AgentContext
    """

    def __init__(self, config_path: str = "config/tianshu_target.yml"):
        self._config_path = Path(config_path)
        self._config: dict[str, Any] = {}
        self._conn: Any = None  # DuckDB 连接
        self._contracts: dict[str, Any] = {}

    def load_config(self) -> dict[str, Any]:
        """加载 tianshu_target.yml 配置"""
        if not self._config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self._config_path}")

        with open(self._config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

        # TianShu 路径以 Agent 项目根目录为基准，避免落到 config/ 下。
        tianshu_rel = self._config.get("tianshu", {}).get("project_root", "../TianShu")
        agent_root = self._config_path.parent.parent
        self._tianshu_root = (agent_root / tianshu_rel).resolve()
        return self._config

    def load_contracts(self) -> dict[str, Any]:
        """加载 TianShu contracts/ 目录中的所有 YAML 契约文件"""
        contracts_path = self._tianshu_root / self._config.get("tianshu", {}).get("contracts_path", "contracts")
        if not contracts_path.exists():
            raise FileNotFoundError(f"契约目录不存在: {contracts_path}")

        for contract_file in contracts_path.glob("*.yml"):
            with open(contract_file, "r", encoding="utf-8") as f:
                self._contracts[contract_file.stem] = yaml.safe_load(f)

        return self._contracts

    def connect(self) -> Any:
        """建立 DuckDB 只读连接"""
        if duckdb is None:
            raise ImportError("需要 duckdb 包: pip install duckdb")

        duckdb_rel = self._config.get("tianshu", {}).get("duckdb_path", "data/tian_shu.duckdb")
        db_path = self._tianshu_root / duckdb_rel

        if not db_path.exists():
            raise FileNotFoundError(f"DuckDB 文件不存在: {db_path}")

        self._conn = duckdb.connect(str(db_path), read_only=True)
        return self._conn

    def discover_tables(self) -> list[TableInfo]:
        """从 DuckDB information_schema 动态发现可用表"""
        if self._conn is None:
            self.connect()

        tables: list[TableInfo] = []
        rows = self._conn.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema IN ('gold', 'meta') "
            "ORDER BY table_schema, table_name"
        ).fetchall()

        for schema, name in rows:
            # 获取列信息
            cols = self._conn.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = ? AND table_name = ? "
                "ORDER BY ordinal_position",
                [schema, name],
            ).fetchall()

            table_info = TableInfo(
                schema=schema,
                name=name,
                columns=[c[0] for c in cols],
                column_types={c[0]: c[1] for c in cols},
            )
            tables.append(table_info)

        return tables

    def discover_metrics(self) -> list[MetricInfo]:
        """从 meta.metric_definitions 动态发现可用指标（回退到 contracts）"""
        metrics: list[MetricInfo] = []

        # 优先从 DuckDB 动态发现
        if self._conn is not None:
            try:
                result = self._conn.execute(
                    "SELECT * FROM meta.metric_definitions ORDER BY metric_name"
                )
                rows = result.fetchall()
                columns = [desc[0] for desc in result.description]
                for row in rows:
                    row_data = dict(zip(columns, row))
                    metric_name = str(row_data.get("metric_name", row[0]))
                    source_table = str(row_data.get("source_table", row_data.get("base_table", "")))
                    aggregation = str(row_data.get("calculation_sql", row_data.get("aggregation", "")))
                    metrics.append(MetricInfo(
                        name=metric_name,
                        zh_name=str(row_data.get("metric_name_zh", row_data.get("zh_name", ""))),
                        domain=str(row_data.get("domain", self._infer_metric_domain(metric_name, source_table))),
                        aggregation=aggregation,
                        base_table=source_table,
                        unit=str(row_data.get("unit", "")),
                        g3_available=bool(
                            row_data.get("g3_available", source_table.startswith("gold.dws_"))
                        ),
                    ))
                return metrics
            except Exception:
                pass  # 回退到 contracts

        # 回退：从 metric_contract.yml 加载
        metric_contract = self._contracts.get("metric_contract", {})
        for m in metric_contract.get("metrics", []):
            metrics.append(MetricInfo(
                name=m["name"],
                zh_name=m.get("zh_name", ""),
                domain=m.get("domain", ""),
                aggregation=m.get("aggregation", ""),
                base_table=m.get("base_table", ""),
                unit=m.get("unit", ""),
                g3_available=m.get("g3_available", False),
            ))

        return metrics

    def _infer_metric_domain(self, metric_name: str, source_table: str) -> str:
        """从指标名和来源表推断基础业务域"""
        text = f"{metric_name} {source_table}"
        if "trip" in text or "fare" in text or "distance" in text:
            return "traffic"
        if "parking" in text or "violation" in text or "fine" in text:
            return "violation"
        if "crash" in text or "injured" in text or "killed" in text:
            return "safety"
        if "tif" in text or "payment" in text or "application" in text:
            return "supply"
        return ""

    def build_context(self) -> AgentContext:
        """
        构建 Agent 运行时上下文。

        合并静态契约 + 动态 schema 发现，生成 Prompt 渲染所需的完整上下文。
        """
        # 1. 加载配置和契约
        self.load_config()
        self.load_contracts()

        # 2. 尝试连接 DuckDB
        try:
            self.connect()
        except Exception:
            self._conn = None  # 离线模式：仅使用契约文件

        # 3. 动态发现；离线时从契约生成静态白名单。
        available_tables = self.discover_tables() if self._conn else self._tables_from_contracts()
        available_metrics = self.discover_metrics()

        # 4. 从契约中提取规则
        join_whitelist: list[tuple[str, str]] = []
        sql_safety = self._contracts.get("sql_safety_policy", {})
        for rule in sql_safety.get("table_reference_rules", []):
            if rule.get("rule") == "join_whitelist":
                for join_str in rule.get("allowed_joins", []):
                    # 解析 "gold.fact_trips ↔ gold.dim_date (pickup_date_key)"
                    parts = join_str.split("↔")
                    if len(parts) == 2:
                        left = parts[0].strip().split("(")[0].strip()
                        right = parts[1].strip().split("(")[0].strip()
                        join_whitelist.append((left, right))

        # G3 日汇总表按契约必须经 dim_date 做日期过滤，补齐本 Agent 的查询路径。
        join_whitelist.extend([
            ("gold.dws_daily_trip_summary", "gold.dim_date"),
            ("gold.dws_daily_parking_summary", "gold.dim_date"),
            ("gold.dws_daily_crash_summary", "gold.dim_date"),
        ])

        forbidden_patterns: list[str] = []
        semantic = self._contracts.get("semantic_contract", {})
        for fb in semantic.get("forbidden", []):
            forbidden_patterns.append(fb.get("pattern", ""))

        # C-2 修复：从统一加载器获取禁止的 SQL 关键字（合并 agent_config extras）
        contracts_abs = self._tianshu_root / self._config.get("tianshu", {}).get("contracts_path", "contracts")
        forbidden_keywords: list[str] = load_forbidden_keywords(
            contracts_path=contracts_abs.resolve(),
            strict=False,  # 已在 load_contracts 中验证契约存在，此处无需重复抛异常
        )

        return AgentContext(
            available_tables=available_tables,
            available_metrics=available_metrics,
            join_whitelist=join_whitelist,
            forbidden_patterns=forbidden_patterns,
            forbidden_sql_keywords=forbidden_keywords,
        )

    def _tables_from_contracts(self) -> list[TableInfo]:
        """从语义契约构建离线表白名单"""
        semantic = self._contracts.get("semantic_contract", {})
        entries: list[dict[str, Any]] = []
        for key in ("g3_summary", "g2_facts", "dimensions", "views", "meta"):
            entries.extend(semantic.get(key, []))

        tables: list[TableInfo] = []
        for entry in entries:
            full_name = entry.get("table", "")
            if "." not in full_name:
                continue
            schema, name = full_name.split(".", 1)
            tables.append(TableInfo(schema=schema, name=name))
        return tables

    def execute_sql(
        self,
        sql: str,
        timeout_seconds: int = 30,
        source_table: str = "",
    ) -> SQLResult:
        """
        在 DuckDB 只读连接上执行 SQL，返回结构化结果。

        封装了 _conn 的访问细节，防止外部代码直接操作 DuckDB 连接。
        内部调用 executor.execute_sql() 执行实际查询。

        Args:
            sql: 要执行的 SELECT 语句
            timeout_seconds: 超时时间（秒），默认 30 秒
            source_table: 主数据来源表（用于结果标注）

        Returns:
            SQLResult 包含列名、数据类型、数据行、执行时间和签名。
            连接不可用时返回带有错误信息的 SQLResult。
        """
        if self._conn is None:
            return SQLResult(
                sql=sql,
                error="数据库未连接（离线模式）",
            )
        return _do_execute(
            self._conn,
            sql,
            timeout_seconds=timeout_seconds,
            source_table=source_table,
        )

    def close(self):
        """关闭 DuckDB 连接"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
