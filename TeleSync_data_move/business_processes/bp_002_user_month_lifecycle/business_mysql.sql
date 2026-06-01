/*
业务过程：用户月生命周期分析
SQL类型：业务SQL
SQL口径：MySQL
输入表：dws.dws_user_month_summary、dwd.dim_user
输出表：dws.dws_user_month_lifecycle
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/
SET @biz_date = '2025-12-31';
SET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');

INSERT INTO dws.dws_user_month_lifecycle
WITH
-- 按业务口径拆分中间结果，便于后续迁移转换和静态检查
month_seq AS (
  SELECT m.*,
         LAG(monthly_revenue_fee) OVER (PARTITION BY user_id ORDER BY data_month_date) AS previous_month_revenue_fee,
         LAG(mobile_data_usage_mb) OVER (PARTITION BY user_id ORDER BY data_month_date) AS previous_month_usage_mb,
         LAG(recharge_amount) OVER (PARTITION BY user_id ORDER BY data_month_date) AS previous_month_recharge_amount
  FROM dws.dws_user_month_summary m
  WHERE data_month_date BETWEEN DATE_SUB(@month_start, INTERVAL 2 MONTH) AND @month_start
),
current_month AS (
  SELECT data_month_date, user_id, monthly_revenue_fee, mobile_data_usage_mb, voice_usage_min, recharge_amount, outstanding_amount, previous_month_revenue_fee, previous_month_usage_mb, previous_month_recharge_amount
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
