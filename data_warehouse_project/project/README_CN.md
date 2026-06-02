# 电信数据仓库 Agent 实验室

本项目是一个可在个人电脑运行的企业级电信数据仓库模拟项目。它不是一次性建表脚本，而是一个长期实验室，用来练习 MySQL 数仓建模、Python ETL、指标体系、SQL 查询接口、FastAPI 服务、LangGraph Agent 和后续 Next.js 前端。

项目不追求生产级海量数据，但追求企业级结构、分层、命名、指标口径和业务逻辑真实感。

## 当前状态

已完成：

- 电信字段标准化设计。
- ODS、DWD、DWS、ADS 四层数仓建模。
- MySQL 建库建表 SQL。
- 接近真实业务逻辑的模拟数据生成。
- 数据质量校验报告。
- 项目目录重构和归档。
- 业务背景、指标字典、数据模型、系统架构、项目状态等知识档案。

下一阶段：

- 元数据读取模块。
- 只读 SQL 执行引擎。
- 指标目录服务。
- FastAPI 查询接口。
- LangGraph Agent 工作流。
- Next.js 前端。

## 总体架构

```text
本地业务字段资料
        |
        v
字段标准化与数仓建模
        |
        v
Python 数据生成与 ETL
        |
        v
MySQL: ods / dwd / dws / ads
        |
        v
指标目录与语义元数据
        |
        v
FastAPI + LangGraph Agent + Next.js
```

## 技术栈

- 数据库：MySQL
- 数据生成与 ETL：Python
- API 服务：FastAPI
- Agent 工作流：LangGraph
- LLM 应用层：兼容 LangChain 生态
- 前端：Next.js
- 配置：YAML 与 `.env`

## 项目目录

```text
telecom-dw-agent-lab/
├── AGENTS.md
├── README.md
├── README_CN.md
├── config/
│   ├── settings.yaml
│   ├── database.yaml
│   └── agent.yaml
├── data/
│   ├── raw/
│   ├── generated/
│   ├── exports/
│   └── logs/
├── docs/
│   ├── business_context.md
│   ├── data_dictionary.md
│   ├── metric_dictionary.md
│   ├── data_model.md
│   ├── system_architecture.md
│   ├── project_status.md
│   ├── data_warehouse_build_journey.md
│   └── project_structure_guide_CN.md
├── scripts/
│   └── generate_data.py
├── sql/
│   ├── create_dw_tables.sql
│   ├── ods/
│   ├── dwd/
│   ├── dws/
│   ├── ads/
│   └── checks/
├── src/
│   ├── telecom_dw/
│   └── frontend/
└── tests/
```

## 知识档案

- [业务背景](docs/business_context.md)：电信核心业务对象、主题域和分析场景。
- [字段字典](docs/data_dictionary.md)：标准字段、命名规则、字段含义和主题域。
- [指标字典](docs/metric_dictionary.md)：指标名称、口径、粒度、来源表和应用场景。
- [数据模型](docs/data_model.md)：ODS、DWD、DWS、ADS 分层模型和主外键关系。
- [系统架构](docs/system_architecture.md)：系统模块、服务规划和 Agent 流程。
- [项目状态](docs/project_status.md)：当前进度、约束和下一步任务。
- [建设过程总结](docs/data_warehouse_build_journey.md)：建仓过程、修正记录和经验。
- [目录结构说明](docs/project_structure_guide_CN.md)：目录职责和配置文件含义。

## MySQL 数仓分层

本项目使用 MySQL schema 作为数仓物理分层：

| 层级 | schema | 职责 |
|---|---|---|
| ODS | `ods` | 原始接入层，承载模拟源业务数据 |
| DWD | `dwd` | 明细数据层，承载清洗后的维度表和事实表 |
| DWS | `dws` | 汇总数据层，按主题域沉淀轻度汇总 |
| ADS | `ads` | 应用数据层，服务指标、报表和 Agent 查询 |

建库建表 SQL 位于：

```text
sql/create_dw_tables.sql
```

## 数据生成

主入口：

```powershell
python scripts/generate_data.py
```

生成数据落盘目录：

```text
data/generated/mysql_load/
```

这些文件体积较大，且可以重复生成，因此不进入 Git。

## Git 管理规则

以下资料只保留在本地，不推送 GitHub：

- `docs/telecom_fields.xlsx`
- `docs/telecom_dw_table_design.xlsx`
- `docs/telecom_dw_table_design_cn.xlsx`
- `data/generated/**`
- `data/raw/**`
- `data/exports/**`

GitHub 只归档源码、SQL、配置模板、文档和轻量级质量报告。

## 后续开发建议

1. 建设 `src/telecom_dw/metadata`，读取 MySQL 表结构和字段注释。
2. 建设 `src/telecom_dw/sql_engine`，实现只读 SQL 校验、超时和行数限制。
3. 建设 `src/telecom_dw/metrics`，把指标字典落入 ADS 指标目录。
4. 建设 FastAPI 元数据、指标、SQL 和 Agent 接口。
5. 建设 LangGraph 指标识别、SQL 生成、安全校验和结果解释流程。
6. 补齐数据质量、SQL 安全、指标口径和 Agent 行为测试。
