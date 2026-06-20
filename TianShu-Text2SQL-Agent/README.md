# TianShu Text2SQL Agent

以 TianShu NYC 交通数据仓库为数据源的中文问数分析 Agent —— 自然语言 → 三层 IR → 只读 SQL → 中文解释。

## 目录

- [项目简介](#项目简介)
- [快速开始](#快速开始)
- [REPL 交互式使用](#repl-交互式使用)
- [REST API 使用](#rest-api-使用)
- [Web UI 使用](#web-ui-使用)
- [响应契约](#响应契约)
- [项目结构](#项目结构)
- [配置说明](#配置说明)
- [测试与质量门禁](#测试与质量门禁)
- [Makefile 目标](#makefile-目标)
- [Windows 注意事项](#windows-注意事项)
- [常见问题](#常见问题)
- [契约来源](#契约来源)
- [许可证](#许可证)

## 项目简介

TianShu Text2SQL Agent 将中文自然语言问题安全地转换为只读 SQL，在 DuckDB 数据仓库上执行，并将结果翻译为中文解释。

**核心流水线**：

```
中文问题 → QuestionIntent → SQLPlan → SQL → 只读执行 → 中文解释
              ↑ 反问          ↑ 降级      ↑ 6 项安全检查
```

**三层 IR（中间表示）** 每层独立校验，在错误传播前拦截：

| 层 | 结构 | 作用 |
|----|------|------|
| L1 意图 | `QuestionIntent` | 指标、维度、时间范围、聚合函数的语义识别 |
| L2 规划 | `SQLPlan` | 表名、字段、JOIN、过滤条件的结构化计划 |
| L3 结果 | `SQLResult` | 执行结果 + 元数据 + 来源追溯 |

**三种最终响应类型**：`answer`（回答）、`clarification`（反问）、`refusal`（拒绝），互斥且确定。

**安全边界**：所有 SQL 由 `sql_plan_to_sql()` 程序生成（非 LLM），经过 6 项纯规则安全检查后，在 DuckDB `read_only=True` 连接上执行。

## 快速开始

### 1. 前置要求

- **Python** >= 3.10
- **Git**（含 Git Bash，Windows 用户）
- **TianShu 数据仓库**：DuckDB 数据库文件（`TianShu/data/tianShu.duckdb`）和契约文件（`TianShu/contracts/`）

### 2. 克隆项目

```bash
git clone <repo-url>
cd TianShu-Text2SQL-Agent
```

### 3. 配置环境变量

```bash
# 从模板创建 .env 文件
cp .env.example .env

# 编辑 .env，设置本地 API 令牌（至少 32 字符）
# 生成安全令牌：
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

必需环境变量：

| 变量 | 用途 | 要求 |
|------|------|------|
| `TIANSHU_LOCAL_API_TOKEN` | REST API 认证令牌 | >= 32 字符 |
| `PYTHONIOENCODING` | 控制台编码（Windows）| 建议 `utf-8` |

### 4. 安装依赖

```bash
# 安装全部依赖（含 API 服务和开发工具）
pip install -e ".[api,dev]"

# 或仅安装核心依赖
pip install -e .
```

### 5. 配置数据源

编辑 `config/tianshu_target.yml`，确认 DuckDB 数据库路径和契约路径正确。

编辑 `config/secrets.yml`，填入 DeepSeek API Key（如需 LLM 模式）：

```yaml
deepseek_api_key: "sk-your-api-key"
```

> 提示：`config/secrets.yml.example` 提供了完整的配置模板。

### 6. 运行验收

```bash
# 一键验收（编译 → 测试 → 安全检查 → API 闭环）
make verify
```

验收通过即表示本地环境配置正确、所有功能可用。

## REPL 交互式使用

```bash
# 启动交互式问数
tianshu-ask
```

REPL 支持的命令：

```
> 2026年1月曼哈顿每天有多少行程？
  → Agent 分析并返回答案

> /help    显示帮助
> /exit    退出（也可按 Ctrl+C）
```

**工作模式**：

- **LLM 模式**（默认）：使用 DeepSeek 模型进行意图识别和 SQL 规划
- **Rule 模式**：不调用 LLM，使用配置中的关键词→指标映射规则（适合离线/测试场景）

在 `config/agent_config.yml` 中通过 `rule_mode.enabled` 切换。

> 更多 REPL 使用示例见 [`examples/repl/`](examples/repl/)。

## REST API 使用

### 启动服务

```bash
# 方式一：Makefile
make api

# 方式二：CLI 命令
tianshu-api --config config/api_config.yml

# 方式三：直接脚本
python scripts/run_api.py --config config/api_config.yml
```

服务默认绑定 `127.0.0.1:8000`，自动开启 Swagger 文档（`/docs`）。

### 端点一览

| 方法 | 路径 | 认证 | 说明 |
|------|------|:--:|------|
| `GET` | `/health/live` | 否 | 进程存活检查 |
| `GET` | `/health/ready` | 否 | Agent + Auth + DuckDB 就绪检查 |
| `POST` | `/v1/ask` | 是 | 中文问数查询 |

### 认证方式

所有 `POST /v1/ask` 请求需携带 `X-TianShu-Token` 请求头：

```bash
curl -X POST http://127.0.0.1:8000/v1/ask \
  -H "Content-Type: application/json" \
  -H "X-TianShu-Token: $TIANSHU_LOCAL_API_TOKEN" \
  -d '{"question": "2026年1月每天有多少行程？"}'
```

### 安全特性

| 特性 | 说明 |
|------|------|
| 令牌认证 | `X-TianShu-Token` header + `hmac.compare_digest()` 恒定时间比较 |
| 限流 | 固定窗口 30 req/min + 3 burst，超限返回 429 + Retry-After |
| Body 限制 | 最大 8192 字节，超限返回 413 |
| 安全响应头 | nosniff / DENY / no-referrer / no-store |
| 审计日志 | JSONL 脱敏审计（不含 question/answer/SQL/token） |
| 错误脱敏 | 500 错误仅返回安全消息，不暴露内部细节 |

### 状态码说明

| 状态码 | 含义 |
|:--:|------|
| 200 | 成功（response_type 表示 answer/clarification/refusal） |
| 401 | 认证失败 |
| 413 | 请求体过大 |
| 422 | 请求格式错误 |
| 429 | 请求频率超限 |
| 500 | 服务内部错误（安全脱敏） |
| 503 | 服务未就绪 |

> 完整请求/响应示例见 [`examples/api/`](examples/api/)。

## Web UI 使用

启动 API 后，打开浏览器访问 `http://127.0.0.1:8000/` 即可使用中文问数 Web 界面。

```bash
# 1. 启动服务
make api

# 2. 浏览器打开
# http://127.0.0.1:8000/
```

### 界面功能

| 区域 | 说明 |
|------|------|
| **顶部状态栏** | 显示 API 可用状态、版本号 (v1.0.0)、本地模式标识 |
| **认证令牌** | 输入 `X-TianShu-Token` 连接服务。令牌仅保存在当前页面内存，刷新后失效 |
| **中文问数** | 多行中文输入框，Ctrl+Enter 提交，含示例问题快捷按钮 |
| **查询结果** | 根据 `response_type` 展示中文答案、反问提示或拒绝原因 |
| **数据展示** | 原生 SVG 图表（折线/柱状/指标卡）、数据预览表、来源、警告 |

### 安全特性

- 令牌仅保存在 JavaScript 闭包内存（不写 localStorage / Cookie / URL）
- 所有后端数据通过 `textContent` 安全渲染（零 `innerHTML`）
- 严格 Content-Security-Policy（无 `unsafe-inline` / `unsafe-eval`）
- 不显示 SQL、trace、Token、数据库路径等内部信息
- 纯原生 HTML/CSS/JS + 原生 SVG，无外部 CDN 依赖

> 详细安全说明见 [Web UI 安全测试](tests/test_web_ui_security.py)。

## 响应契约

所有 `POST /v1/ask` 响应遵循**统一公开响应契约 v1.0**：

```json
{
  "contract_version": "1.0",
  "response_type": "answer",
  "question": "2026年1月每天有多少行程？",
  "answer": {"text": "2026年1月平均每天有 45,230 行程……"},
  "clarification": {"needed": false, "message": null},
  "refusal": {"refused": false, "reason": null},
  "data": {
    "is_multi_plan": false,
    "summaries": [{"...": "ResultSummary"}],
    "merged_result": null,
    "chart_spec": {"...": "ChartSpec"},
    "sources": ["gold.dws_daily_trip_summary"]
  },
  "warnings": [],
  "meta": {"execution_mode": "single"}
}
```

**安全保证**：响应中**绝不包含** SQL 语句、数据库路径、API Key、认证令牌、traceback 等敏感信息。

## 项目结构

```
├── AGENTS.md                    # Agent 开发规则（变更传播矩阵 + CRCS）
├── CHANGELOG.md                 # 版本变更日志
├── CONTRIBUTING.md              # 贡献指南
├── LICENSE                      # MIT 许可证
├── Makefile                     # 一键脚本（install/test/harness/verify/clean）
├── README.md                    # 本文件
├── VERSION                      # 版本标识（1.0.0）
├── pyproject.toml               # 项目元数据 + 依赖 + 入口点
├── .env.example                 # 环境变量模板
├── .githooks/                   # Git Hooks（pre-commit 5 步门禁）
├── config/
│   ├── agent_config.yml         # Agent 运行时配置（模型/行为/安全/日志）
│   ├── api_config.yml           # API 安全配置（令牌/限流/审计/响应头）
│   ├── tianshu_target.yml       # 数据仓库连接配置
│   ├── secrets.yml              # API Key（gitignored）
│   └── secrets.yml.example      # secrets 配置模板
├── src/
│   ├── agent.py                 # Text2SQLAgent 主循环
│   ├── ir.py                    # 三层 IR 数据结构
│   ├── resolver.py              # DuckDB + 契约动态加载
│   ├── sql_gen.py               # SQLPlan → SQL 程序生成
│   ├── executor.py              # DuckDB 只读执行器
│   ├── explainer.py             # 结果 → 中文解释
│   ├── ambiguity.py             # 歧义检测与反问
│   ├── repl.py                  # 交互式 REPL
│   ├── response_contract.py     # 统一公开响应契约 v1.0
│   ├── safety_policy_loader.py  # 安全策略加载
│   ├── request_guard.py         # 请求预检查
│   ├── chart_spec.py            # 图表规格（纯规则）
│   ├── cross_domain_policy.py   # 跨域展示策略
│   ├── result_summary.py        # 结果结构化摘要
│   ├── result_merge.py          # 多计划结果合并
│   ├── result_fusion.py         # 结果 LLM 融合
│   ├── plan_executor.py         # 计划执行编排
│   ├── execution_strategy.py    # 串行/并行执行策略
│   ├── llm.py / llm_adapter.py / llm_pipeline.py  # LLM 集成
│   └── api/                     # REST API 子包（Phase 6B/6C）
│       ├── app.py               # FastAPI 应用 + 中间件栈
│       ├── runtime.py           # Agent 受控运行时
│       ├── schemas.py           # Pydantic 请求/响应模型
│       ├── errors.py            # 6 种错误码 + 安全脱敏
│       ├── local_auth.py        # 本地令牌认证
│       ├── local_rate_limit.py  # 固定窗口 + 令牌桶限流
│       ├── body_limit.py        # 请求体大小限制
│       └── local_audit.py       # 脱敏 JSONL 审计
├── scripts/
│   ├── run_api.py               # API 服务启动脚本
│   ├── run_local_api_closure.py # 本地安全闭环验证（8 项）
│   ├── run_real_duckdb_e2e.py   # 真实 DuckDB E2E 评测
│   ├── run_rest_api_smoke.py    # REST API 冒烟测试
│   └── generate_rule_index.py   # 规则来源索引生成
├── harness/
│   ├── run_harness.py           # 12 项 Harness 入口
│   ├── run_fast_gate.py         # 快速门禁（5 步，Mock）
│   ├── run_slow_gate.py         # 慢速门禁（真实 LLM，观察）
│   ├── run_baseline_freeze.py   # 双基线快照
│   ├── checks/                  # 12 个安全检查脚本
│   └── reports/                 # 报告输出目录
├── tests/                       # ~55 个测试文件（1709 用例）
├── evals/                       # 评测问题集（7 个 YAML 文件）
├── prompts/                     # LLM Prompt 模板（6 个文件）
├── docs/
│   ├── README.md                # 文档索引
│   ├── text2sql_current_pipeline.md  # 当前工作流说明
│   ├── text2sql_engineering_glossary.md  # 工程术语表
│   ├── TROUBLESHOOTING.md       # 故障排查指南
│   ├── memory/                  # 长期记忆（经验/风险/规则）
│   └── planning/                # 各阶段设计报告
└── examples/
    ├── README.md                # 示例索引
    ├── repl/                    # REPL 使用示例
    └── api/                     # API 请求/响应 JSON 示例
```

## 配置说明

| 配置文件 | 用途 | 关键项 |
|----------|------|--------|
| `agent_config.yml` | Agent 运行时行为 | 模型选择、歧义阈值、安全规则、执行策略、离线 fallback |
| `api_config.yml` | REST API 安全 | 令牌认证、限流（30/min+3 burst）、Body 限制（8192 字节）、审计、安全响应头 |
| `tianshu_target.yml` | 数据仓库连接 | DuckDB 路径、契约路径、read_only、内存限制、契约文件列表 |
| `secrets.yml` | API 密钥 | DeepSeek API Key（gitignored，模板见 `secrets.yml.example`） |

## 测试与质量门禁

### 运行测试

```bash
make test                             # 全部 1709 单元测试
make harness                          # 12 项 Harness 安全检查
python harness/run_fast_gate.py       # 5 步快速门禁
```

### 安装 Pre-commit Hook

```bash
git config core.hooksPath .githooks
```

安装后每次 `git commit` 自动执行 5 步检查：

1. **编译检查**（`compileall`）
2. **单元测试**（`pytest`）
3. **Harness 五项安全检查**（SQL 只读 / IR Schema / 反问策略 / 层级合规 / 指标注册）
4. **Memory Gate 记忆更新检查**
5. **Memory Harness 阻断规则检查**

### 质量体系一览

| 层级 | 触发时机 | 说明 |
|------|----------|------|
| Pre-commit | 每次 `git commit` | 5 步阻断，失败展示修复指导 |
| Fast Gate | CI / 手动 | 5 步全 Mock，exit code 驱动 |
| Slow Gate | 手动 | 真实 LLM 观察，continue-on-error |
| Baseline Freeze | 发布时 | 双基线快照（Source + Runtime） |

## Makefile 目标

| 目标 | 命令 | 说明 |
|------|------|------|
| `install` | `make install` | 安装全部依赖（含 API 和开发工具） |
| `test` | `make test` | 运行全部单元测试 |
| `harness` | `make harness` | 运行 12 项 Harness 安全检查 |
| `api` | `make api` | 启动 REST API 服务 |
| `closure` | `make closure` | 运行本地 API 安全闭环验收 |
| `baseline` | `make baseline` | 生成发布基线快照 |
| `verify` | `make verify` | **一键验收**：编译 → 测试 → 安全检查 → 闭环 |
| `clean` | `make clean` | 清理临时文件和缓存 |
| `env` | `make env` | 检查环境配置状态 |

## Windows 注意事项

- **编码**：Windows 控制台默认 GBK 编码可能导致乱码。Harness 和脚本已内置自动检测和 UTF-8 切换。建议在 `.env` 中设置 `PYTHONIOENCODING=utf-8`。
- **终端**：推荐使用 **Git Bash**（`make` 命令可用）或 Windows Terminal。
- **路径格式**：所有配置中的路径使用正斜杠（`/`），与 Unix 保持一致。
- **tmp_path 权限**：部分测试在 Windows 上使用 `pytest tmp_path` 可能遇到权限问题。测试套件已使用 `tempfile.mkdtemp()` 规避，不影响正常使用。
- **端口占用**：API 默认端口 8000。如被占用，修改 `config/api_config.yml` 中的 `server.port`。

## 常见问题

| 问题 | 解决 |
|------|------|
| `tianshu-ask: command not found` | 运行 `pip install -e .` 后确认 PATH 包含 Python Scripts 目录 |
| `/health/ready` 返回 503 | 检查 `TIANSHU_LOCAL_API_TOKEN` 是否设置且 >= 32 字符，DuckDB 文件是否存在 |
| API 返回 401 | 确认 `X-TianShu-Token` 请求头值与 `TIANSHU_LOCAL_API_TOKEN` 环境变量一致 |
| API 返回 429 | 请求频率超限，等待 60 秒或调整 `api_config.yml` 中的限流参数 |
| DuckDB 文件不存在 | 检查 `config/tianshu_target.yml` 中的 `duckdb_path` 是否正确 |
| pre-commit hook 阻断提交 | 按 hook 输出的修复建议操作，确认无误后可 `git commit --no-verify` |

> 更多问题见 [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)。

## 契约来源

所有契约文件在 TianShu 项目中维护（`../TianShu/contracts/`），Agent 启动时动态读取：

- `metric_contract.yml` — 指标注册表
- `metric_definitions.yml` — 指标业务定义（口径）
- `data_model.yml` — 数据模型与字段定义
- `question_policy.yml` — 反问与拒绝策略规则
- `sql_safety_policy.yml` — SQL 安全关键字列表

Agent 通过 `src/resolver.py` 在启动时动态发现表结构和指标元数据，不依赖硬编码。

## 许可证

MIT — 详见 [`LICENSE`](LICENSE) 文件。

---

🤖 与 TianShu 数仓变更 Agent 配合使用，形成"分析 → 发现不足 → 变更提案 → 合入 → 分析受益"的闭环。
