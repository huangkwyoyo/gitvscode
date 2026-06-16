# LLM 接入 Phase 2A：Prompt 模板 + LLM 接口设计

## 一、目标与范围

Phase 2A 的目标是：**在不接入真实 LLM API 的前提下，为后续 LLM 接入建立稳定的 Prompt 模板、结构化 Schema 校验、接口抽象和测试保护层。**

### 为什么先做模板和接口，不直接接 API

| 原因 | 说明 |
|------|------|
| **安全第一** | LLM 输出不可信，必须有 Schema 校验 + 安全校验双拦截层 |
| **可回滚** | 规则版 MVP 必须保持完整可用，任何时候可以关掉 LLM 回退到规则链路 |
| **可测试** | FakeLLM/MockLLM 让所有 LLM 接入路径在离线状态下可测试 |
| **契约先行** | Prompt 模板定义清晰的输入/输出契约，接入真实 API 只是替换 client 实现 |

## 二、架构概览

```
                        ┌─────────────────────┐
                        │    Text2SQLAgent     │  ← 规则版 MVP（不变）
                        │   (rule mode only)   │
                        └─────────────────────┘

   ┌────────────────────────────────────────────────────┐
   │                   Phase 2A 新增                     │
   │                                                    │
   │  prompts/*.md          LLMAdapter                  │
   │  (Prompt 模板)    ──▶  (接口封装)                   │
   │                         │                          │
   │                    ┌────┴────┐                      │
   │                    │ LLMClient│ ← Protocol          │
   │                    └────┬────┘                      │
   │                         │                          │
   │              ┌──────────┼──────────┐               │
   │              ▼          ▼          ▼               │
   │        FakeLLM     MockLLM    (OpenAI) ← 2B 阶段   │
   │                                                    │
   │  schema_validators.py                              │
   │  (JSON Schema 校验)                                │
   │  4 个校验函数，拒绝未知字段                          │
   │                                                    │
   │  validate_sql_safety()  ← 不可绕过                  │
   └────────────────────────────────────────────────────┘
```

## 三、安全边界

### 规则版 MVP 的防线（不变）

```
中文问题 → _classify_intent() → detect_ambiguity()
        → _plan_query() → sql_plan_to_sql()
        → validate_sql_safety() → DuckDB(只读) → explain_result()
```

每一层都有独立校验，Phase 2A **不修改这条链路**。

### LLM 在链路中的职责边界

| 允许 | 禁止 |
|------|------|
| 生成 QuestionIntent JSON | 直接执行 SQL |
| 生成 SQLPlan JSON | 绕过 `validate_sql_safety()` |
| 生成 SELECT SQL 字符串 | 生成 INSERT/UPDATE/DELETE/DROP |
| 生成中文解释文本 | 编造不在 SQLResult 中的数据 |
| 标记 `human_review` | 编造未注册的表/字段/指标 |

## 四、四个 Prompt 模板

| 模板 | 输入 | 输出 | 反幻觉规则数 |
|------|------|------|-------------|
| `intent_classifier.md` | 问题 + 指标 + 策略 | QuestionIntent JSON | 10 条 |
| `sql_planner.md` | QuestionIntent + 表 + JOIN 白名单 | SQLPlan JSON | 12 条 |
| `sql_generator.md` | SQLPlan + 安全策略 | SQL + source_table | 11 条 |
| `explainer.md` | 问题 + SQL + 结果 + 口径 | 中文解释 | 10 条 |

### human_review 标记机制

每个 Prompt 的输出 JSON 都包含 `human_review` 字段：

```json
{
  "human_review": {
    "requires_review": false,
    "flagged_fields": [
      {"field": "metrics", "reason": "无法确定指向哪个指标"}
    ],
    "reason": "多项输入不明确，需人工确认"
  }
}
```

当 LLM 对某个字段不确定时，必须标记 `requires_review=true` 并列出不确定的字段和原因。

## 五、LLM Adapter 设计

### 接口（`src/llm_adapter.py`）

```python
class LLMAdapter:
    def __init__(self, llm_client: LLMClient, prompt_loader: PromptLoader)

    def classify_intent(question, context) -> QuestionIntent
    def plan_sql(intent, context) -> SQLPlan
    def generate_sql(plan, safety_policy) -> str      # 必经 validate_sql_safety()
    def explain_result(question, result, metrics) -> str
```

### 安全保证

1. **不导入 `OpenAIChatLLMClient`** —— 代码级隔离，无法实例化真实客户端
2. **不读取 API 密钥** —— 不导入 `_resolve_api_key`、`_SECRETS_PATH`
3. **Schema 校验** —— 每个方法在 LLM 返回 JSON 后立即调用对应的 `validate_*_output()`
4. **安全校验** —— `generate_sql()` 调用 `validate_sql_safety()`，失败则抛出 `ValueError`

### Schema 校验（`src/schema_validators.py`）

| 校验函数 | 拒绝未知字段 | 必需字段检查 | 语义交叉校验 |
|---------|-------------|-------------|-------------|
| `validate_intent_output` | ✓ | 10 个 | needs_clarification → reason 非空 |
| `validate_plan_output` | ✓ | 10 个 | 非 G3 策略 → downgrade_reason 非空 |
| `validate_sql_output` | ✓ | 2 个 | 必须以 SELECT 开头 |
| `validate_explain_output` | ✓ | 2 个 | — |

## 六、测试覆盖

| 类别 | 测试数 | 覆盖内容 |
|------|--------|---------|
| A: Prompt 模板完整性 | 9 | human_review 字段、反幻觉规则、用途说明 |
| B: Adapter 隔离性 | 2 | 不导入真实 API、不创建自身 client |
| C: Adapter 快乐路径 | 4 | classify/plan/generate/explain 正常返回 |
| D: Schema 校验 | 4 | 拒绝未知字段、拒绝缺字段、接收合法数据 |
| E: SQL 安全集成 | 2 | Schema 层拦截 INSERT、安全层拦截未授权表 |
| F: 导入完整性 | 2 | 模块可导入、现有导入未损坏 |

**总计新增 24 个测试。现有 57 个测试零破坏。**

## 七、后续 Phase 2B 建议接入顺序

1. **Phase 2B-1**：在 `Text2SQLAgent` 中新增 `_classify_intent_llm()` 方法，通过 `LLMAdapter` 调用 MockLLM，与规则版对比输出差异
2. **Phase 2B-2**：为 `_plan_query_llm()` 同样接入 MockLLM
3. **Phase 2B-3**：接入真实 DeepSeek API（通过已有的 `OpenAIChatLLMClient`），在 fixture 回归中验证
4. **Phase 2B-4**：配置化切换（`agent_config.yml` 中 `mode: "llm"` vs `mode: "rule"`）
5. **Phase 2C**：解释器 LLM 接入 + 端到端评测

## 八、风险清单与回滚方案

| 风险 | 等级 | 缓解 |
|------|------|------|
| LLM 输出格式漂移 | 中 | Schema 校验拒绝未知字段，`human_review` 标记不确定输出 |
| LLM 编造表/字段 | 高 | 多层拦截：Prompt 硬性边界 → Schema 校验 → `SQLPlan.validate()` → `validate_sql_safety()` |
| LLM 生成危险 SQL | 高 | `generate_sql()` 必经 `validate_sql_safety()`，非 SELECT 在 Schema 层即拦截 |
| Schema 过于严格导致误拒 | 低 | 仅拒绝顶层未知字段，嵌套结构允许扩展 |

### 回滚方案

1. **配置回滚**：`agent_config.yml` → 所有阶段设 `strategy: rule`
2. **代码回滚**：`src/llm_adapter.py` 和 `src/schema_validators.py` 为独立新增文件，删除即回滚
3. **Prompt 模板回滚**：模板变更仅增加了 `human_review` 字段和反幻觉规则，不影响现有 fixture 和 PromptLoader

## 九、新增/修改文件清单

### 新建文件

| 文件 | 行数 | 用途 |
|------|------|------|
| `src/schema_validators.py` | ~300 | 4 个 JSON Schema 校验函数 |
| `src/llm_adapter.py` | ~280 | LLMAdapter 类 + 4 个方法 |
| `tests/test_phase2a_llm_integration.py` | ~490 | 24 个测试 |
| `docs/llm_integration_phase2a.md` | 本文件 | 设计文档 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `prompts/intent_classifier.md` | 输出加 `human_review`，硬性边界加 3 条反幻觉规则，示例更新 |
| `prompts/sql_planner.md` | 同上 |
| `prompts/sql_generator.md` | 同上 |
| `prompts/explainer.md` | 同上 |

### 未修改文件

`src/llm.py`、`src/agent.py`、`src/ir.py`、`src/llm_pipeline.py`、`src/sql_gen.py`、`src/executor.py`、`src/explainer.py`、`src/ambiguity.py`、`src/resolver.py`——全部不变。
