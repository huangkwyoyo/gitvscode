/*
业务过程：欠费风险用户识别
SQL类型：业务SQL
SQL口径：MySQL
输入表：dwd.fact_billing_monthly、dwd.fact_recharge_daily、dwd.fact_usage_daily、dwd.dim_user、dwd.dim_product
输出表：ads.ads_user_arrears_risk_day
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/
SET @biz_date = '2025-12-31';
SET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');

INSERT INTO ads.ads_user_arrears_risk_day
WITH
-- 按业务口径拆分中间结果，便于后续迁移转换和静态检查
billing_3m AS (
  SELECT user_id,
         account_id,
         SUM(CASE WHEN valid_outstanding_amount > 0 THEN 1 ELSE 0 END) AS arrears_month_count,
         MAX(valid_outstanding_amount) AS max_outstanding_amount,
         SUM(CASE WHEN billing_month_date = @month_start THEN valid_outstanding_amount ELSE 0 END) AS valid_outstanding_amount
  FROM dwd.fact_billing_monthly
  WHERE billing_month_date BETWEEN DATE_SUB(@month_start, INTERVAL 2 MONTH) AND @month_start
  GROUP BY user_id, account_id
),
recharge_30d AS (
  SELECT user_id, SUM(recharge_amount) AS last_30d_recharge_amount
  FROM dwd.fact_recharge_daily
  WHERE recharge_date BETWEEN DATE_SUB(@biz_date, INTERVAL 29 DAY) AND @biz_date
  GROUP BY user_id
),
usage_30d AS (
  SELECT user_id,
         SUM(mobile_data_usage_mb) AS last_30d_usage_mb,
         SUM(voice_usage_min) AS last_30d_voice_min
  FROM dwd.fact_usage_daily
  WHERE data_date BETWEEN DATE_SUB(@biz_date, INTERVAL 29 DAY) AND @biz_date
  GROUP BY user_id
),
base AS (
  SELECT @biz_date AS biz_date,
         b.user_id,
         b.account_id,
         p.product_type,
         b.arrears_month_count,
         b.max_outstanding_amount,
         b.valid_outstanding_amount,
         COALESCE(r.last_30d_recharge_amount, 0) AS last_30d_recharge_amount,
         COALESCE(us.last_30d_usage_mb, 0) AS last_30d_usage_mb,
         COALESCE(us.last_30d_voice_min, 0) AS last_30d_voice_min,
         CASE WHEN b.valid_outstanding_amount = 0 THEN 1.000000
              ELSE COALESCE(r.last_30d_recharge_amount, 0) / b.valid_outstanding_amount END AS recharge_cover_rate
  FROM billing_3m b
  LEFT JOIN recharge_30d r ON b.user_id = r.user_id
  LEFT JOIN usage_30d us ON b.user_id = us.user_id
  LEFT JOIN dwd.dim_user u ON b.user_id = u.user_id
  LEFT JOIN dwd.dim_product p ON u.product_id = p.product_id
)
SELECT biz_date,
       user_id,
       account_id,
       product_type,
       arrears_month_count,
       max_outstanding_amount,
       valid_outstanding_amount,
       last_30d_recharge_amount,
       last_30d_usage_mb,
       last_30d_voice_min,
       recharge_cover_rate,
       valid_outstanding_amount * 0.6
         + arrears_month_count * 30
         + CASE WHEN recharge_cover_rate < 0.3 THEN 50 ELSE 0 END
         + CASE WHEN last_30d_usage_mb < 100 AND last_30d_voice_min < 10 THEN 30 ELSE 0 END AS risk_score,
       CASE
         WHEN arrears_month_count >= 3 OR valid_outstanding_amount >= 200 THEN 'HIGH'
         WHEN arrears_month_count >= 2 OR recharge_cover_rate < 0.3 THEN 'MEDIUM'
         WHEN valid_outstanding_amount > 0 THEN 'LOW'
         ELSE 'NONE'
       END AS risk_level,
       NOW() AS created_at
FROM base
WHERE valid_outstanding_amount > 0 OR arrears_month_count > 0;
