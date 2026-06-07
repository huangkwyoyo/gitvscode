# 数据库设计文档

本目录是本项目的**最高事实源**。当以下内容冲突时，以本目录中的文档为准：
- SQL 建表脚本
- DuckDB 实际 schema
- Excel 字段字典
- Markdown 规划文档
- Agent 生成的任何内容

## 文档清单

| 文档 | 说明 | 状态 |
|---|---|---|
| `bronze_database_design.md` | Bronze 层 16 张表的正式设计 | 待创建 |
| `silver_database_design.md` | Silver 层 11 张表的正式设计 | 待创建 |
| `gold_database_design.md` | Gold 层星型模型正式设计 | 待创建 |

## 变更流程

每次 schema 变更必须：
1. 更新对应层的 database_design 文档
2. 更新 data_dictionary 字段字典
3. 通过一致性检查
4. PR Review 后才能合入
