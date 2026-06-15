"""
Layer 3 IR 定义——SQLPlan 相关的所有数据结构和枚举类型

此模块仅包含纯 IR 定义（dataclass + Enum），不包含任何规划逻辑。
规划逻辑位于 layer3_plan.py。

IR 类型：
  - SQLPlan / PipelinePlan（顶层计划 IR）
  - JoinGraph / JoinNode / JoinCondition（表结构）
  - ColumnBinding / DimensionColumnBinding / FilterBinding（列绑定）
  - ExpressionRef / ExpressionOperand / ExpressionConfig（表达式）
  - WindowFunctionDef / WindowFunctionArg（窗口函数）
  - CTEDefinition（CTE）
  - ColumnRef / LiteralValue / OrderByEntry（通用结构）
  - ExecutionConstraints（执行约束）
  - 所有枚举类型（ExpressionType / WindowFunctionName / FilterType 等）

异常：
  - SQLCompileError——SQL 编译错误（跨层共享）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any


# ═══════════════════════════════════════════════════════════
# 共享异常
# ═══════════════════════════════════════════════════════════

class SQLCompileError(Exception):
    """SQL 编译错误——表示 SQLPlan 中缺少编译所需的必要信息"""
    pass


# ═══════════════════════════════════════════════════════════
# SQLPlan 数据结构
# ═══════════════════════════════════════════════════════════

@dataclass
class JoinCondition:
    """JOIN 条件"""
    left: str   # 左表.列名（使用别名）
    right: str  # 右表.列名（使用别名）


@dataclass
class JoinNode:
    """JoinGraph 中的一个 JOIN 节点"""
    table: str          # 完全限定表名
    alias: str          # SQL 别名
    type: str           # LEFT JOIN | INNER JOIN
    condition: JoinCondition
    constraint_ref: str  # 约束来源如 "sql_safety_policy.yml#join_whitelist"


@dataclass
class JoinGraph:
    """表结构关系图"""
    primary: JoinNode  # 主表（使用 JoinNode 类型以保持一致性）
    joins: list[JoinNode] = field(default_factory=list)


@dataclass
class ColumnBinding:
    """
    字段绑定——将指标映射到物理列

    column_ref 格式：schema.table.column（如 gold.dws_daily_trip_summary.trip_count）。
    编译器在 Pass 2 通过别名映射表将 schema.table 前缀替换为 SQL 别名。
    """
    metric_name: str
    column_ref: str       # 列引用——格式 schema.table.column 或 table_ref.column_name
    alias: str
    unit: str
    domain: str


@dataclass
class DimensionColumnBinding:
    """
    维度列绑定

    column_ref 格式同 ColumnBinding——编译器统一处理。
    """
    dim_name: str
    column_ref: str
    alias: str


@dataclass
class FilterBinding:
    """过滤条件绑定——所有列引用使用 column_ref（与 Schema 契约一致）"""
    filter_type: FilterType  # 过滤类型枚举
    column_ref: str          # 列引用——格式 schema.table.column 或 table_ref.column_name
    operator: str            # BETWEEN | IN | = | >= | <= | > | < | !=
    value: Any               # 过滤值


# ═══════════════════════════════════════════════════════════
# Phase 2：枚举类型——编译器类型安全的基石
# ═══════════════════════════════════════════════════════════

class ExpressionType(str, Enum):
    """表达式类型枚举——决定编译时使用哪个模板"""
    DATE_DIFF = "date_diff"
    DATE_TRUNC = "date_trunc"
    DATE_FORMAT = "date_format"
    ARITHMETIC = "arithmetic"
    CONDITIONAL = "conditional"
    COALESCE = "coalesce"
    CAST = "cast"
    CONCAT = "concat"
    LITERAL = "literal"
    COLUMN_REF = "column_ref"


class WindowFunctionName(str, Enum):
    """窗口函数名枚举——编译器可据此校验参数数量和类型"""
    LEAD = "lead"
    LAG = "lag"
    ROW_NUMBER = "row_number"
    RANK = "rank"
    DENSE_RANK = "dense_rank"
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    FIRST_VALUE = "first_value"
    LAST_VALUE = "last_value"


class LiteralType(str, Enum):
    """字面量类型枚举"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"


class OutputType(str, Enum):
    """表达式输出类型枚举——用于下游类型校验"""
    STRING = "STRING"
    INTEGER = "INTEGER"
    DOUBLE = "DOUBLE"
    DECIMAL = "DECIMAL"
    DATE = "DATE"
    TIMESTAMP = "TIMESTAMP"
    BOOLEAN = "BOOLEAN"


class OperandKind(str, Enum):
    """表达式操作数种类——区分列引用、字面量、嵌套表达式"""
    COLUMN_REF = "column_ref"
    LITERAL = "literal"
    EXPR_REF = "expr_ref"


class FunctionArgKind(str, Enum):
    """窗口函数参数种类"""
    COLUMN = "column"
    LITERAL = "literal"


class FrameType(str, Enum):
    """窗口帧类型"""
    RANGE = "RANGE"
    ROWS = "ROWS"
    GROUPS = "GROUPS"


class FilterType(str, Enum):
    """过滤条件类型枚举"""
    DATE_RANGE = "date_range"
    IN_LIST = "in_list"
    EQUALS = "equals"
    COMPARISON = "comparison"
    NOT_EQUALS = "not_equals"
    COLUMN_COMPARISON = "column_comparison"


# ═══════════════════════════════════════════════════════════
# Phase 2：统一的类型定义（列引用、字面量、排序项、表达式配置）
# ═══════════════════════════════════════════════════════════

@dataclass
class OrderByEntry:
    """
    ORDER BY 子句中的一个排序项——统一用于 SQLPlan.order_by 和
    WindowFunctionDef.order_by。使用 ColumnRef 确保多表 JOIN 时
    编译器能解析列归属。

    示例：
      OrderByEntry(column_ref=ColumnRef("primary", "crash_date"), direction="DESC")
        → 编译器生成：t1.crash_date DESC
    """
    column_ref: ColumnRef
    direction: str = "ASC"  # ASC | DESC


@dataclass
class ExpressionConfig:
    """
    表达式编译配置——类型化的可选字段集合，替换原来的 dict[str, Any]

    编译器根据 ExpressionRef.expr_type 知道哪些字段是必需的：
      - date_diff:     unit 必需
      - date_trunc:    unit 必需
      - date_format:   format 必需
      - arithmetic:    op 必需
      - cast:          target_type 必需
      - conditional:   when_clauses 必需，else_value 可选
      - coalesce:      无配置
      - concat:        无配置
      - literal:       无配置（值在 operands[0] 中）
    """
    # date_diff / date_trunc 的时间单位
    unit: Optional[str] = None
    # arithmetic 的运算符：+ - * /
    op: Optional[str] = None
    # cast 的目标类型：string integer double decimal date timestamp boolean
    target_type: Optional[str] = None
    # conditional 的 WHEN 子句列表
    when_clauses: Optional[list[dict[str, Any]]] = None
    # conditional 的 ELSE 值
    else_value: Any = None
    # date_format 的格式字符串（方言无关中间格式）
    format: Optional[str] = None


@dataclass
class ColumnRef:
    """
    统一的列引用结构——所有需要引用列的地方都使用此结构

    格式：table_ref 是 JoinGraph 中的引用标识符（如 'primary' 或 joins[].ref），
    column_name 是裸列名。编译器在别名分配阶段将 table_ref 映射为 SQL 别名。

    示例：
      ColumnRef(table_ref="primary", column_name="trip_count")
        → 编译器映射 → t1.trip_count
    """
    table_ref: str       # JoinGraph 中的引用标识符（'primary' 或 joins[].ref）
    column_name: str     # 裸列名——不含表名前缀


@dataclass
class LiteralValue:
    """
    字面量值——用于表达式和窗口函数的非列参数

    示例：
      LiteralValue(literal_type="integer", value=1)
      LiteralValue(literal_type="string", value="N/A")
    """
    literal_type: LiteralType  # 字面量类型枚举
    value: Any


@dataclass
class WindowFunctionArg:
    """
    窗口函数参数——可以是列引用或字面量

    示例：
      WindowFunctionArg(kind="column", column_ref=ColumnRef("primary", "crash_date"))
      WindowFunctionArg(kind="literal", literal=LiteralValue("integer", 1))
    """
    kind: FunctionArgKind           # 参数类型：列引用或字面量
    column_ref: Optional[ColumnRef] = None
    literal: Optional[LiteralValue] = None


# ═══════════════════════════════════════════════════════════
# Phase 2：SQLPlan 扩展字段的结构定义
# ═══════════════════════════════════════════════════════════

@dataclass
class WindowFunctionDef:
    """
    窗口函数 IR 定义——属于 SQLPlan（语句级）

    编译器根据 target_dialect 将此 IR 翻译为：
      LEAD(t1.crash_date, 1) OVER (PARTITION BY t1.zone_name ORDER BY t1.crash_date)

    所有列引用使用 ColumnRef，字面量使用 LiteralValue。
    """
    func_name: WindowFunctionName               # 窗口函数名枚举——编译器可校验参数数量
    args: list[WindowFunctionArg] = field(default_factory=list)
    partition_by: list[ColumnRef] = field(default_factory=list)
    order_by: list[OrderByEntry] = field(default_factory=list)
    # 使用 OrderByEntry(column_ref=ColumnRef(...), direction="ASC")——
    # ColumnRef 保证多表 JOIN 时编译器能解析列归属
    alias: str = ""                            # 输出列别名
    frame_start: str = ""                      # 如 "UNBOUNDED PRECEDING"
    frame_end: str = ""                        # 如 "CURRENT ROW"
    frame_type: FrameType = FrameType.RANGE    # 窗口帧类型枚举


@dataclass
class ExpressionOperand:
    """
    表达式操作数——ColumnRef、LiteralValue 或嵌套 ExpressionRef 之一
    """
    kind: OperandKind                # 操作数类型枚举
    column_ref: Optional[ColumnRef] = None
    literal: Optional[LiteralValue] = None
    expr_alias: str = ""  # 当 kind=OperandKind.EXPR_REF 时，引用另一个 ExpressionRef 的 alias


@dataclass
class ExpressionRef:
    """
    表达式 IR 定义——属于 SQLPlan（列级）

    编译器根据 target_dialect 将此结构化 IR 翻译为：
      DuckDB:    DATEDIFF('day', t1.start, t1.end)
      Hive:      DATEDIFF(t1.start, t1.end)
      PostgreSQL: (t1.end - t1.start)
    """
    expr_type: ExpressionType          # 表达式类型枚举——编译器据此选择模板
    operands: list[ExpressionOperand] = field(default_factory=list)
    config: ExpressionConfig = field(default_factory=ExpressionConfig)
    # 类型化的编译配置——编译器不用"猜" config 里有什么 key
    alias: str = ""                    # 输出列别名
    output_type: OutputType = OutputType.STRING  # 表达式输出类型——下游校验用


@dataclass
class CTEDefinition:
    """
    单个 CTE 的 IR 定义——属于 SQLPlan（语句级 WITH 子句）

    CTE 的生命周期仅限于一条 SQL 语句。一个 SQLPlan 可以有 0-N 个 CTE。
    CTE 之间可以通过 cte_name 相互引用（同一语句内）。

    编译器生成：
      WITH cte1 AS (SELECT ...), cte2 AS (SELECT ... FROM cte1 ...)
      SELECT ... FROM cte2 ...

    注意：sql_plan 是嵌套的 SQLPlan——CTE 体本身是一条完整的 SELECT。
    """
    cte_name: str                      # CTE 名称——通过 $cte.xxx 引用
    # 🚨 嵌套 SQLPlan——引用同一模块中的类，from __future__ import annotations 处理
    sql_plan: Optional[SQLPlan] = None
    # ── 递归深度约束（Phase 2 硬限制）──
    # CTE 体内不允许嵌套 CTE。即：若此 CTEDefinition 位于 SQLPlan.cte_definitions 中，
    # 则 sql_plan.cte_definitions 必须为空列表（或 sql_plan 为 None）。
    # 嵌套 CTE（WITH a AS (WITH b AS (...) SELECT ...)）推迟到 Phase 3+。
    # 此约束由 Layer 5 validate_pipeline_cte_recursion() 强制执行。


@dataclass
class ExecutionConstraints:
    """执行约束（从 TianShu contracts 注入）"""
    read_only: bool = True
    query_timeout_seconds: int = 30
    max_result_rows: int = 100000
    allowed_tables: list[str] = field(default_factory=list)
    requires_date_dim: bool = False


@dataclass
class SQLPlan:
    """
    SQLPlan —— Layer 3 的输出，Layer 4（SQL Compiler）的唯一输入

    所有字段值来自 ColumnBindingTable 或 Contracts 的确定性查询。
    LLM 不参与此对象的任何构造。
    """
    plan_id: str
    plan_name: str
    source_layer: str  # "g3" | "g2"
    domain: str
    target_dialect: str = "duckdb"  # duckdb | hive | spark_sql | postgresql——从 PipelinePlan 继承

    # 表结构
    join_graph: Optional[JoinGraph] = None

    # 字段绑定
    column_bindings: list[ColumnBinding] = field(default_factory=list)
    dimension_bindings: list[DimensionColumnBinding] = field(default_factory=list)
    filter_bindings: list[FilterBinding] = field(default_factory=list)

    # 聚合规格
    group_by: list[str] = field(default_factory=list)
    order_by: list[dict[str, str]] = field(default_factory=list)
    # 格式：[{column: "schema.table.col", direction: "ASC"}]
    # 注意：此字段仍使用裸字典——与 WindowFunctionDef.order_by 不同。
    # 原因是构造代码目前生成 schema.table.column 格式的值而非 IR 级引用。
    # 待列引用全面迁移到 ColumnRef 后同步修复。
    limit: Optional[int] = None

    # ── Phase 2 扩展：窗口函数（SELECT 子句级）──
    window_functions: list[WindowFunctionDef] = field(default_factory=list)

    # ── Phase 2 扩展：表达式（列级——编译后出现在 SELECT 列表）──
    expression_refs: list[ExpressionRef] = field(default_factory=list)

    # ── Phase 2 扩展：CTE 定义（WITH 子句，语句级）──
    cte_definitions: list[CTEDefinition] = field(default_factory=list)

    # 执行约束
    execution_constraints: Optional[ExecutionConstraints] = None

    # 输出
    output_format: str = "parquet"
    output_path_template: str = ""

    # 诊断
    warnings: list[str] = field(default_factory=list)
    is_valid: bool = True
    block_reason: str = ""
