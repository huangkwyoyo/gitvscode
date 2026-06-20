"""Phase 6B —— API 错误处理与安全错误响应。

约束：
    - 500/503 不返回 traceback、SQL、数据库路径、API Key
    - 所有错误使用统一 ErrorEnvelope
    - request_id 由中间件注入
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .schemas import ApiErrorDetail, ApiErrorResponse


# ═══════════════════════════════════════════════════════════════
# 错误码常量
# ═══════════════════════════════════════════════════════════════

ERROR_CODE_VALIDATION = "VALIDATION_ERROR"
ERROR_CODE_SERVICE_NOT_READY = "SERVICE_NOT_READY"
ERROR_CODE_SERVICE_BUSY = "SERVICE_BUSY"
ERROR_CODE_INTERNAL_ERROR = "INTERNAL_ERROR"
ERROR_CODE_AUTH_FAILED = "AUTH_FAILED"
ERROR_CODE_REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"


# ═══════════════════════════════════════════════════════════════
# 安全错误消息（中文，不含内部细节）
# ═══════════════════════════════════════════════════════════════

_USER_FACING_MESSAGES: dict[str, str] = {
    ERROR_CODE_SERVICE_NOT_READY: "问数服务暂不可用，请稍后再试",
    ERROR_CODE_SERVICE_BUSY: "当前问数请求较多，请稍后再试",
    ERROR_CODE_INTERNAL_ERROR: "服务内部异常，请联系管理员",
    ERROR_CODE_AUTH_FAILED: "认证失败",
    ERROR_CODE_REQUEST_TOO_LARGE: "请求体过大",
}


def _get_request_id(request: Request) -> str:
    """从请求状态中提取 request_id（由中间件注入）"""
    return getattr(request.state, "request_id", "")


def build_error_response(
    status_code: int,
    code: str,
    message: str | None = None,
    request_id: str = "",
) -> JSONResponse:
    """构建安全的 API 错误响应。

    Args:
        status_code: HTTP 状态码
        code: 错误码（如 SERVICE_NOT_READY）
        message: 用户可见消息（None 时使用默认消息）
        request_id: 请求追踪 ID

    Returns:
        JSONResponse，Content-Type: application/json
    """
    msg = message or _USER_FACING_MESSAGES.get(code, "服务异常")
    return JSONResponse(
        status_code=status_code,
        content=ApiErrorResponse(
            error=ApiErrorDetail(code=code, message=msg, request_id=request_id or ""),
        ).model_dump(),
    )


# ═══════════════════════════════════════════════════════════════
# FastAPI 异常处理器（注册到 app）
# ═══════════════════════════════════════════════════════════════


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """请求校验失败 → 422，安全消息"""
    return build_error_response(
        status_code=422,
        code=ERROR_CODE_VALIDATION,
        message="请求格式不正确，请检查 question 字段",
        request_id=_get_request_id(request),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """HTTP 异常 → 透传状态码和 headers，但不泄露内部 detail"""
    # 503 和 429 保留原始状态码，但 message 使用安全版本
    if exc.status_code == 503:
        return build_error_response(
            status_code=503,
            code=ERROR_CODE_SERVICE_NOT_READY,
            request_id=_get_request_id(request),
        )
    if exc.status_code == 429:
        return build_error_response(
            status_code=429,
            code=ERROR_CODE_SERVICE_BUSY,
            request_id=_get_request_id(request),
        )
    if exc.status_code == 401:
        return build_error_response(
            status_code=401,
            code=ERROR_CODE_AUTH_FAILED,
            request_id=_get_request_id(request),
        )
    if exc.status_code == 413:
        return build_error_response(
            status_code=413,
            code=ERROR_CODE_REQUEST_TOO_LARGE,
            request_id=_get_request_id(request),
        )
    # 其他 HTTP 异常
    return build_error_response(
        status_code=exc.status_code,
        code=ERROR_CODE_INTERNAL_ERROR,
        request_id=_get_request_id(request),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """未预期异常 → 500，安全消息，不返回 traceback"""
    return build_error_response(
        status_code=500,
        code=ERROR_CODE_INTERNAL_ERROR,
        request_id=_get_request_id(request),
    )
