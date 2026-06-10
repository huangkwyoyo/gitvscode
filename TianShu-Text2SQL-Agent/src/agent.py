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

from pathlib import Path
from typing import Any, Optional

from .ir import AgentResponse, QuestionIntent, SQLPlan, SQLResult
from .resolver import TianShuResolver, AgentContext
from .ambiguity import detect_ambiguity, load_clarification_rules
from .sql_gen import sql_plan_to_sql, validate_sql_safety
from .executor import execute_sql
from .explainer import explain_result


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
    ):
        self._agent_config: dict[str, Any] = {}
        self._context: Optional[AgentContext] = None
        self._resolver: Optional[TianShuResolver] = None
        self._clarification_rules: list = []

        # 加载配置
        self._load_agent_config(agent_config_path)

        # 初始化 TianShu 连接
        self._init_resolver(tianshu_config_path)

    def _load_agent_config(self, config_path: str) -> None:
        """加载 Agent 运行时配置"""
        import yaml
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
            print(f"       Agent 将在离线模式下运行（无数据库连接）")
            self._context = AgentContext()

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

        # ── Step 1: 意图分类（TODO: 接入 LLM）──
        response.trace.append("[STEP 1] 意图分类...")
        intent = self._classify_intent(question)
        response.intent = intent
        response.trace.append(f"         领域={intent.domain}, 指标={intent.metrics}, 置信度={intent.confidence:.2f}")

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

        if plan.strategy.value == "need_clarification":
            response.clarification_needed = True
            response.clarification_message = plan.downgrade_reason or "需要进一步确认"
            return response

        # ── Step 4: 安全检查 + SQL 生成 ──
        response.trace.append("[STEP 4] SQL 生成 + 安全检查...")
        sql = sql_plan_to_sql(plan)

        forbidden_kw = self._context.forbidden_sql_keywords if self._context else []
        violations = validate_sql_safety(sql, forbidden_kw)
        if violations:
            response.refusal = True
            response.refusal_reason = f"SQL 安全检查失败: {'; '.join(violations)}"
            response.trace.append(f"         [FAIL] {response.refusal_reason}")
            return response

        # ── Step 5: 执行 SQL ──
        response.trace.append("[STEP 5] 执行 SQL...")
        if self._resolver and self._resolver._conn:
            result = execute_sql(
                self._resolver._conn,
                sql,
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
        """
        意图分类（桩实现）。

        TODO: 接入 LLM，使用 prompts/intent_classifier.md 模板。
        当前返回默认的 QuestionIntent。
        """
        # 桩：返回需要反问的意图，提示用户 Agent 尚未接入 LLM
        return QuestionIntent(
            needs_clarification=True,
            clarification_reason=(
                "Agent 意图分类器尚未接入 LLM。"
                "当前为骨架版本，请在 prompts/intent_classifier.md 中配置 Prompt 模板后重新启动。"
            ),
            confidence=0.0,
            raw_question=question,
        )

    def _plan_query(self, intent: QuestionIntent) -> SQLPlan:
        """
        查询规划（桩实现）。

        TODO: 接入 LLM，使用 prompts/sql_planner.md 模板。
        """
        from .ir import Strategy
        return SQLPlan(strategy=Strategy.NEED_CLARIFICATION)

    def close(self):
        """关闭 Agent，释放资源"""
        if self._resolver:
            self._resolver.close()


def main():
    """CLI 入口（桩）"""
    print("TianShu Text2SQL Agent v0.1.0")
    print("当前为骨架版本，核心 LLM 链路尚未接入。")
    print()
    print("已验证：")
    print("  ✅ 项目结构建立")
    print("  ✅ 三层 IR 数据结构定义")
    print("  ✅ TianShu 契约文件加载")
    print("  ✅ Harness 门禁骨架")
    print()
    print("下一步：")
    print("  1. 编写 prompts/ 目录下的 LLM 提示词模板")
    print("  2. 实现 agent.py 中的 _classify_intent() 和 _plan_query()")
    print("  3. 接入 LLM API 调用")
    print("  4. 运行 python harness/run_harness.py 验证")


if __name__ == "__main__":
    main()
