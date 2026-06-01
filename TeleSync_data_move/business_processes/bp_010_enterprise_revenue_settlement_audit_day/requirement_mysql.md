# 10 政企收入与结算稽核需求说明书

## 业务目标

按日分析政企客户收入、结算分摊、税费和部门归属，识别收入确认与结算分摊不一致、税费异常、部门归属缺失等稽核问题。

## 源表清单

| 层级 | 表名 | 用途 |
|---|---|---|
| ODS | `ods.ods_account_income_monthly` | 账户收入明细 |
| ODS | `ods.ods_settlement_allocation_daily` | 日结算分摊 |
| ODS | `ods.ods_post_settlement_allocation_daily` | 后向结算与投诉处理相关费用 |
| DWD | `dwd.dim_account` | 账户维表 |
| DWD | `dwd.dim_org` | 部门维表 |

## 结果表

`ads.ads_enterprise_revenue_settlement_audit_day`

## 调度周期

每日运行一次，业务日期参数为 `@biz_date`。

## 业务规则

1. 收入表按 `date(data_time) = @biz_date` 或当月月初口径取数。
2. 结算分摊表按 `date(data_time) = @biz_date` 取数。
3. 按账户、部门聚合收入、税费、结算分摊金额。
4. 收入金额与结算金额差异超过 5% 标记为 `SETTLEMENT_MISMATCH`。
5. 税费为负或税率超过合理区间标记为 `TAX_ABNORMAL`。
6. 部门缺失或账户维表缺失标记为 `DIM_MISSING`。

## 字段口径

| 字段 | 口径 |
|---|---|
| `account_id` | 账户 ID |
| `department_id` | 归属部门 |
| `revenue_fee` | 收入金额 |
| `settlement_fee` | 结算分摊金额 |
| `tax_fee` | 税费 |
| `audit_tag` | 稽核标签 |

## 迁移测试价值

覆盖 ODS 超宽表、金额稽核、多源汇总、全外关联替代思路、维表缺失识别。



## 标准目录信息

- 业务过程 ID：`bp_010_enterprise_revenue_settlement_audit_day`
- MySQL 结果表：`ads.ads_enterprise_revenue_settlement_audit_day`
- 标准化日期：2026-06-01
