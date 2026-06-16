"""
测试 IR 类型系统——枚举值、构造、序列化、桥接。
"""

from __future__ import annotations

import pytest

from src.ir.types import (
    Domain, IntentType, TimeRangeType, Strategy, MergeStatus,
    ExecutionMode, ValidationStatus, CrossValidateStatus,
    TimeRange, Filter, QuestionIntent, SubIntent,
    JoinPlan, Aggregation, SQLPlan,
    SQLResult, ExecutionTrace,
    ResultSummary, MergedResult,
    UnifiedResponse, AgentResponse,
    CodeGenerationRequest, CodeGenerationResult,
    CheckResult, ValidationReport, CrossValidationResult,
    ReviewMaterial, ReviewPackage,
)


class TestEnums:
    """枚举值不重复、序列化正确"""

    def test_domain_values(self):
        assert Domain.TRAFFIC.value == "traffic"
        assert Domain.SAFETY.value == "safety"
        assert Domain.VIOLATION.value == "violation"
        assert Domain.SUPPLY.value == "supply"
        assert len(set(v.value for v in Domain)) == 6

    def test_strategy_values(self):
        assert Strategy.G3_DIRECT.value == "g3_direct"
        assert Strategy.G2_FACT.value == "g2_fact"
        assert Strategy.NEED_CLARIFICATION.value == "need_clarification"

    def test_validation_status_values(self):
        assert ValidationStatus.PASSED.value == "passed"
        assert ValidationStatus.FAILED.value == "failed"
        assert ValidationStatus.WARN.value == "warn"

    def test_cross_validate_status_values(self):
        assert CrossValidateStatus.CONSISTENT.value == "consistent"
        assert CrossValidateStatus.INCONSISTENT.value == "inconsistent"
        assert CrossValidateStatus.SKIPPED.value == "skipped"


class TestQuestionIntent:
    """Layer 1 构造与校验"""

    def test_construction_minimal(self):
        qi = QuestionIntent()
        assert qi.metrics == []
        assert qi.confidence == 0.0
        assert qi.time_range.type == TimeRangeType.FUZZY

    def test_validate_empty(self):
        """完全空的 intent 校验应报错"""
        qi = QuestionIntent()
        errors = qi.validate()
        assert len(errors) > 0

    def test_validate_with_metrics(self):
        """有指标的 intent 校验通过"""
        qi = QuestionIntent(metrics=["trip_count"], domain=Domain.TRAFFIC)
        errors = qi.validate()
        assert len(errors) == 0

    def test_to_dict(self):
        qi = QuestionIntent(
            domain=Domain.TRAFFIC,
            metrics=["trip_count"],
            time_range=TimeRange(
                type=TimeRangeType.ABSOLUTE,
                start="2026-01-01",
                end="2026-03-31",
            ),
        )
        d = qi.to_dict()
        assert d["domain"] == "traffic"
        assert d["metrics"] == ["trip_count"]
        assert d["time_range"]["start"] == "2026-01-01"


class TestSQLPlan:
    """Layer 2 构造与校验"""

    def test_construction_g3(self):
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
        )
        assert plan.primary_table == "gold.dws_daily_trip_summary"

    def test_validate_needs_clarification(self):
        plan = SQLPlan(strategy=Strategy.NEED_CLARIFICATION)
        errors = plan.validate()
        assert len(errors) > 0
        assert "NEED_CLARIFICATION" in errors[0]

    def test_validate_no_primary_table(self):
        plan = SQLPlan(strategy=Strategy.G3_DIRECT)
        errors = plan.validate()
        assert any("primary_table" in e for e in errors)

    def test_validate_downgrade_no_reason(self):
        plan = SQLPlan(
            strategy=Strategy.G2_FACT,
            primary_table="gold.fact_trips",
        )
        errors = plan.validate()
        assert any("downgrade_reason" in e for e in errors)

    def test_validate_with_available_tables(self):
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
        )
        errors = plan.validate(
            available_tables={"gold.dws_daily_trip_summary"}
        )
        assert len(errors) == 0

    def test_validate_table_not_available(self):
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.unknown_table",
        )
        errors = plan.validate(available_tables={"gold.known_table"})
        assert any("不在可用表" in e for e in errors)

    def test_validate_join_whitelist_violation(self):
        plan = SQLPlan(
            strategy=Strategy.G3_CROSS,
            primary_table="gold.table_a",
            joins=[JoinPlan(table="gold.table_c", on="a.id = c.id")],
        )
        errors = plan.validate(
            join_whitelist={("gold.table_a", "gold.table_b")}
        )
        assert any("不在核准白名单" in e for e in errors)

    def test_validate_join_whitelist_pass(self):
        plan = SQLPlan(
            strategy=Strategy.G3_CROSS,
            primary_table="gold.table_a",
            joins=[JoinPlan(table="gold.table_b", on="a.id = b.id")],
            downgrade_reason="跨表JOIN是唯一可行的查询路径",  # 非 G3_DIRECT 必须填写降级原因
        )
        errors = plan.validate(
            join_whitelist={("gold.table_a", "gold.table_b")}
        )
        assert len(errors) == 0

    def test_to_dict(self):
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
            group_by=["trip_date"],
            limit=100,
        )
        d = plan.to_dict()
        assert d["strategy"] == "g3_direct"
        assert d["limit"] == 100


class TestSQLResult:
    """Layer 3 构造与签名"""

    def test_construction(self):
        result = SQLResult(
            sql="SELECT 1",
            columns=["a"],
            column_types=["INTEGER"],
            rows=[(1,)],
            row_count=1,
        )
        assert result.row_count == 1
        assert result.error is None

    def test_signature_stable(self):
        r1 = SQLResult(
            sql="SELECT 1",
            columns=["a", "b"],
            column_types=["INTEGER", "VARCHAR"],
            row_count=100,
        )
        r2 = SQLResult(
            sql="SELECT 2",
            columns=["a", "b"],
            column_types=["INTEGER", "VARCHAR"],
            row_count=100,
        )
        assert r1.result_signature == r2.result_signature

    def test_signature_different(self):
        r1 = SQLResult(
            sql="SELECT 1",
            columns=["a"],
            column_types=["INTEGER"],
            row_count=100,
        )
        r2 = SQLResult(
            sql="SELECT 1",
            columns=["a", "b"],
            column_types=["INTEGER", "VARCHAR"],
            row_count=100,
        )
        assert r1.result_signature != r2.result_signature

    def test_validate_error(self):
        result = SQLResult(sql="SELECT 1", error="connection refused")
        warnings = result.validate()
        assert len(warnings) > 0

    def test_validate_empty_result(self):
        result = SQLResult(sql="SELECT 1", row_count=0)
        warnings = result.validate()
        assert any("为空" in w for w in warnings)


class TestV2Types:
    """v2.0 新增类型"""

    def test_code_generation_request(self):
        req = CodeGenerationRequest(
            design={"strategy": "g3_direct"},
            context={"available_tables": ["gold.t1"]},
        )
        assert req.include_spark is True
        assert req.target_dialect == "duckdb"

    def test_code_generation_result(self):
        result = CodeGenerationResult(
            sql_code="SELECT 1",
            spark_dsl_code="spark.table('t1').select('*')",
            uncertain_annotations=["指标映射置信度低"],
        )
        assert result.generation_mode == ExecutionMode.SQL_ONLY

    def test_validation_report_passed(self):
        report = ValidationReport(
            overall_status=ValidationStatus.PASSED,
            checks=[
                CheckResult(check_id=1, name="检查1", status=ValidationStatus.PASSED),
            ],
        )
        assert report.passed is True
        assert report.has_warnings is False
        assert report.fail_count == 0

    def test_validation_report_failed(self):
        report = ValidationReport(
            overall_status=ValidationStatus.FAILED,
            checks=[
                CheckResult(check_id=1, name="检查1", status=ValidationStatus.FAILED,
                           detail="失败"),
            ],
        )
        assert report.passed is False
        assert report.fail_count == 1

    def test_validation_report_warn(self):
        report = ValidationReport(
            overall_status=ValidationStatus.WARN,
            checks=[
                CheckResult(check_id=6, name="结果质量", status=ValidationStatus.WARN,
                           detail="结果为空", severity="WARN"),
            ],
        )
        assert report.passed is True  # 无 FAIL
        assert report.has_warnings is True

    def test_cross_validation_result(self):
        cvr = CrossValidationResult(
            status=CrossValidateStatus.SKIPPED,
            detail="Spark 不可用",
        )
        d = cvr.to_dict()
        assert d["status"] == "skipped"

    def test_review_package(self):
        rp = ReviewPackage(
            requirement={"name": "test"},
            design={"strategy": "g3"},
            uncertainties=["项1"],
            created_at="2026-06-16",
        )
        assert len(rp.uncertainties) == 1


class TestV1Bridge:
    """v1.x ↔ v2.0 桥接测试"""

    def test_to_v1_plan_g3(self):
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
        )
        from src.ir.v1_bridge import to_v1_plan
        v1_dict = to_v1_plan(plan)
        assert v1_dict["source_layer"] == "g3"
        assert v1_dict["is_valid"] is True

    def test_to_v1_plan_g2(self):
        plan = SQLPlan(
            strategy=Strategy.G2_FACT,
            primary_table="gold.fact_trips",
        )
        from src.ir.v1_bridge import to_v1_plan
        v1_dict = to_v1_plan(plan)
        assert v1_dict["source_layer"] == "g2"

    def test_from_v1_plan_basic(self):
        """测试从 dict-like 对象构造 v2.0 SQLPlan"""
        from src.ir.v1_bridge import from_v1_plan

        # 模拟 v1.x SQLPlan 对象
        class MockV1Plan:
            primary_table = "gold.dws_daily_trip_summary"
            source_layer = "g3"
            group_by = ["trip_date"]
            join_graph = None

        plan = from_v1_plan(MockV1Plan())
        assert plan.strategy == Strategy.G3_DIRECT
        assert plan.primary_table == "gold.dws_daily_trip_summary"
        assert plan.group_by == ["trip_date"]

    def test_strategy_layer_mapping(self):
        """策略与层级的映射一致性"""
        from src.ir.v1_bridge import _strategy_to_layer
        assert _strategy_to_layer(Strategy.G3_DIRECT) == "g3"
        assert _strategy_to_layer(Strategy.G2_FACT) == "g2"
        assert _strategy_to_layer(Strategy.NEED_CLARIFICATION) == "g3"  # 默认


class TestContracts:
    """YAML 契约解析测试"""

    def test_parse_requirement_valid(self, tmp_path):
        import yaml
        from src.ir.contracts import parse_requirement

        yaml_file = tmp_path / "test_req.yml"
        yaml_file.write_text(yaml.dump({
            "name": "test_report",
            "metrics": ["trip_count"],
            "filters": {"date_range": ["2026-01-01", "2026-03-31"]},
        }), encoding="utf-8")

        req = parse_requirement(str(yaml_file))
        assert req.is_valid is True
        assert req.name == "test_report"
        assert len(req.metrics) == 1

    def test_parse_requirement_missing_file(self):
        from src.ir.contracts import parse_requirement
        req = parse_requirement("nonexistent.yml")
        assert req.is_valid is False
        assert "文件不存在" in req.validation_errors[0]

    def test_parse_requirement_missing_metrics(self, tmp_path):
        import yaml
        from src.ir.contracts import parse_requirement

        yaml_file = tmp_path / "bad_req.yml"
        yaml_file.write_text(yaml.dump({
            "name": "bad_report",
            "filters": {"date_range": ["2026-01-01", "2026-03-31"]},
        }), encoding="utf-8")

        req = parse_requirement(str(yaml_file))
        assert req.is_valid is False
        assert any("metrics" in e for e in req.validation_errors)
