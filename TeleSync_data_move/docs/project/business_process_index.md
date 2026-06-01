# 业务过程索引

| 编号 | 业务过程ID | 业务过程名称 | 结果表 | 主要输入表 |
|---|---|---|---|---|
| 01 | `bp_001_user_daily_value_tag` | 用户日价值分层 | `ads.ads_user_daily_value_tag` | `dwd.fact_user_snapshot_daily, dwd.fact_usage_daily, dwd.fact_recharge_daily, dwd.fact_billing_monthly, dwd.dim_user, dwd.dim_product` |
| 02 | `bp_002_user_month_lifecycle` | 用户月生命周期分析 | `dws.dws_user_month_lifecycle` | `dws.dws_user_month_summary, dwd.dim_user` |
| 03 | `bp_003_user_voice_sms_day_profile` | 语音短信行为日画像 | `dws.dws_user_voice_sms_day_profile` | `dwd.fact_usage_daily, dwd.dim_user, dwd.dim_product` |
| 04 | `bp_004_user_app_preference_day` | DPI应用流量偏好 | `dws.dws_user_app_preference_day` | `dwd.fact_dpi_usage_daily, dwd.dim_application, dwd.fact_usage_daily, dwd.dim_user` |
| 05 | `bp_005_channel_order_conversion_day` | 渠道订单转化日分析 | `dws.dws_channel_order_conversion_day` | `dwd.fact_order_daily, dwd.dim_channel, dwd.dim_product` |
| 06 | `bp_006_user_recharge_billing_reconcile_day` | 充值账单对账日分析 | `ads.ads_user_recharge_billing_reconcile_day` | `dwd.fact_recharge_daily, dwd.fact_billing_monthly, dwd.dim_user, dwd.dim_product` |
| 07 | `bp_007_user_arrears_risk_day` | 欠费风险用户识别 | `ads.ads_user_arrears_risk_day` | `dwd.fact_billing_monthly, dwd.fact_recharge_daily, dwd.fact_usage_daily, dwd.dim_user, dwd.dim_product` |
| 08 | `bp_008_complaint_sla_escalation_day` | 投诉SLA升级分析 | `ads.ads_complaint_sla_escalation_day` | `dwd.fact_complaint_daily, dwd.dim_user, dwd.dim_product, dwd.dim_org, dwd.fact_billing_monthly` |
| 09 | `bp_009_terminal_contract_fulfillment_day` | 终端合约履约分析 | `dws.dws_terminal_contract_fulfillment_day` | `ods.ods_terminal_sales_daily, ods.ods_terminal_presale_daily, dwd.dim_user, dwd.dim_terminal` |
| 10 | `bp_010_enterprise_revenue_settlement_audit_day` | 政企收入与结算稽核 | `ads.ads_enterprise_revenue_settlement_audit_day` | `ods.ods_account_income_monthly, ods.ods_settlement_allocation_daily, ods.ods_post_settlement_allocation_daily, dwd.dim_account, dwd.dim_org` |
