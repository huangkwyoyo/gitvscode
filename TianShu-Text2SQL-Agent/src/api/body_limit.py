"""Phase 6C —— 原始请求体大小限制。

职责：
    1. 在 JSON/Pydantic 解析前限制 body 大小
    2. Content-Length 超限时返回 413
    3. 无 Content-Length 时仍累积检查 body
    4. 超限 body 不进入认证、限流、AgentRuntime
    5. 不无限缓冲 request body

错误码：
    REQUEST_TOO_LARGE
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("tianshu.api.body_limit")


class RequestTooLargeError(Exception):
    """请求体过大异常。

    属性：
        status_code: HTTP 413
        error_code: REQUEST_TOO_LARGE
        message: 用户可见错误消息
    """

    def __init__(self, max_bytes: int):
        self.status_code = 413
        self.error_code = "REQUEST_TOO_LARGE"
        self.message = f"请求体过大，最大允许 {max_bytes} 字节"
        super().__init__(self.message)


class BodyLimitMiddleware:
    """请求体大小限制中间件。

    两层检查：
        1. Content-Length header 预检查（快速拒绝）
        2. 累积 body 读取检查（无 Content-Length 时兜底）

    使用方式：
        limit = BodyLimitMiddleware(max_body_bytes=8192)
        # 在读取 body 前：
        limit.check_content_length(content_length)
        # 在读取 body 过程中：
        limit.check_accumulated(accumulated_bytes)
    """

    def __init__(self, max_body_bytes: int = 8192):
        self._max_bytes = max(0, max_body_bytes)

    @property
    def max_body_bytes(self) -> int:
        return self._max_bytes

    def check_content_length(self, content_length: int | None) -> None:
        """检查 Content-Length header。

        Args:
            content_length: Content-Length 值（字节），None 表示未提供

        Raises:
            RequestTooLargeError: body 超限
        """
        if content_length is None or content_length < 0:
            # 无 Content-Length 或无效值：放行，由累积检查兜底
            return

        if content_length > self._max_bytes:
            logger.warning(
                "请求体过大：Content-Length=%d，限制=%d",
                content_length, self._max_bytes,
            )
            raise RequestTooLargeError(self._max_bytes)

    def check_accumulated(self, accumulated_bytes: int) -> None:
        """检查累积读取的字节数。

        用于无 Content-Length 时的渐进式检查。
        应在每次读取 body chunk 后调用。

        Args:
            accumulated_bytes: 已读取的总字节数

        Raises:
            RequestTooLargeError: body 超限
        """
        if accumulated_bytes > self._max_bytes:
            logger.warning(
                "请求体过大：已累积=%d，限制=%d",
                accumulated_bytes, self._max_bytes,
            )
            raise RequestTooLargeError(self._max_bytes)
