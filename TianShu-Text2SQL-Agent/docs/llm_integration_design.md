# LLM 接入设计

## 目标

第二阶段先完成 Prompt 模板和 LLM 接口设计，不直接接真实 API。目标是让 LLM 只在受控边界内生成结构化中间结果，现有规则版 MVP、IR 校验、SQL 安全校验和 DuckDB 只读执行链路继续保留。

## 接入顺序

1. `intent_classifier`：中文问题转 `QuestionIntent`。
2. `sql_planner`：`QuestionIntent` 和上下文转 `SQLPlan`。
3. `sql_generator`：`SQLPlan` 转只读 SQL。
4. `explainer`：`SQLResult` 转中文解释。

优先接前两层，因为它们输出结构化 IR，风险更容易被校验拦截。SQL 生成器和解释器放后面接入。

## 安全边界

- LLM 不允许直接执行 SQL。
- LLM 不能绕过 `QuestionIntent.validate()`、`SQLPlan.validate()` 和 `validate_sql_safety()`。
- LLM 不能编造未注册指标、未登记表或未批准 JOIN。
- 任何日期过滤必须通过 `gold.dim_date`。
- 写操作、Bronze/Silver 直查、金额歧义和模糊时间必须保持反问或拒绝。

## 当前交付

- `prompts/intent_classifier.md`
- `prompts/sql_planner.md`
- `prompts/sql_generator.md`
- `prompts/explainer.md`
- `src/llm.py`

`src/llm.py` 只提供协议、请求/响应结构、Prompt 加载器和 `FakeLLMClient`。真实 API 客户端将在下一步实现。

## 后续接 API 的建议

先实现 `LLMClient` 的真实适配器，再用 fixture 测试验证模型输出能被解析为 IR。真实 API 输出必须先通过 JSON 解析和 schema 校验，再进入 Agent 主流程。
