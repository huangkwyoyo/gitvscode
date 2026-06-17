"""
LLM Prompt 回放与 IR 转换工具"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from .ir import (
    Aggregation,
    Domain,
    Filter,
    IntentType,
    JoinPlan,
    QuestionIntent,
    SQLPlan,
    Strategy,
    TimeRange,
    TimeRangeType,
)
from .llm import LLMClient, LLMRequest, PromptLoader
from .sql_gen import sql_plan_to_sql, validate_sql_safety
from .safety_policy_loader import load_forbidden_keywords


AVAILABLE_TABLES = {
    "gold.dws_daily_trip_summary",
    "gold.dws_daily_parking_summary",
    "gold.dws_daily_crash_summary",
    "gold.dim_date",
}
JOIN_WHITELIST = {
    ("gold.dws_daily_trip_summary", "gold.dim_date"),
    ("gold.dws_daily_parking_summary", "gold.dim_date"),
    ("gold.dws_daily_crash_summary", "gold.dim_date"),
}

# C-2 修复：移除硬编码的 FORBIDDEN_KEYWORDS（只含 7 个关键字，缺失 12 个），
# 改为从契约文件动态加载完整 19 关键字列表
_FORBIDDEN_KEYWORDS_CACHE: list[str] | None = None


def _get_forbidden_keywords() -> list[str]:
    """获取禁止的 SQL 关键字（从契约加载，fail-closed）。

    使用模块级缓存避免重复文件 I/O，缓存可被测试清理。
    """
    global _FORBIDDEN_KEYWORDS_CACHE
    if _FORBIDDEN_KEYWORDS_CACHE is not None:
        return _FORBIDDEN_KEYWORDS_CACHE
    # strict=False：prompt 回归是非关键路径，契约缺失时用完整回退列表
    _FORBIDDEN_KEYWORDS_CACHE = load_forbidden_keywords(strict=False)
    return _FORBIDDEN_KEYWORDS_CACHE


def _clear_forbidden_keywords_cache() -> None:
    """清理禁止关键字缓存（供测试使用）"""
    global _FORBIDDEN_KEYWORDS_CACHE
    _FORBIDDEN_KEYWORDS_CACHE = None


@dataclass(frozen=True)
class PromptFixtureResult:
    """单条 Prompt fixture 的回放结果"""

    case_id: str
    task: str
    passed: bool
    expected: dict[str, Any]
    actual: dict[str, Any]
    question: str = ""
    expected_type: str = "answer"
    actual_type: str = "unknown"
    failure_reason: str | None = None
    confidence_check: dict[str, Any] = field(default_factory=dict)
    safety_check: dict[str, Any] = field(default_factory=dict)
    raw_output_file: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class PromptRegressionReport:
    """Prompt 回归报告对象"""

    run_id: str
    timestamp: str
    model_name: str
    cases: list[PromptFixtureResult]
    markdown_path: str
    json_path: str
    raw_output_refs: list[str]

    def __iter__(self):
        """兼容旧测试：允许把报告当作 case 列表遍历"""
        return iter(self.cases)

    def __bool__(self) -> bool:
        """兼容旧测试：报告包含 case 时为真"""
        return bool(self.cases)

    @property
    def failures(self) -> list[PromptFixtureResult]:
        """返回失败用例"""
        return [case for case in self.cases if not case.passed]

    @property
    def summary(self) -> dict[str, Any]:
        """生成报告摘要"""
        return {
            "total_cases": len(self.cases),
            "passed": sum(1 for case in self.cases if case.passed),
            "failed": sum(1 for case in self.cases if not case.passed),
            "skipped": 0,
            "answer_cases": sum(1 for case in self.cases if case.expected_type == "answer"),
            "clarification_cases": sum(
                1 for case in self.cases if case.expected_type == "clarification"
            ),
            "refusal_cases": sum(1 for case in self.cases if case.expected_type == "refusal"),
        }


def extract_json_object(text: str) -> dict[str, Any]:
    """从 LLM 输出中提取 JSON 对象"""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = [line for line in stripped.splitlines() if not line.strip().startswith("```")]
        stripped = "\n".join(lines).strip()
    return json.loads(stripped)


def question_intent_from_dict(data: dict[str, Any]) -> QuestionIntent:
    """从字典构造 QuestionIntent"""
    time_range = data.get("time_range") or {}
    return QuestionIntent(
        domain=Domain(data["domain"]) if data.get("domain") else None,
        intent_type=IntentType(data["intent_type"]) if data.get("intent_type") else None,
        metrics=data.get("metrics", []),
        time_range=TimeRange(
            type=TimeRangeType(time_range.get("type", TimeRangeType.FUZZY.value)),
            start=time_range.get("start"),
            end=time_range.get("end"),
            raw_expression=time_range.get("raw_expression"),
        ),
        dimensions=data.get("dimensions", []),
        filters=[
            Filter(
                field=item["field"],
                op=item["op"],
                value=item["value"],
                value_type=item.get("value_type", "string"),
            )
            for item in data.get("filters", [])
        ],
        needs_clarification=data.get("needs_clarification", False),
        clarification_reason=data.get("clarification_reason"),
        confidence=data.get("confidence", 0.0),
        raw_question=data.get("raw_question"),
    )


def sql_plan_from_dict(data: dict[str, Any]) -> SQLPlan:
    """从字典构造 SQLPlan"""
    return SQLPlan(
        strategy=Strategy(data["strategy"]),
        primary_table=data.get("primary_table"),
        joins=[
            JoinPlan(
                table=item["table"],
                on=item["on"],
                type=item.get("type", "INNER"),
            )
            for item in data.get("joins", [])
        ],
        where_clauses=data.get("where_clauses", []),
        group_by=data.get("group_by", []),
        order_by=data.get("order_by", []),
        aggregations=[
            Aggregation(expr=item["expr"], alias=item["alias"])
            for item in data.get("aggregations", [])
        ],
        limit=data.get("limit"),
        downgrade_reason=data.get("downgrade_reason"),
        confidence=data.get("confidence", 0.0),
    )


class PromptFixtureRunner:
    """执行 Prompt fixture 离线回放"""

    def __init__(
        self,
        llm_client: LLMClient,
        fixture_dir: Path | str = "tests/fixtures/prompts",
        prompt_dir: Path | str = "prompts",
        report_dir: Path | str = "harness/reports",
        model_name: str = "mock",
        run_id: str | None = None,
    ):
        self._llm_client = llm_client
        self._fixture_dir = Path(fixture_dir)
        self._prompt_loader = PromptLoader(prompt_dir)
        self._report_dir = Path(report_dir)
        self._model_name = model_name
        self._run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self._timestamp = datetime.now(timezone.utc).isoformat()
        self._raw_output_refs: list[str] = []

    def run_regression(self) -> PromptRegressionReport:
        """执行回归并写入 Markdown/JSON 报告"""
        cases = self.run_all()
        return self._write_reports(cases)

    def run_all(self) -> list[PromptFixtureResult]:
        """执行当前支持的全部 Prompt fixture"""
        return [
            *self.run_intent_cases(),
            *self.run_sql_plan_cases(),
        ]

    def run_intent_cases(self) -> list[PromptFixtureResult]:
        """回放意图分类 fixture"""
        results: list[PromptFixtureResult] = []
        for case in self._load_cases("intent_classifier_cases.yml"):
            expected_type = self._expected_type(case)
            expected = self._expected_payload(case)
            actual, raw_output, parse_success, error = self._complete_json("intent_classifier", case)
            result = self._compare(
                case=case,
                task="intent_classifier",
                expected=expected,
                actual=actual,
                raw_output=raw_output,
                parse_success=parse_success,
                error=error,
                expected_type=expected_type,
            )
            results.append(result)
        return results

    def run_sql_plan_cases(self) -> list[PromptFixtureResult]:
        """回放 SQL 规划 fixture"""
        results: list[PromptFixtureResult] = []
        for case in self._load_cases("sql_planner_cases.yml"):
            expected = self._expected_payload(case)
            actual, raw_output, parse_success, error = self._complete_json("sql_planner", case)
            result = self._compare(
                case=case,
                task="sql_planner",
                expected=expected,
                actual=actual,
                raw_output=raw_output,
                parse_success=parse_success,
                error=error,
                expected_type=self._expected_type(case),
            )
            results.append(result)
        return results

    def _load_cases(self, filename: str) -> list[dict[str, Any]]:
        """读取 fixture 用例列表"""
        data = yaml.safe_load((self._fixture_dir / filename).read_text(encoding="utf-8"))
        return data["cases"]

    def _complete_json(
        self,
        task: str,
        case: dict[str, Any],
    ) -> tuple[dict[str, Any], str, bool, str | None]:
        """调用 LLM 并解析 JSON"""
        raw_output = ""
        try:
            response = self._llm_client.complete(
                LLMRequest(
                    task=task,
                    prompt=self._render_prompt(task, case),
                    metadata={"case_id": case["id"], "question": case.get("question")},
                )
            )
            raw_output = response.content
            return extract_json_object(response.content), raw_output, True, None
        except Exception as exc:
            return {}, raw_output, False, str(exc)

    def _render_prompt(self, task: str, case: dict[str, Any]) -> str:
        """渲染 fixture 回放用 Prompt"""
        template = self._prompt_loader.load(task)
        payload = json.dumps(case, ensure_ascii=False, indent=2)
        return f"{template}\n\n## 本次输入\n```json\n{payload}\n```"

    def _compare(
        self,
        case: dict[str, Any],
        task: str,
        expected: dict[str, Any],
        actual: dict[str, Any],
        raw_output: str,
        parse_success: bool,
        error: str | None,
        expected_type: str,
    ) -> PromptFixtureResult:
        """比较期望输出和实际输出"""
        actual_type = self._actual_type(task, actual)
        confidence_check = self._check_confidence(case, actual)
        safety_check = self._check_safety(task, actual, raw_output)
        failure_reason = self._failure_reason(
            case=case,
            task=task,
            expected=expected,
            actual=actual,
            expected_type=expected_type,
            actual_type=actual_type,
            parse_success=parse_success,
            error=error,
            confidence_check=confidence_check,
            safety_check=safety_check,
        )
        passed = failure_reason is None
        raw_output_file = self._save_raw_output(
            case=case,
            task=task,
            raw_output=raw_output,
            parsed_output=actual,
            parse_success=parse_success,
            validation_success=passed,
            error_message=error or failure_reason,
        )
        return PromptFixtureResult(
            case_id=case["id"],
            task=task,
            passed=passed,
            expected=expected,
            actual=actual,
            question=case.get("question") or case.get("input_intent", {}).get("raw_question", ""),
            expected_type=expected_type,
            actual_type=actual_type,
            failure_reason=failure_reason,
            confidence_check=confidence_check,
            safety_check=safety_check,
            raw_output_file=raw_output_file,
            error=error,
        )

    def _expected_type(self, case: dict[str, Any]) -> str:
        """读取期望类型，兼容旧字段"""
        return case.get("expected_type") or case.get("expected_behavior") or "answer"

    def _expected_payload(self, case: dict[str, Any]) -> dict[str, Any]:
        """读取期望输出，兼容旧字段"""
        if "expected_intent" in case:
            return case["expected_intent"]
        if "expected_sql_plan" in case:
            return case["expected_sql_plan"]
        if "expected_plan" in case:
            return case["expected_plan"]
        if "expected_refusal" in case:
            return case["expected_refusal"]
        return {}

    def _actual_type(self, task: str, actual: dict[str, Any]) -> str:
        """根据实际输出判断类型"""
        if actual.get("refusal") is True or actual.get("refusal_reason"):
            return "refusal"
        if actual.get("needs_clarification") is True:
            return "clarification"
        if actual.get("strategy") == Strategy.NEED_CLARIFICATION.value:
            return "clarification"
        if actual:
            return "answer"
        return "unknown"

    def _check_confidence(self, case: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
        """按区间检查 confidence"""
        expected_min = case.get("confidence_min")
        expected_max = case.get("confidence_max")
        actual_value = actual.get("confidence")
        check = {
            "expected_min": expected_min,
            "expected_max": expected_max,
            "actual": actual_value,
            "passed": True,
            "missing": False,
        }
        if expected_min is None and expected_max is None:
            return check
        if actual_value is None:
            check["passed"] = False
            check["missing"] = True
            return check
        if expected_min is not None and actual_value < expected_min:
            check["passed"] = False
        if expected_max is not None and actual_value > expected_max:
            check["passed"] = False
        return check

    def _check_safety(self, task: str, actual: dict[str, Any], raw_output: str) -> dict[str, Any]:
        """检查 Prompt 回归阶段的安全边界"""
        check = {
            "llm_direct_sql": self._has_direct_sql(actual, raw_output),
            "sql_plan_to_sql_ran": False,
            "validate_sql_safety_ran": False,
            "passed": True,
            "errors": [],
        }
        if task != "sql_planner" or check["llm_direct_sql"]:
            check["passed"] = not check["llm_direct_sql"]
            return check

        try:
            plan = sql_plan_from_dict(actual)

            # Phase 4：UNSUPPORTED_MULTI_PLAN 是跨表多指标占位符，
            # Agent 会在运行时拆分为 SubIntent 并分别生成 SQL。
            # fixture 回归中跳过 SQL 生成和安全校验（无单表可校验）。
            if plan.strategy == Strategy.UNSUPPORTED_MULTI_PLAN:
                check["sql_plan_to_sql_ran"] = False
                check["validate_sql_safety_ran"] = False
                # 仅校验策略本身是否有效（能成功解析即为通过）
                check["passed"] = True
                return check

            plan_errors = plan.validate(AVAILABLE_TABLES, JOIN_WHITELIST)
            if plan_errors:
                check["schema_validation_failed"] = True
                check["errors"].extend(plan_errors)
            sql = sql_plan_to_sql(plan)
            check["sql_plan_to_sql_ran"] = True
            check["validate_sql_safety_ran"] = True
            safety_errors = validate_sql_safety(
                sql,
                forbidden_keywords=_get_forbidden_keywords(),
                available_tables=AVAILABLE_TABLES,
                join_whitelist=JOIN_WHITELIST,
            )
            check["errors"].extend(safety_errors)
        except Exception as exc:
            check["errors"].append(str(exc))
        check["passed"] = not check["errors"]
        return check

    def _has_direct_sql(self, actual: dict[str, Any], raw_output: str) -> bool:
        """识别 LLM 是否直接给出了最终 SQL"""
        if "sql" in actual:
            return True
        stripped = raw_output.strip()
        return bool(re.match(r"^(SELECT|WITH)\b", stripped, flags=re.IGNORECASE))

    def _failure_reason(
        self,
        case: dict[str, Any],
        task: str,
        expected: dict[str, Any],
        actual: dict[str, Any],
        expected_type: str,
        actual_type: str,
        parse_success: bool,
        error: str | None,
        confidence_check: dict[str, Any],
        safety_check: dict[str, Any],
    ) -> str | None:
        """生成失败原因分类"""
        if not parse_success or error:
            return "raw_output_parse_failed"
        if safety_check.get("llm_direct_sql"):
            return "llm_direct_sql_detected"
        if expected_type != actual_type:
            if expected_type == "clarification":
                return "clarification_expected_but_answered"
            if expected_type == "refusal":
                return "refusal_expected_but_answered"
            return "intent_mismatch"
        if not confidence_check.get("passed", True):
            return "confidence_missing" if confidence_check.get("missing") else "confidence_out_of_range"
        if task == "intent_classifier":
            return self._intent_failure(case, expected, actual)
        if task == "sql_planner":
            if safety_check.get("schema_validation_failed"):
                return "schema_validation_failed"
            if not safety_check.get("passed", True):
                return "safety_validation_failed"
            plan_reason = self._plan_failure(case, expected, actual)
            if plan_reason:
                return plan_reason
        return None

    def _intent_failure(
        self,
        case: dict[str, Any],
        expected: dict[str, Any],
        actual: dict[str, Any],
    ) -> str | None:
        """比较 Intent 输出"""
        expected_type = self._expected_type(case)
        if expected_type == "refusal":
            expected_text = case.get("expected_refusal_contains")
            if expected_text and expected_text not in str(actual.get("refusal_reason", "")):
                return "refusal_text_mismatch"
            return None
        if expected_type == "clarification":
            expected_text = case.get("expected_clarification_contains")
            if expected_text and expected_text not in str(actual.get("clarification_reason", "")):
                return "clarification_text_mismatch"

        for key, value in expected.items():
            if key == "confidence":
                continue
            if actual.get(key) != value:
                return "intent_mismatch"
        return None

    def _plan_failure(
        self,
        case: dict[str, Any],
        expected: dict[str, Any],
        actual: dict[str, Any],
    ) -> str | None:
        """比较 SQLPlan 输出"""
        # Phase 4：UNSUPPORTED_MULTI_PLAN 没有 primary_table，
        # 表引用检查应在 expected_tables 列表中完成（跨表场景）
        actual_strategy = actual.get("strategy", "")
        if actual_strategy != Strategy.UNSUPPORTED_MULTI_PLAN.value:
            for table in case.get("expected_tables", []):
                if table != actual.get("primary_table") and table not in [
                    join.get("table") for join in actual.get("joins", [])
                ]:
                    return "table_mismatch"
        for field in case.get("expected_fields", []):
            if field not in json.dumps(actual, ensure_ascii=False):
                return "field_mismatch"
        for key, value in expected.items():
            if key == "confidence":
                continue
            if actual.get(key) != value:
                return "plan_mismatch"
        return None

    def _save_raw_output(
        self,
        case: dict[str, Any],
        task: str,
        raw_output: str,
        parsed_output: dict[str, Any],
        parse_success: bool,
        validation_success: bool,
        error_message: str | None,
    ) -> str:
        """保存单次 LLM 原始输出"""
        raw_dir = self._report_dir / "llm_raw_outputs" / self._run_id
        raw_dir.mkdir(parents=True, exist_ok=True)
        path = raw_dir / f"{case['id']}_{task}_{uuid4().hex[:8]}.json"
        payload = {
            "question_id": case["id"],
            "question": case.get("question") or case.get("input_intent", {}).get("raw_question"),
            "stage": "intent" if task == "intent_classifier" else "plan",
            "prompt_name": task,
            "model_name": self._model_name,
            "raw_output": raw_output,
            "parsed_output": parsed_output,
            "parse_success": parse_success,
            "validation_success": validation_success,
            "error_message": error_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        ref = str(path)
        self._raw_output_refs.append(ref)
        return ref

    def _write_reports(self, cases: list[PromptFixtureResult]) -> PromptRegressionReport:
        """写入 Markdown 和 JSON 报告"""
        self._report_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = self._report_dir / "prompt_regression_latest.md"
        json_path = self._report_dir / "prompt_regression_latest.json"
        report = PromptRegressionReport(
            run_id=self._run_id,
            timestamp=self._timestamp,
            model_name=self._model_name,
            cases=cases,
            markdown_path=str(markdown_path),
            json_path=str(json_path),
            raw_output_refs=list(self._raw_output_refs),
        )
        markdown_path.write_text(self._render_markdown(report), encoding="utf-8")
        json_path.write_text(
            json.dumps(self._report_to_dict(report), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return report

    def _render_markdown(self, report: PromptRegressionReport) -> str:
        """渲染 Markdown 报告"""
        summary = report.summary
        lines = [
            "# Prompt Regression Report",
            "",
            "## Summary",
            "",
            f"* total cases: {summary['total_cases']}",
            f"* passed: {summary['passed']}",
            f"* failed: {summary['failed']}",
            f"* skipped: {summary['skipped']}",
            f"* answer cases: {summary['answer_cases']}",
            f"* clarification cases: {summary['clarification_cases']}",
            f"* refusal cases: {summary['refusal_cases']}",
            f"* model_name: {report.model_name}",
            f"* run_time: {report.timestamp}",
            "",
            "## Failed Cases",
            "",
        ]
        if not report.failures:
            lines.append("无失败样例。")
        for case in report.failures:
            lines.extend([
                f"### {case.case_id}",
                "",
                f"* question_id: {case.case_id}",
                f"* question: {case.question}",
                f"* expected_type: {case.expected_type}",
                f"* actual_type: {case.actual_type}",
                f"* failure_reason: {case.failure_reason}",
                f"* expected: `{json.dumps(case.expected, ensure_ascii=False)}`",
                f"* actual: `{json.dumps(case.actual, ensure_ascii=False)}`",
                f"* raw_output_file: {case.raw_output_file}",
                "",
            ])
        lines.extend([
            "## Drift Observation",
            "",
            *self._drift_lines(report.cases),
            "",
            "## Safety Check",
            "",
            *self._safety_lines(report.cases),
            "",
            "## Next Regression Cases",
            "",
        ])
        failures = report.failures
        if not failures:
            lines.append("当前没有建议新增的 regression case。")
        for case in failures:
            lines.extend([
                f"* {case.case_id}: 建议加入 regression cases，类型={case.expected_type}，"
                f"失败分类={case.failure_reason}。",
                f"  推荐 fixture: `{json.dumps(self._recommended_fixture(case), ensure_ascii=False)}`",
            ])
        return "\n".join(lines) + "\n"

    def _drift_lines(self, cases: list[PromptFixtureResult]) -> list[str]:
        """生成漂移观察段落"""
        lines = [
            "* confidence 漂移: " + self._count_reason(cases, "confidence_out_of_range"),
            "* intent 漂移: " + self._count_reason(cases, "intent_mismatch"),
            "* plan 漂移: " + self._count_reason(cases, "plan_mismatch"),
            "* answer 文案漂移: 当前未启用 answer 文案比较。",
            "* clarification/refusal 类型漂移: "
            + str(sum(1 for case in cases if case.expected_type != case.actual_type)),
        ]
        return lines

    def _safety_lines(self, cases: list[PromptFixtureResult]) -> list[str]:
        """生成安全检查段落"""
        direct_sql = any(case.safety_check.get("llm_direct_sql") for case in cases)
        sql_plan_ran = all(
            case.task != "sql_planner" or case.safety_check.get("sql_plan_to_sql_ran")
            or case.safety_check.get("llm_direct_sql")
            for case in cases
        )
        safety_ran = all(
            case.task != "sql_planner" or case.safety_check.get("validate_sql_safety_ran")
            or case.safety_check.get("llm_direct_sql")
            for case in cases
        )
        unauthorized = [
            case.case_id for case in cases
            if case.failure_reason in {"table_mismatch", "field_mismatch", "safety_validation_failed"}
        ]
        return [
            f"* 是否出现 LLM 直接 SQL: {'是' if direct_sql else '否'}",
            f"* 是否绕过 SQLPlan: {'否' if sql_plan_ran else '是'}",
            f"* 是否绕过 validate_sql_safety(): {'否' if safety_ran else '是'}",
            f"* 是否访问未授权表字段: {'是' if unauthorized else '否'}",
        ]

    def _report_to_dict(self, report: PromptRegressionReport) -> dict[str, Any]:
        """生成机器可读报告"""
        cases = [self._case_to_dict(case) for case in report.cases]
        return {
            "run_id": report.run_id,
            "timestamp": report.timestamp,
            "model_name": report.model_name,
            "summary": report.summary,
            "cases": cases,
            "failures": [case for case in cases if not case["passed"]],
            "raw_output_refs": report.raw_output_refs,
        }

    def _case_to_dict(self, case: PromptFixtureResult) -> dict[str, Any]:
        """序列化单个 case"""
        return {
            "question_id": case.case_id,
            "question": case.question,
            "expected_type": case.expected_type,
            "actual_type": case.actual_type,
            "passed": case.passed,
            "failure_reason": case.failure_reason,
            "expected": case.expected,
            "actual": case.actual,
            "confidence_check": case.confidence_check,
            "safety_check": case.safety_check,
            "raw_output_file": case.raw_output_file,
            "suggest_regression_case": not case.passed,
            "recommended_regression_case_type": case.expected_type if not case.passed else None,
            "failure_category": case.failure_reason,
            "recommended_fixture": self._recommended_fixture(case) if not case.passed else None,
        }

    def _recommended_fixture(self, case: PromptFixtureResult) -> dict[str, Any]:
        """生成失败样例的 regression fixture 建议"""
        return {
            "id": case.case_id,
            "question": case.question,
            "expected_type": case.expected_type,
            "failure_reason": case.failure_reason,
            "expected": case.expected,
            "actual": case.actual,
        }

    def _count_reason(self, cases: list[PromptFixtureResult], reason: str) -> str:
        """统计指定失败原因"""
        return str(sum(1 for case in cases if case.failure_reason == reason))
