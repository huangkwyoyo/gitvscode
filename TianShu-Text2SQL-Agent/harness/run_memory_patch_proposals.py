"""CLI 入口：从 memory review report 生成 patch proposal snapshot。

Step 14：读取人工审批决策文件 + Step 12 审查报告，
为每个 approved 的 review item 生成 patch proposal 草案。

用法：
    # 基础用法
    python harness/run_memory_patch_proposals.py \
      --input harness/reports/memory_reviews/memory_suggestion_review_20260618T120000Z.json \
      --approved-decisions harness/reports/memory_reviews/approved_decisions_20260618T120000Z.json

    # 指定输出目录
    python harness/run_memory_patch_proposals.py \
      --input harness/reports/memory_reviews/memory_suggestion_review_20260618T120000Z.json \
      --approved-decisions approved.json \
      --output-dir custom_patches/

关键边界：
    - 只生成 timestamp snapshot，不写 latest
    - 不修改 docs/memory/*
    - 不写入 memory_rules.yml
    - 不自动新增 tests / evals / harness/checks
    - 不调用真实 LLM
    - 不接入 fast gate / pre-commit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.memory_patch_proposals import (  # noqa: E402
    build_patch_proposal_report,
    load_approved_decisions,
    load_review_report,
    write_patch_proposal_snapshot,
)

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "harness" / "reports" / "memory_patch_proposals"


def main() -> int:
    """CLI 入口：只生成 patch proposal，不修改任何目标文件。"""
    parser = argparse.ArgumentParser(
        description="从 memory review report 生成 patch proposal snapshot（Step 14）"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Step 12 生成的 memory_suggestion_review_*.json 文件路径（只能显式指定，不读 latest）",
    )
    parser.add_argument(
        "--approved-decisions",
        type=Path,
        required=True,
        help="人工审批决策 JSON 文件路径（只能显式指定，不读 latest）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="patch proposal 报告输出目录（默认 harness/reports/memory_patch_proposals/）",
    )
    args = parser.parse_args()

    input_path = args.input.resolve()
    approved_path = args.approved_decisions.resolve()

    # 拒绝读取 *_latest.* 文件
    for label, path in [("--input", input_path), ("--approved-decisions", approved_path)]:
        if "latest" in path.name.lower():
            print(
                f"ERROR: {label} 不允许读取 *_latest.* 文件: {path.name}。请指定显式的 timestamp snapshot。",
                file=sys.stderr,
            )
            return 1

    # 加载审批决策
    try:
        approved_decisions = load_approved_decisions(approved_path)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: 审批决策文件格式不正确: {exc}", file=sys.stderr)
        return 1

    if not approved_decisions["approved_indices"]:
        print("WARNING: 审批决策文件中没有 approved items。将生成空 patch proposal。")

    # 加载审查报告
    try:
        review_report = load_review_report(input_path)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: 审查报告格式不正确: {exc}", file=sys.stderr)
        return 1

    # 生成 patch proposal 报告
    try:
        report = build_patch_proposal_report(
            review_report,
            approved_decisions,
            source_review_path=str(input_path),
        )
        paths = write_patch_proposal_snapshot(report, args.output_dir)
    except Exception as exc:
        print(f"ERROR: patch proposal 生成失败: {exc}", file=sys.stderr)
        return 1

    summary = report["summary"]
    counts = summary["patch_type_counts"]

    print("Memory Patch Proposal Report")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['markdown']}")
    print(f"total_review_items: {summary['total_review_items']}")
    print(f"approved_items: {summary['approved_items']}")
    print(f"unapproved_items: {summary['unapproved_items']}")
    print(f"approved_but_skipped: {summary['approved_but_skipped']}")
    print(f"total_patches: {summary['total_patches']}")
    print()
    if counts:
        print("Patch 类型分布:")
        for pt, count in sorted(counts.items()):
            print(f"  {pt}: {count}")
    else:
        print("（无 patch 生成）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
