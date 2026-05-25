const form = document.querySelector("#analysisForm");
const statusPill = document.querySelector("#statusPill");
const fileInput = document.querySelector("#dataFile");
const fileName = document.querySelector("#fileName");
const metrics = document.querySelector("#metrics");
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
  if (spec.type === "correlation") return renderCorrelation(spec.data || []);
  return renderBars(spec.data || []);
}

function renderBars(data) {
  const width = 520, height = 260, pad = 34;
  const max = Math.max(...data.map((d) => Number(d.value) || 0), 1);
  const barGap = 8;
  const barWidth = Math.max(10, (width - pad * 2) / Math.max(data.length, 1) - barGap);
  const bars = data.map((d, i) => {
    const value = Number(d.value) || 0;
    const h = (height - pad * 2) * value / max;
    const x = pad + i * (barWidth + barGap);
    const y = height - pad - h;
    const label = String(d.label ?? "").slice(0, 9);
    return `<rect x="${x}" y="${y}" width="${barWidth}" height="${h}" rx="3" fill="#176b87"></rect>
      <text x="${x + barWidth / 2}" y="${height - 10}" text-anchor="middle" font-size="10" fill="#65727e">${escapeHtml(label)}</text>`;
  }).join("");
  return `<svg viewBox="0 0 ${width} ${height}" role="img">
    <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="#ccd7df"></line>
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

