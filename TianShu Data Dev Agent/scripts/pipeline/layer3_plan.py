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

from datetime import datetime
from typing import Optional

from .column_binding import (
    get_binding_by_metric_name,
    get_dimension_binding,
    get_join_path,
    BindingEntry,
    DimensionBinding,
    JoinPath,
)
from .layer2_intent import Intent, ResolvedMetric, ResolvedDimension
from .layer3_ir import (
    # 异常
    SQLCompileError,
    # 核心 IR
    SQLPlan,
    JoinGraph, JoinNode, JoinCondition,
    ColumnBinding, DimensionColumnBinding, FilterBinding,
    # 表达式 IR
    ExpressionRef, ExpressionOperand, ExpressionConfig,
    ExpressionType, OperandKind,
    ColumnRef, LiteralValue, LiteralType, OutputType,
    # 窗口函数 IR
    WindowFunctionDef, WindowFunctionName, WindowFunctionArg,
    FunctionArgKind, OrderByEntry, FrameType,
    # CTE IR
    CTEDefinition,
    # 过滤器
    FilterType,
    # 执行约束
    ExecutionConstraints,
)


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
