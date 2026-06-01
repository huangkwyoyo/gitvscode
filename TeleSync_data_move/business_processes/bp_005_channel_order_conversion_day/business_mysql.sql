/*
业务过程：渠道订单转化日分析
SQL类型：业务SQL
SQL口径：MySQL
输入表：dwd.fact_order_daily、dwd.dim_channel、dwd.dim_product
输出表：dws.dws_channel_order_conversion_day
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/
SET @biz_date = '2025-12-31';
SET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');

INSERT INTO dws.dws_channel_order_conversion_day
WITH
-- 按业务口径拆分中间结果，便于后续迁移转换和静态检查
agg AS (
  SELECT DATE(o.order_created_time) AS biz_date,
         o.channel_id,
         c.channel_type,
         p.product_type,
         COUNT(*) AS order_count,
         SUM(CASE WHEN o.order_status = 'paid' THEN 1 ELSE 0 END) AS paid_order_count,
         SUM(CASE WHEN o.order_status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_order_count,
         SUM(CASE WHEN o.order_status = 'created' THEN 1 ELSE 0 END) AS created_order_count,
         SUM(CASE WHEN o.order_status = 'paid' THEN o.order_amount ELSE 0 END) AS payment_amount,
         AVG(CASE WHEN o.order_status = 'paid' AND o.payment_time IS NOT NULL THEN TIMESTAMPDIFF(MINUTE, o.order_created_time, o.payment_time) END) AS avg_pay_minutes
  FROM dwd.fact_order_daily o
  LEFT JOIN dwd.dim_channel c ON o.channel_id = c.channel_id
  LEFT JOIN dwd.dim_product p ON o.product_id = p.product_id
  WHERE DATE(o.order_created_time) = @biz_date
  GROUP BY DATE(o.order_created_time), o.channel_id, c.channel_type, p.product_type
),
scored AS (
  SELECT a.*,
         paid_order_count / NULLIF(order_count, 0) AS conversion_rate,
         cancelled_order_count / NULLIF(order_count, 0) AS cancel_rate,
         AVG(paid_order_count / NULLIF(order_count, 0)) OVER (PARTITION BY channel_type) AS channel_type_avg_conversion_rate
  FROM agg a
)
SELECT biz_date,
       channel_id,
       channel_type,
       product_type,
       order_count,
       paid_order_count,
       cancelled_order_count,
       created_order_count,
       payment_amount,
       conversion_rate,
       cancel_rate,
       avg_pay_minutes,
       channel_type_avg_conversion_rate,
       CASE
         WHEN cancel_rate >= 0.25 AND order_count >= 20 THEN 'HIGH_CANCEL'
         WHEN conversion_rate < channel_type_avg_conversion_rate * 0.7 THEN 'LOW_CONVERSION'
         WHEN avg_pay_minutes > 120 THEN 'SLOW_PAYMENT'
         ELSE 'NORMAL'
       END AS channel_risk_tag,
       NOW() AS created_at
FROM scored;
