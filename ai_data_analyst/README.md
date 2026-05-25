# AI Data Analyst

可扩展的数据分析工具 MVP：上传 CSV/Excel，输入分析需求，自动完成数据加载、清洗、探索分析、可视化、洞察提取和 HTML 报告生成。

## 架构选择

本项目采用“LangGraph 风格”的确定性工作流内核：

- 每个分析步骤都是独立节点，输入输出进入统一 `AnalysisState`
- 数据处理使用 pandas/numpy，保证结果可复现
- LLM 只负责解释与总结，不参与不可控的数据改写
- 后续可以把 `app/workflow.py` 替换为 LangGraph 的 StateGraph

## 快速启动

```bash
cd ai_data_analyst
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000
```

## 功能

- CSV / Excel 数据上传
- 分析需求文字输入，支持额外上传文本需求文档
- 自动类型推断、缺失值处理、去重、异常值检测
- 描述性统计、相关性分析、字段质量评分
- 自动生成图表规格，由前端渲染
- 规则洞察 + 可选 OpenAI 兼容 LLM 洞察
- HTML 报告导出

## 可选 LLM 配置

不配置也能完整运行本地分析。需要 LLM 洞察时设置：

```bash
set OPENAI_API_KEY=你的key
set OPENAI_BASE_URL=https://api.openai.com/v1
set OPENAI_MODEL=gpt-4.1-mini
```

