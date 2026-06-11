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

import calendar
import re
import sys
from pathlib import Path
from typing import Any, Optional

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
from .resolver import TianShuResolver, AgentContext
from .ambiguity import detect_ambiguity, load_clarification_rules
from .sql_gen import sql_plan_to_sql, validate_sql_safety
from .executor import execute_sql
from .explainer import explain_result


def _setup_console_encoding() -> None:
    """
    设置控制台编码为 UTF-8，解决 Windows GBK 控制台下 emoji 字符输出崩溃问题。

    仅在 Windows 平台执行。Python 3.7+ 支持 sys.stdout.reconfigure()。
    如 reconfigure 失败（极老的 Python），静默跳过。
    """
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore[attr-defined]
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')  # type: ignore[attr-defined]
        except Exception:
            # reconfigure 不可用（Python < 3.7 或非标准 stdout），使用替代方案
            pass


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

        if self._is_write_request(question):
            response.refusal = True
            response.refusal_reason = "我是只读分析 Agent，不能修改、删除或创建数据。"
            response.trace.append(f"         [REFUSE] {response.refusal_reason}")
            return response

        if self._is_forbidden_layer_request(question):
            response.refusal = True
            response.refusal_reason = "Bronze/Silver 层不能直接用于业务问数，请改用 Gold 层指标提问。"
            response.trace.append(f"         [REFUSE] {response.refusal_reason}")
            return response

        # ── Step 1: 意图分类（TODO: 接入 LLM）──
        response.trace.append("[STEP 1] 意图分类...")
        intent = self._classify_intent(question)
        response.intent = intent
        response.trace.append(f"         领域={intent.domain}, 指标={intent.metrics}, 置信度={intent.confidence:.2f}")

        # ── Step 1.5: IR 校验 —— Layer 1 语义校验 ──
        intent_errors = intent.validate()
        if intent_errors:
            response.clarification_needed = True
            response.clarification_message = f"意图校验失败: {'; '.join(intent_errors)}"
            response.trace.append(f"         [FAIL] Layer1 校验失败: {response.clarification_message}")
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
            response.refusal = True
            response.refusal_reason = f"SQL 规划校验失败: {'; '.join(plan_errors)}"
            response.trace.append(f"         [FAIL] Layer2 校验失败: {response.refusal_reason}")
            return response

        # ── Step 4: 安全检查 + SQL 生成 ──
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
            return response

        # ── Step 5: 执行 SQL ──
        response.trace.append("[STEP 5] 执行 SQL...")
        if self._resolver and self._resolver._conn:
            timeout_seconds = self._agent_config.get("safety", {}).get("query_timeout", 30)
            result = execute_sql(
                self._resolver._conn,
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
        if metric_info is None:
            return QuestionIntent(
                needs_clarification=True,
                clarification_reason="暂未识别到已注册指标，请说明要查询行程量、停车罚单数量还是事故数量。",
                confidence=0.0,
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
        """
        规则版查询规划。

        MVP 只选择 G3 日汇总表，并显式 JOIN gold.dim_date 做日期过滤。
        """
        metric = intent.metrics[0] if intent.metrics else ""
        config = {
            "trip_count": {
                "table": "gold.dws_daily_trip_summary",
                "date_col": "trip_date",
                "value_expr": "trip_count",
            },
            "parking_violation_count": {
                "table": "gold.dws_daily_parking_summary",
                "date_col": "issue_date",
                "value_expr": "violation_count",
            },
            "crash_count": {
                "table": "gold.dws_daily_crash_summary",
                "date_col": "crash_date",
                "value_expr": "crash_count",
            },
        }.get(metric)

        if config is None:
            return SQLPlan(
                strategy=Strategy.NEED_CLARIFICATION,
                downgrade_reason="该指标暂未纳入规则版 MVP，请明确或等待接入 LLM 规划器。",
            )

        table = config["table"]
        date_col = config["date_col"]
        value_expr = config["value_expr"]
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
            aggregations=[Aggregation(expr=f"SUM({value_expr})", alias=metric)],
            confidence=0.95,
        )

    def _is_write_request(self, question: str) -> bool:
        """识别明显写操作请求"""
        return any(word in question for word in ["删除", "更新", "修改", "插入", "写入", "创建", "建表"])

    def _is_forbidden_layer_request(self, question: str) -> bool:
        """识别直接查询 Bronze/Silver 的请求"""
        lowered = question.lower()
        return "bronze" in lowered or "silver" in lowered or "原始表" in question or "原始数据" in question

    def _has_ambiguous_amount(self, question: str) -> bool:
        """金额词未落到具体指标时必须反问"""
        amount_words = ["金额", "多少钱", "费用", "收了多少", "收入"]
        concrete_words = ["车费", "罚款", "罚金", "TIF", "tif", "支付"]
        return any(word in question for word in amount_words) and not any(
            word in question for word in concrete_words
        )

    def _detect_metric(self, question: str) -> Optional[dict[str, Any]]:
        """用关键词识别 MVP 支持的三个注册指标"""
        if any(word in question for word in ["行程", "出行", "订单"]):
            return {"metric": "trip_count", "domain": Domain.TRAFFIC}
        if any(word in question for word in ["停车罚单", "罚单", "违章"]):
            return {"metric": "parking_violation_count", "domain": Domain.VIOLATION}
        if any(word in question for word in ["事故", "碰撞"]):
            return {"metric": "crash_count", "domain": Domain.SAFETY}
        return None

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
    """CLI 入口（桩）"""
    _setup_console_encoding()
    print("TianShu Text2SQL Agent v0.1.0")
    print("当前为骨架版本，核心 LLM 链路尚未接入。")
    print()
    print("已验证：")
    print("  [OK] 项目结构建立")
    print("  [OK] 三层 IR 数据结构定义")
    print("  [OK] TianShu 契约文件加载")
    print("  [OK] Harness 门禁骨架")
    print()
    print("下一步：")
    print("  1. 编写 prompts/ 目录下的 LLM 提示词模板")
    print("  2. 实现 agent.py 中的 _classify_intent() 和 _plan_query()")
    print("  3. 接入 LLM API 调用")
    print("  4. 运行 python harness/run_harness.py 验证")


if __name__ == "__main__":
    main()
