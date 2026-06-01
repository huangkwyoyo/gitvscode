# 电信数据仓库建设过程总结与经验

## 建设目标

本项目的目标不是只建一批 MySQL 表，而是构建一个可在个人电脑运行的电信业务数据仓库实验室，用于后续训练和验证：

- 指标体系设计
- SQL 查询接口
- FastAPI 服务
- LangGraph Agent
- 自然语言查指标
- 自动生成 SQL
- 指标口径解释
- 用户价值分析
- 流失风险识别
- 营销人群圈选
- 套餐推荐
- 账单异常分析

## 已完成的关键工作

### 1. 字段清单分析

起点是 `docs/telecom_fields.xlsx`。该文件不是普通字段字典，而是一组电信经分和即席查询视图字段清单，包含用户、账单、充值、欠费、订购、投诉、终端、结算、DPI 等业务主题。

建设时没有直接照抄源系统字段名，而是先抽取中文字段含义，再重构为企业级数仓标准字段。

### 2. 字段标准化

字段命名统一为英文 `snake_case`，并强制遵守后缀和前缀规范：

- ID 字段：`xxx_id`
- 编码字段：`xxx_code`
- 名称字段：`xxx_name`
- 类型字段：`xxx_type`
- 状态字段：`xxx_status`
- 标志字段：`is_xxx`
- 金额字段：`xxx_amount`
- 费用字段：`xxx_fee`
- 次数字段：`xxx_count`
- 日期字段：`xxx_date`
- 时间字段：`xxx_time`
- 比率字段：`xxx_rate`
- 比例字段：`xxx_ratio`
- 时长字段：`xxx_duration`
- 流量字段：`xxx_usage_mb`
- 分钟字段：`xxx_usage_min`

经验：字段标准化必须早于建表。否则后续 API、指标、Agent 和前端都会被源系统缩写、内部编码和历史命名拖累。

### 3. 分层建模

MySQL 按数仓层级拆成四个库：

- `ods`
- `dwd`
- `dws`
- `ads`

表使用全限定名，例如：

- `ods.ods_user_profile_daily`
- `dwd.dim_user`
- `dwd.fact_billing_monthly`
- `dws.dws_user_month_summary`
- `ads.ads_kpi_user_overview_monthly`

经验：库名直接对应分层，比只靠表名前缀更清晰，也更适合后续权限控制、SQL 生成和 Agent 表检索。

### 4. ODS 表命名修正

建设过程中明确禁止把源系统视图名和内部口径写入设计表名，例如：

- 不使用 `新即席查询日视图_3.0`
- 不使用 `360`
- 不使用 `NDH101`

修正后的命名改为业务含义，例如：

- `ods.ods_user_profile_daily`
- `ods.ods_user_profile_monthly`

经验：ODS 虽然保留源层含义，但设计表名仍应面向业务，不能把临时报表、即席查询菜单或内部模型编号固化为数仓资产。

### 5. MySQL 建库建表

已在本地 MySQL 创建：

- `ods`：31 张物理表
- `dwd`：17 张物理表
- `dws`：8 张物理表
- `ads`：9 张物理表

由于部分 ODS 表字段过宽，超过 InnoDB 单行大小限制，采用了物理拆分：

- `ods.ods_arrears_daily_part1~part3`
- `ods.ods_combo_product_monthly_part1~part5`

这些拆分表使用 `synthetic_row_id` 关联同一原始行。

经验：模拟企业宽表时，必须考虑 MySQL 的真实限制。设计文档可以保留逻辑表，但物理落库需要可运行的拆分策略。

### 6. 模拟数据生成

第一版数据生成后发现 DWD 行数大于 ODS，这不符合严格数仓分层关系。随后修正为：

```text
ODS > DWD > DWS > ADS
```

当前数据规模：

| 层 | 表数 | 行数 |
|---|---:|---:|
| ODS | 31 | 12,080,000 |
| DWD | 17 | 10,460,065 |
| DWS | 8 | 1,202,555 |
| ADS | 9 | 108 |

经验：ODS 不能只是样本层。哪怕是模拟项目，也应该体现“原始接入层到明细清洗层再到汇总层”的数据量递减关系。

### 7. 生命周期质量校验

发现并修正了业务时间问题：

- 入网时间必须小于离网时间
- 账单、充值、使用、订单、投诉、DPI 等业务时间必须在入网和离网之间
- 订单创建时间、支付时间和业务时间必须精确到时分秒
- 支付时间不能早于订单创建时间

最终校验结果均为 0 异常。

经验：模拟数据不能只看行数。时间逻辑、生命周期逻辑、主外键逻辑和业务分布逻辑同样重要。

## 当前资产

核心文档：

- `docs/data_dictionary.md`
- `docs/telecom_dw_table_design_cn.xlsx`
- `docs/data_warehouse_build_journey.md`
- `docs/project_structure_guide_CN.md`

核心 SQL：

- `sql/create_dw_tables.sql`

核心脚本：

- `src/telecom_dw/data_generator/generate_telecom_dw_data.py`
- `scripts/generate_data.py`

数据和报告：

- `data/generated/mysql_load/`
- `data/logs/data_quality_report.md`

## 后续建议

下一阶段不建议继续堆数据量，而应该进入语义层和服务层：

1. 建立指标口径表和指标文档。
2. 实现 `metadata` 模块，提供表、字段、主外键、血缘检索。
3. 实现 `metrics` 模块，沉淀 ARPU、DOU、MOU、欠费率、投诉率等指标。
4. 实现 `sql_engine`，支持 SQL 模板、SQL 安全校验和查询执行。
5. 实现 FastAPI。
6. 实现 LangGraph Agent。
7. 最后接入 Next.js 前端。
