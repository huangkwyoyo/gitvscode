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
    """
    available_tables: list[TableInfo] = field(default_factory=list)
    available_metrics: list[MetricInfo] = field(default_factory=list)
    join_whitelist: list[tuple[str, str]] = field(default_factory=list)
    forbidden_patterns: list[str] = field(default_factory=list)
    forbidden_sql_keywords: list[str] = field(default_factory=list)
    dim_date_range: tuple[str, str] = ("1997-01-01", "2027-12-31")


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

        # 解析 TianShu 项目路径（相对于本项目的相对路径 → 绝对路径）
        tianshu_rel = self._config.get("tianshu", {}).get("project_root", "../TianShu")
        self._tianshu_root = (self._config_path.parent / tianshu_rel).resolve()
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
                rows = self._conn.execute(
                    "SELECT * FROM meta.metric_definitions ORDER BY domain, metric_name"
                ).fetchall()
                # 按实际列名解析（TODO：适配 TianShu 的 meta.metric_definitions 表结构）
                for row in rows:
                    # 假设列顺序：metric_name, zh_name, domain, aggregation, base_table, unit, g3_available
                    metrics.append(MetricInfo(
                        name=str(row[0]),
                        zh_name=str(row[1]) if len(row) > 1 else "",
                        domain=str(row[2]) if len(row) > 2 else "",
                        aggregation=str(row[3]) if len(row) > 3 else "",
                        base_table=str(row[4]) if len(row) > 4 else "",
                        unit=str(row[5]) if len(row) > 5 else "",
                        g3_available=bool(row[6]) if len(row) > 6 else False,
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

        # 3. 动态发现
        available_tables = self.discover_tables() if self._conn else []
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

        forbidden_patterns: list[str] = []
        semantic = self._contracts.get("semantic_contract", {})
        for fb in semantic.get("forbidden", []):
            forbidden_patterns.append(fb.get("pattern", ""))

        # 从安全策略中提取禁止的 SQL 关键字
        forbidden_keywords: list[str] = []
        forbidden_ops = sql_safety.get("forbidden_operations", [])
        for op in forbidden_ops:
            forbidden_keywords.extend(op.get("keywords", []))

        return AgentContext(
            available_tables=available_tables,
            available_metrics=available_metrics,
            join_whitelist=join_whitelist,
            forbidden_patterns=forbidden_patterns,
            forbidden_sql_keywords=forbidden_keywords,
        )

    def close(self):
        """关闭 DuckDB 连接"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
