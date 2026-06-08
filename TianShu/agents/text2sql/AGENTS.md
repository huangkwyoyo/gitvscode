# Text2SQL Agent 规则

> 从属于根 `AGENTS.md`。Text2SQL Agent 必须比数据开发 Agent 更保守。

## 1. 核心原则

Text2SQL Agent 只能基于已审核的语义层和数据库设计文档生成 SQL。不能为了满足用户问题而临时创造字段或指标。

## 2. 数据源优先级

1. Gold 层（已审核的指标和星型模型）
2. Silver 层（Gold 不存在时使用标准明细表）
3. Bronze 层（仅用于排查和追溯，不用于直接回答业务问题）

## 3. SQL 生成规则

- 优先使用 Gold 事实表和维度表的 JOIN
- Gold 不存在时使用 Silver 标准明细表
- 金额字段必须使用 DECIMAL 类型
- 日期字段使用标准 DATE/TIMESTAMP 类型
- 禁止使用 `DATE::INT`（DuckDB 不兼容）
- 禁止使用无序 `ROW_NUMBER() OVER ()`
- 所有表名使用全限定名（`silver.trip_detail` 而非 `trip_detail`）

## 4. 无法回答时的行为

以下情况必须拒绝生成 SQL 并说明原因：
- 需要的字段在 Silver/Gold 中不存在
- Join 关系未经人工确认
- 指标口径未经确认
- 业务含义不确定

拒绝时必须给出：
- 缺少什么字段/关系/口径
- 可能的替代方案
- 需要人工确认的内容

## 5. 中文口径

- 用户用中文提问时，Agent 必须先理解问题对应的业务指标（参考 meta.indicator_definitions）
- 中文表名、中文字段名必须来自 Meta 元数据，不得自行翻译
- 输出的 SQL 注释必须使用中文
