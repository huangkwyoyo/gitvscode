"""Memory Harness Step 17 — Promotion Apply Validation Workflow 测试。

覆盖 23 个测试场景：
1. valid promotion report 可以生成 validation report
2. latest promotion report 输入被拒绝
3. promotion report JSON 格式错误 → failed
4. proposed_to_active 已正确应用 → passed
5. proposed_to_active 未应用 → pending
6. active_to_blocking 已正确应用且闭环完整 → passed
7. active_to_blocking 缺 rollback_plan → failed
8. not_eligible 规则被人工 active → failed
9. keep_proposed 规则被 blocking=true → failed
10. needs_manual_review 规则被 blocking=true → failed
11. proposed 规则直接 active+blocking=true 越级 → failed
12. active+blocking=true 缺 required_tests → failed
13. duplicate rule_id → failed
14. 非 TA-Rxxx rule_id → failed
15. rule index 未同步 → warning 或 failed
16. CLI 只生成 timestamp snapshot
17. CLI 不生成 latest
18. CLI 不修改 docs/memory/*
19. CLI 不自动运行 generate_rule_index.py（除非 --run-checks）
20. JSON renderer 包含 summary / validation_items
21. Markdown renderer 包含 Rollback Readiness
22. 不调用 LLM
23. 不接 fast gate 阻断
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# 测试辅助函数
# ---------------------------------------------------------------------------

def _make_rule(
    rule_id: str = "TA-R900",
    title: str = "测试规则",
    status: str = "proposed",
    blocking: bool = False,
    severity: str = "high",
    applies_to: list[str] | None = None,
    required_checks: list[str] | None = None,
    required_tests: list[str] | None = None,
    required_evals: list[str] | None = None,
    notes: str = "",
) -> dict:
    """构造最小规则字典。"""
    return {
        "rule_id": rule_id,
        "title": title,
        "status": status,
        "blocking": blocking,
        "severity": severity,
        "source_memory": "test",
        "risk_ids": ["RISK-999"],
        "applies_to": applies_to or ["src/demo.py"],
        "required_checks": required_checks or [],
        "required_tests": required_tests or [],
        "required_evals": required_evals or [],
        "notes": notes,
    }


def _make_candidate(
    rule_id: str = "TA-R900",
    title: str = "测试规则",
    promotion_type: str = "proposed_to_active",
    eligibility: str = "eligible",
    proposed_status: str = "active",
    proposed_blocking: str = "false",
    current_status: str = "proposed",
    current_blocking: bool = False,
    reasons: list[str] | None = None,
    missing_requirements: list[str] | None = None,
    false_positive_risk: str = "low",
    required_checks_status: str = "complete",
    required_tests_status: str = "complete",
    required_evals_status: str = "complete",
    validation_status: str = "passed",
    fast_gate_stability: dict | None = None,
    manual_approval_required: bool = False,
    rollback_plan: str | None = None,
) -> dict:
    """构造最小 promotion candidate 字典。"""
    if fast_gate_stability is None:
        fast_gate_stability = {
            "total_runs": 5, "stable_runs": 5,
            "required_runs": 3, "is_stable": True,
            "reason": "稳定运行 5/3 次",
        }
    return {
        "rule_id": rule_id,
        "title": title,
        "current_status": current_status,
        "current_blocking": current_blocking,
        "proposed_status": proposed_status,
        "proposed_blocking": proposed_blocking,
        "promotion_type": promotion_type,
        "eligibility": eligibility,
        "reasons": reasons or [],
        "missing_requirements": missing_requirements or [],
        "false_positive_risk": false_positive_risk,
        "required_checks_status": required_checks_status,
        "required_tests_status": required_tests_status,
        "required_evals_status": required_evals_status,
        "validation_status": validation_status,
        "fast_gate_stability": fast_gate_stability,
        "recommended_action": "测试推荐操作",
        "manual_approval_required": manual_approval_required,
        "rollback_plan": rollback_plan,
    }


def _make_promotion_report(candidates: list[dict]) -> dict:
    """构造最小 promotion report。"""
    return {
        "run_id": "rule-promotion-test",
        "timestamp": "2026-06-18T12:00:00Z",
        "source_rules": "docs/memory/memory_rules.yml",
        "source_validation_report": "test",
        "source_fast_gate_history": None,
        "source_approval_decisions": None,
        "summary": {
            "total_rules": len(candidates),
            "total_candidates": len(candidates),
            "proposed_to_active": sum(1 for c in candidates if c.get("promotion_type") == "proposed_to_active"),
            "active_to_blocking": sum(1 for c in candidates if c.get("promotion_type") == "active_to_blocking"),
            "keep_proposed": sum(1 for c in candidates if c.get("promotion_type") == "keep_proposed"),
            "demote_or_rewrite": sum(1 for c in candidates if c.get("promotion_type") == "demote_or_rewrite"),
            "eligible": sum(1 for c in candidates if c.get("eligibility") == "eligible"),
            "not_eligible": sum(1 for c in candidates if c.get("eligibility") == "not_eligible"),
            "needs_manual_review": sum(1 for c in candidates if c.get("eligibility") == "needs_manual_review"),
        },
        "candidates": candidates,
        "eligible": [c for c in candidates if c.get("eligibility") == "eligible"],
        "not_eligible": [c for c in candidates if c.get("eligibility") == "not_eligible"],
        "needs_manual_review": [c for c in candidates if c.get("eligibility") == "needs_manual_review"],
        "proposed_to_active": [c for c in candidates if c.get("promotion_type") == "proposed_to_active"],
        "active_to_blocking": [c for c in candidates if c.get("promotion_type") == "active_to_blocking"],
        "keep_proposed": [c for c in candidates if c.get("promotion_type") == "keep_proposed"],
        "demote_or_rewrite": [c for c in candidates if c.get("promotion_type") == "demote_or_rewrite"],
        "write_mode": "proposal_only",
    }


def _write_rules_yml(tmp_path: Path, rules: list[dict]) -> Path:
    """写入临时 memory_rules.yml。"""
    path = tmp_path / "memory_rules.yml"
    path.write_text(
        yaml.dump({"rules": rules}, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    return path


def _write_promotion_report_json(tmp_path: Path, report: dict) -> Path:
    """写入临时 promotion report JSON。"""
    path = tmp_path / "promotion_report.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _touch(root: Path, relative_path: str) -> str:
    """创建占位文件并返回相对路径。"""
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# test placeholder\n", encoding="utf-8")
    return relative_path


# ---------------------------------------------------------------------------
# 场景 1: valid promotion report 可以生成 validation report
# ---------------------------------------------------------------------------

class TestBasicValidation:
    """基础 validation 测试。"""

    def test_valid_promotion_report_generates_validation(self, tmp_path):
        """场景 1: 有效的 promotion report 可以生成 validation report。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        # 规则保持 proposed（未被应用）
        rule = _make_rule()
        rules_path = _write_rules_yml(tmp_path, [rule])

        candidate = _make_candidate()
        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([candidate]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        assert "run_id" in report
        assert report["write_mode"] == "proposal_only"
        assert report["summary"]["candidates_checked"] == 1
        assert len(report["validation_items"]) > 0


# ---------------------------------------------------------------------------
# 场景 2: latest 输入被拒绝
# ---------------------------------------------------------------------------

class TestLatestRejected:
    """latest 输入拒绝测试。"""

    def test_latest_promotion_report_rejected(self, tmp_path):
        """场景 2a: latest promotion report 输入被拒绝。"""
        from harness.memory_promotion_validation import load_promotion_report

        path = tmp_path / "memory_rule_promotion_latest.json"
        path.write_text('{"candidates": []}', encoding="utf-8")
        with pytest.raises(ValueError, match="latest"):
            load_promotion_report(path)

    def test_latest_rules_rejected(self, tmp_path):
        """场景 2b: latest rules 输入被拒绝。"""
        from harness.memory_promotion_validation import load_rules

        path = tmp_path / "memory_rules_latest.yml"
        path.write_text("rules: []\n", encoding="utf-8")
        with pytest.raises(ValueError, match="latest"):
            load_rules(path)


# ---------------------------------------------------------------------------
# 场景 3: promotion report JSON 格式错误
# ---------------------------------------------------------------------------

class TestFormatErrors:
    """格式错误测试。"""

    def test_malformed_promotion_report_json(self, tmp_path):
        """场景 3: 格式错误的 promotion report JSON → 异常。"""
        path = tmp_path / "bad.json"
        path.write_text("not valid json", encoding="utf-8")
        with pytest.raises(Exception):
            from harness.memory_promotion_validation import load_promotion_report
            load_promotion_report(path)

    def test_missing_candidates_field(self, tmp_path):
        """promotion report 缺少 candidates 字段 → ValueError。"""
        path = tmp_path / "report.json"
        path.write_text('{"run_id": "test"}', encoding="utf-8")
        with pytest.raises(ValueError, match="candidates"):
            from harness.memory_promotion_validation import load_promotion_report
            load_promotion_report(path)


# ---------------------------------------------------------------------------
# 场景 4: proposed_to_active 已正确应用 → passed
# ---------------------------------------------------------------------------

class TestProposedToActiveApplied:
    """proposed_to_active 正确应用测试。"""

    def test_proposed_to_active_correctly_applied(self, tmp_path):
        """场景 4: proposed_to_active 已正确应用（active+blocking=false）→ passed。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        # 规则已被人工改为 active
        rule = _make_rule(rule_id="TA-R900", status="active", blocking=False)
        rules_path = _write_rules_yml(tmp_path, [rule])

        candidate = _make_candidate(
            rule_id="TA-R900",
            promotion_type="proposed_to_active",
            eligibility="eligible",
            proposed_status="active",
            proposed_blocking="false",
        )
        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([candidate]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        assert report["summary"]["applied"] == 1
        assert report["summary"]["failures"] == 0
        # 找对应的 passed 项
        promo_items = [
            i for i in report["validation_items"]
            if i.get("check_category") == "promotion_application"
            and i.get("rule_id") == "TA-R900"
        ]
        assert promo_items[0]["status"] == "passed"


# ---------------------------------------------------------------------------
# 场景 5: proposed_to_active 未应用 → pending
# ---------------------------------------------------------------------------

class TestProposedToActivePending:
    """proposed_to_active 未应用测试。"""

    def test_proposed_to_active_not_applied_is_pending(self, tmp_path):
        """场景 5: proposed_to_active 未应用（仍为 proposed）→ pending。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rule = _make_rule(rule_id="TA-R900", status="proposed", blocking=False)
        rules_path = _write_rules_yml(tmp_path, [rule])

        candidate = _make_candidate(
            rule_id="TA-R900",
            promotion_type="proposed_to_active",
            eligibility="eligible",
            proposed_status="active",
            proposed_blocking="false",
        )
        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([candidate]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        assert report["summary"]["pending_manual_actions"] >= 1
        promo_items = [
            i for i in report["validation_items"]
            if i.get("check_category") == "promotion_application"
            and i.get("rule_id") == "TA-R900"
        ]
        assert promo_items[0]["status"] == "pending"


# ---------------------------------------------------------------------------
# 场景 6: active_to_blocking 已正确应用且闭环完整 → passed
# ---------------------------------------------------------------------------

class TestActiveToBlockingApplied:
    """active_to_blocking 正确应用测试。"""

    def test_active_to_blocking_correctly_applied_with_closure(self, tmp_path):
        """场景 6: active_to_blocking 已正确应用且闭环完整 → passed。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        checks = _touch(tmp_path, "harness/checks/TA-R901.py")
        tests = _touch(tmp_path, "tests/test_TA-R901.py")
        evals = _touch(tmp_path, "evals/TA-R901.yml")

        rule = _make_rule(
            rule_id="TA-R901",
            status="active",
            blocking=True,  # 已经应用为 blocking=true
            required_checks=[checks],
            required_tests=[tests],
            required_evals=[evals],
            notes="回滚计划：将 blocking 改回 false 即可恢复。",
        )
        rules_path = _write_rules_yml(tmp_path, [rule])

        candidate = _make_candidate(
            rule_id="TA-R901",
            promotion_type="active_to_blocking",
            eligibility="eligible",
            proposed_status="active",
            proposed_blocking="true",
            current_status="active",
            current_blocking=False,
        )
        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([candidate]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        assert report["summary"]["applied"] >= 1
        promo_items = [
            i for i in report["validation_items"]
            if i.get("check_category") == "promotion_application"
            and i.get("rule_id") == "TA-R901"
        ]
        assert promo_items[0]["status"] == "passed"


# ---------------------------------------------------------------------------
# 场景 7: active_to_blocking 缺 rollback_plan → failed
# ---------------------------------------------------------------------------

class TestActiveToBlockingMissingRollback:
    """active_to_blocking 缺少回滚计划测试。"""

    def test_active_to_blocking_missing_rollback_plan_is_failed(self, tmp_path):
        """场景 7: active_to_blocking 已应用但缺 rollback_plan → failed。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        checks = _touch(tmp_path, "harness/checks/TA-R901.py")
        tests = _touch(tmp_path, "tests/test_TA-R901.py")
        evals = _touch(tmp_path, "evals/TA-R901.yml")

        rule = _make_rule(
            rule_id="TA-R901",
            status="active",
            blocking=True,
            required_checks=[checks],
            required_tests=[tests],
            required_evals=[evals],
            notes="",  # 无回滚计划
        )
        rules_path = _write_rules_yml(tmp_path, [rule])

        candidate = _make_candidate(
            rule_id="TA-R901",
            promotion_type="active_to_blocking",
            eligibility="eligible",
            proposed_status="active",
            proposed_blocking="true",
        )
        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([candidate]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        assert report["summary"]["failures"] >= 1
        promo_items = [
            i for i in report["validation_items"]
            if i.get("check_category") == "promotion_application"
            and i.get("rule_id") == "TA-R901"
        ]
        assert promo_items[0]["status"] == "failed"
        assert "回滚" in promo_items[0]["message"]


# ---------------------------------------------------------------------------
# 场景 8: not_eligible 规则被人工 active → failed
# ---------------------------------------------------------------------------

class TestNotEligiblePromoted:
    """not_eligible 规则被错误晋升测试。"""

    def test_not_eligible_rule_promoted_to_active_is_failed(self, tmp_path):
        """场景 8: not_eligible 规则被人工 active → failed。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        # 规则被错误设置为 active
        rule = _make_rule(rule_id="TA-R900", status="active", blocking=False)
        rules_path = _write_rules_yml(tmp_path, [rule])

        candidate = _make_candidate(
            rule_id="TA-R900",
            promotion_type="keep_proposed",
            eligibility="not_eligible",
            proposed_status="proposed",
            proposed_blocking="false",
        )
        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([candidate]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        assert report["summary"]["failures"] >= 1
        un_items = [
            i for i in report["validation_items"]
            if i.get("check_category") == "unauthorized_promotion"
        ]
        assert len(un_items) >= 1
        assert un_items[0]["status"] == "failed"


# ---------------------------------------------------------------------------
# 场景 9: keep_proposed 规则被 blocking=true → failed
# ---------------------------------------------------------------------------

class TestKeepProposedBlocking:
    """keep_proposed 规则被错误设置 blocking 测试。"""

    def test_keep_proposed_rule_blocking_true_is_failed(self, tmp_path):
        """场景 9: keep_proposed 规则被设置 blocking=true → failed。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rule = _make_rule(rule_id="TA-R900", status="proposed", blocking=True)
        rules_path = _write_rules_yml(tmp_path, [rule])

        candidate = _make_candidate(
            rule_id="TA-R900",
            promotion_type="keep_proposed",
            eligibility="not_eligible",
            proposed_status="proposed",
            proposed_blocking="false",
        )
        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([candidate]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        assert report["summary"]["failures"] >= 1


# ---------------------------------------------------------------------------
# 场景 10: needs_manual_review 规则被 blocking=true → failed
# ---------------------------------------------------------------------------

class TestNeedsManualReviewBlocking:
    """needs_manual_review 规则错误设置 blocking 测试。"""

    def test_needs_manual_review_rule_blocking_true_is_failed(self, tmp_path):
        """场景 10: needs_manual_review 规则被设置 blocking=true → failed。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rule = _make_rule(rule_id="TA-R900", status="active", blocking=True)
        rules_path = _write_rules_yml(tmp_path, [rule])

        candidate = _make_candidate(
            rule_id="TA-R900",
            promotion_type="proposed_to_active",
            eligibility="needs_manual_review",
            proposed_status="active",
            proposed_blocking="false",
        )
        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([candidate]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        assert report["summary"]["failures"] >= 1
        un_items = [
            i for i in report["validation_items"]
            if i.get("check_category") == "unauthorized_promotion"
        ]
        assert any("blocking=true" in i["message"] for i in un_items)


# ---------------------------------------------------------------------------
# 场景 11: proposed 规则直接 active+blocking=true → failed（越级）
# ---------------------------------------------------------------------------

class TestEscalationPrevention:
    """越级晋升防止测试。"""

    def test_proposed_directly_active_blocking_true_is_escalation(self, tmp_path):
        """场景 11: proposed 规则直接 active+blocking=true 越级 → failed。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rule = _make_rule(rule_id="TA-R900", status="active", blocking=True)
        rules_path = _write_rules_yml(tmp_path, [rule])

        candidate = _make_candidate(
            rule_id="TA-R900",
            promotion_type="proposed_to_active",
            eligibility="eligible",
            proposed_status="active",
            proposed_blocking="false",
        )
        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([candidate]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        assert report["summary"]["failures"] >= 1
        promo_items = [
            i for i in report["validation_items"]
            if i.get("check_category") == "promotion_application"
            and i.get("rule_id") == "TA-R900"
        ]
        assert any("越级" in i["message"] for i in promo_items)


# ---------------------------------------------------------------------------
# 场景 12: active+blocking=true 缺 required_tests → failed
# ---------------------------------------------------------------------------

class TestActiveBlockingClosure:
    """active+blocking=true 闭环检查测试。"""

    def test_active_blocking_true_missing_required_tests_fails(self, tmp_path):
        """场景 12: active+blocking=true 缺 required_tests → failed。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        checks = _touch(tmp_path, "harness/checks/TA-R900.py")
        evals = _touch(tmp_path, "evals/TA-R900.yml")

        rule = _make_rule(
            rule_id="TA-R900",
            status="active",
            blocking=True,
            required_checks=[checks],
            required_tests=[],  # 缺失！
            required_evals=[evals],
            notes="回滚计划：将 blocking 改回 false。",
        )
        rules_path = _write_rules_yml(tmp_path, [rule])

        # 不需要对应的 candidate——closure 检查是全局的
        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        closure_items = [
            i for i in report["validation_items"]
            if i.get("check_category") == "active_blocking_closure"
        ]
        assert len(closure_items) >= 1
        assert closure_items[0]["status"] == "failed"
        assert "required_tests" in closure_items[0]["message"]


# ---------------------------------------------------------------------------
# 场景 13: duplicate rule_id → failed
# ---------------------------------------------------------------------------

class TestDuplicateRuleId:
    """重复 rule_id 测试。"""

    def test_duplicate_rule_id_is_failed(self, tmp_path):
        """场景 13: duplicate rule_id → failed。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        r1 = _make_rule(rule_id="TA-R900")
        r2 = _make_rule(rule_id="TA-R900")  # 重复
        rules_path = _write_rules_yml(tmp_path, [r1, r2])

        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        basics_items = [
            i for i in report["validation_items"]
            if i.get("check_category") == "rules_basics" and i["status"] == "failed"
        ]
        assert any("重复" in i["message"] for i in basics_items)


# ---------------------------------------------------------------------------
# 场景 14: 非 TA-Rxxx rule_id → failed
# ---------------------------------------------------------------------------

class TestInvalidRuleIdFormat:
    """非法 rule_id 格式测试。"""

    def test_non_tar_format_rule_id_is_failed(self, tmp_path):
        """场景 14: 非 TA-Rxxx rule_id → failed。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rule = _make_rule(rule_id="INVALID_ID")
        rules_path = _write_rules_yml(tmp_path, [rule])

        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        basics_items = [
            i for i in report["validation_items"]
            if i.get("check_category") == "rules_basics" and i["status"] == "failed"
        ]
        assert any("格式不正确" in i["message"] for i in basics_items)


# ---------------------------------------------------------------------------
# 场景 15: rule index 未同步 → warning
# ---------------------------------------------------------------------------

class TestRuleIndexSync:
    """Rule index 同步检查测试。"""

    def test_rule_index_out_of_sync_is_warning(self, tmp_path):
        """场景 15: rule index 未同步 → warning。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rule = _make_rule(rule_id="TA-R900")
        rules_path = _write_rules_yml(tmp_path, [rule])

        # 创建不同步的索引文件
        docs_memory = tmp_path / "docs" / "memory"
        docs_memory.mkdir(parents=True, exist_ok=True)
        index_path = docs_memory / "规则来源索引.md"
        index_path.write_text("# 规则来源索引\n\n**TA-R999**\n", encoding="utf-8")

        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        index_items = [
            i for i in report["validation_items"]
            if i.get("check_category") == "rule_index_sync"
        ]
        assert len(index_items) >= 1
        assert index_items[0]["status"] == "warning"
        assert "不同步" in index_items[0]["message"]


# ---------------------------------------------------------------------------
# 场景 16-19: CLI 行为测试
# ---------------------------------------------------------------------------

class TestCLIBehavior:
    """CLI 行为测试。"""

    def test_cli_generates_timestamp_snapshot(self, tmp_path):
        """场景 16: CLI 只生成 timestamp snapshot。"""
        rules = [_make_rule(rule_id="TA-R900")]
        rules_path = _write_rules_yml(tmp_path, rules)
        promo_path = _write_promotion_report_json(
            tmp_path,
            _make_promotion_report([_make_candidate()]),
        )
        output_dir = tmp_path / "out"

        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_promotion_validation.py",
                "--promotion-report", str(promo_path),
                "--rules", str(rules_path),
                "--output-dir", str(output_dir),
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        assert result.returncode == 0, result.stderr
        json_files = list(output_dir.glob("memory_promotion_validation_*.json"))
        md_files = list(output_dir.glob("memory_promotion_validation_*.md"))
        assert len(json_files) == 1
        assert len(md_files) == 1

    def test_cli_does_not_generate_latest(self, tmp_path):
        """场景 17: CLI 不生成 latest 文件。"""
        rules = [_make_rule(rule_id="TA-R900")]
        rules_path = _write_rules_yml(tmp_path, rules)
        promo_path = _write_promotion_report_json(
            tmp_path, _make_promotion_report([_make_candidate()])
        )
        output_dir = tmp_path / "out"

        subprocess.run(
            [
                sys.executable,
                "harness/run_memory_promotion_validation.py",
                "--promotion-report", str(promo_path),
                "--rules", str(rules_path),
                "--output-dir", str(output_dir),
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        assert not (output_dir / "memory_promotion_validation_latest.json").exists()
        assert not (output_dir / "memory_promotion_validation_latest.md").exists()

    def test_cli_does_not_modify_rules_yml(self, tmp_path):
        """场景 18: CLI 不修改 docs/memory/*（通过验证文件内容不变）。"""
        rules = [_make_rule(rule_id="TA-R900")]
        rules_path = _write_rules_yml(tmp_path, rules)
        promo_path = _write_promotion_report_json(
            tmp_path, _make_promotion_report([_make_candidate()])
        )
        before = rules_path.read_text(encoding="utf-8")

        subprocess.run(
            [
                sys.executable,
                "harness/run_memory_promotion_validation.py",
                "--promotion-report", str(promo_path),
                "--rules", str(rules_path),
                "--output-dir", str(tmp_path / "out"),
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        after = rules_path.read_text(encoding="utf-8")
        assert before == after

    def test_cli_does_not_run_generate_rule_index_by_default(self, tmp_path):
        """场景 19: CLI 默认不运行 generate_rule_index.py。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rules = [_make_rule(rule_id="TA-R900")]
        rules_path = _write_rules_yml(tmp_path, rules)
        promo_path = _write_promotion_report_json(
            tmp_path, _make_promotion_report([_make_candidate()])
        )

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
            run_checks=False,
        )

        assert report["run_checks"] is False


# ---------------------------------------------------------------------------
# 场景 20-21: 渲染器测试
# ---------------------------------------------------------------------------

class TestRenderers:
    """JSON 和 Markdown 渲染器测试。"""

    def test_json_renderer_includes_summary_and_validation_items(self, tmp_path):
        """场景 20: JSON renderer 包含 summary / validation_items。"""
        from harness.memory_promotion_validation import (
            build_promotion_validation_report,
            render_promotion_validation_json,
        )

        rules = [_make_rule(rule_id="TA-R900")]
        rules_path = _write_rules_yml(tmp_path, rules)
        promo_path = _write_promotion_report_json(
            tmp_path, _make_promotion_report([_make_candidate()])
        )

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )
        json_data = render_promotion_validation_json(report)

        assert "summary" in json_data
        assert "validation_items" in json_data
        assert "recommended_commands" in json_data
        assert json_data["write_mode"] == "proposal_only"
        assert json_data["summary"]["candidates_checked"] == 1

    def test_markdown_renderer_includes_rollback_readiness(self, tmp_path):
        """场景 21: Markdown renderer 包含 Rollback Readiness。"""
        from harness.memory_promotion_validation import (
            build_promotion_validation_report,
            render_promotion_validation_markdown,
        )

        rules = [_make_rule(rule_id="TA-R900")]
        rules_path = _write_rules_yml(tmp_path, rules)
        promo_path = _write_promotion_report_json(
            tmp_path, _make_promotion_report([_make_candidate()])
        )

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )
        md = render_promotion_validation_markdown(report)

        assert "Memory Promotion Validation Report" in md
        assert "## Summary" in md
        assert "Rollback Readiness" in md
        assert "Recommended Commands" in md
        assert "Safety Boundaries" in md
        assert "Not Applied Automatically" in md
        assert "Applied Promotions" in md
        assert "Pending Manual Actions" in md
        assert "Validation Failures" in md
        assert "Warnings" in md
        assert "Active Blocking Rules" in md


# ---------------------------------------------------------------------------
# 场景 22-23: 不调用 LLM + 不接 fast gate 阻断
# ---------------------------------------------------------------------------

class TestNoLLMAndNoFastGate:
    """不调用 LLM 和 fast gate 阻断测试。"""

    def test_build_report_uses_no_llm(self, tmp_path):
        """场景 22: 不调用 LLM（快速执行验证）。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rules = [_make_rule(rule_id="TA-R900")]
        rules_path = _write_rules_yml(tmp_path, rules)
        promo_path = _write_promotion_report_json(
            tmp_path, _make_promotion_report([_make_candidate()])
        )

        import time
        start = time.time()
        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )
        elapsed = time.time() - start

        assert elapsed < 5.0, f"执行耗时 {elapsed:.1f}s，疑似调用了 LLM"
        assert "run_id" in report

    def test_no_fast_gate_blocking_integration(self, tmp_path):
        """场景 23: 不接 fast gate 阻断（报告不含阻断决策字段）。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rules = [_make_rule(rule_id="TA-R900")]
        rules_path = _write_rules_yml(tmp_path, rules)
        promo_path = _write_promotion_report_json(
            tmp_path, _make_promotion_report([_make_candidate()])
        )

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        assert report.get("write_mode") == "proposal_only"
        for item in report["validation_items"]:
            assert "auto_block" not in item
            assert "gate_blocking" not in item


# ---------------------------------------------------------------------------
# 边界和额外测试
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """边界情况测试。"""

    def test_empty_rules_and_candidates(self, tmp_path):
        """空规则和空 candidates。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rules_path = _write_rules_yml(tmp_path, [])
        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        assert report["summary"]["total_validation_items"] >= 0

    def test_status_enum_invalid(self, tmp_path):
        """非法 status 枚举值 → failed。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rule = _make_rule(rule_id="TA-R900", status="invalid_status")
        rules_path = _write_rules_yml(tmp_path, [rule])
        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        basics_items = [
            i for i in report["validation_items"]
            if i.get("check_category") == "rules_basics" and i["status"] == "failed"
        ]
        assert any("status 非法" in i["message"] for i in basics_items)

    def test_blocking_not_bool(self, tmp_path):
        """blocking 非布尔值 → failed。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rule = _make_rule(rule_id="TA-R900", status="proposed")
        rule["blocking"] = "not_a_bool"
        rules_path = _write_rules_yml(tmp_path, [rule])
        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        basics_items = [
            i for i in report["validation_items"]
            if i.get("check_category") == "rules_basics" and i["status"] == "failed"
        ]
        assert any("blocking" in i["message"] for i in basics_items)

    def test_needs_manual_review_promoted_to_active_is_warning(self, tmp_path):
        """needs_manual_review 规则被改为 active → warning（非 failed）。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rule = _make_rule(rule_id="TA-R900", status="active", blocking=False)
        rules_path = _write_rules_yml(tmp_path, [rule])

        candidate = _make_candidate(
            rule_id="TA-R900",
            promotion_type="proposed_to_active",
            eligibility="needs_manual_review",
            proposed_status="active",
            proposed_blocking="false",
        )
        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([candidate]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        un_items = [
            i for i in report["validation_items"]
            if i.get("check_category") == "unauthorized_promotion"
        ]
        assert any(
            i["status"] == "warning" and "active" in i["message"]
            for i in un_items
        )

    def test_demote_or_rewrite_promoted_to_active_is_failed(self, tmp_path):
        """demote_or_rewrite 规则被改为 active → failed。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rule = _make_rule(rule_id="TA-R900", status="active", blocking=False)
        rules_path = _write_rules_yml(tmp_path, [rule])

        candidate = _make_candidate(
            rule_id="TA-R900",
            promotion_type="demote_or_rewrite",
            eligibility="not_eligible",
            proposed_status="proposed",
            proposed_blocking="false",
        )
        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report([candidate]))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        assert report["summary"]["failures"] >= 1

    def test_all_outputs_marked_proposal_only(self, tmp_path):
        """所有输出标记 proposal_only。"""
        from harness.memory_promotion_validation import (
            build_promotion_validation_report,
            render_promotion_validation_json,
            render_promotion_validation_markdown,
            write_promotion_validation_snapshot,
        )

        rules = [_make_rule(rule_id="TA-R900")]
        rules_path = _write_rules_yml(tmp_path, rules)
        promo_path = _write_promotion_report_json(
            tmp_path, _make_promotion_report([_make_candidate()])
        )

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )
        assert report["write_mode"] == "proposal_only"

        json_data = render_promotion_validation_json(report)
        assert json_data["write_mode"] == "proposal_only"

        md = render_promotion_validation_markdown(report)
        assert "proposal_only" in md

        paths = write_promotion_validation_snapshot(report, tmp_path / "out")
        json_content = json.loads(paths["json"].read_text(encoding="utf-8"))
        assert json_content["write_mode"] == "proposal_only"
        md_content = paths["markdown"].read_text(encoding="utf-8")
        assert "proposal_only" in md_content


class TestLoadFunctions:
    """加载函数边界测试。"""

    def test_load_promotion_report_file_not_found(self, tmp_path):
        from harness.memory_promotion_validation import load_promotion_report
        with pytest.raises(FileNotFoundError):
            load_promotion_report(tmp_path / "nonexistent.json")

    def test_load_rules_file_not_found(self, tmp_path):
        from harness.memory_promotion_validation import load_rules
        with pytest.raises(FileNotFoundError):
            load_rules(tmp_path / "nonexistent.yml")

    def test_promotion_report_missing_write_mode(self, tmp_path):
        """promotion report 没有 proposal_only → failed。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rules = [_make_rule(rule_id="TA-R900")]
        rules_path = _write_rules_yml(tmp_path, rules)
        report = _make_promotion_report([_make_candidate()])
        report["write_mode"] = "direct_apply"  # 错误的 write_mode
        promo_path = _write_promotion_report_json(tmp_path, report)

        result = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        basics_items = [
            i for i in result["validation_items"]
            if i.get("check_category") == "promotion_report_basics"
            and i["status"] == "failed"
        ]
        assert any("proposal_only" in i["message"] for i in basics_items)

    def test_candidate_missing_fields(self, tmp_path):
        """candidate 缺少必填字段 → failed。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rules = [_make_rule(rule_id="TA-R900")]
        rules_path = _write_rules_yml(tmp_path, rules)
        report = _make_promotion_report([
            {"rule_id": "TA-R900"}  # 缺很多字段
        ])
        # 修正 write_mode
        report["write_mode"] = "proposal_only"
        promo_path = _write_promotion_report_json(tmp_path, report)

        result = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        basics_items = [
            i for i in result["validation_items"]
            if i.get("check_category") == "promotion_report_basics"
            and i["status"] == "failed"
        ]
        assert any("缺少" in i["message"] for i in basics_items)


class TestSnapshotWriter:
    """Snapshot 写入测试。"""

    def test_write_snapshot_creates_timestamp_files(self, tmp_path):
        from harness.memory_promotion_validation import (
            build_promotion_validation_report,
            write_promotion_validation_snapshot,
        )

        rules = [_make_rule(rule_id="TA-R900")]
        rules_path = _write_rules_yml(tmp_path, rules)
        promo_path = _write_promotion_report_json(
            tmp_path, _make_promotion_report([_make_candidate()])
        )

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )
        output_dir = tmp_path / "out"
        paths = write_promotion_validation_snapshot(report, output_dir)

        assert paths["json"].exists()
        assert paths["markdown"].exists()
        assert "latest" not in paths["json"].name.lower()
        assert "memory_promotion_validation_" in paths["json"].name


class TestEndToEnd:
    """端到端完整流程测试。"""

    def test_full_pipeline_multiple_rules(self, tmp_path):
        """完整 pipeline：多种规则状态混合验证。"""
        from harness.memory_promotion_validation import (
            build_promotion_validation_report,
            render_promotion_validation_json,
            render_promotion_validation_markdown,
            write_promotion_validation_snapshot,
        )

        # 规则 1: proposed_to_active → 已应用（active+blocking=false）
        r1 = _make_rule(rule_id="TA-R901", status="active", blocking=False)
        # 规则 2: proposed_to_active → 未应用（仍为 proposed）
        r2 = _make_rule(rule_id="TA-R902", status="proposed", blocking=False)
        # 规则 3: active_to_blocking → 已正确应用（有回滚计划）
        r3 = _make_rule(
            rule_id="TA-R903", status="active", blocking=True,
            required_checks=[_touch(tmp_path, "harness/checks/TA-R903.py")],
            required_tests=[_touch(tmp_path, "tests/test_TA-R903.py")],
            required_evals=[_touch(tmp_path, "evals/TA-R903.yml")],
            notes="回滚计划：将 blocking 改回 false",
        )
        rules_path = _write_rules_yml(tmp_path, [r1, r2, r3])

        candidates = [
            _make_candidate(rule_id="TA-R901", promotion_type="proposed_to_active",
                            eligibility="eligible", proposed_status="active",
                            proposed_blocking="false"),
            _make_candidate(rule_id="TA-R902", promotion_type="proposed_to_active",
                            eligibility="eligible", proposed_status="active",
                            proposed_blocking="false"),
            _make_candidate(rule_id="TA-R903", promotion_type="active_to_blocking",
                            eligibility="eligible", proposed_status="active",
                            proposed_blocking="true", current_status="active",
                            current_blocking=False),
        ]
        promo_path = _write_promotion_report_json(tmp_path, _make_promotion_report(candidates))

        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        s = report["summary"]
        assert s["candidates_checked"] == 3
        assert s["applied"] >= 2  # TA-R901 + TA-R903
        assert s["pending_manual_actions"] >= 1  # TA-R902
        assert s["failures"] == 0

        json_data = render_promotion_validation_json(report)
        assert json_data["write_mode"] == "proposal_only"

        md = render_promotion_validation_markdown(report)
        assert "TA-R901" in md
        assert "TA-R902" in md
        assert "TA-R903" in md

        paths = write_promotion_validation_snapshot(report, tmp_path / "output")
        assert paths["json"].exists()
        assert paths["markdown"].exists()

    def test_no_files_modified_during_validation(self, tmp_path):
        """验证 validation 不修改任何 docs/memory 文件。"""
        from harness.memory_promotion_validation import build_promotion_validation_report

        rule = _make_rule(rule_id="TA-R900")
        rules_path = _write_rules_yml(tmp_path, [rule])
        initial_rules = rules_path.read_text(encoding="utf-8")

        # 创建 docs/memory 目录下的文件
        docs_memory = tmp_path / "docs" / "memory"
        docs_memory.mkdir(parents=True, exist_ok=True)
        recap = docs_memory / "经验复盘.md"
        recap.write_text("# 测试复盘\n", encoding="utf-8")
        risk = docs_memory / "风险清单.md"
        risk.write_text("# 测试风险\n", encoding="utf-8")
        index_file = docs_memory / "规则来源索引.md"
        index_file.write_text("# 测试索引\n", encoding="utf-8")

        initial_recap = recap.read_text(encoding="utf-8")
        initial_risk = risk.read_text(encoding="utf-8")
        initial_index = index_file.read_text(encoding="utf-8")

        promo_path = _write_promotion_report_json(
            tmp_path, _make_promotion_report([_make_candidate()])
        )

        build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            project_root=tmp_path,
        )

        assert rules_path.read_text(encoding="utf-8") == initial_rules
        assert recap.read_text(encoding="utf-8") == initial_recap
        assert risk.read_text(encoding="utf-8") == initial_risk
        assert index_file.read_text(encoding="utf-8") == initial_index
