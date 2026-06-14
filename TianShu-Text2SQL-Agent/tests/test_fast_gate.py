from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.run_fast_gate import STEPS, StepResult, run_fast_gate


def test_pytest_step_uses_project_local_basetemp():
    """pytest 步骤必须使用项目内临时目录，避免系统 Temp 权限导致误失败。"""
    pytest_step = next(step for step in STEPS if step["name"] == "pytest")
    command_text = " ".join(pytest_step["command"])

    assert "--basetemp" in pytest_step["command"]
    assert "harness/reports/test_tmp/pytest_fast_gate" in command_text


def test_fast_gate_total_steps_matches_executed_and_skipped(monkeypatch, tmp_path):
    """fast gate 汇总总数应等于实际执行和跳过的步骤数。"""

    def fake_run_step(step, cwd, timeout_seconds=120):
        if step["name"] == "pytest":
            return StepResult(
                name=step["name"],
                display=step["display"],
                status="FAIL",
                exit_code=1,
                stdout="failed",
                stderr="",
                duration_seconds=0.01,
            )
        return StepResult(
            name=step["name"],
            display=step["display"],
            status="PASS",
            exit_code=0,
            stdout="ok",
            stderr="",
            duration_seconds=0.01,
        )

    monkeypatch.setattr("harness.run_fast_gate.run_step", fake_run_step)

    report = run_fast_gate(skip_mock=True, cwd=PROJECT_ROOT, report_dir=tmp_path)

    assert report.total_steps == len(report.steps)
    assert report.passed == 1
    assert report.failed == 1
    assert report.skipped == 1
