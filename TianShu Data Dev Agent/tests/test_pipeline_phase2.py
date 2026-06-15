"""
Phase 2 管道级校验测试

测试 DAG 结构验证和安全层级操作合规检查。
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from scripts.pipeline.layer3_pipeline_plan import (
    PipelinePlan,
    PipelineStep,
    IncrementalIntent,
    StepOperation,
)
from scripts.pipeline.layer3_ir import (
    SQLPlan,
    JoinGraph,
    JoinNode,
    JoinCondition,
    # Phase 2 扩展类型——从 layer3_ir 导入（它们属于 SQLPlan 层）
    ColumnRef,
    LiteralValue,
    WindowFunctionArg,
    WindowFunctionDef,
    ExpressionOperand,
    ExpressionRef,
    CTEDefinition,
)
from scripts.pipeline.layer5_validate_pipeline import (
    validate_pipeline_dag,
    validate_operation_compliance,
    validate_pipeline,
    DAGValidationReport,
    OperationComplianceReport,
    SAFETY_TIER_OPERATIONS,
)


# ═══════════════════════════════════════════════════════════
# 测试用辅助函数
# ═══════════════════════════════════════════════════════════

def _make_step(
    step_id: str,
    step_name: str = "",
    operation: str = StepOperation.SELECT_ONLY,
    target_table: str = "generated.dummy",
    depends_on: list[str] | None = None,
    sql_plan: SQLPlan | None = None,
) -> PipelineStep:
    """快速创建测试用 PipelineStep"""
    return PipelineStep(
        step_id=step_id,
        step_name=step_name or f"步骤 {step_id}",
        operation=operation,
        target_table=target_table,
        depends_on=depends_on or [],
        sql_plan=sql_plan,
    )


def _make_sqlplan_with_tables(
    primary_table: str = "gold.dws_test",
    join_tables: list[str] | None = None,
) -> SQLPlan:
    """创建带表引用的测试用 SQLPlan"""
    primary = JoinNode(
        table=primary_table,
        alias="t1",
        type="PRIMARY",
        condition=JoinCondition(left="", right=""),
        constraint_ref="",
    )
    joins = []
    if join_tables:
        for i, table in enumerate(join_tables):
            joins.append(
                JoinNode(
                    table=table,
                    alias=f"tj{i+1}",
                    type="LEFT JOIN",
                    condition=JoinCondition(left="", right=""),
                    constraint_ref="",
                )
            )
    return SQLPlan(
        plan_id=f"test_{primary_table}",
        plan_name="test",
        source_layer="g3",
        domain="test",
        join_graph=JoinGraph(primary=primary, joins=joins),
    )


# ═══════════════════════════════════════════════════════════
# P1：DAG 结构验证测试
# ═══════════════════════════════════════════════════════════

class TestDAGCycleDetection:
    """DAG 环检测测试"""

    def test_linear_dag_no_cycle(self):
        """线性 DAG 应该无环"""
        steps = [
            _make_step("A", depends_on=[]),
            _make_step("B", depends_on=["A"]),
            _make_step("C", depends_on=["B"]),
        ]
        report = validate_pipeline_dag(steps)
        assert report.passed, f"线性 DAG 不应报环: {report.errors}"
        assert not report.has_cycle
        assert report.execution_order == ["A", "B", "C"]

    def test_diamond_dag_no_cycle(self):
        """菱形 DAG 应该无环"""
        steps = [
            _make_step("A", depends_on=[]),
            _make_step("B_left", depends_on=["A"]),
            _make_step("C_right", depends_on=["A"]),
            _make_step("D", depends_on=["B_left", "C_right"]),
        ]
        report = validate_pipeline_dag(steps)
        assert report.passed, f"菱形 DAG 不应报环: {report.errors}"
        assert not report.has_cycle

    def test_simple_cycle_detected(self):
        """简单的环（A→B→A）应该被检测"""
        steps = [
            _make_step("A", depends_on=["B"]),
            _make_step("B", depends_on=["A"]),
        ]
        report = validate_pipeline_dag(steps)
        assert not report.passed
        assert report.has_cycle
        assert "循环依赖" in report.cycle_details

    def test_triangle_cycle_detected(self):
        """三角环（A→B→C→A）应该被检测"""
        steps = [
            _make_step("A", depends_on=["C"]),
            _make_step("B", depends_on=["A"]),
            _make_step("C", depends_on=["B"]),
        ]
        report = validate_pipeline_dag(steps)
        assert not report.passed
        assert report.has_cycle

    def test_self_loop_detected(self):
        """自环（A→A）应该被检测"""
        steps = [
            _make_step("A", depends_on=["A"]),
        ]
        report = validate_pipeline_dag(steps)
        assert not report.passed
        assert report.has_cycle

    def test_no_steps(self):
        """空步骤列表应通过"""
        steps: list[PipelineStep] = []
        report = validate_pipeline_dag(steps)
        assert report.passed
        assert not report.has_cycle


class TestDAGDependencyReferences:
    """依赖引用完整性测试"""

    def test_all_dependencies_present(self):
        """所有依赖都存在"""
        steps = [
            _make_step("A", depends_on=[]),
            _make_step("B", depends_on=["A"]),
        ]
        report = validate_pipeline_dag(steps)
        assert report.passed
        assert len(report.missing_dependencies) == 0

    def test_missing_dependency_detected(self):
        """缺失的依赖应被检测"""
        steps = [
            _make_step("A", depends_on=[]),
            _make_step("B", depends_on=["X"]),  # X 不存在
        ]
        report = validate_pipeline_dag(steps)
        assert not report.passed
        assert len(report.missing_dependencies) == 1
        assert "X" in report.missing_dependencies[0]

    def test_multiple_missing_dependencies(self):
        """多个缺失依赖应全部被检测"""
        steps = [
            _make_step("A", depends_on=["Y"]),  # Y 不存在
            _make_step("B", depends_on=["Z"]),  # Z 不存在
        ]
        report = validate_pipeline_dag(steps)
        assert not report.passed
        assert len(report.missing_dependencies) == 2


class TestDAGTopologicalOrder:
    """拓扑序合法性测试"""

    def test_correct_order(self):
        """正确的拓扑序应通过"""
        steps = [
            _make_step("A", depends_on=[]),
            _make_step("B", depends_on=["A"]),
            _make_step("C", depends_on=["A", "B"]),
        ]
        report = validate_pipeline_dag(steps)
        assert report.passed
        assert report.topological_order_valid

    def test_wrong_order_detected(self):
        """错误的拓扑序应被检测（被依赖步骤排在了依赖步骤之后）"""
        steps = [
            _make_step("B", depends_on=["A"]),  # B 依赖 A，但 A 不在前面
            _make_step("A", depends_on=[]),
        ]
        report = validate_pipeline_dag(steps)
        assert not report.passed
        assert not report.topological_order_valid
        assert any("拓扑序违规" in e for e in report.errors)

    def test_correct_order_with_diamond(self):
        """菱形 DAG 的拓扑序应通过"""
        steps = [
            _make_step("extract", depends_on=[]),
            _make_step("compute", depends_on=["extract"]),
            _make_step("tag", depends_on=["compute"]),
            _make_step("report", depends_on=["compute", "tag"]),
        ]
        report = validate_pipeline_dag(steps)
        assert report.passed


# ═══════════════════════════════════════════════════════════
# P2：安全层级操作合规测试
# ═══════════════════════════════════════════════════════════

class TestSafetyTierOperationCompliance:
    """安全层级操作合规测试"""

    def test_select_allowed_in_query_tier(self):
        """SELECT 在 query 层级允许"""
        steps = [_make_step("A", operation=StepOperation.SELECT_ONLY)]
        report = validate_operation_compliance(steps, safety_tier="query")
        assert report.passed, f"SELECT 应在 query 层级允许: {report.errors}"

    def test_ctas_blocked_in_query_tier(self):
        """CTAS 在 query 层级禁止"""
        steps = [_make_step("A", operation=StepOperation.CREATE_TABLE_AS_SELECT)]
        report = validate_operation_compliance(steps, safety_tier="query")
        assert not report.passed
        assert any("CREATE_TABLE_AS_SELECT" in e for e in report.errors)

    def test_ctas_allowed_in_pipeline_tier(self):
        """CTAS 在 pipeline 层级允许"""
        steps = [
            _make_step(
                "A",
                operation=StepOperation.CREATE_TABLE_AS_SELECT,
                target_table="generated.test_table",
            )
        ]
        report = validate_operation_compliance(steps, safety_tier="pipeline")
        assert report.passed, f"CTAS 应在 pipeline 层级允许: {report.errors}"

    def test_write_to_gold_blocked_in_pipeline(self):
        """写入 gold.* 在 pipeline 层级禁止"""
        steps = [
            _make_step(
                "A",
                operation=StepOperation.CREATE_TABLE_AS_SELECT,
                target_table="gold.new_table",  # 不允许！
            )
        ]
        report = validate_operation_compliance(steps, safety_tier="pipeline")
        assert not report.passed
        assert any("gold" in e for e in report.errors)

    def test_write_to_generated_allowed_in_pipeline(self):
        """写入 generated.* 在 pipeline 层级允许"""
        steps = [
            _make_step(
                "A",
                operation=StepOperation.CREATE_TABLE_AS_SELECT,
                target_table="generated.intermediate",
            )
        ]
        report = validate_operation_compliance(steps, safety_tier="pipeline")
        assert report.passed, f"写入 generated.* 应在 pipeline 层级允许: {report.errors}"

    def test_select_with_bronze_table_blocked(self):
        """读取 bronze.* 表在任何层级禁止"""
        sql_plan = _make_sqlplan_with_tables(primary_table="bronze.raw_data")
        steps = [_make_step("A", sql_plan=sql_plan)]
        report = validate_operation_compliance(steps, safety_tier="pipeline")
        assert not report.passed
        assert any("bronze" in e for e in report.errors)

    def test_select_with_gold_table_allowed(self):
        """读取 gold.* 表在 query 层级允许"""
        sql_plan = _make_sqlplan_with_tables(primary_table="gold.dws_test")
        steps = [_make_step("A", sql_plan=sql_plan)]
        report = validate_operation_compliance(steps, safety_tier="query")
        assert report.passed, f"读取 gold.* 应在 query 层级允许: {report.errors}"

    def test_read_generated_allowed_in_pipeline_not_query(self):
        """读取 generated.* 在 pipeline 层级允许，query 层级禁止"""
        sql_plan = _make_sqlplan_with_tables(primary_table="generated.intermediate")
        steps = [_make_step("A", sql_plan=sql_plan)]

        # pipeline 层允许
        report_pipe = validate_operation_compliance(steps, safety_tier="pipeline")
        assert report_pipe.passed, f"读取 generated.* 应在 pipeline 层级允许: {report_pipe.errors}"

        # query 层禁止
        report_query = validate_operation_compliance(steps, safety_tier="query")
        assert not report_query.passed

    def test_unknown_safety_tier_rejected(self):
        """未知的安全层级应被拒绝"""
        steps = [_make_step("A")]
        report = validate_operation_compliance(steps, safety_tier="admin")
        assert not report.passed
        assert "未知的 safety_tier" in report.errors[0]

    def test_mixed_operations_in_pipeline(self):
        """混合操作（SELECT + CTAS）在 pipeline 层级应全部合规"""
        steps = [
            _make_step(
                "extract",
                operation=StepOperation.CREATE_TABLE_AS_SELECT,
                target_table="generated.extracted",
            ),
            _make_step(
                "query",
                operation=StepOperation.SELECT_ONLY,
                target_table="generated.dummy",
            ),
        ]
        report = validate_operation_compliance(steps, safety_tier="pipeline")
        assert report.passed, f"混合操作应全部合规: {report.errors}"


# ═══════════════════════════════════════════════════════════
# P1 + P2 综合验证
# ═══════════════════════════════════════════════════════════

class TestValidatePipeline:
    """综合校验测试（DAG + 安全层级）"""

    def test_valid_pipeline_passes_both_checks(self):
        """合法的管道应通过 DAG 和安全层级两层校验"""
        steps = [
            _make_step(
                "extract",
                operation=StepOperation.CREATE_TABLE_AS_SELECT,
                target_table="generated.extracted",
                depends_on=[],
            ),
            _make_step(
                "report",
                operation=StepOperation.SELECT_ONLY,
                target_table="generated.report",
                depends_on=["extract"],
            ),
        ]
        pipeline = PipelinePlan(
            pipeline_id="test_001",
            pipeline_name="test",
            steps=steps,
        )
        dag_report, compliance_report = validate_pipeline(pipeline, safety_tier="pipeline")
        assert dag_report.passed, f"DAG 验证失败: {dag_report.errors}"
        assert compliance_report.passed, f"合规验证失败: {compliance_report.errors}"

    def test_cycle_causes_dag_failure_but_compliance_ok(self):
        """DAG 有环时 DAG 验证失败，但合规检查仍独立通过"""
        steps = [
            _make_step("A", depends_on=["B"]),
            _make_step("B", depends_on=["A"]),
        ]
        pipeline = PipelinePlan(
            pipeline_id="test_cycle",
            pipeline_name="test",
            steps=steps,
        )
        dag_report, compliance_report = validate_pipeline(pipeline, safety_tier="query")
        assert not dag_report.passed  # 有环 —— DAG 失败
        assert compliance_report.passed  # 操作合规 —— SELECT 在 query 层允许

    def test_pipeline_tier_write_to_gold_fails(self):
        """pipeline 层级写入 gold.* 应失败"""
        steps = [
            _make_step(
                "bad_write",
                operation=StepOperation.CREATE_TABLE_AS_SELECT,
                target_table="gold.new_table",  # 不允许
            )
        ]
        pipeline = PipelinePlan(
            pipeline_id="test_bad_write",
            pipeline_name="test",
            steps=steps,
        )
        dag_report, compliance_report = validate_pipeline(pipeline, safety_tier="pipeline")
        assert dag_report.passed  # 无结构问题
        assert not compliance_report.passed  # 写入合规失败
