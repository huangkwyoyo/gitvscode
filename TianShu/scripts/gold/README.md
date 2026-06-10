# Gold 脚本

用于存放 Gold 星型模型、事故 ER 子模型和汇总表生成脚本。

## 当前脚本

| 脚本 | 中文说明 | 当前状态 |
|---|---|---|
| `build_gold_duckdb.py` | 构建 DuckDB Gold G0/G1 维表和 G2 明细事实表，并写入中文表注释和字段注释 | 已启用 |

## 当前已建设批次

| 批次 | 英文表名 | 中文表名 |
|---|---|---|
| G0 | `gold.dim_date` | 日期维表 |
| G0 | `gold.dim_taxi_zone` | 出租车区域维表 |
| G1 | `gold.dim_vehicle` | 车辆维表 |
| G1 | `gold.dim_driver` | 司机维表 |
| G1 | `gold.dim_base` | 基地维表 |
| G1 | `gold.dim_violation_type` | 违章类型维表 |
| G2 | `gold.fact_trips` | 出行事实表 |
| G2 | `gold.fact_parking_violations` | 停车罚单事实表 |
| G2 | `gold.fact_tif_payments` | TIF支付事实表 |
| G2 | `gold.fact_driver_applications` | 司机申请事实表 |
| G2 | `gold.fact_crashes` | 事故事实表 |
| G2 | `gold.fact_crash_persons` | 事故人员事实表 |

运行方式：

```powershell
python scripts/gold/build_gold_duckdb.py --batches G0,G1,G2
python scripts/quality/check_gold_physical.py --batches G0,G1,G2
```

注意：`dim_violation_type.standard_fine_amount` 已从官方数据字典 Excel 导入。`fact_parking_violations.standard_fine_amount` 通过 `violation_code` 关联 `dim_violation_type` 带入，表示标准罚款金额，不代表实际缴纳金额。
