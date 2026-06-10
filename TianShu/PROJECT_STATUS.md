# 项目状态

## 当前阶段

Silver 层 11 张表已完成修复并通过 post-Silver 强校验。Gold G0/G1 维表、G2 明细事实表、G3 汇总表和中文语义层已落库，并通过 Gold 设计门禁、物理表门禁、语义层门禁和空值画像检查。当前阶段进入标准中文问题集与 Agent Harness 封装验证（`harness/config/harness_targets.yml` 中的 `project.stage` 为 `gold_g3_semantic_layer`）。

## 最近完成

- [x] **Silver 层 11 张表全部建成**（`scripts/silver/build_silver_duckdb.py`）
- [x] Silver P0：dim_date(90行) + taxi_zone(265行) + trip_detail(8,032万行)
- [x] Silver P1：vehicle_detail(12万) + driver_detail(36万) + base_detail(5.9万) + driver_application_detail(4,076)
- [x] Silver P2：parking_violation_detail(958万) + tif_payment_detail(4.8万) + crash_detail(166万) + crash_person_detail(533万)
- [x] Meta 中文注释已写入：11 条表级 + 210 条字段级
- [x] Silver 层构建耗时 464 秒（trip_detail 466s，其余表均 < 5s）
- [x] Bronze 枚举值字典已完善（95 项 ✅，6 项 ⚠️，5 项 NYPD 遗留）
- [x] 枚举值识别方法论已建立（`docs/warehouse/data_dictionary/枚举值识别方法论.md`）
- [x] MV-104AN 编码手册 PDF 已验证（EasyOCR）
- [x] VEH 字段映射分析已完成
- [x] 质量门禁：字典一致性 ✅、危险模式 ✅、回归测试 6/6 ✅
- [x] Bronze 16 张表已导入 DuckDB（`nyc_transport.duckdb`）
- [x] Meta 元数据已生成（5 张物理表 + 3 个视图，table/column_comments 已写入）
- [x] Silver 层 11 张表规划文档已完成（`docs/silver/Silver白银层规划.md`）
- [x] 全局 AGENTS.md + 6 个分层 AGENTS.md 已创建
- [x] `scripts/quality/check_schema_consistency.py` 已实现
- [x] `scripts/quality/run_all_checks.py` 统一 Harness 检查入口已实现
- [x] `docs/warehouse/database_design/gold_database_design.md` 已创建为 Gold 设计入口
- [x] Harness 全量检查已通过（Silver 字典一致性、危险模式、schema 一致性、pytest）
- [x] Memory Gate 已接入 `run_all_checks.py`，关键变更必须同步更新 `docs/memory`
- [x] Silver 字段漂移已修复：数据库设计、Silver xlsx、DuckDB 实表、`meta.column_comments` 已一致
- [x] Silver 日期和金额转换已修复：美国日期、ISO 日期、TIF 美元金额不再因 `TRY_CAST` 静默失败而全 NULL
- [x] Gold 层数据库设计入口已升级为字段级方案草案，明确中文名来源、事实表粒度、维表来源和建设批次
- [x] Gold 设计门禁已接入：`scripts/quality/check_gold_design.py`
- [x] Gold G0/G1 维表已建设：`dim_date`、`dim_taxi_zone`、`dim_vehicle`、`dim_driver`、`dim_base`、`dim_violation_type`
- [x] Gold 物理表门禁已接入：`scripts/quality/check_gold_physical.py --batches G0,G1,G2`
- [x] Gold G0/G1 中文表注释和字段注释已写入 `meta.table_comments`、`meta.column_comments`
- [x] Gold G2 明细事实表已建设：`fact_trips`、`fact_parking_violations`、`fact_tif_payments`、`fact_driver_applications`、`fact_crashes`、`fact_crash_persons`
- [x] `fact_parking_violations.standard_fine_amount` 已通过 `dim_violation_type` 引入官方标准罚款金额
- [x] Gold G3 汇总表已建设：`dws_daily_trip_summary`、`dws_zone_trip_summary`、`dws_daily_parking_summary`、`dws_daily_crash_summary`
- [x] 中文语义层已建设：`meta.metric_definitions`、`meta.semantic_dimensions`、`meta.semantic_query_templates`、`meta.business_terms`
- [x] 标准中文问题集已接入：`harness/questions/gold_standard_questions.yml`
- [x] 语义层门禁已接入 Harness：`scripts/quality/check_semantic_layer.py`
- [x] `docs/standards/` 已调整为规范索引入口，不重复维护数据库设计或字段字典规范
- [x] `docs/modeling/README.md` 已调整为建模索引入口
- [x] 官方数据字典位置已登记到 `docs/warehouse/data_dictionary/README.md`
- [x] 字段字典规范已补充枚举值（状态码/标志位/分类代码）中文含义要求
- [x] `harness/` 工程执行入口已建立（README、检查清单、配置、报告入口、lessons 路由）
- [x] `Agent Memory + Warehouse Harness统一体系方案.md` 已补充“从散落脚本到 Harness 工程入口”的认知提升
- [x] Silver 实施前审查已完成：同步 `dim_date` 为固定生成 2026Q1 日期范围，重新生成 Silver 数据字典 xlsx，并通过 Harness 全量检查

## 下一步

1. [x] 补充 `docs/warehouse/database_design/` 正式设计文档 ✅
2. [x] 补充 `docs/warehouse/data_dictionary/` 正式字段字典 ✅
3. [x] 为 11 个 Silver 设计文档补充 source_type 字段来源分类列 ✅
4. [x] 修复 3 处中文类型残留 → 确认为 grep 误报，类型列均使用纯英文 ✅
5. [x] 实现 `scripts/quality/check_silver_dictionary.py` 检查脚本 ✅
6. [x] 实现 `scripts/quality/check_dangerous_patterns.py` 危险模式扫描 ✅
7. [x] 实现 `tests/test_silver_dictionary.py` 回归测试（6 个用例，6 passed） ✅
8. [x] 修复 `_gen_xlsx.py` 中字段数：trip_detail 39、parking_violation 33、tif_payment 12、crash 26、crash_person 23 ✅
9. [x] 启用 Silver 字段来源类型测试 ✅
10. [x] 实现 `scripts/quality/check_schema_consistency.py` ✅
11. [x] 实现 `scripts/quality/run_all_checks.py` ✅
12. [x] 生成并执行 Silver 建表脚本 ✅
13. [x] 执行 Silver 数据质量校验 ✅
14. [x] 进入 Gold 层数据库设计和星型模型落地方案 ✅
15. [x] 建设 Gold G0/G1 公共维表和业务维表 ✅
16. [x] 建设 Gold G2 明细事实表 ✅
17. [x] 建设 Gold G3 汇总表和中文语义层 ✅

## 阻塞点

无阻塞。post-Silver Harness 强校验、Gold G0/G1/G2/G3 门禁和中文语义层门禁已完成。

## 重要注意

- `parking_violations_all` 没有金额字段。金额需在 Gold 层通过 `violation_code` 关联 `dim_violation_type`（来自官方 xlsx）获取。
- DuckDB 禁用 `DATE::INT`，用 `strftime(d, '%Y%m%d')::INTEGER`。
- 禁用无序 `ROW_NUMBER() OVER ()` 生成主键，用 MD5 哈希。
- 枚举值以 `SELECT DISTINCT` 为准，不得硬编码。
- 官方 xlsx 只能补充枚举说明，不得用于确认字段存在性。
- 官方原始 xlsx 继续放在 `D:/ProgramData/Datawarehouse/纽约市城市交通/官方数据字典/`，项目内只维护索引和抽取后的轻量说明。
- `docs/standards/` 只做规范索引入口，不重复维护 `database_design/` 和 `data_dictionary/` 的具体规范。
- `harness/` 只做 Harness 工程执行入口，不维护正式 schema、字段字典或经验复盘。
- 字段中的状态码、标志位、分类代码等枚举值必须补中文含义；无法确认时标记 `Human Review`。
- 每次文档、字段字典、SQL 或 schema 变更后，运行 `python scripts/quality/run_all_checks.py`。
- 运行 Harness 前需关闭占用 `nyc_transport.duckdb` 的桌面工具，例如 DBeaver；否则 DuckDB 读取检查会因文件锁失败。
- 当前项目阶段已从 `gold_g2_build` 推进到 `gold_g3_semantic_layer`，schema 一致性检查仍必须启用 Silver 实表强校验。
- `check_silver_null.py` 会输出高缺失字段画像。高缺失不一定是错误，需结合源表适用范围判断；但全 NULL 的日期、金额字段必须优先排查转换逻辑。
- 当前 Harness 阶段为 `gold_g3_semantic_layer`，全量检查会同时执行 Gold 设计门禁、Gold G0/G1/G2/G3 物理门禁、中文语义层门禁和 Gold 空值画像。
- `gold.dim_violation_type` 的 `standard_fine_amount` 已从官方数据字典 Excel 导入（覆盖 97/100 个违章代码），`penalty_amount` 因 Excel 不含滞纳金数据保持 NULL。`source_status` 标记为 `from_official_dictionary` 或 `missing_from_dictionary`。

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
| 官方数据字典索引 | `docs/warehouse/data_dictionary/README.md`（已合并） |
| 规范索引 | `docs/standards/` |
| 建模索引 | `docs/modeling/` |
| Harness 工程入口 | `harness/` |
| 数据字典 xlsx | `D:/ProgramData/Datawarehouse/纽约市城市交通/分析报告/` |
| Agent Memory | `docs/memory/` |
| Harness 统一检查入口 | `scripts/quality/run_all_checks.py` |
