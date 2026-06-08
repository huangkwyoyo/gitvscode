# Bronze 层数据库设计文档

> **事实源层级**：本文件是 Bronze 层的正式设计文档。与 DuckDB 实际 schema 冲突时，以 DuckDB `DESCRIBE` 结果为准并更新本文件。

## 概述

- **Schema**：`bronze`
- **表数量**：16 张（7 VIEW + 9 TABLE）
- **总行数**：97,600,814
- **总字段数**：264
- **数据库**：`D:/ProgramData/Datawarehouse/纽约市城市交通/nyc_transport.duckdb`

## 表清单

| 英文表名 | 中文表名 | 数据域 | 格式 | 对象类型 | 行数 | 字段数 | 候选键 | 候选键状态 |
|---|---|---|---|---|---|---|---|---|
| `yellow_tripdata_2026q1` | 黄色出租车行程表(2026Q1) | 出行域 | parquet | VIEW | 11,077,206 | 20 | — | 无自然主键 |
| `green_tripdata_2026q1` | 绿色出租车行程表(2026Q1) | 出行域 | parquet | VIEW | 121,853 | 21 | — | 无自然主键 |
| `fhv_tripdata_2026q1` | FHV网约车行程表(2026Q1) | 出行域 | parquet | VIEW | 6,250,941 | 7 | — | 无自然主键 |
| `fhvhv_tripdata_2026q1` | FHVHV高端网约车行程表(2026Q1) | 出行域 | parquet | VIEW | 62,874,417 | 25 | — | 无自然主键 |
| `active_vehicles` | 活跃车辆注册表 | 资产域 | csv | TABLE | 119,207 | 26 | License Number | ✅ 可作为主键 |
| `fhv_active_vehicles` | FHV活跃车辆表 | 资产域 | csv | TABLE | 104,420 | 23 | Vehicle License Number | ✅ 可作为主键 |
| `fhv_active_drivers` | FHV活跃驾驶员表 | 供给域 | csv | TABLE | 179,773 | 7 | License Number | ✅ 可作为主键 |
| `shl_active_drivers` | SHL活跃司机表 | 供给域 | csv | TABLE | 180,236 | 7 | License Number | ✅ 可作为主键 |
| `fhv_base_aggregate_report` | FHV基地汇总报告表 | 供给域 | csv | TABLE | 58,923 | 9 | Base License Number | ❌ 需复合键 |
| `crash_merged` | 机动车碰撞事故事实表 | 安全域 | parquet | VIEW | 1,655,065 | 29 | collision_id | ✅ 可作为主键 |
| `crash_person_all` | 机动车碰撞事故人员表 | 安全域 | parquet | VIEW | 5,333,042 | 21 | unique_id | ✅ 可作为主键 |
| `parking_violations_all` | 停车违章罚单全量表 | 监管合规域 | parquet | VIEW | 9,582,412 | 29 | summons_number | ✅ 可作为主键 |
| `medallion_authorized_vehicles` | 授权Medallion车辆表 | 监管合规域 | csv | TABLE | 10,547 | 16 | License Number | ✅ 可作为主键 |
| `new_driver_applications` | TLC新司机申请状态表 | 监管合规域 | csv | TABLE | 4,076 | 12 | App No | ✅ 可作为主键 |
| `tif_medallion_payments` | TIF牌照费支付记录表 | 监管合规域 | csv | TABLE | 48,431 | 8 | License Number | ❌ 需复合键 |
| `taxi_zone_lookup` | 出租车区域字典表 | 空间地理域 | csv | TABLE | 265 | 4 | LocationID | ✅ 可作为主键 |

## 字段详情

完整字段级信息请通过以下方式获取（以 DuckDB 实际 schema 为准）：

```sql
SELECT column_name, data_type, ordinal_position
FROM information_schema.columns
WHERE table_schema = 'bronze' AND table_name = '<表名>'
ORDER BY ordinal_position;
```

或查询 meta 元数据：
```sql
SELECT * FROM meta.source_columns WHERE table_name = '<表名>' ORDER BY ordinal_position;
```

## 已知问题

- `fhv_base_aggregate_report`：Base License Number 非唯一，需 Silver 层用复合键（+Year+Month）
- `tif_medallion_payments`：License Number 非唯一，需 Silver 层用复合键（+Payment Date）
- `fhv_tripdata_2026q1`：PUlocationID 缺失率 87%
- `parking_violations_all`：无金额字段（29 列全为 VARCHAR）
