-- 05 渠道订单转化日分析
SET @biz_date = '2025-12-31';

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

INSERT INTO dws.dws_channel_order_conversion_day
WITH agg AS (
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

-- 校验：业务日订单数
SELECT COUNT(*) AS order_count
FROM dwd.fact_order_daily
WHERE DATE(order_created_time) = @biz_date;

