"""Phase 6C —— 本地访问令牌认证。

职责：
    1. 只保护 POST /v1/ask
    2. 健康检查（/health/live, /health/ready）保持无认证
    3. 只接受 X-TianShu-Token 请求头
    4. 令牌来源只限环境变量 TIANSHU_LOCAL_API_TOKEN
    5. 使用 hmac.compare_digest() 常量时间比较
    6. 不记录令牌、错误响应不回显令牌

禁止的令牌来源：
    - URL query
    - request body
    - Cookie
    - YAML 明文
    - Git 仓库文件
    - Authorization Bearer
    - 命令行明文参数
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import Any

from fastapi import Request

logger = logging.getLogger("tianshu.api.auth")


# ── 令牌最小长度 ──
_MIN_TOKEN_LENGTH = 32


class LocalAuthError(Exception):
    """本地认证失败异常。

    属性：
        status_code: HTTP 状态码（始终 401）
        message: 安全错误消息（不含令牌值）
    """

    def __init__(self, message: str = "认证失败"):
        self.status_code = 401
        self.message = message
        super().__init__(message)


class LocalTokenAuth:
    """本地访问令牌认证器。

    只验证 X-TianShu-Token 请求头中的令牌是否与环境变量匹配。
    在 secure_mode 下，令牌缺失或太短会导致服务 not-ready。

    使用方式：
        auth = LocalTokenAuth(
            local_secure_mode=True,
            token_env="TIANSHU_LOCAL_API_TOKEN",
        )
        # 检查就绪状态
        if not auth.is_ready:
            raise SomeError(auth.ready_error)
        # 认证请求
        auth.authenticate(request)
    """

    def __init__(
        self,
        local_secure_mode: bool = True,  # 安全默认：必须 fail-closed
        token_env: str = "TIANSHU_LOCAL_API_TOKEN",
    ):
        self._secure_mode = local_secure_mode
        self._token_env = token_env
        self._ready_error: str | None = None

        # ── 加载令牌 ──
        self._token: str | None = None
        self._load_token()

    # ═══════════════════════════════════════════════════════════
    # 公开属性
    # ═══════════════════════════════════════════════════════════

    @property
    def is_ready(self) -> bool:
        """认证器是否就绪。

        secure_mode 启用时：
            - 令牌环境变量必须存在
            - 令牌长度必须 >= 32
        非 secure_mode 时始终就绪。
        """
        return self._ready_error is None

    @property
    def ready_error(self) -> str | None:
        """就绪失败原因（用于 /health/ready 报告）"""
        return self._ready_error

    @property
    def secure_mode(self) -> bool:
        """是否启用安全模式"""
        return self._secure_mode

    # ═══════════════════════════════════════════════════════════
    # 认证入口
    # ═══════════════════════════════════════════════════════════

    def authenticate(self, request: Request) -> None:
        """对请求执行令牌认证。

        仅在 secure_mode 启用时执行实际校验。
        非 secure_mode 时直接通过。

        Args:
            request: FastAPI Request 对象

        Raises:
            LocalAuthError: 认证失败（始终 401）
        """
        # 非安全模式：跳过认证
        if not self._secure_mode:
            return

        # 如果认证器自身不可用（例如 token 缺失），拒绝所有请求
        if not self.is_ready:
            raise LocalAuthError("认证服务未就绪")

        # 从请求中提取令牌
        provided = _extract_token_from_request(request)

        # 校验令牌
        if not _validate_token(self._token, provided):
            raise LocalAuthError("认证失败")

    # ═══════════════════════════════════════════════════════════
    # 内部方法
    # ═══════════════════════════════════════════════════════════

    def _load_token(self) -> None:
        """从环境变量加载令牌并校验。

        在 secure_mode 下校验失败会设置 _ready_error。
        """
        if not self._secure_mode:
            # 非安全模式：不需要令牌
            self._ready_error = None
            return

        # 检查环境变量中是否有明文 token（YAML 中不应有 token 字段，
        # 此检查由 parse_local_security_config() 完成）
        raw = os.environ.get(self._token_env, "")

        if not raw:
            self._ready_error = (
                f"本地安全模式已启用，但环境变量 {self._token_env} 未设置"
            )
            logger.warning(self._ready_error)
            return

        if len(raw) < _MIN_TOKEN_LENGTH:
            self._ready_error = (
                f"本地令牌长度不足（需要至少 {_MIN_TOKEN_LENGTH} 字符）"
            )
            logger.warning(self._ready_error)
            return

        # 令牌有效
        self._token = raw
        self._ready_error = None


# ═══════════════════════════════════════════════════════════════
# 模块级辅助函数
# ═══════════════════════════════════════════════════════════════


def _extract_token_from_request(request: Request) -> str | None:
    """从请求中提取令牌。

    只接受 X-TianShu-Token 请求头。
    不接受 URL query、body、Cookie、Authorization Bearer。

    Args:
        request: FastAPI Request 对象

    Returns:
        令牌字符串，不存在或为空时返回 None
    """
    token = request.headers.get("X-TianShu-Token", "")
    if not token or not token.strip():
        return None
    return token.strip()


def _validate_token(stored: str | None, provided: str | None) -> bool:
    """常量时间比较令牌。

    使用 hmac.compare_digest() 防止时序攻击。

    Args:
        stored: 存储的令牌
        provided: 请求中提供的令牌

    Returns:
        True 表示匹配
    """
    if not stored or not provided:
        return False
    return hmac.compare_digest(stored, provided)


def _is_secure_mode(api_config: dict[str, Any]) -> bool:
    """从 API 配置中读取 secure_mode 设置。

    安全默认：缺失或非法时返回 True（fail-closed）。

    Args:
        api_config: 完整的 API 配置字典

    Returns:
        True 表示启用了本地安全模式
    """
    security = api_config.get("security", {})
    raw = security.get("local_secure_mode", True)
    # 类型校验：非 bool 类型视为非法，强制返回 True
    if not isinstance(raw, bool):
        return True
    # 显式 False 也强制返回 True（安全闭环不允许关闭认证）
    if raw is False:
        return True
    return True


def parse_local_security_config(api_config: dict[str, Any]) -> dict[str, Any]:
    """解析本地安全配置段。

    Args:
        api_config: 完整的 API 配置字典

    Returns:
        本地安全配置字典，包含：
            - local_secure_mode: bool
            - token_env: str
            - rate_limit_enabled: bool
            - requests_per_minute: int
            - burst: int
            - audit_enabled: bool
            - audit_directory: str

    Raises:
        ValueError: YAML 中出现明文 token 字段时
    """
    security = api_config.get("security", {})
    local_sec = api_config.get("local_security", {})

    # ── 安全检查：YAML 中不得出现明文 token ──
    if "token" in local_sec:
        raise ValueError(
            "配置文件中不得包含明文 token 字段。"
            "请使用环境变量提供令牌。"
        )

    # ── 安全强制：local_secure_mode 类型校验 ──
    raw_secure_mode = security.get("local_secure_mode", True)
    if not isinstance(raw_secure_mode, bool):
        # 非 bool 类型（字符串/数字/None）→ 强制 True
        logger.warning(
            "API 配置 local_secure_mode 类型非法（%s），已强制为 True",
            type(raw_secure_mode).__name__,
        )
        raw_secure_mode = True
    elif raw_secure_mode is False:
        # 显式关闭 → 强制 True（安全闭环不允许关闭认证）
        logger.warning("API 配置 local_secure_mode=false，已强制为 True")
        raw_secure_mode = True

    rate_cfg = local_sec.get("rate_limit", {})
    audit_cfg = local_sec.get("audit", {})

    return {
        "local_secure_mode": raw_secure_mode,  # 经过类型校验的安全值
        "token_env": security.get("token_env", "TIANSHU_LOCAL_API_TOKEN"),
        "rate_limit_enabled": rate_cfg.get("enabled", True),  # 安全默认：启用限流
        "requests_per_minute": rate_cfg.get("requests_per_minute", 30),
        "burst": rate_cfg.get("burst", 3),
        "audit_enabled": audit_cfg.get("enabled", True),  # 安全默认：启用审计
        "audit_directory": audit_cfg.get("directory", "harness/reports/local_api_audit"),
    }
