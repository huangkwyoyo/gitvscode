"""TianShu Text2SQL Agent 快速门禁统一入口。

职责：
    一键运行所有离线质量检查（不调用任何 LLM）。
    全部通过 → exit 0（允许 commit / 允许合并）
    任一项失败 → exit 1（阻断）

检查顺序（fail-fast，第一项失败立即中断）：
    1. compileall  — 代码编译检查
    2. pytest      — 单元测试套件
    3. harness     — 六项安全检查（含 Memory Gate）+ 五项观察期检查
    4. mock 回归   — Mock Prompt Regression
    5. mock E2E    — Mock E2E Eval

观察期检查（warn-only）：
    以下 5 个安全检查处于观察期，发现问题仅警告，不阻断 fast gate：
    - check_plan_executor_safety.py       (PlanExecutor 安全链路)
    - check_execution_strategy_safety.py  (执行策略串行/隔离)
    - check_result_fusion_safety.py       (LLM 融合 SQL/因果/编造检测)
    - check_cross_domain_policy.py        (隐私保护/因果禁止/跨域降级)
    - check_chart_spec_safety.py          (HTML/JS/LLM/DuckDB 禁止)

    观察期结束后，经连续稳定运行验证，可升级为 error 模式（阻断）。

快速门禁硬性约束：
    - 所有步骤使用 --provider mock，不接受 CLI 覆盖
    - 不调用任何真实 LLM
    - 不读取 latest 报告作为判断依据（只依赖 exit code）
    - 不修改任何源码或 Prompt 模板

用法：
    python harness/run_fast_gate.py               # 全部 5 项
    python harness/run_fast_gate.py --skip-mock   # 只跑前三项（编译+测试+安全）
    python harness/run_fast_gate.py --json        # 只输出 JSON（给 CI）
    python harness/run_fast_gate.py --step 3      # 只跑第 3 步（harness）
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ═══════════════════════════════════════════════════════════════════════════════
# 观察期检查配置（warn-only）
# ═══════════════════════════════════════════════════════════════════════════════
# 这些检查处于观察期（observation mode），在 run_harness.py STEPS 中的索引（1-based）
# 发现问题时打印 WARNING，不阻断 fast gate。
# 仅基础设施错误（脚本不存在、Python 语法错误、超时）会导致失败。
#
# 索引对应关系（run_harness.py STEPS）：
#   7 = check_execution_strategy_safety.py  (执行策略安全门禁)
#   8 = check_result_fusion_safety.py       (LLM 融合安全门禁)
#   9 = check_cross_domain_policy.py        (跨域策略安全门禁)
#  10 = check_chart_spec_safety.py          (图表规格安全门禁)
#  11 = check_plan_executor_safety.py       (PlanExecutor 安全门禁)
#
# 升级条件（全部满足后可将对应索引移出此列表）：
#   1. 连续 30 天无规则误报
#   2. 所有 warn 触达率 > 90%（该 warn 的规则确有对应业务代码变更）
#   3. 团队确认接受该检查的阻断语义
#   4. pre-commit 接入是最后一步，不在观察期内完成
WARN_ONLY_CHECK_INDICES: list[int] = [7, 8, 9, 10, 11]

# 观察期检查对应的脚本路径（文档用，与上方索引一一对应）
WARN_ONLY_CHECKS: list[str] = [
    "harness/checks/check_execution_strategy_safety.py",
    "harness/checks/check_result_fusion_safety.py",
    "harness/checks/check_cross_domain_policy.py",
    "harness/checks/check_chart_spec_safety.py",
    "harness/checks/check_plan_executor_safety.py",
]
# ═══════════════════════════════════════════════════════════════════════════════

# 快速门禁步骤定义（按执行顺序）
# 格式: (步骤名称, 命令列表, 预期耗时估计)
STEPS: list[dict[str, Any]] = [
    {
        "name": "compileall",
        "display": "代码编译检查",
        "command": [sys.executable, "-m", "compileall", "-q", "src", "harness", "tests"],
        "estimate": "< 5s",
    },
    {
        "name": "pytest",
        "display": "单元测试 (Mock)",
        "command": [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--basetemp",
            "harness/reports/test_tmp/pytest_fast_gate",
        ],
        "estimate": "< 30s",
    },
    {
        "name": "harness",
        "display": "Harness 安全检查（6 项阻断 + 5 项观察期）",
        "command": [
            sys.executable,
            "harness/run_harness.py",
            "--warn-steps",
            ",".join(str(i) for i in WARN_ONLY_CHECK_INDICES),
            "--json-summary",
        ],
        "estimate": "< 15s",
    },
    {
        "name": "mock_prompt_regression",
        "display": "Mock Prompt 回归",
        "command": [
            sys.executable,
            "harness/run_prompt_regression.py",
            "--provider", "mock",
        ],
        "estimate": "< 5s",
    },
    {
        "name": "mock_e2e_eval",
        "display": "Mock E2E 端到端评测",
        "command": [
            sys.executable,
            "harness/run_llm_e2e_eval.py",
            "--provider", "mock",
        ],
        "estimate": "< 10s",
    },
]

# 前三项为核心检查（不含 mock 回归）
CORE_STEP_COUNT = 3
TOTAL_STEP_COUNT = len(STEPS)


@dataclass
class StepResult:
    """单步检查的执行结果。"""

    name: str
    display: str
    status: str          # "PASS" | "WARN" | "FAIL" | "SKIPPED"
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    error_message: str | None = None
    # 仅 harness 步骤携带的子检查统计
    harness_summary: dict[str, int] | None = None


@dataclass
class FastGateReport:
    """快速门禁完整报告。"""

    run_id: str
    timestamp: str
    commit_sha: str | None
    branch: str | None
    total_steps: int
    passed: int
    failed: int
    skipped: int
    warned: int = 0
    overall: str = ""     # "PASS" | "FAIL"
    steps: list[dict[str, Any]] = field(default_factory=list)
    duration_total_seconds: float = 0.0
    # 观察期检查统计
    warn_checks_passed: int = 0
    warn_checks_warned: int = 0
    warn_checks_infra_fail: int = 0


def _now_utc() -> str:
    """返回 UTC ISO 时间戳。"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _get_git_info(cwd: Path) -> tuple[str | None, str | None]:
    """获取当前 commit SHA 短码和分支名（只读，不修改任何文件）。"""
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
    """截断过长输出，防止报告膨胀。"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n...[输出过长已截断]"


def _parse_harness_json_summary(stdout: str) -> dict[str, int] | None:
    """从 harness stdout 中解析 JSON 摘要行。

    格式: __HARNESS_JSON_SUMMARY__ {"blocking_pass": 6, ...}

    Returns:
        解析成功返回 dict，失败返回 None
    """
    match = re.search(r'__HARNESS_JSON_SUMMARY__\s*(\{.*\})', stdout)
    if not match:
        return None
    try:
        summary = json.loads(match.group(1))
        # 确保所有期望的键都是整数
        expected_keys = [
            "blocking_pass", "blocking_fail",
            "warn_pass", "warn_warn", "warn_infra_fail",
            "total_pass", "total_warn", "total_fail", "total_steps",
        ]
        return {k: int(summary.get(k, 0)) for k in expected_keys}
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def run_step(step: dict[str, Any], cwd: Path, timeout_seconds: int = 120) -> StepResult:
    """执行单步检查并捕获完整输出证据。

    Args:
        step: 步骤定义（name, display, command）
        cwd: 工作目录（项目根目录）
        timeout_seconds: 超时秒数

    Returns:
        StepResult 包含 exit_code、stdout、stderr、耗时和错误信息
    """
    cmd = step["command"]
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
        return StepResult(
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
        return StepResult(
            name=step["name"],
            display=step["display"],
            status="FAIL",
            exit_code=-1,
            stdout=_sanitize_text(exc.stdout or ""),
            stderr=_sanitize_text(exc.stderr or ""),
            duration_seconds=duration,
            error_message=f"步骤超时（{timeout_seconds}s 限制）",
        )
    except OSError as exc:
        duration = round(time.perf_counter() - start, 3)
        return StepResult(
            name=step["name"],
            display=step["display"],
            status="FAIL",
            exit_code=None,
            stdout="",
            stderr=str(exc),
            duration_seconds=duration,
            error_message=f"命令执行异常: {exc}",
        )


def render_markdown(report: FastGateReport) -> str:
    """生成人工可读的 Markdown 报告。"""
    lines: list[str] = []
    lines.append("# TianShu Fast Gate 报告")
    lines.append("")
    lines.append(f"**Run ID:** `{report.run_id}`")
    lines.append(f"**时间:** {report.timestamp}")
    if report.commit_sha:
        lines.append(f"**Commit:** `{report.commit_sha}`")
    if report.branch:
        lines.append(f"**分支:** `{report.branch}`")
    lines.append("")
    lines.append("## 汇总")
    lines.append("")
    overall_icon = "✅" if report.overall == "PASS" else "❌"
    lines.append(f"| 状态 | 总数 | 通过 | 失败 | 跳过 | 警告 | 总耗时 |")
    lines.append(f"|------|------|------|------|------|------|--------|")
    lines.append(
        f"| {overall_icon} **{report.overall}** "
        f"| {report.total_steps} "
        f"| {report.passed} "
        f"| {report.failed} "
        f"| {report.skipped} "
        f"| {report.warned} "
        f"| {report.duration_total_seconds:.1f}s |"
    )
    lines.append("")

    # 观察期检查统计
    if WARN_ONLY_CHECK_INDICES:
        lines.append("### 观察期检查（warn-only）")
        lines.append("")
        lines.append(f"| 指标 | 数量 |")
        lines.append(f"|------|------|")
        lines.append(f"| 通过 | {report.warn_checks_passed} |")
        lines.append(f"| 警告 | {report.warn_checks_warned} |")
        lines.append(f"| 基础设施失败 | {report.warn_checks_infra_fail} |")
        lines.append("")
        lines.append("> ⚠️ 这些检查处于**观察期**，发现问题仅警告不阻断。")
        lines.append("> 连续稳定运行后可升级为 error 模式。")
        lines.append("")

    lines.append("## 逐步详情")
    lines.append("")
    for step in report.steps:
        status = step["status"]
        if status == "PASS":
            icon = "✅"
        elif status == "WARN":
            icon = "⚠️"
        elif status == "SKIPPED":
            icon = "⏭️"
        else:
            icon = "❌"
        lines.append(f"### {icon} {step['display']} ({step['name']})")
        lines.append(f"- 状态: **{step['status']}**")
        lines.append(f"- 耗时: {step['duration_seconds']}s")
        lines.append(f"- 退出码: {step['exit_code']}")
        if step.get("error_message"):
            lines.append(f"- 错误: {step['error_message']}")
        # 观察期子检查统计
        hs = step.get("harness_summary")
        if hs:
            lines.append(f"- 阻断检查: {hs.get('blocking_pass', 0)} 通过 / {hs.get('blocking_fail', 0)} 失败")
            lines.append(f"- 观察期检查: {hs.get('warn_pass', 0)} 通过 / {hs.get('warn_warn', 0)} 警告 / {hs.get('warn_infra_fail', 0)} 基础设施失败")
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
    lines.append("- ✅ 所有步骤使用 `--provider mock`（未调用真实 LLM）")
    lines.append("- ✅ 判断依据仅来自 stdout / stderr / exit code")
    lines.append("- ✅ 未读取 `*_latest.*` 报告作为 truth source")
    lines.append("- ✅ 未修改任何源码或 Prompt 模板")
    if WARN_ONLY_CHECK_INDICES:
        lines.append(f"- ⚠️ {len(WARN_ONLY_CHECK_INDICES)} 项安全检查处于观察期（warn-only），不阻断")
    lines.append("")
    return "\n".join(lines)


def run_fast_gate(
    skip_mock: bool = False,
    only_step: int | None = None,
    cwd: Path = PROJECT_ROOT,
    report_dir: Path | str = "harness/reports",
) -> FastGateReport:
    """执行快速门禁全流程。

    Args:
        skip_mock: 跳过 mock 回归和 mock E2E 步骤（只跑核心 3 项）
        only_step: 只跑指定步骤（1-based 索引）
        cwd: 工作目录
        report_dir: 报告输出目录

    Returns:
        FastGateReport 包含所有步骤结果和整体判定
    """
    run_id = _now_utc()
    commit_sha, branch = _get_git_info(cwd)
    report_start = time.perf_counter()

    # 确定要运行的步骤
    if only_step is not None:
        if 1 <= only_step <= TOTAL_STEP_COUNT:
            steps_to_run = [STEPS[only_step - 1]]
        else:
            raise ValueError(f"步骤编号超出范围 (1-{TOTAL_STEP_COUNT}): {only_step}")
    elif skip_mock:
        steps_to_run = STEPS[:CORE_STEP_COUNT]
    else:
        steps_to_run = list(STEPS)

    # 执行步骤（fail-fast 模式）
    step_results: list[StepResult] = []
    harness_summary: dict[str, int] | None = None
    for i, step in enumerate(steps_to_run, 1):
        print(f"[{i}/{len(steps_to_run)}] {step['display']}...", end=" ", flush=True)
        result = run_step(step, cwd)
        step_results.append(result)

        # 解析 harness 步骤的 JSON 摘要
        if step["name"] == "harness":
            parsed = _parse_harness_json_summary(result.stdout)
            if parsed:
                harness_summary = parsed
                result.harness_summary = parsed

        print(f"{result.status} ({result.duration_seconds}s)")

        # fail-fast：任一步骤失败立即中断后续步骤
        # WARN 状态不触发 fail-fast（仅 FAIL 触发）
        if result.status == "FAIL":
            remaining = steps_to_run[i:]  # 尚未执行的步骤
            for skipped in remaining:
                skipped_result = StepResult(
                    name=skipped["name"],
                    display=skipped["display"],
                    status="SKIPPED",
                    exit_code=None,
                    stdout="",
                    stderr="",
                    duration_seconds=0.0,
                    error_message="前序步骤失败，跳过执行",
                )
                step_results.append(skipped_result)
                print(f"  ⏭️ {skipped['display']} (前序步骤失败，跳过)")
            break

    total_duration = round(time.perf_counter() - report_start, 3)

    # 计算汇总
    passed = sum(1 for r in step_results if r.status == "PASS")
    warned = sum(1 for r in step_results if r.status == "WARN")
    failed = sum(1 for r in step_results if r.status == "FAIL")
    skipped = sum(1 for r in step_results if r.status == "SKIPPED")
    overall = "PASS" if failed == 0 else "FAIL"

    # 观察期检查统计
    warn_checks_passed = harness_summary.get("warn_pass", 0) if harness_summary else 0
    warn_checks_warned = harness_summary.get("warn_warn", 0) if harness_summary else 0
    warn_checks_infra_fail = harness_summary.get("warn_infra_fail", 0) if harness_summary else 0

    report = FastGateReport(
        run_id=run_id,
        timestamp=run_id,
        commit_sha=commit_sha,
        branch=branch,
        total_steps=len(step_results),
        passed=passed,
        failed=failed,
        skipped=skipped,
        warned=warned,
        overall=overall,
        steps=[asdict(r) for r in step_results],
        duration_total_seconds=total_duration,
        warn_checks_passed=warn_checks_passed,
        warn_checks_warned=warn_checks_warned,
        warn_checks_infra_fail=warn_checks_infra_fail,
    )

    # 写入报告文件
    report_root = Path(report_dir)
    report_root.mkdir(parents=True, exist_ok=True)

    json_path = report_root / "fast_gate_latest.json"
    json_path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md_path = report_root / "fast_gate_latest.md"
    md_path.write_text(render_markdown(report), encoding="utf-8")

    return report


def main(argv: list[str] | None = None) -> int:
    """快速门禁 CLI 入口。"""
    # 确保控制台输出 UTF-8
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="TianShu Text2SQL Agent 快速门禁 — 离线质量检查一键运行",
    )
    parser.add_argument(
        "--skip-mock",
        action="store_true",
        help="跳过 mock 回归和 mock E2E 步骤（只跑 compileall + pytest + harness）",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=None,
        metavar="N",
        help=f"只运行指定步骤（1-{TOTAL_STEP_COUNT}）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="只输出 JSON 报告到 stdout（给 CI 消费）",
    )
    parser.add_argument(
        "--report-dir",
        default="harness/reports",
        help="报告输出目录（默认 harness/reports）",
    )
    args = parser.parse_args(argv)

    print("=" * 60)
    print("TianShu Text2SQL Agent 快速门禁")
    if args.skip_mock:
        print(f"模式: 核心检查 ({CORE_STEP_COUNT} 项)")
    elif args.step:
        print(f"模式: 单步 (第 {args.step} 步)")
    else:
        print(f"模式: 完整检查 ({TOTAL_STEP_COUNT} 项)")
    print(f"约束: 纯离线，不调用任何 LLM")
    print("=" * 60)
    print()

    try:
        report = run_fast_gate(
            skip_mock=args.skip_mock,
            only_step=args.step,
            report_dir=args.report_dir,
        )
    except ValueError as exc:
        print(f"❌ 参数错误: {exc}", file=sys.stderr)
        return 2

    # 汇总输出
    print(f"\n{'=' * 60}")
    overall_icon = "✅" if report.overall == "PASS" else "❌"
    print(f"{overall_icon} 快速门禁: {report.overall}")
    print(f"   阻断检查: {report.passed} 通过 / {report.failed} 失败"
          + (f" / {report.skipped} 跳过" if report.skipped else ""))
    # 观察期检查统计
    if WARN_ONLY_CHECK_INDICES:
        print(f"   观察期检查: {report.warn_checks_passed} 通过 / {report.warn_checks_warned} 警告"
              + (f" / {report.warn_checks_infra_fail} 基础设施失败" if report.warn_checks_infra_fail else ""))
    if report.warned:
        print(f"   {report.warned} 个顶级步骤存在警告")
    print(f"   总耗时: {report.duration_total_seconds:.1f}s")
    if WARN_ONLY_CHECK_INDICES:
        print(f"")
        print(f"   ⚠️ {len(WARN_ONLY_CHECK_INDICES)} 项安全检查处于观察期（warn-only），不阻断")
    print(f"{'=' * 60}")

    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))

    report_path = Path(args.report_dir)
    print(f"\n📄 Markdown 报告: {report_path / 'fast_gate_latest.md'}")
    print(f"📄 JSON 报告:   {report_path / 'fast_gate_latest.json'}")

    return 0 if report.overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
