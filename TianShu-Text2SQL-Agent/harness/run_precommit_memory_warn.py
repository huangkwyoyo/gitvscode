"""Memory Harness pre-commit warn-only 脚本（Step 20）。

职责：
    在 git commit 前运行轻量 Memory Rule Enforcement 检查。
    发现 active+blocking=true 规则失败时输出 WARNING，但始终 exit 0，
    不阻断 commit。

用法：
    python harness/run_precommit_memory_warn.py

关键边界：
    - 始终 exit 0（不阻断 commit）
    - 使用临时 report dir，不污染 harness/reports/*
    - 不生成 latest
    - 不修改 docs/memory/*
    - 不修改 memory_rules.yml
    - 不调用真实 LLM
    - 不改变任何规则状态
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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


def run_precommit_warn(temp_root: str | None = None, quiet: bool = False) -> int:
    """执行 pre-commit warn 检查，始终返回 0。

    Args:
        temp_root: 临时目录父路径，None 则使用系统默认
        quiet: True 则在全部通过时不输出任何内容

    Returns:
        始终返回 0
    """
    try:
        # 创建临时目录
        temp_dir = tempfile.mkdtemp(
            prefix="memory_warn_",
            dir=temp_root,
        )

        # 运行 fast gate step 3
        report = _run_fast_gate_step3(temp_dir)

        if report is None:
            # fast gate 运行失败 → WARN 但不阻断（quiet 也输出）
            print(
                _color(
                    "[WARN] fast gate step 3 执行异常，跳过 Memory Rule Enforcement。"
                    " 建议手动运行: python harness/run_fast_gate.py",
                    _YELLOW,
                )
            )
            return 0

        # 分析 enforcement
        analysis = _analyze_enforcement(report)

        # 输出结果（quiet 模式下仅在有问题时输出）
        has_issues = analysis.get("blocking_failures", 0) > 0
        lack_enforcement = not analysis.get("enforcement_available", False)

        if not quiet or has_issues or lack_enforcement:
            output = render_warn_output(analysis)
            if output.strip():
                print(output)

        return 0

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
        return 0

    finally:
        # 清理临时目录
        try:
            if 'temp_dir' in locals() and Path(temp_dir).exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass  # 清理失败也不影响


def main(argv: list[str] | None = None) -> int:
    """CLI 入口 — pre-commit warn-only Memory Harness。"""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="Memory Harness pre-commit warn-only 检查（Step 20）"
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
    args = parser.parse_args(argv)

    return run_precommit_warn(temp_root=args.temp_root, quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
