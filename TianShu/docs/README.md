# 文档目录说明

本目录存放项目文档、建模说明、数据规范、架构决策、项目记忆和数据仓库事实源说明。

```text
docs
├─ decisions  # 架构决策记录，解释为什么这样设计
├─ memory     # 经验复盘、风险清单、规则来源索引
├─ warehouse  # 数据仓库分层规则、数据库设计事实源、字段字典入口
├─ modeling   # ER、维度建模、星型模型、雪花模型、分层说明
├─ standards  # 规范索引入口，不重复维护具体规范
├─ meta       # 元数据设计、中文语义层、指标口径、问数模板说明
└─ silver     # Silver 白银层规划和设计文档
```

文档目录之外，项目根目录的 `harness/` 是 Agent Memory + Warehouse Harness 的工程执行入口，负责运行说明、检查清单、配置和报告入口。

## 事实源关系

- 表结构、字段、主键、类型的正式定义维护在 `docs/warehouse/database_design/`。
- 字段字典、枚举值（状态码/标志位/分类代码）的含义维护在 `docs/warehouse/data_dictionary/`。
- `docs/standards/` 只做规范索引和路由，不承载重复规范。
- `harness/` 只做工程执行入口，不承载数据库设计事实源。
- 建模方法论和设计解释维护在 `docs/modeling/`。
- 已发生问题和规则来源维护在 `docs/memory/`。
