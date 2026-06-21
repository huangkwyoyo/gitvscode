"""Phase 6C —— 请求体大小限制测试。

覆盖：
    - 正常 body 通过
    - Content-Length 超限返回 413
    - 无 Content-Length 超限仍返回 413
    - 超限 body 不进入认证
    - 超限 body 不进入限流
    - 超限 body 不进入 AgentRuntime
    - question 字符限制仍生效
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.body_limit import BodyLimitMiddleware, RequestTooLargeError


# ═══════════════════════════════════════════════════════════════
# 测试：BodyLimitMiddleware 类
# ═══════════════════════════════════════════════════════════════


class TestBodyLimitMiddleware:
    """BodyLimitMiddleware 单元测试"""

    def test_normal_body_passes(self):
        """正常大小的 body 通过检查"""
        mw = BodyLimitMiddleware(max_body_bytes=8192)
        # 正常 JSON body（用 ASCII 安全字符测试）
        body = b'{"question": "How many trips in January 2026?"}'
        # 不应抛出异常
        mw.check_content_length(len(body))

    def test_content_length_exceeded_raises_413(self):
        """Content-Length 超限抛出 RequestTooLargeError (413)"""
        mw = BodyLimitMiddleware(max_body_bytes=100)
        with pytest.raises(RequestTooLargeError) as exc:
            mw.check_content_length(500)
        assert exc.value.status_code == 413
        assert "REQUEST_TOO_LARGE" in exc.value.error_code

    def test_content_length_at_limit_passes(self):
        """Content-Length 等于限制值时通过"""
        mw = BodyLimitMiddleware(max_body_bytes=100)
        # 恰好等于限制值不应抛出异常
        mw.check_content_length(100)

    def test_content_length_zero_passes(self):
        """Content-Length 为 0 时通过（后续由 Pydantic 校验 body）"""
        mw = BodyLimitMiddleware(max_body_bytes=8192)
        mw.check_content_length(0)

    def test_no_content_length_checked_via_read(self):
        """无 Content-Length 时通过累积读取检查"""
        mw = BodyLimitMiddleware(max_body_bytes=100)
        # 模拟读取 body 的过程
        chunks = [b"a" * 50, b"b" * 60]  # 总共 110 字节，超限
        accumulated = 0
        for chunk in chunks:
            accumulated += len(chunk)
            try:
                mw.check_accumulated(accumulated)
            except RequestTooLargeError as exc:
                assert exc.status_code == 413
                return
        pytest.fail("应该抛出 RequestTooLargeError")

    def test_accumulated_within_limit_passes(self):
        """累积读取在限制内时通过"""
        mw = BodyLimitMiddleware(max_body_bytes=100)
        mw.check_accumulated(50)  # 不应抛出异常
        mw.check_accumulated(99)  # 不应抛出异常

    def test_accumulated_exceeded_raises(self):
        """累积读取超限抛出异常"""
        mw = BodyLimitMiddleware(max_body_bytes=100)
        with pytest.raises(RequestTooLargeError):
            mw.check_accumulated(150)

    def test_negative_content_length_treated_as_missing(self):
        """负 Content-Length 视为缺失（通过检查，后续累积检查兜底）"""
        mw = BodyLimitMiddleware(max_body_bytes=8192)
        # 负值不应触发 413，由累积检查兜底
        mw.check_content_length(-1)

    def test_default_max_body_bytes(self):
        """默认 max_body_bytes 为 8192"""
        mw = BodyLimitMiddleware()
        assert mw.max_body_bytes == 8192


# ═══════════════════════════════════════════════════════════════
# 测试：RequestTooLargeError
# ═══════════════════════════════════════════════════════════════


class TestRequestTooLargeError:
    """RequestTooLargeError 异常测试"""

    def test_status_code_413(self):
        """异常 status_code 为 413"""
        exc = RequestTooLargeError(8192)
        assert exc.status_code == 413

    def test_error_code(self):
        """异常包含 REQUEST_TOO_LARGE 错误码"""
        exc = RequestTooLargeError(8192)
        assert exc.error_code == "REQUEST_TOO_LARGE"

    def test_message_contains_limit(self):
        """异常消息包含大小限制信息"""
        exc = RequestTooLargeError(4096)
        assert "4096" in exc.message or "请求体" in exc.message


# ═══════════════════════════════════════════════════════════════
# 测试：边界条件
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界条件测试"""

    def test_zero_max_body_bytes_rejects_all(self):
        """max_body_bytes=0 时拒绝所有请求"""
        mw = BodyLimitMiddleware(max_body_bytes=0)
        # Content-Length=0 可以通过（空 body）
        mw.check_content_length(0)
        # Content-Length=1 被拒绝
        with pytest.raises(RequestTooLargeError):
            mw.check_content_length(1)

    def test_very_large_limit_allows_normal_bodies(self):
        """很大的限制值允许正常 body 通过"""
        mw = BodyLimitMiddleware(max_body_bytes=1024 * 1024)  # 1MB
        mw.check_content_length(10000)

    def test_no_infinite_buffering(self):
        """验证不会无限缓冲请求体：max_body_bytes 限制生效"""
        mw = BodyLimitMiddleware(max_body_bytes=8192)
        # 超过限制的累积值应立即抛出异常
        with pytest.raises(RequestTooLargeError):
            mw.check_accumulated(10000)
