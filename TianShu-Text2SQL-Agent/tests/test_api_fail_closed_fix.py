"""Phase 6C —— API 认证 fail-open 修复测试。

覆盖（先写失败测试，再修改实现）：
    1. API 配置文件不存在 → secure mode 仍为 True，/v1/ask 不执行 Agent
    2. YAML 无法解析 → 使用安全默认配置，认证和限流保持启用
    3. security 段缺失 → local_secure_mode=True, cors_enabled=False
    4. local_secure_mode 字段类型非法 → fail closed
    5. token 环境变量缺失/不足 32 字符 → /health/ready 503, /v1/ask 被拒
    6. 正确 token → 请求正常进入 Agent
    7. 错误/Bearer/Cookie/query/body token → 全部拒绝
    8. 配置显式 local_secure_mode=false → 强制恢复 True
    9. 认证失败 → 不消耗限流额度、不记录 token、不调用 Agent
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════
# 测试组 1: 配置缺失/非法时的 fail-closed 行为
# ═══════════════════════════════════════════════════════════════


class TestConfigMissingFailClosed:
    """API 配置文件不存在或无法解析时，必须 fail-closed（启用安全模式）"""

    def test_default_config_secure_mode_is_true(self):
        """_DEFAULT_API_CONFIG 的 local_secure_mode 必须为 True"""
        from src.api.runtime import _DEFAULT_API_CONFIG
        assert _DEFAULT_API_CONFIG["security"]["local_secure_mode"] is True, (
            "默认配置的 local_secure_mode 必须为 True（fail-closed）"
        )

    def test_default_config_rate_limit_enabled(self):
        """_DEFAULT_API_CONFIG 的 rate_limit.enabled 必须为 True"""
        from src.api.runtime import _DEFAULT_API_CONFIG
        assert _DEFAULT_API_CONFIG["local_security"]["rate_limit"]["enabled"] is True, (
            "默认配置的限流必须启用（fail-closed）"
        )

    def test_config_missing_uses_secure_defaults(self):
        """配置文件不存在时，使用安全默认值（secure_mode=True）"""
        from src.api.runtime import AgentRuntime

        runtime = AgentRuntime(api_config_path="nonexistent_config_file.yml")
        runtime._load_api_config()

        assert runtime.api_config["security"]["local_secure_mode"] is True, (
            "配置文件缺失时应默认 local_secure_mode=True"
        )
        assert runtime.api_config["security"]["cors_enabled"] is False
        assert runtime.api_config["server"]["host"] == "127.0.0.1"

    def test_broken_yaml_uses_secure_defaults(self):
        """YAML 解析失败时，使用安全默认值"""
        from src.api.runtime import AgentRuntime
        import os

        # 创建非法 YAML 文件
        fd, path = tempfile.mkstemp(suffix=".yml")
        with os.fdopen(fd, "w") as f:
            f.write("server: [unclosed\n  host: broken: yaml: [\n")

        try:
            runtime = AgentRuntime(api_config_path=path)
            runtime._load_api_config()

            assert runtime.api_config["security"]["local_secure_mode"] is True, (
                "YAML 解析失败时应默认 local_secure_mode=True"
            )
            assert runtime.api_config["security"]["cors_enabled"] is False
        finally:
            os.unlink(path)

    def test_security_section_missing_uses_secure_defaults(self):
        """security 段缺失时，默认启用安全模式"""
        from src.api.runtime import AgentRuntime
        import os
        import yaml

        # 创建缺少 security 段的配置
        config_data = {
            "server": {"host": "127.0.0.1", "port": 8000},
            "runtime": {"max_concurrent_agent_requests": 1},
            "request": {"max_question_length": 2000},
            # 故意缺少 security 段
        }

        fd, path = tempfile.mkstemp(suffix=".yml")
        with os.fdopen(fd, "w") as f:
            yaml.dump(config_data, f)

        try:
            runtime = AgentRuntime(api_config_path=path)
            runtime._load_api_config()

            assert runtime.api_config["security"]["local_secure_mode"] is True, (
                "security 段缺失时应默认 local_secure_mode=True"
            )
            assert runtime.api_config["security"]["cors_enabled"] is False
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════
# 测试组 2: local_secure_mode 字段类型校验
# ═══════════════════════════════════════════════════════════════


class TestSecureModeTypeCheck:
    """local_secure_mode 字段必须为 bool 类型，不允许 Python truthy/falsy 隐式转换"""

    def test_secure_mode_string_rejected(self):
        """local_secure_mode 为字符串 "false" 时不得被当作 False（Python truthy 陷阱）"""
        from src.api.local_auth import parse_local_security_config

        api_config = {
            "security": {"local_secure_mode": "false"},  # 字符串，Python 认为是 truthy
        }
        cfg = parse_local_security_config(api_config)
        # 字符串类型非法 → 应强制为 True（fail-closed）
        assert cfg["local_secure_mode"] is True, (
            "local_secure_mode 为字符串时应强制为 True"
        )

    def test_secure_mode_int_zero_rejected(self):
        """local_secure_mode 为 0 时不得被当作 False"""
        from src.api.local_auth import parse_local_security_config

        api_config = {
            "security": {"local_secure_mode": 0},  # 整数 0，Python 认为是 falsy
        }
        cfg = parse_local_security_config(api_config)
        assert cfg["local_secure_mode"] is True, (
            "local_secure_mode 为 0 时应强制为 True"
        )

    def test_secure_mode_int_one_accepted(self):
        """local_secure_mode 为 1 时依然非法（非 bool），应强制为 True"""
        from src.api.local_auth import parse_local_security_config

        api_config = {
            "security": {"local_secure_mode": 1},
        }
        cfg = parse_local_security_config(api_config)
        # 1 不是 bool 类型，应强制为 True
        assert cfg["local_secure_mode"] is True

    def test_secure_mode_none_rejected(self):
        """local_secure_mode 为 None 时不得被当作 False"""
        from src.api.local_auth import parse_local_security_config

        api_config = {
            "security": {"local_secure_mode": None},
        }
        cfg = parse_local_security_config(api_config)
        assert cfg["local_secure_mode"] is True, (
            "local_secure_mode 为 None 时应强制为 True"
        )

    def test_secure_mode_true_bool_accepted(self):
        """local_secure_mode=True（布尔类型）应接受"""
        from src.api.local_auth import parse_local_security_config

        api_config = {
            "security": {"local_secure_mode": True},
        }
        cfg = parse_local_security_config(api_config)
        assert cfg["local_secure_mode"] is True


# ═══════════════════════════════════════════════════════════════
# 测试组 3: 配置显式 local_secure_mode=false 被拒绝
# ═══════════════════════════════════════════════════════════════


class TestExplicitSecureModeFalseRejected:
    """配置显式写入 local_secure_mode=false 时，必须强制恢复 True"""

    def test_explicit_false_in_parse_config(self):
        """parse_local_security_config 收到 False 时必须强制 True"""
        from src.api.local_auth import parse_local_security_config

        api_config = {
            "security": {"local_secure_mode": False},
        }
        cfg = parse_local_security_config(api_config)
        # 显式写入 False 也应被强制为 True（安全闭环不允许关闭认证）
        assert cfg["local_secure_mode"] is True, (
            "显式 local_secure_mode=false 必须被强制为 True"
        )

    def test_explicit_false_in_runtime_load(self):
        """_load_api_config 收到 local_secure_mode=false 时必须强制 True"""
        from src.api.runtime import AgentRuntime
        import os
        import yaml

        config_data = {
            "server": {"host": "127.0.0.1", "port": 8000},
            "runtime": {"max_concurrent_agent_requests": 1},
            "request": {"max_question_length": 2000},
            "security": {
                "local_secure_mode": False,  # 显式关闭
                "token_env": "TIANSHU_LOCAL_API_TOKEN",
                "cors_enabled": False,
                "expose_internal_errors": False,
            },
            "local_security": {
                "rate_limit": {"enabled": True, "requests_per_minute": 30},
                "audit": {"enabled": True, "directory": "test_audit"},
            },
        }

        fd, path = tempfile.mkstemp(suffix=".yml")
        with os.fdopen(fd, "w") as f:
            yaml.dump(config_data, f)

        try:
            runtime = AgentRuntime(api_config_path=path)
            runtime._load_api_config()

            assert runtime.api_config["security"]["local_secure_mode"] is True, (
                "显式 local_secure_mode=false 必须被强制为 True"
            )
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════
# 测试组 4: Token 环境变量缺失时的 readiness 与拒绝行为
# ═══════════════════════════════════════════════════════════════


class TestTokenMissingBehavior:
    """token 环境变量缺失时，/health/ready 返回 503，/v1/ask 被拒绝"""

    def test_auth_not_ready_no_token_env(self):
        """token 环境变量缺失时认证器 not_ready"""
        # 确保环境变量不存在
        os.environ.pop("TIANSHU_LOCAL_API_TOKEN_NONEXISTENT", None)

        from src.api.local_auth import LocalTokenAuth

        auth = LocalTokenAuth(
            local_secure_mode=True,
            token_env="TIANSHU_LOCAL_API_TOKEN_NONEXISTENT",
        )
        assert auth.is_ready is False
        assert auth.ready_error is not None

    def test_auth_not_ready_short_token(self):
        """token 长度不足 32 时认证器 not_ready"""
        os.environ["TIANSHU_LOCAL_API_TOKEN_SHORT"] = "tooshort"
        try:
            from src.api.local_auth import LocalTokenAuth

            auth = LocalTokenAuth(
                local_secure_mode=True,
                token_env="TIANSHU_LOCAL_API_TOKEN_SHORT",
            )
            assert auth.is_ready is False
            assert auth.ready_error is not None
        finally:
            os.environ.pop("TIANSHU_LOCAL_API_TOKEN_SHORT", None)

    def test_health_ready_503_when_token_missing(self):
        """token 缺失时 /health/ready 返回 503"""
        os.environ.pop("TIANSHU_LOCAL_API_TOKEN_MISSING", None)

        from fastapi.testclient import TestClient
        from src.api.app import create_app
        from src.api.local_auth import LocalTokenAuth

        auth = LocalTokenAuth(
            local_secure_mode=True,
            token_env="TIANSHU_LOCAL_API_TOKEN_MISSING",
        )

        mock_rt = MagicMock()
        mock_rt.agent = MagicMock()
        mock_rt.agent.is_online = True
        mock_rt.api_config = {
            "server": {"host": "127.0.0.1", "port": 8000},
            "security": {"local_secure_mode": True, "cors_enabled": False},
            "local_security": {
                "rate_limit": {"enabled": False},
                "audit": {"enabled": False},
            },
        }
        mock_rt.start = AsyncMock()
        mock_rt.close = AsyncMock()
        mock_rt.readiness.return_value = {
            "status": "ready", "agent_online": True, "contract_version": "1.0",
        }

        app = create_app(runtime=mock_rt, local_auth=auth)
        with TestClient(app) as client:
            resp = client.get("/health/ready")
            # Agent online but auth not ready → 503
            assert resp.status_code == 503, (
                f"token 缺失时 /health/ready 应返回 503，实际 {resp.status_code}"
            )
            data = resp.json()
            assert data["auth_ready"] is False

    def test_v1_ask_401_when_token_missing(self):
        """token 缺失时 POST /v1/ask 返回 401"""
        os.environ.pop("TIANSHU_LOCAL_API_TOKEN_MISSING", None)

        from fastapi.testclient import TestClient
        from src.api.app import create_app
        from src.api.local_auth import LocalTokenAuth

        auth = LocalTokenAuth(
            local_secure_mode=True,
            token_env="TIANSHU_LOCAL_API_TOKEN_MISSING",
        )

        mock_rt = MagicMock()
        mock_rt.agent = MagicMock()
        mock_rt.agent.is_online = True
        mock_rt.api_config = {
            "server": {"host": "127.0.0.1", "port": 8000},
            "security": {"local_secure_mode": True, "cors_enabled": False},
            "local_security": {
                "rate_limit": {"enabled": False},
                "audit": {"enabled": False},
            },
        }
        mock_rt.start = AsyncMock()
        mock_rt.close = AsyncMock()
        mock_rt.readiness.return_value = {
            "status": "ready", "agent_online": True, "contract_version": "1.0",
        }

        app = create_app(runtime=mock_rt, local_auth=auth)
        with TestClient(app) as client:
            resp = client.post("/v1/ask", json={"question": "测试"})
            # 即使有正确 token header，认证器自身不可用 → 拒绝
            assert resp.status_code in (401, 503), (
                f"token 缺失时 /v1/ask 应被拒绝，实际 {resp.status_code}"
            )


# ═══════════════════════════════════════════════════════════════
# 测试组 5: 认证失败不消耗限流额度、不调用 Agent
# ═══════════════════════════════════════════════════════════════


class TestAuthFailureSideEffects:
    """认证失败时不得消耗限流额度、记录 token、调用 Agent"""

    def test_auth_failure_before_rate_limit(self):
        """认证失败应在限流检查之前发生（中间件顺序）"""
        from fastapi.testclient import TestClient
        from src.api.app import create_app
        from src.api.local_auth import LocalTokenAuth

        os.environ["TIANSHU_LOCAL_API_TOKEN"] = "a" * 32
        auth = LocalTokenAuth(local_secure_mode=True)

        mock_rt = MagicMock()
        mock_rt.agent = MagicMock()
        mock_rt.agent.is_online = True
        mock_rt.api_config = {
            "server": {"host": "127.0.0.1", "port": 8000},
            "security": {"local_secure_mode": True, "cors_enabled": False},
            "local_security": {
                "rate_limit": {"enabled": True, "requests_per_minute": 1, "burst": 0},
                "audit": {"enabled": False},
            },
        }
        mock_rt.start = AsyncMock()
        mock_rt.close = AsyncMock()
        mock_rt.readiness.return_value = {
            "status": "ready", "agent_online": True, "contract_version": "1.0",
        }
        mock_rt.ask = AsyncMock(return_value={
            "contract_version": "1.0", "response_type": "answer",
            "question": "test", "answer": {"text": "ok"},
            "clarification": {"needed": False, "message": None},
            "refusal": {"refused": False, "reason": None},
            "data": {"is_multi_plan": False, "summaries": [], "merged_result": None, "chart_spec": None, "sources": []},
            "warnings": [], "meta": {"execution_mode": "single"},
        })

        from src.api.local_rate_limit import create_rate_limiter
        rl = create_rate_limiter(enabled=True, requests_per_minute=1, burst=0)

        app = create_app(runtime=mock_rt, local_auth=auth, rate_limiter=rl)
        with TestClient(app) as client:
            # 先发几次认证失败的请求
            for _ in range(5):
                resp = client.post(
                    "/v1/ask",
                    json={"question": "test"},
                    headers={"X-TianShu-Token": "wrong"},
                )
                assert resp.status_code == 401

            # 认证成功的请求不应因前面失败请求被限流
            resp = client.post(
                "/v1/ask",
                json={"question": "test"},
                headers={"X-TianShu-Token": "a" * 32},
            )
            # 应为 200（成功通过认证和限流），而非 429
            assert resp.status_code == 200, (
                f"认证失败不应消耗限流额度，期望 200，实际 {resp.status_code}"
            )

    def test_auth_failure_does_not_call_agent(self):
        """认证失败时不得调用 Agent"""
        from fastapi.testclient import TestClient
        from src.api.app import create_app
        from src.api.local_auth import LocalTokenAuth

        os.environ["TIANSHU_LOCAL_API_TOKEN"] = "a" * 32
        auth = LocalTokenAuth(local_secure_mode=True)

        mock_rt = MagicMock()
        mock_rt.agent = MagicMock()
        mock_rt.agent.is_online = True
        mock_rt.api_config = {
            "server": {"host": "127.0.0.1", "port": 8000},
            "security": {"local_secure_mode": True, "cors_enabled": False},
            "local_security": {
                "rate_limit": {"enabled": False},
                "audit": {"enabled": False},
            },
        }
        mock_rt.start = AsyncMock()
        mock_rt.close = AsyncMock()
        mock_rt.readiness.return_value = {
            "status": "ready", "agent_online": True, "contract_version": "1.0",
        }
        mock_rt.ask = AsyncMock(return_value={
            "contract_version": "1.0", "response_type": "answer",
            "question": "test", "answer": {"text": "ok"},
            "clarification": {"needed": False, "message": None},
            "refusal": {"refused": False, "reason": None},
            "data": {"is_multi_plan": False, "summaries": [], "merged_result": None, "chart_spec": None, "sources": []},
            "warnings": [], "meta": {"execution_mode": "single"},
        })

        app = create_app(runtime=mock_rt, local_auth=auth)
        with TestClient(app) as client:
            # 认证失败的请求
            resp = client.post(
                "/v1/ask",
                json={"question": "test"},
                headers={"X-TianShu-Token": "wrong"},
            )
            assert resp.status_code == 401

            # mock_rt.ask 不应被调用
            mock_rt.ask.assert_not_called()


# ═══════════════════════════════════════════════════════════════
# 测试组 6: 各种 token 来源拒绝
# ═══════════════════════════════════════════════════════════════


class TestAllTokenSourcesRejected:
    """只接受 X-TianShu-Token header，其他来源全部拒绝"""

    _TEST_TOKEN = "a" * 32

    @pytest.fixture(autouse=True)
    def setup_token(self):
        os.environ["TIANSHU_LOCAL_API_TOKEN"] = self._TEST_TOKEN
        yield
        os.environ.pop("TIANSHU_LOCAL_API_TOKEN", None)

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.app import create_app
        from src.api.local_auth import LocalTokenAuth

        auth = LocalTokenAuth(local_secure_mode=True)

        mock_rt = MagicMock()
        mock_rt.agent = MagicMock()
        mock_rt.agent.is_online = True
        mock_rt.api_config = {
            "server": {"host": "127.0.0.1", "port": 8000},
            "security": {"local_secure_mode": True, "cors_enabled": False},
            "local_security": {
                "rate_limit": {"enabled": False},
                "audit": {"enabled": False},
            },
        }
        mock_rt.start = AsyncMock()
        mock_rt.close = AsyncMock()
        mock_rt.readiness.return_value = {
            "status": "ready", "agent_online": True, "contract_version": "1.0",
        }
        mock_rt.ask = AsyncMock(return_value={
            "contract_version": "1.0", "response_type": "answer",
            "question": "test", "answer": {"text": "ok"},
            "clarification": {"needed": False, "message": None},
            "refusal": {"refused": False, "reason": None},
            "data": {"is_multi_plan": False, "summaries": [], "merged_result": None, "chart_spec": None, "sources": []},
            "warnings": [], "meta": {"execution_mode": "single"},
        })

        app = create_app(runtime=mock_rt, local_auth=auth)
        with TestClient(app) as c:
            yield c

    def test_bearer_token_rejected(self, client):
        """Authorization Bearer 被拒绝"""
        resp = client.post(
            "/v1/ask",
            json={"question": "test"},
            headers={"Authorization": f"Bearer {self._TEST_TOKEN}"},
        )
        assert resp.status_code == 401

    def test_cookie_token_rejected(self, client):
        """Cookie 中的 token 被拒绝"""
        resp = client.post(
            "/v1/ask",
            json={"question": "test"},
            headers={"Cookie": f"tianshu_token={self._TEST_TOKEN}"},
        )
        assert resp.status_code == 401

    def test_query_token_rejected(self, client):
        """URL query 中的 token 被拒绝"""
        resp = client.post(
            f"/v1/ask?token={self._TEST_TOKEN}",
            json={"question": "test"},
        )
        assert resp.status_code == 401

    def test_body_token_rejected(self, client):
        """请求体中的 token 字段被拒绝"""
        resp = client.post(
            "/v1/ask",
            json={"question": "test", "token": self._TEST_TOKEN},
        )
        assert resp.status_code == 401

    def test_correct_header_accepted(self, client):
        """正确的 X-TianShu-Token 被接受"""
        resp = client.post(
            "/v1/ask",
            json={"question": "test"},
            headers={"X-TianShu-Token": self._TEST_TOKEN},
        )
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════
# 测试组 7: AuthError 日志不含 token
# ═══════════════════════════════════════════════════════════════


class TestAuthErrorNoTokenLeak:
    """认证失败时日志和响应不含 token"""

    def test_401_error_no_token_in_body(self):
        """401 响应中不含请求中提供的 token"""
        from fastapi.testclient import TestClient
        from src.api.app import create_app
        from src.api.local_auth import LocalTokenAuth

        os.environ["TIANSHU_LOCAL_API_TOKEN"] = "s" * 32
        auth = LocalTokenAuth(local_secure_mode=True)

        mock_rt = MagicMock()
        mock_rt.agent = MagicMock()
        mock_rt.agent.is_online = True
        mock_rt.api_config = {
            "server": {"host": "127.0.0.1", "port": 8000},
            "security": {"local_secure_mode": True, "cors_enabled": False},
            "local_security": {
                "rate_limit": {"enabled": False},
                "audit": {"enabled": False},
            },
        }
        mock_rt.start = AsyncMock()
        mock_rt.close = AsyncMock()
        mock_rt.readiness.return_value = {
            "status": "ready", "agent_online": True, "contract_version": "1.0",
        }

        app = create_app(runtime=mock_rt, local_auth=auth)
        with TestClient(app) as client:
            resp = client.post(
                "/v1/ask",
                json={"question": "test"},
                headers={"X-TianShu-Token": "leaked-token-value-32-chars!!"},
            )
            assert resp.status_code == 401
            body = resp.json()
            body_str = str(body)
            assert "leaked-token-value-32-chars!!" not in body_str


# ═══════════════════════════════════════════════════════════════
# 测试组 8: 正确 token 下完整链路可用
# ═══════════════════════════════════════════════════════════════


class TestCorrectTokenFullPath:
    """正确 token 下完整链路可用"""

    def test_correct_token_agent_called(self):
        """正确 token 下 Agent 被正常调用"""
        from fastapi.testclient import TestClient
        from src.api.app import create_app
        from src.api.local_auth import LocalTokenAuth

        os.environ["TIANSHU_LOCAL_API_TOKEN"] = "c" * 32
        auth = LocalTokenAuth(local_secure_mode=True)

        mock_rt = MagicMock()
        mock_rt.agent = MagicMock()
        mock_rt.agent.is_online = True
        mock_rt.api_config = {
            "server": {"host": "127.0.0.1", "port": 8000},
            "security": {"local_secure_mode": True, "cors_enabled": False},
            "local_security": {
                "rate_limit": {"enabled": False},
                "audit": {"enabled": False},
            },
        }
        mock_rt.start = AsyncMock()
        mock_rt.close = AsyncMock()
        mock_rt.readiness.return_value = {
            "status": "ready", "agent_online": True, "contract_version": "1.0",
        }
        mock_rt.ask = AsyncMock(return_value={
            "contract_version": "1.0", "response_type": "answer",
            "question": "test", "answer": {"text": "成功回答"},
            "clarification": {"needed": False, "message": None},
            "refusal": {"refused": False, "reason": None},
            "data": {"is_multi_plan": False, "summaries": [], "merged_result": None, "chart_spec": None, "sources": []},
            "warnings": [], "meta": {"execution_mode": "single"},
        })

        app = create_app(runtime=mock_rt, local_auth=auth)
        with TestClient(app) as client:
            resp = client.post(
                "/v1/ask",
                json={"question": "测试问题"},
                headers={"X-TianShu-Token": "c" * 32},
            )
            assert resp.status_code == 200
            mock_rt.ask.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# 测试组 9: LocalTokenAuth 默认值变更
# ═══════════════════════════════════════════════════════════════


class TestLocalTokenAuthDefaults:
    """LocalTokenAuth 默认应为 secure_mode=True"""

    def test_default_is_secure_mode(self):
        """LocalTokenAuth 默认参数应为 secure_mode=True"""
        from src.api.local_auth import LocalTokenAuth

        auth = LocalTokenAuth()
        assert auth.secure_mode is True, (
            "LocalTokenAuth 默认应为 secure_mode=True（fail-closed）"
        )

    def test_parse_config_default_is_true(self):
        """parse_local_security_config 空配置默认 secure_mode=True"""
        from src.api.local_auth import parse_local_security_config

        cfg = parse_local_security_config({})
        assert cfg["local_secure_mode"] is True, (
            "parse_local_security_config 默认值应为 True"
        )

    def test_parse_config_default_rate_limit_enabled(self):
        """parse_local_security_config 空配置默认 rate_limit_enabled=True"""
        from src.api.local_auth import parse_local_security_config

        cfg = parse_local_security_config({})
        assert cfg["rate_limit_enabled"] is True, (
            "parse_local_security_config 默认 rate_limit 应启用"
        )


# ═══════════════════════════════════════════════════════════════
# 测试组 10: create_app 默认值
# ═══════════════════════════════════════════════════════════════


class TestCreateAppDefaults:
    """create_app 不传参数时应使用 fail-closed 默认值"""

    def test_create_app_no_auth_uses_secure_mode(self):
        """不传 local_auth 时 create_app 创建的认证器应为 secure_mode"""
        from src.api.app import create_app
        from unittest.mock import MagicMock, AsyncMock

        mock_rt = MagicMock()
        mock_rt.agent = MagicMock()
        mock_rt.agent.is_online = True
        mock_rt.api_config = {}
        mock_rt.start = AsyncMock()
        mock_rt.close = AsyncMock()
        mock_rt.readiness.return_value = {
            "status": "ready", "agent_online": True, "contract_version": "1.0",
        }
        mock_rt.ask = AsyncMock(return_value={
            "contract_version": "1.0", "response_type": "answer",
            "question": "test", "answer": {"text": "ok"},
            "clarification": {"needed": False, "message": None},
            "refusal": {"refused": False, "reason": None},
            "data": {"is_multi_plan": False, "summaries": [], "merged_result": None, "chart_spec": None, "sources": []},
            "warnings": [], "meta": {"execution_mode": "single"},
        })

        app = create_app(runtime=mock_rt)  # 不传 local_auth
        auth = app.state.local_auth
        assert auth.secure_mode is True, (
            "create_app 默认认证器应为 secure_mode=True"
        )
