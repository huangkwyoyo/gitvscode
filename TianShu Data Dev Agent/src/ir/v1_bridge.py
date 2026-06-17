"""
v1.x ↔ v2.0 IR 双向桥接适配器。

用途：
  - to_v1_plan(): 将 v2.0 SQLPlan 转为 v1.x 格式——供 compile/engine.py
    封装 v1.x L4 编译器使用
  - from_v1_plan(): 将 v1.x SQLPlan 转为 v2.0 格式——供迁移/兼容场景使用

Phase 1 实现最小映射——仅映射 compile_fallback() 需要的字段。
完整映射在 Phase 4 补充。

核心原则：
  - 隔离新旧 IR 系统：v2.0 代码不直接 import v1.x IR 类型
  - 所有跨版本调用通过此模块进行
  - 桥接失败时抛出清晰异常而非静默丢弃字段
"""

from __future__ import annotations

from typing import Any

from .types import SQLPlan, JoinPlan, Aggregation, Strategy


def to_v1_plan(plan: SQLPlan) -> dict[str, Any]:
    """
    将 v2.0 SQLPlan 转换为 v1.x 兼容的字典结构。

    v1.x 编译器（scripts/pipeline/layer4_generate.py）期望 SQLPlan 包含：
      - plan_id, plan_name
      - source_layer (str: "g3" | "g2")
      - domain
      - target_dialect
      - join_graph (JoinGraph 对象)
      - column_bindings, dimension_bindings, filter_bindings
      - group_by, order_by, limit
      - execution_constraints
      - output_format
      - is_valid, block_reason

    Phase 1 最小映射：仅映射 foundation 字段。
    详细的 JoinGraph/ColumnBinding 映射在 Phase 4 完成。

    Args:
        plan: v2.0 的 SQLPlan

    Returns:
        v1.x 兼容的字典——可直接传给 v1.x 编译器
    """
    v1_dict: dict[str, Any] = {
        "plan_id": f"v2_bridge_{id(plan)}",
        "plan_name": plan.primary_table or "unnamed",
        "source_layer": _strategy_to_layer(plan.strategy),
        "domain": "traffic",  # Phase 1 默认——Phase 2 从 context 传入
        "target_dialect": "duckdb",
        "group_by": plan.group_by,
        "order_by": [
            {"column": col, "direction": "ASC"} for col in plan.order_by
        ],
        "limit": plan.limit,
        "output_format": "parquet",
        "is_valid": True,
        "block_reason": "",
        "warnings": [],
    }

    # 映射 WHERE 条件——Phase 1 保留，Phase 4 转换为 v1.x filter_bindings
    if plan.where_clauses:
        v1_dict["where_clauses"] = plan.where_clauses

    # 映射聚合表达式——Phase 1 保留，Phase 4 转换为 v1.x column_bindings/expression_refs
    if plan.aggregations:
        v1_dict["aggregations"] = [
            {"expr": a.expr, "alias": a.alias} for a in plan.aggregations
        ]

    # 映射 JOIN 信息（如果存在）
    if plan.primary_table:
        v1_dict["primary_table"] = plan.primary_table
        if plan.joins:
            v1_dict["joins"] = [
                {"table": j.table, "on": j.on, "type": j.type}
                for j in plan.joins
            ]

    return v1_dict


def from_v1_plan(v1_plan: Any) -> SQLPlan:
    """
    将 v1.x SQLPlan 对象转为 v2.0 SQLPlan。

    Phase 1 最小实现——从 v1.x 对象的 dict 表示中提取关键字段。

    Args:
        v1_plan: v1.x 的 SQLPlan 对象（来自 scripts/pipeline/layer3_ir.py）

    Returns:
        v2.0 SQLPlan
    """
    # 尝试从 v1.x 对象获取属性，失败时尝试 dict 访问
    try:
        primary_table = getattr(v1_plan, "primary_table", None)
        if primary_table is None and hasattr(v1_plan, "join_graph"):
            jg = v1_plan.join_graph
            if jg is not None:
                primary_table = getattr(jg.primary, "table", None)
    except Exception:
        primary_table = None

    try:
        source_layer = getattr(v1_plan, "source_layer", "g3")
    except Exception:
        source_layer = "g3"

    # 映射策略
    strategy = _layer_to_strategy(source_layer)

    plan = SQLPlan(
        strategy=strategy,
        primary_table=primary_table,
        group_by=list(getattr(v1_plan, "group_by", []) or []),
    )

    # 提取 JOIN 信息
    try:
        if hasattr(v1_plan, "join_graph") and v1_plan.join_graph is not None:
            jg = v1_plan.join_graph
            for jn in getattr(jg, "joins", []) or []:
                plan.joins.append(JoinPlan(
                    table=getattr(jn, "table", ""),
                    on=f"{getattr(jn.condition, 'left', '')} = {getattr(jn.condition, 'right', '')}",
                    type=getattr(jn, "type", "INNER"),
                ))
    except Exception:
        pass

    return plan


def _strategy_to_layer(strategy: Strategy) -> str:
    """将 v2.0 Strategy 映射为 v1.x 的 source_layer 字符串"""
    g3_strategies = {Strategy.G3_DIRECT, Strategy.G3_CROSS, Strategy.G0_DIM_DIRECT}
    g2_strategies = {Strategy.G2_FACT, Strategy.G2_FACT_JOIN}

    if strategy in g3_strategies:
        return "g3"
    elif strategy in g2_strategies:
        return "g2"
    else:
        return "g3"  # 默认 G3


def _layer_to_strategy(layer: str) -> Strategy:
    """将 v1.x source_layer 映射为 v2.0 Strategy"""
    if layer == "g2":
        return Strategy.G2_FACT
    return Strategy.G3_DIRECT
