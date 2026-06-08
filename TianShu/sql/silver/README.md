# Silver 标准层 SQL

用途：维护 `silver` schema 的标准明细表。

## 构建方式

Silver 层由构建脚本统一管理：

```powershell
python scripts/silver/build_silver_duckdb.py --batch P0
python scripts/silver/build_silver_duckdb.py --batch P1
python scripts/silver/build_silver_duckdb.py --batch P2
python scripts/silver/build_silver_duckdb.py --batch all --replace
```

## Silver 表清单（11 张，已全部建成）

| 批次 | 英文表名 | 中文表名 | 行数 | 字段数 | 主键 |
|---|---|---|---|---|---|
| P0 | `dim_date` | 日期维表 | 90 | 10 | `date_key` |
| P0 | `taxi_zone` | 出租车区域标准维表 | 265 | 5 | `location_id` |
| P0 | `trip_detail` | 行程明细标准表 | 8,032万 | 39 | `trip_id`（代理键） |
| P1 | `vehicle_detail` | 车辆明细标准表 | 12万 | 25 | `vehicle_id`（代理键） |
| P1 | `driver_detail` | 司机明细标准表 | 36万 | 11 | `license_number+driver_type` |
| P1 | `base_detail` | 基地月度明细标准表 | 5.9万 | 12 | `composite_key` |
| P1 | `driver_application_detail` | 司机申请明细标准表 | 4,076 | 14 | `app_no` |
| P2 | `parking_violation_detail` | 停车罚单明细标准表 | 958万 | 30 | `violation_id`（代理键） |
| P2 | `tif_payment_detail` | TIF支付明细标准表 | 4.8万 | 12 | `composite_key` |
| P2 | `crash_detail` | 事故明细标准表 | 166万 | 26 | `collision_id` |
| P2 | `crash_person_detail` | 事故人员明细标准表 | 533万 | 23 | `unique_id` |

## 规则约束

- 禁止新增 Bronze 不存在的业务字段。
- 禁止使用 `DATE::INT`（DuckDB 不兼容，应用 `strftime`）。
- 禁止使用无序 `ROW_NUMBER()` 生成主键（应用稳定 MD5）。
- 详细规则见 `docs/warehouse/silver/AGENTS.md`。

## 设计文档

- 规划：`docs/silver/Silver白银层规划.md`
- 事实源：`docs/warehouse/database_design/silver_database_design.md`
- 构建脚本：`scripts/silver/build_silver_duckdb.py`
- 字段字典：`scripts/silver/_gen_xlsx.py`
