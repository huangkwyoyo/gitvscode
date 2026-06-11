from src.explainer import explain_result
from src.ir import SQLResult


def test_explain_result_summarizes_rows_and_source():
    """解释器应给出行数、字段、样例和来源"""
    result = SQLResult(
        sql="SELECT gold.dim_date.date, SUM(trip_count) AS trip_count FROM gold.dws_daily_trip_summary",
        columns=["date", "trip_count"],
        column_types=["DATE", "BIGINT"],
        rows=[("2026-01-01", 10), ("2026-01-02", 20)],
        row_count=2,
        execution_time_ms=12.5,
        source_table="gold.dws_daily_trip_summary",
    )

    answer = explain_result("2026年1月每天有多少行程？", result)

    assert "返回 2 行" in answer
    assert "gold.dws_daily_trip_summary" in answer
    assert "date, trip_count" in answer
    assert "2026-01-01" in answer


def test_explain_result_handles_empty_result():
    """空结果应说明可能原因和来源"""
    result = SQLResult(
        sql="SELECT 1 WHERE 1=0",
        row_count=0,
        source_table="gold.dws_daily_trip_summary",
    )

    answer = explain_result("2026年1月每天有多少行程？", result)

    assert "未返回数据" in answer
    assert "gold.dws_daily_trip_summary" in answer
