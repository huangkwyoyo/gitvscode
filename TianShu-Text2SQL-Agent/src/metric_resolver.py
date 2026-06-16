"""注册指标解析器。

设计动机：
    将指标识别逻辑从 agent.py 的硬编码 if/else 链中抽离为独立的可测试单元。
    MetricResolver 不依赖 LLM，完全基于注册指标目录 + 同义词/关键词规则运行，
    因此规则模式和 LLM 模式共用同一套解析逻辑，保证行为一致性。

匹配策略：
    采用 4 层优先级降级匹配，高优先级命中即停止，避免关键词组合误伤精确匹配。
    优先级链：metric_name 直接命中 > 中文名 > 同义词 > 配置别名 > 关键词组合

歧义处理：
    当用户问"金额是多少"而未限定具体口径时（如车费 vs 罚金），
    必须反问而非猜测——因为错误猜测会导致用户基于错误数据做决策，
    这是比"无法回答"更严重的问题。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .resolver import MetricInfo


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

    使用方式：
        resolver = MetricResolver(metrics, aliases=config_aliases)
        result = resolver.resolve("2026年1月每天车费总额是多少？")
        if result.matched:
            print(f"命中指标: {result.metric.name}")
        else:
            print(f"需要反问: {result.clarification_message}")

    设计决策：
        - 同义词表硬编码在类中而非配置文件中，因为这些是语言学层面的同义映射，
          不随数据仓库变化而变化；配置别名面向运维新增别名场景。
        - 关键词组合（_KEYWORDS）要求所有词项同时出现才命中，
          这是为了防止单关键词导致误匹配（如"订单"单独命中 trip_count，
          但用户可能只是提到"订单"而非查询订单数）。
    """

    # ── 同义词表：中文口语表达 → 注册指标名 ──
    # 这些是语言学层面的同义映射，独立于数据仓库配置，
    # 因此硬编码在类中而非 agent_config.yml。
    _SYNONYMS: dict[str, list[str]] = {
        "standard_fine_total": ["罚款总额", "标准罚款", "标准罚金", "罚单金额"],
        "total_fare_amount": ["车费总额", "基础车费", "车费收入", "车费金额"],
        "avg_distance_miles": ["平均行程距离", "平均里程"],
        "persons_injured": ["受伤人数", "受伤人口", "伤者人数"],
        "persons_killed": ["死亡人数", "死亡人口", "遇难人数"],
        "trip_count": ["行程数", "行程量", "出行量", "订单数"],
        "parking_violation_count": ["罚单数量", "停车罚单数量", "违章数量", "停车违章数量"],
        "crash_count": ["事故数", "事故数量", "碰撞数量"],
    }

    # ── 关键词组合表：需同时出现的词组才触发命中 ──
    # 每个元素是一个 tuple，tuple 中所有词必须同时出现在问题中才算命中。
    # 单元素 tuple 如 ("受伤",) 表示该词本身已足够特异，无需搭配其他词。
    # 多元素 tuple 如 ("平均", "距离") 防止"平均"或"距离"单独出现时误匹配。
    _KEYWORDS: dict[str, list[tuple[str, ...]]] = {
        "standard_fine_total": [("罚款", "总额"), ("罚金", "总额")],
        "total_fare_amount": [("车费", "总额"), ("车费", "收入")],
        "avg_distance_miles": [("平均", "距离"), ("平均", "里程")],
        "persons_injured": [("受伤",), ("伤者",)],
        "persons_killed": [("死亡",), ("遇难",)],
        "trip_count": [("行程",), ("出行",), ("订单",)],
        "parking_violation_count": [("停车", "罚单"), ("违章",)],
        "crash_count": [("事故",), ("碰撞",)],
    }

    # ── 金额歧义触发词 ──
    # 当问题包含这些词但未指定具体口径（车费/罚金）时，触发金额歧义反问。
    # "多少钱"和"收入"也需要纳入，因为用户常说"每天多少钱"或"每天收入"。
    _AMOUNT_WORDS = ("金额", "费用", "多少钱", "收入")

    def __init__(self, metrics: list[MetricInfo], aliases: dict[str, list[str]] | None = None):
        self._metrics = [metric for metric in metrics if metric.g3_available]
        self._aliases = aliases or {}

    def resolve(self, question: str) -> MetricMatchResult:
        """解析问题中的 G3 指标。

        决策流程（按优先级依次判断）：

        1. 金额歧义优先拦截
           ——"金额是多少"这类问题有多个金额类指标候选（车费 vs 罚金），
           必须先反问而非走常规候选匹配，否则可能在前一步被关键词误匹配。

        2. 无候选 → 反问用户重新描述

        3. 多候选且置信度差距 < 0.12 → 反问用户选择
           ——0.12 的阈值来自经验调优：太大会导致可区分场景也被反问（过度保守），
           太小会导致真正歧义场景被放过（误答）。实际数据中同义词命中(0.93)
           和关键词命中(0.82)差 0.11，设 0.12 可在两者之间建立缓冲区。

        4. 唯一候选 → 返回命中结果
        """
        candidates = self._collect_candidates(question)

        # ── 优先级 1: 金额歧义必须先于常规候选匹配 ──
        # 即使常规匹配也命中了某个金额指标，仍需要反问确认。
        # 因为用户说"金额"时可能指车费也可能指罚金，猜错了后果严重。
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

    def _collect_candidates(self, question: str) -> list[MetricCandidate]:
        """按优先级降级收集候选指标。

        匹配优先级链（高→低，命中即停止，不降级）：
            metric_name  → 1.00   用户直接说出了英文指标名（如 "persons_injured"）
            zh_name      → 0.98   用户说出了注册的中文名（精确匹配）
            synonym      → 0.93   用户用了同义词（如"罚款总额"→standard_fine_total）
            alias        → 0.90   命中配置文件中运维新增的别名
            keyword      → 0.82   命中关键词组合（最低置信度，最宽泛）

        优先级设计理由：
            - metric_name/zh_name 几乎零误匹配概率 → 最高置信度
            - synonym 是同义语言学映射，稳定性高 → 次高
            - alias 来自运维配置，可能存在质量差异 → 中等置信度
            - keyword 依赖词组组合，边界情况最多 → 最低置信度

        使用 dict 去重：同一指标名只会保留首次（最高优先级）命中结果。
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
            # 优先级 3: 同义词匹配
            synonym = self._match_synonym(metric.name, question)
            if synonym:
                result[metric.name] = MetricCandidate(metric, 0.93, "synonym", [synonym])
                continue
            # 优先级 4: 运维配置别名匹配
            alias = self._match_alias(metric.name, question)
            if alias:
                result[metric.name] = MetricCandidate(metric, 0.9, "alias", [alias])
                continue
            # 优先级 5: 关键词组合匹配（最宽泛，最后尝试）
            keywords = self._match_keywords(metric.name, question)
            if keywords:
                result[metric.name] = MetricCandidate(metric, 0.82, "keyword", list(keywords))
        return list(result.values())

    def _match_synonym(self, metric_name: str, question: str) -> str | None:
        """匹配指标同义词。"""
        for term in self._SYNONYMS.get(metric_name, []):
            if term in question:
                return term
        return None

    def _match_alias(self, metric_name: str, question: str) -> str | None:
        """匹配配置或契约补充的指标别名。"""
        question_lower = question.lower()
        for term in self._aliases.get(metric_name, []):
            if term and term.lower() in question_lower:
                return term
        return None

    def _match_keywords(self, metric_name: str, question: str) -> tuple[str, ...] | None:
        """匹配关键词组合。"""
        for group in self._KEYWORDS.get(metric_name, []):
            if all(term in question for term in group):
                return group
        return None

    def _looks_like_ambiguous_amount(self, question: str) -> bool:
        """识别未限定口径的金额类问题。

        判断逻辑：
            1. 问题包含金额类词（"金额"/"费用"/"多少钱"/"收入"）
            2. 且问题中没有出现任何具体口径词（如"车费总额"/"罚款总额"等 _SYNONYMS 中的词）

        设计理由：
            "金额是多少"在系统中有多个金额类指标（total_fare_amount 和 standard_fine_total），
            不能猜测用户意图，必须反问。但如果用户说了"车费金额"（包含具体同义词"车费金额"），
            则不算歧义——因为同义词表会将"车费金额"映射到 total_fare_amount。
        """
        if not any(word in question for word in self._AMOUNT_WORDS):
            return False
        # 收集所有具体口径词（排除金额类通用词自身，避免循环判断）
        concrete_terms = [
            term
            for terms in self._SYNONYMS.values()
            for term in terms
            if term not in self._AMOUNT_WORDS
        ]
        # 如果至少命中了一个具体口径词，说明用户已经限定了范围，不算歧义
        return not any(term in question for term in concrete_terms)

    def _amount_candidates(self) -> list[MetricCandidate]:
        """返回当前 G3 指标中的金额类候选。

        硬编码金额类指标名集合，因为金额语义与业务强相关，不适合从配置文件中泛化推导。
        置信度 0.72 比关键词组合(0.82)更低——因为"金额"的语义粒度比关键词更模糊。
        """
        amount_metric_names = {"total_fare_amount", "standard_fine_total"}
        return [
            MetricCandidate(metric, 0.72, "keyword", ["金额"])
            for metric in self._metrics
            if metric.name in amount_metric_names
        ]

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
