# Gold 脚本

用于存放 Gold 星型模型、事故 ER 子模型和汇总表生成脚本。

## 当前脚本

| 脚本 | 中文说明 | 当前状态 |
|---|---|---|
| `build_gold_duckdb.py` | 构建 DuckDB Gold G0/G1 维表，并写入中文表注释和字段注释 | 已启用 |

## 当前已建设批次

| 批次 | 英文表名 | 中文表名 |
|---|---|---|
| G0 | `gold.dim_date` | 日期维表 |
| G0 | `gold.dim_taxi_zone` | 出租车区域维表 |
| G1 | `gold.dim_vehicle` | 车辆维表 |
| G1 | `gold.dim_driver` | 司机维表 |
| G1 | `gold.dim_base` | 基地维表 |
| G1 | `gold.dim_violation_type` | 违章类型维表 |

运行方式：

```powershell
python scripts/gold/build_gold_duckdb.py --batches G0,G1
python scripts/quality/check_gold_physical.py --batches G0,G1
```

注意：`dim_violation_type` 的金额字段当前只保留结构，不从 Silver 推断金额；正式金额口径需要官方字典或人工审核后再补。
