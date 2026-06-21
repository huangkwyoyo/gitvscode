"""Pre-commit Warn Observation 聚合器（Step 21c）。

职责：
    扫描 harness/reports/precommit_memory_warn_history/ 目录中的
    所有 timestamp observation snapshot（Step 21b 产出），聚合统计
    数据为单份报告，供 Step 22 readiness review 使用。

    只产出事实统计，不判定 readiness（Step 22 负责）。

用法：
    python harness/precommit_warn_observation_aggregator.py
    python harness/precommit_warn_observation_aggregator.py \\
        --history-dir harness/reports/precommit_memory_warn_history \\
        --output-dir harness/reports/precommit_memory_warn_aggregations

关键边界：
    - 不读取 latest 文件
    - 不生成 latest 文件
    - 不修改 memory_rules.yml / docs/memory/*
    - 不进入 blocking
    - 不调用 LLM
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 默认目录
_DEFAULT_HISTORY_DIR = str(
    PROJECT_ROOT / "harness" / "reports" / "precommit_memory_warn_history"
)
_DEFAULT_OUTPUT_DIR = str(
    PROJECT_ROOT / "harness" / "reports" / "precommit_memory_warn_aggregations"
)

# 阈值常量（与 Step 22 对齐）
MIN_OBSERVATION_DAYS = 7
MIN_OBSERVATION_RUNS = 20

# Observation 文件名匹配模式
_OBSERVATION_FILE_PATTERN = "precommit_memory_warn_observation_"


# ═══════════════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TaR018Stats:
    """TA-R018 规则在各次 observation 中的结果分布。"""

    passed: int = 0
    failed: int = 0
    warning: int = 0
    skipped: int = 0
    total: int = 0


@dataclass
class DurationStats:
    """耗时统计。"""

    average_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    total_runs_with_duration: int = 0


@dataclass
class AggregationResult:
    """单次聚合的全部结果。"""

    run_id: str = ""
    timestamp: str = ""
    source_dir: str = ""
    observation_count: int = 0
    observation_span_days: float = 0.0
    first_observation_ts: str = ""
    last_observation_ts: str = ""
    duration_stats: DurationStats = field(default_factory=DurationStats)
    warning_total: int = 0
    worktree_pollution_count: int = 0
    latest_generation_count: int = 0
    ta_r018_stats: TaR018Stats = field(default_factory=TaR018Stats)
    meets_20_commits: bool = False
    meets_7_days: bool = False
    recommendation: str = "insufficient_observations"
    error_files: list[str] = field(default_factory=list)
    file_count_errors: int = 0
    valid_observation_timestamps: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# 加载
# ═══════════════════════════════════════════════════════════════════════════════


def load_observations(
    history_dir: str | Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    """扫描 history 目录，加载所有 observation JSON。

    规则：
        - 匹配文件名含 _OBSERVATION_FILE_PATTERN 的 .json 文件
        - 拒绝文件名含 "latest" 的文件
        - JSON 解析失败的文件计入 errors 列表，不中断

    Args:
        history_dir: observation 历史目录路径

    Returns:
        (observations: list[dict], errors: list[str])
    """
    root = Path(history_dir)
    observations: list[dict[str, Any]] = []
    errors: list[str] = []

    if not root.exists() or not root.is_dir():
        return observations, []

    for fpath in sorted(root.glob("*.json")):
        fname = fpath.name

        # 拒绝 latest
        if "latest" in fname.lower():
            errors.append(f"{fname}: 跳过 latest 文件")
            continue

        # 只处理 observation 文件
        if _OBSERVATION_FILE_PATTERN not in fname:
            continue

        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"{fname}: JSON 解析失败 — {exc}")
            continue

        if not isinstance(data, dict):
            errors.append(f"{fname}: 预期 dict，实际 {type(data).__name__}")
            continue

        # 校验 report_type
        rt = data.get("report_type", "")
        if rt != "precommit_memory_warn_single_observation":
            errors.append(
                f"{fname}: report_type 不匹配 "
                f"(预期 precommit_memory_warn_single_observation，实际 {rt})"
            )
            continue

        observations.append(data)

    return observations, errors


# ═══════════════════════════════════════════════════════════════════════════════
# 聚合
# ═══════════════════════════════════════════════════════════════════════════════


def _parse_ts(ts_str: str) -> datetime | None:
    """解析 ISO 时间戳字符串。

    Args:
        ts_str: ISO 格式时间戳

    Returns:
        datetime 对象或 None
    """
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def aggregate(observations: list[dict[str, Any]]) -> AggregationResult:
    """聚合 observation 统计数据。

    纯函数，不产生 I/O 副作用。

    Args:
        observations: load_observations 返回的有效 observation 列表

    Returns:
        AggregationResult
    """
    now = datetime.now(timezone.utc)
    run_id = f"AGG-{now.strftime('%Y%m%dT%H%M%S')}"
    timestamp = now.isoformat().replace("+00:00", "Z")

    result = AggregationResult(
        run_id=run_id,
        timestamp=timestamp,
    )

    # 空 observations
    if not observations:
        result.recommendation = "insufficient_observations"
        return result

    result.observation_count = len(observations)

    # ── 时间跨度 ──
    timestamps: list[datetime] = []
    for obs in observations:
        ts = _parse_ts(obs.get("timestamp", ""))
        if ts:
            timestamps.append(ts)

    if timestamps:
        timestamps.sort()
        first = timestamps[0]
        last = timestamps[-1]
        result.first_observation_ts = first.isoformat()
        result.last_observation_ts = last.isoformat()
        result.observation_span_days = round(
            (last - first).total_seconds() / 86400.0, 3
        )

    # ── 耗时统计 ──
    durations = [
        obs["duration_ms"]
        for obs in observations
        if isinstance(obs.get("duration_ms"), (int, float)) and obs["duration_ms"] > 0
    ]
    if durations:
        result.duration_stats = DurationStats(
            average_ms=round(sum(durations) / len(durations), 1),
            min_ms=round(min(durations), 1),
            max_ms=round(max(durations), 1),
            total_runs_with_duration=len(durations),
        )

    # ── warning 统计 ──
    result.warning_total = sum(
        obs.get("warning_count", 0) for obs in observations
    )

    # ── 工作区污染统计 ──
    # 污染定义：运行前干净但运行后变脏（即 observation 过程产生了新污染）
    # 保守策略：只统计 explicitly 标记为 True 的 worktree_dirty_after
    result.worktree_pollution_count = sum(
        1 for obs in observations
        if obs.get("worktree_dirty_after", False) is True
    )

    # ── latest 生成统计 ──
    result.latest_generation_count = sum(
        1 for obs in observations
        if obs.get("generated_latest", False) is True
    )

    # ── TA-R018 统计 ──
    ta_stats = TaR018Stats()
    for obs in observations:
        r = obs.get("ta_r018_result", "skipped")
        if r == "passed":
            ta_stats.passed += 1
        elif r == "failed":
            ta_stats.failed += 1
        elif r == "warning":
            ta_stats.warning += 1
        else:
            ta_stats.skipped += 1
    ta_stats.total = len(observations)
    result.ta_r018_stats = ta_stats

    # ── readiness 口径（只报告事实，不批准）──
    result.meets_20_commits = result.observation_count >= MIN_OBSERVATION_RUNS
    result.meets_7_days = result.observation_span_days >= MIN_OBSERVATION_DAYS

    # ── 推荐 ──
    if result.meets_20_commits and result.meets_7_days:
        result.recommendation = "ready_for_review"
    elif result.meets_20_commits or result.meets_7_days:
        result.recommendation = "partial_criteria_met"
    else:
        result.recommendation = "continue_observation"

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 渲染
# ═══════════════════════════════════════════════════════════════════════════════


def render_aggregation_json(
    agg: AggregationResult,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    """将聚合结果序列化为 JSON 安全的字典。

    Args:
        agg: 聚合结果
        errors: load_observations 返回的错误列表

    Returns:
        JSON 可序列化的 dict
    """
    return {
        "report_type": "precommit_memory_warn_aggregation",
        "run_id": agg.run_id,
        "timestamp": agg.timestamp,
        "source_dir": agg.source_dir,
        "observation_count": agg.observation_count,
        "observation_span_days": agg.observation_span_days,
        "first_observation_ts": agg.first_observation_ts,
        "last_observation_ts": agg.last_observation_ts,
        "duration_stats": {
            "average_ms": agg.duration_stats.average_ms,
            "min_ms": agg.duration_stats.min_ms,
            "max_ms": agg.duration_stats.max_ms,
            "total_runs_with_duration": agg.duration_stats.total_runs_with_duration,
        },
        "warning_total": agg.warning_total,
        "worktree_pollution_count": agg.worktree_pollution_count,
        "latest_generation_count": agg.latest_generation_count,
        "ta_r018_stats": {
            "passed": agg.ta_r018_stats.passed,
            "failed": agg.ta_r018_stats.failed,
            "warning": agg.ta_r018_stats.warning,
            "skipped": agg.ta_r018_stats.skipped,
            "total": agg.ta_r018_stats.total,
        },
        "meets_20_commits": agg.meets_20_commits,
        "meets_7_days": agg.meets_7_days,
        "recommendation": agg.recommendation,
        "recommendation_labels": {
            "ready_for_review": "满足 20 次 commit 且 ≥7 天观察期，可进入 Step 22 readiness review",
            "partial_criteria_met": (
                f"部分条件满足（commits: {agg.meets_20_commits}, "
                f"days: {agg.meets_7_days}），建议继续观察"
            ),
            "continue_observation": (
                f"观察期不足（{agg.observation_count} 次 / "
                f"{MIN_OBSERVATION_RUNS} 次，{agg.observation_span_days} 天 / "
                f"{MIN_OBSERVATION_DAYS} 天），继续自然观察"
            ),
            "insufficient_observations": "无可用 observation，请先运行 pre-commit warn",
        },
        "boundary_confirmations": {
            "no_blocking": True,
            "no_latest": True,
            "no_docs_memory_modification": True,
            "no_memory_rules_yml_modification": True,
        },
        "file_count_errors": len(errors or []),
        "error_files": errors or [],
    }


def render_aggregation_markdown(agg: AggregationResult) -> str:
    """将聚合结果渲染为 Markdown 字符串。

    Args:
        agg: 聚合结果

    Returns:
        Markdown 文本
    """
    lines: list[str] = []
    lines.append("# Pre-commit Warn Observation Aggregation Report")
    lines.append("")
    lines.append(f"**Run ID:** `{agg.run_id}`")
    lines.append(f"**时间:** {agg.timestamp}")
    lines.append("**Step:** 21c — Observation Aggregator")
    lines.append("")

    # 汇总
    lines.append("## Summary")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| observation_count | {agg.observation_count} |")
    lines.append(f"| observation_span_days | {agg.observation_span_days} |")
    lines.append(f"| meets_20_commits | {agg.meets_20_commits} |")
    lines.append(f"| meets_7_days | {agg.meets_7_days} |")
    lines.append(f"| recommendation | **{agg.recommendation}** |")
    lines.append("")

    # 时间范围
    lines.append("## Time Range")
    lines.append("")
    lines.append(f"- 首次 observation: {agg.first_observation_ts}")
    lines.append(f"- 最后 observation: {agg.last_observation_ts}")
    lines.append(f"- 跨度: {agg.observation_span_days} 天")
    lines.append("")

    # 耗时
    ds = agg.duration_stats
    lines.append("## Duration Stats")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| 平均耗时 | {ds.average_ms:.1f} ms |")
    lines.append(f"| 最小耗时 | {ds.min_ms:.1f} ms |")
    lines.append(f"| 最大耗时 | {ds.max_ms:.1f} ms |")
    lines.append(f"| 有效样本 | {ds.total_runs_with_duration} |")
    lines.append("")

    # Warning 统计
    lines.append("## Warning Stats")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| warning_total | {agg.warning_total} |")
    lines.append(f"| worktree_pollution_count | {agg.worktree_pollution_count} |")
    lines.append(f"| latest_generation_count | {agg.latest_generation_count} |")
    lines.append("")

    # TA-R018
    ta = agg.ta_r018_stats
    lines.append("## TA-R018 Stats")
    lines.append("")
    lines.append("| 结果 | 次数 | 占比 |")
    lines.append("|------|------|------|")
    lines.append(
        f"| passed | {ta.passed} | "
        f"{ta.passed / max(ta.total, 1) * 100:.1f}% |"
    )
    lines.append(
        f"| failed | {ta.failed} | "
        f"{ta.failed / max(ta.total, 1) * 100:.1f}% |"
    )
    lines.append(
        f"| warning | {ta.warning} | "
        f"{ta.warning / max(ta.total, 1) * 100:.1f}% |"
    )
    lines.append(
        f"| skipped | {ta.skipped} | "
        f"{ta.skipped / max(ta.total, 1) * 100:.1f}% |"
    )
    lines.append(f"| **total** | **{ta.total}** | — |")
    lines.append("")

    # Readiness 口径
    lines.append("## Readiness Criteria (事实统计)")
    lines.append("")
    lines.append("| 条件 | 当前值 | 阈值 | 满足 |")
    lines.append("|------|--------|------|:--:|")
    lines.append(
        f"| ≥{MIN_OBSERVATION_RUNS} 次 commit | {agg.observation_count} | "
        f"{MIN_OBSERVATION_RUNS} | {'✅' if agg.meets_20_commits else '❌'} |"
    )
    lines.append(
        f"| ≥{MIN_OBSERVATION_DAYS} 天观察期 | {agg.observation_span_days} | "
        f"{MIN_OBSERVATION_DAYS} | {'✅' if agg.meets_7_days else '❌'} |"
    )
    lines.append("")

    # 推荐
    lines.append("## Recommendation")
    lines.append("")
    labels = {
        "ready_for_review": "✅ 满足全部观察条件，可以进入 Step 22 readiness review",
        "partial_criteria_met": f"🟡 部分条件满足（commits: {agg.meets_20_commits}, days: {agg.meets_7_days}），建议继续观察",
        "continue_observation": (
            f"🔴 观察期不足（{agg.observation_count}/{MIN_OBSERVATION_RUNS} commits, "
            f"{agg.observation_span_days}/{MIN_OBSERVATION_DAYS} days），继续自然观察"
        ),
        "insufficient_observations": "🔴 无可用 observation 数据，请确保 pre-commit warn 已启用",
    }
    lines.append(labels.get(agg.recommendation, agg.recommendation))
    lines.append("")

    # 边界确认
    lines.append("## Boundary Confirmations")
    lines.append("")
    lines.append("- ✅ 未进入 blocking")
    lines.append("- ✅ 未生成 latest")
    lines.append("- ✅ 未修改 docs/memory/*")
    lines.append("- ✅ 未修改 memory_rules.yml")
    lines.append("- ✅ 未调用 LLM")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*聚合生成: {agg.timestamp}*")
    lines.append("*聚合器: Claude Code Agent (Step 21c)*")
    lines.append("")
    lines.append(
        "> ⚠️ 本报告仅提供事实统计。Readiness 判定须由 Step 22 在人工审查后做出。"
    )

    return "\n".join(lines)


def write_aggregation_snapshot(
    agg: AggregationResult,
    output_dir: str | Path,
    errors: list[str] | None = None,
) -> dict[str, str]:
    """将聚合结果写入 timestamp snapshot 文件（不生成 latest）。

    Args:
        agg: 聚合结果
        output_dir: 输出目录
        errors: load_observations 返回的错误列表

    Returns:
        {"json": path, "markdown": path}
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    ts_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_name = f"precommit_memory_warn_aggregation_{ts_slug}.json"
    md_name = f"precommit_memory_warn_aggregation_{ts_slug}.md"

    # JSON
    json_path = out / json_name
    json_data = render_aggregation_json(agg, errors)
    json_path.write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Markdown
    md_path = out / md_name
    md_path.write_text(
        render_aggregation_markdown(agg),
        encoding="utf-8",
    )

    return {"json": str(json_path), "markdown": str(md_path)}


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════


def main(argv: list[str] | None = None) -> int:
    """CLI 入口 — Observation 聚合器（Step 21c）。"""
    parser = argparse.ArgumentParser(
        description="Pre-commit Warn Observation 聚合器（Step 21c）"
    )
    parser.add_argument(
        "--history-dir",
        default=_DEFAULT_HISTORY_DIR,
        help=f"observation 历史目录（默认 {_DEFAULT_HISTORY_DIR}）",
    )
    parser.add_argument(
        "--output-dir",
        default=_DEFAULT_OUTPUT_DIR,
        help=f"聚合报告输出目录（默认 {_DEFAULT_OUTPUT_DIR}）",
    )
    args = parser.parse_args(argv)

    # 加载
    observations, errors = load_observations(args.history_dir)

    if errors:
        for err in errors:
            print(f"[WARN] {err}", file=sys.stderr)

    # 聚合
    agg = aggregate(observations)
    agg.source_dir = args.history_dir
    agg.file_count_errors = len(errors)
    agg.error_files = errors

    # 输出简洁摘要
    print(f"observation_count: {agg.observation_count}")
    print(f"observation_span_days: {agg.observation_span_days}")
    print(f"meets_20_commits: {agg.meets_20_commits}")
    print(f"meets_7_days: {agg.meets_7_days}")
    print(f"recommendation: {agg.recommendation}")

    # 写入报告
    paths = write_aggregation_snapshot(agg, args.output_dir, errors)
    print("\n聚合报告已生成:")
    print(f"  JSON: {paths['json']}")
    print(f"  MD:   {paths['markdown']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
