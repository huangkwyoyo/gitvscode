# Text2SQL Agent 规则

> 从属于根 `AGENTS.md`。Text2SQL Agent 必须比数据开发 Agent 更保守。

## 1. 核心原则

Text2SQL Agent 只能基于已审核的语义层和数据库设计文档生成 SQL。不能为了满足用户问题而临时创造字段或指标。

## 2. 数据源优先级

1. Gold 层（已审核的指标和星型模型）
2. Silver 层（Gold 不存在时使用标准明细表）
3. Bronze 层（仅用于排查和追溯，不用于直接回答业务问题）

## 3. SQL 生成规则

- 优先使用 Gold 事实表和维度表的 JOIN
- Gold 不存在时使用 Silver 标准明细表
- 金额字段必须使用 DECIMAL 类型
- 日期字段使用标准 DATE/TIMESTAMP 类型
- 禁止使用 `DATE::INT`（DuckDB 不兼容）
- 禁止使用无序 `ROW_NUMBER() OVER ()`
- 所有表名使用全限定名（`silver.trip_detail` 而非 `trip_detail`）

## 4. 无法回答时的行为

以下情况必须拒绝生成 SQL 并说明原因：
- 需要的字段在 Silver/Gold 中不存在
- Join 关系未经人工确认
- 指标口径未经确认
- 业务含义不确定

拒绝时必须给出：
- 缺少什么字段/关系/口径
- 可能的替代方案
- 需要人工确认的内容

## 5. 中文口径

- 用户用中文提问时，Agent 必须先理解问题对应的业务指标（参考 meta.metric_definitions）
- 中文表名、中文字段名必须来自 Meta 元数据，不得自行翻译
- 输出的 SQL 注释必须使用中文

## 6. 查询路径决策树

遇到中文问数问题时，按以下优先级匹配推荐表：

### 6.1 维度查询（无指标要求）

| 查询内容 | 推荐表 | 说明 |
|---------|--------|------|
| 行政区列表 | `gold.dim_taxi_zone` | `SELECT DISTINCT borough` |
| 车辆信息（牌照类型、年份等） | `gold.dim_vehicle` | 车辆维表 |
| 司机信息（到期日期、状态等） | `gold.dim_driver` | 司机维表 |
| 基地信息 | `gold.dim_base` | 基地维表 |
| 违章类型描述 | `gold.dim_violation_type` | 含标准罚款金额 |
| 日期属性（年/月/季度/星期） | `gold.dim_date` | 1997-2027 全域日期维表 |

### 6.2 行程/出行分析（有指标要求）

| 查询粒度 | 推荐表 | 何时降级 |
|---------|--------|---------|
| 每日行程量/总车费/平均距离/接客里程 | `gold.dws_daily_trip_summary` | 几乎不需要降级 |
| 区域行程量/区域总车费 | `gold.dws_zone_trip_summary` | 需要按 borough 过滤时已内置支持 |
| 需要按行程来源类型（trip_source）分组 | 降级到 `gold.fact_trips` JOIN `gold.dim_date` | G3 汇总表不含 trip_source 维度 |
| 需要按车辆维度（牌照类型/年份）分组 | 降级到 `gold.fact_trips` JOIN `gold.dim_vehicle` | 通过 plate_no → base_license_number 关联 |
| 需要按司机维度分组 | 降级到 `gold.fact_trips` JOIN `gold.dim_driver` | G3 汇总表不含司机维度 |

### 6.3 停车罚单分析

| 查询粒度 | 推荐表 | 何时降级 |
|---------|--------|---------|
| 每日罚单量/标准罚款总额 | `gold.dws_daily_parking_summary`（或优先使用 `gold.v_parking_violations_valid`） | 需确认是否排除异常日期 |
| 需要按违章类型描述分组 | 降级到 `gold.fact_parking_violations` JOIN `gold.dim_violation_type` | G3 汇总表不含违章类型维度 |
| 需要按行政区分组 | 降级到 `gold.fact_parking_violations` | G3 汇总表不含行政区维度 |
| 车辆品牌/年份分布 | `gold.fact_parking_violations` | 退化维度已包含 plate_type、vehicle_year 等 |

### 6.4 事故分析

| 查询粒度 | 推荐表 | 何时降级 |
|---------|--------|---------|
| 每日事故量/死亡人数/受伤人数 | `gold.dws_daily_crash_summary` | 几乎不需要降级 |
| 需要按事故原因/车辆类型分组 | 降级到 `gold.fact_crashes` | G3 汇总表不含事故原因维度 |

### 6.5 TIF 支付分析

| 查询粒度 | 推荐表 | 何时降级 |
|---------|--------|---------|
| 每日支付总额/支付笔数 | `gold.fact_tif_payments` JOIN `gold.dim_date` | 无 G3 汇总表，直接使用 G2 |

### 6.6 司机申请分析

| 查询粒度 | 推荐表 | 何时降级 |
|---------|--------|---------|
| 每日申请量 | `gold.fact_driver_applications` JOIN `gold.dim_date` | 无 G3 汇总表，直接使用 G2 |

## 7. 日期范围过滤规则

1. **所有日期过滤必须通过 `gold.dim_date` 的 `date` 字段完成**，不得直接比较事实表中的整数 `date_key`。推荐写法：
   ```sql
   WHERE d.date BETWEEN DATE '2026-01-01' AND DATE '2026-03-31'
   ```
2. `dim_date` 当前覆盖 **1997-01-01 ~ 2027-12-31**（11,322 行）。超出此范围的日期键应视为异常。
3. **停车罚单异常日期提醒**：`fact_parking_violations.issue_date_key` 包含 1971、2060 及 2028+ 等异常值。
   - 优先使用 `gold.v_parking_violations_valid` 视图（INNER JOIN dim_date 自动过滤）
   - 直接查询基表时，建议加 `INNER JOIN gold.dim_date` 做隐式过滤
4. **出行数据时间范围**：`fact_trips` 主要为 2026 Q1 行程数据。查询其他时间段时可能为空。
5. **事故数据时间范围**：`fact_crashes` 覆盖历史事故数据，日期分布与行程数据不同。

## 8. 跨表 JOIN 白名单

### 8.1 已核准的 JOIN 路径

| 左表 | 右表 | JOIN 键 | 用途 |
|------|------|---------|------|
| `fact_trips` | `dim_date` | `pickup_date_key → date_key` | 接客日期维度 |
| `fact_trips` | `dim_date` | `dropoff_date_key → date_key` | 送客日期维度 |
| `fact_trips` | `dim_taxi_zone` | `pickup_location_id → location_id` | 上车区域维度 |
| `fact_trips` | `dim_taxi_zone` | `dropoff_location_id → location_id` | 下车区域维度 |
| `fact_trips` | `dim_vehicle` | `plate_no → base_license_number` | 车辆维度（注意：通过基地编号关联，不是 vehicle_key） |
| `fact_parking_violations` | `dim_date` | `issue_date_key → date_key` | 开票日期维度 |
| `fact_parking_violations` | `dim_violation_type` | `violation_code → violation_code` | 违章类型维度 |
| `fact_parking_violations` | `dim_taxi_zone` | `plate_no → location_id`（退化维度已含 borough） | 注意：停车罚单已有退化维度 borough |
| `fact_crashes` | `dim_date` | `crash_date_key → date_key` | 事故日期维度 |
| `fact_crash_persons` | `dim_date` | `crash_date_key → date_key` | 人员事故日期维度 |
| `fact_tif_payments` | `dim_date` | `payment_date_key → date_key` | 支付日期维度 |
| `fact_driver_applications` | `dim_date` | `app_date_key → date_key` | 申请日期维度 |
| `dws_daily_trip_summary` | `dws_daily_crash_summary` | `trip_date ↔ crash_date`（通过 `dim_date` 的 date 字段） | 跨主题对比分析 |

### 8.2 禁止的 JOIN

- `fact_trips` 与 `fact_parking_violations` 之间无核准 JOIN 键
- `fact_crashes` 与 `fact_trips` 之间无核准 JOIN 键
- 跨事实表的 JOIN 仅允许在 G3 汇总表层面通过日期字段关联
- 不得在无明确外键关系的情况下做 CROSS JOIN 或笛卡尔积

## 9. 金额字段说明

Gold 层存在多种金额字段，口径不同，不得混用：

| 英文字段名 | 中文字段名 | 来源 | 口径说明 |
|-----------|-----------|------|---------|
| `total_fare_amount` | 总车费 | `silver.trip_detail.fare_amount` | 单程车费，仅 Yellow/Green 有值，FHV/HV 为 0 |
| `standard_fine_amount` | 标准罚款金额 | 官方违章代码字典（Excel） | **参考标准**，不是实际缴款金额。通过 violation_code 关联 dim_violation_type 带入 |
| `tif_payment_amount` | TIF 支付金额 | `silver.tif_payment_detail.payment_amount` | 实际支付金额，来自 TIF 系统 |

禁止行为：
- 禁止将 `standard_fine_amount` 当作"实际收款"或"罚单收入"
- 禁止将 `total_fare_amount` 当作"公司收入"（车费含司机分成、通行费、小费等）
- 禁止在不同金额字段之间做算术运算（如 fare_amount + standard_fine_amount），它们来自不同的业务域
