"""CLI 入口：生成 memory promotion validation report（Step 17）。

读取 Step 16 promotion report + memory_rules.yml，验证人工应用的 promotion
是否符合 proposal。只做 validation，不修改任何文件。

用法：
    python harness/run_memory_promotion_validation.py \
      --promotion-report harness/reports/memory_rule_promotions/memory_rule_promotion_<timestamp>.json \
      --rules docs/memory/memory_rules.yml

    # 指定输出目录
    python harness/run_memory_promotion_validation.py \
      --promotion-report harness/reports/memory_rule_promotions/memory_rule_promotion_<timestamp>.json \
      --rules docs/memory/memory_rules.yml \
      --output-dir custom_validations/

    # 同时运行重型检查命令
    python harness/run_memory_promotion_validation.py \
      --promotion-report harness/reports/memory_rule_promotions/memory_rule_promotion_<timestamp>.json \
      --rules docs/memory/memory_rules.yml \
      --run-checks

关键边界：
    - 只生成 timestamp snapshot，不写 latest
    - 不修改 docs/memory/*
    - 不修改 memory_rules.yml
    - 不自动晋升规则
    - 不调用真实 LLM
    - 不接入 pre-commit / fast gate 阻断
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.memory_promotion_validation import (  # noqa: E402
    build_promotion_validation_report,
    write_promotion_validation_snapshot,
)

DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "harness" / "reports" / "memory_promotion_validations"
)


def main() -> int:
    """CLI 入口：只做 validation，不修改任何目标文件。"""
    parser = argparse.ArgumentParser(
        description="生成 memory promotion validation report（Step 17）"
    )
    parser.add_argument(
        "--promotion-report",
        type=Path,
        required=True,
        help="Step 16 生成的 memory_rule_promotion_*.json 文件路径（只能显式指定，不读 latest）",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        required=True,
        help="memory_rules.yml 文件路径（只能显式指定，不读 latest）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="validation report 输出目录（默认 harness/reports/memory_promotion_validations/）",
    )
    parser.add_argument(
        "--run-checks",
        action="store_true",
        default=False,
        help="是否实际运行重型检查命令（generate_rule_index.py 等）",
    )
    args = parser.parse_args()

    promo_path = args.promotion_report.resolve()
    rules_path = args.rules.resolve()

    # 拒绝读取 *_latest.* 文件
    for label, path in [("--promotion-report", promo_path), ("--rules", rules_path)]:
        if "latest" in path.name.lower():
            print(
                f"ERROR: {label} 不允许读取 *_latest.* 文件: {path.name}。"
                f"请指定显式的 timestamp snapshot。",
                file=sys.stderr,
            )
            return 1

    # 检查文件是否存在
    for label, path in [("promotion report", promo_path), ("rules", rules_path)]:
        if not path.exists():
            print(f"ERROR: {label} 文件不存在: {path}", file=sys.stderr)
            return 1

    # 生成 validation report
    try:
        report = build_promotion_validation_report(
            promotion_report_path=promo_path,
            rules_path=rules_path,
            run_checks=args.run_checks,
        )
        paths = write_promotion_validation_snapshot(report, args.output_dir)
    except Exception as exc:
        print(f"ERROR: validation report 生成失败: {exc}", file=sys.stderr)
        return 1

    summary = report["summary"]

    print("Memory Promotion Validation Report")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['markdown']}")
    print(f"candidates_checked: {summary['candidates_checked']}")
    print(f"applied: {summary['applied']}")
    print(f"passed: {summary['passed']}")
    print(f"warnings: {summary['warnings']}")
    print(f"failures: {summary['failures']}")
    print(f"pending_manual_actions: {summary['pending_manual_actions']}")
    print()

    # 输出推荐命令
    if report.get("recommended_commands"):
        print("推荐命令:")
        for cmd in report["recommended_commands"]:
            print(f"  {cmd}")
        print()

    # 退出码：有 failures 时返回 1
    if summary["failures"] > 0:
        print(
            f"[WARN] 验证发现 {summary['failures']} 个 failures，请先修复后再继续。",
            file=sys.stderr,
        )
        return 1

    if summary["warnings"] > 0:
        print(f"[WARN] 验证通过但有 {summary['warnings']} 个 warnings，请注意查看。")

    if summary["pending_manual_actions"] > 0:
        print(f"[PENDING] 有 {summary['pending_manual_actions']} 个待人工操作项。")

    print("[OK] Validation 完成。未修改 memory_rules.yml。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
