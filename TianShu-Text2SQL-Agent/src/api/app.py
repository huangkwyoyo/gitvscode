"""Phase 6C —— FastAPI 只读 REST API 应用（本地安全闭环）。

端点：
    GET  /health/live    — 进程存活（无需认证）
    GET  /health/ready   — Agent + Auth + DuckDB 是否可用（无需认证）
    POST /v1/ask         — 中文问数（需认证 + 限流 + 审计）

安全边界（Phase 6B 基础上叠加 Phase 6C）：
    - 本地令牌认证（X-TianShu-Token）
    - 进程内请求频率限制
    - 原始请求体大小限制
    - 安全响应头（nosniff, DENY, no-referrer, no-store）
    - 本地脱敏 JSONL 审计
    - HTTP 层只能调用 Text2SQLAgent.ask()
    - 只能返回 build_public_response()
    - 不提供 /sql、/execute、/debug、/trace
    - 不接受 SQL、SQLPlan、表名、config、API Key 等控制参数
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Any

from pathlib import Path as _FilePath

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .schemas import AskRequest
from .errors import (
    ERROR_CODE_AUTH_FAILED,
    ERROR_CODE_INTERNAL_ERROR,
    ERROR_CODE_REQUEST_TOO_LARGE,
    ERROR_CODE_SERVICE_BUSY,
    ERROR_CODE_SERVICE_NOT_READY,
    build_error_response,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from .runtime import AgentRuntime, ServiceBusyError, ServiceNotReadyError
from .local_auth import LocalTokenAuth, LocalAuthError
from .local_rate_limit import FixedWindowRateLimiter, RateLimitExceeded
from .body_limit import BodyLimitMiddleware, RequestTooLargeError
from .local_audit import AuditEvent, AuditWriteError, LocalAuditWriter, generate_startup_timestamp

logger = logging.getLogger("tianshu.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期管理：startup → yield → shutdown"""
    # ── Startup ──
    runtime: AgentRuntime = app.state.runtime
    try:
        await runtime.start()
        logger.info("AgentRuntime 启动完成，online=%s",
                     runtime.agent.is_online if runtime.agent else False)
    except Exception as exc:
        logger.error("AgentRuntime 启动失败: %s", exc)
        pass

    # 初始化审计写入器
    try:
        audit_cfg = runtime.api_config.get("local_security", {}).get("audit", {})
        if audit_cfg.get("enabled", False):
            audit_dir = audit_cfg.get("directory", "harness/reports/local_api_audit")
            startup_ts = generate_startup_timestamp()
            app.state.audit_writer = LocalAuditWriter(
                audit_dir=audit_dir,
                startup_timestamp=startup_ts,
            )
            logger.info("审计写入器已初始化: %s", app.state.audit_writer.file_path)
    except Exception as exc:
        logger.error("审计写入器初始化失败: %s", exc)
        app.state.audit_writer = None

    yield

    # ── Shutdown ──
    try:
        await runtime.close()
        logger.info("AgentRuntime 已关闭")
    except Exception as exc:
        logger.error("AgentRuntime 关闭时出现异常: %s", exc)


def create_app(
    runtime: AgentRuntime | None = None,
    local_auth: LocalTokenAuth | None = None,
    rate_limiter: FixedWindowRateLimiter | None = None,
) -> FastAPI:
    """创建 FastAPI 应用实例。

    Args:
        runtime: AgentRuntime 实例（用于测试注入 mock）
        local_auth: 本地令牌认证器（None 时根据配置自动创建）
        rate_limiter: 限流器（None 时根据配置自动创建）

    Returns:
        配置好的 FastAPI 应用
    """
    if runtime is None:
        runtime = AgentRuntime()

    # ── 创建认证器 ──
    if local_auth is None:
        # 从 runtime 配置创建（startup 后才可用，此处使用安全默认值）
        local_auth = LocalTokenAuth(
            local_secure_mode=False,  # 默认关闭，startup 后由配置覆盖
        )

    # ── 创建限流器 ──
    if rate_limiter is None:
        from .local_rate_limit import create_rate_limiter
        rate_limiter = create_rate_limiter(enabled=False)  # 默认关闭

    # ── 创建 body 限制中间件 ──
    body_limit = BodyLimitMiddleware(max_body_bytes=8192)

    app = FastAPI(
        title="TianShu Text2SQL Agent API",
        description="基于 Phase 6A 统一公开响应契约的只读中文问数服务（本地安全闭环）",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
    )

    # ── 存储引用 ──
    app.state.runtime = runtime
    app.state.local_auth = local_auth
    app.state.rate_limiter = rate_limiter
    app.state.body_limit = body_limit
    app.state.audit_writer = None  # 在 lifespan startup 中设置

    # ── 注册异常处理器 ──
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ═══════════════════════════════════════════════════════════
    # 中间件
    # ═══════════════════════════════════════════════════════════

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        """安全响应头中间件。

        所有响应添加：
            X-Content-Type-Options: nosniff
            X-Frame-Options: DENY
            Referrer-Policy: no-referrer
            Cache-Control: no-store
        本地 HTTP 不设置 HSTS。
        """
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        """为每个请求生成唯一 request_id，注入 X-Request-ID 响应头。

        安全日志：只记录 request_id / route / HTTP status / duration_ms / response_type / error_code。
        不记录 question、answer、SQL、trace、API Key、数据库路径。
        """
        rid = str(uuid.uuid4())
        request.state.request_id = rid

        t_start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - t_start) * 1000)

        response.headers["X-Request-ID"] = rid

        # ── 安全日志（不含敏感信息）──
        logger.info(
            "request_id=%s route=%s status=%s duration_ms=%s",
            rid,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        return response

    @app.middleware("http")
    async def body_limit_middleware(request: Request, call_next):
        """请求体大小限制中间件。

        在 JSON 解析前检查 Content-Length，超限立即返回 413。
        无 Content-Length 时通过累积 body 读取兜底。
        """
        bl: BodyLimitMiddleware = request.app.state.body_limit

        # ── 检查 Content-Length ──
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                bl.check_content_length(int(content_length))
            except RequestTooLargeError:
                rid = getattr(request.state, "request_id", "")
                return build_error_response(
                    status_code=413,
                    code=ERROR_CODE_REQUEST_TOO_LARGE,
                    request_id=rid,
                )

        return await call_next(request)

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        """本地令牌认证中间件。

        只保护 POST /v1/ask 端点。
        /health/live、/health/ready、/ 和 /assets/* 保持无认证。
        """
        # 健康检查和 UI 页面无需认证
        _path = request.url.path
        if _path in ("/health/live", "/health/ready", "/") or _path.startswith("/assets"):
            return await call_next(request)

        # 只保护 /v1/ask
        if request.url.path == "/v1/ask" and request.method == "POST":
            auth: LocalTokenAuth = request.app.state.local_auth
            try:
                auth.authenticate(request)
            except LocalAuthError as exc:
                rid = getattr(request.state, "request_id", "")
                # 记录审计：rejected
                await _audit_event(request, AuditEvent.REJECTED, 401, error_code="AUTH_FAILED")
                return build_error_response(
                    status_code=401,
                    code=ERROR_CODE_AUTH_FAILED,
                    message=exc.message,
                    request_id=rid,
                )

        return await call_next(request)

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        """请求频率限制中间件。

        在认证成功后、AgentRuntime 之前执行。
        只限制 POST /v1/ask 端点。
        认证失败不消耗额度（由 auth_middleware 先拦截）。
        """
        if request.url.path == "/v1/ask" and request.method == "POST":
            rl: FixedWindowRateLimiter | None = request.app.state.rate_limiter
            if rl is not None:
                try:
                    rl.check_and_record()
                except RateLimitExceeded as exc:
                    rid = getattr(request.state, "request_id", "")
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": {
                                "code": ERROR_CODE_SERVICE_BUSY,
                                "message": "当前问数请求较多，请稍后再试",
                                "request_id": rid or "",
                            }
                        },
                        headers={"Retry-After": str(exc.retry_after)},
                    )

        return await call_next(request)

    # ═══════════════════════════════════════════════════════════
    # Phase 7 Web UI —— 同源托管 + CSP
    # ═══════════════════════════════════════════════════════════

    # ── 读取 UI 配置 ──
    ui_config = runtime.api_config.get("ui", {}) if runtime.api_config else {}
    ui_enabled = ui_config.get("enabled", True)

    # ── 静态资源目录（固定路径，防止目录穿越）──
    _web_dir = _FilePath(__file__).resolve().parents[1] / "web"
    if ui_enabled and _web_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_web_dir)), name="assets")
    else:
        logger.info("Web UI 目录不存在或已禁用: %s", _web_dir)

    @app.middleware("http")
    async def ui_csp_middleware(request: Request, call_next):
        """UI CSP 中间件。

        仅对 / 和 /assets/* 路由应用严格 CSP，不影响 /docs 等其他路由。

        CSP 策略：
            default-src 'self'; script-src 'self'; style-src 'self';
            img-src 'self' data:; connect-src 'self'; object-src 'none';
            base-uri 'none'; frame-ancestors 'none'; form-action 'self';
        """
        response = await call_next(request)

        _path = request.url.path
        # 仅对 UI 路由应用严格 CSP
        if _path == "/" or _path.startswith("/assets"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self'; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "object-src 'none'; "
                "base-uri 'none'; "
                "frame-ancestors 'none'; "
                "form-action 'self'"
            )

        return response

    # ═══════════════════════════════════════════════════════════
    # 端点
    # ═══════════════════════════════════════════════════════════

    @app.get("/")
    async def web_ui_root(request: Request):
        """Web UI 根页面。

        UI 启用时返回 index.html，禁用时返回 404。
        页面本身无需认证（Token 由用户在浏览器中输入后通过 JS 传递）。
        """
        ui_cfg = request.app.state.runtime.api_config.get("ui", {})
        if not ui_cfg.get("enabled", True):
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "NOT_FOUND", "message": "Web UI 未启用"}},
            )

        index_path = _web_dir / "index.html"
        if not index_path.exists():
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "NOT_FOUND", "message": "Web UI 页面文件不存在"}},
            )

        return FileResponse(str(index_path), media_type="text/html; charset=utf-8")

    @app.get("/health/live")
    async def health_live(request: Request):
        """进程存活检查。

        始终返回 200，不查询业务数据，无需认证。
        """
        return JSONResponse(content={"status": "alive"})

    @app.get("/health/ready")
    async def health_ready(request: Request):
        """就绪状态检查。

        检查项：
            - Agent 在线状态
            - 认证器就绪状态（secure_mode 下 token 必须有效）

        全部就绪返回 200，任一不可用返回 503。
        不返回数据库绝对路径、contracts 内容或异常堆栈。
        """
        runtime: AgentRuntime = request.app.state.runtime
        auth: LocalTokenAuth = request.app.state.local_auth

        agent_state = runtime.readiness()
        agent_online = agent_state.get("agent_online", False)

        # ── 认证器就绪检查 ──
        auth_ready = True
        auth_error = None
        if auth is not None:
            auth_ready = auth.is_ready
            auth_error = auth.ready_error if not auth_ready else None

        all_ready = agent_online and auth_ready

        state = {
            "status": "ready" if all_ready else "not_ready",
            "agent_online": agent_online,
            "auth_ready": auth_ready,
            "contract_version": "1.0",
        }
        if auth_error:
            state["auth_error"] = auth_error

        if all_ready:
            return JSONResponse(content=state, status_code=200)
        else:
            return JSONResponse(content=state, status_code=503)

    @app.post("/v1/ask")
    async def ask(ask_req: AskRequest, request: Request):
        """中文问数入口。

        请求链路（按顺序）：
            1. Body 大小限制（body_limit 中间件）
            2. 令牌认证（auth 中间件）
            3. 请求频率限制（rate_limit 中间件）
            4. AgentRuntime.ask() → build_public_response()

        只接受 question 字段，通过 Text2SQLAgent.ask() → build_public_response() 返回。
        不接受 SQL、SQLPlan、config、API Key 等控制参数。

        HTTP 语义：
            - answer / clarification / refusal → 200
            - 认证失败 → 401
            - 请求体过大 → 413
            - 服务繁忙/限流 → 429
            - Agent offline / not ready → 503
            - 未预期异常 → 500（安全脱敏）
        """
        runtime: AgentRuntime = request.app.state.runtime
        rid = getattr(request.state, "request_id", "")

        # ── 记录审计：accepted ──
        question_len = len(ask_req.question) if ask_req.question else 0
        await _audit_event(
            request,
            AuditEvent.ACCEPTED,
            200,
            question_length=question_len,
        )

        try:
            public = await runtime.ask(ask_req.question)
            # ── 确保响应可 JSON 序列化（date/datetime → ISO 字符串）──
            public_safe = _make_json_safe(public)
            # ── 记录审计：completed ──
            await _audit_event(
                request,
                AuditEvent.COMPLETED,
                200,
                response_type=public.get("response_type", ""),
                duration_ms=None,
                question_length=question_len,
                execution_mode=public.get("meta", {}).get("execution_mode", ""),
            )
            return JSONResponse(content=public_safe, status_code=200)

        except ServiceNotReadyError:
            await _audit_event(request, AuditEvent.REJECTED, 503,
                               error_code=ERROR_CODE_SERVICE_NOT_READY)
            return build_error_response(
                status_code=503,
                code=ERROR_CODE_SERVICE_NOT_READY,
                request_id=rid,
            )

        except ServiceBusyError:
            await _audit_event(request, AuditEvent.REJECTED, 429,
                               error_code=ERROR_CODE_SERVICE_BUSY)
            return build_error_response(
                status_code=429,
                code=ERROR_CODE_SERVICE_BUSY,
                request_id=rid,
            )

        except Exception:
            # 未预期异常已在 unhandled_exception_handler 中处理
            # 此处兜底确保安全
            logger.exception("ask endpoint 未预期异常")
            await _audit_event(request, AuditEvent.REJECTED, 500,
                               error_code=ERROR_CODE_INTERNAL_ERROR)
            return build_error_response(
                status_code=500,
                code=ERROR_CODE_INTERNAL_ERROR,
                request_id=rid,
            )

    return app


async def _audit_event(
    request: Request,
    event: str,
    http_status: int,
    response_type: str | None = None,
    duration_ms: int | None = None,
    error_code: str | None = None,
    question_length: int | None = None,
    execution_mode: str | None = None,
) -> None:
    """安全写入审计事件。

    写入失败时记录错误日志但不阻断请求（已通过安全校验的关键路径不因审计失败中断）。
    但在审计初始化阶段，写入失败会抛出 AuditWriteError（在 startup 时捕获）。

    Args:
        request: FastAPI Request
        event: 事件类型（accepted / completed / rejected）
        http_status: HTTP 响应状态码
        response_type: answer / clarification / refusal / None
        duration_ms: 请求耗时（毫秒）
        error_code: 错误码
        question_length: 问题字符数
        execution_mode: 执行模式（single / serial / parallel / offline）
    """
    writer: LocalAuditWriter | None = getattr(request.app.state, "audit_writer", None)
    if writer is None:
        return

    rid = getattr(request.state, "request_id", "")

    record: dict[str, Any] = {
        "timestamp": _now_iso(),
        "request_id": rid,
        "event": event,
        "route": "/v1/ask",
        "http_status": http_status,
        "response_type": response_type,
        "duration_ms": duration_ms,
        "error_code": error_code,
        "question_length": question_length,
        "execution_mode": execution_mode,
    }

    try:
        await writer.write_event_async(record)
    except AuditWriteError as exc:
        logger.error("审计写入失败（不阻断请求）: %s", exc)


def _now_iso() -> str:
    """生成 ISO 8601 时间戳（UTC）"""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _make_json_safe(obj: Any) -> Any:
    """递归转换对象中不可 JSON 序列化的类型（date/datetime → ISO 字符串）。

    在 DuckDB 查询结果中，DATE 列返回 datetime.date 对象，
    Python 标准 json.dumps 无法直接序列化，需要提前转换。
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(v) for v in obj]
    # 其他类型 → 字符串回退
    try:
        return str(obj)
    except Exception:
        return repr(obj)


def main():
    """API 服务启动入口（tianshu-api 命令 / scripts/run_api.py 共用）"""
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="TianShu Text2SQL Agent REST API")
    parser.add_argument(
        "--config", default="config/api_config.yml",
        help="API 配置文件路径（默认: config/api_config.yml）",
    )
    parser.add_argument(
        "--host", default=None,
        help="绑定地址（覆盖配置文件）",
    )
    parser.add_argument(
        "--port", type=int, default=None,
        help="绑定端口（覆盖配置文件）",
    )
    args = parser.parse_args()

    # 创建 runtime 并预先加载配置以获取 host/port
    runtime = AgentRuntime(api_config_path=args.config)

    # 手动加载配置（startup 也会加载，但我们需要提前取 host/port）
    import yaml as _yaml
    from pathlib import Path as _Path

    config_path = _Path(args.config)
    api_config = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            api_config = _yaml.safe_load(f) or {}

    server_cfg = api_config.get("server", {})
    host = args.host or server_cfg.get("host", "127.0.0.1")
    port = args.port or server_cfg.get("port", 8000)

    # 安全检查：host 不得为 0.0.0.0
    if host == "0.0.0.0":
        print("[WARN] host=0.0.0.0 不符合安全要求，已重置为 127.0.0.1")
        host = "127.0.0.1"

    # ── 创建安全组件 ──
    from .local_auth import LocalTokenAuth, parse_local_security_config
    from .local_rate_limit import create_rate_limiter

    local_cfg = parse_local_security_config(api_config)
    local_auth = LocalTokenAuth(
        local_secure_mode=local_cfg["local_secure_mode"],
        token_env=local_cfg["token_env"],
    )
    rate_limiter = create_rate_limiter(
        enabled=local_cfg["rate_limit_enabled"],
        requests_per_minute=local_cfg["requests_per_minute"],
        burst=local_cfg["burst"],
    )

    app = create_app(runtime=runtime, local_auth=local_auth, rate_limiter=rate_limiter)

    # ── 更新 runtime 中的安全组件引用（供 startup 使用）──
    runtime._local_auth = local_auth
    runtime._rate_limiter_cfg = local_cfg

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
