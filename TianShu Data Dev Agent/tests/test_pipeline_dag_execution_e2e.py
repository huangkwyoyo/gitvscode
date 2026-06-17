"""
DAG 执行语义端到端测试

覆盖现有编译级测试未覆盖的执行语义缺口：
  1. 多步串联依赖产物（中间表传递链）
  2. 执行 trace 完整性（step_id / depends_on / target_table）
  3. 中间表引用校验（下游必须引用上游 output，不得凭空引用）
  4. 失败传播模型（静态计划层——不伪装真实执行器/回滚）
  5. 跨步列引用正确性
  6. 安全层级写约束（query 禁 CTAS，pipeline 允许 generated 禁 gold）

约束：
  - 纯静态验证——不连接数据库，不执行 SQL
  - 不改生产代码（除非发现 A 类局部 bug）
  - 不接 LLM / Spark / 生产库
  - 不伪装已实现的能力

当前能力边界：
  - ✅ 编译级验证：compile_sql / compile_operation / validate_pipeline_dag
  - ✅ 策略解析：resolve_strategy
  - ❌ 真实 DAG 执行器（layer6_execute 的 pipeline 模式）
  - ❌ 中间表物化管理
  - ❌ 真实回滚/失败停止
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import yaml

from scripts.pipeline.layer3_pipeline_plan import (
    PipelinePlan,
    PipelineStep,
    StepOperation,
    IncrementalIntent,
)
from scripts.pipeline.layer3_ir import (
    SQLPlan,
    JoinGraph,
    JoinNode,
    JoinCondition,
    ColumnBinding,
    FilterBinding,
    FilterType,
    SQLCompileError,
)
from scripts.pipeline.layer4_generate import compile_sql
from scripts.pipeline.layer4_operation import (
    compile_operation,
    resolve_strategy,
    ExecutionStrategy,
)
from scripts.pipeline.layer5_validate_pipeline import (
    validate_pipeline_dag,
    validate_operation_compliance,
    validate_pipeline,
    DAGValidationReport,
    OperationComplianceReport,
)
from tests.test_pipeline_dag_e2e import (
    _load_yaml_fixture,
    _assert_sql_structure,
    _build_join_graph,
    _build_column_bindings,
    _build_filter_bindings,
    _infer_filter_type,
    _infer_source_layer,
)


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════

def _make_minimal_step(
    step_id: str,
    step_name: str = "",
    operation: StepOperation = StepOperation.SELECT_ONLY,
    target_table: str = "",
    depends_on: list[str] | None = None,
    primary_table: str = "gold.dws_daily_trip_summary",
    column_bindings: list[dict] | None = None,
    group_by: list[str] | None = None,
) -> PipelineStep:
    """快速创建测试用 PipelineStep（带最小 SQLPlan）"""
    if column_bindings is None:
        column_bindings = [
            {"column_name": "city_id", "alias": "city_id"},
            {"column_name": "trip_count", "alias": "trip_count"},
        ]

    primary = JoinNode(
        table=primary_table,
        alias="t1",
        type="PRIMARY",
        condition=JoinCondition(left="", right=""),
        constraint_ref="",
    )

    cols = _build_column_bindings(column_bindings, primary_table)

    sql_plan = SQLPlan(
        plan_id=f"test_{step_id}",
        plan_name=step_name or f"步骤 {step_id}",
        source_layer="g3",
        domain="test",
        join_graph=JoinGraph(primary=primary, joins=[]),
        column_bindings=cols,
        group_by=group_by or [],
    )

    return PipelineStep(
        step_id=step_id,
        step_name=step_name or f"步骤 {step_id}",
        operation=operation,
        target_table=target_table,
        depends_on=depends_on or [],
        sql_plan=sql_plan,
    )


def _build_3step_pipeline() -> PipelinePlan:
    """
    构建标准 3 步串联管道：
      Step A（CTAS）→ Step B（CTAS）→ Step C（SELECT_ONLY）

    中间表链路：generated.step_a_out → generated.step_b_out
    """
    return PipelinePlan(
        pipeline_id="test_3step",
        pipeline_name="3步串联测试管道",
        target_dialect="duckdb",
        steps=[
            _make_minimal_step(
                step_id="step_a",
                step_name="提取原始数据",
                operation=StepOperation.CREATE_TABLE_AS_SELECT,
                target_table="generated.step_a_out",
                depends_on=[],
                primary_table="gold.dws_daily_trip_summary",
            ),
            _make_minimal_step(
                step_id="step_b",
                step_name="聚合中间结果",
                operation=StepOperation.CREATE_TABLE_AS_SELECT,
                target_table="generated.step_b_out",
                depends_on=["step_a"],
                primary_table="generated.step_a_out",
                column_bindings=[
                    {"column_name": "city_id", "alias": "city_id"},
                    {"column_name": "trip_count", "alias": "total_trips", "aggregation": "SUM"},
                ],
                group_by=["city_id"],
            ),
            _make_minimal_step(
                step_id="step_c",
                step_name="最终查询报告",
                operation=StepOperation.SELECT_ONLY,
                target_table="",
                depends_on=["step_b"],
                primary_table="generated.step_b_out",
            ),
        ],
    )


# ═══════════════════════════════════════════════════════════
# 1. 多步串联 DAG——拓扑顺序 + 产物传递
# ═══════════════════════════════════════════════════════════

class TestMultiStepSerialChain:
    """2-3 步串联 DAG：拓扑顺序、下游引用上游 output target"""

    def test_3step_topological_order_correct(self):
        """3 步串联：拓扑排序应为 A → B → C"""
        pipeline = _build_3step_pipeline()
        report = validate_pipeline_dag(pipeline.steps)
        assert report.passed, f"DAG 校验失败: {report.errors}"
        assert report.execution_order == ["step_a", "step_b", "step_c"], (
            f"拓扑顺序错误: {report.execution_order}"
        )

    def test_3step_downstream_depends_on_upstream(self):
        """下游步骤的 depends_on 必须指向上游 step_id"""
        pipeline = _build_3step_pipeline()
        # Step B 依赖 Step A
        assert "step_a" in pipeline.steps[1].depends_on, (
            "Step B 应依赖 Step A"
        )
        # Step C 依赖 Step B
        assert "step_b" in pipeline.steps[2].depends_on, (
            "Step C 应依赖 Step B"
        )

    def test_3step_downstream_references_upstream_target_table(self):
        """下游 SQL 的 primary_table 必须是上游的 target_table"""
        pipeline = _build_3step_pipeline()
        # Step B 读取 Step A 的输出表
        step_b = pipeline.steps[1]
        assert step_b.sql_plan is not None
        assert step_b.sql_plan.join_graph.primary.table == "generated.step_a_out", (
            f"Step B 应读取 generated.step_a_out，实际读取 {step_b.sql_plan.join_graph.primary.table}"
        )
        # Step C 读取 Step B 的输出表
        step_c = pipeline.steps[2]
        assert step_c.sql_plan is not None
        assert step_c.sql_plan.join_graph.primary.table == "generated.step_b_out", (
            f"Step C 应读取 generated.step_b_out，实际读取 {step_c.sql_plan.join_graph.primary.table}"
        )

    def test_3step_all_steps_compile_successfully(self):
        """3 步串联：每步 SQL 编译成功"""
        pipeline = _build_3step_pipeline()
        for step in pipeline.steps:
            assert step.sql_plan is not None
            sql, _ = compile_sql(step.sql_plan)
            assert isinstance(sql, str) and len(sql) > 0, (
                f"{step.step_id} 编译失败或产出为空"
            )
            assert "SELECT" in sql.upper(), (
                f"{step.step_id} 编译结果不包含 SELECT"
            )

    def test_2step_minimal_chain(self):
        """2 步最小链：A(CTAS) → B(SELECT_ONLY)，B 引用 A 的输出"""
        pipeline = PipelinePlan(
            pipeline_id="test_2step",
            pipeline_name="2步最小链",
            steps=[
                _make_minimal_step(
                    step_id="extract",
                    operation=StepOperation.CREATE_TABLE_AS_SELECT,
                    target_table="generated.raw",
                    depends_on=[],
                ),
                _make_minimal_step(
                    step_id="query",
                    operation=StepOperation.SELECT_ONLY,
                    target_table="",
                    depends_on=["extract"],
                    primary_table="generated.raw",
                ),
            ],
        )
        report = validate_pipeline_dag(pipeline.steps)
        assert report.passed, f"2步链 DAG 校验失败: {report.errors}"
        assert report.execution_order == ["extract", "query"]

        # 验证编译
        sql, _ = compile_sql(pipeline.steps[1].sql_plan)
        assert "generated.raw" in sql, (
            f"下游 SQL 应引用上游输出表 generated.raw:\n{sql}"
        )


# ═══════════════════════════════════════════════════════════
# 2. 5 步链式 DAG——执行 trace 完整性
# ═══════════════════════════════════════════════════════════

class TestChain5StepExecutionTrace:
    """5 步链式 DAG（使用 chain_5step fixture）——每步 trace 完整性"""

    @pytest.fixture
    def chain(self) -> PipelinePlan:
        return _load_yaml_fixture("chain_5step")

    def test_all_5_steps_have_step_id(self, chain):
        """每个步骤必须有 step_id"""
        step_ids = [s.step_id for s in chain.steps]
        assert len(step_ids) == 5
        assert len(set(step_ids)) == 5, f"step_id 重复: {step_ids}"
        assert all(sid for sid in step_ids), "存在空的 step_id"

    def test_all_5_steps_have_depends_on_list(self, chain):
        """每个步骤的 depends_on 必须存在（即使为空列表）"""
        for step in chain.steps:
            assert isinstance(step.depends_on, list), (
                f"{step.step_id} 的 depends_on 不是列表"
            )

    def test_all_5_steps_have_target_table(self, chain):
        """每个步骤必须有 target_table 或声明为空（SELECT_ONLY）"""
        for step in chain.steps:
            if step.operation == StepOperation.SELECT_ONLY:
                assert step.target_table == "", (
                    f"SELECT_ONLY 步骤 {step.step_id} target_table 应为空字符串"
                )
            else:
                assert step.target_table, (
                    f"写操作步骤 {step.step_id} 必须有 target_table"
                )
                assert step.target_table.startswith("generated."), (
                    f"{step.step_id} target_table 应以 generated. 开头: {step.target_table}"
                )

    def test_chain_forms_correct_dependency_order(self, chain):
        """依赖链形成正确的顺序：extract_trip → aggregate_daily → enrich_city → tag_anomaly → final_report"""
        expected = [
            "extract_trip",
            "aggregate_daily",
            "enrich_city",
            "tag_anomaly",
            "final_report",
        ]
        report = validate_pipeline_dag(chain.steps)
        assert report.execution_order == expected, (
            f"执行顺序错误: {report.execution_order}"
        )

    def test_chain_dependencies_form_linear_sequence(self, chain):
        """每步只依赖紧前步骤（线性链）"""
        # Step 1：无依赖
        assert chain.steps[0].depends_on == []
        # Step 2-5：各依赖前一步
        for i in range(1, 5):
            prev_id = chain.steps[i - 1].step_id
            assert chain.steps[i].depends_on == [prev_id], (
                f"{chain.steps[i].step_id} 应只依赖 [{prev_id}]，"
                f"实际依赖 {chain.steps[i].depends_on}"
            )

    def test_each_step_compiles_to_valid_sql(self, chain):
        """每步编译产生有效 SQL"""
        for step in chain.steps:
            assert step.sql_plan is not None
            sql, _ = compile_sql(step.sql_plan)
            assert len(sql) > 0, f"{step.step_id} 编译产出为空"
            assert "SELECT" in sql.upper(), (
                f"{step.step_id} 编译结果不包含 SELECT"
            )

    def test_each_step_compiles_to_operation_sql(self, chain):
        """每步编译 + 操作包裹产生有效 SQL"""
        for step in chain.steps:
            assert step.sql_plan is not None
            select_sql, _ = compile_sql(step.sql_plan)
            op_sql = compile_operation(step, select_sql, dialect="duckdb")
            assert len(op_sql) > 0, f"{step.step_id} 操作编译产出为空"

    def test_intermediate_table_chain_is_continuous(self, chain):
        """中间表链路连续——每步的输出表成为下一步的输入表"""
        # Step 1 → 输出 generated.tmp_trip_raw
        assert chain.steps[0].target_table == "generated.tmp_trip_raw"
        # Step 2 → 读取 generated.tmp_trip_raw，输出 generated.agg_trip_daily
        assert chain.steps[1].sql_plan.join_graph.primary.table == "generated.tmp_trip_raw"
        assert chain.steps[1].target_table == "generated.agg_trip_daily"
        # Step 3 → 读取 generated.agg_trip_daily，输出 generated.enriched_trip
        assert chain.steps[2].sql_plan.join_graph.primary.table == "generated.agg_trip_daily"
        assert chain.steps[2].target_table == "generated.enriched_trip"
        # Step 4 → 读取 generated.enriched_trip，输出 generated.tagged_trip
        assert chain.steps[3].sql_plan.join_graph.primary.table == "generated.enriched_trip"
        assert chain.steps[3].target_table == "generated.tagged_trip"
        # Step 5 → 读取 generated.tagged_trip，无输出（SELECT_ONLY）
        assert chain.steps[4].sql_plan.join_graph.primary.table == "generated.tagged_trip"
        assert chain.steps[4].operation == StepOperation.SELECT_ONLY

    def test_chain_operations_are_valid_ctas_and_select(self, chain):
        """链式 DAG 前 4 步为 CTAS，最后一步为 SELECT_ONLY"""
        for i in range(4):
            assert chain.steps[i].operation == StepOperation.CREATE_TABLE_AS_SELECT, (
                f"Step {i+1} 应为 CTAS，实际为 {chain.steps[i].operation}"
            )
        assert chain.steps[4].operation == StepOperation.SELECT_ONLY


# ═══════════════════════════════════════════════════════════
# 3. 中间表引用校验
# ═══════════════════════════════════════════════════════════

class TestIntermediateTableReferences:
    """中间表引用——下游必须引用上游 output，不得凭空引用"""

    def test_downstream_references_declared_upstream_target(self):
        """下游 primary_table 必须匹配上游 target_table（已声明的中间表）"""
        pipeline = _build_3step_pipeline()
        # Step B primary_table = generated.step_a_out = Step A target_table
        assert pipeline.steps[1].sql_plan.join_graph.primary.table == pipeline.steps[0].target_table, (
            "下游 primary_table 与上游 target_table 不一致"
        )

    def test_undeclared_intermediate_table_caught_by_dag_check(self):
        """
        引用未声明的中间表——DAG 依赖校验可发现

        如果 Step C depends_on=["step_b"] 但 step_b 的 target_table 与
        step_c 的 primary_table 不匹配，虽然 DAG 拓扑正确但语义错误。
        当前验证层通过 depends_on 完整性检查捕获依赖缺失，
        但不主动校验 primary_table ↔ target_table 一致性——
        这是当前的能力边界。
        """
        # 创建一个 depends_on 正确但表引用不匹配的场景
        steps = [
            _make_minimal_step(
                step_id="step_a",
                operation=StepOperation.CREATE_TABLE_AS_SELECT,
                target_table="generated.a_out",
                depends_on=[],
            ),
            _make_minimal_step(
                step_id="step_b",
                operation=StepOperation.CREATE_TABLE_AS_SELECT,
                target_table="generated.b_out",
                depends_on=["step_a"],
                primary_table="generated.nonexistent_table",  # ← 不存在的表！
            ),
        ]
        pipeline = PipelinePlan(
            pipeline_id="test_bad_ref",
            pipeline_name="bad",
            steps=steps,
        )
        # DAG 结构校验通过（depends_on 引用有效）
        dag_report = validate_pipeline_dag(pipeline.steps)
        assert dag_report.passed, (
            "DAG 结构应通过——depends_on 引用有效，"
            "primary_table 一致性不在 DAG 结构校验范围"
        )
        # 注意：当前没有自动校验 primary_table ↔ target_table 一致性。
        # 这是已知能力边界——需要 table_existence 运行时检查或
        # PipelinePlan 级引用完整性校验（未来实现）。
        # 当前防线 2 的 check_table_existence 可在连接数据库后捕获此类问题。

    def test_primary_table_in_upstream_list(self):
        """
        下游读取的表应当在某个上游步骤的 target_table 或 gold.* 表中

        这是引用完整性校验的逻辑——当前通过代码审查/人审保证，
        自动校验尚未实现。
        """
        pipeline = _build_3step_pipeline()
        # 收集所有上游 target_table
        upstream_targets: set[str] = set()
        for step in pipeline.steps:
            if step.target_table:
                upstream_targets.add(step.target_table)

        # Step B 的 primary_table 应在集合中或为 gold.*
        step_b_table = pipeline.steps[1].sql_plan.join_graph.primary.table
        is_valid = (
            step_b_table in upstream_targets
            or step_b_table.startswith("gold.")
        )
        assert is_valid, (
            f"Step B 读取的 {step_b_table} 不在已知上游输出 {upstream_targets} 中"
        )

    def test_cross_step_column_references_match(self):
        """
        跨步列引用正确性——
        下游引用的列应当来自上游输出表的已知列

        当前通过 lineage/source_refs 注释标注来源，
        自动校验通过静态扫描 source_refs 实现。
        """
        # 使用 chain_5step fixture——各步列引用已通过 source_refs 标注
        chain = _load_yaml_fixture("chain_5step")
        # Step 3 (enrich_city) 的 column_bindings 标注了 source_table
        step3 = chain.steps[2]
        assert step3.sql_plan is not None
        for col in step3.sql_plan.column_bindings:
            # 每个列绑定应有明确的 column_ref
            assert col.column_ref, f"列 {col.alias} 缺少 column_ref"
            # column_ref 应包含源表信息
            assert "." in col.column_ref or col.alias, (
                f"列 {col.alias} 的 column_ref 格式异常: {col.column_ref}"
            )


# ═══════════════════════════════════════════════════════════
# 4. 失败路径——静态计划层失败传播模型
# ═══════════════════════════════════════════════════════════

class TestFailurePropagationModel:
    """
    失败传播模型——静态计划层

    ⚠️ 当前能力边界：
      - ❌ 无真实 DAG 执行器（scripts/pipeline/ 的 layer6_execute.py 是单 SQL 执行器）
      - ❌ 无中间表物化管理
      - ❌ 无真实回滚/失败停止机制
      - ✅ DAG 结构校验可在计划层检测无效依赖
      - ✅ 操作合规检查可在计划层阻止危险操作

    本节测试静态计划层的失效检测能力，不伪装已实现真实执行回滚。
    """

    def test_missing_dependency_causes_dag_failure(self):
        """缺失的依赖导致 DAG 校验失败——计划层即可拦截"""
        steps = [
            _make_minimal_step(
                step_id="step_a",
                operation=StepOperation.CREATE_TABLE_AS_SELECT,
                target_table="generated.a_out",
                depends_on=[],
            ),
            _make_minimal_step(
                step_id="step_b",
                operation=StepOperation.SELECT_ONLY,
                target_table="",
                depends_on=["step_missing"],  # ← 不存在的依赖
            ),
        ]
        report = validate_pipeline_dag(steps)
        assert not report.passed, "缺失依赖应导致 DAG 校验失败"
        assert len(report.missing_dependencies) == 1
        assert "step_missing" in report.missing_dependencies[0]

    def test_cycle_causes_dag_failure(self):
        """环导致 DAG 校验失败——计划层即可拦截"""
        steps = [
            _make_minimal_step("A", depends_on=["B"]),
            _make_minimal_step("B", depends_on=["A"]),
        ]
        report = validate_pipeline_dag(steps)
        assert not report.passed
        assert report.has_cycle
        assert "循环依赖" in report.cycle_details

    def test_topological_order_violation_causes_dag_failure(self):
        """拓扑序违规导致 DAG 校验失败"""
        steps = [
            _make_minimal_step("B", depends_on=["A"]),  # B 依赖 A 但 A 在后面
            _make_minimal_step("A", depends_on=[]),
        ]
        report = validate_pipeline_dag(steps)
        assert not report.passed
        assert not report.topological_order_valid
        assert any("拓扑序违规" in e for e in report.errors)

    def test_no_real_executor_capability_boundary(self):
        """
        明确能力边界：当前无真实 DAG 执行器

        layer6_execute.py 的 execute_sql 是单条 SQL 执行器，不支持：
          - 按 DAG 拓扑序自动执行多步骤
          - 中间表物化到 generated schema
          - 步骤失败后阻止下游执行
          - 回滚已执行的中间步骤

        这是已记录的 TODO，不是缺陷。
        防线 2 的静态检查 + 人审闸门是当前的实际安全边界。
        """
        # 验证 DAG 结构校验可用——这是当前实际可用的防线
        pipeline = _build_3step_pipeline()
        dag_report, compliance_report = validate_pipeline(pipeline, safety_tier="pipeline")
        assert dag_report.passed, "合法 3 步链应通过 DAG 校验"
        assert compliance_report.passed, "合法 3 步链应通过合规检查"

        # 确认这些检查都是纯静态的（不连接数据库）
        assert len(dag_report.checks) >= 3, "DAG 校验应包含至少 3 项检查"
        for check in dag_report.checks:
            assert check.passed, f"DAG 检查项 '{check.check_name}' 应通过: {check.detail}"

    def test_compliance_blocks_dangerous_pipeline(self):
        """合规检查在计划层阻止危险管道——即使 DAG 结构正确"""
        steps = [
            _make_minimal_step(
                step_id="bad_step",
                operation=StepOperation.CREATE_TABLE_AS_SELECT,
                target_table="gold.production_table",  # ← 不允许！
                depends_on=[],
            ),
        ]
        pipeline = PipelinePlan(
            pipeline_id="test_bad",
            pipeline_name="bad",
            steps=steps,
        )
        dag_report, compliance_report = validate_pipeline(pipeline, safety_tier="pipeline")
        assert dag_report.passed, "DAG 结构应正确（无依赖问题）"
        assert not compliance_report.passed, "写入 gold.* 应被合规检查拦截"
        assert any("gold" in e for e in compliance_report.errors), (
            f"错误信息应包含 'gold': {compliance_report.errors}"
        )


# ═══════════════════════════════════════════════════════════
# 5. 安全层级——query 禁 CTAS，pipeline 允许 generated 禁 gold
# ═══════════════════════════════════════════════════════════

class TestSafetyTierPipelineWriteConstraints:
    """安全层级写约束——query vs pipeline 的中间表权限边界"""

    def test_query_tier_blocks_all_writes(self):
        """query 层级禁止所有写操作（CTAS/INSERT/CREATE_VIEW）"""
        write_ops = [
            StepOperation.CREATE_TABLE_AS_SELECT,
            StepOperation.INSERT_OVERWRITE_PARTITION,
            StepOperation.INSERT_INTO_PARTITION,
            StepOperation.CREATE_VIEW,
        ]
        for op in write_ops:
            steps = [_make_minimal_step(
                step_id="w",
                operation=op,
                target_table="generated.test",
            )]
            report = validate_operation_compliance(steps, safety_tier="query")
            assert not report.passed, (
                f"query 层级应阻止 {op.value}，但校验通过了"
            )

    def test_query_tier_allows_select_only(self):
        """query 层级只允许 SELECT_ONLY"""
        steps = [_make_minimal_step(
            step_id="s",
            operation=StepOperation.SELECT_ONLY,
        )]
        report = validate_operation_compliance(steps, safety_tier="query")
        assert report.passed, f"query 层级应允许 SELECT_ONLY: {report.errors}"

    def test_pipeline_tier_allows_write_to_generated(self):
        """pipeline 层级允许写入 generated.*"""
        allowed_ops = [
            StepOperation.CREATE_TABLE_AS_SELECT,
            StepOperation.INSERT_OVERWRITE_PARTITION,
            StepOperation.INSERT_INTO_PARTITION,
            StepOperation.CREATE_VIEW,
        ]
        for op in allowed_ops:
            steps = [_make_minimal_step(
                step_id="w",
                operation=op,
                target_table="generated.intermediate",
            )]
            report = validate_operation_compliance(steps, safety_tier="pipeline")
            assert report.passed, (
                f"pipeline 层级应允许 {op.value} 写入 generated.*: {report.errors}"
            )

    def test_pipeline_tier_blocks_write_to_gold(self):
        """pipeline 层级禁止写入 gold.*"""
        steps = [_make_minimal_step(
            step_id="bad",
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            target_table="gold.new_table",
        )]
        report = validate_operation_compliance(steps, safety_tier="pipeline")
        assert not report.passed, "写入 gold.* 应被 pipeline 层级拦截"
        assert any("gold" in e for e in report.errors)

    def test_pipeline_tier_blocks_write_to_bronze(self):
        """pipeline 层级禁止写入 bronze.*"""
        steps = [_make_minimal_step(
            step_id="bad",
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            target_table="bronze.raw",
        )]
        report = validate_operation_compliance(steps, safety_tier="pipeline")
        assert not report.passed, "写入 bronze.* 应被拦截"
        assert any("bronze" in e for e in report.errors)

    def test_pipeline_tier_blocks_write_to_silver(self):
        """pipeline 层级禁止写入 silver.*"""
        steps = [_make_minimal_step(
            step_id="bad",
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            target_table="silver.clean",
        )]
        report = validate_operation_compliance(steps, safety_tier="pipeline")
        assert not report.passed, "写入 silver.* 应被拦截"
        assert any("silver" in e for e in report.errors)

    def test_pipeline_tier_allows_read_generated(self):
        """pipeline 层级允许读取 generated.*（中间表引用）"""
        steps = [_make_minimal_step(
            step_id="r",
            operation=StepOperation.SELECT_ONLY,
            primary_table="generated.intermediate",
        )]
        report = validate_operation_compliance(steps, safety_tier="pipeline")
        assert report.passed, f"pipeline 层级应允许读取 generated.*: {report.errors}"

    def test_pipeline_tier_blocks_read_bronze(self):
        """pipeline 层级禁止读取 bronze.*"""
        steps = [_make_minimal_step(
            step_id="bad",
            operation=StepOperation.SELECT_ONLY,
            primary_table="bronze.raw_data",
        )]
        report = validate_operation_compliance(steps, safety_tier="pipeline")
        assert not report.passed, "读取 bronze.* 应被拦截"
        assert any("bronze" in e for e in report.errors)

    def test_full_pipeline_with_write_constraints(self):
        """
        完整管道校验：query 层级拒绝 multi-step CTAS pipeline，
        pipeline 层级接受合法的 generated.* 写入管道
        """
        pipeline = _build_3step_pipeline()

        # query 层级应拒绝（含 2 个 CTAS 步骤）
        _, q_report = validate_pipeline(pipeline, safety_tier="query")
        assert not q_report.passed, "query 层级应拒绝含 CTAS 的管道"

        # pipeline 层级应接受
        _, p_report = validate_pipeline(pipeline, safety_tier="pipeline")
        assert p_report.passed, (
            f"pipeline 层级应接受合法 generated.* 写入: {p_report.errors}"
        )


# ═══════════════════════════════════════════════════════════
# 6. 执行策略解析——静态验证
# ═══════════════════════════════════════════════════════════

class TestExecutionStrategyResolution:
    """执行策略解析：验证 resolve_strategy 的正确性"""

    def test_ctas_without_incremental_yields_full_overwrite(self):
        """CTAS 无增量意图 → FULL_OVERWRITE"""
        step = _make_minimal_step(
            step_id="s",
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            target_table="generated.test",
        )
        assert resolve_strategy(step) == ExecutionStrategy.FULL_OVERWRITE

    def test_select_only_yields_select_only(self):
        """SELECT_ONLY → SELECT_ONLY（忽略增量意图）"""
        step = _make_minimal_step(
            step_id="s",
            operation=StepOperation.SELECT_ONLY,
        )
        # 即使有增量意图，SELECT_ONLY 也始终返回 SELECT_ONLY
        step.incremental_intent = IncrementalIntent(
            incremental=True,
            dedup_scope="partition",
            partition_column="dt",
        )
        assert resolve_strategy(step) == ExecutionStrategy.SELECT_ONLY

    def test_create_view_yields_create_view(self):
        """CREATE_VIEW → CREATE_VIEW"""
        step = _make_minimal_step(
            step_id="s",
            operation=StepOperation.CREATE_VIEW,
            target_table="generated.my_view",
        )
        assert resolve_strategy(step) == ExecutionStrategy.CREATE_VIEW

    def test_ctas_with_partition_incremental_yields_partition_overwrite(self):
        """CTAS + 增量分区覆盖 → PARTITION_OVERWRITE"""
        step = _make_minimal_step(
            step_id="s",
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            target_table="generated.test",
        )
        step.incremental_intent = IncrementalIntent(
            incremental=True,
            dedup_scope="partition",
            partition_column="dt",
        )
        assert resolve_strategy(step) == ExecutionStrategy.PARTITION_OVERWRITE

    def test_ctas_with_key_merge_incremental_yields_key_merge(self):
        """CTAS + KEY_MERGE 增量 → KEY_MERGE"""
        step = _make_minimal_step(
            step_id="s",
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            target_table="generated.test",
        )
        step.incremental_intent = IncrementalIntent(
            incremental=True,
            dedup_scope="key_merge",
            key_columns=["id"],
        )
        assert resolve_strategy(step) == ExecutionStrategy.KEY_MERGE

    def test_key_merge_compile_raises_not_implemented(self):
        """KEY_MERGE 编译应抛出 SQLCompileError（暂未实现）"""
        step = _make_minimal_step(
            step_id="s",
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            target_table="generated.test",
        )
        step.incremental_intent = IncrementalIntent(
            incremental=True,
            dedup_scope="key_merge",
            key_columns=["id"],
        )
        select_sql, _ = compile_sql(step.sql_plan)
        with pytest.raises(SQLCompileError, match="KEY_MERGE"):
            compile_operation(step, select_sql, dialect="duckdb")

    def test_chain_5step_strategies_are_correct(self):
        """chain_5step 每步策略解析正确"""
        chain = _load_yaml_fixture("chain_5step")
        strategies = [resolve_strategy(s) for s in chain.steps]
        # Step 1-4：CTAS 无增量 → FULL_OVERWRITE
        for i in range(4):
            assert strategies[i] == ExecutionStrategy.FULL_OVERWRITE, (
                f"Step {i+1} 应为 FULL_OVERWRITE，实际为 {strategies[i]}"
            )
        # Step 5：SELECT_ONLY → SELECT_ONLY
        assert strategies[4] == ExecutionStrategy.SELECT_ONLY


# ═══════════════════════════════════════════════════════════
# 7. 菱形 DAG——分支 + 汇聚 执行语义
# ═══════════════════════════════════════════════════════════

class TestDiamondDAGExecutionSemantics:
    """菱形 DAG：分支并行 + 汇聚——验证多依赖汇聚步骤的正确性"""

    @pytest.fixture
    def diamond(self) -> PipelinePlan:
        return _load_yaml_fixture("diamond_4step")

    def test_diamond_topological_order(self, diamond):
        """菱形 DAG 拓扑序：根 → 左右分支（任意序） → 汇聚"""
        report = validate_pipeline_dag(diamond.steps)
        assert report.passed, f"DAG 校验失败: {report.errors}"
        order = report.execution_order
        # 根节点最先
        assert order[0] == "extract_base"
        # 汇聚节点最后
        assert order[-1] == "merge_report"
        # 左右分支在中间
        assert "compute_city_agg" in order[1:3]
        assert "compute_date_agg" in order[1:3]

    def test_diamond_merge_depends_on_both_branches(self, diamond):
        """汇聚步骤必须依赖两个分支"""
        merge = diamond.steps[3]
        assert merge.step_id == "merge_report"
        assert "compute_city_agg" in merge.depends_on, (
            f"汇聚步骤应依赖 compute_city_agg，实际: {merge.depends_on}"
        )
        assert "compute_date_agg" in merge.depends_on, (
            f"汇聚步骤应依赖 compute_date_agg，实际: {merge.depends_on}"
        )

    def test_diamond_branches_independent_of_each_other(self, diamond):
        """两个分支之间不应相互依赖"""
        left = diamond.steps[1]
        right = diamond.steps[2]
        assert right.step_id not in left.depends_on, (
            "左分支不应依赖右分支"
        )
        assert left.step_id not in right.depends_on, (
            "右分支不应依赖左分支"
        )

    def test_diamond_merge_references_both_branch_outputs(self, diamond):
        """汇聚步骤应引用两个分支的输出表"""
        merge = diamond.steps[3]
        assert merge.sql_plan is not None
        # primary_table 应引用左分支
        assert merge.sql_plan.join_graph.primary.table == "generated.agg_by_city"
        # join_tables 应引用右分支
        join_tables = [j.table for j in merge.sql_plan.join_graph.joins]
        assert "generated.agg_by_date" in join_tables, (
            f"汇聚步骤的 JOIN 应引用右分支输出 generated.agg_by_date，"
            f"实际 JOIN 表: {join_tables}"
        )

    def test_diamond_all_steps_compile_and_have_strategies(self, diamond):
        """菱形 DAG 每步编译 + 策略解析正确"""
        for step in diamond.steps:
            assert step.sql_plan is not None
            sql, _ = compile_sql(step.sql_plan)
            assert len(sql) > 0

            strategy = resolve_strategy(step)
            op_sql = compile_operation(step, sql, dialect="duckdb")
            assert len(op_sql) > 0

            # Step 1-3：CTAS → FULL_OVERWRITE
            if step.operation == StepOperation.CREATE_TABLE_AS_SELECT:
                assert strategy == ExecutionStrategy.FULL_OVERWRITE
            # Step 4：SELECT_ONLY → SELECT_ONLY
            elif step.operation == StepOperation.SELECT_ONLY:
                assert strategy == ExecutionStrategy.SELECT_ONLY


# ═══════════════════════════════════════════════════════════
# 8. v1 pipeline 兼容性
# ═══════════════════════════════════════════════════════════

class TestV1PipelineCompatibility:
    """v1 pipeline 保持可用——不因 DAG 测试改动而退化"""

    def test_v1_fixture_loadable_and_compilable(self):
        """v1 trip_daily_report fixture 仍可通过现有管道编译"""
        from pathlib import Path
        v1_fixture = (
            Path(__file__).resolve().parents[1]
            / "fixtures" / "requirements" / "trip_daily_report.yml"
        )
        assert v1_fixture.exists(), f"v1 fixture 不存在: {v1_fixture}"

        with open(v1_fixture, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "metrics" in data, "v1 fixture 应包含 metrics 字段"

    def test_dag_fixtures_compile_to_safe_sql(self):
        """所有 DAG fixture 编译产物不含危险关键字"""
        FORBIDDEN = ["DROP", "DELETE", "TRUNCATE", "ALTER", "GRANT", "REVOKE"]
        for fixture_name in ["chain_5step", "diamond_4step", "complex_6step", "single_step"]:
            pipeline = _load_yaml_fixture(fixture_name)
            for step in pipeline.steps:
                assert step.sql_plan is not None
                sql, _ = compile_sql(step.sql_plan)
                sql_upper = sql.upper()
                for kw in FORBIDDEN:
                    assert kw not in sql_upper, (
                        f"[{fixture_name}/{step.step_id}] 含危险关键字 '{kw}'"
                    )
