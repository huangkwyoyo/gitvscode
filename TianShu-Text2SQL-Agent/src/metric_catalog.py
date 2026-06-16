"""指标目录：单一事实源管理器。

设计动机：
    当前指标信息散落在 DuckDB / metric_contract.yml / MetricResolver 硬编码 /
    agent_config.yml 四个位置。MetricCatalog 作为统一的指标加载、查询、校验、
    导出入口，解决事实源分散、口径混淆、同义词硬编码三大问题。

职责：
    1. 从 DuckDB / 离线快照 / 契约文件 加载指标
    2. 维护一致性校验（validate 模式）
    3. 提供指标查询接口（按名称查找、按域过滤、所有 G3 指标）
    4. 导出指标快照供离线模式使用

不负责：
    - 自然语言匹配（这是 MetricResolver 的职责）
    - SQL 生成或执行
    - LLM 调用

数据源优先级：
    在线: DuckDB meta.metric_definitions → MetricInfo（source="duckdb"）
    离线: config/metric_snapshot.json → MetricInfo（source="snapshot"）
    兜底: TianShu/contracts/metric_contract.yml → MetricInfo（source="contract"）

用法：
    # 在线模式
    catalog = MetricCatalog.from_duckdb(conn)

    # 离线模式
    catalog = MetricCatalog.from_snapshot("config/metric_snapshot.json")

    # 查询
    metric = catalog.get_metric("trip_count")
    g3_metrics = catalog.list_g3_metrics()

    # 校验
    errors = catalog.validate()
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .resolver import MetricInfo


@dataclass
class MetricCatalog:
    """指标目录：加载、查询、校验、导出。

    指标列表由外部注入（便于测试），工厂方法负责从不同数据源构造。

    Attributes:
        _metrics: 所有已加载的指标（包含 G3 和非 G3）
        _source: 数据来源标识
        _loaded_at: 加载时间（用于快照新鲜度检查）
    """

    _metrics: list[MetricInfo] = field(default_factory=list)
    _source: str = "unknown"

    # ── 工厂方法 ────────────────────────────────────────────────

    @classmethod
    def from_duckdb(cls, metrics: list[MetricInfo]) -> MetricCatalog:
        """从 DuckDB 已加载的 MetricInfo 列表构造目录。

        DuckDB 是权威数据源，source 标记为 "duckdb"。
        调用方（TianShuResolver.discover_metrics）负责从 DuckDB 查询并传入。
        """
        return cls(_metrics=metrics, _source="duckdb")

    @classmethod
    def from_snapshot(cls, path: str) -> MetricCatalog:
        """从导出的静态 JSON 快照加载指标目录。

        快照文件由 CI 在每次 DuckDB 构建完成后自动导出。
        用于离线模式（DuckDB 不可用时）。
        """
        snapshot_path = Path(path)
        if not snapshot_path.exists():
            raise FileNotFoundError(f"指标快照文件不存在: {snapshot_path}")

        with open(snapshot_path, "r", encoding="utf-8") as f:
            raw_list = json.load(f)

        metrics = cls._parse_snapshot(raw_list)
        return cls(_metrics=metrics, _source="snapshot")

    @classmethod
    def from_contract(cls, path: str) -> MetricCatalog:
        """从 metric_contract.yml 加载指标目录（离线兜底）。

        此路径仅作为 snapshot 不可用时的最终后备。
        contract 中的 base_table/aggregation 可能有 G2/G3 口径混淆，
        因此 source 标记为 "contract" 以便下游区分。
        """
        contract_path = Path(path)
        if not contract_path.exists():
            raise FileNotFoundError(f"契约文件不存在: {contract_path}")

        with open(contract_path, "r", encoding="utf-8") as f:
            contract = yaml.safe_load(f)

        metrics = cls._parse_contract(contract)
        return cls(_metrics=metrics, _source="contract")

    # ── 查询接口 ────────────────────────────────────────────────

    def get_metric(self, name: str) -> MetricInfo | None:
        """按英文名精确查找指标。"""
        for metric in self._metrics:
            if metric.name == name:
                return metric
        return None

    def list_g3_metrics(self) -> list[MetricInfo]:
        """返回所有 G3 可用的指标。

        这是 MetricResolver 的输入范围——只允许查询 G3 汇总表支持的指标。
        非 G3 指标（如 driver_application_count）被自动排除。
        """
        return [m for m in self._metrics if m.g3_available]

    def list_g2_metrics(self) -> list[MetricInfo]:
        """返回所有非 G3 指标（即仅 G2 事实表可用的指标）。

        这些指标没有 G3 汇总表，必须通过 G2 事实表聚合查询。
        证据来源：metric_contract.yml 中 g3_available=false 的指标。
        """
        return [m for m in self._metrics if not m.g3_available]

    def list_by_domain(self, domain: str) -> list[MetricInfo]:
        """按业务域过滤指标。"""
        return [m for m in self._metrics if m.domain == domain]

    def list_all(self) -> list[MetricInfo]:
        """返回全部已加载指标（含非 G3）。"""
        return list(self._metrics)

    # ── 校验 ────────────────────────────────────────────────────

    def validate(self) -> list[str]:
        """执行一致性校验，返回问题列表。

        校验项：
            1. 指标名唯一性
            2. G3 可用指标的 base_table 必须非空
            3. 同义词不应包含指标中文名（会导致优先级混乱）
            4. domain 值在合法枚举内
            5. G3 可用指标的 aggregation 必须非空
        """
        errors: list[str] = []

        # 1. 指标名唯一性
        names = [m.name for m in self._metrics]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            errors.append(f"指标名重复: {duplicates}")

        valid_domains = {"traffic", "violation", "safety", "supply"}

        for metric in self._metrics:
            # 2. G3 可用但 base_table 为空
            if metric.g3_available and not metric.base_table:
                errors.append(
                    f"指标 '{metric.name}' 标记为 g3_available 但 base_table 为空"
                )

            # 3. 同义词包含中文名
            if metric.zh_name and metric.zh_name in metric.synonyms:
                errors.append(
                    f"指标 '{metric.name}' 的同义词包含中文名 '{metric.zh_name}'，"
                    f"应放入 zh_name 字段而非 synonyms"
                )

            # 4. domain 合法性
            if metric.domain and metric.domain not in valid_domains:
                errors.append(
                    f"指标 '{metric.name}' 的 domain '{metric.domain}' "
                    f"不在合法值 {valid_domains} 中"
                )

            # 5. G3 可用但 aggregation 为空
            if metric.g3_available and not metric.aggregation:
                errors.append(
                    f"指标 '{metric.name}' 标记为 g3_available 但 aggregation 为空"
                )

        return errors

    # ── 导出 ────────────────────────────────────────────────────

    def export_snapshot(self, path: str) -> None:
        """将当前指标目录导出为 JSON 快照。

        快照格式包含所有字段，用于离线模式加载和 CI 校验。
        生成的 JSON 可被 from_snapshot() 直接读取。
        """
        output: list[dict] = []
        for metric in self.list_g3_metrics():
            output.append({
                "metric_name": metric.name,
                "metric_name_zh": metric.zh_name,
                "domain": metric.domain,
                "source_table": metric.base_table,
                "calculation_sql": metric.aggregation,
                "unit": metric.unit,
                "g3_available": metric.g3_available,
                "synonyms": metric.synonyms,
                "keywords": [list(g) for g in metric.keyword_groups],
                "aliases": metric.aliases,
                "description": metric.description,
                "caution": metric.caution,
            })

        snapshot_path = Path(path)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    # ── 内部解析 ────────────────────────────────────────────────

    @staticmethod
    def _parse_snapshot(raw_list: list[dict]) -> list[MetricInfo]:
        """解析 snapshot JSON 为 MetricInfo 列表。

        快照字段名沿用 DuckDB 列名风格（metric_name / metric_name_zh / source_table），
        映射到 MetricInfo 的 Python 风格字段。
        """
        metrics: list[MetricInfo] = []
        for item in raw_list:
            # 关键词在快照中存储为 [["词1","词2"],["词3"]]
            # 加载后转为 tuple 格式
            raw_keywords = item.get("keywords", [])
            keyword_groups = [
                tuple(group) for group in raw_keywords if isinstance(group, list)
            ]

            metrics.append(MetricInfo(
                name=str(item.get("metric_name", "")),
                zh_name=str(item.get("metric_name_zh", "")),
                domain=str(item.get("domain", "")),
                aggregation=str(item.get("calculation_sql", "")),
                base_table=str(item.get("source_table", "")),
                unit=str(item.get("unit", "")),
                g3_available=bool(item.get("g3_available", False)),
                synonyms=[
                    s for s in item.get("synonyms", []) if isinstance(s, str)
                ],
                keyword_groups=keyword_groups,
                aliases=[
                    a for a in item.get("aliases", []) if isinstance(a, str)
                ],
                description=str(item.get("description", "")),
                caution=str(item.get("caution", "")),
                source="snapshot",
            ))
        return metrics

    @staticmethod
    def _parse_contract(contract: dict) -> list[MetricInfo]:
        """解析 metric_contract.yml 为 MetricInfo 列表。

        contract 是文档导向的，字段完整性低于 DuckDB/snapshot。
        base_table 和 aggregation 取 contract 中的值，但可能指向 G2 事实表——
        source 标记为 "contract" 提醒下游注意。
        """
        metrics: list[MetricInfo] = []
        for item in contract.get("metrics", []):
            metrics.append(MetricInfo(
                name=str(item.get("name", "")),
                zh_name=str(item.get("zh_name", "")),
                domain=str(item.get("domain", "")),
                aggregation=str(item.get("aggregation", "")),
                base_table=str(item.get("base_table", "")),
                unit=str(item.get("unit", "")),
                g3_available=bool(item.get("g3_available", False)),
                synonyms=[],       # contract 不含同义词列
                keyword_groups=[], # contract 不含关键词列
                aliases=[],        # contract 不含别名列
                description=str(item.get("description", "")),
                caution=str(item.get("caution", "")),
                source="contract",
            ))
        return metrics

    def __len__(self) -> int:
        return len(self._metrics)

    def __repr__(self) -> str:
        return (
            f"MetricCatalog(metrics={len(self._metrics)}, "
            f"g3={len(self.list_g3_metrics())}, "
            f"source='{self._source}')"
        )
