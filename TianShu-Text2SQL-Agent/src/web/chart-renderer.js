/* ═══════════════════════════════════════════════════════════════
 * Phase 7 —— chart-renderer.js
 *
 * 原生 SVG 图表渲染器——严格消费后端 ChartSpec，不做业务推断。
 *
 * 支持图表类型：
 *   - line   : 原生 SVG 折线图
 *   - bar    : 原生 SVG 柱状图
 *   - metric_card : 指标卡
 *   - table  : 表格预览
 *   - 降级   : 未知/异常类型降级为 table
 *
 * 安全约束：
 *   - 不自行推断业务含义
 *   - 不修改数值
 *   - 不推断因果关系
 *   - 异常时降级不消失
 *   - SVG 包含 aria-label
 * ═══════════════════════════════════════════════════════════════ */

(function () {
    "use strict";

    var C = window.TianShuChartRenderer = window.TianShuChartRenderer || {};

    // ── 颜色方案（青蓝系冷调，按星枢设计体系）──
    var COLORS = [
        "#4870A3", "#2D6A4F", "#6366F1", "#0E7490",
        "#7C3AED", "#059669", "#2563EB", "#0D9488",
        "#4F46E5", "#0284C7", "#6D28D9", "#0891B2",
    ];

    // ── SVG 配置 ──
    var SVG_WIDTH = 700;
    var SVG_HEIGHT = 350;
    var PADDING = { top: 40, right: 30, bottom: 60, left: 60 };

    /**
     * 安全获取文本（textContent 方式）
     * @param {*} val
     * @returns {string}
     */
    function safeStr(val) {
        if (val === null || val === undefined) { return "—"; }
        return String(val);
    }

    /**
     * 解析数值（非数值返回 NaN）
     * @param {*} val
     * @returns {number}
     */
    function parseNum(val) {
        if (val === null || val === undefined) { return NaN; }
        if (typeof val === "number" && !isNaN(val)) { return val; }
        if (typeof val === "string") {
            var n = parseFloat(val);
            return n;
        }
        return NaN;
    }

    /**
     * 主入口：按 chart_type 分发渲染
     * @param {object} spec - ChartSpec 对象
     * @param {HTMLElement} container - 渲染目标容器
     */
    C.renderChart = function (spec, container) {
        if (!container) { return; }

        // 清空
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }

        var chartType = (spec && spec.chart_type) ? spec.chart_type : "table";
        console.log("chart-renderer: renderChart 被调用, chart_type=" + chartType + ", spec keys=" + (spec ? Object.keys(spec).join(",") : "null"));

        // ── 降级检查 ──
        if (!spec || !spec.chart_type) {
            console.warn("chart-renderer: chart_type 缺失，降级为表格");
            C._renderFallbackTable(spec, container, "chart_type 缺失，降级为表格");
            return;
        }

        // 空数据 → table
        var dataPreview = spec.data_preview || [];
        if (dataPreview.length === 0 && chartType !== "metric_card") {
            console.warn("chart-renderer: 数据为空，降级为表格");
            C._renderFallbackTable(spec, container, "数据为空，降级为表格");
            return;
        }

        // warnings 禁止展示 → table
        var warnings = spec.warnings || [];
        for (var i = 0; i < warnings.length; i++) {
            if (warnings[i] && (warnings[i].indexOf("禁止") >= 0 || warnings[i].toLowerCase().indexOf("refusal") >= 0)) {
                C._renderFallbackTable(spec, container, "图表展示被禁止: " + warnings[i]);
                return;
            }
        }

        // ── 按类型分发 ──
        try {
            switch (chartType) {
                case "line":
                    C.renderLineChart(spec, container);
                    break;
                case "bar":
                    C.renderBarChart(spec, container);
                    break;
                case "metric_card":
                    C.renderMetricCard(spec, container);
                    break;
                case "table":
                    C.renderTableChart(spec, container);
                    break;
                default:
                    C._renderFallbackTable(spec, container, "未知 chart_type: " + chartType);
            }
        } catch (e) {
            // 渲染异常 → 降级 table
            C._renderFallbackTable(spec, container, "SVG 渲染异常，降级为表格");
        }
    };

    /**
     * 渲染折线图（原生 SVG）
     * @param {object} spec
     * @param {HTMLElement} container
     */
    C.renderLineChart = function (spec, container) {
        var series = spec.series || [];
        var title = spec.title || "";
        var xField = spec.x_field || "x";

        if (series.length === 0) {
            C._renderFallbackTable(spec, container, "series 缺失，降级为表格");
            return;
        }

        // ── 收集所有 x 值和 y 值范围 ──
        var allX = [];
        var yMin = Infinity, yMax = -Infinity;
        for (var s = 0; s < series.length; s++) {
            var sData = series[s];
            var xArr = sData.x || [];
            var yArr = sData.y || [];
            if (xArr.length !== yArr.length) {
                C._renderFallbackTable(spec, container, "series[" + s + "] x/y 长度不一致，降级为表格");
                return;
            }
            for (var j = 0; j < yArr.length; j++) {
                var yv = parseNum(yArr[j]);
                if (!isNaN(yv)) {
                    if (yv < yMin) { yMin = yv; }
                    if (yv > yMax) { yMax = yv; }
                }
            }
            if (xArr.length > 0) {
                allX = xArr.slice();  // 取第一组的 x 值
            }
        }

        if (allX.length === 0) {
            C._renderFallbackTable(spec, container, "无有效数据点，降级为表格");
            return;
        }

        if (!isFinite(yMin) || !isFinite(yMax)) {
            yMin = 0; yMax = 1;
        }
        if (yMin === yMax) {
            yMin = yMin - 1;
            yMax = yMax + 1;
        }

        var chartW = SVG_WIDTH - PADDING.left - PADDING.right;
        var chartH = SVG_HEIGHT - PADDING.top - PADDING.bottom;
        var xStep = chartW / Math.max(allX.length - 1, 1);

        // ── Y 轴刻度 ──
        var yTickCount = 5;
        var yTicks = [];
        for (var t = 0; t <= yTickCount; t++) {
            yTicks.push(yMin + (yMax - yMin) * t / yTickCount);
        }

        function xToSvg(i) { return PADDING.left + i * xStep; }
        function yToSvg(yv) { return PADDING.top + chartH - (yv - yMin) / (yMax - yMin) * chartH; }

        // ── 构建 SVG ──
        var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("viewBox", "0 0 " + SVG_WIDTH + " " + SVG_HEIGHT);
        svg.setAttribute("width", "100%");
        svg.setAttribute("height", String(SVG_HEIGHT));
        svg.setAttribute("role", "img");
        svg.setAttribute("aria-label", title + "（折线图）");

        // 标题
        var titleEl = document.createElementNS("http://www.w3.org/2000/svg", "text");
        titleEl.setAttribute("x", String(SVG_WIDTH / 2));
        titleEl.setAttribute("y", "24");
        titleEl.setAttribute("text-anchor", "middle");
        titleEl.setAttribute("font-size", "14");
        titleEl.setAttribute("font-weight", "600");
        titleEl.setAttribute("fill", "#171C33");  /* 墨蓝 */
        titleEl.textContent = title;
        svg.appendChild(titleEl);

        // ── X 轴 ──
        var xAxis = document.createElementNS("http://www.w3.org/2000/svg", "line");
        xAxis.setAttribute("x1", String(PADDING.left));
        xAxis.setAttribute("y1", String(PADDING.top + chartH));
        xAxis.setAttribute("x2", String(PADDING.left + chartW));
        xAxis.setAttribute("y2", String(PADDING.top + chartH));
        xAxis.setAttribute("stroke", "#DFE4ED");  /* 霜线 */
        xAxis.setAttribute("stroke-width", "1");
        svg.appendChild(xAxis);

        // X 轴标签（每隔 max 7 个点显示）
        var xLabelStep = Math.max(1, Math.ceil(allX.length / 7));
        for (var xi = 0; xi < allX.length; xi += xLabelStep) {
            var xLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
            xLabel.setAttribute("x", String(xToSvg(xi)));
            xLabel.setAttribute("y", String(PADDING.top + chartH + 20));
            xLabel.setAttribute("text-anchor", "middle");
            xLabel.setAttribute("font-size", "11");
            xLabel.setAttribute("fill", "#6B7A90");  /* 石墨 */
            xLabel.textContent = safeStr(allX[xi]);
            svg.appendChild(xLabel);
        }

        // ── Y 轴 ──
        var yAxis = document.createElementNS("http://www.w3.org/2000/svg", "line");
        yAxis.setAttribute("x1", String(PADDING.left));
        yAxis.setAttribute("y1", String(PADDING.top));
        yAxis.setAttribute("x2", String(PADDING.left));
        yAxis.setAttribute("y2", String(PADDING.top + chartH));
        yAxis.setAttribute("stroke", "#DFE4ED");  /* 霜线 */
        yAxis.setAttribute("stroke-width", "1");
        svg.appendChild(yAxis);

        // Y 轴刻度和网格线
        for (var yt = 0; yt < yTicks.length; yt++) {
            var yPos = yToSvg(yTicks[yt]);
            // 网格线
            var gridLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
            gridLine.setAttribute("x1", String(PADDING.left));
            gridLine.setAttribute("y1", String(yPos));
            gridLine.setAttribute("x2", String(PADDING.left + chartW));
            gridLine.setAttribute("y2", String(yPos));
            gridLine.setAttribute("stroke", "#EBEEF4");  /* 浅霜线 */
            gridLine.setAttribute("stroke-width", "1");
            svg.appendChild(gridLine);

            // 标签
            var yLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
            yLabel.setAttribute("x", String(PADDING.left - 8));
            yLabel.setAttribute("y", String(yPos + 4));
            yLabel.setAttribute("text-anchor", "end");
            yLabel.setAttribute("font-size", "11");
            yLabel.setAttribute("fill", "#6B7A90");  /* 石墨 */
            yLabel.textContent = yTicks[yt].toFixed(0);
            svg.appendChild(yLabel);
        }

        // ── 数据折线 ──
        for (var si = 0; si < series.length; si++) {
            var color = COLORS[si % COLORS.length];
            var sData = series[si];
            var yArr = sData.y || [];

            // 构建路径点
            var points = "";
            for (var pi = 0; pi < allX.length; pi++) {
                var yv = parseNum(yArr[pi]);
                if (isNaN(yv)) { continue; }
                var px = xToSvg(pi);
                var py = yToSvg(yv);
                points += (pi === 0 ? "M" : "L") + px.toFixed(1) + "," + py.toFixed(1) + " ";
            }

            if (points) {
                // 折线
                var path = document.createElementNS("http://www.w3.org/2000/svg", "path");
                path.setAttribute("d", points);
                path.setAttribute("fill", "none");
                path.setAttribute("stroke", color);
                path.setAttribute("stroke-width", "2");
                path.setAttribute("stroke-linejoin", "round");
                svg.appendChild(path);

                // 数据点
                for (var di = 0; di < allX.length; di++) {
                    var dyv = parseNum(yArr[di]);
                    if (isNaN(dyv)) { continue; }
                    var dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                    dot.setAttribute("cx", String(xToSvg(di).toFixed(1)));
                    dot.setAttribute("cy", String(yToSvg(dyv).toFixed(1)));
                    dot.setAttribute("r", "3");
                    dot.setAttribute("fill", color);
                    svg.appendChild(dot);
                }
            }
        }

        // ── 图例 ──
        if (series.length > 0) {
            var legendContainer = document.createElement("div");
            legendContainer.className = "chart-legend";
            for (var li = 0; li < series.length; li++) {
                var item = document.createElement("span");
                item.className = "chart-legend-item";
                var colorDot = document.createElement("span");
                colorDot.className = "chart-legend-color";
                colorDot.style.backgroundColor = COLORS[li % COLORS.length];
                item.appendChild(colorDot);
                var nameSpan = document.createElement("span");
                nameSpan.textContent = safeStr(series[li].name || "系列 " + (li + 1));
                item.appendChild(nameSpan);
                legendContainer.appendChild(item);
            }
            container.appendChild(svg);
            container.appendChild(legendContainer);
        } else {
            container.appendChild(svg);
        }

        // ── 数据来源 ──
        if (spec.source) {
            var sourceEl = document.createElement("p");
            sourceEl.textContent = "数据来源: " + spec.source;
            sourceEl.style.cssText = "font-size:0.8rem;color:var(--color-text-muted);text-align:center;margin-top:8px;";
            container.appendChild(sourceEl);
        }
    };

    /**
     * 渲染柱状图（原生 SVG）
     * @param {object} spec
     * @param {HTMLElement} container
     */
    C.renderBarChart = function (spec, container) {
        var series = spec.series || [];
        var title = spec.title || "";

        if (series.length === 0) {
            C._renderFallbackTable(spec, container, "series 缺失，降级为表格");
            return;
        }

        // 取第一组 x 值
        var firstSeries = series[0];
        var categories = firstSeries.x || [];
        var yValues = firstSeries.y || [];

        if (categories.length === 0) {
            C._renderFallbackTable(spec, container, "无类别数据，降级为表格");
            return;
        }

        // 数值范围
        var yMin = 0, yMax = -Infinity;
        for (var s = 0; s < series.length; s++) {
            var yArr = series[s].y || [];
            for (var j = 0; j < yArr.length; j++) {
                var yv = parseNum(yArr[j]);
                if (!isNaN(yv) && yv > yMax) { yMax = yv; }
            }
        }
        if (!isFinite(yMax)) { yMax = 1; }

        var chartW = SVG_WIDTH - PADDING.left - PADDING.right;
        var chartH = SVG_HEIGHT - PADDING.top - PADDING.bottom;
        var barGroupWidth = chartW / Math.max(categories.length, 1);
        var barWidth = Math.min(barGroupWidth / (series.length + 1), 40);

        // Y 轴刻度
        var yTickCount = 5;
        var yTicks = [];
        for (var t = 0; t <= yTickCount; t++) {
            yTicks.push(yMin + (yMax - yMin) * t / yTickCount);
        }

        function barX(catIdx, seriesIdx) {
            var groupStart = PADDING.left + catIdx * barGroupWidth;
            var offset = (seriesIdx - (series.length - 1) / 2) * barWidth;
            return groupStart + barGroupWidth / 2 + offset - barWidth / 2;
        }
        function barY(yv) { return PADDING.top + chartH - (yv - yMin) / (yMax - yMin) * chartH; }
        function barH(yv) { return (yv - yMin) / (yMax - yMin) * chartH; }

        var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("viewBox", "0 0 " + SVG_WIDTH + " " + SVG_HEIGHT);
        svg.setAttribute("width", "100%");
        svg.setAttribute("height", String(SVG_HEIGHT));
        svg.setAttribute("role", "img");
        svg.setAttribute("aria-label", title + "（柱状图）");

        // 标题
        var titleEl = document.createElementNS("http://www.w3.org/2000/svg", "text");
        titleEl.setAttribute("x", String(SVG_WIDTH / 2));
        titleEl.setAttribute("y", "24");
        titleEl.setAttribute("text-anchor", "middle");
        titleEl.setAttribute("font-size", "14");
        titleEl.setAttribute("font-weight", "600");
        titleEl.setAttribute("fill", "#171C33");  /* 墨蓝 */
        titleEl.textContent = title;
        svg.appendChild(titleEl);

        // X 轴
        var xAxis = document.createElementNS("http://www.w3.org/2000/svg", "line");
        xAxis.setAttribute("x1", String(PADDING.left));
        xAxis.setAttribute("y1", String(PADDING.top + chartH));
        xAxis.setAttribute("x2", String(PADDING.left + chartW));
        xAxis.setAttribute("y2", String(PADDING.top + chartH));
        xAxis.setAttribute("stroke", "#e0dcd5");
        xAxis.setAttribute("stroke-width", "1");
        svg.appendChild(xAxis);

        // X 轴标签
        var xLabelStep = Math.max(1, Math.ceil(categories.length / 10));
        for (var ci = 0; ci < categories.length; ci += xLabelStep) {
            var cx = PADDING.left + ci * barGroupWidth + barGroupWidth / 2;
            var xLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
            xLabel.setAttribute("x", String(cx));
            xLabel.setAttribute("y", String(PADDING.top + chartH + 20));
            xLabel.setAttribute("text-anchor", "middle");
            xLabel.setAttribute("font-size", "11");
            xLabel.setAttribute("fill", "#5a6577");
            xLabel.textContent = safeStr(categories[ci]);
            svg.appendChild(xLabel);
        }

        // Y 轴
        var yAxis = document.createElementNS("http://www.w3.org/2000/svg", "line");
        yAxis.setAttribute("x1", String(PADDING.left));
        yAxis.setAttribute("y1", String(PADDING.top));
        yAxis.setAttribute("x2", String(PADDING.left));
        yAxis.setAttribute("y2", String(PADDING.top + chartH));
        yAxis.setAttribute("stroke", "#DFE4ED");  /* 霜线 */
        yAxis.setAttribute("stroke-width", "1");
        svg.appendChild(yAxis);

        for (var yt = 0; yt < yTicks.length; yt++) {
            var yPos = barY(yTicks[yt]);
            var gridLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
            gridLine.setAttribute("x1", String(PADDING.left));
            gridLine.setAttribute("y1", String(yPos));
            gridLine.setAttribute("x2", String(PADDING.left + chartW));
            gridLine.setAttribute("y2", String(yPos));
            gridLine.setAttribute("stroke", "#EBEEF4");  /* 浅霜线 */
            gridLine.setAttribute("stroke-width", "1");
            svg.appendChild(gridLine);

            var yLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
            yLabel.setAttribute("x", String(PADDING.left - 8));
            yLabel.setAttribute("y", String(yPos + 4));
            yLabel.setAttribute("text-anchor", "end");
            yLabel.setAttribute("font-size", "11");
            yLabel.setAttribute("fill", "#6B7A90");  /* 石墨 */
            yLabel.textContent = yTicks[yt].toFixed(0);
            svg.appendChild(yLabel);
        }

        // 柱子
        for (var si = 0; si < series.length; si++) {
            var color = COLORS[si % COLORS.length];
            var yArr = series[si].y || [];
            for (var bi = 0; bi < Math.min(categories.length, yArr.length); bi++) {
                var yv = parseNum(yArr[bi]);
                if (isNaN(yv)) { yv = 0; }
                var bx = barX(bi, si);
                var bh = barH(yv);
                var by = barY(yv);

                var rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
                rect.setAttribute("x", String(bx.toFixed(1)));
                rect.setAttribute("y", String(by.toFixed(1)));
                rect.setAttribute("width", String(barWidth.toFixed(1)));
                rect.setAttribute("height", String(Math.max(bh, 0).toFixed(1)));
                rect.setAttribute("fill", color);
                rect.setAttribute("rx", "2");
                svg.appendChild(rect);
            }
        }

        // 图例
        var legendContainer = document.createElement("div");
        legendContainer.className = "chart-legend";
        for (var li = 0; li < series.length; li++) {
            var item = document.createElement("span");
            item.className = "chart-legend-item";
            var colorDot = document.createElement("span");
            colorDot.className = "chart-legend-color";
            colorDot.style.backgroundColor = COLORS[li % COLORS.length];
            item.appendChild(colorDot);
            var nameSpan = document.createElement("span");
            nameSpan.textContent = safeStr(series[li].name || "系列 " + (li + 1));
            item.appendChild(nameSpan);
            legendContainer.appendChild(item);
        }
        container.appendChild(svg);
        container.appendChild(legendContainer);

        if (spec.source) {
            var sourceEl = document.createElement("p");
            sourceEl.textContent = "数据来源: " + spec.source;
            sourceEl.style.cssText = "font-size:0.8rem;color:var(--color-text-muted);text-align:center;margin-top:8px;";
            container.appendChild(sourceEl);
        }
    };

    /**
     * 渲染指标卡
     * @param {object} spec
     * @param {HTMLElement} container
     */
    C.renderMetricCard = function (spec, container) {
        var title = spec.title || "指标";
        var yFields = spec.y_fields || [];
        var dataPreview = spec.data_preview || [];

        var card = document.createElement("div");
        card.className = "metric-card";

        var nameEl = document.createElement("div");
        nameEl.className = "metric-name";
        nameEl.textContent = title;
        card.appendChild(nameEl);

        // 从 data_preview 中提取指标值
        var metricValue = "—";
        if (dataPreview.length > 0 && dataPreview[0].length > 0) {
            var val = dataPreview[0][dataPreview[0].length - 1]; // 取最后一列（数值列）
            if (val !== null && val !== undefined) {
                var nv = parseNum(val);
                if (!isNaN(nv)) {
                    metricValue = nv.toLocaleString("zh-CN");
                } else {
                    metricValue = safeStr(val);
                }
            }
        }

        var valueEl = document.createElement("div");
        valueEl.className = "metric-value";
        valueEl.textContent = metricValue;
        card.appendChild(valueEl);

        if (spec.source) {
            var sourceEl = document.createElement("div");
            sourceEl.className = "metric-source";
            sourceEl.textContent = "来源: " + spec.source;
            card.appendChild(sourceEl);
        }

        // 警告
        if (spec.warnings && spec.warnings.length > 0) {
            for (var wi = 0; wi < spec.warnings.length; wi++) {
                var warnEl = document.createElement("div");
                warnEl.textContent = "⚠ " + spec.warnings[wi];
                warnEl.style.cssText = "font-size:0.75rem;margin-top:8px;opacity:0.8;";
                card.appendChild(warnEl);
            }
        }

        container.appendChild(card);
    };

    /**
     * 渲染表格类型
     * @param {object} spec
     * @param {HTMLElement} container
     */
    C.renderTableChart = function (spec, container) {
        if (window.TianShuRenderers && window.TianShuRenderers.renderTablePreview) {
            window.TianShuRenderers.renderTablePreview(
                spec.columns || [],
                spec.data_preview || []
            );
        }

        if (spec.source) {
            var sourceEl = document.createElement("p");
            sourceEl.textContent = "数据来源: " + spec.source;
            sourceEl.style.cssText = "font-size:0.8rem;color:var(--color-text-muted);margin-top:8px;";
            container.appendChild(sourceEl);
        }
    };

    /**
     * 降级渲染为表格
     * @param {object} spec
     * @param {HTMLElement} container
     * @param {string} reason - 降级原因
     */
    C._renderFallbackTable = function (spec, container, reason) {
        // 添加降级提示
        var warnEl = document.createElement("p");
        warnEl.textContent = reason;
        warnEl.style.cssText = "font-size:0.8rem;color:var(--color-warning);margin-bottom:8px;font-style:italic;";
        container.appendChild(warnEl);

        // 渲染表格预览
        if (spec && spec.data_preview) {
            C.renderTableChart(spec, container);
        }
    };
})();
