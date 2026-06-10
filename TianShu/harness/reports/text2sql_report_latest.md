# Text2SQL 中文问数能力评测报告

**生成时间**: 2026-06-10 20:51:25
**评测问题数**: 10
**通过**: 10 | **警告**: 0 | **失败**: 0

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

## 统计

| 指标 | 数值 |
|------|------|
| 问题总数 | 10 |
| 全部通过 | 10 |
| 存在警告 | 0 |
| 存在失败 | 0 |
| 通过率 | 100.0% |

## Schema 概况

- **Gold G0/G1 维表 (dim_*)**: 6 个表/指标
- **Gold G2 明细事实表 (fact_*)**: 6 个表/指标
- **Gold G3 汇总表 (dws_*)**: 4 个表/指标
- **已注册指标 (meta.metric_definitions)**: 8 个表/指标
