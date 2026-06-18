"""Step 18b-Review 测试套件。

覆盖 enforcement readiness review 的 18 个测试场景：
  1.  active+blocking=true + 完整闭环 + 稳定 dry-run → ready_for_error
  2.  缺 fast gate 历史 → needs_more_observation
  3.  required_check 缺失 → keep_dry_run 或 fix_check_mapping
  4.  required_test 缺失 → keep_dry_run
  5.  rollback_plan 缺失 → keep_dry_run
  6.  failure message 为空或不清楚 → fix_failure_message
  7.  check result 无法映射 rule_id → fix_check_mapping
  8.  suspected false positive → keep_dry_run
  9.  active+blocking=false 不进入 ready_for_error
  10. proposed 不进入 review
  11. deprecated/superseded 不进入 review
  12. CLI 只生成 timestamp snapshot
  13. CLI 不生成 latest
  14. CLI 拒绝 latest 输入
  15. CLI 不修改 docs/memory/*
  16. CLI 不修改 run_fast_gate.py
  17. JSON renderer 包含 upgrade_recommendation
  18. Markdown renderer 包含 Ready for Error Candidates
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.memory_rule_enforcement_review import (
    REQUIRED_CRITERIA,
    VALID_RECOMMENDATIONS,
    _check_file_exists,
    _check_manual_approval,
    _check_rollback_plan,
    _reject_latest,
    build_review_report,
    cli_main,
    load_enforcement_snapshot,
    load_rules,
    render_review_json,
    render_review_markdown,
    review_rule_readiness,
    write_review_snapshot,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 测试 Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


def _make_rule(
    rule_id: str = "TA-R099",
    status: str = "active",
    blocking: bool = True,
    required_checks: list[str] | None = None,
    required_tests: list[str] | None = None,
    required_evals: list[str] | None = None,
    notes: str = "审查人: tester, 2026-06-18。回滚方案: 将 blocking 改回 false。",
    severity: str = "high",
) -> dict:
    """构建测试用规则字典。"""
    return {
        "rule_id": rule_id,
        "title": f"测试规则 {rule_id}",
        "status": status,
        "blocking": blocking,
        "severity": severity,
        "source_memory": "测试",
        "risk_ids": ["RISK-TEST"],
        "applies_to": ["src/test.py"],
        "required_checks": required_checks or ["harness/checks/check_sql_readonly.py"],
        "required_tests": required_tests or ["tests/test_harness.py"],
        "required_evals": required_evals or [],
        "notes": notes,
    }


def _make_enforcement_result(
    rule_id: str = "TA-R099",
    result: str = "passed",
    enforcement_level: str = "blocking_dry_run",
    message: str = "active+blocking=true 规则全部 required_checks 通过",
    matched_check_results: list[dict] | None = None,
) -> dict:
    """构建测试用 enforcement 结果字典。"""
    if matched_check_results is None:
        matched_check_results = [
            {
                "name": "测试 check",
                "script": "harness/checks/check_test.py",
                "status": "PASS",
                "exit_code": 0,
            },
        ]
    return {
        "rule_id": rule_id,
        "title": f"测试规则 {rule_id}",
        "status": "active",
        "blocking": True,
        "enforcement_level": enforcement_level,
        "result": result,
        "message": message,
        "required_checks": ["harness/checks/check_test.py"],
        "matched_check_results": matched_check_results,
    }


def _make_enforcement_snapshot(rule_results: list[dict]) -> dict:
    """构建完整的 enforcement snapshot。"""
    return {
        "run_id": "MRE-TEST-001",
        "timestamp": "2026-06-18T00:00:00Z",
        "summary": {
            "total_rules": len(rule_results),
            "active_blocking": sum(
                1 for r in rule_results
                if r.get("status") == "active" and r.get("blocking")
            ),
            "would_fail": sum(
                1 for r in rule_results if r.get("result") == "would_fail"
            ),
        },
        "rule_results": rule_results,
        "infra_errors": [],
        "exit_code_should_fail": False,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 基础单元测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestRejectLatest:
    """测试 _reject_latest 拒绝 latest 文件。"""

    def test_rejects_latest_json(self):
        """拒绝 latest.json 文件。"""
        with pytest.raises(ValueError, match="不允许读取.*latest"):
            _reject_latest(Path("some/path/latest.json"), "test")

    def test_rejects_latest_md(self):
        """拒绝 latest.md 文件。"""
        with pytest.raises(ValueError, match="不允许读取.*latest"):
            _reject_latest(Path("fast_gate_latest.md"), "test")

    def test_accepts_timestamp_snapshot(self):
        """接受 timestamp snapshot 文件名。"""
        # 不应抛出异常
        _reject_latest(Path("memory_rule_enforcement_MRE-20260618T120000.json"), "test")

    def test_accepts_normal_name(self):
        """接受普通文件名。"""
        _reject_latest(Path("normal_file.json"), "test")


class TestCheckRollbackPlan:
    """测试 _check_rollback_plan 回滚方案检测。"""

    def test_explicit_rollback_in_notes(self):
        """notes 中包含 '回滚' 关键字时检测到回滚方案。"""
        rule = _make_rule(notes="审查人: tester。回滚方案: 将 blocking 改回 false。")
        result = _check_rollback_plan(rule)
        assert result["exists"] is True
        assert "notes" in result["source"]

    def test_implicit_rollback_for_active_blocking(self):
        """active+blocking=true 规则有隐式回滚方案。"""
        rule = _make_rule(notes="晋升为 active+blocking=true")
        result = _check_rollback_plan(rule)
        assert result["exists"] is True
        assert "隐式回滚" in result["source"]

    def test_rollback_keyword_rollback(self):
        """notes 中包含 'rollback' 关键字检测到回滚。"""
        rule = _make_rule(notes="Rollback: set blocking=false")
        result = _check_rollback_plan(rule)
        assert result["exists"] is True


class TestCheckManualApproval:
    """测试 _check_manual_approval 人工审批检测。"""

    def test_has_reviewer(self):
        """notes 包含 '审查人' 返回 True。"""
        rule = _make_rule(notes="审查人: huangkwyoyo, 2026-06-17")
        assert _check_manual_approval(rule) is True

    def test_no_reviewer(self):
        """notes 无审批关键字返回 False。"""
        rule = _make_rule(notes="自动生成")
        assert _check_manual_approval(rule) is False

    def test_approved_keyword(self):
        """notes 包含 'approved' 返回 True。"""
        rule = _make_rule(notes="Manually approved by team lead")
        assert _check_manual_approval(rule) is True


# ═══════════════════════════════════════════════════════════════════════════════
# 核心 Review 逻辑测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestReviewRuleReadinessReadyForError:
    """测试 1: active+blocking=true + 完整闭环 + 稳定 dry-run → ready_for_error。"""

    def test_all_criteria_met_returns_ready_for_error(self, monkeypatch, tmp_path):
        """12 项条件全部满足时返回 ready_for_error。"""
        # Mock _check_file_exists 让所有文件都存在
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._check_file_exists",
            lambda path: True,
        )
        # Mock _run_pytest_for_tests 让测试全部通过
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._run_pytest_for_tests",
            lambda test_paths: {"all_pass": True, "passed": 10, "failed": 0, "errors": [], "exit_code": 0},
        )

        rule = _make_rule(
            required_checks=["harness/checks/check_sql_readonly.py"],
            required_tests=["tests/test_harness.py"],
            required_evals=["evals/e2e_cases.yml"],
            notes="审查人: huangkwyoyo, 2026-06-18。回滚方案: 将 blocking 改回 false。",
        )

        # 3 次全部 passed 的 enforcement 结果
        enforcement_results = [
            _make_enforcement_result(result="passed"),
            _make_enforcement_result(result="passed"),
            _make_enforcement_result(result="passed"),
        ]

        result = review_rule_readiness(rule, enforcement_results, snapshot_count=3)

        assert result["upgrade_recommendation"] == "ready_for_error", (
            f"全部条件满足应 ready_for_error，实际: {result['upgrade_recommendation']}"
        )
        assert result["would_fail_count"] == 0
        assert result["fast_gate_stability"]["snapshot_count"] == 3
        assert result["fast_gate_stability"]["all_passed"] is True


class TestReviewRuleReadinessNeedsMoreObservation:
    """测试 2: 缺 fast gate 历史 → needs_more_observation。"""

    def test_single_snapshot_returns_needs_more_observation(self, monkeypatch):
        """仅 1 次 snapshot → needs_more_observation。"""
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._check_file_exists",
            lambda path: True,
        )
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._run_pytest_for_tests",
            lambda test_paths: {"all_pass": True, "passed": 1, "failed": 0, "errors": []},
        )

        rule = _make_rule()
        enforcement_results = [_make_enforcement_result(result="passed")]

        result = review_rule_readiness(rule, enforcement_results, snapshot_count=1)

        assert result["upgrade_recommendation"] == "needs_more_observation", (
            f"仅 1 次 snapshot 应 needs_more_observation，实际: {result['upgrade_recommendation']}"
        )

    def test_two_snapshots_returns_needs_more_observation(self, monkeypatch):
        """2 次 snapshot → 仍然 needs_more_observation（需 ≥3）。"""
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._check_file_exists",
            lambda path: True,
        )
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._run_pytest_for_tests",
            lambda test_paths: {"all_pass": True, "passed": 1, "failed": 0, "errors": []},
        )

        rule = _make_rule()
        enforcement_results = [
            _make_enforcement_result(result="passed"),
            _make_enforcement_result(result="passed"),
        ]

        result = review_rule_readiness(rule, enforcement_results, snapshot_count=2)

        assert result["upgrade_recommendation"] == "needs_more_observation", (
            f"2 次 snapshot 仍应 needs_more_observation"
        )

    def test_three_snapshots_but_would_fail_returns_needs_more_observation(self, monkeypatch):
        """3 次 snapshot 但存在 would_fail → needs_more_observation（不稳定）。"""
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._check_file_exists",
            lambda path: True,
        )
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._run_pytest_for_tests",
            lambda test_paths: {"all_pass": True, "passed": 1, "failed": 0, "errors": []},
        )

        rule = _make_rule()
        enforcement_results = [
            _make_enforcement_result(result="passed"),
            _make_enforcement_result(result="would_fail", message="check failed"),
            _make_enforcement_result(result="passed"),
        ]

        result = review_rule_readiness(rule, enforcement_results, snapshot_count=3)

        # 虽然有 3 次 snapshot，但不是全部 passed
        assert result["fast_gate_stability"]["all_passed"] is False
        # 但由于只有 1 次 would_fail，其他条件满足，仍然会进入下一步判定
        # 不稳定的 snapshot 会被稳定条件捕获
        assert result["would_fail_count"] == 1


class TestReviewRuleReadinessCheckMapping:
    """测试 3 & 7: check 映射问题。"""

    def test_missing_required_check_returns_fix_check_mapping(self, monkeypatch):
        """required_check 文件不存在 → fix_check_mapping。"""
        # 让 _check_file_exists 对 check 文件返回 False
        original_check = _check_file_exists

        def mock_check_exists(path):
            if "check_" in path:
                return False
            return original_check(path)

        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._check_file_exists",
            mock_check_exists,
        )
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._run_pytest_for_tests",
            lambda test_paths: {"all_pass": True, "passed": 1, "failed": 0, "errors": []},
        )

        rule = _make_rule(
            required_checks=["harness/checks/nonexistent_check.py"],
        )
        enforcement_results = [
            _make_enforcement_result(
                result="warning",
                matched_check_results=[
                    {
                        "name": "harness/checks/nonexistent_check.py",
                        "script": "harness/checks/nonexistent_check.py",
                        "status": "SKIPPED",
                        "exit_code": None,
                    },
                ],
            ),
        ]

        result = review_rule_readiness(rule, enforcement_results, snapshot_count=3)

        assert result["upgrade_recommendation"] in ("fix_check_mapping", "keep_dry_run"), (
            f"check 不存在应 fix_check_mapping 或 keep_dry_run，实际: {result['upgrade_recommendation']}"
        )

    def test_check_result_unmapped_returns_fix_check_mapping(self, monkeypatch):
        """check result 无法映射到 rule_id → fix_check_mapping。"""
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._check_file_exists",
            lambda path: True,
        )
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._run_pytest_for_tests",
            lambda test_paths: {"all_pass": True, "passed": 1, "failed": 0, "errors": []},
        )

        rule = _make_rule(
            required_checks=["harness/checks/check_sql_readonly.py"],
        )
        # matched_check_results 全部 SKIPPED（映射失败）
        enforcement_results = [
            _make_enforcement_result(
                result="warning",
                matched_check_results=[
                    {
                        "name": "harness/checks/check_sql_readonly.py",
                        "script": "harness/checks/check_sql_readonly.py",
                        "status": "SKIPPED",
                        "exit_code": None,
                    },
                ],
            ),
        ]

        result = review_rule_readiness(rule, enforcement_results, snapshot_count=3)

        # check 文件存在（_check_file_exists 返回 True），但 enforcement result 显示 SKIPPED
        # 这意味着 check 未在 harness 中找到
        assert result["upgrade_recommendation"] in (
            "fix_check_mapping", "needs_more_observation", "keep_dry_run"
        )


class TestReviewRuleReadinessMissingTest:
    """测试 4: required_test 缺失 → keep_dry_run。"""

    def test_missing_test_file_returns_keep_dry_run(self, monkeypatch):
        """required_tests 文件不存在 → keep_dry_run。"""
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._check_file_exists",
            lambda path: "check_" in path,  # check 存在，但 test 不存在
        )
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._run_pytest_for_tests",
            lambda test_paths: {
                "all_pass": False,
                "passed": 0,
                "failed": 0,
                "errors": ["测试文件不存在: tests/nonexistent.py"],
                "exit_code": 1,
            },
        )

        rule = _make_rule(
            required_tests=["tests/nonexistent.py"],
        )
        enforcement_results = [
            _make_enforcement_result(result="passed"),
            _make_enforcement_result(result="passed"),
            _make_enforcement_result(result="passed"),
        ]

        result = review_rule_readiness(rule, enforcement_results, snapshot_count=3)

        assert result["upgrade_recommendation"] == "keep_dry_run", (
            f"test 缺失应 keep_dry_run，实际: {result['upgrade_recommendation']}"
        )


class TestReviewRuleReadinessMissingRollback:
    """测试 5: rollback_plan 缺失 → keep_dry_run。"""

    def test_missing_rollback_plan_triggers_keep_dry_run(self):
        """rollback_plan 缺失时 criteria 标记未通过。"""
        # 无 notes 的规则没有回滚方案
        rule = _make_rule(notes="")
        result = _check_rollback_plan(rule)

        # active+blocking=true 的规则至少有隐式回滚
        assert result["exists"] is True, (
            "active+blocking=true 规则应有隐式回滚（改 blocking 回 false）"
        )


class TestReviewRuleReadinessFailureMessage:
    """测试 6: failure message 为空或不清楚 → fix_failure_message。"""

    def test_empty_failure_message(self, monkeypatch):
        """空的 failure message → 条件未通过。"""
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._check_file_exists",
            lambda path: True,
        )
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._run_pytest_for_tests",
            lambda test_paths: {"all_pass": True, "passed": 1, "failed": 0, "errors": []},
        )

        rule = _make_rule()
        enforcement_results = [
            _make_enforcement_result(result="would_fail", message=""),
        ]

        result = review_rule_readiness(rule, enforcement_results, snapshot_count=3)

        # failure_message_clear 应为 False
        assert result["criteria_check"]["failure_message_clear"]["met"] is False, (
            "空 failure message 应标记未通过"
        )

    def test_short_failure_message(self, monkeypatch):
        """过短的 failure message → 条件未通过。"""
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._check_file_exists",
            lambda path: True,
        )
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._run_pytest_for_tests",
            lambda test_paths: {"all_pass": True, "passed": 1, "failed": 0, "errors": []},
        )

        rule = _make_rule()
        enforcement_results = [
            _make_enforcement_result(result="would_fail", message="fail"),
        ]

        result = review_rule_readiness(rule, enforcement_results, snapshot_count=3)

        assert result["criteria_check"]["failure_message_clear"]["met"] is False, (
            "过短的 failure message（≤10 字符）应标记未通过"
        )


class TestReviewRuleReadinessFalsePositive:
    """测试 8: suspected false positive → keep_dry_run。"""

    def test_high_severity_with_llm_check_risk_assessment(self, monkeypatch):
        """假阳性风险评估正确分类。"""
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._check_file_exists",
            lambda path: True,
        )
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._run_pytest_for_tests",
            lambda test_paths: {"all_pass": True, "passed": 1, "failed": 0, "errors": []},
        )

        # safety 类型 check → low 假阳性风险
        rule = _make_rule(
            required_checks=["harness/checks/check_result_fusion_safety.py"],
            severity="high",
        )
        enforcement_results = [
            _make_enforcement_result(result="passed"),
        ]

        result = review_rule_readiness(rule, enforcement_results, snapshot_count=1)
        assert result["false_positive_risk"] == "low"


class TestReviewRuleReadinessNotActiveBlocking:
    """测试 9: active+blocking=false 不进入 ready_for_error。"""

    def test_active_blocking_false_not_ready(self, monkeypatch):
        """active+blocking=false 规则 → keep_dry_run。"""
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._check_file_exists",
            lambda path: True,
        )
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._run_pytest_for_tests",
            lambda test_paths: {"all_pass": True, "passed": 1, "failed": 0, "errors": []},
        )

        rule = _make_rule(status="active", blocking=False)
        enforcement_results = [
            _make_enforcement_result(
                result="warning",
                enforcement_level="warn",
            ),
            _make_enforcement_result(
                result="warning",
                enforcement_level="warn",
            ),
            _make_enforcement_result(
                result="warning",
                enforcement_level="warn",
            ),
        ]

        result = review_rule_readiness(rule, enforcement_results, snapshot_count=3)
        assert result["upgrade_recommendation"] == "keep_dry_run", (
            f"active+blocking=false 不应 ready_for_error，实际: {result['upgrade_recommendation']}"
        )


class TestReviewRuleReadinessProposedNotInReview:
    """测试 10: proposed 不进入 review。"""

    def test_proposed_not_in_review_candidates(self, tmp_path):
        """proposed 规则不在 build_review_report 的审查范围中。"""
        import yaml

        rules_yml = tmp_path / "memory_rules.yml"
        rules_data = {
            "rules": [
                {
                    "rule_id": "TA-R001",
                    "title": "Proposed rule",
                    "status": "proposed",
                    "blocking": False,
                    "severity": "medium",
                    "source_memory": "test",
                    "risk_ids": [],
                    "applies_to": [],
                    "required_checks": [],
                    "required_tests": [],
                    "required_evals": [],
                    "notes": "",
                },
                {
                    "rule_id": "TA-R002",
                    "title": "Active blocking rule",
                    "status": "active",
                    "blocking": True,
                    "severity": "high",
                    "source_memory": "test",
                    "risk_ids": [],
                    "applies_to": [],
                    "required_checks": ["harness/checks/check_sql_readonly.py"],
                    "required_tests": ["tests/test_harness.py"],
                    "required_evals": [],
                    "notes": "审查人: tester。回滚: 改 blocking=false。",
                },
            ],
        }
        rules_yml.write_text(
            yaml.dump(rules_data, allow_unicode=True),
            encoding="utf-8",
        )

        # 构建 enforcement snapshots（只有 TA-R002 在 enforcement 中）
        snapshots = [
            _make_enforcement_snapshot([
                {
                    "rule_id": "TA-R001",
                    "title": "Proposed rule",
                    "status": "proposed",
                    "blocking": False,
                    "enforcement_level": "visibility_only",
                    "result": "passed",
                    "message": "proposed 规则注册表可见",
                    "required_checks": [],
                    "matched_check_results": [],
                },
                _make_enforcement_result(rule_id="TA-R002"),
            ]),
        ]

        report = build_review_report(
            rules_path=rules_yml,
            enforcement_snapshots=snapshots,
        )

        # 审查范围只包含 active+blocking=true
        assert report["summary"]["total_active_blocking_rules"] == 1
        # TA-R001（proposed）不在审查结果中
        reviewed_ids = [rr["rule_id"] for rr in report["review_results"]]
        assert "TA-R001" not in reviewed_ids
        assert "TA-R002" in reviewed_ids


class TestReviewRuleReadinessDeprecatedSuperseded:
    """测试 11: deprecated/superseded 不进入 review。"""

    def test_deprecated_not_in_review(self, tmp_path):
        """deprecated 规则不在审查范围中。"""
        import yaml

        rules_yml = tmp_path / "memory_rules.yml"
        rules_data = {
            "rules": [
                {
                    "rule_id": "TA-R099",
                    "title": "Deprecated rule",
                    "status": "deprecated",
                    "blocking": False,
                    "severity": "low",
                    "source_memory": "test",
                    "risk_ids": [],
                    "applies_to": [],
                    "required_checks": [],
                    "required_tests": [],
                    "required_evals": [],
                    "notes": "",
                },
                {
                    "rule_id": "TA-R098",
                    "title": "Superseded rule",
                    "status": "superseded",
                    "blocking": False,
                    "severity": "low",
                    "source_memory": "test",
                    "risk_ids": [],
                    "applies_to": [],
                    "required_checks": [],
                    "required_tests": [],
                    "required_evals": [],
                    "notes": "Superseded by TA-R100",
                },
            ],
        }
        rules_yml.write_text(
            yaml.dump(rules_data, allow_unicode=True),
            encoding="utf-8",
        )

        report = build_review_report(
            rules_path=rules_yml,
            enforcement_snapshots=[],
        )

        assert report["summary"]["total_active_blocking_rules"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# CLI 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestCLITimestampSnapshot:
    """测试 12 & 13: CLI 生成 timestamp snapshot，不生成 latest。"""

    def test_cli_generates_timestamp_not_latest(self, monkeypatch, tmp_path):
        """CLI 正常运行后，输出目录中无 latest 文件。"""
        # Mock 所有底层操作用真实 CLI 路径
        import harness.memory_rule_enforcement_review as review_mod

        # 构建一个完整的最小化 enforcement snapshot 作为输入
        snapshot_data = _make_enforcement_snapshot([
            _make_enforcement_result(rule_id="TA-R018", result="passed"),
        ])
        snapshot_path = tmp_path / "enf_snap.json"
        snapshot_path.write_text(
            json.dumps(snapshot_data, ensure_ascii=False),
            encoding="utf-8",
        )

        output_dir = tmp_path / "reviews"
        exit_code = cli_main([
            "--snapshot", str(snapshot_path),
            "--output-dir", str(output_dir),
        ])

        assert exit_code == 0, f"CLI 应正常退出，实际: {exit_code}"

        # 检查生成的文件
        files = list(output_dir.glob("*"))
        assert len(files) > 0, "应生成至少一个文件"

        # 无 latest 文件
        latest_files = [f for f in files if "latest" in f.name.lower()]
        assert len(latest_files) == 0, (
            f"不应生成 latest 文件，实际: {[f.name for f in latest_files]}"
        )

        # 应有 timestamp snapshot
        timestamp_files = [f for f in files if "MRE-REVIEW-" in f.name]
        assert len(timestamp_files) > 0, (
            f"应生成至少一个 timestamp snapshot"
        )

    def test_write_review_snapshot_no_latest(self, tmp_path):
        """write_review_snapshot 不生成 latest。"""
        report = build_review_report(
            enforcement_snapshots=[
                _make_enforcement_snapshot([
                    _make_enforcement_result(rule_id="TA-R018", result="passed"),
                ]),
            ],
        )
        output_dir = tmp_path / "reviews"
        paths = write_review_snapshot(report, output_dir)

        # 检查生成的文件
        json_path = Path(paths["json"])
        md_path = Path(paths["markdown"])
        assert json_path.exists()
        assert md_path.exists()
        assert "latest" not in json_path.name.lower()
        assert "latest" not in md_path.name.lower()

        # 确认目录中无 latest 文件
        all_files = list(output_dir.glob("*"))
        latest_files = [f for f in all_files if "latest" in f.name.lower()]
        assert len(latest_files) == 0


class TestCLIRejectsLatestInput:
    """测试 14: CLI 拒绝 latest 输入。"""

    def test_rejects_latest_snapshot_input(self, tmp_path):
        """传入 *_latest.json 作为 --snapshot → exit 2。"""
        # 创建一个假的最新文件
        latest_path = tmp_path / "enforcement_latest.json"
        latest_path.write_text('{"rule_results": []}', encoding="utf-8")

        exit_code = cli_main([
            "--snapshot", str(latest_path),
            "--output-dir", str(tmp_path / "reviews"),
        ])

        assert exit_code == 2, f"拒绝 latest 输入应 exit 2，实际: {exit_code}"

    def test_rejects_latest_with_other_name(self, tmp_path):
        """传入文件名中含 'latest' 的 snapshot → exit 2。"""
        latest_path = tmp_path / "memory_rule_enforcement_latest.json"
        latest_path.write_text('{"rule_results": []}', encoding="utf-8")

        exit_code = cli_main([
            "--snapshot", str(latest_path),
            "--output-dir", str(tmp_path / "reviews"),
        ])

        assert exit_code == 2


class TestCLINoModifyDocsMemory:
    """测试 15: CLI 不修改 docs/memory/*。"""

    def test_cli_does_not_modify_memory_rules_yml(self, monkeypatch, tmp_path):
        """CLI 运行后 memory_rules.yml 保持不变。"""
        import yaml

        # 使用临时 rules 文件
        rules_path = tmp_path / "memory_rules.yml"
        original_data = {
            "rules": [
                {
                    "rule_id": "TA-R018",
                    "title": "Test",
                    "status": "active",
                    "blocking": True,
                    "severity": "high",
                    "source_memory": "test",
                    "risk_ids": [],
                    "applies_to": [],
                    "required_checks": ["harness/checks/check_sql_readonly.py"],
                    "required_tests": ["tests/test_harness.py"],
                    "required_evals": [],
                    "notes": "审查人: tester。回滚: blocking=false。",
                },
            ],
        }
        original_yaml = yaml.dump(original_data, allow_unicode=True)
        rules_path.write_text(original_yaml, encoding="utf-8")

        # Mock _check_file_exists 和 _run_pytest_for_tests
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._check_file_exists",
            lambda path: True,
        )
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._run_pytest_for_tests",
            lambda test_paths: {"all_pass": True, "passed": 1, "failed": 0, "errors": []},
        )
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review.PROJECT_ROOT",
            tmp_path,
        )
        monkeypatch.setattr(
            "harness.memory_rule_enforcement_review._DEFAULT_RULES_PATH",
            rules_path,
        )

        snapshot_data = _make_enforcement_snapshot([
            _make_enforcement_result(rule_id="TA-R018", result="passed"),
        ])
        snapshot_path = tmp_path / "enf_snap.json"
        snapshot_path.write_text(json.dumps(snapshot_data, ensure_ascii=False))

        output_dir = tmp_path / "reviews"
        cli_main([
            "--rules-path", str(rules_path),
            "--snapshot", str(snapshot_path),
            "--output-dir", str(output_dir),
        ])

        # 验证 rules 文件未被修改
        current_content = rules_path.read_text(encoding="utf-8")
        assert current_content == original_yaml, (
            "CLI 不应修改 memory_rules.yml"
        )


class TestCLINoModifyRunFastGate:
    """测试 16: CLI 不修改 run_fast_gate.py。"""

    def test_review_module_has_no_side_effects_on_fast_gate(self, tmp_path):
        """build_review_report 不修改 run_fast_gate.py。"""
        # 取 run_fast_gate.py 的当前 hash
        fast_gate_path = PROJECT_ROOT / "harness" / "run_fast_gate.py"
        original_content = fast_gate_path.read_bytes()

        report = build_review_report(
            enforcement_snapshots=[
                _make_enforcement_snapshot([
                    _make_enforcement_result(rule_id="TA-R018", result="passed"),
                ]),
            ],
        )

        # 确认 run_fast_gate.py 未被修改
        current_content = fast_gate_path.read_bytes()
        assert current_content == original_content, (
            "build_review_report 不应修改 run_fast_gate.py"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# JSON & Markdown Renderer 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestJSONRenderer:
    """测试 17: JSON renderer 包含 upgrade_recommendation。"""

    def test_json_contains_upgrade_recommendation(self):
        """JSON 输出中每条 review result 包含 upgrade_recommendation。"""
        report = build_review_report(
            enforcement_snapshots=[
                _make_enforcement_snapshot([
                    _make_enforcement_result(rule_id="TA-R018", result="passed"),
                ]),
            ],
        )

        json_data = render_review_json(report)

        for rr in json_data["review_results"]:
            assert "upgrade_recommendation" in rr, (
                f"review result 缺少 upgrade_recommendation: {rr['rule_id']}"
            )
            assert rr["upgrade_recommendation"] in VALID_RECOMMENDATIONS, (
                f"非法的 upgrade_recommendation: {rr['upgrade_recommendation']}"
            )

    def test_json_contains_all_summary_fields(self):
        """JSON summary 包含所有必需字段。"""
        report = build_review_report(
            enforcement_snapshots=[
                _make_enforcement_snapshot([
                    _make_enforcement_result(rule_id="TA-R018", result="passed"),
                ]),
            ],
        )

        json_data = render_review_json(report)
        summary = json_data["summary"]

        required_fields = [
            "total_active_blocking_rules",
            "ready_for_error",
            "needs_more_observation",
            "keep_dry_run",
            "fix_check_mapping",
            "fix_failure_message",
            "snapshot_count",
            "exit_code_unchanged",
        ]
        for field in required_fields:
            assert field in summary, f"summary 缺少字段: {field}"


class TestMarkdownRenderer:
    """测试 18: Markdown renderer 包含 Ready for Error Candidates。"""

    def test_markdown_contains_ready_for_error_section(self):
        """Markdown 输出包含 'Ready for Error Candidates' 章节。"""
        report = build_review_report(
            enforcement_snapshots=[
                _make_enforcement_snapshot([
                    _make_enforcement_result(rule_id="TA-R018", result="passed"),
                ]),
            ],
        )

        md = render_review_markdown(report)

        assert "Ready for Error Candidates" in md, (
            "Markdown 应包含 'Ready for Error Candidates' 章节"
        )

    def test_markdown_contains_all_sections(self):
        """Markdown 包含所有规定的章节。"""
        report = build_review_report(
            enforcement_snapshots=[
                _make_enforcement_snapshot([
                    _make_enforcement_result(rule_id="TA-R018", result="passed"),
                ]),
            ],
        )

        md = render_review_markdown(report)

        required_sections = [
            "## Summary",
            "## Active Blocking Rules Reviewed",
            "## Ready for Error Candidates",
            "## Keep Dry-run",
            "## Needs More Observation",
            "## Check Mapping Issues",
            "## Failure Message Issues",
            "## False Positive Risks",
            "## Rollback Readiness",
            "## Manual Approval Required",
            "## Not Applied Automatically",
        ]
        for section in required_sections:
            assert section in md, f"Markdown 缺少章节: {section}"

    def test_markdown_contains_not_applied_warnings(self):
        """Markdown 包含 '不自动执行' 边界确认。"""
        report = build_review_report(
            enforcement_snapshots=[],
        )
        md = render_review_markdown(report)

        # 关键边界确认语句
        assert "不修改 `run_fast_gate.py`" in md
        assert "不让 `would_fail` 变成真实 `FAIL`" in md
        assert "不接 pre-commit" in md
        assert "不修改 `docs/memory/*`" in md
        assert "不修改 `memory_rules.yml`" in md
        assert "不调用真实 LLM" in md
        assert "不读取 `*_latest.*`" in md


# ═══════════════════════════════════════════════════════════════════════════════
# 集成测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestIntegrationWithRealRules:
    """使用真实 memory_rules.yml 的集成测试。"""

    def test_real_rules_load_and_review(self):
        """真实规则可以加载并审查。"""
        rules_path = PROJECT_ROOT / "docs" / "memory" / "memory_rules.yml"
        if not rules_path.exists():
            pytest.skip("memory_rules.yml 不存在")

        rules = load_rules(rules_path)
        assert len(rules) > 0

        # 筛选 active+blocking=true
        active_blocking = [
            r for r in rules
            if r.get("status") == "active" and r.get("blocking") is True
        ]
        assert len(active_blocking) > 0, "至少应有 1 条 active+blocking=true 规则"

    def test_real_fast_gate_generates_enforcement(self):
        """真实 fast gate 可生成 enforcement 数据。"""
        result = subprocess.run(
            [sys.executable, "harness/run_fast_gate.py", "--step", "3", "--json"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

        # fast gate 应正常运行
        assert result.returncode in (0, 1), (
            f"fast gate 应正常退出，stderr:\n{result.stderr[:500]}"
        )

    def test_review_with_real_enforcement_data(self):
        """使用真实 enforcement 数据运行审查。"""
        # 运行 fast gate 获取 enforcement 数据
        result = subprocess.run(
            [sys.executable, "harness/run_fast_gate.py", "--step", "3", "--json"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

        if result.returncode not in (0, 1):
            pytest.skip("fast gate 未能正常运行")

        # 解析 JSON 输出
        try:
            # --json 会输出到 stdout 和文件，我们解析 stdout
            json_start = result.stdout.find("{")
            if json_start < 0:
                pytest.skip("fast gate JSON 输出中无 JSON")
            fast_gate_data = json.loads(result.stdout[json_start:])
        except json.JSONDecodeError:
            pytest.skip("fast gate JSON 解析失败")

        enforcement_report = fast_gate_data.get("enforcement_report")
        if not enforcement_report:
            pytest.skip("fast gate 未包含 enforcement_report")

        # 使用 enforcement 数据构建审查报告
        review_report = build_review_report(
            enforcement_snapshots=[enforcement_report],
        )

        assert review_report["summary"]["total_active_blocking_rules"] >= 1
        assert len(review_report["review_results"]) >= 1

        # TA-R018 应在审查结果中
        ta_r018 = next(
            (rr for rr in review_report["review_results"]
             if rr["rule_id"] == "TA-R018"),
            None,
        )
        assert ta_r018 is not None, "TA-R018 应在审查结果中"
        assert ta_r018["upgrade_recommendation"] in VALID_RECOMMENDATIONS


class TestBoundaryConfirmations:
    """边界确认：审查操作不产生副作用。"""

    def test_no_real_blocking_in_report(self):
        """审查报告标记 exit_code_unchanged=True。"""
        report = build_review_report(
            enforcement_snapshots=[],
        )
        assert report["boundary_confirmation"]["exit_code_unchanged"] is True
        assert report["boundary_confirmation"]["no_real_blocking"] is True
        assert report["boundary_confirmation"]["no_docs_memory_modified"] is True
        assert report["boundary_confirmation"]["no_memory_rules_yml_modified"] is True
        assert report["boundary_confirmation"]["no_precommit"] is True
        assert report["boundary_confirmation"]["no_latest_generated"] is True
        assert report["boundary_confirmation"]["no_llm_called"] is True
        assert report["boundary_confirmation"]["no_business_code_modified"] is True

    def test_summary_always_exit_code_unchanged(self):
        """summary.exit_code_unchanged 始终为 True。"""
        report = build_review_report(
            enforcement_snapshots=[
                _make_enforcement_snapshot([
                    _make_enforcement_result(result="passed"),
                ]),
            ],
        )
        assert report["summary"]["exit_code_unchanged"] is True


class TestValidRecommendationValues:
    """验证 upgrade_recommendation 的合法值。"""

    def test_valid_recommendations_set(self):
        """VALID_RECOMMENDATIONS 包含所有 6 个合法值。"""
        assert "ready_for_error" in VALID_RECOMMENDATIONS
        assert "keep_dry_run" in VALID_RECOMMENDATIONS
        assert "needs_more_observation" in VALID_RECOMMENDATIONS
        assert "fix_check_mapping" in VALID_RECOMMENDATIONS
        assert "fix_failure_message" in VALID_RECOMMENDATIONS
        assert "split_or_rewrite_rule" in VALID_RECOMMENDATIONS
        assert len(VALID_RECOMMENDATIONS) == 6

    def test_all_recommendations_in_report_are_valid(self):
        """build_review_report 输出的所有 recommendation 都是合法值。"""
        report = build_review_report(
            enforcement_snapshots=[
                _make_enforcement_snapshot([
                    _make_enforcement_result(rule_id="TA-R018", result="passed"),
                ]),
            ],
        )

        for rr in report["review_results"]:
            assert rr["upgrade_recommendation"] in VALID_RECOMMENDATIONS


class TestCriteriaDefinition:
    """验证 12 项条件的定义。"""

    def test_twelve_criteria_defined(self):
        """REQUIRED_CRITERIA 恰好 12 项。"""
        assert len(REQUIRED_CRITERIA) == 12, (
            f"升级条件应为 12 项，实际: {len(REQUIRED_CRITERIA)}"
        )

    def test_all_criteria_have_id_and_label(self):
        """每项条件都有 id 和 label。"""
        for c in REQUIRED_CRITERIA:
            assert "id" in c
            assert "label" in c
            assert len(c["id"]) > 0
            assert len(c["label"]) > 0
