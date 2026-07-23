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

## 能力边界

### 能做
- 读取已注册项目的 Git 历史和受控文件
- 基于源项目证据生成派生的知识文档
- 维护跨项目的术语表、架构视图和方法论库
- 以只读方式浏览项目文档树
- 通过自然语言驱动：指定项目、知识点、文档类型，生成或更新文档

### 不能做
- 修改源项目的任何文件（AGENTS.md、契约、Memory、状态文档）
- 宣称自己是任何项目的事实源
- 绕过源项目的治理模型（Memory Gate、Human Review 等）
- 读取源项目的 .env、密钥、日志、LLM 原始响应

## 核心规范

所有设计规范位于 `specs/` 目录（固定路径，无时间戳）：

| 文件 | 内容 |
|------|------|
| `specs/document-lifecycle.md` | 核心设计文档：事实源与文档生命周期 |
| `specs/registry-spec.md` | 项目注册信息规范 |
| `specs/scanner-spec.md` | Scanner 详细规范 |
| `specs/prompt-spec.md` | Prompt 模板编写规范 |
| `specs/front-matter-spec.md` | 统一 Front Matter 规范 |
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
2. `AGENTS.md` — 本文档

## 代码规范

- 所有注释使用中文，解释"为什么"而非"是什么"
- 函数/类使用简短的中文 docstring
