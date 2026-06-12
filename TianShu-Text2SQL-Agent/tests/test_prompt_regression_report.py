import json
import shutil
from uuid import uuid4
from pathlib import Path

import yaml

from harness.run_prompt_regression import build_fixture_mock_client, run_prompt_regression
from src.llm import MockLLMClient
from src.llm_pipeline import PromptFixtureRunner


FIXTURE_DIR = Path("tests/fixtures/prompts")


def _report_tmp() -> Path:
    """创建项目内临时报表目录，避开系统 Temp 权限问题"""
    path = Path("harness/reports/test_tmp") / uuid4().hex
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def _load_cases(filename: str) -> list[dict]:
    """读取 Prompt fixture 用例"""
    data = yaml.safe_load((FIXTURE_DIR / filename).read_text(encoding="utf-8"))
    return data["cases"]


def test_answer_clarification_and_refusal_fixtures_can_pass():
    """answer、clarification、refusal 三类 fixture 都应支持回归通过"""
    client = build_fixture_mock_client(FIXTURE_DIR)
    runner = PromptFixtureRunner(
        client,
        fixture_dir=FIXTURE_DIR,
        prompt_dir=Path("prompts"),
        report_dir=_report_tmp(),
        model_name="mock-model",
    )

    report = runner.run_regression()

    case_types = {case.expected_type for case in report.cases}
    assert {"answer", "clarification", "refusal"}.issubset(case_types)
    assert all(case.passed for case in report.cases)


def test_confidence_range_passes_and_out_of_range_fails():
    """confidence 应按区间比较，超出范围时失败"""
    case = _load_cases("intent_classifier_cases.yml")[0]
    good = dict(case["expected_intent"], confidence=0.82)
    bad = dict(case["expected_intent"], confidence=0.31)

    good_client = MockLLMClient({("intent_classifier", case["id"]): json.dumps(good)})
    good_runner = PromptFixtureRunner(
        good_client,
        fixture_dir=FIXTURE_DIR,
        prompt_dir=Path("prompts"),
        report_dir=_report_tmp() / "good",
        model_name="mock-model",
    )

    good_result = good_runner.run_intent_cases()[0]

    assert good_result.passed is True
    assert good_result.confidence_check["passed"] is True

    bad_client = MockLLMClient({("intent_classifier", case["id"]): json.dumps(bad)})
    bad_runner = PromptFixtureRunner(
        bad_client,
        fixture_dir=FIXTURE_DIR,
        prompt_dir=Path("prompts"),
        report_dir=_report_tmp() / "bad",
        model_name="mock-model",
    )

    bad_result = bad_runner.run_intent_cases()[0]

    assert bad_result.passed is False
    assert bad_result.confidence_check["passed"] is False
    assert bad_result.failure_reason == "confidence_out_of_range"


def test_markdown_json_and_raw_outputs_are_written_without_api_key():
    """回归运行应生成 Markdown、JSON 和 raw output，且不包含 API Key"""
    secret = "sk-test-secret-should-not-appear"
    client = build_fixture_mock_client(FIXTURE_DIR)
    report_dir = _report_tmp()

    report = run_prompt_regression(
        client,
        fixture_dir=FIXTURE_DIR,
        prompt_dir=Path("prompts"),
        report_dir=report_dir,
        model_name="mock-model",
        api_key_redaction_probe=secret,
    )

    markdown = report_dir / "prompt_regression_latest.md"
    machine = report_dir / "prompt_regression_latest.json"

    assert markdown.exists()
    assert machine.exists()
    assert report.raw_output_refs
    assert all(Path(item).exists() for item in report.raw_output_refs)
    assert secret not in markdown.read_text(encoding="utf-8")
    assert secret not in machine.read_text(encoding="utf-8")


def test_raw_output_file_contains_required_audit_fields():
    """raw output 文件应包含审计所需字段"""
    client = build_fixture_mock_client(FIXTURE_DIR)
    report = run_prompt_regression(
        client,
        fixture_dir=FIXTURE_DIR,
        prompt_dir=Path("prompts"),
        report_dir=_report_tmp(),
        model_name="mock-model",
    )

    raw = json.loads(Path(report.raw_output_refs[0]).read_text(encoding="utf-8"))

    assert {
        "question_id",
        "question",
        "stage",
        "prompt_name",
        "model_name",
        "raw_output",
        "parsed_output",
        "parse_success",
        "validation_success",
        "error_message",
        "timestamp",
    }.issubset(raw)


def test_llm_direct_sql_is_failed_before_execution():
    """LLM 直接输出最终 SQL 应被标记失败"""
    case = _load_cases("sql_planner_cases.yml")[0]
    client = MockLLMClient({
        ("sql_planner", case["id"]): json.dumps({"sql": "SELECT * FROM gold.fact_trips"}),
    })
    runner = PromptFixtureRunner(
        client,
        fixture_dir=FIXTURE_DIR,
        prompt_dir=Path("prompts"),
        report_dir=_report_tmp(),
        model_name="mock-model",
    )

    result = runner.run_sql_plan_cases()[0]

    assert result.passed is False
    assert result.failure_reason == "llm_direct_sql_detected"
    assert result.safety_check["llm_direct_sql"] is True


def test_sql_plan_safety_validation_must_pass():
    """SQLPlan 通过后仍必须经过 validate_sql_safety"""
    case = _load_cases("sql_planner_cases.yml")[0]
    unsafe = dict(case["expected_plan"])
    unsafe["primary_table"] = "silver.fact_trips"
    client = MockLLMClient({("sql_planner", case["id"]): json.dumps(unsafe)})
    runner = PromptFixtureRunner(
        client,
        fixture_dir=FIXTURE_DIR,
        prompt_dir=Path("prompts"),
        report_dir=_report_tmp(),
        model_name="mock-model",
    )

    result = runner.run_sql_plan_cases()[0]

    assert result.passed is False
    assert result.failure_reason in {"schema_validation_failed", "safety_validation_failed"}
    assert result.safety_check["validate_sql_safety_ran"] is True
