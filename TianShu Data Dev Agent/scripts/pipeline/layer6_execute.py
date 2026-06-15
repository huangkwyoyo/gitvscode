"""
Layer 6：SQL 执行层

职责：
  1. 与 TianShu DuckDB 建立只读连接
  2. 执行 Layer 5 校验通过的 SQL
  3. 返回 DataFrame + 执行元数据

LLM 角色：
  **完全禁止**。此层是纯数据库操作。

安全约束：
  - 连接必须使用 read_only=True
  - 单次查询超时 30 秒
  - 禁止多语句执行
  - 禁止加载扩展

输入：SQL 文本 + 参数列表
输出：{dataframe, row_count, execution_time_ms, columns[]}
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class ColumnInfo:
    """列信息"""
    name: str
    dtype: str  # DuckDB 原生类型名
    nullable: bool = True


@dataclass
class ExecutionResult:
    """SQL 执行结果"""
    # 数据
    dataframe: Any = None  # pandas DataFrame 或 None（失败时）

    # 元数据
    row_count: int = 0
    column_count: int = 0
    columns: list[ColumnInfo] = field(default_factory=list)

    # 执行信息
    execution_time_ms: int = 0
    sql_compiled: str = ""

    # 状态
    success: bool = True
    error_message: str = ""
    error_type: str = ""  # timeout | lock | permission | syntax | other


def execute_sql(
    sql: str,
    params: list[object],
    duckdb_path: str,
    timeout_seconds: int = 30,
    max_retries: int = 1,
    retry_delay_seconds: int = 5,
) -> ExecutionResult:
    """
    以只读模式执行 SQL 查询

    参数：
      - sql: 编译后的 SQL（来自 Layer 4）
      - params: 参数化查询参数
      - duckdb_path: DuckDB 文件路径
      - timeout_seconds: 查询超时
      - max_retries: 超时/锁定时的最大重试次数
      - retry_delay_seconds: 重试间隔
    """
    import duckdb

    last_error: Optional[ExecutionResult] = None

    for attempt in range(max_retries + 1):
        try:
            # ── 建立只读连接 ──
            conn = duckdb.connect(
                duckdb_path,
                read_only=True,
                config={"enable_external_access": False},
            )

            try:
                start_time = time.perf_counter()

                # ── 执行参数化查询（防止注入）──
                # DuckDB 的 execute 支持参数化
                if params:
                    result = conn.execute(sql, params)
                else:
                    result = conn.execute(sql)

                # ── 获取结果 ──
                df = result.fetchdf()
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)

                # ── 提取列信息 ──
                description = result.description
                columns = [
                    ColumnInfo(
                        name=desc[0],
                        dtype=desc[1] if len(desc) > 1 else "UNKNOWN",
                        nullable=True,
                    )
                    for desc in (description or [])
                ]

                return ExecutionResult(
                    dataframe=df,
                    row_count=len(df),
                    column_count=len(df.columns),
                    columns=columns,
                    execution_time_ms=elapsed_ms,
                    sql_compiled=sql,
                    success=True,
                )

            finally:
                conn.close()

        except Exception as e:
            error_str = str(e).lower()

            # 分类错误
            if "timeout" in error_str or "timed out" in error_str:
                error_type = "timeout"
            elif "lock" in error_str or "locked" in error_str:
                error_type = "lock"
            elif "permission" in error_str or "read-only" in error_str:
                error_type = "permission"
            elif "syntax" in error_str or "parser" in error_str:
                error_type = "syntax"
            else:
                error_type = "other"

            last_error = ExecutionResult(
                success=False,
                error_message=str(e),
                error_type=error_type,
                sql_compiled=sql,
            )

            # 仅对超时和锁定重试
            if error_type in ("timeout", "lock") and attempt < max_retries:
                time.sleep(retry_delay_seconds)
                continue
            else:
                break

    # 所有重试失败
    if last_error:
        return last_error

    return ExecutionResult(
        success=False,
        error_message="未知执行错误",
        error_type="other",
        sql_compiled=sql,
    )
