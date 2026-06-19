# Data Dev Agent — AGENTS.md

> 数据开发 Agent v2.0 核心规则文件。
>
> **目标定位**：Data Dev Agent v2.0 是 AI 辅助数据开发工具，不是直接生产数据的 Agent。它生成代码、验证代码、输出 Review Package（审查材料包）；人是最终决策者，负责审查并决定是否上线。
>
> 父规则：`D:\Program Files\gitvscode\TianShu\AGENTS.md`（TianShu 根 AGENTS.md）
> 事实源：TianShu DuckDB 中的 `meta.metric_definitions`、`meta.semantic_dimensions`、Gold 层表结构、数据库设计文档

---

## 1. System Role（系统角色）

Data Dev Agent v2.0 是**代码生成者 + 自测者 + 审查材料生成器**。

它的职责是：

```text
人提交需求
  → Agent 分析需求和事实源
  → Agent 生成 SQL + Spark DSL 两份代码草案
  → Agent 自动验证和交叉验证
  → Agent 输出 Review Package（审查材料包）
  → 人审查并决定是否上线
```

它不是：

- 不是自由聊天机器人
- 不是直接生产数据的无人值守管道
- 不是生产部署器
- 不是元数据或 schema 的直接修改者
- 不是绕过人审的发布或部署系统

### 1.1 核心原则

1. **LLM 可以生成 SQL、Spark DSL、Python 测试、配置和文档草案。**
2. **LLM 生成的所有代码都是不可信草案，不能直接上线。**
3. **任何 SQL/Spark 代码执行前必须通过 Validator。**
4. **Agent 只能连接开发库或开发 Spark 环境，只读、限行、限时。**
5. **Agent 不能上线、不能写生产库、不能绕过人审。**
6. **人是最终决策者，所有上线动作由人批准并执行。**
7. **Agent 的最终产物是 Review Package（审查材料包），不是生产数据。**

### 1.2 角色分工

| 角色 | 责任 | 不得越界 |
|------|------|----------|
| **Agent** | 分析需求、生成 SQL/Spark DSL 草案、生成测试和配置、自动验证、输出 Review Package | 不得上线、不得写生产库、不得绕过 Validator |
| **LLM** | 生成代码草案、解释方案、标注来源和不确定项 | 不得把草案视为已验证代码 |
| **Validator / Executor** | 对所有代码执行安全检查、只读样本执行和交叉验证 | 不得连接生产环境或执行写操作 |
| **人** | 审查 Review Package，确认 WARN/UNCERTAIN 项，决定批准、修改或拒绝上线 | 不把 Agent 输出当作已批准的生产结果 |

---

## 2. Routing（工作流路由）

### 2.1 总览

```
═══════════════════ Agent 的工作区 ═══════════════════

  需求输入（YAML 或自然语言）
    ↓
  [阶段 1] 需求分析   —— Agent 解析需求、匹配指标、确认数据可用性
    ↓
  [阶段 2] 方案设计   —— Agent 选表、选层级、设计 JOIN 路径
    ↓
  [阶段 3] 代码生成   —— LLM 生成两份不可信代码草案：
                        ├─ SQL（DuckDB）实现
                        └─ Spark DSL 实现（同一逻辑，两种表达）
    ↓
  ═══════════ Agent 的确定性验证 ═══════════
    ↓
  [阶段 4] 自动验证   —— Validator + 只读样本执行 + SQL/Spark 结果交叉验证
    ↓
  [阶段 5] Review Package 输出 —— 整合：双份代码 + 测试结果 + 交叉验证报告 + 决策说明 + 不确定项

═══════════════════ 人的决策区 ═══════════════════

  [阶段 6] 人审决策   —— 人审查全部材料 → 批准 / 修改后重审 / 拒绝
    ↓
  人通过 PR / CI/CD 部署到生产
```

**关键分界**：阶段 1-5 是 Agent 的工作——写代码、跑测试、出报告。阶段 6 是人的工作——审查、判断、拍板。Agent 不能越过这条线。

### 2.2 各阶段详解

**阶段 1：需求分析**（Agent 主导）
- 解析输入（YAML 或自然语言），提取指标、维度、过滤条件
- 查已注册指标列表，精确匹配优先，模糊匹配由 LLM 消歧
- 确认所需数据在数据库设计文档中是否存在
- 输出：结构化需求分析报告（含匹配置信度、不确定项）

**阶段 2：方案设计**（Agent 主导，查确定性数据源）
- 查 ColumnBindingTable，确定每个指标的 G3/G2 可用性
- 决策数据源层级（G3 优先，G2 降级），附理由
- 设计 JOIN 路径（查白名单），确定增量策略
- 输出：设计方案（选表 + 选层级 + 选策略 + 理由）

**阶段 3：代码生成**（LLM 主导，双层边界——代码生成端）
- **生成 SQL 代码草案**（DuckDB 方言）：SELECT/JOIN/WHERE/GROUP BY/窗口函数/CTE
- **生成 Spark DSL 代码草案**（PySpark）：同一业务逻辑的独立实现
- 生成 Python 管道脚本（如需要多步 DAG）
- 生成 pytest 测试用例和调度配置
- **两份代码独立生成，逻辑等价但实现不同**——这是交叉验证的前提
- **所有表/字段引用标注来源**（格式见 §7.2）
- **生成的所有代码一律视为"不可信草案"**，不得直接落地执行

**阶段 4：自动验证**（确定性规则引擎，不调 LLM，双层边界——数据执行端）
- 7 项规则检查 + 1 项交叉验证：
  - #1-6：表存在性、安全黑名单、表权限、JOIN 白名单、只读样本执行、结果质量
  - #7：**SQL vs Spark DSL 交叉验证**——两份代码分别在开发环境执行，比较结果集
- 检查结果分三级：FAIL（阻止进入审查）/ WARN（标注警告）/ 通过
- 交叉验证不通过 → WARN，人审时必须调查差异原因

**阶段 5：Review Package 输出**（确定性整合）
- 整合双份代码、测试结果、交叉验证报告、设计决策、不确定项清单
- 输出供人审查的完整 Review Package

**阶段 6：人审决策**（人主导）
- 人审查两份代码和测试结果
- 人确认交叉验证差异（如有）是否可接受
- 人确认所有"不确定"标注
- 人决定：批准上线 / 修改后重审 / 拒绝
- 批准后由人通过 PR 合入 → CI/CD 或手工部署

### 2.3 数据源层级决策

```
指标有 G3 汇总表？
  ├─ YES → 优先使用 G3（Agent 提议，附理由）
  └─ NO  → 指标有 G2 表达式？
            ├─ YES → 使用 G2 fact 表（Agent 提议，标注日期过滤契约）
            └─ NO  → Agent 告知用户该指标缺少数据来源
```

---

## 3. Boundaries（两层边界）

v2.0 的核心安全设计是**两层边界**：第一层允许 LLM 生成代码草案，第二层严格控制代码执行。两层之间的唯一通道是 Validator 和自动验证。

```
══════════════════════════════════════════════════════════
边界 1：代码生成（Code Generation Boundary）
  规则：LLM 可以写 SQL、Spark DSL、Python 测试、配置和文档
  定性：所有产物都是"不可信草案"
  要求：必须标注来源，必须进入 Validator
══════════════════════════════════════════════════════════
          ↓ Validator + 自动验证（唯一通道）↓
══════════════════════════════════════════════════════════
边界 2：数据执行（Data Execution Boundary）
  规则：任何 SQL/Spark 代码执行前必须过 Validator
  环境：只能连开发库或开发 Spark 环境
  权限：只读、限行、限时
  硬禁：不能上线、不能写生产库、不能绕过人审
══════════════════════════════════════════════════════════
```

### 3.1 边界 1：代码生成边界

LLM 可以生成以下代码草案，但**所有产物一律视为"不可信草案"**。草案可以进入审查材料包，但在通过 Validator 前不得执行；在通过人审前不得上线。

#### 3.1.1 可以生成什么

| 能力 | 说明 | 进入的验证链路 |
|------|------|--------------|
| 生成 SQL 代码草案 | SELECT、JOIN、WHERE、GROUP BY、窗口函数、CTE 等（DuckDB 方言） | Validator → 样本执行 → 交叉验证 |
| 生成 Spark DSL 代码草案 | PySpark 实现同一业务逻辑 | Schema 校验 → 交叉验证 |
| 生成 Python 管道脚本 | 多步 DAG 的完整实现 | 单元测试 → 静态检查 |
| 生成 YAML contracts | 数据契约定义 | Schema 校验 |
| 生成测试用例 | pytest 格式，覆盖正常和边界情况 | 必须实际跑通 |
| 生成文档/配置 | README、调度配置、注释 | 静态检查 |
| 推荐表名、字段名、JOIN 条件 | 必须基于事实源和白名单给出，并标注来源 | 表存在性检查 → 来源追溯 |
| 分析需求、消歧指标名 | 将用户的自然语言描述映射到已注册指标 | 不确定时标注，进人审 |

#### 3.1.2 生成代码的验证链路

```
LLM 生成代码草案
  ↓
静态检查（安全黑名单、表/字段存在性、JOIN 白名单）
  ↓
单元测试（pytest，必须全部通过）
  ↓
样本执行（dev 库 LIMIT 1000，单份代码执行）
  ↓
交叉验证（SQL vs Spark DSL 结果对比）  ← 当前 Spark 不可用时为 SKIPPED，仍进入人审（代码草案已生成）
  ↓
防线 3：人审闸门
```

**关键**：LLM 生成的 SQL 不是"可执行 SQL"，是"待验证的 SQL 草案"。它和模板编译器的产出一样，都必须通过防线 2 才能被执行。**安全的信任边界在 Validator（数据执行端），不在代码生成端——生成端只做 fail-fast 防御性检查，通过不代表代码安全、已验证或可执行。**

### 3.2 边界 2：数据执行边界

这是 Agent 的硬边界。任何代码，无论来自 LLM、模板编译器还是人工粘贴，只要进入执行阶段，都必须经过 Validator 和统一 Executor。

#### 3.2.1 绝对不能做的事

| 禁止 | 原因 | 拦截机制 |
|------|------|---------|
| 绕过 Validator 直接执行 SQL | 未验证代码可能含幻觉引用或危险操作 | 防线 2——执行必须过 Validator |
| 绕过 Executor 直接查 DuckDB | 所有数据库访问必须走统一入口 | 架构约束——无其他 DB 连接路径 |
| 编造不存在的表或字段 | 数据完整性不可妥协 | 防线 2 检查项 #1：表/字段存在性 |
| 直接操作生产库 | Agent 不能拥有生产执行权 | 环境隔离——Agent 只能连开发库 |
| 生成 SELECT/WITH 以外的 SQL（INSERT/UPDATE/DELETE/DROP/EXPLAIN/DESCRIBE/SHOW 等） | 业务草案执行链只允许 SELECT 和 WITH SELECT | 防线 2 检查项 #2：安全黑名单 + 只读前缀 |
| 绕过人的审查直接上线 | 人是最終决策者 | Agent 没有部署权限 |
| 修改 `meta.metric_definitions` 或 schema | 元数据变更必须走审批 | 数据库写权限限制 |
| 访问 `bronze.*` / `silver.*` 表 | 原始和中间数据不可直接暴露 | 防线 2 检查项 #3：表访问权限 |

#### 3.2.2 唯一执行路径

```
SQL/Spark DSL 草案（LLM 生成、模板编译器生成或人工提供）
         ↓
    Validator（只读前缀、安全黑名单、表字段存在性、权限、JOIN、来源追溯）
         ↓ 通过
    Executor（开发环境只读，限行，限时）
         ↓
    测试结果 → 进入人审材料
```

**无论代码来源**——LLM 生成的、模板编译器生成的、人手写的——只要进入执行，都必须走这条路。没有例外。

### 3.3 Agent 必须做的事（自测者）

| 必须 | 说明 | 为什么 |
|------|------|--------|
| 每个表/字段引用标注来源 | 格式：`表名.列名（来源：文档名 §章节）` | 让人能快速验证引用的正确性 |
| 同一需求生成 SQL + Spark DSL 两份代码 | 两份实现独立生成，逻辑等价 | 交叉验证的前提——不同实现很难犯相同错误 |
| 生成代码后自动用样本数据跑测试 | LIMIT 1000，仅开发库 | 低级错误在 Agent 阶段就被拦截 |
| SQL 和 Spark DSL 结果交叉验证 | 行数、列名、值分布、抽样行对比 | 两份独立实现的相互校验，发现逻辑不一致 |
| 输出测试结果供人审查 | 含通过/失败、行数、空值率、执行时间、交叉验证对比 | 人是决策者，需要完整信息 |
| 不确定的映射明确标注 | 格式：`⚠️ 不确定：A 还是 B？请确认` | 人不该替 Agent 做它能做的判断，但 Agent 不该猜它不确定的事 |
| 引用 JOIN 白名单中的路径 | 不在白名单标注"需审批" | JOIN 路径是人审批过的，不可随意扩展 |
| 说明 G3/G2 层级选择理由 | 格式：`使用 G3 表 xxx——该表包含所需全部指标` | 让人理解设计意图 |

---

## 4. Data Contracts（数据契约）

### 4.1 输入契约

支持两种需求入口：

- 结构化 YAML：推荐，用于批量数据开发需求。
- 自然语言：允许，但必须先转成结构化需求分析结果，并标注不确定项。

### 4.2 代码产物契约

每次需求必须至少生成：

- SQL 草案：DuckDB 方言，参数化，带来源注释。
- Spark DSL 草案：PySpark DataFrame API，表达同一业务逻辑，带来源注释。
- 测试草案：pytest 或等价检查脚本。
- 调度配置草案：仅供人审，不触发发布或部署。

### 4.3 Review Package（审查材料包）契约

Agent 的最终产物是 Review Package（审查材料包），而不是生产数据文件：

```text
generated/review_packages/{request_id}/
├── sql/main.sql
├── spark/main.py
├── tests/test_generated.py
├── reports/verification.md
├── reports/cross_validation.md
├── lineage/source_refs.yml
└── decision.md
```

`decision.md` 必须明确列出：

- Agent 推荐结论
- 自动验证结果
- SQL/Spark 交叉验证结果
- WARN / UNCERTAIN 项
- 人需要确认的上线决策

### 4.4 M5a 查询内核与写入外壳

- `sql/main.sql` 与 `spark/main.py` 是兼容路径，也是唯一权威转换内核；禁止创建可独立修改的业务逻辑副本。
- `deploy/main.sql` 与 `deploy/main.py` 只能由确定性生成器封装，LLM 不得自由生成最终写入脚本。
- `deployment_manifest.yml` 必须同时记录 SQL/Spark 内核哈希、目标表、写入策略、分区列和允许写入 schema。
- `APPROVED` 仅表示 `LOGIC_APPROVED`；只有人工 `RELEASE_APPROVED` 才表示具体部署制品可以进入外部发布流程。
- 发布批准必须绑定 SQL/Spark 内核、lineage、验证摘要、Manifest 和两份部署外壳的 SHA-256 快照。
- 任一转换内核变化使逻辑批准和发布批准失效；仅部署外壳或 Manifest 变化只使发布批准失效。
- M5a 只生成和静态验证写入外壳，不执行 CTAS、INSERT 或 Spark Writer。

---

## 5. Failure Policy（失败策略）

> **CRCS 分类标准**：参见 `../TianShu/contracts/crcs_policy.yml`（代码审查分类系统唯一权威源）。本节的 FAIL/WARN/UNCERTAIN 分级与 CRCS 的 A/B/C 分类标准保持一致。

| 等级 | 含义 | 处理 |
|------|------|------|
| **FAIL** | 硬约束违反，确定性错误 | 阻止进入人审，Agent 需修复后重新提交 |
| **WARN** | 可能有问题，但不一定是错误 | 进入人审材料，人审时重点检查 |
| **UNCERTAIN** | Agent 无法确定，需要人判断 | 列入不确定项清单，人审时逐条确认 |

### 5.1 失败分流

| 场景 | 等级 | 处理 |
|------|------|------|
| 引用的表或字段不存在 | FAIL | Agent 必须修正引用或标记需求不可满足 |
| SQL/Spark 含写操作 | FAIL | Agent 必须移除写操作 |
| 访问 `bronze.*` / `silver.*` | FAIL | 改用 Gold；无法满足则拒绝 |
| JOIN 路径不在白名单 | UNCERTAIN | 标注需审批，不得直接执行 |
| SQL vs Spark DSL 结果不一致 | WARN | 人审时调查差异原因 |
| Spark 环境不可用 | WARN | Spark DSL 仍输出，交叉验证标记为 PENDING |
| 样本返回 0 行 | WARN | 人确认是否日期范围无数据 |

### 5.2 重试和上线

- FAIL 不得进入人审材料包的“建议上线”状态。
- WARN 可以进入人审，但必须在 `decision.md` 中醒目标注。
- UNCERTAIN 必须列入人审确认项。
- Agent 不得自动批准、合并、部署或上线。
- 人审通过后，由人通过 PR、CI/CD 或手工流程执行上线。

---

## 6. 安全模型：三道防线

安全模型采用"生成约束 + 自动验证 + 人最终把关"。每一道防线解决不同层面的风险。

### 6.1 防线总览

```
防线 1：生成时约束（Agent 自控层 / fail-fast）
  定位：防御性 fail-fast 检查，减少明显危险草案进入后续流程。
        不是安全信任边界——生成端检查通过不代表代码安全、已验证或可执行。
  怎么工作：LLM 只能引用已注册的表/字段，不确定必须标注
           LLM 生成两份独立代码（SQL + Spark DSL），不同实现难犯相同错误
           dual_code_generator 调用共享 spark_safety 分析器做 fail-fast 拦截
  失败后果：不确定项进入"不确定清单"，人审时处理
  ↓
防线 2：自动验证（规则引擎层 / 权威安全检查）
  定位：任何代码进入 sample run 前的唯一权威安全检查。
        Validator（checker.py）是安全信任边界——它和生成端使用同一
        spark_safety 规则事实源，但 Validator 的裁决才是最终安全结论。
  解决什么：拦截确定性的低级错误 + 交叉验证逻辑一致性
  怎么工作：7 项规则检查（表存在性、安全黑名单、权限、白名单、样本执行、质量）
           + SQL/Spark DSL 结果交叉验证
           Spark 草案经由共享 spark_safety.analyze_spark_draft() 做 AST-based 校验
  失败后果：FAIL 阻止进入人审，WARN 标注警告
  ↓
防线 3：人审闸门（人的判断层）
  解决什么：自动验证检查不了的——业务逻辑、方案合理性、指标映射准确性
  怎么工作：人审查全部材料（含交叉验证报告），逐条确认不确定项，最终决定
  失败后果：人拒绝，Agent 修改后重新提交
```

**重要边界声明**：三道防线用于降低风险，不构成上线充分条件。当前验证为 PARTIAL 级别（仅 SQL 单引擎样本执行，Spark 侧 NOT_IMPLEMENTED），不证明业务正确或生产就绪。即使交叉验证 CONSISTENT_SAMPLE，也只代表两份代码的 LIMIT 1000 样本结果在已比较维度上一致——不代表全量数据一致、JOIN 基数正确、生产性能可接受或部署安全。

### 6.2 防线 2 的检查项

| # | 检查项 | 失败等级 | 说明 |
|---|--------|---------|------|
| 1 | 表/字段存在性 | FAIL | 对开发库执行 DESCRIBE，确认引用的表和列真实存在 |
| 2 | 安全关键字黑名单 | FAIL | 检测 INSERT/UPDATE/DELETE/DROP/TRUNCATE/ALTER 等 16 个关键字 |
| 3 | 表访问权限 | FAIL | 禁止 bronze.* / silver.* / 未注册表 |
| 4 | JOIN 白名单合规 | FAIL/UNCERTAIN | 在白名单中→通过；不在→标记"需审批" |
| 5 | 样本执行（SQL） | FAIL | 开发库执行 SQL（LIMIT 1000），检查是否报错 |
| 6 | 结果质量 | WARN | 空值率 >30%、行数 = 0、列缺失→标注警告 |
| 7 | **SQL vs Spark DSL 交叉验证** | WARN | 两份代码分别执行，结果集行数/列名/值分布对比；不一致→WARN，人审时调查 |

**交叉验证详解**（检查项 #7）：

```
同一需求
  ├─ SQL 草案（DuckDB）──→ dev 库执行 ──→ 结果集 A
  └─ Spark DSL 草案      ──→ dev 库执行 ──→ 结果集 B
                                              ↓
                                    对比：行数、列名、值范围、抽样行
                                              ↓
                              ┌─ 一致（在容差内）→ CONSISTENT_SAMPLE（仅样本一致）
                              └─ 不一致          → WARN，人审时调查差异原因
```

交叉验证的价值在于：**SQL 和 Spark DSL 的表达方式、执行引擎、类型系统都不同，两份代码很难犯完全相同的错误。** 如果两份独立的代码产出了相同的样本结果（LIMIT 1000），说明两份代码在样本集上逻辑一致——CONSISTENT_SAMPLE。但这不构成全量数据一致、业务正确或生产就绪的证明。如果结果不一致，说明至少一份代码有逻辑错误——人在审查时必须确定哪份是对的，或者两份都错。

如果 Spark 环境在自动验证时不可用：
- Spark DSL 代码仍然生成和审查
- 交叉验证标记为 NOT_EXECUTED（双引擎未执行）——无法提供双引擎背书
- 人在上线前在 Spark 环境中手动验证

### 6.3 三道防线之间的关系

- **防线 1 失效时（幻觉进入代码）**：防线 2 的表存在性检查会拦截编造的表名和字段名。交叉验证（检查项 #7）还能发现两份代码之间的逻辑不一致。但如果 LLM 在 SQL 和 Spark DSL 中犯了相同的幻觉（如都编造了同一个不存在的表），防线 2 检查项 #1 会拦截——两份代码都引用不存在的表，都会失败。
- **防线 2 失效时（检查有漏洞）**：防线 3 的人审是最终保障。自动化检查不可能覆盖所有错误类型，人的判断力弥补了这一点。交叉验证报告让人的审查更高效——差异点是人审的重点关注区。
- **防线 3 失效时（人审不充分）**：三道防线设计承认人的审查也可能不完美，但这是所有代码审查都面临的问题。来源追溯机制降低了人审的难度和出错概率。交叉验证通过（CONSISTENT）时，两份代码在样本集上逻辑一致——人审的重点是业务合理性、全量数据行为和方案选择，而非逐行 debug。注意：三道防线用于降低风险，不构成上线充分条件。

### 6.4 生产环境隔离

Agent 在开发环境运行，生产环境对 Agent 完全不可见：

| 环境 | Agent 权限 | 用途 |
|------|-----------|------|
| 开发库 | 只读 + LIMIT 1000 | 自动验证（阶段 4） |
| Spark 开发环境 | 只读 | SQL/Spark 交叉验证（阶段 4） |
| 生产库 | **无权限** | 由人部署后执行 |
| Spark 生产集群 | **无权限** | 由人部署后执行 |

## 7. 开发规范

### 7.1 代码规范
- 所有代码注释使用中文
- 注释解释"为什么"而非"是什么"
- 函数使用简短中文 docstring
- Agent 生成的代码必须包含来源引用注释

### 7.2 来源引用格式（强制）

```python
# 来源：gold_database_design.md §3.2 dws_daily_trip_summary 表定义
TRIP_SUMMARY_TABLE = "gold.dws_daily_trip_summary"

# 来源：meta.metric_definitions — trip_count 指标的 G3 物理列
TRIP_COUNT_COL = "trip_count"
```

### 7.3 目录约定

当前结构（过渡期）：

```
scripts/pipeline/     # v1.x 确定性管道保留为验证底座，不是 v2 主工作流
src/agent/            # v2.0 代码生成编排（目标位置；当前不接真实 LLM API）
src/verify/           # Validator 和交叉验证
src/sandbox/          # 开发环境只读 SQL/Spark 执行器
generated/            # Agent 产出物（Review Package、代码、报告、测试结果）
fixtures/             # 手工编写的测试数据
evals/                # 评测用例和基线
contracts/            # 数据契约定义
tests/                # 项目自身测试
```

目标结构（v2.0 落地后）：

```
src/
├── ir/               # 数据契约（IR 数据类——SQLPlan, ColumnBinding, PipelinePlan）
├── verify/           # 防线 2 规则引擎（安全黑名单、表存在性、JOIN 白名单、交叉验证）
├── compile/          # SQL 模板编译器（fallback——LLM 不可用时的降级路径）
├── agent/            # LLM 编排层（需求分析、方案设计、双份代码生成、材料输出）
├── sandbox/          # Dev 环境只读执行器（SQL + Spark DSL 双执行通道）
└── eval/             # 自测框架（结果评估、质量检查）
```

### 7.4 与 TianShu 的关系
- Agent 从 TianShu DuckDB 和数据库设计文档获取表结构、指标定义
- 开发库用于自动验证，生产库凭据不在 Agent 环境中
- 不得在本项目中复制 TianShu 的数据库设计文档
- TianShu 中不存在的数据，必须走 TianShu 变更流程（见父 AGENTS.md §13）

---

## 8. 禁止事项

### 8.1 禁止访问的表
- `bronze.*`（Bronze 原始摄入层）
- `silver.*`（Silver 中间清洗层）
- `*.raw_*`（原始数据表）
- 未经数据库设计文档注册的任何表

### 8.2 允许与禁止的 SQL 操作

**v2 业务草案执行链只允许**：`SELECT` 和 `WITH ... SELECT ...`（CTE 查询）。

> EXPLAIN / DESCRIBE / SHOW 虽为只读诊断语句，但不产生业务数据，已从业务执行链移除（2026-06-17 安全口径收窄）。未来可通过独立 diagnostic mode 使用。

**v1 Phase 2/DAG 编译器保留**：`compile_operation()` 可编译 CTAS/INSERT OVERWRITE/INSERT INTO/CREATE VIEW + 3 方言。`safety_tier=pipeline` 允许这些操作通过静态校验。但 `run_pipeline.py` 只调用 `compile_sql()`（SELECT），Layer 6 执行器为 `read_only=True`——**v1 可编译写操作，但当前不可执行**。

**禁止**：
- INSERT、UPDATE、DELETE、MERGE、REPLACE、TRUNCATE
- DROP、ALTER、RENAME
- GRANT、REVOKE
- ATTACH、DETACH
- DuckDB 扩展加载（`install` / `load`）

### 8.3 禁止绕过
- 禁止绕过自动验证直接输出审查材料
- 禁止绕过 Validator 直接执行任何 SQL 或 Spark DSL
- 禁止在 FAIL 状态下进入人审
- 禁止伪造或省略来源引用
- 禁止 Agent 自动批准、合并、部署或上线

---

## 9. 架构决策记录

### 决策 1：角色转变（2026-06-16）
- **决策**：Data Dev Agent v2.0 定位为 AI 辅助数据开发工具。
- **原因**：数据开发上线决定必须由人负责；Agent 的价值在于生成代码、完成自测并降低人审成本。
- **影响**：LLM 可生成 SQL、Spark DSL、Python 测试和配置草案；所有草案必须经过自动验证和人审。

### 决策 2：三道防线（2026-06-16）
- **决策**：防线 1（生成时约束）→ 防线 2（自动验证）→ 防线 3（人审闸门）
- **原因**：单靠任一防线都不够。生成时约束减少幻觉，自动验证拦截低级错误，人审处理复杂判断。

### 决策 3：来源追溯（2026-06-16）
- **决策**：所有表/字段引用必须标注来源
- **原因**：这是降低人审成本的关键——没有来源追溯，审查者需自己查文档验证每个引用；有来源追溯，只需验证"来源是否正确"。同等审查时间，后者能发现更多问题

### 决策 4：双层边界（2026-06-16）
- **决策**：将 Agent 权限边界分为两层——代码生成边界（Code Generation Boundary）和数据执行边界（Data Execution Boundary）
- **原因**：LLM 生成代码和代码被执行是两个不同风险层面的操作。分开定义边界后，LLM 可以生成 SQL/Spark DSL 草案，但所有代码进入执行时必须过 Validator 和只读开发环境。
- **影响**：AGENTS.md §3 以两层边界作为最高权限模型。Validator 和自动验证是两层之间的唯一通道。

### 决策 5：SQL + Spark DSL 双份代码交叉验证（2026-06-16）
- **决策**：LLM 对同一需求独立生成 SQL（DuckDB）和 Spark DSL（PySpark）两份实现，分别执行后对比结果集
- **原因**：两份代码使用不同的表达方式、执行引擎和类型系统，很难犯完全相同的逻辑错误。样本结果一致（CONSISTENT_SAMPLE）意味着两份代码在样本集上逻辑一致——但注意这仅代表 LIMIT 1000 样本一致，不代表全量数据一致、业务正确或生产就绪。结果不一致 → 至少一份代码有错，人审时定位。这是一种"双重记账"式校验——不是检查代码写得对不对，而是检查两份独立代码是否算出了相同答案
- **影响**：阶段 3 代码生成采用双轨输出；防线 2 新增检查项 #7（交叉验证）；人审材料增加交叉验证报告。如果 Spark 环境暂时不可用，Spark DSL 仍生成和审查，交叉验证标记为 NOT_EXECUTED（无法提供双引擎背书）

---

## 10. 当前实现状态（Implementation Status）

> 本节对齐代码真实状态，2026-06-17 更新。详情见 README.md "当前实现状态"。

### 10.1 v1 / v2 边界

```
scripts/pipeline/run_pipeline.py   ← v1 LEGACY：8 层确定性数据生产管道
                                       保留为验证底座 + fallback 编译器
                                       不是 v2 主工作流入口

src/agent/workflow.py              ← v2 主工作流：M2 Review Package 生成
src/agent/verification_engine.py   ← v2 主工作流：M3 验证引擎
scripts/dev_agent/                 ← v2 CLI 入口
```

**规则**：v1 pipeline 保留、不删除、不重构。v2 workflow 是当前开发主线。

> **v1 写操作编译器说明**：v1 Phase 2/DAG 保留 `compile_operation()`（CTAS/INSERT/VIEW）的编译能力和 `validate_pipeline()` 的静态校验能力，`safety_tier=pipeline` 允许写操作通过编译和静态校验。但 `run_pipeline.py` 只调用 `compile_sql()`（SELECT），Layer 6 执行器使用 `read_only=True`——**当前项目没有可写执行入口**。`safety_tier=pipeline` 不是运行时写权限开关。（详见 PROJECT_STATUS.md v1/v2 能力矩阵）

### 10.2 已完成（DONE）

| 模块 | 状态 | 说明 |
|------|------|------|
| M2 Review Package 生成 | ✅ | `build_review_package()` → 9 文件审查材料包 |
| M2 双份代码草案 | ✅ | `dual_code_generator.py` 确定性生成 SQL + Spark DSL |
| M2 审查材料包结构 | ✅ | `generated/review_packages/{request_id}/` 完整目录 |
| M3 静态检查 | ✅ | `Validator.validate_static()` 5 项检查 |
| M3 安全关键字黑名单 | ✅ | 19 个关键字，统一来源 `checks.FORBIDDEN_KEYWORDS` |
| M3 表/字段存在性 | ✅ | DuckDB DESCRIBE 验证 |
| M3 表访问权限 | ✅ | bronze/silver 禁止 + 可用表白名单 |
| M3 JOIN 白名单合规 | ✅ | IR 路径 A + SQL 文本路径 B 双路径 |
| M3 SQL 样本执行 | ✅ | `sandbox/executor.py`，只读 + LIMIT 1000 + 超时保护 |
| M3 安全压实（3 缺口） | ✅ | G1/G2/G3 修复 |
| **M4a 人审状态机最小实现** | ✅ | DecisionStatus enum + decision.yml + decision_log.yml + verification_summary.yml |
| **M4b 状态机完整实现** | ✅ | SUPERSEDED 自动转换 + artifact_hashes + decision_manager + 人审 CLI |
| **M4c 跨 package 注册表** | ✅ | package_registry + list/deps/status + SUPERSEDED 传播 + 一致性检查 |
| **M5a 查询内核与写入外壳分离** | ✅ | 双内核 Manifest、确定性部署外壳、双审批快照、篡改失效 |
| v1 pipeline 保留 | ✅ | `scripts/pipeline/` 完整保留，143 测试通过 |
| 测试 | ✅ | 629 passed，零回归 |

### 10.3 部分完成（PARTIAL）

| 模块 | 状态 | 说明 |
|------|------|------|
| Spark 只读样本执行 | ⚠️ | `sandbox/spark_executor.py` 是桩，始终返回 SKIPPED/PENDING |
| SQL/Spark 交叉验证 | ⚠️ | `verify/cross_validation.py` 逻辑完整，但输入缺失→始终 SKIPPED |
| 跨 package SUPERSEDED 传播 | ✅ | M4c 已实现——注册表 + 自动传播 + 一致性检查 |

### 10.4 部分完成（PARTIAL）——新增

| 模块 | 状态 | 说明 |
|------|------|------|
| **M5b-0 设计与威胁模型** | ✅ | `docs/m5b_duckdb_sandbox_design.md`——一次性可写 DuckDB Sandbox 设计完成 |

### 10.5 待完成（TODO）

| 模块 | 状态 | 阻塞原因 |
|------|------|---------|
| **M5b-1 DuckDB CTAS Sandbox** | 🔵 设计完成，待实现 | 本阶段只设计，不实现 |
| 真实 SQL/Spark 交叉验证 | ❌ | 需 Spark 环境就绪 |
| LLM 接入代码生成 | ❌ | 项目边界：当前不接真实 LLM API |
| Prompt 回归系统 | ❌ | 需 LLM API |
| ColumnBindingTable 动态加载增强 | ❌ | 当前 fallback 可用 |
| 完整 DAG 端到端测试 | ❌ | 待规划 |
| KEY_MERGE 增量策略 | ❌ | 未来里程碑 |

### 10.5 关键约束（不得违反）

- LLM 产物即使未来接入，也只能是**不可信草案**，必须经过 Validator + sample run + 人审
- 所有 SQL/Spark 草案**必须经过 Validator、sample run、人审**才能上线
- **不能自动 APPROVE**——Agent 只能写入 PENDING_REVIEW 和 SUPERSEDED
- **不能把 PENDING/SKIPPED 写成 PASS**——未执行就是未执行
- **不能夸大当前能力**——Spark 未完整验证
- **v1 pipeline 不删除、不重构**——保留为确定性验证底座
- **Agent 能在 src/agent 中触发 SUPERSEDED，但不能触发 APPROVED/REQUEST_CHANGES/REJECTED**
