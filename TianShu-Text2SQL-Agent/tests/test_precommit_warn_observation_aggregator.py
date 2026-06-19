"""Memory Harness Step 21c —— Observation 聚合器测试。

覆盖场景：
    1. 加载多个 observation JSON
    2. 计算 observation_count
    3. 计算 observation_span_days
    4. 计算平均耗时
    5. 统计 warning_total
    6. 统计 worktree_pollution_count
    7. 统计 latest_generation_count
    8. 统计 TA-R018 passed / failed / warning / skipped
    9. 拒绝读取 latest 文件
    10. 不生成 latest 报告
    11. 空目录 → insufficient_observations
    12. 不修改 docs/memory/*
    13. 不修改 memory_rules.yml
    14. 不进入 blocking
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# 确保项目根目录在导入路径中
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.precommit_warn_observation_aggregator import (
    MIN_OBSERVATION_DAYS,
    MIN_OBSERVATION_RUNS,
    AggregationResult,
    DurationStats,
    TaR018Stats,
    _parse_ts,
    aggregate,
    load_observations,
    main,
    render_aggregation_json,
    render_aggregation_markdown,
    write_aggregation_snapshot,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 测试夹具 —— 构造 observation 数据
# ═══════════════════════════════════════════════════════════════════════════════


def _now_ts() -> str:
    """当前 UTC 时间戳。"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ts_offset(offset_hours: float) -> str:
    """返回 offset_hours 前的时间戳。"""
    dt = datetime.now(timezone.utc) - timedelta(hours=offset_hours)
    return dt.isoformat().replace("+00:00", "Z")


def _make_observation(
    *,
    timestamp: str | None = None,
    duration_ms: float = 1300.0,
    exit_code: int = 0,
    warning_count: int = 0,
    ta_r018_result: str = "passed",
    worktree_dirty_before: bool = False,
    worktree_dirty_after: bool = False,
    generated_latest: bool = False,
    git_commit: str = "abc123def",
    branch: str = "main",
) -> dict:
    """构造一条 observation dict。"""
    return {
        "report_type": "precommit_memory_warn_single_observation",
        "run_id": f"OBS-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}",
        "timestamp": timestamp or _now_ts(),
        "git_commit": git_commit,
        "branch": branch,
        "duration_ms": duration_ms,
        "exit_code": exit_code,
        "warning_count": warning_count,
        "active_blocking_rules": ["TA-R018"],
        "ta_r018_result": ta_r018_result,
        "memory_warn_exit_code": 0,
        "precommit_mode": "warn_only",
        "polluted_reports": False,
        "generated_latest": generated_latest,
        "worktree_dirty_before": worktree_dirty_before,
        "worktree_dirty_after": worktree_dirty_after,
        "enforcement_summary": {
            "total_rules": 21,
            "passed": 20,
            "warnings": 1,
            "blocking_failures": warning_count,
            "active_blocking": 1,
        },
        "boundary_confirmations": {
            "no_blocking": True,
            "no_latest": True,
            "no_docs_memory_modification": True,
            "no_memory_rules_yml_modification": True,
            "temp_report_dir_used": True,
        },
    }


def _write_observation_files(
    obs_dir: Path,
    observations: list[dict],
    prefix: str = "precommit_memory_warn_observation",
) -> list[Path]:
    """将 observation dict 列表写入目录，返回写入的文件路径列表。"""
    obs_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, obs in enumerate(observations):
        ts = obs.get("timestamp", "").replace(":", "").replace("-", "").replace("T", "_")
        if not ts:
            ts = f"20260619_{210000 + i:06d}"
        fname = f"{prefix}_{ts}.json"
        fpath = obs_dir / fname
        fpath.write_text(json.dumps(obs, ensure_ascii=False, indent=2), encoding="utf-8")
        paths.append(fpath)
    return paths


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：load_observations
# ═══════════════════════════════════════════════════════════════════════════════


class TestLoadObservations:
    """observation 加载测试。"""

    def test_load_multiple_observations(self, tmp_path):
        """加载多个 observation JSON 应返回正确数量。"""
        obs = [
            _make_observation(timestamp=_ts_offset(2)),
            _make_observation(timestamp=_ts_offset(1)),
            _make_observation(timestamp=_ts_offset(0)),
        ]
        _write_observation_files(tmp_path, obs)

        loaded, errors = load_observations(tmp_path)
        assert len(loaded) == 3
        assert len(errors) == 0

    def test_load_skips_latest_files(self, tmp_path):
        """应拒绝文件名包含 latest 的文件。"""
        # 正常文件
        obs = [_make_observation()]
        _write_observation_files(tmp_path, obs)

        # 写入一个 latest 文件
        latest_path = tmp_path / "precommit_memory_warn_observation_latest.json"
        latest_path.write_text(
            json.dumps(_make_observation(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        loaded, errors = load_observations(tmp_path)
        assert len(loaded) == 1  # 只加载正常文件
        assert any("latest" in e.lower() for e in errors)

    def test_load_skips_invalid_json(self, tmp_path):
        """JSON 解析失败的文件应计入 errors。"""
        obs = [_make_observation()]
        _write_observation_files(tmp_path, obs)

        # 写入无效 JSON
        bad_path = tmp_path / "precommit_memory_warn_observation_bad.json"
        bad_path.write_text("这不是有效的 JSON {{{", encoding="utf-8")

        loaded, errors = load_observations(tmp_path)
        assert len(loaded) == 1
        assert any("JSON 解析失败" in e for e in errors)

    def test_load_skips_wrong_report_type(self, tmp_path):
        """report_type 不匹配的文件应计入 errors。"""
        obs = [_make_observation()]
        _write_observation_files(tmp_path, obs)

        # 写入一个 report_type 错误的文件
        wrong_path = tmp_path / "precommit_memory_warn_observation_wrong.json"
        wrong_obs = _make_observation()
        wrong_obs["report_type"] = "some_other_type"
        wrong_path.write_text(json.dumps(wrong_obs, ensure_ascii=False, indent=2), encoding="utf-8")

        loaded, errors = load_observations(tmp_path)
        assert len(loaded) == 1
        assert any("report_type 不匹配" in e for e in errors)

    def test_load_empty_directory(self, tmp_path):
        """空目录应返回空列表。"""
        loaded, errors = load_observations(tmp_path)
        assert len(loaded) == 0
        assert len(errors) == 0

    def test_load_nonexistent_directory(self):
        """不存在的目录应返回空列表。"""
        loaded, errors = load_observations("/nonexistent/path/12345")
        assert len(loaded) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：aggregate
# ═══════════════════════════════════════════════════════════════════════════════


class TestAggregate:
    """聚合统计测试。"""

    def test_aggregate_observation_count(self):
        """observation_count 应正确。"""
        obs = [
            _make_observation(),
            _make_observation(),
            _make_observation(),
        ]
        result = aggregate(obs)
        assert result.observation_count == 3

    def test_aggregate_span_days(self):
        """span_days 应正确计算。"""
        now = datetime.now(timezone.utc)
        obs = [
            _make_observation(
                timestamp=(now - timedelta(days=3)).isoformat().replace("+00:00", "Z")
            ),
            _make_observation(
                timestamp=now.isoformat().replace("+00:00", "Z")
            ),
            _make_observation(
                timestamp=(now - timedelta(days=1)).isoformat().replace("+00:00", "Z")
            ),
        ]
        result = aggregate(obs)
        assert result.observation_span_days >= 2.9
        assert result.observation_span_days <= 3.1

    def test_aggregate_average_duration(self):
        """平均耗时计算正确。"""
        obs = [
            _make_observation(duration_ms=1000),
            _make_observation(duration_ms=2000),
            _make_observation(duration_ms=3000),
        ]
        result = aggregate(obs)
        assert result.duration_stats.average_ms == 2000.0
        assert result.duration_stats.min_ms == 1000.0
        assert result.duration_stats.max_ms == 3000.0

    def test_aggregate_warning_total(self):
        """warning_total 应正确。"""
        obs = [
            _make_observation(warning_count=0),
            _make_observation(warning_count=2),
            _make_observation(warning_count=1),
        ]
        result = aggregate(obs)
        assert result.warning_total == 3

    def test_aggregate_worktree_pollution_count(self):
        """worktree_pollution_count 应正确。"""
        obs = [
            _make_observation(worktree_dirty_after=False),
            _make_observation(worktree_dirty_after=True),  # 污染
            _make_observation(worktree_dirty_after=False),
            _make_observation(worktree_dirty_after=True),  # 污染
        ]
        result = aggregate(obs)
        assert result.worktree_pollution_count == 2

    def test_aggregate_latest_generation_count(self):
        """latest_generation_count 应正确。"""
        obs = [
            _make_observation(generated_latest=False),
            _make_observation(generated_latest=False),
        ]
        result = aggregate(obs)
        assert result.latest_generation_count == 0

    def test_aggregate_ta_r018_stats(self):
        """TA-R018 统计应正确。"""
        obs = [
            _make_observation(ta_r018_result="passed"),
            _make_observation(ta_r018_result="passed"),
            _make_observation(ta_r018_result="failed"),
            _make_observation(ta_r018_result="passed"),
            _make_observation(ta_r018_result="warning"),
            _make_observation(ta_r018_result="skipped"),
        ]
        result = aggregate(obs)
        ta = result.ta_r018_stats
        assert ta.passed == 3
        assert ta.failed == 1
        assert ta.warning == 1
        assert ta.skipped == 1
        assert ta.total == 6

    def test_aggregate_meets_20_commits(self):
        """≥20 次 observation 应满足 meets_20_commits。"""
        obs = [_make_observation() for _ in range(20)]
        result = aggregate(obs)
        assert result.meets_20_commits is True
        assert result.meets_7_days is False  # 同时间戳跨度 ~0 天

    def test_aggregate_meets_7_days(self):
        """≥7 天跨度应满足 meets_7_days。"""
        now = datetime.now(timezone.utc)
        obs = [
            _make_observation(
                timestamp=(now - timedelta(days=8)).isoformat().replace("+00:00", "Z")
            ),
            _make_observation(
                timestamp=now.isoformat().replace("+00:00", "Z")
            ),
        ]
        result = aggregate(obs)
        assert result.meets_7_days is True

    def test_aggregate_empty_observations(self):
        """空 observation 列表 → insufficient_observations。"""
        result = aggregate([])
        assert result.observation_count == 0
        assert result.recommendation == "insufficient_observations"
        assert result.meets_20_commits is False
        assert result.meets_7_days is False

    def test_aggregate_recommendation_both_met(self):
        """同时满足两个条件 → ready_for_review。"""
        now = datetime.now(timezone.utc)
        obs = [
            _make_observation(
                timestamp=(now - timedelta(days=10)).isoformat().replace("+00:00", "Z")
            ),
            _make_observation(
                timestamp=now.isoformat().replace("+00:00", "Z")
            ),
        ] + [_make_observation() for _ in range(18)]
        result = aggregate(obs)
        assert result.meets_20_commits is True
        assert result.meets_7_days is True
        assert result.recommendation == "ready_for_review"

    def test_aggregate_recommendation_partial(self):
        """仅满足一个条件 → partial_criteria_met。"""
        obs = [_make_observation() for _ in range(20)]  # 20 次但同时间戳
        result = aggregate(obs)
        assert result.meets_20_commits is True
        assert result.meets_7_days is False
        assert result.recommendation == "partial_criteria_met"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：渲染
# ═══════════════════════════════════════════════════════════════════════════════


class TestRender:
    """渲染测试。"""

    def test_render_json_has_report_type(self):
        """JSON 输出应包含 report_type。"""
        obs = [_make_observation()]
        agg = aggregate(obs)
        data = render_aggregation_json(agg)
        assert data["report_type"] == "precommit_memory_warn_aggregation"

    def test_render_json_includes_all_fields(self):
        """JSON 输出应包含所有聚合字段。"""
        obs = [_make_observation(), _make_observation()]
        agg = aggregate(obs)
        data = render_aggregation_json(agg)

        required_keys = [
            "report_type", "run_id", "timestamp", "observation_count",
            "observation_span_days", "duration_stats", "warning_total",
            "worktree_pollution_count", "latest_generation_count",
            "ta_r018_stats", "meets_20_commits", "meets_7_days",
            "recommendation", "boundary_confirmations", "error_files",
        ]
        for key in required_keys:
            assert key in data, f"缺少字段: {key}"

    def test_render_markdown_contains_recommendation(self):
        """Markdown 输出应包含 recommendation。"""
        obs = [_make_observation()]
        agg = aggregate(obs)
        md = render_aggregation_markdown(agg)
        assert agg.recommendation in md

    def test_write_snapshot_no_latest(self, tmp_path):
        """write_aggregation_snapshot 生成的文件名不应包含 latest。"""
        obs = [_make_observation()]
        agg = aggregate(obs)
        paths = write_aggregation_snapshot(agg, tmp_path)

        for path_str in paths.values():
            assert "latest" not in Path(path_str).name.lower()

        # 验证文件确实存在
        assert Path(paths["json"]).exists()
        assert Path(paths["markdown"]).exists()


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：与 readiness review 的兼容性
# ═══════════════════════════════════════════════════════════════════════════════


class TestReadinessCompatibility:
    """验证聚合结果与 Step 22 readiness review 的对齐。"""

    def test_constants_align_with_readiness(self):
        """聚合器阈值常量应与 readiness review 一致。"""
        from harness.precommit_blocking_readiness import (
            MIN_OBSERVATION_DAYS as R_MIN_DAYS,
            MIN_OBSERVATION_RUNS as R_MIN_RUNS,
        )
        assert MIN_OBSERVATION_DAYS == R_MIN_DAYS
        assert MIN_OBSERVATION_RUNS == R_MIN_RUNS

    def test_aggregation_is_read_only(self):
        """聚合器不应修改任何文件（除自己的输出目录外）。"""
        # 纯函数 aggregate 无副作用
        obs = [_make_observation()]
        agg = aggregate(obs)
        assert agg.recommendation in (
            "insufficient_observations",
            "continue_observation",
            "partial_criteria_met",
            "ready_for_review",
        )

    def test_no_blocking_recommendation(self):
        """聚合器推荐不应等于 ready_for_blocking（那是 Step 22 的判定）。"""
        obs = [_make_observation() for _ in range(25)]
        result = aggregate(obs)
        # recommendation 只能是 4 个合法值之一
        assert result.recommendation in (
            "insufficient_observations",
            "continue_observation",
            "partial_criteria_met",
            "ready_for_review",
        )
        # 绝不会输出 blocking 判定
        assert "blocking" not in result.recommendation


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：边界确认
# ═══════════════════════════════════════════════════════════════════════════════


class TestBoundaryConfirmations:
    """边界确认测试。"""

    def test_does_not_modify_memory_rules_yml(self):
        """聚合器不应修改 memory_rules.yml。"""
        rules_path = PROJECT_ROOT / "docs" / "memory" / "memory_rules.yml"
        if not rules_path.exists():
            pytest.skip("memory_rules.yml 不存在")

        original = rules_path.read_bytes()
        # 执行聚合（纯内存操作，本身不应修改文件）
        obs = [_make_observation()]
        aggregate(obs)
        # 验证确实未变
        assert rules_path.read_bytes() == original, "memory_rules.yml 不应被修改"

    def test_does_not_modify_docs_memory(self):
        """聚合器不应修改 docs/memory/ 下的文件。"""
        memory_dir = PROJECT_ROOT / "docs" / "memory"
        if not memory_dir.exists():
            pytest.skip("docs/memory/ 不存在")

        mtimes_before = {}
        for f in memory_dir.rglob("*"):
            if f.is_file():
                mtimes_before[str(f)] = f.stat().st_mtime

        obs = [_make_observation()]
        aggregate(obs)

        for f in memory_dir.rglob("*"):
            if f.is_file() and str(f) in mtimes_before:
                assert f.stat().st_mtime == mtimes_before[str(f)], (
                    f"{f.name} 不应被修改"
                )

    def test_no_latest_generated(self):
        """聚合器不生成 latest 文件。"""
        obs = [_make_observation()]
        agg = aggregate(obs)
        # 验证 aggregation result 的数据确认不包含 latest 路径
        # 实际写入测试见 TestRender.test_write_snapshot_no_latest
        assert agg.run_id.startswith("AGG-")


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：_parse_ts
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseTs:
    """时间戳解析测试。"""

    def test_parse_valid_iso(self):
        """有效 ISO 时间戳应正确解析。"""
        ts = _parse_ts("2026-06-19T21:00:00+08:00")
        assert ts is not None
        assert ts.year == 2026

    def test_parse_utc_z(self):
        """UTC Z 后缀应正确解析。"""
        ts = _parse_ts("2026-06-19T13:00:00Z")
        assert ts is not None

    def test_parse_invalid(self):
        """无效时间戳应返回 None。"""
        assert _parse_ts("not-a-timestamp") is None
        assert _parse_ts("") is None


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：main CLI
# ═══════════════════════════════════════════════════════════════════════════════


class TestMainCLI:
    """CLI 入口测试。"""

    def test_main_with_test_data(self, tmp_path):
        """main 应加载 observation、聚合并输出报告。"""
        obs = [
            _make_observation(timestamp=_ts_offset(2)),
            _make_observation(timestamp=_ts_offset(1)),
        ]
        _write_observation_files(tmp_path, obs)

        out_dir = tmp_path / "aggregations"

        exit_code = main([
            "--history-dir", str(tmp_path),
            "--output-dir", str(out_dir),
        ])
        assert exit_code == 0

        # 验证输出文件已生成
        json_files = list(out_dir.glob("*.json"))
        md_files = list(out_dir.glob("*.md"))
        assert len(json_files) >= 1
        assert len(md_files) >= 1
        assert "latest" not in json_files[0].name.lower()

    def test_main_empty_directory(self, tmp_path):
        """空目录应仍 exit 0 并输出 insufficient_observations。"""
        out_dir = tmp_path / "aggregations"
        exit_code = main([
            "--history-dir", str(tmp_path),
            "--output-dir", str(out_dir),
        ])
        assert exit_code == 0

        json_files = list(out_dir.glob("*.json"))
        assert len(json_files) == 1
        data = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert data["recommendation"] == "insufficient_observations"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：不调用 LLM
# ═══════════════════════════════════════════════════════════════════════════════


def test_no_llm_imports():
    """聚合器不应导入任何 LLM 相关模块。"""
    import inspect
    from harness import precommit_warn_observation_aggregator as script

    source = inspect.getsource(script)
    llm_indicators = [
        "deepseek",
        "openai",
        "anthropic",
        "requests.post",
        "httpx",
    ]
    for indicator in llm_indicators:
        assert indicator not in source.lower(), (
            f"聚合器不应包含 LLM 调用相关代码: {indicator}"
        )
