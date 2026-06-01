-- 08 投诉SLA升级分析
SET @biz_date = '2025-12-31';
SET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');

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

INSERT INTO ads.ads_complaint_sla_escalation_day
WITH complaint_30d AS (
  SELECT user_id, COUNT(*) AS last_30d_complaint_count
  FROM dwd.fact_complaint_daily
  WHERE complaint_date BETWEEN DATE_SUB(@biz_date, INTERVAL 29 DAY) AND @biz_date
  GROUP BY user_id
),
billing AS (
  SELECT user_id, SUM(billed_revenue_fee) AS month_billed_revenue_fee
  FROM dwd.fact_billing_monthly
  WHERE billing_month_date = @month_start
  GROUP BY user_id
),
base AS (
  SELECT c.complaint_date AS biz_date,
         c.complaint_event_id,
         c.user_id,
         c.responsible_department_id,
         o.department_name,
         c.complaint_type,
         c.complaint_status,
         c.is_first_dispatch_success,
         c.complaint_handle_duration,
         CASE
           WHEN c.complaint_type = '网络质量' THEN 24
           WHEN c.complaint_type = '费用争议' THEN 48
           ELSE 72
         END AS sla_limit_hour,
         COALESCE(c30.last_30d_complaint_count, 0) AS last_30d_complaint_count,
         COALESCE(b.month_billed_revenue_fee, 0) AS month_billed_revenue_fee,
         COUNT(*) OVER (PARTITION BY c.responsible_department_id) AS department_complaint_count
  FROM dwd.fact_complaint_daily c
  LEFT JOIN complaint_30d c30 ON c.user_id = c30.user_id
  LEFT JOIN billing b ON c.user_id = b.user_id
  LEFT JOIN dwd.dim_org o ON c.responsible_department_id = o.department_id
  WHERE c.complaint_date = @biz_date
),
ranked AS (
  SELECT b.*,
         DENSE_RANK() OVER (ORDER BY department_complaint_count DESC) AS department_pressure_rank
  FROM base b
)
SELECT biz_date,
       complaint_event_id,
       user_id,
       responsible_department_id,
       department_name,
       complaint_type,
       complaint_status,
       complaint_handle_duration,
       sla_limit_hour,
       CASE WHEN complaint_handle_duration > sla_limit_hour THEN 1 ELSE 0 END AS is_sla_timeout,
       last_30d_complaint_count,
       month_billed_revenue_fee,
       department_pressure_rank,
       CASE
         WHEN is_first_dispatch_success = 0 AND complaint_handle_duration > sla_limit_hour THEN 'P1'
         WHEN last_30d_complaint_count >= 3 THEN 'P1'
         WHEN month_billed_revenue_fee >= 200 AND complaint_handle_duration > sla_limit_hour THEN 'P2'
         WHEN complaint_handle_duration > sla_limit_hour THEN 'P2'
         ELSE 'P3'
       END AS escalation_level,
       NOW() AS created_at
FROM ranked
WHERE complaint_handle_duration > sla_limit_hour
   OR last_30d_complaint_count >= 2
   OR month_billed_revenue_fee >= 200;

-- 校验：业务日投诉工单数
SELECT COUNT(*) AS complaint_count
FROM dwd.fact_complaint_daily
WHERE complaint_date = @biz_date;

