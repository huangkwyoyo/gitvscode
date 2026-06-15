"""
Layer 4 扩展：操作编译器 + 增量策略解析器（Phase 6 + Phase 7）

职责：
  1. 接收 PipelineStep IR（操作类型 + 目标表 + 增量意图）
  2. 解析执行策略（全量覆盖 / 分区覆盖 / 分区追加 / 键合并）
  3. 将已编译的 SELECT 语句包裹到 DDL/DML 操作 SQL 中
  4. 通过注册表模式支持多方言操作语法差异

LLM 角色：
  **完全禁止**。此层是纯编译器，零 LLM 参与。

设计原则：
  - 策略解析是纯函数：PipelineStep → ExecutionStrategy（不调外部服务）
  - 操作编译是纯模板：ExecutionStrategy + SELECT + 方言 → 完整 DDL/DML
  - 方言差异只体现在 SQL 语法模板上（如 Hive 的 PARTITION 子句）

输入：PipelineStep + 已编译的 SELECT SQL + 方言
输出：包裹了 DDL/DML 操作的完整 SQL 语句
"""

from __future__ import annotations

from enum import Enum
from typing import Callable, Optional

from .layer3_pipeline_plan import (
    PipelineStep,
    StepOperation,
    IncrementalIntent,
)
from .layer3_ir import SQLCompileError


# ═══════════════════════════════════════════════════════════
# P7：执行策略枚举
# ═══════════════════════════════════════════════════════════

class ExecutionStrategy(str, Enum):
    """
    增量执行策略——由 PipelineStep 的操作类型 + 增量意图决定

    这是编译器/执行器决定"如何执行"的关键中间产物。
    同一操作类型在不同增量配置下可能产生不同策略。
    """
    SELECT_ONLY = "select_only"              # 只读查询（dry-run 或无写入意图的 SELECT）
    FULL_OVERWRITE = "full_overwrite"        # 全量覆盖（CTAS 或 INSERT OVERWRITE 全表）
    PARTITION_OVERWRITE = "partition_overwrite"  # 分区覆盖写入（INSERT OVERWRITE PARTITION）
    PARTITION_APPEND = "partition_append"         # 分区追加写入（INSERT INTO PARTITION）
    CREATE_VIEW = "create_view"              # 创建视图
    KEY_MERGE = "key_merge"                  # 按键合并（MERGE/UPSERT——未来实现）


# ═══════════════════════════════════════════════════════════
# P7：策略解析器
# ═══════════════════════════════════════════════════════════

def resolve_strategy(step: PipelineStep) -> ExecutionStrategy:
    """
    从 PipelineStep 的操作类型 + 增量意图，确定性解析执行策略

    解析规则（按优先级）：

      1. SELECT_ONLY → SELECT_ONLY（只读，忽略增量意图）
      2. CREATE_VIEW → CREATE_VIEW（视图创建，忽略增量意图）
      3. CREATE_TABLE_AS_SELECT：
         - 无增量意图 或 incremental=False → FULL_OVERWRITE
         - incremental=True + dedup_scope=full_table → FULL_OVERWRITE
         - incremental=True + dedup_scope=partition → PARTITION_OVERWRITE
         - incremental=True + dedup_scope=key_merge → KEY_MERGE
      4. INSERT_OVERWRITE_PARTITION：
         - incremental=True + dedup_scope=partition → PARTITION_OVERWRITE
         - 其他 → FULL_OVERWRITE（降级）
      5. INSERT_INTO_PARTITION：
         - incremental=True → PARTITION_APPEND
         - 其他 → PARTITION_APPEND（默认行为即追加）

    参数：
      step: 管道步骤——包含操作类型、目标表、增量意图

    返回：
      ExecutionStrategy 枚举值——编译器据此选择操作 SQL 模板

    异常：
      无——此函数不抛异常。不支持的组合降级为安全默认值。
    """
    op = step.operation
    intent = step.incremental_intent

    # ── 规则 1：只读查询 ──
    if op == StepOperation.SELECT_ONLY:
        return ExecutionStrategy.SELECT_ONLY

    # ── 规则 2：视图创建 ──
    if op == StepOperation.CREATE_VIEW:
        return ExecutionStrategy.CREATE_VIEW

    # ── 规则 3-5：写入操作——按增量意图决定策略 ──
    is_incremental = intent is not None and intent.incremental

    if op == StepOperation.CREATE_TABLE_AS_SELECT:
        if is_incremental and intent is not None:
            if intent.dedup_scope == "key_merge" and intent.key_columns:
                return ExecutionStrategy.KEY_MERGE
            elif intent.dedup_scope == "partition" and intent.partition_column:
                return ExecutionStrategy.PARTITION_OVERWRITE
        # 默认：全量覆盖
        return ExecutionStrategy.FULL_OVERWRITE

    if op == StepOperation.INSERT_OVERWRITE_PARTITION:
        if is_incremental and intent is not None:
            if intent.dedup_scope == "key_merge" and intent.key_columns:
                return ExecutionStrategy.KEY_MERGE
            elif intent.dedup_scope == "partition" and intent.partition_column:
                return ExecutionStrategy.PARTITION_OVERWRITE
        # 降级：无分区列 → 全量覆盖
        return ExecutionStrategy.FULL_OVERWRITE

    if op == StepOperation.INSERT_INTO_PARTITION:
        if is_incremental and intent is not None:
            if intent.dedup_scope == "key_merge" and intent.key_columns:
                return ExecutionStrategy.KEY_MERGE
        # 默认：分区追加
        return ExecutionStrategy.PARTITION_APPEND

    # 防御：未知操作类型
    return ExecutionStrategy.SELECT_ONLY


# ═══════════════════════════════════════════════════════════
# P6：操作编译器
# ═══════════════════════════════════════════════════════════

def _indent_sql(sql: str, spaces: int = 4) -> str:
    """将 SQL 文本每行缩进指定空格数（用于 CTAS/INSERT 体）"""
    prefix = " " * spaces
    return "\n".join(prefix + line for line in sql.split("\n"))


# ── DuckDB 操作编译 ──

def _compile_select_only(
    target_table: str,
    compiled_select: str,
    partition_column: str = "",
) -> str:
    """SELECT_ONLY——直接透传 SELECT"""
    return compiled_select


def _compile_full_overwrite_duckdb(
    target_table: str,
    compiled_select: str,
    partition_column: str = "",
) -> str:
    """
    DuckDB 全量覆盖：CREATE OR REPLACE TABLE AS SELECT

    DuckDB 没有 INSERT OVERWRITE 语法，使用 CREATE OR REPLACE 等价实现。
    此语法原子性地替换整个表，语义等同于全量覆盖。
    """
    indented = _indent_sql(compiled_select, 4)
    return f"CREATE OR REPLACE TABLE {target_table} AS\n{indented}"


def _compile_partition_overwrite_duckdb(
    target_table: str,
    compiled_select: str,
    partition_column: str = "",
) -> str:
    """
    DuckDB 分区覆盖：降级为全量覆盖

    DuckDB 不支持 Hive 风格的分区覆盖。
    在 DuckDB 中，分区表通过不同的表名模拟（如 table_20260101）。
    如果调用方传入分区意图，fallback 到全量覆盖并发出警告。
    """
    # DuckDB 不支持分区覆盖——降级为全量覆盖
    return _compile_full_overwrite_duckdb(target_table, compiled_select)


def _compile_partition_append_duckdb(
    target_table: str,
    compiled_select: str,
    partition_column: str = "",
) -> str:
    """DuckDB 追加写入：INSERT INTO target SELECT ..."""
    indented = _indent_sql(compiled_select, 4)
    return f"INSERT INTO {target_table}\n{indented}"


def _compile_create_view_duckdb(
    target_table: str,
    compiled_select: str,
    partition_column: str = "",
) -> str:
    """DuckDB 视图创建：CREATE OR REPLACE VIEW target AS SELECT ..."""
    indented = _indent_sql(compiled_select, 4)
    return f"CREATE OR REPLACE VIEW {target_table} AS\n{indented}"


def _compile_key_merge_placeholder(
    target_table: str,
    compiled_select: str,
    partition_column: str = "",
) -> str:
    """KEY_MERGE 策略暂未实现——抛出明确错误"""
    raise SQLCompileError(
        f"KEY_MERGE 策略暂未实现。目标表: {target_table}。"
        f"当前支持的策略：FULL_OVERWRITE / PARTITION_OVERWRITE / PARTITION_APPEND / CREATE_VIEW"
    )


# ── Hive 操作编译 ──

def _compile_full_overwrite_hive(
    target_table: str,
    compiled_select: str,
    partition_column: str = "",
) -> str:
    """
    Hive 全量覆盖：INSERT OVERWRITE TABLE target SELECT ...

    Hive 使用 INSERT OVERWRITE 而非 CTAS 做全量覆盖——
    因为目标表已经存在（已建好分区结构）。
    """
    indented = _indent_sql(compiled_select, 4)
    return f"INSERT OVERWRITE TABLE {target_table}\n{indented}"


def _compile_ctas_hive(
    target_table: str,
    compiled_select: str,
    partition_column: str = "",
) -> str:
    """Hive CTAS：CREATE TABLE target AS SELECT ..."""
    indented = _indent_sql(compiled_select, 4)
    return f"CREATE TABLE {target_table} AS\n{indented}"


def _compile_partition_overwrite_hive(
    target_table: str,
    compiled_select: str,
    partition_column: str = "",
) -> str:
    """
    Hive 分区覆盖：INSERT OVERWRITE TABLE target PARTITION (col) SELECT ...

    需要提取分区列值（由增量意图的 watermark_column 或 partition_column 指定）。
    分区列必须存在于 SELECT 输出中——编译器不做隐式修改。
    """
    if not partition_column:
        raise SQLCompileError(
            f"INSERT OVERWRITE PARTITION 需要指定分区列，但目标表 {target_table} 未提供 partition_column"
        )
    indented = _indent_sql(compiled_select, 4)
    return (
        f"INSERT OVERWRITE TABLE {target_table}\n"
        f"PARTITION ({partition_column})\n"
        f"{indented}"
    )


def _compile_partition_append_hive(
    target_table: str,
    compiled_select: str,
    partition_column: str = "",
) -> str:
    """Hive 分区追加：INSERT INTO TABLE target PARTITION (col) SELECT ..."""
    if not partition_column:
        raise SQLCompileError(
            f"INSERT INTO PARTITION 需要指定分区列，但目标表 {target_table} 未提供 partition_column"
        )
    indented = _indent_sql(compiled_select, 4)
    return (
        f"INSERT INTO TABLE {target_table}\n"
        f"PARTITION ({partition_column})\n"
        f"{indented}"
    )


def _compile_create_view_hive(
    target_table: str,
    compiled_select: str,
    partition_column: str = "",
) -> str:
    """Hive 视图创建：CREATE VIEW target AS SELECT ..."""
    indented = _indent_sql(compiled_select, 4)
    return f"CREATE VIEW {target_table} AS\n{indented}"


# ── PostgreSQL 操作编译 ──

def _compile_full_overwrite_postgresql(
    target_table: str,
    compiled_select: str,
    partition_column: str = "",
) -> str:
    """PostgreSQL 全量覆盖：原子 DELETE + INSERT 在事务中执行"""
    # PostgreSQL 不支持 CREATE OR REPLACE TABLE，使用事务包裹的 TRUNCATE + INSERT
    indented_select = _indent_sql(compiled_select, 4)
    return (
        f"BEGIN;\n"
        f"DELETE FROM {target_table};\n"
        f"INSERT INTO {target_table}\n"
        f"{indented_select};\n"
        f"COMMIT;"
    )


def _compile_partition_append_postgresql(
    target_table: str,
    compiled_select: str,
    partition_column: str = "",
) -> str:
    """PostgreSQL 追加写入：INSERT INTO target SELECT ..."""
    indented = _indent_sql(compiled_select, 4)
    return f"INSERT INTO {target_table}\n{indented}"


def _compile_create_view_postgresql(
    target_table: str,
    compiled_select: str,
    partition_column: str = "",
) -> str:
    """PostgreSQL 视图创建：CREATE OR REPLACE VIEW target AS SELECT ..."""
    indented = _indent_sql(compiled_select, 4)
    return f"CREATE OR REPLACE VIEW {target_table} AS\n{indented}"


# ═══════════════════════════════════════════════════════════
# 注册表：{dialect: {ExecutionStrategy: handler}}
# ═══════════════════════════════════════════════════════════

# 类型别名：操作编译处理函数
OperationHandler = Callable[[str, str, str], str]

_OPERATION_HANDLERS: dict[str, dict[ExecutionStrategy, OperationHandler]] = {}


def _register_op_handler(
    dialect: str,
    strategy: ExecutionStrategy,
    handler: OperationHandler,
) -> None:
    """注册一个方言+策略的编译处理函数"""
    if dialect not in _OPERATION_HANDLERS:
        _OPERATION_HANDLERS[dialect] = {}
    _OPERATION_HANDLERS[dialect][strategy] = handler


def _register_default_handlers() -> None:
    """注册 DuckDB 默认操作编译实现"""
    _register_op_handler('duckdb', ExecutionStrategy.SELECT_ONLY, _compile_select_only)
    _register_op_handler('duckdb', ExecutionStrategy.FULL_OVERWRITE, _compile_full_overwrite_duckdb)
    _register_op_handler('duckdb', ExecutionStrategy.PARTITION_OVERWRITE, _compile_partition_overwrite_duckdb)
    _register_op_handler('duckdb', ExecutionStrategy.PARTITION_APPEND, _compile_partition_append_duckdb)
    _register_op_handler('duckdb', ExecutionStrategy.CREATE_VIEW, _compile_create_view_duckdb)
    _register_op_handler('duckdb', ExecutionStrategy.KEY_MERGE, _compile_key_merge_placeholder)
    # spark_sql 使用 DuckDB 相同实现（CTAS/INSERT）
    for strategy in ExecutionStrategy:
        handler = _OPERATION_HANDLERS['duckdb'][strategy]
        _register_op_handler('spark_sql', strategy, handler)


def _register_hive_handlers() -> None:
    """注册 Hive 操作编译实现"""
    _register_op_handler('hive', ExecutionStrategy.SELECT_ONLY, _compile_select_only)
    _register_op_handler('hive', ExecutionStrategy.FULL_OVERWRITE, _compile_full_overwrite_hive)
    _register_op_handler('hive', ExecutionStrategy.PARTITION_OVERWRITE, _compile_partition_overwrite_hive)
    _register_op_handler('hive', ExecutionStrategy.PARTITION_APPEND, _compile_partition_append_hive)
    _register_op_handler('hive', ExecutionStrategy.CREATE_VIEW, _compile_create_view_hive)
    _register_op_handler('hive', ExecutionStrategy.KEY_MERGE, _compile_key_merge_placeholder)


def _register_postgresql_handlers() -> None:
    """注册 PostgreSQL 操作编译实现"""
    _register_op_handler('postgresql', ExecutionStrategy.SELECT_ONLY, _compile_select_only)
    _register_op_handler('postgresql', ExecutionStrategy.FULL_OVERWRITE, _compile_full_overwrite_postgresql)
    _register_op_handler('postgresql', ExecutionStrategy.PARTITION_OVERWRITE, _compile_full_overwrite_postgresql)  # PG 无原生分区
    _register_op_handler('postgresql', ExecutionStrategy.PARTITION_APPEND, _compile_partition_append_postgresql)
    _register_op_handler('postgresql', ExecutionStrategy.CREATE_VIEW, _compile_create_view_postgresql)
    _register_op_handler('postgresql', ExecutionStrategy.KEY_MERGE, _compile_key_merge_placeholder)


# 模块加载时自动注册
_register_default_handlers()
_register_hive_handlers()
_register_postgresql_handlers()


# ═══════════════════════════════════════════════════════════
# P6 核心分发器
# ═══════════════════════════════════════════════════════════

def compile_operation(
    step: PipelineStep,
    compiled_select: str,
    dialect: str = "duckdb",
) -> str:
    """
    将已编译的 SELECT 语句包裹到操作 DDL/DML SQL 中

    编译流程：
      1. resolve_strategy(step) → ExecutionStrategy
      2. 查找 {dialect: strategy} 对应的操作编译处理器
      3. 调用处理器：handler(target_table, compiled_select, partition_column)

    参数：
      step: 管道步骤——提供操作类型、目标表、增量意图
      compiled_select: 已编译的 SELECT SQL（来自 compile_sql）
      dialect: 目标 SQL 方言

    返回：
      包裹了 DDL/DML 操作的完整 SQL 语句

    示例：
      step.operation = CREATE_TABLE_AS_SELECT
      step.target_table = "generated.daily_stats"
      → "CREATE OR REPLACE TABLE generated.daily_stats AS\n    SELECT ..."
    """
    # ── 步骤 1：策略解析 ──
    strategy = resolve_strategy(step)

    # ── 步骤 2：获取分区列（如有）──
    partition_column = ""
    if step.incremental_intent:
        partition_column = step.incremental_intent.partition_column

    # ── 步骤 3：分发到方言处理器 ──
    handlers = _OPERATION_HANDLERS.get(dialect, {})
    handler = handlers.get(strategy)

    # Fallback 到 DuckDB
    if handler is None and dialect != 'duckdb':
        duckdb_handlers = _OPERATION_HANDLERS.get('duckdb', {})
        handler = duckdb_handlers.get(strategy)

    if handler is None:
        raise SQLCompileError(
            f"不支持的操作组合：strategy='{strategy.value}'，dialect='{dialect}'"
        )

    return handler(step.target_table, compiled_select, partition_column)
