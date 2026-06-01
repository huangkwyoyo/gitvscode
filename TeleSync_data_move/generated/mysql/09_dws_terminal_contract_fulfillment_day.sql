-- 09 终端合约履约分析
SET @biz_date = '2025-12-31';

CREATE TABLE IF NOT EXISTS dws.dws_terminal_contract_fulfillment_day (
  biz_date DATE COMMENT '业务日期',
  user_id VARCHAR(64) COMMENT '用户ID',
  terminal_id VARCHAR(64) COMMENT '终端ID',
  terminal_model_name VARCHAR(255) COMMENT '终端型号',
  is_super_sim_supported TINYINT COMMENT '是否支持超级SIM',
  payment_transaction_amount DECIMAL(18,2) COMMENT '支付金额',
  refund_amount DECIMAL(18,2) COMMENT '退款金额',
  monthly_mobile_usage_mb DECIMAL(18,3) COMMENT '月流量',
  monthly_voice_call_count BIGINT COMMENT '月语音次数',
  monthly_sms_count BIGINT COMMENT '月短信条数',
  fulfillment_score DECIMAL(18,3) COMMENT '履约评分',
  fulfillment_tag VARCHAR(64) COMMENT '履约标签',
  created_at DATETIME COMMENT '生成时间',
  PRIMARY KEY (biz_date, user_id, terminal_id)
) COMMENT='终端合约履约日分析表';

INSERT INTO dws.dws_terminal_contract_fulfillment_day
WITH sales AS (
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

-- 校验：业务日终端销售记录数
SELECT COUNT(*) AS terminal_sales_count
FROM ods.ods_terminal_sales_daily
WHERE DATE(data_time) = @biz_date;

