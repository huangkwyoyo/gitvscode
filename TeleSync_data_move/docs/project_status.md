# 项目状态

## 当前阶段

项目处于 MySQL 业务过程材料标准化阶段。

## 已完成

- 已确认项目范围：MySQL 到 Doris 数据迁移模拟项目。
- 已确认项目数据库范围：`ods`、`dwd`、`dws`、`ads`。
- 已确认 WebSQL 环境信息。
- 已读取 MySQL 数仓元数据、行数、日期范围和样本。
- 已规划 10 个电信业务过程。
- 已生成 10 个需求说明书。
- 已生成 10 个 MySQL 口径 SQL 材料。
- 已创建标准项目目录结构。
- 已创建根级 `AGENTS.md`。
- 已创建 `README.md`。
- 已创建 `docs/business_context.md`。
- 已创建 `docs/project_status.md`。
- 已补齐 `docs/project/` 五个项目治理文档。
- 已按 `business_processes/bp_xxx/` 重组 10 个业务过程。
- 已拆分每个业务过程的 DDL、业务 SQL、校验 SQL。

## 待验收

- 项目目录结构是否符合预期。
- 根级 `AGENTS.md` 是否作为后续开发约束。
- `README.md` 是否准确描述项目。
- `docs/business_context.md` 是否覆盖业务上下文。
- `docs/project_status.md` 是否能作为进度跟踪入口。

## 下一步建议

验收通过后再继续：

1. 创建 Python 项目基础配置。
2. 初始化 FastAPI 服务。
3. 初始化 LangGraph 状态模型。
4. 建立批次配置格式。
5. 建立 SQL 静态校验规则。
6. 将 10 个 MySQL SQL 材料纳入批次管理。

## 风险与注意事项

- 当前 SQL 材料尚未执行建表或写入。
- 当前 SQL 材料仍需做 MySQL 语法级校验。
- 后续 Doris 转换前，需要先冻结 MySQL 口径需求。
- WebSQL 只支持 SQL 脚本，不适合直接承载复杂 Agent 执行逻辑。
