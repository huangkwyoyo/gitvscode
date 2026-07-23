# DashVault 统一 Front Matter 规范

> doc_id: dashvault.spec.front-matter
> spec_version: 1.0.0
> review_status: draft
> publication_status: unpublished
> 拆分自：specs/document-lifecycle.md 第四节

---

## 四、统一 Front Matter 规范

### 4.1 核心原则

> 文档身份、修订版本、审查状态、发布状态、来源快照分别建模，禁止用单一字段混合表达。所有 Front Matter 必须有机器可执行的 JSON Schema 校验。

### 4.2 完整 Front Matter 模板

```yaml
---
# —— 逻辑文档身份（稳定不变）——
doc_id: "datadev.current-architecture"
doc_type: "current_architecture"
project_ids: ["datadev-v3"]

# —— 本次修订身份（每次生成唯一）——
revision_id: "01J3R7XK..."              # ULID，本次生成全局唯一
revision: 4                              # 修订序号，从 1 开始递增
previous_revision_id: "01J2ZZAB..."     # 被本次替代的 revision_id（原位更新时填写）
content_hash: "sha256:a1b2c3..."        # 正文内容哈希（不含 Front Matter）

# —— 审查与发布状态 ——
review_status: "draft"                   # draft | in_review | approved | rejected
publication_status: "unpublished"        # unpublished | published | superseded | retired | retracted

# —— 来源与权威 ——
provenance: "derived"                    # source | derived | synthesis | inferred
authority: "canonical_view"             # source_of_truth | canonical_view | reference
evidence_level: "supported"             # verified | supported | speculative
                                          # 注：此为文档默认值，正文内可逐声明标注

# —— 生成规范版本 ——
spec_id: "dashvault.spec.document-lifecycle"
spec_version: "1.0.0"
spec_content_hash: "sha256:d4e5f6..."
prompt_id: "prompt-current-architecture"
prompt_version: "1.0.0"
prompt_content_hash: "sha256:g7h8i9..."

# —— 来源快照（可多个项目）——
source_snapshots:
  - project_id: "datadev-v3"
    git_commit: "428d772f1a3b5c6d7e8f9a0b1c2d3e4f5a6b7c8d"  # 完整 40 位 SHA，禁止短 SHA
    git_root: "D:\\Program Files\\gitvscode"
    git_pathspec: "TianShu-DataDev-Agent-v3/"
    worktree_state: "dirty"              # clean | dirty | non_git
    worktree_hash: "sha256:9a0b1c2..."
    evidence_manifest: "_evidence/manifest-01J3R7XK.json"

# —— 生成元数据 ——
title: "DataDev Agent v3 当前架构"
generated_at: "2026-07-23T15:30:00+08:00"
dashvault_version: "0.1.0"
provider: "anthropic"
model: "claude-opus-4-8"
model_revision: "20250701"
run_id: "run-01J3R7XKAB..."

# —— 关联 ——
supersedes: null                         # 被本文档取代的逻辑 doc_id
superseded_by: null                      # 取代本文档的逻辑 doc_id
corrected_by: null                       # 纠错本文档的 doc_id
references: []
tags: []
reviewed_at: null
reviewed_by: null
---
```

### 4.3 字段分类与必填规则

#### 逻辑文档身份（必填）

| 字段 | 说明 |
|------|------|
| `doc_id` | 逻辑文档全局唯一标识，格式：`项目缩写.文档角色` |
| `doc_type` | 文档类型枚举，驱动 prompt 选择和规范引用 |
| `project_ids` | 关联项目 ID 列表，synthesis 类型可跨多个项目 |

#### 本次修订身份（必填）

| 字段 | 说明 |
|------|------|
| `revision_id` | ULID，本次具体生成结果的全局唯一标识 |
| `revision` | 该 `doc_id` 下的修订序号，从 1 递增 |
| `previous_revision_id` | 原位更新时填写被替代的 `revision_id`（`revision > 1` 时必填） |
| `content_hash` | 正文内容的 SHA-256 哈希 |

**规则：**
- `supersedes` 仅表达**逻辑文档**间的替代关系，不用于原位更新的修订追踪
- 不可变报告的 `doc_id` 必须含事件或时间身份（如 `phase-2-report`），多次报告通过独立 `doc_id` 区分

#### 审查与发布状态（必填）

| 字段 | 说明 |
|------|------|
| `review_status` | `draft` → `in_review` → `approved` \| `rejected` |
| `publication_status` | `unpublished` → `published` \| `superseded` \| `retired` \| `retracted` |

#### 来源与权威（必填）

| 字段 | 说明 |
|------|------|
| `provenance` | `source` \| `derived` \| `synthesis` \| `inferred` |
| `authority` | `source_of_truth` \| `canonical_view` \| `reference` |
| `evidence_level` | `verified` \| `supported` \| `speculative` |

#### 生成规范版本（必填）

| 字段 | 说明 |
|------|------|
| `spec_id` | 引用的规范 doc_id |
| `spec_version` | 规范的语义版本 |
| `spec_content_hash` | 生成时所依据的规范文件内容哈希 |
| `prompt_id` | 引用的 prompt 模板 doc_id |
| `prompt_version` | prompt 模板的语义版本 |
| `prompt_content_hash` | prompt 模板内容哈希 |

#### 来源快照（必填）

`source_snapshots` 支持多来源，单个快照结构：

| 字段 | 必填 | 说明 |
|------|------|------|
| `project_id` | ✅ | 注册表中的项目 ID |
| `git_commit` | ✅ | 完整 40 位 SHA，非 Git 项目用 `"non_git"` |
| `git_root` | ✅ | Git 仓库根路径 |
| `git_pathspec` | ✅ | 仓库内的项目路径限定 |
| `worktree_state` | ✅ | `clean` \| `dirty` \| `non_git` |
| `worktree_hash` | 仅 dirty | 工作区内容快照哈希 |
| `evidence_manifest` | ✅ | 指向该快照对应的证据清单文件 |

#### 关联字段（可选）

| 字段 | 说明 |
|------|------|
| `supersedes` | 被本文档取代的逻辑 doc_id |
| `superseded_by` | 取代本文档的逻辑 doc_id |
| `corrected_by` | 纠错本文档的 doc_id |
| `references` | 引用的其他 doc_id 列表 |
| `tags` | 标签列表 |
| `reviewed_at` | ISO 8601，未审查时为 null |
| `reviewed_by` | 审查人标识 |

### 4.3 附加：字段类型映射表

| YAML 字段 | JSON Schema type | Python type | 校验规则 |
|-----------|-----------------|-------------|---------|
| `doc_id` | `string (pattern)` | `str` | `^[a-z0-9-]+\.[a-z0-9_-]+$` |
| `doc_type` | `string (enum)` | `Literal[...]` | 见 4.4 枚举 |
| `project_ids` | `array[string]` | `list[str]` | minItems: 1 |
| `revision_id` | `string (pattern)` | `str` | ULID, 26 chars |
| `revision` | `integer` | `int` | minimum: 1 |
| `previous_revision_id` | `string \| null` | `str \| None` | — |
| `content_hash` | `string (pattern)` | `str` | `^sha256:[a-f0-9]{64}$` |
| `review_status` | `string (enum)` | `Literal[...]` | 见 3.5 节 |
| `publication_status` | `string (enum)` | `Literal[...]` | 见 3.5 节 |
| `role_status` | `string \| null (enum)` | `str \| None` | 见 3.5 节 |
| `provenance` | `string (enum)` | `Literal[...]` | 见 1.3 节 |
| `authority` | `string (enum)` | `Literal[...]` | 见 1.3 节 |
| `evidence_level` | `string (enum)` | `Literal[...]` | 见 1.3 节 |
| `spec_version` | `string (pattern)` | `str` | `^\d+\.\d+\.\d+$` |
| `git_commit` | `string (pattern)` | `str` | `^[a-f0-9]{40}$` 或 `"non_git"` |
| `generated_at` | `string (format)` | `str` | ISO 8601 |
| `last_generated_commit` | `string` | `str` | 40 位 hex 或 `""` 或 `"non_git"` |
| `last_published_commit` | `string \| null` | `str \| None` | — |

### 4.4 `doc_type` 枚举

```yaml
doc_type:
  - charter                     # 项目宪章
  - current_state               # 项目当前状态
  - current_architecture        # 当前架构
  - engineering_glossary        # 工程术语表
  - strategic                   # 完整战略文档
  - project_plan                # 项目规划书
  - phase_plan                  # 阶段规划
  - phase_report                # 阶段报告
  - adr                         # 架构决策记录
  - methodology                 # 方法论/指南
  - quick_reference             # 快速参考卡
  - retrospective               # 项目总结回顾
  - incident_report             # 事故复盘
  - experiment_log              # 实验记录
  - component_deep_dive         # 组件深度解析
  - pipeline_walkthrough        # 链路全览
  - change_summary              # 变更摘要
  - spec                        # 规范文档（DashVault 自身）
```

### 4.5 `doc_id` 命名规范

```
{项目缩写}.{文档角色}
```

| 项目 | 项目缩写 |
|------|---------|
| TianShu 数据仓库 | `tianshu` |
| TianShu-DataDev-Agent-v3 | `datadev` |
| TianShu-Text2SQL-Agent | `text2sql` |
| TianShu-Text2SQL-Lite | `text2sql-lite` |

示例：
```
datadev.current-architecture
datadev.engineering-glossary
datadev.adr-003-sql-compiler
text2sql.phase-2-report
tianshu.governance-review
```

### 4.6 文档引用协议

DashVault 内文档互相引用使用自定义 URI：

```markdown
[DataDev 工程术语表](dashvault://doc/datadev.engineering-glossary)
[AD-003 第 5 节](dashvault://doc/datadev.adr-003-sql-compiler#section-5)
[SqlBuildPlan 术语](dashvault://term/datadev.term.SqlBuildPlan)
[铁律 1](dashvault://rule/datadev.rule.001)
```

导出降级规则：

| 导出目标 | 降级方式 |
|---------|---------|
| Obsidian | URI 替换为本地文件相对路径 + doc_id 索引查找表 |
| GitHub/GitLab | URI 替换为仓库内相对文件路径 |
| 普通 Markdown 阅读器 | URI 替换为纯文本 `[标题]（参见：doc_id）` |

### 4.7 跨字段强制约束（JSON Schema 校验）

```yaml
# —— 状态转换约束 ——
# - 模型生成后必须为 draft + unpublished
# - published 要求 review_status == approved
# - retracted 要求 publication_status 原为 published

# —— 权威等级约束 ——
# - provenance:inferred → authority 禁止为 source_of_truth
# - provenance:source → 禁止 evidence_level: speculative
# - DashVault 生成文档 authority 不得为 source_of_truth
# - source_of_truth 仅用于源项目明确指定的权威文件索引

# —— 修订身份约束 ——
# - revision > 1 → previous_revision_id 必填
# - project_ids 长度 > 1 → provenance 必须为 synthesis

# —— 哈希格式约束 ——
# - 所有哈希字段前缀 sha256: 后跟 64 位十六进制字符
# - git_commit 为 40 位十六进制字符串或 "non_git"
```

### 4.8 机器校验要求

DashVault 必须提供 `schemas/front-matter.schema.json`，对每份生成文档的 Front Matter 执行：
1. 类型校验：所有字段类型、枚举值
2. 必填校验：必填字段非空
3. 跨字段约束：上节所有约束规则
4. 哈希格式校验
5. Git SHA 格式校验

### 4.9 版本兼容策略

Front Matter Schema 的演进遵循以下规则：

1. **新增字段**：必须为 optional（`required` 列表中不包含），默认值为 `null` 或合理默认值
2. **删除字段**：不能直接移除。流程：标记 deprecated（在 description 中注明）→ 保留一个完整版本周期 → 移除
3. **修改枚举值**：只能新增枚举值，不能删除或重命名已有枚举值
4. **修改 pattern**：只能放宽，不能收紧
5. **版本号规则**：
   - 新增 optional 字段 → 递增 PATCH（1.0.0 → 1.0.1）
   - 新增 doc_type 枚举值 → 递增 MINOR（1.0.0 → 1.1.0）
   - 删除字段或修改 required 列表 → 递增 MAJOR（1.0.0 → 2.0.0）

---
