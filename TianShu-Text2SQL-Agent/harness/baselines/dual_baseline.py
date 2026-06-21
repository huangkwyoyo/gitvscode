"""双基线快照的编排与报告生成。"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from harness.baselines.failure_triage import load_failure_triage_from_report
from harness.memory_suggestion_pipeline import (
    render_pipeline_summary_for_baseline,
    run_pipeline_on_failure_triage,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE_DIR = Path("harness/reports/baselines")


@dataclass
class CommandResult:
    """记录单条命令的真实执行证据。"""

    name: str
    command: list[str]
    executed: bool
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    error_message: str | None = None


@dataclass
class BaselineStatus:
    """统一状态与判定原因。"""

    status: str
    reason: str


@dataclass
class BaselineCommand:
    """Runner 需要执行的命令定义。"""

    name: str
    command: list[str]


@dataclass
class GitState:
    """记录执行前后的 git 状态。"""

    head: str | None
    status_porcelain: str
    dirty: bool


@dataclass
class FileDiff:
    """记录 baseline 前后的文件变化。"""

    before_status: str
    after_status: str
    diff_stat: str
    summary: dict[str, int] = field(default_factory=dict)


def build_source_commands() -> list[BaselineCommand]:
    """构造 Source 基线命令，禁止包含真实 LLM runner。

    Source Baseline 覆盖五项检查：
        1. compileall — 代码编译检查（src + harness + tests）
        2. pytest — 全部单元测试（Mock 模式，不调用 LLM）
        3. harness — 五项安全检查（SQL 只读 / IR schema / 拒绝策略 / 层级合规 / 指标注册）
        4. mock_prompt_regression — Mock Prompt 回归（验证工程链路完整）
        5. mock_e2e_eval — Mock E2E 端到端评测（验证 Golden Path 完整）
    """
    return [
        BaselineCommand(
            "compile_check",
            [sys.executable, "-m", "compileall", "-q", "src", "harness", "tests"],
        ),
        BaselineCommand(
            "pytest",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
            ],
        ),
        BaselineCommand(
            "harness",
            [sys.executable, "harness/run_harness.py"],
        ),
        BaselineCommand(
            "mock_prompt_regression",
            [
                sys.executable,
                "harness/run_prompt_regression.py",
                "--provider", "mock",
            ],
        ),
        BaselineCommand(
            "mock_e2e_eval",
            [
                sys.executable,
                "harness/run_llm_e2e_eval.py",
                "--provider", "mock",
            ],
        ),
    ]


def build_runtime_commands(provider: str = "deepseek", model: str | None = None) -> list[BaselineCommand]:
    """构造 Runtime LLM 基线命令，只运行真实 LLM 相关评估。"""
    prompt_command = [
        sys.executable,
        "harness/run_prompt_regression.py",
        "--provider",
        provider,
    ]
    e2e_command = [
        sys.executable,
        "harness/run_llm_e2e_eval.py",
        "--provider",
        provider,
    ]
    if model:
        prompt_command.extend(["--model", model])
        e2e_command.extend(["--model", model])
    return [
        BaselineCommand("prompt_regression", prompt_command),
        BaselineCommand("llm_e2e_eval", e2e_command),
    ]


def calculate_source_status(
    working_tree_dirty_before: bool,
    commands: Iterable[CommandResult],
) -> BaselineStatus:
    """按 Source 规则计算状态，dirty 优先于其他结论。"""
    command_list = list(commands)
    if working_tree_dirty_before:
        return BaselineStatus("DIRTY", "working tree dirty before source baseline")
    blocked = [item.name for item in command_list if not item.executed]
    if blocked:
        return BaselineStatus("BLOCKED", f"commands not executed: {', '.join(blocked)}")
    failed = [item.name for item in command_list if item.exit_code != 0]
    if failed:
        return BaselineStatus("FAIL", f"commands failed: {', '.join(failed)}")
    return BaselineStatus("PASS", "all source baseline commands exited with 0")


def calculate_runtime_status(commands: Iterable[CommandResult]) -> BaselineStatus:
    """按 Runtime 规则计算状态，不使用 DIRTY。"""
    command_list = list(commands)
    blocked = [item.name for item in command_list if not item.executed]
    if blocked:
        return BaselineStatus("BLOCKED", f"commands not executed: {', '.join(blocked)}")
    failed = [item for item in command_list if item.exit_code != 0]
    if failed:
        if any(_looks_like_provider_instability(item) for item in failed):
            return BaselineStatus("UNSTABLE", "provider/network/model instability detected")
        failed_names = ", ".join(item.name for item in failed)
        return BaselineStatus("FAIL", f"runtime evaluation commands failed: {failed_names}")
    return BaselineStatus("PASS", "all runtime baseline commands exited with 0")


def _looks_like_provider_instability(result: CommandResult) -> bool:
    """识别常见外部 provider 或网络不稳定信号。"""
    text = f"{result.stdout}\n{result.stderr}\n{result.error_message or ''}".lower()
    keywords = [
        "provider",
        "deepseek",
        "openai",
        "api",
        "timeout",
        "timed out",
        "network",
        "connection",
        "rate limit",
        "429",
        "401",
        "403",
        "502",
        "503",
        "504",
    ]
    return any(keyword in text for keyword in keywords)


def redact_sensitive_text(text: str) -> str:
    """脱敏命令输出，避免把密钥写入 baseline 快照。"""
    if not text:
        return ""
    patterns = [
        r"(?i)(OPENAI_API_KEY|DEEPSEEK_API_KEY|API_KEY|TOKEN|AUTHORIZATION)\s*=\s*[^\s]+",
        r"(?i)(Authorization:\s*Bearer\s+)[^\s]+",
        r"(?i)(token\s*=\s*)[^\s]+",
        r"sk-[A-Za-z0-9_\-]{8,}",
    ]
    redacted = text
    for pattern in patterns:
        redacted = re.sub(pattern, lambda m: _redact_match(m), redacted)
    return redacted


def _redact_match(match: re.Match[str]) -> str:
    """保留键名，替换敏感值。"""
    if match.lastindex:
        return f"{match.group(1)}[REDACTED]"
    return "[REDACTED]"


def run_command(command: BaselineCommand, cwd: Path, timeout_seconds: int) -> CommandResult:
    """执行命令并捕获 stdout、stderr、exit code。"""
    start = time.perf_counter()
    try:
        result = subprocess.run(
            command.command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return CommandResult(
            name=command.name,
            command=command.command,
            executed=True,
            exit_code=result.returncode,
            stdout=redact_sensitive_text(result.stdout),
            stderr=redact_sensitive_text(result.stderr),
            duration_seconds=round(time.perf_counter() - start, 3),
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            name=command.name,
            command=command.command,
            executed=True,
            exit_code=-1,
            stdout=redact_sensitive_text(exc.stdout or ""),
            stderr=redact_sensitive_text(exc.stderr or ""),
            duration_seconds=round(time.perf_counter() - start, 3),
            error_message=f"command timed out after {timeout_seconds}s",
        )
    except OSError as exc:
        return CommandResult(
            name=command.name,
            command=command.command,
            executed=False,
            exit_code=None,
            duration_seconds=round(time.perf_counter() - start, 3),
            error_message=redact_sensitive_text(str(exc)),
        )


def collect_git_state(cwd: Path) -> GitState:
    """读取 git head 和 porcelain 状态，不解析报告内容。"""
    head = _run_git_text(["git", "rev-parse", "HEAD"], cwd).strip() or None
    status = _run_git_text(["git", "status", "--porcelain"], cwd)
    return GitState(head=head, status_porcelain=status, dirty=bool(status.strip()))


def collect_file_diff(before: GitState, after: GitState, cwd: Path) -> FileDiff:
    """记录前后文件状态和 diff stat。"""
    diff_stat = _run_git_text(["git", "diff", "--stat"], cwd)
    return FileDiff(
        before_status=before.status_porcelain,
        after_status=after.status_porcelain,
        diff_stat=diff_stat,
        summary=_summarize_status_change(before.status_porcelain, after.status_porcelain),
    )


def _run_git_text(command: list[str], cwd: Path) -> str:
    """执行只读 git 命令并返回脱敏文本。"""
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return redact_sensitive_text(result.stdout if result.returncode == 0 else result.stderr)
    except OSError as exc:
        return redact_sensitive_text(str(exc))


def _summarize_status_change(before_status: str, after_status: str) -> dict[str, int]:
    """汇总 after 状态中的新增、修改、删除数量。"""
    _ = before_status
    summary = {"added": 0, "modified": 0, "deleted": 0, "renamed": 0, "untracked": 0}
    for line in after_status.splitlines():
        code = line[:2]
        if code == "??":
            summary["untracked"] += 1
            summary["added"] += 1
        if "M" in code:
            summary["modified"] += 1
        if "D" in code:
            summary["deleted"] += 1
        if "R" in code:
            summary["renamed"] += 1
    return summary


def build_snapshot(
    baseline_type: str,
    status: BaselineStatus,
    commands: list[CommandResult],
    before_git: GitState,
    after_git: GitState,
    file_diff: FileDiff,
    timestamp: str,
    provider: str | None = None,
    model: str | None = None,
) -> dict:
    """构造统一 snapshot schema。"""
    run_id = f"{baseline_type}_{_compact_timestamp(timestamp)}"
    snapshot = {
        "schema_version": "1.0",
        "baseline_type": baseline_type,
        "run_id": run_id,
        "timestamp": timestamp,
        "status": status.status,
        "status_reason": status.reason,
        "project_root": str(PROJECT_ROOT),
        "truth_source": ["stdout", "stderr", "exit_code", "git_status", "git_diff"],
        "forbidden_truth_sources": [
            "harness_report_latest.*",
            "prompt_regression_latest.*",
            "llm_e2e_eval_latest.*",
            "llm_raw_outputs/*",
        ],
        "git": {
            "before_head": before_git.head,
            "after_head": after_git.head,
            "working_tree_dirty_before": before_git.dirty,
            "working_tree_dirty_after": after_git.dirty,
        },
        "commands": [asdict(item) for item in commands],
        "file_diff": asdict(file_diff),
        "boundary": _boundary_for(baseline_type),
    }
    if baseline_type == "runtime_llm":
        snapshot["provider"] = provider
        snapshot["model"] = model
        snapshot["runtime_side_effects_are_not_source_status"] = True
    return snapshot


def _boundary_for(baseline_type: str) -> dict[str, object]:
    """声明当前 baseline 的边界规则。"""
    if baseline_type == "source":
        return {
            "allows_real_llm": False,
            "forbids_prompt_regression_with_real_provider": True,
            "forbids_llm_e2e_eval_with_real_provider": True,
            "mock_only": True,
            "answers": [
                "main 是否稳定",
                "代码是否破坏",
                "SQL 安全链路是否正确",
                "Mock 工程链路是否完整",
            ],
            "checks": [
                "compileall (src+harness+tests)",
                "pytest (全部用例，Mock 模式)",
                "harness (五项安全检查)",
                "mock prompt regression (工程链路验证)",
                "mock E2E eval (Golden Path 验证)",
            ],
        }
    return {
        "allows_real_llm": True,
        "does_not_judge_source_quality": True,
        "answers": ["LLM 是否漂移", "prompt 是否退化", "provider 是否不稳定"],
    }


def _compact_timestamp(timestamp: str) -> str:
    """将 ISO 时间转成文件名友好格式。"""
    return timestamp.replace("-", "").replace(":", "").replace("+00:00", "Z")


def write_snapshot_files(snapshot: dict, base_dir: Path | str = DEFAULT_BASELINE_DIR) -> dict[str, Path]:
    """按双基线目录结构写入 JSON 和 Markdown 快照。"""
    root = Path(base_dir)
    baseline_type = snapshot["baseline_type"]
    if baseline_type == "source":
        subdir = root / "source"
        prefix = "source_baseline"
    elif baseline_type == "runtime_llm":
        subdir = root / "runtime"
        prefix = "runtime_llm_baseline"
    else:
        raise ValueError(f"不支持的 baseline_type: {baseline_type}")

    subdir.mkdir(parents=True, exist_ok=True)
    timestamp = _compact_timestamp(snapshot["timestamp"])
    json_path = subdir / f"{prefix}_{timestamp}.json"
    md_path = subdir / f"{prefix}_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(snapshot), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def render_markdown(snapshot: dict) -> str:
    """渲染人工可读的 baseline Markdown。"""
    title = "Source Baseline" if snapshot["baseline_type"] == "source" else "Runtime LLM Baseline"
    git = snapshot.get("git", {})
    lines = [
        f"# {title}",
        "",
        "## Summary",
        "",
        f"- run_id: `{snapshot['run_id']}`",
        f"- timestamp: `{snapshot['timestamp']}`",
        f"- status: `{snapshot['status']}`",
        f"- status_reason: {snapshot.get('status_reason', '')}",
        f"- before_head: `{git.get('before_head')}`",
        f"- after_head: `{git.get('after_head')}`",
        f"- working_tree_dirty_before: `{git.get('working_tree_dirty_before')}`",
        f"- working_tree_dirty_after: `{git.get('working_tree_dirty_after')}`",
        "",
        "## Commands",
        "",
    ]
    for command in snapshot["commands"]:
        lines.extend([
            f"### {command['name']}",
            f"- command: `{' '.join(command['command'])}`",
            f"- executed: `{command['executed']}`",
            f"- exit_code: `{command['exit_code']}`",
            f"- duration_seconds: `{command['duration_seconds']}`",
        ])
        if command.get("error_message"):
            lines.append(f"- error_message: {command['error_message']}")
        lines.extend(["", "```text", _truncate(command.get("stdout") or command.get("stderr") or ""), "```", ""])

    lines.extend([
        "## File Diff",
        "",
        f"- summary: `{snapshot['file_diff']['summary']}`",
        "",
        "```text",
        _truncate(snapshot.get("file_diff", {}).get("after_status", "")),
        "```",
        "",
    ])
    triage = snapshot.get("failure_triage")
    if triage is not None:
        lines.extend(_render_failure_triage(triage))
    # Step 13: Memory suggestion pipeline 摘要
    pipeline = snapshot.get("memory_suggestion_pipeline")
    if pipeline is not None:
        lines.append(render_pipeline_summary_for_baseline(pipeline))
    lines.extend([
        "## Boundary",
        "",
        "```json",
        json.dumps(snapshot.get("boundary", {}), ensure_ascii=False, indent=2),
        "```",
    ])
    return "\n".join(lines)


def _render_failure_triage(triage: dict) -> list[str]:
    """渲染 Runtime 失败样例分析段落。"""
    lines = [
        "## Failure Triage",
        "",
        f"- total_failed: `{triage.get('total_failed', 0)}`",
        f"- source: `{triage.get('source', '')}`",
    ]
    if triage.get("error"):
        lines.append(f"- error: {triage['error']}")
    lines.append("")
    items = triage.get("items") or []
    if not items:
        lines.append("当前没有失败样例需要归因。")
        lines.append("")
        return lines
    for item in items:
        lines.extend([
            f"### {item.get('case_id')}",
            f"- failure_type: {item.get('failure_type')}",
            f"- root_cause_hint: {item.get('root_cause_hint')}",
            f"- recommended_action: {item.get('recommended_action')}",
            f"- regression_candidate: `{item.get('regression_candidate')}`",
            f"- asset_dependency: `{item.get('asset_dependency')}`",
            "",
        ])
    return lines


def _truncate(text: str, limit: int = 8000) -> str:
    """限制 Markdown 中的长输出长度。"""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


def run_source_baseline(
    cwd: Path = PROJECT_ROOT,
    output_dir: Path | str = DEFAULT_BASELINE_DIR,
    timeout_seconds: int = 300,
    command_runner: Callable[[BaselineCommand, Path, int], CommandResult] = run_command,
) -> dict:
    """运行 Source Baseline 并写入隔离快照。"""
    timestamp = _now_utc()
    before = collect_git_state(cwd)
    commands = [command_runner(command, cwd, timeout_seconds) for command in build_source_commands()]
    after = collect_git_state(cwd)
    file_diff = collect_file_diff(before, after, cwd)
    status = calculate_source_status(before.dirty, commands)
    snapshot = build_snapshot("source", status, commands, before, after, file_diff, timestamp)
    paths = write_snapshot_files(snapshot, output_dir)
    snapshot["snapshot_paths"] = {key: str(value) for key, value in paths.items()}
    return snapshot


def run_runtime_baseline(
    provider: str = "deepseek",
    model: str | None = None,
    cwd: Path = PROJECT_ROOT,
    output_dir: Path | str = DEFAULT_BASELINE_DIR,
    timeout_seconds: int = 600,
    command_runner: Callable[[BaselineCommand, Path, int], CommandResult] = run_command,
) -> dict:
    """运行 Runtime LLM Baseline 并写入隔离快照。"""
    timestamp = _now_utc()
    before = collect_git_state(cwd)
    commands = [
        command_runner(command, cwd, timeout_seconds)
        for command in build_runtime_commands(provider=provider, model=model)
    ]
    after = collect_git_state(cwd)
    file_diff = collect_file_diff(before, after, cwd)
    status = calculate_runtime_status(commands)
    snapshot = build_snapshot(
        "runtime_llm",
        status,
        commands,
        before,
        after,
        file_diff,
        timestamp,
        provider=provider,
        model=model,
    )
    snapshot["failure_triage"] = load_failure_triage_from_report(
        cwd / "harness/reports/llm_e2e_eval_latest.json"
    )

    # ── Step 13: 自动生成 memory suggestion + review 报告 ──
    # 只在存在 failed cases 时触发；zero failure 时不生成空报告
    # 管道失败不吞掉原始 baseline failure
    triage = snapshot["failure_triage"]
    if triage.get("total_failed", 0) > 0:
        try:
            pipeline_result = run_pipeline_on_failure_triage(
                triage,
                output_root=output_dir,
            )
            snapshot["memory_suggestion_pipeline"] = pipeline_result
        except Exception:
            # 管道失败作为 warning 记录，不替代原始 baseline failure
            snapshot["memory_suggestion_pipeline"] = {
                "generated": False,
                "failed_cases": triage.get("total_failed", 0),
                "suggestions_report": None,
                "review_report": None,
                "warnings": ["pipeline 调用异常"],
                "summary": "Memory suggestion pipeline 异常，原始 baseline 结论不受影响",
                "error": "pipeline exception",
            }

    paths = write_snapshot_files(snapshot, output_dir)
    snapshot["snapshot_paths"] = {key: str(value) for key, value in paths.items()}
    return snapshot


def write_combined_index(snapshots: list[dict], output_dir: Path | str = DEFAULT_BASELINE_DIR) -> Path:
    """写入只引用两个独立快照的索引，不合并结论。"""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    index = {
        "schema_version": "1.0",
        "timestamp": _now_utc(),
        "principle": "Source = 代码是否正确；Runtime = AI 是否稳定；两者不合并为单一结论。",
        "snapshots": [
            {
                "baseline_type": item["baseline_type"],
                "run_id": item["run_id"],
                "status": item["status"],
                "status_reason": item["status_reason"],
                "snapshot_paths": item.get("snapshot_paths", {}),
            }
            for item in snapshots
        ],
    }
    path = root / f"dual_baseline_index_{_compact_timestamp(index['timestamp'])}.json"
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _now_utc() -> str:
    """返回 UTC ISO 时间。"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="TianShu Dual Baseline Freeze")
    parser.add_argument("--mode", choices=["source", "runtime", "all"], default="source")
    parser.add_argument("--provider", choices=["deepseek", "openai"], default="deepseek")
    parser.add_argument("--model", default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_BASELINE_DIR))
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args(argv)

    snapshots: list[dict] = []
    if args.mode in ("source", "all"):
        source = run_source_baseline(output_dir=args.output_dir, timeout_seconds=args.timeout)
        snapshots.append(source)
        print(f"[SOURCE] status={source['status']} json={source['snapshot_paths']['json']}")
    if args.mode in ("runtime", "all"):
        runtime = run_runtime_baseline(
            provider=args.provider,
            model=args.model,
            output_dir=args.output_dir,
            timeout_seconds=args.timeout,
        )
        snapshots.append(runtime)
        print(f"[RUNTIME] status={runtime['status']} json={runtime['snapshot_paths']['json']}")
        # Step 13: 输出 memory suggestion pipeline 摘要
        pipeline = runtime.get("memory_suggestion_pipeline")
        if pipeline is not None:
            if pipeline.get("generated"):
                print(f"  [MEMORY SUGGESTION] generated={pipeline['generated']} failed_cases={pipeline.get('failed_cases', 0)}")
                sr = pipeline.get("suggestions_report", {}) or {}
                rr = pipeline.get("review_report", {}) or {}
                if sr.get("json"):
                    print(f"    suggestions: {sr['json']}")
                if rr.get("json"):
                    print(f"    review: {rr['json']}")
                for warning in pipeline.get("warnings", []):
                    print(f"    warning: {warning}")
            else:
                print(f"  [MEMORY SUGGESTION] skipped: {pipeline.get('summary', 'no failed cases')}")
    if args.mode == "all":
        index_path = write_combined_index(snapshots, args.output_dir)
        print(f"[INDEX] {index_path}")

    if any(item["status"] in ("FAIL", "BLOCKED", "DIRTY", "UNSTABLE") for item in snapshots):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
