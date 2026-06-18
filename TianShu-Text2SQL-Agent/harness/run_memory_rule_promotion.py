"""CLI 入口：生成 memory rule promotion proposal report（Step 16）。

读取 memory_rules.yml + Step 15 validation report，评估每条规则的晋升资格，
生成 promotion proposal snapshot。只做评估，不修改任何目标文件。

用法：
    # 基础用法
    python harness/run_memory_rule_promotion.py \
      --rules docs/memory/memory_rules.yml \
      --validation-report harness/reports/memory_patch_validations/memory_patch_validation_<timestamp>.json

    # 指定输出目录
    python harness/run_memory_rule_promotion.py \
      --rules docs/memory/memory_rules.yml \
      --validation-report harness/reports/memory_patch_validations/memory_patch_validation_<timestamp>.json \
      --output-dir custom_promotions/

    # 包含 fast gate 历史和审批决策
    python harness/run_memory_rule_promotion.py \
      --rules docs/memory/memory_rules.yml \
      --validation-report harness/reports/memory_patch_validations/memory_patch_validation_<timestamp>.json \
      --fast-gate-history harness/reports/fast_gate_history_<timestamp>.json \
      --approval-decisions harness/reports/memory_rule_promotions/promotion_approvals_<timestamp>.json

关键边界：
    - 只生成 timestamp snapshot，不写 latest
    - 不修改 docs/memory/*
    - 不修改 memory_rules.yml
    - 不自动晋升规则（不修改 status / blocking）
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

from harness.memory_rule_promotion import (  # noqa: E402
    build_rule_promotion_report,
    write_rule_promotion_snapshot,
)

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "harness" / "reports" / "memory_rule_promotions"


def main() -> int:
    """CLI 入口：只生成 promotion proposal，不修改任何目标文件。"""
    parser = argparse.ArgumentParser(
        description="生成 memory rule promotion proposal report（Step 16）"
    )
    parser.add_argument(
        "--rules",
        type=Path,
        required=True,
        help="memory_rules.yml 文件路径（只能显式指定，不读 latest）",
    )
    parser.add_argument(
        "--validation-report",
        type=Path,
        required=True,
        help="Step 15 生成的 memory_patch_validation_*.json 文件路径（只能显式指定，不读 latest）",
    )
    parser.add_argument(
        "--fast-gate-history",
        type=Path,
        default=None,
        help="fast gate 历史记录 JSON 文件路径（可选）",
    )
    parser.add_argument(
        "--approval-decisions",
        type=Path,
        default=None,
        help="人工审批决策 JSON 文件路径（可选）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="promotion report 输出目录（默认 harness/reports/memory_rule_promotions/）",
    )
    args = parser.parse_args()

    # 拒绝读取 *_latest.* 文件
    rules_path = args.rules.resolve()
    val_path = args.validation_report.resolve()

    for label, path in [
        ("--rules", rules_path),
        ("--validation-report", val_path),
    ]:
        if "latest" in path.name.lower():
            print(
                f"ERROR: {label} 不允许读取 *_latest.* 文件: {path.name}。"
                f"请指定显式的 timestamp snapshot。",
                file=sys.stderr,
            )
            return 1

    # 可选参数也拒绝 latest
    if args.fast_gate_history:
        fg_path = args.fast_gate_history.resolve()
        if "latest" in fg_path.name.lower():
            print(
                f"ERROR: --fast-gate-history 不允许读取 *_latest.* 文件: {fg_path.name}。",
                file=sys.stderr,
            )
            return 1
    if args.approval_decisions:
        ad_path = args.approval_decisions.resolve()
        if "latest" in ad_path.name.lower():
            print(
                f"ERROR: --approval-decisions 不允许读取 *_latest.* 文件: {ad_path.name}。",
                file=sys.stderr,
            )
            return 1

    # 检查 rules 文件是否存在
    if not rules_path.exists():
        print(f"ERROR: 规则文件不存在: {rules_path}", file=sys.stderr)
        return 1

    # 检查 validation report 是否存在
    if not val_path.exists():
        print(f"ERROR: 验证报告文件不存在: {val_path}", file=sys.stderr)
        return 1

    # 生成 promotion report
    try:
        report = build_rule_promotion_report(
            rules_path=rules_path,
            validation_report_path=val_path,
            fast_gate_history_path=args.fast_gate_history.resolve()
            if args.fast_gate_history
            else None,
            approval_decisions_path=args.approval_decisions.resolve()
            if args.approval_decisions
            else None,
        )
        paths = write_rule_promotion_snapshot(report, args.output_dir)
    except Exception as exc:
        print(f"ERROR: promotion report 生成失败: {exc}", file=sys.stderr)
        return 1

    summary = report["summary"]

    print("Memory Rule Promotion Proposal Report")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['markdown']}")
    print(f"total_rules: {summary['total_rules']}")
    print(f"total_candidates: {summary['total_candidates']}")
    print()
    print("Promotion 类型分布:")
    print(f"  proposed_to_active: {summary['proposed_to_active']}")
    print(f"  active_to_blocking: {summary['active_to_blocking']}")
    print(f"  keep_proposed: {summary['keep_proposed']}")
    print(f"  demote_or_rewrite: {summary['demote_or_rewrite']}")
    print()
    print("资格分布:")
    print(f"  eligible: {summary['eligible']}")
    print(f"  not_eligible: {summary['not_eligible']}")
    print(f"  needs_manual_review: {summary['needs_manual_review']}")
    print()

    # 注意：eligible > 0 时返回 0（因为 eligible 表示满足条件，是正常结果）
    # demote_or_rewrite > 0 时也返回 0（因为这也是正常评估结果）
    # 只有在生成过程出错时才返回 1

    print("[OK] Promotion proposal 报告生成完成。")
    print("[WARN] 未修改 memory_rules.yml，所有晋升需人工审查后手动执行。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
