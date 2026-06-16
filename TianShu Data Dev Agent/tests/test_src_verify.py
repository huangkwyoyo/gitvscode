"""
测试 verify 规则引擎——7 项检查 + Validator 编排。
"""

from __future__ import annotations

import pytest

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

from src.ir.types import (
    ValidationStatus, CheckResult, ValidationReport,
    SQLPlan, SQLResult, Strategy, JoinPlan,
)
from src.verify.checks import (
    FORBIDDEN_KEYWORDS,
    check_forbidden_keywords,
    check_table_permissions,
    check_join_whitelist,
    check_result_quality,
    check_cross_validation,
    check_table_existence,
    check_sample_execution,
    _extract_table_references,
    _clean_sql_for_keyword_scan,
    _is_table_forbidden,
)
from src.verify.checker import Validator
from src.verify.cross_validation import compare_results
from src.verify.report import make_success_report, make_fail_report, make_pending_report


class TestHelperFunctions:
    """工具函数测试"""

    def test_extract_table_references_simple(self):
        refs = _extract_table_references("SELECT * FROM gold.table_a")
        assert "gold.table_a" in refs

    def test_extract_table_references_join(self):
        sql = "SELECT * FROM gold.table_a INNER JOIN gold.table_b ON a.id = b.id"
        refs = _extract_table_references(sql)
        assert "gold.table_a" in refs
        assert "gold.table_b" in refs

    def test_extract_table_references_dedup(self):
        sql = """
            SELECT * FROM gold.table_a
            WHERE id IN (SELECT id FROM gold.table_a)
        """
        refs = _extract_table_references(sql)
        assert len(refs) == 1  # 去重

    def test_clean_sql_removes_strings(self):
        cleaned = _clean_sql_for_keyword_scan("SELECT 'INSERT INTO' FROM t")
        assert "INSERT" not in cleaned.upper()  # 字符串内关键字被移除

    def test_clean_sql_removes_comments(self):
        cleaned = _clean_sql_for_keyword_scan(
            "SELECT * FROM t -- DROP TABLE users\nWHERE id = 1"
        )
        assert "DROP" not in cleaned.upper()

    def test_is_table_forbidden_bronze(self):
        is_bad, reason = _is_table_forbidden("bronze.raw_trips")
        assert is_bad is True

    def test_is_table_forbidden_silver(self):
        is_bad, reason = _is_table_forbidden("silver.cleaned_trips")
        assert is_bad is True

    def test_is_table_forbidden_gold(self):
        is_bad, reason = _is_table_forbidden("gold.dws_daily_trip_summary")
        assert is_bad is False


class TestCheckForbiddenKeywords:
    """检查 #2：安全关键字黑名单"""

    def test_clean_sql_passes(self):
        result = check_forbidden_keywords(
            sql="SELECT * FROM gold.dws_daily_trip_summary WHERE trip_date BETWEEN '2026-01-01' AND '2026-03-31'"
        )
        assert result.status == ValidationStatus.PASSED

    def test_drop_table_fails(self):
        result = check_forbidden_keywords(
            sql="DROP TABLE gold.dws_daily_trip_summary"
        )
        assert result.status == ValidationStatus.FAILED

    def test_insert_fails(self):
        result = check_forbidden_keywords(
            sql="INSERT INTO gold.table_a VALUES (1, 'test')"
        )
        assert result.status == ValidationStatus.FAILED

    def test_update_fails(self):
        result = check_forbidden_keywords(
            sql="UPDATE gold.table_a SET name = 'new' WHERE id = 1"
        )
        assert result.status == ValidationStatus.FAILED

    def test_delete_fails(self):
        result = check_forbidden_keywords(
            sql="DELETE FROM gold.table_a WHERE id = 1"
        )
        assert result.status == ValidationStatus.FAILED

    def test_keyword_in_string_not_false_positive(self):
        """SQL 字符串内的关键字不应误报"""
        result = check_forbidden_keywords(
            sql="SELECT 'INSERT INTO gold.t VALUES (1)' AS description FROM gold.table_a"
        )
        assert result.status == ValidationStatus.PASSED

    def test_created_at_not_matched(self):
        """列名 'created_at' 不应匹配 'CREATE'"""
        result = check_forbidden_keywords(
            sql="SELECT created_at FROM gold.table_a"
        )
        assert result.status == ValidationStatus.PASSED

    def test_all_19_keywords_present(self):
        """确认 19 个禁止关键字全部注册"""
        expected = {
            "INSERT", "UPDATE", "DELETE", "MERGE", "REPLACE", "TRUNCATE",
            "CREATE", "ALTER", "DROP", "RENAME",
            "GRANT", "REVOKE",
            "ATTACH", "DETACH", "EXPORT", "IMPORT",
            "COPY", "INSTALL", "LOAD",
        }
        assert set(FORBIDDEN_KEYWORDS.keys()) == expected


class TestCheckTablePermissions:
    """检查 #3：表访问权限"""

    def test_gold_table_passes(self):
        result = check_table_permissions(
            sql="SELECT * FROM gold.dws_daily_trip_summary"
        )
        assert result.status == ValidationStatus.PASSED

    def test_bronze_table_fails(self):
        result = check_table_permissions(
            sql="SELECT * FROM bronze.raw_trips"
        )
        assert result.status == ValidationStatus.FAILED

    def test_silver_table_fails(self):
        result = check_table_permissions(
            sql="SELECT * FROM silver.cleaned_trips"
        )
        assert result.status == ValidationStatus.FAILED

    def test_unknown_table_with_whitelist(self):
        result = check_table_permissions(
            sql="SELECT * FROM gold.unknown_table",
            available_tables={"gold.known_table"},
        )
        assert result.status == ValidationStatus.FAILED

    def test_whitelist_pass(self):
        result = check_table_permissions(
            sql="SELECT * FROM gold.known_table",
            available_tables={"gold.known_table"},
        )
        assert result.status == ValidationStatus.PASSED


class TestCheckJoinWhitelist:
    """检查 #4：JOIN 白名单合规"""

    def test_single_table_passes(self):
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.table_a",
            joins=[],
        )
        result = check_join_whitelist(plan=plan)
        assert result.status == ValidationStatus.PASSED

    def test_no_plan_skips(self):
        result = check_join_whitelist()
        assert result.status == ValidationStatus.PASSED  # 允许通过，由 SQL 侧兜底

    def test_join_in_whitelist_passes(self):
        plan = SQLPlan(
            strategy=Strategy.G3_CROSS,
            primary_table="gold.table_a",
            joins=[JoinPlan(table="gold.table_b", on="a.id = b.id")],
        )
        result = check_join_whitelist(
            plan=plan,
            join_whitelist={("gold.table_a", "gold.table_b")},
        )
        assert result.status == ValidationStatus.PASSED

    def test_join_not_in_whitelist_fails(self):
        plan = SQLPlan(
            strategy=Strategy.G3_CROSS,
            primary_table="gold.table_a",
            joins=[JoinPlan(table="gold.table_c", on="a.id = c.id")],
        )
        result = check_join_whitelist(
            plan=plan,
            join_whitelist={("gold.table_a", "gold.table_b")},
        )
        assert result.status == ValidationStatus.FAILED

    def test_reverse_pair_in_whitelist(self):
        """白名单中 (table_b, table_a) 应匹配 JOIN a ↔ b"""
        plan = SQLPlan(
            strategy=Strategy.G3_CROSS,
            primary_table="gold.table_a",
            joins=[JoinPlan(table="gold.table_b", on="a.id = b.id")],
        )
        result = check_join_whitelist(
            plan=plan,
            join_whitelist={("gold.table_b", "gold.table_a")},  # 反向
        )
        assert result.status == ValidationStatus.PASSED


class TestCheckResultQuality:
    """检查 #6：结果质量"""

    def test_normal_result_passes(self):
        result = SQLResult(
            sql="SELECT 1",
            columns=["a", "b"],
            column_types=["INTEGER", "VARCHAR"],
            row_count=100,
        )
        check = check_result_quality(result=result)
        assert check.status == ValidationStatus.PASSED

    def test_empty_result_warns(self):
        result = SQLResult(
            sql="SELECT 1",
            columns=["a"],
            column_types=["INTEGER"],
            row_count=0,
        )
        check = check_result_quality(result=result)
        assert check.status == ValidationStatus.WARN

    def test_error_result_warns(self):
        result = SQLResult(
            sql="SELECT 1",
            error="connection refused",
        )
        check = check_result_quality(result=result)
        assert check.status == ValidationStatus.WARN

    def test_no_result_skips(self):
        check = check_result_quality()
        assert check.status == ValidationStatus.PASSED


class TestCheckCrossValidation:
    """检查 #7：交叉验证（Phase 1 桩）"""

    def test_no_spark_result_passes(self):
        result = check_cross_validation(
            sql_result=SQLResult(sql="SELECT 1", row_count=10),
        )
        assert result.status == ValidationStatus.PASSED

    def test_with_spark_result_passes_stub(self):
        result = check_cross_validation(
            sql_result=SQLResult(sql="SELECT 1", row_count=10),
            spark_result=SQLResult(sql="spark.table('t')", row_count=10),
        )
        # Phase 1 桩——对比逻辑未实现
        assert result.status == ValidationStatus.PASSED


class TestValidator:
    """验证器编排测试"""

    def test_all_checks_pass(self):
        # 提供 available_tables 确保检查 #3（表访问权限）通过
        validator = Validator(context={
            "available_tables": {"gold.dws_daily_trip_summary"},
        })
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
        )
        report = validator.validate(
            sql="SELECT * FROM gold.dws_daily_trip_summary LIMIT 10",
            plan=plan,
        )
        # 无数据库连接时检查 #1 和 #5 会跳过（返回 PASSED）
        # 无白名单时检查 #4 跳过
        assert report.overall_status == ValidationStatus.PASSED
        assert len(report.checks) == 7

    def test_forbidden_keyword_fails_overall(self):
        validator = Validator()
        report = validator.validate(
            sql="DROP TABLE gold.dws_daily_trip_summary",
        )
        assert report.overall_status == ValidationStatus.FAILED

    def test_seven_checks_all_present(self):
        validator = Validator()
        report = validator.validate(
            sql="SELECT 1",
        )
        assert len(report.checks) == 7
        check_ids = {c.check_id for c in report.checks}
        assert check_ids == {1, 2, 3, 4, 5, 6, 7}

    def test_validation_report_to_dict(self):
        validator = Validator()
        report = validator.validate(sql="SELECT 1")
        d = report.to_dict()
        assert "overall_status" in d
        assert len(d["checks"]) == 7


class TestCrossValidationEngine:
    """交叉验证引擎测试"""

    def test_compare_results_both_none(self):
        result = compare_results()
        assert result.status.value == "not_attempted"

    def test_compare_results_no_spark(self):
        result = compare_results(
            sql_result=SQLResult(sql="SELECT 1", row_count=10),
        )
        assert result.status.value == "skipped"

    def test_compare_results_phase1_stub(self):
        result = compare_results(
            sql_result=SQLResult(sql="SELECT 1", row_count=10),
            spark_result=SQLResult(sql="spark.code", row_count=10),
        )
        assert result.status.value == "consistent"


class TestReportFactories:
    """验证报告工厂函数"""

    def test_make_success(self):
        report = make_success_report()
        assert report.overall_status == ValidationStatus.PASSED

    def test_make_fail(self):
        report = make_fail_report(["错误1", "错误2"])
        assert report.overall_status == ValidationStatus.FAILED
        assert len(report.checks) == 2

    def test_make_pending(self):
        report = make_pending_report()
        assert report.overall_status == ValidationStatus.PENDING


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="duckdb 未安装")
class TestChecksWithDB:
    """需要 DuckDB 连接的检查项测试"""

    @pytest.fixture
    def conn(self):
        con = duckdb.connect(":memory:", read_only=False)
        con.execute("CREATE TABLE test_t (id INTEGER, val DOUBLE)")
        yield con
        con.close()

    def test_check_table_existence_pass(self, conn):
        result = check_table_existence(
            sql="SELECT * FROM test_t",
            conn=conn,
        )
        assert result.status == ValidationStatus.PASSED

    def test_check_table_existence_fail(self, conn):
        result = check_table_existence(
            sql="SELECT * FROM nonexistent",
            conn=conn,
        )
        assert result.status == ValidationStatus.FAILED

    def test_check_sample_execution_pass(self, conn):
        result = check_sample_execution(
            sql="SELECT * FROM test_t",
            conn=conn,
        )
        assert result.status == ValidationStatus.PASSED

    def test_check_sample_execution_fail(self, conn):
        result = check_sample_execution(
            sql="SELECT nonexistent_column FROM test_t",
            conn=conn,
        )
        assert result.status == ValidationStatus.FAILED
