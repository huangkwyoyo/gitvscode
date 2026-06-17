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
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from src.ir.types import SQLPlan
from src.ir.v1_bridge import to_v1_plan


@contextmanager
def _temporary_sys_path(path: str) -> Iterator[None]:
    """
    上下文管理器：临时添加路径到 sys.path 并在退出时恢复。

    防止 sys.path.insert(0, ...) 污染全局 import 路径。
    """
    was_inserted = False
    try:
        if path not in sys.path:
            sys.path.insert(0, path)
            was_inserted = True
        yield
    finally:
        if was_inserted and path in sys.path:
            sys.path.remove(path)


def compile_fallback(plan: SQLPlan) -> tuple[str, list[Any]]:
    """
    确定性编译 SQL（fallback 降级路径）。

    当 LLM 生成 SQL 失败或不可用时使用此路径。
    v1.x 编译器通过 143 个测试验证，提供高置信度保障。

    使用上下文管理器管理 sys.path 临时添加，确保异常时路径恢复。

    Args:
        plan: v2.0 SQLPlan

    Returns:
        (sql_text, sql_params)——参数化 SQL 及绑定参数列表

    Raises:
        ImportError: v1.x 编译器不可用
        RuntimeError: 编译失败（携带 v1.x 的诊断信息）
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    scripts_path = str(project_root / "scripts")

    with _temporary_sys_path(scripts_path):
        return _do_compile(plan)


def _do_compile(plan: SQLPlan) -> tuple[str, list[Any]]:
    """
    实际编译逻辑——从 compile_fallback 中分离，便于测试 sys.path 隔离。

    Raises:
        ImportError: v1.x 编译器不可用
        RuntimeError: 编译失败或 v1 模块结构不兼容
    """
    # 将 v2.0 SQLPlan 桥接为 v1.x 兼容格式
    v1_dict = to_v1_plan(plan)

    # 导入 v1.x 编译器模块
    try:
        from scripts.pipeline.layer4_generate import compile_sql as v1_compile_sql
        from scripts.pipeline.layer3_ir import SQLPlan as V1SQLPlan
    except ImportError as e:
        raise ImportError(
            f"v1.x 编译器（scripts/pipeline/layer4_generate.py）不可用: {e}\n"
            f"请确认 scripts/pipeline/ 目录存在且 layer4_generate.py 可导入。"
        ) from e

    # 尝试构造 v1.x SQLPlan 对象
    # 注意：v1_dict 可能包含 where_clauses/aggregations 等 Phase 1 保留字段，
    # 但 V1SQLPlan 使用 filter_bindings/column_bindings 机制（Phase 4 转换）。
    # 此处仅提取 V1SQLPlan 支持的字段，额外字段不传入以避免 TypeError。
    _v1_supported = {
        "plan_id", "plan_name", "source_layer", "domain",
        "target_dialect", "group_by", "order_by", "limit",
        "output_format", "is_valid", "block_reason", "warnings",
    }
    v1_kwargs = {k: v for k, v in v1_dict.items() if k in _v1_supported}

    try:
        v1_plan = V1SQLPlan(**v1_kwargs)
    except (TypeError, ValueError, AttributeError) as e:
        raise RuntimeError(
            f"v1.x SQLPlan 构造失败——v1/v2 IR 结构不兼容: {e}\n"
            f"传入字段: {sorted(v1_kwargs.keys())}"
        ) from e

    try:
        return v1_compile_sql(v1_plan)
    except (TypeError, ValueError, AttributeError) as e:
        raise RuntimeError(
            f"v1.x compile_sql() 调用失败——v1 编译器内部不兼容: {e}"
        ) from e
