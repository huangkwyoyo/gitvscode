"""
结果解释器：SQLResult → 中文回答。

职责：
    将 SQL 执行结果翻译为用户可理解的中文解释。
    标注数据来源、指标口径、值得注意的数据特征。

注意：
    当前为桩实现。实际应由 LLM 根据结果 + Prompt 模板生成中文解释。
"""

from __future__ import annotations

from .ir import SQLResult


def explain_result(
    question: str,
    result: SQLResult,
) -> str:
    """
    将 SQL 执行结果解释为中文回答。

    当前为桩实现，生成基本的描述性文字。实际应由 LLM 根据结果生成。

    Args:
        question: 用户的原始问题
        result: SQL 执行结果

    Returns:
        中文解释字符串
    """
    if result.error:
        return f"抱歉，查询执行时出错：{result.error}"

    if result.row_count == 0:
        return (
            f"查询'{question}'未返回任何数据。"
            f"可能原因：该时间范围内没有记录，或过滤条件过严。"
            f"数据来源：{result.source_table or '未知表'}。"
        )

    # 桩：基本的统计描述
    parts: list[str] = []

    parts.append(f"查询'{question}'返回 {result.row_count} 行数据。")

    if result.columns:
        parts.append(f"包含 {len(result.columns)} 个字段：{'、'.join(result.columns[:10])}。")

    if result.source_table:
        parts.append(f"数据来源：{result.source_table}。")

    return " ".join(parts)
