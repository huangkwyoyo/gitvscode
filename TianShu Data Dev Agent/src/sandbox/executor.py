"""
只读 SQL 执行器——数据执行边界的唯一入口。

从 TianShu-Text2SQL-Agent/src/executor.py 移植，适配 v2.0 IR 类型。

职责：
    在 DuckDB 上以 read_only=True 模式执行 SQL，返回结构化 SQLResult。
    内置超时保护（通过线程中断 DuckDB 查询）、错误捕获和结果签名计算。

超时机制：
    DuckDB 1.x 不提供 statement_timeout 配置参数。
    使用 threading.Timer 实现超时：超时后调用 conn.interrupt() 中断正在执行的查询，
    DuckDB 会抛出 InterruptException 被 error 捕获。
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Optional

from src.ir.types import SQLResult

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

    启用超时保护：执行前启动定时器线程，超时后调用 conn.interrupt()
    中断正在执行的查询。查询正常完成后取消定时器，避免资源泄漏。

    Args:
        conn: DuckDB 只读连接（read_only=True）
        sql: 要执行的 SELECT 语句
        timeout_seconds: 超时时间（秒），默认 30 秒。设为 0 禁用超时
        source_table: 主数据来源表（用于结果标注）

    Returns:
        SQLResult 包含列名、数据类型、数据行、执行时间和签名

    Raises:
        ImportError: duckdb 包未安装
    """
    if duckdb is None:
        raise ImportError("需要 duckdb 包: pip install duckdb")

    start_time = time.perf_counter()

    # ── 超时中断定时器 ──
    # 守护线程在查询完成后自动取消，超时未完成则中断 DuckDB 查询
    interrupt_timer: Optional[threading.Timer] = None
    if timeout_seconds > 0:

        def _interrupt():
            """超时回调：中断 DuckDB 当前查询"""
            try:
                conn.interrupt()
            except Exception:
                pass  # 连接可能已关闭

        interrupt_timer = threading.Timer(timeout_seconds, _interrupt)
        interrupt_timer.daemon = True  # 守护线程，主线程退出时自动清理
        interrupt_timer.start()

    try:
        # ── 执行查询 ──
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

    finally:
        # ── 取消超时定时器（查询已完成，不需要中断）──
        if interrupt_timer is not None:
            interrupt_timer.cancel()

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


def execute_sql_sample(
    conn: Any,
    sql: str,
    limit: int = 1000,
    timeout_seconds: int = 30,
    source_table: str = "",
) -> SQLResult:
    """执行只读 SQL sample run，并强制限行限时。"""
    if conn is None:
        return SQLResult(
            sql=sql,
            error="SKIPPED: 未提供开发库或 sample 数据源，SQL sample run 跳过。",
            source_table=source_table,
        )

    body = _strip_sql_comments(sql).strip().rstrip(";")
    if not body.upper().startswith("SELECT"):
        return SQLResult(
            sql=sql,
            error="SQL sample run 被拒绝：只允许 SELECT 查询。",
            source_table=source_table,
        )

    forbidden = [
        "CREATE", "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
        "TRUNCATE", "MERGE", "COPY", "EXPORT", "ATTACH", "INSTALL", "LOAD",
    ]
    upper = body.upper()
    for keyword in forbidden:
        if re.search(rf"\b{keyword}\b", upper):
            return SQLResult(
                sql=sql,
                error=f"SQL sample run 被拒绝：检测到禁止关键字 {keyword}。",
                source_table=source_table,
            )

    wrapped = body
    if not re.search(r"\bLIMIT\b", upper):
        wrapped = f"SELECT * FROM ({body}) AS v2_sample LIMIT {int(limit)}"

    return execute_sql(
        conn=conn,
        sql=wrapped,
        timeout_seconds=timeout_seconds,
        source_table=source_table,
    )


def _strip_sql_comments(sql: str) -> str:
    """去除 SQL 注释，避免注释内容影响安全判断。"""
    without_line = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    return re.sub(r"/\*.*?\*/", "", without_line, flags=re.DOTALL)
