"""
交叉验证引擎——防线 2 检查项 #7 的具体实现。

Phase 3 实现完整对比逻辑。Phase 1 仅定义接口和数据结构。

交叉验证的核心思想：
  - SQL（DuckDB）和 Spark DSL（PySpark）两份代码独立生成
  - 分别执行后对比行数、列名、值分布、抽样行
  - 两份代码很难犯完全相同的逻辑错误
  - 一致 → 置信度大幅提高；不一致 → 至少一份有错

Phase 3 实现计划：
  - compare_results()：接收两个 SQLResult，逐项对比
  - 容差控制：float 列的数值差异在 0.1% 内视为一致
  - 抽样行对比：取前 5 行逐行逐列比较
"""

from __future__ import annotations

from typing import Optional

from src.ir.types import (
    CrossValidationResult, CrossValidateStatus, SQLResult,
)


def compare_results(
    sql_result: Optional[SQLResult] = None,
    spark_result: Optional[SQLResult] = None,
    tolerance: float = 0.001,
) -> CrossValidationResult:
    """
    比较 SQL 和 Spark DSL 的执行结果。

    Phase 3 实现完整对比。Phase 1 返回 SKIPPED。

    Args:
        sql_result: DuckDB SQL 执行结果
        spark_result: PySpark DSL 执行结果
        tolerance: 数值差异容差（默认 0.1%）

    Returns:
        CrossValidationResult
    """
    if sql_result is None and spark_result is None:
        return CrossValidationResult(
            status=CrossValidateStatus.NOT_ATTEMPTED,
            detail="无执行结果——交叉验证未尝试",
        )

    if spark_result is None:
        return CrossValidationResult(
            status=CrossValidateStatus.SKIPPED,
            detail="Spark DSL 执行结果不可用——交叉验证跳过（仅 SQL 执行模式）",
        )

    if sql_result is None:
        return CrossValidationResult(
            status=CrossValidateStatus.SKIPPED,
            detail="SQL 执行结果不可用——交叉验证跳过",
        )

    # ── Phase 3 实现以下对比逻辑 ──
    # 1. 行数对比：sql_result.row_count vs spark_result.row_count
    # 2. 列名对比：sql_result.columns vs spark_result.columns（排序后比较）
    # 3. 值分布对比：对数值列计算 min/max/avg，差异在容差内
    # 4. 抽样行对比：取前 5 行逐行逐列比较

    # Phase 1 返回 NOT_ATTEMPTED
    return CrossValidationResult(
        status=CrossValidateStatus.NOT_ATTEMPTED,
        detail="交叉验证引擎仍未启用（Phase 3 实现完整对比逻辑）",
    )
