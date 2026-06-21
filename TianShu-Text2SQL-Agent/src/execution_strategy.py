"""
SQL 计划执行策略 —— 串行 / 并发执行编排。

职责：
    编排多个 UnifiedResponse 的执行顺序，不参与单个 plan 的执行细节。
    每个 plan 仍独立走 execute_one() 完整链路（sql_plan_to_sql → validate_sql_safety → execute_sql）。

设计约束（Phase 3A）：
    - 不允许 SQL 层跨表 JOIN
    - 不允许 LLM 参与执行策略
    - 不允许绕过 SQLPlan
    - 不允许绕过 sql_plan_to_sql()
    - 不允许绕过 validate_sql_safety()
    - 不允许共享同一个 DuckDB connection 跨线程
    - 并发默认关闭
    - 串行行为必须完全保持兼容
"""

from __future__ import annotations

import concurrent.futures
from abc import ABC, abstractmethod
from typing import Any, Callable

from .ir import (
    ExecutionTrace,
    SQLPlan,
    Strategy,
    UnifiedResponse,
)

# PlanExecutor 工厂类型：每次调用返回一个全新的 PlanExecutor 实例
ExecutorFactory = Callable[[], Any]


class ExecutionStrategy(ABC):
    """执行策略抽象基类。

    策略只负责编排，不参与单个 plan 的安全链路。
    """

    @abstractmethod
    def execute(
        self,
        responses: list[UnifiedResponse],
        executor_factory: ExecutorFactory,
    ) -> list[UnifiedResponse]:
        """
        执行多个 UnifiedResponse 中的所有计划。

        Args:
            responses: 待执行的 UnifiedResponse 列表
            executor_factory: 创建 PlanExecutor 的工厂函数。
                              每次调用应返回一个全新的、独立的 PlanExecutor。
                              对于串行策略，可以复用同一个实例；
                              对于并发策略，每个 worker 必须获取独立实例。

        Returns:
            同一列表（原地修改），每个元素的 result 和 execution_trace 已回填。
        """
        ...


class SerialExecutionStrategy(ExecutionStrategy):
    """串行执行策略 —— 按 index 顺序逐个执行。

    这是默认策略，行为与 PlanExecutor.execute_many_serial() 完全一致。
    """

    def execute(
        self,
        responses: list[UnifiedResponse],
        executor_factory: ExecutorFactory,
    ) -> list[UnifiedResponse]:
        executor = executor_factory()
        for i, ur in enumerate(responses):
            plan_index = i + 1
            sub_plan = ur.plan

            # 跳过无法执行的计划
            if sub_plan is None or sub_plan.strategy == Strategy.NEED_CLARIFICATION:
                ur.execution_trace = ExecutionTrace(
                    plan_index=plan_index,
                    strategy=sub_plan.strategy.value if sub_plan else "",
                    primary_table=sub_plan.primary_table if sub_plan else "",
                    execution_status="failed",
                    error_message=(
                        sub_plan.downgrade_reason if sub_plan else "plan 为空"
                    ),
                )
                continue

            result = executor.execute_one(sub_plan, plan_index=plan_index)
            ur.result = result
            ur.execution_trace = executor.last_trace

        return responses


class ThreadPoolExecutionStrategy(ExecutionStrategy):
    """并发执行策略 —— 使用 ThreadPoolExecutor 并发调度多个独立 plan。

    安全约束：
        - 每个 worker 线程通过 executor_factory 获取独立的 PlanExecutor
        - 独立的 PlanExecutor → 独立的 resolver → 独立的 DuckDB read_only 连接
        - 绝不共享 connection 跨线程

    如果 executor_factory 不可用或无法创建独立连接，策略启动时即失败，
    不会退化成"假并发"。
    """

    def __init__(self, max_workers: int = 2):
        """
        Args:
            max_workers: ThreadPoolExecutor 的最大工作线程数（默认 2）
        """
        if max_workers < 1:
            raise ValueError(f"max_workers 必须 >= 1，当前值: {max_workers}")
        self._max_workers = max_workers

    @property
    def max_workers(self) -> int:
        """返回配置的最大工作线程数（只读）"""
        return self._max_workers

    def execute(
        self,
        responses: list[UnifiedResponse],
        executor_factory: ExecutorFactory,
    ) -> list[UnifiedResponse]:
        """
        使用 ThreadPoolExecutor 并发执行多个计划。

        流程：
            1. 遍历 responses，对每条判断是否需要执行
            2. NEED_CLARIFICATION / plan=None → 直接标记 skip，不提交线程池
            3. 需要执行的 → submit(fn, plan_index, plan) 到线程池
            4. 收集 future 结果，按 plan_index 排序回填
            5. 单个 future 异常不影响其他 future 的结果回填

        Args:
            responses: 待执行的 UnifiedResponse 列表
            executor_factory: 创建独立 PlanExecutor 的工厂函数。
                              并发模式下每个 worker 会调用一次。

        Returns:
            同一列表（原地修改），按原始 plan_index 顺序排列。

        Raises:
            RuntimeError: 如果 executor_factory 返回 None 或抛出异常
        """
        # ── 预扫描：分类需要执行和需要跳过的计划 ──
        to_execute: list[tuple[int, UnifiedResponse]] = []  # (plan_index, ur)
        for i, ur in enumerate(responses):
            plan_index = i + 1
            sub_plan = ur.plan

            if sub_plan is None or sub_plan.strategy == Strategy.NEED_CLARIFICATION:
                # 直接标记跳过，不提交线程池
                ur.execution_trace = ExecutionTrace(
                    plan_index=plan_index,
                    strategy=sub_plan.strategy.value if sub_plan else "",
                    primary_table=sub_plan.primary_table if sub_plan else "",
                    execution_status="failed",
                    error_message=(
                        sub_plan.downgrade_reason if sub_plan else "plan 为空"
                    ),
                )
            else:
                to_execute.append((plan_index, ur))

        # ── 无需执行的直接返回 ──
        if not to_execute:
            return responses

        # ── 验证 factory 可用性（创建测试 executor 后立即清理，防止连接泄漏）──
        _test_executor = None
        try:
            _test_executor = executor_factory()
            if _test_executor is None:
                raise RuntimeError(
                    "executor_factory 返回 None，"
                    "无法创建独立 DuckDB 连接，并发模式不可用"
                )
        except RuntimeError as exc:
            # 统一包装，确保错误消息明确指示并发模式不可用
            if "无法创建独立 DuckDB 连接" in str(exc):
                raise
            raise RuntimeError(
                f"无法创建独立 DuckDB 连接，并发模式不可用: {exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"无法创建独立 DuckDB 连接，并发模式不可用: {exc}"
            ) from exc
        finally:
            # 防御式清理：验证完成后立即释放测试 executor 持有的资源
            if _test_executor is not None:
                if hasattr(_test_executor, "close"):
                    try:
                        _test_executor.close()
                    except Exception:
                        pass
                del _test_executor

        # ── 提交到线程池 ──
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self._max_workers,
        ) as pool:
            future_map: dict[
                concurrent.futures.Future,
                tuple[int, UnifiedResponse],
            ] = {}

            for plan_index, ur in to_execute:
                future = pool.submit(
                    self._execute_in_worker,
                    executor_factory,
                    ur.plan,
                    plan_index,
                )
                future_map[future] = (plan_index, ur)

            # ── 收集结果（单个异常不影响其他）──
            for future in concurrent.futures.as_completed(future_map):
                plan_index, ur = future_map[future]
                try:
                    result, trace = future.result()
                    ur.result = result
                    ur.execution_trace = trace
                except Exception as exc:
                    # 单个 worker 异常 → 记录到对应 UnifiedResponse
                    ur.execution_trace = ExecutionTrace(
                        plan_index=plan_index,
                        strategy=ur.plan.strategy.value if ur.plan else "",
                        primary_table=ur.plan.primary_table if ur.plan else "",
                        execution_status="failed",
                        error_message=f"并发执行异常: {exc}",
                    )

        # ── 确保按原始顺序排列（原地修改已通过索引回填，无需重排）──
        return responses

    @staticmethod
    def _execute_in_worker(
        executor_factory: ExecutorFactory,
        plan: SQLPlan,
        plan_index: int,
    ) -> tuple:
        """
        在独立线程中执行的 worker 函数。

        每个 worker 获取自己的 PlanExecutor 实例，确保：
            - 独立的 resolver 实例
            - 独立的 DuckDB read_only 连接
            - 完整的安全链路（sql_plan_to_sql → validate_sql_safety → execute_sql）

        Args:
            executor_factory: 创建 PlanExecutor 的工厂函数
            plan: 待执行的 SQLPlan
            plan_index: 计划序号

        Returns:
            (SQLResult, ExecutionTrace) 元组
        """
        executor = executor_factory()
        result = executor.execute_one(plan, plan_index=plan_index)
        trace = executor.last_trace
        return result, trace
