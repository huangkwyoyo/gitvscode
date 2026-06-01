# 08 投诉 SLA 升级分析需求说明书

## 业务目标

按日分析投诉工单处理 SLA，识别超时、重复投诉、高价值用户投诉和责任部门压力，输出投诉升级清单。

## 源表清单

| 层级 | 表名 | 用途 |
|---|---|---|
| DWD | `dwd.fact_complaint_daily` | 投诉工单 |
| DWD | `dwd.dim_user` | 用户基础属性 |
| DWD | `dwd.dim_product` | 用户套餐价值 |
| DWD | `dwd.dim_org` | 责任部门 |
| DWD | `dwd.fact_billing_monthly` | 用户月收入 |

## 结果表

`ads.ads_complaint_sla_escalation_day`

## 调度周期

每日运行一次，业务日期参数为 `@biz_date`。

## 业务规则

1. 处理 `complaint_date = @biz_date` 的投诉。
2. 近 30 日同用户投诉超过 2 次为重复投诉。
3. 网络质量投诉 SLA 阈值 24 小时，费用争议 48 小时，其他 72 小时。
4. 超过 SLA 或重复投诉或高月租用户投诉进入升级清单。
5. 按责任部门计算当日投诉压力排名。
6. 一次派单失败且处理时长超过阈值的工单升级优先级最高。

## 字段口径

| 字段 | 口径 |
|---|---|
| `sla_limit_hour` | 投诉类型对应 SLA 阈值 |
| `is_sla_timeout` | 是否超时 |
| `last_30d_complaint_count` | 近 30 日投诉次数 |
| `department_pressure_rank` | 部门投诉量排名 |
| `escalation_level` | 升级等级 |

## 迁移测试价值

覆盖按类型阈值、近 30 日重复识别、部门排名、复杂升级规则、多表 Join。



## 标准目录信息

- 业务过程 ID：`bp_008_complaint_sla_escalation_day`
- MySQL 结果表：`ads.ads_complaint_sla_escalation_day`
- 标准化日期：2026-06-01
