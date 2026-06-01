# 项目状态

## 当前阶段

项目已完成“数仓设计、建库建表、模拟数据生成、质量校验、目录重构和知识档案沉淀”的基础阶段。下一阶段应进入“指标服务、SQL 查询接口、FastAPI 和 LangGraph Agent”建设。

## 已完成

| 模块 | 状态 | 说明 |
|---|---|---|
| 字段标准化 | 已完成 | 已形成 `docs/data_dictionary.md` |
| 数仓分层设计 | 已完成 | 使用 `ods`、`dwd`、`dws`、`ads` 四个 MySQL schema |
| 建库建表 | 已完成 | 建表 SQL 已归档到 `sql/create_dw_tables.sql` |
| 模拟数据生成 | 已完成 | 已为 ODS、DWD、DWS、ADS 生成本地 MySQL 数据 |
| 数据质量校验 | 已完成 | 报告位于 `data/logs/data_quality_report.md` |
| 项目目录重构 | 已完成 | 已拆分 `config`、`docs`、`data`、`sql`、`src`、`tests` |
| Git 归档 | 已完成 | 已推送到 `codex/telecom-dw-project-archive` 分支 |
| 大文件排除 | 已完成 | 生成数据和本地 Excel 工作簿已加入 `.gitignore` |
| 知识文档 | 已补齐 | 已新增指标、模型、架构和状态文档 |

## 当前数据规模

| 层级 | 表数量 | 数据量说明 |
|---|---:|---|
| ODS | 31 张物理表 | 约 1208 万行 |
| DWD | 17 张表 | 约 1046 万行 |
| DWS | 8 张表 | 约 120 万行 |
| ADS | 9 张表 | 少量指标和语义目录样例 |

## 关键约束

- MySQL 使用本地连接，分层库名固定为 `ods`、`dwd`、`dws`、`ads`。
- 字段统一使用英文 `snake_case`，字段中文含义通过 comment 和文档表达。
- 表名不能使用源系统视图名，必须使用企业数仓语义命名。
- 业务时间必须位于用户入网和离网生命周期内。
- 订单创建时间、支付时间、业务时间必须精确到时分秒。
- 生成数据和本地 Excel 工作簿不推送 GitHub。

## 待建设

| 优先级 | 模块 | 目标 |
|---|---|---|
| P0 | 指标目录入库 | 将 `docs/metric_dictionary.md` 的核心指标同步到 ADS 指标目录 |
| P0 | SQL 只读执行器 | 提供安全 SQL 执行、超时、LIMIT 和风险拦截 |
| P1 | FastAPI 服务 | 暴露元数据、指标、SQL 查询和 Agent 接口 |
| P1 | LangGraph Agent | 支持自然语言查指标、解释口径、生成 SQL |
| P1 | 测试体系 | 增加数据质量、指标口径和 SQL 安全测试 |
| P2 | Next.js 前端 | 建设指标看板、SQL 工作台和 Agent 对话页面 |
| P2 | 流失风险规则 | 基于欠费、投诉、使用下降和套餐行为构建规则模型 |
| P2 | 营销人群圈选 | 支持按价值、地域、套餐、风险和行为筛选用户 |

## Git 状态

- 分支：`codex/telecom-dw-project-archive`
- 基础归档提交：`c24d2f61bb564b76a218d388ab77272917785458`
- 说明：基础归档提交已排除本地 Excel 工作簿和大规模生成数据。后续提交应继续遵守该规则。

## 下一步建议

1. 先建设 `src/telecom_dw/metadata`，读取 MySQL 表结构和中文注释。
2. 再建设 `src/telecom_dw/sql_engine`，实现只读 SQL 校验和执行。
3. 然后建设 `src/telecom_dw/metrics`，把指标字典落到 ADS 表。
4. 最后接入 FastAPI 和 LangGraph Agent，形成自然语言到指标查询的闭环。
