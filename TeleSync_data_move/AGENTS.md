# AGENTS.md

## 1. 项目定位
本项目用于构建一套基于本机电信模拟数仓的数据迁移 Agent 工程。

当前阶段不是直接迁移生产数据，而是先在本机 MySQL 电信模拟数仓中，构造可迁移、可校验、可调度的业务过程材料。

项目最终目标是形成以下闭环：

1. 从 MySQL 数仓读取业务表结构、数据量和样本数据。
2. 基于真实业务字段设计复杂电信业务过程。
3. 生成 MySQL 口径需求说明书、结果表 DDL、业务 SQL 和校验 SQL。
4. 使用 LangGraph Agent 将 MySQL DDL/SQL 转换为 Doris DDL/SQL。
5. 通过 WebSQL 调度单批次迁移任务。
6. 每批迁移后生成结构化校验报告。
7. 将迁移规则、失败原因和人工确认点沉淀为可复用工程资产。

本项目的核心价值不是单次生成 SQL，而是沉淀一套可持续演进的数据迁移 Agent 工程流程。

## 2. 阶段目标

本项目分阶段演进，任何 Agent 在执行任务前必须先判断当前任务属于哪个阶段，不得跨阶段提前实现未要求的能力。

阶段 1：MySQL 数仓画像
目标是读取本机 MySQL 电信模拟数仓的库、表、字段、主键、索引、数据量、样本数据、字段分布和表关系。
本阶段只允许读库，不允许改库。
产物包括表结构画像、字段画像、样本数据摘要、可用于业务过程设计的候选实体和主题域。

阶段 2：MySQL 口径业务过程材料生成
目标是基于已有 MySQL 数仓，设计 10 个有实际复杂度的电信业务过程。
每个业务过程必须包含需求说明书、结果表 DDL、业务 SQL、校验 SQL、测试样例和依赖表说明。
本阶段所有 SQL 均以 MySQL 口径为准，不提前改写为 Doris 口径。

阶段 3：MySQL 到 Doris 迁移转换
目标是基于规则文件和 Agent 流程，将 MySQL DDL/SQL 转换为 Doris DDL/SQL。
转换过程必须保留原始 MySQL 材料，并输出 Doris 版本材料。
不得直接覆盖原始 SQL。

阶段 4：WebSQL 调度集成
目标是通过 WebSQL 调度单批次迁移任务。
WebSQL 只负责调度入口、SQL 执行入口和结果查看，不承载复杂业务逻辑。
复杂的迁移转换、校验、报告生成逻辑必须放在后端服务或 Agent 流程中。

阶段 5：批次校验和报告生成
目标是每批迁移后生成校验报告。
报告必须记录批次号、业务过程、源表、目标表、执行 SQL、校验 SQL、行数对比、关键指标对比、异常样本、成功/失败/阻断原因。

## 3. 目录结构约定

项目材料必须按阶段和业务过程组织，避免混放。

推荐目录结构：

docs/
  project/
    project_goal.md
    phase_plan.md
    business_process_index.md

metadata/
  mysql_profile/
    table_inventory.md
    column_profile.md
    sample_data_summary.md
    relationship_analysis.md

business_processes/
  bp_001_xxx/
    requirement_mysql.md
    result_table_mysql.sql
    business_mysql.sql
    check_mysql.sql
    test_cases.md
    lineage.md
  bp_002_xxx/
    ...

migration_rules/
  mysql_to_doris_rules.md
  ddl_mapping_rules.md
  sql_mapping_rules.md
  function_mapping_rules.md
  risk_patterns.md

doris_outputs/
  bp_001_xxx/
    result_table_doris.sql
    business_doris.sql
    check_doris.sql
    conversion_report.md

agent/
  graph/
  nodes/
  states/
  prompts/
  tools/
  validators/

reports/
  batch_YYYYMMDD_xxx/
    execution_report.md
    validation_report.md
    error_report.md

## 4. 代码规范

### 4.1 通用规范

所有代码必须遵循：

- 可读性优先于技巧性。
- 可维护性优先于代码长度。
- 明确优先于隐式。
- 先保证正确，再考虑性能优化。

禁止：

- 为了减少代码行数而降低可读性。
- 过度封装。
- 无意义抽象。
- 提前优化。

---

### 4.2 命名规范

统一使用英文命名。

要求：

- 类名：PascalCase
- 函数名：snake_case
- 变量名：snake_case
- 常量：UPPER_CASE
- 文件名：snake_case

示例：

CustomerValueService

generate_business_sql()

business_process_id

MYSQL_DEFAULT_TIMEOUT

---

### 4.3 注释规范

所有注释必须使用中文。

包括：

- 函数注释
- 类注释
- SQL注释
- 行内注释
- 文档字符串

注释应解释：

为什么这样做

而不是：

代码做了什么

错误示例：

**遍历用户列表**

for user in users:

正确示例：

**为避免一次性加载过大数据量，采用分批处理**

for user in users:

---

### 4.4 类型规范

所有公共函数必须声明类型。

禁止：

def run(data):

要求：

def run(data: MigrationTask) -> ValidationResult:

LangGraph State 必须使用 Pydantic。

禁止使用裸 dict 作为核心状态对象。

---

### 4.5 SQL规范

生成 SQL 必须遵守：

- 禁止 select *
- 字段必须显式列出
- join 条件必须完整
- 指标字段必须有业务别名
- SQL 文件必须有中文文件头说明

复杂 SQL 必须使用 CTE 分层。

示例：

WITH customer_base AS (
),
billing_summary AS (
),
result AS (
)

---

### 4.6 日志规范

统一使用 logging。

禁止：

print()

必须记录：

- task_id
- batch_id
- node_name

日志级别：

DEBUG
INFO
WARNING
ERROR

---

### 4.7 异常处理规范

禁止：

except Exception:
    pass

禁止吞异常。

所有异常必须：

- 保留原始异常
- 输出上下文信息
- 返回结构化错误

推荐：

BusinessError

ValidationError

ConversionError

ExecutionError

---

### 4.8 测试规范

核心模块必须有测试。

至少覆盖：

- SQL转换
- SQL校验
- 规则匹配
- Agent节点

新增核心逻辑时：

先补测试再提交。

---

### 4.9 配置规范

所有环境配置统一放入：

config/

禁止硬编码：

- 数据库地址
- 用户名
- 密码
- 环境名称
- API Key

统一从配置文件或环境变量读取。

## 5. 工作边界

### 5.1 数据库边界

未经明确要求：

禁止执行以下操作：

- DROP
- DELETE
- TRUNCATE
- UPDATE
- INSERT

允许：

- SHOW
- DESCRIBE
- EXPLAIN
- SELECT

当前阶段仅允许读取：

- ods
- dwd
- dws
- ads

禁止访问非项目数据库。

---

### 5.2 文件边界

未经明确要求：

禁止：

- 删除文件
- 覆盖已有业务材料
- 修改无关目录

允许：

- 新建规范目录
- 新增文档
- 新增 SQL

修改已有文件时必须说明：

- 修改原因
- 修改内容
- 影响范围

---

### 5.3 Agent边界

当前阶段目标：

构建 MySQL 业务过程材料。

允许：

- 数仓画像
- 业务过程设计
- MySQL SQL生成
- 校验SQL生成

禁止：

- 提前实现生产调度
- 提前实现全自动迁移
- 提前接入真实生产环境

---

### 5.4 Doris边界

当前阶段：

Doris 仅作为未来目标。

允许：

- 设计转换规则
- 建立映射规则

禁止：

- 为适配 Doris 修改 MySQL 原始逻辑
- 用 Doris 逻辑反向约束 MySQL 设计

MySQL 材料始终作为事实来源。

---

### 5.5 Prompt边界

禁止：

将核心迁移规则写死在 Prompt。

必须：

沉淀到：

migration_rules/

目录。

Prompt 只负责调用规则。

规则文件才是事实来源。

---

### 5.6 执行边界

未经明确要求：

禁止执行：

- 建表
- 跑批
- 数据迁移
- 数据导出

允许：

- 生成脚本
- 静态检查
- 风险分析

所有执行类操作必须经过人工确认。

---

### 5.7 报告边界

Agent 不得声称：

- 已执行成功
- 已完成迁移
- 已完成校验

除非实际执行过。

如果未执行：

必须明确标记：

【未执行，仅生成】

【未验证，仅静态检查】

禁止虚假完成。

---

### 5.8 人工确认边界

以下情况必须进入 Human Review：

- SQL 无法自动转换
- Doris 映射不确定
- 校验失败
- 数据差异超阈值
- 涉及删除或覆盖操作
- 涉及生产环境

禁止自动跳过人工审核。

---

### 5.9 项目边界

本项目目标：

沉淀 MySQL → Doris 数据迁移 Agent 工程能力。

不是：

- BI项目
- 数据大屏项目
- OLTP业务系统
- 通用数据库平台

所有设计必须围绕：

业务过程生成
↓
SQL生成
↓
SQL转换
↓
批次迁移
↓
结果校验
↓
报告生成

这条主链路展开。



## 6. 工程约定

工程约定

项目采用分层架构。

禁止业务逻辑跨层传播。

目录职责如下：

api/
接口层

agent/
LangGraph流程层

services/
业务服务层

repositories/
数据访问层

rules/
迁移规则层

validators/
校验层

reports/
报告层

--------------------------------

FastAPI

职责：

- 接收请求
- 参数校验
- 返回结果

禁止：

- 编写业务逻辑
- 编写SQL
- 调用数据库

--------------------------------

LangGraph

职责：

- 状态管理
- 节点编排
- 流程控制

禁止：

- 编写数据库访问逻辑
- 编写大量业务规则

--------------------------------

Service

职责：

- 实现业务逻辑
- 调用规则引擎
- 调用数据库访问层

--------------------------------

Repository

职责：

- 数据读取
- SQL执行

禁止：

- 编写业务规则

--------------------------------

Rule

职责：

- 存储迁移规则
- 存储转换规则
- 存储校验规则

禁止：

- 将规则写死在 Prompt 中

--------------------------------

Validator

职责：

- SQL静态检查
- DDL检查
- 配置检查
- 迁移校验

--------------------------------

状态对象

LangGraph State 统一使用 Pydantic 定义。

禁止使用 dict 任意传值。

--------------------------------

配置管理

所有配置统一放入：

config/

包括：

- mysql.yaml
- doris.yaml
- websql.yaml
- agent.yaml

禁止在代码中硬编码：

数据库地址
账号
密码
环境信息

--------------------------------

日志规范

统一使用 logging。

必须记录：

- task_id
- batch_id
- node_name

日志级别：

DEBUG
INFO
WARNING
ERROR

禁止使用 print。

--------------------------------

异常处理

所有异常必须分类：

BusinessError
ValidationError
ConversionError
ExecutionError

禁止：

except Exception:
    pass

禁止吞异常。

--------------------------------

测试要求

所有核心模块必须有测试。

至少覆盖：

- SQL转换
- 规则匹配
- 校验逻辑

Agent节点新增后必须补充测试。

--------------------------------

可追溯性

任何产物必须可追溯：

需求
↓
SQL
↓
转换
↓
执行
↓
校验
↓
报告

必须能够定位到：

是谁生成

何时生成

基于哪个版本生成

对应哪个业务过程

## 7. 上下文继承约定

每次新开对话必须优先阅读：

AGENTS.md

docs/project/project_goal.md

docs/project/current_status.md

docs/project/next_tasks.md

如果上述文件未读取完成：

禁止开始编码。

每完成一个阶段必须更新：

current_status.md

next_tasks.md



## 8. 业务过程设计标准

每个业务过程必须具备真实业务复杂度，不能只做简单 select、count、group by。

每个业务过程至少满足以下条件中的 4 项：

1. 涉及 3 张及以上业务表。
2. 包含客户、号码、套餐、账单、流量、通话、工单、渠道、基站、终端等至少两个主题域。
3. 包含时间窗口逻辑，例如日、月、近 7 天、近 30 天、账期、自然月。
4. 包含业务规则判断，例如高价值客户、异常流量、沉默用户、欠费风险、套餐适配度。
5. 包含聚合指标，例如金额、次数、时长、流量、活跃天数、投诉次数。
6. 包含维度字段，例如城市、渠道、套餐类型、客户等级、终端品牌。
7. 包含异常处理逻辑，例如 null 值、重复数据、无匹配维表、状态无效。
8. 包含校验 SQL，能够验证行数、关键指标、主键唯一性和核心字段非空。

每个业务过程必须输出以下材料：

- 业务过程名称
- 业务背景
- 输入表清单
- 输出结果表说明
- 业务口径说明
- 字段映射说明
- MySQL 结果表 DDL
- MySQL 业务 SQL
- MySQL 校验 SQL
- 测试样例
- 风险点和边界条件

## 9. SQL 生成规范

生成 SQL 时必须遵守以下要求：

1. SQL 必须可读、可审阅、可迁移。
2. 禁止生成一整坨不可读 SQL。
3. 复杂逻辑必须使用 CTE 分层表达。
4. 每个 CTE 必须有中文注释说明其业务作用。
5. 字段必须显式列出，禁止使用 select *。
6. join 条件必须显式写清楚。
7. where 条件必须体现业务时间范围或批次范围。
8. 指标字段必须有明确别名。
9. 金额、流量、时长等指标必须说明单位。
10. 涉及除法时必须处理除零风险。
11. 涉及 null 值时必须显式处理。
12. 不允许使用无法迁移或强依赖 MySQL 特性的写法，除非在转换报告中说明风险。
13. SQL 文件必须包含文件头注释，说明业务过程、输入表、输出表、执行口径和生成时间。

推荐 SQL 文件头格式：

/*
业务过程：客户月度综合价值评估
SQL 口径：MySQL
输入表：dwd_customer、dwd_user_number、dws_billing_month、dws_usage_month
输出表：ads_customer_month_value
时间口径：按账期月份统计
说明：用于识别高价值客户、低活跃高消费客户和潜在流失客户
*/

## 10. 校验 SQL 标准

校验 SQL 标准

每个业务过程必须至少提供以下校验 SQL：

1. 结果表行数校验
用于验证结果表是否生成预期数量的数据。

2. 主键唯一性校验
用于验证结果表业务主键是否重复。

3. 核心字段非空校验
用于验证客户号、号码、账期、统计日期等关键字段是否为空。

4. 指标范围校验
用于验证金额、流量、时长、次数等指标是否出现负数或异常极值。

5. 源表到结果表聚合一致性校验
用于验证核心指标在源表和结果表之间是否一致。

6. 维表关联丢失校验
用于检查 join 后是否出现大量未知、未匹配或默认值。

校验 SQL 必须输出以下字段：

- check_name：校验名称
- check_type：校验类型
- check_result：校验结果，取值 PASS / FAIL / WARN
- expected_value：期望值
- actual_value：实际值
- diff_value：差异值
- remark：中文说明

## 11. MySQL 到 Doris 转换要求

MySQL 到 Doris 转换要求

MySQL 到 Doris 的转换必须基于规则文件执行，不允许完全依赖模型自由发挥。

转换流程必须包括：

1. 读取 MySQL 原始 DDL/SQL。
2. 识别 MySQL 特有语法、函数、数据类型和风险点。
3. 根据规则文件生成 Doris DDL/SQL。
4. 生成转换差异说明。
5. 对 Doris SQL 做静态检查。
6. 保留原始 MySQL 文件，不得覆盖。
7. 输出转换报告。

转换报告必须包含：

- 原始文件路径
- Doris 输出文件路径
- 数据类型映射清单
- 函数映射清单
- SQL 改写点
- 无法自动转换的风险点
- 需要人工确认的问题
- 静态检查结果

常见映射规则必须沉淀到 migration_rules 目录，包括但不限于：

- MySQL 数据类型到 Doris 数据类型
- MySQL 日期函数到 Doris 日期函数
- MySQL 字符串函数到 Doris 字符串函数
- MySQL 聚合函数到 Doris 聚合函数
- MySQL 建表属性到 Doris 建表属性
- 主键模型、明细模型、聚合模型、唯一模型的选择规则

## 12. LangGraph Agent 约定

LangGraph Agent 约定

LangGraph 用于编排迁移任务状态流，不用于承载所有业务逻辑。

推荐状态字段包括：

- task_id：任务 ID
- batch_id：批次 ID
- business_process_id：业务过程 ID
- source_sql_path：MySQL SQL 路径
- source_ddl_path：MySQL DDL 路径
- target_sql_path：Doris SQL 路径
- target_ddl_path：Doris DDL 路径
- current_stage：当前阶段
- validation_status：校验状态
- blocking_errors：阻断错误
- warnings：警告信息
- report_path：报告路径

推荐节点包括：

1. profile_mysql_schema_node
读取 MySQL 表结构、数据量、样本数据。

2. generate_business_process_node
生成 MySQL 口径业务过程材料。

3. static_validate_mysql_sql_node
静态检查 MySQL DDL 和 SQL。

4. convert_mysql_to_doris_node
转换 Doris DDL 和 SQL。

5. static_validate_doris_sql_node
静态检查 Doris SQL。

6. submit_websql_batch_node
提交 WebSQL 单批次任务。

7. collect_execution_result_node
收集执行结果。

8. generate_validation_report_node
生成校验报告。

9. human_review_node
遇到高风险变更、无法转换 SQL 或校验失败时，进入人工确认。

节点设计要求：

- 每个节点只做一类事情。
- 节点输入输出必须使用 Pydantic 定义。
- 节点不得直接读取全局变量。
- 节点不得静默吞掉异常。
- 节点失败时必须返回结构化错误。

## 13. WebSQL 调度约定

WebSQL 仅作为任务调度和 SQL 执行入口。

禁止在 WebSQL 中编写复杂业务逻辑。

复杂逻辑必须由后端服务或 LangGraph Agent 完成。

调度流程统一为：

业务过程
↓
生成 MySQL SQL
↓
静态检查
↓
提交 WebSQL
↓
执行结果采集
↓
校验 SQL 执行
↓
生成校验报告

每个调度任务必须具备：

- batch_id
- task_id
- business_process_id
- sql_version
- submit_time
- operator
- execution_status

执行状态统一：

PENDING
RUNNING
SUCCESS
FAILED
BLOCKED

禁止使用自由文本表示状态。

所有执行 SQL 必须记录：

- SQL 文件路径
- SQL 版本
- 执行时间
- 执行耗时
- 影响行数
- 执行状态

任务失败时必须记录：

- error_code
- error_message
- error_stage
- retryable

禁止只记录“执行失败”。

调度任务必须支持：

- 单任务执行
- 单业务过程重跑
- 单批次重跑
- 全量重跑

重跑必须生成新的 batch_id。

不得覆盖历史执行记录。

所有执行记录必须可追溯。

## 14. 报告生成约定

任何执行任务结束后必须生成报告。

报告采用 Markdown 格式。

统一存放：

reports/
  batch_xxx/

报告分类：

1. execution_report.md
执行报告

2. validation_report.md
校验报告

3. conversion_report.md
转换报告

4. error_report.md
异常报告

--------------------------------

执行报告必须包含：

- batch_id
- task_id
- business_process_id
- execution_start_time
- execution_end_time
- duration
- execution_status

输入：

- 源表
- SQL 文件

输出：

- 结果表
- 行数

异常：

- 错误信息
- 阻断原因

--------------------------------

校验报告必须包含：

基础校验

- 行数校验
- 主键校验
- 非空校验
- 指标校验

结果：

PASS
FAIL
WARN

校验结果必须结构化展示：

| 校验项 | 结果 | 期望值 | 实际值 |
| ------ | ---- | ------ | ------ |

--------------------------------

转换报告必须包含：

MySQL文件

↓

Doris文件

转换内容：

- 类型映射
- 函数映射
- SQL改写

风险点：

- 自动转换成功
- 自动转换失败
- 需人工确认

--------------------------------

异常报告必须包含：

错误时间

错误阶段

错误SQL

错误信息

建议处理方案

影响范围

重试建议

禁止只记录堆栈信息。

## 15. Agent 执行规则

Agent 执行规则

每次开始任务前，Agent 必须先阅读：

1. AGENTS.md
2. docs/project/project_goal.md
3. docs/project/phase_plan.md
4. 当前任务相关目录下的 README 或说明文件
5. 已存在的同类产物

Agent 不得在不了解现有结构的情况下直接新建大量文件。

执行任务时必须遵守：

1. 先复述当前任务属于哪个阶段。
2. 说明计划修改或新增哪些文件。
3. 优先修改已有结构，不重复造轮子。
4. 新增文件必须放入约定目录。
5. 修改完成后必须说明改了什么、为什么改、如何验证。
6. 如果无法验证，必须明确说明未验证原因。
7. 不得声称“已完成测试”，除非实际执行过测试命令或 SQL 检查。

当上下文过长需要新开对话时，新对话必须先读取：

- AGENTS.md
- docs/project/project_goal.md
- docs/project/phase_plan.md
- docs/project/current_status.md
- docs/project/next_tasks.md

因此，每个阶段结束时必须更新 current_status.md 和 next_tasks.md。

## 16. 禁止事项

禁止事项

未经明确要求，禁止执行以下操作：

1. 删除数据库、删除表、清空表、更新业务数据。
2. 修改非项目相关数据库。
3. 在没有备份或说明的情况下覆盖已有 SQL 材料。
4. 将 MySQL SQL 直接改写成 Doris SQL 并覆盖原文件。
5. 生成没有校验 SQL 的业务过程。
6. 生成没有字段说明的结果表 DDL。
7. 生成无法解释业务口径的指标。
8. 把迁移规则只写在提示词里，而不沉淀到规则文件。
9. 把复杂业务逻辑写死在 FastAPI 接口层。
10. 把 WebSQL 当作主要业务逻辑执行引擎。
11. 在没有静态检查的情况下进入执行阶段。
12. 对失败任务只返回失败，不记录失败原因。

## 17. 完成标准

完成标准

任何任务声称完成前，必须满足对应完成标准。

MySQL 画像任务完成标准：

- 已列出相关库表清单。
- 已记录表字段、字段类型、字段注释。
- 已统计表数据量。
- 已抽取样本数据。
- 已识别候选主键、时间字段和关联字段。
- 已输出画像文档。

业务过程生成任务完成标准：

- 已生成需求说明书。
- 已生成 MySQL 结果表 DDL。
- 已生成 MySQL 业务 SQL。
- 已生成 MySQL 校验 SQL。
- 已说明输入表、输出表、业务口径。
- 已完成静态检查。
- 已说明未实际执行的部分。

迁移转换任务完成标准：

- 已保留 MySQL 原始材料。
- 已生成 Doris DDL。
- 已生成 Doris SQL。
- 已生成转换报告。
- 已列出类型映射、函数映射和风险点。
- 已完成静态检查。

批次执行任务完成标准：

- 已记录 batch_id。
- 已记录执行 SQL。
- 已记录执行状态。
- 已记录成功、失败、阻断原因。
- 已生成校验报告。



# Git Workflow

所有开发必须遵循 Feature Branch 工作流。该规则优先于临时使用的 `codex/*` 工作分支；如果当前工作仍在 `codex/*` 分支上，进入正式开发前必须切换到符合规范的 `feature/*` 分支。

## 分支规则

- `main` 是唯一长期存在的稳定分支。
- 禁止直接修改或直接提交到 `main`。
- 每个功能、修复或阶段性交付必须创建独立 Feature Branch。
- 一个 Feature Branch 只承载一个清晰目标，禁止多个功能混用同一分支。

命名规范：

```text
feature/<feature-name>
```

命名要求：

- `<feature-name>` 使用英文小写、数字和短横线。
- 名称必须能表达功能范围。
- 禁止使用空泛名称，例如 `feature/update`、`feature/test`、`feature/temp`。

示例：

```text
feature/sql-generator
feature/rag-knowledgebase
feature/github-daily-report
feature/agent-memory
feature/mysql-profile-docs
feature/doris-conversion-rules
```

## 开发流程

1. 从 `main` 创建 Feature Branch。

```bash
git checkout main
git pull origin main
git checkout -b feature/<feature-name>
```

2. 在当前 Feature Branch 完成功能开发。

3. 提交前检查当前分支和变更范围。

```bash
git branch --show-current
git status --short
```

4. 提交代码。

```bash
git add <path>
git commit -m "feat: <feature-name>"
```

5. 推送远程仓库。

```bash
git push -u origin feature/<feature-name>
```

6. 创建 Pull Request。

source:

```text
feature/<feature-name>
```

target:

```text
main
```

7. Pull Request 描述必须包含：

- 功能说明
- 修改文件列表
- 风险分析
- 测试结果
- 未执行测试时必须明确说明原因，禁止写“已测试”但没有真实测试记录。

8. Pull Request 合并后删除 Feature Branch。

```bash
git branch -d feature/<feature-name>
git push origin --delete feature/<feature-name>
```

## 禁止事项

- 禁止长期使用单一 `codex/*` 分支承载所有开发。
- 禁止直接提交到 `main`。
- 禁止多个功能共用一个 Feature Branch。
- 禁止在未确认变更范围时执行 `git add .`。
- 禁止把无关目录、临时文件、依赖缓存、数据库文件一起提交。
- 禁止提交包含明文密码、Token、API Key 的配置文件。

## Agent 提交流程补充

Agent 执行 Git 操作前必须：

1. 运行 `git status --short --branch` 确认当前分支。
2. 说明本次计划提交的文件范围。
3. 只暂存与当前任务相关的文件或目录。
4. 提交前运行 `git diff --cached --name-status` 核对暂存清单。
5. 如果发现无关文件已暂存，必须先停止并请求人工确认。
6. 提交后运行 `git log -1 --oneline` 记录提交号。
7. 推送后说明远端分支和提交号。
