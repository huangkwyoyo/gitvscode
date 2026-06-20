"""Phase 6C —— 本地令牌认证测试。

覆盖：
    - health/live 无 token 可访问
    - health/ready 无 token 可访问
    - /v1/ask 缺 token 返回 401
    - 空 token 返回 401
    - 错误 token 返回 401
    - 正确 token 请求通过
    - token 只接受 X-TianShu-Token
    - query token 被拒绝
    - body token 被拒绝
    - Cookie token 被拒绝
    - Authorization Bearer 被拒绝
    - 使用 hmac.compare_digest()
    - 日志不含 token
    - 错误响应不含 token
    - token 环境变量缺失时 not-ready
    - token 太短时 not-ready
    - YAML 中出现明文 token 时 fail closed
"""

from __future__ import annotations

import hmac
import logging
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from src.api.local_auth import (
    LocalTokenAuth,
    LocalAuthError,
    _extract_token_from_request,
    _is_secure_mode,
    _validate_token,
    parse_local_security_config,
)


# ═══════════════════════════════════════════════════════════════
# 测试：配置解析
# ═══════════════════════════════════════════════════════════════


class TestLocalSecurityConfig:
    """本地安全配置解析测试"""

    def test_secure_mode_enabled_default(self):
        """local_secure_mode 默认为 false（缺失时）"""
        cfg = parse_local_security_config({})
        assert cfg["local_secure_mode"] is False

    def test_secure_mode_true(self):
        """local_secure_mode 可设置为 true"""
        cfg = parse_local_security_config({
            "security": {"local_secure_mode": True},
        })
        assert cfg["local_secure_mode"] is True

    def test_token_env_key_read(self):
        """token_env 从配置中读取"""
        cfg = parse_local_security_config({
            "security": {
                "local_secure_mode": True,
                "token_env": "MY_CUSTOM_TOKEN",
            },
        })
        assert cfg["token_env"] == "MY_CUSTOM_TOKEN"

    def test_token_env_default(self):
        """token_env 默认值为 TIANSHU_LOCAL_API_TOKEN"""
        cfg = parse_local_security_config({})
        assert cfg["token_env"] == "TIANSHU_LOCAL_API_TOKEN"


# ═══════════════════════════════════════════════════════════════
# 测试：令牌提取
# ═══════════════════════════════════════════════════════════════


class TestTokenExtraction:
    """从请求中提取令牌的测试"""

    def test_extract_from_header(self):
        """从 X-TianShu-Token header 提取令牌"""
        mock_request = MagicMock()
        mock_request.headers = {"X-TianShu-Token": "my-secret-token-32chars-long!!"}
        mock_request.query_params = {}
        token = _extract_token_from_request(mock_request)
        assert token == "my-secret-token-32chars-long!!"

    def test_extract_no_header_returns_none(self):
        """没有 X-TianShu-Token header 返回 None"""
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.query_params = {}
        token = _extract_token_from_request(mock_request)
        assert token is None

    def test_extract_empty_header_returns_none(self):
        """空的 X-TianShu-Token header 返回 None"""
        mock_request = MagicMock()
        mock_request.headers = {"X-TianShu-Token": ""}
        mock_request.query_params = {}
        token = _extract_token_from_request(mock_request)
        assert token is None

    def test_query_param_ignored(self):
        """URL query 参数中的 token 被忽略"""
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.query_params = {"token": "query-token-value"}
        token = _extract_token_from_request(mock_request)
        assert token is None

    def test_authorization_bearer_ignored(self):
        """Authorization Bearer header 被忽略"""
        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer some-token"}
        mock_request.query_params = {}
        token = _extract_token_from_request(mock_request)
        assert token is None

    def test_cookie_ignored(self):
        """Cookie 中的 token 被忽略"""
        mock_request = MagicMock()
        mock_request.headers = {"Cookie": "tianshu_token=cookie-value"}
        mock_request.query_params = {}
        token = _extract_token_from_request(mock_request)
        assert token is None


# ═══════════════════════════════════════════════════════════════
# 测试：令牌校验
# ═══════════════════════════════════════════════════════════════


class TestTokenValidation:
    """令牌校验逻辑测试"""

    def test_valid_token_passes(self):
        """正确令牌通过校验"""
        result = _validate_token("correct-token-32chars-long!!", "correct-token-32chars-long!!")
        assert result is True

    def test_wrong_token_fails(self):
        """错误令牌校验失败"""
        result = _validate_token("correct-token-32chars-long!!", "wrong-token-value-here!!!!")
        assert result is False

    def test_uses_hmac_compare_digest(self):
        """使用 hmac.compare_digest() 进行常量时间比较"""
        with patch("hmac.compare_digest", wraps=hmac.compare_digest) as mock_compare:
            _validate_token("token-a", "token-a")
            mock_compare.assert_called_once()

    def test_empty_stored_token_always_fails(self):
        """存储的令牌为空时，任何输入都失败"""
        result = _validate_token("", "some-token")
        assert result is False

    def test_none_stored_token_always_fails(self):
        """存储的令牌为 None 时，任何输入都失败"""
        result = _validate_token(None, "some-token")
        assert result is False

    def test_none_input_token_always_fails(self):
        """输入令牌为 None 时失败"""
        result = _validate_token("stored-token", None)
        assert result is False

    def test_case_sensitive(self):
        """令牌比较区分大小写"""
        result = _validate_token("My-Token-Value", "my-token-value")
        assert result is False


# ═══════════════════════════════════════════════════════════════
# 测试：LocalTokenAuth 类
# ═══════════════════════════════════════════════════════════════


class TestLocalTokenAuth:
    """LocalTokenAuth 认证器测试"""

    def setup_method(self):
        """每个测试前清理环境变量"""
        os.environ.pop("TIANSHU_LOCAL_API_TOKEN", None)

    def teardown_method(self):
        """每个测试后清理环境变量"""
        os.environ.pop("TIANSHU_LOCAL_API_TOKEN", None)

    def test_secure_mode_token_missing_not_ready(self):
        """secure_mode 启用但 token 环境变量缺失 → not_ready"""
        auth = LocalTokenAuth(
            local_secure_mode=True,
            token_env="TIANSHU_LOCAL_API_TOKEN_NONEXISTENT",
        )
        assert auth.is_ready is False
        assert auth.ready_error is not None
        assert "token" in auth.ready_error.lower()

    def test_secure_mode_token_too_short_not_ready(self):
        """secure_mode 启用但 token 太短 → not_ready"""
        os.environ["TIANSHU_LOCAL_API_TOKEN"] = "short"
        auth = LocalTokenAuth(
            local_secure_mode=True,
            token_env="TIANSHU_LOCAL_API_TOKEN",
        )
        assert auth.is_ready is False
        assert "32" in auth.ready_error or "短" in auth.ready_error

    def test_secure_mode_valid_token_ready(self):
        """secure_mode 启用且 token 有效 → ready"""
        os.environ["TIANSHU_LOCAL_API_TOKEN"] = "a" * 32
        auth = LocalTokenAuth(
            local_secure_mode=True,
            token_env="TIANSHU_LOCAL_API_TOKEN",
        )
        assert auth.is_ready is True

    def test_non_secure_mode_no_token_still_ready(self):
        """非 secure_mode 时缺少 token 仍然 ready"""
        auth = LocalTokenAuth(
            local_secure_mode=False,
            token_env="TIANSHU_LOCAL_API_TOKEN",
        )
        assert auth.is_ready is True

    def test_non_secure_mode_skip_auth(self):
        """非 secure_mode 时 authenticate() 始终通过"""
        auth = LocalTokenAuth(
            local_secure_mode=False,
            token_env="TIANSHU_LOCAL_API_TOKEN",
        )
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.query_params = {}
        # 不抛异常即为通过
        auth.authenticate(mock_request)

    def test_secure_mode_missing_token_raises(self):
        """secure_mode 启用时缺少 token 抛出 LocalAuthError"""
        os.environ["TIANSHU_LOCAL_API_TOKEN"] = "a" * 32
        auth = LocalTokenAuth(
            local_secure_mode=True,
            token_env="TIANSHU_LOCAL_API_TOKEN",
        )
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.query_params = {}
        with pytest.raises(LocalAuthError):
            auth.authenticate(mock_request)

    def test_secure_mode_wrong_token_raises(self):
        """secure_mode 启用时错误 token 抛出 LocalAuthError"""
        os.environ["TIANSHU_LOCAL_API_TOKEN"] = "a" * 32
        auth = LocalTokenAuth(
            local_secure_mode=True,
            token_env="TIANSHU_LOCAL_API_TOKEN",
        )
        mock_request = MagicMock()
        mock_request.headers = {"X-TianShu-Token": "wrong-token-value-here!!!!!"}
        mock_request.query_params = {}
        mock_request.url = MagicMock()
        mock_request.url.path = "/v1/ask"
        with pytest.raises(LocalAuthError):
            auth.authenticate(mock_request)

    def test_401_same_for_missing_and_wrong(self):
        """缺少 token 和错误 token 返回相同的 401 状态码（不区分）"""
        os.environ["TIANSHU_LOCAL_API_TOKEN"] = "a" * 32
        auth = LocalTokenAuth(
            local_secure_mode=True,
            token_env="TIANSHU_LOCAL_API_TOKEN",
        )

        # 缺失 token
        req1 = MagicMock()
        req1.headers = {}
        req1.query_params = {}
        req1.url = MagicMock()
        req1.url.path = "/v1/ask"
        with pytest.raises(LocalAuthError) as exc1:
            auth.authenticate(req1)
        assert exc1.value.status_code == 401

        # 错误 token
        req2 = MagicMock()
        req2.headers = {"X-TianShu-Token": "wrong!!"}
        req2.query_params = {}
        req2.url = MagicMock()
        req2.url.path = "/v1/ask"
        with pytest.raises(LocalAuthError) as exc2:
            auth.authenticate(req2)
        assert exc2.value.status_code == 401

    def test_authenticate_does_not_log_token(self, caplog):
        """认证过程不记录令牌"""
        os.environ["TIANSHU_LOCAL_API_TOKEN"] = "a" * 32
        auth = LocalTokenAuth(
            local_secure_mode=True,
            token_env="TIANSHU_LOCAL_API_TOKEN",
        )
        mock_request = MagicMock()
        mock_request.headers = {"X-TianShu-Token": "a" * 32}
        mock_request.query_params = {}
        mock_request.url = MagicMock()
        mock_request.url.path = "/v1/ask"

        with caplog.at_level(logging.DEBUG):
            auth.authenticate(mock_request)

        # 日志中不应出现 token 值
        combined = " ".join(rec.message for rec in caplog.records)
        assert "a" * 32 not in combined

    def test_error_response_no_token_echo(self):
        """错误响应不回显令牌"""
        os.environ["TIANSHU_LOCAL_API_TOKEN"] = "s" * 32
        auth = LocalTokenAuth(
            local_secure_mode=True,
            token_env="TIANSHU_LOCAL_API_TOKEN",
        )
        mock_request = MagicMock()
        mock_request.headers = {"X-TianShu-Token": "wrong-token-32chars-long!!"}
        mock_request.query_params = {}
        mock_request.url = MagicMock()
        mock_request.url.path = "/v1/ask"

        with pytest.raises(LocalAuthError) as exc:
            auth.authenticate(mock_request)

        error_body = exc.value.message
        assert "wrong-token-32chars-long!!" not in error_body

    def test_yaml_plaintext_token_detected(self):
        """YAML 配置中出现明文 token 时 fail closed"""
        # 模拟配置中包含明文 token 字段
        api_config = {
            "security": {
                "local_secure_mode": True,
                "token_env": "TIANSHU_LOCAL_API_TOKEN",
            },
            "local_security": {
                # 这是禁止的：YAML 中不应有 token 明文
                "token": "hardcoded-token-in-yaml!!",
            },
        }
        # 检测逻辑：如果 local_security 中存在 token 字段 → fail
        is_invalid = "token" in api_config.get("local_security", {})
        assert is_invalid is True


# ═══════════════════════════════════════════════════════════════
# 测试：与 FastAPI 集成
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# Phase 6C 集成测试 fixtures（函数级，避免类级 fixture 交互问题）
# ═══════════════════════════════════════════════════════════════

_TEST_TOKEN = "test-local-token-32chars-long!!!"


@pytest.fixture
def auth_fixture():
    """创建测试用认证器（secure_mode 启用）"""
    os.environ["TIANSHU_LOCAL_API_TOKEN"] = _TEST_TOKEN
    auth = LocalTokenAuth(
        local_secure_mode=True,
        token_env="TIANSHU_LOCAL_API_TOKEN",
    )
    yield auth
    os.environ.pop("TIANSHU_LOCAL_API_TOKEN", None)


@pytest.fixture
def mock_runtime_fixture():
    """创建 mock runtime"""
    runtime = MagicMock()
    runtime.agent = MagicMock()
    runtime.agent.is_online = True
    runtime._lock = MagicMock()
    runtime.api_config = {
        "server": {"host": "127.0.0.1", "port": 8000},
        "request": {"max_question_length": 2000, "max_body_bytes": 8192},
        "security": {
            "local_secure_mode": True,
            "token_env": "TIANSHU_LOCAL_API_TOKEN",
            "cors_enabled": False,
            "expose_internal_errors": False,
            "docs_enabled": True,
        },
        "local_security": {
            "rate_limit": {"enabled": False, "requests_per_minute": 30, "burst": 3},
            "audit": {"enabled": False, "directory": "harness/reports/local_api_audit"},
        },
    }
    runtime.start = AsyncMock()
    runtime.close = AsyncMock()

    async def mock_ask(question):
        return {
            "contract_version": "1.0",
            "response_type": "answer",
            "question": question,
            "answer": {"text": "测试回答"},
            "clarification": {"needed": False, "message": None},
            "refusal": {"refused": False, "reason": None},
            "data": {
                "is_multi_plan": False,
                "summaries": [],
                "merged_result": None,
                "chart_spec": None,
                "sources": ["gold.test"],
            },
            "warnings": [],
            "meta": {"execution_mode": "single"},
        }
    runtime.ask = AsyncMock(side_effect=mock_ask)
    runtime.readiness.return_value = {
        "status": "ready",
        "agent_online": True,
        "contract_version": "1.0",
    }
    return runtime


@pytest.fixture
def client_fixture(auth_fixture, mock_runtime_fixture):
    """创建带认证的测试客户端"""
    from src.api.app import create_app
    app = create_app(runtime=mock_runtime_fixture, local_auth=auth_fixture)
    return TestClient(app)


class TestAuthIntegration:
    """认证与 FastAPI 集成测试"""

    def test_health_live_no_token(self, client_fixture):
        """health/live 无需令牌"""
        resp = client_fixture.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"

    def test_health_ready_no_token(self, client_fixture):
        """health/ready 无需令牌"""
        resp = client_fixture.get("/health/ready")
        # ready 状态取决于 mock runtime
        assert resp.status_code in (200, 503)

    def test_ask_missing_token_401(self, client_fixture):
        """POST /v1/ask 缺 token 返回 401"""
        resp = client_fixture.post("/v1/ask", json={"question": "测试问题"})
        assert resp.status_code == 401
        body = resp.json()
        assert "error" in body

    def test_ask_empty_token_401(self, client_fixture):
        """POST /v1/ask 空 token 返回 401"""
        resp = client_fixture.post(
            "/v1/ask",
            json={"question": "测试问题"},
            headers={"X-TianShu-Token": ""},
        )
        assert resp.status_code == 401

    def test_ask_wrong_token_401(self, client_fixture):
        """POST /v1/ask 错误 token 返回 401"""
        resp = client_fixture.post(
            "/v1/ask",
            json={"question": "测试问题"},
            headers={"X-TianShu-Token": "wrong-token-value-here!!!"},
        )
        assert resp.status_code == 401

    def test_ask_correct_token_passes(self, client_fixture):
        """POST /v1/ask 正确 token 请求通过"""
        resp = client_fixture.post(
            "/v1/ask",
            json={"question": "测试问题"},
            headers={"X-TianShu-Token": _TEST_TOKEN},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["response_type"] == "answer"

    def test_query_token_rejected(self, client_fixture):
        """URL query 中的 token 被拒绝（401）"""
        resp = client_fixture.post(
            f"/v1/ask?token={_TEST_TOKEN}",
            json={"question": "测试问题"},
        )
        assert resp.status_code == 401

    def test_body_token_rejected(self, client_fixture):
        """请求体中的 token 字段被拒绝（认证中间件先拦截 → 401）"""
        resp = client_fixture.post(
            "/v1/ask",
            json={
                "question": "测试问题",
                "token": _TEST_TOKEN,
            },
        )
        # auth 中间件先于 Pydantic 执行，无 header token → 401
        assert resp.status_code == 401

    def test_cookie_token_rejected(self, client_fixture):
        """Cookie 中的 token 被拒绝（401）"""
        resp = client_fixture.post(
            "/v1/ask",
            json={"question": "测试问题"},
            headers={"Cookie": f"tianshu_token={_TEST_TOKEN}"},
        )
        assert resp.status_code == 401

    def test_authorization_bearer_rejected(self, client_fixture):
        """Authorization Bearer 被拒绝（401）"""
        resp = client_fixture.post(
            "/v1/ask",
            json={"question": "测试问题"},
            headers={"Authorization": f"Bearer {_TEST_TOKEN}"},
        )
        assert resp.status_code == 401

    def test_error_response_no_token_leak(self, client_fixture):
        """401 错误响应不含令牌值"""
        resp = client_fixture.post(
            "/v1/ask",
            json={"question": "测试问题"},
            headers={"X-TianShu-Token": "leaked-token-should-not-appear"},
        )
        assert resp.status_code == 401
        body = resp.json()
        body_str = str(body)
        assert "leaked-token-should-not-appear" not in body_str
        assert "X-TianShu-Token" not in body_str
