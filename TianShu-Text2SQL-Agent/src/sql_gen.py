"""
SQL 生成器：SQLPlan → SQL 字符串。

职责：
    将 Layer 2 的 SQLPlan（结构化执行计划）转换为 Layer 3 的 SQL 字符串。
    生成前必须通过安全检查（只读、JOIN 白名单、表引用合规、日期过滤通过 dim_date）。

安全校验规则（来自 AGENTS.md + contracts/sql_safety_policy.yml）：
    1. 必须以 SELECT 开头
    2. 表名必须完全限定（schema.table）
    3. 表名必须在可用表白名单中（如提供）
    4. 日期过滤必须通过 gold.dim_date
    5. JOIN 必须在核准白名单中（如提供）
    6. 不包含禁止的 SQL 关键字（INSERT/UPDATE/DELETE/DDL/PRAGMA 等）

注意：
    当前为桩实现。实际应由 LLM 根据 SQLPlan + Prompt 模板生成 SQL。
"""

from __future__ import annotations

import re
from typing import Optional

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


# ═══════════════════════════════════════════════════════════
# 表引用提取工具
# ═══════════════════════════════════════════════════════════


def _extract_table_references(sql: str) -> list[str]:
    """
    从 SQL 中提取 FROM 和 JOIN 子句引用的所有表名。

    支持：FROM table, FROM schema.table, JOIN table, INNER/LEFT/RIGHT/FULL/CROSS JOIN table

    Args:
        sql: SQL 字符串

    Returns:
        去重的表引用列表（保持出现顺序），包含完全限定名或非限定名
    """
    # 匹配 FROM/JOIN 后的表名（含可选的 schema 前缀）
    # 不捕获 AS 别名和 ON 条件
    pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)'
    matches = re.findall(pattern, sql, re.IGNORECASE)

    seen: set[str] = set()
    refs: list[str] = []
    for m in matches:
        key = m.lower()
        if key not in seen:
            seen.add(key)
            refs.append(m)
    return refs


def _has_date_condition(sql: str) -> bool:
    """
    检测 SQL 中是否包含日期过滤条件。

    检测模式：
        - 列名包含 date_key
        - BETWEEN + 8位数字（如 20260101）
        - BETWEEN + 日期字符串（如 '2026-01-01'）
        - 日期函数调用（DATE(), YEAR(), MONTH(), DAY()）

    Args:
        sql: SQL 字符串

    Returns:
        True 表示 SQL 包含日期过滤
    """
    sql_upper = sql.upper()
    date_patterns = [
        r'DATE_KEY',                         # 日期键列名
        r'BETWEEN\s+\d{8}',                  # BETWEEN 20260101 AND 20260131
        r"BETWEEN\s+'\d{4}-\d{2}-\d{2}'",   # BETWEEN '2026-01-01' AND '2026-01-31'
        r'\b(DATE|YEAR|MONTH|DAY)\s*\(',     # 日期函数
        r"'(?:\d{4}-\d{2}-\d{2}|\d{8})'",    # 日期字面量
    ]
    for pattern in date_patterns:
        if re.search(pattern, sql_upper):
            return True
    return False


def _check_join_whitelist(
    sql: str,
    join_whitelist: set[tuple[str, str]],
) -> list[str]:
    """
    检查 SQL 中的所有 JOIN 是否都在白名单中。

    比较时忽略大小写，确保 gold.fact_trips ↔ gold.dim_date 和
    gold.dim_date ↔ gold.fact_trips 都被正确匹配。

    Args:
        sql: SQL 字符串
        join_whitelist: JOIN 白名单，每项为 (table_a, table_b) 的 tuple

    Returns:
        违规列表
    """
    violations: list[str] = []

    # 提取 FROM 后的主表
    from_match = re.search(r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)', sql, re.IGNORECASE)
    main_table = from_match.group(1) if from_match else None

    if not main_table:
        return violations

    # 提取所有 JOIN 子句引用的表
    join_matches = re.findall(
        r'(?:INNER\s+|LEFT\s+|RIGHT\s+|FULL\s+|CROSS\s+)?JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)',
        sql, re.IGNORECASE,
    )

    if not join_matches:
        return violations

    # 构建大小写不敏感的白名单查找集合
    whitelist_lower = {
        (a.lower().strip(), b.lower().strip())
        for a, b in join_whitelist
    }

    main_lower = main_table.lower().strip()
    for join_table in join_matches:
        join_lower = join_table.lower().strip()
        pair = (main_lower, join_lower)
        reverse_pair = (join_lower, main_lower)
        if pair not in whitelist_lower and reverse_pair not in whitelist_lower:
            violations.append(
                f"JOIN {main_table} ↔ {join_table} 不在核准白名单中"
            )

    return violations


# ═══════════════════════════════════════════════════════════
# 安全校验主函数
# ═══════════════════════════════════════════════════════════


def validate_sql_safety(
    sql: str,
    forbidden_keywords: list[str],
    available_tables: Optional[set[str]] = None,
    join_whitelist: Optional[set[tuple[str, str]]] = None,
) -> list[str]:
    """
    对生成的 SQL 执行多层安全校验。

    检查项（按顺序）：
        1. 必须以 SELECT 开头（只读约束）
        2. 表名必须完全限定（schema.table 格式）
        3. 表名必须在可用表列表中（如提供了 available_tables）
        4. 日期过滤必须引用 gold.dim_date
        5. JOIN 必须在核准白名单中（如提供了 join_whitelist）
        6. 不包含禁止的 SQL 关键字

    Args:
        sql: 待检查的 SQL 字符串
        forbidden_keywords: 禁止的 SQL 关键字列表
        available_tables: 可用的完全限定表名集合（用于白名单校验）
        join_whitelist: JOIN 白名单，元素为 (table_a, table_b) tuple

    Returns:
        违规列表。空列表表示通过全部安全检查。
    """
    violations: list[str] = []
    sql_stripped = sql.strip()

    # ── 1. 必须以 SELECT 开头（允许 WITH ... SELECT 的 CTE 形式）──
    sql_upper_stripped = sql_stripped.upper()
    if not sql_upper_stripped.startswith('SELECT') and not sql_upper_stripped.startswith('WITH'):
        violations.append("SQL 必须以 SELECT 开头（只读查询），当前不以 SELECT/WITH 开头")

    # ── 2. 提取表引用，检查是否完全限定 ──
    table_refs = _extract_table_references(sql)
    unqualified = [t for t in table_refs if '.' not in t]
    if unqualified:
        violations.append(
            f"表名必须完全限定（schema.table 格式），"
            f"以下表名缺少 schema 前缀: {', '.join(unqualified)}"
        )

    non_gold_tables = [
        t for t in table_refs
        if "." in t and not t.lower().startswith("gold.")
    ]
    if non_gold_tables:
        violations.append(
            f"业务查询只能引用 gold 层表，以下表不允许直接查询: {', '.join(non_gold_tables)}"
        )

    # ── 3. 表名白名单校验 ──
    # C-1 修复：用 is not None 区分"未提供白名单"与"白名单为空（离线模式）"
    if available_tables is not None:
        # 大小写不敏感比较
        available_lower = {t.lower() for t in available_tables}
        unknown = [t for t in table_refs if t.lower() not in available_lower]
        if unknown:
            violations.append(
                f"以下表不在可用表白名单中: {', '.join(unknown)}"
            )

    # ── 4. 日期过滤必须通过 gold.dim_date ──
    has_date_filter = _has_date_condition(sql)
    has_dim_date = any('dim_date' in t.lower() for t in table_refs)
    if has_date_filter and not has_dim_date:
        violations.append(
            "SQL 包含日期过滤条件但未引用 gold.dim_date，"
            "日期过滤必须通过 gold.dim_date 进行（AGENTS.md 安全规则第3条）"
        )

    # ── 5. JOIN 白名单校验（兜底防线）──
    # B-7：SQL 级 JOIN 检查是兜底防线，防止 sql_plan_to_sql() 生成阶段
    # 引入了 SQLPlan 中未出现的 JOIN（防御深度）。
    # 主防线在 SQLPlan.validate()（IR 级）。
    # C-1 修复：用 is not None 区分"未提供白名单"与"白名单为空（离线模式）"
    if join_whitelist is not None:
        join_violations = _check_join_whitelist(sql, join_whitelist)
        violations.extend(join_violations)

    # ── 6. 禁止的 SQL 关键字检查 ──
    sql_upper = sql.upper()
    for keyword in forbidden_keywords:
        # 使用词边界匹配，避免误匹配列名中的子串
        pattern = r'\b' + re.escape(keyword.upper()) + r'\b'
        if re.search(pattern, sql_upper):
            violations.append(f"SQL 包含禁止的关键字: {keyword}")

    return violations
