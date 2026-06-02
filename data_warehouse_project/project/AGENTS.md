# Telecom Data Warehouse Agent Lab

## Project Goal

Build a telecom enterprise data warehouse simulation that runs on a personal computer.

The project is designed for:

- Data warehouse practice
- BI and metrics development
- AI Agent development
- SQL generation
- Business analysis
- LangGraph workflow development

The goal is realism of architecture and business logic, not big data scale.

------

## Technology Stack

Backend:

- Python 3.12+
- MySQL
- FastAPI
- LangGraph
- LangChain

Frontend:

- Next.js
- TypeScript

------

## Data Source

Primary source:

docs/telecom_fields.xlsx

This file contains real telecom business fields.

Do not invent field meanings without analysis.

If assumptions are required:

- explicitly state assumptions
- mark generated fields as synthetic

------

## Development Workflow

Before coding:

1. Read relevant files
2. Explain implementation plan
3. Confirm assumptions

During coding:

1. Make minimal changes
2. Keep modules focused
3. Follow existing architecture

After coding:

1. Run verification
2. Report actual results
3. Explain changes

------

## Data Warehouse Standards

Layers:

ODS
DWD
DWS
ADS

Naming:

ods_xxx
dwd_xxx
dws_xxx
ads_xxx

Prefer star schema.

Dimension tables:

dim_xxx

Fact tables:

fact_xxx

------

## Agent Architecture

Agent workflows must use LangGraph.

Requirements:

- explicit state
- explicit routing
- retry handling
- timeout handling
- logging

Avoid hidden logic.

------

## FastAPI Standards

Keep API layer thin.

Business logic belongs in services.

Use Pydantic schemas.

Validate all inputs.

------

## SQL Standards

Prefer readable SQL.

Avoid nested queries when joins are clearer.

Document business metric logic.

------

## Verification

Before completion:

- run tests
- run lint
- run type checks

Never claim success without verification.

# Git Workflow

所有开发必须遵循 Feature Branch 工作流。`main` 只作为长期稳定分支，不直接承载日常开发提交。

## 分支规则

- `main` 是唯一长期存在的稳定分支。
- 禁止直接在 `main` 上开发、提交或推送。
- 每个功能、修复或实验必须创建独立 Feature Branch。
- 分支命名必须使用 `feature/<feature-name>`。
- `<feature-name>` 使用小写英文、数字和连字符，避免空格、中文和无意义缩写。

示例：

```bash
feature/sql-generator
feature/rag-knowledgebase
feature/github-daily-report
feature/agent-memory
```

## 开发流程

1. 从 `main` 创建 Feature Branch。

```bash
git checkout main
git pull origin main
git checkout -b feature/<feature-name>
```

2. 在当前 Feature Branch 完成功能开发。

3. 提交代码。

```bash
git add <changed-files>
git commit -m "feat: <feature-name>"
```

4. 推送远程仓库。

```bash
git push -u origin feature/<feature-name>
```

5. 创建 Pull Request。

```text
source: feature/<feature-name>
target: main
```

6. Pull Request 描述必须包含：

- 功能说明
- 修改文件列表
- 风险分析
- 测试结果

7. Pull Request 合并后删除 Feature Branch。

```bash
git checkout main
git pull origin main
git branch -d feature/<feature-name>
git push origin --delete feature/<feature-name>
```

## Agent 执行约束

- Agent 开始编码前必须先确认当前分支。
- 如果当前分支是 `main`，必须先创建 `feature/<feature-name>` 分支。
- Agent 暂存文件时必须使用明确文件路径，禁止在混合工作区中直接执行 `git add .`。
- Agent 提交前必须说明本次提交范围。
- Agent 推送前必须确认远端分支名和目标 PR 分支。

## 禁止事项

- 禁止长期使用单一 `codex/*` 分支承载多个功能。
- 禁止直接提交到 `main`。
- 禁止多个功能共用一个 Feature Branch。
- 禁止把本地大文件、生成数据、Excel 工作簿或密钥文件提交到 GitHub。
