-- 06 充值账单对账日分析
SET @biz_date = '2025-12-31';
SET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');

CREATE TABLE IF NOT EXISTS ads.ads_user_recharge_billing_reconcile_day (
  biz_date DATE COMMENT '业务日期',
  user_id VARCHAR(64) COMMENT '用户ID',
  account_id VARCHAR(64) COMMENT '账户ID',
  product_type VARCHAR(64) COMMENT '产品类型',
  payment_timing_type VARCHAR(64) COMMENT '付费类型',
  daily_recharge_amount DECIMAL(18,2) COMMENT '当日充值',
  last_7d_recharge_amount DECIMAL(18,2) COMMENT '近7日充值',
  billed_revenue_fee DECIMAL(18,2) COMMENT '当月出账收入',
  valid_outstanding_amount DECIMAL(18,2) COMMENT '有效欠费',
  recharge_cover_rate DECIMAL(18,6) COMMENT '充值覆盖率',
  reconcile_tag VARCHAR(64) COMMENT '对账标签',
  created_at DATETIME COMMENT '生成时间',
  PRIMARY KEY (biz_date, user_id)
) COMMENT='用户充值账单对账日表';

INSERT INTO ads.ads_user_recharge_billing_reconcile_day
WITH recharge AS (
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

-- 校验：业务月账单用户数
SELECT COUNT(DISTINCT user_id) AS billing_user_count
FROM dwd.fact_billing_monthly
WHERE billing_month_date = @month_start;

