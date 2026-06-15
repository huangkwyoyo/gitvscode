"""
Layer 4 扩展：表达式编译器（Phase 3）

职责：
  1. 接收 ExpressionRef IR 和方言选择
  2. 将结构化表达式 IR 编译为方言特定的 SQL 表达式字符串
  3. 通过注册表模式支持多方言（DuckDB 为默认实现）

LLM 角色：
  **完全禁止**。此层是纯编译器，零 LLM 参与。

设计原则：
  - 确定性：同样的 ExpressionRef + 方言 → 永远同样的 SQL 文本
  - 方言感知：通过注册表模式按方言+表达式类型分发，O(1) 查找
  - 递归安全：嵌套 EXPR_REF 操作数通过两遍编译 + 深度上限处理
  - 类型安全：所有合法值由 ExpressionType 等枚举约束

输入：ExpressionRef 对象、方言字符串、table_ref 映射表
输出：SQL 表达式字符串（不含 AS alias——别名由调用方附加）
"""

from __future__ import annotations

from typing import Callable, Optional, Any

from .layer3_ir import (
    ExpressionRef,
    ExpressionOperand,
    ExpressionConfig,
    ExpressionType,
    OperandKind,
    ColumnRef,
    LiteralValue,
    LiteralType,
    JoinGraph,
    SQLCompileError,
)


# ═══════════════════════════════════════════════════════════
# 基础设施：表引用映射和列引用解析
# ═══════════════════════════════════════════════════════════


def _build_table_ref_map(join_graph: JoinGraph) -> dict[str, str]:
    """
    构建 table_ref → SQL 列前缀 映射

    这是 ColumnRef(table_ref, column_name) 解析为 SQL 列引用的关键。

    单表查询（无 JOIN）：
      FROM 子句不使用别名 → table_ref 映射为全限定表名
      {'primary': 'gold.dws_daily_trip_summary'}
      → ColumnRef("primary", "trip_count") → "gold.dws_daily_trip_summary.trip_count"

    多表 JOIN：
      FROM 子句使用别名 → table_ref 映射为 SQL 别名
      {'primary': 't_daily_trip'}
      → ColumnRef("primary", "trip_count") → "t_daily_trip.trip_count"

    未来扩展：当 JoinNode 支持命名 ref 后，可以为 joins 中的表添加映射。
    """
    ref_map: dict[str, str] = {}
    if not join_graph:
        return ref_map

    if not join_graph.joins:
        # 单表查询：FROM gold.table（无别名）
        ref_map['primary'] = join_graph.primary.table
    else:
        # 多表 JOIN：FROM gold.table AS alias
        ref_map['primary'] = join_graph.primary.alias
        # 未来：为 join_graph.joins 中的每个节点添加 {ref: alias} 映射
        # for jn in join_graph.joins:
        #     ref_map[jn.ref] = jn.alias

    return ref_map


def _resolve_column_ref_obj(
    ref: ColumnRef,
    table_ref_map: dict[str, str],
) -> str:
    """
    将 ColumnRef 对象解析为 SQL 列引用字符串

    输入：ColumnRef(table_ref="primary", column_name="trip_count")
    输出：'gold.dws_daily_trip_summary.trip_count'（单表）或 't1.trip_count'（多表）

    规则：
      - table_ref 存在于映射中 → 使用映射值作为前缀
      - table_ref 不存在 → 直接使用 table_ref 值（防御性降级）
    """
    prefix = table_ref_map.get(ref.table_ref, ref.table_ref)
    return f"{prefix}.{ref.column_name}"


def _compile_literal(literal: LiteralValue) -> str:
    """
    将 LiteralValue 编译为 SQL 字面量字符串

    STRING:  单引号包裹，内部单引号转义为 ''（SQL 标准）
    INTEGER: 裸数字
    FLOAT:   裸浮点数
    BOOLEAN: TRUE / FALSE 关键字
    """
    if literal.literal_type == LiteralType.STRING:
        escaped = str(literal.value).replace("'", "''")
        return f"'{escaped}'"
    elif literal.literal_type == LiteralType.INTEGER:
        return str(int(literal.value))
    elif literal.literal_type == LiteralType.FLOAT:
        return str(float(literal.value))
    elif literal.literal_type == LiteralType.BOOLEAN:
        return "TRUE" if literal.value else "FALSE"
    else:
        raise SQLCompileError(f"未知的字面量类型: {literal.literal_type}")


# ═══════════════════════════════════════════════════════════
# 操作数编译（含嵌套表达式递归）
# ═══════════════════════════════════════════════════════════

def _compile_operand(
    op: ExpressionOperand,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """
    编译单个表达式操作数

    分派逻辑：
      - COLUMN_REF → _resolve_column_ref_obj()
      - LITERAL    → _compile_literal()
      - EXPR_REF   → 递归编译 expr_map[op.expr_alias]

    _depth 参数防止无限递归（上限 10 层）。
    """
    if _depth > 10:
        raise SQLCompileError(
            f"表达式嵌套深度超过上限（10 层），操作数 expr_alias='{op.expr_alias}'"
        )

    if op.kind == OperandKind.COLUMN_REF:
        if op.column_ref is None:
            raise SQLCompileError("COLUMN_REF 操作数缺少 column_ref")
        return _resolve_column_ref_obj(op.column_ref, table_ref_map)

    elif op.kind == OperandKind.LITERAL:
        if op.literal is None:
            raise SQLCompileError("LITERAL 操作数缺少 literal 值")
        return _compile_literal(op.literal)

    elif op.kind == OperandKind.EXPR_REF:
        if not op.expr_alias:
            raise SQLCompileError("EXPR_REF 操作数缺少 expr_alias")
        if op.expr_alias not in expr_map:
            raise SQLCompileError(
                f"嵌套表达式引用 '{op.expr_alias}' 未在 expression_refs 中定义"
            )
        inner = expr_map[op.expr_alias]
        # 递归展开：编译引用的表达式，返回完整 SQL 文本
        return _compile_expression(
            inner, expr_map, dialect, table_ref_map, _depth + 1
        )

    raise SQLCompileError(f"未知的操作数类型: {op.kind}")


# ═══════════════════════════════════════════════════════════
# 表达式类型：LITERAL（字面量表达式）
# ═══════════════════════════════════════════════════════════

def _compile_literal_expr(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """编译字面量表达式——直接输出字面值的 SQL 表示"""
    if not expr.operands:
        raise SQLCompileError("LITERAL 表达式缺少操作数")
    if expr.operands[0].kind != OperandKind.LITERAL:
        raise SQLCompileError("LITERAL 表达式的第一个操作数必须是 LITERAL 类型")
    if expr.operands[0].literal is None:
        raise SQLCompileError("LITERAL 表达式操作数缺少 literal 值")
    return _compile_literal(expr.operands[0].literal)


# ═══════════════════════════════════════════════════════════
# 表达式类型：COLUMN_REF（简单列引用透传）
# ═══════════════════════════════════════════════════════════

def _compile_column_ref_expr(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """编译列引用表达式——将 ColumnRef 解析为 SQL 列引用"""
    if not expr.operands:
        raise SQLCompileError("COLUMN_REF 表达式缺少操作数")
    if expr.operands[0].kind != OperandKind.COLUMN_REF:
        raise SQLCompileError("COLUMN_REF 表达式的第一个操作数必须是 COLUMN_REF 类型")
    if expr.operands[0].column_ref is None:
        raise SQLCompileError("COLUMN_REF 表达式操作数缺少 column_ref")
    return _resolve_column_ref_obj(expr.operands[0].column_ref, table_ref_map)


# ═══════════════════════════════════════════════════════════
# 表达式类型：CONCAT（字符串拼接）
# ═══════════════════════════════════════════════════════════

def _compile_concat_duckdb(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """DuckDB/Hive：CONCAT(a, b, c) 函数语法"""
    compiled = [
        _compile_operand(op, expr_map, dialect, table_ref_map, _depth)
        for op in expr.operands
    ]
    return f"CONCAT({', '.join(compiled)})"


def _compile_concat_postgresql(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """PostgreSQL：a || b || c 运算符语法"""
    compiled = [
        _compile_operand(op, expr_map, dialect, table_ref_map, _depth)
        for op in expr.operands
    ]
    return ' || '.join(compiled)


# ═══════════════════════════════════════════════════════════
# 表达式类型：COALESCE（空值合并）
# ═══════════════════════════════════════════════════════════

def _compile_coalesce(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """COALESCE(a, b, c)——所有方言语法一致"""
    if not expr.operands:
        raise SQLCompileError("COALESCE 表达式至少需要一个操作数")
    compiled = [
        _compile_operand(op, expr_map, dialect, table_ref_map, _depth)
        for op in expr.operands
    ]
    return f"COALESCE({', '.join(compiled)})"


# ═══════════════════════════════════════════════════════════
# 表达式类型：CAST（类型转换）
# ═══════════════════════════════════════════════════════════

def _compile_cast_duckdb(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """DuckDB/Hive：CAST(value AS TYPE)"""
    if not expr.operands:
        raise SQLCompileError("CAST 表达式缺少操作数")
    if not expr.config.target_type:
        raise SQLCompileError("CAST 表达式缺少 config.target_type")
    value_sql = _compile_operand(
        expr.operands[0], expr_map, dialect, table_ref_map, _depth
    )
    return f"CAST({value_sql} AS {expr.config.target_type.upper()})"


def _compile_cast_postgresql(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """PostgreSQL：value::type 简写语法"""
    if not expr.operands:
        raise SQLCompileError("CAST 表达式缺少操作数")
    if not expr.config.target_type:
        raise SQLCompileError("CAST 表达式缺少 config.target_type")
    value_sql = _compile_operand(
        expr.operands[0], expr_map, dialect, table_ref_map, _depth
    )
    return f"{value_sql}::{expr.config.target_type.lower()}"


# ═══════════════════════════════════════════════════════════
# 表达式类型：ARITHMETIC（算术运算）
# ═══════════════════════════════════════════════════════════

def _compile_arithmetic(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """算术运算——所有方言语法一致：(a + b), (a / b)"""
    if not expr.config.op:
        raise SQLCompileError("ARITHMETIC 表达式缺少 config.op")
    if expr.config.op not in ('+', '-', '*', '/', '%'):
        raise SQLCompileError(f"不支持的算术运算符: {expr.config.op}")
    if len(expr.operands) < 2:
        raise SQLCompileError(
            f"ARITHMETIC 表达式至少需要 2 个操作数，实际: {len(expr.operands)}"
        )

    compiled = [
        _compile_operand(op, expr_map, dialect, table_ref_map, _depth)
        for op in expr.operands
    ]
    # 用括号包裹避免运算符优先级歧义
    return f"({f' {expr.config.op} '.join(compiled)})"


# ═══════════════════════════════════════════════════════════
# 表达式类型：DATE_DIFF（日期差值）
# ═══════════════════════════════════════════════════════════

def _compile_date_diff_duckdb(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """
    DuckDB DATEDIFF 语法：DATEDIFF('unit', start, end)

    示例：DATEDIFF('day', t1.start_date, t1.end_date)
    """
    if not expr.config.unit:
        raise SQLCompileError("DATE_DIFF 表达式缺少 config.unit")
    if len(expr.operands) < 2:
        raise SQLCompileError(
            f"DATE_DIFF 表达式需要 2 个操作数（start, end），实际: {len(expr.operands)}"
        )

    start_sql = _compile_operand(
        expr.operands[0], expr_map, dialect, table_ref_map, _depth
    )
    end_sql = _compile_operand(
        expr.operands[1], expr_map, dialect, table_ref_map, _depth
    )
    return f"DATEDIFF('{expr.config.unit}', {start_sql}, {end_sql})"


def _compile_date_diff_hive(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """
    Hive DATEDIFF 语法：DATEDIFF(end, start)

    注意：Hive 的 DATEDIFF 只返回天数，不接受 unit 参数。
    参数顺序与 DuckDB 不同（end 在前，start 在后）。
    """
    if len(expr.operands) < 2:
        raise SQLCompileError(
            f"DATE_DIFF 表达式需要 2 个操作数（start, end），实际: {len(expr.operands)}"
        )

    # Hive：第一个操作数是 start，第二个是 end
    # 但 DATEDIFF 的参数顺序是 (end, start)
    end_sql = _compile_operand(
        expr.operands[1], expr_map, dialect, table_ref_map, _depth
    )
    start_sql = _compile_operand(
        expr.operands[0], expr_map, dialect, table_ref_map, _depth
    )
    return f"DATEDIFF({end_sql}, {start_sql})"


def _compile_date_diff_postgresql(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """
    PostgreSQL 日期差：(end - start)

    日期类型直接相减返回天数（INTEGER）。
    """
    if len(expr.operands) < 2:
        raise SQLCompileError(
            f"DATE_DIFF 表达式需要 2 个操作数（start, end），实际: {len(expr.operands)}"
        )

    start_sql = _compile_operand(
        expr.operands[0], expr_map, dialect, table_ref_map, _depth
    )
    end_sql = _compile_operand(
        expr.operands[1], expr_map, dialect, table_ref_map, _depth
    )
    return f"({end_sql} - {start_sql})"


# ═══════════════════════════════════════════════════════════
# 表达式类型：DATE_TRUNC（日期截断）
# ═══════════════════════════════════════════════════════════

def _compile_date_trunc_duckdb(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """DuckDB：DATE_TRUNC('unit', col)"""
    if not expr.config.unit:
        raise SQLCompileError("DATE_TRUNC 表达式缺少 config.unit")
    if not expr.operands:
        raise SQLCompileError("DATE_TRUNC 表达式缺少操作数（日期列）")
    col_sql = _compile_operand(
        expr.operands[0], expr_map, dialect, table_ref_map, _depth
    )
    return f"DATE_TRUNC('{expr.config.unit}', {col_sql})"


def _compile_date_trunc_hive(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """Hive：TRUNC(col, 'unit')——参数顺序与 DuckDB 相反"""
    if not expr.config.unit:
        raise SQLCompileError("DATE_TRUNC 表达式缺少 config.unit")
    if not expr.operands:
        raise SQLCompileError("DATE_TRUNC 表达式缺少操作数（日期列）")
    col_sql = _compile_operand(
        expr.operands[0], expr_map, dialect, table_ref_map, _depth
    )
    return f"TRUNC({col_sql}, '{expr.config.unit}')"


# ═══════════════════════════════════════════════════════════
# 表达式类型：DATE_FORMAT（日期格式化）
# ═══════════════════════════════════════════════════════════

def _compile_date_format_duckdb(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """DuckDB：STRFTIME(col, 'format')"""
    if not expr.config.format:
        raise SQLCompileError("DATE_FORMAT 表达式缺少 config.format")
    if not expr.operands:
        raise SQLCompileError("DATE_FORMAT 表达式缺少操作数（日期列）")
    col_sql = _compile_operand(
        expr.operands[0], expr_map, dialect, table_ref_map, _depth
    )
    return f"STRFTIME({col_sql}, '{expr.config.format}')"


def _compile_date_format_hive(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """Hive：DATE_FORMAT(col, 'format')"""
    if not expr.config.format:
        raise SQLCompileError("DATE_FORMAT 表达式缺少 config.format")
    if not expr.operands:
        raise SQLCompileError("DATE_FORMAT 表达式缺少操作数（日期列）")
    col_sql = _compile_operand(
        expr.operands[0], expr_map, dialect, table_ref_map, _depth
    )
    return f"DATE_FORMAT({col_sql}, '{expr.config.format}')"


def _compile_date_format_postgresql(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """PostgreSQL：TO_CHAR(col, 'format')"""
    if not expr.config.format:
        raise SQLCompileError("DATE_FORMAT 表达式缺少 config.format")
    if not expr.operands:
        raise SQLCompileError("DATE_FORMAT 表达式缺少操作数（日期列）")
    col_sql = _compile_operand(
        expr.operands[0], expr_map, dialect, table_ref_map, _depth
    )
    return f"TO_CHAR({col_sql}, '{expr.config.format}')"


# ═══════════════════════════════════════════════════════════
# 表达式类型：CONDITIONAL（CASE WHEN）
# ═══════════════════════════════════════════════════════════

def _compile_conditional(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """
    编译 CASE WHEN 条件表达式——所有方言语法一致

    格式：
      CASE
        WHEN condition_1 THEN result_1
        WHEN condition_2 THEN result_2
        ELSE default_value
      END

    config.when_clauses 格式：
      [{"condition": "<sql_text>", "result": "<sql_text>"}, ...]

    注意：condition 和 result 字段当前约定为 SQL 文本（或表达式别名）。
    未来迭代将扩展为结构化条件 ExpressionRef。
    """
    when_clauses = expr.config.when_clauses
    if not when_clauses:
        raise SQLCompileError("CONDITIONAL 表达式缺少 config.when_clauses")

    lines = ["CASE"]
    for clause in when_clauses:
        cond = clause.get("condition", "TRUE")
        then_val = clause.get("result", "NULL")
        # 如果 condition/result 是表达式别名，尝试从 expr_map 解析
        if isinstance(cond, str) and cond in expr_map:
            cond = _compile_expression(
                expr_map[cond], expr_map, dialect, table_ref_map, _depth + 1
            )
        if isinstance(then_val, str) and then_val in expr_map:
            then_val = _compile_expression(
                expr_map[then_val], expr_map, dialect, table_ref_map, _depth + 1
            )
        lines.append(f"  WHEN {cond} THEN {then_val}")

    if expr.config.else_value is not None:
        lines.append(f"  ELSE {expr.config.else_value}")
    lines.append("END")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# 注册表和主分发器
# ═══════════════════════════════════════════════════════════

# 类型别名：表达式编译处理函数
ExpressionHandler = Callable[
    [ExpressionRef, dict[str, ExpressionRef], str, dict[str, str], int],
    str,
]

# 二级注册表：{dialect: {ExpressionType: handler}}
_EXPRESSION_HANDLERS: dict[str, dict[ExpressionType, ExpressionHandler]] = {}


def _register_handler(
    dialect: str,
    expr_type: ExpressionType,
    handler: ExpressionHandler,
) -> None:
    """注册一个方言+表达式类型的编译处理函数"""
    if dialect not in _EXPRESSION_HANDLERS:
        _EXPRESSION_HANDLERS[dialect] = {}
    _EXPRESSION_HANDLERS[dialect][expr_type] = handler


# ── 模块加载时自动注册所有方言的实现 ──


def _register_default_handlers() -> None:
    """注册 DuckDB 默认实现（覆盖全部 10 种表达式类型）"""
    common: list[tuple[ExpressionType, ExpressionHandler]] = [
        (ExpressionType.LITERAL, _compile_literal_expr),
        (ExpressionType.COLUMN_REF, _compile_column_ref_expr),
        (ExpressionType.CONCAT, _compile_concat_duckdb),
        (ExpressionType.COALESCE, _compile_coalesce),
        (ExpressionType.CAST, _compile_cast_duckdb),
        (ExpressionType.ARITHMETIC, _compile_arithmetic),
        (ExpressionType.DATE_DIFF, _compile_date_diff_duckdb),
        (ExpressionType.DATE_TRUNC, _compile_date_trunc_duckdb),
        (ExpressionType.DATE_FORMAT, _compile_date_format_duckdb),
        (ExpressionType.CONDITIONAL, _compile_conditional),
    ]
    for expr_type, handler in common:
        _register_handler('duckdb', expr_type, handler)
    # spark_sql 与 hive 共用实现——通过方言别名映射
    for expr_type, handler in common:
        _register_handler('spark_sql', expr_type, handler)


def _register_hive_handlers() -> None:
    """注册 Hive 特有的表达式编译函数（仅覆盖与 DuckDB 不同的类型）"""
    _register_handler('hive', ExpressionType.DATE_DIFF, _compile_date_diff_hive)
    _register_handler('hive', ExpressionType.DATE_TRUNC, _compile_date_trunc_hive)
    _register_handler('hive', ExpressionType.DATE_FORMAT, _compile_date_format_hive)


def _register_postgresql_handlers() -> None:
    """注册 PostgreSQL 特有的表达式编译函数"""
    _register_handler('postgresql', ExpressionType.DATE_DIFF, _compile_date_diff_postgresql)
    _register_handler('postgresql', ExpressionType.CAST, _compile_cast_postgresql)
    _register_handler('postgresql', ExpressionType.CONCAT, _compile_concat_postgresql)
    _register_handler('postgresql', ExpressionType.DATE_FORMAT, _compile_date_format_postgresql)


# 自动注册
_register_default_handlers()
_register_hive_handlers()
_register_postgresql_handlers()


# ═══════════════════════════════════════════════════════════
# 核心分发器
# ═══════════════════════════════════════════════════════════

def _compile_expression(
    expr: ExpressionRef,
    expr_map: dict[str, ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
    _depth: int = 0,
) -> str:
    """
    将单个 ExpressionRef IR 编译为方言特定的 SQL 表达式字符串

    分发顺序：
      1. 查找当前方言注册表 → 找到则使用
      2. 未找到 → fallback 到 'duckdb' 实现（DuckDB 覆盖最全）
      3. 仍未找到 → 抛出 SQLCompileError

    这是表达式编译器的核心分发函数。
    """
    if _depth > 10:
        raise SQLCompileError(f"表达式 '{expr.alias}' 嵌套深度超过上限（10 层）")

    # 步骤 1：查找当前方言
    handlers = _EXPRESSION_HANDLERS.get(dialect, {})
    handler = handlers.get(expr.expr_type)

    # 步骤 2：Fallback 到 DuckDB
    if handler is None and dialect != 'duckdb':
        duckdb_handlers = _EXPRESSION_HANDLERS.get('duckdb', {})
        handler = duckdb_handlers.get(expr.expr_type)

    if handler is None:
        raise SQLCompileError(
            f"不支持的表达式组合：expr_type='{expr.expr_type}'，dialect='{dialect}'"
        )

    return handler(expr, expr_map, dialect, table_ref_map, _depth)


# ═══════════════════════════════════════════════════════════
# 批量编译入口（两遍编译）
# ═══════════════════════════════════════════════════════════

def compile_expressions(
    expression_refs: list[ExpressionRef],
    dialect: str,
    table_ref_map: dict[str, str],
) -> list[str]:
    """
    编译 SQLPlan 中的所有 ExpressionRef

    两遍编译策略：
      Pass 1（构建索引）：
        遍历 expression_refs，构建 expr_map = {expr.alias → expr}
        校验：每个 expression_refs 必须有非空 alias
        校验：无重复 alias

      Pass 2（编译）：
        逐个调用 _compile_expression 编译
        当遇到 EXPR_REF 操作数时，从 expr_map 中查找并递归编译展开

    返回：与 expression_refs 一一对应的 SQL 表达式字符串列表
      示例：["DATEDIFF('day', t1.start_date, t1.end_date)", ...]

    调用方负责将每个 SQL 片段与对应的 ExpressionRef.alias 配对使用。
    """
    if not expression_refs:
        return []

    # ── Pass 1：构建别名索引 ──
    expr_map: dict[str, ExpressionRef] = {}
    for expr in expression_refs:
        if not expr.alias:
            raise SQLCompileError(
                f"表达式 '{expr.expr_type}' 缺少 alias——所有 expression_refs 必须有别名"
            )
        if expr.alias in expr_map:
            raise SQLCompileError(
                f"重复的表达式别名 '{expr.alias}'——每个 expression_ref 的 alias 必须唯一"
            )
        expr_map[expr.alias] = expr

    # ── Pass 2：编译每个表达式 ──
    results: list[str] = []
    for expr in expression_refs:
        sql_segment = _compile_expression(expr, expr_map, dialect, table_ref_map)
        results.append(sql_segment)

    return results
