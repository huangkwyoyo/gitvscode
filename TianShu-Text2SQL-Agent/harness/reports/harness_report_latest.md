# TianShu Text2SQL Agent Harness 报告

生成时间：2026-06-12 22:57:47

## 汇总

| 状态 | 数量 |
|------|------|
| PASS | 5 |
| FAIL | 0 |
| **总计** | **5** |

## 逐步详情

### ✅ SQL 只读安全门禁
- 状态: PASS
- 耗时: 0.08s
- 退出码: 0

```
============================================================
SQL 只读安全门禁
禁止关键字 (21): ALTER, ATTACH, CHECKPOINT, COPY, CREATE, DELETE, DETACH, DROP, EXPORT, GRANT, IMPORT, INSERT, INSTALL, LOAD, MERGE, PRAGMA, RENAME, REPLACE, REVOKE, TRUNCATE, UPDATE
============================================================
  [PASS] 全部 3 条 SQL 通过只读检查

[OK] 全部 3 条 SQL 通过只读安全检查。

```

### ✅ IR 数据结构完整性
- 状态: PASS
- 耗时: 0.08s
- 退出码: 0

```
============================================================
IR 三层数据结构完整性门禁
============================================================

── src/ir.py 数据类检查 ──
  [PASS] QuestionIntent 实例化 + 序列化
         字段数=9, 包含 keys=['domain', 'intent_type', 'metrics', 'time_range', 'dimensions']...
  [PASS] QuestionIntent.validate()
         通过
  [PASS] QuestionIntent 歧义检测（needs_clarification=true）
         检测到 1 个问题
  [PASS] SQLPlan 实例化 + 序列化
         策略=g3_direct, 主表=gold.dws_daily_trip_summary
  [PASS] SQLPlan 降级原因检查（缺失 downgrade_reason）
         检测到 1 个问题
  [PASS] SQLResult 签名计算
         MD5=84ff789f34d8a324...
  [PASS] AgentResponse 完整链路序列化
         包含 keys=['question', 'intent', 'plan', 'result', 'chinese_answer', 'clarification_needed', 'clarification_message', 'refusal', 'refusal_reason', 'trace']

── evals/ 文件结构检查 ──
  [WARN] ambiguous_questions.yml / ambiguous_fuzzy_time_trip
         缺少字段: ['sql']
  [WARN] ambiguous_questions.yml / ambiguous_amount
         缺少字段: ['sql']
  [WARN] ambiguous_questions.yml / ambiguous_unregistered_metric
         缺少字段: ['sql']
  [WARN] e2e_cases.yml 结构
         问题列表为空
  [WARN] regression_cases.yml / regression_trip_daily_2026_01
         缺少字段: ['sql']
  [WARN] regression_cases.yml / regression_parking_daily_2026_02
         缺少字段: ['sql']
  [WARN] regression_cases.yml / regression_crash_daily_2026_03
         缺少字段: ['sql']
  [WARN] regression_cases.yml / regression_refusal_write_delete
         缺少字段: ['sql']
  [WARN] regression_cases.yml / regression_refusal_bronze_direct
         缺少字段: ['sql']
  [WARN] regression_cases.yml / regression_refusal_update_data
         缺少字段: ['sql']
  [PASS] standard_questions.yml / standard_trip_daily_2026_01
         '2026年1月每天有多少行程？...'
  [PASS] standard_questions.yml / standard_parking_daily_2026_02
         '2026年2月每天停车罚单数量是多少？...'
  [PASS] standard_questions.yml / standard_crash_daily_2026_03
         '2026年3月每天事故数是多少？...'
  [WARN] unsafe_questions.yml / unsafe_delete_data
         缺少字段: ['sql']
  [WARN] unsafe_questions.yml / unsafe_update_metric
         缺少字段: ['sql']
  [WARN] unsafe_questions.yml / unsafe_bronze_direct
         缺少字段: ['sql']

  检查完成 — 通过: 10, 失败: 0

[OK] IR 数据结构完整性检查通过。

```

### ✅ 反问/拒绝策略完备性
- 状态: PASS
- 耗时: 0.06s
- 退出码: 0

```
============================================================
反问/拒绝策略完备性门禁
============================================================

── contracts/question_policy.yml 检查 ──
  [PASS] 可回答的问题域定义
         已定义 6 个问题域: ['traffic', 'violation', 'safety', 'supply', 'asset', 'spatial']
  [PASS] 必须反问的场景数
         已定义 5 种反问场景: {'unregistered_metric', 'missing_dimension', 'ambiguous_amount', 'fuzzy_time', 'ambiguous_region'}
  [PASS] 反问模板完备性
         全部反问规则都有模板
  [PASS] 必须拒绝的场景数
         已定义 4 种拒绝场景: {'metric_invention', 'write_operation', 'bronze_direct', 'out_of_scope'}
  [PASS] 拒绝模板完备性
         全部拒绝规则都有模板

── evals/ 策略评测文件检查 ──
  [PASS] ambiguous_questions.yml
         3 道歧义问题
  [PASS] unsafe_questions.yml
         3 道越权问题

  检查完成 — 通过: 7, 失败: 0, 跳过: 0

[OK] 反问/拒绝策略完备性检查通过。

```

### ✅ 层级合规门禁
- 状态: PASS
- 耗时: 0.07s
- 退出码: 0

```
============================================================
层级合规门禁
规则: G3 > G2 > Silver > Bronze
============================================================

── 逐题检查 (3 题) ──
  [PASS] standard_questions.yml / standard_trip_daily_2026_01
         使用 G3 表: {'gold.dws_daily_trip_summary'}
  [PASS] standard_questions.yml / standard_parking_daily_2026_02
         使用 G3 表: {'gold.dws_daily_parking_summary'}
  [PASS] standard_questions.yml / standard_crash_daily_2026_03
         使用 G3 表: {'gold.dws_daily_crash_summary'}

  检查完成 — 通过: 3, 警告: 0, 失败: 0

[OK] 层级合规检查通过（0 项警告，不阻断）。

```

### ✅ 指标注册合规门禁
- 状态: PASS
- 耗时: 0.07s
- 退出码: 0

```
============================================================
指标注册合规门禁
已注册指标数: 10
============================================================

── 逐题检查 (15 题) ──
  [PASS] ambiguous_questions.yml / ambiguous_fuzzy_time_trip
         纯维度/列表查询（metric_names 为空），无需指标检查
  [PASS] ambiguous_questions.yml / ambiguous_amount
         纯维度/列表查询（metric_names 为空），无需指标检查
  [PASS] ambiguous_questions.yml / ambiguous_unregistered_metric
         纯维度/列表查询（metric_names 为空），无需指标检查
  [PASS] regression_cases.yml / regression_trip_daily_2026_01
         纯维度/列表查询（metric_names 为空），无需指标检查
  [PASS] regression_cases.yml / regression_parking_daily_2026_02
         纯维度/列表查询（metric_names 为空），无需指标检查
  [PASS] regression_cases.yml / regression_crash_daily_2026_03
         纯维度/列表查询（metric_names 为空），无需指标检查
  [PASS] regression_cases.yml / regression_refusal_write_delete
         纯维度/列表查询（metric_names 为空），无需指标检查
  [PASS] regression_cases.yml / regression_refusal_bronze_direct
         纯维度/列表查询（metric_names 为空），无需指标检查
  [PASS] regression_cases.yml / regression_refusal_update_data
         纯维度/列表查询（metric_names 为空），无需指标检查
  [PASS] standard_questions.yml / standard_trip_daily_2026_01
         指标全部已注册: ['trip_count']
  [PASS] standard_questions.yml / standard_parking_daily_2026_02
         指标全部已注册: ['parking_violation_count']
  [PASS] standard_questions.yml / standard_crash_daily_2026_03
         指标全部已注册: ['crash_count']
  [PASS] unsafe_questions.yml / unsafe_delete_data
         纯维度/列表查询（metric_names 为空），无需指标检查
  [PASS] unsafe_questions.yml / unsafe_update_metric
         纯维度/列表查询（metric_names 为空），无需指标检查
  [PASS] unsafe_questions.yml / unsafe_bronze_direct
         纯维度/列表查询（metric_names 为空），无需指标检查

  检查完成 — 通过: 15, 失败: 0, 跳过: 0

[OK] 指标注册合规检查通过。

```
