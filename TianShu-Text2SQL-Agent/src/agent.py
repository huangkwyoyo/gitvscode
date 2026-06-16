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
    IntentType,
    JoinPlan,
    QuestionIntent,
    SQLPlan,
    SQLResult,
    Strategy,
    TimeRange,
    TimeRangeType,
)
from .resolver import TianShuResolver, AgentContext, MetricInfo
from .metric_resolver import MetricResolver
from .ambiguity import detect_ambiguity, load_clarification_rules
from .request_guard import is_write_request, is_forbidden_layer_request
from .sql_gen import sql_plan_to_sql, validate_sql_safety
from .explainer import explain_result
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

        # ── Step 3.5: IR 校验 —— Layer 2 规划校验（表存在性、JOIN 白名单、降级原因）──
        available_tables_set: Optional[set[str]] = None
        join_whitelist_set: Optional[set[tuple[str, str]]] = None
        if self._context:
            available_tables_set = {
                f"{t.schema}.{t.name}" for t in self._context.available_tables
            }
            join_whitelist_set = set(self._context.join_whitelist)

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

        # ── Step 4: SQL 生成 + 安全检查（二层防线）──
        # B-7 职责分离：
        #   - 主防线: SQLPlan.validate() 已在 Step 3.5 完成 JOIN 白名单校验
        #   - 兜底防线: validate_sql_safety() 在此检查 SQL 中是否引入了计划外 JOIN
        #   - 两层都检查：SELECT only、表白名单、禁止关键字、日期过滤
        response.trace.append("[STEP 4] SQL 生成 + 安全检查...")
        sql = sql_plan_to_sql(plan)

        forbidden_kw = self._context.forbidden_sql_keywords if self._context else []
        violations = validate_sql_safety(
            sql, forbidden_kw,
            available_tables=available_tables_set,
            join_whitelist=join_whitelist_set,
        )
        if violations:
            response.refusal = True
            response.refusal_reason = f"SQL 安全检查失败: {'; '.join(violations)}"
            response.trace.append(f"         [FAIL] {response.refusal_reason}")
            # 保存证据：SQL 本身即 raw_output，plan raw 提供上下文
            self._save_raw_output_on_failure(
                question=question,
                stage="sql_safety",
                prompt_name="sql_planner",
                raw_output=sql,
                parsed_output=plan.to_dict() if plan else {},
                parse_success=True,
                validation_success=False,
                error_message=response.refusal_reason,
            )
            return response

        # ── Step 5: 执行 SQL ──
        response.trace.append("[STEP 5] 执行 SQL...")
        # C-1 修复：离线模式必须阻断 SQL 执行（防御深度）
        # 即使前面的安全校验因为某种原因未拦截，这一层也必须阻断
        if self._context and self._context.offline:
            result = SQLResult(
                sql=sql,
                error="Agent 处于离线模式，禁止执行 SQL（安全约束）",
            )
            response.trace.append("         [BLOCKED] 离线模式禁止执行 SQL")
        elif self._resolver:
            timeout_seconds = self._agent_config.get("safety", {}).get("query_timeout", 30)
            result = self._resolver.execute_sql(
                sql,
                timeout_seconds=timeout_seconds,
                source_table=plan.primary_table or "",
            )
        else:
            result = SQLResult(
                sql=sql,
                error="数据库未连接（离线模式）",
            )
        response.result = result
        response.trace.append(f"         行数={result.row_count}, 耗时={result.execution_time_ms}ms")

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

    def _classify_intent_rule(self, question: str) -> QuestionIntent:
        """
        规则版意图分类。

        MVP 只覆盖高频 G3 日汇总问题；未覆盖的指标先反问，不编造口径。
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

        metric_info = self._detect_metric(question)
        if metric_info is None or not metric_info.get("metric"):
            return QuestionIntent(
                needs_clarification=True,
                clarification_reason=metric_info.get("clarification_reason") if metric_info else (
                    "暂未识别到已注册指标，请明确要查询的指标。"
                ),
                confidence=metric_info.get("confidence", 0.0) if metric_info else 0.0,
                raw_question=question,
            )

        time_range = self._parse_month_range(question)
        if time_range.type == TimeRangeType.FUZZY:
            return QuestionIntent(
                domain=metric_info["domain"],
                intent_type=IntentType.TREND,
                metrics=[metric_info["metric"]],
                time_range=time_range,
                dimensions=["date"],
                needs_clarification=True,
                clarification_reason="请明确查询时间范围，例如“2026年1月”或“2026年Q1”。",
                confidence=0.9,
                raw_question=question,
            )

        return QuestionIntent(
            domain=metric_info["domain"],
            intent_type=IntentType.TREND,
            metrics=[metric_info["metric"]],
            time_range=time_range,
            dimensions=["date"],
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

    def _plan_query_rule(self, intent: QuestionIntent) -> SQLPlan:
        """
        规则版查询规划（PoC / 离线 fallback）。

        B-8 修复：指标→表映射优先级：
            1. resolver context 中的 available_metrics（从 meta.metric_definitions 动态发现）
            2. agent_config.yml 的 rule_mode.metric_to_table（离线 fallback）

        规则模式定位为 PoC / fallback，不作为生产主路径。
        """
        metric = intent.metrics[0] if intent.metrics else ""
        config = self._resolve_metric_table_mapping(metric)

        if config is None:
            return SQLPlan(
                strategy=Strategy.NEED_CLARIFICATION,
                downgrade_reason=(
                    f"指标 '{metric}' 暂未纳入规则模式，"
                    f"请明确或等待接入 LLM 规划器"
                ),
            )

        table = config["table"]
        date_col = config["date_col"]
        # 直接使用 _resolve_metric_table_mapping 返回的完整聚合表达式，
        # 避免再次拼接 SUM() 导致 SUM(SUM(x)) 双包裹
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

        # ── Step 1: 从 context 或 config 获取表名 ──
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
            # config 的 value_expr 最精确，优先使用
            value_expr = config_entry.get("value_expr", value_expr or metric_name)
            if aggregation_expr is None:
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
        if result.failure_reason == "metric_not_found":
            return None
        return {
            "metric": None,
            "domain": None,
            "confidence": result.confidence,
            "clarification_reason": result.clarification_message,
        }

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
