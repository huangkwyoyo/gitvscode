# 项目目录结构中文说明

## 总体定位

本项目建议命名为 `telecom-dw-agent-lab`，定位是：

```text
电信业务数据仓库
+
指标体系
+
SQL 查询接口
+
FastAPI 服务
+
LangGraph Agent
+
Next.js 前端
```

它不是一次性脚本项目，而是一个可持续扩展的本地数据工程和 Agent 实验室。

## 推荐目录结构

```text
telecom-dw-agent-lab/
├── AGENTS.md
├── README.md
├── README_CN.md
├── pyproject.toml
├── .env.example
├── config/
│   ├── settings.yaml
│   ├── database.yaml
│   └── agent.yaml
├── docs/
│   ├── telecom_fields.xlsx
│   ├── data_dictionary.md
│   ├── telecom_dw_table_design_cn.xlsx
│   ├── data_warehouse_build_journey.md
│   └── project_structure_guide_CN.md
├── data/
│   ├── raw/
│   ├── generated/
│   ├── exports/
│   └── logs/
├── sql/
│   ├── create_dw_tables.sql
│   ├── ods/
│   ├── dwd/
│   ├── dws/
│   ├── ads/
│   └── checks/
├── scripts/
│   └── generate_data.py
├── src/
│   ├── telecom_dw/
│   │   ├── field_parser/
│   │   ├── data_generator/
│   │   ├── etl/
│   │   ├── metadata/
│   │   ├── metrics/
│   │   ├── sql_engine/
│   │   ├── api/
│   │   └── agents/
│   └── frontend/
└── tests/
    ├── test_data_quality/
    ├── test_metrics/
    ├── test_sql_engine/
    ├── test_api/
    └── test_agents/
```

## 根目录文件

### `AGENTS.md`

给 Codex 或其他 Agent 使用的项目约束文件。

建议包含：

- 代码注释必须使用中文
- 数仓分层规范
- SQL 命名规范
- FastAPI 规范
- LangGraph Agent 规范
- 数据质量校验要求

### `README.md` / `README_CN.md`

项目说明文档。

建议 `README.md` 用英文简述，`README_CN.md` 用中文详细说明。

### `pyproject.toml`

Python 项目的标准配置文件。

用于声明：

- 项目名称
- Python 版本
- 测试路径
- 包路径
- 后续依赖

### `.env.example`

环境变量模板。

真实密码不建议写入代码仓库。当前本地实验阶段可以使用默认配置，但后续应从 `.env` 或环境变量读取。

## `config/` 配置目录

### `config/settings.yaml`

项目总配置文件。

当前字段含义：

| 配置项 | 含义 |
|---|---|
| `project.name` | 项目名称 |
| `project.description` | 项目定位说明 |
| `project.timezone` | 默认时区 |
| `warehouse.layers` | ODS、DWD、DWS、ADS 四层定义 |
| `data_generation.seed` | 随机种子，保证模拟数据可复现 |
| `data_generation.period_start` | 模拟数据开始日期 |
| `data_generation.period_end` | 模拟数据结束日期 |
| `data_generation.user_count` | 用户规模 |
| `data_generation.billing_months` | 账单月份数 |
| `data_generation.batch_size` | 批量导入行数 |
| `data_generation.local_infile` | 是否启用 MySQL `LOAD DATA LOCAL INFILE` |
| `data_generation.output_dir` | 生成中间文件目录 |
| `data_generation.quality_report` | 数据质量报告路径 |
| `quality_rules.enforce_user_lifecycle` | 是否校验用户生命周期 |
| `quality_rules.enforce_referential_integrity` | 是否校验主外键关联 |
| `quality_rules.enforce_mobile_number_rule` | 是否校验手机号规则 |
| `quality_rules.enforce_region_hierarchy` | 是否校验省市区县层级 |
| `quality_rules.enforce_order_time_seconds` | 是否要求订单时间精确到秒 |
| `quality_rules.enforce_ods_ge_dwd` | 是否要求 ODS 行数不少于 DWD |
| `paths` | 项目关键目录 |

### `config/database.yaml`

数据库连接配置。

当前字段含义：

| 配置项 | 含义 |
|---|---|
| `mysql.host` | MySQL 主机 |
| `mysql.port` | MySQL 端口 |
| `mysql.user` | MySQL 用户 |
| `mysql.password` | MySQL 密码 |
| `mysql.charset` | 字符集 |
| `mysql.local_infile` | 是否允许本地文件导入 |
| `mysql.databases` | 四层库名映射 |
| `connection_pool.pool_size` | API 服务连接池大小 |
| `connection_pool.max_overflow` | 连接池额外连接数 |
| `connection_pool.pool_recycle_seconds` | 连接回收时间 |
| `security.sql_allow_select_only_for_agent` | Agent 是否只允许查询 SQL |
| `security.max_query_seconds` | 查询最大执行秒数 |
| `security.max_result_rows` | 查询最大返回行数 |

### `config/agent.yaml`

LangGraph Agent 配置。

当前字段含义：

| 配置项 | 含义 |
|---|---|
| `agent.framework` | Agent 框架 |
| `agent.default_language` | 默认回复语言 |
| `agent.max_retry` | 节点重试次数 |
| `agent.timeout_seconds` | 单次请求超时时间 |
| `tools.metadata_search` | 是否启用元数据检索 |
| `tools.metric_search` | 是否启用指标检索 |
| `tools.sql_generation` | 是否启用 SQL 生成 |
| `tools.sql_validation` | 是否启用 SQL 校验 |
| `tools.sql_execution` | 是否启用 SQL 执行 |
| `tools.result_explanation` | 是否启用结果解释 |
| `workflow.steps` | Agent 工作流节点顺序 |
| `guardrails.allow_dml` | 是否允许 DML |
| `guardrails.allow_ddl` | 是否允许 DDL |
| `guardrails.require_limit_for_detail_query` | 明细查询是否强制 `LIMIT` |
| `guardrails.default_limit` | 默认明细查询返回行数 |

## `docs/` 文档目录

用于保存设计过程和长期参考资料。

主要文件：

- `telecom_fields.xlsx`：原始字段清单
- `data_dictionary.md`：标准字段字典
- `telecom_dw_table_design_cn.xlsx`：四层表结构设计
- `data_warehouse_build_journey.md`：建仓过程总结
- `project_structure_guide_CN.md`：项目目录说明

## `data/` 数据目录

### `data/raw/`

原始输入文件目录。

当前可以为空，后续可放源系统导出的 CSV、Excel 或样例文件。

### `data/generated/`

模拟数据生成产物。

当前 `mysql_load/` 中保存了批量导入 MySQL 的 TSV 文件。

### `data/exports/`

查询导出、指标导出或前端下载文件目录。

### `data/logs/`

运行日志和质量报告目录。

当前保存：

- `data_quality_report.md`

## `sql/` SQL 目录

### `sql/create_dw_tables.sql`

当前 MySQL 建库建表 DDL。

### `sql/ods/`、`sql/dwd/`、`sql/dws/`、`sql/ads/`

建议后续把不同层的 SQL 拆分到各自目录。

例如：

- `sql/dwd/load_dim_user.sql`
- `sql/dws/build_user_month_summary.sql`
- `sql/ads/build_kpi_user_overview.sql`

### `sql/checks/`

数据质量校验 SQL。

建议后续沉淀：

- 生命周期校验
- 主外键校验
- 指标汇总校验
- 业务分布校验

## `src/telecom_dw/` Python 源码目录

### `field_parser/`

负责解析 `telecom_fields.xlsx`，生成标准字段字典。

### `data_generator/`

负责生成模拟数据。

当前核心脚本：

- `generate_telecom_dw_data.py`

### `etl/`

负责 ODS 到 DWD、DWD 到 DWS、DWS 到 ADS 的分层加工。

### `metadata/`

负责表、字段、主题域、主外键、血缘等元数据管理。

这是后续 Agent 查字段、查表、生成 SQL 的基础。

### `metrics/`

负责指标体系。

建议沉淀：

- 指标编码
- 指标名称
- 指标口径
- 指标 SQL 模板
- 指标依赖表
- 指标解释文本

### `sql_engine/`

负责 SQL 生成、SQL 安全校验和 SQL 执行。

后续自然语言转 SQL 会依赖该模块。

### `api/`

FastAPI 服务目录。

建议接口：

- `/metadata/tables`
- `/metadata/fields`
- `/metrics`
- `/query/sql`
- `/query/nl2sql`
- `/analysis/user-value`
- `/analysis/churn-risk`

### `agents/`

LangGraph Agent 工作流目录。

建议工作流：

```text
用户问题
-> 意图识别
-> 字段/指标检索
-> SQL 生成
-> SQL 安全校验
-> SQL 执行
-> 结果解释
-> 业务建议
```

## `src/frontend/` 前端目录

后续放 Next.js 项目。

建议名称：

```text
src/frontend/telecom-dw-web/
```

## `scripts/` 命令入口目录

放面向开发者的一键运行脚本。

当前：

- `scripts/generate_data.py`

它会调用 `src/telecom_dw/data_generator/generate_telecom_dw_data.py`。

## `tests/` 测试目录

建议分模块测试：

- `test_data_quality/`
- `test_metrics/`
- `test_sql_engine/`
- `test_api/`
- `test_agents/`

测试重点不只是代码能跑，还应验证业务规则是否成立。
