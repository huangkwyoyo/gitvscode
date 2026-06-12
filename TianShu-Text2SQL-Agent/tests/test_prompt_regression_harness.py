from pathlib import Path
from uuid import uuid4

import pytest

from harness.run_prompt_regression import (
    build_fixture_mock_client,
    build_llm_client,
    run_prompt_regression,
)
from src.llm import MockLLMClient, OpenAIChatLLMClient


def _report_tmp() -> Path:
    """创建项目内测试报告目录"""
    path = Path("harness/reports/test_tmp") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_prompt_regression_harness_replays_all_current_fixtures():
    """Prompt 回归入口应回放当前所有可回答 fixture"""
    fixture_dir = Path("tests/fixtures/prompts")
    client = build_fixture_mock_client(fixture_dir)

    results = run_prompt_regression(
        client,
        fixture_dir=fixture_dir,
        prompt_dir=Path("prompts"),
        report_dir=_report_tmp(),
    )

    assert results
    assert all(result.passed for result in results)


def test_prompt_regression_provider_factory_supports_mock_and_openai(monkeypatch):
    """Prompt 回归入口应支持 mock / openai / deepseek 三种 provider"""
    fixture_dir = Path("tests/fixtures/prompts")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    mock_client = build_llm_client("mock", fixture_dir=fixture_dir, model="ignored")
    openai_client = build_llm_client("openai", fixture_dir=fixture_dir, model="test-model")
    deepseek_client = build_llm_client("deepseek", fixture_dir=fixture_dir)

    assert isinstance(mock_client, MockLLMClient)
    assert isinstance(openai_client, OpenAIChatLLMClient)
    assert isinstance(deepseek_client, OpenAIChatLLMClient)
    # DeepSeek 推荐模型（deepseek-chat 将于 2026/07/24 弃用）
    assert deepseek_client._model == "deepseek-v4-pro"


def test_prompt_regression_provider_factory_rejects_unknown_provider():
    """未知 provider 应显式失败"""
    with pytest.raises(ValueError, match="provider"):
        build_llm_client("unknown")
