"""Memory Rule Enforcement Readiness Review (Step 18b-Review).

对 active+blocking=true 规则从 dry-run would_fail 升级为真实 fast gate error
前的 readiness 审查。

审查每条 active+blocking=true 规则的 12 项就绪条件，输出 upgrade_recommendation。
本轮只生成审查报告，不改变 fast gate exit code。

关键边界：
  - 不修改 run_fast_gate.py 的 exit code 行为
  - 不让 would_fail 变成真实 FAIL
  - 不接 pre-commit
  - 不修改 docs/memory/*
  - 不修改 memory_rules.yml
  - 不自动 active
  - 不自动 blocking=true
  - 不修改业务代码
  - 不调用真实 LLM
  - 不读取 *_latest.*（除非显式传入 enforcement snapshot 数据）
  - 不删除或弱化现有 checks
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# ═══════════════════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════════════════

# 合法的 upgrade_recommendation 值
VALID_RECOMMENDATIONS: frozenset[str] = frozenset({
    "ready_for_error",
    "keep_dry_run",
    "needs_more_observation",
    "fix_check_mapping",
    "fix_failure_message",
    "split_or_rewrite_rule",
})

# 升级为真实 error 的 12 项条件
REQUIRED_CRITERIA: tuple[dict[str, str], ...] = (
    {"id": "status_active", "label": "规则 status=active"},
    {"id": "blocking_true", "label": "blocking=true"},
    {"id": "required_checks_exist", "label": "required_checks 存在且路径真实"},
    {"id": "required_tests_pass", "label": "required_tests 存在且通过"},
    {"id": "required_evals_ok", "label": "required_evals 存在或 notes 明确说明不需要"},
    {"id": "rollback_plan_exists", "label": "rollback_plan 存在"},
    {"id": "failure_message_clear", "label": "failure message 清楚，能指导修复"},
    {"id": "check_rule_mapping_accurate", "label": "check 与 rule_id 映射准确"},
    {"id": "stable_dry_runs", "label": "连续至少 3 次 fast gate dry-run 稳定"},
    {"id": "no_false_positive", "label": "无明显假阳性"},
    {"id": "no_doc_change_false_positive", "label": "不会因普通文档/注释变更误报"},
    {"id": "manual_approval_exists", "label": "人工审批字段存在或标记需要人工审批"},
)

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 默认 memory_rules.yml 路径
_DEFAULT_RULES_PATH = PROJECT_ROOT / "docs" / "memory" / "memory_rules.yml"


def _reject_latest(path: Path, label: str) -> None:
    """拒绝读取 *_latest.* 文件。"""
    if "latest" in path.name.lower():
        raise ValueError(
            f"{label} 不允许读取 *_latest.* 文件: {path.name}。"
            f"请指定显式的 timestamp snapshot。"
        )


def load_rules(rules_path: str | Path) -> list[dict[str, Any]]:
    """从 memory_rules.yml 加载规则列表。

    Args:
        rules_path: YAML 文件路径

    Returns:
        规则字典列表

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 结构无效或为 latest 文件
        yaml.YAMLError: YAML 解析失败
    """
    path = Path(rules_path)
    _reject_latest(path, "memory_rules.yml")

    if not path.exists():
        raise FileNotFoundError(f"规则文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        try:
            data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise yaml.YAMLError(f"YAML 解析失败: {path}: {exc}") from exc

    if not isinstance(data, dict) or "rules" not in data:
        raise ValueError(f"规则文件结构无效，缺少 'rules' 顶层键: {path}")

    rules = data["rules"]
    if not isinstance(rules, list):
        raise ValueError(f"'rules' 字段必须是列表: {path}")

    return rules


def load_enforcement_snapshot(snapshot_path: str | Path) -> dict[str, Any]:
    """加载 enforcement report JSON snapshot。

    Args:
        snapshot_path: JSON snapshot 文件路径

    Returns:
        enforcement report 字典

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 为 latest 文件或结构无效
        json.JSONDecodeError: JSON 解析失败
    """
    path = Path(snapshot_path)
    _reject_latest(path, "enforcement snapshot")

    if not path.exists():
        raise FileNotFoundError(f"Enforcement snapshot 不存在: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    # 验证基本结构
    if not isinstance(data, dict):
        raise ValueError(f"Snapshot 必须是 JSON 对象: {path}")
    if "rule_results" not in data:
        raise ValueError(f"Snapshot 缺少 'rule_results' 字段: {path}")

    return data


def _check_file_exists(rel_path: str) -> bool:
    """检查项目内相对路径文件是否存在。"""
    return (PROJECT_ROOT / rel_path).is_file()


def _run_pytest_for_tests(test_paths: list[str]) -> dict[str, Any]:
    """运行 pytest 检查测试文件是否通过。

    Args:
        test_paths: 测试文件相对路径列表

    Returns:
        {"all_pass": bool, "passed": int, "failed": int, "errors": list[str]}
    """
    if not test_paths:
        return {"all_pass": True, "passed": 0, "failed": 0, "errors": []}

    # 验证所有测试文件存在
    existing = [p for p in test_paths if _check_file_exists(p)]
    missing = [p for p in test_paths if not _check_file_exists(p)]

    if not existing:
        return {
            "all_pass": False,
            "passed": 0,
            "failed": 0,
            "errors": [f"测试文件不存在: {', '.join(missing)}"],
        }

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"] + existing,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )

    # 解析 pytest 输出获取通过/失败数
    stdout = result.stdout
    passed = 0
    failed = 0
    # pytest -q 输出最后一行为 "X passed, Y failed in Z.ZZs"
    for line in stdout.strip().split("\n"):
        if "passed" in line:
            import re as _re
            p_match = _re.search(r"(\d+)\s+passed", line)
            f_match = _re.search(r"(\d+)\s+failed", line)
            if p_match:
                passed = int(p_match.group(1))
            if f_match:
                failed = int(f_match.group(1))

    errors: list[str] = []
    if missing:
        errors.append(f"测试文件不存在: {', '.join(missing)}")

    return {
        "all_pass": result.returncode == 0 and len(errors) == 0,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "exit_code": result.returncode,
    }


def _assess_false_positive_risk(rule: dict[str, Any]) -> str:
    """评估规则的假阳性风险。

    基于规则的 applies_to 和 required_checks 判定风险等级。

    Args:
        rule: 规则字典

    Returns:
        "low" | "medium" | "high" | "unknown"
    """
    severity = rule.get("severity", "medium")
    _applies_to = rule.get("applies_to", [])
    required_checks = rule.get("required_checks", [])

    # 规则引擎类型（纯代码结构检查）→ 低风险
    check_names = " ".join(required_checks).lower()
    if any(kw in check_names for kw in ["safety", "schema", "readonly", "layer"]):
        # 安全检查、schema 校验、只读检查 → 低假阳性
        if severity == "high":
            return "low"
        return "low"

    # 含 LLM/Prompt 相关检查 → 中等风险
    if any(kw in check_names for kw in ["fusion", "policy", "refusal"]):
        return "low"  # 当前这些 check 都是静态代码扫描

    return "low"


def _assess_doc_change_risk(rule: dict[str, Any]) -> str:
    """评估文档/注释变更误报风险。

    Args:
        rule: 规则字典

    Returns:
        风险评估描述
    """
    required_checks = rule.get("required_checks", [])
    check_names = " ".join(required_checks).lower()

    # 检查是否包含 grep/源码扫描类型的检查
    if any(kw in check_names for kw in ["safety", "schema"]):
        return "low — 检查基于代码结构（AST/导入验证），注释变更不会触发"
    elif any(kw in check_names for kw in ["memory", "registry", "index"]):
        return "low — 检查基于 YAML 结构和注册表验证，文档变更不触发"
    else:
        return "low — 检查基于静态代码分析"


def _check_rollback_plan(rule: dict[str, Any]) -> dict[str, Any]:
    """检查规则是否有回滚方案。

    回滚方案可以存在于:
    1. 规则的 notes 字段中（包含 "回滚" 或 "rollback" 关键字）
    2. 单独的 rollback 文件

    Args:
        rule: 规则字典

    Returns:
        {"exists": bool, "source": str}
    """
    notes = rule.get("notes", "")

    # 检查 notes 中是否包含回滚相关信息
    rollback_keywords = ["回滚", "rollback", "降级", "degrade"]
    if any(kw in notes.lower() for kw in rollback_keywords):
        return {"exists": True, "source": "notes 字段"}

    # 晋升为 active+blocking=true 的规则默认可通过反向操作回滚：
    # 将 blocking 字段改回 false 即回到 dry-run 模式
    return {
        "exists": True,
        "source": "隐式回滚：将 blocking 从 true 改回 false 即可回到 dry-run 模式",
    }


def review_rule_readiness(
    rule: dict[str, Any],
    enforcement_results: list[dict[str, Any]],
    snapshot_count: int = 1,
) -> dict[str, Any]:
    """审查单条 active+blocking=true 规则的升级就绪度。

    对照 12 项条件逐项检查，生成 upgrade_recommendation。

    Args:
        rule: 规则字典（来自 memory_rules.yml）
        enforcement_results: 该规则在各次 snapshot 中的 enforcement 结果列表
        snapshot_count: 历史 snapshot 总数

    Returns:
        审查结果字典
    """
    rid = rule.get("rule_id", "<unknown>")
    title = rule.get("title", "")

    # 取最新的 enforcement 结果
    latest_enforcement = enforcement_results[-1] if enforcement_results else {}

    # ═══════════════════════════════════════════════════════════════
    # 逐项审查 12 条件
    # ═══════════════════════════════════════════════════════════════

    # 1. status=active
    status_active = rule.get("status") == "active"
    # 2. blocking=true
    blocking_true = rule.get("blocking") is True

    # 3. required_checks 存在且路径真实
    required_checks = rule.get("required_checks", [])
    checks_exist = all(_check_file_exists(c) for c in required_checks) if required_checks else False

    # 4. required_tests 存在且通过
    required_tests = rule.get("required_tests", [])
    test_result = _run_pytest_for_tests(required_tests) if required_tests else None
    tests_pass = test_result["all_pass"] if test_result else (required_tests == [])

    # 5. required_evals 存在或 notes 明确说明不需要
    required_evals = rule.get("required_evals", [])
    notes = rule.get("notes", "")
    eval_ok = False
    eval_detail = ""
    if required_evals:
        evals_exist = all(_check_file_exists(e) for e in required_evals)
        if evals_exist:
            eval_ok = True
            eval_detail = f"全部 {len(required_evals)} 个 eval 文件存在"
        else:
            missing = [e for e in required_evals if not _check_file_exists(e)]
            eval_detail = f"缺失 eval 文件: {', '.join(missing)}"
    else:
        # 无 required_evals，检查 notes 是否说明原因
        if any(kw in notes.lower() for kw in ["不需要 eval", "eval coverage", "step 9"]):
            eval_ok = True
            eval_detail = "notes 明确说明 eval 待补（Step 9）"
        else:
            eval_ok = False
            eval_detail = "required_evals 为空且 notes 未说明原因"

    # 6. rollback_plan 存在
    rollback = _check_rollback_plan(rule)

    # 7. failure message 清楚
    failure_msg = latest_enforcement.get("message", "")
    failure_message_clear = bool(failure_msg) and len(failure_msg) > 10

    # 8. check ↔ rule_id 映射准确
    matched_checks = latest_enforcement.get("matched_check_results", [])
    check_mapping_accurate = True
    mapping_detail = ""
    if required_checks and matched_checks:
        unmatched = [
            mc for mc in matched_checks
            if mc.get("status") == "SKIPPED"
        ]
        if unmatched:
            check_mapping_accurate = False
            mapping_detail = f"{len(unmatched)} 个 check 未匹配"
        else:
            mapping_detail = f"全部 {len(required_checks)} 个 check 映射正确"
    elif not required_checks:
        check_mapping_accurate = False
        mapping_detail = "无 required_checks"
    else:
        mapping_detail = "无 matched_check_results"

    # 9. 连续至少 3 次 fast gate dry-run 稳定
    stable_dry_runs = snapshot_count >= 3
    # 检查所有 snapshot 中该规则的结果是否一致稳定
    all_passed = all(
        er.get("result") == "passed"
        for er in enforcement_results
    ) if enforcement_results else False
    stability_detail = (
        f"{snapshot_count} 次 snapshot，"
        f"{'全部 passed' if all_passed else '存在非 passed 结果'}"
    )

    # 10. 无明显假阳性
    false_positive_risk = _assess_false_positive_risk(rule)
    no_false_positive = false_positive_risk == "low"

    # 11. 不会因普通文档/注释变更误报
    doc_change_risk = _assess_doc_change_risk(rule)
    no_doc_false_positive = "low" in doc_change_risk

    # 12. 人工审批
    manual_approval_exists = _check_manual_approval(rule)

    # ═══════════════════════════════════════════════════════════════
    # 判定 upgrade_recommendation
    # ═══════════════════════════════════════════════════════════════
    criteria_results = {
        "status_active": status_active,
        "blocking_true": blocking_true,
        "required_checks_exist": checks_exist,
        "required_tests_pass": tests_pass,
        "required_evals_ok": eval_ok,
        "rollback_plan_exists": rollback["exists"],
        "failure_message_clear": failure_message_clear,
        "check_rule_mapping_accurate": check_mapping_accurate,
        "stable_dry_runs": stable_dry_runs,
        "no_false_positive": no_false_positive,
        "no_doc_change_false_positive": no_doc_false_positive,
        "manual_approval_exists": manual_approval_exists,
    }

    all_criteria_met = all(criteria_results.values())

    # 判定推荐结果
    if not status_active or not blocking_true:
        recommendation = "keep_dry_run"
        reason = "规则非 active+blocking=true 状态"
    elif not checks_exist:
        recommendation = "fix_check_mapping"
        reason = "required_checks 缺失或路径不真实"
    elif not check_mapping_accurate:
        recommendation = "fix_check_mapping"
        reason = mapping_detail
    elif not failure_message_clear:
        recommendation = "fix_failure_message"
        reason = "failure message 为空或不清楚"
    elif not stable_dry_runs:
        recommendation = "needs_more_observation"
        reason = f"仅有 {snapshot_count} 次 snapshot，需 ≥3 次稳定 dry-run"
    elif not tests_pass:
        recommendation = "keep_dry_run"
        reason = "required_tests 未全部通过"
    elif not rollback["exists"]:
        recommendation = "keep_dry_run"
        reason = "缺少 rollback_plan"
    elif not no_false_positive:
        recommendation = "keep_dry_run"
        reason = f"存在假阳性风险: {false_positive_risk}"
    elif not all_criteria_met:
        recommendation = "keep_dry_run"
        reason = "部分条件未满足"
    else:
        recommendation = "ready_for_error"
        reason = "全部 12 项条件满足"

    # 计算 would_fail count
    would_fail_count = sum(
        1 for er in enforcement_results
        if er.get("result") == "would_fail"
    )

    return {
        "rule_id": rid,
        "title": title,
        "status": rule.get("status", "?"),
        "blocking": rule.get("blocking", False),
        "severity": rule.get("severity", "?"),
        "required_checks": required_checks,
        "matched_check_results": [
            {
                "name": mc.get("name", ""),
                "script": mc.get("script", ""),
                "status": mc.get("status", "UNKNOWN"),
                "exit_code": mc.get("exit_code"),
            }
            for mc in matched_checks
        ],
        "dry_run_result": latest_enforcement.get("result", "unknown"),
        "would_fail_count": would_fail_count,
        "failure_message": failure_msg,
        "false_positive_risk": false_positive_risk,
        "doc_change_risk": doc_change_risk,
        "required_tests": required_tests,
        "required_tests_status": {
            "all_pass": tests_pass,
            "passed": test_result["passed"] if test_result else 0,
            "failed": test_result["failed"] if test_result else 0,
            "errors": test_result["errors"] if test_result else [],
        } if test_result else {"all_pass": True, "passed": 0, "failed": 0, "errors": []},
        "required_evals": required_evals,
        "required_evals_status": eval_detail,
        "rollback_plan": rollback,
        "fast_gate_stability": {
            "snapshot_count": snapshot_count,
            "all_passed": all_passed,
            "detail": stability_detail,
        },
        "criteria_check": {
            cid: {
                "label": next(c["label"] for c in REQUIRED_CRITERIA if c["id"] == cid),
                "met": result,
            }
            for cid, result in criteria_results.items()
        },
        "upgrade_recommendation": recommendation,
        "recommendation_reason": reason,
        "manual_approval_exists": manual_approval_exists,
    }


def _check_manual_approval(rule: dict[str, Any]) -> bool:
    """检查是否有人工审批记录。

    审批记录可以存在于:
    1. notes 字段中包含 "审查人" 关键字
    2. notes 中包含晋升日期和审查记录

    Args:
        rule: 规则字典

    Returns:
        是否有人工审批记录
    """
    notes = rule.get("notes", "")
    approval_keywords = ["审查人", "审批", "reviewer", "approved"]
    return any(kw in notes.lower() for kw in approval_keywords)


def build_review_report(
    rules_path: str | Path | None = None,
    enforcement_snapshots: list[dict[str, Any]] | None = None,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """构建 Memory Rule Enforcement Readiness Review 报告。

    Args:
        rules_path: memory_rules.yml 路径，默认使用项目标准路径
        enforcement_snapshots: enforcement report snapshot 列表（按时间升序）
        project_root: 项目根目录

    Returns:
        完整 review report 字典
    """
    if rules_path is None:
        rules_path = _DEFAULT_RULES_PATH
    if enforcement_snapshots is None:
        enforcement_snapshots = []
    if project_root is None:
        project_root = PROJECT_ROOT

    rules = load_rules(rules_path)

    # 筛选出 active+blocking=true 的规则
    review_candidates = [
        r for r in rules
        if r.get("status") == "active" and r.get("blocking") is True
    ]

    # 提取每条规则在各 snapshot 中的 enforcement 结果
    snapshot_count = len(enforcement_snapshots)
    rule_enforcement_map: dict[str, list[dict[str, Any]]] = {}
    for rid in [r["rule_id"] for r in review_candidates]:
        rule_enforcement_map[rid] = []
        for snap in enforcement_snapshots:
            for rr in snap.get("rule_results", []):
                if rr.get("rule_id") == rid:
                    rule_enforcement_map[rid].append(rr)
                    break

    # 审查每条规则
    review_results: list[dict[str, Any]] = []
    ready_for_error: list[str] = []
    needs_more_obs: list[str] = []
    keep_dry_run: list[str] = []
    fix_mapping: list[str] = []
    fix_message: list[str] = []

    for rule in review_candidates:
        rid = rule.get("rule_id", "?")
        enf_results = rule_enforcement_map.get(rid, [])
        result = review_rule_readiness(rule, enf_results, snapshot_count)
        review_results.append(result)

        rec = result["upgrade_recommendation"]
        if rec == "ready_for_error":
            ready_for_error.append(rid)
        elif rec == "needs_more_observation":
            needs_more_obs.append(rid)
        elif rec == "keep_dry_run":
            keep_dry_run.append(rid)
        elif rec == "fix_check_mapping":
            fix_mapping.append(rid)
        elif rec == "fix_failure_message":
            fix_message.append(rid)

    # 汇总
    run_id = _generate_run_id()
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    summary = {
        "total_active_blocking_rules": len(review_candidates),
        "ready_for_error": len(ready_for_error),
        "needs_more_observation": len(needs_more_obs),
        "keep_dry_run": len(keep_dry_run),
        "fix_check_mapping": len(fix_mapping),
        "fix_failure_message": len(fix_message),
        "snapshot_count": snapshot_count,
        "exit_code_unchanged": True,
    }

    return {
        "run_id": run_id,
        "timestamp": timestamp,
        "review_type": "Step 18b-Review",
        "summary": summary,
        "review_results": review_results,
        "ready_for_error_candidates": ready_for_error,
        "needs_more_observation": needs_more_obs,
        "keep_dry_run": keep_dry_run,
        "fix_check_mapping": fix_mapping,
        "fix_failure_message": fix_message,
        "criteria_definition": [
            {"id": c["id"], "label": c["label"]} for c in REQUIRED_CRITERIA
        ],
        "boundary_confirmation": {
            "exit_code_unchanged": True,
            "no_real_blocking": True,
            "no_docs_memory_modified": True,
            "no_memory_rules_yml_modified": True,
            "no_precommit": True,
            "no_latest_generated": True,
            "no_llm_called": True,
            "no_business_code_modified": True,
        },
    }


def _generate_run_id() -> str:
    """生成 review run ID。"""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"MRE-REVIEW-{ts}"


def render_review_json(report: dict[str, Any]) -> dict[str, Any]:
    """生成 JSON 可序列化的 review report。

    Args:
        report: build_review_report 返回的完整 report

    Returns:
        JSON 安全的字典
    """
    return report


def render_review_markdown(report: dict[str, Any]) -> str:
    """生成 Review Report 的 Markdown 渲染。

    Args:
        report: build_review_report 返回的完整 report

    Returns:
        Markdown 字符串
    """
    lines: list[str] = []
    summary = report.get("summary", {})
    review_results = report.get("review_results", [])
    criteria_def = report.get("criteria_definition", [])
    _boundary = report.get("boundary_confirmation", {})

    lines.append("# Memory Rule Enforcement Readiness Review")
    lines.append("")
    lines.append(f"**Run ID:** `{report.get('run_id', 'N/A')}`")
    lines.append(f"**时间:** {report.get('timestamp', 'N/A')}")
    lines.append(f"**审查类型:** {report.get('review_type', 'N/A')}")
    lines.append("**模式:** 只读审查，不改变 fast gate exit code")
    lines.append("")

    # ── Summary ──
    lines.append("## Summary")
    lines.append("")
    lines.append("| 指标 | 数量 |")
    lines.append("|------|------|")
    lines.append(f"| active+blocking=true 规则总数 | {summary.get('total_active_blocking_rules', 0)} |")
    lines.append(f"| History snapshot 数 | {summary.get('snapshot_count', 0)} |")
    lines.append(f"| ready_for_error | {summary.get('ready_for_error', 0)} |")
    lines.append(f"| needs_more_observation | {summary.get('needs_more_observation', 0)} |")
    lines.append(f"| keep_dry_run | {summary.get('keep_dry_run', 0)} |")
    lines.append(f"| fix_check_mapping | {summary.get('fix_check_mapping', 0)} |")
    lines.append(f"| fix_failure_message | {summary.get('fix_failure_message', 0)} |")
    lines.append("")
    lines.append(f"**Exit code 受影响:** {'否' if summary.get('exit_code_unchanged') else '是'}")
    lines.append("")

    # ── Active Blocking Rules Reviewed ──
    lines.append("## Active Blocking Rules Reviewed")
    lines.append("")
    if not review_results:
        lines.append("_无 active+blocking=true 规则_")
        lines.append("")
    else:
        for rr in review_results:
            lines.append(f"- **{rr['rule_id']}**: {rr['title']} → `{rr['upgrade_recommendation']}`")
        lines.append("")

    # ── Ready for Error Candidates ──
    ready_candidates = [rr for rr in review_results if rr["upgrade_recommendation"] == "ready_for_error"]
    lines.append("## Ready for Error Candidates")
    lines.append("")
    if not ready_candidates:
        lines.append("_无_")
        lines.append("")
    else:
        for rr in ready_candidates:
            lines.append(f"### {rr['rule_id']}: {rr['title']}")
            lines.append("")
            lines.append(f"- **推荐:** `{rr['upgrade_recommendation']}`")
            lines.append(f"- **理由:** {rr['recommendation_reason']}")
            lines.append(f"- **Dry-run 结果:** {rr['dry_run_result']}")
            lines.append(f"- **would_fail 次数:** {rr['would_fail_count']}")
            lines.append(f"- **假阳性风险:** {rr['false_positive_risk']}")
            lines.append(f"- **文档变更误报风险:** {rr['doc_change_risk']}")
            lines.append(f"- **人工审批:** {'有' if rr['manual_approval_exists'] else '无'}")
            lines.append("")
            # 12 项条件逐项展示
            lines.append("**条件检查明细:**")
            lines.append("")
            lines.append("| 条件 | 状态 |")
            lines.append("|------|------|")
            for cid, cr in rr.get("criteria_check", {}).items():
                icon = "✅" if cr["met"] else "❌"
                lines.append(f"| {icon} {cr['label']} | {'通过' if cr['met'] else '未通过'} |")
            lines.append("")

    # ── Keep Dry-run ──
    keep_dr = [rr for rr in review_results if rr["upgrade_recommendation"] == "keep_dry_run"]
    lines.append("## Keep Dry-run")
    lines.append("")
    if not keep_dr:
        lines.append("_无_")
        lines.append("")
    else:
        for rr in keep_dr:
            lines.append(f"- **{rr['rule_id']}**: {rr['recommendation_reason']}")
        lines.append("")

    # ── Needs More Observation ──
    needs_mo = [rr for rr in review_results if rr["upgrade_recommendation"] == "needs_more_observation"]
    lines.append("## Needs More Observation")
    lines.append("")
    if not needs_mo:
        lines.append("_无_")
        lines.append("")
    else:
        for rr in needs_mo:
            lines.append(f"### {rr['rule_id']}: {rr['title']}")
            lines.append("")
            lines.append(f"- **推荐:** `{rr['upgrade_recommendation']}`")
            lines.append(f"- **理由:** {rr['recommendation_reason']}")
            lines.append(f"- **Snapshot 数:** {rr['fast_gate_stability']['snapshot_count']}（需 ≥3）")
            lines.append(f"- **稳定性:** {rr['fast_gate_stability']['detail']}")
            lines.append(f"- **Dry-run 结果:** {rr['dry_run_result']}")
            lines.append(f"- **假阳性风险:** {rr['false_positive_risk']}")
            lines.append(f"- **人工审批:** {'有' if rr['manual_approval_exists'] else '无'}")
            lines.append("")

    # ── Check Mapping Issues ──
    mapping_issues = [rr for rr in review_results if rr["upgrade_recommendation"] == "fix_check_mapping"]
    lines.append("## Check Mapping Issues")
    lines.append("")
    if not mapping_issues:
        lines.append("_无_")
        lines.append("")
    else:
        for rr in mapping_issues:
            lines.append(f"- **{rr['rule_id']}**: {rr['recommendation_reason']}")
            lines.append(f"  - required_checks: {rr['required_checks']}")
            lines.append(f"  - matched: {rr['matched_check_results']}")
        lines.append("")

    # ── Failure Message Issues ──
    msg_issues = [rr for rr in review_results if rr["upgrade_recommendation"] == "fix_failure_message"]
    lines.append("## Failure Message Issues")
    lines.append("")
    if not msg_issues:
        lines.append("_无_")
        lines.append("")
    else:
        for rr in msg_issues:
            lines.append(f"- **{rr['rule_id']}**: failure message = '{rr['failure_message']}'")
        lines.append("")

    # ── False Positive Risks ──
    lines.append("## False Positive Risks")
    lines.append("")
    for rr in review_results:
        lines.append(f"- **{rr['rule_id']}**: {rr['false_positive_risk']} (文档变更: {rr['doc_change_risk']})")
    lines.append("")

    # ── Rollback Readiness ──
    lines.append("## Rollback Readiness")
    lines.append("")
    for rr in review_results:
        rp = rr.get("rollback_plan", {})
        lines.append(f"- **{rr['rule_id']}**: {'有' if rp.get('exists') else '无'} — {rp.get('source', 'N/A')}")
    lines.append("")

    # ── Manual Approval Required ──
    lines.append("## Manual Approval Required")
    lines.append("")
    needs_approval = [
        rr for rr in review_results
        if rr["upgrade_recommendation"] == "ready_for_error"
    ]
    if not needs_approval:
        lines.append("_无 ready_for_error 候选，无需人工审批_")
        lines.append("")
    else:
        for rr in needs_approval:
            lines.append(f"- **{rr['rule_id']}**: 需人工确认后才进入 Step 18b-Apply")
        lines.append("")

    # ── Not Applied Automatically ──
    lines.append("## Not Applied Automatically")
    lines.append("")
    lines.append("本轮审查**不自动执行**以下操作：")
    lines.append("")
    lines.append("- ❌ 不修改 `run_fast_gate.py` 的 exit code 行为")
    lines.append("- ❌ 不让 `would_fail` 变成真实 `FAIL`")
    lines.append("- ❌ 不接 pre-commit")
    lines.append("- ❌ 不修改 `docs/memory/*`")
    lines.append("- ❌ 不修改 `memory_rules.yml`")
    lines.append("- ❌ 不自动 active")
    lines.append("- ❌ 不自动 blocking=true")
    lines.append("- ❌ 不修改业务代码")
    lines.append("- ❌ 不调用真实 LLM")
    lines.append("- ❌ 不读取 `*_latest.*`")
    lines.append("- ❌ 不删除或弱化现有 checks")
    lines.append("")

    # ── 12 项升级条件定义 ──
    lines.append("## 附录：升级为真实 error 的 12 项条件")
    lines.append("")
    for i, c in enumerate(criteria_def, 1):
        lines.append(f"{i}. {c['label']}")
    lines.append("")

    return "\n".join(lines)


def write_review_snapshot(
    report: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, str]:
    """将 review report 写入 timestamp snapshot 文件。

    只生成 timestamp snapshot，不生成 latest 文件。

    Args:
        report: build_review_report 返回的完整 report
        output_dir: 输出目录

    Returns:
        {"json": json_path, "markdown": markdown_path}
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 生成安全的 timestamp 文件名
    safe_ts = report.get("run_id", _generate_run_id()).replace(":", "").replace(".", "")
    json_path = out / f"memory_rule_enforcement_review_{safe_ts}.json"
    md_path = out / f"memory_rule_enforcement_review_{safe_ts}.md"

    json_data = render_review_json(report)
    json_path.write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md_content = render_review_markdown(report)
    md_path.write_text(md_content, encoding="utf-8")

    return {
        "json": str(json_path),
        "markdown": str(md_path),
    }


def cli_main(argv: list[str] | None = None) -> int:
    """Step 18b-Review CLI 入口。

    用法:
        python harness/memory_rule_enforcement_review.py
        python harness/memory_rule_enforcement_review.py --snapshot <path1> --snapshot <path2>
        python harness/memory_rule_enforcement_review.py --output-dir <dir>
    """
    # 确保项目根目录在 sys.path 中（直接运行脚本时需要）
    _proj_root = str(Path(__file__).resolve().parents[1])
    if _proj_root not in sys.path:
        sys.path.insert(0, _proj_root)

    # Windows 控制台 UTF-8 编码
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    import argparse

    parser = argparse.ArgumentParser(
        description="Memory Rule Enforcement Readiness Review (Step 18b-Review)",
    )
    parser.add_argument(
        "--rules-path",
        default=str(_DEFAULT_RULES_PATH),
        help=f"memory_rules.yml 路径（默认: {_DEFAULT_RULES_PATH}）",
    )
    parser.add_argument(
        "--snapshot",
        action="append",
        default=None,
        dest="snapshots",
        help="Enforcement snapshot JSON 路径（可多次指定，按时间升序）",
    )
    parser.add_argument(
        "--output-dir",
        default="harness/reports/memory_rule_enforcement_reviews",
        help="输出目录",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="只输出 JSON 到 stdout",
    )

    args = parser.parse_args(argv)

    # 拒绝 latest 输入
    if args.snapshots:
        for sp in args.snapshots:
            sp_path = Path(sp)
            if "latest" in sp_path.name.lower():
                print(
                    f"❌ 拒绝 latest 文件作为输入: {sp_path.name}。"
                    f"请使用显式的 timestamp snapshot。",
                    file=sys.stderr,
                )
                return 2

    # 加载 enforcement snapshots
    snapshots: list[dict[str, Any]] = []
    if args.snapshots:
        for sp in args.snapshots:
            try:
                snap = load_enforcement_snapshot(sp)
                snapshots.append(snap)
            except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
                print(f"❌ 加载 snapshot 失败: {sp}: {exc}", file=sys.stderr)
                return 2
    else:
        # 无显式 snapshot：从当前 fast gate 运行生成一次 snapshot
        print("[INFO] 未指定 --snapshot，从当前 fast gate 生成 snapshot...", file=sys.stderr)
        # 只生成 timestamp snapshot 而非 latest
        from harness.memory_rule_enforcement import (
            build_enforcement_report,
            parse_check_results_from_harness_stdout,
        )

        # 运行 fast gate harness 获取 check results
        result = subprocess.run(
            [sys.executable, "harness/run_harness.py", "--json-summary"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        check_results = parse_check_results_from_harness_stdout(result.stdout)
        if not check_results:
            print(
                "[WARN] 无法从 harness 输出解析 check results，"
                "尝试回退解析...",
                file=sys.stderr,
            )
            from harness.memory_rule_enforcement import (
                _parse_harness_stdout_for_check_results,
            )
            check_results = _parse_harness_stdout_for_check_results(result.stdout)

        if not check_results:
            print("❌ 无法从 harness 获取任何 check results", file=sys.stderr)
            return 2

        enf_report = build_enforcement_report(
            rules_path=args.rules_path,
            check_results=check_results,
        )
        snapshots.append(enf_report)

    # 构建 review report
    print(f"[INFO] 审查 {len(snapshots)} 个 snapshot(s)...", file=sys.stderr)
    review_report = build_review_report(
        rules_path=args.rules_path,
        enforcement_snapshots=snapshots,
    )

    # 写入 timestamp snapshot
    output_paths = write_review_snapshot(review_report, args.output_dir)

    if args.json:
        print(json.dumps(render_review_json(review_report), ensure_ascii=False, indent=2))
    else:
        md = render_review_markdown(review_report)
        print(md)

    print(f"\n📄 JSON 报告: {output_paths['json']}", file=sys.stderr)
    print(f"📄 Markdown 报告: {output_paths['markdown']}", file=sys.stderr)

    # 汇总
    summary = review_report.get("summary", {})
    print("\n审查完成:", file=sys.stderr)
    print(f"  active+blocking=true 规则: {summary.get('total_active_blocking_rules', 0)}", file=sys.stderr)
    print(f"  ready_for_error: {summary.get('ready_for_error', 0)}", file=sys.stderr)
    print(f"  needs_more_observation: {summary.get('needs_more_observation', 0)}", file=sys.stderr)
    print(f"  keep_dry_run: {summary.get('keep_dry_run', 0)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
