# Text2SQL Agent 工程词典

> 版本：v1.1 | 日期：2026-06-14 | 覆盖：Phase 1-3（含 IR Freeze + P3 表达式编译器）
>
> 读者：项目 Owner、数据平台架构师、新加入的工程团队成员。
> 用途：理解 TianShu Data Dev Agent 的关键术语、工程思想、文件位置和验收方式。

---

## 阅读指南

本文档按"是什么 → 为什么需要 → 在哪实现 → 输入/输出 → 出错风险 → 例子 → Owner 审查问题"的格式，逐一解释项目中的核心概念。

**如果你只有 5 分钟**：先读 §1-§8（系统定位、编译器优先、LLM 边界、IR、ColumnBindingTable、管道八层、安全体系、Phase 2 扩展）。新增 §27-§29（IR 冻结、表达式编译器、注册表模式）了解最新进展。

**如果你要审查项目**：每个术语末尾都有"Owner 审查时应该问什么"——直接拿着这些问题去问工程团队。

---

## §1 系统定位

### 1. Data Dev Agent（数据开发 Agent）

**是什么**：TianShu Data Dev Agent 是一个**确定性的数据生产管道系统**。它接收结构化的 YAML 需求说明书，经过 8 层管道处理，产出数据结果文件、验证报告和调度任务配置。

**它不是什么**：
- 不是聊天机器人——用户不能自由对话
- 不是 Text2SQL 查询工具——不能输入自然语言直接得到 SQL
- 不是 BI 自助分析平台——不支持拖拽式探索

**它解决什么问题**：传统数据开发中，从"需求文档"到"生产 SQL"需要数据工程师手工编写，存在以下问题：
- 字段名写错（"事故数"在表中叫 `crash_count` 而非 `accident_count`）
- 查了不该查的表（原始数据层 bronze.* 包含未清洗数据）
- 同样的需求两次写出不同的 SQL（不可回归测试）
- 出问题后无法追溯"为什么要这样写"

**在当前项目中的位置**：整个项目。入口文件 `scripts/pipeline/run_pipeline.py`。

**输入**：一份 YAML 格式的需求说明书（`fixtures/requirements/*.yml`）

**输出**：
- 数据结果文件（Parquet/CSV）→ `generated/results/`
- 验证报告（Markdown）→ `generated/reports/`
- 调度任务配置（YAML）→ `generated/tasks/`

**出错会导致什么风险**：如果 Agent 定位不清晰，团队可能把它当聊天机器人用，导致 LLM 直接生成 SQL——这将破坏整个系统的确定性基础。

**简单例子**：用户提交 `trip_daily_report.yml`（"统计 2026 年 Q1 每日行程量"），Agent 产出包含 90 行 × 4 列的 `trip_count`、`total_fare_amount`、`total_distance_miles` 结果表。

**Owner 审查时应该问什么**：
1. "这个项目与市面上的 Text2SQL 工具有什么本质区别？"
2. "如果用户输入了包含 SQL 注入的需求，系统如何防御？"
3. "系统的确定性如何验证——同样的需求跑两次，SQL 是否 100% 一致？"

---

## §2 核心设计思想

### 2. 编译器优先设计（Compiler-First Design）

**是什么**：把数据开发流程类比为编译器工作流程——需求说明书是"源代码"，SQL 是"目标代码"。**SQL 不是"写"出来的，是"编译"出来的。**

**它解决什么问题**：传统方式中，数据工程师是"人脑编译器"——读需求 → 想 SQL → 写代码。人脑编译器不稳定、不标准、不可审计。编译器优先设计将 SQL 生成从"人脑推理"变为"机械转换"。

**在当前项目中的位置**：核心实现是 Layer 3（规划层）+ Layer 4（编译层）：
- `scripts/pipeline/layer3_plan.py`：构造 SQLPlan IR
- `scripts/pipeline/layer3_pipeline_plan.py`：构造 PipelinePlan IR（Phase 2）
- `scripts/pipeline/layer4_generate.py`：从 SQLPlan IR 编译 SQL 文本

**输入**：Intention JSON（描述"要查什么"）

**输出**：完整参数化 SQL 文本 + 参数列表

**出错会导致什么风险**：如果编译器不是纯函数（有随机性、依赖外部状态），同样的需求两次编译可能生成不同 SQL——这正是"确定性"被破坏的标准症状。

**简单例子**：
```
需求 "按天统计行程量" → LLM输出: {metric: "trip_count", dimension: "date"}
→ Layer 3 查 ColumnBindingTable → trip_count 在 gold.dws_daily_trip_summary
→ Layer 4 编译: SELECT dws_daily_trip_summary.trip_count FROM gold.dws_daily_trip_summary
```
这个过程的每一步都是机械的——查表、替换、拼接。

**Owner 审查时应该问什么**：
1. "编译器有哪些 Pass？每个 Pass 的输入输出是什么？"
2. "如果 ColumnBindingTable 中缺少某个指标，编译器会怎样——生成错误的 SQL，还是拒绝编译？"

---

### 3. 确定性（Determinism）

**是什么**：同样的输入永远产生同样的输出。在这个项目中，一条 YAML 需求说明书 + 同一个 ColumnBindingTable 状态 → 永远生成同一条 SQL。

**它解决什么问题**：
- **可回归测试**：改代码后跑同样的需求，SQL 不变就是"没改坏"
- **可审计**：出问题时可以追溯"当时的 SQL 是什么"
- **可重现**：生产环境的问题在开发环境可以精确复现
- **可信任**：用户不需要担心 AI 的"随机性"

**在当前项目中的位置**：所有 Layer 3-8 的代码都是纯确定性代码。检查方法：运行 `python -m pytest tests/ -v`，75 个测试全部通过（Phase 1: 19 + Phase 2: 25 + P3 表达式编译器: 31）。

**输入**：固定的 YAML 需求 + 固定的 ColumnBindingTable

**输出**：固定的 SQL 文本 + 固定的执行结果

**出错会导致什么风险**：确定性被破坏意味着系统不可信任。最常见的破坏来源是：LLM 越界参与 SQL 生成、代码中使用随机数、依赖外部服务的非确定性响应。

**Owner 审查时应该问什么**：
1. "如何证明系统是确定性的？有没有自动化测试来验证？"
2. "如果 ColumnBindingTable 的内容变了（比如新增了一个指标），已有需求的 SQL 会变吗？"

---

### 4. LLM 边界（LLM Boundary）

**是什么**：系统中一条不可逾越的线。LLM（大语言模型，如 Claude）只能在 Layer 1 和 Layer 2 参与——它的输出必须是**结构化 JSON**，不能包含表名、字段名、JOIN 条件或 SQL 片段。

**它解决什么问题**：LLM 本质上是概率性的——它有时会编造信息（幻觉）。如果让它推荐表名或写 SQL，它可能：
- 编造不存在的表名（`dws_daily_accident_summary` 实际叫 `dws_daily_crash_summary`）
- 写错 JOIN 条件（`a.id = b.id` 实际应该用 `a.trip_date = b.crash_date`）
- 同样的需求两次输出不同 SQL

**在当前项目中的位置**：
- `AGENTS.md`：第 1 节定义了 LLM 禁止做的事
- `AGENTS.md`：第 2 节标注了 LLM 边界线
- `scripts/pipeline/layer1_requirement.py`：LLM 可参与（YAML 解析 fallback）
- `scripts/pipeline/layer2_intent.py`：LLM 最后出现的地方——输出 Intent JSON
- Layer 3-8：LLM 完全禁止

**LLM 允许做的事**（Layer 1-2）：
| 允许 | 机制 |
|------|------|
| YAML schema 不匹配时辅助解析 | 规则解析器优先，LLM 仅 fallback |
| 指标消歧（"行程量" → `trip_count`） | LLM 只能输出 Intent JSON |
| 识别维度和过滤条件 | 输出中不含表名/字段名 |

**LLM 禁止做的事**（Layer 3-8）：
| 禁止 | 替代方案 |
|------|---------|
| 输出表名 | Layer 3 查 ColumnBindingTable |
| 输出字段名 | ColumnBindingTable 预编译映射 |
| 决定 G3 或 G2 层 | `resolve_layer()` 函数决定 |
| 写 JOIN 条件 | JoinGraph 白名单构造 |
| 生成 SQL 或其片段 | Layer 4 模板编译器 |
| 绕过安全策略 | Layer 5 纯规则引擎 |

**出错会导致什么风险**：LLM 越界是系统最大的安全风险。一旦 LLM 生成的 SQL 片段进入编译器，确定性就被破坏，审计和回归测试全部失效。

**Owner 审查时应该问什么**：
1. "如何在代码层面防止 LLM 越界——有没有机制检测 LLM 输出中是否包含表名？"
2. "如果 LLM 服务宕机，管道还能跑吗？哪些功能会降级？"

---

### 5. IR（中间表示 / Intermediate Representation）

**是什么**：一种标准化的 JSON 结构，描述"要做什么"（WHAT），不描述"怎么做"（HOW）。IR 是系统各层之间的"世界语"。

**它解决什么问题**：没有 IR 的话，每一层都需要理解上一层的内部细节——这会造成紧耦合。IR 让每一层可以独立替换：换一个更好的 LLM（Layer 2）不需要改 SQL 编译器（Layer 4），换一个数据库方言（DuckDB → Hive）不需要改规划层（Layer 3）。

**在当前项目中的位置**：

| IR 类型 | 层级 | 对应文件 |
|---------|------|---------|
| Intent IR | Layer 2 输出 | `scripts/pipeline/layer2_intent.py` |
| SQLPlan IR | Layer 3 输出 | `scripts/pipeline/layer3_plan.py` |
| PipelinePlan IR | Layer 3 输出（Phase 2） | `scripts/pipeline/layer3_pipeline_plan.py` |
| 契约定义 | 静态文档 | `contracts/sqlplan_schema.yml`, `contracts/pipeline_plan_schema.yml` |

**IR 层次关系**（v2.1 修正后）：

```
PipelinePlan IR（跨步骤 DAG）
  └── steps[]
      ├── depends_on[]（跨步骤引用——唯一跨步骤信息）
      ├── operation + target_table（步骤属性）
      ├── incremental_intent（增量意图）
      └── sql_plan: SQLPlan IR（单条 SQL 的完整描述）
          ├── join_graph（表结构）
          ├── column_bindings（SELECT 列）
          ├── filter_bindings（WHERE 条件）
          ├── window_functions[]（窗口函数——语句级）
          ├── expression_refs[]（表达式——列级）
          └── cte_definitions[]（CTE——语句级 WITH 子句）
```

**注意**：窗口函数、表达式、CTE 属于 SQLPlan（语句级），不属于 PipelinePlan（管道级）。这是 v2.1 修正的核心——纠正了 IR 分层错误。

**输入**：上一层的输出

**输出**：下一层的输入

**出错会导致什么风险**：IR 设计错误是最昂贵的技术债。IR 分层混乱（如把语句级概念放在管道级）会导致编译器无法正确编译、方言适配失效。

**Owner 审查时应该问什么**：
1. "IR 的设计原则是什么？如何保证 IR 是方言无关的？"
2. "IR 中存在原始 SQL 字符串吗？如果有，为什么？"

---

## §3 数据层概念

### 6. ColumnBindingTable（列绑定表——系统的"中枢神经"）

**是什么**：一张映射表，将**指标名称**（如 "行程量"）映射到**物理列名**（如 `gold.dws_daily_trip_summary.trip_count`）。每个指标在 G3（汇总层）和 G2（明细层）各有映射。

**它解决什么问题**：如果没有这张表，系统需要"知道"每个指标在哪个表的哪一列——这是数据工程师脑子里的隐性知识。ColumnBindingTable 把这种知识从"人脑"搬到了"代码"中，实现了字段名的确定性映射。

**在当前项目中的位置**：
- `scripts/pipeline/column_binding.py`：ColumnBindingTable 的实现
- 启动时从 TianShu DuckDB 的 `meta.metric_definitions` 动态加载已审批指标
- 静态绑定作为 fallback

**当前注册的指标**（10 个，4 个业务域）：

| 域 | 指标 | G3 列 | G2 表达式 |
|----|------|-------|----------|
| traffic | trip_count | dws_daily_trip_summary.trip_count | COUNT(*) |
| traffic | total_fare_amount | dws_daily_trip_summary.total_fare_amount | SUM(fare_amount) |
| traffic | total_tip_amount | —（G3 不含） | SUM(tip_amount) |
| traffic | total_distance_miles | dws_daily_trip_summary.total_distance_miles | SUM(trip_miles) |
| violation | parking_violation_count | dws_daily_parking_summary.violation_count | COUNT(*) |
| violation | standard_fine_total | dws_daily_parking_summary.standard_fine_total | SUM(standard_fine_amount) |
| safety | crash_count | dws_daily_crash_summary.crash_count | COUNT(*) |
| safety | persons_killed | dws_daily_crash_summary.persons_killed | SUM(persons_killed) |
| safety | persons_injured | dws_daily_crash_summary.persons_injured | SUM(persons_injured) |
| supply | tif_payment_amount | —（无 G3 汇总表） | SUM(total_payment_amount) |

**输入**：指标名称（字符串）

**输出**：BindingEntry（包含物理表名、列名、别名、单位、业务域）

**出错会导致什么风险**：如果 ColumnBindingTable 的映射错误（如把 `crash_count` 映射到 `accident_count`），整个系统生成的 SQL 都会使用错误的列名，导致查询失败或数据错误。

**简单例子**：用户说"我要查事故数量" → Layer 2 输出 `{metric: "crash_count"}` → Layer 3 查 ColumnBindingTable → 得到 `gold.dws_daily_crash_summary.crash_count` → 编译器生成 `SELECT crash_count FROM gold.dws_daily_crash_summary`。

**Owner 审查时应该问什么**：
1. "ColumnBindingTable 的数据从哪里来？是手动维护还是自动同步？"
2. "如果 TianShu 数仓新增了一个指标，ColumnBindingTable 如何感知？需要重启 Agent 吗？"
3. "LLM 能访问 ColumnBindingTable 吗？如果不能，如何保证？"

---

### 7. G3 / G2 / dim_date JOIN

**是什么**：数据层的层级区分和日期过滤契约。

- **G3（Gold 汇总层）**：预聚合的每日汇总表。速度快、安全性高。优先使用。
- **G2（Gold 明细层）**：明细事实表。G3 不包含某指标时降级使用。
- **G2 日期过滤契约**：G2 事实表的日期列是整数代理键（如 `pickup_date_key`），不能直接与字符串日期比较。必须 JOIN `gold.dim_date` 并通过 `dim_date.date`（实际 DATE 类型）过滤。

**它解决什么问题**：
- G3 优先策略保证性能和安全性——汇总表比明细表快得多
- 日期过滤契约防止了最常见的 SQL 错误：将整数代理键与日期字符串比较（`WHERE pickup_date_key BETWEEN '2026-01-01' AND '2026-03-31'` 是类型错误）

**在当前项目中的位置**：
- `scripts/pipeline/layer3_plan.py`：`_resolve_layer()` 函数决定 G3/G2
- `scripts/pipeline/layer3_plan.py`：`_is_date_key_column()` 检测 _key 后缀
- `scripts/pipeline/layer3_plan.py`：`_build_dim_date_join()` 自动构造 dim_date JOIN
- `scripts/pipeline/layer5_validate.py`：`_check_date_compliance()` 校验日期合规

**输入**：指标的 G3/G2 可用性

**输出**：层级决策 + 可能触发 dim_date JOIN

**出错会导致什么风险**：如果 G2 日期过滤契约被绕过，SQL 中的日期比较会静默失败（整数与字符串比较在 DuckDB 中不会报错，但结果错误）。

**简单例子**：用户要查"2026 年 Q1 小费总额"——小费只有 G2 表 `gold.fact_trips` 包含，日期列是 `pickup_date_key`（整数）。系统自动：
1. 检测到 G3 不包含 total_tip_amount → 降级到 G2
2. 检测到 `pickup_date_key` 以 `_key` 结尾 → 触发 dim_date JOIN
3. 生成 SQL：`FROM gold.fact_trips JOIN gold.dim_date ON fact_trips.pickup_date_key = dim_date.date_key WHERE dim_date.date BETWEEN '2026-01-01' AND '2026-03-31'`

**Owner 审查时应该问什么**：
1. "G2 日期过滤契约是在代码的哪个位置实现的？如何验证它没有被绕过？"
2. "如果 TianShu 新增了一张 G3 汇总表，包含之前只有 G2 才有的指标，系统会自动切换到 G3 吗？"

---

### 8. JoinGraph（表关系图）

**是什么**：描述一条 SQL 中表之间关联方式的数据结构。包含主表（primary）、JOIN 列表（每个 JOIN 包含从表、JOIN 类型、ON 条件、约束来源）。

**它解决什么问题**：多表查询时，JOIN 的条件和方向必须精确。错误的 JOIN 会产生笛卡尔积、错误关联或遗漏数据。JoinGraph 将 JOIN 关系结构化——编译器不需要"理解" JOIN，只需要机械渲染。

**在当前项目中的位置**：
- `scripts/pipeline/layer3_plan.py`：JoinGraph、JoinNode、JoinCondition 数据类
- `scripts/pipeline/column_binding.py`：JOIN_WHITELIST（白名单 JOIN 路径）
- `scripts/pipeline/layer5_validate.py`：`_check_join_whitelist()` 校验 JOIN 是否在白名单中

**v2.1 修正**：JoinGraph 中的 condition 使用结构化 `{table_ref, column}` 引用，而非 SQL 别名字符串。编译器在别名分配阶段将 table_ref 映射为 SQL 别名。

**输入**：Intent（跨域标记）+ JOIN_WHITELIST

**输出**：JoinGraph 对象（包含 primary + joins[]）

**出错会导致什么风险**：JOIN 方向错误（`LEFT JOIN ON b.key = a.key` 写成 `ON a.key = b.key`）会导致数据错误或性能灾难。

**Owner 审查时应该问什么**：
1. "JOIN 白名单是谁维护的？新增 JOIN 路径的审批流程是什么？"
2. "如果用户需求涉及白名单中没有的 JOIN，系统如何响应？"

---

## §4 管道八层（Layer 1-8）

### 9. Layer 1：需求解析层（Requirement Parser）

**是什么**：解析 YAML 需求说明书，产出结构化的 Requirement 对象。优先使用规则解析器，YAML schema 不匹配时 LLM 可作 fallback。

**在当前项目中的位置**：`scripts/pipeline/layer1_requirement.py`

**输入**：YAML 文件路径 → 见 `fixtures/requirements/trip_daily_report.yml`

**输出**：Requirement 对象 `{name, description, metrics[], dimensions[], filters{}, output{}}`

**出错会导致什么风险**：YAML 解析失败会导致整个管道无法启动。

**Owner 审查时应该问什么**：
1. "如果用户提交了一个语法正确但语义不合法的 YAML（如查询不存在的指标），会在哪一层被拦截？"

---

### 10. Layer 2：意图理解层（Intent Agent）

**是什么**：将 Requirement 对象中的指标名与已注册指标精确匹配。精确匹配失败的指标才调 LLM 做模糊匹配。**这是 LLM 最后出现的地方。**

**在当前项目中的位置**：`scripts/pipeline/layer2_intent.py`

**输入**：Requirement 对象

**输出**：Intent 对象——`{metrics_requested[{registered_name}], dimensions[], filters{}, domain, confidence{}}`。**Intent 中不含表名、字段名、JOIN。**

**出错会导致什么风险**：如果 Intent 中的指标匹配错误，后续所有层基于错误指标生成 SQL——这是"失之毫厘，谬以千里"的起点。

**Owner 审查时应该问什么**：
1. "精确匹配和模糊匹配的优先级是什么？当两者冲突时如何处理？"
2. "如果 LLM 输出了一个未注册的指标名，Layer 2 会怎么处理？"

---

### 11. Layer 3：规划层（SQLPlan Planner）

**是什么**：纯确定性代码。从 Intent 出发，通过查表构造完整的 SQLPlan IR——包含 JoinGraph、ColumnBindings、FilterBindings、GroupBy、OrderBy、执行约束。

**在当前项目中的位置**：
- `scripts/pipeline/layer3_plan.py`（SQLPlan 及构造逻辑）
- `scripts/pipeline/layer3_pipeline_plan.py`（PipelinePlan——Phase 2 新增）

**输入**：Intent 对象

**输出**：SQLPlan 对象（或 PipelinePlan 对象）

**确定性保证**：LLM 完全禁止参与。所有决策通过查表和规则完成。

**出错会导致什么风险**：Layer 3 的决策错误（如选错数据源层级）会导致 SQL 执行失败或返回错误数据。

**Owner 审查时应该问什么**：
1. "Layer 3 的 7 个子步骤分别是什么？每个子步骤的输入输出能独立测试吗？"

---

### 12. Layer 4：编译层（SQL Compiler）

**是什么**：纯模板编译器。从 SQLPlan IR 机械拼接 SQL 文本。6 个编译 Pass + 最终 `"\n".join()` 组装。

**在当前项目中的位置**：
- `scripts/pipeline/layer4_generate.py`：SQL 编译编排层（SELECT/FROM/JOIN/WHERE/GROUP BY/ORDER BY/LIMIT）
- `scripts/pipeline/layer4_expression.py`：表达式编译器（P3 新建——10 种 ExpressionType × 3 方言）

**核心原理**：编译器不是"创作" SQL，而是把 IR 的每个字段序列化到对应的 SQL 模板位置，然后字符串拼接。`column_bindings[]` → SELECT 列，`join_graph` → FROM + JOIN，`filter_bindings[]` → WHERE。

**输入**：SQLPlan IR

**输出**：`(sql_text, params[])`——完整参数化 SQL + 参数列表

**出错会导致什么风险**：编译失败（抛 SQLCompileError）比生成错误 SQL 更安全——这是"fail-fast"原则。编译器必须宁可失败也不生成可能错误的 SQL。

**Owner 审查时应该问什么**：
1. "编译器在什么情况下会拒绝编译？返回错误信息还是生成不完整的 SQL？"
2. "如何验证编译器生成的 SQL 语法是正确的？"

---

### 13. Layer 5：校验层（SQL Validator + DAG Validator）

**是什么**：**纯规则引擎的安全门禁**。在 SQL 执行前执行 6 项检查（Phase 1）+ DAG 结构验证 + 安全层级操作合规检查（Phase 2）。**这是系统中最重要的安全层。**

**在当前项目中的位置**：
- `scripts/pipeline/layer5_validate.py`：SQL 级校验（安全黑名单、JOIN 白名单、日期合规）
- `scripts/pipeline/layer5_validate_pipeline.py`：PipelinePlan 级校验（DAG 环检测、安全层级合规）

**六项 Phase 1 检查**：
1. 禁止操作黑名单（INSERT/UPDATE/DELETE/DROP/TRUNCATE/ALTER 等 16 个关键字）
2. 只读前缀检查（必须以 SELECT/WITH/EXPLAIN/DESCRIBE/SHOW 开头）
3. 表引用合法性（禁止 bronze.* / silver.*）
4. 完全限定名检查（所有表名必须是 schema.table 格式）
5. JOIN 白名单检查
6. 日期合规检查（G2 必须 JOIN dim_date）

**Phase 2 新增检查**：
7. DAG 结构验证（环检测、依赖引用完整性、拓扑序合法性）
8. 安全层级操作合规（操作类型 × 目标 schema × safety_tier 三元合规矩阵）

**输入**：SQL 文本 + SQLPlan（或 PipelinePlan）

**输出**：ValidationReport `{passed, checks[], issues[], warnings[]}`

**出错会导致什么风险**：如果校验层被绕过，危险 SQL（DROP TABLE、DELETE FROM）可能被执行——这是灾难性的。

**Owner 审查时应该问什么**：
1. "校验层是纯规则引擎吗？有没有调用 LLM？"
2. "如果 SQL 通过了 Layer 5，是否意味着它一定是安全的？有哪些安全风险是 Layer 5 覆盖不到的？"

---

### 14. Layer 6：执行层（SQL Executor）

**是什么**：在 DuckDB 上执行已验证的 SQL。安全层级为 `query` 时使用 `read_only=True` 连接；安全层级为 `pipeline` 时允许写 `generated.*`（但 SQL 必须已通过 Layer 5 校验）。

**在当前项目中的位置**：`scripts/pipeline/layer6_execute.py`

**输入**：已验证的 SQL 文本 + 参数列表

**输出**：ExecutionResult `{success, dataframe, row_count, execution_time_ms}`

**约束**：30s 超时（query 层），禁止多语句，参数化查询防注入。

**出错会导致什么风险**：执行超时会浪费数据库资源。

**Owner 审查时应该问什么**：
1. "如果 SQL 执行超时或失败，管道如何处理？会重试吗？"

---

### 15. Layer 7：评估层（Result Evaluator）

**是什么**：执行后的统计检验。检查行数、空值率、列完整性、指标一致性。

**在当前项目中的位置**：`scripts/pipeline/layer7_evaluate.py`

**输入**：DataFrame + SQLPlan

**输出**：EvaluationReport `{status, checks[], warnings[]}`——检查：行数范围（< max_result_rows）、空值率（< 30%）、列完整性、指标一致性

**出错会导致什么风险**：质量检查过于宽松会导致脏数据进入产出物。

**Owner 审查时应该问什么**：
1. "空值率 > 30% 会拒绝吗？还是只报警？"
2. "谁定义什么算'合理的行数范围'？"

---

### 16. Layer 8：产出层（Product Publisher）

**是什么**：将结果数据、验证报告、调度任务配置输出到文件。

**在当前项目中的位置**：`scripts/pipeline/layer8_product.py`

**输出物**：
- `generated/results/{plan_name}_{timestamp}.parquet`——结果数据
- `generated/reports/{plan_id}_report_{timestamp}.md`——验证报告
- `generated/tasks/{plan_id}_task_{timestamp}.yml`——调度任务配置

**Owner 审查时应该问什么**：
1. "产出物的命名规则是什么？如何避免同名覆盖？"
2. "产出物可以直接接入调度平台吗？需要人工审核吗？"

---

## §5 安全体系

### 17. 安全黑名单（Safety Blacklist）

**是什么**：Layer 5 的第一道防线——16 个永久禁止的 SQL 关键字。任何层级（query/pipeline/admin）都不允许。

| 类别 | 禁止关键字 |
|------|-----------|
| DML | INSERT, UPDATE, DELETE, MERGE, REPLACE, TRUNCATE |
| DDL | CREATE, ALTER, DROP, RENAME |
| DCL | GRANT, REVOKE |
| 危险操作 | ATTACH, DETACH, EXPORT, IMPORT |
| 系统操作 | COPY, INSTALL, LOAD |

**在哪里**：`scripts/pipeline/layer5_validate.py` 的 `FORBIDDEN_KEYWORDS` 字典。

**重要**：v2.1 修正后，DELETE BY ANTI JOIN 已从所有枚举中移除——DELETE 在所有层级永久禁止。增量清理由 `INSERT OVERWRITE PARTITION` 等价实现。

**Owner 审查时应该问什么**：
1. "CREATE 在 pipeline 层级是允许的（CREATE TABLE AS SELECT），但在黑名单中。这个矛盾如何解决？"
   - **答案**：Layer 5 的校验不是只看黑名单，还会检查 operation 类型和 safety_tier 的组合。`CREATE TABLE AS SELECT` 在 `safety_tier=pipeline` 下是合法操作，但目标必须是 `generated.*`。

---

### 18. safety_tier（安全层级）

**是什么**：不是"模式"（mode），是递进的安全层级。`pipeline` 包含 `query` 的所有约束，再叠加写入限制。

| 层级 | 允许操作 | 允许写入 | 超时 |
|------|---------|---------|------|
| query | SELECT ONLY | 无 | 30s |
| pipeline | SELECT + CTAS + INSERT OVERWRITE + CREATE VIEW | generated.* 仅限 | 30min |

**在哪里**：
- `contracts/pipeline_execution_config_schema.yml`——执行层配置契约
- `scripts/pipeline/layer5_validate_pipeline.py`——安全层级合规检查

**为什么不在 IR 中**：safety_tier 是执行层参数——同样的 PipelinePlan IR 可以用 query 层级 dry-run，也可以用 pipeline 层级正式执行。

**Owner 审查时应该问什么**：
1. "如果有人在 pipeline 层级尝试写入 gold.*，会在哪一层被拦截？"
2. "query 层级和 pipeline 层级的校验逻辑是同一套代码吗？"

---

### 19. 参数化查询（Parameterized Query）

**是什么**：用户输入值通过 `?` 占位符绑定到 SQL，而非直接拼接进 SQL 字符串。防止 SQL 注入的最后一道防线。

**例子**：日期范围 `['2026-01-01', '2026-03-31']` 不会拼成 `WHERE date = '2026-01-01'`，而是 `WHERE date BETWEEN ? AND ?` + 参数列表 `['2026-01-01', '2026-03-31']`。

**在哪里**：`scripts/pipeline/layer4_generate.py` 的 `_compile_where_clause()`

---

## §6 质量保障体系

### 20. Prompt 回归（Prompt Regression）

**是什么**：定期自动运行固定的评测用例，对比 LLM 的 Intent 输出是否与基线一致。如果某次 LLM 升级后 Intent 输出变了，回归系统会告警。

**它解决什么问题**：LLM 模型的版本更新可能导致同一个需求被"理解"成不同的 Intent——即使两个理解都是合理的，也会导致输出 SQL 变化。Prompt 回归系统在产品环境中提供了一个客观的确定性保障——确保 LLM 的"翻译"行为是一致的。

**在当前项目中的位置**（当前阶段——尚未生效）：
- `evals/regression_baseline.yml`——基线状态定义（5 个端到端用例）
- `evals/e2e_cases.yml`——端到端测试用例
- 回归测试当前以 pytest 形式在 `tests/test_pipeline.py` 中运行（Layer 2 Intent 测试）
- **真实 LLM Prompt 回归报告系统：待实现**

**输入**：固定的评测用例（需求 YAML）

**输出**：对比报告——当前 LLM 输出 vs 基线 LLM 输出

**出错会导致什么风险**：LLM 的行为漂移意味着"确定性"被破坏——虽然 Layer 3-8 仍然是确定性的，但 Layer 2 的输出变了，整个链路的输出就变了。

**Owner 审查时应该问什么**：
1. "Prompt 回归测试多久跑一次？由谁触发？"
2. "如果回归测试失败了（Intent 输出变化），是自动拒绝部署还是人工审批？"
3. "回归基线是谁定义的？谁负责更新？"

---

### 21. E2E 测试（端到端测试）

**是什么**：从 YAML 需求到最终产出物的完整链路测试。当前 3 个端到端场景全部以 dry-run 模式运行（只生成 SQL，不执行）。总测试数 75 个（Phase 1: 19 + Phase 2: 25 + P3 表达式编译器: 31）。

**在哪里**：
- `tests/test_pipeline.py`：Phase 1 + P3 测试（50 个）——含 `TestEndToEndPipeline`、`TestExpressionCompiler` 等
- `tests/test_pipeline_phase2.py`：Phase 2 测试（25 个）——DAG 验证 + 安全层级合规

**当前覆盖场景**：
- 行程日报（trip_daily）—— 90 行 × 4 列
- 违章日报（parking_daily）—— 90 行 × 3 列
- 事故日报（crash_daily）—— 90 行 × 4 列

**Owner 审查时应该问什么**：
1. "E2E 测试覆盖了多少个业务域？有多少个用例？"
2. "如果新增一个需求类型（如跨域 JOIN），E2E 测试如何补充？"

---

### 22. Dry Run（干跑模式）

**是什么**：只跑 Layer 1-5（需求解析 → SQL 校验），不执行 SQL。用于快速验证"需求是否能通过全部校验"。

**如何使用**：`python scripts/pipeline/run_pipeline.py -r <需求文件> --dry-run`

**Owner 审查时应该问什么**：
1. "dry-run 和正式运行在安全上有什么区别？"

---

## §7 Phase 2 扩展概念

### 23. PipelinePlan（管道计划）

**是什么**：Phase 2 的核心 IR。SQLPlan 描述一条 SQL，PipelinePlan 描述包含多条 SQL 的 DAG。

**v2.1 修正**：PipelinePlan 只保留跨步骤概念（DAG 依赖、操作类型、输出目标、增量意图）。窗口函数、表达式、CTE 属于 SQLPlan（语句级），不在此层。

**在哪里**：`scripts/pipeline/layer3_pipeline_plan.py`、`contracts/pipeline_plan_schema.yml`

**Owner 审查时应该问什么**：
1. "PipelinePlan 和 SQLPlan 的边界在哪里？什么属于 Pipeline，什么属于 SQLPlan？"

---

### 24. DAG 验证器（DAG Validator）

**是什么**：Layer 5 的 Phase 2 扩展——纯静态分析 PipelinePlan 的 DAG 结构。
- 环检测（有环的 DAG 无法执行）
- 依赖引用完整性（`depends_on` 中的 step_id 必须存在）
- 拓扑序合法性（被依赖步骤必须先在 steps[] 中出现）

**在哪里**：`scripts/pipeline/layer5_validate_pipeline.py` 的 `validate_pipeline_dag()`

**测试**：25 个测试覆盖（环检测 6 个 + 引用完整性 3 个 + 拓扑序 3 个 + 安全层级 10 个 + 综合 3 个）

---

### 25. 增量意图（Incremental Intent）

**是什么**：IR 只描述"要不要增量"和"以什么键去重"。不包含执行策略（merge/append/overwrite）——策略由编译器根据目标表结构决定。

**在哪里**：`scripts/pipeline/layer3_pipeline_plan.py` 的 `IncrementalIntent` 数据类

**Owner 审查时应该问什么**：
1. "为什么不直接把 merge/append/overwrite 策略写在 IR 中？"

---

### 26. ColumnRef（统一列引用）

**是什么**：v2.1 引入的统一列引用结构 `{table_ref, column_name}`。所有引用列的地方（FilterBinding、WindowFunctionDef、ExpressionRef、ColumnBinding）都使用此结构。编译器在别名分配阶段将 table_ref 映射为 SQL 别名。

**在哪里**：`scripts/pipeline/layer3_plan.py` 的 `ColumnRef` 数据类

**解决什么问题**：之前系统中有三种不同的列引用方式（裸列名字符串、table_ref.column 字符串、全限定名），编译器无法统一处理。ColumnRef 消除了这个不一致。

**v2.3 完善**：伴随 IR Freeze，新的 `OrderByEntry(ColumnRef, direction)` 替代了 WindowFunctionDef 中的 `list[dict[str, str]]` 裸字典——多表 JOIN 时编译器现在能确定排序列属于哪个表。

---

### 27. IR 冻结（IR Freeze）

**是什么**：在进入编译器实现之前，对 IR 结构进行的最后审定和修正。冻结 = 所有字段类型已知、所有合法值可通过枚举穷举、JSON Schema 与 Python dataclass 完全一致。

**为什么需要**：编译器是 IR 的唯一消费者。如果 IR 中存在 `dict[str, Any]` 这样的无类型字段，编译器就无法在编译期保证正确性——它只能"猜"这个字典里有什么 key，猜错了就抛运行时异常。冻结消除了所有"猜测"。

**v2.3 冻结修正（C1-C6）**：

| 修正 | 变更内容 |
|------|---------|
| C1 | `ExpressionRef.config` 从 `dict[str, Any]` 改为 `ExpressionConfig` dataclass |
| C2 | `WindowFunctionDef.order_by` 从 `list[dict]` 改为 `list[OrderByEntry(ColumnRef, direction)]` |
| C3 | 移除 `CTEDefinition.materialized`（PostgreSQL 方言特定） |
| C4 | CTE 递归深度硬限制（Phase 2：CTE 体内不允许嵌套 CTE） |
| C5 | Python dataclass 字段名 `fully_qualified` → `column_ref`（与 Schema 一致） |
| C6 | 9 个自由字符串字段改为 `str+Enum` 枚举类 |

**冻结后状态**：44 个已有测试零回归。编译器可以安全地通过 `ExpressionType.DATE_DIFF`（而非字符串 `"date_diff"`）做分支，编译器知道 `ExpressionConfig` 有 `unit` 字段（而非从裸字典中 `get("unit")`）。

**Owner 审查时应该问什么**：
1. "IR 冻结后，新增一个表达式类型需要改哪些文件？流程是什么？"
2. "如果有人修改了 IR dataclass 但没更新 Schema，会在哪里被发现？"

---

### 28. ExpressionRef / 表达式编译器（P3 Expression Compiler）

**是什么**：Phase 3 交付的表达式编译系统。`ExpressionRef` 是表达式的 IR 定义——描述一个 SQL 表达式（如 `DATEDIFF('day', start, end)`）的结构化组成。表达式编译器将此 IR 编译为方言特定的 SQL 字符串。

**支持的表达式类型**（10 种）：`DATE_DIFF`、`DATE_TRUNC`、`DATE_FORMAT`、`ARITHMETIC`、`CONDITIONAL`（CASE WHEN）、`COALESCE`、`CAST`、`CONCAT`、`LITERAL`、`COLUMN_REF`

**支持的方言**（3 种）：DuckDB（默认）、Hive、PostgreSQL——通过注册表模式分发，未注册的类型自动 fallback 到 DuckDB 实现。

**关键设计决策**：

1. **注册表模式**：`_EXPRESSION_HANDLERS[dialect][ExpressionType]` 二级字典，O(1) 分发，无 if/elif 链
2. **两遍编译**：Pass 1 构建 `{alias → ExpressionRef}` 索引 → Pass 2 逐个编译，EXPR_REF 操作数递归展开
3. **ColumnRef 解析**：新增 `_build_table_ref_map` 将 `table_ref → SQL 前缀`，独立于旧式字符串 alias_map

**在哪里**：`scripts/pipeline/layer4_expression.py`（~460 行，新建文件）

**输入**：`list[ExpressionRef]` + 方言字符串 + table_ref_map

**输出**：`list[str]`——与输入一一对应的 SQL 表达式字符串

**测试**：31 个专项测试，覆盖全部 10 种表达式类型、3 种方言差异、嵌套表达式、SELECT 集成

**Owner 审查时应该问什么**：
1. "添加对新数据库方言的支持需要改多少代码？"
2. "嵌套表达式（EXPR_REF）的深度上限是多少？如何防止循环引用？"

---

### 29. 注册表模式（Registry Pattern —— 方言分发）

**是什么**：表达式编译器使用的**二级字典分发机制**，替代传统的 if/elif 链。`{方言: {表达式类型: 编译函数}}` ——每个方言只注册自己与默认实现不同的函数，缺失的自动 fallback 到 DuckDB。

**为什么不用 if/elif**：如果有 3 种方言 × 10 种表达式类型 = 30 个分支，if/elif 链会非常冗长且难以维护。注册表模式支持：运行时注册新方言、独立测试每种方言的每个表达式类型、编译器代码热加载新方言实现。

**示例**：
```python
# DuckDB 注册全部 10 种
_register_handler('duckdb', ExpressionType.DATE_DIFF, _compile_date_diff_duckdb)
# Hive 只注册与 DuckDB 不同的 3 种
_register_handler('hive', ExpressionType.DATE_DIFF, _compile_date_diff_hive)
# PostgreSQL 只注册 4 种差异
_register_handler('postgresql', ExpressionType.CAST, _compile_cast_postgresql)
```

**Owner 审查时应该问什么**：
1. "如果用户指定了一个不存在的方言，编译器的行为是什么？"
2. "如何验证所有方言的所有表达式类型都被覆盖了？"

---

## §8 项目文件地图

### 代码文件

| 文件 | 层 | 职责 |
|------|-----|------|
| `run_pipeline.py` | 入口 | 8 层全链路编排 |
| `layer1_requirement.py` | L1 | YAML 需求解析 |
| `layer2_intent.py` | L2 | 意图理解（LLM 辅助） |
| `layer3_plan.py` | L3 | SQLPlan 构造 |
| `layer3_pipeline_plan.py` | L3 | PipelinePlan 构造（Phase 2） |
| `layer4_generate.py` | L4 | SQL 编译（编排层） |
| `layer4_expression.py` | L4 | 表达式编译器（P3 新建——10类型×3方言） |
| `layer5_validate.py` | L5 | SQL 安全校验 |
| `layer5_validate_pipeline.py` | L5 | DAG + 安全层级校验（Phase 2） |
| `layer6_execute.py` | L6 | SQL 执行 |
| `layer7_evaluate.py` | L7 | 结果评估 |
| `layer8_product.py` | L8 | 产物输出 |
| `column_binding.py` | 中枢 | ColumnBindingTable + 动态加载 |

### 契约文件

| 文件 | 内容 |
|------|------|
| `contracts/requirement_schema.yml` | 需求说明书格式 |
| `contracts/sqlplan_schema.yml` | SQLPlan IR 格式 |
| `contracts/pipeline_plan_schema.yml` | PipelinePlan IR 格式（v2.1） |
| `contracts/pipeline_execution_config_schema.yml` | 执行层配置 |
| `contracts/validation_schema.yml` | 校验报告格式 |
| `contracts/result_schema.yml` | 结果文件格式 |

### 测试文件

| 文件 | 内容 |
|------|------|
| `tests/test_pipeline.py` | Phase 1（19 个）+ P3 表达式编译器（31 个） = 50 个测试 |
| `tests/test_pipeline_phase2.py` | Phase 2 测试（25 个） |

**总测试数：75 个（零回归）**

### 评测文件

| 文件 | 内容 |
|------|------|
| `evals/e2e_cases.yml` | 端到端测试用例 |
| `evals/regression_baseline.yml` | 回归基线 |

### 需求样例

| 文件 | 业务域 |
|------|--------|
| `fixtures/requirements/trip_daily_report.yml` | traffic |
| `fixtures/requirements/parking_daily_report.yml` | violation |
| `fixtures/requirements/crash_daily_report.yml` | safety |

---

## §9 快速检查表（Owner 10 分钟审查用）

| # | 检查项 | 查看文件 |
|---|--------|---------|
| 1 | LLM 是否参与 SQL 生成？ | `AGENTS.md` §1 |
| 2 | 安全黑名单是否完整？ | `layer5_validate.py` FORBIDDEN_KEYWORDS |
| 3 | 测试是否全部通过？ | `pytest tests/ -v`（应显示 75 passed） |
| 4 | ColumnBindingTable 是否覆盖所有指标？ | `column_binding.py` METRIC_BINDINGS |
| 5 | G2 日期过滤契约是否被校验？ | `layer5_validate.py` _check_date_compliance() |
| 6 | IR 中是否存在手写 SQL？ | `contracts/pipeline_plan_schema.yml`——检查是否包含 sql/text 字段 |
| 7 | safety_tier 的合规检查在哪？ | `layer5_validate_pipeline.py` SAFETY_TIER_OPERATIONS |
| 8 | DAG 环检测是否覆盖？ | `test_pipeline_phase2.py` TestDAGCycleDetection |
