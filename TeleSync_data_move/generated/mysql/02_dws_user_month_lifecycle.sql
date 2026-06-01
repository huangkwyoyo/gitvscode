-- 02 用户月生命周期分析
SET @biz_date = '2025-12-31';
SET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');

CREATE TABLE IF NOT EXISTS dws.dws_user_month_lifecycle (
  data_month_date DATE COMMENT '业务月',
  user_id VARCHAR(64) COMMENT '用户ID',
  product_id VARCHAR(64) COMMENT '产品ID',
  activation_date DATE COMMENT '入网日期',
  termination_date DATE COMMENT '销户日期',
  monthly_revenue_fee DECIMAL(18,2) COMMENT '当月收入',
  previous_month_revenue_fee DECIMAL(18,2) COMMENT '上月收入',
  mobile_data_usage_mb DECIMAL(18,3) COMMENT '当月流量',
  previous_month_usage_mb DECIMAL(18,3) COMMENT '上月流量',
  voice_usage_min DECIMAL(18,3) COMMENT '当月语音',
  recharge_amount DECIMAL(18,2) COMMENT '当月充值',
  outstanding_amount DECIMAL(18,2) COMMENT '当月欠费',
  revenue_mom_rate DECIMAL(18,6) COMMENT '收入环比',
  usage_mom_rate DECIMAL(18,6) COMMENT '流量环比',
  lifecycle_status VARCHAR(32) COMMENT '生命周期状态',
  warning_reason VARCHAR(255) COMMENT '预警原因',
  created_at DATETIME COMMENT '生成时间',
  PRIMARY KEY (data_month_date, user_id)
) COMMENT='用户月生命周期分析表';

INSERT INTO dws.dws_user_month_lifecycle
WITH month_seq AS (
  SELECT m.*,
         LAG(monthly_revenue_fee) OVER (PARTITION BY user_id ORDER BY data_month_date) AS previous_month_revenue_fee,
         LAG(mobile_data_usage_mb) OVER (PARTITION BY user_id ORDER BY data_month_date) AS previous_month_usage_mb,
         LAG(recharge_amount) OVER (PARTITION BY user_id ORDER BY data_month_date) AS previous_month_recharge_amount
  FROM dws.dws_user_month_summary m
  WHERE data_month_date BETWEEN DATE_SUB(@month_start, INTERVAL 2 MONTH) AND @month_start
),
current_month AS (
  SELECT *
  FROM month_seq
  WHERE data_month_date = @month_start
)
SELECT c.data_month_date,
       c.user_id,
       u.product_id,
       u.activation_date,
       u.termination_date,
       c.monthly_revenue_fee,
       COALESCE(c.previous_month_revenue_fee, 0) AS previous_month_revenue_fee,
       c.mobile_data_usage_mb,
       COALESCE(c.previous_month_usage_mb, 0) AS previous_month_usage_mb,
       c.voice_usage_min,
       c.recharge_amount,
       c.outstanding_amount,
       CASE WHEN COALESCE(c.previous_month_revenue_fee, 0) = 0 THEN NULL
            ELSE (c.monthly_revenue_fee - c.previous_month_revenue_fee) / c.previous_month_revenue_fee END AS revenue_mom_rate,
       CASE WHEN COALESCE(c.previous_month_usage_mb, 0) = 0 THEN NULL
            ELSE (c.mobile_data_usage_mb - c.previous_month_usage_mb) / c.previous_month_usage_mb END AS usage_mom_rate,
       CASE
         WHEN u.termination_date IS NOT NULL AND u.termination_date <= LAST_DAY(@month_start) THEN 'CHURNED'
         WHEN DATE_FORMAT(u.activation_date, '%Y-%m-01') = @month_start THEN 'NEW'
         WHEN c.outstanding_amount > 0 AND c.monthly_revenue_fee < COALESCE(c.previous_month_revenue_fee, 0) THEN 'CHURN_WARNING'
         WHEN c.mobile_data_usage_mb < 100 AND c.voice_usage_min < 5 AND c.recharge_amount = 0 THEN 'SILENT'
         ELSE 'ACTIVE'
       END AS lifecycle_status,
       CASE
         WHEN u.termination_date IS NOT NULL AND u.termination_date <= LAST_DAY(@month_start) THEN '用户已销户'
         WHEN c.outstanding_amount > 0 AND c.monthly_revenue_fee < COALESCE(c.previous_month_revenue_fee, 0) THEN '欠费且收入下降'
         WHEN c.mobile_data_usage_mb < 100 AND c.voice_usage_min < 5 AND c.recharge_amount = 0 THEN '低使用且无充值'
         ELSE '正常'
       END AS warning_reason,
       NOW() AS created_at
FROM current_month c
JOIN dwd.dim_user u ON c.user_id = u.user_id;

-- 校验：业务月用户汇总行数
SELECT COUNT(*) AS source_month_user_count
FROM dws.dws_user_month_summary
WHERE data_month_date = @month_start;

