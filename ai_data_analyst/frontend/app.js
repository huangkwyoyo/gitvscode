/* ── 全局引用与事件绑定 ── */
const form = document.querySelector("#analysisForm");
const statusPill = document.querySelector("#statusPill");
const fileInput = document.querySelector("#dataFile");
const fileName = document.querySelector("#fileName");
const metrics = document.querySelector("#metrics");
const financeMetrics = document.querySelector("#financeMetrics");
const insights = document.querySelector("#insights");
const charts = document.querySelector("#charts");
const previewTable = document.querySelector("#previewTable");
const reportLink = document.querySelector("#reportLink");
const resultSubtitle = document.querySelector("#resultSubtitle");
const historyList = document.querySelector("#historyList");

let currentResult = null;

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.target));
});

document.querySelector("#refreshJobs").addEventListener("click", loadHistory);

fileInput.addEventListener("change", () => {
  fileName.textContent = fileInput.files[0]?.name || "拖入或点击选择文件";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = form.querySelector(".primary");
  submit.disabled = true;
  setStatus("分析中");
  animateStepper();
  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      body: new FormData(form),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "分析失败");
    currentResult = data;
    renderResult(data);
    setStatus(data.errors?.length ? "有错误" : "已完成");
    switchView("result");
    loadHistory();
  } catch (error) {
    setStatus("失败");
    alert(error.message);
  } finally {
    submit.disabled = false;
  }
});

function switchView(id) {
  document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === id));
  document.querySelectorAll(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.target === id));
}

function setStatus(text) {
  statusPill.textContent = text;
}

function animateStepper() {
  document.querySelectorAll("#stepper div").forEach((step, index) => {
    step.classList.remove("done");
    setTimeout(() => step.classList.add("done"), index * 250);
  });
}

function renderResult(data) {
  resultSubtitle.textContent = `${data.filename} · ${data.schema.rows} 行 · ${data.schema.columns} 列`;
  reportLink.href = data.report_url;
  reportLink.classList.toggle("hidden", !data.report_url);

  metrics.innerHTML = [
    ["原始行数", data.schema.rows],
    ["字段数", data.schema.columns],
    ["清洗后行数", data.quality.rows_after],
    ["完整度", `${Math.round((data.quality.completeness || 0) * 1000) / 10}%`],
  ].map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value ?? "-"}</strong></div>`).join("");

  renderFinanceMetrics(data.finance_metrics || {});

  insights.classList.remove("empty");
  insights.innerHTML = (data.insights || []).map((item) => `<div class="insight">${escapeHtml(item)}</div>`).join("") || "暂无洞察";

  charts.innerHTML = "";
  (data.chart_specs || []).forEach((spec) => {
    const card = document.createElement("div");
    card.className = "chart-card";
    card.innerHTML = `<h3>${escapeHtml(spec.title)}</h3>${renderChart(spec)}`;
    charts.appendChild(card);
  });

  renderPreview(data.preview_rows || []);
}

function renderFinanceMetrics(fm) {
  const container = financeMetrics;
  container.innerHTML = "";
  const entries = Object.entries(fm);
  if (!entries.length) {
    container.classList.add("hidden");
    return;
  }
  container.classList.remove("hidden");

  entries.forEach(([key, m]) => {
    const items = [
      ["年化收益率", m.annualized_return, "pct", "ret"],
      ["累计收益率", m.cumulative_return, "pct", "ret"],
      ["年化波动率", m.annualized_volatility, "pct", null],
      ["夏普比率", m.sharpe_ratio, "num", null],
      ["最大回撤", m.max_drawdown, "pct", "dd"],
      ["Calmar比率", m.calmar_ratio, "num", null],
    ];
    if (m.excess_return != null) {
      items.push(["超额收益率", m.excess_return, "pct", "ret"]);
    }
    const cards = items.map(([label, value, fmt, mood]) => {
      let display = "--";
      if (value != null) {
        if (fmt === "pct") display = (value * 100).toFixed(2) + "%";
        else display = value.toFixed(2);
      }
      let color = "";
      if (mood === "ret") color = value > 0 ? "color:var(--ok)" : "color:var(--danger)";
      if (mood === "dd") color = "color:var(--danger)";
      return `<div class="metric"><span>${label}</span><strong style="${color}">${display}</strong></div>`;
    }).join("");

    const dd = m.drawdown_info;
    let ddHtml = "";
    if (dd) {
      ddHtml = `
        <div class="drawdown-detail">
          <span>峰值 ${dd.peak_date}</span>
          <span>→ 谷底 ${dd.trough_date}</span>
          <span>持续 ${dd.drawdown_days} 天</span>
          ${dd.recovered ? `<span>恢复于 ${dd.recovery_date} (${dd.recovery_days} 天)</span>` : `<span>⚠ 尚未恢复</span>`}
        </div>`;
    }

    container.insertAdjacentHTML("beforeend",
      `<div class="finance-block"><h3>${escapeHtml(m.field)} <small>${m.start_date} ~ ${m.end_date}</small></h3><div class="metrics">${cards}</div>${ddHtml}</div>`);
  });
}

function renderPreview(rows) {
  if (!rows.length) {
    previewTable.innerHTML = "";
    return;
  }
  const columns = Object.keys(rows[0]);
  previewTable.innerHTML = `
    <thead><tr>${columns.map((col) => `<th>${escapeHtml(col)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((row) => `<tr>${columns.map((col) => `<td>${escapeHtml(row[col])}</td>`).join("")}</tr>`).join("")}</tbody>
  `;
}

function renderChart(spec) {
  switch (spec.type) {
    case "line": return renderLineChart(spec.data || [], spec.format);
    case "area": return renderAreaChart(spec.data || [], spec.format);
    case "multiline": return renderMultiLineChart(spec.data || {}, spec.format);
    case "correlation": return renderCorrelation(spec.data || []);
    default: return renderBars(spec.data || []);
  }
}

function renderBars(data) {
  const W = 520, H = 260, pad = 34;
  const max = Math.max(...data.map((d) => Number(d.value) || 0), 1);
  const barGap = 8;
  const barWidth = Math.max(10, (W - pad * 2) / Math.max(data.length, 1) - barGap);
  const bars = data.map((d, i) => {
    const value = Number(d.value) || 0;
    const h = (H - pad * 2) * value / max;
    const x = pad + i * (barWidth + barGap);
    const y = H - pad - h;
    const label = String(d.label ?? "").slice(0, 9);
    return `<rect x="${x}" y="${y}" width="${barWidth}" height="${h}" rx="3" fill="#176b87"></rect>
      <text x="${x + barWidth / 2}" y="${H - 10}" text-anchor="middle" font-size="10" fill="#65727e">${escapeHtml(label)}</text>`;
  }).join("");
  return `<svg viewBox="0 0 ${W} ${H}" role="img">
    <line x1="${pad}" y1="${H - pad}" x2="${W - pad}" y2="${H - pad}" stroke="#ccd7df"></line>
    ${bars}
  </svg>`;
}

function renderCorrelation(data) {
  const rows = data.map((d) => {
    const width = Math.min(100, Math.abs(Number(d.value) || 0) * 100);
    const color = Number(d.value) >= 0 ? "#176b87" : "#bf3b3b";
    return `<div class="corr-row">
      <span>${escapeHtml(d.x)} ↔ ${escapeHtml(d.y)}</span>
      <i style="width:${width}%;background:${color}"></i>
      <b>${d.value}</b>
    </div>`;
  }).join("");
  return `<div class="corr-chart">${rows || "暂无相关性数据"}</div>
    <style>.corr-row{display:grid;grid-template-columns:140px 1fr 50px;gap:8px;align-items:center;margin:10px 0;font-size:12px}.corr-row i{display:block;height:10px;border-radius:99px}.corr-row b{text-align:right}</style>`;
}

/* ── Financial line / area charts ── */

function _chartLayout(data) {
  const W = 520, H = 260;
  const pad = { top: 20, right: 20, bottom: 40, left: 50 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;
  const ys = data.map((d) => Number(d.value) || 0);
  const yMin = Math.min(0, ...ys);
  const yMax = Math.max(...ys, yMin + 0.001);
  const yRange = yMax - yMin || 1;
  const xScale = (i) => pad.left + (i / Math.max(data.length - 1, 1)) * plotW;
  const yScale = (v) => pad.top + plotH - ((v - yMin) / yRange) * plotH;
  return { W, H, pad, plotW, plotH, yMin, yMax, yRange, xScale, yScale, ys };
}

function _formatPct(v) { return (v * 100).toFixed(1) + "%"; }
function _formatNum(v) { return Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 1 ? v.toFixed(1) : v.toFixed(3); }

function _yAxisTicks(yMin, yMax, yRange, plotH, yScale) {
  const steps = 5;
  const ticks = [];
  for (let i = 0; i <= steps; i++) {
    const v = yMin + (yRange * i) / steps;
    ticks.push({ v, y: yScale(v), label: _formatNum(v) });
  }
  return ticks;
}

function renderLineChart(data, fmt) {
  if (!data.length) return "<p>数据不足</p>";
  const L = _chartLayout(data);
  const fmtFn = fmt === "pct" ? _formatPct : _formatNum;

  const points = data.map((d, i) => `${L.xScale(i)},${L.yScale(Number(d.value) || 0)}`).join(" ");
  const zeroY = L.yScale(0);

  const ticks = _yAxisTicks(L.yMin, L.yMax, L.yRange, L.plotH, L.yScale);
  const yAxis = ticks.map((t) =>
    `<text x="${L.pad.left - 6}" y="${t.y + 4}" text-anchor="end" font-size="10" fill="#65727e">${t.label}</text>`
  ).join("");

  const xLabels = _xAxisLabels(data, L);

  return `<svg viewBox="0 0 ${L.W} ${L.H}" role="img">
    <line x1="${L.pad.left}" y1="${zeroY}" x2="${L.W - L.pad.right}" y2="${zeroY}" stroke="#ccd7df" stroke-dasharray="4,3" />
    ${yAxis}
    <polyline points="${points}" fill="none" stroke="#176b87" stroke-width="2" />
    ${xLabels}
  </svg>`;
}

function renderAreaChart(data, fmt) {
  if (!data.length) return "<p>数据不足</p>";
  const L = _chartLayout(data);

  let pathD = "";
  const zeroY = L.yScale(0);
  data.forEach((d, i) => {
    const x = L.xScale(i);
    const y = L.yScale(Number(d.value) || 0);
    pathD += (i === 0 ? `M${x},${y}` : `L${x},${y}`);
  });
  const lastX = L.xScale(data.length - 1);
  pathD += `L${lastX},${zeroY} L${L.xScale(0)},${zeroY} Z`;

  const ticks = _yAxisTicks(L.yMin, L.yMax, L.yRange, L.plotH, L.yScale);
  const yAxis = ticks.map((t) =>
    `<text x="${L.pad.left - 6}" y="${t.y + 4}" text-anchor="end" font-size="10" fill="#65727e">${t.label}</text>`
  ).join("");

  const xLabels = _xAxisLabels(data, L);

  return `<svg viewBox="0 0 ${L.W} ${L.H}" role="img">
    <line x1="${L.pad.left}" y1="${zeroY}" x2="${L.W - L.pad.right}" y2="${zeroY}" stroke="#ccd7df" />
    ${yAxis}
    <path d="${pathD}" fill="#176b8720" stroke="#176b87" stroke-width="1.5" />
    ${xLabels}
  </svg>`;
}

function renderMultiLineChart(seriesMap, fmt) {
  const keys = Object.keys(seriesMap);
  if (!keys.length) return "<p>数据不足</p>";

  const colors = ["#176b87", "#bf3b3b", "#b7791f", "#16885a"];
  let allData = [];
  keys.forEach((key) => { allData = allData.concat(seriesMap[key] || []); });
  if (!allData.length) return "<p>数据不足</p>";

  const L = _chartLayout(allData);

  const ticks = _yAxisTicks(L.yMin, L.yMax, L.yRange, L.plotH, L.yScale);
  const yAxis = ticks.map((t) =>
    `<text x="${L.pad.left - 6}" y="${t.y + 4}" text-anchor="end" font-size="10" fill="#65727e">${t.label}</text>`
  ).join("");

  const zeroY = L.yScale(0);

  let lines = "";
  keys.forEach((key, ki) => {
    const data = seriesMap[key] || [];
    if (!data.length) return;
    const points = data.map((d, i) => `${L.xScale(i)},${L.yScale(Number(d.value) || 0)}`).join(" ");
    lines += `<polyline points="${points}" fill="none" stroke="${colors[ki % colors.length]}" stroke-width="2" />`;
  });

  let legend = "";
  keys.forEach((key, ki) => {
    legend += `<span style="display:inline-flex;align-items:center;gap:4px;margin-right:12px;font-size:11px;"><i style="width:12px;height:3px;display:inline-block;background:${colors[ki % colors.length]};border-radius:2px;"></i>${escapeHtml(key)}</span>`;
  });

  const xLabels = _xAxisLabels(allData, L);

  return `<div style="margin-bottom:8px">${legend}</div>
    <svg viewBox="0 0 ${L.W} ${L.H}" role="img">
    <line x1="${L.pad.left}" y1="${zeroY}" x2="${L.W - L.pad.right}" y2="${zeroY}" stroke="#ccd7df" stroke-dasharray="4,3" />
    ${yAxis}
    ${lines}
    ${xLabels}
  </svg>`;
}

function _xAxisLabels(data, L) {
  const n = data.length;
  if (n <= 1) return "";
  const maxLabels = 6;
  const step = Math.max(1, Math.floor((n - 1) / (maxLabels - 1)));
  let labels = "";
  for (let i = 0; i < n; i += step) {
    const label = String(data[i].date ?? data[i].label ?? "").slice(0, 10);
    labels += `<text x="${L.xScale(i)}" y="${L.H - 8}" text-anchor="middle" font-size="9" fill="#65727e">${escapeHtml(label)}</text>`;
  }
  return labels;
}

async function loadHistory() {
  const response = await fetch("/api/jobs");
  const jobs = await response.json();
  historyList.innerHTML = jobs.map((job) => `
    <div class="history-item">
      <div><strong>${escapeHtml(job.filename)}</strong><p>${job.rows ?? "-"} 行 · ${job.columns ?? "-"} 列</p></div>
      ${job.report_url ? `<a class="secondary" target="_blank" href="${job.report_url}">报告</a>` : ""}
    </div>
  `).join("") || `<div class="panel empty">暂无任务</div>`;
}

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loadHistory();
