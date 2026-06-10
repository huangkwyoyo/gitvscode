# Gold 主题模型 SQL

用途：维护 `gold` schema 的主题星型模型和事故 ER 子模型 SQL 说明。

当前 DuckDB 实际构建入口在 `scripts/gold/build_gold_duckdb.py`。本目录用于沉淀可复用 SQL、DDL 草案和后续事实表 SQL，不作为唯一执行入口。

规划对象：

| 英文表名 | 中文表名 | 当前状态 |
|---|---|---|
| `gold.dim_date` | 日期维表 | 已由脚本构建 |
| `gold.dim_taxi_zone` | 出租车区域维表 | 已由脚本构建 |
| `gold.dim_vehicle` | 车辆维表 | 已由脚本构建 |
| `gold.dim_driver` | 司机维表 | 已由脚本构建 |
| `gold.dim_base` | 基地维表 | 已由脚本构建 |
| `gold.dim_violation_type` | 违章类型维表 | 已由脚本构建，标准罚款金额来自官方字典 |
| `gold.fact_trips` | 出行事实表 | 已由脚本构建 |
| `gold.fact_parking_violations` | 停车罚单事实表 | 已由脚本构建，标准罚款金额通过违章类型维表带入 |
| `gold.fact_tif_payments` | TIF支付事实表 | 已由脚本构建 |
| `gold.fact_driver_applications` | 司机申请事实表 | 已由脚本构建 |
| `gold.fact_crashes` | 事故事实表 | 已由脚本构建 |
| `gold.fact_crash_persons` | 事故人员事实表 | 已由脚本构建 |
