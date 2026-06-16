"""注册指标解析器。

设计动机：
    将指标识别逻辑从 agent.py 的硬编码 if/else 链中抽离为独立的可测试单元。
    MetricResolver 不依赖 LLM，完全基于注册指标目录 + 同义词/关键词规则运行，
    因此规则模式和 LLM 模式共用同一套解析逻辑，保证行为一致性。

匹配策略：
    采用 5 层优先级降级匹配，高优先级命中即停止，避免关键词组合误伤精确匹配。
    优先级链：metric_name 直接命中 > 中文名 > 同义词 > 配置别名 > 关键词组合

歧义处理：
    当用户问"金额是多少"而未限定具体口径时（如车费 vs 罚金），
    必须反问而非猜测——因为错误猜测会导致用户基于错误数据做决策，
    这是比"无法回答"更严重的问题。

v2 变更（B 类重构）：
    - 移除硬编码 _SYNONYMS / _KEYWORDS 类变量
    - 同义词/关键词/别名现在从 MetricInfo 的属性中读取
    - __init__ 兼容旧接口 (list[MetricInfo], aliases) 和新接口 (MetricCatalog)
    - 金额候选指标改为动态计算（筛选 unit="美元" 的 G3 指标）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .resolver import MetricInfo

if TYPE_CHECKING:
    from .metric_catalog import MetricCatalog


@dataclass(frozen=True)
class MetricCandidate:
    """单个指标候选及其命中证据。

    Attributes:
        metric: 命中的注册指标信息
        confidence: 匹配置信度（0.0~1.0），由匹配方式的精确度决定
        matched_by: 命中的匹配方式标识（metric_name/zh_name/synonym/alias/keyword）
        matched_terms: 触发命中的具体中文词条，用于调试和反问文案生成
    """

    metric: MetricInfo
    confidence: float
    matched_by: str
    matched_terms: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MetricMatchResult:
    """指标解析结果。

    该结果直接驱动 Agent 的三种后续行为：
        - matched=True  → 继续 SQL 规划和执行
        - matched=False, ambiguous=True → 反问用户选择候选指标
        - matched=False, ambiguous=False → 反问用户重新描述

    Attributes:
        matched: 是否唯一匹配到注册指标
        metric: 匹配到的指标（仅 matched=True 时有值）
        confidence: 匹配置信度（综合所有候选的最高置信度）
        ambiguous: 是否因多候选置信度过近而歧义
        candidates: 所有命中的候选列表（用于反问时列出选项）
        clarification_message: 需要反问时的中文文案
        failure_reason: 失败原因标识（metric_not_found / ambiguous_metric）
    """

    matched: bool
    metric: MetricInfo | None = None
    confidence: float = 0.0
    ambiguous: bool = False
    candidates: list[MetricCandidate] = field(default_factory=list)
    clarification_message: str | None = None
    failure_reason: str | None = None


class MetricResolver:
    """基于注册指标目录解析用户问题中的指标。

    v2 接口（推荐）：
        from .metric_catalog import MetricCatalog
        resolver = MetricResolver(catalog)
        result = resolver.resolve("2026年1月每天车费总额是多少？")

    v1 接口（向后兼容，逐步弃用）：
        resolver = MetricResolver(metrics, aliases=config_aliases)
        result = resolver.resolve("2026年1月每天车费总额是多少？")

    设计决策：
        - v2 中同义词/关键词/别名从每个 MetricInfo 的自身属性读取，
          不再使用类级别的硬编码 _SYNONYMS / _KEYWORDS 字典。
        - _AMOUNT_WORDS 保留为类常量——这些是中文通用语义词，
          不绑定到任何特定指标。
    """

    # ── 金额歧义触发词（通用中文语义词，不绑定特定指标）──
    _AMOUNT_WORDS = ("金额", "费用", "多少钱", "收入")

    def __init__(
        self,
        catalog_or_metrics: "MetricCatalog | list[MetricInfo]",
        aliases: dict[str, list[str]] | None = None,
    ):
        """初始化指标解析器。

        支持两种构造方式：
            v2（推荐）: MetricResolver(catalog)
            v1（兼容）: MetricResolver(metrics, aliases=...)

        Args:
            catalog_or_metrics: MetricCatalog 或 list[MetricInfo]
            aliases: 仅 v1 接口使用，v2 中忽略（别名从 MetricInfo 读取）
        """
        from .metric_catalog import MetricCatalog

        if isinstance(catalog_or_metrics, MetricCatalog):
            # v2 接口：从 MetricCatalog 获取 G3 指标
            self._metrics = catalog_or_metrics.list_g3_metrics()
            self._catalog = catalog_or_metrics
        else:
            # v1 接口（向后兼容）：直接传入 MetricInfo 列表
            self._metrics = [m for m in catalog_or_metrics if m.g3_available]
            self._aliases = aliases or {}
            self._catalog = None

    def resolve(self, question: str) -> MetricMatchResult:
        """解析问题中的 G3 指标。

        决策流程（按优先级依次判断）：

        1. 金额歧义优先拦截
           ——"金额是多少"有多个金额类候选（车费 vs 罚金），
           必须先反问而非走常规候选匹配。

        2. 无候选 → 反问用户重新描述

        3. 多候选且置信度差距 < 0.12 → 反问用户选择
           ——0.12 阈值来自经验调优：同义词命中(0.93)与关键词命中(0.82)
           差 0.11，设 0.12 在两者间建立缓冲区。

        4. 唯一候选 → 返回命中结果
        """
        candidates = self._collect_candidates(question)

        # ── 优先级 1: 金额歧义必须先于常规候选匹配 ──
        if self._looks_like_ambiguous_amount(question):
            amount_candidates = self._amount_candidates()
            if len(amount_candidates) > 1:
                return MetricMatchResult(
                    matched=False,
                    ambiguous=True,
                    candidates=amount_candidates,
                    clarification_message=self._clarification_for_candidates(amount_candidates),
                    failure_reason="ambiguous_metric",
                )

        # ── 优先级 2: 完全没有匹配到注册指标 ──
        if not candidates:
            return MetricMatchResult(
                matched=False,
                candidates=[],
                clarification_message=self._unmatched_message(),
                failure_reason="metric_not_found",
            )

        # ── 优先级 3: 多候选置信度过近 → 歧义反问 ──
        candidates = sorted(candidates, key=lambda item: item.confidence, reverse=True)
        top = candidates[0]
        if len(candidates) > 1 and top.confidence - candidates[1].confidence < 0.12:
            return MetricMatchResult(
                matched=False,
                ambiguous=True,
                candidates=candidates,
                clarification_message=self._clarification_for_candidates(candidates),
                failure_reason="ambiguous_metric",
            )

        # ── 优先级 4: 唯一候选，返回成功 ──
        return MetricMatchResult(
            matched=True,
            metric=top.metric,
            confidence=top.confidence,
            ambiguous=False,
            candidates=candidates,
        )

    def resolve_all(
        self, question: str, min_confidence: float = 0.80,
    ) -> list[MetricCandidate]:
        """返回所有高于置信度阈值的候选指标，不做歧义消解。

        与 resolve() 的核心区别：
            - 不提前返回：不因金额歧义或单候选而中断
            - 不做 top-2 置信度差距判断：所有高于阈值的候选都返回
            - 金额歧义拦截不触发：那是单指标消歧行为，多指标场景下用户可能
              确实在问两个金额指标（如"车费收入和罚款总额"）

        复用 _collect_candidates() 的 5 层匹配逻辑和按 metric.name 去重机制。

        Args:
            question: 用户问题文本
            min_confidence: 最低置信度阈值，低于此值的候选被过滤（默认 0.80）

        Returns:
            按置信度降序排列的候选列表。空列表表示没有注册指标匹配。
        """
        candidates = self._collect_candidates(question)  # list[MetricCandidate]，已按 metric.name 去重
        filtered = [c for c in candidates if c.confidence >= min_confidence]
        return sorted(filtered, key=lambda c: c.confidence, reverse=True)

    def _collect_candidates(self, question: str) -> list[MetricCandidate]:
        """按优先级降级收集候选指标。

        匹配优先级链（高→低，命中即停止，不降级）：
            metric_name  → 1.00   英文指标名直接出现在问题中
            zh_name      → 0.98   中文指标名精确匹配
            synonym      → 0.93   指标自身 synonyms 中任一词条命中
            alias        → 0.90   指标自身 aliases 中任一别名命中
            keyword      → 0.82   指标自身 keyword_groups 中任一组全部命中

        使用 dict 去重：同一指标名只保留首次（最高优先级）命中结果。
        """
        result: dict[str, MetricCandidate] = {}
        question_lower = question.lower()
        for metric in self._metrics:
            # 优先级 1: 英文指标名直接出现在问题中
            if metric.name.lower() in question_lower:
                result[metric.name] = MetricCandidate(metric, 1.0, "metric_name", [metric.name])
                continue
            # 优先级 2: 中文指标名精确匹配
            if metric.zh_name and metric.zh_name in question:
                result[metric.name] = MetricCandidate(metric, 0.98, "zh_name", [metric.zh_name])
                continue
            # 优先级 3: 同义词匹配（v2: 从 metric.synonyms；v1: 从 _SYNONYMS）
            synonym = self._match_synonym(metric, question)
            if synonym:
                result[metric.name] = MetricCandidate(metric, 0.93, "synonym", [synonym])
                continue
            # 优先级 4: 配置别名匹配（v2: metric.aliases；v1: self._aliases）
            alias = self._match_alias_for_metric(metric, question)
            if alias:
                result[metric.name] = MetricCandidate(metric, 0.9, "alias", [alias])
                continue
            # 优先级 5: 关键词组合匹配（v2: metric.keyword_groups；v1: 内联）
            keywords = self._match_keywords_for_metric(metric, question)
            if keywords:
                result[metric.name] = MetricCandidate(metric, 0.82, "keyword", list(keywords))
        return list(result.values())

    # ── 匹配方法（v2：从 MetricInfo 属性读取）──

    @staticmethod
    def _match_synonym(metric: MetricInfo, question: str) -> str | None:
        """从 metric.synonyms 列表中匹配同义词。

        v2 优先从 MetricInfo.synonyms 读取；v1 兼容旧 _SYNONYMS 硬编码字典。
        当 metric.synonyms 为空时回退到类级别的旧数据。
        """
        synonyms = metric.synonyms if metric.synonyms else _LEGACY_SYNONYMS.get(metric.name, [])
        for term in synonyms:
            if term in question:
                return term
        return None

    def _match_alias_for_metric(self, metric: MetricInfo, question: str) -> str | None:
        """从 metric.aliases 或 v1 兼容 aliases 字典匹配别名。"""
        question_lower = question.lower()
        # v2: metric.aliases 优先
        for term in metric.aliases:
            if term and term.lower() in question_lower:
                return term
        # v1: 回退到旧 aliases 字典
        if hasattr(self, '_aliases') and self._aliases:
            for term in self._aliases.get(metric.name, []):
                if term and term.lower() in question_lower:
                    return term
        return None

    @staticmethod
    def _match_keywords_for_metric(metric: MetricInfo, question: str) -> tuple | None:
        """从 metric.keyword_groups 中匹配关键词组合。

        每个 group 中的所有词必须同时出现在问题中才命中。
        v2 优先从 MetricInfo.keyword_groups 读取；v1 回退到旧 _KEYWORDS 硬编码。
        """
        groups = metric.keyword_groups if metric.keyword_groups else _LEGACY_KEYWORDS.get(metric.name, [])
        for group in groups:
            # group 可能是 tuple 或 list（来自快照 JSON 反序列化）
            if all(term in question for term in group):
                return tuple(group)
        return None

    def _looks_like_ambiguous_amount(self, question: str) -> bool:
        """识别未限定口径的金额类问题。

        判断逻辑：
            1. 问题包含金额类词（"金额"/"费用"/"多少钱"/"收入"）
            2. 且问题中没有出现任何具体口径词（所有 G3 指标的同义词）

        v2 变更：具体口径词不再从硬编码 _SYNONYMS 收集，
        而是遍历所有 G3 指标的 synonyms 属性动态获取。
        """
        if not any(word in question for word in self._AMOUNT_WORDS):
            return False
        # 收集所有 G3 指标的具体口径词（排除金额类通用词自身）
        concrete_terms: set[str] = set()
        for metric in self._metrics:
            for term in metric.synonyms:
                if term not in self._AMOUNT_WORDS:
                    concrete_terms.add(term)
        # 同时纳入旧 _SYNONYMS 中未迁移到 MetricInfo.synonyms 的词
        for terms in _LEGACY_SYNONYMS.values():
            for term in terms:
                if term not in self._AMOUNT_WORDS:
                    concrete_terms.add(term)
        return not any(term in question for term in concrete_terms)

    def _amount_candidates(self) -> list[MetricCandidate]:
        """返回当前 G3 指标中的金额类候选。

        v2 变更：改为动态筛选——unit 为"美元"的 G3 指标自动归为金额类。
        不再硬编码指标名集合。
        置信度 0.72 比关键词组合(0.82)更低——"金额"的语义粒度比关键词更模糊。
        """
        candidates: list[MetricCandidate] = []
        for metric in self._metrics:
            if metric.unit == "美元":
                candidates.append(MetricCandidate(metric, 0.72, "keyword", ["金额"]))
        # 如果按 unit 筛选为空，回退到旧硬编码集合（兼容 unit 字段缺失的场景）
        if not candidates:
            amount_metric_names = {"total_fare_amount", "standard_fine_total"}
            candidates = [
                MetricCandidate(metric, 0.72, "keyword", ["金额"])
                for metric in self._metrics
                if metric.name in amount_metric_names
            ]
        return candidates

    def _clarification_for_candidates(self, candidates: list[MetricCandidate]) -> str:
        """生成候选指标反问文案。"""
        labels = [
            f"{item.metric.zh_name or item.metric.name}（{item.metric.name}）"
            for item in candidates
        ]
        return "请明确要查询哪个指标：" + "、".join(labels)

    def _unmatched_message(self) -> str:
        """生成未识别指标反问文案。"""
        labels = [
            f"{metric.zh_name or metric.name}（{metric.name}）"
            for metric in self._metrics
        ]
        return "暂未识别到已注册 G3 指标，请明确要查询：" + "、".join(labels)


# ── v1 兼容：旧硬编码同义词/关键词（过渡用）──
# 当 MetricInfo.synonyms / MetricInfo.keyword_groups 为空时，
# MetricResolver 回退到这些字典。待 DuckDB 扩展列部署完成后可移除。

_LEGACY_SYNONYMS: dict[str, list[str]] = {
    "standard_fine_total": ["罚款总额", "标准罚款", "标准罚金", "罚单金额"],
    "total_fare_amount": ["车费总额", "基础车费", "车费收入", "车费金额"],
    "avg_distance_miles": ["平均行程距离", "平均里程"],
    "persons_injured": ["受伤人数", "受伤人口", "伤者人数"],
    "persons_killed": ["死亡人数", "死亡人口", "遇难人数"],
    "trip_count": ["行程数", "行程量", "出行量", "订单数"],
    "parking_violation_count": ["罚单数量", "停车罚单数量", "违章数量", "停车违章数量"],
    "crash_count": ["事故数", "事故数量", "碰撞数量"],
}

_LEGACY_KEYWORDS: dict[str, list[tuple[str, ...]]] = {
    "standard_fine_total": [("罚款", "总额"), ("罚金", "总额")],
    "total_fare_amount": [("车费", "总额"), ("车费", "收入")],
    "avg_distance_miles": [("平均", "距离"), ("平均", "里程")],
    "persons_injured": [("受伤",), ("伤者",)],
    "persons_killed": [("死亡",), ("遇难",)],
    "trip_count": [("行程",), ("出行",), ("订单",)],
    "parking_violation_count": [("停车", "罚单"), ("违章",)],
    "crash_count": [("事故",), ("碰撞",)],
}
