"""CLI 入口：独立运行 Memory Rule Enforcement（Step 18a）。

读取 memory_rules.yml + 可选 harness check results 文件，计算每条规则的
enforcement 级别和结果，生成 dry-run enforcement report。

用法：
    # 基础用法（仅规则分析，无 check results）
    python harness/run_memory_rule_enforcement.py \
      --rules docs/memory/memory_rules.yml

    # 传入 check results JSON 文件
    python harness/run_memory_rule_enforcement.py \
      --rules docs/memory/memory_rules.yml \
      --check-results harness/reports/check_results.json

    # 指定输出目录
    python harness/run_memory_rule_enforcement.py \
      --rules docs/memory/memory_rules.yml \
      --output-dir custom_enforcement/

关键边界：
    - 只生成 timestamp snapshot，不写 latest
    - 不修改 docs/memory/*
    - 不修改 memory_rules.yml
    - 不自动晋升规则
    - 不改变 exit code（dry-run only）
    - 不调用真实 LLM
    - 不接入 pre-commit
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.memory_rule_enforcement import (  # noqa: E402
    build_enforcement_report,
    render_enforcement_console_summary,
    write_enforcement_snapshot,
)

DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "harness" / "reports" / "memory_rule_enforcements"
)


def main() -> int:
    """CLI 入口：独立的 memory rule enforcement dry-run。"""
    parser = argparse.ArgumentParser(
        description="Memory Rule Enforcement dry-run（Step 18a）"
    )
    parser.add_argument(
        "--rules",
        type=Path,
        required=True,
        help="memory_rules.yml 文件路径（只能显式指定，不读 latest）",
    )
    parser.add_argument(
        "--check-results",
        type=Path,
        default=None,
        help="harness check results JSON 文件路径（可选，格式为 check result 列表）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="enforcement report 输出目录（默认 harness/reports/memory_rule_enforcements/）",
    )
    args = parser.parse_args()

    rules_path = args.rules.resolve()

    # 拒绝读取 *_latest.* 文件
    if "latest" in rules_path.name.lower():
        print(
            f"ERROR: --rules 不允许读取 *_latest.* 文件: {rules_path.name}。"
            f"请指定显式的文件路径。",
            file=sys.stderr,
        )
        return 1

    if not rules_path.exists():
        print(f"ERROR: 规则文件不存在: {rules_path}", file=sys.stderr)
        return 1

    # 加载 check results
    check_results = None
    if args.check_results:
        cr_path = args.check_results.resolve()
        if "latest" in cr_path.name.lower():
            print(
                f"ERROR: --check-results 不允许读取 *_latest.* 文件: {cr_path.name}。",
                file=sys.stderr,
            )
            return 1
        if not cr_path.exists():
            print(f"ERROR: check results 文件不存在: {cr_path}", file=sys.stderr)
            return 1
        try:
            check_results = json.loads(cr_path.read_text(encoding="utf-8"))
            if not isinstance(check_results, list):
                print(
                    f"ERROR: check results 必须是 JSON 数组: {cr_path}",
                    file=sys.stderr,
                )
                return 1
        except (json.JSONDecodeError, OSError) as exc:
            print(f"ERROR: 无法读取 check results 文件: {exc}", file=sys.stderr)
            return 1

    # 生成 enforcement report
    try:
        report = build_enforcement_report(
            rules_path=rules_path,
            check_results=check_results,
        )
        paths = write_enforcement_snapshot(report, args.output_dir)
    except Exception as exc:
        print(f"ERROR: enforcement report 生成失败: {exc}", file=sys.stderr)
        return 1

    # 输出 summary
    summary = report["summary"]
    print("Memory Rule Enforcement Report (Step 18a Dry-Run)")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['markdown']}")
    print(f"total_rules: {summary['total_rules']}")
    print(f"proposed (visibility_only): {summary['proposed']}")
    print(f"active_warning: {summary['active_warning']}")
    print(f"active_blocking (dry-run): {summary['active_blocking']}")
    print(f"deprecated: {summary['deprecated']}")
    print(f"superseded: {summary['superseded']}")
    print(f"passed: {summary['passed']}")
    print(f"warnings: {summary['warnings']}")
    print(f"would_fail (dry-run): {summary['would_fail']}")
    print(f"skipped: {summary['skipped']}")
    print(f"infra_errors: {summary['infra_errors']}")
    print()

    # 输出控制台摘要（与 fast gate 集成格式相同）
    console_summary = render_enforcement_console_summary(report)
    print(console_summary)

    # Step 18a: 始终返回 0（dry-run 不改变 exit code）
    print("[OK] Enforcement dry-run 完成。exit code 不受影响。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
