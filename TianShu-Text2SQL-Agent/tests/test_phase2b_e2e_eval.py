"""
Phase 2B：LLM E2E 端到端评测运行器 单元测试。

测试范围：
    A. 用例加载 —— 从 YAML 解析 E2ECase
    B. 断言逻辑 —— 各行为类型的断言验证
    C. 失败分类 —— 断言结果到失败分类的映射
    D. 报告生成 —— Markdown + JSON 报告
    E. Mock 客户端构造 —— MockLLMClient 响应映射
    F. 集成测试 —— Mock LLM 下的完整评测流程（无真实 API）

约束：
    - 不接入真实 LLM API
    - 默认不联网
    - 不依赖 TianShu DB（mock 模式下 DB 连接失败是预期行为）
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.run_llm_e2e_eval import (
    E2ECase,
    E2EAssertion,
    E2EResult,
    E2EReport,
    E2ERunner,
)
from src.ir import (
    AgentResponse,
    Aggregation,
    Domain,
    IntentType,
    JoinPlan,
    QuestionIntent,
    SQLPlan,
    SQLResult,
    Strategy,
    TimeRange,
    TimeRangeType,
)
from src.llm import MockLLMClient


# ═══════════════════════════════════════════════════════════
# 测试辅助工具
# ═══════════════════════════════════════════════════════════


def _make_answer_response() -> AgentResponse:
    """构造一个完整的 answer 类型 AgentResponse"""
    intent = QuestionIntent(
        domain=Domain.TRAFFIC,
        intent_type=IntentType.TREND,
        metrics=["trip_count"],
        time_range=TimeRange(
            type=TimeRangeType.ABSOLUTE,
            start="2026-01-01",
            end="2026-01-31",
            raw_expression="2026年1月",
        ),
        dimensions=["date"],
        confidence=0.95,
        raw_question="2026年1月每天有多少行程？",
    )
    plan = SQLPlan(
        strategy=Strategy.G3_DIRECT,
        primary_table="gold.dws_daily_trip_summary",
        joins=[
            JoinPlan(
                table="gold.dim_date",
                on="gold.dim_date.date = gold.dws_daily_trip_summary.trip_date",
                type="INNER",
            )
        ],
        where_clauses=[
            "gold.dim_date.date BETWEEN DATE '2026-01-01' AND DATE '2026-01-31'"
        ],
        group_by=["gold.dim_date.date"],
        order_by=["gold.dim_date.date"],
        aggregations=[Aggregation(expr="SUM(trip_count)", alias="trip_count")],
        confidence=0.95,
    )
    result = SQLResult(
        sql="SELECT gold.dim_date.date, SUM(trip_count) AS trip_count\nFROM gold.dws_daily_trip_summary\n  INNER JOIN gold.dim_date ON gold.dim_date.date = gold.dws_daily_trip_summary.trip_date\nWHERE gold.dim_date.date BETWEEN DATE '2026-01-01' AND DATE '2026-01-31'\nGROUP BY gold.dim_date.date\nORDER BY gold.dim_date.date",
        columns=["date", "trip_count"],
        rows=[("2026-01-01", 100)],
        row_count=31,
        execution_time_ms=3.0,
        source_table="gold.dws_daily_trip_summary",
    )
    return AgentResponse(
        question="2026年1月每天有多少行程？",
        intent=intent,
        plan=plan,
        result=result,
        chinese_answer="查询返回 31 行。",
        trace=["[STEP 1] ...", "[DONE]"],
    )


def _make_clarification_response() -> AgentResponse:
    """构造一个 clarification 类型 AgentResponse"""
    intent = QuestionIntent(
        domain=None,
        intent_type=None,
        metrics=[],
        time_range=TimeRange(
            type=TimeRangeType.FUZZY,
            raw_expression="最近",
        ),
        needs_clarification=True,
        clarification_reason="时间范围不明确，需要用户说明最近指哪一段日期。",
        confidence=0.2,
        raw_question="最近每天有多少行程？",
    )
    return AgentResponse(
        question="最近每天有多少行程？",
        intent=intent,
        clarification_needed=True,
        clarification_message="意图校验失败: 需要反问用户: 时间范围不明确，需要用户说明最近指哪一段日期。",
        trace=["[STEP 1] ...", "[FAIL] Layer1 校验失败"],
    )


def _make_refusal_response() -> AgentResponse:
    """构造一个 refusal 类型 AgentResponse"""
    return AgentResponse(
        question="帮我删除异常停车罚单数据",
        refusal=True,
        refusal_reason="我是只读分析 Agent，不能修改、删除或创建数据。",
        trace=["[INFO] 收到问题: ...", "[REFUSE] ..."],
    )


def _make_temp_yaml(cases: list[dict[str, Any]]) -> str:
    """创建临时 YAML 文件并返回路径"""
    content = yaml.dump({"cases": cases}, allow_unicode=True, default_flow_style=False)
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", encoding="utf-8", delete=False
    )
    tmp.write(content)
    tmp.close()
    return tmp.name


# ═══════════════════════════════════════════════════════════
# A 类：用例加载
# ═══════════════════════════════════════════════════════════


class TestE2ECaseLoading:
    """从 YAML 加载 E2E 评测用例"""

    def test_load_answer_case(self):
        """加载 answer 类型用例"""
        yaml_path = _make_temp_yaml([
            {
                "id": "test_answer",
                "question_zh": "测试问题",
                "expected_behavior": "answer",
                "expected_tables": ["gold.test_table"],
                "expected_metrics": ["test_metric"],
                "mock_intent_response": '{"domain": "traffic"}',
                "mock_plan_response": '{"strategy": "g3_direct"}',
            }
        ])
        try:
            runner = E2ERunner(cases_path=yaml_path)
            cases = runner._load_cases()
            assert len(cases) == 1
            case = cases[0]
            assert case.id == "test_answer"
            assert case.question_zh == "测试问题"
            assert case.expected_behavior == "answer"
            assert case.expected_tables == ["gold.test_table"]
            assert case.expected_metrics == ["test_metric"]
            assert "traffic" in case.mock_intent_response
            assert "g3_direct" in case.mock_plan_response
        finally:
            Path(yaml_path).unlink()

    def test_load_clarification_case(self):
        """加载 clarification 类型用例"""
        yaml_path = _make_temp_yaml([
            {
                "id": "test_clarify",
                "question_zh": "模糊问题",
                "expected_behavior": "clarification",
                "expected_clarification_contains": "时间",
                "mock_intent_response": '{"needs_clarification": true}',
            }
        ])
        try:
            runner = E2ERunner(cases_path=yaml_path)
            cases = runner._load_cases()
            assert len(cases) == 1
            case = cases[0]
            assert case.expected_behavior == "clarification"
            assert case.expected_clarification_contains == "时间"
            assert case.expected_tables == []
            assert case.expected_metrics == []
        finally:
            Path(yaml_path).unlink()

    def test_load_refusal_case(self):
        """加载 refusal 类型用例"""
        yaml_path = _make_temp_yaml([
            {
                "id": "test_refuse",
                "question_zh": "删除数据",
                "expected_behavior": "refusal",
                "expected_refusal_contains": "只读",
                "mock_intent_response": '{"refusal": true, "refusal_reason": "只读"}',
            }
        ])
        try:
            runner = E2ERunner(cases_path=yaml_path)
            cases = runner._load_cases()
            assert len(cases) == 1
            case = cases[0]
            assert case.expected_behavior == "refusal"
            assert case.expected_refusal_contains == "只读"
            assert case.mock_plan_response == ""  # 拒绝类不需要 plan
        finally:
            Path(yaml_path).unlink()

    def test_load_multiple_cases(self):
        """加载多条混合用例"""
        yaml_path = _make_temp_yaml([
            {"id": "c1", "question_zh": "q1", "expected_behavior": "answer",
             "mock_intent_response": "{}", "mock_plan_response": "{}"},
            {"id": "c2", "question_zh": "q2", "expected_behavior": "refusal",
             "mock_intent_response": '{"refusal": true}'},
            {"id": "c3", "question_zh": "q3", "expected_behavior": "clarification",
             "mock_intent_response": '{"needs_clarification": true}'},
        ])
        try:
            runner = E2ERunner(cases_path=yaml_path)
            cases = runner._load_cases()
            assert len(cases) == 3
            behaviors = [c.expected_behavior for c in cases]
            assert behaviors == ["answer", "refusal", "clarification"]
        finally:
            Path(yaml_path).unlink()

    def test_load_nonexistent_file_raises(self):
        """加载不存在的文件应抛出 FileNotFoundError"""
        runner = E2ERunner(cases_path="nonexistent_file.yml")
        with pytest.raises(FileNotFoundError):
            runner._load_cases()


# ═══════════════════════════════════════════════════════════
# B 类：断言逻辑
# ═══════════════════════════════════════════════════════════


class TestAssertionsAnswer:
    """answer 类断言"""

    def test_intent_generated_for_answer(self):
        """answer 类：生成 intent 应通过"""
        response = _make_answer_response()
        case = E2ECase(id="test", question_zh="q", expected_behavior="answer")
        result = E2ERunner._check_intent_generated(case, response)
        assert result.passed is True
        # Domain.TRAFFIC 的 str 表示为 "Domain.TRAFFIC"
        assert "Domain.TRAFFIC" in result.detail or "trip_count" in result.detail

    def test_intent_not_generated_for_answer_fails(self):
        """answer 类：未生成 intent 应失败"""
        response = AgentResponse(question="q")
        case = E2ECase(id="test", question_zh="q", expected_behavior="answer")
        result = E2ERunner._check_intent_generated(case, response)
        assert result.passed is False

    def test_answer_unexpected_refusal_fails(self):
        """answer 类：意外触发拒绝应失败"""
        response = AgentResponse(
            question="q",
            refusal=True,
            refusal_reason="意外拒绝",
        )
        case = E2ECase(id="test", question_zh="q", expected_behavior="answer")
        result = E2ERunner._check_intent_generated(case, response)
        assert result.passed is False
        assert "意外拒绝" in result.detail

    def test_expected_metric_hit(self):
        """指标命中检查"""
        response = _make_answer_response()
        case = E2ECase(
            id="test", question_zh="q",
            expected_behavior="answer",
            expected_metrics=["trip_count"],
        )
        result = E2ERunner._check_expected_metrics(case, response)
        assert result.passed is True
        assert "trip_count" in result.detail

    def test_expected_metric_miss(self):
        """指标未命中检查"""
        response = _make_answer_response()
        case = E2ECase(
            id="test", question_zh="q",
            expected_behavior="answer",
            expected_metrics=["wrong_metric"],
        )
        result = E2ERunner._check_expected_metrics(case, response)
        assert result.passed is False
        assert "wrong_metric" in result.detail

    def test_expected_metric_no_constraint(self):
        """无期望指标约束时默认通过"""
        response = _make_answer_response()
        case = E2ECase(id="test", question_zh="q", expected_behavior="answer")
        result = E2ERunner._check_expected_metrics(case, response)
        assert result.passed is True

    def test_plan_generated(self):
        """plan 生成检查"""
        response = _make_answer_response()
        result = E2ERunner._check_plan_generated(response)
        assert result.passed is True
        assert "g3_direct" in result.detail

    def test_plan_not_generated(self):
        """plan 未生成检查"""
        response = AgentResponse(question="q")
        result = E2ERunner._check_plan_generated(response)
        assert result.passed is False

    def test_expected_table_hit(self):
        """表命中检查"""
        response = _make_answer_response()
        case = E2ECase(
            id="test", question_zh="q",
            expected_behavior="answer",
            expected_tables=["gold.dws_daily_trip_summary", "gold.dim_date"],
        )
        result = E2ERunner._check_expected_tables(case, response)
        assert result.passed is True

    def test_expected_table_miss(self):
        """表未命中检查"""
        response = _make_answer_response()
        case = E2ECase(
            id="test", question_zh="q",
            expected_behavior="answer",
            expected_tables=["gold.wrong_table"],
        )
        result = E2ERunner._check_expected_tables(case, response)
        assert result.passed is False
        assert "wrong_table" in result.detail

    def test_sql_is_readonly(self):
        """SQL 只读检查"""
        response = _make_answer_response()
        result = E2ERunner._check_sql_readonly(response)
        assert result.passed is True

    def test_sql_not_readonly(self):
        """SQL 非只读（INSERT）应失败"""
        response = _make_answer_response()
        response.result.sql = "INSERT INTO t VALUES (1)"
        result = E2ERunner._check_sql_readonly(response)
        assert result.passed is False

    def test_execution_successful(self):
        """执行成功检查"""
        response = _make_answer_response()
        result = E2ERunner._check_execution(response)
        assert result.passed is True
        assert "31" in result.detail

    def test_execution_failed(self):
        """执行失败检查"""
        response = _make_answer_response()
        response.result.error = "Connection refused"
        result = E2ERunner._check_execution(response)
        assert result.passed is False
        assert "Connection refused" in result.detail


class TestAssertionsClarification:
    """clarification 类断言"""

    def test_clarification_correct(self):
        """反问正确触发"""
        response = _make_clarification_response()
        case = E2ECase(id="test", question_zh="q", expected_behavior="clarification")
        runner = E2ERunner()
        assertions = runner._check_clarification_case(case, response)
        clarification_assert = [a for a in assertions if a.name == "clarification_correct"][0]
        assert clarification_assert.passed is True

    def test_clarification_content_match(self):
        """反问内容匹配"""
        response = _make_clarification_response()
        case = E2ECase(
            id="test", question_zh="q",
            expected_behavior="clarification",
            expected_clarification_contains="时间范围",
        )
        runner = E2ERunner()
        assertions = runner._check_clarification_case(case, response)
        content_assert = [a for a in assertions if a.name == "clarification_content_match"][0]
        assert content_assert.passed is True

    def test_clarification_content_mismatch(self):
        """反问内容不匹配"""
        response = _make_clarification_response()
        case = E2ECase(
            id="test", question_zh="q",
            expected_behavior="clarification",
            expected_clarification_contains="不存在的关键词XYZ",
        )
        runner = E2ERunner()
        assertions = runner._check_clarification_case(case, response)
        content_assert = [a for a in assertions if a.name == "clarification_content_match"][0]
        assert content_assert.passed is False

    def test_no_sql_for_clarification(self):
        """反问类不应生成 SQL"""
        response = _make_clarification_response()
        case = E2ECase(id="test", question_zh="q", expected_behavior="clarification")
        runner = E2ERunner()
        assertions = runner._check_clarification_case(case, response)
        no_sql_assert = [a for a in assertions if a.name == "no_sql_for_clarification"][0]
        assert no_sql_assert.passed is True


class TestAssertionsRefusal:
    """refusal 类断言"""

    def test_intent_generated_for_refusal(self):
        """拒绝类：拒绝触发应通过"""
        response = _make_refusal_response()
        case = E2ECase(id="test", question_zh="q", expected_behavior="refusal")
        result = E2ERunner._check_intent_generated(case, response)
        assert result.passed is True
        assert "拒绝" in result.detail

    def test_intent_generated_for_refusal_not_triggered(self):
        """拒绝类：未触发拒绝应失败"""
        response = _make_answer_response()  # answer 类型，没有 refusal
        case = E2ECase(id="test", question_zh="q", expected_behavior="refusal")
        result = E2ERunner._check_intent_generated(case, response)
        assert result.passed is False
        assert "应触发拒绝" in result.detail

    def test_refusal_correct(self):
        """拒绝正确触发"""
        response = _make_refusal_response()
        case = E2ECase(id="test", question_zh="q", expected_behavior="refusal")
        runner = E2ERunner()
        assertions = runner._check_refusal_case(case, response)
        refusal_assert = [a for a in assertions if a.name == "refusal_correct"][0]
        assert refusal_assert.passed is True

    def test_refusal_content_match(self):
        """拒绝内容匹配"""
        response = _make_refusal_response()
        case = E2ECase(
            id="test", question_zh="q",
            expected_behavior="refusal",
            expected_refusal_contains="只读",
        )
        runner = E2ERunner()
        assertions = runner._check_refusal_case(case, response)
        content_assert = [a for a in assertions if a.name == "refusal_content_match"][0]
        assert content_assert.passed is True

    def test_refusal_content_mismatch(self):
        """拒绝内容不匹配"""
        response = _make_refusal_response()
        case = E2ECase(
            id="test", question_zh="q",
            expected_behavior="refusal",
            expected_refusal_contains="不存在的关键词XYZ",
        )
        runner = E2ERunner()
        assertions = runner._check_refusal_case(case, response)
        content_assert = [a for a in assertions if a.name == "refusal_content_match"][0]
        assert content_assert.passed is False

    def test_no_sql_for_refusal(self):
        """拒绝类不应生成 SQL"""
        response = _make_refusal_response()
        case = E2ECase(id="test", question_zh="q", expected_behavior="refusal")
        runner = E2ERunner()
        assertions = runner._check_refusal_case(case, response)
        no_sql_assert = [a for a in assertions if a.name == "no_sql_for_refusal"][0]
        assert no_sql_assert.passed is True


class TestAssertionsDirectSQL:
    """直接 SQL 检测断言"""

    def test_direct_sql_not_detected_normal_path(self):
        """正常链路：SQL 通过 SQLPlan 生成，不应标记为直接 SQL"""
        response = _make_answer_response()
        result = E2ERunner._check_direct_sql(response)
        assert result.passed is True
        assert "SQLPlan" in result.detail

    def test_direct_sql_no_result(self):
        """无执行结果：不标记为直接 SQL"""
        response = AgentResponse(question="q")
        result = E2ERunner._check_direct_sql(response)
        assert result.passed is True

    def test_direct_sql_detected_no_plan(self):
        """有 SQL 但无 plan：应检测为直接 SQL"""
        response = AgentResponse(
            question="q",
            result=SQLResult(
                sql="SELECT * FROM t",
                error="数据库未连接",
            ),
        )
        # 没有 plan → 应检测为直接 SQL
        result = E2ERunner._check_direct_sql(response)
        assert result.passed is False
        assert "缺少 SQLPlan" in result.detail


# ═══════════════════════════════════════════════════════════
# C 类：失败分类
# ═══════════════════════════════════════════════════════════


class TestFailureClassification:
    """断言结果到失败分类的映射"""

    def test_classify_intent_failed(self):
        """intent_generated 断言失败 → intent_failed"""
        assertions = [E2EAssertion("intent_generated", False, "未生成")]
        case = E2ECase(id="test", question_zh="q", expected_behavior="answer")
        response = AgentResponse(question="q")
        runner = E2ERunner()
        categories = runner._classify_failures(case, response, assertions)
        assert "intent_failed" in categories

    def test_classify_wrong_metric(self):
        """expected_metric_hit 断言失败 → wrong_metric"""
        assertions = [E2EAssertion("expected_metric_hit", False, "缺少指标")]
        case = E2ECase(id="test", question_zh="q", expected_behavior="answer")
        response = _make_answer_response()
        runner = E2ERunner()
        categories = runner._classify_failures(case, response, assertions)
        assert "wrong_metric" in categories

    def test_classify_wrong_table(self):
        """expected_table_hit 断言失败 → wrong_table"""
        assertions = [E2EAssertion("expected_table_hit", False, "缺少表")]
        case = E2ECase(id="test", question_zh="q", expected_behavior="answer")
        response = _make_answer_response()
        runner = E2ERunner()
        categories = runner._classify_failures(case, response, assertions)
        assert "wrong_table" in categories

    def test_classify_plan_failed(self):
        """plan_generated 断言失败 → plan_failed"""
        assertions = [E2EAssertion("plan_generated", False, "未生成 SQLPlan")]
        case = E2ECase(id="test", question_zh="q", expected_behavior="answer")
        response = AgentResponse(question="q")
        runner = E2ERunner()
        categories = runner._classify_failures(case, response, assertions)
        assert "plan_failed" in categories

    def test_classify_safety_failed(self):
        """sql_is_readonly 断言失败 → safety_failed"""
        assertions = [E2EAssertion("sql_is_readonly", False, "SQL 非只读")]
        case = E2ECase(id="test", question_zh="q", expected_behavior="answer")
        response = _make_answer_response()
        runner = E2ERunner()
        categories = runner._classify_failures(case, response, assertions)
        assert "safety_failed" in categories

    def test_classify_execution_failed(self):
        """execution_successful 断言失败 → execution_failed"""
        assertions = [E2EAssertion("execution_successful", False, "执行错误")]
        case = E2ECase(id="test", question_zh="q", expected_behavior="answer")
        response = _make_answer_response()
        runner = E2ERunner()
        categories = runner._classify_failures(case, response, assertions)
        assert "execution_failed" in categories

    def test_classify_clarification_mismatch(self):
        """clarification_correct 断言失败 → clarification_mismatch"""
        assertions = [E2EAssertion("clarification_correct", False, "应反问但未反问")]
        case = E2ECase(id="test", question_zh="q", expected_behavior="clarification")
        response = _make_clarification_response()
        runner = E2ERunner()
        categories = runner._classify_failures(case, response, assertions)
        assert "clarification_mismatch" in categories

    def test_classify_refusal_mismatch(self):
        """refusal_correct 断言失败 → refusal_mismatch"""
        assertions = [E2EAssertion("refusal_correct", False, "应拒绝但未拒绝")]
        case = E2ECase(id="test", question_zh="q", expected_behavior="refusal")
        response = AgentResponse(question="q")
        runner = E2ERunner()
        categories = runner._classify_failures(case, response, assertions)
        assert "refusal_mismatch" in categories

    def test_classify_direct_sql_detected(self):
        """direct_sql_detected 断言失败 → direct_sql_detected"""
        assertions = [E2EAssertion("direct_sql_detected", False, "LLM 直接 SQL")]
        case = E2ECase(id="test", question_zh="q", expected_behavior="answer")
        response = _make_answer_response()
        runner = E2ERunner()
        categories = runner._classify_failures(case, response, assertions)
        assert "direct_sql_detected" in categories

    def test_classify_all_pass_no_failures(self):
        """全部断言通过 → 无失败分类"""
        assertions = [
            E2EAssertion("intent_generated", True, "ok"),
            E2EAssertion("plan_generated", True, "ok"),
            E2EAssertion("execution_successful", True, "ok"),
        ]
        case = E2ECase(id="test", question_zh="q", expected_behavior="answer")
        response = _make_answer_response()
        runner = E2ERunner()
        categories = runner._classify_failures(case, response, assertions)
        assert categories == []

    def test_classify_refusal_case_answered_as_answer(self):
        """refusal 类被误当 answer → refusal_mismatch"""
        assertions: list[E2EAssertion] = []
        case = E2ECase(id="test", question_zh="q", expected_behavior="refusal")
        response = _make_answer_response()  # answer 响应，refusal=False
        runner = E2ERunner()
        categories = runner._classify_failures(case, response, assertions)
        assert "refusal_mismatch" in categories


# ═══════════════════════════════════════════════════════════
# D 类：报告生成
# ═══════════════════════════════════════════════════════════


class TestE2EReportGeneration:
    """Markdown + JSON 报告生成"""

    def _make_sample_report(self) -> E2EReport:
        """构造示例报告用于测试"""
        results = [
            E2EResult(
                case_id="test_answer",
                question_zh="测试问题1",
                expected_behavior="answer",
                passed=True,
                assertions=[
                    E2EAssertion("intent_generated", True, "ok"),
                    E2EAssertion("plan_generated", True, "ok"),
                ],
                agent_response=_make_answer_response(),
            ),
            E2EResult(
                case_id="test_refusal",
                question_zh="删除数据",
                expected_behavior="refusal",
                passed=True,
                assertions=[
                    E2EAssertion("refusal_correct", True, "正确拒绝"),
                ],
                agent_response=_make_refusal_response(),
            ),
            E2EResult(
                case_id="test_fail",
                question_zh="失败问题",
                expected_behavior="answer",
                passed=False,
                assertions=[
                    E2EAssertion("execution_successful", False, "执行失败"),
                ],
                failure_categories=["execution_failed"],
                suggestion="加入 regression",
            ),
        ]
        return E2EReport(
            run_id="test_run",
            timestamp="2026-06-12T00:00:00",
            provider="mock",
            model_name="mock",
            cases=results,
            markdown_path="/tmp/report.md",
            json_path="/tmp/report.json",
        )

    def test_summary_statistics(self):
        """报告摘要统计"""
        report = self._make_sample_report()
        s = report.summary
        assert s["total"] == 3
        assert s["passed"] == 2
        assert s["failed"] == 1
        assert s["pass_rate"] == "66.7%"
        assert s["answer_total"] == 2
        assert s["answer_passed"] == 1
        assert s["refusal_total"] == 1
        assert s["refusal_passed"] == 1
        assert s["failure_category_counts"] == {"execution_failed": 1}

    def test_regression_candidates(self):
        """回归候选列表"""
        report = self._make_sample_report()
        candidates = report.regression_candidates
        assert len(candidates) == 1
        assert candidates[0].case_id == "test_fail"
        assert "execution_failed" in candidates[0].failure_categories

    def test_markdown_report_contains_key_sections(self):
        """Markdown 报告包含关键段落"""
        runner = E2ERunner()
        report = self._make_sample_report()
        md = runner._render_markdown(report)
        assert "# LLM E2E" in md
        assert "## 汇总" in md
        assert "## 逐步详情" in md
        assert "## Regression Candidates" in md
        assert "## 安全边界验证" in md
        assert "test_answer" in md
        assert "test_refusal" in md
        assert "test_fail" in md
        assert "execution_failed" in md

    def test_json_report_structure(self):
        """JSON 报告结构完整"""
        runner = E2ERunner()
        report = self._make_sample_report()
        data = runner._report_to_dict(report)
        assert data["run_id"] == "test_run"
        assert data["provider"] == "mock"
        assert len(data["cases"]) == 3
        assert data["summary"]["total"] == 3
        assert len(data["regression_candidates"]) == 1
        # 验证 case 结构
        case = data["cases"][0]
        assert "case_id" in case
        assert "assertions" in case
        assert "agent_response_summary" in case

    def test_write_reports_creates_files(self):
        """写入报告创建文件"""
        tmp_dir = tempfile.mkdtemp()
        try:
            runner = E2ERunner(report_dir=tmp_dir)
            report = self._make_sample_report()
            # 直接调用 _write_reports（但需要替换 report 的路径）
            result = runner._write_reports(report.cases)

            md_path = Path(tmp_dir) / "llm_e2e_eval_latest.md"
            json_path = Path(tmp_dir) / "llm_e2e_eval_latest.json"
            assert md_path.exists()
            assert json_path.exists()

            # 验证 JSON 可解析
            data = json.loads(json_path.read_text(encoding="utf-8"))
            assert data["run_id"] == result.run_id
            assert "cases" in data
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════
# E 类：MockLLMClient 构造
# ═══════════════════════════════════════════════════════════


class TestMockClientConstruction:
    """Mock LLM 客户端构造"""

    def test_build_mock_client_answer_case(self):
        """answer 类 case：两个 mock 响应都应设置"""
        case = E2ECase(
            id="test", question_zh="q",
            expected_behavior="answer",
            mock_intent_response='{"domain": "traffic"}',
            mock_plan_response='{"strategy": "g3_direct"}',
        )
        runner = E2ERunner()
        client = runner._build_mock_client(case)
        assert isinstance(client, MockLLMClient)
        assert "intent_classifier" in client._responses
        assert "sql_planner" in client._responses
        assert "traffic" in client._responses["intent_classifier"]
        assert "g3_direct" in client._responses["sql_planner"]

    def test_build_mock_client_refusal_case(self):
        """refusal 类 case：只有 intent mock 响应"""
        case = E2ECase(
            id="test", question_zh="q",
            expected_behavior="refusal",
            mock_intent_response='{"refusal": true, "refusal_reason": "test"}',
        )
        runner = E2ERunner()
        client = runner._build_mock_client(case)
        assert "intent_classifier" in client._responses
        assert "sql_planner" not in client._responses

    def test_build_mock_client_clarification_case(self):
        """clarification 类 case：只有 intent mock 响应"""
        case = E2ECase(
            id="test", question_zh="q",
            expected_behavior="clarification",
            mock_intent_response='{"needs_clarification": true}',
        )
        runner = E2ERunner()
        client = runner._build_mock_client(case)
        assert "intent_classifier" in client._responses
        assert "sql_planner" not in client._responses


# ═══════════════════════════════════════════════════════════
# F 类：集成测试（Mock LLM + Agent）
# ═══════════════════════════════════════════════════════════


class TestE2EIntegration:
    """Mock LLM + Text2SQLAgent 集成测试"""

    def test_answer_case_integration(self):
        """answer 类用例完整评测流程（mock LLM）"""
        yaml_path = _make_temp_yaml([
            {
                "id": "integration_test_answer",
                "question_zh": "2026年1月每天有多少行程？",
                "expected_behavior": "answer",
                "expected_tables": ["gold.dws_daily_trip_summary", "gold.dim_date"],
                "expected_metrics": ["trip_count"],
                "mock_intent_response": json.dumps({
                    "domain": "traffic",
                    "intent_type": "trend",
                    "metrics": ["trip_count"],
                    "time_range": {
                        "type": "absolute",
                        "start": "2026-01-01",
                        "end": "2026-01-31",
                        "raw_expression": "2026年1月",
                    },
                    "dimensions": ["date"],
                    "filters": [],
                    "needs_clarification": False,
                    "clarification_reason": None,
                    "confidence": 0.95,
                    "raw_question": "2026年1月每天有多少行程？",
                    "human_review": {
                        "requires_review": False,
                        "flagged_fields": [],
                        "reason": None,
                    },
                }, ensure_ascii=False),
                "mock_plan_response": json.dumps({
                    "strategy": "g3_direct",
                    "primary_table": "gold.dws_daily_trip_summary",
                    "joins": [
                        {
                            "table": "gold.dim_date",
                            "on": "gold.dim_date.date = gold.dws_daily_trip_summary.trip_date",
                            "type": "INNER",
                        }
                    ],
                    "where_clauses": [
                        "gold.dim_date.date BETWEEN DATE '2026-01-01' AND DATE '2026-01-31'"
                    ],
                    "group_by": ["gold.dim_date.date"],
                    "order_by": ["gold.dim_date.date"],
                    "aggregations": [
                        {"expr": "SUM(trip_count)", "alias": "trip_count"}
                    ],
                    "limit": None,
                    "downgrade_reason": None,
                    "confidence": 0.95,
                }, ensure_ascii=False),
            }
        ])
        try:
            runner = E2ERunner(cases_path=yaml_path, provider="mock")
            # 单个 case 直接跑
            cases = runner._load_cases()
            assert len(cases) == 1

            result = runner._run_one(cases[0])
            # intent/plan 应正常生成；SQL 应通过安全校验
            # 执行可能失败（DB 不可用为正常离线行为）
            intent_assert = [a for a in result.assertions if a.name == "intent_generated"][0]
            assert intent_assert.passed is True

            plan_assert = [a for a in result.assertions if a.name == "plan_generated"][0]
            assert plan_assert.passed is True

            safety_assert = [a for a in result.assertions if a.name == "sql_passed_safety"][0]
            assert safety_assert.passed is True

            # 不强制要求执行成功（DB 连接依环境而定）
        finally:
            Path(yaml_path).unlink()

    def test_refusal_case_integration(self):
        """refusal 类用例完整评测流程（mock LLM）"""
        yaml_path = _make_temp_yaml([
            {
                "id": "integration_test_refusal",
                "question_zh": "帮我删除异常停车罚单数据",
                "expected_behavior": "refusal",
                "expected_refusal_contains": "只读",
                "mock_intent_response": json.dumps({
                    "refusal": True,
                    "refusal_reason": "当前 Agent 只允许只读问数，不能执行删除或修改数据的操作。",
                }, ensure_ascii=False),
            }
        ])
        try:
            runner = E2ERunner(cases_path=yaml_path, provider="mock")
            cases = runner._load_cases()
            result = runner._run_one(cases[0])

            refusal_assert = [a for a in result.assertions if a.name == "refusal_correct"][0]
            assert refusal_assert.passed is True, f"应为正确拒绝: {result.assertions}"

            content_assert = [a for a in result.assertions if a.name == "refusal_content_match"][0]
            assert content_assert.passed is True

            assert result.passed is True
        finally:
            Path(yaml_path).unlink()

    def test_clarification_case_integration(self):
        """clarification 类用例完整评测流程（mock LLM）"""
        yaml_path = _make_temp_yaml([
            {
                "id": "integration_test_clarification",
                "question_zh": "最近每天有多少行程？",
                "expected_behavior": "clarification",
                "expected_clarification_contains": "时间范围",
                "mock_intent_response": json.dumps({
                    "domain": "traffic",
                    "intent_type": "trend",
                    "metrics": ["trip_count"],
                    "time_range": {
                        "type": "fuzzy",
                        "start": None,
                        "end": None,
                        "raw_expression": "最近",
                    },
                    "dimensions": ["date"],
                    "filters": [],
                    "needs_clarification": True,
                    "clarification_reason": "时间范围不明确，需要用户说明最近指哪一段日期。",
                    "confidence": 0.9,
                    "raw_question": "最近每天有多少行程？",
                    "human_review": {
                        "requires_review": False,
                        "flagged_fields": [],
                        "reason": None,
                    },
                }, ensure_ascii=False),
            }
        ])
        try:
            runner = E2ERunner(cases_path=yaml_path, provider="mock")
            cases = runner._load_cases()
            result = runner._run_one(cases[0])

            clarify_assert = [a for a in result.assertions if a.name == "clarification_correct"][0]
            assert clarify_assert.passed is True, f"应为正确反问: {result.assertions}"

            assert result.passed is True
        finally:
            Path(yaml_path).unlink()

    def test_direct_sql_detection_integration(self):
        """LLM 直接输出 SQL 的检测集成测试"""
        yaml_path = _make_temp_yaml([
            {
                "id": "integration_test_direct_sql",
                "question_zh": "2026年1月每天有多少行程？",
                "expected_behavior": "answer",
                "expected_tables": ["gold.dws_daily_trip_summary"],
                "expected_metrics": ["trip_count"],
                "mock_intent_response": "SELECT * FROM gold.dws_daily_trip_summary",
                # LLM 直接输出 SQL 文本，不是 JSON
            }
        ])
        try:
            runner = E2ERunner(cases_path=yaml_path, provider="mock")
            cases = runner._load_cases()
            result = runner._run_one(cases[0])

            # 应检测到 direct_sql
            assert result.passed is False
            assert "direct_sql_detected" in result.failure_categories
        finally:
            Path(yaml_path).unlink()

    def test_expected_safety_violation_direct_sql_passes_when_detected(self):
        """安全负例：期望 direct SQL 被检测到时，case 应通过。"""
        yaml_path = _make_temp_yaml([
            {
                "id": "integration_test_expected_direct_sql",
                "question_zh": "2026年1月每天有多少行程？",
                "expected_behavior": "safety_violation",
                "expected_failure_categories": ["direct_sql_detected"],
                "mock_intent_response": "SELECT * FROM gold.dws_daily_trip_summary",
            }
        ])
        try:
            runner = E2ERunner(cases_path=yaml_path, provider="mock")
            cases = runner._load_cases()
            result = runner._run_one(cases[0])

            assert result.passed is True
            assert result.failure_categories == []
            assert any(a.name == "safety_violation_detected" and a.passed for a in result.assertions)
        finally:
            Path(yaml_path).unlink()


# ═══════════════════════════════════════════════════════════
# G 类：安全边界验证
# ═══════════════════════════════════════════════════════════


class TestSafetyBoundary:
    """安全边界检查"""

    def test_sql_safety_check_insert_detected(self):
        """包含 INSERT 的 SQL 应被安全校验拒绝"""
        response = _make_answer_response()
        response.result.sql = "INSERT INTO t VALUES (1)"
        runner = E2ERunner()
        result = runner._check_sql_safety(response)
        assert result.passed is False

    def test_sql_safety_check_delete_detected(self):
        """包含 DELETE 的 SQL 应被安全校验拒绝"""
        response = _make_answer_response()
        response.result.sql = "DELETE FROM t WHERE id=1"
        runner = E2ERunner()
        result = runner._check_sql_safety(response)
        assert result.passed is False

    def test_sql_safety_check_select_passes(self):
        """正常 SELECT 应通过安全校验"""
        response = _make_answer_response()
        runner = E2ERunner()
        result = runner._check_sql_safety(response)
        assert result.passed is True

    def test_sql_readonly_with_prefix(self):
        """WITH CTE 开头的只读 SQL 应通过"""
        response = _make_answer_response()
        response.result.sql = "WITH cte AS (SELECT 1) SELECT * FROM cte"
        result = E2ERunner._check_sql_readonly(response)
        assert result.passed is True

    def test_direct_sql_detection_prevents_bypass(self):
        """验证 direct_sql 检测机制：无 plan 有 SQL → 应告警"""
        response = AgentResponse(
            question="q",
            result=SQLResult(
                sql="SELECT * FROM gold.dws_daily_trip_summary WHERE 1=1",
                error=None,
            ),
            # 故意不设置 plan
        )
        result = E2ERunner._check_direct_sql(response)
        assert result.passed is False
        assert "SQLPlan" in result.detail
