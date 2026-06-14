# 当前 Text2SQL Agent 工作流

本文面向刚进入项目的工程同学、审查者和验收者，说明 TianShu Text2SQL Agent 当前如何工作、哪些环节由 LLM 参与、哪些环节必须由规则程序控制，以及为什么当前阶段仍然禁止 LLM 直接生成最终 SQL。

本文只描述当前工程边界，不代表已经放开所有能力。后续实现真实 LLM Prompt 回归报告系统时，应以本文作为安全审查基线。

## 1. 当前完整工作流

当前 Agent 的目标是把中文问数问题安全地转换为只读 SQL，并返回可解释结果。完整链路如下：

```text
用户中文问题
  ↓
Step 0: 请求安全预检查
  ↓
Step 1: 意图识别，生成 QuestionIntent
  ↓
Step 2: 歧义检测，必要时反问
  ↓
Step 3: SQL 规划，生成 SQLPlan
  ↓
Step 4: SQLPlan 校验
  ↓
Step 5: SQLPlan -> sql_plan_to_sql()
  ↓
Step 6: validate_sql_safety()
  ↓
Step 7: DuckDB read_only 执行
  ↓
Step 8: 结果解释
  ↓
返回 answer / clarification / refusal
```

对应主入口：

- `src/agent.py`
- `src/ir.py`
- `src/sql_gen.py`
- `src/executor.py`
- `src/explainer.py`
- `src/resolver.py`

## 2. 三种最终响应类型

Agent 最终只应该返回三种类型之一。

### answer

表示问题可以安全回答。

典型链路：

```text
QuestionIntent 通过
SQLPlan 通过
SQL 安全校验通过
DuckDB 只读执行
中文解释结果
```

### clarification

表示需要反问用户，不能继续生成 SQL。

常见场景：

- 时间范围模糊，例如“最近”
- 金额口径不清，例如“金额是多少”
- 指标不在注册表中
- 分组维度有歧义

### refusal

表示必须拒绝回答，不能继续生成 SQL。

常见场景：

- 删除、更新、插入、建表等写操作
- 直接查询 Bronze/Silver/原始表
- 越权访问
- 违反 TianShu 契约规则

对应文件：

- `src/agent.py`
- `src/ambiguity.py`
- `evals/ambiguous_questions.yml`
- `evals/unsafe_questions.yml`
- `evals/regression_cases.yml`

## 3. 哪些节点由 LLM 参与

当前阶段，LLM 只能参与低风险或中风险的结构化理解任务，不能直接控制最终 SQL 执行。

### 允许 LLM 参与的节点

| 节点 | LLM 作用 | 输出 |
|---|---|---|
| Intent 识别 | 理解中文问题 | `QuestionIntent` JSON |
| SQLPlan 规划 | 选择表、指标、过滤、聚合、JOIN 路径 | `SQLPlan` JSON |
| 结果解释 | 把 SQLResult 解释成中文 | 中文说明 |

对应文件：

- `prompts/intent_classifier.md`
- `prompts/sql_planner.md`
- `prompts/explainer.md`
- `src/llm.py`
- `src/llm_adapter.py`
- `src/llm_pipeline.py`
- `src/schema_validators.py`

### LLM 输出必须满足的要求

LLM 输出必须是可解析、可校验、可审计的结构化结果。

例如 Intent 阶段输出：

```json
{
  "domain": "traffic",
  "intent_type": "trend",
  "metrics": ["trip_count"],
  "time_range": {
    "type": "absolute",
    "start": "2026-01-01",
    "end": "2026-01-31",
    "raw_expression": "2026年1月"
  },
  "dimensions": ["date"],
  "filters": [],
  "needs_clarification": false,
  "clarification_reason": null,
  "confidence": 0.95,
  "raw_question": "2026年1月每天有多少行程？"
}
```

LLM 如果输出不可解析 JSON、缺字段、字段类型错误、违反 schema，都应失败并进入报告或 regression 候选。

## 4. 哪些节点由规则程序控制

规则程序控制的是安全关键路径。这里不能交给 LLM 自由发挥。

### 规则控制节点

| 节点 | 控制方式 | 目的 |
|---|---|---|
| 写操作识别 | 规则预检查 | 删除、更新、插入等请求直接拒绝 |
| Bronze/Silver 直查识别 | 规则预检查 | 防止绕过 Gold 层业务口径 |
| QuestionIntent 校验 | `QuestionIntent.validate()` | 阻止低置信度、模糊时间等继续规划 |
| SQLPlan 校验 | `SQLPlan.validate()` | 检查表、JOIN、降级原因 |
| SQL 生成 | `sql_plan_to_sql()` | 禁止 LLM 直接产出最终 SQL |
| SQL 安全检查 | `validate_sql_safety()` | 只读、Gold 层、日期维表、JOIN 白名单 |
| SQL 执行 | DuckDB `read_only=True` | 数据库层只读防线 |

对应文件：

- `src/agent.py`
- `src/ir.py`
- `src/sql_gen.py`
- `src/executor.py`
- `src/resolver.py`

## 5. 哪些节点是安全门禁

安全门禁是指失败后必须停止链路的节点。不能为了“回答用户”跳过这些节点。

### 门禁 1：请求预检查

位置：

- `src/agent.py`

职责：

- 识别写操作
- 识别 Bronze/Silver/原始表直查
- 识别明显越权请求

失败后：

- 返回 `refusal`
- 不进入 Intent / SQLPlan / SQL 生成

### 门禁 2：QuestionIntent 校验

位置：

- `src/ir.py`

职责：

- 检查是否需要反问
- 检查 confidence 是否过低
- 检查时间范围是否模糊
- 检查领域和指标是否可识别

失败后：

- 返回 `clarification`
- 不继续生成 SQLPlan

### 门禁 3：SQLPlan 校验

位置：

- `src/ir.py`

职责：

- 检查 `primary_table`
- 检查表是否存在于可用表集合
- 检查 JOIN 是否在白名单
- 检查非最优策略是否写明 `downgrade_reason`

失败后：

- 返回拒绝或失败
- 不生成 SQL

### 门禁 4：SQL 安全校验

位置：

- `src/sql_gen.py`

职责：

- SQL 必须是 `SELECT` 或合规 `WITH`
- 表名必须完全限定
- 业务查询只能引用 `gold.*`
- 日期过滤必须通过 `gold.dim_date`
- JOIN 必须在白名单中
- 禁止 `INSERT`、`UPDATE`、`DELETE`、`DROP` 等关键字

失败后：

- 不执行 SQL

### 门禁 5：DuckDB 只读执行

位置：

- `src/resolver.py`
- `src/executor.py`

职责：

- 使用 DuckDB `read_only=True`
- 即使前面校验遗漏，也不允许修改数据库

失败后：

- 记录执行错误
- 不伪造结果

## 6. 当前阶段为什么不允许 LLM 直接写 SQL

LLM 直接写 SQL 的风险不在于“SQL 写得好不好”，而在于它可能绕过项目治理边界。

### 风险 1：绕过指标注册表

LLM 可能临时编造指标，例如把某个金额字段当成收入。

本项目要求：

- 只能使用已注册指标
- 金额口径不清必须反问
- `standard_fine_amount` 不能被解释成实际收入

### 风险 2：绕过 Gold 层优先规则

LLM 可能直接查 Bronze/Silver 或明细事实表。

本项目要求：

- 业务问数优先 Gold G3
- 必要时按规则降级到 G2
- 不能直接查 Bronze/Silver 回答业务问题

### 风险 3：绕过 JOIN 白名单

LLM 可能生成看似合理但语义错误的 JOIN。

本项目要求：

- JOIN 只能来自白名单
- 不允许自由拼接表关系

### 风险 4：绕过日期维表规则

LLM 可能直接比较事实表里的日期字段或 date_key。

本项目要求：

- 日期过滤必须通过 `gold.dim_date`

### 风险 5：绕过只读安全

LLM 可能输出包含写操作、DDL、PRAGMA 或其他危险 SQL。

本项目要求：

- 可执行 SQL 必须经过 `validate_sql_safety()`
- 数据库连接必须只读

因此，当前阶段允许 LLM 规划，但不允许 LLM 直接生成最终可执行 SQL。最终 SQL 必须由规则程序从 SQLPlan 生成。

## 7. 当前 LLM 允许的边界

当前允许：

- LLM 识别 `QuestionIntent`
- LLM 规划 `SQLPlan`
- LLM 解释结果
- LLM 输出 clarification/refusal 的结构化判断

当前禁止：

- LLM 直接输出最终 SQL 并执行
- LLM 绕过 `SQLPlan`
- LLM 绕过 `sql_plan_to_sql()`
- LLM 绕过 `validate_sql_safety()`
- LLM 自由访问 Bronze/Silver/原始表
- LLM 编造未注册指标
- LLM 静默忽略失败样例

## 8. Prompt 回归报告系统要解决什么问题

Prompt 回归报告系统不是为了立刻提高答案准确率，而是为真实 LLM 接入建立工程证据。

它要解决五类问题。

### 8.1 可观测性

要看见每次真实模型调用发生了什么：

- 问题是什么
- 调用哪个 prompt
- 使用哪个模型
- raw output 是什么
- 是否解析成功
- 解析后结构是什么
- validation 是否通过
- confidence 是否漂移
- 失败原因是什么

对应输出：

- `harness/reports/llm_raw_outputs/`
- `harness/reports/prompt_regression_latest.md`
- `harness/reports/prompt_regression_latest.json`

### 8.2 可回归性

同一个问题必须能反复跑。

如果某次 prompt 修改后，原来必须拒绝的问题变成了正常 answer，这就是回归。

对应输入：

- `tests/fixtures/prompts/intent_classifier_cases.yml`
- `tests/fixtures/prompts/sql_planner_cases.yml`
- `evals/regression_cases.yml`

### 8.3 可审计性

失败后必须能追溯证据。

不能只说“模型错了”，而要能打开 raw output，看见模型到底输出了什么，为什么被判失败。

### 8.4 Prompt 稳定性观察

观察同一 prompt 在真实模型下是否稳定输出：

- 类型是否稳定：answer / clarification / refusal
- confidence 是否异常波动
- Intent 是否漂移
- SQLPlan 是否漂移
- 是否出现 LLM 直接 SQL

### 8.5 失败样例沉淀

真实失败不能只看一眼就算了。失败样例应进入 regression 候选，后续由人确认后固化到 regression cases。

对应文件：

- `evals/regression_cases.yml`
- `harness/reports/prompt_regression_latest.md`

## 9. Prompt 回归报告应包含什么

后续实现真实 LLM Prompt 回归报告系统时，报告至少应包含：

### Markdown 报告

路径建议：

- `harness/reports/prompt_regression_latest.md`

面向人阅读，应包含：

- Summary
- Failed Cases
- Drift Observation
- Safety Check
- Next Regression Cases

### JSON 报告

路径建议：

- `harness/reports/prompt_regression_latest.json`

面向程序和 CI，应包含：

- `run_id`
- `timestamp`
- `model_name`
- `summary`
- `cases[]`
- `failures[]`
- `raw_output_refs[]`

### Raw Output

路径建议：

- `harness/reports/llm_raw_outputs/`

每次模型调用至少记录：

- `question_id`
- `question`
- `stage`
- `prompt_name`
- `model_name`
- `raw_output`
- `parsed_output`
- `parse_success`
- `validation_success`
- `error_message`
- `timestamp`

不得记录：

- API Key
- 敏感环境变量
- 无关长日志

## 10. 后续实现 Prompt 回归报告系统前必须保留的边界

实现前必须确认以下边界没有被破坏。

### 边界 1：SQL 仍由规则生成

可执行 SQL 必须来自：

```text
SQLPlan -> sql_plan_to_sql()
```

不能来自：

```text
中文问题 -> LLM 直接 SQL -> 执行
```

### 边界 2：SQL 仍必须安全校验

任何可执行 SQL 都必须经过：

```text
validate_sql_safety()
```

报告系统也应记录是否执行过该校验。

### 边界 3：LLM 输出失败不能静默忽略

以下情况必须进入失败报告：

- raw output 不可解析
- schema 校验失败
- confidence 缺失
- confidence 超出范围
- expected_type 与 actual_type 不一致
- 表不匹配
- 字段不匹配
- 出现 direct SQL
- 安全校验失败

### 边界 4：refusal 必须是明确拒绝

对于写操作、Bronze/Silver 直查等高风险问题，模型不能只输出普通 clarification。

建议结构：

```json
{
  "refusal": true,
  "refusal_reason": "当前 Agent 只允许只读问数，不能执行删除或修改数据的操作。"
}
```

### 边界 5：报告不得泄露密钥

报告和 raw output 不得包含：

- `OPENAI_API_KEY`
- DeepSeek API Key
- `config/secrets.yml` 内容
- 任何真实 token

### 边界 6：规则版 MVP 不能被破坏

Prompt 回归是 LLM 质量观察系统，不应影响规则版 MVP。

验收命令仍包括：

```powershell
python -m pytest -q
python harness/run_harness.py
python -m compileall -q src harness tests
```

## 11. 后续工程审查清单

实现真实 LLM Prompt 回归报告系统时，审查者应逐项确认：

- 是否没有让 LLM 直接生成最终 SQL 并执行
- 是否没有绕过 `SQLPlan`
- 是否没有绕过 `sql_plan_to_sql()`
- 是否没有绕过 `validate_sql_safety()`
- 是否保留 DuckDB 只读连接
- 是否保存 raw output
- 是否生成 Markdown 报告
- 是否生成 JSON 报告
- 是否记录失败原因分类
- 是否将失败样例列为 regression candidates
- 是否不保存 API Key
- 是否不删除规则版测试
- 是否能用 mock LLM 离线测试
- 是否能用真实 provider 运行但不依赖真实 provider 才能通过单元测试

## 12. 当前阶段验收口径

当前阶段的验收目标不是“模型回答所有问题都准确”，而是：

1. 链路边界清楚。
2. LLM 参与节点清楚。
3. 规则控制节点清楚。
4. 安全门禁不可绕过。
5. 失败可记录。
6. 输出可比较。
7. 失败样例可沉淀。
8. 后续工程审查有明确依据。

只要这些边界没有建立好，就不应进入“让 LLM 直接 SQL candidate”阶段。

