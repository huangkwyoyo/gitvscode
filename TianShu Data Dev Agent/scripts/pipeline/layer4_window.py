"""
Layer 4 扩展：窗口函数编译器（Phase 4）

职责：
  1. 接收 WindowFunctionDef IR 和方言选择
  2. 将结构化窗口函数 IR 编译为方言特定的 SQL 窗口函数字符串
  3. 通过注册表模式支持多方言（默认实现覆盖标准 SQL 窗口函数）

LLM 角色：
  **完全禁止**。此层是纯编译器，零 LLM 参与。

设计原则：
  - 确定性：同样的 WindowFunctionDef + 方言 → 永远同样的 SQL 文本
  - 模板统一：所有窗口函数遵循 FUNC(args) OVER (PARTITION BY ... ORDER BY ... frame) 模板
  - 方言差异仅通过注册表覆盖边缘情况（如 Hive 的 ROWS-only 帧限制）

输入：list[WindowFunctionDef]、方言字符串、table_ref_map
输出：list[str]——SQL 窗口函数字符串（含 OVER 子句，不含 AS alias）
"""

from __future__ import annotations

from typing import Callable, Optional

from .layer3_ir import (
    WindowFunctionDef,
    WindowFunctionName,
    WindowFunctionArg,
    FunctionArgKind,
    OrderByEntry,
    FrameType,
    ColumnRef,
    LiteralValue,
    SQLCompileError,
    JoinGraph,
)
from .layer4_expression import (
    _resolve_column_ref_obj,
    _compile_literal,
    _build_table_ref_map,
)


# ═══════════════════════════════════════════════════════════
# 操作数解析
# ═══════════════════════════════════════════════════════════

def _resolve_window_arg(
    arg: WindowFunctionArg,
    table_ref_map: dict[str, str],
) -> str:
    """
    将 WindowFunctionArg 解析为 SQL 参数片段

    COLUMN 类型 → 通过 table_ref_map 解析 ColumnRef 为全限定列引用
    LITERAL 类型 → 编译 LiteralValue 为 SQL 字面量
    """
    if arg.kind == FunctionArgKind.COLUMN:
        if arg.column_ref is None:
            raise SQLCompileError("COLUMN 类型的窗口函数参数缺少 column_ref")
        return _resolve_column_ref_obj(arg.column_ref, table_ref_map)
    elif arg.kind == FunctionArgKind.LITERAL:
        if arg.literal is None:
            raise SQLCompileError("LITERAL 类型的窗口函数参数缺少 literal 值")
        return _compile_literal(arg.literal)
    else:
        raise SQLCompileError(f"未知的窗口函数参数类型: {arg.kind}")


# ═══════════════════════════════════════════════════════════
# OVER 子句编译
# ═══════════════════════════════════════════════════════════

def _compile_partition_by(
    partition_by: list[ColumnRef],
    table_ref_map: dict[str, str],
) -> str:
    """编译 PARTITION BY 子句——将 ColumnRef 列表解析为逗号分隔的列引用"""
    if not partition_by:
        return ""
    cols = [_resolve_column_ref_obj(cr, table_ref_map) for cr in partition_by]
    return f"PARTITION BY {', '.join(cols)}"


def _compile_window_order_by(
    order_by: list[OrderByEntry],
    table_ref_map: dict[str, str],
) -> str:
    """编译窗口函数的 ORDER BY 子句——解析 ColumnRef + 方向"""
    if not order_by:
        return ""
    parts = []
    for oe in order_by:
        col_sql = _resolve_column_ref_obj(oe.column_ref, table_ref_map)
        parts.append(f"{col_sql} {oe.direction}")
    return f"ORDER BY {', '.join(parts)}"


def _compile_frame_clause(wf: WindowFunctionDef) -> str:
    """
    编译窗口帧子句

    格式：{frame_type} BETWEEN {frame_start} AND {frame_end}

    仅当 frame_start 或 frame_end 有值时输出帧子句。
    默认值：frame_start 空 → "UNBOUNDED PRECEDING"，frame_end 空 → "CURRENT ROW"
    """
    if not wf.frame_start and not wf.frame_end:
        return ""
    frame_type = wf.frame_type.value
    start = wf.frame_start if wf.frame_start else "UNBOUNDED PRECEDING"
    end = wf.frame_end if wf.frame_end else "CURRENT ROW"
    return f"{frame_type} BETWEEN {start} AND {end}"


def _compile_over_clause(
    wf: WindowFunctionDef,
    table_ref_map: dict[str, str],
) -> str:
    """
    编译完整的 OVER 子句

    组装顺序：PARTITION BY → ORDER BY → frame 子句
    每个非空部分用换行缩进分隔。

    如果三个部分都为空（裸 OVER），返回 "OVER ()"。
    """
    parts = []

    partition_sql = _compile_partition_by(wf.partition_by, table_ref_map)
    if partition_sql:
        parts.append(partition_sql)

    order_sql = _compile_window_order_by(wf.order_by, table_ref_map)
    if order_sql:
        parts.append(order_sql)

    frame_sql = _compile_frame_clause(wf)
    if frame_sql:
        parts.append(frame_sql)

    if not parts:
        return "OVER ()"

    over_body = "\n    ".join(parts)
    return f"OVER (\n    {over_body}\n  )"


# ═══════════════════════════════════════════════════════════
# 默认窗口函数编译器（覆盖标准 SQL 方言：DuckDB / PostgreSQL）
# ═══════════════════════════════════════════════════════════

def _compile_window_function_default(
    wf: WindowFunctionDef,
    dialect: str,
    table_ref_map: dict[str, str],
) -> str:
    """
    默认窗口函数编译——适用于 DuckDB / PostgreSQL 等标准 SQL 方言

    模板：FUNC_NAME(arg1, arg2, ...) OVER (
              PARTITION BY ...
              ORDER BY ...
              frame_type BETWEEN ... AND ...
          )

    所有 12 种窗口函数（LEAD/LAG/ROW_NUMBER/RANK/DENSE_RANK/
    COUNT/SUM/AVG/MIN/MAX/FIRST_VALUE/LAST_VALUE）都遵循此模板。
    """
    # ── 编译函数名 ──
    func_name = wf.func_name.value.upper()

    # ── 编译参数列表 ──
    args_sql = [_resolve_window_arg(arg, table_ref_map) for arg in wf.args]
    func_call = f"{func_name}({', '.join(args_sql)})"

    # ── 编译 OVER 子句 ──
    over_clause = _compile_over_clause(wf, table_ref_map)

    # ── 组装 ──
    return f"{func_call} {over_clause}"


# ═══════════════════════════════════════════════════════════
# 注册表和主分发器
# ═══════════════════════════════════════════════════════════

# 类型别名：窗口函数编译处理函数
WindowFunctionHandler = Callable[
    [WindowFunctionDef, str, dict[str, str]],
    str,
]

# 二级注册表：{dialect: {WindowFunctionName: handler}}
_WINDOW_HANDLERS: dict[str, dict[WindowFunctionName, WindowFunctionHandler]] = {}


def _register_window_handler(
    dialect: str,
    func_name: WindowFunctionName,
    handler: WindowFunctionHandler,
) -> None:
    """注册一个方言+窗口函数名的编译处理函数"""
    if dialect not in _WINDOW_HANDLERS:
        _WINDOW_HANDLERS[dialect] = {}
    _WINDOW_HANDLERS[dialect][func_name] = handler


def _register_default_window_handlers() -> None:
    """注册 DuckDB 默认实现（覆盖全部 12 种窗口函数）"""
    all_functions = list(WindowFunctionName)
    for func_name in all_functions:
        _register_window_handler('duckdb', func_name, _compile_window_function_default)
    # spark_sql 使用与 DuckDB 相同的实现
    for func_name in all_functions:
        _register_window_handler('spark_sql', func_name, _compile_window_function_default)


def _register_postgresql_window_handlers() -> None:
    """注册 PostgreSQL 窗口函数实现（标准 SQL，与默认一致）"""
    all_functions = list(WindowFunctionName)
    for func_name in all_functions:
        _register_window_handler('postgresql', func_name, _compile_window_function_default)


def _register_hive_window_handlers() -> None:
    """
    注册 Hive 窗口函数实现

    Hive 的窗口函数语法与标准 SQL 基本一致。
    主要差异：
      - Hive 要求窗口函数有 ORDER BY 时必须同时有窗口帧（某些版本）
      - 建议优先使用 ROWS 帧而非 RANGE（性能更好）

    当前阶段：Hive 使用与 DuckDB 相同的默认实现。
    当发现具体方言差异时，在此处注册覆盖函数。
    """
    all_functions = list(WindowFunctionName)
    for func_name in all_functions:
        _register_window_handler('hive', func_name, _compile_window_function_default)


# 模块加载时自动注册
_register_default_window_handlers()
_register_postgresql_window_handlers()
_register_hive_window_handlers()


# ═══════════════════════════════════════════════════════════
# 核心分发器
# ═══════════════════════════════════════════════════════════

def _compile_window_function(
    wf: WindowFunctionDef,
    dialect: str,
    table_ref_map: dict[str, str],
) -> str:
    """
    将单个 WindowFunctionDef IR 编译为方言特定的 SQL 窗口函数字符串

    分发顺序：
      1. 查找当前方言注册表中对应窗口函数名的处理器
      2. 未找到 → fallback 到 'duckdb' 实现
      3. 仍未找到 → 抛出 SQLCompileError

    返回的 SQL 字符串格式：
      ROW_NUMBER() OVER (
          PARTITION BY t1.zone_name
          ORDER BY t1.trip_count DESC
      )
    """
    # 步骤 1：查找当前方言
    handlers = _WINDOW_HANDLERS.get(dialect, {})
    handler = handlers.get(wf.func_name)

    # 步骤 2：Fallback 到 DuckDB
    if handler is None and dialect != 'duckdb':
        duckdb_handlers = _WINDOW_HANDLERS.get('duckdb', {})
        handler = duckdb_handlers.get(wf.func_name)

    if handler is None:
        raise SQLCompileError(
            f"不支持的窗口函数组合：func_name='{wf.func_name.value}'，dialect='{dialect}'"
        )

    return handler(wf, dialect, table_ref_map)


# ═══════════════════════════════════════════════════════════
# 批量编译入口
# ═══════════════════════════════════════════════════════════

def compile_window_functions(
    window_functions: list[WindowFunctionDef],
    dialect: str,
    table_ref_map: dict[str, str],
) -> list[str]:
    """
    编译 SQLPlan 中的所有窗口函数

    校验规则：
      - 每个窗口函数必须有非空 alias（用于 SELECT 别名）
      - 别名不可重复（防止 SELECT 列名冲突）
      - PARTITION BY 和 ORDER BY 至少有一个非空（合规校验，非硬阻断）

    返回：与 window_functions 一一对应的 SQL 窗口函数字符串列表
      示例：[
        "ROW_NUMBER() OVER (\n    PARTITION BY t1.zone\n    ORDER BY t1.trip_count DESC\n  )",
        "LEAD(t1.date, 1) OVER (\n    ORDER BY t1.date\n  )",
      ]

    调用方负责：
      - 将每个 SQL 片段与对应的 WindowFunctionDef.alias 配对
      - 组装到 SELECT 子句中（如 f"{sql} AS \"{wf.alias}\""）
    """
    if not window_functions:
        return []

    # ── 校验：别名唯一性 ──
    seen_aliases: set[str] = set()
    for wf in window_functions:
        if not wf.alias:
            raise SQLCompileError(
                f"窗口函数 '{wf.func_name.value}' 缺少 alias——所有窗口函数必须有别名"
            )
        if wf.alias in seen_aliases:
            raise SQLCompileError(
                f"重复的窗口函数别名 '{wf.alias}'——每个窗口函数的 alias 必须唯一"
            )
        seen_aliases.add(wf.alias)

    # ── 编译 ──
    results: list[str] = []
    for wf in window_functions:
        sql_segment = _compile_window_function(wf, dialect, table_ref_map)
        results.append(sql_segment)

    return results
