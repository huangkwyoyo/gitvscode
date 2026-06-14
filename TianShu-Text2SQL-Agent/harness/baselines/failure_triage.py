"""E2E 失败样例的旁路归因分析。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FAILURE_RULES: list[tuple[str, set[str], dict[str, Any]]] = [
    (
        "应拒绝但回答",
        {"refusal_mismatch", "refusal_expected_but_answered"},
        {
            "root_cause_hint": "拒绝策略没有拦住越权、写操作或不支持的问题。",
            "recommended_action": "修 prompt + 补 regression case",
            "regression_candidate": True,
            "asset_dependency": "none",
        },
    ),
    (
        "应反问但回答",
        {"clarification_mismatch", "clarification_expected_but_answered"},
        {
            "root_cause_hint": "歧义问题被继续规划或回答，反问策略没有生效。",
            "recommended_action": "修 prompt + 补 regression case",
            "regression_candidate": True,
            "asset_dependency": "none",
        },
    ),
    (
        "safety 拦截",
        {"safety_validation_failed", "direct_sql_detected", "sql_not_readonly"},
        {
            "root_cause_hint": "SQL 安全门禁发现直接 SQL、非只读 SQL 或不合规访问。",
            "recommended_action": "修 schema validator 或补 regression case",
            "regression_candidate": True,
            "asset_dependency": "none",
        },
    ),
    (
        "执行失败",
        {"execution_failed", "db_execution_failed", "table_not_found", "field_not_found"},
        {
            "root_cause_hint": "SQL 已进入执行阶段，但数据库、表字段或数据资产不可用。",
            "recommended_action": "等待数仓资产补充或修 fixture",
            "regression_candidate": True,
            "asset_dependency": "possible",
        },
    ),
    (
        "plan 错",
        {"plan_mismatch", "table_mismatch", "field_mismatch", "metric_mismatch"},
        {
            "root_cause_hint": "Intent 之后的 SQLPlan 选择了错误表、字段、指标或策略。",
            "recommended_action": "修 prompt 或修 fixture",
            "regression_candidate": True,
            "asset_dependency": "possible",
        },
    ),
    (
        "intent 错",
        {"intent_mismatch", "intent_parse_failed", "schema_validation_failed"},
        {
            "root_cause_hint": "问题理解或 QuestionIntent 结构化输出不符合预期。",
            "recommended_action": "修 prompt + 补 regression case",
            "regression_candidate": True,
            "asset_dependency": "none",
        },
    ),
    (
        "解释不合格",
        {"answer_content_mismatch", "explanation_mismatch", "answer_missing"},
        {
            "root_cause_hint": "查询链路完成后，中文解释没有满足 fixture 或业务表达要求。",
            "recommended_action": "修 prompt 或修 fixture",
            "regression_candidate": True,
            "asset_dependency": "none",
        },
    ),
]


def build_failure_triage(case: dict[str, Any]) -> dict[str, Any]:
    """把单个 E2E 失败 case 映射到固定处置建议。"""
    categories = set(case.get("failure_categories") or [])
    failure_type, metadata = _match_rule(categories, case)
    return {
        "case_id": case.get("case_id") or case.get("id"),
        "question": case.get("question_zh") or case.get("question") or "",
        "expected_behavior": case.get("expected_behavior") or case.get("expected_type"),
        "failure_categories": sorted(categories),
        "failure_type": failure_type,
        "root_cause_hint": metadata["root_cause_hint"],
        "recommended_action": metadata["recommended_action"],
        "regression_candidate": metadata["regression_candidate"],
        "asset_dependency": metadata["asset_dependency"],
    }


def build_failure_triage_from_e2e_report(report: dict[str, Any]) -> dict[str, Any]:
    """从 E2E JSON 报告构造 failure_triage 段落。"""
    failed_cases = [case for case in report.get("cases", []) if not case.get("passed")]
    items = [build_failure_triage(case) for case in failed_cases]
    return {
        "source": "e2e_eval_report",
        "run_id": report.get("run_id"),
        "total_failed": len(items),
        "items": items,
        "category_counts": _count_by_type(items),
    }


def load_failure_triage_from_report(path: Path | str) -> dict[str, Any]:
    """读取 E2E JSON 报告并生成 triage；缺失时返回 blocked 结构。"""
    report_path = Path(path)
    if not report_path.exists():
        return {
            "source": "e2e_eval_report",
            "report_path": str(report_path),
            "total_failed": 0,
            "items": [],
            "category_counts": {},
            "error": "e2e report not found",
        }
    data = json.loads(report_path.read_text(encoding="utf-8"))
    triage = build_failure_triage_from_e2e_report(data)
    triage["report_path"] = str(report_path)
    return triage


def _match_rule(categories: set[str], case: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """按优先级匹配失败类型。"""
    expected = case.get("expected_behavior") or case.get("expected_type")
    if expected == "refusal" and not categories:
        categories = {"refusal_mismatch"}
    if expected == "clarification" and not categories:
        categories = {"clarification_mismatch"}

    for failure_type, rule_categories, metadata in FAILURE_RULES:
        if categories & rule_categories:
            return failure_type, metadata
    return (
        "未分类失败",
        {
            "root_cause_hint": "报告未提供可识别的失败分类，需要人工查看断言详情。",
            "recommended_action": "补 regression case",
            "regression_candidate": True,
            "asset_dependency": "unknown",
        },
    )


def _count_by_type(items: list[dict[str, Any]]) -> dict[str, int]:
    """按 failure_type 汇总数量。"""
    counts: dict[str, int] = {}
    for item in items:
        failure_type = item["failure_type"]
        counts[failure_type] = counts.get(failure_type, 0) + 1
    return counts
