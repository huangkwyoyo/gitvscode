"""
B-7 JOIN 白名单两层防线职责分离测试。

验证：
    1. IR 级（SQLPlan.validate()）为主防线
    2. SQL 级（validate_sql_safety()）为兜底防线
    3. 两层独立工作，不重复报错
"""


from src.ir import (
    JoinPlan,
    SQLPlan,
    Strategy,
)
from src.sql_gen import sql_plan_to_sql, validate_sql_safety, _check_join_whitelist


# ══════════════════════════════════════════════════════
# 辅助数据
# ══════════════════════════════════════════════════════

_SAMPLE_TABLES = {
    "gold.dws_daily_trip_summary",
    "gold.dim_date",
    "gold.fact_trips",
    "gold.dim_vehicle",
}

_SAMPLE_WHITELIST = {
    ("gold.dws_daily_trip_summary", "gold.dim_date"),
    ("gold.fact_trips", "gold.dim_date"),
    ("gold.fact_trips", "gold.dim_vehicle"),
}

_FORBIDDEN_KW = ["DELETE", "INSERT", "UPDATE", "DROP", "CREATE"]


def _make_plan(primary_table, join_table, join_on):
    """构造单 JOIN 的 SQLPlan"""
    return SQLPlan(
        strategy=Strategy.G3_DIRECT,
        primary_table=primary_table,
        joins=[JoinPlan(table=join_table, on=join_on)],
        where_clauses=["gold.dim_date.date BETWEEN DATE '2026-01-01' AND DATE '2026-01-31'"],
        group_by=["gold.dim_date.date"],
    )


# ══════════════════════════════════════════════════════
# IR 级主防线测试
# ══════════════════════════════════════════════════════

class TestIRPrimaryJoinCheck:
    """IR 级 JOIN 检查：SQLPlan.validate() 为主防线"""

    def test_valid_join_passes_ir_check(self):
        """白名单内的 JOIN 应通过 IR 级检查"""
        plan = _make_plan(
            "gold.dws_daily_trip_summary",
            "gold.dim_date",
            "gold.dim_date.date = gold.dws_daily_trip_summary.trip_date",
        )
        errors = plan.validate(
            available_tables=_SAMPLE_TABLES,
            join_whitelist=_SAMPLE_WHITELIST,
        )
        assert len([e for e in errors if "JOIN" in e and "IR 主防线" in e]) == 0

    def test_invalid_join_caught_at_ir_level(self):
        """非白名单 JOIN 应在 IR 级被拦截，带 [IR 主防线] 标记"""
        plan = _make_plan(
            "gold.fact_trips",
            "gold.dws_daily_parking_summary",  # 不在白名单中
            "some_col = other_col",
        )
        errors = plan.validate(
            available_tables=_SAMPLE_TABLES,
            join_whitelist=_SAMPLE_WHITELIST,
        )
        join_errors = [e for e in errors if "JOIN" in e]
        assert len(join_errors) >= 1
        assert "[IR 主防线]" in join_errors[0]

    def test_no_whitelist_provided_skips_ir_join_check(self):
        """未提供白名单时，IR 级跳过 JOIN 检查"""
        plan = _make_plan(
            "gold.fact_trips",
            "gold.unknown_table",
            "some_col = other_col",
        )
        errors = plan.validate(
            available_tables=_SAMPLE_TABLES,
            join_whitelist=None,  # 未提供
        )
        join_errors = [e for e in errors if "JOIN" in e]
        assert len(join_errors) == 0  # None 表示跳过检查

    def test_empty_whitelist_blocks_all_joins(self):
        """空白名单（如离线模式）应拦截所有 JOIN"""
        plan = _make_plan(
            "gold.dws_daily_trip_summary",
            "gold.dim_date",
            "some_col = other_col",
        )
        errors = plan.validate(
            available_tables=_SAMPLE_TABLES,
            join_whitelist=set(),  # 空白名单 = 离线模式，无允许的 JOIN
        )
        join_errors = [e for e in errors if "JOIN" in e]
        assert len(join_errors) == 1


# ══════════════════════════════════════════════════════
# SQL 级兜底防线测试
# ══════════════════════════════════════════════════════

class TestSQLFallbackJoinCheck:
    """SQL 级 JOIN 检查：validate_sql_safety() 为兜底防线"""

    def test_sql_level_catches_extra_join(self):
        """SQL 级应捕获 sql_plan_to_sql 意外引入的计划外 JOIN"""
        # 构造一个在 SQLPlan 中只有合法 JOIN 但实际 SQL 中出现了额外 JOIN 的场景
        # 这模拟了 sql_plan_to_sql 如果被修改后可能引入计划外 JOIN
        sql = (
            "SELECT gold.dim_date.date, SUM(trip_count) AS trip_count\n"
            "FROM gold.dws_daily_trip_summary\n"
            "INNER JOIN gold.dim_date\n"
            "  ON gold.dim_date.date = gold.dws_daily_trip_summary.trip_date\n"
            "INNER JOIN gold.dim_vehicle\n"  # 不在白名单中（对于 trip_summary）
            "  ON gold.dim_vehicle.vehicle_id = gold.dws_daily_trip_summary.vehicle_id\n"
            "WHERE gold.dim_date.date BETWEEN DATE '2026-01-01' AND DATE '2026-01-31'\n"
            "GROUP BY gold.dim_date.date"
        )
        violations = validate_sql_safety(
            sql,
            _FORBIDDEN_KW,
            available_tables=_SAMPLE_TABLES,
            join_whitelist=_SAMPLE_WHITELIST,
        )
        join_violations = [v for v in violations if "JOIN" in v]
        # trip_summary ↔ dim_vehicle 不在白名单中，应被拦截
        assert len(join_violations) >= 1

    def test_sql_level_passes_valid_join(self):
        """白名单内的 JOIN 应同时通过 SQL 级检查"""
        sql = (
            "SELECT gold.dim_date.date, SUM(trip_count) AS trip_count\n"
            "FROM gold.dws_daily_trip_summary\n"
            "INNER JOIN gold.dim_date\n"
            "  ON gold.dim_date.date = gold.dws_daily_trip_summary.trip_date\n"
            "WHERE gold.dim_date.date BETWEEN DATE '2026-01-01' AND DATE '2026-01-31'\n"
            "GROUP BY gold.dim_date.date"
        )
        violations = validate_sql_safety(
            sql,
            _FORBIDDEN_KW,
            available_tables=_SAMPLE_TABLES,
            join_whitelist=_SAMPLE_WHITELIST,
        )
        join_violations = [v for v in violations if "JOIN" in v]
        assert len(join_violations) == 0

    def test_ir_pass_then_sql_pass_end_to_end(self):
        """完整链路：IR 级通过 + SQL 级通过 → 无报错"""
        plan = _make_plan(
            "gold.dws_daily_trip_summary",
            "gold.dim_date",
            "gold.dim_date.date = gold.dws_daily_trip_summary.trip_date",
        )

        # IR 级检查
        ir_errors = plan.validate(
            available_tables=_SAMPLE_TABLES,
            join_whitelist=_SAMPLE_WHITELIST,
        )
        assert len(ir_errors) == 0

        # SQL 生成 + 安全检查
        sql = sql_plan_to_sql(plan)
        violations = validate_sql_safety(
            sql,
            _FORBIDDEN_KW,
            available_tables=_SAMPLE_TABLES,
            join_whitelist=_SAMPLE_WHITELIST,
        )
        assert len(violations) == 0

    def test_sql_level_preserves_other_checks(self):
        """SQL 级即使 JOIN 通过，其他检查（SELECT only 等）仍生效"""
        sql = "DELETE FROM gold.dws_daily_trip_summary"
        violations = validate_sql_safety(
            sql,
            _FORBIDDEN_KW,
            available_tables=_SAMPLE_TABLES,
            join_whitelist=_SAMPLE_WHITELIST,
        )
        # 必须有非 JOIN 相关的违规
        non_join = [v for v in violations if "JOIN" not in v]
        assert len(non_join) >= 1


# ══════════════════════════════════════════════════════
# _check_join_whitelist 单元测试
# ══════════════════════════════════════════════════════

class TestCheckJoinWhitelistUnit:
    """_check_join_whitelist() 工具函数单元测试"""

    def test_detects_unwhitelisted_join(self):
        """应检测出不在白名单中的 JOIN"""
        sql = (
            "SELECT * FROM gold.fact_trips\n"
            "INNER JOIN gold.fact_payments ON gold.fact_trips.id = gold.fact_payments.trip_id"
        )
        violations = _check_join_whitelist(sql, _SAMPLE_WHITELIST)
        assert len(violations) == 1
        assert "fact_payments" in violations[0]

    def test_allows_whitelisted_join(self):
        """应允许白名单中的 JOIN"""
        sql = (
            "SELECT * FROM gold.fact_trips\n"
            "INNER JOIN gold.dim_date ON gold.fact_trips.pickup_date_key = gold.dim_date.date_key"
        )
        violations = _check_join_whitelist(sql, _SAMPLE_WHITELIST)
        assert len(violations) == 0

    def test_no_joins_returns_empty(self):
        """没有 JOIN 的 SQL 应返回空 violations"""
        sql = "SELECT * FROM gold.fact_trips"
        violations = _check_join_whitelist(sql, _SAMPLE_WHITELIST)
        assert len(violations) == 0

    def test_case_insensitive_matching(self):
        """JOIN 检查应大小写不敏感"""
        sql = "SELECT * FROM gold.fact_trips\nINNER JOIN GOLD.DIM_DATE ON ..."
        violations = _check_join_whitelist(sql, _SAMPLE_WHITELIST)
        assert len(violations) == 0

    def test_reverse_order_also_matches(self):
        """反向顺序的 JOIN 对也应匹配"""
        whitelist = {("gold.dim_date", "gold.fact_trips")}
        sql = "SELECT * FROM gold.fact_trips\nINNER JOIN gold.dim_date ON ..."
        violations = _check_join_whitelist(sql, whitelist)
        assert len(violations) == 0
