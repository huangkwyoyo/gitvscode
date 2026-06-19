"""
SQLResult 结构摘要生成器。

职责：
    从 UnifiedResponse（含 SQLResult）中提取结构化摘要，供后续 date merge、
    LLM 融合、图表生成等环节使用。

约束（Phase B1）：
    - 只读取 SQLResult 已有数据，不访问原始大表
    - 不执行新 SQL
    - 不推断因果、不补造数据
    - date_min/date_max 只能来自结果中真实的 date 列
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Optional

from .ir import (
    MergeStatus,
    MergedResult,
    ResultSummary,
    SQLResult,
    Strategy,
    UnifiedResponse,
)


def summarize_sql_result(
    ur: UnifiedResponse,
    plan_index: int = 1,
) -> ResultSummary:
    """
    从 UnifiedResponse 生成 ResultSummary。

    只做结构化提取，不做业务解释。所有字段值均来自 SQLResult 的已有数据。

    Args:
        ur: 统一响应（含 sub_intent、plan、result）
        plan_index: 计划序号（从 1 开始），用于 source_plan_index

    Returns:
        ResultSummary 包含结构化的列信息、行数、样本行、日期范围等。
        如果 ur.result 为空，返回空摘要（row_count=0，warnings 含提示）。
    """
    # ── 提取指标和维度 ──
    metrics: list[str] = []
    dimensions: list[str] = []
    if ur.sub_intent is not None:
        metrics = list(ur.sub_intent.metrics)
        dimensions = list(ur.sub_intent.dimensions) if ur.sub_intent.dimensions else []

    # ── 提取策略和表名 ──
    strategy = ""
    primary_table = ""
    if ur.plan is not None:
        strategy = ur.plan.strategy.value if ur.plan.strategy else ""
        primary_table = ur.plan.primary_table or ""

    # ── 处理空结果 ──
    result = ur.result
    if result is None:
        return ResultSummary(
            source_plan_index=plan_index,
            metrics=metrics,
            dimensions=dimensions,
            primary_table=primary_table,
            strategy=strategy,
            columns=[],
            column_types=[],
            row_count=0,
            sample_rows=[],
            has_date_column=False,
            grain="unknown",
            date_min="",
            date_max="",
            warnings=["结果为空（result=None）"],
        )

    warnings: list[str] = []

    # ── 行数为 0 的警告 ──
    if result.row_count == 0 and not result.error:
        warnings.append("查询结果为空，可能时间范围内无数据或过滤条件过严")

    # ── 检测日期列 ──
    date_col_index = _find_date_column(result.columns, result.column_types)
    has_date = date_col_index is not None

    # ── 提取日期范围和粒度 ──
    grain = "unknown"
    date_min = ""
    date_max = ""
    if has_date and result.rows:
        dates = _extract_date_values(result.rows, date_col_index)  # type: ignore[arg-type]
        if dates:
            dates_sorted = sorted(dates)
            date_min = dates_sorted[0].isoformat()[:10]  # "YYYY-MM-DD"
            date_max = dates_sorted[-1].isoformat()[:10]
            grain = _detect_grain(dates_sorted)
        if not dates:
            warnings.append(f"日期列 '{result.columns[date_col_index]}' 无有效日期值")

    # ── 提取样本行（前 5 行，值转为可序列化格式）──
    sample_rows = _extract_sample_rows(result.rows, result.column_types, max_rows=5)

    # ── 确保列类型全是字符串（DuckDB 可能返回 DuckDBPyType 对象）──
    safe_column_types = [str(ct) for ct in result.column_types]

    return ResultSummary(
        source_plan_index=plan_index,
        metrics=metrics,
        dimensions=dimensions,
        primary_table=primary_table,
        strategy=strategy,
        columns=list(result.columns),
        column_types=safe_column_types,
        row_count=result.row_count,
        sample_rows=sample_rows,
        has_date_column=has_date,
        grain=grain,
        date_min=date_min,
        date_max=date_max,
        warnings=warnings,
    )


def make_merged_result(
    summaries: list[ResultSummary],
    merge_status: MergeStatus = MergeStatus.NOT_ATTEMPTED,
    reason: str = "",
) -> MergedResult:
    """
    从多个 ResultSummary 构造 MergedResult 骨架。

    Phase B1：只构建结构，不做真正合并。
    默认 merge_status = NOT_ATTEMPTED。

    Args:
        summaries: 来源摘要列表
        merge_status: 合并状态（默认 not_attempted）
        reason: 状态说明

    Returns:
        MergedResult 包含来源摘要，merge_status 标记为未尝试。
    """
    plan_indexes = [s.source_plan_index for s in summaries]
    total_rows = sum(s.row_count for s in summaries)

    return MergedResult(
        merge_status=merge_status,
        merge_key="",
        columns=[],
        rows=[],
        row_count=total_rows,
        source_plan_indexes=plan_indexes,
        source_summaries=list(summaries),
        merge_warnings=[],
        reason=reason or _default_reason(merge_status),
    )


# ═══════════════════════════════════════════════════════════
# 内部辅助函数
# ═══════════════════════════════════════════════════════════


def _find_date_column(
    columns: list[str],
    column_types: list[str],
) -> Optional[int]:
    """
    查找结果中的日期列。

    策略：
        1. 优先按列类型：TIMESTAMP、DATE、DATETIME
        2. 其次按列名：包含 "date" 或 "time" 的列

    Returns:
        日期列的索引（从 0 开始），无日期列返回 None。
    """
    # 策略 1：按类型匹配
    date_types = {"TIMESTAMP", "DATE", "DATETIME"}
    for i, col_type in enumerate(column_types):
        # DuckDB 的 column_types 可能是 DuckDBPyType 对象，需转为字符串比较
        if str(col_type).upper() in date_types:
            return i

    # 策略 2：按列名匹配（回退）
    for i, col_name in enumerate(columns):
        lower = col_name.lower()
        if "date" in lower or "time" in lower:
            return i

    return None


def _extract_date_values(
    rows: list[tuple],
    date_col_index: int,
) -> list[_dt.date]:
    """
    从数据行中提取日期值列表。

    兼容 Python datetime.date / datetime.datetime / ISO 字符串格式。
    无法解析的值静默跳过。

    Args:
        rows: SQL 结果行
        date_col_index: 日期列索引

    Returns:
        有效的 date 对象列表
    """
    dates: list[_dt.date] = []
    for row in rows:
        if date_col_index >= len(row):
            continue
        val = row[date_col_index]
        parsed = _coerce_to_date(val)
        if parsed is not None:
            dates.append(parsed)
    return dates


def _coerce_to_date(val: Any) -> Optional[_dt.date]:
    """
    将值转为 datetime.date。

    支持：datetime.date / datetime.datetime / ISO 字符串（"2026-01-01"）。
    datetime.datetime 通过 .date() 转为纯日期对象。
    """
    if val is None:
        return None
    if isinstance(val, _dt.datetime):
        return val.date()  # datetime → date
    if isinstance(val, _dt.date):
        return val
    if isinstance(val, str):
        try:
            # 尝试 ISO 格式
            return _dt.date.fromisoformat(val[:10])
        except (ValueError, TypeError):
            return None
    return None


def _detect_grain(dates_sorted: list[_dt.date]) -> str:
    """
    根据日期序列推断时间粒度。

    规则：
        - 仅 1 行 → unknown（不足以判断）
        - 相邻日期差全为 1 天 → daily
        - 其他 → unknown

    Args:
        dates_sorted: 已排序的日期列表

    Returns:
        "daily" 或 "unknown"
    """
    if len(dates_sorted) < 2:
        return "unknown"

    # 检查是否所有相邻日期差均为 1 天
    for i in range(1, len(dates_sorted)):
        delta = (dates_sorted[i] - dates_sorted[i - 1]).days
        if delta != 1:
            return "unknown"

    return "daily"


def _extract_sample_rows(
    rows: list[tuple],
    column_types: list[str],
    max_rows: int = 5,
) -> list[list]:
    """
    提取前 N 行样本数据，将复杂类型转为 JSON 可序列化格式。

    - datetime.date / datetime.datetime → ISO 字符串
    - 其他类型 → str() 回退

    Args:
        rows: SQL 结果行
        column_types: 列类型列表（用于判断转换策略）
        max_rows: 最多取前 N 行

    Returns:
        序列化后的样本行列表（list of list）
    """
    samples: list[list] = []
    for row in rows[:max_rows]:
        sample_row: list = []
        for j, val in enumerate(row):
            col_type = column_types[j] if j < len(column_types) else ""
            sample_row.append(_serialize_value(val, col_type))
        samples.append(sample_row)
    return samples


def _serialize_value(val: Any, col_type: str = "") -> Any:
    """
    将单个值转为 JSON 可序列化格式。

    - datetime → ISO 字符串
    - date → ISO 字符串
    - 其他 → 保持原值（int/float/str/None）
    """
    if val is None:
        return None
    if isinstance(val, (_dt.datetime, _dt.date)):
        return val.isoformat()
    # int / float / str / bool 已是 JSON 可序列化
    if isinstance(val, (int, float, str, bool)):
        return val
    # 其他类型 → 字符串回退
    return str(val)


def _default_reason(status: MergeStatus) -> str:
    """MergeStatus 的默认原因说明"""
    reasons = {
        MergeStatus.NOT_ATTEMPTED: "Phase B1：未执行合并（数据结构预留）",
        MergeStatus.SKIPPED: "Phase B1：已跳过（数据结构预留）",
        MergeStatus.MERGED: "",
        MergeStatus.FAILED: "",
    }
    return reasons.get(status, "")
