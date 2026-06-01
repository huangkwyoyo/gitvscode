-- 03 语音短信行为日画像
SET @biz_date = '2025-12-31';

CREATE TABLE IF NOT EXISTS dws.dws_user_voice_sms_day_profile (
  biz_date DATE COMMENT '业务日期',
  user_id VARCHAR(64) COMMENT '用户ID',
  city_name VARCHAR(64) COMMENT '城市',
  product_type VARCHAR(64) COMMENT '产品类型',
  voice_usage_min DECIMAL(18,3) COMMENT '语音分钟数',
  sms_count BIGINT COMMENT '短信条数',
  mobile_data_usage_mb DECIMAL(18,3) COMMENT '流量MB',
  voice_rank_in_group BIGINT COMMENT '同组语音排名',
  group_user_count BIGINT COMMENT '同组用户数',
  voice_percent_rank DECIMAL(18,6) COMMENT '语音分位',
  behavior_tag VARCHAR(64) COMMENT '行为标签',
  created_at DATETIME COMMENT '生成时间',
  PRIMARY KEY (biz_date, user_id)
) COMMENT='用户语音短信日画像表';

INSERT INTO dws.dws_user_voice_sms_day_profile
WITH base AS (
  SELECT f.data_date AS biz_date,
         f.user_id,
         u.city_name,
         p.product_type,
         f.voice_usage_min,
         f.sms_count,
         f.mobile_data_usage_mb
  FROM dwd.fact_usage_daily f
  JOIN dwd.dim_user u ON f.user_id = u.user_id
  LEFT JOIN dwd.dim_product p ON u.product_id = p.product_id
  WHERE f.data_date = @biz_date
),
ranked AS (
  SELECT b.*,
         RANK() OVER (PARTITION BY city_name, product_type ORDER BY voice_usage_min DESC) AS voice_rank_in_group,
         COUNT(*) OVER (PARTITION BY city_name, product_type) AS group_user_count,
         PERCENT_RANK() OVER (PARTITION BY city_name, product_type ORDER BY voice_usage_min) AS voice_percent_rank,
         PERCENT_RANK() OVER (PARTITION BY city_name, product_type ORDER BY sms_count) AS sms_percent_rank
  FROM base b
)
SELECT biz_date,
       user_id,
       city_name,
       product_type,
       voice_usage_min,
       sms_count,
       mobile_data_usage_mb,
       voice_rank_in_group,
       group_user_count,
       voice_percent_rank,
       CASE
         WHEN voice_usage_min = 0 AND sms_count = 0 AND mobile_data_usage_mb = 0 THEN 'SILENT_DAY'
         WHEN voice_percent_rank >= 0.90 THEN 'HIGH_VOICE'
         WHEN sms_percent_rank >= 0.95 THEN 'HIGH_SMS'
         ELSE 'NORMAL'
       END AS behavior_tag,
       NOW() AS created_at
FROM ranked;

-- 校验：业务日用量行数
SELECT COUNT(*) AS usage_count
FROM dwd.fact_usage_daily
WHERE data_date = @biz_date;

