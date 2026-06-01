/*
业务过程：用户月生命周期分析
SQL类型：结果表DDL
SQL口径：MySQL
输入表：dws.dws_user_month_summary、dwd.dim_user
输出表：dws.dws_user_month_lifecycle
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/

CREATE TABLE IF NOT EXISTS dws.dws_user_month_lifecycle (
  data_month_date DATE COMMENT '业务月',
  user_id VARCHAR(64) COMMENT '用户ID',
  product_id VARCHAR(64) COMMENT '产品ID',
  activation_date DATE COMMENT '入网日期',
  termination_date DATE COMMENT '销户日期',
  monthly_revenue_fee DECIMAL(18,2) COMMENT '当月收入',
  previous_month_revenue_fee DECIMAL(18,2) COMMENT '上月收入',
  mobile_data_usage_mb DECIMAL(18,3) COMMENT '当月流量',
  previous_month_usage_mb DECIMAL(18,3) COMMENT '上月流量',
  voice_usage_min DECIMAL(18,3) COMMENT '当月语音',
  recharge_amount DECIMAL(18,2) COMMENT '当月充值',
  outstanding_amount DECIMAL(18,2) COMMENT '当月欠费',
  revenue_mom_rate DECIMAL(18,6) COMMENT '收入环比',
  usage_mom_rate DECIMAL(18,6) COMMENT '流量环比',
  lifecycle_status VARCHAR(32) COMMENT '生命周期状态',
  warning_reason VARCHAR(255) COMMENT '预警原因',
  created_at DATETIME COMMENT '生成时间',
  PRIMARY KEY (data_month_date, user_id)
) COMMENT='用户月生命周期分析表';
