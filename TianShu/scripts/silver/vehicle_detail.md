# silver.vehicle_detail（车辆明细标准表）

## 表概览

| 属性 | 值 |
|---|---|
| 英文表名 | `silver.vehicle_detail` |
| 中文表名 | 车辆明细标准表 |
| 数据域 | 资产域 |
| 数据角色 | 维表（Dimension） |
| 批次 | P1（第二批） |
| 来源 | `bronze.active_vehicles`（119,207 行）+ `bronze.fhv_active_vehicles`（104,420 行）+ `bronze.medallion_authorized_vehicles`（10,547 行） |
| 预计行数 | ~12 万（去重合并后） |
| 主键 | `vehicle_id`（BIGINT，代理键） |
| 字段数 | 25 |

## 设计理由

### 为什么需要代理键 `vehicle_id`

三张 Bronze 表各有自己的"主键"：
- `active_vehicles.License Number` — 覆盖 Medallion + FHV
- `fhv_active_vehicles.Vehicle License Number` — 仅 FHV
- `medallion_authorized_vehicles.License Number` — 仅 Medallion

三者有重叠但不能简单 UNION ALL（同一辆车可能同时出现在多张表中，且字段值可能不完全一致）。用代理键可以：
1. 统一主键格式（BIGINT）
2. 隔离合并逻辑的复杂性（下游不需要知道自然键的冲突）
3. 保持 `license_number` 作为候选键（加唯一索引）

### 为什么同名异源字段要设优先级

以燃料类型为例：

| 来源表 | 字段 | 分类精度 | 缺失率 |
|---|---|---|---|
| `active_vehicles` | `Fuel Type` | 7 种 | ~2.5% |
| `fhv_active_vehicles` | 无此字段 | — | — |
| `medallion_authorized_vehicles` | 无此字段 | — | — |

结论：燃料类型只能从 `active_vehicles` 获取，不存在冲突。

以 WAV 标志为例：

| 来源表 | 字段 | 缺失率 |
|---|---|---|
| `active_vehicles` | `WAV` | 2.4% |
| `fhv_active_vehicles` | `Wheelchair Accessible` | 91.6% |

结论：优先取 `active_vehicles.WAV`，缺失率低得多。

### 为什么 `stretch_limo`、`insurance_carrier` 等字段只来自一张表

这些字段是某张 Bronze 表独有的。Silver 层保留它们（填 NULL 给其他来源），因为它们对特定分析有价值：
- `stretch_limo`：监管豪华轿车运营
- `insurance_carrier`：车辆保险风险评估
- `medallion_type`：Medallion 牌照的管理模式分析

## 三表合并策略

```
active_vehicles (119K)         ← 基础表，覆盖最全
    ↓ LEFT JOIN
fhv_active_vehicles (104K)     ← 补充 FHV 专有字段（基地、地址等）
    ↓ LEFT JOIN
medallion_authorized_vehicles  ← 补充 Medallion 专有字段（代理、类型）
    (10K)
    ↓
silver.vehicle_detail (~12万行去重)
```

## 字段优先级速查

| 合并字段 | 优先来源 | 原因 |
|---|---|---|
| `license_number` | `active_vehicles` | 唯一覆盖 Medallion + FHV |
| `vin` | `active_vehicles` | 格式最规范（17位VIN） |
| `fuel_type` | `active_vehicles` | 唯一来源，7种分类 |
| `wav_flag` | `active_vehicles` | 缺失率 2.4% vs 91.6% |
| `vehicle_year` | `active_vehicles` | 覆盖最全（2011-2026） |
| `base_number` | `fhv_active_vehicles` | FHV 专有 |
| `base_name` | `fhv_active_vehicles` | FHV 专有 |
| `agent_number` | `medallion_authorized_vehicles` | Medallion 专有 |

## 质量规则

- `license_number` 不允许为空，候选键唯一索引。
- `vehicle_year < 2000` 或 `> 2027` 标记质量问题。
- `wav_flag` 为空时填 `UNKNOWN`。
- `expiration_date` 早于 `2026-01-01` 标记为已过期。

## 字段来源分类

| 字段 | 来源类型 | 优先来源 | 说明 |
|---|---|---|---|
| `vehicle_id` | derived | — | 自增代理键 |
| `license_number` | direct | active_vehicles | `License Number` / `Vehicle License Number` |
| `license_type` | direct | active_vehicles | `License Type` |
| `license_status` | direct | active_vehicles | `TLC Vehicle License Status` / `Current Status` |
| `owner_name` | direct | active_vehicles | `Owner Name` / `Name` |
| `expiration_date` | standardized | active_vehicles | `Expiration Date`（VARCHAR→DATE） |
| `dmv_plate_number` | direct | active_vehicles | `DMV Plate Number` / `DMV License Plate Number` |
| `vin` | direct | active_vehicles | `VIN` / `Vehicle VIN Number` |
| `vehicle_make` | direct | active_vehicles | `Vehicle Make` |
| `vehicle_model` | direct | active_vehicles | `Vehicle Model` |
| `vehicle_year` | standardized | active_vehicles | `Vehicle Year` / `Model Year`（VARCHAR→INTEGER） |
| `fuel_type` | direct | active_vehicles | `Fuel Type`（7种分类） |
| `wav_flag` | direct | active_vehicles | `WAV` / `Wheelchair Accessible`（缺失率2.4%优于91.6%） |
| `stretch_limo` | direct | active_vehicles | `Stretch Limo`（独有） |
| `medallion_type` | direct | medallion | `Medallion Type`（独有） |
| `base_number` | direct | fhv_active_vehicles | `Base Number`（FHV专有） |
| `base_name` | direct | fhv_active_vehicles | `Base Name`（FHV专有） |
| `base_type` | direct | fhv_active_vehicles | `Base Type`（FHV专有） |
| `base_address` | direct | fhv_active_vehicles | `Base Address`（FHV专有） |
| `agent_number` | direct | medallion | `Agent Number`（Medallion专有） |
| `agent_name` | direct | medallion | `Agent Name`（缺失率47%） |
| `insurance_carrier` | direct | active_vehicles | `Insurance Carrier Name`（独有） |
| `insurance_policy_number` | direct | active_vehicles | `Automobile Insurance Policy Number`（独有） |
| `last_date_updated` | standardized | active_vehicles | `Last Date Updated`（VARCHAR→DATE） |
| `source_table` | derived | — | 常量，记录Bronze来源表 |
