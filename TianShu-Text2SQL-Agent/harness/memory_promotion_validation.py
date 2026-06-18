"""Memory Promotion Apply Validation Workflow（Step 17）。

读取 Step 16 promotion proposal report + memory_rules.yml，
验证人工应用的 promotion 是否正确，不自动修改任何文件。

关键边界：
    - 只做 validation，不做 apply
    - 不自动修改 memory_rules.yml
    - 不自动修改 docs/memory/*
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

VALID_STATUSES = {"proposed", "active", "deprecated", "superseded"}


# ---------------------------------------------------------------------------
# 加载函数
# ---------------------------------------------------------------------------

def load_promotion_report(report_path: str | Path) -> dict[str, Any]:
    """加载 Step 16 生成的 promotion proposal report。

    Args:
        report_path: promotion report JSON 文件路径

    Returns:
        完整的 promotion report 字典

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 格式不正确或包含 latest
    """
    path = Path(report_path)
    _reject_latest(path, "promotion-report")
    if not path.exists():
        raise FileNotFoundError(f"Promotion report 文件不存在: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if "candidates" not in data:
        raise ValueError("Promotion report 缺少 candidates 字段")
    return data


def load_rules(rules_path: str | Path) -> list[dict[str, Any]]:
    """从 memory_rules.yml 加载规则列表。"""
    path = Path(rules_path)
    _reject_latest(path, "rules")
    if not path.exists():
        raise FileNotFoundError(f"规则文件不存在: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules = data.get("rules", [])
    if not isinstance(rules, list):
        raise ValueError("memory_rules.yml 的 rules 必须是列表")
    return rules


def _reject_latest(path: Path, label: str) -> None:
    """如果文件名包含 latest 则抛出 ValueError。"""
    if "latest" in path.name.lower():
        raise ValueError(
            f"--{label} 不允许读取 *_latest.* 文件: {path.name}。"
            f"请指定显式的 timestamp snapshot。"
        )


# ---------------------------------------------------------------------------
# 检查 1: Promotion report 基础检查
# ---------------------------------------------------------------------------

def _validate_promotion_report_basics(report: dict[str, Any]) -> list[dict[str, Any]]:
    """检查 promotion report 结构完整性。"""
    items: list[dict[str, Any]] = []

    # write_mode 检查
    write_mode = report.get("write_mode", "")
    if write_mode != "proposal_only":
        items.append({
            "rule_id": "N/A",
            "promotion_type": "N/A",
            "check_category": "promotion_report_basics",
            "status": "failed",
            "message": f"promotion report 的 write_mode 应为 proposal_only，实际为 {write_mode}",
            "expected_status": "",
            "actual_status": "",
            "expected_blocking": False,
            "actual_blocking": False,
            "manual_action": "确认 promotion report 来源正确，应是 Step 16 proposal_only 输出",
        })
    else:
        items.append({
            "rule_id": "N/A",
            "promotion_type": "N/A",
            "check_category": "promotion_report_basics",
            "status": "passed",
            "message": "promotion report write_mode 为 proposal_only",
            "expected_status": "",
            "actual_status": "",
            "expected_blocking": False,
            "actual_blocking": False,
            "manual_action": None,
        })

    # candidates 字段检查
    candidates = report.get("candidates", [])
    if not candidates:
        items.append({
            "rule_id": "N/A",
            "promotion_type": "N/A",
            "check_category": "promotion_report_basics",
            "status": "warning",
            "message": "promotion report 的 candidates 为空",
            "expected_status": "",
            "actual_status": "",
            "expected_blocking": False,
            "actual_blocking": False,
            "manual_action": "确认 promotion report 是否来自空规则集或未评估场景",
        })

    # 每个 candidate 的必填字段
    required_fields = {"rule_id", "promotion_type", "proposed_status",
                       "proposed_blocking", "eligibility"}
    missing_field_candidates = []
    for c in candidates:
        missing = required_fields - set(c.keys())
        if missing:
            missing_field_candidates.append(
                f"{c.get('rule_id', '?')}: 缺少 {', '.join(sorted(missing))}"
            )
    if missing_field_candidates:
        items.append({
            "rule_id": "N/A",
            "promotion_type": "N/A",
            "check_category": "promotion_report_basics",
            "status": "failed",
            "message": f"candidates 缺少必填字段: {'; '.join(missing_field_candidates)}",
            "expected_status": "",
            "actual_status": "",
            "expected_blocking": False,
            "actual_blocking": False,
            "manual_action": "检查 promotion report 生成是否正确",
        })
    else:
        items.append({
            "rule_id": "N/A",
            "promotion_type": "N/A",
            "check_category": "promotion_report_basics",
            "status": "passed",
            "message": f"全部 {len(candidates)} 个 candidate 字段完整",
            "expected_status": "",
            "actual_status": "",
            "expected_blocking": False,
            "actual_blocking": False,
            "manual_action": None,
        })

    return items


# ---------------------------------------------------------------------------
# 检查 2: memory_rules.yml 基础检查
# ---------------------------------------------------------------------------

def _validate_rules_basics(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """检查 memory_rules.yml 的 rule_id 格式、唯一性、status/blocking 合法性。"""
    items: list[dict[str, Any]] = []

    if not rules:
        items.append({
            "rule_id": "N/A",
            "promotion_type": "N/A",
            "check_category": "rules_basics",
            "status": "warning",
            "message": "memory_rules.yml 的 rules 为空",
            "expected_status": "",
            "actual_status": "",
            "expected_blocking": False,
            "actual_blocking": False,
            "manual_action": None,
        })
        return items

    # 收集 rule_id
    seen_ids: dict[str, int] = {}
    for rule in rules:
        rid = str(rule.get("rule_id", ""))
        seen_ids[rid] = seen_ids.get(rid, 0) + 1

    # 检查重复
    duplicates = {rid: cnt for rid, cnt in seen_ids.items() if cnt > 1}
    if duplicates:
        dup_msg = "; ".join(f"{rid} 出现 {cnt} 次" for rid, cnt in duplicates.items())
        items.append({
            "rule_id": "N/A",
            "promotion_type": "N/A",
            "check_category": "rules_basics",
            "status": "failed",
            "message": f"rule_id 重复: {dup_msg}",
            "expected_status": "",
            "actual_status": "",
            "expected_blocking": False,
            "actual_blocking": False,
            "manual_action": "删除重复规则，确保每个 rule_id 唯一",
        })

    # 逐条检查
    for rule in rules:
        rid = str(rule.get("rule_id", ""))
        status = rule.get("status", "")
        blocking = rule.get("blocking", None)

        # TA-Rxxx 格式
        if not re.match(r"^TA-R\d{3,}$", rid):
            items.append({
                "rule_id": rid or "?",
                "promotion_type": "N/A",
                "check_category": "rules_basics",
                "status": "failed",
                "message": f"rule_id 格式不正确: {rid}，需匹配 TA-Rxxx",
                "expected_status": "",
                "actual_status": str(status),
                "expected_blocking": False,
                "actual_blocking": bool(blocking),
                "manual_action": "修正 rule_id 为 TA-Rxxx 格式",
            })

        # status 枚举
        if status not in VALID_STATUSES:
            items.append({
                "rule_id": rid,
                "promotion_type": "N/A",
                "check_category": "rules_basics",
                "status": "failed",
                "message": f"status 非法: {status}，合法值为 {sorted(VALID_STATUSES)}",
                "expected_status": "",
                "actual_status": str(status),
                "expected_blocking": False,
                "actual_blocking": bool(blocking),
                "manual_action": "修正 status 为合法枚举值",
            })

        # blocking 类型
        if not isinstance(blocking, bool):
            items.append({
                "rule_id": rid,
                "promotion_type": "N/A",
                "check_category": "rules_basics",
                "status": "failed",
                "message": f"blocking 应为布尔值，实际类型为 {type(blocking).__name__}",
                "expected_status": str(status),
                "actual_status": str(status),
                "expected_blocking": False,
                "actual_blocking": bool(blocking) if isinstance(blocking, bool) else False,
                "manual_action": "修正 blocking 为 true 或 false",
            })

    if not items:
        items.append({
            "rule_id": "N/A",
            "promotion_type": "N/A",
            "check_category": "rules_basics",
            "status": "passed",
            "message": f"全部 {len(rules)} 条规则基础检查通过",
            "expected_status": "",
            "actual_status": "",
            "expected_blocking": False,
            "actual_blocking": False,
            "manual_action": None,
        })

    return items


# ---------------------------------------------------------------------------
# 辅助: 在 rules 列表中按 rule_id 查找
# ---------------------------------------------------------------------------

def _find_rule_by_id(rule_id: str, rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    """按 rule_id 查找规则。"""
    for rule in rules:
        if str(rule.get("rule_id", "")) == rule_id:
            return rule
    return None


def _has_rollback_plan(rule: dict[str, Any]) -> bool:
    """检查规则 notes 中是否有回滚计划。"""
    notes = str(rule.get("notes", ""))
    markers = ["回滚", "rollback", "降级", "回退", "恢复方案"]
    return any(marker in notes.lower() for marker in markers)


def _check_required_paths(rule: dict[str, Any], project_root: Path) -> dict[str, str]:
    """检查 required_* 路径是否存在。返回每个字段的状态。"""
    result: dict[str, str] = {}
    for field in ("required_checks", "required_tests", "required_evals"):
        values = rule.get(field, []) or []
        if not values:
            notes = str(rule.get("notes", ""))
            if "暂不需要" in notes or "无需" in notes:
                result[field] = "deferred"
            else:
                result[field] = "missing"
        else:
            all_exist = all((project_root / p).exists() for p in values)
            result[field] = "complete" if all_exist else "invalid"
    return result


# ---------------------------------------------------------------------------
# 检查 3: 人工应用是否符合 proposal
# ---------------------------------------------------------------------------

def _validate_promotion_application(
    rules: list[dict[str, Any]],
    report: dict[str, Any],
    project_root: Path,
) -> list[dict[str, Any]]:
    """验证人工应用是否符合 Step 16 proposal。

    仅对 eligible 的 candidate 做对照检查。
    """
    items: list[dict[str, Any]] = []
    candidates = report.get("candidates", [])

    for candidate in candidates:
        rule_id = str(candidate.get("rule_id", ""))
        promotion_type = candidate.get("promotion_type", "")
        eligibility = candidate.get("eligibility", "")
        proposed_status = candidate.get("proposed_status", "")
        proposed_blocking = candidate.get("proposed_blocking", "false")
        proposed_blocking_bool = proposed_blocking == "true"

        rule = _find_rule_by_id(rule_id, rules)
        if rule is None:
            # 规则可能已被删除
            items.append({
                "rule_id": rule_id,
                "promotion_type": promotion_type,
                "check_category": "promotion_application",
                "status": "warning",
                "message": f"promotion report 中的规则 {rule_id} 在 memory_rules.yml 中不存在（可能已删除）",
                "expected_status": proposed_status,
                "actual_status": "（不存在）",
                "expected_blocking": proposed_blocking_bool,
                "actual_blocking": False,
                "manual_action": "确认该规则是否被有意删除",
            })
            continue

        actual_status = str(rule.get("status", ""))
        actual_blocking = bool(rule.get("blocking", False))

        if eligibility == "eligible":
            if promotion_type == "proposed_to_active":
                _check_proposed_to_active_applied(
                    items, rule_id, rule, proposed_status, proposed_blocking_bool,
                    actual_status, actual_blocking,
                )
            elif promotion_type == "active_to_blocking":
                _check_active_to_blocking_applied(
                    items, rule_id, rule, proposed_blocking_bool,
                    actual_status, actual_blocking, project_root,
                )
            else:
                items.append({
                    "rule_id": rule_id,
                    "promotion_type": promotion_type,
                    "check_category": "promotion_application",
                    "status": "warning",
                    "message": f"eligible candidate 的 promotion_type 为 {promotion_type}，无对应检查逻辑",
                    "expected_status": proposed_status,
                    "actual_status": actual_status,
                    "expected_blocking": proposed_blocking_bool,
                    "actual_blocking": actual_blocking,
                    "manual_action": None,
                })

    return items


def _check_proposed_to_active_applied(
    items: list[dict[str, Any]],
    rule_id: str,
    rule: dict[str, Any],
    proposed_status: str,
    proposed_blocking_bool: bool,
    actual_status: str,
    actual_blocking: bool,
) -> None:
    """检查 proposed_to_active 是否被正确应用。"""
    if actual_status == "active" and actual_blocking is False:
        items.append({
            "rule_id": rule_id,
            "promotion_type": "proposed_to_active",
            "check_category": "promotion_application",
            "status": "passed",
            "message": "proposed_to_active 已正确应用: status=active, blocking=false",
            "expected_status": "active",
            "actual_status": actual_status,
            "expected_blocking": False,
            "actual_blocking": actual_blocking,
            "manual_action": None,
        })
    elif actual_status == "active" and actual_blocking is True:
        items.append({
            "rule_id": rule_id,
            "promotion_type": "proposed_to_active",
            "check_category": "promotion_application",
            "status": "failed",
            "message": "proposed_to_active 被越级提升: blocking=true（proposal 只建议到 active+blocking=false）",
            "expected_status": "active",
            "actual_status": actual_status,
            "expected_blocking": False,
            "actual_blocking": actual_blocking,
            "manual_action": "将 blocking 改回 false，或提供 active→blocking 审批记录",
        })
    elif actual_status == "proposed":
        items.append({
            "rule_id": rule_id,
            "promotion_type": "proposed_to_active",
            "check_category": "promotion_application",
            "status": "pending",
            "message": "proposed_to_active proposal 尚未被应用（仍为 proposed）",
            "expected_status": "active",
            "actual_status": actual_status,
            "expected_blocking": False,
            "actual_blocking": actual_blocking,
            "manual_action": "审查 proposal 后手动将 status 改为 active, blocking 保持 false",
        })
    else:
        items.append({
            "rule_id": rule_id,
            "promotion_type": "proposed_to_active",
            "check_category": "promotion_application",
            "status": "failed",
            "message": f"proposed_to_active 应用异常: 期望 active，实际 status={actual_status}, blocking={actual_blocking}",
            "expected_status": "active",
            "actual_status": actual_status,
            "expected_blocking": False,
            "actual_blocking": actual_blocking,
            "manual_action": "检查规则状态变更是否符合 proposal",
        })


def _check_active_to_blocking_applied(
    items: list[dict[str, Any]],
    rule_id: str,
    rule: dict[str, Any],
    proposed_blocking_bool: bool,
    actual_status: str,
    actual_blocking: bool,
    project_root: Path,
) -> None:
    """检查 active_to_blocking 是否被正确应用。"""
    if actual_status == "active" and actual_blocking is True:
        # 已应用，检查闭环
        path_status = _check_required_paths(rule, project_root)
        missing_fields = [f for f, s in path_status.items() if s in ("missing", "invalid")]
        has_rb = _has_rollback_plan(rule)

        issues = []
        if missing_fields:
            issues.append(f"{', '.join(missing_fields)} 未闭环")
        if not has_rb:
            issues.append("缺少回滚计划")

        if issues:
            items.append({
                "rule_id": rule_id,
                "promotion_type": "active_to_blocking",
                "check_category": "promotion_application",
                "status": "failed",
                "message": f"active_to_blocking 已应用但闭环不完整: {'; '.join(issues)}",
                "expected_status": "active",
                "actual_status": actual_status,
                "expected_blocking": True,
                "actual_blocking": actual_blocking,
                "manual_action": "补齐缺失的 required_* 路径或回滚计划",
            })
        else:
            items.append({
                "rule_id": rule_id,
                "promotion_type": "active_to_blocking",
                "check_category": "promotion_application",
                "status": "passed",
                "message": "active_to_blocking 已正确应用且闭环完整",
                "expected_status": "active",
                "actual_status": actual_status,
                "expected_blocking": True,
                "actual_blocking": actual_blocking,
                "manual_action": None,
            })
    elif actual_status == "active" and actual_blocking is False:
        items.append({
            "rule_id": rule_id,
            "promotion_type": "active_to_blocking",
            "check_category": "promotion_application",
            "status": "pending",
            "message": "active_to_blocking proposal 尚未被应用（仍为 blocking=false）",
            "expected_status": "active",
            "actual_status": actual_status,
            "expected_blocking": True,
            "actual_blocking": actual_blocking,
            "manual_action": "审查 proposal 后手动将 blocking 改为 true",
        })
    else:
        items.append({
            "rule_id": rule_id,
            "promotion_type": "active_to_blocking",
            "check_category": "promotion_application",
            "status": "failed",
            "message": f"active_to_blocking 应用异常: 期望 active+blocking=true，实际 status={actual_status}, blocking={actual_blocking}",
            "expected_status": "active",
            "actual_status": actual_status,
            "expected_blocking": True,
            "actual_blocking": actual_blocking,
            "manual_action": "检查规则状态变更是否符合 proposal",
        })


# ---------------------------------------------------------------------------
# 检查 4: 防止越级晋升
# ---------------------------------------------------------------------------

def _validate_no_unauthorized_promotions(
    rules: list[dict[str, Any]],
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    """检查 not_eligible / keep_proposed / demote_or_rewrite / needs_manual_review
    的规则是否被错误晋升。"""
    items: list[dict[str, Any]] = []
    candidates = report.get("candidates", [])

    for candidate in candidates:
        rule_id = str(candidate.get("rule_id", ""))
        promotion_type = candidate.get("promotion_type", "")
        eligibility = candidate.get("eligibility", "")

        # 只检查非 eligible 的 candidate
        if eligibility == "eligible":
            continue

        rule = _find_rule_by_id(rule_id, rules)
        if rule is None:
            continue

        actual_status = str(rule.get("status", ""))
        actual_blocking = bool(rule.get("blocking", False))

        if eligibility == "needs_manual_review":
            # 不得 blocking=true
            if actual_blocking is True:
                items.append({
                    "rule_id": rule_id,
                    "promotion_type": promotion_type,
                    "check_category": "unauthorized_promotion",
                    "status": "failed",
                    "message": f"needs_manual_review 规则 {rule_id} 被设置为 blocking=true，缺少审批记录",
                    "expected_status": "",
                    "actual_status": actual_status,
                    "expected_blocking": False,
                    "actual_blocking": actual_blocking,
                    "manual_action": "将 blocking 改回 false 或补充审批记录",
                })
            elif actual_status == "active":
                items.append({
                    "rule_id": rule_id,
                    "promotion_type": promotion_type,
                    "check_category": "unauthorized_promotion",
                    "status": "warning",
                    "message": f"needs_manual_review 规则 {rule_id} 被设置为 active，需确认是否有审批记录",
                    "expected_status": "",
                    "actual_status": actual_status,
                    "expected_blocking": False,
                    "actual_blocking": actual_blocking,
                    "manual_action": "确认是否有补充审批记录，如有可忽略此 warning",
                })

        elif eligibility == "not_eligible":
            # 不得 active，不得 blocking=true
            if actual_status == "active" or actual_blocking is True:
                items.append({
                    "rule_id": rule_id,
                    "promotion_type": promotion_type,
                    "check_category": "unauthorized_promotion",
                    "status": "failed",
                    "message": (
                        f"not_eligible 规则 {rule_id} 被晋升: status={actual_status}, "
                        f"blocking={actual_blocking}（不符合晋升条件: {candidate.get('promotion_type', '')})"
                    ),
                    "expected_status": "",
                    "actual_status": actual_status,
                    "expected_blocking": False,
                    "actual_blocking": actual_blocking,
                    "manual_action": "将该规则恢复为 proposed+blocking=false",
                })

        elif eligibility == "not_eligible" and promotion_type == "demote_or_rewrite":
            # demote_or_rewrite → 更严格：任何非 proposed 状态都算问题
            if actual_status not in ("proposed", "deprecated"):
                items.append({
                    "rule_id": rule_id,
                    "promotion_type": promotion_type,
                    "check_category": "unauthorized_promotion",
                    "status": "failed",
                    "message": (
                        f"demote_or_rewrite 规则 {rule_id} 不应为 active: "
                        f"status={actual_status}, blocking={actual_blocking}"
                    ),
                    "expected_status": "",
                    "actual_status": actual_status,
                    "expected_blocking": False,
                    "actual_blocking": actual_blocking,
                    "manual_action": "降级或重写该规则，不应保持 active",
                })

    return items


# ---------------------------------------------------------------------------
# 检查 5: active+blocking=true 闭环检查
# ---------------------------------------------------------------------------

def _validate_active_blocking_closure(
    rules: list[dict[str, Any]],
    project_root: Path,
) -> list[dict[str, Any]]:
    """对所有 active+blocking=true 规则检查全覆盖闭环。"""
    items: list[dict[str, Any]] = []
    active_blocking_rules = [
        r for r in rules
        if r.get("status") == "active" and r.get("blocking") is True
    ]

    if not active_blocking_rules:
        items.append({
            "rule_id": "N/A",
            "promotion_type": "N/A",
            "check_category": "active_blocking_closure",
            "status": "passed",
            "message": "无 active+blocking=true 规则，闭环检查通过",
            "expected_status": "",
            "actual_status": "",
            "expected_blocking": False,
            "actual_blocking": False,
            "manual_action": None,
        })
        return items

    for rule in active_blocking_rules:
        rid = str(rule.get("rule_id", ""))
        path_status = _check_required_paths(rule, project_root)
        issues = []

        for field, label in [("required_checks", "required_checks"),
                              ("required_tests", "required_tests")]:
            if path_status.get(field) != "complete":
                issues.append(f"{label} 状态={path_status.get(field, '?')}")

        # required_evals 可有 deferred 状态
        evals_status = path_status.get("required_evals", "missing")
        if evals_status == "missing":
            issues.append("required_evals 缺失")
        elif evals_status == "invalid":
            issues.append("required_evals 路径无效")

        if not _has_rollback_plan(rule):
            issues.append("缺少回滚计划")

        if issues:
            items.append({
                "rule_id": rid,
                "promotion_type": "N/A",
                "check_category": "active_blocking_closure",
                "status": "failed",
                "message": f"active+blocking=true 规则 {rid} 闭环不完整: {'; '.join(issues)}",
                "expected_status": "active",
                "actual_status": "active",
                "expected_blocking": True,
                "actual_blocking": True,
                "manual_action": "补齐缺失的 required_* 文件或回滚计划",
            })
        else:
            items.append({
                "rule_id": rid,
                "promotion_type": "N/A",
                "check_category": "active_blocking_closure",
                "status": "passed",
                "message": f"规则 {rid} active+blocking=true 闭环完整",
                "expected_status": "active",
                "actual_status": "active",
                "expected_blocking": True,
                "actual_blocking": True,
                "manual_action": None,
            })

    return items


# ---------------------------------------------------------------------------
# 检查 6: Rule index 同步检查
# ---------------------------------------------------------------------------

def _check_rule_index_sync(
    rules: list[dict[str, Any]],
    project_root: Path,
) -> list[dict[str, Any]]:
    """检查 规则来源索引.md 是否与 memory_rules.yml 同步。"""
    items: list[dict[str, Any]] = []
    index_path = project_root / "docs" / "memory" / "规则来源索引.md"

    if not index_path.exists():
        items.append({
            "rule_id": "N/A",
            "promotion_type": "N/A",
            "check_category": "rule_index_sync",
            "status": "warning",
            "message": "规则来源索引.md 不存在",
            "expected_status": "",
            "actual_status": "",
            "expected_blocking": False,
            "actual_blocking": False,
            "manual_action": "运行 scripts/generate_rule_index.py 生成索引",
        })
        return items

    content = index_path.read_text(encoding="utf-8")
    # 提取索引中注册的 rule_id
    index_rule_ids = set(re.findall(r"\*\*(TA-R\d{3,})\*\*", content))
    yaml_rule_ids = {str(r.get("rule_id", "")) for r in rules}
    yaml_rule_ids.discard("")

    missing_in_index = yaml_rule_ids - index_rule_ids
    extra_in_index = index_rule_ids - yaml_rule_ids

    if missing_in_index or extra_in_index:
        details = []
        if missing_in_index:
            details.append(f"索引缺失: {', '.join(sorted(missing_in_index))}")
        if extra_in_index:
            details.append(f"索引多余: {', '.join(sorted(extra_in_index))}")
        items.append({
            "rule_id": "N/A",
            "promotion_type": "N/A",
            "check_category": "rule_index_sync",
            "status": "warning",
            "message": f"规则来源索引.md 与 memory_rules.yml 不同步: {'; '.join(details)}",
            "expected_status": "",
            "actual_status": "",
            "expected_blocking": False,
            "actual_blocking": False,
            "manual_action": "运行 scripts/generate_rule_index.py 更新索引",
        })
    else:
        items.append({
            "rule_id": "N/A",
            "promotion_type": "N/A",
            "check_category": "rule_index_sync",
            "status": "passed",
            "message": "规则来源索引.md 与 memory_rules.yml 同步",
            "expected_status": "",
            "actual_status": "",
            "expected_blocking": False,
            "actual_blocking": False,
            "manual_action": None,
        })

    return items


# ---------------------------------------------------------------------------
# 检查 7: 推荐命令
# ---------------------------------------------------------------------------

def _build_recommended_commands() -> list[str]:
    """生成建议运行的命令列表。"""
    return [
        "python scripts/generate_rule_index.py",
        "python harness/checks/check_memory_update.py --registry",
        "python harness/run_harness.py",
        "python harness/run_fast_gate.py",
        'python -m pytest tests -k "memory"',
    ]


# ---------------------------------------------------------------------------
# 编排函数
# ---------------------------------------------------------------------------

def build_promotion_validation_report(
    promotion_report_path: str | Path,
    rules_path: str | Path,
    project_root: Path | None = None,
    run_checks: bool = False,
) -> dict[str, Any]:
    """生成 promotion apply validation report。

    Args:
        promotion_report_path: Step 16 promotion report JSON 路径
        rules_path: memory_rules.yml 路径
        project_root: 项目根目录
        run_checks: 是否运行重型命令

    Returns:
        完整的 validation report 字典
    """
    root = Path(project_root) if project_root else PROJECT_ROOT

    # 加载输入文件
    report = load_promotion_report(promotion_report_path)
    rules = load_rules(rules_path)

    # 汇总所有 validation items
    all_items: list[dict[str, Any]] = []

    # 1. Promotion report 基础检查
    all_items.extend(_validate_promotion_report_basics(report))

    # 2. memory_rules.yml 基础检查
    all_items.extend(_validate_rules_basics(rules))

    # 3. 人工应用是否符合 proposal
    all_items.extend(_validate_promotion_application(rules, report, root))

    # 4. 防止越级晋升
    all_items.extend(_validate_no_unauthorized_promotions(rules, report))

    # 5. active+blocking=true 闭环检查
    all_items.extend(_validate_active_blocking_closure(rules, root))

    # 6. Rule index 同步
    all_items.extend(_check_rule_index_sync(rules, root))

    # 7. 推荐命令
    recommended_commands = _build_recommended_commands()

    # 汇总
    passed = sum(1 for i in all_items if i["status"] == "passed")
    warnings = sum(1 for i in all_items if i["status"] == "warning")
    failures = sum(1 for i in all_items if i["status"] == "failed")
    pending = sum(1 for i in all_items if i["status"] == "pending")
    applied = sum(
        1 for i in all_items
        if i.get("check_category") == "promotion_application"
        and i["status"] == "passed"
    )

    now = datetime.now(UTC)
    run_id = "PRV" + now.strftime("%Y%m%dT%H%M%SZ")

    return {
        "run_id": run_id,
        "timestamp": now.isoformat(),
        "source_promotion_report": str(promotion_report_path),
        "rules_file": str(rules_path),
        "run_checks": run_checks,
        "summary": {
            "candidates_checked": len(report.get("candidates", [])),
            "total_validation_items": len(all_items),
            "applied": applied,
            "passed": passed,
            "warnings": warnings,
            "failures": failures,
            "pending_manual_actions": pending,
        },
        "validation_items": all_items,
        "recommended_commands": recommended_commands,
        "write_mode": "proposal_only",
    }


# ---------------------------------------------------------------------------
# 渲染函数
# ---------------------------------------------------------------------------

def render_promotion_validation_json(report: dict[str, Any]) -> dict[str, Any]:
    """构造可 JSON 序列化的 validation report。"""
    payload = copy.deepcopy(report)
    payload.setdefault("run_id", "PRV-unknown")
    payload.setdefault("timestamp", datetime.now(UTC).isoformat())
    payload.setdefault("source_promotion_report", "")
    payload.setdefault("rules_file", "")
    payload.setdefault("run_checks", False)
    payload.setdefault("summary", {})
    payload.setdefault("validation_items", [])
    payload.setdefault("recommended_commands", [])
    payload.setdefault("write_mode", "proposal_only")
    return json.loads(json.dumps(payload, ensure_ascii=False))


def render_promotion_validation_markdown(report: dict[str, Any]) -> str:
    """渲染人工审查用 Markdown 报告。"""
    r = render_promotion_validation_json(report)
    s = r["summary"]
    items = r["validation_items"]

    lines = [
        "# Memory Promotion Validation Report",
        "",
        "## Summary",
        "",
        f"- run_id: `{r['run_id']}`",
        f"- timestamp: `{r['timestamp']}`",
        f"- candidates checked: {s['candidates_checked']}",
        f"- total validation items: {s['total_validation_items']}",
        f"- **applied**: {s['applied']}",
        f"- passed: {s['passed']}",
        f"- warnings: {s['warnings']}",
        f"- failures: {s['failures']}",
        f"- pending manual actions: {s['pending_manual_actions']}",
        "",
        "## Source Promotion Report",
        "",
        f"- report: `{r['source_promotion_report']}`",
        f"- rules file: `{r['rules_file']}`",
        "",
        "> **重要说明**：本报告只做 validation，不修改 `memory_rules.yml`。",
        "> 所有 failed 项需人工修复后重新运行验证。",
        "",
    ]

    # Applied Promotions
    applied_items = [
        i for i in items
        if i.get("check_category") == "promotion_application" and i["status"] == "passed"
    ]
    _append_section(lines, "Applied Promotions", applied_items)

    # Pending Manual Actions
    pending_items = [i for i in items if i["status"] == "pending"]
    _append_section(lines, "Pending Manual Actions", pending_items)

    # Validation Failures
    failed_items = [i for i in items if i["status"] == "failed"]
    _append_section(lines, "Validation Failures", failed_items)

    # Warnings
    warning_items = [i for i in items if i["status"] == "warning"]
    _append_section(lines, "Warnings", warning_items)

    # Active Blocking Rules (闭环)
    closure_items = [
        i for i in items if i.get("check_category") == "active_blocking_closure"
    ]
    _append_section(lines, "Active Blocking Rules", closure_items)

    # Rollback Readiness
    lines.append("## Rollback Readiness")
    lines.append("")
    rb_items = []
    for i in items:
        if i.get("check_category") == "active_blocking_closure":
            rid = i.get("rule_id", "")
            msg = i.get("message", "")
            if "回滚" in msg.lower():
                rb_items.append(f"- **{rid}**: 回滚计划缺失")
    for i in items:
        if i.get("check_category") == "promotion_application" and "active_to_blocking" in str(i.get("promotion_type", "")):
            rid = i.get("rule_id", "")
            msg = i.get("message", "")
            if "回滚" in msg.lower():
                rb_items.append(f"- **{rid}**: {_escape_md(msg)}")
    if rb_items:
        lines.extend(rb_items)
    else:
        lines.append("所有 active+blocking=true 规则回滚计划就绪（或无需检查）。")
    lines.append("")

    # Recommended Commands
    lines.append("## Recommended Commands")
    lines.append("")
    if r.get("recommended_commands"):
        for cmd in r["recommended_commands"]:
            lines.append(f"- `{cmd}`")
    else:
        lines.append("无。")
    lines.append("")

    # Safety Boundaries
    lines.append("## Safety Boundaries")
    lines.append("")
    lines.append("- 未自动修改 `docs/memory/memory_rules.yml`")
    lines.append("- 未自动修改 `docs/memory/经验复盘.md`")
    lines.append("- 未自动修改 `docs/memory/风险清单.md`")
    lines.append("- 未自动修改 `docs/memory/规则来源索引.md`")
    lines.append("- 未自动运行 `generate_rule_index.py`（除非 --run-checks）")
    lines.append("- 未自动晋升规则")
    lines.append("- 未读取 `_latest.*` 文件")
    lines.append("- 未调用真实 LLM")
    lines.append("")

    # Not Applied Automatically
    lines.append("## Not Applied Automatically")
    lines.append("")
    lines.append("- 所有输出标记为 `proposal_only`")
    lines.append("- 本报告仅供人工审查，不驱动任何自动修改")
    lines.append("")

    return "\n".join(lines)


def _append_section(
    lines: list[str],
    title: str,
    items: list[dict[str, Any]],
) -> None:
    """追加 validation item 表格章节。"""
    lines.extend([f"## {title}", ""])
    if not items:
        lines.extend(["无。", ""])
        return
    lines.append(
        "| rule_id | check_category | status | message | manual_action |"
    )
    lines.append("| --- | --- | --- | --- | --- |")
    for i in items:
        lines.append(
            f"| {i.get('rule_id', '?')} "
            f"| {i.get('check_category', '')} "
            f"| {i.get('status', '')} "
            f"| {_escape_md(str(i.get('message', '')))} "
            f"| {_escape_md(str(i.get('manual_action', '') or ''))} |"
        )
    lines.append("")


def _escape_md(value: str) -> str:
    """转义 Markdown 特殊字符。"""
    return value.replace("|", "\\|").replace("\n", " ")


# ---------------------------------------------------------------------------
# Snapshot 写入
# ---------------------------------------------------------------------------

def write_promotion_validation_snapshot(
    report: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Path]:
    """写入带 timestamp 的 snapshot 报告，不生成 latest 文件。"""
    r = render_promotion_validation_json(report)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    timestamp = _safe_timestamp(r["timestamp"])
    json_path = output / f"memory_promotion_validation_{timestamp}.json"
    markdown_path = output / f"memory_promotion_validation_{timestamp}.md"
    json_path.write_text(
        json.dumps(r, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_promotion_validation_markdown(report),
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
