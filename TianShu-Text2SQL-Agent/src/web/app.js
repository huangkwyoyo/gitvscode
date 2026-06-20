/* ═══════════════════════════════════════════════════════════════
 * Phase 7 —— app.js
 *
 * Web UI 主交互逻辑——状态机 + 事件绑定。
 *
 * 状态机：idle → token_missing → submitting → answer/clarification/refusal/api_error
 *
 * 安全约束：
 *   - 不保存 Token 到任何浏览器存储
 *   - 不把 Token 输出到 console/DOM
 *   - 不允许用户修改 API URL
 *   - 不自动重试问数请求
 * ═══════════════════════════════════════════════════════════════ */

(function () {
    "use strict";

    var Api = window.TianShuApi;
    var Renderers = window.TianShuRenderers;

    if (!Api || !Renderers) {
        console.error("TianShu Web UI: 依赖模块未加载");
        return;
    }

    // ── 状态枚举 ──
    var STATE = {
        IDLE: "idle",
        TOKEN_MISSING: "token_missing",
        SUBMITTING: "submitting",
        ANSWER: "answer",
        CLARIFICATION: "clarification",
        REFUSAL: "refusal",
        API_ERROR: "api_error",
    };

    var _currentState = STATE.TOKEN_MISSING;

    // ── DOM 引用 ──
    var $ = function (id) { return document.getElementById(id); };

    var dom = {
        apiStatus: $("api-status"),
        tokenInput: $("token-input"),
        tokenApplyBtn: $("token-apply-btn"),
        tokenClearBtn: $("token-clear-btn"),
        tokenStatus: $("token-status"),
        questionInput: $("question-input"),
        submitBtn: $("submit-btn"),
        clearBtn: $("clear-btn"),
        charCountCurrent: $("char-count-current"),
        charCountMax: $("char-count-max"),
        resultSection: $("result-section"),
        resultContent: $("result-content"),
        dataSection: $("data-section"),
        loadingOverlay: $("loading-overlay"),
    };

    // ── 配置 ──
    var MAX_QUESTION_LENGTH = 2000;

    /**
     * 转换状态
     * @param {string} newState
     */
    function setState(newState) {
        _currentState = newState;
    }

    /**
     * 显示/隐藏 loading
     * @param {boolean} show
     */
    function showLoading(show) {
        if (dom.loadingOverlay) {
            dom.loadingOverlay.classList.toggle("hidden", !show);
        }
        if (dom.submitBtn) {
            dom.submitBtn.disabled = show;
        }
    }

    /**
     * 更新 API 状态指示器
     */
    async function checkApiStatus() {
        if (!dom.apiStatus) { return; }
        dom.apiStatus.className = "status-indicator status-checking";
        var statusText = dom.apiStatus.querySelector(".status-text");
        if (statusText) { statusText.textContent = "检查中…"; }

        try {
            var health = await Api.checkHealth();
            if (health.ready) {
                dom.apiStatus.className = "status-indicator status-ready";
                if (statusText) { statusText.textContent = "可用"; }
            } else {
                dom.apiStatus.className = "status-indicator status-error";
                if (statusText) { statusText.textContent = "不可用"; }
            }
        } catch (e) {
            dom.apiStatus.className = "status-indicator status-error";
            if (statusText) { statusText.textContent = "不可用"; }
        }
    }

    /**
     * 更新 Token 状态 UI
     */
    function updateTokenUI() {
        var hasToken = Api.hasToken();
        if (dom.tokenStatus) {
            if (hasToken) {
                dom.tokenStatus.textContent = "✓ 令牌已设置（仅内存中）";
                dom.tokenStatus.className = "token-status token-set";
            } else {
                dom.tokenStatus.textContent = "";
                dom.tokenStatus.className = "token-status";
            }
        }
        updateSubmitState();
    }

    /**
     * 更新提交按钮状态
     */
    function updateSubmitState() {
        if (!dom.submitBtn || !dom.questionInput) { return; }

        var hasToken = Api.hasToken();
        var question = dom.questionInput.value.trim();
        var isSubmitting = _currentState === STATE.SUBMITTING;

        dom.submitBtn.disabled = !hasToken || question.length === 0 || question.length > MAX_QUESTION_LENGTH || isSubmitting;
    }

    /**
     * 更新字符计数
     */
    function updateCharCount() {
        if (!dom.charCountCurrent || !dom.questionInput) { return; }
        var len = dom.questionInput.value.length;
        dom.charCountCurrent.textContent = String(len);
        if (len > MAX_QUESTION_LENGTH) {
            dom.charCountCurrent.style.color = "var(--color-error)";
        } else {
            dom.charCountCurrent.style.color = "";
        }
    }

    /**
     * 隐藏结果区域
     */
    function hideResults() {
        if (dom.resultSection) { dom.resultSection.classList.add("hidden"); }
        if (dom.dataSection) { dom.dataSection.classList.add("hidden"); }
    }

    /**
     * 应用 Token
     */
    function applyToken() {
        if (!dom.tokenInput) { return; }
        var token = dom.tokenInput.value.trim();
        if (!token) {
            if (dom.tokenStatus) {
                dom.tokenStatus.textContent = "请输入令牌";
                dom.tokenStatus.className = "token-status token-error";
            }
            setState(STATE.TOKEN_MISSING);
            return;
        }

        try {
            Api.setToken(token);
            if (dom.tokenStatus) {
                dom.tokenStatus.textContent = "✓ 令牌已设置（仅内存中）";
                dom.tokenStatus.className = "token-status token-set";
            }
            setState(STATE.IDLE);
        } catch (e) {
            if (dom.tokenStatus) {
                dom.tokenStatus.textContent = "令牌设置失败";
                dom.tokenStatus.className = "token-status token-error";
            }
            setState(STATE.TOKEN_MISSING);
        }

        updateTokenUI();
    }

    /**
     * 清空 Token
     */
    function clearToken() {
        Api.clearToken();
        if (dom.tokenInput) { dom.tokenInput.value = ""; }
        if (dom.tokenStatus) {
            dom.tokenStatus.textContent = "";
            dom.tokenStatus.className = "token-status";
        }
        setState(STATE.TOKEN_MISSING);
        updateTokenUI();
        hideResults();
    }

    /**
     * 提交问数请求
     */
    async function submitQuestion() {
        if (_currentState === STATE.SUBMITTING) { return; }
        if (!Api.hasToken()) {
            setState(STATE.TOKEN_MISSING);
            updateTokenUI();
            return;
        }

        var question = dom.questionInput ? dom.questionInput.value.trim() : "";
        if (!question) { return; }
        if (question.length > MAX_QUESTION_LENGTH) { return; }

        setState(STATE.SUBMITTING);
        showLoading(true);
        hideResults();

        try {
            var result = await Api.ask(question);

            showLoading(false);
            setSubmitReady();

            // ── 判断是否为 API 错误 ──
            if (result._error) {
                setState(STATE.API_ERROR);
                if (dom.resultSection) { dom.resultSection.classList.remove("hidden"); }
                Renderers.renderApiError(result, dom.resultContent);
                return;
            }

            // ── 按 response_type 分发渲染 ──
            var responseType = result.response_type || "answer";
            if (dom.resultSection) { dom.resultSection.classList.remove("hidden"); }

            switch (responseType) {
                case "answer":
                    setState(STATE.ANSWER);
                    Renderers.renderAnswer(result, dom.resultContent);
                    break;
                case "clarification":
                    setState(STATE.CLARIFICATION);
                    Renderers.renderClarification(result, dom.resultContent);
                    break;
                case "refusal":
                    setState(STATE.REFUSAL);
                    Renderers.renderRefusal(result, dom.resultContent);
                    break;
                case "error":
                    setState(STATE.API_ERROR);
                    Renderers.renderApiError({
                        _error: true,
                        _errorType: "internal_error",
                        code: "INTERNAL_ERROR",
                        message: "查询执行出错",
                        request_id: "",
                    }, dom.resultContent);
                    break;
                default:
                    setState(STATE.API_ERROR);
                    Renderers.renderApiError({
                        _error: true,
                        _errorType: "internal_error",
                        code: "INTERNAL_ERROR",
                        message: "未知响应类型",
                        request_id: "",
                    }, dom.resultContent);
            }

        } catch (e) {
            // 网络异常
            showLoading(false);
            setSubmitReady();
            setState(STATE.API_ERROR);

            if (dom.resultSection) { dom.resultSection.classList.remove("hidden"); }
            Renderers.renderApiError({
                _error: true,
                _errorType: "network_error",
                code: "NETWORK_ERROR",
                message: "网络连接异常，请检查服务是否运行",
                request_id: "",
            }, dom.resultContent);
        }
    }

    /**
     * 恢复提交按钮状态
     */
    function setSubmitReady() {
        if (_currentState === STATE.SUBMITTING) {
            setState(STATE.IDLE);
        }
        updateSubmitState();
    }

    /**
     * 填充示例问题（不自动提交）
     * @param {string} question
     */
    function fillExample(question) {
        if (!dom.questionInput) { return; }
        dom.questionInput.value = question;
        dom.questionInput.focus();
        updateCharCount();
        updateSubmitState();
    }

    // ═══════════════════════════════════════════════════════════
    // 事件绑定
    // ═══════════════════════════════════════════════════════════

    // Token 操作
    if (dom.tokenApplyBtn) {
        dom.tokenApplyBtn.addEventListener("click", applyToken);
    }
    if (dom.tokenClearBtn) {
        dom.tokenClearBtn.addEventListener("click", clearToken);
    }
    if (dom.tokenInput) {
        dom.tokenInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter") { applyToken(); }
        });
    }

    // 问数提交
    if (dom.submitBtn) {
        dom.submitBtn.addEventListener("click", submitQuestion);
    }

    // Ctrl+Enter 提交
    if (dom.questionInput) {
        dom.questionInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                submitQuestion();
            }
        });
        dom.questionInput.addEventListener("input", function () {
            updateCharCount();
            updateSubmitState();
        });
    }

    // 清空按钮
    if (dom.clearBtn) {
        dom.clearBtn.addEventListener("click", function () {
            if (dom.questionInput) {
                dom.questionInput.value = "";
                updateCharCount();
                updateSubmitState();
            }
            hideResults();
            setState(STATE.IDLE);
        });
    }

    // 示例问题按钮
    var exampleBtns = document.querySelectorAll(".btn-example[data-question]");
    for (var i = 0; i < exampleBtns.length; i++) {
        exampleBtns[i].addEventListener("click", function () {
            var q = this.getAttribute("data-question") || "";
            fillExample(q);
        });
    }

    // ═══════════════════════════════════════════════════════════
    // 初始化
    // ═══════════════════════════════════════════════════════════

    function init() {
        // 设置最大字符数显示
        if (dom.charCountMax) {
            dom.charCountMax.textContent = String(MAX_QUESTION_LENGTH);
        }

        // 初始状态
        setState(STATE.TOKEN_MISSING);
        updateSubmitState();
        hideResults();

        // 检查 API 状态
        checkApiStatus();

        // 定时检查（每 30 秒）
        setInterval(checkApiStatus, 30000);

        // focus Token 输入框
        if (dom.tokenInput) {
            setTimeout(function () { dom.tokenInput.focus(); }, 100);
        }
    }

    // DOM 加载完成后初始化
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
