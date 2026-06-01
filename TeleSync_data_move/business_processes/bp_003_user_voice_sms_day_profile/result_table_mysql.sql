/*
业务过程：语音短信行为日画像
SQL类型：结果表DDL
SQL口径：MySQL
输入表：dwd.fact_usage_daily、dwd.dim_user、dwd.dim_product
输出表：dws.dws_user_voice_sms_day_profile
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/

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
