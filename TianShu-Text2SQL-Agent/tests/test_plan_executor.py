"""
Phase A：PlanExecutor 单元测试和回归测试。

覆盖：
    - 单计划执行（SQL 生成 → 安全校验 → 执行）
    - 多计划串行执行 + ExecutionTrace 回填
    - 安全校验独立执行（第二个 plan 失败不影响第一个）
    - 输出顺序稳定
    - 端到端回归（单指标、同表多指标、跨表多计划）
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.ir import (
    AgentResponse,
    Aggregation,
    Domain,
    ExecutionTrace,
    IntentType,
    JoinPlan,
    QuestionIntent,
    SQLPlan,
    SQLResult,
    Strategy,
    SubIntent,
    TimeRange,
    TimeRangeType,
    UnifiedResponse,
)
from src.plan_executor import PlanExecutor
from src.execution_strategy import (
    SerialExecutionStrategy,
    ThreadPoolExecutionStrategy,
)
from src.sql_gen import sql_plan_to_sql, validate_sql_safety


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_mock_resolver():
    """构造 mock resolver，execute_sql 返回固定结果。"""
    mock = MagicMock()
    mock.execute_sql.return_value = SQLResult(
        sql="SELECT mock FROM mock_table",
        columns=["date", "value"],
        column_types=["DATE", "INTEGER"],
        rows=[("2026-01-01", 100)],
        row_count=1,
        execution_time_ms=5.0,
        source_table="gold.mock_table",
    )
    return mock


def _make_mock_context(offline=False):
    """构造 mock context，含基本安全白名单。"""
    from src.resolver import TableInfo

    mock = MagicMock()
    mock.offline = offline
    mock.available_tables = [
        TableInfo(schema="gold", name="dws_daily_trip_summary"),
        TableInfo(schema="gold", name="dws_daily_crash_summary"),
        TableInfo(schema="gold", name="dim_date"),
    ]
    mock.join_whitelist = [
        ("gold.dws_daily_trip_summary", "gold.dim_date"),
        ("gold.dws_daily_crash_summary", "gold.dim_date"),
    ]
    mock.forbidden_sql_keywords = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
        "CREATE", "TRUNCATE", "PRAGMA",
    ]
    return mock


def _make_g3_trip_plan():
    """构造一个标准 G3 trip 查询计划。"""
    return SQLPlan(
        strategy=Strategy.G3_DIRECT,
        primary_table="gold.dws_daily_trip_summary",
        joins=[
            JoinPlan(
                table="gold.dim_date",
                on="gold.dim_date.date = gold.dws_daily_trip_summary.trip_date",
            ),
        ],
        where_clauses=[
            "gold.dim_date.date BETWEEN DATE '2026-01-01' AND DATE '2026-01-31'",
        ],
        group_by=["gold.dim_date.date"],
        order_by=["gold.dim_date.date"],
        aggregations=[Aggregation(expr="SUM(trip_count)", alias="trip_count")],
        confidence=0.95,
    )


def _make_g3_crash_plan():
    """构造一个标准 G3 crash 查询计划。"""
    return SQLPlan(
        strategy=Strategy.G3_DIRECT,
        primary_table="gold.dws_daily_crash_summary",
        joins=[
            JoinPlan(
                table="gold.dim_date",
                on="gold.dim_date.date = gold.dws_daily_crash_summary.crash_date",
            ),
        ],
        where_clauses=[
            "gold.dim_date.date BETWEEN DATE '2026-01-01' AND DATE '2026-01-31'",
        ],
        group_by=["gold.dim_date.date"],
        order_by=["gold.dim_date.date"],
        aggregations=[Aggregation(expr="SUM(persons_injured)", alias="persons_injured")],
        confidence=0.95,
    )


# ═══════════════════════════════════════════════════════════════
# 单计划执行测试
# ═══════════════════════════════════════════════════════════════


class TestSinglePlanExecution:
    """单计划执行：SQL 生成 → 安全校验 → 执行 → ExecutionTrace"""

    def test_execute_one_generates_sql_and_returns_result(self):
        """输入单个 SQLPlan → 生成 SQL、通过安全校验、调用 resolver 执行"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)

        plan = _make_g3_trip_plan()
        result = executor.execute_one(plan)

        # 返回有效 SQLResult
        assert isinstance(result, SQLResult)
        assert result.error is None or result.error == ""
        assert result.row_count > 0

        # resolver.execute_sql 被调用时传入的 SQL 应包含目标表
        call_args = resolver.execute_sql.call_args
        assert call_args is not None
        passed_sql = call_args[0][0]  # 第一个位置参数是 SQL
        assert passed_sql.startswith("SELECT")
        assert "gold.dws_daily_trip_summary" in passed_sql

    def test_execute_one_sets_execution_trace(self):
        """单计划执行后 last_trace 包含完整执行信息"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)

        plan = _make_g3_trip_plan()
        executor.execute_one(plan)

        trace = executor.last_trace
        assert trace is not None
        assert trace.plan_index == 1
        assert trace.strategy == "g3_direct"
        assert trace.primary_table == "gold.dws_daily_trip_summary"
        assert trace.safety_check_passed is True
        assert trace.execution_status == "success"
        assert trace.row_count > 0
        assert trace.generated_sql.startswith("SELECT")

    def test_execute_one_trace_on_safety_failure(self):
        """安全校验失败时 trace 记录失败状态"""
        context = _make_mock_context()
        # 不提供 resolver → 安全校验失败应独立于执行层
        executor = PlanExecutor(None, context)

        # 使用一个会产生安全问题的 SQLPlan（bare table without schema）
        unsafe_plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="fact_trips",  # 无 schema 前缀
            aggregations=[Aggregation(expr="COUNT(*)", alias="cnt")],
        )
        result = executor.execute_one(unsafe_plan)

        trace = executor.last_trace
        assert trace is not None
        # 安全校验应失败（表名未完全限定）
        assert trace.safety_check_passed is False
        assert trace.execution_status == "failed"
        assert "安全检查失败" in trace.error_message

    def test_execute_one_offline_mode_blocked(self):
        """离线模式下 execute_one 应阻断执行并记录 trace"""
        context = _make_mock_context(offline=True)
        resolver = _make_mock_resolver()
        executor = PlanExecutor(resolver, context)

        plan = _make_g3_trip_plan()
        result = executor.execute_one(plan)

        trace = executor.last_trace
        assert trace is not None
        assert trace.execution_status == "failed"
        assert "离线模式" in trace.error_message
        # resolver 不应被调用来执行
        resolver.execute_sql.assert_not_called()

    def test_execute_one_no_resolver_blocked(self):
        """无 resolver 时也应阻断"""
        context = _make_mock_context(offline=False)
        executor = PlanExecutor(None, context)

        plan = _make_g3_trip_plan()
        result = executor.execute_one(plan)

        trace = executor.last_trace
        assert trace is not None
        assert trace.execution_status == "failed"
        assert "离线模式" in trace.error_message or "未连接" in trace.error_message

    def test_execute_one_with_plan_index(self):
        """plan_index 正确传递到 ExecutionTrace"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)

        executor.execute_one(_make_g3_trip_plan(), plan_index=5)
        assert executor.last_trace.plan_index == 5


# ═══════════════════════════════════════════════════════════════
# 多计划串行执行测试
# ═══════════════════════════════════════════════════════════════


class TestMultiPlanSerialExecution:
    """多计划串行执行：每个 plan 独立执行 + ExecutionTrace 回填"""

    def test_execute_many_serial_fills_results(self):
        """两个 UnifiedResponse → 每个的 result 都被回填"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)

        responses = [
            UnifiedResponse(
                sub_intent=SubIntent(
                    metrics=["trip_count"],
                    domain=Domain.TRAFFIC,
                    planning_table="gold.dws_daily_trip_summary",
                ),
                plan=_make_g3_trip_plan(),
            ),
            UnifiedResponse(
                sub_intent=SubIntent(
                    metrics=["persons_injured"],
                    domain=Domain.SAFETY,
                    planning_table="gold.dws_daily_crash_summary",
                ),
                plan=_make_g3_crash_plan(),
            ),
        ]

        result = executor.execute_many_serial(responses)

        assert len(result) == 2
        for ur in result:
            assert ur.result is not None
            assert ur.result.row_count > 0

    def test_execute_many_serial_fills_execution_trace(self):
        """每个 UnifiedResponse.execution_trace 被回填"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)

        responses = [
            UnifiedResponse(
                sub_intent=SubIntent(
                    metrics=["trip_count"],
                    domain=Domain.TRAFFIC,
                    planning_table="gold.dws_daily_trip_summary",
                ),
                plan=_make_g3_trip_plan(),
            ),
            UnifiedResponse(
                sub_intent=SubIntent(
                    metrics=["persons_injured"],
                    domain=Domain.SAFETY,
                    planning_table="gold.dws_daily_crash_summary",
                ),
                plan=_make_g3_crash_plan(),
            ),
        ]

        executor.execute_many_serial(responses)

        for i, ur in enumerate(responses):
            assert ur.execution_trace is not None, f"计划{i+1} 缺少 execution_trace"
            tr = ur.execution_trace
            assert tr.plan_index == i + 1
            assert tr.execution_status == "success"
            assert tr.safety_check_passed is True
            assert tr.row_count > 0
            assert len(tr.generated_sql) > 0

    def test_execute_many_serial_preserves_order(self):
        """输出顺序必须与输入顺序一致"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)

        responses = [
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["a"], planning_table="gold.table_a"),
                plan=_make_g3_trip_plan(),
            ),
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["b"], planning_table="gold.table_b"),
                plan=_make_g3_crash_plan(),
            ),
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["c"], planning_table="gold.table_c"),
                plan=_make_g3_trip_plan(),
            ),
        ]

        result = executor.execute_many_serial(responses)

        # 顺序不变
        assert result[0].sub_intent.metrics == ["a"]
        assert result[1].sub_intent.metrics == ["b"]
        assert result[2].sub_intent.metrics == ["c"]

    def test_execute_many_serial_skips_null_plan(self):
        """plan 为 None 的 UnifiedResponse 标记为失败但不阻断其他计划"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)

        responses = [
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["a"], planning_table="gold.table_a"),
                plan=_make_g3_trip_plan(),
            ),
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["b"], planning_table="gold.table_b"),
                plan=None,  # 无计划
            ),
        ]

        executor.execute_many_serial(responses)

        # 第一个成功
        assert responses[0].execution_trace.execution_status == "success"
        assert responses[0].result is not None

        # 第二个标记失败
        assert responses[1].execution_trace.execution_status == "failed"
        assert "plan 为空" in responses[1].execution_trace.error_message

    def test_execute_many_serial_skips_clarification_plan(self):
        """strategy=NEED_CLARIFICATION 的计划被跳过但记录 trace"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)

        need_clarify_plan = SQLPlan(
            strategy=Strategy.NEED_CLARIFICATION,
            downgrade_reason="需要确认指标口径",
        )

        responses = [
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["a"], planning_table="gold.table_a"),
                plan=_make_g3_trip_plan(),
            ),
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["b"], planning_table="gold.table_b"),
                plan=need_clarify_plan,
            ),
        ]

        executor.execute_many_serial(responses)

        # 第一个成功
        assert responses[0].execution_trace.execution_status == "success"

        # 第二个跳过但记录
        assert responses[1].execution_trace.execution_status == "failed"
        assert "需要确认指标口径" in responses[1].execution_trace.error_message


# ═══════════════════════════════════════════════════════════════
# 安全校验独立性测试
# ═══════════════════════════════════════════════════════════════


class TestSafetyCheckIndependence:
    """每个 plan 独立走安全校验，一个失败不影响另一个的 trace 记录"""

    def test_second_plan_safety_failure_does_not_affect_first_trace(self):
        """第二个 plan 安全校验失败 → 第一个 plan 的 trace 仍是 success"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)

        # 第一个 plan 正常
        good_plan = _make_g3_trip_plan()

        # 第二个 plan 会有安全问题（裸表名）
        bad_plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="fact_trips",  # 无 schema 前缀 → 安全校验失败
            aggregations=[Aggregation(expr="COUNT(*)", alias="cnt")],
        )

        responses = [
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["trip_count"], planning_table="gold.dws_daily_trip_summary"),
                plan=good_plan,
            ),
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["other"], planning_table="fact_trips"),
                plan=bad_plan,
            ),
        ]

        executor.execute_many_serial(responses)

        # 第一个 plan 的 trace 仍为 success
        trace1 = responses[0].execution_trace
        assert trace1 is not None
        assert trace1.execution_status == "success"
        assert trace1.safety_check_passed is True

        # 第二个 plan 的 trace 为 failed
        trace2 = responses[1].execution_trace
        assert trace2 is not None
        assert trace2.safety_check_passed is False
        assert trace2.execution_status == "failed"

    def test_each_plan_independently_calls_sql_gen(self):
        """验证两个 plan 各自生成独立的 SQL"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)

        plan1 = _make_g3_trip_plan()
        plan2 = _make_g3_crash_plan()

        responses = [
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["trip_count"], planning_table="gold.dws_daily_trip_summary"),
                plan=plan1,
            ),
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["persons_injured"], planning_table="gold.dws_daily_crash_summary"),
                plan=plan2,
            ),
        ]

        executor.execute_many_serial(responses)

        # 两个 SQL 不同
        sql1 = responses[0].execution_trace.generated_sql
        sql2 = responses[1].execution_trace.generated_sql
        assert sql1 != sql2
        assert "dws_daily_trip_summary" in sql1
        assert "dws_daily_crash_summary" in sql2


# ═══════════════════════════════════════════════════════════════
# ExecutionTrace 序列化测试
# ═══════════════════════════════════════════════════════════════


class TestExecutionTraceSerialization:
    """ExecutionTrace.to_dict() 序列化"""

    def test_to_dict(self):
        """验证 to_dict 输出格式正确"""
        trace = ExecutionTrace(
            plan_index=1,
            strategy="g3_direct",
            primary_table="gold.dws_daily_trip_summary",
            generated_sql="SELECT * FROM gold.dws_daily_trip_summary",
            safety_check_passed=True,
            row_count=31,
            execution_status="success",
            execution_time_ms=12.5,
        )

        d = trace.to_dict()
        assert d["plan_index"] == 1
        assert d["strategy"] == "g3_direct"
        assert d["primary_table"] == "gold.dws_daily_trip_summary"
        assert d["safety_check_passed"] is True
        assert d["row_count"] == 31
        assert d["execution_status"] == "success"
        assert d["generated_sql"] == "SELECT * FROM gold.dws_daily_trip_summary"

    def test_default_trace(self):
        """默认构造的 trace 状态为 pending"""
        trace = ExecutionTrace()
        assert trace.execution_status == "pending"
        assert trace.safety_check_passed is False
        assert trace.row_count == 0


# ═══════════════════════════════════════════════════════════════
# 端到端回归测试（通过 agent.py 的完整链路）
# ═══════════════════════════════════════════════════════════════


class TestPlanExecutorEndToEnd:
    """通过 Text2SQLAgent 的完整 ask() 链路验证 PlanExecutor 集成正确"""

    def test_single_metric_path_uses_executor(self):
        """单指标路径 → PlanExecutor 参与执行 → 行为不变"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天有多少行程？")

        # 行为不变：单计划正常执行
        assert not response.clarification_needed
        assert not response.refusal
        assert response.result is not None
        assert response.result.row_count > 0
        assert response.result.error is None or response.result.error == ""
        assert response.chinese_answer is not None

    def test_same_table_multi_metric_path_uses_executor(self):
        """同表多指标路径 → PlanExecutor → 行为不变"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天受伤人数和死亡人数是多少？")

        assert not response.is_multi_plan
        assert not response.clarification_needed
        assert response.result is not None
        assert response.result.row_count > 0
        assert "persons_injured" in response.result.sql
        assert "persons_killed" in response.result.sql

    def test_cross_table_multi_plan_uses_executor(self):
        """跨表多计划路径 → PlanExecutor.execute_many_serial → 行为不变"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天行程数和受伤人数分别是多少？")

        assert response.is_multi_plan
        assert len(response.plans) == 2

        for i, ur in enumerate(response.plans):
            assert ur.result is not None, f"计划{i+1} result 为空"
            assert ur.result.row_count > 0, f"计划{i+1} 返回 0 行"

            # Phase A 新增：execution_trace 必须回填
            assert ur.execution_trace is not None, f"计划{i+1} 缺少 execution_trace"
            tr = ur.execution_trace
            assert tr.execution_status == "success", (
                f"计划{i+1} 执行状态异常: {tr.error_message}"
            )

    def test_cross_table_multi_plan_trace_fields(self):
        """跨表多计划 → 每个子计划有完整的 ExecutionTrace 字段"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天行程数和受伤人数分别是多少？")

        assert response.is_multi_plan
        for i, ur in enumerate(response.plans):
            tr = ur.execution_trace
            assert tr is not None
            assert tr.plan_index == i + 1
            assert len(tr.strategy) > 0
            assert len(tr.primary_table) > 0
            assert tr.generated_sql.startswith("SELECT")
            assert tr.safety_check_passed is True
            assert tr.row_count > 0
            assert tr.execution_status == "success"

    def test_all_existing_tests_still_pass(self):
        """交叉验证：Phase 1-2 所有现有测试行为不变"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()

        # 单指标
        r1 = agent.ask("2026年1月每天有多少行程？")
        assert not r1.clarification_needed and not r1.refusal
        assert r1.intent.metrics == ["trip_count"]

        # 同表多指标
        r2 = agent.ask("2026年1月每天受伤人数和死亡人数是多少？")
        assert not r2.is_multi_plan
        assert len(r2.plan.aggregations) == 2

        # 跨表多指标
        r3 = agent.ask("2026年1月每天行程数和受伤人数分别是多少？")
        assert r3.is_multi_plan
        assert len(r3.plans) == 2

        # 反问
        r4 = agent.ask("最近每天有多少行程？")
        assert r4.clarification_needed is True

        # 拒绝
        r5 = agent.ask("帮我删除异常停车罚单数据")
        assert r5.refusal is True


# ═══════════════════════════════════════════════════════════════
# Phase 3A：execute_many() 策略参数回归测试
# ═══════════════════════════════════════════════════════════════


class TestExecuteManyStrategy:
    """execute_many() 带 strategy 参数的回归测试"""

    def test_execute_many_with_serial_strategy_equals_serial(self):
        """execute_many(strategy=SerialExecutionStrategy()) 与 execute_many_serial() 行为一致"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)

        responses = [
            UnifiedResponse(
                sub_intent=SubIntent(
                    metrics=["trip_count"],
                    planning_table="gold.dws_daily_trip_summary",
                ),
                plan=_make_g3_trip_plan(),
            ),
            UnifiedResponse(
                sub_intent=SubIntent(
                    metrics=["persons_injured"],
                    planning_table="gold.dws_daily_crash_summary",
                ),
                plan=_make_g3_crash_plan(),
            ),
        ]

        executor.execute_many(responses, strategy=SerialExecutionStrategy())

        # 两个 response 均正确回填
        for i, ur in enumerate(responses):
            assert ur.result is not None, f"计划{i+1} result 为空"
            assert ur.result.row_count > 0
            assert ur.execution_trace is not None
            assert ur.execution_trace.execution_status == "success"
            assert ur.execution_trace.plan_index == i + 1

    def test_execute_many_without_strategy_uses_serial(self):
        """execute_many() 不传 strategy 默认使用串行策略"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)

        responses = [
            UnifiedResponse(
                sub_intent=SubIntent(
                    metrics=["trip_count"],
                    planning_table="gold.dws_daily_trip_summary",
                ),
                plan=_make_g3_trip_plan(),
            ),
        ]

        executor.execute_many(responses)

        assert responses[0].result is not None
        assert responses[0].execution_trace.execution_status == "success"

    def test_execute_many_skip_clarification_with_strategy(self):
        """execute_many 带 strategy 时仍正确跳过 NEED_CLARIFICATION 计划"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)

        need_clarify = SQLPlan(
            strategy=Strategy.NEED_CLARIFICATION,
            downgrade_reason="需要确认",
        )

        responses = [
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["a"], planning_table="gold.t_a"),
                plan=_make_g3_trip_plan(),
            ),
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["b"], planning_table="gold.t_b"),
                plan=need_clarify,
            ),
        ]

        executor.execute_many(responses, strategy=SerialExecutionStrategy())

        assert responses[0].execution_trace.execution_status == "success"
        assert responses[1].execution_trace.execution_status == "failed"
        assert "需要确认" in responses[1].execution_trace.error_message

    def test_config_safety_none_does_not_crash(self):
        """config["safety"]=None 时不触发 AttributeError，默认 timeout 生效"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        config = {"safety": None}  # 显式 None——旧代码会崩溃

        executor = PlanExecutor(resolver, context, agent_config=config)
        plan = _make_g3_trip_plan()

        result = executor.execute_one(plan, plan_index=1)
        # 不应崩溃，使用默认 timeout=30 正常执行
        assert result is not None
        assert result.row_count > 0
        assert executor.last_trace.execution_status == "success"

    def test_config_safety_missing_uses_default(self):
        """config 无 safety 键时使用默认值"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        config = {}  # 无 safety 键

        executor = PlanExecutor(resolver, context, agent_config=config)
        plan = _make_g3_trip_plan()

        result = executor.execute_one(plan, plan_index=1)
        assert result is not None
        assert executor.last_trace.execution_status == "success"
