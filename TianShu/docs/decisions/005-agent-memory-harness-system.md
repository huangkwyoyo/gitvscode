# 005 — Agent Memory + Warehouse Harness 统一治理体系

## Status（状态）

Accepted

## Context（背景）

TianShu 项目在建设过程中逐步暴露出几个结构性问题：

1. **对话上下文不可靠**：随着任务增多（数据源扫描→Bronze 入库→Silver 规划→字典生成→多 Agent 审查），上下文越来越长，Agent 抓不住重点，且不同 Agent 会话之间信息不共享
2. **同类错误反复出现**：AI 会根据业务直觉编造 Bronze 中不存在的字段（如停车罚单的金额字段）、使用 DuckDB 不支持的语法（`DATE::INT`）、生成无序主键（`ROW_NUMBER() OVER ()`）
3. **规则无执行能力**：`AGENTS.md` 写了规则，但没有自动检查机制，规则靠"Agent 自觉遵守"
4. **多 Agent 协作无统一标准**：项目中出现 Codex 和 Claude Code 协作，不同 Agent 对字段命名、中文注释、指标口径的理解不一致

如果只靠人工提醒和对话上下文来保证质量，项目在多 Agent、长周期的数据仓库建设中必然会不断踩坑。

核心问题：**如何让项目经验不依赖某一次对话，而成为长期可复用的资产？如何让规则不只是"写在那里"，而是能被自动执行和验证？**

## Decision（决策）

**构建统一的 Agent Memory + Warehouse Harness 体系，把记忆沉淀、规则约束和自动检查连接成一个闭环。**

### 体系结构

```text
Agent Memory（经验沉淀层）
  ├── docs/memory/经验复盘.md      ← 踩过的坑
  ├── docs/memory/风险清单.md      ← 已知风险
  └── docs/memory/规则来源索引.md  ← 每条规则从哪条经验来

Warehouse Harness（规则执行层）
  ├── docs/warehouse/              ← 分层规则 + 数据库设计（最高事实源）
  ├── docs/standards/              ← 规范索引入口，不重复维护具体规范
  ├── docs/decisions/              ← 架构决策记录（为什么这么做）
  ├── scripts/quality/             ← 自动检查脚本
  ├── tests/                       ← 回归测试
  ├── harness/                     ← Harness 工程入口、检查清单、配置和报告入口
  ├── agents/review/               ← 审核 Agent 守门
  └── agents/text2sql/             ← 问数 Agent 规则
```

### 闭环链路

```text
发现问题
  ↓
docs/memory 记录经验
  ↓
docs/warehouse 形成正式规则
  ↓
docs/warehouse/database_design 更新事实源
  ↓
scripts/quality 新增检查脚本
  ↓
tests 固化为回归测试
  ↓
agents/review 在审核阶段拦截
  ↓
同类错误不再进入项目
```

### 核心原则

1. **数据库设计文档是最高事实源**——代码、SQL、Excel、Markdown 冲突时，以数据库设计文档为准
2. **Agent 只能整理事实，不能创造事实**——所有字段必须可追溯到 Bronze 或 Meta
3. **AGENTS.md 是规则入口，不是知识垃圾桶**——详细规则拆分到对应文档
4. **standards/ 只做规范索引，不做第二事实源**——具体规范维护在 `database_design/`、`data_dictionary/`、分层 `AGENTS.md`
5. **harness/ 只做工程执行入口，不做第二事实源**——检查清单和配置可以放在 Harness，但 schema 和字典仍归属 `docs/warehouse/`
6. **经验必须转化为规则，规则必须转化为检查**——只写复盘而不补检查的闭环是断的

## Alternatives（替代方案）

| 方案 | 优势 | 劣势 | 排除原因 |
|---|---|---|---|
| **只靠 AGENTS.md + 人工 Checking** | 实现成本最低 | Agent 可能没读到、读到但忘记执行、人类忘记提醒、规则没有测试保护 | 已经验证不可靠——停车罚单金额字段就是在有 AGENTS.md 的情况下编造的 |
| **引入 dbt + Great Expectations** | 工业级数据质量工具，生态成熟 | 需要额外学习成本，dbt 与 DuckDB 的集成有局限，对 AI 幻觉类问题没有针对性检查 | 过度设计——当前 11 张表不需要工业级工具链 |
| **只做 Memory 不做 Harness** | 简单，先沉淀经验再说 | 经验写了但没有执行机制，同类错误仍然可能再次出现 | Memory 的价值在于阻止下一次错误，没有 Harness 的 Memory 是"记了但没用" |
| **Memory + Harness 统一体系** ✅ | 经验到规则的链路完整，检查脚本能自动拦截已发生过的错误 | 初期建设成本较高（需要写文档 + 脚本 + 测试） | 已通过最小可行版本策略控制成本 |

## Consequences（后果）

### 正面影响

- **闭环自动拦截**：已发生过的 5 类错误（无来源金额字段、`DATE::INT`、无序 `ROW_NUMBER`、字段数不一致、缺少中文注释）都有对应的检查脚本
- **知识可传递**：新 Agent 进入项目时，读 `AGENTS.md` → `PROJECT_STATUS.md` → `docs/decisions/` → 分层 AGENTS.md，即可理解项目全貌
- **规则可追溯**：每条规则都能追溯到 `docs/memory/规则来源索引.md` 中的原始经验
- **审核有依据**：审核 Agent 不是凭感觉拒绝，而是引用具体的规则文档和事实源

### 负面影响 / 代价

- 维护 Harness 本身需要成本——新增一类检查需要同时更新文档、脚本、测试
- 过度自动化可能阻碍快速原型（但 Harness 设计为可跳过的人工触发模式，不会阻塞探索）
- 如果检查脚本本身有 bug，可能产生误报（已通过 `run_all_checks.py` 统一入口缓解）

### 重新评估条件

1. **团队扩展到 3 人以上**：考虑引入 CI/CD Pipeline，在 PR 阶段自动运行 `run_all_checks.py`
2. **数据源扩展到 50 张表以上**：考虑引入 dbt 管理分层转换，Great Expectations 管理数据质量
3. **项目进入维护期（不再频繁新增表）**：简化 Harness，只保留回归测试
