/*
业务过程：充值账单对账日分析
SQL类型：业务SQL
SQL口径：MySQL
输入表：dwd.fact_recharge_daily、dwd.fact_billing_monthly、dwd.dim_user、dwd.dim_product
输出表：ads.ads_user_recharge_billing_reconcile_day
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/
SET @biz_date = '2025-12-31';
SET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');

INSERT INTO ads.ads_user_recharge_billing_reconcile_day
WITH
-- 按业务口径拆分中间结果，便于后续迁移转换和静态检查
recharge AS (
  SELECT user_id,
         SUM(CASE WHEN recharge_date = @biz_date THEN recharge_amount ELSE 0 END) AS daily_recharge_amount,
         SUM(recharge_amount) AS last_7d_recharge_amount
  FROM dwd.fact_recharge_daily
  WHERE recharge_date BETWEEN DATE_SUB(@biz_date, INTERVAL 6 DAY) AND @biz_date
  GROUP BY user_id
),
billing AS (
  SELECT user_id,
         account_id,
         SUM(billed_revenue_fee) AS billed_revenue_fee,
         SUM(valid_outstanding_amount) AS valid_outstanding_amount
  FROM dwd.fact_billing_monthly
  WHERE billing_month_date = @month_start
  GROUP BY user_id, account_id
)
SELECT @biz_date AS biz_date,
       b.user_id,
       b.account_id,
       p.product_type,
       u.payment_timing_type,
       COALESCE(r.daily_recharge_amount, 0) AS daily_recharge_amount,
       COALESCE(r.last_7d_recharge_amount, 0) AS last_7d_recharge_amount,
       b.billed_revenue_fee,
       b.valid_outstanding_amount,
       CASE WHEN b.valid_outstanding_amount = 0 THEN 1.000000
            ELSE COALESCE(r.last_7d_recharge_amount, 0) / b.valid_outstanding_amount END AS recharge_cover_rate,
       CASE
         WHEN b.valid_outstanding_amount > 0 AND COALESCE(r.last_7d_recharge_amount, 0) / NULLIF(b.valid_outstanding_amount, 0) < 0.5 THEN 'INSUFFICIENT_RECHARGE'
         WHEN b.valid_outstanding_amount = 0 AND COALESCE(r.last_7d_recharge_amount, 0) > b.billed_revenue_fee THEN 'PREPAID_ENOUGH'
         WHEN COALESCE(r.daily_recharge_amount, 0) = 0 AND u.payment_timing_type = 'postpaid' THEN 'POSTPAID_NO_RECHARGE'
         ELSE 'BALANCED'
       END AS reconcile_tag,
       NOW() AS created_at
FROM billing b
LEFT JOIN recharge r ON b.user_id = r.user_id
LEFT JOIN dwd.dim_user u ON b.user_id = u.user_id
LEFT JOIN dwd.dim_product p ON u.product_id = p.product_id;
