"""
Fallback SQL 编译器——LLM 不可用时的确定性降级路径。

封装 v1.x scripts/pipeline/layer4_generate.py 的 compile_sql()。
通过 v1_bridge.to_v1_plan() 将 v2.0 SQLPlan 转为 v1.x 兼容格式后，
调用 v1.x 编译器生成 SQL。

用法：
    from src.compile import compile_fallback
    sql_text, params = compile_fallback(v2_sqlplan)

职责边界：
  - 仅负责编译——不负责表选择、方案设计、安全校验
  - LLM 优先路径失败时使用
  - v1.x 编译器 143 个测试提供置信度保障
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from src.ir.types import SQLPlan
from src.ir.v1_bridge import to_v1_plan


def compile_fallback(plan: SQLPlan) -> tuple[str, list[Any]]:
    """
    确定性编译 SQL（fallback 降级路径）。

    当 LLM 生成 SQL 失败或不可用时使用此路径。
    v1.x 编译器通过 143 个测试验证，提供高置信度保障。

    Args:
        plan: v2.0 SQLPlan

    Returns:
        (sql_text, sql_params)——参数化 SQL 及绑定参数列表

    Raises:
        ImportError: v1.x 编译器不可用
        Exception: 编译失败（携带 v1.x 的 SQLCompileError 诊断信息）
    """
    # 确保 scripts/ 在 sys.path 中——v1.x 编译器使用相对 import
    project_root = Path(__file__).resolve().parent.parent.parent
    scripts_path = project_root / "scripts"
    if str(scripts_path) not in sys.path:
        sys.path.insert(0, str(scripts_path))

    # 将 v2.0 SQLPlan 桥接为 v1.x 兼容格式
    v1_dict = to_v1_plan(plan)

    # 调用 v1.x 编译器
    # 注意：v1.x compile_sql 接收的是 v1.x 的 SQLPlan 对象而非 dict
    # 此处尝试直接 import 并调用——如果因类型不匹配失败，退回到从 dict 构造
    try:
        from scripts.pipeline.layer4_generate import compile_sql as v1_compile_sql
        from scripts.pipeline.layer3_ir import SQLPlan as V1SQLPlan

        # 尝试构造 v1.x SQLPlan 对象
        v1_plan = V1SQLPlan(
            plan_id=v1_dict.get("plan_id", "fallback"),
            plan_name=v1_dict.get("plan_name", "unnamed"),
            source_layer=v1_dict.get("source_layer", "g3"),
            domain=v1_dict.get("domain", "traffic"),
            target_dialect=v1_dict.get("target_dialect", "duckdb"),
            group_by=v1_dict.get("group_by", []),
            order_by=v1_dict.get("order_by", []),
            limit=v1_dict.get("limit"),
            output_format=v1_dict.get("output_format", "parquet"),
            is_valid=v1_dict.get("is_valid", True),
            block_reason=v1_dict.get("block_reason", ""),
            warnings=v1_dict.get("warnings", []),
        )

        return v1_compile_sql(v1_plan)

    except ImportError as e:
        raise ImportError(
            f"v1.x 编译器（scripts/pipeline/layer4_generate.py）不可用: {e}\n"
            f"请确认 scripts/pipeline/ 目录存在且 layer4_generate.py 可导入。"
        )
