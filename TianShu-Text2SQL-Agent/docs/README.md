# 项目文档

> TianShu Text2SQL Agent 的设计文档和开发日志。

## 目录结构

```
docs/
├── README.md                           (本文件——文档索引)
├── text2sql_current_pipeline.md        (当前工作流——工程边界和安全门禁说明)
├── text2sql_engineering_glossary.md    (工程术语表——40 个术语的完整定义)
├── TROUBLESHOOTING.md                  (本地故障排查——16 项常见问题与解决方案)
├── memory/                             (长期记忆系统——经验、风险、规则)
│   ├── 经验复盘.md                      (R001-R013：经验条目与置信演化链)
│   ├── 风险清单.md                      (RISK-001 至 RISK-034：当前风险与防线)
│   ├── 规则来源索引.md                   (规则→经验→检查→测试的追溯链)
│   └── 变更复盘模板.md                   (经验写入模板与状态生命周期)
└── planning/                           (阶段规划与设计报告)
    ├── Phase2完成与后续规划_20260616_2058.md  (Phase 2-5 路线图 v1)
    ├── Phase2完成与后续规划_v2_20260616_1500.md(Phase 2-5 路线图 v2——修订版)
	    ├── Phase6A真实DuckDB_E2E与统一响应契约_20260619_2347.md  (Phase 6A 完成报告)
	    ├── Phase6B只读REST_API与服务运行时_20260620_0715.md  (Phase 6B 完成报告)
	    ├── Phase6C本地API安全闭环与可重复验收_20260620_0750.md  (Phase 6C 完成报告)
    ├── llm_integration_design.md             (LLM 接入设计——Prompt 模板与接口)
    ├── llm_integration_phase2a.md            (LLM 接入 Phase 2A 设计报告)
    └── prompt_regression.md                  (Prompt 回归体系说明)
```

## 相关文档

- **构建方案**：`C:\Users\62414\Nutstore\1\Obsidian Vault\Ai Learning\text2sql知识积累\Text2SQL数据分析Agent构建方案_20260610_2300.md`
- **评测集设计逻辑**：`C:\Users\62414\Nutstore\1\Obsidian Vault\Ai Learning\text2sql知识积累\Text2SQL评测集的设计逻辑_20260610_2139.md`
- **TianShu 数仓设计**：`../TianShu/docs/warehouse/database_design/`
- **TianShu 契约文件**：`../TianShu/contracts/`

## 开发日志

| 日期 | 内容 |
|------|------|
| 2026-06-20 | Phase 6D 完成：v1.0 发布冻结与使用体验收尾——版本号 1.0.0、CHANGELOG、Makefile 一键验收、README 快速开始、示例目录、故障排查文档、基线冻结、git tag v1.0.0 |
| 2026-06-20 | Phase 6C 完成：本地 API 安全闭环——令牌认证（X-TianShu-Token + hmac.compare_digest）、固定窗口限流（429 + Retry-After）、Body 大小限制（413）、脱敏 JSONL 审计、安全响应头、local_secure_mode fail-closed、112 新测试 |
| 2026-06-20 | Phase 6B 完成：只读 REST API 与服务运行时——FastAPI + uvicorn、3 个端点（/health/live, /health/ready, POST /v1/ask）、AgentRuntime 受控生命周期、公共响应契约 v1.0、38 测试 |
| 2026-06-19 | Phase 6A 完成：真实 DuckDB E2E 与统一响应契约——AgentResponse 结构化产物字段、build_public_response()、真实 DuckDB E2E runner、10/10 E2E passed |
| 2026-06-16 | Phase 2A→2D 完成：跨表多指标多计划能力（SubIntent、UnifiedResponse、AgentResponse.plans），35 测试通过，零回归 |
| 2026-06-10 | 项目骨架建立：目录结构、三层 IR 定义、5 个契约文件、5 步 Harness 门禁 |
