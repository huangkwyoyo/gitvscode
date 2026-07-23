# DashVault 证据标注规范

> doc_id: dashvault.spec.evidence
> spec_version: 1.0.0
> review_status: draft
> publication_status: unpublished
> 拆分自：specs/document-lifecycle.md 第五节

---

## 五、证据标注规范

### 5.1 核心原则

> `evidence_level` 在 Front Matter 中是文档默认值，正文内每条关键声明必须独立标注证据来源和强度。无法验证的推断必须可见地标记为"推断"或"待确认"，不得伪装为事实。

### 5.2 证据强度（逐声明标注）

| 级别 | 含义 | 判定标准 |
|------|------|---------|
| `verified` | 已通过验证 | 有源文件内容哈希匹配 + 可复现的测试/门禁结果 |
| `supported` | 有证据支撑 | 有明确的源文件路径和 commit，但未经独立验证 |
| `inferred` | 模型推断 | 基于现有证据的合理推断，但无直接来源 |
| `unconfirmed` | 尚未确认 | 模型生成后标注，需人工补充证据或降级为推断 |

与 Front Matter 中 `evidence_level` 的关系：
- Front Matter 的 `evidence_level` = 本文档中所有声明的**最低**证据强度
- 正文内每条声明可标注**更高**的证据强度
- 一份文档可出现 `verified`、`supported`、`inferred` 三种声明并存
- 正文内出现 `inferred` 或 `unconfirmed` → Front Matter `evidence_level` 不得高于它们中的最低值

### 5.3 正文内证据标注语法

每条关键声明后紧跟证据标注块，使用 `> ` blockquote + `🧾` 前缀：

```markdown
SQL 编译器使用 DuckDB 方言作为编译目标，通过 SqlBuildPlan 的 10
种封闭步骤类型生成 SQL，LLM 不直接输出 SQL 字符串。

> 🧾 **证据**
> - 来源：`src/compiler/duckdb_compiler.py:45-78`
> - 类型：源代码
> - 强度：verified
> - 检验方式：`tests/test_compiler.py::test_all_step_types` 全覆盖通过
> - 快照：commit `428d772f1a3b5c6d7e8f9a0b1c2d3e4f5a6b7c8d`，文件哈希 `sha256:a1b2...`

Spark 转换层未来可能支持增量物化视图以降低重计算成本。

> 🧾 **推断**
> - 依据：`docs/04-spark-multi-agent-plan.md` 中提到"后续考虑增量机制"
>   （commit `3f8a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8d`，文件哈希 `sha256:d4e5...`）
> - 强度：inferred
> - 待确认：未在任何已生效的 AGENTS.md 或 contracts 中找到相关约束
```

### 5.4 标注块字段规范

```yaml
---
annotation_id: "ann-01J3R7XK-001"        # ULID，本文档内唯一
claim_hash: "sha256:..."                  # 被标注声明的文本哈希
evidence:
  - source_path: "src/compiler/duckdb_compiler.py"
    source_lines: "45-78"
    source_commit: "428d772f1a3b5c6d7e8f9a0b1c2d3e4f5a6b7c8d"
    source_content_hash: "sha256:a1b2..."
    evidence_type: "source_code"          # source_code | config | doc | test_result | git_log | dependency_spec | external
    strength: "verified"
    verification:                         # 仅 verified/supported 填写
      method: "test_coverage"
      reference: "tests/test_compiler.py::test_all_step_types"
      result: "pass"
    note: null
```

### 5.5 证据类型枚举

| `evidence_type` | 含义 | 示例 |
|-----------------|------|------|
| `source_code` | 源项目代码文件 | `src/compiler/duckdb_compiler.py` |
| `config` | 配置文件、契约 | `contracts/sql_safety_policy.yml` |
| `doc` | 源项目自身的文档 | `AGENTS.md`、`docs/01-target-architecture.md` |
| `test_result` | 测试或门禁输出 | `harness/reports/phase-3-exit.json` |
| `git_log` | Git 提交记录 | `git log -- TianShu/` 输出摘要 |
| `dependency_spec` | 依赖声明 | `pyproject.toml`、`uv.lock` |
| `external` | 外部来源 | DashVault 知识库外的引用 |

### 5.6 标注范围规则

| 粒度 | 标注位置 | 规则 |
|------|---------|------|
| **整文档** | Front Matter `evidence_level` + `source_snapshots` | 最低强度，通用来源 |
| **章节** | 章节标题下一行的标注块 | 该节内所有声明的默认证据，除非逐段覆盖 |
| **段落/声明** | 紧跟声明的标注块 | 精确到该声明的证据，优先级最高 |

继承规则：
```
段落标注 > 章节标注 > 文档默认
无标注 = 视为 inferred（安全兜底）
```

### 5.7 推断与待确认标记

所有非 `verified`/`supported` 的声明必须在标注块中使用**视觉区分**：

```markdown
> 🧾 **推断**         ← inferred：合理推断，但无直接证据
> 🧾 **待确认**        ← unconfirmed：连推断依据都不充分
```

`provenance: inferred` 的文档：
- 正文内**每条声明**都必须标注为 `inferred` 或 `unconfirmed`
- 不得出现 `verified` 或 `supported` 声明
- 文档开头必须显示：

```markdown
> ⚠️ **本文档为模型推断产物，尚未经人工审查验证。所有声明均应视为推断。**
```

### 5.8 证据清单文件

`evidence_manifest` 指向的 JSON 文件记录本次生成运行时实际读取的所有文件及其内容哈希：

```jsonc
// _evidence/manifest-01J3R7XK.json
{
  "manifest_id": "01J3R7XK...",
  "run_id": "run-01J3R7XKAB...",
  "generated_at": "2026-07-23T15:30:00+08:00",
  "projects": [
    {
      "project_id": "datadev-v3",
      "git_commit": "428d772f1a3b5c6d7e8f9a0b1c2d3e4f5a6b7c8d",
      "git_root": "D:\\Program Files\\gitvscode",
      "git_pathspec": "TianShu-DataDev-Agent-v3/",
      "worktree_state": "dirty",
      "worktree_hash": "sha256:9a0b1c2...",
      "files_read": [
        {
          "path": "AGENTS.md",
          "content_hash": "sha256:a1b2...",
          "lines_read": "1-148",
          "reason": "项目宪法，理解治理模型"
        }
      ],
      "files_excluded": [
        {
          "path": ".venv/",
          "reason": "强制排除规则：Python 虚拟环境"
        }
      ]
    }
  ]
}
```

### 5.9 校验规则

DashVault 的 `reviewer.py` 在一致性检查阶段对证据标注执行以下校验：

| 校验项 | 失败动作 |
|--------|---------|
| 标注块中的 `source_path` 必须在 `evidence_manifest` 的 `files_read` 中出现 | 标记为"证据不在清单中" |
| 标注块中的 `source_content_hash` 必须与清单中对应文件一致 | 标记为"证据哈希不匹配" |
| 所有 `inferred`/`unconfirmed` 标注必须有明确的 `note` | 提示补充推断依据 |
| 文档中各声明的 `strength` 最低值必须与 Front Matter `evidence_level` 一致 | 修正 Front Matter |
| `verified` 声明必须有 `verification` 字段 | 降级为 `supported` |

### 5.10 与前端渲染的关系

前端在渲染文档时：
- `inferred` 标注块渲染为黄色左边框 + ⚠️ 图标
- `unconfirmed` 标注块渲染为红色左边框 + ❓ 图标
- `verified` 标注块渲染为绿色左边框 + ✅ 图标
- `supported` 标注块渲染为蓝色左边框 + 📎 图标
- 鼠标悬停显示 source_path、commit、验证方式的 tooltip
- 点击 source_path 跳转到源文件（如果有权限访问）

### 5.11 标注块 YAML 的 JSON Schema 定义

以下 JSON Schema 供 `reviewer.py` 对证据标注块进行机器校验。校验器应当验证标注块的 YAML 结构、字段类型和枚举值范围。

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "dashvault.spec.evidence.annotation",
  "title": "证据标注块",
  "description": "DashVault 文档中每条关键声明的证据标注结构",
  "type": "object",
  "required": ["annotation_id", "claim_hash", "evidence"],
  "properties": {
    "annotation_id": {
      "type": "string",
      "pattern": "^ann-[0-9A-HJKMNP-TV-Z]{10}-[0-9]{3}$",
      "description": "ULID 格式的标注标识符，本文档内唯一"
    },
    "claim_hash": {
      "type": "string",
      "pattern": "^sha256:[a-f0-9]{64}$",
      "description": "被标注声明的 SHA-256 文本哈希"
    },
    "evidence": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["source_path", "evidence_type", "strength"],
        "properties": {
          "source_path": {
            "type": "string",
            "description": "证据源文件路径，须在 evidence_manifest 的 files_read 中出现"
          },
          "source_lines": {
            "type": "string",
            "pattern": "^[0-9]+(-[0-9]+)?$",
            "description": "证据所在行号或行号范围"
          },
          "source_commit": {
            "type": "string",
            "pattern": "^[a-f0-9]{40}$",
            "description": "证据源文件所属的完整 commit SHA"
          },
          "source_content_hash": {
            "type": "string",
            "pattern": "^sha256:[a-f0-9]{64}$",
            "description": "证据源文件在读取时刻的内容哈希"
          },
          "evidence_type": {
            "type": "string",
            "enum": [
              "source_code",
              "config",
              "doc",
              "test_result",
              "git_log",
              "dependency_spec",
              "external"
            ],
            "description": "证据类型枚举"
          },
          "strength": {
            "type": "string",
            "enum": ["verified", "supported", "inferred", "unconfirmed"],
            "description": "证据强度等级"
          },
          "verification": {
            "type": "object",
            "description": "仅 verified/supported 等级填写，记录验证方法",
            "required": ["method", "reference", "result"],
            "properties": {
              "method": {
                "type": "string",
                "description": "验证方式，如 test_coverage、manual_review、static_analysis"
              },
              "reference": {
                "type": "string",
                "description": "验证依据引用，如测试用例路径或审查记录 ID"
              },
              "result": {
                "type": "string",
                "enum": ["pass", "fail", "n/a"],
                "description": "验证结果"
              }
            }
          },
          "note": {
            "type": ["string", "null"],
            "description": "补充说明，inferred/unconfirmed 必须填写"
          }
        }
      }
    }
  }
}
```

### 5.12 前端渲染 CSS 类名约定

前端渲染引擎对证据标注块应用以下 CSS 类名。每个类名的视觉样式定义如下：

| CSS 类名 | 对应强度 | 左边框颜色 | 图标 | 背景色 |
|----------|---------|-----------|------|--------|
| `.evidence--verified` | verified | `#22c55e`（绿色） | ✅ | `#f0fdf4`（浅绿） |
| `.evidence--supported` | supported | `#3b82f6`（蓝色） | 📎 | `#eff6ff`（浅蓝） |
| `.evidence--inferred` | inferred | `#eab308`（黄色） | ⚠️ | `#fefce8`（浅黄） |
| `.evidence--unconfirmed` | unconfirmed | `#ef4444`（红色） | ❓ | `#fef2f2`（浅红） |

```css
/* 证据标注块基础样式 */
.evidence {
  position: relative;
  padding: 12px 16px;
  margin: 8px 0;
  border-left: 4px solid transparent;
  border-radius: 4px;
  font-size: 0.875rem;
  line-height: 1.5;
}

/* —— 已验证 —— */
.evidence--verified {
  border-left-color: #22c55e;
  background-color: #f0fdf4;
}
.evidence--verified::before {
  content: "✅";
  margin-right: 8px;
}

/* —— 有支撑 —— */
.evidence--supported {
  border-left-color: #3b82f6;
  background-color: #eff6ff;
}
.evidence--supported::before {
  content: "📎";
  margin-right: 8px;
}

/* —— 模型推断 —— */
.evidence--inferred {
  border-left-color: #eab308;
  background-color: #fefce8;
}
.evidence--inferred::before {
  content: "⚠️";
  margin-right: 8px;
}

/* —— 尚未确认 —— */
.evidence--unconfirmed {
  border-left-color: #ef4444;
  background-color: #fef2f2;
}
.evidence--unconfirmed::before {
  content: "❓";
  margin-right: 8px;
}

/* 鼠标悬停 tooltip */
.evidence:hover .evidence-tooltip {
  display: block;
}
.evidence-tooltip {
  display: none;
  position: absolute;
  bottom: calc(100% + 4px);
  left: 0;
  padding: 8px 12px;
  background: #1f2937;
  color: #f9fafb;
  border-radius: 6px;
  font-size: 0.75rem;
  white-space: nowrap;
  z-index: 100;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

/* source_path 可点击跳转 */
.evidence-source-link {
  color: inherit;
  text-decoration: underline;
  text-decoration-style: dotted;
  cursor: pointer;
}
.evidence-source-link:hover {
  text-decoration-style: solid;
}
```

说明：
- `.evidence` 为基类，所有标注块元素均应同时挂载基类和对应的强度类。
- `::before` 伪元素用于渲染图标，避免修改 HTML 结构。
- 暗色模式下应使用对应的暗色变量（如 `dark:bg-green-900/20`），实际颜色值由前端主题系统覆盖。
- tooltip 通过纯 CSS 实现：`.evidence:hover .evidence-tooltip` 控制显示/隐藏。
- `evidence-source-link` 类用于可跳转的 source_path，点击行为由前端路由处理。

---

