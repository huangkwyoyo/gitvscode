# TeleSync Data Move

MySQL 到 Doris 数据迁移 Agent 项目。

## 项目目标

基于本机电信模拟数仓，构建一套可用于迁移测试的业务过程材料和后续 Agent 工程骨架。目标流程是：

1. 从 MySQL 数仓读取业务表结构、数据量和样本。
2. 设计 10 个有实际复杂度的电信业务过程。
3. 生成 MySQL 口径需求说明书、结果表 DDL、业务 SQL、校验 SQL。
4. 后续基于 LangGraph Agent 自动转换为 Doris DDL/SQL。
5. 通过 WebSQL 调度单批次任务。
6. 每批迁移后生成校验报告。

## 当前范围

当前只纳入本机 MySQL 的四个项目库：

- `ods`
- `dwd`
- `dws`
- `ads`

当前不纳入：

- `mysql`
- `information_schema`
- `performance_schema`
- `sys`
- `sakila`
- `world`
- `py_sql`

## WebSQL 环境

- 访问地址：`http://localhost:80/`
- Docker 容器名：`websql`
- 支持任务类型：SQL 脚本
- 项目目录挂载：`D:/Program Files/gitvscode/TeleSync_data_move:/app/data`
- 容器可访问：`host.docker.internal`、`127.0.0.1`、本机 MySQL、本机 FastAPI

## 目录结构

```text
app/
  api/          FastAPI 接口
  batches/      批次配置
  cli/          命令行入口
  core/         核心配置与公共能力
  data/         本地数据或临时材料
  graph/        LangGraph 状态机
  rules/        SQL 和迁移规则
  schemas/      Pydantic 模型
  services/     业务服务
config/         环境配置模板
docs/           项目文档
generated/      生成材料
scripts/        辅助脚本
tests/          测试
```

## 当前交付物

- 项目治理文档：`docs/project/`
- 标准业务过程材料：`business_processes/bp_xxx/`
- 历史集中版需求说明书：`docs/业务需求说明书/`
- 历史集中版 MySQL SQL：`generated/mysql/`
- MySQL 画像入口：`metadata/mysql_profile/`
- 项目上下文：`docs/business_context.md`

## 下一阶段

验收初始化文档和目录后，进入代码阶段：

1. 对 `business_processes/` 执行静态检查。
2. 补齐 `migration_rules/` 初版 MySQL 到 Doris 映射规则。
3. 创建 FastAPI 基础服务。
4. 创建 LangGraph 迁移状态机。
5. 建立 SQL 静态校验服务。
