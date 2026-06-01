# 阶段计划

## 阶段 1：MySQL 数仓画像

目标：只读分析 `ods`、`dwd`、`dws`、`ads` 四个库，输出表清单、字段画像、样本摘要和表关系分析。

## 阶段 2：MySQL 口径业务过程材料生成

目标：按 `business_processes/bp_xxx/` 组织 10 个业务过程，每个过程包含需求、DDL、业务 SQL、校验 SQL、测试样例、血缘说明。

## 阶段 3：MySQL 到 Doris 迁移转换

目标：基于 `migration_rules/` 规则文件生成 Doris 版本 DDL/SQL 和转换报告，不覆盖 MySQL 原始材料。

## 阶段 4：WebSQL 调度集成

目标：WebSQL 只作为 SQL 执行入口和调度入口，复杂逻辑由 FastAPI/LangGraph 承载。

## 阶段 5：批次校验和报告生成

目标：每批输出执行报告、校验报告、异常报告，历史记录不得覆盖。
