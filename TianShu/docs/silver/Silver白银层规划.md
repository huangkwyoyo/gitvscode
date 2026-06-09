# Silver 白银层规划

## 目标

Silver 白银层是从 `bronze` 原始层提取出来的标准明细层。

它的目标不是汇总，而是把原始数据变成：

- 字段名标准。
- 类型标准（金额→DECIMAL、日期→DATE、数字→BIGINT、文本→VARCHAR）。
- 主键清晰。
- 时间字段可用。
- 空间字段可用。
- 质量问题有标记（时间异常、位置缺失、距离异常、溯源哈希）。
- 中文表名和字段中文名可查询（同步写入 `meta.table_comments` + `meta.column_comments`）。

Silver 层建设完成后，Gold 星型模型和 Agent 问数才有稳定基础。

## 规划与门禁关系

本文件是 Silver 层规划文档，不是自动执行器。实际建表由 `scripts/silver/build_silver_duckdb.py` 完成，落库结果必须通过 Harness 强校验后才视为有效。

Silver 建成后必须执行：

```powershell
python scripts\quality\check_schema_consistency.py --require-silver-tables
python scripts\quality\check_silver_null.py
python scripts\quality\run_all_checks.py
```

如果规划文档、Silver 数据字典、建表脚本、DuckDB 实表、`meta.column_comments` 不一致，应先修复 Silver，不得直接进入 Gold。

## 当前 DuckDB 结构

DuckDB 文件：

```text
D:\ProgramData\Datawarehouse\纽约市城市交通\nyc_transport.duckdb
```

已存在 schema：

```text
bronze  # 原始层，16 张表（7 VIEW + 9 TABLE）
silver  # 标准层，下一步建设（当前为空）
gold    # 主题模型层，后续建设（当前为空）
meta    # 元数据和中文语义层，8 个对象已建成
```

## 数据类型标准化规则

Silver 层必须对 Bronze 层的不规范类型做强制转换。以下规则适用于所有 Silver 表：

| Bronze 现状 | Silver 标准 | 典型场景 |
|---|---|---|
| VARCHAR 存储的数字 | BIGINT | 基地汇总的 `Total Dispatched Trips`、`Unique Dispatched Vehicles` |
| VARCHAR / DOUBLE 存储的金额 | DECIMAL(12,2) | 行程费用、罚单金额、TIF 支付金额 |
| VARCHAR 存储的日期 | DATE | TIF 的 `Payment Date`、基地汇总的 `Year`+`Month` |
| VARCHAR 存储的 Y/N | VARCHAR(1) | `shared_request_flag`、`wav_match_flag` |
| DOUBLE 存储的 ID/代码 | BIGINT | `PULocationID`、`RatecodeID`、`payment_type` |
| TIMESTAMP | TIMESTAMP | 保持不变，统一字段名即可 |

## Silver 建设优先级

建议分三批建设。

### 第一批：稳定公共基础（P0）

| 英文表名 | 中文表名 | 来源表 | 建设原因 |
|---|---|---|---|
| `silver.dim_date` | 日期维表 | 固定生成 2026Q1 日期范围，后续年度扩展时由批次参数控制 | 所有 Gold 汇总表的公共时间维度 |
| `silver.taxi_zone` | 出租车区域标准维表 | `bronze.taxi_zone_lookup` | 空间维表最稳定，先建 |
| `silver.trip_detail` | 行程明细标准表 | 四类 TLC 行程表 | 出行域是核心事实数据，8,032 万行 |

### 第二批：供给和资产（P1）

| 英文表名 | 中文表名 | 来源表 | 建设原因 |
|---|---|---|---|
| `silver.vehicle_detail` | 车辆明细标准表 | `bronze.active_vehicles`、`bronze.fhv_active_vehicles`、`bronze.medallion_authorized_vehicles` | 支撑车辆、牌照、VIN、燃料、WAV 分析 |
| `silver.driver_detail` | 司机明细标准表 | `bronze.fhv_active_drivers`、`bronze.shl_active_drivers` | 支撑司机供给分析 |
| `silver.base_detail` | 基地月度明细标准表 | `bronze.fhv_base_aggregate_report` | 支撑 FHV 基地分析（需复合键治理） |
| `silver.driver_application_detail` | 司机申请明细标准表 | `bronze.new_driver_applications` | 支撑审批状态分析 |

### 第三批：监管合规和安全（P2）

| 英文表名 | 中文表名 | 来源表 | 建设原因 |
|---|---|---|---|
| `silver.parking_violation_detail` | 停车罚单明细标准表 | `bronze.parking_violations_all` | 支撑监管合规分析，958 万行 |
| `silver.tif_payment_detail` | TIF支付明细标准表 | `bronze.tif_medallion_payments` | 支撑补贴支付分析（需复合键治理） |
| `silver.crash_detail` | 事故明细标准表 | `bronze.crash_merged` | 支撑安全分析，166 万行 |
| `silver.crash_person_detail` | 事故人员明细标准表 | `bronze.crash_person_all` | 支撑事故人员伤害分析，533 万行 |

---

## 第一批详细设计

### silver.dim_date（日期维表）

来源：固定生成 2026-01-01 至 2026-03-31 日期范围，后续年度扩展时由批次参数控制。`dim_date` 需要早于 `trip_detail` 构建，因此不得依赖 `silver.trip_detail` 取日期范围。

主键：

| 英文名 | 中文名 | 说明 |
|---|---|---|
| `date_key` | 日期键 | INTEGER，格式 YYYYMMDD，如 `20260115` |

字段规划：

| 英文字段名 | 中文字段名 | 类型 | 说明 |
|---|---|---|---|
| `date_key` | 日期键 | INTEGER | PK，格式 YYYYMMDD |
| `date` | 日期 | DATE | 标准日期 |
| `year` | 年 | INTEGER | 如 2026 |
| `quarter` | 季度 | INTEGER | 1-4 |
| `month` | 月 | INTEGER | 1-12 |
| `week` | 周 | INTEGER | ISO 周号 1-53 |
| `day_of_week` | 星期几 | INTEGER | 1=周一，7=周日 |
| `day_of_week_name` | 星期名称 | VARCHAR | Monday-Sunday |
| `is_weekend` | 是否周末 | BOOLEAN | 周六/周日为 TRUE |
| `fiscal_year` | NYC财年 | INTEGER | NYC 财年：7月1日-6月30日 |

使用方式：trip_detail 中 `pickup_date = dim_date.date`，Gold 汇总表通过 `date_key` 关联。

### silver.taxi_zone（出租车区域标准维表）

来源：

```text
bronze.taxi_zone_lookup
```

主键：

| 英文名 | 中文名 | 说明 |
|---|---|---|
| `location_id` | 出租车区域编号 | INTEGER，来源于 `LocationID`，265 个唯一值，可作为主键 |

字段规划：

| 英文字段名 | 中文字段名 | 来源字段 | 类型 | 说明 |
|---|---|---|---|---|
| `location_id` | 出租车区域编号 | `LocationID` | INTEGER | PK，区域唯一编号 1-265 |
| `borough` | 行政区 | `Borough` | VARCHAR | Manhattan / Queens / Brooklyn / Bronx / Staten Island / EWR / Unknown |
| `zone_name` | 区域名称 | `Zone` | VARCHAR | 261 个唯一区域名称 |
| `service_zone` | 服务区域 | `service_zone` | VARCHAR | Yellow Zone / Boro Zone / Airports / EWR |
| `is_unknown_zone` | 是否未知区域 | 派生 | BOOLEAN | `borough = 'Unknown'` 时为 TRUE |

质量规则：

- `location_id` 不允许为空，必须唯一。
- `borough`、`zone_name`、`service_zone` 保留原始英文值。

### silver.trip_detail（行程明细标准表）

来源：

```text
bronze.yellow_tripdata_2026q1   -- 1,108 万行，20 列
bronze.green_tripdata_2026q1    -- 12 万行，21 列
bronze.fhv_tripdata_2026q1      -- 625 万行，7 列
bronze.fhvhv_tripdata_2026q1    -- 6,287 万行，25 列
```

合计约 8,032 万行。通过 UNION ALL 合并，HVFHV 独有字段在其他来源中填 NULL。

主键：

| 英文名 | 中文名 | 说明 |
|---|---|---|
| `trip_id` | 行程代理主键 | VARCHAR，Silver 层生成，格式 `{trip_source}_{row_number}` |

核心字段规划（字段名统一映射）：

| 英文字段名 | 中文字段名 | 类型 | 来源映射 | 说明 |
|---|---|---|---|---|
| `trip_id` | 行程代理主键 | VARCHAR | 生成 | PK，格式 `yellow_0000001` |
| `trip_source` | 行程来源类型 | VARCHAR | 常量 | `yellow` / `green` / `fhv` / `fhvhv` |
| `pickup_at` | 接客时间 | TIMESTAMP | `tpep_pickup_datetime` / `lpep_pickup_datetime` / `pickup_datetime` | 统一字段名 |
| `dropoff_at` | 送客时间 | TIMESTAMP | `tpep_dropoff_datetime` / `lpep_dropoff_datetime` / `dropOff_datetime` / `dropoff_datetime` | 统一字段名 |
| `pickup_date` | 接客日期 | DATE | 从 `pickup_at` 派生 | 关联 `silver.dim_date.date` |
| `pickup_location_id` | 上车区域编号 | INTEGER | `PULocationID` / `PUlocationID` | 关联 `silver.taxi_zone.location_id` |
| `dropoff_location_id` | 下车区域编号 | INTEGER | `DOLocationID` / `DOlocationID` | 关联 `silver.taxi_zone.location_id` |
| `base_no` | 派车基地编号 | VARCHAR | `dispatching_base_num` / `Affiliated_base_number` | FHV/HVFHV 可用 |
| `passenger_count` | 乘客人数 | BIGINT | `passenger_count` | Yellow/Green/HVFHV 可用 |
| `distance_miles` | 行程距离（英里） | DOUBLE | `trip_distance` / `trip_miles` | Yellow/Green 用 `trip_distance`，HVFHV 用 `trip_miles` |
| `payment_type` | 支付方式 | BIGINT | `payment_type` | Yellow/Green 可用，0=Flex,1=信用卡,2=现金,3=免费,4=争议,5=未知 |
| `rate_code_id` | 费率代码 | BIGINT | `RatecodeID` | Yellow/Green 可用，1=标准,2=JFK,3=Newark,4=Nassau,5=议价,6=拼车,99=未知 |
| `trip_type` | 行程类型 | BIGINT | `trip_type` | Green 独有，1=路边拦车,2=调度 |

金额字段（统一 DECIMAL(12,2)）：

| 英文字段名 | 中文字段名 | 类型 | 来源映射 | 可用范围 |
|---|---|---|---|---|
| `fare_amount` | 基础车费 | DECIMAL(12,2) | `fare_amount` / `base_passenger_fare` | Yellow/Green/HVFHV |
| `total_amount` | 总费用 | DECIMAL(12,2) | `total_amount` | Yellow/Green |
| `extra` | 附加费 | DECIMAL(12,2) | `extra` | Yellow/Green |
| `mta_tax` | MTA税 | DECIMAL(12,2) | `mta_tax` | Yellow/Green |
| `tip_amount` | 小费 | DECIMAL(12,2) | `tip_amount` / `tips` | Yellow/Green/HVFHV |
| `tolls_amount` | 通行费 | DECIMAL(12,2) | `tolls_amount` / `tolls` | Yellow/Green/HVFHV |
| `improvement_surcharge` | 改善附加费 | DECIMAL(12,2) | `improvement_surcharge` | Yellow/Green |
| `congestion_surcharge` | 拥堵附加费 | DECIMAL(12,2) | `congestion_surcharge` | Yellow/Green/HVFHV |
| `airport_fee` | 机场费 | DECIMAL(12,2) | `Airport_fee` / `airport_fee` | Yellow/Green/HVFHV |
| `cbd_congestion_fee` | CBD拥堵费 | DECIMAL(12,2) | `cbd_congestion_fee` | Yellow/Green/HVFHV |
| `sales_tax` | 销售税 | DECIMAL(12,2) | `sales_tax` | HVFHV 独有 |
| `bcf` | 黑车基金费 | DECIMAL(12,2) | `bcf` | HVFHV 独有 |
| `driver_pay` | 司机净收入 | DECIMAL(12,2) | `driver_pay` | HVFHV 独有 |
| `ehail_fee` | 电子预约费 | DECIMAL(12,2) | `ehail_fee` | Green 独有，100% 为空 |

HVFHV 独有标志位：

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `request_datetime` | 乘客请求时间 | TIMESTAMP | `request_datetime` | HVFHV 独有 |
| `on_scene_datetime` | 司机到达时间 | TIMESTAMP | `on_scene_datetime` | HVFHV 独有 |
| `shared_request_flag` | 请求共享标志 | VARCHAR(1) | `shared_request_flag` | HVFHV 独有，Y/N |
| `shared_match_flag` | 实际共享标志 | VARCHAR(1) | `shared_match_flag` | HVFHV 独有，Y/N |
| `wav_request_flag` | 请求WAV标志 | VARCHAR(1) | `wav_request_flag` | HVFHV 独有，Y/N |
| `wav_match_flag` | 匹配WAV标志 | VARCHAR(1) | `wav_match_flag` | HVFHV 独有，Y/N |
| `access_a_ride_flag` | MTA无障碍标志 | VARCHAR(1) | `access_a_ride_flag` | HVFHV 独有，Y/N |

质量标记字段：

| 英文字段名 | 中文字段名 | 类型 | 说明 |
|---|---|---|---|
| `is_time_anomaly` | 是否时间异常 | BOOLEAN | `pickup_at` 不在 2026 Q1 范围，或 `dropoff_at < pickup_at`，或时长 > 6 小时 |
| `is_location_missing` | 是否位置缺失 | BOOLEAN | `pickup_location_id` 或 `dropoff_location_id` IS NULL |
| `is_distance_outlier` | 是否距离异常 | BOOLEAN | `distance_miles` IS NULL 或 ≤ 0 或 > 500 |
| `source_row_hash` | 来源行哈希 | VARCHAR(64) | MD5(`trip_source` + 原始行所有字段拼接)，用于溯源 |
| `source_table` | 来源表 | VARCHAR | 记录 Bronze 来源表名，如 `yellow_tripdata_2026q1` |

质量规则：

- `pickup_at` 不允许为空。
- `dropoff_at` 为空时保留，但标记 `is_time_anomaly = TRUE`。
- `pickup_at` 不在 2026-01-01 ~ 2026-03-31 范围内时标记 `is_time_anomaly = TRUE`。
- FHV 行程 `pickup_location_id` 缺失率 87%，不能强行补值，标记 `is_location_missing = TRUE` 即可。
- 金额字段中出现负值时标记质量问题（疑为退款/调整记录），但不丢弃。

---

## 第二批详细设计

### silver.vehicle_detail（车辆明细标准表）

来源三表合并去重：

| 英文表名 | 中文表名 | 行数 | 主键 |
|---|---|---|---|
| `bronze.active_vehicles` | 活跃车辆注册表 | 119,207 | `License Number`（唯一） |
| `bronze.fhv_active_vehicles` | FHV活跃车辆表 | 104,420 | `Vehicle License Number`（唯一） |
| `bronze.medallion_authorized_vehicles` | 授权Medallion车辆表 | 10,547 | `License Number`（唯一） |

合并策略：

- 以 `License Number` / `Vehicle License Number` 为合并键。
- `active_vehicles` 为基础表（覆盖最全），其余两表做 LEFT JOIN 补充。
- 同名异源字段取数据质量更高的来源。

完整字段设计：

| 英文字段名 | 中文字段名 | 类型 | 来源映射 | 优先来源 | 说明 |
|---|---|---|---|---|---|
| `vehicle_id` | 车辆代理主键 | BIGINT | 生成 | — | PK，自增 |
| `license_number` | 牌照编号 | VARCHAR | `License Number` / `Vehicle License Number` | `active_vehicles` | 唯一覆盖 Medallion + FHV |
| `license_type` | 牌照类型 | VARCHAR | `License Type` | `active_vehicles` | For Hire Vehicle / Medallion / Stand By / Paratransit / Commuter Van |
| `license_status` | 牌照状态 | VARCHAR | `TLC Vehicle License Status` / `Current Status` | `active_vehicles` | Current / Suspended |
| `owner_name` | 车主姓名/公司名 | VARCHAR | `Owner Name` / `Name` | `active_vehicles` | 所有权人 |
| `expiration_date` | 牌照到期日期 | DATE | `Expiration Date` | `active_vehicles` | VARCHAR→DATE |
| `dmv_plate_number` | DMV车牌号 | VARCHAR | `DMV Plate Number` / `DMV License Plate Number` | `active_vehicles` | 覆盖最全 |
| `vin` | 车辆识别码 | VARCHAR | `VIN` / `Vehicle VIN Number` | `active_vehicles` | 17 位 VIN |
| `vehicle_make` | 车辆品牌 | VARCHAR | `Vehicle Make` | `active_vehicles` | Toyota、Honda 等 |
| `vehicle_model` | 车辆型号 | VARCHAR | `Vehicle Model` | `active_vehicles` | Camry、Suburban 等 |
| `vehicle_year` | 车辆年份 | INTEGER | `Vehicle Year` / `Model Year` | `active_vehicles` | VARCHAR→INTEGER，2011-2026 |
| `fuel_type` | 燃料类型 | VARCHAR | `Fuel Type` | `active_vehicles` | 7 种分类最细 |
| `wav_flag` | 无障碍车辆标志 | VARCHAR | `WAV` / `Wheelchair Accessible` / `Vehicle Type` | `active_vehicles` | YES/NO/Pilot，缺失率 2.4% |
| `stretch_limo` | 是否加长豪华轿车 | VARCHAR | `Stretch Limo` | `active_vehicles` | YES/NO，active_vehicles 独有 |
| `medallion_type` | Medallion类型 | VARCHAR | `Medallion Type` | `medallion_authorized_vehicles` | Owner must driver / Named Driver |
| `base_number` | 基地编号 | VARCHAR | `Base Number` / `Affiliated Base/Agent Number` | `fhv_active_vehicles` | FHV 专有 |
| `base_name` | 基地名称 | VARCHAR | `Base Name` | `fhv_active_vehicles` | FHV 专有 |
| `base_type` | 基地类型 | VARCHAR | `Base Type` | `fhv_active_vehicles` | BLACK CAR / LUXURY / LIVERY |
| `base_address` | 基地地址 | VARCHAR | `Base Address` | `fhv_active_vehicles` | FHV 专有 |
| `agent_number` | 代理编号 | VARCHAR | `Agent Number` | `medallion_authorized_vehicles` | Medallion 专有 |
| `agent_name` | 代理名称 | VARCHAR | `Agent Name` | `medallion_authorized_vehicles` | 缺失率 47% |
| `insurance_carrier` | 保险公司名称 | VARCHAR | `Insurance Carrier Name` | `active_vehicles` | active_vehicles 独有 |
| `insurance_policy_number` | 保险单号 | VARCHAR | `Automobile Insurance Policy Number` | `active_vehicles` | active_vehicles 独有 |
| `last_date_updated` | 最后更新日期 | DATE | `Last Date Updated` | `active_vehicles` | VARCHAR→DATE |
| `source_table` | 来源表 | VARCHAR | 常量 | — | 记录来自哪张 Bronze 表 |

质量规则：

- `license_number` 不允许为空，必须唯一。
- `vehicle_year` < 2000 或 > 2027 时标记质量问题。
- `wav_flag` 为空时标记为 `UNKNOWN`。
- `expiration_date` 早于 `2026-01-01` 时标记为已过期。

### silver.driver_detail（司机明细标准表）

来源：

| 英文表名 | 中文表名 | 行数 | 主键 |
|---|---|---|---|
| `bronze.fhv_active_drivers` | FHV活跃驾驶员表 | 179,773 | `License Number`（唯一） |
| `bronze.shl_active_drivers` | SHL活跃司机表 | 180,236 | `License Number`（唯一） |

合并策略：UNION ALL 后以 `license_number` + `driver_type` 为复合主键（同一人可能同时持有 FHV 和 SHL 牌照）。

完整字段设计：

| 英文字段名 | 中文字段名 | 类型 | 来源映射 | 说明 |
|---|---|---|---|---|
| `driver_id` | 司机代理主键 | BIGINT | 生成 | PK，自增 |
| `license_number` | 司机牌照号 | VARCHAR | `License Number` | 来自两表 |
| `driver_name` | 司机姓名 | VARCHAR | `Name` | 司机全名 |
| `driver_type` | 司机类型 | VARCHAR | `Type` / 常量 | FHV=`FOR HIRE VEHICLE DRIVER`，SHL=`SHL DRIVER` |
| `status_code` | 状态码 | INTEGER | `Status Code` | SHL 独有，1/2/3 许可级别，VARCHAR→INTEGER |
| `status_description` | 状态描述 | VARCHAR | `Status Description` | SHL 独有 |
| `expiration_date` | 牌照到期日期 | DATE | `Expiration Date` | VARCHAR→DATE |
| `wav_trained` | 是否WAV培训 | VARCHAR | `Wheelchair Accessible Trained` | FHV 独有，WAV 或空 |
| `last_date_updated` | 最后更新日期 | DATE | `Last Date Updated` | VARCHAR→DATE |
| `last_time_updated` | 最后更新时间 | VARCHAR | `Last Time Updated` | HH:MM:SS |
| `source_table` | 来源表 | VARCHAR | 常量 | `fhv_active_drivers` / `shl_active_drivers` |

质量规则：

- `license_number` + `driver_type` 复合键不允许重复。
- `expiration_date` 早于 `2026-01-01` 时标记为已过期。

### silver.base_detail（基地月度明细标准表）

来源：

```text
bronze.fhv_base_aggregate_report  -- 58,923 行，9 列，全部 VARCHAR
```

**核心问题**：`Base License Number` 不唯一（1,117 唯一值 vs 58,923 行），需用复合键 `Base License Number + Year + Month`。

完整字段设计（全部 VARCHAR → 标准类型）：

| 英文字段名 | 中文字段名 | 新类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `base_detail_id` | 基地明细代理主键 | BIGINT | 生成 | PK，自增 |
| `base_license_number` | 基地牌照号 | VARCHAR | `Base License Number` | 1,117 个唯一值 |
| `base_name` | 基地名称 | VARCHAR | `Base Name` | 基地官方名称 |
| `dba` | 经营别名 | VARCHAR | `DBA` | Doing Business As，缺失率 80.7% |
| `year` | 年份 | INTEGER | `Year` | VARCHAR→INTEGER |
| `month` | 月份 | INTEGER | `Month` | VARCHAR→INTEGER |
| `month_name` | 月份名称 | VARCHAR | `Month Name` | January-December |
| `total_dispatched_trips` | 调度行程总数 | BIGINT | `Total Dispatched Trips` | VARCHAR→BIGINT |
| `total_dispatched_shared_trips` | 共享行程数 | BIGINT | `Total Dispatched Shared Trips` | VARCHAR→BIGINT |
| `unique_dispatched_vehicles` | 去重调度车辆数 | BIGINT | `Unique Dispatched Vehicles` | VARCHAR→BIGINT |
| `composite_key` | 复合键 | VARCHAR | 生成 | `base_license_number + '_' + year + '_' + month` |
| `is_duplicate_key` | 是否复合键重复 | BOOLEAN | 生成 | 复合键出现 > 1 次时为 TRUE |

### silver.driver_application_detail（司机申请明细标准表）

来源：

```text
bronze.new_driver_applications  -- 4,076 行，12 列，全部 VARCHAR
```

主键 `App No` 已唯一。

完整字段设计：

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `application_id` | 申请代理主键 | BIGINT | 生成 | PK，自增 |
| `app_no` | 申请编号 | VARCHAR | `App No` | 原始主键，格式如 `HDR001234` |
| `application_type` | 申请类型 | VARCHAR | `Type` | HDR：Medallion/FHV 司机 |
| `app_date` | 申请日期 | DATE | `App Date` | VARCHAR→DATE |
| `status` | 审批状态 | VARCHAR | `Status` | Incomplete / Pending Fitness Interview / Approved / Denied |
| `fru_interview_scheduled` | 体能审查面试状态 | VARCHAR | `FRU Interview Scheduled` | 面试安排状态 |
| `drug_test` | 药检状态 | VARCHAR | `Drug Test` | Needed / Passed / Not Applicable |
| `wav_course` | WAV培训状态 | VARCHAR | `WAV Course` | 无障碍车辆培训完成状态 |
| `defensive_driving` | 防御性驾驶状态 | VARCHAR | `Defensive Driving` | 6 小时 NYS 防御性驾驶课程 |
| `driver_exam` | 司机考试状态 | VARCHAR | `Driver Exam` | TLC 司机考试状态 |
| `medical_clearance_form` | 体检表状态 | VARCHAR | `Medical Clearance Form` | 医疗许可表提交状态 |
| `other_requirements` | 其他要求状态 | VARCHAR | `Other Requirements` | 其他审批材料 |
| `last_updated` | 最后更新日期 | DATE | `Last Updated` | VARCHAR→DATE |

---

## 第三批详细设计

### silver.parking_violation_detail（停车罚单明细标准表）

来源：

```text
bronze.parking_violations_all  -- 9,582,412 行，29 列，全部 VARCHAR
```

主键 `summons_number` 当前唯一，需在 Silver 层确认。

完整字段设计：

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `violation_id` | 罚单代理主键 | BIGINT | 生成 | PK，自增 |
| `summons_number` | 罚单编号 | VARCHAR | `summons_number` | 候选键，需验证唯一性 |
| `plate_id` | 车牌号 | VARCHAR | `plate_id` | 违章车辆车牌 |
| `registration_state` | 注册州 | VARCHAR | `registration_state` | 车辆注册所在州 |
| `plate_type` | 车牌类型 | VARCHAR | `plate_type` | 45 种类型 |
| `issue_date` | 开票日期 | DATE | `issue_date` | VARCHAR→DATE |
| `violation_code` | 违章代码 | VARCHAR | `violation_code` | 219 种违章代码 |
| `violation_description` | 违章描述 | VARCHAR | `violation_description` | 违章行为描述 |
| `vehicle_body_type` | 车身类型 | VARCHAR | `vehicle_body_type` | Sedan / SUV 等 |
| `vehicle_make` | 车辆品牌 | VARCHAR | `vehicle_make` | 罚单上手写品牌 |
| `vehicle_color` | 车辆颜色 | VARCHAR | `vehicle_color` | 罚单记录颜色 |
| `vehicle_year` | 车辆年份 | INTEGER | `vehicle_year` | VARCHAR→INTEGER |
| `vehicle_expiration_date` | 车辆注册到期日 | DATE | `vehicle_expiration_date` | VARCHAR→DATE |
| `issuing_agency` | 开票机构 | VARCHAR | `issuing_agency` | 执法机构代码 |
| `violation_precinct` | 违章管辖区 | VARCHAR | `violation_precinct` | 违章发生所在警区 |
| `issuer_precinct` | 开票管辖区 | VARCHAR | `issuer_precinct` | 开票警员所在警区 |
| `issuer_code` | 开票人员代码 | VARCHAR | `issuer_code` | 执法人员编号 |
| `violation_time` | 违章时间 | VARCHAR | `violation_time` | 违章发生具体时间 |
| `violation_county` | 违章所在县 | VARCHAR | `violation_county` | 如 NY（纽约县）、K（国王县） |
| `street_name` | 街道名称 | VARCHAR | `street_name` | 违章地点街道名 |
| `intersecting_street` | 交叉街道 | VARCHAR | `intersecting_street` | 缺失率 48.7% |
| `date_first_observed` | 首次观察日期 | VARCHAR | `date_first_observed` | 首次发现违章日期 |
| `law_section` | 法律条款 | VARCHAR | `law_section` | 违章对应法律条款 |
| `sub_division` | 法律子条款 | VARCHAR | `sub_division` | 法律子条款编号 |
| `violation_legal_code` | 违章法律代码 | VARCHAR | `violation_legal_code` | 缺失率 57.2% |
| `feet_from_curb` | 距路缘英尺数 | VARCHAR | `feet_from_curb` | 车辆距路缘距离 |
| `fiscal_year` | 财年 | INTEGER | `fiscal_year` | VARCHAR→INTEGER |

质量标记：

| 英文字段名 | 中文字段名 | 类型 | 说明 |
|---|---|---|---|
| `is_duplicate_summons` | 是否重复罚单 | BOOLEAN | `summons_number` 出现 > 1 次时为 TRUE |
| `source_row_hash` | 来源行哈希 | VARCHAR(64) | MD5 溯源 |

质量规则：

- `summons_number` 需验证唯一性。
- `issue_date` 不在 2025-07-01 ~ 2026-06-30（2026 财年）范围内时标记。
- `violation_code` 不允许为空。

> **注意**：Bronze 层 `parking_violations_all` 无金额字段（无 `fine_amount`、`penalty_amount` 等），罚款金额需从官方数据字典 `Parking_Violations_Issued_Data_Dictionary.xlsx` 的 Violation Codes sheet 按 `violation_code` 关联获取，在 Gold 层做 JOIN 补充。

### silver.tif_payment_detail（TIF支付明细标准表）

来源：

```text
bronze.tif_medallion_payments  -- 48,431 行，8 列，全部 VARCHAR
```

**核心问题**：`License Number` 不唯一（6,115 唯一值 vs 48,431 行），需用复合键 `License Number + Payment Date`。

完整字段设计（全部 VARCHAR → 标准类型）：

| 英文字段名 | 中文字段名 | 新类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `payment_id` | 支付代理主键 | BIGINT | 生成 | PK，自增 |
| `license_number` | 牌照号 | VARCHAR | `License Number` | Medallion 牌照编号 |
| `agent_number` | 代理编号 | VARCHAR | `Agent Number` | 管理代理编号，缺失率 47.6% |
| `hackup_payment_amount` | 改装支付金额 | DECIMAL(12,2) | `Hackup Payment Amount` | WAV 车辆改装成功后的支付 |
| `operational_payment_amount` | 运营支付金额 | DECIMAL(12,2) | `Operational Payment Amount` | 三年度检查成功后支付（$1,333/次） |
| `total_payment_amount` | 总支付金额 | DECIMAL(12,2) | `Total Payment Amount` | 改装 + 运营支付合计 |
| `payment_date` | 支付日期 | DATE | `Payment Date` | VARCHAR→DATE |
| `last_date_updated` | 最后更新日期 | DATE | `Last Date Updated` | VARCHAR→DATE |
| `last_time_updated` | 最后更新时间 | VARCHAR | `Last Time Updated` | HH:MM:SS |
| `composite_key` | 复合键 | VARCHAR | 生成 | `license_number + '_' + payment_date` |
| `is_duplicate_key` | 是否复合键重复 | BOOLEAN | 生成 | 复合键出现 > 1 次时为 TRUE |

### silver.crash_detail（事故明细标准表）

来源：

```text
bronze.crash_merged  -- 1,655,065 行，29 列，全部 VARCHAR
```

主键 `collision_id` 当前唯一。仅保留缺失率 < 95% 的字段（弃用车辆 3-5 列）。

完整字段设计：

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `collision_id` | 事故编号 | BIGINT | `collision_id` | PK，VARCHAR→BIGINT |
| `crash_at` | 事故时间 | TIMESTAMP | `crash_date` + `crash_time` | VARCHAR 合并→TIMESTAMP |
| `borough` | 行政区 | VARCHAR | `borough` | 缺失率 30.4% |
| `zip_code` | 邮政编码 | VARCHAR | `zip_code` | 缺失率 30.4% |
| `latitude` | 纬度 | DOUBLE | `latitude` | VARCHAR→DOUBLE，WGS84 |
| `longitude` | 经度 | DOUBLE | `longitude` | VARCHAR→DOUBLE，WGS84 |
| `on_street_name` | 所在街道 | VARCHAR | `on_street_name` | 事故发生所在街道 |
| `cross_street_name` | 交叉街道 | VARCHAR | `cross_street_name` | 缺失率 82.0% |
| `off_street_name` | 非街道地址 | VARCHAR | `off_street_name` | 缺失率 38.4% |

伤亡统计字段（VARCHAR→INTEGER）：

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `persons_injured` | 受伤总人数 | INTEGER | `number_of_persons_injured` | VARCHAR→INTEGER |
| `persons_killed` | 死亡总人数 | INTEGER | `number_of_persons_killed` | VARCHAR→INTEGER |
| `pedestrians_injured` | 行人受伤数 | INTEGER | `number_of_pedestrians_injured` | VARCHAR→INTEGER |
| `pedestrians_killed` | 行人死亡数 | INTEGER | `number_of_pedestrians_killed` | VARCHAR→INTEGER |
| `cyclist_injured` | 骑行者受伤数 | INTEGER | `number_of_cyclist_injured` | VARCHAR→INTEGER |
| `cyclist_killed` | 骑行者死亡数 | INTEGER | `number_of_cyclist_killed` | VARCHAR→INTEGER |
| `motorist_injured` | 驾驶员受伤数 | INTEGER | `number_of_motorist_injured` | VARCHAR→INTEGER |
| `motorist_killed` | 驾驶员死亡数 | INTEGER | `number_of_motorist_killed` | VARCHAR→INTEGER |

涉事车辆字段（仅保留车辆 1-2，车辆 3-5 缺失率 93-99% 已弃用）：

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `vehicle_type_1` | 涉事车辆1类型 | VARCHAR | `vehicle_type_code1` | 碰撞中第 1 辆车类型 |
| `vehicle_type_2` | 涉事车辆2类型 | VARCHAR | `vehicle_type_code2` | 碰撞中第 2 辆车类型 |
| `contributing_factor_1` | 车辆1事故因素 | VARCHAR | `contributing_factor_vehicle_1` | 导致碰撞的因素（车辆1） |
| `contributing_factor_2` | 车辆2事故因素 | VARCHAR | `contributing_factor_vehicle_2` | 导致碰撞的因素（车辆2） |

质量标记：

| 英文字段名 | 中文字段名 | 类型 | 说明 |
|---|---|---|---|
| `is_duplicate_collision` | 是否重复事故 | BOOLEAN | `collision_id` 出现 > 1 次时为 TRUE |
| `is_location_missing` | 是否位置缺失 | BOOLEAN | `latitude` 或 `longitude` IS NULL 时为 TRUE |
| `source_table` | 来源表 | VARCHAR | 固定值 `crash_merged` |
| `source_row_hash` | 来源行哈希 | VARCHAR(64) | MD5 溯源 |

质量规则：

- `collision_id` 需验证唯一性。
- `crash_at` 不能为 NULL。
- `persons_injured` < 0 或 > 100 时标记为异常。

### silver.crash_person_detail（事故人员明细标准表）

来源：

```text
bronze.crash_person_all  -- 5,333,042 行，21 列，全部 VARCHAR
```

主键 `unique_id` 当前唯一。仅保留缺失率 < 50% 的辅助字段。

完整字段设计：

核心标识字段：

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `unique_id` | 人员记录编号 | BIGINT | `unique_id` | PK，VARCHAR→BIGINT |
| `collision_id` | 事故编号 | BIGINT | `collision_id` | 外键，关联 `silver.crash_detail.collision_id` |
| `crash_date` | 事故日期 | DATE | `crash_date` | VARCHAR→DATE |
| `crash_time` | 事故时间 | VARCHAR | `crash_time` | HH:MM 格式 |
| `person_id` | 人员编号 | VARCHAR | `person_id` | 事故内人员序号 |

人员属性字段：

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `person_type` | 人员类型 | VARCHAR | `person_type` | 驾驶员 / 乘客 / 行人 / 骑行者 |
| `person_injury` | 伤害程度 | VARCHAR | `person_injury` | 受伤 / 死亡等级别 |
| `person_sex` | 性别 | VARCHAR | `person_sex` | 性别标识 |
| `person_age` | 年龄 | INTEGER | `person_age` | VARCHAR→INTEGER |
| `vehicle_id` | 涉事车辆ID | VARCHAR | `vehicle_id` | 关联涉事车辆信息 |
| `ped_role` | 行人角色 | VARCHAR | `ped_role` | 行人的具体角色 |

辅助字段（缺失率 46-49%，保留但标注质量）：

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 缺失率 | 说明 |
|---|---|---|---|---|---|
| `ejection` | 是否弹出 | VARCHAR | `ejection` | 48.6% | 人员是否被弹出车外 |
| `emotional_status` | 情绪状态 | VARCHAR | `emotional_status` | 46.9% | 人员当时情绪状态 |
| `bodily_injury` | 身体伤害 | VARCHAR | `bodily_injury` | 46.9% | 身体伤害描述 |
| `position_in_vehicle` | 车内位置 | VARCHAR | `position_in_vehicle` | 48.6% | 人员在车内的座位位置 |
| `safety_equipment` | 安全设备 | VARCHAR | `safety_equipment` | 48.6% | 使用的安全设备（安全带等） |
| `complaint` | 投诉信息 | VARCHAR | `complaint` | 46.9% | 人员投诉信息 |

质量标记：

| 英文字段名 | 中文字段名 | 类型 | 说明 |
|---|---|---|---|
| `is_duplicate_person` | 是否重复记录 | BOOLEAN | `unique_id` 出现 > 1 次时为 TRUE |
| `is_orphan_record` | 是否孤立记录 | BOOLEAN | `collision_id` 在 `silver.crash_detail` 中不存在时为 TRUE |
| `has_missing_aux` | 是否缺失辅助字段 | BOOLEAN | 6 个辅助字段全部为 NULL 时为 TRUE |
| `source_table` | 来源表 | VARCHAR | 固定值 `crash_person_all` |
| `source_row_hash` | 来源行哈希 | VARCHAR(64) | MD5 溯源 |

质量规则：

- `unique_id` 需验证唯一性。
- `collision_id` 需验证与 `silver.crash_detail.collision_id` 的覆盖关系（当前覆盖不完全）。
- `person_age` < 0 或 > 120 时标记为异常。
- 弃用字段（缺失率 ≥ 50%）：`ped_location`（98.2%）、`ped_action`（98.2%）、`contributing_factor_1`（98.2%）、`contributing_factor_2`（98.2%）。

---

## Silver 表必须同步写入 Meta

每建一张 Silver 表，必须同步写入两张 Meta 注释表：

```text
meta.table_comments   -- 表级中文注释
meta.column_comments  -- 字段级中文注释
```

最低要求：

| 英文对象 | 中文对象 | 说明 |
|---|---|---|
| `table_name` | 英文表名 | 例如 `silver.trip_detail` |
| `table_name_zh` | 中文表名 | 例如"行程明细标准表" |
| `column_name` | 英文字段名 | 例如 `pickup_at` |
| `column_name_zh` | 中文字段名 | 例如"接客时间" |
| `data_type` | 数据类型 | 例如 `TIMESTAMP` |
| `column_role_zh` | 字段角色 | 主键 / 时间字段 / 空间字段 / 金额字段 / 维度外键 / 标志位 / 质量标记 / 溯源字段 |

## Silver 表完整清单

| 批次 | 英文表名 | 中文表名 | 数据域 | 数据角色 | 字段数 | 预计行数 | 主键/候选键 |
|---|---|---|---|---|---|---|---|---|
| P0 | `silver.dim_date` | 日期维表 | 通用 | 维表 | 10 | ~90 | `date_key` |
| P0 | `silver.taxi_zone` | 出租车区域标准维表 | 空间地理域 | 维表 | 5 | 265 | `location_id` |
| P0 | `silver.trip_detail` | 行程明细标准表 | 出行域 | 事实表 | 39 | 8,032 万 | `trip_id`（代理键） |
| P1 | `silver.vehicle_detail` | 车辆明细标准表 | 资产域 | 维表 | 25 | ~12 万 | `vehicle_id`（代理键） |
| P1 | `silver.driver_detail` | 司机明细标准表 | 供给域 | 维表 | 11 | ~36 万 | `license_number` + `driver_type` |
| P1 | `silver.base_detail` | 基地月度明细标准表 | 供给域 | 事实表 | 12 | ~5.9 万 | `composite_key` |
| P1 | `silver.driver_application_detail` | 司机申请明细标准表 | 监管合规域 | 事实表 | 14 | 4,076 | `app_no` |
| P2 | `silver.parking_violation_detail` | 停车罚单明细标准表 | 监管合规域 | 事实表 | 33 | 958 万 | `violation_id`（代理键） | `bronze.parking_violations_all` |
| P2 | `silver.tif_payment_detail` | TIF支付明细标准表 | 监管合规域 | 事实表 | 12 | ~4.8 万 | `payment_id`（代理键） |
| P2 | `silver.crash_detail` | 事故明细标准表 | 安全域 | 事实表 | 26 | 166 万 | `crash_id`（代理键） |
| P2 | `silver.crash_person_detail` | 事故人员明细标准表 | 安全域 | 事实表 | 24 | 533 万 | `crash_person_id`（代理键） |

## 下一步执行建议

第一步先实现 P0：

```text
silver.dim_date
silver.taxi_zone
silver.trip_detail
meta.table_comments
meta.column_comments
```

这一步完成后，纽约市城市交通数据底座就具备最小可用 Silver 层：

```text
日期维表 + 空间维表 + 出行明细事实（8,032 万行）
```

后续再逐步扩展到车辆、司机、基地、罚单、事故。
