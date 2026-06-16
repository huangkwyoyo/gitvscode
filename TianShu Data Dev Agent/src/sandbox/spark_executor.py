"""
PySpark DSL 执行器——数据执行边界的第二通道。

Phase 3 实现完整逻辑。Phase 1 仅定义接口和数据类型。
"""

from __future__ import annotations

from typing import Any, Optional

from src.ir.types import SQLResult


def execute_spark_dsl(
    code: str,
    spark_session: Any = None,
    timeout_seconds: int = 60,
    source_table: str = "",
) -> SQLResult:
    """
    执行 PySpark DSL 代码并返回结构化结果。

    Phase 3 实现。当前为占位桩——Spark 环境不可用时返回 SKIPPED 状态。

    Args:
        code: PySpark DSL 代码字符串
        spark_session: SparkSession 实例（None 时无法执行）
        timeout_seconds: 超时时间（秒），默认 60 秒
        source_table: 主数据来源表

    Returns:
        SQLResult——Phase 1 始终返回 error（NotImplementedError）
    """
    if spark_session is None:
        return SQLResult(
            sql=code,
            error="PySpark 执行器尚未实现——Spark 环境不可用。待 Phase 3 实现。",
            source_table=source_table,
        )

    # Phase 3 实现：通过 spark_session 执行 PySpark 代码，
    # 收集结果并转为 SQLResult 格式（列名、行数据等）
    return SQLResult(
        sql=code,
        error="PySpark 执行器尚未实现。Phase 3 待实现。",
        source_table=source_table,
    )
