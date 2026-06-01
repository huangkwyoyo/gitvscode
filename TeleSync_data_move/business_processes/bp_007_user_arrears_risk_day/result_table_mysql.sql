/*
业务过程：欠费风险用户识别
SQL类型：结果表DDL
SQL口径：MySQL
输入表：dwd.fact_billing_monthly、dwd.fact_recharge_daily、dwd.fact_usage_daily、dwd.dim_user、dwd.dim_product
输出表：ads.ads_user_arrears_risk_day
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/

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
