# 血缘说明

## 业务过程

- 业务过程 ID：`bp_005_channel_order_conversion_day`
- 业务过程名称：渠道订单转化日分析
- MySQL 结果表：`dws.dws_channel_order_conversion_day`

## 表级血缘

| 表名 | 类型 | 说明 |
|---|---|---|
| `dwd.fact_order_daily` | 输入 | 参与 渠道订单转化日分析 计算 |
| `dwd.dim_channel` | 输入 | 参与 渠道订单转化日分析 计算 |
| `dwd.dim_product` | 输入 | 参与 渠道订单转化日分析 计算 |
| `dws.dws_channel_order_conversion_day` | 输出 | MySQL 口径结果表 |

## 字段级血缘原则

1. 主键字段来自业务过程的周期字段和业务实体字段。
2. 维度字段来自对应维表或 ODS 宽表中的稳定字段。
3. 指标字段来自事实表聚合、窗口计算或业务规则计算。
4. 标签字段由 `CASE WHEN` 业务规则生成。
5. `created_at` 记录材料执行时的生成时间。

## 可追溯要求

后续 Doris 转换必须保留本目录 MySQL 原始材料，并输出到 `doris_outputs/bp_005_channel_order_conversion_day/`。
