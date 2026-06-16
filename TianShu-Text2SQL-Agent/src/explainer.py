"""
结果解释器: SQLResult -> 中文回答.

职责:
    将 SQL 执行结果翻译为用户可理解的中文解释.
    标注数据来源、指标口径、值得注意的数据特征.

注意:
    当前为桩实现. 实际应由 LLM 根据结果 + Prompt 模板生成中文解释.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .ir import SQLResult

if TYPE_CHECKING:
    from .ir import UnifiedResponse


def explain_result(
    question: str,
    result: SQLResult,
) -> str:
    if result.error:
        return f"抱歉, 查询执行时出错: {result.error}. 数据来源: {result.source_table or '未知表'}."

    if result.row_count == 0:
        return (
            f"查询 [{question}] 未返回数据. "
            f"可能原因: 该时间范围内没有记录, 或过滤条件过严. "
            f"数据来源: {result.source_table or '未知表'}."
        )

    parts: list[str] = []
    parts.append(f"查询 [{question}] 返回 {result.row_count} 行.")

    if result.source_table:
        parts.append(f"数据来源: {result.source_table}.")

    if result.columns:
        parts.append(f"字段: {', '.join(result.columns[:10])}.")

    if result.rows:
        preview_lines = []
        for row in result.rows[:5]:
            values = [str(value) for value in row]
            preview_lines.append(", ".join(values))
        parts.append(f"前 {len(preview_lines)} 行样例: {'; '.join(preview_lines)}.")

    parts.append(f"执行耗时: {result.execution_time_ms}ms.")

    return " ".join(parts)


def fuse_results(
    question: str,
    unified_responses: list[UnifiedResponse],
) -> str:
    n = len(unified_responses)
    NL = chr(10)
    parts: list[str] = [
        f"该问题被拆分为 {n} 个查询计划分别执行.",
    ]

    for i, ur in enumerate(unified_responses):
        metrics_str = "、".join(ur.sub_intent.metrics) if ur.sub_intent else "未知指标"
        table = ur.sub_intent.planning_table if ur.sub_intent else "未知表"
        zh_metrics = _lookup_zh_names(ur)

        label = zh_metrics or metrics_str

        prefix = f"{NL}{i + 1}. 指标 {label}: 来自 {table} 表"

        if ur.result is None:
            parts.append(f"{prefix}, 未执行.")
            continue

        if ur.result.error:
            parts.append(f"{prefix}, 执行出错: {ur.result.error}")
            continue

        row_count = ur.result.row_count
        if row_count == 0:
            parts.append(f"{prefix}, 未返回数据.")
            continue

        parts.append(f"{prefix}, 返回 {row_count} 行.")

        if ur.result.columns and ur.result.rows:
            cols = ur.result.columns
            preview = []
            for row in ur.result.rows[:3]:
                values = []
                for j, val in enumerate(row):
                    col_name = cols[j] if j < len(cols) else f"col{j}"
                    values.append(f"{col_name}={val}")
                preview.append("{" + ", ".join(values) + "}")
            parts.append(f"   样例: {'; '.join(preview)}")

        if ur.result.rows and ur.result.columns:
            numeric_cols = _find_numeric_columns(ur)
            if numeric_cols:
                stats_parts = []
                for col_name, values in numeric_cols.items():
                    if values:
                        total = sum(values)
                        avg = total / len(values)
                        stats_parts.append(f"{col_name} 合计={total:.0f}, 日均={avg:.0f}")
                if stats_parts:
                    parts.append(f"   统计: {'; '.join(stats_parts)}")

    return NL.join(parts)


def _lookup_zh_names(ur: UnifiedResponse) -> str:
    if ur.plan and ur.plan.aggregations:
        names = [a.alias for a in ur.plan.aggregations]
        return "、".join(names)
    return ""


def _find_numeric_columns(ur: UnifiedResponse) -> dict[str, list[float]]:
    if not ur.result or not ur.result.columns or not ur.result.rows:
        return {}

    numeric: dict[str, list[float]] = {}
    for j, col_name in enumerate(ur.result.columns):
        values = []
        for row in ur.result.rows:
            if j < len(row):
                try:
                    val = float(row[j])
                    values.append(val)
                except (ValueError, TypeError):
                    pass
        if values and len(values) == ur.result.row_count:
            numeric[col_name] = values

    return numeric
