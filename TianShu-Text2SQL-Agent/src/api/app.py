"""Phase 6B —— FastAPI 只读 REST API 应用。

端点：
    GET  /health/live    — 进程存活
    GET  /health/ready   — Agent、contracts、DuckDB 是否可用
    POST /v1/ask         — 中文问数，返回 contract v1.0

安全边界：
    - HTTP 层只能调用 Text2SQLAgent.ask()
    - 只能返回 build_public_response()
    - 不提供 /sql、/execute、/debug、/trace
    - 不接受 SQL、SQLPlan、表名、config、API Key 等控制参数
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .schemas import AskRequest
from .errors import (
    ERROR_CODE_INTERNAL_ERROR,
    ERROR_CODE_SERVICE_BUSY,
    ERROR_CODE_SERVICE_NOT_READY,
    build_error_response,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from .runtime import AgentRuntime, ServiceBusyError, ServiceNotReadyError

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("tianshu.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期管理：startup → yield → shutdown"""
    # ── Startup ──
    runtime: AgentRuntime = app.state.runtime
    try:
        await runtime.start()
        logger.info("AgentRuntime 启动完成，online=%s", runtime.agent.is_online if runtime.agent else False)
    except Exception as exc:
        logger.error("AgentRuntime 启动失败: %s", exc)
        # 不阻止应用启动 —— readiness 会报告 not_ready
        pass

    yield

    # ── Shutdown ──
    try:
        await runtime.close()
        logger.info("AgentRuntime 已关闭")
    except Exception as exc:
        logger.error("AgentRuntime 关闭时出现异常: %s", exc)


def create_app(runtime: AgentRuntime | None = None) -> FastAPI:
    """创建 FastAPI 应用实例。

    Args:
        runtime: AgentRuntime 实例（用于测试注入 mock）

    Returns:
        配置好的 FastAPI 应用
    """
    if runtime is None:
        runtime = AgentRuntime()

    app = FastAPI(
        title="TianShu Text2SQL Agent API",
        description="基于 Phase 6A 统一公开响应契约的只读中文问数服务",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
    )

    # ── 存储 runtime 引用 ──
    app.state.runtime = runtime

    # ── 默认关闭 CORS ──
    # （runtime.api_config 在 startup 前不可用，此处不添加 CORS middleware）

    # ── 注册异常处理器 ──
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ── 请求 ID 中间件 ──
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

    # ═══════════════════════════════════════════════════════════
    # 端点
    # ═══════════════════════════════════════════════════════════

    @app.get("/health/live")
    async def health_live(request: Request):
        """进程存活检查。

        始终返回 200，不查询业务数据。
        """
        return JSONResponse(content={"status": "alive"})

    @app.get("/health/ready")
    async def health_ready(request: Request):
        """就绪状态检查。

        Agent 在线时返回 200，离线时返回 503。
        不返回数据库绝对路径、contracts 内容或异常堆栈。
        """
        runtime: AgentRuntime = request.app.state.runtime
        state = runtime.readiness()

        if state["status"] == "ready":
            return JSONResponse(content=state, status_code=200)
        else:
            return JSONResponse(content=state, status_code=503)

    @app.post("/v1/ask")
    async def ask(ask_req: AskRequest, request: Request):
        """中文问数入口。

        只接受 question 字段，通过 Text2SQLAgent.ask() → build_public_response() 返回。
        不接受 SQL、SQLPlan、config、API Key 等控制参数。

        HTTP 语义：
            - answer / clarification / refusal → 200
            - Agent offline / not ready → 503
            - 服务繁忙 → 429
            - 未预期异常 → 500（安全脱敏）
        """
        runtime: AgentRuntime = request.app.state.runtime

        try:
            public = await runtime.ask(ask_req.question)
            return JSONResponse(content=public, status_code=200)

        except ServiceNotReadyError:
            return build_error_response(
                status_code=503,
                code=ERROR_CODE_SERVICE_NOT_READY,
                request_id=getattr(request.state, "request_id", ""),
            )

        except ServiceBusyError:
            return build_error_response(
                status_code=429,
                code=ERROR_CODE_SERVICE_BUSY,
                request_id=getattr(request.state, "request_id", ""),
            )

        except Exception:
            # 未预期异常已在 unhandled_exception_handler 中处理
            # 此处兜底确保安全
            logger.exception("ask endpoint 未预期异常")
            return build_error_response(
                status_code=500,
                code=ERROR_CODE_INTERNAL_ERROR,
                request_id=getattr(request.state, "request_id", ""),
            )

    return app


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

    app = create_app(runtime=runtime)

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
