from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.run_fast_gate import (
    STEPS,
    WARN_ONLY_CHECK_INDICES,
    WARN_ONLY_CHECKS,
    StepResult,
    FastGateReport,
    _parse_harness_json_summary,
    run_fast_gate,
)


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


# ═══════════════════════════════════════════════════════════════════════════════
# Step 3: Fast Gate warn 模式集成测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestFastGateWarnModeStep3:
    """Step 3：fast gate 与 harness warn 模式集成测试"""

    def test_warn_only_check_indices_configured(self):
        """验证 WARN_ONLY_CHECK_INDICES 已配置且值在有效范围内"""
        assert len(WARN_ONLY_CHECK_INDICES) == 5, (
            f"应有 5 个观察期检查，实际: {len(WARN_ONLY_CHECK_INDICES)}"
        )
        # WARN_ONLY_CHECK_INDICES 引用的是 run_harness.py 的 STEPS（共 11 项）
        for idx in WARN_ONLY_CHECK_INDICES:
            assert 7 <= idx <= 11, (
                f"WARN_ONLY_CHECK_INDICES 索引 {idx} 应在 7-11 范围内"
            )

    def test_warn_only_checks_list_matches_indices(self):
        """验证 WARN_ONLY_CHECKS 列表与 WARN_ONLY_CHECK_INDICES 长度一致"""
        assert len(WARN_ONLY_CHECKS) == len(WARN_ONLY_CHECK_INDICES), (
            f"WARN_ONLY_CHECKS ({len(WARN_ONLY_CHECKS)}) 与 "
            f"WARN_ONLY_CHECK_INDICES ({len(WARN_ONLY_CHECK_INDICES)}) 长度不一致"
        )

    def test_harness_step_includes_warn_steps_flag(self):
        """验证 harness 步骤的命令包含 --warn-steps 和 --json-summary"""
        harness_step = next(step for step in STEPS if step["name"] == "harness")
        command_text = " ".join(harness_step["command"])

        assert "--warn-steps" in command_text, (
            f"harness 步骤应包含 --warn-steps:\n{command_text}"
        )
        assert "--json-summary" in command_text, (
            f"harness 步骤应包含 --json-summary:\n{command_text}"
        )
        # 确认所有 5 个索引都在
        for idx in WARN_ONLY_CHECK_INDICES:
            assert str(idx) in command_text, (
                f"harness 步骤应包含 warn 索引 {idx}:\n{command_text}"
            )

    def test_parse_harness_json_summary_valid(self):
        """验证 _parse_harness_json_summary 正确解析有效 JSON"""
        stdout = (
            "一些输出...\n"
            '__HARNESS_JSON_SUMMARY__ {"blocking_pass": 6, "blocking_fail": 0, '
            '"warn_pass": 3, "warn_warn": 2, "warn_infra_fail": 0, '
            '"total_pass": 9, "total_warn": 2, "total_fail": 0, "total_steps": 11}\n'
            "更多输出..."
        )
        summary = _parse_harness_json_summary(stdout)
        assert summary is not None, "应成功解析 JSON 摘要"
        assert summary["blocking_pass"] == 6
        assert summary["blocking_fail"] == 0
        assert summary["warn_pass"] == 3
        assert summary["warn_warn"] == 2
        assert summary["warn_infra_fail"] == 0
        assert summary["total_steps"] == 11

    def test_parse_harness_json_summary_missing_line(self):
        """验证 _parse_harness_json_summary 在无 JSON 行时返回 None"""
        stdout = "普通输出，没有 JSON 摘要行"
        summary = _parse_harness_json_summary(stdout)
        assert summary is None, "无 JSON 摘要时应返回 None"

    def test_parse_harness_json_summary_malformed_json(self):
        """验证 _parse_harness_json_summary 在 JSON 格式错误时返回 None"""
        stdout = '__HARNESS_JSON_SUMMARY__ {bad json!!!'
        summary = _parse_harness_json_summary(stdout)
        assert summary is None, "JSON 格式错误时应返回 None"

    def test_harness_output_with_warns_still_passes_fast_gate(self, monkeypatch, tmp_path):
        """warn check 产生警告时，fast gate 仍应通过（核心行为验证）"""
        import subprocess
        import sys
        import os

        project_root = PROJECT_ROOT

        # 直接端到端测试：运行 harness + warn 模式，验证 fast gate 通过
        result = subprocess.run(
            [
                sys.executable,
                "harness/run_harness.py",
                "--warn-steps", "7,8,9,10,11",
                "--json-summary",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        # 全部检查通过时，退出码应为 0
        assert result.returncode == 0, (
            f"warn 模式 + 全部通过 → exit 0:\nstderr:\n{result.stderr}"
        )

        # JSON 摘要应包含正确的统计
        summary = _parse_harness_json_summary(result.stdout)
        assert summary is not None, f"应输出 JSON 摘要:\n{result.stdout}"
        assert summary["warn_pass"] == 5, f"5 个 warn check 应全部通过: {summary}"
        assert summary["warn_warn"] == 0
        assert summary["warn_infra_fail"] == 0
        assert summary["blocking_fail"] == 0
        assert summary["total_fail"] == 0

    def test_fast_gate_report_includes_warn_stats(self, monkeypatch, tmp_path):
        """验证 FastGateReport 包含 warn 统计字段"""
        harness_summary = {
            "blocking_pass": 6,
            "blocking_fail": 0,
            "warn_pass": 4,
            "warn_warn": 1,
            "warn_infra_fail": 0,
            "total_pass": 10,
            "total_warn": 1,
            "total_fail": 0,
            "total_steps": 11,
        }

        def fake_run_step(step, cwd, timeout_seconds=120):
            if step["name"] == "harness":
                return StepResult(
                    name=step["name"],
                    display=step["display"],
                    status="PASS",
                    exit_code=0,
                    stdout=(
                        "Harness 输出...\n"
                        f"__HARNESS_JSON_SUMMARY__ {json.dumps(harness_summary, ensure_ascii=False)}\n"
                    ),
                    stderr="",
                    duration_seconds=0.5,
                    harness_summary=harness_summary,
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

        assert report.overall == "PASS", "warn 不阻断，应 PASS"
        assert report.warn_checks_passed == 4
        assert report.warn_checks_warned == 1
        assert report.warn_checks_infra_fail == 0

    def test_fast_gate_report_markdown_contains_warn_section(self, monkeypatch, tmp_path):
        """验证生成的 Markdown 报告包含观察期检查章节"""
        from harness.run_fast_gate import render_markdown

        harness_summary = {
            "blocking_pass": 6,
            "blocking_fail": 0,
            "warn_pass": 5,
            "warn_warn": 0,
            "warn_infra_fail": 0,
            "total_pass": 11,
            "total_warn": 0,
            "total_fail": 0,
            "total_steps": 11,
        }

        report = FastGateReport(
            run_id="test-001",
            timestamp="2026-06-17T00:00:00Z",
            commit_sha="abc1234",
            branch="main",
            total_steps=3,
            passed=3,
            failed=0,
            skipped=0,
            warned=0,
            overall="PASS",
            steps=[{
                "name": "harness",
                "display": "Harness",
                "status": "PASS",
                "exit_code": 0,
                "stdout": "",
                "stderr": "",
                "duration_seconds": 0.5,
                "harness_summary": harness_summary,
            }],
            duration_total_seconds=1.0,
            warn_checks_passed=5,
            warn_checks_warned=0,
            warn_checks_infra_fail=0,
        )

        md = render_markdown(report)
        assert "观察期检查（warn-only）" in md, (
            f"Markdown 应包含观察期检查章节:\n{md[:500]}"
        )
        assert "warn-only" in md.lower()
        assert "观察期" in md

    def test_fast_gate_end_to_end_with_warn_mode(self):
        """端到端：运行 fast gate --step 3（仅 harness），验证 warn 模式不阻断"""
        import subprocess
        import sys
        import os
        from pathlib import Path

        project_root = PROJECT_ROOT
        result = subprocess.run(
            [sys.executable, "harness/run_fast_gate.py", "--step", "3"],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

        # 不应崩溃，应有正常输出
        assert "快速门禁" in result.stdout, f"应包含 '快速门禁':\n{result.stdout[:500]}"
        assert "观察期" in result.stdout, (
            f"输出应提及观察期检查:\n{result.stdout[:500]}"
        )
        # harness 步骤应通过
        assert result.returncode == 0, (
            f"harness + warn 模式应正常退出:\nstderr:\n{result.stderr[:500]}"
        )

    def test_blocking_checks_still_block_in_fast_gate(self, monkeypatch, tmp_path):
        """验证原有阻断检查（compileall/pytest）仍然能阻断 fast gate"""
        def fake_run_step(step, cwd, timeout_seconds=120):
            if step["name"] == "compileall":
                return StepResult(
                    name=step["name"],
                    display=step["display"],
                    status="FAIL",
                    exit_code=1,
                    stdout="SyntaxError: invalid syntax in src/ir.py",
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

        # compileall 失败 → 应阻断
        assert report.overall == "FAIL", "阻断检查失败时应 FAIL"
        assert report.failed >= 1
        # 后续步骤应被跳过
        assert report.skipped >= 1
