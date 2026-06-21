"""验证 SQL AST 安全边界。"""

from __future__ import annotations

import pytest

from src.ir import SQLPlan, Strategy
from src.sql_gen import sql_plan_to_sql
from src.sql_gen import validate_sql_safety


FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "MERGE", "REPLACE", "TRUNCATE",
    "CREATE", "ALTER", "DROP", "RENAME", "GRANT", "REVOKE",
    "ATTACH", "DETACH", "EXPORT", "IMPORT", "COPY", "INSTALL", "LOAD",
]


def _violations(sql: str) -> list[str]:
    """使用生产安全器校验独立 SQL。"""
    return validate_sql_safety(sql, FORBIDDEN_KEYWORDS)


def test_rejects_multiple_statements() -> None:
    """第二条有效语句必须被拒绝。"""
    assert _violations("SELECT 1; SELECT 2")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT read_blob('file')",
        "SELECT read_text('file')",
        "SELECT read_csv('file.csv')",
        "SELECT * FROM read_csv_auto('file.csv')",
        "SELECT read_json('file.json')",
        "SELECT read_json_auto('file.json')",
        "SELECT read_ndjson('file.ndjson')",
        "SELECT * FROM read_parquet('file.parquet')",
        "SELECT parquet_scan('file.parquet')",
        "SELECT csv_scan('file.csv')",
        "SELECT glob('*')",
        "SELECT sqlite_scan('file.db')",
        "SELECT postgres_scan('dsn')",
        "SELECT mysql_scan('dsn')",
        "SELECT http_get('https://example.invalid')",
    ],
)
def test_rejects_external_resource_functions(sql: str) -> None:
    """外部资源读取函数必须被拒绝。"""
    assert _violations(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1;",
        "SELECT ';' AS value",
        "SELECT 1 -- ;",
        "WITH cte AS (SELECT 1 AS value) SELECT value FROM cte",
    ],
)
def test_allows_valid_semicolon_and_cte_cases(sql: str) -> None:
    """非语句边界分号和查询型 CTE 必须继续允许。"""
    assert _violations(sql) == []


@pytest.mark.parametrize(
    "sql",
    [
        "WITH cte AS (SELECT 1) DELETE FROM gold.fact_trips",
        "WITH cte AS (SELECT 1) INSERT INTO gold.fact_trips SELECT * FROM cte",
        "WITH cte AS (SELECT 1) UPDATE gold.fact_trips SET trip_count = 0",
    ],
)
def test_rejects_cte_with_non_select_final_statement(sql: str) -> None:
    """CTE 最终语句不是查询时必须拒绝。"""
    assert _violations(sql)


def test_rejects_parse_failure() -> None:
    """无法解析的 SQL 必须关闭执行路径。"""
    assert _violations("SELECT (")


def test_rejects_unknown_statement_type() -> None:
    """未核准的顶层 AST 类型必须被拒绝。"""
    assert _violations("VALUES (1)")


def test_rejects_function_outside_allowlist() -> None:
    """非外部函数也必须显式进入白名单才能使用。"""
    assert _violations("SELECT LOWER('VALUE')")


def test_allows_registered_safe_functions() -> None:
    """当前指标链路需要的安全函数必须继续可用。"""
    sql = (
        "SELECT COUNT(*), SUM(1), AVG(1), MIN(1), MAX(1), "
        "COALESCE(NULL, 0), ROUND(1.2), CAST(1 AS INTEGER)"
    )
    assert _violations(sql) == []


def test_allows_existing_valid_gold_query() -> None:
    """现有 Gold 查询及日期过滤规则不得回归。"""
    sql = """
        SELECT gold.dim_date.date, SUM(gold.dws_daily_trip_summary.trip_count) AS trip_count
        FROM gold.dws_daily_trip_summary
        INNER JOIN gold.dim_date
          ON gold.dim_date.date = gold.dws_daily_trip_summary.trip_date
        WHERE gold.dim_date.date BETWEEN '2026-01-01' AND '2026-01-31'
        GROUP BY gold.dim_date.date
        ORDER BY gold.dim_date.date
    """
    available_tables = {"gold.dws_daily_trip_summary", "gold.dim_date"}
    join_whitelist = {("gold.dws_daily_trip_summary", "gold.dim_date")}

    assert validate_sql_safety(
        sql,
        FORBIDDEN_KEYWORDS,
        available_tables=available_tables,
        join_whitelist=join_whitelist,
    ) == []


def test_rejects_unsupported_multi_plan_sql_generation() -> None:
    """多计划占位符不能生成未知表 SQL。"""
    plan = SQLPlan(strategy=Strategy.UNSUPPORTED_MULTI_PLAN)

    with pytest.raises(ValueError, match="UNSUPPORTED_MULTI_PLAN"):
        sql_plan_to_sql(plan)
