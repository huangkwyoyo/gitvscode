"""Memory Rule 晋升候选报告逻辑。"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "docs" / "memory" / "memory_rules.yml"


def load_rules_from_registry(registry_path: Path | str = DEFAULT_REGISTRY_PATH) -> list[dict[str, Any]]:
    """读取 memory_rules.yml 中的规则列表。"""
    path = Path(registry_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules = data.get("rules", [])
    if not isinstance(rules, list):
        raise ValueError("memory_rules.yml 的 rules 必须是列表")
    return rules


def analyze_promotion_candidates(
    rules: list[dict[str, Any]],
    project_root: Path | str = PROJECT_ROOT,
    source_registry: str = "docs/memory/memory_rules.yml",
) -> dict[str, Any]:
    """分析 proposed 规则是否具备进入人工晋升审查的条件。"""
    root = Path(project_root)
    analyzed_rules = [_analyze_rule(rule, root) for rule in rules]

    return {
        "run_id": _build_run_id(),
        "timestamp": datetime.now(UTC).isoformat(),
        "source_registry": source_registry,
        "summary": _build_summary(rules, analyzed_rules),
        "rules": analyzed_rules,
        "ready_for_human_review": [
            item for item in analyzed_rules
            if item["candidate_status"] == "ready_for_human_review"
        ],
        "missing_coverage": [
            item for item in analyzed_rules
            if item["candidate_status"] == "missing_coverage"
        ],
        "invalid_references": [
            item for item in analyzed_rules
            if item["candidate_status"] == "invalid_references"
        ],
        "not_recommended": [
            item for item in analyzed_rules
            if item["candidate_status"] == "not_recommended"
        ],
        "manual_review_required": [
            item for item in analyzed_rules
            if item.get("manual_review_required")
        ],
    }


def build_memory_promotion_json(result: dict[str, Any]) -> dict[str, Any]:
    """构造可 JSON 序列化的晋升候选报告结构。"""
    payload = copy.deepcopy(result)
    payload.setdefault("run_id", _build_run_id())
    payload.setdefault("timestamp", datetime.now(UTC).isoformat())
    payload.setdefault("source_registry", "docs/memory/memory_rules.yml")
    payload.setdefault("summary", {})
    payload.setdefault("rules", [])
    payload.setdefault("ready_for_human_review", [])
    payload.setdefault("missing_coverage", [])
    payload.setdefault("invalid_references", [])
    payload.setdefault("not_recommended", [])
    payload.setdefault("manual_review_required", [])

    # 通过 JSON round-trip 保证返回值只包含机器可序列化类型。
    return json.loads(json.dumps(payload, ensure_ascii=False))


def render_memory_promotion_markdown(result: dict[str, Any]) -> str:
    """渲染人工审查用 Markdown 报告文本。"""
    report = build_memory_promotion_json(result)
    summary = report["summary"]
    lines = [
        "# Memory Rule Promotion Candidate Report",
        "",
        "## Summary",
        "",
        f"- run_id: `{report['run_id']}`",
        f"- timestamp: `{report['timestamp']}`",
        f"- source_registry: `{report['source_registry']}`",
        f"- total rules: {summary['total_rules']}",
        f"- proposed rules: {summary['proposed_rules']}",
        f"- active rules: {summary['active_rules']}",
        f"- ready for human review: {summary['ready_for_human_review']}",
        f"- missing coverage: {summary['missing_coverage']}",
        f"- invalid references: {summary['invalid_references']}",
        f"- not recommended: {summary['not_recommended']}",
        "",
    ]

    _append_rule_section(lines, "Ready For Human Review", report["ready_for_human_review"])
    _append_rule_section(lines, "Missing Coverage", report["missing_coverage"])
    _append_rule_section(lines, "Invalid References", report["invalid_references"])
    _append_rule_section(lines, "Not Recommended", report["not_recommended"])
    _append_rule_section(lines, "Blocking Semantics Review", report["manual_review_required"])

    lines.extend([
        "## Suggested Next Actions",
        "",
        "- 补齐缺失的 required_checks / required_tests / required_evals。",
        "- 对覆盖完整的 proposed 规则做人工 blocking 语义审查。",
        "- 人工确认后再单独修改 `memory_rules.yml`，本报告不自动晋升规则。",
        "",
    ])
    return "\n".join(lines)


def write_memory_promotion_snapshot(
    result: dict[str, Any],
    output_dir: Path | str,
) -> dict[str, Path]:
    """写入带 timestamp 的 snapshot 报告，不生成 latest 文件。"""
    report = build_memory_promotion_json(result)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    timestamp = _safe_timestamp(report["timestamp"])
    json_path = output / f"memory_promotion_{timestamp}.json"
    markdown_path = output / f"memory_promotion_{timestamp}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_memory_promotion_markdown(report),
        encoding="utf-8",
    )
    return {"json": json_path, "markdown": markdown_path}


def _analyze_rule(rule: dict[str, Any], project_root: Path) -> dict[str, Any]:
    missing = _find_missing_coverage(rule)
    invalid_paths = _find_invalid_paths(rule, project_root)
    status = rule.get("status")
    blocking = rule.get("blocking")

    item = {
        "rule_id": rule.get("rule_id", "?"),
        "title": rule.get("title", ""),
        "status": status,
        "blocking": blocking,
        "severity": rule.get("severity", ""),
        "risk_ids": rule.get("risk_ids", []),
        "missing_checks": missing["required_checks"],
        "missing_tests": missing["required_tests"],
        "missing_evals": missing["required_evals"],
        "invalid_paths": invalid_paths,
        "coverage_score": _build_coverage_score(rule, missing, invalid_paths),
        "manual_review_required": False,
        "blocking_semantics_review_required": False,
        "recommendation": "",
        "reason": "",
        "source_notes": rule.get("notes", ""),
    }

    if status != "proposed":
        item.update({
            "candidate_status": "not_applicable",
            "recommendation": "非 proposed 规则不参与晋升候选报告",
            "reason": f"当前状态为 {status}",
        })
        return item

    if blocking is True:
        item.update({
            "candidate_status": "not_recommended",
            "recommendation": "先恢复为 proposed + blocking=false，再做人工审查",
            "reason": "proposed 规则不能直接 blocking=true",
        })
        return item

    notes = str(rule.get("notes", ""))
    if _notes_indicate_not_ready(notes):
        item.update({
            "candidate_status": "not_recommended",
            "recommendation": "先完成 notes 中标注的待办或人工确认",
            "reason": "notes 显示规则仍处于待补或待审状态",
        })
        return item

    if any(missing.values()):
        item.update({
            "candidate_status": "missing_coverage",
            "recommendation": "补齐 required_checks / required_tests / required_evals",
            "reason": "存在覆盖字段为空",
        })
        return item

    if invalid_paths:
        item.update({
            "candidate_status": "invalid_references",
            "recommendation": "修正不存在的 required_* 路径",
            "reason": "存在无法解析到项目内文件的路径",
        })
        return item

    item.update({
        "candidate_status": "ready_for_human_review",
        "manual_review_required": True,
        "blocking_semantics_review_required": True,
        "recommendation": "覆盖完整，可进入人工审查，确认后才可考虑晋升 active",
        "reason": "required_checks / required_tests / required_evals 均非空且路径存在",
    })
    return item


def _find_missing_coverage(rule: dict[str, Any]) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {
        "required_checks": [],
        "required_tests": [],
        "required_evals": [],
    }
    for field_name in missing:
        if not rule.get(field_name):
            missing[field_name].append(f"{field_name} 为空")
    return missing


def _find_invalid_paths(rule: dict[str, Any], project_root: Path) -> list[str]:
    invalid: list[str] = []
    for field_name in ["required_checks", "required_tests", "required_evals"]:
        for relative_path in rule.get(field_name, []) or []:
            if not (project_root / relative_path).exists():
                invalid.append(relative_path)
    return sorted(invalid)


def _build_coverage_score(
    rule: dict[str, Any],
    missing: dict[str, list[str]],
    invalid_paths: list[str],
) -> dict[str, str]:
    scores: dict[str, str] = {}
    field_map = {
        "checks": "required_checks",
        "tests": "required_tests",
        "evals": "required_evals",
    }
    for label, field_name in field_map.items():
        if missing[field_name]:
            scores[label] = "missing"
        elif _field_has_invalid_path(rule, field_name, invalid_paths):
            scores[label] = "invalid"
        else:
            scores[label] = "complete"
    return scores


def _field_has_invalid_path(
    rule: dict[str, Any],
    field_name: str,
    invalid_paths: list[str],
) -> bool:
    values = set(rule.get(field_name, []) or [])
    return bool(values & set(invalid_paths))


def _build_summary(
    rules: list[dict[str, Any]],
    analyzed_rules: list[dict[str, Any]],
) -> dict[str, int]:
    return {
        "total_rules": len(rules),
        "proposed_rules": sum(1 for rule in rules if rule.get("status") == "proposed"),
        "active_rules": sum(1 for rule in rules if rule.get("status") == "active"),
        "ready_for_human_review": _count_status(analyzed_rules, "ready_for_human_review"),
        "missing_coverage": _count_status(analyzed_rules, "missing_coverage"),
        "invalid_references": _count_status(analyzed_rules, "invalid_references"),
        "not_recommended": _count_status(analyzed_rules, "not_recommended"),
    }


def _count_status(items: list[dict[str, Any]], status: str) -> int:
    return sum(1 for item in items if item.get("candidate_status") == status)


def _append_rule_section(
    lines: list[str],
    title: str,
    items: list[dict[str, Any]],
) -> None:
    lines.extend([f"## {title}", ""])
    if not items:
        lines.extend(["无。", ""])
        return

    lines.append("| rule_id | title | recommendation | reason |")
    lines.append("| --- | --- | --- | --- |")
    for item in items:
        lines.append(
            "| {rule_id} | {title} | {recommendation} | {reason} |".format(
                rule_id=item["rule_id"],
                title=_escape_md(str(item.get("title", ""))),
                recommendation=_escape_md(str(item.get("recommendation", ""))),
                reason=_escape_md(str(item.get("reason", ""))),
            )
        )
    lines.append("")


def _notes_indicate_not_ready(notes: str) -> bool:
    markers = ["TODO", "待补", "待审", "待确认", "未完成"]
    return any(marker in notes for marker in markers)


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _build_run_id() -> str:
    return "memory-promotion-" + _safe_timestamp(datetime.now(UTC).isoformat())


def _safe_timestamp(value: str) -> str:
    return (
        value.replace(":", "")
        .replace("-", "")
        .replace(".", "")
        .replace("+", "")
    )
