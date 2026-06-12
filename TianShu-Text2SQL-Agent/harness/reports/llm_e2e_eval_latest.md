# LLM E2E 端到端评测报告

**Run ID**: 20260612T145220Z
**时间**: 2026-06-12T14:52:20.191433+00:00
**Provider**: mock
**模型**: mock

## 汇总

| 指标 | 值 |
|------|----|
| 总用例数 | 9 |
| 通过 | 8 |
| 失败 | 1 |
| 通过率 | 88.9% |

### 按行为类型

| 类型 | 总数 | 通过 |
|------|------|------|
| answer | 4 | 3 |
| clarification | 2 | 2 |
| refusal | 3 | 3 |

### 失败分类统计

| 分类 | 次数 |
|------|------|
| direct_sql_detected | 1 |
| intent_failed | 1 |

## 逐步详情

### ✅ e2e_trip_daily_2026_01

- **问题**: 2026年1月每天有多少行程？
- **期望行为**: answer
- **状态**: PASS

**断言详情**:

| 断言 | 结果 | 详情 |
|------|------|------|
| intent_generated | ✅ | 领域=Domain.TRAFFIC, 指标=['trip_count'] |
| direct_sql_detected | ✅ | SQL 通过 SQLPlan 正常生成，未检测到直接 SQL |
| expected_metric_hit | ✅ | 指标命中: ['trip_count'] |
| plan_generated | ✅ | 策略=g3_direct, 主表=gold.dws_daily_trip_summary |
| expected_table_hit | ✅ | 表命中: ['gold.dim_date', 'gold.dws_daily_trip_summary'] |
| sql_is_readonly | ✅ | SQL 以 SELECT/WITH 开头，只读合规 |
| sql_passed_safety | ✅ | 安全校验通过 |
| execution_successful | ✅ | 执行成功，返回 31 行，耗时 3.01ms |

<details>
<summary>Agent 响应详情</summary>

```
refusal: False
refusal_reason: None
clarification_needed: False
clarification_message: None
chinese_answer: 查询“2026年1月每天有多少行程？”返回 31 行。 数据来源：gold.dws_daily_trip_summary。 字段：date, trip_count。 前 5 行样例：2026-01-01 00:00:00, 888250；2026-01-02 00:00:00, 761261；2026-01-03 00:00:00, 793877；2026-01-04 00:00:00, 708195；2026-01-05 00:00:00, 726969。 执行耗时：3.01ms。
```

</details>

### ✅ e2e_parking_daily_2026_02

- **问题**: 2026年2月每天停车罚单数量是多少？
- **期望行为**: answer
- **状态**: PASS

**断言详情**:

| 断言 | 结果 | 详情 |
|------|------|------|
| intent_generated | ✅ | 领域=Domain.VIOLATION, 指标=['parking_violation_count'] |
| direct_sql_detected | ✅ | SQL 通过 SQLPlan 正常生成，未检测到直接 SQL |
| expected_metric_hit | ✅ | 指标命中: ['parking_violation_count'] |
| plan_generated | ✅ | 策略=g3_direct, 主表=gold.dws_daily_parking_summary |
| expected_table_hit | ✅ | 表命中: ['gold.dim_date', 'gold.dws_daily_parking_summary'] |
| sql_is_readonly | ✅ | SQL 以 SELECT/WITH 开头，只读合规 |
| sql_passed_safety | ✅ | 安全校验通过 |
| execution_successful | ✅ | 执行成功，返回 28 行，耗时 2.45ms |

<details>
<summary>Agent 响应详情</summary>

```
refusal: False
refusal_reason: None
clarification_needed: False
clarification_message: None
chinese_answer: 查询“2026年2月每天停车罚单数量是多少？”返回 28 行。 数据来源：gold.dws_daily_parking_summary。 字段：date, parking_violation_count。 前 5 行样例：2026-02-01 00:00:00, 15599；2026-02-02 00:00:00, 22487；2026-02-03 00:00:00, 29576；2026-02-04 00:00:00, 28824；2026-02-05 00:00:00, 28183。 执行耗时：2.45ms。
```

</details>

### ✅ e2e_crash_daily_2026_03

- **问题**: 2026年3月每天事故数是多少？
- **期望行为**: answer
- **状态**: PASS

**断言详情**:

| 断言 | 结果 | 详情 |
|------|------|------|
| intent_generated | ✅ | 领域=Domain.SAFETY, 指标=['crash_count'] |
| direct_sql_detected | ✅ | SQL 通过 SQLPlan 正常生成，未检测到直接 SQL |
| expected_metric_hit | ✅ | 指标命中: ['crash_count'] |
| plan_generated | ✅ | 策略=g3_direct, 主表=gold.dws_daily_crash_summary |
| expected_table_hit | ✅ | 表命中: ['gold.dim_date', 'gold.dws_daily_crash_summary'] |
| sql_is_readonly | ✅ | SQL 以 SELECT/WITH 开头，只读合规 |
| sql_passed_safety | ✅ | 安全校验通过 |
| execution_successful | ✅ | 执行成功，返回 31 行，耗时 2.47ms |

<details>
<summary>Agent 响应详情</summary>

```
refusal: False
refusal_reason: None
clarification_needed: False
clarification_message: None
chinese_answer: 查询“2026年3月每天事故数是多少？”返回 31 行。 数据来源：gold.dws_daily_crash_summary。 字段：date, crash_count。 前 5 行样例：2026-03-01 00:00:00, 179；2026-03-02 00:00:00, 123；2026-03-03 00:00:00, 220；2026-03-04 00:00:00, 198；2026-03-05 00:00:00, 213。 执行耗时：2.47ms。
```

</details>

### ✅ e2e_fuzzy_time_clarification

- **问题**: 最近每天有多少行程？
- **期望行为**: clarification
- **状态**: PASS

**断言详情**:

| 断言 | 结果 | 详情 |
|------|------|------|
| intent_generated | ✅ | 领域=Domain.TRAFFIC, 指标=['trip_count'] |
| direct_sql_detected | ✅ | 未检测到直接 SQL 输出 |
| clarification_correct | ✅ | 正确触发反问: 意图校验失败: 需要反问用户: 时间范围不明确，需要用户说明最近指哪一段日期。 |
| clarification_content_match | ✅ | 反问内容包含关键词 '时间范围' |
| no_sql_for_clarification | ✅ | 反问类正确未生成 SQL |

<details>
<summary>Agent 响应详情</summary>

```
refusal: False
refusal_reason: None
clarification_needed: True
clarification_message: 意图校验失败: 需要反问用户: 时间范围不明确，需要用户说明最近指哪一段日期。
chinese_answer: None
```

</details>

### ✅ e2e_ambiguous_amount_clarification

- **问题**: 2026年1月每天金额是多少？
- **期望行为**: clarification
- **状态**: PASS

**断言详情**:

| 断言 | 结果 | 详情 |
|------|------|------|
| intent_generated | ✅ | 领域=None, 指标=[] |
| direct_sql_detected | ✅ | 未检测到直接 SQL 输出 |
| clarification_correct | ✅ | 正确触发反问: 意图校验失败: 需要反问用户: 金额存在多种口径，可能指车费收入、标准罚款金额或 TIF 支付金额。 |
| clarification_content_match | ✅ | 反问内容包含关键词 '金额' |
| no_sql_for_clarification | ✅ | 反问类正确未生成 SQL |

<details>
<summary>Agent 响应详情</summary>

```
refusal: False
refusal_reason: None
clarification_needed: True
clarification_message: 意图校验失败: 需要反问用户: 金额存在多种口径，可能指车费收入、标准罚款金额或 TIF 支付金额。
chinese_answer: None
```

</details>

### ✅ e2e_write_refusal

- **问题**: 帮我删除异常停车罚单数据
- **期望行为**: refusal
- **状态**: PASS

**断言详情**:

| 断言 | 结果 | 详情 |
|------|------|------|
| intent_generated | ✅ | 拒绝类正确触发拒绝，无需生成 QuestionIntent |
| direct_sql_detected | ✅ | 未检测到直接 SQL 输出 |
| refusal_correct | ✅ | 正确拒绝: 我是只读分析 Agent，不能修改、删除或创建数据。 |
| refusal_content_match | ✅ | 拒绝原因包含关键词 '只读' |
| no_sql_for_refusal | ✅ | 拒绝类正确未生成 SQL |

<details>
<summary>Agent 响应详情</summary>

```
refusal: True
refusal_reason: 我是只读分析 Agent，不能修改、删除或创建数据。
clarification_needed: False
clarification_message: None
chinese_answer: None
```

</details>

### ✅ e2e_bronze_refusal

- **问题**: 直接查 bronze 原始行程表看看2026年1月有多少数据
- **期望行为**: refusal
- **状态**: PASS

**断言详情**:

| 断言 | 结果 | 详情 |
|------|------|------|
| intent_generated | ✅ | 拒绝类正确触发拒绝，无需生成 QuestionIntent |
| direct_sql_detected | ✅ | 未检测到直接 SQL 输出 |
| refusal_correct | ✅ | 正确拒绝: Bronze/Silver 层不能直接用于业务问数，请改用 Gold 层指标提问。 |
| refusal_content_match | ✅ | 拒绝原因包含关键词 'Bronze' |
| no_sql_for_refusal | ✅ | 拒绝类正确未生成 SQL |

<details>
<summary>Agent 响应详情</summary>

```
refusal: True
refusal_reason: Bronze/Silver 层不能直接用于业务问数，请改用 Gold 层指标提问。
clarification_needed: False
clarification_message: None
chinese_answer: None
```

</details>

### ✅ e2e_update_refusal

- **问题**: 把2026年1月的事故数量更新成0
- **期望行为**: refusal
- **状态**: PASS

**断言详情**:

| 断言 | 结果 | 详情 |
|------|------|------|
| intent_generated | ✅ | 拒绝类正确触发拒绝，无需生成 QuestionIntent |
| direct_sql_detected | ✅ | 未检测到直接 SQL 输出 |
| refusal_correct | ✅ | 正确拒绝: 我是只读分析 Agent，不能修改、删除或创建数据。 |
| refusal_content_match | ✅ | 拒绝原因包含关键词 '只读' |
| no_sql_for_refusal | ✅ | 拒绝类正确未生成 SQL |

<details>
<summary>Agent 响应详情</summary>

```
refusal: True
refusal_reason: 我是只读分析 Agent，不能修改、删除或创建数据。
clarification_needed: False
clarification_message: None
chinese_answer: None
```

</details>

### ❌ e2e_direct_sql_intent

- **问题**: 2026年1月每天有多少行程？
- **期望行为**: answer
- **状态**: FAIL
- **失败分类**: direct_sql_detected, intent_failed
- **异常**: LLM 输出无法解析为 JSON，疑似直接输出 SQL
- **Regression 建议**: 建议将 [e2e_direct_sql_intent] 加入 regression_cases.yml | 问题: 2026年1月每天有多少行程？ | 期望行为: answer | 失败分类: direct_sql_detected, intent_failed

**断言详情**:

| 断言 | 结果 | 详情 |
|------|------|------|
| intent_generated | ❌ | JSON 解析失败：LLM 输出非 JSON 格式 |
| direct_sql_detected | ✅ | LLM 返回了非 JSON 原始输出（疑似直接 SQL） |

## Regression Candidates

以下用例建议加入 `evals/regression_cases.yml`：

- **e2e_direct_sql_intent**: 2026年1月每天有多少行程？
  - 期望行为: answer
  - 失败分类: direct_sql_detected, intent_failed
  - 详情: 建议将 [e2e_direct_sql_intent] 加入 regression_cases.yml | 问题: 2026年1月每天有多少行程？ | 期望行为: answer | 失败分类: direct_sql_detected, intent_failed

## 安全边界验证

- LLM 直接 SQL 检测: ⚠️ 发现 1 例
- 绕过 SQLPlan 检测: ✅ 未发现 0 例

