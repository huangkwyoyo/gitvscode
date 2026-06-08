# Schema 变更审核清单

任何表结构、字段、主键、类型、注释或指标口径变化，都必须按本清单审核。

## 变更说明

- [ ] 说明变更类型：新增、删除、改名、类型变化、主键变化、派生逻辑变化。
- [ ] 说明变更原因。
- [ ] 说明影响范围：Bronze、Silver、Gold、Meta、Text2SQL、报告或下游应用。

## 事实源同步

- [ ] 已更新 `docs/warehouse/database_design/`。
- [ ] 已更新 `docs/warehouse/data_dictionary/` 或对应字典生成脚本。
- [ ] 已更新相关单表规划文档。
- [ ] 已更新 `PROJECT_STATUS.md`。
- [ ] 如属于经验沉淀，已更新 `docs/memory/`。

## 自动检查

- [ ] 已运行 `python scripts\quality\run_all_checks.py`。
- [ ] 如果检查失败，已说明失败原因。
- [ ] 如果失败原因是环境问题，例如 DuckDB 被占用，已记录并重跑。

## 驳回条件

出现以下情况直接驳回：

- [ ] 新字段没有来源字段或派生逻辑。
- [ ] 使用官方 xlsx 推断 Bronze 存在某字段。
- [ ] 字段代码、缩写或状态值没有中文含义且未标记 `Human Review`。
- [ ] SQL、xlsx、Markdown、数据库设计文档字段数不一致。
- [ ] Gold 跳过 Silver 直接引用 Bronze 建正式模型。
