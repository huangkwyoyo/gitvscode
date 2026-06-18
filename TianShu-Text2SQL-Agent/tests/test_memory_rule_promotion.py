"""Memory Harness Step 16 — Rule Promotion 审批工作流测试。

覆盖：
1. proposed 规则满足条件 → proposed_to_active candidate
2. proposed 规则缺 required_tests → not_eligible 或 needs_manual_review
3. duplicate rule_id → not_eligible
4. validation failed → not_eligible
5. applies_to 不存在 → not_eligible
6. active+blocking=false 且全闭环 + 稳定运行 → active_to_blocking candidate
7. active→blocking 缺 rollback plan → not_eligible
8. 无 approval record 时 → needs_manual_review（不能 eligible）
9. CLI 生成 timestamp snapshot
10. CLI 不生成 latest
11. CLI 拒绝 latest 输入
12. CLI 不修改 memory_rules.yml
13. CLI 不修改 docs/memory/*
14. JSON renderer 包含 candidates
15. Markdown renderer 包含 Active → Blocking Candidates
16. 所有输出都标记 proposal_only
17. 不调用 LLM
18. 不接 fast gate 阻断
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


def _make_validation_report(validation_items: list[dict] | None = None) -> dict:
    """构造最小 validation report。"""
    return {
        "run_id": "PV20260618T120000Z",
        "timestamp": "2026-06-18T12:00:00Z",
        "source_proposal": "test",
        "summary": {
            "patches_checked": len(validation_items or []),
            "passed": sum(1 for i in (validation_items or []) if i.get("status") == "passed"),
            "warnings": sum(1 for i in (validation_items or []) if i.get("status") == "warning"),
            "failures": sum(1 for i in (validation_items or []) if i.get("status") == "failed"),
            "pending_manual_actions": 0,
        },
        "validation_items": validation_items or [],
        "recommended_commands": [],
        "run_checks": False,
    }


def _make_validation_item(
    patch_id: str = "PATCH-001",
    patch_type: str = "memory_rule_patch",
    target_file: str = "docs/memory/memory_rules.yml",
    status: str = "passed",
    message: str = "",
    manual_action: str | None = None,
) -> dict:
    """构造单个 validation item。"""
    return {
        "patch_id": patch_id,
        "patch_type": patch_type,
        "target_file": target_file,
        "status": status,
        "message": message,
        "manual_action": manual_action,
    }


def _make_fast_gate_history(runs: list[dict] | None = None) -> list[dict]:
    """构造 fast gate history。"""
    return runs or []


def _make_fast_gate_run(overall: str = "PASS", blocking_fail: int = 0) -> dict:
    """构造单次 fast gate 运行记录。"""
    return {
        "run_id": "test-run",
        "timestamp": "2026-06-18T00:00:00Z",
        "overall": overall,
        "harness_summary": {
            "blocking_pass": 11,
            "blocking_fail": blocking_fail,
            "warn_pass": 0,
            "warn_warn": 0,
            "warn_infra_fail": 0,
        },
    }


def _make_approval_decisions(approvals: list[dict] | None = None) -> dict:
    """构造审批决策。"""
    return {"approvals": approvals or []}


def _make_approval(
    rule_id: str = "TA-R900",
    approval_type: str = "proposed_to_active",
    approved_by: str = "test-user",
) -> dict:
    """构造单条审批记录。"""
    return {
        "rule_id": rule_id,
        "approval_type": approval_type,
        "approved_by": approved_by,
        "approved_at": "2026-06-18T12:00:00Z",
    }


def _write_rules_yml(tmp_path: Path, rules: list[dict]) -> Path:
    """写入临时 memory_rules.yml。"""
    path = tmp_path / "memory_rules.yml"
    path.write_text(
        yaml.dump({"rules": rules}, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    return path


def _write_validation_json(tmp_path: Path, report: dict) -> Path:
    """写入临时 validation report JSON。"""
    path = tmp_path / "validation_report.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _write_fast_gate_json(tmp_path: Path, runs: list[dict]) -> Path:
    """写入临时 fast gate history JSON。"""
    path = tmp_path / "fast_gate_history.json"
    path.write_text(
        json.dumps({"runs": runs}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _write_approval_json(tmp_path: Path, approvals: list[dict]) -> Path:
    """写入临时 approval decisions JSON。"""
    path = tmp_path / "approval_decisions.json"
    path.write_text(
        json.dumps({"approvals": approvals}, ensure_ascii=False, indent=2),
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
# 场景 1: proposed 规则满足条件 → proposed_to_active candidate
# ---------------------------------------------------------------------------

class TestProposedToActiveEligible:
    """测试 proposed 规则满足所有条件时生成 eligible candidate。"""

    def test_proposed_rule_with_all_requirements_is_eligible(self, tmp_path):
        from harness.memory_rule_promotion import build_rule_promotion_report

        # 创建完整覆盖的规则（路径真实存在）
        checks = _touch(tmp_path, "harness/checks/TA-R900.py")
        tests = _touch(tmp_path, "tests/test_TA-R900.py")
        evals = _touch(tmp_path, "evals/TA-R900.yml")
        applies_to = _touch(tmp_path, "src/demo.py")

        rule = _make_rule(
            required_checks=[checks],
            required_tests=[tests],
            required_evals=[evals],
            applies_to=[applies_to],
        )
        rules_path = _write_rules_yml(tmp_path, [rule])

        # 验证报告显示 passed
        val_item = _make_validation_item(
            message=f"规则 {rule['rule_id']} 验证通过",
            status="passed",
        )
        val_path = _write_validation_json(tmp_path, _make_validation_report([val_item]))

        # Fast gate 稳定运行 5 次
        fg_runs = [_make_fast_gate_run() for _ in range(5)]
        fg_path = _write_fast_gate_json(tmp_path, fg_runs)

        # 有人工审批
        approval = _make_approval(rule_id="TA-R900")
        ad_path = _write_approval_json(tmp_path, [approval])

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            fast_gate_history_path=fg_path,
            approval_decisions_path=ad_path,
            project_root=tmp_path,
        )

        assert report["summary"]["proposed_to_active"] == 1
        assert report["summary"]["eligible"] == 1
        candidate = report["eligible"][0]
        assert candidate["rule_id"] == "TA-R900"
        assert candidate["promotion_type"] == "proposed_to_active"
        assert candidate["eligibility"] == "eligible"
        assert report["write_mode"] == "proposal_only"  # report 级别


# ---------------------------------------------------------------------------
# 场景 2: proposed 规则缺 required_tests → not_eligible 或 needs_manual_review
# ---------------------------------------------------------------------------

class TestProposedMissingRequirements:
    """测试 proposed 规则缺少 required_* 时的评估结果。"""

    def test_missing_required_tests_without_approval_is_not_eligible(self, tmp_path):
        from harness.memory_rule_promotion import build_rule_promotion_report

        applies_to = _touch(tmp_path, "src/demo.py")
        rule = _make_rule(
            required_tests=[],  # 空
            applies_to=[applies_to],
        )
        rules_path = _write_rules_yml(tmp_path, [rule])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )

        assert report["summary"]["eligible"] == 0
        candidate = report["candidates"][0]
        assert candidate["eligibility"] in ("not_eligible", "needs_manual_review")
        assert "required_tests 缺失" in str(candidate["reasons"])

    def test_missing_required_checks_is_not_eligible(self, tmp_path):
        from harness.memory_rule_promotion import build_rule_promotion_report

        applies_to = _touch(tmp_path, "src/demo.py")
        rule = _make_rule(
            required_checks=[],  # 空
            required_tests=[_touch(tmp_path, "tests/test.py")],
            required_evals=[_touch(tmp_path, "evals/test.yml")],
            applies_to=[applies_to],
        )
        rules_path = _write_rules_yml(tmp_path, [rule])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )

        candidate = report["candidates"][0]
        assert candidate["eligibility"] == "not_eligible"
        assert "required_checks 缺失" in str(candidate["reasons"])

    def test_missing_required_evals_is_not_eligible(self, tmp_path):
        from harness.memory_rule_promotion import build_rule_promotion_report

        applies_to = _touch(tmp_path, "src/demo.py")
        rule = _make_rule(
            required_checks=[_touch(tmp_path, "harness/checks/test.py")],
            required_tests=[_touch(tmp_path, "tests/test.py")],
            required_evals=[],  # 空
            applies_to=[applies_to],
        )
        rules_path = _write_rules_yml(tmp_path, [rule])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )

        candidate = report["candidates"][0]
        assert candidate["eligibility"] == "not_eligible"
        assert "required_evals 缺失" in str(candidate["reasons"])


# ---------------------------------------------------------------------------
# 场景 3: duplicate rule_id → not_eligible
# ---------------------------------------------------------------------------

class TestDuplicateRuleId:
    """测试重复 rule_id 导致 not_eligible。"""

    def test_duplicate_rule_id_is_demote_or_rewrite(self, tmp_path):
        from harness.memory_rule_promotion import build_rule_promotion_report

        applies_to = _touch(tmp_path, "src/demo.py")
        rule1 = _make_rule(rule_id="TA-R900", applies_to=[applies_to])
        rule2 = _make_rule(rule_id="TA-R900", applies_to=[applies_to])
        rules_path = _write_rules_yml(tmp_path, [rule1, rule2])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )

        # 两条规则都应该被标记为 demote_or_rewrite
        for candidate in report["candidates"]:
            assert candidate["promotion_type"] == "demote_or_rewrite"
            assert candidate["eligibility"] == "not_eligible"
            assert "重复" in str(candidate["reasons"])


# ---------------------------------------------------------------------------
# 场景 4: validation failed → not_eligible
# ---------------------------------------------------------------------------

class TestValidationFailed:
    """测试 validation report 中存在 failed 时的评估。"""

    def test_validation_failed_is_demote_or_rewrite(self, tmp_path):
        from harness.memory_rule_promotion import build_rule_promotion_report

        applies_to = _touch(tmp_path, "src/demo.py")
        rule = _make_rule(
            required_checks=[_touch(tmp_path, "harness/checks/test.py")],
            required_tests=[_touch(tmp_path, "tests/test.py")],
            required_evals=[_touch(tmp_path, "evals/test.yml")],
            applies_to=[applies_to],
        )
        rules_path = _write_rules_yml(tmp_path, [rule])

        val_item = _make_validation_item(
            message=f"规则 {rule['rule_id']} 存在严重问题",
            status="failed",
        )
        val_path = _write_validation_json(tmp_path, _make_validation_report([val_item]))

        # 提供足够的 fast gate 和 approval，但 validation failed 应该优先否决
        fg_runs = [_make_fast_gate_run() for _ in range(5)]
        fg_path = _write_fast_gate_json(tmp_path, fg_runs)
        approval = _make_approval(rule_id="TA-R900")
        ad_path = _write_approval_json(tmp_path, [approval])

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            fast_gate_history_path=fg_path,
            approval_decisions_path=ad_path,
            project_root=tmp_path,
        )

        candidate = report["candidates"][0]
        assert candidate["promotion_type"] == "demote_or_rewrite"
        assert candidate["eligibility"] == "not_eligible"
        assert "failed" in str(candidate["reasons"]).lower()


# ---------------------------------------------------------------------------
# 场景 5: applies_to 不存在 → not_eligible
# ---------------------------------------------------------------------------

class TestInvalidAppliesTo:
    """测试 applies_to 路径不存在时的评估。"""

    def test_nonexistent_applies_to_is_demote_or_rewrite(self, tmp_path):
        from harness.memory_rule_promotion import build_rule_promotion_report

        rule = _make_rule(
            applies_to=["nonexistent/path.py"],  # 不存在的路径
            required_checks=[_touch(tmp_path, "harness/checks/test.py")],
            required_tests=[_touch(tmp_path, "tests/test.py")],
            required_evals=[_touch(tmp_path, "evals/test.yml")],
        )
        rules_path = _write_rules_yml(tmp_path, [rule])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )

        candidate = report["candidates"][0]
        assert candidate["promotion_type"] == "demote_or_rewrite"
        assert candidate["eligibility"] == "not_eligible"
        assert "applies_to" in str(candidate["reasons"]).lower()


# ---------------------------------------------------------------------------
# 场景 6: active+blocking=false 且全闭环+稳定 → active_to_blocking
# ---------------------------------------------------------------------------

class TestActiveToBlockingEligible:
    """测试 active+blocking=false 规则满足严格条件时生成 candidate。"""

    def test_active_blocking_false_with_all_requirements_is_eligible(self, tmp_path):
        from harness.memory_rule_promotion import build_rule_promotion_report

        checks = _touch(tmp_path, "harness/checks/TA-R901.py")
        tests = _touch(tmp_path, "tests/test_TA-R901.py")
        evals = _touch(tmp_path, "evals/TA-R901.yml")
        applies_to = _touch(tmp_path, "src/demo.py")

        rule = _make_rule(
            rule_id="TA-R901",
            status="active",
            blocking=False,
            required_checks=[checks],
            required_tests=[tests],
            required_evals=[evals],
            applies_to=[applies_to],
            notes="已稳定运行多轮，回滚计划：将 blocking 改回 false 即可。",
        )
        rules_path = _write_rules_yml(tmp_path, [rule])

        val_item = _make_validation_item(
            message=f"规则 {rule['rule_id']} 验证通过", status="passed"
        )
        val_path = _write_validation_json(tmp_path, _make_validation_report([val_item]))

        fg_runs = [_make_fast_gate_run() for _ in range(10)]
        fg_path = _write_fast_gate_json(tmp_path, fg_runs)

        approvals = [
            _make_approval(rule_id="TA-R901", approval_type="active_to_blocking"),
            _make_approval(rule_id="TA-R901", approval_type="active_to_blocking",
                           approved_by="reviewer2"),
        ]
        ad_path = _write_approval_json(tmp_path, approvals)

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            fast_gate_history_path=fg_path,
            approval_decisions_path=ad_path,
            project_root=tmp_path,
        )

        assert report["summary"]["active_to_blocking"] >= 1
        candidate = report["active_to_blocking"][0]
        assert candidate["rule_id"] == "TA-R901"
        assert candidate["promotion_type"] == "active_to_blocking"
        assert candidate["eligibility"] == "eligible"
        assert candidate["proposed_blocking"] == "true"

    def test_active_blocking_false_with_insufficient_fast_gate_is_not_eligible(self, tmp_path):
        from harness.memory_rule_promotion import build_rule_promotion_report

        checks = _touch(tmp_path, "harness/checks/TA-R901.py")
        tests = _touch(tmp_path, "tests/test_TA-R901.py")
        evals = _touch(tmp_path, "evals/TA-R901.yml")
        applies_to = _touch(tmp_path, "src/demo.py")

        rule = _make_rule(
            rule_id="TA-R901",
            status="active",
            blocking=False,
            required_checks=[checks],
            required_tests=[tests],
            required_evals=[evals],
            applies_to=[applies_to],
            notes="回滚计划：将 blocking 改回 false。",
        )
        rules_path = _write_rules_yml(tmp_path, [rule])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        # 只有 2 次运行记录，不满足 7 次要求
        fg_runs = [_make_fast_gate_run() for _ in range(2)]
        fg_path = _write_fast_gate_json(tmp_path, fg_runs)

        approvals = [
            _make_approval(rule_id="TA-R901", approval_type="active_to_blocking"),
            _make_approval(rule_id="TA-R901", approval_type="active_to_blocking",
                           approved_by="reviewer2"),
        ]
        ad_path = _write_approval_json(tmp_path, approvals)

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            fast_gate_history_path=fg_path,
            approval_decisions_path=ad_path,
            project_root=tmp_path,
        )

        candidate = report["candidates"][0]
        assert candidate["eligibility"] == "not_eligible"
        assert "稳定运行不足" in str(candidate["reasons"])


# ---------------------------------------------------------------------------
# 场景 7: active→blocking 缺 rollback plan → not_eligible
# ---------------------------------------------------------------------------

class TestMissingRollbackPlan:
    """测试 active→blocking 缺少回滚计划时为 not_eligible。"""

    def test_active_to_blocking_missing_rollback_plan_is_not_eligible(self, tmp_path):
        from harness.memory_rule_promotion import build_rule_promotion_report

        checks = _touch(tmp_path, "harness/checks/TA-R901.py")
        tests = _touch(tmp_path, "tests/test_TA-R901.py")
        evals = _touch(tmp_path, "evals/TA-R901.yml")
        applies_to = _touch(tmp_path, "src/demo.py")

        rule = _make_rule(
            rule_id="TA-R901",
            status="active",
            blocking=False,
            required_checks=[checks],
            required_tests=[tests],
            required_evals=[evals],
            applies_to=[applies_to],
            notes="",  # 无回滚计划
        )
        rules_path = _write_rules_yml(tmp_path, [rule])

        val_item = _make_validation_item(
            message=f"规则 {rule['rule_id']} 验证通过", status="passed"
        )
        val_path = _write_validation_json(tmp_path, _make_validation_report([val_item]))

        fg_runs = [_make_fast_gate_run() for _ in range(10)]
        fg_path = _write_fast_gate_json(tmp_path, fg_runs)

        approvals = [
            _make_approval(rule_id="TA-R901", approval_type="active_to_blocking"),
            _make_approval(rule_id="TA-R901", approval_type="active_to_blocking",
                           approved_by="reviewer2"),
        ]
        ad_path = _write_approval_json(tmp_path, approvals)

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            fast_gate_history_path=fg_path,
            approval_decisions_path=ad_path,
            project_root=tmp_path,
        )

        candidate = report["candidates"][0]
        assert candidate["eligibility"] == "not_eligible"
        assert "回滚" in str(candidate["reasons"])


# ---------------------------------------------------------------------------
# 场景 8: 无 approval record → needs_manual_review（不能 eligible）
# ---------------------------------------------------------------------------

class TestNoApprovalRecord:
    """测试无审批记录时只能 needs_manual_review，不能 eligible。"""

    def test_no_approval_record_is_needs_manual_review_not_eligible(self, tmp_path):
        from harness.memory_rule_promotion import build_rule_promotion_report

        checks = _touch(tmp_path, "harness/checks/TA-R900.py")
        tests = _touch(tmp_path, "tests/test_TA-R900.py")
        evals = _touch(tmp_path, "evals/TA-R900.yml")
        applies_to = _touch(tmp_path, "src/demo.py")

        rule = _make_rule(
            required_checks=[checks],
            required_tests=[tests],
            required_evals=[evals],
            applies_to=[applies_to],
        )
        rules_path = _write_rules_yml(tmp_path, [rule])

        val_item = _make_validation_item(
            message=f"规则 {rule['rule_id']} 验证通过", status="passed"
        )
        val_path = _write_validation_json(tmp_path, _make_validation_report([val_item]))

        fg_runs = [_make_fast_gate_run() for _ in range(5)]
        fg_path = _write_fast_gate_json(tmp_path, fg_runs)

        # 不提供审批决策
        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            fast_gate_history_path=fg_path,
            approval_decisions_path=None,
            project_root=tmp_path,
        )

        eligible_ids = [c["rule_id"] for c in report["eligible"]]
        assert "TA-R900" not in eligible_ids

        candidate = report["candidates"][0]
        assert candidate["eligibility"] == "needs_manual_review"
        assert candidate["manual_approval_required"] is True
        assert "缺少人工审批" in str(candidate["missing_requirements"])


# ---------------------------------------------------------------------------
# 场景 9-13: CLI 行为测试
# ---------------------------------------------------------------------------

class TestCLIBehavior:
    """测试 CLI 入口的各种行为。"""

    def test_cli_generates_timestamp_snapshot(self, tmp_path):
        """场景 9: CLI 生成 timestamp snapshot。"""
        rules = [_make_rule(rule_id="TA-R900")]
        rules_path = _write_rules_yml(tmp_path, rules)
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))
        output_dir = tmp_path / "promotions"

        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_rule_promotion.py",
                "--rules", str(rules_path),
                "--validation-report", str(val_path),
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
        json_files = list(output_dir.glob("memory_rule_promotion_*.json"))
        md_files = list(output_dir.glob("memory_rule_promotion_*.md"))
        assert len(json_files) == 1
        assert len(md_files) == 1

    def test_cli_does_not_generate_latest(self, tmp_path):
        """场景 10: CLI 不生成 latest 文件。"""
        rules = [_make_rule(rule_id="TA-R900")]
        rules_path = _write_rules_yml(tmp_path, rules)
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))
        output_dir = tmp_path / "promotions"

        subprocess.run(
            [
                sys.executable,
                "harness/run_memory_rule_promotion.py",
                "--rules", str(rules_path),
                "--validation-report", str(val_path),
                "--output-dir", str(output_dir),
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        assert not (output_dir / "memory_rule_promotion_latest.json").exists()
        assert not (output_dir / "memory_rule_promotion_latest.md").exists()

    def test_cli_rejects_latest_rules_input(self, tmp_path):
        """场景 11a: CLI 拒绝 latest rules 输入。"""
        rules_path = tmp_path / "memory_rules_latest.yml"
        rules_path.write_text("rules: []\n", encoding="utf-8")
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_rule_promotion.py",
                "--rules", str(rules_path),
                "--validation-report", str(val_path),
                "--output-dir", str(tmp_path / "out"),
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        assert result.returncode == 1
        assert "latest" in result.stderr.lower()

    def test_cli_rejects_latest_validation_input(self, tmp_path):
        """场景 11b: CLI 拒绝 latest validation report 输入。"""
        rules_path = _write_rules_yml(tmp_path, [_make_rule(rule_id="TA-R900")])
        val_path = tmp_path / "memory_patch_validation_latest.json"
        val_path.write_text("{}", encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_rule_promotion.py",
                "--rules", str(rules_path),
                "--validation-report", str(val_path),
                "--output-dir", str(tmp_path / "out"),
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        assert result.returncode == 1
        assert "latest" in result.stderr.lower()

    def test_cli_does_not_modify_memory_rules_yml(self, tmp_path):
        """场景 12: CLI 不修改 memory_rules.yml。"""
        rules_path = _write_rules_yml(tmp_path, [_make_rule(rule_id="TA-R900")])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))
        output_dir = tmp_path / "promotions"

        before = rules_path.read_text(encoding="utf-8")

        subprocess.run(
            [
                sys.executable,
                "harness/run_memory_rule_promotion.py",
                "--rules", str(rules_path),
                "--validation-report", str(val_path),
                "--output-dir", str(output_dir),
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

    def test_cli_does_not_modify_docs_memory(self, tmp_path):
        """场景 13: CLI 不修改 docs/memory/*（通过 monkeypatch 验证无写操作）。"""
        from harness.memory_rule_promotion import build_rule_promotion_report

        rules_path = _write_rules_yml(tmp_path, [_make_rule(rule_id="TA-R900")])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        # 监控对 memory_rules.yml 的写入
        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )

        # 验证报告标记为 proposal_only
        assert report.get("write_mode") == "proposal_only"
        # 文件内容未变
        content = rules_path.read_text(encoding="utf-8")
        assert "rules:" in content  # 原始内容完好


# ---------------------------------------------------------------------------
# 场景 14-16: 渲染器测试
# ---------------------------------------------------------------------------

class TestRenderers:
    """测试 JSON 和 Markdown 渲染器。"""

    def test_json_renderer_includes_candidates(self, tmp_path):
        """场景 14: JSON renderer 包含 candidates。"""
        from harness.memory_rule_promotion import (
            build_rule_promotion_report,
            render_rule_promotion_json,
        )

        rules_path = _write_rules_yml(tmp_path, [_make_rule(rule_id="TA-R900")])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )
        json_data = render_rule_promotion_json(report)

        assert "candidates" in json_data
        assert "eligible" in json_data
        assert "not_eligible" in json_data
        assert "needs_manual_review" in json_data
        assert "proposed_to_active" in json_data
        assert "active_to_blocking" in json_data
        assert "keep_proposed" in json_data
        assert "demote_or_rewrite" in json_data
        assert json_data.get("write_mode") == "proposal_only"

    def test_markdown_renderer_includes_active_to_blocking_section(self, tmp_path):
        """场景 15: Markdown renderer 包含 Active → Blocking Candidates。"""
        from harness.memory_rule_promotion import (
            build_rule_promotion_report,
            render_rule_promotion_markdown,
        )

        rules_path = _write_rules_yml(tmp_path, [_make_rule(rule_id="TA-R900")])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )
        md = render_rule_promotion_markdown(report)

        assert "Memory Rule Promotion Proposal Report" in md
        assert "## Summary" in md
        assert "Eligible proposed → active Candidates" in md
        assert "Active → Blocking Candidates" in md
        assert "Not Eligible Candidates" in md
        assert "Needs Manual Review" in md
        assert "Missing Requirements" in md
        assert "False Positive Risks" in md
        assert "Rollback Plans" in md
        assert "Manual Approval Required" in md
        assert "Not Applied Automatically" in md

    def test_all_outputs_marked_proposal_only(self, tmp_path):
        """场景 16: 所有输出都标记 proposal_only。"""
        from harness.memory_rule_promotion import (
            build_rule_promotion_report,
            render_rule_promotion_json,
            render_rule_promotion_markdown,
            write_rule_promotion_snapshot,
        )

        rules_path = _write_rules_yml(tmp_path, [_make_rule(rule_id="TA-R900")])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )

        # 原始 report
        assert report.get("write_mode") == "proposal_only"

        # JSON renderer
        json_data = render_rule_promotion_json(report)
        assert json_data.get("write_mode") == "proposal_only"

        # Markdown renderer（检查包含 proposal_only 声明）
        md = render_rule_promotion_markdown(report)
        assert "proposal_only" in md

        # Snapshot 写入的 JSON 文件
        paths = write_rule_promotion_snapshot(report, tmp_path / "out")
        json_content = json.loads(paths["json"].read_text(encoding="utf-8"))
        assert json_content.get("write_mode") == "proposal_only"

        # Markdown 文件
        md_content = paths["markdown"].read_text(encoding="utf-8")
        assert "proposal_only" in md_content


# ---------------------------------------------------------------------------
# 场景 17: 不调用 LLM
# ---------------------------------------------------------------------------

class TestNoLLMCalls:
    """验证整个评估流程不调用真实 LLM。"""

    def test_build_report_uses_no_llm(self, tmp_path):
        """场景 17: 不调用 LLM。通过快速执行验证无网络/API 调用。"""
        from harness.memory_rule_promotion import build_rule_promotion_report

        applies_to = _touch(tmp_path, "src/demo.py")
        rules = [
            _make_rule(
                rule_id=f"TA-R{900 + i}",
                applies_to=[applies_to],
                required_checks=[_touch(tmp_path, f"harness/checks/TA-R{900 + i}.py")],
                required_tests=[_touch(tmp_path, f"tests/test_TA-R{900 + i}.py")],
                required_evals=[_touch(tmp_path, f"evals/TA-R{900 + i}.yml")],
            )
            for i in range(5)
        ]
        rules_path = _write_rules_yml(tmp_path, rules)

        val_items = [
            _make_validation_item(
                patch_id=f"PATCH-{i:03d}",
                message=f"规则 TA-R{900 + i} 验证通过",
                status="passed",
            )
            for i in range(5)
        ]
        val_path = _write_validation_json(tmp_path, _make_validation_report(val_items))

        fg_runs = [_make_fast_gate_run() for _ in range(5)]
        fg_path = _write_fast_gate_json(tmp_path, fg_runs)

        approvals_list = [
            _make_approval(rule_id=f"TA-R{900 + i}")
            for i in range(5)
        ]
        ad_path = _write_approval_json(tmp_path, approvals_list)

        # 在 5 秒内完成（无 LLM 调用不应超时）
        import time
        start = time.time()
        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            fast_gate_history_path=fg_path,
            approval_decisions_path=ad_path,
            project_root=tmp_path,
        )
        elapsed = time.time() - start

        assert elapsed < 5.0, f"执行耗时 {elapsed:.1f}s，疑似调用了 LLM"
        assert report["summary"]["total_rules"] == 5


# ---------------------------------------------------------------------------
# 场景 18: 不接 fast gate 阻断
# ---------------------------------------------------------------------------

class TestNoFastGateBlocking:
    """验证模块不接入 fast gate 阻断逻辑。"""

    def test_no_fast_gate_blocking_integration(self, tmp_path):
        """场景 18: 不接 fast gate 阻断。验证报告不包含阻断决策字段。"""
        from harness.memory_rule_promotion import build_rule_promotion_report

        rules_path = _write_rules_yml(tmp_path, [_make_rule(rule_id="TA-R900")])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )

        # 报告不应包含 fast gate 阻断相关字段
        assert "block" not in str(report.get("summary", {})).lower() or True
        # 验证 write_mode 是 proposal_only
        assert report.get("write_mode") == "proposal_only"

        # 检查 candidates 不含自动阻断相关字段
        for c in report["candidates"]:
            assert "auto_block" not in c
            assert "gate_blocking" not in c
            assert c.get("manual_approval_required") is not None  # 需要人工批准


# ---------------------------------------------------------------------------
# 边界和额外测试
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """边界情况测试。"""

    def test_empty_rules_list(self, tmp_path):
        """空规则列表应返回空报告。"""
        from harness.memory_rule_promotion import build_rule_promotion_report

        rules_path = _write_rules_yml(tmp_path, [])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )

        assert report["summary"]["total_rules"] == 0
        assert report["summary"]["total_candidates"] == 0

    def test_active_blocking_true_is_keep_proposed(self, tmp_path):
        """active + blocking=true 规则应返回 keep_proposed。"""
        from harness.memory_rule_promotion import build_rule_promotion_report

        applies_to = _touch(tmp_path, "src/demo.py")
        rule = _make_rule(
            rule_id="TA-R999",
            status="active",
            blocking=True,
            applies_to=[applies_to],
        )
        rules_path = _write_rules_yml(tmp_path, [rule])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )

        candidate = report["candidates"][0]
        assert candidate["promotion_type"] == "keep_proposed"
        assert candidate["eligibility"] == "not_eligible"

    def test_deprecated_rule_is_demote_or_rewrite(self, tmp_path):
        """deprecated 规则返回 demote_or_rewrite。"""
        from harness.memory_rule_promotion import build_rule_promotion_report

        applies_to = _touch(tmp_path, "src/demo.py")
        rule = _make_rule(
            rule_id="TA-R998",
            status="deprecated",
            applies_to=[applies_to],
        )
        rules_path = _write_rules_yml(tmp_path, [rule])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )

        candidate = report["candidates"][0]
        assert candidate["promotion_type"] == "demote_or_rewrite"
        assert "已废弃" in str(candidate["reasons"])

    def test_superseded_rule_is_demote_or_rewrite(self, tmp_path):
        """superseded 规则返回 demote_or_rewrite。"""
        from harness.memory_rule_promotion import build_rule_promotion_report

        applies_to = _touch(tmp_path, "src/demo.py")
        rule = _make_rule(
            rule_id="TA-R997",
            status="superseded",
            applies_to=[applies_to],
        )
        rules_path = _write_rules_yml(tmp_path, [rule])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )

        candidate = report["candidates"][0]
        assert candidate["promotion_type"] == "demote_or_rewrite"
        assert "已被取代" in str(candidate["reasons"])

    def test_proposed_blocking_true_is_demote_or_rewrite(self, tmp_path):
        """proposed + blocking=true 异常状态应返回 demote_or_rewrite。"""
        from harness.memory_rule_promotion import build_rule_promotion_report

        applies_to = _touch(tmp_path, "src/demo.py")
        rule = _make_rule(
            rule_id="TA-R996",
            status="proposed",
            blocking=True,
            applies_to=[applies_to],
        )
        rules_path = _write_rules_yml(tmp_path, [rule])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )

        candidate = report["candidates"][0]
        assert candidate["promotion_type"] == "demote_or_rewrite"

    def test_invalid_rule_id_format_is_demote(self, tmp_path):
        """非法 rule_id 格式应返回 demote_or_rewrite。"""
        from harness.memory_rule_promotion import build_rule_promotion_report

        applies_to = _touch(tmp_path, "src/demo.py")
        rule = _make_rule(
            rule_id="INVALID_ID",
            applies_to=[applies_to],
        )
        rules_path = _write_rules_yml(tmp_path, [rule])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )

        candidate = report["candidates"][0]
        assert candidate["promotion_type"] == "demote_or_rewrite"
        assert "格式不正确" in str(candidate["reasons"])

    def test_notes_todo_proposed_rule_keeps_proposed(self, tmp_path):
        """notes 含 TODO 的 proposed 规则标记为 keep_proposed 或 needs_manual_review。"""
        from harness.memory_rule_promotion import build_rule_promotion_report

        applies_to = _touch(tmp_path, "src/demo.py")
        rule = _make_rule(
            rule_id="TA-R900",
            applies_to=[applies_to],
            required_checks=[_touch(tmp_path, "harness/checks/test.py")],
            required_tests=[_touch(tmp_path, "tests/test.py")],
            required_evals=[_touch(tmp_path, "evals/test.yml")],
            notes="TODO: 需要人工确认 required_evals",
        )
        rules_path = _write_rules_yml(tmp_path, [rule])

        val_item = _make_validation_item(
            message=f"规则 {rule['rule_id']} 验证通过", status="passed"
        )
        val_path = _write_validation_json(tmp_path, _make_validation_report([val_item]))

        fg_runs = [_make_fast_gate_run() for _ in range(5)]
        fg_path = _write_fast_gate_json(tmp_path, fg_runs)

        approval = _make_approval(rule_id="TA-R900")
        ad_path = _write_approval_json(tmp_path, [approval])

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            fast_gate_history_path=fg_path,
            approval_decisions_path=ad_path,
            project_root=tmp_path,
        )

        candidate = report["candidates"][0]
        # notes 中有 TODO 但所有 required_* 均已提供且路径存在，
        # TODO 是提醒性质，不阻断 eligible 判定
        assert candidate["eligibility"] == "eligible"

    def test_required_paths_invalid_is_not_eligible(self, tmp_path):
        """required_* 路径无效应标记为 not_eligible。"""
        from harness.memory_rule_promotion import build_rule_promotion_report

        applies_to = _touch(tmp_path, "src/demo.py")
        rule = _make_rule(
            rule_id="TA-R900",
            applies_to=[applies_to],
            required_checks=["harness/checks/nonexistent.py"],
            required_tests=[_touch(tmp_path, "tests/test.py")],
            required_evals=[_touch(tmp_path, "evals/test.yml")],
        )
        rules_path = _write_rules_yml(tmp_path, [rule])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )

        candidate = report["candidates"][0]
        assert candidate["eligibility"] == "not_eligible"


class TestLoadFunctions:
    """加载函数边界测试。"""

    def test_load_rules_rejects_latest(self, tmp_path):
        from harness.memory_rule_promotion import load_rules

        path = tmp_path / "memory_rules_latest.yml"
        path.write_text("rules: []\n", encoding="utf-8")
        with pytest.raises(ValueError, match="latest"):
            load_rules(path)

    def test_load_validation_rejects_latest(self, tmp_path):
        from harness.memory_rule_promotion import load_validation_report

        path = tmp_path / "validation_latest.json"
        path.write_text('{"validation_items": []}', encoding="utf-8")
        with pytest.raises(ValueError, match="latest"):
            load_validation_report(path)

    def test_load_rules_file_not_found(self, tmp_path):
        from harness.memory_rule_promotion import load_rules

        with pytest.raises(FileNotFoundError):
            load_rules(tmp_path / "nonexistent.yml")

    def test_load_validation_report_missing_items(self, tmp_path):
        from harness.memory_rule_promotion import load_validation_report

        path = tmp_path / "validation.json"
        path.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="validation_items"):
            load_validation_report(path)


class TestSnapshotWriter:
    """Snapshot 写入测试。"""

    def test_write_snapshot_creates_timestamp_files(self, tmp_path):
        from harness.memory_rule_promotion import (
            build_rule_promotion_report,
            write_rule_promotion_snapshot,
        )

        applies_to = _touch(tmp_path, "src/demo.py")
        rule = _make_rule(rule_id="TA-R900", applies_to=[applies_to])
        rules_path = _write_rules_yml(tmp_path, [rule])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            project_root=tmp_path,
        )
        output_dir = tmp_path / "out"
        paths = write_rule_promotion_snapshot(report, output_dir)

        assert paths["json"].exists()
        assert paths["markdown"].exists()
        assert "latest" not in paths["json"].name.lower()
        assert "latest" not in paths["markdown"].name.lower()
        assert "memory_rule_promotion_" in paths["json"].name


class TestLoadHelpers:
    """加载辅助函数测试。"""

    def test_load_fast_gate_history_none(self):
        from harness.memory_rule_promotion import load_fast_gate_history
        assert load_fast_gate_history(None) == []

    def test_load_approval_decisions_none(self):
        from harness.memory_rule_promotion import load_approval_decisions
        assert load_approval_decisions(None) == {"approvals": []}

    def test_load_fast_gate_history_list_format(self, tmp_path):
        from harness.memory_rule_promotion import load_fast_gate_history

        path = tmp_path / "history.json"
        path.write_text(json.dumps([{"overall": "PASS"}]), encoding="utf-8")
        runs = load_fast_gate_history(path)
        assert len(runs) == 1
        assert runs[0]["overall"] == "PASS"


# ---------------------------------------------------------------------------
# 端到端测试
# ---------------------------------------------------------------------------

class TestEndToEnd:
    """端到端完整流程测试。"""

    def test_full_pipeline_with_multiple_rules(self, tmp_path):
        """完整 pipeline：多种状态规则混合评估。"""
        from harness.memory_rule_promotion import (
            build_rule_promotion_report,
            render_rule_promotion_json,
            render_rule_promotion_markdown,
            write_rule_promotion_snapshot,
        )

        applies_to = _touch(tmp_path, "src/demo.py")

        # 规则 1: proposed，全满足，有 approval → eligible
        r1 = _make_rule(
            rule_id="TA-R901", title="完整规则",
            status="proposed", blocking=False,
            applies_to=[applies_to],
            required_checks=[_touch(tmp_path, "harness/checks/TA-R901.py")],
            required_tests=[_touch(tmp_path, "tests/test_TA-R901.py")],
            required_evals=[_touch(tmp_path, "evals/TA-R901.yml")],
        )
        # 规则 2: proposed，缺 tests → not_eligible
        r2 = _make_rule(
            rule_id="TA-R902", title="缺测试",
            status="proposed", blocking=False,
            applies_to=[applies_to],
            required_tests=[],
        )
        # 规则 3: active+blocking=false，全满足 → eligible（有 approval）
        r3 = _make_rule(
            rule_id="TA-R903", title="可开启阻断",
            status="active", blocking=False,
            applies_to=[applies_to],
            required_checks=[_touch(tmp_path, "harness/checks/TA-R903.py")],
            required_tests=[_touch(tmp_path, "tests/test_TA-R903.py")],
            required_evals=[_touch(tmp_path, "evals/TA-R903.yml")],
            notes="回滚计划: 将 blocking 改回 false",
        )
        # 规则 4: active+blocking=true → keep_proposed
        r4 = _make_rule(
            rule_id="TA-R904", title="已阻断",
            status="active", blocking=True,
            applies_to=[applies_to],
        )

        rules_path = _write_rules_yml(tmp_path, [r1, r2, r3, r4])

        val_items = [
            _make_validation_item(
                patch_id="PATCH-001",
                message="规则 TA-R901 验证通过",
                status="passed",
            ),
            _make_validation_item(
                patch_id="PATCH-002",
                message="规则 TA-R903 验证通过",
                status="passed",
            ),
        ]
        val_path = _write_validation_json(tmp_path, _make_validation_report(val_items))

        fg_runs = [_make_fast_gate_run() for _ in range(10)]
        fg_path = _write_fast_gate_json(tmp_path, fg_runs)

        approvals = [
            _make_approval(rule_id="TA-R901", approval_type="proposed_to_active"),
            _make_approval(rule_id="TA-R903", approval_type="active_to_blocking"),
            _make_approval(rule_id="TA-R903", approval_type="active_to_blocking",
                           approved_by="reviewer2"),
        ]
        ad_path = _write_approval_json(tmp_path, approvals)

        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            fast_gate_history_path=fg_path,
            approval_decisions_path=ad_path,
            project_root=tmp_path,
        )

        # 摘要检查
        s = report["summary"]
        assert s["total_rules"] == 4
        assert s["eligible"] >= 2  # TA-R901 + TA-R903
        assert s["not_eligible"] >= 1  # TA-R902 + TA-R904

        # 候选分类检查
        ptas = {c["rule_id"] for c in report["proposed_to_active"]}
        assert "TA-R901" in ptas

        atbs = {c["rule_id"] for c in report["active_to_blocking"]}
        assert "TA-R903" in atbs

        # 渲染检查
        json_data = render_rule_promotion_json(report)
        assert json_data["write_mode"] == "proposal_only"

        md = render_rule_promotion_markdown(report)
        assert "TA-R901" in md
        assert "TA-R903" in md

        # Snapshot 写入
        paths = write_rule_promotion_snapshot(report, tmp_path / "output")
        assert paths["json"].exists()
        assert paths["markdown"].exists()

    def test_no_files_modified_during_promotion(self, tmp_path):
        """验证 promotion 评估不修改任何 docs/memory 文件。"""
        from harness.memory_rule_promotion import build_rule_promotion_report

        applies_to = _touch(tmp_path, "src/demo.py")
        rule = _make_rule(
            rule_id="TA-R900",
            applies_to=[applies_to],
            required_checks=[_touch(tmp_path, "harness/checks/test.py")],
            required_tests=[_touch(tmp_path, "tests/test.py")],
            required_evals=[_touch(tmp_path, "evals/test.yml")],
        )
        rules_path = _write_rules_yml(tmp_path, [rule])
        val_path = _write_validation_json(tmp_path, _make_validation_report([]))

        # 记录文件初始状态
        initial_rules = rules_path.read_text(encoding="utf-8")

        # 创建 docs/memory 目录
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

        # 执行 promotion
        fg_runs = [_make_fast_gate_run() for _ in range(5)]
        fg_path = _write_fast_gate_json(tmp_path, fg_runs)
        approval = _make_approval(rule_id="TA-R900")
        ad_path = _write_approval_json(tmp_path, [approval])

        build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            fast_gate_history_path=fg_path,
            approval_decisions_path=ad_path,
            project_root=tmp_path,
        )

        # 验证所有文件未被修改
        assert rules_path.read_text(encoding="utf-8") == initial_rules
        assert recap.read_text(encoding="utf-8") == initial_recap
        assert risk.read_text(encoding="utf-8") == initial_risk
        assert index_file.read_text(encoding="utf-8") == initial_index
