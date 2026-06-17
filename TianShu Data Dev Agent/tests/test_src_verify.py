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
        """无 plan 且无 sql 时，返回 PENDING 而非静默 PASS"""
        result = check_join_whitelist()
        assert result.status == ValidationStatus.PENDING  # 缺少上下文，不应静默通过

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

    def test_all_checks_pass_with_full_context(self):
        """完整上下文（conn + available_tables + join_whitelist）时全部通过"""
        try:
            import duckdb
            conn = duckdb.connect(":memory:", read_only=False)
            conn.execute("CREATE TABLE dws_daily_trip_summary (trip_date DATE, trip_count INTEGER)")
        except ImportError:
            pytest.skip("duckdb 未安装")

        validator = Validator(context={
            "available_tables": {"dws_daily_trip_summary"},
            "join_whitelist": set(),
            "conn": conn,
        })
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="dws_daily_trip_summary",
        )
        report = validator.validate(
            sql="SELECT * FROM dws_daily_trip_summary LIMIT 10",
            plan=plan,
        )
        # 有完整上下文时，所有检查应能执行并通过
        assert report.overall_status == ValidationStatus.PASSED
        assert len(report.checks) == 7
        conn.close()

    def test_missing_context_produces_pending(self):
        """缺少数据库连接时，表存在性和样本执行检查返回 PENDING，不静默 PASS"""
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
        # 无 conn 时 #1 和 #5 返回 PENDING，#4 无 whitelist 返回 WARN
        # validate() 自动前置 validate_context()，额外产生 2 条上下文告警（conn + join_whitelist）
        statuses = {c.check_id: c.status for c in report.checks}
        assert statuses[1] == ValidationStatus.PENDING  # 表存在性——缺少 conn
        assert statuses[5] == ValidationStatus.PENDING  # 样本执行——缺少 conn
        # 上下文告警应出现
        context_warnings = [c for c in report.checks if c.check_id == 0]
        assert len(context_warnings) >= 2  # conn 和 join_whitelist 缺失
        # 整体状态：有 PENDING 项时不应为 PASSED
        assert report.overall_status != ValidationStatus.PASSED
        assert len(report.checks) == 9  # 2 上下文告警 + 7 项检查

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
        # validate() 自动前置 validate_context()——无上下文时额外产生 3 条上下文告警
        # 总共 3 (上下文) + 7 (主检查) = 10 条
        check_ids = {c.check_id for c in report.checks}
        assert {1, 2, 3, 4, 5, 6, 7}.issubset(check_ids), \
            f"7 项主检查应全部存在，实际: {check_ids}"
        # 上下文告警应存在
        assert 0 in check_ids, f"上下文检查（id=0）应自动出现，实际: {check_ids}"
        assert len(report.checks) == 10

    def test_validation_report_to_dict(self):
        validator = Validator()
        report = validator.validate(sql="SELECT 1")
        d = report.to_dict()
        assert "overall_status" in d
        # validate() 自动前置 validate_context()——无上下文时 3 上下文 + 7 主检查 = 10
        assert len(d["checks"]) == 10


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


class TestWithQuerySupport:
    """M3 静态检查——只读业务查询前缀校验（SELECT / WITH）"""

    def test_with_select_passes_select_only_check(self):
        """CTE 查询 WITH cte AS (...) SELECT ... 通过 SELECT-only 检查"""
        validator = Validator()
        report = validator.validate_static(
            sql="WITH cte AS (SELECT id FROM gold.t1) SELECT * FROM cte",
        )
        # 找到 SQL 只读语句检查（check_id=101）
        sql_check = [c for c in report.checks if c.check_id == 101][0]
        assert sql_check.status == ValidationStatus.PASSED, \
            f"WITH...SELECT 应通过只读检查，实际: {sql_check.detail}"

    def test_with_select_passes_in_validate(self):
        """七项检查中也应接受 WITH 前缀的 SQL"""
        validator = Validator()
        report = validator.validate(
            sql="WITH cte AS (SELECT id FROM gold.t1) SELECT * FROM cte",
        )
        # 检查 #2（安全关键字）应通过——WITH 不是禁止关键字
        check2 = [c for c in report.checks if c.check_id == 2][0]
        assert check2.status == ValidationStatus.PASSED, \
            f"WITH 不应触发禁止关键字，实际: {check2.detail}"

    def test_explain_rejected_by_static_check(self):
        """EXPLAIN 不再通过——方案 A 口径收窄，只允许 SELECT/WITH"""
        validator = Validator()
        report = validator.validate_static(
            sql="EXPLAIN SELECT * FROM gold.t1",
        )
        sql_check = [c for c in report.checks if c.check_id == 101][0]
        assert sql_check.status == ValidationStatus.FAILED, \
            "EXPLAIN 不应再通过业务查询前缀检查（方案 A 口径收窄）"

    def test_insert_still_fails_static_check(self):
        """非只读前缀（INSERT）仍应被拦截"""
        validator = Validator()
        report = validator.validate_static(
            sql="INSERT INTO gold.t1 VALUES (1)",
        )
        sql_check = [c for c in report.checks if c.check_id == 101][0]
        assert sql_check.status == ValidationStatus.FAILED

    def test_describe_rejected_by_static_check(self):
        """DESCRIBE 不再通过——方案 A 口径收窄，只允许 SELECT/WITH"""
        validator = Validator()
        report = validator.validate_static(
            sql="DESCRIBE gold.t1",
        )
        sql_check = [c for c in report.checks if c.check_id == 101][0]
        assert sql_check.status == ValidationStatus.FAILED, \
            "DESCRIBE 不应再通过业务查询前缀检查（方案 A 口径收窄）"

    def test_show_rejected_by_static_check(self):
        """SHOW 从未有测试覆盖——方案 A 口径收窄后确认被拒绝"""
        validator = Validator()
        report = validator.validate_static(
            sql="SHOW TABLES",
        )
        sql_check = [c for c in report.checks if c.check_id == 101][0]
        assert sql_check.status == ValidationStatus.FAILED, \
            "SHOW 不应通过业务查询前缀检查（方案 A 口径收窄）"


class TestTableExtractionEnhanced:
    """增强的表名提取——逗号分隔、多跳 JOIN"""

    def test_comma_separated_from(self):
        """FROM t1, t2, t3 的逗号分隔表全部被识别"""
        refs = _extract_table_references(
            "SELECT * FROM gold.table_a, gold.table_b, gold.table_c WHERE id > 0"
        )
        assert "gold.table_a" in refs
        assert "gold.table_b" in refs
        assert "gold.table_c" in refs
        assert len(refs) == 3

    def test_multi_hop_join(self):
        """A JOIN B JOIN C 的多跳 JOIN 全部被识别"""
        refs = _extract_table_references(
            "SELECT * FROM gold.t1 "
            "INNER JOIN gold.t2 ON t1.id = t2.id "
            "LEFT JOIN gold.t3 ON t2.id = t3.id"
        )
        assert "gold.t1" in refs
        assert "gold.t2" in refs
        assert "gold.t3" in refs
        assert len(refs) == 3

    def test_comma_with_join_mixed(self):
        """逗号分隔与 JOIN 混合使用"""
        refs = _extract_table_references(
            "SELECT * FROM gold.t1, gold.t2 "
            "INNER JOIN gold.t3 ON t1.id = t3.id"
        )
        assert "gold.t1" in refs
        assert "gold.t2" in refs
        assert "gold.t3" in refs
        assert len(refs) == 3

    def test_cross_join(self):
        """CROSS JOIN 的表也被识别"""
        refs = _extract_table_references(
            "SELECT * FROM gold.t1 CROSS JOIN gold.t2"
        )
        assert len(refs) == 2
        assert "gold.t1" in refs
        assert "gold.t2" in refs

    def test_full_outer_join(self):
        """FULL OUTER JOIN 的表也被识别"""
        refs = _extract_table_references(
            "SELECT * FROM gold.t1 FULL OUTER JOIN gold.t2 ON t1.id = t2.id"
        )
        assert len(refs) == 2
        assert "gold.t1" in refs
        assert "gold.t2" in refs


class TestJoinWhitelistNoPlan:
    """plan=None 时 JOIN 白名单 SQL 文本兜底检查"""

    def test_no_plan_no_sql_returns_pending(self):
        """无 plan 且无 sql 时返回 PENDING"""
        result = check_join_whitelist()
        assert result.status == ValidationStatus.PENDING

    def test_no_plan_single_table_passes(self):
        """无 plan 但 SQL 仅引用单表——通过"""
        result = check_join_whitelist(
            sql="SELECT * FROM gold.table_a WHERE id = 1",
        )
        assert result.status == ValidationStatus.PASSED

    def test_no_plan_multi_table_no_whitelist_warns(self):
        """无 plan 多表但无 whitelist——WARN，不静默 PASS"""
        result = check_join_whitelist(
            sql="SELECT * FROM gold.table_a INNER JOIN gold.table_b ON a.id = b.id",
        )
        assert result.status == ValidationStatus.WARN
        assert "缺少 JOIN 白名单" in result.detail

    def test_no_plan_illegal_join_fails(self):
        """无 plan，SQL 中有非法 JOIN 对——FAIL，不静默通过"""
        result = check_join_whitelist(
            sql="SELECT * FROM gold.table_a INNER JOIN gold.table_c ON a.id = c.id",
            join_whitelist={("gold.table_a", "gold.table_b")},
        )
        assert result.status == ValidationStatus.FAILED
        assert "不在核准白名单" in result.detail

    def test_no_plan_legal_join_passes(self):
        """无 plan，SQL 中 JOIN 对在白名单——PASS"""
        result = check_join_whitelist(
            sql="SELECT * FROM gold.table_a INNER JOIN gold.table_b ON a.id = b.id",
            join_whitelist={("gold.table_a", "gold.table_b")},
        )
        assert result.status == ValidationStatus.PASSED

    def test_no_plan_three_table_illegal_pair_fails(self):
        """无 plan，三表中有一对不在白名单——FAIL"""
        result = check_join_whitelist(
            sql="SELECT * FROM gold.t1, gold.t2, gold.t3",
            join_whitelist={("gold.t1", "gold.t2")},  # t3 不在白名单中
        )
        assert result.status == ValidationStatus.FAILED
        assert "gold.t3" in result.detail or "t3" in result.detail


class TestValidateContext:
    """前置上下文检查——缺失时明确报告"""

    def test_context_complete_when_all_provided(self):
        """完整上下文时不报告缺失"""
        try:
            import duckdb
            conn = duckdb.connect(":memory:", read_only=False)
        except ImportError:
            pytest.skip("duckdb 未安装")
        validator = Validator(context={
            "conn": conn,
            "available_tables": {"gold.t1"},
            "join_whitelist": {("gold.t1", "gold.t2")},
        })
        issues = validator.validate_context()
        assert len(issues) == 0  # 上下文完整
        conn.close()

    def test_context_missing_conn_reported(self):
        """缺少 conn 时报告"""
        validator = Validator(context={})
        issues = validator.validate_context()
        assert len(issues) >= 1
        assert any("conn" in issue.detail.lower() for issue in issues)

    def test_context_missing_available_tables_reported(self):
        """缺少 available_tables 时报告"""
        validator = Validator(context={})
        issues = validator.validate_context()
        assert any("available_tables" in issue.detail.lower() for issue in issues)

    def test_context_missing_join_whitelist_reported(self):
        """缺少 join_whitelist 时报告"""
        validator = Validator(context={})
        issues = validator.validate_context()
        assert any("join_whitelist" in issue.detail.lower() for issue in issues)

    def test_context_partial_reports_only_missing(self):
        """部分上下文时只报告缺失项"""
        validator = Validator(context={
            "available_tables": {"gold.t1"},
        })
        issues = validator.validate_context()
        # 只有 conn 和 join_whitelist 缺失被报告
        assert len(issues) == 2
        missing_refs = {issue.detail for issue in issues}
        assert any("conn" in d.lower() for d in missing_refs)
        assert any("join_whitelist" in d.lower() for d in missing_refs)
        # available_tables 不应被报告（已提供）
        assert not any(
            "available_tables" in d.lower()
            for d in missing_refs
            if "缺少可用表" in d  # 仅检查"缺少"类报告
        )


class TestValidateContextAutoCall:
    """G3 安全压实：validate() 入口自动调用 validate_context()"""

    def test_context_warnings_auto_included_in_validate(self):
        """空上下文 validate() 时上下文告警自动出现在报告最前面"""
        validator = Validator()  # 无任何 context
        report = validator.validate(sql="SELECT 1")
        # 前 3 条应为上下文告警（check_id=0）
        first_three = report.checks[:3]
        for check in first_three:
            assert check.check_id == 0, f"前三条应为上下文检查，实际 check_id={check.check_id}"
            assert check.status == ValidationStatus.WARN
        assert any("conn" in c.detail.lower() for c in first_three)
        assert any("available_tables" in c.detail.lower() for c in first_three)
        assert any("join_whitelist" in c.detail.lower() for c in first_three)

    def test_full_context_produces_no_extra_checks(self):
        """完整上下文时 validate_context() 不产生额外条目"""
        try:
            import duckdb
            conn = duckdb.connect(":memory:", read_only=False)
            conn.execute("CREATE TABLE dws_daily_trip_summary (trip_date DATE, trip_count INTEGER)")
        except ImportError:
            pytest.skip("duckdb 未安装")

        validator = Validator(context={
            "available_tables": {"dws_daily_trip_summary"},
            "join_whitelist": set(),
            "conn": conn,
        })
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="dws_daily_trip_summary",
        )
        report = validator.validate(
            sql="SELECT * FROM dws_daily_trip_summary LIMIT 10",
            plan=plan,
        )
        # 上下文完整——无 check_id=0 的条目
        context_checks = [c for c in report.checks if c.check_id == 0]
        assert len(context_checks) == 0
        # 仅有 7 项主检查
        assert len(report.checks) == 7
        conn.close()

    def test_partial_context_correctly_reported(self):
        """部分上下文时仅报告缺失项"""
        validator = Validator(context={
            "available_tables": {"gold.t1"},
            "join_whitelist": {("gold.t1", "gold.t2")},
        })
        report = validator.validate(sql="SELECT * FROM gold.t1")
        # 仅 conn 缺失——只产生 1 条上下文告警
        context_checks = [c for c in report.checks if c.check_id == 0]
        assert len(context_checks) == 1
        assert "conn" in context_checks[0].detail.lower()


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

    # ── G1 安全压实：check_sample_execution 防御纵深测试 ──

    def test_sample_execution_reject_insert_prefix(self, conn):
        """INSERT 前缀在 sample 执行前被拦截（不落入 conn.execute）"""
        result = check_sample_execution(
            sql="INSERT INTO test_t VALUES (1, 2.0)",
            conn=conn,
        )
        assert result.status == ValidationStatus.FAILED
        assert "INSERT" in result.detail.upper() or "开头" in result.detail

    def test_sample_execution_reject_drop_keyword(self, conn):
        """DROP 关键字在 sample 执行前被拦截（前缀通过但含禁止关键字）"""
        result = check_sample_execution(
            sql="SELECT * FROM test_t; DROP TABLE test_t",
            conn=conn,
        )
        assert result.status == ValidationStatus.FAILED
        assert "DROP" in result.detail.upper() or "禁止关键字" in result.detail

    def test_sample_execution_accept_with_prefix(self, conn):
        """WITH 前缀的 CTE 查询可以通过 sample 执行"""
        result = check_sample_execution(
            sql="WITH cte AS (SELECT id FROM test_t) SELECT * FROM cte",
            conn=conn,
        )
        # 表 test_t 存在且 SELECT safe，应通过
        assert result.status == ValidationStatus.PASSED

    def test_sample_execution_reject_alter(self, conn):
        """ALTER 前缀在 sample 执行前被拦截"""
        result = check_sample_execution(
            sql="ALTER TABLE test_t RENAME TO test_t2",
            conn=conn,
        )
        assert result.status == ValidationStatus.FAILED
        assert "ALTER" in result.detail.upper() or "开头" in result.detail
