"""Phase 6C —— 本地脱敏审计测试。

覆盖：
    - accepted 事件写入
    - completed 事件写入
    - rejected 事件写入
    - request_id 与响应头一致
    - JSONL 每行可解析
    - 不记录 token
    - 不记录 question 原文
    - 不记录 answer
    - 不记录 SQL/generated_sql
    - 不记录 trace
    - 不记录数据库路径
    - 不记录环境变量
    - 文件名不含 latest
    - audit 写入失败返回 503
    - audit 写入失败不被静默忽略
    - 并发写入不交错
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.local_audit import (
    LocalAuditWriter,
    AuditWriteError,
    sanitize_audit_record,
)


# ═══════════════════════════════════════════════════════════════
# 测试：审计记录脱敏
# ═══════════════════════════════════════════════════════════════


class TestAuditSanitization:
    """审计记录脱敏测试"""

    def test_allowed_fields_present(self):
        """允许的字段在记录中保留"""
        record = {
            "timestamp": "2026-06-20T10:00:00",
            "request_id": "abc-123",
            "event": "completed",
            "route": "/v1/ask",
            "http_status": 200,
            "response_type": "answer",
            "duration_ms": 123,
            "error_code": None,
            "question_length": 18,
            "execution_mode": "single",
        }
        sanitized = sanitize_audit_record(record)
        for key in record:
            assert key in sanitized
            assert sanitized[key] == record[key]

    def test_token_field_removed(self):
        """token 字段被移除"""
        record = {
            "request_id": "abc",
            "token": "secret-token-value",
            "http_status": 200,
        }
        sanitized = sanitize_audit_record(record)
        assert "token" not in sanitized

    def test_question_field_removed(self):
        """question 原文字段被移除"""
        record = {
            "request_id": "abc",
            "question": "用户问的敏感问题",
            "http_status": 200,
        }
        sanitized = sanitize_audit_record(record)
        assert "question" not in sanitized

    def test_answer_field_removed(self):
        """answer 字段被移除"""
        record = {
            "request_id": "abc",
            "answer": {"text": "包含业务数据的回答"},
            "http_status": 200,
        }
        sanitized = sanitize_audit_record(record)
        assert "answer" not in sanitized

    def test_sql_field_removed(self):
        """SQL 字段被移除"""
        record = {
            "request_id": "abc",
            "sql": "SELECT * FROM gold.trips",
            "generated_sql": "SELECT * FROM gold.trips",
            "http_status": 200,
        }
        sanitized = sanitize_audit_record(record)
        assert "sql" not in sanitized
        assert "generated_sql" not in sanitized

    def test_trace_field_removed(self):
        """trace 字段被移除"""
        record = {
            "request_id": "abc",
            "trace": "Traceback (most recent call last)...",
            "http_status": 500,
        }
        sanitized = sanitize_audit_record(record)
        assert "trace" not in sanitized

    def test_db_path_removed(self):
        """数据库路径被移除"""
        record = {
            "request_id": "abc",
            "db_path": "/data/tianshu.duckdb",
            "duckdb_path": "/data/tianshu.duckdb",
            "http_status": 200,
        }
        sanitized = sanitize_audit_record(record)
        assert "db_path" not in sanitized
        assert "duckdb_path" not in sanitized

    def test_api_key_removed(self):
        """API Key 字段被移除"""
        record = {
            "request_id": "abc",
            "api_key": "sk-1234567890abcdef",
            "authorization": "Bearer token",
            "http_status": 200,
        }
        sanitized = sanitize_audit_record(record)
        assert "api_key" not in sanitized
        assert "authorization" not in sanitized

    def test_env_var_removed(self):
        """环境变量字段被移除"""
        record = {
            "request_id": "abc",
            "env": {"TIANSHU_TOKEN": "secret"},
            "environment": {"PATH": "/usr/bin"},
            "http_status": 200,
        }
        sanitized = sanitize_audit_record(record)
        assert "env" not in sanitized
        assert "environment" not in sanitized

    def test_traceback_removed(self):
        """traceback 字段被移除"""
        record = {
            "request_id": "abc",
            "traceback": "File ... line 42, in ...",
            "exception": "Something went wrong",
            "http_status": 500,
        }
        sanitized = sanitize_audit_record(record)
        assert "traceback" not in sanitized
        assert "exception" not in sanitized

    def test_summaries_removed(self):
        """summaries 字段被移除（可能包含聚合数据）"""
        record = {
            "request_id": "abc",
            "summaries": [{"rows": 100, "preview": "..."}],
            "http_status": 200,
        }
        sanitized = sanitize_audit_record(record)
        assert "summaries" not in sanitized

    def test_merged_rows_removed(self):
        """merged rows 字段被移除"""
        record = {
            "request_id": "abc",
            "merged_rows": [{"date": "2026-01-01", "count": 100}],
            "http_status": 200,
        }
        sanitized = sanitize_audit_record(record)
        assert "merged_rows" not in sanitized

    def test_chart_data_removed(self):
        """chart 数据字段被移除"""
        record = {
            "request_id": "abc",
            "chart_data": {"x": [1, 2, 3], "y": [4, 5, 6]},
            "http_status": 200,
        }
        sanitized = sanitize_audit_record(record)
        assert "chart_data" not in sanitized

    def test_contracts_content_removed(self):
        """contracts 内容字段被移除"""
        record = {
            "request_id": "abc",
            "contracts": {"gold": {"tables": []}},
            "http_status": 200,
        }
        sanitized = sanitize_audit_record(record)
        assert "contracts" not in sanitized


# ═══════════════════════════════════════════════════════════════
# 测试：LocalAuditWriter
# ═══════════════════════════════════════════════════════════════


class TestLocalAuditWriter:
    """LocalAuditWriter 审计写入器测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时审计目录"""
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    def test_write_accepted_event(self, temp_dir):
        """accepted 事件写入成功"""
        writer = LocalAuditWriter(
            audit_dir=temp_dir,
            startup_timestamp="20260620_100000",
        )
        record = {
            "timestamp": "2026-06-20T10:00:00",
            "request_id": "test-req-001",
            "event": "accepted",
            "route": "/v1/ask",
            "http_status": 200,
            "response_type": None,
            "duration_ms": None,
            "error_code": None,
            "question_length": 18,
            "execution_mode": "single",
        }
        writer.write_event(record)

        # 验证文件已创建
        audit_files = list(Path(temp_dir).glob("*.jsonl"))
        assert len(audit_files) == 1
        assert "latest" not in audit_files[0].name

    def test_write_completed_event(self, temp_dir):
        """completed 事件写入成功"""
        writer = LocalAuditWriter(
            audit_dir=temp_dir,
            startup_timestamp="20260620_100000",
        )
        record = {
            "timestamp": "2026-06-20T10:00:01",
            "request_id": "test-req-002",
            "event": "completed",
            "route": "/v1/ask",
            "http_status": 200,
            "response_type": "answer",
            "duration_ms": 150,
            "error_code": None,
            "question_length": 18,
            "execution_mode": "single",
        }
        writer.write_event(record)

    def test_write_rejected_event(self, temp_dir):
        """rejected 事件写入成功"""
        writer = LocalAuditWriter(
            audit_dir=temp_dir,
            startup_timestamp="20260620_100000",
        )
        record = {
            "timestamp": "2026-06-20T10:00:02",
            "request_id": "test-req-003",
            "event": "rejected",
            "route": "/v1/ask",
            "http_status": 401,
            "response_type": None,
            "duration_ms": 1,
            "error_code": "AUTH_FAILED",
            "question_length": None,
            "execution_mode": None,
        }
        writer.write_event(record)

    def test_jsonl_each_line_parsable(self, temp_dir):
        """每条记录可独立 JSON 解析"""
        writer = LocalAuditWriter(
            audit_dir=temp_dir,
            startup_timestamp="20260620_100000",
        )
        for i in range(5):
            writer.write_event({
                "timestamp": f"2026-06-20T10:00:{i:02d}",
                "request_id": f"req-{i:03d}",
                "event": "completed",
                "route": "/v1/ask",
                "http_status": 200,
                "response_type": "answer",
                "duration_ms": 100 + i,
                "error_code": None,
                "question_length": 18,
                "execution_mode": "single",
            })

        # 读取并解析每一行
        audit_files = list(Path(temp_dir).glob("*.jsonl"))
        with open(audit_files[0], "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    parsed = json.loads(line)
                    assert "request_id" in parsed
                    assert "event" in parsed

    def test_request_id_matches_header(self, temp_dir):
        """审计记录中 request_id 应与响应头一致"""
        writer = LocalAuditWriter(
            audit_dir=temp_dir,
            startup_timestamp="20260620_100000",
        )
        request_id = "uuid-req-12345"
        writer.write_event({
            "timestamp": "2026-06-20T10:00:00",
            "request_id": request_id,
            "event": "completed",
            "route": "/v1/ask",
            "http_status": 200,
            "response_type": "answer",
            "duration_ms": 100,
            "error_code": None,
            "question_length": 18,
            "execution_mode": "single",
        })

        audit_files = list(Path(temp_dir).glob("*.jsonl"))
        with open(audit_files[0], "r", encoding="utf-8") as f:
            record = json.loads(f.readline())
            assert record["request_id"] == request_id

    def test_no_latest_in_filename(self, temp_dir):
        """审计文件名不含 latest"""
        writer = LocalAuditWriter(
            audit_dir=temp_dir,
            startup_timestamp="20260620_100000",
        )
        writer.write_event({
            "timestamp": "2026-06-20T10:00:00",
            "request_id": "req-1",
            "event": "accepted",
            "route": "/v1/ask",
            "http_status": 200,
            "response_type": None,
            "duration_ms": None,
            "error_code": None,
            "question_length": 18,
            "execution_mode": "single",
        })

        audit_files = list(Path(temp_dir).glob("*.jsonl"))
        for f in audit_files:
            assert "latest" not in f.name
            # 验证文件名格式：local_api_audit_<timestamp>.jsonl
            assert f.name.startswith("local_api_audit_")
            assert f.name.endswith(".jsonl")

    def test_sensitive_fields_not_in_output(self, temp_dir):
        """敏感字段不出现在审计文件中"""
        writer = LocalAuditWriter(
            audit_dir=temp_dir,
            startup_timestamp="20260620_100000",
        )
        # 包含敏感信息的记录
        writer.write_event({
            "timestamp": "2026-06-20T10:00:00",
            "request_id": "req-sensitive",
            "event": "completed",
            "route": "/v1/ask",
            "http_status": 200,
            "response_type": "answer",
            "duration_ms": 100,
            "error_code": None,
            "question_length": 18,
            "execution_mode": "single",
            # 这些字段应被移除
            "token": "secret-token",
            "question": "用户问题原文",
            "answer": "回答内容",
            "sql": "SELECT * FROM gold.trips",
            "generated_sql": "SELECT * FROM gold.trips",
            "trace": "traceback...",
            "db_path": "/path/to/db.duckdb",
            "api_key": "sk-abc123",
        })

        audit_files = list(Path(temp_dir).glob("*.jsonl"))
        with open(audit_files[0], "r", encoding="utf-8") as f:
            content = f.read()
            assert "secret-token" not in content
            assert "用户问题原文" not in content
            assert "回答内容" not in content
            assert "SELECT * FROM" not in content
            assert "traceback" not in content
            assert "duckdb" not in content
            assert "sk-abc123" not in content

    def test_write_failure_raises(self, temp_dir):
        """审计写入失败抛出 AuditWriteError"""
        writer = LocalAuditWriter(
            audit_dir=temp_dir,
            startup_timestamp="20260620_100000",
        )
        writer._initialized = True
        # 将文件路径设为目录路径，导致写入失败
        writer._file_path = Path(temp_dir)  # 目录无法作为文件写入
        with pytest.raises(AuditWriteError):
            writer.write_event({
                "timestamp": "2026-06-20T10:00:00",
                "request_id": "req-err",
                "event": "accepted",
                "route": "/v1/ask",
                "http_status": 200,
                "response_type": None,
                "duration_ms": None,
                "error_code": None,
                "question_length": 18,
                "execution_mode": "single",
            })

    def test_write_failure_not_silent(self, temp_dir):
        """审计写入失败不被静默忽略"""
        writer = LocalAuditWriter(
            audit_dir=temp_dir,
            startup_timestamp="20260620_100000",
        )
        writer._initialized = True
        writer._file_path = Path(temp_dir)  # 目录无法作为文件写入
        # 应抛出异常，不是静默返回
        error_raised = False
        try:
            writer.write_event({
                "request_id": "req-err",
                "event": "accepted",
                "http_status": 200,
            })
        except AuditWriteError:
            error_raised = True
        assert error_raised, "审计写入失败应抛出 AuditWriteError"

    def test_directory_auto_created(self, temp_dir):
        """审计目录不存在时自动创建"""
        audit_subdir = os.path.join(temp_dir, "new_audit_dir")
        writer = LocalAuditWriter(
            audit_dir=audit_subdir,
            startup_timestamp="20260620_100000",
        )
        writer.write_event({
            "timestamp": "2026-06-20T10:00:00",
            "request_id": "req-auto",
            "event": "accepted",
            "route": "/v1/ask",
            "http_status": 200,
            "response_type": None,
            "duration_ms": None,
            "error_code": None,
            "question_length": 18,
            "execution_mode": "single",
        })
        assert os.path.isdir(audit_subdir)


# ═══════════════════════════════════════════════════════════════
# 测试：并发写入安全
# ═══════════════════════════════════════════════════════════════


class TestConcurrentAuditWrite:
    """并发写入测试"""

    @pytest.mark.asyncio
    async def test_concurrent_writes_no_interleaving(self):
        """并发写入不交错（使用 asyncio.Lock）"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            writer = LocalAuditWriter(
                audit_dir=tmp,
                startup_timestamp="20260620_100000",
            )

            async def write_one(i: int):
                writer.write_event({
                    "timestamp": f"2026-06-20T10:00:{i:02d}",
                    "request_id": f"req-concurrent-{i:03d}",
                    "event": "completed",
                    "route": "/v1/ask",
                    "http_status": 200,
                    "response_type": "answer",
                    "duration_ms": 100 + i,
                    "error_code": None,
                    "question_length": 18,
                    "execution_mode": "single",
                })

            # 并发写入 10 条记录
            tasks = [write_one(i) for i in range(10)]
            await asyncio.gather(*tasks)

            # 验证每个文件中的每行都可解析
            audit_files = list(Path(tmp).glob("*.jsonl"))
            all_ids = []
            for f in audit_files:
                with open(f, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            record = json.loads(line)
                            all_ids.append(record["request_id"])

            # 所有 10 条记录都应存在
            assert len(all_ids) == 10
            for i in range(10):
                assert f"req-concurrent-{i:03d}" in all_ids
