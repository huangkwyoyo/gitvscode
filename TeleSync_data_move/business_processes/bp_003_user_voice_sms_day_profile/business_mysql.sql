/*
业务过程：语音短信行为日画像
SQL类型：业务SQL
SQL口径：MySQL
输入表：dwd.fact_usage_daily、dwd.dim_user、dwd.dim_product
输出表：dws.dws_user_voice_sms_day_profile
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/
SET @biz_date = '2025-12-31';
SET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');

INSERT INTO dws.dws_user_voice_sms_day_profile
WITH
-- 按业务口径拆分中间结果，便于后续迁移转换和静态检查
base AS (
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
