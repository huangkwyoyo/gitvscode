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


def test_active_blocking_failure_makes_fast_gate_exit_nonzero(monkeypatch, tmp_path):
    """Memory blocking failure 应把全通过的 fast gate 转为非零退出。"""
    import harness.run_fast_gate as fast_gate

    def fake_run_step(step, cwd, timeout_seconds=120):
        return StepResult(
            name=step["name"],
            display=step["display"],
            status="PASS",
            exit_code=0,
            stdout="check results" if step["name"] == "harness" else "ok",
            stderr="",
            duration_seconds=0.01,
        )

    enforcement_report = {
        "summary": {"blocking_failures": 1},
        "rule_results": [
            {
                "rule_id": "TA-R018",
                "title": "LLM 融合安全规则",
                "enforcement_level": "blocking_error",
                "result": "FAIL",
            },
        ],
        "exit_code_should_fail": True,
    }
    monkeypatch.setattr(fast_gate, "run_step", fake_run_step)
    monkeypatch.setattr(
        fast_gate,
        "_run_memory_rule_enforcement",
        lambda stdout: enforcement_report,
    )

    report = fast_gate.run_fast_gate(
        skip_mock=True,
        cwd=PROJECT_ROOT,
        report_dir=tmp_path,
    )
    assert report.overall == "FAIL"
    assert report.failed == 0
    assert report.enforcement_report == enforcement_report

    # CLI 退出码只依赖最终 overall，验证真实进程语义为非零。
    monkeypatch.setattr(fast_gate, "run_fast_gate", lambda **kwargs: report)
    assert fast_gate.main(["--report-dir", str(tmp_path)]) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Step 9: 观察期结束，全部检查升级为阻断
# ═══════════════════════════════════════════════════════════════════════════════


class TestFastGateWarnModeStep3:
    """Step 9：观察期已结束，5 个安全检查已升级为阻断"""

    def test_warn_only_check_indices_has_step_12(self):
        """JSON-P1: 第 12 步 (JSON 响应契约序列化门禁) 处于观察期"""
        assert WARN_ONLY_CHECK_INDICES == [12], (
            f"当前 WARN_ONLY_CHECK_INDICES 应为 [12]（JSON 响应契约序列化门禁），实际: {WARN_ONLY_CHECK_INDICES}"
        )

    def test_warn_only_checks_list_is_empty(self):
        """观察期已结束，WARN_ONLY_CHECKS 应为空列表"""
        assert len(WARN_ONLY_CHECKS) == 0, (
            f"观察期结束后 WARN_ONLY_CHECKS 应为空，实际: {WARN_ONLY_CHECKS}"
        )

    def test_harness_step_has_warn_steps_12(self):
        """JSON-P1: 观察期内 harness 命令应包含 --warn-steps 12"""
        harness_step = next(step for step in STEPS if step["name"] == "harness")
        command_text = " ".join(harness_step["command"])

        assert "--warn-steps 12" in command_text, (
            f"观察期内 harness 命令应包含 --warn-steps 12:\n{command_text}"
        )
        assert "--json-summary" in command_text, (
            f"harness 步骤应包含 --json-summary:\n{command_text}"
        )

    def test_parse_harness_json_summary_all_blocking(self):
        """验证 _parse_harness_json_summary 正确解析全阻断模式 JSON（12 项阻断）"""
        stdout = (
            "一些输出...\n"
            '__HARNESS_JSON_SUMMARY__ {"blocking_pass": 12, "blocking_fail": 0, '
            '"warn_pass": 0, "warn_warn": 0, "warn_infra_fail": 0, '
            '"total_pass": 12, "total_warn": 0, "total_fail": 0, "total_steps": 12}\n'
            "更多输出..."
        )
        summary = _parse_harness_json_summary(stdout)
        assert summary is not None, "应成功解析 JSON 摘要"
        assert summary["blocking_pass"] == 12
        assert summary["blocking_fail"] == 0
        assert summary["warn_pass"] == 0
        assert summary["warn_warn"] == 0
        assert summary["warn_infra_fail"] == 0
        assert summary["total_steps"] == 12

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

    def test_all_12_checks_are_blocking(self):
        """JSON-P1: 不含 --warn-steps 时，所有 12 项检查均为阻断模式"""
        import subprocess
        import sys
        import os

        project_root = PROJECT_ROOT

        # 运行 harness，不传 --warn-steps（所有步骤均为阻断）
        result = subprocess.run(
            [
                sys.executable,
                "harness/run_harness.py",
                "--json-summary",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        # 全部检查通过时，退出码应为 0
        assert result.returncode == 0, (
            f"全阻断模式 + 全部通过 → exit 0:\nstderr:\n{result.stderr}"
        )

        # JSON 摘要应包含正确的统计：12 项阻断，0 项观察期
        summary = _parse_harness_json_summary(result.stdout)
        assert summary is not None, f"应输出 JSON 摘要:\n{result.stdout}"
        assert summary["blocking_pass"] == 12, f"全部检查应为阻断且通过: {summary}"
        assert summary["warn_pass"] == 0, f"warn_pass 应为 0: {summary}"
        assert summary["warn_warn"] == 0
        assert summary["warn_infra_fail"] == 0
        assert summary["blocking_fail"] == 0
        assert summary["total_fail"] == 0

    def test_fast_gate_report_warn_fields_are_zero(self, monkeypatch, tmp_path):
        """观察期结束后，FastGateReport 的 warn_* 字段应全部为 0"""
        harness_summary = {
            "blocking_pass": 11,
            "blocking_fail": 0,
            "warn_pass": 0,
            "warn_warn": 0,
            "warn_infra_fail": 0,
            "total_pass": 11,
            "total_warn": 0,
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

        assert report.overall == "PASS", "全部通过应 PASS"
        assert report.warn_checks_passed == 0, "观察期已结束，warn_checks_passed 应为 0"
        assert report.warn_checks_warned == 0
        assert report.warn_checks_infra_fail == 0

    def test_fast_gate_report_markdown_has_observation_section(self, monkeypatch, tmp_path):
        """JSON-P1 观察期内，生成的 Markdown 报告应包含「观察期检查」章节"""
        from harness.run_fast_gate import render_markdown

        harness_summary = {
            "blocking_pass": 11,
            "blocking_fail": 0,
            "warn_pass": 1,
            "warn_warn": 0,
            "warn_infra_fail": 0,
            "total_pass": 12,
            "total_warn": 0,
            "total_fail": 0,
            "total_steps": 12,
        }

        report = FastGateReport(
            run_id="test-step9",
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
                "display": "Harness 安全检查（11 项阻断 + 1 项观察）",
                "status": "PASS",
                "exit_code": 0,
                "stdout": "",
                "stderr": "",
                "duration_seconds": 0.5,
                "harness_summary": harness_summary,
            }],
            duration_total_seconds=1.0,
            warn_checks_passed=0,
            warn_checks_warned=0,
            warn_checks_infra_fail=0,
        )

        md = render_markdown(report)
        assert "观察期检查（warn-only）" in md, (
            f"JSON-P1 观察期内 Markdown 应出现观察期检查章节:\n{md[:500]}"
        )
        assert "观察期" in md, (
            f"Markdown 应包含「观察期」字样:\n{md[:500]}"
        )

    def test_fast_gate_stdout_has_observation_notice(self, tmp_path):
        """JSON-P1 观察期内，fast gate 输出应提示「观察期」"""
        import subprocess
        import sys
        import os

        project_root = PROJECT_ROOT
        result = subprocess.run(
            [sys.executable, "harness/run_fast_gate.py", "--step", "3",
             "--report-dir", str(tmp_path)],
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
            f"JSON-P1 观察期内输出应包含「观察期」:\n{result.stdout[:500]}"
        )
        assert "11 项阻断" in result.stdout, (
            f"输出应显示 11 项阻断:\n{result.stdout[:500]}"
        )
        # harness 步骤应通过
        assert result.returncode == 0, (
            f"harness 全阻断模式应正常退出:\nstderr:\n{result.stderr[:500]}"
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

    def test_security_check_failure_blocks_fast_gate(self, monkeypatch, tmp_path):
        """原步骤 7-11 安全门禁任一失败 → fast gate FAIL（观察期结束后）"""
        def fake_run_step(step, cwd, timeout_seconds=120):
            if step["name"] == "harness":
                return StepResult(
                    name=step["name"],
                    display=step["display"],
                    status="FAIL",
                    exit_code=1,
                    stdout="check_execution_strategy_safety.py FAIL: 检测到并发安全违规",
                    stderr="",
                    duration_seconds=0.5,
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

        # harness 安全门禁失败 → 应阻断（不再是 WARN 后继续 PASS）
        assert report.overall == "FAIL", (
            f"安全门禁失败应导致 FAIL，实际: {report.overall}"
        )
        assert report.failed >= 1, f"应有至少 1 个 FAIL，实际: {report.failed}"
