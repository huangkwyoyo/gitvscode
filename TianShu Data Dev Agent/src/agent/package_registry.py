"""
Package 注册表管理器——M4c 跨 package 协调核心。

负责：
  - 注册表读写（registry.yml）
  - 依赖解析与自动检测
  - SUPERSEDED 跨 package 传播
  - 一致性检查与过期批准检测
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import yaml


REGISTRY_FILENAME = "registry.yml"
DEFAULT_REGISTRY_DIR = "generated/review_packages"


def _iso_now() -> str:
    """返回当前 UTC ISO8601 时间戳。"""
    return datetime.now(timezone.utc).isoformat()


def get_registry_path(output_root: str | Path = DEFAULT_REGISTRY_DIR) -> Path:
    """返回注册表文件路径。"""
    return Path(output_root) / REGISTRY_FILENAME


# ═══════════════════════════════════════════════════════════
# 注册表读写
# ═══════════════════════════════════════════════════════════


def read_registry(output_root: str | Path = DEFAULT_REGISTRY_DIR) -> dict[str, Any]:
    """读取 package 注册表。

    Args:
        output_root: Review Package 输出根目录

    Returns:
        注册表 dict。若注册表不存在或为空，返回空注册表骨架。
    """
    registry_path = get_registry_path(output_root)
    if not registry_path.is_file():
        return {
            "registry_version": 1,
            "last_updated": "",
            "packages": {},
        }
    return yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {
        "registry_version": 1,
        "last_updated": "",
        "packages": {},
    }


def write_registry(
    registry: dict[str, Any],
    output_root: str | Path = DEFAULT_REGISTRY_DIR,
) -> None:
    """原子写入注册表（先写 .tmp 再 replace）。

    Args:
        registry: 注册表 dict
        output_root: Review Package 输出根目录
    """
    registry["last_updated"] = _iso_now()
    registry_path = get_registry_path(output_root)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = registry_path.with_suffix(".tmp")
    tmp_path.write_text(
        yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    tmp_path.replace(registry_path)


# ═══════════════════════════════════════════════════════════
# Package 注册与注销
# ═══════════════════════════════════════════════════════════


def register_package(
    package_id: str,
    package_path: str | Path,
    artifact_hashes: dict[str, Any] | None = None,
    depends_on: list[str] | None = None,
    output_root: str | Path = DEFAULT_REGISTRY_DIR,
) -> dict[str, Any]:
    """在注册表中注册（或更新）一个 Review Package。

    Args:
        package_id: Package 标识（如 trip_daily_report_m2）
        package_path: Package 目录路径
        artifact_hashes: artifact 哈希 dict（可选）
        depends_on: 手动声明的依赖列表（可选）
        output_root: Review Package 输出根目录

    Returns:
        更新后的注册表
    """
    registry = read_registry(output_root)
    packages = registry.setdefault("packages", {})

    now_iso = _iso_now()

    if package_id not in packages:
        # 新注册——尝试从 decision.yml 读取真实状态
        initial_state = "PENDING_REVIEW"
        try:
            pkg_path = Path(package_path)
            decision_yml = pkg_path / "decision.yml"
            if decision_yml.is_file():
                decision = yaml.safe_load(decision_yml.read_text(encoding="utf-8")) or {}
                ds = decision.get("current_state", "")
                if ds:
                    initial_state = ds
        except Exception:
            pass

        packages[package_id] = {
            "path": str(Path(package_path).resolve()),
            "current_state": initial_state,
            "depends_on": list(depends_on or []),
            "depended_by": [],
            "artifact_hashes": artifact_hashes or {},
            "created_at": now_iso,
            "last_updated": now_iso,
        }
    else:
        # 更新已有记录——保留 depended_by，更新其他字段
        existing = packages[package_id]
        existing["path"] = str(Path(package_path).resolve())
        existing["last_updated"] = now_iso
        if artifact_hashes:
            existing["artifact_hashes"] = artifact_hashes
        if depends_on is not None:
            # 清理旧反向依赖
            _remove_from_depended_by(packages, package_id)
            existing["depends_on"] = list(depends_on)

    # 维护反向依赖：对于每个依赖项，将当前 package 加入其 depended_by
    _rebuild_depended_by(packages, package_id)

    write_registry(registry, output_root)
    return registry


def _remove_from_depended_by(packages: dict, package_id: str) -> None:
    """从所有上游的 depended_by 中移除该 package。"""
    if package_id not in packages:
        return
    for dep_id in packages[package_id].get("depends_on", []):
        if dep_id in packages:
            depended = packages[dep_id].setdefault("depended_by", [])
            if package_id in depended:
                depended.remove(package_id)


def _rebuild_depended_by(packages: dict, package_id: str) -> None:
    """重建当前 package 对上游的反向依赖。"""
    if package_id not in packages:
        return
    for dep_id in packages[package_id].get("depends_on", []):
        if dep_id in packages:
            depended = packages[dep_id].setdefault("depended_by", [])
            if package_id not in depended:
                depended.append(package_id)


def unregister_package(
    package_id: str,
    output_root: str | Path = DEFAULT_REGISTRY_DIR,
) -> dict[str, Any]:
    """从注册表注销一个 Review Package。

    Args:
        package_id: Package 标识
        output_root: Review Package 输出根目录

    Returns:
        更新后的注册表
    """
    registry = read_registry(output_root)
    packages = registry.setdefault("packages", {})

    if package_id in packages:
        # 清理反向依赖
        _remove_from_depended_by(packages, package_id)
        del packages[package_id]

    write_registry(registry, output_root)
    return registry


# ═══════════════════════════════════════════════════════════
# 依赖解析
# ═══════════════════════════════════════════════════════════


def auto_detect_dependencies(
    package_dir: Path,
    registry: dict[str, Any],
) -> list[str]:
    """从 lineage 自动检测 package 依赖。

    读取 lineage/source_refs.yml 的 source_tables 列表，
    若某项的 name 匹配注册表中已知 package 的 request_id，
    则视为依赖。

    Args:
        package_dir: Package 目录路径
        registry: 当前注册表

    Returns:
        检测到的依赖 package ID 列表（已去重）
    """
    lineage_path = package_dir / "lineage" / "source_refs.yml"
    if not lineage_path.is_file():
        return []

    lineage = yaml.safe_load(lineage_path.read_text(encoding="utf-8")) or {}
    source_tables = lineage.get("source_tables") or []

    # 收集注册表中所有已知的 package ID
    known_packages = set(registry.get("packages", {}).keys())

    dependencies: list[str] = []
    for table in source_tables:
        name = ""
        if isinstance(table, dict):
            name = str(table.get("name") or "")
        else:
            name = str(table)

        # 检查表名是否匹配某个已知 package
        # 匹配规则：表名含 package_id 或 package_id 含表名
        for pkg_id in known_packages:
            if pkg_id == name or pkg_id in name or name in pkg_id:
                if pkg_id not in dependencies:
                    dependencies.append(pkg_id)

    return dependencies


def detect_dependency_cycle(
    registry: dict[str, Any],
) -> list[list[str]]:
    """检测注册表中的依赖环。

    Args:
        registry: 当前注册表

    Returns:
        检测到的环列表，每个环是 package ID 列表。空列表表示无环。
    """
    packages = registry.get("packages", {})

    # 构建邻接表
    adj: dict[str, list[str]] = {}
    for pkg_id, pkg in packages.items():
        adj.setdefault(pkg_id, [])
        for dep in pkg.get("depends_on", []):
            if dep in packages:
                adj.setdefault(pkg_id, []).append(dep)

    # DFS 三色标记检测环
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {pkg_id: WHITE for pkg_id in adj}
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        path.append(node)
        for neighbor in adj.get(node, []):
            if color.get(neighbor) == WHITE:
                dfs(neighbor, path)
            elif color.get(neighbor) == GRAY:
                # 发现环
                cycle_start = path.index(neighbor)
                cycles.append(path[cycle_start:] + [neighbor])
        path.pop()
        color[node] = BLACK

    for pkg_id in adj:
        if color[pkg_id] == WHITE:
            dfs(pkg_id, [])

    return cycles


def get_dependency_tree(
    package_id: str,
    registry: dict[str, Any],
) -> dict[str, Any]:
    """获取指定 package 的依赖树。

    Args:
        package_id: Package 标识
        registry: 当前注册表

    Returns:
        依赖树 dict，含 depends_on 和 depended_by 子树
    """
    packages = registry.get("packages", {})

    def _build_subtree(pkg_id: str, visited: set) -> dict | None:
        if pkg_id in visited:
            return {"_circular": True}
        if pkg_id not in packages:
            return None
        pkg = packages[pkg_id]
        visited.add(pkg_id)
        return {
            "package_id": pkg_id,
            "current_state": pkg.get("current_state", "?"),
            "depends_on": [
                _build_subtree(d, visited.copy())
                for d in pkg.get("depends_on", [])
            ],
            "depended_by": [
                _build_subtree(d, visited.copy())
                for d in pkg.get("depended_by", [])
            ],
        }

    return _build_subtree(package_id, set()) or {}


# ═══════════════════════════════════════════════════════════
# 状态同步
# ═══════════════════════════════════════════════════════════


def update_registry_state(
    package_id: str,
    state: str,
    output_root: str | Path = DEFAULT_REGISTRY_DIR,
) -> dict[str, Any]:
    """更新注册表中指定 package 的状态。

    供 decision_manager 在状态转换后调用，保持注册表与 decision.yml 一致。

    Args:
        package_id: Package 标识
        state: 新状态
        output_root: Review Package 输出根目录

    Returns:
        更新后的注册表
    """
    registry = read_registry(output_root)
    packages = registry.setdefault("packages", {})

    if package_id in packages:
        packages[package_id]["current_state"] = state
        packages[package_id]["last_updated"] = _iso_now()

    write_registry(registry, output_root)
    return registry


# ═══════════════════════════════════════════════════════════
# SUPERSEDED 跨 package 传播
# ═══════════════════════════════════════════════════════════


def propagate_superseded(
    package_id: str,
    reason: str,
    verification_id: str | None = None,
    output_root: str | Path = DEFAULT_REGISTRY_DIR,
    _transition_fn: Callable[..., bool] | None = None,
    _visited: set | None = None,
) -> list[str]:
    """当 package 进入 SUPERSEDED 后，传播到所有下游 APPROVED package。

    传播规则：
      - 下游 APPROVED → 自动 SUPERSEDED（旧批准基于旧上游代码）
      - 下游 PENDING_REVIEW / REQUEST_CHANGES → 追加提醒 notes
      - 递归传播：下游的下游也受影响

    Args:
        package_id: 进入 SUPERSEDED 的 package ID
        reason: 传播原因（用于 decision_log）
        verification_id: 触发验证的 ID（可选）
        output_root: Review Package 输出根目录
        _transition_fn: transition_state 函数引用（避免循环导入）
        _visited: 已访问集合（防止无限递归）

    Returns:
        受影响的 package ID 列表（不含自身）
    """
    # 防止无限递归
    if _visited is None:
        _visited = set()
    if package_id in _visited:
        return []
    _visited.add(package_id)

    # 延迟导入避免循环依赖
    if _transition_fn is None:
        from .decision_manager import transition_state as _ts

        _transition_fn = _ts

    registry = read_registry(output_root)
    packages = registry.get("packages", {})

    # 确保当前 package 状态已在注册表中更新
    if package_id in packages:
        packages[package_id]["current_state"] = "SUPERSEDED"
        packages[package_id]["last_updated"] = _iso_now()

    downstream_ids = list(
        packages.get(package_id, {}).get("depended_by", [])
    )
    affected: list[str] = []

    for downstream_id in downstream_ids:
        if downstream_id not in packages:
            continue

        downstream = packages[downstream_id]
        downstream_path = Path(downstream["path"])
        current_state = downstream.get("current_state", "PENDING_REVIEW")

        if current_state == "APPROVED":
            # 自动 SUPERSEDED——旧批准基于过时上游代码
            try:
                _transition_fn(
                    downstream_path,
                    to_state="SUPERSEDED",
                    changed_by="agent",
                    reason=(
                        f"上游 {package_id} 已 SUPERSEDED——{reason}。"
                        f"本 package 的旧批准基于过时上游代码，自动过渡至 SUPERSEDED"
                    ),
                    verification_id=verification_id,
                    actor_id="agent",
                )
                packages[downstream_id]["current_state"] = "SUPERSEDED"
                packages[downstream_id]["last_updated"] = _iso_now()
                affected.append(downstream_id)

                # 递归传播到下游的下游
                sub_affected = propagate_superseded(
                    downstream_id,
                    reason=f"上游 {package_id} 传播",
                    verification_id=verification_id,
                    output_root=output_root,
                    _transition_fn=_transition_fn,
                    _visited=_visited,
                )
                affected.extend(sub_affected)

            except (ValueError, FileNotFoundError):
                # 传播失败不阻断主流程
                pass

        elif current_state in ("PENDING_REVIEW", "REQUEST_CHANGES"):
            # 非终态——追加提醒 notes，不自动转换状态
            try:
                _append_reminder_note(
                    downstream_path,
                    f"M4c 提醒：上游 {package_id} 已变更（{reason}），"
                    f"人审时请确认本 package 代码是否需要更新。",
                )
            except (ValueError, FileNotFoundError):
                pass

    write_registry(registry, output_root)
    return affected


def _append_reminder_note(package_dir: Path, note: str) -> None:
    """向 decision.yml 的 notes 字段追加提醒。

    Args:
        package_dir: Package 目录路径
        note: 提醒内容
    """
    from .decision_manager import read_decision, write_decision

    decision = read_decision(package_dir)
    notes = decision.setdefault("notes", [])
    if note not in notes:
        notes.append(note)
    decision["last_updated"] = _iso_now()
    write_decision(package_dir, decision)


# ═══════════════════════════════════════════════════════════
# 一致性检查
# ═══════════════════════════════════════════════════════════


def check_consistency(
    output_root: str | Path = DEFAULT_REGISTRY_DIR,
) -> dict[str, list[str]]:
    """检查注册表与实际 package 目录的一致性。

    Returns:
        dict，可能包含以下键：
          - orphaned_entries: 注册表有记录但目录已删除的 package
          - unregistered_dirs: 有目录但未注册的 package
          - state_mismatches: 注册表状态与 decision.yml 不一致的 package
    """
    registry = read_registry(output_root)
    packages = registry.get("packages", {})
    root = Path(output_root)

    result: dict[str, list[str]] = {
        "orphaned_entries": [],
        "unregistered_dirs": [],
        "state_mismatches": [],
    }

    # 检查注册表中有但目录已删除的（ORPHANED）
    for pkg_id, pkg in packages.items():
        pkg_path = Path(pkg.get("path", ""))
        if not pkg_path.is_dir():
            result["orphaned_entries"].append(
                f"{pkg_id}: 注册路径 {pkg_path} 不存在——目录可能已被删除"
            )

    # 检查有目录但未注册的
    if root.is_dir():
        for subdir in sorted(root.iterdir()):
            if not subdir.is_dir():
                continue
            if subdir.name.startswith("."):
                continue
            # 有 decision.yml 才是 review package
            if not (subdir / "decision.yml").is_file():
                continue
            if subdir.name not in packages:
                result["unregistered_dirs"].append(
                    f"{subdir.name}: 目录 {subdir} 存在但未在注册表中——"
                    f"可能是旧 package 或注册遗漏"
                )

    # 检查状态一致性（registry vs decision.yml）
    for pkg_id, pkg in packages.items():
        pkg_path = Path(pkg.get("path", ""))
        if not pkg_path.is_dir():
            continue
        decision_yml = pkg_path / "decision.yml"
        if not decision_yml.is_file():
            continue
        try:
            decision = (
                yaml.safe_load(decision_yml.read_text(encoding="utf-8")) or {}
            )
            registry_state = pkg.get("current_state", "?")
            decision_state = decision.get("current_state", "?")
            if registry_state != decision_state:
                result["state_mismatches"].append(
                    f"{pkg_id}: registry={registry_state}, "
                    f"decision.yml={decision_state}"
                )
        except Exception:
            pass

    return result


def check_for_stale_approvals(
    output_root: str | Path = DEFAULT_REGISTRY_DIR,
) -> list[dict[str, str]]:
    """检查是否有下游 package 的批准可能已过期。

    遍历注册表，对于每个 APPROVED package，检查其上游是否有异常状态。

    Returns:
        疑似过期的 package 列表，每项含 package_id、状态和原因。
    """
    registry = read_registry(output_root)
    packages = registry.get("packages", {})

    stale: list[dict[str, str]] = []

    for pkg_id, pkg in packages.items():
        if pkg.get("current_state") != "APPROVED":
            continue

        for dep_id in pkg.get("depends_on", []):
            if dep_id not in packages:
                continue
            dep_state = packages[dep_id].get("current_state", "")
            if dep_state == "SUPERSEDED":
                stale.append({
                    "package_id": pkg_id,
                    "state": "APPROVED",
                    "reason": (
                        f"上游 {dep_id} 已 SUPERSEDED——"
                        f"本 package 的批准可能基于过时的上游代码"
                    ),
                    "upstream": dep_id,
                })
            elif dep_state not in ("APPROVED", "PENDING_REVIEW"):
                stale.append({
                    "package_id": pkg_id,
                    "state": "APPROVED",
                    "reason": (
                        f"上游 {dep_id} 状态为 {dep_state}——"
                        f"上游变更可能影响本 package"
                    ),
                    "upstream": dep_id,
                })

    return stale
