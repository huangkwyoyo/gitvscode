"""CLI 入口：从 memory suggestions snapshot 生成人工审查报告。

Step 12：加载 Step 11 生成的 memory_suggestions_*.json，
对每条 suggestion 进行 review_action 分类，输出结构化审查报告。

用法：
    python harness/run_memory_suggestion_review.py \
      --input harness/reports/memory_suggestions/memory_suggestions_20260618T120000Z.json

    python harness/run_memory_suggestion_review.py \
      --input memory_suggestions_20260618T120000Z.json \
      --output-dir custom_reviews/

关键边界：
    - 只能读取显式 --input 指定的文件
    - 不读取 *_latest.*
    - 只生成 timestamp snapshot，不写 latest
    - 不修改 docs/memory/*
    - 不调用真实 LLM
    - 不接入 fast gate 阻断
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.memory_suggestion_review import (  # noqa: E402
    build_memory_suggestion_review_report,
    load_memory_suggestions_snapshot,
    write_memory_suggestion_review_snapshot,
)

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "harness" / "reports" / "memory_reviews"


def main() -> int:
    """CLI 入口：只生成审查报告，不修改任何规则状态。"""
    parser = argparse.ArgumentParser(
        description="从 memory suggestions snapshot 生成人工审查报告（Step 12）"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Step 11 生成的 memory_suggestions_*.json 文件路径（只能显式指定，不读 latest）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="审查报告输出目录（默认 harness/reports/memory_reviews/）",
    )
    args = parser.parse_args()

    input_path = args.input.resolve()

    # 拒绝读取 *_latest.* 文件
    if "latest" in input_path.name.lower():
        print(
            "ERROR: 不允许读取 *_latest.* 文件。请指定显式的 timestamp snapshot。",
            file=sys.stderr,
        )
        return 1

    try:
        # 加载 Step 11 的建议报告（只读显式 --input）
        suggestions_report = load_memory_suggestions_snapshot(input_path)

        # 生成审查报告
        review_report = build_memory_suggestion_review_report(
            suggestions_report,
            source_snapshot_path=str(input_path),
        )

        # 写入 snapshot（不生成 latest）
        paths = write_memory_suggestion_review_snapshot(review_report, args.output_dir)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: 输入文件格式不正确: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = review_report["summary"]
    action_counts = summary["action_counts"]

    print("Memory Suggestion Review Report")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['markdown']}")
    print(f"total_suggestions: {summary['total_suggestions']}")
    print(f"total_reviewed: {summary['total_reviewed']}")
    print(f"high_priority: {summary['high_priority_count']}")
    print(f"manual_review_required: {summary['manual_review_required_count']}")
    print()
    print("Review Action 分布:")
    for action in sorted(action_counts.keys()):
        print(f"  {action}: {action_counts[action]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
