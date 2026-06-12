# Prompt 回归说明

## 为什么要做 Prompt 回归

Prompt 回归用于观察真实模型输出是否稳定。Text2SQL 链路里，模型输出一旦发生漂移，可能导致错误指标、错误表、错误日期范围，甚至越过只读边界。回归系统把每次真实模型输出保存下来，并和 fixture 的期望结构比较，方便定位是意图识别漂移、SQLPlan 漂移，还是反问/拒绝类型漂移。

## 为什么先观察真实模型输出

当前阶段不直接放开 LLM 写 SQL。原因是最终 SQL 会被执行，风险高于 Intent 和 SQLPlan。现在的安全边界是：

1. LLM 只负责 Intent 识别、SQLPlan 规划和结果解释。
2. SQL 必须由 `SQLPlan -> sql_plan_to_sql()` 规则生成。
3. 生成 SQL 后必须经过 `validate_sql_safety()`。
4. 执行仍使用 DuckDB 只读连接。

这样可以先观察模型是否能稳定产出结构化 IR，再逐步扩大能力。

## 三类 fixture

`answer` 表示问题可以正常回答。模型应输出完整的 `QuestionIntent` 或 `SQLPlan`，并通过结构、confidence、表字段和安全校验。

`clarification` 表示必须反问用户。常见原因包括时间范围模糊、金额口径不清、分组维度有歧义、指标不在注册表中。

`refusal` 表示必须拒绝。常见原因包括写操作、越权查询、直接查询 Bronze/Silver/原始表、无关或无法支持的问题。

## confidence 为什么使用容忍比较

真实模型的 confidence 不是确定性字段，不应要求完全相等。回归使用 `confidence_min` / `confidence_max` 区间判断：

- 缺失 confidence 时明确记录为失败。
- 低于下限或高于上限时判定为失败。
- 报告中同时显示 expected 与 actual，便于观察置信度漂移。

## 为什么保存 raw output

raw output 是定位 Prompt 漂移的证据。报告只保存必要字段：

- question_id
- question
- stage
- prompt_name
- model_name
- raw_output
- parsed_output
- parse_success
- validation_success
- error_message
- timestamp

报告不会保存 API Key，也不会保存环境变量。

## Markdown 和 JSON 报告

Markdown 报告面向人阅读，路径为 `harness/reports/prompt_regression_latest.md`。它用于快速查看摘要、失败样例、漂移观察、安全检查和下一批 regression 候选。

JSON 报告面向机器处理，路径为 `harness/reports/prompt_regression_latest.json`。它用于后续 CI、趋势分析、失败归档和自动生成 regression cases。

## 失败样例如何进入 regression cases

失败样例会在报告中标注：

- 是否建议加入 regression cases
- 推荐 case 类型
- 推荐 fixture 内容
- 失败原因分类

失败原因包括：

- `intent_mismatch`
- `plan_mismatch`
- `table_mismatch`
- `field_mismatch`
- `clarification_expected_but_answered`
- `refusal_expected_but_answered`
- `confidence_out_of_range`
- `schema_validation_failed`
- `safety_validation_failed`
- `raw_output_parse_failed`
- `llm_direct_sql_detected`

## 什么时候考虑 LLM SQL candidate

只有在以下条件满足后，才考虑让 LLM 产出 SQL candidate：

1. Intent 和 SQLPlan 的真实模型回归长期稳定。
2. clarification/refusal 覆盖足够多的高风险样例。
3. SQLPlan 安全门禁稳定发现未授权表、字段和 JOIN。
4. LLM SQL candidate 只作为候选，不直接执行。
5. candidate 必须经过解析、白名单、只读、JOIN、日期过滤和 `validate_sql_safety()` 全部门禁。

在当前 Phase 2A-Next 中，LLM 直接 SQL 仍然禁止。
