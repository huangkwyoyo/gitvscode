"""
SQL 与 Spark 结果交叉验证。

M3 阶段只做基础比较：行数、列名、抽样行，以及可识别数值列的合计。
交叉验证只产出审查信号，不自动修复代码，也不替代人工审批。
"""

from __future__ import annotations

import math
from typing import Optional

from src.ir.types import CrossValidateStatus, CrossValidationResult, SQLResult


def compare_results(
    sql_result: Optional[SQLResult] = None,
    spark_result: Optional[SQLResult] = None,
    tolerance: float = 0.001,
) -> CrossValidationResult:
    """比较 SQL 与 Spark sample run 结果。"""
    if sql_result is None and spark_result is None:
        return CrossValidationResult(
            status=CrossValidateStatus.NOT_ATTEMPTED,
            detail="没有 SQL/Spark 执行结果，交叉验证未尝试。",
        )

    if sql_result is None:
        return CrossValidationResult(
            status=CrossValidateStatus.SKIPPED,
            spark_row_count=spark_result.row_count if spark_result else 0,
            detail="SQL 结果缺失，交叉验证不能通过。",
        )

    if spark_result is None:
        return CrossValidationResult(
            status=CrossValidateStatus.SKIPPED,
            sql_row_count=sql_result.row_count,
            detail="Spark 结果缺失或不可用，交叉验证跳过。",
        )

    if sql_result.error:
        return CrossValidationResult(
            status=CrossValidateStatus.SKIPPED,
            sql_row_count=sql_result.row_count,
            spark_row_count=spark_result.row_count,
            detail=f"SQL sample run 失败，交叉验证跳过: {sql_result.error}",
        )

    if spark_result.error:
        return CrossValidationResult(
            status=CrossValidateStatus.SKIPPED,
            sql_row_count=sql_result.row_count,
            spark_row_count=spark_result.row_count,
            detail=f"Spark sample run 失败或不可用，交叉验证跳过: {spark_result.error}",
        )

    diffs: list[dict] = []
    column_match = sql_result.columns == spark_result.columns
    if not column_match:
        diffs.append({
            "type": "columns",
            "sql": sql_result.columns,
            "spark": spark_result.columns,
        })

    if sql_result.row_count != spark_result.row_count:
        diffs.append({
            "type": "row_count",
            "sql": sql_result.row_count,
            "spark": spark_result.row_count,
        })

    sql_sample = list(sql_result.rows[:5])
    spark_sample = list(spark_result.rows[:5])
    if sql_sample != spark_sample:
        diffs.append({
            "type": "sample_rows",
            "sql": sql_sample,
            "spark": spark_sample,
        })

    diffs.extend(_compare_numeric_sums(sql_result, spark_result, tolerance))

    if diffs:
        return CrossValidationResult(
            status=CrossValidateStatus.INCONSISTENT,
            sql_row_count=sql_result.row_count,
            spark_row_count=spark_result.row_count,
            column_match=column_match,
            value_diffs=diffs,
            detail="SQL 与 Spark 结果存在差异，进入人工审查。",
        )

    return CrossValidationResult(
        status=CrossValidateStatus.CONSISTENT,
        sql_row_count=sql_result.row_count,
        spark_row_count=spark_result.row_count,
        column_match=True,
        value_diffs=[],
        detail=(
            "行数、列名、抽样行与数值合计一致（LIMIT 1000 样本）。"
            "注意：样本一致不代表全量数据一致、业务正确或生产就绪——"
            "交叉验证只能发现两份代码逻辑不一致，不能证明两份代码都正确。"
        ),
    )


def _compare_numeric_sums(
    sql_result: SQLResult,
    spark_result: SQLResult,
    tolerance: float,
) -> list[dict]:
    """比较同名数值列合计，避免抽样行一致但汇总值漂移。"""
    if sql_result.columns != spark_result.columns:
        return []

    diffs: list[dict] = []
    for index, name in enumerate(sql_result.columns):
        sql_values = [_as_number(row[index]) for row in sql_result.rows if len(row) > index]
        spark_values = [_as_number(row[index]) for row in spark_result.rows if len(row) > index]
        sql_nums = [value for value in sql_values if value is not None]
        spark_nums = [value for value in spark_values if value is not None]
        if not sql_nums and not spark_nums:
            continue

        sql_sum = sum(sql_nums)
        spark_sum = sum(spark_nums)
        allowed = max(abs(sql_sum), abs(spark_sum), 1.0) * tolerance
        if abs(sql_sum - spark_sum) > allowed:
            diffs.append({
                "type": "numeric_sum",
                "column": name,
                "sql": sql_sum,
                "spark": spark_sum,
                "tolerance": tolerance,
            })
    return diffs


def _as_number(value: object) -> float | None:
    """只把明确的数字值纳入数值合计。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None
