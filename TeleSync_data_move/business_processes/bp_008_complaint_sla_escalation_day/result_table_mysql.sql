/*
业务过程：投诉SLA升级分析
SQL类型：结果表DDL
SQL口径：MySQL
输入表：dwd.fact_complaint_daily、dwd.dim_user、dwd.dim_product、dwd.dim_org、dwd.fact_billing_monthly
输出表：ads.ads_complaint_sla_escalation_day
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/

CREATE TABLE IF NOT EXISTS ads.ads_complaint_sla_escalation_day (
  biz_date DATE COMMENT '业务日期',
  complaint_event_id VARCHAR(64) COMMENT '投诉事件ID',
  user_id VARCHAR(64) COMMENT '用户ID',
  responsible_department_id VARCHAR(64) COMMENT '责任部门ID',
  department_name VARCHAR(255) COMMENT '责任部门名称',
  complaint_type VARCHAR(64) COMMENT '投诉类型',
  complaint_status VARCHAR(64) COMMENT '投诉状态',
  complaint_handle_duration BIGINT COMMENT '处理时长小时',
  sla_limit_hour BIGINT COMMENT 'SLA阈值小时',
  is_sla_timeout TINYINT COMMENT '是否SLA超时',
  last_30d_complaint_count BIGINT COMMENT '近30日投诉次数',
  month_billed_revenue_fee DECIMAL(18,2) COMMENT '当月出账收入',
  department_pressure_rank BIGINT COMMENT '部门投诉压力排名',
  escalation_level VARCHAR(32) COMMENT '升级等级',
  created_at DATETIME COMMENT '生成时间',
  PRIMARY KEY (biz_date, complaint_event_id)
) COMMENT='投诉SLA升级日分析表';
