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


# ── 记忆回写模板 ──────────────────────────────────────────────

# 每个失败类型对应的记忆条目建议模板
MEMORY_SUGGESTION_TEMPLATES: dict[str, dict[str, str]] = {
    "应拒绝但回答": {
        "title": "拒绝策略在 {case_id} 场景下失效",
        "rule": "拒绝策略必须覆盖 {question} 类问题的中英文危险表达。在 check_refusal_policy.py 中追加对应关键词，并在 evals/unsafe_questions.yml 中新增变体。",
    },
    "应反问但回答": {
        "title": "歧义检测在 {case_id} 场景下未触发反问",
        "rule": "当用户问题包含 {question} 时，应触发反问而非直接回答。检查 ambiguity.py 的歧义检测规则和 agent_config.yml 的 ambiguity_threshold。",
    },
    "safety 拦截": {
        "title": "SQL 安全门禁在 {case_id} 场景被绕过",
        "rule": "LLM 在 {question} 场景下直接输出了 SQL 或绕过了安全检查。检查 schema_validators.py 的 JSON Schema 校验是否拦截了嵌入 SQL 文本的字段，并在 Prompt 模板中增加反例说明。",
    },
    "执行失败": {
        "title": "SQL 执行在 {case_id} 场景下失败",
        "rule": "{question} 类查询的 SQL 在 DuckDB 中执行失败。检查 sql_plan_to_sql() 生成的 SQL 是否使用了 DuckDB 不支持的方言语法，或检查 TianShu 数据仓库的相关表是否可用。",
    },
    "plan 错": {
        "title": "SQLPlan 在 {case_id} 场景下选择了错误表/字段/策略",
        "rule": "{question} 类查询的 SQLPlan 选择了不正确的表或字段。检查 prompts/sql_planner.md 的表选择指导规则和 resolve_layer() 的降级逻辑。",
    },
    "intent 错": {
        "title": "Intent 分类器在 {case_id} 场景下解析错误",
        "rule": "{question} 类问题的意图解析不符合预期。检查 prompts/intent_classifier.md 的指标展示方式——同域相近指标应分组展示并触发反问。",
    },
    "解释不合格": {
        "title": "中文解释在 {case_id} 场景下不满足预期",
        "rule": "{question} 类查询的中文解释不满足 fixture 或业务表达要求。检查 explainer.py 的模板逻辑或 prompts/explainer.md 的解释规则。",
    },
    "未分类失败": {
        "title": "新失败模式: {case_id}",
        "rule": "{question} 产生了一个未预见的失败模式，需人工分析。建议在 failure_triage.py 的 FAILURE_RULES 中新增对应分类规则。",
    },
}


def suggest_memory_entry(case: dict[str, Any]) -> dict[str, Any] | None:
    """对 E2E 失败 case 生成记忆条目建议。

    如果该失败类型已有对应的记忆条目模板，则填充生成建议条目；
    返回 None 表示不需要新条目（如已有经验覆盖）。

    Args:
        case: 单个失败 case 的字典，需包含 case_id、question、failure_type 等字段

    Returns:
        记忆条目建议字典，或 None
    """
    failure_type = case.get("failure_type", "未分类失败")
    template = MEMORY_SUGGESTION_TEMPLATES.get(failure_type)
    if not template:
        return None

    case_id = case.get("case_id") or case.get("id") or "unknown"
    question = case.get("question_zh") or case.get("question") or ""

    # 构造建议标题和规则（用 case 字段填充模板）
    title = template["title"].format(
        case_id=case_id,
        question=question[:80],
    )
    rule = template["rule"].format(
        case_id=case_id,
        question=question[:80],
    )

    # 构造完整的记忆条目建议
    return {
        "suggested_title": title,
        "suggested_rule": rule,
        "failure_type": failure_type,
        "root_cause_hint": case.get("root_cause_hint", ""),
        "recommended_action": case.get("recommended_action", ""),
        "source": "harness/failure_triage auto-suggestion",
        "initial_confidence": "L2",  # 自动生成的初始置信等级为 L2（Hypothesis）
        "case_id": case_id,
        "question": question,
    }


def build_memory_suggestions(triage: dict[str, Any]) -> list[dict[str, Any]]:
    """从 failure_triage 结果生成记忆条目建议列表。

    Args:
        triage: build_failure_triage_from_e2e_report() 的输出

    Returns:
        记忆条目建议列表（已去重——相同 failure_type 只保留第一个）
    """
    seen_types: set[str] = set()
    suggestions: list[dict[str, Any]] = []

    for item in triage.get("items", []):
        suggestion = suggest_memory_entry(item)
        if suggestion is None:
            continue
        failure_type = suggestion["failure_type"]
        if failure_type in seen_types:
            continue  # 同类型失败只建议一次
        seen_types.add(failure_type)
        suggestions.append(suggestion)

    return suggestions


def check_existing_memory_coverage(
    suggestions: list[dict[str, Any]],
    memory_path: str = "docs/memory/经验复盘.md",
) -> dict[str, Any]:
    """检查建议的条目是否已被已有经验覆盖。

    Args:
        suggestions: build_memory_suggestions() 的输出
        memory_path: 经验复盘文件的路径（相对于项目根目录）

    Returns:
        {
            "covered": [...],   # 已有经验覆盖的建议（不需要写入）
            "uncovered": [...], # 无已有经验覆盖的建议（需要写入）
        }
    """
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    memory_file = project_root / memory_path

    if not memory_file.exists():
        return {"covered": [], "uncovered": suggestions}

    memory_content = memory_file.read_text(encoding="utf-8")

    covered = []
    uncovered = []
    for suggestion in suggestions:
        failure_type = suggestion["failure_type"]
        # 简单检查：经验复盘文件中是否提到了该失败类型
        if failure_type in memory_content:
            covered.append(suggestion)
        else:
            uncovered.append(suggestion)

    return {"covered": covered, "uncovered": uncovered}
