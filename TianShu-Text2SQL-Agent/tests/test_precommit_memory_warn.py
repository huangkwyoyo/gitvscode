"""Memory Harness Step 20 —— pre-commit warn 模式测试。

覆盖场景：
    1. 正常通过时 exit code = 0
    2. fast gate 失败时 exit code 仍为 0
    3. 失败时输出 WARNING
    4. 失败时输出 rule_id
    5. 失败时提示运行 python harness/run_fast_gate.py
    6. 脚本异常时 exit code 仍为 0
    7. 使用临时 report dir，不污染 harness/reports/*
    8. 不生成 latest
    9. 不修改 docs/memory/*
    10. 不修改 memory_rules.yml
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# 确保项目根目录在导入路径中
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.run_precommit_memory_warn import (
    _analyze_enforcement,
    _find_json_object_start,
    _find_matching_brace,
    _get_git_info,
    _get_worktree_dirty,
    _record_observation,
    _run_fast_gate_step3,
    render_warn_output,
    run_precommit_warn,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 测试夹具 —— 构造各种 FastGateReport 场景
# ═══════════════════════════════════════════════════════════════════════════════


def _make_pass_report() -> dict:
    """构造一个全部通过的 FastGateReport。"""
    return {
        "run_id": "test-pass-001",
        "timestamp": "2026-01-01T00:00:00Z",
        "total_steps": 1,
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "overall": "PASS",
        "enforcement_report": {
            "run_id": "MRE-test-001",
            "summary": {
                "total_rules": 21,
                "proposed": 20,
                "active_warning": 0,
                "active_blocking": 1,
                "deprecated": 0,
                "superseded": 0,
                "passed": 20,
                "warnings": 1,
                "blocking_failures": 0,
                "skipped": 0,
                "infra_errors": 0,
            },
            "rule_results": [
                {
                    "rule_id": "TA-R018",
                    "title": "LLM 融合安全规则",
                    "status": "active",
                    "blocking": True,
                    "enforcement_level": "blocking_error",
                    "result": "passed",
                    "message": "active+blocking=true 规则全部 required_checks 通过",
                    "required_checks": [],
                    "matched_check_results": [],
                },
            ],
            "exit_code_should_fail": False,
        },
    }


def _make_blocking_failure_report() -> dict:
    """构造一个包含 active+blocking=true 规则失败的 FastGateReport。"""
    return {
        "run_id": "test-fail-001",
        "timestamp": "2026-01-01T00:00:00Z",
        "total_steps": 1,
        "passed": 0,
        "failed": 1,
        "skipped": 0,
        "overall": "FAIL",
        "enforcement_report": {
            "run_id": "MRE-test-002",
            "summary": {
                "total_rules": 21,
                "proposed": 20,
                "active_warning": 0,
                "active_blocking": 1,
                "deprecated": 0,
                "superseded": 0,
                "passed": 20,
                "warnings": 0,
                "blocking_failures": 1,
                "skipped": 0,
                "infra_errors": 0,
            },
            "rule_results": [
                {
                    "rule_id": "TA-R018",
                    "title": "LLM 融合安全规则",
                    "status": "active",
                    "blocking": True,
                    "enforcement_level": "blocking_error",
                    "result": "FAIL",
                    "message": (
                        "active+blocking=true 规则 TA-R018 的 1 项 required_checks 失败"
                        "（检查项），fast gate 阻断。"
                    ),
                    "failed_required_checks": [
                        "harness/checks/check_result_fusion_safety.py"
                    ],
                    "failure_message": "检查项 status=FAIL, exit_code=1",
                    "suggested_fix": "检查上述 required_check 的检查输出，修复失败原因后重新运行 fast gate。",
                    "rollback_plan": (
                        "将 memory_rules.yml 中 TA-R018 的 blocking 从 true 改回 false，"
                        "即可恢复非阻断模式，无需修改业务代码。"
                    ),
                    "required_checks": [
                        "harness/checks/check_result_fusion_safety.py",
                        "harness/checks/check_cross_domain_policy.py",
                    ],
                    "matched_check_results": [
                        {
                            "name": "结果融合安全",
                            "script": "harness/checks/check_result_fusion_safety.py",
                            "status": "FAIL",
                            "exit_code": 1,
                        },
                    ],
                },
            ],
            "exit_code_should_fail": True,
        },
    }


def _make_no_enforcement_report() -> dict:
    """构造一个不含 enforcement_report 的 FastGateReport。"""
    return {
        "run_id": "test-noenf-001",
        "timestamp": "2026-01-01T00:00:00Z",
        "total_steps": 1,
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "overall": "PASS",
        # enforcement_report 缺失
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：_find_json_object_start 和 _find_matching_brace
# ═══════════════════════════════════════════════════════════════════════════════


def test_find_json_object_start_top_level():
    """顶层 JSON（2 空格缩进）应被正确匹配。"""
    stdout = '一些前置文本\n{\n  "run_id": "test-001",\n  "overall": "PASS"\n}\n后续文本'
    pos = _find_json_object_start(stdout)
    assert pos >= 0
    assert stdout[pos] == "{"


def test_find_json_object_start_nested_not_matched():
    """嵌套 JSON（4 空格缩进）不应被误匹配为顶层对象。"""
    # 构造一个包含嵌套 enforcement_report 的 stdout 片段
    # 顶层是 2 空格缩进，嵌套是 4 空格缩进
    stdout = (
        '前文\n'
        '{\n'
        '  "run_id": "top-level",\n'
        '  "enforcement_report": {\n'
        '    "run_id": "nested-level",\n'
        '    "summary": {}\n'
        '  }\n'
        '}\n'
        '后文'
    )
    pos = _find_json_object_start(stdout)
    assert pos >= 0
    # 验证匹配到的是顶层 {（在 "top-level" 之前），而非嵌套 {（在 "nested-level" 之前）
    text_from_pos = stdout[pos:]
    assert '"run_id": "top-level"' in text_from_pos[:100]


def test_find_json_object_start_no_match():
    """无 JSON 时应返回 -1。"""
    stdout = '只有普通文本，没有 JSON 对象'
    assert _find_json_object_start(stdout) == -1


def test_find_matching_brace_simple():
    """简单花括号匹配。"""
    text = '{"key": "value"}'
    end = _find_matching_brace(text, 0)
    assert end == len(text) - 1
    assert text[end] == "}"


def test_find_matching_brace_nested():
    """嵌套花括号应正确匹配。"""
    text = '{"outer": {"inner": [1, 2, 3]}, "key": "val"}'
    end = _find_matching_brace(text, 0)
    assert text[end] == "}"
    # 解析整个子串验证是合法 JSON
    parsed = json.loads(text[0:end + 1])
    assert parsed["key"] == "val"


def test_find_matching_brace_invalid_start():
    """起始字符非 { 应返回 -1。"""
    assert _find_matching_brace("not a brace", 0) == -1


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：_analyze_enforcement
# ═══════════════════════════════════════════════════════════════════════════════


def test_analyze_enforcement_pass():
    """全部通过的 enforcement 报告应正确解析。"""
    report = _make_pass_report()
    analysis = _analyze_enforcement(report)

    assert analysis["enforcement_available"] is True
    assert analysis["blocking_failures"] == 0
    assert analysis["failure_rules"] == []


def test_analyze_enforcement_blocking_failure():
    """有阻断失败的 enforcement 报告应正确解析。"""
    report = _make_blocking_failure_report()
    analysis = _analyze_enforcement(report)

    assert analysis["enforcement_available"] is True
    assert analysis["blocking_failures"] == 1
    assert len(analysis["failure_rules"]) == 1
    assert analysis["failure_rules"][0]["rule_id"] == "TA-R018"
    assert analysis["failure_rules"][0]["result"] == "FAIL"


def test_analyze_enforcement_no_report():
    """无 enforcement_report 时应标记为不可用。"""
    report = _make_no_enforcement_report()
    analysis = _analyze_enforcement(report)

    assert analysis["enforcement_available"] is False
    assert analysis["blocking_failures"] == 0
    assert analysis["failure_rules"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：render_warn_output
# ═══════════════════════════════════════════════════════════════════════════════


def test_render_warn_output_pass():
    """全部通过时应输出简洁的 PASS 摘要。"""
    report = _make_pass_report()
    analysis = _analyze_enforcement(report)
    output = render_warn_output(analysis)

    assert "全部通过" in output


def test_render_warn_output_blocking_failure_shows_warning():
    """阻断失败时必须输出 WARNING 标识。"""
    report = _make_blocking_failure_report()
    analysis = _analyze_enforcement(report)
    output = render_warn_output(analysis)

    assert "WARNING" in output


def test_render_warn_output_blocking_failure_shows_rule_id():
    """阻断失败时必须输出 rule_id。"""
    report = _make_blocking_failure_report()
    analysis = _analyze_enforcement(report)
    output = render_warn_output(analysis)

    assert "TA-R018" in output


def test_render_warn_output_blocking_failure_suggests_fast_gate():
    """阻断失败时必须提示运行 python harness/run_fast_gate.py。"""
    report = _make_blocking_failure_report()
    analysis = _analyze_enforcement(report)
    output = render_warn_output(analysis)

    assert "python harness/run_fast_gate.py" in output


def test_render_warn_output_blocking_failure_shows_failed_check():
    """阻断失败时必须列出失败的检查项。"""
    report = _make_blocking_failure_report()
    analysis = _analyze_enforcement(report)
    output = render_warn_output(analysis)

    assert "check_result_fusion_safety" in output


def test_render_warn_output_no_enforcement():
    """无 enforcement 报告时应输出 WARN 跳过信息。"""
    report = _make_no_enforcement_report()
    analysis = _analyze_enforcement(report)
    output = render_warn_output(analysis)

    assert "WARN" in output
    assert "跳过" in output


def test_render_warn_output_does_not_block_commit():
    """输出应明确说明不阻断 commit。"""
    report = _make_blocking_failure_report()
    analysis = _analyze_enforcement(report)
    output = render_warn_output(analysis)

    assert "不阻断 commit" in output


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：run_precommit_warn —— exit code 始终为 0
# ═══════════════════════════════════════════════════════════════════════════════


def test_run_precommit_warn_pass_returns_zero(monkeypatch):
    """正常通过时 exit code 必须为 0。"""
    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        lambda report_dir: _make_pass_report(),
    )
    exit_code = run_precommit_warn()
    assert exit_code == 0


def test_run_precommit_warn_blocking_failure_returns_zero(monkeypatch):
    """fast gate 发现 active+blocking=true 规则失败时，exit code 仍为 0。"""
    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        lambda report_dir: _make_blocking_failure_report(),
    )
    exit_code = run_precommit_warn()
    assert exit_code == 0


def test_run_precommit_warn_no_enforcement_returns_zero(monkeypatch):
    """无 enforcement_report 时 exit code 仍为 0。"""
    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        lambda report_dir: _make_no_enforcement_report(),
    )
    exit_code = run_precommit_warn()
    assert exit_code == 0


def test_run_precommit_warn_subprocess_error_returns_zero(monkeypatch):
    """fast gate 子进程执行失败时 exit code 仍为 0。"""
    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        lambda report_dir: None,
    )
    exit_code = run_precommit_warn()
    assert exit_code == 0


def test_run_precommit_warn_exception_returns_zero(monkeypatch):
    """内部异常时 exit code 仍为 0。"""
    def _raise_exception(report_dir):
        raise RuntimeError("模拟内部异常")
    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        _raise_exception,
    )
    exit_code = run_precommit_warn()
    assert exit_code == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：WARNING 输出内容
# ═══════════════════════════════════════════════════════════════════════════════


def test_blocking_failure_output_contains_warning(capsys, monkeypatch):
    """阻断失败时 stdout 必须包含 WARNING。"""
    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        lambda report_dir: _make_blocking_failure_report(),
    )
    run_precommit_warn()
    captured = capsys.readouterr()
    assert "WARNING" in captured.out


def test_blocking_failure_output_contains_rule_id(capsys, monkeypatch):
    """阻断失败时输出必须包含 rule_id。"""
    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        lambda report_dir: _make_blocking_failure_report(),
    )
    run_precommit_warn()
    captured = capsys.readouterr()
    assert "TA-R018" in captured.out


def test_blocking_failure_output_suggests_fast_gate(capsys, monkeypatch):
    """阻断失败时输出必须提示运行 python harness/run_fast_gate.py。"""
    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        lambda report_dir: _make_blocking_failure_report(),
    )
    run_precommit_warn()
    captured = capsys.readouterr()
    assert "python harness/run_fast_gate.py" in captured.out


def test_pass_output_is_quiet_in_quiet_mode(capsys, monkeypatch):
    """quiet 模式下全部通过时不应输出任何内容。"""
    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        lambda report_dir: _make_pass_report(),
    )
    run_precommit_warn(quiet=True)
    captured = capsys.readouterr()
    assert captured.out.strip() == ""


def test_failure_output_still_shows_in_quiet_mode(capsys, monkeypatch):
    """quiet 模式下有阻断失败时仍应输出 WARNING。"""
    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        lambda report_dir: _make_blocking_failure_report(),
    )
    run_precommit_warn(quiet=True)
    captured = capsys.readouterr()
    assert "WARNING" in captured.out


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：临时目录与隔离
# ═══════════════════════════════════════════════════════════════════════════════


def test_uses_temporary_report_dir(monkeypatch):
    """验证 fast gate 使用临时目录而非 harness/reports。"""
    captured_dir: list[str] = []

    def _capture_dir(report_dir: str) -> dict:
        captured_dir.append(report_dir)
        return _make_pass_report()

    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        _capture_dir,
    )
    run_precommit_warn()
    assert len(captured_dir) == 1
    # 临时目录不应是 harness/reports
    assert "harness/reports" not in captured_dir[0]


def test_temp_dir_is_cleaned_up(monkeypatch):
    """临时目录应在脚本结束后被清理。"""
    import tempfile as tf
    # 使用项目内的临时目录避免 Windows tmp_path 权限问题
    temp_subdir = str(PROJECT_ROOT / "harness" / "reports" / "precommit_test_tmp")

    def _fake_run(report_dir: str) -> dict:
        # 写入一个文件到 report_dir，后续检查是否被清理
        marker = Path(report_dir) / "marker.txt"
        marker.write_text("test", encoding="utf-8")
        return _make_pass_report()

    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        _fake_run,
    )
    # 使用自定义 temp_root 便于观察
    exit_code = run_precommit_warn(temp_root=temp_subdir)
    assert exit_code == 0

    # 验证临时目录已被清理（不应存在 marker 文件）
    remaining = list(Path(temp_subdir).glob("memory_warn_*"))
    assert len(remaining) == 0, f"临时目录未被清理: {remaining}"


def test_no_latest_files_generated(monkeypatch):
    """不应在 harness/reports/ 下生成任何 latest 文件。（脚本使用临时目录）"""
    # 检查 harness/reports 下当前的文件列表
    reports_dir = PROJECT_ROOT / "harness" / "reports"
    before_files = set()
    if reports_dir.exists():
        before_files = {f.name for f in reports_dir.iterdir()}

    def _fake_run_with_temp(report_dir: str) -> dict:
        return _make_blocking_failure_report()

    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        _fake_run_with_temp,
    )
    run_precommit_warn()

    # 验证 harness/reports 下没有新文件
    if reports_dir.exists():
        after_files = {f.name for f in reports_dir.iterdir()}
        new_files = after_files - before_files
        # 排除测试自身可能生成的临时目录
        new_files = {f for f in new_files if "precommit_test_tmp" not in f}
        assert len(new_files) == 0, f"不应有新文件: {new_files}"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：不修改 docs/memory/* 和 memory_rules.yml
# ═══════════════════════════════════════════════════════════════════════════════


def test_does_not_modify_memory_rules_yml(monkeypatch):
    """验证脚本不修改 memory_rules.yml。"""
    rules_path = PROJECT_ROOT / "docs" / "memory" / "memory_rules.yml"
    if not rules_path.exists():
        pytest.skip("memory_rules.yml 不存在")

    # 记录当前内容
    original_content = rules_path.read_bytes()

    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        lambda report_dir: _make_blocking_failure_report(),
    )
    run_precommit_warn()

    # 验证内容未变
    assert rules_path.read_bytes() == original_content, "memory_rules.yml 不应被修改"


def test_does_not_modify_memory_docs(monkeypatch):
    """验证脚本不修改 docs/memory/ 下的文件。"""
    memory_dir = PROJECT_ROOT / "docs" / "memory"
    if not memory_dir.exists():
        pytest.skip("docs/memory/ 不存在")

    # 记录所有文件的修改时间
    mtimes_before = {}
    for f in memory_dir.rglob("*"):
        if f.is_file():
            mtimes_before[str(f)] = f.stat().st_mtime

    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        lambda report_dir: _make_blocking_failure_report(),
    )
    run_precommit_warn()

    # 验证所有文件修改时间未变
    for f in memory_dir.rglob("*"):
        if f.is_file():
            key = str(f)
            if key in mtimes_before:
                assert f.stat().st_mtime == mtimes_before[key], (
                    f"{f.name} 不应被修改"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：main 函数 —— CLI 入口
# ═══════════════════════════════════════════════════════════════════════════════


def test_main_returns_zero(monkeypatch):
    """CLI 入口应始终返回 0。"""
    from harness.run_precommit_memory_warn import main

    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        lambda report_dir: _make_pass_report(),
    )
    assert main([]) == 0

    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        lambda report_dir: _make_blocking_failure_report(),
    )
    assert main([]) == 0


def test_main_quiet_flag(monkeypatch, capsys):
    """--quiet 标志应正确的被传递。"""
    from harness.run_precommit_memory_warn import main

    monkeypatch.setattr(
        "harness.run_precommit_memory_warn._run_fast_gate_step3",
        lambda report_dir: _make_pass_report(),
    )
    main(["--quiet"])
    captured = capsys.readouterr()
    # quiet 模式 + 全部通过 → 无输出
    assert captured.out.strip() == ""


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：不调用 LLM
# ═══════════════════════════════════════════════════════════════════════════════


def test_no_llm_imports():
    """脚本不应导入任何 LLM 相关模块。"""
    import inspect
    from harness import run_precommit_memory_warn as script

    source = inspect.getsource(script)
    # 不应包含 LLM provider 相关的导入
    llm_indicators = [
        "deepseek",
        "openai",
        "anthropic",
        "requests.post",
        "httpx",
    ]
    for indicator in llm_indicators:
        assert indicator not in source.lower(), (
            f"脚本不应包含 LLM 调用相关代码: {indicator}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：Step 21b — observation 记录功能
# ═══════════════════════════════════════════════════════════════════════════════


class TestObservationRecording:
    """Step 21b 观察证据收集器测试。"""

    @staticmethod
    def _mock_git_clean():
        """模拟工作区干净（无未提交变更）。"""
        return False

    @staticmethod
    def _mock_git_dirty():
        """模拟工作区有变更。"""
        return True

    @staticmethod
    def _mock_git_info():
        """模拟 git 信息返回。"""
        return {
            "commit": "7d915ddfe8a1bc3c4f5e6d7a8b9c0d1e2f3a4b5c",
            "branch": "main",
        }

    def test_record_observation_creates_json(self, monkeypatch, tmp_path):
        """--record-observation 应生成 timestamp JSON 文件。"""
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._run_fast_gate_step3",
            lambda report_dir: _make_pass_report(),
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_worktree_dirty",
            self._mock_git_clean,
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_git_info",
            self._mock_git_info,
        )

        obs_dir = str(tmp_path / "history")
        exit_code = run_precommit_warn(
            record_observation=True,
            observation_dir=obs_dir,
        )
        assert exit_code == 0

        # 验证生成 JSON 文件
        json_files = list(Path(obs_dir).glob("*.json"))
        assert len(json_files) == 1, f"应有 1 个 JSON 文件，实际: {json_files}"
        assert "latest" not in json_files[0].name.lower()

        # 验证 JSON 内容结构
        data = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert data["report_type"] == "precommit_memory_warn_single_observation"

    def test_observation_filename_not_latest(self, monkeypatch, tmp_path):
        """observation 文件名不应包含 latest。"""
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._run_fast_gate_step3",
            lambda report_dir: _make_pass_report(),
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_worktree_dirty",
            self._mock_git_clean,
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_git_info",
            self._mock_git_info,
        )

        obs_dir = str(tmp_path / "history")
        run_precommit_warn(
            record_observation=True,
            observation_dir=obs_dir,
        )

        all_files = list(Path(obs_dir).rglob("*"))
        for f in all_files:
            if f.is_file():
                assert "latest" not in f.name.lower(), (
                    f"文件名不应包含 latest: {f.name}"
                )

    def test_observation_records_duration_and_exit_code(self, monkeypatch, tmp_path):
        """observation 应记录 duration_ms 和 exit_code。"""
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._run_fast_gate_step3",
            lambda report_dir: _make_pass_report(),
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_worktree_dirty",
            self._mock_git_clean,
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_git_info",
            self._mock_git_info,
        )

        obs_dir = str(tmp_path / "history")
        run_precommit_warn(
            record_observation=True,
            observation_dir=obs_dir,
        )

        json_files = list(Path(obs_dir).glob("*.json"))
        data = json.loads(json_files[0].read_text(encoding="utf-8"))

        assert "duration_ms" in data
        assert isinstance(data["duration_ms"], (int, float))
        assert data["duration_ms"] > 0
        assert data["exit_code"] == 0
        assert data["memory_warn_exit_code"] == 0

    def test_observation_records_git_commit(self, monkeypatch, tmp_path):
        """observation 应记录 git_commit 和 branch。"""
        expected_commit = "abc123def456"
        expected_branch = "feature/test"

        def _mock_info():
            return {"commit": expected_commit, "branch": expected_branch}

        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._run_fast_gate_step3",
            lambda report_dir: _make_pass_report(),
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_worktree_dirty",
            self._mock_git_clean,
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_git_info",
            _mock_info,
        )

        obs_dir = str(tmp_path / "history")
        run_precommit_warn(
            record_observation=True,
            observation_dir=obs_dir,
        )

        json_files = list(Path(obs_dir).glob("*.json"))
        data = json.loads(json_files[0].read_text(encoding="utf-8"))

        assert data["git_commit"] == expected_commit
        assert data["branch"] == expected_branch

    def test_observation_records_active_blocking_rules(self, monkeypatch, tmp_path):
        """observation 应记录 active_blocking_rules 包含 TA-R018。"""
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._run_fast_gate_step3",
            lambda report_dir: _make_pass_report(),
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_worktree_dirty",
            self._mock_git_clean,
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_git_info",
            self._mock_git_info,
        )

        obs_dir = str(tmp_path / "history")
        run_precommit_warn(
            record_observation=True,
            observation_dir=obs_dir,
        )

        json_files = list(Path(obs_dir).glob("*.json"))
        data = json.loads(json_files[0].read_text(encoding="utf-8"))

        assert "active_blocking_rules" in data
        assert "TA-R018" in data["active_blocking_rules"]

    def test_observation_records_worktree_dirty(self, monkeypatch, tmp_path):
        """observation 应记录 worktree_dirty_before 和 worktree_dirty_after。"""
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._run_fast_gate_step3",
            lambda report_dir: _make_pass_report(),
        )
        # 模拟运行前工作区有变更
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_worktree_dirty",
            self._mock_git_dirty,
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_git_info",
            self._mock_git_info,
        )

        obs_dir = str(tmp_path / "history")
        run_precommit_warn(
            record_observation=True,
            observation_dir=obs_dir,
        )

        json_files = list(Path(obs_dir).glob("*.json"))
        data = json.loads(json_files[0].read_text(encoding="utf-8"))

        assert "worktree_dirty_before" in data
        assert "worktree_dirty_after" in data
        # 两次调用 _get_worktree_dirty 都返回 True
        assert data["worktree_dirty_before"] is True
        assert data["worktree_dirty_after"] is True

    def test_observation_write_failure_still_exit_zero(self, monkeypatch, tmp_path):
        """observation 写入失败时脚本应仍 exit 0 并输出 warning。"""
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._run_fast_gate_step3",
            lambda report_dir: _make_pass_report(),
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_worktree_dirty",
            self._mock_git_clean,
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_git_info",
            self._mock_git_info,
        )
        # 模拟 _record_observation 内部异常
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._record_observation",
            lambda **kwargs: (_ for _ in ()).throw(RuntimeError("模拟写入失败")),
        )

        exit_code = run_precommit_warn(
            record_observation=True,
            observation_dir=str(tmp_path / "no-perm-dir"),
        )
        assert exit_code == 0

    def test_observation_on_failure_still_exit_zero(self, monkeypatch, tmp_path):
        """warn 失败场景下 record_observation 仍应 exit 0。"""
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._run_fast_gate_step3",
            lambda report_dir: _make_blocking_failure_report(),
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_worktree_dirty",
            self._mock_git_clean,
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_git_info",
            self._mock_git_info,
        )

        obs_dir = str(tmp_path / "history")
        exit_code = run_precommit_warn(
            record_observation=True,
            observation_dir=obs_dir,
        )
        assert exit_code == 0

        # 同时验证 observation 记录了 warning_count > 0
        json_files = list(Path(obs_dir).glob("*.json"))
        data = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert data["warning_count"] >= 1
        assert data["ta_r018_result"] == "failed"

    def test_record_observation_uses_temp_report_dir(self, monkeypatch, tmp_path):
        """record_observation 模式下仍使用临时 report dir，不污染 harness/reports。"""
        captured_dir: list[str] = []

        def _capture_dir(report_dir: str) -> dict:
            captured_dir.append(report_dir)
            return _make_pass_report()

        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._run_fast_gate_step3",
            _capture_dir,
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_worktree_dirty",
            self._mock_git_clean,
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_git_info",
            self._mock_git_info,
        )

        obs_dir = str(tmp_path / "history")
        run_precommit_warn(
            record_observation=True,
            observation_dir=obs_dir,
        )

        assert len(captured_dir) == 1
        # report_dir 不应是 harness/reports
        assert "harness/reports" not in str(captured_dir[0])

    def test_record_observation_no_docs_modification(self, monkeypatch, tmp_path):
        """record_observation 模式下不修改 docs/memory/*。"""
        memory_dir = PROJECT_ROOT / "docs" / "memory"
        if not memory_dir.exists():
            pytest.skip("docs/memory/ 不存在")

        # 记录修改时间
        mtimes_before = {}
        for f in memory_dir.rglob("*"):
            if f.is_file():
                mtimes_before[str(f)] = f.stat().st_mtime

        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._run_fast_gate_step3",
            lambda report_dir: _make_pass_report(),
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_worktree_dirty",
            self._mock_git_clean,
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_git_info",
            self._mock_git_info,
        )

        obs_dir = str(tmp_path / "history")
        run_precommit_warn(
            record_observation=True,
            observation_dir=obs_dir,
        )

        for f in memory_dir.rglob("*"):
            if f.is_file():
                key = str(f)
                if key in mtimes_before:
                    assert f.stat().st_mtime == mtimes_before[key], (
                        f"{f.name} 不应被修改"
                    )

    def test_record_observation_no_rules_modification(self, monkeypatch, tmp_path):
        """record_observation 模式下不修改 memory_rules.yml。"""
        rules_path = PROJECT_ROOT / "docs" / "memory" / "memory_rules.yml"
        if not rules_path.exists():
            pytest.skip("memory_rules.yml 不存在")

        original_content = rules_path.read_bytes()

        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._run_fast_gate_step3",
            lambda report_dir: _make_pass_report(),
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_worktree_dirty",
            self._mock_git_clean,
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_git_info",
            self._mock_git_info,
        )

        obs_dir = str(tmp_path / "history")
        run_precommit_warn(
            record_observation=True,
            observation_dir=obs_dir,
        )

        assert rules_path.read_bytes() == original_content, (
            "memory_rules.yml 不应被修改"
        )

    def test_main_supports_record_observation_flag(self, monkeypatch, tmp_path):
        """main() 的 --record-observation 标志应正确传递。"""
        from harness.run_precommit_memory_warn import main

        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._run_fast_gate_step3",
            lambda report_dir: _make_pass_report(),
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_worktree_dirty",
            self._mock_git_clean,
        )
        monkeypatch.setattr(
            "harness.run_precommit_memory_warn._get_git_info",
            self._mock_git_info,
        )

        obs_dir = str(tmp_path / "history")
        result = main([
            "--record-observation",
            "--observation-dir", obs_dir,
        ])
        assert result == 0

        # 验证确实生成了 observation 文件
        json_files = list(Path(obs_dir).glob("*.json"))
        assert len(json_files) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：_get_git_info 和 _get_worktree_dirty 辅助函数
# ═══════════════════════════════════════════════════════════════════════════════


def test_get_git_info_returns_dict():
    """_get_git_info 应返回包含 commit 和 branch 的 dict。"""
    info = _get_git_info()
    assert isinstance(info, dict)
    assert "commit" in info
    assert "branch" in info
    # 在 git 仓库中应能获取到非 unknown 的值
    assert len(info["commit"]) >= 7 or info["commit"] == "unknown"


def test_get_worktree_dirty_returns_bool():
    """_get_worktree_dirty 应返回 bool。"""
    dirty = _get_worktree_dirty()
    assert isinstance(dirty, bool)
