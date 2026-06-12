# 知识治理体系设计（Knowledge Governance）

> 确保 TianShu 的文档、规则、决策、规范构成一个自洽的知识体系，而非一堆相互矛盾的碎片。

---

## 1. 知识资产全景

### 1.1 知识资产清单

| 类型 | 位置 | 数量 | 治理状态 |
|------|------|:--:|---------|
| **架构决策记录（ADR）** | `docs/decisions/` | 6 | ⚠️ 全部标记 Accepted，无复审计划 |
| **分层规则文件** | `docs/warehouse/{layer}/AGENTS.md` | 4 | ✅ 结构清晰，有路由表 |
| **Agent 行为规则** | `agents/{role}/AGENTS.md` | 3 | ✅ 场景化清单，可执行 |
| **根规则文件** | `AGENTS.md` | 1 | ✅ 最高事实源，路由表完整 |
| **契约文件** | `contracts/` | 5 | ⚠️ 无版本号，无变更日志 |
| **数据库设计事实源** | `docs/warehouse/database_design/` | 3 | ✅ 分层清晰 |
| **字段字典** | `docs/warehouse/data_dictionary/` | 2 | ✅ 有枚举值说明 |
| **经验记忆** | `docs/memory/经验复盘.md` | 22 条 | ⚠️ 见 Memory 治理审查 |
| **风险清单** | `docs/memory/风险清单.md` | 29 条 | ✅ 含防线标注 |
| **规范索引** | `docs/standards/` | 2 | ✅ 职责边界明确 |
| **Harness 检查清单** | `harness/checklists/` | 3 | ⚠️ PR 审查清单较简略 |
| **标准问题集** | `harness/questions/` | 1 | ✅ 与语义层同步 |

### 1.2 知识流向图

```
数据库设计事实源（最高优先级）
    ↓ 约束
分层 AGENTS.md（各层规则）
    ↓ 约束
Agent 行为规则（agents/*/AGENTS.md）
    ↓ 约束
契约文件（contracts/）
    ↓ 约束
Agent 产出（SQL、建表、记忆写入）
    ↓ 反馈（踩坑后）
经验记忆（docs/memory/）
    ↓ 成熟后沉淀
AGENTS.md 规则 + 检查脚本 + 测试
```

---

## 2. 重复知识检测

### 2.1 发现的重复

| 编号 | 重复位置 A | 重复位置 B | 重复内容 | 严重度 | 建议 |
|------|-----------|-----------|---------|:-----:|------|
| DUP-01 | `AGENTS.md` §15 数据文档规范 | `docs/standards/数据仓库文档规范.md` | 中英文并列、字段类型规范 | 中 | 保留 AGENTS.md §15 为规范正文，standards/ 仅做索引链接 |
| DUP-02 | `docs/warehouse/gold/AGENTS.md` §6 指标必须包含 | `contracts/metric_contract.yml` | 指标必须包含的字段定义 | 中 | metric_contract.yml 作为机器可读版本，gold/AGENTS.md 作为人类可读版本——需在两者间增加交叉引用 |
| DUP-03 | `docs/warehouse/gold/AGENTS.md` §10 中文语义层 | `contracts/semantic_contract.yml` | G3 汇总表优先级和降级规则 | 中 | 同上——增加交叉引用 |
| DUP-04 | `docs/warehouse/gold/AGENTS.md` §9 金额字段关联规则 | `contracts/metric_contract.yml` 易混淆指标对照表 | 三种金额字段的口径说明 | 低 | 已有自然互补关系，但应显式交叉引用 |
| DUP-05 | `agents/text2sql/AGENTS.md` §8 跨表 JOIN 白名单 | `contracts/sql_safety_policy.yml` join_whitelist | 已核准的 JOIN 路径 | 中 | text2sql 版本更详尽（含说明列），sql_safety_policy 是机器可读版——需确保同步 |

**当前状态**：上述重复尚未导致实际冲突（内容一致），但维护负担已经存在——修改口径时需要同时更新 2-3 个文件。这是"知识分叉"的前兆。

### 2.2 去重策略

```
原则：每类知识只在一个地方是"权威正文"，其他地方只能是"引用或缓存"

实现方式：
1. 确定每个知识域的"权威源"（Source of Truth）
2. 其他文件只能包含指向权威源的链接
3. 契约文件（contracts/）作为"机器可读缓存"，在头部声明权威源路径
4. 在 check_knowledge_consistency.py（新建）中自动检测分叉
```

---

## 3. 冲突知识检测

### 3.1 发现的冲突

| 编号 | 位置 A | 位置 B | 冲突描述 | 严重度 | 建议 |
|------|--------|--------|---------|:-----:|------|
| CON-01 | `contracts/warehouse_connection.yml` | `PROJECT_STATUS.md` | 数据库文件名不一致：`tian_shu.duckdb` vs `nyc_transport.duckdb` | 高 | 统一为 `nyc_transport.duckdb`，更新 warehouse_connection.yml |
| CON-02 | `agents/text2sql/AGENTS.md` §2 数据源优先级 | `contracts/sql_safety_policy.yml` forbidden_joins | Text2SQL 说"Gold > Silver > Bronze"，sql_safety 说"只能查 Gold，禁止 Bronze/Silver" | 中 | Text2SQL 的 Silver 是降级方案（极少触发），sql_safety 的禁止是正确的硬约束。在 Text2SQL 中明确：Silver 降级仅限 Gold 完全不存在对应表时的最后手段，且必须经过人工确认 |
| CON-03 | `docs/warehouse/gold/AGENTS.md` §3 Gold 禁止做 | `docs/warehouse/silver/AGENTS.md` §3 Silver 禁止做 | 两个文件都声明了"禁止编造金额字段"，但责任边界模糊——当金额字段实际上来自 Bronze 时，应该放 Silver 还是 Gold？ | 低 | ADR-006 已解决此问题（金额放 Gold），但白银层禁止条款未引用此 ADR |

### 3.2 冲突处理规则

```
检测到冲突时的处理流程：

1. 标记冲突（在冲突双方文件中增加注释 "→ 与 XXX 存在潜在冲突，见 docs/governance/02_knowledge_governance.md#CON-XXX"）
2. 确定权威源（ADR 已决策 → 以 ADR 为准；未决策 → 发起新 ADR）
3. 更新非权威源（使其与权威源一致或增加交叉引用）
4. 注销冲突记录
```

---

## 4. 未定义概念检测

### 4.1 发现的未定义概念

| 编号 | 概念 | 出现位置 | 出现次数 | 严重度 | 问题 |
|------|------|---------|:------:|:-----:|------|
| UND-01 | `可信等级（高/中/低）` | `docs/warehouse/silver/AGENTS.md` §4.3 | 1 | 高 | 引用了但从未定义——什么算"高"？谁来判断？判断标准是什么？ |
| UND-02 | `Human Review` | 全项目（AGENTS.md、silver/AGENTS.md、gold/AGENTS.md、字段字典等） | 15+ | 高 | 作为最常用的标记，没有一个文件定义 Human Review 的完整流程 |
| UND-03 | `TianShu 数仓变更流程` | `contracts/question_policy.yml`、`contracts/sql_safety_policy.yml` | 2 | 中 | 契约文件引用了此流程但流程本身不存在于项目的任何文件中 |
| UND-04 | `审核流程` | 根 `AGENTS.md` §0（"全局表字段变更应由独立项目或独立模块维护"） | 1 | 中 | 提到"审核流程"但未定义具体步骤、审核人、时限 |
| UND-05 | `Agent 语义层` | `docs/warehouse/AGENTS.md` §2（"Bronze → Silver → Gold → Agent语义层"） | 1 | 低 | Agent 语义层到底是什么？是 `contracts/semantic_contract.yml`？是 `meta.*` 表？是 Text2SQL Agent 的上下文？ |

### 4.2 定义补全计划

| 概念 | 定义位置 | 内容要求 |
|------|---------|---------|
| 可信等级 | `docs/standards/` 新建 `可信等级定义.md` | 定义高/中/低的具体判定标准、示例、使用场景 |
| Human Review | `docs/governance/` 新建 `human_review_process.md` | 触发条件、指派规则、时限、升级路径、关闭标准 |
| TianShu 数仓变更流程 | 根 `AGENTS.md` §13 扩展或新建独立文档 | 变更类型分类、审批流、门禁、回滚机制 |
| 审核流程 | 根 `AGENTS.md` §0 扩展 | 谁审核、审核什么、多长时间、审核不通过怎么办 |
| Agent 语义层 | `agents/text2sql/AGENTS.md` 或 `docs/warehouse/gold/AGENTS.md` §10 扩展 | 明确定义其组成（契约 + meta 表 + 标准问题集） |

---

## 5. 过期知识检测

### 5.1 发现的潜在过期知识

| 编号 | 文件/位置 | 内容 | 疑似过期原因 | 严重度 | 建议 |
|------|----------|------|------------|:-----:|------|
| EXP-01 | `docs/silver/Silver白银层规划.md` | Silver 表规划 | 11 张表已全部建成，规划文档可能未与实际对齐 | 中 | 检查规划与实际是否一致，如不一致则更新或标注"规划已完成" |
| EXP-02 | `docs/decisions/003-silver-three-batch-strategy.md` | Silver 三批建设策略 | Silver 已全部建成，三批策略已完成使命 | 低 | 标记为 "Implemented"（已实施），保留作为历史参考 |
| EXP-03 | `docs/decisions/004-primary-key-strategy.md` | 主键策略 | R007 记录了 MD5 碰撞问题，可能需要对策略进行补充决策 | 中 | 检查 ADR-004 是否需要补充关于 MD5 碰撞的经验 |
| EXP-04 | `PROJECT_STATUS.md` 下一步 | 17 项全部标记 `[x]` | "下一步"已经全部完成，但项目还在继续 | 低 | 更新为新的下一步计划，或改为"下一阶段" |

### 5.2 过期知识处理规则

```
1. 文档头部增加 YAML frontmatter：
   ---
   created: 2026-06-07
   updated: 2026-06-12
   status: active | implemented | superseded | deprecated
   review_cycle: 90d
   next_review: 2026-09-10
   ---

2. 状态含义：
   - active：当前有效，维护中
   - implemented：决策或计划已执行完毕，保留作为历史参考
   - superseded：被新文档取代（标注取代者）
   - deprecated：已废弃，不再适用

3. 自动检测：check_knowledge_consistency.py 识别超过复审周期未更新的文档
```

---

## 6. AI 幻觉风险点

### 6.1 高风险幻觉场景

| 编号 | 场景 | 风险描述 | 当前防线 | 额外建议 |
|------|------|---------|---------|---------|
| HAL-01 | Agent 根据常识补充字段含义 | Agent 看到 `PULocationID` 可能推测为"上车地点 ID"而非"PULocationID 对应的出租车区域编号" | §3 零幻觉原则 | 在数据字典中为每个缩写字段增加"禁止推测"标注 |
| HAL-02 | Agent 编造 Join 关系 | Agent 看到两个表都有 `location_id` 就假设可以 JOIN | text2sql/AGENTS.md §8 JOIN 白名单 | 在 sql_safety_policy.yml 中增加"不在白名单中的 JOIN 默认禁止"的硬规则（已部分实现） |
| HAL-03 | Agent 填充缺失字段 | Agent 发现 Silver 缺少某字段，自行从 Bronze "推测"添加 | silver/AGENTS.md §3 禁止新增字段 | 在 Dev Agent 执行清单 §5 禁止行为中增加"禁止基于推测补充字段" |
| HAL-04 | Agent 翻译缩写 | Agent 将 `HDR`、`PDR` 等缩写直接翻译为中文而不查数据字典 | gold/AGENTS.md §4 中文名规则 | 已覆盖——需强化执行 |
| HAL-05 | Agent 解释指标口径 | Agent 在 Text2SQL 中自行解释"金额"的含义而不追问 | question_policy.yml must_clarify | 已覆盖——需确保 Agent 真的读了此文件 |

### 6.2 幻觉预防机制完善建议

1. **"先查后说"原则**：Agent 在输出任何字段含义、Join 关系、指标口径前，必须先引用信息来源（哪份文档、哪个表、哪个 DESCRIBE 结果）
2. **不确定性声明**：Agent 在不确定时，必须显式声明不确定等级（"确定存在"、"高置信度"、"推测——需人工确认"、"无法确认"）
3. **反幻觉抽样审计**：定期随机抽取 Agent 产出，由 Review Agent 或人工验证是否存在幻觉

---

## 7. 知识治理健康度指标

| 指标 | 计算方式 | 目标值 | 当前值 |
|------|---------|--------|-------|
| 知识重复度 | 存在交叉引用的重复知识对数量 | 0（只有引用，没有重复） | 5（DUP-01~05） |
| 知识冲突数 | 内容矛盾的文档对数量 | 0 | 3（CON-01~03） |
| 未定义概念数 | 被引用但未定义的概念数量 | 0 | 5（UND-01~05） |
| 过期文档数 | status ≠ active 的文档数 / 总文档数 | < 10% | 约 5%（估算） |
| 文档更新及时度 | 近 30 天内更新的文档比例 | > 70% | 约 80%（近期活跃） |
| 交叉引用完整度 | 有交叉引用的关联文档对 / 应有交叉引用的文档对 | 100% | 约 40%（估算） |
| Human Review 积压 | 标记 Human Review 但超过 30 天未处理的条目数 | 0 | 未知 |

---

## 8. 实现路线图

### Phase 1：紧急修复（1-2 周）

| 任务 | 优先级 |
|------|:-----:|
| 修复 CON-01：统一数据库文件名 | P0 |
| 定义 UND-01~05：为所有未定义概念创建正式定义 | P0 |
| 为所有知识文档增加 YAML frontmatter（日期、状态、复审周期） | P0 |

### Phase 2：结构优化（2-3 周）

| 任务 | 优先级 |
|------|:-----:|
| 实施去重策略：确定每个知识域的权威源，消除重复维护 | P1 |
| 建立冲突检测和处理流程 | P1 |
| 建立 Human Review 完整流程文档 | P1 |
| 为契约文件增加版本号和变更日志 | P1 |

### Phase 3：持续治理（长期）

| 任务 | 优先级 |
|------|:-----:|
| 创建 `check_knowledge_consistency.py` 自动检测知识分叉、过期、冲突 | P2 |
| 建立知识文档复审日历（ADR 每季度、AGENTS.md 每月、契约文件每次变更） | P2 |
| 定期反幻觉抽样审计 | P2 |
