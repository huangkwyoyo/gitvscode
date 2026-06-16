"""
PySpark DSL sample run 执行器。

M3 不假设 Spark 环境可用。没有 SparkSession 时返回 SKIPPED；
即使传入 SparkSession，本阶段也只保留只读 sample run 的接口边界，不写表、不落盘。
"""

from __future__ import annotations

from typing import Any

from src.ir.types import SQLResult


def execute_spark_dsl(
    code: str,
    spark_session: Any = None,
    timeout_seconds: int = 60,
    source_table: str = "",
) -> SQLResult:
    """执行 Spark DSL 草案；不可用时返回非 PASS 状态。"""
    if spark_session is None:
        return SQLResult(
            sql=code,
            error="SKIPPED: Spark 环境不可用，Spark sample run 跳过；Spark 执行尚未实现。",
            source_table=source_table,
        )

    _ = timeout_seconds
    return SQLResult(
        sql=code,
        error="PENDING: Spark 只读 sample run 尚未接入，尚未实现，不能标记 PASS。",
        source_table=source_table,
    )
