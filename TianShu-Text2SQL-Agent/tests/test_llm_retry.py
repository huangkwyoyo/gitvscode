"""
LLM API 异常处理与重试机制测试。

验证 OpenAIChatLLMClient.complete() 在网络异常时的行为：
    - 网络错误（URLError）→ 重试
    - 超时（socket.timeout）→ 重试
    - HTTP 429（限流）→ 重试
    - HTTP 5xx（服务端错误）→ 重试
    - HTTP 400（请求错误）→ 不重试
    - 成功时 → 不重试
"""
import json
import socket
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from src.llm import LLMRequest, OpenAIChatLLMClient


# ── 辅助：构造一个带假密钥的客户端 ──

def _make_client(model: str = "test-model") -> OpenAIChatLLMClient:
    return OpenAIChatLLMClient(
        api_key="sk-test-dummy-key",
        model=model,
        base_url="https://api.test.example/v1",
        timeout_seconds=5,
    )


# ── 实际网络调用测试 ──


class TestRetryOnNetworkErrors:
    """网络层错误应触发重试"""

    def test_retries_on_urlerror(self):
        """URLError（连接拒绝/DNS 失败）应重试，3次均失败后抛出 RuntimeError"""
        client = _make_client()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            with pytest.raises(RuntimeError, match="3 次尝试"):
                client.complete(LLMRequest(task="test", prompt="hello"))

            # 应尝试 3 次（1 次原始 + 2 次重试）
            assert mock_urlopen.call_count == 3

    def test_retries_on_socket_timeout(self):
        """socket.timeout 应重试"""
        client = _make_client()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = socket.timeout("timed out")

            with pytest.raises(RuntimeError, match="3 次尝试"):
                client.complete(LLMRequest(task="test", prompt="hello"))

            assert mock_urlopen.call_count == 3

    def test_retries_on_oserror(self):
        """OSError（socket 意外关闭）应重试"""
        client = _make_client()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = OSError("Socket closed unexpectedly")

            with pytest.raises(RuntimeError, match="3 次尝试"):
                client.complete(LLMRequest(task="test", prompt="hello"))

            assert mock_urlopen.call_count == 3


class TestRetryOnHTTPErrors:
    """HTTP 错误：可重试 vs 不重试"""

    def test_http_429_rate_limit_retries(self):
        """429 限流应重试"""
        client = _make_client()

        with patch("urllib.request.urlopen") as mock_urlopen:
            error = urllib.error.HTTPError(
                url="https://api.test.example/v1/chat/completions",
                code=429,
                msg="Too Many Requests",
                hdrs={},
                fp=None,
            )
            mock_urlopen.side_effect = error

            with pytest.raises(RuntimeError, match="3 次尝试"):
                client.complete(LLMRequest(task="test", prompt="hello"))

            assert mock_urlopen.call_count == 3

    def test_http_500_retries(self):
        """500 服务端错误应重试"""
        client = _make_client()

        with patch("urllib.request.urlopen") as mock_urlopen:
            error = urllib.error.HTTPError(
                url="https://api.test.example/v1/chat/completions",
                code=500,
                msg="Internal Server Error",
                hdrs={},
                fp=None,
            )
            mock_urlopen.side_effect = error

            with pytest.raises(RuntimeError, match="3 次尝试"):
                client.complete(LLMRequest(task="test", prompt="hello"))

            assert mock_urlopen.call_count == 3

    def test_http_400_does_not_retry(self):
        """400 请求格式错误不应重试（重试无意义）"""
        client = _make_client()

        with patch("urllib.request.urlopen") as mock_urlopen:
            error = urllib.error.HTTPError(
                url="https://api.test.example/v1/chat/completions",
                code=400,
                msg="Bad Request",
                hdrs={},
                fp=None,
            )
            mock_urlopen.side_effect = error

            with pytest.raises(RuntimeError, match="请求错误"):
                client.complete(LLMRequest(task="test", prompt="hello"))

            # 400 应只尝试 1 次
            assert mock_urlopen.call_count == 1

    def test_http_401_does_not_retry(self):
        """401 认证失败不应重试"""
        client = _make_client()

        with patch("urllib.request.urlopen") as mock_urlopen:
            error = urllib.error.HTTPError(
                url="https://api.test.example/v1/chat/completions",
                code=401,
                msg="Unauthorized",
                hdrs={},
                fp=None,
            )
            mock_urlopen.side_effect = error

            with pytest.raises(RuntimeError, match="请求错误"):
                client.complete(LLMRequest(task="test", prompt="hello"))

            assert mock_urlopen.call_count == 1


class TestNoRetryOnSuccess:
    """成功响应不触发重试"""

    def test_success_on_first_attempt(self):
        """第一次尝试成功 → 不重试"""
        client = _make_client()

        with patch("urllib.request.urlopen") as mock_urlopen:
            # 模拟成功的 HTTP 响应
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps({
                "choices": [
                    {"message": {"content": "Hello, world!"}},
                ],
            }).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_response

            result = client.complete(LLMRequest(task="test", prompt="hello"))

            assert result.content == "Hello, world!"
            assert mock_urlopen.call_count == 1

    def test_success_after_one_retry(self):
        """第一次失败（URLError），第二次成功 → 重试 1 次后返回结果"""
        client = _make_client()

        with patch("urllib.request.urlopen") as mock_urlopen:
            # urlopen 返回的是上下文管理器，其 __enter__ 返回实际响应对象
            # 成功响应：构造完整的 mock 链: urlopen() → ctx → __enter__ → response.read()
            success_ctx = MagicMock()
            success_response = MagicMock()
            success_response.read.return_value = json.dumps({
                "choices": [
                    {"message": {"content": "Recovered!"}},
                ],
            }).encode("utf-8")
            success_ctx.__enter__.return_value = success_response

            mock_urlopen.side_effect = [
                urllib.error.URLError("Temporary failure"),
                success_ctx,
            ]

            result = client.complete(LLMRequest(task="test", prompt="hello"))

            assert result.content == "Recovered!"
            assert mock_urlopen.call_count == 2


class TestErrorMessageQuality:
    """错误消息应包含有效诊断信息"""

    def test_error_message_includes_attempt_count(self):
        """失败消息应包含尝试次数"""
        client = _make_client()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = socket.timeout("timed out")

            with pytest.raises(RuntimeError) as exc_info:
                client.complete(LLMRequest(task="test", prompt="hello"))

            assert "3 次尝试" in str(exc_info.value)
            assert "超时" in str(exc_info.value)

    def test_error_message_includes_http_code(self):
        """HTTP 错误消息应包含状态码"""
        client = _make_client()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                urllib.error.URLError("fail"),
                urllib.error.URLError("fail"),
                urllib.error.URLError("Connection refused"),
            ]

            with pytest.raises(RuntimeError) as exc_info:
                client.complete(LLMRequest(task="test", prompt="hello"))

            assert "Connection refused" in str(exc_info.value)


class TestMissingAPIKey:
    """缺少 API 密钥时应立即失败，不重试"""

    def test_missing_api_key_raises_immediately(self):
        """无 API 密钥 → 直接抛出 ValueError"""
        client = OpenAIChatLLMClient(
            api_key=None,
            base_url="https://api.test.example/v1",
        )
        # 清除环境变量避免干扰
        with patch.dict("os.environ", {}, clear=True):
            with patch("src.llm._SECRETS_PATH", new=None):
                pass
        # 直接设置 _api_key 为 None
        client._api_key = None

        with pytest.raises(ValueError, match="缺少 API 密钥"):
            client.complete(LLMRequest(task="test", prompt="hello"))
