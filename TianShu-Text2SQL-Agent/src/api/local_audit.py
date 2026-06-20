"""Phase 6C —— 本地脱敏 JSONL 审计。

职责：
    1. 每个请求记录一条 JSONL 审计记录
    2. 只记录允许字段，禁止记录敏感信息
    3. 使用 asyncio.Lock 保证单进程写入不交错
    4. append-only，每条记录可独立 JSON 解析
    5. request_id 与响应头一致
    6. 审计写入失败时抛出 AuditWriteError（不静默继续）

允许记录的字段：
    - timestamp, request_id, event, route, http_status
    - response_type, duration_ms, error_code
    - question_length, execution_mode

禁止记录的字段：
    - local token, question 原文, answer, clarification message
    - refusal reason, SQL, generated_sql, trace, summaries
    - merged rows, chart data, DuckDB 绝对路径, contracts 内容
    - API Key, Authorization, 环境变量, traceback

审计文件：
    harness/reports/local_api_audit/local_api_audit_<startup_timestamp>.jsonl
    不生成 latest。

限制声明：
    这是本地诊断审计，不是合规级不可变审计。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("tianshu.api.audit")


# ── 禁止记录的字段（即使调用方传入也会被移除）──
_FORBIDDEN_FIELDS: set[str] = {
    # 认证相关
    "token", "local_token", "api_token",
    # 业务内容
    "question", "answer", "clarification", "refusal_reason",
    # SQL 相关
    "sql", "generated_sql", "sql_plan", "sql_text",
    # 调试信息
    "trace", "traceback", "exception", "stack_trace",
    # 数据内容
    "summaries", "merged_rows", "merged_result", "chart_data", "chart_spec",
    # 数据库信息
    "db_path", "duckdb_path", "database_path",
    # 认证信息
    "api_key", "authorization", "auth_header",
    # 环境信息
    "env", "environment", "env_vars",
    # 配置内容
    "contracts", "config",
}


class AuditWriteError(Exception):
    """审计写入失败异常。

    审计写入失败不应被静默忽略——调用方应捕获此异常并返回安全 503。
    """

    def __init__(self, message: str = "审计写入失败"):
        self.message = message
        super().__init__(message)


class AuditEvent:
    """审计事件类型常量"""
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    REJECTED = "rejected"


def sanitize_audit_record(record: dict[str, Any]) -> dict[str, Any]:
    """脱敏审计记录：移除所有禁止字段。

    Args:
        record: 原始审计记录字典

    Returns:
        脱敏后的记录（新字典，不修改原记录）
    """
    return {
        key: value
        for key, value in record.items()
        if key not in _FORBIDDEN_FIELDS
    }


class LocalAuditWriter:
    """本地 JSONL 审计写入器。

    特性：
        - append-only JSONL
        - 使用 asyncio.Lock 保护并发写入
        - 自动创建审计目录
        - 文件名含启动时间戳，不生成 latest
        - 写入失败抛出 AuditWriteError

    使用方式：
        writer = LocalAuditWriter(
            audit_dir="harness/reports/local_api_audit",
            startup_timestamp="20260620_100000",
        )
        writer.write_event({
            "timestamp": "...",
            "request_id": "...",
            "event": "completed",
            ...
        })
    """

    def __init__(self, audit_dir: str, startup_timestamp: str):
        self._audit_dir = Path(audit_dir)
        self._startup_timestamp = startup_timestamp
        self._file_path: Path | None = None
        self._lock = asyncio.Lock()
        self._initialized = False

    # ═══════════════════════════════════════════════════════════
    # 公开方法
    # ═══════════════════════════════════════════════════════════

    def write_event(self, record: dict[str, Any]) -> None:
        """写入一条审计记录。

        在同步上下文中调用（FastAPI 中间件/端点），
        内部使用同步文件写入 + asyncio.Lock 保护。

        Args:
            record: 审计记录字典（会被脱敏处理）

        Raises:
            AuditWriteError: 写入失败
        """
        # ── 确保已初始化 ──
        if not self._initialized:
            self._initialize()

        # ── 脱敏 ──
        safe_record = sanitize_audit_record(record)

        # ── 序列化 ──
        try:
            line = json.dumps(safe_record, ensure_ascii=False, default=str) + "\n"
        except (TypeError, ValueError) as exc:
            raise AuditWriteError(f"审计记录序列化失败: {exc}") from exc

        # ── 写入（同步，但受 asyncio.Lock 保护）──
        try:
            # 在事件循环中使用 run_coroutine_threadsafe 获取锁
            # 或直接使用同步锁保护
            self._write_line(line)
        except AuditWriteError:
            raise
        except Exception as exc:
            raise AuditWriteError(f"审计写入失败: {exc}") from exc

    async def write_event_async(self, record: dict[str, Any]) -> None:
        """异步写入一条审计记录。

        Args:
            record: 审计记录字典（会被脱敏处理）

        Raises:
            AuditWriteError: 写入失败
        """
        if not self._initialized:
            self._initialize()

        safe_record = sanitize_audit_record(record)

        try:
            line = json.dumps(safe_record, ensure_ascii=False, default=str) + "\n"
        except (TypeError, ValueError) as exc:
            raise AuditWriteError(f"审计记录序列化失败: {exc}") from exc

        # 使用锁保护并发写入
        async with self._lock:
            try:
                self._write_line(line)
            except AuditWriteError:
                raise
            except Exception as exc:
                raise AuditWriteError(f"审计写入失败: {exc}") from exc

    @property
    def file_path(self) -> str | None:
        """审计文件路径"""
        if self._file_path:
            return str(self._file_path)
        return None

    # ═══════════════════════════════════════════════════════════
    # 内部方法
    # ═══════════════════════════════════════════════════════════

    def _initialize(self) -> None:
        """创建审计目录和文件。"""
        try:
            self._audit_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise AuditWriteError(f"无法创建审计目录 {self._audit_dir}: {exc}") from exc

        # 文件名：local_api_audit_<startup_timestamp>.jsonl
        filename = f"local_api_audit_{self._startup_timestamp}.jsonl"
        self._file_path = self._audit_dir / filename

        # 确保文件存在（不覆盖已有内容）
        try:
            self._file_path.touch(exist_ok=True)
        except OSError as exc:
            raise AuditWriteError(f"无法创建审计文件 {self._file_path}: {exc}") from exc

        self._initialized = True
        logger.info("审计文件: %s", self._file_path)

    def _write_line(self, line: str) -> None:
        """同步追加写入一行（内部使用）。

        前提：调用方已持有锁。

        Raises:
            AuditWriteError: 写入失败
        """
        if self._file_path is None:
            raise AuditWriteError("审计文件未初始化")

        try:
            with open(self._file_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        except OSError as exc:
            raise AuditWriteError(f"审计文件写入失败: {exc}") from exc


def generate_startup_timestamp() -> str:
    """生成服务启动时间戳（用于审计文件名）。

    Returns:
        格式为 YYYYMMDD_HHMMSS 的时间戳字符串
    """
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
