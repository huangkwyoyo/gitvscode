from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.baselines.dual_baseline import (
    BaselineCommand,
    CommandResult,
    build_runtime_commands,
    build_source_commands,
    calculate_runtime_status,
    calculate_source_status,
    redact_sensitive_text,
    run_runtime_baseline,
    write_snapshot_files,
)


def test_source_status_dirty_has_priority():
    """Source 基线遇到运行前 dirty 必须标记 DIRTY"""
    commands = [
        CommandResult(name="pytest", command=["python", "-m", "pytest", "-q"], executed=True, exit_code=0),
        CommandResult(name="harness", command=["python", "harness/run_harness.py"], executed=True, exit_code=0),
    ]

    status = calculate_source_status(working_tree_dirty_before=True, commands=commands)

    assert status.status == "DIRTY"
    assert "working tree" in status.reason


def test_source_status_fails_on_nonzero_exit_code():
    """Source 基线任一命令失败时必须标记 FAIL"""
    commands = [
        CommandResult(name="pytest", command=["python", "-m", "pytest", "-q"], executed=True, exit_code=1),
        CommandResult(name="harness", command=["python", "harness/run_harness.py"], executed=True, exit_code=0),
    ]

    status = calculate_source_status(working_tree_dirty_before=False, commands=commands)

    assert status.status == "FAIL"
    assert "pytest" in status.reason


def test_source_status_blocks_when_command_not_executed():
    """Source 基线缺少执行项时必须标记 BLOCKED"""
    commands = [
        CommandResult(name="pytest", command=["python", "-m", "pytest", "-q"], executed=False, exit_code=None),
    ]

    status = calculate_source_status(working_tree_dirty_before=False, commands=commands)

    assert status.status == "BLOCKED"


def test_runtime_status_uses_unstable_for_provider_failures():
    """Runtime 基线的 provider 或网络失败应归为 UNSTABLE"""
    commands = [
        CommandResult(
            name="prompt_regression",
            command=["python", "harness/run_prompt_regression.py", "--provider", "deepseek"],
            executed=True,
            exit_code=1,
            stderr="Provider timeout while calling DeepSeek API",
        )
    ]

    status = calculate_runtime_status(commands)

    assert status.status == "UNSTABLE"
    assert "provider" in status.reason.lower() or "network" in status.reason.lower()


def test_runtime_status_does_not_use_dirty_status():
    """Runtime 基线不能把文件副作用折算成 DIRTY"""
    commands = [
        CommandResult(name="prompt_regression", command=["cmd"], executed=True, exit_code=0),
        CommandResult(name="llm_e2e_eval", command=["cmd"], executed=True, exit_code=0),
    ]

    status = calculate_runtime_status(commands)

    assert status.status == "PASS"
    assert status.status != "DIRTY"


def test_build_source_commands_do_not_include_real_llm_runners():
    """Source 命令可以包含 mock provider 的回归脚本，但不能包含真实 LLM provider"""
    commands = build_source_commands()
    flattened = " ".join(" ".join(item.command) for item in commands)

    # mock provider 的回归脚本允许出现在 source baseline 中
    # （用于验证 prompt 模板和 E2E 逻辑在离线状态下不退化）
    assert "--provider mock" in flattened or "run_prompt_regression.py" in flattened
    # 但不能有真实 provider 调用
    assert "--provider deepseek" not in flattened
    assert "--provider openai" not in flattened
    # 核心检查必须存在
    assert "pytest" in flattened
    assert "run_harness.py" in flattened


def test_build_source_commands_use_shared_pytest_entry():
    """Source baseline 必须复用统一 pytest 临时目录插件。"""
    commands = build_source_commands()
    pytest_commands = [item.command for item in commands if item.name == "pytest"]

    assert pytest_commands
    pytest_command = pytest_commands[0]
    assert pytest_command[:3] == [sys.executable, "-m", "pytest"]
    assert "--basetemp" not in pytest_command


def test_build_runtime_commands_include_only_llm_runners():
    """Runtime 命令只包含真实 LLM 评估入口"""
    commands = build_runtime_commands(provider="deepseek")
    flattened = " ".join(" ".join(item.command) for item in commands)

    assert "run_prompt_regression.py" in flattened
    assert "run_llm_e2e_eval.py" in flattened
    assert "run_harness.py" not in flattened
    assert "--provider deepseek" in flattened


def test_redact_sensitive_text_removes_api_keys():
    """快照文本不能泄露 API Key"""
    text = "OPENAI_API_KEY=sk-secret-value Authorization: Bearer abc123 token=xyz"

    redacted = redact_sensitive_text(text)

    assert "sk-secret-value" not in redacted
    assert "abc123" not in redacted
    assert "xyz" not in redacted
    assert "[REDACTED]" in redacted


def test_write_snapshot_files_uses_separate_directories(tmp_path):
    """Source 与 Runtime 快照必须写入隔离目录"""
    source_snapshot = {
        "schema_version": "1.0",
        "baseline_type": "source",
        "run_id": "source_20260614T010203Z",
        "timestamp": "2026-06-14T01:02:03Z",
        "status": "PASS",
        "commands": [],
        "file_diff": {"summary": {"added": 0, "modified": 0, "deleted": 0}},
    }
    runtime_snapshot = {
        "schema_version": "1.0",
        "baseline_type": "runtime_llm",
        "run_id": "runtime_llm_20260614T010203Z",
        "timestamp": "2026-06-14T01:02:03Z",
        "status": "UNSTABLE",
        "provider": "deepseek",
        "commands": [],
        "file_diff": {"summary": {"added": 1, "modified": 2, "deleted": 0}},
    }

    source_paths = write_snapshot_files(source_snapshot, tmp_path)
    runtime_paths = write_snapshot_files(runtime_snapshot, tmp_path)

    assert source_paths["json"].parent == tmp_path / "source"
    assert runtime_paths["json"].parent == tmp_path / "runtime"
    assert source_paths["json"].name.startswith("source_baseline_")
    assert runtime_paths["json"].name.startswith("runtime_llm_baseline_")

    source_data = json.loads(source_paths["json"].read_text(encoding="utf-8"))
    runtime_md = runtime_paths["markdown"].read_text(encoding="utf-8")
    assert source_data["baseline_type"] == "source"
    assert "Runtime LLM Baseline" in runtime_md


def test_runtime_baseline_snapshot_contains_failure_triage(tmp_path):
    """Runtime baseline 应附带 failure_triage，但不改变 exit code 判定。"""
    report_dir = tmp_path / "harness" / "reports"
    report_dir.mkdir(parents=True)
    (report_dir / "llm_e2e_eval_latest.json").write_text(
        json.dumps(
            {
                "run_id": "e2e_run",
                "cases": [
                    {
                        "case_id": "bad_refusal",
                        "question_zh": "删除数据",
                        "expected_behavior": "refusal",
                        "passed": False,
                        "failure_categories": ["refusal_mismatch"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def fake_runner(command: BaselineCommand, cwd: Path, timeout: int) -> CommandResult:
        return CommandResult(
            name=command.name,
            command=command.command,
            executed=True,
            exit_code=0,
            stdout="ok",
        )

    snapshot = run_runtime_baseline(
        cwd=tmp_path,
        output_dir=tmp_path / "baselines",
        command_runner=fake_runner,
    )

    assert snapshot["status"] == "PASS"
    assert snapshot["failure_triage"]["total_failed"] == 1
    assert snapshot["failure_triage"]["items"][0]["failure_type"] == "应拒绝但回答"
