# Silver 层数据库设计文档

> **事实源层级**：本文件是 Silver 层的正式设计文档。所有 Silver 建表 SQL 和字段字典必须与本文件一致。

## 概述

- **Schema**：`silver`
- **表数量**：11 张
- **数据来源**：Bronze 层 16 张表
- **设计文档**：`docs/silver/Silver白银层规划.md`
- **详细设计**：`scripts/silver/`（每表一份设计文档）

## 表清单

| 批次 | 英文表名 | 中文表名 | 数据域 | 数据角色 | 字段数 | 预计行数 | 主键 |
|---|---|---|---|---|---|---|---|
| P0 | `dim_date` | 日期维表 | 通用 | 维表 | 10 | ~90 | `date_key` |
| P0 | `taxi_zone` | 出租车区域标准维表 | 空间地理域 | 维表 | 5 | 265 | `location_id` |
| P0 | `trip_detail` | 行程明细标准表 | 出行域 | 事实表 | 39 | 8,032万 | `trip_id`（代理键） |
| P1 | `vehicle_detail` | 车辆明细标准表 | 资产域 | 维表 | 25 | ~12万 | `vehicle_id`（代理键） |
| P1 | `driver_detail` | 司机明细标准表 | 供给域 | 维表 | 11 | ~36万 | `license_number`+`driver_type` |
| P1 | `base_detail` | 基地月度明细标准表 | 供给域 | 事实表 | 12 | ~5.9万 | `composite_key` |
| P1 | `driver_application_detail` | 司机申请明细标准表 | 监管合规域 | 事实表 | 14 | 4,076 | `app_no` |
| P2 | `parking_violation_detail` | 停车罚单明细标准表 | 监管合规域 | 事实表 | 33 | 958万 | `violation_id`（代理键） |
| P2 | `tif_payment_detail` | TIF支付明细标准表 | 监管合规域 | 事实表 | 12 | ~4.8万 | `payment_id`（代理键） |
| P2 | `crash_detail` | 事故明细标准表 | 安全域 | 事实表 | 26 | 166万 | `crash_id`（代理键） |
| P2 | `crash_person_detail` | 事故人员明细标准表 | 安全域 | 事实表 | 24 | 533万 | `crash_person_id`（代理键） |

## 表间关联关系

| 主表 | 关联表 | 关联字段 | 关联类型 |
|---|---|---|---|
| `trip_detail` | `taxi_zone` | `pickup_location_id` → `location_id` | 外键 |
| `trip_detail` | `taxi_zone` | `dropoff_location_id` → `location_id` | 外键 |
| `trip_detail` | `dim_date` | `pickup_date` → `date` | 外键 |
| `crash_person_detail` | `crash_detail` | `collision_id` → `collision_id` | 外键（需验证覆盖） |
| `vehicle_detail` | `base_detail` | `base_number` → `base_license_number` | 外键（聚合级） |

## 字段来源分类规则

每个 Silver 字段必须标注 source_type：
- `direct`：直接来自 Bronze 字段
- `standardized`：来自 Bronze 但进行了标准化（命名/类型/格式）
- `derived`：通过计算/组合得出，Bronze 中无直接对应列

## 已知约束

- `parking_violations_all` 无金额字段，Silver 层不新增来源型金额
- `dim_date.date_key` 使用 `strftime('%Y%m%d')::INTEGER`，禁用 `DATE::INT`
- `trip_detail.trip_id` 使用 MD5 稳定哈希，禁用无序 `ROW_NUMBER()`
- 枚举值以 `SELECT DISTINCT` 为准，不得硬编码
- Silver 字段不得凭空新增，必须能追溯到 Bronze DESCRIBE 结果
