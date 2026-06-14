import json
from pathlib import Path

import pytest
import yaml

from harness.run_prompt_regression import build_fixture_mock_client
from src.agent import Text2SQLAgent
from src.ir import Domain, Strategy
from src.llm import LLMRequest, MockLLMClient, OpenAIChatLLMClient
from src.llm_pipeline import (
    PromptFixtureRunner,
    question_intent_from_dict,
    sql_plan_from_dict,
)


FIXTURE_DIR = Path("tests/fixtures/prompts")


def _load_cases(filename: str) -> list[dict]:
    """读取 Prompt fixture 用例"""
    data = yaml.safe_load((FIXTURE_DIR / filename).read_text(encoding="utf-8"))
    return data["cases"]


def test_mock_llm_client_replays_responses_by_task_and_case_id():
    """MockLLMClient 应按任务和 case_id 回放响应并记录调用"""
    client = MockLLMClient({
        ("intent_classifier", "case_a"): '{"metrics": ["trip_count"]}',
    })

    response = client.complete(
        LLMRequest(
            task="intent_classifier",
            prompt="classify",
            metadata={"case_id": "case_a"},
        )
    )

    assert response.content == '{"metrics": ["trip_count"]}'
    assert client.calls[0].task == "intent_classifier"
    assert client.calls[0].metadata["case_id"] == "case_a"


def test_prompt_fixture_runner_compares_mock_llm_output_with_expected_ir():
    """fixture 回放器应比较 Mock LLM 输出和期望 IR"""
    client = build_fixture_mock_client(FIXTURE_DIR)
    runner = PromptFixtureRunner(client, fixture_dir=FIXTURE_DIR, prompt_dir=Path("prompts"))

    results = runner.run_all()

    assert results
    assert all(item.passed for item in results)


def test_llm_agent_uses_mock_llm_for_intent_and_plan():
    """LLM 版 Agent 应通过可插拔客户端完成意图和规划"""
    intent_case = _load_cases("intent_classifier_cases.yml")[0]
    plan_case = _load_cases("sql_planner_cases.yml")[0]
    client = MockLLMClient({
        "intent_classifier": json.dumps(intent_case["expected_intent"], ensure_ascii=False),
        "sql_planner": json.dumps(plan_case["expected_plan"], ensure_ascii=False),
    })
    agent = Text2SQLAgent(mode="llm", llm_client=client)

    response = agent.ask(intent_case["question"])

    assert response.refusal is False
    assert response.clarification_needed is False
    assert response.intent.domain == Domain.TRAFFIC
    assert response.plan.strategy == Strategy.G3_DIRECT
    assert response.plan.primary_table == "gold.dws_daily_trip_summary"
    assert [call.task for call in client.calls] == ["intent_classifier", "sql_planner"]


def test_agent_raw_output_failure_file_is_sanitized_and_redacted(tmp_path):
    """Agent 保存失败证据时，文件名必须安全且内容不能泄露密钥。"""
    agent = Text2SQLAgent()
    agent._raw_output_enabled = True
    agent._raw_output_dir = tmp_path

    saved_path = agent._save_raw_output_on_failure(
        question="2026/01 金额是多少？",
        stage="intent",
        prompt_name="intent_classifier",
        raw_output="OPENAI_API_KEY=sk-secret-value Authorization: Bearer abc123",
        parsed_output={"token": "token=xyz"},
        parse_success=False,
        validation_success=False,
        error_message="DEEPSEEK_API_KEY=deepseek-secret",
    )

    path = Path(saved_path)
    payload_text = path.read_text(encoding="utf-8")

    assert path.exists()
    assert "/" not in path.name
    assert "sk-secret-value" not in payload_text
    assert "abc123" not in payload_text
    assert "xyz" not in payload_text
    assert "deepseek-secret" not in payload_text
    assert "[REDACTED]" in payload_text


def test_rule_agent_still_uses_rule_path_without_llm_calls():
    """规则版 Agent 应继续使用原有规则路径"""
    client = MockLLMClient({})
    agent = Text2SQLAgent(mode="rule", llm_client=client)

    response = agent.ask("2026年1月每天有多少行程？")

    assert response.intent.metrics == ["trip_count"]
    assert response.plan.primary_table == "gold.dws_daily_trip_summary"
    assert client.calls == []


def test_openai_client_requires_api_key_before_network_call(monkeypatch):
    """真实 API 客户端缺少密钥时应在本地失败"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # 同时屏蔽 secrets 文件回退，确保三种密钥来源全部为空
    monkeypatch.setattr(
        "src.llm._load_api_key_from_secrets", lambda provider=None: None
    )
    client = OpenAIChatLLMClient(api_key=None)

    with pytest.raises(ValueError, match="缺少 API 密钥"):
        client.complete(LLMRequest(task="intent_classifier", prompt="{}"))


def test_ir_dict_converters_preserve_fixture_contract():
    """IR 转换器应复用 fixture 契约字段"""
    intent = question_intent_from_dict(_load_cases("intent_classifier_cases.yml")[0]["expected_intent"])
    plan = sql_plan_from_dict(_load_cases("sql_planner_cases.yml")[0]["expected_plan"])

    assert intent.validate() == []
    assert intent.metrics == ["trip_count"]
    assert plan.validate(
        {"gold.dws_daily_trip_summary", "gold.dim_date"},
        {("gold.dws_daily_trip_summary", "gold.dim_date")},
    ) == []
