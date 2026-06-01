/*
业务过程：用户日价值分层
SQL类型：业务SQL
SQL口径：MySQL
输入表：dwd.fact_user_snapshot_daily、dwd.fact_usage_daily、dwd.fact_recharge_daily、dwd.fact_billing_monthly、dwd.dim_user、dwd.dim_product
输出表：ads.ads_user_daily_value_tag
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/
SET @biz_date = '2025-12-31';
SET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');

INSERT INTO ads.ads_user_daily_value_tag (
  biz_date, user_id, customer_id, account_id, product_id, product_type, city_name,
  is_active_subscriber, daily_revenue_fee, daily_mobile_data_usage_mb, usage_mobile_data_mb,
  voice_usage_min, sms_count, month_billed_revenue_fee, month_outstanding_amount,
  last_30d_recharge_amount, recharge_cover_rate, value_score, value_level, risk_tag, created_at
)
WITH
-- 按业务口径拆分中间结果，便于后续迁移转换和静态检查
recharge_30d AS (
  SELECT user_id, SUM(recharge_amount) AS last_30d_recharge_amount
  FROM dwd.fact_recharge_daily
  WHERE recharge_date BETWEEN DATE_SUB(@biz_date, INTERVAL 29 DAY) AND @biz_date
  GROUP BY user_id
),
billing_month AS (
  SELECT user_id,
         SUM(billed_revenue_fee) AS month_billed_revenue_fee,
         SUM(valid_outstanding_amount) AS month_outstanding_amount
  FROM dwd.fact_billing_monthly
  WHERE billing_month_date = @month_start
  GROUP BY user_id
),
base AS (
  SELECT s.data_date AS biz_date,
         s.user_id,
         u.customer_id,
         u.account_id,
         u.product_id,
         p.product_type,
         u.city_name,
         s.is_active_subscriber,
         s.daily_revenue_fee,
         s.daily_mobile_data_usage_mb,
         COALESCE(us.mobile_data_usage_mb, 0) AS usage_mobile_data_mb,
         COALESCE(us.voice_usage_min, 0) AS voice_usage_min,
         COALESCE(us.sms_count, 0) AS sms_count,
         COALESCE(b.month_billed_revenue_fee, 0) AS month_billed_revenue_fee,
         COALESCE(b.month_outstanding_amount, 0) AS month_outstanding_amount,
         COALESCE(r.last_30d_recharge_amount, 0) AS last_30d_recharge_amount,
         CASE
           WHEN COALESCE(b.month_outstanding_amount, 0) = 0 THEN 1.000000
           ELSE COALESCE(r.last_30d_recharge_amount, 0) / b.month_outstanding_amount
         END AS recharge_cover_rate
  FROM dwd.fact_user_snapshot_daily s
  JOIN dwd.dim_user u ON s.user_id = u.user_id
  LEFT JOIN dwd.dim_product p ON u.product_id = p.product_id
  LEFT JOIN dwd.fact_usage_daily us ON s.user_id = us.user_id AND s.data_date = us.data_date
  LEFT JOIN billing_month b ON s.user_id = b.user_id
  LEFT JOIN recharge_30d r ON s.user_id = r.user_id
  WHERE s.data_date = @biz_date
)
SELECT biz_date, user_id, customer_id, account_id, product_id, product_type, city_name,
       is_active_subscriber, daily_revenue_fee, daily_mobile_data_usage_mb, usage_mobile_data_mb,
       voice_usage_min, sms_count, month_billed_revenue_fee, month_outstanding_amount,
       last_30d_recharge_amount, recharge_cover_rate,
       (
         COALESCE(daily_revenue_fee, 0) * 3
         + COALESCE(last_30d_recharge_amount, 0) * 0.2
         + COALESCE(month_billed_revenue_fee, 0) * 0.5
         + LEAST(COALESCE(usage_mobile_data_mb, 0) / 1024, 20)
         + LEAST(COALESCE(voice_usage_min, 0) / 10, 10)
         - COALESCE(month_outstanding_amount, 0) * 0.4
       ) AS value_score,
       CASE
         WHEN month_outstanding_amount > 0 AND recharge_cover_rate < 0.5 THEN 'RISK_VALUE'
         WHEN daily_revenue_fee >= 20 OR month_billed_revenue_fee >= 180 THEN 'HIGH_VALUE'
         WHEN usage_mobile_data_mb >= 2048 OR voice_usage_min >= 120 THEN 'GROWTH_VALUE'
         ELSE 'NORMAL_VALUE'
       END AS value_level,
       CASE
         WHEN month_outstanding_amount > 0 AND recharge_cover_rate < 0.5 THEN 'ARREARS_RISK'
         WHEN usage_mobile_data_mb < 10 AND voice_usage_min < 1 AND sms_count = 0 THEN 'LOW_ACTIVITY'
         ELSE 'NORMAL'
       END AS risk_tag,
       NOW() AS created_at
FROM base;
