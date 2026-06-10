# Gold 层数据库设计文档

> **事实源层级**：本文件是 Gold 层正式设计入口。Gold 建模只能基于 Silver 标准层、Meta 中文注释、字段字典和已审核业务口径，不得跳过 Silver 直接读取 Bronze。

## 1. 当前状态

| 项目 | 内容 |
|---|---|
| 英文 Schema | `gold` |
| 中文 Schema | 主题分析层 |
| 当前状态 | G0/G1 维表和 G2 明细事实表已正式建表，G3 汇总表尚未建设 |
| 上游依赖 | `silver` 标准层、`meta.table_comments`、`meta.column_comments`、字段字典、枚举值字典 |
| 前置门禁 | `check_schema_consistency.py --require-silver-tables`、`check_gold_design.py`、`check_gold_physical.py --batches G0,G1,G2` 必须通过 |
| 设计目标 | 面向中文工程师、BI、Text2SQL Agent 和数据分析 Agent 的主题星型模型 |

## 2. Gold 层设计原则

### 2.1 英文物理名 + 中文语义名

Gold 物理表名和字段名继续使用英文，避免 SQL、BI、ETL、DuckDB 兼容问题。

但每一张 Gold 表、每一个 Gold 字段都必须同步维护中文名：

- 表中文名写入 `meta.table_comments`
- 字段中文名写入 `meta.column_comments`
- 指标中文名写入后续 `meta.metric_definitions`
- 问数口径写入中文语义层

示例：

| 英文表名 | 中文表名 |
|---|---|
| `gold.fact_trips` | 出行事实表 |
| `gold.dim_vehicle` | 车辆维表 |

| 英文字段名 | 中文字段名 |
|---|---|
| `trip_id` | 行程代理主键 |
| `pickup_date_key` | 接客日期键 |
| `total_amount` | 总费用 |

### 2.2 不使用 Google 翻译直接生成正式中文名

Gold 层面向中文工程师使用，确实需要审查 Silver 字段中文名，但**不建议把字段名交给 Google 翻译直接生成正式中文名**。

原因：

1. 字段名不是普通翻译，而是业务术语。`base` 在 TLC 语境中是“营运基地”，不是普通“基础”。
2. 缩写和状态码需要领域解释。`FHV`、`SHL`、`TIF`、`WAV` 不能靠通用翻译。
3. 同一英文词在不同表中含义不同。`type` 可能是车辆类型、申请类型、人员类型或牌照类型。
4. 机器翻译容易产生多个同义中文名，破坏中文问数一致性。

推荐规则：

| 来源优先级 | 中文名来源 | 是否可直接进入 Gold |
|---|---|---|
| 1 | `meta.column_comments` 中已审核中文名 | 可以 |
| 2 | Silver 数据字典 xlsx 中字段中文名 | 可以，但需与 meta 对齐 |
| 3 | 官方数据字典中的中文整理结果 | 可以，但需标注来源 |
| 4 | 项目人工维护术语表 | 可以 |
| 5 | Google 翻译、LLM 翻译 | 只能作草稿，必须 Human Review |

结论：

> Gold 需要审查 Silver 字段中文名，但应采用“受控中文术语表 + 人工审核 + meta 注释同步”，不能把 Google 翻译作为事实源。

### 2.3 Gold 不重复 Silver 的脏数据处理

Silver 已经处理的内容，Gold 不重复实现：

- 字段重命名
- 类型转换
- 日期解析
- 金额清洗
- 基础质量标记
- 来源表记录

Gold 只做：

- 主题建模
- 事实表和维表组织
- 指标计算
- 汇总表
- 中文语义层

### 2.4 高缺失字段进入 Gold 的规则

Silver 空值画像中高缺失字段分三类：

| 类型 | Gold 处理规则 | 示例 |
|---|---|---|
| 源表适用范围导致稀疏 | 可进入 Gold，但字段说明必须写明适用范围 | `trip_detail.total_amount` 仅 Yellow/Green 有值 |
| 可选业务属性 | 可进入维表，但不作为核心筛选条件 | `vehicle_detail.agent_name` |
| 已废弃或全 NULL | 默认不进入 Gold，除非保留为兼容字段 | `trip_detail.ehail_fee` |

## 3. Gold 层模型总览

Gold 采用“主题星型模型 + 事故 ER 子模型 + 中文语义层”的组合。

```text
gold
├─ 公共维表
│  ├─ dim_date              # 日期维表
│  ├─ dim_taxi_zone         # 出租车区域维表
│  ├─ dim_vehicle           # 车辆维表
│  ├─ dim_driver            # 司机维表
│  ├─ dim_base              # 基地维表
│  └─ dim_violation_type    # 违章类型维表
├─ 事实表
│  ├─ fact_trips                    # 出行事实表
│  ├─ fact_parking_violations       # 停车罚单事实表
│  ├─ fact_tif_payments             # TIF支付事实表
│  ├─ fact_driver_applications      # 司机申请事实表
│  ├─ fact_crashes                  # 事故事实表
│  └─ fact_crash_persons            # 事故人员事实表
└─ 汇总表（第二阶段）
   ├─ dws_daily_trip_summary        # 每日出行汇总表
   ├─ dws_zone_trip_summary         # 区域出行汇总表
   ├─ dws_daily_parking_summary     # 每日罚单汇总表
   └─ dws_daily_crash_summary       # 每日事故汇总表
```

## 4. 第一阶段 Gold 表清单

| 英文表名 | 中文表名 | 来源 Silver 表 | 数据域 | 数据角色 | 粒度 | 主键 | 建设批次 |
|---|---|---|---|---|---|---|---|
| `gold.dim_date` | 日期维表 | `silver.dim_date` | 通用 | 维表 | 一天一行 | `date_key` | G0 |
| `gold.dim_taxi_zone` | 出租车区域维表 | `silver.taxi_zone` | 空间地理域 | 维表 | 一个出租车区域一行 | `location_id` | G0 |
| `gold.dim_vehicle` | 车辆维表 | `silver.vehicle_detail` | 资产域 | 维表 | 一辆车一行 | `vehicle_key` | G1 |
| `gold.dim_driver` | 司机维表 | `silver.driver_detail` | 供给域 | 维表 | 一个司机牌照一行 | `driver_key` | G1 |
| `gold.dim_base` | 基地维表 | `silver.base_detail`、`silver.vehicle_detail` | 供给域 | 维表 | 一个基地一行 | `base_key` | G1 |
| `gold.dim_violation_type` | 违章类型维表 | 官方数据字典 + `silver.parking_violation_detail` | 监管合规域 | 维表 | 一个违章代码一行 | `violation_code` | G1 |
| `gold.fact_trips` | 出行事实表 | `silver.trip_detail` | 出行域 | 事实表 | 一次行程一行 | `trip_id` | G2 |
| `gold.fact_parking_violations` | 停车罚单事实表 | `silver.parking_violation_detail` | 监管合规域 | 事实表 | 一张罚单一行 | `violation_id` | G2 |
| `gold.fact_tif_payments` | TIF支付事实表 | `silver.tif_payment_detail` | 监管合规域 | 事实表 | 一次支付一行 | `payment_id` | G2 |
| `gold.fact_driver_applications` | 司机申请事实表 | `silver.driver_application_detail` | 监管合规域 | 事实表 | 一次申请一行 | `application_id` | G2 |
| `gold.fact_crashes` | 事故事实表 | `silver.crash_detail` | 安全域 | 事实表 | 一次事故一行 | `crash_id` | G2 |
| `gold.fact_crash_persons` | 事故人员事实表 | `silver.crash_person_detail` | 安全域 | 事实表 | 一名涉事人员一行 | `crash_person_id` | G2 |

## 5. 公共维表设计

### 5.1 `gold.dim_date` 日期维表

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `date_key` | 日期键 | INTEGER | `silver.dim_date.date_key` | 主键，YYYYMMDD |
| `date` | 日期 | DATE | `silver.dim_date.date` | 标准日期 |
| `year` | 年 | INTEGER | `silver.dim_date.year` | 自然年 |
| `quarter` | 季度 | INTEGER | `silver.dim_date.quarter` | 自然季度 |
| `month` | 月 | INTEGER | `silver.dim_date.month` | 月份 |
| `week` | ISO周号 | INTEGER | `silver.dim_date.week` | ISO周 |
| `day_of_week` | 星期几 | INTEGER | `silver.dim_date.day_of_week` | 1=周一，7=周日 |
| `day_of_week_name` | 星期名称 | VARCHAR | `silver.dim_date.day_of_week_name` | 英文星期名 |
| `is_weekend` | 是否周末 | BOOLEAN | `silver.dim_date.is_weekend` | 周六/周日 |
| `fiscal_year` | NYC财年 | INTEGER | `silver.dim_date.fiscal_year` | NYC 财年 |

### 5.2 `gold.dim_taxi_zone` 出租车区域维表

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `location_id` | 出租车区域编号 | INTEGER | `silver.taxi_zone.location_id` | 主键 |
| `borough` | 行政区 | VARCHAR | `silver.taxi_zone.borough` | Manhattan、Queens 等 |
| `zone_name` | 区域名称 | VARCHAR | `silver.taxi_zone.zone_name` | TLC 区域名 |
| `service_zone` | 服务区域 | VARCHAR | `silver.taxi_zone.service_zone` | Yellow Zone、Boro Zone 等 |
| `is_unknown_zone` | 是否未知区域 | BOOLEAN | `silver.taxi_zone.is_unknown_zone` | 质量标记 |

### 5.3 `gold.dim_vehicle` 车辆维表

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `vehicle_key` | 车辆维表代理键 | BIGINT | `silver.vehicle_detail.vehicle_id` | Gold 车辆维表主键 |
| `license_number` | 牌照编号 | VARCHAR | `silver.vehicle_detail.license_number` | 车辆牌照号 |
| `license_type` | 牌照类型 | VARCHAR | `silver.vehicle_detail.license_type` | TLC 牌照类型 |
| `license_status` | 牌照状态 | VARCHAR | `silver.vehicle_detail.license_status` | 当前牌照状态 |
| `owner_name` | 车主姓名或公司名 | VARCHAR | `silver.vehicle_detail.owner_name` | 车辆所有者 |
| `expiration_date` | 牌照到期日期 | DATE | `silver.vehicle_detail.expiration_date` | 可用于有效性分析 |
| `dmv_plate_number` | DMV车牌号 | VARCHAR | `silver.vehicle_detail.dmv_plate_number` | DMV 车牌 |
| `vin` | 车辆识别码 | VARCHAR | `silver.vehicle_detail.vin` | VIN |
| `vehicle_make` | 车辆品牌 | VARCHAR | `silver.vehicle_detail.vehicle_make` | 品牌 |
| `vehicle_model` | 车辆型号 | VARCHAR | `silver.vehicle_detail.vehicle_model` | 型号 |
| `vehicle_year` | 车辆年份 | INTEGER | `silver.vehicle_detail.vehicle_year` | 年款 |
| `fuel_type` | 燃料类型 | VARCHAR | `silver.vehicle_detail.fuel_type` | 燃料分类 |
| `wav_flag` | 无障碍车辆标志 | VARCHAR | `silver.vehicle_detail.wav_flag` | WAV |
| `stretch_limo` | 是否加长豪华轿车 | VARCHAR | `silver.vehicle_detail.stretch_limo` | 标志位 |
| `medallion_type` | Medallion类型 | VARCHAR | `silver.vehicle_detail.medallion_type` | 仅少量 Medallion 车辆有值 |
| `base_number` | 基地编号 | VARCHAR | `silver.vehicle_detail.base_number` | FHV 相关 |
| `base_name` | 基地名称 | VARCHAR | `silver.vehicle_detail.base_name` | FHV 相关 |
| `base_type` | 基地类型 | VARCHAR | `silver.vehicle_detail.base_type` | FHV 相关 |
| `base_address` | 基地地址 | VARCHAR | `silver.vehicle_detail.base_address` | FHV 相关 |
| `agent_number` | 代理编号 | VARCHAR | `silver.vehicle_detail.agent_number` | Medallion 相关 |
| `agent_name` | 代理名称 | VARCHAR | `silver.vehicle_detail.agent_name` | Medallion 相关 |
| `insurance_carrier` | 保险公司名称 | VARCHAR | `silver.vehicle_detail.insurance_carrier` | 保险信息 |
| `insurance_policy_number` | 保险单号 | VARCHAR | `silver.vehicle_detail.insurance_policy_number` | 保险信息 |
| `last_date_updated` | 最后更新日期 | DATE | `silver.vehicle_detail.last_date_updated` | 数据更新时间 |

### 5.4 `gold.dim_driver` 司机维表

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `driver_key` | 司机维表代理键 | BIGINT | `silver.driver_detail.driver_id` | 主键 |
| `license_number` | 司机牌照号 | VARCHAR | `silver.driver_detail.license_number` | 司机牌照 |
| `driver_name` | 司机姓名 | VARCHAR | `silver.driver_detail.driver_name` | 司机姓名 |
| `driver_type` | 司机类型 | VARCHAR | `silver.driver_detail.driver_type` | FHV / SHL |
| `status_code` | 状态码 | INTEGER | `silver.driver_detail.status_code` | SHL 有值 |
| `status_description` | 状态描述 | VARCHAR | `silver.driver_detail.status_description` | SHL 状态 |
| `expiration_date` | 牌照到期日期 | DATE | `silver.driver_detail.expiration_date` | 司机牌照到期 |
| `wav_trained` | 是否WAV培训 | VARCHAR | `silver.driver_detail.wav_trained` | FHV 有值，SHL 稀疏 |
| `last_date_updated` | 最后更新日期 | DATE | `silver.driver_detail.last_date_updated` | 数据更新时间 |

### 5.5 `gold.dim_base` 基地维表

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `base_key` | 基地维表代理键 | BIGINT | 派生 | 按 `base_license_number` 稳定生成 |
| `base_license_number` | 基地牌照号 | VARCHAR | `silver.base_detail.base_license_number` | 基地自然键 |
| `base_name` | 基地名称 | VARCHAR | `silver.base_detail.base_name` | 基地名称 |
| `dba` | 经营别名 | VARCHAR | `silver.base_detail.dba` | 可选字段，高缺失 |
| `base_type` | 基地类型 | VARCHAR | `silver.vehicle_detail.base_type` | 可从车辆表补充 |
| `base_address` | 基地地址 | VARCHAR | `silver.vehicle_detail.base_address` | 可从车辆表补充 |

### 5.6 `gold.dim_violation_type` 违章类型维表

`dim_violation_type` 是 Gold 前必须重点补齐的维表。Silver 罚单表没有金额字段，罚款金额不能凭空新增，必须来自官方数据字典或人工审核结果。

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `violation_code` | 违章代码 | VARCHAR | `silver.parking_violation_detail.violation_code` + 官方字典 | 主键 |
| `violation_description` | 违章描述 | VARCHAR | `silver.parking_violation_detail.violation_description` | 描述 |
| `standard_fine_amount` | 标准罚款金额 | DECIMAL(12,2) | 官方数据字典 | 待人工确认 |
| `penalty_amount` | 滞纳金金额 | DECIMAL(12,2) | 官方数据字典 | 待人工确认 |
| `source_status` | 来源状态 | VARCHAR | 派生 | `from_official_dictionary` / `missing_from_dictionary` |

## 6. 事实表设计

### 6.1 `gold.fact_trips` 出行事实表

粒度：一次行程一行。

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `trip_id` | 行程代理主键 | VARCHAR | `silver.trip_detail.trip_id` | 主键 |
| `trip_source` | 行程来源类型 | VARCHAR | `silver.trip_detail.trip_source` | yellow / green / fhv / fhvhv |
| `pickup_date_key` | 接客日期键 | INTEGER | `strftime(pickup_date, '%Y%m%d')` | 关联 `dim_date` |
| `pickup_location_id` | 上车区域编号 | INTEGER | `silver.trip_detail.pickup_location_id` | 关联 `dim_taxi_zone` |
| `dropoff_location_id` | 下车区域编号 | INTEGER | `silver.trip_detail.dropoff_location_id` | 关联 `dim_taxi_zone` |
| `base_no` | 派车基地编号 | VARCHAR | `silver.trip_detail.base_no` | 可关联 `dim_base` |
| `pickup_at` | 接客时间 | TIMESTAMP | `silver.trip_detail.pickup_at` | 明细时间 |
| `dropoff_at` | 送客时间 | TIMESTAMP | `silver.trip_detail.dropoff_at` | 明细时间 |
| `passenger_count` | 乘客人数 | BIGINT | `silver.trip_detail.passenger_count` | FHV/HV 稀疏 |
| `distance_miles` | 行程距离英里 | DOUBLE | `silver.trip_detail.distance_miles` | 度量 |
| `fare_amount` | 基础车费 | DECIMAL(12,2) | `silver.trip_detail.fare_amount` | 度量 |
| `total_amount` | 总费用 | DECIMAL(12,2) | `silver.trip_detail.total_amount` | Yellow/Green 适用 |
| `tip_amount` | 小费 | DECIMAL(12,2) | `silver.trip_detail.tip_amount` | 度量 |
| `tolls_amount` | 通行费 | DECIMAL(12,2) | `silver.trip_detail.tolls_amount` | 度量 |
| `driver_pay` | 司机净收入 | DECIMAL(12,2) | `silver.trip_detail.driver_pay` | HVFHV 适用 |
| `is_time_anomaly` | 是否时间异常 | BOOLEAN | `silver.trip_detail.is_time_anomaly` | 质量标记 |
| `is_location_missing` | 是否位置缺失 | BOOLEAN | `silver.trip_detail.is_location_missing` | 质量标记 |
| `is_distance_outlier` | 是否距离异常 | BOOLEAN | `silver.trip_detail.is_distance_outlier` | 质量标记 |

默认不进入 `fact_trips` 的字段：

- `ehail_fee`：当前全 NULL，保留在 Silver，不进入 Gold 第一阶段。
- `source_row_hash`：保留在 Silver，Gold 可只保留必要审计字段。

### 6.2 `gold.fact_parking_violations` 停车罚单事实表

粒度：一张罚单一行。

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `violation_id` | 罚单代理主键 | BIGINT | `silver.parking_violation_detail.violation_id` | 主键 |
| `summons_number` | 罚单编号 | VARCHAR | `silver.parking_violation_detail.summons_number` | 候选键 |
| `issue_date_key` | 开票日期键 | INTEGER | `issue_date` 派生 | 关联 `dim_date` |
| `violation_code` | 违章代码 | VARCHAR | `silver.parking_violation_detail.violation_code` | 关联 `dim_violation_type` |
| `plate_id` | 车牌号 | VARCHAR | `silver.parking_violation_detail.plate_id` | 退化维度 |
| `registration_state` | 注册州 | VARCHAR | `silver.parking_violation_detail.registration_state` | 退化维度 |
| `plate_type` | 车牌类型 | VARCHAR | `silver.parking_violation_detail.plate_type` | 退化维度 |
| `vehicle_body_type` | 车身类型 | VARCHAR | `silver.parking_violation_detail.vehicle_body_type` | 退化维度 |
| `vehicle_make` | 车辆品牌 | VARCHAR | `silver.parking_violation_detail.vehicle_make` | 退化维度 |
| `vehicle_year` | 车辆年份 | INTEGER | `silver.parking_violation_detail.vehicle_year` | 0 表示未记录 |
| `violation_county` | 违章所在县 | VARCHAR | `silver.parking_violation_detail.violation_county` | 空间属性 |
| `violation_precinct` | 违章管辖区 | VARCHAR | `silver.parking_violation_detail.violation_precinct` | 空间属性 |
| `issuing_agency` | 开票机构 | VARCHAR | `silver.parking_violation_detail.issuing_agency` | 执法机构 |
| `feet_from_curb` | 距路缘英尺数 | DOUBLE | `silver.parking_violation_detail.feet_from_curb` | 度量 |
| `fiscal_year` | 财年 | INTEGER | `silver.parking_violation_detail.fiscal_year` | 财年 |
| `standard_fine_amount` | 标准罚款金额 | DECIMAL(12,2) | `gold.dim_violation_type.standard_fine_amount` | 官方字典标准金额 |
| `fine_source_status` | 罚款金额来源状态 | VARCHAR | `gold.dim_violation_type.source_status` | from_official_dictionary / missing_from_dictionary |
| `is_duplicate_summons` | 是否重复罚单 | BOOLEAN | `silver.parking_violation_detail.is_duplicate_summons` | 质量标记 |

金额字段规则：

> `standard_fine_amount` 已通过 `violation_code` 关联 `gold.dim_violation_type` 引入，来源为官方数据字典 Excel 中的标准罚款金额。它表示标准罚款金额，不代表实际缴纳金额、减免后金额或滞纳金金额。

### 6.3 `gold.fact_tif_payments` TIF支付事实表

粒度：一次支付一行。

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `payment_id` | 支付代理主键 | BIGINT | `silver.tif_payment_detail.payment_id` | 主键 |
| `license_number` | 牌照号 | VARCHAR | `silver.tif_payment_detail.license_number` | 可关联车辆 |
| `agent_number` | 代理编号 | VARCHAR | `silver.tif_payment_detail.agent_number` | 退化维度 |
| `payment_date_key` | 支付日期键 | INTEGER | `payment_date` 派生 | 关联 `dim_date` |
| `hackup_payment_amount` | 改装支付金额 | DECIMAL(12,2) | `silver.tif_payment_detail.hackup_payment_amount` | 度量 |
| `operational_payment_amount` | 运营支付金额 | DECIMAL(12,2) | `silver.tif_payment_detail.operational_payment_amount` | 度量 |
| `total_payment_amount` | 总支付金额 | DECIMAL(12,2) | `silver.tif_payment_detail.total_payment_amount` | 度量 |
| `is_duplicate_key` | 是否复合键重复 | BOOLEAN | `silver.tif_payment_detail.is_duplicate_key` | 质量标记 |

### 6.4 `gold.fact_driver_applications` 司机申请事实表

粒度：一次申请一行。

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `application_id` | 申请代理主键 | BIGINT | `silver.driver_application_detail.application_id` | 主键 |
| `app_no` | 申请编号 | VARCHAR | `silver.driver_application_detail.app_no` | 业务编号 |
| `application_type` | 申请类型 | VARCHAR | `silver.driver_application_detail.application_type` | PDR / VDR / HDR 等 |
| `app_date_key` | 申请日期键 | INTEGER | `app_date` 派生 | 关联 `dim_date` |
| `status` | 审批状态 | VARCHAR | `silver.driver_application_detail.status` | 状态 |
| `drug_test` | 药检状态 | VARCHAR | `silver.driver_application_detail.drug_test` | 状态 |
| `wav_course` | WAV培训状态 | VARCHAR | `silver.driver_application_detail.wav_course` | 状态 |
| `defensive_driving` | 防御性驾驶状态 | VARCHAR | `silver.driver_application_detail.defensive_driving` | 状态 |
| `driver_exam` | 司机考试状态 | VARCHAR | `silver.driver_application_detail.driver_exam` | 状态 |
| `last_updated` | 最后更新日期 | DATE | `silver.driver_application_detail.last_updated` | 数据更新时间 |

### 6.5 `gold.fact_crashes` 事故事实表

粒度：一次事故一行。

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `crash_id` | 事故代理主键 | BIGINT | `silver.crash_detail.crash_id` | 主键 |
| `collision_id` | 事故编号 | BIGINT | `silver.crash_detail.collision_id` | 自然键 |
| `crash_date_key` | 事故日期键 | INTEGER | `crash_at` 派生 | 关联 `dim_date` |
| `borough` | 行政区 | VARCHAR | `silver.crash_detail.borough` | 退化维度 |
| `zip_code` | 邮政编码 | VARCHAR | `silver.crash_detail.zip_code` | 退化维度 |
| `latitude` | 纬度 | DOUBLE | `silver.crash_detail.latitude` | 空间字段 |
| `longitude` | 经度 | DOUBLE | `silver.crash_detail.longitude` | 空间字段 |
| `persons_injured` | 受伤总人数 | INTEGER | `silver.crash_detail.persons_injured` | 度量 |
| `persons_killed` | 死亡总人数 | INTEGER | `silver.crash_detail.persons_killed` | 度量 |
| `pedestrians_injured` | 行人受伤数 | INTEGER | `silver.crash_detail.pedestrians_injured` | 度量 |
| `pedestrians_killed` | 行人死亡数 | INTEGER | `silver.crash_detail.pedestrians_killed` | 度量 |
| `cyclist_injured` | 骑行者受伤数 | INTEGER | `silver.crash_detail.cyclist_injured` | 度量 |
| `cyclist_killed` | 骑行者死亡数 | INTEGER | `silver.crash_detail.cyclist_killed` | 度量 |
| `motorist_injured` | 驾驶员受伤数 | INTEGER | `silver.crash_detail.motorist_injured` | 度量 |
| `motorist_killed` | 驾驶员死亡数 | INTEGER | `silver.crash_detail.motorist_killed` | 度量 |
| `vehicle_type_1` | 涉事车辆1类型 | VARCHAR | `silver.crash_detail.vehicle_type_1` | 分类 |
| `vehicle_type_2` | 涉事车辆2类型 | VARCHAR | `silver.crash_detail.vehicle_type_2` | 分类 |
| `contributing_factor_1` | 车辆1事故因素 | VARCHAR | `silver.crash_detail.contributing_factor_1` | 分类 |
| `contributing_factor_2` | 车辆2事故因素 | VARCHAR | `silver.crash_detail.contributing_factor_2` | 分类 |
| `is_location_missing` | 是否位置缺失 | BOOLEAN | `silver.crash_detail.is_location_missing` | 质量标记 |

### 6.6 `gold.fact_crash_persons` 事故人员事实表

粒度：一名涉事人员一行。

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `crash_person_id` | 事故人员代理主键 | BIGINT | `silver.crash_person_detail.crash_person_id` | 主键 |
| `unique_id` | 人员记录编号 | BIGINT | `silver.crash_person_detail.unique_id` | 自然键 |
| `collision_id` | 事故编号 | BIGINT | `silver.crash_person_detail.collision_id` | 关联事故 |
| `crash_date_key` | 事故日期键 | INTEGER | `crash_date` 派生 | 关联 `dim_date` |
| `person_type` | 人员类型 | VARCHAR | `silver.crash_person_detail.person_type` | 分类 |
| `person_injury` | 伤害程度 | VARCHAR | `silver.crash_person_detail.person_injury` | 分类 |
| `person_sex` | 性别 | VARCHAR | `silver.crash_person_detail.person_sex` | 分类 |
| `person_age` | 年龄 | INTEGER | `silver.crash_person_detail.person_age` | 度量 |
| `ped_role` | 行人角色 | VARCHAR | `silver.crash_person_detail.ped_role` | 分类 |
| `ejection` | 是否弹出 | VARCHAR | `silver.crash_person_detail.ejection` | 分类 |
| `emotional_status` | 情绪状态 | VARCHAR | `silver.crash_person_detail.emotional_status` | 状态 |
| `bodily_injury` | 身体伤害 | VARCHAR | `silver.crash_person_detail.bodily_injury` | 分类 |
| `position_in_vehicle` | 车内位置 | VARCHAR | `silver.crash_person_detail.position_in_vehicle` | 分类 |
| `safety_equipment` | 安全设备 | VARCHAR | `silver.crash_person_detail.safety_equipment` | 分类 |
| `is_orphan_record` | 是否孤立记录 | BOOLEAN | `silver.crash_person_detail.is_orphan_record` | 质量标记 |
| `is_age_anomaly` | 是否年龄异常 | BOOLEAN | `silver.crash_person_detail.is_age_anomaly` | 质量标记 |

事故人员表保留 ER 子模型特征：

- `fact_crash_persons.collision_id` → `fact_crashes.collision_id`
- 当前 Silver 已标记 `is_orphan_record`
- Gold 查询事故伤亡时，优先使用 `fact_crashes` 的事故级人数统计；做人员画像时使用 `fact_crash_persons`

## 7. 指标设计草案

| 英文指标名 | 中文指标名 | 来源表 | 计算公式 | 时间口径 | 审核状态 |
|---|---|---|---|---|---|
| `trip_count` | 行程量 | `gold.fact_trips` | `count(*)` | `pickup_date_key` | 待审核 |
| `total_fare_amount` | 基础车费总额 | `gold.fact_trips` | `sum(fare_amount)` | `pickup_date_key` | 待审核 |
| `total_trip_amount` | 行程总费用 | `gold.fact_trips` | `sum(total_amount)` | `pickup_date_key` | 待审核，仅 Yellow/Green |
| `avg_distance_miles` | 平均行程距离 | `gold.fact_trips` | `avg(distance_miles)` | `pickup_date_key` | 待审核 |
| `parking_violation_count` | 停车罚单量 | `gold.fact_parking_violations` | `count(*)` | `issue_date_key` | 待审核 |
| `tif_total_payment_amount` | TIF支付总额 | `gold.fact_tif_payments` | `sum(total_payment_amount)` | `payment_date_key` | 待审核 |
| `driver_application_count` | 司机申请量 | `gold.fact_driver_applications` | `count(*)` | `app_date_key` | 待审核 |
| `crash_count` | 事故量 | `gold.fact_crashes` | `count(*)` | `crash_date_key` | 待审核 |
| `persons_injured` | 受伤人数 | `gold.fact_crashes` | `sum(persons_injured)` | `crash_date_key` | 待审核 |
| `persons_killed` | 死亡人数 | `gold.fact_crashes` | `sum(persons_killed)` | `crash_date_key` | 待审核 |

## 8. Gold 建设批次

### G0：公共维表

1. `gold.dim_date`
2. `gold.dim_taxi_zone`

先建这两张，支撑时间和空间分析。

### G1：业务维表

1. `gold.dim_vehicle`
2. `gold.dim_driver`
3. `gold.dim_base`
4. `gold.dim_violation_type`

其中 `dim_violation_type` 需要先从官方数据字典抽取违章代码和金额口径，并标记审核状态。

### G2：明细事实表

1. `gold.fact_trips`
2. `gold.fact_parking_violations`
3. `gold.fact_tif_payments`
4. `gold.fact_driver_applications`
5. `gold.fact_crashes`
6. `gold.fact_crash_persons`

### G3：汇总表和语义层

1. 每日出行汇总
2. 区域出行汇总
3. 每日罚单汇总
4. 每日事故汇总
5. 中文指标口径
6. Text2SQL 问数模板

## 9. Gold 前置检查

Gold 建表前必须完成：

- [x] `check_schema_consistency.py --require-silver-tables` 通过
- [x] `check_silver_null.py` 通过或已建立高缺失字段基线
- [x] 每张 Gold G0/G1 表字段都有英文名和中文名
- [x] 不使用 Google 翻译结果直接作为正式中文名
- [x] Gold G0/G1 构建脚本写入 `meta.table_comments` 和 `meta.column_comments`
- [x] `check_gold_design.py` 通过
- [x] `check_gold_physical.py --batches G0,G1,G2` 通过
- [x] `dim_violation_type` 官方字典金额来源确认
- [x] G2 明细事实表字段来源已确认
- [ ] 每个 G3 汇总指标都有来源表、来源字段和计算公式

## 10. G0/G1 落库状态

当前 DuckDB 中已建设以下 Gold 维表：

| 英文表名 | 中文表名 | 行数 | 字段数 | 构建来源 | 状态 |
|---|---|---:|---:|---|---|
| `gold.dim_date` | 日期维表 | 90 | 10 | `silver.dim_date` | 已落库 |
| `gold.dim_taxi_zone` | 出租车区域维表 | 265 | 5 | `silver.taxi_zone` | 已落库 |
| `gold.dim_vehicle` | 车辆维表 | 119207 | 24 | `silver.vehicle_detail` | 已落库 |
| `gold.dim_driver` | 司机维表 | 360009 | 9 | `silver.driver_detail` | 已落库 |
| `gold.dim_base` | 基地维表 | 1117 | 6 | `silver.base_detail`、`silver.vehicle_detail` | 已落库 |
| `gold.dim_violation_type` | 违章类型维表 | 100 | 5 | `silver.parking_violation_detail`、官方数据字典 Excel | 已落库，标准罚款金额已导入 |

说明：

- `gold.dim_violation_type.standard_fine_amount` 当前来自官方数据字典 Excel，覆盖 97/100 个违章代码。
- `gold.dim_violation_type.penalty_amount` 因当前官方 Excel 不含滞纳金数据，继续保留为 `NULL`。
- `gold.fact_parking_violations.standard_fine_amount` 通过 `violation_code` 关联维表取得，表示标准罚款金额，不代表实际缴纳金额。
- G0/G1 的中文表名和中文字段名已写入 `meta.table_comments`、`meta.column_comments`。

## 11. G2 落库状态

当前 DuckDB 中已建设以下 Gold 明细事实表：

| 英文表名 | 中文表名 | 行数 | 字段数 | 构建来源 | 状态 |
|---|---|---:|---:|---|---|
| `gold.fact_trips` | 出行事实表 | 80324417 | 18 | `silver.trip_detail` | 已落库 |
| `gold.fact_parking_violations` | 停车罚单事实表 | 9582412 | 18 | `silver.parking_violation_detail`、`gold.dim_violation_type` | 已落库，已带入标准罚款金额 |
| `gold.fact_tif_payments` | TIF支付事实表 | 48431 | 8 | `silver.tif_payment_detail` | 已落库 |
| `gold.fact_driver_applications` | 司机申请事实表 | 4076 | 10 | `silver.driver_application_detail` | 已落库 |
| `gold.fact_crashes` | 事故事实表 | 1655065 | 20 | `silver.crash_detail` | 已落库 |
| `gold.fact_crash_persons` | 事故人员事实表 | 5333042 | 16 | `silver.crash_person_detail` | 已落库 |

停车罚单金额覆盖：

| 来源状态 | 中文说明 | 罚单行数 | 有标准罚款金额行数 |
|---|---|---:|---:|
| `from_official_dictionary` | 来自官方违章代码字典 | 9581483 | 9581483 |
| `missing_from_dictionary` | 源表违章代码未在官方字典匹配 | 929 | 0 |

`gold.fact_parking_violations.standard_fine_amount` 可用于估算标准罚款金额，总额当前为 `686536335.00`。该指标不是实际收款金额。
