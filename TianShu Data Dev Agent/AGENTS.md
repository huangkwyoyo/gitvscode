# Data Dev Agent — AGENTS.md

> 数据开发 Agent 核心规则文件。TianShu Data Dev Agent 是从属于 TianShu 数据仓库的确定性数据生产管道系统。
>
> 父规则：`D:\Program Files\gitvscode\TianShu\AGENTS.md`（TianShu 根 AGENTS.md）
> 配套契约：本目录 `contracts/` 下的 4 份 YAML 契约
> 事实源：TianShu DuckDB 中的 `meta.metric_definitions`、`meta.semantic_dimensions`、Gold 层表结构

---

## 1. System Role（系统角色）

**Data Dev Agent 是一个确定性的数据生产管道系统。**

它不是一个聊天机器人。它不是一个自由查询工具。它不是一个交互式 Text2SQL 工具。

它的唯一职责是：

```
用户提交结构化 YAML 需求说明书
  → Agent 解析需求
  → 匹配已注册指标和语义层
  → 确定性生成 SQL
  → 只读执行 SQL 抽取数据
  → 校验结果质量
  → 生成最终结果表和验证报告
  → 生成可接入调度平台的任务配置
```

### 核心约束

1. **LLM 不允许生成 SQL 或 SQL 片段。** SQL 由 ColumnBindingTable + 模板编译器确定性生成。
2. **LLM 不允许推荐表名、字段名、JOIN 条件。** 这些由 metric_registry、semantic_registry 和 JoinGraph 确定性构造。
3. **LLM 的职责边界**：仅在 Layer 1（YAML 解析）和 Layer 2（意图理解）中可参与，且只能输出 **结构化 JSON**。
4. **数据库设计文档、contracts、meta 表、Gold 层是唯一事实源。**
5. **禁止编造任何表、字段、指标、Join 关系。**

---

## 2. Routing（路由）

### 2.1 主路由

```
Request（YAML 需求说明书）
  ↓
[Layer 1] Requirement Parser  → 结构化 Requirement 对象
  ↓
[Layer 2] Intent Agent        → Intent 对象（WHAT，不含表/字段/JOIN）
  ↓
══════════ LLM 边界 ══════════
  ↓
[Layer 3] SQLPlan Planner     → 完整 SQLPlan + JoinGraph + ColumnBindings
  ↓
[Layer 4] SQL Compiler        → 完整 SQL 文本
  ↓
[Layer 5] SQL Validator       → 校验结果（通过/拒绝）
  ↓
[Layer 6] SQL Executor        → DataFrame + 执行元数据
  ↓
[Layer 7] Result Evaluator    → 评估报告
  ↓
[Layer 8] Product Publisher   → 结果文件 + 报告 + 任务配置
```

### 2.2 子路由（规划层内部）

```
Intent 对象
  ↓
[3a] 指标注册表查询 → 获取每个指标的来源表和字段
  ↓
[3b] 层级决策 resolve_layer() → G3 优先，G2 降级
  ↓
[3c] JoinGraph 构造 → 单表或多表（仅限白名单 JOIN）
  ↓
[3d] ColumnBinding 绑定 → 查 ColumnBindingTable
  ↓
[3e] 执行约束注入 → 来自 sql_safety_policy.yml + warehouse_connection.yml
  ↓
完整 SQLPlan 对象
```

### 2.3 降级路由

```
指标在 G3 可用？
  ├─ YES → 使用 G3 汇总表（首选）
  └─ NO  → 指标有 G2 表达式？
            ├─ YES → 使用 G2 fact 表
            └─ NO  → BLOCKED：告知用户缺失的指标来源
```

### 2.4 跨域路由

```
需求涉及多个业务域（traffic + safety）？
  ├─ YES → 检查跨主题 JOIN 白名单
  │         ├─ 允许（trip↔crash via G3 date）→ 构造 JoinGraph
  │         └─ 不允许 → BLOCKED
  └─ NO  → 单主题查询
```

---

## 3. Boundaries（边界）

### 3.1 LLM 不能做什么

| 禁止 | 原因 | 替代机制 | 代码证据 |
|------|------|---------|---------|
| 生成 SQL 文本 | SQL 必须可审计、可追溯 | ColumnBindingTable + 模板编译器 | `layer4_generate.py`——compile_sql() 纯模板编译，无 LLM 调用 |
| 推荐表名 | 表选择是确定性决策 | `resolve_layer()` 函数 | `layer3_plan.py:441`——_resolve_layer() 查 ColumnBindingTable |
| 决定 JOIN 条件 | JOIN 必须来自白名单 | JoinGraph 数据结构 | `column_binding.py:JOIN_WHITELIST`——硬编码白名单列表 |
| 映射 metric → column | 映射必须唯一确定 | ColumnBindingTable | `column_binding.py:get_binding_by_metric_name()`——纯函数查表 |
| 编造字段名 | 违背零幻觉原则 | 所有字段来自 meta.metric_definitions | `column_binding.py:METRIC_BINDINGS`——BindingEntry 列表 |
| 判断 G3 vs G2 | 层级选择是规则决策 | `resolve_layer()` 函数 | `layer3_plan.py:441`——纯 if/else 逻辑 |
| 绕过安全策略 | 安全是不可协商的 | Layer 5 纯规则引擎 | `layer5_validate.py:validate_sql()`——6 项硬检查 |

### 3.2 SQL 不能怎么生成

- **禁止字符串拼接**：不得用 f-string、`+` 或模板字符串直接拼接表名、字段名到 SQL
- **禁止裸标识符**：所有表名必须是 `schema.table` 全限定名，所有字段名必须是 `schema.table.column` 全限定名
- **禁止 FROM 子句中出现未在 semantic_contract.yml 中注册的表**
- **禁止 WHERE 子句中出现非日期列的裸日期比较**（必须通过 dim_date）

### 3.3 不能访问哪些表

- **禁止**：`bronze.*`（Bronze 原始摄入层）
- **禁止**：`silver.*`（Silver 中间清洗层）
- **禁止**：`*.raw_*`（原始数据表）
- **禁止**：未经 `semantic_contract.yml` 注册的任何表

### 3.4 不能绕过哪些函数

- **禁止**直接调用 `duckdb.connect()` 而不带 `read_only=True`
- **禁止**调用 `execute()` 执行非 SELECT 语句
- **禁止**调用 `install` / `load` 加载 DuckDB 扩展
- **禁止**绕过 `layer5_validate.py` 直接进入 `layer6_execute.py`
- **禁止**绕过 `layer3_plan.py` 直接在 `layer4_generate.py` 中构造 SQLPlan

---

## 4. Data Contracts（数据契约）

### 4.1 输入契约：需求说明书 YAML

定义在 `contracts/requirement_schema.yml`。

```yaml
# 最小有效需求
name: "需求名称"
description: "需求描述"
metrics:
  - name: "已注册的指标名"
dimensions:
  - name: "已注册的维度名"
filters:
  date_range: ["YYYY-MM-DD", "YYYY-MM-DD"]
output:
  format: "parquet"  # parquet | csv
```

### 4.2 中间契约：SQLPlan

定义在 `contracts/sqlplan_schema.yml`。

SQLPlan 是 Layer 3 → Layer 4 的唯一接口，包含：
- `join_graph`：表结构表达（primary table + joins[]）
- `column_bindings`：每列的全限定名绑定
- `filters`：过滤条件
- `group_by` / `order_by`：分组排序
- `execution_constraints`：执行约束

### 4.3 输出契约：执行结果

定义在 `contracts/result_schema.yml`。

### 4.4 校验契约：验证报告

定义在 `contracts/validation_schema.yml`。

---

## 5. Failure Policy（失败策略）

### 5.1 失败等级

| 等级 | 含义 | 行为 |
|------|------|------|
| **FAIL** | 硬约束违反，不可恢复 | 立即终止管道，不生成任何产出物 |
| **BLOCKED** | 需要人工介入才能继续 | 暂停管道，保留中间状态供排查 |
| **DIRTY** | 结果可能有问题但可交付 | 完成管道但标记 DIRTY，附加所有警告 |

### 5.2 每层失败映射

| 层 | FAIL | BLOCKED | DIRTY |
|----|------|---------|-------|
| Layer 1 | YAML 无法解析 | 必填字段缺失 | 可选字段缺失 |
| Layer 2 | 指标全不匹配（0/N） | 指标歧义需反问（如"金额"→3个候选） | 匹配置信度=medium |
| Layer 3 | 所有指标无 G3/G2 来源 | 降级到 G2 但 G2 表达式未注册 | G3 表数据可能为空的时间范围 |
| Layer 4 | ColumnBindingTable 缺少必要绑定 | — | — |
| Layer 5 | 检测到 DML/DDL 关键词 | — | 使用非 G3 表触发降级警告 |
| Layer 6 | SQL 执行超时 30s | DB 文件锁定 | 返回 0 行 |
| Layer 7 | 关键指标列缺失 | 行数超过预期上限需确认 | 空值率 >30% |
| Layer 8 | 磁盘写入失败 | — | — |

### 5.3 重试规则

| 场景 | 重试次数 | 间隔 | 超限处理 |
|------|---------|------|---------|
| Layer 6 执行超时 | 1 | 5s | 升级为 FAIL |
| Layer 6 DB 锁定 | 1 | 10s | 升级为 BLOCKED |
| 其他层 | 0 | — | 直接失败 |

### 5.4 Fallback 规则

```
G3 汇总表不包含所需维度？
  → 自动降级到 G2 fact 表（如果该指标的 g2_expression 已注册）

G2 也不包含所需维度？
  → BLOCKED，告知用户当前数据不支持该维度分析

跨主题 JOIN 不在白名单？
  → BLOCKED，告知用户该 JOIN 路径未核准

日期范围超出 dim_date 覆盖范围（1997-2027）？
  → FAIL，sql_safety_policy 要求所有日期过滤通过 dim_date
```

### 5.5 拒绝（Refusal）规则

以下情况**无条件拒绝**，不生成任何 SQL：

1. **未注册指标**：用户指定的指标名不在 `meta.metric_definitions` 中
2. **禁止表访问**：需求隐式或显式涉及 `bronze.*`、`silver.*` 表
3. **非法 JOIN**：需要不被白名单允许的跨事实表 JOIN
4. **日期越界**：过滤日期范围完全超出 dim_date 覆盖范围
5. **非只读意图**：需求描述中包含"修改""删除""更新""插入"等操作

拒绝时输出：
- 拒绝原因
- 涉及的具体指标/表/JOIN
- 可能的替代方案（如有）
- 需要人工确认的内容

---

## 6. 开发规则

### 6.1 代码规范

- 所有代码注释使用中文
- 注释解释"为什么"而非"是什么"
- 函数使用简短中文 docstring

### 6.2 目录约定

- `scripts/pipeline/`：管道各层实现
- `scripts/quality/`：质量检查脚本
- `generated/`：所有自动生成的产出物
- `fixtures/`：手工编写的测试数据
- `evals/`：评测用例和基线

### 6.3 文件命名约定

- 产出文件名格式：`{描述}_{YYYYMMDD}_{HHMM}.{ext}`
- 契约文件使用英文 snake_case

### 6.4 与 TianShu 的关系

- 本 Agent 通过 `contracts/` 中定义的接口连接 TianShu
- DuckDB 连接路径、表结构、指标定义均以 TianShu 为事实源
- 不得在本项目中复制 TianShu 的数据库设计文档或字段字典
- 如需要 TianShu 中不存在的数据，必须通过 TianShu 的变更流程（见父 AGENTS.md §13）

---

## 7. Code Review Classification System（代码审查分类系统）

> 所有 Codex / Claude Code / Agent 输出的代码审查、问题分析、修复建议，**必须先进行 A/B/C 分类**。

### 7.1 总原则

1. **每一个发现的问题都必须单独归类为 A / B / C 之一。**
2. **单个问题不允许混合分类。**
3. 如果分类存在争议，按更高风险类别处理：**C > B > A**。
4. 分类必须出现在每个问题分析的开头。
5. **禁止输出未分类的审查结论。**
6. **禁止绕过分类直接修改代码。**

---

### 7.2 A类（AUTO-FIX）

#### 定义

可局部安全修复的问题，例如：

- 明确代码错误
- 工具函数 Bug
- 测试缺失
- 局部逻辑错误
- 不影响架构边界的小型修复

#### 处理方式

- **允许直接修改代码**
- 必须附带单元测试
- 不需要架构确认

#### 限制

A 类修复**不得改变**以下任一边界：

| 边界 | 说明 |
|------|------|
| Agent 行为边界 | LLM 参与范围、管道路由逻辑 |
| SQLPlan 流程 | Layer 3→4 的 IR 传递链路 |
| SQL 安全门禁 | Layer 5 校验规则、安全策略 |
| Prompt 语义 | 任何 LLM prompt 的含义或结构 |
| Schema 结构 | contracts/ 中的 YAML 契约定义 |
| Memory 写入机制 | 记忆系统的读写行为 |

> 如果触碰以上任一边界，**必须升级为 B 类或 C 类**。

---

### 7.3 B类（DESIGN-REVIEW）

#### 定义

需要设计确认的问题，例如：

- 代码与当前设计文档不一致
- 模块职责模糊
- Pipeline 流程需要确认
- Prompt / Pipeline 行为不一致
- IR / Schema 使用方式存在歧义
- 修复方式存在多种选择

#### 处理方式

**禁止直接修改代码。**

必须先输出：

1. **当前实现说明**——代码现状，引用具体文件和行号
2. **问题分析**——为什么当前实现有问题
3. **至少 3 种修复方案**——每种方案的利弊和影响范围
4. **推荐方案及理由**——明确推荐哪一个，说明原因

> 需要项目 Owner 确认后才能执行修改。

---

### 7.4 C类（ARCHITECTURE-RISK）

#### 定义

涉及系统核心边界或高风险行为的问题，例如：

- 可能影响 Agent 行为边界
- 可能破坏 SQL 安全链路
- 可能绕过 SQLPlan 流程
- 可能影响 Schema / Memory / Prompt 体系
- 可能引入 LLM 自由执行能力
- 可能允许 LLM 直接生成 SQL
- 可能放宽 DuckDB read-only 或 SQL safety 限制

#### 处理方式

**绝对禁止自动修复。**

必须先输出**风险评估报告**：

##### 必含内容

1. **深度风险分析**——问题根因和潜在危害
2. **系统影响范围**——哪些模块、哪些管道层受影响
3. **边界检查清单**（逐项确认）：

   | 边界 | 是否触及 | 说明 |
   |------|---------|------|
   | SQL 安全门禁（Layer 5） | 是/否 | |
   | SQLPlan 流程（Layer 3→4） | 是/否 | |
   | Schema 约束（contracts/） | 是/否 | |
   | Memory 写入机制 | 是/否 | |
   | LLM 是否可能直接生成 SQL | 是/否 | |
   | DuckDB read-only 限制 | 是/否 | |
   | 管道路由逻辑 | 是/否 | |

4. **至少 2 种安全替代方案**——每种方案说明安全边界是否保持完整

> **必须由项目 Owner 显式批准后，才能进入下一步。**

---

### 7.5 输出格式

每个审查发现**必须**使用以下格式：

```text
【分类】：A类 / B类 / C类
【理由】：简述归类原因
【问题】：说明发现的问题
【处理建议】：说明下一步动作
```

> 如果一次审查发现多个问题，**必须逐条分类**，不允许只给整体分类。

---

### 7.6 与本项目边界的对照

CRCS 分类时，以下为本项目的**关键硬边界**（触碰即 C 类）：

| 硬边界 | 来源 |
|--------|------|
| LLM 不允许生成 SQL 或 SQL 片段 | §1 核心约束 #1 |
| LLM 不允许推荐表名、字段名、JOIN 条件 | §1 核心约束 #2 |
| LLM 仅在 Layer 1-2 可参与，且只能输出结构化 JSON | §1 核心约束 #3 |
| SQL 由 ColumnBindingTable + 模板编译器确定性生成 | §1 核心约束 #1 |
| 禁止绕过 Layer 5 校验直接执行 | §3.4 禁止绕过 |
| 禁止绕过 Layer 3 规划直接编译 | §3.4 禁止绕过 |
| 禁止访问 bronze.* / silver.* 表 | §3.3 禁止访问 |
| 禁止编造表、字段、指标、Join 关系 | §1 核心约束 #5 |
| DuckDB 连接必须 read_only=True | §3.4 禁止绕过 |
| JOIN 必须来自白名单 | §2.4 跨域路由 |

---

### 7.7 复杂审查的 Skill 辅助规则

> **核心规则**：对于高风险审查、复杂设计审查、架构边界审查，优先使用 `superpowers` / `review` skill 辅助拆解；但最终分类和结论仍必须落到 CRCS 的 A/B/C 体系。Skill 输出不替代人工判定。

#### 审查场景 → Skill 映射

| 审查场景 | 推荐辅助 Skill | 使用目的 |
|---------|---------------|---------|
| C 类 — 架构边界风险 | `superpowers:brainstorming` | 拆解风险链路、穷举影响面、识别所有触及的硬边界 |
| C 类 — SQL 安全链路审查 | `security-review` | 逐项检查 Layer 5 门禁、DuckDB read-only、白名单合规 |
| B 类 — 设计一致性审查 | `review` | 多维对比当前实现 vs contracts + 设计文档 |
| B 类 — 修复方案选择 | `superpowers:brainstorming` | 生成 ≥3 种可行方案并对比安全影响 |
| B/C 类 — 代码审查报告 | `code-review` | 生成结构化审查发现，再由审查者逐条归入 A/B/C |
| A/B/C 类 — 验证修复效果 | `verify` | 修改后确认行为无回归、安全边界完整 |

#### 使用约束

1. **Skill 输出仅作为分析素材**——最终分类判定必须由审查者根据 §7.2-§7.4 定义执行，不得直接套用 skill 的分类结论
2. **问题必须逐条拆解**——Skill 发现的多个问题必须逐条独立归类，禁止整体套用分类
3. **C 类不可替代**——对 C 类问题，skill 输出不可替代 §7.4 要求的完整风险评估报告（深度风险分析 + 系统影响范围 + 边界检查清单 + ≥2 种安全替代方案）
4. **硬边界优先**——Skill 分析过程中若发现触及 §7.6 中任一硬边界，立即升级为 C 类，终止 skill 辅助，输出完整风险评估报告
