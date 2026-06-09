# Silver 标准层 SQL

用途：维护 `silver` schema 的标准明细表。

本目录是 Silver SQL 入口说明，不是当前唯一执行源。当前实际构建入口是 `scripts/silver/build_silver_duckdb.py`。如果本目录说明、构建脚本、Silver 数据字典和 DuckDB 实表发生冲突，以 `docs/warehouse/database_design/silver_database_design.md` 为最高事实源，并通过 Harness 强校验裁决。

Silver 建成后，不能只看脚本执行成功，必须通过：

```powershell
python scripts\quality\check_schema_consistency.py --require-silver-tables
python scripts\quality\check_silver_null.py
python scripts\quality\run_all_checks.py
```

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
| P2 | `parking_violation_detail` | 停车罚单明细标准表 | 958万 | 33 | `violation_id`（代理键） |
| P2 | `tif_payment_detail` | TIF支付明细标准表 | 4.8万 | 12 | `payment_id`（代理键） |
| P2 | `crash_detail` | 事故明细标准表 | 166万 | 26 | `crash_id`（代理键） |
| P2 | `crash_person_detail` | 事故人员明细标准表 | 533万 | 24 | `crash_person_id`（代理键） |

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
