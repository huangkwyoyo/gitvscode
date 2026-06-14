from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.baselines.failure_triage import (
    build_failure_triage,
    build_failure_triage_from_e2e_report,
)


def _case(
    case_id: str,
    expected_behavior: str,
    categories: list[str],
    assertions: list[dict] | None = None,
) -> dict:
    """构造最小失败 case。"""
    return {
        "case_id": case_id,
        "question_zh": f"{case_id} 问题",
        "expected_behavior": expected_behavior,
        "passed": False,
        "failure_categories": categories,
        "assertions": assertions or [],
        "agent_response_summary": {},
    }


def test_triage_intent_failure_recommends_prompt_and_regression():
    """intent 错应建议修 prompt 并补 regression case。"""
    result = build_failure_triage(
        _case("bad_intent", "answer", ["intent_mismatch"])
    )

    assert result["failure_type"] == "intent 错"
    assert result["recommended_action"] == "修 prompt + 补 regression case"
    assert result["regression_candidate"] is True
    assert result["asset_dependency"] == "none"


def test_triage_plan_failure_recommends_prompt_or_fixture():
    """plan 错应指向 SQLPlan 规划层。"""
    result = build_failure_triage(
        _case("bad_plan", "answer", ["plan_mismatch", "table_mismatch"])
    )

    assert result["failure_type"] == "plan 错"
    assert result["recommended_action"] == "修 prompt 或修 fixture"
    assert result["regression_candidate"] is True


def test_triage_safety_failure_recommends_validator_review():
    """safety 拦截应优先审查安全边界。"""
    result = build_failure_triage(
        _case("bad_safety", "answer", ["safety_validation_failed"])
    )

    assert result["failure_type"] == "safety 拦截"
    assert result["recommended_action"] == "修 schema validator 或补 regression case"
    assert "安全" in result["root_cause_hint"]


def test_triage_execution_failure_can_wait_for_assets():
    """执行失败可能依赖数仓资产补充。"""
    result = build_failure_triage(
        _case("bad_execution", "answer", ["execution_failed"])
    )

    assert result["failure_type"] == "执行失败"
    assert result["recommended_action"] == "等待数仓资产补充或修 fixture"
    assert result["asset_dependency"] == "possible"


def test_triage_explanation_failure_recommends_explainer_prompt():
    """解释不合格应定位到解释层。"""
    result = build_failure_triage(
        _case("bad_explain", "answer", ["answer_content_mismatch"])
    )

    assert result["failure_type"] == "解释不合格"
    assert result["recommended_action"] == "修 prompt 或修 fixture"


def test_triage_clarification_expected_but_answered():
    """应反问但回答应归为反问策略失败。"""
    result = build_failure_triage(
        _case("bad_clarify", "clarification", ["clarification_mismatch"])
    )

    assert result["failure_type"] == "应反问但回答"
    assert result["recommended_action"] == "修 prompt + 补 regression case"


def test_triage_refusal_expected_but_answered():
    """应拒绝但回答应归为拒绝策略失败。"""
    result = build_failure_triage(
        _case("bad_refusal", "refusal", ["refusal_mismatch"])
    )

    assert result["failure_type"] == "应拒绝但回答"
    assert result["recommended_action"] == "修 prompt + 补 regression case"


def test_build_failure_triage_from_e2e_report_skips_passed_cases():
    """报告级 triage 只输出失败用例。"""
    report = {
        "run_id": "run1",
        "cases": [
            {"case_id": "ok", "passed": True, "failure_categories": []},
            _case("bad_plan", "answer", ["plan_mismatch"]),
        ],
    }

    triage = build_failure_triage_from_e2e_report(report)

    assert triage["total_failed"] == 1
    assert triage["items"][0]["case_id"] == "bad_plan"
    assert triage["items"][0]["failure_type"] == "plan 错"
