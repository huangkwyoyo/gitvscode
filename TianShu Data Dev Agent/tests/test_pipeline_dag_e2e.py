"""
DAG 端到端编译测试

编译级（dry-run）端到端测试，覆盖 4 种 DAG 模式：
  - 链式（chain_5step）：5 步线性依赖
  - 菱形（diamond_4step）：扇出 + 扇入
  - 复杂（complex_6step）：多层依赖 + 多分支
  - 单步（single_step）：边界——最小 DAG

测试内容：
  1. YAML fixture → PipelinePlan IR 反序列化
  2. 每个步骤 compile_sql() 编译成功
  3. 编译产出的 SQL 字符串结构合法（关键字、表引用、列引用）
  4. 步骤间依赖表引用正确传递
  5. 安全黑名单关键字检查

不连接数据库，纯静态验证。
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
from scripts.pipeline.layer5_validate_pipeline import (
    validate_pipeline_dag,
    validate_operation_compliance,
    validate_pipeline,
)


# ═══════════════════════════════════════════════════════════
# 路径配置
# ═══════════════════════════════════════════════════════════

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "dag_e2e"

# ═══════════════════════════════════════════════════════════
# 安全黑名单——任何编译产出的 SQL 中不得出现这些关键字
# ═══════════════════════════════════════════════════════════

FORBIDDEN_SQL_KEYWORDS = ["DROP", "DELETE", "TRUNCATE", "ALTER", "GRANT", "REVOKE"]


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════

def _infer_filter_type(operator: str) -> FilterType:
    """根据运算符推断 FilterType 枚举值"""
    mapping = {
        "=": FilterType.EQUALS,
        "!=": FilterType.NOT_EQUALS,
        ">": FilterType.COMPARISON,
        "<": FilterType.COMPARISON,
        ">=": FilterType.COMPARISON,
        "<=": FilterType.COMPARISON,
        "BETWEEN": FilterType.DATE_RANGE,
        "IN": FilterType.IN_LIST,
    }
    return mapping.get(operator, FilterType.COMPARISON)


def _infer_source_layer(primary_table: str) -> str:
    """根据主表前缀推断 source_layer 值——G3 汇总表会跳过 GROUP BY"""
    if primary_table.startswith("gold."):
        return "g3"
    return "generated"


def _build_join_graph(primary_table: str, join_tables: list[dict] | None) -> JoinGraph:
    """
    从 YAML 中的 primary_table 和 join_tables 构建 JoinGraph

    primary_table: "gold.dws_daily_trip_summary"
    join_tables: [{table, alias, type, condition: {left, right}}, ...]
    """
    primary = JoinNode(
        table=primary_table,
        alias="t1",
        type="PRIMARY",
        condition=JoinCondition(left="", right=""),
        constraint_ref="",
    )

    joins: list[JoinNode] = []
    for jt in (join_tables or []):
        joins.append(JoinNode(
            table=jt["table"],
            alias=jt["alias"],
            type=jt["type"],
            condition=JoinCondition(
                left=jt["condition"]["left"],
                right=jt["condition"]["right"],
            ),
            constraint_ref="",
        ))

    return JoinGraph(primary=primary, joins=joins)


def _build_column_bindings(
    bindings: list[dict],
    primary_table: str,
) -> list[ColumnBinding]:
    """
    从 YAML 中的 column_bindings 构建 ColumnBinding 列表

    YAML 格式（简化）：
      - {column_name: "city_id", alias: "city_id", aggregation: "SUM"}
      - {column_name: "city_name", alias: "city_name", source_table: "gold.dim_city"}

    IR 格式：
      ColumnBinding(
        metric_name=alias,
        column_ref="{table}.{column_name}",  # 全限定列引用
        alias=alias,
        unit="",
        domain="test",
      )
    """
    result: list[ColumnBinding] = []
    for b in bindings:
        source = b.get("source_table", primary_table)
        aggregation = b.get("aggregation", "")
        column_name = b["column_name"]
        alias = b["alias"]

        # 构建 column_ref：{source_table}.{column_name}
        column_ref = f"{source}.{column_name}"

        # 如果有聚合函数，column_ref 前加聚合
        if aggregation:
            column_ref = f"{aggregation}({column_ref})"

        result.append(ColumnBinding(
            metric_name=alias,
            column_ref=column_ref,
            alias=alias,
            unit="",
            domain="test",
        ))
    return result


def _build_filter_bindings(
    filters: list[dict] | None,
    primary_table: str,
) -> list[FilterBinding]:
    """
    从 YAML 中的 filter_bindings 构建 FilterBinding 列表

    YAML 格式：
      - {column_name: "dt", operator: ">=", value: "2026-01-01"}

    IR 格式：
      FilterBinding(
        filter_type=FilterType.COMPARISON,
        column_ref="{primary_table}.{column_name}",
        operator=">=",
        value="2026-01-01",
      )
    """
    result: list[FilterBinding] = []
    for f in (filters or []):
        result.append(FilterBinding(
            filter_type=_infer_filter_type(f["operator"]),
            column_ref=f"{primary_table}.{f['column_name']}",
            operator=f["operator"],
            value=f["value"],
        ))
    return result


def _load_yaml_fixture(name: str) -> PipelinePlan:
    """
    从 YAML fixture 文件加载 PipelinePlan

    将简化的 YAML 格式转换为完整的 PipelinePlan IR 对象。
    fixture 是"输入数据"——YAML 中的简化字段由本函数映射到完整的 IR dataclass。
    """
    fixture_path = FIXTURE_DIR / f"{name}.yml"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture 文件不存在: {fixture_path}")

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    steps: list[PipelineStep] = []
    for step_data in data["steps"]:
        sp = step_data["sql_plan"]
        primary_table = sp["primary_table"]

        # 构建 JoinGraph
        join_graph = _build_join_graph(primary_table, sp.get("join_tables"))

        # 构建 SQLPlan
        sql_plan = SQLPlan(
            plan_id=f"test_{step_data['step_id']}",
            plan_name=step_data["step_name"],
            source_layer=_infer_source_layer(primary_table),
            domain="test",
            target_dialect=data.get("target_dialect", "duckdb"),
            join_graph=join_graph,
            column_bindings=_build_column_bindings(
                sp.get("column_bindings", []), primary_table
            ),
            filter_bindings=_build_filter_bindings(
                sp.get("filter_bindings"), primary_table
            ),
            group_by=sp.get("group_by", []),
        )

        # 构建 PipelineStep
        step = PipelineStep(
            step_id=step_data["step_id"],
            step_name=step_data["step_name"],
            operation=StepOperation(step_data["operation"]),
            target_table=step_data.get("target_table", ""),
            depends_on=step_data.get("depends_on", []),
            sql_plan=sql_plan,
        )
        steps.append(step)

    return PipelinePlan(
        pipeline_id=data["pipeline_id"],
        pipeline_name=data["pipeline_name"],
        target_dialect=data.get("target_dialect", "duckdb"),
        steps=steps,
    )


def _assert_sql_structure(sql: str, expected: dict):
    """
    声明式 SQL 结构断言

    expected dict 结构：
      {
        "must_contain": ["SELECT", "FROM", "WHERE"],        # 必须含有的 SQL 关键字
        "must_not_contain": ["DROP", "DELETE"],             # 禁止含有的关键字
        "tables": ["gold.dws_daily_trip_summary"],          # 必须引用的表名
        "columns": ["city_id", "trip_count"],               # 必须出现的列别名
        "filters": ["dt"],                                  # WHERE 中必须出现的列
      }
    """
    sql_upper = sql.upper()

    # 检查必须含有的关键字
    for keyword in expected.get("must_contain", []):
        assert keyword.upper() in sql_upper, (
            f"SQL 中缺少关键字 '{keyword}'\nSQL:\n{sql}"
        )

    # 检查禁止含有的关键字
    for keyword in expected.get("must_not_contain", []):
        assert keyword.upper() not in sql_upper, (
            f"SQL 中包含禁止关键字 '{keyword}'\nSQL:\n{sql}"
        )

    # 检查表名引用
    for table in expected.get("tables", []):
        assert table in sql, (
            f"SQL 中缺少表名引用 '{table}'\nSQL:\n{sql}"
        )

    # 检查列别名
    for column in expected.get("columns", []):
        assert column in sql, (
            f"SQL 中缺少列别名 '{column}'\nSQL:\n{sql}"
        )

    # 检查 WHERE 中的过滤列
    for filter_col in expected.get("filters", []):
        assert filter_col in sql, (
            f"SQL WHERE 中缺少过滤列 '{filter_col}'\nSQL:\n{sql}"
        )


# ═══════════════════════════════════════════════════════════
# 测试类 1：YAML Fixture 加载
# ═══════════════════════════════════════════════════════════

class TestYAMLFxtureLoading:
    """YAML fixture → PipelinePlan IR 反序列化测试"""

    def test_load_chain_fixture(self):
        """链式 DAG 应正确加载为 5 步 PipelinePlan"""
        pipeline = _load_yaml_fixture("chain_5step")
        assert pipeline.pipeline_id == "e2e_chain_5step"
        assert len(pipeline.steps) == 5

        # 验证拓扑序：步骤按依赖顺序排列
        step_ids = [s.step_id for s in pipeline.steps]
        assert step_ids == [
            "extract_trip",
            "aggregate_daily",
            "enrich_city",
            "tag_anomaly",
            "final_report",
        ]

        # 验证操作类型
        assert pipeline.steps[0].operation == StepOperation.CREATE_TABLE_AS_SELECT
        assert pipeline.steps[-1].operation == StepOperation.SELECT_ONLY

        # 验证 DAG 结构无环
        report = validate_pipeline_dag(pipeline.steps)
        assert report.passed, f"DAG 验证失败: {report.errors}"
        assert not report.has_cycle

    def test_load_diamond_fixture(self):
        """菱形 DAG 应正确加载为 4 步 PipelinePlan"""
        pipeline = _load_yaml_fixture("diamond_4step")
        assert pipeline.pipeline_id == "e2e_diamond_4step"
        assert len(pipeline.steps) == 4

        # 验证扇出结构：第 2、3 步都依赖第 1 步
        assert pipeline.steps[1].depends_on == ["extract_base"]
        assert pipeline.steps[2].depends_on == ["extract_base"]

        # 验证汇聚：第 4 步依赖两个分支
        assert set(pipeline.steps[3].depends_on) == {
            "compute_city_agg",
            "compute_date_agg",
        }

        # 验证 DAG 结构无环
        report = validate_pipeline_dag(pipeline.steps)
        assert report.passed, f"DAG 验证失败: {report.errors}"
        assert not report.has_cycle

    def test_load_complex_fixture(self):
        """复杂 DAG 应正确加载为 6 步 PipelinePlan"""
        pipeline = _load_yaml_fixture("complex_6step")
        assert pipeline.pipeline_id == "e2e_complex_6step"
        assert len(pipeline.steps) == 6

        # 验证 3 层依赖深度
        assert pipeline.steps[0].depends_on == []  # L1 无依赖
        assert pipeline.steps[1].depends_on == ["extract_raw"]  # L2
        assert pipeline.steps[2].depends_on == ["clean_and_filter"]  # L3

        # 验证 INSERT_OVERWRITE_PARTITION 操作
        insert_step = pipeline.steps[4]
        assert insert_step.operation == StepOperation.INSERT_OVERWRITE_PARTITION
        assert insert_step.target_table == "generated.report_partitioned"

        # 验证 CREATE_VIEW 操作
        view_step = pipeline.steps[5]
        assert view_step.operation == StepOperation.CREATE_VIEW
        assert view_step.target_table == "generated.v_report"

        # 验证 DAG 结构无环
        report = validate_pipeline_dag(pipeline.steps)
        assert report.passed, f"DAG 验证失败: {report.errors}"
        assert not report.has_cycle

    def test_load_single_step_fixture(self):
        """单步 fixture 应正确加载为 1 步 PipelinePlan（边界测试）"""
        pipeline = _load_yaml_fixture("single_step")
        assert pipeline.pipeline_id == "e2e_single_step"
        assert len(pipeline.steps) == 1

        step = pipeline.steps[0]
        assert step.step_id == "lone_view"
        assert step.operation == StepOperation.CREATE_VIEW
        assert step.depends_on == []

        # 单步 DAG 应通过验证
        report = validate_pipeline_dag(pipeline.steps)
        assert report.passed


# ═══════════════════════════════════════════════════════════
# 测试类 2：DAG 编译 Dry-Run
# ═══════════════════════════════════════════════════════════

class TestDAGCompileDryRun:
    """编译级 dry-run：验证所有步骤的 SQLPlan 能通过 compile_sql() 成功编译"""

    def test_chain_all_steps_compile(self):
        """链式 DAG 全部 5 个步骤应编译成功"""
        pipeline = _load_yaml_fixture("chain_5step")
        for step in pipeline.steps:
            assert step.sql_plan is not None, f"步骤 {step.step_id} 缺少 sql_plan"
            sql, params = compile_sql(step.sql_plan)
            assert sql, f"步骤 {step.step_id} 编译结果为空"
            assert isinstance(sql, str), f"步骤 {step.step_id} 编译结果不是字符串"

    def test_diamond_all_steps_compile(self):
        """菱形 DAG 全部 4 个步骤应编译成功"""
        pipeline = _load_yaml_fixture("diamond_4step")
        for step in pipeline.steps:
            assert step.sql_plan is not None, f"步骤 {step.step_id} 缺少 sql_plan"
            sql, params = compile_sql(step.sql_plan)
            assert sql, f"步骤 {step.step_id} 编译结果为空"

    def test_complex_all_steps_compile(self):
        """复杂 DAG 全部 6 个步骤应编译成功"""
        pipeline = _load_yaml_fixture("complex_6step")
        for step in pipeline.steps:
            assert step.sql_plan is not None, f"步骤 {step.step_id} 缺少 sql_plan"
            sql, params = compile_sql(step.sql_plan)
            assert sql, f"步骤 {step.step_id} 编译结果为空"

    def test_single_step_compiles(self):
        """单步 fixture 应编译成功"""
        pipeline = _load_yaml_fixture("single_step")
        step = pipeline.steps[0]
        assert step.sql_plan is not None
        sql, params = compile_sql(step.sql_plan)
        assert sql

    def test_dependency_table_reference_chain(self):
        """链式 DAG 中，下游步骤的 FROM 应引用上游步骤的 target_table"""
        pipeline = _load_yaml_fixture("chain_5step")

        # Step 2 (aggregate_daily) FROM 应引用 Step 1 的 target_table
        sql2, _ = compile_sql(pipeline.steps[1].sql_plan)
        assert "generated.tmp_trip_raw" in sql2, (
            f"Step 2 FROM 未引用上游 target_table\nSQL:\n{sql2}"
        )

        # Step 3 (enrich_city) FROM 应引用 Step 2 的 target_table
        sql3, _ = compile_sql(pipeline.steps[2].sql_plan)
        assert "generated.agg_trip_daily" in sql3, (
            f"Step 3 FROM 未引用上游 target_table\nSQL:\n{sql3}"
        )

        # Step 5 (final_report) FROM 应引用 Step 4 的 target_table
        sql5, _ = compile_sql(pipeline.steps[4].sql_plan)
        assert "generated.tagged_trip" in sql5, (
            f"Step 5 FROM 未引用上游 target_table\nSQL:\n{sql5}"
        )

    def test_diamond_branch_independence(self):
        """菱形 DAG 的两个分支不应互相引用对方中间表"""
        pipeline = _load_yaml_fixture("diamond_4step")
        sql_left, _ = compile_sql(pipeline.steps[1].sql_plan)  # compute_city_agg
        sql_right, _ = compile_sql(pipeline.steps[2].sql_plan)  # compute_date_agg

        # 左分支不应引用右分支的输出表
        assert "generated.agg_by_date" not in sql_left
        # 右分支不应引用左分支的输出表
        assert "generated.agg_by_city" not in sql_right

    def test_compile_error_on_missing_join_graph(self):
        """缺少 join_graph 的 SQLPlan 应抛出 SQLCompileError"""
        bad_plan = SQLPlan(
            plan_id="bad",
            plan_name="bad",
            source_layer="g3",
            domain="test",
        )
        with pytest.raises(SQLCompileError, match="join_graph"):
            compile_sql(bad_plan)

    def test_compile_error_on_invalid_plan(self):
        """is_valid=False 的 SQLPlan 应抛出 SQLCompileError"""
        bad_plan = SQLPlan(
            plan_id="bad",
            plan_name="bad",
            source_layer="g3",
            domain="test",
            is_valid=False,
            block_reason="测试用阻塞原因",
        )
        with pytest.raises(SQLCompileError, match="无效"):
            compile_sql(bad_plan)


# ═══════════════════════════════════════════════════════════
# 测试类 3：SQL 结构验证
# ═══════════════════════════════════════════════════════════

class TestSQLStructureValidation:
    """SQL 结构验证：编译产出必须包含正确的关键字和标识符"""

    # ── 链式 DAG 结构验证 ──

    def test_chain_step1_select_from_where(self):
        """链式 Step 1（简单提取）：SELECT + FROM + WHERE"""
        pipeline = _load_yaml_fixture("chain_5step")
        sql, _ = compile_sql(pipeline.steps[0].sql_plan)
        _assert_sql_structure(sql, {
            "must_contain": ["SELECT", "FROM", "WHERE"],
            "tables": ["gold.dws_daily_trip_summary"],
            "columns": ["city_id", "trip_count", "dt"],
            "filters": ["dt"],
        })

    def test_chain_step2_group_by_and_aggregation(self):
        """链式 Step 2（聚合）：SELECT + GROUP BY + SUM"""
        pipeline = _load_yaml_fixture("chain_5step")
        sql, _ = compile_sql(pipeline.steps[1].sql_plan)
        _assert_sql_structure(sql, {
            "must_contain": ["SELECT", "FROM", "GROUP BY", "SUM"],
            "tables": ["generated.tmp_trip_raw"],
            "columns": ["city_id", "dt", "daily_total"],
        })

    def test_chain_step3_join_clause(self):
        """链式 Step 3（JOIN）：SELECT + LEFT JOIN"""
        pipeline = _load_yaml_fixture("chain_5step")
        sql, _ = compile_sql(pipeline.steps[2].sql_plan)
        _assert_sql_structure(sql, {
            "must_contain": ["SELECT", "FROM", "JOIN"],
            "tables": ["generated.agg_trip_daily", "gold.dim_city"],
            "columns": ["city_id", "city_name", "dt", "daily_total"],
        })

    def test_chain_step4_simple_ctas_select(self):
        """链式 Step 4（标记）：SELECT + FROM（无 GROUP BY / JOIN）"""
        pipeline = _load_yaml_fixture("chain_5step")
        sql, _ = compile_sql(pipeline.steps[3].sql_plan)
        _assert_sql_structure(sql, {
            "must_contain": ["SELECT", "FROM"],
            "tables": ["generated.enriched_trip"],
            "columns": ["city_id", "city_name", "dt", "daily_total"],
        })

    def test_chain_step5_where_filter(self):
        """链式 Step 5（最终查询）：SELECT + WHERE 过滤"""
        pipeline = _load_yaml_fixture("chain_5step")
        sql, _ = compile_sql(pipeline.steps[4].sql_plan)
        _assert_sql_structure(sql, {
            "must_contain": ["SELECT", "FROM", "WHERE"],
            "tables": ["generated.tagged_trip"],
            "columns": ["城市", "日期", "行程量"],
            "filters": ["daily_total"],
        })

    # ── 菱形 DAG 结构验证 ──

    def test_diamond_branches_have_group_by(self):
        """菱形 DAG 的两个分支都应包含 GROUP BY"""
        pipeline = _load_yaml_fixture("diamond_4step")
        sql_left, _ = compile_sql(pipeline.steps[1].sql_plan)
        sql_right, _ = compile_sql(pipeline.steps[2].sql_plan)

        assert "GROUP BY" in sql_left.upper(), f"左分支缺少 GROUP BY\n{sql_left}"
        assert "GROUP BY" in sql_right.upper(), f"右分支缺少 GROUP BY\n{sql_right}"

    def test_diamond_merge_joins_both_branches(self):
        """菱形汇聚步骤应引用两个分支的输出表"""
        pipeline = _load_yaml_fixture("diamond_4step")
        sql, _ = compile_sql(pipeline.steps[3].sql_plan)

        assert "generated.agg_by_city" in sql, f"缺少左分支表引用\n{sql}"
        assert "generated.agg_by_date" in sql, f"缺少右分支表引用\n{sql}"
        assert "JOIN" in sql.upper(), f"汇聚步骤缺少 JOIN\n{sql}"

    # ── 复杂 DAG 结构验证 ──

    def test_complex_clean_step_has_where(self):
        """复杂 DAG Step 2（清洗）：SELECT + WHERE 过滤"""
        pipeline = _load_yaml_fixture("complex_6step")
        sql, _ = compile_sql(pipeline.steps[1].sql_plan)
        _assert_sql_structure(sql, {
            "must_contain": ["SELECT", "FROM", "WHERE"],
            "tables": ["generated.raw_data"],
            "filters": ["trip_count"],
        })

    def test_complex_city_stats_has_aggregations(self):
        """复杂 DAG Step 3（城市统计）：多聚合函数 + GROUP BY"""
        pipeline = _load_yaml_fixture("complex_6step")
        sql, _ = compile_sql(pipeline.steps[2].sql_plan)
        _assert_sql_structure(sql, {
            "must_contain": ["SELECT", "FROM", "GROUP BY", "AVG", "MAX"],
            "tables": ["generated.cleaned_data"],
            "columns": ["city_id", "avg_trip", "max_trip"],
        })

    def test_complex_date_stats_has_sum(self):
        """复杂 DAG Step 4（日期统计）：SUM + GROUP BY"""
        pipeline = _load_yaml_fixture("complex_6step")
        sql, _ = compile_sql(pipeline.steps[3].sql_plan)
        _assert_sql_structure(sql, {
            "must_contain": ["SELECT", "FROM", "GROUP BY", "SUM"],
            "tables": ["generated.cleaned_data"],
            "columns": ["dt", "daily_sum"],
        })

    def test_complex_final_view_has_join(self):
        """复杂 DAG Step 6（视图）：SELECT + LEFT JOIN"""
        pipeline = _load_yaml_fixture("complex_6step")
        sql, _ = compile_sql(pipeline.steps[5].sql_plan)
        _assert_sql_structure(sql, {
            "must_contain": ["SELECT", "FROM", "JOIN"],
            "tables": ["generated.city_stats", "generated.cleaned_data"],
            "columns": ["城市ID", "平均行程", "峰值行程"],
        })

    # ── 边界验证 ──

    def test_single_step_view_select(self):
        """单步 fixture（CREATE VIEW）：SELECT + FROM + WHERE"""
        pipeline = _load_yaml_fixture("single_step")
        sql, _ = compile_sql(pipeline.steps[0].sql_plan)
        _assert_sql_structure(sql, {
            "must_contain": ["SELECT", "FROM", "WHERE"],
            "tables": ["gold.dws_daily_trip_summary"],
            "columns": ["城市ID", "行程量", "日期"],
            "filters": ["dt"],
        })

    # ── 安全验证 ──

    @pytest.mark.parametrize("fixture_name", [
        "chain_5step",
        "diamond_4step",
        "complex_6step",
        "single_step",
    ])
    def test_no_dangerous_keywords_in_any_fixture(self, fixture_name):
        """所有 fixture 的全部步骤编译结果不得包含危险 SQL 关键字"""
        pipeline = _load_yaml_fixture(fixture_name)
        for step in pipeline.steps:
            sql, _ = compile_sql(step.sql_plan)
            sql_upper = sql.upper()
            for keyword in FORBIDDEN_SQL_KEYWORDS:
                assert keyword not in sql_upper, (
                    f"[{fixture_name}/{step.step_id}] SQL 中包含危险关键字 '{keyword}'\nSQL:\n{sql}"
                )


# ═══════════════════════════════════════════════════════════
# 测试类 4：DAG 校验 + 编译集成
# ═══════════════════════════════════════════════════════════

class TestDAGValidationIntegration:
    """DAG 校验与编译的集成测试"""

    def test_chain_pipeline_dag_and_compliance_both_pass(self):
        """链式 DAG 应通过 DAG 校验和安全层级合规检查"""
        pipeline = _load_yaml_fixture("chain_5step")
        dag_report, compliance_report = validate_pipeline(
            pipeline, safety_tier="pipeline"
        )
        assert dag_report.passed, f"DAG 校验失败: {dag_report.errors}"
        assert compliance_report.passed, f"合规检查失败: {compliance_report.errors}"

    def test_complex_pipeline_dag_and_compliance_both_pass(self):
        """复杂 DAG 应通过 DAG 校验和安全层级合规检查"""
        pipeline = _load_yaml_fixture("complex_6step")
        dag_report, compliance_report = validate_pipeline(
            pipeline, safety_tier="pipeline"
        )
        assert dag_report.passed, f"DAG 校验失败: {dag_report.errors}"
        assert compliance_report.passed, f"合规检查失败: {compliance_report.errors}"

    def test_cycle_in_modified_dag_detected(self):
        """手动插入环后，DAG 校验应检测到环"""
        pipeline = _load_yaml_fixture("chain_5step")
        # 修改 Step 1 使其依赖 Step 5——形成环
        pipeline.steps[0].depends_on.append("final_report")
        report = validate_pipeline_dag(pipeline.steps)
        assert not report.passed
        assert report.has_cycle

    def test_query_tier_blocks_ctas(self):
        """query 安全层级应阻止 CTAS 操作"""
        pipeline = _load_yaml_fixture("chain_5step")
        # chain 的前 4 步都是 CTAS——在 query 层级应该被阻止
        report = validate_operation_compliance(pipeline.steps, safety_tier="query")
        assert not report.passed
        assert len(report.errors) > 0
