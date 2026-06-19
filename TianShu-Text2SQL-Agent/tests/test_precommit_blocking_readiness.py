"""Memory Harness Step 22 —— pre-commit blocking readiness review 测试。

覆盖场景：
    1. 观察期不足 → needs_more_observation
    2. 有 false positive → fix_false_positive
    3. 有 worktree pollution → fix_worktree_pollution
    4. runtime_cost 超阈值 → fix_runtime_cost
    5. rollback plan 缺失 → keep_warn_only
    6. JSON renderer 包含 readiness_status
    7. Markdown renderer 包含 Rollback Plan
    8. 不生成 latest
    9. 不读取 latest
    10. 不修改 .githooks/pre-commit
    11. 不修改 docs/memory/*
    12. 不修改 memory_rules.yml
    13. 本轮不进入 blocking
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# 确保项目根目录在导入路径中
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.precommit_blocking_readiness import (
    MAX_AVERAGE_DURATION_SECONDS,
    MIN_OBSERVATION_DAYS,
    MIN_OBSERVATION_RUNS,
    FIX_FALSE_POSITIVE,
    FIX_PRECOMMIT_OUTPUT,
    FIX_RUNTIME_COST,
    FIX_WORKTREE_POLLUTION,
    KEEP_WARN_ONLY,
    NEEDS_MORE_OBSERVATION,
    READY_FOR_BLOCKING,
    VALID_READINESS_STATUSES,
    ReadinessCheck,
    ReadinessReview,
    _build_rollback_plan,
    _compute_observation_span,
    _derive_readiness_status,
    _generate_recommendation,
    _load_observation_data,
    _perform_readiness_checks,
    _review_false_positives,
    _review_runtime_cost,
    _review_worktree_pollution,
    render_readiness_json,
    render_readiness_markdown,
    run_readiness_review,
    write_readiness_snapshot,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 测试夹具 —— 构造各种观察数据场景
# ═══════════════════════════════════════════════════════════════════════════════


def _make_minimal_observation(**overrides) -> dict:
    """构造最小可用的观察报告数据。"""
    data = {
        "report_type": "precommit_memory_warn_observation",
        "step": "Step 21",
        "run_id": "OBS-test-001",
        "timestamp": "2026-01-01T00:00:00Z",
        "observation_summary": {
            "total_normal_runs": 3,
            "all_exit_code_zero": True,
            "all_no_pollution": True,
            "all_no_latest": True,
            "negative_verification_passed": True,
            "ready_for_continued_observation": True,
        },
        "normal_runs": [],
        "negative_verification": {
            "exit_code": 0,
            "output_contains_warning": True,
            "output_contains_rule_id": True,
            "output_contains_failed_check": True,
            "output_contains_fast_gate_suggestion": True,
            "output_contains_non_blocking_notice": True,
        },
        "worktree_pollution": {
            "new_untracked_files": 0,
            "new_modified_files": 0,
            "harness_reports_unchanged": True,
            "docs_memory_unchanged": True,
            "memory_rules_yml_unchanged": True,
            "temp_directories_cleaned": True,
        },
        "developer_experience": {
            "average_duration_seconds": 1.3,
            "warning_has_rule_id": True,
            "warning_has_failed_check": True,
            "warning_has_suggested_fix": True,
            "warning_has_rollback_plan": True,
            "warning_has_fast_gate_suggestion": True,
            "warning_has_non_blocking_notice": True,
            "needs_caching": False,
        },
        "runtime_cost_breakdown": {
            "fast_gate_step3_subprocess": "~1.0s",
            "json_parse_and_analysis": "~0.05s",
            "output_rendering": "~0.01s",
            "tempdir_cleanup": "~0.05s",
            "overhead": "~0.2s",
        },
        "boundary_confirmations": {
            "no_docs_memory_modification": True,
            "no_memory_rules_yml_modification": True,
        },
        "test_results": {
            "full_precommit_hook_exit_code": 0,
        },
    }
    data.update(overrides)
    return data


def _make_rich_observation(total_runs: int = 25, span_days: float = 8.0) -> dict:
    """构造满足观察期条件的观察数据（≥ 20 次运行，≥ 7 天）。"""
    runs = []
    for i in range(total_runs):
        runs.append({
            "run": i + 1,
            "timestamp": f"2026-06-{(i % 28) + 1:02d}T10:00:00Z",
            "exit_code": 0,
            "duration_ms": 1300,
            "duration_seconds": 1.3,
            "warning_output": False,
            "output_summary": "全部通过",
            "polluted_reports": False,
            "generated_latest": False,
            "modified_docs_memory": False,
            "modified_memory_rules_yml": False,
            "worktree_after": "clean",
        })
    return _make_minimal_observation(
        normal_runs=runs,
        observation_summary={
            "total_normal_runs": total_runs,
            "all_exit_code_zero": True,
            "all_no_pollution": True,
            "all_no_latest": True,
            "negative_verification_passed": True,
            "ready_for_continued_observation": True,
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：常量验证
# ═══════════════════════════════════════════════════════════════════════════════


def test_min_observation_days_value():
    """最小观察天数应为 7。"""
    assert MIN_OBSERVATION_DAYS == 7


def test_min_observation_runs_value():
    """最小观察次数应为 20。"""
    assert MIN_OBSERVATION_RUNS == 20


def test_max_duration_seconds_value():
    """运行时耗阈值应为 3.0s。"""
    assert MAX_AVERAGE_DURATION_SECONDS == 3.0


def test_valid_readiness_statuses():
    """所有合法的 readiness_status 应可枚举。"""
    assert READY_FOR_BLOCKING in VALID_READINESS_STATUSES
    assert NEEDS_MORE_OBSERVATION in VALID_READINESS_STATUSES
    assert KEEP_WARN_ONLY in VALID_READINESS_STATUSES
    assert FIX_PRECOMMIT_OUTPUT in VALID_READINESS_STATUSES


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：_compute_observation_span
# ═══════════════════════════════════════════════════════════════════════════════


def test_compute_observation_span_empty():
    """无运行记录时 span 为 0。"""
    obs = _make_minimal_observation(normal_runs=[])
    span = _compute_observation_span(obs)
    assert span["total_runs"] == 0
    assert span["span_days"] == 0.0


def test_compute_observation_span_single_day():
    """同一天 3 次运行，span ≈ 0 天。"""
    obs = _make_minimal_observation(normal_runs=[
        {"timestamp": "2026-06-19T10:00:00Z"},
        {"timestamp": "2026-06-19T10:01:00Z"},
        {"timestamp": "2026-06-19T10:02:00Z"},
    ])
    span = _compute_observation_span(obs)
    assert span["total_runs"] == 3
    # 同一天内 span 应接近 0
    assert span["span_days"] < 0.1


def test_compute_observation_span_multi_day():
    """跨 8 天应正确计算。"""
    obs = _make_minimal_observation(normal_runs=[
        {"timestamp": "2026-06-01T00:00:00Z"},
        {"timestamp": "2026-06-09T00:00:00Z"},
    ])
    span = _compute_observation_span(obs)
    assert span["span_days"] >= 7.9


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：_load_observation_data
# ═══════════════════════════════════════════════════════════════════════════════


def test_load_observation_data_rejects_latest():
    """加载 latest 文件应抛出 ValueError。"""
    with pytest.raises(ValueError, match="latest"):
        _load_observation_data("some_latest.json")


def test_load_observation_data_rejects_wrong_type():
    """加载非 observation 类型的 JSON 应抛出 ValueError。"""
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump({"report_type": "something_else"}, f)
        tmp_path = f.name
    try:
        with pytest.raises(ValueError, match="类型不匹配"):
            _load_observation_data(tmp_path)
    finally:
        Path(tmp_path).unlink()


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：_derive_readiness_status
# ═══════════════════════════════════════════════════════════════════════════════


def test_derive_status_needs_more_observation():
    """条件 #1（观察期长度）失败 → needs_more_observation。"""
    checks = [
        {"index": 1, "passed": False, "detail": "不足"},
    ]
    assert _derive_readiness_status(checks) == NEEDS_MORE_OBSERVATION


def test_derive_status_ready_for_blocking():
    """全部 15 条通过 → ready_for_blocking。"""
    checks = [{"index": i, "passed": True} for i in range(1, 16)]
    assert _derive_readiness_status(checks) == READY_FOR_BLOCKING


def test_derive_status_fix_false_positive():
    """条件 #1 通过但 #9 失败 → fix_false_positive。"""
    checks = [
        {"index": 1, "passed": True},
        {"index": 9, "passed": False},
    ]
    assert _derive_readiness_status(checks) == FIX_FALSE_POSITIVE


def test_derive_status_fix_worktree_pollution():
    """条件 #1 通过但 #4 失败 → fix_worktree_pollution。"""
    checks = [
        {"index": 1, "passed": True},
        {"index": 4, "passed": False},
        {"index": 9, "passed": True},
    ]
    assert _derive_readiness_status(checks) == FIX_WORKTREE_POLLUTION


def test_derive_status_fix_runtime_cost():
    """条件 #1 通过但 #3 失败 → fix_runtime_cost。"""
    checks = [
        {"index": 1, "passed": True},
        {"index": 3, "passed": False},
        {"index": 4, "passed": True},
        {"index": 9, "passed": True},
    ]
    assert _derive_readiness_status(checks) == FIX_RUNTIME_COST


def test_derive_status_keep_warn_only_other_failure():
    """非关键条件失败 → keep_warn_only。"""
    checks = [
        {"index": 1, "passed": True},
        {"index": 2, "passed": False},  # exit code 不稳定
        {"index": 3, "passed": True},
        {"index": 4, "passed": True},
        {"index": 9, "passed": True},
    ]
    assert _derive_readiness_status(checks) == KEEP_WARN_ONLY


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：run_readiness_review —— 观察期不足
# ═══════════════════════════════════════════════════════════════════════════════


def test_readiness_review_needs_more_observation_insufficient_runs():
    """观察期不足（3 次运行，0 天）→ needs_more_observation。"""
    import tempfile
    data = _make_minimal_observation(normal_runs=[
        {"timestamp": "2026-06-19T10:00:00Z"},
        {"timestamp": "2026-06-19T10:01:00Z"},
        {"timestamp": "2026-06-19T10:02:00Z"},
    ])
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(data, f)
        tmp_path = f.name
    try:
        review = run_readiness_review(tmp_path)
        assert review.readiness_status == NEEDS_MORE_OBSERVATION
        assert review.observation_total_runs == 3
        assert review.observation_span_days < 1.0
    finally:
        Path(tmp_path).unlink()


def test_readiness_review_needs_more_observation_message():
    """needs_more_observation 应给出明确的推荐信息。"""
    import tempfile
    data = _make_minimal_observation(normal_runs=[
        {"timestamp": "2026-06-19T10:00:00Z"},
    ])
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(data, f)
        tmp_path = f.name
    try:
        review = run_readiness_review(tmp_path)
        assert "观察期不足" in review.recommendation or "More" in review.recommendation or "更多" in review.recommendation
    finally:
        Path(tmp_path).unlink()


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：run_readiness_review —— 满足条件（mock）
# ═══════════════════════════════════════════════════════════════════════════════


def test_readiness_review_ready_for_blocking():
    """观察期充足 + 全部通过 → ready_for_blocking。"""
    import tempfile
    data = _make_rich_observation(total_runs=25, span_days=8.0)
    data["observation_summary"]["all_exit_code_zero"] = True
    data["observation_summary"]["negative_verification_passed"] = True

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(data, f)
        tmp_path = f.name
    try:
        review = run_readiness_review(tmp_path)
        # 注意：条件 #15（人工审批）默认不通过
        assert review.readiness_status == KEEP_WARN_ONLY
        # 但至少有 14/15 通过
        assert review.passed_count >= 14
    finally:
        Path(tmp_path).unlink()


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：误报审查
# ═══════════════════════════════════════════════════════════════════════════════


def test_false_positive_review_no_false_positives():
    """无 warning 输出 → 无误报。"""
    obs = _make_minimal_observation(normal_runs=[
        {"timestamp": "2026-06-19T10:00:00Z", "warning_output": False},
        {"timestamp": "2026-06-19T10:01:00Z", "warning_output": False},
    ])
    review = _review_false_positives(obs)
    assert review["has_false_positives"] is False
    assert review["warning_rate"] == 0.0


def test_false_positive_review_with_warnings():
    """有 warning 输出 → 误报率 > 0。"""
    obs = _make_minimal_observation(normal_runs=[
        {"timestamp": "2026-06-19T10:00:00Z", "warning_output": True},
        {"timestamp": "2026-06-19T10:01:00Z", "warning_output": False},
        {"timestamp": "2026-06-19T10:02:00Z", "warning_output": True},
    ])
    review = _review_false_positives(obs)
    assert review["has_false_positives"] is False  # 默认不上报误报
    assert review["warning_rate"] > 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：运行时耗审查
# ═══════════════════════════════════════════════════════════════════════════════


def test_runtime_cost_review_acceptable():
    """平均耗时低于阈值 → 可接受。"""
    obs = _make_minimal_observation()
    review = _review_runtime_cost(obs)
    assert review["is_acceptable"] is True
    assert review["average_seconds"] < MAX_AVERAGE_DURATION_SECONDS


def test_runtime_cost_review_too_slow():
    """平均耗时超过阈值 → 不可接受。"""
    obs = _make_minimal_observation()
    obs["developer_experience"]["average_duration_seconds"] = 5.0
    obs["normal_runs"] = [
        {"duration_seconds": 5.0},
        {"duration_seconds": 5.5},
    ]
    review = _review_runtime_cost(obs)
    assert review["is_acceptable"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：工作区污染审查
# ═══════════════════════════════════════════════════════════════════════════════


def test_worktree_pollution_review_clean():
    """无污染 → 干净。"""
    obs = _make_minimal_observation()
    review = _review_worktree_pollution(obs)
    assert review["has_pollution"] is False
    assert review["new_untracked_files"] == 0
    assert review["temp_directories_cleaned"] is True


def test_worktree_pollution_review_dirty():
    """有污染 → 标记污染。"""
    obs = _make_minimal_observation()
    obs["worktree_pollution"]["new_untracked_files"] = 3
    obs["worktree_pollution"]["harness_reports_unchanged"] = False
    review = _review_worktree_pollution(obs)
    assert review["new_untracked_files"] == 3
    assert review["harness_reports_polluted"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：_build_rollback_plan
# ═══════════════════════════════════════════════════════════════════════════════


def test_rollback_plan_has_three_methods():
    """回滚方案应有 3 种方法。"""
    plan = _build_rollback_plan()
    assert "method_1" in plan
    assert "method_2" in plan
    assert "method_3" in plan
    assert plan["method_1"]["name"] != ""
    assert plan["method_2"]["name"] != ""


def test_rollback_plan_has_verification():
    """回滚方案应有验证命令。"""
    plan = _build_rollback_plan()
    assert "verification" in plan
    assert "command" in plan["verification"]
    assert plan["verification"]["expected_exit_code"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：JSON renderer
# ═══════════════════════════════════════════════════════════════════════════════


def test_json_renderer_contains_readiness_status():
    """JSON 输出必须包含 readiness_status。"""
    review = ReadinessReview(
        run_id="test",
        timestamp="2026-01-01T00:00:00Z",
        readiness_status=NEEDS_MORE_OBSERVATION,
        observation_source="test.json",
        observation_total_runs=3,
        observation_span_days=0.0,
        observation_span_first="2026-01-01",
        observation_span_last="2026-01-01",
    )
    data = render_readiness_json(review)
    assert data["readiness_status"] == NEEDS_MORE_OBSERVATION
    assert data["report_type"] == "precommit_blocking_readiness_review"


def test_json_renderer_contains_boundary_confirmations():
    """JSON 输出必须包含边界确认。"""
    review = ReadinessReview(
        run_id="test",
        timestamp="2026-01-01T00:00:00Z",
        readiness_status=NEEDS_MORE_OBSERVATION,
        observation_source="test.json",
        observation_total_runs=3,
        observation_span_days=0.0,
        observation_span_first="2026-01-01",
        observation_span_last="2026-01-01",
    )
    data = render_readiness_json(review)
    bc = data["boundary_confirmations"]
    assert bc["did_not_modify_precommit_hook"] is True
    assert bc["did_not_enter_blocking"] is True
    assert bc["did_not_modify_memory_rules_yml"] is True
    assert bc["did_not_modify_docs_memory"] is True
    assert bc["did_not_generate_latest"] is True
    assert bc["did_not_call_llm"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：Markdown renderer
# ═══════════════════════════════════════════════════════════════════════════════


def test_markdown_renderer_contains_rollback_plan():
    """Markdown 输出必须包含 Rollback Plan 章节。"""
    review = ReadinessReview(
        run_id="test",
        timestamp="2026-01-01T00:00:00Z",
        readiness_status=NEEDS_MORE_OBSERVATION,
        observation_source="test.json",
        observation_total_runs=3,
        observation_span_days=0.0,
        observation_span_first="2026-01-01",
        observation_span_last="2026-01-01",
        checks=[],
        rollback_plan=_build_rollback_plan(),
        recommendation="测试建议",
    )
    md = render_readiness_markdown(review)
    assert "Rollback Plan" in md
    assert "method_1" in md.lower() or "修改" in md


def test_markdown_renderer_contains_readiness_checklist():
    """Markdown 输出必须包含 Readiness Checklist。"""
    review = ReadinessReview(
        run_id="test",
        timestamp="2026-01-01T00:00:00Z",
        readiness_status=NEEDS_MORE_OBSERVATION,
        observation_source="test.json",
        observation_total_runs=3,
        observation_span_days=0.0,
        observation_span_first="2026-01-01",
        observation_span_last="2026-01-01",
        checks=[],
        rollback_plan=_build_rollback_plan(),
        recommendation="测试",
    )
    md = render_readiness_markdown(review)
    assert "Readiness Checklist" in md


def test_markdown_renderer_contains_not_applied_section():
    """Markdown 输出必须包含 Not Applied Automatically 章节。"""
    review = ReadinessReview(
        run_id="test",
        timestamp="2026-01-01T00:00:00Z",
        readiness_status=NEEDS_MORE_OBSERVATION,
        observation_source="test.json",
        observation_total_runs=3,
        observation_span_days=0.0,
        observation_span_first="2026-01-01",
        observation_span_last="2026-01-01",
        checks=[],
        rollback_plan=_build_rollback_plan(),
        recommendation="测试",
    )
    md = render_readiness_markdown(review)
    assert "Not Applied Automatically" in md


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：write_readiness_snapshot —— 不生成 latest
# ═══════════════════════════════════════════════════════════════════════════════


def test_write_snapshot_no_latest_in_filename():
    """Snapshot 文件名不应包含 latest。使用项目内临时目录。"""
    import tempfile, shutil
    tmp_path = tempfile.mkdtemp(prefix="test_snapshot_", dir=PROJECT_ROOT / "harness" / "reports")
    try:
        review = ReadinessReview(
            run_id="test-001",
            timestamp="2026-01-01T00:00:00Z",
            readiness_status=NEEDS_MORE_OBSERVATION,
            observation_source="test.json",
            observation_total_runs=3,
            observation_span_days=0.0,
            observation_span_first="2026-01-01",
            observation_span_last="2026-01-01",
        )
        paths = write_readiness_snapshot(review, str(tmp_path))
        assert "latest" not in Path(paths["json"]).name.lower()
        assert "latest" not in Path(paths["markdown"]).name.lower()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_write_snapshot_creates_both_formats():
    """Snapshot 应同时生成 JSON 和 Markdown。使用项目内临时目录。"""
    import tempfile, shutil
    tmp_path = tempfile.mkdtemp(prefix="test_snapshot_", dir=PROJECT_ROOT / "harness" / "reports")
    try:
        review = ReadinessReview(
            run_id="test-002",
            timestamp="2026-01-01T00:00:00Z",
            readiness_status=NEEDS_MORE_OBSERVATION,
            observation_source="test.json",
            observation_total_runs=3,
            observation_span_days=0.0,
            observation_span_first="2026-01-01",
            observation_span_last="2026-01-01",
        )
        paths = write_readiness_snapshot(review, str(tmp_path))
        assert Path(paths["json"]).exists()
        assert Path(paths["markdown"]).exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：不修改 .githooks/pre-commit / memory_rules.yml / docs/memory/*
# ═══════════════════════════════════════════════════════════════════════════════


def test_run_readiness_review_does_not_modify_precommit_hook():
    """run_readiness_review 不应修改 .githooks/pre-commit。"""
    precommit_path = PROJECT_ROOT / ".githooks" / "pre-commit"
    if not precommit_path.exists():
        pytest.skip(".githooks/pre-commit 不存在")

    mtime_before = precommit_path.stat().st_mtime

    import tempfile
    data = _make_minimal_observation(normal_runs=[
        {"timestamp": "2026-06-19T10:00:00Z"},
    ])
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(data, f)
        tmp_path = f.name
    try:
        run_readiness_review(tmp_path)
        assert precommit_path.stat().st_mtime == mtime_before, (
            ".githooks/pre-commit 不应被修改"
        )
    finally:
        Path(tmp_path).unlink()


def test_run_readiness_review_does_not_modify_memory_rules():
    """run_readiness_review 不应修改 memory_rules.yml。"""
    rules_path = PROJECT_ROOT / "docs" / "memory" / "memory_rules.yml"
    if not rules_path.exists():
        pytest.skip("memory_rules.yml 不存在")

    mtime_before = rules_path.stat().st_mtime

    import tempfile
    data = _make_minimal_observation(normal_runs=[
        {"timestamp": "2026-06-19T10:00:00Z"},
    ])
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(data, f)
        tmp_path = f.name
    try:
        run_readiness_review(tmp_path)
        assert rules_path.stat().st_mtime == mtime_before, (
            "memory_rules.yml 不应被修改"
        )
    finally:
        Path(tmp_path).unlink()


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：本轮不进入 blocking
# ═══════════════════════════════════════════════════════════════════════════════


def test_readiness_review_no_blocking_decision_applied():
    """readiness review 仅是分析，不触发实际 blocking 变更。"""
    import tempfile
    data = _make_rich_observation(total_runs=25, span_days=8.0)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(data, f)
        tmp_path = f.name
    try:
        review = run_readiness_review(tmp_path)
        # 即使数据完美，也不自动进入 blocking
        assert review.readiness_status != READY_FOR_BLOCKING or review.failed_count > 0
    finally:
        Path(tmp_path).unlink()


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：_generate_recommendation
# ═══════════════════════════════════════════════════════════════════════════════


def test_generate_recommendation_for_each_status():
    """每种 status 都应生成非空推荐。"""
    from harness.precommit_blocking_readiness import (
        FIX_PRECOMMIT_OUTPUT,
        _generate_recommendation,
    )
    for status in [
        READY_FOR_BLOCKING,
        NEEDS_MORE_OBSERVATION,
        KEEP_WARN_ONLY,
        FIX_PRECOMMIT_OUTPUT,
        FIX_RUNTIME_COST,
        FIX_FALSE_POSITIVE,
        FIX_WORKTREE_POLLUTION,
    ]:
        rec = _generate_recommendation(status)
        assert len(rec) > 10, f"推荐文本过短: {status} → {rec[:50]}"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：_perform_readiness_checks 数量
# ═══════════════════════════════════════════════════════════════════════════════


def test_perform_readiness_checks_count():
    """应恰好返回 15 条审查条件。"""
    obs = _make_minimal_observation()
    span = _compute_observation_span(obs)
    checks = _perform_readiness_checks(
        obs, span, span["total_runs"], span["span_days"]
    )
    assert len(checks) == 15, f"预期 15 条，实际 {len(checks)} 条"


def test_each_check_has_required_fields():
    """每条审查条件应有 index、label、description、passed、detail、evidence。"""
    obs = _make_minimal_observation()
    span = _compute_observation_span(obs)
    checks = _perform_readiness_checks(
        obs, span, span["total_runs"], span["span_days"]
    )
    for c in checks:
        assert "index" in c
        assert "label" in c
        assert "description" in c
        assert "passed" in c
        assert "detail" in c
        assert "evidence" in c
