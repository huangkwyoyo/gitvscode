"""Step 15 Patch Validation Workflow 测试套件。

覆盖：validation report 生成、边界检查、CLI 行为、渲染器。
所有测试不修改真实项目文件。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.memory_patch_validation import (  # noqa: E402
    VALID_RULE_STATUSES,
    _build_recommended_commands,
    _check_memory_rules,
    _check_recap_references,
    _check_risk_references,
    _check_rule_index,
    _extract_rule_ids,
    _load_memory_rules,
    _validate_proposal_basics,
    build_validation_report,
    load_patch_proposal,
    render_validation_json,
    render_validation_markdown,
    write_validation_snapshot,
)


# ═══════════════════════════════════════════════════════════════
# 测试辅助函数
# ═══════════════════════════════════════════════════════════════


def _make_patch_proposal(patches: list[dict]) -> dict:
    """构造一个最小化的 patch proposal JSON。"""
    return {
        "run_id": "PP20260618T120000Z",
        "timestamp": "2026-06-18T12:00:00Z",
        "source_review": "harness/reports/memory_reviews/review_20260618T120000Z.json",
        "summary": {"total_patches": len(patches)},
        "patches": patches,
    }


def _write_temp_proposal(patches: list[dict], suffix: str = "") -> Path:
    """写入临时 proposal JSON 文件并返回路径。"""
    name = f"memory_patch_proposal_PP20260618T120001Z{suffix}.json"
    tmp = Path(tempfile.gettempdir()) / name
    proposal = _make_patch_proposal(patches)
    tmp.write_text(json.dumps(proposal, ensure_ascii=False), encoding="utf-8")
    return tmp


# ═══════════════════════════════════════════════════════════════
# Test 1: 有效 proposal 生成 validation report
# ═══════════════════════════════════════════════════════════════


class TestValidProposalGeneratesReport:
    """有效 proposal 能生成完整验证报告。"""

    def test_valid_proposal_generates_report_full(self):
        """包含各类型 patch 的有效 proposal 生成报告。"""
        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "write_mode": "proposal_only",
                "content": "rule_id: TA-R099",
            },
            {
                "patch_id": "PATCH-002",
                "patch_type": "regression_case_patch",
                "target_file": "evals/regression/prompt_regression.yml",
                "write_mode": "proposal_only",
                "content": "cases: []",
            },
        ]
        tmp = _write_temp_proposal(patches)
        try:
            report = build_validation_report(tmp)
            assert report["run_id"].startswith("PV")
            assert report["source_proposal"] == str(tmp)
            assert report["summary"]["patches_checked"] == 2
            assert "validation_items" in report
            assert len(report["validation_items"]) > 0
            assert "recommended_commands" in report
        finally:
            tmp.unlink(missing_ok=True)

    def test_valid_proposal_passes_basics(self):
        """基础字段完整的 patch 通过基础检查。"""
        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "regression_case_patch",
                "target_file": "evals/regression/prompt_regression.yml",
                "write_mode": "proposal_only",
                "content": "",
            },
        ]
        items = _validate_proposal_basics(patches)
        assert len(items) == 1
        assert items[0]["status"] == "passed"


# ═══════════════════════════════════════════════════════════════
# Test 2: latest proposal 被拒绝
# ═══════════════════════════════════════════════════════════════


class TestLatestRejected:
    """latest 文件被拒绝。"""

    def test_latest_filename_rejected_in_load(self):
        """文件名含 latest 时加载抛出 ValueError。"""
        with pytest.raises(ValueError, match="latest"):
            load_patch_proposal("memory_patch_proposal_latest.json")

    def test_latest_filename_rejected_in_report(self):
        """文件路径含 latest 时报告生成失败。"""
        report = build_validation_report("memory_patch_proposal_latest.json")
        assert report["summary"]["patches_checked"] == 0
        assert len(report["validation_items"]) == 1
        assert report["validation_items"][0]["status"] == "failed"
        assert "latest" in report["validation_items"][0]["message"].lower() or \
            "latest" in str(report.get("error", "")).lower()


# ═══════════════════════════════════════════════════════════════
# Test 3: JSON 格式错误
# ═══════════════════════════════════════════════════════════════


class TestProposalFormatError:
    """JSON 格式错误导致 failed。"""

    def test_bad_json_fails(self):
        """解析失败的 JSON 导致 failed 报告。"""
        tmp = Path(tempfile.gettempdir()) / "memory_patch_proposal_PP20260618T120002Z.json"
        tmp.write_text("{this is not json", encoding="utf-8")
        try:
            report = build_validation_report(tmp)
            assert report["summary"]["patches_checked"] == 0
            assert len(report["validation_items"]) == 1
            assert report["validation_items"][0]["status"] == "failed"
        finally:
            tmp.unlink(missing_ok=True)

    def test_patches_not_list_fails(self):
        """patches 不是 list 类型时报告 failed。"""
        proposal = _make_patch_proposal([])
        proposal["patches"] = "not_a_list"
        tmp = Path(tempfile.gettempdir()) / "memory_patch_proposal_PP20260618T120003Z.json"
        tmp.write_text(json.dumps(proposal), encoding="utf-8")
        try:
            report = build_validation_report(tmp)
            assert report["summary"]["patches_checked"] == 0
            assert len(report["validation_items"]) == 1
            assert report["validation_items"][0]["status"] == "failed"
        finally:
            tmp.unlink(missing_ok=True)

    def test_file_not_found_fails(self):
        """文件不存在时报告 failed。"""
        report = build_validation_report("/nonexistent/path/to/proposal.json")
        assert report["summary"]["patches_checked"] == 0
        assert len(report["validation_items"]) == 1
        assert report["validation_items"][0]["status"] == "failed"


# ═══════════════════════════════════════════════════════════════
# Test 4: write_mode 非 proposal_only
# ═══════════════════════════════════════════════════════════════


class TestWriteModeNonProposalOnly:
    """write_mode 非 proposal_only 会 failed。"""

    def test_write_mode_auto_apply_fails(self):
        """write_mode='auto_apply' → failed。"""
        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "write_mode": "auto_apply",
                "content": "",
            },
        ]
        items = _validate_proposal_basics(patches)
        assert items[0]["status"] == "failed"
        assert "proposal_only" in items[0]["message"]

    def test_write_mode_missing_fails(self):
        """write_mode 缺失 → failed。"""
        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "content": "",
            },
        ]
        items = _validate_proposal_basics(patches)
        assert items[0]["status"] == "failed"


# ═══════════════════════════════════════════════════════════════
# Test 5: memory_rules.yml 缺失时 memory_rule_patch → failed
# ═══════════════════════════════════════════════════════════════


class TestMemoryRulesYmlMissing:
    """memory_rules.yml 缺失且 proposal 有 memory_rule_patch → failed。"""

    def test_missing_rules_with_memory_rule_patch_fails(self, monkeypatch):
        """模拟 memory_rules.yml 不存在。"""
        monkeypatch.setattr(
            "harness.memory_patch_validation._load_memory_rules", lambda: None
        )
        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "write_mode": "proposal_only",
                "content": "",
            },
        ]
        items = _check_memory_rules(patches)
        assert any(v["status"] == "failed" for v in items)
        assert any("不存在" in v["message"] for v in items)


# ═══════════════════════════════════════════════════════════════
# Test 6: duplicate rule_id
# ═══════════════════════════════════════════════════════════════


class TestDuplicateRuleId:
    """重复 rule_id 导致 failed。"""

    def test_duplicate_rule_id_fails(self, tmp_path, monkeypatch):
        """两个规则使用相同 rule_id → failed。"""
        rules_yml = tmp_path / "memory_rules.yml"
        rules_yml.write_text("""
rules:
  - rule_id: TA-R099
    title: "测试规则 A"
    status: proposed
    blocking: false
    severity: medium
    source_memory: "test"
    risk_ids: []
    applies_to: []
    required_checks: []
    required_tests: []
    required_evals: []
    notes: ""
  - rule_id: TA-R099
    title: "测试规则 B"
    status: proposed
    blocking: false
    severity: medium
    source_memory: "test"
    risk_ids: []
    applies_to: []
    required_checks: []
    required_tests: []
    required_evals: []
    notes: ""
""", encoding="utf-8")

        def _fake_load():
            import yaml
            raw = rules_yml.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
            return {"rules": data["rules"], "raw": raw, "path": str(rules_yml)}

        monkeypatch.setattr(
            "harness.memory_patch_validation._load_memory_rules", _fake_load
        )
        monkeypatch.setattr(
            "harness.memory_patch_validation.PROJECT_ROOT", tmp_path
        )

        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "write_mode": "proposal_only",
                "content": "",
            },
        ]
        items = _check_memory_rules(patches)
        dup_items = [v for v in items if "重复" in v.get("message", "")]
        assert len(dup_items) >= 1
        assert dup_items[0]["status"] == "failed"


# ═══════════════════════════════════════════════════════════════
# Test 7: 非 TA-Rxxx rule_id
# ═══════════════════════════════════════════════════════════════


class TestNonTARFormatRuleId:
    """非 TA-Rxxx 格式的 rule_id 导致 failed。"""

    def test_non_tar_format_fails(self, tmp_path, monkeypatch):
        """rule_id='R001' → failed。"""
        rules_yml = tmp_path / "memory_rules.yml"
        rules_yml.write_text("""
rules:
  - rule_id: R001
    title: "错误的编号格式"
    status: proposed
    blocking: false
    severity: medium
    source_memory: "test"
    risk_ids: []
    applies_to: []
    required_checks: []
    required_tests: []
    required_evals: []
    notes: ""
""", encoding="utf-8")

        def _fake_load():
            import yaml
            raw = rules_yml.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
            return {"rules": data["rules"], "raw": raw, "path": str(rules_yml)}

        monkeypatch.setattr(
            "harness.memory_patch_validation._load_memory_rules", _fake_load
        )
        monkeypatch.setattr(
            "harness.memory_patch_validation.PROJECT_ROOT", tmp_path
        )

        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "write_mode": "proposal_only",
                "content": "",
            },
        ]
        items = _check_memory_rules(patches)
        format_items = [v for v in items if "TA-R" in v.get("message", "")]
        assert len(format_items) >= 1
        assert format_items[0]["status"] == "failed"


# ═══════════════════════════════════════════════════════════════
# Test 8: proposed 规则缺 test/eval 但有 TODO notes → warning
# ═══════════════════════════════════════════════════════════════


class TestProposedRuleMissingWithTODO:
    """proposed 规则缺 required_* 但有 TODO → warning 不 failed。"""

    def test_proposed_missing_test_with_todo_is_warning(self, tmp_path, monkeypatch):
        """proposed 规则 required_test 不存在但 notes 有 TODO → warning。"""
        rules_yml = tmp_path / "memory_rules.yml"
        rules_yml.write_text("""
rules:
  - rule_id: TA-R099
    title: "测试规则"
    status: proposed
    blocking: false
    severity: medium
    source_memory: "test"
    risk_ids: []
    applies_to: []
    required_checks: []
    required_tests:
      - tests/nonexistent_test.py
    required_evals: []
    notes: "TODO: 待补充测试文件"
""", encoding="utf-8")

        def _fake_load():
            import yaml
            raw = rules_yml.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
            return {"rules": data["rules"], "raw": raw, "path": str(rules_yml)}

        monkeypatch.setattr(
            "harness.memory_patch_validation._load_memory_rules", _fake_load
        )
        monkeypatch.setattr(
            "harness.memory_patch_validation.PROJECT_ROOT", tmp_path
        )

        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "write_mode": "proposal_only",
                "content": "",
            },
        ]
        items = _check_memory_rules(patches)
        warn_items = [v for v in items if v["status"] == "warning"
                      and "TODO" in v.get("message", "")]
        assert len(warn_items) >= 1
        # 不应该有 failed
        failed = [v for v in items if v["status"] == "failed"]
        assert len(failed) == 0


# ═══════════════════════════════════════════════════════════════
# Test 9: active + blocking=true 缺 required_tests → failed
# ═══════════════════════════════════════════════════════════════


class TestActiveBlockingMissingRequiredTests:
    """active + blocking=true 缺 required_tests → failed。"""

    def test_active_blocking_missing_required_tests_fails(self, tmp_path, monkeypatch):
        """active+blocking=true 但 required_tests 为空 → failed。"""
        rules_yml = tmp_path / "memory_rules.yml"
        rules_yml.write_text("""
rules:
  - rule_id: TA-R099
    title: "高危规则"
    status: active
    blocking: true
    severity: high
    source_memory: "test"
    risk_ids:
      - RISK-099
    applies_to:
      - src/agent.py
    required_checks:
      - harness/checks/check_sql_readonly.py
    required_tests: []
    required_evals: []
    notes: ""
""", encoding="utf-8")

        def _fake_load():
            import yaml
            raw = rules_yml.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
            return {"rules": data["rules"], "raw": raw, "path": str(rules_yml)}

        monkeypatch.setattr(
            "harness.memory_patch_validation._load_memory_rules", _fake_load
        )
        monkeypatch.setattr(
            "harness.memory_patch_validation.PROJECT_ROOT", tmp_path
        )

        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "write_mode": "proposal_only",
                "content": "",
            },
        ]
        items = _check_memory_rules(patches)
        failed_items = [
            v for v in items
            if v["status"] == "failed" and "active + blocking" in v.get("message", "")
        ]
        assert len(failed_items) >= 1


# ═══════════════════════════════════════════════════════════════
# Test 10: index 未同步 → warning
# ═══════════════════════════════════════════════════════════════


class TestIndexOutOfSync:
    """规则来源索引与 memory_rules.yml 不同步 → warning。"""

    def test_index_out_of_sync_is_warning(self, tmp_path, monkeypatch):
        """索引中缺少某个 rule_id → warning。"""
        rules_yml = tmp_path / "docs" / "memory" / "memory_rules.yml"
        rules_yml.parent.mkdir(parents=True, exist_ok=True)
        rules_yml.write_text("""
rules:
  - rule_id: TA-R099
    title: "新规则"
    status: proposed
    blocking: false
    severity: medium
    source_memory: "test"
    risk_ids: []
    applies_to: []
    required_checks: []
    required_tests: []
    required_evals: []
    notes: ""
""", encoding="utf-8")

        index_md = tmp_path / "docs" / "memory" / "规则来源索引.md"
        index_md.parent.mkdir(parents=True, exist_ok=True)
        # 索引中没有 TA-R099
        index_md.write_text("# 规则来源索引\n\n| **TA-R010** | ... |\n", encoding="utf-8")

        def _fake_load():
            import yaml
            raw = rules_yml.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
            return {"rules": data["rules"], "raw": raw, "path": str(rules_yml)}

        monkeypatch.setattr(
            "harness.memory_patch_validation._load_memory_rules", _fake_load
        )
        monkeypatch.setattr(
            "harness.memory_patch_validation.PROJECT_ROOT", tmp_path
        )

        items = _check_rule_index()
        warn_items = [v for v in items if v["status"] == "warning"]
        assert len(warn_items) >= 1
        assert any("不同步" in v["message"] for v in warn_items)


# ═══════════════════════════════════════════════════════════════
# Test 11: memory_recap_patch 未在经验复盘中找到 → warning
# ═══════════════════════════════════════════════════════════════


class TestRecapPatchNotFound:
    """memory_recap_patch 引用未在经验复盘中找到 → warning。"""

    def test_recap_patch_not_found_warning(self, tmp_path, monkeypatch):
        """经验复盘存在但不包含 patch 的引用 → warning。"""
        recap_md = tmp_path / "docs" / "memory" / "经验复盘.md"
        recap_md.parent.mkdir(parents=True, exist_ok=True)
        recap_md.write_text("# 经验复盘\n\n## R001: 某条经验\n", encoding="utf-8")

        monkeypatch.setattr(
            "harness.memory_patch_validation.PROJECT_ROOT", tmp_path
        )

        patches = [
            {
                "patch_id": "PATCH-RECAP-001",
                "patch_type": "memory_recap_patch",
                "target_file": "docs/memory/经验复盘.md",
                "write_mode": "proposal_only",
                "content": "TA-R099: 新的经验复盘条目",
            },
        ]
        items = _check_recap_references(patches)
        assert len(items) >= 1
        assert items[0]["status"] == "warning"


# ═══════════════════════════════════════════════════════════════
# Test 12: risk_item_patch 未在风险清单中找到 → warning
# ═══════════════════════════════════════════════════════════════


class TestRiskPatchNotFound:
    """risk_item_patch 引用未在风险清单中找到 → warning。"""

    def test_risk_patch_not_found_warning(self, tmp_path, monkeypatch):
        """风险清单存在但不包含 patch 的 risk_id → warning。"""
        risk_md = tmp_path / "docs" / "memory" / "风险清单.md"
        risk_md.parent.mkdir(parents=True, exist_ok=True)
        risk_md.write_text("# 风险清单\n\n| RISK-001 | 旧风险 |\n", encoding="utf-8")

        monkeypatch.setattr(
            "harness.memory_patch_validation.PROJECT_ROOT", tmp_path
        )

        patches = [
            {
                "patch_id": "PATCH-RISK-001",
                "patch_type": "risk_item_patch",
                "target_file": "docs/memory/风险清单.md",
                "write_mode": "proposal_only",
                "content": "RISK-099: 新的风险项",
            },
        ]
        items = _check_risk_references(patches)
        assert len(items) >= 1
        assert items[0]["status"] == "warning"


# ═══════════════════════════════════════════════════════════════
# Test 13: required_checks 不存在 → warning/failed
# ═══════════════════════════════════════════════════════════════


class TestRequiredChecksNotExist:
    """required_checks 文件不存在时按规则 status 返回 warning 或 failed。"""

    def test_proposed_rule_missing_check_is_warning(self, tmp_path, monkeypatch):
        """proposed 规则 required_checks 文件不存在且无 TODO → warning。"""
        rules_yml = tmp_path / "memory_rules.yml"
        rules_yml.write_text("""
rules:
  - rule_id: TA-R099
    title: "测试规则"
    status: proposed
    blocking: false
    severity: medium
    source_memory: "test"
    risk_ids: []
    applies_to: []
    required_checks:
      - harness/checks/nonexistent_check.py
    required_tests: []
    required_evals: []
    notes: ""
""", encoding="utf-8")

        def _fake_load():
            import yaml
            raw = rules_yml.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
            return {"rules": data["rules"], "raw": raw, "path": str(rules_yml)}

        monkeypatch.setattr(
            "harness.memory_patch_validation._load_memory_rules", _fake_load
        )
        monkeypatch.setattr(
            "harness.memory_patch_validation.PROJECT_ROOT", tmp_path
        )

        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "write_mode": "proposal_only",
                "content": "",
            },
        ]
        items = _check_memory_rules(patches)
        warn_items = [
            v for v in items
            if v["status"] == "warning" and "required_check" in v.get("message", "")
        ]
        assert len(warn_items) >= 1


# ═══════════════════════════════════════════════════════════════
# Test 14-16: CLI 行为
# ═══════════════════════════════════════════════════════════════


class TestCLIBehavior:
    """CLI 行为测试：timestamp snapshot、不生成 latest、不修改文件。"""

    def test_cli_generates_timestamp_snapshot(self, tmp_path):
        """CLI 生成 timestamp snapshot 格式的文件名。"""
        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "write_mode": "proposal_only",
                "content": "",
            },
        ]
        tmp = _write_temp_proposal(patches)
        out_dir = tmp_path / "validations"
        try:
            report = build_validation_report(tmp)
            paths = write_validation_snapshot(report, out_dir)
            # 文件名应包含 PV 前缀和时间戳
            assert "memory_patch_validation_PV" in paths["json"]
            assert "memory_patch_validation_PV" in paths["markdown"]
            # 不应包含 latest
            assert "latest" not in Path(paths["json"]).name.lower()
            assert "latest" not in Path(paths["markdown"]).name.lower()
        finally:
            tmp.unlink(missing_ok=True)

    def test_cli_does_not_generate_latest(self, tmp_path):
        """CLI 不生成 latest 文件。"""
        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "write_mode": "proposal_only",
                "content": "",
            },
        ]
        tmp = _write_temp_proposal(patches)
        out_dir = tmp_path / "validations"
        try:
            report = build_validation_report(tmp)
            _paths = write_validation_snapshot(report, out_dir)
            # 检查输出目录中没有 latest 文件
            all_files = list(out_dir.rglob("*"))
            latest_files = [f for f in all_files if "latest" in f.name.lower()]
            assert len(latest_files) == 0
        finally:
            tmp.unlink(missing_ok=True)

    def test_cli_does_not_modify_docs_memory(self, tmp_path):
        """CLI 不修改 docs/memory/*。"""
        # 记录真实 docs/memory 的修改时间
        real_memory = PROJECT_ROOT / "docs" / "memory"
        if real_memory.exists():
            before_times = {}
            for f in real_memory.rglob("*"):
                if f.is_file():
                    before_times[str(f)] = f.stat().st_mtime

        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "write_mode": "proposal_only",
                "content": "",
            },
        ]
        tmp = _write_temp_proposal(patches)
        out_dir = tmp_path / "validations"
        try:
            report = build_validation_report(tmp)
            write_validation_snapshot(report, out_dir)

            # 验证 real docs/memory 没有被修改
            if real_memory.exists():
                for f in real_memory.rglob("*"):
                    if f.is_file():
                        assert str(f) in before_times, f"新文件被创建: {f}"
                        assert f.stat().st_mtime == before_times[str(f)], \
                            f"文件被修改: {f}"
        finally:
            tmp.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════
# Test 17: 不自动运行 generate_rule_index.py
# ═══════════════════════════════════════════════════════════════


class TestNoAutoRunScript:
    """默认不自动运行 generate_rule_index.py。"""

    def test_default_does_not_auto_run(self):
        """run_checks=False 时 report 中 run_checks 为 False。"""
        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "write_mode": "proposal_only",
                "content": "",
            },
        ]
        tmp = _write_temp_proposal(patches)
        try:
            report = build_validation_report(tmp, run_checks=False)
            assert report.get("run_checks") is False
        finally:
            tmp.unlink(missing_ok=True)

    def test_run_checks_true_sets_flag(self):
        """run_checks=True 时 report 中 run_checks 为 True。"""
        patches = [{"patch_id": "P-1", "patch_type": "test_case_patch",
                     "target_file": "tests/x.py", "write_mode": "proposal_only"}]
        tmp = _write_temp_proposal(patches)
        try:
            report = build_validation_report(tmp, run_checks=True)
            assert report.get("run_checks") is True
        finally:
            tmp.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════
# Test 18: JSON renderer 包含 summary / validation_items
# ═══════════════════════════════════════════════════════════════


class TestJSONRenderer:
    """JSON renderer 包含必要字段。"""

    def test_json_has_summary_and_validation_items(self):
        """渲染后的 JSON 包含 summary 和 validation_items。"""
        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "write_mode": "proposal_only",
                "content": "",
            },
        ]
        tmp = _write_temp_proposal(patches)
        try:
            report = build_validation_report(tmp)
            rendered = render_validation_json(report)
            assert "summary" in rendered
            assert "validation_items" in rendered
            assert isinstance(rendered["summary"], dict)
            assert isinstance(rendered["validation_items"], list)
            # 检查 summary 必要字段
            for key in ["patches_checked", "passed", "warnings", "failures",
                        "pending_manual_actions"]:
                assert key in rendered["summary"]
        finally:
            tmp.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════
# Test 19: Markdown renderer 包含 Pending Manual Actions
# ═══════════════════════════════════════════════════════════════


class TestMarkdownRenderer:
    """Markdown renderer 包含必要段落。"""

    def test_markdown_has_pending_manual_actions(self):
        """Markdown 包含 Pending Manual Actions 段落。"""
        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "test_case_patch",
                "target_file": "tests/（待定）",
                "write_mode": "proposal_only",
                "content": "",
            },
        ]
        tmp = _write_temp_proposal(patches)
        try:
            report = build_validation_report(tmp)
            md = render_validation_markdown(report)
            assert "# Memory Patch Validation Report" in md
            assert "## Summary" in md
            assert "## Pending Manual Actions" in md or "## ⏳ Pending Manual Actions" in md
            assert "## Recommended Commands" in md
            assert "## Safety Boundaries" in md
            assert "## Not Applied Automatically" in md
        finally:
            tmp.unlink(missing_ok=True)

    def test_markdown_has_all_required_sections(self):
        """Markdown 包含所有必需段落。"""
        patches = [
            {
                "patch_id": "PATCH-FAIL-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "write_mode": "auto_apply",  # 会触发 failed
                "content": "",
            },
        ]
        tmp = _write_temp_proposal(patches)
        try:
            report = build_validation_report(tmp)
            md = render_validation_markdown(report)
            # 有 failed items 时应包含 Failures 章节
            if report["summary"]["failures"] > 0:
                assert "## Failures" in md or "## ❌ Failures" in md
            # 应包含 All Validation Results
            assert "## All Validation Results" in md
        finally:
            tmp.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════
# Test 20: 无 patch 时生成 no-op report
# ═══════════════════════════════════════════════════════════════


class TestNoOpReport:
    """patches 为空时生成 no-op 报告。"""

    def test_empty_patches_generates_noop_report(self):
        """空 patches → patches_checked=0，warning 标记。"""
        patches: list[dict] = []
        items = _validate_proposal_basics(patches)
        assert len(items) == 1
        assert items[0]["status"] == "warning"
        assert "no-op" in items[0]["message"].lower() or "空" in items[0]["message"]

    def test_empty_patches_report_builds(self):
        """空 patches 的完整报告可以正常构建。"""
        tmp = _write_temp_proposal([])
        try:
            report = build_validation_report(tmp)
            assert report["summary"]["patches_checked"] == 0
            assert len(report["validation_items"]) > 0
            md = render_validation_markdown(report)
            assert md  # 不为空
        finally:
            tmp.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════
# 边界 / 辅助函数测试
# ═══════════════════════════════════════════════════════════════


class TestBoundaries:
    """边界和辅助函数测试。"""

    def test_extract_rule_ids(self):
        """_extract_rule_ids 正确提取 TA-Rxxx。"""
        text = "rule_id: TA-R010, 还有 TA-R099 和 TA-R018。"
        ids = _extract_rule_ids(text)
        assert "TA-R010" in ids
        assert "TA-R099" in ids
        assert "TA-R018" in ids

    def test_build_recommended_commands_includes_index(self):
        """推荐命令始终包含 generate_rule_index。"""
        commands = _build_recommended_commands([])
        assert any("generate_rule_index" in c for c in commands)
        assert any("check_memory_update" in c for c in commands)
        assert any("run_harness" in c for c in commands)

    def test_build_recommended_commands_with_patches(self):
        """有 test/memory patch 时包含 pytest memory。"""
        patches = [
            {"patch_id": "P-1", "patch_type": "test_case_patch",
             "target_file": "tests/x.py", "write_mode": "proposal_only"},
        ]
        commands = _build_recommended_commands(patches)
        assert any('pytest tests -k "memory"' in c for c in commands)

    def test_load_memory_rules_returns_none_for_missing(self, tmp_path, monkeypatch):
        """_load_memory_rules 在文件不存在时返回 None。"""
        monkeypatch.setattr(
            "harness.memory_patch_validation.PROJECT_ROOT", tmp_path
        )
        result = _load_memory_rules()
        assert result is None

    def test_render_validation_snapshot_writes_both_formats(self, tmp_path):
        """写快照同时产出 JSON 和 Markdown。"""
        patches = [{"patch_id": "P-1", "patch_type": "memory_rule_patch",
                     "target_file": "x.yml", "write_mode": "proposal_only"}]
        tmp = _write_temp_proposal(patches)
        try:
            report = build_validation_report(tmp)
            paths = write_validation_snapshot(report, tmp_path)
            assert Path(paths["json"]).exists()
            assert Path(paths["markdown"]).exists()
            # JSON 可解析
            data = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
            assert "validation_items" in data
        finally:
            tmp.unlink(missing_ok=True)

    def test_valid_rule_statuses(self):
        """VALID_RULE_STATUSES 包含 4 种状态。"""
        assert "proposed" in VALID_RULE_STATUSES
        assert "active" in VALID_RULE_STATUSES
        assert "deprecated" in VALID_RULE_STATUSES
        assert "superseded" in VALID_RULE_STATUSES

    def test_report_contains_all_recommended_commands(self):
        """完整报告包含所有推荐命令。"""
        patches = [
            {"patch_id": "P-1", "patch_type": "memory_rule_patch",
             "target_file": "docs/memory/memory_rules.yml", "write_mode": "proposal_only"},
        ]
        tmp = _write_temp_proposal(patches)
        try:
            report = build_validation_report(tmp)
            cmds = report["recommended_commands"]
            assert any("generate_rule_index" in c for c in cmds)
            assert any("check_memory_update" in c for c in cmds)
            assert any("run_harness" in c for c in cmds)
        finally:
            tmp.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════
# 端到端测试（使用项目真实文件）
# ═══════════════════════════════════════════════════════════════


class TestEndToEnd:
    """端到端测试：验证与真实项目文件的交互。"""

    def test_e2e_with_real_memory_rules(self):
        """使用真实 memory_rules.yml 的完整验证流程。"""
        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "write_mode": "proposal_only",
                "content": "",
            },
            {
                "patch_id": "PATCH-002",
                "patch_type": "regression_case_patch",
                "target_file": "evals/regression/prompt_regression.yml",
                "write_mode": "proposal_only",
                "content": "",
            },
        ]
        tmp = _write_temp_proposal(patches)
        try:
            report = build_validation_report(tmp)
            # 验证报告结构
            assert "run_id" in report
            assert "summary" in report
            assert "validation_items" in report
            assert len(report["validation_items"]) > 0

            # JSON 渲染
            json_out = render_validation_json(report)
            assert isinstance(json_out, dict)

            # Markdown 渲染
            md_out = render_validation_markdown(report)
            assert isinstance(md_out, str)
            assert len(md_out) > 100

            # 快照写入
            with tempfile.TemporaryDirectory() as td:
                paths = write_validation_snapshot(report, td)
                assert Path(paths["json"]).exists()
                assert Path(paths["markdown"]).exists()
        finally:
            tmp.unlink(missing_ok=True)

    def test_e2e_regression_no_modification(self):
        """端到端验证不修改任何项目文件。"""
        patches = [
            {
                "patch_id": "PATCH-001",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "write_mode": "proposal_only",
                "content": "",
            },
        ]
        tmp = _write_temp_proposal(patches)

        # 记录真实 memory_rules.yml 的修改时间
        real_path = PROJECT_ROOT / "docs" / "memory" / "memory_rules.yml"
        before_mtime = real_path.stat().st_mtime if real_path.exists() else None

        try:
            report = build_validation_report(tmp)
            with tempfile.TemporaryDirectory() as td:
                write_validation_snapshot(report, td)

            # 验证真实文件未被修改
            if before_mtime is not None:
                assert real_path.stat().st_mtime == before_mtime
        finally:
            tmp.unlink(missing_ok=True)
