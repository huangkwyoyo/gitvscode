"""
SQL 生成器：SQLPlan → SQL 字符串。

职责：
    将 Layer 2 的 SQLPlan（结构化执行计划）转换为 Layer 3 的 SQL 字符串。
    生成前必须通过安全检查（只读、JOIN 白名单、表引用合规）。

注意：
    当前为桩实现。实际应由 LLM 根据 SQLPlan + Prompt 模板生成 SQL。
"""

from __future__ import annotations

from .ir import SQLPlan, Strategy


def sql_plan_to_sql(plan: SQLPlan) -> str:
    """
    将 SQLPlan 转换为 SQL 字符串。

    当前为桩实现，返回骨架 SQL。实际应由 LLM 根据 SQLPlan 生成。

    Args:
        plan: Layer 2 的执行计划

    Returns:
        SQL 字符串（仅 SELECT）
    """
    if plan.strategy == Strategy.NEED_CLARIFICATION:
        raise ValueError("SQLPlan 策略为 NEED_CLARIFICATION，不应生成 SQL")

    table = plan.primary_table or "未知表"

    # 构建 SELECT 子句
    if plan.aggregations:
        select_parts = [f"{a.expr} AS {a.alias}" for a in plan.aggregations]
        if plan.group_by:
            select_parts = plan.group_by + select_parts
        select_clause = ",\n  ".join(select_parts)
    else:
        select_clause = "*"

    # 构建 JOIN 子句
    join_clauses = ""
    for join in plan.joins:
        join_clauses += f"\n  {join.type} JOIN {join.table}\n    ON {join.on}"

    # 构建 WHERE 子句
    where_clause = ""
    if plan.where_clauses:
        where_clause = "\nWHERE " + "\n  AND ".join(plan.where_clauses)

    # 构建 GROUP BY / ORDER BY / LIMIT
    group_clause = ""
    if plan.group_by:
        group_clause = "\nGROUP BY " + ", ".join(plan.group_by)

    order_clause = ""
    if plan.order_by:
        order_clause = "\nORDER BY " + ", ".join(plan.order_by)

    limit_clause = ""
    if plan.limit:
        limit_clause = f"\nLIMIT {plan.limit}"

    sql = (
        f"SELECT {select_clause}"
        f"\nFROM {table}"
        f"{join_clauses}"
        f"{where_clause}"
        f"{group_clause}"
        f"{order_clause}"
        f"{limit_clause}"
    )

    return sql


def validate_sql_safety(sql: str, forbidden_keywords: list[str]) -> list[str]:
    """
    检查 SQL 字符串的安全性（只读检查）。

    Args:
        sql: SQL 字符串
        forbidden_keywords: 禁止的 SQL 关键字列表

    Returns:
        违规列表。空列表表示通过安全检查。
    """
    violations: list[str] = []
    sql_upper = sql.upper()

    for keyword in forbidden_keywords:
        # 使用词边界匹配，避免误匹配列名中的子串
        import re
        pattern = r'\b' + re.escape(keyword.upper()) + r'\b'
        if re.search(pattern, sql_upper):
            violations.append(f"SQL 包含禁止的关键字: {keyword}")

    return violations
