"""
三层 IR 数据结构单元测试。

验证 QuestionIntent、SQLPlan、SQLResult 的：
    - 实例化
    - 序列化/反序列化
    - validate() 校验逻辑
    - 签名计算
"""

import pytest


class TestQuestionIntent:
    """Layer 1: QuestionIntent 测试"""

    def test_instantiation(self):
        """测试基本实例化"""
        from src.ir import QuestionIntent, Domain, IntentType, TimeRange, TimeRangeType

        intent = QuestionIntent(
            domain=Domain.TRAFFIC,
            intent_type=IntentType.AGGREGATION,
            metrics=["trip_count"],
            time_range=TimeRange(type=TimeRangeType.ABSOLUTE, start="2026-01-01", end="2026-03-31"),
            confidence=0.95,
        )
        assert intent.domain == Domain.TRAFFIC
        assert len(intent.metrics) == 1
        assert intent.confidence == 0.95

    def test_validate_clean_intent(self):
        """测试干净意图的校验"""
        from src.ir import QuestionIntent, Domain, IntentType, TimeRange, TimeRangeType

        intent = QuestionIntent(
            domain=Domain.TRAFFIC,
            intent_type=IntentType.AGGREGATION,
            metrics=["trip_count"],
            time_range=TimeRange(type=TimeRangeType.ABSOLUTE, start="2026-01-01", end="2026-03-31"),
            confidence=0.95,
        )
        errors = intent.validate()
        assert errors == []

    def test_validate_needs_clarification(self):
        """测试需要反问的场景"""
        from src.ir import QuestionIntent

        intent = QuestionIntent(
            needs_clarification=True,
            clarification_reason="时间范围模糊",
            confidence=0.3,
        )
        errors = intent.validate()
        assert len(errors) > 0
        assert any("反问" in e for e in errors)

    def test_validate_fuzzy_time(self):
        """测试模糊时间的校验"""
        from src.ir import QuestionIntent, TimeRange, TimeRangeType

        intent = QuestionIntent(
            metrics=["trip_count"],
            time_range=TimeRange(type=TimeRangeType.FUZZY, raw_expression="最近"),
            confidence=0.6,
        )
        errors = intent.validate()
        assert len(errors) > 0

    def test_validate_low_confidence(self):
        """测试低置信度的校验"""
        from src.ir import QuestionIntent, Domain, IntentType, TimeRange, TimeRangeType

        intent = QuestionIntent(
            domain=Domain.TRAFFIC,
            intent_type=IntentType.AGGREGATION,
            metrics=["trip_count"],
            time_range=TimeRange(type=TimeRangeType.ABSOLUTE, start="2026-01-01", end="2026-03-31"),
            confidence=0.3,
        )
        errors = intent.validate()
        assert len(errors) > 0

    def test_to_dict(self):
        """测试序列化"""
        from src.ir import QuestionIntent, Domain, IntentType, TimeRange, TimeRangeType

        intent = QuestionIntent(
            domain=Domain.TRAFFIC,
            intent_type=IntentType.AGGREGATION,
            metrics=["trip_count"],
            time_range=TimeRange(type=TimeRangeType.ABSOLUTE, start="2026-01-01", end="2026-03-31"),
            dimensions=["date"],
            confidence=0.95,
            raw_question="测试",
        )
        d = intent.to_dict()
        assert d["domain"] == "traffic"
        assert d["metrics"] == ["trip_count"]
        assert d["time_range"]["start"] == "2026-01-01"


class TestSQLPlan:
    """Layer 2: SQLPlan 测试"""

    def test_instantiation(self):
        """测试基本实例化"""
        from src.ir import SQLPlan, Strategy, Aggregation

        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
            aggregations=[Aggregation(expr="SUM(trip_count)", alias="trip_count")],
            confidence=0.97,
        )
        assert plan.strategy == Strategy.G3_DIRECT
        assert plan.primary_table == "gold.dws_daily_trip_summary"

    def test_validate_missing_downgrade_reason(self):
        """测试降级但未标注原因"""
        from src.ir import SQLPlan, Strategy

        plan = SQLPlan(
            strategy=Strategy.G2_FACT_JOIN,
            primary_table="gold.fact_trips",
            downgrade_reason=None,
        )
        errors = plan.validate()
        assert len(errors) > 0

    def test_validate_clean_plan(self):
        """测试干净的 G3 计划"""
        from src.ir import SQLPlan, Strategy, Aggregation

        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
            aggregations=[Aggregation(expr="SUM(trip_count)", alias="trip_count")],
            confidence=0.97,
        )
        errors = plan.validate()
        assert errors == []

    def test_validate_table_not_in_allowlist(self):
        """测试表不在白名单"""
        from src.ir import SQLPlan, Strategy

        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.nonexistent_table",
            confidence=0.9,
        )
        errors = plan.validate(available_tables={"gold.dws_daily_trip_summary"})
        assert len(errors) > 0

    def test_to_dict(self):
        """测试序列化"""
        from src.ir import SQLPlan, Strategy, Aggregation

        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
            where_clauses=["trip_date >= DATE '2026-01-01'"],
            group_by=["trip_date"],
            aggregations=[Aggregation(expr="SUM(trip_count)", alias="trip_count")],
        )
        d = plan.to_dict()
        assert d["strategy"] == "g3_direct"
        assert d["primary_table"] == "gold.dws_daily_trip_summary"
        assert len(d["aggregations"]) == 1


class TestSQLResult:
    """Layer 3: SQLResult 测试"""

    def test_signature_stability(self):
        """测试签名稳定性：同样输入 → 同样签名"""
        from src.ir import SQLResult

        r1 = SQLResult(
            sql="SELECT 1",
            columns=["a", "b"],
            column_types=["INTEGER", "VARCHAR"],
            row_count=100,
        )
        r2 = SQLResult(
            sql="SELECT 2",  # 不同 SQL 不影响签名
            columns=["a", "b"],
            column_types=["INTEGER", "VARCHAR"],
            row_count=100,
        )
        assert r1.result_signature == r2.result_signature

    def test_signature_different(self):
        """测试签名差异：不同结构 → 不同签名"""
        from src.ir import SQLResult

        r1 = SQLResult(
            sql="SELECT 1",
            columns=["a", "b"],
            column_types=["INTEGER", "VARCHAR"],
            row_count=100,
        )
        r2 = SQLResult(
            sql="SELECT 1",
            columns=["a", "b", "c"],  # 多了一列
            column_types=["INTEGER", "VARCHAR", "DATE"],
            row_count=100,
        )
        assert r1.result_signature != r2.result_signature

    def test_validate_error(self):
        """测试错误结果的校验"""
        from src.ir import SQLResult

        result = SQLResult(
            sql="SELECT * FROM nonexistent",
            error="Table not found",
        )
        warnings = result.validate()
        assert len(warnings) > 0

    def test_validate_empty(self):
        """测试空结果的校验"""
        from src.ir import SQLResult

        result = SQLResult(
            sql="SELECT * FROM gold.dws_daily_trip_summary WHERE 1=0",
            row_count=0,
        )
        warnings = result.validate()
        assert len(warnings) > 0

    def test_validate_clean(self):
        """测试正常结果的校验"""
        from src.ir import SQLResult

        result = SQLResult(
            sql="SELECT * FROM gold.dws_daily_trip_summary LIMIT 10",
            columns=["trip_date", "trip_count"],
            column_types=["DATE", "BIGINT"],
            row_count=10,
        )
        warnings = result.validate()
        assert warnings == []


class TestAgentResponse:
    """顶层 AgentResponse 测试"""

    def test_full_pipeline_serialization(self):
        """测试完整链路的序列化"""
        from src.ir import (
            AgentResponse, QuestionIntent, SQLPlan, SQLResult,
            Domain, IntentType, Strategy, TimeRange, TimeRangeType,
            Aggregation,
        )

        response = AgentResponse(
            question="2026年Q1曼哈顿每天多少行程？",
            intent=QuestionIntent(
                domain=Domain.TRAFFIC,
                intent_type=IntentType.AGGREGATION,
                metrics=["trip_count"],
                time_range=TimeRange(type=TimeRangeType.ABSOLUTE, start="2026-01-01", end="2026-03-31"),
                confidence=0.95,
            ),
            plan=SQLPlan(
                strategy=Strategy.G3_DIRECT,
                primary_table="gold.dws_zone_trip_summary",
                aggregations=[Aggregation(expr="SUM(trip_count)", alias="trip_count")],
            ),
            result=SQLResult(
                sql="SELECT borough, SUM(trip_count) FROM gold.dws_zone_trip_summary ...",
                columns=["borough", "trip_count"],
                column_types=["VARCHAR", "BIGINT"],
                row_count=5,
            ),
            chinese_answer="2026年Q1曼哈顿各区域行程量...",
        )

        d = response.to_dict()
        assert d["question"] == "2026年Q1曼哈顿每天多少行程？"
        assert d["intent"] is not None
        assert d["plan"] is not None
        assert d["result"] is not None
        assert d["chinese_answer"] is not None

    def test_clarification_response(self):
        """测试反问响应"""
        from src.ir import AgentResponse

        response = AgentResponse(
            question="最近生意怎么样？",
            clarification_needed=True,
            clarification_message="请明确时间范围和指标。",
        )
        d = response.to_dict()
        assert d["clarification_needed"] is True
        assert d["intent"] is None
        assert d["result"] is None

    def test_refusal_response(self):
        """测试拒绝响应"""
        from src.ir import AgentResponse

        response = AgentResponse(
            question="帮我删掉异常数据",
            refusal=True,
            refusal_reason="Agent 不能修改数据。",
        )
        d = response.to_dict()
        assert d["refusal"] is True
