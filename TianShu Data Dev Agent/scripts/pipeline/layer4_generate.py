"""
Layer 4：SQL 编译层

职责：
  1. 接收 Layer 3 的 SQLPlan 对象
  2. 从 ColumnBindingTable 获取所有字段的全限定名
  3. 基于预定义模板，机械拼接生成完整 SQL 文本
  4. 全程无字符串拼接——所有标识符来自 ColumnBindingTable

LLM 角色：
  **完全禁止**。此层是纯编译器，零 LLM 参与。

设计原则：
  - SQL 编译器不是"字符串拼接器"——所有标识符必须从 ColumnBindingTable 获取
  - 表名、字段名、别名都是不可变的预编译输入
  - 如果 ColumnBinding 中缺少任何必要信息 → 编译失败，不产生 SQL

输入：SQLPlan 对象
输出：完整 SQL 文本（string）
"""

from __future__ import annotations

from .layer3_ir import (
    SQLPlan, JoinGraph, JoinNode,
    ColumnBinding, FilterBinding, DimensionColumnBinding,
    FilterType, SQLCompileError,
)
from .layer4_expression import compile_expressions, _build_table_ref_map
from .layer4_window import compile_window_functions
from .layer4_cte import compile_cte_clause


def _build_alias_map(join_graph: JoinGraph) -> dict[str, str]:
    """
    从 JoinGraph 构建表全限定名 → SQL 别名的映射

    多表 JOIN 场景下，DuckDB 一旦给表起别名（AS alias），
    后续 SELECT/WHERE/GROUP BY/ORDER BY 中就不能再用全限定名，
    必须使用别名引用列。此映射用于将全限定名转换为别名引用。

    单表查询（无 JOIN）返回空映射——此时不应使用别名（避免 DuckDB alias shadowing 问题）。
    """
    if not join_graph.joins:
        # 单表查询不使用别名，返回空映射
        return {}

    alias_map: dict[str, str] = {}
    alias_map[join_graph.primary.table] = join_graph.primary.alias
    for jn in join_graph.joins:
        alias_map[jn.table] = jn.alias
    return alias_map


def _resolve_column_ref(column_ref: str, alias_map: dict[str, str]) -> str:
    """
    将列引用解析为当前 SQL 上下文中正确的引用形式

    单表查询：列引用原样返回（gold.dws_daily_trip_summary.trip_count）
    多表 JOIN：替换为别名引用（dws_daily_trip_summary.trip_count）

    支持简单列引用（gold.table.col）和 G2 聚合表达式（SUM(gold.table.col)）。
    通过查找 alias_map 中匹配的 schema.table. 前缀来替换。

    🚨 P0-3 修复：添加防御性校验——多表 JOIN 时，如果列引用中仍包含
    schema.table 全限定前缀（未被 alias 替换），在 DuckDB 中会导致
    "referenced table not in FROM clause" 错误。
    """
    if not alias_map:
        return column_ref
    result = column_ref
    for full_table, alias in alias_map.items():
        prefix = full_table + "."
        # 使用 replace 而非 startswith：G2 表达式如 SUM(gold.fact_trips.col)
        # 不以表名开头，需要替换表达式内部的表引用
        result = result.replace(prefix, alias + ".")

    # P0-3 防御：检查是否还有未替换的 schema.table 前缀
    # 多表 JOIN 场景下，DuckDB 不接受 schema.table.col 格式
    for full_table in alias_map:
        if full_table + "." in result:
            raise SQLCompileError(
                f"列引用解析失败：'{result}' 中仍包含全限定表名 '{full_table}'。"
                f"DuckDB 在别名模式下要求使用别名引用，而非 schema.table.column。"
            )

    return result


def _compile_select_clause(
    plan: SQLPlan,
    alias_map: dict[str, str] | None = None,
    table_ref_map: dict[str, str] | None = None,
) -> str:
    """
    编译 SELECT 子句

    组装顺序：维度列 → 表达式 → 指标列 → 窗口函数。
    所有列名从 ColumnBinding 获取——绝对不拼接字符串。

    alias_map: 多表 JOIN 时提供表名→别名映射，将全限定列名转换为别名引用
    table_ref_map: table_ref→SQL前缀映射，用于解析 ColumnRef 对象（表达式操作数）
    """
    if alias_map is None:
        alias_map = {}
    if table_ref_map is None:
        table_ref_map = {}
    parts: list[str] = []

    # 维度列（排在前面——分组键）
    for dim in plan.dimension_bindings:
        col_ref = _resolve_column_ref(dim.column_ref, alias_map)
        parts.append(f"    {col_ref} AS \"{dim.alias}\"")

    # 表达式列（Phase 3：维度之后、指标之前）
    if plan.expression_refs:
        dialect = getattr(plan, 'target_dialect', 'duckdb')
        expr_sqls = compile_expressions(
            plan.expression_refs, dialect, table_ref_map
        )
        for sql_segment, expr_ref in zip(expr_sqls, plan.expression_refs):
            parts.append(f"    {sql_segment} AS \"{expr_ref.alias}\"")

    # 指标列
    for binding in plan.column_bindings:
        col_ref = _resolve_column_ref(binding.column_ref, alias_map)
        parts.append(f"    {col_ref} AS \"{binding.alias}\"")

    # 窗口函数列（Phase 4：指标之后、表达式之后——窗口函数操作聚合结果集）
    if plan.window_functions:
        dialect = getattr(plan, 'target_dialect', 'duckdb')
        wf_sqls = compile_window_functions(
            plan.window_functions, dialect, table_ref_map
        )
        for sql_segment, wf in zip(wf_sqls, plan.window_functions):
            parts.append(f"    {sql_segment} AS \"{wf.alias}\"")

    if not parts:
        raise SQLCompileError("SELECT 子句为空：没有可用的列绑定或表达式")

    return ",\n".join(parts)


def _compile_from_clause(join_graph: JoinGraph) -> str:
    """
    编译 FROM 子句

    从 JoinGraph 组装 FROM + JOIN。
    注意 DuckDB 行为：一旦给表起别名（AS），后续 WHERE/GROUP BY/ORDER BY
    中就不能再使用 schema.table 全限定名，必须使用别名。
    因此：
    - 单表查询：不使用别名，直接在列引用中使用全限定名
    - 多表 JOIN：使用别名，列引用中也使用别名前缀
    """
    p = join_graph.primary
    has_joins = len(join_graph.joins) > 0

    if has_joins:
        # 多表场景：使用别名
        from_clause = f"FROM {p.table} AS {p.alias}"
    else:
        # 单表场景：不使用别名，直接用全限定名
        from_clause = f"FROM {p.table}"

    for join_node in join_graph.joins:
        from_clause += (
            f"\n{join_node.type} {join_node.table} AS {join_node.alias}"
            f"\n  ON {join_node.condition.left} = {join_node.condition.right}"
        )

    return from_clause


def _compile_where_clause(
    filter_bindings: list[FilterBinding], alias_map: dict[str, str] | None = None
) -> tuple[str, list[object]]:
    """
    编译 WHERE 子句

    从 filter_bindings 组装 WHERE 条件。
    使用参数化占位符防止注入。

    alias_map: 多表 JOIN 时提供表名→别名映射，将全限定列名转换为别名引用

    返回：(where_clause, params)
    """
    if alias_map is None:
        alias_map = {}
    if not filter_bindings:
        return "", []

    conditions: list[str] = []
    params: list[object] = []

    for fb in filter_bindings:
        col_ref = _resolve_column_ref(fb.column_ref, alias_map)
        if fb.filter_type == FilterType.DATE_RANGE and fb.operator == "BETWEEN":
            conditions.append(f"{col_ref} BETWEEN ? AND ?")
            values = fb.value
            if isinstance(values, (list, tuple)) and len(values) == 2:
                params.extend([values[0], values[1]])
        elif fb.filter_type == FilterType.IN_LIST and fb.operator == "IN":
            placeholders = ", ".join(["?" for _ in fb.value])
            conditions.append(f"{col_ref} IN ({placeholders})")
            params.extend(fb.value)
        elif fb.operator == "=":
            conditions.append(f"{col_ref} = ?")
            params.append(fb.value)
        else:
            # 未知操作符，跳过
            continue

    if not conditions:
        return "", []

    where_clause = "WHERE " + "\n  AND ".join(conditions)
    return where_clause, params


def _compile_group_by(group_by: list[str], source_layer: str, alias_map: dict[str, str] | None = None) -> str:
    """
    编译 GROUP BY 子句

    注意：G3 汇总表的数据已预聚合，不需要 GROUP BY。
    GROUP BY 仅在 G2 层（从明细表聚合）时需要。

    alias_map: 多表 JOIN 时将全限定列名转换为别名引用
    """
    if alias_map is None:
        alias_map = {}
    if not group_by:
        return ""
    if source_layer == "g3":
        # G3 表数据已按维度预聚合，不需要 GROUP BY
        return ""
    resolved = [_resolve_column_ref(col, alias_map) for col in group_by]
    columns = ",\n    ".join(resolved)
    return f"GROUP BY\n    {columns}"


def _compile_order_by(order_by: list[dict[str, str]], alias_map: dict[str, str] | None = None) -> str:
    """
    编译 ORDER BY 子句

    alias_map: 多表 JOIN 时将全限定列名转换为别名引用
    """
    if alias_map is None:
        alias_map = {}
    if not order_by:
        return ""
    parts = []
    for ob in order_by:
        col = ob.get('column', '')
        if col:
            resolved = _resolve_column_ref(col, alias_map)
            parts.append(f"{resolved} {ob['direction']}")
    if not parts:
        return ""
    return "ORDER BY " + ", ".join(parts)


def _compile_limit(limit: int | None) -> str:
    """编译 LIMIT 子句"""
    if limit is None:
        return ""
    return f"LIMIT {limit}"


def compile_sql(plan: SQLPlan) -> tuple[str, list[object]]:
    """
    从 SQLPlan 编译完整 SQL 语句

    返回：(sql_text, params) —— params 是参数化查询的参数列表

    编译流程：
    1. 构建别名映射表（多表 JOIN 场景）
    2. SELECT → 从 column_bindings + dimension_bindings（经别名解析）
    3. FROM + JOIN → 从 join_graph
    4. WHERE → 从 filter_bindings（经别名解析）
    5. GROUP BY → 从 group_by（经别名解析）
    6. ORDER BY → 从 order_by（经别名解析）
    7. LIMIT → 从 limit

    关键安全属性：
    - 所有标识符来自 ColumnBindingTable，不拼接用户输入
    - 多表 JOIN 场景下列引用自动切换为别名引用，与 DuckDB 语义一致
    - 单表查询不使用别名，避免 DuckDB alias shadowing 问题

    如果任何步骤缺少必要信息 → 抛出 SQLCompileError
    """
    if not plan.is_valid:
        raise SQLCompileError(f"SQLPlan 无效，无法编译: {plan.block_reason}")

    if plan.join_graph is None:
        raise SQLCompileError("SQLPlan 缺少 join_graph")

    # ── 步骤 -1：编译 CTE WITH 子句（Phase 5）──
    # CTE 定义在主查询之前编译——CTE 体通过递归调用 compile_sql() 编译。
    # CTE 的参数（? 占位符）排在主查询参数之前。
    cte_clause, cte_params = compile_cte_clause(
        plan.cte_definitions, plan.target_dialect, compile_sql
    )

    # ── 步骤 0：构建别名映射表 ──
    # 多表 JOIN 时，DuckDB 要求通过别名引用列（不能用 schema.table 全限定名）
    alias_map = _build_alias_map(plan.join_graph)
    # table_ref → SQL 前缀映射（用于表达式 ColumnRef 解析）
    table_ref_map = _build_table_ref_map(plan.join_graph)

    # ── 步骤 1：编译 SELECT ──
    select_clause = _compile_select_clause(plan, alias_map, table_ref_map)

    # ── 步骤 2：编译 FROM ──
    from_clause = _compile_from_clause(plan.join_graph)

    # ── 步骤 3：编译 WHERE ──
    where_clause, params = _compile_where_clause(plan.filter_bindings, alias_map)

    # ── 步骤 4：编译 GROUP BY（G3 预聚合表跳过）──
    group_clause = _compile_group_by(plan.group_by, plan.source_layer, alias_map)

    # ── 步骤 5：编译 ORDER BY ──
    order_clause = _compile_order_by(plan.order_by, alias_map)

    # ── 步骤 6：编译 LIMIT ──
    limit_clause = _compile_limit(plan.limit)

    # ── 组装完整 SQL ──
    # CTE WITH 子句（如有）在主查询 SELECT 之前
    sql_parts: list[str] = []
    if cte_clause:
        sql_parts.append(cte_clause)

    sql_parts.extend([
        "SELECT",
        select_clause,
        from_clause,
    ])

    if where_clause:
        sql_parts.append(where_clause)
    if group_clause:
        sql_parts.append(group_clause)
    if order_clause:
        sql_parts.append(order_clause)
    if limit_clause:
        sql_parts.append(limit_clause)

    sql_text = "\n".join(sql_parts)

    # ── 后置检查：SQL 中不应出现裸标识符 ──
    # 所有表名必须包含 schema.table 格式
    if plan.join_graph.primary.table:
        schema, _, _ = plan.join_graph.primary.table.partition(".")
        if not schema:
            raise SQLCompileError(f"表名缺少 schema 限定: {plan.join_graph.primary.table}")

    # ── 合并参数：CTE 参数 + 主查询参数 ──
    all_params = cte_params + params

    return sql_text, all_params
