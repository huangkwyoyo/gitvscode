"""
Text2SQL Agent 主循环。

串联完整链路：
    用户中文问题
    → QuestionIntent（意图分类）
    → 歧义检测 → 反问（如需要）
    → SQLPlan（查询规划）
    → SQL（生成）
    → 执行（DuckDB 只读）
    → 中文解释

用法：
    from src.agent import Text2SQLAgent
    agent = Text2SQLAgent()
    answer = agent.ask("2026年Q1曼哈顿每天多少行程？")
"""

from __future__ import annotations

import atexit
import calendar
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import yaml

from .ir import (
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
from .resolver import TianShuResolver, AgentContext, MetricInfo
from .metric_resolver import MetricResolver
from .ambiguity import detect_ambiguity, load_clarification_rules
from .request_guard import is_write_request, is_forbidden_layer_request
from .plan_executor import PlanExecutor
from .execution_strategy import (
    ExecutionStrategy,
    SerialExecutionStrategy,
    ThreadPoolExecutionStrategy,
)
from .result_merge import merge_results_on_date
from .explainer import explain_result, fuse_results
from .result_fusion import (
    fuse_results_with_llm,
    validate_fusion_output,
    fallback_to_template,
    build_result_fusion_payload,
)
from .result_summary import summarize_sql_result
from .cross_domain_policy import CrossDomainPolicy, CrossDomainDecision
from .llm import LLMClient, LLMRequest, PromptLoader
from .llm_adapter import RefusalDetected
from .llm_pipeline import extract_json_object, question_intent_from_dict, sql_plan_from_dict
from .utils import setup_console_encoding


class Text2SQLAgent:
    """
    TianShu 中文问数分析 Agent。

    启动时：
        1. 加载 config/agent_config.yml（Agent 运行时配置）
        2. 通过 TianShuResolver 加载 TianShu 契约 + 建立 DuckDB 连接
        3. 构建 AgentContext（可用表、指标、规则）

    调用 ask() 方法处理用户的中文问题。
    """

    def __init__(
        self,
        agent_config_path: str = "config/agent_config.yml",
        tianshu_config_path: str = "config/tianshu_target.yml",
        mode: str = "rule",
        llm_client: Optional[LLMClient] = None,
        prompt_loader: Optional[PromptLoader] = None,
    ):
        self._agent_config: dict[str, Any] = {}
        self._context: Optional[AgentContext] = None
        self._resolver: Optional[TianShuResolver] = None
        self._clarification_rules: list = []
        self._mode = mode
        self._llm_client = llm_client
        self._prompt_loader = prompt_loader or PromptLoader()
        self._last_intent_raw: str | None = None   # 最近一次 intent LLM 原始输出（供 ask() 校验失败时保存证据）
        self._last_plan_raw: str | None = None     # 最近一次 plan LLM 原始输出
        self._last_trace_message: str | None = None  # 最近一次诊断消息（如 LLM 融合回退原因）

        if self._mode not in {"rule", "llm"}:
            raise ValueError("mode 只能是 'rule' 或 'llm'")
        if self._mode == "llm" and self._llm_client is None:
            raise ValueError("LLM 模式必须传入 llm_client")

        # 加载配置
        self._load_agent_config(agent_config_path)

        # raw output 失败保存配置（在 _load_agent_config 之后读取，允许配置文件覆写）
        raw_cfg = self._agent_config.get("raw_output", {}) if self._agent_config else {}
        self._raw_output_enabled = raw_cfg.get("enabled", True)
        self._raw_output_dir = Path(raw_cfg.get("dir", "harness/reports"))

        # 初始化 TianShu 连接
        self._init_resolver(tianshu_config_path)
        # Phase A：初始化 PlanExecutor（执行边界，隔离执行细节）
        self._executor: Optional[PlanExecutor] = None
        # 进程退出时自动关闭 DuckDB 连接，防止测试中未调用 close() 导致的连接泄露
        atexit.register(self.close)

    def _load_agent_config(self, config_path: str) -> None:
        """加载 Agent 运行时配置"""
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                self._agent_config = yaml.safe_load(f)

    def _init_resolver(self, tianshu_config_path: str) -> None:
        """初始化 TianShu 解析器并构建上下文"""
        try:
            self._resolver = TianShuResolver(tianshu_config_path)
            self._context = self._resolver.build_context()

            # 加载反问规则
            question_policy = self._resolver._contracts.get("question_policy", {})
            if question_policy:
                self._clarification_rules = load_clarification_rules(question_policy)
        except Exception as exc:
            print(f"[WARN] TianShu 连接初始化失败: {exc}")
            print(f"       Agent 将在离线模式下运行（无数据库连接，禁止执行 SQL）")
            # C-1 修复：显式标记离线模式 + 清空 resolver 防止部分初始化绕过
            self._context = AgentContext(offline=True)
            self._resolver = None  # 确保无残留连接引用

    @property
    def is_ready(self) -> bool:
        """Agent 是否已就绪（可处理查询）"""
        return self._context is not None

    def _get_executor(self) -> PlanExecutor:
        """懒初始化 PlanExecutor（需要 resolver 和 context 就绪）"""
        if self._executor is None:
            self._executor = PlanExecutor(
                resolver=self._resolver,
                context=self._context,
                agent_config=self._agent_config,
            )
        return self._executor

    def _get_execution_strategy(self) -> ExecutionStrategy:
        """
        根据配置创建执行策略。

        execution.parallel_enabled=true → ThreadPoolExecutionStrategy
        否则 → SerialExecutionStrategy（默认）
        """
        exec_cfg = self._agent_config.get("execution", {}) if self._agent_config else {}
        parallel_enabled = exec_cfg.get("parallel_enabled", False)

        if parallel_enabled:
            max_workers = exec_cfg.get("max_workers", 2)
            return ThreadPoolExecutionStrategy(max_workers=max_workers)

        return SerialExecutionStrategy()

    def _create_parallel_executor_factory(self):
        """
        创建用于并发模式的 PlanExecutor 工厂函数。

        每次调用都会创建独立的 TianShuResolver（含独立 DuckDB read_only 连接）
        和独立的 PlanExecutor，确保跨线程无共享连接。

        Returns:
            无参 callable，每次调用返回新的 PlanExecutor 实例

        Raises:
            RuntimeError: 如果 resolver 初始化失败（离线模式等）
        """
        # 捕获创建独立连接所需的配置路径
        if self._resolver is not None and hasattr(self._resolver, "_config_path"):
            tianshu_config_path = str(self._resolver._config_path)
        else:
            tianshu_config_path = "config/tianshu_target.yml"

        agent_config = self._agent_config

        def _factory():
            """在 worker 线程中调用，创建独立 resolver + executor"""
            from .resolver import TianShuResolver

            # 创建独立的 resolver（含独立 DuckDB read_only 连接）
            resolver = TianShuResolver(tianshu_config_path)
            context = resolver.build_context()

            return PlanExecutor(
                resolver=resolver,
                context=context,
                agent_config=agent_config,
            )

        return _factory

    def _fuse_results_with_llm(
        self,
        question: str,
        unified_responses: list[UnifiedResponse],
        merged: Any,  # MergedResult
        cross_domain_decision: Any = None,  # CrossDomainDecision
    ) -> str:
        """
        尝试 LLM 结果融合，失败时自动 fallback 到模板融合（含合并状态前缀）。

        根据 fusion.llm_fusion_enabled 配置决定是否启用 LLM 融合。
        LLM 只接触 ResultSummary / MergedResult 的结构化摘要，
        绝不接触 SQL、DuckDB 或原始大表数据。

        模板融合（默认/fallback）仍会附带合并状态前缀，
        保持与 Phase B2 行为完全向后兼容。

        Args:
            question: 用户原始中文问题
            unified_responses: 统一响应列表（用于 fallback）
            merged: MergedResult 合并结果
            cross_domain_decision: 跨域策略决策（可选，传递给后校验）

        Returns:
            中文解释文本
        """
        # ── 检查是否启用 LLM 融合 ──
        fusion_cfg = self._agent_config.get("fusion", {}) if self._agent_config else {}
        llm_fusion_enabled = fusion_cfg.get("llm_fusion_enabled", False)

        if not llm_fusion_enabled:
            # 默认路径：模板融合（带合并状态前缀）
            return self._template_fusion_with_prefix(question, unified_responses, merged)

        # ── LLM 融合需要 llm_client ──
        if self._llm_client is None:
            self._last_trace_message = "LLM 融合已启用但无 llm_client，回退模板融合"
            return self._template_fusion_with_prefix(question, unified_responses, merged)

        # ── 构建 summaries ──
        summaries: list[Any] = []  # list[ResultSummary]
        for i, ur in enumerate(unified_responses):
            plan_index = i + 1
            try:
                summary = summarize_sql_result(ur, plan_index=plan_index)
                summaries.append(summary)
            except Exception as exc:
                # 单个摘要构建失败不应阻止整体流程
                from .ir import ResultSummary
                summaries.append(
                    ResultSummary(
                        source_plan_index=plan_index,
                        warnings=[f"摘要构建失败: {exc}"],
                    )
                )

        # ── 调用 LLM 融合 ──
        try:
            explanation, used_llm, fallback_reason = fuse_results_with_llm(
                question=question,
                summaries=summaries,
                merged_result=merged,
                merge_status=merged.merge_status.value if merged else "not_attempted",
                warnings=list(merged.merge_warnings) if merged else [],
                llm_client=self._llm_client,
                prompt_loader=self._prompt_loader,
                cross_domain_decision=cross_domain_decision,
            )
        except Exception as exc:
            # 完全意外异常，回退模板
            self._last_trace_message = f"LLM 融合异常: {exc}"
            return self._template_fusion_with_prefix(question, unified_responses, merged)

        # ── 根据结果决定是否使用 LLM 输出 ──
        if used_llm:
            return explanation

        # LLM 融合失败，记录原因并回退模板（带合并状态前缀）
        if fallback_reason:
            self._last_trace_message = f"LLM 融合回退: {fallback_reason}"

        return self._template_fusion_with_prefix(question, unified_responses, merged)

    @staticmethod
    def _template_fusion_with_prefix(
        question: str,
        unified_responses: list[UnifiedResponse],
        merged: Any,  # MergedResult
    ) -> str:
        """
        模板融合 + 合并状态前缀。

        保持与 Phase B2 行为完全向后兼容。
        """
        NL = "\n"
        template_text = fallback_to_template(question, unified_responses)

        if merged is None:
            return template_text

        if merged.merge_status.value == "merged":
            metric_names = [
                m for s in merged.source_summaries for m in s.metrics
            ]
            return (
                f"多个查询结果已按 date 对齐合并展示。"
                f"共 {merged.row_count} 天的数据，"
                f"包含指标：{'、'.join(metric_names)}。{NL}{NL}"
                + template_text
            )
        elif merged.merge_status.value == "skipped":
            return (
                f"由于 {merged.reason}，未进行自动合并，"
                f"以下为并列结果。{NL}{NL}"
                + template_text
            )

        # failed / not_attempted → 直接返回模板文本
        return template_text

    def ask(self, question: str) -> AgentResponse:
        """
        处理用户的中文问题，返回完整的 AgentResponse。

        Args:
            question: 用户的中文问题

        Returns:
            AgentResponse 包含完整的问答链路和中文解释
        """
        response = AgentResponse(question=question)
        response.trace.append(f"[INFO] 收到问题: {question}")

        # ── Step 0.5: 请求安全预检查（rule/llm 共享同一路径）──
        if is_write_request(question):
            response.refusal = True
            response.refusal_reason = "我是只读分析 Agent，不能修改、删除或创建数据。"
            response.trace.append(f"         [REFUSE] {response.refusal_reason}")
            return response

        if is_forbidden_layer_request(question):
            response.refusal = True
            response.refusal_reason = "Bronze/Silver 层不能直接用于业务问数，请改用 Gold 层指标提问。"
            response.trace.append(f"         [REFUSE] {response.refusal_reason}")
            return response

        # ── Step 1: 意图分类 ──
        response.trace.append("[STEP 1] 意图分类...")
        try:
            intent = self._classify_intent(question)
        except RefusalDetected as exc:
            response.refusal = True
            response.refusal_reason = exc.refusal_reason
            response.trace.append(f"         [REFUSE] {exc.refusal_reason}")
            return response
        response.intent = intent
        response.trace.append(f"         领域={intent.domain}, 指标={intent.metrics}, 置信度={intent.confidence:.2f}")

        # ── Step 1.5: 意图歧义前置检查 + IR 结构校验 ──
        # B-5：intent 自身标记的 needs_clarification 优先于结构性校验，
        # 使用 intent 自带的友好反问消息，而非 validate() 的结构错误提示
        if intent.needs_clarification:
            response.clarification_needed = True
            response.clarification_message = (
                intent.clarification_reason or "需要进一步确认您的需求"
            )
            response.trace.append(f"         [CLARIFY] 意图标记需要反问: {response.clarification_message}")
            # 保存证据
            if self._last_intent_raw is not None:
                self._save_raw_output_on_failure(
                    question=question,
                    stage="intent_clarification",
                    prompt_name="intent_classifier",
                    raw_output=self._last_intent_raw,
                    parsed_output=intent.to_dict(),
                    parse_success=True,
                    validation_success=False,
                    error_message=response.clarification_message,
                )
            return response

        # B-5：validate() 仅做结构性检查（domain + metrics 是否可解析）
        intent_errors = intent.validate()
        if intent_errors:
            response.clarification_needed = True
            response.clarification_message = f"抱歉，没能理解您的问题: {'; '.join(intent_errors)}"
            response.trace.append(f"         [CLARIFY] Layer1 结构校验: {response.clarification_message}")
            # 保存证据用于诊断（raw output 在 _classify_intent_llm 中暂存）
            if self._last_intent_raw is not None:
                self._save_raw_output_on_failure(
                    question=question,
                    stage="intent_validation",
                    prompt_name="intent_classifier",
                    raw_output=self._last_intent_raw,
                    parsed_output=intent.to_dict(),
                    parse_success=True,
                    validation_success=False,
                    error_message=response.clarification_message,
                )
            return response

        # ── Step 2: 歧义检测 ──
        response.trace.append("[STEP 2] 歧义检测...")
        ambiguity_threshold = self._agent_config.get("behavior", {}).get("ambiguity_threshold", 0.85)
        needs_clarify, clarify_msg = detect_ambiguity(
            intent, question, self._clarification_rules, ambiguity_threshold
        )
        if needs_clarify:
            response.clarification_needed = True
            response.clarification_message = clarify_msg
            response.trace.append(f"         需要反问: {clarify_msg}")
            return response

        # ── Step 3: SQL 规划（TODO: 接入 LLM）──
        response.trace.append("[STEP 3] SQL 规划...")
        plan = self._plan_query(intent)
        response.plan = plan
        response.trace.append(f"         策略={plan.strategy.value}, 主表={plan.primary_table}")

        if plan.strategy == Strategy.NEED_CLARIFICATION:
            response.clarification_needed = True
            response.clarification_message = plan.downgrade_reason or "需要进一步确认"
            return response

        # ── 预加载 plan 校验所需的上下文变量（SQL 安全校验已由 PlanExecutor 承载）──
        available_tables_set: Optional[set[str]] = None
        join_whitelist_set: Optional[set[tuple[str, str]]] = None
        if self._context:
            available_tables_set = {
                f"{t.schema}.{t.name}" for t in self._context.available_tables
            }
            join_whitelist_set = set(self._context.join_whitelist)

        # ── Phase 2B/2C：跨表多指标 → SubIntent 拆分 + 多计划生成 + 串行执行 ──
        if plan.strategy == Strategy.UNSUPPORTED_MULTI_PLAN:
            response.trace.append("[STEP 3b] 跨表多指标 → SubIntent 拆分...")
            # 重新获取逐指标决策结果（_plan_query_multi_metric 中已经算过一次，
            # 这里需要重新获取以便分组。为保持干净，调用内部方法重新规划）
            per_metric_plans: list[dict[str, Any]] = []
            for metric_name in intent.metrics:
                plan_info = self._determine_single_metric_plan(metric_name, intent)
                per_metric_plans.append(plan_info)

            sub_intents = self._split_into_sub_intents(intent, per_metric_plans)
            response.trace.append(
                f"         拆分为 {len(sub_intents)} 个 SubIntent: "
                + ", ".join(
                    f"[{', '.join(si.metrics)}]→{si.planning_table}"
                    for si in sub_intents
                )
            )

            unified_responses = self._plan_sub_intents(sub_intents, intent)
            response.plans = unified_responses
            response.is_multi_plan = True

            # 填充兼容字段（plan/result 指向第一个子计划）
            if unified_responses:
                response.plan = unified_responses[0].plan

            response.trace.append(
                f"         生成 {len(unified_responses)} 个查询计划"
            )
            for i, ur in enumerate(unified_responses):
                response.trace.append(
                    f"          计划{i+1}: {ur.sub_intent.metrics} → "
                    f"{ur.plan.primary_table if ur.plan else 'N/A'}"
                )

            # ── Phase 2C/3A：多计划执行（PlanExecutor + 策略编排）──
            strategy = self._get_execution_strategy()
            parallel = isinstance(strategy, ThreadPoolExecutionStrategy)
            mode_label = (
                f"并发(max_workers={strategy.max_workers})"
                if parallel else "串行"
            )
            response.trace.append(f"[STEP 4] 多计划执行（{mode_label}）...")
            executor = self._get_executor()
            factory = (
                self._create_parallel_executor_factory()
                if parallel else None
            )
            executor.execute_many(unified_responses, strategy=strategy, executor_factory=factory)

            # 记录每个子计划的执行 trace
            for i, ur in enumerate(unified_responses):
                tr = ur.execution_trace
                if tr:
                    if tr.execution_status == "success":
                        response.trace.append(
                            f"         计划{i+1} 结果: 状态=success, "
                            f"行数={tr.row_count}, 耗时={tr.execution_time_ms}ms"
                        )
                    else:
                        response.trace.append(
                            f"         计划{i+1} 失败: {tr.error_message}"
                        )

            # 填充兼容字段：第一个子计划的结果
            if unified_responses and unified_responses[0].result:
                response.result = unified_responses[0].result

            # Phase 3D: 跨域策略评估（在 date merge 和 fusion 之前）
            response.trace.append("[STEP 5a] 跨域策略评估...")
            cross_domains = CrossDomainPolicy.extract_domains_from_responses(
                unified_responses
            )
            cross_metrics = CrossDomainPolicy.extract_metrics_from_responses(
                unified_responses
            )
            policy = CrossDomainPolicy()
            policy_decision = policy.evaluate(
                domains=cross_domains,
                metrics=cross_metrics,
            )
            response.trace.append(
                f"         跨域策略: {policy_decision.reason}"
            )
            response.trace.append(
                f"         decision: display={policy_decision.allow_display}, "
                f"merge={policy_decision.allow_result_merge}, "
                f"causal={policy_decision.allow_causal_language}, "
                f"clarify={policy_decision.requires_clarification}, "
                f"refusal={policy_decision.refusal}"
            )
            if policy_decision.warnings:
                for w in policy_decision.warnings:
                    response.trace.append(f"         policy warning: {w}")

            # ── 处理 refusal ──
            if policy_decision.refusal:
                response.refusal = True
                response.refusal_reason = policy_decision.reason
                response.chinese_answer = (
                    f"抱歉，无法回答该问题。{policy_decision.reason}"
                )
                response.trace.append(
                    f"[REFUSAL] 跨域策略拒绝: {policy_decision.reason}"
                )
                return response

            # ── 处理 clarification ──
            if policy_decision.requires_clarification:
                response.clarification_needed = True
                response.clarification_message = (
                    f"您的查询涉及多个业务域，需要进一步确认：{policy_decision.reason}"
                )
                response.trace.append(
                    f"[CLARIFY] 跨域策略需要反问: {policy_decision.reason}"
                )
                return response

            # Phase B2: 执行完毕后尝试 date merge，跳过单计划路径，进入融合阶段
            response.trace.append("[DONE] 多计划执行完成")

            # ── 跨域策略控制是否允许 merge ──
            if policy_decision.allow_result_merge:
                response.trace.append("[STEP 5b] 尝试 date merge...")
                merged = merge_results_on_date(unified_responses)

                if merged.merge_status.value == "merged":
                    response.trace.append(
                        f"         date merge 成功: {merged.row_count} 行, "
                        f"列={merged.columns}"
                    )
                    if merged.merge_warnings:
                        response.trace.append(
                            f"         merge warnings: {'; '.join(merged.merge_warnings)}"
                        )
                elif merged.merge_status.value == "skipped":
                    response.trace.append(
                        f"         date merge 跳过: {merged.reason}"
                    )
                elif merged.merge_status.value == "failed":
                    response.trace.append(
                        f"         date merge 失败: {merged.reason}"
                    )
            else:
                response.trace.append(
                    f"[STEP 5b] date merge 跳过（跨域策略禁止）: {policy_decision.reason}"
                )
                from .ir import MergeStatus, MergedResult, ResultSummary as _RS
                # 构造一个 skipped 的 MergedResult，原因来自策略
                merged = MergedResult(
                    merge_status=MergeStatus.SKIPPED,
                    reason=f"跨域策略禁止 merge: {policy_decision.reason}",
                )

            # Phase 3B: 尝试 LLM 结果融合（可配置，默认关闭）
            # 将跨域策略 warning 注入到 merge_warnings 中，确保它们出现在最终回答
            if policy_decision.warnings and merged is not None:
                all_warnings = list(merged.merge_warnings) + policy_decision.warnings
                merged.merge_warnings = all_warnings

            response.chinese_answer = self._fuse_results_with_llm(
                question=question,
                unified_responses=unified_responses,
                merged=merged,
                cross_domain_decision=policy_decision,
            )

            # ── 将策略 warning 追加到最终回答 ──
            if policy_decision.warnings:
                warning_prefix = "\n\n".join(
                    f"⚠️ {w}" for w in policy_decision.warnings
                )
                response.chinese_answer = (
                    warning_prefix + "\n\n" + (response.chinese_answer or "")
                )

            return response

        # ── Step 3.5: IR 校验 —— Layer 2 规划校验（表存在性、JOIN 白名单、降级原因）──
        # 上下文变量已在 Step 3 后预加载，此处直接使用

        plan_errors = plan.validate(
            available_tables=available_tables_set,
            join_whitelist=join_whitelist_set,
        )
        if plan_errors:
            # B-3 修复：plan 校验失败应温和反问，而非硬拒绝
            response.clarification_needed = True
            response.clarification_message = (
                f"查询规划需要确认: {'; '.join(plan_errors)}"
            )
            response.trace.append(f"         [CLARIFY] Layer2 校验: {response.clarification_message}")
            # 保存证据用于诊断（raw output 在 _plan_query_llm 中暂存）
            if self._last_plan_raw is not None:
                self._save_raw_output_on_failure(
                    question=question,
                    stage="plan_validation",
                    prompt_name="sql_planner",
                    raw_output=self._last_plan_raw,
                    parsed_output=plan.to_dict(),
                    parse_success=True,
                    validation_success=False,
                    error_message=response.clarification_message,
                )
            return response

        # ── Step 4-5: SQL 生成 + 安全检查 + 执行（PlanExecutor 封装）──
        # Phase A：执行逻辑已抽离到 PlanExecutor，agent.py 只负责调度
        #   - 主防线: SQLPlan.validate() 已在 Step 3.5 完成 JOIN 白名单校验
        #   - 兜底防线: validate_sql_safety() 在 PlanExecutor 中检查
        response.trace.append("[STEP 4-5] SQL 生成 + 安全检查 + 执行（PlanExecutor）...")
        executor = self._get_executor()
        result = executor.execute_one(plan)
        response.result = result

        # 记录执行 trace 到 AgentResponse
        if executor.last_trace:
            exec_trace = executor.last_trace
            if exec_trace.execution_status == "failed" and not result.error:
                # trace 标记失败但 result 无 error（离线模式等）→ 直接记录
                pass
            response.trace.append(
                f"         状态={exec_trace.execution_status}, "
                f"行数={result.row_count}, 耗时={result.execution_time_ms}ms"
            )
            if not exec_trace.safety_check_passed:
                response.refusal = True
                response.refusal_reason = result.error or "SQL 安全检查失败"
                response.trace.append(f"         [FAIL] {response.refusal_reason}")
                # 保存证据：SQL 本身即 raw_output
                self._save_raw_output_on_failure(
                    question=question,
                    stage="sql_safety",
                    prompt_name="sql_planner",
                    raw_output=exec_trace.generated_sql,
                    parsed_output=plan.to_dict() if plan else {},
                    parse_success=True,
                    validation_success=False,
                    error_message=response.refusal_reason,
                )
                return response

            if result.error:
                response.trace.append(f"         [ERROR] {result.error}")

        # ── Step 6: 中文解释 ──
        response.trace.append("[STEP 6] 生成解释...")
        response.chinese_answer = explain_result(question, result)
        response.trace.append("[DONE] 问答完成")

        return response

    def _classify_intent(self, question: str) -> QuestionIntent:
        """根据当前模式执行意图分类"""
        if self._mode == "llm":
            return self._classify_intent_llm(question)
        return self._classify_intent_rule(question)

    def _classify_intent_llm(self, question: str) -> QuestionIntent:
        """使用 LLM 生成 QuestionIntent（含 refusal 检测）。

        LLM 可能返回两种格式：
            - 格式 A（QuestionIntent）：正常回答或需反问
            - 格式 B（Refusal）：拒绝回答（写操作 / Bronze 直查等）

        Returns:
            校验通过的 QuestionIntent 对象。

        Raises:
            RefusalDetected: LLM 检测到拒绝回答的场景。
        """
        assert self._llm_client is not None
        raw_output = ""
        parsed_output: dict[str, Any] = {}
        response = self._llm_client.complete(
            LLMRequest(
                task="intent_classifier",
                prompt=self._render_llm_prompt(
                    "intent_classifier",
                    {"question": question, "context": self._context_payload()},
                ),
                metadata={"question": question},
            )
        )
        raw_output = response.content
        self._last_intent_raw = raw_output  # 暂存，供 ask() 校验失败时保存证据

        # ── JSON 提取 ──
        try:
            parsed_output = extract_json_object(raw_output)
            parse_success = True
        except Exception as exc:
            self._save_raw_output_on_failure(
                question=question,
                stage="intent",
                prompt_name="intent_classifier",
                raw_output=raw_output,
                parsed_output={},
                parse_success=False,
                validation_success=False,
                error_message=f"JSON 解析失败: {exc}",
            )
            raise

        # ── refusal 检测（预期行为，不算失败，不保存 raw output）──
        if parsed_output.get("refusal") is True and isinstance(parsed_output.get("refusal_reason"), str):
            raise RefusalDetected(
                refusal_reason=parsed_output["refusal_reason"],
                question=question,
            )

        # ── dict → dataclass 转换 ──
        try:
            return question_intent_from_dict(parsed_output)
        except Exception as exc:
            self._save_raw_output_on_failure(
                question=question,
                stage="intent",
                prompt_name="intent_classifier",
                raw_output=raw_output,
                parsed_output=parsed_output,
                parse_success=True,
                validation_success=False,
                error_message=f"QuestionIntent 构造失败: {exc}",
            )
            raise

    # ── 维度提取：中文关键词 → 候选维度英文标识符 ──
    # 严格约束：只负责 NLP 抽取，不决定 fact 表、SQL 字段、join。
    # 候选维度是否可用、落在哪张表、是否需要 join，由后续方法从 semantic_contract 校验。
    _DIMENSION_KEYWORDS: dict[str, str] = {
        "行政区": "borough",
        "borough": "borough",
        "违章类型": "violation_type",
        "车辆类型": "vehicle_type",
        "行程来源": "trip_source",
        "支付类型": "payment_type",
        "区域": "zone_name",
    }

    # ── 维表→维度映射（从 join_keys 推导维表覆盖的维度）──
    # 证据来源：semantic_contract.yml#/g2_facts/*/join_keys
    _DIM_TABLE_TO_DIM: dict[str, str] = {
        "gold.dim_violation_type": "violation_type",
        "gold.dim_taxi_zone": "borough",
        "gold.dim_vehicle": "vehicle_type",
    }

    # ── 维表的分组列映射（(维表, 维度) → 维表上的分组列）──
    _DIM_GROUP_COL: dict[tuple[str, str], str] = {
        ("gold.dim_violation_type", "violation_type"): "violation_code",
        ("gold.dim_taxi_zone", "borough"): "borough",
        ("gold.dim_taxi_zone", "zone_name"): "zone_name",
    }

    # ── Fact 表直接包含的维度列（从 g2_facts note 字段推导）──
    # 证据来源：semantic_contract.yml#/g2_facts/*/note
    _FACT_DIRECT_COLUMNS: dict[str, set[str]] = {
        "gold.fact_crashes": {"borough"},  # note: "直接包含 borough 字段，无需 JOIN 维表获取行政区"
    }

    @classmethod
    def _extract_dimensions_from_question(cls, question: str) -> list[str]:
        """从用户问题中提取候选维度（仅 NLP 抽取，不决定表/列/join）。

        严格约束：
            - 只负责从中文文本中识别维度关键词
            - 不决定 fact 表、不决定 SQL 字段、不决定 join
            - 候选维度是否可用、落在哪张表、是否需要 join，由后续方法校验

        Args:
            question: 用户的中文问题

        Returns:
            候选维度英文标识符列表（去重），不含 "date"
        """
        found: list[str] = []
        question_lower = question.lower()
        for pattern, dim_name in cls._DIMENSION_KEYWORDS.items():
            if pattern.lower() in question_lower:
                if dim_name not in found:
                    found.append(dim_name)
        return found

    def _get_metric_info(self, metric_name: str) -> MetricInfo | None:
        """按名称查找完整的 MetricInfo 对象。

        搜索路径：
            1. context.available_metrics（在线 DuckDB 加载）
            2. _available_metric_infos()（包含离线 config 回退）
        """
        if self._context and self._context.available_metrics:
            for m in self._context.available_metrics:
                if m.name == metric_name:
                    return m
        # 离线 fallback
        for m in self._available_metric_infos():
            if m.name == metric_name:
                return m
        return None

    def _g3_covers_dimensions(
        self, metric_info: MetricInfo, dimensions: list[str],
    ) -> tuple[bool, list[str]]:
        """检查 G3 汇总表是否覆盖用户请求的所有维度。

        证据来源：
            - g3_table → metric_contract.yml g3_table 字段
            - key_dimensions → semantic_contract.yml g3_summary 段

        Args:
            metric_info: 指标信息（含 g3_table）
            dimensions: 用户请求的维度列表

        Returns:
            (是否全覆盖, 缺失的维度列表)。"date" 维度始终视为覆盖。
        """
        g3_table = metric_info.g3_table or metric_info.base_table

        # 若 g3_table 为空，无法判断覆盖 → 视为不覆盖
        if not g3_table:
            return False, [d for d in dimensions if d != "date"]

        # 从 semantic_contract 获取 G3 汇总表的 key_dimensions
        g3_meta = None
        if self._context:
            g3_meta = self._context.g3_summaries.get(g3_table)

        # 若 G3 汇总表未在 semantic_contract 中注册 → 不覆盖（不猜字段）
        if g3_meta is None:
            return False, [d for d in dimensions if d != "date"]

        covered_dims = set(g3_meta.key_dimensions)
        # "date" 维度始终视为覆盖（所有 G3 表都以日期为 grain）
        covered_dims.add("date")

        missing: list[str] = []
        for dim in dimensions:
            if dim not in covered_dims:
                missing.append(dim)

        return len(missing) == 0, missing

    def _build_g2_plan(
        self,
        metric_info: MetricInfo,
        intent: QuestionIntent,
        missing_dims: list[str],
    ) -> SQLPlan:
        """构建 G2 降级查询计划。

        严格按证据链验证每个字段来源：
            - base_table → metric_contract.yml
            - join_keys → semantic_contract.yml g2_facts 段
            - group_by 列 → g2_facts note + join_keys 推导
            - downgrade_reason → 中文，说明为什么降级、缺失哪个维度

        Args:
            metric_info: 指标信息
            intent: 用户查询意图
            missing_dims: G3 不覆盖的维度（不含 "date"）

        Returns:
            SQLPlan，策略为 G2_FACT / G2_FACT_JOIN / NEED_CLARIFICATION
        """
        g2_table = metric_info.base_table

        # ── 校验 1: base_table 必须非空 ──
        if not g2_table:
            return SQLPlan(
                strategy=Strategy.NEED_CLARIFICATION,
                downgrade_reason=(
                    f"指标 '{metric_info.name}' 的 base_table 为空，"
                    f"无法确定 G2 事实表（需检查 metric_contract.yml）"
                ),
            )

        # ── 校验 2: G2 事实表必须在 semantic_contract 中注册 ──
        g2_meta = None
        if self._context:
            g2_meta = self._context.g2_facts.get(g2_table)

        if g2_meta is None:
            return SQLPlan(
                strategy=Strategy.NEED_CLARIFICATION,
                downgrade_reason=(
                    f"G2 事实表 '{g2_table}' 未在 semantic_contract.yml "
                    f"g2_facts 段中注册，无法确定 JOIN 键和列信息"
                ),
            )

        # ── 确定日期 JOIN 键（所有 G2 fact 表都需通过 dim_date 过滤日期）──
        date_join_key: str | None = None
        date_dim_col: str | None = None
        for key_col, dim_ref in g2_meta.join_keys.items():
            if "dim_date" in dim_ref:
                date_join_key = key_col
                # dim_ref 格式: "gold.dim_date.date_key"
                date_dim_col = dim_ref.split(".")[-1] if "." in dim_ref else dim_ref
                break

        joins: list[JoinPlan] = []
        group_by: list[str] = []
        where_clauses: list[str] = []

        # ── 日期维度：通过 dim_date 过滤 ──
        if date_join_key and date_dim_col:
            joins.append(JoinPlan(
                table="gold.dim_date",
                on=f"gold.dim_date.{date_dim_col} = {g2_table}.{date_join_key}",
            ))
            group_by.append("gold.dim_date.date")

        if intent.time_range and intent.time_range.type == TimeRangeType.ABSOLUTE:
            where_clauses.append(
                f"gold.dim_date.date BETWEEN DATE '{intent.time_range.start}' "
                f"AND DATE '{intent.time_range.end}'"
            )

        # ── 非日期维度：逐一校验是否能从 G2 fact 或其维表获取 ──
        for dim in missing_dims:
            if dim == "date":
                continue

            # 检查 fact 表是否直接包含该维度列（证据来自 g2_facts note 字段）
            if self._fact_has_column(g2_table, dim):
                group_by.append(f"{g2_table}.{dim}")
                continue

            # 需要 JOIN：在 join_keys 中查找匹配的维表
            join_resolved = False
            for key_col, dim_ref in g2_meta.join_keys.items():
                # dim_ref 格式: "gold.dim_violation_type.violation_code"
                parts = dim_ref.split(".")
                if len(parts) >= 2:
                    dim_table = ".".join(parts[:2])  # gold.dim_violation_type
                    dim_col = parts[2] if len(parts) > 2 else parts[1]

                    # 检查此维表是否覆盖缺失维度
                    if self._dim_table_covers(dim_table, dim):
                        group_col = self._resolve_dim_group_col(dim_table, dim, dim_col)
                        joins.append(JoinPlan(
                            table=dim_table,
                            on=f"{dim_table}.{dim_col} = {g2_table}.{key_col}",
                        ))
                        group_by.append(f"{dim_table}.{group_col}")
                        join_resolved = True
                        break

            if not join_resolved:
                return SQLPlan(
                    strategy=Strategy.NEED_CLARIFICATION,
                    downgrade_reason=(
                        f"维度 '{dim}' 无法从 G2 事实表 '{g2_table}' 或其 join_keys "
                        f"（{list(g2_meta.join_keys.keys())}）中解析到对应维表，"
                        f"请检查 semantic_contract.yml g2_facts 段"
                    ),
                )

        # ── 生成降级原因 ──
        g3_table = metric_info.g3_table or "未知"
        if not metric_info.g3_available:
            downgrade_reason = (
                f"指标 '{metric_info.name}' 无 G3 汇总表（g3_available=false），"
                f"直接使用 G2 事实表 {g2_table}"
            )
        else:
            missing_str = "、".join(d for d in missing_dims if d != "date")
            g3_dims = (
                self._context.g3_summaries[g3_table].key_dimensions
                if self._context and g3_table in self._context.g3_summaries
                else []
            )
            downgrade_reason = (
                f"G3 汇总表 {g3_table} 不包含 {missing_str} 维度"
                f"（key_dimensions={g3_dims}），降级到 G2 事实表 {g2_table}"
            )

        # ── 构建聚合表达式 ──
        aggregation_expr = self._normalize_aggregation_expr(
            metric_info.aggregation, metric_info.name
        )

        # ── 确定策略类型 ──
        # 只有 dim_date JOIN → G2_FACT；有额外维表 JOIN → G2_FACT_JOIN
        strategy = Strategy.G2_FACT_JOIN if len(joins) > 1 else Strategy.G2_FACT

        return SQLPlan(
            strategy=strategy,
            primary_table=g2_table,
            joins=joins,
            where_clauses=where_clauses,
            group_by=group_by,
            order_by=group_by[:1] if group_by else [],
            aggregations=[Aggregation(expr=aggregation_expr, alias=metric_info.name)],
            downgrade_reason=downgrade_reason,
            confidence=0.90,
        )

    @classmethod
    def _fact_has_column(cls, fact_table: str, dimension: str) -> bool:
        """检查 G2 事实表是否直接包含某维度列。

        证据来源：semantic_contract.yml g2_facts 段的 note 字段。
        例如 fact_crashes 的 note 说"直接包含 borough 字段"。
        同时查 _FACT_DIRECT_COLUMNS 硬编码表作为补充。
        """
        direct = cls._FACT_DIRECT_COLUMNS.get(fact_table, set())
        return dimension in direct

    @classmethod
    def _dim_table_covers(cls, dim_table: str, dimension: str) -> bool:
        """检查维表是否覆盖指定维度。

        证据来源：semantic_contract.yml g2_facts 段的 join_keys。
        从 join_keys 的维表引用推导维表与维度的关系。
        """
        mapped_dim = cls._DIM_TABLE_TO_DIM.get(dim_table)
        return mapped_dim == dimension

    @classmethod
    def _resolve_dim_group_col(cls, dim_table: str, dimension: str, fallback: str) -> str:
        """解析维表上的分组列名。

        优先从 _DIM_GROUP_COL 映射表查找，找不到则用 join key 列名。
        """
        return cls._DIM_GROUP_COL.get((dim_table, dimension), fallback)

    def _classify_intent_rule(self, question: str) -> QuestionIntent:
        """
        规则版意图分类。

        从用户问题中识别指标、时间范围和多维度分组需求。
        非 date 维度通过 _extract_dimensions_from_question() 提取，
        由后续 _plan_query_rule() 校验维度是否可满足。
        """
        if self._has_ambiguous_amount(question):
            return QuestionIntent(
                needs_clarification=True,
                clarification_reason=(
                    "您提到的“金额”可能指车费收入、标准罚款金额或 TIF 支付金额，请明确要查询哪一种。"
                ),
                confidence=1.0,
                raw_question=question,
            )

        all_metrics = self._detect_all_metrics(question)
        if not all_metrics:
            return QuestionIntent(
                needs_clarification=True,
                clarification_reason="暂未识别到已注册指标，请明确要查询的指标。",
                confidence=0.0,
                raw_question=question,
            )

        # ── 提取候选维度（仅 NLP 抽取，不绑定表/列）──
        extra_dims = self._extract_dimensions_from_question(question)

        # 主 domain 取最高置信度指标的 domain
        primary_domain = all_metrics[0]["domain"]

        time_range = self._parse_month_range(question)
        if time_range.type == TimeRangeType.FUZZY:
            return QuestionIntent(
                domain=primary_domain,
                intent_type=IntentType.TREND,
                metrics=[m["metric"] for m in all_metrics],
                time_range=time_range,
                dimensions=["date"] + extra_dims,
                needs_clarification=True,
                clarification_reason="请明确查询时间范围，例如“2026年1月”或“2026年Q1”。",
                confidence=0.9,
                raw_question=question,
            )

        return QuestionIntent(
            domain=primary_domain,
            intent_type=IntentType.TREND,
            metrics=[m["metric"] for m in all_metrics],
            time_range=time_range,
            dimensions=["date"] + extra_dims,
            confidence=0.95,
            raw_question=question,
        )

    def _plan_query(self, intent: QuestionIntent) -> SQLPlan:
        """根据当前模式执行 SQL 规划"""
        if self._mode == "llm":
            return self._plan_query_llm(intent)
        return self._plan_query_rule(intent)

    def _plan_query_llm(self, intent: QuestionIntent) -> SQLPlan:
        """使用 LLM 生成 SQLPlan"""
        assert self._llm_client is not None
        raw_output = ""
        parsed_output: dict[str, Any] = {}
        question = intent.raw_question or str(intent.metrics)
        response = self._llm_client.complete(
            LLMRequest(
                task="sql_planner",
                prompt=self._render_llm_prompt(
                    "sql_planner",
                    {"intent": intent.to_dict(), "context": self._context_payload()},
                ),
                metadata={"metrics": intent.metrics},
            )
        )
        raw_output = response.content
        self._last_plan_raw = raw_output  # 暂存，供 ask() 校验失败时保存证据

        # ── JSON 提取 ──
        try:
            parsed_output = extract_json_object(raw_output)
            parse_success = True
        except Exception as exc:
            self._save_raw_output_on_failure(
                question=question,
                stage="plan",
                prompt_name="sql_planner",
                raw_output=raw_output,
                parsed_output={},
                parse_success=False,
                validation_success=False,
                error_message=f"JSON 解析失败: {exc}",
            )
            raise

        # ── dict → dataclass 转换 ──
        try:
            return sql_plan_from_dict(parsed_output)
        except Exception as exc:
            self._save_raw_output_on_failure(
                question=question,
                stage="plan",
                prompt_name="sql_planner",
                raw_output=raw_output,
                parsed_output=parsed_output,
                parse_success=True,
                validation_success=False,
                error_message=f"SQLPlan 构造失败: {exc}",
            )
            raise

    @staticmethod
    def _extract_plan_info_from_sqlplan(
        metric_name: str, plan: SQLPlan, domain=None,
    ) -> dict[str, Any]:
        """从 SQLPlan 对象中提取 planning_info dict。

        用于 _determine_single_metric_plan() 统一 G2 降级路径的返回格式。
        domain 参数（Phase 4 新增）：跨域策略需要知道每个指标的所属业务域。
        """
        return {
            "metric": metric_name,
            "strategy": plan.strategy,
            "planning_table": plan.primary_table or "",
            "aggregation": (
                plan.aggregations[0]
                if plan.aggregations
                else Aggregation(expr="", alias=metric_name)
            ),
            "group_by": plan.group_by,
            "where_clauses": plan.where_clauses,
            "joins": plan.joins,
            "downgrade_reason": plan.downgrade_reason,
            "domain": domain,
        }

    def _determine_single_metric_plan(
        self, metric_name: str, intent: QuestionIntent,
    ) -> dict[str, Any]:
        """对单个指标执行完整的 G3/G2 策略决策。

        从 _plan_query_rule() 中提取单指标决策逻辑，返回 planning_info dict
        供合并条件检查使用。

        Returns:
            {
                "metric": str,              # 指标名
                "strategy": Strategy,       # G3_DIRECT / G2_FACT / G2_FACT_JOIN / NEED_CLARIFICATION
                "planning_table": str,      # 最终使用的表（策略选择后）
                "aggregation": Aggregation, # 聚合表达式
                "group_by": list[str],      # GROUP BY 列
                "where_clauses": list[str], # WHERE 条件
                "joins": list[JoinPlan],    # JOIN 计划
                "downgrade_reason": str | None,  # 降级原因
            }
        """
        metric_info = self._get_metric_info(metric_name)
        dimensions = intent.dimensions if intent.dimensions else ["date"]

        # Phase 4：解析指标所属业务域（跨域策略需要此信息）
        _metric_domain = None
        if metric_info is not None and metric_info.domain:
            try:
                _metric_domain = Domain(metric_info.domain)
            except ValueError:
                _metric_domain = intent.domain if intent.domain else None
        if _metric_domain is None:
            _metric_domain = intent.domain if intent.domain else None

        # ── 情况 0: G3 不可用 → 直接走 G2 ──
        if metric_info is not None and not metric_info.g3_available:
            g2_plan = self._build_g2_plan(metric_info, intent, dimensions)
            return self._extract_plan_info_from_sqlplan(
                metric_name, g2_plan, domain=_metric_domain,
            )

        config = self._resolve_metric_table_mapping(metric_name)

        if config is None:
            # table mapping 失败但 metric_info 存在 → 尝试 G2
            if metric_info is not None:
                g2_plan = self._build_g2_plan(metric_info, intent, dimensions)
                return self._extract_plan_info_from_sqlplan(
                    metric_name, g2_plan, domain=_metric_domain,
                )
            return {
                "metric": metric_name,
                "strategy": Strategy.NEED_CLARIFICATION,
                "planning_table": "",
                "aggregation": Aggregation(expr="", alias=metric_name),
                "group_by": [],
                "where_clauses": [],
                "joins": [],
                "downgrade_reason": (
                    f"指标 '{metric_name}' 暂未纳入规则模式，"
                    f"请明确或等待接入 LLM 规划器"
                ),
                "domain": _metric_domain,
            }

        # ── 情况 2: G3 可用，检查维度覆盖 ──
        if metric_info is not None and metric_info.g3_available:
            covered, missing = self._g3_covers_dimensions(metric_info, dimensions)
            if covered:
                # G3 覆盖所有维度 → G3_DIRECT
                g3_table = metric_info.g3_table or config["table"]
                date_col = config["date_col"]
                aggregation_expr = config["aggregation_expr"]
                return {
                    "metric": metric_name,
                    "strategy": Strategy.G3_DIRECT,
                    "planning_table": g3_table,
                    "aggregation": Aggregation(expr=aggregation_expr, alias=metric_name),
                    "group_by": ["gold.dim_date.date"],
                    "domain": _metric_domain,
                    "where_clauses": [
                        (
                            f"gold.dim_date.date BETWEEN DATE '{intent.time_range.start}' "
                            f"AND DATE '{intent.time_range.end}'"
                        )
                    ],
                    "joins": [
                        JoinPlan(
                            table="gold.dim_date",
                            on=f"gold.dim_date.date = {g3_table}.{date_col}",
                        )
                    ],
                    "downgrade_reason": None,
                }
            else:
                # G3 不覆盖某些维度 → 降级 G2
                g2_plan = self._build_g2_plan(metric_info, intent, missing)
                return self._extract_plan_info_from_sqlplan(
                    metric_name, g2_plan, domain=_metric_domain,
                )

        # ── 情况 3: metric_info 为空 → 使用配置走 G3_DIRECT（向后兼容）──
        table = config["table"]
        date_col = config["date_col"]
        aggregation_expr = config["aggregation_expr"]
        return {
            "metric": metric_name,
            "strategy": Strategy.G3_DIRECT,
            "planning_table": table,
            "aggregation": Aggregation(expr=aggregation_expr, alias=metric_name),
            "group_by": ["gold.dim_date.date"],
            "domain": _metric_domain,
            "where_clauses": [
                (
                    f"gold.dim_date.date BETWEEN DATE '{intent.time_range.start}' "
                    f"AND DATE '{intent.time_range.end}'"
                )
            ],
            "joins": [
                JoinPlan(
                    table="gold.dim_date",
                    on=f"gold.dim_date.date = {table}.{date_col}",
                )
            ],
            "downgrade_reason": None,
        }

    @staticmethod
    def _check_multi_metric_merge_conditions(
        plans: list[dict[str, Any]],
    ) -> tuple[bool, str]:
        """检查多个指标的查询计划是否可合并为单 SQL。

        六项合并条件（必须全部满足）：
            1. strategy 一致           — 都走 G3_DIRECT 或都走 G2_FACT
            2. planning_table 一致     — 策略选择后的最终表相同
            3. group_by 一致           — 分组维度相同
            4. where_clauses 一致      — 过滤条件相同
            5. join path 一致          — JOIN 的表列表相同
            6. grain 一致              — 隐含在 group_by 中

        Args:
            plans: _determine_single_metric_plan() 返回的 planning_info 列表

        Returns:
            (True, "") 表示可合并
            (False, "原因描述") 表示不可合并
        """
        if len(plans) <= 1:
            return True, ""

        base = plans[0]

        # 1. strategy 一致
        for i, p in enumerate(plans):
            if base["strategy"] == Strategy.NEED_CLARIFICATION:
                return False, f"指标 '{p['metric']}' 无法规划"
            if p["strategy"] == Strategy.NEED_CLARIFICATION:
                return False, f"指标 '{p['metric']}' 无法规划"

        for i, p in enumerate(plans[1:], 1):
            # 1. strategy 一致
            if base["strategy"] != p["strategy"]:
                return False, (
                    f"指标 '{base['metric']}'({base['strategy'].value}) 与 "
                    f"'{p['metric']}'({p['strategy'].value}) 的 strategy 不一致"
                )

            # 2. planning_table 一致
            if base["planning_table"] != p["planning_table"]:
                return False, (
                    f"指标 '{base['metric']}' 在表 {base['planning_table']}，"
                    f"'{p['metric']}' 在表 {p['planning_table']}，planning_table 不一致"
                )

            # 3. group_by 一致
            if base["group_by"] != p["group_by"]:
                return False, (
                    f"指标 '{base['metric']}' 与 '{p['metric']}' 的 group_by 不一致"
                )

            # 4. where_clauses 一致
            if base["where_clauses"] != p["where_clauses"]:
                return False, (
                    f"指标 '{base['metric']}' 与 '{p['metric']}' 的 where_clauses 不一致"
                )

            # 5. join path 一致（比较 JOIN 表列表）
            base_join_tables = sorted([j.table for j in (base["joins"] or [])])
            p_join_tables = sorted([j.table for j in (p["joins"] or [])])
            if base_join_tables != p_join_tables:
                return False, (
                    f"指标 '{base['metric']}' 与 '{p['metric']}' 的 join path 不一致"
                )

            # 6. grain 一致（隐含在 group_by 中，已通过检查 3 覆盖）

        return True, ""

    def _plan_query_multi_metric(self, intent: QuestionIntent) -> SQLPlan:
        """多指标查询规划：逐个决策 → 合并校验 → 生成单 SQLPlan。

        流程：
            1. 对每个指标调用 _determine_single_metric_plan()
            2. 检查 6 项合并条件
            3. 可合并 → 以第一个 plan 为模板，聚合所有 Aggregation
            4. 不可合并 → 返回 NEED_CLARIFICATION + UNSUPPORTED_MULTI_METRIC
        """
        # 1. 逐个决策
        per_metric_plans = []
        for metric_name in intent.metrics:
            plan_info = self._determine_single_metric_plan(metric_name, intent)
            per_metric_plans.append(plan_info)

        # 2. 检查合并条件
        can_merge, reason = self._check_multi_metric_merge_conditions(
            per_metric_plans
        )

        if not can_merge:
            # 收集指标名和表名用于生成清晰的错误消息
            metric_names = [p["metric"] for p in per_metric_plans]
            table_names = [p["planning_table"] or "未知" for p in per_metric_plans]

            # ── Phase 2A：显式跨表检测 ──
            # 判断是否属于跨表场景（同一指标在不同 planning_table）
            unique_tables = set(t for t in table_names if t and t != "未知")
            is_cross_table = len(unique_tables) > 1

            if is_cross_table:
                # 跨表多指标：显式标记，Phase 2B 将在此处拆分为 SubIntent
                return SQLPlan(
                    strategy=Strategy.UNSUPPORTED_MULTI_PLAN,
                    downgrade_reason=(
                        f"[cross_table_multi_metric] 已识别 {len(metric_names)} 个指标"
                        f"（{', '.join(metric_names)}），"
                        f"分布在 {len(unique_tables)} 张表"
                        f"（{', '.join(sorted(unique_tables))}），"
                        f"当前规则模式暂不支持跨表融合。"
                        f"原因: {reason}"
                        f"。建议分别查询每个指标。"
                    ),
                )

            # 其他不兼容（strategy 不一致、group_by 不一致等）→ 仍然反问
            return SQLPlan(
                strategy=Strategy.NEED_CLARIFICATION,
                downgrade_reason=(
                    f"UNSUPPORTED_MULTI_METRIC: 已识别多个指标（{', '.join(metric_names)}），"
                    f"但查询计划不兼容。"
                    f"原因: {reason}"
                    f"。建议分别查询每个指标。"
                ),
            )

        # 3. 合并：以第一个 plan 的结构为模板，聚合所有 Aggregation
        base = per_metric_plans[0]
        all_aggs: list[Aggregation] = []
        for p in per_metric_plans:
            agg = p["aggregation"]
            if isinstance(agg, Aggregation):
                all_aggs.append(agg)

        # 合并 downgrade_reason（取第一个非空的，多指标降级原因相同）
        merged_downgrade = None
        for p in per_metric_plans:
            if p.get("downgrade_reason"):
                merged_downgrade = p["downgrade_reason"]
                break

        return SQLPlan(
            strategy=base["strategy"],
            primary_table=base["planning_table"],
            joins=list(base["joins"]),
            where_clauses=list(base["where_clauses"]),
            group_by=list(base["group_by"]),
            order_by=list(base["group_by"]),  # 同 group_by
            aggregations=all_aggs,
            downgrade_reason=merged_downgrade,
            confidence=0.95,
        )

    # ═══════════════════════════════════════════════════════════
    # Phase 2B：跨表多指标 → SubIntent 拆分 + 多计划生成
    # ═══════════════════════════════════════════════════════════

    def _split_into_sub_intents(
        self, intent: QuestionIntent, per_metric_plans: list[dict[str, Any]],
    ) -> list[SubIntent]:
        """将跨表多指标按 planning_table 分组为 SubIntent 列表。

        分组逻辑：
            - 同一 planning_table 的指标合并到同一个 SubIntent
            - 每个 SubIntent 继承父意图的 time_range 和 dimensions
            - domain 取自第一个指标（按 planning_table 分组后的子域）

        Args:
            intent: 父级 QuestionIntent
            per_metric_plans: _determine_single_metric_plan() 返回的列表

        Returns:
            按 planning_table 分组后的 SubIntent 列表
        """
        # 按 planning_table 分组
        groups: dict[str, list[dict[str, Any]]] = {}
        for plan_info in per_metric_plans:
            table = plan_info.get("planning_table", "") or "未知"
            groups.setdefault(table, []).append(plan_info)

        sub_intents: list[SubIntent] = []
        for table, plans in sorted(groups.items()):
            metrics = [p["metric"] for p in plans]
            # 取第一个非空 domain
            domain = None
            for p in plans:
                d = p.get("domain")
                if d:
                    domain = d
                    break
            if domain is None:
                domain = intent.domain

            sub_intent = SubIntent(
                metrics=metrics,
                domain=domain,
                planning_table=table,
                time_range=intent.time_range,
                dimensions=list(intent.dimensions) if intent.dimensions else ["date"],
            )
            sub_intents.append(sub_intent)

        return sub_intents

    def _plan_sub_intents(
        self, sub_intents: list[SubIntent], parent_intent: QuestionIntent,
    ) -> list[UnifiedResponse]:
        """为每个 SubIntent 生成独立的 SQLPlan，返回 UnifiedResponse 列表。

        每个 SubIntent 复用 _plan_query_rule() 的等价逻辑：
            - 如果 SubIntent 只有 1 个指标 → 走单指标路径
            - 如果 SubIntent 有多个指标 → 走同表合并路径（_plan_query_multi_metric）

        Args:
            sub_intents: 拆分后的子意图列表
            parent_intent: 父级意图（用于传递 time_range / dimensions 等上下文）

        Returns:
            UnifiedResponse 列表，每个包含 sub_intent 和 plan
        """
        unified_responses: list[UnifiedResponse] = []

        for si in sub_intents:
            # 构造 mini intent（与 SubIntent 匹配的单意图）
            mini_intent = QuestionIntent(
                domain=si.domain,
                intent_type=parent_intent.intent_type,
                metrics=si.metrics,
                time_range=si.time_range or parent_intent.time_range,
                dimensions=si.dimensions,
                confidence=0.95,
                raw_question=parent_intent.raw_question,
            )

            # 复用现有规划逻辑
            if len(si.metrics) == 1:
                plan = self._plan_query_rule(mini_intent)
            else:
                plan = self._plan_query_multi_metric(mini_intent)

            unified_responses.append(UnifiedResponse(
                sub_intent=si,
                plan=plan,
            ))

        return unified_responses

    def _plan_query_rule(self, intent: QuestionIntent) -> SQLPlan:
        """规则版查询规划，支持 G3→G2 降级。

        策略分支：
            - G3 可用且覆盖所有维度 → G3_DIRECT
            - G3 不可用（g3_available=False）→ _build_g2_plan()
            - G3 可用但缺维度 → _build_g2_plan()
            - G2 也无法确定 → NEED_CLARIFICATION

        证据链：所有表名、维度、JOIN 键均来自 metric_contract.yml 和 semantic_contract.yml。
        """
        # ── 多指标分流：len > 1 走多指标规划路径 ──
        if len(intent.metrics) > 1:
            return self._plan_query_multi_metric(intent)

        metric = intent.metrics[0] if intent.metrics else ""
        # ── 获取完整的 MetricInfo（用于 g3_available / g3_table 判断）──
        metric_info = self._get_metric_info(metric)
        dimensions = intent.dimensions if intent.dimensions else ["date"]

        # ── 情况 0: G3 不可用 → 直接走 G2（即使 table mapping 为 None 也尝试）──
        if metric_info is not None and not metric_info.g3_available:
            return self._build_g2_plan(metric_info, intent, dimensions)

        config = self._resolve_metric_table_mapping(metric)

        if config is None:
            # 如果 MetricInfo 存在（G3 可用但 table mapping 失败），也尝试 G2
            if metric_info is not None:
                return self._build_g2_plan(metric_info, intent, dimensions)
            return SQLPlan(
                strategy=Strategy.NEED_CLARIFICATION,
                downgrade_reason=(
                    f"指标 '{metric}' 暂未纳入规则模式，"
                    f"请明确或等待接入 LLM 规划器"
                ),
            )

        # ── 情况 2: G3 可用，检查维度覆盖 ──
        if metric_info is not None and metric_info.g3_available:
            covered, missing = self._g3_covers_dimensions(metric_info, dimensions)
            if covered:
                # G3 覆盖所有维度 → G3_DIRECT（保持原有逻辑）
                g3_table = metric_info.g3_table or config["table"]
                date_col = config["date_col"]
                aggregation_expr = config["aggregation_expr"]
                return SQLPlan(
                    strategy=Strategy.G3_DIRECT,
                    primary_table=g3_table,
                    joins=[
                        JoinPlan(
                            table="gold.dim_date",
                            on=f"gold.dim_date.date = {g3_table}.{date_col}",
                        )
                    ],
                    where_clauses=[
                        (
                            f"gold.dim_date.date BETWEEN DATE '{intent.time_range.start}' "
                            f"AND DATE '{intent.time_range.end}'"
                        )
                    ],
                    group_by=["gold.dim_date.date"],
                    order_by=["gold.dim_date.date"],
                    aggregations=[Aggregation(expr=aggregation_expr, alias=metric)],
                    confidence=0.95,
                )
            else:
                # G3 不覆盖某些维度 → 降级 G2
                return self._build_g2_plan(metric_info, intent, missing)

        # ── 情况 3: metric_info 为空 → 使用原有配置走 G3_DIRECT（向后兼容）──
        table = config["table"]
        date_col = config["date_col"]
        aggregation_expr = config["aggregation_expr"]
        return SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table=table,
            joins=[
                JoinPlan(
                    table="gold.dim_date",
                    on=f"gold.dim_date.date = {table}.{date_col}",
                )
            ],
            where_clauses=[
                (
                    f"gold.dim_date.date BETWEEN DATE '{intent.time_range.start}' "
                    f"AND DATE '{intent.time_range.end}'"
                )
            ],
            group_by=["gold.dim_date.date"],
            order_by=["gold.dim_date.date"],
            aggregations=[Aggregation(expr=aggregation_expr, alias=metric)],
            confidence=0.95,
        )

    def _resolve_metric_table_mapping(
        self, metric_name: str,
    ) -> Optional[dict[str, str]]:
        """
        解析指标名 → G3 表的映射（数据驱动，双层 fallback）。

        优先级：
          1. resolver context 中的 available_metrics（在线模式，动态发现）
          2. agent_config.yml 的 rule_mode.metric_to_table（离线 fallback）

        aggregation_expr vs value_expr：
            - value_expr: 纯列名（如 "total_fare_amount"），用于反问文案和调试
            - aggregation_expr: 完整聚合表达式（如 "SUM(total_fare_amount)"），
              直接写入 SQLPlan，省去 SQL 生成环节再次拼接

        B-8 修复背景：
            此前 value_expr 直接写入 SQLPlan.aggregations，但 SQL 生成时又套了一层 SUM()，
            导致 SUM(SUM(x)) 双包裹。现在 aggregation_expr 承载完整聚合表达式，
            SQL 生成直接使用，不再套壳。

        Returns:
            {"table": "...", "date_col": "...", "aggregation_expr": "..."} 或 None
        """
        table = None
        date_col = None
        value_expr = None
        aggregation_expr = None

        # ── Step 1: 从 context 获取 G2 事实表元数据 ──
        if self._context and self._context.available_metrics:
            for m in self._context.available_metrics:
                if m.name == metric_name and m.base_table:
                    table = m.base_table
                    date_col = self._infer_date_column(table)
                    value_expr = self._extract_value_expr(m.aggregation, metric_name)
                    aggregation_expr = self._normalize_aggregation_expr(m.aggregation, metric_name)
                    break

        # ── Step 2: config 中的精确值覆盖推导值 ──
        rule_cfg = self._agent_config.get("rule_mode", {})
        metric_table = rule_cfg.get("metric_to_table", {})
        config_entry = metric_table.get(metric_name)
        if config_entry:
            if table is None:
                table = config_entry["table"]
            if date_col is None:
                date_col = config_entry.get("date_col", "date")
            # config 的 value_expr 始终优先于推导值（覆盖 G2 表的聚合表达式）
            cfg_value_expr = config_entry.get("value_expr")
            if cfg_value_expr:
                value_expr = cfg_value_expr
                # 保留 Step 1 的聚合函数（如 AVG/SUM/COUNT），只替换列名
                func = "SUM"
                if aggregation_expr:
                    import re as _re
                    func_match = _re.match(r'^(\w+)\(', aggregation_expr)
                    if func_match:
                        func = func_match.group(1).upper()
                aggregation_expr = f"{func}({value_expr})"
            elif aggregation_expr is None:
                aggregation_expr = f"SUM({value_expr})"

        if table is None:
            return None

        return {
            "table": table,
            "date_col": date_col or "date",
            "value_expr": value_expr or metric_name,
            "aggregation_expr": aggregation_expr or f"SUM({value_expr or metric_name})",
        }

    @staticmethod
    def _normalize_aggregation_expr(aggregation: str, fallback: str) -> str:
        """标准化注册表中的聚合表达式，保留 AVG/SUM 等函数语义。

        为什么需要大写归一化：
            注册表（从契约文件或配置加载）中的聚合表达式可能是任意大小写
            （如 'sum(total_fare)' 或 'SUM(total_fare)'），但最终生成的 SQL
            和 IR 中统一使用大写函数名。此方法确保无论输入什么大小写，
            输出都是大写函数名，避免后续环节因大小写不一致而判断错误。
        """
        if not aggregation:
            return f"SUM({fallback})"
        return re.sub(
            r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            lambda match: f"{match.group(1).upper()}(",
            aggregation.strip(),
            count=1,
        )

    @staticmethod
    def _extract_value_expr(aggregation: str, fallback: str) -> str:
        """
        从聚合表达式（如 'SUM(violation_count)'）中提取值列名。

        如果提取失败，使用 fallback。
        """
        import re
        # 匹配 SUM(expr)、COUNT(expr) 等
        match = re.search(r'[A-Z]+\s*\(\s*(\w+)\s*\)', aggregation, re.IGNORECASE)
        if match:
            return match.group(1)
        # 如果 aggregation 已经是纯列名
        if aggregation and re.match(r'^\w+$', aggregation):
            return aggregation
        return fallback

    @staticmethod
    def _infer_date_column(table_name: str) -> str:
        """从 G3 汇总表名推导日期列名"""
        date_map = {
            "trip": "trip_date",
            "parking": "issue_date",
            "crash": "crash_date",
        }
        for key, date_col in date_map.items():
            if key in table_name.lower():
                return date_col
        return "date"

    def _render_llm_prompt(self, task: str, payload: dict[str, Any]) -> str:
        """渲染 LLM 调用 Prompt"""
        template = self._prompt_loader.load(task)
        return (
            f"{template}\n\n"
            "## 本次输入\n"
            "```json\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
            "```"
        )

    def _context_payload(self) -> dict[str, Any]:
        """构造供 Prompt 使用的轻量上下文"""
        if not self._context:
            return {}
        return {
            "available_tables": [
                f"{table.schema}.{table.name}" for table in self._context.available_tables
            ],
            "available_metrics": [
                metric.name for metric in self._context.available_metrics
            ],
            "join_whitelist": [
                [left, right] for left, right in self._context.join_whitelist
            ],
            "forbidden_sql_keywords": self._context.forbidden_sql_keywords,
        }

    def _save_raw_output_on_failure(
        self,
        question: str,
        stage: str,
        prompt_name: str,
        raw_output: str,
        parsed_output: dict[str, Any],
        parse_success: bool,
        validation_success: bool,
        error_message: str | None,
    ) -> str | None:
        """
        LLM 输出失败时保存原始输出，用于诊断根因。

        Returns:
            保存的文件路径，如果未启用则返回 None。
        """
        if not self._raw_output_enabled:
            return None

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        raw_dir = self._raw_output_dir / "llm_raw_outputs" / run_id
        raw_dir.mkdir(parents=True, exist_ok=True)

        # 文件名只使用净化后的短标识，避免问题文本中的路径字符影响落盘。
        case_id = self._safe_question_id(question)
        path = raw_dir / f"{case_id}_{stage}_{uuid4().hex[:8]}.json"
        model_name = self._model_name_for_prompt(prompt_name)

        payload = {
            "question_id": case_id,
            "question": question,
            "stage": stage,
            "prompt_name": prompt_name,
            "model_name": model_name,
            "raw_output": self._redact_sensitive_text(raw_output),
            "parsed_output": self._redact_sensitive_data(parsed_output),
            "parse_success": parse_success,
            "validation_success": validation_success,
            "error_message": self._redact_sensitive_text(error_message or ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def _model_name_for_prompt(self, prompt_name: str) -> str:
        """按 prompt 阶段读取模型名，缺失时返回 unknown。"""
        model_cfg = self._agent_config.get("model", {}) if self._agent_config else {}
        prompt_cfg = model_cfg.get(prompt_name, {}) if isinstance(model_cfg, dict) else {}
        return str(prompt_cfg.get("model") or "unknown")

    @staticmethod
    def _safe_question_id(question: str) -> str:
        """把问题文本转换为可跨平台使用的短文件名前缀。"""
        compact = re.sub(r"\s+", "_", question.strip())[:30]
        safe = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", compact).strip("_")
        digest = hashlib.sha1(question.encode("utf-8")).hexdigest()[:8]
        return f"{safe or 'question'}_{digest}"

    @classmethod
    def _redact_sensitive_data(cls, value: Any) -> Any:
        """递归脱敏结构化数据中的密钥文本。"""
        if isinstance(value, dict):
            return {key: cls._redact_sensitive_data(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._redact_sensitive_data(item) for item in value]
        if isinstance(value, str):
            return cls._redact_sensitive_text(value)
        return value

    @staticmethod
    def _redact_sensitive_text(text: str) -> str:
        """脱敏常见 API Key、token 与 Authorization 片段。"""
        if not text:
            return ""
        patterns = [
            r"(?i)(OPENAI_API_KEY|DEEPSEEK_API_KEY|API_KEY|TOKEN|AUTHORIZATION)\s*=\s*[^\s]+",
            r"(?i)(Authorization:\s*Bearer\s+)[^\s]+",
            r"(?i)(token\s*=\s*)[^\s]+",
            r"sk-[A-Za-z0-9_\-]{8,}",
        ]
        redacted = text
        for pattern in patterns:
            redacted = re.sub(pattern, lambda match: f"{match.group(1)}[REDACTED]" if match.lastindex else "[REDACTED]", redacted)
        return redacted

    def _has_ambiguous_amount(self, question: str) -> bool:
        """金额词未落到具体指标时必须反问"""
        amount_words = ["金额", "多少钱", "费用", "收了多少", "收入"]
        concrete_words = ["车费", "罚款", "罚金", "TIF", "tif", "支付"]
        return any(word in question for word in amount_words) and not any(
            word in question for word in concrete_words
        )

    def _detect_metric(self, question: str) -> Optional[dict[str, Any]]:
        """通过注册指标目录识别 G3 指标。

        三返回值设计：
            - 返回 dict(metric=..., domain=..., confidence=...)
              → 命中唯一指标，调用方可直接使用
            - 返回 dict(metric=None, clarification_reason=..., confidence=...)
              → 指标歧义，需反问用户选择；confidence 来自 MetricResolver 的最高候选置信度
            - 返回 None（metric_not_found）
              → 完全无法匹配，触发兜底反问文案

        为什么不用异常区分而是用 dict 的 metric=None：
            异常会导致调用方 _classify_intent_rule 需要额外 try/except，
            而 dict 三态让调用方用统一的 if metric_info is None or not metric_info.get("metric")
            即可覆盖 all 场景，保持控制流扁平。
        """
        result = MetricResolver(
            self._available_metric_infos(),
            aliases=self._metric_aliases(),
        ).resolve(question)
        if result.matched and result.metric:
            return {
                "metric": result.metric.name,
                "domain": Domain(result.metric.domain) if result.metric.domain else None,
                "confidence": result.confidence,
            }

        # G3 未命中时，尝试匹配非 G3 指标（用于 G2 降级查询）
        if result.failure_reason == "metric_not_found":
            g2_match = self._detect_g2_metric(question)
            if g2_match:
                return g2_match
            return None
        return {
            "metric": None,
            "domain": None,
            "confidence": result.confidence,
            "clarification_reason": result.clarification_message,
        }

    def _detect_g2_metric(self, question: str) -> Optional[dict[str, Any]]:
        """在 G3 指标未命中时，尝试匹配非 G3 指标。

        非 G3 指标（g3_available=False）不使用 MetricResolver 的复杂匹配逻辑，
        仅在中文名或关键词直接出现在问题中时命中（忽略空格差异）。
        证据来源：metric_contract.yml 中 g3_available=false 的指标。
        """
        all_metrics = self._available_metric_infos()
        g2_metrics = [m for m in all_metrics if not m.g3_available]
        question_no_space = question.replace(" ", "")

        for metric in g2_metrics:
            # 简单匹配：中文名或英文名出现在问题中（忽略空格）
            zh_no_space = metric.zh_name.replace(" ", "") if metric.zh_name else ""
            if zh_no_space and zh_no_space in question_no_space:
                return {
                    "metric": metric.name,
                    "domain": Domain(metric.domain) if metric.domain else None,
                    "confidence": 0.85,
                }
            if metric.name.lower() in question.lower():
                return {
                    "metric": metric.name,
                    "domain": Domain(metric.domain) if metric.domain else None,
                    "confidence": 0.85,
                }
        return None

    def _detect_all_g2_metrics(self, question: str) -> list[dict[str, Any]]:
        """批量检测非 G3 指标，返回所有匹配的候选。

        扩展自 _detect_g2_metric()：不返回第一个匹配就停止，
        而是收集所有匹配的非 G3 指标。
        证据来源：metric_contract.yml 中 g3_available=false 的指标。
        """
        all_metrics = self._available_metric_infos()
        g2_metrics = [m for m in all_metrics if not m.g3_available]
        question_no_space = question.replace(" ", "")

        results: list[dict[str, Any]] = []
        for metric in g2_metrics:
            matched_text = None
            matched_by = None

            # 中文名匹配（忽略空格）
            zh_no_space = metric.zh_name.replace(" ", "") if metric.zh_name else ""
            if zh_no_space and zh_no_space in question_no_space:
                matched_text = metric.zh_name
                matched_by = "zh_name"
            # 英文名匹配
            elif metric.name.lower() in question.lower():
                matched_text = metric.name
                matched_by = "metric_name"

            if matched_text:
                results.append({
                    "metric": metric.name,
                    "confidence": 0.85,
                    "matched_text": matched_text,
                    "matched_by": matched_by,
                    "domain": Domain(metric.domain) if metric.domain else None,
                    "metric_info": metric,
                })

        return results

    def _detect_all_metrics(self, question: str) -> list[dict[str, Any]]:
        """批量检测问题中所有匹配的指标，输出候选证据列表。

        处理流程：
            1. G3 指标：MetricResolver.resolve_all() → MetricCandidate 列表
            2. G2 指标：_detect_all_g2_metrics() → 简单 substring 匹配
            3. 去重：同一 metric name 保留最高 confidence
            4. 低置信度过滤：confidence < 0.80 淘汰

        Returns:
            候选证据列表（按置信度降序），每项包含:
                - metric: str           # 指标英文名
                - confidence: float     # 匹配置信度
                - matched_text: str     # 触发匹配的文本
                - matched_by: str       # 匹配方式: metric_name/zh_name/synonym/alias/keyword
                - domain: Domain | None # 业务域
                - metric_info: MetricInfo  # 完整指标信息对象
        """
        results: list[dict[str, Any]] = []

        # 1. G3 指标匹配
        resolver = MetricResolver(
            self._available_metric_infos(),
            aliases=self._metric_aliases(),
        )
        g3_candidates = resolver.resolve_all(question)
        for c in g3_candidates:
            results.append({
                "metric": c.metric.name,
                "confidence": c.confidence,
                "matched_text": c.matched_terms[0] if c.matched_terms else "",
                "matched_by": c.matched_by,
                "domain": Domain(c.metric.domain) if c.metric.domain else None,
                "metric_info": c.metric,
            })

        # 2. G2 指标匹配
        g2_candidates = self._detect_all_g2_metrics(question)
        results.extend(g2_candidates)

        # 3. 去重：同一 metric name 只保留最高 confidence
        deduped: dict[str, dict[str, Any]] = {}
        for r in results:
            name = r["metric"]
            if name not in deduped or r["confidence"] > deduped[name]["confidence"]:
                deduped[name] = r

        # 4. 低置信度过滤
        filtered = [r for r in deduped.values() if r["confidence"] >= 0.80]

        return sorted(filtered, key=lambda r: r["confidence"], reverse=True)

    def _available_metric_infos(self) -> list[MetricInfo]:
        """读取当前上下文中的指标目录；离线时回退到规则配置。

        在线/离线双路径：
            - 在线（context 可用）：直接从 TianShu 契约文件加载的 MetricInfo 列表，
              包含完整字段（zh_name、unit、聚合表达式等）
            - 离线（context 不可用）：从 agent_config.yml 的 rule_mode 段提取
              keyword_to_metric + metric_to_table 拼装 MetricInfo。
              离线模式的 zh_name 为空、unit 为空、aggregation 为 sum 硬编码，
              因为配置文件不包含这些信息。

        为什么离线模式要走规则配置而不是直接返回空：
            REPL 启动时即使 DuckDB 连接失败，用户仍可测试规则匹配逻辑。
            返回空列表会导致所有问题都变成"未识别指标"。
        """
        if self._context and self._context.available_metrics:
            return self._context.available_metrics

        metrics: list[MetricInfo] = []
        rule_cfg = self._agent_config.get("rule_mode", {})
        keyword_map = rule_cfg.get("keyword_to_metric", {})
        metric_table = rule_cfg.get("metric_to_table", {})
        for mapping in keyword_map.values():
            metric_name = mapping.get("metric")
            table_cfg = metric_table.get(metric_name, {})
            value_expr = table_cfg.get("value_expr", metric_name)
            metrics.append(MetricInfo(
                name=metric_name,
                zh_name="",
                domain=mapping.get("domain", ""),
                aggregation=f"sum({value_expr})",
                base_table=table_cfg.get("table", ""),
                unit="",
                g3_available=bool(table_cfg.get("table")),
            ))
        return metrics

    def _metric_aliases(self) -> dict[str, list[str]]:
        """从规则配置读取指标别名，兼容离线 fallback 关键词。

        keyword_to_metric 中的 keywords 列表被复用为别名来源。
        例如配置中 trip_count 对应 keywords=["行程数","行程量","出行量","订单数"]，
        这些关键词会成为 trip_count 的别名，由 MetricResolver 在 alias 优先级层匹配。

        与 MetricResolver._SYNONYMS 的关系：
            - _SYNONYMS 是语言学层面的硬编码同义映射
            - aliases 是运维在配置文件中可随时新增的业务别名
            - MetricResolver 先查 _SYNONYMS（置信度 0.93），再查 aliases（置信度 0.90），
              确保语言学映射优先级高于配置别名
        """
        aliases: dict[str, list[str]] = {}
        rule_cfg = self._agent_config.get("rule_mode", {})
        for mapping in rule_cfg.get("keyword_to_metric", {}).values():
            metric_name = mapping.get("metric")
            if not metric_name:
                continue
            aliases.setdefault(metric_name, []).extend(mapping.get("keywords", []))
        return aliases

    def _parse_month_range(self, question: str) -> TimeRange:
        """解析“2026年1月”这类绝对月份"""
        if any(word in question for word in ["最近", "近期", "上个月", "这阵子", "过去", "这几天"]):
            return TimeRange(type=TimeRangeType.FUZZY, raw_expression=question)

        match = re.search(r"(?P<year>20\d{2})\s*年\s*(?P<month>1[0-2]|0?[1-9])\s*月", question)
        if not match:
            return TimeRange(type=TimeRangeType.FUZZY, raw_expression=question)

        year = int(match.group("year"))
        month = int(match.group("month"))
        last_day = calendar.monthrange(year, month)[1]
        return TimeRange(
            type=TimeRangeType.ABSOLUTE,
            start=f"{year:04d}-{month:02d}-01",
            end=f"{year:04d}-{month:02d}-{last_day:02d}",
            raw_expression=match.group(0),
        )

    def close(self):
        """关闭 Agent，释放资源"""
        if self._resolver:
            self._resolver.close()


def main():
    """CLI 入口 — 输出当前版本和已验证功能清单"""
    setup_console_encoding()
    print("TianShu Text2SQL Agent v0.3.0")
    print("规则模式 (rule) 定位为 PoC / 离线 fallback；LLM 模式需传入 llm_client 启用。")
    print("指标映射从 agent_config.yml 加载（rule_mode 段），新增指标无需改代码。")
    print()
    print("已验证：")
    print("  [OK] 项目结构建立")
    print("  [OK] 三层 IR 数据结构定义 (QuestionIntent / SQLPlan / SQLResult)")
    print("  [OK] TianShu 契约文件加载 (contracts/*.yml)")
    print("  [OK] SQL 安全门禁 (6 项检查 + 统一关键字加载器)")
    print("  [OK] 歧义检测与反问生成")
    print("  [OK] 规则模式 MVP (行程/违章/事故 G3 日汇总)")
    print("  [OK] LLM Pipeline 接入 (DeepSeek / OpenAI 兼容)")
    print("  [OK] Harness 门禁 (fast gate + slow gate + 双基线)")
    print()
    print("入口：")
    print("  python -m src.repl           # 交互式 REPL (规则模式)")
    print("  python -m src.agent          # 本入口 (版本信息)")
    print("  python harness/run_fast_gate.py  # 快速门禁")
    print("  python harness/run_slow_gate.py  # 慢速门禁 (需 LLM API)")


if __name__ == "__main__":
    main()
