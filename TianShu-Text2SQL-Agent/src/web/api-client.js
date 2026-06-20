/* ═══════════════════════════════════════════════════════════════
 * Phase 7 —— api-client.js
 *
 * API 调用模块——安全封装对后端 /v1/ask 的调用。
 *
 * 安全约束：
 *   - Token 仅保存在模块闭包变量中（不写任何浏览器存储）
 *   - 请求仅发送到同源 /v1/ask
 *   - Token 通过 X-TianShu-Token header 发送
 *   - 不把 Token 放入 URL、请求体、console、DOM
 *   - 清空后不再携带旧 Token
 * ═══════════════════════════════════════════════════════════════ */

(function () {
    "use strict";

    // ── 模块内存变量（闭包私有，外部不可访问）──
    var _token = "";

    /**
     * 设置内存中的 Token
     * @param {string} token - 本地 API 令牌
     */
    window.TianShuApi = window.TianShuApi || {};
    window.TianShuApi.setToken = function (token) {
        if (typeof token !== "string" || !token.trim()) {
            throw new Error("令牌不能为空");
        }
        _token = token.trim();
    };

    /**
     * 清空内存中的 Token
     */
    window.TianShuApi.clearToken = function () {
        _token = "";
    };

    /**
     * 检查是否已设置 Token
     * @returns {boolean}
     */
    window.TianShuApi.hasToken = function () {
        return _token.length > 0;
    };

    /**
     * 检查 API 健康状态
     * @returns {Promise<object>} { ready: boolean, agent_online: boolean, ... }
     */
    window.TianShuApi.checkHealth = async function () {
        var resp = await fetch("/health/ready", { method: "GET" });
        var data = await resp.json();
        return {
            ready: resp.status === 200,
            status: resp.status,
            agent_online: data.agent_online || false,
            auth_ready: data.auth_ready || false,
            contract_version: data.contract_version || "",
        };
    };

    /**
     * 发送中文问数请求
     * @param {string} question - 用户的中文问题
     * @returns {Promise<object>} 公开响应结构
     */
    window.TianShuApi.ask = async function (question) {
        if (!_token) {
            throw new Error("未设置认证令牌");
        }
        if (!question || !question.trim()) {
            throw new Error("问题不能为空");
        }

        var resp = await fetch("/v1/ask", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-TianShu-Token": _token,
            },
            body: JSON.stringify({ question: question.trim() }),
        });

        var data = await resp.json();

        // ── 按 HTTP 状态码分类处理 ──
        if (resp.status === 200) {
            return data;  // 成功：answer / clarification / refusal
        }

        // ── 错误状态 ──
        var errorInfo = data.error || {};
        if (resp.status === 401) {
            _token = "";  // Token 无效时清空
            return {
                _error: true,
                _errorType: "auth_failed",
                code: errorInfo.code || "AUTH_FAILED",
                message: errorInfo.message || "认证失败，请重新输入令牌",
                request_id: errorInfo.request_id || "",
            };
        }
        if (resp.status === 429) {
            var retryAfter = resp.headers.get("Retry-After") || "60";
            return {
                _error: true,
                _errorType: "rate_limited",
                code: errorInfo.code || "SERVICE_BUSY",
                message: errorInfo.message || "当前问数请求较多，请稍后再试",
                retry_after: parseInt(retryAfter, 10) || 60,
                request_id: errorInfo.request_id || "",
            };
        }
        if (resp.status === 413) {
            return {
                _error: true,
                _errorType: "request_too_large",
                code: errorInfo.code || "REQUEST_TOO_LARGE",
                message: errorInfo.message || "请求体过大",
                request_id: errorInfo.request_id || "",
            };
        }
        if (resp.status === 422) {
            return {
                _error: true,
                _errorType: "validation_error",
                code: errorInfo.code || "VALIDATION_ERROR",
                message: errorInfo.message || "请求格式不正确",
                request_id: errorInfo.request_id || "",
            };
        }
        if (resp.status === 503) {
            return {
                _error: true,
                _errorType: "service_not_ready",
                code: errorInfo.code || "SERVICE_NOT_READY",
                message: errorInfo.message || "问数服务暂不可用，请稍后再试",
                request_id: errorInfo.request_id || "",
            };
        }

        // 其他错误（500 等）→ 通用错误
        return {
            _error: true,
            _errorType: "internal_error",
            code: errorInfo.code || "INTERNAL_ERROR",
            message: errorInfo.message || "服务内部异常，请联系管理员",
            request_id: errorInfo.request_id || "",
        };
    };
})();
