from pathlib import Path

import pytest


PROMPT_FILES = [
    "intent_classifier.md",
    "sql_planner.md",
    "sql_generator.md",
    "explainer.md",
]


@pytest.mark.parametrize("filename", PROMPT_FILES)
def test_prompt_template_contains_required_contract_sections(filename):
    """Prompt 模板必须声明输入、输出、边界和示例"""
    text = (Path("prompts") / filename).read_text(encoding="utf-8")

    assert "## 输入" in text
    assert "## 输出" in text
    assert "JSON" in text
    assert "## 硬性边界" in text
    assert "## 示例" in text


def test_prompt_loader_reads_template_by_name():
    """PromptLoader 应能按名称加载模板文本"""
    from src.llm import PromptLoader

    loader = PromptLoader(Path("prompts"))

    template = loader.load("intent_classifier")

    assert "QuestionIntent" in template
    assert "只输出 JSON" in template


def test_fake_llm_client_returns_registered_response():
    """FakeLLMClient 用于离线测试 LLM 接口"""
    from src.llm import FakeLLMClient, LLMRequest

    client = FakeLLMClient({"intent_classifier": '{"metrics": ["trip_count"]}'})

    response = client.complete(
        LLMRequest(
            task="intent_classifier",
            prompt="classify",
            metadata={"question": "2026年1月每天有多少行程？"},
        )
    )

    assert response.task == "intent_classifier"
    assert response.content == '{"metrics": ["trip_count"]}'
    assert response.raw == {"source": "fake"}


def test_fake_llm_client_fails_for_unregistered_task():
    """未注册任务应显式失败，避免测试误用空响应"""
    from src.llm import FakeLLMClient, LLMRequest

    client = FakeLLMClient({})

    with pytest.raises(KeyError):
        client.complete(LLMRequest(task="sql_planner", prompt="plan"))
