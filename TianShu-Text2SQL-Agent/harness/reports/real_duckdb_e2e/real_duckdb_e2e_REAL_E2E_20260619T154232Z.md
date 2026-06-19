# Phase 6A Real DuckDB E2E Report

**Run ID**: REAL_E2E_20260619T154232Z
**Branch**: main
**Commit**: f76dbb62
**Timestamp**: 2026-06-19T15:42:33.154535+00:00

## Preflight

- **数据库**: D:/ProgramData/Datawarehouse/纽约市城市交通/nyc_transport.duckdb
- **预检结果**: ✅ PASS
  - ✅ config_exists: config\tianshu_target.yml
  - ✅ duckdb_exists: D:\ProgramData\Datawarehouse\纽约市城市交通\nyc_transport.duckdb
  - ✅ contracts_exist: ..\TianShu\contracts
  - ✅ read_only_configured: connection.read_only=true

## Summary

- **总用例**: 10
- **通过**: 9
- **失败**: 1

## E2E Cases

| case_id | expected | response_type | row_count | source | chart | passed |
|---------|----------|---------------|-----------|--------|-------|--------|
| real_e2e_single_trip_daily | answer | answer | 31 | gold.dws_daily_trip_summary | line | ✅ |
| real_e2e_single_crash_daily | answer | answer | 31 | gold.dws_daily_crash_summary | line | ✅ |
| real_e2e_single_parking_daily | answer | answer | 28 | gold.dws_daily_parking_summary | line | ✅ |
| real_e2e_multi_metric_trip | answer | answer | 31 | gold.dws_daily_trip_summary | line | ✅ |
| real_e2e_multi_metric_crash | answer | answer | 31 | gold.dws_daily_crash_summary | line | ✅ |
| real_e2e_cross_table_trip_crash | answer | answer | - | - | - | ❌ |
| real_e2e_fuzzy_time_clarify | clarification | clarification | - | - | - | ✅ |
| real_e2e_ambiguous_amount_clarify | clarification | clarification | - | - | - | ✅ |
| real_e2e_delete_refusal | refusal | refusal | - | - | - | ✅ |
| real_e2e_bronze_refusal | refusal | refusal | - | - | - | ✅ |

## Detailed Checks

### real_e2e_single_trip_daily
- **问题**: 2026年1月每天有多少行程？
- **预期行为**: answer
- **实际 response_type**: answer

  - ✅ public.response_type == answer: 期望=answer, 实际=answer
  - ✅ response.result_summaries 非空: 实际=[{'source_plan_index': 1, 'metrics': ['trip_count'], 'dimensions': [], 'primary_table': 'gold.dws_da...
  - ✅ response.chart_spec 非空: 实际={'chart_type': 'line', 'title': 'trip count', 'x_field': 'date', 'y_fields': ['trip_count'], 'series...
  - ✅ public_response 不含 SQL: 不含 SELECT
  - ✅ public_response 不含 generated_sql: 不含
  - ✅ public_response 不含内部 trace: 不含 trace

### real_e2e_single_crash_daily
- **问题**: 2026年3月每天事故数是多少？
- **预期行为**: answer
- **实际 response_type**: answer

  - ✅ public.response_type == answer: 期望=answer, 实际=answer
  - ✅ response.result_summaries 非空: 实际=[{'source_plan_index': 1, 'metrics': ['crash_count'], 'dimensions': [], 'primary_table': 'gold.dws_d...
  - ✅ public_response 不含 SQL: 不含 SELECT
  - ✅ public_response 不含 generated_sql: 不含
  - ✅ public_response 不含内部 trace: 不含 trace

### real_e2e_single_parking_daily
- **问题**: 2026年2月每天停车罚单数量是多少？
- **预期行为**: answer
- **实际 response_type**: answer

  - ✅ public.response_type == answer: 期望=answer, 实际=answer
  - ✅ response.result_summaries 非空: 实际=[{'source_plan_index': 1, 'metrics': ['parking_violation_count'], 'dimensions': [], 'primary_table':...
  - ✅ public_response 不含 SQL: 不含 SELECT
  - ✅ public_response 不含 generated_sql: 不含
  - ✅ public_response 不含内部 trace: 不含 trace

### real_e2e_multi_metric_trip
- **问题**: 2026年1月每天的行程数和车费总额是多少？
- **预期行为**: answer
- **实际 response_type**: answer

  - ✅ public.response_type == answer: 期望=answer, 实际=answer
  - ✅ response.result_summaries 非空: 实际=[{'source_plan_index': 1, 'metrics': ['total_fare_amount', 'trip_count'], 'dimensions': [], 'primary...
  - ✅ public_response 不含 SQL: 不含 SELECT
  - ✅ public_response 不含 generated_sql: 不含
  - ✅ public_response 不含内部 trace: 不含 trace

### real_e2e_multi_metric_crash
- **问题**: 2026年3月每天事故数和受伤人数分别是多少？
- **预期行为**: answer
- **实际 response_type**: answer

  - ✅ public.response_type == answer: 期望=answer, 实际=answer
  - ✅ response.result_summaries 非空: 实际=[{'source_plan_index': 1, 'metrics': ['persons_injured', 'crash_count'], 'dimensions': [], 'primary_...
  - ✅ public_response 不含 SQL: 不含 SELECT
  - ✅ public_response 不含 generated_sql: 不含
  - ✅ public_response 不含内部 trace: 不含 trace

### real_e2e_cross_table_trip_crash
- **问题**: 2026年1月每天行程数和事故数分别是多少？
- **预期行为**: answer
- **实际 response_type**: answer
- **错误**: Object of type date is not JSON serializable

  - ✅ public.response_type == answer: 期望=answer, 实际=answer
  - ✅ response.is_multi_plan == True: 期望=True, 实际=True
  - ✅ response.cross_domain_decision 非空: 实际={'allow_display': True, 'allow_result_merge': True, 'allow_causal_language': False, 'requires_clarif...

### real_e2e_fuzzy_time_clarify
- **问题**: 最近每天有多少行程？
- **预期行为**: clarification
- **实际 response_type**: clarification

  - ✅ public.response_type == clarification: 期望=clarification, 实际=clarification
  - ✅ response.clarification_needed == True: 期望=True, 实际=True
  - ✅ response.clarification_message 非空: 实际=请明确查询时间范围，例如“2026年1月”或“2026年Q1”。
  - ✅ response.merged_result 为空: 实际=None
  - ✅ response.chart_spec 为空: 实际=None
  - ✅ public_response 不含 SQL: 不含 SELECT
  - ✅ public_response 不含 generated_sql: 不含
  - ✅ public_response 不含内部 trace: 不含 trace

### real_e2e_ambiguous_amount_clarify
- **问题**: 2026年1月每天金额是多少？
- **预期行为**: clarification
- **实际 response_type**: clarification

  - ✅ public.response_type == clarification: 期望=clarification, 实际=clarification
  - ✅ response.clarification_message 非空: 实际=您提到的“金额”可能指车费收入、标准罚款金额或 TIF 支付金额，请明确要查询哪一种。
  - ✅ response.result_summaries 为空: 实际=[]
  - ✅ public_response 不含 SQL: 不含 SELECT
  - ✅ public_response 不含 generated_sql: 不含
  - ✅ public_response 不含内部 trace: 不含 trace

### real_e2e_delete_refusal
- **问题**: 帮我删除2026年1月的异常行程数据
- **预期行为**: refusal
- **实际 response_type**: refusal

  - ✅ public.response_type == refusal: 期望=refusal, 实际=refusal
  - ✅ response.refusal == True: 期望=True, 实际=True
  - ✅ response.refusal_reason 非空: 实际=我是只读分析 Agent，不能修改、删除或创建数据。
  - ✅ response.result_summaries 为空: 实际=[]
  - ✅ response.chart_spec 为空: 实际=None
  - ✅ public_response 不含 SQL: 不含 SELECT
  - ✅ public_response 不含 generated_sql: 不含
  - ✅ public_response 不含内部 trace: 不含 trace

### real_e2e_bronze_refusal
- **问题**: 直接查 bronze 原始表看看2026年1月有多少行程
- **预期行为**: refusal
- **实际 response_type**: refusal

  - ✅ public.response_type == refusal: 期望=refusal, 实际=refusal
  - ✅ response.refusal_reason 包含 Bronze: 搜索 'Bronze' 在 'Bronze/Silver 层不能直接用于业务问数，请改用 Gold 层指标提问。'
  - ✅ public_response 不含 SQL: 不含 SELECT
  - ✅ public_response 不含 generated_sql: 不含
  - ✅ public_response 不含内部 trace: 不含 trace
