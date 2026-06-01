# 业务上下文

## 背景

本项目模拟电信行业 MySQL 数仓迁移到 Apache Doris 的过程。当前本机 MySQL 已有模拟数仓数据，覆盖 ODS、DWD、DWS、ADS 四层。

## 数据仓库分层

| 层级 | 说明 |
|---|---|
| ODS | 源系统贴源层，包含用户画像、欠费、充值、终端、DPI、结算等宽表和明细表 |
| DWD | 明细事实层和维度层，包含用户、账户、产品、渠道、应用、组织等维表，以及用量、账单、充值、投诉、订单等事实表 |
| DWS | 主题汇总层，包含用户日/月、产品月、渠道日、投诉日、DPI 应用日等汇总表 |
| ADS | 指标应用层，包含收入、欠费、渠道、产品、投诉、用户总览等 KPI 表 |

## 已识别核心事实表

| 表名 | 行数级别 | 业务含义 |
|---|---:|---|
| `dwd.fact_usage_daily` | 360 万 | 用户日流量、语音、短信行为 |
| `dwd.fact_dpi_usage_daily` | 300 万 | 用户应用访问和 DPI 流量 |
| `dwd.fact_user_snapshot_daily` | 120 万 | 用户日快照和日收入 |
| `dwd.fact_billing_monthly` | 120 万 | 用户月账单和欠费 |
| `dwd.fact_recharge_daily` | 90 万 | 用户充值明细 |
| `dwd.fact_order_daily` | 20 万 | 渠道订单明细 |
| `dwd.fact_complaint_daily` | 3 万 | 投诉工单明细 |

## 业务日期范围

| 表名 | 日期范围 |
|---|---|
| `dwd.fact_usage_daily` | 2025-01-01 至 2025-12-31 |
| `dwd.fact_dpi_usage_daily` | 2025-01-01 至 2025-12-31 |
| `dwd.fact_recharge_daily` | 2025-01-01 至 2025-12-31 |
| `dwd.fact_order_daily` | 2025-01-01 至 2025-12-31 |
| `dwd.fact_complaint_daily` | 2025-01-01 至 2025-12-31 |
| `dwd.fact_billing_monthly` | 2025-01-01 至 2025-12-01 |

## 业务过程设计原则

10 个业务过程应覆盖真实迁移中的复杂 SQL 特征：

- 多表 Join
- CTE
- 窗口函数
- 日期窗口
- 日/月粒度混合
- 条件聚合
- 去重取最新
- 风险评分
- 标签分层
- 金额、流量、语音、短信等多指标计算

## 已规划业务过程

1. 用户日价值分层
2. 用户月生命周期分析
3. 语音短信行为日画像
4. DPI 应用流量偏好
5. 渠道订单转化日分析
6. 充值账单对账日分析
7. 欠费风险用户识别
8. 投诉 SLA 升级分析
9. 终端合约履约分析
10. 政企收入与结算稽核

## WebSQL 使用定位

WebSQL 当前支持 SQL 脚本任务，因此在 MySQL 口径阶段可以直接执行生成的 SQL 脚本。后续进入 Doris 迁移 Agent 阶段，推荐将 WebSQL 定位为调度入口，通过任务表或 API 间接触发 FastAPI/LangGraph。

