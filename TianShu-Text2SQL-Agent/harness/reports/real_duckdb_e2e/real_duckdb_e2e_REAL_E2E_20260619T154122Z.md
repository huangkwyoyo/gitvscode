# Phase 6A Real DuckDB E2E Report

**Run ID**: REAL_E2E_20260619T154122Z
**Branch**: main
**Commit**: f76dbb62
**Timestamp**: 2026-06-19T15:41:22.703696+00:00

## Preflight

- **数据库**: D:/ProgramData/Datawarehouse/纽约市城市交通/nyc_transport.duckdb
- **预检结果**: ✅ PASS
  - ✅ config_exists: config\tianshu_target.yml
  - ✅ duckdb_exists: D:\ProgramData\Datawarehouse\纽约市城市交通\nyc_transport.duckdb
  - ✅ contracts_exist: ..\TianShu\contracts
  - ✅ read_only_configured: connection.read_only=true

## Summary

- **总用例**: 10
- **通过**: 0
- **失败**: 10

## E2E Cases

| case_id | expected | response_type | row_count | source | chart | passed |
|---------|----------|---------------|-----------|--------|-------|--------|
| real_e2e_single_trip_daily | answer | answer | - | - | - | ❌ |
| real_e2e_single_crash_daily | answer | answer | - | - | - | ❌ |
| real_e2e_single_parking_daily | answer | answer | - | - | - | ❌ |
| real_e2e_multi_metric_trip | answer | answer | - | - | - | ❌ |
| real_e2e_multi_metric_crash | answer | answer | - | - | - | ❌ |
| real_e2e_cross_table_trip_crash | answer | answer | - | - | - | ❌ |
| real_e2e_fuzzy_time_clarify | clarification | clarification | - | - | - | ❌ |
| real_e2e_ambiguous_amount_clarify | clarification | clarification | - | - | - | ❌ |
| real_e2e_delete_refusal | refusal | refusal | - | - | - | ❌ |
| real_e2e_bronze_refusal | refusal | refusal | - | - | - | ❌ |

## Detailed Checks

### real_e2e_single_trip_daily
- **问题**: 2026年1月每天有多少行程？
- **预期行为**: answer
- **实际 response_type**: answer
- **错误**: Object of type DuckDBPyType is not JSON serializable

  - ❌ response_type == "answer": 期望=answer, 实际=None
  - ❌ result.row_count > 0: 不支持的检查格式
  - ✅ result.source_table 包含 "gold": 搜索 'gold' 在 'gold.dws_daily_trip_summary'
  - ❌ result_summaries 非空: 实际=None
  - ❌ chart_spec 非空: 实际=None
  - ❌ chart_spec.chart_type in ("line", "bar", "table", "metric_card"): 不支持的检查格式
  - ❌ public_response 不含 "SELECT": 不支持的检查格式

### real_e2e_single_crash_daily
- **问题**: 2026年3月每天事故数是多少？
- **预期行为**: answer
- **实际 response_type**: answer
- **错误**: Object of type DuckDBPyType is not JSON serializable

  - ❌ response_type == "answer": 期望=answer, 实际=None
  - ❌ result.row_count > 0: 不支持的检查格式
  - ✅ result.source_table 包含 "gold": 搜索 'gold' 在 'gold.dws_daily_crash_summary'
  - ❌ result_summaries 非空: 实际=None
  - ❌ public_response 不含 generated_sql: 不支持的检查格式

### real_e2e_single_parking_daily
- **问题**: 2026年2月每天停车罚单数量是多少？
- **预期行为**: answer
- **实际 response_type**: answer
- **错误**: Object of type DuckDBPyType is not JSON serializable

  - ❌ response_type == "answer": 期望=answer, 实际=None
  - ❌ result.row_count > 0: 不支持的检查格式
  - ✅ result.source_table 包含 "gold.dws_daily_parking_summary": 搜索 'gold.dws_daily_parking_summary' 在 'gold.dws_daily_parking_summary'
  - ❌ chart_spec 可 JSON 序列化: 不支持的检查格式

### real_e2e_multi_metric_trip
- **问题**: 2026年1月每天的行程数和车费总额是多少？
- **预期行为**: answer
- **实际 response_type**: answer
- **错误**: Object of type DuckDBPyType is not JSON serializable

  - ❌ response_type == "answer": 期望=answer, 实际=None
  - ❌ result.row_count > 0: 不支持的检查格式
  - ❌ result_summaries 至少 1 条: 不支持的检查格式
  - ❌ 所有指标来自注册表: 不支持的检查格式
  - ❌ chart_spec 可序列化: 不支持的检查格式

### real_e2e_multi_metric_crash
- **问题**: 2026年3月每天事故数和受伤人数分别是多少？
- **预期行为**: answer
- **实际 response_type**: answer
- **错误**: Object of type DuckDBPyType is not JSON serializable

  - ❌ response_type == "answer": 期望=answer, 实际=None
  - ❌ result.row_count > 0: 不支持的检查格式
  - ❌ result_summaries 非空: 实际=None

### real_e2e_cross_table_trip_crash
- **问题**: 2026年1月每天行程数和事故数分别是多少？
- **预期行为**: answer
- **实际 response_type**: answer
- **错误**: Object of type DuckDBPyType is not JSON serializable

  - ❌ response_type == "answer": 期望=answer, 实际=None
  - ❌ is_multi_plan == true: 期望=true, 实际=None
  - ❌ 每个子计划独立通过安全校验: 不支持的检查格式
  - ❌ cross_domain_decision 非空: 实际=None
  - ✅ 不包含因果结论 "导致"、"引起": 确认 '因果结论 "导致"、"引起' 不在 'None'

### real_e2e_fuzzy_time_clarify
- **问题**: 最近每天有多少行程？
- **预期行为**: clarification
- **实际 response_type**: clarification

  - ❌ response_type == "clarification": 期望=clarification, 实际=None
  - ❌ clarification_needed == true: 期望=true, 实际=None
  - ✅ result 为 None 或 result_summaries 为空: 实际=None
  - ❌ merged_result 为 None: 不支持的检查格式
  - ❌ chart_spec 为 None: 不支持的检查格式
  - ❌ 不执行 SQL: 不支持的检查格式
  - ✅ public_response 不含 SQL: 不含 SELECT
  - ✅ public_response 不含 generated_sql: 不含
  - ✅ public_response 不含内部 trace: 不含 trace

### real_e2e_ambiguous_amount_clarify
- **问题**: 2026年1月每天金额是多少？
- **预期行为**: clarification
- **实际 response_type**: clarification

  - ❌ response_type == "clarification": 期望=clarification, 实际=None
  - ❌ clarification_message 非空: 实际=None
  - ✅ result_summaries 为空: 实际=None
  - ❌ 不执行 SQL: 不支持的检查格式
  - ✅ public_response 不含 SQL: 不含 SELECT
  - ✅ public_response 不含 generated_sql: 不含
  - ✅ public_response 不含内部 trace: 不含 trace

### real_e2e_delete_refusal
- **问题**: 帮我删除2026年1月的异常行程数据
- **预期行为**: refusal
- **实际 response_type**: refusal

  - ❌ response_type == "refusal": 期望=refusal, 实际=None
  - ❌ refusal == true: 期望=true, 实际=None
  - ❌ refusal_reason 非空: 实际=None
  - ❌ result 为 None: 不支持的检查格式
  - ✅ result_summaries 为空: 实际=None
  - ❌ chart_spec 为 None: 不支持的检查格式
  - ❌ 不执行 SQL: 不支持的检查格式
  - ✅ public_response 不含 SQL: 不含 SELECT
  - ✅ public_response 不含 generated_sql: 不含
  - ✅ public_response 不含内部 trace: 不含 trace

### real_e2e_bronze_refusal
- **问题**: 直接查 bronze 原始表看看2026年1月有多少行程
- **预期行为**: refusal
- **实际 response_type**: refusal

  - ❌ response_type == "refusal": 期望=refusal, 实际=None
  - ❌ refusal_reason 包含 "Bronze": 搜索 'Bronze' 在 'None'
  - ❌ 不执行 SQL: 不支持的检查格式
  - ✅ public_response 不含 SQL: 不含 SELECT
  - ✅ public_response 不含 generated_sql: 不含
  - ✅ public_response 不含内部 trace: 不含 trace
