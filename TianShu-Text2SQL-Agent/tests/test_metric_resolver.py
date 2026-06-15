from __future__ import annotations

from src.metric_resolver import MetricResolver
from src.resolver import MetricInfo


def _metrics() -> list[MetricInfo]:
    """构造覆盖 G3 与非 G3 的指标目录。"""
    return [
        MetricInfo("trip_count", "行程量", "traffic", "sum(trip_count)", "gold.dws_daily_trip_summary", "次", True),
        MetricInfo("total_fare_amount", "基础车费总额", "traffic", "sum(total_fare_amount)", "gold.dws_daily_trip_summary", "美元", True),
        MetricInfo("avg_distance_miles", "平均行程距离", "traffic", "avg(avg_distance_miles)", "gold.dws_daily_trip_summary", "英里", True),
        MetricInfo("standard_fine_total", "标准罚款总额", "violation", "sum(standard_fine_total)", "gold.dws_daily_parking_summary", "美元", True),
        MetricInfo("persons_injured", "受伤人数", "safety", "sum(persons_injured)", "gold.dws_daily_crash_summary", "人", True),
        MetricInfo("persons_killed", "死亡人数", "safety", "sum(persons_killed)", "gold.dws_daily_crash_summary", "人", True),
        MetricInfo("driver_application_count", "司机申请量", "supply", "count(*)", "gold.fact_driver_applications", "次", False),
    ]


def test_resolves_metric_by_chinese_name():
    """中文指标名应直接命中注册指标。"""
    result = MetricResolver(_metrics()).resolve("2026年3月每天受伤人数是多少？")

    assert result.matched is True
    assert result.metric.name == "persons_injured"
    assert result.ambiguous is False
    assert result.confidence >= 0.95


def test_resolves_metric_by_english_name():
    """英文 metric name 应直接命中注册指标。"""
    result = MetricResolver(_metrics()).resolve("2026年3月每天 persons_injured 是多少？")

    assert result.matched is True
    assert result.metric.name == "persons_injured"
    assert result.candidates[0].matched_by == "metric_name"


def test_resolves_metric_by_synonym():
    """同义词应映射到注册指标，而不是在 Agent 中堆 if。"""
    result = MetricResolver(_metrics()).resolve("2026年2月每天罚款总额是多少？")

    assert result.matched is True
    assert result.metric.name == "standard_fine_total"
    assert result.candidates[0].matched_by == "synonym"


def test_resolves_metric_by_keyword():
    """关键词组合应支持常见自然表达。"""
    result = MetricResolver(_metrics()).resolve("2026年1月每天平均距离是多少？")

    assert result.matched is True
    assert result.metric.name == "avg_distance_miles"
    assert result.candidates[0].matched_by == "keyword"


def test_unmatched_metric_returns_clarification():
    """匹配不到注册指标时应反问。"""
    result = MetricResolver(_metrics()).resolve("2026年1月每天拥堵指数是多少？")

    assert result.matched is False
    assert result.ambiguous is False
    assert "暂未识别" in result.clarification_message


def test_ambiguous_amount_returns_clarification():
    """金额类弱表达命中多个指标时必须反问，不能猜测。"""
    result = MetricResolver(_metrics()).resolve("2026年1月每天金额是多少？")

    assert result.matched is False
    assert result.ambiguous is True
    assert {candidate.metric.name for candidate in result.candidates} >= {
        "total_fare_amount",
        "standard_fine_total",
    }
    assert "请明确" in result.clarification_message


def test_only_g3_available_metrics_are_returned():
    """规则版本轮只允许返回 G3 可用指标。"""
    result = MetricResolver(_metrics()).resolve("2026年1月每天司机申请量是多少？")

    assert result.matched is False
    assert all(candidate.metric.g3_available for candidate in result.candidates)
