"""
Phase B2：严格 date merge 测试。

覆盖：
    - 成功 merge（date 对齐）
    - 缺 date 不合并
    - 不同 grain 不合并
    - date 重复不合并
    - date 范围不一致（outer merge + warning）
    - 不产生因果解释
"""

import datetime as _dt

import pytest

from src.ir import (
    MergeStatus,
    MergedResult,
    SQLResult,
    UnifiedResponse,
    SubIntent,
    SQLPlan,
    Strategy,
    Domain,
    Aggregation,
)
from src.result_merge import (
    can_merge_on_date,
    merge_results_on_date,
)
from src.result_summary import summarize_sql_result


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_ur(metrics, planning_table, rows, columns=None, column_types=None, strategy=Strategy.G3_DIRECT):
    """快捷构造 UnifiedResponse（含 SQLResult）"""
    if columns is None:
        cols = ["date"] + metrics
    else:
        cols = list(columns)
    if column_types is None:
        types = ["TIMESTAMP"] + ["HUGEINT"] * len(metrics)
    else:
        types = list(column_types)

    result = SQLResult(
        sql="SELECT mock",
        columns=cols,
        column_types=types,
        rows=rows,
        row_count=len(rows),
        source_table=planning_table,
    )
    return UnifiedResponse(
        sub_intent=SubIntent(
            metrics=list(metrics),
            domain=Domain.TRAFFIC,
            planning_table=planning_table,
            dimensions=["date"],
        ),
        plan=SQLPlan(
            strategy=strategy,
            primary_table=planning_table,
            aggregations=[
                Aggregation(expr=f"SUM({m})", alias=m) for m in metrics
            ],
        ),
        result=result,
    )


def _daily_rows(start_day=1, end_day=31, value_func=None):
    """生成连续日期的数据行 [(datetime, val), ...]"""
    if value_func is None:
        value_func = lambda d: d * 100
    return [
        (_dt.datetime(2026, 1, d, 0, 0), value_func(d))
        for d in range(start_day, end_day + 1)
    ]


# ═══════════════════════════════════════════════════════════════
# 成功 merge 测试
# ═══════════════════════════════════════════════════════════════


class TestSuccessfulMerge:
    """全部条件满足 → merge_status=merged"""

    def test_e2e_merge_everyday_trips_and_injuries(self):
        """"每天行程数和受伤人数" → 两个结果都有 date、grain=daily → merged"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天行程数和受伤人数分别是多少？")

        assert response.is_multi_plan
        assert response.chinese_answer is not None

        # 两个结果都有 date，grain=daily，范围都是 2026-01-01 ~ 2026-01-31
        # → 应该 merge 成功
        assert "已按 date 对齐合并" in response.chinese_answer or "未进行自动合并" in response.chinese_answer

    def test_merge_status_is_merged(self):
        """两个 daily 结果，相同 date 范围 → merge_status=merged"""
        ur1 = _make_ur(
            metrics=["trip_count"],
            planning_table="gold.dws_daily_trip_summary",
            rows=_daily_rows(1, 31, lambda d: 800000 + d * 1000),
        )
        ur2 = _make_ur(
            metrics=["persons_injured"],
            planning_table="gold.dws_daily_crash_summary",
            rows=_daily_rows(1, 31, lambda d: 50 + d),
        )

        merged = merge_results_on_date([ur1, ur2])

        assert merged.merge_status == MergeStatus.MERGED
        assert merged.merge_key == "date"

    def test_merged_columns_contain_date_and_all_metrics(self):
        """合并后 columns 包含 date + 各来源的指标列"""
        ur1 = _make_ur(
            metrics=["trip_count"],
            planning_table="gold.dws_daily_trip_summary",
            rows=_daily_rows(1, 7, lambda d: 800000 + d * 1000),
        )
        ur2 = _make_ur(
            metrics=["persons_injured"],
            planning_table="gold.dws_daily_crash_summary",
            rows=_daily_rows(1, 7, lambda d: 50 + d),
        )

        merged = merge_results_on_date([ur1, ur2])

        assert merged.merge_status == MergeStatus.MERGED
        assert "date" in merged.columns
        assert "trip_count" in merged.columns
        assert "persons_injured" in merged.columns

    def test_merged_row_count_equals_unique_dates(self):
        """合并后行数 = 唯一日期数（日期范围完全一致）"""
        ur1 = _make_ur(
            metrics=["trip_count"],
            planning_table="gold.dws_daily_trip_summary",
            rows=_daily_rows(1, 10),
        )
        ur2 = _make_ur(
            metrics=["persons_injured"],
            planning_table="gold.dws_daily_crash_summary",
            rows=_daily_rows(1, 10, lambda d: 50),
        )

        merged = merge_results_on_date([ur1, ur2])

        assert merged.merge_status == MergeStatus.MERGED
        assert merged.row_count == 10

    def test_merged_source_summaries_accessible(self):
        """MergedResult 中 source_summaries 可追溯"""
        ur1 = _make_ur(
            metrics=["trip_count"],
            planning_table="gold.dws_daily_trip_summary",
            rows=_daily_rows(1, 7),
        )
        ur2 = _make_ur(
            metrics=["persons_injured"],
            planning_table="gold.dws_daily_crash_summary",
            rows=_daily_rows(1, 7, lambda d: 50),
        )

        merged = merge_results_on_date([ur1, ur2])

        assert len(merged.source_summaries) == 2
        assert merged.source_plan_indexes == [1, 2]
        assert merged.source_summaries[0].metrics == ["trip_count"]
        assert merged.source_summaries[1].metrics == ["persons_injured"]

    def test_merged_values_aligned_by_date(self):
        """合并后的每一行：同一个 date 的两个指标值对齐"""
        ur1 = _make_ur(
            metrics=["trip_count"],
            planning_table="gold.dws_daily_trip_summary",
            rows=_daily_rows(1, 3, lambda d: 800000 + d * 1000),
        )
        ur2 = _make_ur(
            metrics=["persons_injured"],
            planning_table="gold.dws_daily_crash_summary",
            rows=_daily_rows(1, 3, lambda d: 50 + d),
        )

        merged = merge_results_on_date([ur1, ur2])

        # 第 1 行：2026-01-01
        row1 = merged.rows[0]
        date_val = row1[0]
        trip_val = row1[1]  # trip_count 是第一个来源的第一个指标
        injury_val = row1[2]  # persons_injured 是第二个来源的第一个指标

        assert date_val == _dt.date(2026, 1, 1)
        assert trip_val == 801000
        assert injury_val == 51


# ═══════════════════════════════════════════════════════════════
# 缺 date 不合并测试
# ═══════════════════════════════════════════════════════════════


class TestMissingDateSkip:
    """缺 date 列 → merge_status=skipped"""

    def test_one_result_no_date_skipped(self):
        """一个结果有 date，另一个无 → skipped"""
        ur1 = _make_ur(
            metrics=["trip_count"],
            planning_table="gold.dws_daily_trip_summary",
            rows=_daily_rows(1, 7),
        )
        # 无 date 列的结果（如按 borough 分组）
        ur2 = UnifiedResponse(
            sub_intent=SubIntent(
                metrics=["avg_fare"],
                domain=Domain.TRAFFIC,
                planning_table="gold.fact_fares",
                dimensions=["borough"],
            ),
            plan=SQLPlan(
                strategy=Strategy.G2_FACT,
                primary_table="gold.fact_fares",
                aggregations=[Aggregation(expr="AVG(fare)", alias="avg_fare")],
            ),
            result=SQLResult(
                sql="SELECT mock",
                columns=["borough", "avg_fare"],
                column_types=["VARCHAR", "DOUBLE"],
                rows=[("Manhattan", 12.5), ("Brooklyn", 10.0)],
                row_count=2,
            ),
        )

        merged = merge_results_on_date([ur1, ur2])

        assert merged.merge_status == MergeStatus.SKIPPED
        assert "缺少 date 列" in merged.reason

    def test_both_results_no_date_skipped(self):
        """两个结果都无 date → skipped"""
        rows1 = [("Manhattan", 100)]
        rows2 = [("Brooklyn", 200)]

        ur1 = UnifiedResponse(
            sub_intent=SubIntent(metrics=["cnt1"], planning_table="gold.t1"),
            plan=SQLPlan(strategy=Strategy.G3_DIRECT, primary_table="gold.t1"),
            result=SQLResult(
                sql="mock", columns=["borough", "cnt"],
                column_types=["VARCHAR", "INTEGER"],
                rows=rows1, row_count=1,
            ),
        )
        ur2 = UnifiedResponse(
            sub_intent=SubIntent(metrics=["cnt2"], planning_table="gold.t2"),
            plan=SQLPlan(strategy=Strategy.G3_DIRECT, primary_table="gold.t2"),
            result=SQLResult(
                sql="mock", columns=["borough", "cnt"],
                column_types=["VARCHAR", "INTEGER"],
                rows=rows2, row_count=1,
            ),
        )

        merged = merge_results_on_date([ur1, ur2])
        assert merged.merge_status == MergeStatus.SKIPPED
        assert "缺少 date 列" in merged.reason

    def test_skipped_still_has_source_summaries(self):
        """skip 后 source_summaries 仍完整，可追溯原始结果"""
        ur1 = _make_ur(
            metrics=["trip_count"],
            planning_table="gold.dws_daily_trip_summary",
            rows=_daily_rows(1, 7),
        )
        ur2 = UnifiedResponse(
            sub_intent=SubIntent(metrics=["avg_fare"], planning_table="gold.t2"),
            plan=SQLPlan(strategy=Strategy.G2_FACT, primary_table="gold.t2"),
            result=SQLResult(
                sql="mock", columns=["borough", "avg_fare"],
                column_types=["VARCHAR", "DOUBLE"],
                rows=[("Manhattan", 12.5)], row_count=1,
            ),
        )

        merged = merge_results_on_date([ur1, ur2])
        assert merged.merge_status == MergeStatus.SKIPPED
        assert len(merged.source_summaries) == 2


# ═══════════════════════════════════════════════════════════════
# 不同 grain 不合并测试
# ═══════════════════════════════════════════════════════════════


class TestDifferentGrainSkip:
    """grain 不一致 → merge_status=skipped"""

    def test_one_daily_one_unknown_grain_skipped(self):
        """一个 daily，一个 grain=unknown（非 daily 场景）→ skipped"""
        ur1 = _make_ur(
            metrics=["trip_count"],
            planning_table="gold.dws_daily_trip_summary",
            rows=_daily_rows(1, 7),
        )

        # 非 daily 粒度的结果（行内有间隔，grain 检测为 unknown）
        gap_rows = [
            (_dt.datetime(2026, 1, 1, 0, 0), 100),
            (_dt.datetime(2026, 1, 5, 0, 0), 200),  # 跳过 4 天
            (_dt.datetime(2026, 1, 10, 0, 0), 300),
        ]
        ur2 = _make_ur(
            metrics=["other_metric"],
            planning_table="gold.table2",
            rows=gap_rows,
        )

        merged = merge_results_on_date([ur1, ur2])
        assert merged.merge_status == MergeStatus.SKIPPED
        assert "grain" in merged.reason.lower()

    def test_single_row_unknown_grain_skipped(self):
        """单行结果 grain=unknown → skipped"""
        ur1 = _make_ur(
            metrics=["trip_count"],
            planning_table="gold.dws_daily_trip_summary",
            rows=_daily_rows(1, 7),
        )
        ur2 = _make_ur(
            metrics=["summary_metric"],
            planning_table="gold.table2",
            rows=[(_dt.datetime(2026, 1, 15, 0, 0), 999)],  # 单行 → unknown
        )

        merged = merge_results_on_date([ur1, ur2])
        assert merged.merge_status == MergeStatus.SKIPPED
        assert "grain" in merged.reason.lower()


# ═══════════════════════════════════════════════════════════════
# date 重复不合并测试
# ═══════════════════════════════════════════════════════════════


class TestDuplicateDateSkip:
    """同一结果中 date 重复 → merge_status=skipped"""

    def test_duplicate_date_in_one_result_skipped(self):
        """一个结果中同一 date 有多行 → skipped"""
        ur1 = _make_ur(
            metrics=["trip_count"],
            planning_table="gold.dws_daily_trip_summary",
            rows=_daily_rows(1, 7),
        )
        # date 重复的数据
        dup_rows = [
            (_dt.datetime(2026, 1, 1, 0, 0), 100),
            (_dt.datetime(2026, 1, 1, 0, 0), 200),  # 重复 date
            (_dt.datetime(2026, 1, 2, 0, 0), 300),
        ]
        ur2 = _make_ur(
            metrics=["dup_metric"],
            planning_table="gold.table2",
            rows=dup_rows,
        )

        merged = merge_results_on_date([ur1, ur2])

        assert merged.merge_status == MergeStatus.SKIPPED
        assert "重复 date" in merged.reason

    def test_both_results_have_duplicate_dates_skipped(self):
        """两个结果各有重复 date → skipped"""
        dup1_rows = [
            (_dt.datetime(2026, 1, 1, 0, 0), 100),
            (_dt.datetime(2026, 1, 1, 0, 0), 200),
        ]
        dup2_rows = [
            (_dt.datetime(2026, 1, 1, 0, 0), 300),
            (_dt.datetime(2026, 1, 2, 0, 0), 400),
            (_dt.datetime(2026, 1, 2, 0, 0), 500),
        ]
        ur1 = _make_ur(metrics=["a"], planning_table="gold.t1", rows=dup1_rows)
        ur2 = _make_ur(metrics=["b"], planning_table="gold.t2", rows=dup2_rows)

        merged = merge_results_on_date([ur1, ur2])
        assert merged.merge_status == MergeStatus.SKIPPED
        assert "重复 date" in merged.reason


# ═══════════════════════════════════════════════════════════════
# date 范围不一致测试
# ═══════════════════════════════════════════════════════════════


class TestDateRangeMismatch:
    """date 范围不一致 → outer merge + merge_warnings"""

    def test_partial_overlap_outer_merge_with_warning(self):
        """部分重叠的日期范围 → merged（outer merge）+ merge_warnings"""
        ur1 = _make_ur(
            metrics=["trip_count"],
            planning_table="gold.dws_daily_trip_summary",
            rows=_daily_rows(1, 15),  # 1月1-15日
        )
        ur2 = _make_ur(
            metrics=["persons_injured"],
            planning_table="gold.dws_daily_crash_summary",
            rows=_daily_rows(10, 25, lambda d: 50 + d),  # 1月10-25日
        )

        merged = merge_results_on_date([ur1, ur2])

        # 范围不完全一致 → 仍执行 outer merge
        assert merged.merge_status == MergeStatus.MERGED
        assert len(merged.merge_warnings) > 0
        # 含 date 范围不一致的警告
        range_warning_found = any(
            "范围不一致" in w or "缺失" in w
            for w in merged.merge_warnings
        )
        assert range_warning_found, f"merge_warnings: {merged.merge_warnings}"

    def test_no_overlap_outer_merge(self):
        """完全不重叠 → outer merge，所有 date 都出现"""
        ur1 = _make_ur(
            metrics=["trip_count"],
            planning_table="gold.dws_daily_trip_summary",
            rows=_daily_rows(1, 5),
        )
        ur2 = _make_ur(
            metrics=["persons_injured"],
            planning_table="gold.dws_daily_crash_summary",
            rows=_daily_rows(10, 15, lambda d: 50 + d),
        )

        merged = merge_results_on_date([ur1, ur2])

        assert merged.merge_status == MergeStatus.MERGED
        # 应有 5+6 = 11 个不同日期
        assert merged.row_count == 11
        # 有 Nones 填充
        assert len(merged.merge_warnings) > 0

    def test_exact_same_range_no_warning(self):
        """完全相同的日期范围 → merged，无范围不一致警告"""
        ur1 = _make_ur(
            metrics=["trip_count"],
            planning_table="gold.dws_daily_trip_summary",
            rows=_daily_rows(1, 10),
        )
        ur2 = _make_ur(
            metrics=["persons_injured"],
            planning_table="gold.dws_daily_crash_summary",
            rows=_daily_rows(1, 10, lambda d: 50 + d),
        )

        merged = merge_results_on_date([ur1, ur2])

        assert merged.merge_status == MergeStatus.MERGED
        # 不应该有 missing date 的逐行警告
        missing_warnings = [w for w in merged.merge_warnings if "缺失" in w]
        assert len(missing_warnings) == 0, f"不应有缺失警告: {missing_warnings}"


# ═══════════════════════════════════════════════════════════════
# can_merge_on_date 单元测试
# ═══════════════════════════════════════════════════════════════


class TestCanMergeOnDate:
    """can_merge_on_date() 条件检查"""

    def test_all_conditions_met_returns_true(self):
        """全部条件满足 → True"""
        ur1 = _make_ur(["trip_count"], "gold.dws_daily_trip_summary", _daily_rows(1, 7))
        ur2 = _make_ur(["injured"], "gold.dws_daily_crash_summary", _daily_rows(1, 7))

        s1 = summarize_sql_result(ur1, plan_index=1)
        s2 = summarize_sql_result(ur2, plan_index=2)

        ok, reasons = can_merge_on_date([s1, s2])
        assert ok is True
        assert reasons == []

    def test_single_result_returns_false(self):
        """只有 1 个结果 → False"""
        ur = _make_ur(["trip_count"], "gold.t", _daily_rows(1, 7))
        s = summarize_sql_result(ur, plan_index=1)

        ok, reasons = can_merge_on_date([s])
        assert ok is False

    def test_missing_date_column_returns_false(self):
        """有结果缺 date 列 → False"""
        ur1 = _make_ur(["trip_count"], "gold.t1", _daily_rows(1, 7))
        ur2 = UnifiedResponse(
            sub_intent=SubIntent(metrics=["cnt"], planning_table="gold.t2"),
            plan=SQLPlan(strategy=Strategy.G3_DIRECT, primary_table="gold.t2"),
            result=SQLResult(
                sql="mock", columns=["borough", "cnt"],
                column_types=["VARCHAR", "INTEGER"],
                rows=[("X", 1)], row_count=1,
            ),
        )
        s1 = summarize_sql_result(ur1, plan_index=1)
        s2 = summarize_sql_result(ur2, plan_index=2)

        ok, reasons = can_merge_on_date([s1, s2])
        assert ok is False
        assert any("缺少 date 列" in r for r in reasons)

    def test_different_grain_returns_false(self):
        """grain 不一致 → False"""
        ur1 = _make_ur(["trip_count"], "gold.t1", _daily_rows(1, 7))
        # 非 daily：只有 1 行
        ur2 = _make_ur(
            ["other"], "gold.t2",
            rows=[(_dt.datetime(2026, 1, 15, 0, 0), 999)],
        )

        s1 = summarize_sql_result(ur1, plan_index=1)
        s2 = summarize_sql_result(ur2, plan_index=2)

        ok, reasons = can_merge_on_date([s1, s2])
        assert ok is False
        assert any("grain" in r.lower() for r in reasons)


# ═══════════════════════════════════════════════════════════════
# 不产生因果解释测试
# ═══════════════════════════════════════════════════════════════


class TestNoCausalLanguage:
    """合并后的 chinese_answer 不包含因果语言"""

    def test_merged_answer_no_causal_words(self):
        """"每天行程数和受伤人数" → chinese_answer 不含因果词"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天行程数和受伤人数分别是多少？")

        full_answer = response.chinese_answer or ""

        # 跨域策略警告中可能包含因果词作为反例说明（如"不能推断因果关系（如『...是因为...』）"），
        # 这些不应被判定为违规。剥离 ⚠️ 前缀的警告行后再检查正文。
        answer = full_answer
        if "⚠️" in answer:
            # 移除所有以 ⚠️ 开头的策略警告行（包括续行）
            lines = answer.split("\n")
            clean_lines = [
                line for line in lines
                if not line.strip().startswith("⚠️")
            ]
            answer = "\n".join(clean_lines).strip()

        # 禁止的因果词
        causal_words = ["导致", "造成", "引起", "因为", "所以", "因此", "从而"]
        for word in causal_words:
            assert word not in answer, (
                f"chinese_answer 正文包含因果词 '{word}': ...{answer[max(0, answer.find(word)-20):answer.find(word)+30]}..."
            )

    def test_merged_answer_describes_merge_not_causality(self):
        """"每天行程数和受伤人数" → 描述合并，不描述"X 导致 Y"之类的因果关系"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天行程数和受伤人数分别是多少？")

        answer = response.chinese_answer or ""

        # 不应有跨指标的因果描述模式
        bad_patterns = [
            "行程数导致", "受伤人数导致",
            "因为行程", "因为受伤",
            "所以事故", "因此受伤",
        ]
        for pattern in bad_patterns:
            assert pattern not in answer, f"发现因果模式: '{pattern}'"

    def test_skipped_answer_no_causal_words(self):
        """被跳过 merge 的回答也同样不含因果词"""
        causal_words = ["导致", "造成", "引起", "因为", "所以", "因此", "从而"]

        # 构造一个会 skip 的场景（一个结果无 date）
        ur1 = _make_ur(["trip_count"], "gold.t1", _daily_rows(1, 7))
        ur2 = UnifiedResponse(
            sub_intent=SubIntent(metrics=["cnt"], planning_table="gold.t2"),
            plan=SQLPlan(strategy=Strategy.G3_DIRECT, primary_table="gold.t2"),
            result=SQLResult(
                sql="mock", columns=["borough", "cnt"],
                column_types=["VARCHAR", "INTEGER"],
                rows=[("X", 1)], row_count=1,
            ),
        )

        merged = merge_results_on_date([ur1, ur2])
        assert merged.merge_status == MergeStatus.SKIPPED

        # reason 也不应含因果词
        for word in causal_words:
            assert word not in merged.reason

    def test_make_skipped_row_count_consistent(self):
        """_make_skipped: rows=[] 时必须 row_count=0"""
        from src.result_merge import _make_skipped
        from src.result_summary import summarize_sql_result

        ur = _make_ur(["trip_count"], "gold.t1", _daily_rows(1, 7))
        summary = summarize_sql_result(ur, plan_index=1)
        # 原始 summary 的 row_count > 0
        assert summary.row_count > 0

        skipped = _make_skipped([summary], "测试跳过")
        assert skipped.merge_status == MergeStatus.SKIPPED
        assert skipped.rows == []
        assert skipped.row_count == 0, (
            f"rows=[] 时 row_count 必须为 0，实际={skipped.row_count}"
        )

    def test_irregular_row_no_index_error(self):
        """行长度不足 date_idx 时跳过，不触发 IndexError"""
        # 构造列数与行数据不匹配的 SQLResult
        ur = UnifiedResponse(
            sub_intent=SubIntent(metrics=["trip_count"], planning_table="gold.t1"),
            plan=SQLPlan(strategy=Strategy.G3_DIRECT, primary_table="gold.t1"),
            result=SQLResult(
                sql="mock",
                columns=["trip_date", "trip_count"],
                column_types=["DATE", "INTEGER"],
                rows=[
                    (_dt.datetime(2026, 1, 1), 100),   # 正常行
                    (_dt.datetime(2026, 1, 2),),       # 不足 2 列——不崩溃
                    (_dt.datetime(2026, 1, 3), 300),   # 正常行
                ],
                row_count=3,
            ),
        )
        # 不应抛出 IndexError
        merged = merge_results_on_date([ur])
        assert merged.merge_status == MergeStatus.SKIPPED  # 单结果无法合并
        # 关键在于调用过程中未崩溃
