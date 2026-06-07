# 项目状态

## 当前阶段

Agent Memory + Warehouse Harness 最小闭环已完成，准备进入 Silver 建表阶段。

## 最近完成

- [x] Bronze 16 张表已导入 DuckDB（`nyc_transport.duckdb`）
- [x] Meta 元数据已生成（5 张物理表 + 3 个视图）
- [x] 全表数据字典已生成（15 张 Bronze 表 + Meta 层 8 个对象）
- [x] 指标口径定义已完成（出行/供给/安全/监管合规 4 大类）
- [x] Silver 层 11 张表规划文档已完成（`docs/silver/Silver白银层规划.md`）
- [x] Silver 层 11 张表详细设计文档已完成（`scripts/silver/`）
- [x] Silver 层数据字典 xlsx 已生成（12 sheet）
- [x] 全局 AGENTS.md 已升级至 v2（12 个规范章节 + 第一原则）
- [x] 6 个分层 AGENTS.md 已创建（warehouse/bronze/silver/gold + text2sql/review）
- [x] 发现并修复停车罚单虚构金额字段问题（6 个不存在的字段）
- [x] 发现并修复 dim_date DuckDB SQL 兼容问题（DATE::INT → strftime）
- [x] 发现并修复 trip_id 无序 ROW_NUMBER 问题（→ MD5 稳定哈希）
- [x] 发现并修复 driver_application 硬编码枚举问题（4 种 → 5 种实际值）
- [x] 发现并修复 crash_detail 弃用字段数错误（8 个 → 7 个）
- [x] 记忆系统三篇认知文档已输出到 Obsidian 知识库
- [x] `docs/memory/` 记忆层已落地（经验复盘、风险清单、规则来源索引、变更复盘模板）
- [x] Silver 数据字典 xlsx 已扩展字段来源列（字段来源类型、来源 Bronze 表、来源 Bronze 字段、派生逻辑、可信等级、审核状态）
- [x] `scripts/quality/check_schema_consistency.py` 已实现
- [x] `scripts/quality/run_all_checks.py` 统一 Harness 检查入口已实现
- [x] `docs/warehouse/database_design/gold_database_design.md` 已创建为 Gold 设计入口
- [x] Harness 全量检查已通过（Silver 字典一致性、危险模式、schema 一致性、pytest）

## 下一步

1. [x] 补充 `docs/warehouse/database_design/` 正式设计文档 ✅
2. [x] 补充 `docs/warehouse/data_dictionary/` 正式字段字典 ✅
3. [x] 为 11 个 Silver 设计文档补充 source_type 字段来源分类列 ✅
4. [x] 修复 3 处中文类型残留 → 确认为 grep 误报，类型列均使用纯英文 ✅
5. [x] 实现 `scripts/quality/check_silver_dictionary.py` 检查脚本 ✅
6. [x] 实现 `scripts/quality/check_dangerous_patterns.py` 危险模式扫描 ✅
7. [x] 实现 `tests/test_silver_dictionary.py` 回归测试（6 个用例，6 passed） ✅
8. [x] 修复 `_gen_xlsx.py` 中 trip_detail (42→39)、parking_violation (36→32)、crash (22→25)、crash_person (20→22) 字段数 ✅
9. [x] 启用 Silver 字段来源类型测试 ✅
10. [x] 实现 `scripts/quality/check_schema_consistency.py` ✅
11. [x] 实现 `scripts/quality/run_all_checks.py` ✅
12. [ ] 开始生成 Silver 建表 SQL
13. [ ] 执行 Silver 数据质量校验

## 阻塞点

无阻塞。Harness 最小闭环已完成。

## 重要注意

- `parking_violations_all` 没有金额字段。金额需在 Gold 层通过 `violation_code` 关联 `dim_violation_type`（来自官方 xlsx）获取。
- DuckDB 禁用 `DATE::INT`，用 `strftime(d, '%Y%m%d')::INTEGER`。
- 禁用无序 `ROW_NUMBER() OVER ()` 生成主键，用 MD5 哈希。
- 枚举值以 `SELECT DISTINCT` 为准，不得硬编码。
- 官方 xlsx 只能补充枚举说明，不得用于确认字段存在性。
- 每次文档、字段字典、SQL 或 schema 变更后，运行 `python scripts/quality/run_all_checks.py`。
- 当前 Silver 实表尚未建设，schema 一致性检查会跳过 Silver 实表对比；Silver 建表后需要启用实表一致性检查。

## 数据库位置

```
D:/ProgramData/Datawarehouse/纽约市城市交通/nyc_transport.duckdb
```

## 事实源文档位置

| 文档 | 路径 |
|---|---|
| 全局 Agent 规则 | `AGENTS.md` |
| 数据仓库总规则 | `docs/warehouse/AGENTS.md` |
| Bronze 层规则 | `docs/warehouse/bronze/AGENTS.md` |
| Silver 层规则 | `docs/warehouse/silver/AGENTS.md` |
| Gold 层规则 | `docs/warehouse/gold/AGENTS.md` |
| Silver 层规划 | `docs/silver/Silver白银层规划.md` |
| Silver 表设计文档 | `scripts/silver/` |
| 数据库设计文档 | `docs/warehouse/database_design/` |
| 字段字典 | `docs/warehouse/data_dictionary/` |
| 数据字典 xlsx | `D:/ProgramData/Datawarehouse/纽约市城市交通/分析报告/` |
| Agent Memory | `docs/memory/` |
| Harness 统一检查入口 | `scripts/quality/run_all_checks.py` |
