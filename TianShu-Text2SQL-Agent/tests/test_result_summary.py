"""
Phase B1：ResultSummary / MergedResult 测试。

覆盖：
    - 单个结果摘要（字段正确性）
    - date 列识别（有 date 列 / 无 date 列）
    - date_min/date_max 正确性
    - grain 检测（daily vs unknown）
    - 多计划摘要（每天行程数和受伤人数）
    - MergedResult 初始状态
"""

import datetime as _dt

import pytest

from src.ir import (
    MergeStatus,
    MergedResult,
    ResultSummary,
    SQLPlan,
    SQLResult,
    Strategy,
    SubIntent,
    Domain,
    Aggregation,
    JoinPlan,
    UnifiedResponse,
)
from src.result_summary import (
    make_merged_result,
    summarize_sql_result,
    _find_date_column,
    _extract_date_values,
    _detect_grain,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_daily_result(rows=None, columns=None, column_types=None):
    """构造标准的日粒度 SQLResult（31 行，date + metric）"""
    if columns is None:
        columns = ["date", "trip_count"]
    if column_types is None:
        column_types = ["TIMESTAMP", "HUGEINT"]
    if rows is None:
        rows = [
            (_dt.datetime(2026, 1, d, 0, 0), 800000 + d * 1000)
            for d in range(1, 32)
        ]
    return SQLResult(
        sql="SELECT mock FROM gold.dws_daily_trip_summary",
        columns=columns,
        column_types=column_types,
        rows=rows,
        row_count=len(rows),
        execution_time_ms=5.0,
        source_table="gold.dws_daily_trip_summary",
    )


def _make_unified_response(result=None, metrics=None, dimensions=None,
                           planning_table="gold.dws_daily_trip_summary",
                           strategy=Strategy.G3_DIRECT):
    """构造标准 UnifiedResponse"""
    if metrics is None:
        metrics = ["trip_count"]
    if dimensions is None:
        dimensions = ["date"]
    return UnifiedResponse(
        sub_intent=SubIntent(
            metrics=metrics,
            domain=Domain.TRAFFIC,
            planning_table=planning_table,
            dimensions=dimensions,
        ),
        plan=SQLPlan(
            strategy=strategy,
            primary_table=planning_table,
            aggregations=[Aggregation(expr="SUM(trip_count)", alias=metrics[0])],
        ),
        result=result,
    )


# ═══════════════════════════════════════════════════════════════
# 单结果摘要测试
# ═══════════════════════════════════════════════════════════════


class TestSingleResultSummary:
    """单个 SQLResult → ResultSummary"""

    def test_row_count_correct(self):
        """row_count 正确"""
        result = _make_daily_result()
        ur = _make_unified_response(result=result)
        summary = summarize_sql_result(ur, plan_index=1)

        assert summary.row_count == 31
        assert summary.source_plan_index == 1

    def test_columns_correct(self):
        """columns 和 column_types 正确复制"""
        result = _make_daily_result(
            columns=["date", "trip_count", "avg_fare"],
            column_types=["TIMESTAMP", "HUGEINT", "DOUBLE"],
            rows=[(_dt.datetime(2026, 1, 1, 0, 0), 1000, 12.5)],
        )
        ur = _make_unified_response(result=result)
        summary = summarize_sql_result(ur)

        assert summary.columns == ["date", "trip_count", "avg_fare"]
        assert summary.column_types == ["TIMESTAMP", "HUGEINT", "DOUBLE"]

    def test_metrics_correct(self):
        """metrics 从 SubIntent 正确提取"""
        result = _make_daily_result()
        ur = _make_unified_response(
            result=result,
            metrics=["persons_injured", "persons_killed"],
        )
        summary = summarize_sql_result(ur)

        assert summary.metrics == ["persons_injured", "persons_killed"]

    def test_primary_table_correct(self):
        """primary_table 和 strategy 正确提取"""
        result = _make_daily_result()
        ur = _make_unified_response(
            result=result,
            planning_table="gold.dws_daily_crash_summary",
            strategy=Strategy.G2_FACT,
        )
        summary = summarize_sql_result(ur)

        assert summary.primary_table == "gold.dws_daily_crash_summary"
        assert summary.strategy == "g2_fact"

    def test_sample_rows_extracted(self):
        """sample_rows 包含前 5 行，日期序列化为 ISO 字符串"""
        result = _make_daily_result()
        ur = _make_unified_response(result=result)
        summary = summarize_sql_result(ur)

        assert len(summary.sample_rows) == 5
        # 日期应为 ISO 格式
        assert summary.sample_rows[0][0] == "2026-01-01T00:00:00"
        assert isinstance(summary.sample_rows[0][1], int)

    def test_sample_rows_respects_max(self):
        """sample_rows 不超过 5 行（即使原始数据只有 3 行）"""
        result = _make_daily_result(rows=[
            (_dt.datetime(2026, 1, d, 0, 0), d * 10) for d in range(1, 4)
        ])
        ur = _make_unified_response(result=result)
        summary = summarize_sql_result(ur)

        assert len(summary.sample_rows) == 3

    def test_null_result_returns_empty_summary(self):
        """result=None → 空摘要，含警告"""
        ur = _make_unified_response(result=None)
        summary = summarize_sql_result(ur)

        assert summary.row_count == 0
        assert summary.columns == []
        assert summary.sample_rows == []
        assert len(summary.warnings) > 0
        assert "result=None" in summary.warnings[0]

    def test_zero_row_result_has_warning(self):
        """row_count=0 时产生警告"""
        result = SQLResult(
            sql="SELECT mock",
            columns=["date", "trip_count"],
            column_types=["TIMESTAMP", "HUGEINT"],
            rows=[],
            row_count=0,
        )
        ur = _make_unified_response(result=result)
        summary = summarize_sql_result(ur)

        assert summary.row_count == 0
        assert any("结果为空" in w for w in summary.warnings)


# ═══════════════════════════════════════════════════════════════
# date 列识别测试
# ═══════════════════════════════════════════════════════════════


class TestDateColumnDetection:
    """日期列的识别、范围提取和粒度检测"""

    def test_has_date_column_true(self):
        """结果有 date 列时 has_date_column=True"""
        result = _make_daily_result()
        ur = _make_unified_response(result=result)
        summary = summarize_sql_result(ur)

        assert summary.has_date_column is True

    def test_date_min_max_correct(self):
        """date_min 和 date_max 正确"""
        result = _make_daily_result()
        ur = _make_unified_response(result=result)
        summary = summarize_sql_result(ur)

        assert summary.date_min == "2026-01-01"
        assert summary.date_max == "2026-01-31"

    def test_grain_daily_detected(self):
        """连续 31 天 → grain=daily"""
        result = _make_daily_result()
        ur = _make_unified_response(result=result)
        summary = summarize_sql_result(ur)

        assert summary.grain == "daily"

    def test_grain_daily_7_days(self):
        """连续 7 天也是 daily"""
        rows = [(_dt.datetime(2026, 1, d, 0, 0), d) for d in range(1, 8)]
        result = _make_daily_result(rows=rows)
        ur = _make_unified_response(result=result)
        summary = summarize_sql_result(ur)

        assert summary.grain == "daily"
        assert summary.date_min == "2026-01-01"
        assert summary.date_max == "2026-01-07"

    def test_grain_unknown_single_row(self):
        """只有 1 行 → grain=unknown"""
        rows = [(_dt.datetime(2026, 1, 15, 0, 0), 100)]
        result = _make_daily_result(rows=rows)
        ur = _make_unified_response(result=result)
        summary = summarize_sql_result(ur)

        assert summary.has_date_column is True
        assert summary.grain == "unknown"

    def test_grain_unknown_gap(self):
        """日期有间隔 → grain=unknown"""
        rows = [
            (_dt.datetime(2026, 1, 1, 0, 0), 100),
            (_dt.datetime(2026, 1, 3, 0, 0), 200),  # 跳过了 1/2
            (_dt.datetime(2026, 1, 5, 0, 0), 300),
        ]
        result = _make_daily_result(rows=rows)
        ur = _make_unified_response(result=result)
        summary = summarize_sql_result(ur)

        assert summary.grain == "unknown"

    def test_date_column_by_name_fallback(self):
        """列类型不匹配时，按列名 'date' 回退检测"""
        result = SQLResult(
            sql="SELECT mock",
            columns=["some_date", "value"],
            column_types=["VARCHAR", "INTEGER"],  # 类型不匹配
            rows=[("2026-01-01", 100), ("2026-01-02", 200)],
            row_count=2,
        )
        ur = _make_unified_response(result=result)
        summary = summarize_sql_result(ur)

        assert summary.has_date_column is True

    def test_date_column_by_type_timestamp(self):
        """TIMESTAMP 类型被正确识别为日期列"""
        result = _make_daily_result(
            columns=["ts", "val"],
            column_types=["TIMESTAMP", "INTEGER"],
        )
        ur = _make_unified_response(result=result)
        summary = summarize_sql_result(ur)

        assert summary.has_date_column is True
        assert summary.date_min == "2026-01-01"


# ═══════════════════════════════════════════════════════════════
# 无 date 列测试
# ═══════════════════════════════════════════════════════════════


class TestNoDateColumn:
    """结果无日期列时的行为"""

    def test_no_date_column_has_date_false(self):
        """无 date 列时 has_date_column=False"""
        result = SQLResult(
            sql="SELECT mock",
            columns=["borough", "count"],
            column_types=["VARCHAR", "INTEGER"],
            rows=[("Manhattan", 500), ("Brooklyn", 300)],
            row_count=2,
        )
        ur = _make_unified_response(result=result)
        summary = summarize_sql_result(ur)

        assert summary.has_date_column is False
        assert summary.grain == "unknown"
        assert summary.date_min == ""
        assert summary.date_max == ""

    def test_only_metric_columns_no_date(self):
        """仅有指标列（无 date/无 TIMESTAMP）"""
        result = _make_daily_result(
            columns=["borough", "avg_fare"],
            column_types=["VARCHAR", "DOUBLE"],
            rows=[("Manhattan", 12.5)],
        )
        ur = _make_unified_response(result=result)
        summary = summarize_sql_result(ur)

        assert summary.has_date_column is False
        assert summary.grain == "unknown"

    def test_empty_rows_no_date(self):
        """空结果无 date 列"""
        result = SQLResult(
            sql="SELECT mock",
            columns=["value"],
            column_types=["INTEGER"],
            rows=[],
            row_count=0,
        )
        ur = _make_unified_response(result=result)
        summary = summarize_sql_result(ur)

        assert summary.has_date_column is False
        assert summary.grain == "unknown"
        assert summary.date_min == ""
        assert summary.date_max == ""


# ═══════════════════════════════════════════════════════════════
# 多计划结果摘要测试
# ═══════════════════════════════════════════════════════════════


class TestMultiPlanSummary:
    """多个 UnifiedResponse → 各自生成 ResultSummary"""

    def test_each_plan_gets_summary(self):
        """每天行程数和受伤人数 → 每个计划都可以生成摘要"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天行程数和受伤人数分别是多少？")

        assert response.is_multi_plan
        assert len(response.plans) == 2

        summaries: list[ResultSummary] = []
        for i, ur in enumerate(response.plans):
            summary = summarize_sql_result(ur, plan_index=i + 1)
            summaries.append(summary)

        # 两个摘要都成功生成
        for s in summaries:
            assert s.row_count > 0
            assert len(s.columns) > 0

    def test_source_plan_index_stable(self):
        """source_plan_index 保持稳定"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天行程数和受伤人数分别是多少？")

        assert response.is_multi_plan

        for i, ur in enumerate(response.plans):
            summary = summarize_sql_result(ur, plan_index=i + 1)
            assert summary.source_plan_index == i + 1

    def test_different_tables_have_different_primary(self):
        """不同表的摘要 primary_table 不同"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天行程数和受伤人数分别是多少？")

        assert response.is_multi_plan
        tables = set()
        for ur in response.plans:
            summary = summarize_sql_result(ur)
            tables.add(summary.primary_table)

        # 两个计划应来自不同表
        assert len(tables) == 2

    def test_both_summaries_have_date_column(self):
        """两个计划的摘要都有 date 列（日粒度查询）"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天行程数和受伤人数分别是多少？")

        for ur in response.plans:
            summary = summarize_sql_result(ur)
            assert summary.has_date_column is True
            assert summary.grain == "daily"
            assert summary.date_min == "2026-01-01"
            assert summary.date_max == "2026-01-31"


# ═══════════════════════════════════════════════════════════════
# MergedResult 初始状态测试
# ═══════════════════════════════════════════════════════════════


class TestMergedResultInitialState:
    """MergedResult 默认状态：不做真正合并"""

    def test_default_status_not_attempted(self):
        """默认 merge_status=not_attempted"""
        merged = make_merged_result([])
        assert merged.merge_status == MergeStatus.NOT_ATTEMPTED
        assert merged.row_count == 0
        assert merged.merge_key == ""
        assert merged.columns == []
        assert merged.rows == []

    def test_source_summaries_traceable(self):
        """source_summaries 保留所有来源摘要，可追溯"""
        summary1 = ResultSummary(
            source_plan_index=1,
            metrics=["trip_count"],
            primary_table="gold.dws_daily_trip_summary",
            row_count=31,
        )
        summary2 = ResultSummary(
            source_plan_index=2,
            metrics=["persons_injured"],
            primary_table="gold.dws_daily_crash_summary",
            row_count=31,
        )

        merged = make_merged_result(
            [summary1, summary2],
            merge_status=MergeStatus.SKIPPED,
            reason="Phase B1 预留，未执行实际合并",
        )

        assert merged.merge_status == MergeStatus.SKIPPED
        assert len(merged.source_summaries) == 2
        assert merged.source_plan_indexes == [1, 2]
        assert merged.row_count == 62  # 31 + 31 行数之和
        assert merged.source_summaries[0].metrics == ["trip_count"]
        assert merged.source_summaries[1].primary_table == "gold.dws_daily_crash_summary"
        assert "Phase B1" in merged.reason

    def test_make_merged_result_from_e2e(self):
        """E2E：从真实查询构造 MergedResult"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天行程数和受伤人数分别是多少？")

        summaries = [
            summarize_sql_result(ur, plan_index=i + 1)
            for i, ur in enumerate(response.plans)
        ]

        merged = make_merged_result(
            summaries,
            merge_status=MergeStatus.SKIPPED,
            reason="Phase B1：数据结构预留",
        )

        assert merged.merge_status == MergeStatus.SKIPPED
        assert len(merged.source_summaries) == 2
        assert merged.source_plan_indexes == [1, 2]
        # 每个来源都可追溯
        for s in merged.source_summaries:
            assert s.row_count > 0
            assert s.has_date_column is True
            assert s.grain == "daily"

    def test_merge_status_skipped_explicit(self):
        """显式标记 SKIPPED 且带原因"""
        merged = make_merged_result(
            [],
            merge_status=MergeStatus.SKIPPED,
            reason="无 date 列，跳过合并",
        )
        assert merged.merge_status == MergeStatus.SKIPPED
        assert "跳过合并" in merged.reason

    def test_merge_status_failed_skeleton(self):
        """FAILED 状态骨架（为 Phase 3C 预留）"""
        merged = MergedResult(
            merge_status=MergeStatus.FAILED,
            reason="grain 不一致：daily vs weekly",
            merge_warnings=["grain_mismatch"],
        )
        assert merged.merge_status == MergeStatus.FAILED
        assert "grain 不一致" in merged.reason
        assert "grain_mismatch" in merged.merge_warnings


# ═══════════════════════════════════════════════════════════════
# 辅助函数单元测试
# ═══════════════════════════════════════════════════════════════


class TestHelperFunctions:
    """内部辅助函数的单元测试"""

    def test_find_date_column_by_type(self):
        """按类型检测 TIMESTAMP 列"""
        idx = _find_date_column(
            ["borough", "crash_date", "injured"],
            ["VARCHAR", "TIMESTAMP", "INTEGER"],
        )
        assert idx == 1

    def test_find_date_column_by_type_date(self):
        """按类型检测 DATE 列"""
        idx = _find_date_column(
            ["val", "d"],
            ["INTEGER", "DATE"],
        )
        assert idx == 1

    def test_find_date_column_fallback_name(self):
        """按列名回退检测"""
        idx = _find_date_column(
            ["val", "report_date", "cnt"],
            ["INTEGER", "VARCHAR", "INTEGER"],  # 类型不匹配
        )
        assert idx == 1

    def test_find_date_column_none(self):
        """无任何日期特征"""
        idx = _find_date_column(
            ["name", "count"],
            ["VARCHAR", "INTEGER"],
        )
        assert idx is None

    def test_detect_grain_daily(self):
        """连续日期 → daily"""
        dates = [_dt.date(2026, 1, d) for d in range(1, 8)]
        assert _detect_grain(dates) == "daily"

    def test_detect_grain_single(self):
        """单行 → unknown"""
        assert _detect_grain([_dt.date(2026, 1, 1)]) == "unknown"

    def test_detect_grain_gap(self):
        """有间隔 → unknown"""
        dates = [
            _dt.date(2026, 1, 1),
            _dt.date(2026, 1, 3),
            _dt.date(2026, 1, 5),
        ]
        assert _detect_grain(dates) == "unknown"

    def test_extract_date_values_from_timestamp(self):
        """从 TIMESTAMP 列提取日期值"""
        rows = [
            (_dt.datetime(2026, 1, 1, 0, 0), 100),
            (_dt.datetime(2026, 1, 2, 0, 0), 200),
        ]
        dates = _extract_date_values(rows, 0)
        assert len(dates) == 2
        assert dates[0] == _dt.date(2026, 1, 1)
        assert dates[1] == _dt.date(2026, 1, 2)

    def test_extract_date_values_skip_invalid(self):
        """跳过无效日期值"""
        rows = [
            ("not_a_date", 100),
            (_dt.date(2026, 1, 2), 200),
        ]
        dates = _extract_date_values(rows, 0)
        # "not_a_date" 无法解析 → 跳过
        assert len(dates) == 1
        assert dates[0] == _dt.date(2026, 1, 2)
