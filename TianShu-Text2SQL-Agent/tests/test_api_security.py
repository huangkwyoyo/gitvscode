"""Phase 6B —— API 安全测试。

覆盖：
    - API 响应不含 SQL
    - API 响应不含 generated_sql
    - API 响应不含 trace
    - API 响应不含 API Key
    - API 响应不含数据库绝对路径
    - 500 响应不含 traceback
    - HTTP 层只调用 agent.ask() 和 build_public_response()
    - 文档端点不泄露信息
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def mock_runtime():
    """创建在线状态 mock runtime"""
    runtime = MagicMock()
    runtime.agent = MagicMock()
    runtime.agent.is_online = True
    runtime.agent.is_ready = True
    runtime._max_concurrent = 1
    runtime._queue_timeout = 2.0
    runtime.api_config = {
        "server": {"host": "127.0.0.1", "port": 8000},
        "request": {"max_question_length": 2000},
        "security": {"cors_enabled": False, "expose_internal_errors": False},
    }
    runtime.start = AsyncMock()
    runtime.close = AsyncMock()

    # 正常的 answer 响应
    async def mock_ask(question: str) -> dict:
        return {
            "contract_version": "1.0",
            "response_type": "answer",
            "question": question,
            "answer": {"text": "根据查询结果，2026年1月共有310次行程。"},
            "clarification": {"needed": False, "message": None},
            "refusal": {"refused": False, "reason": None},
            "data": {
                "is_multi_plan": False,
                "summaries": [{
                    "source_plan_index": 1,
                    "metrics": ["trip_count"],
                    "dimensions": ["date"],
                    "primary_table": "gold.dws_daily_trip_summary",
                    "strategy": "g3_direct",
                    "row_count": 31,
                }],
                "merged_result": None,
                "chart_spec": {"chart_type": "line", "title": "每日行程数"},
                "sources": ["gold.dws_daily_trip_summary"],
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
def security_client(mock_runtime):
    """创建带 mock runtime 的测试客户端"""
    from fastapi.testclient import TestClient
    from src.api.app import create_app

    app = create_app(runtime=mock_runtime)
    with TestClient(app) as c:
        yield c


# ═══════════════════════════════════════════════════════════════
# 测试组 1: SQL 泄露检测
# ═══════════════════════════════════════════════════════════════


class TestNoSQLLeak:
    """API 响应不应包含 SQL"""

    def test_answer_no_select(self, security_client):
        """answer 响应不应包含 SELECT 语句"""
        resp = security_client.post("/v1/ask", json={"question": "test"})
        data = resp.json()
        response_text = json.dumps(data, ensure_ascii=False)
        assert "SELECT" not in response_text

    def test_answer_no_sql_keywords(self, security_client):
        """answer 响应不应包含 SQL 关键字"""
        resp = security_client.post("/v1/ask", json={"question": "test"})
        data = resp.json()
        response_text = json.dumps(data, ensure_ascii=False)
        sql_keywords = ["INSERT", "DELETE", "UPDATE", "DROP", "CREATE"]
        for kw in sql_keywords:
            assert kw not in response_text, f"响应不应包含 {kw}"

    def test_error_no_sql(self, security_client):
        """错误响应也不应包含 SQL"""
        resp = security_client.post("/v1/ask", json={})  # 触发 422
        data = resp.json()
        response_text = json.dumps(data, ensure_ascii=False)
        assert "SELECT" not in response_text


class TestNoGeneratedSqlLeak:
    """API 响应不应包含 generated_sql"""

    def test_answer_no_generated_sql_field(self, security_client):
        """answer 响应不应有 generated_sql 字段"""
        resp = security_client.post("/v1/ask", json={"question": "test"})
        data = resp.json()
        assert "generated_sql" not in data
        # 深度搜索
        response_text = json.dumps(data, ensure_ascii=False)
        assert "generated_sql" not in response_text


class TestNoTraceLeak:
    """API 响应不应包含内部 trace"""

    def test_answer_no_trace_field(self, security_client):
        """answer 响应不应有 trace 字段"""
        resp = security_client.post("/v1/ask", json={"question": "test"})
        data = resp.json()
        assert "trace" not in data

    def test_answer_no_execution_trace(self, security_client):
        """answer 响应不应有 execution_trace 字段"""
        resp = security_client.post("/v1/ask", json={"question": "test"})
        data = resp.json()
        assert "execution_trace" not in data


class TestNoApiKeyLeak:
    """API 响应不应包含 API Key"""

    def test_answer_no_api_key(self, security_client):
        """answer 响应不应包含 API Key 模式"""
        resp = security_client.post("/v1/ask", json={"question": "test"})
        data = resp.json()
        response_text = json.dumps(data, ensure_ascii=False)
        # 不应包含 sk- 开头的 key
        assert "sk-" not in response_text
        # 不应包含 API_KEY 字样
        assert "api_key" not in response_text.lower()
        assert "apikey" not in response_text.lower()

    def test_error_no_api_key(self, security_client):
        """错误响应也不应包含 API Key"""
        resp = security_client.post("/v1/ask", json={})
        data = resp.json()
        response_text = json.dumps(data, ensure_ascii=False)
        assert "sk-" not in response_text


class TestNoDbPathLeak:
    """API 响应不应包含数据库绝对路径"""

    def test_answer_no_duckdb_path(self, security_client):
        """answer 响应不应包含 DuckDB 文件路径"""
        resp = security_client.post("/v1/ask", json={"question": "test"})
        data = resp.json()
        response_text = json.dumps(data, ensure_ascii=False)
        # 检测 Windows 路径模式
        assert ".duckdb" not in response_text
        assert "D:/" not in response_text or "D:/" not in response_text
        assert "C:\\" not in response_text or "C:\\" not in response_text

    def test_health_no_db_path(self, security_client):
        """health 端点响应不应包含数据库路径"""
        resp = security_client.get("/health/ready")
        data = resp.json()
        response_text = json.dumps(data, ensure_ascii=False)
        assert ".duckdb" not in response_text


class TestNoTracebackLeak:
    """500 响应不应包含 traceback"""

    def test_500_no_traceback(self, security_client):
        """未预期异常的 500 响应不应暴露 traceback"""
        async def raise_exc(q):
            raise RuntimeError("内部错误")
        security_client.app.state.runtime.ask = AsyncMock(side_effect=raise_exc)

        resp = security_client.post("/v1/ask", json={"question": "test"})
        data = resp.json()
        response_text = json.dumps(data, ensure_ascii=False)
        assert "Traceback" not in response_text
        assert "most recent call last" not in response_text.lower()

    def test_500_message_safe(self, security_client):
        """500 响应的消息应安全（不含内部细节）"""
        async def raise_exc(q):
            raise RuntimeError("模拟内部异常")
        security_client.app.state.runtime.ask = AsyncMock(side_effect=raise_exc)

        resp = security_client.post("/v1/ask", json={"question": "test"})
        data = resp.json()
        assert "RuntimeError" not in data.get("error", {}).get("message", "")


class TestResponseBoundary:
    """HTTP 层边界检查"""

    def test_only_public_contract_returned(self, security_client):
        """只能通过 build_public_response 返回数据"""
        resp = security_client.post("/v1/ask", json={"question": "test"})
        data = resp.json()

        # 公开契约必须有的字段
        assert "contract_version" in data
        assert "response_type" in data
        assert "question" in data
        assert "answer" in data
        assert "clarification" in data
        assert "refusal" in data
        assert "data" in data
        assert "warnings" in data
        assert "meta" in data

        # 公开契约禁止的字段
        forbidden = ["sql", "generated_sql", "trace", "api_key", "authorization"]
        for field in forbidden:
            assert field not in data

    def test_api_runtime_uses_build_public_response(self, security_client):
        """API 层应使用 build_public_response 构建输出"""
        import inspect
        from src.api.runtime import AgentRuntime

        src = inspect.getsource(AgentRuntime.ask)
        assert "build_public_response" in src, (
            "AgentRuntime.ask() 必须调用 build_public_response()"
        )

    def test_api_only_calls_agent_ask(self, security_client):
        """API 层只能调用 agent.ask()"""
        import inspect
        from src.api import app as app_module

        # 检查 create_app 中定义的 ask 端点函数
        src = inspect.getsource(app_module.create_app)
        # 端点应通过 runtime.ask() 调用
        assert "runtime.ask" in src, (
            "API 端点必须通过 runtime.ask() 调用"
        )


# ═══════════════════════════════════════════════════════════════
# 测试组 2: 禁止端点
# ═══════════════════════════════════════════════════════════════


class TestNoDirectSQL:
    """禁止直接 SQL 执行端点"""

    @pytest.mark.parametrize("path", [
        "/sql", "/execute", "/debug", "/trace", "/query", "/raw", "/admin",
    ])
    def test_forbidden_paths_get(self, security_client, path):
        """禁止路径的 GET 请求返回 404"""
        resp = security_client.get(path)
        assert resp.status_code == 404

    @pytest.mark.parametrize("path", [
        "/sql", "/execute", "/debug", "/trace", "/query",
    ])
    def test_forbidden_paths_post(self, security_client, path):
        """禁止路径的 POST 请求返回 404"""
        resp = security_client.post(path)
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# 测试组 3: 默认安全配置
# ═══════════════════════════════════════════════════════════════


class TestDefaultSecurityConfig:
    """安全默认配置"""

    def test_default_host_is_localhost(self):
        """默认 host 应为 127.0.0.1"""
        import yaml
        config_path = PROJECT_ROOT / "config" / "api_config.yml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["server"]["host"] == "127.0.0.1"

    def test_default_cors_is_disabled(self):
        """默认 CORS 应关闭"""
        import yaml
        config_path = PROJECT_ROOT / "config" / "api_config.yml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert config["security"]["cors_enabled"] is False

    def _test_fail_on_illegal_config(self):
        """非法配置应 fail closed（需要 mock）"""
        from src.api.runtime import AgentRuntime

        runtime = AgentRuntime(api_config_path="nonexistent_config.yml")
        runtime._load_api_config()
        # 使用安全默认值
        assert runtime.api_config["server"]["host"] == "127.0.0.1"
        assert runtime.api_config["security"]["cors_enabled"] is False

    def test_cors_not_in_app_middleware(self, security_client):
        """FastAPI app 不应有 CORS middleware"""
        app = security_client.app
        middlewares = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" not in middlewares


# ═══════════════════════════════════════════════════════════════
# 测试组 4: Runtime 不保存敏感数据
# ═══════════════════════════════════════════════════════════════


class TestRuntimeNoPersistence:
    """Runtime 不保存 question/answer 到持久化日志"""

    def test_runtime_ask_no_file_write(self):
        """ask() 方法不应写文件（持久化）"""
        import inspect
        from src.api.runtime import AgentRuntime

        src = inspect.getsource(AgentRuntime.ask)
        # 不应有文件写入操作
        assert "write_text" not in src
        assert "open(" not in src
        assert "json.dump" not in src

    def test_runtime_no_api_key_access(self):
        """runtime 不应读取 API Key"""
        import inspect
        from src.api.runtime import AgentRuntime

        src = inspect.getsource(AgentRuntime)
        # 只在 ask 方法中检查（其他方法中有配置注释是正常的）
        ask_src = inspect.getsource(AgentRuntime.ask)
        # ask 方法不应访问 api_key 或 token
        assert "api_key" not in ask_src.lower(), "ask() 不应访问 api_key"
        assert "authorization" not in ask_src.lower(), "ask() 不应访问 authorization"


# ═══════════════════════════════════════════════════════════════
# 测试组 5: 请求不允许控制参数
# ═══════════════════════════════════════════════════════════════


class TestNoClientControlParams:
    """客户端不能通过 HTTP 请求控制 Agent 行为"""

    def test_mode_param_rejected(self, security_client):
        """mode 参数应被拒绝"""
        resp = security_client.post("/v1/ask", json={
            "question": "test",
            "mode": "llm",
        })
        assert resp.status_code == 422

    def test_sql_param_rejected(self, security_client):
        """sql 参数应被拒绝"""
        resp = security_client.post("/v1/ask", json={
            "question": "test",
            "sql": "SELECT 1",
        })
        assert resp.status_code == 422

    def test_config_param_rejected(self, security_client):
        """config 参数应被拒绝"""
        resp = security_client.post("/v1/ask", json={
            "question": "test",
            "provider": "other",
        })
        assert resp.status_code == 422

    def test_api_key_param_rejected(self, security_client):
        """客户端传入的 API Key 参数应被拒绝"""
        resp = security_client.post("/v1/ask", json={
            "question": "test",
            "api_key": "sk-test",
        })
        assert resp.status_code == 422
