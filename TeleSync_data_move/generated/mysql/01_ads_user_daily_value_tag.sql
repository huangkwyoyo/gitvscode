-- 01 用户日价值分层
SET @biz_date = '2025-12-31';
SET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');

CREATE TABLE IF NOT EXISTS ads.ads_user_daily_value_tag (
  biz_date DATE COMMENT '业务日期',
  user_id VARCHAR(64) COMMENT '用户ID',
  customer_id VARCHAR(64) COMMENT '客户ID',
  account_id VARCHAR(64) COMMENT '账户ID',
  product_id VARCHAR(64) COMMENT '产品ID',
  product_type VARCHAR(64) COMMENT '产品类型',
  city_name VARCHAR(64) COMMENT '城市',
  is_active_subscriber TINYINT COMMENT '是否活跃用户',
  daily_revenue_fee DECIMAL(18,2) COMMENT '当日收入',
  daily_mobile_data_usage_mb DECIMAL(18,3) COMMENT '当日快照流量',
  usage_mobile_data_mb DECIMAL(18,3) COMMENT '当日使用流量',
  voice_usage_min DECIMAL(18,3) COMMENT '当日语音分钟数',
  sms_count BIGINT COMMENT '当日短信条数',
  month_billed_revenue_fee DECIMAL(18,2) COMMENT '当月出账收入',
  month_outstanding_amount DECIMAL(18,2) COMMENT '当月欠费',
  last_30d_recharge_amount DECIMAL(18,2) COMMENT '近30日充值金额',
  recharge_cover_rate DECIMAL(18,6) COMMENT '充值覆盖率',
  value_score DECIMAL(18,3) COMMENT '综合价值评分',
  value_level VARCHAR(32) COMMENT '用户价值层级',
  risk_tag VARCHAR(64) COMMENT '风险标签',
  created_at DATETIME COMMENT '生成时间',
  PRIMARY KEY (biz_date, user_id)
) COMMENT='用户日价值分层结果表';

INSERT INTO ads.ads_user_daily_value_tag (
  biz_date, user_id, customer_id, account_id, product_id, product_type, city_name,
  is_active_subscriber, daily_revenue_fee, daily_mobile_data_usage_mb, usage_mobile_data_mb,
  voice_usage_min, sms_count, month_billed_revenue_fee, month_outstanding_amount,
  last_30d_recharge_amount, recharge_cover_rate, value_score, value_level, risk_tag, created_at
)
WITH recharge_30d AS (
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

-- 校验：源端业务日期快照行数
SELECT COUNT(*) AS source_snapshot_count
FROM dwd.fact_user_snapshot_daily
WHERE data_date = @biz_date;

