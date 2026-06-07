# Agent Memory + Warehouse Harness 统一体系方案

## 1. 文档目的

本文档用于说明 TianShu 项目为什么需要构建一个统一的 **Agent Memory + Warehouse Harness** 体系。

它不是单纯的“记忆文档”，也不是单纯的“测试脚本集合”，而是一个把 **规则、文档、复盘、测试、审核、一致性检查、Agent 协作规范** 连接起来的项目治理机制。

本项目当前已经进入以下阶段：

- 数据源已经覆盖纽约市城市交通多域数据。
- Bronze 层已经完成初步入库。
- Silver 层规划已经开始。
- 已经出现多 Agent 协作，包括 Codex、Claude Code 等。
- 已经出现规划文档、Excel 数据字典、DuckDB 实际 schema、Markdown 设计文档之间可能不一致的问题。
- 已经发现 AI 会根据业务直觉或外部知识生成 Bronze 中不存在的字段。

因此，项目已经不能只依赖一次对话上下文、单个 Agent 的临时记忆，或者人工口头提醒来保证质量。

本项目需要一个能持续沉淀经验、固化规则、自动检查、防止重复犯错的统一体系。

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

### 3.2 Claude Code 提出的三层记忆

Claude Code 给出的三层建议是：

```text
第一层：AGENTS.md
内容：Agent 能做什么、不能做什么
作用：约束 Agent 行为，防止重复犯错

第二层：CLAUDE.md / 项目 README
内容：项目是什么、当前阶段、关键决策
作用：让 Agent 一进来就知道上下文

第三层：知识库文档
内容：设计决策、踩坑复盘、方法论沉淀
作用：人类积累，跨项目复用
```

这个方案是正确的，但还不够。

它解决了“记忆放在哪里”的问题，但没有完全解决“记忆如何执行”的问题。

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

## 6. 本项目为什么尤其需要这个体系

### 6.1 数据域复杂

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

### 6.2 AI 容易在数据仓库项目中产生“合理幻觉”

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

### 6.3 多 Agent 协作需要共同规则

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

## 7. 统一体系的目录规划

建议在 `D:\Program Files\gitvscode\TianShu` 中采用以下结构：

```text
D:\Program Files\gitvscode\TianShu
├─ AGENTS.md
├─ PROJECT_STATUS.md
├─ docs
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
│  │     ├─ bronze_data_dictionary.xlsx
│  │     ├─ silver_data_dictionary.xlsx
│  │     └─ gold_data_dictionary.xlsx
│  ├─ standards
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
│  │  ├─ check_database_design.py
│  │  ├─ check_silver_dictionary.py
│  │  ├─ check_schema_consistency.py
│  │  ├─ check_agent_rules.py
│  │  └─ check_dangerous_patterns.py
│  ├─ bronze
│  ├─ silver
│  ├─ gold
│  └─ meta
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

## 8. 各部分职责

### 8.1 AGENTS.md：规则入口

根目录 `AGENTS.md` 不是知识库，也不是项目流水账。

它的职责是：

- 定义最高原则。
- 说明 Agent 不能做什么。
- 指向更细的规则文档。
- 约束所有 Agent 行为。

当前已经加入的最高原则是：

```text
数据库设计文档是本项目的唯一事实源。
AI 不允许脱离 Bronze 原始字段和数据库设计文档创造字段。
任何字段新增、删除、改名、类型变化，都必须通过文档更新、PR 审核和一致性检查。
AGENTS.md 不是知识垃圾桶，而是规则入口。
```

这条原则应该长期保留。

### 8.2 PROJECT_STATUS.md：项目状态入口

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

### 8.3 docs/memory：经验沉淀层

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

### 8.4 docs/warehouse：数据仓库事实和规则层

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

### 8.5 scripts/quality：规则执行层

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

### 8.6 tests：回归保护层

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

### 8.7 agents/text2sql：问数 Agent 规则

Text2SQL Agent 必须比普通数据开发 Agent 更保守。

它不能为了满足用户问题而临时创造字段或指标。

它必须遵守：

- 优先使用 Gold。
- Gold 不存在时使用 Silver。
- Bronze 只用于排查和追溯。
- 无法确认字段和 Join 时必须反问或提示无法生成。
- SQL 输出必须基于已审核语义层和数据库设计文档。

### 8.8 agents/review：审核 Agent 规则

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

## 9. 经验如何转化为规则和测试

### 9.1 示例一：停车罚单金额字段

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

### 9.2 示例二：dim_date 的 DuckDB 日期转换

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

### 9.3 示例三：无序 ROW_NUMBER 生成主键

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

---

## 10. 数据库设计文档为什么是最高优先级

### 10.1 数据仓库项目不能只相信代码

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

### 10.2 数据库设计文档必须包含什么

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

### 10.3 字段变更必须走流程

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

## 11. 自动触发还是人工触发

### 11.1 当前状态

当前项目中的记忆更新不是自动触发的。

也就是说，如果没有明确流程，Agent 不会天然地在每次出错后自动：

- 写入经验复盘
- 更新规则文档
- 增加检查脚本
- 增加测试

因此，需要把触发机制显式写入 Harness。

### 11.2 推荐触发方式

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

---

## 12. 最小可行版本

不要一开始就把 Harness 做得过重。

建议先建设最小可行版本。

### 12.1 第一阶段：目录和文档

先建立：

```text
docs/memory/经验复盘.md
docs/memory/风险清单.md
docs/memory/规则来源索引.md
docs/warehouse/database_design/README.md
docs/warehouse/data_dictionary/README.md
PROJECT_STATUS.md
```

目标是让记忆、事实源和状态有固定位置。

### 12.2 第二阶段：第一批检查脚本

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

### 12.3 第三阶段：测试固化

建立：

```text
tests/test_silver_dictionary.py
tests/test_dangerous_patterns.py
tests/test_schema_consistency.py
```

目标不是测试业务结果，而是测试项目规则是否被执行。

### 12.4 第四阶段：PR 审核流程

后续再把 Harness 接入 PR 流程。

PR 合并前必须通过：

- 数据库设计检查
- 字段字典检查
- schema 一致性检查
- 危险模式扫描
- Agent 规则检查

---

## 13. 本项目建议的近期落地计划

### 13.1 立即要做

1. 建立 `docs/memory`。
2. 建立 `docs/warehouse/database_design`。
3. 建立 `docs/warehouse/data_dictionary`。
4. 建立 `scripts/quality`。
5. 建立 `tests`。
6. 把本次 Silver 审查发现的问题写入第一批经验复盘。

### 13.2 第一批经验

建议第一批写入：

1. `parking_violation_detail` 不得凭空新增金额字段。
2. `dim_date.date_key` 不得使用 DuckDB 不支持的 `DATE::INT`。
3. 稳定主键不得使用无序 `ROW_NUMBER() OVER ()`。
4. Silver 字段数量必须与 Excel 数据字典一致。
5. Gold 不得跳过 Silver 直接基于 Bronze 建正式模型。
6. 字段中文名、表中文名、中文注释必须完整。

### 13.3 第一批自动检查

建议第一批脚本检查：

- Markdown 和 Excel 中是否出现无来源金额字段。
- Markdown 和 SQL 中是否出现 `DATE::INT`。
- Markdown 和 SQL 中是否出现无序 `ROW_NUMBER() OVER ()`。
- Excel 字段行数与 Markdown 声明字段数是否一致。
- 字段是否有英文名和中文名。
- 建表 SQL 是否有中文表注释和字段注释。

---

## 14. 最终目标

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

---

## 15. 总结

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

