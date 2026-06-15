"""注册指标解析器。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .resolver import MetricInfo


@dataclass(frozen=True)
class MetricCandidate:
    """单个指标候选及其命中证据。"""

    metric: MetricInfo
    confidence: float
    matched_by: str
    matched_terms: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MetricMatchResult:
    """指标解析结果。"""

    matched: bool
    metric: MetricInfo | None = None
    confidence: float = 0.0
    ambiguous: bool = False
    candidates: list[MetricCandidate] = field(default_factory=list)
    clarification_message: str | None = None
    failure_reason: str | None = None


class MetricResolver:
    """基于注册指标目录解析用户问题中的指标。"""

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
    _AMOUNT_WORDS = ("金额", "费用", "多少钱", "收入")

    def __init__(self, metrics: list[MetricInfo], aliases: dict[str, list[str]] | None = None):
        self._metrics = [metric for metric in metrics if metric.g3_available]
        self._aliases = aliases or {}

    def resolve(self, question: str) -> MetricMatchResult:
        """解析问题中的 G3 指标。"""
        candidates = self._collect_candidates(question)
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

        if not candidates:
            return MetricMatchResult(
                matched=False,
                candidates=[],
                clarification_message=self._unmatched_message(),
                failure_reason="metric_not_found",
            )

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

        return MetricMatchResult(
            matched=True,
            metric=top.metric,
            confidence=top.confidence,
            ambiguous=False,
            candidates=candidates,
        )

    def _collect_candidates(self, question: str) -> list[MetricCandidate]:
        """按优先级收集候选指标。"""
        result: dict[str, MetricCandidate] = {}
        question_lower = question.lower()
        for metric in self._metrics:
            if metric.name.lower() in question_lower:
                result[metric.name] = MetricCandidate(metric, 1.0, "metric_name", [metric.name])
                continue
            if metric.zh_name and metric.zh_name in question:
                result[metric.name] = MetricCandidate(metric, 0.98, "zh_name", [metric.zh_name])
                continue
            synonym = self._match_synonym(metric.name, question)
            if synonym:
                result[metric.name] = MetricCandidate(metric, 0.93, "synonym", [synonym])
                continue
            alias = self._match_alias(metric.name, question)
            if alias:
                result[metric.name] = MetricCandidate(metric, 0.9, "alias", [alias])
                continue
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
        """识别未限定口径的金额类问题。"""
        if not any(word in question for word in self._AMOUNT_WORDS):
            return False
        concrete_terms = [
            term
            for terms in self._SYNONYMS.values()
            for term in terms
            if term not in self._AMOUNT_WORDS
        ]
        return not any(term in question for term in concrete_terms)

    def _amount_candidates(self) -> list[MetricCandidate]:
        """返回当前 G3 指标中的金额类候选。"""
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
