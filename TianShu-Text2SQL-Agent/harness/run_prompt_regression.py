"""Prompt fixture 离线回归入口"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm import LLMClient, MockLLMClient, OpenAIChatLLMClient
from src.llm_pipeline import PromptFixtureResult, PromptFixtureRunner, PromptRegressionReport


def build_fixture_mock_client(fixture_dir: Path | str = "tests/fixtures/prompts") -> MockLLMClient:
    """从 fixture 期望输出构造 Mock LLM 客户端"""
    fixture_path = Path(fixture_dir)
    responses: dict[str | tuple[str, str], str] = {}

    intent_cases = _load_cases(fixture_path / "intent_classifier_cases.yml")
    for case in intent_cases:
        expected = case.get("expected_intent") or case.get("expected_refusal") or {}
        responses[("intent_classifier", case["id"])] = json.dumps(
            expected,
            ensure_ascii=False,
        )

    plan_cases = _load_cases(fixture_path / "sql_planner_cases.yml")
    for case in plan_cases:
        responses[("sql_planner", case["id"])] = json.dumps(
            case["expected_plan"],
            ensure_ascii=False,
        )

    return MockLLMClient(responses)


def build_llm_client(
    provider: str,
    fixture_dir: Path | str = "tests/fixtures/prompts",
    model: str | None = None,
) -> LLMClient:
    """根据 provider 构造 LLM 客户端"""
    if provider == "mock":
        return build_fixture_mock_client(fixture_dir)
    if provider in ("openai", "deepseek"):
        # DeepSeek 推荐模型 deepseek-v4-pro / deepseek-v4-flash
        model = model or ("deepseek-v4-pro" if provider == "deepseek" else "gpt-4.1-mini")
        return OpenAIChatLLMClient(model=model, provider=provider)
    raise ValueError(f"provider 只能是 mock / openai / deepseek，不支持: {provider}")


def run_prompt_regression(
    llm_client: LLMClient,
    fixture_dir: Path | str = "tests/fixtures/prompts",
    prompt_dir: Path | str = "prompts",
    report_dir: Path | str = "harness/reports",
    model_name: str = "mock",
    api_key_redaction_probe: str | None = None,
) -> PromptRegressionReport:
    """运行 Prompt fixture 回归"""
    runner = PromptFixtureRunner(
        llm_client,
        fixture_dir=fixture_dir,
        prompt_dir=prompt_dir,
        report_dir=report_dir,
        model_name=model_name,
    )
    # api_key_redaction_probe 只用于测试报告不含密钥；不写入任何输出。
    _ = api_key_redaction_probe
    return runner.run_regression()


def _load_cases(path: Path) -> list[dict]:
    """读取 YAML 用例列表"""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["cases"]


def main(argv: list[str] | None = None) -> int:
    """命令行入口"""
    parser = argparse.ArgumentParser(description="运行 Prompt fixture 回归")
    parser.add_argument("--provider", choices=["mock", "openai", "deepseek"], default="mock")
    parser.add_argument("--model", default=None, help="默认按 provider 自动选择模型")
    parser.add_argument("--fixture-dir", default="tests/fixtures/prompts")
    parser.add_argument("--prompt-dir", default="prompts")
    args = parser.parse_args(argv)

    client = build_llm_client(args.provider, fixture_dir=args.fixture_dir, model=args.model)
    report = run_prompt_regression(
        client,
        fixture_dir=args.fixture_dir,
        prompt_dir=args.prompt_dir,
        report_dir="harness/reports",
        model_name=args.model or args.provider,
    )
    results = report.cases
    failed = report.failures

    print("=" * 60)
    print(f"TianShu Prompt Fixture Regression ({args.provider})")
    print("=" * 60)
    for item in results:
        status = "PASS" if item.passed else "FAIL"
        print(f"[{status}] {item.task} :: {item.case_id}")
        if item.error:
            print(f"       error={item.error}")

    print("=" * 60)
    print(f"完成: {len(results) - len(failed)} PASS, {len(failed)} FAIL")
    print(f"Markdown 报告: {report.markdown_path}")
    print(f"JSON 报告: {report.json_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
