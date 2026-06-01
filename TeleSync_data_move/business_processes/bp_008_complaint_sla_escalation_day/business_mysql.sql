/*
业务过程：投诉SLA升级分析
SQL类型：业务SQL
SQL口径：MySQL
输入表：dwd.fact_complaint_daily、dwd.dim_user、dwd.dim_product、dwd.dim_org、dwd.fact_billing_monthly
输出表：ads.ads_complaint_sla_escalation_day
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/
SET @biz_date = '2025-12-31';
SET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');

INSERT INTO ads.ads_complaint_sla_escalation_day
WITH
-- 按业务口径拆分中间结果，便于后续迁移转换和静态检查
complaint_30d AS (
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
