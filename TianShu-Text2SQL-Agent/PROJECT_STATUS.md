# 项目状态

> TianShu Text2SQL Agent 当前工程状态概览。非发布说明，非路线图。
> 最后更新：2026-06-21

## 版本

| 项目 | 值 |
|------|-----|
| **当前版本** | 1.0.0 |
| **版本来源** | `src/version.py`（从 pyproject.toml 解析） |
| **Python** | >= 3.10 |
| **仓库分支** | `main` |

## 核心流水线状态

| 环节 | 状态 | 说明 |
|------|:----:|------|
| 意图识别 (L1) | ✅ 生产 | LLM + Rule 双模式；歧义反问；refusal 检测 |
| SQL 规划 (L2) | ✅ 生产 | G3 优先 → G2 降级；指标注册校验 |
| SQL 生成 (L3) | ✅ 生产 | 程序生成（非 LLM）；DuckDB 方言 AST + 函数白名单 |
| 执行 | ✅ 生产 | DuckDB read_only=True；串行/并行切换 |
| 解释 | ✅ 生产 | 中文结构化解释；图表规格 |
| REST API | ✅ 生产 | 3 端点；令牌认证；限流；审计；安全响应头 |
| Web UI | ✅ 生产 | 原生 HTML/CSS/JS + SVG；严格 CSP |
| 安全门禁 | ✅ 生产 | pre-commit 6 步；Fast Gate 7 步；Slow Gate 观测 |

## 已知阻塞

| 阻塞项 | 影响 | 状态 |
|--------|------|:----:|
| G3→dim_date JOIN 未在权威契约中声明 | ~60% 日汇总查询 fail-closed（返回 clarification） | ⏳ 已提交契约变更建议，待 TianShu Dev Agent 审批 |
| Memory 测试中硬编码规则数量 | 规则新增后测试期望值漂移 | ⚠️ 待改为动态读取注册表 |

## 测试健康度

| 指标 | 当前值 |
|------|--------|
| 测试文件数 | 动态（通过 pytest discovery） |
| 通过预期 | 全部排除已知阻塞后应 100% PASS |
| 已知失败 | G3→dim_date JOIN 相关 ~36 个 fail-closed（预期行为） |

## 质量门禁覆盖

| 门禁 | 触发条件 | 阻断 | 说明 |
|------|----------|:----:|------|
| Ruff 代码检查 | pre-commit / CI / `make lint` | ✅ | 零违规 |
| 代码编译 | pre-commit / CI / `make verify` | ✅ | compileall 全量 |
| 单元测试 | pre-commit / CI / `make test` | ✅ | pytest 全量 |
| Harness 安全检查 | pre-commit / CI / `make harness` | ✅ | 12 项（SQL 只读、IR Schema、反问策略等） |
| Memory Gate | pre-commit | ✅ | 关键路径变更 → 记忆文件同步 |
| Memory Harness | pre-commit | ✅ | active+blocking=true 规则阻断 |
| JOIN 白名单检查 | CI | ✅ | 禁止硬编码绕过 |
| Mock Prompt 回归 | CI (Fast Gate) | ✅ | 离线 Prompt 行为一致性 |
| Mock E2E 评测 | CI (Fast Gate) | ✅ | 离线端到端验证 |
| 真实 LLM 观测 | CI (Slow Gate, push main) | ❌ | 仅报告，不阻断 |

## 安全链路完整性

| 安全层 | 机制 | 状态 |
|--------|------|:----:|
| SQL 生成 | `sql_plan_to_sql()` 程序生成（非 LLM） | ✅ |
| SQL 校验 | DuckDB 方言 AST + 函数白名单 + 6 项规则 | ✅ |
| JOIN 控制 | 白名单仅从权威契约加载（零硬编码） | ✅ |
| 执行隔离 | DuckDB read_only=True | ✅ |
| API 认证 | X-TianShu-Token + hmac.compare_digest | ✅ |
| API 限流 | 固定窗口 30 req/min | ✅ |
| API 审计 | JSONL 脱敏追加写入 | ✅ |
| Web UI | CSP + textContent + 零 innerHTML | ✅ |
| 错误脱敏 | 500 仅返回安全消息 | ✅ |

## 近期治理记录

| 日期 | 治理项 | 状态 |
|------|--------|:----:|
| 2026-06-21 | CI 工作流迁至仓库根目录 | ✅ |
| 2026-06-21 | JOIN 白名单硬编码移除 | ✅ |
| 2026-06-21 | Ruff 门禁集成 | ✅ |
| 2026-06-21 | 版本号统一（src/version.py） | ✅ |
| 2026-06-21 | 文档过期描述清理 | ✅ |
| 2026-06-21 | Harness 报告目录治理 | 进行中 |
| 2026-06-21 | 失败记录隐私脱敏 | 进行中 |

## 文档索引

- [AGENTS.md](AGENTS.md) — Agent 开发规则（变更传播矩阵 + CRCS）
- [CHANGELOG.md](CHANGELOG.md) — 版本变更日志
- [CONTRIBUTING.md](CONTRIBUTING.md) — 贡献指南
- [README.md](README.md) — 用户快速开始
- [docs/README.md](docs/README.md) — 设计文档索引
- [docs/text2sql_current_pipeline.md](docs/text2sql_current_pipeline.md) — 工程边界与安全门禁
- [docs/text2sql_engineering_glossary.md](docs/text2sql_engineering_glossary.md) — 工程术语表
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — 本地故障排查
- [docs/memory/](docs/memory/) — 长期记忆系统（经验复盘、风险清单、规则索引）
