# Data Cleaning, Analysis, Visualization Pipeline

面向业务数据分析与报表生成的端到端工程骨架，覆盖：

1. 数据加载：CSV、Excel、数据库，自动推断数据类型
2. 数据清洗：缺失值、去重、格式标准化、异常值检测
3. 探索分析：描述性统计、相关性分析、分布图
4. 洞察提取：使用 LLM 解读数据，发现趋势和异常
5. 报告生成：输出包含图表和分析结论的完整报告

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m src.cli run --config configs/default.yaml
```

启动 Web 报表应用：

```powershell
python -m src.cli web --host 127.0.0.1 --port 8000
```

浏览器打开 `http://127.0.0.1:8000`，可上传 CSV/Excel 并生成报告。

启用 LLM 洞察：

1. 复制 `.env.example` 为 `.env`
2. 填写 `OPENAI_API_KEY`
3. 在 `configs/default.yaml` 中设置 `llm.enabled: true`，或在 Web 页面勾选“启用 LLM 洞察”

## 目录概览

```text
.
├── configs/              # 运行配置、数据源配置、LLM 配置
├── data/                 # 原始数据、中间数据、清洗后数据
├── docs/                 # 设计文档、字段字典、业务口径
├── notebooks/            # 探索性分析笔记本
├── reports/              # 输出报告、图表、表格
├── scripts/              # 辅助脚本
├── src/                  # 主工程代码
├── tests/                # 单元测试与集成测试
└── pyproject.toml        # 项目依赖与工具配置
```
