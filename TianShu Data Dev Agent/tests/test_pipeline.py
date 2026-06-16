"""
Data Dev Agent 端到端测试

测试管道从 YAML 需求到产出物的完整链路。
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from scripts.pipeline.layer1_requirement import parse_requirement
from scripts.pipeline.layer2_intent import build_intent, Intent
from scripts.pipeline.layer3_ir import (
    SQLPlan, SQLCompileError,
    JoinGraph, JoinNode, JoinCondition,
    ColumnBinding, FilterBinding,
    # Phase 2 类型
    ExpressionRef, ExpressionOperand, ExpressionConfig,
    ExpressionType, OperandKind,
    ColumnRef, LiteralValue, LiteralType, OutputType,
    FilterType,
    # Phase 4 类型
    WindowFunctionDef, WindowFunctionName, WindowFunctionArg,
    FunctionArgKind, OrderByEntry, FrameType,
    # Phase 5 类型
    CTEDefinition,
)
from scripts.pipeline.layer3_plan import construct_sqlplan
from scripts.pipeline.layer4_generate import compile_sql
from scripts.pipeline.layer4_expression import (
    compile_expressions, _build_table_ref_map,
    _compile_expression,
)
from scripts.pipeline.layer4_window import compile_window_functions
from scripts.pipeline.layer4_cte import compile_cte_clause
from scripts.pipeline.layer4_operation import (
    compile_operation, resolve_strategy, ExecutionStrategy,
)
from scripts.pipeline.layer3_pipeline_plan import (
    PipelineStep, StepOperation, IncrementalIntent, PipelinePlan,
)
from scripts.pipeline.layer5_validate import validate_sql


class TestLayer4SQLCompile:
    """第4层测试：SQL 编译"""

    def test_g3_compile_no_errors(self):
        """G3 编译成功"""
        req = parse_requirement(
            PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
        )
        intent = build_intent(req)
        plan = construct_sqlplan(intent)
        sql, params = compile_sql(plan)
        assert "SELECT" in sql
        assert "FROM gold.dws_daily_trip_summary" in sql
        assert "trip_count" in sql
        assert len(params) == 2  # date range params

    def test_invalid_plan_raises(self):
        """无效 SQLPlan 抛出异常"""
        from scripts.pipeline.layer3_ir import SQLPlan
        invalid_plan = SQLPlan(
            plan_id="test",
            plan_name="test",
            source_layer="unavailable",
            domain="traffic",
            is_valid=False,
            block_reason="测试错误",
        )
        with pytest.raises(SQLCompileError):
            compile_sql(invalid_plan)


class TestLayer5Validation:
    """第5层测试：SQL 校验"""

    def test_valid_sql_passes(self):
        """合法 SQL 通过校验"""
        req = parse_requirement(
            PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
        )
        intent = build_intent(req)
        plan = construct_sqlplan(intent)
        sql, _ = compile_sql(plan)
        report = validate_sql(sql, plan)
        assert report.passed
        assert len(report.issues) == 0

    def test_forbidden_keyword_detected(self):
        """检测到禁止关键字"""
        req = parse_requirement(
            PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
        )
        intent = build_intent(req)
        plan = construct_sqlplan(intent)
        # 构造一个注入 SQL（模拟恶意输入）
        malicious_sql = "SELECT * FROM gold.dws_daily_trip_summary; DROP TABLE gold.fact_trips;"
        report = validate_sql(malicious_sql, plan)
        assert not report.passed


class TestColumnBindingTable:
    """ColumnBindingTable 完整性测试"""

    def test_all_10_metrics_registered(self):
        """确认 10 个已注册指标都在绑定表中"""
        from scripts.pipeline.column_binding import METRIC_BINDINGS, get_binding_by_metric_name

        expected = [
            "trip_count", "total_fare_amount", "total_tip_amount", "total_distance_miles",
            "parking_violation_count", "standard_fine_total",
            "crash_count", "persons_killed", "persons_injured",
            "tif_payment_amount",
        ]
        for name in expected:
            binding = get_binding_by_metric_name(name)
            assert binding is not None, f"指标 '{name}' 未在 ColumnBindingTable 中"

    def test_g3_bindings_have_table(self):
        """所有有 G3 的指标的 g3_table 非空"""
        from scripts.pipeline.column_binding import METRIC_BINDINGS
        for b in METRIC_BINDINGS:
            if b.g3_available:
                assert b.g3_table is not None, f"指标 '{b.metric_name}' G3 可用但 g3_table 为空"

    def test_g2_fallback_expressions(self):
        """G3 不可用的指标有 G2 表达式"""
        from scripts.pipeline.column_binding import METRIC_BINDINGS
        for b in METRIC_BINDINGS:
            if not b.g3_available:
                assert b.g2_expression is not None, f"指标 '{b.metric_name}' 无 G3 且无 G2 表达式"


# ═══════════════════════════════════════════════════════════
# Phase 3：表达式编译器测试
# ═══════════════════════════════════════════════════════════

# ── 测试用工厂函数 ──

def _make_expr(
    expr_type: ExpressionType,
    operands: list | None = None,
    config: ExpressionConfig | None = None,
    alias: str = "expr_result",
    output_type: OutputType = OutputType.STRING,
) -> ExpressionRef:
    """快速创建测试用 ExpressionRef"""
    return ExpressionRef(
        expr_type=expr_type,
        operands=operands or [],
        config=config or ExpressionConfig(),
        alias=alias,
        output_type=output_type,
    )


def _col_op(table_ref: str = "primary", column_name: str = "trip_count") -> ExpressionOperand:
    """创建列引用操作数"""
    return ExpressionOperand(
        kind=OperandKind.COLUMN_REF,
        column_ref=ColumnRef(table_ref=table_ref, column_name=column_name),
    )


def _lit_op(literal_type: LiteralType = LiteralType.STRING, value=None) -> ExpressionOperand:
    """创建字面量操作数"""
    return ExpressionOperand(
        kind=OperandKind.LITERAL,
        literal=LiteralValue(literal_type=literal_type, value=value),
    )


def _expr_ref_op(expr_alias: str) -> ExpressionOperand:
    """创建表达式引用操作数（用于嵌套）"""
    return ExpressionOperand(kind=OperandKind.EXPR_REF, expr_alias=expr_alias)


def _make_single_table_join_graph(
    table_name: str = "gold.test_table",
) -> JoinGraph:
    """快速创建单表 JoinGraph（用于表达式测试）"""
    return JoinGraph(
        primary=JoinNode(
            table=table_name,
            alias="t_test",
            type="",
            condition=JoinCondition(left="", right=""),
            constraint_ref="",
        ),
        joins=[],
    )


# ── 单元测试：基础设施函数 ──

class TestTableRefMap:
    """table_ref 映射表构建测试"""

    def test_single_table_map(self):
        """单表查询：table_ref 映射为全限定表名"""
        jg = _make_single_table_join_graph("gold.dws_test")
        ref_map = _build_table_ref_map(jg)
        assert ref_map['primary'] == 'gold.dws_test'

    def test_multi_table_map(self):
        """多表 JOIN：table_ref 映射为 SQL 别名"""
        jg = JoinGraph(
            primary=JoinNode(
                table="gold.fact_trips",
                alias="t_trips",
                type="",
                condition=JoinCondition(left="", right=""),
                constraint_ref="",
            ),
            joins=[
                JoinNode(
                    table="gold.dim_date",
                    alias="dim_date",
                    type="LEFT JOIN",
                    condition=JoinCondition(left="t_trips.date_key", right="dim_date.date_key"),
                    constraint_ref="",
                ),
            ],
        )
        ref_map = _build_table_ref_map(jg)
        assert ref_map['primary'] == 't_trips'


# ── 单元测试：LITERAL 表达式 ──

class TestLiteralExpression:
    """字面量表达式编译测试"""

    def test_literal_string(self):
        """字符串字面量——应被单引号包裹"""
        expr = _make_expr(
            ExpressionType.LITERAL,
            operands=[_lit_op(LiteralType.STRING, "hello")],
            alias="greeting",
        )
        result = _compile_expression(expr, {}, "duckdb", {"primary": "t1"})
        assert result == "'hello'"

    def test_literal_integer(self):
        """整数字面量——应输出裸数字"""
        expr = _make_expr(
            ExpressionType.LITERAL,
            operands=[_lit_op(LiteralType.INTEGER, 42)],
            alias="count",
            output_type=OutputType.INTEGER,
        )
        result = _compile_expression(expr, {}, "duckdb", {"primary": "t1"})
        assert result == "42"

    def test_literal_boolean_true(self):
        """布尔字面量——应输出 TRUE"""
        expr = _make_expr(
            ExpressionType.LITERAL,
            operands=[_lit_op(LiteralType.BOOLEAN, True)],
            alias="flag",
            output_type=OutputType.BOOLEAN,
        )
        result = _compile_expression(expr, {}, "duckdb", {"primary": "t1"})
        assert result == "TRUE"

    def test_literal_single_quote_escaped(self):
        """字符串内含单引号——应转义为 ''"""
        expr = _make_expr(
            ExpressionType.LITERAL,
            operands=[_lit_op(LiteralType.STRING, "it's")],
            alias="escaped",
        )
        result = _compile_expression(expr, {}, "duckdb", {"primary": "t1"})
        assert result == "'it''s'"


# ── 单元测试：COLUMN_REF 表达式 ──

class TestColumnRefExpression:
    """列引用表达式编译测试"""

    def test_column_ref_single_table(self):
        """单表查询：ColumnRef 映射为全限定表名.列名"""
        expr = _make_expr(
            ExpressionType.COLUMN_REF,
            operands=[_col_op("primary", "trip_count")],
            alias="col_ref",
        )
        result = _compile_expression(
            expr, {}, "duckdb",
            {"primary": "gold.dws_daily_trip_summary"}
        )
        assert result == "gold.dws_daily_trip_summary.trip_count"

    def test_column_ref_multi_table(self):
        """多表 JOIN：ColumnRef 映射为别名.列名"""
        expr = _make_expr(
            ExpressionType.COLUMN_REF,
            operands=[_col_op("primary", "zone_name")],
            alias="col_ref",
        )
        result = _compile_expression(expr, {}, "duckdb", {"primary": "t1"})
        assert result == "t1.zone_name"


# ── 单元测试：CONCAT 表达式 ──

class TestConcatExpression:
    """字符串拼接表达式测试"""

    def test_concat_two_strings_duckdb(self):
        """DuckDB：CONCAT('a', 'b')"""
        expr = _make_expr(
            ExpressionType.CONCAT,
            operands=[
                _lit_op(LiteralType.STRING, "Hello "),
                _lit_op(LiteralType.STRING, "World"),
            ],
            alias="greeting",
        )
        result = _compile_expression(expr, {}, "duckdb", {})
        assert result == "CONCAT('Hello ', 'World')"

    def test_concat_postgresql(self):
        """PostgreSQL：'a' || 'b'"""
        expr = _make_expr(
            ExpressionType.CONCAT,
            operands=[
                _lit_op(LiteralType.STRING, "A"),
                _lit_op(LiteralType.STRING, "B"),
            ],
            alias="joined",
        )
        result = _compile_expression(expr, {}, "postgresql", {})
        assert result == "'A' || 'B'"


# ── 单元测试：COALESCE 表达式 ──

class TestCoalesceExpression:
    """空值合并表达式测试"""

    def test_coalesce_two_values(self):
        """COALESCE(a, b)"""
        expr = _make_expr(
            ExpressionType.COALESCE,
            operands=[
                _col_op("primary", "zone_name"),
                _lit_op(LiteralType.STRING, "未知"),
            ],
            alias="zone_label",
        )
        result = _compile_expression(expr, {}, "duckdb", {"primary": "t1"})
        assert "COALESCE" in result
        assert "t1.zone_name" in result
        assert "'未知'" in result

    def test_coalesce_three_values(self):
        """COALESCE(a, b, c)"""
        expr = _make_expr(
            ExpressionType.COALESCE,
            operands=[
                _col_op("primary", "col1"),
                _col_op("primary", "col2"),
                _lit_op(LiteralType.INTEGER, 0),
            ],
            alias="fallback",
        )
        result = _compile_expression(expr, {}, "duckdb", {"primary": "t1"})
        assert result.startswith("COALESCE(")
        assert "t1.col1" in result
        assert "t1.col2" in result
        assert "0" in result


# ── 单元测试：CAST 表达式 ──

class TestCastExpression:
    """类型转换表达式测试"""

    def test_cast_duckdb(self):
        """DuckDB：CAST(col AS INTEGER)"""
        expr = _make_expr(
            ExpressionType.CAST,
            operands=[_col_op("primary", "trip_count")],
            config=ExpressionConfig(target_type="integer"),
            alias="count_int",
            output_type=OutputType.INTEGER,
        )
        result = _compile_expression(expr, {}, "duckdb", {"primary": "t1"})
        assert result == "CAST(t1.trip_count AS INTEGER)"

    def test_cast_postgresql(self):
        """PostgreSQL：col::integer"""
        expr = _make_expr(
            ExpressionType.CAST,
            operands=[_lit_op(LiteralType.FLOAT, 3.14)],
            config=ExpressionConfig(target_type="integer"),
            alias="casted",
        )
        result = _compile_expression(expr, {}, "postgresql", {})
        assert result == "3.14::integer"


# ── 单元测试：ARITHMETIC 表达式 ──

class TestArithmeticExpression:
    """算术表达式测试"""

    def test_arithmetic_add(self):
        """(a + b)"""
        expr = _make_expr(
            ExpressionType.ARITHMETIC,
            operands=[
                _col_op("primary", "amount"),
                _lit_op(LiteralType.INTEGER, 100),
            ],
            config=ExpressionConfig(op="+"),
            alias="total",
        )
        result = _compile_expression(expr, {}, "duckdb", {"primary": "t1"})
        assert result == "(t1.amount + 100)"

    def test_arithmetic_division(self):
        """(a / b)"""
        expr = _make_expr(
            ExpressionType.ARITHMETIC,
            operands=[
                _col_op("primary", "total"),
                _lit_op(LiteralType.INTEGER, 30),
            ],
            config=ExpressionConfig(op="/"),
            alias="monthly",
        )
        result = _compile_expression(expr, {}, "duckdb", {"primary": "t1"})
        assert result == "(t1.total / 30)"

    def test_arithmetic_with_nested_expr_ref(self):
        """嵌套表达式引用——EXPR_REF 操作数全量展开"""
        duration_expr = _make_expr(
            ExpressionType.DATE_DIFF,
            operands=[
                _col_op("primary", "start_date"),
                _col_op("primary", "end_date"),
            ],
            config=ExpressionConfig(unit="day"),
            alias="duration",
            output_type=OutputType.INTEGER,
        )
        monthly_expr = _make_expr(
            ExpressionType.ARITHMETIC,
            operands=[
                _expr_ref_op("duration"),
                _lit_op(LiteralType.INTEGER, 30),
            ],
            config=ExpressionConfig(op="/"),
            alias="monthly_duration",
            output_type=OutputType.DOUBLE,
        )
        expr_map = {"duration": duration_expr, "monthly_duration": monthly_expr}
        result = _compile_expression(
            monthly_expr, expr_map, "duckdb", {"primary": "t1"}
        )
        # 嵌套的 DATE_DIFF 应被展开在内
        assert "DATEDIFF" in result
        assert "/ 30" in result
        assert result.startswith("(")


# ── 单元测试：DATE_DIFF 表达式 ──

class TestDateDiffExpression:
    """日期差值表达式测试（含方言差异）"""

    def test_date_diff_duckdb(self):
        """DuckDB：DATEDIFF('day', start, end)"""
        expr = _make_expr(
            ExpressionType.DATE_DIFF,
            operands=[
                _col_op("primary", "start_date"),
                _col_op("primary", "end_date"),
            ],
            config=ExpressionConfig(unit="day"),
            alias="duration",
            output_type=OutputType.INTEGER,
        )
        result = _compile_expression(expr, {}, "duckdb", {"primary": "t1"})
        assert result == "DATEDIFF('day', t1.start_date, t1.end_date)"

    def test_date_diff_hive(self):
        """Hive：DATEDIFF(end, start)——参数顺序不同，无 unit 参数"""
        expr = _make_expr(
            ExpressionType.DATE_DIFF,
            operands=[
                _col_op("primary", "start_date"),
                _col_op("primary", "end_date"),
            ],
            config=ExpressionConfig(unit="day"),
            alias="duration",
            output_type=OutputType.INTEGER,
        )
        result = _compile_expression(expr, {}, "hive", {"primary": "t1"})
        # Hive：参数顺序 (end, start)
        assert result == "DATEDIFF(t1.end_date, t1.start_date)"

    def test_date_diff_postgresql(self):
        """PostgreSQL：(end - start)"""
        expr = _make_expr(
            ExpressionType.DATE_DIFF,
            operands=[
                _col_op("primary", "start_date"),
                _col_op("primary", "end_date"),
            ],
            config=ExpressionConfig(unit="day"),
            alias="duration",
            output_type=OutputType.INTEGER,
        )
        result = _compile_expression(expr, {}, "postgresql", {"primary": "t1"})
        assert result == "(t1.end_date - t1.start_date)"


# ── 单元测试：DATE_TRUNC 表达式 ──

class TestDateTruncExpression:
    """日期截断表达式测试"""

    def test_date_trunc_duckdb(self):
        """DuckDB：DATE_TRUNC('month', col)"""
        expr = _make_expr(
            ExpressionType.DATE_TRUNC,
            operands=[_col_op("primary", "trip_date")],
            config=ExpressionConfig(unit="month"),
            alias="trip_month",
            output_type=OutputType.DATE,
        )
        result = _compile_expression(expr, {}, "duckdb", {"primary": "t1"})
        assert result == "DATE_TRUNC('month', t1.trip_date)"


# ── 单元测试：DATE_FORMAT 表达式 ──

class TestDateFormatExpression:
    """日期格式化表达式测试"""

    def test_date_format_duckdb(self):
        """DuckDB：STRFTIME(col, '%Y-%m')"""
        expr = _make_expr(
            ExpressionType.DATE_FORMAT,
            operands=[_col_op("primary", "trip_date")],
            config=ExpressionConfig(format="%Y-%m"),
            alias="month_str",
            output_type=OutputType.STRING,
        )
        result = _compile_expression(expr, {}, "duckdb", {"primary": "t1"})
        assert result == "STRFTIME(t1.trip_date, '%Y-%m')"

    def test_date_format_hive(self):
        """Hive：DATE_FORMAT(col, 'yyyy-MM')"""
        expr = _make_expr(
            ExpressionType.DATE_FORMAT,
            operands=[_col_op("primary", "trip_date")],
            config=ExpressionConfig(format="yyyy-MM"),
            alias="month_str",
            output_type=OutputType.STRING,
        )
        result = _compile_expression(expr, {}, "hive", {"primary": "t1"})
        assert result == "DATE_FORMAT(t1.trip_date, 'yyyy-MM')"

    def test_date_format_postgresql(self):
        """PostgreSQL：TO_CHAR(col, 'YYYY-MM')"""
        expr = _make_expr(
            ExpressionType.DATE_FORMAT,
            operands=[_col_op("primary", "trip_date")],
            config=ExpressionConfig(format="YYYY-MM"),
            alias="month_str",
            output_type=OutputType.STRING,
        )
        result = _compile_expression(expr, {}, "postgresql", {"primary": "t1"})
        assert result == "TO_CHAR(t1.trip_date, 'YYYY-MM')"


# ── 单元测试：CASE WHEN 表达式 ──

class TestConditionalExpression:
    """CASE WHEN 条件表达式测试"""

    def test_conditional_case_when(self):
        """基本 CASE WHEN 结构"""
        expr = _make_expr(
            ExpressionType.CONDITIONAL,
            operands=[],
            config=ExpressionConfig(
                when_clauses=[
                    {"condition": "t1.amount > 1000", "result": "'高'"},
                    {"condition": "t1.amount > 100", "result": "'中'"},
                ],
                else_value="'低'",
            ),
            alias="level",
            output_type=OutputType.STRING,
        )
        result = _compile_expression(expr, {}, "duckdb", {"primary": "t1"})
        assert "CASE" in result
        assert "WHEN t1.amount > 1000 THEN '高'" in result
        assert "WHEN t1.amount > 100 THEN '中'" in result
        assert "ELSE '低'" in result
        assert "END" in result


# ── 集成测试：表达式编译到 SELECT 中 ──

class TestExpressionSelectIntegration:
    """表达式在 SELECT 子句中的集成测试"""

    def test_expressions_appear_in_select(self):
        """编译生成的 SQL 应包含表达式列"""
        jg = JoinGraph(
            primary=JoinNode(
                table="gold.test",
                alias="t_test",
                type="",
                condition=JoinCondition(left="", right=""),
                constraint_ref="",
            ),
            joins=[],
        )
        plan = SQLPlan(
            plan_id="test_expr", plan_name="test",
            source_layer="g3", domain="test",
            join_graph=jg,
            expression_refs=[
                _make_expr(
                    ExpressionType.DATE_DIFF,
                    operands=[
                        _col_op("primary", "start_date"),
                        _col_op("primary", "end_date"),
                    ],
                    config=ExpressionConfig(unit="day"),
                    alias="duration",
                    output_type=OutputType.INTEGER,
                ),
            ],
            column_bindings=[
                ColumnBinding(
                    metric_name="m1",
                    column_ref="gold.test.col1",
                    alias="metric1",
                    unit="次",
                    domain="test",
                ),
            ],
        )
        sql, params = compile_sql(plan)
        # 表达式应出现在 SELECT 列表中
        assert "DATEDIFF" in sql
        assert '"duration"' in sql
        # 指标列应在表达式之后
        assert '"metric1"' in sql
        # 表达式应在指标列之前（维度列之后）
        dur_pos = sql.index("duration")
        metric_pos = sql.index("metric1")
        assert dur_pos < metric_pos, "表达式应排在指标列之前"

    def test_multiple_expressions_in_select(self):
        """多个表达式都应出现在 SELECT 中"""
        jg = _make_single_table_join_graph("gold.test")
        plan = SQLPlan(
            plan_id="test_multi_expr", plan_name="test",
            source_layer="g3", domain="test",
            join_graph=jg,
            expression_refs=[
                _make_expr(
                    ExpressionType.DATE_DIFF,
                    operands=[
                        _col_op("primary", "start"),
                        _col_op("primary", "end"),
                    ],
                    config=ExpressionConfig(unit="day"),
                    alias="duration",
                    output_type=OutputType.INTEGER,
                ),
                _make_expr(
                    ExpressionType.COALESCE,
                    operands=[
                        _col_op("primary", "zone"),
                        _lit_op(LiteralType.STRING, "未知"),
                    ],
                    alias="zone_label",
                    output_type=OutputType.STRING,
                ),
            ],
            column_bindings=[
                ColumnBinding(
                    metric_name="m1",
                    column_ref="gold.test.col1",
                    alias="metric1",
                    unit="次",
                    domain="test",
                ),
            ],
        )
        sql, params = compile_sql(plan)
        assert '"duration"' in sql
        assert 'COALESCE' in sql
        assert '"zone_label"' in sql
        assert '"metric1"' in sql

    def test_no_expression_refs_still_works(self):
        """没有 expression_refs 的 SQLPlan 应正常编译（向后兼容）"""
        jg = _make_single_table_join_graph("gold.test")
        plan = SQLPlan(
            plan_id="test_no_expr", plan_name="test",
            source_layer="g3", domain="test",
            join_graph=jg,
            expression_refs=[],  # 空列表
            column_bindings=[
                ColumnBinding(
                    metric_name="m1",
                    column_ref="gold.test.col1",
                    alias="metric1",
                    unit="次",
                    domain="test",
                ),
            ],
        )
        sql, params = compile_sql(plan)
        assert "SELECT" in sql
        assert '"metric1"' in sql
        # 不应有表达式相关内容
        assert "DATEDIFF" not in sql


# ── 单元测试：compile_expressions 批量编译 ──

class TestCompileExpressionsBatch:
    """批量表达式编译测试"""

    def test_compile_multiple_expressions(self):
        """批量编译多个表达式，返回对应数量的 SQL 片段"""
        exprs = [
            _make_expr(
                ExpressionType.LITERAL,
                operands=[_lit_op(LiteralType.INTEGER, 1)],
                alias="one",
            ),
            _make_expr(
                ExpressionType.LITERAL,
                operands=[_lit_op(LiteralType.INTEGER, 2)],
                alias="two",
            ),
        ]
        results = compile_expressions(exprs, "duckdb", {})
        assert len(results) == 2
        assert results[0] == "1"
        assert results[1] == "2"

    def test_duplicate_alias_raises(self):
        """重复的别名应抛出 SQLCompileError"""
        exprs = [
            _make_expr(
                ExpressionType.LITERAL,
                operands=[_lit_op(LiteralType.INTEGER, 1)],
                alias="same_name",
            ),
            _make_expr(
                ExpressionType.LITERAL,
                operands=[_lit_op(LiteralType.INTEGER, 2)],
                alias="same_name",  # 重复！
            ),
        ]
        with pytest.raises(SQLCompileError, match="重复的表达式别名"):
            compile_expressions(exprs, "duckdb", {})

    def test_missing_alias_raises(self):
        """缺少 alias 的表达式应抛出 SQLCompileError"""
        exprs = [
            _make_expr(
                ExpressionType.LITERAL,
                operands=[_lit_op(LiteralType.INTEGER, 1)],
                alias="",  # 空 alias
            ),
        ]
        with pytest.raises(SQLCompileError, match="缺少 alias"):
            compile_expressions(exprs, "duckdb", {})


# ═══════════════════════════════════════════════════════════
# Phase 4：窗口函数编译器测试
# ═══════════════════════════════════════════════════════════

# ── 测试用工厂函数 ──

def _make_wf(
    func_name: WindowFunctionName,
    args: list | None = None,
    partition_by: list | None = None,
    order_by: list | None = None,
    alias: str = "wf_result",
    frame_start: str = "",
    frame_end: str = "",
    frame_type: FrameType = FrameType.ROWS,
) -> WindowFunctionDef:
    """快速创建测试用 WindowFunctionDef"""
    return WindowFunctionDef(
        func_name=func_name,
        args=args or [],
        partition_by=partition_by or [],
        order_by=order_by or [],
        alias=alias,
        frame_start=frame_start,
        frame_end=frame_end,
        frame_type=frame_type,
    )


def _wf_col_arg(table_ref: str = "primary", column_name: str = "trip_count") -> WindowFunctionArg:
    """创建窗口函数列引用参数"""
    return WindowFunctionArg(
        kind=FunctionArgKind.COLUMN,
        column_ref=ColumnRef(table_ref=table_ref, column_name=column_name),
    )


def _wf_lit_arg(literal_type: LiteralType = LiteralType.INTEGER, value=None) -> WindowFunctionArg:
    """创建窗口函数字面量参数"""
    return WindowFunctionArg(
        kind=FunctionArgKind.LITERAL,
        literal=LiteralValue(literal_type=literal_type, value=value),
    )


def _wf_order_by(col_name: str = "trip_count", direction: str = "DESC") -> OrderByEntry:
    """创建窗口函数排序项"""
    return OrderByEntry(
        column_ref=ColumnRef(table_ref="primary", column_name=col_name),
        direction=direction,
    )


# ── 单元测试：基本窗口函数编译 ──

class TestWindowFunctionCompile:
    """窗口函数编译器——各类型函数编译测试"""

    TABLE_MAP = _build_table_ref_map(_make_single_table_join_graph())

    def test_row_number(self):
        """ROW_NUMBER() OVER (ORDER BY col DESC)"""
        wf = _make_wf(
            WindowFunctionName.ROW_NUMBER,
            order_by=[_wf_order_by("trip_count", "DESC")],
            alias="row_num",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert len(results) == 1
        assert "ROW_NUMBER()" in results[0]
        assert "OVER" in results[0]
        assert "ORDER BY" in results[0]
        assert "trip_count DESC" in results[0]

    def test_rank(self):
        """RANK() OVER (PARTITION BY col ORDER BY col)"""
        wf = _make_wf(
            WindowFunctionName.RANK,
            partition_by=[ColumnRef("primary", "zone_name")],
            order_by=[_wf_order_by("trip_count", "DESC")],
            alias="rank_num",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert "RANK()" in results[0]
        assert "PARTITION BY" in results[0]
        assert "zone_name" in results[0]

    def test_dense_rank(self):
        """DENSE_RANK() OVER (ORDER BY col)"""
        wf = _make_wf(
            WindowFunctionName.DENSE_RANK,
            order_by=[_wf_order_by("total_fare", "DESC")],
            alias="dr",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert "DENSE_RANK()" in results[0]

    def test_lead_basic(self):
        """LEAD(col, 1) OVER (ORDER BY col)——向前偏移"""
        wf = _make_wf(
            WindowFunctionName.LEAD,
            args=[_wf_col_arg("primary", "crash_date"), _wf_lit_arg(LiteralType.INTEGER, 1)],
            order_by=[_wf_order_by("crash_date", "ASC")],
            alias="next_date",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert "LEAD(" in results[0]
        assert "crash_date" in results[0]
        assert "1" in results[0]
        assert "ORDER BY" in results[0]

    def test_lead_with_default(self):
        """LEAD(col, 1, 'N/A') OVER (...)——带默认值的向前偏移"""
        wf = _make_wf(
            WindowFunctionName.LEAD,
            args=[
                _wf_col_arg("primary", "crash_date"),
                _wf_lit_arg(LiteralType.INTEGER, 1),
                _wf_lit_arg(LiteralType.STRING, "N/A"),
            ],
            order_by=[_wf_order_by("crash_date", "ASC")],
            alias="next_date_default",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert "'N/A'" in results[0]

    def test_lag_basic(self):
        """LAG(col, 1) OVER (ORDER BY col)——向后偏移"""
        wf = _make_wf(
            WindowFunctionName.LAG,
            args=[_wf_col_arg("primary", "crash_date"), _wf_lit_arg(LiteralType.INTEGER, 1)],
            order_by=[_wf_order_by("crash_date", "ASC")],
            alias="prev_date",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert "LAG(" in results[0]

    def test_count_all(self):
        """COUNT(col) OVER (PARTITION BY col)"""
        wf = _make_wf(
            WindowFunctionName.COUNT,
            args=[_wf_col_arg("primary", "trip_count")],
            partition_by=[ColumnRef("primary", "zone_name")],
            alias="cnt",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert "COUNT(" in results[0]
        assert "PARTITION BY" in results[0]

    def test_sum(self):
        """SUM(col) OVER (PARTITION BY col ORDER BY col)"""
        wf = _make_wf(
            WindowFunctionName.SUM,
            args=[_wf_col_arg("primary", "total_fare_amount")],
            partition_by=[ColumnRef("primary", "zone_name")],
            order_by=[_wf_order_by("trip_date", "ASC")],
            alias="running_total",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert "SUM(" in results[0]
        assert "PARTITION BY" in results[0]
        assert "ORDER BY" in results[0]

    def test_avg(self):
        """AVG(col) OVER (PARTITION BY col)"""
        wf = _make_wf(
            WindowFunctionName.AVG,
            args=[_wf_col_arg("primary", "trip_count")],
            partition_by=[ColumnRef("primary", "zone_name")],
            alias="avg_trips",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert "AVG(" in results[0]

    def test_min_max(self):
        """MIN/MAX(col) OVER (PARTITION BY col)"""
        wf_min = _make_wf(
            WindowFunctionName.MIN,
            args=[_wf_col_arg("primary", "trip_count")],
            partition_by=[ColumnRef("primary", "zone_name")],
            alias="min_trips",
        )
        wf_max = _make_wf(
            WindowFunctionName.MAX,
            args=[_wf_col_arg("primary", "trip_count")],
            partition_by=[ColumnRef("primary", "zone_name")],
            alias="max_trips",
        )
        results = compile_window_functions([wf_min, wf_max], "duckdb", self.TABLE_MAP)
        assert "MIN(" in results[0]
        assert "MAX(" in results[1]

    def test_first_value(self):
        """FIRST_VALUE(col) OVER (PARTITION BY col ORDER BY col)"""
        wf = _make_wf(
            WindowFunctionName.FIRST_VALUE,
            args=[_wf_col_arg("primary", "crash_count")],
            partition_by=[ColumnRef("primary", "zone_name")],
            order_by=[_wf_order_by("crash_date", "ASC")],
            alias="first_crash",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert "FIRST_VALUE(" in results[0]

    def test_last_value(self):
        """LAST_VALUE(col) OVER (PARTITION BY col ORDER BY col)"""
        wf = _make_wf(
            WindowFunctionName.LAST_VALUE,
            args=[_wf_col_arg("primary", "crash_count")],
            partition_by=[ColumnRef("primary", "zone_name")],
            order_by=[_wf_order_by("crash_date", "ASC")],
            alias="last_crash",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert "LAST_VALUE(" in results[0]


# ── 单元测试：OVER 子句组合 ──

class TestWindowFunctionOverClause:
    """窗口函数编译器——OVER 子句各部分测试"""

    TABLE_MAP = _build_table_ref_map(_make_single_table_join_graph())

    def test_over_with_frame_clause(self):
        """带窗口帧的 OVER 子句——ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING"""
        wf = _make_wf(
            WindowFunctionName.SUM,
            args=[_wf_col_arg("primary", "trip_count")],
            order_by=[_wf_order_by("trip_date", "ASC")],
            frame_start="1 PRECEDING",
            frame_end="1 FOLLOWING",
            frame_type=FrameType.ROWS,
            alias="rolling_sum",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert "ROWS BETWEEN" in results[0]
        assert "1 PRECEDING" in results[0]
        assert "1 FOLLOWING" in results[0]

    def test_over_unbounded_preceding(self):
        """无边界前导——ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW"""
        wf = _make_wf(
            WindowFunctionName.SUM,
            args=[_wf_col_arg("primary", "trip_count")],
            order_by=[_wf_order_by("trip_date", "ASC")],
            frame_start="UNBOUNDED PRECEDING",
            frame_type=FrameType.ROWS,
            alias="cumsum",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert "UNBOUNDED PRECEDING" in results[0]
        assert "CURRENT ROW" in results[0]

    def test_bare_over(self):
        """裸 OVER ()——无 PARTITION BY、无 ORDER BY、无帧子句"""
        wf = _make_wf(
            WindowFunctionName.ROW_NUMBER,
            alias="bare_rn",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert "OVER ()" in results[0]
        assert "PARTITION BY" not in results[0]

    def test_multi_column_partition_by(self):
        """多列 PARTITION BY——PARTITION BY col1, col2"""
        wf = _make_wf(
            WindowFunctionName.ROW_NUMBER,
            partition_by=[
                ColumnRef("primary", "zone_name"),
                ColumnRef("primary", "borough"),
            ],
            order_by=[_wf_order_by("trip_count", "DESC")],
            alias="rn_multi",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert "PARTITION BY" in results[0]
        assert "zone_name" in results[0]
        assert "borough" in results[0]

    def test_multi_column_order_by(self):
        """多列 ORDER BY——ORDER BY col1 ASC, col2 DESC"""
        wf = _make_wf(
            WindowFunctionName.ROW_NUMBER,
            order_by=[
                _wf_order_by("zone_name", "ASC"),
                _wf_order_by("trip_count", "DESC"),
            ],
            alias="rn_multi_ord",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert "ORDER BY" in results[0]
        assert "zone_name ASC" in results[0]
        assert "trip_count DESC" in results[0]

    def test_range_frame_type(self):
        """RANGE 帧类型——RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW"""
        wf = _make_wf(
            WindowFunctionName.COUNT,
            args=[_wf_col_arg("primary", "trip_count")],
            order_by=[_wf_order_by("trip_date", "ASC")],
            frame_start="UNBOUNDED PRECEDING",
            frame_type=FrameType.RANGE,
            alias="range_cnt",
        )
        results = compile_window_functions([wf], "duckdb", self.TABLE_MAP)
        assert "RANGE BETWEEN" in results[0]


# ── 集成测试：窗口函数在 SELECT 中的表现 ──

class TestWindowFunctionSelectIntegration:
    """窗口函数集成到 SELECT 子句的端到端测试"""

    def test_select_with_window_function(self):
        """包含窗口函数的完整 SELECT 编译"""
        req = parse_requirement(
            PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
        )
        intent = build_intent(req)
        plan = construct_sqlplan(intent)

        # 注入测试用窗口函数
        plan.window_functions = [
            _make_wf(
                WindowFunctionName.ROW_NUMBER,
                partition_by=[ColumnRef("primary", "trip_count")],
                order_by=[_wf_order_by("trip_count", "DESC")],
                alias="row_num",
            ),
        ]
        # 窗口函数编译需要 table_ref_map——让 compile_sql 构建
        sql, params = compile_sql(plan)
        assert "ROW_NUMBER()" in sql
        assert "OVER" in sql
        assert 'AS "row_num"' in sql
        # 指标列也应存在
        assert "trip_count" in sql

    def test_multiple_window_functions_in_select(self):
        """SELECT 中包含多个窗口函数"""
        req = parse_requirement(
            PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
        )
        intent = build_intent(req)
        plan = construct_sqlplan(intent)

        plan.window_functions = [
            _make_wf(
                WindowFunctionName.ROW_NUMBER,
                order_by=[_wf_order_by("trip_count", "DESC")],
                alias="row_num",
            ),
            _make_wf(
                WindowFunctionName.LEAD,
                args=[_wf_col_arg("primary", "trip_count"), _wf_lit_arg(LiteralType.INTEGER, 1)],
                order_by=[_wf_order_by("trip_date", "ASC")],
                alias="next_trips",
            ),
        ]
        sql, params = compile_sql(plan)
        assert 'AS "row_num"' in sql
        assert 'AS "next_trips"' in sql
        assert "LEAD(" in sql

    def test_empty_window_functions_backward_compatible(self):
        """空窗口函数列表——向后兼容（不应影响现有输出）"""
        req = parse_requirement(
            PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
        )
        intent = build_intent(req)
        plan = construct_sqlplan(intent)
        # plan.window_functions 默认为空列表
        sql, params = compile_sql(plan)
        assert "OVER" not in sql  # 无窗口函数，不应出现 OVER 关键字

    def test_duplicate_alias_raises(self):
        """重复的窗口函数别名应抛出 SQLCompileError"""
        wfs = [
            _make_wf(WindowFunctionName.ROW_NUMBER, alias="same_name"),
            _make_wf(WindowFunctionName.RANK, alias="same_name"),
        ]
        with pytest.raises(SQLCompileError, match="重复的窗口函数别名"):
            compile_window_functions(wfs, "duckdb", _build_table_ref_map(_make_single_table_join_graph()))

    def test_missing_alias_raises(self):
        """缺少 alias 的窗口函数应抛出 SQLCompileError"""
        wfs = [
            _make_wf(WindowFunctionName.ROW_NUMBER, alias=""),
        ]
        with pytest.raises(SQLCompileError, match="缺少 alias"):
            compile_window_functions(wfs, "duckdb", _build_table_ref_map(_make_single_table_join_graph()))

    def test_empty_list_returns_empty(self):
        """空列表返回空列表"""
        results = compile_window_functions([], "duckdb", {})
        assert results == []

    def test_dialect_fallback_to_duckdb(self):
        """未注册方言 fallback 到 DuckDB 实现"""
        wf = _make_wf(
            WindowFunctionName.ROW_NUMBER,
            order_by=[_wf_order_by("trip_count", "DESC")],
            alias="rn",
        )
        # "mysql" 未注册——应 fallback 到 DuckDB
        results = compile_window_functions([wf], "mysql", self.TABLE_MAP if hasattr(self, 'TABLE_MAP') else _build_table_ref_map(_make_single_table_join_graph()))
        assert "ROW_NUMBER()" in results[0]

    # 为该测试单独设置 TABLE_MAP
    TABLE_MAP = _build_table_ref_map(_make_single_table_join_graph())


# ═══════════════════════════════════════════════════════════
# Phase 5：CTE 编译器测试
# ═══════════════════════════════════════════════════════════

# ── 测试用工厂函数 ──

def _make_simple_sqlplan(
    table_name: str = "gold.test_table",
    col_name: str = "col_a",
    col_alias: str = "测试列",
    source_layer: str = "g3",
    domain: str = "traffic",
) -> SQLPlan:
    """快速创建测试用 SQLPlan——用于 CTE 体的嵌套编译"""
    jg = _make_single_table_join_graph(table_name)
    return SQLPlan(
        plan_id="test_cte_body",
        plan_name="cte_body",
        source_layer=source_layer,
        domain=domain,
        join_graph=jg,
        column_bindings=[
            ColumnBinding(
                metric_name="test_metric",
                column_ref=f"{table_name}.{col_name}",
                alias=col_alias,
                unit="次",
                domain=domain,
            ),
        ],
        is_valid=True,
    )


def _make_cte(
    cte_name: str = "stage_1",
    sql_plan: SQLPlan | None = None,
) -> CTEDefinition:
    """快速创建测试用 CTEDefinition"""
    return CTEDefinition(
        cte_name=cte_name,
        sql_plan=sql_plan or _make_simple_sqlplan(),
    )


# ── 单元测试：CTE 基本编译 ──

class TestCTECompile:
    """CTE 编译器——基本编译测试"""

    def test_single_cte(self):
        """单个 CTE 编译——WITH stage_1 AS (SELECT ...)"""
        cte = _make_cte("stage_1")
        clause, params = compile_cte_clause([cte], "duckdb", compile_sql)
        assert "WITH" in clause
        assert "stage_1 AS (" in clause
        assert "SELECT" in clause
        assert "测试列" in clause

    def test_multiple_ctes(self):
        """多个 CTE 编译——逗号分隔的多个 WITH 子句"""
        cte1 = _make_cte("stage_1", _make_simple_sqlplan(table_name="gold.fact_trips", col_name="trip_count", col_alias="行程量"))
        cte2 = _make_cte("stage_2", _make_simple_sqlplan(table_name="stage_1", col_name="行程量", col_alias="行程量2"))
        clause, params = compile_cte_clause([cte1, cte2], "duckdb", compile_sql)
        assert "stage_1 AS (" in clause
        assert "stage_2 AS (" in clause
        assert clause.index("stage_1") < clause.index("stage_2")  # 顺序保持

    def test_cte_from_cte_reference(self):
        """CTE 引用前一个 CTE 作为数据源——FROM stage_1"""
        cte1 = _make_cte("stage_1", _make_simple_sqlplan(table_name="gold.fact_trips", col_name="trip_count", col_alias="行程量"))
        # stage_2 的 FROM 表是 stage_1（CTE 引用）
        cte2 = _make_cte("stage_2", _make_simple_sqlplan(table_name="stage_1", col_name="行程量", col_alias="行程量_ranked"))
        clause, params = compile_cte_clause([cte1, cte2], "duckdb", compile_sql)
        assert "FROM stage_1" in clause

    def test_empty_list_returns_empty(self):
        """空 CTE 列表返回空字符串和空参数"""
        clause, params = compile_cte_clause([], "duckdb", compile_sql)
        assert clause == ""
        assert params == []

    def test_cte_body_with_where(self):
        """CTE 体包含 WHERE 子句——参数化查询"""
        from scripts.pipeline.layer3_ir import FilterType
        jg = _make_single_table_join_graph("gold.fact_trips")
        plan = SQLPlan(
            plan_id="test_cte_filtered",
            plan_name="filtered_cte",
            source_layer="g2",
            domain="traffic",
            join_graph=jg,
            column_bindings=[
                ColumnBinding(
                    metric_name="trip_count",
                    column_ref="gold.fact_trips.trip_count",
                    alias="行程量",
                    unit="次",
                    domain="traffic",
                ),
            ],
            filter_bindings=[
                FilterBinding(
                    filter_type=FilterType.DATE_RANGE,
                    column_ref="gold.fact_trips.pickup_date",
                    operator="BETWEEN",
                    value=["2026-01-01", "2026-01-31"],
                ),
            ],
            is_valid=True,
        )
        cte = _make_cte("filtered_stage", plan)
        clause, params = compile_cte_clause([cte], "duckdb", compile_sql)
        assert "WHERE" in clause
        assert "BETWEEN ? AND ?" in clause
        assert len(params) == 2
        assert params == ["2026-01-01", "2026-01-31"]


# ── 单元测试：C4 约束 ──

class TestCTERecursionConstraint:
    """CTE 递归深度约束——C4 硬限制"""

    def test_no_nested_ctes_allowed(self):
        """CTE 体内不允许嵌套 CTE——应抛出 SQLCompileError"""
        # 构造一个 CTE，其 sql_plan 包含自己的 cte_definitions
        inner_cte = _make_cte("inner_cte")
        inner_plan = _make_simple_sqlplan()
        inner_plan.cte_definitions = [inner_cte]  # 违反 C4 约束！

        outer_cte = CTEDefinition(
            cte_name="outer_cte",
            sql_plan=inner_plan,
        )
        with pytest.raises(SQLCompileError, match="递归深度约束"):
            compile_cte_clause([outer_cte], "duckdb", compile_sql)

    def test_missing_sql_plan_raises(self):
        """缺少 sql_plan 的 CTE 应抛出 SQLCompileError"""
        bad_cte = CTEDefinition(cte_name="bad_cte", sql_plan=None)
        with pytest.raises(SQLCompileError, match="缺少 sql_plan"):
            compile_cte_clause([bad_cte], "duckdb", compile_sql)

    def test_params_propagated_from_nested_plan(self):
        """CTE 体的参数应传递到调用方"""
        from scripts.pipeline.layer3_ir import FilterType
        jg = _make_single_table_join_graph("gold.fact_trips")
        plan = SQLPlan(
            plan_id="test_params",
            plan_name="with_params",
            source_layer="g2",
            domain="traffic",
            join_graph=jg,
            column_bindings=[
                ColumnBinding(
                    metric_name="trip_count",
                    column_ref="gold.fact_trips.trip_count",
                    alias="行程量",
                    unit="次",
                    domain="traffic",
                ),
            ],
            filter_bindings=[
                FilterBinding(
                    filter_type=FilterType.DATE_RANGE,
                    column_ref="gold.fact_trips.pickup_date",
                    operator="BETWEEN",
                    value=["2026-01-01", "2026-03-31"],
                ),
            ],
            is_valid=True,
        )
        cte = _make_cte("param_stage", plan)
        clause, params = compile_cte_clause([cte], "duckdb", compile_sql)
        assert len(params) == 2
        assert params[0] == "2026-01-01"
        assert params[1] == "2026-03-31"


# ── 集成测试：CTE 在完整 SQL 中的表现 ──

class TestCTESelectIntegration:
    """CTE 集成到完整 SQL 编译的端到端测试"""

    def test_outer_query_with_cte(self):
        """外层查询引用 CTE——WITH + SELECT 完整编译"""
        req = parse_requirement(
            PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
        )
        intent = build_intent(req)
        plan = construct_sqlplan(intent)

        # 为外层查询添加 CTE 定义
        cte_plan = _make_simple_sqlplan(
            table_name="gold.fact_trips",
            col_name="trip_count",
            col_alias="行程量",
        )
        plan.cte_definitions = [_make_cte("stage_1", cte_plan)]
        # 外层查询的 FROM 改为 CTE 名
        plan.join_graph = _make_single_table_join_graph("stage_1")

        sql, params = compile_sql(plan)
        assert sql.startswith("WITH")
        assert "stage_1 AS (" in sql
        assert "FROM stage_1" in sql

    def test_cte_chain_in_outer_query(self):
        """外层查询使用链式 CTE"""
        req = parse_requirement(
            PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
        )
        intent = build_intent(req)
        plan = construct_sqlplan(intent)

        # 构建两阶段 CTE 链
        cte1 = _make_cte(
            "stage_1",
            _make_simple_sqlplan(table_name="gold.fact_trips", col_name="trip_count", col_alias="行程量"),
        )
        cte2 = _make_cte(
            "stage_2",
            _make_simple_sqlplan(table_name="stage_1", col_name="行程量", col_alias="行程量2"),
        )
        plan.cte_definitions = [cte1, cte2]
        plan.join_graph = _make_single_table_join_graph("stage_2")

        sql, params = compile_sql(plan)
        assert "stage_1 AS (" in sql
        assert "stage_2 AS (" in sql
        assert "FROM stage_2" in sql

    def test_outer_query_params_include_cte_params(self):
        """外层 SQL 参数包含 CTE 体参数"""
        from scripts.pipeline.layer3_ir import FilterType
        # 构建带 WHERE 的 CTE 体
        jg = _make_single_table_join_graph("gold.fact_trips")
        cte_plan = SQLPlan(
            plan_id="cte_filtered",
            plan_name="filtered",
            source_layer="g2",
            domain="traffic",
            join_graph=jg,
            column_bindings=[
                ColumnBinding(
                    metric_name="trip_count",
                    column_ref="gold.fact_trips.trip_count",
                    alias="行程量",
                    unit="次",
                    domain="traffic",
                ),
            ],
            filter_bindings=[
                FilterBinding(
                    filter_type=FilterType.DATE_RANGE,
                    column_ref="gold.fact_trips.pickup_date",
                    operator="BETWEEN",
                    value=["2026-01-01", "2026-01-31"],
                ),
            ],
            is_valid=True,
        )

        req = parse_requirement(
            PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
        )
        intent = build_intent(req)
        plan = construct_sqlplan(intent)
        plan.cte_definitions = [_make_cte("stage_1", cte_plan)]
        plan.join_graph = _make_single_table_join_graph("stage_1")

        sql, params = compile_sql(plan)
        # CTE 参数（2个日期）+ 外层查询参数（2个日期）
        assert len(params) == 4
        assert params[0] == "2026-01-01"
        assert params[1] == "2026-01-31"


# ═══════════════════════════════════════════════════════════
# Phase 6+7：操作编译器 + 增量策略测试
# ═══════════════════════════════════════════════════════════

# ── 测试用工厂函数 ──

def _make_step(
    step_id: str = "step_1",
    operation: StepOperation = StepOperation.CREATE_TABLE_AS_SELECT,
    target_table: str = "generated.test_table",
    incremental_intent: IncrementalIntent | None = None,
) -> PipelineStep:
    """快速创建测试用 PipelineStep"""
    return PipelineStep(
        step_id=step_id,
        step_name=f"Test {step_id}",
        operation=operation,
        target_table=target_table,
        incremental_intent=incremental_intent,
    )


def _make_incremental(
    dedup_scope: str = "partition",
    key_columns: list | None = None,
    partition_column: str = "batch_date",
    watermark_column: str = "event_date",
) -> IncrementalIntent:
    """快速创建测试用 IncrementalIntent"""
    return IncrementalIntent(
        incremental=True,
        key_columns=key_columns or [],
        watermark_column=watermark_column,
        partition_column=partition_column,
        dedup_scope=dedup_scope,
    )


SAMPLE_SELECT = "SELECT\n    gold.test.col_a AS \"测试列\"\nFROM gold.test"


# ── P7 单元测试：策略解析 ──

class TestExecutionStrategy:
    """增量策略解析器——PipelineStep → ExecutionStrategy"""

    def test_select_only(self):
        """SELECT_ONLY → SELECT_ONLY（忽略增量意图）"""
        step = _make_step(operation=StepOperation.SELECT_ONLY)
        strategy = resolve_strategy(step)
        assert strategy == ExecutionStrategy.SELECT_ONLY

    def test_create_view(self):
        """CREATE_VIEW → CREATE_VIEW（忽略增量意图）"""
        step = _make_step(operation=StepOperation.CREATE_VIEW)
        strategy = resolve_strategy(step)
        assert strategy == ExecutionStrategy.CREATE_VIEW

    def test_ctas_no_incremental(self):
        """CTAS + 无增量意图 → FULL_OVERWRITE"""
        step = _make_step(operation=StepOperation.CREATE_TABLE_AS_SELECT)
        strategy = resolve_strategy(step)
        assert strategy == ExecutionStrategy.FULL_OVERWRITE

    def test_ctas_incremental_partition(self):
        """CTAS + incremental + partition → PARTITION_OVERWRITE"""
        step = _make_step(
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            incremental_intent=_make_incremental(dedup_scope="partition"),
        )
        strategy = resolve_strategy(step)
        assert strategy == ExecutionStrategy.PARTITION_OVERWRITE

    def test_ctas_incremental_key_merge(self):
        """CTAS + incremental + key_merge → KEY_MERGE"""
        step = _make_step(
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            incremental_intent=_make_incremental(
                dedup_scope="key_merge",
                key_columns=["id"],
            ),
        )
        strategy = resolve_strategy(step)
        assert strategy == ExecutionStrategy.KEY_MERGE

    def test_insert_overwrite_partition_incremental(self):
        """INSERT_OVERWRITE + incremental + partition → PARTITION_OVERWRITE"""
        step = _make_step(
            operation=StepOperation.INSERT_OVERWRITE_PARTITION,
            incremental_intent=_make_incremental(dedup_scope="partition"),
        )
        strategy = resolve_strategy(step)
        assert strategy == ExecutionStrategy.PARTITION_OVERWRITE

    def test_insert_overwrite_no_partition_col(self):
        """INSERT_OVERWRITE + 无分区列 → 降级到 FULL_OVERWRITE"""
        step = _make_step(
            operation=StepOperation.INSERT_OVERWRITE_PARTITION,
            incremental_intent=_make_incremental(partition_column=""),
        )
        strategy = resolve_strategy(step)
        assert strategy == ExecutionStrategy.FULL_OVERWRITE

    def test_insert_into_partition(self):
        """INSERT_INTO + incremental → PARTITION_APPEND"""
        step = _make_step(
            operation=StepOperation.INSERT_INTO_PARTITION,
            incremental_intent=_make_incremental(),
        )
        strategy = resolve_strategy(step)
        assert strategy == ExecutionStrategy.PARTITION_APPEND

    def test_non_incremental_overrides(self):
        """非增量意图（incremental=False）→ FULL_OVERWRITE"""
        intent = IncrementalIntent(incremental=False)
        step = _make_step(
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            incremental_intent=intent,
        )
        strategy = resolve_strategy(step)
        assert strategy == ExecutionStrategy.FULL_OVERWRITE


# ── P6 单元测试：操作编译 ──

class TestOperationCompile:
    """操作编译器——DDL/DML 包裹测试"""

    def test_select_only_passthrough(self):
        """SELECT_ONLY——直接透传 SELECT"""
        step = _make_step(operation=StepOperation.SELECT_ONLY)
        result = compile_operation(step, SAMPLE_SELECT, "duckdb")
        assert result == SAMPLE_SELECT

    def test_full_overwrite_duckdb(self):
        """DuckDB 全量覆盖：CREATE OR REPLACE TABLE AS SELECT"""
        step = _make_step(
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            target_table="generated.daily_stats",
        )
        result = compile_operation(step, SAMPLE_SELECT, "duckdb")
        assert "CREATE OR REPLACE TABLE generated.daily_stats AS" in result
        assert "SELECT" in result
        assert "gold.test.col_a" in result

    def test_full_overwrite_hive(self):
        """Hive 全量覆盖：INSERT OVERWRITE TABLE target SELECT"""
        step = _make_step(
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            target_table="generated.daily_stats",
        )
        result = compile_operation(step, SAMPLE_SELECT, "hive")
        assert "INSERT OVERWRITE TABLE generated.daily_stats" in result
        assert "PARTITION" not in result  # 无分区列

    def test_partition_append_duckdb(self):
        """DuckDB 追加写入：INSERT INTO target SELECT"""
        step = _make_step(
            operation=StepOperation.INSERT_INTO_PARTITION,
            target_table="generated.daily_stats",
            incremental_intent=_make_incremental(),
        )
        result = compile_operation(step, SAMPLE_SELECT, "duckdb")
        assert "INSERT INTO generated.daily_stats" in result
        assert "SELECT" in result

    def test_partition_overwrite_hive(self):
        """Hive 分区覆盖：INSERT OVERWRITE TABLE target PARTITION (col) SELECT"""
        step = _make_step(
            operation=StepOperation.INSERT_OVERWRITE_PARTITION,
            target_table="generated.daily_stats",
            incremental_intent=_make_incremental(partition_column="batch_date"),
        )
        result = compile_operation(step, SAMPLE_SELECT, "hive")
        assert "INSERT OVERWRITE TABLE generated.daily_stats" in result
        assert "PARTITION (batch_date)" in result

    def test_partition_append_hive(self):
        """Hive 分区追加：INSERT INTO TABLE target PARTITION (col) SELECT"""
        step = _make_step(
            operation=StepOperation.INSERT_INTO_PARTITION,
            target_table="generated.daily_stats",
            incremental_intent=_make_incremental(partition_column="batch_date"),
        )
        result = compile_operation(step, SAMPLE_SELECT, "hive")
        assert "INSERT INTO TABLE generated.daily_stats" in result
        assert "PARTITION (batch_date)" in result

    def test_create_view_duckdb(self):
        """DuckDB 视图创建：CREATE OR REPLACE VIEW AS SELECT"""
        step = _make_step(
            operation=StepOperation.CREATE_VIEW,
            target_table="generated.daily_view",
        )
        result = compile_operation(step, SAMPLE_SELECT, "duckdb")
        assert "CREATE OR REPLACE VIEW generated.daily_view AS" in result

    def test_create_view_postgresql(self):
        """PostgreSQL 视图创建：CREATE OR REPLACE VIEW AS SELECT"""
        step = _make_step(
            operation=StepOperation.CREATE_VIEW,
            target_table="generated.daily_view",
        )
        result = compile_operation(step, SAMPLE_SELECT, "postgresql")
        assert "CREATE OR REPLACE VIEW generated.daily_view AS" in result

    def test_key_merge_raises(self):
        """KEY_MERGE 策略暂未实现——应抛出 SQLCompileError"""
        step = _make_step(
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            incremental_intent=_make_incremental(
                dedup_scope="key_merge",
                key_columns=["id"],
            ),
        )
        with pytest.raises(SQLCompileError, match="KEY_MERGE"):
            compile_operation(step, SAMPLE_SELECT, "duckdb")

    def test_partition_append_postgresql(self):
        """PostgreSQL 追加写入：INSERT INTO target SELECT"""
        step = _make_step(
            operation=StepOperation.INSERT_INTO_PARTITION,
            target_table="generated.daily_stats",
            incremental_intent=_make_incremental(),
        )
        result = compile_operation(step, SAMPLE_SELECT, "postgresql")
        assert "INSERT INTO generated.daily_stats" in result

    def test_full_overwrite_postgresql(self):
        """PostgreSQL 全量覆盖：事务包裹 DELETE + INSERT"""
        step = _make_step(
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            target_table="generated.daily_stats",
        )
        result = compile_operation(step, SAMPLE_SELECT, "postgresql")
        assert "BEGIN;" in result
        assert "DELETE FROM generated.daily_stats" in result
        assert "INSERT INTO generated.daily_stats" in result
        assert "COMMIT;" in result

    def test_dialect_fallback(self):
        """未注册方言 fallback 到 DuckDB"""
        step = _make_step(
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            target_table="generated.test",
        )
        result = compile_operation(step, SAMPLE_SELECT, "mysql")
        assert "CREATE OR REPLACE TABLE generated.test AS" in result

    def test_hive_ctas_direct(self):
        """Hive CTAS：CREATE TABLE target AS SELECT"""
        step = _make_step(
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            target_table="generated.new_table",
        )
        result = compile_operation(step, SAMPLE_SELECT, "hive")
        # Hive 的 FULL_OVERWRITE 使用 INSERT OVERWRITE（目标表已存在）
        assert "INSERT OVERWRITE TABLE" in result


# ── 集成测试：端到端管道步骤编译 ──

class TestPipelineStepCompile:
    """PipelineStep 完整编译——SELECT + 操作包裹"""

    def test_full_step_ctas(self):
        """完整 CTAS 步骤编译"""
        req = parse_requirement(
            PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
        )
        intent = build_intent(req)
        plan = construct_sqlplan(intent)

        step = _make_step(
            operation=StepOperation.CREATE_TABLE_AS_SELECT,
            target_table="generated.trip_daily",
        )
        # 将 plan 的 SQL 赋给 step
        select_sql, params = compile_sql(plan)
        full_sql = compile_operation(step, select_sql, "duckdb")

        assert "CREATE OR REPLACE TABLE generated.trip_daily AS" in full_sql
        assert "SELECT" in full_sql
        assert "trip_count" in full_sql
        assert len(params) == 2  # 日期参数

    def test_full_step_insert_append(self):
        """完整 INSERT INTO 步骤编译"""
        req = parse_requirement(
            PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
        )
        intent = build_intent(req)
        plan = construct_sqlplan(intent)

        step = _make_step(
            operation=StepOperation.INSERT_INTO_PARTITION,
            target_table="generated.trip_daily",
            incremental_intent=_make_incremental(),
        )
        select_sql, params = compile_sql(plan)
        full_sql = compile_operation(step, select_sql, "duckdb")

        assert "INSERT INTO generated.trip_daily" in full_sql
        assert "SELECT" in full_sql
