# AGENTS.md

## 0. 数据仓库 Agent 项目第一原则

数据库设计文档是本项目的唯一事实源。

AI 不允许脱离 Bronze 原始字段和数据库设计文档创造字段。任何字段新增、删除、改名、类型变化，都必须通过文档更新、PR 审核和一致性检查。

AGENTS.md 不是知识垃圾桶，而是规则入口。详细规则必须拆分到对应文档，并定期与代码和数据库保持一致。

数据库设计文档拥有最高优先级。其他文档可以暂时没有，数据库设计文档必须存在、可追溯、可审查、可复用。

表、字段、主键、外键、指标、类型、中文名、字段注释、表注释的新增、删除、改名、类型变化，必须遵守以下流程：

```text
提交数据库设计变更 PR
  ↓
更新数据库设计文档
  ↓
更新字段字典
  ↓
通过一致性检查
  ↓
用户 Review
  ↓
合入
  ↓
同步开发库
  ↓
同步所有线上库
```

冲突处理规则：

- 文档与开发库不一致时，不得继续向线上库同步。
- 代码、SQL、Excel 字典、Markdown 规划、DuckDB 实际 schema 冲突时，必须进入审核流程。
- 未经过数据库设计文档确认的字段变更，直接驳回。
- 全局表字段变更应由独立项目或独立模块维护，其他研发和 Agent 只能通过 PR 申请复用。

## 强制前置阅读（路由表——非"仅供参考"，而是"必须先读"）

以下指令不是"有空再看"的建议。**在对应任务开始前，你必须调用 Read 工具按顺序读取指定文件。** 跳过前置阅读直接开始工作 = 违反本文件最高原则。

### 做 Silver 层字段设计 / 建表前 → 必须先读

| 顺序 | 文件 | 为什么必须读 |
|---|---|---|
| 1 | `docs/warehouse/silver/AGENTS.md` | Silver 能做什么、不能做什么 |
| 2 | `docs/memory/风险清单.md` | 已知高风险点（虚构字段、金额幻觉、SQL方言、硬编码枚举、不稳定主键） |
| 3 | `docs/memory/经验复盘.md` | 搜索"金额""字段来源""派生"关键词，找相关教训 |
| 4 | `docs/warehouse/database_design/silver_database_design.md` | 当前 Silver schema 事实源 |
| 5 | `docs/decisions/004-primary-key-strategy.md` | 主键策略（代理键/复合键/哈希键的选择依据） |
| 6 | `docs/warehouse/data_dictionary/` | 字段中文名、枚举值含义 |

### 做 Gold 层建模 / 建表前 → 必须先读

| 顺序 | 文件 | 为什么必须读 |
|---|---|---|
| 1 | `docs/warehouse/gold/AGENTS.md` | Gold 能做什么、不能做什么 |
| 2 | `docs/warehouse/database_design/silver_database_design.md` | 确认 Silver 有哪些可用字段 |
| 3 | `docs/decisions/006-parking-violation-amount-in-gold.md` | 金额字段为何放 Gold 而非 Silver |
| 4 | `docs/warehouse/database_design/gold_database_design.md` | 当前 Gold schema 事实源 |

### 修改任何数据库 Schema（Bronze/Silver/Gold）前 → 必须先读

| 顺序 | 文件 | 为什么必须读 |
|---|---|---|
| 1 | `docs/warehouse/database_design/`（该层的设计文档） | 当前 schema 事实源 |
| 2 | `docs/decisions/004-primary-key-strategy.md` | 主键策略决策依据 |
| 3 | `harness/checklists/schema_change_review.md` | Schema 变更审核清单 |
| 4 | `docs/decisions/002-bronze-silver-gold-layering.md` | 三层分层架构决策（理解变更对各层的影响） |

### 做数据查询 / Text2SQL 前 → 必须先读

| 顺序 | 文件 | 为什么必须读 |
|---|---|---|
| 1 | `agents/text2sql/AGENTS.md` | Text2SQL 规则（优先用 Gold、无法确认必须反问） |
| 2 | `docs/warehouse/database_design/` | 可用表和字段 |
| 3 | `docs/warehouse/data_dictionary/` | 字段中文名、枚举值含义 |

### 审核任何 Agent 产出前 → 必须先读

| 顺序 | 文件 | 为什么必须读 |
|---|---|---|
| 1 | `agents/review/AGENTS.md` | 审核 Agent 规则（守门人，只拦截不圆场） |
| 2 | `docs/warehouse/database_design/`（相关层的设计文档） | 对照事实源逐项检查 |
| 3 | `docs/memory/风险清单.md` | 对照已知风险点检查 |
| 4 | `harness/checklists/schema_change_review.md` | Schema 变更审核清单 |

### 项目状态与决策查询 → 按需读取

| 文件 | 何时读 |
|---|---|
| `PROJECT_STATUS.md` | 首次进入项目、阶段切换时 |
| `docs/decisions/README.md` | 需要了解所有架构决策时 |
| `docs/decisions/001~006-*.md` | 需要理解某个具体决策的背景时 |
| `docs/standards/` | 需要查命名/文档/建表规范时 |
| `harness/README.md` | 需要了解 Harness 怎么运行时 |
| `docs/warehouse/data_dictionary/bronze_enum_values.md` | 需要翻译 Bronze 代码/缩写为中文时 |

> **完成上述前置阅读后**：返回到本文件，继续执行 §§1-13 中对应层级的规则。前置阅读是"了解上下文"，本文件的规则是"行动约束"——两者缺一不可。

---

## 1. 项目定位

本项目基于 NYC 城市交通开放数据，构建 Bronze → Silver → Gold 数据仓库，并为后续数据分析 Agent、Text2SQL Agent、数据开发 Agent 提供可信数据底座。

当前核心目标：

- 基于 Bronze 原始数据建立 Silver 标准层
- 基于 Silver 和 Meta 建立 Gold 主题模型
- 建立中文语义层
- 避免 AI 编造字段、指标、金额、关联关系和业务口径

---

## 2. 数据真源原则

所有建模必须基于真实来源。

来源优先级：

1. Bronze 实际字段和样本数据（通过 `DESCRIBE` / `SELECT * LIMIT 10` 获取）
2. `meta.source_columns`（构建脚本自动生成，与 Bronze 同步，可信）
3. 官方数据字典 xlsx（仅用于补充枚举值说明和业务含义，**不得用于确认字段是否存在**）
4. 数据画像结果（缺失率、唯一性校验等）
5. 人工确认结果

Agent 不得使用常识、训练知识或猜测补充字段和业务含义。

字段中的代码、缩写、状态标识必须在字段字典中补充中文含义；无法确认官方含义时，必须标记 `Human Review`，不得凭经验翻译为正式口径。

无法确认时，必须标记：

- TODO
- Human Review

---

## 3. 零幻觉建模原则

Agent 只能整理事实，不能创造事实。

禁止编造：

- 表名
- 字段名
- 字段含义
- 主键
- 外键
- Join 关系
- 金额
- 指标
- KPI
- 业务规则
- 地理归属
- 业务口径
- 根据官方数据字典（xlsx）推断 Bronze 表包含某字段（必须以 `DESCRIBE` 结果为准）

任何不来自 Bronze 或 Meta 的内容，都不得直接进入 Silver 或 Gold。

---

## 4. Bronze 层原则

Bronze 是原始层。

要求：

- 保留原始字段
- 保留原始结构
- 保留原始数据类型或记录原始类型
- 不做业务改造
- 不生成指标
- 不修改字段含义

Bronze 的职责是提供事实来源。

---

## 5. Silver 层规范

Silver 是标准化层，不是业务建模层。

Silver 允许做：

- 字段命名标准化
- 数据类型标准化
- 时间字段标准化
- 空值标注
- 异常值标注
- 枚举值清洗
- 去重规则定义
- 数据质量规则定义

Silver 禁止做：

- 新增 Bronze 不存在的业务字段
- 删除 Bronze 字段
- 编造金额字段
- 编造地理字段
- 编造指标
- 编造 KPI
- 推断主键
- 推断外键
- 推断 Join 关系
- 聚合统计
- 业务结论分析

Silver 字段必须能追溯到 Bronze 字段。

如果确实需要派生字段，必须标记：

```text
review_status: TODO
reason: 需要人工确认派生规则
```

## 6. Gold 层规范

Gold 是业务主题建模层。

Gold 必须基于：

- Silver 标准层
- Meta 元数据
- 人工确认的业务规则

Gold 可以做：

- 主题建模
- 星型模型设计
- 事实表设计
- 维度表设计
- 汇总表设计
- 指标计算
- 分析宽表设计
- 中文语义层建设

Gold 禁止做：

- 直接基于想象设计指标
- 直接基于 Bronze 跳过 Silver 建模
- 使用未确认的字段含义
- 使用未确认的 Join 关系
- 使用未确认的主键 / 外键
- 使用未确认的业务规则
- 编造金额、区域、车辆、司机、事故、罚单等业务属性

Gold 中的每个指标必须包含：

- 指标名称
- 指标含义
- 来源表
- 来源字段
- 计算公式
- 时间口径
- 过滤条件
- 是否人工确认

未确认指标必须标记为：

```
status: TODO
review_required: true
```

------

## 7. Meta 元数据规范

Meta 用于解释数据，不得替代数据事实。

Meta 应包含：

- 表说明
- 字段说明
- 字段中文名
- 字段业务含义
- 数据类型
- 枚举值说明
- 数据质量问题
- 字段来源
- 是否人工确认

如果 Meta 与 Bronze 冲突：

以 Bronze 实际字段为准。

如果 Meta 与业务规则冲突：

进入 Human Review。

------

## 8. ER 与星型模型规则

ER 模型用于描述复杂实体关系。

星型模型用于支撑分析查询。

允许建立：

- 事故 ER 子模型
- 出行事实模型
- 罚单事实模型
- 车辆维度模型
- 司机维度模型
- 区域维度模型
- 日期维度模型

但所有关系必须来自：

- 真实字段
- 数据画像
- Meta 说明
- 人工确认

禁止凭字段名相似直接确定 Join 关系。

------

## 9. 中文语义层规范

中文语义层服务于 Data Analysis Agent 和 Text2SQL Agent。

中文语义层必须基于：

- Silver 字段
- Gold 指标
- Meta 说明
- 人工确认口径

禁止把猜测性的中文解释写入正式语义层。

不确定内容必须标记：

```
待确认
```

------

## 10. Human Review 触发条件

以下情况必须进入人工确认：

- 新增字段
- 派生字段
- 指标计算
- 主键判断
- 外键判断
- Join 关系
- 金额逻辑
- 地理归属
- 事故关系建模
- 罚单业务口径
- 车辆/司机关联关系
- 中文语义解释不确定

------

## 11. 完成标准

任何 Silver 或 Gold 建模任务完成前，必须说明：

- **是否完成了强制前置阅读路由表中对应任务的全部预读项**（如未完成，先补读再提交）
- 读取了哪些 Bronze 表
- 使用了哪些 Meta 文件
- 生成了哪些表
- 是否新增字段
- 是否存在派生字段
- 是否存在 TODO
- 是否存在 Human Review 项
- 是否通过字段对照检查
- 是否存在潜在幻觉风险

禁止只说“已完成”。

------

## 12. 核心原则

Bronze 提供事实。

Meta 提供解释。

Silver 整理事实。

Gold 建模业务。

Agent 不得创造事实。


## 13. 变更传播规则

每次执行以下操作时，必须同步扫描并更新受影响的所有项目文件：

### 13.1 触发条件

| 操作类型 | 触发条件 |
|---|---|
| **建表/改表** | 新建或修改 Silver/Gold/Meta 层的表结构、字段、行数 |
| **新建脚本** | 新增 `scripts/` 下的构建或质量检查脚本 |
| **新发现** | 发现并确认的枚举值含义、数据质量问题、编码手册验证结果 |
| **阶段完成** | 一个构建批次（P0/P1/P2）或里程碑完成 |
| **新增/修改关键文档** | 新增或重大修改 `docs/decisions/`、`docs/memory/`、`harness/`、`AGENTS.md` |

### 13.2 传播清单

操作完成后，必须逐项检查以下文件是否需要更新：

| 文件 | 何时更新 |
|---|---|
| `docs/warehouse/database_design/` | 表结构、字段数、主键变更时 |
| `docs/warehouse/data_dictionary/bronze_enum_values.md` | Bronze 枚举值新增或确认时 |
| `sql/{schema}/README.md` | 该 schema 的表清单、行数、构建方式变更时 |
| `sql/README.md` | 目录结构新增或调整时 |
| `docs/silver/Silver白银层规划.md` | 规划与实建不一致时 |
| `scripts/silver/_gen_xlsx.py` | 字段定义变更时（需重新生成 xlsx） |
| `PROJECT_STATUS.md` | 阶段完成或重大变更时 |
| `docs/memory/` | 新的经验复盘、分析报告、验证记录产生时 |
| `harness/checklists/` | 新增质量检查或门禁规则时 |
| `AGENTS.md`（本文件） | 新规则或流程变更时 |

### 13.3 执行顺序

1. 完成核心操作（建表/修字段/确认枚举值）
2. 更新最高事实源（`docs/warehouse/database_design/`）
3. 更新字段字典（`docs/warehouse/data_dictionary/`）
4. 更新 SQL 目录说明（`sql/{schema}/README.md`）
5. 更新项目状态（`PROJECT_STATUS.md`）
6. 运行质量门禁（`python scripts/quality/run_all_checks.py`）
7. **判断是否触发 13.4 的记忆写入条件**：
   - 若满足 13.4 中任一条件 → 强制执行记忆写入，不得跳过
   - 若不满足（操作顺利完成，无踩坑）→ 输出"本次无踩坑，跳过记忆写入"即可，不得编造内容

### 13.4 记忆写入强制要求

以下情况**必须**写入 `docs/memory/经验复盘.md`：

| 触发条件 | 示例 |
|---|---|
| SQL/数据库方言兼容问题导致的错误 | DuckDB `DATE::INT` 报错、`INSERT OR REPLACE` 无约束 |
| 数据格式与预期不一致导致的结果异常 | crash_at 全 NULL、trip_id 碰撞 |
| 主键/代理键策略失败 | MD5 碰撞、ROW_NUMBER 别名引用 |
| 变更传播遗漏 | 建完表后发现关联文档未更新 |

每条记录必须包含：日期、来源问题、根因、风险、落地规则/检查。

### 13.5 输出要求

禁止只说"已完成"。变更完成后必须列出：
- 更新了哪些文件
- 每处改了什么（一行说明）
- 是否写入 `docs/memory/`，如未写入说明原因

### 13.6 强制质量门禁（Harness 执行保障）

任何涉及以下操作的动作完成后，**必须立即运行质量门禁**，检查不通过则不得进入下一步：

| 操作 | 必须运行的检查 | 不通过时的处理 |
|---|---|---|
| `CREATE TABLE`（任何 schema） | `python scripts/quality/run_all_checks.py` | 修到通过为止，不得跳过 |
| 修改已有表的字段定义 | 同上 + `check_schema_consistency.py --require-silver-tables`（如适用） | 对齐设计文档后重跑 |
| 新增/修改 `_gen_xlsx.py` 字段定义 | 重新生成 xlsx + `run_all_checks.py` | 确认字段数一致 |
| Bronze 枚举值新增 | `check_silver_dictionary.py` | 确认枚举值来源可追溯 |

**禁止行为**：
- 禁止在检查失败后直接进入下一张表的构建。
- 禁止用 `--dry-run` 绕过检查。
- 禁止在检查失败后只报告不修复。

这条规则是 Harness 工程的执行保障——Harness 提供了检查脚本，本条规则确保它们**一定会被执行**。

**操作前基线检查**：除了操作后跑检查，**操作前也必须跑一次检查**以确认当前基线状态：
- 建表/改表前：运行 `python scripts/quality/run_all_checks.py`，确认当前基线全部通过
- 如果基线本身有失败项：先修复或记录，再开始新操作
- 目的：避免在已有问题的基线上叠加新变更，导致问题归属不清

### 13.8 数据开发 Agent 执行清单

本节是面向人类工程师的规则概述。面向 Agent 的场景化执行清单定义在 `agents/dev/AGENTS.md` 中。数据开发 Agent 在执行建表/改字段/增指标/改语义层操作时，必须遵循该文件中的四大场景清单（场景 A：新增表、场景 B：修改字段、场景 C：新增指标、场景 D：修改语义层）。

### 13.9 设计原则

- `docs/standards/` 只做索引路由，不复制具体规范。
- `docs/warehouse/database_design/` 是唯一事实源，其他文档必须与之对齐。
- `docs/warehouse/data_dictionary/` 维护字段中文名和枚举值含义。
- `sql/` 的 README.md 是给开发者看的快速索引，不是事实源。
- `PROJECT_STATUS.md` 是项目进度快照。
- `docs/memory/` 是分析过程归档，不是规范。


## 14. 代码规范

- 所有代码注释必须使用中文，包括函数注释、变量说明、行内注释、文档字符串等。
- 注释应简洁明了，解释”为什么”而非”是什么”。
- 函数和类使用简短的中文 docstring 说明用途。

## 15. 数据文档与建模规范

- 所有生成的数据文档都必须采用“英文名 + 中文名”并列口径。
- 表名、字段名、主键、外键、候选键、索引、约束、指标名、枚举值等，只要出现英文技术名，后一列或紧邻位置必须提供中文名或中文说明。
- **字段类型使用英文名**。数据类型列统一使用数据库原生英文类型名，如 `VARCHAR`、`INT`、`BIGINT`、`BOOLEAN`、`DOUBLE`、`FLOAT`、`TIMESTAMP`、`DATE`、`TIME` 等。不需要附带中文说明。
- **涉及金额、费用、收入等货币类字段，类型统一使用 `DECIMAL`**。包括但不限于：票价（fare_amount）、总费用（total_amount）、小费（tips）、通行费（tolls）、罚款金额（fine_amount）、滞纳金（penalty_amount）、支付金额（payment_amount）、司机收入（driver_pay）等。金额字段不得使用 `DOUBLE` 或 `FLOAT`，避免浮点精度问题。
- 表格类文档推荐字段顺序：
  - 英文表名、中文表名、英文字段名、中文字段名、英文主键名、中文主键说明。
- 如果是字段级数据字典，必须至少包含：
  - 英文字段名、中文字段名、数据类型（英文类型名，如 `VARCHAR`、`BIGINT`、`DOUBLE`）、字段层级、业务含义、治理备注。
- 如果是表级数据目录，必须至少包含：
  - 英文表名、中文表名、数据域、数据角色、主键/候选键、主要关联键、来源路径。

## 16. DuckDB / SQL 建表规范

- 建表时，物理表名和物理字段名可以使用英文，但必须同步提供中文注释。
- 每张表建成后必须写入中文表名或中文表说明。
- 每个字段建成后必须写入中文字段注释。
- 如果目标数据库原生支持 `COMMENT ON TABLE` 和 `COMMENT ON COLUMN`，优先使用原生注释语句。
- 如果目标数据库不稳定支持原生注释，必须在 `meta` schema 中维护表注释和字段注释，例如：
  - `meta.table_comments`
  - `meta.column_comments`
- 建表脚本不得只创建英文表结构而不生成中文语义元数据。

## 17. Agent 输出要求

- 当 Agent 生成数据规范、数据字典、建表 SQL、DuckDB schema、ER 图、星型模型、ODS/DWD/DWS/ADS 分层设计时，必须同时输出英文技术名和中文业务名。
- Agent 不得假设中文名“以后补充”；如果无法确定准确中文名，必须显式标注为“待确认中文名”并说明原因。
- 面向中文用户的最终文档应优先保证中文可读性，英文名用于精确落库和工程实现。
