# Code Review Fixes — AI Data Analyst 优化

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Superpowers 代码审查发现的 Critical 和 Important 级问题，优化代码生产就绪度。

**Architecture:** 分 4 个阶段执行 — 先修复确定性的 Bug（C1-C5），再加固生产基础设施（异步处理/并发安全/日志），然后补齐运维能力（持久化/健康检查），最后处理设计改进。每个阶段可独立验证。

**Tech Stack:** Python 3.12, FastAPI, pandas, numpy, pytest

---

### Task 1: 修复 `_detect_frequency` 短序列错误默认日频（C1）

**Files:**
- Modify: `ai_data_analyst/app/services/finance_metrics.py:31-32`
- Modify: `ai_data_analyst/app/services/finance_metrics.py:353-432` (compute_finance_metrics)
- Modify: `ai_data_analyst/tests/test_finance_metrics.py` (新增测试)

- [ ] **Step 1: 修改 `_detect_frequency` — 短序列不再武断默认日频**

将 `ai_data_analyst/app/services/finance_metrics.py` 第 31-32 行：
```python
    if len(dates) < 10:
        return "daily"  # 数据太少时默认日频
```

替换为：
```python
    if len(dates) < 10:
        return "insufficient"  # 数据不足，保守处理以避免年化失真
```

- [ ] **Step 2: 添加 `"insufficient"` 频率的年化乘数**

在 `ai_data_analyst/app/services/finance_metrics.py` 第 22 行 `FREQUENCY_MULTIPLIER` 字典中添加：
```python
FREQUENCY_MULTIPLIER = {
    "daily": 252,
    "weekly": 52,
    "monthly": 12,
    "quarterly": 4,
    "insufficient": 0,  # 数据不足时不进行年化计算
}
```

- [ ] **Step 3: 修改 `_get_trading_days` — 对 insufficient 返回 0**

将 `ai_data_analyst/app/services/finance_metrics.py` 第 54-59 行：
```python
def _get_trading_days(frequency: str) -> int:
    """根据频率返回对应的年化交易日乘数。"""
    if frequency in FREQUENCY_MULTIPLIER:
        return FREQUENCY_MULTIPLIER[frequency]
    # 季度频等特殊频率使用 4 次/年
    return 4
```

替换为：
```python
def _get_trading_days(frequency: str) -> int:
    """根据频率返回对应的年化交易日乘数。"""
    return FREQUENCY_MULTIPLIER.get(frequency, 4)
```

- [ ] **Step 4: 修改 `compute_finance_metrics` — 不足时不计算年化指标**

在 `ai_data_analyst/app/services/finance_metrics.py` 的 `compute_finance_metrics` 函数中，第 374 行 `frequency = _detect_frequency(dates)` 之后，添加逻辑跳过不足数据的年化计算。在第 377 行 `ann_ret = annualized_return(nav, dates, frequency)` 替换为：
```python
        if frequency == "insufficient":
            ann_ret = None
            ann_vol = None
            sharpe = None
            sortino = None
            rolling = {}
        else:
            ann_ret = annualized_return(nav, dates, frequency)
            ann_vol = annualized_volatility(nav, frequency)
            sharpe = sharpe_ratio(nav, dates, frequency=frequency)
            sortino = sortino_ratio(nav, dates, frequency=frequency)
            rolling = rolling_returns(nav, dates, frequency)
```

同时相应地调整后面第 376-384 行中使用这些变量的代码。

- [ ] **Step 5: 添加测试用例**

在 `ai_data_analyst/tests/test_finance_metrics.py` 的 `TestDetectFrequency` 类末尾添加：
```python
    def test_insufficient_data_points(self):
        """测试数据不足 10 个点时返回 'insufficient' 而非武断默认日频。"""
        dates = pd.Series(pd.date_range("2023-01-01", periods=5, freq="MS"))
        assert _detect_frequency(dates) == "insufficient"
```

在文件末尾添加新测试类：
```python
class TestInsufficientDataSkipsAnnualization:
    """数据不足时跳过所有年化计算，避免失真。"""

    def test_short_series_skips_annualized_return(self, tmp_path):
        """8 个月度数据点不应使用日频年化乘数 252。"""
        import numpy as np
        dates = pd.date_range("2023-01-01", periods=8, freq="MS")
        nav = pd.Series([1.0, 1.01, 1.02, 1.03, 1.04, 1.05, 1.06, 1.07], index=dates)
        df = pd.DataFrame({"date": dates, "nav": nav})
        from app.services.finance_metrics import compute_finance_metrics
        result = compute_finance_metrics(df, "date", ["nav"])
        assert result["nav"]["annualized_return"] is None
        assert result["nav"]["sharpe_ratio"] is None
```

- [ ] **Step 6: 运行测试验证**

```bash
cd "D:/Program Files/gitvscode" && python -m pytest ai_data_analyst/tests/test_finance_metrics.py -v
```

Expected: 所有测试 PASS，含新增的 `test_insufficient_data_points` 和 `TestInsufficientDataSkipsAnnualization`。

- [ ] **Step 7: Commit**

```bash
git add ai_data_analyst/app/services/finance_metrics.py ai_data_analyst/tests/test_finance_metrics.py
git commit -m "fix(ai_data_analyst): 修复短序列数据年化失真 — <10点不再默认日频"
```

---

### Task 2: 修复 CSV 加载仅支持 utf-8-sig 编码（C2）

**Files:**
- Modify: `ai_data_analyst/app/services/adapters/file_adapter.py:16-22`

- [ ] **Step 1: 修改 `FileDataSourceAdapter.load()` 添加多编码支持**

将 `ai_data_analyst/app/services/adapters/file_adapter.py` 第 16-22 行：
```python
    def load(self, source: Path) -> pd.DataFrame:
        suffix = source.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(source, encoding="utf-8-sig")
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(source)
        raise ValueError("仅支持 CSV、XLSX、XLS 文件")
```

替换为：
```python
    # CSV 编码尝试顺序：utf-8-sig（Excel 默认导出）> utf-8 > gbk（中文 Windows）> gb2312
    _CSV_ENCODINGS = ["utf-8-sig", "utf-8", "gbk", "gb2312"]

    def load(self, source: Path) -> pd.DataFrame:
        suffix = source.suffix.lower()
        if suffix == ".csv":
            for encoding in self._CSV_ENCODINGS:
                try:
                    return pd.read_csv(source, encoding=encoding)
                except (UnicodeDecodeError, UnicodeError):
                    continue
            # 所有编码都失败时，用最常用的编码尝试并让异常自然抛出
            return pd.read_csv(source, encoding="utf-8-sig")
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(source)
        raise ValueError("仅支持 CSV、XLSX、XLS 文件")
```

- [ ] **Step 2: 运行现有测试验证不破坏已有功能**

```bash
cd "D:/Program Files/gitvscode" && python -m pytest ai_data_analyst/tests/ -v
```

Expected: 所有现有测试 PASS。

- [ ] **Step 3: Commit**

```bash
git add ai_data_analyst/app/services/adapters/file_adapter.py
git commit -m "fix(ai_data_analyst): CSV加载支持多编码自动检测 — utf-8-sig/utf-8/gbk/gb2312"
```

---

### Task 3: 修复 `str.strip()` 字符范围 Bug（C3）

**Files:**
- Modify: `ai_data_analyst/app/services/insights.py:113`

- [ ] **Step 1: 修复 strip 字符集，将 `-` 移到末尾**

将 `ai_data_analyst/app/services/insights.py` 第 113 行：
```python
        llm_lines = [line.strip(" -0123456789.、") for line in text.splitlines() if line.strip()]
```

替换为：
```python
        # 注意：strip() 参数中 - 在字符中间会形成 ASCII 范围，必须放在开头或末尾
        llm_lines = [line.strip(" 0123456789.、-") for line in text.splitlines() if line.strip()]
```

- [ ] **Step 2: 验证修改**

```bash
cd "D:/Program Files/gitvscode" && python -c "
# 验证 strip 不会吃掉标点符号
line = '1. 2024年营收增长20%！(超预期)'
result = line.strip(' 0123456789.、-')
print(f'输入: {repr(line)}')
print(f'输出: {repr(result)}')
assert '!' in result, '感叹号被错误删除了！'
assert '(' in result, '括号被错误删除了！'
print('验证通过')
"
```

Expected: 断言通过，"验证通过"。

- [ ] **Step 3: Commit**

```bash
git add ai_data_analyst/app/services/insights.py
git commit -m "fix(ai_data_analyst): 修复LLM洞察strip()字符范围Bug — -移至末尾避免误删标点"
```

---

### Task 4: 修复异常值检测 `std == 0` 除零问题（C5）

**Files:**
- Modify: `ai_data_analyst/app/services/cleaning.py:82-88`

- [ ] **Step 1: 添加 std 保护条件**

将 `ai_data_analyst/app/services/cleaning.py` 第 81-86 行：
```python
        std = series.std()
        if not np.isnan(std):
            z = ((series - series.mean()) / std).abs()
            count = int((z > 3).sum())
```

替换为：
```python
        std = series.std()
        if std > 0 and not np.isnan(std):
            z = ((series - series.mean()) / std).abs()
            count = int((z > 3).sum())
```

- [ ] **Step 2: 运行测试验证**

```bash
cd "D:/Program Files/gitvscode" && python -m pytest ai_data_analyst/tests/ -v
```

Expected: 所有测试 PASS，无 numpy 除零警告。

- [ ] **Step 3: Commit**

```bash
git add ai_data_analyst/app/services/cleaning.py
git commit -m "fix(ai_data_analyst): 异常值检测添加std>0保护，避免常量列除零"
```

---

### Task 5: 修复异步端点同步阻塞（Arch-C1）

**Files:**
- Modify: `ai_data_analyst/app/main.py:110`

- [ ] **Step 1: 导入 asyncio 并使用 to_thread 包装工作流**

将 `ai_data_analyst/app/main.py` 第 1 行之后添加：
```python
import asyncio
```

将第 110 行：
```python
    state = workflow.run(state)
```

替换为：
```python
    state = await asyncio.to_thread(workflow.run, state)
```

- [ ] **Step 2: 运行测试验证**

```bash
cd "D:/Program Files/gitvscode" && python -m pytest ai_data_analyst/tests/ -v
```

Expected: 所有测试 PASS（workflow 测试应继续正常工作）。

- [ ] **Step 3: Commit**

```bash
git add ai_data_analyst/app/main.py
git commit -m "fix(ai_data_analyst): 异步端点使用to_thread避免阻塞事件循环"
```

---

### Task 6: 修复 JOBS 并发竞态（Bug-C4）

**Files:**
- Modify: `ai_data_analyst/app/main.py:37-43, 111-112`

- [ ] **Step 1: 添加 threading.Lock 保护 JOBS**

将 `ai_data_analyst/app/main.py` 第 2 行之后添加 `threading` 导入：
```python
import threading
```

将第 37-38 行：
```python
workflow = AnalysisWorkflow()
JOBS: OrderedDict[str, AnalysisState] = OrderedDict()
```

替换为：
```python
workflow = AnalysisWorkflow()
JOBS: OrderedDict[str, AnalysisState] = OrderedDict()
_JOBS_LOCK = threading.Lock()
```

将 `_evict_old_jobs()` 函数（第 41-43 行）修改为不内部加锁（调用方负责加锁）。

将 `analyze()` 端点中第 110-112 行：
```python
    state = await asyncio.to_thread(workflow.run, state)
    _evict_old_jobs()
    JOBS[job_id] = state
```

替换为：
```python
    state = await asyncio.to_thread(workflow.run, state)
    with _JOBS_LOCK:
        _evict_old_jobs()
        JOBS[job_id] = state
```

将 `list_jobs()` 端点中第 116-128 行的列表推导式用 `with _JOBS_LOCK:` 包裹。

将 `get_job()` 端点中第 132-136 行的 `JOBS.get()` 用 `with _JOBS_LOCK:` 包裹。

- [ ] **Step 2: 运行测试验证**

```bash
cd "D:/Program Files/gitvscode" && python -m pytest ai_data_analyst/tests/ -v
```

Expected: 所有测试 PASS。

- [ ] **Step 3: Commit**

```bash
git add ai_data_analyst/app/main.py
git commit -m "fix(ai_data_analyst): JOBS字典添加threading.Lock防止并发竞态"
```

---

### Task 7: 添加结构化日志（I4）

**Files:**
- Create: `ai_data_analyst/app/services/logger.py`
- Modify: `ai_data_analyst/app/main.py`
- Modify: `ai_data_analyst/app/workflow.py`
- Modify: `ai_data_analyst/app/services/loader.py`
- Modify: `ai_data_analyst/app/services/cleaning.py`
- Modify: `ai_data_analyst/app/services/insights.py`

- [ ] **Step 1: 创建日志配置模块**

创建 `ai_data_analyst/app/services/logger.py`：
```python
"""统一的日志配置模块。"""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """获取带有统一格式的 logger 实例。"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
```

- [ ] **Step 2: 在工作流中添加日志**

在 `ai_data_analyst/app/workflow.py` 顶部添加：
```python
from app.services.logger import get_logger

logger = get_logger(__name__)
```

在 `run()` 方法的第 48 行 `for node_name, node in self.nodes:` 之后添加：
```python
            logger.info("执行节点: %s", node_name)
```

在 try 块中的 `state = node(state)` 之后添加：
```python
            logger.info("节点完成: %s", node_name)
```

- [ ] **Step 3: 在 main.py 中添加请求日志**

在 `ai_data_analyst/app/main.py` 中 `analyze` 端点开头添加：
```python
    logger = get_logger("app.api")
    logger.info("收到分析请求: file=%s, type=%s", data_file.filename, analysis_type)
```

- [ ] **Step 4: 运行测试验证**

```bash
cd "D:/Program Files/gitvscode" && python -m pytest ai_data_analyst/tests/ -v
```

Expected: 测试正常 PASS，控制台有 INFO 级别日志输出。

- [ ] **Step 5: Commit**

```bash
git add ai_data_analyst/app/services/logger.py ai_data_analyst/app/main.py ai_data_analyst/app/workflow.py
git commit -m "feat(ai_data_analyst): 添加结构化日志基础设施"
```

---

### Task 8: 添加健康检查端点 + 清理死代码 + 优化导入（M1/M2/M3）

**Files:**
- Modify: `ai_data_analyst/app/main.py` (添加 /api/health)
- Modify: `ai_data_analyst/app/services/reporting.py` (移除 state_json 死代码)
- Modify: `ai_data_analyst/app/services/utils.py` (safe_float 导入移到顶部)

- [ ] **Step 1: 添加健康检查端点**

在 `ai_data_analyst/app/main.py` 的 `list_jobs` 端点之前添加：
```python
@app.get("/api/health")
def health():
    """健康检查端点，返回服务状态。"""
    return {"status": "ok", "jobs_count": len(JOBS)}
```

- [ ] **Step 2: 移除 reporting.py 中未使用的 state_json**

将 `ai_data_analyst/app/services/reporting.py` 第 16-21 行：
```python
    html = template.render(
        title=f"{state.original_filename} 分析报告",
        state=state.public_payload(),
        state_json=json.dumps(state.public_payload(), ensure_ascii=False),
    )
```

替换为：
```python
    html = template.render(
        title=f"{state.original_filename} 分析报告",
        state=state.public_payload(),
    )
```

同时移除顶部未使用的 `import json`（第 3 行）。

- [ ] **Step 3: safe_float 的 numpy 导入移到模块顶部**

将 `ai_data_analyst/app/services/utils.py` 第 1-5 行：
```python
"""共享工具函数。"""
from __future__ import annotations
import pandas as pd
```

替换为：
```python
"""共享工具函数。"""
from __future__ import annotations
import numpy as np
import pandas as pd
```

将 `safe_float` 函数中的：
```python
    try:
        import numpy as np
        if isinstance(value, float) and np.isnan(value):
            return None
    except ImportError:
        pass
```

替换为：
```python
    if isinstance(value, float) and np.isnan(value):
        return None
```

- [ ] **Step 4: 运行测试验证**

```bash
cd "D:/Program Files/gitvscode" && python -m pytest ai_data_analyst/tests/ -v
```

Expected: 所有测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add ai_data_analyst/app/main.py ai_data_analyst/app/services/reporting.py ai_data_analyst/app/services/utils.py
git commit -m "chore(ai_data_analyst): 添加健康检查端点，移除死代码，优化safe_float导入"
```

---

### Task 9: `_save_upload` TOCTOU 修复 + 磁盘清理（I2 + I6）

**Files:**
- Modify: `ai_data_analyst/app/main.py:55-61`
- Modify: `ai_data_analyst/app/main.py` (添加清理函数)
- Modify: `ai_data_analyst/app/settings.py` (添加配置项)

- [ ] **Step 1: 添加磁盘清理配置**

在 `ai_data_analyst/app/settings.py` 末尾添加：
```python
# 磁盘清理配置
JOB_RETENTION_HOURS = int(os.getenv("JOB_RETENTION_HOURS", 24))  # 作业文件保留时间
```

- [ ] **Step 2: 改造 `_save_upload` 为流式大小检查**

将 `ai_data_analyst/app/main.py` 第 55-61 行：
```python
async def _save_upload(file: UploadFile, target: Path) -> None:
    with target.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    saved = target.stat().st_size
    if saved > MAX_UPLOAD_BYTES:
        target.unlink()
        raise HTTPException(status_code=413, detail="上传文件超过 50MB 限制")
```

替换为：
```python
async def _save_upload(file: UploadFile, target: Path) -> None:
    """流式保存上传文件，边写边检查大小，避免先写完整文件再校验的TOCTOU窗口。"""
    written = 0
    with target.open("wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 每次读 1MB
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                buffer.close()
                target.unlink()
                raise HTTPException(status_code=413, detail="上传文件超过 50MB 限制")
            buffer.write(chunk)
```

- [ ] **Step 3: 添加磁盘清理函数**

在 `ai_data_analyst/app/main.py` 的 `_evict_old_jobs` 函数之后添加：
```python
def _cleanup_old_files() -> None:
    """清理超出保留时间的上传和输出文件。"""
    import time
    from app.settings import JOB_RETENTION_HOURS
    cutoff = time.time() - JOB_RETENTION_HOURS * 3600
    for dir_path in [UPLOAD_DIR, OUTPUT_DIR]:
        for job_dir in dir_path.iterdir():
            if job_dir.is_dir() and job_dir.stat().st_mtime < cutoff:
                shutil.rmtree(job_dir, ignore_errors=True)
```

在 `analyze()` 端点的 `_evict_old_jobs()` 之后添加 `_cleanup_old_files()` 调用。

- [ ] **Step 4: 运行测试验证**

```bash
cd "D:/Program Files/gitvscode" && python -m pytest ai_data_analyst/tests/ -v
```

Expected: 所有测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add ai_data_analyst/app/main.py ai_data_analyst/app/settings.py
git commit -m "fix(ai_data_analyst): 流式上传大小检查 + 磁盘自动清理"
```

---

### Task 10: 工作流完成后释放 DataFrame 内存（Arch-C3）

**Files:**
- Modify: `ai_data_analyst/app/workflow.py:46-68`
- Modify: `ai_data_analyst/app/models.py`

- [ ] **Step 1: 在 `AnalysisState` 中添加清理方法**

在 `ai_data_analyst/app/models.py` 的 `AnalysisState` 类中添加方法（`public_payload` 方法之后）：
```python
    def release_dataframes(self) -> None:
        """释放 DataFrame 内存，工作流完成后调用。"""
        self.raw_df = None
        self.clean_df = None
```

- [ ] **Step 2: 在工作流完成后调用清理**

在 `ai_data_analyst/app/workflow.py` 的 `run()` 方法中，`return state` 之前（第 67 行）添加：
```python
        # 释放 DataFrame 内存，后续仅需 preview_rows 和 exploration 等聚合数据
        state.release_dataframes()
```

- [ ] **Step 3: 运行测试验证**

```bash
cd "D:/Program Files/gitvscode" && python -m pytest ai_data_analyst/tests/ -v
```

Expected: 所有测试 PASS。特别注意 `test_workflow_modes.py` 的集成测试应继续正常工作（它们只依赖聚合数据）。

- [ ] **Step 4: Commit**

```bash
git add ai_data_analyst/app/workflow.py ai_data_analyst/app/models.py
git commit -m "perf(ai_data_analyst): 工作流完成后释放DataFrame内存"
```

---

### Task 11: 最终验证

**Files:** (无修改，仅验证)

- [ ] **Step 1: 运行全部测试**

```bash
cd "D:/Program Files/gitvscode" && python -m pytest ai_data_analyst/tests/ -v
```

Expected: 全部 29 个测试 PASS。

- [ ] **Step 2: 检查导入完整性**

```bash
cd "D:/Program Files/gitvscode" && python -c "
from app.main import app
from app.workflow import AnalysisWorkflow
from app.models import AnalysisState
from app.services.loader import load_data
from app.services.cleaning import clean_data
from app.services.exploration import explore_data
from app.services.finance_metrics import compute_finance_metrics, _detect_frequency
from app.services.visualization import build_chart_specs
from app.services.insights import generate_insights
from app.services.reporting import generate_report
from app.services.logger import get_logger
print('所有模块导入成功')
"
```

Expected: "所有模块导入成功"。

- [ ] **Step 3: 查看最终 diff 摘要**

```bash
cd "D:/Program Files/gitvscode" && git diff --stat HEAD -- ai_data_analyst/
```
