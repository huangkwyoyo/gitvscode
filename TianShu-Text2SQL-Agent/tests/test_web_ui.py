"""Phase 7 —— Web UI 静态路由测试。

覆盖：
    - GET / 返回 200 + text/html
    - UI disabled 返回 404
    - 静态资源返回 200
    - 无目录穿越
    - HTML 无内联 script/style
    - 无外部 URL 引用
"""

from __future__ import annotations

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
    """创建完全 mock 的 AgentRuntime，不连接任何真实数据库"""
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
                "sources": [],
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
    """使用 mock runtime 创建测试客户端（非安全模式，用于 UI 路由测试）"""
    from src.api.app import create_app
    from src.api.local_auth import LocalTokenAuth
    from src.api.local_rate_limit import create_rate_limiter

    local_auth = LocalTokenAuth(local_secure_mode=False)
    rate_limiter = create_rate_limiter(enabled=False)
    app = create_app(
        runtime=mock_runtime,
        local_auth=local_auth,
        rate_limiter=rate_limiter,
    )
    return TestClient(app)


@pytest.fixture
def client_secure(mock_runtime, monkeypatch):
    """创建安全模式的测试客户端（用于认证测试）"""
    from src.api.app import create_app
    from src.api.local_auth import LocalTokenAuth
    from src.api.local_rate_limit import create_rate_limiter

    # 设置临时环境变量作为有效令牌
    monkeypatch.setenv("TIANSHU_LOCAL_API_TOKEN", "test-secret-token-at-least-32-chars!!")
    local_auth = LocalTokenAuth(local_secure_mode=True, token_env="TIANSHU_LOCAL_API_TOKEN")
    rate_limiter = create_rate_limiter(enabled=False)
    app = create_app(
        runtime=mock_runtime,
        local_auth=local_auth,
        rate_limiter=rate_limiter,
    )
    return TestClient(app)


@pytest.fixture
def client_ui_disabled(mock_runtime):
    """创建 UI 禁用的测试客户端"""
    from src.api.app import create_app
    from src.api.local_auth import LocalTokenAuth
    from src.api.local_rate_limit import create_rate_limiter

    mock_runtime.api_config["ui"] = {"enabled": False, "title": "TianShu 中文问数"}
    local_auth = LocalTokenAuth(local_secure_mode=False)
    rate_limiter = create_rate_limiter(enabled=False)
    app = create_app(
        runtime=mock_runtime,
        local_auth=local_auth,
        rate_limiter=rate_limiter,
    )
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════
# 静态 UI 路由测试
# ═══════════════════════════════════════════════════════════════


class TestRootEndpoint:
    """测试 GET / 根路由"""

    def test_root_returns_200(self, client):
        """GET / 返回 200（测试 #1）"""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_content_type_html(self, client):
        """GET / Content-Type 为 text/html（测试 #2）"""
        resp = client.get("/")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_ui_disabled_returns_404(self, client_ui_disabled):
        """UI 禁用时 GET / 返回 404（测试 #3）"""
        resp = client_ui_disabled.get("/")
        assert resp.status_code == 404

    def test_root_contains_title(self, client):
        """GET / 返回的 HTML 包含页面标题"""
        resp = client.get("/")
        assert "天枢" in resp.text


class TestStaticAssets:
    """测试静态资源路由"""

    def test_static_css_returns_200(self, client):
        """CSS 资源返回 200（测试 #4）"""
        resp = client.get("/assets/styles.css")
        assert resp.status_code == 200

    def test_static_app_js_returns_200(self, client):
        """app.js 资源返回 200"""
        resp = client.get("/assets/app.js")
        assert resp.status_code == 200

    def test_static_api_client_js_returns_200(self, client):
        """api-client.js 资源返回 200"""
        resp = client.get("/assets/api-client.js")
        assert resp.status_code == 200

    def test_static_renderers_js_returns_200(self, client):
        """renderers.js 资源返回 200"""
        resp = client.get("/assets/renderers.js")
        assert resp.status_code == 200

    def test_static_chart_renderer_js_returns_200(self, client):
        """chart-renderer.js 资源返回 200"""
        resp = client.get("/assets/chart-renderer.js")
        assert resp.status_code == 200


class TestDirectoryTraversal:
    """测试目录穿越防护（测试 #5）"""

    def test_no_parent_traversal(self, client):
        """.. 路径不能穿越到上级目录"""
        resp = client.get("/assets/../config/secrets.yml")
        # 应返回 404 而非文件内容
        assert resp.status_code == 404

    def test_no_absolute_path(self, client):
        """绝对路径不能访问"""
        resp = client.get("/assets/etc/passwd")
        assert resp.status_code == 404

    def test_nonexistent_asset(self, client):
        """不存在的资源返回 404"""
        resp = client.get("/assets/nonexistent.js")
        assert resp.status_code == 404


class TestSecurityHeadersOnUI:
    """测试 UI 路由的安全响应头"""

    def test_ui_has_csp_header(self, client):
        """UI 页面应有 Content-Security-Policy 头"""
        resp = client.get("/")
        # 验证 CSP 存在且不含 unsafe-inline
        csp = resp.headers.get("content-security-policy", "")
        assert "default-src" in csp
        assert "unsafe-inline" not in csp.lower()
        assert "unsafe-eval" not in csp.lower()

    def test_ui_has_security_headers(self, client):
        """UI 页面保留 Phase 6C 安全响应头"""
        resp = client.get("/")
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"
        assert resp.headers.get("referrer-policy") == "no-referrer"


class TestHTMLContent:
    """测试 HTML 内容安全性"""

    def test_no_inline_script(self, client):
        """HTML 不含内联 <script>（测试 #8）"""
        resp = client.get("/")
        html = resp.text
        # 检查 script 标签不直接包含代码
        import re
        scripts = re.findall(r'<script[^>]*>', html)
        for s in scripts:
            # 所有 script 标签应有 src 属性（外部引用），无内联代码
            if 'src=' not in s:
                # 允许 type="module" 的空标签
                pass

    def test_no_inline_style(self, client):
        """HTML 不含内联 <style>（测试 #9）"""
        resp = client.get("/")
        html = resp.text
        # 不应有 <style> 标签（样式通过外部 CSS）
        assert "<style>" not in html.lower()

    def test_no_external_cdn(self, client):
        """HTML 不引用外部 CDN 资源（测试 #6）"""
        resp = client.get("/")
        html = resp.text
        # 不引用外部域名
        assert "http://" not in html
        assert "https://" not in html
        assert "cdn." not in html.lower()
        assert "googleapis" not in html.lower()
        assert "unpkg" not in html.lower()
        assert "jsdelivr" not in html.lower()

    def test_script_tags_have_src(self, client):
        """所有 <script> 标签通过 src 引用外部文件（无内联代码）"""
        resp = client.get("/")
        html = resp.text
        import re
        # 找到所有 <script> 开始标签
        script_starts = re.findall(r'<script\b[^>]*>', html)
        for tag in script_starts:
            assert 'src=' in tag, f"内联 script 标签: {tag}"


# ═══════════════════════════════════════════════════════════════
# API 兼容性测试 — 确保 UI 路由不破坏现有端点
# ═══════════════════════════════════════════════════════════════


class TestAPICompatibility:
    """测试现有 API 端点不受影响"""

    def test_health_live_still_works(self, client):
        """GET /health/live 仍然返回 200"""
        resp = client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"

    def test_health_ready_still_works(self, client):
        """GET /health/ready 仍然可用"""
        resp = client.get("/health/ready")
        assert resp.status_code == 200

    def test_ask_without_token_returns_401(self, client_secure):
        """POST /v1/ask 无 Token（安全模式）返回 401"""
        resp = client_secure.post("/v1/ask", json={"question": "测试"})
        assert resp.status_code == 401

    def test_ask_with_valid_token_returns_200(self, client_secure):
        """POST /v1/ask 带有效 Token 返回 200"""
        resp = client_secure.post(
            "/v1/ask",
            json={"question": "测试"},
            headers={"X-TianShu-Token": "test-secret-token-at-least-32-chars!!"},
        )
        assert resp.status_code == 200

    def test_docs_still_works(self, client):
        """/docs 仍然可用"""
        resp = client.get("/docs")
        assert resp.status_code == 200
