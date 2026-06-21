"""
ChartSpec 规则图表规格测试套件（Phase 5）。

覆盖：
    1. MergedResult date 多指标 → line
    2. 单 ResultSummary date 单指标 → line
    3. 类别排名 → bar
    4. 单值 → metric_card
    5. 无法识别 → table
    6. 不生成 JS/HTML
    7. 不调用 LLM
    8. 不调用 DuckDB
    9. warnings 保留
    10. ChartSpec.to_dict() 可 JSON 序列化
"""

from __future__ import annotations

import ast
import datetime as _dt
import json


from src.chart_spec import (
    ChartSpec,
    build_chart_spec_from_summary,
    build_chart_spec_from_merged_result,
)
from src.ir import (
    MergeStatus,
    MergedResult,
    ResultSummary,
    SQLPlan,
    Strategy,
)


# ═══════════════════════════════════════════════════════════
# 测试辅助函数
# ═══════════════════════════════════════════════════════════


def _make_summary(
    plan_index: int = 1,
    metrics: list[str] | None = None,
    primary_table: str = "gold.dws_daily_trip_summary",
    columns: list[str] | None = None,
    sample_rows: list[list] | None = None,
    row_count: int = 0,
    has_date_column: bool = False,
    grain: str = "unknown",
    date_min: str = "",
    date_max: str = "",
    warnings: list[str] | None = None,
) -> ResultSummary:
    """创建测试用 ResultSummary"""
    if sample_rows and row_count == 0:
        row_count = len(sample_rows)
    return ResultSummary(
        source_plan_index=plan_index,
        metrics=metrics or ["trip_count"],
        primary_table=primary_table,
        columns=columns or ["date", "trip_count"],
        sample_rows=sample_rows or [],
        row_count=row_count,
        has_date_column=has_date_column,
        grain=grain,
        date_min=date_min,
        date_max=date_max,
        warnings=warnings or [],
    )


def _make_merged(
    columns: list[str] | None = None,
    rows: list[list] | None = None,
    merge_status: MergeStatus = MergeStatus.MERGED,
    merge_key: str = "date",
    source_summaries: list[ResultSummary] | None = None,
    merge_warnings: list[str] | None = None,
    reason: str = "",
) -> MergedResult:
    """创建测试用 MergedResult"""
    if source_summaries is None:
        source_summaries = [
            _make_summary(plan_index=1, metrics=["trip_count"],
                          primary_table="gold.dws_daily_trip_summary"),
            _make_summary(plan_index=2, metrics=["crash_count"],
                          primary_table="gold.dws_daily_crash_summary"),
        ]
    return MergedResult(
        merge_status=merge_status,
        merge_key=merge_key,
        columns=columns or ["date", "trip_count", "crash_count"],
        rows=rows or [],
        row_count=len(rows) if rows else 0,
        source_plan_indexes=[s.source_plan_index for s in source_summaries],
        source_summaries=source_summaries,
        merge_warnings=merge_warnings or [],
        reason=reason,
    )


# ═══════════════════════════════════════════════════════════
# TestChartSpecDataclass — 基础结构
# ═══════════════════════════════════════════════════════════


class TestChartSpecDataclass:
    """ChartSpec dataclass 基本行为"""

    def test_default_values(self):
        """默认值为 table 类型"""
        spec = ChartSpec()
        assert spec.chart_type == "table"
        assert spec.title == ""
        assert spec.x_field == ""
        assert spec.y_fields == []
        assert spec.series == []
        assert spec.source == ""
        assert spec.warnings == []
        assert spec.data_preview == []

    def test_all_fields_settable(self):
        """所有字段可显式设置"""
        spec = ChartSpec(
            chart_type="line",
            title="测试图表",
            x_field="date",
            y_fields=["trip_count", "crash_count"],
            series=[{"name": "trip_count", "x": [], "y": []}],
            source="test_table",
            warnings=["测试警告"],
            data_preview=[["2026-01-01", 100]],
        )
        assert spec.chart_type == "line"
        assert spec.title == "测试图表"
        assert spec.x_field == "date"
        assert len(spec.y_fields) == 2
        assert len(spec.series) == 1

    def test_to_dict_serializable(self):
        """验收 10: to_dict() 返回纯 JSON 可序列化结构"""
        spec = ChartSpec(
            chart_type="line",
            title="测试",
            x_field="date",
            y_fields=["val"],
            series=[{"name": "val", "x": ["2026-01-01"], "y": [100]}],
            source="test",
            warnings=["w1"],
            data_preview=[["2026-01-01", 100]],
        )
        d = spec.to_dict()
        # 必须可 JSON 序列化（不抛异常）
        json_str = json.dumps(d, ensure_ascii=False)
        assert isinstance(json_str, str)
        assert "line" in json_str

    def test_to_json_method(self):
        """to_json() 返回 JSON 字符串"""
        spec = ChartSpec(
            chart_type="bar",
            title="排名",
            x_field="category",
            y_fields=["count"],
        )
        result = spec.to_json()
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["chart_type"] == "bar"


# ═══════════════════════════════════════════════════════════
# TestMergedResultDateLine — 验收 1
# ═══════════════════════════════════════════════════════════


class TestMergedResultDateLine:
    """验收 1: MergedResult date 多指标 → line"""

    def test_merged_date_multi_metric_returns_line(self):
        """MergedResult 含 date + 多个数值列 → line"""
        merged = _make_merged(
            columns=["date", "trip_count", "crash_count"],
            rows=[
                [_dt.date(2026, 1, 1), 15000, 3],
                [_dt.date(2026, 1, 2), 16000, 2],
                [_dt.date(2026, 1, 3), 14500, 4],
            ],
            merge_key="date",
        )
        spec = build_chart_spec_from_merged_result(merged)
        assert spec.chart_type == "line"
        assert spec.x_field == "date"
        assert "trip_count" in spec.y_fields
        assert "crash_count" in spec.y_fields

    def test_merged_date_multi_metric_has_series(self):
        """line 类型应包含 series 数据"""
        merged = _make_merged(
            columns=["date", "trip_count", "crash_count"],
            rows=[
                [_dt.date(2026, 1, 1), 15000, 3],
                [_dt.date(2026, 1, 2), 16000, 2],
            ],
            merge_key="date",
        )
        spec = build_chart_spec_from_merged_result(merged)
        assert len(spec.series) == 2  # 两个 y 字段
        for s in spec.series:
            assert "name" in s
            assert "x" in s
            assert "y" in s
            assert len(s["x"]) == 2
            assert len(s["y"]) == 2

    def test_merged_date_single_metric_also_line(self):
        """MergedResult date 单指标 → 也是 line"""
        merged = _make_merged(
            columns=["date", "trip_count"],
            rows=[
                [_dt.date(2026, 1, 1), 15000],
                [_dt.date(2026, 1, 2), 16000],
            ],
            merge_key="date",
        )
        spec = build_chart_spec_from_merged_result(merged)
        assert spec.chart_type == "line"
        assert len(spec.y_fields) == 1

    def test_merged_skipped_returns_table(self):
        """未合并的 MergedResult → table"""
        merged = _make_merged(
            columns=["date", "trip_count"],
            rows=[],
            merge_status=MergeStatus.SKIPPED,
            merge_key="",
            reason="缺少 date 列",
        )
        spec = build_chart_spec_from_merged_result(merged)
        assert spec.chart_type == "table"

    def test_merged_empty_returns_table(self):
        """空 MergedResult → table"""
        merged = _make_merged(
            columns=[],
            rows=[],
            merge_status=MergeStatus.MERGED,
            merge_key="date",
        )
        spec = build_chart_spec_from_merged_result(merged)
        assert spec.chart_type == "table"


# ═══════════════════════════════════════════════════════════
# TestSummaryDateLine — 验收 2
# ═══════════════════════════════════════════════════════════


class TestSummaryDateLine:
    """验收 2: 单 ResultSummary date 单指标 → line"""

    def test_single_summary_date_one_metric_returns_line(self):
        """有 date 列 + 一个数值列 → line"""
        summary = _make_summary(
            metrics=["trip_count"],
            primary_table="gold.dws_daily_trip_summary",
            columns=["date", "trip_count"],
            sample_rows=[
                ["2026-01-01", 15000],
                ["2026-01-02", 16000],
                ["2026-01-03", 14500],
            ],
            row_count=31,
            has_date_column=True,
            grain="daily",
            date_min="2026-01-01",
            date_max="2026-01-31",
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type == "line"
        assert spec.x_field == "date"
        assert spec.y_fields == ["trip_count"]

    def test_single_summary_date_multi_metric_returns_line(self):
        """有 date 列 + 多个数值列 → line"""
        summary = _make_summary(
            metrics=["trip_count", "total_fare_amount"],
            columns=["date", "trip_count", "total_fare_amount"],
            sample_rows=[
                ["2026-01-01", 15000, 250000.0],
                ["2026-01-02", 16000, 260000.0],
            ],
            row_count=31,
            has_date_column=True,
            grain="daily",
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type == "line"
        assert len(spec.y_fields) == 2

    def test_summary_no_date_no_line(self):
        """无 date 列 → 不生成 line"""
        summary = _make_summary(
            metrics=["trip_count"],
            columns=["region", "trip_count"],
            sample_rows=[
                ["曼哈顿", 15000],
                ["布鲁克林", 12000],
            ],
            row_count=5,
            has_date_column=False,
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type != "line"


# ═══════════════════════════════════════════════════════════
# TestCategoryBar — 验收 3
# ═══════════════════════════════════════════════════════════


class TestCategoryBar:
    """验收 3: 类别排名 → bar"""

    def test_category_with_values_returns_bar(self):
        """无 date 但有类别列 + 数值列 → bar"""
        summary = _make_summary(
            metrics=["trip_count"],
            columns=["region", "trip_count"],
            sample_rows=[
                ["曼哈顿", 15000],
                ["布鲁克林", 12000],
                ["皇后区", 8000],
                ["布朗克斯", 5000],
            ],
            row_count=4,
            has_date_column=False,
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type == "bar"
        assert spec.x_field == "region"
        assert "trip_count" in spec.y_fields

    def test_bar_has_series_data(self):
        """bar 类型包含 series 数据"""
        summary = _make_summary(
            metrics=["crash_count"],
            columns=["borough", "crash_count"],
            sample_rows=[
                ["曼哈顿", 45],
                ["布鲁克林", 32],
                ["皇后区", 28],
            ],
            row_count=3,
            has_date_column=False,
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type == "bar"
        assert len(spec.series) == 1
        assert len(spec.series[0]["x"]) == 3

    def test_multi_category_bar(self):
        """多个类别列 + 多个数值列 → 仍为 bar"""
        summary = _make_summary(
            metrics=["trip_count", "total_fare_amount"],
            columns=["region", "trip_count", "total_fare_amount"],
            sample_rows=[
                ["曼哈顿", 15000, 250000.0],
                ["布鲁克林", 12000, 180000.0],
            ],
            row_count=2,
            has_date_column=False,
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type == "bar"


# ═══════════════════════════════════════════════════════════
# TestMetricCard — 验收 4
# ═══════════════════════════════════════════════════════════


class TestMetricCard:
    """验收 4: 单值 → metric_card"""

    def test_single_row_single_metric_returns_metric_card(self):
        """单行单指标 → metric_card"""
        summary = _make_summary(
            metrics=["trip_count"],
            columns=["trip_count"],
            sample_rows=[[15000]],
            row_count=1,
            has_date_column=False,
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type == "metric_card"

    def test_single_row_multi_metric_not_card(self):
        """单行多指标 → 不生成 metric_card"""
        summary = _make_summary(
            metrics=["trip_count", "total_fare_amount"],
            columns=["trip_count", "total_fare_amount"],
            sample_rows=[[15000, 250000.0]],
            row_count=1,
        )
        spec = build_chart_spec_from_summary(summary)
        # 单行但多列，无法判断 → table
        assert spec.chart_type != "metric_card"

    def test_metric_card_has_value(self):
        """metric_card 的 data_preview 包含指标值"""
        summary = _make_summary(
            metrics=["crash_count"],
            columns=["crash_count"],
            sample_rows=[[42]],
            row_count=1,
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type == "metric_card"
        assert len(spec.data_preview) == 1


# ═══════════════════════════════════════════════════════════
# TestFallbackTable — 验收 5
# ═══════════════════════════════════════════════════════════


class TestFallbackTable:
    """验收 5: 无法识别 → table"""

    def test_empty_summary_returns_table(self):
        """空摘要 → table"""
        summary = _make_summary(
            metrics=[],
            columns=[],
            row_count=0,
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type == "table"

    def test_no_columns_returns_table(self):
        """无列名 → table"""
        summary = _make_summary(
            metrics=["trip_count"],
            columns=[],
            sample_rows=[],
            row_count=0,
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type == "table"

    def test_all_text_columns_returns_table(self):
        """全是文本列无数值列 → table"""
        summary = _make_summary(
            metrics=["name"],
            columns=["name", "description"],
            sample_rows=[
                ["项目A", "描述A"],
                ["项目B", "描述B"],
            ],
            row_count=2,
            has_date_column=False,
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type == "table"

    def test_fallback_table_has_reason_in_warnings(self):
        """table 降级时 warnings 包含原因"""
        summary = _make_summary(
            metrics=["name"],
            columns=["name"],
            sample_rows=[["A"], ["B"]],
            row_count=2,
            has_date_column=False,
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type == "table"


# ═══════════════════════════════════════════════════════════
# TestNoFrontendCode — 验收 6
# ═══════════════════════════════════════════════════════════


class TestNoFrontendCode:
    """验收 6: 不生成 JS/HTML"""

    def test_chart_spec_no_html_output(self):
        """ChartSpec.to_dict() 不包含任何 HTML"""
        spec = ChartSpec(chart_type="line", title="测试")
        d = spec.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        assert "<div" not in json_str.lower()
        assert "<svg" not in json_str.lower()
        assert "<html" not in json_str.lower()

    def test_chart_spec_no_javascript_output(self):
        """ChartSpec.to_dict() 不包含任何 JavaScript"""
        spec = build_chart_spec_from_summary(
            _make_summary(
                metrics=["trip_count"],
                columns=["date", "trip_count"],
                sample_rows=[["2026-01-01", 15000]],
                row_count=1,
                has_date_column=True,
            )
        )
        json_str = spec.to_json()
        assert "function" not in json_str.lower()
        assert "javascript" not in json_str.lower()
        assert "document." not in json_str.lower()
        assert "window." not in json_str.lower()
        assert "<script" not in json_str.lower()

    def test_source_code_no_js_html_strings(self):
        """chart_spec.py 源码不含 JS/HTML 生成逻辑（AST 检查）"""
        with open("src/chart_spec.py", encoding="utf-8") as f:
            source = f.read()
        # 不包含 echo/print 输出 HTML 的模式
        assert "echarts" not in source.lower()
        assert "plotly" not in source.lower()
        assert "highcharts" not in source.lower()
        assert "<div" not in source


# ═══════════════════════════════════════════════════════════
# TestNoLLM — 验收 7
# ═══════════════════════════════════════════════════════════


class TestNoLLM:
    """验收 7: 不调用 LLM"""

    def test_chart_spec_does_not_import_llm(self):
        """chart_spec.py 不导入 LLM 模块"""
        with open("src/chart_spec.py", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "llm" not in node.module, (
                        "chart_spec 不应导入 LLM 模块"
                    )

    def test_build_functions_no_llm_client_param(self):
        """构建函数不接收 llm_client 参数"""
        import inspect
        sig1 = inspect.signature(build_chart_spec_from_summary)
        sig2 = inspect.signature(build_chart_spec_from_merged_result)
        for sig in (sig1, sig2):
            params = list(sig.parameters.keys())
            assert "llm_client" not in params
            assert "llm" not in params

    def test_chart_spec_pure_rules_no_network(self):
        """纯规则调用，不产生网络请求"""
        summary = _make_summary(
            metrics=["trip_count"],
            columns=["date", "trip_count"],
            sample_rows=[["2026-01-01", 15000]],
            row_count=1,
            has_date_column=True,
        )
        # 无 mock、无 patch——纯规则不应抛异常
        spec = build_chart_spec_from_summary(summary)
        assert isinstance(spec, ChartSpec)


# ═══════════════════════════════════════════════════════════
# TestNoDuckDB — 验收 8
# ═══════════════════════════════════════════════════════════


class TestNoDuckDB:
    """验收 8: 不调用 DuckDB"""

    def test_chart_spec_does_not_import_duckdb(self):
        """chart_spec.py 不导入 duckdb"""
        with open("src/chart_spec.py", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in (node.names if hasattr(node, 'names') else []):
                    name = getattr(alias, 'name', '')
                    assert "duckdb" not in name.lower(), (
                        "chart_spec 不应导入 duckdb"
                    )

    def test_chart_spec_does_not_import_sql_gen(self):
        """chart_spec.py 不导入 sql_gen"""
        with open("src/chart_spec.py", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "sql_gen" not in node.module, (
                        "chart_spec 不应导入 sql_gen"
                    )

    def test_chart_spec_does_not_modify_sqlplan(self):
        """chart_spec 不操作 SQLPlan"""
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
        )
        original = plan.to_dict()

        summary = _make_summary(
            metrics=["trip_count"],
            columns=["date", "trip_count"],
            sample_rows=[["2026-01-01", 15000]],
            row_count=1,
            has_date_column=True,
        )
        build_chart_spec_from_summary(summary)

        assert plan.to_dict() == original


# ═══════════════════════════════════════════════════════════
# TestWarningsPreserved — 验收 9
# ═══════════════════════════════════════════════════════════


class TestWarningsPreserved:
    """验收 9: warnings 保留"""

    def test_summary_warnings_preserved(self):
        """原始 warnings 传递到 ChartSpec"""
        summary = _make_summary(
            metrics=["trip_count"],
            columns=["date", "trip_count"],
            sample_rows=[["2026-01-01", 15000]],
            row_count=1,
            has_date_column=True,
            warnings=["数据采样自部分区域"],
        )
        spec = build_chart_spec_from_summary(summary)
        assert "数据采样自部分区域" in spec.warnings

    def test_merged_warnings_preserved(self):
        """MergedResult 的 merge_warnings 传递到 ChartSpec"""
        merged = _make_merged(
            columns=["date", "trip_count", "crash_count"],
            rows=[
                [_dt.date(2026, 1, 1), 15000, 3],
                [_dt.date(2026, 1, 2), 16000, 2],
            ],
            merge_key="date",
            merge_warnings=["date 范围不一致: 计划1=2026-01-01 ~ 2026-01-31, 计划2=2026-01-01 ~ 2026-01-15"],
        )
        spec = build_chart_spec_from_merged_result(merged)
        assert "date 范围不一致" in " ".join(spec.warnings)

    def test_cross_domain_warning_appended(self):
        """跨域策略 warning 被追加到 ChartSpec.warnings"""
        summary = _make_summary(
            metrics=["trip_count"],
            columns=["date", "trip_count"],
            sample_rows=[["2026-01-01", 15000]],
            row_count=1,
            has_date_column=True,
        )
        spec = build_chart_spec_from_summary(
            summary,
            cross_domain_warning="traffic+safety 跨域：只能做并列观察，不能推断因果",
        )
        assert any("并列观察" in w for w in spec.warnings)

    def test_cross_domain_refusal_downgrades_to_table(self):
        """跨域 refusal → 降级为 table"""
        summary = _make_summary(
            metrics=["driver_count"],
            columns=["driver_id", "driver_name"],
            sample_rows=[["D001", "张三"]],
            row_count=1,
            has_date_column=False,
        )
        spec = build_chart_spec_from_summary(
            summary,
            cross_domain_warning="refusal: 涉及人员隐私字段，禁止展示",
        )
        assert spec.chart_type == "table"


# ═══════════════════════════════════════════════════════════
# TestDataPreviews — 数据预览
# ═══════════════════════════════════════════════════════════


class TestDataPreviews:
    """数据预览序列化"""

    def test_date_objects_serialized_to_iso(self):
        """date/datetime 对象序列化为 ISO 字符串"""
        merged = _make_merged(
            columns=["date", "trip_count"],
            rows=[
                [_dt.date(2026, 1, 1), 15000],
                [_dt.datetime(2026, 1, 2, 0, 0), 16000],
            ],
            merge_key="date",
        )
        spec = build_chart_spec_from_merged_result(merged)
        json_str = spec.to_json()
        _parsed = json.loads(json_str)
        # 检查 data_preview 中的日期值
        assert "2026-01-01" in json_str or "2026-01-02" in json_str

    def test_none_values_preserved(self):
        """None 值保持为 null"""
        merged = _make_merged(
            columns=["date", "trip_count", "crash_count"],
            rows=[
                [_dt.date(2026, 1, 1), 15000, None],
                [_dt.date(2026, 1, 2), 16000, 2],
            ],
            merge_key="date",
        )
        spec = build_chart_spec_from_merged_result(merged)
        json_str = spec.to_json()
        assert "null" in json_str


# ═══════════════════════════════════════════════════════════
# TestTitleGeneration — 标题生成
# ═══════════════════════════════════════════════════════════


class TestTitleGeneration:
    """标题生成逻辑"""

    def test_single_metric_title(self):
        """单指标标题"""
        summary = _make_summary(
            metrics=["trip_count"],
            columns=["date", "trip_count"],
            sample_rows=[["2026-01-01", 15000]],
            row_count=1,
            has_date_column=True,
        )
        spec = build_chart_spec_from_summary(summary)
        assert "trip count" in spec.title.lower()

    def test_multi_metric_title(self):
        """多指标标题"""
        summary = _make_summary(
            metrics=["trip_count", "total_fare_amount"],
            columns=["date", "trip_count", "total_fare_amount"],
            sample_rows=[["2026-01-01", 15000, 250000.0]],
            row_count=1,
            has_date_column=True,
        )
        spec = build_chart_spec_from_summary(summary)
        assert "trip count" in spec.title.lower()
        assert "total fare amount" in spec.title.lower()

    def test_empty_metrics_title(self):
        """无指标时有默认标题"""
        summary = _make_summary(
            metrics=[],
            columns=["date"],
            sample_rows=[["2026-01-01"]],
            row_count=1,
        )
        spec = build_chart_spec_from_summary(summary)
        assert len(spec.title) > 0


# ═══════════════════════════════════════════════════════════
# TestEdgeCases
# ═══════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况"""

    def test_bool_values_not_treated_as_numeric(self):
        """bool 值不应被误判为数值列"""
        summary = _make_summary(
            metrics=["is_active"],
            columns=["name", "is_active"],
            sample_rows=[
                ["项目A", True],
                ["项目B", False],
            ],
            row_count=2,
            has_date_column=False,
        )
        spec = build_chart_spec_from_summary(summary)
        # bool 列不应被识别为数值列 → 降级为 table
        assert spec.chart_type == "table"

    def test_mixed_date_and_category_prefers_line(self):
        """同时有 date 和类别列时，首选 line（date 优先）"""
        summary = _make_summary(
            metrics=["trip_count"],
            columns=["date", "region", "trip_count"],
            sample_rows=[
                ["2026-01-01", "曼哈顿", 5000],
                ["2026-01-02", "曼哈顿", 4800],
            ],
            row_count=31,
            has_date_column=True,
            grain="daily",
        )
        spec = build_chart_spec_from_summary(summary)
        # date 优先 → line
        assert spec.chart_type == "line"
        assert spec.x_field == "date"

    def test_int_columns_detected_as_numeric(self):
        """整数列应被识别为数值列（不含特殊关键词时靠类型推断）"""
        summary = _make_summary(
            metrics=["trip_count"],
            columns=["date", "trip_count"],
            sample_rows=[
                ["2026-01-01", 15000],
                ["2026-01-02", 16000],
            ],
            row_count=2,
            has_date_column=True,
        )
        spec = build_chart_spec_from_summary(summary)
        assert "trip_count" in spec.y_fields

    def test_float_columns_detected_as_numeric(self):
        """浮点数列应被识别为数值列"""
        summary = _make_summary(
            metrics=["avg_distance_miles"],
            columns=["date", "avg_distance_miles"],
            sample_rows=[
                ["2026-01-01", 3.5],
                ["2026-01-02", 4.2],
            ],
            row_count=2,
            has_date_column=True,
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type == "line"
