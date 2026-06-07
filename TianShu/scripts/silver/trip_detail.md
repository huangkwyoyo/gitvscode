# silver.trip_detail（行程明细标准表）

## 表概览

| 属性 | 值 |
|---|---|
| 英文表名 | `silver.trip_detail` |
| 中文表名 | 行程明细标准表 |
| 数据域 | 出行域 |
| 数据角色 | 事实表（Fact） |
| 批次 | P0（第一批） |
| 来源 | `bronze.yellow_tripdata_2026q1` + `bronze.green_tripdata_2026q1` + `bronze.fhv_tripdata_2026q1` + `bronze.fhvhv_tripdata_2026q1` |
| 预计行数 | 80,324,417 |
| 主键 | `trip_id`（VARCHAR，代理键，格式 `{trip_source}_{hash}`，MD5 稳定哈希） |
| 字段数 | 39 |

## 设计理由

### 为什么 39 个字段而非保守的 15 个

HVFHV 占出行域 78%（6,287 万行），其独有的 14 个字段是后续 Gold 层"司机收入分析""共享出行占比""WAV 匹配率"等指标的唯一来源。如果 Silver 层丢弃这些字段，Gold 层就得回查 Bronze 的 HVFHV 原始表，违背了 Lakehouse 逐层提纯的原则。

### 为什么用 UNION ALL 宽表而非分表

- **Agent 查询简单**：一张 `trip_detail` 覆盖所有行程，Agent 不需要判断去查哪张子表。
- **HVFHV 独有字段对非 HVFHV 来源填 NULL**：DuckDB 的列式存储对 NULL 压缩效率极高，几乎不占空间。
- 如果分表（`trip_detail_core` + `trip_detail_hvfhv`），每次跨类型分析都需要 JOIN，增加 Agent 出错概率。

### 为什么字段名要统一

Bronze 层四张表的同义字段名各异：

| 语义 | Yellow | Green | FHV | HVFHV |
|---|---|---|---|---|
| 上车时间 | `tpep_pickup_datetime` | `lpep_pickup_datetime` | `pickup_datetime` | `pickup_datetime` |
| 上车区域 | `PULocationID` | `PULocationID` | `PUlocationID` | `PULocationID` |
| 行程距离 | `trip_distance` | `trip_distance` | 无 | `trip_miles` |

Silver 层必须统一为 `pickup_at`、`pickup_location_id`、`distance_miles`。

### 为什么金额字段统一 DECIMAL(12,2)

- Bronze 层金额字段为 DOUBLE，存在浮点精度问题（如 0.1 + 0.2 != 0.3）。
- `DECIMAL(12,2)` 精确到分，足够覆盖 NYC 出租车费用范围（单程最高约 $500）。
- 遵循 AGENTS.md 规范："涉及金额、费用、收入等货币类字段，类型统一使用 DECIMAL"。

### 为什么保留 `ehail_fee`（电子预约费）

该字段在 Green 出租车中 100% 为空（已实质废弃），但保留它的理由：
- 不占额外存储（NULL 在列式存储中近乎免费）。
- 未来 Green 出租车可能重新启用此字段。
- 丢弃字段是不可逆操作，保留比丢弃更安全。

### 为什么 `trip_id` 用 VARCHAR 而非 BIGINT

- 格式 `{trip_source}_{hash}`（如 `yellow_a1b2c3d4`）。不依赖 `ROW_NUMBER()`（无 `ORDER BY` 会导致重跑时 ID 漂移），而是基于 `trip_source + source_table + MD5(原始行)` 生成稳定哈希。
- 自带来源标识，溯源时只需解析 `trip_id` 前缀即可知道来源。
- 稳定哈希确保了同一行数据在任何时候重跑入库都生成相同的 `trip_id`，支持增量更新和幂等写入。

### 为什么设计 5 个质量标记

| 标记 | 覆盖场景 |
|---|---|
| `is_time_anomaly` | ① pickup 不在 2026Q1 范围（2008/2009 历史数据混入）；② dropoff < pickup（时间倒流）；③ 时长 > 6h（极端长行程） |
| `is_location_missing` | FHV 类 PUlocationID 缺失率 87%，必须标记而非丢弃 |
| `is_distance_outlier` | trip_distance 极端值达 328,522 英里（约为地球周长的 13 倍），明显异常 |
| `source_row_hash` | MD5 溯源，确保每条 Silver 记录可追溯到对应 Bronze 行 |
| `source_table` | 文字溯源，方便人工排查时快速定位来源表 |

## 字段设计

### 核心标识与时间字段

| 英文字段名 | 中文字段名 | 类型 | 字段层级 | 说明 |
|---|---|---|---|---|
| `trip_id` | 行程代理主键 | VARCHAR | 主键 | 格式 `{trip_source}_{hash}`，MD5 稳定哈希 |
| `trip_source` | 行程来源类型 | VARCHAR | 退化维度 | `yellow` / `green` / `fhv` / `fhvhv` |
| `pickup_at` | 接客时间 | TIMESTAMP | 时间字段 | 统一四个源表的上车时间 |
| `dropoff_at` | 送客时间 | TIMESTAMP | 时间字段 | 统一下车时间 |
| `pickup_date` | 接客日期 | DATE | 时间字段 | 从 `pickup_at` 派生，关联 `dim_date.date` |

### 空间与维度外键

| 英文字段名 | 中文字段名 | 类型 | 字段层级 | 说明 |
|---|---|---|---|---|
| `pickup_location_id` | 上车区域编号 | INTEGER | 空间字段 | 关联 `silver.taxi_zone.location_id` |
| `dropoff_location_id` | 下车区域编号 | INTEGER | 空间字段 | 同上 |
| `base_no` | 派车基地编号 | VARCHAR | 维度外键 | FHV/HVFHV 可用，关联 `vehicle_detail.base_number` |

### 度量字段

| 英文字段名 | 中文字段名 | 类型 | 可用范围 |
|---|---|---|---|
| `passenger_count` | 乘客人数 | BIGINT | Yellow/Green/HVFHV |
| `distance_miles` | 行程距离（英里） | DOUBLE | Yellow/Green/HVFHV |
| `payment_type` | 支付方式 | BIGINT | Yellow/Green |
| `rate_code_id` | 费率代码 | BIGINT | Yellow/Green |
| `trip_type` | 行程类型 | BIGINT | Green 独有 |

### 金额字段（全部 DECIMAL(12,2)）

| 英文字段名 | 中文字段名 | 可用范围 |
|---|---|---|
| `fare_amount` | 基础车费 | Yellow/Green/HVFHV |
| `total_amount` | 总费用 | Yellow/Green |
| `extra` | 附加费 | Yellow/Green |
| `mta_tax` | MTA税 | Yellow/Green |
| `tip_amount` | 小费 | Yellow/Green/HVFHV |
| `tolls_amount` | 通行费 | Yellow/Green/HVFHV |
| `improvement_surcharge` | 改善附加费 | Yellow/Green |
| `congestion_surcharge` | 拥堵附加费 | Yellow/Green/HVFHV |
| `airport_fee` | 机场费 | Yellow/Green/HVFHV |
| `cbd_congestion_fee` | CBD拥堵费 | Yellow/Green/HVFHV |
| `sales_tax` | 销售税 | HVFHV 独有 |
| `bcf` | 黑车基金费 | HVFHV 独有 |
| `driver_pay` | 司机净收入 | HVFHV 独有 |
| `ehail_fee` | 电子预约费 | Green 独有 |

### HVFHV 独有时间与标志位

| 英文字段名 | 中文字段名 | 类型 | 说明 |
|---|---|---|---|
| `request_datetime` | 乘客请求时间 | TIMESTAMP | 乘客发起叫车请求的时间 |
| `on_scene_datetime` | 司机到达时间 | TIMESTAMP | 司机到达接客地点的时间 |
| `shared_request_flag` | 请求共享标志 | VARCHAR(1) | Y/N |
| `shared_match_flag` | 实际共享标志 | VARCHAR(1) | Y/N |
| `wav_request_flag` | 请求WAV标志 | VARCHAR(1) | Y/N |
| `wav_match_flag` | 匹配WAV标志 | VARCHAR(1) | Y/N |
| `access_a_ride_flag` | MTA无障碍标志 | VARCHAR(1) | Y/N |

### 质量标记与溯源

| 英文字段名 | 中文字段名 | 类型 | 说明 |
|---|---|---|---|
| `is_time_anomaly` | 是否时间异常 | BOOLEAN | pickup 不在 2026Q1 范围 或 dropoff < pickup 或时长 > 6h |
| `is_location_missing` | 是否位置缺失 | BOOLEAN | pickup_location_id 或 dropoff_location_id IS NULL |
| `is_distance_outlier` | 是否距离异常 | BOOLEAN | distance_miles IS NULL 或 ≤ 0 或 > 500 |
| `source_row_hash` | 来源行哈希 | VARCHAR(64) | MD5(trip_source + 原始行所有字段拼接) |
| `source_table` | 来源表 | VARCHAR | Bronze 来源表名 |

## 生成逻辑（伪代码）

```sql
INSERT INTO silver.trip_detail
SELECT
    'yellow_' || MD5(CONCAT(
        'yellow_tripdata_2026q1',
        COALESCE(CAST(tpep_pickup_datetime AS VARCHAR), ''),
        COALESCE(CAST(tpep_dropoff_datetime AS VARCHAR), ''),
        COALESCE(CAST(PULocationID AS VARCHAR), ''),
        COALESCE(CAST(DOLocationID AS VARCHAR), ''),
        COALESCE(CAST(trip_distance AS VARCHAR), ''),
        COALESCE(CAST(total_amount AS VARCHAR), '')
    )) AS trip_id,  -- 稳定哈希，重跑不漂移
    'yellow' AS trip_source,
    tpep_pickup_datetime AS pickup_at,
    tpep_dropoff_datetime AS dropoff_at,
    tpep_pickup_datetime::DATE AS pickup_date,
    -- ... 其余字段 ...
    'yellow_tripdata_2026q1' AS source_table
FROM bronze.yellow_tripdata_2026q1

UNION ALL

SELECT
    'green_' || MD5(CONCAT(
    'green' AS trip_source,
    -- ... 同上模式 ...
FROM bronze.green_tripdata_2026q1

UNION ALL
-- fhv, fhvhv 同理
;
```

## 质量规则

- `pickup_at` 不允许为空。
- `dropoff_at` 为空时保留，标记 `is_time_anomaly = TRUE`。
- 金额字段出现负值时标记但不丢弃（疑为退款/调整记录）。
- FHV 行程 `pickup_location_id` 缺失率 87%，标记 `is_location_missing = TRUE`，不强行补值。
- `distance_miles > 500` 标记 `is_distance_outlier = TRUE`。

## 字段来源分类

### 核心标识与时间（5字段）

| 字段 | 来源类型 | 来源字段/逻辑 |
|---|---|---|
| `trip_id` | derived | MD5(trip_source + source_table + 关键字段)，稳定哈希 |
| `trip_source` | derived | 常量，来自 UNION ALL 分支 |
| `pickup_at` | standardized | Yellow:`tpep_pickup_datetime` / Green:`lpep_pickup_datetime` / FHV+HVFHV:`pickup_datetime` |
| `dropoff_at` | standardized | Yellow:`tpep_dropoff_datetime` / Green:`lpep_dropoff_datetime` / FHV:`dropOff_datetime` / HVFHV:`dropoff_datetime` |
| `pickup_date` | derived | `pickup_at::DATE` |

### 空间与维度外键（3字段）

| 字段 | 来源类型 | 来源字段/逻辑 |
|---|---|---|
| `pickup_location_id` | standardized | Yellow+Green+HVFHV:`PULocationID` / FHV:`PUlocationID`（统一命名+INTEGER） |
| `dropoff_location_id` | standardized | Yellow+Green+HVFHV:`DOLocationID` / FHV:`DOlocationID`（统一命名+INTEGER） |
| `base_no` | standardized | HVFHV:`dispatching_base_num` / FHV:`Affiliated_base_number` |

### 度量字段（5字段）

| 字段 | 来源类型 | 来源字段/逻辑 | 可用范围 |
|---|---|---|---|
| `passenger_count` | direct | `passenger_count` | Yellow/Green/HVFHV |
| `distance_miles` | standardized | Yellow+Green:`trip_distance` / HVFHV:`trip_miles` | Yellow/Green/HVFHV |
| `payment_type` | direct | `payment_type` | Yellow/Green |
| `rate_code_id` | direct | `RatecodeID` | Yellow/Green |
| `trip_type` | direct | `trip_type` | Green独有 |

### 金额字段（14字段，全部 DECIMAL(12,2)）

| 字段 | 来源类型 | 来源字段 | 可用范围 |
|---|---|---|---|
| `fare_amount` | standardized | Yellow+Green:`fare_amount` / HVFHV:`base_passenger_fare`（DOUBLE→DECIMAL） | Yellow/Green/HVFHV |
| `total_amount` | standardized | `total_amount`（DOUBLE→DECIMAL） | Yellow/Green |
| `extra` | standardized | `extra`（DOUBLE→DECIMAL） | Yellow/Green |
| `mta_tax` | standardized | `mta_tax`（DOUBLE→DECIMAL） | Yellow/Green |
| `tip_amount` | standardized | Yellow+Green:`tip_amount` / HVFHV:`tips`（DOUBLE→DECIMAL） | Yellow/Green/HVFHV |
| `tolls_amount` | standardized | Yellow+Green:`tolls_amount` / HVFHV:`tolls`（DOUBLE→DECIMAL） | Yellow/Green/HVFHV |
| `improvement_surcharge` | standardized | `improvement_surcharge`（DOUBLE→DECIMAL） | Yellow/Green |
| `congestion_surcharge` | standardized | `congestion_surcharge`（DOUBLE→DECIMAL） | Yellow/Green/HVFHV |
| `airport_fee` | standardized | Yellow:`Airport_fee` / Green+HVFHV:`airport_fee`（DOUBLE→DECIMAL） | Yellow/Green/HVFHV |
| `cbd_congestion_fee` | standardized | `cbd_congestion_fee`（DOUBLE→DECIMAL） | Yellow/Green/HVFHV |
| `sales_tax` | standardized | `sales_tax`（DOUBLE→DECIMAL） | HVFHV独有 |
| `bcf` | standardized | `bcf`（DOUBLE→DECIMAL） | HVFHV独有 |
| `driver_pay` | standardized | `driver_pay`（DOUBLE→DECIMAL） | HVFHV独有 |
| `ehail_fee` | standardized | `ehail_fee`（DOUBLE→DECIMAL） | Green独有 |

### HVFHV独有时间与标志位（7字段）

| 字段 | 来源类型 | 来源字段 | 可用范围 |
|---|---|---|---|
| `request_datetime` | direct | `request_datetime` | HVFHV独有 |
| `on_scene_datetime` | direct | `on_scene_datetime` | HVFHV独有 |
| `shared_request_flag` | direct | `shared_request_flag` | HVFHV独有 |
| `shared_match_flag` | direct | `shared_match_flag` | HVFHV独有 |
| `wav_request_flag` | direct | `wav_request_flag` | HVFHV独有 |
| `wav_match_flag` | direct | `wav_match_flag` | HVFHV独有 |
| `access_a_ride_flag` | direct | `access_a_ride_flag` | HVFHV独有 |

### 质量标记与溯源（5字段）

| 字段 | 来源类型 | 来源字段/逻辑 |
|---|---|---|
| `is_time_anomaly` | derived | pickup不在2026Q1范围 或 dropoff<pickup 或 时长>6h |
| `is_location_missing` | derived | pickup_location_id或dropoff_location_id IS NULL |
| `is_distance_outlier` | derived | distance_miles IS NULL 或 ≤0 或 >500 |
| `source_row_hash` | derived | MD5(trip_source + 原始行所有字段拼接) |
| `source_table` | derived | 常量，Bronze来源表名 |
