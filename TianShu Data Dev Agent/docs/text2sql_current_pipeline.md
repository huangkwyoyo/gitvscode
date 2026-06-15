# Text2SQL Agent 当前管道完整工作流

> 版本：v1.0 | 日期：2026-06-14
>
> 状态：Phase 1 已交付 | Phase 2 DAG 扩展开发中
>
> 本文档描述 TianShu Data Dev Agent 的当前完整工作流——哪些节点由 LLM 参与、哪些由规则程序控制、哪些是安全门禁、为什么不允许 LLM 直接写 SQL、Prompt 回归系统需要解决什么。

---

## 一、管道总览

Text2SQL Agent 的管道包含 8 层，从 YAML 需求说明书到最终数据产物的完整链路：

```
──── 输入 ────
  YAML 需求说明书
  fixtures/requirements/trip_daily_report.yml

    ↓

──── 翻译阶段（LLM 可参与）────
  [Layer 1] 需求解析层     → Requirement 对象
  [Layer 2] 意图理解层     → Intent 对象
    ↓
  ═══════════════════════════════════════════════
              LLM 边界 —— 不可逾越
  ═══════════════════════════════════════════════
    ↓

──── 编译阶段（纯确定性代码）────
  [Layer 3] 规划层         → SQLPlan IR
  [Layer 4] 编译层         → 完整 SQL 文本 + 参数列表
    ↓

──── 安全门禁 ────
  [Layer 5] 校验层         → 校验报告（通过 / 拒绝）
    ↓

──── 执行与产出阶段 ────
  [Layer 6] 执行层         → DataFrame
  [Layer 7] 评估层         → 评估报告
  [Layer 8] 产出层         → 结果文件 + 报告 + 任务配置

──── 输出 ────
  generated/results/*.parquet
  generated/reports/*.md
  generated/tasks/*.yml
```

---

## 二、逐层详解

### Layer 1：需求解析层（Requirement Parser）

**谁控制**：规则解析器优先，LLM 仅 fallback

**做什么**：
1. 读取 YAML 文件，按 `contracts/requirement_schema.yml` 的 schema 解析
2. 提取：需求名称、描述、指标列表、维度列表、过滤条件、输出格式
3. 如果 YAML 严格符合 schema → 纯规则解析。如果不匹配 → LLM 辅助解析（但 LLM 只输出 JSON）

**代码位置**：`scripts/pipeline/layer1_requirement.py`

**输入**：YAML 需求文件路径

**输出**：`Requirement` 对象
```
{
  name: "2026年Q1每日行程量趋势",
  description: "统计...",
  metrics: [{name: "行程量"}, {name: "总收入"}, {name: "总里程"}],
  dimensions: [{name: "日期"}],
  filters: {date_range: ["2026-01-01", "2026-03-31"]},
  group_by: ["日期"],
  output: {format: "parquet"}
}
```

**LLM 参与方式**：只有当 YAML schema 校验失败时才调 LLM——LLM 读取原始文本，输出符合 schema 的 JSON。

**安全风险**：LLM 可能错误解析指标名（"行程量"被误解为其他指标）——但 Layer 2 会进行二次验证。

---

### Layer 2：意图理解层（Intent Agent）

**谁控制**：规则匹配优先，LLM 模糊匹配，两者都不行时反问澄清

**做什么**：
1. 遍历需求中的每个指标名，尝试**精确匹配**已注册指标（查 `METRIC_REGISTRY` 字典）
2. 精确匹配失败的指标 → 调 LLM 做**模糊匹配**（"用户说'行程量'，已注册指标有 trip_count / total_fare_amount / ...，请选择最接近的"）
3. LLM 返回后 → **再次校验**：`assert response["registered_name"] in METRIC_REGISTRY`
4. 无法匹配且 LLM 也不确定 → 返回澄清问题给用户（反问机制）
5. 组装 Intent 对象

**代码位置**：`scripts/pipeline/layer2_intent.py`

**输入**：`Requirement` 对象

**输出**：`Intent` 对象——**这是 LLM 输出在系统中的最后形态**
```
{
  metrics_requested: [
    {registered_name: "trip_count", fuzzy_matched: false, user_name: "行程量"},
    {registered_name: "total_fare_amount", fuzzy_matched: false, user_name: "总收入"},
    {registered_name: "total_distance_miles", fuzzy_matched: false, user_name: "总里程"}
  ],
  dimensions: [{name: "date", alias: "日期"}],
  filters: {date_range: ["2026-01-01", "2026-03-31"]},
  group_by: ["date"],
  domain: "traffic",
  confidence: {metric_match: "high"}
}
```

**关键约束**：Intent 对象中**绝对不能出现**：
- 表名（如 `gold.dws_daily_trip_summary`）
- 字段名（如 `trip_count` 只作为 registered_name 出现，而非物理列引用）
- JOIN 关键词
- SQL 片段

**LLM 参与方式**：仅当指标名无法精确匹配时调 LLM。LLM 的输入是需求原文 + 已注册指标列表，LLM 的输出是选中的指标名（必须是列表中的值）。输出被 JSON Schema 严格约束。

**安全措施**：
1. `registered_name` 必须在 `METRIC_REGISTRY` 中存在——不存在的指标被拒绝
2. 维度名必须在已注册维度列表中
3. 日期范围必须可解析
4. **这是 LLM 的终点。之后的所有层都不调 LLM。**

---

### ═══ LLM 边界 ═══

**这条线上方**：LLM 可以参与（Layer 1 fallback + Layer 2 模糊匹配）。LLM 的输出被 JSON Schema 严格约束，且输出中不含表名/字段名/JOIN/SQL。

**这条线下方**：100% 确定性代码。无 LLM 调用、无随机性、无外部服务依赖（除了 DuckDB 数据库）。同样的 Intent 永远产生同样的 SQLPlan → 同样的 SQL → 同样的执行结果。

**为什么 LLM 绝对不能越界**：见第五节。

---

### Layer 3：规划层（SQLPlan Planner）

**谁控制**：100% 确定性代码

**做什么**（7 个子步骤）：
```
Intent 对象
  ↓
[3a] resolve_layer()         → G3 优先，缺指标降级 G2
[3b] determine_primary_table() → 查 metric_registry
[3c] 检测 needs_dim_date       → G2 表的日期列以 _key 结尾时触发
[3d] build_join_graph()        → 单表 / 跨域 / dim_date JOIN
[3e] build_column_bindings()   → 查 ColumnBindingTable
[3f] build_filter_bindings()   → 参数化，G2 时切换到 dim_date.date
[3g] build_execution_constraints() → 从 join_graph 推算 requires_date_dim
  ↓
SQLPlan IR
```

**代码位置**：
- `scripts/pipeline/layer3_plan.py` — SQLPlan 构造
- `scripts/pipeline/column_binding.py` — ColumnBindingTable 查询

**输入**：Intent 对象

**输出**：SQLPlan IR——Layer 4 编译器的唯一输入

**SQLPlan IR 结构（Phase 2 扩展后）**：
```
{
  plan_id, plan_name, source_layer, domain,
  
  join_graph: {
    primary: {ref: "primary", table: "gold.dws_daily_trip_summary"},
    joins: []  // 单表查询时为空
  },
  
  column_bindings: [
    {metric_name: "trip_count", column_ref: "primary.trip_count", alias: "行程量"}
  ],
  
  filter_bindings: [
    {filter_type: "date_range", column_ref: "primary.trip_date", operator: "BETWEEN",
     value: ["2026-01-01", "2026-03-31"]}
  ],
  
  group_by: ["primary.trip_date"],
  order_by: [{column: "primary.trip_date", direction: "ASC"}],
  
  // Phase 2 扩展（属于 SQLPlan，不属于 PipelineStep）
  window_functions: [],
  expression_refs: [],
  cte_definitions: []
}
```

**确定性保障**：
- 所有决策通过查表和规则完成
- ColumnBindingTable 在启动时加载，运行时只读
- LLM 完全禁止参与
- 不调用外部服务
- 不生成随机值

---

### Layer 4：编译层（SQL Compiler）

**谁控制**：100% 确定性代码——纯模板编译器

**做什么**：从 SQLPlan IR 机械拼接 SQL 文本。7 个编译 Pass：

```
Pass 0: build_alias_map()     → 构建 table_ref → SQL 别名映射
Pass 1: compile_select()      → column_bindings[] → "SELECT t1.col1, t1.col2"
Pass 2: compile_from()        → join_graph → "FROM gold.table AS t1"
Pass 3: compile_where()       → filter_bindings[] → "WHERE t1.date BETWEEN ? AND ?"
Pass 4: compile_group_by()    → group_by[] → "GROUP BY t1.date"
Pass 5: compile_order_by()    → order_by[] → "ORDER BY t1.date ASC"
Pass 6: compile_limit()       → limit → "LIMIT 1000"
       ↓
"\n".join()                   → 完整 SQL 文本
```

**代码位置**：`scripts/pipeline/layer4_generate.py`

**输入**：SQLPlan IR

**输出**：`(sql_text: str, params: list)`——参数化 SQL + 参数列表

**为什么"拼接"就够了**：SQL 的各个组成部分天然可拆分——SELECT 列、FROM 表、WHERE 条件各自独立，各自对应 SQLPlan IR 中的一个字段。编译器不是"创作" SQL，而是把 IR 的每个字段填进模板的对应位置。这就像填空题——模板固定，答案来自 JSON。

**安全属性**：
- 所有标识符来自 ColumnBindingTable，不拼接用户输入
- 过滤值通过参数化占位符 `?` 绑定，不拼入 SQL
- 编译失败（抛 `SQLCompileError`）比生成错误的 SQL 更安全

---

### Layer 5：校验层（Validator）——安全门禁

**谁控制**：100% 确定性代码——纯规则引擎

**做什么**：在 SQL 执行前执行多项安全检查。**这是系统中最重要的安全层。**

**Phase 1 检查项（6 项）**：

| # | 检查项 | 实现函数 | 失败后果 |
|---|--------|---------|---------|
| 1 | 禁止操作黑名单 | `_check_forbidden_keywords()` | 拒绝执行 |
| 2 | 只读前缀检查 | `_check_allowed_prefix()` | 拒绝执行 |
| 3 | 表引用合法性 | `_check_table_references()` | 拒绝执行 |
| 4 | 完全限定名检查 | `_check_fully_qualified_names()` | 拒绝执行 |
| 5 | JOIN 白名单检查 | `_check_join_whitelist()` | 拒绝执行 |
| 6 | 日期合规检查 | `_check_date_compliance()` | 拒绝执行 |

**Phase 2 新增检查项（2 项）**：

| # | 检查项 | 实现函数 | 失败后果 |
|---|--------|---------|---------|
| 7 | DAG 结构验证 | `validate_pipeline_dag()` | 拒绝执行 |
| 8 | 安全层级合规 | `validate_operation_compliance()` | 拒绝执行 |

**代码位置**：
- `scripts/pipeline/layer5_validate.py` — SQL 级校验
- `scripts/pipeline/layer5_validate_pipeline.py` — PipelinePlan 级校验

**关键原则**：
- 不调 LLM——纯规则引擎
- 不连数据库——纯静态分析
- 所有检查失败都是硬拒绝（不是警告）——宁可不执行也不执行不安全的 SQL

**LLM 参与方式**：无。完全禁止。

---

### Layer 6：执行层（Executor）

**谁控制**：DuckDB 执行引擎

**做什么**：
- `safety_tier=query` 时：DuckDB `read_only=True` 连接
- `safety_tier=pipeline` 时：正常连接，但 SQL 已通过 Layer 5
- 参数化查询执行
- 30s 超时（query 层）或 30min（pipeline 层）
- 禁止多语句

**代码位置**：`scripts/pipeline/layer6_execute.py`

---

### Layer 7：评估层（Evaluator）

**谁控制**：纯统计检查代码

**检查项**：
- 行数范围（< max_result_rows = 100000）
- 空值率（< 30%）
- 列完整性（所有预期列存在）
- 指标一致性（列数 ≥ metrics 数量）

**代码位置**：`scripts/pipeline/layer7_evaluate.py`

---

### Layer 8：产出层（Publisher）

**谁控制**：纯输出代码

**输出物**：
| 文件 | 路径模式 |
|------|---------|
| 数据结果（Parquet） | `generated/results/{plan_name}_{timestamp}.parquet` |
| 验证报告（Markdown） | `generated/reports/{plan_id}_report_{timestamp}.md` |
| 任务配置（YAML） | `generated/tasks/{plan_id}_task_{timestamp}.yml` |

**代码位置**：`scripts/pipeline/layer8_product.py`

---

## 三、LLM 参与和不参与的节点总结

| 层 | LLM 是否参与 | 参与方式 | 约束 |
|-----|-------------|---------|------|
| Layer 1 | **是**（仅 fallback） | YAML schema 不匹配时，LLM 辅助解析 | LLM 只能输出符合 schema 的 JSON |
| Layer 2 | **是**（仅模糊匹配） | 指标名无法精确匹配时，LLM 做模糊匹配 | LLM 只能从已注册指标列表中选择 |
| Layer 3 | **否** | — | 所有决策通过查表和规则 |
| Layer 4 | **否** | — | 纯模板编译 |
| Layer 5 | **否** | — | 纯规则引擎 |
| Layer 6 | **否** | — | DuckDB 执行 |
| Layer 7 | **否** | — | 纯统计检查 |
| Layer 8 | **否** | — | 纯文件输出 |

---

## 四、安全门禁清单

系统中有 **3 道安全门禁**。任何一道失败都会阻止后续流程：

| 门禁 | 位置 | 检查内容 | 严重度 |
|------|------|---------|--------|
| **门禁 1：Layer 2 校验** | `layer2_intent.py` | 所有指标名必须在已注册列表中；Intent JSON 中不得出现表名/字段名 | 🔴 |
| **门禁 2：Layer 5 SQL 校验** | `layer5_validate.py` | 安全黑名单 + 只读前缀 + 表引用 + JOIN 白名单 + 日期合规 | 🔴 |
| **门禁 3：Layer 5 DAG 校验** | `layer5_validate_pipeline.py` | DAG 环检测 + 依赖引用完整性 + 拓扑序 + safety_tier 合规 | 🔴 |

**注意**：Layer 3 和 Layer 4 的"编译失败"也构成隐式门禁——如果 ColumnBindingTable 中缺少必要信息，编译器会拒绝生成 SQL。

---

## 五、为什么当前阶段不允许 LLM 直接写 SQL

这是一个经常被问到的问题。以下是完整的技术论证：

### 5.1 对比：两种架构

```
架构 A：LLM 直接生成 SQL（大多数 Text2SQL 系统）
  用户自然语言 → LLM → SQL 文本 → 执行

架构 B：IR 中介 + 编译器（本系统）
  用户 YAML 需求 → LLM → Intent JSON → 确定性编译器 → SQL → 执行
```

### 5.2 架构 A 的问题

| 问题 | 具体表现 |
|------|---------|
| **幻觉** | LLM 可能编造不存在的表名或字段名——"事故数"在表中叫 `crash_count`，LLM 可能写成 `accident_count` |
| **安全风险** | 恶意的 prompt 可能诱导 LLM 生成 `DROP TABLE` 或访问禁止的表 |
| **非确定性** | 同样的需求两次调 LLM 可能生成不同的 SQL——无法回归测试 |
| **不可审计** | 无法追溯"为什么这条 SQL 是这样写的"——LLM 是黑箱 |
| **方言错误** | LLM 可能混用不同数据库的语法（DuckDB 的 `DATE_TRUNC` vs Oracle 的 `TRUNC`） |
| **JOIN 错误** | LLM 可能编造错误的 JOIN 条件或遗漏必要的 JOIN |

### 5.3 架构 B 如何解决这些问题

| 架构 A 的问题 | 架构 B 的解决方案 |
|-------------|-----------------|
| 幻觉（编造表名/字段名） | Layer 3 从 ColumnBindingTable 确定性查表——不存在的东西查不到，编译失败 |
| 安全风险 | Layer 5 16 个关键字黑名单 + 7 项检查——LLM 不参与安全决策 |
| 非确定性 | Layer 3-8 都是纯函数——同样输入永远同样输出 |
| 不可审计 | IR 中的每个字段都可追溯到来源（哪条规则、哪个契约条目） |
| 方言错误 | 编译器根据 target_dialect 翻译，LLM 不感知方言 |
| JOIN 错误 | JoinGraph 从 JOIN_WHITELIST 构造，LLM 不参与 JOIN 决策 |

### 5.4 为什么当前阶段是 YAML 输入而非自然语言输入

当前阶段的需求输入是结构化 YAML（而非自然语言），原因：
1. **YAML 可自动验证**——schema 校验可以拒绝格式错误的需求
2. **YAML 消除歧义**——"行程量"在 YAML 中是显式声明的指标名，而非需要 LLM 猜测的自然语言
3. **YAML 是稳定的**——同样的 YAML 永远产生同样的解析结果（自然语言同理可能有多种合理理解）
4. **为自然语言入口打基础**——一旦 YAML 管道稳定（44 个测试全部通过），可以安全地在 Layer 1 前方增加一个"自然语言→YAML"的翻译层，该层允许 LLM 参与，但输出被 YAML schema 严格约束

---

## 六、Prompt 回归报告系统

### 6.1 当前状态

**Prompt 回归报告系统尚未实现。**

当前 LLM 相关的测试以 pytest 形式在 `tests/test_pipeline.py` 的 `TestLayer2Intent` 类中运行——测试 Layer 2 的指标匹配逻辑（精确匹配、模糊匹配、非法指标拦截、跨域检测）。

`evals/regression_baseline.yml` 文件已创建，但基线数据（status、last_run、last_rows）仍为 `pending` 状态。

### 6.2 最终目标

设计一个自动化的 Prompt 回归报告系统，在 LLM 模型版本变动时提供客观的质量判定：

```
每次 LLM 模型升级后（或定期触发）
  → 运行所有固定的评测用例（e2e_cases.yml）
  → 记录每个用例的 Intent 输出
  → 与基线（regression_baseline.yml）对比
  → 生成回归报告：
    - 哪些用例的 Intent 完全一致 → ✅ 通过
    - 哪些用例的 Intent 有变化但语义等价 → ⚠️ 警告（需人工审查）
    - 哪些用例的 Intent 完全变化 → ❌ 失败（需回滚或调整）
```

### 6.3 Prompt 回归要解决的核心问题

LLM 的 Prompt 回归不是 SQL 回归（SQL 回归已经被确定性编译器保证了）。它解决的是 LLM 的**翻译稳定性**问题：

| 场景 | 说明 | 回归系统的判断 |
|------|------|-------------|
| 模型升级后"行程量"仍匹配 `trip_count` | 翻译稳定 | ✅ 通过 |
| 模型升级后"行程量"变成了 `total_trip_amount` | 翻译漂移——可能影响业务 | ❌ 失败 |
| 模型升级后"行程量"仍匹配 `trip_count`，但置信度从 `high` 降为 `medium` | 语义等价但模型更不确定 | ⚠️ 警告 |
| 新增指标后"事故量"仍匹配 `crash_count` | 已有基线不受新增影响 | ✅ 通过 |

### 6.4 当前可以回归测试什么（不需要 LLM API）

即使没有真实的 LLM API，以下内容已经可以回归测试：

1. **Layer 3-8 确定性**：19 个 pytest 端到端测试——验证 Intent → SQL → 校验的完整链路
2. **Layer 2 精确匹配逻辑**：精确匹配不需要 LLM——pytest 测试覆盖了匹配/不匹配/非法三种情况
3. **ColumnBindingTable 稳定性**：`test_all_10_metrics_registered` 验证指标映射完整性
4. **安全门禁有效性**：`test_forbidden_keyword_detected` 验证安全黑名单

**唯一不能回归测试的是 LLM 的模糊匹配行为**——这需要真实 LLM API 来验证"模型升级前后，同样的模糊输入是否产生同样的匹配结果"。

### 6.5 实现真实 Prompt 回归系统前，必须保留的边界

| 边界 | 为什么必须保留 | 如果被破坏 |
|------|-------------|-----------|
| **Intent JSON Schema 不可变** | 回归对比依赖 JSON 结构一致。如果 schema 变了，旧的基线全部失效。 | 无法区分"模型行为变化"和"schema 变化" |
| **Layer 2 的输入/输出接口不可变** | `build_intent(requirement) → Intent` 的签名和返回值格式是回归测试的锚点 | 回归测试无法运行 |
| **LLM 只出现在 Layer 1-2** | 如果在 Layer 3-8 中增加 LLM 调用，回归系统必须覆盖更多层 | 回归覆盖不全 |
| **已注册指标列表的变更需审批** | 如果随意增减指标，LLM 的匹配行为会变 | 回归基线失效 |
| **回归基线独立于代码版本** | 基线存在 `evals/regression_baseline.yml` 中，不与代码混在一起 | 代码回滚时基线丢失 |
| **评测用例独立于运行环境** | e2e_cases.yml 中的用例不依赖具体数据库状态 | 不同环境跑出不同结果 |

---

## 七、当前测试覆盖

| 测试类 | 测试数 | 覆盖内容 |
|--------|--------|---------|
| TestLayer1Requirement | 3 | YAML 解析（有效/无效/全部 fixture） |
| TestLayer2Intent | 4 | 精确匹配/模糊匹配/非法拦截/跨域检测 |
| TestLayer3SQLPlan | 2 | G3 单表规划/跨域 JOIN 图 |
| TestLayer4SQLCompile | 2 | 有效 SQL 编译/无效计划拒绝 |
| TestLayer5Validation | 2 | 安全 SQL 通过/危险关键字检测 |
| TestColumnBindingTable | 3 | 10 个指标全部注册/G3 绑定/ G2 降级 |
| TestEndToEndPipeline | 3 | 行程日报/违章日报/事故日报 dry-run |
| **Phase 1 合计** | **19** | |
| TestDAGCycleDetection | 6 | 线性/菱形/简单环/三角环/自环/空列表 |
| TestDAGDependencyReferences | 3 | 全部存在/缺失引用/多个缺失 |
| TestDAGTopologicalOrder | 3 | 正确序/错误序/菱形 |
| TestSafetyTierCompliance | 10 | SELECT/CTAS/写入 gold/bronze/generated/未知 tier/混合操作 |
| TestValidatePipeline | 3 | 合法管道/有环但合规/写入 gold 失败 |
| **Phase 2 合计** | **25** | |
| **总计** | **44** | **全部通过** |

---

## 八、后续实现 Prompt 回归报告系统的建议第一步

不是直接实现完整系统——而是先建立 **Prompt 回归的最小可行锚点**：

### 第一步：实现 Intent 输出的 JSON 快照

```python
# 最小可行实现——只记录、不判断
def baseline_snapshot(case_id: str, intent: Intent) -> dict:
    """将 LLM 的 Intent 输出保存为基线快照"""
    return {
        "case_id": case_id,
        "model": "current-model-id",
        "metrics_matched": [m.registered_name for m in intent.metrics_requested],
        "fuzzy_matched": [m.fuzzy_matched for m in intent.metrics_requested],
        "confidence": intent.confidence.metric_match,
        "domain": intent.domain,
    }
```

### 为什么从这步开始

1. **零依赖**：不需要真实 LLM API——可以先把手动记录的基线写入 `regression_baseline.yml`，然后 mock LLM 输出来验证对比逻辑
2. **明确边界**：只碰 Intent JSON——不碰 SQL（SQL 已经被确定性编译器保障了）
3. **可验证**：可以先在 `TestLayer2Intent` 中增加一个测试——"当前 mock LLM 输出是否与基线一致"
4. **为完整系统打基础**：快照格式稳定后，后续只需要"调真实 LLM → 生成快照 → 对比基线"

### 什么时候可以进入完整实现

当满足以下条件时：
1. Intent JSON Schema 锁定（字段不增不减不改名）
2. 已注册指标列表稳定
3. 至少 5 个评测用例的基线手动审核通过
4. 有一个自动化 CI 步骤来运行回归测试

---

## 九、快速参考

| 你想知道 | 去这里看 |
|---------|---------|
| Agent 能做什么、不能做什么 | `AGENTS.md` §1 |
| 8 层管道路由 | `AGENTS.md` §2 |
| 每个术语的定义 | `docs/text2sql_engineering_glossary.md` |
| 全部测试通过了吗 | `pytest tests/ -v`（44 passed） |
| 安全黑名单完整吗 | `scripts/pipeline/layer5_validate.py` FORBIDDEN_KEYWORDS |
| IR 中有手写 SQL 吗 | `contracts/pipeline_plan_schema.yml`——搜索 `sql:` 字段 |
| LLM 在哪出现 | `scripts/pipeline/layer2_intent.py` Line: `call_llm(llm_prompt)` |
| ColumnBindingTable 有哪些指标 | `scripts/pipeline/column_binding.py` METRIC_BINDINGS |
| 怎么跑一条需求 | `python scripts/pipeline/run_pipeline.py -r fixtures/requirements/trip_daily_report.yml` |
