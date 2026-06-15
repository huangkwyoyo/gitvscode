"""
Layer 4 扩展：CTE 编译器（Phase 5）

职责：
  1. 接收 CTEDefinition IR 列表
  2. 编译为 SQL WITH 子句
  3. 强制执行 C4 递归深度约束（CTE 体内不允许嵌套 CTE）

LLM 角色：
  **完全禁止**。此层是纯编译器，零 LLM 参与。

设计原则：
  - CTE 编译需要递归调用 compile_sql() 来编译嵌套的 sql_plan
  - 使用回调模式避免 layer4_cte ↔ layer4_generate 循环导入
  - C4 约束：CTE 体内不允许嵌套 CTE（递归深度硬限制）

输入：list[CTEDefinition]、方言字符串、compile_sql 回调函数
输出：WITH 子句字符串（可拼接到主查询 SQL 前方）
"""

from __future__ import annotations

from typing import Callable, Optional

from .layer3_ir import (
    CTEDefinition,
    SQLPlan,
    SQLCompileError,
)


def _validate_cte_recursion(cte_definitions: list[CTEDefinition]) -> None:
    """
    强制执行 C4 递归深度约束

    规则：CTE 体内不允许嵌套 CTE。
    即：对于 cte_definitions 中的每个 CTE，其 sql_plan.cte_definitions 必须为空。

    此约束保证 WITH 子句只有一层深度，编译器不需要处理嵌套 WITH。
    """
    for cte in cte_definitions:
        if cte.sql_plan is None:
            continue
        if cte.sql_plan.cte_definitions:
            nested_names = [c.cte_name for c in cte.sql_plan.cte_definitions]
            raise SQLCompileError(
                f"CTE '{cte.cte_name}' 体内包含嵌套 CTE: {nested_names}——"
                f"违反 C4 递归深度约束（CTE 体内不允许嵌套 CTE）"
            )


def compile_cte_clause(
    cte_definitions: list[CTEDefinition],
    dialect: str,
    compile_sql_fn: Callable[[SQLPlan], tuple[str, list]],
) -> tuple[str, list]:
    """
    编译 CTE WITH 子句

    编译流程：
      1. 验证 C4 约束（无嵌套 CTE）
      2. 校验每个 CTE 的 sql_plan 非空
      3. 按顺序递归编译每个 CTE 体（通过 compile_sql_fn 回调）
      4. 组装为 WITH ... AS (...) 子句

    参数：
      cte_definitions: CTE 定义列表——按依赖顺序排列（被引用者在前）
      dialect: 目标 SQL 方言
      compile_sql_fn: compile_sql 回调——用于递归编译 CTE 体中的嵌套 SQLPlan

    返回：(with_clause: str, all_params: list)
      with_clause: 完整的 WITH 子句字符串（包含换行和缩进）
      all_params: 所有 CTE 体中收集的参数化查询参数列表（已去重合并）

    示例输出：
      WITH
        stage_1 AS (
          SELECT
              gold.fact_trips.trip_count AS "行程量"
          FROM gold.fact_trips
        ),
        stage_2 AS (
          SELECT
              stage_1."行程量",
              ROW_NUMBER() OVER (ORDER BY stage_1."行程量" DESC) AS "排名"
          FROM stage_1
        )

    异常：
      SQLCompileError——CTE 缺少 sql_plan、C4 约束违反、嵌套编译失败
    """
    if not cte_definitions:
        return "", []

    # ── 步骤 1：C4 约束校验 ──
    _validate_cte_recursion(cte_definitions)

    # ── 步骤 2：编译每个 CTE 体 ──
    cte_parts: list[str] = []
    all_params: list = []

    for cte in cte_definitions:
        if cte.sql_plan is None:
            raise SQLCompileError(
                f"CTE '{cte.cte_name}' 缺少 sql_plan——CTE 体必须是一个有效的 SQLPlan"
            )

        # 确保嵌套 SQLPlan 不包含 CTE（C4 约束已在步骤 1 校验，此处为防御性断言）
        if cte.sql_plan.cte_definitions:
            raise SQLCompileError(
                f"CTE '{cte.cte_name}' 体内包含嵌套 CTE——"
                f"此错误不应到达此处（已由 _validate_cte_recursion 拦截）"
            )

        # 递归编译 CTE 体——通过回调调用 compile_sql()
        body_sql, body_params = compile_sql_fn(cte.sql_plan)

        # 合并参数（保持顺序）
        all_params.extend(body_params)

        # 缩进 CTE 体 SQL（每行加 4 空格），提升可读性
        indented_body = "\n".join("    " + line for line in body_sql.split("\n"))
        cte_parts.append(f"  {cte.cte_name} AS (\n{indented_body}\n  )")

    # ── 步骤 3：组装 WITH 子句 ──
    with_clause = "WITH\n" + ",\n".join(cte_parts)

    return with_clause, all_params
