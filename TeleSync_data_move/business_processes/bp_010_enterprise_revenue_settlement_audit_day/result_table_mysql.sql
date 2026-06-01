/*
业务过程：政企收入与结算稽核
SQL类型：结果表DDL
SQL口径：MySQL
输入表：ods.ods_account_income_monthly、ods.ods_settlement_allocation_daily、ods.ods_post_settlement_allocation_daily、dwd.dim_account、dwd.dim_org
输出表：ads.ads_enterprise_revenue_settlement_audit_day
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/

CREATE TABLE IF NOT EXISTS ads.ads_enterprise_revenue_settlement_audit_day (
  biz_date DATE COMMENT '业务日期',
  account_id VARCHAR(64) COMMENT '账户ID',
  account_name VARCHAR(255) COMMENT '账户名称',
  department_id VARCHAR(64) COMMENT '归属部门ID',
  department_name VARCHAR(255) COMMENT '归属部门名称',
  revenue_fee DECIMAL(18,2) COMMENT '收入金额',
  settlement_fee DECIMAL(18,2) COMMENT '结算分摊金额',
  post_settlement_fee DECIMAL(18,2) COMMENT '后向结算金额',
  tax_fee DECIMAL(18,2) COMMENT '税费',
  revenue_settlement_diff DECIMAL(18,2) COMMENT '收入结算差异',
  revenue_settlement_diff_rate DECIMAL(18,6) COMMENT '收入结算差异率',
  audit_tag VARCHAR(64) COMMENT '稽核标签',
  created_at DATETIME COMMENT '生成时间',
  PRIMARY KEY (biz_date, account_id, department_id)
) COMMENT='政企收入结算稽核日表';
