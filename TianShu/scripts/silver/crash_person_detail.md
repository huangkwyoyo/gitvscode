# silver.crash_person_detail（事故人员明细标准表）

## 表概览

| 属性 | 值 |
|---|---|
| 英文表名 | `silver.crash_person_detail` |
| 中文表名 | 事故人员明细标准表 |
| 数据域 | 安全域 |
| 数据角色 | 事实表（Fact） |
| 批次 | P2（第三批） |
| 来源 | `bronze.crash_person_all`（5,333,042 行，21 列，全部 VARCHAR） |
| 预计行数 | 533 万 |
| 主键 | `unique_id`（BIGINT，自然键） |
| 字段数 | 22 |

## 设计理由

### 为什么弃用 4 个缺失率 ≥ 50% 的字段

| 弃用字段 | 缺失率 | 弃用原因 |
|---|---|---|
| `ped_location` | 98.2% | 几乎全空，无法做有效分析 |
| `ped_action` | 98.2% | 同上 |
| `contributing_factor_1` | 98.2% | 事故因素信息在 `crash_detail` 表中更完整 |
| `contributing_factor_2` | 98.2% | 同上 |

`contributing_factor_1/2` 在人员表中几乎全空（98.2%），但事故主表 `crash_merged` 中有对应的 `contributing_factor_vehicle_1/2` 且缺失率低得多。因此人员维度不需要重复保留事故因素，应通过 `collision_id` 关联到 `crash_detail` 获取。

### 为什么保留 6 个缺失率 46-49% 的辅助字段

| 保留字段 | 缺失率 | 保留原因 |
|---|---|---|
| `ejection` | 48.6% | 安全分析核心："弹出车外"是致死关键因素 |
| `emotional_status` | 46.9% | 事故原因分析："情绪状态"可能是肇事因素 |
| `bodily_injury` | 46.9% | 伤亡详情："身体伤害"比 `person_injury` 更具体 |
| `position_in_vehicle` | 48.6% | 安全分析："哪个座位最危险" |
| `safety_equipment` | 48.6% | 安全分析："安全带使用率与伤亡关系" |
| `complaint` | 46.9% | 投诉趋势分析 |

46-49% 的缺失率意味着超过一半（51-54%）的数据是可用的。对于安全分析来说，533 万行 × 51% ≈ **272 万行有值**——足够做统计显著性分析。

这些字段的**分析价值极高**：
- 安全带使用 → 伤亡程度的相关性
- 弹出车外 → 致死率的风险比
- 车内位置 → 安全设计改进方向

### 为什么新增 `is_orphan_record`（孤立记录标记）

当前已知 `crash_person_all.collision_id` 与 `crash_merged.collision_id` 覆盖不完全。部分人员记录的 `collision_id` 在事故主表中找不到对应行。

`is_orphan_record` 标记让下游分析时可以选择"只统计有事故详情的人员"或"包含所有人员"，而非静默丢失数据。

### 为什么 `person_age` 需要范围校验

- VARCHAR→INTEGER 转换可能产生异常值。
- 交通事故中年龄 < 0 无意义，年龄 > 120 极可能是数据错误。
- 标记但不丢弃，让下游决定是否排除。

## 关联验证

```sql
-- Silver 层建表后验证
SELECT
    COUNT(*) AS total_persons,
    SUM(CASE WHEN cd.collision_id IS NULL THEN 1 ELSE 0 END) AS orphan_count,
    ROUND(orphan_count * 100.0 / total_persons, 1) AS orphan_pct
FROM silver.crash_person_detail cpd
LEFT JOIN silver.crash_detail cd
    ON cpd.collision_id = cd.collision_id;
```

## 质量规则

- `unique_id` 需验证唯一性（Bronze 层已初步校验唯一）。
- `collision_id` 需验证与 `silver.crash_detail.collision_id` 的外键覆盖关系。
- `person_age < 0` 或 `> 120` 标记异常。
- `is_orphan_record = TRUE` 的行不丢弃，保留供独立分析。
- 6 个辅助字段全部为 NULL 时标记 `has_missing_aux = TRUE`。

## 字段来源分类

| 字段 | 来源类型 | 来源字段/逻辑 |
|---|---|---|
| `unique_id` | standardized | `unique_id`（VARCHAR→BIGINT，主键） |
| `collision_id` | standardized | `collision_id`（VARCHAR→BIGINT） |
| `crash_date` | standardized | `crash_date`（VARCHAR→DATE） |
| `crash_time` | direct | `crash_time` |
| `person_id` | direct | `person_id` |
| `person_type` | direct | `person_type` |
| `person_injury` | direct | `person_injury` |
| `person_sex` | direct | `person_sex` |
| `person_age` | standardized | `person_age`（VARCHAR→INTEGER） |
| `vehicle_id` | direct | `vehicle_id` |
| `ped_role` | direct | `ped_role` |
| `ejection` | direct | `ejection`（缺失率48.6%，保留） |
| `emotional_status` | direct | `emotional_status`（缺失率46.9%，保留） |
| `bodily_injury` | direct | `bodily_injury`（缺失率46.9%，保留） |
| `position_in_vehicle` | direct | `position_in_vehicle`（缺失率48.6%，保留） |
| `safety_equipment` | direct | `safety_equipment`（缺失率48.6%，保留） |
| `complaint` | direct | `complaint`（缺失率46.9%，保留） |
| `is_duplicate_person` | derived | unique_id重复检查 |
| `is_orphan_record` | derived | collision_id外键覆盖检查 |
| `has_missing_aux` | derived | 6个辅助字段全NULL检查 |
| `source_table` | derived | 固定值 `crash_person_all` |
| `source_row_hash` | derived | MD5溯源 |
