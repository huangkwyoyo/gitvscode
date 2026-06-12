# TianShu 治理专项审查报告（Governance Review Report）

> **审查日期**：2026-06-12
> **审查范围**：Memory 治理、知识治理、Schema 治理、Harness 演进路线
> **审查人**：治理专项审查（多角色视角：首席架构师 / 知识治理负责人 / Agent Runtime 架构师 / Memory System Reviewer / 技术文档委员会主席）

---

## 执行摘要

TianShu 项目在工程执行层面已达到较高成熟度——9 个质量检查脚本、22 条经验记忆、5 份契约文件、4 层路由表、3 个 Agent 角色分工。**但在治理层面（长期可演进、可审计、可防污染）仍存在系统性缺口。**

### 核心发现

1. **Memory 治理**：当前只有"有没有写"和"写得好不好"的检查，缺少"写得对不对"的自动验证。错误记忆一旦进入系统，没有自动发现、自动通知下游、自动修复的闭环。
2. **知识治理**：发现 5 处知识重复、3 处内容冲突、5 个未定义概念。知识体系正在从"小而精"走向"大而乱"的临界点。
3. **Schema 治理**：存在 AI→文档→AI 的双向污染风险。数据库设计文档可以被 Agent 修改，而唯一的审核者也是 AI。
4. **Harness 演进**：当前处于 L3（团队级），具备向 L4（平台级）演进的基础，但关键维度（自动化触发、审计追踪、自愈能力、元治理）仍处于 L1-L2 水平。

### 建议优先级

**立即行动（P0，本周内）**：实现记忆事实置信等级、database_design 自动交叉验证、CODEOWNERS 机制、修复已发现的 3 处知识冲突。

**近期行动（P1，1 个月内）**：实现知识文档生命周期管理、Human Review 完整流程、结构化来源字段、引用计数。

**长期投资（P2，季度规划）**：可信度数值评分、治理仪表板、元治理自检、Harness 框架抽象。

---

## 第一部分：Memory 治理审查结果

### 1.1 能力矩阵

| 能力维度 | 状态 | 评分 | 关键发现 |
|---------|:----:|:---:|---------|
| 事实置信等级 | ❌ 缺失 | 0/5 | 无 Fact/Verified Fact/Assumption/Hypothesis 分级 |
| 来源追踪 | ⚠️ 部分 | 2/5 | 有自由文本字段，无结构化来源（文档/PR/Commit/人工） |
| 版本管理 | ❌ 缺失 | 0/5 | 无 v1/v2/v3 版本演进记录 |
| 撤销机制 | ⚠️ 部分 | 2/5 | 有 disputed→superseded 流程，但全手动，无自动通知 |
| 可信度评分 | ❌ 缺失 | 0/5 | 无 0-100 置信分数 |
| 写入门禁 | ✅ 成熟 | 4/5 | 有关联检查 + 内容质量校验（必填字段、长度、重复、来源） |
| 生命周期管理 | ⚠️ 部分 | 3/5 | 有 active/disputed/superseded/archived 状态机 |
| 防重复写入 | ✅ 成熟 | 4/5 | 有正文完全相同检测 |

### 1.2 关键风险

| 风险编号 | 描述 | 等级 |
|---------|------|:---:|
| GR-001 | 缺少事实置信等级——Agent 无法区分已验证事实和推测 | P0 |
| GR-002 | 无自动交叉验证——错误记忆可能潜伏数月 | P0 |
| GR-003 | 缺少写入冷却期——错误记忆立即对所有 Agent 可见 | P0 |
| GR-006 | 无下游自动通知——标记 disputed 后不知道影响了谁 | P0 |

### 1.3 修改方案概要

详见 `01_memory_governance.md`。核心改动：

1. **变更复盘模板**：增加 `置信等级`、`版本`、结构化来源字段（来源文档/PR/Commit/数据/人工确认/ADR）
2. **check_memory_update.py**：增加结构化来源验证、database_design 交叉验证、下游影响分析
3. **AGENTS.md**：增加 Agent 根据置信等级调整行为的规则
4. **经验复盘.md**：为现有 22 条条目补充置信等级和结构化来源字段

---

## 第二部分：知识治理审查结果

### 2.1 发现汇总

| 类别 | 数量 | 详情 |
|------|:---:|------|
| 知识重复 | 5 | DUP-01~05（见 `02_knowledge_governance.md` §2.1） |
| 内容冲突 | 3 | CON-01~03（含数据库文件名不一致的高危问题） |
| 未定义概念 | 5 | UND-01~05（含 Human Review 流程缺失的高危问题） |
| 潜在过期 | 4 | EXP-01~04 |
| AI 幻觉风险点 | 5 | HAL-01~05 |

### 2.2 关键风险

| 风险编号 | 描述 | 等级 |
|---------|------|:---:|
| CON-01 | 数据库文件名不一致（tian_shu.duckdb vs nyc_transport.duckdb） | **P0，已修复：`warehouse_connection.yml` 已统一指向 `nyc_transport.duckdb` 真实路径** |
| UND-01 | "可信等级（高/中/低）"被引用但从未定义 | **P0，已修复：`docs/standards/可信等级定义.md` 已创建** |
| UND-02 | "Human Review"是最常用标记但无完整流程 | **P0，已修复：`docs/governance/human_review_process.md` 已创建** |
| GR-004 | AGENTS.md 路由表无强制执行验证 | P0 |
| GR-010 | 契约文件无版本锁定 | P1 |
| GR-011 | ADR 无定期复审机制 | P1 |

### 2.3 修改方案概要

详见 `02_knowledge_governance.md`。核心改动：

1. **修复 CON-01**：统一为 `nyc_transport.duckdb`，`warehouse_connection.yml` 已指向真实 DuckDB 文件路径
2. **定义 UND-01~05**：已创建 `docs/governance/human_review_process.md`、`docs/standards/可信等级定义.md`，并在根 AGENTS.md 中补充相关读取和引用规则
3. **去重**：为每类知识确定权威源，其他文件只保留引用链接
4. **文档生命周期**：为所有 docs/ 文件增加 YAML frontmatter（日期、状态、复审周期）

---

## 第三部分：Schema 治理审查结果

### 3.1 双向污染风险评估

| 污染方向 | 当前风险等级 | 最薄弱环节 |
|---------|:----------:|-----------|
| Schema → 文档 → Agent（正向） | 中 | Agent 对 Schema 的理解可能错误 |
| Agent → 文档 → Schema（反向） | **高** | Agent 可修改 database_design，审核者也是 AI |

### 3.2 关键风险

| 风险编号 | 描述 | 等级 |
|---------|------|:---:|
| GR-005 | database_design 变更无强制人工审批——AI 可闭环修改 | **P0** |
| GR-014 | 缺少对 Agent 产出的真实性抽样审计 | P1 |

### 3.3 修改方案概要

详见 `03_schema_governance.md`。核心改动：

1. **CODEOWNERS**：锁定 `docs/warehouse/database_design/` 和 `contracts/`，要求指定人员审批
2. **pre-commit 增强**：检测 database_design、contracts、AGENTS.md、CODEOWNERS 等受保护路径变更，并以非交互方式提示必须进入 PR 审批；强制审批由 GitHub CODEOWNERS 承担
3. **冷却期机制**：对修改/删除字段的变更引入 24-72 小时冷却期
4. **溯源性增强**：`check_gold_design.py` 增加字段溯源完整性检查

---

## 第四部分：Harness 演进路线评估

### 4.1 当前评级

| 维度 | 等级 |
|------|:----:|
| 检查体系 | L3+ |
| 自动化触发 | L3 |
| 文档约束 | L3+ |
| 测试覆盖 | L3 |
| 记忆治理 | L3- |
| 审计追踪 | L2+ |
| 自愈能力 | L2 |
| 多 Agent 协作 | L3- |
| 元治理 | L1 |
| 跨项目复用 | L2 |
| **综合** | **L3（团队级）** |

### 4.2 演进路径

```
L3（当前）──── 2-3 周 ────→ L3+（补齐治理短板）
    │
    └──── 3 个月 ────→ L4（平台级：自动化触发、审计追踪、自愈能力）
                            │
                            └──── 6-12 个月 ────→ L5（企业级：联邦知识管理、元治理、全自动闭环）
```

### 4.3 修改方案概要

详见 `04_harness_evolution_roadmap.md`。三阶段共 25 项任务。

---

## 第五部分：P0/P1/P2 优先级汇总

### P0 — 必须立即修复（6 项）

| 编号 | 问题 | 修改方案 | 涉及文件 | 预计工作量 |
|:---:|------|---------|---------|:--------:|
| GR-001 | 缺少事实置信等级 | 新增置信等级字段和 Agent 引用规则 | 变更复盘模板、经验复盘、AGENTS.md | 已完成主体规则 |
| GR-002 | 无自动交叉验证 | check_memory_update.py 增加 database_design 交叉验证 | check_memory_update.py | 已完成初版，仍需降低误报 |
| GR-003 | 缺少写入冷却期 | 新增 proposed 状态，新记忆默认 proposed | 变更复盘模板、经验复盘 | 已完成规则定义 |
| GR-005 | database_design 无强制人工审批 | 创建 CODEOWNERS，增强 pre-commit | CODEOWNERS、.githooks/pre-commit | 已完成本地提示，PR 强制审批依赖 GitHub CODEOWNERS |
| CON-01 | 数据库文件名不一致 | 统一为 nyc_transport.duckdb | warehouse_connection.yml | 已完成 |
| UND-01/02 | 可信等级和 Human Review 未定义 | 创建定义文档 | 新建 2 份文档 | 已完成 |

**P0 合计工作量**：约 11.5 小时（1.5 个工作日）

### P1 — 建议尽快修复（8 项）

| 编号 | 问题 | 涉及文件 | 预计工作量 |
|:---:|------|---------|:--------:|
| GR-006 | 无下游自动通知 | 规则来源索引、check_memory_update.py | 4h |
| GR-007 | 缺少结构化来源字段 | 变更复盘模板、check_memory_update.py | 2h |
| GR-008 | 缺少版本号管理 | 变更复盘模板、经验复盘 | 2h |
| GR-009 | 缺少引用计数 | 规则来源索引 | 2h |
| GR-010 | 契约文件无版本锁定 | contracts/ 全部文件 | 1h |
| GR-011 | ADR 无定期复审 | docs/decisions/ | 2h |
| GR-012 | Human Review 无完整流程 | 新建 human_review_process.md | 3h |
| GR-013 | 知识文档无生命周期管理 | docs/ 全部文件 | 3h |

**P1 合计工作量**：约 19 小时（2.5 个工作日）

### P2 — 优化项（6 项）

| 编号 | 问题 | 预计工作量 |
|:---:|------|:--------:|
| GR-015 | 缺少可信度数值评分 | 2-3 天 |
| GR-016 | 缺少记忆图谱 | 1-2 天 |
| GR-017 | 缺少治理仪表板 | 3-5 天 |
| GR-018 | 配置文件无 schema 校验 | 0.5 天 |
| GR-019 | 缺少多 Agent 信息来源声明规范 | 1 天 |
| GR-020 | 缺少元治理自检 | 2-3 天 |

**P2 合计工作量**：约 10-15 天

---

## 第六部分：文件改动全景图

### 6.1 需新建的文件

| 文件 | 路径 | 内容 |
|------|------|------|
| Memory 治理设计 | `docs/governance/01_memory_governance.md` | ✅ 已生成 |
| 知识治理设计 | `docs/governance/02_knowledge_governance.md` | ✅ 已生成 |
| Schema 治理设计 | `docs/governance/03_schema_governance.md` | ✅ 已生成 |
| Harness 演进路线图 | `docs/governance/04_harness_evolution_roadmap.md` | ✅ 已生成 |
| 治理风险登记册 | `docs/governance/05_risk_register.md` | ✅ 已生成 |
| 治理审查报告 | `docs/governance/governance_review_report.md` | ✅ 本文件 |
| Human Review 流程 | `docs/governance/human_review_process.md` | ✅ 已创建 |
| 可信等级定义 | `docs/standards/可信等级定义.md` | ✅ 已创建 |
| CODEOWNERS | `CODEOWNERS` | ✅ 已创建 |
| 知识一致性检查 | `scripts/quality/check_knowledge_consistency.py` | 待创建（P2） |
| 治理仪表板 | `scripts/quality/governance_dashboard.py` | 待创建（P2） |

### 6.2 需修改的文件

| 文件 | 改动类型 | 优先级 | 说明 |
|------|---------|:-----:|------|
| `docs/memory/变更复盘模板.md` | 增强 | P0 | 增加置信等级、版本号、结构化来源字段 |
| `docs/memory/经验复盘.md` | 批量更新 | P0 | 为现有 22 条条目补充新字段 |
| `scripts/quality/check_memory_update.py` | 增强 | P0 | 增加结构化来源验证、交叉验证、下游影响分析 |
| `AGENTS.md` | 增强 | P0 | 增加置信等级引用规则、信息来源声明规范 |
| `contracts/warehouse_connection.yml` | 修复 | P0 | 数据库文件名统一，并指向真实 DuckDB 绝对路径 |
| `.githooks/pre-commit` | 增强 | P0 | 增加受保护路径变更检测；本地只做非交互提示，审批由 PR CODEOWNERS 承担 |
| `scripts/quality/check_gold_design.py` | 增强 | P0 | 增加溯源性完整性检查 |
| `docs/memory/规则来源索引.md` | 增强 | P1 | 增加反向索引（被引用者）列 |
| `contracts/*.yml`（5 个文件） | 增强 | P1 | 增加 version 和 last_reviewed 字段 |
| `docs/decisions/*.md`（6 个文件） | 增强 | P1 | 增加复审日期、更新状态 |
| `docs/` 下所有 .md 文件 | 批处理 | P1 | 增加 YAML frontmatter |
| `docs/warehouse/gold/AGENTS.md` | 修复 | P1 | 增加与 metric_contract.yml 的交叉引用 |
| `agents/text2sql/AGENTS.md` | 修复 | P1 | 明确 Silver 降级的前提条件 |

---

## 第七部分：诚实边界

### 7.1 本审查未覆盖的领域

- **性能治理**：检查脚本的执行效率、数据库查询性能
- **安全治理**：访问控制、敏感数据脱敏、密钥管理
- **成本治理**：LLM API 调用成本、存储成本
- **Agent Prompt 治理**：各 Agent 的系统提示词是否正确反映 AGENTS.md 规则

### 7.2 治理系统自身的局限性

1. **元治理悖论**：治理系统本身也是由 Agent 构建和修改的。谁审查治理系统的变更？当前答案是"人类"，但这是一个递归问题。
2. **规则膨胀风险**：随着经验记忆和规则的持续增长，AGENTS.md 的路由表会越来越长。Agent 的上下文窗口有限——某一天，路由表本身可能超出 Agent 的有效注意力范围。
3. **自动化 vs 人工的平衡**：过度自动化可能导致"垃圾进、垃圾出"的加速。过度依赖人工可能导致响应不及时。本报告的设计偏向"关键节点保留人工，常规检查自动执行"。

### 7.3 长期未解决的问题

- **多 Agent 协作的"知识一致性"问题**：当 3 个 Agent 同时工作，Agent A 修改了 database_design 而 Agent B 正在读取时，Agent B 可能基于过时信息做出决策。当前系统没有乐观锁或版本控制来解决此问题。
- **外部数据源的 Schema 漂移**：TianShu 依赖 NYC 开放数据，外部数据的 Schema 可能随时变化。当前系统没有外部 Schema 变化监控。

---

## 附录 A：治理文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| Memory 治理设计 | `docs/governance/01_memory_governance.md` | 事实等级、来源追踪、版本管理、撤销机制、可信度评分 |
| 知识治理设计 | `docs/governance/02_knowledge_governance.md` | 重复/冲突/未定义/过期/幻觉风险检测与修复 |
| Schema 治理设计 | `docs/governance/03_schema_governance.md` | 双向污染防护、强制人工审批、冷却期、溯源性增强 |
| Harness 演进路线图 | `docs/governance/04_harness_evolution_roadmap.md` | L3→L4→L5 成熟度模型、三阶段演进计划 |
| 治理风险登记册 | `docs/governance/05_risk_register.md` | 20 条治理风险（GR-001 ~ GR-020）及风险矩阵 |
| 治理审查报告 | `docs/governance/governance_review_report.md` | 本文件——P0/P1/P2 优先级汇总和修改方案 |

## 附录 B：与工程风险清单的关系

`docs/memory/风险清单.md`（RISK-001 ~ RISK-029）关注**工程执行风险**（数据会不会错）。

`docs/governance/05_risk_register.md`（GR-001 ~ GR-020）关注**治理系统风险**（体系能不能长期演进不被污染）。

两者的交集是 RISK-029（Agent 写错误记忆）——工程风险清单识别了此风险，治理风险登记册提供了系统性修复方案。

---

> **结论**：TianShu 在工程执行层面已经走得很远——9 个检查脚本、4 个测试模块、22 条经验记忆构成了坚实的质量基础。但**"防止 Agent 污染数据底座"的治理体系**仍处于早期阶段。P0 级别的 6 项修复是当前最紧迫的工作——它们直接关系到"记忆系统是否可信"、"Schema 是否安全"、"知识体系是否自洽"这三个核心命题。建议在本周内完成 P0 修复，使 TianShu 的治理能力从"被动响应"升级到"主动防护"。
