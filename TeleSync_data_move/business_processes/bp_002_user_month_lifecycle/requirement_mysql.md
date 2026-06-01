# 02 用户月生命周期需求说明书

## 业务目标

按月生成用户生命周期状态，识别新入网、活跃、沉默、流失预警、已流失用户，并输出最近 3 个月收入、流量、语音、充值和欠费趋势。

## 源表清单

| 层级 | 表名 | 用途 |
|---|---|---|
| DWD | `dwd.dim_user` | 入网时间、销户时间、用户状态 |
| DWD | `dwd.dws_user_month_summary` | 用户月收入、用量、充值、欠费 |

## 结果表

`dws.dws_user_month_lifecycle`

## 调度周期

每日调度，但只处理 `@biz_date` 所在月份，业务月为 `date_format(@biz_date, '%Y-%m-01')`。

## 业务规则

1. 以业务月的用户月汇总为主表。
2. 使用窗口函数取当前月、上月、上上月的收入和用量。
3. 入网月等于业务月的用户为 `NEW`。
4. 连续两个月流量和语音低于阈值且充值金额为 0 的用户为 `SILENT`。
5. 当前月欠费大于 0 且收入连续下降的用户为 `CHURN_WARNING`。
6. 已存在销户日期且销户日期小于等于月末的用户为 `CHURNED`。
7. 其余有正常收入或用量的用户为 `ACTIVE`。

## 字段口径

| 字段 | 口径 |
|---|---|
| `data_month_date` | 业务月月初 |
| `monthly_revenue_fee` | 当月收入 |
| `revenue_mom_rate` | 收入环比 |
| `usage_mom_rate` | 流量环比 |
| `lifecycle_status` | 生命周期状态 |
| `warning_reason` | 预警原因 |

## 迁移测试价值

覆盖窗口函数 `LAG`、月度口径、环比计算、用户状态优先级、复杂 `CASE WHEN`。



## 标准目录信息

- 业务过程 ID：`bp_002_user_month_lifecycle`
- MySQL 结果表：`dws.dws_user_month_lifecycle`
- 标准化日期：2026-06-01
