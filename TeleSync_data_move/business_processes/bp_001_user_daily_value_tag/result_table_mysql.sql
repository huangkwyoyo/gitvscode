/*
业务过程：用户日价值分层
SQL类型：结果表DDL
SQL口径：MySQL
输入表：dwd.fact_user_snapshot_daily、dwd.fact_usage_daily、dwd.fact_recharge_daily、dwd.fact_billing_monthly、dwd.dim_user、dwd.dim_product
输出表：ads.ads_user_daily_value_tag
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/

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
