-- 07 欠费风险用户识别
SET @biz_date = '2025-12-31';
SET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');

CREATE TABLE IF NOT EXISTS ads.ads_user_arrears_risk_day (
  biz_date DATE COMMENT '业务日期',
  user_id VARCHAR(64) COMMENT '用户ID',
  account_id VARCHAR(64) COMMENT '账户ID',
  product_type VARCHAR(64) COMMENT '产品类型',
  arrears_month_count BIGINT COMMENT '最近3个月欠费月份数',
  max_outstanding_amount DECIMAL(18,2) COMMENT '最近3个月最大欠费',
  valid_outstanding_amount DECIMAL(18,2) COMMENT '当前有效欠费',
  last_30d_recharge_amount DECIMAL(18,2) COMMENT '近30日充值',
  last_30d_usage_mb DECIMAL(18,3) COMMENT '近30日流量',
  last_30d_voice_min DECIMAL(18,3) COMMENT '近30日语音',
  recharge_cover_rate DECIMAL(18,6) COMMENT '充值覆盖率',
  risk_score DECIMAL(18,3) COMMENT '风险评分',
  risk_level VARCHAR(32) COMMENT '风险等级',
  created_at DATETIME COMMENT '生成时间',
  PRIMARY KEY (biz_date, user_id)
) COMMENT='欠费风险用户日识别表';

INSERT INTO ads.ads_user_arrears_risk_day
WITH billing_3m AS (
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

-- 校验：最近3个月欠费用户数
SELECT COUNT(DISTINCT user_id) AS arrears_user_count
FROM dwd.fact_billing_monthly
WHERE billing_month_date BETWEEN DATE_SUB(@month_start, INTERVAL 2 MONTH) AND @month_start
  AND valid_outstanding_amount > 0;

