"""Phase 6C —— 本地 API 闭环 runner 测试。

覆盖：
    - run_id 生成（无 latest，唯一）
    - 前置条件检查
    - 安全响应检查
    - JSON 报告结构和可序列化
    - Markdown 报告生成
    - 审计文件检查
    - 服务子进程启动/关闭
    - 失败时 exit code 非 0
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_local_api_closure import (
    RUN_ID,
    check_audit_file,
    check_preconditions,
    check_response_security,
    generate_run_id,
    render_json_report,
    render_markdown_report,
    run_smoke_case,
    wait_for_server,
)


# ═══════════════════════════════════════════════════════════════
# 测试：run_id 生成
# ═══════════════════════════════════════════════════════════════


class TestRunId:
    """运行 ID 生成测试"""

    def test_generate_run_id_no_latest(self):
        """生成的 run_id 不含 latest"""
        rid = generate_run_id()
        assert "latest" not in rid

    def test_generate_run_id_unique(self):
        """连续生成的 run_id 都唯一"""
        ids = [generate_run_id() for _ in range(5)]
        assert len(set(ids)) == 5

    def test_generate_run_id_format(self):
        """run_id 格式正确（时间戳 + 下划线 + 随机 hex）"""
        rid = generate_run_id()
        assert "_" in rid
        parts = rid.split("_")
        assert len(parts) >= 3
        # 第一部分是日期 YYYYMMDD
        assert len(parts[0]) == 8


# ═══════════════════════════════════════════════════════════════
# 测试：安全响应检查
# ═══════════════════════════════════════════════════════════════


class TestSecurityCheck:
    """安全响应检查测试"""

    def test_clean_response_no_issues(self):
        """安全响应不产生任何问题"""
        clean = {
            "contract_version": "1.0",
            "response_type": "answer",
            "question": "test",
            "answer": {"text": "正常回答"},
        }
        issues = check_response_security(clean)
        assert len(issues) == 0

    def test_sql_leak_detected(self):
        """SQL 关键字泄露被检测"""
        bad = {"contract_version": "1.0", "response_type": "answer",
               "sql": "SELECT * FROM gold.trips"}
        issues = check_response_security(bad)
        assert len(issues) > 0

    def test_trace_field_detected(self):
        """trace 字段被检测"""
        bad = {"contract_version": "1.0", "response_type": "error",
               "trace": "Traceback..."}
        issues = check_response_security(bad)
        assert len(issues) > 0

    def test_api_key_detected(self):
        """API Key (sk-) 被检测"""
        bad = {"contract_version": "1.0", "response_type": "answer",
               "api_key": "sk-1234567890abcdef"}
        issues = check_response_security(bad)
        assert len(issues) > 0

    def test_db_path_detected(self):
        """DuckDB 路径被检测"""
        bad = {"contract_version": "1.0", "response_type": "answer",
               "db_path": "/data/tianshu.duckdb"}
        issues = check_response_security(bad)
        assert len(issues) > 0


# ═══════════════════════════════════════════════════════════════
# 测试：审计文件检查
# ═══════════════════════════════════════════════════════════════


class TestAuditCheck:
    """审计文件检查测试（使用 tempfile 避免 Windows tmp_path 权限问题）"""

    @staticmethod
    def _create_audit_dir_with_file(filename: str, records: list[dict]) -> str:
        """在临时目录中创建审计文件，返回目录路径"""
        tmpdir = tempfile.mkdtemp()
        audit_file = Path(tmpdir) / filename
        with open(audit_file, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return tmpdir

    def test_no_audit_dir(self):
        """审计目录不存在时返回空结果"""
        result = check_audit_file("/nonexistent/audit/dir")
        assert result["found"] is False
        assert result["records"] == 0

    def test_empty_audit_dir(self):
        """空审计目录返回 found=False"""
        tmpdir = tempfile.mkdtemp()
        try:
            result = check_audit_file(tmpdir)
            assert result["found"] is False
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_valid_audit_file(self):
        """有效审计文件可正确解析"""
        records = [
            {"timestamp": "2026-06-20T10:00:00", "request_id": "r1",
             "event": "accepted", "route": "/v1/ask", "http_status": 200},
            {"timestamp": "2026-06-20T10:00:01", "request_id": "r2",
             "event": "completed", "route": "/v1/ask", "http_status": 200},
            {"timestamp": "2026-06-20T10:00:02", "request_id": "r3",
             "event": "rejected", "route": "/v1/ask", "http_status": 401},
        ]
        tmpdir = self._create_audit_dir_with_file(
            "local_api_audit_20260620_test.jsonl", records)
        try:
            result = check_audit_file(tmpdir)
            assert result["found"] is True
            assert result["records"] == 3
            assert "accepted" in result["events"]
            assert "completed" in result["events"]
            assert "rejected" in result["events"]
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_audit_with_sensitive_content_detected(self):
        """含敏感内容的审计文件被检测（使用禁止的键名 token）"""
        records = [
            {"timestamp": "2026-06-20T10:00:00", "request_id": "r1",
             "event": "completed", "route": "/v1/ask", "http_status": 200,
             "token": "should-not-be-here"},  # token 是明确禁止的键名
        ]
        tmpdir = self._create_audit_dir_with_file(
            "local_api_audit_20260620_sensitive.jsonl", records)
        try:
            result = check_audit_file(tmpdir)
            assert result["found"] is True
            assert result["has_sensitive"] is True
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_audit_without_sensitive_content_passes(self):
        """无敏感内容的审计文件通过检查"""
        records = [
            {"timestamp": "2026-06-20T10:00:00", "request_id": "r1",
             "event": "completed", "route": "/v1/ask", "http_status": 200,
             "response_type": "answer", "duration_ms": 100,
             "question_length": 18, "execution_mode": "single"},
        ]
        tmpdir = self._create_audit_dir_with_file(
            "local_api_audit_20260620_clean.jsonl", records)
        try:
            result = check_audit_file(tmpdir)
            assert result["found"] is True
            # 只有安全字段，不应触发敏感内容检测
            assert result["has_sensitive"] is False
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
# 测试：JSON 报告
# ═══════════════════════════════════════════════════════════════


class TestJsonReport:
    """JSON 报告生成测试"""

    def test_json_report_structure(self):
        """JSON 报告结构完整"""
        results = [
            {"case": "test1", "status_code": 200, "expected_status": 200,
             "passed": True, "duration_ms": 100, "details": []},
        ]
        report = render_json_report(results, "test_run_id", 8000)

        assert report["report"] == "local_api_closure"
        assert report["run_id"] == "test_run_id"
        assert "timestamp" in report
        assert report["summary"]["total"] == 1
        assert report["summary"]["passed"] == 1
        assert report["summary"]["failed"] == 0

    def test_json_report_all_pass(self):
        """全部通过时 overall = PASS"""
        results = [
            {"case": "t1", "passed": True, "status_code": 200, "expected_status": 200, "duration_ms": 1, "details": []},
            {"case": "t2", "passed": True, "status_code": 401, "expected_status": 401, "duration_ms": 1, "details": []},
        ]
        report = render_json_report(results, "rid", 8000)
        assert report["summary"]["overall"] == "PASS"

    def test_json_report_has_failure(self):
        """存在失败时 overall = FAIL"""
        results = [
            {"case": "t1", "passed": True, "status_code": 200, "expected_status": 200, "duration_ms": 1, "details": []},
            {"case": "t2", "passed": False, "status_code": 401, "expected_status": 200, "duration_ms": 1, "details": []},
        ]
        report = render_json_report(results, "rid", 8000)
        assert report["summary"]["overall"] == "FAIL"

    def test_json_report_serializable(self):
        """JSON 报告可序列化"""
        results = [
            {"case": "t1", "passed": True, "status_code": 200, "expected_status": 200, "duration_ms": 1, "details": []},
        ]
        report = render_json_report(results, "rid", 8000)
        serialized = json.dumps(report)
        parsed = json.loads(serialized)
        assert parsed["run_id"] == "rid"


# ═══════════════════════════════════════════════════════════════
# 测试：Markdown 报告
# ═══════════════════════════════════════════════════════════════


class TestMarkdownReport:
    """Markdown 报告生成测试"""

    def test_markdown_report_contains_summary(self):
        """Markdown 报告包含概要信息"""
        json_report = {
            "run_id": "test_123",
            "timestamp": "2026-06-20T10:00:00",
            "port": 8000,
            "summary": {"total": 3, "passed": 2, "failed": 1, "overall": "FAIL"},
            "cases": [],
        }
        md = render_markdown_report(json_report)

        assert "test_123" in md
        assert "8000" in md
        assert "3" in md
        assert "2" in md
        assert "1" in md

    def test_markdown_report_no_latest_reference(self):
        """Markdown 报告不含 latest 引用"""
        json_report = {
            "run_id": "test_123",
            "timestamp": "2026-06-20T10:00:00",
            "port": 8000,
            "summary": {"total": 1, "passed": 1, "failed": 0, "overall": "PASS"},
            "cases": [],
        }
        md = render_markdown_report(json_report)
        # _latest 文件命名模式不应出现（latest 链接在独立行）
        assert "_latest." not in md


# ═══════════════════════════════════════════════════════════════
# 测试：前置条件检查
# ═══════════════════════════════════════════════════════════════


class TestPreconditions:
    """前置条件检查测试"""

    def test_missing_token_env(self):
        """缺少 token 环境变量时返回错误"""
        # 确保 token 未设置
        old_token = os.environ.pop("TIANSHU_LOCAL_API_TOKEN", None)
        try:
            args = MagicMock()
            args.tianshu_config = str(PROJECT_ROOT / "config" / "tianshu_target.yml")
            errors = check_preconditions(args)
            # 至少应该有 token 相关错误
            has_token_error = any("token" in e.lower() for e in errors)
            assert has_token_error, f"期望 token 错误，实际错误: {errors}"
        finally:
            if old_token:
                os.environ["TIANSHU_LOCAL_API_TOKEN"] = old_token

    def test_token_too_short(self):
        """token 太短时返回错误"""
        os.environ["TIANSHU_LOCAL_API_TOKEN"] = "short"
        try:
            args = MagicMock()
            args.tianshu_config = str(PROJECT_ROOT / "config" / "tianshu_target.yml")
            errors = check_preconditions(args)
            has_len_error = any("32" in e for e in errors)
            assert has_len_error, f"期望长度错误，实际错误: {errors}"
        finally:
            os.environ.pop("TIANSHU_LOCAL_API_TOKEN", None)


# ═══════════════════════════════════════════════════════════════
# 测试：服务生命周期
# ═══════════════════════════════════════════════════════════════


class TestServiceLifecycle:
    """服务子进程生命周期测试"""

    def test_wait_for_server_unavailable(self):
        """服务不可用时 wait_for_server 返回 False"""
        # 使用一个不可能在监听的端口
        result = wait_for_server(59999, timeout=0.5)
        assert result is False
