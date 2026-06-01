/*
业务过程：终端合约履约分析
SQL类型：结果表DDL
SQL口径：MySQL
输入表：ods.ods_terminal_sales_daily、ods.ods_terminal_presale_daily、dwd.dim_user、dwd.dim_terminal
输出表：dws.dws_terminal_contract_fulfillment_day
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/

CREATE TABLE IF NOT EXISTS dws.dws_terminal_contract_fulfillment_day (
  biz_date DATE COMMENT '业务日期',
  user_id VARCHAR(64) COMMENT '用户ID',
  terminal_id VARCHAR(64) COMMENT '终端ID',
  terminal_model_name VARCHAR(255) COMMENT '终端型号',
  is_super_sim_supported TINYINT COMMENT '是否支持超级SIM',
  payment_transaction_amount DECIMAL(18,2) COMMENT '支付金额',
  refund_amount DECIMAL(18,2) COMMENT '退款金额',
  monthly_mobile_usage_mb DECIMAL(18,3) COMMENT '月流量',
  monthly_voice_call_count BIGINT COMMENT '月语音次数',
  monthly_sms_count BIGINT COMMENT '月短信条数',
  fulfillment_score DECIMAL(18,3) COMMENT '履约评分',
  fulfillment_tag VARCHAR(64) COMMENT '履约标签',
  created_at DATETIME COMMENT '生成时间',
  PRIMARY KEY (biz_date, user_id, terminal_id)
) COMMENT='终端合约履约日分析表';
