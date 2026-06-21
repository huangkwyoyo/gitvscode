/* ═══════════════════════════════════════════════════════════════
 * Phase 7 —— renderers.js
 *
 * 响应渲染模块——将公开响应结构渲染为安全 DOM 元素。
 *
 * 安全约束：
 *   - 所有后端文本通过 textContent 或 createElement 渲染
 *   - 零 innerHTML 插入后端数据
 *   - 零 eval / new Function
 *   - 不显示 SQL、trace、Token、数据库路径
 *   - 按 response_type 互斥渲染
 * ═══════════════════════════════════════════════════════════════ */

(function () {
    "use strict";

    var R = window.TianShuRenderers = window.TianShuRenderers || {};

    /**
     * 创建安全文本元素（textContent，防 XSS）
     * @param {string} tag - HTML 标签名
     * @param {string} text - 文本内容
     * @param {string} [className] - CSS 类名
     * @returns {HTMLElement}
     */
    function safeEl(tag, text, className) {
        var el = document.createElement(tag);
        if (text != null) {
            el.textContent = text;
        }
        if (className) {
            el.className = className;
        }
        return el;
    }

    /**
     * 清空容器
     * @param {HTMLElement} container
     */
    function clearContainer(container) {
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }
    }

    /**
     * 渲染 answer 类型响应
     * @param {object} data - 公开响应
     * @param {HTMLElement} resultContainer - 结果内容容器
     */
    R.renderAnswer = function (data, resultContainer) {
        clearContainer(resultContainer);

        var answer = data.answer || {};
        var answerText = answer.text || "";

        // 中文答案文本
        if (answerText) {
            var textEl = safeEl("div", answerText, "answer-text");
            resultContainer.appendChild(textEl);
        }

        // 渲染数据区域
        R.renderDataSection(data);
    };

    /**
     * 渲染 clarification 类型响应
     * @param {object} data - 公开响应
     * @param {HTMLElement} resultContainer - 结果内容容器
     */
    R.renderClarification = function (data, resultContainer) {
        clearContainer(resultContainer);

        var clarification = data.clarification || {};
        var message = clarification.message || "";

        var box = document.createElement("div");
        box.className = "clarification-box";

        var title = safeEl("div", "需要补充信息", "clarification-title");
        box.appendChild(title);

        if (message) {
            var msg = safeEl("p", message);
            box.appendChild(msg);
        }

        var hint = safeEl("p", "请根据上述提示补充问题后重新提交。", "clarification-hint");
        box.appendChild(hint);

        resultContainer.appendChild(box);

        // 隐藏数据区域（不应显示图表）
        var dataSection = document.getElementById("data-section");
        if (dataSection) { dataSection.classList.add("hidden"); }
    };

    /**
     * 渲染 refusal 类型响应
     * @param {object} data - 公开响应
     * @param {HTMLElement} resultContainer - 结果内容容器
     */
    R.renderRefusal = function (data, resultContainer) {
        clearContainer(resultContainer);

        var refusal = data.refusal || {};
        var reason = refusal.reason || "";

        var box = document.createElement("div");
        box.className = "refusal-box";

        var title = safeEl("div", "请求已被拒绝", "refusal-title");
        box.appendChild(title);

        if (reason) {
            var reasonEl = safeEl("p", reason);
            box.appendChild(reasonEl);
        }

        resultContainer.appendChild(box);

        // 隐藏数据区域
        var dataSection = document.getElementById("data-section");
        if (dataSection) { dataSection.classList.add("hidden"); }
    };

    /**
     * 渲染 API 错误
     * @param {object} errorData - { _error: true, _errorType, code, message, request_id }
     * @param {HTMLElement} resultContainer - 结果内容容器
     */
    R.renderApiError = function (errorData, resultContainer) {
        clearContainer(resultContainer);

        var box = document.createElement("div");
        box.className = "error-box";

        if (errorData.code) {
            box.appendChild(safeEl("div", errorData.code, "error-code"));
        }
        if (errorData.message) {
            box.appendChild(safeEl("div", errorData.message, "error-message"));
        }
        if (errorData.request_id) {
            box.appendChild(safeEl("div", "请求 ID: " + errorData.request_id, "error-request-id"));
        }

        resultContainer.appendChild(box);

        // 隐藏数据区域
        var dataSection = document.getElementById("data-section");
        if (dataSection) { dataSection.classList.add("hidden"); }

        // 特殊处理：限流时显示倒计时
        if (errorData._errorType === "rate_limited" && errorData.retry_after) {
            var countdown = safeEl("div", String(errorData.retry_after) + " 秒后可重试", "retry-countdown");
            box.parentNode.insertBefore(countdown, box.nextSibling);

            // 倒计时
            var remaining = errorData.retry_after;
            var interval = setInterval(function () {
                remaining--;
                if (remaining <= 0) {
                    clearInterval(interval);
                    countdown.textContent = "现在可以重新提交";
                } else {
                    countdown.textContent = remaining + " 秒后可重试";
                }
            }, 1000);
        }
    };

    /**
     * 渲染警告列表
     * @param {Array<string>} warnings
     */
    R.renderWarnings = function (warnings) {
        var container = document.getElementById("warnings-container");
        var list = document.getElementById("warnings-list");
        if (!container || !list) { return; }

        clearContainer(list);

        if (!warnings || warnings.length === 0) {
            container.classList.add("hidden");
            return;
        }

        container.classList.remove("hidden");
        for (var i = 0; i < warnings.length; i++) {
            var li = safeEl("li", warnings[i]);
            list.appendChild(li);
        }
    };

    /**
     * 渲染数据来源列表
     * @param {Array<string>} sources
     */
    R.renderSources = function (sources) {
        var container = document.getElementById("sources-container");
        var list = document.getElementById("sources-list");
        if (!container || !list) { return; }

        clearContainer(list);

        if (!sources || sources.length === 0) {
            container.classList.add("hidden");
            return;
        }

        container.classList.remove("hidden");
        for (var i = 0; i < sources.length; i++) {
            var li = safeEl("li", sources[i]);
            list.appendChild(li);
        }
    };

    /**
     * 渲染元信息（execution_mode, contract_version）
     * @param {object} meta
     * @param {string} contractVersion
     */
    R.renderMeta = function (meta, contractVersion) {
        var container = document.getElementById("meta-container");
        var modeEl = document.getElementById("execution-mode");
        var versionEl = document.getElementById("contract-version");
        if (!container || !modeEl || !versionEl) { return; }

        container.classList.remove("hidden");
        modeEl.textContent = (meta && meta.execution_mode) ? meta.execution_mode : "—";
        versionEl.textContent = contractVersion || "—";
    };

    /**
     * 渲染完整数据区域
     * @param {object} data - 公开响应
     */
    R.renderDataSection = function (data) {
        var dataSection = document.getElementById("data-section");
        if (!dataSection) { return; }

        dataSection.classList.remove("hidden");

        var responseData = data.data || {};

        // 渲染图表
        var chartSpec = responseData.chart_spec;
        var hasChart = chartSpec && chartSpec.chart_type;
        console.log("renderers: renderDataSection, hasChart=" + hasChart + ", chart_type=" + (chartSpec && chartSpec.chart_type) + ", TianShuChartRenderer=" + (typeof window.TianShuChartRenderer));
        var chartContainer = document.getElementById("chart-container");
        if (hasChart && chartContainer && window.TianShuChartRenderer) {
            chartContainer.classList.remove("hidden");
            try {
                window.TianShuChartRenderer.renderChart(chartSpec, chartContainer);
            } catch (e) {
                // 图表渲染异常，降级为 table
                console.error("图表渲染失败:", e);
                chartContainer.classList.add("hidden");
                // 在表格上方显示降级原因
                var errNote = document.createElement("p");
                errNote.textContent = "图表渲染失败，已降级为表格：" + (e.message || "未知错误");
                errNote.style.cssText = "font-size:12px;color:var(--color-warning);margin-bottom:8px;";
                var tableContainer = document.getElementById("table-preview-container");
                if (tableContainer) {
                    tableContainer.insertBefore(errNote, tableContainer.firstChild);
                }
                if (chartSpec.data_preview) {
                    R.renderTablePreview(chartSpec.columns || [], chartSpec.data_preview);
                }
            }
        } else if (chartContainer) {
            chartContainer.classList.add("hidden");
            // 无 chart_spec 但有数据预览时，显示表格
            if (chartSpec && chartSpec.data_preview && chartSpec.data_preview.length > 0) {
                R.renderTablePreview(chartSpec.columns || [], chartSpec.data_preview);
            }
        }

        // 渲染警告
        R.renderWarnings(data.warnings);

        // 渲染数据来源
        R.renderSources(responseData.sources);

        // 渲染元信息
        R.renderMeta(data.meta, data.contract_version);

        // 多计划标记
        if (responseData.is_multi_plan) {
            var metaContainer = document.getElementById("meta-container");
            if (metaContainer) {
                var multiPlanBadge = safeEl("span", "多计划查询", "");
                multiPlanBadge.style.cssText =
                    "background: rgba(200, 137, 30, 0.08); color: #C8891E; " +
                    "padding: 2px 8px; border-radius: 3px; font-size: 11px; margin-left: 8px;";
                metaContainer.appendChild(multiPlanBadge);
            }
        }
    };

    /**
     * 渲染数据预览表格（降级或 table 类型时使用）
     * @param {Array<string>} columns - 列名
     * @param {Array<Array>} rows - 数据行
     */
    R.renderTablePreview = function (columns, rows) {
        var container = document.getElementById("table-preview-container");
        var preview = document.getElementById("table-preview");
        if (!container || !preview) { return; }

        clearContainer(preview);
        container.classList.remove("hidden");

        if (!rows || rows.length === 0) {
            preview.appendChild(safeEl("p", "无数据", ""));
            return;
        }

        // 构建表格
        var table = document.createElement("table");
        table.className = "data-table";

        // 表头
        var thead = document.createElement("thead");
        var headerRow = document.createElement("tr");
        var cols = columns && columns.length > 0 ? columns : [];
        // 如果未提供列名，生成默认列名
        if (cols.length === 0 && rows.length > 0) {
            for (var c = 0; c < rows[0].length; c++) {
                cols.push("列 " + (c + 1));
            }
        }
        for (var i = 0; i < cols.length; i++) {
            var th = safeEl("th", cols[i]);
            headerRow.appendChild(th);
        }
        thead.appendChild(headerRow);
        table.appendChild(thead);

        // 表体
        var tbody = document.createElement("tbody");
        for (var r = 0; r < rows.length; r++) {
            var tr = document.createElement("tr");
            var row = rows[r] || [];
            for (var ci = 0; ci < cols.length; ci++) {
                var td = document.createElement("td");
                var val = ci < row.length ? row[ci] : null;
                if (val === null || val === undefined || val === "") {
                    td.textContent = "—";
                    td.className = "null-value";
                } else {
                    td.textContent = String(val);
                }
                tr.appendChild(td);
            }
            tbody.appendChild(tr);
        }
        table.appendChild(tbody);

        preview.appendChild(table);
    };
})();
