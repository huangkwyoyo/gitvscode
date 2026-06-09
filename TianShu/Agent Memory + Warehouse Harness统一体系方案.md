# Agent Memory + Warehouse Harness 统一体系方案

## 1. 文档目的

本文档用于说明 TianShu 项目为什么需要构建一个统一的 **Agent Memory + Warehouse Harness** 体系。

它不是单纯的“记忆文档”，也不是单纯的“测试脚本集合”，而是一个把 **规则、文档、复盘、测试、审核、一致性检查、Agent 协作规范** 连接起来的项目治理机制。

本项目当前已经进入以下阶段：

- 数据源已经覆盖纽约市城市交通多域数据。
- Bronze 层已完成入库（16 张表，约 1.5 亿行）。
- Silver 层 11 张表已全部建成并完成修复（~9,738 万行，字段数 211，meta 注释全覆盖）。
- Harness 质量门禁体系已完成 6 个检查脚本 + 3 个测试模块 + Git pre-commit hook。
- 已出现多 Agent 协作（Codex、Claude Code），并已验证 AGENTS.md 路由机制和 Memory Gate。
- 已通过 Silver 层实战验证：字段漂移、TRY_CAST 静默失败、阶段感知缺失均已被门禁拦截。
- 下一阶段：Gold 层星型模型设计与建设。

因此，项目已经不能只依赖一次对话上下文、单个 Agent 的临时记忆，或者人工口头提醒来保证质量。

本项目需要一个能持续沉淀经验、固化规则、自动检查、防止重复犯错的统一体系。

### 1.1 关键概念说明

在深入阅读之前，先明确本文中反复出现的几个核心概念：

**Agent（AI 编程助手）**：本文中的"Agent"指 AI 编程助手（如 Claude Code、Codex），它们通过读取项目文件、理解自然语言指令来生成代码、SQL、文档和设计方案。Agent 不是独立运行的自动程序——它由人类在对话中调用，每次调用时会重新读取项目中的规则文件来约束自己的行为。Agent 的核心限制是：它不会"记住"上一次对话的内容，除非信息被写入项目文件。**另一个关键限制：Agent 启动时只自动加载根目录的 AGENTS.md（和 CLAUDE.md），项目中其他所有文档都不会被自动读取——必须由 AGENTS.md 中的路由指令或人类显式要求才会被 Agent 打开。**

**上下文（Context）**：AI Agent 的"上下文"类似于它的短期记忆——每次对话中，它能"看到"当前会话的所有对话内容以及被加载的项目文件。上下文有长度上限，当项目经历几十轮对话后，早期的关键设计决策和踩坑经验可能不在当前上下文中，Agent 就等同于"忘记"了它们。

**AI 幻觉（Hallucination）**：Agent 在生成设计方案时，会基于训练数据中的"常识"进行推断——例如它"知道"停车罚单通常包含罚款金额，所以会自然地假设这个字段存在，即使实际的原始数据表中并没有。这种"看似合理但无事实依据"的生成行为被称为幻觉。数据仓库项目中，幻觉往往不是荒谬的，而是"看起来合理"的，这正是它危险的地方。

**Harness（约束执行系统）**：这个名称借用了软件工程中的 Test Harness 概念——将多个检查、测试和规则集成到一个统一的执行框架中，就像电路测试中的测试夹具将多个探针组织在一起。在本文中，Harness 指一整套规则执行和自动检查机制，其目标不是"记录错误"而是"阻止同类错误再次进入项目"。

**TRY_CAST / try_strptime / regexp_replace**：DuckDB SQL 函数。`TRY_CAST(col AS TYPE)` 尝试将列转换为目标类型，转换失败时返回 NULL（不报错）——这正是它危险的地方：错误被静默吞掉。`try_strptime(col, format)` 按指定格式解析日期字符串。`regexp_replace(col, pattern, replacement, 'g')` 用正则表达式替换字符串内容。这三个函数是数据仓库中最常见的转换工具，也是最常见的静默错误来源。

---

## 2. 起点问题：为什么普通上下文不够

### 2.1 对话上下文天然会变长

在数据仓库项目中，一个任务很少是一次性完成的。

以本项目为例，前期已经经历了：

- 数据源扫描
- 数据域划分
- Bronze 入库
- DuckDB schema 建设
- 元数据目录生成
- Bronze 缺失率和主键校验
- Silver 层规划
- Silver 数据字典生成
- Agent 基座可行性分析
- 数据完整性分析
- 建模教学文档生成
- 多 Agent 规划互相审查

每一步都会产生新的事实、新的规则、新的问题和新的决策。

如果这些内容只留在对话上下文里，会出现几个问题：

1. 上下文越来越长，Agent 会抓不住重点。
2. 后续 Agent 不一定能读到完整历史。
3. 人类用户需要不断重复说明项目背景。
4. 同一个错误可能反复出现。
5. 文档、脚本、数据库之间容易不一致。

因此，对话上下文不能作为长期项目记忆。

### 2.2 Agent 的“记住”不是工程意义上的记忆

Agent 在一次对话中可以记住前文，但这种记忆不是项目资产。

它有几个限制：

- 不能天然跨工具、跨 Agent、跨会话稳定复用。
- 不能自动转化为测试。
- 不能自动阻止错误。
- 不能被 PR 审核。
- 不能被数据库设计文档引用。
- 不能作为团队协作的事实源。

所以，真正有价值的记忆，必须落地到项目中，成为：

- 文档
- 规则
- 检查脚本
- 测试用例
- 审核流程
- 数据库设计事实源

这就是从“上下文记忆”走向“项目记忆系统”的第一步。

---

## 3. 第一次认知升级：从上下文记忆到项目记忆系统

### 3.1 最初的想法

最初的问题是：

> 项目构建过程中不断审核优化，上下文拉得太长，是否应该在项目起始阶段就构建记忆系统？

这个问题的本质不是“要不要写几个记忆文件”，而是：

> 如何让项目经验不依赖某一次对话，而成为项目长期可复用的资产？

因此，第一层认知是：

```text
对话上下文不是长期记忆。
长期记忆必须沉淀到项目文件系统。
```

### 3.2 Codex 提出的三层记忆

Codex 给出的三层建议是：

```text
第一层：AGENTS.md
内容：Agent 能做什么、不能做什么
作用：约束 Agent 行为，防止重复犯错

第二层：项目 README
内容：项目是什么、当前阶段、关键决策
作用：让 Agent 一进来就知道上下文

第三层：知识库文档
内容：设计决策、踩坑复盘、方法论沉淀
作用：人类积累，跨项目复用

> **AGENTS.md 是如何被读取的？** Agent 在每次对话启动时，会自动扫描项目中的 `AGENTS.md` 文件并加载到当前上下文中。这不是魔法——它是 Agent 平台的默认行为（类似浏览器会自动加载网页的 `robots.txt`）。因此，只要规则写在正确位置的 `AGENTS.md` 中，Agent 就会"看到"它。但这也意味着：如果规则写在其他文件名下，Agent 不会主动发现。

详情如下：
第一层：AGENTS.md（约束层）
     
  ▎ 内容：Agent 能做什么、不能做什么 | 作用：约束 Agent 行为，防止重复犯错
     
  ┌─────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────┐
  │                  文件                   │                                  职责                                   │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
  │ TianShu/AGENTS.md                       │ 全局规则入口——最高原则、零幻觉建模、Human Review 触发条件、分层规则索引 │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
  │ TianShu/docs/warehouse/AGENTS.md        │ 数据仓库建模总规则                                                      │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
  │ TianShu/docs/warehouse/bronze/AGENTS.md │ Bronze 原始层规则（保留原始，不做业务改造）                             │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
  │ TianShu/docs/warehouse/silver/AGENTS.md │ Silver 标准层规则（只能标准化，禁止编造字段/聚合）                      │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
  │ TianShu/docs/warehouse/gold/AGENTS.md   │ Gold 主题层规则（基于 Silver 建模，禁止跳过 Silver）                    │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
  │ TianShu/agents/text2sql/AGENTS.md       │ Text2SQL Agent 规则（优先用 Gold，无法确认必须反问）                    │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
  │ TianShu/agents/review/AGENTS.md         │ 审核 Agent 规则（守门人，只拦截不圆场）                                 │
  └─────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────────┘

  共 7 个 AGENTS.md，形成从全局到分层的规则树。

  ---
  第二层：项目 README（上下文层）

  ▎ 内容：项目是什么、当前阶段、关键决策 | 作用：让 Agent 一进来就知道上下文

  ┌─────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────
│                          文件                            │                                 职责                                  ├─────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────
│ TianShu/PROJECT_STATUS.md                               │ 核心入口——当前阶段、最近完成、下一步、阻塞点、事实源位置、数据库位置            │
├─────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────
│ TianShu/docs/README.md                                  │ 文档目录导航                                                        
├─────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────
│ TianShu/docs/decisions/README.md                        │ 架构决策索引（6 份 ADR 列表）                                          │
├─────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────
│ TianShu/Agent Memory + Warehouse Harness统一体系方案.md   │ 项目治理体系总述（为什么需要这套体系）                                    │
└─────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────

  Agent 进来先读 PROJECT_STATUS.md 知道"做到哪了"，再读 decisions/ 知道"为什么这么做"。

  ---
  第三层：知识库文档（沉淀层）

  ▎ 内容：设计决策、踩坑复盘、方法论沉淀 | 作用：人类积累，跨项目复用

  ┌─────────────────────────────────────────┬─────────────────────────────────────────────────────────────────┐
  │                文件/目录                  │                              职责                               │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ TianShu/docs/memory/经验复盘.md           │ 踩过的坑 + 怎么修 + 沉淀了什么规则                              │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ TianShu/docs/memory/风险清单.md           │ 已知风险项                                                      │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ TianShu/docs/memory/规则来源索引.md       │ 每条规则从哪条经验来，有没有对应检查脚本                        │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ TianShu/docs/memory/变更复盘模板.md       │ 标准化复盘格式                                                  │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ TianShu/docs/decisions/001~006-*.md     │ 6 份架构决策记录（为什么选 DuckDB、为什么三层、为什么分三批……） │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ TianShu/docs/silver/Silver白银层规划.md   │ Silver 层 11 张表的完整设计方案                                 │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ TianShu/docs/warehouse/database_design/ │ 数据库设计文档（最高事实源）                                    │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ TianShu/docs/warehouse/data_dictionary/ │ 字段字典                                                        │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ TianShu/docs/modeling/                  │ ER 模型、星型模型、维度建模方法论                               │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ TianShu/docs/standards/                 │ 规范索引入口，指向 database_design、data_dictionary 等事实源       │
  ├─────────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ TianShu/docs/meta/                      │ 元数据设计、中文语义层设计说明                                  │
  └─────────────────────────────────────────┴─────────────────────────────────────────────────────────────────┘

  ---
  三层关系一览

  第一层 AGENTS.md       →  Agent 进来先读规则，知道"不能做什么"
  第二层 项目 README      →  读完规则看状态，知道"做到哪了、为什么这么做"
  第三层 知识库文档        →  深入细节，看设计、看复盘、看方法论

  三层从"约束→上下文→沉淀"，粒度从粗到细，Agent 按顺序读就能理解项目全貌。
```

这个方案是正确的，但还不够。

它解决了”记忆放在哪里”的问题，但没有解决两个更关键的问题：

**第一，”记忆如何被触发”的问题。** 三层记忆是存储分层，不是触发分层。Agent 不会因为一份文档放在”第三层”就自动找到并读取它。实际上，Agent 启动时只自动加载根目录的 `AGENTS.md`——项目中的其他任何文档（`docs/memory/`、`docs/decisions/`、`docs/warehouse/` 等）都不会被自动读取。它们只有在 AGENTS.md 明确写了”做 X 前必须先读 Y”时，才可能被 Agent 主动打开。如果 AGENTS.md 只是列出文件名（”这是经验复盘”），Agent 大概率不会去读。

**第二，”记忆如何执行”的问题。** 即使 Agent 读到了文档，也不能保证它会遵守。

如果只是写文档，仍然可能出现：

- Agent 没读到。
- Agent 读到了但忘了执行。
- 人类忘记提醒。
- 规则没有测试保护。
- 错误仍然可以进入 SQL、Excel、Markdown 和数据库。

所以，这个阶段的结论是：

```text
记忆系统必须有，但单纯记忆系统不够。
```

---

## 4. 第二次认知升级：从记忆系统到 Harness

### 4.1 为什么需要 Harness

在 Silver 层规划审查时，项目暴露出一个典型问题：

`parking_violation_detail` 规划了以下金额字段：

- `fine_amount`
- `penalty_amount`
- `interest_amount`
- `reduction_amount`
- `payment_amount`
- `amount_due`

但是实际 Bronze 表 `parking_violations_all` 并没有这些字段。

这说明 AI 在规划时发生了典型风险：

```text
根据业务直觉补齐字段。
```

从业务上看，停车罚单似乎应该有罚款金额、支付金额、欠款金额。

但从数据仓库工程上看，只要 Bronze 原始数据里没有，数据库设计文档也没有确认，这些字段就不能进入 Silver 作为正式来源字段。

这类问题如果只写进经验复盘，下一次仍然可能出现。

为什么写了文档还不够？因为 Agent 的"阅读"和人的阅读有本质区别：

- **人读文档**：会联想，会举一反三。读到"停车罚单没有金额字段"这条经验，人在下次设计其他表时会主动检查字段是否存在。
- **Agent 读文档**：只匹配当前任务。如果当前任务是设计 `crash_detail` 而非 `parking_violation_detail`，Agent 可能不会主动联想到"无来源字段"这条通用规则也适用于事故表。Agent 倾向于把经验当作"那个具体场景的故事"而非"可迁移的通用约束"。

因此，经验必须被显式转化为可执行检查——不是"提醒 Agent 注意"，而是"当条件 X 满足时，检查必须失败"。只有机器检查才能做到每一次都执行，不受上下文长度、任务关联性和 Agent 会话状态的影响。

因此，需要一个 Harness，把经验变成自动检查。

### 4.2 Harness 的含义

这里的 Harness 不是单个测试脚本，而是一整套约束执行系统。

它包括：

- 规则入口
- 数据库设计文档
- 字段字典
- 质量检查脚本
- 自动测试
- 复盘文档
- 审核 Agent 规则
- Text2SQL Agent 规则
- schema 一致性检查

它的目标不是“记录错误”，而是“阻止同类错误再次进入项目”。

### 4.3 Harness 的核心闭环

Harness 的核心闭环是：

```text
发现问题
  ↓
写入经验复盘
  ↓
抽象为项目规则
  ↓
更新数据库设计文档或字段字典
  ↓
新增质量检查脚本
  ↓
新增测试用例
  ↓
以后每次变更自动检查
  ↓
同类错误直接拦截
```

这比普通记忆系统多了两个关键环节：

1. 经验必须变成规则。
2. 规则必须变成可执行检查。

---

## 5. 第三次认知升级：记忆系统和 Harness 不是两个系统

### 5.1 原始疑问

在讨论中进一步提出了一个关键问题：

> 记忆系统的 Harness 不能和 Data Warehouse Agent Harness 结合起来吗？要分开吗？

这个问题非常重要。

如果把“记忆系统”和“Data Warehouse Agent Harness”分开，会导致两个系统各自孤立：

- 记忆系统写了很多经验，但没有执行能力。
- Harness 跑了很多测试，但不知道规则从何而来。
- 规则来源不透明，后续难以维护。
- 人类无法知道某条测试背后曾经踩过什么坑。

因此，二者不应该分开。

### 5.2 正确关系

正确关系是：

```text
记忆系统 = 经验沉淀层
Data Warehouse Agent Harness = 规则执行与自动拦截层
```

二者是上下游关系，不是并列关系。

更准确地说：

```text
Agent Memory 负责积累经验。
Warehouse Harness 负责执行规则。
```

统一后的体系可以叫：

```text
TianShu Agent Memory + Warehouse Harness
```

或者简称：

```text
TianShu Agent Harness
```

### 5.3 统一体系的工作方式

统一体系的完整链路是：

```text
一次错误或经验
  ↓
docs/memory 记录
  ↓
docs/warehouse 形成正式规则
  ↓
docs/warehouse/database_design 更新事实源
  ↓
docs/warehouse/data_dictionary 更新字段字典
  ↓
scripts/quality 形成检查脚本
  ↓
tests 固化为回归测试
  ↓
agents/review 在审核阶段执行
  ↓
agents/text2sql 在问数阶段遵守
```

这个链路的价值在于：

- 经验有来源。
- 规则有出处。
- 检查有依据。
- 测试能复用。
- Agent 能理解边界。
- 人类能审核变更。

---

## 6. 第四次认知提升：从设计文档到架构决策记录

### 6.1 审查发现的结构性缺失

在对 TianShu 项目文档体系进行完整审查后，发现一个关键缺失：

项目当前有：

- `docs/silver/Silver白银层规划.md` — 回答 **"怎么做"**
- `docs/warehouse/` — 回答 **"规则是什么"**
- `docs/memory/` — 回答 **"踩过什么坑"**
- `AGENTS.md` — 回答 **"Agent 不能做什么"**

但缺少一个关键层：

```text
缺少"为什么这么做"的架构决策记录。
```

### 6.2 当前关键决策的散落状态

项目已经积累了大量关键架构决策，但它们没有统一存放位置：

| 关键决策 | 当前所在位置 | 问题 |
|---|---|---|
| 为什么选 DuckDB 作为数仓引擎？ | 无正式记录 | 完全缺失 |
| 为什么 Bronze→Silver→Gold 三层分层？ | `AGENTS.md` | 只写了规则，未写决策理由 |
| Silver 为什么分三批建设？优先级依据？ | `docs/silver/Silver白银层规划.md` | 隐含在设计文档中 |
| 主键策略为什么不同？（代理键/复合键/MD5哈希） | `PROJECT_STATUS.md` 的"重要注意" | 散落在状态文件中 |
| 罚单金额为什么放 Gold 不放 Silver？ | `AGENTS.md` + 规划文档 | 决策逻辑分散，未独立说明 |
| Agent Memory + Warehouse Harness 体系为什么这样设计？ | 本文档 | 仅本文档自身在说明 |
| 为什么 trip_id 从 ROW_NUMBER 改为 MD5 哈希？ | `PROJECT_STATUS.md` | 作为修复记录存在 |
| 为什么 driver_application 枚举不能硬编码？ | `PROJECT_STATUS.md` + `docs/memory/` | 分布在复盘和经验中 |

这些决策如果只在设计文档中隐含、在状态文件中零散记录、或在对话上下文中口头说明，后续维护者（包括未来的自己）将无法理解"当时为什么这样设计"。

更严重的是，当某个决策需要重新评估时——例如"DuckDB 是否还适合当前数据规模"——如果没有原始决策记录，就无法知道当初选择 DuckDB 时考虑了哪些因素、排除了哪些替代方案、假定了什么前提条件。没有这些信息，重新评估就变成了重新猜测。

### 6.3 ADR：软件工程的成熟实践

ADR（Architecture Decision Records，架构决策记录）是软件工程中记录关键架构决策的成熟实践，最早由 Michael Nygard 在 2011 年提出，现已成为 ThoughtWorks 技术雷达的"采纳"级实践。

其核心思想极为简单：

```text
每一个重要的架构决策，都应该被独立记录：
- 我们决定了什么？（Title）
- 为什么这样决定？（Context + Decision）
- 考虑了哪些替代方案？（Alternatives）
- 带来了什么后果？（Consequences）
```

数据仓库项目同样需要 ADR，甚至更需要——

因为数据仓库的决策链条更长：数据源选择 → 分层策略 → 主键策略 → 字段派生规则 → 指标口径 → 聚合粒度。每一步的选择都会影响下游所有层，且数据 warehouse 的生命周期通常以年为单位，远长于普通应用软件。

### 6.4 TianShu 所需的 decisions/ 结构

建议新增 `docs/decisions/` 目录，存放架构决策记录：

```text
docs/decisions/
├── README.md                              # 决策索引 + ADR 模板
├── 001-duckdb-as-warehouse-engine.md       # 为什么选 DuckDB 作为数仓引擎
├── 002-bronze-silver-gold-layering.md      # 三层分层架构决策
├── 003-silver-three-batch-strategy.md      # Silver 分三批建设的优先级决策
├── 004-primary-key-strategy.md             # 主键策略：代理键/复合键/MD5哈希的选择依据
├── 005-agent-memory-harness-system.md      # Agent Memory + Warehouse Harness 统一体系决策
└── 006-parking-violation-amount-in-gold.md  # 罚单金额放在 Gold 层而非 Silver 层的决策
```

每份 ADR 建议包含以下结构：

```text
# 标题（以决策编号开头）

## Status（状态）
 Proposed / Accepted / Deprecated / Superseded

## Context（背景）
 当时面临什么问题？有什么约束？

## Decision（决策）
 我们决定怎么做？

## Alternatives（替代方案）
 考虑过哪些其他方案？为什么没选？

## Consequences（后果）
 这个决定带来了什么正面和负面影响？
```

### 6.5 decisions/ 与现有文档体系的关系

`decisions/` 不替代任何现有文档，而是补充缺失的"为什么"这一环：

| 目录 | 职责 | 回答的问题 |
|---|---|---|
| `docs/decisions/` | 架构决策记录 | **为什么**这么做？ |
| `docs/standards/` | 规范与约定 | **按什么标准**做？ |
| `docs/modeling/` | 建模方法论 | **用什么方法**建模？ |
| `docs/silver/` | 分层规划与设计 | Silver 层**怎么做**？ |
| `docs/warehouse/` | 规则 + 数据库设计 + 字典 | 具体**规则和 schema**是什么？ |
| `docs/memory/` | 经验复盘 + 风险清单 | **学到了什么**教训？ |
| `docs/meta/` | 元数据与语义层设计 | 元数据**如何设计**？ |

### 6.6 决策记录与经验复盘的区别

一个常见的疑问是：决策记录和经验复盘都是"回头看"，它们有什么区别？

```text
经验复盘（docs/memory）：
  记录"我们踩了一个坑"。
  关注点：错误是什么 → 怎么修复 → 沉淀了什么规则。
  时间方向：从现在回头看过去的问题。

决策记录（docs/decisions）：
  记录"我们做了一个选择"。
  关注点：为什么选 A 不选 B → 考虑了哪些因素 → 什么条件下需要重新评估。
  时间方向：从决策当时看未来，为将来的重新评估保留上下文。
```

举例来说：

```text
经验复盘写：
  "trip_id 用了 ROW_NUMBER() OVER ()，重跑后 ID 不稳定，已改为 MD5 哈希。"

决策记录写：
  "我们决定用 MD5 哈希作为 Silver 层代理主键的生成方式。
   替代方案包括 ROW_NUMBER（已排除，因为无序）、UUID（已排除，因为 DuckDB 不支持）、
   自增序列（已排除，因为跨表合并时冲突）。
   后果：主键确定性稳定，但存储空间略大，且无法由主键推断插入顺序。"
```

两者互补，而非替代。

### 6.7 本次认知的核心

```text
设计文档回答"怎么做"。
规则文档回答"不能做什么"。
记忆文档回答"踩过什么坑"。
决策记录回答"为什么这么做"。

四者构成完整闭环。
```

加上 `decisions/` 后，TianShu 的文档体系才真正完整——从决策理由到设计执行，从规则约束到经验沉淀，每一层都有明确归属，不再依赖对话上下文或口头传承。任何未来的维护者（包括一年后的自己）都能从 `decisions/` 快速理解项目的关键设计意图。

---

## 7. 第五次认知提升：从散落脚本到 Harness 工程入口

在前面的设计中，Harness 的能力已经存在：

- `scripts/quality/` 有检查脚本。
- `tests/` 有回归测试。
- `docs/memory/` 有经验复盘。
- `docs/warehouse/database_design/` 有数据库设计事实源。
- `docs/warehouse/data_dictionary/` 有字段字典和枚举值说明。

但继续审查后发现一个新问题：

```text
Harness 的能力存在，但 Harness 自己没有工程入口。
```

如果没有独立入口，后续 Agent 需要在多个目录之间猜：

- 检查命令在哪里？
- 检查前置条件是什么？
- PR 前应该看哪份清单？
- Schema 变更应该走什么审核步骤？
- 检查报告应该放哪里？
- Harness 的配置目标在哪里？

这会让 Harness 本身变成“散落的脚本和规则”，降低可维护性。

因此，项目需要新增一个 `harness/` 目录，作为 Harness 的工程执行入口。

但这一步必须明确边界：

```text
harness/ 是执行入口，不是第二事实源。
```

它不能复制数据库设计文档，不能复制字段字典，不能复制经验复盘。它只能引用这些事实源，并组织如何执行检查。

新的职责划分是：

| 目录 | 职责 |
|---|---|
| `docs/warehouse/database_design/` | 表结构、字段、主键、类型的最高事实源 |
| `docs/warehouse/data_dictionary/` | 字段字典、枚举值（状态码/标志位/分类代码）中文含义 |
| `docs/memory/` | 经验复盘、风险清单、规则来源 |
| `docs/standards/` | 规范索引入口，不重复维护具体规范 |
| `scripts/quality/` | 具体质量检查脚本 |
| `tests/` | 回归测试 |
| `harness/` | Harness 运行说明、检查清单、配置和报告入口 |

这次认知提升的核心是：

```text
docs/ 负责事实、规则、记忆和方法论。
scripts/quality/ 负责具体检查实现。
tests/ 负责回归保护。
harness/ 负责把这些能力组织成可执行工程流程。
```

这样设计后，Agent 进入项目时可以先读：

1. `AGENTS.md`：知道不能做什么。
2. `PROJECT_STATUS.md`：知道项目做到哪里。
3. `harness/README.md`：知道如何运行检查和走审核流程。
4. `docs/warehouse/database_design/`：确认正式 schema。
5. `docs/warehouse/data_dictionary/`：确认字段和枚举值含义。

这比把所有说明继续堆在 `docs/` 或 `scripts/quality/` 更清晰。

### 7.1 Harness 不是复制目录，而是编排边界

进一步思考后，还需要防止另一个误区：

```text
每新增一种治理能力，就再建一个 harness_xx 文件夹。
```

这种做法表面上看像是“模块化”，但如果没有清晰边界，很容易变成新的混乱来源。

例如：

```text
harness/
harness_silver/
harness_gold/
harness_text2sql/
harness_review/
harness_memory/
```

如果每个目录都各自维护入口、规则、配置、检查脚本、报告说明，问题会很快出现：

1. Agent 不知道应该先读哪个 Harness 入口。
2. 同一个检查规则可能被复制到多个目录。
3. 数据库设计和字段字典可能被某个 harness_xx 目录局部复制。
4. 同一条经验可能在 `docs/memory/` 和 `harness_memory/` 中重复维护。
5. PR 审核时难以判断哪个 Harness 是当前有效门禁。

因此，`harness/` 不应该被理解为“把所有能力搬进一个新目录”，也不应该被理解为“每类能力都新建一个 harness_xx”。

更合理的理解是：

```text
harness/ 是治理工程的控制面。
```

它负责组织和编排项目中已经存在的能力：

- 检查脚本仍然在 `scripts/quality/`。
- 回归测试仍然在 `tests/`。
- 经验复盘仍然在 `docs/memory/`。
- 数据库设计仍然在 `docs/warehouse/database_design/`。
- 字段字典和枚举说明仍然在 `docs/warehouse/data_dictionary/`。
- 分层规则仍然在 `docs/warehouse/*/AGENTS.md`。

`harness/` 只负责回答：

```text
这些能力如何组合起来执行？
什么时候执行？
执行前看什么清单？
执行失败如何判断是规则问题还是环境问题？
PR 前需要哪些证据？
```

所以，Harness 的能力不是集中在 `harness/` 一个目录里，也不是无序散落在项目各处，而是：

```text
能力分布在正确的职责目录中；
harness/ 负责把这些能力组织成流程。
```

这是一种“分布式能力 + 中央编排入口”的结构。

它和“只建索引”的区别在于：

| 方案 | 特点 | 风险 |
|---|---|---|
| 只建索引 | 只告诉人去哪里找文件 | 没有运行流程，Agent 仍需自己拼步骤 |
| 把能力全部搬进 harness/ | 入口统一 | 复制事实源，形成第二套规范 |
| 每类能力新建 harness_xx | 看似模块化 | 入口泛滥，规则重复，边界不清 |
| 单一 harness/ 编排入口 | 保持事实源归位，同时统一执行流程 | 需要维护清单和配置的一致性 |

因此，当前最合适的方案是：

```text
只保留一个顶层 harness/。
```

当未来需要扩展 Harness 能力时，应优先在 `harness/` 内部增加子目录或配置项，而不是在项目根目录新增多个并列的 `harness_xx/`。

例如：

```text
harness/checklists/text2sql_review.md
harness/checklists/gold_model_review.md
harness/config/harness_targets.yml
harness/reports/local/
```

如果某一类 Harness 能力发展到非常复杂，确实需要独立工程，也应该先满足三个条件：

1. 它有独立生命周期。
2. 它有独立依赖和运行环境。
3. 它不会复制数据库设计、字段字典和经验复盘。

否则，就继续留在统一 `harness/` 下，由 `harness/README.md` 作为唯一入口。

这次认知提升可以概括为：

```text
Harness 不是文件夹越多越强。
Harness 的强度来自边界清楚、事实源唯一、执行路径稳定。
```

---

## 8. 第六次认知提升：AGENTS.md 是唯一自动加载的文档

### 8.1 一个被忽略的前提

前五次认知升级构建了完整的体系——记忆存储、规则执行、Memory 与 Harness 统一、架构决策记录、Harness 工程入口。但这一切建立在一个未被审视的前提上：

```text
Agent 会读到我们写的文档。
```

这个前提对吗？只对了一小部分。

**Agent 启动时只自动加载根目录的 `AGENTS.md`（和 Claude Code 场景下的 `CLAUDE.md`）。** 项目中其他所有文档——`docs/memory/经验复盘.md`、`docs/decisions/001-*.md`、`docs/warehouse/silver/AGENTS.md`、`harness/checklists/`——都不会被自动读取。

Agent 要读到这些文档，只有三种途径：

| 途径 | 机制 | 可靠性 |
|---|---|---|
| AGENTS.md 路由指令 | AGENTS.md 中写了"做 X 前必须先读 Y"，Agent 执行 X 时主动去读 Y | 中等（取决于 Agent 是否遵循） |
| 人类显式要求 | 用户说"读一下经验复盘" | 高（但人必须记得） |
| Agent 自主探索 | Agent 用搜索工具发现文件后自行判断需要读取 | 低（Agent 不一定搜到，也不一定判断为相关） |

### 8.2 这意味着什么

TianShu 最需要被 Agent 读到的文档，恰恰是最不可靠被读到的：

- `docs/memory/经验复盘.md` —— AGENTS.md 只是"列出"了它，没有写"做 Silver 设计前必须先读"
- `docs/decisions/001~006-*.md` —— 同上
- `docs/memory/风险清单.md` —— 同上

当前的 AGENTS.md 是**索引式**的：

```text
"分层规则入口：docs/warehouse/AGENTS.md"
```

Agent 看到的是"这个文件存在"，而不是"我现在必须去读它"。Agent 天然倾向于跳过"仅供参考"的链接，直接开始工作。

### 8.3 AGENTS.md 必须从索引升级为路由表

修复方案不是新建更多文档，而是改变 AGENTS.md 的写法：

```text
索引式（当前）：   "分层规则入口：docs/warehouse/AGENTS.md"
路由式（修复后）： "做 Silver 字段设计前，必须先读取：
                  1. docs/warehouse/silver/AGENTS.md
                  2. docs/memory/风险清单.md
                  3. docs/memory/经验复盘.md（搜索'金额''字段来源'关键词）"
```

关键区别：**路由式不依赖 Agent 的判断。** 它说"做 X 之前必须读 Y"，而不是"Y 存在，你看着办"。

### 8.4 三层记忆模型被修正

第 3.2 节提出的三层记忆（AGENTS.md → 项目 README → 知识库文档）是**存储分层**，不是**触发分层**。Agent 不会因为一份文档在"第三层"就自动在需要的时候找到并读取它。

修正后的完整模型是：

```text
存储分层（三层记忆）→ 回答"文档放在哪里"
触发分层（AGENTS.md 路由表）→ 回答"Agent 什么时候读"  ← 本次补充
执行分层（Harness 检查脚本）→ 回答"读了也可能不遵守怎么办"
```

三者缺一不可。存储没有触发是死知识，触发没有执行是软约束。

### 8.5 本次认知的核心

```text
AGENTS.md 是 Agent 看到的第一个文件，也是唯一自动加载的文件。
它不能只做"索引入口"——列出有哪些文档。
它必须做"路由表"——在什么任务下必须读什么文档。

只列文件名而不写触发条件，
等于把文档藏在了 Agent 看不到的地方。
```

这也意味着：**Harness 的自动检查脚本是最后防线。** 无论 Agent 是否读了经验复盘，无论 AGENTS.md 的路由指令是否被遵循，`check_silver_dictionary.py` 都会在字段无来源时报错。路由表提升 Agent 主动避坑的概率，检查脚本保证即使路由失败也不会漏过去。

> **延伸阅读**：本文聚焦于治理体系的演进逻辑。关于 Agent 的底层运作机制——LLM 如何生成 SQL 和代码、五层校验链条如何叠加生效、Claude Code / Codex / OpenCode 的本质区别——详见 Obsidian 知识库 [[Agent与LLM交互的完整执行链路-从prompt到SQL与代码生成的运作机制]]。

---

## 9. 第七次认知提升：从设计验证到生产强化——Harness 闭环的实战完善

### 9.1 背景

第六次认知升级完成了 AGENTS.md 从索引到路由表的转变。当时 Harness 体系的四个自动化层次还处于"设计完成但未全面验证"的状态：

```text
AGENTS.md 定义规则       ← 已完成
  ↓
check_*.py 执行规则      ← 已完成（5 个检查脚本）
  ↓
run_all_checks.py 汇总   ← 已完成
  ↓
Git hook / CI 自动触发   ← 未完成
```

Silver 层 11 张表建成后（2026-06-09），经历了一轮完整的"问题暴露→根因分析→修复验证→门禁强化"循环。这个循环暴露了 Harness 体系在从设计阶段进入生产阶段时的三个关键缺口，并逐一修复。

### 9.2 缺口一：阶段感知缺失——Harness 不知道 Silver 已建成

**问题**：Silver 建表完成后，`check_schema_consistency.py` 仍然按"Silver 未建成"模式运行——检测到 Silver schema 为空就跳过实表对比，返回成功。结果是 xlsx 字段数（32/11/25/22）与 DuckDB 实表（30/12/26/23）的 4 张表漂移全部漏检。

**根因**：Harness 没有阶段概念。它不知道当前是"建表前"（应宽松）还是"建表后"（应严格）。

**修复**：
```yaml
# harness_targets.yml
project:
  stage: gold_g0_g1_build  # ← 阶段已推进到 Gold G0/G1 建成后
```

```python
# run_all_checks.py
if config.stage in ("post_silver_build", "pre_gold_build") or config.stage.startswith("gold"):
    schema_command.append("--require-silver-tables")  # ← 阶段感知自动追加
```

**认知**：Harness 必须是有状态的。同一套检查脚本，在不同项目阶段应有不同的严格程度。Silver 建成后要启用 Silver 实表强校验；Gold G0/G1 建成后，还要启用 Gold 设计门禁和 Gold 物理表门禁。阶段不是说明文字，而是 Harness 判断应该拦截什么问题的输入。

### 9.3 缺口二：空值检查没有基线——分不清信号和噪音

**问题**：Silver 建成后发现 18 个字段 NULL 率超过 50%。其中一些是真正的转换 bug（如 `total_dispatched_trips` 55% NULL 因为逗号），另一些是预期的业务稀疏（如 `passenger_count` 90% NULL 因为 FHV 行程无此字段）。没有基线时，二者混在一起无法区分。

**根因**：空值检查只报了"缺失率 > 50%"，但没有声明"哪些缺失是正常的"。检查脚本不知道业务上下文。

**修复**：建立三级空值分类体系：

```yaml
# silver_sparsity_baseline.yml —— 17 条预期稀疏基线
baselines:
  - field: "trip_detail.passenger_count"
    expected_null_rate: 0.90
    reason: "FHV 和 HVFHV 源表无此字段，仅 Yellow/Green 有"
```

```text
[!] 超出预期/全NULL    → 必须修复
[~] 预期稀疏（在容忍范围内） → 正常
[?] 无基线需人工判断    → 需补充基线
```

**结果**：17 个字段从"需关注"降级为"[~] 预期稀疏"，唯一真正的异常（`base_detail.total_dispatched_trips` 55%）被清晰标出并修复。

**认知**：质量检查不能只有"绝对值阈值"（NULL 率 > 50%），必须有"相对基线"（超出预期多少）。基线是业务知识和自动检查之间的桥梁。

### 9.4 缺口三：规则写了但没人执行——Memory Gate 补全第四层

**问题**：`AGENTS.md` §13 写明了变更传播规则——改 schema/字典/SQL/质量脚本后必须同步更新 `docs/memory`。但这条规则没有任何脚本检查，完全依赖人和 Agent 的记忆。Codex 修复 Silver 后没有自动写入经验复盘，证明了"规则声明 ≠ 自动执行"。

**根因**：前六次认知升级建立了规则声明层、检查脚本层、统一门禁层，但缺少关键的"Memory Gate"——检查"变更是否伴随经验沉淀"的专用脚本。同时第四层（Git hook 自动触发）也未建立。

**修复**：新增 `check_memory_update.py`，补全四层自动化：

```text
AGENTS.md 定义规则
  ↓
check_memory_update.py 执行规则  ← 本次新增
  ↓                          （扫描 git diff → 判断关键路径变更 → 检查 memory 是否同步更新）
run_all_checks.py 汇总门禁
  ↓
.git/hooks/pre-commit 自动触发   ← 本次新增（不依赖 DuckDB，DBeaver 占用时也能运行）
```

**认知**：四层自动化从设计到落地的最后一公里是 Git hook。没有 hook，门禁仍然依赖"人记得跑 `run_all_checks.py`"。有了 hook，每次 `git commit` 自动执行 Memory Gate + 危险模式 + pytest。

### 9.5 实战验证：TRY_CAST 静默失败的精确机制

本轮实战还揭示了 `TRY_CAST` 的一个精确陷阱——它不是"格式不对就返回 NULL"，而是对**三类不同格式**分别静默失败：

| 格式 | 示例 | 失败原因 | 修复 |
|---|---|---|---|
| 美国日期 | `'05/22/2026'` | `TRY_CAST AS DATE` 期望 ISO 格式 | `try_strptime(col, '%m/%d/%Y')` |
| 货币字符串 | `'$1,000.00'` | `TRY_CAST AS DECIMAL` 无法处理 `$` 和 `,` | `regexp_replace(col, '[$,]', '', 'g')` |
| 千位分隔整数 | `'3,316'` | `TRY_CAST AS BIGINT` 无法处理 `,` | `regexp_replace(col, ',', '', 'g')` |

Codex 修复了前两类，但遗漏了第三类（`base_detail.total_dispatched_trips`），导致 55% 数据静默丢失。这说明即使是"同类问题"，也需要逐表逐列的格式审查，不能假设修了一个就修了全部。

**经验编码为检查规则**：`check_silver_null.py` 现在默认启用，每次门禁自动扫描所有 Silver 表。任何全 NULL 的日期/金额/数值字段都会被立即发现，不再依赖人工逐列检查。

### 9.6 Harness 当前完整状态

```
第一层·规则声明    AGENTS.md（路由表）+ docs/warehouse/*/AGENTS.md + docs/standards/
                   ↓
第二层·检查脚本    check_silver_dictionary.py / check_dangerous_patterns.py /
                   check_schema_consistency.py / check_silver_null.py /
                   check_memory_update.py  ← 共 5 个
                   ↓
第三层·统一门禁    run_all_checks.py（阶段感知：post_silver_build 自动启用强校验）
                   ↓
第四层·自动触发    .githooks/pre-commit（Memory Gate + 危险模式 + pytest，不依赖 DuckDB）
                   ↓
第五层·CI/PR       待建立（GitHub Actions / PR required checks）
```

已落地的检查矩阵：

| 检查项 | 脚本 | 依赖 DuckDB | 已接入门禁 |
|---|---|---|---|
| Silver 字段来源合法性 | `check_silver_dictionary.py` | 否 | ✓ |
| 危险 SQL 模式 | `check_dangerous_patterns.py` | 否 | ✓ |
| schema 文档-实表一致性 | `check_schema_consistency.py` | 是 | ✓ |
| Silver 空值画像 | `check_silver_null.py` | 是 | ✓ |
| 经验沉淀强制执行 | `check_memory_update.py` | 否 | ✓ |
| 字典回归测试 | `test_silver_dictionary.py`（6 用例） | 否 | ✓ |
| Harness 自检 | `test_harness_quality.py`（5 用例） | 否 | ✓ |

### 9.7 本次认知的核心

```text
一套可工作的 Harness 不是"设计出来"的，而是"打出来"的。

前六次认知升级完成了架构设计。
第七次认知升级来自 Silver 上线后的真实问题暴露——
阶段感知缺失、空值基线缺失、Memory Gate 缺失、TRY_CAST 陷阱。

每一个真实问题都在 Harness 中留下了一道新的自动防线。
这些防线合在一起，才让 Harness 从"文档中的设计"变成了"每次提交都会运行的检查"。

Harness 的成熟度不是看有多少检查脚本，而是看有多少个"下一次同类问题被自动拦截"的实例。
```

> **延伸阅读**：本轮实战的完整技术细节和修复过程，详见 Obsidian 知识库 [[Silver层深度审查与优化_20260609]] 和 [[Silver层问题复盘-Harness为何通过但数据仍有问题_20260609]]。关于 AGENTS 规则与自动触发机制的理论分析，详见 [[AGENTS规则与自动触发机制的区别_20260609]]。

---

## 10. 本项目为什么尤其需要这个体系

### 9.1 数据域复杂

纽约市城市交通数据不是单一主题数据，而是多域数据。

当前已经覆盖：

- 出行域
- 资产域
- 安全域
- 供给域
- 监管/合规域
- 空间地理域

不同数据域之间有不同粒度、不同主键、不同时间字段、不同空间字段和不同数据质量问题。

例如：

- 出行数据以 trip 为核心。
- 事故数据以 collision_id 为核心。
- 事故人员数据与事故主表是一对多关系。
- 停车罚单以 summons_number 为核心。
- 车辆资产涉及 License Number、VIN、Plate 等多个候选关联字段。
- FHV 基地聚合数据不是基地主数据，而是按年月聚合的运营数据。

这种复杂度决定了项目必须有严格的数据库设计事实源。

### 9.2 AI 容易在数据仓库项目中产生”合理幻觉”

数据仓库项目里的 AI 幻觉往往不是荒谬的，而是“看起来合理”的。

典型例子：

- 停车罚单应该有罚款金额。
- 出行事实表应该有稳定 trip_id。
- 日期维表可以直接用日期转整数。
- 字段名相同就可以 Join。
- 车辆表和司机表应该能自然关联。

这些判断在业务直觉上可能合理，但在数据工程上必须有证据。

本项目明确要求：

```text
Agent 只能整理事实，不能创造事实。
```

因此，必须通过 Harness 把“零幻觉建模”变成可执行检查。

### 9.3 多 Agent 协作需要共同规则

本项目已经出现 Codex 和 Claude Code 协作。

后续还可能出现：

- 数据开发 Agent
- 数据分析 Agent
- Text2SQL Agent
- 审核 Agent
- 文档生成 Agent
- SQL 生成 Agent

如果没有统一规则，各 Agent 会按照自己的风格生成内容。

结果可能是：

- 字段命名风格不一致。
- 中文名不一致。
- 指标口径不一致。
- 文档结构不一致。
- 一个 Agent 生成的字段，另一个 Agent 当成事实继续使用。

因此，统一 Harness 的另一个目标是：

```text
让不同 Agent 共享同一套事实源、同一套规则、同一套检查机制。
```

---

## 11. 统一体系的目录规划

建议在 `D:\Program Files\gitvscode\TianShu` 中采用以下结构：

```text
D:\Program Files\gitvscode\TianShu
├─ AGENTS.md
├─ PROJECT_STATUS.md
├─ docs
│  ├─ decisions
│  │  ├─ README.md
│  │  ├─ 001-duckdb-as-warehouse-engine.md
│  │  ├─ 002-bronze-silver-gold-layering.md
│  │  ├─ 003-silver-three-batch-strategy.md
│  │  ├─ 004-primary-key-strategy.md
│  │  ├─ 005-agent-memory-harness-system.md
│  │  └─ 006-parking-violation-amount-in-gold.md
│  ├─ memory
│  │  ├─ 经验复盘.md
│  │  ├─ 风险清单.md
│  │  ├─ 规则来源索引.md
│  │  └─ 变更复盘模板.md
│  ├─ warehouse
│  │  ├─ AGENTS.md
│  │  ├─ bronze
│  │  │  └─ AGENTS.md
│  │  ├─ silver
│  │  │  └─ AGENTS.md
│  │  ├─ gold
│  │  │  └─ AGENTS.md
│  │  ├─ database_design
│  │  │  ├─ README.md
│  │  │  ├─ bronze_database_design.md
│  │  │  ├─ silver_database_design.md
│  │  │  └─ gold_database_design.md
│  │  └─ data_dictionary
│  │     ├─ README.md
│  │     ├─ 枚举值识别方法论.md
│  │     └─ bronze_enum_values.md
│  ├─ standards
│  │  ├─ README.md
│  │  └─ 数据仓库文档规范.md
│  ├─ meta
│  ├─ modeling
│  └─ silver
├─ agents
│  ├─ text2sql
│  │  └─ AGENTS.md
│  └─ review
│     └─ AGENTS.md
├─ scripts
│  ├─ memory
│  │  └─ append_lesson.py
│  ├─ quality
│  │  ├─ check_silver_dictionary.py
│  │  ├─ check_dangerous_patterns.py
│  │  ├─ check_schema_consistency.py
│  │  ├─ check_silver_null.py
│  │  ├─ check_memory_update.py
│  │  ├─ check_gold_design.py
│  │  ├─ check_gold_physical.py
│  │  ├─ run_all_checks.py
│  │  └─ harness_config.py
│  ├─ bronze
│  ├─ silver
│  │  ├─ build_silver_duckdb.py
│  │  └─ _gen_xlsx.py
│  ├─ gold
│  └─ meta
├─ .githooks
│  └─ pre-commit
├─ harness
│  ├─ README.md
│  ├─ checklists
│  │  ├─ pre_silver_build.md
│  │  ├─ schema_change_review.md
│  │  └─ pr_review.md
│  ├─ config
│  │  ├─ harness_targets.yml
│  │  └─ silver_sparsity_baseline.yml
│  ├─ reports
│  │  └─ README.md
│  └─ lessons
│     └─ README.md
├─ sql
│  ├─ bronze
│  ├─ silver
│  ├─ gold
│  └─ meta
└─ tests
   ├─ test_database_design.py
   ├─ test_silver_dictionary.py
   ├─ test_schema_consistency.py
   ├─ test_agent_rules.py
   └─ test_dangerous_patterns.py
```

---

## 12. 各部分职责

### 快速导航：我要做什么？

| 你的角色 | 你要做什么 | 先读 | 再跑 |
|---|---|---|---|
| 新加入的开发者 | 了解项目全貌 | `AGENTS.md` → `PROJECT_STATUS.md` → `docs/decisions/README.md` | 不需要 |
| Agent / AI 助手 | 开始一个任务 | `AGENTS.md`（自动加载）→ 按路由指令读对应文档 | 任务完成后跑 `run_all_checks.py` |
| 修改了表结构 | 确保一致性 | `docs/warehouse/database_design/` → `docs/memory/风险清单.md` | `check_schema_consistency.py --require-silver-tables` |
| 修改了构建脚本 | 确保经验沉淀 | `docs/memory/规则来源索引.md` | `check_memory_update.py` |
| 建完一批表 | 验证数据质量 | `docs/silver/Silver白银层规划.md` | `run_all_checks.py`（全部门禁） |
| 提交代码前 | 通过门禁 | 自动触发 `.githooks/pre-commit` | 或手动 `run_all_checks.py` |

### 校验视角

> 以下每个目录/文件不只是"存放内容"，还对应 Agent 代码正确性校验链条中的某一层。每一层单独拦不住所有错误，但五层叠加后拦截率趋近 100%：规则约束（告诉 Agent 边界）→ 事实锚定（给 Agent 准确数据）→ 经验避坑（警告 Agent 已知陷阱）→ 自主验证（Agent 自己检查输出）→ 自动检查（脚本硬拦截，这是最后防线）。

| 目录/文件 | 校验层 | 如果缺失 |
|---|---|---|
| `AGENTS.md` | 第 1 层·规则约束 | LLM 不知道边界 |
| `docs/warehouse/database_design/` | 第 2 层·事实锚定 | LLM 凭记忆猜测表结构 |
| `docs/warehouse/data_dictionary/` | 第 2 层·事实锚定 | LLM 不知道枚举值含义 |
| `docs/memory/` | 第 3 层·经验避坑 | 同类错误反复出现 |
| `docs/decisions/` | 第 1+2 层 | LLM 可能推翻已有决策 |
| `scripts/quality/check_*.py` | 第 5 层·自动检查 | 无硬拦截，全靠自律 |
| `tests/test_*.py` | 第 5 层·回归保护 | 修过的 bug 再次出现 |
| `harness/checklists/` | 跨层·人类操作指南 | 人不知道何时跑什么检查 |

### 11.1 AGENTS.md：规则入口 + 路由表

根目录 `AGENTS.md` 不是知识库，也不是项目流水账。

它的职责是：

- 定义最高原则。
- 说明 Agent 不能做什么。
- **作为路由表，强制指定"做 X 任务前必须先读 Y 文档"。**
- 指向更细的规则文档。
- 约束所有 Agent 行为。

> **关键认知一（路由表）**：AGENTS.md 是 Agent 启动时唯一自动加载的文档。项目中的其他文档——`docs/memory/`、`docs/decisions/`、`docs/warehouse/`——都不会被自动读取。Agent 只有在 AGENTS.md 中明确看到"做 X 前必须先读 Y"时，才会主动去打开 Y。因此，AGENTS.md 不能只做"索引"（列出有哪些文档），必须做"路由"（在什么任务下必须读什么文档）。只列文件名而不写触发条件，等于把文档藏在了 Agent 看不到的地方。
>
> **关键认知二（内容拆分）**：AGENTS.md 的每一行都会在所有任务中持续占用上下文——无论当前任务是否用得上。因此，AGENTS.md 中只能保留**所有任务都需要的通用规则**（最高原则、零幻觉约束、路由表、Human Review 触发条件、完成标准）。**只在特定任务中需要的专项规范**（DuckDB 建表语法、文档格式要求、Agent 输出格式）应移至 `docs/standards/`，只在该任务的 AGENTS.md 路由条目中指向它。判断标准：该规则在 90%+ 的任务中需要 → 留在 AGENTS.md；在 <30% 的任务中需要 → 移出。详见 Obsidian 知识库 [[AGENTS.md内容拆分原则-通用vs专项与上下文预算]]。

当前已经加入的最高原则是：

```text
数据库设计文档是本项目的唯一事实源。
AI 不允许脱离 Bronze 原始字段和数据库设计文档创造字段。
任何字段新增、删除、改名、类型变化，都必须通过文档更新、PR 审核和一致性检查。
AGENTS.md 不是知识垃圾桶，而是规则入口 + 路由表。
```

这条原则应该长期保留。

**AGENTS.md长度** 目前长度：523 行，在可接受范围
     
  AGENTS.md 注入 System Prompt 后约占用 2000+ tokens。Claude Code 的上下文窗口是 200K tokens，占比约 1%。当前长度不是问题，但如果未来继续膨胀（超过   
  800 行），需要考虑把详细规范（如代码规范、DuckDB 建表规范）拆分到 docs/standards/ 下，AGENTS.md 只保留路由指令 + 最高原则。

### 11.2 PROJECT_STATUS.md：项目状态入口

`PROJECT_STATUS.md` 用来解决“Agent 一进来不知道项目做到哪里”的问题。

它应该记录：

- 当前阶段
- 最近完成事项
- 当前阻塞点
- 下一步计划
- 最近发现的高风险问题
- 当前事实源文档位置
- 当前数据库位置

它不是详细设计文档，而是状态导航。

建议每次阶段切换时更新。

### 11.3 docs/memory：经验沉淀层

`docs/memory` 是真正的项目记忆区。

它回答：

```text
我们踩过什么坑？
为什么踩坑？
当时怎么修？
沉淀成了哪条规则？
有没有对应检查脚本？
有没有对应测试？
```

它应该包含：

- `经验复盘.md`
- `风险清单.md`
- `规则来源索引.md`
- `变更复盘模板.md`

它不应该替代数据库设计文档，也不应该承载正式字段定义。

### 11.4 docs/decisions：架构决策记录层

`docs/decisions` 是项目关键架构决策的统一存放位置。

它回答：

```text
为什么选这个技术方案？
当时有哪些替代方案？
决策的前提条件是什么？
什么情况下需要重新评估这个决策？
```

它应该包含：

- `README.md`：决策索引 + ADR 模板
- 以编号开头的独立决策文件（如 `001-duckdb-as-warehouse-engine.md`）

每份决策记录应包含：

```text
Status（状态）：Proposed / Accepted / Deprecated / Superseded
Context（背景）：当时面临什么问题？有什么约束？
Decision（决策）：我们决定怎么做？
Alternatives（替代方案）：考虑过哪些其他方案？为什么没选？
Consequences（后果）：这个决定带来了什么正面和负面影响？
```

它与 `docs/memory` 的区别：

```text
经验复盘（memory）：记录"我们踩了一个坑"→ 怎么修 → 沉淀什么规则。
决策记录（decisions）：记录"我们做了一个选择"→ 为什么选 A 不选 B → 何时重新评估。
```

它不应该：
- 替代数据库设计文档
- 记录日常操作步骤
- 变成另一个知识垃圾桶

### 11.5 docs/warehouse：数据仓库事实和规则层

`docs/warehouse` 是数据仓库的正式规则区。

它回答：

```text
当前正式规则是什么？
数据库设计事实源是什么？
Bronze、Silver、Gold 各层允许什么？
表字段以哪个文档为准？
```

其中：

- `docs/warehouse/AGENTS.md` 是数据仓库总规则。
- `docs/warehouse/bronze/AGENTS.md` 是 Bronze 规则。
- `docs/warehouse/silver/AGENTS.md` 是 Silver 规则。
- `docs/warehouse/gold/AGENTS.md` 是 Gold 规则。
- `docs/warehouse/database_design` 是最高事实源目录。
- `docs/warehouse/data_dictionary` 是字段字典目录。

### 11.6 docs/standards：规范索引层

`docs/standards` 是规范入口和路由层。

它回答：

```text
某类规范应该去哪里看？
哪个目录维护正式规则？
发生冲突时以哪里为准？
```

它不应该：

- 维护正式数据库设计。
- 维护字段字典。
- 维护枚举值（状态码/标志位/分类代码）含义。
- 复制 `docs/warehouse/*/AGENTS.md` 的分层规则。

具体规范必须下沉到对应事实源：

- 表结构、字段、主键、类型：`docs/warehouse/database_design/`
- 字段字典、枚举值（状态码/标志位/分类代码）含义：`docs/warehouse/data_dictionary/`
- 分层规则：`docs/warehouse/*/AGENTS.md`
- 经验复盘：`docs/memory/`

### 11.7 scripts/quality：检查脚本实现层

`scripts/quality` 是 Harness 的执行核心。

它负责把文档规则变成程序检查。

应该逐步实现：

- 数据库设计文档是否存在
- 字段字典是否存在
- 字段字典与数据库设计文档是否一致
- DuckDB 实际 schema 与数据库设计文档是否一致
- Silver 字段是否能追溯到 Bronze
- 派生字段是否有来源字段和计算逻辑
- 中文名和中文注释是否完整
- 是否出现危险 SQL 模式
- Gold 是否跳过 Silver 直接引用 Bronze

### 11.8 harness：工程执行入口

`harness/` 是 Agent Memory + Warehouse Harness 的工程入口。

它回答：

```text
怎么运行 Harness？
运行前要检查什么？
PR 前看哪份清单？
Schema 变更怎么审核？
检查目标路径在哪里登记？
检查报告怎么管理？
```

它应该包含：

- `README.md`：Harness 总入口。
- `checklists/`：Silver 建表前、Schema 变更、PR 审核清单。
- `config/`：Harness 检查目标路径。
- `reports/`：检查报告目录说明。
- `lessons/`：说明如何引用 `docs/memory/`，不重复记录经验。

它不应该：

- 定义正式表结构。
- 复制字段字典。
- 复制经验复盘。
- 替代 `docs/warehouse/database_design/`。
- 替代 `docs/warehouse/data_dictionary/`。

### 11.9 tests：回归保护层

`tests` 是经验固化后的回归保护。

当一次错误被发现后，不应该只写复盘，还应该补测试。

例如：

```text
发现 parking_violation_detail 凭空新增金额字段
  ↓
写入 docs/memory/经验复盘.md
  ↓
更新 docs/warehouse/silver/AGENTS.md
  ↓
新增 scripts/quality/check_silver_dictionary.py 检查
  ↓
新增 tests/test_silver_dictionary.py 回归测试
```

这样下一次同类问题会被自动拦截。

### 11.10 agents/text2sql：问数 Agent 规则

Text2SQL Agent 必须比普通数据开发 Agent 更保守。

它不能为了满足用户问题而临时创造字段或指标。

它必须遵守：

- 优先使用 Gold。
- Gold 不存在时使用 Silver。
- Bronze 只用于排查和追溯。
- 无法确认字段和 Join 时必须反问或提示无法生成。
- SQL 输出必须基于已审核语义层和数据库设计文档。

### 11.11 agents/review：审核 Agent 规则

审核 Agent 是 Harness 的守门人。

它不负责“帮忙圆回来”，而是负责发现问题并阻止不合规变更。

它应该重点检查：

- 文档是否缺失
- 字段是否凭空出现
- 类型是否无说明变化
- Excel 和 Markdown 是否不一致
- SQL 和数据库设计是否不一致
- DuckDB 实际 schema 是否不一致
- 主键和 Join 是否缺少数据画像支持

---

## 13. 经验如何转化为规则和测试

### 12.1 示例一：停车罚单金额字段

#### 发现问题

Silver 规划中出现：

- `fine_amount`
- `payment_amount`
- `amount_due`

但 Bronze 表 `parking_violations_all` 中不存在这些字段。

#### 经验复盘

写入 `docs/memory/经验复盘.md`：

```text
问题：AI 根据业务直觉为停车罚单补充金额字段。
原因：规划时没有强制对照 Bronze schema 和数据库设计文档。
影响：Silver 层会出现虚假来源字段，后续 Gold 指标和 Text2SQL 会继续放大错误。
规则：Silver 字段必须可追溯到 Bronze，或有明确派生逻辑和 Human Review 状态。
```

#### 规则沉淀

写入 `docs/warehouse/silver/AGENTS.md`：

```text
parking_violations_all 当前没有金额字段，不得在 silver.parking_violation_detail 中直接新增实收、应收、罚款、滞纳金等来源型金额字段。
```

#### 自动检查

在 `scripts/quality/check_silver_dictionary.py` 中检查：

- Silver 字段是否存在来源字段。
- 如果不存在来源字段，是否填写派生逻辑。
- 如果字段名包含 `amount`、`fine`、`payment`、`penalty`、`fee`，是否有来源和金额口径说明。

#### 回归测试

在 `tests/test_silver_dictionary.py` 中增加测试：

```text
当 Silver 数据字典出现无来源金额字段时，检查必须失败。
```

> **闭环耗时**：从发现问题到测试落地约 1 个工作日。其中编写检查脚本耗时最长（需遍历 11 张表的字段来源），但这一次投入后，同类问题永不再过。

### 12.2 示例二：dim_date 的 DuckDB 日期转换

#### 发现问题

规划 SQL 使用：

```sql
DATE::INT
```

但 DuckDB 不支持 `DATE` 直接转 `INT`。

#### 经验复盘

问题不是简单的 SQL 写错，而是：

```text
模型规划文档中的 SQL 片段也必须经过数据库方言校验。
```

#### 规则沉淀

写入 Silver 规则：

```text
dim_date.date_key 在 DuckDB 中不得使用 DATE::INT，应使用 strftime(date_value, '%Y%m%d')::INTEGER。
```

#### 自动检查

`check_dangerous_patterns.py` 扫描：

```text
DATE::INT
```

发现后直接报错。

> **闭环耗时**：从发现到规则落地约半小时——这是一个典型的"语法级"问题，检查脚本只需正则匹配 `DATE::INT` 即可。这也说明：问题的通用性越高，检查脚本的投入产出比越好。

### 12.3 示例三：无序 ROW_NUMBER 生成主键

#### 发现问题

规划中使用：

```sql
ROW_NUMBER() OVER ()
```

生成 `trip_id`。

这会导致重跑后 ID 不稳定。

#### 经验复盘

问题本质是：

```text
代理键可以生成，但稳定主键不能依赖无序行号。
```

#### 规则沉淀

写入 Silver 规则：

```text
不得使用无序 ROW_NUMBER() OVER () 生成稳定主键。
```

#### 自动检查

扫描 SQL 和 Markdown：

```text
ROW_NUMBER() OVER ()
```

如果用于主键字段，必须失败。

> **闭环耗时**：从发现到规则落地约半小时，与示例二类似。但主键策略的影响面远超语法问题——它催生了 ADR-004（主键策略分级决策），从"禁止一种写法"升级为"定义一套策略"。这也展示了 Harness 的典型升级路径：具体错误 → 通用规则 → 架构决策。

---

## 14. 数据库设计文档为什么是最高优先级

### 13.1 数据仓库项目不能只相信代码

在普通软件项目中，代码经常是事实源。

但在数据仓库项目中，只有代码不够。

原因是：

- SQL 只说明怎么建表，不一定说明字段业务含义。
- DuckDB schema 只说明字段存在，不说明字段来源。
- Excel 字典可能和实际表结构不同步。
- Markdown 规划可能是草案，不一定已审核。
- Agent 生成的内容可能包含推断。

因此，必须有一个明确的最高事实源：

```text
数据库设计文档。
```

### 13.2 数据库设计文档必须包含什么

数据库设计文档不能只写表名和字段名。

它必须至少包含：

- 英文表名
- 中文表名
- 表说明
- 所属层级
- 所属数据域
- 数据粒度
- 主键
- 候选键
- 关联键
- 英文字段名
- 中文字段名
- 数据类型
- 字段来源
- 来源表
- 来源字段
- 派生逻辑
- 空值规则
- 枚举说明
- 质量规则
- 是否审核通过

### 13.3 字段变更必须走流程

每次 schema 变更必须遵守：

```text
每次 schema 变更
  ↓
必须更新数据库设计文档
  ↓
必须更新字段字典
  ↓
必须通过一致性检查
  ↓
PR 才能合并
```

这个流程的作用是：

- 防止 Agent 私自新增字段。
- 防止 SQL 与文档不一致。
- 防止 Excel 字典滞后。
- 防止开发库和线上库不一致。
- 防止 Text2SQL 使用错误字段。

---

## 15. 自动触发还是人工触发

### 14.1 当前状态

当前项目中的记忆更新不是自动触发的。

也就是说，如果没有明确流程，Agent 不会天然地在每次出错后自动：

- 写入经验复盘
- 更新规则文档
- 增加检查脚本
- 增加测试

因此，需要把触发机制显式写入 Harness。

### 14.2 推荐触发方式

建议采用三类触发。

#### 人工触发

当用户说：

```text
把这次经验写入记忆
```

Agent 必须执行：

1. 更新 `docs/memory/经验复盘.md`。
2. 判断是否需要更新 `AGENTS.md` 或分层规则。
3. 判断是否需要增加 quality 检查。
4. 判断是否需要增加测试。

#### 阶段触发

每完成一个阶段时，自动进行复盘。

例如：

- Bronze 阶段完成
- Silver 规划完成
- Silver 建表完成
- Gold 建模完成
- Text2SQL Agent 接入完成

阶段复盘应回答：

- 本阶段新增了哪些事实？
- 本阶段发现了哪些问题？
- 哪些问题需要写入记忆？
- 哪些问题需要变成规则？
- 哪些规则需要自动检查？

#### 变更触发

每次修改以下内容时，必须运行一致性检查：

- 数据库设计文档
- 字段字典
- Silver 规划
- Gold 指标规划
- SQL 建表脚本
- DuckDB schema
- Agent 规则文件
- Harness 检查清单和配置

---

## 16. 最小可行版本

不要一开始就把 Harness 做得过重。

建议先建设最小可行版本。

### 15.1 第一阶段：目录和文档

先建立：

```text
docs/memory/经验复盘.md
docs/memory/风险清单.md
docs/memory/规则来源索引.md
docs/warehouse/database_design/README.md
docs/warehouse/data_dictionary/README.md
PROJECT_STATUS.md
harness/README.md
```

目标是让记忆、事实源、状态和 Harness 执行入口都有固定位置。

### 15.2 第二阶段：Harness 工程入口

建立：

```text
harness/README.md
harness/checklists/pre_silver_build.md
harness/checklists/schema_change_review.md
harness/checklists/pr_review.md
harness/config/harness_targets.yml
harness/reports/README.md
harness/lessons/README.md
```

这一阶段只定义运行入口和检查清单，不复制 `database_design/`、`data_dictionary/` 和 `docs/memory/` 的内容。

### 15.3 第三阶段：第一批检查脚本

先实现：

```text
scripts/quality/check_silver_dictionary.py
scripts/quality/check_dangerous_patterns.py
scripts/quality/check_schema_consistency.py
```

第一批检查聚焦已经发生过的问题：

- Silver 中无来源金额字段
- `DATE::INT`
- 无序 `ROW_NUMBER() OVER ()`
- 文档字段数与 Excel 字典字段数不一致
- 英文名缺少中文名

### 15.4 第四阶段：测试固化

建立：

```text
tests/test_silver_dictionary.py
tests/test_dangerous_patterns.py
tests/test_schema_consistency.py
```

目标不是测试业务结果，而是测试项目规则是否被执行。

### 15.5 第五阶段：PR 审核流程

后续再把 Harness 接入 PR 流程。

PR 合并前必须通过：

- 数据库设计检查
- 字段字典检查
- schema 一致性检查
- 危险模式扫描
- Agent 规则检查

### 15.6 可扩展性考量

以上是最小可行版本。当项目规模增长时，Harness 自身也需要演进，但演进应遵循三条原则：

**原则一：事实源不能随规模扩散。** 当 ADR 积累到 50 份、经验复盘到 5000 行时，不能通过"再新建一个目录"来解决组织问题——那会制造新的事实源。正确做法是在现有目录内部建立子索引。例如 `docs/decisions/README.md` 的索引表已经提供了按状态和日期筛选的能力，`docs/memory/规则来源索引.md` 已经提供了经验到规则的映射。

**原则二：检查脚本的运行成本必须可控。** 当检查脚本积累到 30 个时，全量运行可能需要数分钟。`run_all_checks.py` 应支持按层级筛选（如 `--layer silver`）和按变更范围筛选（如 `--changed-files`），让日常开发只运行相关检查，全量检查留给 PR 门禁。

**原则三：复盘文档必须有生命周期管理。** `docs/memory/经验复盘.md` 如果涨到 5000 行，本身就会变成另一个"上下文过长"的问题——Agent 需要从 5000 行复盘中找到与当前任务相关的 2 条。解决方式不是让 Agent 全量阅读，而是：每条经验沉淀后，其核心规则必须提取到分层 `AGENTS.md`，复盘原文降级为"详细背景说明"，日常 Agent 只读 `AGENTS.md` 规则，只有需要深入理解时才查看复盘原文。

---

## 17. 落地进展与下一步计划

> 本章节反映当前实际状态，每次阶段切换时更新。

### 17.1 已落地（2026-05 ~ 2026-06-09）

- [x] 建立 `docs/memory`（经验复盘、风险清单、规则来源索引、变更复盘模板）
- [x] 建立 `docs/warehouse/database_design`（Bronze/Silver/Gold 三层数据库设计文档）
- [x] 建立 `docs/warehouse/data_dictionary`（字段字典 + 枚举值识别方法论 + Bronze 枚举值）
- [x] 建立 `scripts/quality`（6 个检查脚本：dictionary、dangerous_patterns、schema_consistency、silver_null、memory_update、gold_design）
- [x] 建立 `tests`（test_silver_dictionary 6 用例、test_harness_quality 5 用例、test_gold_design_quality）
- [x] 建立 `docs/decisions`（6 份架构决策记录 + 索引）
- [x] 建立 `harness/` 工程入口（checklists、config、reports、lessons）+ `harness_targets.yml` 阶段配置
- [x] 建立 7 个分层 AGENTS.md，根 AGENTS.md 从索引升级为路由表
- [x] Silver 层 11 张表全部建成（~9,738 万行）+ 数据字典 xlsx（12 sheets，211 字段）
- [x] Silver 数据质量校验通过（schema 一致性、空值画像、主键唯一性、金额/日期转换）
- [x] `run_all_checks.py` 全量门禁通过（7 项检查，11 个 pytest 全部通过）
- [x] **Memory Gate** 落地：`check_memory_update.py` 强制关键变更同步更新 `docs/memory`
- [x] **预期稀疏基线**体系建立：`silver_sparsity_baseline.yml`（17 条基线，三级分类）
- [x] **阶段感知 Harness**：`stage: post_silver_build` 自动启用 `--require-silver-tables`
- [x] **Git pre-commit hook**：`.githooks/pre-commit` 自动运行 Memory Gate + 危险模式 + pytest
- [x] `docs/standards/`、`docs/silver/`、`sql/silver/` 已同步更新，明确"规范不自动生效，需 Harness 执行"
- [x] Silver 构建脚本日期/金额转换修复（美国日期、货币字符串、千位分隔整数）

### 17.2 经验已沉淀（共 14 条经验 + 6 条规则 + 19 个风险）

**经验复盘（R001-R014）：**
1. R001：Silver 不得凭空新增 Bronze 不存在的金额字段 → `check_silver_dictionary.py`
2. R002：DuckDB 禁用 `DATE::INT` → `check_dangerous_patterns.py`
3. R003：稳定主键不得使用无序 `ROW_NUMBER() OVER ()` → `check_dangerous_patterns.py`
4. R004：枚举值不得硬编码 → `check_silver_dictionary.py`
5. R005：字段数字典、Markdown 和设计文档必须一致 → `check_schema_consistency.py`
6. R006：金额字段必须使用 `DECIMAL` → `test_silver_dictionary.py`
7. R007：MD5 代理键在 8,000 万行规模下可能碰撞 → `build_silver_duckdb.py` 内置校验
8. R008：DuckDB `TRY_CAST` 无法解析 ISO 日期格式拼接时间 → `build_silver_duckdb.py` 修复
9. R009：DuckDB `ROW_NUMBER` 不能引用同层 SELECT 的别名 → `build_silver_duckdb.py` 修复
10. R010：DuckDB `INSERT OR REPLACE` 需要唯一约束 → `build_silver_duckdb.py` 修复
11. R011：建表完成后未同步更新关联文档 → `AGENTS.md` §13 变更传播规则
12. R012：AGENTS 规则不是自动触发器 → `check_memory_update.py` + `run_all_checks.py`
13. R013：Silver 建成后必须启用实表强校验 → `harness_targets.yml` + `--require-silver-tables`
14. R014：`TRY_CAST` 静默失败必须用格式化解析和空值检查兜底 → `try_strptime` + `regexp_replace` + `check_silver_null.py`

**风险清单（RISK-001 ~ RISK-019）：** 覆盖 DuckDB 方言、主键碰撞、文档漂移、`TRY_CAST` 陷阱、阶段感知缺失、规则无执行器等 19 项风险。

### 17.3 下一步：Gold 层建设

**核心原则**：Silver 层的教训是"表建出来了，文档、字典、注释、门禁没跟上"。Gold 层不重复这个模式——**先建维表 + 同步补 Gold post-build gate，不一次性建所有事实表**。

#### Gold 建设批次

```text
G0 公共维表（先建，零依赖）
  gold.dim_date           → 来源 silver.dim_date
  gold.dim_taxi_zone      → 来源 silver.taxi_zone
  同步：更新 Gold 设计文档 + meta.column_comments

G1 业务维表（依赖 G0）
  gold.dim_vehicle        → 来源 silver.vehicle_detail
  gold.dim_driver         → 来源 silver.driver_detail
  gold.dim_base           → 来源 silver.base_detail
  gold.dim_violation_type → 来源官方违章代码字典
  同步：扩展 check_schema_consistency.py 增加 Gold schema 对比

G2 明细事实表（依赖 G0+G1）
  gold.fact_trips               → 来源 silver.trip_detail
  gold.fact_parking_violations  → 来源 silver.parking_violation_detail
  gold.fact_tif_payments        → 来源 silver.tif_payment_detail
  gold.fact_driver_applications → 来源 silver.driver_application_detail
  gold.fact_crashes             → 来源 silver.crash_detail
  gold.fact_crash_persons       → 来源 silver.crash_person_detail
  同步：增加 Gold 指标来源校验

G3 汇总与语义层
  每日出行汇总、区域 OD 汇总、每日罚单汇总、每日事故汇总
  中文指标口径定义、Text2SQL 问数模板
```

#### Gold 专用强校验（建 Gold 实表时同步扩展）

当前 Harness 已能拦截 Silver 层的大部分错误。Gold 实表落地时需在 `check_schema_consistency.py` 中增加：

| 检查项 | 说明 | 优先级 |
|---|---|---|
| Gold 设计文档 vs DuckDB gold schema | 表存在性、字段数、字段名、数据类型双向一致 | P0 |
| Gold 字段中文注释覆盖率 | `meta.column_comments` 中 gold 注释 = 实表字段数，必须 100% | P0 |
| Gold 指标来源字段校验 | 每个 Gold 指标字段必须标注来源 Silver 表/字段或派生逻辑 | P1 |
| Gold 禁止直接 `FROM bronze` | 扫描 Gold SQL，`FROM bronze.` 必须报错（白名单例外）。**原因**：Gold 如果跳过 Silver 直接读 Bronze，会丢失 Silver 层做的类型标准化（如 VARCHAR→DECIMAL）、质量标记（is_time_anomaly 等）和字段统一命名，导致指标口径不一致。 | P1 |

#### 中文字段名原则

Gold 中文名不得用 LLM 翻译直接生成。必须来源于：
1. `meta.column_comments`（Silver 已有中文注释直接复用）
2. Silver 数据字典 xlsx（已有中文名延续使用）
3. 官方数据字典整理结果
4. 项目术语表（待建）
5. 人工审核

> 原则：中文名必须可追溯来源，与上游保持一致。LLM 翻译只能做草稿，不能作为最终事实源。

### 17.4 远期待办

1. [ ] 实现 `check_agent_rules.py`（Gold 不跳过 Silver 的检查）
2. [ ] CI/PR 审核流程接入 Harness（GitHub Actions 自动运行全部门禁）

---

## 18. 最终目标

最终目标不是让 Agent “记得更多”，而是让项目形成自己的防错系统。

理想状态是：

```text
Agent 可以忘记上下文。
但项目不会忘记规则。
```

每次经验都应该被沉淀成：

```text
经验复盘
  ↓
规则文档
  ↓
设计文档
  ↓
检查脚本
  ↓
测试用例
```

这样项目才能在多 Agent、多阶段、长周期的数据仓库建设中保持一致性。

### 18.1 Harness 的元治理：谁来保证 Harness 本身的质量不下滑？

一个自然的疑问是：Harness 约束 Agent，但谁来约束 Harness 的维护者？

答案是：**当前阶段，Harness 的维护者是项目负责人自己。** Harness 不是自动运行的 AI——它是人在发现错误后，主动写复盘、写检查、写测试，然后把检查接入 `run_all_checks.py`。这套动作的触发依赖于人的纪律，而非自动化。

但这并不意味着元治理问题不重要。随着项目演进，以下机制可以逐步引入：

1. **Harness 自我检查**：`check_agent_rules.py`（待实现）会检查 AGENTS.md 中的每条规则是否都有对应的 quality 脚本——如果一条规则没有执行机制，检查脚本本身就会报 Warning。
2. **阶段复盘强制触发**：每次 `PROJECT_STATUS.md` 的阶段状态变更时，Review Agent 检查是否伴随了经验复盘更新。
3. **Harness 腐烂检测**：如果 `run_all_checks.py` 超过 N 天未运行或未更新，在下次运行时给出提示——"Harness 自身可能已过时，请检查是否有新的问题未被覆盖"。

这些机制的核心思路是一致的：**用 Harness 的一部分能力来检查 Harness 本身的完整性。** 这不是完美的自举（完全自举是不可能的），但足以防止最常见的腐化模式——"规则写了但检查没跟上"。

---

## 19. 总结

本项目不应该只建设一个“记忆系统”，也不应该只建设一个“测试 Harness”。

正确方向是建设统一的：

```text
Agent Memory + Warehouse Harness
```

其中：

- Agent Memory 负责记录经验、复盘问题、解释规则来源。
- Warehouse Harness 负责把规则变成检查、测试和审核门禁。
- 数据库设计文档是最高事实源。
- AGENTS.md 是规则入口，不是知识垃圾桶。
- 每次 schema 变更都必须更新设计文档、字段字典，并通过一致性检查。

这套体系的核心价值是：

```text
让每一次错误都变成下一次的自动防线。
```

---

## 附录：术语表

| 术语 | 英文 | 含义 |
|---|---|---|
| Agent | AI Coding Assistant | AI 编程助手，通过读取项目文件和自然语言指令来生成代码、SQL、文档和设计方案。本项目涉及的 Agent 包括 Claude Code、Codex 等 |
| 上下文 | Context | Agent 在单次对话中能"看到"的所有内容的统称，包括对话历史和加载的项目文件。有长度上限，超出的内容 Agent 无法感知 |
| 幻觉 | Hallucination | Agent 基于训练数据中的"常识"而非项目实际数据进行的推断，产物"看起来合理但无事实依据" |
| AGENTS.md | — | Agent 规则文件，Agent 在对话启动时自动扫描并加载。是项目的规则入口 |
| Harness | — | 约束执行系统，将多个检查、测试和规则集成到统一执行框架中 |
| ADR | Architecture Decision Record | 架构决策记录，独立记录每个关键架构决策的背景、方案、替代方案和后果 |
| Bronze 层 | Bronze Layer | 数据仓库原始层，保留原始数据不做业务改造 |
| Silver 层 | Silver Layer | 数据仓库标准明细层，对 Bronze 做字段命名、类型、质量标记的标准化 |
| Gold 层 | Gold Layer | 数据仓库业务主题层，基于 Silver 做星型模型、指标计算和分析宽表 |
| Meta 层 | Meta Layer | 元数据层，贯穿三层提供中文表名、字段名、枚举说明 |
| DuckDB | — | 嵌入式 OLAP 数据库引擎，本项目选用的数仓引擎 |
| Codex | OpenAI Codex | OpenAI 提供的 AI 编程助手 |
| Claude Code | — | Anthropic 提供的 CLI AI 编程助手 |
| Text2SQL | — | 自然语言转 SQL 查询的技术，本项目中专指将中文问题转为 DuckDB SQL 的 Agent |
| PR | Pull Request | Git 代码合并请求，Harness 的质量门禁在 PR 阶段执行检查 |
| Schema | — | 数据库结构定义，包括表名、字段名、数据类型、主键、外键等 |

