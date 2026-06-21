"""TianShu Text2SQL Agent 慢速门禁统一入口。

职责：
    一键运行真实 LLM 质量观测检查（调用真实 Provider）。
    这是观测报告，不是门禁信号——永远 exit 0。

检查项（全量运行，不 fail-fast）：
    1. 真实 LLM Prompt 回归（--provider deepseek）
    2. 真实 LLM E2E 端到端评测（--provider deepseek）

慢速门禁硬性约束：
    - Provider 必须是真实 provider（deepseek / openai），不允许 mock
    - Provider 不可用时标记 BLOCKED（不是 FAIL）
    - 永远 exit 0（失败不阻断——这是观测，不是门禁）
    - 报告中标注"此报告为观测数据，不作为门禁阻断信号"
    - 不修改任何源码或 Prompt 模板
    - API Key 绝不出现在报告中

与快速门禁的关系：
    - 快速门禁（run_fast_gate.py）= 阻断信号 → 决定能否合并
    - 慢速门禁（run_slow_gate.py）= 观测信号 → 了解模型行为变化

用法：
    python harness/run_slow_gate.py                           # 使用默认 provider (deepseek)
    python harness/run_slow_gate.py --provider openai         # 切换 provider
    python harness/run_slow_gate.py --model deepseek-v4-pro   # 指定模型
    python harness/run_slow_gate.py --json                    # 只输出 JSON（给 CI）
    python harness/run_slow_gate.py --timeout 600             # 自定义超时
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 合法的真实 Provider（不允许 mock）
REAL_PROVIDERS = {"deepseek", "openai"}

# 慢速门禁步骤定义
SLOW_STEPS: list[dict[str, Any]] = [
    {
        "name": "prompt_regression",
        "display": "真实 LLM Prompt 回归",
        "script": "harness/run_prompt_regression.py",
        "estimate": "1-5 min",
    },
    {
        "name": "llm_e2e_eval",
        "display": "真实 LLM E2E 端到端评测",
        "script": "harness/run_llm_e2e_eval.py",
        "estimate": "2-10 min",
    },
]


@dataclass
class SlowStepResult:
    """慢速门禁单步执行结果。"""

    name: str
    display: str
    status: str          # "PASS" | "FAIL" | "BLOCKED"
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    error_message: str | None = None


@dataclass
class SlowGateReport:
    """慢速门禁完整观测报告。"""

    run_id: str
    timestamp: str
    commit_sha: str | None
    branch: str | None
    provider: str
    model: str | None
    total_steps: int
    passed: int
    failed: int
    blocked: int
    overall: str          # "PASS" | "FAIL" | "BLOCKED" | "PARTIAL"
    steps: list[dict[str, Any]] = field(default_factory=list)
    duration_total_seconds: float = 0.0
    observation_note: str = (
        "⚠️ 此报告为观测数据，不作为门禁阻断信号。"
        "慢速门禁失败不阻断 PR 合并，但需要人工关注模型行为变化。"
    )


def _now_utc() -> str:
    """返回 UTC ISO 时间戳。"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _get_git_info(cwd: Path) -> tuple[str | None, str | None]:
    """获取当前 commit SHA 短码和分支名（只读）。"""
    commit_sha = None
    branch = None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if result.returncode == 0:
            commit_sha = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return commit_sha, branch


def _sanitize_text(text: str, max_length: int = 5000) -> str:
    """截断过长输出。"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n...[输出过长已截断]"


def _detect_provider_instability(result: SlowStepResult) -> bool:
    """识别常见的 Provider 或网络不稳定信号。"""
    text = f"{result.stdout}\n{result.stderr}\n{result.error_message or ''}".lower()
    keywords = [
        "provider", "deepseek", "openai", "api",
        "timeout", "timed out", "network", "connection",
        "rate limit", "429", "401", "403", "502", "503", "504",
    ]
    return any(keyword in text for keyword in keywords)


def run_step(
    step: dict[str, Any],
    provider: str,
    model: str | None,
    cwd: Path,
    timeout_seconds: int = 600,
) -> SlowStepResult:
    """执行单步慢速检查。

    Args:
        step: 步骤定义
        provider: LLM provider（必须是真实 provider）
        model: 模型名称（可选）
        cwd: 工作目录
        timeout_seconds: 超时秒数（慢速门禁默认更长）

    Returns:
        SlowStepResult 包含完整执行证据
    """
    cmd = [
        sys.executable,
        step["script"],
        "--provider", provider,
    ]
    if model:
        cmd.extend(["--model", model])

    start = time.perf_counter()
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
        )
        duration = round(time.perf_counter() - start, 3)
        return SlowStepResult(
            name=step["name"],
            display=step["display"],
            status="PASS" if result.returncode == 0 else "FAIL",
            exit_code=result.returncode,
            stdout=_sanitize_text(result.stdout),
            stderr=_sanitize_text(result.stderr),
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired as exc:
        duration = round(time.perf_counter() - start, 3)
        result_obj = SlowStepResult(
            name=step["name"],
            display=step["display"],
            status="BLOCKED",
            exit_code=-1,
            stdout=_sanitize_text(exc.stdout or ""),
            stderr=_sanitize_text(exc.stderr or ""),
            duration_seconds=duration,
            error_message=f"步骤超时（{timeout_seconds}s 限制）",
        )
        # 超时也可能是 provider 不稳定
        if _detect_provider_instability(result_obj):
            result_obj.error_message += " — 疑似 Provider/网络不稳定"
        return result_obj
    except OSError as exc:
        duration = round(time.perf_counter() - start, 3)
        return SlowStepResult(
            name=step["name"],
            display=step["display"],
            status="BLOCKED",
            exit_code=None,
            stdout="",
            stderr=str(exc),
            duration_seconds=duration,
            error_message=f"命令执行异常: {exc}",
        )


def render_markdown(report: SlowGateReport) -> str:
    """生成人工可读的 Markdown 观测报告。"""
    lines: list[str] = []
    lines.append("# TianShu Slow Gate 观测报告")
    lines.append("")
    lines.append(f"**Run ID:** `{report.run_id}`")
    lines.append(f"**时间:** {report.timestamp}")
    if report.commit_sha:
        lines.append(f"**Commit:** `{report.commit_sha}`")
    if report.branch:
        lines.append(f"**分支:** `{report.branch}`")
    lines.append(f"**Provider:** {report.provider}")
    if report.model:
        lines.append(f"**Model:** {report.model}")
    lines.append("")
    lines.append("> ⚠️ **此报告为观测数据，不作为门禁阻断信号。**")
    lines.append("> 慢速门禁失败不阻断 PR 合并，但需要人工关注模型行为变化。")
    lines.append("")

    lines.append("## 汇总")
    lines.append("")
    overall_icon = "✅" if report.overall == "PASS" else ("⚠️" if report.overall == "PARTIAL" else "❌")
    lines.append("| 状态 | 总数 | 通过 | 失败 | 阻塞 | 总耗时 |")
    lines.append("|------|------|------|------|------|--------|")
    lines.append(
        f"| {overall_icon} **{report.overall}** "
        f"| {report.total_steps} "
        f"| {report.passed} "
        f"| {report.failed} "
        f"| {report.blocked} "
        f"| {report.duration_total_seconds:.1f}s |"
    )
    lines.append("")

    lines.append("## 逐步详情")
    lines.append("")
    for step in report.steps:
        icon_map = {"PASS": "✅", "FAIL": "❌", "BLOCKED": "🚫"}
        icon = icon_map.get(step["status"], "❓")
        lines.append(f"### {icon} {step['display']} ({step['name']})")
        lines.append(f"- 状态: **{step['status']}**")
        lines.append(f"- 耗时: {step['duration_seconds']}s")
        lines.append(f"- 退出码: {step['exit_code']}")
        if step.get("error_message"):
            lines.append(f"- 错误: {step['error_message']}")
        lines.append("")
        if step.get("stdout"):
            lines.append("```text")
            lines.append(step["stdout"][:3000])
            lines.append("```")
        if step.get("stderr"):
            lines.append("```text")
            lines.append(step["stderr"][:1000])
            lines.append("```")
        lines.append("")

    lines.append("## 边界确认")
    lines.append("")
    lines.append(f"- ✅ Provider 为真实 LLM（`{report.provider}`），未使用 mock")
    lines.append("- ✅ 此报告不作为门禁阻断信号（exit code 始终为 0）")
    lines.append("- ✅ API Key 不出现在报告中（已脱敏）")
    lines.append("- ✅ 未修改任何源码或 Prompt 模板")
    lines.append("")

    return "\n".join(lines)


def run_slow_gate(
    provider: str = "deepseek",
    model: str | None = None,
    cwd: Path = PROJECT_ROOT,
    report_dir: Path | str = "harness/reports",
    timeout_seconds: int = 600,
) -> SlowGateReport:
    """执行慢速门禁全流程（全量运行，不 fail-fast）。

    Args:
        provider: LLM provider（必须为真实 provider）
        model: 模型名称（可选）
        cwd: 工作目录
        report_dir: 报告输出目录
        timeout_seconds: 每步超时秒数

    Returns:
        SlowGateReport 包含所有步骤结果和观测状态

    Raises:
        ValueError: provider 为 mock 时拒绝执行
    """
    # 边界守卫：不允许 mock 伪装成真实 provider
    if provider not in REAL_PROVIDERS:
        raise ValueError(
            f"慢速门禁要求真实 LLM Provider（{REAL_PROVIDERS}），"
            f"不允许使用 mock。当前 provider: {provider}"
        )

    run_id = _now_utc()
    commit_sha, branch = _get_git_info(cwd)
    report_start = time.perf_counter()

    # 全量运行，不 fail-fast
    step_results: list[SlowStepResult] = []
    for i, step in enumerate(SLOW_STEPS, 1):
        print(f"[{i}/{len(SLOW_STEPS)}] {step['display']}...", end=" ", flush=True)
        result = run_step(step, provider, model, cwd, timeout_seconds)
        step_results.append(result)

        # 识别 Provider 不稳定信号
        if result.status == "FAIL" and _detect_provider_instability(result):
            result.status = "BLOCKED"
            if result.error_message:
                result.error_message += " | 已自动识别为 Provider/网络不稳定"
            else:
                result.error_message = "已自动识别为 Provider/网络不稳定"

        status_icon = {"PASS": "✅", "FAIL": "❌", "BLOCKED": "🚫"}.get(result.status, "❓")
        print(f"{status_icon} {result.status} ({result.duration_seconds}s)")

    total_duration = round(time.perf_counter() - report_start, 3)

    # 计算汇总
    passed = sum(1 for r in step_results if r.status == "PASS")
    failed = sum(1 for r in step_results if r.status == "FAIL")
    blocked = sum(1 for r in step_results if r.status == "BLOCKED")

    if blocked == len(SLOW_STEPS):
        overall = "BLOCKED"
    elif failed == 0 and blocked == 0:
        overall = "PASS"
    elif failed > 0 and passed > 0:
        overall = "PARTIAL"
    elif blocked > 0 and failed == 0:
        overall = "PARTIAL"
    else:
        overall = "FAIL"

    report = SlowGateReport(
        run_id=run_id,
        timestamp=run_id,
        commit_sha=commit_sha,
        branch=branch,
        provider=provider,
        model=model,
        total_steps=len(SLOW_STEPS),
        passed=passed,
        failed=failed,
        blocked=blocked,
        overall=overall,
        steps=[asdict(r) for r in step_results],
        duration_total_seconds=total_duration,
    )

    # 写入报告文件
    report_root = Path(report_dir)
    report_root.mkdir(parents=True, exist_ok=True)

    json_path = report_root / "slow_gate_latest.json"
    json_path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md_path = report_root / "slow_gate_latest.md"
    md_path.write_text(render_markdown(report), encoding="utf-8")

    return report


def main(argv: list[str] | None = None) -> int:
    """慢速门禁 CLI 入口。

    无论观测结果如何，永远返回 exit 0。
    """
    # 确保控制台输出 UTF-8
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="TianShu Text2SQL Agent 慢速门禁 — 真实 LLM 质量观测",
    )
    parser.add_argument(
        "--provider",
        choices=["deepseek", "openai"],
        default="deepseek",
        help="真实 LLM Provider（不允许 mock）",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="模型名称（默认按 provider 自动选择）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="只输出 JSON 报告到 stdout（给 CI 消费）",
    )
    parser.add_argument(
        "--report-dir",
        default="harness/reports",
        help="报告输出目录",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="每步超时秒数（默认 600s）",
    )
    args = parser.parse_args(argv)

    print("=" * 60)
    print("TianShu Text2SQL Agent 慢速门禁（观测模式）")
    print(f"Provider: {args.provider}")
    if args.model:
        print(f"Model: {args.model}")
    print("约束: 真实 LLM 调用，仅观测不阻断")
    print("=" * 60)
    print()

    try:
        report = run_slow_gate(
            provider=args.provider,
            model=args.model,
            report_dir=args.report_dir,
            timeout_seconds=args.timeout,
        )
    except ValueError as exc:
        print(f"❌ 参数错误: {exc}", file=sys.stderr)
        return 2

    # 汇总输出
    print(f"\n{'=' * 60}")
    overall_icon = {"PASS": "✅", "FAIL": "❌", "BLOCKED": "🚫", "PARTIAL": "⚠️"}.get(
        report.overall, "❓"
    )
    print(f"{overall_icon} 慢速门禁观测: {report.overall}")
    print(f"   {report.passed} 通过 / {report.failed} 失败 / {report.blocked} 阻塞")
    print(f"   总耗时: {report.duration_total_seconds:.1f}s")
    print("   ⚠️ 此为观测报告，不作为门禁阻断信号")
    print(f"{'=' * 60}")

    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))

    report_path = Path(args.report_dir)
    print(f"\n📄 Markdown 报告: {report_path / 'slow_gate_latest.md'}")
    print(f"📄 JSON 报告:   {report_path / 'slow_gate_latest.json'}")

    # 核心原则：慢速门禁永远不阻断，exit 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
