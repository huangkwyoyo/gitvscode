/*
业务过程：终端合约履约分析
SQL类型：业务SQL
SQL口径：MySQL
输入表：ods.ods_terminal_sales_daily、ods.ods_terminal_presale_daily、dwd.dim_user、dwd.dim_terminal
输出表：dws.dws_terminal_contract_fulfillment_day
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/
SET @biz_date = '2025-12-31';
SET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');

INSERT INTO dws.dws_terminal_contract_fulfillment_day
WITH
-- 按业务口径拆分中间结果，便于后续迁移转换和静态检查
sales AS (
  SELECT DATE(data_time) AS biz_date,
         user_id,
         terminal_id,
         monthly_mobile_usage_mb,
         monthly_voice_call_count,
         monthly_sms_count,
         ROW_NUMBER() OVER (PARTITION BY user_id, terminal_id ORDER BY data_time DESC) AS rn
  FROM ods.ods_terminal_sales_daily
  WHERE DATE(data_time) = @biz_date
),
presale AS (
  SELECT service_number_id,
         terminal_id,
         payment_transaction_amount,
         refund_amount,
         ROW_NUMBER() OVER (PARTITION BY service_number_id, terminal_id ORDER BY transaction_data_time DESC) AS rn
  FROM ods.ods_terminal_presale_daily
  WHERE DATE(transaction_data_time) = @biz_date
)
SELECT s.biz_date,
       s.user_id,
       s.terminal_id,
       t.terminal_model_name,
       t.is_super_sim_supported,
       COALESCE(p.payment_transaction_amount, 0) AS payment_transaction_amount,
       COALESCE(p.refund_amount, 0) AS refund_amount,
       s.monthly_mobile_usage_mb,
       s.monthly_voice_call_count,
       s.monthly_sms_count,
       COALESCE(p.payment_transaction_amount, 0) * 0.2
         + COALESCE(s.monthly_mobile_usage_mb, 0) / 1024
         + COALESCE(s.monthly_voice_call_count, 0) * 0.5
         - COALESCE(p.refund_amount, 0) * 0.3 AS fulfillment_score,
       CASE
         WHEN COALESCE(p.refund_amount, 0) > COALESCE(p.payment_transaction_amount, 0) * 0.5 THEN 'REFUND_ABNORMAL'
         WHEN COALESCE(p.payment_transaction_amount, 0) >= 500 AND COALESCE(s.monthly_mobile_usage_mb, 0) < 100 AND COALESCE(s.monthly_voice_call_count, 0) < 5 THEN 'SUBSIDY_LOW_ACTIVITY'
         WHEN t.is_super_sim_supported = 1 AND COALESCE(s.monthly_mobile_usage_mb, 0) < 100 THEN 'DEVICE_VALUE_LOSS'
         ELSE 'NORMAL'
       END AS fulfillment_tag,
       NOW() AS created_at
FROM sales s
LEFT JOIN presale p ON s.terminal_id = p.terminal_id AND p.rn = 1
LEFT JOIN dwd.dim_terminal t ON s.terminal_id = t.terminal_id
WHERE s.rn = 1;
