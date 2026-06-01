# 05 渠道订单转化日分析需求说明书

## 业务目标

按日分析各渠道订单创建、支付转化、支付时延和产品结构，识别高转化渠道、低转化高流量渠道和异常取消渠道。

## 源表清单

| 层级 | 表名 | 用途 |
|---|---|---|
| DWD | `dwd.fact_order_daily` | 订单明细 |
| DWD | `dwd.dim_channel` | 渠道信息 |
| DWD | `dwd.dim_product` | 产品信息 |

## 结果表

`dws.dws_channel_order_conversion_day`

## 调度周期

每日运行一次，业务日期参数为 `@biz_date`。

## 业务规则

1. 以 `date(order_created_time) = @biz_date` 作为订单创建口径。
2. 统计订单数、支付订单数、取消订单数、创建未支付订单数。
3. 支付转化率 = 支付订单数 / 订单数。
4. 平均支付时延 = `payment_time - order_created_time` 的分钟数。
5. 按渠道类型和产品类型输出渠道转化表现。
6. 取消率超过 25% 且订单数超过 20 的渠道标记为 `HIGH_CANCEL`。
7. 转化率低于同渠道类型均值 30% 的渠道标记为 `LOW_CONVERSION`。

## 字段口径

| 字段 | 口径 |
|---|---|
| `channel_id` | 渠道 ID |
| `channel_type` | 渠道类型 |
| `product_type` | 产品类型 |
| `conversion_rate` | 支付转化率 |
| `avg_pay_minutes` | 平均支付时延 |
| `channel_risk_tag` | 渠道风险标签 |

## 迁移测试价值

覆盖时间差计算、条件聚合、同组均值对比、渠道维表关联、订单状态枚举。



## 标准目录信息

- 业务过程 ID：`bp_005_channel_order_conversion_day`
- MySQL 结果表：`dws.dws_channel_order_conversion_day`
- 标准化日期：2026-06-01
