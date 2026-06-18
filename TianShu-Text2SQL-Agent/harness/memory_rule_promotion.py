"""Memory Rule Promotion 审批工作流（Step 16）。

读取 memory_rules.yml + Step 15 validation report + 可选的 fast_gate_history
和 approval_decisions，为每条规则生成 promotion proposal candidate。

关键边界：
    - 只生成 proposal report，不自动修改 memory_rules.yml
    - 不自动晋升规则（不修改 status / blocking）
    - 不接入 pre-commit / fast gate 阻断
    - 不调用真实 LLM
    - 不读取 *_latest.* 文件
"""

from __future__ import annotations

import copy
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES_PATH = PROJECT_ROOT / "docs" / "memory" / "memory_rules.yml"

# ---------------------------------------------------------------------------
# 晋升类型元数据
# ---------------------------------------------------------------------------

PROMOTION_TYPE_META: dict[str, dict[str, str]] = {
    "proposed_to_active": {
        "label": "proposed → active",
        "description": "proposed 规则满足全部晋升条件，建议晋升为 active（blocking=false）",
        "target_status": "active",
        "target_blocking": "false",
    },
    "active_to_blocking": {
        "label": "active → blocking=true",
        "description": "active 规则满足全部阻断条件，建议开启 blocking=true",
        "target_status": "active",
        "target_blocking": "true",
    },
    "keep_proposed": {
        "label": "保持 proposed",
        "description": "规则不满足晋升条件或缺少审批，建议保持 proposed 状态",
        "target_status": "proposed",
        "target_blocking": "false",
    },
    "demote_or_rewrite": {
        "label": "降级或重写",
        "description": "规则存在严重问题（验证失败、路径无效等），建议降级或重写",
        "target_status": "proposed",
        "target_blocking": "false",
    },
}

# 晋升条件常量
PROPOSED_TO_ACTIVE_MIN_STABLE_RUNS = 3
ACTIVE_TO_BLOCKING_MIN_STABLE_RUNS = 7
ACTIVE_TO_BLOCKING_MIN_APPROVALS = 2
PROPOSED_TO_ACTIVE_MIN_APPROVALS = 1


# ---------------------------------------------------------------------------
# 加载函数
# ---------------------------------------------------------------------------

def load_rules(rules_path: str | Path) -> list[dict[str, Any]]:
    """从 memory_rules.yml 加载规则列表。

    Args:
        rules_path: YAML 文件路径（必须显式指定，不读 latest）

    Returns:
        规则字典列表

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 格式不正确或包含 latest
    """
    path = Path(rules_path)
    _reject_latest(path, "rules")
    if not path.exists():
        raise FileNotFoundError(f"规则文件不存在: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules = data.get("rules", [])
    if not isinstance(rules, list):
        raise ValueError("memory_rules.yml 的 rules 必须是列表")
    return rules


def load_validation_report(report_path: str | Path) -> dict[str, Any]:
    """加载 Step 15 生成的 patch validation report。

    Args:
        report_path: validation report JSON 文件路径

    Returns:
        验证报告字典（含 validation_items、summary 等）

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 格式不正确或包含 latest
    """
    path = Path(report_path)
    _reject_latest(path, "validation-report")
    if not path.exists():
        raise FileNotFoundError(f"验证报告文件不存在: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if "validation_items" not in data:
        raise ValueError("验证报告缺少 validation_items 字段")
    return data


def load_fast_gate_history(history_path: str | Path | None) -> list[dict[str, Any]]:
    """加载 fast gate 历史记录（可选）。

    Args:
        history_path: fast gate history JSON 文件路径，None 表示无历史

    Returns:
        fast gate 运行记录列表

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 格式不正确或包含 latest
    """
    if history_path is None:
        return []
    path = Path(history_path)
    _reject_latest(path, "fast-gate-history")
    if not path.exists():
        raise FileNotFoundError(f"Fast gate 历史文件不存在: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    # 支持两种格式：{"runs": [...]} 或直接的 [...]
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "runs" in data:
        runs = data["runs"]
        if not isinstance(runs, list):
            raise ValueError("fast_gate_history 的 runs 必须是列表")
        return runs
    raise ValueError("fast_gate_history 格式不正确，需要 runs 数组或顶层数组")


def load_approval_decisions(decisions_path: str | Path | None) -> dict[str, Any]:
    """加载人工审批决策记录（可选）。

    Args:
        decisions_path: approval decisions JSON 文件路径，None 表示无记录

    Returns:
        审批决策字典，包含 approvals 列表

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 格式不正确或包含 latest
    """
    if decisions_path is None:
        return {"approvals": []}
    path = Path(decisions_path)
    _reject_latest(path, "approval-decisions")
    if not path.exists():
        raise FileNotFoundError(f"审批决策文件不存在: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if "approvals" not in data:
        # 兼容格式：直接返回包装后的结构
        return {"approvals": data if isinstance(data, list) else []}
    if not isinstance(data["approvals"], list):
        raise ValueError("approval_decisions 的 approvals 必须是列表")
    return data


# ---------------------------------------------------------------------------
# 内部评估函数
# ---------------------------------------------------------------------------

def _reject_latest(path: Path, label: str) -> None:
    """如果文件名包含 latest 则抛出 ValueError。"""
    if "latest" in path.name.lower():
        raise ValueError(
            f"--{label} 不允许读取 *_latest.* 文件: {path.name}。请指定显式的 timestamp snapshot。"
        )


def _check_rule_id_format(rule_id: str) -> bool:
    """检查 rule_id 是否符合 TA-Rxxx 格式。"""
    return bool(re.match(r"^TA-R\d{3,}$", str(rule_id)))


def _check_rule_id_valid(rule: dict[str, Any], all_rules: list[dict[str, Any]]) -> list[str]:
    """检查 rule_id 格式和唯一性，返回问题列表（空列表表示通过）。"""
    issues: list[str] = []
    rule_id = str(rule.get("rule_id", ""))
    if not rule_id:
        issues.append("rule_id 缺失")
    elif not _check_rule_id_format(rule_id):
        issues.append(f"rule_id 格式不正确: {rule_id}，需匹配 TA-Rxxx")
    # 检查唯一性
    dup_count = sum(1 for r in all_rules if str(r.get("rule_id", "")) == rule_id)
    if dup_count > 1:
        issues.append(f"rule_id 重复: {rule_id} 出现 {dup_count} 次")
    return issues


def _check_applies_to_paths(
    rule: dict[str, Any], project_root: Path
) -> list[str]:
    """检查 applies_to 中的路径是否真实存在，返回不存在路径列表。"""
    missing: list[str] = []
    for relative_path in rule.get("applies_to", []) or []:
        if not (project_root / relative_path).exists():
            missing.append(relative_path)
    return missing


def _find_rule_in_validation(
    rule_id: str, validation_report: dict[str, Any]
) -> dict[str, Any] | None:
    """在 validation report 中查找与指定 rule_id 相关的验证结果。

    匹配策略：
    1. 在 validation_items 的 message 字段中搜索 rule_id
    2. 对于 memory_rule_patch 类型，匹配 target_file 为 memory_rules.yml 的项
    """
    items = validation_report.get("validation_items", [])
    matched: list[dict] = []
    for item in items:
        msg = str(item.get("message", ""))
        if rule_id in msg:
            matched.append(item)
    if matched:
        # 返回最高严重级别：failed > warning > passed > pending
        for status in ("failed", "warning", "passed", "pending"):
            for item in matched:
                if item.get("status") == status:
                    return item
        return matched[0]
    return None


def _check_fast_gate_stability(
    history: list[dict[str, Any]], min_runs: int
) -> dict[str, Any]:
    """检查 fast gate 运行稳定性。

    Args:
        history: fast gate 运行记录列表
        min_runs: 要求的最小稳定运行次数

    Returns:
        {
            "total_runs": int,
            "stable_runs": int,
            "required_runs": int,
            "is_stable": bool,
            "reason": str,
        }
    """
    if not history:
        return {
            "total_runs": 0,
            "stable_runs": 0,
            "required_runs": min_runs,
            "is_stable": False,
            "reason": "无 fast gate 历史记录",
        }
    stable_count = sum(
        1 for run in history
        if run.get("overall", "").upper() == "PASS"
        and run.get("harness_summary", {}).get("blocking_fail", 1) == 0
    )
    return {
        "total_runs": len(history),
        "stable_runs": stable_count,
        "required_runs": min_runs,
        "is_stable": stable_count >= min_runs,
        "reason": (
            f"稳定运行 {stable_count}/{min_runs} 次"
            if stable_count >= min_runs
            else f"稳定运行不足: {stable_count}/{min_runs} 次"
        ),
    }


def _evaluate_false_positive_risk(
    rule: dict[str, Any],
    validation_report: dict[str, Any],
) -> str:
    """评估规则的假阳性风险等级。

    Returns:
        "low" / "medium" / "high" / "unknown"
    """
    rule_id = str(rule.get("rule_id", ""))
    val_item = _find_rule_in_validation(rule_id, validation_report)
    if val_item is None:
        return "unknown"
    status = val_item.get("status", "unknown")
    if status == "failed":
        return "high"
    if status == "warning":
        return "medium"
    if status == "passed":
        # 检查 severity 和 message 内容进一步区分
        msg = str(val_item.get("message", ""))
        if "假阳性" in msg or "false positive" in msg.lower():
            return "medium"
        return "low"
    return "unknown"


def _has_rollback_plan(rule: dict[str, Any]) -> bool:
    """检查规则是否有回滚计划（通过 notes 字段判断）。"""
    notes = str(rule.get("notes", ""))
    markers = ["回滚", "rollback", "降级", "回退", "恢复方案"]
    return any(marker in notes.lower() for marker in markers)


def _check_coverage_status(
    rule: dict[str, Any], project_root: Path, field_name: str
) -> str:
    """检查单个 required_* 字段的覆盖状态。

    Returns:
        "complete": 非空且路径全部存在
        "missing": 字段为空
        "invalid": 非空但存在无效路径
        "todo_noted": 为空但 notes 中标注了 TODO/暂不需要
    """
    values = rule.get(field_name, []) or []
    if not values:
        notes = str(rule.get("notes", ""))
        if _notes_indicate_deferred(notes, field_name):
            return "todo_noted"
        return "missing"
    # 检查路径是否存在
    for relative_path in values:
        if not (project_root / relative_path).exists():
            return "invalid"
    return "complete"


def _notes_indicate_deferred(notes: str, field_name: str = "") -> bool:
    """检查 notes 是否明确说明某个字段暂不需要。"""
    markers = ["TODO", "待补", "待审", "待确认", "未完成"]
    defer_markers = ["暂不需要", "暂不要求", "暂缓", "延后", "无需"]
    has_todo = any(m in notes for m in markers)
    has_defer = any(m in notes for m in defer_markers)
    return has_todo or has_defer


def _notes_indicate_not_ready(notes: str) -> bool:
    """检查 notes 是否标记为未就绪（严格模式，用于 active→blocking）。"""
    markers = ["TODO", "待补", "待审", "待确认", "未完成"]
    return any(marker in notes for marker in markers)


# ---------------------------------------------------------------------------
# 单条规则评估
# ---------------------------------------------------------------------------

def _evaluate_proposed_to_active(
    rule: dict[str, Any],
    all_rules: list[dict[str, Any]],
    validation_report: dict[str, Any],
    fast_gate_history: list[dict[str, Any]],
    approval_decisions: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    """评估 proposed 规则是否满足晋升为 active 的条件。"""
    rule_id = str(rule.get("rule_id", ""))
    reasons: list[str] = []
    missing_reqs: list[str] = []

    # 1. 检查 rule_id 合法且唯一
    id_issues = _check_rule_id_valid(rule, all_rules)
    if id_issues:
        reasons.extend(id_issues)
        missing_reqs.append("rule_id 不合法或重复")
        return _make_candidate(
            rule, "demote_or_rewrite", "not_eligible",
            reasons, missing_reqs, "unknown",
            _build_coverage_status_map(rule, project_root),
            "failed" if id_issues else "not_found",
            _check_fast_gate_stability(fast_gate_history, PROPOSED_TO_ACTIVE_MIN_STABLE_RUNS),
            False,
        )

    # 2. 检查 applies_to 路径
    missing_paths = _check_applies_to_paths(rule, project_root)
    if missing_paths:
        reasons.append(f"applies_to 路径不存在: {', '.join(missing_paths)}")
        missing_reqs.append(f"applies_to 路径无效: {missing_paths}")
        return _make_candidate(
            rule, "demote_or_rewrite", "not_eligible",
            reasons, missing_reqs, "unknown",
            _build_coverage_status_map(rule, project_root),
            "not_found",
            _check_fast_gate_stability(fast_gate_history, PROPOSED_TO_ACTIVE_MIN_STABLE_RUNS),
            False,
        )

    # 3. 检查 validation report 状态
    val_item = _find_rule_in_validation(rule_id, validation_report)
    validation_status = val_item["status"] if val_item else "not_found"
    if validation_status == "failed":
        reasons.append(f"validation report 中存在 failed: {val_item.get('message', '')}")
        missing_reqs.append("validation report 有 failed 项")
        return _make_candidate(
            rule, "demote_or_rewrite", "not_eligible",
            reasons, missing_reqs,
            _evaluate_false_positive_risk(rule, validation_report),
            _build_coverage_status_map(rule, project_root),
            validation_status,
            _check_fast_gate_stability(fast_gate_history, PROPOSED_TO_ACTIVE_MIN_STABLE_RUNS),
            False,
        )

    # 4. 检查 required_* 覆盖
    coverage = _build_coverage_status_map(rule, project_root)
    for field, label in [("required_checks", "required_checks"),
                          ("required_tests", "required_tests"),
                          ("required_evals", "required_evals")]:
        status = coverage.get(label, "missing")
        if status == "missing":
            missing_reqs.append(f"{label} 为空且 notes 未说明暂不需要")
            reasons.append(f"{label} 缺失")
        elif status == "invalid":
            missing_reqs.append(f"{label} 存在无效路径")
            reasons.append(f"{label} 路径无效")
        elif status == "todo_noted":
            reasons.append(f"{label} 标记为暂不需要（notes 中有 TODO/暂缓标注）")

    # 5. 检查 fast gate 稳定性
    fg_stability = _check_fast_gate_stability(
        fast_gate_history, PROPOSED_TO_ACTIVE_MIN_STABLE_RUNS
    )
    if not fg_stability["is_stable"]:
        reasons.append(f"fast gate 稳定性不足: {fg_stability['reason']}")
        missing_reqs.append(f"fast gate 稳定运行不足 {PROPOSED_TO_ACTIVE_MIN_STABLE_RUNS} 次")

    # 6. 假阳性风险
    fp_risk = _evaluate_false_positive_risk(rule, validation_report)
    if fp_risk == "high":
        reasons.append("假阳性风险为 high")
        missing_reqs.append("假阳性风险过高")

    # 7. 检查 approval record（不加入 missing_reqs，单独判定）
    approvals = _count_approvals_for_rule(rule_id, approval_decisions, "proposed_to_active")
    has_approval = approvals >= PROPOSED_TO_ACTIVE_MIN_APPROVALS

    # 综合判定
    if not missing_reqs and has_approval:
        return _make_candidate(
            rule, "proposed_to_active", "eligible",
            reasons, missing_reqs, fp_risk, coverage,
            validation_status, fg_stability, True,
        )
    elif not missing_reqs and not has_approval:
        # 条件满足但缺审批
        reasons.append("所有晋升条件已满足，但缺少人工审批记录")
        return _make_candidate(
            rule, "proposed_to_active", "needs_manual_review",
            reasons,
            [f"缺少人工审批记录（需要 >= {PROPOSED_TO_ACTIVE_MIN_APPROVALS}）"],
            fp_risk, coverage,
            validation_status, fg_stability, True,
        )
    elif missing_reqs:
        # 技术条件存在缺陷
        # 只有 coverage todo_noted 才放宽到 needs_manual_review
        non_todo_missing = [
            m for m in missing_reqs
            if "暂不需要" not in m and "TODO" not in m
        ]
        if not non_todo_missing and has_approval:
            return _make_candidate(
                rule, "proposed_to_active", "needs_manual_review",
                reasons, missing_reqs, fp_risk, coverage,
                validation_status, fg_stability, True,
            )
        # 追加审批状态到 reasons 以帮助诊断
        if not has_approval:
            reasons.append(f"缺少人工审批记录（需要 >= {PROPOSED_TO_ACTIVE_MIN_APPROVALS}）")
        return _make_candidate(
            rule, "keep_proposed", "not_eligible",
            reasons, missing_reqs, fp_risk, coverage,
            validation_status, fg_stability, False,
        )

    return _make_candidate(
        rule, "keep_proposed", "not_eligible",
        reasons, missing_reqs, fp_risk, coverage,
        validation_status, fg_stability, False,
    )


def _evaluate_active_to_blocking(
    rule: dict[str, Any],
    all_rules: list[dict[str, Any]],
    validation_report: dict[str, Any],
    fast_gate_history: list[dict[str, Any]],
    approval_decisions: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    """评估 active+blocking=false 规则是否满足晋升为 blocking=true 的条件。"""
    rule_id = str(rule.get("rule_id", ""))
    reasons: list[str] = []
    missing_reqs: list[str] = []

    # 0. 前置检查：必须是 active 且 blocking 为 false
    current_status = rule.get("status", "")
    current_blocking = rule.get("blocking", None)
    if current_status != "active":
        reasons.append(f"规则状态为 {current_status}，非 active")
        missing_reqs.append("必须是 active 状态")
    if current_blocking is not False:
        reasons.append(f"blocking 当前为 {current_blocking}，非 false")
        missing_reqs.append("blocking 必须为 false 才能申请晋升")

    if missing_reqs:
        return _make_candidate(
            rule, "keep_proposed", "not_eligible",
            reasons, missing_reqs, "unknown",
            _build_coverage_status_map(rule, project_root),
            "not_found",
            _check_fast_gate_stability(fast_gate_history, ACTIVE_TO_BLOCKING_MIN_STABLE_RUNS),
            False,
        )

    # 1. required_* 全部存在且通过（不能有 todo_noted）
    coverage = _build_coverage_status_map(rule, project_root)
    for field, label in [("required_checks", "required_checks"),
                          ("required_tests", "required_tests"),
                          ("required_evals", "required_evals")]:
        status = coverage.get(label, "missing")
        if status == "missing":
            missing_reqs.append(f"{label} 为空")
            reasons.append(f"{label} 缺失")
        elif status == "invalid":
            missing_reqs.append(f"{label} 存在无效路径")
            reasons.append(f"{label} 路径无效")
        elif status == "todo_noted":
            missing_reqs.append(f"{label} 标记为暂不需要，active→blocking 要求完全闭环")
            reasons.append(f"{label} 标记为暂不需要（active→blocking 不允许）")

    # 2. notes 不能标记为未就绪
    notes = str(rule.get("notes", ""))
    if _notes_indicate_not_ready(notes):
        missing_reqs.append("notes 包含未就绪标记")
        reasons.append("notes 显示规则仍处于待补或待审状态")

    # 3. fast gate 至少 7 次稳定运行
    fg_stability = _check_fast_gate_stability(
        fast_gate_history, ACTIVE_TO_BLOCKING_MIN_STABLE_RUNS
    )
    if not fg_stability["is_stable"]:
        reasons.append(f"fast gate 稳定性不足: {fg_stability['reason']}")
        missing_reqs.append(f"fast gate 稳定运行不足 {ACTIVE_TO_BLOCKING_MIN_STABLE_RUNS} 次")

    # 4. 假阳性风险必须为 low
    fp_risk = _evaluate_false_positive_risk(rule, validation_report)
    if fp_risk in ("high", "medium"):
        reasons.append(f"假阳性风险为 {fp_risk}，active→blocking 要求 low")
        missing_reqs.append("假阳性风险必须为 low")

    # 5. 有回滚计划
    if not _has_rollback_plan(rule):
        reasons.append("缺少回滚计划（notes 中无回滚/rollback/降级/回退/恢复方案）")
        missing_reqs.append("缺少回滚计划")

    # 6. 有人工二次 approval
    approvals = _count_approvals_for_rule(rule_id, approval_decisions, "active_to_blocking")
    has_approval = approvals >= ACTIVE_TO_BLOCKING_MIN_APPROVALS
    if not has_approval:
        missing_reqs.append(
            f"缺少人工审批记录（需要 >= {ACTIVE_TO_BLOCKING_MIN_APPROVALS} 次）"
        )

    # 7. validation report 状态
    val_item = _find_rule_in_validation(rule_id, validation_report)
    validation_status = val_item["status"] if val_item else "not_found"
    if validation_status == "failed":
        reasons.append(f"validation report 中存在 failed")
        missing_reqs.append("validation report 有 failed 项")

    # 综合判定
    if not missing_reqs and has_approval:
        return _make_candidate(
            rule, "active_to_blocking", "eligible",
            reasons, missing_reqs, fp_risk, coverage,
            validation_status, fg_stability, True,
            rollback_plan=str(rule.get("notes", "")),
        )
    elif not missing_reqs and not has_approval:
        reasons.append("所有晋升条件已满足，但缺少人工审批记录")
        return _make_candidate(
            rule, "active_to_blocking", "needs_manual_review",
            reasons, missing_reqs, fp_risk, coverage,
            validation_status, fg_stability, True,
            rollback_plan=str(rule.get("notes", "")),
        )

    return _make_candidate(
        rule, "keep_proposed", "not_eligible",
        reasons, missing_reqs, fp_risk, coverage,
        validation_status, fg_stability, False,
    )


def _evaluate_rule(
    rule: dict[str, Any],
    all_rules: list[dict[str, Any]],
    validation_report: dict[str, Any],
    fast_gate_history: list[dict[str, Any]],
    approval_decisions: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    """调度到合适的评估器。

    评估策略：
    - status=proposed + blocking=false → _evaluate_proposed_to_active
    - status=active + blocking=false → _evaluate_active_to_blocking
    - status=active + blocking=true → keep_proposed（已处于最高级别）
    - status=deprecated/superseded → demote_or_rewrite
    """
    status = rule.get("status", "")
    blocking = rule.get("blocking", None)
    rule_id = str(rule.get("rule_id", ""))
    coverage = _build_coverage_status_map(rule, project_root)
    fg_default = _check_fast_gate_stability(fast_gate_history, 0)

    if status == "proposed" and blocking is False:
        return _evaluate_proposed_to_active(
            rule, all_rules, validation_report,
            fast_gate_history, approval_decisions, project_root,
        )
    elif status == "active" and blocking is False:
        return _evaluate_active_to_blocking(
            rule, all_rules, validation_report,
            fast_gate_history, approval_decisions, project_root,
        )
    elif status == "active" and blocking is True:
        return _make_candidate(
            rule, "keep_proposed", "not_eligible",
            ["已是 active + blocking=true，无需进一步晋升"],
            [], "low", coverage, "not_found", fg_default, False,
        )
    elif status == "deprecated":
        return _make_candidate(
            rule, "demote_or_rewrite", "not_eligible",
            ["规则已废弃 (deprecated)"],
            ["规则已废弃"], "unknown", coverage, "not_found", fg_default, False,
        )
    elif status == "superseded":
        return _make_candidate(
            rule, "demote_or_rewrite", "not_eligible",
            ["规则已被取代 (superseded)"],
            ["规则已被取代"], "unknown", coverage, "not_found", fg_default, False,
        )
    elif blocking is True and status == "proposed":
        # proposed + blocking=true 是异常状态
        return _make_candidate(
            rule, "demote_or_rewrite", "not_eligible",
            ["proposed 规则不能 blocking=true，需先恢复 blocking=false"],
            ["proposed 规则 blocking 异常"], "unknown", coverage,
            "not_found", fg_default, False,
        )
    else:
        return _make_candidate(
            rule, "keep_proposed", "not_eligible",
            [f"未知状态组合: status={status}, blocking={blocking}"],
            [], "unknown", coverage, "not_found", fg_default, False,
        )


# ---------------------------------------------------------------------------
# 候选对象构造
# ---------------------------------------------------------------------------

def _make_candidate(
    rule: dict[str, Any],
    promotion_type: str,
    eligibility: str,
    reasons: list[str],
    missing_requirements: list[str],
    false_positive_risk: str,
    coverage: dict[str, str],
    validation_status: str,
    fast_gate_stability: dict[str, Any],
    manual_approval_required: bool,
    rollback_plan: str | None = None,
) -> dict[str, Any]:
    """构造单个 promotion candidate 字典。"""
    meta = PROMOTION_TYPE_META.get(promotion_type, {})
    return {
        "rule_id": str(rule.get("rule_id", "")),
        "title": str(rule.get("title", "")),
        "current_status": rule.get("status", ""),
        "current_blocking": rule.get("blocking", False),
        "proposed_status": meta.get("target_status", rule.get("status", "")),
        "proposed_blocking": meta.get("target_blocking", "false"),
        "promotion_type": promotion_type,
        "eligibility": eligibility,
        "reasons": reasons,
        "missing_requirements": missing_requirements,
        "false_positive_risk": false_positive_risk,
        "required_checks_status": coverage.get("required_checks", "unknown"),
        "required_tests_status": coverage.get("required_tests", "unknown"),
        "required_evals_status": coverage.get("required_evals", "unknown"),
        "validation_status": validation_status,
        "fast_gate_stability": fast_gate_stability,
        "recommended_action": meta.get("description", ""),
        "manual_approval_required": manual_approval_required,
        "rollback_plan": rollback_plan,
    }


def _build_coverage_status_map(
    rule: dict[str, Any], project_root: Path
) -> dict[str, str]:
    """构建规则的三项覆盖状态映射。"""
    return {
        "required_checks": _check_coverage_status(rule, project_root, "required_checks"),
        "required_tests": _check_coverage_status(rule, project_root, "required_tests"),
        "required_evals": _check_coverage_status(rule, project_root, "required_evals"),
    }


def _count_approvals_for_rule(
    rule_id: str,
    approval_decisions: dict[str, Any],
    approval_type: str,
) -> int:
    """统计指定规则在审批决策中特定类型的审批次数。"""
    approvals = approval_decisions.get("approvals", [])
    count = 0
    for approval in approvals:
        if approval.get("rule_id") == rule_id:
            # 如果审批记录有 approval_type 则精确匹配，否则宽松计数
            at = approval.get("approval_type", "")
            if not at or at == approval_type:
                count += 1
    return count


# ---------------------------------------------------------------------------
# 编排函数
# ---------------------------------------------------------------------------

def build_rule_promotion_report(
    rules_path: str | Path,
    validation_report_path: str | Path,
    fast_gate_history_path: str | Path | None = None,
    approval_decisions_path: str | Path | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """生成 rule promotion proposal report。

    Args:
        rules_path: memory_rules.yml 路径
        validation_report_path: Step 15 validation report JSON 路径
        fast_gate_history_path: fast gate 历史 JSON 路径（可选）
        approval_decisions_path: 审批决策 JSON 路径（可选）
        project_root: 项目根目录（默认使用模块级 PROJECT_ROOT）

    Returns:
        完整的 promotion report 字典
    """
    root = Path(project_root) if project_root else PROJECT_ROOT

    # 加载输入
    rules = load_rules(rules_path)
    validation_report = load_validation_report(validation_report_path)
    fast_gate_history = load_fast_gate_history(fast_gate_history_path)
    approval_decisions = load_approval_decisions(approval_decisions_path)

    # 评估每条规则
    candidates = [
        _evaluate_rule(rule, rules, validation_report,
                       fast_gate_history, approval_decisions, root)
        for rule in rules
    ]

    # 分组
    proposed_to_active = [
        c for c in candidates if c["promotion_type"] == "proposed_to_active"
    ]
    active_to_blocking = [
        c for c in candidates if c["promotion_type"] == "active_to_blocking"
    ]
    keep_proposed = [
        c for c in candidates if c["promotion_type"] == "keep_proposed"
    ]
    demote_or_rewrite = [
        c for c in candidates if c["promotion_type"] == "demote_or_rewrite"
    ]
    eligible = [c for c in candidates if c["eligibility"] == "eligible"]
    not_eligible = [c for c in candidates if c["eligibility"] == "not_eligible"]
    needs_manual_review = [
        c for c in candidates if c["eligibility"] == "needs_manual_review"
    ]

    now = datetime.now(UTC)
    run_id = "rule-promotion-" + _safe_timestamp(now.isoformat())

    return {
        "run_id": run_id,
        "timestamp": now.isoformat(),
        "source_rules": str(rules_path),
        "source_validation_report": str(validation_report_path),
        "source_fast_gate_history": str(fast_gate_history_path) if fast_gate_history_path else None,
        "source_approval_decisions": str(approval_decisions_path) if approval_decisions_path else None,
        "summary": {
            "total_rules": len(rules),
            "total_candidates": len(candidates),
            "proposed_to_active": len(proposed_to_active),
            "active_to_blocking": len(active_to_blocking),
            "keep_proposed": len(keep_proposed),
            "demote_or_rewrite": len(demote_or_rewrite),
            "eligible": len(eligible),
            "not_eligible": len(not_eligible),
            "needs_manual_review": len(needs_manual_review),
        },
        "candidates": candidates,
        "eligible": eligible,
        "not_eligible": not_eligible,
        "needs_manual_review": needs_manual_review,
        "proposed_to_active": proposed_to_active,
        "active_to_blocking": active_to_blocking,
        "keep_proposed": keep_proposed,
        "demote_or_rewrite": demote_or_rewrite,
        "write_mode": "proposal_only",
    }


# ---------------------------------------------------------------------------
# 渲染函数
# ---------------------------------------------------------------------------

def render_rule_promotion_json(report: dict[str, Any]) -> dict[str, Any]:
    """构造可 JSON 序列化的 promotion report。"""
    payload = copy.deepcopy(report)
    payload.setdefault("run_id", "rule-promotion-unknown")
    payload.setdefault("timestamp", datetime.now(UTC).isoformat())
    payload.setdefault("source_rules", "")
    payload.setdefault("source_validation_report", "")
    payload.setdefault("source_fast_gate_history", None)
    payload.setdefault("source_approval_decisions", None)
    payload.setdefault("summary", {})
    payload.setdefault("candidates", [])
    payload.setdefault("eligible", [])
    payload.setdefault("not_eligible", [])
    payload.setdefault("needs_manual_review", [])
    payload.setdefault("proposed_to_active", [])
    payload.setdefault("active_to_blocking", [])
    payload.setdefault("keep_proposed", [])
    payload.setdefault("demote_or_rewrite", [])
    payload.setdefault("write_mode", "proposal_only")
    return json.loads(json.dumps(payload, ensure_ascii=False))


def render_rule_promotion_markdown(report: dict[str, Any]) -> str:
    """渲染人工审查用 Markdown 报告。"""
    r = render_rule_promotion_json(report)
    s = r["summary"]
    lines = [
        "# Memory Rule Promotion Proposal Report",
        "",
        "## Summary",
        "",
        f"- run_id: `{r['run_id']}`",
        f"- timestamp: `{r['timestamp']}`",
        f"- total rules: {s['total_rules']}",
        f"- total candidates: {s['total_candidates']}",
        f"- **proposed → active**: {s['proposed_to_active']}",
        f"- **active → blocking**: {s['active_to_blocking']}",
        f"- keep proposed: {s['keep_proposed']}",
        f"- demote or rewrite: {s['demote_or_rewrite']}",
        f"- eligible: {s['eligible']}",
        f"- not eligible: {s['not_eligible']}",
        f"- needs manual review: {s['needs_manual_review']}",
        "",
        "## Source Inputs",
        "",
        f"- rules: `{r['source_rules']}`",
        f"- validation report: `{r['source_validation_report']}`",
        f"- fast gate history: `{r['source_fast_gate_history'] or '（未提供）'}`",
        f"- approval decisions: `{r['source_approval_decisions'] or '（未提供）'}`",
        "",
        "> **重要说明**：本报告仅生成 promotion proposal，不自动修改 `memory_rules.yml`。",
        "> 所有晋升需人工审查后手动执行。",
        "",
    ]

    # Eligible proposed → active
    _append_candidate_section(
        lines, "Eligible proposed → active Candidates",
        [c for c in r.get("proposed_to_active", []) if c.get("eligibility") == "eligible"],
    )

    # Eligible active → blocking
    _append_candidate_section(
        lines, "Active → Blocking Candidates",
        [c for c in r.get("active_to_blocking", []) if c.get("eligibility") == "eligible"],
    )

    # Not Eligible
    _append_candidate_section(
        lines, "Not Eligible Candidates",
        r.get("not_eligible", []),
    )

    # Needs Manual Review
    _append_candidate_section(
        lines, "Needs Manual Review",
        r.get("needs_manual_review", []),
    )

    # Missing Requirements
    all_missing: dict[str, list[str]] = {}
    for c in r.get("candidates", []):
        for req in c.get("missing_requirements", []):
            rule_id = c.get("rule_id", "?")
            all_missing.setdefault(str(req), []).append(rule_id)
    lines.append("## Missing Requirements")
    lines.append("")
    if all_missing:
        for req, rule_ids in sorted(all_missing.items()):
            lines.append(f"- **{_escape_md(req)}**: {', '.join(rule_ids)}")
    else:
        lines.append("无。")
    lines.append("")

    # False Positive Risks
    lines.append("## False Positive Risks")
    lines.append("")
    fp_items = [
        c for c in r.get("candidates", [])
        if c.get("false_positive_risk") in ("medium", "high")
    ]
    if fp_items:
        lines.append("| rule_id | title | risk level |")
        lines.append("| --- | --- | --- |")
        for c in fp_items:
            lines.append(
                f"| {c['rule_id']} | {_escape_md(c.get('title', ''))} "
                f"| {c.get('false_positive_risk', 'unknown')} |"
            )
    else:
        lines.append("无高风险假阳性规则。")
    lines.append("")

    # Rollback Plans
    lines.append("## Rollback Plans")
    lines.append("")
    rb_items = [
        c for c in r.get("active_to_blocking", [])
        if c.get("rollback_plan")
    ]
    if rb_items:
        for c in rb_items:
            lines.append(f"- **{c['rule_id']}**: {_escape_md(str(c.get('rollback_plan', '')))}")
    else:
        lines.append("（无 active→blocking 候选或缺少回滚计划）")
    lines.append("")

    # Manual Approval Required
    lines.append("## Manual Approval Required")
    lines.append("")
    manual_items = [
        c for c in r.get("candidates", [])
        if c.get("manual_approval_required")
    ]
    if manual_items:
        for c in manual_items:
            lines.append(f"- **{c['rule_id']}** ({c.get('promotion_type', '')}): "
                         f"{_escape_md(str(c.get('recommended_action', '')))}")
    else:
        lines.append("无需人工审批的候选。")
    lines.append("")

    # Safety Boundaries
    lines.append("## Not Applied Automatically")
    lines.append("")
    lines.append("本轮安全边界：")
    lines.append("")
    lines.append("- ✅ 未自动修改 `docs/memory/memory_rules.yml`")
    lines.append("- ✅ 未自动修改 `docs/memory/经验复盘.md`")
    lines.append("- ✅ 未自动修改 `docs/memory/风险清单.md`")
    lines.append("- ✅ 未自动运行 `generate_rule_index.py`")
    lines.append("- ✅ 未把任何 proposed 自动改成 active")
    lines.append("- ✅ 未把任何 blocking 自动改成 true")
    lines.append("- ✅ 未接入 fast gate 阻断")
    lines.append("- ✅ 未接入 pre-commit")
    lines.append("- ✅ 未读取 `_latest.*` 文件")
    lines.append("- ✅ 未调用真实 LLM")
    lines.append("- ✅ 未修改业务代码")
    lines.append("- ✅ 所有输出标记为 `proposal_only`")
    lines.append("")

    return "\n".join(lines)


def _append_candidate_section(
    lines: list[str],
    title: str,
    items: list[dict[str, Any]],
) -> None:
    """追加候选规则表格章节。"""
    lines.extend([f"## {title}", ""])
    if not items:
        lines.extend(["无。", ""])
        return
    lines.append(
        "| rule_id | title | promotion_type | eligibility | "
        "false_positive_risk | validation | reasons |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for c in items:
        reason_str = "; ".join(c.get("reasons", [])[:3])
        if len(c.get("reasons", [])) > 3:
            reason_str += f" ... (+{len(c['reasons']) - 3})"
        lines.append(
            f"| {c['rule_id']} "
            f"| {_escape_md(str(c.get('title', '')))} "
            f"| {c.get('promotion_type', '')} "
            f"| {c.get('eligibility', '')} "
            f"| {c.get('false_positive_risk', '')} "
            f"| {c.get('validation_status', '')} "
            f"| {_escape_md(reason_str)} |"
        )
    lines.append("")


def _escape_md(value: str) -> str:
    """转义 Markdown 特殊字符。"""
    return value.replace("|", "\\|").replace("\n", " ")


# ---------------------------------------------------------------------------
# Snapshot 写入
# ---------------------------------------------------------------------------

def write_rule_promotion_snapshot(
    report: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Path]:
    """写入带 timestamp 的 snapshot 报告，不生成 latest 文件。

    Args:
        report: promotion report 字典
        output_dir: 输出目录

    Returns:
        {"json": Path, "markdown": Path}
    """
    r = render_rule_promotion_json(report)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    timestamp = _safe_timestamp(r["timestamp"])
    json_path = output / f"memory_rule_promotion_{timestamp}.json"
    markdown_path = output / f"memory_rule_promotion_{timestamp}.md"
    json_path.write_text(
        json.dumps(r, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_rule_promotion_markdown(report),
        encoding="utf-8",
    )
    return {"json": json_path, "markdown": markdown_path}


def _safe_timestamp(value: str) -> str:
    """将 ISO timestamp 转换为文件名安全格式。"""
    return (
        value.replace(":", "")
        .replace("-", "")
        .replace(".", "")
        .replace("+", "")
    )
