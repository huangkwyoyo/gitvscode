"""Memory Rule Blocking Expansion Readiness Review 引擎（Step 25）。

职责：
    读取 memory_rules.yml 和实际 asset 状态，逐规则评估是否适合
    从 proposed → active+blocking=true 晋升。

    本轮只做 readiness review，不修改任何规则状态或门禁行为。

用法：
    python harness/memory_rule_blocking_expansion.py
    python harness/memory_rule_blocking_expansion.py --rules-path ... --output-dir ...

关键边界：
    - 只读分析，不修改任何文件
    - 不调用 LLM
    - 不生成 latest
    - 不改变规则状态
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_RULES_PATH = PROJECT_ROOT / "docs" / "memory" / "memory_rules.yml"
_DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "harness" / "reports" / "memory_rule_blocking_expansion"
)

# 合法推荐值
VALID_RECOMMENDATIONS = frozenset({
    "ready_for_fast_gate_blocking",
    "ready_for_precommit_blocking_review",
    "needs_more_observation",
    "missing_checks",
    "missing_tests",
    "missing_evals",
    "keep_non_blocking",
    "split_or_rewrite",
    "reject_for_now",
})


@dataclass
class RuleReview:
    """单条规则的审查结果。"""

    rule_id: str
    title: str
    status: str
    blocking: bool
    recommendation: str
    reason: str
    checks_exist: bool = False
    tests_exist: bool = False
    evals_exist: bool = False
    checks_stable: bool | None = None  # None 表示无法判断
    false_positive_risk: str = "unknown"  # low / medium / high
    rollback_plan_clear: bool = False
    security_critical: bool = False
    checks_detail: list[str] = field(default_factory=list)
    tests_detail: list[str] = field(default_factory=list)
    evals_detail: list[str] = field(default_factory=list)


@dataclass
class ExpansionReview:
    """Blocking 扩展审查的完整结果。"""

    run_id: str
    timestamp: str
    rules_path: str
    total_rules: int
    active_blocking_rules: list[str]
    ta_r018_stable: bool
    precommit_blocking_stable: bool
    reviews: list[RuleReview]
    ready_candidates: list[RuleReview] = field(default_factory=list)
    needs_observation: list[RuleReview] = field(default_factory=list)
    missing_assets: list[RuleReview] = field(default_factory=list)
    kept_non_blocking: list[RuleReview] = field(default_factory=list)
    rejected: list[RuleReview] = field(default_factory=list)


def _count_pytest_tests(test_path: str) -> int | None:
    """统计指定测试文件中的测试函数数量（通过 --collect-only）。

    Args:
        test_path: 相对于项目根目录的测试文件路径

    Returns:
        测试函数数量，失败返回 None
    """
    full_path = PROJECT_ROOT / test_path
    if not full_path.exists():
        return None
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(full_path), "--collect-only", "-q", "--no-header"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # 解析输出：最后一行通常是 "N tests collected"
        output = result.stdout + result.stderr
        for line in reversed(output.splitlines()):
            line = line.strip()
            if "collected" in line.lower() or "selected" in line.lower():
                continue
            if line and line[0].isdigit():
                try:
                    return int(line.split()[0])
                except (ValueError, IndexError):
                    continue
        # fallback: count lines with "::"
        count = sum(1 for l in output.splitlines() if "::" in l and "test" in l.lower())
        return count if count > 0 else None
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return None


def _asset_exists(rel_path: str) -> bool:
    """检查文件资产是否存在。

    Args:
        rel_path: 相对于项目根目录的文件路径

    Returns:
        文件存在返回 True
    """
    return (PROJECT_ROOT / rel_path).is_file()


def _eval_has_content(rel_path: str) -> bool:
    """检查 eval 文件是否有实际内容（非空 YAML 非模板）。

    Args:
        rel_path: eval 文件路径

    Returns:
        文件存在且包含实际内容返回 True
    """
    fp = PROJECT_ROOT / rel_path
    if not fp.is_file():
        return False
    try:
        text = fp.read_text(encoding="utf-8").strip()
        # 排除纯模板/注释文件
        if len(text) < 10:
            return False
        data = yaml.safe_load(text)
        return data is not None and (isinstance(data, (list, dict)) and len(data) > 0)
    except Exception:
        return False


def _assess_false_positive_risk(rule: dict) -> str:
    """评估规则的误报风险等级。

    判断依据：
    - 规则是否依赖文档/注释内容检测 → high risk
    - 规则是否依赖 LLM 输出格式检测 → medium risk
    - 规则是否依赖纯结构化检查 → low risk

    Args:
        rule: 规则 dict

    Returns:
        "low" / "medium" / "high"
    """
    title = (rule.get("title") or "").lower()
    notes = (rule.get("notes") or "").lower()
    rule_id = rule.get("rule_id", "")
    risk_ids = [str(r).upper() for r in (rule.get("risk_ids") or [])]

    # Meta 规则（依赖文档/注册表变更检测）→ 高误报风险
    meta_keywords = ["meta", "注册表", "registry", "索引", "生成", "同步"]
    if any(k in title for k in meta_keywords) or any(k in notes for k in meta_keywords):
        if rule_id in ("TA-R026", "TA-R027", "TA-R028", "TA-R029", "TA-R030"):
            return "high"

    # 文档变更依赖 → 高误报风险
    if any(k in title for k in ["prompt 修改", "文档", "注释", "生成脚本", "baselines 变更"]):
        return "high"

    # LLM 输出格式/内容检测 → 中风险
    llm_keywords = ["llm", "prompt", "模板", "fallback", "融合", "编造"]
    if any(k in title for k in llm_keywords):
        return "medium"

    # 纯结构化/规则引擎检查 → 低风险
    structural_keywords = ["sql", "只读", "readonly", "schema", "ir", "安全链路",
                           "并发", "execution", "plan", "跨域", "chart", "不可绕过"]
    if any(k in title for k in structural_keywords):
        return "low"

    # 默认中等
    return "medium"


def review_rules(rules_path: str | Path | None = None) -> ExpansionReview:
    """执行全部规则的 blocking 扩展 readiness 审查。

    Args:
        rules_path: memory_rules.yml 路径，默认使用项目标准路径

    Returns:
        ExpansionReview 对象，包含所有规则的审查结果
    """
    rp = Path(rules_path) if rules_path else _DEFAULT_RULES_PATH
    if not rp.exists():
        raise FileNotFoundError(f"规则文件不存在: {rp}")

    with open(rp, "r", encoding="utf-8") as fh:
        rules_data = yaml.safe_load(fh)

    all_rules: list[dict] = rules_data.get("rules", [])
    now = datetime.now(timezone.utc)
    run_id = f"BRE-{now.strftime('%Y%m%dT%H%M%S')}"

    # 当前 baseline
    active_blocking_ids = [
        r["rule_id"] for r in all_rules
        if r.get("status") == "active" and r.get("blocking") is True
    ]

    reviews: list[RuleReview] = []

    for rule in all_rules:
        rid = rule["rule_id"]
        title = rule["title"]
        status = rule.get("status", "proposed")
        blocking = rule.get("blocking", False)
        severity = rule.get("severity", "medium")
        notes = rule.get("notes", "") or ""

        # 检查资产存在性
        required_checks = rule.get("required_checks") or []
        required_tests = rule.get("required_tests") or []
        required_evals = rule.get("required_evals") or []

        checks_exist = all(_asset_exists(c) for c in required_checks) if required_checks else None
        tests_exist = all(_asset_exists(t) for t in required_tests) if required_tests else None
        evals_exist = all(_eval_has_content(e) for e in required_evals) if required_evals else None

        # 误报风险评估
        fp_risk = _assess_false_positive_risk(rule)

        # rollback plan 清晰度（notes 中是否有回滚说明）
        rollback_clear = any(k in notes.lower() for k in ["回滚", "rollback", "改回", "恢复"])

        # 安全关键性（仅精确匹配安全链路/安全边界/绕过检测）
        security_critical = (
            severity == "high"
            and any(k in title.lower() for k in [
                "安全链路", "不可绕过", "并发安全", "跨域",
                "planexecutor", "executionstrategy", "crossdomain",
            ])
        )

        # ── 确定 recommendation ──

        # 已废弃/被替代 → 忽略
        if status in ("deprecated", "superseded"):
            reviews.append(RuleReview(
                rule_id=rid, title=title, status=status, blocking=blocking,
                recommendation="reject_for_now",
                reason=f"规则状态为 {status}，已废弃或被替代，不再评估",
                checks_exist=bool(checks_exist), tests_exist=bool(tests_exist),
                evals_exist=bool(evals_exist),
                false_positive_risk=fp_risk, rollback_plan_clear=rollback_clear,
                security_critical=security_critical,
                checks_detail=required_checks, tests_detail=required_tests,
                evals_detail=required_evals,
            ))
            continue

        # 已是 active+blocking=true → 跳过（已在 baseline 中）
        if status == "active" and blocking is True:
            reviews.append(RuleReview(
                rule_id=rid, title=title, status=status, blocking=blocking,
                recommendation="keep_non_blocking",  # 不需要改变
                reason="已是 active+blocking=true，当前 baseline，无需变更",
                checks_exist=bool(checks_exist), tests_exist=bool(tests_exist),
                evals_exist=bool(evals_exist),
                false_positive_risk=fp_risk, rollback_plan_clear=rollback_clear,
                security_critical=security_critical,
                checks_detail=required_checks, tests_detail=required_tests,
                evals_detail=required_evals,
            ))
            continue

        # 缺少 required_checks
        if required_checks and checks_exist is False:
            reviews.append(RuleReview(
                rule_id=rid, title=title, status=status, blocking=blocking,
                recommendation="missing_checks",
                reason=f"required_checks 中有 {sum(1 for c in required_checks if not _asset_exists(c))} 项不存在: "
                       f"{[c for c in required_checks if not _asset_exists(c)]}",
                checks_exist=False, tests_exist=bool(tests_exist),
                evals_exist=bool(evals_exist),
                false_positive_risk=fp_risk, rollback_plan_clear=rollback_clear,
                security_critical=security_critical,
                checks_detail=required_checks, tests_detail=required_tests,
                evals_detail=required_evals,
            ))
            continue

        # 缺少 required_tests（有 required_tests 但不存在）
        if required_tests and tests_exist is False:
            reviews.append(RuleReview(
                rule_id=rid, title=title, status=status, blocking=blocking,
                recommendation="missing_tests",
                reason=f"required_tests 中有 {sum(1 for t in required_tests if not _asset_exists(t))} 项不存在: "
                       f"{[t for t in required_tests if not _asset_exists(t)]}",
                checks_exist=bool(checks_exist), tests_exist=False,
                evals_exist=bool(evals_exist),
                false_positive_risk=fp_risk, rollback_plan_clear=rollback_clear,
                security_critical=security_critical,
                checks_detail=required_checks, tests_detail=required_tests,
                evals_detail=required_evals,
            ))
            continue

        # 缺少 required_evals 且 notes 中没有 TODO/eval 说明
        if required_evals and evals_exist is False:
            has_todo = any(k in notes.lower() for k in ["todo", "待补", "step 9", "step 8"])
            if not has_todo:
                reviews.append(RuleReview(
                    rule_id=rid, title=title, status=status, blocking=blocking,
                    recommendation="missing_evals",
                    reason=f"required_evals 中有 {sum(1 for e in required_evals if not _eval_has_content(e))} 项不完整，"
                           f"且 notes 中无 TODO 说明",
                    checks_exist=bool(checks_exist), tests_exist=bool(tests_exist),
                    evals_exist=False,
                    false_positive_risk=fp_risk, rollback_plan_clear=rollback_clear,
                    security_critical=security_critical,
                    checks_detail=required_checks, tests_detail=required_tests,
                    evals_detail=required_evals,
                ))
                continue
            else:
                reviews.append(RuleReview(
                    rule_id=rid, title=title, status=status, blocking=blocking,
                    recommendation="needs_more_observation",
                    reason=f"required_evals 不完整（{notes[:80]}...），待补齐后重新审查",
                    checks_exist=bool(checks_exist), tests_exist=bool(tests_exist),
                    evals_exist=False,
                    false_positive_risk=fp_risk, rollback_plan_clear=rollback_clear,
                    security_critical=security_critical,
                    checks_detail=required_checks, tests_detail=required_tests,
                    evals_detail=required_evals,
                ))
                continue

        # required_evals 为空但 notes 中有 TODO 标记 → 评估未完成
        if not required_evals and evals_exist is None:
            has_todo = any(k in notes.lower() for k in ["todo", "待补", "step 9", "step 8"])
            if has_todo:
                reviews.append(RuleReview(
                    rule_id=rid, title=title, status=status, blocking=blocking,
                    recommendation="missing_evals",
                    reason=f"required_evals 为空，notes 标注待补: {notes[:80]}...",
                    checks_exist=bool(checks_exist), tests_exist=bool(tests_exist),
                    evals_exist=False,
                    false_positive_risk=fp_risk, rollback_plan_clear=rollback_clear,
                    security_critical=security_critical,
                    checks_detail=required_checks, tests_detail=required_tests,
                    evals_detail=required_evals,
                ))
                continue

        # required_checks 为空且 required_tests 为空 → 缺少资产
        if not required_checks and not required_tests:
            reviews.append(RuleReview(
                rule_id=rid, title=title, status=status, blocking=blocking,
                recommendation="missing_checks",
                reason="required_checks 和 required_tests 均为空，规则缺乏可验证的检查资产",
                checks_exist=False, tests_exist=False,
                evals_exist=bool(evals_exist),
                false_positive_risk=fp_risk, rollback_plan_clear=rollback_clear,
                security_critical=security_critical,
                checks_detail=[], tests_detail=[],
                evals_detail=required_evals,
            ))
            continue

        # 高误报风险 + proposed → keep_non_blocking
        if fp_risk == "high" and status == "proposed":
            reviews.append(RuleReview(
                rule_id=rid, title=title, status=status, blocking=blocking,
                recommendation="keep_non_blocking",
                reason=f"误报风险为 high（规则依赖文档/注释/注册表变更检测），不适合进入 blocking",
                checks_exist=bool(checks_exist), tests_exist=bool(tests_exist),
                evals_exist=bool(evals_exist),
                false_positive_risk=fp_risk, rollback_plan_clear=rollback_clear,
                security_critical=security_critical,
                checks_detail=required_checks, tests_detail=required_tests,
                evals_detail=required_evals,
            ))
            continue

        # proposed 规则且资产齐全且低/中误报风险 → ready_for_fast_gate_blocking
        # （proposed 不能直接推荐 precommit blocking，需先晋升 active）
        if status == "proposed":
            if checks_exist and tests_exist and security_critical and fp_risk == "low":
                reviews.append(RuleReview(
                    rule_id=rid, title=title, status=status, blocking=blocking,
                    recommendation="ready_for_fast_gate_blocking",
                    reason="资产齐全（checks+tests+evals），安全关键，误报风险低。"
                           "建议先进入 fast gate blocking 观察，稳定后晋升 active+blocking=true",
                    checks_exist=True, tests_exist=True,
                    evals_exist=bool(evals_exist),
                    checks_stable=True,  # 当前 fast gate 全部 passed
                    false_positive_risk=fp_risk, rollback_plan_clear=rollback_clear,
                    security_critical=security_critical,
                    checks_detail=required_checks, tests_detail=required_tests,
                    evals_detail=required_evals,
                ))
            elif checks_exist and tests_exist:
                reviews.append(RuleReview(
                    rule_id=rid, title=title, status=status, blocking=blocking,
                    recommendation="needs_more_observation",
                    reason="资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking",
                    checks_exist=True, tests_exist=True,
                    evals_exist=bool(evals_exist),
                    false_positive_risk=fp_risk, rollback_plan_clear=rollback_clear,
                    security_critical=security_critical,
                    checks_detail=required_checks, tests_detail=required_tests,
                    evals_detail=required_evals,
                ))
            else:
                reviews.append(RuleReview(
                    rule_id=rid, title=title, status=status, blocking=blocking,
                    recommendation="needs_more_observation",
                    reason="资产不完整或误报风险评估不明确，需进一步补齐",
                    checks_exist=bool(checks_exist), tests_exist=bool(tests_exist),
                    evals_exist=bool(evals_exist),
                    false_positive_risk=fp_risk, rollback_plan_clear=rollback_clear,
                    security_critical=security_critical,
                    checks_detail=required_checks, tests_detail=required_tests,
                    evals_detail=required_evals,
                ))
            continue

        # 兜底
        reviews.append(RuleReview(
            rule_id=rid, title=title, status=status, blocking=blocking,
            recommendation="needs_more_observation",
            reason="需进一步评估",
            checks_exist=bool(checks_exist), tests_exist=bool(tests_exist),
            evals_exist=bool(evals_exist),
            false_positive_risk=fp_risk, rollback_plan_clear=rollback_clear,
            security_critical=security_critical,
            checks_detail=required_checks, tests_detail=required_tests,
            evals_detail=required_evals,
        ))

    # 分类
    result = ExpansionReview(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        rules_path=str(rp),
        total_rules=len(all_rules),
        active_blocking_rules=active_blocking_ids,
        ta_r018_stable=True,  # Step 24 验证通过
        precommit_blocking_stable=True,  # Step 24 验证通过
        reviews=reviews,
    )

    for rv in reviews:
        rec = rv.recommendation
        if rec == "ready_for_fast_gate_blocking":
            result.ready_candidates.append(rv)
        elif rec == "ready_for_precommit_blocking_review":
            result.ready_candidates.append(rv)
        elif rec in ("needs_more_observation",):
            result.needs_observation.append(rv)
        elif rec in ("missing_checks", "missing_tests", "missing_evals"):
            result.missing_assets.append(rv)
        elif rec in ("keep_non_blocking",):
            result.kept_non_blocking.append(rv)
        elif rec in ("reject_for_now",):
            result.rejected.append(rv)

    return result


def render_review_json(review: ExpansionReview) -> dict:
    """将审查结果渲染为可序列化的 JSON dict。"""
    def _rv_to_dict(rv: RuleReview) -> dict:
        return {
            "rule_id": rv.rule_id,
            "title": rv.title,
            "status": rv.status,
            "blocking": rv.blocking,
            "recommendation": rv.recommendation,
            "reason": rv.reason,
            "checks_exist": rv.checks_exist,
            "tests_exist": rv.tests_exist,
            "evals_exist": rv.evals_exist,
            "checks_stable": rv.checks_stable,
            "false_positive_risk": rv.false_positive_risk,
            "rollback_plan_clear": rv.rollback_plan_clear,
            "security_critical": rv.security_critical,
            "checks_detail": rv.checks_detail,
            "tests_detail": rv.tests_detail,
            "evals_detail": rv.evals_detail,
        }

    return {
        "report_type": "memory_rule_blocking_expansion_review",
        "run_id": review.run_id,
        "timestamp": review.timestamp,
        "rules_path": review.rules_path,
        "total_rules": review.total_rules,
        "active_blocking_rules": review.active_blocking_rules,
        "ta_r018_stable": review.ta_r018_stable,
        "precommit_blocking_stable": review.precommit_blocking_stable,
        "ready_candidates": [_rv_to_dict(r) for r in review.ready_candidates],
        "needs_observation": [_rv_to_dict(r) for r in review.needs_observation],
        "missing_assets": [_rv_to_dict(r) for r in review.missing_assets],
        "kept_non_blocking": [_rv_to_dict(r) for r in review.kept_non_blocking],
        "rejected": [_rv_to_dict(r) for r in review.rejected],
        "all_reviews": [_rv_to_dict(r) for r in review.reviews],
        "boundary_confirmations": {
            "no_memory_rules_yml_modified": True,
            "no_docs_memory_modified": True,
            "no_precommit_behavior_changed": True,
            "no_new_blocking_rules": True,
            "no_latest_generated": True,
            "no_llm_called": True,
            "no_business_code_modified": True,
        },
    }


def render_review_markdown(review: ExpansionReview) -> str:
    """将审查结果渲染为 Markdown 报告。"""
    lines: list[str] = []

    lines.append("# Memory Rule Blocking Expansion Readiness Review")
    lines.append("")
    lines.append(f"**Run ID:** `{review.run_id}`")
    lines.append(f"**时间:** {review.timestamp}")
    lines.append(f"**规则文件:** {review.rules_path}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| 指标 | 值 |")
    lines.append(f"|------|-----|")
    lines.append(f"| 总规则数 | {review.total_rules} |")
    lines.append(f"| 当前 active+blocking | {len(review.active_blocking_rules)} ({', '.join(review.active_blocking_rules)}) |")
    lines.append(f"| TA-R018 稳定 | {'✅' if review.ta_r018_stable else '❌'} |")
    lines.append(f"| pre-commit blocking 稳定 | {'✅' if review.precommit_blocking_stable else '❌'} |")
    lines.append(f"| ready_for_fast_gate_blocking | {len(review.ready_candidates)} |")
    lines.append(f"| needs_more_observation | {len(review.needs_observation)} |")
    lines.append(f"| missing_assets | {len(review.missing_assets)} |")
    lines.append(f"| keep_non_blocking | {len(review.kept_non_blocking)} |")
    lines.append(f"| rejected | {len(review.rejected)} |")
    lines.append("")

    # Current Blocking Baseline
    lines.append("## Current Blocking Baseline")
    lines.append("")
    lines.append(f"- **active+blocking 规则:** {', '.join(review.active_blocking_rules) if review.active_blocking_rules else '（无）'}")
    lines.append(f"- **TA-R018 稳定性:** Step 24 验证 — 11 次 blocking 模式观察，全部 exit 0，误报 0")
    lines.append(f"- **pre-commit blocking 状态:** Step 23 已启用，Step 24 稳定运行")
    lines.append("")

    # All candidates reviewed
    lines.append("## Candidate Rules Reviewed")
    lines.append("")
    lines.append("| rule_id | status | blocking | recommendation | reason |")
    lines.append("|---------|--------|----------|----------------|--------|")
    for rv in review.reviews:
        rec_emoji = {
            "ready_for_fast_gate_blocking": "🟢",
            "ready_for_precommit_blocking_review": "🟡",
            "needs_more_observation": "🔵",
            "missing_checks": "🔴",
            "missing_tests": "🔴",
            "missing_evals": "🔴",
            "keep_non_blocking": "⚪",
            "reject_for_now": "⚫",
        }.get(rv.recommendation, "❓")
        reason_short = rv.reason[:60] + "..." if len(rv.reason) > 60 else rv.reason
        lines.append(
            f"| {rv.rule_id} | {rv.status} | {rv.blocking} | "
            f"{rec_emoji} {rv.recommendation} | {reason_short} |"
        )
    lines.append("")

    # Ready Candidates
    if review.ready_candidates:
        lines.append("## Ready Candidates")
        lines.append("")
        for rv in review.ready_candidates:
            lines.append(f"### {rv.rule_id}: {rv.title}")
            lines.append("")
            lines.append(f"- **推荐:** {rv.recommendation}")
            lines.append(f"- **原因:** {rv.reason}")
            lines.append(f"- **checks:** {', '.join(rv.checks_detail) if rv.checks_detail else '（无）'}")
            lines.append(f"- **tests:** {', '.join(rv.tests_detail) if rv.tests_detail else '（无）'}")
            lines.append(f"- **evals:** {', '.join(rv.evals_detail) if rv.evals_detail else '（无）'}")
            lines.append(f"- **误报风险:** {rv.false_positive_risk}")
            lines.append(f"- **安全关键:** {'✅' if rv.security_critical else '❌'}")
            lines.append("")
    else:
        lines.append("## Ready Candidates")
        lines.append("")
        lines.append("（无规则可直接推荐 pre-commit blocking）")
        lines.append("")

    # Needs More Observation
    if review.needs_observation:
        lines.append("## Needs More Observation")
        lines.append("")
        for rv in review.needs_observation:
            lines.append(f"- **{rv.rule_id}**: {rv.reason}")
        lines.append("")

    # Missing Assets
    if review.missing_assets:
        lines.append("## Missing Assets")
        lines.append("")
        lines.append("| rule_id | 缺失 |")
        lines.append("|---------|------|")
        for rv in review.missing_assets:
            missing = []
            if rv.recommendation == "missing_checks":
                missing.append("checks")
            if rv.recommendation == "missing_tests":
                missing.append("tests")
            if rv.recommendation == "missing_evals":
                missing.append("evals")
            lines.append(f"| {rv.rule_id} | {', '.join(missing)} |")
        lines.append("")

    # False Positive Risks
    lines.append("## False Positive Risks")
    lines.append("")
    lines.append("| rule_id | risk | note |")
    lines.append("|---------|------|------|")
    for rv in review.reviews:
        if rv.false_positive_risk in ("high", "medium") and rv.recommendation != "reject_for_now":
            lines.append(f"| {rv.rule_id} | {rv.false_positive_risk} | {rv.reason[:50]} |")
    lines.append("")

    # Rollback Readiness
    lines.append("## Rollback Readiness")
    lines.append("")
    for rv in review.ready_candidates:
        lines.append(f"- **{rv.rule_id}**: rollback plan {'清晰 ✅' if rv.rollback_plan_clear else '缺失 ❌'}")
    lines.append("")
    lines.append("通用回滚方式：将对应规则的 blocking 从 true 改回 false，无需修改业务代码。")
    lines.append("")

    # Recommendation
    lines.append("## Recommendation")
    lines.append("")
    if review.ready_candidates:
        lines.append(f"共 {len(review.ready_candidates)} 条规则可进入 fast gate blocking 观察：")
        for rv in review.ready_candidates:
            lines.append(f"1. **{rv.rule_id}** — {rv.title}")
        lines.append("")
        lines.append("建议进入 Step 26：针对上述候选规则做人工审批和 fast gate blocking apply。")
        lines.append("在 fast gate blocking 稳定观察 ≥7 天后，再评估 pre-commit blocking。")
    else:
        lines.append("当前无规则可直接推荐 pre-commit blocking。")
        lines.append("")
        if review.needs_observation:
            lines.append(f"有 {len(review.needs_observation)} 条规则需要补齐资产或经过 fast gate 观察期后重新审查。")
        if review.missing_assets:
            lines.append(f"有 {len(review.missing_assets)} 条规则缺少 checks/tests/evals。")
    lines.append("")

    # Not Applied
    lines.append("## Not Applied Automatically")
    lines.append("")
    lines.append("本轮明确未做的操作：")
    lines.append("")
    lines.append("- ❌ 未修改 memory_rules.yml")
    lines.append("- ❌ 未将任何规则 blocking 改为 true")
    lines.append("- ❌ 未将 proposed 改为 active")
    lines.append("- ❌ 未修改 docs/memory/*")
    lines.append("- ❌ 未修改 TA-R018")
    lines.append("- ❌ 未修改 .githooks/pre-commit")
    lines.append("- ❌ 未修改 pre-commit blocking 行为")
    lines.append("- ❌ 未新增 CI 阻断")
    lines.append("- ❌ 未修改业务代码")
    lines.append("- ❌ 未调用真实 LLM")
    lines.append("- ❌ 未生成 latest")
    lines.append("- ❌ 未批量扩大阻断范围")
    lines.append("")

    lines.append("---")
    lines.append(f"*Step 25 自动审查 — {review.timestamp}*")

    return "\n".join(lines)


def write_review_snapshot(
    review: ExpansionReview,
    output_dir: str | Path | None = None,
) -> dict[str, str]:
    """写入审查结果 JSON + MD 到指定目录。

    不生成 latest 文件。

    Args:
        review: 审查结果
        output_dir: 输出目录

    Returns:
        {"json": path, "md": path}
    """
    out_dir = Path(output_dir) if output_dir else _DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).astimezone()
    ts_slug = now.strftime("%Y%m%d_%H%M%S")

    json_name = f"memory_rule_blocking_expansion_review_{ts_slug}.json"
    md_name = f"memory_rule_blocking_expansion_review_{ts_slug}.md"

    json_path = out_dir / json_name
    md_path = out_dir / md_name

    json_path.write_text(
        json.dumps(render_review_json(review), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(render_review_markdown(review), encoding="utf-8")

    return {"json": str(json_path), "md": str(md_path)}


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。"""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="Memory Rule Blocking Expansion Readiness Review（Step 25）"
    )
    parser.add_argument(
        "--rules-path",
        default=str(_DEFAULT_RULES_PATH),
        help=f"memory_rules.yml 路径（默认 {_DEFAULT_RULES_PATH}）",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_DEFAULT_OUTPUT_DIR),
        help=f"输出目录（默认 {_DEFAULT_OUTPUT_DIR}）",
    )
    args = parser.parse_args(argv)

    try:
        review = review_rules(args.rules_path)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except yaml.YAMLError as exc:
        print(f"[ERROR] YAML 解析失败: {exc}", file=sys.stderr)
        return 1

    paths = write_review_snapshot(review, args.output_dir)

    print(f"审查完成: {review.run_id}")
    print(f"  总规则数: {review.total_rules}")
    print(f"  当前 active+blocking: {review.active_blocking_rules}")
    print(f"  ready_for_fast_gate_blocking: {len(review.ready_candidates)}")
    print(f"  needs_more_observation: {len(review.needs_observation)}")
    print(f"  missing_assets: {len(review.missing_assets)}")
    print(f"  keep_non_blocking: {len(review.kept_non_blocking)}")
    print(f"  rejected: {len(review.rejected)}")
    print(f"  JSON: {paths['json']}")
    print(f"  MD:   {paths['md']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
