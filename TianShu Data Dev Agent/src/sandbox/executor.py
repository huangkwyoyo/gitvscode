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
from src.verify.checks import FORBIDDEN_KEYWORDS, ALLOWED_PREFIXES

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

    # ── 安全前缀检查（防御纵深——与 execute_sql_sample 对齐，拦截非只读语句）──
    body = _strip_sql_comments(sql).strip().rstrip(";")
    upper = body.upper()

    if not any(upper.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        return SQLResult(
            sql=sql,
            error=(
                f"安全拦截：SQL 必须以 {' / '.join(ALLOWED_PREFIXES)} 开头，"
                f"当前以 {upper.split()[0] if upper.split() else '(空)'} 开头"
            ),
            source_table=source_table,
        )

    # ── 安全关键字检查（防御纵深——即使绕过 execute_sql_sample 直接调用也拦截）──
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper):
            return SQLResult(
                sql=sql,
                error=f"安全拦截：检测到禁止关键字 {keyword}（{FORBIDDEN_KEYWORDS[keyword]}）。",
                source_table=source_table,
            )

    start_time = time.perf_counter()

    # ── 超时中断定时器（使用 threading.Event 消除竞态）──
    # 问题：Timer 可能在查询刚完成时触发 conn.interrupt()，导致：
    #   - 中断已完成查询后的连接状态
    #   - 误中断下一个复用同一连接的查询
    # 解决：query_done Event 标记——Timer 回调先检查 Event，避免误中断
    interrupt_timer: Optional[threading.Timer] = None
    query_done = threading.Event()  # 标记查询是否已完成

    if timeout_seconds > 0:

        def _interrupt():
            """超时回调：仅在查询未完成时中断 DuckDB 当前查询"""
            if query_done.is_set():
                return  # 查询已完成，跳过中断
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
        # ── 先标记完成，再取消 Timer——消除竞态窗口 ──
        query_done.set()
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
    upper = body.upper()

    # 使用统一的只读前缀列表（与 checker.py / checks.py 一致）
    if not any(upper.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        return SQLResult(
            sql=sql,
            error=(
                f"SQL sample run 被拒绝：必须以 {' / '.join(ALLOWED_PREFIXES)} 开头，"
                f"当前以 {upper.split()[0] if upper.split() else '(空)'} 开头"
            ),
            source_table=source_table,
        )

    # 使用统一的禁止关键字列表（单一事实源 checks.FORBIDDEN_KEYWORDS）
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper):
            return SQLResult(
                sql=sql,
                error=f"SQL sample run 被拒绝：检测到禁止关键字 {keyword}（{FORBIDDEN_KEYWORDS[keyword]}）。",
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
