# 数据仓库建模总规则

> 本文件从属于项目根 `AGENTS.md`。全局硬约束以根 `AGENTS.md` 为准。

## 1. 数据库设计文档是唯一事实源

数据库设计文档拥有最高优先级。其他文档可以暂时没有，数据库设计文档必须存在、可追溯、可审查、可复用。

当以下内容发生冲突时，以数据库设计文档为准：SQL 建表脚本、DuckDB 实际 schema、Excel 字段字典、Markdown 规划文档、Agent 生成的任何内容。

## 2. 分层规则

| 层 | Schema | 中文名 | 职责 | 规则文件 |
|---|---|---|---|---|
| Bronze | `bronze` | 青铜层/原始数据层 | 原始接入，保持原貌 | [bronze/AGENTS.md](bronze/AGENTS.md) |
| Silver | `silver` | 白银层/清洗数据层 | 标准化、去重、统一字段 | [silver/AGENTS.md](silver/AGENTS.md) |
| Gold | `gold` | 黄金层/业务数据层 | 主题星型模型、BI看板 | [gold/AGENTS.md](gold/AGENTS.md) |
| Meta | `meta` | 元数据层 | 质量监控、血缘追踪、中文语义 | 见根AGENTS.md第7节 |

分层依赖：Bronze(事实来源) → Silver(标准化，禁止凭空造字段) → Gold(业务建模，禁止跳过Silver直接引用Bronze) → Agent语义层

## 3. Schema变更流程

每次schema变更：提交PR → 更新数据库设计文档 → 更新字段字典 → 通过一致性检查 → 用户Review → 合入 → 同步开发库 → 同步所有线上库

冲突处理：文档与开发库不一致时不得向线上库同步。未经过数据库设计文档确认的字段变更直接驳回。

## 4. 数据真源优先级

1. Bronze实际字段(DESCRIBE / SELECT * LIMIT 10)
2. meta.source_columns(构建脚本自动生成)
3. 官方xlsx(仅用于枚举说明，不得确认字段是否存在)
4. 数据画像结果
5. 人工确认结果

## 5. 零幻觉建模

禁止编造：表名、字段名、字段含义、主键、外键、Join关系、金额、指标、KPI、业务规则、地理归属、业务口径。禁止根据xlsx推断Bronze表包含某字段。

## 6. 分层规则入口

- Bronze层 → [bronze/AGENTS.md](bronze/AGENTS.md)
- Silver层 → [silver/AGENTS.md](silver/AGENTS.md)
- Gold层 → [gold/AGENTS.md](gold/AGENTS.md)
- Text2SQL Agent → `../../agents/text2sql/AGENTS.md`
- Review Agent → `../../agents/review/AGENTS.md`
