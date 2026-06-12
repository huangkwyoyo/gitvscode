# Text2SQL 中文问数能力评测报告

**生成时间**: 2026-06-12 21:20:38
**评测问题数**: 22
**通过**: 22 | **警告**: 0 | **失败**: 0

## 评测汇总

| 问题ID | 问题 | 表选择 | 指标 | 可执行 | 结果一致性 | 层级合规 | 总评 |
|--------|------|--------|------|--------|------------|----------|------|
| q_daily_trip_count | 2026 年 Q1 每天有多少... | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_top_pickup_zone | 哪个区域上车量最高？ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_daily_parking_count | 每天停车罚单数量是多少？ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_daily_standard_fine | 标准罚款金额最高的日期是哪天？ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_daily_crash_trend | 每天事故数量和死亡人数趋势如何... | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_daily_injury_trend | 每天事故受伤人数是多少？ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_top_borough_fares | 曼哈顿行政区的行程量和总车费是... | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_trip_source_breakdown | 2026 年 Q1 每天不同行... | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_borough_list | 纽约市有哪些行政区？ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_cross_fact_comparison | 2026 年 1 月每日行程量... | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_daily_trip_revenue | 2026 年 1 月每天的总车... | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_vehicle_license_status | 不同牌照类型的车辆各有多少？ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_trip_by_vehicle_type | 2026 年 Q1 不同牌照类... | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_driver_expiration_2026 | 有多少司机的牌照在 2026 ... | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_driver_applications_daily | 2026 年 Q1 每天有多少... | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_violation_type_top | 最常发生的违章类型是哪些？ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_tif_payment_daily | 2026 年 Q1 每天的 T... | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_violation_fine_avg | 不同违章类型的标准罚款金额排序... | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_zone_fare_per_trip | 哪个行政区平均每程车费最高？ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_borough_crash_density | 各行政区的事故数量对比如何？ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_parking_date_filtered | 2026 年 1 月每天的有效... | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |
| q_empty_date_range | 2025 年 12 月 25 ... | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 通过 |

## 逐题详情

### q_daily_trip_count — ✅ 通过

> **问题**: 2026 年 Q1 每天有多少行程？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dws_daily_trip_summary` (G3 汇总表，最优) | — |
| 指标 | ✅ PASS | 指标已注册: ['trip_count'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 90 行, 2 列 (trip_date, trip_count) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dws_daily_trip_summary` (G3 汇总表，最优) | — |

### q_top_pickup_zone — ✅ 通过

> **问题**: 哪个区域上车量最高？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dws_zone_trip_summary` (G3 汇总表，最优) | — |
| 指标 | ✅ PASS | 指标已注册: ['trip_count'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 20 行, 3 列 (borough, zone_name, trip_count) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dws_zone_trip_summary` (G3 汇总表，最优) | — |

### q_daily_parking_count — ✅ 通过

> **问题**: 每天停车罚单数量是多少？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dws_daily_parking_summary` (G3 汇总表，最优) | — |
| 指标 | ✅ PASS | 指标已注册: ['parking_violation_count'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 1247 行, 2 列 (issue_date, violation_count) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dws_daily_parking_summary` (G3 汇总表，最优) | — |

### q_daily_standard_fine — ✅ 通过

> **问题**: 标准罚款金额最高的日期是哪天？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dws_daily_parking_summary` (G3 汇总表，最优) | — |
| 指标 | ✅ PASS | 指标已注册: ['standard_fine_total'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 20 行, 2 列 (issue_date, standard_fine_total) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dws_daily_parking_summary` (G3 汇总表，最优) | — |

### q_daily_crash_trend — ✅ 通过

> **问题**: 每天事故数量和死亡人数趋势如何？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dws_daily_crash_summary` (G3 汇总表，最优) | — |
| 指标 | ✅ PASS | 指标已注册: ['crash_count', 'persons_killed'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 5085 行, 3 列 (crash_date, crash_count, persons_killed) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dws_daily_crash_summary` (G3 汇总表，最优) | — |

### q_daily_injury_trend — ✅ 通过

> **问题**: 每天事故受伤人数是多少？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dws_daily_crash_summary` (G3 汇总表，最优) | — |
| 指标 | ✅ PASS | 指标已注册: ['persons_injured'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 5085 行, 2 列 (crash_date, persons_injured) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dws_daily_crash_summary` (G3 汇总表，最优) | — |

### q_top_borough_fares — ✅ 通过

> **问题**: 曼哈顿行政区的行程量和总车费是多少？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dws_zone_trip_summary` (G3 汇总表，最优) | — |
| 指标 | ✅ PASS | 指标已注册: ['total_fare_amount', 'trip_count'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 67 行, 3 列 (zone_name, trip_count, total_fare_amount) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dws_zone_trip_summary` (G3 汇总表，最优) | — |

### q_trip_source_breakdown — ✅ 通过

> **问题**: 2026 年 Q1 每天不同行程来源类型的行程量分布如何？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.fact_trips` (G2 明细事实表，可接受但非最优), `gold.dim_date` (G0 公共维表，仅维度属性，无事实指标) | — |
| 指标 | ✅ PASS | 指标已注册: ['trip_count'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 360 行, 3 列 (date, trip_source, trip_count) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dim_date` (G0 公共维表，仅维度属性，无事实指标), `gold.fact_trips` (G2 明细事实表，可接受但非最优) | — |

### q_borough_list — ✅ 通过

> **问题**: 纽约市有哪些行政区？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dim_taxi_zone` (G1 业务维表，仅维度属性，无事实指标) | — |
| 指标 | ✅ PASS | 无指标要求（纯维度查询）; 返回值列: ['borough'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 8 行, 1 列 (borough) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dim_taxi_zone` (G1 业务维表，仅维度属性，无事实指标) | — |

### q_cross_fact_comparison — ✅ 通过

> **问题**: 2026 年 1 月每日行程量和事故量的对比趋势？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dws_daily_trip_summary` (G3 汇总表，最优), `gold.dws_daily_crash_summary` (G3 汇总表，最优) | — |
| 指标 | ✅ PASS | 指标已注册: ['crash_count', 'trip_count'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 31 行, 3 列 (trip_date, trip_count, crash_count) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dws_daily_crash_summary` (G3 汇总表，最优), `gold.dws_daily_trip_summary` (G3 汇总表，最优) | — |

### q_daily_trip_revenue — ✅ 通过

> **问题**: 2026 年 1 月每天的总车费收入是多少？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dws_daily_trip_summary` (G3 汇总表，最优) | — |
| 指标 | ✅ PASS | 指标已注册: ['total_fare_amount'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 31 行, 2 列 (trip_date, total_fare_amount) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dws_daily_trip_summary` (G3 汇总表，最优) | — |

### q_vehicle_license_status — ✅ 通过

> **问题**: 不同牌照类型的车辆各有多少？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dim_vehicle` (G1 业务维表，仅维度属性，无事实指标) | — |
| 指标 | ✅ PASS | 无指标要求（纯维度查询）; 返回值列: ['cnt', 'license_type'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 5 行, 2 列 (license_type, cnt) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dim_vehicle` (G1 业务维表，仅维度属性，无事实指标) | — |

### q_trip_by_vehicle_type — ✅ 通过

> **问题**: 2026 年 Q1 不同牌照类型的车辆各完成了多少行程？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.fact_trips` (G2 明细事实表，可接受但非最优), `gold.dim_vehicle` (G1 业务维表，仅维度属性，无事实指标), `gold.dim_date` (G0 公共维表，仅... | — |
| 指标 | ✅ PASS | 指标已注册: ['trip_count'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 0 行, 2 列 (license_type, trip_count) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dim_date` (G0 公共维表，仅维度属性，无事实指标), `gold.dim_vehicle` (G1 业务维表，仅维度属性，无事实指标), `gold.fact_trips` (G2 明细事实表，可接... | — |

### q_driver_expiration_2026 — ✅ 通过

> **问题**: 有多少司机的牌照在 2026 年到期？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dim_driver` (G1 业务维表，仅维度属性，无事实指标) | — |
| 指标 | ✅ PASS | 无指标要求（纯维度查询）; 返回值列: ['cnt'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 1 行, 1 列 (cnt) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dim_driver` (G1 业务维表，仅维度属性，无事实指标) | — |

### q_driver_applications_daily — ✅ 通过

> **问题**: 2026 年 Q1 每天有多少新的司机申请？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dim_date` (G0 公共维表，仅维度属性，无事实指标), `gold.fact_driver_applications` (G2 明细事实表，可接受但非最优) | — |
| 指标 | ✅ PASS | 无指标要求（纯维度查询）; 返回值列: ['cnt', 'date'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 65 行, 2 列 (date, cnt) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dim_date` (G0 公共维表，仅维度属性，无事实指标), `gold.fact_driver_applications` (G2 明细事实表，可接受但非最优) | — |

### q_violation_type_top — ✅ 通过

> **问题**: 最常发生的违章类型是哪些？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.fact_parking_violations` (G2 明细事实表，可接受但非最优), `gold.dim_violation_type` (G1 业务维表，仅维度属性，无事实指标) | — |
| 指标 | ✅ PASS | 指标已注册: ['parking_violation_count'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 20 行, 2 列 (violation_description, violation_count) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dim_violation_type` (G1 业务维表，仅维度属性，无事实指标), `gold.fact_parking_violations` (G2 明细事实表，可接受但非最优) | — |

### q_tif_payment_daily — ✅ 通过

> **问题**: 2026 年 Q1 每天的 TIF 支付总额是多少？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.fact_tif_payments` (G2 明细事实表，可接受但非最优), `gold.dim_date` (G0 公共维表，仅维度属性，无事实指标) | — |
| 指标 | ✅ PASS | 无指标要求（纯维度查询）; 返回值列: ['daily_total', 'date'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 0 行, 2 列 (date, daily_total) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dim_date` (G0 公共维表，仅维度属性，无事实指标), `gold.fact_tif_payments` (G2 明细事实表，可接受但非最优) | — |

### q_violation_fine_avg — ✅ 通过

> **问题**: 不同违章类型的标准罚款金额排序？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dim_violation_type` (G1 业务维表，仅维度属性，无事实指标) | — |
| 指标 | ✅ PASS | 无指标要求（纯维度查询）; 返回值列: ['standard_fine_amount', 'violation_description'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 20 行, 2 列 (violation_description, standard_fine_amount) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dim_violation_type` (G1 业务维表，仅维度属性，无事实指标) | — |

### q_zone_fare_per_trip — ✅ 通过

> **问题**: 哪个行政区平均每程车费最高？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dws_zone_trip_summary` (G3 汇总表，最优) | — |
| 指标 | ✅ PASS | 指标已注册: ['total_fare_amount', 'trip_count'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 10 行, 5 列 (borough, zone_name, trip_count, total_fare_amount, fare_per_trip) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dws_zone_trip_summary` (G3 汇总表，最优) | — |

### q_borough_crash_density — ✅ 通过

> **问题**: 各行政区的事故数量对比如何？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.fact_crashes` (G2 明细事实表，可接受但非最优) | — |
| 指标 | ✅ PASS | 指标已注册: ['crash_count'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 6 行, 2 列 (borough, crash_count) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.fact_crashes` (G2 明细事实表，可接受但非最优) | — |

### q_parking_date_filtered — ✅ 通过

> **问题**: 2026 年 1 月每天的有效停车罚单量是多少？（排除异常日期）

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dim_date` (G0 公共维表，仅维度属性，无事实指标), `gold.v_parking_violations_valid` (未知层级: gold) | — |
| 指标 | ✅ PASS | 指标已注册: ['parking_violation_count'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 31 行, 2 列 (date, violation_count) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dim_date` (G0 公共维表，仅维度属性，无事实指标), `gold.v_parking_violations_valid` (未知层级: gold) | — |

### q_empty_date_range — ✅ 通过

> **问题**: 2025 年 12 月 25 日圣诞节的行程量是多少？

| 维度 | 结果 | 详情 | 修复建议 |
|------|------|------|----------|
| 表选择 | ✅ PASS | SQL 正确引用了推荐表: `gold.dws_daily_trip_summary` (G3 汇总表，最优) | — |
| 指标 | ✅ PASS | 指标已注册: ['trip_count'] | — |
| SQL 可执行性 | ✅ PASS | SQL 语法正确，可执行 | — |
| 结果一致性 | ✅ PASS | 与基线一致: 0 行, 2 列 (trip_date, trip_count) | — |
| 层级合规 | ✅ PASS | 表层级使用正确: `gold.dws_daily_trip_summary` (G3 汇总表，最优) | — |

## 统计

| 指标 | 数值 |
|------|------|
| 问题总数 | 22 |
| 全部通过 | 22 |
| 存在警告 | 0 |
| 存在失败 | 0 |
| 通过率 | 100.0% |

## Schema 概况

- **Gold G0/G1 维表 (dim_*)**: 6 个表/指标
- **Gold G2 明细事实表 (fact_*)**: 6 个表/指标
- **Gold G3 汇总表 (dws_*)**: 4 个表/指标
- **已注册指标 (meta.metric_definitions)**: 8 个表/指标
