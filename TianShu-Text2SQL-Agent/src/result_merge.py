"""
严格 date merge —— 跨表多计划结果按 date 对齐合并。

职责：
    在满足全部安全条件时，将多个 UnifiedResponse 的结果按 date 列做结果层合并。
    这是结果层 merge，不是 SQL 层跨表 JOIN。

安全条件（必须全部满足）：
    1. 所有子结果都有 date 列
    2. 所有子结果 grain 都是 daily
    3. date 范围一致（如不一致，记录 warning 仍执行 outer merge）
    4. 每个子结果中每个 date 最多一行
    5. merge key 只能是 date
    6. 所有结果来自已执行完成的 SQLResult
    7. 每个 source result 可追溯到 source_plan_index

约束（Phase B2）：
    - 不允许 SQL 层跨业务表 JOIN
    - 不允许多 key 自动猜测
    - 不允许不同 grain 强行合并
    - 不允许缺 date 列时强行合并
    - 不允许把 merge 结果解释成因果关系
    - 不允许 LLM 决定是否 merge
"""

from __future__ import annotations

import datetime as _dt
from collections import OrderedDict
from typing import Any, Optional

from .ir import (
    MergeStatus,
    MergedResult,
    ResultSummary,
    UnifiedResponse,
)
from .result_summary import (
    _coerce_to_date,
    _find_date_column,
    summarize_sql_result,
)


# ═══════════════════════════════════════════════════════════
# 合并条件检查
# ═══════════════════════════════════════════════════════════


def can_merge_on_date(summaries: list[ResultSummary]) -> tuple[bool, list[str]]:
    """
    检查多个 ResultSummary 是否满足按 date 合并的全部条件。

    条件（必须全部通过）：
        1. 至少有 2 个摘要
        2. 所有摘要都有 date 列
        3. 所有摘要 grain 都是 daily
        4. 每个摘要中每个 date 最多一行（无重复 date）
        5. 所有摘要的 date 范围一致（不一致仅记录，不阻断）

    Args:
        summaries: ResultSummary 列表

    Returns:
        (True, []) 表示可以合并
        (False, ["原因1", "原因2"]) 表示不能合并及原因列表
    """
    reasons: list[str] = []

    # ── 条件 1: 至少 2 个结果 ──
    if len(summaries) < 2:
        reasons.append("至少需要 2 个结果才能合并")
        return False, reasons

    # ── 条件 2: 所有结果都有 date 列 ──
    for s in summaries:
        if not s.has_date_column:
            reasons.append(
                f"计划{s.source_plan_index}（{', '.join(s.metrics)}）缺少 date 列"
            )
    if reasons:
        return False, reasons

    # ── 条件 3: 所有结果 grain 都是 daily ──
    for s in summaries:
        if s.grain != "daily":
            reasons.append(
                f"计划{s.source_plan_index}（{', '.join(s.metrics)}）"
                f"grain={s.grain}，需要 daily"
            )
    if reasons:
        return False, reasons

    # ── 条件 4: 每个结果中每个 date 最多一行 ──
    for s in summaries:
        # 通过 sample_rows 无法判断是否有重复 date。
        # 必须在 merge 时检查（merge_results_on_date 遍历原始 rows 时检测）。
        # 此处只做前置检查——如果 row_count 和 date 范围天数一致，
        # 大概率无重复；如果不一致，不一定有重复（可能只是日期不连续）。
        # 实际重复检测延迟到 merge 阶段。
        pass

    # ── 条件 5: merge key 只能是 date（硬约束，不检查其他 key）──

    # ── 条件 6-7: 结果来自已执行完成的 SQLResult + 可追溯到 source_plan_index ──
    for s in summaries:
        if s.row_count == 0 and not s.warnings:
            reasons.append(
                f"计划{s.source_plan_index}（{', '.join(s.metrics)}）结果为空"
            )
    if reasons:
        return False, reasons

    return True, []


# ═══════════════════════════════════════════════════════════
# 结果层 date merge
# ═══════════════════════════════════════════════════════════


def merge_results_on_date(
    responses: list[UnifiedResponse],
) -> MergedResult:
    """
    将多个 UnifiedResponse 按 date 列做结果层合并。

    流程：
        1. 为每个 response 生成 ResultSummary
        2. 调用 can_merge_on_date() 检查条件
        3. 条件通过 → 执行 date-by-date 对齐合并
        4. 条件不通过 → 返回 merge_status=skipped + 原因

    合并策略（outer merge）：
        - 收集所有来源的全部日期
        - 对每个日期，从各来源查找对应指标值
        - 某来源缺少某日期时填充 None，记录 warning
        - columns = ["date"] + 各来源的指标列（按 plan_index 顺序）

    Args:
        responses: 已执行的 UnifiedResponse 列表（含 result）

    Returns:
        MergedResult，merge_status 为 merged / skipped / failed
    """
    # ── Step 1: 生成摘要 ──
    summaries: list[ResultSummary] = []
    for i, ur in enumerate(responses):
        summary = summarize_sql_result(ur, plan_index=i + 1)
        summaries.append(summary)

    # ── Step 2: 检测重复 date（优先于 grain，防止重复干扰 grain 检测）──
    dup_reasons = _check_duplicate_dates(responses, summaries)
    if dup_reasons:
        return _make_skipped(summaries, "; ".join(dup_reasons))

    # ── Step 3: 检查合并条件（grain、date 列、范围等）──
    can_merge, reasons = can_merge_on_date(summaries)
    if not can_merge:
        return _make_skipped(summaries, "; ".join(reasons))

    # ── Step 4: 执行 date-by-date outer merge ──
    try:
        return _do_merge(responses, summaries)
    except Exception as exc:
        return MergedResult(
            merge_status=MergeStatus.FAILED,
            merge_key="date",
            source_plan_indexes=[s.source_plan_index for s in summaries],
            source_summaries=summaries,
            reason=f"合并异常: {exc}",
        )


# ═══════════════════════════════════════════════════════════
# 内部实现
# ═══════════════════════════════════════════════════════════


def _check_duplicate_dates(
    responses: list[UnifiedResponse],
    summaries: list[ResultSummary],
) -> list[str]:
    """
    检查每个来源结果中是否存在同一 date 的多行数据。

    Returns:
        重复 date 的描述列表（空 = 全部通过）
    """
    reasons: list[str] = []
    for i, ur in enumerate(responses):
        result = ur.result
        if result is None or not result.rows:
            continue
        summary = summaries[i]
        date_idx = _find_date_column(result.columns, result.column_types)
        if date_idx is None:
            continue

        date_counts: dict[_dt.date, int] = {}
        for row in result.rows:
            d = _coerce_to_date(row[date_idx])
            if d is not None:
                date_counts[d] = date_counts.get(d, 0) + 1

        duplicates = [d for d, cnt in date_counts.items() if cnt > 1]
        if duplicates:
            dup_str = ", ".join(str(d) for d in sorted(duplicates)[:5])
            if len(duplicates) > 5:
                dup_str += f" 等 {len(duplicates)} 个重复日期"
            reasons.append(
                f"计划{summary.source_plan_index}（{', '.join(summary.metrics)}）"
                f"存在重复 date: {dup_str}"
            )

    return reasons


def _do_merge(
    responses: list[UnifiedResponse],
    summaries: list[ResultSummary],
) -> MergedResult:
    """
    执行 date-by-date outer merge。
    """
    merge_warnings: list[str] = []

    # ── 按来源提取 date → (date_obj, {metric_name: value}) 映射 ──
    # sources[i] = {date_obj: {metric_col: value, ...}}
    sources: list[dict[_dt.date, dict[str, Any]]] = []
    source_metric_names: list[list[str]] = []  # 每个来源的指标列名（非 date 列）

    for i, ur in enumerate(responses):
        result = ur.result
        summary = summaries[i]
        if result is None or not result.rows:
            sources.append({})
            source_metric_names.append([])
            continue

        date_idx = _find_date_column(result.columns, result.column_types)
        if date_idx is None:
            sources.append({})
            source_metric_names.append([])
            continue

        # 非 date 列全部作为指标列
        metric_cols = [
            col for j, col in enumerate(result.columns) if j != date_idx
        ]
        source_metric_names.append(metric_cols)

        date_map: dict[_dt.date, dict[str, Any]] = {}
        for row in result.rows:
            d = _coerce_to_date(row[date_idx])
            if d is None:
                continue
            # 按列名提取非 date 列的值
            values: dict[str, Any] = {}
            for j, col in enumerate(result.columns):
                if j == date_idx:
                    continue
                values[col] = row[j] if j < len(row) else None
            date_map[d] = values
        sources.append(date_map)

    # ── 检查日期范围一致性 ──
    ranges = _check_range_consistency(sources, summaries)
    if ranges["has_mismatch"]:
        merge_warnings.append(
            f"date 范围不一致: "
            + "; ".join(
                f"计划{idx}={rng}"
                for idx, rng in ranges["per_source"].items()
            )
        )

    # ── 收集所有日期（outer merge）──
    all_dates: set[_dt.date] = set()
    for date_map in sources:
        all_dates.update(date_map.keys())
    all_dates_sorted = sorted(all_dates)

    # ── 构建合并后的列名 ──
    merged_columns = ["date"]
    for i, metric_names in enumerate(source_metric_names):
        for mname in metric_names:
            # 避免重名列（如两个 plan 都有 "date" 之外的相同列名）
            if mname in merged_columns:
                mname = f"{mname}_{summaries[i].source_plan_index}"
            merged_columns.append(mname)

    # ── 构建合并后的行 ──
    merged_rows: list[list] = []
    for d in all_dates_sorted:
        row: list = [d]
        for i, date_map in enumerate(sources):
            values = date_map.get(d)
            if values is None:
                # 该日期在来源 i 中不存在 → None 填充
                for _ in source_metric_names[i]:
                    row.append(None)
                merge_warnings.append(
                    f"日期 {d.isoformat()[:10]} 在计划"
                    f"{summaries[i].source_plan_index}（"
                    f"{', '.join(summaries[i].metrics)}）中不存在"
                )
            else:
                for mname in source_metric_names[i]:
                    row.append(values.get(mname))
        merged_rows.append(row)

    # ── 去重 merge_warnings（同一类警告只保留一条摘要）──
    if len(merge_warnings) > 10:
        # 大量逐行警告时压缩为摘要
        missing_summary: dict[int, int] = {}  # plan_index → missing count
        for w in merge_warnings:
            for s in summaries:
                if f"计划{s.source_plan_index}" in w:
                    missing_summary[s.source_plan_index] = (
                        missing_summary.get(s.source_plan_index, 0) + 1
                    )
        merge_warnings = [
            f"计划{idx} 缺失 {cnt} 个日期的数据"
            for idx, cnt in sorted(missing_summary.items())
        ]
        if ranges["has_mismatch"]:
            merge_warnings.insert(
                0,
                f"date 范围不一致: "
                + "; ".join(
                    f"计划{idx}={rng}"
                    for idx, rng in ranges["per_source"].items()
                ),
            )

    return MergedResult(
        merge_status=MergeStatus.MERGED,
        merge_key="date",
        columns=merged_columns,
        rows=merged_rows,
        row_count=len(merged_rows),
        source_plan_indexes=[s.source_plan_index for s in summaries],
        source_summaries=summaries,
        merge_warnings=merge_warnings,
        reason="",
    )


def _check_range_consistency(
    sources: list[dict[_dt.date, dict[str, Any]]],
    summaries: list[ResultSummary],
) -> dict[str, Any]:
    """
    检查各来源的日期范围是否一致。

    Returns:
        {
            "has_mismatch": bool,
            "per_source": {plan_index: "YYYY-MM-DD ~ YYYY-MM-DD"},
        }
    """
    per_source: dict[int, str] = {}
    overall_min: Optional[_dt.date] = None
    overall_max: Optional[_dt.date] = None

    for i, date_map in enumerate(sources):
        if not date_map:
            per_source[summaries[i].source_plan_index] = "无数据"
            continue
        dates_sorted = sorted(date_map.keys())
        dmin = dates_sorted[0]
        dmax = dates_sorted[-1]
        per_source[summaries[i].source_plan_index] = (
            f"{dmin.isoformat()[:10]} ~ {dmax.isoformat()[:10]}"
        )
        if overall_min is None or dmin < overall_min:
            overall_min = dmin
        if overall_max is None or dmax > overall_max:
            overall_max = dmax

    has_mismatch = False
    if len(sources) >= 2 and overall_min is not None and overall_max is not None:
        for date_map in sources:
            if not date_map:
                has_mismatch = True
                break
            dates_sorted = sorted(date_map.keys())
            if dates_sorted[0] != overall_min or dates_sorted[-1] != overall_max:
                has_mismatch = True
                break

    return {"has_mismatch": has_mismatch, "per_source": per_source}


def _make_skipped(summaries: list[ResultSummary], reason: str) -> MergedResult:
    """构造 merge_status=skipped 的 MergedResult"""
    return MergedResult(
        merge_status=MergeStatus.SKIPPED,
        merge_key="",
        columns=[],
        rows=[],
        row_count=sum(s.row_count for s in summaries),
        source_plan_indexes=[s.source_plan_index for s in summaries],
        source_summaries=summaries,
        merge_warnings=[],
        reason=reason,
    )
