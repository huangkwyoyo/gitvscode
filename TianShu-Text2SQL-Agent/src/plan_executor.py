"""
SQL 计划执行器 —— 稳定的执行边界。

职责：
    输入 SQLPlan（或 list[UnifiedResponse]），输出 SQLResult（或回填后的 list[UnifiedResponse]）。
    每个 plan 独立走完整执行链路：
        sql_plan_to_sql() → validate_sql_safety() → resolver.execute_sql()
    并记录 ExecutionTrace 用于调试和回归。

设计约束（Phase A）：
    - 不实现 ThreadPoolExecutor 并行
    - 不实现 DuckDB 多连接并发
    - 不实现 LLM 结果融合
    - 不实现 date merge
    - 不改变 SQL 生成模板
    - 不改变 SQL 安全校验
    - 不改变 G3/G2 规划逻辑
"""

from __future__ import annotations

from typing import Any, Optional

from .ir import (
    ExecutionTrace,
    SQLPlan,
    SQLResult,
    Strategy,
    UnifiedResponse,
)
from .sql_gen import sql_plan_to_sql, validate_sql_safety


class PlanExecutor:
    """
    负责执行 SQLPlan，保证每条 SQL 独立生成、独立校验、独立执行。

    用法：
        executor = PlanExecutor(resolver, context, agent_config)
        result = executor.execute_one(plan)
        responses = executor.execute_many_serial(unified_responses)

    每个执行步骤记录 ExecutionTrace，可通过 last_trace 属性访问最近一次追踪。
    """

    def __init__(
        self,
        resolver: Any,           # TianShuResolver（含 execute_sql 方法）
        context: Any,            # AgentContext（含安全白名单和离线标志）
        agent_config: dict[str, Any] | None = None,
    ):
        """
        Args:
            resolver: TianShuResolver 实例（提供 execute_sql 入口）
            context: AgentContext 实例（提供可用表、JOIN 白名单、禁止关键字等）
            agent_config: Agent 运行时配置（超时时间等）
        """
        self._resolver = resolver
        self._context = context
        self._config = agent_config or {}

        # ── 预加载安全上下文（避免每次执行都重复计算）──
        self._available_tables: Optional[set[str]] = None
        self._join_whitelist: Optional[set[tuple[str, str]]] = None
        self._forbidden_kw: list[str] = []

        if self._context is not None:
            self._available_tables = {
                f"{t.schema}.{t.name}" for t in self._context.available_tables
            }
            self._join_whitelist = set(self._context.join_whitelist)
            self._forbidden_kw = list(self._context.forbidden_sql_keywords)

        # ── 最近一次执行的 trace（供单计划路径访问）──
        self._last_trace: Optional[ExecutionTrace] = None

    @property
    def last_trace(self) -> Optional[ExecutionTrace]:
        """最近一次 execute_one() 产生的 ExecutionTrace（只读）"""
        return self._last_trace

    # ═══════════════════════════════════════════════════════════
    # 公开接口
    # ═══════════════════════════════════════════════════════════

    def execute_one(
        self, plan: SQLPlan, plan_index: int = 1,
    ) -> SQLResult:
        """
        执行单个 SQLPlan，返回 SQLResult。

        完整链路：
            1. sql_plan_to_sql(plan) → SQL 文本
            2. validate_sql_safety(sql) → 安全校验
            3. resolver.execute_sql(sql) → 执行
            4. 记录 ExecutionTrace

        Args:
            plan: 待执行的 SQLPlan
            plan_index: 计划序号（用于 trace 记录，默认 1）

        Returns:
            SQLResult 包含执行结果（列名、数据行、耗时等）。
            如果安全校验失败，SQLResult.error 包含违规详情。
        """
        # ── 初始化 trace ──
        trace = ExecutionTrace(
            plan_index=plan_index,
            strategy=plan.strategy.value if plan.strategy else "",
            primary_table=plan.primary_table or "",
            execution_status="pending",
        )

        # ── Step 1: SQL 生成 ──
        try:
            sql = sql_plan_to_sql(plan)
            trace.generated_sql = sql
        except Exception as exc:
            trace.execution_status = "failed"
            trace.error_message = f"SQL 生成失败: {exc}"
            self._last_trace = trace
            return SQLResult(
                sql="",
                error=trace.error_message,
                source_table=plan.primary_table or "",
            )

        # ── Step 2: 安全校验 ──
        violations = validate_sql_safety(
            sql, self._forbidden_kw,
            available_tables=self._available_tables,
            join_whitelist=self._join_whitelist,
        )
        if violations:
            trace.safety_check_passed = False
            trace.execution_status = "failed"
            trace.error_message = f"安全检查失败: {'; '.join(violations)}"
            self._last_trace = trace
            return SQLResult(
                sql=sql,
                error=trace.error_message,
                source_table=plan.primary_table or "",
            )
        trace.safety_check_passed = True

        # ── Step 3: 执行 SQL ──
        # 防御深度：离线模式阻断
        if self._context is not None and getattr(self._context, "offline", False):
            trace.execution_status = "failed"
            trace.error_message = "Agent 处于离线模式，禁止执行 SQL（安全约束）"
            self._last_trace = trace
            return SQLResult(
                sql=sql,
                error=trace.error_message,
                source_table=plan.primary_table or "",
            )

        if self._resolver is None:
            trace.execution_status = "failed"
            trace.error_message = "数据库未连接（离线模式）"
            self._last_trace = trace
            return SQLResult(
                sql=sql,
                error=trace.error_message,
                source_table=plan.primary_table or "",
            )

        timeout_seconds = self._config.get("safety", {}).get("query_timeout", 30)
        result = self._resolver.execute_sql(
            sql,
            timeout_seconds=timeout_seconds,
            source_table=plan.primary_table or "",
        )

        # ── 回填 trace ──
        trace.row_count = result.row_count
        trace.execution_time_ms = result.execution_time_ms
        if result.error:
            trace.execution_status = "failed"
            trace.error_message = result.error
        else:
            trace.execution_status = "success"

        self._last_trace = trace
        return result

    def execute_many_serial(
        self, responses: list[UnifiedResponse],
    ) -> list[UnifiedResponse]:
        """
        串行执行多个 UnifiedResponse 中的所有计划。

        按 index 顺序逐个执行，每个 plan 独立走完整链路并记录 ExecutionTrace。
        执行结果回填到对应 UnifiedResponse 的 result 和 execution_trace 字段。

        输入顺序即输出顺序——不会因执行时长不同而改变排列。

        Args:
            responses: 待执行的 UnifiedResponse 列表（已有 sub_intent 和 plan）

        Returns:
            同一列表（原地修改），每个元素的 result 和 execution_trace 已回填。
        """
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

            # 执行单个计划
            result = self.execute_one(sub_plan, plan_index=plan_index)

            # 回填结果和 trace
            ur.result = result
            ur.execution_trace = self._last_trace

        return responses
