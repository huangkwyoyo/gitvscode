"""失败样例 → memory suggestion 的映射与报告生成。

Step 11：当 Runtime LLM Baseline 或 E2E eval 出现 failed cases 时，
把失败样例自动映射成 memory suggestion，用于人工审查和后续规则沉淀。

关键边界：
    - 不允许自动写入 memory_rules.yml
    - 不允许把 suggested rule 标成 active
    - 不允许把 blocking 设置为 true
    - 不允许调用真实 LLM
    - 不允许读取 *_latest.* 作为唯一判断依据
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


# ═══════════════════════════════════════════════════════════════
# 失败类型 → 分类规则映射
# ═══════════════════════════════════════════════════════════════

FAILURE_CLASSIFICATION: dict[str, dict[str, Any]] = {
    "intent_mismatch": {
        "root_cause_hint": "问题理解或 QuestionIntent 结构化输出不符合预期。",
        "recommended_action": "修 prompt / 补 regression case",
        "regression_candidate": True,
        "asset_dependency": False,
        "manual_review_required": False,
    },
    "plan_mismatch": {
        "root_cause_hint": "Intent 之后的 SQLPlan 选择了错误的策略或结构。",
        "recommended_action": "修 prompt / 修 schema validator / 补 regression case",
        "regression_candidate": True,
        "asset_dependency": False,
        "manual_review_required": False,
    },
    "table_mismatch": {
        "root_cause_hint": "SQLPlan 引用了不存在的表或未按契约选择表层。",
        "recommended_action": "修 schema validator / 补 regression case",
        "regression_candidate": True,
        "asset_dependency": False,
        "manual_review_required": False,
    },
    "field_mismatch": {
        "root_cause_hint": "SQLPlan 引用的字段在目标表中不存在或语义错误。",
        "recommended_action": "修 schema validator / 等待数仓资产补充",
        "regression_candidate": True,
        "asset_dependency": True,
        "manual_review_required": False,
    },
    "clarification_expected_but_answered": {
        "root_cause_hint": "歧义问题被继续规划或回答，反问策略没有生效。",
        "recommended_action": "修 prompt / 补 regression case",
        "regression_candidate": True,
        "asset_dependency": False,
        "manual_review_required": False,
    },
    "refusal_expected_but_answered": {
        "root_cause_hint": "应拒绝的问题被正常回答，安全边界可能被绕过。",
        "recommended_action": "修 prompt / 补 unsafe regression case",
        "regression_candidate": True,
        "asset_dependency": False,
        "manual_review_required": True,
    },
    "confidence_out_of_range": {
        "root_cause_hint": "LLM 输出 confidence 值与 fixture 容忍范围偏差过大。",
        "recommended_action": "修 prompt 或放宽 fixture tolerance，需人工确认",
        "regression_candidate": True,
        "asset_dependency": False,
        "manual_review_required": True,
    },
    "schema_validation_failed": {
        "root_cause_hint": "LLM 输出的 JSON schema 不符合契约定义。",
        "recommended_action": "修 schema validator 或 prompt 输出 schema",
        "regression_candidate": True,
        "asset_dependency": False,
        "manual_review_required": False,
    },
    "safety_validation_failed": {
        "root_cause_hint": "SQL 安全门禁发现直接 SQL、非只读 SQL 或不合规访问。",
        "recommended_action": "修 safety validator / prompt 边界，必须人工审查",
        "regression_candidate": True,
        "asset_dependency": False,
        "manual_review_required": True,
    },
    "raw_output_parse_failed": {
        "root_cause_hint": "LLM 返回了无法解析的原始输出（非 JSON 或格式错误）。",
        "recommended_action": "修 prompt 输出格式 / parser",
        "regression_candidate": True,
        "asset_dependency": False,
        "manual_review_required": False,
    },
    "execution_failed": {
        "root_cause_hint": "SQL 已进入执行阶段，但数据库、表字段或数据资产不可用。",
        "recommended_action": "等待数仓资产补充或修 SQLPlan 规则",
        "regression_candidate": True,
        "asset_dependency": True,
        "manual_review_required": False,
    },
    "explain_failed": {
        "root_cause_hint": "查询链路完成后，中文解释没有满足 fixture 或业务表达要求。",
        "recommended_action": "修 result_fusion prompt 或 explanation validator",
        "regression_candidate": True,
        "asset_dependency": False,
        "manual_review_required": False,
    },
}

# E2E 失败分类 → 标准 failure_type 的映射
# E2E evaluator 的 _classify_failures 产出的分类名需要归一化
E2E_CATEGORY_MAPPING: dict[str, str] = {
    "intent_failed": "intent_mismatch",
    "intent_mismatch": "intent_mismatch",
    "wrong_metric": "intent_mismatch",
    "plan_failed": "plan_mismatch",
    "plan_mismatch": "plan_mismatch",
    "wrong_table": "table_mismatch",
    "table_mismatch": "table_mismatch",
    "field_mismatch": "field_mismatch",
    "metric_mismatch": "intent_mismatch",
    "clarification_mismatch": "clarification_expected_but_answered",
    "clarification_expected_but_answered": "clarification_expected_but_answered",
    "refusal_mismatch": "refusal_expected_but_answered",
    "refusal_expected_but_answered": "refusal_expected_but_answered",
    "safety_failed": "safety_validation_failed",
    "safety_validation_failed": "safety_validation_failed",
    "direct_sql_detected": "safety_validation_failed",
    "sql_not_readonly": "safety_validation_failed",
    "execution_failed": "execution_failed",
    "db_execution_failed": "execution_failed",
    "table_not_found": "execution_failed",
    "field_not_found": "field_mismatch",
    "explain_failed": "explain_failed",
    "explanation_mismatch": "explain_failed",
    "answer_content_mismatch": "explain_failed",
    "answer_content_violation": "explain_failed",
    "answer_missing": "explain_failed",
    "raw_output_parse_failed": "raw_output_parse_failed",
    "intent_parse_failed": "raw_output_parse_failed",
    "confidence_out_of_range": "confidence_out_of_range",
    "schema_validation_failed": "schema_validation_failed",
    "downgrade_not_triggered": "plan_mismatch",
    "downgrade_reason_missing": "plan_mismatch",
    "downgrade_wrong_strategy": "plan_mismatch",
    "downgrade_reason_mismatch": "plan_mismatch",
    "downgrade_sql_missing": "execution_failed",
    "safety_violation_not_detected": "safety_validation_failed",
}


# ═══════════════════════════════════════════════════════════════
# 核心纯函数：failure case → suggestion
# ═══════════════════════════════════════════════════════════════


def normalize_failure_type(raw_type: str) -> str:
    """将 E2E 或其他来源的原始失败分类归一化为标准 failure_type。

    Args:
        raw_type: 原始失败分类字符串

    Returns:
        标准 failure_type，未匹配时返回原始值
    """
    return E2E_CATEGORY_MAPPING.get(raw_type, raw_type)


def classify_failure(failure_type: str) -> dict[str, Any]:
    """根据标准 failure_type 查找分类规则。

    Args:
        failure_type: 标准 failure_type 字符串

    Returns:
        分类规则字典；未匹配时返回默认兜底规则
    """
    if failure_type in FAILURE_CLASSIFICATION:
        return dict(FAILURE_CLASSIFICATION[failure_type])
    return {
        "root_cause_hint": "未预见的失败模式，需要人工分析。",
        "recommended_action": "补 regression case / 人工分析",
        "regression_candidate": True,
        "asset_dependency": False,
        "manual_review_required": True,
    }


def build_suggested_memory_rule(
    title: str,
    failure_type: str,
    root_cause_hint: str,
    source_failure_case: str,
    severity: str = "medium",
    risk_ids: list[str] | None = None,
    applies_to: list[str] | None = None,
    required_checks: list[str] | None = None,
    required_tests: list[str] | None = None,
    required_evals: list[str] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    """构造 suggested_memory_rule 字典。

    所有自动生成的规则始终 status=proposed、blocking=false。

    Args:
        title: 规则标题
        failure_type: 失败类型
        root_cause_hint: 根因提示
        source_failure_case: 来源失败 case 标识
        severity: 严重程度，默认 medium
        risk_ids: 关联风险 ID 列表
        applies_to: 适用范围列表
        required_checks: 需要的检查列表
        required_tests: 需要的测试列表
        required_evals: 需要的评测列表
        notes: 备注

    Returns:
        suggested_memory_rule 字典
    """
    return {
        "proposed_rule_id": "",  # 可为空，人工审查后分配
        "title": title,
        "status": "proposed",
        "blocking": False,
        "severity": severity,
        "risk_ids": risk_ids or [],
        "applies_to": applies_to or [],
        "required_checks": required_checks or [],
        "required_tests": required_tests or [],
        "required_evals": required_evals or [],
        "notes": notes,
        "source_failure_case": source_failure_case,
    }


def build_memory_suggestion(case: dict[str, Any]) -> dict[str, Any]:
    """纯函数：单个失败 case → memory suggestion。

    不读取文件、不调用 LLM、不修改规则注册表。

    Args:
        case: 失败 case 字典，可包含以下字段：
            - question_id / question / failure_type（必需）
            - expected_type / actual_type / failure_reason
            - expected / actual / raw_output_file
            - provider / model_name / stage
            - safety_check / confidence_check

    Returns:
        memory suggestion 字典，包含 failure_type / root_cause_hint /
        recommended_action / regression_candidate / asset_dependency /
        suggested_memory_rule
    """
    question_id = case.get("question_id") or case.get("case_id") or case.get("id", "unknown")
    question = case.get("question") or case.get("question_zh") or ""
    raw_failure_type = case.get("failure_type") or case.get("failure_reason") or "unknown"

    # 归一化 failure_type
    failure_type = normalize_failure_type(raw_failure_type)

    # 查找分类规则
    classification = classify_failure(failure_type)

    # 构造 suggested_memory_rule
    title = _build_rule_title(failure_type, question_id, question)
    notes = _build_rule_notes(failure_type, question, case)
    source = f"{question_id}: {question[:80]}" if question else question_id

    suggested_rule = build_suggested_memory_rule(
        title=title,
        failure_type=failure_type,
        root_cause_hint=classification["root_cause_hint"],
        source_failure_case=source,
        severity=_severity_for(failure_type),
        notes=notes,
    )

    return {
        "question_id": question_id,
        "question": question,
        "failure_type": failure_type,
        "raw_failure_type": raw_failure_type if raw_failure_type != failure_type else None,
        "root_cause_hint": classification["root_cause_hint"],
        "recommended_action": classification["recommended_action"],
        "regression_candidate": classification["regression_candidate"],
        "asset_dependency": classification["asset_dependency"],
        "manual_review_required": classification["manual_review_required"],
        "suggested_memory_rule": suggested_rule,
    }


# ═══════════════════════════════════════════════════════════════
# 报告构建
# ═══════════════════════════════════════════════════════════════


def build_memory_suggestions_report(
    failed_cases: list[dict[str, Any]],
    source: str = "runtime_baseline",
    source_run_id: str = "",
) -> dict[str, Any]:
    """从失败 case 列表生成 memory suggestions 报告。

    Args:
        failed_cases: 失败 case 列表
        source: 数据来源标识（runtime_baseline / llm_e2e_eval / prompt_regression）
        source_run_id: 来源运行的 run_id

    Returns:
        完整报告字典
    """
    suggestions = [build_memory_suggestion(case) for case in failed_cases]

    regression_candidates = [s for s in suggestions if s["regression_candidate"]]
    asset_dependencies = [s for s in suggestions if s["asset_dependency"]]
    manual_review_items = [s for s in suggestions if s["manual_review_required"]]

    return {
        "run_id": _build_run_id(),
        "timestamp": datetime.now(UTC).isoformat(),
        "source": source,
        "source_run_id": source_run_id,
        "summary": {
            "total_failed_cases": len(failed_cases),
            "suggestions": len(suggestions),
            "regression_candidates": len(regression_candidates),
            "asset_dependencies": len(asset_dependencies),
            "manual_review_required": len(manual_review_items),
        },
        "suggestions": suggestions,
        "regression_candidates": [
            {
                "question_id": s["question_id"],
                "failure_type": s["failure_type"],
                "recommended_action": s["recommended_action"],
            }
            for s in regression_candidates
        ],
        "asset_dependencies": [
            {
                "question_id": s["question_id"],
                "failure_type": s["failure_type"],
                "root_cause_hint": s["root_cause_hint"],
            }
            for s in asset_dependencies
        ],
        "suggested_memory_rules": [s["suggested_memory_rule"] for s in suggestions],
        "manual_review_required": [
            {
                "question_id": s["question_id"],
                "failure_type": s["failure_type"],
                "root_cause_hint": s["root_cause_hint"],
                "recommended_action": s["recommended_action"],
            }
            for s in manual_review_items
        ],
    }


def build_memory_suggestions_from_e2e_report(
    report: dict[str, Any],
    source: str = "llm_e2e_eval",
) -> dict[str, Any]:
    """从 E2E JSON 报告构造 memory suggestions。

    Args:
        report: E2E 评测报告字典（包含 cases 列表）
        source: 来源标识

    Returns:
        memory suggestions 报告字典
    """
    failed_cases = []
    for case in report.get("cases", []):
        if case.get("passed", True):
            continue
        # 将 E2E case 转换为通用失败 case 格式
        failure_categories = case.get("failure_categories", [])
        primary_failure = failure_categories[0] if failure_categories else "unknown"
        failed_cases.append({
            "question_id": case.get("case_id") or case.get("id", "unknown"),
            "question": case.get("question_zh") or case.get("question", ""),
            "expected_type": case.get("expected_behavior", ""),
            "failure_type": primary_failure,
            "failure_categories": failure_categories,
            "failure_reason": ", ".join(failure_categories),
            "error": case.get("error"),
            "suggestion": case.get("suggestion", ""),
        })

    return build_memory_suggestions_report(
        failed_cases,
        source=source,
        source_run_id=report.get("run_id", ""),
    )


def build_memory_suggestions_from_prompt_regression(
    report: dict[str, Any],
    source: str = "prompt_regression",
) -> dict[str, Any]:
    """从 Prompt Regression JSON 报告构造 memory suggestions。

    Args:
        report: Prompt regression 报告字典（包含 cases 列表）
        source: 来源标识

    Returns:
        memory suggestions 报告字典
    """
    failed_cases = []
    for case in report.get("cases", []):
        if case.get("passed", True):
            continue
        # 从 prompt regression case 推断 failure_type
        error = case.get("error", "")
        failure_type = _infer_prompt_regression_failure_type(case, error)
        failed_cases.append({
            "question_id": case.get("case_id") or case.get("id", "unknown"),
            "question": case.get("task", ""),
            "failure_type": failure_type,
            "failure_reason": error,
            "error": error,
            "expected": case.get("expected"),
            "actual": case.get("actual"),
        })

    return build_memory_suggestions_report(
        failed_cases,
        source=source,
        source_run_id=report.get("run_id", ""),
    )


def _infer_prompt_regression_failure_type(case: dict[str, Any], error: str) -> str:
    """从 prompt regression case 的错误信息推断 failure_type。"""
    error_lower = error.lower()
    if "parse" in error_lower or "json" in error_lower or "decode" in error_lower:
        return "raw_output_parse_failed"
    if "schema" in error_lower or "validation" in error_lower:
        return "schema_validation_failed"
    if "safety" in error_lower or "sql" in error_lower or "forbidden" in error_lower:
        return "safety_validation_failed"
    if "confidence" in error_lower:
        return "confidence_out_of_range"
    task = case.get("task", "").lower()
    if "intent" in task:
        return "intent_mismatch"
    if "plan" in task:
        return "plan_mismatch"
    return "intent_mismatch"


# ═══════════════════════════════════════════════════════════════
# JSON / Markdown 渲染
# ═══════════════════════════════════════════════════════════════


def render_memory_suggestions_json(report: dict[str, Any]) -> dict[str, Any]:
    """构造可 JSON 序列化的 memory suggestions 报告结构。

    Args:
        report: build_memory_suggestions_report() 的输出

    Returns:
        纯 dict（仅含 JSON 可序列化类型）
    """
    payload = copy.deepcopy(report)
    payload.setdefault("run_id", _build_run_id())
    payload.setdefault("timestamp", datetime.now(UTC).isoformat())
    payload.setdefault("source", "unknown")
    payload.setdefault("source_run_id", "")
    payload.setdefault("summary", {})
    payload.setdefault("suggestions", [])
    payload.setdefault("regression_candidates", [])
    payload.setdefault("asset_dependencies", [])
    payload.setdefault("suggested_memory_rules", [])
    payload.setdefault("manual_review_required", [])

    # 通过 JSON round-trip 保证返回值只包含机器可序列化类型
    return json.loads(json.dumps(payload, ensure_ascii=False))


def render_memory_suggestions_markdown(report: dict[str, Any]) -> str:
    """渲染人工审查用 Markdown 报告文本。

    Args:
        report: build_memory_suggestions_report() 的输出

    Returns:
        Markdown 格式的报告字符串
    """
    payload = render_memory_suggestions_json(report)
    summary = payload["summary"]
    lines = [
        "# Failure Triage Memory Suggestions",
        "",
        "## Summary",
        "",
        f"- run_id: `{payload['run_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- source: `{payload['source']}`",
        f"- source_run_id: `{payload['source_run_id']}`",
        f"- total_failed_cases: {summary['total_failed_cases']}",
        f"- suggestions: {summary['suggestions']}",
        f"- regression_candidates: {summary['regression_candidates']}",
        f"- asset_dependencies: {summary['asset_dependencies']}",
        f"- manual_review_required: {summary.get('manual_review_required', 0)}",
        "",
    ]

    # 逐条建议详情
    lines.extend(["## Suggestions", ""])
    suggestions = payload["suggestions"]
    if not suggestions:
        lines.extend(["无失败样例需要生成建议。", ""])
    else:
        for item in suggestions:
            lines.extend([
                f"### {item['question_id']}",
                "",
                f"- failure_type: `{item['failure_type']}`",
            ])
            if item.get("raw_failure_type"):
                lines.append(f"- raw_failure_type: `{item['raw_failure_type']}`")
            lines.extend([
                f"- root_cause_hint: {item['root_cause_hint']}",
                f"- recommended_action: {item['recommended_action']}",
                f"- regression_candidate: `{item['regression_candidate']}`",
                f"- asset_dependency: `{item['asset_dependency']}`",
                f"- manual_review_required: `{item['manual_review_required']}`",
                "",
                "**Suggested Memory Rule:**",
                "",
            ])
            rule = item["suggested_memory_rule"]
            lines.extend([
                f"- proposed_rule_id: `{rule.get('proposed_rule_id') or '(待分配)'}`",
                f"- title: {rule['title']}",
                f"- status: `{rule['status']}`",
                f"- blocking: `{rule['blocking']}`",
                f"- severity: `{rule.get('severity', 'medium')}`",
                f"- risk_ids: `{rule.get('risk_ids', [])}`",
                f"- applies_to: `{rule.get('applies_to', [])}`",
                f"- notes: {rule.get('notes', '')}",
                f"- source_failure_case: {rule.get('source_failure_case', '')}",
                "",
            ])

    # Regression Candidates
    lines.extend(["## Regression Candidates", ""])
    rc = payload["regression_candidates"]
    if rc:
        lines.append("| question_id | failure_type | recommended_action |")
        lines.append("| --- | --- | --- |")
        for item in rc:
            lines.append(
                f"| {_escape_md(item['question_id'])} "
                f"| {_escape_md(item['failure_type'])} "
                f"| {_escape_md(item['recommended_action'])} |"
            )
        lines.append("")
    else:
        lines.extend(["无。", ""])

    # Asset Dependencies
    lines.extend(["## Asset Dependencies", ""])
    ad = payload["asset_dependencies"]
    if ad:
        lines.append("| question_id | failure_type | root_cause_hint |")
        lines.append("| --- | --- | --- |")
        for item in ad:
            lines.append(
                f"| {_escape_md(item['question_id'])} "
                f"| {_escape_md(item['failure_type'])} "
                f"| {_escape_md(item['root_cause_hint'])} |"
            )
        lines.append("")
    else:
        lines.extend(["无。", ""])

    # Suggested Memory Rules
    lines.extend(["## Suggested Memory Rules", ""])
    smr = payload["suggested_memory_rules"]
    if smr:
        lines.append("| title | severity | status | blocking | source |")
        lines.append("| --- | --- | --- | --- | --- |")
        for rule in smr:
            lines.append(
                f"| {_escape_md(rule.get('title', ''))} "
                f"| {rule.get('severity', 'medium')} "
                f"| {rule.get('status', 'proposed')} "
                f"| {rule.get('blocking', False)} "
                f"| {_escape_md(rule.get('source_failure_case', ''))} |"
            )
        lines.append("")
    else:
        lines.extend(["无。", ""])

    # Manual Review Required
    lines.extend(["## Manual Review Required", ""])
    mr = payload["manual_review_required"]
    if mr:
        lines.extend([
            "以下建议涉及安全边界或需要人工判断，**禁止自动应用**：",
            "",
            "| question_id | failure_type | root_cause_hint | recommended_action |",
            "| --- | --- | --- | --- |",
        ])
        for item in mr:
            lines.append(
                f"| {_escape_md(item['question_id'])} "
                f"| {_escape_md(item['failure_type'])} "
                f"| {_escape_md(item['root_cause_hint'])} "
                f"| {_escape_md(item['recommended_action'])} |"
            )
        lines.append("")
    else:
        lines.extend(["无。", ""])

    # 底部声明
    lines.extend([
        "---",
        "",
        "> ⚠️ **重要声明**",
        "> - 本报告由 `harness/memory_suggestions.py` 自动生成。",
        "> - 所有 suggested_memory_rule 均为 `status: proposed`、`blocking: false`。",
        "> - 不会自动修改 `docs/memory/memory_rules.yml`。",
        "> - 不会自动晋升为 active 规则。",
        "> - 不会自动接入 fast gate 阻断。",
        "> - 人工审查通过后再手动更新规则注册表。",
        "",
    ])

    return "\n".join(lines)


def write_memory_suggestions_snapshot(
    report: dict[str, Any],
    output_dir: Path | str,
) -> dict[str, Path]:
    """写入带 timestamp 的 snapshot 报告，不生成 latest 文件。

    Args:
        report: build_memory_suggestions_report() 的输出
        output_dir: 输出目录路径

    Returns:
        {"json": Path, "markdown": Path}
    """
    payload = render_memory_suggestions_json(report)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    timestamp = _safe_timestamp(payload["timestamp"])
    json_path = output / f"memory_suggestions_{timestamp}.json"
    markdown_path = output / f"memory_suggestions_{timestamp}.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_memory_suggestions_markdown(report),
        encoding="utf-8",
    )
    return {"json": json_path, "markdown": markdown_path}


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _build_rule_title(failure_type: str, question_id: str, question: str) -> str:
    """从失败信息构造建议规则标题。"""
    type_labels = {
        "intent_mismatch": f"Intent 分类在 {question_id} 场景下解析错误",
        "plan_mismatch": f"SQLPlan 在 {question_id} 场景下选择了错误策略",
        "table_mismatch": f"表选择在 {question_id} 场景下不匹配",
        "field_mismatch": f"字段映射在 {question_id} 场景下错误",
        "clarification_expected_but_answered": f"歧义检测在 {question_id} 场景下未触发反问",
        "refusal_expected_but_answered": f"拒绝策略在 {question_id} 场景下失效",
        "confidence_out_of_range": f"置信度在 {question_id} 场景下超出范围",
        "schema_validation_failed": f"Schema 校验在 {question_id} 场景下失败",
        "safety_validation_failed": f"SQL 安全门禁在 {question_id} 场景被绕过",
        "raw_output_parse_failed": f"LLM 输出在 {question_id} 场景下无法解析",
        "execution_failed": f"SQL 执行在 {question_id} 场景下失败",
        "explain_failed": f"中文解释在 {question_id} 场景下不满足预期",
    }
    return type_labels.get(failure_type, f"新失败模式: {question_id}")


def _build_rule_notes(failure_type: str, question: str, case: dict[str, Any]) -> str:
    """构造 suggested_memory_rule 的 notes 字段。"""
    snippet = question[:120] if question else ""
    source_info = (
        f"来源: {case.get('provider', 'unknown')} / "
        f"{case.get('model_name', 'unknown')} / "
        f"stage={case.get('stage', 'unknown')}"
    )
    return f"自动生成建议。原始问题: {snippet}。{source_info}。需人工审查确认后决定是否纳入规则注册表。"


def _severity_for(failure_type: str) -> str:
    """根据失败类型判定严重程度。"""
    high_severity = {
        "safety_validation_failed",
        "refusal_expected_but_answered",
        "clarification_expected_but_answered",
    }
    if failure_type in high_severity:
        return "high"
    return "medium"


def _build_run_id() -> str:
    """构造唯一的 run_id。"""
    return "memory-suggestions-" + _safe_timestamp(datetime.now(UTC).isoformat())


def _safe_timestamp(value: str) -> str:
    """将 ISO 时间转成文件名友好格式。"""
    return (
        value.replace(":", "")
        .replace("-", "")
        .replace(".", "")
        .replace("+", "")
    )


def _escape_md(value: str) -> str:
    """转义 Markdown 表格中的特殊字符。"""
    return value.replace("|", "\\|").replace("\n", " ")
