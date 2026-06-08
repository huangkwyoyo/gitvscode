# 项目状态

## 当前阶段

Silver 层 11 张表全部建成（P0/P1/P2），~9,700 万行，质量门禁通过。准备进入 Gold 层。

## 最近完成

- [x] **Silver 层 11 张表全部建成**（`scripts/silver/build_silver_duckdb.py`）
- [x] Silver P0：dim_date(90行) + taxi_zone(265行) + trip_detail(8,032万行)
- [x] Silver P1：vehicle_detail(12万) + driver_detail(36万) + base_detail(5.9万) + driver_application_detail(4,076)
- [x] Silver P2：parking_violation_detail(958万) + tif_payment_detail(4.8万) + crash_detail(166万) + crash_person_detail(533万)
- [x] Meta 中文注释已写入：11 条表级 + 201 条字段级
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
- 官方原始 xlsx 继续放在 `D:/ProgramData/Datawarehouse/纽约市城市交通/官方数据字典/`，项目内只维护索引和抽取后的轻量说明。
- `docs/standards/` 只做规范索引入口，不重复维护 `database_design/` 和 `data_dictionary/` 的具体规范。
- `harness/` 只做 Harness 工程执行入口，不维护正式 schema、字段字典或经验复盘。
- 字段中的状态码、标志位、分类代码等枚举值必须补中文含义；无法确认时标记 `Human Review`。
- 每次文档、字段字典、SQL 或 schema 变更后，运行 `python scripts/quality/run_all_checks.py`。
- 运行 Harness 前需关闭占用 `nyc_transport.duckdb` 的桌面工具，例如 DBeaver；否则 DuckDB 读取检查会因文件锁失败。
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
| 官方数据字典索引 | `docs/warehouse/data_dictionary/README.md`（已合并） |
| 规范索引 | `docs/standards/` |
| 建模索引 | `docs/modeling/` |
| Harness 工程入口 | `harness/` |
| 数据字典 xlsx | `D:/ProgramData/Datawarehouse/纽约市城市交通/分析报告/` |
| Agent Memory | `docs/memory/` |
| Harness 统一检查入口 | `scripts/quality/run_all_checks.py` |
