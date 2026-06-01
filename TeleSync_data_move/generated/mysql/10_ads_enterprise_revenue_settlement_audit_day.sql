-- 10 政企收入与结算稽核
SET @biz_date = '2025-12-31';

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

INSERT INTO ads.ads_enterprise_revenue_settlement_audit_day
WITH income AS (
  SELECT DATE(data_time) AS biz_date,
         CAST(account_id AS CHAR(64)) AS account_id,
         MAX(CAST(account_name AS CHAR(255))) AS account_name,
         CAST(acquisition_department_id AS CHAR(64)) AS department_id,
         SUM(COALESCE(inc_fee, 0)) AS revenue_fee,
         SUM(COALESCE(tax_fee, 0)) AS tax_fee
  FROM ods.ods_account_income_monthly
  WHERE DATE(data_time) = @biz_date
  GROUP BY DATE(data_time), CAST(account_id AS CHAR(64)), CAST(acquisition_department_id AS CHAR(64))
),
settlement AS (
  SELECT DATE(data_time) AS biz_date,
         CAST(service_number_id AS CHAR(64)) AS account_id,
         CAST(acquisition_department_id AS CHAR(64)) AS department_id,
         SUM(COALESCE(revenue_fee, 0)) AS settlement_fee
  FROM ods.ods_settlement_allocation_daily
  WHERE DATE(data_time) = @biz_date
  GROUP BY DATE(data_time), CAST(service_number_id AS CHAR(64)), CAST(acquisition_department_id AS CHAR(64))
),
post_settlement AS (
  SELECT DATE(data_time) AS biz_date,
         CAST(customer_contact_phone_name AS CHAR(64)) AS account_id,
         CAST(duty_department_id AS CHAR(64)) AS department_id,
         SUM(COALESCE(comps_money_amount, 0)) AS post_settlement_fee
  FROM ods.ods_post_settlement_allocation_daily
  WHERE DATE(data_time) = @biz_date
  GROUP BY DATE(data_time), CAST(customer_contact_phone_name AS CHAR(64)), CAST(duty_department_id AS CHAR(64))
),
merged AS (
  SELECT i.biz_date,
         i.account_id,
         i.account_name,
         i.department_id,
         i.revenue_fee,
         COALESCE(s.settlement_fee, 0) AS settlement_fee,
         COALESCE(ps.post_settlement_fee, 0) AS post_settlement_fee,
         i.tax_fee
  FROM income i
  LEFT JOIN settlement s ON i.biz_date = s.biz_date AND i.account_id = s.account_id AND i.department_id = s.department_id
  LEFT JOIN post_settlement ps ON i.biz_date = ps.biz_date AND i.account_id = ps.account_id AND i.department_id = ps.department_id
  UNION ALL
  SELECT s.biz_date,
         s.account_id,
         NULL AS account_name,
         s.department_id,
         0 AS revenue_fee,
         s.settlement_fee,
         COALESCE(ps.post_settlement_fee, 0) AS post_settlement_fee,
         0 AS tax_fee
  FROM settlement s
  LEFT JOIN income i ON i.biz_date = s.biz_date AND i.account_id = s.account_id AND i.department_id = s.department_id
  LEFT JOIN post_settlement ps ON s.biz_date = ps.biz_date AND s.account_id = ps.account_id AND s.department_id = ps.department_id
  WHERE i.account_id IS NULL
)
SELECT m.biz_date,
       m.account_id,
       COALESCE(a.account_name, m.account_name) AS account_name,
       m.department_id,
       o.department_name,
       m.revenue_fee,
       m.settlement_fee,
       m.post_settlement_fee,
       m.tax_fee,
       m.revenue_fee - m.settlement_fee AS revenue_settlement_diff,
       CASE WHEN m.revenue_fee = 0 THEN NULL ELSE (m.revenue_fee - m.settlement_fee) / m.revenue_fee END AS revenue_settlement_diff_rate,
       CASE
         WHEN a.account_id IS NULL THEN 'DIM_MISSING'
         WHEN m.tax_fee < 0 THEN 'TAX_ABNORMAL'
         WHEN ABS(m.revenue_fee - m.settlement_fee) / NULLIF(ABS(m.revenue_fee), 0) > 0.05 THEN 'SETTLEMENT_MISMATCH'
         ELSE 'NORMAL'
       END AS audit_tag,
       NOW() AS created_at
FROM merged m
LEFT JOIN dwd.dim_account a ON m.account_id = a.account_id
LEFT JOIN dwd.dim_org o ON m.department_id = o.department_id;

-- 校验：业务日收入记录数
SELECT COUNT(*) AS income_count
FROM ods.ods_account_income_monthly
WHERE DATE(data_time) = @biz_date;

