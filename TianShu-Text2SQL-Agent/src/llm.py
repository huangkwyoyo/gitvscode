"""LLM 接口抽象与 Prompt 加载工具"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Protocol

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


@dataclass(frozen=True)
class LLMRequest:
    """一次 LLM 调用请求"""

    task: str
    prompt: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    """一次 LLM 调用响应"""

    task: str
    content: str
    raw: object | None = None


class LLMClient(Protocol):
    """LLM 客户端协议"""

    def complete(self, request: LLMRequest) -> LLMResponse:
        """执行一次文本补全"""
        ...


class FakeLLMClient:
    """用于离线测试的假 LLM 客户端"""

    def __init__(self, responses: Mapping[str, str]):
        self._responses = dict(responses)

    def complete(self, request: LLMRequest) -> LLMResponse:
        """返回预注册的任务响应"""
        if request.task not in self._responses:
            raise KeyError(f"未注册 LLM 假响应: {request.task}")
        return LLMResponse(
            task=request.task,
            content=self._responses[request.task],
            raw={"source": "fake"},
        )


class MockLLMClient:
    """按任务或用例回放响应的 Mock LLM 客户端"""

    def __init__(self, responses: Mapping[str | tuple[str, str], str]):
        self._responses = dict(responses)
        self.calls: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        """根据 task 和可选 case_id 返回预设响应"""
        self.calls.append(request)
        case_id = request.metadata.get("case_id")
        case_key = (request.task, str(case_id)) if case_id is not None else None
        if case_key is not None and case_key in self._responses:
            content = self._responses[case_key]
        elif request.task in self._responses:
            content = self._responses[request.task]
        else:
            raise KeyError(f"未注册 Mock LLM 响应: {request.task}/{case_id}")
        return LLMResponse(
            task=request.task,
            content=content,
            raw={"source": "mock", "case_id": case_id},
        )


# ── 密钥文件路径（项目级配置，不推远程） ──
# 使用 __file__ 解析绝对路径，避免 CWD 不在项目根时解析失败
_SECRETS_PATH = Path(__file__).resolve().parent.parent / "config" / "secrets.yml"


def _load_api_key_from_secrets(provider: str = "deepseek") -> str | None:
    """从 config/secrets.yml 中加载 API 密钥（兜底方案）"""
    if not _HAS_YAML:
        return None
    if not _SECRETS_PATH.exists():
        return None
    try:
        secrets = yaml.safe_load(_SECRETS_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    # 支持两种写法：顶层 key 或嵌套 provider.key
    key = secrets.get(f"{provider}_api_key")
    if key:
        return str(key)
    provider_cfg = secrets.get(provider, {})
    if isinstance(provider_cfg, dict):
        key = provider_cfg.get("api_key")
        if key:
            return str(key)
    return None


def _resolve_api_key(
    api_key: str | None = None,
    env_var: str = "OPENAI_API_KEY",
    provider: str = "deepseek",
) -> str | None:
    """按优先级获取 API 密钥：参数 → 环境变量 → secrets 文件"""
    if api_key:
        return api_key
    from_env = os.getenv(env_var)
    if from_env:
        return from_env
    return _load_api_key_from_secrets(provider)


class OpenAIChatLLMClient:
    """基于 OpenAI Chat Completions API 的真实 LLM 客户端（兼容 DeepSeek 等）"""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "deepseek-v4-pro",
        base_url: str = "https://api.deepseek.com/v1",  # 实际端点: /v1/chat/completions
        timeout_seconds: int = 60,
        provider: str = "deepseek",
    ):
        # 按优先级解析密钥：参数 > OPENAI_API_KEY 环境变量 > config/secrets.yml
        self._api_key = _resolve_api_key(api_key, provider=provider)
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def complete(self, request: LLMRequest) -> LLMResponse:
        """调用 Chat Completions API 并返回文本输出。

        内置重试机制：网络层错误（URLError、socket.timeout）和可重试的 HTTP 错误
        （429 限流、5xx 服务端错误）最多重试 2 次，使用指数退避。
        400 类请求格式错误不重试，直接抛出。
        """
        if not self._api_key:
            raise ValueError(
                "缺少 API 密钥，请通过参数 api_key、环境变量 OPENAI_API_KEY "
                "或 config/secrets.yml 提供密钥"
            )

        payload = {
            "model": self._model,
            "messages": [
                {"role": "user", "content": request.prompt},
            ],
        }

        max_retries = 2
        last_error: str | None = None

        for attempt in range(max_retries + 1):
            try:
                http_request = urllib.request.Request(
                    url=f"{self._base_url}/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(
                    http_request, timeout=self._timeout_seconds,
                ) as response:
                    raw = json.loads(response.read().decode("utf-8"))

                return LLMResponse(
                    task=request.task,
                    content=self._extract_output_text(raw),
                    raw=raw,
                )

            except urllib.error.HTTPError as exc:
                # 读取错误响应体（如有）
                try:
                    error_body = exc.read().decode("utf-8") if exc.fp else ""
                except Exception:
                    error_body = ""
                last_error = (
                    f"HTTP {exc.code} {exc.reason}"
                    f"{': ' + error_body[:200] if error_body else ''}"
                )
                # 400 系列：请求格式问题，重试无意义
                if 400 <= exc.code < 500 and exc.code != 429:
                    raise RuntimeError(
                        f"LLM API 请求错误: {last_error}"
                    ) from exc
                # 429（限流）和 5xx（服务端错误）：可重试

            except urllib.error.URLError as exc:
                last_error = f"网络错误: {exc.reason}"
                # URLError 通常是网络层问题（DNS、连接拒绝、socket 关闭），可重试

            except socket.timeout:
                last_error = f"请求超时（{self._timeout_seconds}s）"

            except OSError as exc:
                last_error = f"系统网络错误: {exc}"
                # socket 意外关闭等底层错误，可重试

            # ── 重试前等待（指数退避）──
            if attempt < max_retries:
                backoff = 2 ** attempt  # 1s, 2s
                time.sleep(backoff)

        raise RuntimeError(
            f"LLM API 调用失败（{max_retries + 1} 次尝试后仍失败）: {last_error}"
        )

    def _extract_output_text(self, raw: dict) -> str:
        """从 Chat Completions API 响应中提取文本内容"""
        # 标准 Chat Completions 格式：choices[0].message.content
        choices = raw.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()

        raise ValueError("Chat Completions API 响应中没有可用文本输出")


class PromptLoader:
    """按任务名加载 prompts 目录下的模板"""

    def __init__(self, prompt_dir: Path | str = "prompts"):
        self._prompt_dir = Path(prompt_dir)

    def load(self, name: str) -> str:
        """加载指定 Prompt 模板"""
        path = self._prompt_dir / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt 模板不存在: {path}")
        return path.read_text(encoding="utf-8")
