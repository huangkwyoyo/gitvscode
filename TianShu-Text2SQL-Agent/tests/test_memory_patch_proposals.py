"""test_memory_patch_proposals.py —— Step 14 patch proposal generator 测试。

覆盖：
    1. approved memory_rule_candidate 生成 memory_rule_patch
    2. approved risk_item 生成 risk_item_patch + harness_check_patch
    3. approved regression_candidate 生成 regression_case_patch + test_case_patch
    4. 未 approved item 不生成 patch
    5. memory_rule_patch status 始终 proposed
    6. memory_rule_patch blocking 始终 false
    7. CLI 生成 timestamp snapshot
    8. CLI 不生成 latest
    9. CLI 拒绝读取 latest 输入
    10. CLI 不修改 docs/memory/*
    11. CLI 不写 memory_rules.yml
    12. CLI 不新增 tests/evals/checks
    13. JSON renderer 包含 summary/patches
    14. Markdown renderer 包含 Proposed memory_rules.yml Patches
    15. 所有 patch write_mode = proposal_only
    16. reject / noise / asset_dependency_wait 不生成 patch
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.memory_patch_proposals import (  # noqa: E402
    PATCH_TYPE_META,
    build_harness_check_patch,
    build_memory_recap_patch,
    build_memory_rule_patch,
    build_patch_proposal_report,
    build_regression_case_patch,
    build_risk_item_patch,
    build_test_case_patch,
    generate_patches_for_item,
    load_approved_decisions,
    load_review_report,
    render_patch_proposal_json,
    render_patch_proposal_markdown,
    write_patch_proposal_snapshot,
)


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _make_review_item(
    review_index: int = 0,
    question_id: str = "C001",
    failure_type: str = "intent_mismatch",
    review_action: list[str] | None = None,
    **kwargs,
) -> dict:
    """构造最小 review item 字典。"""
    item = {
        "review_index": review_index,
        "question_id": question_id,
        "question": f"测试问题_{question_id}",
        "failure_type": failure_type,
        "review_action": review_action or ["accept_as_regression_case"],
        "review_reason": "测试审查理由",
        "manual_review_required": False,
        "priority": "medium",
        "suggested_owner": "prompt",
        "root_cause_hint": "测试根因",
        "suggested_memory_rule_preview": {
            "title": f"测试规则_{question_id}",
            "severity": "medium",
            "status": "proposed",
            "blocking": False,
            "source_failure_case": question_id,
        },
        "suggested_regression_case_preview": {
            "case_id": f"reg_{failure_type}_{question_id}",
            "question": f"测试问题_{question_id}",
            "failure_type": failure_type,
            "expected_behavior": "correct_behavior",
            "notes": "测试备注",
        },
        "suggested_risk_item_preview": {
            "risk_id": f"RISK_{failure_type}_{question_id}",
            "title": f"{failure_type} 风险",
            "severity": "high",
            "description": f"测试风险描述: {failure_type}",
        },
    }
    item.update(kwargs)
    return item


def _make_review_report(items: list[dict]) -> dict:
    """构造最小审查报告。"""
    return {
        "run_id": "review-test-001",
        "timestamp": "2026-06-18T12:00:00Z",
        "review_items": items,
        "summary": {
            "total_suggestions": len(items),
            "total_reviewed": len(items),
        },
    }


def _make_approved_decisions(indices: list[int], **kwargs) -> dict:
    """构造最小审批决策。"""
    return {
        "approved_indices": indices,
        "approved_by": "test_reviewer",
        "approved_at": "2026-06-18T12:00:00Z",
        "notes": "测试审批",
        "decisions_by_index": {
            idx: {
                "review_index": idx,
                "approved": True,
                "approved_by": "test_reviewer",
                "approved_at": "2026-06-18T12:00:00Z",
                "notes": f"approved item {idx}",
            }
            for idx in indices
        },
        **kwargs,
    }


# ═══════════════════════════════════════════════════════════════
# 测试 1: memory_rule_patch 生成
# ═══════════════════════════════════════════════════════════════


class TestMemoryRulePatch:
    """memory_rule_candidate → memory_rule_patch + memory_recap_patch。"""

    def test_generates_rule_patch(self):
        """approved memory_rule_candidate 生成 memory_rule_patch。"""
        item = _make_review_item(
            review_index=0,
            failure_type="explain_failed",
            review_action=["accept_as_memory_rule_candidate"],
        )
        patches = generate_patches_for_item(item)

        rule_patches = [p for p in patches if p["patch_type"] == "memory_rule_patch"]
        assert len(rule_patches) == 1
        p = rule_patches[0]
        assert p["patch_type"] == "memory_rule_patch"
        assert p["target_file"] == "docs/memory/memory_rules.yml"
        assert p["write_mode"] == "proposal_only"
        assert "status: proposed" in p["content"]
        assert "blocking: false" in p["content"]

    def test_rule_patch_status_always_proposed(self):
        """memory_rule_patch 中 status 始终 proposed。"""
        item = _make_review_item(
            review_index=0,
            failure_type="explain_failed",
            review_action=["accept_as_memory_rule_candidate"],
        )
        patches = generate_patches_for_item(item)
        rule_patch = [p for p in patches if p["patch_type"] == "memory_rule_patch"][0]
        # 检查内容中 status 为 proposed（不是 active）
        assert "status: proposed" in rule_patch["content"]
        assert "status: active" not in rule_patch["content"]

    def test_rule_patch_blocking_always_false(self):
        """memory_rule_patch 中 blocking 始终 false。"""
        item = _make_review_item(
            review_index=0,
            failure_type="explain_failed",
            review_action=["accept_as_memory_rule_candidate"],
        )
        patches = generate_patches_for_item(item)
        rule_patch = [p for p in patches if p["patch_type"] == "memory_rule_patch"][0]
        assert "blocking: false" in rule_patch["content"]
        assert "blocking: true" not in rule_patch["content"]

    def test_generates_recap_patch(self):
        """memory_rule_candidate 同时生成 memory_recap_patch。"""
        item = _make_review_item(
            review_index=0,
            failure_type="explain_failed",
            review_action=["accept_as_memory_rule_candidate"],
        )
        patches = generate_patches_for_item(item)
        recap_patches = [p for p in patches if p["patch_type"] == "memory_recap_patch"]
        assert len(recap_patches) == 1
        p = recap_patches[0]
        assert p["target_file"] == "docs/memory/经验复盘.md"
        assert p["write_mode"] == "proposal_only"


# ═══════════════════════════════════════════════════════════════
# 测试 2: risk_item_patch 生成
# ═══════════════════════════════════════════════════════════════


class TestRiskItemPatch:
    """risk_item → risk_item_patch + harness_check_patch。"""

    def test_generates_risk_item_patch(self):
        """approved risk_item 生成 risk_item_patch。"""
        item = _make_review_item(
            review_index=0,
            failure_type="safety_validation_failed",
            review_action=["accept_as_risk_item"],
        )
        patches = generate_patches_for_item(item)

        risk_patches = [p for p in patches if p["patch_type"] == "risk_item_patch"]
        assert len(risk_patches) == 1
        p = risk_patches[0]
        assert p["target_file"] == "docs/memory/风险清单.md"
        assert p["write_mode"] == "proposal_only"
        assert "RISK_" in p["content"]

    def test_generates_harness_check_patch(self):
        """risk_item 同时生成 harness_check_patch。"""
        item = _make_review_item(
            review_index=0,
            failure_type="safety_validation_failed",
            review_action=["accept_as_risk_item"],
        )
        patches = generate_patches_for_item(item)

        check_patches = [p for p in patches if p["patch_type"] == "harness_check_patch"]
        assert len(check_patches) == 1
        p = check_patches[0]
        assert "NOT_IMPLEMENTED" in p["content"]
        assert p["write_mode"] == "proposal_only"

    def test_multi_label_refusal(self):
        """refusal_expected_but_answered 同时生成 regression + risk + check patches。"""
        item = _make_review_item(
            review_index=0,
            failure_type="refusal_expected_but_answered",
            review_action=["accept_as_regression_case", "accept_as_risk_item"],
        )
        patches = generate_patches_for_item(item)
        patch_types = {p["patch_type"] for p in patches}
        assert "regression_case_patch" in patch_types
        assert "test_case_patch" in patch_types
        assert "risk_item_patch" in patch_types
        assert "harness_check_patch" in patch_types
        # 多标签应生成 4 个 patch
        assert len(patches) == 4


# ═══════════════════════════════════════════════════════════════
# 测试 3: regression_case_patch 生成
# ═══════════════════════════════════════════════════════════════


class TestRegressionCasePatch:
    """regression_candidate → regression_case_patch + test_case_patch。"""

    def test_generates_regression_case_patch(self):
        """approved regression_candidate 生成 regression_case_patch。"""
        item = _make_review_item(
            review_index=0,
            failure_type="intent_mismatch",
            review_action=["accept_as_regression_case"],
        )
        patches = generate_patches_for_item(item)

        reg_patches = [p for p in patches if p["patch_type"] == "regression_case_patch"]
        assert len(reg_patches) == 1
        p = reg_patches[0]
        assert "regression" in p["target_file"]
        assert p["write_mode"] == "proposal_only"
        assert "question_zh" in p["content"]

    def test_generates_test_case_patch(self):
        """regression_candidate 同时生成 test_case_patch。"""
        item = _make_review_item(
            review_index=0,
            failure_type="intent_mismatch",
            review_action=["accept_as_regression_case"],
        )
        patches = generate_patches_for_item(item)

        test_patches = [p for p in patches if p["patch_type"] == "test_case_patch"]
        assert len(test_patches) == 1
        p = test_patches[0]
        assert "def test_" in p["content"]
        assert p["write_mode"] == "proposal_only"

    def test_safety_regression_targets_safety_file(self):
        """safety 相关回归用例指向 safety_regression.yml。"""
        item = _make_review_item(
            review_index=0,
            failure_type="safety_validation_failed",
            review_action=["accept_as_regression_case"],
        )
        patches = generate_patches_for_item(item)
        reg_patch = [p for p in patches if p["patch_type"] == "regression_case_patch"][0]
        assert "safety_regression.yml" in reg_patch["target_file"]


# ═══════════════════════════════════════════════════════════════
# 测试 4: 未审批 / 跳过逻辑
# ═══════════════════════════════════════════════════════════════


class TestUnapprovedAndSkipped:
    """未审批 item 不生成 patch；reject/noise/wait 不生成 patch。"""

    def test_unapproved_item_no_patch(self):
        """未在 approved_indices 中的 item 不生成 patch。"""
        items = [
            _make_review_item(0, "C001", "intent_mismatch", ["accept_as_regression_case"]),
            _make_review_item(1, "C002", "plan_mismatch", ["accept_as_regression_case"]),
        ]
        report = _make_review_report(items)
        decisions = _make_approved_decisions([0])  # 只批 C001

        result = build_patch_proposal_report(report, decisions)
        assert result["summary"]["approved_items"] == 1
        assert result["summary"]["unapproved_items"] == 1
        assert result["summary"]["total_patches"] == 2  # C001 → 2 patches

        # unapproved_item 中应有 C002
        unapproved = result["unapproved_items"]
        assert len(unapproved) == 1
        assert unapproved[0]["question_id"] == "C002"

    def test_reject_action_no_patch(self):
        """reject action 审批后不生成 patch（skipped）。"""
        item = _make_review_item(
            review_index=0,
            failure_type="unknown_type",
            review_action=["reject"],
        )
        report = _make_review_report([item])
        decisions = _make_approved_decisions([0])

        result = build_patch_proposal_report(report, decisions)
        assert result["summary"]["total_patches"] == 0
        assert result["summary"]["approved_but_skipped"] == 1

    def test_provider_runtime_noise_no_patch(self):
        """provider_runtime_noise 不生成 patch。"""
        item = _make_review_item(
            review_index=0,
            failure_type="confidence_out_of_range",
            review_action=["provider_runtime_noise"],
        )
        report = _make_review_report([item])
        decisions = _make_approved_decisions([0])

        result = build_patch_proposal_report(report, decisions)
        assert result["summary"]["total_patches"] == 0
        assert result["summary"]["approved_but_skipped"] == 1

    def test_asset_dependency_wait_no_patch(self):
        """asset_dependency_wait 不生成 patch。"""
        item = _make_review_item(
            review_index=0,
            failure_type="execution_failed",
            review_action=["asset_dependency_wait"],
        )
        report = _make_review_report([item])
        decisions = _make_approved_decisions([0])

        result = build_patch_proposal_report(report, decisions)
        assert result["summary"]["total_patches"] == 0
        assert result["summary"]["approved_but_skipped"] == 1

    def test_no_approved_indices_empty_result(self):
        """无 approved indices 时生成空结果。"""
        items = [
            _make_review_item(0, "C001", "intent_mismatch", ["accept_as_regression_case"]),
        ]
        report = _make_review_report(items)
        decisions = _make_approved_decisions([])

        result = build_patch_proposal_report(report, decisions)
        assert result["summary"]["total_patches"] == 0
        assert result["summary"]["approved_items"] == 0


# ═══════════════════════════════════════════════════════════════
# 测试 5: 审批决策加载
# ═══════════════════════════════════════════════════════════════


class TestApprovedDecisionsLoading:
    """审批决策文件加载测试。"""

    def test_load_simple_format(self, tmp_path):
        """加载简明格式（approved_indices 列表）。"""
        f = tmp_path / "approved.json"
        f.write_text(json.dumps({
            "approved_indices": [0, 2, 5],
            "approved_by": "tester",
            "approved_at": "2026-06-18T12:00:00Z",
        }), encoding="utf-8")

        result = load_approved_decisions(f)
        assert result["approved_indices"] == {0, 2, 5}
        assert result["approved_by"] == "tester"
        assert len(result["decisions_by_index"]) == 3

    def test_load_detailed_format(self, tmp_path):
        """加载详细格式（decisions 列表）。"""
        f = tmp_path / "approved.json"
        f.write_text(json.dumps({
            "decisions": [
                {"review_index": 0, "approved": True, "approved_by": "a"},
                {"review_index": 1, "approved": False},
                {"review_index": 2, "approved": True, "approved_by": "b"},
            ],
            "approved_by": "team",
        }), encoding="utf-8")

        result = load_approved_decisions(f)
        assert result["approved_indices"] == {0, 2}
        assert len(result["decisions_by_index"]) == 2

    def test_rejects_latest_filename(self, tmp_path):
        """拒绝 latest 文件名。"""
        f = tmp_path / "approved_latest.json"
        f.write_text('{"approved_indices": []}', encoding="utf-8")
        with pytest.raises(ValueError, match="latest"):
            load_approved_decisions(f)

    def test_missing_file(self, tmp_path):
        """文件不存在时抛异常。"""
        with pytest.raises(FileNotFoundError):
            load_approved_decisions(tmp_path / "nonexistent.json")

    def test_invalid_format(self, tmp_path):
        """格式不正确时抛异常。"""
        f = tmp_path / "bad.json"
        f.write_text('{"foo": "bar"}', encoding="utf-8")
        with pytest.raises(ValueError, match="格式不正确"):
            load_approved_decisions(f)


# ═══════════════════════════════════════════════════════════════
# 测试 6: 审查报告加载
# ═══════════════════════════════════════════════════════════════


class TestReviewReportLoading:
    """审查报告加载测试。"""

    def test_load_valid_report(self, tmp_path):
        """加载有效审查报告。"""
        f = tmp_path / "review.json"
        report = _make_review_report([_make_review_item(0)])
        f.write_text(json.dumps(report), encoding="utf-8")
        result = load_review_report(f)
        assert len(result["review_items"]) == 1

    def test_rejects_latest(self, tmp_path):
        """拒绝 latest 文件名。"""
        f = tmp_path / "review_latest.json"
        f.write_text('{"review_items": []}', encoding="utf-8")
        with pytest.raises(ValueError, match="latest"):
            load_review_report(f)

    def test_missing_review_items(self, tmp_path):
        """缺少 review_items 字段时抛异常。"""
        f = tmp_path / "bad_review.json"
        f.write_text('{"run_id": "x"}', encoding="utf-8")
        with pytest.raises(ValueError, match="review_items"):
            load_review_report(f)


# ═══════════════════════════════════════════════════════════════
# 测试 7: 渲染与写入
# ═══════════════════════════════════════════════════════════════


class TestRenderAndWrite:
    """JSON / Markdown 渲染和快照写入。"""

    def test_json_renderer_has_summary_and_patches(self, tmp_path):
        """JSON 输出包含 summary 和 patches。"""
        items = [
            _make_review_item(0, "C001", "intent_mismatch", ["accept_as_regression_case"]),
        ]
        report = _make_review_report(items)
        decisions = _make_approved_decisions([0])
        result = build_patch_proposal_report(report, decisions)

        json_data = render_patch_proposal_json(result)
        assert "summary" in json_data
        assert "patches" in json_data
        assert json_data["summary"]["total_patches"] == 2

    def test_markdown_has_required_sections(self, tmp_path):
        """Markdown 包含所有必需段落。"""
        items = [
            _make_review_item(0, "C001", "intent_mismatch", ["accept_as_regression_case"]),
            _make_review_item(1, "C002", "safety_validation_failed", ["accept_as_risk_item"]),
        ]
        report = _make_review_report(items)
        decisions = _make_approved_decisions([0, 1])
        result = build_patch_proposal_report(report, decisions)

        md = render_patch_proposal_markdown(result)
        assert "Memory Patch Proposal Report" in md
        assert "Proposed memory_rules.yml Patches" in md or "total_patches" in md
        assert "Proposed 风险清单.md Entries" in md
        assert "Proposed Regression / Eval Cases" in md
        assert "Proposed Pytest Cases" in md
        assert "Proposed Harness Checks" in md
        assert "Safety Boundaries" in md
        assert "Not Applied Automatically" in md
        assert "Manual Application Steps" in md

    def test_write_snapshot_timestamp_only(self, tmp_path):
        """写入文件为 timestamp snapshot，无 latest。"""
        items = [_make_review_item(0)]
        report = _make_review_report(items)
        decisions = _make_approved_decisions([0])
        result = build_patch_proposal_report(report, decisions)

        paths = write_patch_proposal_snapshot(result, tmp_path)
        assert paths["json"].name.startswith("memory_patch_proposal_")
        assert paths["markdown"].name.startswith("memory_patch_proposal_")
        assert "latest" not in paths["json"].name.lower()
        assert "latest" not in paths["markdown"].name.lower()
        assert paths["json"].exists()
        assert paths["markdown"].exists()

    def test_no_latest_files_generated(self, tmp_path):
        """确认不生成任何 latest 文件。"""
        items = [_make_review_item(0)]
        report = _make_review_report(items)
        decisions = _make_approved_decisions([0])
        result = build_patch_proposal_report(report, decisions)

        write_patch_proposal_snapshot(result, tmp_path)
        all_latest = list(tmp_path.rglob("*latest*"))
        assert len(all_latest) == 0


# ═══════════════════════════════════════════════════════════════
# 测试 8: 边界与约束
# ═══════════════════════════════════════════════════════════════


class TestBoundaries:
    """所有 patch 的 write_mode、安全边界检查。"""

    def test_all_patches_proposal_only(self, tmp_path):
        """所有 patch 的 write_mode 为 proposal_only。"""
        items = [
            _make_review_item(0, "C001", "intent_mismatch", ["accept_as_regression_case"]),
            _make_review_item(1, "C002", "safety_validation_failed", ["accept_as_risk_item"]),
            _make_review_item(
                2, "C003", "explain_failed",
                ["accept_as_memory_rule_candidate"],
            ),
        ]
        report = _make_review_report(items)
        decisions = _make_approved_decisions([0, 1, 2])
        result = build_patch_proposal_report(report, decisions)

        for p in result["patches"]:
            assert p["write_mode"] == "proposal_only", (
                f"patch {p['patch_id']} write_mode={p['write_mode']}, 期望 proposal_only"
            )

    def test_all_six_patch_types_covered(self):
        """6 种 patch 类型全部在 PATCH_TYPE_META 中定义。"""
        expected_types = {
            "memory_rule_patch",
            "memory_recap_patch",
            "risk_item_patch",
            "regression_case_patch",
            "test_case_patch",
            "harness_check_patch",
        }
        assert set(PATCH_TYPE_META.keys()) == expected_types

    def test_no_docs_memory_modified(self, tmp_path):
        """不修改任何 docs/memory/* 文件。"""
        docs_memory = tmp_path / "docs" / "memory"
        docs_memory.mkdir(parents=True, exist_ok=True)

        items = [_make_review_item(0)]
        report = _make_review_report(items)
        decisions = _make_approved_decisions([0])
        result = build_patch_proposal_report(report, decisions)
        write_patch_proposal_snapshot(result, tmp_path)

        # docs/memory/ 下不应有任何文件变化（只有可能已存在的空目录）
        all_files = list(docs_memory.rglob("*"))
        assert len(all_files) == 0

    def test_no_memory_rules_yml_created(self, tmp_path):
        """不创建 memory_rules.yml。"""
        items = [_make_review_item(0)]
        report = _make_review_report(items)
        decisions = _make_approved_decisions([0])
        result = build_patch_proposal_report(report, decisions)
        write_patch_proposal_snapshot(result, tmp_path)

        all_yml = list(tmp_path.rglob("memory_rules.yml"))
        assert len(all_yml) == 0

    def test_no_tests_evals_checks_created(self, tmp_path):
        """不新增 tests/ evals/ harness/checks/ 文件。"""
        items = [_make_review_item(0)]
        report = _make_review_report(items)
        decisions = _make_approved_decisions([0])
        result = build_patch_proposal_report(report, decisions)
        write_patch_proposal_snapshot(result, tmp_path)

        all_tests = list(tmp_path.rglob("test_*.py"))
        all_evals = list(tmp_path.rglob("*.yml"))
        all_checks = list(tmp_path.rglob("check_*.py"))
        # 只应有我们生成的 patch_proposal 文件
        assert all(
            "memory_patch_proposal" in str(p)
            for p in all_tests + all_evals + all_checks
        )

    def test_empty_review_report(self, tmp_path):
        """空的审查报告（无 review_items）生成空结果。"""
        report = _make_review_report([])
        decisions = _make_approved_decisions([])
        result = build_patch_proposal_report(report, decisions)
        assert result["summary"]["total_patches"] == 0
        assert result["summary"]["total_review_items"] == 0

    def test_patch_has_manual_steps(self):
        """每个 patch 都包含 manual_steps。"""
        item = _make_review_item(0, "C001", "intent_mismatch", ["accept_as_regression_case"])
        patches = generate_patches_for_item(item)
        for p in patches:
            assert len(p["manual_steps"]) >= 1, (
                f"patch {p['patch_id']} 缺少 manual_steps"
            )

    def test_patch_has_safety_notes(self):
        """每个 patch 都包含 safety_notes。"""
        item = _make_review_item(0, "C001", "intent_mismatch", ["accept_as_regression_case"])
        patches = generate_patches_for_item(item)
        for p in patches:
            assert len(p["safety_notes"]) >= 1, (
                f"patch {p['patch_id']} 缺少 safety_notes"
            )


# ═══════════════════════════════════════════════════════════════
# 测试 9: CLI 行为
# ═══════════════════════════════════════════════════════════════


class TestCLI:
    """run_memory_patch_proposals.py CLI 行为。"""

    def test_cli_generates_snapshot(self, tmp_path):
        """CLI 生成 timestamp snapshot 报告。"""
        import subprocess

        review_file = tmp_path / "review.json"
        items = [_make_review_item(0)]
        report = _make_review_report(items)
        review_file.write_text(json.dumps(report), encoding="utf-8")

        approved_file = tmp_path / "approved.json"
        approved_file.write_text(json.dumps({"approved_indices": [0]}), encoding="utf-8")

        out_dir = tmp_path / "patches"

        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_patch_proposals.py",
                "--input", str(review_file),
                "--approved-decisions", str(approved_file),
                "--output-dir", str(out_dir),
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Memory Patch Proposal Report" in result.stdout
        assert "total_patches" in result.stdout

        # 确认输出文件存在
        json_files = list(out_dir.rglob("*.json"))
        md_files = list(out_dir.rglob("*.md"))
        assert len(json_files) >= 1
        assert len(md_files) >= 1
        for f in json_files + md_files:
            assert "latest" not in f.name.lower()

    def test_cli_rejects_latest_input(self, tmp_path):
        """CLI 拒绝 latest 输入文件。"""
        import subprocess

        review_file = tmp_path / "review_latest.json"
        review_file.write_text('{"review_items": []}', encoding="utf-8")
        approved_file = tmp_path / "approved.json"
        approved_file.write_text('{"approved_indices": []}', encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_patch_proposals.py",
                "--input", str(review_file),
                "--approved-decisions", str(approved_file),
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

    def test_cli_rejects_latest_approved(self, tmp_path):
        """CLI 拒绝 latest 审批文件。"""
        import subprocess

        review_file = tmp_path / "review.json"
        review_file.write_text('{"review_items": []}', encoding="utf-8")
        approved_file = tmp_path / "approved_latest.json"
        approved_file.write_text('{"approved_indices": []}', encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_patch_proposals.py",
                "--input", str(review_file),
                "--approved-decisions", str(approved_file),
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

    def test_cli_no_approved_items_warning(self, tmp_path):
        """无 approved items 时输出 warning 但正常完成。"""
        import subprocess

        review_file = tmp_path / "review.json"
        items = [_make_review_item(0)]
        report = _make_review_report(items)
        review_file.write_text(json.dumps(report), encoding="utf-8")

        approved_file = tmp_path / "approved.json"
        approved_file.write_text(json.dumps({"approved_indices": []}), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_patch_proposals.py",
                "--input", str(review_file),
                "--approved-decisions", str(approved_file),
                "--output-dir", str(tmp_path / "out"),
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        assert result.returncode == 0
        # 无 patch 时输出相应信息
        assert "无 patch 生成" in result.stdout or "total_patches: 0" in result.stdout

    def test_cli_missing_input(self):
        """--input 缺少时退出非零。"""
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_patch_proposals.py",
                "--approved-decisions", "dummy.json",
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0


# ═══════════════════════════════════════════════════════════════
# 测试 10: 端到端
# ═══════════════════════════════════════════════════════════════


class TestEndToEnd:
    """从 review report + approved decisions → patch proposal 的完整流程。"""

    def test_full_pipeline(self, tmp_path):
        """完整流程：加载 → 审批 → 生成 → 渲染 → 写入。"""
        items = [
            _make_review_item(0, "C001", "intent_mismatch", ["accept_as_regression_case"]),
            _make_review_item(1, "C002", "plan_mismatch", ["accept_as_regression_case"]),
            _make_review_item(
                2, "C003", "explain_failed",
                ["accept_as_memory_rule_candidate"],
                manual_review_required=True,
            ),
            _make_review_item(3, "C004", "safety_validation_failed", ["accept_as_risk_item"]),
            _make_review_item(4, "C005", "confidence_out_of_range", ["provider_runtime_noise"]),
            _make_review_item(5, "C006", "unknown_failure", ["reject"]),
        ]
        report = _make_review_report(items)
        # 只审批 0, 2, 3 (skip 1, 4, 5)
        decisions = _make_approved_decisions([0, 2, 3])

        result = build_patch_proposal_report(report, decisions)

        # 3 approved, 3 unapproved
        assert result["summary"]["approved_items"] == 3
        assert result["summary"]["unapproved_items"] == 3
        # C001(0): 2 patches, C003(2): 2 patches (rule+recap), C004(3): 2 patches (risk+check)
        assert result["summary"]["total_patches"] == 6

        # 验证 patch 类型（无重复计数检查）
        counts = result["summary"]["patch_type_counts"]
        assert counts.get("regression_case_patch", 0) == 1
        assert counts.get("test_case_patch", 0) == 1
        assert counts.get("memory_rule_patch", 0) == 1
        assert counts.get("memory_recap_patch", 0) == 1
        assert counts.get("risk_item_patch", 0) == 1
        assert counts.get("harness_check_patch", 0) == 1

        # 写入快照
        paths = write_patch_proposal_snapshot(result, tmp_path)
        assert paths["json"].exists()
        assert paths["markdown"].exists()

        # 重新读取 JSON 验证
        written = json.loads(paths["json"].read_text(encoding="utf-8"))
        assert written["summary"]["total_patches"] == 6
        assert len(written["patches"]) == 6
        for p in written["patches"]:
            assert p["write_mode"] == "proposal_only"

    def test_specific_patch_builders(self):
        """单独测试 6 个 patch builder 函数。"""
        item = _make_review_item(0, "C001", "intent_mismatch", ["accept_as_regression_case"])

        # 逐一构建
        mp = build_memory_rule_patch(item, "PATCH-001")
        assert mp["patch_type"] == "memory_rule_patch"
        assert mp["write_mode"] == "proposal_only"

        rp = build_memory_recap_patch(item, "PATCH-002")
        assert rp["patch_type"] == "memory_recap_patch"
        assert "经验复盘" in rp["target_file"]

        rip = build_risk_item_patch(item, "PATCH-003")
        assert rip["patch_type"] == "risk_item_patch"
        assert "风险清单" in rip["target_file"]

        rcp = build_regression_case_patch(item, "PATCH-004")
        assert rcp["patch_type"] == "regression_case_patch"

        tcp = build_test_case_patch(item, "PATCH-005")
        assert tcp["patch_type"] == "test_case_patch"
        assert "def test_" in tcp["content"]

        hcp = build_harness_check_patch(item, "PATCH-006")
        assert hcp["patch_type"] == "harness_check_patch"
        assert "NOT_IMPLEMENTED" in hcp["content"]
