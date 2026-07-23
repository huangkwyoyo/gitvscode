# AGENTS.md

## 角色定义

DashVault 是一个**跨项目、只读采集、带来源证据的派生知识层**。它是观察者，不是管理者。

## 能力边界

### 能做
- 读取已注册项目的 Git 历史和受控文件
- 基于源项目证据生成派生的知识文档
- 维护跨项目的术语表、架构视图和方法论库
- 以只读方式浏览项目文档树

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

## 强制前置阅读

Agent 启动时必须读取的核心文件：
1. `specs/document-lifecycle.md` — 了解项目定位和架构
2. `AGENTS.md` — 本文档

## 代码规范

- 所有注释使用中文，解释"为什么"而非"是什么"
- 函数/类使用简短的中文 docstring
