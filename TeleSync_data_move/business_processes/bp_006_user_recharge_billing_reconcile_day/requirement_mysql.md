# 06 充值账单对账日分析需求说明书

## 业务目标

按日识别用户充值与账单欠费的匹配关系，判断充值是否覆盖欠费，输出欠费缓解、欠费扩大、充值不足、预存充足等对账标签。

## 源表清单

| 层级 | 表名 | 用途 |
|---|---|---|
| DWD | `dwd.fact_recharge_daily` | 用户充值明细 |
| DWD | `dwd.fact_billing_monthly` | 月账单收入与欠费 |
| DWD | `dwd.dim_user` | 用户账户关系 |
| DWD | `dwd.dim_product` | 产品类型 |

## 结果表

`ads.ads_user_recharge_billing_reconcile_day`

## 调度周期

每日运行一次，业务日期参数为 `@biz_date`。

## 业务规则

1. 统计用户当日充值和近 7 日充值。
2. 关联业务日期所在月的账单与欠费。
3. 充值覆盖率 = 近 7 日充值 / 有效欠费。
4. 欠费大于 0 且覆盖率小于 0.5 标记为 `INSUFFICIENT_RECHARGE`。
5. 欠费为 0 且近 7 日充值大于当月出账金额标记为 `PREPAID_ENOUGH`。
6. 后付费用户优先纳入风险识别。

## 字段口径

| 字段 | 口径 |
|---|---|
| `daily_recharge_amount` | 当日充值 |
| `last_7d_recharge_amount` | 近 7 日充值 |
| `valid_outstanding_amount` | 有效欠费 |
| `recharge_cover_rate` | 充值覆盖率 |
| `reconcile_tag` | 对账标签 |

## 迁移测试价值

覆盖滑动时间窗口、金额比率、月日粒度关联、除零保护、风险标签。



## 标准目录信息

- 业务过程 ID：`bp_006_user_recharge_billing_reconcile_day`
- MySQL 结果表：`ads.ads_user_recharge_billing_reconcile_day`
- 标准化日期：2026-06-01
