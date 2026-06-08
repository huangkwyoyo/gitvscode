# Silver 白银层脚本与规划

本目录包含 Silver 白银层 11 张标准明细表的详细设计文档和生成脚本。

## 文档索引

| 批次 | 英文表名 | 中文表名 | 设计文档 | 字段数 |
|---|---|---|---|---|
| P0 | `silver.dim_date` | 日期维表 | [dim_date.md](dim_date.md) | 10 |
| P0 | `silver.taxi_zone` | 出租车区域标准维表 | [taxi_zone.md](taxi_zone.md) | 5 |
| P0 | `silver.trip_detail` | 行程明细标准表 | [trip_detail.md](trip_detail.md) | 42 |
| P1 | `silver.vehicle_detail` | 车辆明细标准表 | [vehicle_detail.md](vehicle_detail.md) | 25 |
| P1 | `silver.driver_detail` | 司机明细标准表 | [driver_detail.md](driver_detail.md) | 11 |
| P1 | `silver.base_detail` | 基地月度明细标准表 | [base_detail.md](base_detail.md) | 12 |
| P1 | `silver.driver_application_detail` | 司机申请明细标准表 | [driver_application_detail.md](driver_application_detail.md) | 14 |
| P2 | `silver.parking_violation_detail` | 停车罚单明细标准表 | [parking_violation_detail.md](parking_violation_detail.md) | 36 |
| P2 | `silver.tif_payment_detail` | TIF支付明细标准表 | [tif_payment_detail.md](tif_payment_detail.md) | 11 |
| P2 | `silver.crash_detail` | 事故明细标准表 | [crash_detail.md](crash_detail.md) | 22 |
| P2 | `silver.crash_person_detail` | 事故人员明细标准表 | [crash_person_detail.md](crash_person_detail.md) | 20 |

## 数据字典

完整字段级数据字典见：`D:\ProgramData\Datawarehouse\纽约市城市交通\分析报告\Silver层数据字典.xlsx`

包含 12 个 Sheet：Silver表清单 + 每张表一个 Sheet。

## 通用设计原则

1. **代理键统一**：除维表外，所有事实表使用自增 BIGINT 代理键，避免依赖 Bronze 层自然键。
2. **类型强制转换**：Bronze 层 CSV 导入的全 VARCHAR 字段必须转为目标类型（DATE、INTEGER、BIGINT、DECIMAL、DOUBLE）。
3. **金额 DECIMAL**：所有货币字段统一 DECIMAL(12,2)，避免浮点精度问题。
4. **质量标记不丢弃**：异常数据标记但不删除，下游可自行决定是否过滤。
5. **溯源可追**：每表保留 `source_row_hash`（MD5）或 `source_table` 字段，可回溯到 Bronze 原始行。
6. **Meta 同步**：建表后必须写入 `meta.table_comments` 和 `meta.column_comments`。
