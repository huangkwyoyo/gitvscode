"""
Layer 3：SQLPlan 规划层

职责：
  1. 接收 Layer 2 的 Intent 对象
  2. 通过查 ColumnBindingTable 确定每个指标的物理列
  3. 决定数据源层级（G3 优先 → G2 降级）
  4. 构造 JoinGraph（单表或多表）
  5. 注入执行约束
  6. 输出完整 SQLPlan 对象

===== LLM 硬边界 =====

此层及以下所有层（L3-L8）**完全禁止 LLM 参与**。
LLM 输出的 Intent 对象不包含任何表名、列名、JOIN 条件。
所有物理层决策（表选择、JOIN 构造、列绑定）由本层纯代码完成。

安全保证：即使 LLM 产生幻觉（输出错误的指标名），
最坏结果也是本层查 ColumnBindingTable 失败 → BLOCKED（拒绝执行），
不会生成错误的 SQL。因为：
  - 表名来自 ColumnBindingTable（代码查表，非 LLM 选择）
  - JOIN 路径来自 JOIN_WHITELIST（硬编码白名单，非 LLM 构造）
  - 列绑定由 get_binding_by_metric_name() 纯函数完成

LLM 角色：
  **完全禁止**。此层是纯确定性代码。
  所有决策通过查表和规则完成，不经过任何 LLM 调用。

输入：Intent 对象
输出：SQLPlan 对象
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any
from datetime import datetime

from .column_binding import (
    get_binding_by_metric_name,
    get_dimension_binding,
    get_join_path,
    BindingEntry,
    DimensionBinding,
    JoinPath,
)
from .layer2_intent import Intent, ResolvedMetric, ResolvedDimension


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


# ═══════════════════════════════════════════════════════════
# 规划器核心逻辑
# ═══════════════════════════════════════════════════════════

def _generate_plan_id() -> str:
    """生成唯一计划 ID"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 简单序号（生产环境可用更健壮的 ID 生成）
    import random
    seq = random.randint(1000, 9999)
    return f"plan_{timestamp}_{seq}"


def _resolve_layer(metrics: list[ResolvedMetric]) -> tuple[str, list[str]]:
    """
    决定数据源层级：G3 优先，G2 降级

    返回：(layer, warnings)
    - 所有指标都有 G3 绑定 → "g3"
    - 任一指标无 G3 → 降级到 "g2"（前提是 G2 表达式已注册）
    - G2 也无表达式 → 标记为无效
    """
    warnings: list[str] = []
    all_g3 = True
    any_missing_g2 = False

    for metric in metrics:
        binding = get_binding_by_metric_name(metric.registered_name)
        if binding is None:
            continue
        if not binding.g3_available or binding.g3 is None:
            all_g3 = False
            if binding.g2_expression is None:
                any_missing_g2 = True
                warnings.append(
                    f"指标 '{metric.registered_name}' 无 G3 汇总表且无 G2 表达式，无法生成 SQL"
                )

    if all_g3:
        return "g3", warnings
    elif not any_missing_g2:
        warnings.append("部分指标降级到 G2 fact 表（G3 不包含所需指标）")
        return "g2", warnings
    else:
        return "unavailable", warnings


def _determine_primary_table(metrics: list[ResolvedMetric], layer: str) -> tuple[Optional[str], list[str]]:
    """
    确定主表

    规则：
    - G3 层：各指标可能来自不同 G3 汇总表，需要从 BindingEntry.g3_table 获取
    - G2 层：类似逻辑，从 g2_table 获取
    - 如果所有指标在同一张表 → 单表查询
    - 如果指标分散在不同表 → 需要 JoinGraph（Phase 1 最多跨 2 张表）
    """
    # P0-2 修复：使用排序列表确保确定性顺序，避免 set 迭代不稳定
    tables: set[str] = set()
    for metric in metrics:
        binding = get_binding_by_metric_name(metric.registered_name)
        if binding is None:
            continue
        if layer == "g3":
            table = binding.g3_table
        else:
            table = binding.g2_table
        if table:
            tables.add(table)

    # 转换为排序列表（字母序）——保证每次运行结果一致
    sorted_tables = sorted(tables)

    warnings: list[str] = []
    if len(sorted_tables) == 0:
        return None, ["无法确定主表：所有指标的来源表均为空"]
    if len(sorted_tables) == 1:
        return sorted_tables[0], []
    elif len(sorted_tables) == 2:
        # 检查是否在 JOIN 白名单中（使用确定性顺序）
        join_path = get_join_path(sorted_tables[0], sorted_tables[1])
        if join_path:
            return sorted_tables[0], []  # 第一个表为主表（字典序，确定性）
        else:
            return None, [
                f"指标分布在多张表 ({', '.join(sorted_tables)})，但这些表之间没有白名单 JOIN 路径"
            ]
    else:
        return None, [f"指标分布在超过 2 张表 ({', '.join(sorted_tables)})，Phase 1 不支持"]


def _build_column_bindings(
    metrics: list[ResolvedMetric], layer: str, primary_table: str
) -> list[ColumnBinding]:
    """构建字段绑定表"""
    bindings: list[ColumnBinding] = []
    for metric in metrics:
        binding = get_binding_by_metric_name(metric.registered_name)
        if binding is None:
            continue

        if layer == "g3" and binding.g3:
            fq = binding.g3
        elif layer == "g2" and binding.g2_expression:
            # G2 场景：fully_qualified 是表达式而非列名
            fq = binding.g2_expression
        else:
            continue

        bindings.append(ColumnBinding(
            metric_name=metric.registered_name,
            column_ref=fq,
            alias=metric.user_name if metric.fuzzy_matched else binding.zh_name,
            unit=binding.unit,
            domain=binding.domain,
        ))

    return bindings


def _build_dimension_bindings(
    dimensions: list[ResolvedDimension], primary_table: str
) -> list[DimensionColumnBinding]:
    """构建维度字段绑定"""
    bindings: list[DimensionColumnBinding] = []
    for dim in dimensions:
        dim_binding = get_dimension_binding(dim.name)
        if dim_binding is None:
            continue
        # 从映射中找到主表对应的列名
        column = dim_binding.mappings.get(primary_table)
        if column is None:
            # 降级：使用默认来源
            column = dim_binding.default_source.split(".")[-1]
            fq = dim_binding.default_source
        else:
            fq = f"{primary_table}.{column}"

        bindings.append(DimensionColumnBinding(
            dim_name=dim.name,
            column_ref=fq,
            alias=dim.alias or dim.name,
        ))

    return bindings


def _is_date_key_column(column_name: str) -> bool:
    """
    检测列名是否为整数代理键（需要 JOIN dim_date 才能做日期过滤）

    注意（P0-1 修复后）：此函数仅作为辅助诊断工具保留。主安全策略已改为
    construct_sqlplan() 中的硬门禁——G2 层有日期过滤时强制 requires_dim_date=True，
    不再依赖此启发式判断。见 construct_sqlplan() 步骤 2.5。
    """
    return column_name.endswith("_key")


def _build_filter_bindings(
    filters: dict, primary_table: str, needs_dim_date: bool = False
) -> list[FilterBinding]:
    """
    构建过滤条件绑定

    安全策略：
      - G2 fact 表的日期列是整数代理键（如 pickup_date_key），不能直接与字符串日期比较
      - needs_dim_date=True → 使用 gold.dim_date.date 作为过滤列（硬编码安全路径）
      - needs_dim_date=False → 使用主表的日期列（G3 表直接含 DATE 类型日期列）

    🚨 P0-1 修复：needs_dim_date 现在由 construct_sqlplan() 的硬门禁设置——G2+日期过滤
    强制为 True，不再是启发式猜测。
    """
    bindings: list[FilterBinding] = []

    # 日期范围过滤
    if "date_range" in filters:
        date_range = filters["date_range"]
        if needs_dim_date:
            # G2 fact 表：日期列是整数 _key，必须通过 dim_date.date 过滤
            # 硬编码安全路径 gold.dim_date.date——不拼接用户输入
            bindings.append(FilterBinding(
                filter_type=FilterType.DATE_RANGE,
                column_ref="gold.dim_date.date",
                operator="BETWEEN",
                value=list(date_range),
            ))
        else:
            # G3 汇总表：日期列直接是 DATE 类型
            dim_binding = get_dimension_binding("date")
            date_column = "date"  # 默认
            if dim_binding and primary_table:
                date_column = dim_binding.mappings.get(primary_table, "date")

            bindings.append(FilterBinding(
                filter_type=FilterType.DATE_RANGE,
                column_ref=f"{primary_table}.{date_column}",
                operator="BETWEEN",
                value=list(date_range),
            ))

    # 维度值过滤
    if "dimension_filters" in filters:
        for dim_name, values in filters["dimension_filters"].items():
            dim_binding = get_dimension_binding(dim_name)
            column = dim_name  # 默认
            if dim_binding and primary_table:
                column = dim_binding.mappings.get(primary_table, dim_name)

            bindings.append(FilterBinding(
                filter_type=FilterType.IN_LIST,
                column_ref=f"{primary_table}.{column}",
                operator="IN",
                value=values,
            ))

    return bindings


def _build_join_graph(
    metrics: list[ResolvedMetric], layer: str, needs_dim_date: bool = False,
    primary_table_override: str | None = None
) -> tuple[Optional[JoinGraph], list[str]]:
    """
    构造 JoinGraph（Phase 1 支持最多 1 个跨域 JOIN + 1 个 dim_date JOIN）

    参数：
        needs_dim_date: G2 fact 表需要 JOIN dim_date 做日期过滤
        primary_table_override: 外部指定的主表（用于保证 JOIN 方向正确）

    关键修复（P0-2）：不再依赖 set 迭代顺序，而是根据 JoinPath 的
    left_table/right_table 方向确定主表和从表，确保 left_key 应用到左表、
    right_key 应用到右表。
    """
    # P0-2 修复：使用排序列表确保确定性顺序
    tables: set[str] = set()
    for metric in metrics:
        binding = get_binding_by_metric_name(metric.registered_name)
        if binding is None:
            continue
        table = binding.g3_table if layer == "g3" else binding.g2_table
        if table:
            tables.add(table)

    sorted_tables = sorted(tables)

    if len(sorted_tables) == 0:
        return None, ["无法确定任何源表"]

    if len(sorted_tables) == 1:
        # 单表查询
        primary_table = sorted_tables[0]
        table_short = primary_table.split(".")[-1]
        join_graph = JoinGraph(
            primary=JoinNode(
                table=primary_table,
                alias=table_short,
                type="",
                condition=JoinCondition(left="", right=""),
                constraint_ref="",
            ),
            joins=[],
        )
        # G2 fact 表需要追加 dim_date JOIN
        if needs_dim_date:
            dim_join = _build_dim_date_join(primary_table, table_short)
            if dim_join:
                join_graph.joins.append(dim_join)
        return join_graph, []

    # 多表查询：检查白名单，确定 JOIN 方向（使用排序列表保证确定性）
    join_path = get_join_path(sorted_tables[0], sorted_tables[1])
    if join_path is None:
        return None, [
            f"表 '{sorted_tables[0]}' 和 '{sorted_tables[1]}' 之间无白名单 JOIN 路径"
        ]

    # ── P0-2 修复：按 JoinPath 的方向确定主表和从表 ──
    # JoinPath 有 left_table/right_table 方向，left_key 属于 left_table，
    # right_key 属于 right_table。必须保证方向一致，否则生成无效 ON 条件。
    if join_path.left_table == sorted_tables[0]:
        primary_table = sorted_tables[0]
        secondary_table = sorted_tables[1]
    elif join_path.left_table == sorted_tables[1]:
        primary_table = sorted_tables[1]
        secondary_table = sorted_tables[0]
    else:
        # 防御：理论上 get_join_path 双向匹配，不应走到这里
        primary_table = sorted_tables[0]
        secondary_table = sorted_tables[1]

    p_alias = primary_table.split(".")[-1]
    s_alias = secondary_table.split(".")[-1]

    join_graph = JoinGraph(
        primary=JoinNode(
            table=primary_table,
            alias=p_alias,
            type="",
            condition=JoinCondition(left="", right=""),
            constraint_ref="",
        ),
        joins=[
            JoinNode(
                table=secondary_table,
                alias=s_alias,
                type=join_path.join_type,
                condition=JoinCondition(
                    left=f"{p_alias}.{join_path.left_key}",
                    right=f"{s_alias}.{join_path.right_key}",
                ),
                constraint_ref=join_path.constraint_ref,
            )
        ],
    )

    # G2 fact 表需要追加 dim_date JOIN（在跨域 JOIN 之后）
    if needs_dim_date:
        dim_join = _build_dim_date_join(primary_table, p_alias)
        if dim_join:
            join_graph.joins.append(dim_join)

    return join_graph, []


def _build_dim_date_join(fact_table: str, fact_alias: str) -> JoinNode | None:
    """
    为 G2 fact 表构造 dim_date JOIN 节点

    fact 表的日期列是整数代理键（如 pickup_date_key），
    必须通过 dim_date.date_key 关联才能获取实际日期值。
    """
    join_path = get_join_path(fact_table, "gold.dim_date")
    if join_path is None:
        return None
    return JoinNode(
        table="gold.dim_date",
        alias="dim_date",
        type=join_path.join_type,
        condition=JoinCondition(
            left=f"{fact_alias}.{join_path.left_key}",
            right=f"dim_date.{join_path.right_key}",
        ),
        constraint_ref=join_path.constraint_ref,
    )


def _build_execution_constraints(
    join_graph: JoinGraph, layer: str
) -> ExecutionConstraints:
    """从 JoinGraph 和层信息构造执行约束"""
    allowed_tables = [join_graph.primary.table]
    for join_node in join_graph.joins:
        allowed_tables.append(join_node.table)

    # 检测是否实际 JOIN 了 dim_date（而非硬编码为 False）
    requires_date_dim = any(
        "dim_date" in jn.table for jn in join_graph.joins
    )

    return ExecutionConstraints(
        read_only=True,
        query_timeout_seconds=30,
        max_result_rows=100000,
        allowed_tables=allowed_tables,
        requires_date_dim=requires_date_dim,
    )


def construct_sqlplan(intent: Intent) -> SQLPlan:
    """
    从 Intent 确定性构造 SQLPlan

    这是整个管道最关键的步骤——将"用户想要什么"（Intent）
    转换为"系统如何获取"（SQLPlan），全程无 LLM 参与。
    """
    warnings: list[str] = intent.warnings.copy()

    plan_id = _generate_plan_id()

    if not intent.is_valid:
        return SQLPlan(
            plan_id=plan_id,
            plan_name=intent.description,
            source_layer="unavailable",
            domain=intent.domain,
            is_valid=False,
            block_reason=intent.block_reason,
        )

    # ── 步骤 1：决定数据源层级 ──
    layer, layer_warnings = _resolve_layer(intent.metrics_requested)
    warnings.extend(layer_warnings)

    if layer == "unavailable":
        return SQLPlan(
            plan_id=plan_id,
            plan_name=intent.description,
            source_layer="unavailable",
            domain=intent.domain,
            is_valid=False,
            block_reason="; ".join(layer_warnings),
        )

    # ── 步骤 2：确定主表 ──
    primary_table, table_warnings = _determine_primary_table(
        intent.metrics_requested, layer
    )
    warnings.extend(table_warnings)

    if primary_table is None:
        return SQLPlan(
            plan_id=plan_id,
            plan_name=intent.description,
            source_layer=layer,
            domain=intent.domain,
            is_valid=False,
            block_reason="; ".join(table_warnings),
        )

    # ── 步骤 2.5：G2 日期过滤安全策略 ──
    # G2 fact 表的日期列是整数代理键（如 pickup_date_key），
    # 不能直接与字符串日期比较，必须通过 gold.dim_date.date 过滤。
    # 🚨 P0-1 修复：不再依赖列名后缀启发式（_is_date_key_column），
    # 而是强制要求——G2 层有任何日期过滤时必须 JOIN dim_date。
    # 这是硬安全门禁，不是可选优化。
    needs_dim_date = False
    has_date_filter = "date_range" in intent.filters
    if layer == "g2" and has_date_filter:
        # G2 + 日期过滤 → 强制要求 dim_date JOIN（硬安全门禁）
        needs_dim_date = True
        # 校验：确认该 fact 表在白名单中有到 dim_date 的 JOIN 路径
        if primary_table:
            date_join = get_join_path(primary_table, "gold.dim_date")
            if date_join is None:
                warnings.append(
                    f"G2 日期过滤安全门禁：表 '{primary_table}' 在白名单中无到 gold.dim_date 的 JOIN 路径，"
                    f"无法安全执行日期过滤。拒绝编译。"
                )
                return SQLPlan(
                    plan_id=plan_id,
                    plan_name=intent.description,
                    source_layer=layer,
                    domain=intent.domain,
                    is_valid=False,
                    block_reason=f"G2 日期过滤安全门禁：'{primary_table}' 缺少 dim_date JOIN 路径",
                )

    # ── 步骤 3：构造 JoinGraph ──
    join_graph, join_warnings = _build_join_graph(
        intent.metrics_requested, layer, needs_dim_date=needs_dim_date
    )
    warnings.extend(join_warnings)

    if join_graph is None:
        return SQLPlan(
            plan_id=plan_id,
            plan_name=intent.description,
            source_layer=layer,
            domain=intent.domain,
            is_valid=False,
            block_reason="; ".join(join_warnings),
        )

    # ── 步骤 4：构建字段绑定 ──
    column_bindings = _build_column_bindings(
        intent.metrics_requested, layer, primary_table
    )
    dimension_bindings = _build_dimension_bindings(
        intent.dimensions, primary_table
    )
    filter_bindings = _build_filter_bindings(
        intent.filters, primary_table, needs_dim_date=needs_dim_date
    )

    # ── 步骤 5：构建 group_by 和 order_by ──
    group_by: list[str] = []
    for gb in intent.group_by:
        dim_binding = get_dimension_binding(gb)
        if dim_binding:
            column = dim_binding.mappings.get(primary_table, gb)
            group_by.append(f"{primary_table}.{column}")
        else:
            group_by.append(f"{primary_table}.{gb}")

    # 通过维度绑定表解析 ORDER BY 的列名
    order_by: list[dict[str, str]] = []
    for ob in intent.group_by:
        dim_binding = get_dimension_binding(ob)
        if dim_binding:
            column = dim_binding.mappings.get(primary_table, ob)
            order_by.append({"column": f"{primary_table}.{column}", "direction": "ASC"})
        else:
            order_by.append({"column": f"{primary_table}.{ob}", "direction": "ASC"})

    # ── 步骤 6：注入执行约束 ──
    execution_constraints = _build_execution_constraints(join_graph, layer)

    # ── 步骤 7：输出路径 ──
    output_path = f"generated/results/{plan_id}.parquet"

    # ── 步骤 8：组装 SQLPlan ──
    plan = SQLPlan(
        plan_id=plan_id,
        plan_name=intent.description,
        source_layer=layer,
        domain=intent.domain,
        join_graph=join_graph,
        column_bindings=column_bindings,
        dimension_bindings=dimension_bindings,
        filter_bindings=filter_bindings,
        group_by=group_by,
        order_by=order_by,
        limit=None,
        execution_constraints=execution_constraints,
        output_format="parquet",
        output_path_template=output_path,
        warnings=warnings,
        is_valid=True,
    )

    return plan
