# DashVault 项目注册信息规范

> doc_id: dashvault.spec.registry
> spec_version: 1.0.0
> review_status: draft
> publication_status: unpublished

## 1. 概述

本文档定义 DashVault 项目注册表（`dashvault.yaml`）的完整 schema。

## 2. 注册表顶层结构

```yaml
# dashvault.yaml
version: 1
projects:
  # —— 示例：独立 Git 仓库项目 ——
  - project_id: "datadev-v3"
    name: "DataDev Agent v3"
    project_root: "D:\\Program Files\\gitvscode\\TianShu-DataDev-Agent-v3"
    git_root: "D:\\Program Files\\gitvscode\\TianShu-DataDev-Agent-v3"
    git_pathspec: "."
    scan_mode: "git"
    last_observed_commit: ""
    last_scan_time: null
    include_rules: []
    exclude_rules: []
    tags: ["数据开发", "Agent"]

  # —— 示例：共享仓库中的子项目 ——
  - project_id: "tianshu"
    name: "TianShu 数据仓库"
    project_root: "D:\\Program Files\\gitvscode\\TianShu"
    git_root: "D:\\Program Files\\gitvscode"
    git_pathspec: "TianShu/"
    scan_mode: "git"
    last_observed_commit: ""
    last_scan_time: null
    include_rules: []
    exclude_rules: ["reports/"]
    tags: ["数据仓库", "底座"]

  # —— 示例：非 Git 知识库 ——
  - project_id: "ai-learning"
    name: "AI Learning 知识库"
    project_root: "C:\\Users\\62414\\Nutstore\\1\\Obsidian Vault\\Ai Learning"
    git_root: null
    git_pathspec: "."
    scan_mode: "directory"
    last_observed_commit: null
    last_scan_time: null
    include_rules: ["**/*.md"]
    exclude_rules: []
    tags: ["知识库"]
```

## 3. 字段定义

### 3.1 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `version` | `int` | ✅ | 注册表格式版本，当前为 `1` |
| `projects` | `list[ProjectEntry]` | ✅ | 注册项目列表 |

### 3.2 ProjectEntry 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `project_id` | `str` | ✅ | 全局唯一标识，`[a-z0-9-]+`，长度 1-64 |
| `name` | `str` | ✅ | 人类可读的项目名称 |
| `project_root` | `str` | ✅ | 项目文件系统的绝对路径 |
| `git_root` | `str \| null` | ✅ | Git 仓库根目录，非 Git 项目为 null |
| `git_pathspec` | `str` | ✅ | 仓库内路径限定，独立仓库为 `"."` |
| `scan_mode` | `str` | ✅ | `"git"` 或 `"directory"` |
| `last_observed_commit` | `str \| null` | ✅ | Scanner 上次采集到的 HEAD（40 位 SHA），初始为 `""`（Git）或 null（非 Git） |
| `last_scan_time` | `str \| null` | ❌ | 上次扫描的 ISO 8601 时间戳 |
| `include_rules` | `list[str]` | ❌ | 额外文件包含 glob 规则 |
| `exclude_rules` | `list[str]` | ❌ | 额外文件排除 glob 规则 |
| `tags` | `list[str]` | ❌ | 项目标签 |
| `description` | `str \| null` | ❌ | 简短描述 |

### 3.3 字段约束

- `project_id`：仅允许 `[a-z0-9-]+`，长度 1-64，全局唯一
- `git_root`：必须含 `.git/` 目录（`scan_mode: git` 时），project_root 必须为其子目录
- `git_pathspec`：独立仓库为 `"."`，共享仓库以 `/` 结尾（如 `"TianShu/"`）
- `last_observed_commit`：`scan_mode: git` 时为 40 位 hex 或空字符串，`scan_mode: directory` 时为 null
- 以 `/` 结尾的 glob 规则仅匹配目录

## 4. 文件采集规则

### 4.1 全局强制排除（不可覆盖）

```yaml
global_exclude:
  - ".env"
  - ".env.*"
  - ".venv/"
  - ".pytest_cache/"
  - ".pytest_tmp/"
  - ".ruff_cache/"
  - "__pycache__/"
  - "*.pyc"
  - "logs/"
  - "llm_responses/"
  - "llm_reports/"
  - "generated/"
  - ".git/"
  - "node_modules/"
```

### 4.2 规则优先级

```
1. 全局强制排除（不可覆盖）
2. 项目 exclude_rules
3. 项目 include_rules（与 exclude 冲突时 include 胜出）
4. 默认：仅 git ls-files 受控文件（scan_mode: git）或 os.walk + glob（scan_mode: directory）
```

## 5. 注册操作

### 5.1 CLI

```bash
dashvault register /path/to/project [--name "..."] [--mode directory] [--include "**/*.md"]
dashvault unregister <project_id>
dashvault list
```

### 5.2 注册流程

```
1. 验证 project_root 存在且可读
2. 检测 git_root（向上查找 .git/）→ 设置 scan_mode
3. 计算 git_pathspec
4. 生成 project_id（目录名 → kebab-case，冲突时追加数字）
5. 写入 dashvault.yaml
```

### 5.3 取消注册

只从注册表移除条目，不删除已生成的文档。

## 6. 启动校验

| 校验项 | 失败动作 |
|--------|---------|
| `project_id` 唯一性 | 拒绝启动 |
| `project_root` 存在性 | 标记"不可达"，跳过 |
| `git_root` 有效性 | 标记"Git 不可用"，跳过 |
| `version` 兼容性 | 拒绝启动 |
