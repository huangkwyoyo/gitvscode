#!/usr/bin/env python3
"""
人审决策 CLI——M4c 跨 package 协调版。

子命令：
  show    <package_dir>          只读：展示当前状态和最近日志
  set     <package_dir> [选项]   设置决策状态（APPROVED / REQUEST_CHANGES / REJECTED）
  audit   <package_dir>          只读：展示完整审计日志
  list                           只读：列出注册表中所有 package
  deps    <package_dir>          只读：显示依赖树
  status                         只读：全局状态一览 + 一致性检查

M4c 新增（跨 package）：
  - list / deps / status 只读子命令
  - set 操作自动同步注册表
  - SUPERSEDED 传播（via verification_engine）

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
from src.agent.package_registry import (
    check_consistency,
    check_for_stale_approvals,
    detect_dependency_cycle,
    get_dependency_tree,
    read_registry,
    update_registry_state,
)
from src.ir.types import DecisionStatus

# ═══════════════════════════════════════════════════════════
# 错误码（M4c 扩展）
# ═══════════════════════════════════════════════════════════

EXIT_SUCCESS = 0
EXIT_MISSING_FILE = 2        # 必备文件缺失
EXIT_INVALID_STATE = 3       # 状态不合法（如 FAIL 时 APPROVED）
EXIT_EMPTY_MESSAGE = 4       # --message 为空
EXIT_TRANSITION_DENIED = 5   # 状态转换被拒绝
EXIT_USAGE = 6                # 参数错误
EXIT_REGISTRY_ERROR = 7      # 注册表读写失败（M4c）
EXIT_DEPENDENCY_CYCLE = 8    # 依赖链中存在环（M4c）
EXIT_PROPAGATION_BLOCKED = 9 # SUPERSEDED 传播部分失败（M4c）


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
    print(
        f"  verification_overall:    "
        f"{decision.get('verification_overall_status', 'N/A')}"
    )
    print(f"  last_updated:            {decision.get('last_updated', 'N/A')}")
    print(f"  last_updated_by:         {decision.get('last_updated_by', 'N/A')}")
    print(
        f"  human_decision_note:     "
        f"{decision.get('human_decision_note', '(空)')}"
    )

    # artifact_hashes 简略显示
    hashes = decision.get("artifact_hashes", {})
    if hashes:
        print(f"  artifact_hashes:")
        for key, val in hashes.items():
            if val:
                print(f"    {key}: {val[:16]}...")
            else:
                print(f"    {key}: (null)")

    # notes 显示（M4c：跨 package 提醒）
    notes = decision.get("notes", [])
    if notes:
        print(f"  notes:")
        for note in notes:
            print(f"    - {note}")

    # 读取 verification_summary（若存在）
    summary_path = package_dir / "reports" / "verification_summary.yml"
    if summary_path.is_file() and yaml is not None:
        summary = yaml.safe_load(summary_path.read_text(encoding="utf-8")) or {}
        print()
        print("═══════════════════════════════════════════")
        print("  验证摘要（verification_summary.yml）")
        print("═══════════════════════════════════════════")
        print(
            f"  verification_id:         "
            f"{summary.get('verification_id', '(M4a 旧格式)')}"
        )
        print(f"  overall_status:          {summary.get('overall_status', 'N/A')}")
        print(f"  sql_static:              {summary.get('sql_static_status', 'N/A')}")
        print(f"  sql_sample:              {summary.get('sql_sample_status', 'N/A')}")
        print(
            f"  spark_static:            {summary.get('spark_static_status', 'N/A')}"
        )
        print(
            f"  spark_sample:            {summary.get('spark_sample_status', 'N/A')}"
        )
        print(
            f"  cross_validation:        "
            f"{summary.get('cross_validation_status', 'N/A')}"
        )
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
# 只读：list（M4c 新增）
# ═══════════════════════════════════════════════════════════


def cmd_list(
    output_root: str = "generated/review_packages",
    state_filter: str = "",
    json_output: bool = False,
) -> int:
    """列出注册表中所有 package。

    Args:
        output_root: Review Package 输出根目录
        state_filter: 可选状态过滤
        json_output: 是否输出 JSON

    只读，不修改任何文件。
    """
    try:
        registry = read_registry(output_root)
    except Exception as exc:
        print(f"[ERROR] 注册表读取失败: {exc}", file=sys.stderr)
        return EXIT_REGISTRY_ERROR

    packages = registry.get("packages", {})

    if state_filter:
        packages = {
            k: v for k, v in packages.items()
            if v.get("current_state") == state_filter
        }

    if json_output:
        import json
        result = []
        for pkg_id, pkg in sorted(packages.items()):
            result.append({
                "package_id": pkg_id,
                "state": pkg.get("current_state", "?"),
                "last_updated": pkg.get("last_updated", ""),
                "depends_on": pkg.get("depends_on", []),
                "depended_by": pkg.get("depended_by", []),
            })
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return EXIT_SUCCESS

    if not packages:
        print("注册表为空——尚无已注册的 Review Package。")
        return EXIT_SUCCESS

    print(f"{'Package ID':40s} {'状态':20s} {'最后更新'}")
    print("-" * 90)
    for pkg_id, pkg in sorted(packages.items()):
        state = pkg.get("current_state", "?")
        updated = pkg.get("last_updated", "")[:19]
        print(f"{pkg_id:40s} {state:20s} {updated}")

    print()
    print(f"共 {len(packages)} 个 package。")
    return EXIT_SUCCESS


# ═══════════════════════════════════════════════════════════
# 只读：deps（M4c 新增）
# ═══════════════════════════════════════════════════════════


def cmd_deps(
    package_dir: Path,
    output_root: str = "generated/review_packages",
) -> int:
    """显示指定 package 的依赖树。

    只读，不修改任何文件。
    """
    try:
        registry = read_registry(output_root)
    except Exception as exc:
        print(f"[ERROR] 注册表读取失败: {exc}", file=sys.stderr)
        return EXIT_REGISTRY_ERROR

    package_id = package_dir.name

    # 检查依赖环
    cycles = detect_dependency_cycle(registry)
    if cycles:
        print("[警告] 注册表中存在依赖环：")
        for cycle in cycles:
            print(f"  {' → '.join(cycle)}")
        print()

    tree = get_dependency_tree(package_id, registry)
    packages = registry.get("packages", {})

    # 如果注册表没有直接信息，从 packages 中获取
    pkg = packages.get(package_id, {})
    state = pkg.get("current_state", "未注册")

    if not pkg:
        print(f"{package_id} [未注册]——该 package 尚未注册到注册表。")
        print()
        print("请先运行 M2 build 以注册此 package：")
        print(
            f"  python scripts/dev_agent/build_review_package.py "
            f"-r fixtures/requirements/{package_id.replace('_m2', '')}.yml"
        )
        return EXIT_MISSING_FILE

    print()
    print(f"{package_id} [{state}]")
    print()

    # 显示上游依赖
    deps_on = pkg.get("depends_on", [])
    if deps_on:
        print("  依赖上游（depends_on）：")
        for dep_id in deps_on:
            dep = packages.get(dep_id, {})
            dep_state = dep.get("current_state", "未注册")
            flag = ""
            if dep_state == "SUPERSEDED":
                flag = " [!] 已过期"
            elif dep_state != "APPROVED":
                flag = " [!] 状态不稳定"
            print(f"    ├── {dep_id} [{dep_state}]{flag}")
        print()
    else:
        print("  无上游依赖。")
        print()

    # 显示下游被依赖
    dep_by = pkg.get("depended_by", [])
    if dep_by:
        print("  被下游依赖（depended_by）：")
        for dep_id in dep_by:
            dep = packages.get(dep_id, {})
            dep_state = dep.get("current_state", "未注册")
            flag = ""
            if dep_state == "APPROVED":
                flag = " ← 本 package 变更会影响此下游"
            elif dep_state == "SUPERSEDED":
                flag = " ← 已因本 package 变更而 SUPERSEDED"
            print(f"    ├── {dep_id} [{dep_state}]{flag}")
        print()
    else:
        print("  无下游依赖。")
        print()

    # 过期提醒
    stale = check_for_stale_approvals(output_root)
    related = [s for s in stale if s.get("upstream") == package_id]
    if related:
        print("  [!] 下游批准可能过期：")
        for s in related:
            print(f"    - {s['package_id']}: {s['reason']}")
        print()

    return EXIT_SUCCESS


# ═══════════════════════════════════════════════════════════
# 只读：status（M4c 新增）
# ═══════════════════════════════════════════════════════════


def cmd_status(output_root: str = "generated/review_packages") -> int:
    """显示全局注册表概览和一致性检查。

    只读，不修改任何文件。
    """
    try:
        registry = read_registry(output_root)
    except Exception as exc:
        print(f"[ERROR] 注册表读取失败: {exc}", file=sys.stderr)
        return EXIT_REGISTRY_ERROR

    packages = registry.get("packages", {})

    # 统计
    state_counts: dict[str, int] = {}
    for pkg in packages.values():
        s = pkg.get("current_state", "?")
        state_counts[s] = state_counts.get(s, 0) + 1

    print("═══════════════════════════════════════════")
    print("  注册表概览")
    print("═══════════════════════════════════════════")
    print(f"  总 package 数:     {len(packages)}")
    for state in ["APPROVED", "PENDING_REVIEW", "SUPERSEDED", "REQUEST_CHANGES", "REJECTED"]:
        count = state_counts.get(state, 0)
        if count:
            print(f"  {state:20s} {count}")
    print()

    # 一致性检查
    consistency = check_consistency(output_root)

    issues_found = False
    if consistency["orphaned_entries"]:
        issues_found = True
        print("[!] ORPHANED（注册表中记录但目录已删除）：")
        for entry in consistency["orphaned_entries"]:
            print(f"    - {entry}")
        print()

    if consistency["unregistered_dirs"]:
        issues_found = True
        print("[!] 未注册目录（有 package 目录但注册表无记录）：")
        for entry in consistency["unregistered_dirs"]:
            print(f"    - {entry}")
        print()

    if consistency["state_mismatches"]:
        issues_found = True
        print("[!] 状态不一致（注册表与 decision.yml 不匹配）：")
        for entry in consistency["state_mismatches"]:
            print(f"    - {entry}")
        print()

    if not issues_found and packages:
        print("[OK] 注册表与所有 package 目录一致。")
        print()

    # 过期批准检测
    stale = check_for_stale_approvals(output_root)
    if stale:
        print("[!] 需关注——下游批准可能过期：")
        for s in stale:
            print(f"    - {s['package_id']} [{s['state']}]: {s['reason']}")
        print()

    # 依赖环检测
    cycles = detect_dependency_cycle(registry)
    if cycles:
        print("[ERROR] 依赖环检测：")
        for cycle in cycles:
            print(f"    {' → '.join(cycle)}")
        print()
        return EXIT_DEPENDENCY_CYCLE

    if not packages:
        print("注册表为空——尚无已注册的 Review Package。")
        print("运行 M2 build 后 package 会自动注册。")

    return EXIT_SUCCESS


# ═══════════════════════════════════════════════════════════
# 写：set（M4c 增强——同步注册表）
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
    M4c：状态变更后同步注册表。
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
            summary = (
                yaml.safe_load(summary_path.read_text(encoding="utf-8")) or {}
            )
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

    # M4c：状态变更后同步注册表（从 package_dir 推导 output_root）
    package_id = package_dir.name
    output_root = str(package_dir.parent)
    try:
        update_registry_state(package_id, state, output_root=output_root)
    except Exception as exc:
        print(
            f"[警告] 注册表同步失败（不影响决策结果）: {exc}",
            file=sys.stderr,
        )

    if changed:
        decision = read_decision(package_dir)
        print(f"决策已更新: {decision.get('current_state')}")
        print(f"操作者:     human:{user}")
        print(f"理由:       {message.strip()}")

        # M5：从 APPROVED 转为 release 状态时的提醒
    if state == "APPROVED":
        deploy_manifest_path = package_dir / "deployment_manifest.yml"
        if deploy_manifest_path.is_file():
            print()
            print(
                "[提醒] 当前 APPROVED 仅表示 QUERY_LOGIC_APPROVED（只读查询逻辑已审查）。"
            )
            print(
                "部署产物及配置需要独立的发布审批——请使用 'release' 子命令。"
            )
            print(
                f"  python scripts/dev_agent/review_decision.py release {package_dir}"
                f" --state RELEASE_APPROVED --message \"...\""
            )

    # M4c：从 SUPERSEDED 恢复时提醒下游
        if state == "APPROVED":
            try:
                registry = read_registry(output_root)
                packages = registry.get("packages", {})
                deps = packages.get(package_id, {}).get("depended_by", [])
                if deps:
                    print()
                    print(
                        f"[提醒] 本 package 有 {len(deps)} 个下游 package。"
                        f"若下游曾因本 package SUPERSEDED 而自动过期，"
                        f"请提醒下游审查者重新审查。"
                    )
                    for d in deps:
                        ds = packages.get(d, {}).get("current_state", "?")
                        print(f"  - {d}: {ds}")
            except Exception:
                pass
    else:
        decision = read_decision(package_dir)
        print(f"状态未变更（已是 {decision.get('current_state')}）")

    return EXIT_SUCCESS


# ═══════════════════════════════════════════════════════════
# 写：release set（M5 新增——发布审批）
# ═══════════════════════════════════════════════════════════


def cmd_release_set(
    package_dir: Path,
    state: str,
    message: str,
    user: str = "human",
) -> int:
    """设置发布审批状态（RELEASE_APPROVED / RELEASE_REJECTED）。

    严格校验：
      - 仅人能设置
      - deployment_manifest.yml 必须存在
      - 部署静态检查必须通过（无 FAIL）
      - --message 非空
      - RELEASE_APPROVED 要求 verification_summary.yml 存在
    """
    # 校验 1：消息非空
    if not message or not message.strip():
        print("[ERROR] --message 不能为空。发布审批必须提供理由。", file=sys.stderr)
        return EXIT_EMPTY_MESSAGE

    # 校验 2：状态有效
    valid_states = {"RELEASE_APPROVED", "RELEASE_REJECTED"}
    if state not in valid_states:
        print(
            f"[ERROR] 无效的发布审批状态: {state}。"
            f"人可设置的状态: {sorted(valid_states)}",
            file=sys.stderr,
        )
        return EXIT_INVALID_STATE

    # 校验 3：deployment_manifest.yml 必须存在
    deploy_manifest_path = package_dir / "deployment_manifest.yml"
    if not deploy_manifest_path.is_file():
        print(
            "[ERROR] deployment_manifest.yml 不存在——"
            "请先运行 M2 build 生成部署草案。",
            file=sys.stderr,
        )
        return EXIT_MISSING_FILE

    # 校验 4：RELEASE_APPROVED 要求验证通过
    if state == "RELEASE_APPROVED":
        summary_path = package_dir / "reports" / "verification_summary.yml"
        if not summary_path.is_file():
            print(
                "[ERROR] RELEASE_APPROVED 要求 verification_summary.yml 存在——"
                "请先运行 M3 验证引擎。",
                file=sys.stderr,
            )
            return EXIT_MISSING_FILE

        if yaml is not None:
            summary = yaml.safe_load(summary_path.read_text(encoding="utf-8")) or {}
            overall = summary.get("overall_status", "N/A")
            deploy_status = summary.get("deploy_static_status", "N/A")

            if overall == "FAIL":
                print(
                    f"[ERROR] 验证 overall_status 为 FAIL，不能 RELEASE_APPROVED。",
                    file=sys.stderr,
                )
                return EXIT_INVALID_STATE

            if deploy_status == "FAIL":
                print(
                    f"[ERROR] 部署静态检查 status 为 FAIL，不能 RELEASE_APPROVED。\n"
                    f"请先修复部署产物中的 FAIL 项。",
                    file=sys.stderr,
                )
                return EXIT_INVALID_STATE

    # 执行：更新 deployment_manifest.yml
    if yaml is None:
        print("[ERROR] 缺少 pyyaml 依赖: pip install pyyaml", file=sys.stderr)
        return EXIT_MISSING_FILE

    deploy_manifest = yaml.safe_load(deploy_manifest_path.read_text(encoding="utf-8")) or {}
    current_status = deploy_manifest.get("release_status", "DRAFT")

    if current_status == state:
        print(f"发布审批状态未变更（已是 {state}）")
        return EXIT_SUCCESS

    deploy_manifest["release_status"] = state
    deploy_manifest["release_approved_by"] = f"human:{user}"
    deploy_manifest["release_message"] = message.strip()

    # 原子写入
    tmp_path = deploy_manifest_path.with_suffix(".tmp")
    tmp_path.write_text(
        yaml.safe_dump(deploy_manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    tmp_path.replace(deploy_manifest_path)

    # 同时追加到 decision_log
    try:
        from src.agent.decision_manager import append_decision_log
        from datetime import datetime, timezone

        now_iso = datetime.now(timezone.utc).isoformat()
        append_decision_log(package_dir, {
            "timestamp": now_iso,
            "from_state": f"release:{current_status}",
            "to_state": f"release:{state}",
            "changed_by": "human",
            "actor_id": f"human:{user}",
            "reason": f"发布审批: {message.strip()[:200]}",
        })
    except Exception:
        pass  # 日志追加失败不阻断

    print(f"发布审批状态已更新: {current_status} → {state}")
    print(f"操作者:     human:{user}")
    print(f"理由:       {message.strip()}")

    if state == "RELEASE_APPROVED":
        print()
        print("[重要] RELEASE_APPROVED 表示部署产物及配置已审查，可以进入发布流程。")
        print("但实际部署仍需人执行，Agent 不自动上线。")
    else:
        print()
        print("[提醒] 发布被拒绝——部署产物需修改后重新提交审批。")

    return EXIT_SUCCESS


# ═══════════════════════════════════════════════════════════
# CLI 入口（M4c 扩展 + M5 release）
# ═══════════════════════════════════════════════════════════


def main() -> int:
    """解析命令行参数并执行子命令"""
    parser = argparse.ArgumentParser(
        description="Data Dev Agent v2.0 人审决策 CLI（M4c）",
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

    # ---- list（M4c 新增） ----
    list_parser = subparsers.add_parser("list", help="列出注册表中所有 package")
    list_parser.add_argument(
        "--state",
        default="",
        help="按状态过滤（如 --state APPROVED）",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出",
    )
    list_parser.add_argument(
        "--registry",
        default="generated/review_packages",
        help="Review Package 输出根目录",
    )

    # ---- deps（M4c 新增） ----
    deps_parser = subparsers.add_parser("deps", help="显示依赖树")
    deps_parser.add_argument(
        "package_dir",
        help="Review Package 目录路径",
    )
    deps_parser.add_argument(
        "--registry",
        default="generated/review_packages",
        help="Review Package 输出根目录",
    )

    # ---- status（M4c 新增） ----
    status_parser = subparsers.add_parser("status", help="全局注册表概览")
    status_parser.add_argument(
        "--registry",
        default="generated/review_packages",
        help="Review Package 输出根目录",
    )

    # ---- release（M5 新增——发布审批） ----
    release_parser = subparsers.add_parser("release", help="设置发布审批状态（M5 部署绑定）")
    release_parser.add_argument(
        "package_dir",
        help="Review Package 目录路径",
    )
    release_parser.add_argument(
        "--state",
        required=True,
        choices=["RELEASE_APPROVED", "RELEASE_REJECTED"],
        help="发布审批状态",
    )
    release_parser.add_argument(
        "--message",
        required=True,
        help="发布审批理由（必填，非空）",
    )
    release_parser.add_argument(
        "--user",
        default="human",
        help="操作者标识（默认: human）",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return EXIT_USAGE

    # list/status 不需要 package_dir
    if args.command == "list":
        return cmd_list(
            output_root=args.registry,
            state_filter=args.state,
            json_output=args.json,
        )
    elif args.command == "status":
        return cmd_status(output_root=args.registry)

    # 其余命令需要 package_dir
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
    elif args.command == "deps":
        return cmd_deps(package_dir, output_root=args.registry)
    elif args.command == "release":
        return cmd_release_set(
            package_dir,
            state=args.state,
            message=args.message,
            user=args.user,
        )
    else:
        parser.print_help()
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
