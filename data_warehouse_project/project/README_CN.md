# 电信数据仓库 Agent 实验室

## 项目概述

本项目用于模拟一个可在个人电脑运行的企业级电信数据仓库，并作为 SQL 查询、指标解释、FastAPI、LangGraph Agent 和前端分析应用的长期实验室。

主要目标：

- 数据仓库建模实践
- SQL 开发实践
- ETL 流程设计
- FastAPI 服务开发
- LangGraph Agent 开发
- AI 驱动的数据分析

整个系统设计为可在个人电脑上独立运行。

------

## 系统架构

本地字段清单

↓

ODS（原始数据层）

↓

DWD（明细数据层）

↓

DWS（汇总数据层）

↓

ADS（应用数据层）

↓

FastAPI + LangGraph Agent

------

## 技术栈

- Python
- MySQL
- FastAPI
- LangGraph
- LangChain
- Next.js

------

## 项目目录结构

```text
docs/
data/
sql/
src/
tests/
```

## 知识档案

- [业务背景](docs/business_context.md)
- [字段字典](docs/data_dictionary.md)
- [指标字典](docs/metric_dictionary.md)
- [数据模型](docs/data_model.md)
- [系统架构](docs/system_architecture.md)
- [项目状态](docs/project_status.md)
- [建设过程总结](docs/data_warehouse_build_journey.md)
- [目录结构说明](docs/project_structure_guide_CN.md)

------

## 项目路线图

### 第一阶段：字段资产盘点

- 字段梳理与分析
- 数据字典建设
- 业务主题域划分

### 第二阶段：数据仓库建模

- 数仓模型设计
- ODS 层建设
- DWD 层建设
- DWS 层建设
- ADS 层建设

### 第三阶段：模拟数据与 ETL

- 模拟业务数据生成
- ETL 数据处理流水线建设

### 第四阶段：FastAPI 服务

- 数据查询接口开发
- 指标查询接口开发
- 数据服务能力建设

### 第五阶段：LangGraph Agent

- SQL Agent
- 指标分析 Agent
- 数据问答 Agent
- 智能分析 Agent

### 第六阶段：BI 可视化看板

- 核心指标展示
- 运营分析看板
- 用户分析看板
- Agent 分析结果展示

------

## 运行方式

当前已完成数仓建模、MySQL 建库建表、模拟数据生成、数据质量校验和项目目录归档。后续优先建设指标查询接口、SQL 生成服务和 Agent 工程能力。
