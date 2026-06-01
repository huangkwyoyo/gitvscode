# 指标字典

## 设计目标

指标字典用于把业务问题、口径、SQL 查询和 Agent 解释统一起来。后续自然语言查询指标时，Agent 应先读取本文件，再结合 `ads.ads_agent_metric_catalog`、`ads.ads_agent_field_catalog` 和 `ads.ads_agent_semantic_join` 生成 SQL。

## 指标命名规范

| 类型 | 命名规则 | 示例 |
|---|---|---|
| 用户规模 | `xxx_user_count` | `active_user_count` |
| 收入金额 | `xxx_revenue_amount` | `billing_revenue_amount` |
| 费用金额 | `xxx_fee` | `overdue_fee` |
| 使用量 | `xxx_usage_mb` / `xxx_usage_min` | `data_usage_mb` |
| 次数 | `xxx_count` | `complaint_count` |
| 比率 | `xxx_rate` | `churn_risk_rate` |
| 比例 | `xxx_ratio` | `high_value_user_ratio` |

## 核心指标清单

| metric_name | 中文名称 | 业务含义 | 推荐来源表 | 统计粒度 | 口径说明 | 应用场景 |
|---|---|---|---|---|---|---|
| `active_user_count` | 在网用户数 | 当前仍处于正常或欠费未离网状态的用户数量 | `dws.dws_user_month_summary` | 月、地域、套餐 | 按统计月去重计算有效 `user_id` | 用户规模分析 |
| `new_user_count` | 新增用户数 | 统计期内新入网用户数量 | `dwd.dim_user` | 月、地域、渠道 | `activation_date` 落在统计期内 | 拉新效果分析 |
| `churn_user_count` | 离网用户数 | 统计期内发生离网的用户数量 | `dwd.dim_user` | 月、地域、套餐 | `termination_date` 落在统计期内 | 流失分析 |
| `churn_rate` | 离网率 | 离网用户占期初在网用户比例 | `dws.dws_user_month_summary` | 月、地域、套餐 | `churn_user_count / beginning_active_user_count` | 经营健康度 |
| `billing_revenue_amount` | 出账收入 | 账单侧应收收入金额 | `dwd.fact_billing_monthly` | 月、地域、套餐 | 汇总账单金额，排除测试和异常账期 | 收入分析 |
| `payment_amount` | 缴费金额 | 用户实际缴费到账金额 | `dwd.fact_recharge_daily` | 日、月、渠道 | 汇总有效缴费流水金额 | 回款分析 |
| `arrears_user_count` | 欠费用户数 | 存在未缴清账单的用户数量 | `dws.dws_arrears_month_summary` | 月、地域 | 账期末欠费金额大于 0 的用户去重 | 欠费治理 |
| `arrears_fee` | 欠费金额 | 账期末未回收费用 | `dws.dws_arrears_month_summary` | 月、地域 | 汇总欠费余额 | 催缴分析 |
| `arpu_amount` | 用户月均收入 | 每户每月平均收入 | `ads.ads_kpi_revenue_monthly` | 月、地域、套餐 | `billing_revenue_amount / active_user_count` | 价值分析 |
| `data_usage_mb` | 移动数据流量 | 用户移动数据使用量 | `dwd.fact_usage_daily` | 日、月、用户、套餐 | 汇总数据流量 MB | 网络和套餐分析 |
| `voice_usage_min` | 语音通话分钟数 | 用户语音使用分钟数 | `dwd.fact_usage_daily` | 日、月、用户、套餐 | 汇总语音分钟数 | 行为分析 |
| `sms_count` | 短信条数 | 用户短信使用次数 | `dwd.fact_usage_daily` | 日、月、用户、套餐 | 汇总短信条数 | 行为分析 |
| `complaint_count` | 投诉量 | 用户投诉工单数量 | `dwd.fact_complaint_daily` | 日、地域、问题类型 | 统计有效投诉工单 | 服务质量分析 |
| `complaint_rate` | 投诉率 | 投诉用户占活跃用户比例 | `ads.ads_kpi_complaint_daily` | 日、地域 | `complaint_user_count / active_user_count` | 客诉监控 |
| `order_count` | 订单量 | 业务办理订单数量 | `dwd.fact_order_daily` | 日、渠道、产品 | 统计有效订单 | 渠道运营 |
| `order_payment_success_rate` | 订单支付成功率 | 已支付订单占创建订单比例 | `dwd.fact_order_daily` | 日、渠道、产品 | `paid_order_count / order_count` | 转化分析 |
| `marketing_conversion_rate` | 营销转化率 | 营销触达后完成订购或支付的比例 | `dwd.fact_order_daily` | 月、渠道、产品 | 触达后窗口期内转化订单数除以触达用户数 | 营销分析 |
| `high_value_user_count` | 高价值用户数 | 高消费能力或高 ARPU 用户数量 | `dws.dws_user_month_summary` | 月、地域、套餐 | 按 ARPU、套餐档位和使用行为综合识别 | 人群圈选 |
| `churn_risk_user_count` | 流失风险用户数 | 存在欠费、投诉、低活跃等风险信号的用户数量 | `dws.dws_user_month_summary` | 月、地域、套餐 | 按风险规则或模型分数圈选 | 流失预警 |

## Agent 使用规则

1. 先识别用户问题对应的指标名称。
2. 再确认时间粒度、地域粒度、产品粒度和用户范围。
3. 优先查询 ADS 指标表；ADS 不满足时下钻到 DWS，再下钻到 DWD。
4. 回答时必须说明指标口径、过滤条件和数据来源表。
5. 涉及金额类指标时默认单位为元，涉及流量类指标时默认单位为 MB。
