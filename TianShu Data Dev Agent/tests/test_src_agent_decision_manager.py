"""
决策状态管理器直接单元测试——M4b。

覆盖 decision_manager.py 的所有路径：
- decision.yml 读写
- decision_log.yml 追加（保留历史）
- 状态转换合法性
- artifact 哈希计算与完整性检查
- 原子写入
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from src.agent.decision_manager import (
    _ALLOWED_TRANSITIONS,
    append_decision_log,
    check_artifact_integrity,
    compute_artifact_hashes,
    read_decision,
    read_decision_log,
    transition_state,
    update_artifact_hashes_in_decision,
    write_decision,
)
from src.ir.types import ArtifactHashes


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
BUILD_CLI = PROJECT_ROOT / "scripts" / "dev_agent" / "build_review_package.py"


def _build_package(tmp_path: Path) -> Path:
    """先生成 M2 Review Package。"""
    result = subprocess.run(
        [
            sys.executable,
            str(BUILD_CLI),
            "-r",
            str(FIXTURE),
            "--output-root",
            str(tmp_path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return tmp_path / "trip_daily_report_m2"


# ═══════════════════════════════════════════════════════════
# decision.yml 基本读写
# ═══════════════════════════════════════════════════════════


def test_read_decision_returns_dict(tmp_path):
    """正常读取 decision.yml 返回 dict。"""
    package_dir = _build_package(tmp_path)
    decision = read_decision(package_dir)
    assert isinstance(decision, dict)
    assert "request_id" in decision
    assert "current_state" in decision


def test_read_decision_missing_file_raises(tmp_path):
    """文件缺失时抛出 FileNotFoundError。"""
    package_dir = _build_package(tmp_path)
    (package_dir / "decision.yml").unlink()
    with pytest.raises(FileNotFoundError, match="decision.yml"):
        read_decision(package_dir)


def test_write_decision_persists(tmp_path):
    """写入 decision.yml 后可正确读回。"""
    package_dir = _build_package(tmp_path)
    decision = read_decision(package_dir)
    decision["current_state"] = "APPROVED"
    write_decision(package_dir, decision)
    reloaded = read_decision(package_dir)
    assert reloaded["current_state"] == "APPROVED"


# ═══════════════════════════════════════════════════════════
# decision_log.yml 追加
# ═══════════════════════════════════════════════════════════


def test_read_decision_log_returns_entries(tmp_path):
    """decision_log.yml 必须包含 entries 列表。"""
    package_dir = _build_package(tmp_path)
    log = read_decision_log(package_dir)
    assert "entries" in log
    assert len(log["entries"]) == 1  # 仅创建条目


def test_append_decision_log_preserves_history(tmp_path):
    """追加条目时已有条目全部保留。"""
    package_dir = _build_package(tmp_path)
    original = read_decision_log(package_dir)
    assert len(original["entries"]) == 1

    append_decision_log(package_dir, {
        "timestamp": "2026-06-18T12:00:00+00:00",
        "from_state": "PENDING_REVIEW",
        "to_state": "APPROVED",
        "changed_by": "human",
        "actor_id": "human:test",
        "reason": "测试批准",
    })
    append_decision_log(package_dir, {
        "timestamp": "2026-06-18T13:00:00+00:00",
        "from_state": "APPROVED",
        "to_state": "SUPERSEDED",
        "changed_by": "agent",
        "actor_id": "agent",
        "reason": "自动过期",
        "verification_id": "verify_test_001",
    })

    updated = read_decision_log(package_dir)
    assert len(updated["entries"]) == 3  # 1 原始 + 2 新增
    assert updated["entries"][1]["to_state"] == "APPROVED"
    assert updated["entries"][2]["to_state"] == "SUPERSEDED"


def test_read_decision_log_missing_file_raises(tmp_path):
    """decision_log.yml 缺失时抛出 FileNotFoundError。"""
    package_dir = _build_package(tmp_path)
    (package_dir / "decision_log.yml").unlink()
    with pytest.raises(FileNotFoundError, match="decision_log.yml"):
        read_decision_log(package_dir)


# ═══════════════════════════════════════════════════════════
# 状态转换
# ═══════════════════════════════════════════════════════════


def test_transition_pending_to_approved(tmp_path):
    """PENDING_REVIEW → APPROVED（人审通过）正常转换。"""
    package_dir = _build_package(tmp_path)
    changed = transition_state(
        package_dir,
        to_state="APPROVED",
        changed_by="human",
        reason="业务口径确认无误",
        actor_id="human:test_user",
    )
    assert changed is True
    decision = read_decision(package_dir)
    assert decision["current_state"] == "APPROVED"

    log = read_decision_log(package_dir)
    assert len(log["entries"]) == 2
    assert log["entries"][1]["to_state"] == "APPROVED"
    assert log["entries"][1]["actor_id"] == "human:test_user"


def test_transition_pending_to_request_changes(tmp_path):
    """PENDING_REVIEW → REQUEST_CHANGES 正常转换。"""
    package_dir = _build_package(tmp_path)
    transition_state(
        package_dir,
        to_state="REQUEST_CHANGES",
        changed_by="human",
        reason="SQL 需修复表引用",
        actor_id="human:reviewer",
    )
    assert read_decision(package_dir)["current_state"] == "REQUEST_CHANGES"


def test_transition_pending_to_rejected(tmp_path):
    """PENDING_REVIEW → REJECTED 正常转换。"""
    package_dir = _build_package(tmp_path)
    transition_state(
        package_dir,
        to_state="REJECTED",
        changed_by="human",
        reason="指标口径不匹配",
        actor_id="human:reviewer",
    )
    assert read_decision(package_dir)["current_state"] == "REJECTED"


def test_transition_rejected_to_approved(tmp_path):
    """REJECTED → APPROVED：REJECTED 不是终态，人可重新批准。"""
    package_dir = _build_package(tmp_path)
    transition_state(
        package_dir,
        to_state="REJECTED",
        changed_by="human",
        reason="初始拒绝",
        actor_id="human:reviewer",
    )
    transition_state(
        package_dir,
        to_state="APPROVED",
        changed_by="human",
        reason="修复后重新审查通过",
        actor_id="human:reviewer",
    )
    assert read_decision(package_dir)["current_state"] == "APPROVED"


def test_transition_approved_to_superseded_by_agent(tmp_path):
    """APPROVED → SUPERSEDED：Agent 可自动触发。"""
    package_dir = _build_package(tmp_path)
    # 先让人批准
    transition_state(
        package_dir,
        to_state="APPROVED",
        changed_by="human",
        reason="初始批准",
        actor_id="human:reviewer",
    )
    # Agent 触发 SUPERSEDED
    changed = transition_state(
        package_dir,
        to_state="SUPERSEDED",
        changed_by="agent",
        reason="重新验证检测到旧批准已过期",
        verification_id="verify_test_002",
        actor_id="agent",
    )
    assert changed is True
    assert read_decision(package_dir)["current_state"] == "SUPERSEDED"

    log = read_decision_log(package_dir)
    assert len(log["entries"]) == 3
    assert log["entries"][2]["to_state"] == "SUPERSEDED"
    assert log["entries"][2]["verification_id"] == "verify_test_002"


def test_transition_superseded_idempotent(tmp_path):
    """SUPERSEDED → SUPERSEDED 幂等，不写入变更。"""
    package_dir = _build_package(tmp_path)
    # 先批准再 SUPERSEDED
    transition_state(package_dir, to_state="APPROVED", changed_by="human", reason="批准", actor_id="human:t")
    transition_state(package_dir, to_state="SUPERSEDED", changed_by="agent", reason="过期", actor_id="agent")

    # 再次 SUPERSEDED 应返回 False（幂等）
    changed = transition_state(
        package_dir,
        to_state="SUPERSEDED",
        changed_by="agent",
        reason="重复触发",
        actor_id="agent",
    )
    assert changed is False
    # 日志不增长（第二次未写入）
    assert len(read_decision_log(package_dir)["entries"]) == 3  # 创建 + 批准 + SUPERSEDED


def test_agent_cannot_set_approved(tmp_path):
    """Agent 绝对不能设置 APPROVED。"""
    package_dir = _build_package(tmp_path)
    with pytest.raises(ValueError, match="Agent 不能设置 APPROVED"):
        transition_state(
            package_dir,
            to_state="APPROVED",
            changed_by="agent",
            reason="不应该成功",
            actor_id="agent",
        )


def test_agent_cannot_set_request_changes(tmp_path):
    """Agent 绝对不能设置 REQUEST_CHANGES。"""
    package_dir = _build_package(tmp_path)
    with pytest.raises(ValueError, match="Agent 不能设置 REQUEST_CHANGES"):
        transition_state(
            package_dir,
            to_state="REQUEST_CHANGES",
            changed_by="agent",
            reason="不应该成功",
            actor_id="agent",
        )


def test_agent_cannot_set_rejected(tmp_path):
    """Agent 绝对不能设置 REJECTED。"""
    package_dir = _build_package(tmp_path)
    with pytest.raises(ValueError, match="Agent 不能设置 REJECTED"):
        transition_state(
            package_dir,
            to_state="REJECTED",
            changed_by="agent",
            reason="不应该成功",
            actor_id="agent",
        )


def test_transition_invalid_state_raises(tmp_path):
    """无效的目标状态抛出 ValueError。"""
    package_dir = _build_package(tmp_path)
    with pytest.raises(ValueError, match="无效的目标状态"):
        transition_state(
            package_dir,
            to_state="INVALID_STATE",
            changed_by="human",
            reason="test",
        )


def test_transition_illegal_combination_raises(tmp_path):
    """非法的 (from, to, changed_by) 组合抛出 ValueError。"""
    package_dir = _build_package(tmp_path)
    # 先批准
    transition_state(package_dir, to_state="APPROVED", changed_by="human", reason="批准", actor_id="human:t")
    # 人不能直接把 APPROVED 改成 REJECTED（不走 SUPERSEDED）
    # 实际上这个在 _ALLOWED_TRANSITIONS 中是否允许取决于设计
    # 当前 APPROVED → REJECTED (human) 不在允许列表中
    with pytest.raises(ValueError, match="非法的状态转换"):
        transition_state(
            package_dir,
            to_state="REJECTED",
            changed_by="human",
            reason="直接拒绝已批准的",
        )


# ═══════════════════════════════════════════════════════════
# artifact 哈希
# ═══════════════════════════════════════════════════════════


def test_compute_artifact_hashes_all_present(tmp_path):
    """正常计算 sql/spark/lineage 的哈希，verification_summary 为 None（M2 阶段）。"""
    package_dir = _build_package(tmp_path)
    hashes = compute_artifact_hashes(package_dir)

    assert isinstance(hashes, ArtifactHashes)
    assert len(hashes.sql_main) == 64  # SHA-256
    assert len(hashes.spark_main) == 64
    assert len(hashes.lineage_source_refs) == 64
    # M2 阶段 verification_summary.yml 尚未生成
    assert hashes.verification_summary is None


def test_compute_artifact_hashes_missing_file_raises(tmp_path):
    """缺少必备文件时抛出 FileNotFoundError。"""
    package_dir = _build_package(tmp_path)
    (package_dir / "sql" / "main.sql").unlink()
    with pytest.raises(FileNotFoundError, match="main.sql"):
        compute_artifact_hashes(package_dir)


def test_hash_deterministic(tmp_path):
    """同一文件多次计算哈希结果一致。"""
    package_dir = _build_package(tmp_path)
    h1 = compute_artifact_hashes(package_dir)
    h2 = compute_artifact_hashes(package_dir)
    assert h1.sql_main == h2.sql_main
    assert h1.spark_main == h2.spark_main
    assert h1.lineage_source_refs == h2.lineage_source_refs


def test_hash_changes_on_content_change(tmp_path):
    """文件内容改变后哈希不同。"""
    package_dir = _build_package(tmp_path)
    h1 = compute_artifact_hashes(package_dir)
    # 修改 sql
    (package_dir / "sql" / "main.sql").write_text(
        (package_dir / "sql" / "main.sql").read_text(encoding="utf-8") + "\n-- modified\n",
        encoding="utf-8",
    )
    h2 = compute_artifact_hashes(package_dir)
    assert h1.sql_main != h2.sql_main


# ═══════════════════════════════════════════════════════════
# artifact 完整性检查
# ═══════════════════════════════════════════════════════════


def test_check_artifact_integrity_all_match(tmp_path):
    """未修改文件时返回空警告列表。"""
    package_dir = _build_package(tmp_path)
    hashes = compute_artifact_hashes(package_dir)
    warnings = check_artifact_integrity(package_dir, hashes.to_dict())
    assert warnings == []


def test_check_artifact_integrity_detects_change(tmp_path):
    """修改 sql/main.sql 后检测到差异。"""
    package_dir = _build_package(tmp_path)
    stored = compute_artifact_hashes(package_dir).to_dict()
    # 修改文件
    (package_dir / "sql" / "main.sql").write_text("SELECT 1;\n", encoding="utf-8")
    warnings = check_artifact_integrity(package_dir, stored)
    assert len(warnings) == 1
    assert "sql/main.sql" in warnings[0]
    assert "已被修改" in warnings[0]


def test_check_artifact_integrity_missing_file_warns(tmp_path):
    """文件被删除时产生警告。"""
    package_dir = _build_package(tmp_path)
    stored = compute_artifact_hashes(package_dir).to_dict()
    (package_dir / "sql" / "main.sql").unlink()
    warnings = check_artifact_integrity(package_dir, stored)
    assert any("sql/main.sql" in w and "缺失" in w for w in warnings)


def test_check_artifact_integrity_empty_stored_hashes(tmp_path):
    """无存储哈希时跳过检查（旧格式兼容）。"""
    package_dir = _build_package(tmp_path)
    warnings = check_artifact_integrity(package_dir, {})
    assert warnings == []


# ═══════════════════════════════════════════════════════════
# update_artifact_hashes_in_decision
# ═══════════════════════════════════════════════════════════


def test_update_artifact_hashes_persists(tmp_path):
    """更新 artifact_hashes 后 decision.yml 反映变更。"""
    package_dir = _build_package(tmp_path)
    # 先创建 verification_summary.yml 使其存在
    summary_path = package_dir / "reports" / "verification_summary.yml"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("overall_status: PASS\n", encoding="utf-8")

    hashes = compute_artifact_hashes(package_dir)
    assert hashes.verification_summary is not None  # 文件存在后应有哈希
    update_artifact_hashes_in_decision(package_dir, hashes)
    decision = read_decision(package_dir)
    assert decision["artifact_hashes"]["verification_summary"] is not None


# ═══════════════════════════════════════════════════════════
# 允许的转换表完整性
# ═══════════════════════════════════════════════════════════


def test_allowed_transitions_contains_creation():
    """允许的转换表包含创建事件。"""
    assert (None, "PENDING_REVIEW", "agent") in _ALLOWED_TRANSITIONS


def test_allowed_transitions_contains_human_decisions():
    """允许的转换表包含三种人审决策。"""
    assert ("PENDING_REVIEW", "APPROVED", "human") in _ALLOWED_TRANSITIONS
    assert ("PENDING_REVIEW", "REQUEST_CHANGES", "human") in _ALLOWED_TRANSITIONS
    assert ("PENDING_REVIEW", "REJECTED", "human") in _ALLOWED_TRANSITIONS


def test_allowed_transitions_contains_superseded():
    """允许的转换表包含 SUPERSEDED 自动转换。"""
    assert ("APPROVED", "SUPERSEDED", "agent") in _ALLOWED_TRANSITIONS


def test_allowed_transitions_no_direct_approve_by_agent():
    """允许的转换表中不存在 Agent 直接 APPROVED 的条目。"""
    assert ("PENDING_REVIEW", "APPROVED", "agent") not in _ALLOWED_TRANSITIONS
