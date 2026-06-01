/*
业务过程：充值账单对账日分析
SQL类型：结果表DDL
SQL口径：MySQL
输入表：dwd.fact_recharge_daily、dwd.fact_billing_monthly、dwd.dim_user、dwd.dim_product
输出表：ads.ads_user_recharge_billing_reconcile_day
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/

CREATE TABLE IF NOT EXISTS ads.ads_user_recharge_billing_reconcile_day (
  biz_date DATE COMMENT '业务日期',
  user_id VARCHAR(64) COMMENT '用户ID',
  account_id VARCHAR(64) COMMENT '账户ID',
  product_type VARCHAR(64) COMMENT '产品类型',
  payment_timing_type VARCHAR(64) COMMENT '付费类型',
  daily_recharge_amount DECIMAL(18,2) COMMENT '当日充值',
  last_7d_recharge_amount DECIMAL(18,2) COMMENT '近7日充值',
  billed_revenue_fee DECIMAL(18,2) COMMENT '当月出账收入',
  valid_outstanding_amount DECIMAL(18,2) COMMENT '有效欠费',
  recharge_cover_rate DECIMAL(18,6) COMMENT '充值覆盖率',
  reconcile_tag VARCHAR(64) COMMENT '对账标签',
  created_at DATETIME COMMENT '生成时间',
  PRIMARY KEY (biz_date, user_id)
) COMMENT='用户充值账单对账日表';
