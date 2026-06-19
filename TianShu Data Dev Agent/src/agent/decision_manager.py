"""
决策状态管理器——M4b 状态机核心。

负责 decision.yml / decision_log.yml 的读写、状态转换合法性校验、
artifact 哈希计算与完整性检查。

Agent 只能写入 PENDING_REVIEW 和 SUPERSEDED。
APPROVED / REQUEST_CHANGES / REJECTED 只能由人通过 CLI 设置。
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from src.ir.types import ArtifactHashes, DecisionStatus


# ═══════════════════════════════════════════════════════════
# 状态转换合法性表
# ═══════════════════════════════════════════════════════════

# 允许的 (from_state, to_state, changed_by) 组合
_ALLOWED_TRANSITIONS: set[tuple[Optional[str], str, str]] = {
    # M2 创建——Agent 初始写入
    (None, "PENDING_REVIEW", "agent"),
    # 人审决策——从 PENDING_REVIEW 出发
    ("PENDING_REVIEW", "APPROVED", "human"),
    ("PENDING_REVIEW", "REQUEST_CHANGES", "human"),
    ("PENDING_REVIEW", "REJECTED", "human"),
    # 人审决策——从 SUPERSEDED 出发（旧批准已失效，重新决策）
    ("SUPERSEDED", "APPROVED", "human"),
    ("SUPERSEDED", "REQUEST_CHANGES", "human"),
    ("SUPERSEDED", "REJECTED", "human"),
    # 人审决策——从 REJECTED 出发（允许重新决策）
    ("REJECTED", "APPROVED", "human"),
    ("REJECTED", "REQUEST_CHANGES", "human"),
    # M3 自动转换——Agent 触发 SUPERSEDED
    ("APPROVED", "SUPERSEDED", "agent"),
    # APPROVED 后重新验证→回到 PENDING_REVIEW（Agent 可触发）
    ("APPROVED", "PENDING_REVIEW", "agent"),
    ("SUPERSEDED", "PENDING_REVIEW", "agent"),
}

# 终态集合：这些状态一旦进入（且非 SUPERSEDED），不可再自动变更
# SUPERSEDED 不是终态——人可以重新决策
# REJECTED 不是终态——人可从 REJECTED 转为 APPROVED 或 REQUEST_CHANGES
TERMINAL_STATES: set[str] = set()


def _iso_now() -> str:
    """返回当前 UTC ISO8601 时间戳。"""
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════
# decision.yml 读写
# ═══════════════════════════════════════════════════════════


def read_decision(package_dir: Path) -> dict[str, Any]:
    """读取 decision.yml 并返回解析后的 dict。

    Args:
        package_dir: Review Package 目录路径

    Returns:
        decision.yml 的解析内容

    Raises:
        FileNotFoundError: decision.yml 不存在
    """
    decision_path = package_dir / "decision.yml"
    if not decision_path.is_file():
        raise FileNotFoundError(f"decision.yml 不存在: {decision_path}")
    return yaml.safe_load(decision_path.read_text(encoding="utf-8")) or {}


def write_decision(package_dir: Path, decision: dict[str, Any]) -> None:
    """原子写入 decision.yml（先写 .tmp 再 replace）。

    Args:
        package_dir: Review Package 目录路径
        decision: 待写入的决策数据
    """
    decision_path = package_dir / "decision.yml"
    tmp_path = decision_path.with_suffix(".tmp")
    tmp_path.write_text(
        yaml.safe_dump(decision, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    tmp_path.replace(decision_path)


# ═══════════════════════════════════════════════════════════
# decision_log.yml 读写
# ═══════════════════════════════════════════════════════════


def read_decision_log(package_dir: Path) -> dict[str, Any]:
    """读取 decision_log.yml 并返回解析后的 dict。

    Args:
        package_dir: Review Package 目录路径

    Returns:
        decision_log.yml 的解析内容（含 entries 列表）

    Raises:
        FileNotFoundError: decision_log.yml 不存在
    """
    log_path = package_dir / "decision_log.yml"
    if not log_path.is_file():
        raise FileNotFoundError(f"decision_log.yml 不存在: {log_path}")
    return yaml.safe_load(log_path.read_text(encoding="utf-8")) or {"entries": []}


def append_decision_log(package_dir: Path, entry: dict[str, Any]) -> None:
    """原子追加一条决策日志条目。

    只追加不覆盖——已有 entries 永久保留。
    先写 .tmp 再 replace 保证原子性。

    Args:
        package_dir: Review Package 目录路径
        entry: 日志条目 dict，必须含 timestamp/from_state/to_state/changed_by/reason
    """
    log_path = package_dir / "decision_log.yml"
    current = read_decision_log(package_dir)
    current.setdefault("entries", []).append(entry)
    tmp_path = log_path.with_suffix(".tmp")
    tmp_path.write_text(
        yaml.safe_dump(current, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    tmp_path.replace(log_path)


# ═══════════════════════════════════════════════════════════
# 状态转换
# ═══════════════════════════════════════════════════════════


def transition_state(
    package_dir: Path,
    to_state: str,
    changed_by: str,
    reason: str,
    *,
    verification_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    dry_run: bool = False,
) -> bool:
    """执行一次状态转换。

    校验合法性 → 更新 decision.yml → 追加 decision_log.yml。
    所有操作在同一个调用中原子执行（decision_log 追加失败不更新 decision.yml）。

    Args:
        package_dir: Review Package 目录路径
        to_state: 目标状态（DecisionStatus 值）
        changed_by: "agent" 或 "human"
        reason: 人读原因（≤200 字符）
        verification_id: 自动转换时填入验证标识（人操作为 None）
        actor_id: 操作者身份（"agent" 或 "human:<username>"）
        dry_run: 仅校验合法性，不实际写入

    Returns:
        True 表示已执行转换（或 dry_run 可通过）；False 表示无变更

    Raises:
        ValueError: 转换非法
    """
    # 校验目标状态
    valid_states = {s.value for s in DecisionStatus}
    if to_state not in valid_states:
        raise ValueError(
            f"无效的目标状态: {to_state}，有效值: {sorted(valid_states)}"
        )

    # 读取当前状态
    decision = read_decision(package_dir)
    from_state = decision.get("current_state")

    # 幂等：同状态不重复转换
    if from_state == to_state:
        return False

    # Agent 不能设置人审状态（在转换表校验之前检查，给出更明确的错误）
    human_only_states = {"APPROVED", "REQUEST_CHANGES", "REJECTED"}
    if changed_by == "agent" and to_state in human_only_states:
        raise ValueError(
            f"Agent 不能设置 {to_state}——该状态仅人能设置。"
            f"Agent 只能写入 PENDING_REVIEW 或 SUPERSEDED。"
        )

    # 校验合法性
    transition_key = (from_state, to_state, changed_by)
    if transition_key not in _ALLOWED_TRANSITIONS:
        raise ValueError(
            f"非法的状态转换: {from_state} → {to_state} (changed_by={changed_by})。"
            f"允许的转换: {sorted(str(t) for t in _ALLOWED_TRANSITIONS)}"
        )

    if dry_run:
        return True

    # 写入 decision_log（先写——如果失败则不更新 decision.yml）
    now_iso = _iso_now()
    log_entry = {
        "timestamp": now_iso,
        "from_state": from_state,
        "to_state": to_state,
        "changed_by": changed_by,
        "actor_id": actor_id or changed_by,
        "reason": reason[:200],  # 截断至 200 字符
    }
    if verification_id:
        log_entry["verification_id"] = verification_id

    append_decision_log(package_dir, log_entry)

    # 更新 decision.yml
    decision["current_state"] = to_state
    decision["last_updated"] = now_iso
    decision["last_updated_by"] = actor_id or changed_by
    write_decision(package_dir, decision)

    return True


# ═══════════════════════════════════════════════════════════
# artifact 哈希
# ═══════════════════════════════════════════════════════════


def _hash_file(path: Path) -> str:
    """计算文件的 SHA-256 哈希。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_artifact_hashes(package_dir: Path) -> ArtifactHashes:
    """计算 Review Package 中关键文件的 SHA-256 哈希。

    Args:
        package_dir: Review Package 目录路径

    Returns:
        ArtifactHashes，含 sql/spark/lineage 的哈希；verification_summary 在
        verification_summary.yml 存在时填充，否则为 None

    Raises:
        FileNotFoundError: sql/spark/lineage 任一文件缺失
    """
    sql_path = package_dir / "sql" / "main.sql"
    spark_path = package_dir / "spark" / "main.py"
    lineage_path = package_dir / "lineage" / "source_refs.yml"
    summary_path = package_dir / "reports" / "verification_summary.yml"
    # M5：部署产物也纳入哈希计算
    deploy_sql_path = package_dir / "deploy" / "main.sql"
    deploy_spark_path = package_dir / "deploy" / "main.py"
    deploy_manifest_path = package_dir / "deployment_manifest.yml"

    for required in [sql_path, spark_path, lineage_path]:
        if not required.is_file():
            raise FileNotFoundError(f"无法计算哈希——文件不存在: {required}")

    verification_summary_hash = None
    if summary_path.is_file():
        verification_summary_hash = _hash_file(summary_path)

    deploy_sql_hash = ""
    deploy_spark_hash = ""
    deploy_manifest_hash = ""
    if deploy_sql_path.is_file():
        deploy_sql_hash = _hash_file(deploy_sql_path)
    if deploy_spark_path.is_file():
        deploy_spark_hash = _hash_file(deploy_spark_path)
    if deploy_manifest_path.is_file():
        deploy_manifest_hash = _hash_file(deploy_manifest_path)

    return ArtifactHashes(
        sql_main=_hash_file(sql_path),
        spark_main=_hash_file(spark_path),
        lineage_source_refs=_hash_file(lineage_path),
        verification_summary=verification_summary_hash,
        deploy_sql=deploy_sql_hash,
        deploy_spark=deploy_spark_hash,
        deployment_manifest=deploy_manifest_hash,
    )


def check_artifact_integrity(
    package_dir: Path,
    stored_hashes: dict[str, Any],
) -> list[str]:
    """比对当前文件哈希与 decision.yml 中记录的哈希。

    Args:
        package_dir: Review Package 目录路径
        stored_hashes: decision.yml 中 artifact_hashes 的 dict

    Returns:
        警告列表——每项描述一个文件的不一致。空列表表示全部一致。
    """
    warnings: list[str] = []
    file_map = {
        "sql_main": "sql/main.sql",
        "spark_main": "spark/main.py",
        "lineage_source_refs": "lineage/source_refs.yml",
        # M5：部署产物也纳入完整性检查
        "deploy_sql": "deploy/main.sql",
        "deploy_spark": "deploy/main.py",
        "deployment_manifest": "deployment_manifest.yml",
    }

    for hash_key, rel_path in file_map.items():
        stored = stored_hashes.get(hash_key)
        if not stored:
            continue  # 无存储哈希，跳过（首次生成或旧格式）
        file_path = package_dir / rel_path
        if not file_path.is_file():
            warnings.append(
                f"artifact 完整性警告：{rel_path} 缺失，"
                f"decision.yml 记录了哈希 {stored[:12]}..."
            )
            continue
        current_hash = _hash_file(file_path)
        if current_hash != stored:
            warnings.append(
                f"artifact 完整性警告：{rel_path} 已被修改"
                f"（记录 {stored[:12]}...，当前 {current_hash[:12]}...）。"
                f"批准后修改代码会使旧批准失效。"
            )

    return warnings


def update_artifact_hashes_in_decision(
    package_dir: Path,
    hashes: ArtifactHashes,
) -> None:
    """将 artifact 哈希写入 decision.yml（不记录为状态变更）。

    仅更新 artifact_hashes 和 last_updated 字段，不追加 decision_log。
    用于 M2 首次写入或 M3 更新 verification_summary hash。

    Args:
        package_dir: Review Package 目录路径
        hashes: 待写入的 ArtifactHashes
    """
    decision = read_decision(package_dir)
    decision["artifact_hashes"] = hashes.to_dict()
    decision["last_updated"] = _iso_now()
    # 不追加 decision_log——这是数据更新，不是状态变更
    write_decision(package_dir, decision)
