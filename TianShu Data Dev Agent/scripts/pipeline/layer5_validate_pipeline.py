"""
Layer 5 扩展：PipelinePlan 级校验（Phase 2）

新增两项校验（它们操作 PipelinePlan 结构，不需要数据库连接）：

  1. DAG 结构验证：
     - 环检测（DFS 拓扑排序——有环的 DAG 无法执行）
     - 依赖引用完整性（depends_on 中的 step_id 必须存在）
     - 拓扑序合法性（被依赖步骤必须先在 steps[] 中出现）

  2. 安全层级操作合规检查（safety_tier enforcement）：
     - 操作类型必须在当前 safety_tier 的允许列表中
     - 写操作的目标 schema 必须是 generated
     - 读操作不能引用 bronze/silver

LLM 角色：
  **完全禁止**。此层是纯确定性规则引擎。

设计原则：
  - 纯静态分析——不连接数据库，不执行 SQL
  - 所有检查是确定性规则——不调 LLM
  - 与现有 Layer 5 SQL 级校验互补——PipelinePlan 校验在此，
    SQL 文本校验在原有 layer5_validate.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .layer3_pipeline_plan import (
    PipelinePlan,
    PipelineStep,
    StepOperation,
)
from .layer3_ir import SQLPlan


# ═══════════════════════════════════════════════════════════
# 安全层级定义（从 pipeline_execution_config_schema.yml 衍生）
# ═══════════════════════════════════════════════════════════

# ── 每个安全层级允许的操作 ──
SAFETY_TIER_OPERATIONS: dict[str, set[str]] = {
    "query": {
        StepOperation.SELECT_ONLY,
    },
    "pipeline": {
        StepOperation.SELECT_ONLY,
        StepOperation.CREATE_TABLE_AS_SELECT,
        StepOperation.INSERT_OVERWRITE_PARTITION,
        StepOperation.INSERT_INTO_PARTITION,
        StepOperation.CREATE_VIEW,
    },
}

# ── 每个安全层级允许读取的 schema ──
SAFETY_TIER_READ_SCHEMAS: dict[str, set[str]] = {
    "query": {"gold"},
    "pipeline": {"gold", "generated"},
}

# ── 禁止读取的 schema（所有层级）──
FORBIDDEN_READ_SCHEMAS: set[str] = {"bronze", "silver"}

# ── 每个安全层级允许写入的 schema ──
SAFETY_TIER_WRITE_SCHEMAS: dict[str, set[str]] = {
    "query": set(),  # 不允许任何写入
    "pipeline": {"generated"},
}

# ── 禁止写入的 schema（所有层级）──
FORBIDDEN_WRITE_SCHEMAS: set[str] = {"gold", "bronze", "silver"}

# ── 全局禁止的 SQL 操作（所有层级，永久禁止）──
# 注意：DELETE_BY_ANTI_JOIN 已从 StepOperation 枚举中移除——
# DELETE 在任何层级都是黑名单操作。增量清理由 INSERT OVERWRITE 等价实现。
GLOBALLY_FORBIDDEN_OPERATIONS: set[str] = set()


# ═══════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════

@dataclass
class DAGValidationResult:
    """DAG 结构验证单项结果"""
    check_name: str
    passed: bool
    detail: str


@dataclass
class DAGValidationReport:
    """DAG 结构验证报告"""
    passed: bool
    # 环检测
    has_cycle: bool = False
    cycle_details: str = ""
    # 依赖引用完整性
    missing_dependencies: list[str] = field(default_factory=list)
    # 拓扑序
    topological_order_valid: bool = True
    execution_order: list[str] = field(default_factory=list)
    # 所有检查项
    checks: list[DAGValidationResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class OperationComplianceReport:
    """操作合规检查报告"""
    passed: bool
    checks: list[DAGValidationResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════
# P1：DAG 结构验证器
# ═══════════════════════════════════════════════════════════

def _detect_cycle(steps: list[PipelineStep]) -> tuple[bool, str, list[str]]:
    """
    使用 DFS 检测 DAG 中的环，同时返回拓扑排序

    算法：Kahn 算法（基于入度的拓扑排序）
      - 构建邻接表
      - 计算每个节点的入度
      - 迭代移除入度为 0 的节点
      - 若最终还有剩余节点 → 存在环

    返回：(has_cycle, cycle_detail, topological_order)
    """
    step_ids = {s.step_id for s in steps}
    # 构建邻接表和入度
    graph: dict[str, list[str]] = {s.step_id: [] for s in steps}
    in_degree: dict[str, int] = {s.step_id: 0 for s in steps}

    for step in steps:
        for dep in step.depends_on:
            if dep in step_ids:
                graph[dep].append(step.step_id)
                in_degree[step.step_id] += 1

    # Kahn 算法
    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    topological_order: list[str] = []

    while queue:
        current = queue.pop(0)
        topological_order.append(current)
        for neighbor in graph[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # 如果拓扑排序的节点数 < 总节点数 → 存在环
    if len(topological_order) < len(step_ids):
        remaining = step_ids - set(topological_order)
        return (
            True,
            f"检测到环——以下步骤形成循环依赖：{', '.join(sorted(remaining))}",
            topological_order,
        )
    return False, "", topological_order


def _check_dependency_references(steps: list[PipelineStep]) -> list[str]:
    """
    检查 depends_on 中引用的 step_id 是否都存在于 steps[] 中

    返回缺失引用的描述列表。
    """
    step_ids = {s.step_id for s in steps}
    missing: list[str] = []

    for step in steps:
        for dep in step.depends_on:
            if dep not in step_ids:
                missing.append(
                    f"步骤 '{step.step_id}' 依赖的 '{dep}' 在步骤列表中不存在"
                )
    return missing


def _check_topological_order(steps: list[PipelineStep]) -> tuple[bool, list[str]]:
    """
    检查 steps[] 是否按拓扑序排列
    规则：被依赖的步骤必须先在列表中出现在对应步骤之前

    返回：(是否合法, 违规描述列表)
    """
    # 记录每个 step_id 在列表中的位置
    position = {s.step_id: i for i, s in enumerate(steps)}
    violations: list[str] = []

    for i, step in enumerate(steps):
        for dep in step.depends_on:
            if dep in position and position[dep] >= i:
                violations.append(
                    f"拓扑序违规：步骤 '{step.step_id}'（位置 {i}）"
                    f"依赖 '{dep}'（位置 {position[dep]}），"
                    f"但 '{dep}' 排在了 '{step.step_id}' 之后"
                )
    return len(violations) == 0, violations


def validate_pipeline_dag(steps: list[PipelineStep]) -> DAGValidationReport:
    """
    PipelinePlan DAG 结构验证——纯静态分析

    这是 Layer 5 的 Phase 2 新增检查项。
    操作的对象是 PipelinePlan IR 的结构——不需要数据库连接。

    三项检查：
      1. 环检测（DFS 拓扑排序）
      2. 依赖引用完整性
      3. 拓扑序合法性（被依赖步骤必须先在 steps[] 中出现）
    """
    checks: list[DAGValidationResult] = []
    errors: list[str] = []

    # ── 检查 1：环检测 ──
    has_cycle, cycle_detail, exec_order = _detect_cycle(steps)
    cycle_check = DAGValidationResult(
        check_name="DAG 环检测",
        passed=not has_cycle,
        detail="未检测到环" if not has_cycle else cycle_detail,
    )
    checks.append(cycle_check)
    if has_cycle:
        errors.append(cycle_detail)

    # ── 检查 2：依赖引用完整性 ──
    missing = _check_dependency_references(steps)
    ref_check = DAGValidationResult(
        check_name="依赖引用完整性",
        passed=len(missing) == 0,
        detail="所有依赖引用有效" if not missing else f"缺失引用：{'; '.join(missing)}",
    )
    checks.append(ref_check)
    errors.extend(missing)

    # ── 检查 3：拓扑序合法性 ──
    order_valid, order_violations = _check_topological_order(steps)
    order_check = DAGValidationResult(
        check_name="拓扑序合法性",
        passed=order_valid,
        detail="拓扑序合法" if order_valid else f"违规：{'; '.join(order_violations)}",
    )
    checks.append(order_check)
    errors.extend(order_violations)

    return DAGValidationReport(
        passed=not has_cycle and len(missing) == 0 and order_valid,
        has_cycle=has_cycle,
        cycle_details=cycle_detail,
        missing_dependencies=missing,
        topological_order_valid=order_valid,
        execution_order=exec_order if not has_cycle else [],
        checks=checks,
        errors=errors,
    )


# ═══════════════════════════════════════════════════════════
# P2：安全层级操作合规检查
# ═══════════════════════════════════════════════════════════

def _extract_read_tables(step: PipelineStep) -> list[str]:
    """
    从步骤的 SQLPlan 中提取所有被读取的表名

    只提取 schema.table 前缀（不含列名），用于 schema 权限检查。
    """
    tables: list[str] = []
    if step.sql_plan and step.sql_plan.join_graph:
        tables.append(step.sql_plan.join_graph.primary.table)
        for join_node in step.sql_plan.join_graph.joins:
            tables.append(join_node.table)
    return tables


def _get_table_schema(table_name: str) -> str:
    """从全限定表名提取 schema（如 gold.dws_table → gold）"""
    parts = table_name.split(".")
    return parts[0] if len(parts) >= 2 else ""


def _check_read_schema_compliance(
    step: PipelineStep, safety_tier: str
) -> tuple[bool, str]:
    """
    检查步骤读取的表 schema 是否在当前安全层级允许列表内
    """
    read_tables = _extract_read_tables(step)
    if not read_tables:
        return True, "无表引用（跳过）"

    allowed = SAFETY_TIER_READ_SCHEMAS.get(safety_tier, set())

    violations: list[str] = []
    for table in read_tables:
        schema = _get_table_schema(table)
        if schema in FORBIDDEN_READ_SCHEMAS:
            violations.append(f"禁止读取 {table}（{schema} 层在所有安全层级中禁止访问）")
        elif schema not in allowed:
            violations.append(
                f"禁止读取 {table}（{schema} 层不在 safety_tier={safety_tier} 允许列表中）"
            )

    if violations:
        return False, "; ".join(violations)
    return True, f"所有读取的表 schema 合规（tier={safety_tier}）"


def _check_write_schema_compliance(
    step: PipelineStep, safety_tier: str
) -> tuple[bool, str]:
    """
    检查步骤写入的目标 schema 是否合规

    规则：
      - 写入目标必须以 generated. 开头（pipeline 层级）
      - 永远禁止写入 gold/bronze/silver
    """
    target = step.target_table
    schema = _get_table_schema(target)

    # 检查是否在全局禁止列表中
    if schema in FORBIDDEN_WRITE_SCHEMAS:
        return False, f"禁止写入 {target}（{schema} 层在所有安全层级中永久禁止写入）"

    # 检查是否在当前层级允许列表中
    allowed = SAFETY_TIER_WRITE_SCHEMAS.get(safety_tier, set())
    if schema not in allowed:
        return False, (
            f"禁止写入 {target}（{schema} 层不在 safety_tier={safety_tier} 允许写入列表中）"
            f"——允许写入的 schema：{allowed if allowed else '无（query 层禁止所有写入）'}"
        )

    return True, f"写入目标合规（safety_tier={safety_tier}，target={target}）"


def _check_operation_allowed(
    step: PipelineStep, safety_tier: str
) -> tuple[bool, str]:
    """
    检查步骤的 operation 是否在当前安全层级允许列表中
    """
    allowed = SAFETY_TIER_OPERATIONS.get(safety_tier, set())

    if step.operation not in allowed:
        return False, (
            f"操作 '{step.operation}' 不允许在 safety_tier={safety_tier} 下执行"
            f"——允许的操作：{sorted(allowed)}"
        )

    return True, f"操作 '{step.operation}' 在 safety_tier={safety_tier} 允许列表中"


def validate_operation_compliance(
    steps: list[PipelineStep], safety_tier: str = "query"
) -> OperationComplianceReport:
    """
    安全层级操作合规检查

    对每个步骤检查三项：
      1. operation 类型是否在该 safety_tier 允许列表中
      2. 读操作的表 schema 是否合规
      3. 写操作的目标 schema 是否合规（仅写操作步骤）
    """
    if safety_tier not in SAFETY_TIER_OPERATIONS:
        return OperationComplianceReport(
            passed=False,
            errors=[f"未知的 safety_tier: '{safety_tier}'——已知层级：{list(SAFETY_TIER_OPERATIONS.keys())}"],
        )

    checks: list[DAGValidationResult] = []
    errors: list[str] = []

    for step in steps:
        # 检查 1：操作类型允许
        op_ok, op_detail = _check_operation_allowed(step, safety_tier)
        checks.append(
            DAGValidationResult(
                check_name=f"操作类型检查 [{step.step_id}]",
                passed=op_ok,
                detail=op_detail,
            )
        )
        if not op_ok:
            errors.append(op_detail)
            # 如果操作不被允许，跳过后续检查（表读取/写入无意义）
            continue

        # 检查 2：读取 schema 合规
        read_ok, read_detail = _check_read_schema_compliance(step, safety_tier)
        checks.append(
            DAGValidationResult(
                check_name=f"读取Schema检查 [{step.step_id}]",
                passed=read_ok,
                detail=read_detail,
            )
        )
        if not read_ok:
            errors.append(read_detail)

        # 检查 3：写入 schema 合规（仅写操作）
        if step.operation in StepOperation.write_operations():
            write_ok, write_detail = _check_write_schema_compliance(step, safety_tier)
            checks.append(
                DAGValidationResult(
                    check_name=f"写入Schema检查 [{step.step_id}]",
                    passed=write_ok,
                    detail=write_detail,
                )
            )
            if not write_ok:
                errors.append(write_detail)

    return OperationComplianceReport(
        passed=len(errors) == 0,
        checks=checks,
        errors=errors,
    )


def validate_pipeline(
    pipeline: PipelinePlan, safety_tier: str = "query"
) -> tuple[DAGValidationReport, OperationComplianceReport]:
    """
    PipelinePlan 综合校验——Layer 5 的 Phase 2 入口

    对 PipelinePlan 执行两项独立检查：
      1. DAG 结构验证（拓扑结构正确性）
      2. 安全层级操作合规检查（操作-目标-schema 三元合规矩阵）

    返回两个独立报告——两者必须都通过才能进入 Layer 6。
    """
    dag_report = validate_pipeline_dag(pipeline.steps)
    compliance_report = validate_operation_compliance(pipeline.steps, safety_tier)
    return dag_report, compliance_report
