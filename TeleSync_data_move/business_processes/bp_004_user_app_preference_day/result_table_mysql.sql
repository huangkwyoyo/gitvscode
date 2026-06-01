/*
业务过程：DPI应用流量偏好
SQL类型：结果表DDL
SQL口径：MySQL
输入表：dwd.fact_dpi_usage_daily、dwd.dim_application、dwd.fact_usage_daily、dwd.dim_user
输出表：dws.dws_user_app_preference_day
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/

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
