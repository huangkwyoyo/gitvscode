# 09 终端合约履约分析需求说明书

## 业务目标

按日分析终端销售、预存款、用户活跃和合约履约风险，识别高补贴低活跃、退款异常、终端合约流失预警用户。

## 源表清单

| 层级 | 表名 | 用途 |
|---|---|---|
| ODS | `ods.ods_terminal_sales_daily` | 终端销售与用户使用 |
| ODS | `ods.ods_terminal_presale_daily` | 终端预存、退款、支付 |
| DWD | `dwd.dim_user` | 用户状态 |
| DWD | `dwd.dim_terminal` | 终端维表 |

## 结果表

`dws.dws_terminal_contract_fulfillment_day`

## 调度周期

每日运行一次，业务日期参数为 `@biz_date`。

## 业务规则

1. 终端销售按 `date(data_time) = @biz_date` 取数。
2. 终端预存按 `date(transaction_data_time) = @biz_date` 取数。
3. 同一用户同一终端如果有多笔记录，按最新交易时间取一笔。
4. 近月语音、短信、流量均低且预存或支付金额较高，标记为 `SUBSIDY_LOW_ACTIVITY`。
5. 退款金额大于支付金额 50% 标记为 `REFUND_ABNORMAL`。
6. 终端支持超级 SIM 但用户低活跃，标记为 `DEVICE_VALUE_LOSS`。

## 字段口径

| 字段 | 口径 |
|---|---|
| `terminal_id` | 终端 ID |
| `payment_transaction_amount` | 终端支付金额 |
| `refund_amount` | 退款金额 |
| `monthly_mobile_usage_mb` | 月流量 |
| `fulfillment_score` | 履约评分 |
| `fulfillment_tag` | 履约标签 |

## 迁移测试价值

覆盖 ODS 宽表、去重取最新、金额异常、终端维表关联、字段清洗。



## 标准目录信息

- 业务过程 ID：`bp_009_terminal_contract_fulfillment_day`
- MySQL 结果表：`dws.dws_terminal_contract_fulfillment_day`
- 标准化日期：2026-06-01
