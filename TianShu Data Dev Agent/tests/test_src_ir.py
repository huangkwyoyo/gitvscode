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

    def test_signature_explicit_utf8_encoding(self):
        """签名生成使用显式 UTF-8 编码，不依赖平台默认编码"""
        r1 = SQLResult(
            sql="SELECT 1",
            columns=["日期", "指标"],  # 中文字段名——测试 UTF-8 编码
            column_types=["DATE", "INTEGER"],
            row_count=42,
        )
        # 不应抛出异常，签名应稳定生成
        sig = r1.result_signature
        assert len(sig) == 32  # MD5 十六进制长度为 32
        # 重复调用返回相同的签名（确定性）
        assert r1.result_signature == sig

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

    def test_to_v1_plan_preserves_aggregations(self):
        """v2 SQLPlan 经 to_v1_plan() 转换后聚合表达式不丢失"""
        from src.ir.v1_bridge import to_v1_plan
        from src.ir.types import Aggregation

        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
            aggregations=[
                Aggregation(expr="COUNT(*)", alias="trip_count"),
                Aggregation(expr="SUM(trip_distance)", alias="total_distance"),
            ],
        )
        v1_dict = to_v1_plan(plan)
        assert "aggregations" in v1_dict
        assert len(v1_dict["aggregations"]) == 2
        assert v1_dict["aggregations"][0]["expr"] == "COUNT(*)"
        assert v1_dict["aggregations"][0]["alias"] == "trip_count"
        assert v1_dict["aggregations"][1]["expr"] == "SUM(trip_distance)"

    def test_to_v1_plan_preserves_where_clauses(self):
        """v2 SQLPlan 经 to_v1_plan() 转换后 WHERE 条件不丢失"""
        from src.ir.v1_bridge import to_v1_plan

        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
            where_clauses=["trip_date >= '2026-01-01'", "trip_count > 0"],
        )
        v1_dict = to_v1_plan(plan)
        assert "where_clauses" in v1_dict
        assert len(v1_dict["where_clauses"]) == 2
        assert "trip_date" in v1_dict["where_clauses"][0]
        assert "trip_count > 0" in v1_dict["where_clauses"][1]

    def test_to_v1_plan_no_aggregations_or_where_clauses(self):
        """空聚合和空过滤条件时不添加对应字段（保持最小输出）"""
        from src.ir.v1_bridge import to_v1_plan

        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
        )
        v1_dict = to_v1_plan(plan)
        # 未设置时字段不应存在
        assert "aggregations" not in v1_dict
        assert "where_clauses" not in v1_dict


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


class TestV1BridgeWarnings:
    """v1_bridge 异常不应被静默吞没，应可通过 _bridge_warnings 检测"""

    def test_normal_v1_plan_no_warnings(self):
        """正常 v1 对象桥接不产生告警"""
        from src.ir.v1_bridge import from_v1_plan

        class MockV1Plan:
            primary_table = "gold.t1"
            source_layer = "g3"
            group_by = []
            join_graph = None

        plan = from_v1_plan(MockV1Plan())
        assert hasattr(plan, "_bridge_warnings"), "应始终存在 _bridge_warnings 属性"
        assert len(plan._bridge_warnings) == 0, "正常对象不应有告警"

    def test_corrupt_primary_table_access_warns(self):
        """v1 对象 primary 访问异常不应静默吞掉"""
        from src.ir.v1_bridge import from_v1_plan

        class CorruptV1Plan:
            """join_graph.primary 抛出 AttributeError"""
            source_layer = "g3"
            group_by = []

            @property
            def primary_table(self):
                return None

            @property
            def join_graph(self):
                class BadGraph:
                    @property
                    def primary(self):
                        raise AttributeError("结构不兼容：缺少 primary 字段")
                return BadGraph()

        plan = from_v1_plan(CorruptV1Plan())
        assert len(plan._bridge_warnings) >= 1, "异常应被记录为告警而非静默吞掉"
        assert any("primary" in w.lower() for w in plan._bridge_warnings), \
            f"告警应提及 primary，实际: {plan._bridge_warnings}"

    def test_corrupt_join_extraction_warns(self):
        """v1 对象 JOIN 提取异常不应静默吞掉"""
        from src.ir.v1_bridge import from_v1_plan

        class CorruptJoinPlan:
            primary_table = "gold.t1"
            source_layer = "g3"
            group_by = []

            @property
            def join_graph(self):
                class BadJoinGraph:
                    primary = type("P", (), {"table": "gold.t1"})()

                    @property
                    def joins(self):
                        return [
                            type("BadJoin", (), {
                                "table": "gold.t2",
                                # condition 不存在——会触发 AttributeError
                            })(),
                        ]
                return BadJoinGraph()

        plan = from_v1_plan(CorruptJoinPlan())
        assert len(plan._bridge_warnings) >= 1, "JOIN 提取异常应被记录为告警"
        assert any("JOIN" in w or "join" in w.lower() for w in plan._bridge_warnings), \
            f"告警应提及 JOIN，实际: {plan._bridge_warnings}"

    def test_missing_primary_table_with_joins_warns(self):
        """primary_table 为空但存在 JOIN 时产生完整性告警"""
        from src.ir.v1_bridge import from_v1_plan

        class JoinOnlyPlan:
            """有 JOIN 但无 primary_table"""
            source_layer = "g3"
            group_by = []
            primary_table = None

            @property
            def join_graph(self):
                class HasJoin:
                    primary = type("P", (), {"table": None})()
                    joins = [
                        type("J", (), {
                            "table": "gold.t2",
                            "condition": type("C", (), {"left": "a", "right": "b"})(),
                            "type": "INNER",
                        })(),
                    ]
                return HasJoin()

        plan = from_v1_plan(JoinOnlyPlan())
        assert len(plan._bridge_warnings) >= 1, "应产生完整性告警"
        assert any("primary_table" in w.lower() or "不完整" in w
                   for w in plan._bridge_warnings), \
            f"应报告不完整，实际: {plan._bridge_warnings}"


class TestSQLPlanCaseNormalization:
    """SQLPlan.validate() 表名大小写规范化比较"""

    def test_primary_table_case_insensitive(self):
        """primary_table='Gold.Table' vs available_tables=['gold.table'] 不应错误失败"""
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="Gold.Table",
        )
        errors = plan.validate(
            available_tables={"gold.table"}
        )
        assert len(errors) == 0, \
            f"大小写不同应通过规范化比较，实际错误: {errors}"

    def test_primary_table_whitespace_normalized(self):
        """primary_table=' gold.table ' 带空白应与 'gold.table' 匹配"""
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table=" gold.table ",
        )
        errors = plan.validate(
            available_tables={"gold.table"}
        )
        assert len(errors) == 0, \
            f"空白应被规范化，实际错误: {errors}"

    def test_primary_table_not_in_list_still_fails(self):
        """规范后确实不在列表中的表仍应报错"""
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.unknown",
        )
        errors = plan.validate(
            available_tables={"gold.known_table"}
        )
        assert len(errors) >= 1
        assert any("gold.unknown" in e for e in errors)

    def test_join_whitelist_case_insensitive(self):
        """JOIN 白名单比较大小写不敏感"""
        plan = SQLPlan(
            strategy=Strategy.G3_CROSS,
            primary_table="Gold.TableA",
            joins=[JoinPlan(table="gold.TABLEB", on="a.id = b.id")],
            downgrade_reason="跨表JOIN是唯一可行的查询路径",
        )
        errors = plan.validate(
            join_whitelist={("gold.tablea", "gold.tableb")}
        )
        assert len(errors) == 0, \
            f"JOIN 白名单应大小写不敏感，实际错误: {errors}"

    def test_join_whitelist_reverse_case_insensitive(self):
        """反向 JOIN 对比较也应大小写不敏感"""
        plan = SQLPlan(
            strategy=Strategy.G3_CROSS,
            primary_table="Gold.TableA",
            joins=[JoinPlan(table="gold.TABLEB", on="a.id = b.id")],
            downgrade_reason="跨表JOIN是唯一可行的查询路径",
        )
        errors = plan.validate(
            join_whitelist={("GOLD.TABLEB", "gold.tablea")}  # 反序 + 大写
        )
        assert len(errors) == 0, \
            f"反向 JOIN 对应大小写不敏感，实际错误: {errors}"

    def test_join_not_in_whitelist_still_fails(self):
        """规范后确实不在白名单的 JOIN 仍应报错"""
        plan = SQLPlan(
            strategy=Strategy.G3_CROSS,
            primary_table="gold.table_a",
            joins=[JoinPlan(table="gold.table_c", on="a.id = c.id")],
            downgrade_reason="跨表JOIN是唯一可行的查询路径",
        )
        errors = plan.validate(
            join_whitelist={("gold.table_a", "gold.table_b")}
        )
        assert len(errors) >= 1
        assert any("table_c" in e for e in errors)
