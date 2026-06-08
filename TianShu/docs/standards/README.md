# 规范文档

本目录是 TianShu 项目的规范索引入口，用于把分散在 `AGENTS.md`、`docs/warehouse/`、`docs/warehouse/database_design/`、`docs/warehouse/data_dictionary/`、`docs/modeling/` 中的规范串起来。

项目级强制规则见根目录 `AGENTS.md`。本目录不替代 `AGENTS.md`，而是承接更详细的说明、模板和示例。

## 文档清单

| 文档 | 说明 | 状态 |
|---|---|---|
| `数据仓库文档规范.md` | 数据仓库规范索引，说明各类规范应该去哪里维护 | 已创建 |
| → `枚举值识别方法论` | 见 `docs/warehouse/data_dictionary/枚举值识别方法论.md` | 已创建 |
| → `Bronze层枚举值说明` | 见 `docs/warehouse/data_dictionary/bronze_enum_values.md` | 已创建 |

## 使用原则

- `AGENTS.md` 放必须遵守的硬规则。
- `docs/standards/` 只做规范索引和入口，不重复维护具体规范。
- `docs/warehouse/database_design/` 维护数据库设计事实源。
- `docs/warehouse/data_dictionary/` 维护字段字典、枚举值（状态码/标志位/分类代码）说明规范。
- `docs/warehouse/*/AGENTS.md` 维护分层建模规则。
- 数据库设计文档、字段字典、SQL、实际数据库 schema 发生冲突时，以 `docs/warehouse/database_design/` 中的正式设计文档为最高事实源。
- 所有面向中文用户和中文 Agent 的数据文档，必须同时保留英文技术名和中文业务名。
