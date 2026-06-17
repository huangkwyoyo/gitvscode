from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _touch(root: Path, relative_path: str) -> str:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# test\n", encoding="utf-8")
    return relative_path


def _rule(
    root: Path,
    rule_id: str = "TA-R900",
    status: str = "proposed",
    blocking: bool = False,
    checks: list[str] | None = None,
    tests: list[str] | None = None,
    evals: list[str] | None = None,
    notes: str = "",
) -> dict:
    return {
        "rule_id": rule_id,
        "title": f"测试规则 {rule_id}",
        "status": status,
        "blocking": blocking,
        "severity": "high",
        "source_memory": "test",
        "risk_ids": ["RISK-999"],
        "applies_to": ["src/demo.py"],
        "required_checks": checks if checks is not None else [_touch(root, f"harness/checks/{rule_id}.py")],
        "required_tests": tests if tests is not None else [_touch(root, f"tests/{rule_id}.py")],
        "required_evals": evals if evals is not None else [_touch(root, f"evals/{rule_id}.yml")],
        "notes": notes,
    }


def test_proposed_rule_with_complete_coverage_is_ready_for_human_review(tmp_path):
    from harness.memory_promotion import analyze_promotion_candidates

    report = analyze_promotion_candidates([_rule(tmp_path)], project_root=tmp_path)

    assert report["summary"]["ready_for_human_review"] == 1
    item = report["ready_for_human_review"][0]
    assert item["rule_id"] == "TA-R900"
    assert item["candidate_status"] == "ready_for_human_review"
    assert item["manual_review_required"] is True
    assert item["blocking_semantics_review_required"] is True


def test_missing_required_fields_are_reported_as_missing_coverage(tmp_path):
    from harness.memory_promotion import analyze_promotion_candidates

    rule = _rule(tmp_path, checks=[], tests=[], evals=[])
    report = analyze_promotion_candidates([rule], project_root=tmp_path)

    item = report["missing_coverage"][0]
    assert item["rule_id"] == "TA-R900"
    assert item["candidate_status"] == "missing_coverage"
    assert item["missing_checks"] == ["required_checks 为空"]
    assert item["missing_tests"] == ["required_tests 为空"]
    assert item["missing_evals"] == ["required_evals 为空"]


def test_nonexistent_required_paths_are_reported_as_invalid_references(tmp_path):
    from harness.memory_promotion import analyze_promotion_candidates

    rule = _rule(
        tmp_path,
        checks=["harness/checks/not_found.py"],
        tests=["tests/not_found.py"],
        evals=["evals/not_found.yml"],
    )
    report = analyze_promotion_candidates([rule], project_root=tmp_path)

    item = report["invalid_references"][0]
    assert item["candidate_status"] == "invalid_references"
    assert sorted(item["invalid_paths"]) == [
        "evals/not_found.yml",
        "harness/checks/not_found.py",
        "tests/not_found.py",
    ]


def test_active_rules_do_not_enter_promotion_candidates(tmp_path):
    from harness.memory_promotion import analyze_promotion_candidates

    report = analyze_promotion_candidates([
        _rule(tmp_path, rule_id="TA-R901", status="active", blocking=True)
    ], project_root=tmp_path)

    assert report["summary"]["active_rules"] == 1
    assert report["summary"]["ready_for_human_review"] == 0
    assert report["rules"][0]["candidate_status"] == "not_applicable"


def test_proposed_blocking_true_is_not_recommended(tmp_path):
    from harness.memory_promotion import analyze_promotion_candidates

    report = analyze_promotion_candidates([
        _rule(tmp_path, blocking=True)
    ], project_root=tmp_path)

    item = report["not_recommended"][0]
    assert item["candidate_status"] == "not_recommended"
    assert "proposed 规则不能直接 blocking=true" in item["reason"]


def test_report_renderers_include_required_sections(tmp_path):
    from harness.memory_promotion import (
        analyze_promotion_candidates,
        build_memory_promotion_json,
        render_memory_promotion_markdown,
    )

    report = analyze_promotion_candidates([_rule(tmp_path)], project_root=tmp_path)
    json_payload = build_memory_promotion_json(report)
    md_payload = render_memory_promotion_markdown(report)

    json.dumps(json_payload, ensure_ascii=False)
    assert json_payload["summary"]["total_rules"] == 1
    assert json_payload["source_registry"] == "docs/memory/memory_rules.yml"
    assert "manual_review_required" in json_payload
    assert "Memory Rule Promotion Candidate Report" in md_payload
    assert "## Summary" in md_payload
    assert "Ready For Human Review" in md_payload
    assert "Missing Coverage" in md_payload
    assert "Invalid References" in md_payload
    assert "Not Recommended" in md_payload
    assert "Blocking Semantics Review" in md_payload
    assert "Suggested Next Actions" in md_payload


def test_cli_writes_timestamped_snapshot_reports_without_latest(tmp_path):
    registry = tmp_path / "memory_rules.yml"
    registry.write_text(
        """
rules:
  - rule_id: TA-R900
    title: "测试规则"
    status: proposed
    blocking: false
    severity: high
    source_memory: test
    risk_ids: [RISK-999]
    applies_to: [src/demo.py]
    required_checks: []
    required_tests: []
    required_evals: []
    notes: ""
""",
        encoding="utf-8",
    )
    before = registry.read_text(encoding="utf-8")
    output_dir = tmp_path / "reports"

    result = subprocess.run(
        [
            sys.executable,
            "harness/run_memory_promotion_report.py",
            "--registry",
            str(registry),
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert registry.read_text(encoding="utf-8") == before
    assert "ready_for_human_review:" in result.stdout
    assert "missing_coverage:" in result.stdout
    assert "invalid_references:" in result.stdout
    assert "not_recommended:" in result.stdout
    assert len(list(output_dir.glob("memory_promotion_*.json"))) == 1
    assert len(list(output_dir.glob("memory_promotion_*.md"))) == 1
    assert not (output_dir / "memory_promotion_latest.json").exists()
    assert not (output_dir / "memory_promotion_latest.md").exists()


def test_cli_returns_1_when_registry_yaml_is_invalid(tmp_path):
    registry = tmp_path / "memory_rules.yml"
    registry.write_text("rules: [\n", encoding="utf-8")
    output_dir = tmp_path / "reports"

    result = subprocess.run(
        [
            sys.executable,
            "harness/run_memory_promotion_report.py",
            "--registry",
            str(registry),
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )

    assert result.returncode == 1
    assert "ERROR:" in result.stderr
    assert not output_dir.exists()
