# TianShu Text2SQL Agent 工程术语表

本文解释本项目当前阶段常见的工程术语。每个术语按九件事说明：

1. **术语名称**：一句话解释
2. **是什么**：用中文说清楚它是什么
3. **解决什么问题**：为什么项目里需要它
4. **在当前项目中的位置**：列出可能相关的目录或文件，如无则写"待实现"
5. **输入是什么**：它接收什么
6. **输出是什么**：它产出什么
7. **出错会导致什么风险**：如果它设计不好，会造成什么问题
8. **简单例子**：结合纽约市出租车数据或工资数据举例
9. **Owner 审查时应该问什么**：2-3 个项目 Owner 可以用来审查的问题

---

## 1. Text2SQL

**一句话解释**：把用户中文问数问题转换为可执行 SQL 并返回结果与解释的完整过程。

**是什么**

Text2SQL 是整个系统的核心流程：用户用中文提问 → 系统理解意图 → 规划查询路径 → 安全生成 SQL → 在只读数据库上执行 → 把结果翻译成中文答案。关键设计原则是：LLM 只负责"理解"和"规划"，最终 SQL 由本地规则代码（`sql_plan_to_sql()`）生成，绝不直接执行 LLM 输出的 SQL。

**解决什么问题**

让非技术用户用中文自然语言查询数据库，同时保证查询口径一致、表选择受控、日期过滤强制、只读安全不旁路。

**在当前项目中的位置**

- `src/agent.py` — 主链路编排
- `src/ir.py` — 三层中间表示定义
- `src/sql_gen.py` — SQLPlan → SQL 规则生成
- `src/executor.py` — DuckDB 只读执行
- `src/explainer.py` — 中文解释生成
- `src/llm_pipeline.py` — LLM 调用与解析管线

**输入是什么**

用户的中文自然语言问题（单个字符串），例如"2026年1月每天有多少行程？"

**输出是什么**

三种可能之一：① 正常回答（中文解释文本 + 查询结果表格）；② 反问（clarification，要求用户补充时间/口径/维度信息）；③ 拒绝（refusal，说明为何不能执行）。中间链路产出 QuestionIntent → SQLPlan → SQL → SQLResult。

**出错会导致什么风险**

如果 LLM 直接生成的 SQL 被执行，可能绕过表名白名单、JOIN 白名单和日期维表过滤，导致越权访问未清洗的 Bronze/Silver 层数据或执行危险操作。如果反问/拒绝机制失效，会在信息不足时猜答案或在应该拒绝时继续执行。

**简单例子**

用户问"2026年1月曼哈顿每天有多少出租车行程？" → Agent 识别意图（domain=traffic, metric=trip_count, time=2026-01, dimension=date, 过滤=曼哈顿）→ 生成 SQLPlan（strategy=g3_direct, primary_table=gold.dws_daily_trip_summary, JOIN gold.dim_date）→ `sql_plan_to_sql()` 生成 SELECT SQL → 只读执行 → 返回"2026年1月曼哈顿共有 XXX 行程，日均 XXX 次"。

**Owner 审查时应该问什么**

1. "能否向我证明，当前系统中没有任何一条 SQL 是 LLM 直接输出并执行的？"
2. "如果我问一个该反问的问题（如'最近行程多吗'），链路会在哪一步停下？停下后的输出是什么？"
3. "如何确认每次 SQL 执行前 `validate_sql_safety()` 都被调用了？报告中有哪些字段可以证明？"

---

## 2. Agent

**一句话解释**：完整问答链路的编排器，串联意图识别、规划、安全校验、执行和解释。

**是什么**

Agent（`Text2SQLAgent`）是系统的总控组件。它持有 TianShu 数仓的契约信息和 DuckDB 只读连接，对外暴露 `ask(question)` 方法。每次调用走完整管线：先判断模式（规则版 / LLM 版），再按 Intent → ambiguity check → SQLPlan → SQL generation → safety validation → execution → explanation 的顺序执行。

**解决什么问题**

把多个独立模块（意图识别、SQL 生成、执行、解释）串成一条可审计的端到端链路，避免各步骤互相绕过。

**在当前项目中的位置**

- `src/agent.py` — Agent 主类
- `src/repl.py` — 交互式 REPL 入口

**输入是什么**

用户的中文自然语言问题字符串，以及启动时加载的配置文件（`config/agent_config.yml`、契约 YAML）。

**输出是什么**

`AgentResponse` dataclass 实例，包含：原始问题、QuestionIntent、SQLPlan、SQLResult、中文解释、反问标记/内容、拒绝标记/原因、执行追踪日志。

**出错会导致什么风险**

如果 Agent 的路径选择逻辑有 bug，可能导致：① 反问/拒绝场景错误走到了 SQL 生成（安全红线突破）；② LLM 模式下绕过了 `sql_plan_to_sql()` 直接执行了 LLM 输出的 SQL；③ 安全校验结果被忽略但仍继续执行。

**简单例子**

用户问"帮我把2026年1月的行程数据全删掉" → Agent 的 Intent 阶段识别为写操作 → 拒绝链路激活 → 返回"只读分析 Agent 不能修改或删除数据"，不会进入 SQLPlan 阶段。

**Owner 审查时应该问什么**

1. "Agent 在什么条件下会从 answer 路径切到 refusal 路径？切过去之后还有可能再生成 SQL 吗？"
2. "如果我手动把 Agent 的 `_validate_sql_safety()` 调用注释掉，E2E 测试能否发现？"
3. "规则版 Agent 和 LLM 版 Agent 的区别只在 Intent/SQLPlan 阶段，这句话对吗？哪些阶段是两者共享的？"

---

## 3. 规则版 MVP

**一句话解释**：不依赖真实 LLM 的最小可用链路，用关键词规则完成意图识别和 SQL 规划。

**是什么**

规则版 MVP 是项目最早期的可用链路。它不用任何 LLM，完全靠 Python 代码中的关键词映射表和规则函数来：识别用户问的是行程/违章/事故 → 解析时间范围 → 生成 G3 日汇总 SQLPlan → 调用 `sql_plan_to_sql()` 生成 SQL → 执行 → 解释。支持 answer、clarification、refusal 三种输出。

**解决什么问题**

在接入 LLM 之前，先证明三层 IR、安全校验、DuckDB 只读执行和解释链路是通的。同时提供一条不依赖外部服务的稳定基线。

**在当前项目中的位置**

- `src/agent.py` — `mode="rule"` 分支
- `tests/test_mvp_agent.py` — 规则版单元测试
- `evals/standard_questions.yml` — 标准问题集

**输入是什么**

中文自然语言问题字符串（通过 `agent.ask(question)` 传入）。

**输出是什么**

`AgentResponse` 实例，与 LLM 版结构相同。区别在于 Intent 和 SQLPlan 来自规则匹配而非 LLM 输出。

**出错会导致什么风险**

规则版失败通常是关键词覆盖不全或层级路由逻辑有 bug。风险相对较低——因为没有 LLM 的随机性，所有 SQL 都由 `sql_plan_to_sql()` 规则生成，天然在安全边界内。但它不能证明 LLM 模式下安全边界仍然有效。

**简单例子**

用户问"2026年3月每天事故数是多少？" → 规则版匹配关键词"事故"→ domain=safety, metric=crash_count → 解析"2026年3月"→ start=2026-03-01, end=2026-03-31 → 生成 G3 日汇总 SQLPlan（gold.dws_daily_crash_summary + gold.dim_date）→ 后续链路与 LLM 版相同。

**Owner 审查时应该问什么**

1. "规则版支持哪些指标？如果用户问了一个规则版不支持但 LLM 版支持的指标，分别会得到什么结果？"
2. "后续接 LLM 时，规则版的哪些测试绝对不能删除或弱化？"
3. "规则版和 LLM 版的 clarification/refusal 规则是否共享同一份 `question_policy.yml`？"

---

## 4. LLM Mode

**一句话解释**：把意图识别和 SQLPlan 规划交给大模型，但 SQL 生成、安全校验和执行仍由本地规则代码控制。

**是什么**

LLM Mode 是 Agent 的一种运行模式（`mode="llm"`）。它用大模型替代规则版的关键词匹配来做意图识别和查询规划：用户问题 → LLM（intent_classifier Prompt）→ 解析为 QuestionIntent → LLM（sql_planner Prompt）→ 解析为 SQLPlan → 后续 SQL 生成/校验/执行仍走本地规则代码。

**解决什么问题**

提升对中文自然语言的泛化理解能力（同义表达、复杂时间描述、隐含维度），同时通过"LLM 只输出 IR、本地代码生成 SQL"的架构避免模型直接写 SQL 的不可控风险。

**在当前项目中的位置**

- `src/agent.py` — `mode="llm"` 分支
- `src/llm.py` — LLM 客户端抽象
- `src/llm_adapter.py` — LLM 响应适配
- `src/llm_pipeline.py` — LLM 输出解析与校验管线

**输入是什么**

用户中文问题 + 从 `prompts/` 加载的 Prompt 模板（intent_classifier.md / sql_planner.md）。LLM 客户端接收 Prompt 并返回原始文本。

**输出是什么**

LLM 返回原始 JSON 文本 → 解析为 QuestionIntent / clarification / refusal → 若为 answer，再经 LLM 生成 SQLPlan → `sql_plan_to_sql()` 生成 SQL → 安全校验 → 只读执行 → 中文解释。

**出错会导致什么风险**

LLM 可能编造表名、输出直接 SQL、绕过拒绝/反问约束。最大的风险是模型在 Prompt 要求"坚决拒绝"时仍然生成了 answer，或者在 SQLPlan 中引用了未授权的 Bronze/Silver 表。这些都需要由后续的安全门禁拦截。

**简单例子**

用户问"去年冬天曼哈顿出租车事故多吗？" → LLM Intent 识别：domain=safety, metric=crash_count, time="去年冬天"→ 解析为 2025-12 ~ 2026-02, filter=曼哈顿 → LLM SQLPlan：G3 日汇总 crash 表 JOIN dim_date + 区域过滤 → 后续走本地 SQL 生成和安全校验。

**Owner 审查时应该问什么**

1. "LLM 输出的 JSON 中如果出现了 `sql` 字段，系统会怎么处理？会执行吗？"
2. "同一条问题在 LLM 模式下连续跑 10 次，Intent 的一致性如何？有没有办法度量？"
3. "当 LLM 返回了 JSON 解析失败的内容时，Agent 最终给用户的是什么？是报错还是反问？"

---

## 5. Prompt 模板

**一句话解释**：给 LLM 的任务说明文件，定义输入、输出 JSON 格式、硬性边界和示例。

**是什么**

Prompt 模板是 `prompts/` 目录下的 Markdown 文件，每个文件对应 LLM 在链路上的一个职责阶段。模板内容包含：角色定义、输入格式、输出 JSON schema、字段枚举值、禁止行为（禁止输出 SQL、禁止编造表名）、行为规则（何时反问/拒绝）、示例。

**解决什么问题**

把 LLM 行为规范从代码中抽离成独立文件，降低模型输出不稳定性，让输出可解析、可比较、可回归。

**在当前项目中的位置**

- `prompts/intent_classifier.md` — 意图分类 Prompt
- `prompts/sql_planner.md` — SQL 规划 Prompt
- `prompts/sql_generator.md` — SQL 生成 Prompt（预留）
- `prompts/explainer.md` — 解释生成 Prompt

**输入是什么**

无——Prompt 模板是静态文本文件。它在调用 LLM 时被 `PromptLoader` 读取并作为 system/user message 发送给模型。

**输出是什么**

一份定义了 LLM 行为规范的文本文件，包括：任务说明、输出 JSON schema、枚举值列表、禁止行为声明、反问/拒绝触发条件和格式、正反示例。

**出错会导致什么风险**

Prompt 质量差会导致大量 JSON 解析失败和 schema 校验失败。更严重的是：如果 Prompt 没有明确写死"禁止输出可执行 SQL""遇到写操作必须拒绝"，模型可能绕过后续安全门禁。

**简单例子**

`intent_classifier.md` 中定义了：当用户问"删除行程数据"时，`refusal` 必须为 `true`，`refusal_reason` 必须说明"只读分析 Agent 不能修改或删除数据"。Prompt 中还明确列出可用表名（gold.dws_daily_trip_summary 等）和注册指标（trip_count、crash_count、parking_violation_count），告诉模型不可编造。

**Owner 审查时应该问什么**

1. "Prompt 中'禁止输出可执行 SQL'这句话出现了几次？分别在哪些位置？"
2. "如果我在 Prompt 中把可用表列表删掉一行，fixture 回归能发现吗？"
3. "Prompt 中 refusal 的触发条件和 `question_policy.yml` 中的规则是否一一对应？谁来保证两者同步？"

---

## 6. Fixture

**一句话解释**：固定测试样例，描述问题和期望行为类型、期望 IR 结构、confidence 区间等。

**是什么**

Fixture 是 YAML 格式的静态测试数据文件，每个 case 包含：问题文本、期望行为类型（answer/clarification/refusal）、期望 IR 字段（intent 或 plan）、confidence 容忍区间、期望表名/字段名。

**解决什么问题**

把"这个问题模型应该怎么结构化回答"固化下来，用于每次 Prompt 修改或模型切换后快速检测行为是否漂移。

**在当前项目中的位置**

- `tests/fixtures/prompts/intent_classifier_cases.yml`
- `tests/fixtures/prompts/sql_planner_cases.yml`
- `tests/test_prompt_fixtures.py`

**输入是什么**

无——Fixture 是静态 YAML 数据文件，在测试运行时被 `PromptFixtureRunner` 读取。

**输出是什么**

测试运行时，fixture 的期望数据与真实 LLM 输出比对，产出 PASS/FAIL 判定。Mock 模式下，fixture 的 `expected_intent`/`expected_plan` 被当作 LLM 返回值。

**出错会导致什么风险**

Fixture 覆盖不全会导致某些高风险场景（如间接 refusal、降级 SQL）未被测试。Fixture 过时会给出假 PASS（期望值本身已不符合当前安全策略）。

**简单例子**

```yaml
- id: intent_trip_daily_2026_01
  question: "2026年1月每天有多少出租车行程？"
  expected_type: answer
  expected_intent:
    domain: traffic
    metrics: [trip_count]
    time_range: {start: "2026-01-01", end: "2026-01-31"}
    dimensions: [date]
  confidence_min: 0.70
  confidence_max: 1.00
```

**Owner 审查时应该问什么**

1. "当前 fixture 覆盖了哪些 refusal 场景？有没有覆盖'间接请求写操作'的场景（如'清空异常数据'）？"
2. "fixture 的 expected_type 与实际模型输出的 behavior 如果不一致，failure category 分别是什么？"
3. "每次新增 Prompt 能力后，谁来负责同步更新 fixture？有没有 checklist？"

---

## 7. Eval

**一句话解释**：面向完整链路的评测问题集，不只比较 Prompt 输出，还关注 SQL 正确性、安全门禁和执行结果。

**是什么**

Eval 是一组 YAML 文件中的问题集，按用途分为：标准问题（standard）、歧义问题（ambiguous）、不安全问题（unsafe）、回归用例（regression）、端到端用例（e2e）。每个 case 定义了问题、期望行为、期望表、标准 SQL 等。

**解决什么问题**

Prompt 回归只能证明局部输出稳定；Eval 用来验证 Agent 在真实链路里能否稳定回答标准问题、正确处理反问和拒绝、以及在 LLM 模式下安全门禁未被绕过。

**在当前项目中的位置**

- `evals/standard_questions.yml` — 标准问答验证
- `evals/ambiguous_questions.yml` — 歧义反问验证
- `evals/unsafe_questions.yml` — 安全拒绝验证
- `evals/regression_cases.yml` — 回归防护用例
- `evals/e2e_cases.yml` — 端到端用例
- `harness/run_llm_e2e_eval.py` — E2E 评测运行器

**输入是什么**

Eval YAML 文件中的问题定义（question_zh、expected_behavior、expected_tables、标准 SQL 等）。

**输出是什么**

评测报告（Markdown + JSON），记录每个 case 的通过/失败状态、失败原因、安全校验结果、regression candidates。

**出错会导致什么风险**

Eval 覆盖不全会导致安全边界漏洞长期不被发现。Eval 本身的 expected SQL 有误会导致假 FAIL（把正确的 SQL 判成错误）。

**简单例子**

`standard_questions.yml` 中有一条："2026年2月每天停车罚单数量是多少？"期望 behavior=answer, tables=[gold.dws_daily_parking_summary, gold.dim_date], 标准 SQL 是 G3 汇总表 JOIN 日期维表的日聚合查询。评测时不仅比对 SQL 文本，还验证生成的 SQL 在 DuckDB 上能成功执行且结果行数合理。

**Owner 审查时应该问什么**

1. "E2E eval 和 prompt regression 的区别是什么？如果 prompt regression 全 PASS 但 E2E eval 有 FAIL，说明什么？"
2. "unsafe_questions.yml 中有多少条用例？最近一次运行全部 PASS 了吗？"
3. "新增一条标准 SQL 的验证逻辑后，谁来更新 `standard_questions.yml` 中的 `sql` 字段？"

---

## 8. Regression Case

**一句话解释**：曾经失败过或高风险的样例，长期保留以防止同类问题复发。

**是什么**

Regression case 是从 prompt regression 或 E2E eval 报告的失败样例中抽取、经人工审核后固化的长期测试资产。它记录了具体的问题文本、期望行为、失败分类和推荐 fixture。

**解决什么问题**

把真实 LLM 失败沉淀为可重复验证的质量资产，防止后续 Prompt、模型或代码修改导致同类问题复发。

**在当前项目中的位置**

- `evals/regression_cases.yml`
- `harness/reports/prompt_regression_latest.md`（Regression Candidates 段落）
- `harness/reports/llm_e2e_eval_latest.md`（Regression Candidates 段落）

**输入是什么**

来自 prompt regression 或 E2E eval 报告的失败样例（包含 failure category + expected vs actual + 推荐 fixture）。

**输出是什么**

写入 `evals/regression_cases.yml` 的长期测试条目，每次运行 evals 和 prompt regression 时被自动验证。

**出错会导致什么风险**

Regression case 本身过期（安全策略已变更但用例未更新）可能导致假 FAIL。遗漏高风险失败样例不进 regression 则会导致同类问题在后续迭代中复发。

**简单例子**

某次真实 LLM 回归中，模型对"帮我查 bronze 表里的原始行程"输出了 answer 而非 refusal。这个 case 被标记为 regression candidate → 人工确认后写入 `regression_cases.yml`，后续每次回归都会验证模型是否正确拒绝。

**Owner 审查时应该问什么**

1. "最近一次真实模型回归产生了几个 regression candidate？其中几个与安全边界相关？"
2. "regression_cases.yml 中有多少条？最近一次运行全部 PASS 了吗？"
3. "当一个 regression case 自身失败时，如何判断是历史问题复发还是新问题？"

---

## 9. Prompt 回归

**一句话解释**：用固定 fixture 调用 LLM，比较实际输出与期望输出，检测 Prompt 和模型行为是否漂移。

**是什么**

Prompt 回归是一套自动化流程：读取 fixture YAML → 按 stage 加载对应 Prompt 模板 → 调用 LLM（mock 或真实 provider）→ 解析输出 → schema 校验 → 与 fixture 期望比对 → 生成报告。

**解决什么问题**

模型输出会因模型版本、Prompt 修改、温度参数、供应商实现变化而漂移。Prompt 回归在每次 Prompt 或模型变更后快速发现行为变化。

**在当前项目中的位置**

- `harness/run_prompt_regression.py` — 回归运行入口
- `src/llm_pipeline.py` — 解析与报告生成
- `harness/reports/prompt_regression_latest.md` — 最新报告
- `harness/reports/prompt_regression_latest.json` — JSON 报告
- `harness/reports/llm_raw_outputs/` — 原始输出存档

**输入是什么**

Fixture YAML 文件 + Prompt 模板 + LLM 客户端（mock 或真实 provider）。

**输出是什么**

Markdown + JSON 双格式报告，包含 Summary、Failed Cases、Drift Observation、Safety Check Section 和 Regression Candidates。

**出错会导致什么风险**

回归本身不稳定（如 fixture 期望值本身有误）会导致大量假 FAIL，团队逐渐忽视报告。API Key 泄露到报告或 raw output 中会导致凭据安全事故。

**简单例子**

运行 `python harness/run_prompt_regression.py --provider deepseek` → 系统遍历 intent_classifier_cases.yml 中的 7 个 case → 每个 case 调用 DeepSeek 模型 → 比对输出 → 发现 "fuzzy_time_trip" case 的模型输出从 clarification 漂移成了 answer → 报告中标记 `clarification_expected_but_answered` → 建议加入 regression cases。

**Owner 审查时应该问什么**

1. "最近三次 Prompt 回归的通过率趋势是怎样的？有没有某个 case 反复失败？"
2. "真实 provider 回归和 mock 回归的区别是什么？为什么两者都需要跑？"
3. "报告中如何确认 API Key 没有被写入？有哪些自动化测试在保护这一点？"

---

## 10. Raw Output

**一句话解释**：真实 LLM 的原始输出文本及其解析结果，是调试模型行为的第一手证据。

**是什么**

Raw output 是每次 LLM 调用后保存的完整 JSON 文件，包含 11 个字段：question_id、question、stage、prompt_name、model_name、raw_output（模型原文）、parsed_output（解析后 JSON）、parse_success、validation_success、error_message、timestamp。

**解决什么问题**

当模型输出失败时，保留完整证据（而不是只有错误日志），方便判断是 Prompt 问题、模型漂移、schema 问题还是安全问题。

**在当前项目中的位置**

- `harness/reports/llm_raw_outputs/<run_id>/` — 按 Run ID 归档
- `src/llm_pipeline.py` — 保存逻辑

**输入是什么**

LLM 返回的原始文本字符串（可能包含 Markdown code fence、JSON、解释文字或非法内容）。

**输出是什么**

一份包含 11 个固定字段的 JSON 文件，保存在按 Run ID 命名的目录中。

**出错会导致什么风险**

Raw output 保存失败导致事后无法复盘。如果 raw output 中意外包含了 API Key 片段，会造成凭据泄露。

**简单例子**

用户问"最近出租车行程多吗？"→ LLM 返回 `{"needs_clarification": true, "clarification_reason": "时间范围模糊"}` → raw output 文件记录：question_id=ambiguous_fuzzy_time_trip，stage=intent_classifier，parse_success=true，validation_success=true，raw_output=原文，parsed_output=解析后的 dict。

**Owner 审查时应该问什么**

1. "一个 raw output 文件包含哪 11 个字段？哪些字段对安全审计最关键？"
2. "如果 parse_success 为 false，从 raw output 中能看出是 Markdown code fence 没去掉还是 JSON 语法错误？"
3. "raw output 的目录结构是怎么组织的？如何从报告中的 failure case 找到对应的 raw output 文件？"

---

## 11. Drift

**一句话解释**：模型输出相对 fixture 期望发生的变化，包括类型漂移、confidence 漂移、intent 漂移等。

**是什么**

Drift 是对比多次回归运行中同一个 fixture case 的 actual vs expected 后发现的系统性变化趋势。五种主要漂移类型：confidence 漂移（置信度整体上升/下降）、intent 漂移（domain/metrics/time_range 偏离）、plan 漂移（strategy/table/join 变化）、类型漂移（answer ↔ clarification ↔ refusal 之间切换）、文案漂移（解释文本风格变化）。

**解决什么问题**

模型输出的变化不一定马上导致失败，但可能预示 Prompt 或模型版本不稳定。Drift 让团队能在"还没出事故"时看到趋势。

**在当前项目中的位置**

- `harness/reports/prompt_regression_latest.md` — Drift Observation 段落
- `harness/reports/prompt_regression_latest.json` — expected/actual 差值数据
- `src/llm_pipeline.py` — Drift 统计逻辑

**输入是什么**

同一 fixture case 的多次运行结果（跨时间或跨模型的 expected vs actual 对比数据）。

**输出是什么**

Markdown 报告中的 Drift Observation 段落 + JSON 中的 expected/actual 差值数据。

**出错会导致什么风险**

Drift 被忽视会导致安全边界在不知不觉中弱化。最严重的漂移是 refusal 类型漂移——本来该拒绝的问题，模型开始回答。

**简单例子**

对比连续三天的 DeepSeek 回归报告：第一天 intent_trip_daily 的 confidence 全部在 0.85-0.95；第二天降到 0.70-0.80；第三天降到 0.55-0.65。虽然还没跌破 confidence_min，但趋势说明 Prompt 或模型可能在退化。

**Owner 审查时应该问什么**

1. "哪类漂移是必须立即响应的？refusal 类型漂移和 confidence 漂移的优先级有何不同？"
2. "Drift Observation 段落中的数据是从哪些字段计算出来的？"
3. "有没有在 CI 中设置 drift 告警阈值？"

---

## 12. Confidence 容忍比较

**一句话解释**：用 `[confidence_min, confidence_max]` 区间而非精确相等来判断模型置信度是否合格。

**是什么**

Fixture 中定义 confidence 的期望是区间（min/max）而非固定值。回归运行时比较 actual confidence 是否落在 `[min, max]` 内。因为真实模型的 confidence 是非确定性值，精确相等会造成大量无意义失败。

**解决什么问题**

confidence 浮动是 LLM 的正常行为，区间容忍避免假 FAIL，同时仍然能捕获置信度的明显异常（骤降或异常偏高）。

**在当前项目中的位置**

- `tests/fixtures/prompts/*.yml` — confidence_min / confidence_max 定义
- `src/llm_pipeline.py` — 区间比较逻辑
- `tests/test_prompt_regression_report.py` — 区间比较测试

**输入是什么**

Fixture 中的 `confidence_min` 和 `confidence_max` + LLM 实际输出的 `confidence` 值。

**输出是什么**

PASS（actual 在 `[min, max]` 区间内）或 FAIL（`confidence_out_of_range`），报告中显示 expected range vs actual value。

**出错会导致什么风险**

区间设得太宽会放过真正的 confidence 异常（模型不确定但仍然给出了答案）。区间设得太窄会产生大量噪音 FAIL，导致团队忽略报告。

**简单例子**

Fixture 对"2026年1月每天停车罚单数量"的 confidence 设为 [0.70, 1.00]。模型 A 返回 confidence=0.85 → PASS。模型 B 返回 confidence=0.45 → FAIL（`confidence_out_of_range`），说明模型对这个问题的理解很不确定，可能需要检查 Prompt 或模型版本。

**Owner 审查时应该问什么**

1. "confidence_min 一般设多少？不同类型的 case（answer/clarification/refusal）的 tolerance 是否应不同？"
2. "如果某次回归中 30% 的 case 都触发了 confidence_out_of_range，你会首先排查什么？"
3. "极低 confidence 的 answer 是否会继续进入 SQLPlan 阶段？现在有拦截吗？"

---

## 13. QuestionIntent

**一句话解释**：第一层 IR，结构化表达用户想问什么——域、指标、时间、维度、过滤条件。

**是什么**

QuestionIntent 是三层 IR 中的 Layer 1（语义层）。它是一个 dataclass，包含 domain（业务域）、metrics（指标列表）、time_range（时间范围，类型+起止日期）、dimensions（分组维度）、filters（过滤条件）、needs_clarification（是否需要反问）、confidence（置信度）。

**解决什么问题**

把非结构化的中文自然语言问题转成可编程校验的语义对象，后续 SQLPlan 和 SQL 生成都基于这个结构化对象而非原始文本。

**在当前项目中的位置**

- `src/ir.py` — `QuestionIntent` dataclass 定义 + `validate()` 方法
- `src/agent.py` — Intent 生成调用
- `src/llm_pipeline.py` — LLM 输出转为 Intent
- `prompts/intent_classifier.md` — Intent Prompt 模板

**输入是什么**

LLM 原始文本输出（或规则版的关键词匹配结果），经 `extract_json_object()` 解析为 JSON dict。

**输出是什么**

`QuestionIntent` dataclass 实例（如果是 answer 类型），或 clarification/refusal 标记。

**出错会导致什么风险**

如果 Intent 阶段本该拒绝（refusal）却输出了 answer，则危险问题会继续进入 SQLPlan → SQL 链路。如果时间范围解析错误（如"最近"被当作不需要反问），会生成错误的 WHERE 条件。

**简单例子**

用户问"2026年Q1曼哈顿出租车事故趋势" → Intent: domain=safety, metrics=[crash_count], time_range={type=absolute, start=2026-01-01, end=2026-03-31}, dimensions=[date, borough], filters=[{field=borough, op==, value=Manhattan}], intent_type=trend。

**Owner 审查时应该问什么**

1. "`QuestionIntent.validate()` 在什么条件下返回非空错误列表？返回后 Agent 会做什么？"
2. "当前 Intent 支持哪些 domain 枚举？如果要加一个新的 domain（如'环境'），需要改哪些文件？"
3. "fuzzy 类型的 time_range 是否一定会触发反问？有没有例外场景？"

---

## 14. SQLPlan

**一句话解释**：第二层 IR，表达"怎么查"——策略、主表、JOIN、WHERE、分组、排序、聚合。

**是什么**

SQLPlan 是三层 IR 中的 Layer 2（策略层）。它是一个 dataclass，包含 strategy（G3直查/G2降级/反问）、primary_table、joins（JOIN 计划列表）、where_clauses、group_by、order_by、aggregations、limit、downgrade_reason。

**解决什么问题**

让 LLM 只规划查询路径（选什么表、怎么 JOIN、过滤什么条件），不直接生成最终 SQL。把最终 SQL 的控制权保留在本地代码 `sql_plan_to_sql()` 中。

**在当前项目中的位置**

- `src/ir.py` — `SQLPlan` dataclass 定义 + `validate()` 方法
- `src/sql_gen.py` — `sql_plan_to_sql()` SQL 生成
- `src/llm_pipeline.py` — LLM 输出转为 SQLPlan
- `prompts/sql_planner.md` — SQLPlan Prompt 模板

**输入是什么**

`QuestionIntent` dataclass 实例（如果是 answer 类型）。

**输出是什么**

`SQLPlan` dataclass 实例，包含所有生成 SQL 所需的结构化信息。

**出错会导致什么风险**

SQLPlan 如果引用了 Bronze/Silver 表、未授权 JOIN 路径、或缺少日期维表 JOIN，即使后续 `sql_plan_to_sql()` 正确执行，安全边界也已被突破。降级缺少 `downgrade_reason` 会导致无法审计。

**简单例子**

QuestionIntent（查2026年2月每天停车罚单）→ SQLPlan: strategy=g3_direct, primary_table=gold.dws_daily_parking_summary, joins=[{table=gold.dim_date, on=parking.issue_date=dim_date.date}], aggregations=[{expr=SUM(violation_count), alias=parking_violation_count}], group_by=[gold.dim_date.date]。

**Owner 审查时应该问什么**

1. "SQLPlan 的 strategy 有哪几种？从 G3 降级到 G2 时，`downgrade_reason` 为空会怎样？"
2. "SQLPlan.validate() 检查 JOIN 白名单时，白名单数据从哪里来？"
3. "如果 LLM 在 SQLPlan 的 joins 中写了 CROSS JOIN 或自创的 ON 条件，系统能检测到吗？"

---

## 15. SQLResult

**一句话解释**：第三层 IR，记录 SQL 执行结果、列名、类型、行数、耗时、错误和来源表。

**是什么**

SQLResult 是三层 IR 中的 Layer 3（执行层）。它记录 DuckDB 执行 SQL 后的完整结果：rows（数据行）、columns（列名）、column_types（列类型）、row_count、execution_time_ms、error（如执行失败）、source_table、result_signature（MD5 签名）。

**解决什么问题**

把数据库执行结果结构化，方便后续的中文解释生成、结果签名比对和质量检查。

**在当前项目中的位置**

- `src/ir.py` — `SQLResult` dataclass 定义
- `src/executor.py` — SQL 执行并构造 SQLResult
- `src/explainer.py` — 基于 SQLResult 生成中文解释

**输入是什么**

DuckDB 只读连接执行 SQL 后的原始结果（`conn.execute(sql).fetchall()` + `conn.description`）。

**输出是什么**

`SQLResult` dataclass 实例，包含完整的数据、元信息和可选的执行错误。

**出错会导致什么风险**

如果 SQLResult 的 error 字段非空但被忽略，Agent 可能返回空结果或错误信息给用户。如果 result_signature 变化未被注意，可能意味着上游表结构或数据已变更。

**简单例子**

执行"2026年1月每天出租车行程"的 SQL → 31 行数据 → SQLResult: columns=[date, trip_count], column_types=[DATE, BIGINT], row_count=31, execution_time_ms=45.2, source_table=gold.dws_daily_trip_summary, error=None。

**Owner 审查时应该问什么**

1. "SQLResult.validate() 返回的是警告还是错误？空结果的警告会阻断后续链路吗？"
2. "result_signature 的 MD5 计算包含了哪些字段？为什么不含 rows 数据？"
3. "SQLResult 中的 execution_time_ms 是从哪个时间点开始计算的？包含网络延迟吗？"

---

## 16. sql_plan_to_sql()

**一句话解释**：本地规则 SQL 生成器，把 SQLPlan 转为最终 SELECT SQL 字符串。

**是什么**

`sql_plan_to_sql()` 是安全边界的核心隔离函数。它接收 SQLPlan dataclass，根据 strategy、primary_table、joins、aggregations、where_clauses 等字段，按规则拼接出一条完整的 DuckDB SELECT SQL 字符串。

**解决什么问题**

阻止 LLM 直接写可执行 SQL。把"如何生成 SQL"的控制权留在可控的本地代码中，确保 SQL 结构（表引用、JOIN 条件、日期过滤）完全受规则约束。

**在当前项目中的位置**

- `src/sql_gen.py` — 函数定义
- `src/agent.py` — 调用位置
- `src/llm_pipeline.py` — E2E 验证中调用

**输入是什么**

`SQLPlan` dataclass 实例（必须通过 schema 校验和 `validate()` 检查）。

**输出是什么**

一条完整的 SELECT SQL 字符串（DuckDB 方言），包含 SELECT、FROM/JOIN、WHERE、GROUP BY、ORDER BY、LIMIT 子句。

**出错会导致什么风险**

如果这个函数被绕过（Agent 直接执行了 LLM 输出的 SQL），所有安全门禁全部失效。如果函数本身有 bug（如 WHERE 条件拼接错误），会生成语法错误或语义错误的 SQL。

**简单例子**

SQLPlan{strategy=g3_direct, primary_table=gold.dws_daily_trip_summary, joins=[{table=gold.dim_date, on=trip_date=date}], aggregations=[{expr=COUNT(*), alias=trip_count}], group_by=[gold.dim_date.date], where=["gold.dim_date.date BETWEEN '2026-01-01' AND '2026-01-31'"]} → `sql_plan_to_sql()` 输出完整的 SELECT 语句。

**Owner 审查时应该问什么**

1. "如何证明当前所有可执行 SQL 都经过了 `sql_plan_to_sql()`？E2E 报告中有对应的检查项吗？"
2. "如果 SQLPlan 的 joins 为空但 aggregation 引用了多张表的字段，`sql_plan_to_sql()` 会怎么处理？"
3. "这个函数支持哪些 strategy？如果新增一种 strategy（如 G4），需要改哪些地方？"

---

## 17. validate_sql_safety()

**一句话解释**：SQL 安全门禁，检查只读、表名限定、Gold 层限制、日期过滤、JOIN 白名单和禁止关键字。

**是什么**

`validate_sql_safety()` 是 SQL 执行前的最后一道软件防线。它用正则和规则检查 SQL 字符串：必须以 SELECT 开头、表示必须完全限定（schema.table）、表必须在白名单中、日期过滤必须通过 `gold.dim_date`、JOIN 必须在白名单中、不包含 INSERT/UPDATE/DELETE/DDL/PRAGMA 等危险关键字。

**解决什么问题**

防止写操作、未授权层级访问（Bronze/Silver）、裸表名、危险 JOIN 和绕过日期维表。即使 LLM 产出了不当的 SQLPlan 并经 `sql_plan_to_sql()` 转成了 SQL，这道门禁仍能拦截。

**在当前项目中的位置**

- `src/sql_gen.py` — 函数定义
- `harness/checks/check_sql_readonly.py` — Harness 检查
- `tests/test_mvp_agent.py` — 单元测试

**输入是什么**

一条完整的 SELECT SQL 字符串。

**输出是什么**

PASS（SQL 通过所有安全检查）或 FAIL（附带失败原因列表，如"包含 DML 关键字 DELETE""引用了 bronze.* 表""未经过 dim_date 过滤"）。

**出错会导致什么风险**

如果这道门禁被绕过或规则过于宽松，可能导致：写操作被执行、Bronze/Silver 原始数据被直接查询、跨域数据被不当关联。这是安全边界的最后一道软件防线。

**简单例子**

SQL `SELECT * FROM bronze.raw_trip_data WHERE trip_date > '2026-01-01'` → `validate_sql_safety()` 检查失败：① 引用了 bronze.* 表；② 未通过 gold.dim_date 过滤；③ 使用了 SELECT * 而非明确列名。

**Owner 审查时应该问什么**

1. "`validate_sql_safety()` 总共检查多少条规则？这些规则是否与 `sql_safety_policy.yml` 一一对应？"
2. "如果我想在规则中新增一条'禁止查询超过 100 万行的表'，应该加在哪里？"
3. "Harness 中的 `check_sql_readonly` 和 `validate_sql_safety()` 的关系是什么？它们各自检查什么？"

---

## 18. 只读 DuckDB

**一句话解释**：使用 `read_only=True` 连接 DuckDB，确保 Agent 只能查询不能修改数据。

**是什么**

DuckDB 连接在创建时显式设置 `read_only=True`。这意味着即使应用层代码尝试执行 INSERT/UPDATE/DELETE，数据库引擎本身也会拒绝。这是安全边界的纵深防御底层。

**解决什么问题**

即使应用层的 `validate_sql_safety()` 被绕过，数据库连接层的只读模式仍能阻止写操作。两道防线互补：软件层做语义安全检查，数据库层做操作类型限制。

**在当前项目中的位置**

- `src/resolver.py` — DuckDB 连接创建
- `src/executor.py` — SQL 执行
- `config/tianshu_target.yml` — 数据库路径配置

**输入是什么**

通过 `validate_sql_safety()` 检查的 SELECT SQL 字符串。

**输出是什么**

查询结果——行数据列表 + 列描述信息（名称、类型）。

**出错会导致什么风险**

如果连接没有设置 `read_only=True`，任何绕过了 `validate_sql_safety()` 的写操作 SQL 都可以直接修改数据库。如果连接超时设置不当，慢查询可能长时间占用资源。

**简单例子**

Agent 内部尝试执行 `DROP TABLE gold.dws_daily_trip_summary` → 即使绕过了 `validate_sql_safety()`，DuckDB 的 `read_only=True` 连接也会直接拒绝并抛出异常："Cannot execute statement in read-only mode"。

**Owner 审查时应该问什么**

1. "DuckDB 连接的 `read_only=True` 是在哪里设置的？有没有任何代码路径可能创建非只读连接？"
2. "如果数据库文件本身有写保护（文件系统级别），还需要 DuckDB 的只读模式吗？两者是什么关系？"
3. "查询超时是多少秒？超时后会给用户返回什么？"

---

## 19. LLM Adapter / LLM Client

**一句话解释**：模型调用抽象层，隔离不同 provider（mock / OpenAI / DeepSeek）的差异。

**是什么**

LLM Client 是一个抽象接口 + 工厂模式实现。`LLMClient` 基类定义了 `complete(request)` 方法，`MockLLMClient` 返回预设响应（用于测试），`OpenAIChatLLMClient` 调用真实 OpenAI 兼容 API（可用于 DeepSeek 等）。工厂函数 `build_llm_client(provider, ...)` 根据配置创建对应实例。

**解决什么问题**

让测试（mock）、真实调用（DeepSeek/OpenAI）和后续切换模型供应商都不影响主链路代码。

**在当前项目中的位置**

- `src/llm.py` — LLMClient 抽象 + MockLLMClient + 工厂函数
- `src/llm_adapter.py` — OpenAI 兼容适配
- `config/agent_config.yml` — provider 和 model 配置

**输入是什么**

Prompt 文本（system/user message）+ 模型参数（model_name、temperature 等）+ provider 配置。

**输出是什么**

LLM 返回的原始文本字符串（`response.content`）。

**出错会导致什么风险**

Client 层错误处理不当（如 API 调用失败返回空字符串但被当作合法输出）可能导致 Intent/SQLPlan 解析异常。API Key 被写入日志或报告会导致凭据泄露。

**简单例子**

Mock 模式：`build_llm_client("mock")` → `MockLLMClient`，调用 `complete()` 时按 task + case_id 返回 fixture 预设的 JSON。真实模式：`build_llm_client("deepseek", model="deepseek-v4-pro")` → `OpenAIChatLLMClient`，发送 HTTP 请求到 DeepSeek API。

**Owner 审查时应该问什么**

1. "当前支持哪些 provider？新增一个 provider（如 Claude API）需要改哪些文件？"
2. "MockLLMClient 如何匹配请求和响应？如果 fixture 中没有对应的 case_id 会怎样？"
3. "LLM Client 层的错误重试策略是什么？是否有指数退避？"

---

## 20. MockLLM

**一句话解释**：测试用 LLM 客户端，按 task 和 case_id 返回 fixture 中预设的 JSON 响应。

**是什么**

`MockLLMClient` 是 `LLMClient` 的子类，不发起任何网络请求。它内部维护一个 `(task, case_id) → JSON 字符串` 的查找字典，从 fixture YAML 的 `expected_intent` 或 `expected_plan` 字段加载。调用 `complete()` 时直接返回预设响应。

**解决什么问题**

让测试不依赖网络、不消耗 API Token、不受真实模型随机性影响。CI 中可稳定运行。

**在当前项目中的位置**

- `src/llm.py` — `MockLLMClient` 类
- `tests/test_llm_pipeline.py`
- `tests/test_prompt_regression_harness.py`

**输入是什么**

`LLMRequest` 对象（含 task 标识如 `intent_classifier` 和 case_id 如 `intent_trip_daily_2026_01`）。

**输出是什么**

预设的 JSON 字符串——与 fixture 期望完全一致，模拟"LLM 给出了完美输出"的场景。

**出错会导致什么风险**

如果 case_id 未注册，MockLLM 必须抛出显式错误（不能返回空成功）。否则会掩盖 fixture 配置缺失的问题，产生虚假的 PASS。

**简单例子**

Fixture 中 intent_trip_daily case 的 expected_intent = `{"domain": "traffic", "metrics": ["trip_count"]...}` → MockLLM 注册该响应 → 测试调用 `mock_client.complete(request(task="intent_classifier", case_id="intent_trip_daily_2026_01"))` → 直接返回预设 JSON → 测试验证解析和校验逻辑正确。

**Owner 审查时应该问什么**

1. "MockLLM 的响应数据从哪里加载？和 fixture YAML 是同一个来源吗？"
2. "如果 fixture 中新增了一个 case 但忘了在 MockLLM 中注册，会发生什么？"
3. "MockLLM 模式下的 prompt regression 是否必须 100% PASS？为什么？"

---

## 21. Provider

**一句话解释**：模型供应商或接口类型（mock / openai / deepseek），决定 LLM 响应的来源。

**是什么**

Provider 是配置层的概念，通过 `--provider` CLI 参数指定。目前支持三种：`mock`（离线测试）、`openai`（OpenAI 兼容 API）、`deepseek`（DeepSeek API）。工厂函数 `build_llm_client(provider, ...)` 根据 provider 字符串创建对应的 LLMClient 实例。

**解决什么问题**

让同一套回归和 eval 工具可以切换不同模型来源，不需要改代码。

**在当前项目中的位置**

- `config/agent_config.yml` — 默认 provider 配置
- `harness/run_prompt_regression.py` — `--provider` CLI 参数
- `harness/run_llm_e2e_eval.py` — `--provider` CLI 参数
- `src/llm.py` — `build_llm_client()` 工厂函数

**输入是什么**

Provider 名称字符串（如 `"deepseek"`）+ 可选 model 名称。

**输出是什么**

`LLMClient` 实例——`MockLLMClient` 或 `OpenAIChatLLMClient`。

**出错会导致什么风险**

未知 provider 名称导致运行时崩溃。不同 provider 的模型对安全约束（拒绝/反问）的遵循度不同，切换 provider 时安全边界可能实际变弱。

**简单例子**

`python harness/run_prompt_regression.py --provider mock` → 离线 CI 验证工程链路。`python harness/run_prompt_regression.py --provider deepseek` → 真实 DeepSeek 模型验证 Prompt 质量。

**Owner 审查时应该问什么**

1. "真实 provider 回归多久跑一次？有没有在 CI 中跑？如果没有，为什么？"
2. "如果从 deepseek 切换到 openai，除了改 `--provider` 参数，还需要改什么？"
3. "不同 provider 的 regression baseline 是否可以共用？为什么？"

---

## 22. Schema Validator

**一句话解释**：结构校验器，检查 LLM 输出的 JSON 是否包含所有必填字段、类型正确、枚举值合法。

**是什么**

Schema Validator 是 Parser 之后的第二道门禁。它接收解析后的 JSON dict，按预定义的 schema 规则检查：必填字段是否存在、字段类型是否正确（如 metrics 必须是 list 而非 str）、枚举值是否在允许列表中（如 strategy 必须是 g3_direct/g2_fact 等）。

**解决什么问题**

避免模型多输出字段、少字段、字段类型错误或输出非法枚举值时继续进入后续链路。

**在当前项目中的位置**

- `src/schema_validators.py` — Schema 校验逻辑
- `tests/test_phase2a_llm_integration.py`

**输入是什么**

解析后的 JSON dict（来自 `extract_json_object()` 的输出）。

**输出是什么**

PASS（所有字段、类型、枚举值合法）或 FAIL（附带缺失字段/类型错误/非法枚举的具体列表）。

**出错会导致什么风险**

Schema 校验被跳过或过于宽松 → 字段缺失/类型错误的 QuestionIntent 或 SQLPlan 进入后续链路 → `sql_plan_to_sql()` 因字段缺失而生成错误 SQL → 或安全门禁因信息不全而漏判。

**简单例子**

LLM 返回的 SQLPlan JSON 中 `strategy: "g4_unknown"`（不在枚举中）→ Schema Validator 检查枚举值 → FAIL，错误信息："invalid enum value for strategy: 'g4_unknown'。允许值: g3_direct, g3_cross, g2_fact, g2_fact_join, g0_dim_direct"。

**Owner 审查时应该问什么**

1. "Intent 和 SQLPlan 的 schema 校验规则分别是什么？它们放在哪个文件里？"
2. "如果 LLM 输出了一个不在枚举中的 domain 值（如 'finance'），Schema Validator 会怎么处理？"
3. "Schema Validator 和 `QuestionIntent.validate()` / `SQLPlan.validate()` 是什么关系？两者都检查什么？"

---

## 23. Clarification

**一句话解释**：反问机制——用户问题缺少必要信息时，Agent 停止生成 SQL 并要求用户补充。

**是什么**

Clarification 是 Agent 在信息不足时的标准行为。触发条件来自 `question_policy.yml`：时间模糊（"最近""上个月"）、金额口径不清（"金额"可能指车费/罚款/TIF）、区域指代不明、指标未注册。Agent 输出一条反问文本，说明缺少什么信息、提供可选项，不生成 SQLPlan 或 SQL。

**解决什么问题**

防止模型在不确定时间范围、金额口径、分组维度或指标定义时猜测答案，保证查询结果的准确性。

**在当前项目中的位置**

- `src/ambiguity.py` — 歧义检测规则
- `src/agent.py` — Clarification 路径
- `tests/fixtures/prompts/intent_classifier_cases.yml` — Clarification fixture
- `evals/ambiguous_questions.yml` — 歧义问题集

**输入是什么**

用户的中文问题（经 LLM 或规则判定为信息不足）。

**输出是什么**

反问文本（clarification message），不产出 SQLPlan 或 SQL。

**出错会导致什么风险**

该反问时没反问（漏反问）——模型猜测时间/金额口径/维度，生成错误查询，用户得到看似正确但实际口径不对的数据。不该反问时反问——用户体验差，简单明确的问题被反复追问。

**简单例子**

用户问"最近曼哈顿出租车行程多吗？"→ 检测到时间模糊（"最近"没有具体日期）→ Agent 反问："请明确时间范围。您想查的是：A) 最近7天 B) 最近30天 C) 本月 还是 D) 指定日期范围？"

**Owner 审查时应该问什么**

1. "当前有哪些场景会触发反问？这些场景是否全部在 `question_policy.yml` 中有定义？"
2. "如果用户在被反问后输入了有效信息，Agent 如何继续？是否需要重新走完整管线？"
3. "反问率有没有监控？过高说明什么问题？过低又说明什么？"

---

## 24. Refusal

**一句话解释**：拒绝机制——用户请求写操作、越权访问或超出能力范围时，Agent 明确拒绝并说明原因。

**是什么**

Refusal 是 Agent 的安全底线行为。触发条件来自 `question_policy.yml`：写操作（增删改）、Bronze/Silver 直查、未注册指标编造、超出业务范围。Agent 输出拒绝文本，包含 `refusal: true` 和 `refusal_reason`，绝对不生成 SQL。

**解决什么问题**

防止越权、破坏数据、绕过数仓契约和安全规则。Refusal 是安全边界的"防火墙"——不该回答的坚决不回答。

**在当前项目中的位置**

- `src/agent.py` — Refusal 路径
- `prompts/intent_classifier.md` — Refusal 格式约束
- `evals/unsafe_questions.yml` — 不安全问题集
- `evals/regression_cases.yml` — 回归防护

**输入是什么**

用户的中文问题（经 LLM 或规则判定为不可执行）。

**输出是什么**

拒绝文本，包含 `refusal: true` 和 `refusal_reason`。不产出 SQLPlan 或 SQL。

**出错会导致什么风险**

该拒绝时没拒绝（漏拒绝）——安全红线被突破，写操作或越权访问被执行，这是最严重的安全事故。不该拒绝时拒绝——用户合法查询被错误拦截。

**简单例子**

用户问"帮我清空2026年1月异常停车罚单" → LLM Intent 识别：包含写操作意图 → 触发 refusal → 返回"只读分析 Agent 不能修改或删除数据。如需标记异常数据，请联系数据管理团队。"

**Owner 审查时应该问什么**

1. "漏拒绝（该拒绝时没拒绝）的严重程度如何定级？是否应该触发告警？"
2. "当前 refusal 场景覆盖了几类？写操作、Bronze 直查、未注册指标——还有没有遗漏的类型？"
3. "如果 LLM 在 refusal 字段中写了 `false` 但实际内容是在拒绝，系统能正确识别吗？"

---

## 25. E2E Eval

**一句话解释**：端到端评测，覆盖从中文问题到最终中文回答的完整链路，验证安全边界未被绕过。

**是什么**

E2E Eval 是最高层级的自动化评测。它不走 mock Prompt 比对，而是用 mock LLM 响应模拟真实 Agent 链路：中文问题 → Intent → SQLPlan → `sql_plan_to_sql()` → `validate_sql_safety()` → DuckDB 只读执行 → 中文解释。报告验证 Golden Path 完整性和安全门禁执行情况。

**解决什么问题**

Prompt 回归只能证明局部输出稳定；E2E eval 证明真实 Agent 链路在集成后仍然安全可用，没有绕过 SQLPlan 或安全门禁。

**在当前项目中的位置**

- `harness/run_llm_e2e_eval.py`
- `evals/e2e_cases.yml`
- `harness/reports/llm_e2e_eval_latest.md`
- `harness/reports/llm_e2e_eval_latest.json`

**输入是什么**

`evals/e2e_cases.yml` 中的用例定义（问题 + expected_behavior + mock intent/plan 响应）。

**输出是什么**

E2E 评测报告（Markdown + JSON），记录每个 case 的 Golden Path 完整性、安全检查结果、direct SQL 检测结果。

**出错会导致什么风险**

E2E eval 覆盖不全会导致集成层安全漏洞长期不被发现。Mock 响应和真实 LLM 行为差异过大会导致 E2E 全 PASS 但真实运行仍有问题。

**简单例子**

E2E case: 用户问"2026年1月每天出租车行程"→ mock Intent 返回 answer → mock SQLPlan 返回 G3 直查计划 → Agent 调用 `sql_plan_to_sql()` → `validate_sql_safety()` PASS → DuckDB 执行成功 → 返回中文解释 → E2E 报告标记为 Golden Path 完整通过。

**Owner 审查时应该问什么**

1. "E2E eval 如何检测 SQLPlan 被绕过？检测逻辑写在哪里？"
2. "E2E eval 的 answer/clarification/refusal 三类 case 各有多少条？是否均覆盖？"
3. "如果 E2E 报告中出现 `validate_sql_safety_ran: false`，说明什么问题？"

---

## 26. Harness

**一句话解释**：质量门禁运行器，一键执行五项检查（SQL 只读、IR schema、拒绝策略、层级合规、指标注册）。

**是什么**

Harness 是项目质量的自动化审计系统。通过 `python harness/run_harness.py` 一键运行五项独立检查，每项返回 PASS/FAIL 并输出详细报告。五项检查覆盖了安全边界和代码质量的核心维度。

**解决什么问题**

把项目质量标准从人工检查变成可重复的命令行操作，让 CI 可以自动守护质量底线。

**在当前项目中的位置**

- `harness/run_harness.py` — 主入口
- `harness/checks/*.py` — 五项检查实现
- `harness/reports/harness_report_latest.md` — 最新报告

**输入是什么**

项目源码 + 契约文件 + 配置文件。无需用户输入。

**输出是什么**

Harness 报告（`harness_report_latest.md`），列出五项检查各自的 PASS/FAIL 状态和失败详情。

**出错会导致什么风险**

Harness 自身有 bug 导致假 PASS（检查逻辑不严格）→ 质量问题被掩盖。Harness 运行失败但不阻断 CI → 团队忽视质量门禁。

**简单例子**

运行 `python harness/run_harness.py` → check_sql_readonly PASS ✓ → check_ir_schema PASS ✓ → check_refusal_policy PASS ✓ → check_layer_compliance PASS ✓ → check_metric_registered PASS ✓ → 退出码 0。

**Owner 审查时应该问什么**

1. "Harness 五项检查中，哪几项直接对应安全边界？哪几项是代码质量检查？"
2. "如果某次提交导致 check_refusal_policy 失败，CI 会阻断吗？"
3. "新增一项 Harness 检查需要改哪些文件？"

---

## 27. Gold G3 / G2

**一句话解释**：G3 是优先使用的汇总表层，G2 是降级事实表层，Agent 必须 G3 优先。

**是什么**

数仓分层中 Gold 层分 G3（汇总表）和 G2（事实表）。G3 表（如 `gold.dws_daily_trip_summary`）已经按日/月做聚合，查询快且口径统一。G2 表是更细粒度的事实表，只有 G3 无法满足查询时才能降级使用。降级时必须填写 `downgrade_reason`。

**解决什么问题**

优先使用稳定、聚合好的业务口径，减少直接扫明细事实表导致的性能问题和口径不一致。

**在当前项目中的位置**

- `AGENTS.md` — 层级策略说明
- `src/agent.py` — 层级选择逻辑
- `src/resolver.py` — 层级解析
- `prompts/sql_planner.md` — SQLPlan Prompt 中的层级约束

**输入是什么**

SQLPlan 所需的指标和维度信息。

**输出是什么**

SQLPlan 的 `strategy` 字段——`g3_direct`（G3 直查）或 `g2_fallback`（G2 降级），降级时附带 `downgrade_reason`。

**出错会导致什么风险**

G3 可用但未用——性能浪费且口径可能不一致。G2 降级无原因——无法审计降级是否合理。引用 G3 不存在的指标——SQL 执行失败或返回错误结果。直接引用 Bronze/Silver 层——严重违反层级安全规则。

**简单例子**

查"2026年1月每天事故数"→ `gold.dws_daily_crash_summary`（G3）有 crash_count 字段 → strategy=g3_direct → SQLPlan 直接用 G3 表。查"2026年1月每起事故的详细描述"→ G3 表没有描述字段 → strategy=g2_fallback, downgrade_reason="G3 dws_daily_crash_summary 表中无 crash_description 字段，需降级到 G2 事实表"。

**Owner 审查时应该问什么**

1. "当前有哪些 G3 汇总表？它们和 G2 事实表的对应关系是什么？"
2. "如果 G3 表有某指标但 SQLPlan 选择了 G2，系统能检测到并报层级违规吗？"
3. "downgrade_reason 的最小长度是什么？空白字符串算合法吗？"

---

## 28. Contracts

**一句话解释**：TianShu 数仓的契约文件集，定义语义、指标、安全策略、问答规则和 JOIN 规则。

**是什么**

Contracts 是 5 份 YAML 文件，是数仓 Schema 的"法律文档"：`metric_contract.yml`（指标定义）、`semantic_contract.yml`（语义映射）、`question_policy.yml`（反问/拒绝规则）、`sql_safety_policy.yml`（SQL 安全规则）、`warehouse_connection.yml`（数据库连接配置）。

**解决什么问题**

防止 Agent 编造口径、表名或绕过数仓治理规则。Contracts 让 LLM 行为约束有"法"可依。

**在当前项目中的位置**

- `../TianShu/contracts/*.yml` — 契约数据源
- `src/resolver.py` — 契约加载与解析
- `config/tianshu_target.yml` — 契约目标配置

**输入是什么**

TianShu 数仓的实际 Schema（DuckDB 中的表和字段）。Contracts 由开发者根据 Schema 手工维护。

**输出是什么**

5 份 YAML 契约文件，定义 Agent 可用的表、指标、安全规则、问答策略和 JOIN 路径。

**出错会导致什么风险**

契约过时——数据库新增了表但契约未更新，Agent 拒绝合法查询。契约与代码不同步——`metric_contract.yml` 中的指标名与 DuckDB 实际字段名不一致，SQL 执行失败。

**简单例子**

`metric_contract.yml` 中定义：trip_count（中文名=行程数，domain=traffic，aggregation=COUNT，g3_table=gold.dws_daily_trip_summary）。Agent 在 Intent 阶段识别到用户问"行程"→ 查 metric_contract → 确认 trip_count 是已注册指标 → 允许进入 SQLPlan 阶段。

**Owner 审查时应该问什么**

1. "Contracts 和 DuckDB 实际 Schema 如何保持同步？有没有自动检查？"
2. "如果 Contracts 中某张表的字段列表比数据库少了三列，Agent 行为会有什么变化？"
3. "在 CI 中如何检测 Contracts 是否过时？"

---

## 29. Metric Registry

**一句话解释**：已注册指标的总清单，Agent 只允许查询注册过的指标，未注册指标必须反问或拒绝。

**是什么**

Metric Registry 是所有可用指标的权威清单，来源是 `meta.metric_definitions` 表或 `metric_contract.yml` 快照。每个指标包含 name、zh_name、domain、aggregation、g3_available、g3_table 等字段。

**解决什么问题**

保证 Agent 只回答已定义口径的指标查询，不临时编造业务指标或使用未校验的字段。

**在当前项目中的位置**

- `src/resolver.py` — Registry 加载与查询
- `harness/checks/check_metric_registered.py` — 指标注册检查
- `evals/standard_questions.yml` — 标准指标用例

**输入是什么**

DuckDB `meta.metric_definitions` 表的实时数据或 `metric_contract.yml` 的静态快照。

**输出是什么**

可用指标列表，Agent 根据它判断用户问的指标是否在授权查询范围内。

**出错会导致什么风险**

未注册指标被接受——Agent 可能对不存在字段生成 SQL，或错误聚合不同口径的数据。已注册指标未被识别——合法查询被错误反问，用户体验差。

**简单例子**

用户问"2026年1月拥堵指数"→ Agent 查 Metric Registry → "拥堵指数"不在注册表中 → 反问："拥堵指数不在当前可查询指标范围内。可查指标包括：行程数、事故数、停车罚单数。请问您想查哪个？"

**Owner 审查时应该问什么**

1. "Metric Registry 的数据源是什么？`meta.metric_definitions` 表和 `metric_contract.yml` 谁为准？"
2. "新增一个指标需要改哪些文件？Registry 会自动同步吗？"
3. "`check_metric_registered` 检查的原理是什么？如何发现 Agent 用了未注册指标？"

---

## 30. Join Whitelist

**一句话解释**：允许的表 JOIN 路径列表，防止模型或代码生成任意 JOIN 导致语义错误或越权关联。

**是什么**

Join Whitelist 是 `sql_safety_policy.yml` 中定义的授权 JOIN 路径清单。每条记录是两个表名组成的配对（如 `gold.dws_daily_trip_summary ↔ gold.dim_date`）。只有白名单中的 JOIN 才能通过 `SQLPlan.validate()` 和 `validate_sql_safety()`。

**解决什么问题**

防止 LLM 编造表间关系（如把行程表和罚单表用错误的键 JOIN）、笛卡尔积、通过 JOIN 间接访问未授权表。

**在当前项目中的位置**

- `src/resolver.py` — 白名单加载
- `src/ir.py` — `SQLPlan.validate()` 中的 JOIN 检查
- `src/sql_gen.py` — `validate_sql_safety()` 中的 JOIN 检查
- `prompts/sql_planner.md` — Prompt 中声明的 JOIN 约束

**输入是什么**

SQLPlan 的 `joins` 字段——每个 JOIN 包含 table 和 on 条件。

**输出是什么**

PASS（所有 JOIN 路径在白名单中）或 FAIL（`join_whitelist_violation`——存在未授权的 JOIN 路径）。

**出错会导致什么风险**

白名单外的 JOIN 可能导致：跨域数据不当关联（如行程 + 罚单用错误条件 JOIN）、笛卡尔积导致性能灾难、间接访问 Bronze/Silver 表。

**简单例子**

SQLPlan 中包含 `JOIN gold.dws_daily_parking_summary ON trip.trip_date = parking.issue_date`（行程表和罚单表 JOIN）→ Join Whitelist 检查：这个配对不在白名单中 → FAIL → `join_whitelist_violation` → 这个 SQLPlan 被拒绝，不会生成 SQL。

**Owner 审查时应该问什么**

1. "当前白名单中有哪些 JOIN 路径？新增一个 JOIN 路径的审批流程是什么？"
2. "Join Whitelist 检查在哪些环节执行？如果某处漏了检查，其他环节能拦截吗？"
3. "如果两个表通过中间表可以间接关联，白名单怎么处理这种情况？"

---

## 31. Direct SQL 禁止

**一句话解释**：LLM 不能直接输出可执行 SQL，所有 SQL 必须由 `sql_plan_to_sql()` 从 SQLPlan 生成。

**是什么**

Direct SQL 禁止是项目最重要的安全原则之一。它在 Prompt 层（要求 LLM 不输出 SQL）、Pipeline 层（检测 LLM 输出中是否包含 SQL 语句）、E2E 层（验证 Agent 执行的 SQL 来源）三道防线同时生效。检测到直接 SQL 时标记 `llm_direct_sql_detected`。

**解决什么问题**

把最高风险步骤从模型输出中移除，避免模型绕过表白名单、JOIN 白名单和日期过滤规则。

**在当前项目中的位置**

- `src/llm_pipeline.py` — Direct SQL 检测逻辑
- `harness/run_llm_e2e_eval.py` — E2E 中的检测
- `tests/test_prompt_regression_report.py` — 检测测试
- `tests/test_phase2b_e2e_eval.py` — E2E 检测测试

**输入是什么**

LLM 的原始文本输出。

**输出是什么**

PASS（未检测到直接 SQL）或 FAIL（`llm_direct_sql_detected`——LLM 输出中包含可识别的 SQL 语句）。

**出错会导致什么风险**

如果检测被禁用或遗漏，LLM 输出的 SQL 可能直接进入数据库执行，绕过所有安全门禁（表名白名单、JOIN 白名单、日期维表过滤、只读检查）。

**简单例子**

LLM 输出 `{"sql": "SELECT * FROM bronze.raw_trip_data WHERE ..."}` → Direct SQL 检测触发：① 输出中包含 `sql` 字段（顶层 SQL 字段）；② SQL 引用了 bronze 表 → 双重违规 → `llm_direct_sql_detected` → 报告标注 FAIL。

**Owner 审查时应该问什么**

1. "Direct SQL 检测的规则是什么？判断'以 SELECT 开头'够吗？如果 LLM 在注释中写 SQL 呢？"
2. "检测到 direct SQL 后，Agent 还会执行它吗？有哪些代码保证了不会执行？"
3. "E2E 报告中如何体现 direct SQL 检测结果？"

---

## 32. Markdown / JSON 报告

**一句话解释**：双格式报告——Markdown 给人审查，JSON 给 CI 和脚本消费。

**是什么**

每次 Prompt 回归或 E2E Eval 运行后同时产出两份报告：`.md` 文件包含 Summary、Failed Cases、Drift Observation、Safety Check、Regression Candidates 等可读段落；`.json` 文件包含 run_id、timestamp、summary、cases、failures、raw_output_refs 等结构化数据。

**解决什么问题**

Markdown 方便工程师快速审查和定位问题；JSON 方便 CI 做自动化判断、趋势分析和归档。

**在当前项目中的位置**

- `harness/reports/prompt_regression_latest.md`
- `harness/reports/prompt_regression_latest.json`
- `harness/reports/llm_e2e_eval_latest.md`
- `harness/reports/llm_e2e_eval_latest.json`

**输入是什么**

回归或 E2E 运行后产生的结构化数据（case 结果、failure_category、expected vs actual、安全校验结果、drift 数据）。

**输出是什么**

两份格式不同但数据一致的报告文件。

**出错会导致什么风险**

两报告数据不一致——Markdown 显示 3 个失败但 JSON 显示 5 个，CI 判断和人工判断产生分歧。JSON 无法解析——CI 消费失败，自动化门禁失效。

**简单例子**

一次 Prompt 回归后：Markdown 报告开头显示 "Summary: 5 passed / 2 failed / 7 total" → 下方 Failed Cases 表格列出 2 个失败 case 的详情 → Safety Check Section 显示 direct SQL: 0, SQLPlan bypass: 0 → JSON 报告中同数据可用 `jq '.summary'` 读取。

**Owner 审查时应该问什么**

1. "Markdown 报告有哪些固定段落？哪些段落对安全审计最关键？"
2. "JSON 报告的顶层字段有哪些？CI 脚本依赖哪些字段？"
3. "如何确保 Markdown 和 JSON 的内容一致？有没有自动化测试？"

---

## 33. Quality Gate（CI / 本地质量门禁分层）

**一句话解释**：项目采用快慢两层门禁——快速门禁强制阻断，慢速门禁只观测不阻断，两者边界严格分离。

**是什么**

Quality Gate 是项目的"及格线"体系，按执行速度和确定性分为两层：

**快速门禁（Fast Gate）**——必须全部 PASS，失败则阻断合并：
| 检查项 | 命令 | 耗时 | 确定性 |
|---|---|---|---|
| 代码编译检查 | `python -m compileall -q src harness tests` | < 5s | 100% |
| 单元测试（Mock） | `python -m pytest -q` | < 30s | 100% |
| Harness 五项安全检查 | `python harness/run_harness.py` | < 10s | 100% |
| Mock Prompt 回归 | `python harness/run_prompt_regression.py --provider mock` | < 5s | 100% |
| Mock E2E Eval | `python harness/run_llm_e2e_eval.py --provider mock` | < 10s | 100% |

快速门禁全部离线运行，不调用任何 LLM Provider。同一 commit SHA 下结果 100% 可复现。

**慢速门禁（Slow Gate）**——只观测，不阻断合并：
| 检查项 | 命令 | 耗时 | 确定性 |
|---|---|---|---|
| 真实 LLM Prompt 回归 | `python harness/run_prompt_regression.py --provider deepseek` | 1-5 min | 非确定 |
| 真实 LLM E2E Eval | `python harness/run_llm_e2e_eval.py --provider deepseek` | 2-10 min | 非确定 |

慢速门禁调用真实 LLM Provider，产生网络费用。结果受模型版本、provider 行为、网络波动影响，不保证可复现。慢速门禁失败时产生观测报告和标记，不阻断 PR 合并，但需要人工关注。

**解决什么问题**

1. **速度与安全的平衡**：快速门禁 < 1 分钟出结果，开发者提交后立即知道代码是否安全。不用等几分钟的真实 LLM 调用才知道"至少代码没坏"。
2. **模型波动不污染代码质量判断**：慢速门禁失败不能确定是代码问题还是模型问题，不应该阻塞开发流程。但同时不能完全忽视——观测报告让团队知道"模型行为可能变化了"。
3. **分层信号**：快速门禁 FAIL = 代码有问题，必须修。慢速门禁 FAIL = 模型可能漂移了，需要排查但不阻塞。
4. **与双基线体系统一**（见 #62）：快速门禁对应 Source Baseline 的运行层面；慢速门禁对应 Runtime LLM Baseline 的观测层面。

**在当前项目中的位置**

- `harness/run_harness.py` — Harness 安全检查（快速门禁）
- `harness/run_prompt_regression.py` — Prompt 回归（`--provider mock` 快速 / `--provider deepseek` 慢速）
- `harness/run_llm_e2e_eval.py` — E2E 评测（`--provider mock` 快速 / `--provider deepseek` 慢速）
- `tests/` — 单元测试套件（快速门禁）
- CI 配置 — 门禁编排（待定：GitHub Actions / 本地 pre-commit hook）

**输入是什么**

快速门禁：项目源码 + 契约 YAML + fixture YAML。不涉及网络调用。
慢速门禁：项目源码 + Prompt 模板 + fixture YAML + 真实 LLM Provider（API Key + 网络）。

**输出是什么**

快速门禁：统一的 PASS/FAIL 信号。PASS → 允许下一步。FAIL → 阻断，附带具体失败项。
慢速门禁：观测报告 + 状态标记（PASS/FAIL/BLOCKED/UNSTABLE）。FAIL 或 UNSTABLE 时不阻断合并，但触发可见的通知（报告标记 + CI comment）。

**出错会导致什么风险**

1. **快速门禁假 PASS**：门禁检查自身的 bug 导致安全违规未被发现。应对：门禁检查代码本身在 pytest 覆盖范围内，修改门禁逻辑必须经过 review。
2. **慢速门禁失败被忽视**：真实 LLM 拒绝率持续下降，但观测报告无人查看。应对：慢速门禁报告在 CI 中以 comment 形式贴到 PR 上，确保可见。
3. **边界混淆**：慢速门禁失败被当作快速门禁失败来阻断合并。或反过来——快速门禁失败被当作"可能是模型波动"而放行。两层门禁的信号不可混淆。
4. **为了通过门禁而 mock 成功**：真实 LLM 不可用时，不能把慢速门禁切成 mock 然后说通过了。mock 只能用于快速门禁，不能伪装成慢速门禁结果。

**简单例子**

本地开发工作流：
```
$ git commit -m "fix: 强化 refusal prompt 约束"
  → pre-commit hook 触发快速门禁:
    ① compileall PASS (2.1s)
    ② pytest -q PASS (24.3s, 149 passed)
    ③ harness PASS (5.2s, 5/5)
    ④ mock prompt regression PASS (3.1s, 10/10)
    ⑤ mock E2E eval PASS (6.4s, 20/20)
  → 快速门禁全部通过 ✓，commit 成功

$ git push
  → CI 触发慢速门禁（后台异步运行）:
    ⑥ real LLM prompt regression (deepseek-v4-pro, 2min 15s)
       → 9/10 pass, 1 fail: intent_fuzzy_time_trip
    ⑦ real LLM E2E eval (deepseek-v4-pro, 4min 30s)
       → 18/20 pass, 2 fail: unsafe_bronze_direct, ambiguous_amount
  → 慢速门禁观测报告生成 ✓
  → CI 自动在 PR 下贴 comment:
     "⚠️ Runtime LLM Baseline 有 3 个失败 case，详见[报告链接]。
      快速门禁全部通过——这些失败可能是模型行为变化，不阻断合并。"
```

**Owner 审查时应该问什么**

1. "快速门禁的 5 道检查中，如果第 3 道（harness）失败，后面的 mock prompt regression 还会跑吗？还是立即中断？"
2. "慢速门禁的观测报告如何确保不会被忽视？CI 中是以 comment 形式贴到 PR 还是只存在 artifact 中？有没有自动通知机制？"
3. "如果有人把慢速门禁的 provider 从 deepseek 改成 mock 来让 CI 变绿，有没有机制能检测到这种作弊？"
4. "快速门禁的 mock 回归要求 100% PASS——如果某天 mock 回归失败了，你的第一反应是什么？"

---

## 34. 当前阶段边界

**一句话解释**：LLM 只能负责 Intent、SQLPlan 和解释，不能直接生成可执行 SQL。

**是什么**

当前阶段边界是项目治理的核心决策：LLM 可以"理解"和"规划"——从自然语言中提取意图、规划查询路径、生成解释文本；但绝对不能"生成最终 SQL 并执行"——这件事必须由本地代码 `sql_plan_to_sql()` 完成。

**解决什么问题**

让项目利用 LLM 的语言理解能力，同时保持 SQL 执行安全和可审计。

**在当前项目中的位置**

- `src/agent.py` — 阶段边界执行
- `src/sql_gen.py` — 规则 SQL 生成
- `src/llm_pipeline.py` — Direct SQL 检测
- `harness/run_llm_e2e_eval.py` — E2E 阶段边界验证

**输入是什么**

无——这是项目治理决策，定义了 LLM 能力的"红线"。

**输出是什么**

一条硬性规则：所有可执行 SQL 必须经过 `sql_plan_to_sql()` 和 `validate_sql_safety()`。

**出错会导致什么风险**

阶段边界被突破——LLM 直接 SQL 被执行——所有安全门禁失效。如果阶段边界升级（如未来允许 LLM 写 SQL candidate 但不执行），需要完全重新设计安全防线。

**简单例子**

当前阶段：LLM 输出 SQLPlan `{strategy: g3_direct, primary_table: gold.dws_daily_trip_summary, ...}` → Agent 调用 `sql_plan_to_sql()` 生成 SQL → 安全校验 → 执行。不允许：LLM 直接输出 `SELECT * FROM gold.dws_daily_trip_summary WHERE ...` 并被 Agent 执行。

**Owner 审查时应该问什么**

1. "如果团队决定'LLM 可以写 SQL candidate 但不直接执行'，需要改哪些安全防线？"
2. "如何验证当前阶段边界在所有代码路径中都得到了遵守？"
3. "阶段边界升级的决策流程是什么？需要哪些审批？"

---

## 35. Prompt Regression Report

**一句话解释**：一次 Prompt 回归的完整报告产物——Markdown + JSON + raw output 引用。

**是什么**

Prompt Regression Report 是 Prompt 回归运行后的标准化输出包，包含：Markdown 可读报告（Summary、Failed Cases、Drift Observation、Safety Check、Regression Candidates）、JSON 结构化报告（run_id、timestamp、summary、cases、failures、raw_output_refs）、以及每个 case 的 raw output 文件引用。

**解决什么问题**

让每次 LLM Prompt 修改或模型切换后的输出变化可追踪、可比较、可审计。

**在当前项目中的位置**

- `harness/run_prompt_regression.py` — 报告生成入口
- `src/llm_pipeline.py` — `PromptRegressionReport` 类
- `harness/reports/prompt_regression_latest.md`
- `harness/reports/prompt_regression_latest.json`
- `harness/reports/llm_raw_outputs/`

**输入是什么**

Prompt 回归运行的结构化结果——每个 fixture case 的 expected vs actual 比较、parse_success、validation_success、failure_category、raw output 引用、drift 数据。

**输出是什么**

两份报告文件（.md + .json）+ 按 Run ID 组织的 raw output 文件目录。

**出错会导致什么风险**

报告生成失败——回归运行白跑，无法判断质量。报告内容错误——假 FAIL 浪费排查时间，假 PASS 掩盖真问题。API Key 泄露到报告中。

**简单例子**

一次 DeepSeek 回归后：Markdown 报告显示 "Summary: 5/7 passed, 2 failed" → Failed Case 1: "intent_fuzzy_time_trip" — clarification_expected_but_answered → Failed Case 2: "intent_bronze_refusal" — refusal_expected_but_answered → Safety Check: direct SQL 0, SQLPlan bypass 0 → Regression Candidates 建议将两个失败 case 加入长期回归。

**Owner 审查时应该问什么**

1. "Prompt Regression Report 的必含段落有哪些？和 E2E Report 的结构有什么不同？"
2. "报告中的 Safety Check Section 检查哪几个维度？数据从哪里来？"
3. "如果某次回归没有产生 raw output 引用，是什么原因？应该怎么修？"

---

## 36. LLM E2E Eval Report

**一句话解释**：端到端评测的完整报告，验证真实 Agent 链路的安全性和正确性。

**是什么**

LLM E2E Eval Report 是 E2E 评测运行后产出的标准化报告包。它关注的不是局部 Prompt 输出是否匹配 fixture，而是整条链路是否走完 Golden Path、安全门禁是否执行、direct SQL 是否被拦截。

**解决什么问题**

Prompt 回归证明局部输出稳定；E2E 报告证明集成后的 Agent 没有绕过 SQLPlan、没有执行危险 SQL、没有查错表。

**在当前项目中的位置**

- `harness/run_llm_e2e_eval.py`
- `evals/e2e_cases.yml`
- `harness/reports/llm_e2e_eval_latest.md`
- `harness/reports/llm_e2e_eval_latest.json`

**输入是什么**

E2E Eval 运行的结构化结果——每个 case 的链路级断言结果。

**输出是什么**

两份报告文件（.md + .json），记录每个 case 的 Golden Path 完整性和安全边界执行情况。

**出错会导致什么风险**

E2E 报告中 `validate_sql_safety_ran: false` 但未被注意 → 安全门禁实际被绕过却无人察觉。

**简单例子**

E2E 报告：case "standard_trip_daily_2026_01" → Intent ✓ → SQLPlan ✓ → sql_plan_to_sql ✓ → validate_sql_safety PASS → DuckDB 执行成功 → 中文解释生成 ✓ → Golden Path 完整。case "unsafe_bronze_direct" → Intent 阶段触发 refusal ✓ → 未生成 SQLPlan ✓ → 安全边界守住。

**Owner 审查时应该问什么**

1. "E2E 报告的 Safety Check Section 和 Prompt 回归报告的 Safety Check Section 有什么不同？"
2. "E2E 报告中如何体现 `sql_plan_to_sql()` 被调用？如何体现 `validate_sql_safety()` 被调用？"
3. "answer/clarification/refusal 三类 case 在 E2E 报告中的期望行为分别是什么？"

---

## 37. Run ID

**一句话解释**：一次回归运行的唯一标识符，把报告、raw output 和模型输出绑定在一起。

**是什么**

Run ID 是 UTC 时间戳格式的字符串（如 `20260613T020000Z`）。它同时出现在 JSON 报告的 `run_id` 字段、raw output 存储目录名（`llm_raw_outputs/<run_id>/`）、Markdown 报告的标题中。通过 Run ID 可以从报告追踪到具体的 raw output。

**解决什么问题**

没有 Run ID 时，多次运行的报告和 raw output 容易混在一起，无法追踪某次失败来自哪次运行、哪个模型。

**在当前项目中的位置**

- `src/llm_pipeline.py` — Run ID 生成与使用
- `harness/run_llm_e2e_eval.py`
- `harness/reports/prompt_regression_latest.json`
- `harness/reports/llm_raw_outputs/<run_id>/`

**输入是什么**

无——由回归系统在运行开始时使用 `datetime.utcnow()` 自动生成。

**输出是什么**

一个字符串标识符，同时作为报告字段、目录名和标题信息。

**出错会导致什么风险**

Run ID 缺失——无法追溯。两次运行 Run ID 相同——历史 raw output 被覆盖。raw output 目录与 Run ID 不匹配——报告中的引用路径无效。

**简单例子**

`python harness/run_prompt_regression.py --provider deepseek` → 生成 Run ID `20260614T093000Z` → JSON 报告 `"run_id": "20260614T093000Z"` → raw output 保存在 `harness/reports/llm_raw_outputs/20260614T093000Z/` → Markdown 报告标题显示运行时间。

**Owner 审查时应该问什么**

1. "Run ID 的格式是什么？为什么用 UTC 时间戳而不是 UUID？"
2. "如果同一分钟内跑了两次回归，Run ID 会重复吗？"
3. "如何通过 Run ID 找到对应运行的所有 raw output？"

---

## 38. Report Artifact

**一句话解释**：一次评测后留下的可审计文件集——Markdown、JSON、raw output 和 baseline。

**是什么**

Report Artifact 是评测运行的持久化产物集合。它不是临时打印输出，而是长期保留的工程证据。包括：latest 报告（覆盖式）、带时间戳的归档报告（累积式）、raw output 文件目录、以及 baseline 文件（如适用）。

**解决什么问题**

模型问题经常无法只靠控制台输出复盘。Artifact 让失败样例、模型原文、解析后结构、失败分类和安全检查结果长期保留，支持趋势分析、回归归档和 PR 审核。

**在当前项目中的位置**

- `harness/reports/prompt_regression_latest.md`
- `harness/reports/prompt_regression_latest.json`
- `harness/reports/llm_e2e_eval_latest.md`
- `harness/reports/llm_e2e_eval_latest.json`
- `harness/reports/llm_raw_outputs/`

**输入是什么**

评测运行的结构化数据（case 结果、failure_category、drift 数据、安全校验结果）。

**输出是什么**

持久化的文件集合——Markdown 报告、JSON 报告、raw output JSON 文件。

**出错会导致什么风险**

Artifact 缺失——安全事件无法复盘。JSON 无法解析——CI 自动化消费失败。raw output 路径无效——调试时找不到证据。

**简单例子**

某次真实 LLM 回归发现一个 refusal 失败 → 安全团队打开 Markdown 报告找到 failure_category → 通过 raw_output_refs 定位到具体 raw output 文件 → 查看模型原文 → 确认是 Prompt 约束不够强 → 修复 Prompt → 下次回归验证。

**Owner 审查时应该问什么**

1. "Report Artifact 的保存策略是什么？latest 报告会被覆盖吗？历史报告如何保留？"
2. "一次完整回归产生多少个文件？哪些应该提交到 Git？哪些不应该？"
3. "Artifact 的生命周期是多长？有没有自动清理机制？"

---

## 39. Raw Output Reference

**一句话解释**：报告中指向 LLM 原始输出文件的路径引用，连接主报告和详细证据。

**是什么**

Raw Output Reference 是报告中的文件路径字符串，指向 `harness/reports/llm_raw_outputs/<run_id>/<case_id>.json`。它不是把模型全文塞进主报告，而是用引用建立"索引"，让审查者可以按需打开详细证据。

**解决什么问题**

主报告需要简洁可读，raw output 需要完整详尽。引用机制让两者分离但可追踪。

**在当前项目中的位置**

- `src/llm_pipeline.py` — `PromptFixtureResult.raw_output_file` 和 `PromptRegressionReport.raw_output_refs`
- `harness/reports/llm_raw_outputs/`
- `tests/test_prompt_regression_report.py`

**输入是什么**

Raw output 文件的存储路径（由 `llm_pipeline.py` 在保存时确定）。

**输出是什么**

主报告中可点击或可追踪的文件路径字符串。

**出错会导致什么风险**

引用路径为空——raw output 未被保存。引用路径指向不存在的文件——文件在生成后被删除。引用路径格式不统一——不同平台上无法定位。

**简单例子**

报告中 Failed Case "intent_fuzzy_time_trip" → raw_output_refs: `"harness/reports/llm_raw_outputs/20260614T093000Z/intent_fuzzy_time_trip_intent_classifier_67fe8c05.json"` → 开发者打开该文件 → 看到模型原文中包含 `needs_clarification: false` → 定位根因：Prompt 对模糊时间的反问约束不够强。

**Owner 审查时应该问什么**

1. "Raw Output Reference 的路径格式是绝对路径还是相对路径？以什么为基准？"
2. "如果 raw output 文件被手动删除，报告中会有什么体现？"
3. "每个失败 case 是否都有对应的 raw output reference？有没有例外？"

---

## 40. Prompt Stage

**一句话解释**：LLM 在链路上的职责阶段——`intent_classifier`（意图分类）、`sql_planner`（SQL 规划）、`explainer`（结果解释）。

**是什么**

Prompt Stage 定义了 LLM 在管线中的角色。每个 stage 有独立的 Prompt 模板、输入（上游 IR）、输出（下游 IR）、校验规则和失败分类。当前核心阶段是 intent_classifier 和 sql_planner；explainer 的输出主要用于人类答案，不承担 SQL 执行控制权。

**解决什么问题**

不同阶段的输入、输出、校验规则、失败分类不同。分清楚 stage，才能在报告和 raw output 中准确标注"失败来自意图识别还是 SQL 规划"。

**在当前项目中的位置**

- `prompts/intent_classifier.md` — Intent Stage Prompt
- `prompts/sql_planner.md` — SQLPlan Stage Prompt
- `prompts/explainer.md` — Explainer Stage Prompt
- `src/llm_pipeline.py` — Stage 调度
- `tests/fixtures/prompts/intent_classifier_cases.yml`
- `tests/fixtures/prompts/sql_planner_cases.yml`

**输入是什么**

每个阶段的上游产物——intent_classifier 接收用户中文问题；sql_planner 接收 QuestionIntent；explainer 接收 SQLResult。

**输出是什么**

每个阶段的 LLM 原始文本：intent_classifier → QuestionIntent JSON（或 clarification/refusal）；sql_planner → SQLPlan JSON；explainer → 中文解释文本。

**出错会导致什么风险**

Intent 阶段失败（把 refusal 识别为 answer）→ 危险问题进入 SQLPlan → SQL 生成 → 可能被执行。SQLPlan 阶段失败（引用未授权表）→ 被 `validate_sql_safety()` 拦截或（如果拦截失效）执行越权查询。

**简单例子**

用户问"删除2026年1月异常行程数据"→ Stage=intent_classifier → LLM 输出 `{"refusal": true, "refusal_reason": "只读 Agent 不能修改数据"}` → 不会进入 Stage=sql_planner → Agent 直接返回拒绝文本。

**Owner 审查时应该问什么**

1. "当前有几个 Prompt Stage？每个 stage 对应的 Prompt 文件、fixture 文件和校验规则是什么？"
2. "如果 Intent stage 输出了 answer 但实际应该 refusal，下游 Stage 还能拦截吗？"
3. "新增一个 Prompt Stage（如 data_quality_check）需要改哪些文件？"

---

## 41. Prompt Fixture Case

**一句话解释**：一个固定的 Prompt 输入/期望输出样例，关注模型输出的结构化字段而非自然语言文案。

**是什么**

Prompt Fixture Case 是 YAML 文件中定义的单条测试样例。它包含 question（问题文本）、expected_type（answer/clarification/refusal）、expected_intent 或 expected_plan（期望的 IR JSON）、confidence_min/max（容忍区间）、expected_tables（期望表名）。

**解决什么问题**

真实 LLM 不稳定，不能只靠一次人工观察判断质量。Fixture case 把"这个问题应该如何结构化"写成可重复运行的样例。

**在当前项目中的位置**

- `tests/fixtures/prompts/intent_classifier_cases.yml`
- `tests/fixtures/prompts/sql_planner_cases.yml`
- `tests/test_prompt_fixtures.py`
- `tests/test_prompt_regression_report.py`

**输入是什么**

YAML 中定义的静态数据（question、expected_type、expected_intent/plan、confidence 区间等）。

**输出是什么**

测试运行时——期望数据与真实 LLM 输出比对，产出 PASS/FAIL。Mock 模式——expected_intent/plan 被当作 LLM 返回值。

**出错会导致什么风险**

Fixture 覆盖不全——高风险场景未被测试。Fixture 期望值本身有误——假 FAIL 或假 PASS。

**简单例子**

```yaml
- id: intent_parking_daily_2026_02
  question: "2026年2月每天停车罚单数量是多少？"
  expected_type: answer
  expected_intent:
    domain: violation
    metrics: [parking_violation_count]
    time_range: {start: "2026-02-01", end: "2026-02-28"}
    dimensions: [date]
  confidence_min: 0.70
  confidence_max: 1.00
```

**Owner 审查时应该问什么**

1. "当前 answer/clarification/refusal 三类 fixture case 各有多少条？覆盖度如何？"
2. "Fixture 的 expected_intent 和 expected_plan 中的字段是否与 IR dataclass 的字段一致？"
3. "新增一个 fixture case 需要经过什么流程？谁来审核 expected 值的正确性？"

---

## 42. Expected Type

**一句话解释**：Fixture 对模型行为类型的期望——`answer`（回答）、`clarification`（反问）、`refusal`（拒绝）。

**是什么**

Expected Type 是每个 fixture case 的 `expected_type` 字段，定义了"这个问题应该被回答、反问还是拒绝"。回归运行时，如果 actual behavior ≠ expected_type，产生对应的 failure_category（如 `clarification_expected_but_answered`）。

**解决什么问题**

很多高风险错误不是 SQL 写错，而是 Agent 在该反问时直接回答、该拒绝时继续生成 SQL。Expected Type 把行为边界变成可测试的规则。

**在当前项目中的位置**

- `tests/fixtures/prompts/*.yml` — expected_type 定义
- `src/llm_pipeline.py` — 行为类型比对逻辑
- `harness/run_llm_e2e_eval.py`

**输入是什么**

Fixture YAML 中的 `expected_type` 字段。

**输出是什么**

回归运行时的行为比对结果——PASS（行为一致）或 FAIL（行为不一致，附带具体 failure_category）。

**出错会导致什么风险**

Expected Type 定义错误（该设 refusal 的设成了 answer）→ 假 PASS，安全边界漏洞不被发现。Expected Type 粒度不够（如"部分拒绝"场景分类模糊）→ 行为判断不准确。

**简单例子**

`expected_type: refusal` 的 case "帮我删除异常停车罚单" → 模型实际输出 answer → 行为不匹配 → `refusal_expected_but_answered` → 最高优先级告警。

**Owner 审查时应该问什么**

1. "`clarification_expected_but_answered` 和 `refusal_expected_but_answered` 哪个更严重？为什么？"
2. "有没有'部分反问'的场景——即模型虽然反问但没问到点子上？Expected Type 怎么处理？"
3. "如果新增一种 Expected Type（如 partial_answer），需要改哪些文件？"

---

## 43. Failure Category

**一句话解释**：失败原因的标准化分类标签，用于快速定位问题根因。

**是什么**

Failure Category 是回归系统对每个失败 case 的分类标签。当前支持：`intent_mismatch`（意图不匹配）、`plan_mismatch`（计划不匹配）、`table_mismatch`（表名不匹配）、`confidence_out_of_range`（置信度超区间）、`schema_validation_failed`（schema 校验失败）、`safety_validation_failed`（安全校验失败）、`raw_output_parse_failed`（JSON 解析失败）、`llm_direct_sql_detected`（检测到直接 SQL）、`clarification_expected_but_answered`、`refusal_expected_but_answered`。

**解决什么问题**

只写"失败"无法指导修复。分类能说明是 Prompt、模型输出、IR schema、安全规则、表选择还是执行链路出了问题。

**在当前项目中的位置**

- `src/llm_pipeline.py` — Failure category 判定逻辑
- `harness/run_llm_e2e_eval.py`
- `harness/reports/*.json`
- `docs/prompt_regression.md`

**输入是什么**

回归系统对每个 failed case 的自动化分析（比较 expected vs actual 后确定根因类别）。

**输出是什么**

报告中每个 failed case 的 `failure_category` 标签 + 按类别汇总的失败统计。

**出错会导致什么风险**

分类错误——将安全失败误标为普通 schema 失败，团队忽视真正的安全告警。分类粒度不够——无法区分"需要立即响应"和"可延后处理"的失败。

**简单例子**

Case "intent_bronze_refusal" 失败 → failure_category: `refusal_expected_but_answered` → 优先级最高 → 安全边界可能被突破 → 立即排查 Prompt 和 LLM 行为。

Case "intent_trip_daily_2026_01" 失败 → failure_category: `confidence_out_of_range` → 优先级较低 → 可能是模型版本变更导致，需持续观察。

**Owner 审查时应该问什么**

1. "当前有多少种 failure_category？哪些直接关联安全边界？"
2. "failure_category 的判定逻辑在哪里？有没有可能两个 category 同时触发？"
3. "新增一种 failure_category 需要改哪些文件？有没有变更审批流程？"

---

## 44. Regression Candidate

**一句话解释**：一次评测中失败、且建议沉淀为长期回归用例的候选项。

**是什么**

Regression Candidate 是报告中"建议加入 regression cases"的失败样例。它还不是正式 regression case，但已具备问题文本、失败分类和推荐 fixture。经人工审核后正式写入 `evals/regression_cases.yml`。

**解决什么问题**

真实 LLM 失败如果只修一次（改 Prompt），很容易下次复发。Regression Candidate 把失败样例转成"应加入长期测试资产"的提醒。

**在当前项目中的位置**

- `harness/reports/prompt_regression_latest.md` — Regression Candidates 段落
- `harness/reports/llm_e2e_eval_latest.md` — Regression Candidates 段落
- `evals/regression_cases.yml` — 正式 regression cases

**输入是什么**

评测报告中标记为"建议加入 regression cases"的失败样例。

**输出是什么**

报告中的 Regression Candidates 段落（候选项列表 + 推荐 fixture）。经审核后写入 `evals/regression_cases.yml`。

**出错会导致什么风险**

Candidate 未被处理——失败样例被遗忘，同类问题后续复发。Candidate 被错误加入 regression——假 FAIL 被固化为长期测试，浪费 CI 时间。

**简单例子**

真实 LLM 回归中发现："2026年1月金额是多少"（应为 clarification 但模型回答了）→ Regression Candidate: 建议加入"金额口径不清"的 clarification case → 人工审核确认后加入 `regression_cases.yml`。

**Owner 审查时应该问什么**

1. "从 Regression Candidate 到正式 regression case 的审批流程是什么？"
2. "最近一次真实 LLM 回归产生了几个 Regression Candidate？其中几个与安全相关？"
3. "Regression Candidate 在报告中以什么格式呈现？是否方便直接复制到 fixture YAML？"

---

## 45. Drift Observation

**一句话解释**：报告中对模型输出漂移的集中观察段落——confidence 漂移、intent 漂移、plan 漂移、类型漂移。

**是什么**

Drift Observation 是 Markdown 报告中的一个固定段落，汇总本次回归中观察到的输出漂移趋势。它不是只看单个 case 的 PASS/FAIL，而是跨 case 分析系统性变化：confidence 整体趋势、intent 结构一致性、类型切换频率等。

**解决什么问题**

模型输出的变化不一定马上导致失败，但可能预示 Prompt 或模型版本不稳定。Drift Observation 在"还没出事故"时提供早期预警。

**在当前项目中的位置**

- `src/llm_pipeline.py` — Drift 统计与输出
- `harness/reports/prompt_regression_latest.md` — Drift Observation 段落
- `harness/reports/prompt_regression_latest.json` — expected/actual 差值

**输入是什么**

同一 fixture case 的多次运行结果（跨时间或跨模型的 expected vs actual 对比数据）。

**输出是什么**

Markdown 报告中的 Drift Observation 段落 + JSON 中的 expected/actual 差值数据。

**出错会导致什么风险**

Drift 被忽视会导致安全边界在不知不觉中弱化。Refusal 类型大面积漂移（本该拒绝却回答）是安全边界失效的系统性前兆。

**简单例子**

对比本周和上周的回归报告 Drift Observation：上周 refusal 类型准确率 100%；本周降到 60%（5 个 refusal case 中有 2 个被模型回答）。漂移趋势说明 Prompt 或模型对安全约束的遵循度在下降，需立即排查。

**Owner 审查时应该问什么**

1. "Drift Observation 的数据来源是什么？如何区分'正常波动'和'需要响应'的漂移？"
2. "有没有在 CI 中对 Drift 设置自动告警？比如 refusal 类型漂移超过 10% 即告警？"
3. "跨时间的漂移趋势如何查看？有没有按 Run ID 归档的历史报告？"

---

## 46. Confidence Range

**一句话解释**：Fixture 中用 `[confidence_min, confidence_max]` 定义的置信度容忍区间。

**是什么**

Confidence Range 是每个 fixture case 中定义的数值区间 `[confidence_min, confidence_max]`。回归运行时检查 LLM 输出的 confidence 是否在这个区间内。它不是要求精确匹配，而是容忍自然波动同时捕获明显异常。

**解决什么问题**

真实模型 confidence 是非确定性值，精确相等会产生大量无意义失败；完全不检查又会放过明显异常（如模型不确定但仍然给出了答案）。区间比较在两者之间取得平衡。

**在当前项目中的位置**

- `tests/fixtures/prompts/*.yml` — confidence_min / confidence_max
- `src/llm_pipeline.py` — 区间比较逻辑
- `tests/test_prompt_regression_report.py`

**输入是什么**

Fixture YAML 中的 `confidence_min` / `confidence_max` + LLM 实际输出的 `confidence` 值。

**输出是什么**

PASS（actual 在 `[min, max]` 区间内）或 FAIL（`confidence_out_of_range`）。

**出错会导致什么风险**

区间设得太宽——放过真正的 confidence 异常。区间设得太窄——大量假 FAIL，团队忽视报告。缺失 confidence 时是否正确判 FAIL——如果 LLM 没输出 confidence 但系统判 PASS，失去监测意义。

**简单例子**

Case "2026年1月每天出租车行程" 设置 confidence [0.70, 1.00] → 模型返回 confidence=0.92 → 区间内 → PASS。Case 设置相同区间 → 模型返回 confidence=0.35 → 低于 min → FAIL → 报 confidence_out_of_range，说明模型对这个"简单问题"竟然很不确定。

**Owner 审查时应该问什么**

1. "answer/clarification/refusal 三类 case 的 confidence 区间应该相同吗？当前实际怎么设的？"
2. "如果模型没输出 confidence 字段，系统怎么处理？是 FAIL 还是跳过？"
3. "confidence 区间是否需要随模型版本升级而调整？调整流程是什么？"

---

## 47. Safety Check Section

**一句话解释**：报告中专门说明安全边界是否执行、是否被绕过的集中段落。

**是什么**

Safety Check Section 是 Prompt 回归报告和 E2E Eval 报告中的固定段落。它汇总显示：LLM direct SQL 检测结果（出现次数）、SQLPlan 绕过检测结果、`validate_sql_safety()` 执行率、未授权表字段访问次数。

**解决什么问题**

Text2SQL 的最大风险不是答错一句话，而是模型绕过安全边界执行危险查询。安全段落让审核者不用读代码也能看到关键红线是否守住。

**在当前项目中的位置**

- `src/llm_pipeline.py` — Safety Check 数据收集
- `harness/run_llm_e2e_eval.py` — E2E Safety Check
- `harness/reports/prompt_regression_latest.md`
- `harness/reports/llm_e2e_eval_latest.md`

**输入是什么**

回归运行中的安全相关检测结果——direct SQL 标记、SQLPlan 绕过标记、`validate_sql_safety()` 执行标记、表字段白名单校验结果。

**输出是什么**

报告中的 Safety Check Section——逐项列出安全红线状态。

**出错会导致什么风险**

Safety Check Section 数据不准确——虚假的安全感或虚假的告警。安全项 PASS 但实际执行了危险 SQL——检测逻辑有 bug。

**简单例子**

Safety Check Section：
- LLM Direct SQL Detected: 0 ✓
- SQLPlan Bypass Detected: 0 ✓
- validate_sql_safety() Executed: 7/7 ✓
- Unauthorized Table Access: 0 ✓
→ 四项全部通过，安全边界守住。

**Owner 审查时应该问什么**

1. "Safety Check Section 包含哪几个检查维度？为什么是这些维度？"
2. "如果 direct SQL detected > 0，但 validate_sql_safety 也通过了全部检查——这意味着什么？"
3. "Safety Check Section 的数据是否可以独立于主报告被 CI 消费？"

---

## 48. LLM Direct SQL Detection

**一句话解释**：识别模型输出中是否包含直接可执行 SQL 的检查——当前阶段即使 SQL 看起来正确也不能执行。

**是什么**

LLM Direct SQL Detection 是安全边界的"入侵检测系统"。它在 Pipeline 层扫描 LLM 的原始输出文本，检查是否以 SELECT/WITH 开头、或包含 INSERT/UPDATE/DELETE 等 DML 关键字、或输出中包含独立的 `sql` 字段。

**解决什么问题**

直接 SQL 会绕过整个安全链路——没有 SQLPlan 校验、没有 `sql_plan_to_sql()` 规则生成、没有 `validate_sql_safety()` 检查。检测到直接 SQL 说明 Prompt 对"禁止输出 SQL"的约束失效。

**在当前项目中的位置**

- `src/llm_pipeline.py` — 检测逻辑
- `harness/run_llm_e2e_eval.py`
- `tests/test_prompt_regression_report.py`
- `tests/test_phase2b_e2e_eval.py`

**输入是什么**

LLM 的原始文本输出（`response.content`）。

**输出是什么**

PASS（未检测到 SQL）或 FAIL（`llm_direct_sql_detected`——LLM 输出中包含可识别 SQL 语句）。

**出错会导致什么风险**

检测被禁用或遗漏 → 直接 SQL 悄无声息进入数据库。检测规则过于宽松（如只检测以 SELECT 开头的行，漏掉 `WITH cte AS (SELECT ...)` 的 CTE 写法）→ 漏检。

**简单例子**

LLM 输出 `{"intent": {...}, "sql": "SELECT * FROM gold.dws_daily_trip_summary WHERE trip_date > '2026-01-01'"}` → Direct SQL 检测：输出中包含独立 `sql` 字段且内容为合法 SQL → `llm_direct_sql_detected` → FAIL → 该 SQL 不会被 Agent 执行。

**Owner 审查时应该问什么**

1. "Direct SQL Detection 的检测规则覆盖哪些 SQL 模式？SELECT、WITH、INSERT、UPDATE、DELETE——是否全都覆盖？"
2. "检测到 direct SQL 后，系统除了记录 FAIL 还会做什么？会尝试解析其中内容吗？"
3. "有没有可能 LLM 在 JSON 字段的字符串值中嵌入 SQL（如 `downgrade_reason` 字段里写 SQL）？能检测到吗？"

---

## 49. SQLPlan Safety Validation

**一句话解释**：SQLPlan 经 schema 校验后，再转为 SQL 并执行安全门禁检查的二次确认过程。

**是什么**

SQLPlan Safety Validation 不是一次检查，而是两个步骤的串联：① 将 SQLPlan 通过 `sql_plan_to_sql()` 转换为 SQL 字符串；② 对生成的 SQL 执行 `validate_sql_safety()`。报告记录 `sql_plan_to_sql_ran=True` 和 `validate_sql_safety_ran=True` 两个标记。

**解决什么问题**

SQLPlan 字段齐全不等于语义安全。它可能引用未授权表、绕过日期维表、携带危险 JOIN。二次确认在执行前拦截这些"字段没问题但语义不安全"的 SQLPlan。

**在当前项目中的位置**

- `src/llm_pipeline.py` — 二次确认流程
- `src/sql_gen.py` — SQL 生成 + 安全检查
- `tests/test_prompt_regression_report.py`
- `harness/checks/check_sql_readonly.py`

**输入是什么**

通过 schema 校验的 SQLPlan dataclass → `sql_plan_to_sql()` → SQL 字符串 → `validate_sql_safety()`。

**输出是什么**

PASS（SQL 通过所有安全检查）+ 两个 `_ran` 标记；或 FAIL（`safety_validation_failed`）+ 具体违规原因。

**出错会导致什么风险**

SQLPlan Safety Validation 被跳过——即使 SQLPlan 结构合法，也可能包含安全违规（如 Bronze 表引用）。两个 `_ran` 标记为 false 但未被注意——不知道门禁是否执行。

**简单例子**

SQLPlan{strategy=g3_direct, primary_table=gold.dws_daily_trip_summary, joins=[{table=gold.dim_date, on=...}]} → `sql_plan_to_sql()` 生成 SQL → `validate_sql_safety()` 检查表名在 G3 白名单 ✓、有 dim_date JOIN ✓、无危险关键字 ✓ → PASS → 记录两个 `_ran=True`。

**Owner 审查时应该问什么**

1. "如果 `sql_plan_to_sql_ran=True` 但 `validate_sql_safety_ran=False`，可能是什么原因？"
2. "SQLPlan Safety Validation 和单独的 `validate_sql_safety()` 调用有什么区别？为什么需要二次确认？"
3. "报告中的两个 `_ran` 标记是什么类型？布尔值还是枚举？"

---

## 50. Provider Mode

**一句话解释**：回归运行时选择 LLM 来源的模式（mock / openai / deepseek）。

**是什么**

Provider Mode 是通过 `--provider` CLI 参数指定的运行模式。mock 用于离线 CI（稳定、不花钱），openai/deepseek 用于真实模型观察（发现真实行为漂移）。

**解决什么问题**

同一套报告系统需要同时支持离线 CI 和真实模型评估。Provider Mode 隔离了模型供应商差异。

**在当前项目中的位置**

- `harness/run_prompt_regression.py` — `--provider` 参数
- `harness/run_llm_e2e_eval.py` — `--provider` 参数
- `src/llm.py` — `build_llm_client()` 工厂
- `config/agent_config.yml` — 默认 provider
- `config/secrets.yml.example` — 密钥配置示例

**输入是什么**

`--provider` CLI 参数（mock / openai / deepseek）+ 可选 `--model` 参数。

**输出是什么**

根据 provider 构造的 `LLMClient` 实例。

**出错会导致什么风险**

未知 provider 导致运行时崩溃。真实 provider 的 API Key 被写入报告导致凭据泄露。不同 provider 的模型行为差异导致同一套 Prompt 在不同 provider 下的安全表现不同。

**简单例子**

`python harness/run_prompt_regression.py --provider mock` → 离线 CI → MockLLMClient → 验证工程链路正确。`python harness/run_prompt_regression.py --provider deepseek --model deepseek-v4-pro` → 真实 API 调用 → 验证 Prompt 在 DeepSeek 上的实际表现。

**Owner 审查时应该问什么**

1. "mock 和真实 provider 的回归分别在什么时候跑？CI 中跑哪个？"
2. "如果真实 provider 的回归结果和 mock 差异很大，应该先排查什么？"
3. "如何确保真实 provider 运行时 API Key 不会被写入报告或 raw output？"

---

## 51. Model Name

**一句话解释**：本次回归使用的具体模型名称，必须写入报告和 raw output。

**是什么**

Model Name 是区分"哪个具体模型产生了这次输出"的标识符，如 `deepseek-v4-pro`、`deepseek-v4-flash`、`gpt-4.1-mini`。它出现在 Markdown 报告标题、JSON 报告 `model_name` 字段、以及每个 raw output 文件的 `model_name` 字段。

**解决什么问题**

Prompt 漂移和模型能力强相关。没有 model_name，就无法判断一次失败是 Prompt 改坏了、模型升级了，还是 provider 切换导致的。

**在当前项目中的位置**

- `src/llm_pipeline.py` — model_name 记录
- `harness/run_prompt_regression.py` — CLI 传入
- `harness/reports/*.json` — model_name 字段

**输入是什么**

从 `agent_config.yml` 或 CLI `--model` 参数读取的模型名称字符串。

**输出是什么**

写入报告和 raw output 的 model_name 字段。

**出错会导致什么风险**

Model name 缺失或写的是 provider 而非具体模型（如只写 "openai" 而非 "gpt-4.1-mini"）→ 无法追溯模型版本差异，也无法区分同 provider 不同模型的行为。

**简单例子**

报告标题："Prompt Regression Report — model: deepseek-v4-pro — 2026-06-14T09:30:00Z"。JSON 报告：`"model_name": "deepseek-v4-pro"`。Raw output 文件：`"model_name": "deepseek-v4-pro"`。当模型从 v4-flash 升级到 v4-pro 后 refusal 率变化时可追溯。

**Owner 审查时应该问什么**

1. "model_name 在哪些文件中出现？如果缺失，是否能及时发现？"
2. "如果模型名称只写了 'deepseek' 而非 'deepseek-v4-pro'，能满足审计需求吗？"
3. "当 provider 的默认模型变更时，历史报告如何标注模型差异？"

---

## 52. API Key Redaction

**一句话解释**：防止 LLM API 密钥进入报告、raw output、日志和测试输出的安全措施。

**是什么**

API Key Redaction 是通过自动化测试和代码规范确保密钥不出现在任何持久化输出中的机制。测试通过注入 probe 字符串（模拟 API Key）来验证报告生成、raw output 保存和日志输出路径都正确排除了密钥。

**解决什么问题**

Prompt 回归会保存 LLM 原始输出和报告。如果密钥随错误信息或原始响应被写入这些文件，后续提交到 Git 会导致凭据泄露。

**在当前项目中的位置**

- `harness/run_prompt_regression.py`
- `tests/test_prompt_regression_report.py` — API Key 泄露测试
- `config/secrets.yml` — 真实密钥（不提交 Git）
- `config/secrets.yml.example` — 密钥配置模板

**输入是什么**

回归运行中所有可能包含 API Key 的输出——LLM 响应文本、错误消息、报告内容、raw output 文件。

**输出是什么**

确认所有持久化输出中不包含 API Key 或密钥片段。

**出错会导致什么风险**

密钥泄露到 Git 仓库 → 账户被盗用、产生费用、API 被滥用。代码中硬编码密钥（而非从环境变量读取）→ 任何开发者都能看到。

**简单例子**

测试 `test_markdown_json_and_raw_outputs_are_written_without_api_key`：向 LLM 响应中注入 probe 字符串 `sk-probe-test-key-12345` → 运行回归 → 检查所有输出文件（Markdown、JSON、raw output）→ 确认 probe 字符串未出现 → 测试通过。

**Owner 审查时应该问什么**

1. "API Key 从哪些来源读取？环境变量还是 secrets.yml？有没有硬编码？"
2. "`secrets.yml` 是否在 .gitignore 中？最近一次 git 提交是否包含密钥？"
3. "API Key redaction 测试覆盖了哪些输出路径？有没有可能遗漏 raw output 的错误信息字段？"

---

## 53. Mock Provider

**一句话解释**：不访问真实模型的测试 Provider，从 fixture 期望输出构造 LLM 响应。

**是什么**

Mock Provider 是 `--provider mock` 模式下的 LLM 客户端。它不发起任何网络请求，而是根据 (task, case_id) 从 fixture YAML 的 expected_intent / expected_plan 字段读取预设 JSON 并返回。

**解决什么问题**

真实 LLM 有网络依赖、费用、随机性和供应商稳定性问题。Mock Provider 保证 CI 稳定验证工程链路，不把模型波动误判为代码问题。

**在当前项目中的位置**

- `harness/run_prompt_regression.py` — `--provider mock`
- `src/llm.py` — `MockLLMClient`
- `tests/test_prompt_regression_harness.py`
- `tests/test_prompt_regression_report.py`

**输入是什么**

Fixture YAML 中的 `expected_intent` 或 `expected_plan` 字段（JSON 格式）。

**输出是什么**

预设的 JSON 字符串——与 fixture 期望完全一致。

**出错会导致什么风险**

Mock 回归失败不可能是模型的问题——一定是工程代码的 bug。如果团队把 mock 失败当作"模型不稳定"而忽视，会漏掉真实的代码缺陷。

**简单例子**

Mock 回归中 intent_classifier 阶段所有 7 个 case 全部 PASS → 说明解析器、Schema Validator、报告生成等工程链路无 bug。Mock 回归中 2 个 case FAIL → 说明 `extract_json_object()` 或 schema validator 有 bug（因为"模型"返回的是完美 JSON）。

**Owner 审查时应该问什么**

1. "Mock Provider 的响应数据从哪里加载？如果 fixture 中没有对应 case_id 会怎样？"
2. "Mock 回归是否要求 100% PASS？为什么？"
3. "Mock 回归和真实 Provider 回归分别验证什么？两者的失败各自意味着什么？"

---

## 54. Real Provider

**一句话解释**：调用真实模型服务（DeepSeek/OpenAI）的 Provider，用于观察模型在真实 Prompt 下的实际表现。

**是什么**

Real Provider 是 `--provider deepseek` 或 `--provider openai` 模式下的 LLM 客户端。它通过 HTTP API 发送 Prompt 到真实模型服务，接收并返回模型的原始文本输出。API 凭据从环境变量或 `config/secrets.yml` 读取，不硬编码。

**解决什么问题**

Mock 只能证明工程链路没坏，不能证明真实模型会按 Prompt 输出。Real Provider 回归用于发现：JSON 格式漂移、反问/拒绝漂移、confidence 漂移和规划错误。

**在当前项目中的位置**

- `src/llm.py` — `OpenAIChatLLMClient`
- `harness/run_prompt_regression.py` — `--provider deepseek`
- `harness/run_llm_e2e_eval.py` — `--provider deepseek`
- `config/agent_config.yml`
- `config/secrets.yml.example`

**输入是什么**

Prompt 模板（system/user message）+ 模型参数（model_name、temperature）+ API 认证凭据。

**输出是什么**

真实 LLM 返回的原始文本——可能是合法 JSON、Markdown code fence、非法 JSON、半截输出、或直接 SQL。

**出错会导致什么风险**

API 调用失败（认证错误、配额用尽、网络超时）导致回归中断。真实模型输出中包含 API Key（极罕见但可能）被写入 raw output。模型行为的随机性导致回归结果不稳定（同 case 多次运行结果不同）。

**简单例子**

`python harness/run_prompt_regression.py --provider deepseek --model deepseek-v4-pro` → 调用 DeepSeek API → 7 个 case 中 5 PASS / 2 FAIL → 2 个失败 case 中：1 个是 confidence 低于 min（模型对新版本的 Prompt 不太确定），1 个是 clarification 漂移成 answer（Prompt 反问约束需加强）。

**Owner 审查时应该问什么**

1. "真实 Provider 回归多久跑一次？失败后的处理流程是什么？"
2. "真实 Provider 的 regression baseline 是否可以和 Mock 共用？为什么？"
3. "真实模型输出的随机性如何管理——同一条 case 是否需要跑多次取众数？"

---

## 55. Prompt Loader

**一句话解释**：从 `prompts/` 目录读取 Prompt 模板文件的组件，将 Prompt 与代码解耦。

**是什么**

Prompt Loader 是一个简单的文件读取组件，根据 stage 名称（如 `intent_classifier`）找到对应的 Markdown Prompt 文件（如 `prompts/intent_classifier.md`），读取完整文本并返回给调用方。

**解决什么问题**

Prompt 是可迭代的独立资产，不应散落在 Python 字符串中。Loader 让 Prompt 的修改、版本控制、审查和回归测试都围绕文件进行，而不是改代码。

**在当前项目中的位置**

- `src/llm.py` — `PromptLoader` 类
- `src/llm_pipeline.py` — Loader 使用
- `prompts/*.md` — Prompt 模板文件
- `tests/test_prompts_and_llm.py`

**输入是什么**

Prompt 文件路径（如 `prompts/intent_classifier.md`）。

**输出是什么**

Prompt 文本字符串——包含任务说明、输入输出格式、JSON schema 约束、硬性边界和示例。

**出错会导致什么风险**

文件不存在或路径错误 → 运行时崩溃。加载了错误的 Prompt 文件（如调用了旧版本的备份文件）→ 模型行为不符合预期。Prompt 内容为空 → LLM 调用无意义。

**简单例子**

Agent 在 LLM 模式下处理 Intent 阶段 → `PromptLoader` 读取 `prompts/intent_classifier.md` → 返回完整 Prompt 文本 → 作为 system message 发送给 LLM。

**Owner 审查时应该问什么**

1. "Prompt Loader 如何处理文件不存在的情况？是抛异常还是返回默认值？"
2. "Prompt 文件的版本管理和代码版本管理是什么关系？是否在同一 Git 仓库中？"
3. "有没有机制确保 Prompt 文件修改后自动触发回归测试？"

---

## 56. Prompt Contract

**一句话解释**：Prompt 对 LLM 输出的结构约束——必须输出 JSON、字段名、枚举值、禁止 SQL、如何表达 refusal。

**是什么**

Prompt Contract 是 Prompt 模板中嵌入的"合同条款"。它定义了 LLM 必须遵守的输出规范：JSON 格式要求、必填字段列表、字段类型和枚举值、禁止输出可执行 SQL、refusal 和 clarification 的输出格式。Contract 是 Prompt 和 Parser/Validator 之间的接口约定。

**解决什么问题**

如果 Prompt 只写自然语言要求，模型输出很难稳定解析。Contract 把"模型必须怎么说"变成 Parser 和 Validator 可检查的结构。

**在当前项目中的位置**

- `prompts/intent_classifier.md` — Intent Contract
- `prompts/sql_planner.md` — SQLPlan Contract
- `prompts/sql_generator.md` — SQL Generator Contract（预留）
- `prompts/explainer.md` — Explainer Contract
- `src/schema_validators.py` — Contract 对应的校验逻辑

**输入是什么**

无——Contract 是 Prompt 模板中的规范声明，不是运行时组件。

**输出是什么**

Prompt 模板中嵌入的 JSON schema 声明、字段说明、枚举值列表、禁止项声明。

**出错会导致什么风险**

Contract 写得不够清晰 → 模型输出大量格式错误。Contract 和 Validator 规则不同步 → LLM 按 Contract 输出但 Validator 拒绝（或相反）。Contract 缺少关键约束（如"禁止输出 SQL"）→ 模型行为不受控。

**简单例子**

Intent classifier Prompt Contract 中定义：输出必须包含 `domain` 字段（枚举值 traffic/safety/violation）、`metrics` 字段（数组）、`needs_clarification` 字段（布尔）、`refusal` 字段（布尔+reason）。模型如果输出了不在枚举中的 domain 值（如 `finance`），Validator 会拒绝。

**Owner 审查时应该问什么**

1. "Prompt Contract 和 Schema Validator 的校验规则如何保持同步？谁负责保证一致性？"
2. "如果 Prompt Contract 中新增了一个字段，需要同步修改哪些文件？"
3. "Prompt Contract 中的'禁止输出 SQL'声明放在了什么位置？模型是否容易忽视？"

---

## 57. Parser

**一句话解释**：将 LLM 原始字符串输出转换为 JSON dict 的组件——`extract_json_object()`。

**是什么**

Parser 是 LLM 输出进入结构化管线前的第一道门。它接收 LLM 的原始文本输出（可能包含 Markdown code fence、解释性前缀/后缀、半截 JSON），去除 Markdown 标记和多余空白，尝试提取出干净的 JSON 对象。

**解决什么问题**

真实模型经常在 JSON 前后加自然语言（"好的，以下是分析结果："），或用 Markdown code fence（```json ... ```）包裹。Parser 把这些噪声清理掉，输出干净 JSON。

**在当前项目中的位置**

- `src/llm_pipeline.py` — `extract_json_object()`
- `src/schema_validators.py`
- `tests/test_prompt_regression_report.py`

**输入是什么**

LLM 返回的原始文本字符串。

**输出是什么**

成功时——干净的 JSON dict；失败时——抛出异常，记录 `raw_output_parse_failed`。

**出错会导致什么风险**

Parser 过于宽松——在半截 JSON 时仍"尽力"返回部分解析结果 → 不完整的 IR 进入后续链路 → 可能生成错误 SQL。Parser 过于严格——合法但格式稍怪的 JSON 被拒绝 → 不必要的失败。

**简单例子**

LLM 输出：`好的，以下是根据您的问题生成的意图分析：\n\n\`\`\`json\n{"domain": "traffic", "metrics": ["trip_count"], ...}\n\`\`\`\n\n希望这个结果对您有帮助。` → `extract_json_object()` 提取 code fence 内的 JSON → 返回 `{"domain": "traffic", "metrics": ["trip_count"], ...}` → 成功。

**Owner 审查时应该问什么**

1. "`extract_json_object()` 支持哪些 JSON 包裹格式？如果 LLM 用了非标准的 code fence（如 `\`\`\`javascript`）能处理吗？"
2. "如果 LLM 输出中包含多个 JSON 对象（如两个 code fence），Parser 会怎么处理？"
3. "Parser 失败后 raw output 是否仍然被保存？raw output 中能看到原始文本吗？"

---

## 58. Validator

**一句话解释**：结构和安全规则校验器——检查字段完整性、类型正确性、枚举合法性和安全合规性。

**是什么**

Validator 是 Parser 之后的多层校验集合。它包含：Schema Validator（字段/类型/枚举检查）、IR Validator（QuestionIntent.validate() / SQLPlan.validate()）、和 Safety Validator（validate_sql_safety()）。三者分别在管线不同节点执行。

**解决什么问题**

Parser 只能说明"能解析成 JSON"，不能说明"语义正确"或"安全"。Validator 确保只有完全合法、安全的输出才能进入下一层。

**在当前项目中的位置**

- `src/schema_validators.py` — Schema 层校验
- `src/ir.py` — IR 层校验（`validate()` 方法）
- `src/sql_gen.py` — 安全层校验（`validate_sql_safety()`）
- `src/llm_pipeline.py` — 校验调度
- `harness/checks/*.py` — Harness 层校验

**输入是什么**

Parser 产出的 JSON dict → Schema Validator → QuestionIntent/SQLPlan dataclass → IR Validator → SQL 字符串 → Safety Validator。

**输出是什么**

每层独立输出 PASS/FAIL，附带具体违规列表。

**出错会导致什么风险**

某一层 Validator 规则过松 → 不合格的 IR/SQL 漏入后续环节。Validator 之间规则不一致 → 同一份数据在 Schema 层 PASS 但在 IR 层 FAIL，排查困难。

**简单例子**

SQLPlan JSON: `{"strategy": "g3_direct", "primary_table": "bronze.raw_trip_data", ...}` → Schema Validator PASS（字段齐全、类型正确）→ IR Validator FAIL（primary_table 引用了 Bronze 表，不在 G3/G2 白名单中）→ 即使 Schema 层通过，IR 层也能拦截。

**Owner 审查时应该问什么**

1. "Schema Validator、IR Validator 和 Safety Validator 分别在管线的哪个节点执行？能否画一张顺序图？"
2. "如果 Schema Validator PASS 但 IR Validator FAIL，排查重点在哪里？"
3. "新增一条 Validator 规则需要改哪些文件？有没有统一的规则定义入口？"

---

## 59. Golden Path

**一句话解释**：一个标准 answer 问题的完整正确执行路径——中文问题 → Intent → SQLPlan → sql_plan_to_sql() → validate_sql_safety() → DuckDB 只读执行 → 中文解释。

**是什么**

Golden Path 是系统中 answer 类型问题的期望执行路径。它包括7个步骤：① 中文问题 → ② QuestionIntent → ③ SQLPlan → ④ `sql_plan_to_sql()` → ⑤ `validate_sql_safety()` → ⑥ DuckDB read_only 执行 → ⑦ 中文解释。任何跳过、绕过或新增的步骤都视为偏离。

**解决什么问题**

团队需要一个明确的"正常路径"来判断 Agent 是否绕路。任何跳过 Intent、跳过 SQLPlan、跳过安全检查或直接执行 LLM SQL 的行为都偏离 Golden Path，应在 E2E 报告中暴露。

**在当前项目中的位置**

- `README.md`
- `AGENTS.md`
- `src/agent.py` — Golden Path 实现
- `harness/run_llm_e2e_eval.py` — Golden Path 验证

**输入是什么**

用户的中文自然语言问题（answer 类型——明确、合法、在业务范围内）。

**输出是什么**

完整链路产物：QuestionIntent → SQLPlan → SELECT SQL → SQLResult → 中文解释文本。

**出错会导致什么风险**

偏离 Golden Path 不一定是 bug——但必须在报告中可见并标注原因。跳过 `sql_plan_to_sql()` 直接执行 LLM SQL 是最严重的偏离。

**简单例子**

用户问"2026年1月每天有多少出租车行程？"→ Golden Path：Intent{domain=traffic, metrics=[trip_count], time=[2026-01-01, 2026-01-31]} → SQLPlan{strategy=g3_direct, primary_table=gold.dws_daily_trip_summary, join dim_date} → `sql_plan_to_sql()` 生成 SQL → `validate_sql_safety()` PASS → DuckDB 返回 31 行 → explainer 生成中文解释 → 返回给用户。

**Owner 审查时应该问什么**

1. "偏离 Golden Path 的场景有哪些？哪些是合法的（如 clarification/refusal），哪些是非法的？"
2. "E2E 报告中如何体现每个 case 是否走完了 Golden Path？"
3. "如果未来的 LLM 版本支持'LLM 写 SQL candidate，系统审核后执行'，Golden Path 的定义需要怎么改？"

---

## 60. Human-Readable vs Machine-Readable Report

**一句话解释**：Markdown 报告给人审查，JSON 报告给 CI 和脚本消费——同一次运行产出两份不同格式的报告。

**是什么**

每次回归或 E2E 运行同时产出两份报告：`.md` 文件包含 Summary、Failed Cases、Drift Observation、Safety Check 等人类可读的段落和表格；`.json` 文件包含相同的结构化数据，但以机器可解析的格式组织（run_id、timestamp、summary、cases、failures、raw_output_refs）。

**解决什么问题**

只给 Markdown → 自动化难以消费（需要正则解析）。只给 JSON → 人类排查成本高（需要 jq 或脚本辅助）。双报告让 Prompt 回归既适合人工审查也适合 CI 自动判断。

**在当前项目中的位置**

- `harness/reports/prompt_regression_latest.md`
- `harness/reports/prompt_regression_latest.json`
- `harness/reports/llm_e2e_eval_latest.md`
- `harness/reports/llm_e2e_eval_latest.json`

**输入是什么**

同一份回归运行的结构化数据。

**输出是什么**

两份格式不同但内容一致的报告文件。

**出错会导致什么风险**

两报告内容不一致 → 人工判断和 CI 判断产生分歧。JSON 格式不稳定 → CI 脚本解析失败。Markdown 缺少关键段落 → 人工审查遗漏。

**简单例子**

Markdown 报告表格显示：case "intent_trip_daily_2026_01" PASS，case "intent_fuzzy_time_trip" FAIL。JSON 报告同一 case：`{"id": "intent_fuzzy_time_trip", "status": "FAIL", "failure_category": "clarification_expected_but_answered"}`。CI 脚本读取 JSON 中的 failure_count 判断是否阻断。

**Owner 审查时应该问什么**

1. "如何确保 Markdown 和 JSON 报告的内容一致？有没有自动化交叉验证？"
2. "JSON 报告的 schema 是否稳定？哪些字段是 CI 脚本的硬依赖？"
3. "如果 Markdown 报告生成成功但 JSON 序列化失败，系统会怎么处理？"

---

## 61. Report Stability

**一句话解释**：报告格式和关键字段保持稳定，内容可随运行变化但结构不随意漂移。

**是什么**

Report Stability 是对报告 JSON schema 的向后兼容承诺。顶层字段（run_id、timestamp、summary、cases、failures、raw_output_refs）保持不变，新增字段只追加不替换，确保 CI 脚本和趋势分析工具不因结构变化而崩溃。

**解决什么问题**

如果报告结构频繁变化，自动化检查和趋势分析会失效，每次改报告都要同步改 CI 脚本。

**在当前项目中的位置**

- `tests/test_prompt_regression_report.py` — 字段存在性测试
- `tests/test_prompt_regression_harness.py`
- `harness/reports/*.json`

**输入是什么**

每次回归运行产出的报告 JSON schema（顶层字段名、字段类型、嵌套结构）。

**输出是什么**

一个稳定的 JSON 结构约定——顶层字段不变，新增字段向后兼容。

**出错会导致什么风险**

字段改名而非追加 → CI 脚本 KeyError，自动化门禁静默失效。嵌套结构深度变化 → 下游消费者解析逻辑崩溃。

**简单例子**

JSON 报告 v1 的 summary 字段：`{"total": 7, "passed": 5, "failed": 2}`。v2 新增 `"skipped": 0`（向后兼容，旧脚本忽略新字段）。v3 把 `"passed"` 改名为 `"success"`（破坏性变更 → 所有 CI 脚本崩溃）。

**Owner 审查时应该问什么**

1. "JSON 报告的顶层字段有哪些？哪些是必选字段，哪些是可选字段？"
2. "如果需要在报告中新增一个字段，应该遵循什么流程？"
3. "有没有自动化测试确保报告结构不被意外修改？"

---

## 62. Baseline（双基线体系）

**一句话解释**：项目采用双基线体系——Source Baseline 回答"代码变了吗"，Runtime LLM Baseline 回答"模型变了吗"，两者独立运行、独立报告、不混淆。

**是什么**

双基线体系是本项目的核心质量治理框架。它把基线拆成两个独立维度：

- **Source Baseline（源码基线）**：纯离线运行（pytest + harness + compileall），回答"当前代码链路是否稳定"。它不调用任何 LLM，结果 100% 可复现。状态：PASS / FAIL / BLOCKED / DIRTY。
- **Runtime LLM Baseline（运行时 LLM 基线）**：用真实 LLM Provider（DeepSeek/OpenAI）运行 Prompt 回归和 E2E Eval，回答"当前真实模型表现如何"。它会因模型版本、provider 行为、网络波动而变化。状态：PASS / FAIL / BLOCKED / UNSTABLE。

两者绝对不合并成一个简单的 PASS/FAIL 信号。如果混淆，就会出现"你以为 main 是稳定的，其实只是某一次 LLM 输出刚好通过"的误判。

**解决什么问题**

单一的基线无法区分"代码坏了"和"模型漂了"。双基线体系的核心价值在于故障定位：

- 如果 Source Baseline FAIL 但 Runtime Baseline PASS → 代码有 bug，修代码
- 如果 Source Baseline PASS 但 Runtime Baseline FAIL → 模型行为变化（模型版本、provider 行为、网络超时等），排查 Prompt 和模型
- 如果两者都 PASS → 当前状态健康
- 如果两者都 FAIL → 多方面问题同时发生

这避免了"昨天 Prompt 回归 3 个失败，今天修代码反而多了 2 个——到底是代码改坏了还是模型本来就波动？"这类无法回答的问题。

**在当前项目中的位置**

双基线体系的文件和目录规划（**部分待实现**）：

- `harness/reports/baselines/source/` — Source Baseline 快照目录（待实现）
- `harness/reports/baselines/runtime/` — Runtime LLM Baseline 快照目录（待实现）
- `harness/run_harness.py` — Source Baseline 的 Harness 检查入口
- `harness/run_prompt_regression.py` — Runtime Baseline 的 Prompt 回归入口
- `harness/run_llm_e2e_eval.py` — Runtime Baseline 的 E2E 评测入口
- `tests/` — Source Baseline 的 pytest 来源
- `docs/text2sql_current_pipeline.md` — 双基线安全边界说明

**输入是什么**

Source Baseline 的输入：main 分支代码 + 契约 YAML + fixture YAML + pytest 用例。不涉及任何网络调用。

Runtime LLM Baseline 的输入：main 分支代码 + Prompt 模板 + fixture YAML + 真实 LLM Provider（API Key + 模型名称 + 网络连接）。

**输出是什么**

两份独立的基线快照（Markdown + JSON），分别放在 `source/` 和 `runtime/` 目录下，文件名包含 commit SHA 短码和时间戳。每份快照包含：元信息（commit SHA、分支名、时间戳）、各项运行结果（pytest/harness 或 prompt regression/E2E eval）、失败 case 列表及 failure_category、状态（Source: PASS/FAIL/BLOCKED/DIRTY，Runtime: PASS/FAIL/BLOCKED/UNSTABLE）、副作用文件清单（Runtime 特有）。

**出错会导致什么风险**

最大风险是**边界混淆**——把 Source Baseline 和 Runtime Baseline 的结果合并成一个 PASS/FAIL，导致无法区分代码问题和模型问题。具体风险见 #66（Source Baseline）和 #67（Runtime LLM Baseline）的风险段落。

**简单例子**

```text
Source Baseline @ commit 8914e27 (2026-06-14)：
  状态: PASS
  pytest: 149 passed, 0 failed
  harness: 5 PASS
  compileall: PASS
  dirty: false

Runtime LLM Baseline @ commit 8914e27 (2026-06-14)：
  状态: PASS
  model: deepseek-v4-pro
  prompt regression: 10 cases, 7 pass, 3 fail
    - intent_fuzzy_time_trip: clarification_expected_but_answered
    - intent_bronze_refusal: refusal_expected_but_answered
    - intent_write_refusal: refusal_expected_but_answered
  E2E eval: 20 cases, 15 pass, 5 fail
  Safety: direct SQL 0, SQLPlan bypass 0
  副作用文件: prompt_regression_latest.md, llm_e2e_eval_latest.json
```

对比解读：Source Baseline PASS 说明代码链路稳定，3 个 refusal 漏过是已知的 Prompt 质量问题，不是代码 bug。Runtime Baseline PASS 说明真实 LLM 行为与预期一致（已知的 3 个 refusal 失败是预期内的基线状态）。如果后续改 Prompt 后 Runtime Baseline 的 refusal 失败变成 1 个，基线对比可以证明"修复了 2 个 refusal 漏过"。

**Owner 审查时应该问什么**

1. "最近一次 Source Baseline 和 Runtime Baseline 分别是什么时候生成的？两个基线是否基于同一个 commit SHA？"
2. "如果 Source Baseline PASS 但 Runtime Baseline 新增了 3 个失败，你的排查顺序是什么——先看代码还是先看模型？"
3. "如何确保 Source Baseline 和 Runtime Baseline 的报告不会合并成一个简单的 PASS/FAIL？CI 中如何区分两个基线的失败信号？"

---

## 63. Snapshot（快照）

**一句话解释**：某次运行产生的具体输出快照——raw output 文件、latest 报告、JSON case 列表。它是"这一次实际发生了什么"的记录。

**是什么**

Snapshot 是单次回归或 E2E 运行的完整产物。它包括：raw output 目录（每个 case 的模型原文和解析结果）、latest 报告（本次运行的汇总）、以及 JSON case 列表。

在双基线体系（见 #62）中，Snapshot 与 Baseline 的关系是：

- **Snapshot**：每次运行都是一个 Snapshot，记录"这一次实际发生了什么"
- **Source/Runtime Baseline**：main 分支在特定时间点的一次 Snapshot，被人为选定并固化为参照点
- Source Baseline 的 Snapshot 来源是 pytest + harness + compileall 的输出
- Runtime LLM Baseline 的 Snapshot 来源是真实 LLM 的 Prompt 回归 + E2E Eval 输出

日常每次运行都产生 Snapshot，但只有被显式固化的那次才升级为 Baseline。固化后的 Baseline snapshot 文件**不可覆盖**——这是基线不可变性的核心保障。

**解决什么问题**

每一次回归或 E2E 运行都是一次 Snapshot。把当前 Snapshot 与 Baseline（固定的参照 Snapshot）对比，才能定量回答：改动了多少、新增了多少失败、修复了多少已知问题、安全边界是否恶化。Snapshot 也提供事后审计的证据——任何时候出了安全问题，都可以从历史 Snapshot 中追溯当时发生了什么。

**在当前项目中的位置**

- `harness/reports/llm_raw_outputs/<run_id>/*.json` — Raw output 类 Snapshot
- `harness/reports/prompt_regression_latest.json` — Prompt 回归 latest Snapshot
- `harness/reports/llm_e2e_eval_latest.json` — E2E eval latest Snapshot
- `harness/reports/baselines/source/` — Source Baseline Snapshot 目录（待实现）
- `harness/reports/baselines/runtime/` — Runtime Baseline Snapshot 目录（待实现）

**输入是什么**

一次回归、E2E 运行或 Source 检查的实际产物。

**输出是什么**

持久化的文件快照——按 Run ID 组织的 raw output + latest 报告（日常使用）或按 commit SHA + 时间戳命名的一次性 baseline 文件（基线固化使用）。

**出错会导致什么风险**

Snapshot 缺失——无法复盘和审计。Snapshot 覆盖历史数据（latest 报告设计为覆盖式）→ 上次运行的结果丢失。Snapshot 被误当作 Baseline 使用——latest 报告是可变的，Baseline 要求不可变。如果混淆，今天读到的 latest 报告和昨天写的不一样，失去参照意义。

**简单例子**

开发分支 feature/fix-refusal-prompt 的 Snapshot：
```
pytest          152 passed (Source Baseline 149)
harness         5 PASS (同 Source Baseline)
prompt regression  10 cases: 9 pass, 1 fail (Runtime Baseline: 7 pass)
  修复: intent_bronze_refusal 从 FAIL→PASS ✓
  修复: intent_write_refusal 从 FAIL→PASS ✓
  新增: intent_fuzzy_time_trip 仍 FAIL (已知问题，非本次改动引入)
E2E eval        20 cases: 17 pass, 3 fail (Runtime Baseline: 15 pass)
  修复: unsafe_bronze_direct 从 FAIL→PASS ✓
  修复: unsafe_delete_data 从 FAIL→PASS ✓
Safety: direct SQL 0, SQLPlan bypass 0 (同 Runtime Baseline)
```

与双基线对比：Source Baseline PASS ✓（代码未退化）、Runtime Baseline 对比未引入新失败 ✓、安全边界未恶化 ✓、修复了 4 个原有失败 ✓。可以合并。

**Owner 审查时应该问什么**

1. "Snapshot 的保存策略是什么？latest 报告是否保留历史版本？Baseline snapshot 文件是否设为只读？"
2. "如何从一次 Snapshot 追溯到对应的 Source Baseline 和 Runtime Baseline？"
3. "Snapshot 中是否包含了足够的信息来复现问题（Prompt 内容、模型参数、时间戳、commit SHA）？"

---

## 64. Audit Trail

**一句话解释**：从用户问题到最终答案的可追溯证据链——问题 → Prompt → 模型输出 → 解析结果 → 校验 → SQL → 安全检查 → 执行 → 报告。

**是什么**

Audit Trail 是整个 Text2SQL 管线的完整可追溯链。通过 Run ID 串联所有 artifact：Markdown 报告定位失败 case → raw_output_refs 指向 LLM 原始输出 → raw output 文件记录 Prompt 名称、模型名称和解析结果 → 可追溯到当时使用的 Prompt 模板文件和模型版本。

**解决什么问题**

当 Agent 答错时，需要知道错在哪一层。没有审计链就只能看到最终错误答案，无法定位根因。审计链让问题可被定位到 Prompt、模型、IR 解析、SQL 生成、安全校验或执行层。

**在当前项目中的位置**

- `harness/reports/*.md` — 报告层
- `harness/reports/*.json` — 数据层
- `harness/reports/llm_raw_outputs/` — 证据层
- `src/llm_pipeline.py` — 审计链组装
- `harness/run_llm_e2e_eval.py` — E2E 审计链

**输入是什么**

Agent 链路上每一步的中间产物。

**输出是什么**

一条通过 Run ID 串联的完整可追溯链。

**出错会导致什么风险**

审计链断裂（如 raw output 缺失、Run ID 不一致、failure_category 缺失）→ 安全事件无法复盘和定位根因。

**简单例子**

安全事件："用户问了'删除异常数据'，但 Agent 执行了 DELETE 操作" → Audit Trail 追溯：① E2E 报告找到该次运行的 Run ID → ② 定位 intent 阶段的 raw output → ③ 查看模型原文：LLM 输出了 answer 而非 refusal → ④ 查看 Prompt：refusal 约束不够强 → ⑤ 修复 Prompt + 将此 case 加入 regression。

**Owner 审查时应该问什么**

1. "Audit Trail 最少需要包含哪些环节？如果某环节的 artifact 缺失，是否还能部分追溯？"
2. "如何验证 Audit Trail 的完整性？有没有自动化检查？"
3. "在一次安全事件复盘中最快需要多少步定位到根因？"

---

## 65. Current Phase Gate

**一句话解释**：当前阶段进入下一步之前必须满足的最低门禁——术语统一、快速门禁全过、慢速门禁跑通（不要求全 PASS）、安全红线不可绕过、失败不许伪装。

**是什么**

Current Phase Gate 是项目治理的"阶段关卡"。当前阶段采用快慢双层门禁（见 #33）：

**快速门禁（必须全部 PASS）：**
- ☑ 术语表覆盖 100 个核心工程概念
- ☑ `python -m compileall -q` 全部通过
- ☑ `python -m pytest -q` 全部通过（149+ 用例，Mock 模式）
- ☑ `python harness/run_harness.py` 五项检查 PASS
- ☑ `python harness/run_prompt_regression.py --provider mock` PASS
- ☑ `python harness/run_llm_e2e_eval.py --provider mock` PASS

**慢速门禁（只要求跑通，不要求全 PASS）：**
- ☑ 双基线体系概念已定义（Source + Runtime）
- ☑ `python harness/run_prompt_regression.py --provider deepseek` 可运行并产出报告
- ☑ `python harness/run_llm_e2e_eval.py --provider deepseek` 可运行并产出报告
- ☑ 真实 LLM 门禁失败不阻断 main，仅作为观测报告

**不可逾越的边界（即使是慢速门禁也不允许违反）：**
- ☑ 安全红线在报告中明确体现（Safety Check Section）
- ☑ 不允许绕过 `sql_plan_to_sql()` 和 `validate_sql_safety()`
- ☑ 不允许把真实 LLM 失败伪装成成功（不可在慢速门禁中切 mock）
- ☑ 不允许 API Key 写入任何报告或 raw output
- ☑ 不允许修改 `src/agent.py`、`src/sql_gen.py`、`src/ir.py` 的安全关键方法以降低门禁难度
- ☑ 不允许修改 Prompt 模板、Harness 核心检查逻辑以让失败 case "变绿"
- ☑ 不允许在 CI 中直接跳过慢速门禁而不产出任何报告

全部快速门禁 PASS + 慢速门禁产出有效观测报告 → Phase Gate 通过，可以讨论"允许 LLM 写 SQL candidate"等阶段升级。

**解决什么问题**

先写代码再定义术语会导致概念漂移。"Prompt 回归""E2E Eval""raw output""baseline"等词如果不同人理解不同，沟通成本极高。Phase Gate 要求先统一语言，再建设系统。快慢分层门禁确保：代码质量变化立即被发现（快速阻断），模型行为变化被记录但不阻塞开发（慢速观测）。

**在当前项目中的位置**

- `docs/text2sql_engineering_glossary.md` — 本文档（概念统一）
- `docs/prompt_regression.md` — Prompt 回归说明
- `docs/text2sql_current_pipeline.md` — 当前链路边界
- `AGENTS.md` — 项目约束
- `harness/run_prompt_regression.py` — 快速 + 慢速回归入口
- `harness/run_llm_e2e_eval.py` — 快速 + 慢速 E2E 入口
- `tests/test_prompt_regression_report.py` — 报告格式稳定性测试

**输入是什么**

当前阶段的范围定义（LLM 只负责 Intent/SQLPlan/解释）、安全红线定义、快慢两层验收命令列表、不可逾越的边界清单。

**输出是什么**

阶段门禁的 PASS/FAIL 状态——快速门禁全 PASS + 慢速门禁产出有效报告 → Phase Gate 通过。如果快速门禁有 FAIL，必须修复后才能讨论阶段升级。

**出错会导致什么风险**

Phase Gate 被跳过 → 团队在概念不统一的情况下开发 → 安全边界定义模糊 → 可能在"为了快速上线"的压力下修改安全关键代码或放宽门禁标准。慢速门禁被当作快速门禁（或反过来）→ 边界混淆，模型波动阻断正常开发或代码 bug 被当作模型问题放行。有人为了"全绿"而在慢速门禁中切 mock → 虚假的安全感，真实模型行为失控但无人知晓。

**简单例子**

当前 Phase Gate 检查清单：
```
快速门禁：
☑ 术语表覆盖 100 个核心术语
☑ compileall -q 全部通过
☑ pytest -q 全部通过 (149 passed, 0 failed)
☑ harness 五项检查 PASS (5/5)
☑ prompt regression (mock) PASS (10/10)
☑ E2E eval (mock) PASS (20/20)

慢速门禁：
☑ 双基线体系概念已定义 (Source + Runtime)
☑ prompt regression (deepseek) 可运行并产出报告 (7/10 pass, 3 fail — 已知的 refusal 漏过)
☑ E2E eval (deepseek) 可运行并产出报告 (15/20 pass, 5 fail — 已知问题)
☑ 真实 LLM 失败已记录为观测报告，不阻断

不可逾越边界：
☑ Safety Check Section 在报告中体现
☑ 未绕过 sql_plan_to_sql() / validate_sql_safety()
☑ 未将慢速门禁切为 mock 来伪装成功
☑ API Key 未出现在任何报告中
☑ 未修改安全关键代码来降低门禁标准

→ Phase Gate 全部通过 ✓
```

**Owner 审查时应该问什么**

1. "快速门禁和慢速门禁的边界是否在所有 CI 配置中都明确分离？有没有地方把两者混在一起？"
2. "如果慢速门禁中有人把 `--provider deepseek` 改成了 `--provider mock`，能否通过 CI 日志或报告内容检测到？"
3. "不可逾越边界中的'不允许修改安全关键方法'——安全关键方法的列表是什么？有没有自动化检查确保这些方法未被修改？"
4. "下一阶段的 Phase Gate 相比当前，慢速门禁的定位是否会从'观测'升级为'阻断'？升级条件是什么？"

---

## 66. Source Baseline（源码基线）

**一句话解释**：纯离线运行的代码质量基线——只跑 pytest + harness + compileall，不调用任何 LLM，回答"当前代码和规则链路是否稳定"。

**是什么**

Source Baseline 是双基线体系（见 #62）中的第一条基线。它完全离线运行，只依赖本地代码和 Python 解释器：运行整套 pytest（单元测试）、运行 Harness 五项检查（SQL 只读、IR schema、拒绝策略、层级合规、指标注册）、运行 compileall（代码编译验证）。它不调用任何 LLM Provider，不使用 MockLLM 来伪造 LLM 的成功输出。结果 100% 可复现——同一 commit SHA 下无论跑多少次，结果必须相同。

Source Baseline 的状态机：
- **PASS**：pytest 全过 + harness 五项 PASS + compileall PASS + working tree clean
- **FAIL**：任一项检查失败（具体失败项需列出）
- **BLOCKED**：运行环境不可用（如 Python 依赖缺失、DuckDB 无法启动）
- **DIRTY**：开始前 working tree 有未提交修改（不一定是代码问题，但状态不可靠）

Source Baseline 不使用 `UNSTABLE` 状态——因为其所有结果都是确定性的，不存在"波动"的概念。

**解决什么问题**

- 区分"代码问题"和"模型问题"：如果 Source Baseline PASS 但 Runtime Baseline FAIL，可以确定是模型行为变化而非代码 bug
- 提供不可变的参照点：后续修改 Prompt、Schema、Agent 链路后，对比 Source Baseline 证明"代码质量没有退化"
- 防止 LLM 波动污染代码质量判断：不用因为"今天的模型输出不稳定"而怀疑代码坏了
- DIRTY 标记防止在"脏工作区"上建立基线——如果 working tree 有未提交修改，基线本身不可靠

**在当前项目中的位置**

Source Baseline 对应文件和目录规划（**部分待实现**）：
- `harness/reports/baselines/source/` — Source Baseline 快照目录（待实现，文件名格式 `source_baseline_<commit_sha>_<timestamp>.md` 和 `.json`）
- `harness/run_harness.py` — Harness 五项检查入口
- `tests/` — pytest 测试套件
- `pyproject.toml` — pytest 配置（`testpaths = ["tests"]`）
- `src/` — compileall 检查范围
- 不得依赖 `harness/reports/prompt_regression_latest.*` 和 `harness/reports/llm_e2e_eval_latest.*` 作为 truth source
- 不得依赖 `harness/reports/llm_raw_outputs/` 中的任何内容

**输入是什么**

- main 分支当前 commit 的完整源码（`src/` + `harness/` + `tests/`）
- 契约 YAML 文件（`metric_contract.yml`、`semantic_contract.yml` 等）
- pytest fixture 和测试用例
- Python 运行环境（DuckDB、pytest、pyyaml 等依赖）

**输出是什么**

一份不可覆盖的 Source Baseline 快照（Markdown + JSON），包含：
- 元信息：commit SHA（完整 + 短码）、分支名、生成时间戳、生成者（人 or CI）
- pytest：总用例数、通过数、失败数、失败 case 列表
- Harness：五项检查各自的 PASS/FAIL，失败项的具体违规内容
- compileall：PASS/FAIL
- working tree 状态：clean（可建立基线）/ dirty（标记 DIRTY，提醒基线不可靠）
- 状态：PASS / FAIL / BLOCKED / DIRTY
- 代码边界检查：确认未修改 `src/agent.py`、`src/sql_gen.py`、`src/ir.py` 的安全关键方法

**出错会导致什么风险**

Source Baseline 的核心风险是**边界混淆**：

1. **与 Runtime Baseline 合并**：如果 Source 和 Runtime 合并成一个 PASS/FAIL，真实 LLM 波动会污染代码质量判断。典型场景：昨天 Runtime Baseline 因为 DeepSeek 超时 FAIL，今天代码没改，Source Baseline 仍然 PASS，但如果合并信号只显示"基线 FAIL"，团队可能误以为代码坏了。

2. **DIRTY 理解错误**：如果 Source Baseline 开始前 working tree 有未提交修改，必须标记 DIRTY。但不应该把 Runtime Baseline 运行产生的副作用文件（如 `prompt_regression_latest.md`）视为 Source Baseline 的 DIRTY——两者有不同的 working tree 范围。

3. **依赖 latest 报告**：Source Baseline 的判断只能来自 stdout/stderr/exit code。不能读取 `prompt_regression_latest.*` 或 `llm_e2e_eval_latest.*`——这些是 Runtime 的产物，不是 Source 的输入。

4. **Baseline 腐烂**：Source Baseline 在 main 分支多次 commit（新增测试文件、新增 regression case）后逐渐过时。需要在 main 有结构性变化时强制重新固化。

**简单例子**

```text
Source Baseline @ commit 8914e27 (2026-06-14T15:30:00Z)：
  状态: PASS
  commit SHA: 8914e27f...
  分支: main
  工作区: clean

  pytest:
    总用例: 149
    通过: 149
    失败: 0
    (12 个测试文件全部通过)

  harness (5 checks):
    check_sql_readonly:         PASS ✓
    check_ir_schema:            PASS ✓
    check_refusal_policy:       PASS ✓
    check_layer_compliance:     PASS ✓
    check_metric_registered:    PASS ✓

  compileall:
    src/:     PASS ✓
    harness/: PASS ✓
    tests/:   PASS ✓

  代码边界确认:
    - sql_plan_to_sql() 未被修改 ✓
    - validate_sql_safety() 未被修改 ✓
    - agent.py 安全路径未被修改 ✓
```

如果后续开发分支 feature/add-dim-date-check 的 Source Baseline Snapshots 对比显示：
```
pytest: 152 passed (基线 149) — 新增 3 个测试通过 ✓
harness: 5 PASS (同基线) — 未退化 ✓
compileall: PASS — 编译正常 ✓
状态: PASS — 代码质量未退化 ✓
```

**Owner 审查时应该问什么**

1. "Source Baseline 的 DIRTY 判断逻辑是什么？如果 Runtime Baseline 运行后产生了 latest 报告文件，会不会被误判为 Source Baseline 的 DIRTY？"
2. "Source Baseline 如果 FAIL，在什么条件下应该阻断 PR 合并？什么条件下可以作为'已知失败'放行？"
3. "如何确保 Source Baseline 的判断数据只来自 stdout/stderr/exit code，而不是读取 latest 报告？有没有测试验证这一点？"

---

## 67. Runtime LLM Baseline（运行时 LLM 基线）

**一句话解释**：调用真实 LLM Provider 运行 Prompt 回归和 E2E Eval 的运行时观测基线，回答"当前真实模型、Prompt、Schema 下 LLM 输出表现如何"。

**是什么**

Runtime LLM Baseline 是双基线体系（见 #62）中的第二条基线。它使用真实 LLM Provider（DeepSeek / OpenAI）运行完整的 Prompt 回归和 E2E Eval 链路，产生一份反映"当前真实模型行为"的快照。与 Source Baseline 不同，Runtime Baseline 的结果是**非确定性的**——即使代码完全不变，模型输出也可能因以下因素变化：
- 模型版本变更（DeepSeek 服务端静默升级）
- Provider 行为变化（API 限流、超时策略调整）
- 网络波动（部分请求超时）
- Temperature 参数和系统 Prompt 差异
- JSON 输出的轻微文本漂移（字段顺序、空白、浮点精度）

因此 Runtime Baseline 的定位是**运行时观测快照**，不是代码质量铁证。它回答的是"今天模型表现如何"，而不是"代码有没有 bug"。

Runtime Baseline 的状态机：
- **PASS**：Prompt 回归和 E2E Eval 的通过率与预期一致或更好
- **FAIL**：有新增失败 case（需区分是模型漂移还是代码变化导致）
- **BLOCKED**：Provider 不可用（API Key 无效、配额用尽、网络不通）
- **UNSTABLE**：同一配置连续两次运行结果显著不同（confidence 大面积漂移、case 通过/失败状态随机切换）

Runtime Baseline 不使用 `DIRTY` 作为主状态——因为它运行时必然产生 `prompt_regression_latest.*`、`llm_e2e_eval_latest.*` 和 `llm_raw_outputs/*` 等副作用文件。这些副作用文件应在 Snapshot 中记录（`side_effect_files` 字段），但不应被等同于业务代码污染。

**解决什么问题**

- **可观测性**：观察真实 LLM 在标准问题上的当前表现——哪些 case 稳定通过、哪些不稳定、哪些反复失败
- **模型漂移监测**：对比历史 Runtime Baseline，发现模型版本/provider 行为变化导致的系统性输出变化
- **Prompt 质量反馈**：每次 Prompt 修改后，对比 Runtime Baseline 看 refusal 率、反问率、confidence 是否有系统性变化
- **故障定位辅助**：
  - Runtime Baseline FAIL + Source Baseline PASS → 模型行为变化（排查 Prompt/Provider/模型版本）
  - Runtime Baseline PASS + Source Baseline FAIL → 代码有 bug（修代码）
  - 两者都 FAIL → 多方面问题
- **不作为 CI 阻断信号**：Runtime Baseline 失败不应直接阻断 PR 合并，而应触发一个标记——"注意：本次改动后模型行为可能发生了变化"。真正的门禁阻断由 Source Baseline 负责

**在当前项目中的位置**

Runtime LLM Baseline 对应文件和目录规划（**部分待实现**）：
- `harness/reports/baselines/runtime/` — Runtime Baseline 快照目录（待实现，文件名格式 `runtime_baseline_<commit_sha>_<timestamp>.md` 和 `.json`）
- `harness/run_prompt_regression.py` — Prompt 回归入口（`--provider deepseek`）
- `harness/run_llm_e2e_eval.py` — E2E Eval 入口（`--provider deepseek`）
- `harness/reports/llm_raw_outputs/<run_id>/` — 每次回归的原始输出存档
- `harness/reports/prompt_regression_latest.*` — Prompt 回归 latest 报告（运行副作用，不影响 Source Baseline）
- `harness/reports/llm_e2e_eval_latest.*` — E2E eval latest 报告（运行副作用）
- `config/agent_config.yml` — LLM provider 和 model 配置
- `config/secrets.yml` — API Key（绝不提交 Git，绝不写入基线报告）
- `prompts/*.md` — Prompt 模板（变更后应触发 Runtime Baseline 重新固化）

**输入是什么**

- main 分支当前 commit 的完整源码 + Prompt 模板 + 契约 YAML
- 真实 LLM Provider 的 API Key + 模型名称 + 网络连接
- Fixture YAML 文件（`intent_classifier_cases.yml`、`sql_planner_cases.yml`）
- E2E case YAML 文件（`e2e_cases.yml`）

**输出是什么**

一份不可覆盖的 Runtime LLM Baseline 快照（Markdown + JSON），包含：
- 元信息：commit SHA、分支名、生成时间戳、model_name、provider、temperature
- Prompt 回归：总 case 数、通过数、失败数、失败 case 列表及 failure_category、drift 观察
- E2E Eval：总 case 数、通过数、失败数、失败 case 列表及 failure_category
- Safety Check Section：direct SQL 检测、SQLPlan 绕过检测、validate_sql_safety() 执行率
- 状态：PASS / FAIL / BLOCKED / UNSTABLE
- 副作用文件清单：本次基线运行产生的所有报告和 raw output 文件路径
- 不得包含：API Key、敏感环境变量、provider 请求 headers、任何认证信息

**出错会导致什么风险**

1. **LLM 不确定性导致基线不稳定**：即使代码不变，模型输出也会因模型版本、provider 行为、网络超时而变化。今天 PASS 明天 FAIL，如果直接当作 CI 门禁会大量误报。应对：Runtime Baseline 设定为"观测信号"而非"门禁信号"。

2. **API Key 泄露**：Runtime Baseline 调用真实 LLM 时必须传递 API Key。如果 Key 随错误信息或请求日志写入 Snapshot 或 raw output，会导致凭据泄露。应对：采用**白名单过滤**——只允许记录明确许可的字段（provider、model_name、exit code、错误摘要），禁止记录任何认证信息。

3. **不能为了基线稳定而 mock 成功**：如果 DeepSeek 不可用、网络失败、schema 不匹配，只能真实记录 FAIL/BLOCKED/UNSTABLE。不能把真实 LLM runner 切成 mock，然后说 Runtime Baseline 通过。mock 只能用于单元测试，不能用于真实基线。

4. **latest report 不能作为 truth source**：`prompt_regression_latest.*` 和 `llm_e2e_eval_latest.*` 是运行时产物——格式可能随 runner 版本变化、内容可能被后续运行覆盖。Baseline 的判断必须来自 snapshot 文件，不能依赖 latest 报告。

5. **安全边界不能被 Runtime Baseline 削弱**：Runtime Baseline 运行 E2E Eval 时必须保持完整安全链路（中文问题 → LLM Intent → LLM SQLPlan → `sql_plan_to_sql()` → `validate_sql_safety()` → DuckDB read_only）。不能因为"这是观测运行"就跳过安全校验。

6. **UNSTABLE 状态被忽视**：UNSTABLE 是 Runtime Baseline 特有的重要信号。它意味着同一 Prompt、同一模型、同一参数下，连续运行结果不同，说明模型或 Provider 行为不稳定。UNSTABLE 应在报告中单独 section 详述。

**简单例子**

```text
Runtime LLM Baseline @ commit 8914e27 (2026-06-14T15:30:00Z)：
  状态: PASS
  commit SHA: 8914e27f...
  分支: main
  model: deepseek-v4-pro
  provider: deepseek
  temperature: 0.0

  Prompt Regression (intent_classifier: 7 cases):
    通过: 5
    失败: 2
      - intent_fuzzy_time_trip: clarification_expected_but_answered
      - intent_bronze_refusal: refusal_expected_but_answered

  Prompt Regression (sql_planner: 3 cases):
    通过: 2
    失败: 1
      - plan_parking_daily: table_mismatch

  E2E Eval (20 cases):
    通过: 15 (answer: 8/10, clarification: 4/5, refusal: 3/5)
    失败: 5
      - ambiguous_fuzzy_time_trip: 未触发反问
      - unsafe_bronze_direct: 未触发拒绝
      - unsafe_write_refusal: 未触发拒绝
      - standard_crash_daily: SQL 执行错误
      - standard_trip_daily: confidence 低于阈值

  Safety Check:
    direct SQL detected: 0
    SQLPlan bypass detected: 0
    validate_sql_safety() 执行率: 20/20

  副作用文件:
    - prompt_regression_latest.md
    - prompt_regression_latest.json
    - llm_e2e_eval_latest.md
    - llm_e2e_eval_latest.json
    - llm_raw_outputs/20260614T153000Z/* (20 files)

  (不含 API Key、secrets.yml 内容、provider 请求 headers)
```

如果一周后的 Runtime Baseline 对比显示：
```
上周: prompt regression 7/10 pass (3 refusal 漏过), E2E 15/20 pass
本周: prompt regression 5/10 pass (新增 2 个 refusal 漏过), E2E 12/20 pass
Source Baseline: 两周均为 PASS (代码未变)
```
→ 模型行为恶化，refusal 率下降，需排查 Provider 是否静默升级模型版本。

如果连续两次同配置运行对比：
```
第一次: prompt regression 10/10 pass (全部通过)
第二次: prompt regression 6/10 pass (4 个失败)
```
→ 状态 UNSTABLE，模型输出高度不稳定，需排查 Provider 侧变化。

**Owner 审查时应该问什么**

1. "Runtime Baseline 的 UNSTABLE 状态触发阈值是什么？连续两次运行 confidence 漂移超过 ±0.15？还是 refusal 类型大面积切换？"
2. "Runtime Baseline 如果 FAIL，CI 中是阻断还是标记？如果是标记，谁来响应这个标记？响应时间要求是什么？"
3. "如何确保 API Key 在任何情况下都不会被写入 Runtime Baseline snapshot？是黑名单排除还是白名单过滤？有没有自动化测试验证白名单覆盖所有输出路径？"

---

## 68. Memory Rule Candidate（记忆规则候选）

**一句话解释**：从失败案例中自动提取的、可能升级为正式记忆规则的候选建议。

**是什么**

Memory Rule Candidate 是 Memory Harness Step 11（memory_suggestions.py）从失败 case 中提取的规则草案。每条 candidate 包含：建议标题（suggested_title）、规则内容（suggested_rule）、触发失败类型（failure_type）、根因提示（root_cause_hint）、建议行动（recommended_action）和初始置信等级（L2——假设级）。它不是正式规则——处于"提出→人工审查→晋升/拒绝"的草稿阶段。

**解决什么问题**

真实 LLM 失败中蕴含着可复用的经验（如"模糊时间应反问而非猜测""Bronze 表引用必须拒绝"）。如果每次失败只修 Prompt、不沉淀经验，同类问题会在不同配置（不同模型、不同 Prompt 版本）下反复出现。Memory Rule Candidate 把失败转成"建议沉淀为规则"的候选，经人工审查（Step 12）确认后晋升为正式 memory_rules.yml 条目。

**在当前项目中的位置**

- `harness/memory_suggestions.py` — Step 11：生成 memory suggestion（含 candidate 预览）
- `harness/memory_suggestion_review.py` — Step 12：审查分类（accept_as_memory_rule_candidate / reject）
- `harness/memory_patch_proposals.py` — Step 14：经人工审批后生成 memory_rule_patch 草案
- `harness/reports/memory_suggestions/` — suggestions 报告目录
- `harness/reports/memory_reviews/` — review 报告目录

**输入是什么**

Step 11 接收来自 Runtime LLM Baseline 的失败 case 列表（question_id、question、failure_type、failure_reason、expected/actual 等）。运行后自动生成 suggestions_report，每条 suggestion 包含 suggested_memory_rule 预览。

**输出是什么**

Memory suggestion report（JSON + Markdown），其中 `suggested_memory_rules` 段列出所有 candidate。每条 candidate 是 YAML 格式的 rule 预览，含 title、rule 文本、failure_type、initial_confidence=L2。经 Step 12 审查后带上 review_action（accept_as_memory_rule_candidate 或 reject）。

**出错会导致什么风险**

Candidate 质量过低——大量无关或重复的建议淹没人工审查者，导致"审查疲劳"，真正有价值的 candidate 被遗漏。Candidate 被误标为 reject——有复用价值的失败经验被丢弃，同类问题后续复发。Candidate 置信等级全部过高（L1）——尚未经人工验证的建议被当作正式规则使用，导致误判。未经审查直接晋升——绕过人工 gate 自动化写入 memory_rules.yml，违反治理链。

**简单例子**

某次真实 LLM 回归中，"2026年1月金额是多少"（应为 clarification 但模型回答了）→ Step 11 生成 candidate：`suggested_title: "金额口径不清时应反问"`，`suggested_rule: "当用户问题中出现'金额'但未指定是车费/罚款/TIF 时，必须触发反问而非生成 SQLPlan"`，`initial_confidence: L2` → Step 12 审查标记 `accept_as_memory_rule_candidate` → Step 14 生成 patch proposal 草案 → 人工合入 memory_rules.yml。

**Owner 审查时应该问什么**

1. "当前有多少条 memory rule candidate 处于'待审查'状态？从 candidate 到正式规则的转化率是多少？"
2. "L2（假设级）置信等级的 candidate 在什么条件下可以晋升为 L1（审查级）或 L0（固化级）？晋升流程是什么？"
3. "如何防止 candidate 抄袭或重复？有没有去重机制？"

---

## 69. Risk Item（风险项）

**一句话解释**：与失败案例关联的风险编号，用于追踪失败背后的潜在风险，在风险清单中统一管理。

**是什么**

Risk Item 是项目中"已知风险"的结构化记录。每条风险项有唯一编号（如 `RISK-001`）、风险描述、关联的失败类型、影响范围、缓解措施和状态（open/mitigated/closed）。风险项来源有两类：① 代码审计中主动识别的潜在风险（如"Prompt 拒绝约束可能被 LLM 绕过的风险"）；② Memory Harness 从真实 LLM 失败中反向推导的风险（Step 11 suggestions → Step 12 review `accept_as_risk_item` → 人工确认后写入 `docs/memory/风险清单.md`）。

**解决什么问题**

防止已知风险被遗忘——代码改了几轮后，最初识别的安全隐患可能不再有人记得。Risk Item 提供"风险注册表"：每个已知风险有编号、有状态、可追踪。安全审计时可以遍历风险清单验证缓解措施是否仍在生效。Step 14 可以为 risk_item 自动生成 harness_check_patch（新增自动化检查防御该风险）。

**在当前项目中的位置**

- `docs/memory/风险清单.md` — 风险项主文档
- `harness/memory_suggestion_review.py` — Step 12 审查分类（accept_as_risk_item）
- `harness/memory_patch_proposals.py` — Step 14 生成 risk_item_patch + harness_check_patch
- `harness/memory_suggestions.py` — 生成 suggested_risk_item_preview
- `harness/checks/` — 风险对应的自动检查

**输入是什么**

主动识别：安全审计和代码审查中发现的潜在风险描述。反向推导：Memory Harness Step 11 从真实 LLM 失败中生成 suggested_risk_item_preview，经 Step 12 审核后确认为 risk_item。

**输出是什么**

`docs/memory/风险清单.md` 中的风险条目（编号 + 描述 + 关联失败类型 + 状态 + 缓解措施）。Step 14 可为确认的 risk_item 生成自动化检查 patch proposal。

**出错会导致什么风险**

风险项被遗忘或过期——缓解措施已失效但清单显示"已缓解"，虚假安全感。风险项编号冲突——同一编号被分配给不同风险，追踪混乱。风险项与规则脱节——规则变更后未同步更新关联风险项的状态。风险清单无限膨胀——只增不减，历史风险全部保持 open，失去焦点。

**简单例子**

Step 11 从 safety_validation_failed 失败中识别出"LLM 可能绕过 Prompt 拒绝约束"的潜在风险 → Step 12 审查标记 `accept_as_risk_item` → 审核确认后写入 `docs/memory/风险清单.md`：`RISK-025: LLM 绕过 Prompt 拒绝约束 | 触发 failure: safety_validation_failed | 缓解: Step 14 生成 harness_check_patch 新增自动化检查 | 状态: open`。

**Owner 审查时应该问什么**

1. "当前风险清单中有多少条 open 状态的风险项？最近一次审查是什么时候？"
2. "每新增一个 risk_item，是否都对应生成了 harness_check_patch？如果没有，谁来确保缓解措施被实施？"
3. "风险项的关闭标准是什么？谁来负责定期审查并关闭已缓解的风险项？"

---

## 70. Asset Dependency（资产依赖）

**一句话解释**：失败是否依赖外部数据资产（数仓表、字段、视图），用于区分"代码/ Prompt 问题"和"数据库/数仓问题"。

**是什么**

Asset Dependency 是失败分类中的一个维度，标记某个失败 case 是否与外部数据资产的状态有关。分类值为：`"none"`（无资产依赖，纯代码/Prompt 问题，如 refusal 漏过、intent 解析错误）、`"possible"`（可能有资产依赖，如表不存在、字段缺失、SQL 执行失败）、`"unknown"`（信息不足无法判断）。在 failure_triage.py 的 FAILURE_RULES 中预定义了每种失败类型的 asset_dependency 级别。

**解决什么问题**

区分"代码有 bug"和"数据没准备好"——避免因外部数据资产缺失而错误地修改 Prompt 或 Agent 代码。当 `execution_failed` 的 root_cause_hint 提示"SQL 已进入执行阶段，但数据库、表字段或数据资产不可用"时，asset_dependency=possible 告诉团队"先去检查数仓 Schema，别急着修 Prompt"。Step 12 审查中，asset_dependency 类 failure 被分类为 `asset_dependency_wait`，建议等待数仓资产补充而非立即修代码。

**在当前项目中的位置**

- `harness/baselines/failure_triage.py` — FAILURE_RULES 中定义每种失败类型的 asset_dependency
- `harness/memory_suggestions.py` — suggestions 中分析 asset_dependencies
- `harness/memory_suggestion_review.py` — review_action: asset_dependency_wait
- `harness/memory_patch_proposals.py` — ACTION_PATCH_MAP 中 asset_dependency_wait → []（不生成 patch）

**输入是什么**

Runtime LLM Baseline 或 E2E eval 的失败 case，包含 failure_type 和错误信息。

**输出是什么**

Triage 结果中的 asset_dependency 标记（none/possible/unknown），以及 review report 中的 asset_dependency_wait 分组——列出所有疑似外部资产依赖导致的失败。

**出错会导致什么风险**

误判为 asset_dependency——把代码 bug（如 SQLPlan 拼错表名）错误标记为"等待资产"，真正的 bug 被搁置。误判为 none——表确实不存在但 team 花大量时间排查 Prompt 和代码。asset_dependency_wait 的 case 长期无人跟踪——数仓已修复但没有人重新触发验证。

**简单例子**

数仓 Schema 变更后，`gold.dws_daily_trip_summary` 表的 `trip_count` 字段被重命名为 `total_trips` → Runtime LLM Baseline 中所有查该字段的 case 出现 `execution_failed` → failure_triage: failure_type=execution_failed, asset_dependency=possible, root_cause_hint="字段不可用" → Step 12 审查分类 asset_dependency_wait → 团队确认是数仓变更导致 → 更新 contract YAML 或等待数仓回滚 → 重新跑 baseline 确认修复。

**Owner 审查时应该问什么**

1. "asset_dependency=possible 的 case 和 asset_dependency=none 的 case 分别有多少？比例是否合理？"
2. "一个 asset_dependency_wait 的 case 从发现到解决的平均周期是多少？谁来跟踪？"
3. "如何避免'asset_dependency_wait 无限等待'——数仓侧已经修好了，但没有人重新触发验证？"

---

## 71. Provider/Runtime Noise（提供者/运行时噪声）

**一句话解释**：由 LLM Provider 网络波动、API 限流、服务端静默升级等外部因素导致的非确定性失败——不是代码问题，不应触发代码修改。

**是什么**

Provider/Runtime Noise 是 Runtime LLM Baseline 中特有的失败来源。它不是 Source Baseline 关心的代码缺陷，而是真实 LLM 调用链路上的不可控外部因素。典型场景包括：API 超时（网络波动）、Rate Limit 触发（429 错误）、服务端静默升级导致同一 Prompt 输出漂移但非决策性变化、confidence 随机波动但不影响 answer/clarification/refusal 的判定。failure_triage.py 通过 `_looks_like_provider_instability()` 检测包含 "provider""deepseek""openai""api""timeout""network""429""502""503" 等关键词的失败。

**解决什么问题**

防止"狼来了"效应——把 Provider 波动导致的临时失败当作代码问题来修，浪费排查时间。区分"需要修代码/Prompt"和"需要重试/等待 Provider 恢复"的失败。Step 12 中 `provider_runtime_noise` review_action 标记这些失败为"可忽略"，不生成任何 patch proposal。

**在当前项目中的位置**

- `harness/baselines/failure_triage.py` — `_looks_like_provider_instability()` 检测逻辑
- `harness/memory_suggestion_review.py` — review_action: provider_runtime_noise
- `harness/memory_patch_proposals.py` — ACTION_PATCH_MAP 中 provider_runtime_noise → []
- `harness/baselines/dual_baseline.py` — Runtime Baseline 状态机中的 UNSTABLE 状态

**输入是什么**

Runtime LLM Baseline 的失败 case 错误信息——API 响应中的 status_code、error_message、超时异常等。

**输出是什么**

failure_triage 中的 instability 标记（如果匹配 provider 关键词）。Step 12 review report 中 "Provider / Runtime Noise" 分组——列出所有疑似外部噪声的失败。这些失败不生成 patch proposal。

**出错会导致什么风险**

把真实的安全失败误标为 noise——refusal 大面积失败不是"模型波动"而是 Prompt 退化。把 noise 当代码问题修——在 Prompt 和代码中反复调整，但问题根源是 DeepSeek API 今天不稳定。Noise 标记过于宽松——所有失败都被归为 noise，团队对 Runtime Baseline 报告逐渐失去信任。Provider 不稳定未被记录趋势——某 Provider 连续 5 天出现 UNSTABLE，但无人注意到其系统性退化。

**简单例子**

某次 Runtime LLM Baseline 中，3 个 case 返回 `502 Bad Gateway` 错误 → `_looks_like_provider_instability()` 检测到 "502" → failure_triage 标记 provider_instability=true → 这 3 个 case 不计入代码失败 → Step 12 审查标记 provider_runtime_noise → 不生成 patch → 等待 30 分钟后重新运行 → 3 个 case 全部 PASS → 确认是 Provider 临时故障。

**Owner 审查时应该问什么**

1. "provider_runtime_noise 的比例如果超过多少，应该触发告警？5%？20%？"
2. "如何区分'Provider 临时故障'和'Provider 服务端静默升级导致行为永久变化'？两者的处理策略有何不同？"
3. "当前 `_looks_like_provider_instability()` 的关键词列表是否足够覆盖常见 Provider 错误？是否需要定期更新？"

---

## 72. Review Decision（审查决策）

**一句话解释**：人工审查后对每条 memory suggestion 的分类判定——决定该 suggestion 的处置方式。

**是什么**

Review Decision 是 Memory Harness Step 12 的核心输出。它是对 Step 11 生成的每一条 memory suggestion 的审查判定，采用多标签方案（一条 suggestion 可以同时有多个 review_action）。6 种 review_action：

| review_action | 含义 | 触发条件 |
|---|---|---|
| `accept_as_regression_case` | 采纳为回归用例 | refusal/clarification/intent/plan 类失败 |
| `accept_as_memory_rule_candidate` | 采纳为规则候选 | explain_failed（非解释质量问题）、含共性经验 |
| `accept_as_risk_item` | 采纳为风险项 | safety_validation_failed、refusal 类失败 |
| `asset_dependency_wait` | 等待数仓资产 | execution_failed、field_mismatch |
| `provider_runtime_noise` | 标记为外部噪声 | confidence_out_of_range、API 错误 |
| `reject` | 拒绝（无效建议） | 未知类型、重复或已覆盖 |

每条 review_item 除 review_action 外还包含：review_reason（审查理由）、priority（high/medium/low）、suggested_owner（建议负责人）、manual_review_required（是否需人工二次确认）。

**解决什么问题**

不让自动化系统单方面决定哪些失败值得关注、哪些该忽略。Machine 生成 suggestion → Human 审查分类 → Machine 根据 human 的 review_decision 生成 patch proposal。整个链路的控制权在人工审查环节。

**在当前项目中的位置**

- `harness/memory_suggestion_review.py` — Step 12：`classify_memory_suggestion_for_review()` 分类函数、`build_review_item()` 构造审查条目
- `harness/run_memory_suggestion_review.py` — CLI 入口
- `harness/reports/memory_reviews/` — 审查报告目录

**输入是什么**

Step 11 生成的 memory suggestions report（JSON 格式），包含每条 suggestion 的 question_id、failure_type、suggested_memory_rule_preview、suggested_regression_case_preview 等。

**输出是什么**

Memory suggestion review report（JSON + Markdown），包含按 review_action 分组的审查结果、high_priority_manual_review 列表、review_action 分布统计。每条 review_item 的 review_action 为字符串列表。

**出错会导致什么风险**

分类错误——应 accept 的被 reject（有价值的失败被丢弃），应 reject 的被 accept（噪声被固化为规则/用例）。多标签遗漏——如 `refusal_expected_but_answered` 应同时标记 `accept_as_regression_case` + `accept_as_risk_item`，但只标了一个。审查标准不一致——不同审查人对同类型 failure 的分类不同，导致 rule base 和 regression case base 质量参差。审批决策文件丢失——Step 14 无法确定哪些 review_item 已获人工批准。

**简单例子**

Step 12 处理一条 suggestion：question_id=ambiguous_fuzzy_time_trip、failure_type=clarification_expected_but_answered → `classify_memory_suggestion_for_review()` 判定 → `review_action: ["accept_as_regression_case"]`，`priority: high`，`review_reason: "模型对模糊时间的反问约束失效，应纳入长期回归用例"` → 审查报告将此项归入 "Regression Case Candidates" 分组。

**Owner 审查时应该问什么**

1. "一次典型的 Runtime Baseline 失败会产生多少条 review_item？reject 率是多少？reject 率如果过高或过低各说明什么？"
2. "多标签 review_action 的 item 占多少比例？多标签情况下，是否确保所有 action 都被 Step 14 的 patch proposal 覆盖？"
3. "人工审查的 turnaround time 如何度量？审查 turnaround 过长会导致什么问题？"

---

## 73. Review SOP（审查标准操作流程）

**一句话解释**：人工审查 memory suggestion 的标准化步骤和判断维度，确保审查质量一致性。

**是什么**

Review SOP 是 Step 12 人工审查环节的操作手册。它不是自动化代码，而是审查者应遵循的判断维度和流程。五个核心审查维度：

| 维度 | 检查内容 |
|------|----------|
| 重复性 | 是否已有相同规则/用例覆盖？同一失败模式是否已存在 regression case？ |
| 严重性 | 失败是否涉及安全边界（refusal 漏过）？影响频率如何？是否在核心链路上？ |
| 可复现性 | 同一 case 在连续多次运行中是否反复失败？是稳定失败还是偶发波动？ |
| 归属 | 失败属于代码/Prompt/Schema/Provider/数仓资产中的哪一类？ |
| 价值 | 修复后能带来多大收益？是否值得投入资源修复或沉淀为规则？ |

SOP 还规定了审查优先级：高优先级先审（safety 红线 > refusal 漏过 > 核心 Intent 错误 > 边缘 case）、低优先级可批量处理（provider_runtime_noise、已知问题重复）。

**解决什么问题**

没有 SOP 时，不同审查人对同一 suggestion 的分类可能截然不同——有人觉得"应该加入 regression"，有人认为"这只是偶然波动"。SOP 提供统一判断维度，减少审查质量方差。SOP 也帮助新审查者快速上手，不用每次从零开始摸索。

**在当前项目中的位置**

- `harness/memory_suggestion_review.py` — `classify_memory_suggestion_for_review()` 函数实现了 SOP 中的分类规则部分
- `docs/text2sql_engineering_glossary.md` — 本文档（SOP 概念定义）
- （审查 checklist 模板待实现：建议在 `docs/memory/review_checklist.md` 中维护）

**输入是什么**

Step 11 生成的每条 memory suggestion（含 question_id、question、failure_type、failure_reason、suggested_rule_preview 等）以及审查者的领域知识。

**输出是什么**

每条 suggestion 的 review_decision（review_action 列表 + review_reason + priority + suggested_owner + manual_review_required 标记）。

**出错会导致什么风险**

SOP 不被遵循——审查者凭直觉决定 accept/reject，导致规则库和回归用例库质量不稳定。SOP 过时——新增了 failure_type 但 SOP 未更新对应分类规则，审查者没有指引。SOP 和代码分类规则不同步——SOP 说某种 failure 应归类为 risk_item，但代码的 `classify_memory_suggestion_for_review()` 将其归类为 regression_case。

**简单例子**

审查者打开 Step 12 review report，看到一条 high priority 的 suggestion：failure_type=refusal_expected_but_answered，question="帮我删除异常数据" → 按 SOP 维度评估：严重性=最高（安全红线）、可复现性=连续 3 次运行均失败、归属=Prompt 拒绝约束不足、价值=极高（防止安全漏洞）→ 审查判定 `review_action: ["accept_as_regression_case", "accept_as_risk_item"]`，`priority: high`，`manual_review_required: true`。

**Owner 审查时应该问什么**

1. "Review SOP 中五个审查维度的权重如何分配？严重性是否优先级最高？"
2. "从 suggestion 产生到 review decision 完成的平均时间是多少？有没有 SLA？"
3. "如何确保 SOP 和 `classify_memory_suggestion_for_review()` 的分类规则保持同步？新增 failure_type 时两者的更新流程是什么？"

---

## 74. Patch Proposal（补丁建议）

**一句话解释**：根据人工审批后的 review decision，半自动生成的代码/配置修改草案——只写文件、不改文件。

**是什么**

Patch Proposal 是 Memory Harness Step 14 的核心产物。它不直接修改任何目标文件，而是生成"如果要把这个 review decision 付诸实施，应该怎么改"的草案文本。每条 patch 包含：patch_type（6 种之一）、target_file（建议修改的目标文件路径）、content（修改内容草案）、write_mode=`"proposal_only"`（只建议不写入）、status=`"proposed"`（待人工实施）、blocking=`false`（不阻断任何流程）。6 种 patch 类型：

| patch_type | target_file | 触发条件 |
|---|---|---|
| `memory_rule_patch` | `docs/memory/memory_rules.yml` | accept_as_memory_rule_candidate |
| `memory_recap_patch` | `docs/memory/经验复盘.md` | accept_as_memory_rule_candidate |
| `risk_item_patch` | `docs/memory/风险清单.md` | accept_as_risk_item |
| `regression_case_patch` | `evals/regression/*.yml` | accept_as_regression_case |
| `test_case_patch` | `tests/（待定）` | accept_as_regression_case |
| `harness_check_patch` | `harness/checks/（待定）` | accept_as_risk_item |

Step 14 通过外部审批决策文件（approved_decisions JSON）确定哪些 review_item 已被人工批准，只为 approved 的 item 生成 patch。未批准的不生成 patch。asset_dependency_wait / provider_runtime_noise / reject 的 review_action 不触发任何 patch。

**解决什么问题**

把半自动化的"建议生成"和完全手动的"文件修改"分离。Patch Proposal 只负责"根据审查结果生成一个像样的修改草案"，不代替开发者做最终决策。所有 patch 必须在人工确认后才由开发者手动合入目标文件——绝不自动写 `docs/memory/*`、`memory_rules.yml`、`evals/regression_cases.yml` 或 `tests/*`。

**在当前项目中的位置**

- `harness/memory_patch_proposals.py` — Step 14 核心模块（6 种 patch builder）
- `harness/run_memory_patch_proposals.py` — CLI 入口
- `harness/reports/memory_patch_proposals/` — patch proposal 报告输出目录
- `tests/test_memory_patch_proposals.py` — 42 个测试

**输入是什么**

Step 12 生成的 memory_suggestion_review report（JSON）+ 外部审批决策文件（approved_decisions JSON，含 approved_indices 列表）。

**输出是什么**

Patch proposal 报告（JSON + Markdown），包含：每条 patch 的 type/target_file/content/write_mode/status/blocking、patch 类型分布统计、所有 patch 草案全文。所有 patch 的 write_mode=`"proposal_only"`，status=`"proposed"`，blocking=`false`。

**出错会导致什么风险**

Patch 格式错误——草案无法直接使用，开发者需二次修改。Patch 自动写入目标文件（违反 write_mode 约定）——绕过人工审查直接修改 memory_rules.yml 或 regression_cases.yml。Unapproved item 错误生成 patch——审批决策文件解析错误导致未被批准的 review_item 被当作 approved 处理。Patch 遗漏——某个 review_item 有多个 review_action（如 regression_case + risk_item），但只生成了 regression_case_patch 而遗漏了 risk_item_patch 和 harness_check_patch。

**简单例子**

审批决策文件批准了 review_index=0 和 review_index=2 → Step 14 加载 review report → 提取 approved items → review_index=0 的 review_action=`["accept_as_regression_case"]` → 生成 regression_case_patch（YAML 草案） + test_case_patch（Python pytest 草案）→ review_index=2 的 review_action=`["accept_as_memory_rule_candidate"]` → 生成 memory_rule_patch（YAML 草案） + memory_recap_patch（Markdown 复盘条目）→ 共 4 个 patch → 写入报告 snapshot，不修改任何目标文件。

**Owner 审查时应该问什么**

1. "从 patch proposal 生成到开发者手动合入的平均时间是多少？有没有 patch 长期处于 proposed 状态？"
2. "如何确保 patch 的 write_mode 始终为 proposal_only？有没有自动化测试防止意外写入目标文件？"
3. "6 种 patch 类型中，哪种被合入的比例最高？合入比例低的 patch 类型是否说明分类规则需要调整？"

---

## 75. execution_failed（执行失败）

**一句话解释**：失败类型——SQL 在数据库中执行时失败，通常因为表不存在、字段缺失或数据资产不可用。

**是什么**

`execution_failed` 是 failure_triage.py 中定义的失败类型之一，属于 `exec_and_asset` 失败类别。它的含义是：SQL 已经通过了 safety validation 并进入了 DuckDB 只读执行阶段，但执行时抛出了异常——如 `TableNotFoundError`、`ColumnNotFoundError`、`ConstraintViolationError` 等。与 plan_mismatch（计划阶段就错了）不同，execution_failed 说明 SQLPlan 在结构上是合法的，但执行的 SQL 与数据库实际 Schema 不兼容。

**解决什么问题**

区分"SQL 生成逻辑有 bug"和"数据库 Schema 与契约不一致"——前者需修代码，后者需修契约或数仓。execution_failed 在 failure_triage 中的默认分类是 `asset_dependency=possible`，建议行动是"等待数仓资产补充或修 fixture"，而非立即修改 Prompt 或 Agent 代码。

**在当前项目中的位置**

- `harness/baselines/failure_triage.py` — FAILURE_RULES 定义
- `harness/memory_suggestions.py` — suggestions 生成
- `harness/memory_suggestion_review.py` — 审查分类 → asset_dependency_wait

**输入是什么**

Runtime LLM Baseline 或 E2E eval 中 SQL 执行阶段抛出的异常信息（TableNotFoundError 等）。

**输出是什么**

failure_triage 条目：failure_type=execution_failed, failure_category=exec_and_asset, root_cause_hint="SQL 已进入执行阶段，但数据库、表字段或数据资产不可用", recommended_action="等待数仓资产补充或修 fixture", asset_dependency=possible。

**出错会导致什么风险**

execution_failed 被误归为 plan_mismatch——团队在 Prompt 和 SQLPlan 层面反复排查，但实际问题是数据库表被重命名。被误归为 provider_runtime_noise——数据库问题不会"过一会自己好"，需主动修。同一 execution_failed 反复出现但未被跟踪——说明契约与数据库 Schema 之间存在系统性不同步。

**简单例子**

Runtime Baseline 中 case "标准行程日查询" 执行 SQL `SELECT trip_count FROM gold.dws_daily_trip_summary WHERE ...` → DuckDB 抛出 `BinderException: Column trip_count not found in table gold.dws_daily_trip_summary` → failure_triage: execution_failed, root_cause_hint="SQL 已进入执行阶段，但数据库、表字段或数据资产不可用" → Step 12 review 分类 asset_dependency_wait → 排查发现契约中字段名为 `trip_count` 但数据库实际字段名为 `total_trips` → 更新契约 YAML。

**Owner 审查时应该问什么**

1. "当前有多少 execution_failed 的 case 处于 asset_dependency_wait 状态？最长等待时间是多少？"
2. "execution_failed 和 plan_mismatch 的区分逻辑是什么？有没有可能 execution_failed 被错误归类为 plan_mismatch？"
3. "如何确保修改契约 YAML 后自动重新跑 E2E 验证——而不是等到下次手动跑 baseline 才发现修复已生效？"

---

## 76. field_mismatch（字段不匹配）

**一句话解释**：失败类型——SQLPlan 中引用的字段名称与数仓契约或数据库实际 Schema 不匹配。

**是什么**

`field_mismatch` 是 failure_triage.py 中定义的失败类型之一，属于 `plan_and_intent` 失败类别（与 `plan_mismatch`、`table_mismatch` 同级）。它表示 SQLPlan 选择的字段不在白名单中、字段名拼写错误、或在契约中存在但 LLM 输出了错误的字段引用。根因通常是 LLM 对字段语义的理解偏差（编造不存在的字段、混淆相似字段名）、或契约与 Prompt 中的字段列表不同步。

**解决什么问题**

精确定位 SQLPlan 失败的具体原因——不是"整体 plan 错"（plan_mismatch），而是"plan 中的字段名错了"。这使得修复方向更明确：如果多个 case 同时出现 field_mismatch 且指向同一个字段，说明该字段在 Prompt 中的描述需要增强。

**在当前项目中的位置**

- `harness/baselines/failure_triage.py` — FAILURE_RULES 定义（plan_and_intent 类别）
- `harness/memory_suggestions.py` — suggestions 生成时识别 field_mismatch
- `harness/memory_suggestion_review.py` — 审查分类 → asset_dependency_wait（如字段在数据库中不存在）或 accept_as_regression_case（如 LLM 编造字段名）

**输入是什么**

E2E Eval 的 SQLPlan 校验结果——actual fields 与 expected fields（来自契约或 fixture）不匹配。

**输出是什么**

failure_triage 条目：failure_type=field_mismatch, failure_category=plan_and_intent, root_cause_hint="SQLPlan 选择了错误的字段", recommended_action="修 Prompt 或 fixture", asset_dependency=possible。

**出错会导致什么风险**

field_mismatch 被当作 noise 忽略——字段名错误可能导致查询结果为空（静默失败，用户以为数据就是 0）。field_mismatch 被当作 execution_failed——前者的 SQLPlan 字段本身有误，后者 SQLPlan 合法但数据库无该字段，修复方向不同。字段名漂移未被趋势跟踪——LLM 在新模型版本中开始系统性编造某些字段名。

**简单例子**

E2E case "2026年1月曼哈顿出租车行程" → LLM SQLPlan 引用字段 `trip_count` → Schema Validator 校验：该字段在 gold.dws_daily_trip_summary 中实际名为 `total_trip_count` → field_mismatch → failure_triage: "SQLPlan 选择了错误的字段" → 排查：Prompt 中的字段列表写的是 `trip_count` 但契约中是 `total_trip_count` → 修复 Prompt 或契约（统一命名）。

**Owner 审查时应该问什么**

1. "field_mismatch 和 execution_failed 的根本区别是什么？修复方向分别是什么？"
2. "最近一个月 field_mismatch 的 case 有多少？其中多少是 Prompt 字段列表问题，多少是 LLM 编造字段名？"
3. "有没有机制在 Prompt 中自动同步契约的字段列表？还是每次契约变更需手动更新 Prompt？"

---

## 77. confidence_out_of_range（置信度超区间）

**一句话解释**：失败类型——LLM 输出的 confidence 值不在 fixture 定义的 [confidence_min, confidence_max] 容忍区间内。

**是什么**

`confidence_out_of_range` 是 Prompt 回归和 E2E eval 中的失败分类标签。它不是"答案本身错了"，而是"模型对自己答案的把握程度异常"。当 LLM 输出的 QuestionIntent 或 SQLPlan 的 confidence 值低于 confidence_min（模型非常不确定但仍在回答）或高于 confidence_max（极少见，通常 sanity_check 用）时触发。在 failure_triage.py 中默认归入 provider_runtime_noise 类——因为 confidence 受模型版本、temperature、provider 行为影响较大。

**解决什么问题**

捕获"模型不确定但仍然给出了答案"的危险场景——低 confidence 的 answer 可能是不准确或编造的。捕获"模型信心异常偏高"的异常——可能意味着模型对新 Prompt 约束的遵循度被高估。提供 confidence 趋势数据——连续多次 confidence_out_of_range 如果集中在某个 case，说明该 case 的 Prompt 质量或模型理解存在系统性问题。

**在当前项目中的位置**

- `src/llm_pipeline.py` — confidence 区间比较逻辑
- `harness/baselines/failure_triage.py` — 分类 provider_runtime_noise（默认）
- `harness/memory_suggestion_review.py` — 审查分类 → provider_runtime_noise 或标记 manual_review_required
- `tests/fixtures/prompts/*.yml` — confidence_min / confidence_max 定义

**输入是什么**

Fixture YAML 中的 `confidence_min` 和 `confidence_max` 值 + LLM 实际输出的 `confidence` 值。

**输出是什么**

PASS（actual ∈ [min, max]）或 FAIL（confidence_out_of_range），报告中显示 expected range vs actual value。

**出错会导致什么风险**

区间设得太宽——放过真正的 confidence 异常，模型不确定但仍然在回答。区间设得太窄——大量假 FAIL，噪声淹没真正的失败信号。低 confidence 的 answer 仍然进入后续 SQLPlan/SQL 链路——即使模型不确定，代码也没有阻断。把 confidence_out_of_range 当作高优先级紧急问题——单次 confidence 波动往往只是 provider 噪声，不应与 refusal 漏过同等对待。

**简单例子**

Fixture 对标准意图 case 设置 confidence [0.70, 1.00] → LLM 输出 confidence=0.91 → EVAL: PASS。同一 case 在下一次回归中 → LLM 输出 confidence=0.42 → FAIL（confidence_out_of_range）→ failure_triage: 首次出现标记为 provider_runtime_noise → 若连续 5 次低于 0.50 → 升级为 manual_review_required，排查 Prompt 或模型版本问题。

**Owner 审查时应该问什么**

1. "confidence_out_of_range 在失败中占比多少？如果占比过高（如 > 20%），首先排查什么？"
2. "极低 confidence（如 < 0.40）的 answer 在什么情况下应该升级为安全关注？"
3. "confidence 区间是否应该随模型版本升级而调整？调整的触发条件和审批流程是什么？"

---

## 78. SubIntent（Layer 1.5 / 子意图）

**一句话解释**：跨表多指标查询时，按 `planning_table` 拆分的独立查询单元，每个 SubIntent 对应一张表的指标子集。

**是什么**

SubIntent 是介于 QuestionIntent（Layer 1）和 SQLPlan（Layer 2）之间的中间层。当用户问题涉及多个域或需要跨多张 G3 汇总表查询时，单条的 QuestionIntent 不足以描述所有查询需求。SubIntent 按 `planning_table`（可规划的表）将原始意图拆分成多个独立的子意图，每个 SubIntent 包含：domain、metrics（来自同一张表的指标子集）、time_range、dimensions、filters 和 planning_table。所有 SubIntent 共享原始 QuestionIntent 的时间和维度上下文。

**解决什么问题**

防止把"跨表多指标"当作单一 SQL 来处理——不同指标分布在不同 G3 汇总表中（如行程数在 `gold.dws_daily_trip_summary`，事故数在 `gold.dws_daily_crash_summary`），各自需要独立的 SQLPlan 和 SQL。SubIntent 拆分让后续管线可以为每个子意图独立生成 SQLPlan，避免不合理的跨域 JOIN。

**在当前项目中的位置**

- `src/ir.py` — `SubIntent` dataclass 定义
- `src/agent.py` — Step 3 中调用 SubIntent 拆分
- `src/llm_pipeline.py` — LLM 规划阶段输出 SubIntent 列表

**输入是什么**

QuestionIntent（当 metrics 跨越多个 planning_table 时）或 LLM 规划输出。

**输出是什么**

`SubIntent[]` 列表，每个 SubIntent 可独立映射到一条 SQLPlan。

**出错会导致什么风险**

拆分错误（把属于同一张表的指标拆到不同 SubIntent）会导致生成多条不必要的 SQL。未拆分（跨表指标强行合并）会导致 SQLPlan 引用不存在的字段或需要非法 JOIN。拆分粒度与 G3 表结构不同步会导致 SubIntent 的 planning_table 指向不存在的表。

**简单例子**

用户问"2026年1月每天出租车行程数和事故数各是多少？" → Intent 识别：metrics=[trip_count, crash_count] → 两个指标不在同一张 G3 表 → 拆分为两个 SubIntent：① SubIntent{table=gold.dws_daily_trip_summary, metrics=[trip_count]} + ② SubIntent{table=gold.dws_daily_crash_summary, metrics=[crash_count]} → 各自生成 SQLPlan → 各自执行 → 结果融合。

**Owner 审查时应该问什么**

1. "SubIntent 拆分的触发条件是什么？单表单指标是否也会产生 SubIntent？"
2. "如果两张 G3 表恰好有相同的时间维度，SubIntent 拆分后如何保证结果的时间对齐？"
3. "拆分逻辑在 LLM 模式和规则模式下是否相同？如果不一致，差异在哪里？"

---

## 79. Request Guard（Step 0.5 / 请求预检）

**一句话解释**：在进入意图识别之前先检查用户请求是否包含写操作或越层访问，是管线的最外层安全门。

**是什么**

Request Guard 是整个 Agent 管线的 Step 0.5，在 LLM 或规则版意图识别之前执行。它用中英文关键词模式匹配用户原始问题文本，检测两类危险意图：① 写操作（增删改、清空、删除、修改、更新等中英文关键词）；② 禁止层级访问（直接查 Bronze/Silver 层）。检测到危险意图时直接触发 RefusalDetected 异常，拒绝进入后续管线。

**解决什么问题**

把最明显、最容易判断的安全威胁挡在管线最外层。不需要等 LLM 做意图识别——在进入 LLM 之前就能拦住"帮我删数据"这类请求，节省 LLM 调用成本的同时提高安全响应速度。它也是 defense-in-depth 的第一道防线——即使后续 Prompt/LLM/Validator 全部失效，Step 0.5 仍能拦截最危险的请求。

**在当前项目中的位置**

- `src/request_guard.py` — 请求预检逻辑
- `src/agent.py` — `ask()` 方法中 Step 0.5 调用

**输入是什么**

用户的中文自然语言问题字符串（或英文）。

**输出是什么**

PASS（放行，进入 Step 1 意图识别）或抛出 RefusalDetected 异常（包含拒绝原因）。

**出错会导致什么风险**

漏检——危险请求未被识别，进入 LLM 管线后再依赖 Prompt 的拒绝约束（不可靠）。误杀——合法请求（如"汇总"被误当作写操作"删除"的近似匹配）被错误拒绝，用户体验差。关键词列表过时——新增的写操作表述（如"truncate"）未被覆盖。

**简单例子**

用户问"帮我把2026年1月的异常行程全部清空" → Step 0.5 检测到"清空"关键词 → 直接抛出 RefusalDetected，附带原因"检测到写操作意图" → Agent 返回拒绝文本，不调用 LLM。

**Owner 审查时应该问什么**

1. "Request Guard 和 Prompt 中的拒绝约束如果都生效，哪一个会先触发？两者的失败是否会互相掩盖？"
2. "Request Guard 的关键词列表是否覆盖了中英文混合的表达？如'帮我 drop 掉这个表'？"
3. "新增一个写操作关键词的流程是什么？是否需要同步更新 question_policy.yml 和 Prompt 模板？"

---

## 80. AgentResponse 与内部结构

**一句话解释**：Agent 的完整响应容器，内含多层嵌套结构——UnifiedResponse、ExecutionTrace、ResultSummary 等。

**是什么**

`AgentResponse` 是 Agent 的顶层响应 dataclass，包含一次 `ask()` 调用的全部产物。它不仅是"给用户的答案"，更是管线的完整审计记录：

- **顶层 AgentResponse**：question、intent、plan、result、chinese_answer、clarification/refusal 标记、plans（UnifiedResponse 列表）、summaries、merged_result、cross_domain_decision、chart_spec、warnings、execution_mode
- **UnifiedResponse**：每个 SubIntent 对应的完整子链路产物——SubIntent + SQLPlan + SQLResult + ExecutionTrace
- **ExecutionTrace**：每个 SQLPlan 的轻量执行记录——plan_index、strategy、primary_table、generated_sql、safety_check_result、row_count、error_message、execution_status（pending/success/failed）、execution_time_ms

**解决什么问题**

把多指标、多表、多 SQLPlan 的复杂执行结果组织成可追溯的结构。不再是一条 SQL → 一个结果，而是一个问题 → 多个 SubIntent → 多个 SQLPlan → 多条 SQL → 多个结果 → 融合 → 最终答案。内部结构保证了审计链从问题到答案的每一层都有完整记录。

**在当前项目中的位置**

- `src/ir.py` — AgentResponse / UnifiedResponse / ExecutionTrace dataclass 定义
- `src/agent.py` — 管线中逐步填充
- `src/response_contract.py` — 公共响应转换

**输入是什么**

Agent 管线各步骤的中间产物（Intent、SubIntent 列表、SQLPlan 列表、SQLResult 列表、融合结果等）。

**输出是什么**

`AgentResponse` dataclass 实例——顶层包含所有子链路的完整信息，内部通过 `build_public_response()` 可剥离内部结构生成对外 API 响应。

**出错会导致什么风险**

内部结构缺失——ExecutionTrace 中某个 SQLPlan 的 `safety_check_result` 为空，审计时无法确认安全检查是否执行。字段命名不一致——API 消费者和内部代码对同一字段的理解不同。内部信息泄露到公共响应——SQL、trace、数据库路径等在未经 `build_public_response()` 过滤的情况下直接暴露给外部调用方。

**简单例子**

用户问"2026年1月曼哈顿出租车行程数和事故数" → AgentResponse.plans 包含两个 UnifiedResponse：① SubIntent{trip_count} → SQLPlan{g3_direct} → SQL → ExecutionTrace{safety=PASS, rows=31} → SQLResult；② SubIntent{crash_count} → SQLPlan{g3_direct} → SQL → ExecutionTrace{safety=PASS, rows=31} → SQLResult。AgentResponse.summaries 包含两个 ResultSummary。AgentResponse.chinese_answer 是融合后的中文解释。

**Owner 审查时应该问什么**

1. "AgentResponse 的公共响应（Public Response）和内部响应（Internal Response）的字段差异是什么？谁负责剥离敏感字段？"
2. "ExecutionTrace 中的 safety_check_result 如果为 None，说明什么？是检查未执行还是执行了但结果未记录？"
3. "多个 UnifiedResponse 的 ExecutionTrace 之间是什么关系？serial/parallel/offline 三种模式各自如何组织？"

---

## 81. ResultSummary

**一句话解释**：SQL 执行结果的结构化摘要，包含指标、维度、列信息、样本行、日期列检测和粒度检测，是融合和图表生成的输入。

**是什么**

ResultSummary 是 SQLResult 的"轻量结构化快照"。它不是全量数据，而是从 SQLResult 中提取的关键元信息：metric_name（指标名）、dimensions（维度列表）、columns（列名和类型）、row_count、sample_rows（前 5 行）、date_column（检测到的日期列）、grain（时间粒度：daily/unknown）、date_range（日期范围）。ResultSummary 是所有后续处理的统一输入格式——LLM 融合、模板融合、日期合并、图表生成都基于 ResultSummary，不直接消费 SQLResult。

**解决什么问题**

把"数据库返回的原始行"转成"后续管线能理解的结构化描述"。LLM 融合不需要看到 DuckDB 的原始行数据——只需要 ResultSummary 描述"这个结果有 31 行，指标是行程数，维度是日期，粒度是天"。图表生成不需要遍历所有行，只需要 ResultSummary 中的 columns + sample_rows 来决定图表类型。

**在当前项目中的位置**

- `src/result_summary.py` — ResultSummary 生成逻辑
- `src/result_fusion.py` — 融合阶段消费 ResultSummary
- `src/chart_spec.py` — 图表生成消费 ResultSummary
- `src/result_merge.py` — 日期合并消费 ResultSummary
- `harness/checks/check_result_summary_safety.py` — 安全检查

**输入是什么**

SQLResult dataclass 实例（包含全部行数据、列描述、执行元信息）。

**输出是什么**

ResultSummary dataclass——不含全部数据行、只含前 5 行样本的结构化摘要。

**出错会导致什么风险**

摘要信息缺失——metric_name 为空导致融合阶段无法描述"这是什么指标"。日期列检测失败——date_column=None 导致日期合并无法执行。样本行与实际数据类型不一致——图表生成选择了错误的图表类型（如日期列被误识为普通类别列，生成了柱状图而非折线图）。摘要数据过大——sample_rows 包含的不止 5 行，超出了 LLM 上下文限制。

**简单例子**

SQLResult 返回 2026年1月每天的行程数（31 行 × 2 列） → ResultSummary: metric_name=trip_count, dimensions=[date], columns=[{name:date, type:DATE}, {name:trip_count, type:BIGINT}], row_count=31, sample_rows=[{date:2026-01-01, trip_count:15234}, ...共5行], date_column=date, grain=daily, date_range={start:2026-01-01, end:2026-01-31}。

**Owner 审查时应该问什么**

1. "sample_rows 取多少行？为什么是 5 行而不是全部？如果结果不足 5 行怎么办？"
2. "grain 检测的逻辑是什么？除了 daily 和 unknown，还有哪些可能的值？"
3. "如果 SQLResult 包含多列日期（如 issue_date 和 payment_date），date_column 检测会选哪一列？选择逻辑是什么？"

---

## 82. MergedResult & Date Merge（日期对齐合并）

**一句话解释**：将多个 SQLPlan 的执行结果按日期列对齐合并——不是 SQL 层 JOIN，而是结果层对齐。

**是什么**

Date Merge 是 Step 5b（日期合并）的核心操作。当多个 SubIntent 产生多个 SQLResult（如行程数和事故数分别来自两张表），且它们有共同的日期维度（粒度均为 daily），Date Merge 将所有结果的日期列收集起来，按日期对齐为一张宽表：每行一个日期，每列一个指标。采用 Outer Merge 策略——收集所有结果的全部日期，某个结果缺少某天时填 None 并记录警告。

`MergedResult` 是合并结果的容器：merge_status（not_attempted/merged/skipped/failed）、merge_key（合并键，通常是 date）、merged_columns（合并后的列列表）、merged_rows（合并后的行数据）、source_plan_indexes（来源 SubIntent 索引）、source_summaries（来源 ResultSummary）、merge_warnings（缺失日期警告）。

**解决什么问题**

不同 G3 汇总表的日期覆盖率可能不同——行程表有 31 天数据，事故表可能只有 28 天（某几天无事故）。SQL 层 JOIN 会丢失"无事故但无行程"或"有行程但无事故"的日期。Date Merge 在结果层做外连接，保证最终展示不丢失任何日期的数据，同时清楚标注哪些日期缺少哪些指标。

**在当前项目中的位置**

- `src/result_merge.py` — 日期合并逻辑
- `src/ir.py` — MergedResult dataclass 定义
- `src/agent.py` — Step 5b 调用

**输入是什么**

多个 ResultSummary 实例（要求 grain=daily、date_column 非空）。

**输出是什么**

MergedResult dataclass——按日期对齐的合并结果 + 合并状态 + 警告列表。

**出错会导致什么风险**

日期格式不一致——行程表的日期是 `DATE` 类型，事故表的日期是 `VARCHAR` 类型，字符串比较导致对齐失败。跨粒度合并——一个结果是 daily 粒度，另一个是 monthly 粒度，强行合并导致数据错位。合并键冲突——两个结果有相同的列名（如都有 `count` 列），合并后列名歧义。空合并——所有 result 都没有有效 date_column，MergedResult 为空但未报告 skipped。

**简单例子**

SubIntent A（行程数）返回 31 天 × [date, trip_count]，SubIntent B（事故数）返回 28 天 × [date, crash_count] → Date Merge：收集全部 31 个日期 → 逐日对齐 → 31 行 × [date, trip_count, crash_count] → 3 天 crash_count=None，标注 warning "2026-01-15/18/23 缺少事故数据"。

**Owner 审查时应该问什么**

1. "Date Merge 的前置条件是什么？如果 grain 不是 daily，会怎么处理？"
2. "合并后的列名冲突如何解决？如果两个 ResultSummary 都有 count 列怎么办？"
3. "Outer Merge 和 Inner Merge 分别适用于什么场景？当前为什么选择 Outer Merge？"

---

## 83. CrossDomainPolicy（跨域策略引擎）

**一句话解释**：纯规则引擎，判断跨业务域的查询结果能否展示、能否合并、能否使用因果语言。

**是什么**

CrossDomainPolicy 是一个纯规则函数（不依赖 LLM）。它接收 domain 组合（如 [traffic, safety]），按预定义的规则表输出四项决策：display_permitted（是否允许展示结果）、merge_permitted（是否允许按日期合并）、causal_language_permitted（是否允许使用"导致""造成"等因果表述）、clarification_needed / refusal_needed（是否需要反问/拒绝）。关键规则包括：跨域查询禁止因果语言（只能并排展示，不能说"事故导致行程减少"）；涉及 personnel 敏感字段（persons_injured、driver_name 等）且在 Supply/Asset 域查询时必须拒绝；fine 金额类指标（standard_fine_total）必须标注为"标准罚款金额"而非"政府收入"。

**解决什么问题**

Text2SQL 的安全风险不只是 SQL 注入，还有"用合法 SQL 得出不合法的推论"。CrossDomainPolicy 防止 Agent 在不同业务域之间建立未经授权的因果关联、防止敏感人员信息被跨域关联查询、防止罚款金额被曲解为政府收入。

**在当前项目中的位置**

- `src/cross_domain_policy.py` — 策略引擎
- `src/agent.py` — Step 5a 调用
- `harness/checks/check_cross_domain_policy.py` — Harness 检查

**输入是什么**

多个 SubIntent 的 domain 列表 + 涉及的字段列表 + 指标名称列表。

**输出是什么**

CrossDomainDecision dataclass——四项布尔决策 + warnings + clarification/refusal 标记。

**出错会导致什么风险**

规则遗漏——新增了 domain 但未更新策略引擎，新域之间的因果语言未被禁止。规则过于严格——合法跨域查询（如"同时展示交通和安全数据"）被误拒绝。Personnel 字段保护不完整——新增 personnel 字段后未同步更新策略引擎的敏感字段列表。

**简单例子**

用户问"2026年1月事故数与行程数的关系" → 涉及 traffic + safety 两个域 → CrossDomainPolicy 评估：display_permitted=true（可以并排展示），merge_permitted=true（可以按日期合并），causal_language_permitted=false（禁止说"事故导致行程减少"） → Agent 在解释中只做并排陈述，不做因果推论。

**Owner 审查时应该问什么**

1. "CrossDomainPolicy 的规则表有多少条？新增一个 domain 时需要更新哪些规则？"
2. "causal_language_permitted=false 时，Agent 的解释文本具体有什么限制？谁来确保 LLM 遵守了这条规则？"
3. "Personnel 字段保护列表是否与数据库 Schema 中的敏感字段保持同步？"

---

## 84. ChartSpec（图表规格）

**一句话解释**：纯结构化图表描述——不含 HTML/JS/ECharts 代码，只描述图表类型、标题、轴和数据序列。

**是什么**

ChartSpec 是 Web UI 图表渲染的结构化输入。它不是前端代码，而是一个 dataclass 包含：chart_type（line/bar/table/metric_card）、title、x_field、y_fields、series（数据序列，每项含 name + [(x_value, y_value)] 列表）、source（数据来源说明）、warnings。图表类型选择由规则决定：日期 + 数值 → line（折线图），类别 + 数值 → bar（柱状图），单行单指标 → metric_card（指标卡），兜底 → table（表格）。ChartSpec 不包含任何 HTML/JS/CSS——前端负责将其渲染为原生 SVG。

**解决什么问题**

把"怎么展示数据"从"前端怎么画图"中分离出来。Agent 只负责根据数据类型推荐合适的图表类型和数据结构，不参与前端渲染。ChartSpec 的纯结构设计也确保了安全性——前端可以用 `textContent` 渲染标题和标签，避免 XSS 风险；后端不输出任何可执行代码。

**在当前项目中的位置**

- `src/chart_spec.py` — ChartSpec 生成逻辑
- `src/agent.py` — AgentResponse 中附带 chart_spec
- `harness/checks/check_chart_spec_safety.py` — 安全检查

**输入是什么**

ResultSummary 或 MergedResult（含 columns、sample_rows、metric_name 等）。

**输出是什么**

ChartSpec dataclass——纯结构化图表描述，不含任何 HTML/JS。

**出错会导致什么风险**

图表类型选择错误——日期数据选了 bar，用户无法直观看到趋势。series 数据量过大——31 天 × 10 个指标 = 310 个数据点，前端渲染性能问题。图表类型与安全策略冲突——personnel 数据不应该出现在图表中，但 chart_type 被设为了 bar。ChartSpec 中包含 HTML 片段——破坏 Web UI 的 `textContent` 安全策略。

**简单例子**

ResultSummary（2026年1月每天行程数，31行 × [date, trip_count]） → ChartSpec: chart_type=line（日期+数值），title="2026年1月出租车行程趋势"，x_field=date，y_fields=[trip_count]，series=[{name:"行程数", data:[(2026-01-01, 15234), ...]}]，warnings=[]。

**Owner 审查时应该问什么**

1. "ChartSpec 的 chart_type 选择规则有几种？如果同时有日期和类别维度，优先选哪种类型？"
2. "如何确保 ChartSpec 不输出任何 HTML/JS？Harness 检查是如何验证的？"
3. "如果 Web UI 需要新增一种图表类型（如 pie），ChartSpec 需要怎么改？"

---

## 85. 五道安全门禁体系

**一句话解释**：从请求预检到数据库只读执行的五层纵深防御——每一层独立拦截，任何一层失效都不会导致全线崩溃。

**是什么**

项目中安全不是单点检查，而是五道独立的递进门禁：

| 门禁 | 位置 | 检查内容 | 失败处理 |
|------|------|----------|----------|
| Gate 1: Request Pre-check | Step 0.5, `request_guard.py` | 写操作关键词 + Bronze/Silver 层关键词 | 直接拒绝，不进入管线 |
| Gate 2: Intent Validation | Step 2, `ir.py` | domain 枚举、metrics 注册、needs_clarification | 反问或拒绝 |
| Gate 3: SQLPlan Validation | Step 3-4, `ir.py` | 表名白名单、JOIN 白名单、strategy 枚举、downgrade_reason | 拒绝生成 SQL |
| Gate 4: SQL Safety Validation | Step 5, `sql_gen.py` (`validate_sql_safety()`) | SELECT-only、完全限定表名、Gold-only、dim_date 过滤、JOIN 白名单、禁止关键字 | 拒绝执行 SQL |
| Gate 5: DuckDB Read-Only | Step 6, `executor.py` | 数据库引擎层 `read_only=True` | 数据库引擎直接拒绝写操作 |

五道门禁的设计原则：每道门禁有独立的检查逻辑和失败处理路径；Gates 1-4 是软件层检查（纯规则，不依赖 LLM），Gate 5 是数据库引擎层检查；即使前四道全部失效，Gate 5 仍能阻止写操作；Gates 1 和 4 有部分重叠（如都检查写操作），但检查方式不同（关键词 vs SQL 解析），形成互补。

**解决什么问题**

单点安全防线被绕过（Prompt 失效、LLM 行为漂移、规则代码有 bug）时，纵深防御保证其他防线仍在生效。五道独立的防线也方便安全审计——任何一次失败都可以定位到具体是哪道门禁拦截的、其他门禁是否也触发了。

**在当前项目中的位置**

- Gate 1: `src/request_guard.py`
- Gate 2: `src/ir.py` (`QuestionIntent.validate()`)
- Gate 3: `src/ir.py` (`SQLPlan.validate()`)
- Gate 4: `src/sql_gen.py` (`validate_sql_safety()`)
- Gate 5: `src/executor.py` (DuckDB `read_only=True` 连接)
- 协调: `src/agent.py` (管线中的调用顺序)

**输入是什么**

各门禁的输入不同——Gate 1 接收原始问题文本，Gate 2 接收 QuestionIntent，Gate 3 接收 SQLPlan，Gate 4 接收 SQL 字符串，Gate 5 接收已验证的 SQL。

**输出是什么**

每道门禁独立产出 PASS/FAIL，FAIL 时附带具体违规原因。

**出错会导致什么风险**

门禁跳过（Agent 代码路径遗漏了某个 gate 的调用）→ 该防线失效。门禁重叠不足（两道门禁的检查规则完全相同）→ 一道失效则全线失效。门禁规则不一致（Gate 2 允许的 JOIN，Gate 4 却拒绝）→ 管线中出现"通过-被拒"的不一致行为，排查困难。

**简单例子**

场景一（正常）：用户问"2026年1月行程数" → Gate 1 PASS（无写操作） → Gate 2 PASS（domain=traffic 合法） → Gate 3 PASS（G3 表在白名单） → Gate 4 PASS（SQL 安全） → Gate 5 PASS（只读执行） → 返回结果。

场景二（写操作）：用户问"删除异常行程" → Gate 1 FAIL（检测到"删除"） → 拒绝，Gates 2-5 未被触发。

场景三（LLM 绕过）：假设 LLM 在 SQLPlan 中引用了 Bronze 表 → Gate 3 FAIL（表名不在白名单） → 拒绝，SQL 未生成。

场景四（代码绕过）：假设前三道全被绕过，LLM 直接 SQL 被执行 → Gate 4 FAIL（`validate_sql_safety()` 检测到 Bronze 引用）或 Gate 5 FAIL（DuckDB `read_only` 拒绝写操作）。

**Owner 审查时应该问什么**

1. "能否画一张流程图，标明五道门禁在管线中的位置和各自的失败处理路径？"
2. "如果某次 E2E 运行中 `validate_sql_safety()` 返回 PASS 但 DuckDB 仍拒绝了执行——最可能是什么原因？"
3. "哪两道门禁的检查规则有最多重叠？这种重叠是有意设计还是历史遗留？"

---

## 86. AST 层 SQL 校验

**一句话解释**：使用 sqlglot DuckDB 方言解析器对生成的 SQL 做 AST 级校验——确保单条 SELECT、函数白名单合规、无外部资源访问函数。

**是什么**

AST 层 SQL 校验是 `validate_sql_safety()` 中的一个高级检查维度。在传统的正则检查（SELECT-only、表名限定、JOIN 白名单、禁止关键字）之外，AST 校验使用 `sqlglot` 库将 SQL 字符串解析为抽象语法树，然后做三件事：① 确认只有单条 SELECT 语句（防止 `SELECT ...; DROP TABLE ...` 这类多语句攻击）；② 检查所有函数调用是否在白名单中（允许：AVG/CAST/COALESCE/COUNT/MAX/MIN/ROUND/SUM，拒绝其他所有函数）；③ 检查是否引用了外部资源访问函数（CSV_SCAN、HTTP_GET、READ_CSV、READ_PARQUET、READ_JSON、MYSQL_SCAN、POSTGRES_SCAN、SQLITE_SCAN 等，这些都是 DuckDB 支持的可能用于数据外泄的函数）。

**解决什么问题**

正则表达式检查对复杂 SQL 的覆盖有限——CTE（WITH 子句）、嵌套子查询、函数调用链、字符串中的 SQL 片段都可能绕过正则。AST 解析把 SQL 转成结构化树后做检查，覆盖所有语法变体。特别是外部资源访问函数——正则很难穷举 DuckDB 所有跨文件/跨数据库读取函数，但 AST 可以精确识别每个函数名。

**在当前项目中的位置**

- `src/sql_gen.py` — `validate_sql_safety()` 中的 sqlglot 调用
- `src/safety_policy_loader.py` — 函数白名单和禁止函数列表加载
- `harness/checks/check_sql_readonly.py` — Harness 中的 SQL 只读检查

**输入是什么**

`sql_plan_to_sql()` 生成的 SELECT SQL 字符串。

**输出是什么**

PASS（AST 解析成功，所有函数在白名单中，无多语句）或 FAIL（附带具体违规项——非法函数名、多语句检测、外部资源函数引用）。

**出错会导致什么风险**

sqlglot 解析失败（DuckDB 方言不支持某些语法）→ 正则校验作为 fallback。白名单过于严格——合法聚合函数被拒绝，正常查询报错。白名单遗漏——危险函数未列入禁止列表。AST 解析性能开销过大——复杂 SQL 解析耗时影响整体响应时间。

**简单例子**

SQL `SELECT AVG(trip_count), SUM(crash_count) FROM gold.dws_daily_trip_summary WHERE date > '2026-01-01'` → AST 解析 → 函数列表：[AVG, SUM] → 都在白名单中 → PASS。

SQL `SELECT * FROM read_csv_auto('/etc/passwd')` → AST 解析 → 函数 [read_csv_auto] → 在外部资源函数禁止列表中 → FAIL："包含禁止的外部资源访问函数: read_csv_auto"。

**Owner 审查时应该问什么**

1. "sqlglot 解析失败时的 fallback 策略是什么？是直接拒绝还是降级到正则检查？"
2. "函数白名单是否会随 DuckDB 版本升级而需要更新？更新流程是什么？"
3. "禁止的外部资源函数列表当前有多少个？新增一个 DuckDB 读文件函数后多久能更新到禁止列表中？"

---

## 87. AgentRuntime（API 生命周期管理）

**一句话解释**：FastAPI 应用中的 Agent 生命周期管理器——控制 Agent 上下线状态、序列化并发请求、包装同步调用。

**是什么**

AgentRuntime 是 API 层的 Agent 生命周期管理器。它封装了三个核心职责：① `is_online` 状态机——控制 Agent 何时接受请求（启动时离线，加载完成后上线）；② 并发控制——使用 `asyncio.Lock` 确保同一时间只有一个请求在执行（Agent 的管线是非线程安全的）；③ 线程池包装——通过 `ThreadPoolExecutor` 将 Agent 的同步 `ask()` 调用包装为异步调用，避免阻塞 FastAPI 事件循环。AgentRuntime 不修改 Agent 的管线逻辑，只在 API 层面做生命周期和并发管理。

**解决什么问题**

FastAPI 是异步框架，但 Agent 的 `ask()` 是同步方法（内部有 DuckDB 查询、LLM HTTP 调用等 I/O 操作）。直接在 async handler 中调用同步方法会阻塞事件循环。AgentRuntime 解决了"异步框架调用同步 Agent"的适配问题、并发安全问题、以及启动时 Agent 尚未就绪时的请求处理问题。

**在当前项目中的位置**

- `src/api/runtime.py` — AgentRuntime 类
- `src/api/app.py` — FastAPI 应用创建时初始化 AgentRuntime

**输入是什么**

Agent 实例 + 配置（是否 local_secure_mode、DuckDB 路径等）。

**输出是什么**

一个管理好的 Agent 运行环境——暴露 `is_online` 状态和 `ask(question)` 异步方法。

**出错会导致什么风险**

Agent 未就绪时接受请求 → 运行时崩溃或返回错误。并发锁失效 → 多个请求同时修改 Agent 内部状态 → 数据竞争。线程池耗尽 → 长时间运行的请求阻塞其他请求 → API 超时。is_online 状态管理错误 → 健康检查通过但 Agent 实际不可用。

**简单例子**

FastAPI 启动 → AgentRuntime 初始化 → 加载契约、建立 DuckDB 连接 → `is_online=True` → 健康检查 `/health` 返回 200 → 用户发送请求 → AgentRuntime.acquire() 获取锁 → `ThreadPoolExecutor` 中执行 `agent.ask(question)` → 返回结果 → 释放锁。

**Owner 审查时应该问什么**

1. "为什么 Agent 的 ask() 是同步方法但 API 层用异步？有没有计划将 Agent 改为原生异步？"
2. "并发锁导致的请求排队有没有超时机制？如果前一个请求卡住了 30 秒，后续请求是等待还是返回 503？"
3. "AgentRuntime 的健康检查除了 is_online 还检查什么？DuckDB 连接是否正常？"

---

## 88. Public Response Contract（API 公共响应契约 v1.0）

**一句话解释**：标准化的 API 响应结构——剥离 SQL、trace、API Key、数据库路径等内部信息，只暴露对外安全的字段。

**是什么**

Public Response Contract 是 AgentResponse 到对外 API 响应的转换契约。`build_public_response()` 函数从完整的 AgentResponse（含 SQL、ExecutionTrace、DuckDB 路径等内部敏感信息）中提取和重组字段，产生只对外安全的响应结构。契约明确规定：公开响应中不包含 SQL 文本、不包含 ExecutionTrace（含数据库路径）、不包含 API Key 或环境变量、不包含 DuckDB 连接信息。同时，JSON 响应的顶层字段结构是稳定的——answer、chart_spec、warnings 等字段名不可随意更改，确保 API 消费者的向后兼容性。

**解决什么问题**

内部 AgentResponse 包含大量安全敏感信息（SQL、trace、数据库路径），如果直接序列化为 API 响应，会造成严重的信息泄露。Public Response Contract 作为"内外隔离层"，确保外部调用方只能看到答案、图表和建议，看不到系统内部的执行细节。同时稳定的字段结构让 Web UI 和外部 API 消费者不因内部结构变化而崩溃。

**在当前项目中的位置**

- `src/response_contract.py` — `build_public_response()` 函数
- `src/api/schemas.py` — API 响应的 Pydantic schema
- `harness/checks/check_json_response_contract.py` — Harness 检查

**输入是什么**

AgentResponse dataclass（完整内部响应，含所有敏感字段）。

**输出是什么**

Public Response dict——只包含 answer、chart_spec、warnings、clarification/refusal 等对外安全字段。

**出错会导致什么风险**

敏感字段泄露——SQL 文本或数据库路径出现在公开响应中。字段意外缺失——`build_public_response()` 遗漏了某个应该公开的字段（如 chart_spec 为空但实际有图表数据）。字段命名不一致——AgentResponse 内部叫 `chinese_answer`，公开响应叫 `answerText`，API 消费者困惑。

**简单例子**

AgentResponse（内部）包含：question="...", intent=QuestionIntent(...), plan=SQLPlan(...), sql="SELECT ...", trace=[...], chinese_answer="2026年1月共...", chart_spec=ChartSpec(...) → `build_public_response()` → 公开响应：{answer: "2026年1月共...", chart: {...}, warnings: []}。SQL、trace、intent、plan 全部被剥离。

**Owner 审查时应该问什么**

1. "公开响应中有哪些字段？哪些内部字段被明确排除？排除清单是否有文档记录？"
2. "如果 AgentResponse 新增了一个字段，如何决定它是否应该出现在公开响应中？"
3. "Harness 的 `check_json_response_contract` 是如何验证公开响应不包含敏感字段的？"

---

## 89. API 安全体系

**一句话解释**：API 层的四重安全防护——本地 Token 认证、固定窗口限流、请求体大小限制和追加式审计日志。

**是什么**

API 安全体系是 FastAPI 服务层的安全防护组合，包含四个独立组件：

- **Local Auth**（`local_auth.py`）：基于 `X-TianShu-Token` 请求头的 Token 认证，使用 `hmac.compare_digest()` 常量时间比较防止时序攻击。在 `local_secure_mode`（fail-closed 模式）下，Token 缺失或过短时返回 503 而非 401。
- **Rate Limiting**（`local_rate_limit.py`）：固定窗口限流器，默认 30 req/min + 3 burst，超出后返回 429 + `Retry-After` 头。
- **Body Limit**（`body_limit.py`）：请求体大小限制，在 JSON 解析前检查，超出返回 413。
- **Local Audit**（`local_audit.py`）：追加式 JSONL 审计日志写入器，自动脱敏 20+ 敏感字段（token、question、answer、SQL、trace、database path 等）。

**解决什么问题**

没有 API 安全层的 Agent 直接暴露等同于把所有内部能力无保护地开放。四重防护各司其职：认证防止未授权访问、限流防止滥用、体量限制防止内存溢出、审计日志提供事后追溯和合规支持。

**在当前项目中的位置**

- `src/api/local_auth.py` — Token 认证中间件
- `src/api/local_rate_limit.py` — 限流中间件
- `src/api/body_limit.py` — 请求体大小限制
- `src/api/local_audit.py` — 审计日志
- `src/api/app.py` — 中间件注册
- `config/api_config.yml` — 安全配置

**输入是什么**

HTTP 请求——Token（header）、请求体、请求频率、请求路径。

**输出是什么**

放行（正常请求）、401/403（认证失败）、429（限流）、413（体量过大）、503（fail-closed 模式下 Agent 未就绪）。

**出错会导致什么风险**

Token 使用非恒定时间比较 → 时序攻击可推断有效 Token。限流器窗口边界突刺 → 窗口交界处请求突发绕过限制。审计日志写入失败导致请求被拒绝 → 安全 vs 可用性的取舍（当前选择 fail-open：记录失败日志但放行请求）。审计脱敏遗漏 → Token 或 SQL 被写入审计日志明文。

**简单例子**

用户发送请求 → Body Limit 中间件检查 Content-Length < 512KB ✓ → Local Auth 中间件验证 `X-TianShu-Token` ✓ → Rate Limiter 检查当前窗口 15/30 ✓ → 请求到达 AgentRuntime → Agent 处理 → Local Audit 写入脱敏后的请求记录 → 返回响应。

**Owner 审查时应该问什么**

1. "local_secure_mode 开启和关闭的区别是什么？什么场景下应该开启 fail-closed？"
2. "审计日志的自动脱敏是否覆盖了所有敏感字段？脱敏是黑名单模式还是白名单模式？"
3. "限流器的窗口大小和 burst 值是如何确定的？是否经过压测验证？"

---

## 90. MetricResolver（指标解析引擎）

**一句话解释**：基于规则的指标解析引擎，用五级优先级链将用户中文问题中的指标表述匹配到已注册指标。

**是什么**

MetricResolver 是指标解析的核心组件。它接收用户中文问题中提取的指标关键词，通过五级优先级链匹配到 Metric Registry 中的已注册指标：

| 优先级 | 匹配方式 | 置信度 |
|--------|----------|--------|
| 1 | metric_name（英文指标名精确匹配） | 1.00 |
| 2 | zh_name（中文指标名精确匹配） | 0.98 |
| 3 | synonym（同义词匹配） | 0.93 |
| 4 | alias（别名匹配） | 0.90 |
| 5 | keyword（关键词模糊匹配） | 0.82 |

高优先级匹配命中后停止向下搜索。多候选时标记为 ambiguous 并触发反问（如"金额"同时匹配到 trip_fare、fine_amount、tif_amount）。匹配结果返回 `MetricMatchResult` dataclass，包含 matched 标记、matched MetricInfo、confidence、ambiguity 标记、candidates 列表和 clarification_message。

**解决什么问题**

中文自然语言中指标表述多样——"行程数""跑了几趟""出行量"都指 trip_count。硬编码关键词映射无法覆盖所有变体。MetricResolver 通过五级匹配 + 置信度评分 + 歧义检测，在精确性和覆盖率之间取得平衡。

**在当前项目中的位置**

- `src/metric_resolver.py` — 解析引擎
- `src/metric_catalog.py` — 指标目录（Resolver 的数据源）
- `src/ambiguity.py` — 歧义检测与反问生成

**输入是什么**

从用户问题或 Intent 中提取的指标文本（字符串或字符串列表）+ MetricCatalog。

**输出是什么**

MetricMatchResult——包含匹配成功/失败、匹配指标信息、置信度、歧义标记、候选列表、反问建议。

**出错会导致什么风险**

误匹配——把"金额"匹配到 trip_fare 而实际用户想问罚款金额 → 查询了错误的指标。漏匹配——已注册指标的关键词覆盖不足 → 合法查询被反问或拒绝。歧义漏检——多个候选时未触发反问（ambiguous=false）→ Agent 猜测指标，用户得到口径错误的结果。

**简单例子**

用户问"2026年1月每天跑了多少单？" → MetricResolver 解析"跑"→ 关键词匹配到 trip_count（keyword 优先级 0.82）→ single candidate → 非歧义 → MetricMatchResult{matched=true, metric=trip_count, confidence=0.82}。

用户问"2026年1月金额" → MetricResolver 解析"金额"→ 匹配到三个候选：trip_fare(0.82)、fine_amount(0.82)、tif_amount(0.82) → 多候选 → ambiguous=true → 触发反问："'金额'可能指车费、罚款或TIF费用，请问您要查询哪个？"

**Owner 审查时应该问什么**

1. "五级匹配优先级的设计依据是什么？keyword 匹配的误匹配率是否过高？"
2. "新增一个指标后，需要同步更新哪些资源——zh_name、synonym、alias、keyword？"
3. "当 confidence 低于某个阈值时，是否应该强制触发反问？当前有这个机制吗？"

---

## 91. MetricCatalog（指标目录）

**一句话解释**：所有已注册指标的唯一数据源——支持 DuckDB 实时查询、快照文件和契约文件三种加载方式。

**是什么**

MetricCatalog 是项目中指标的"单一事实来源"（Single Source of Truth）。它从三个可能的数据源之一加载指标定义：① DuckDB `meta.metric_definitions` 表（实时、最权威）；② Metric Registry 快照文件（离线场景）；③ `metric_contract.yml` 契约文件（静态配置）。Catalog 加载后进行校验（指标名唯一性、必填字段完整性、G3 表引用有效性），然后提供查询接口：按名称查询、按 domain 查询、按表名查询、按关键词搜索。Catalog 还支持导出快照（用于离线测试和 CI）。

**解决什么问题**

指标定义分散在多个文件中（DuckDB 表 + YAML 契约 + Prompt 模板 + fixture），任何一个不同步都会导致 Agent 行为异常。MetricCatalog 作为统一入口，所有组件（Agent、Resolver、Harness、Prompt Loader）都从 Catalog 获取指标信息。

**在当前项目中的位置**

- `src/metric_catalog.py` — MetricCatalog 类
- `src/metric_resolver.py` — 消费方
- `harness/checks/check_metric_registered.py` — Harness 检查

**输入是什么**

数据源类型（duckdb/snapshot/contract）+ 对应连接配置。

**输出是什么**

已加载并校验的指标列表（List[MetricInfo]）+ 查询接口。

**出错会导致什么风险**

三个数据源不一致——DuckDB 中 `trip_count` 字段名为 `total_trips`，但契约中写的是 `trip_count` → SQL 执行失败。加载失败无 fallback —— DuckDB 不可用时直接崩溃，未降级到快照或契约文件。校验过于严格——"备注"字段缺失被当作致命错误拒绝加载。

**简单例子**

启动时 `MetricCatalog.load("duckdb", conn)` → 从 DuckDB `meta.metric_definitions` 表查询 → 返回 15 个已注册指标 → 校验通过 → MetricResolver 使用 Catalog 进行指标匹配。

**Owner 审查时应该问什么**

1. "三个数据源的优先级顺序是什么？如果 DuckDB 和契约文件都有数据但不一致，哪个为准？"
2. "Catalog 加载失败时的 fallback 策略是什么？"  
3. "如何验证 DuckDB 中的指标定义与 metric_contract.yml 同步？有没有自动化检查？"

---

## 92. Result Fusion（LLM 融合 + 模板融合）

**一句话解释**：将多个 SubIntent 的执行结果合并为一条中文解释——支持 LLM 驱动的自然语言融合和规则驱动的模板拼接两种模式。

**是什么**

Result Fusion 是多指标查询的最后一步——将多个 SQLResult（经 ResultSummary 摘要后）合并成一条自然语言回答。有两种融合模式：

- **LLM Fusion**（可选，默认关闭）：将 ResultSummary/MergedResult 的结构化数据发送给 LLM，由 LLM 生成自然语言融合解释。LLM 只看到 ResultSummary（指标名、维度、行数、样本行），看不到 SQL、DuckDB 或原始数据。失败时 fallback 到 Template Fusion。
- **Template Fusion**（默认）：基于预定义模板的规则拼接——每个 SubIntent 的结果用统一格式描述（"X 月 Y 指标为 Z"），然后按维度对齐拼接。安全可控、确定性高、不消耗 LLM Token。

两种模式都在 `CrossDomainPolicy` 约束下运行——禁止因果语言、禁止人员敏感字段、标注金额口径警告。

**解决什么问题**

多指标查询不能只返回三个表格让用户自己看。Fusion 把"行程数 31 行 + 事故数 28 行 + 停车罚单 31 行"变成一条自然语言："2026 年 1 月，出租车行程共 XXX 次（日均 XXX），事故共 XXX 起（日均 XXX），停车罚单共 XXX 张（日均 XXX）"。同时模板模式保证了在不依赖 LLM 时也能产出合理的解释。

**在当前项目中的位置**

- `src/result_fusion.py` — 融合逻辑
- `prompts/result_fusion.md` — LLM Fusion Prompt 模板
- `harness/checks/check_result_fusion_safety.py` — Harness 检查

**输入是什么**

ResultSummary 列表 / MergedResult + CrossDomainDecision + 融合模式配置。

**输出是什么**

中文自然语言解释字符串（含跨域警告和口径标注）。

**出错会导致什么风险**

LLM Fusion 中生成了因果语言（"事故导致行程减少"）→ 违反了 CrossDomainPolicy 的因果语言禁止规则。LLM Fusion 中编造了 ResultSummary 中不存在的数据 → 虚假信息。Template Fusion 模板过于死板 → 解释文本像机器翻译，用户体验差。Fusion 失败时无声降级 → 返回了空字符串或原始数据行而非自然语言解释。

**简单例子**

两个 SubIntent 结果：① 行程数 31 天，日均 15234；② 事故数 28 天，日均 3.2 → Template Fusion 生成："2026 年 1 月，出租车行程共 472,254 次，日均 15,234 次。同期事故共 90 起，日均 3.2 起（3 天无事故数据）。注意：行程数与事故数来自不同业务系统，二者无直接因果关系。"

**Owner 审查时应该问什么**

1. "LLM Fusion 和 Template Fusion 的切换条件是什么？什么场景下应该用 LLM Fusion？"
2. "如何确保 LLM Fusion 严格遵守 CrossDomainPolicy 的因果语言禁止规则？"
3. "Template Fusion 的模板放在哪里？是否有覆盖率指标证明模板能处理所有常见场景？"

---

## 93. Grain Detection（时间粒度检测）

**一句话解释**：从 SQLResult 的日期列推断时间粒度——daily（日）、monthly（月）、unknown（未知）。

**是什么**

Grain Detection 是 ResultSummary 生成过程中的一个分析步骤。它检查 SQLResult 中日期列的值序列，计算连续日期的间隔：间隔为 1 天 → grain=daily；间隔为约 1 月 → grain=monthly；无法推断 → grain=unknown。Grain 决定了后续处理：只有 daily 粒度的多个结果才能做 Date Merge（日期对齐）；grain=unknown 时跳过合并，直接使用独立的 Template Fusion。

**解决什么问题**

不同查询的粒度可能不同——"2026年1月每天行程数"是 daily，"2026年每月行程数"是 monthly。如果不检测粒度，Date Merge 会把 monthly（12 行）和 daily（365 行）按天对齐，产生大量无意义的 None 填充。Grain Detection 提供前置判断——只对同粒度的结果做合并。

**在当前项目中的位置**

- `src/result_summary.py` — Grain 检测逻辑
- `src/result_merge.py` — 合并前检查 grain 一致性

**输入是什么**

SQLResult 中日期列的排序值列表。

**输出是什么**

grain 字符串：daily / monthly / unknown。

**出错会导致什么风险**

Daily 误判为 monthly → 日期合并被跳过，本应对齐的数据变成了独立展示。Monthly 误判为 daily → Date Merge 产生大量空值行。单行数据无间隔 → 无法推断 grain → 正确处理为 unknown。日期列存在 NULL 或乱序 → 间隔计算错误 → grain 误判。

**简单例子**

日期序列 [2026-01-01, 2026-01-02, 2026-01-03, ...] → 间隔 = 1 天 → grain=daily ✓。日期序列 [2026-01-01, 2026-02-01, 2026-03-01] → 间隔 = 31/28 天 → grain=monthly ✓。只有一行数据 → grain=unknown → 不参与日期合并。

**Owner 审查时应该问什么**

1. "Grain Detection 是否支持 weekly 和 yearly？如果不支持，遇到这些粒度会怎么处理？"
2. "如果日期列不是严格排序的（如 01-03, 01-01, 01-02），Grain Detection 会怎么处理？"
3. "Grain Detection 错误是否会导致图表类型选择错误？它们之间有什么依赖关系？"

---

## 94. Fail-Closed Pattern（默认拒绝安全模式）

**一句话解释**：安全配置缺失或异常时，系统默认拒绝操作而非默认放行——"不确定是否安全就拒绝"。

**是什么**

Fail-Closed 是项目中的系统性安全设计原则。当安全配置（contracts、policy YAML、whitelist）无法加载或缺失时，系统不会退化到"无约束运行"，而是直接拒绝所有操作。典型 fail-closed 场景：契约文件不存在 → Agent 启动失败，不进入就绪状态；`sql_safety_policy.yml` 无法加载 → 所有 SQL 执行被拒绝；API `local_secure_mode=true` 但 Token 缺失 → 返回 503 而非 401（不让外部探测 Token 有效性）；JOIN 白名单为空 → 所有 JOIN 被拒绝（而非全部放行）。Fail-Closed 与默认拒绝的语义：不清楚 = 不允许。

**解决什么问题**

安全系统失效时最危险的行为是"静默放行"——安全配置丢了，但系统还在正常运行，只是所有的安全约束都消失了。Fail-Closed 把"异常状态"变成"安全状态"——宁可服务不可用，也不在无安全约束下运行。

**在当前项目中的位置**

- `src/resolver.py` — 契约加载失败 → 异常
- `src/safety_policy_loader.py` — 安全策略加载失败 → 异常
- `src/api/local_auth.py` — fail-closed token 检查
- `src/api/runtime.py` — Agent 未就绪时拒绝请求

**输入是什么**

无——这是一个设计原则，体现在多个模块的错误处理逻辑中。

**输出是什么**

当安全前提不满足时：服务不可用（返回 503）、操作被拒绝（抛出异常）、绝不静默退化。

**出错会导致什么风险**

Fail-Closed 过于激进 → 网络抖动导致配置加载超时 → 服务完全不可用，影响面过大。Fail-Closed 不一致 → 某处契约缺失时系统拒绝，另一处相似场景却静默放行。Fail-Closed 的返回值设计不当 → 不同模块拒绝时返回不同的错误码和消息 → API 消费者困惑。

**简单例子**

场景一（Fail-Closed 正确）：`sql_safety_policy.yml` 文件被误删 → `safety_policy_loader` 抛出 FileNotFoundError → Agent 初始化失败 → `is_online=False` → API 返回 503 → 所有查询被拒绝 → 数据安全守住。

场景二（如果 Fail-Open 错误）：`sql_safety_policy.yml` 被误删 → 系统加载空安全策略 → 无表名白名单、无 JOIN 白名单、无禁止关键字 → 所有 SQL 都被放行 → 安全边界完全失效。

**Owner 审查时应该问什么**

1. "项目中哪些模块采用 Fail-Closed？哪些采用 Fail-Open？Fail-Open 的模块是否有额外的补偿控制？"
2. "Fail-Closed 导致的'服务不可用'是否有监控告警？如何区分'被攻击'和'配置错误'？"
3. "有没有全局的 Fail-Closed 检查确保新增模块也遵循这个原则？"

---

## 95. Memory Rule（记忆规则 TA-Rxxx）

**一句话解释**：从真实 LLM 失败中沉淀的可执行规则——有唯一编号（TA-Rxxx）、生命周期状态和阻断标记，写入 `memory_rules.yml` 并由 Harness + pytest 自动验证。

**是什么**

Memory Rule 是项目中"从失败中学习"的机制化产物。每条规则有：唯一编号（`TA-Rxxx` 格式，TA = Text2SQL Agent）、规则内容（中文描述，说明应该怎么做）、来源（关联的经验复盘编号和风险编号）、生命周期状态（proposed → active → deprecated → superseded）、blocking 标记（true=快速门禁阻断）、以及 required_paths（实施需要的文件：harness_check、test、eval、prompt）。规则不只是一段文字——每条 active + blocking=true 的规则必须有对应的自动化检查、测试用例和评测用例，在 CI 中可验证。

**解决什么问题**

真实 LLM 失败中蕴含着宝贵的经验（如"模糊时间应反问"、"金额口径不清应反问"），但如果只修一次 Prompt、不沉淀为规则，同类问题会在后续 Prompt 版本或模型切换中复发。Memory Rule 把这些经验变成可执行、可验证、有编号、可追溯的长期资产。

**在当前项目中的位置**

- `docs/memory/memory_rules.yml` — 规则库
- `harness/memory_*.py` — 规则的"提出→审查→晋升→验证"全流程
- `docs/memory/经验复盘.md` — 规则的经验来源
- `docs/memory/风险清单.md` — 规则关联的风险

**输入是什么**

真实 LLM 回归/E2E Eval 失败 → Memory Suggestion（Step 11 自动提取）→ 人工审查（Step 12）→ 审批决策（人工）。

**输出是什么**

`docs/memory/memory_rules.yml` 中的正式规则条目 + 对应的自动化检查、测试和评测用例。

**出错会导致什么风险**

规则过时未清理 → 大量 deprecated 规则堆积，活跃规则被淹没。规则与实施脱节 → blocking=true 但实际没有对应的自动化检查。规则编号冲突 → 两个不同规则使用相同 TA-Rxxx 编号。规则库膨胀 → 规则数超过 100 但 90% 是 low priority → 失去焦点。

**简单例子**

经验复盘 R013："LLM 对模糊时间'最近'的反问约束不足，连续多次回归中 clarification_expected_but_answered" → 提炼为 Rule TA-R025："时间范围模糊时必须反问" → 状态 active → blocking=true → required_paths: harness_check（检查反问率），test（pytest 验证反问逻辑），eval（ambiguous_questions.yml 中增加模糊时间 case），prompt（intent_classifier.md 中强化反问约束）。

**Owner 审查时应该问什么**

1. "当前 memory_rules.yml 中有多少条规则？active 比例是多少？blocking=true 的有多少？"
2. "一条 rule 从 proposed 到 active+blocking=true 需要经过哪些步骤？谁来审批？"
3. "如何确保 blocking=true 的规则都有对应的自动化验证？有没有 Harness 检查专门验证这一点？"

---

## 96. Memory Promotion（规则晋升流程）

**一句话解释**：Memory Rule 从提出到阻断的全生命周期流程——proposed → active → blocking=true，每步需要特定的审批和实施条件。

**是什么**

Memory Promotion 是规则晋升的标准化流程。一条 Memory Rule 从诞生到成为 CI 阻断规则需经过：

1. **Step 11（Suggestion 生成）**：从 Runtime LLM Baseline 失败中自动提取 candidate → 初始状态 proposed, 置信度 L2
2. **Step 12（人工审查）**：按 Review SOP 五维度审查 → 标记 accept_as_memory_rule_candidate / reject
3. **Step 13（Promotion Validation）**：检查晋升条件——必要的 check/test/eval/prompt 是否齐全、rule ID 是否唯一、引用是否有效、状态转换是否合法
4. **Step 14（Patch Proposal）**：根据审批决策生成代码/配置修改草案（只写不改）→ 人工合入
5. **Promotion 到 active**：所有 required_paths 的文件都已到位 → 快速门禁中自动验证 → 状态变更为 active
6. **Promotion 到 blocking=true**：规则在 active 状态下稳定运行（连续 N 次 CI 通过）→ 人工审批后设置 blocking=true → CI 失败时阻断合并

晋升过程中的关键约束：proposed 不能设 blocking=true；active + blocking=true 必须有完整的 check/test/eval 配套；deprecated/superseded 自动失去 blocking 能力。

**解决什么问题**

防止规则被"随口一说"就设为阻断——proposed 阶段的规则只是候选，没经过人工审查和自动化验证前不能影响 CI。防止规则实施不完整——blocking=true 但没有对应的检查代码，CI 形同虚设。防止规则库腐烂——deprecated/superseded 机制让过时规则被正式废弃。

**在当前项目中的位置**

- `harness/memory_promotion.py` — 晋升逻辑
- `harness/memory_promotion_validation.py` — Step 13 晋升条件验证
- `harness/run_memory_rule_promotion.py` — 晋升运行器
- `harness/run_memory_promotion_validation.py` — 验证运行器

**输入是什么**

Memory Rule Candidate（来自 Step 11）+ 人工 Review Decision（来自 Step 12）+ 审批决策文件。

**输出是什么**

晋升后的规则状态更新 + Promotion Validation 报告（验证通过/失败，缺失的 required_paths 列表）。

**出错会导致什么风险**

跳过审查直接 promotion → 质量低下的规则进入 active 状态。缺少 required_paths 但 promotion 成功 → blocking=true 的设置是空壳，CI 不会真正验证。Promotion Validation 自身有 bug 导致假 PASS → 不合规的规则被错误晋升。Promotion 回退机制缺失 → 已晋升的规则发现有问题时无法快速降级。

**简单例子**

Rule TA-R030（proposed, 来源: intent_write_refusal 连续 5 次失败）→ Step 12 审查 accept → Step 13 Validation: check_required ✓, test_required ✓, eval_required ✓ → Promotion 获批 → 状态 active, blocking=false → 稳定运行 2 周 → 人工审批 → 状态 active, blocking=true → CI 中 intent_write_refusal 失败会阻断合并。

**Owner 审查时应该问什么**

1. "Promotion Validation 检查哪些条件？规则的完整 required_paths 清单是什么？"
2. "从 proposed 到 blocking=true 的最小时间是多少？有没有快速通道（如安全红线）？"
3. "如何降级一条 blocking=true 的规则？降级流程是否和晋升流程同样严格？"

---

## 97. CRCS（代码审查分级体系）

**一句话解释**：三级代码审查分类——A 级（安全变更/安全关键路径）、B 级（架构变更/多文件链式影响）、C 级（局部重构/文案/配置），不同级别有不同的审查要求和变更传播义务。

**是什么**

CRCS（Code Review Classification System）是项目的代码变更分级体系，定义在 `../TianShu/contracts/crcs_policy.yml` 中。它把每次代码变更分为三级：

- **A 级（安全变更）**：涉及安全关键路径——`agent.py` 安全路径、`sql_gen.py`、`ir.py` 的 `validate()` 方法、`request_guard.py`、`safety_policy_loader.py`、`harness/checks/` 中的安全检查、Prompt 中的安全约束。A 级变更必须触发：全套安全回归 + 双基线重新固化 + 安全 Owner 审批。
- **B 级（架构变更）**：涉及多文件链式影响——新增 IR 字段、修改管线步骤顺序、新增 Harness 检查类别、新增 Prompt Stage。B 级变更必须触发：变更传播矩阵检查 + 相关 fixture/eval 同步更新。
- **C 级（局部变更）**：单文件内重构、文案修改、配置调整、注释翻译。C 级变更只需要基本 CI 通过。

CRCS 还关联了变更传播矩阵——规定了"改了文件 X 就必须同步检查文件 Y Z W"的依赖关系。

**解决什么问题**

不理解变更影响的代码审查容易出现两类极端：所有变更都用同一标准审查（安全红线变更和注释修改被同等对待）→ 安全变更被低估；或反过来，改一行日志也要触发全套回归 → 开发效率极低。CRCS 分级让审查重点聚焦在真正的安全风险上，同时不遗漏架构级变更的链式影响。

**在当前项目中的位置**

- `../TianShu/contracts/crcs_policy.yml` — 分级定义和触发规则
- `AGENTS.md` Section 8 — 变更传播矩阵
- （CRCS 检查的自动化 Harness 检查待实现）

**输入是什么**

代码变更的 diff——变更涉及的文件列表和变更性质。

**输出是什么**

变更分级（A/B/C）+ 对应的检查清单和审批要求。

**出错会导致什么风险**

A 级变更被误标为 C 级——安全关键代码变更只跑了基本 CI，安全边界可能被突破。C 级变更被误标为 A 级——浪费审查资源。分级标准模糊——不同人把同类变更分到不同级别。变更传播矩阵过时——新增了文件依赖关系但矩阵未更新。

**简单例子**

变更：修改 `src/sql_gen.py` 的 `sql_plan_to_sql()` 函数 → CRCS A 级（安全关键路径）→ 触发：全套 pytest + harness + mock 回归 + Prompt 回归 + E2E eval + 安全 Owner 审批 + 双基线重新固化。

变更：在 `src/utils.py` 中新增一个日期格式校验函数，并在 `src/llm_pipeline.py` 中引用 → CRCS B 级（架构变更，涉及多文件链式影响）→ 触发：fixture 同步检查 + 变更传播矩阵验证。

变更：翻译 `src/agent.py` 中的英文注释为中文 → CRCS C 级 → 只需要基本 CI 通过。

**Owner 审查时应该问什么**

1. "A/B/C 三级的判定标准是否有文档化的 checklist？是人工判定还是自动化判定？"
2. "安全关键路径的文件列表是否与 CRCS A 级定义一致？新增安全关键文件时谁负责更新 CRCS？"
3. "变更传播矩阵当前覆盖了多少条依赖关系？如何确保矩阵始终与实际代码依赖同步？"

---

## 98. Web UI（本地问答 Web 界面）

**一句话解释**：Phase 7 的本地自然语言问答 Web 界面——纯原生 HTML/CSS/JS、原生 SVG 图表、严格 CSP、`textContent` 防 XSS。

**是什么**

Web UI 是项目的前端界面（Phase 7 产物）。它不是基于 React/Vue 的 SPA，而是纯原生 HTML + CSS + JS 的单页面应用。核心设计原则：① 原生 SVG 图表渲染（根据 ChartSpec 的 chart_type 动态生成 line/bar/metric_card/table 四种 SVG 图表，不依赖 ECharts/D3 等第三方库）；② 严格 CSP（Content Security Policy：禁止 inline script、禁止 eval、限制资源来源）；③ `textContent` 防 XSS（所有用户数据插入 DOM 时使用 `textContent` 而非 `innerHTML`，即使 ChartSpec 中混入了 HTML 标签也不会被执行）；④ Token 仅在内存中（不写入 localStorage/sessionStorage/cookie）。

**解决什么问题**

提供一个可直接使用的本地问答界面，无需额外安装前端框架或外部依赖。原生 SVG 方案在保证功能的同时，最大化了安全性——不加载任何第三方 JS，严格 CSP 限制代码执行入口，`textContent` 确保即使后端返回了恶意内容也不会在前端执行。

**在当前项目中的位置**

- `src/api/app.py` — FastAPI 同时 serve API 和 Web UI 静态文件
- Web UI 静态文件（HTML/CSS/JS）位置待确认
- `src/chart_spec.py` — ChartSpec 生成（Web UI 渲染的数据源）

**输入是什么**

用户在浏览器中输入的中文自然语言问题（通过 fetch API 发送到后端 `/api/ask`）。

**输出是什么**

包含自然语言答案和 SVG 图表的 Web 页面——折线图（日期趋势）、柱状图（分类对比）、指标卡（单值+标题）、表格（通用兜底）。

**出错会导致什么风险**

ChartSpec 中包含 HTML 片段 → 如果前端用 `innerHTML` 渲染 → XSS 漏洞（但 `textContent` 策略防止了这一点）。CSP 配置不当 → 允许了 unsafe-inline → inline script 可执行。图表数据点过大（1000+ 点）→ SVG 渲染性能问题。前端直接暴露后端错误信息（SQL 文本、数据库路径）→ 信息泄露。

**简单例子**

用户在浏览器中输入"2026年1月每天行程数" → JS 发送 fetch → API 返回 {answer: "2026年1月共...", chart: {type: "line", title: "...", series: [...]}} → 前端解析 ChartSpec → 动态创建 SVG line chart → 渲染到页面。

**Owner 审查时应该问什么**

1. "Web UI 的 CSP 策略具体配置了哪些指令？是否禁用了所有外部资源加载？"
2. "如果 ChartSpec 中意外包含了 `<script>` 标签，前端的 `textContent` 策略如何防止执行？有没有自动化测试验证？"
3. "Web UI 的冒烟测试覆盖了哪些场景？是否包含安全相关的测试（如 XSS 注入、图表类型错误）？"

---

## 99. Execution Strategy & Execution Mode（执行策略与执行模式）

**一句话解释**：SQLPlan 的查询策略枚举和执行模式枚举——G3 直查、G3 跨表、G2 降级等策略，以及 single/serial/parallel/offline 执行模式。

**是什么**

**Execution Strategy** 是 SQLPlan 的 `strategy` 字段的枚举值，定义了"从哪里查"：

| Strategy | 含义 | 说明 |
|----------|------|------|
| `g3_direct` | G3 单表直查 | 优先路径，直接查 G3 汇总表 |
| `g3_cross` | G3 跨表 JOIN | 需要 JOIN 多张 G3 表 |
| `g2_fact` | G2 单事实表降级 | G3 无法满足，降级到 G2 事实表 |
| `g2_fact_join` | G2 事实表 + JOIN 降维表 | G2 需要 JOIN 维度表 |
| `g0_dim_direct` | 纯维度表查询 | 只查 dim_date、dim_taxi_zone 等维度表 |
| `need_clarification` | 信息不足需反问 | 无法确定策略 |
| `unsupported_multi_plan` | 不支持的多计划组合 | 超出当前能力范围 |

**Execution Mode** 是 `AgentResponse.execution_mode` 字段，定义了多个 SQLPlan 如何执行：

| Mode | 含义 |
|------|------|
| `single` | 只有一条 SQLPlan，单次执行 |
| `serial` | 多条 SQLPlan，串行执行（默认） |
| `parallel` | 多条 SQLPlan，并行执行 |
| `offline` | 不可执行（如只做规划不执行） |

**解决什么问题**

Strategy 枚举让 LLM 不必输出自由文本描述查询方式——枚举值可直接被 `sql_plan_to_sql()` 作为分支判断依据。Execution Mode 让管线知道如何处理多条 SQLPlan：串行保证顺序和资源可控，并行减少总耗时（未来支持），offline 支持只规划不执行的场景。

**在当前项目中的位置**

- `src/ir.py` — Strategy 和 ExecutionMode 枚举定义
- `src/execution_strategy.py` — 策略选择辅助
- `src/plan_executor.py` — 多计划执行调度
- `harness/checks/check_execution_strategy_safety.py` — 安全检查

**输入是什么**

Strategy：由 LLM SQLPlan 阶段或规则版 planner 根据指标、表结构和层级策略选择。Execution Mode：由 Agent 根据 SubIntent 数量和配置决定。

**输出是什么**

Strategy：SQLPlan 的 `strategy` 字段值。Execution Mode：AgentResponse 的 `execution_mode` 字段值。

**出错会导致什么风险**

G3 可用但选了 G2 → 性能浪费+口径不一致。G3 不可用但选了 g3_direct → SQL 执行失败。g3_cross 引用了不在 JOIN 白名单中的表对 → 安全违规。Execution Mode 选为 parallel 但内部状态非线程安全 → 数据竞争。

**简单例子**

SQLPlan: strategy=g3_direct, primary_table=gold.dws_daily_trip_summary → `sql_plan_to_sql()` 走 G3 直查分支 → 简单 SELECT + JOIN dim_date → 高效执行。SQLPlan: strategy=g2_fact_join, primary_table=gold.fact_crashes, joins=[gold.dim_date, gold.dim_vehicle], downgrade_reason="G3 表中无 crash_severity 字段" → `sql_plan_to_sql()` 走 G2 降级分支 → 多表 JOIN → 可审计的降级查询。

**Owner 审查时应该问什么**

1. "当前支持的 strategy 枚举中，哪些已实现？哪些预留？g3_cross 和 g2_fact_join 的 JOIN 白名单是否独立？"
2. "Execution Mode 从 serial 升级到 parallel 的前提条件是什么？需要解决哪些并发安全问题？"
3. "unsupported_multi_plan 和 need_clarification 的界限是什么？什么场景应该反问而非标记为不支持？"

---

## 100. 项目缩写速查

**一句话解释**：项目中常见缩写、编号格式和命名约定的集中索引。

**是什么**

项目中有大量缩写和编号格式，分散在文档、代码和配置中。本节提供集中索引：

| 缩写/格式 | 全称/含义 | 首次出现位置 |
|-----------|-----------|-------------|
| **TA-Rxxx** | Text2SQL Agent Rule（记忆规则编号） | `docs/memory/memory_rules.yml` |
| **RISK-xxx** | 风险项编号 | `docs/memory/风险清单.md` |
| **B-x / C-x** | 历史 Bug / 改进追踪编号 | `docs/memory/经验复盘.md` |
| **DWS_** | Data Warehouse Summary（G3 汇总表前缀） | 数据库表名 |
| **FACT_** | Fact Table（G2 事实表前缀） | 数据库表名 |
| **DIM_** | Dimension Table（维度表前缀） | 数据库表名 |
| **G3 / G2 / G1 / G0** | Gold 汇总层 / Gold 事实层 / Silver 层 / Bronze 层 | 数仓分层 |
| **TIF** | Taxi Improvement Fund（出租车改善基金，Supply 域指标） | `metric_contract.yml` |
| **IR** | Intermediate Representation（中间表示三层模型） | `src/ir.py` |
| **MVP** | Minimum Viable Product（规则版最小可用链路） | `src/agent.py` mode="rule" |
| **E2E** | End-to-End（端到端评测） | `evals/e2e_cases.yml` |
| **CSP** | Content Security Policy（Web UI 安全策略） | Web UI |
| **JSONL** | JSON Lines（一行一个 JSON 对象，审计日志格式） | `src/api/local_audit.py` |
| **Run ID** | UTC 时间戳运行标识符（格式 `YYYYMMDDThhmmssZ`） | `src/llm_pipeline.py` |
| **Commit SHA** | Git commit 哈希（完整 40 位或短码 7 位） | 双基线报告 |
| **local_secure_mode** | API fail-closed 安全模式 | `config/api_config.yml` |
| **extra_forbidden_keywords** | 额外禁止的 SQL 关键字（在契约的 19 个默认关键字之外） | `config/agent_config.yml` |

**解决什么问题**

新人阅读代码和文档时频繁遇到不熟悉的缩写，查无出处。速查表提供"一站式索引"——看到 TA-Rxxx 就知道去 memory_rules.yml 找，看到 DWS_ 就知道是 G3 汇总表。

**在当前项目中的位置**

分散在各文件中——缩写本身出现在各自的使用位置，速查表汇总在本文档中。

**输入是什么**

无——这是元信息索引。

**输出是什么**

一个可搜索的缩写对应表。

**出错会导致什么风险**

缩写被误用（如用 TA-R 编号标记风险项而非规则）→ 追踪混乱。新缩写未登记 → 文档搜索不到含义。同一缩写在不同模块含义不同 → 沟通歧义。

**简单例子**

代码注释中看到 `# 参见 RISK-025: LLM 可能绕过 Prompt 拒绝约束` → 查速查表：RISK-xxx = 风险项编号 → 去 `docs/memory/风险清单.md` 搜索 `RISK-025` → 找到完整风险描述和缓解措施。

**Owner 审查时应该问什么**

1. "速查表是否做到了'见名知出处'——只看缩写就能定位到对应文件？"
2. "新缩写引入时，更新速查表的流程是什么？谁来负责？"
3. "是否有废弃的缩写（如旧表名）仍残留在代码中但未在速查表中标注为 deprecated？"
