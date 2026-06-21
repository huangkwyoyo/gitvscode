# Changelog

本文件记录 TianShu Text2SQL Agent 所有值得关注的变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 治理

- **Ruff 代码检查门禁**：零违规（433→0），安全修复 + per-file-ignores 配置，集成 CI/pre-commit/Makefile
- **版本号统一**：建立 `src/version.py`（pyproject.toml 优先 + importlib.metadata 回退），移除所有硬编码版本号
- **项目状态文档**：新建 `PROJECT_STATUS.md`，记录版本、流水线状态、已知阻塞、质量门禁覆盖
- **README 清理**：移除易漂移的测试数量、VERSION 文件引用、过期步骤计数
- **CI 工作流修复**：`.github/workflows/` 迁至仓库根目录，GitHub 可正确识别
- **JOIN 白名单安全修复**：移除 resolver.py 和 llm_pipeline.py 的两处硬编码，100% 从权威契约加载
- **CROSS JOIN 检测**：无论表对是否在白名单，CROSS JOIN 一律拒绝

## [1.0.0] - 2026-06-20

### 新增

- **三层 IR 架构**：QuestionIntent → SQLPlan → SQLResult，每层独立校验标记
- **完整问数流水线**：意图识别 → 歧义检测与反问 → SQL 规划 → plan-to-SQL 程序生成 → 安全检查 → 只读执行 → 中文解释
- **三种响应类型**：answer（回答）、clarification（反问）、refusal（拒绝），互斥且确定
- **反问/拒绝策略引擎**：基于 `question_policy.yml` 的 must_clarify / must_refuse 规则匹配
- **SQL 安全校验**：6 项纯规则检查（禁止写操作、强制 dim_date、白名单 JOIN、禁止 Bronze/Silver 表等）
- **跨表多指标多计划执行**：SubIntent 拆分、串行/并行执行策略、PlanExecutor
- **ResultSummary 结构化摘要**：粒度检测、数据预览、来源追溯
- **DateMerge 跨表日期对齐**：多计划结果按日期维度合并
- **CrossDomainPolicy 跨域展示策略**：交叉域因果语言禁止、隐私字段保护、未知域反问
- **ChartSpec 图表规格**：纯规则生成，不调用 LLM/DuckDB，不生成 HTML/JS
- **统一公开响应契约 v1.0**：`build_public_response()` 区分公开/内部边界，不含 SQL/trace/API Key
- **真实 DuckDB E2E 评测**：5 类场景 × 真实数据库，预检 + 报告
- **只读 REST API 服务**（Phase 6B）：3 个端点（`/health/live`、`/health/ready`、`POST /v1/ask`），AgentRuntime 受控生命周期
- **本地令牌认证**（Phase 6C）：`X-TianShu-Token` header，`hmac.compare_digest()` 恒定时间比较，fail-closed
- **进程内限流**（Phase 6C）：固定窗口 + 令牌桶，429 + Retry-After
- **请求体大小限制**（Phase 6C）：Content-Length 预检，413 拒绝
- **本地脱敏 JSONL 审计**（Phase 6C）：append-only，20+ 敏感字段自动剔除
- **安全响应头**（Phase 6C）：X-Content-Type-Options: nosniff、X-Frame-Options: DENY、Referrer-Policy: no-referrer、Cache-Control: no-store
- **本地安全闭环 runner**：8 项验证（认证/限流/审计/契约/安全扫描），自动生成报告
- **长期记忆系统**：经验复盘（R001-R013）、风险清单（RISK-001 至 RISK-034）、规则来源索引（21 条规则）、Memory Rule Enforcement
- **双基线快照系统**：Source 基线（编译+测试+harness+回归）+ Runtime 基线（真实 LLM 观察）
- **快速门禁 pre-commit hook**：5 步编译+测试+安全检查+记忆检查+Memory Harness，失败展示修复指导
- **快速门禁 CLI**（`harness/run_fast_gate.py`）：编译 → 测试 → harness → Prompt 回归 → E2E 评测
- **慢速门禁**（`harness/run_slow_gate.py`）：真实 LLM 观察模式，continue-on-error
- **12 项 Harness 安全检查**：SQL 只读、IR Schema、反问/拒绝策略、层级合规、指标注册、执行策略安全、结果融合安全、跨域策略、图表安全、PlanExecutor 安全、ResultSummary 安全、记忆更新
- **5 类 E2E 评测用例**：basic、clarification、refusal、multi_intent、safety，共 7 个 YAML 文件
- **交互式 REPL**：`tianshu-ask` 命令，支持 rule 模式和 LLM 模式
- **Windows 兼容**：GBK 编码自动检测与修复、路径适配、tmp_path 权限兼容
- **Web UI 本地问数界面**（Phase 7）：FastAPI 同源托管，原生 HTML/CSS/JS + 原生 SVG 图表，零外部 CDN 依赖
- **四种图表渲染**：原生 SVG 折线图（line）、柱状图（bar）、指标卡（metric_card）、数据表（table），未知类型自动降级
- **Web UI 安全防护**：Token 仅内存保存（闭包变量）、严格 CSP（零 unsafe-inline/unsafe-eval）、textContent 防 XSS（零 innerHTML）
- **Web UI Smoke Runner**：15 项自动化验收，启动服务 → 逐项检查 → 关闭服务 → 生成 JSON/Markdown 报告
- **68 项新测试**：静态 UI 路由（23 项）、安全（19 项）、响应/图表渲染（26 项），零 API 回归

### 变更

- 版本从 0.1.0 提升至 1.0.0
- `AgentResponse` 新增 `result_summaries`、`merged_result`、`cross_domain_decision`、`chart_spec`、`warnings`、`execution_mode` 字段（Phase 6A）
- `AgentResponse.to_dict()` 保持向后兼容
- 公开响应不含 SQL、generated_sql、trace、API Key、数据库路径
- `AgentRuntime` 使用单 Agent + asyncio.Lock + ThreadPoolExecutor 串行化（Phase 6B）
- `api_config.yml` 扩展：新增 `local_secure_mode`、`rate_limit`、`audit`、`max_body_bytes` 配置段
- FastAPI 中间件栈：security_headers → request_id → body_limit → auth → rate_limit → endpoint（Phase 6C）
- `POST /v1/ask` 只接受 `question` 字段（`extra = "forbid"`）
- README 全面重构为 v1.0 快速开始指南

### 修复

- Windows GBK 编码兼容：harness 运行器、脚本入口自动检测并切换到 UTF-8
- 控制台 Unicode 输出兜底替换（`errors="replace"`）
- pytest-asyncio Windows tmp_path 权限问题（使用 `tempfile.mkdtemp()` 替代）
- Python bytes 字面量中文编码问题（测试文件）
- 审计关键词误匹配（从字符串子串匹配改为 JSON key 精确检查）
- 固定窗口限流边界条件（retry_after 范围断言修正）

### 文档

- 新增 `CHANGELOG.md`（本文件）
- 新增 `CONTRIBUTING.md` 贡献指南
- 新增 `LICENSE` 文件（MIT）
- 新增 `VERSION` 文件
- 新增 `.env.example` 环境变量模板
- 新增 `Makefile` 一键安装/启动/验收脚本
- 新增 `docs/TROUBLESHOOTING.md` 本地故障排查（16 项常见问题）
- 新增 `examples/` 示例目录（REPL 示例 + API 请求/响应 JSON）
- 新增 `docs/text2sql_current_pipeline.md` 当前工作流说明
- 新增 `docs/text2sql_engineering_glossary.md` 工程术语表（40+ 术语）
- 新增 Phase 报告：Phase 2/6A/6B/6C 各阶段设计报告
- 更新 `docs/README.md` 文档索引与开发日志
- 更新 `docs/memory/经验复盘.md`（R012 fail-closed、R013 审计不可静默忽略）
- 更新 `docs/memory/风险清单.md`（RISK-026 至 RISK-034）

### 安全

- SQL 只读执行：所有 SQL 经过 `validate_sql_safety()` 6 项纯规则检查
- DuckDB 连接始终 `read_only=True`
- REST API 仅绑定 127.0.0.1，禁止 0.0.0.0
- CORS 关闭（`cors_enabled: false`）
- `expose_internal_errors: false`：500 错误只返回安全脱敏消息
- API 不接受 SQL/SQLPlan/表名/config/API Key 等控制参数
- 审计记录自动剔除 token/question/answer/SQL/trace/db_path 等 20+ 敏感字段
- 令牌仅通过环境变量注入，不出现于配置文件或代码
- `local_secure_mode: true` 时缺少令牌 → 503 not-ready（fail-closed）
