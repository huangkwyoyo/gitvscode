# 07 欠费风险用户识别需求说明书

## 业务目标

按日识别欠费风险用户，综合欠费金额、连续欠费月份、近 30 日充值、近 30 日活跃行为、套餐价值和用户状态输出风险等级。

## 源表清单

| 层级 | 表名 | 用途 |
|---|---|---|
| DWD | `dwd.fact_billing_monthly` | 月账单与欠费 |
| DWD | `dwd.fact_recharge_daily` | 近 30 日充值 |
| DWD | `dwd.fact_usage_daily` | 近 30 日活跃 |
| DWD | `dwd.dim_user` | 用户状态 |
| DWD | `dwd.dim_product` | 月租 |

## 结果表

`ads.ads_user_arrears_risk_day`

## 调度周期

每日运行一次，业务日期参数为 `@biz_date`。

## 业务规则

1. 统计截至业务月的最近 3 个月欠费情况。
2. 使用窗口函数计算连续欠费月份。
3. 统计近 30 日充值、流量、语音、短信。
4. 欠费金额高、充值低、活跃低的用户风险分更高。
5. 连续 3 个月欠费或有效欠费超过 200 的用户为 `HIGH`。
6. 连续 2 个月欠费或覆盖率不足 30% 的用户为 `MEDIUM`。
7. 仅单月轻微欠费且仍高活跃的用户为 `LOW`。

## 字段口径

| 字段 | 口径 |
|---|---|
| `arrears_month_count` | 最近 3 个月欠费月份数 |
| `max_outstanding_amount` | 最近 3 个月最大欠费 |
| `last_30d_recharge_amount` | 近 30 日充值 |
| `last_30d_usage_mb` | 近 30 日流量 |
| `risk_score` | 欠费风险评分 |
| `risk_level` | 风险等级 |

## 迁移测试价值

覆盖多窗口聚合、月日混合、风险评分、连续状态判断、复杂分支。



## 标准目录信息

- 业务过程 ID：`bp_007_user_arrears_risk_day`
- MySQL 结果表：`ads.ads_user_arrears_risk_day`
- 标准化日期：2026-06-01
