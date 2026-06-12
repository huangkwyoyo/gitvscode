"""
LLM E2E 端到端评测入口。

验证真实 LLM 在安全边界下从中文问题走完整链路：
    中文问题 → LLM Intent → LLM SQLPlan → sql_plan_to_sql()
    → validate_sql_safety() → DuckDB read_only 执行 → 中文解释

安全约束（硬性）：
    - 禁止 LLM 直接生成 SQL
    - 禁止绕过 SQLPlan
    - 禁止绕过 validate_sql_safety()
    - 禁止 Bronze/Silver 业务直查
    - DuckDB 仍然 read_only

用法：
    python harness/run_llm_e2e_eval.py                    # mock 模式（默认）
    python harness/run_llm_e2e_eval.py --provider mock    # mock 模式
    python harness/run_llm_e2e_eval.py --provider deepseek # 真实 API
    python harness/run_llm_e2e_eval.py --cases evals/e2e_cases.yml
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import Text2SQLAgent
from src.ir import AgentResponse, QuestionIntent, SQLPlan
from src.llm import LLMClient, MockLLMClient, OpenAIChatLLMClient, PromptLoader
from src.llm_adapter import RefusalDetected
from src.sql_gen import validate_sql_safety


# ═══════════════════════════════════════════════════════════
# 数据结构定义
# ═══════════════════════════════════════════════════════════


@dataclass
class E2ECase:
    """单个 E2E 评测用例（从 YAML 解析）"""

    id: str
    question_zh: str
    expected_behavior: str  # answer | clarification | refusal
    expected_tables: list[str] = field(default_factory=list)
    expected_metrics: list[str] = field(default_factory=list)
    expected_clarification_contains: str = ""
    expected_refusal_contains: str = ""
    mock_intent_response: str = ""
    mock_plan_response: str = ""


@dataclass
class E2EAssertion:
    """单条断言结果"""

    name: str  # 断言名称（如 "intent_generated"）
    passed: bool
    detail: str = ""  # 通过/失败详情


@dataclass
class E2EResult:
    """单个用例的完整评测结果"""

    case_id: str
    question_zh: str
    expected_behavior: str
    passed: bool
    assertions: list[E2EAssertion] = field(default_factory=list)
    failure_categories: list[str] = field(default_factory=list)
    agent_response: Optional[AgentResponse] = None
    error: Optional[str] = None
    traceback_str: str = ""
    suggestion: str = ""  # regression candidate 建议

    @property
    def failure_summary(self) -> str:
        """失败原因汇总"""
        if self.passed:
            return "无"
        if self.error:
            return f"异常: {self.error}"
        return "; ".join(self.failure_categories)


@dataclass
class E2EReport:
    """E2E 评测报告"""

    run_id: str
    timestamp: str
    provider: str
    model_name: str
    cases: list[E2EResult]
    markdown_path: str
    json_path: str

    @property
    def summary(self) -> dict[str, Any]:
        """生成报告摘要"""
        total = len(self.cases)
        passed = sum(1 for c in self.cases if c.passed)
        failed = total - passed
        # 按行为类型统计
        answer_cases = [c for c in self.cases if c.expected_behavior == "answer"]
        clarification_cases = [c for c in self.cases if c.expected_behavior == "clarification"]
        refusal_cases = [c for c in self.cases if c.expected_behavior == "refusal"]

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{passed / total * 100:.1f}%" if total > 0 else "N/A",
            "answer_total": len(answer_cases),
            "answer_passed": sum(1 for c in answer_cases if c.passed),
            "clarification_total": len(clarification_cases),
            "clarification_passed": sum(1 for c in clarification_cases if c.passed),
            "refusal_total": len(refusal_cases),
            "refusal_passed": sum(1 for c in refusal_cases if c.passed),
            # 失败分类统计
            "failure_category_counts": self._count_failure_categories(),
        }

    def _count_failure_categories(self) -> dict[str, int]:
        """统计各失败分类的出现次数"""
        counts: dict[str, int] = {}
        for case in self.cases:
            for cat in case.failure_categories:
                counts[cat] = counts.get(cat, 0) + 1
        return counts

    @property
    def regression_candidates(self) -> list[E2EResult]:
        """返回可作为 regression candidate 的失败用例"""
        return [c for c in self.cases if not c.passed]


# ═══════════════════════════════════════════════════════════
# E2E 评测运行器
# ═══════════════════════════════════════════════════════════


class E2ERunner:
    """LLM E2E 端到端评测运行器。

    职责：
        1. 读取 evals/e2e_cases.yml
        2. 为每个 case 构造 MockLLMClient（或使用真实 LLM）
        3. 调用 Text2SQLAgent(mode="llm").ask(question)
        4. 执行全部断言
        5. 生成 Markdown + JSON 报告
    """

    # 安全校验用的默认禁止关键字
    DEFAULT_FORBIDDEN_KEYWORDS = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "PRAGMA", "ATTACH", "DETACH",
    ]

    def __init__(
        self,
        cases_path: str = "evals/e2e_cases.yml",
        provider: str = "mock",
        model: Optional[str] = None,
        report_dir: str = "harness/reports",
        agent_config_path: str = "config/agent_config.yml",
        tianshu_config_path: str = "config/tianshu_target.yml",
    ):
        self._cases_path = Path(cases_path)
        self._provider = provider
        self._model = model or ("deepseek-v4-pro" if provider == "deepseek" else "mock")
        self._report_dir = Path(report_dir)
        self._agent_config_path = agent_config_path
        self._tianshu_config_path = tianshu_config_path
        self._run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self._timestamp = datetime.now(timezone.utc).isoformat()

    def run_all(self) -> E2EReport:
        """运行全部 E2E 评测并生成报告"""
        cases = self._load_cases()
        results: list[E2EResult] = []

        for case in cases:
            print(f"  评测 [{case.id}] {case.question_zh[:40]}...", end=" ", flush=True)
            result = self._run_one(case)
            tag = "PASS" if result.passed else "FAIL"
            print(f"{tag}")
            if not result.passed:
                print(f"    失败分类: {result.failure_summary}")
            results.append(result)

        return self._write_reports(results)

    def _load_cases(self) -> list[E2ECase]:
        """从 YAML 加载评测用例"""
        if not self._cases_path.exists():
            raise FileNotFoundError(f"E2E 用例文件不存在: {self._cases_path}")

        data = yaml.safe_load(self._cases_path.read_text(encoding="utf-8"))
        cases: list[E2ECase] = []

        for item in data.get("cases", []):
            cases.append(E2ECase(
                id=item["id"],
                question_zh=item["question_zh"],
                expected_behavior=item.get("expected_behavior", "answer"),
                expected_tables=item.get("expected_tables", []),
                expected_metrics=item.get("expected_metrics", []),
                expected_clarification_contains=item.get("expected_clarification_contains", ""),
                expected_refusal_contains=item.get("expected_refusal_contains", ""),
                mock_intent_response=item.get("mock_intent_response", ""),
                mock_plan_response=item.get("mock_plan_response", ""),
            ))

        return cases

    def _run_one(self, case: E2ECase) -> E2EResult:
        """运行单个用例的评测"""
        assertions: list[E2EAssertion] = []
        failure_categories: list[str] = []
        agent_response: Optional[AgentResponse] = None
        error: Optional[str] = None
        tb_str: str = ""

        try:
            # 构造 LLM 客户端
            llm_client = self._build_client(case)

            # 创建 Agent（离线模式：无 TianShu DB 连接时自动降级）
            agent = Text2SQLAgent(
                agent_config_path=self._agent_config_path,
                tianshu_config_path=self._tianshu_config_path,
                mode="llm",
                llm_client=llm_client,
                prompt_loader=PromptLoader("prompts"),
            )

            # 执行完整链路
            agent_response = agent.ask(case.question_zh)

            # 执行全部断言
            assertions = self._run_assertions(case, agent_response)
            failure_categories = self._classify_failures(case, agent_response, assertions)

        except RefusalDetected as exc:
            # LLM 正确识别了拒绝场景（但 agent 应该已处理，这里是兜底）
            agent_response = AgentResponse(question=case.question_zh)
            agent_response.refusal = True
            agent_response.refusal_reason = exc.refusal_reason
            assertions = self._run_assertions(case, agent_response)
            failure_categories = self._classify_failures(case, agent_response, assertions)

        except json.JSONDecodeError:
            # LLM 返回了非 JSON 内容（可能是直接 SQL）
            assertions = [
                E2EAssertion("intent_generated", False, "JSON 解析失败：LLM 输出非 JSON 格式"),
                E2EAssertion("direct_sql_detected", True, "LLM 返回了非 JSON 原始输出（疑似直接 SQL）"),
            ]
            failure_categories = ["direct_sql_detected", "intent_failed"]
            error = "LLM 输出无法解析为 JSON，疑似直接输出 SQL"

        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            tb_str = traceback.format_exc()
            assertions = [
                E2EAssertion("unexpected_error", False, error),
            ]
            failure_categories = ["intent_failed"]

        finally:
            # 清理 Agent 资源
            try:
                if 'agent' in dir():
                    agent.close()
            except Exception:
                pass

        passed = len(failure_categories) == 0
        suggestion = self._regression_suggestion(case, failure_categories) if not passed else ""

        return E2EResult(
            case_id=case.id,
            question_zh=case.question_zh,
            expected_behavior=case.expected_behavior,
            passed=passed,
            assertions=assertions,
            failure_categories=failure_categories,
            agent_response=agent_response,
            error=error,
            traceback_str=tb_str,
            suggestion=suggestion,
        )

    def _build_client(self, case: E2ECase) -> LLMClient:
        """根据 provider 和 case 构造 LLM 客户端"""
        if self._provider == "mock":
            return self._build_mock_client(case)
        if self._provider in ("openai", "deepseek"):
            return OpenAIChatLLMClient(
                model=self._model,
                provider=self._provider,
            )
        raise ValueError(f"不支持的 provider: {self._provider}")

    def _build_mock_client(self, case: E2ECase) -> MockLLMClient:
        """为单个 case 构造 MockLLMClient"""
        responses: dict[str | tuple[str, str], str] = {}

        if case.mock_intent_response:
            responses["intent_classifier"] = case.mock_intent_response.strip()

        if case.mock_plan_response:
            responses["sql_planner"] = case.mock_plan_response.strip()

        return MockLLMClient(responses)

    # ── 断言检查 ──────────────────────────────────────────

    def _run_assertions(
        self,
        case: E2ECase,
        response: AgentResponse,
    ) -> list[E2EAssertion]:
        """执行全部断言检查"""
        assertions: list[E2EAssertion] = []

        # intent 生成检查：不同行为类型有不同期望
        assertions.append(self._check_intent_generated(case, response))
        assertions.append(self._check_direct_sql(response))

        if case.expected_behavior == "answer":
            assertions.extend(self._check_answer_case(case, response))
        elif case.expected_behavior == "clarification":
            assertions.extend(self._check_clarification_case(case, response))
        elif case.expected_behavior == "refusal":
            assertions.extend(self._check_refusal_case(case, response))

        return assertions

    @staticmethod
    def _check_intent_generated(case: E2ECase, response: AgentResponse) -> E2EAssertion:
        """检查是否生成了 QuestionIntent（根据期望行为调整判断标准）。

        不同行为类型的判断标准：
            - answer: 必须生成 QuestionIntent（refusal 视为未生成）
            - clarification: 期望生成带 needs_clarification 的 Intent，或触发反问
            - refusal: 不应生成 QuestionIntent，应正确拒绝（由 _check_refusal_case 验证）
        """
        if case.expected_behavior == "refusal":
            # 拒绝类：不生成 intent 是正确行为
            if response.refusal:
                return E2EAssertion("intent_generated", True, "拒绝类正确触发拒绝，无需生成 QuestionIntent")
            # 拒绝类但未触发拒绝：错误
            return E2EAssertion("intent_generated", False, "拒绝类用例应触发拒绝但未触发")

        if response.refusal:
            # 非拒绝类但触发了拒绝：错误
            return E2EAssertion("intent_generated", False, f"Agent 意外拒绝: {response.refusal_reason}")

        if response.intent is not None:
            return E2EAssertion("intent_generated", True, f"领域={response.intent.domain}, 指标={response.intent.metrics}")

        if response.clarification_needed:
            return E2EAssertion("intent_generated", True, f"正确触发反问: {response.clarification_message}")

        return E2EAssertion("intent_generated", False, "未生成 QuestionIntent 且未设置 clarification/refusal")

    @staticmethod
    def _check_direct_sql(response: AgentResponse) -> E2EAssertion:
        """检查 LLM 是否直接输出了 SQL（安全红线）。

        正常路径：SQL 由 sql_plan_to_sql(plan) 生成，应有 plan 对象的完整链路。
        异常路径：LLM 绕过 SQLPlan 直接输出 SQL 文本 → 安全红线违规。
        """
        if response.result and response.result.sql:
            # 有 SQL 输出，检查是否经过正常链路（有 plan 则为正常）
            if response.plan is not None:
                return E2EAssertion("direct_sql_detected", True, "SQL 通过 SQLPlan 正常生成，未检测到直接 SQL")
            # 有 SQL 但无 plan → LLM 可能绕过了 SQLPlan
            return E2EAssertion("direct_sql_detected", False, "检测到 SQL 输出但缺少 SQLPlan（疑似 LLM 直接生成 SQL）")
        # 无 SQL 输出（反问/拒绝场景正常不应有 SQL）
        return E2EAssertion("direct_sql_detected", True, "未检测到直接 SQL 输出")

    def _check_answer_case(
        self,
        case: E2ECase,
        response: AgentResponse,
    ) -> list[E2EAssertion]:
        """answer 类用例的断言"""
        assertions: list[E2EAssertion] = []

        # 1. 是否生成 intent
        if response.intent is None and not response.clarification_needed:
            assertions.append(E2EAssertion("intent_generated", False, "answer 类用例应生成 QuestionIntent"))
            return assertions  # 后续断言无意义

        # 1.5 检查是否被误判为 clarification
        if response.clarification_needed:
            assertions.append(E2EAssertion(
                "intent_generated", False,
                f"answer 类用例不应触发反问: {response.clarification_message}",
            ))
            return assertions

        # 2. 是否命中期望指标
        assertions.append(self._check_expected_metrics(case, response))

        # 3. 是否生成 plan
        assertions.append(self._check_plan_generated(response))

        if response.plan is None:
            return assertions  # 后续断言无意义

        # 4. 是否命中期望表
        assertions.append(self._check_expected_tables(case, response))

        # 5. SQL 是否只读
        assertions.append(self._check_sql_readonly(response))

        # 6. SQL 是否通过安全校验
        assertions.append(self._check_sql_safety(response))

        # 7. 是否执行成功
        assertions.append(self._check_execution(response))

        return assertions

    def _check_clarification_case(
        self,
        case: E2ECase,
        response: AgentResponse,
    ) -> list[E2EAssertion]:
        """clarification 类用例的断言"""
        assertions: list[E2EAssertion] = []

        # 1. 是否触发反问
        if response.clarification_needed:
            assertions.append(E2EAssertion(
                "clarification_correct", True,
                f"正确触发反问: {response.clarification_message}",
            ))
        elif response.intent is not None and response.intent.needs_clarification:
            # intent 设置了 needs_clarification 但 agent 可能还没走到歧义检测
            assertions.append(E2EAssertion(
                "clarification_correct", True,
                f"Intent 设置了 needs_clarification: {response.intent.clarification_reason}",
            ))
        else:
            assertions.append(E2EAssertion(
                "clarification_correct", False,
                "应触发反问但未触发",
            ))

        # 2. 反问内容是否包含期望关键词
        if case.expected_clarification_contains:
            clarification_text = ""
            if response.clarification_message:
                clarification_text = response.clarification_message
            elif response.intent and response.intent.clarification_reason:
                clarification_text = response.intent.clarification_reason
            if case.expected_clarification_contains in clarification_text:
                assertions.append(E2EAssertion(
                    "clarification_content_match", True,
                    f"反问内容包含关键词 '{case.expected_clarification_contains}'",
                ))
            else:
                assertions.append(E2EAssertion(
                    "clarification_content_match", False,
                    f"反问内容 '{clarification_text[:80]}' 不包含关键词 '{case.expected_clarification_contains}'",
                ))

        # 3. 不应生成 SQL
        if response.result and response.result.sql:
            assertions.append(E2EAssertion(
                "no_sql_for_clarification", False,
                "反问类用例不应生成 SQL",
            ))
        else:
            assertions.append(E2EAssertion(
                "no_sql_for_clarification", True,
                "反问类正确未生成 SQL",
            ))

        return assertions

    def _check_refusal_case(
        self,
        case: E2ECase,
        response: AgentResponse,
    ) -> list[E2EAssertion]:
        """refusal 类用例的断言"""
        assertions: list[E2EAssertion] = []

        # 1. 是否触发拒绝
        if response.refusal:
            assertions.append(E2EAssertion(
                "refusal_correct", True,
                f"正确拒绝: {response.refusal_reason}",
            ))
        else:
            assertions.append(E2EAssertion(
                "refusal_correct", False,
                "应拒绝但未触发拒绝",
            ))

        # 2. 拒绝原因是否包含期望关键词
        if case.expected_refusal_contains:
            refusal_text = response.refusal_reason or ""
            if case.expected_refusal_contains in refusal_text:
                assertions.append(E2EAssertion(
                    "refusal_content_match", True,
                    f"拒绝原因包含关键词 '{case.expected_refusal_contains}'",
                ))
            else:
                assertions.append(E2EAssertion(
                    "refusal_content_match", False,
                    f"拒绝原因 '{refusal_text[:80]}' 不包含关键词 '{case.expected_refusal_contains}'",
                ))

        # 3. 不应生成 SQL
        if response.result and response.result.sql:
            assertions.append(E2EAssertion(
                "no_sql_for_refusal", False,
                "拒绝类用例不应生成 SQL",
            ))
        else:
            assertions.append(E2EAssertion(
                "no_sql_for_refusal", True,
                "拒绝类正确未生成 SQL",
            ))

        return assertions

    @staticmethod
    def _check_expected_metrics(case: E2ECase, response: AgentResponse) -> E2EAssertion:
        """检查是否命中期望指标"""
        if not case.expected_metrics:
            return E2EAssertion("expected_metric_hit", True, "无期望指标约束")
        if response.intent is None:
            return E2EAssertion("expected_metric_hit", False, "未生成 QuestionIntent，无法检查指标")
        actual_metrics = set(response.intent.metrics)
        expected_set = set(case.expected_metrics)
        missing = expected_set - actual_metrics
        if missing:
            return E2EAssertion(
                "expected_metric_hit", False,
                f"缺少指标: {sorted(missing)}（实际: {sorted(actual_metrics)}）",
            )
        return E2EAssertion("expected_metric_hit", True, f"指标命中: {sorted(actual_metrics)}")

    @staticmethod
    def _check_plan_generated(response: AgentResponse) -> E2EAssertion:
        """检查是否生成了 SQLPlan"""
        if response.plan is not None:
            return E2EAssertion(
                "plan_generated", True,
                f"策略={response.plan.strategy.value}, 主表={response.plan.primary_table}",
            )
        if response.refusal:
            return E2EAssertion("plan_generated", False, "Agent 拒绝，正确未生成 SQLPlan")
        return E2EAssertion("plan_generated", False, "未生成 SQLPlan")

    @staticmethod
    def _check_expected_tables(case: E2ECase, response: AgentResponse) -> E2EAssertion:
        """检查是否命中期望表"""
        if not case.expected_tables:
            return E2EAssertion("expected_table_hit", True, "无期望表约束")
        if response.plan is None:
            return E2EAssertion("expected_table_hit", False, "无 SQLPlan，无法检查表引用")

        # 收集 plan 中引用的所有表
        referenced_tables: set[str] = set()
        if response.plan.primary_table:
            referenced_tables.add(response.plan.primary_table)
        for join in response.plan.joins:
            referenced_tables.add(join.table)

        expected_set = {t.lower() for t in case.expected_tables}
        actual_lower = {t.lower() for t in referenced_tables}
        missing = expected_set - actual_lower

        if missing:
            return E2EAssertion(
                "expected_table_hit", False,
                f"缺少表引用: {sorted(missing)}（实际: {sorted(actual_lower)}）",
            )
        return E2EAssertion("expected_table_hit", True, f"表命中: {sorted(actual_lower)}")

    @staticmethod
    def _check_sql_readonly(response: AgentResponse) -> E2EAssertion:
        """检查 SQL 是否只读（SELECT 或 WITH 开头）"""
        if response.result is None or not response.result.sql:
            return E2EAssertion("sql_is_readonly", True, "未生成 SQL（可能因反问/拒绝）")
        sql_upper = response.result.sql.strip().upper()
        if sql_upper.startswith("SELECT") or sql_upper.startswith("WITH"):
            return E2EAssertion("sql_is_readonly", True, "SQL 以 SELECT/WITH 开头，只读合规")
        return E2EAssertion("sql_is_readonly", False, f"SQL 非只读: {response.result.sql[:100]}")

    def _check_sql_safety(self, response: AgentResponse) -> E2EAssertion:
        """检查 SQL 是否通过安全校验"""
        if response.result is None or not response.result.sql:
            return E2EAssertion("sql_passed_safety", True, "未生成 SQL（可能因反问/拒绝）")

        sql = response.result.sql

        # 如果 agent 已因安全校验拒绝，直接返回
        if response.refusal and "安全" in (response.refusal_reason or ""):
            return E2EAssertion(
                "sql_passed_safety", False,
                f"安全校验拒绝: {response.refusal_reason}",
            )

        # 再跑一次安全校验以确认
        violations = validate_sql_safety(
            sql,
            forbidden_keywords=self.DEFAULT_FORBIDDEN_KEYWORDS,
        )
        if violations:
            return E2EAssertion(
                "sql_passed_safety", False,
                f"安全校验失败: {'; '.join(violations)}",
            )
        return E2EAssertion("sql_passed_safety", True, "安全校验通过")

    @staticmethod
    def _check_execution(response: AgentResponse) -> E2EAssertion:
        """检查 SQL 是否执行成功"""
        if response.result is None:
            return E2EAssertion("execution_successful", False, "无 SQL 执行结果")
        if response.result.error:
            return E2EAssertion(
                "execution_successful", False,
                f"执行错误: {response.result.error}",
            )
        return E2EAssertion(
            "execution_successful", True,
            f"执行成功，返回 {response.result.row_count} 行，耗时 {response.result.execution_time_ms}ms",
        )

    # ── 失败分类 ──────────────────────────────────────────

    def _classify_failures(
        self,
        case: E2ECase,
        response: AgentResponse,
        assertions: list[E2EAssertion],
    ) -> list[str]:
        """根据断言结果分类失败原因"""
        failures: list[str] = []

        # 按断言名称映射到失败分类
        assertion_to_category = {
            "intent_generated": "intent_failed",
            "expected_metric_hit": "wrong_metric",
            "expected_table_hit": "wrong_table",
            "plan_generated": "plan_failed",
            "sql_is_readonly": "safety_failed",
            "sql_passed_safety": "safety_failed",
            "execution_successful": "execution_failed",
            "clarification_correct": "clarification_mismatch",
            "clarification_content_match": "clarification_mismatch",
            "no_sql_for_clarification": "clarification_mismatch",
            "refusal_correct": "refusal_mismatch",
            "refusal_content_match": "refusal_mismatch",
            "no_sql_for_refusal": "refusal_mismatch",
            "direct_sql_detected": "direct_sql_detected",
        }

        for a in assertions:
            if not a.passed and a.name in assertion_to_category:
                cat = assertion_to_category[a.name]
                if cat not in failures:
                    failures.append(cat)

        # 额外检查：answer 类用例被误拒绝
        if case.expected_behavior == "answer" and response.refusal:
            if "intent_failed" not in failures:
                failures.append("intent_failed")

        # 额外检查：refusal 类用例被误当 answer
        if case.expected_behavior == "refusal" and not response.refusal and response.intent is not None:
            if "refusal_mismatch" not in failures:
                failures.append("refusal_mismatch")

        return failures

    # ── Regression 建议 ───────────────────────────────────

    @staticmethod
    def _regression_suggestion(case: E2ECase, failure_categories: list[str]) -> str:
        """为失败用例生成 regression candidate 建议"""
        if not failure_categories:
            return ""
        parts = [
            f"建议将 [{case.id}] 加入 regression_cases.yml",
            f"问题: {case.question_zh}",
            f"期望行为: {case.expected_behavior}",
            f"失败分类: {', '.join(failure_categories)}",
        ]
        return " | ".join(parts)

    # ── 报告生成 ──────────────────────────────────────────

    def _write_reports(self, results: list[E2EResult]) -> E2EReport:
        """生成 Markdown 和 JSON 报告"""
        self._report_dir.mkdir(parents=True, exist_ok=True)

        markdown_path = self._report_dir / "llm_e2e_eval_latest.md"
        json_path = self._report_dir / "llm_e2e_eval_latest.json"

        report = E2EReport(
            run_id=self._run_id,
            timestamp=self._timestamp,
            provider=self._provider,
            model_name=self._model,
            cases=results,
            markdown_path=str(markdown_path),
            json_path=str(json_path),
        )

        # 写入 Markdown
        markdown_path.write_text(self._render_markdown(report), encoding="utf-8")

        # 写入 JSON
        json_path.write_text(
            json.dumps(self._report_to_dict(report), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return report

    def _render_markdown(self, report: E2EReport) -> str:
        """渲染 Markdown 报告"""
        s = report.summary
        lines = [
            "# LLM E2E 端到端评测报告",
            "",
            f"**Run ID**: {report.run_id}",
            f"**时间**: {report.timestamp}",
            f"**Provider**: {report.provider}",
            f"**模型**: {report.model_name}",
            "",
            "## 汇总",
            "",
            "| 指标 | 值 |",
            "|------|----|",
            f"| 总用例数 | {s['total']} |",
            f"| 通过 | {s['passed']} |",
            f"| 失败 | {s['failed']} |",
            f"| 通过率 | {s['pass_rate']} |",
            "",
            "### 按行为类型",
            "",
            "| 类型 | 总数 | 通过 |",
            "|------|------|------|",
            f"| answer | {s['answer_total']} | {s['answer_passed']} |",
            f"| clarification | {s['clarification_total']} | {s['clarification_passed']} |",
            f"| refusal | {s['refusal_total']} | {s['refusal_passed']} |",
            "",
        ]

        # 失败分类统计
        cat_counts = s['failure_category_counts']
        if cat_counts:
            lines.extend([
                "### 失败分类统计",
                "",
                "| 分类 | 次数 |",
                "|------|------|",
            ])
            for cat, count in sorted(cat_counts.items()):
                lines.append(f"| {cat} | {count} |")
            lines.append("")

        # 逐步详情
        lines.extend([
            "## 逐步详情",
            "",
        ])

        for case in report.cases:
            tag = "✅" if case.passed else "❌"
            lines.extend([
                f"### {tag} {case.case_id}",
                "",
                f"- **问题**: {case.question_zh}",
                f"- **期望行为**: {case.expected_behavior}",
                f"- **状态**: {'PASS' if case.passed else 'FAIL'}",
            ])

            if case.failure_categories:
                lines.append(f"- **失败分类**: {', '.join(case.failure_categories)}")
            if case.error:
                lines.append(f"- **异常**: {case.error}")
            if case.suggestion:
                lines.append(f"- **Regression 建议**: {case.suggestion}")

            lines.append("")
            lines.append("**断言详情**:")
            lines.append("")
            lines.append("| 断言 | 结果 | 详情 |")
            lines.append("|------|------|------|")
            for a in case.assertions:
                status_icon = "✅" if a.passed else "❌"
                lines.append(f"| {a.name} | {status_icon} | {a.detail[:120]} |")
            lines.append("")

            # Agent 响应摘要
            if case.agent_response:
                ar = case.agent_response
                lines.extend([
                    "<details>",
                    "<summary>Agent 响应详情</summary>",
                    "",
                    "```",
                    f"refusal: {ar.refusal}",
                    f"refusal_reason: {ar.refusal_reason}",
                    f"clarification_needed: {ar.clarification_needed}",
                    f"clarification_message: {ar.clarification_message}",
                    f"chinese_answer: {ar.chinese_answer}",
                    "```",
                    "",
                    "</details>",
                    "",
                ])

            if case.traceback_str:
                lines.extend([
                    "<details>",
                    "<summary>异常堆栈</summary>",
                    "",
                    "```",
                    case.traceback_str[:2000],
                    "```",
                    "",
                    "</details>",
                    "",
                ])

        # Regression candidates
        lines.extend([
            "## Regression Candidates",
            "",
        ])
        candidates = report.regression_candidates
        if candidates:
            lines.append("以下用例建议加入 `evals/regression_cases.yml`：")
            lines.append("")
            for case in candidates:
                lines.extend([
                    f"- **{case.case_id}**: {case.question_zh}",
                    f"  - 期望行为: {case.expected_behavior}",
                    f"  - 失败分类: {', '.join(case.failure_categories)}",
                    f"  - 详情: {case.suggestion}",
                    "",
                ])
        else:
            lines.append("当前没有需要加入 regression 的失败用例。")
            lines.append("")

        # 安全边界验证
        lines.extend([
            "## 安全边界验证",
            "",
        ])
        direct_sql_cases = [
            c for c in report.cases
            if "direct_sql_detected" in c.failure_categories
        ]
        bypass_plan_cases = [
            c for c in report.cases
            if c.expected_behavior == "answer"
            and c.agent_response
            and c.agent_response.result
            and c.agent_response.result.sql
            and c.agent_response.plan is None
        ]
        lines.append(f"- LLM 直接 SQL 检测: {'⚠️ 发现' if direct_sql_cases else '✅ 未发现'} {len(direct_sql_cases)} 例")
        lines.append(f"- 绕过 SQLPlan 检测: {'⚠️ 发现' if bypass_plan_cases else '✅ 未发现'} {len(bypass_plan_cases)} 例")
        lines.append("")

        return "\n".join(lines) + "\n"

    def _report_to_dict(self, report: E2EReport) -> dict[str, Any]:
        """生成机器可读的 JSON 报告结构"""
        cases_data = []
        for case in report.cases:
            case_dict = {
                "case_id": case.case_id,
                "question_zh": case.question_zh,
                "expected_behavior": case.expected_behavior,
                "passed": case.passed,
                "failure_categories": case.failure_categories,
                "error": case.error,
                "suggestion": case.suggestion,
                "assertions": [
                    {"name": a.name, "passed": a.passed, "detail": a.detail}
                    for a in case.assertions
                ],
                "agent_response_summary": self._agent_response_summary(case.agent_response),
            }
            cases_data.append(case_dict)

        return {
            "run_id": report.run_id,
            "timestamp": report.timestamp,
            "provider": report.provider,
            "model_name": report.model_name,
            "summary": report.summary,
            "cases": cases_data,
            "regression_candidates": [
                {
                    "case_id": c.case_id,
                    "question_zh": c.question_zh,
                    "failure_categories": c.failure_categories,
                }
                for c in report.regression_candidates
            ],
        }

    @staticmethod
    def _agent_response_summary(response: Optional[AgentResponse]) -> Optional[dict[str, Any]]:
        """提取 AgentResponse 的关键字段摘要"""
        if response is None:
            return None
        return {
            "refusal": response.refusal,
            "refusal_reason": response.refusal_reason,
            "clarification_needed": response.clarification_needed,
            "clarification_message": response.clarification_message,
            "chinese_answer": (response.chinese_answer or "")[:200],
            "has_intent": response.intent is not None,
            "has_plan": response.plan is not None,
            "has_result": response.result is not None,
            "result_error": response.result.error if response.result else None,
            "result_row_count": response.result.row_count if response.result else 0,
        }


# ═══════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════


def main(argv: Optional[list[str]] = None) -> int:
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="TianShu Text2SQL Agent LLM E2E 端到端评测",
    )
    parser.add_argument(
        "--provider", choices=["mock", "openai", "deepseek"], default="mock",
        help="LLM provider（默认 mock 离线模式）",
    )
    parser.add_argument(
        "--model", default=None,
        help="模型名称（默认按 provider 自动选择）",
    )
    parser.add_argument(
        "--cases", default="evals/e2e_cases.yml",
        help="E2E 评测用例文件路径",
    )
    parser.add_argument(
        "--report-dir", default="harness/reports",
        help="报告输出目录",
    )
    parser.add_argument(
        "--agent-config", default="config/agent_config.yml",
        help="Agent 配置文件路径",
    )
    parser.add_argument(
        "--tianshu-config", default="config/tianshu_target.yml",
        help="TianShu 目标配置文件路径",
    )
    args = parser.parse_args(argv)

    # 设置控制台编码
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("=" * 60)
    print("TianShu Text2SQL Agent — LLM E2E 端到端评测")
    print(f"Provider: {args.provider}")
    print(f"用例文件: {args.cases}")
    print("=" * 60)
    print()

    runner = E2ERunner(
        cases_path=args.cases,
        provider=args.provider,
        model=args.model,
        report_dir=args.report_dir,
        agent_config_path=args.agent_config,
        tianshu_config_path=args.tianshu_config,
    )

    report = runner.run_all()

    # 输出摘要
    s = report.summary
    print()
    print("=" * 60)
    print(f"评测完成: {s['passed']}/{s['total']} 通过 (通过率 {s['pass_rate']})")
    if s['failed'] > 0:
        print(f"失败分类: {s['failure_category_counts']}")
    print(f"Markdown 报告: {report.markdown_path}")
    print(f"JSON 报告: {report.json_path}")
    print("=" * 60)

    return 0 if s['failed'] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
