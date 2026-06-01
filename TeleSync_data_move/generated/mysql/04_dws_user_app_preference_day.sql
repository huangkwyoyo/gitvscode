-- 04 DPI 应用流量偏好
SET @biz_date = '2025-12-31';

CREATE TABLE IF NOT EXISTS dws.dws_user_app_preference_day (
  biz_date DATE COMMENT '业务日期',
  user_id VARCHAR(64) COMMENT '用户ID',
  city_name VARCHAR(64) COMMENT '城市',
  top_app_category VARCHAR(255) COMMENT 'Top应用一级分类',
  top_app_usage_mb DECIMAL(18,3) COMMENT 'Top应用流量',
  total_app_usage_mb DECIMAL(18,3) COMMENT 'DPI总流量',
  top_app_usage_ratio DECIMAL(18,6) COMMENT 'Top应用流量占比',
  total_page_view_count BIGINT COMMENT '总访问次数',
  preference_tag VARCHAR(64) COMMENT '偏好标签',
  created_at DATETIME COMMENT '生成时间',
  PRIMARY KEY (biz_date, user_id)
) COMMENT='用户应用流量偏好日表';

INSERT INTO dws.dws_user_app_preference_day
WITH app_group AS (
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

-- 校验：业务日DPI用户数
SELECT COUNT(DISTINCT user_id) AS dpi_user_count
FROM dwd.fact_dpi_usage_daily
WHERE data_date = @biz_date;

