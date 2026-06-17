"""
Phase 3A：执行策略单元测试和集成测试。

覆盖：
    - 默认串行策略
    - 并发关闭时不使用 ThreadPoolExecutor
    - 并发开启时调用多个独立 resolver
    - 结果顺序稳定
    - 单个 future 异常被记录到对应 UnifiedResponse
    - validate_sql_safety 每个 plan 都执行
    - NEED_CLARIFICATION plan 不提交到线程池
    - max_workers 生效
    - fast gate 兼容
"""

import threading
from unittest.mock import MagicMock

import pytest

from src.ir import (
    Aggregation,
    ExecutionTrace,
    JoinPlan,
    SQLPlan,
    SQLResult,
    Strategy,
    SubIntent,
    UnifiedResponse,
)
from src.plan_executor import PlanExecutor
from src.execution_strategy import (
    ExecutionStrategy,
    SerialExecutionStrategy,
    ThreadPoolExecutionStrategy,
)


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _make_mock_resolver():
    """构造 mock resolver，execute_sql 返回固定结果"""
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
    """构造 mock context，含基本安全白名单"""
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
    """构造标准 G3 trip 查询计划"""
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
    """构造标准 G3 crash 查询计划"""
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


def _make_two_responses():
    """构造两个跨表多计划 UnifiedResponse"""
    return [
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


def _make_executor_factory(resolver=None, context=None):
    """创建一个返回 PlanExecutor 的工厂函数"""
    r = resolver or _make_mock_resolver()
    c = context or _make_mock_context()

    def _factory():
        return PlanExecutor(resolver=r, context=c)

    return _factory


# ═══════════════════════════════════════════════════════════════
# 串行策略测试
# ═══════════════════════════════════════════════════════════════


class TestSerialExecutionStrategy:
    """默认串行策略：行为与 execute_many_serial 一致"""

    def test_default_strategy_is_serial(self):
        """execute_many 不传 strategy 时应使用串行策略"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)
        responses = _make_two_responses()

        executor.execute_many(responses)  # 不传 strategy

        # 结果应回填
        for ur in responses:
            assert ur.result is not None
            assert ur.result.row_count > 0
            assert ur.execution_trace is not None
            assert ur.execution_trace.execution_status == "success"

    def test_serial_strategy_fills_results_and_traces(self):
        """串行策略：两个 response 的 result 和 execution_trace 均被回填"""
        strategy = SerialExecutionStrategy()
        factory = _make_executor_factory()
        responses = _make_two_responses()

        strategy.execute(responses, factory)

        for i, ur in enumerate(responses):
            assert ur.result is not None, f"计划{i+1} result 为空"
            assert ur.result.row_count > 0
            assert ur.execution_trace is not None, f"计划{i+1} trace 为空"
            tr = ur.execution_trace
            assert tr.plan_index == i + 1
            assert tr.execution_status == "success"
            assert tr.safety_check_passed is True

    def test_serial_strategy_preserves_order(self):
        """串行策略：输出顺序与输入一致"""
        strategy = SerialExecutionStrategy()
        factory = _make_executor_factory()

        responses = [
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["a"], planning_table="gold.t_a"),
                plan=_make_g3_trip_plan(),
            ),
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["b"], planning_table="gold.t_b"),
                plan=_make_g3_crash_plan(),
            ),
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["c"], planning_table="gold.t_c"),
                plan=_make_g3_trip_plan(),
            ),
        ]

        strategy.execute(responses, factory)

        assert responses[0].sub_intent.metrics == ["a"]
        assert responses[1].sub_intent.metrics == ["b"]
        assert responses[2].sub_intent.metrics == ["c"]

    def test_serial_strategy_skips_null_plan(self):
        """串行策略：plan=None 时标记失败但不阻断其他"""
        strategy = SerialExecutionStrategy()
        factory = _make_executor_factory()

        responses = [
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["a"], planning_table="gold.t_a"),
                plan=_make_g3_trip_plan(),
            ),
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["b"], planning_table="gold.t_b"),
                plan=None,
            ),
        ]

        strategy.execute(responses, factory)

        assert responses[0].execution_trace.execution_status == "success"
        assert responses[1].execution_trace.execution_status == "failed"
        assert "plan 为空" in responses[1].execution_trace.error_message


# ═══════════════════════════════════════════════════════════════
# 并发关闭测试
# ═══════════════════════════════════════════════════════════════


class TestThreadPoolDisabled:
    """parallel_enabled=false 时，行为与串行一致，不使用 ThreadPoolExecutor"""

    def test_parallel_disabled_uses_single_factory_call(self):
        """默认串行策略：executor_factory 只被调用一次（复用同一 executor）"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)
        responses = _make_two_responses()

        factory_calls = [0]

        def _counting_factory():
            factory_calls[0] += 1
            return PlanExecutor(resolver=resolver, context=context)

        executor.execute_many(responses, executor_factory=_counting_factory)

        # 串行策略只需一个 executor 实例
        assert factory_calls[0] == 1

        # 行为正确
        for ur in responses:
            assert ur.result is not None
            assert ur.execution_trace.execution_status == "success"

    def test_serial_strategy_single_factory_call(self):
        """SerialExecutionStrategy：executor_factory 只被调用一次"""
        strategy = SerialExecutionStrategy()
        factory_calls = [0]

        def _counting_factory():
            factory_calls[0] += 1
            return PlanExecutor(
                resolver=_make_mock_resolver(),
                context=_make_mock_context(),
            )

        responses = _make_two_responses()
        strategy.execute(responses, _counting_factory)

        # 串行策略仅调用一次工厂，复用同一个 executor
        assert factory_calls[0] == 1

    def test_parallel_disabled_single_resolver_used(self):
        """串行模式下只使用一个 resolver（不创建多个）"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)
        responses = _make_two_responses()

        executor.execute_many(responses)

        # resolver.execute_sql 被调用 2 次（每个 plan 一次），但使用同一个 resolver
        assert resolver.execute_sql.call_count == 2


# ═══════════════════════════════════════════════════════════════
# 并发开启测试
# ═══════════════════════════════════════════════════════════════


class TestThreadPoolEnabled:
    """parallel_enabled=true 时，并发执行多计划"""

    def test_thread_pool_creates_multiple_factories(self):
        """并发策略：executor_factory 被调用多次（验证 + 每个 worker 各一次）"""
        strategy = ThreadPoolExecutionStrategy(max_workers=2)
        context = _make_mock_context()

        factory_call_count = [0]
        # 记录每次工厂调用所在的线程 ID
        thread_ids = []

        def _counting_factory():
            factory_call_count[0] += 1
            thread_ids.append(threading.current_thread().ident)
            return PlanExecutor(
                resolver=_make_mock_resolver(),
                context=context,
            )

        responses = _make_two_responses()
        strategy.execute(responses, _counting_factory)

        # 工厂至少被调用 1（验证）+ 2（worker）= 3 次
        assert factory_call_count[0] >= 3

        # 结果应全部正确回填
        for ur in responses:
            assert ur.result is not None
            assert ur.execution_trace.execution_status == "success"

    def test_thread_pool_creates_independent_executors(self):
        """并发模式下每个 worker 获得独立的 PlanExecutor"""
        strategy = ThreadPoolExecutionStrategy(max_workers=2)
        context = _make_mock_context()

        # 收集工厂创建的所有 executor
        executors = []

        def _collecting_factory():
            exec = PlanExecutor(
                resolver=_make_mock_resolver(),
                context=context,
            )
            executors.append(exec)
            return exec

        responses = _make_two_responses()
        strategy.execute(responses, _collecting_factory)

        # 创建了多个 executor 实例
        assert len(executors) >= 3
        # 所有 executor 实例互不相同
        unique_ids = {id(e) for e in executors}
        assert len(unique_ids) == len(executors)

    def test_thread_pool_results_order_stable(self):
        """并发模式下结果按 plan_index 稳定排序"""
        strategy = ThreadPoolExecutionStrategy(max_workers=2)

        # 创建延迟不同的 resolver（模拟执行时间不同）
        import time

        resolver_fast = _make_mock_resolver()
        resolver_slow = _make_mock_resolver()
        original_execute_sql = resolver_slow.execute_sql

        def delayed_execute_sql(*args, **kwargs):
            time.sleep(0.1)  # 模拟慢查询
            return original_execute_sql(*args, **kwargs)

        resolver_slow.execute_sql = delayed_execute_sql
        context = _make_mock_context()

        call_idx = [0]

        def _factory():
            call_idx[0] += 1
            r = resolver_fast if call_idx[0] == 1 else resolver_slow
            return PlanExecutor(resolver=r, context=context)

        responses = _make_two_responses()
        strategy.execute(responses, _factory)

        # 顺序必须保持：计划1 → ["trip_count"]，计划2 → ["persons_injured"]
        assert responses[0].sub_intent.metrics == ["trip_count"]
        assert responses[1].sub_intent.metrics == ["persons_injured"]
        assert responses[0].execution_trace.plan_index == 1
        assert responses[1].execution_trace.plan_index == 2

    def test_thread_pool_each_plan_runs_safety_check(self):
        """每个 plan 独立执行 validate_sql_safety"""
        strategy = ThreadPoolExecutionStrategy(max_workers=2)
        responses = _make_two_responses()
        factory = _make_executor_factory()

        strategy.execute(responses, factory)

        for i, ur in enumerate(responses):
            tr = ur.execution_trace
            assert tr.safety_check_passed is True, (
                f"计划{i+1} 安全校验未通过"
            )
            assert tr.generated_sql.startswith("SELECT"), (
                f"计划{i+1} 未生成 SQL"
            )

    def test_thread_pool_skips_clarification_plans(self):
        """NEED_CLARIFICATION 计划不提交线程池，直接标记 skip"""
        strategy = ThreadPoolExecutionStrategy(max_workers=2)
        factory = _make_executor_factory()

        need_clarify_plan = SQLPlan(
            strategy=Strategy.NEED_CLARIFICATION,
            downgrade_reason="需要确认指标口径",
        )

        responses = [
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["a"], planning_table="gold.t_a"),
                plan=_make_g3_trip_plan(),
            ),
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["b"], planning_table="gold.t_b"),
                plan=need_clarify_plan,
            ),
        ]

        strategy.execute(responses, factory)

        # 第一个正常执行
        assert responses[0].execution_trace.execution_status == "success"

        # 第二个直接跳过
        assert responses[1].execution_trace.execution_status == "failed"
        assert "需要确认指标口径" in responses[1].execution_trace.error_message

    def test_thread_pool_max_workers_property(self):
        """max_workers 属性正确存储和返回"""
        strategy = ThreadPoolExecutionStrategy(max_workers=3)
        assert strategy.max_workers == 3

        # 并发执行应正常工作
        factory = _make_executor_factory()
        responses = _make_two_responses()
        strategy.execute(responses, factory)

        for ur in responses:
            assert ur.result is not None
            assert ur.execution_trace.execution_status == "success"

    def test_thread_pool_max_workers_invalid(self):
        """max_workers < 1 应抛出 ValueError"""
        with pytest.raises(ValueError, match="max_workers"):
            ThreadPoolExecutionStrategy(max_workers=0)

    def test_all_plans_are_clarification_no_execution(self):
        """所有计划都是 NEED_CLARIFICATION 时不执行，工厂不被调用"""
        strategy = ThreadPoolExecutionStrategy(max_workers=2)
        factory_calls = [0]

        def _counting_factory():
            factory_calls[0] += 1
            return PlanExecutor(
                resolver=_make_mock_resolver(),
                context=_make_mock_context(),
            )

        responses = [
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["a"], planning_table="gold.t_a"),
                plan=SQLPlan(
                    strategy=Strategy.NEED_CLARIFICATION,
                    downgrade_reason="原因1",
                ),
            ),
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["b"], planning_table="gold.t_b"),
                plan=SQLPlan(
                    strategy=Strategy.NEED_CLARIFICATION,
                    downgrade_reason="原因2",
                ),
            ),
        ]

        strategy.execute(responses, _counting_factory)

        # 所有计划都是 clarification → 提前返回，工厂不被调用
        assert factory_calls[0] == 0

        # 两个 response 的 trace 都标记了失败原因
        assert responses[0].execution_trace.execution_status == "failed"
        assert "原因1" in responses[0].execution_trace.error_message
        assert responses[1].execution_trace.execution_status == "failed"
        assert "原因2" in responses[1].execution_trace.error_message


# ═══════════════════════════════════════════════════════════════
# 并发隔离测试
# ═══════════════════════════════════════════════════════════════


class TestThreadPoolIsolation:
    """并发模式下的隔离性验证"""

    def test_no_shared_connection(self):
        """验证并发模式下不会共享 DuckDB 连接"""
        strategy = ThreadPoolExecutionStrategy(max_workers=2)

        # 每个工厂调用创建不同的 resolver
        resolver_instances = []

        def _factory():
            r = _make_mock_resolver()
            resolver_instances.append(r)
            return PlanExecutor(resolver=r, context=_make_mock_context())

        responses = _make_two_responses()
        strategy.execute(responses, _factory)

        # 创建了多个 resolver 实例
        assert len(resolver_instances) >= 2
        # 两个 resolver 是不同的实例
        assert resolver_instances[0] is not resolver_instances[1]

    def test_single_future_exception_does_not_affect_others(self):
        """一个 worker 异常不影响其他 worker 的结果回填"""
        strategy = ThreadPoolExecutionStrategy(max_workers=2)
        context = _make_mock_context()

        # 使用 thread-local 存储来区分 worker，确保只有一个 worker 失败
        thread_local = threading.local()
        # 使用 plan_index 作为 key 来区分
        fail_plan_index = [1]  # 让 plan_index=1 的 worker 失败

        def _factory():
            return PlanExecutor(
                resolver=_make_mock_resolver(),
                context=context,
            )

        # 通过 monkey-patch execute_one 来模拟特定 plan 的失败
        original_execute_one = PlanExecutor.execute_one

        def _failing_execute_one(self, plan, plan_index=1):
            if plan_index == 1:
                raise RuntimeError("模拟连接失败")
            return original_execute_one(self, plan, plan_index=plan_index)

        PlanExecutor.execute_one = _failing_execute_one

        try:
            responses = _make_two_responses()
            strategy.execute(responses, _factory)

            # 至少有一个成功
            success_count = sum(
                1 for ur in responses
                if ur.execution_trace is not None
                and ur.execution_trace.execution_status == "success"
            )
            assert success_count >= 1, "应至少有一个 worker 成功执行"

            # 至少有一个失败
            fail_count = sum(
                1 for ur in responses
                if ur.execution_trace is not None
                and ur.execution_trace.execution_status == "failed"
            )
            assert fail_count >= 1, "应至少有一个 worker 执行失败"
        finally:
            PlanExecutor.execute_one = original_execute_one

    def test_factory_returns_none_raises_error(self):
        """factory 返回 None 时应抛出 RuntimeError"""
        strategy = ThreadPoolExecutionStrategy(max_workers=2)
        responses = _make_two_responses()

        with pytest.raises(RuntimeError, match="无法创建独立 DuckDB 连接"):
            strategy.execute(responses, lambda: None)

    def test_factory_raises_on_first_call(self):
        """factory 首次调用就抛异常时应抛出 RuntimeError"""
        strategy = ThreadPoolExecutionStrategy(max_workers=2)
        responses = _make_two_responses()

        def _bad_factory():
            raise ConnectionError("数据库文件不存在")

        with pytest.raises(RuntimeError, match="无法创建独立 DuckDB 连接"):
            strategy.execute(responses, _bad_factory)


# ═══════════════════════════════════════════════════════════════
# 集成测试
# ═══════════════════════════════════════════════════════════════


class TestExecutionStrategyIntegration:
    """策略与 PlanExecutor 和 Agent 的集成验证"""

    def test_execute_many_with_serial_strategy(self):
        """PlanExecutor.execute_many() 传入 SerialExecutionStrategy 行为一致"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)
        responses = _make_two_responses()

        executor.execute_many(responses, strategy=SerialExecutionStrategy())

        for ur in responses:
            assert ur.result is not None
            assert ur.execution_trace.execution_status == "success"

    def test_execute_many_without_strategy_uses_serial(self):
        """PlanExecutor.execute_many() 不传 strategy 时默认走串行"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)
        responses = _make_two_responses()

        executor.execute_many(responses)  # 不传 strategy

        # 行为应和 execute_many_serial 完全一致
        for ur in responses:
            assert ur.result is not None
            assert ur.result.row_count == 1
            assert ur.execution_trace.plan_index in (1, 2)
            assert ur.execution_trace.execution_status == "success"

    def test_execute_many_serial_backward_compat(self):
        """execute_many_serial 方法仍可用且行为不变"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)
        responses = _make_two_responses()

        executor.execute_many_serial(responses)

        for i, ur in enumerate(responses):
            assert ur.result is not None
            assert ur.execution_trace.plan_index == i + 1

    def test_execute_many_custom_factory(self):
        """传入自定义 executor_factory 时使用自定义工厂"""
        resolver = _make_mock_resolver()
        context = _make_mock_context()
        executor = PlanExecutor(resolver, context)
        responses = _make_two_responses()

        factory_called = [False]

        def _custom_factory():
            factory_called[0] = True
            return PlanExecutor(resolver=resolver, context=context)

        executor.execute_many(
            responses,
            strategy=SerialExecutionStrategy(),
            executor_factory=_custom_factory,
        )

        assert factory_called[0] is True

    def test_default_agent_uses_serial_execution(self):
        """默认配置下 Text2SQLAgent 使用串行执行"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        strategy = agent._get_execution_strategy()

        assert isinstance(strategy, SerialExecutionStrategy)

    def test_parallel_enabled_creates_thread_pool_strategy(self):
        """parallel_enabled=true 时创建 ThreadPoolExecutionStrategy"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()

        # 临时修改配置
        original_config = dict(agent._agent_config) if agent._agent_config else {}
        agent._agent_config["execution"] = {
            "parallel_enabled": True,
            "max_workers": 3,
        }

        try:
            strategy = agent._get_execution_strategy()
            assert isinstance(strategy, ThreadPoolExecutionStrategy)
            assert strategy.max_workers == 3
        finally:
            # 恢复原配置
            agent._agent_config = original_config

    def test_agent_cross_table_multi_plan_still_works(self):
        """跨表多计划 E2E 在默认配置下行为不变（使用串行策略）"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天行程数和受伤人数分别是多少？")

        assert response.is_multi_plan
        assert len(response.plans) == 2

        for i, ur in enumerate(response.plans):
            assert ur.result is not None, f"计划{i+1} result 为空"
            assert ur.result.row_count > 0
            assert ur.execution_trace is not None
            assert ur.execution_trace.execution_status == "success"

    def test_test_executor_closed_after_validation(self):
        """factory 返回的测试 executor 在验证后被清理——close 被调用"""
        close_called = []
        _factory_calls = []

        class FakeExecutor:
            def __init__(self):
                _factory_calls.append(1)
            def close(self):
                close_called.append(1)
            def execute_one(self, plan, plan_index=1):
                return SQLResult(sql="mock", row_count=5,
                                 columns=["c"], column_types=["INT"],
                                 rows=[(1,)])

        def fake_factory():
            return FakeExecutor()

        plan = _make_g3_trip_plan()
        responses = [
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["a"], planning_table="gold.t_a"),
                plan=plan,
            ),
        ]

        strategy = ThreadPoolExecutionStrategy(max_workers=1)
        strategy.execute(responses, fake_factory)

        # 验证：1 个 worker + 1 个测试 executor 共 2 次 factory 调用
        assert len(_factory_calls) >= 2
        # 测试 executor 的 close 被调用
        assert len(close_called) >= 1, "测试 executor 的 close() 应在验证后被调用"

    def test_test_executor_no_close_method_does_not_crash(self):
        """factory 返回无 close 方法的对象时，验证后不崩溃"""
        class FakeExecutorNoClose:
            def execute_one(self, plan, plan_index=1):
                return SQLResult(sql="mock", row_count=5,
                                 columns=["c"], column_types=["INT"],
                                 rows=[(1,)])

        def fake_factory():
            return FakeExecutorNoClose()

        plan = _make_g3_trip_plan()
        responses = [
            UnifiedResponse(
                sub_intent=SubIntent(metrics=["a"], planning_table="gold.t_a"),
                plan=plan,
            ),
        ]

        strategy = ThreadPoolExecutionStrategy(max_workers=1)
        # 不应抛出异常
        result = strategy.execute(responses, fake_factory)
        assert len(result) == 1
