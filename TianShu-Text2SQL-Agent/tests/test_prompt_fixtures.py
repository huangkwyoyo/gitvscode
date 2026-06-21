import json
from pathlib import Path

import pytest
import yaml

from src.ir import (
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
from src.llm import FakeLLMClient, LLMRequest
from src.sql_gen import sql_plan_to_sql, validate_sql_safety


FIXTURE_DIR = Path("tests/fixtures/prompts")
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


def _load_cases(filename: str) -> list[dict]:
    """读取 Prompt fixture 用例"""
    path = FIXTURE_DIR / filename
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["cases"]


def _question_intent_from_dict(data: dict) -> QuestionIntent:
    """从 fixture 字典构造 QuestionIntent"""
    time_range = data["time_range"]
    return QuestionIntent(
        domain=Domain(data["domain"]) if data.get("domain") else None,
        intent_type=IntentType(data["intent_type"]) if data.get("intent_type") else None,
        metrics=data.get("metrics", []),
        time_range=TimeRange(
            type=TimeRangeType(time_range["type"]),
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


def _sql_plan_from_dict(data: dict) -> SQLPlan:
    """从 fixture 字典构造 SQLPlan"""
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


def test_intent_classifier_fixtures_map_to_valid_intent_or_refusal():
    """意图分类 fixture 应能映射到 IR 或显式拒绝"""
    cases = _load_cases("intent_classifier_cases.yml")

    assert len(cases) >= 7
    for case in cases:
        behavior = case["expected_behavior"]
        if behavior == "refusal":
            refusal = case["expected_refusal"]
            assert refusal["refusal"] is True
            assert refusal["refusal_reason"]
            continue

        intent = _question_intent_from_dict(case["expected_intent"])
        errors = intent.validate()
        if behavior == "answer":
            assert errors == [], case["id"]
        elif behavior == "clarification":
            # B-5: validate() 只做结构性校验，歧义检测由 detect_ambiguity() 处理
            # clarification 意图的 needs_clarification 标志直接由 intent 携带
            assert intent.needs_clarification is True, (
                f"{case['id']}: clarification 意图必须设置 needs_clarification=True"
            )
            assert intent.clarification_reason, (
                f"{case['id']}: clarification 意图必须有 clarification_reason"
            )
        else:
            raise AssertionError(f"未知期望行为: {behavior}")


def test_sql_planner_fixtures_map_to_valid_plan_and_safe_sql():
    """SQL 规划 fixture 应能生成安全 SQL"""
    cases = _load_cases("sql_planner_cases.yml")

    assert len(cases) >= 3
    for case in cases:
        plan = _sql_plan_from_dict(case["expected_plan"])

        assert plan.validate(AVAILABLE_TABLES, JOIN_WHITELIST) == [], case["id"]
        if plan.strategy == Strategy.UNSUPPORTED_MULTI_PLAN:
            with pytest.raises(ValueError, match="UNSUPPORTED_MULTI_PLAN"):
                sql_plan_to_sql(plan)
            continue

        sql = sql_plan_to_sql(plan)
        assert validate_sql_safety(
            sql,
            forbidden_keywords=["INSERT", "UPDATE", "DELETE", "DROP"],
            available_tables=AVAILABLE_TABLES,
            join_whitelist=JOIN_WHITELIST,
        ) == [], case["id"]


def test_fake_llm_can_replay_intent_fixture_json():
    """FakeLLM 应能回放 fixture JSON 并构造 QuestionIntent"""
    case = next(
        item for item in _load_cases("intent_classifier_cases.yml")
        if item["expected_behavior"] == "answer"
    )
    content = json.dumps(case["expected_intent"], ensure_ascii=False)
    client = FakeLLMClient({"intent_classifier": content})

    response = client.complete(
        LLMRequest(
            task="intent_classifier",
            prompt="fixture replay",
            metadata={"case_id": case["id"]},
        )
    )
    intent = _question_intent_from_dict(json.loads(response.content))

    assert intent.validate() == []
    assert intent.metrics == case["expected_intent"]["metrics"]


def test_fake_llm_can_replay_sql_plan_fixture_json():
    """FakeLLM 应能回放 SQLPlan fixture 并通过规划校验"""
    case = _load_cases("sql_planner_cases.yml")[0]
    content = json.dumps(case["expected_plan"], ensure_ascii=False)
    client = FakeLLMClient({"sql_planner": content})

    response = client.complete(
        LLMRequest(
            task="sql_planner",
            prompt="fixture replay",
            metadata={"case_id": case["id"]},
        )
    )
    plan = _sql_plan_from_dict(json.loads(response.content))

    assert plan.validate(AVAILABLE_TABLES, JOIN_WHITELIST) == []
