"""Phase 6B —— API 请求/响应 Schema 定义。

所有 Schema 使用 Pydantic 严格模式：
    - 拒绝未知字段（extra = forbid）
    - question 必填、trim 后不能为空
    - max_length 受配置限制
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class AskRequest(BaseModel):
    """POST /v1/ask 请求体。

    只接受 question 字段，拒绝 SQL、mode、config、provider 等控制参数。
    """

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="用户的中文问数问题",
    )

    model_config = {
        "extra": "forbid",  # 拒绝未知字段（mode, sql, provider 等）
        "json_schema_extra": {
            "example": {"question": "2026年1月每天有多少行程？"},
        },
    }

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, v: str) -> str:
        """trim 后不能为空字符串"""
        stripped = v.strip()
        if not stripped:
            raise ValueError("问题不能为空")
        return stripped


class ApiErrorResponse(BaseModel):
    """API 错误响应 envelope。

    安全约束：
        - 不包含 SQL、trace、API Key、数据库路径、异常堆栈
        - message 使用中文用户友好描述
        - request_id 用于关联日志
    """

    error: ApiErrorDetail


class ApiErrorDetail(BaseModel):
    """API 错误详情"""
    code: str = Field(..., description="错误码，如 VALIDATION_ERROR, SERVICE_NOT_READY")
    message: str = Field(..., description="用户友好的中文错误消息")
    request_id: str = Field("", description="服务端生成的请求 ID（UUID）")
