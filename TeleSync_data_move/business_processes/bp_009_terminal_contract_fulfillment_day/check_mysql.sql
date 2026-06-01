/*
业务过程：终端合约履约分析
SQL类型：校验SQL
SQL口径：MySQL
输入表：ods.ods_terminal_sales_daily、ods.ods_terminal_presale_daily、dwd.dim_user、dwd.dim_terminal
输出表：dws.dws_terminal_contract_fulfillment_day
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：2026-06-01
说明：本文件为迁移测试材料，未在数据库中执行。
*/
SET @biz_date = '2025-12-31';
SET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');

-- 校验1：结果表行数校验
SELECT '结果表行数校验' AS check_name,
       'ROW_COUNT' AS check_type,
       CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'FAIL' END AS check_result,
       '> 0' AS expected_value,
       CAST(COUNT(*) AS CHAR) AS actual_value,
       NULL AS diff_value,
       '结果表在当前业务周期应生成数据' AS remark
FROM dws.dws_terminal_contract_fulfillment_day
WHERE biz_date = @biz_date;

-- 校验2：主键唯一性校验
SELECT '主键唯一性校验' AS check_name,
       'PRIMARY_KEY_UNIQUE' AS check_type,
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS check_result,
       '0' AS expected_value,
       CAST(COUNT(*) AS CHAR) AS actual_value,
       CAST(COUNT(*) AS CHAR) AS diff_value,
       '业务主键不允许重复' AS remark
FROM (
  SELECT biz_date, user_id, terminal_id, COUNT(*) AS duplicate_count
  FROM dws.dws_terminal_contract_fulfillment_day
  WHERE biz_date = @biz_date
  GROUP BY biz_date, user_id, terminal_id
  HAVING COUNT(*) > 1
) duplicated_keys;

-- 校验3：核心字段非空校验
SELECT '核心字段非空校验' AS check_name,
       'NOT_NULL' AS check_type,
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS check_result,
       '0' AS expected_value,
       CAST(COUNT(*) AS CHAR) AS actual_value,
       CAST(COUNT(*) AS CHAR) AS diff_value,
       '业务主键和周期字段不允许为空' AS remark
FROM dws.dws_terminal_contract_fulfillment_day
WHERE biz_date = @biz_date
  AND (biz_date IS NULL OR user_id IS NULL OR terminal_id IS NULL);

-- 校验4：指标范围校验
SELECT '指标范围校验' AS check_name,
       'METRIC_RANGE' AS check_type,
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'WARN' END AS check_result,
       '0' AS expected_value,
       CAST(COUNT(*) AS CHAR) AS actual_value,
       CAST(COUNT(*) AS CHAR) AS diff_value,
       '金额、流量、时长、次数等核心指标原则上不应为负' AS remark
FROM dws.dws_terminal_contract_fulfillment_day
WHERE biz_date = @biz_date
  AND (payment_transaction_amount < 0 OR refund_amount < 0 OR monthly_mobile_usage_mb < 0 OR monthly_voice_call_count < 0 OR monthly_sms_count < 0 OR fulfillment_score < 0);

-- 校验5：源表到结果表数量一致性校验
SELECT '源表到结果表数量一致性校验' AS check_name,
       'SOURCE_TARGET_COUNT' AS check_type,
       CASE WHEN ABS(source_count - target_count) = 0 THEN 'PASS' ELSE 'WARN' END AS check_result,
       CAST(source_count AS CHAR) AS expected_value,
       CAST(target_count AS CHAR) AS actual_value,
       CAST(target_count - source_count AS CHAR) AS diff_value,
       '不同业务过程存在过滤和聚合时允许 WARN 后人工复核' AS remark
FROM (
  SELECT (SELECT COUNT(*) FROM ods.ods_terminal_sales_daily WHERE DATE(data_time) = @biz_date) AS source_count,
         (SELECT COUNT(*) FROM dws.dws_terminal_contract_fulfillment_day WHERE biz_date = @biz_date) AS target_count
) counts;

-- 校验6：维表关联丢失校验
SELECT '维表关联丢失校验' AS check_name,
       'DIM_JOIN_LOSS' AS check_type,
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'WARN' END AS check_result,
       '0' AS expected_value,
       CAST(COUNT(*) AS CHAR) AS actual_value,
       CAST(COUNT(*) AS CHAR) AS diff_value,
       '维度字段为空可能代表维表关联丢失，需要人工复核' AS remark
FROM dws.dws_terminal_contract_fulfillment_day
WHERE biz_date = @biz_date
  AND (user_id IS NULL OR terminal_id IS NULL);
