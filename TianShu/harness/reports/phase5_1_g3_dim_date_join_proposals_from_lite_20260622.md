# Phase 5.1 — G3→dim_date JOIN 契约变更建议

> 文档类型：契约变更提案（提交 TianShu Dev Agent 评审）
> 生成时间：2026-06-22 17:10
> 生成者：TianShu-Text2SQL-Lite Phase 5.1
> 基线提交：`7518a58`

## 1. 背景

TianShu-Text2SQL-Lite 的 `real_contracts_completeness` 检查发现，三个 G3 日度汇总表缺少与 `gold.dim_date` 的 JOIN 白名单注册。

当前 `sql_safety_policy.yml` 中已注册的 G2→dim_date JOIN（共 5 条）：

- `gold.fact_trips ↔ gold.dim_date (pickup_date_key / dropoff_date_key)`
- `gold.fact_parking_violations ↔ gold.dim_date (issue_date_key)`
- `gold.fact_crashes ↔ gold.dim_date (crash_date_key)`
- `gold.fact_tif_payments ↔ gold.dim_date (payment_date_key)`
- `gold.fact_driver_applications ↔ gold.dim_date (app_date_key)`

但对应的 G3 汇总表→dim_date JOIN 均未注册。G3 是优先查询层（语义契约规定 G3 > G2），缺少这些 JOIN 会导致 G3 日度查询被安全校验拒绝（fail-closed）。

## 2. 变更建议

**目标文件**：`TianShu/contracts/sql_safety_policy.yml`
**修改位置**：`table_reference_rules` → `join_whitelist` → `allowed_joins`
**操作**：在现有 8 条后追加 3 条

### 建议 1：dws_daily_trip_summary ↔ dim_date

```yaml
- "gold.dws_daily_trip_summary ↔ gold.dim_date (trip_date = date)"
```

| 项目 | 值 |
|------|-----|
| 左表 | `gold.dws_daily_trip_summary` |
| 右表 | `gold.dim_date` |
| JOIN 键 | `trip_date = date`（左表 `trip_date` TIMESTAMP → 右表 `date` TIMESTAMP） |
| 语义 | 每日行程汇总表按日期关联日期维表，用于日期范围过滤 |
| 代码证据 | `agent.py:1372-1373` — `on=f"gold.dim_date.date = {g3_table}.{date_col}"` |
| 列名证据 | `agent.py:1869` — `"trip": "trip_date"`；DuckDB schema 实测 `trip_date TIMESTAMP` |
| 备用键 | G3 表同时有 `date_key INTEGER`，可通过 `date_key = date_key` 替代，但代码使用 TIMESTAMP 路径 |

### 建议 2：dws_daily_parking_summary ↔ dim_date

```yaml
- "gold.dws_daily_parking_summary ↔ gold.dim_date (issue_date = date)"
```

| 项目 | 值 |
|------|-----|
| 左表 | `gold.dws_daily_parking_summary` |
| 右表 | `gold.dim_date` |
| JOIN 键 | `issue_date = date`（左表 `issue_date` TIMESTAMP → 右表 `date` TIMESTAMP） |
| 语义 | 每日停车罚单汇总表按日期关联日期维表 |
| 代码证据 | `agent.py:1710-1711` — G3 多计划路径使用相同 `on` 模式 |
| 列名证据 | `agent.py:1870` — `"parking": "issue_date"`；DuckDB schema 实测 `issue_date TIMESTAMP` |
| 备用键 | G3 表同时有 `date_key INTEGER`，可通过 `date_key = date_key` 替代，但代码使用 TIMESTAMP 路径 |

### 建议 3：dws_daily_crash_summary ↔ dim_date

```yaml
- "gold.dws_daily_crash_summary ↔ gold.dim_date (crash_date = date)"
```

| 项目 | 值 |
|------|-----|
| 左表 | `gold.dws_daily_crash_summary` |
| 右表 | `gold.dim_date` |
| JOIN 键 | `crash_date = date`（左表 `crash_date` TIMESTAMP → 右表 `date` TIMESTAMP） |
| 语义 | 每日事故汇总表按日期关联日期维表 |
| 代码证据 | `agent.py:1406-1407` — G3 降级路径使用相同 `on` 模式 |
| 列名证据 | `agent.py:1871` — `"crash": "crash_date"`；DuckDB schema 实测 `crash_date TIMESTAMP` |
| 备用键 | G3 表同时有 `date_key INTEGER`，可通过 `date_key = date_key` 替代，但代码使用 TIMESTAMP 路径 |

## 3. 完整变更 Diff

```diff
--- a/TianShu/contracts/sql_safety_policy.yml
+++ b/TianShu/contracts/sql_safety_policy.yml
@@ -65,6 +65,9 @@ table_reference_rules:
       - "gold.fact_tif_payments ↔ gold.dim_date (payment_date_key)"
       - "gold.fact_driver_applications ↔ gold.dim_date (app_date_key)"
       - "gold.dws_daily_trip_summary ↔ gold.dws_daily_crash_summary (trip_date = crash_date)"
+      - "gold.dws_daily_trip_summary ↔ gold.dim_date (trip_date = date)"
+      - "gold.dws_daily_parking_summary ↔ gold.dim_date (issue_date = date)"
+      - "gold.dws_daily_crash_summary ↔ gold.dim_date (crash_date = date)"
```

## 4. 格式说明

### 4.1 为什么使用 `(trip_date = date)` 而非 `(trip_date)`

G2 事实表→dim_date 使用简写格式 `(issue_date_key)`，因为它们 JOIN 的是 `dim_date.date_key`（INTEGER 列，这是 dim_date 的主键约定）。

G3 汇总表→dim_date 使用 `dim_date.date`（TIMESTAMP 类型列），而非 `date_key`：

```python
# agent.py:1372-1373 — G3 单列路径
on=f"gold.dim_date.date = {g3_table}.{date_col}"

# agent.py:1004-1017 — G2 路径（对比）
on=f"gold.dim_date.{date_dim_col} = {g2_table}.{date_join_key}"
# 其中 date_dim_col = "date_key"
```

因此 G3→dim_date 使用显式 `=` 格式，与现有的跨表 JOIN 格式一致：
```yaml
- "gold.dws_daily_trip_summary ↔ gold.dws_daily_crash_summary (trip_date = crash_date)"
```

### 4.2 解析兼容性

`_parse_join_entry()`（`src/safety_policy_loader.py:297`）支持此格式。括号内容通过 `_extract_join_keys()` 正则提取，表名提取忽略括号内容。`check_real_contracts_completeness` 只比较表对（`left_table`, `right_table`），不比较 JOIN 键。

## 5. 实际 Schema 验证

2026-06-22 对 TianShu DuckDB 实测 schema：

### 5.1 G3 表结构

| 表 | 日期列 | 实际类型 | 是否有 `date_key` INTEGER |
|----|--------|---------|--------------------------|
| `gold.dws_daily_trip_summary` | `trip_date` | `TIMESTAMP` | ✅ 是（备用） |
| `gold.dws_daily_parking_summary` | `issue_date` | `TIMESTAMP` | ✅ 是（备用） |
| `gold.dws_daily_crash_summary` | `crash_date` | `TIMESTAMP` | ✅ 是（备用） |

### 5.2 dim_date 结构

| 列 | 实际类型 |
|----|---------|
| `date_key` | `INTEGER`（主键，YYYYMMDD 格式） |
| `date` | `TIMESTAMP` |

### 5.3 G2 vs G3 JOIN 键对照

| 特征 | G2 事实表 | G3 汇总表 |
|------|----------|----------|
| JOIN 用 dim_date 列 | `date_key`（INTEGER） | `date`（TIMESTAMP） |
| 事实表日期列类型 | `INTEGER`（`*_date_key`） | `TIMESTAMP`（`trip_date`/`issue_date`/`crash_date`） |
| 示例 JOIN | `fact.date_key = dim_date.date_key` | `summary.trip_date = dim_date.date` |
| 已有注册 | ✅ 5 条 | ❌ 0 条 |

## 6. 评审清单

TianShu Dev Agent 评审时请确认：

- [x] 三个 G3 表的日期列名与实际 DuckDB schema 一致（已验证：`trip_date`/`issue_date`/`crash_date` 均存在，类型 `TIMESTAMP`）
- [x] `dim_date.date` 类型为 `TIMESTAMP`（已验证，与 G3 日期列类型一致）
- [ ] G3 表同时有 `date_key INTEGER` 列——是否应改用 `date_key = date_key`（INTEGER JOIN 性能更优）？
- [ ] `dim_date.date` 列上存在索引或查询性能可接受
- [ ] G3→dim_date JOIN 不会引入数据重复（每日一行，日期粒度一致）
- [ ] 安全语义：日期过滤仍然强制通过 dim_date，不会绕过日期白名单

## 7. Lite 侧影响

契约更新后，Lite 项目的唯一动作是重新运行：

```bash
cd TianShu-Text2SQL-Lite
python -m harness check --contracts
```

预期：`real_contracts_completeness` 从 `fail` 变为 `pass`，总结果退出码 0。

Lite 不修改契约文件、不硬编码补丁、不在代码中绕过 fail-closed。

## 8. 阻塞状态

当前 Phase 5.1 受 TianShu 外部契约阻塞：`real_contracts_completeness` 未通过（32/33）。

此文档即为 Phase 5.1 工作项 1 的产物。工作项 2（提交 TianShu Dev Agent）需人工或自动化工具将建议送达 TianShu 项目侧。

在契约更新并验证通过前，Phase 5 客观状态为：
> **Phase 5.1 阻塞 — 等待 TianShu 外部契约变更**
