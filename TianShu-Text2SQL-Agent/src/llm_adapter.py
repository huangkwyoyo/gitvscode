"""
LLM Adapter —— Prompt 模板 + LLM 客户端 → 结构化 IR 的封装层。

职责：
    封装"加载 Prompt → 渲染上下文 → 调 LLM → 提取 JSON → Schema 校验 → 转 IR"
    的全流程。当前只接受 FakeLLMClient / MockLLMClient。

安全约束（Phase 2A 强制执行）：
    - 禁止导入 OpenAIChatLLMClient
    - 禁止读取 API 密钥
    - 禁止引入真实 LLM SDK
    - generate_sql() 结果必须经过 validate_sql_safety() 再返回
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ir import (
    Aggregation,
    Domain,
    Filter,
    IntentType,
    JoinPlan,
    QuestionIntent,
    SQLPlan,
    SQLResult,
    Strategy,
    TimeRange,
    TimeRangeType,
)
from .llm import LLMClient, LLMRequest, PromptLoader
from .llm_pipeline import extract_json_object
from .schema_validators import (
    is_refusal_output,
    validate_explain_output,
    validate_intent_output,
    validate_plan_output,
    validate_sql_output,
)


class RefusalDetected(Exception):
    """意图分类器检测到拒绝回答的场景（写操作 / Bronze 直查等）。

    区别于 ValueError（格式错误），这是一个预期的结构化输出，
    表示 LLM 正确识别了拒绝场景。
    """

    def __init__(self, refusal_reason: str, question: str = ""):
        self.refusal_reason = refusal_reason
        self.question = question
        super().__init__(f"REFUSAL: {refusal_reason}")


class LLMAdapter:
    """LLM 适配器 —— 封装 Prompt 模板到结构化 IR 的转换。

    只接受 LLMClient 协议实例（FakeLLMClient / MockLLMClient）。
    不创建真实 API 客户端，不读取密钥。
    """

    def __init__(
        self,
        llm_client: LLMClient,
        prompt_loader: PromptLoader | None = None,
    ):
        """初始化适配器。

        Args:
            llm_client: LLM 客户端（FakeLLMClient / MockLLMClient）。
            prompt_loader: Prompt 模板加载器，默认指向 prompts/ 目录。
        """
        self._client = llm_client
        self._loader = prompt_loader or PromptLoader(Path("prompts"))

    # ── 四个公有方法 ──────────────────────────────────────

    def classify_intent(
        self,
        question: str,
        context: dict[str, Any] | None = None,
    ) -> QuestionIntent:
        """将中文问题转为结构化 QuestionIntent。

        流程：加载 intent_classifier.md → 渲染上下文 → 调 LLM
              → 提取 JSON → Schema 校验 → 检测 refusal → 构造 QuestionIntent

        Args:
            question: 用户原始中文问题。
            context: 可选的上下文信息（可用指标、领域、策略等）。

        Returns:
            校验通过的 QuestionIntent 对象。

        Raises:
            ValueError: LLM 输出格式不合法或 Schema 校验失败。
            RefusalDetected: 检测到拒绝回答（写操作 / Bronze 直查等）。
        """
        template = self._loader.load("intent_classifier")
        prompt = self._render(template, question=question, context=context or {})
        response = self._client.complete(
            LLMRequest(task="intent_classifier", prompt=prompt)
        )
        data = extract_json_object(response.content)

        # Schema 校验 —— 失败则阻断（兼容 QuestionIntent 和 Refusal 两种格式）
        errors = validate_intent_output(data)
        if errors:
            raise ValueError(
                f"意图分类输出校验失败: {'; '.join(errors)}"
            )

        # 检测 refusal —— 拒绝类问题不返回 QuestionIntent
        if is_refusal_output(data):
            raise RefusalDetected(
                refusal_reason=data["refusal_reason"],
                question=question,
            )

        return self._dict_to_intent(data)

    def plan_sql(
        self,
        intent: QuestionIntent,
        context: dict[str, Any] | None = None,
    ) -> SQLPlan:
        """将 QuestionIntent 转为 SQLPlan。

        流程：加载 sql_planner.md → 渲染上下文 → 调 LLM
              → 提取 JSON → Schema 校验 → 构造 SQLPlan

        Args:
            intent: 已校验的 QuestionIntent。
            context: 可选的上下文（可用表、JOIN 白名单、语义契约等）。

        Returns:
            校验通过的 SQLPlan 对象。

        Raises:
            ValueError: LLM 输出格式不合法或 Schema 校验失败。
        """
        template = self._loader.load("sql_planner")
        prompt = self._render(
            template,
            question_intent=intent.to_dict(),
            context=context or {},
        )
        response = self._client.complete(
            LLMRequest(task="sql_planner", prompt=prompt)
        )
        data = extract_json_object(response.content)

        # Schema 校验 —— 失败则阻断
        errors = validate_plan_output(data)
        if errors:
            raise ValueError(
                f"SQL 规划输出校验失败: {'; '.join(errors)}"
            )

        return self._dict_to_plan(data)

    def generate_sql(
        self,
        plan: SQLPlan,
        safety_policy: dict[str, Any] | None = None,
    ) -> str:
        """将 SQLPlan 转为只读 SQL 字符串。

        流程：加载 sql_generator.md → 渲染上下文 → 调 LLM
              → 提取 JSON → Schema 校验 → validate_sql_safety() → 返回 SQL

        Args:
            plan: 已校验的 SQLPlan。
            safety_policy: 可选的安全策略（禁止关键字、可用表、JOIN 白名单）。

        Returns:
            安全校验通过的 SQL 字符串。

        Raises:
            ValueError: LLM 输出不合法 / Schema 校验失败 / SQL 安全校验失败。
        """
        from .sql_gen import validate_sql_safety

        template = self._loader.load("sql_generator")
        prompt = self._render(
            template,
            sql_plan=plan.to_dict(),
            safety_policy=safety_policy or {},
        )
        response = self._client.complete(
            LLMRequest(task="sql_generator", prompt=prompt)
        )
        data = extract_json_object(response.content)

        # Schema 校验
        errors = validate_sql_output(data)
        if errors:
            raise ValueError(
                f"SQL 生成输出校验失败: {'; '.join(errors)}"
            )

        sql = data["sql"]

        # 安全校验 —— 必须通过，不允许绕过
        policy = safety_policy or {}
        safety_errors = validate_sql_safety(
            sql,
            forbidden_keywords=policy.get(
                "forbidden_keywords",
                ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"],
            ),
            available_tables=policy.get("available_tables"),
            join_whitelist=policy.get("join_whitelist"),
        )
        if safety_errors:
            raise ValueError(
                f"SQL 安全校验失败，拒绝执行: {'; '.join(safety_errors)}"
            )

        return sql

    def explain_result(
        self,
        question: str,
        result: SQLResult,
        metric_definitions: list[dict[str, Any]] | None = None,
    ) -> str:
        """将 SQLResult 转为中文解释。

        流程：加载 explainer.md → 渲染上下文 → 调 LLM
              → 提取 JSON → Schema 校验 → 返回解释文本

        Args:
            question: 用户原始中文问题。
            result: SQL 执行结果。
            metric_definitions: 可选的相关指标口径说明。

        Returns:
            中文解释字符串。

        Raises:
            ValueError: LLM 输出不合法或 Schema 校验失败。
        """
        template = self._loader.load("explainer")
        prompt = self._render(
            template,
            question=question,
            result=result.to_dict(),
            metric_definitions=metric_definitions or [],
        )
        response = self._client.complete(
            LLMRequest(task="explainer", prompt=prompt)
        )
        data = extract_json_object(response.content)

        # Schema 校验
        errors = validate_explain_output(data)
        if errors:
            raise ValueError(
                f"结果解释输出校验失败: {'; '.join(errors)}"
            )

        return data["answer_zh"]

    # ── 内部辅助方法 ──────────────────────────────────────

    @staticmethod
    def _render(template: str, **kwargs: Any) -> str:
        """最简模板渲染：将上下文参数追加到模板末尾。

        不引入 Jinja2 依赖，直接拼接 JSON 上下文。
        后期可替换为正式模板引擎。
        """
        # 自定义编码器：将 set/frozenset 转为 list，确保 JSON 可序列化
        def _default_encoder(obj: Any) -> Any:
            if isinstance(obj, (set, frozenset)):
                return sorted(obj)
            if isinstance(obj, tuple):
                return list(obj)
            raise TypeError(
                f"JSON 序列化不支持类型: {type(obj).__name__}"
            )

        context_json = json.dumps(
            kwargs,
            ensure_ascii=False,
            indent=2,
            default=_default_encoder,
        )
        return f"{template}\n\n## 本次输入\n\n```json\n{context_json}\n```"

    @staticmethod
    def _dict_to_intent(data: dict[str, Any]) -> QuestionIntent:
        """从字典构造 QuestionIntent（复用 llm_pipeline 转换逻辑）。"""
        domain_raw = data.get("domain")
        domain = Domain(domain_raw) if domain_raw else None

        intent_raw = data.get("intent_type")
        intent_type = IntentType(intent_raw) if intent_raw else None

        time_data = data.get("time_range", {})
        time_type_raw = time_data.get("type", "fuzzy")
        time_range = TimeRange(
            type=TimeRangeType(time_type_raw),
            start=time_data.get("start"),
            end=time_data.get("end"),
            raw_expression=time_data.get("raw_expression"),
        )

        filters = [
            Filter(
                field=f.get("field", ""),
                op=f.get("op", "="),
                value=f.get("value", ""),
                value_type=f.get("value_type", "string"),
            )
            for f in data.get("filters", [])
        ]

        return QuestionIntent(
            domain=domain,
            intent_type=intent_type,
            metrics=data.get("metrics", []),
            time_range=time_range,
            dimensions=data.get("dimensions", []),
            filters=filters,
            needs_clarification=data.get("needs_clarification", False),
            clarification_reason=data.get("clarification_reason"),
            confidence=data.get("confidence", 0.0),
            raw_question=data.get("raw_question"),
        )

    @staticmethod
    def _dict_to_plan(data: dict[str, Any]) -> SQLPlan:
        """从字典构造 SQLPlan（复用 llm_pipeline 转换逻辑）。"""
        strategy_raw = data.get("strategy", "need_clarification")
        strategy = Strategy(strategy_raw)

        joins = [
            JoinPlan(
                table=j.get("table", ""),
                on=j.get("on", ""),
                type=j.get("type", "INNER"),
            )
            for j in data.get("joins", [])
        ]

        aggregations = [
            Aggregation(
                expr=a.get("expr", ""),
                alias=a.get("alias", ""),
            )
            for a in data.get("aggregations", [])
        ]

        return SQLPlan(
            strategy=strategy,
            primary_table=data.get("primary_table"),
            joins=joins,
            where_clauses=data.get("where_clauses", []),
            group_by=data.get("group_by", []),
            order_by=data.get("order_by", []),
            aggregations=aggregations,
            limit=data.get("limit"),
            downgrade_reason=data.get("downgrade_reason"),
            confidence=data.get("confidence", 0.0),
        )
