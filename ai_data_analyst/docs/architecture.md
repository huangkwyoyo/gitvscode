# 架构说明

## 为什么不用 CrewAI 做主框架

这个项目的核心是“可控的数据分析产品”，不是让多个角色自由对话。数据处理步骤必须可复现、可回放、可审计，所以主干采用确定性工作流。

推荐演进路线：

1. 当前版本：内置 `AnalysisWorkflow`，无额外依赖即可运行
2. 扩展版本：替换为 LangGraph `StateGraph`
3. 企业版本：增加任务队列、数据库、权限、报告历史和模型网关

## 工作流节点

```text
load_data
  -> clean_data
  -> explore_data
  -> visualize
  -> generate_insights
  -> generate_report
```

## 可扩展点

- 新数据源：新增 `DataSourceAdapter`，当前已实现 CSV/Excel/SQLite，本地数据库以 adapter 示例方式接入
- 新清洗策略：扩展 `app/services/cleaning.py`
- 新图表类型：扩展 `app/services/visualization.py` 和 `frontend/app.js`
- 新 LLM：替换 `app/services/insights.py` 中的 OpenAI 兼容调用
- LangGraph 接入：用节点函数复用现有 service，替换 `app/workflow.py`

## 多 Agent 对应关系

为了保留多 agent 的业务分工，本项目把 agent 角色映射为工作流节点：

- RequirementAgent：需求理解，当前由 `analysis_goal` 进入全局状态
- DataLoaderAgent：`load_data`
- DataCleanerAgent：`clean_data`
- ExploreAnalystAgent：`explore_data`
- VisualAnalystAgent：`visualize`
- InsightAgent：`generate_insights`
- ReportAgent：`generate_report`

这样既保留专业分工，又避免 LLM 随意改动数据处理逻辑。
