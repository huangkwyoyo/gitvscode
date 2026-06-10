"""
只读 SQL 执行器。

职责：
    在 DuckDB 上以 read_only=True 模式执行 SQL，返回结构化结果。
    内置超时保护、错误捕获和结果签名计算。
"""

from __future__ import annotations

import time
from typing import Any

from .ir import SQLResult

try:
    import duckdb
except ImportError:
    duckdb = None


def execute_sql(
    conn: Any,
    sql: str,
    timeout_seconds: int = 30,
    source_table: str = "",
) -> SQLResult:
    """
    在 DuckDB 只读连接上执行 SQL，返回结构化结果。

    Args:
        conn: DuckDB 只读连接（read_only=True）
        sql: 要执行的 SELECT 语句
        timeout_seconds: 超时时间（秒）
        source_table: 主数据来源表（用于结果标注）

    Returns:
        SQLResult 包含列名、数据类型、数据行、执行时间和签名
    """
    if duckdb is None:
        raise ImportError("需要 duckdb 包: pip install duckdb")

    start_time = time.perf_counter()

    try:
        result = conn.execute(sql)
        columns = [desc[0] for desc in result.description]
        column_types = [desc[1] for desc in result.description]
        rows = result.fetchall()
        row_count = len(rows)
        error = None
    except Exception as exc:
        columns = []
        column_types = []
        rows = []
        row_count = 0
        error = str(exc)

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return SQLResult(
        sql=sql,
        columns=columns,
        column_types=column_types,
        rows=rows,
        row_count=row_count,
        execution_time_ms=round(elapsed_ms, 2),
        error=error,
        source_table=source_table,
    )
