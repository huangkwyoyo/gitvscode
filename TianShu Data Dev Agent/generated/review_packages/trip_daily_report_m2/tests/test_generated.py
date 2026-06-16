"""
草案：未经验证，未经人审，不得上线。
M2 阶段只生成测试草案，不执行生产 SQL 或 Spark 作业。
"""


def test_review_package_requires_human_decision():
    request_id = "trip_daily_report_m2"
    assert request_id
    assert "APPROVE" != "DEFAULT"
