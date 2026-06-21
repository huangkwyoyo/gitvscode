"""Phase 6B —— 受控 Agent 运行时。

职责：
    1. 生命周期内只持有一个 Text2SQLAgent
    2. startup 创建 Agent，shutdown 调用 Agent.close()
    3. 使用 asyncio.Lock 串行保护 ask()
    4. 同步 agent.ask() 使用线程执行，避免阻塞 event loop
    5. 等待锁超时返回 SERVICE_BUSY
    6. 不读取或修改 SQL、不读取 API Key
    7. 不保存 question/answer 到持久化日志

并发模型：
    单进程 + 单 Text2SQLAgent + API 层 asyncio.Lock + 同一时间最多一个 ask()
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import yaml

from ..agent import Text2SQLAgent
from ..response_contract import build_public_response

logger = logging.getLogger("tianshu.api.runtime")


class ServiceBusyError(Exception):
    """等待锁超时，服务繁忙"""


class ServiceNotReadyError(Exception):
    """Agent 不在线，服务不可用"""


class AgentRuntime:
    """受控的 Text2SQLAgent 运行时。

    使用方式：
        runtime = AgentRuntime(
            agent_config_path="config/agent_config.yml",
            tianshu_config_path="config/tianshu_target.yml",
            api_config_path="config/api_config.yml",
        )
        await runtime.start()
        result = await runtime.ask("2026年1月每天有多少行程？")
        await runtime.close()
    """

    def __init__(
        self,
        agent_config_path: str = "config/agent_config.yml",
        tianshu_config_path: str = "config/tianshu_target.yml",
        api_config_path: str = "config/api_config.yml",
    ):
        self._agent_config_path = agent_config_path
        self._tianshu_config_path = tianshu_config_path
        self._api_config_path = api_config_path
        self.api_config: dict[str, Any] = {}

        # Agent 实例（startup 后创建）
        self.agent: Text2SQLAgent | None = None

        # 并发控制
        self._lock = asyncio.Lock()
        self._max_concurrent: int = 1
        self._queue_timeout: float = 2.0

        # 线程池（用于执行同步 agent.ask()）
        self._executor: ThreadPoolExecutor | None = None

        # 日志安全：只记录 request_id / route / HTTP status / duration_ms / response_type / error code
        self._logger = logging.getLogger("tianshu.api")

        # Phase 6C：安全组件引用（由 app.py 的 main() 注入）
        self._local_auth = None
        self._rate_limiter_cfg: dict[str, Any] = {}

    async def start(self) -> None:
        """启动 Agent 运行时：加载配置、创建 Agent 实例。

        应在 FastAPI startup 事件中调用。
        """
        # ── 加载 API 配置 ──
        self._load_api_config()

        # ── 提取运行时参数 ──
        runtime_cfg = self.api_config.get("runtime", {})
        self._max_concurrent = runtime_cfg.get("max_concurrent_agent_requests", 1)
        self._queue_timeout = runtime_cfg.get("queue_wait_timeout_seconds", 2)

        # ── 创建 Agent（rule 模式，不调用真实 LLM）──
        try:
            self.agent = Text2SQLAgent(
                agent_config_path=self._agent_config_path,
                tianshu_config_path=self._tianshu_config_path,
                mode="rule",
            )
            logger.info("Agent 实例已创建，online=%s", self.agent.is_online)
        except Exception as exc:
            logger.error("Agent 创建失败: %s", exc)
            # 创建失败时，agent 保持 None
            # readiness() 会报告 not_ready
            raise

        # ── 创建线程池（用于同步 agent.ask() 不阻塞 event loop）──
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent")

    async def close(self) -> None:
        """关闭 Agent 运行时：释放 Agent 和线程池。

        应在 FastAPI shutdown 事件中调用。
        """
        # ── 关闭 Agent ──
        if self.agent is not None:
            try:
                self.agent.close()
                logger.info("Agent 已关闭")
            except Exception as exc:
                logger.warning("Agent 关闭时出现异常: %s", exc)
            self.agent = None

        # ── 关闭线程池 ──
        if self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None

    async def ask(self, question: str) -> dict[str, Any]:
        """受控执行问数请求。

        流程：
            1. 检查 Agent 在线状态
            2. 获取 asyncio.Lock（超时返回 SERVICE_BUSY）
            3. 在线程池中同步执行 agent.ask()
            4. 通过 build_public_response() 构建公开响应
            5. 释放锁

        Args:
            question: 用户中文问题（已由 API 层校验）

        Returns:
            公开响应 dict（contract v1.0）

        Raises:
            ServiceNotReadyError: Agent 不在线
            ServiceBusyError: 等待锁超时
        """
        # ── 前置检查：Agent 是否在线 ──
        if self.agent is None or not self.agent.is_online:
            raise ServiceNotReadyError("问数服务暂不可用")

        # ── 获取锁（带超时）──
        try:
            acquired = await asyncio.wait_for(
                self._lock.acquire(),
                timeout=self._queue_timeout,
            )
        except asyncio.TimeoutError:
            raise ServiceBusyError("当前问数请求较多，请稍后再试") from None

        if not acquired:
            raise ServiceBusyError("当前问数请求较多，请稍后再试")

        try:
            # ── 在线程池中执行同步 agent.ask()，避免阻塞 event loop ──
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                self._executor,
                self.agent.ask,
                question,
            )

            # ── 构建公开响应 ──
            public = build_public_response(response)
            return public

        finally:
            self._lock.release()

    def readiness(self) -> dict[str, Any]:
        """返回 Agent 就绪状态。

        Returns:
            {"status": "ready"|"not_ready", "agent_online": bool, "contract_version": str}
        """
        online = self.agent is not None and self.agent.is_online

        if online:
            return {
                "status": "ready",
                "agent_online": True,
                "contract_version": "1.0",
            }
        else:
            return {
                "status": "not_ready",
                "agent_online": False,
            }

    # ═══════════════════════════════════════════════════════════════
    # 内部方法
    # ═══════════════════════════════════════════════════════════════

    def _load_api_config(self) -> None:
        """加载 API 配置文件，缺失或非法时 fail closed。

        默认值安全：
            - host=127.0.0.1（不绑定 0.0.0.0）
            - cors_enabled=false
            - max_question_length=2000
        """
        config_path = Path(self._api_config_path)
        if not config_path.exists():
            logger.warning("API 配置文件 %s 不存在，使用安全默认值", self._api_config_path)
            self.api_config = _DEFAULT_API_CONFIG
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
        except Exception as exc:
            logger.error("API 配置文件解析失败: %s，使用安全默认值", exc)
            self.api_config = _DEFAULT_API_CONFIG
            return

        # ── 校验必填段，缺失时 fail closed ──
        required_sections = ["server", "runtime", "request", "security"]
        for section in required_sections:
            if section not in loaded:
                logger.warning(
                    "API 配置缺少 '%s' 段，使用安全默认值", section
                )
                loaded[section] = _DEFAULT_API_CONFIG.get(section, {})

        # Phase 6C：local_security 段为可选（缺失时使用安全默认值）
        if "local_security" not in loaded:
            loaded["local_security"] = _DEFAULT_API_CONFIG.get("local_security", {})

        # ── 安全强制：host 不得为 0.0.0.0 ──
        server_cfg = loaded.get("server", {})
        if server_cfg.get("host") == "0.0.0.0":
            logger.warning("API 配置 host 为 0.0.0.0，已重置为 127.0.0.1")
            server_cfg["host"] = "127.0.0.1"

        # ── 安全强制：cors 不得开启 ──
        security_cfg = loaded.get("security", {})
        if security_cfg.get("cors_enabled") is True:
            logger.warning("API 配置 cors_enabled=true，已重置为 false")
            security_cfg["cors_enabled"] = False

        # ── 安全强制：local_secure_mode 必须为 True（fail-closed）──
        # 类型校验：非 bool 类型（字符串/数字/None）视为非法配置
        raw_secure_mode = security_cfg.get("local_secure_mode")
        if raw_secure_mode is not True:
            if not isinstance(raw_secure_mode, bool):
                logger.warning(
                    "API 配置 local_secure_mode 类型非法（%s），已强制为 True",
                    type(raw_secure_mode).__name__,
                )
            elif raw_secure_mode is False:
                logger.warning("API 配置 local_secure_mode=false，已强制为 True（安全闭环不允许关闭认证）")
            security_cfg["local_secure_mode"] = True

        # ── 安全强制：限流默认启用 ──
        local_sec_cfg = loaded.get("local_security", {})
        rate_cfg = local_sec_cfg.get("rate_limit", {})
        if not rate_cfg.get("enabled", True):
            logger.warning("API 配置 rate_limit.enabled=false，已强制启用限流")
            rate_cfg["enabled"] = True

        self.api_config = loaded


# ── 安全默认配置（fail closed）──
_DEFAULT_API_CONFIG: dict[str, Any] = {
    "server": {"host": "127.0.0.1", "port": 8000},
    "runtime": {
        "max_concurrent_agent_requests": 1,
        "queue_wait_timeout_seconds": 2,
    },
    "request": {
        "max_question_length": 2000,
        "max_body_bytes": 8192,
    },
    "security": {
        "local_secure_mode": True,   # 安全默认：配置缺失时必须 fail-closed
        "token_env": "TIANSHU_LOCAL_API_TOKEN",
        "cors_enabled": False,
        "expose_internal_errors": False,
        "docs_enabled": True,
    },
    "local_security": {
        "rate_limit": {
            "enabled": True,          # 安全默认：配置缺失时默认启用限流
            "requests_per_minute": 30,
            "burst": 3,
        },
        "audit": {
            "enabled": True,          # 安全默认：配置缺失时默认启用审计
            "directory": "harness/reports/local_api_audit",
        },
    },
}
