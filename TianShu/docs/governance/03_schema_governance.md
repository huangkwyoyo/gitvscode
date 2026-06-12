# Schema 治理体系设计（Schema Governance）

> 保护 TianShu 的数据库 Schema 不被 Agent 双向污染——确保 Schema → 文档 → Agent → 文档 → Schema 的闭环中有足够的安全阀。

---

## 1. 双向污染风险分析

### 1.1 正向污染链路（Schema → 文档 → Agent）

```
DuckDB 实表 Schema（Bronze/Silver/Gold）
    ↓ Agent 读取（DESCRIBE / SELECT）
Agent 理解
    ↓ Agent 写入
数据库设计文档（docs/warehouse/database_design/）
    ↓ Agent 读取
Agent 后续决策
```

**风险**：Agent 可能错误理解 DuckDB Schema（如将 FLOAT 当作 DECIMAL、将代理键当作业务键），并将错误理解写入文档，形成污染。

**当前防线**：
- `check_schema_consistency.py` 检查文档与 DuckDB 实表的一致性 ✅
- Review Agent §2.5 一致性检查 ✅

**缺口**：Agent 对 Schema 的"理解"环节没有验证——Agent 可能正确读取了字段名但错误理解了字段含义。

### 1.2 反向污染链路（Agent → 文档 → Schema）

```
Agent 决策（基于记忆、训练知识或推测）
    ↓ Agent 写入
数据库设计文档（docs/warehouse/database_design/）
    ↓ Dev Agent 读取并建表
DuckDB 实表 Schema
    ↓ 后续 Agent 读取
错误 Schema 被当作事实
```

**风险**：这是 TianShu 当前最危险的污染路径。Agent 修改数据库设计文档后，如果 Review Agent 未拦截或人类未仔细审查，错误 Schema 会通过 Dev Agent 的建表操作进入 DuckDB。

**当前防线**：
- Dev Agent 必须遵循场景 A/B 清单，先更新设计文档再建表
- Review Agent §2.5 一致性检查
- `check_schema_consistency.py` 检查文档与实表一致性
- `check_gold_design.py` 检查 Gold 设计文档字段来源

**缺口**：
- 没有强制人工审批节点（Review Agent 是 AI，可以漏过）
- 没有"设计文档变更 → 实表变更"之间的 cooling period
- 没有对设计文档变更的差异审计（改了什么、为什么、谁批准）

---

## 2. 当前 Schema 变更路径审计

### 2.1 变更路径图谱

```
┌──────────────────────────────────────────────────────────────┐
│                       Schema 变更路径                          │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  路径 A（正常路径）：                                          │
│  人工修改设计文档 → PR → Review Agent → 人工合入 → Dev Agent 建表 │
│  ✅ 此路径有人工介入，风险可控                                   │
│                                                               │
│  路径 B（Agent 主动路径）：                                     │
│  Dev Agent 修改设计文档 → Review Agent → 人工合入 → Dev Agent 建表│
│  ⚠️ 设计文档的修改者是 AI，审核者也是 AI，人类可能只是点"合入"     │
│                                                               │
│  路径 C（静默路径——当前不存在但需要防范）：                      │
│  Agent 直接执行 DDL（当前被 sql_safety_policy.yml 禁止）         │
│  ✅ 已有防线，但需确保连接确实是 read_only                        │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 路径 B 的具体风险场景

**场景**：Dev Agent 在场景 B（修改已有表字段）中：

1. Dev Agent 读取需求："给 fact_parking_violations 增加一个 payment_status 字段"
2. Dev Agent 在 database_design 中新增了字段定义
3. Dev Agent 修改了 build_gold_duckdb.py 的建表 SQL
4. Review Agent 检查：字段有来源吗？有。字段名合规吗？是。通过。
5. 人类看到 PR 标题"新增 payment_status 字段"，点合入。
6. **但 payment_status 在 Bronze 中并不存在**——Agent 基于训练知识推测的。

**后果**：虚假字段进入 Gold 事实表 → 所有下游分析引用此字段 → 发现真相后，已经有一条依赖链。

### 2.3 当前防线是否足够？

| 防线 | 能拦截上述场景吗？ | 为什么 |
|------|:----------------:|--------|
| `check_gold_design.py` | ⚠️ 部分 | 检查 Silver 来源字段是否真实存在，但如果 Agent 将来源标注为 `derived` 并写了一个看似合理的计算逻辑，可能通过 |
| Review Agent §2.2 字段来源合规 | ⚠️ 部分 | 能检测明显的问题（来源字段不存在），但不能检测"派生逻辑本身是假的" |
| 人类 PR 审批 | ⚠️ 取决于人类 | 如果人类只是快速浏览标题，可能漏过 |
| pre-commit hook | ❌ 不能 | 不检查 database_design 的变更内容 |

**结论**：当前防线不能保证拦截所有反向污染。需要增加额外的安全阀。

---

## 3. Schema 治理机制设计

### 3.1 强制人工审批节点（Human Approval Gate）

#### 3.1.1 CODEOWNERS 机制

创建 `CODEOWNERS` 文件，对关键 Schema 文件设置强制人工审批：

```gitattributes
# TianShu CODEOWNERS
# 数据库设计文档的变更必须由指定人员审批

docs/warehouse/database_design/    @data-architect
contracts/                         @data-architect
docs/warehouse/gold/AGENTS.md      @data-architect
docs/warehouse/silver/AGENTS.md    @data-architect
```

#### 3.1.2 pre-commit 增强

在 pre-commit hook 中增加"受保护路径变更检测"。本地 hook 不做交互式人工确认，也不检查 PR 审批状态，因为 pre-commit 发生在 PR 创建之前，无法可靠判断 CODEOWNERS 是否已审批。

本地 hook 的职责：

1. 检测 `docs/warehouse/database_design/`、`contracts/`、根 `AGENTS.md`、`CODEOWNERS` 等受保护路径是否变更。
2. 以非交互方式提示这些变更必须进入 PR 审核。
3. 继续执行 Memory Gate、危险模式扫描和回归测试。

强制审批由 GitHub PR 层的 CODEOWNERS 承担；本地 hook 只负责早提醒和跑检查，避免卡住 CI、Codex、Claude Code 或自动化提交脚本。

### 3.2 Schema 变更冷却期（Change Cooling Period）

#### 3.2.1 分级冷却期

| 变更类型 | 冷却期 | 说明 |
|---------|:-----:|------|
| 新增表（G3 汇总表） | 0 天 | 不阻塞快速迭代 |
| 新增字段（非关键表） | 0 天 | 同上 |
| 修改已有字段类型 | 24 小时 | 给下游消费者反应时间 |
| 修改已有字段含义/口径 | 48 小时 | 需要更多审查时间 |
| 删除字段 | 72 小时 | 最大冷却期，需确认所有下游已适配 |
| 修改 G0/G1 维表（dim_date、dim_taxi_zone 等） | 72 小时 | 维表变更影响全域 |

#### 3.2.2 冷却期实现

在 database_design 文档中为待生效的变更增加 `status: proposed` 标记：

```markdown
## fact_parking_violations

| 字段名 | 类型 | 说明 | 状态 |
|--------|------|------|------|
| issue_date_key | INTEGER | 开票日期键 | active |
| payment_status | VARCHAR(20) | 支付状态（来源：TBD） | proposed（2026-06-13 生效） |
```

`check_schema_consistency.py` 在冷却期内跳过 `proposed` 字段。

### 3.3 设计文档变更差异审计（Change Audit Trail）

#### 3.3.1 审计日志

每次 database_design 变更必须在 commit message 中包含：

```
schema-change: fact_parking_violations
change-type: add-field
field: payment_status
source: silver.tif_payment_detail.payment_status
reviewed-by: 张三
reason: 支持按支付状态分析罚单
```

#### 3.3.2 自动化审计报告

在 `check_schema_consistency.py` 中增加 `--audit` 模式，输出自上次审计以来的所有 Schema 变更：

```
Schema 变更审计报告（2026-06-01 → 2026-06-12）
================================================
新增表：1（dws_daily_parking_summary）
新增字段：3（fact_parking_violations.standard_fine_amount, fine_source_status, ...）
修改字段：0
删除字段：0
未通过审批的变更：0
冷却期中的变更：0
```

### 3.4 字段来源可追溯性增强

#### 3.4.1 字段溯源链

每个字段必须可以沿以下链条完整追溯：

```
Gold 字段 → Silver 来源字段 → Bronze 原始字段 → 原始数据文件
```

当前已部分实现（Silver AGENTS.md §4 要求标注来源），但 Gold 层没有强制要求每个字段标注 Silver 来源。

#### 3.4.2 自动化溯源性检查

在 `check_gold_design.py` 中增加"溯源性完整性"检查：
- 每个 Gold 字段是否标注了 Silver 来源字段
- Silver 来源字段是否在 silver_database_design.md 中真实存在
- Silver 来源字段是否可追溯到 Bronze
- 不能完整追溯的字段标记为 `source_trace: broken`

---

## 4. Schema 只读保护机制

### 4.1 当前只读保护

| 保护层 | 机制 | 状态 |
|--------|------|:---:|
| DuckDB 连接 | `read_only=True`（warehouse_connection.yml） | ✅ |
| SQL 安全策略 | 禁止 DML/DDL/DCL（sql_safety_policy.yml） | ✅ |
| Text2SQL Agent | 禁止写操作（question_policy.yml） | ✅ |
| Dev Agent | 受控建表流程（dev/AGENTS.md 场景 A/B） | ⚠️ 依赖 Agent 自律 |

### 4.2 增强建议

1. **生产数据库与开发数据库分离**：Dev Agent 只能操作开发库，生产库的 Schema 变更必须通过人工执行的迁移脚本
2. **Schema 快照**：每次 Schema 变更后自动生成快照（SQL DDL 导出），存储在 `sql/{schema}/snapshots/`
3. **Schema 回滚能力**：保留所有 DDL 快照，支持回滚到任意历史版本

---

## 5. Schema 治理健康度指标

| 指标 | 计算方式 | 目标值 | 当前值 |
|------|---------|--------|-------|
| 字段溯源性 | 可完整追溯到 Bronze 的字段比例 | 100% | 约 95%（部分 derived 字段溯源链不完整） |
| 未审批变更 | 未经人工审批的 database_design 变更数（近 30 天） | 0 | 未知 |
| Schema 与文档一致性 | check_schema_consistency.py 通过率 | 100% | ✅ 100% |
| 跨层引用完整性 | Gold 字段在 Silver 中有来源标注的比例 | 100% | 约 90%（估算） |
| 设计文档 proposed 字段 | 处于 proposed 状态超过冷却期的字段数 | 0 | 0（当前无此机制） |
| Schema 快照覆盖率 | 有 DDL 快照的表数 / 总表数 | 100% | 0%（当前无此机制） |

---

## 6. 实现路线图

### Phase 1：紧急防线（1 周）

| 任务 | 优先级 |
|------|:-----:|
| 创建 CODEOWNERS 文件，锁定 database_design 和 contracts | P0 |
| 增强 pre-commit hook，检测 database_design 变更 | P0 |
| 增强 check_gold_design.py，增加溯源性完整性检查 | P0 |

### Phase 2：机制完善（2-3 周）

| 任务 | 优先级 |
|------|:-----:|
| 实现分级冷却期机制 | P1 |
| 实现 Schema 变更审计报告（--audit） | P1 |
| 实现 Schema 快照和版本管理 | P1 |

### Phase 3：平台化（长期）

| 任务 | 优先级 |
|------|:-----:|
| 生产库与开发库分离 | P2 |
| 自动化 Schema 回滚 | P2 |
| Schema 变更影响分析（自动检测下游依赖） | P2 |
