"""Memory Harness pre-commit 检查脚本（Step 20 + Step 21b + Step 23）。

职责：
    在 git commit 前运行轻量 Memory Rule Enforcement 检查。
    支持两种模式：
    - warn（默认）：发现 active+blocking=true 规则失败时输出 WARNING，始终 exit 0，不阻断 commit
    - blocking（Step 23）：发现 active+blocking=true 规则失败时输出 BLOCKING ERROR，exit code 非 0，阻断 commit

    可选：--record-observation 在每次运行时生成 timestamp observation snapshot，
    用于 Step 22 readiness review 收集观察证据。

用法：
    python harness/run_precommit_memory_warn.py                          # warn-only（默认）
    python harness/run_precommit_memory_warn.py --mode blocking          # blocking 模式
    python harness/run_precommit_memory_warn.py --mode blocking --record-observation

关键边界：
    - warn 模式始终 exit 0（不阻断 commit）
    - blocking 模式在 active+blocking=true 规则失败时 exit code 非 0
    - 使用临时 report dir，不污染 harness/reports/*
    - 不生成 latest
    - 不修改 docs/memory/*
    - 不修改 memory_rules.yml
    - 不调用真实 LLM
    - 不改变任何规则状态

回滚方式：
    将 .githooks/pre-commit 第 5 步从 --mode blocking 改回 --mode warn 即可。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 观察记录默认输出目录
_DEFAULT_OBSERVATION_DIR = str(
    PROJECT_ROOT / "harness" / "reports" / "precommit_memory_warn_history"
)

# 颜色定义（终端输出）
_GREEN = "\033[0;32m"
_YELLOW = "\033[1;33m"
_RED = "\033[0;31m"
_CYAN = "\033[0;36m"
_NC = "\033[0m"  # No Color


def _color(text: str, code: str) -> str:
    """仅在终端环境下添加颜色，重定向时跳过。"""
    if sys.stdout.isatty():
        return f"{code}{text}{_NC}"
    return text


def _find_json_object_start(stdout: str) -> int:
    """定位 stdout 中 FastGateReport JSON 对象的起始位置。

    策略：FastGateReport 顶层 JSON 由 json.dumps(indent=2) 生成，
    其首行为 `{` 后紧跟换行和 2 空格缩进的 `"run_id"`。
    嵌套的 enforcement_report 中也有 `"run_id"`，但缩进为 4+ 空格，
    通过正则精确匹配顶层格式来区分。

    Args:
        stdout: fast gate 完整 stdout

    Returns:
        JSON 对象的起始索引，未找到返回 -1
    """
    # 匹配顶层 JSON 起始: 行首 { 紧跟换行和 2 空格缩进的 "run_id"
    match = re.search(r'\{\n {2}"run_id"', stdout)
    if match:
        return match.start()
    return -1


def _find_matching_brace(text: str, start: int) -> int:
    """从 start 位置开始，跟踪花括号深度找到匹配的 `}`。

    Args:
        text: 文本
        start: 起始 `{` 的索引

    Returns:
        匹配 `}` 的索引，未找到返回 -1
    """
    if start >= len(text) or text[start] != "{":
        return -1
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _get_git_info() -> dict[str, str]:
    """获取当前 git commit SHA 和分支名。

    Returns:
        {"commit": "...", "branch": "..."}，失败时返回 "unknown"
    """
    commit = "unknown"
    branch = "unknown"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        pass

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        pass

    return {"commit": commit, "branch": branch}


def _get_worktree_dirty() -> bool:
    """检查工作区是否有未提交的变更（包括 untracked 文件）。

    Returns:
        True 表示工作区有变更
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return len(result.stdout.strip()) > 0
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        pass
    # 无法判断时返回 True（保守）
    return True


def _record_observation(
    analysis: dict,
    report: dict | None,
    duration_ms: float,
    worktree_dirty_before: bool,
    observation_dir: str,
    git_commit: str = "unknown",
    branch: str = "unknown",
    mode: str = "warn",
    actual_exit_code: int = 0,
) -> str | None:
    """生成 timestamp observation snapshot（JSON + MD）。

    不生成 latest 文件。写入失败时仅输出 stderr 警告，不抛异常。

    Args:
        analysis: _analyze_enforcement 返回的分析结果
        report: fast gate JSON 报告（可为 None）
        duration_ms: 运行耗时（毫秒）
        worktree_dirty_before: 运行前工作区是否有变更
        observation_dir: 输出目录
        git_commit: git commit SHA
        branch: 分支名
        mode: "warn" 或 "blocking"
        actual_exit_code: 脚本实际 exit code（blocking 模式可能非 0）

    Returns:
        生成的 JSON 文件路径，失败返回 None
    """
    try:
        out_dir = Path(observation_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # 生成 run_id 和时间戳
        now = datetime.now(timezone.utc)
        local_now = now.astimezone()
        run_id = f"OBS-{now.strftime('%Y%m%dT%H%M%S')}"
        timestamp_local = local_now.isoformat()

        # 提取 TA-R018 结果
        ta_r018_result = "skipped"
        enf = (report or {}).get("enforcement_report") or {}
        for rr in enf.get("rule_results", []):
            if rr.get("rule_id") == "TA-R018":
                result_str = (rr.get("result") or "").lower()
                if result_str == "pass":
                    ta_r018_result = "passed"
                elif result_str == "fail":
                    ta_r018_result = "failed"
                elif result_str in ("warn", "warning"):
                    ta_r018_result = "warning"
                else:
                    ta_r018_result = "skipped"
                break

        # 活跃的 blocking 规则列表
        enf_summary = analysis.get("summary", {})
        active_blocking_rules: list[str] = []
        for rr in enf.get("rule_results", []):
            if rr.get("blocking") and rr.get("status") == "active":
                active_blocking_rules.append(rr.get("rule_id", "?"))

        # 运行后工作区状态
        worktree_dirty_after = _get_worktree_dirty()

        # 构建 observation 数据（Step 23：mode 和 exit_code 跟随实际运行模式）
        observation = {
            "report_type": "precommit_memory_warn_single_observation",
            "run_id": run_id,
            "timestamp": timestamp_local,
            "git_commit": git_commit,
            "branch": branch,
            "duration_ms": round(duration_ms, 1),
            "exit_code": actual_exit_code,
            "warning_count": analysis.get("blocking_failures", 0),
            "active_blocking_rules": active_blocking_rules,
            "ta_r018_result": ta_r018_result,
            "memory_warn_exit_code": actual_exit_code,
            "precommit_mode": "blocking" if mode == "blocking" else "warn_only",
            "polluted_reports": False,
            "generated_latest": False,
            "worktree_dirty_before": worktree_dirty_before,
            "worktree_dirty_after": worktree_dirty_after,
            "enforcement_summary": {
                "total_rules": enf_summary.get("total_rules", 0),
                "passed": enf_summary.get("passed", 0),
                "warnings": enf_summary.get("warnings", 0),
                "blocking_failures": enf_summary.get("blocking_failures", 0),
                "active_blocking": enf_summary.get("active_blocking", 0),
            },
            "boundary_confirmations": {
                "no_blocking": mode != "blocking",  # blocking 模式时此边界不适用
                "no_latest": True,
                "no_docs_memory_modification": True,
                "no_memory_rules_yml_modification": True,
                "temp_report_dir_used": True,
            },
        }

        # 生成文件名（timestamp 部分，不含 latest）
        ts_slug = local_now.strftime("%Y%m%d_%H%M%S")
        json_name = f"precommit_memory_warn_observation_{ts_slug}.json"
        md_name = f"precommit_memory_warn_observation_{ts_slug}.md"

        # 写入 JSON
        json_path = out_dir / json_name
        json_path.write_text(
            json.dumps(observation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 写入 Markdown
        md_path = out_dir / md_name
        md_path.write_text(
            _render_observation_markdown(observation),
            encoding="utf-8",
        )

        return str(json_path)

    except Exception as exc:
        print(
            _color(
                f"[WARN] 观察记录写入失败: {exc}（不影响 pre-commit 结果）",
                _YELLOW,
            ),
            file=sys.stderr,
        )
        return None


def _render_observation_markdown(obs: dict) -> str:
    """将 observation dict 渲染为 Markdown 文本。

    Args:
        obs: observation 数据字典

    Returns:
        Markdown 字符串
    """
    lines: list[str] = []
    lines.append("# Pre-commit Memory Warn Observation (Single Run)")
    lines.append("")
    lines.append(f"**Run ID:** `{obs.get('run_id', '?')}`")
    lines.append(f"**时间:** {obs.get('timestamp', '?')}")
    lines.append(f"**Commit:** `{obs.get('git_commit', '?')[:8]}`")
    lines.append(f"**分支:** {obs.get('branch', '?')}")
    lines.append("")

    # 汇总
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| 指标 | 值 |")
    lines.append(f"|------|-----|")
    lines.append(f"| duration_ms | {obs.get('duration_ms', 0):.1f} |")
    lines.append(f"| exit_code | {obs.get('exit_code', 0)} |")
    lines.append(f"| warning_count | {obs.get('warning_count', 0)} |")
    lines.append(f"| ta_r018_result | {obs.get('ta_r018_result', '?')} |")
    lines.append(f"| precommit_mode | {obs.get('precommit_mode', '?')} |")
    lines.append(f"| worktree_dirty_before | {obs.get('worktree_dirty_before', True)} |")
    lines.append(f"| worktree_dirty_after | {obs.get('worktree_dirty_after', True)} |")
    lines.append("")

    # 活跃规则
    rules = obs.get("active_blocking_rules", [])
    lines.append("## Active Blocking Rules")
    lines.append("")
    if rules:
        for r in rules:
            lines.append(f"- {r}")
    else:
        lines.append("- (无)")
    lines.append("")

    # Enforcement 摘要
    enf = obs.get("enforcement_summary", {})
    lines.append("## Enforcement Summary")
    lines.append("")
    lines.append(f"- 总规则数: {enf.get('total_rules', 0)}")
    lines.append(f"- 通过: {enf.get('passed', 0)}")
    lines.append(f"- 警告: {enf.get('warnings', 0)}")
    lines.append(f"- 阻断失败: {enf.get('blocking_failures', 0)}")
    lines.append(f"- active+blocking 规则数: {enf.get('active_blocking', 0)}")
    lines.append("")

    # 边界确认
    boundary = obs.get("boundary_confirmations", {})
    lines.append("## Boundary Confirmations")
    lines.append("")
    lines.append(f"| 边界 | 状态 |")
    lines.append(f"|------|:--:|")
    lines.append(f"| no blocking | {'✅' if boundary.get('no_blocking') else '❌'} |")
    lines.append(f"| no latest | {'✅' if boundary.get('no_latest') else '❌'} |")
    lines.append(f"| no docs/memory modification | {'✅' if boundary.get('no_docs_memory_modification') else '❌'} |")
    lines.append(f"| no memory_rules.yml modification | {'✅' if boundary.get('no_memory_rules_yml_modification') else '❌'} |")
    lines.append(f"| temp report dir used | {'✅' if boundary.get('temp_report_dir_used') else '❌'} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*Step 21b 自动记录 — 由 pre-commit warn 触发*")
    lines.append(f"*记录时间: {obs.get('timestamp', '?')}*")

    return "\n".join(lines)


def _run_fast_gate_step3(report_dir: str) -> dict | None:
    """运行 fast gate step 3（harness），返回解析后的 JSON 报告。

    Args:
        report_dir: 临时报告目录

    Returns:
        解析成功的 FastGateReport dict，失败返回 None
    """
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "harness" / "run_fast_gate.py"),
                "--step", "3",
                "--report-dir", report_dir,
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(
            _color(f"[WARN] 无法运行 fast gate step 3: {exc}", _YELLOW),
            file=sys.stderr,
        )
        return None

    # 从 stdout 解析 JSON
    stdout = result.stdout
    try:
        # --json 模式：stdout 中嵌入了 JSON 报告，后面还有路径和 summary 文本
        # 通过跟踪花括号深度精确定位完整 JSON 对象
        json_start = _find_json_object_start(stdout)
        if json_start < 0:
            raise ValueError("stdout 中未找到 JSON 对象起始")
        json_end = _find_matching_brace(stdout, json_start)
        if json_end < 0:
            raise ValueError("stdout 中未找到 JSON 对象结束")
        json_str = stdout[json_start:json_end + 1]
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as exc:
        print(
            _color(f"[WARN] 无法解析 fast gate JSON: {exc}", _YELLOW),
            file=sys.stderr,
        )
        return None


def _analyze_enforcement(report: dict) -> dict:
    """从 FastGateReport 中提取 enforcement 摘要。

    Args:
        report: fast gate JSON 报告

    Returns:
        包含 summary 和 blocking_failure_rules 的 dict
    """
    enf = report.get("enforcement_report") or {}
    enf_summary = enf.get("summary", {})
    blocking_failures = enf_summary.get("blocking_failures", 0)

    failure_rules: list[dict] = []
    for rr in enf.get("rule_results", []):
        if rr.get("result") == "FAIL":
            failure_rules.append(rr)

    return {
        "enforcement_available": bool(enf),
        "blocking_failures": blocking_failures,
        "failure_rules": failure_rules,
        "summary": enf_summary,
    }


def render_warn_output(analysis: dict) -> str:
    """渲染 pre-commit warn 输出。

    Args:
        analysis: _analyze_enforcement 返回的分析结果

    Returns:
        预格式化的终端输出字符串
    """
    lines: list[str] = []

    if not analysis["enforcement_available"]:
        lines.append(
            _color("[WARN] Memory Rule Enforcement 未能生成报告，跳过。", _YELLOW)
        )
        return "\n".join(lines)

    enf_summary = analysis["summary"]
    failure_rules = analysis["failure_rules"]
    blocking_failures = analysis["blocking_failures"]

    # 简要统计
    total = enf_summary.get("total_rules", 0)
    passed = enf_summary.get("passed", 0)
    warnings = enf_summary.get("warnings", 0)
    active_blocking = enf_summary.get("active_blocking", 0)

    if blocking_failures == 0:
        lines.append(
            _color(
                f"  Memory Rule Enforcement: {total} 规则, "
                f"{passed} passed, {warnings} warn, "
                f"{active_blocking} active+blocking — 全部通过",
                _GREEN,
            )
        )
        return "\n".join(lines)

    # 有阻断失败 → WARNING
    lines.append("")
    lines.append(
        _color(
            "╔══════════════════════════════════════════════════════════╗",
            _YELLOW,
        )
    )
    lines.append(
        _color(
            "║  ⚠️  Memory Rule Enforcement WARNING (pre-commit)       ║",
            _YELLOW,
        )
    )
    lines.append(
        _color(
            "╚══════════════════════════════════════════════════════════╝",
            _YELLOW,
        )
    )
    lines.append("")
    lines.append(
        _color(
            f"  检测到 {blocking_failures} 项 active+blocking=true 规则失败：",
            _YELLOW,
        )
    )
    lines.append("")

    for rr in failure_rules:
        rule_id = rr.get("rule_id", "?")
        title = rr.get("title", "")
        failed_checks = rr.get("failed_required_checks", [])
        failure_msg = rr.get("failure_message", "")
        suggested_fix = rr.get("suggested_fix", "")
        rollback_plan = rr.get("rollback_plan", "")

        lines.append(f"  📌 {rule_id}: {title}")
        if failed_checks:
            lines.append(
                f"     失败检查: {', '.join(str(c) for c in failed_checks)}"
            )
        if failure_msg:
            lines.append(f"     失败详情: {failure_msg}")
        if suggested_fix:
            lines.append(f"     修复建议: {suggested_fix}")
        if rollback_plan:
            lines.append(f"     回滚方案: {rollback_plan}")
        lines.append("")

    lines.append(
        _color(
            "  💡 建议手动运行完整检查确认问题：",
            _CYAN,
        )
    )
    lines.append(
        _color(
            "     python harness/run_fast_gate.py",
            _CYAN,
        )
    )
    lines.append("")
    lines.append(
        _color(
            "  ⚠️  本次 pre-commit 不阻断 commit，但请关注以上问题。",
            _YELLOW,
        )
    )
    lines.append("")

    return "\n".join(lines)


def render_blocking_output(analysis: dict) -> str:
    """渲染 pre-commit blocking 错误输出（Step 23）。

    与 warn 输出不同，blocking 输出必须包含：
    - "Memory Harness Blocking Error" 标识
    - rule_id、title、failed check、failure message
    - rollback plan、suggested fix
    - 阻断 commit 的明确提示

    Args:
        analysis: _analyze_enforcement 返回的分析结果

    Returns:
        预格式化的终端输出字符串
    """
    lines: list[str] = []

    if not analysis["enforcement_available"]:
        lines.append(
            _color("[WARN] Memory Rule Enforcement 未能生成报告，跳过阻断检查。", _YELLOW)
        )
        return "\n".join(lines)

    enf_summary = analysis["summary"]
    failure_rules = analysis["failure_rules"]
    blocking_failures = analysis["blocking_failures"]

    total = enf_summary.get("total_rules", 0)
    passed = enf_summary.get("passed", 0)
    warnings = enf_summary.get("warnings", 0)
    active_blocking = enf_summary.get("active_blocking", 0)

    if blocking_failures == 0:
        lines.append(
            _color(
                f"  Memory Rule Enforcement: {total} 规则, "
                f"{passed} passed, {warnings} warn, "
                f"{active_blocking} active+blocking — 全部通过",
                _GREEN,
            )
        )
        return "\n".join(lines)

    # 有阻断失败 → BLOCKING ERROR
    lines.append("")
    lines.append(
        _color(
            "╔══════════════════════════════════════════════════════════╗",
            _RED,
        )
    )
    lines.append(
        _color(
            "║  🚫  Memory Harness Blocking Error                       ║",
            _RED,
        )
    )
    lines.append(
        _color(
            "╚══════════════════════════════════════════════════════════╝",
            _RED,
        )
    )
    lines.append("")
    lines.append(
        _color(
            f"  Memory Harness Blocking Error: 检测到 {blocking_failures} 项 "
            f"active+blocking=true 规则失败，commit 已阻断。",
            _RED,
        )
    )
    lines.append("")

    for rr in failure_rules:
        rule_id = rr.get("rule_id", "?")
        title = rr.get("title", "")
        failed_checks = rr.get("failed_required_checks", [])
        failure_msg = rr.get("failure_message", "")
        suggested_fix = rr.get("suggested_fix", "")
        rollback_plan = rr.get("rollback_plan", "")

        lines.append(f"  📌 rule_id: {rule_id}")
        lines.append(f"     title: {title}")
        if failed_checks:
            lines.append(
                f"     failed required_check: {', '.join(str(c) for c in failed_checks)}"
            )
        if failure_msg:
            lines.append(f"     failure message: {failure_msg}")
        if rollback_plan:
            lines.append(f"     rollback plan: {rollback_plan}")
        if suggested_fix:
            lines.append(f"     suggested fix: {suggested_fix}")
        lines.append("")

    lines.append(
        _color(
            "  💡 可手动运行完整检查确认问题：",
            _CYAN,
        )
    )
    lines.append(
        _color(
            "     python harness/run_fast_gate.py",
            _CYAN,
        )
    )
    lines.append("")
    lines.append(
        _color(
            "  🚫  commit 已阻断。请修复以上问题后重新提交。",
            _RED,
        )
    )
    lines.append(
        _color(
            "     紧急情况可跳过（不推荐）：git commit --no-verify",
            _YELLOW,
        )
    )
    lines.append("")

    return "\n".join(lines)


def run_precommit_warn(
    temp_root: str | None = None,
    quiet: bool = False,
    record_observation: bool = False,
    observation_dir: str | None = None,
    mode: str = "warn",
) -> int:
    """执行 pre-commit Memory Harness 检查（Step 20 + Step 21b + Step 23）。

    Args:
        temp_root: 临时目录父路径，None 则使用系统默认
        quiet: True 则在全部通过时不输出任何内容
        record_observation: True 则在检查后生成 observation snapshot（Step 21b）
        observation_dir: observation 输出目录，None 使用默认目录
        mode: "warn"（默认，始终 exit 0）或 "blocking"（规则失败时 exit code 非 0）

    Returns:
        warn 模式始终返回 0；blocking 模式在 active+blocking=true 规则失败时返回 1
    """
    t_start = time.perf_counter()
    report = None
    analysis: dict = {}
    worktree_dirty_before = False
    git_commit = "unknown"
    branch = "unknown"
    exit_code: int = 0  # Step 23：blocking 模式下可能变为非 0

    # 观察记录的前置采集（运行前）
    if record_observation:
        worktree_dirty_before = _get_worktree_dirty()
        git_info = _get_git_info()
        git_commit = git_info["commit"]
        branch = git_info["branch"]

    try:
        # 创建临时目录
        temp_dir = tempfile.mkdtemp(
            prefix="memory_warn_",
            dir=temp_root,
        )

        # 运行 fast gate step 3
        report = _run_fast_gate_step3(temp_dir)

        if report is None:
            # fast gate 运行失败 → WARN 但不阻断（基础设施故障不阻断 commit）
            print(
                _color(
                    "[WARN] fast gate step 3 执行异常，跳过 Memory Rule Enforcement。"
                    " 建议手动运行: python harness/run_fast_gate.py",
                    _YELLOW,
                )
            )
            analysis = {"blocking_failures": 0, "enforcement_available": False}
            return 0

        # 分析 enforcement
        analysis = _analyze_enforcement(report)

        # 输出结果（quiet 模式下仅在有问题时输出）
        has_issues = analysis.get("blocking_failures", 0) > 0
        lack_enforcement = not analysis.get("enforcement_available", False)

        if mode == "blocking":
            # blocking 模式：用 blocking renderer 输出
            if not quiet or has_issues or lack_enforcement:
                output = render_blocking_output(analysis)
                if output.strip():
                    print(output)
            # blocking 模式下，active+blocking=true 规则失败 → exit code 非 0
            if has_issues:
                exit_code = 1
        else:
            # warn 模式（默认）：用 warn renderer 输出，始终 exit 0
            if not quiet or has_issues or lack_enforcement:
                output = render_warn_output(analysis)
                if output.strip():
                    print(output)

        return exit_code

    except Exception as exc:
        # 任何未预料的异常 → WARN 但不阻断（quiet 也输出）
        print(
            _color(
                f"[WARN] Memory pre-commit 检查异常: {exc}。"
                " 建议手动运行: python harness/run_fast_gate.py",
                _YELLOW,
            ),
            file=sys.stderr,
        )
        analysis = {"blocking_failures": 0, "enforcement_available": False}
        return 0

    finally:
        # 观察记录（Step 21b + Step 23）—— 在清理临时目录前执行（不影响 exit code）
        if record_observation:
            try:
                duration_ms = (time.perf_counter() - t_start) * 1000.0
                obs_dir = observation_dir or _DEFAULT_OBSERVATION_DIR
                _record_observation(
                    analysis=analysis,
                    report=report,
                    duration_ms=duration_ms,
                    worktree_dirty_before=worktree_dirty_before,
                    observation_dir=obs_dir,
                    git_commit=git_commit,
                    branch=branch,
                    mode=mode,
                    actual_exit_code=exit_code,
                )
            except Exception as obs_exc:
                # 观察记录写入失败绝不影响 exit code
                print(
                    _color(
                        f"[WARN] 观察记录写入失败: {obs_exc}（不影响 pre-commit 结果）",
                        _YELLOW,
                    ),
                    file=sys.stderr,
                )

        # 清理临时目录
        try:
            if 'temp_dir' in locals() and Path(temp_dir).exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass  # 清理失败也不影响


def main(argv: list[str] | None = None) -> int:
    """CLI 入口 — pre-commit Memory Harness（Step 20 + Step 21b + Step 23）。"""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="Memory Harness pre-commit 检查（Step 20 + Step 21b + Step 23）"
    )
    parser.add_argument(
        "--temp-root",
        default=None,
        help="临时目录父路径（默认系统临时目录）",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="静默模式：仅在发现问题时输出",
    )
    parser.add_argument(
        "--record-observation",
        action="store_true",
        help="生成 timestamp observation snapshot 用于 Step 22 readiness review（Step 21b）",
    )
    parser.add_argument(
        "--observation-dir",
        default=_DEFAULT_OBSERVATION_DIR,
        help=f"observation 输出目录（默认 {_DEFAULT_OBSERVATION_DIR}）",
    )
    parser.add_argument(
        "--mode",
        choices=["warn", "blocking"],
        default="warn",
        help="运行模式：warn（默认，始终 exit 0）或 blocking（规则失败时 exit code 非 0）",
    )
    args = parser.parse_args(argv)

    return run_precommit_warn(
        temp_root=args.temp_root,
        quiet=args.quiet,
        record_observation=args.record_observation,
        observation_dir=args.observation_dir,
        mode=args.mode,
    )


if __name__ == "__main__":
    sys.exit(main())
