/*
业务过程：DPI应用流量偏好
SQL类型：业务SQL
SQL口径：MySQL
输入表：dwd.fact_dpi_usage_daily、dwd.dim_application、dwd.fact_usage_daily、dwd.dim_user
输出表：dws.dws_user_app_preference_day
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/
SET @biz_date = '2025-12-31';
SET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');

INSERT INTO dws.dws_user_app_preference_day
WITH
-- 按业务口径拆分中间结果，便于后续迁移转换和静态检查
app_group AS (
  SELECT f.data_date AS biz_date,
         f.user_id,
         a.application_level1_name,
         SUM(f.page_view_count) AS page_view_count,
         SUM(f.application_traffic_usage_mb) AS app_usage_mb
  FROM dwd.fact_dpi_usage_daily f
  JOIN dwd.dim_application a ON f.application_id = a.application_id
  WHERE f.data_date = @biz_date
  GROUP BY f.data_date, f.user_id, a.application_level1_name
),
ranked AS (
  SELECT ag.*,
         SUM(app_usage_mb) OVER (PARTITION BY biz_date, user_id) AS total_app_usage_mb,
         SUM(page_view_count) OVER (PARTITION BY biz_date, user_id) AS total_page_view_count,
         ROW_NUMBER() OVER (PARTITION BY biz_date, user_id ORDER BY app_usage_mb DESC, page_view_count DESC) AS rn
  FROM app_group ag
)
SELECT r.biz_date,
       r.user_id,
       u.city_name,
       r.application_level1_name AS top_app_category,
       r.app_usage_mb AS top_app_usage_mb,
       r.total_app_usage_mb,
       CASE WHEN r.total_app_usage_mb = 0 THEN 0 ELSE r.app_usage_mb / r.total_app_usage_mb END AS top_app_usage_ratio,
       r.total_page_view_count,
       CASE
         WHEN r.application_level1_name IN ('视频', '短视频') AND r.app_usage_mb >= 2048 AND r.app_usage_mb / NULLIF(r.total_app_usage_mb, 0) >= 0.6 THEN 'HEAVY_VIDEO'
         WHEN r.page_view_count < 5 AND r.app_usage_mb >= 1024 THEN 'LOW_PV_HIGH_TRAFFIC'
         WHEN r.application_level1_name = '游戏' AND r.page_view_count >= 50 THEN 'GAME_ACTIVE'
         ELSE 'NORMAL'
       END AS preference_tag,
       NOW() AS created_at
FROM ranked r
LEFT JOIN dwd.dim_user u ON r.user_id = u.user_id
WHERE r.rn = 1;
