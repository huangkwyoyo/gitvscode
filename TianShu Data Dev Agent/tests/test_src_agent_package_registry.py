"""
Package 注册表管理器测试——M4c。

覆盖：
  - 注册表读写（空注册表、读写、原子写入）
  - package 注册/注销/更新
  - 反向依赖维护
  - 依赖自动检测（lineage 语义匹配）
  - 依赖环检测
  - SUPERSEDED 传播（单下游、链式、菱形、非 APPROVED 跳过）
  - 一致性检查（ORPHANED、未注册、状态不匹配）
  - 过期批准检测
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.agent.decision_manager import (
    read_decision,
    transition_state,
)
from src.agent.package_registry import (
    _append_reminder_note,
    auto_detect_dependencies,
    check_consistency,
    check_for_stale_approvals,
    detect_dependency_cycle,
    get_dependency_tree,
    propagate_superseded,
    read_registry,
    register_package,
    unregister_package,
    update_registry_state,
    write_registry,
)


# ═══════════════════════════════════════════════════════════
# 注册表读写
# ═══════════════════════════════════════════════════════════


def test_read_empty_registry(tmp_path):
    """读取不存在的注册表返回空骨架。"""
    registry = read_registry(output_root=str(tmp_path))
    assert registry["registry_version"] == 1
    assert registry["packages"] == {}


def test_write_and_read_registry(tmp_path):
    """写入后读取注册表应一致。"""
    registry = {
        "registry_version": 1,
        "last_updated": "",
        "packages": {},
    }
    write_registry(registry, output_root=str(tmp_path))
    result = read_registry(output_root=str(tmp_path))
    assert result["registry_version"] == 1
    assert "last_updated" in result


def test_registry_atomic_write_leaves_no_tmp(tmp_path):
    """原子写入后不应残留 .tmp 文件。"""
    registry = {
        "registry_version": 1,
        "last_updated": "",
        "packages": {"test": {"current_state": "PENDING_REVIEW"}},
    }
    write_registry(registry, output_root=str(tmp_path))
    tmp_files = list(Path(tmp_path).glob("*.tmp"))
    assert len(tmp_files) == 0


# ═══════════════════════════════════════════════════════════
# package 注册 / 注销 / 更新
# ═══════════════════════════════════════════════════════════


def test_register_new_package(tmp_path):
    """注册新 package 应写入注册表。"""
    pkg_dir = tmp_path / "test_pkg_m2"
    pkg_dir.mkdir()
    register_package(
        "test_pkg_m2", pkg_dir,
        artifact_hashes={"sql_main": "abc123"},
        output_root=str(tmp_path),
    )
    registry = read_registry(output_root=str(tmp_path))
    assert "test_pkg_m2" in registry["packages"]
    pkg = registry["packages"]["test_pkg_m2"]
    assert pkg["current_state"] == "PENDING_REVIEW"
    assert pkg["artifact_hashes"]["sql_main"] == "abc123"
    assert pkg["depends_on"] == []
    assert pkg["depended_by"] == []


def test_register_package_preserves_existing(tmp_path):
    """注册新 package 不覆盖注册表中已有的其他 package。"""
    pkg_a = tmp_path / "pkg_a"
    pkg_a.mkdir()
    pkg_b = tmp_path / "pkg_b"
    pkg_b.mkdir()

    register_package("pkg_a", pkg_a, output_root=str(tmp_path))
    register_package("pkg_b", pkg_b, output_root=str(tmp_path))

    registry = read_registry(output_root=str(tmp_path))
    assert "pkg_a" in registry["packages"]
    assert "pkg_b" in registry["packages"]


def test_register_updates_existing(tmp_path):
    """重复注册同一个 package 应更新字段而非创建重复条目。"""
    pkg_dir = tmp_path / "test_pkg_m2"
    pkg_dir.mkdir()

    register_package("test_pkg_m2", pkg_dir, output_root=str(tmp_path))
    register_package(
        "test_pkg_m2", pkg_dir,
        artifact_hashes={"sql_main": "updated_hash"},
        output_root=str(tmp_path),
    )

    registry = read_registry(output_root=str(tmp_path))
    assert len(registry["packages"]) == 1
    pkg = registry["packages"]["test_pkg_m2"]
    assert pkg["artifact_hashes"]["sql_main"] == "updated_hash"


def test_unregister_package(tmp_path):
    """注销 package 应从注册表移除。"""
    pkg_dir = tmp_path / "test_pkg_m2"
    pkg_dir.mkdir()

    register_package("test_pkg_m2", pkg_dir, output_root=str(tmp_path))
    unregister_package("test_pkg_m2", output_root=str(tmp_path))

    registry = read_registry(output_root=str(tmp_path))
    assert "test_pkg_m2" not in registry["packages"]


def test_unregister_nonexistent_is_harmless(tmp_path):
    """注销不存在的 package 不报错。"""
    result = unregister_package("no_such_pkg", output_root=str(tmp_path))
    assert "no_such_pkg" not in result.get("packages", {})


# ═══════════════════════════════════════════════════════════
# 反向依赖维护
# ═══════════════════════════════════════════════════════════


def test_depended_by_maintained_on_register(tmp_path):
    """注册 package 时自动维护上游的 depended_by。"""
    pkg_a = tmp_path / "pkg_a"
    pkg_b = tmp_path / "pkg_b"
    pkg_a.mkdir()
    pkg_b.mkdir()

    register_package("pkg_a", pkg_a, output_root=str(tmp_path))
    register_package(
        "pkg_b", pkg_b,
        depends_on=["pkg_a"],
        output_root=str(tmp_path),
    )

    registry = read_registry(output_root=str(tmp_path))
    assert "pkg_b" in registry["packages"]["pkg_a"]["depended_by"]
    assert "pkg_a" in registry["packages"]["pkg_b"]["depends_on"]


def test_depended_by_cleaned_on_reregister(tmp_path):
    """重新注册时清理旧反向依赖再重建。"""
    pkg_a = tmp_path / "pkg_a"
    pkg_b = tmp_path / "pkg_b"
    pkg_c = tmp_path / "pkg_c"
    for d in [pkg_a, pkg_b, pkg_c]:
        d.mkdir()

    register_package("pkg_a", pkg_a, output_root=str(tmp_path))
    register_package("pkg_b", pkg_b, output_root=str(tmp_path))
    register_package("pkg_c", pkg_c, output_root=str(tmp_path))

    # B 初始依赖 A
    register_package("pkg_b", pkg_b, depends_on=["pkg_a"], output_root=str(tmp_path))
    assert "pkg_b" in read_registry(str(tmp_path))["packages"]["pkg_a"]["depended_by"]

    # B 改为依赖 C——应从 A 的 depended_by 移除并加入 C 的 depended_by
    register_package("pkg_b", pkg_b, depends_on=["pkg_c"], output_root=str(tmp_path))
    registry = read_registry(str(tmp_path))
    assert "pkg_b" not in registry["packages"]["pkg_a"]["depended_by"]
    assert "pkg_b" in registry["packages"]["pkg_c"]["depended_by"]


def test_unregister_cleans_depended_by(tmp_path):
    """注销 package 时清理上游的 depended_by。"""
    pkg_a = tmp_path / "pkg_a"
    pkg_b = tmp_path / "pkg_b"
    pkg_a.mkdir()
    pkg_b.mkdir()

    register_package("pkg_a", pkg_a, output_root=str(tmp_path))
    register_package("pkg_b", pkg_b, depends_on=["pkg_a"], output_root=str(tmp_path))

    unregister_package("pkg_b", output_root=str(tmp_path))

    registry = read_registry(str(tmp_path))
    assert "pkg_b" not in registry["packages"]["pkg_a"]["depended_by"]


# ═══════════════════════════════════════════════════════════
# 依赖自动检测
# ═══════════════════════════════════════════════════════════


def test_auto_detect_no_lineage(tmp_path):
    """无 lineage 文件时返回空列表。"""
    registry = read_registry(output_root=str(tmp_path))
    deps = auto_detect_dependencies(tmp_path, registry)
    assert deps == []


def test_auto_detect_matching_package(tmp_path):
    """lineage 中 source_table 名与已注册 package 匹配时自动检测。"""
    pkg_dir = tmp_path / "downstream_m2"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "lineage").mkdir(parents=True)

    # 注册一个上游 package
    register_package("trip_daily_report_m2", tmp_path / "upstream", output_root=str(tmp_path))

    # 下游 lineage 引用了上游的表
    lineage = {
        "source_tables": [
            {"name": "trip_daily_report_m2", "type": "gold"},
        ],
    }
    (pkg_dir / "lineage" / "source_refs.yml").write_text(
        yaml.safe_dump(lineage), encoding="utf-8",
    )

    registry = read_registry(output_root=str(tmp_path))
    deps = auto_detect_dependencies(pkg_dir, registry)
    assert "trip_daily_report_m2" in deps


def test_auto_detect_no_match(tmp_path):
    """lineage 中 source_table 不与任何已注册 package 匹配时返回空。"""
    pkg_dir = tmp_path / "test_m2"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "lineage").mkdir(parents=True)

    lineage = {
        "source_tables": [
            {"name": "gold.dws_daily_trip_summary", "type": "gold"},
        ],
    }
    (pkg_dir / "lineage" / "source_refs.yml").write_text(
        yaml.safe_dump(lineage), encoding="utf-8",
    )

    registry = read_registry(output_root=str(tmp_path))
    deps = auto_detect_dependencies(pkg_dir, registry)
    assert deps == []


# ═══════════════════════════════════════════════════════════
# 依赖环检测
# ═══════════════════════════════════════════════════════════


def test_no_cycle_empty_registry(tmp_path):
    """空注册表无环。"""
    registry = read_registry(output_root=str(tmp_path))
    assert detect_dependency_cycle(registry) == []


def test_no_cycle_linear_chain(tmp_path):
    """线性链（A→B→C）无环。"""
    for name in ["pkg_a", "pkg_b", "pkg_c"]:
        d = tmp_path / name
        d.mkdir()
    register_package("pkg_a", tmp_path / "pkg_a", output_root=str(tmp_path))
    register_package("pkg_b", tmp_path / "pkg_b", depends_on=["pkg_a"], output_root=str(tmp_path))
    register_package("pkg_c", tmp_path / "pkg_c", depends_on=["pkg_b"], output_root=str(tmp_path))

    registry = read_registry(str(tmp_path))
    assert detect_dependency_cycle(registry) == []


def test_detect_simple_cycle(tmp_path):
    """A→B→A 环被检测。"""
    for name in ["pkg_a", "pkg_b"]:
        d = tmp_path / name
        d.mkdir()
    register_package("pkg_a", tmp_path / "pkg_a", depends_on=["pkg_b"], output_root=str(tmp_path))
    register_package("pkg_b", tmp_path / "pkg_b", depends_on=["pkg_a"], output_root=str(tmp_path))

    registry = read_registry(str(tmp_path))
    cycles = detect_dependency_cycle(registry)
    assert len(cycles) > 0


def test_detect_self_loop(tmp_path):
    """自环（A→A）被检测。"""
    d = tmp_path / "pkg_a"
    d.mkdir()
    register_package("pkg_a", tmp_path / "pkg_a", depends_on=["pkg_a"], output_root=str(tmp_path))

    registry = read_registry(str(tmp_path))
    cycles = detect_dependency_cycle(registry)
    assert len(cycles) > 0


# ═══════════════════════════════════════════════════════════
# 状态同步
# ═══════════════════════════════════════════════════════════


def test_update_registry_state(tmp_path):
    """更新注册表中 package 状态。"""
    pkg_dir = tmp_path / "test_m2"
    pkg_dir.mkdir()
    register_package("test_m2", pkg_dir, output_root=str(tmp_path))

    update_registry_state("test_m2", "APPROVED", output_root=str(tmp_path))

    registry = read_registry(str(tmp_path))
    assert registry["packages"]["test_m2"]["current_state"] == "APPROVED"


def test_update_registry_state_nonexistent(tmp_path):
    """更新不存在的 package 不报错。"""
    update_registry_state("no_such_pkg", "APPROVED", output_root=str(tmp_path))
    registry = read_registry(str(tmp_path))
    assert "no_such_pkg" not in registry["packages"]


# ═══════════════════════════════════════════════════════════
# SUPERSEDED 传播
# ═══════════════════════════════════════════════════════════


def _setup_package_with_decision(
    tmp_path: Path,
    pkg_id: str,
    state: str = "PENDING_REVIEW",
) -> Path:
    """创建一个含 decision.yml 的最小 package 目录。"""
    pkg_dir = tmp_path / pkg_id
    pkg_dir.mkdir(parents=True)
    for sub in ["sql", "spark", "lineage", "reports", "tests"]:
        (pkg_dir / sub).mkdir(exist_ok=True)
    # 写最小文件
    (pkg_dir / "sql" / "main.sql").write_text("SELECT 1", encoding="utf-8")
    (pkg_dir / "spark" / "main.py").write_text("print(1)", encoding="utf-8")
    (pkg_dir / "lineage" / "source_refs.yml").write_text(
        yaml.safe_dump({"source_tables": [{"name": "test"}]}), encoding="utf-8",
    )
    (pkg_dir / "reports" / "verification_summary.yml").write_text(
        yaml.safe_dump({"overall_status": "PASS"}), encoding="utf-8",
    )
    # 写 decision.yml
    decision = {
        "request_id": pkg_id,
        "current_state": state,
        "human_review_required": True,
        "last_updated": "2026-06-18T00:00:00Z",
        "last_updated_by": "agent",
        "verification_overall_status": "PASS",
        "human_decision_note": "",
        "artifact_hashes": {},
    }
    (pkg_dir / "decision.yml").write_text(
        yaml.safe_dump(decision, allow_unicode=True), encoding="utf-8",
    )
    # 写 decision_log.yml
    log = {
        "request_id": pkg_id,
        "entries": [{
            "timestamp": "2026-06-18T00:00:00Z",
            "from_state": None,
            "to_state": state,
            "changed_by": "agent",
            "actor_id": "agent",
            "reason": "创建",
        }],
    }
    (pkg_dir / "decision_log.yml").write_text(
        yaml.safe_dump(log, allow_unicode=True), encoding="utf-8",
    )
    return pkg_dir


def test_propagate_superseded_single_approved_downstream(tmp_path):
    """单一下游 APPROVED 应被自动 SUPERSEDED。"""
    upstream_dir = _setup_package_with_decision(tmp_path, "upstream", "APPROVED")
    downstream_dir = _setup_package_with_decision(tmp_path, "downstream", "APPROVED")

    # 注册并建立依赖
    register_package("upstream", upstream_dir, output_root=str(tmp_path))
    register_package(
        "downstream", downstream_dir,
        depends_on=["upstream"],
        output_root=str(tmp_path),
    )

    affected = propagate_superseded(
        "upstream",
        reason="测试传播",
        output_root=str(tmp_path),
        _transition_fn=transition_state,
    )

    assert "downstream" in affected
    # 下游状态应变为 SUPERSEDED
    downstream_decision = read_decision(downstream_dir)
    assert downstream_decision["current_state"] == "SUPERSEDED"


def test_propagate_superseded_chain(tmp_path):
    """链式传播（A→B→C，A SUPERSEDED 应传递到 C）。"""
    a_dir = _setup_package_with_decision(tmp_path, "pkg_a", "APPROVED")
    b_dir = _setup_package_with_decision(tmp_path, "pkg_b", "APPROVED")
    c_dir = _setup_package_with_decision(tmp_path, "pkg_c", "APPROVED")

    register_package("pkg_a", a_dir, output_root=str(tmp_path))
    register_package("pkg_b", b_dir, depends_on=["pkg_a"], output_root=str(tmp_path))
    register_package("pkg_c", c_dir, depends_on=["pkg_b"], output_root=str(tmp_path))

    affected = propagate_superseded(
        "pkg_a",
        reason="链式测试",
        output_root=str(tmp_path),
        _transition_fn=transition_state,
    )

    assert "pkg_b" in affected
    assert "pkg_c" in affected
    assert read_decision(c_dir)["current_state"] == "SUPERSEDED"


def test_propagate_skips_non_approved_downstream(tmp_path):
    """PENDING_REVIEW 下游不应被 SUPERSEDED，但应追加提醒。"""
    upstream_dir = _setup_package_with_decision(tmp_path, "upstream", "APPROVED")
    downstream_dir = _setup_package_with_decision(tmp_path, "downstream", "PENDING_REVIEW")

    register_package("upstream", upstream_dir, output_root=str(tmp_path))
    register_package(
        "downstream", downstream_dir,
        depends_on=["upstream"],
        output_root=str(tmp_path),
    )

    affected = propagate_superseded(
        "upstream",
        reason="测试跳过",
        output_root=str(tmp_path),
        _transition_fn=transition_state,
    )

    # PENDING_REVIEW 不应被自动转换
    assert "downstream" not in affected
    decision = read_decision(downstream_dir)
    assert decision["current_state"] == "PENDING_REVIEW"
    # 应有提醒 notes
    notes = decision.get("notes", [])
    assert any("上游" in n for n in notes)


def test_propagate_no_downstream_is_harmless(tmp_path):
    """无下游时传播不报错。"""
    pkg_dir = _setup_package_with_decision(tmp_path, "solo", "APPROVED")
    register_package("solo", pkg_dir, output_root=str(tmp_path))

    affected = propagate_superseded(
        "solo",
        reason="无下游",
        output_root=str(tmp_path),
        _transition_fn=transition_state,
    )
    assert affected == []


def test_propagate_diamond_dependency(tmp_path):
    """菱形依赖（B,C ← A; D ← B,C）——A SUPERSEDED 应传播到全部下游。"""
    a_dir = _setup_package_with_decision(tmp_path, "pkg_a", "APPROVED")
    b_dir = _setup_package_with_decision(tmp_path, "pkg_b", "APPROVED")
    c_dir = _setup_package_with_decision(tmp_path, "pkg_c", "APPROVED")
    d_dir = _setup_package_with_decision(tmp_path, "pkg_d", "APPROVED")

    register_package("pkg_a", a_dir, output_root=str(tmp_path))
    register_package("pkg_b", b_dir, depends_on=["pkg_a"], output_root=str(tmp_path))
    register_package("pkg_c", c_dir, depends_on=["pkg_a"], output_root=str(tmp_path))
    register_package("pkg_d", d_dir, depends_on=["pkg_b", "pkg_c"], output_root=str(tmp_path))

    affected = propagate_superseded(
        "pkg_a",
        reason="菱形测试",
        output_root=str(tmp_path),
        _transition_fn=transition_state,
    )

    assert "pkg_b" in affected
    assert "pkg_c" in affected
    # D 应通过 B 的链式传播被影响
    assert "pkg_d" in affected


def test_propagate_preserves_decision_log(tmp_path):
    """传播 SUPERSEDED 应追加 decision_log 条目。"""
    upstream_dir = _setup_package_with_decision(tmp_path, "upstream", "APPROVED")
    downstream_dir = _setup_package_with_decision(tmp_path, "downstream", "APPROVED")

    register_package("upstream", upstream_dir, output_root=str(tmp_path))
    register_package(
        "downstream", downstream_dir,
        depends_on=["upstream"],
        output_root=str(tmp_path),
    )

    propagate_superseded(
        "upstream",
        reason="日志测试",
        output_root=str(tmp_path),
        _transition_fn=transition_state,
    )

    # 下游 decision_log 应有 2 条以上记录
    log_path = downstream_dir / "decision_log.yml"
    log = yaml.safe_load(log_path.read_text(encoding="utf-8"))
    assert len(log["entries"]) >= 2
    assert any(
        e["to_state"] == "SUPERSEDED" and "agent" in str(e.get("actor_id", ""))
        for e in log["entries"]
    )


# ═══════════════════════════════════════════════════════════
# 提醒 notes
# ═══════════════════════════════════════════════════════════


def test_reminder_note_appended(tmp_path):
    """提醒 notes 应追加到 decision.yml。"""
    pkg_dir = _setup_package_with_decision(tmp_path, "test_m2", "PENDING_REVIEW")
    _append_reminder_note(pkg_dir, "M4c 测试提醒")
    decision = read_decision(pkg_dir)
    assert "M4c 测试提醒" in decision.get("notes", [])


def test_reminder_note_deduplicated(tmp_path):
    """重复提醒不应追加。"""
    pkg_dir = _setup_package_with_decision(tmp_path, "test_m2", "PENDING_REVIEW")
    _append_reminder_note(pkg_dir, "M4c 测试提醒")
    _append_reminder_note(pkg_dir, "M4c 测试提醒")
    decision = read_decision(pkg_dir)
    # 应只有一个
    assert decision["notes"].count("M4c 测试提醒") == 1


# ═══════════════════════════════════════════════════════════
# 一致性检查
# ═══════════════════════════════════════════════════════════


def test_consistency_all_ok(tmp_path):
    """完全一致的注册表不报问题。"""
    pkg_dir = _setup_package_with_decision(tmp_path, "test_m2", "APPROVED")
    register_package("test_m2", pkg_dir, output_root=str(tmp_path))

    result = check_consistency(output_root=str(tmp_path))
    assert result["orphaned_entries"] == []
    assert result["unregistered_dirs"] == []
    # 注册时已知状态一致
    assert "test_m2" not in str(result["state_mismatches"])


def test_consistency_detects_orphaned(tmp_path):
    """注册表中记录但目录已删除→ORPHANED。"""
    pkg_dir = _setup_package_with_decision(tmp_path, "test_m2", "APPROVED")
    register_package("test_m2", pkg_dir, output_root=str(tmp_path))

    # 删除目录
    import shutil
    shutil.rmtree(pkg_dir)

    result = check_consistency(output_root=str(tmp_path))
    assert len(result["orphaned_entries"]) >= 1
    assert any("test_m2" in entry for entry in result["orphaned_entries"])


def test_consistency_detects_unregistered(tmp_path):
    """有目录但未注册→未注册。"""
    pkg_dir = _setup_package_with_decision(tmp_path, "test_m2", "APPROVED")
    # 不注册

    result = check_consistency(output_root=str(tmp_path))
    assert len(result["unregistered_dirs"]) >= 1
    assert any("test_m2" in entry for entry in result["unregistered_dirs"])


def test_consistency_detects_state_mismatch(tmp_path):
    """注册表状态与 decision.yml 不一致时应检测。"""
    pkg_dir = _setup_package_with_decision(tmp_path, "test_m2", "APPROVED")
    # 注册为不同状态
    register_package("test_m2", pkg_dir, output_root=str(tmp_path))
    # 手动改注册表状态
    registry = read_registry(str(tmp_path))
    registry["packages"]["test_m2"]["current_state"] = "SUPERSEDED"
    write_registry(registry, str(tmp_path))

    result = check_consistency(output_root=str(tmp_path))
    assert len(result["state_mismatches"]) >= 1
    assert any("test_m2" in m for m in result["state_mismatches"])


# ═══════════════════════════════════════════════════════════
# 过期批准检测
# ═══════════════════════════════════════════════════════════


def test_stale_approval_detected(tmp_path):
    """下游 APPROVED 但上游 SUPERSEDED 应被检测。"""
    upstream_dir = _setup_package_with_decision(tmp_path, "upstream", "SUPERSEDED")
    downstream_dir = _setup_package_with_decision(tmp_path, "downstream", "APPROVED")

    register_package("upstream", upstream_dir, output_root=str(tmp_path))
    register_package(
        "downstream", downstream_dir,
        depends_on=["upstream"],
        output_root=str(tmp_path),
    )

    stale = check_for_stale_approvals(output_root=str(tmp_path))
    assert len(stale) >= 1
    assert stale[0]["package_id"] == "downstream"
    assert "SUPERSEDED" in stale[0]["reason"]


def test_stale_approval_not_triggered_for_stable_upstream(tmp_path):
    """上游 APPROVED 的下游不报过期。"""
    upstream_dir = _setup_package_with_decision(tmp_path, "upstream", "APPROVED")
    downstream_dir = _setup_package_with_decision(tmp_path, "downstream", "APPROVED")

    register_package("upstream", upstream_dir, output_root=str(tmp_path))
    register_package(
        "downstream", downstream_dir,
        depends_on=["upstream"],
        output_root=str(tmp_path),
    )

    stale = check_for_stale_approvals(output_root=str(tmp_path))
    assert len(stale) == 0


def test_stale_approval_empty_registry(tmp_path):
    """空注册表无过期项。"""
    assert check_for_stale_approvals(output_root=str(tmp_path)) == []


# ═══════════════════════════════════════════════════════════
# 依赖树
# ═══════════════════════════════════════════════════════════


def test_dependency_tree(tmp_path):
    """依赖树包含上下游信息。"""
    a_dir = _setup_package_with_decision(tmp_path, "pkg_a", "APPROVED")
    b_dir = _setup_package_with_decision(tmp_path, "pkg_b", "APPROVED")

    register_package("pkg_a", a_dir, output_root=str(tmp_path))
    register_package("pkg_b", b_dir, depends_on=["pkg_a"], output_root=str(tmp_path))

    registry = read_registry(str(tmp_path))
    tree = get_dependency_tree("pkg_a", registry)
    assert tree["package_id"] == "pkg_a"
    assert len(tree.get("depended_by", [])) >= 1


def test_dependency_tree_nonexistent(tmp_path):
    """不存在的 package 返回空 dict。"""
    registry = read_registry(str(tmp_path))
    assert get_dependency_tree("no_such", registry) == {}
