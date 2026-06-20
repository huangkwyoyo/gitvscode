# 贡献指南

感谢你对 TianShu Text2SQL Agent 的关注！本文档帮助你快速上手开发。

## 开发环境搭建

### 前置要求

- Python >= 3.10
- Git（推荐 Git Bash for Windows）
- TianShu 数据仓库（DuckDB 文件 + 契约文件）

### 安装步骤

```bash
# 1. 克隆项目
git clone <repo-url>
cd TianShu-Text2SQL-Agent

# 2. 安装全部依赖（核心 + API + 开发工具）
pip install -e ".[api,dev]"

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，设置 TIANSHU_LOCAL_API_TOKEN

# 4. 配置数据源和 API Key
# 编辑 config/tianshu_target.yml（DuckDB 路径）
# 编辑 config/secrets.yml（DeepSeek API Key，见 secrets.yml.example）

# 5. 安装 Git Hooks
git config core.hooksPath .githooks

# 6. 运行验收确认环境正确
make verify
```

## Git Hooks

项目使用 `.githooks/pre-commit` 作为 pre-commit hook，安装方式：

```bash
git config core.hooksPath .githooks
```

每次 `git commit` 自动执行 5 步门禁检查：

1. **编译检查** — `compileall -q src harness tests`
2. **单元测试** — `pytest -q`
3. **Harness 安全检查** — 5 项（SQL 只读 / IR Schema / 反问策略 / 层级合规 / 指标注册）
4. **Memory Gate** — 关键路径变更 → 记忆文件同步检查
5. **Memory Harness** — active+blocking=true 规则强制检查

> Hook 失败时会展示具体原因和修复建议。紧急情况可用 `git commit --no-verify` 绕过（不推荐）。

## 分支策略

- **`main`**：主分支，保持可发布状态。所有 PR 合并到此分支。
- **Feature 分支**：从 `main` 分出，命名格式 `feature/<phase>-<description>`，如 `feature/6c-local-auth`。
- **Fix 分支**：从 `main` 分出，命名格式 `fix/<description>`。

## Pull Request 流程

1. 从 `main` 创建 feature/fix 分支
2. 开发和测试（确保 `make test` 和 `make harness` 均通过）
3. 推送前运行 `make verify` 完整验收
4. 创建 PR，描述变更内容和测试结果
5. 等待 Code Review
6. 合并到 `main`

## 代码审查分类系统（CRCS）

项目使用 AGENTS.md 中定义的三级分类系统评估变更影响：

| 分类 | 含义 | 审查要求 |
|:--:|------|----------|
| **A** | 关键安全变更（SQL 生成、安全检查、契约解析、认证/授权） | 必须审查 + 完整回归 + Harness 全量 |
| **B** | 架构变更（IR 结构、执行策略、API 接口、Prompt 模板） | 必须审查 + 定向测试 + 相关 Harness |
| **C** | 辅助变更（文档、日志、测试补充、REPL 体验、示例） | 审查推荐 + 编译通过 |

### 关键边界（不得突破）

1. LLM 不得直接生成最终 SQL — `sql_plan_to_sql()` 是唯一 SQL 生成入口
2. SQL 必须经过 `validate_sql_safety()` — 6 项纯规则检查
3. DuckDB 连接必须 `read_only=True` — executor.py 强制
4. API 不得暴露 SQL/trace/内部路径 — `build_public_response()` 过滤
5. 令牌不得写入代码/配置/报告 — 仅通过环境变量注入

## 代码规范

- **所有注释使用中文**（函数注释、变量说明、行内注释、文档字符串等）
- 注释应简洁明了，解释"为什么"而非"是什么"
- 函数/类使用简短的中文 docstring 说明用途

```python
def validate_sql_safety(sql: str) -> bool:
    """对生成的 SQL 执行 6 项纯规则安全检查，禁止写操作和越权访问。"""
    # 逐项检查，任何一项不通过即返回 False
    ...
```

## 变更传播规则

修改以下文件时，必须同步更新关联文件（详见 `AGENTS.md §8`）：

| 修改源 | 需同步的文件 |
|--------|-------------|
| `src/ir.py` | `schema_validators.py`、`response_contract.py`、相关 test |
| `src/agent.py` | `test_mvp_agent.py`、`response_contract.py` |
| `src/sql_gen.py` | `check_sql_readonly.py`、`check_plan_executor_safety.py` |
| Prompt 文件 | `evals/` 相关 case、Prompt 回归 fixture |
| `config/agent_config.yml` | `harness/config.py` |
| 安全策略文件 | `safety_policy_loader.py`、`check_refusal_policy.py` |

## 测试指南

```bash
# 全部测试
make test

# 特定模块
python -m pytest tests/test_local_auth.py -q

# 跳过真实 DuckDB 测试（默认已跳过）
python -m pytest -q -k "not real_duckdb"

# 含覆盖率报告
python -m pytest --cov=src --cov-report=term-missing -q
```

## 项目文档

| 文档 | 路径 |
|------|------|
| 开发规则 | `AGENTS.md` |
| 版本日志 | `CHANGELOG.md` |
| 当前工作流 | `docs/text2sql_current_pipeline.md` |
| 工程术语表 | `docs/text2sql_engineering_glossary.md` |
| 故障排查 | `docs/TROUBLESHOOTING.md` |
| 经验复盘 | `docs/memory/经验复盘.md` |
| 风险清单 | `docs/memory/风险清单.md` |
| 各阶段报告 | `docs/planning/` |
