"""CLI 入口：从 patch proposal 生成 validation report。

Step 15：验证人工应用 patch proposal 后的落地结果是否合格。
只做 validation，不做 apply。

用法：
    python harness/run_memory_patch_validation.py \
      --proposal harness/reports/memory_patch_proposals/memory_patch_proposal_PP20260618T120000Z.json

    # 指定输出目录
    python harness/run_memory_patch_validation.py \
      --proposal harness/reports/memory_patch_proposals/memory_patch_proposal_PP20260618T120000Z.json \
      --output-dir custom_validations/

    # 同时运行重型检查命令
    python harness/run_memory_patch_validation.py \
      --proposal harness/reports/memory_patch_proposals/memory_patch_proposal_PP20260618T120000Z.json \
      --run-checks

关键边界：
    - 只生成 timestamp snapshot，不写 latest
    - 不修改 docs/memory/*
    - 不自动运行 generate_rule_index.py（除非显式 --run-checks）
    - 不调用真实 LLM
    - 不接入 pre-commit / fast gate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.memory_patch_validation import (  # noqa: E402
    build_validation_report,
    write_validation_snapshot,
)

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "harness" / "reports" / "memory_patch_validations"


def main() -> int:
    """CLI 入口：只做验证，不做 apply。"""
    parser = argparse.ArgumentParser(
        description="从 patch proposal 生成 validation report（Step 15）"
    )
    parser.add_argument(
        "--proposal",
        type=Path,
        required=True,
        help="Step 14 生成的 memory_patch_proposal_*.json 文件路径（只能显式指定，不读 latest）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="验证报告输出目录（默认 harness/reports/memory_patch_validations/）",
    )
    parser.add_argument(
        "--run-checks",
        action="store_true",
        default=False,
        help="是否实际运行重型检查命令（generate_rule_index.py、check_memory_update.py 等）",
    )
    args = parser.parse_args()

    proposal_path = args.proposal.resolve()

    # 拒绝读取 *_latest.* 文件
    if "latest" in proposal_path.name.lower():
        print(
            f"ERROR: --proposal 不允许读取 *_latest.* 文件: {proposal_path.name}。"
            f"请指定显式的 timestamp snapshot。",
            file=sys.stderr,
        )
        return 1

    # 生成验证报告
    try:
        report = build_validation_report(
            proposal_path,
            run_checks=args.run_checks,
        )
        paths = write_validation_snapshot(report, args.output_dir)
    except Exception as exc:
        print(f"ERROR: 验证报告生成失败: {exc}", file=sys.stderr)
        return 1

    summary = report["summary"]

    print("Memory Patch Validation Report")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['markdown']}")
    print(f"patches_checked: {summary['patches_checked']}")
    print(f"passed: {summary['passed']}")
    print(f"warnings: {summary['warnings']}")
    print(f"failures: {summary['failures']}")
    print(f"pending_manual_actions: {summary['pending_manual_actions']}")
    print()

    # 输出推荐的命令
    if report.get("recommended_commands"):
        print("推荐命令:")
        for cmd in report["recommended_commands"]:
            print(f"  {cmd}")
        print()

    # 退出码：有 failures 时返回 1
    if summary["failures"] > 0:
        print(
            f"⚠️  验证发现 {summary['failures']} 个 failures，请先修复后再继续。",
            file=sys.stderr,
        )
        return 1

    if summary["warnings"] > 0:
        print(f"⚠️  验证通过但有 {summary['warnings']} 个 warnings，请注意查看。")

    if summary["pending_manual_actions"] > 0:
        print(
            f"⏳ 有 {summary['pending_manual_actions']} 个待人工操作项。"
        )

    print("✅ Validation 完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
