#!/usr/bin/env python3
"""
人审决策 CLI——M4b 人审闸门入口。

子命令：
  show  <package_dir>          只读：展示当前状态和最近日志
  set   <package_dir> [选项]   设置决策状态（APPROVED / REQUEST_CHANGES / REJECTED）
  audit <package_dir>          只读：展示完整审计日志

规则：
  - APPROVED 只能由人显式执行（禁止 Agent 调用）
  - APPROVED 必须要求 --message 非空
  - APPROVED 必须要求 verification_summary.yml 存在
  - overall_status == FAIL 时禁止 APPROVED
  - REQUEST_CHANGES / REJECTED 必须要求 --message 非空
  - REJECTED 不是终态——人可从 REJECTED 转为 APPROVED 或 REQUEST_CHANGES
  - 所有 set 操作追加 decision_log.yml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import yaml
except ImportError:
    yaml = None

from src.agent.decision_manager import (
    read_decision,
    read_decision_log,
    transition_state,
)
from src.ir.types import DecisionStatus

# ═══════════════════════════════════════════════════════════
# 错误码
# ═══════════════════════════════════════════════════════════

EXIT_SUCCESS = 0
EXIT_MISSING_FILE = 2       # 必备文件缺失
EXIT_INVALID_STATE = 3      # 状态不合法（如 FAIL 时 APPROVED）
EXIT_EMPTY_MESSAGE = 4       # --message 为空
EXIT_TRANSITION_DENIED = 5  # 状态转换被拒绝
EXIT_USAGE = 6               # 参数错误


# ═══════════════════════════════════════════════════════════
# 只读：show
# ═══════════════════════════════════════════════════════════


def cmd_show(package_dir: Path) -> int:
    """展示 Review Package 的当前决策状态和最近日志。

    只读，不修改任何文件。
    """
    # 读取 decision.yml
    try:
        decision = read_decision(package_dir)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return EXIT_MISSING_FILE

    print("═══════════════════════════════════════════")
    print("  决策状态（decision.yml）")
    print("═══════════════════════════════════════════")
    print(f"  request_id:              {decision.get('request_id', 'N/A')}")
    print(f"  current_state:           {decision.get('current_state', 'N/A')}")
    print(f"  human_review_required:   {decision.get('human_review_required', 'N/A')}")
    print(f"  verification_overall:    {decision.get('verification_overall_status', 'N/A')}")
    print(f"  last_updated:            {decision.get('last_updated', 'N/A')}")
    print(f"  last_updated_by:         {decision.get('last_updated_by', 'N/A')}")
    print(f"  human_decision_note:     {decision.get('human_decision_note', '(空)')}")

    # artifact_hashes 简略显示
    hashes = decision.get("artifact_hashes", {})
    if hashes:
        print(f"  artifact_hashes:")
        for key, val in hashes.items():
            if val:
                print(f"    {key}: {val[:16]}...")
            else:
                print(f"    {key}: (null)")

    # 读取 verification_summary（若存在）
    summary_path = package_dir / "reports" / "verification_summary.yml"
    if summary_path.is_file() and yaml is not None:
        summary = yaml.safe_load(summary_path.read_text(encoding="utf-8")) or {}
        print()
        print("═══════════════════════════════════════════")
        print("  验证摘要（verification_summary.yml）")
        print("═══════════════════════════════════════════")
        print(f"  verification_id:         {summary.get('verification_id', '(M4a 旧格式)')}")
        print(f"  overall_status:          {summary.get('overall_status', 'N/A')}")
        print(f"  sql_static:              {summary.get('sql_static_status', 'N/A')}")
        print(f"  sql_sample:              {summary.get('sql_sample_status', 'N/A')}")
        print(f"  spark_static:            {summary.get('spark_static_status', 'N/A')}")
        print(f"  spark_sample:            {summary.get('spark_sample_status', 'N/A')}")
        print(f"  cross_validation:        {summary.get('cross_validation_status', 'N/A')}")
        before = summary.get("decision_state_before_verify")
        after = summary.get("decision_state_after_verify")
        if before:
            print(f"  decision_state_before:   {before}")
        if after:
            print(f"  decision_state_after:    {after}")
        failures = summary.get("failures", [])
        if failures:
            print(f"  failures:                {len(failures)} 条")
            for f in failures:
                print(f"    - {f}")
        warnings = summary.get("warnings", [])
        if warnings:
            print(f"  warnings:                {len(warnings)} 条（取前 5 条）")
            for w in warnings[:5]:
                print(f"    - {w}")

    # 最近决策日志（最后 5 条）
    try:
        log = read_decision_log(package_dir)
        entries = log.get("entries", [])
    except FileNotFoundError:
        entries = []

    print()
    print("═══════════════════════════════════════════")
    print(f"  决策日志（最近 5 / 共 {len(entries)} 条）")
    print("═══════════════════════════════════════════")
    for entry in entries[-5:]:
        print(f"  {entry.get('timestamp', '?')[:19]}")
        print(f"    {entry.get('from_state')} → {entry.get('to_state')}")
        print(f"    by: {entry.get('actor_id', entry.get('changed_by', '?'))}")
        print(f"    reason: {entry.get('reason', '(无)')}")
        print()

    return EXIT_SUCCESS


# ═══════════════════════════════════════════════════════════
# 只读：audit
# ═══════════════════════════════════════════════════════════


def cmd_audit(package_dir: Path) -> int:
    """展示完整审计日志。

    只读，不修改任何文件。
    """
    try:
        log = read_decision_log(package_dir)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return EXIT_MISSING_FILE

    entries = log.get("entries", [])
    request_id = log.get("request_id", "N/A")

    print(f"审计日志：{request_id}")
    print(f"共 {len(entries)} 条记录")
    print("=" * 70)

    for i, entry in enumerate(entries, 1):
        ts = entry.get("timestamp", "?")[:19]
        from_s = entry.get("from_state") or "(创建)"
        to_s = entry.get("to_state", "?")
        actor = entry.get("actor_id", entry.get("changed_by", "?"))
        reason = entry.get("reason", "")
        vid = entry.get("verification_id", "")

        print(f"[{i:03d}] {ts}")
        print(f"     {from_s} → {to_s}")
        print(f"     actor: {actor}")
        if vid:
            print(f"     verification: {vid}")
        print(f"     reason: {reason}")
        print()

    return EXIT_SUCCESS


# ═══════════════════════════════════════════════════════════
# 写：set
# ═══════════════════════════════════════════════════════════


def cmd_set(
    package_dir: Path,
    state: str,
    message: str,
    user: str = "human",
) -> int:
    """设置人审决策状态。

    严格校验：
      - APPROVED 要求 verification_summary.yml 存在
      - APPROVED 要求 overall_status != FAIL
      - 所有 set 要求 --message 非空
    """
    # 校验 1：消息非空
    if not message or not message.strip():
        print(
            "[ERROR] --message 不能为空。人审决策必须提供理由。",
            file=sys.stderr,
        )
        return EXIT_EMPTY_MESSAGE

    # 校验 2：状态有效
    valid_for_human = {"APPROVED", "REQUEST_CHANGES", "REJECTED"}
    if state not in valid_for_human:
        print(
            f"[ERROR] 无效的决策状态: {state}。"
            f"人可设置的状态: {sorted(valid_for_human)}",
            file=sys.stderr,
        )
        return EXIT_INVALID_STATE

    # 校验 3：APPROVED 必须验证过
    if state == "APPROVED":
        summary_path = package_dir / "reports" / "verification_summary.yml"
        if not summary_path.is_file():
            print(
                "[ERROR] APPROVED 要求 verification_summary.yml 存在——"
                "请先运行 M3 验证引擎。",
                file=sys.stderr,
            )
            return EXIT_MISSING_FILE

        # 校验 4：FAIL 时禁止 APPROVED
        if yaml is not None:
            summary = yaml.safe_load(summary_path.read_text(encoding="utf-8")) or {}
            overall = summary.get("overall_status", "N/A")
            if overall == "FAIL":
                print(
                    f"[ERROR] 验证 overall_status 为 FAIL，不能 APPROVED。\n"
                    f"请先处理以下 FAIL 项后重新验证：",
                    file=sys.stderr,
                )
                for f in summary.get("failures", []):
                    print(f"  - {f}", file=sys.stderr)
                return EXIT_INVALID_STATE

            # 提示：PENDING/SKIPPED/WARN 可以 APPROVED，但给出提醒
            if overall in {"PENDING", "SKIPPED"}:
                print(
                    f"[提醒] 验证 overall_status 为 {overall}，"
                    f"部分检查未完成。请确认已审查未完成项后再 APPROVED。"
                )
            elif overall == "WARN":
                print(
                    f"[提醒] 验证 overall_status 为 WARN。"
                    f"请确认已审查所有警告项后再 APPROVED。"
                )

    # 执行状态转换
    try:
        changed = transition_state(
            package_dir,
            to_state=state,
            changed_by="human",
            reason=message.strip(),
            actor_id=f"human:{user}",
        )
    except FileNotFoundError as exc:
        print(f"[ERROR] 文件缺失: {exc}", file=sys.stderr)
        return EXIT_MISSING_FILE
    except ValueError as exc:
        print(f"[ERROR] 状态转换被拒绝: {exc}", file=sys.stderr)
        return EXIT_TRANSITION_DENIED

    if changed:
        # 读取当前状态确认
        decision = read_decision(package_dir)
        print(f"决策已更新: {decision.get('current_state')}")
        print(f"操作者:     human:{user}")
        print(f"理由:       {message.strip()}")
    else:
        decision = read_decision(package_dir)
        print(f"状态未变更（已是 {decision.get('current_state')}）")

    return EXIT_SUCCESS


# ═══════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════


def main() -> int:
    """解析命令行参数并执行子命令"""
    parser = argparse.ArgumentParser(
        description="Data Dev Agent v2.0 人审决策 CLI（M4b）",
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # ---- show ----
    show_parser = subparsers.add_parser("show", help="展示当前决策状态")
    show_parser.add_argument(
        "package_dir",
        help="Review Package 目录路径",
    )

    # ---- set ----
    set_parser = subparsers.add_parser("set", help="设置决策状态（人审决策）")
    set_parser.add_argument(
        "package_dir",
        help="Review Package 目录路径",
    )
    set_parser.add_argument(
        "--state",
        required=True,
        choices=["APPROVED", "REQUEST_CHANGES", "REJECTED"],
        help="目标决策状态",
    )
    set_parser.add_argument(
        "--message",
        required=True,
        help="决策理由（必填，非空）",
    )
    set_parser.add_argument(
        "--user",
        default="human",
        help="操作者标识（默认: human）",
    )

    # ---- audit ----
    audit_parser = subparsers.add_parser("audit", help="展示完整审计日志")
    audit_parser.add_argument(
        "package_dir",
        help="Review Package 目录路径",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return EXIT_USAGE

    package_dir = Path(args.package_dir)
    if not package_dir.is_dir():
        print(f"[ERROR] 目录不存在: {package_dir}", file=sys.stderr)
        return EXIT_MISSING_FILE

    if args.command == "show":
        return cmd_show(package_dir)
    elif args.command == "set":
        return cmd_set(
            package_dir,
            state=args.state,
            message=args.message,
            user=args.user,
        )
    elif args.command == "audit":
        return cmd_audit(package_dir)
    else:
        parser.print_help()
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
