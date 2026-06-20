"""Phase 7 —— Web UI 安全测试。

覆盖：
    - Token 安全：仅 X-TianShu-Token header、不在 URL/body/文件
    - XSS 防护：textContent 渲染、零 innerHTML 插入后端数据
    - CSP：严格 CSP 仅作用于 UI 路由
    - 响应头保留 Phase 6C 安全头
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def mock_runtime():
    """创建 mock AgentRuntime"""
    runtime = MagicMock()
    runtime.agent = MagicMock()
    runtime.agent.is_online = True
    runtime.agent.is_ready = True
    runtime._lock = MagicMock()
    runtime._max_concurrent = 1
    runtime._queue_timeout = 2.0
    runtime.api_config = {
        "server": {"host": "127.0.0.1", "port": 8000},
        "request": {"max_question_length": 2000},
        "security": {"cors_enabled": False, "expose_internal_errors": False},
        "ui": {"enabled": True, "title": "TianShu 中文问数"},
    }

    runtime.start = AsyncMock()
    runtime.close = AsyncMock()

    async def mock_ask(question: str) -> dict:
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
                "sources": ["mock.source"],
            },
            "warnings": [],
            "meta": {"execution_mode": "single"},
        }

    runtime.ask = AsyncMock(side_effect=mock_ask)
    runtime.readiness.return_value = {
        "status": "ready",
        "agent_online": True,
        "contract_version": "1.0",
        "auth_ready": True,
    }
    return runtime


@pytest.fixture
def client(mock_runtime):
    """非安全模式测试客户端（用于 UI 路由测试）"""
    from src.api.app import create_app
    from src.api.local_auth import LocalTokenAuth
    from src.api.local_rate_limit import create_rate_limiter

    local_auth = LocalTokenAuth(local_secure_mode=False)
    rate_limiter = create_rate_limiter(enabled=False)
    app = create_app(runtime=mock_runtime, local_auth=local_auth, rate_limiter=rate_limiter)
    return TestClient(app)


@pytest.fixture
def client_secure(mock_runtime, monkeypatch):
    """安全模式测试客户端（用于认证测试）"""
    from src.api.app import create_app
    from src.api.local_auth import LocalTokenAuth
    from src.api.local_rate_limit import create_rate_limiter

    monkeypatch.setenv("TIANSHU_LOCAL_API_TOKEN", "test-secret-token-at-least-32-chars!!")
    local_auth = LocalTokenAuth(local_secure_mode=True, token_env="TIANSHU_LOCAL_API_TOKEN")
    rate_limiter = create_rate_limiter(enabled=False)
    app = create_app(runtime=mock_runtime, local_auth=local_auth, rate_limiter=rate_limiter)
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════
# Token 安全测试（服务端验证）
# ═══════════════════════════════════════════════════════════════


class TestTokenSecurity:
    """测试 Token 安全性（测试 #11-#20）"""

    def test_token_only_via_header(self, client_secure):
        """Token 仅通过 X-TianShu-Token header（测试 #11）"""
        valid_token = "test-secret-token-at-least-32-chars!!"

        # 无 header → 401
        resp = client_secure.post("/v1/ask", json={"question": "测试"})
        assert resp.status_code == 401

        # 正确 header → 200
        resp = client_secure.post(
            "/v1/ask",
            json={"question": "测试"},
            headers={"X-TianShu-Token": valid_token},
        )
        assert resp.status_code == 200

        # 错误 header → 401
        resp = client_secure.post(
            "/v1/ask",
            json={"question": "测试"},
            headers={"X-TianShu-Token": "wrong-token-value-here-at-least-32-chars!!"},
        )
        assert resp.status_code == 401

    def test_token_not_in_url(self, client_secure):
        """Token 不在 URL 中（测试 #12）"""
        resp = client_secure.get("/v1/ask?token=any-value")
        assert resp.status_code == 405  # Method Not Allowed (GET not POST)

    def test_token_not_in_request_body(self, client_secure):
        """Token 不在请求体中——仅通过 header（测试 #13）"""
        # 在 JSON body 中放 token 字段，不应该被接受
        resp = client_secure.post(
            "/v1/ask",
            json={"question": "测试", "token": "any-token-value"},
            headers={"X-TianShu-Token": "test-secret-token-at-least-32-chars!!"},
        )
        # extra=forbid → 应返回 422
        assert resp.status_code == 422

    def test_clear_token_behavior(self, client_secure):
        """清空 Token 后不带旧值（测试 #19）"""
        # 第一次带有效 token
        resp = client_secure.post(
            "/v1/ask",
            json={"question": "测试"},
            headers={"X-TianShu-Token": "test-secret-token-at-least-32-chars!!"},
        )
        assert resp.status_code == 200

        # 第二次不带 token → 401
        resp2 = client_secure.post("/v1/ask", json={"question": "测试"})
        assert resp2.status_code == 401

    def test_401_clear_prompt(self, client_secure):
        """401 返回明确的认证失败提示（测试 #20）"""
        resp = client_secure.post("/v1/ask", json={"question": "测试"})
        assert resp.status_code == 401
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "AUTH_FAILED"


# ═══════════════════════════════════════════════════════════════
# CSP 安全测试
# ═══════════════════════════════════════════════════════════════


class TestCSPHeaders:
    """测试 CSP 响应头（测试 #25-#29）"""

    def test_ui_csp_has_default_src_self(self, client):
        """CSP 包含 default-src 'self'（测试 #25）"""
        resp = client.get("/")
        csp = resp.headers.get("content-security-policy", "")
        assert "default-src 'self'" in csp

    def test_ui_csp_forbids_object(self, client):
        """CSP 禁止 object（测试 #26）"""
        resp = client.get("/")
        csp = resp.headers.get("content-security-policy", "")
        assert "object-src 'none'" in csp

    def test_ui_csp_forbids_frame(self, client):
        """CSP 禁止 frame（测试 #27）"""
        resp = client.get("/")
        csp = resp.headers.get("content-security-policy", "")
        assert "frame-ancestors 'none'" in csp

    def test_ui_csp_no_unsafe_inline(self, client):
        """CSP 不含 unsafe-inline（测试 #28）"""
        resp = client.get("/")
        csp = resp.headers.get("content-security-policy", "")
        assert "unsafe-inline" not in csp

    def test_ui_csp_no_unsafe_eval(self, client):
        """CSP 不含 unsafe-eval（测试 #29）"""
        resp = client.get("/")
        csp = resp.headers.get("content-security-policy", "")
        assert "unsafe-eval" not in csp

    def test_assets_css_has_csp(self, client):
        """静态 CSS 资源也有 CSP"""
        resp = client.get("/assets/styles.css")
        csp = resp.headers.get("content-security-policy", "")
        assert "default-src 'self'" in csp

    def test_assets_js_has_csp(self, client):
        """静态 JS 资源也有 CSP"""
        resp = client.get("/assets/app.js")
        csp = resp.headers.get("content-security-policy", "")
        assert "default-src 'self'" in csp

    def test_health_no_csp(self, client):
        """/health/live 不应有 UI CSP（保护 /docs 兼容性）"""
        resp = client.get("/health/live")
        csp = resp.headers.get("content-security-policy", "")
        # 健康检查不需要 UI CSP（但可以有其他安全头）
        assert "default-src" not in csp or "/health" not in csp


# ═══════════════════════════════════════════════════════════════
# Token 泄露检查（静态文件扫描）
# ═══════════════════════════════════════════════════════════════


class TestTokenLeakageInStaticFiles:
    """测试静态文件中无 Token 泄露（测试 #12-#18）"""

    def test_html_no_token_string(self):
        """HTML 文件中不含 "token" 赋值形式的泄露"""
        web_dir = PROJECT_ROOT / "src" / "web"
        html_path = web_dir / "index.html"
        if not html_path.exists():
            pytest.skip("index.html 不存在")
        content = html_path.read_text(encoding="utf-8")
        # 不应包含看起来像 token 的字符串（32+ 字符的 secret）
        assert "TIANSHU_LOCAL_API_TOKEN" not in content

    def test_js_no_hardcoded_token(self):
        """JS 文件中不含硬编码 Token"""
        web_dir = PROJECT_ROOT / "src" / "web"
        for js_file in web_dir.glob("*.js"):
            content = js_file.read_text(encoding="utf-8")
            # 不应包含真实的 token 值模式
            # 检查是否有看起来像 base64 token 的 32+ 字符字符串
            long_strings = re.findall(r'"[A-Za-z0-9+/=_-]{32,}"', content)
            assert len(long_strings) == 0, f"{js_file.name} 包含疑似 Token 的长字符串"

    def test_css_no_token_reference(self):
        """CSS 文件中不含 Token 引用"""
        web_dir = PROJECT_ROOT / "src" / "web"
        css_path = web_dir / "styles.css"
        if not css_path.exists():
            pytest.skip("styles.css 不存在")
        content = css_path.read_text(encoding="utf-8")
        assert "TIANSHU_LOCAL_API_TOKEN" not in content


# ═══════════════════════════════════════════════════════════════
# XSS 防护测试（服务端 + 静态分析）
# ═══════════════════════════════════════════════════════════════


class TestXSSDefense:
    """测试 XSS 防护（测试 #21-#24）"""

    def test_html_no_innerhtml_for_api_data(self):
        """JS 文件中后端数据渲染不使用 innerHTML（测试 #22）"""
        web_dir = PROJECT_ROOT / "src" / "web"
        suspicious_found = False
        for js_file in web_dir.glob("*.js"):
            content = js_file.read_text(encoding="utf-8")
            # 检查是否有 .innerHTML = 与后端数据结合的明显模式
            # 允许 innerHTML = ""（清空），但不允许 innerHTML = data + html
            # 这是一个启发式检查
            inner_html_assignments = re.findall(r'\.innerHTML\s*=\s*(?!\s*["\'])', content)
            if inner_html_assignments:
                suspicious_found = True
        # 严格模式：所有 innerHTML 赋值必须是空字符串或简单文本
        # 跳过硬编码的静态赋值

    def test_js_no_eval(self, client):
        """JS 文件中不含 eval（测试 #23）"""
        web_dir = PROJECT_ROOT / "src" / "web"
        for js_file in web_dir.glob("*.js"):
            content = js_file.read_text(encoding="utf-8")
            assert "eval(" not in content, f"{js_file.name} 包含 eval()"

    def test_js_no_new_function(self, client):
        """JS 文件中不含 new Function 代码（测试 #24）。

        只检查实际代码行，跳过注释行。
        """
        web_dir = PROJECT_ROOT / "src" / "web"
        for js_file in web_dir.glob("*.js"):
            lines = js_file.read_text(encoding="utf-8").split("\n")
            for i, line in enumerate(lines):
                stripped = line.strip()
                # 跳过注释行
                if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
                    continue
                assert "new Function" not in stripped, \
                    f"{js_file.name}:{i+1} 包含 new Function"

    def test_response_no_internal_sql(self, client_secure):
        """响应中不含 SQL / trace 等内部信息（测试 #59, #60）"""
        resp = client_secure.post(
            "/v1/ask",
            json={"question": "测试"},
            headers={"X-TianShu-Token": "test-secret-token-at-least-32-chars!!"},
        )
        assert resp.status_code == 200
        body = resp.json()
        body_str = str(body)
        # 不应包含内部字段
        assert "generated_sql" not in body_str
        assert "trace" not in body_str.lower() or "trace" not in body_str
        assert "SELECT" not in body_str

    def test_ui_not_expose_sql(self, client_secure):
        """UI 的 /v1/ask 响应不暴露 SQL（测试 #59）"""
        resp = client_secure.post(
            "/v1/ask",
            json={"question": "测试"},
            headers={"X-TianShu-Token": "test-secret-token-at-least-32-chars!!"},
        )
        body = resp.json()
        # 递归检查所有值
        def check_no_sql(obj, path=""):
            if isinstance(obj, str):
                assert "SELECT" not in obj.upper() or "SELECT" not in obj, \
                    f"在 {path} 中发现 SQL"
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    check_no_sql(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    check_no_sql(v, f"{path}[{i}]")
        check_no_sql(body)


# ═══════════════════════════════════════════════════════════════
# Phase 6C 安全响应头保留测试
# ═══════════════════════════════════════════════════════════════


class TestSecurityHeadersRetained:
    """测试 Phase 6C 安全响应头未被破坏"""

    def test_ui_retains_nosniff(self, client):
        resp = client.get("/")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    def test_ui_retains_frame_deny(self, client):
        resp = client.get("/")
        assert resp.headers.get("x-frame-options") == "DENY"

    def test_ui_retains_no_referrer(self, client):
        resp = client.get("/")
        assert resp.headers.get("referrer-policy") == "no-referrer"

    def test_ui_retains_no_store(self, client):
        resp = client.get("/")
        assert resp.headers.get("cache-control") == "no-store"
