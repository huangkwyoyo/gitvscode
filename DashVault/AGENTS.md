# AGENTS.md

## 第一性原理

DashVault 的唯一存在理由：**让各个 Agent 项目成为你学习 Agent 工程的助力文档，从新手入门到精通。**

它通过观察你亲手构建的每一个 Agent 项目，提取其中沉淀的设计决策、架构演进、踩坑经验和工程方法论，转化为结构化、可检索、带来源证据的知识文档——而不是让你去读别人的教程。

```
源项目（你的 Agent 项目）
    ↓ 只读采集（Git 历史 + 当前状态）
DashVault（跨项目知识层）
    ↓ 自动生成/更新 MD 知识文档
面（全局）→ 战略、架构、回顾
线（阶段）→ 阶段规划、阶段报告、ADR
点（具体）→ 术语表、方法论、快速参考
    ↓ 前端浏览 + NL 驱动查询
你（从新手 → 精通）
```

## 角色定义

DashVault 是一个**跨项目、只读采集、带来源证据的派生知识层**。它是观察者，不是管理者。

---

## 项目边界

边界是 DashVault 的最高行为准则。以下每一条边界在设计文档中都有对应的技术实现，不可逾越。

### 1. 数据边界——能读什么、不能读什么

| 可以读 | 禁止读 |
|--------|--------|
| 源项目的 Git 受控文件（`git ls-files` 白名单内） | `.env`、`.env.*` — 环境变量和密钥 |
| AGENTS.md、CLAUDE.md、契约文件 | `logs/`、`llm_responses/`、`llm_reports/` — LLM 原始输出 |
| `docs/` 目录下的 Markdown 文档 | `.venv/`、`node_modules/`、`__pycache__/` — 依赖和构建产物 |
| Git 提交历史（commit message、diff） | `generated/`、`.pytest_cache/`、`.pytest_tmp/` — 临时文件 |
| 工作区未提交变更（按需） | `*.pyc`、`*.pkl`、`*.zip` — 二进制文件 |
| Obsidian 知识库中的 Markdown 文件 | 源项目的 Memory 目录（除非源项目 AGENTS.md 明确允许） |

**强制排除列表在 scanner-spec 中定义，项目级 `exclude_rules` 只能追加不能覆盖。**

### 2. 治理边界——尊重源项目的独立性

```
DashVault 绝不以任何形式：
├── 写入或修改源项目的任何文件
├── 宣称自己是源项目的事实源（authority 不得为 source_of_truth）
├── 绕过源项目的 Memory Gate 或 Human Review 流程
├── 替源项目建立其明确拒绝的术语表或 Memory
├── 向源项目强制其未采纳的治理模型
└── 覆盖或干扰源项目自身的 docs/memory/ 目录
```

四个已注册源项目的治理模式差异：

| 项目 | 治理特征 | DashVault 的边界约束 |
|------|---------|---------------------|
| TianShu | DB 设计是唯一事实源，新记忆先入 proposed | 不覆盖 `docs/memory/` |
| DataDev-Agent-v3 | 明确不建设独立 Engineering Memory | 不替它建术语表 |
| Text2SQL-Lite | 刻意剥离重型 Memory | 不反向加回 Memory Gate |
| Text2SQL-Agent | 有阻断性文档目录和 Memory Gate | 不绕过其门禁写入 |

### 3. 权威边界——派生知识的硬上限

DashVault 生成的所有文档，`authority` 字段最高为 **`canonical_view`**（规范视图），永远不能为 **`source_of_truth`**（事实源）。

```
权威等级（从高到低）：
  source_of_truth  ← 仅源项目自身可达，DashVault 禁止
  canonical_view   ← DashVault 生成文档的最高权威
  reference        ← 仅供参考的文档默认权威
```

**跨字段约束（JSON Schema 强制校验）：**
- `provenance: inferred` → 禁止 `authority: source_of_truth`
- `provenance: source` → 禁止 `evidence_level: speculative`
- `project_ids` 长度 > 1 → 必须 `provenance: synthesis`
- `revision > 1` → 必须填写 `previous_revision_id`

### 4. 安全边界——六阶段硬门禁

从自然语言到文件落盘，必须经过六阶段，任何阶段失败则中止：

```
NL 输入
 → 阶段 1：意图解析（结构化 Intent，不阻断，仅标记模糊点）
 → 阶段 2：范围解析（项目可达性、文件可读性、token 上限——任一失败则中止）
 → 阶段 3：操作计划（用户必须显式确认，30 分钟超时）
 → 阶段 4：文档生成（Scanner 采集 → Claude API → 输出 Schema 校验）
 → 阶段 5：一致性检查（结构/引用/事实/证据/安全 五道硬门禁）
 → 阶段 6：确认发布（Diff 预览 + 人工确认 + 原子写入）
 → 文件落盘
```

**硬门禁 = 任何失败立即中止，禁止降级绕过。软门禁在此项目中不存在。**

双层安全模型：

| 层级 | 机制 | 说明 |
|------|------|------|
| **应用层** | `GenerationSandbox` 数据类 | Python 约束声明，自文档化——不是真正的安全边界 |
| **OS 层** | 进程隔离 + 文件系统 ACL + 动作白名单 | 真正的安全边界——generator.py 进程无 shell、无额外文件写入 |

### 5. 技术边界——硬性限制

| 限制项 | 值 | 越界处理 |
|--------|-----|---------|
| 单文件最大尺寸 | 1 MB | 跳过，记录 `files_skipped` |
| 单次最多文件数 | 500 | 分批采集 |
| 禁止二进制 | 文件头魔数检测 | 跳过 |
| 单次 LLM 调用 token 上限 | 评估阶段 2 预估 | 超出则建议缩小范围 |
| HTTP 超时 | 120 秒 | 抛出 `AdapterError` |
| 最大输出 token | 8192 | Adapter 层限制 |
| 非 UTF-8 编码 | latin-1 回退 | 失败则跳过 |
| 磁盘 IO 错误 | 重试 2 次 | 仍失败则中止 |
| 路径遍历攻击 | `os.path.normpath` + 前缀校验 | 抛出 `PathTraversalError` |
| 符号链接 | 不跟随 | 记录但标记 `is_symlink: true` |

### 6. 存储边界——读写范围

**只写以下目录：**
- `DashVault/docs/{project_id}/` — 生成的文档
- `DashVault/_evidence/` — 证据清单（运行时生成，不提交 Git）

**只读以下目录：**
- 已注册源项目的 Git 受控文件
- `DashVault/prompts/` — Prompt 模板
- `DashVault/specs/` — 自身规范

**不写也不读：**
- 源项目的 `.git/` 内部对象
- 源项目的 `.env`、密钥文件
- 源项目的 `_audit/`、`_evidence/`、`generated/`

### 7. 触发边界——何时生成、何时不生成

| 触发方式 | 行为 |
|---------|------|
| 前端手动触发 | 完整六阶段流水线 |
| CLI 命令 | 跳过阶段 1（NL 解析），保留阶段 2-6 |
| Git push 自动触发 | 不在 Phase 0 范围 |
| 定时任务 | 不在 Phase 0 范围 |

**不触发生成的情况：**
- 源项目自身修改文件时——DashVault 被动响应，不主动监听
- 文档 `review_status` 为 `draft` 时——不进入发布流程
- 项目 `scan_mode: directory`（非 Git）——不追踪 commit

---

## 能力边界

### 能做
- 读取已注册项目的 Git 历史和受控文件
- 基于源项目证据生成派生的知识文档（authority ≤ `canonical_view`）
- 维护跨项目的术语表、架构视图和方法论库
- 以只读方式浏览项目文档树（前端 + CLI）
- 通过自然语言指定项目、知识点、文档类型，生成或更新文档
- 为每条声明附带证据标注块（来源路径、行号、可信等级）

### 不能做
- 修改源项目的任何文件（AGENTS.md、契约、Memory、状态文档）
- 宣称自己是任何项目的事实源（`authority` 禁止为 `source_of_truth`）
- 绕过源项目的治理模型（Memory Gate、Human Review 等）
- 读取源项目的 `.env`、密钥、日志、LLM 原始响应
- 在用户未确认操作计划的情况下写入任何文件
- 对源项目执行 shell 命令或启动子进程
- 跟踪或记录用户在 DashVault 前端以外的浏览行为

---

## 核心规范

所有设计规范位于 `specs/` 目录（固定路径，无时间戳）：

| 文件 | 内容 |
|------|------|
| `specs/document-lifecycle.md` | 核心设计文档：事实源与文档生命周期 |
| `specs/registry-spec.md` | 项目注册信息规范 |
| `specs/scanner-spec.md` | Scanner 详细规范（含安全约束） |
| `specs/prompt-spec.md` | Prompt 模板编写规范 |
| `specs/front-matter-spec.md` | 统一 Front Matter 规范（含 JSON Schema 约束） |
| `specs/evidence-spec.md` | 证据标注规范 |
| `specs/document-roles.md` | 底层文档角色定义 |

## 学习路径与文档角色映射

| 学习阶段 | 对应文档角色 | 说明 |
|---------|-------------|------|
| **入门** | `engineering_glossary`、`quick_reference`、`methodology` | 理解领域术语、掌握核心方法 |
| **实践** | `phase_plan`、`phase_report`、`adr` | 跟着阶段走，理解决策过程 |
| **贯通** | `current_architecture`、`strategic` | 理解系统全局结构和设计思想 |
| **精通** | `retrospective`、`change_summary` | 跨项目复盘，形成方法论体系 |

## 强制前置阅读

Agent 启动时必须读取的核心文件：
1. `specs/document-lifecycle.md` — 了解项目定位和架构
2. `AGENTS.md` — 本文档（边界定义）

## 代码规范

- 所有注释使用中文，解释"为什么"而非"是什么"
- 函数/类使用简短的中文 docstring

## 当前状态

**Phase 0（规范闭环）已完成。** 7 个规范文件 + JSON Schema + 10 个校验测试全部就绪。Phase 1 进入业务代码开发。

```bash
# 运行测试验证
cd DashVault && pytest tests/ -v  # 当前 10 passed
```
