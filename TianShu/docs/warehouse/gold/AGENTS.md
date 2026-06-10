# Gold 层规则

> 从属于 `docs/warehouse/AGENTS.md` 和根 `AGENTS.md`。

## 1. Gold 层职责

Gold 是业务主题建模层。**唯一职责：基于 Silver 标准层和 Meta 元数据，建设面向分析和 Agent 问数的星型模型。**

## 2. Gold 层允许做

- 主题建模（出行、安全、监管合规、资产、供给）
- 星型模型设计（事实表 + 维度表）
- 事实表设计（一行一个可度量业务事件）
- 维度表设计（一行一个分析角度）
- 汇总表设计（预聚合，直接供BI使用）
- 指标计算（SUM/AVG/COUNT，口径明确）
- 分析宽表设计
- 中文语义层建设
- 公共维度跨主题复用（dim_date、dim_taxi_zone、dim_location）

## 3. Gold 层禁止做

- 直接基于 Bronze 跳过 Silver 建模
- 直接基于想象设计指标
- 使用未确认的字段含义
- 使用未确认的 Join 关系
- 使用未确认的主键/外键
- 使用未确认的业务规则
- 编造金额、区域、车辆、司机、事故、罚单等业务属性
- Silver 层能做的事不要在 Gold 层重复做
- 使用 Google 翻译或 LLM 翻译结果直接作为正式中文表名、字段名、指标名

## 4. Gold 中文名规则

Gold 表名、字段名和指标名面向中文工程师和 Text2SQL Agent 使用，必须采用受控中文名。

中文名来源优先级：

1. `meta.column_comments` 和 `meta.table_comments` 中已审核中文名。
2. Silver 数据字典 xlsx 中已审核中文名。
3. 官方数据字典整理后的中文说明。
4. 项目人工维护术语表。

Google 翻译、LLM 翻译只能作为草稿参考，不能作为正式事实源。无法确认时写 `Human Review`，不得写成看似确定的中文名。

## 5. Gold 门禁规则

Gold 建表必须通过两类门禁：

- 设计门禁：`scripts/quality/check_gold_design.py`，检查字段中文名、英文类型、Silver 来源字段是否真实存在。
- 物理门禁：`scripts/quality/check_gold_physical.py`，检查 DuckDB 实表、字段集合、表中文注释、字段中文注释是否一致。

当前阶段为 `gold_g3_semantic_layer`，Gold G0/G1 维表、G2 明细事实表、G3 汇总表和中文语义层已全部建设完成。`harness/config/harness_targets.yml` 的 `project.stage` 应保持与此同步。`scripts/quality/run_all_checks.py` 自动执行全部 Gold 相关检查（设计门禁、物理表门禁、语义层门禁、空值画像和 Text2SQL 问数能力评测）。

## 6. Gold 指标必须包含

每个 Gold 指标必须填写：
- 指标名称
- 指标含义
- 来源表（Silver 表名）
- 来源字段
- 计算公式
- 时间口径
- 过滤条件
- 是否人工确认

未确认指标标记：
```
status: TODO
review_required: true
```

## 7. 六大业务主题域

| 主题域 | 事实表 | 维度表 |
|---|---|---|
| 出行域 | fact_trips | dim_taxi_zone、dim_date |
| 安全域 | fact_crashes、fact_crash_persons | dim_location、dim_date |
| 监管合规域 | fact_parking_violations、fact_tif_payments | dim_violation_type、dim_license_status |
| 资产域 | (可选)fact_vehicle_daily_snapshot | dim_vehicle |
| 供给域 | fact_driver_applications | dim_driver、dim_base |
| 空间地理域 | 不单独做事实表 | dim_taxi_zone、dim_location（公共维度） |

## 8. Gold 事实表粒度原则

- 事实表粒度决定分析能力。一行一程可以回答"每天每个区域多少行程"；如果预聚合成日汇总，就丢失了按小时分析的能力。
- 除非查询性能必须，优先保留细粒度。
- 预聚合汇总表（daily_zone_trip_summary等）和明细事实表可以并存。

## 9. 金额字段关联规则

如果 Bronze 源表没有金额字段，禁止在 Silver 或 Gold 层凭空新增来源型金额。金额数据必须通过关联获取：
- 停车罚单金额 → Gold 层 JOIN dim_violation_type（来自官方 xlsx）
- TIF 支付金额 → Bronze 已有，Silver 层做 VARCHAR→DECIMAL 转换

## 10. 中文语义层与 Text2SQL

Gold 层建设完成后须建立中文语义层，支撑 Text2SQL Agent 和中文问数：

- **指标定义**（`meta.metric_definitions`）：每个指标必须包含 metric_name、metric_name_zh、source_table、calculation_sql、time_key。
- **语义维度**（`meta.semantic_dimensions`）：登记可用的分组/过滤维度及其来源表。
- **问数模板**（`meta.semantic_query_templates`）：标准中文问题与对应 SQL 模板。
- **业务术语**（`meta.business_terms`）：领域缩写和专有名词的中文释义。

Text2SQL 评测通过 `scripts/quality/check_text2sql.py` 执行，基于 `harness/questions/gold_standard_questions.yml` 中的标准问题集进行五维评测（表选择、指标、SQL 可执行性、结果一致性、层级合规），报告写入 `harness/reports/`。

Text2SQL 数据源优先级：Gold G3 汇总表 > Gold G2 明细事实表 > Silver 明细层 > Bronze（仅追溯，不回答业务问题）。

## 11. 当前已知问题

- **日期维表范围**：`dim_date` 是全域事实日期维表（1997-2027，11,322 行），不是仅 2026Q1 行程日期维表。问数时需注意日期过滤。
- **停车罚单异常日期**：`fact_parking_violations.issue_date_key` 包含 1971 和 2060 等异常值。G3 汇总表 `dws_daily_parking_summary` 未主动过滤这些异常日期，需在问数口径中明确是否排除。
