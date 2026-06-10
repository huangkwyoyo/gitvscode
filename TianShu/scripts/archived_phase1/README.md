# 阶段一数据勘探脚本（已归档）

归档时间：2026-06-10

## 退役原因

这两个脚本是项目阶段一（"手工作坊"阶段）的数据侦察工具。当时面对一批陌生的 parquet/CSV 文件，需要暴力扫描来理解数据结构——扫描表名、字段名、数据类型、缺失率、数据域归属。

它们的产出物（全域数据规范.xlsx、可行性评估.md、完整性分析报告.md、中文名映射字典）已经迁移到正式体系：

| 原产出 | 现在的正式等价物 |
|---|---|
| 全域数据规范 xlsx | `docs/warehouse/database_design/` + `docs/warehouse/data_dictionary/` |
| Agent 基座可行性评估 | `PROJECT_STATUS.md` + 各层 AGENTS.md |
| 数据完整性分析报告 | `harness/` 质量门禁（自动运行，不再输出静态文档） |
| 字段中文名映射 | `docs/warehouse/data_dictionary/` 正式字段字典 |

## 归档后保留原因

1. 它们是**可复现的勘探记录**——未来如有新数据源接入，可修改 `BASE_DIR` 后重新运行，快速获得新数据的首次侦察报告
2. 包含的领域知识（字段映射、数据域分类逻辑）是后续正式体系的起点

## 使用方法（仅在新数据源接入时）

```bash
# 修改脚本中的 BASE_DIR 指向新数据目录，然后：
python scripts/archived_phase1/generate_nyc_transport_docs.py
python scripts/archived_phase1/optimize_programdata_nyc_transport_docs.py
```

这两个脚本不在活跃构建管线中，不需要随 schema 变更而维护。
