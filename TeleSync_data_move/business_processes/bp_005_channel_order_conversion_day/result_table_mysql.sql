/*
业务过程：渠道订单转化日分析
SQL类型：结果表DDL
SQL口径：MySQL
输入表：dwd.fact_order_daily、dwd.dim_channel、dwd.dim_product
输出表：dws.dws_channel_order_conversion_day
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/

CREATE TABLE IF NOT EXISTS dws.dws_channel_order_conversion_day (
  biz_date DATE COMMENT '业务日期',
  channel_id VARCHAR(64) COMMENT '渠道ID',
  channel_type VARCHAR(64) COMMENT '渠道类型',
  product_type VARCHAR(64) COMMENT '产品类型',
  order_count BIGINT COMMENT '订单数',
  paid_order_count BIGINT COMMENT '支付订单数',
  cancelled_order_count BIGINT COMMENT '取消订单数',
  created_order_count BIGINT COMMENT '创建未支付订单数',
  payment_amount DECIMAL(18,2) COMMENT '支付金额',
  conversion_rate DECIMAL(18,6) COMMENT '支付转化率',
  cancel_rate DECIMAL(18,6) COMMENT '取消率',
  avg_pay_minutes DECIMAL(18,3) COMMENT '平均支付时延分钟',
  channel_type_avg_conversion_rate DECIMAL(18,6) COMMENT '同类型平均转化率',
  channel_risk_tag VARCHAR(64) COMMENT '渠道风险标签',
  created_at DATETIME COMMENT '生成时间',
  PRIMARY KEY (biz_date, channel_id, product_type)
) COMMENT='渠道订单转化日分析表';
