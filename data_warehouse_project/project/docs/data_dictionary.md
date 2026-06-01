# 电信数据仓库标准字段字典

## 设计说明

- 本文档基于 `docs/telecom_fields.xlsx` 的中文字段说明进行字段标准化设计，不生成 SQL。
- 文档不输出源系统英文字段；使用 `chinese_name` 作为业务人员可识别的字段注释入口。
- `standard_field` 统一使用英文 `snake_case`，避免拼音、内部系统缩写和无意义编码。
- 所有标准字段必须符合统一命名规范：`xxx_id`、`xxx_code`、`xxx_name`、`xxx_type`、`xxx_status`、`is_xxx`、`xxx_amount`、`xxx_fee`、`xxx_count`、`xxx_date`、`xxx_time`、`xxx_rate`、`xxx_ratio`、`xxx_duration`、`xxx_usage_mb`、`xxx_usage_min`。

## 分层库名规范

- MySQL 使用分层 schema 作为库名：`ods`、`dwd`、`dws`、`ads`。
- 所有表在设计、文档、ETL、API 和 Agent 工具中都必须使用全限定表名：`层名.表名`。
- ODS 层表名格式：`ods.ods_xxx`，保留原始来源粒度和装载批次信息。
- DWD 层表名格式：`dwd.dim_xxx` 或 `dwd.fact_xxx`，承载清洗后的维度表和明细事实表。
- DWS 层表名格式：`dws.dws_xxx`，承载按主题、用户、产品、渠道、账期等粒度汇总的数据。
- ADS 层表名格式：`ads.ads_xxx`，承载指标、报表、Agent 语义查询和业务分析结果。
- 示例：划分到 ODS 层的用户 360 日视图表应命名为 `ods.ods_user_360_daily`，而不是只写 `ods_user_360_daily`。

| layer | database/schema | table naming pattern | example |
|---|---|---|---|
| ODS | `ods` | `ods_xxx` | `ods.ods_user_360_daily` |
| DWD | `dwd` | `dim_xxx` / `fact_xxx` | `dwd.fact_user_snapshot_daily` |
| DWS | `dws` | `dws_xxx` | `dws.dws_user_month_summary` |
| ADS | `ads` | `ads_xxx` | `ads.ads_kpi_user_overview_monthly` |

## 统一命名规范

| 字段类别 | 命名规则 | 示例 |
|---|---|---|
| ID字段 | `xxx_id` | `customer_id` |
| 编码字段 | `xxx_code` | `order_status_code` |
| 名称字段 | `xxx_name` | `customer_name` |
| 类型字段 | `xxx_type` | `product_type` |
| 状态字段 | `xxx_status` | `order_status` |
| 标志字段 | `is_xxx` | `is_active_subscriber` |
| 金额字段 | `xxx_amount` | `payment_amount` |
| 费用字段 | `xxx_fee` | `monthly_fee` |
| 次数字段 | `xxx_count` | `voice_call_count` |
| 日期字段 | `xxx_date` | `activation_date` |
| 时间字段 | `xxx_time` | `payment_time` |
| 比率字段 | `xxx_rate` | `churn_rate` |
| 比例字段 | `xxx_ratio` | `traffic_ratio` |
| 时长字段 | `xxx_duration` | `complaint_handle_duration` |
| 流量字段 | `xxx_usage_mb` | `mobile_data_usage_mb` |
| 分钟字段 | `xxx_usage_min` | `voice_usage_min` |

## 汇总

- 字段记录数：3654
- 主题域数量：16
- 维度字段数：2438
- 指标字段数：1216
- 主键/业务键候选字段数：99
- 枚举字段数：837
- 命名规范违规数：0
- 是否输出源系统英文字段：否

## 主题域分布

| domain | field_count |
|---|---:|
| customer_user | 2219 |
| product_subscription | 334 |
| settlement_allocation | 184 |
| product_value_change | 169 |
| billing_arrears | 146 |
| service_complaint | 112 |
| digital_channel_order | 70 |
| order_channel | 69 |
| account_income | 66 |
| payment_recharge | 63 |
| credit_risk | 54 |
| real_name_compliance | 44 |
| terminal_presale | 40 |
| payment_transaction | 30 |
| terminal_device | 30 |
| network_application_usage | 24 |

## 字段标准化明细

| source_view | source_table | chinese_name | standard_field | business_meaning | data_type | domain | naming_rule | is_dimension_field | is_metric_field | is_primary_key | is_enum_field |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 账户编码 | account_code | 账户编码 | varchar(64) | account_income | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 帐户标识 | account_id | 帐户标识；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 帐目唯一编号 | account_item_id | 帐目唯一编号 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 二级帐目 | account_item_id_level2_type | 二级帐目 | varchar(64) | account_income | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 三级帐目 | account_item_id_level3_type | 三级帐目 | varchar(64) | account_income | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 四级账目 | account_item_id_level4_type | 四级账目 | varchar(64) | account_income | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 四级账目id | account_item_id_level4_type | 四级账目id | varchar(64) | account_income | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 帐目 | account_item_id_type | 帐目 | varchar(64) | account_income | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 计费帐目 | account_item_id_type | 计费帐目 | varchar(64) | account_income | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 账目标识 | account_item_id_type | 账目标识；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | account_income | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 四级帐目 | account_item_name_level4_type | 四级帐目 | varchar(64) | account_income | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 帐户名称 | account_name | 帐户名称 | varchar(255) | account_income | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 发展六级部门 | acquisition_department_id | 发展六级部门 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 用户发展六级部门 | acquisition_department_id | 用户发展六级部门 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 发展二级部门 | acquisition_department_level2_id | 发展二级部门 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 用户发展二级部门 | acquisition_department_level2_id | 用户发展二级部门 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 发展三级部门 | acquisition_department_level3_id | 发展三级部门 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 用户发展三级部门 | acquisition_department_level3_id | 用户发展三级部门 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 发展四级部门 | acquisition_department_level4_id | 发展四级部门 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 用户发展四级部门 | acquisition_department_level4_id | 用户发展四级部门 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 发展员工 | acquisition_staff_id | 发展员工 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 入网时间 | activation_time | 入网时间 | datetime | account_income | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 从计费帐单的OFFER_ID来的资费ID | b_price_plan_id | 从计费帐单的OFFER_ID来的资费ID | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 帐单帐期 | billing_cycle_date | 帐单帐期 | date | account_income | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 组合产品实例 | combo_product_instance_id | 组合产品实例 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 组合产品细类 | combo_product_instance_id | 组合产品细类 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 客户编号 | customer_id | 客户编号；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 客户名称 | customer_name | 客户名称 | varchar(255) | account_income | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 客户名称(全) | customer_name | 客户名称(全) | varchar(255) | account_income | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 数据来源 | data_source_name | 数据来源 | varchar(255) | account_income | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 数据日期 | data_time | 数据日期 | datetime | account_income | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | ICT收入分类 | ict_income_class_amount | ICT收入分类 | decimal(18,2) | account_income | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 本月实际应收(总账) | inc_fee | 本月实际应收(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | account_income | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 本月实际应收(总账)（元） | inc_fee | 本月实际应收(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | account_income | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 电渠条线标识 | is_digital_channel_line | 电渠条线标识 | boolean | account_income | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 是否ICT收入 | is_if_ict_income | 是否ICT收入 | boolean | account_income | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 标志_预付后付 | is_prepaid_subscriber | 标志_预付后付 | boolean | account_income | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 预付后付 | is_prepaid_subscriber | 预付后付 | boolean | account_income | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 预后标识 | is_prepaid_subscriber | 预后标识 | boolean | account_income | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 销渠条线标识 | is_sale_chnl_line | 销渠条线标识 | boolean | account_income | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 移动固网 | is_service_network | 移动固网 | boolean | account_income | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 移固标识 | is_service_network | 移固标识 | boolean | account_income | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 帐目来源唯一编号 | item_source_id | 帐目来源唯一编号 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 需要计税的费用 | need_tax_fee | 需要计税的费用 | decimal(18,2) | account_income | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 考核部门 | new_user_perf_department_id | 考核部门 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 新兴业务一级分类 | newbiz_account_item_id_level1_type | 新兴业务一级分类 | varchar(64) | account_income | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 新兴业务二级分类 | newbiz_account_item_id_level2_type | 新兴业务二级分类 | varchar(64) | account_income | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 新兴业务三级分类 | newbiz_account_item_id_level3_type | 新兴业务三级分类 | varchar(64) | account_income | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 单产品销售品细类 | offer_id | 单产品销售品细类 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 帐单金额 | ori_fee | 帐单金额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | account_income | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 帐单金额（元） | ori_fee | 帐单金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | account_income | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 主资费名称 | primary_price_plan_name | 主资费名称 | varchar(255) | account_income | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 主产品细类 | primary_product_id | 主产品细类 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 主产品细类id | primary_product_id | 主产品细类id | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 主产品细类二级 | primary_product_level2_id | 主产品细类二级 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 服务号码 | service_number_id | 服务号码 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 服务号码(全) | service_number_id | 服务号码(全) | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 用户状态 | state_status | 用户状态 | varchar(64) | account_income | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 税金 | tax_fee | 税金 | decimal(18,2) | account_income | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 税率 | tax_rate | 税率 | decimal(9,6) | account_income | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 出帐用户数 | user_id | 出帐用户数 | integer | account_income | 按次数字段规范命名为 xxx_count | 否 | 是 | 是 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 用户标识 | user_id | 用户标识 | varchar(64) | account_income | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 用户编码 | user_id | 用户编码 | varchar(64) | account_income | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 用户编码(文件导入) | user_id | 用户编码(文件导入) | varchar(64) | account_income | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 合同编码 | zhetno_code | 合同编码 | varchar(64) | account_income | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新用户账目月视图_3.0 | da.a_ac_income_360_m | 项目编码 | zictno_code | 项目编码 | varchar(64) | account_income | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 账户编码 | account_code | 账户编码 | varchar(64) | billing_arrears | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 帐户标识 | account_id | 帐户标识；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 账户名称 | account_name | 账户名称 | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 账户名称(全) | account_name | 账户名称(全) | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 用户发展六级渠道 | acquisition_department_id | 用户发展六级渠道 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 用户发展渠道 | acquisition_department_id | 用户发展渠道 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 用户发展二级渠道 | acquisition_department_level2_id | 用户发展二级渠道 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 用户发展渠道二级 | acquisition_department_level2_id | 用户发展渠道二级 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 发展渠道三级 | acquisition_department_level3_id | 发展渠道三级 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 用户发展三级渠道 | acquisition_department_level3_id | 用户发展三级渠道 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 发展渠道四级 | acquisition_department_level4_id | 发展渠道四级 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 用户发展四级渠道 | acquisition_department_level4_id | 用户发展四级渠道 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 发展渠道五级 | acquisition_department_level5_id | 发展渠道五级 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 用户发展五级渠道 | acquisition_department_level5_id | 用户发展五级渠道 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 用户发展员工 | acquisition_staff_id | 用户发展员工 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 入网月份 | activation_month_date | 入网月份 | date | billing_arrears | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 入网时间 | activation_time | 入网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | billing_arrears | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 累计回款金额 | bak_amount_fee | 累计回款金额 | decimal(18,2) | billing_arrears | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 累计回款金额(元) | bak_amount_fee | 累计回款金额(元)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | billing_arrears | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 有效欠费月累计销账金额 | bak_get_fee | 有效欠费月累计销账金额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | billing_arrears | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 有效欠费月累计销账金额（元） | bak_get_fee | 有效欠费月累计销账金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | billing_arrears | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 无效欠费月累计销账金额 | bak_invalid_fee | 无效欠费月累计销账金额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | billing_arrears | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 无效欠费月累计销账金额（元） | bak_invalid_fee | 无效欠费月累计销账金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | billing_arrears | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 欠费月份 | billing_cycle_date | 欠费月份 | date | billing_arrears | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 客户经理二级部门 | customer_manager_department_level2_name | 客户经理二级部门 | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 客户经理部门 | customer_manager_department_name | 客户经理部门 | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 客户名称 | customer_name | 客户名称 | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 客户名称(全) | customer_name | 客户名称(全) | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 数据日期 | data_time | 数据日期 | datetime | billing_arrears | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 免催停失效时期 | exp_date | 免催停失效时期 | date | billing_arrears | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 入网时租机资费 | first_lease_plan_id | 入网时租机资费 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 有效欠费（元） | get_fee | 有效欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | billing_arrears | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 入网时主资费 | initial_primary_price_plan_id | 入网时主资费 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 无效欠费（元） | invalid_fee | 无效欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | billing_arrears | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 电渠条线标识 | is_digital_channel_line | 电渠条线标识 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 是否单位担保租机 | is_ent_lease | 是否单位担保租机 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 是否周期内标识（1是0否） | is_inpay | 是否周期内标识（1是0否） | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 有效无效标识 | is_invalid | 有效无效标识 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 标志_是否租机 | is_lease | 标志_是否租机 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 标志_当月新增用户 | is_month_new | 标志_当月新增用户 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 标志_当月离网用户 | is_month_off | 标志_当月离网用户 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 免催停用户分类 | is_number_double_stop | 免催停用户分类 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 标志_免双停 | is_number_double_stop | 标志_免双停 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 免催停业务类型 | is_number_single_stop | 免催停业务类型 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 标志_免单停 | is_number_single_stop | 标志_免单停 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 免催停生效日期 | is_number_urge | 免催停生效日期 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 标志_免催 | is_number_urge | 标志_免催 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 标志_计费欠费 | is_outstanding | 标志_计费欠费 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 预后付费标识 | is_prepaid_subscriber | 预后付费标识 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 销渠条线标识 | is_sale_chnl_line | 销渠条线标识 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 是否校园标志 | is_school | 是否校园标志 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 移动固网标识 | is_service_network | 移动固网标识 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 标志_是否欠费 | is_sf_outstanding | 标志_是否欠费 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 是否特殊缴费期用户标识 | is_special | 是否特殊缴费期用户标识 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 租机计划 | lease_plan_id | 租机计划 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 租机计划失效时间 | lease_price_plan_eff_date_time | 租机计划失效时间 | datetime | billing_arrears | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 租机计划生效时间 | lease_price_plan_exp_date_time | 租机计划生效时间 | datetime | billing_arrears | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 免催停申请部门 | number_urge_department_name | 免催停申请部门 | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 单产品销售品细类 | offer_id | 单产品销售品细类 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 单产品销售品二级 | offer_level2_id | 单产品销售品二级 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 单产品销售品细类二级 | offer_level2_id | 单产品销售品细类二级 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 欠费金额 | outstanding_balance_amount | 欠费金额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | billing_arrears | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 欠费金额（元） | outstanding_balance_amount | 欠费金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | billing_arrears | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 主资费 | primary_price_plan_id | 主资费 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 资费名称 | primary_price_plan_name | 资费名称 | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 主产品 | primary_product_id | 主产品 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 主产品细类 | primary_product_id | 主产品细类 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 主产品细类二级 | primary_product_level2_id | 主产品细类二级 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 服务号码 | service_number_id | 服务号码 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 设备号码 | service_number_id | 设备号码 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 设备号码(全) | service_number_id | 设备号码(全) | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 客户经理 | staff_name | 客户经理 | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 停机类型 | stop_type_status | 停机类型 | varchar(64) | billing_arrears | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 离网时间 | termination_time | 离网时间 | datetime | billing_arrears | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 当前状态时间 | user_date_status | 当前状态时间 | varchar(64) | billing_arrears | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 用户编号 | user_id | 用户编号 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 用户编码 | user_id | 用户编码 | varchar(64) | billing_arrears | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 用户状态 | user_id_status | 用户状态 | varchar(64) | billing_arrears | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新即席查询欠费日视图_3.0 | DA.A_U_OWE_MID_BILLING_D | 圈集团客户名称 | vir_grp_customer_name | 圈集团客户名称 | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 账户编码 | account_code | 账户编码 | varchar(64) | billing_arrears | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 帐户标识 | account_id | 帐户标识 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 账户名称 | account_name | 账户名称 | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 账户名称(全) | account_name | 账户名称(全) | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 用户发展六级部门 | acquisition_department_id | 用户发展六级部门 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 用户发展部门 | acquisition_department_id | 用户发展部门 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 用户发展二级部门 | acquisition_department_level2_id | 用户发展二级部门 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 用户发展三级部门 | acquisition_department_level3_id | 用户发展三级部门 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 用户发展四级部门 | acquisition_department_level4_id | 用户发展四级部门 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 用户发展五级部门 | acquisition_department_level5_id | 用户发展五级部门 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 用户发展员工 | acquisition_staff_id | 用户发展员工 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 入网月份 | activation_month_date | 入网月份 | date | billing_arrears | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 欠费账期 | billing_cycle_date | 欠费账期 | date | billing_arrears | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 客户经理二级部门 | customer_manager_department_level2_name | 客户经理二级部门 | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 客户经理部门 | customer_manager_department_name | 客户经理部门 | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 客户名称 | customer_name | 客户名称 | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 客户名称(全) | customer_name | 客户名称(全) | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 数据日期 | data_time | 数据日期 | datetime | billing_arrears | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 免催停失效时期 | exp_date | 免催停失效时期 | date | billing_arrears | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 入网时租机资费 | first_lease_plan_id | 入网时租机资费 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 入网时主资费 | initial_primary_price_plan_id | 入网时主资费 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 无效欠费（元） | invalid_outstanding_fee | 无效欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | billing_arrears | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 电渠条线标识 | is_digital_channel_line | 电渠条线标识 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 是否单位担保租机 | is_ent_lease | 是否单位担保租机 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 是否周期内标识（1是0否） | is_inpay | 是否周期内标识（1是0否） | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 有效无效标识 | is_invalid | 有效无效标识 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 标志_是否租机 | is_lease | 标志_是否租机 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 标志_当月新增用户 | is_month_new | 标志_当月新增用户 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 标志_当月离网用户 | is_month_off | 标志_当月离网用户 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 免催停用户分类 | is_number_double_stop | 免催停用户分类 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 标志_免双停 | is_number_double_stop | 标志_免双停 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 免催停业务类型 | is_number_single_stop | 免催停业务类型 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 标志_免单停 | is_number_single_stop | 标志_免单停 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 免催停生效日期 | is_number_urge | 免催停生效日期 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 标志_免催 | is_number_urge | 标志_免催 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 标志免催停 | is_number_urge | 标志免催停 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 标志_计费欠费 | is_outstanding | 标志_计费欠费 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 预后付费标识 | is_prepaid_subscriber | 预后付费标识 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 销渠条线标识 | is_sale_chnl_line | 销渠条线标识 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 是否校园标志 | is_school | 是否校园标志 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 移动固网标识 | is_service_network | 移动固网标识 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 是否特殊缴费期用户标识 | is_special | 是否特殊缴费期用户标识 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 标志_零缴费 | is_zero_payment | 标志_零缴费 | boolean | billing_arrears | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 租机计划 | lease_plan_id | 租机计划 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 租机计划失效时间 | lease_price_plan_eff_date_time | 租机计划失效时间 | datetime | billing_arrears | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 租机计划生效时间 | lease_price_plan_exp_date_time | 租机计划生效时间 | datetime | billing_arrears | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 免催停申请部门 | number_urge_department_name | 免催停申请部门 | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 单产品销售品细类 | offer_id | 单产品销售品细类 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 单产品销售品二级 | offer_level2_id | 单产品销售品二级 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 欠费金额 | outstanding_balance_amount | 欠费金额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | billing_arrears | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 欠费金额（元） | outstanding_balance_amount | 欠费金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | billing_arrears | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 资费名称 | primary_price_plan_name | 资费名称 | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 主产品细类 | primary_product_id | 主产品细类 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 主产品细类二级 | primary_product_level2_id | 主产品细类二级 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 服务号码 | service_number_id | 服务号码 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 服务号码(全) | service_number_id | 服务号码(全) | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 客户经理 | staff_name | 客户经理 | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 停机类型 | stop_type_status | 停机类型 | varchar(64) | billing_arrears | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 离网时间 | termination_time | 离网时间 | datetime | billing_arrears | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 当前状态时间 | user_date_status | 当前状态时间 | varchar(64) | billing_arrears | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 用户编号 | user_id | 用户编号 | varchar(64) | billing_arrears | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 用户编码 | user_id | 用户编码 | varchar(64) | billing_arrears | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 用户状态 | user_id_status | 用户状态 | varchar(64) | billing_arrears | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 有效欠费（元） | valid_outstanding_fee | 有效欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | billing_arrears | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 圈集团客户名称 | vir_grp_customer_name | 圈集团客户名称 | varchar(255) | billing_arrears | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 合同编码 | zhetno_code | 合同编码 | varchar(64) | billing_arrears | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新用户账期欠费月视图_3.0 | da.A_u_OWE_BILLING_M | 项目编码 | zictno_code | 项目编码 | varchar(64) | billing_arrears | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 账户编码 | account_id | 账户编码 | varchar(64) | credit_risk | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 用户发展六级部门 | acquisition_department_id | 用户发展六级部门 | varchar(64) | credit_risk | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 用户发展二级部门 | acquisition_department_level2_id | 用户发展二级部门 | varchar(64) | credit_risk | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 用户发展三级部门 | acquisition_department_level3_id | 用户发展三级部门 | varchar(64) | credit_risk | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 用户发展四级部门 | acquisition_department_level4_id | 用户发展四级部门 | varchar(64) | credit_risk | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 用户发展五级部门 | acquisition_department_level5_id | 用户发展五级部门 | varchar(64) | credit_risk | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 入网日期 | activation_date | 入网日期；由源表达式进行空值处理、截取或单位换算后形成 | date | credit_risk | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 活跃天数 | active_day_count | 活跃天数 | integer | credit_risk | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 活跃天数得分 | active_day_score_count | 活跃天数得分 | integer | credit_risk | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 入网月数 | active_subscriber_months_name | 入网月数 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 入网月数得分 | active_subscriber_months_score_name | 入网月数得分 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | ARUP值(元) | arpu_name | ARUP值(元) | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | ARPU得分 | arpu_score_name | ARPU得分 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 评级周期 | billing_date | 评级周期；由源表达式进行空值处理、截取或单位换算后形成 | date | credit_risk | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 信用度计算账期 | credit_calculation_date | 信用度计算账期 | date | credit_risk | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 总得分 | credit_score_name | 总得分 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 信用度值 | credit_value_name | 信用度值 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 评级前信用度值 | credit_value_name | 评级前信用度值 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 客户编码 | customer_id | 客户编码 | varchar(64) | credit_risk | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 客户姓名 | customer_name | 客户姓名 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 数据日期 | data_time | 数据日期 | datetime | credit_risk | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 最总信用度值 | final_credit_value_name | 最总信用度值 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 计费信用度 | hb_user_credit_value_name | 计费信用度 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 国际漫游得分 | is_gj_roam_score | 国际漫游得分 | boolean | credit_risk | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 用户发展部门一级名称 | kh_department_level1_name | 用户发展部门一级名称 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 用户发展部门二级名称 | kh_department_level2_name | 用户发展部门二级名称 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 用户发展部门三级名称 | kh_department_level3_name | 用户发展部门三级名称 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 用户发展部门四级名称 | kh_department_level4_name | 用户发展部门四级名称 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 用户发展部门五级名称 | kh_department_level5_name | 用户发展部门五级名称 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 年龄 | p_age_name | 年龄 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 最近第1月收入(总账) | previous_1_bill_fee | 最近第1月收入(总账) | decimal(18,2) | credit_risk | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 最近第2月收入(总账) | previous_2_bill_fee | 最近第2月收入(总账) | decimal(18,2) | credit_risk | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 最近第3月收入(总账) | previous_3_bill_fee | 最近第3月收入(总账) | decimal(18,2) | credit_risk | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 最近第4月收入(总账) | previous_4_bill_fee | 最近第4月收入(总账) | decimal(18,2) | credit_risk | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 最近第5月收入(总账) | previous_5_bill_fee | 最近第5月收入(总账) | decimal(18,2) | credit_risk | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 最近第6月收入(总账) | previous_6_bill_fee | 最近第6月收入(总账) | decimal(18,2) | credit_risk | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 主资费名称 | primary_price_plan_id_name | 主资费名称 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 用户号码 | service_number_id | 用户号码 | varchar(64) | credit_risk | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 用户号码(全) | service_number_id | 用户号码(全) | varchar(64) | credit_risk | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 捆绑黏度得分 | single_product_score_level2_name | 捆绑黏度得分 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 评级前星级 | star_level_name | 评级前星级 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 评级前星级名称 | star_level_name | 评级前星级名称 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 停机次数 | stop_cnt_count | 停机次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | credit_risk | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 停机次数得分 | stop_cnt_score_count | 停机次数得分 | integer | credit_risk | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 停机时长(小时) | stop_duration | 停机时长(小时)；由源表达式进行空值处理、截取或单位换算后形成 | integer | credit_risk | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 停机时长得分 | stop_score_duration | 停机时长得分 | integer | credit_risk | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 评级前授信系数 | sxxs_idx_name | 评级前授信系数 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 评级后信用度值 | up_credit_value_name | 评级后信用度值 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 评级后星级 | up_star_level_name | 评级后星级 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 评级后星级名称 | up_star_level_name | 评级后星级名称 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 评级后授信系数 | up_sxxs_idx_name | 评级后授信系数 | varchar(255) | credit_risk | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 用户数 | user_id | 用户数 | integer | credit_risk | 按次数字段规范命名为 xxx_count | 否 | 是 | 是 | 否 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | 用户编码 | user_id | 用户编码 | varchar(64) | credit_risk | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 信用度即席查询月视图_3.0 | DA.A_U_USER_CREDIT_DTL_M | VIP标示 | vip_card_type | VIP标示；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | credit_risk | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 新装受理渠道ID | accept_channel_id | 新装受理渠道ID | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 新装受理渠道名称 | accept_channel_name | 新装受理渠道名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 帐户编码 | account_code | 帐户编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 账户编码 | account_code | 账户编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 账户经理二级部门 | account_manager_department_level2_name | 账户经理二级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 账户经理三级部门 | account_manager_department_level3_name | 账户经理三级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 账户经理四级部门 | account_manager_department_level4_name | 账户经理四级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 账户经理六级部门 | account_manager_department_name | 账户经理六级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 账户经理 | account_manager_id | 账户经理 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 帐户名称 | account_name | 帐户名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 帐户名称（全） | account_name | 帐户名称（全） | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 账户名称 | account_name | 账户名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 账户名称(全) | account_name | 账户名称(全) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 累计欠费 | accumulated_outstanding_fee | 累计欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 累计欠费（元） | accumulated_outstanding_fee | 累计欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户发展六级部门编码 | acquisition_department_code | 用户发展六级部门编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户发展六级部门编码(文件导入) | acquisition_department_code | 用户发展六级部门编码(文件导入)；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_用户发展六级部门(仅限移固融合关联查询) | acquisition_department_id | 宽带_用户发展六级部门(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户发展六级部门 | acquisition_department_id | 用户发展六级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_用户发展二级部门(仅限移固融合关联查询) | acquisition_department_level2_id | 宽带_用户发展二级部门(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户发展二级部门 | acquisition_department_level2_id | 用户发展二级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_用户发展三级部门(仅限移固融合关联查询) | acquisition_department_level3_id | 宽带_用户发展三级部门(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户发展三级部门 | acquisition_department_level3_id | 用户发展三级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_用户发展四级部门(仅限移固融合关联查询) | acquisition_department_level4_id | 宽带_用户发展四级部门(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户发展四级部门 | acquisition_department_level4_id | 用户发展四级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_用户发展五级部门(仅限移固融合关联查询) | acquisition_department_level5_id | 宽带_用户发展五级部门(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户发展五级部门 | acquisition_department_level5_id | 用户发展五级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_用户发展员工(仅限移固融合关联查询) | acquisition_staff_id | 宽带_用户发展员工(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户发展员工 | acquisition_staff_id | 用户发展员工 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户发展员工ID | acquisition_staff_id | 用户发展员工ID | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户发展员工工号 | acquisition_staff_id | 用户发展员工工号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 入网日期 | activation_date | 入网日期；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_入网时间 | activation_time | 主卡_入网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 入网时间 | activation_time | 入网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_入网时间(仅限移固融合关联查询) | activation_time | 宽带_入网时间(仅限移固融合关联查询)；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计活跃天数 | active_day_count | 本月累计活跃天数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 翼支付红包金到期未消费明细加回收入 | add_redenvelope_fee | 翼支付红包金到期未消费明细加回收入 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 年龄分段 | age_split_name | 年龄分段 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 代理商编码 | agent_code | 代理商编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 代理商名称 | agent_name | 代理商名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月缴费金额 | agg_m_amount | 本月缴费金额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月缴费金额（元） | agg_m_amount | 本月缴费金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 累计缴费金额 | agg_total_amount | 累计缴费金额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 累计缴费金额（元） | agg_total_amount | 累计缴费金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 累计实收总费用 | agg_wrt_fee | 累计实收总费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 累计实收总费用(元） | agg_wrt_fee | 累计实收总费用(元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 欠费帐龄1月欠费 | aging_1_month_outstanding_fee | 欠费帐龄1月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 欠费帐龄1月欠费（元） | aging_1_month_outstanding_fee | 欠费帐龄1月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 欠费帐龄2月欠费 | aging_2_month_outstanding_fee | 欠费帐龄2月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 欠费帐龄2月欠费（元） | aging_2_month_outstanding_fee | 欠费帐龄2月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 欠费帐龄3月欠费 | aging_3_month_outstanding_fee | 欠费帐龄3月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 欠费帐龄3月欠费（元） | aging_3_month_outstanding_fee | 欠费帐龄3月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 欠费帐龄4月欠费 | aging_4_month_outstanding_fee | 欠费帐龄4月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 欠费帐龄4月欠费（元） | aging_4_month_outstanding_fee | 欠费帐龄4月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 欠费帐龄5月欠费 | aging_5_month_outstanding_fee | 欠费帐龄5月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 欠费帐龄5月欠费（元） | aging_5_month_outstanding_fee | 欠费帐龄5月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 欠费帐龄6月欠费 | aging_6_month_outstanding_fee | 欠费帐龄6月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 欠费帐龄6月欠费（元） | aging_6_month_outstanding_fee | 欠费帐龄6月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 地区编码 | area_id_code | 地区编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 当前星级生效时间 | assess_date_time | 当前星级生效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 考核二级部门 | assessment_department_level2_id | 考核二级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 考核三级部门 | assessment_department_level3_id | 考核三级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-实体渠道类型 | attr_value_type | 渠道视图-实体渠道类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计计价时长 | base_bill_dura_duration | 本月累计计价时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计计价流量 | base_bill_usage_mb | 本月累计计价流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月累计本地通话次数 | base_count | >本月累计本地通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计基本计费时长 | base_duration | 本月累计基本计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计计价短信条数 | bill_sms_count | 本月累计计价短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 入网月份 | billing_date | 入网月份；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 建档月份 | billing_date | 建档月份；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 证件首次入网时间 | billing_time | 证件首次入网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 证件首次入网时间(月) | billing_time | 证件首次入网时间(月)；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 捆绑机型 | binding_device_model_name | 捆绑机型 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 租机协议名称 | binding_device_model_name | 租机协议名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-商圈状态 | biz_zone_code_status | 渠道视图-商圈状态 | varchar(64) | customer_user | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-商圈类型 | biz_zone_code_type | 渠道视图-商圈类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-商圈级别 | biz_zone_level_name | 渠道视图-商圈级别 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-商圈名称 | biz_zone_name | 渠道视图-商圈名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-商圈编码 | biz_zone_number_code | 渠道视图-商圈编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 品牌 | brand_id | 品牌 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_宽带速率(仅限移固融合关联查询) | brd_line_rate | 宽带_宽带速率(仅限移固融合关联查询) | decimal(9,6) | customer_user | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带速率 | brd_line_rate | 宽带速率 | decimal(9,6) | customer_user | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇区县 | building_area_id | 楼宇区县 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_楼宇区局(仅限移固融合关联查询) | building_bureau_id | 宽带_楼宇区局(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇区局 | building_bureau_id | 楼宇区局 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇编号 | building_code | 楼宇编号 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇编码 | building_code | 楼宇编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_楼宇区局二级(仅限移固融合关联查询) | building_district_id | 宽带_楼宇区局二级(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇区局二级 | building_district_id | 楼宇区局二级 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇区局细类（摊分后) | building_district_id | 楼宇区局细类（摊分后) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 所属组别 | building_group_name | 所属组别 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_楼宇编号(仅限移固融合关联查询) | building_id | 宽带_楼宇编号(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇编号 | building_id | 楼宇编号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_楼宇性质(仅限移固融合关联查询) | building_kind_id | 宽带_楼宇性质(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇性质 | building_kind_id | 楼宇性质 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇等级 | building_levels_name | 楼宇等级 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇经理六级部门 | building_manager_department_id | 楼宇经理六级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇经理二级部门 | building_manager_department_level2_id | 楼宇经理二级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇经理三级部门 | building_manager_department_level3_id | 楼宇经理三级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇经理四级部门 | building_manager_department_level4_id | 楼宇经理四级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇经理 | building_manager_id | 楼宇经理 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_楼宇名称(仅限移固融合关联查询) | building_name | 宽带_楼宇名称(仅限移固融合关联查询) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇名称 | building_name | 楼宇名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_楼宇类型(仅限移固融合关联查询) | building_type | 宽带_楼宇类型(仅限移固融合关联查询) | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇类型 | building_type | 楼宇类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 商机编码 | business_code | 商机编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 订单证件类型 | card_code_type | 订单证件类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 出生年份 | certificate_count | 出生年份；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 客户证件类型 | certificate_id_type | 客户证件类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-销售点区域 | channel_area_id | 渠道视图-销售点区域 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-销售点业务排他 | channel_busi_pt_id | 渠道视图-销售点业务排他 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-销售点业务范围 | channel_busi_scope_id | 渠道视图-销售点业务范围 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-渠道类别 | channel_class_type | 渠道视图-渠道类别 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-渠道类型 | channel_code_type | 渠道视图-渠道类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-销售点功能类型 | channel_gn_id_type | 渠道视图-销售点功能类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-连锁经营主体类型 | channel_lsjy_id_type | 渠道视图-连锁经营主体类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道经理二级部门 | channel_manager_department_level2_name | 渠道经理二级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道经理三级部门 | channel_manager_department_level3_name | 渠道经理三级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道经理四级部门 | channel_manager_department_level4_name | 渠道经理四级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道经理六级部门 | channel_manager_department_name | 渠道经理六级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道经理 | channel_manager_name | 渠道经理 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-销售点卖场类型 | channel_mc_id_type | 渠道视图-销售点卖场类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-销售点名称 | channel_name | 渠道视图-销售点名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-销售点编码 | channel_number_code | 渠道视图-销售点编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-销售点ID | channel_number_id | 渠道视图-销售点ID | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-渠道状态 | channel_number_status | 渠道视图-渠道状态 | varchar(64) | customer_user | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-授权门店级别 | channel_sq_class_id | 渠道视图-授权门店级别 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-渠道子类型 | channel_subtype_code_type | 渠道视图-渠道子类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-专营门店类别 | channel_zyd_class_id_type | 渠道视图-专营门店类别 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-自有厅级别 | channel_zyt_class_id | 渠道视图-自有厅级别 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 测试电路结束日期 | circuit_end_date | 测试电路结束日期 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 测试电路开始日期 | circuit_start_date | 测试电路开始日期 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 收货地市 | citycode_name | 收货地市 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 组合产品细类 | combo_product_id | 组合产品细类 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 组合产品实例 | combo_product_instance_id | 组合产品实例 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 组合销售品细类 | combo_product_offer_id | 组合销售品细类 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 组合销售品成员角色 | combo_product_relationship_role_name | 组合销售品成员角色 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 接应经理二级部门 | con_manager_department_level2_name | 接应经理二级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 接应经理三级部门 | con_manager_department_level3_name | 接应经理三级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 接应经理四级部门 | con_manager_department_level4_name | 接应经理四级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 接应经理六级部门 | con_manager_department_name | 接应经理六级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 接应经理 | con_manager_name | 接应经理 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 接应经理（服务账户经理) | con_manager_name | 接应经理（服务账户经理) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 合作渠道（发展代理商） | coop_channel_name | 合作渠道（发展代理商） | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 关联合作渠道单元 | cooperation_channel_unit_name | 关联合作渠道单元 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 收货区县 | countycode_count | 收货区县 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 建档时间 | create_date_time | 建档时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本期欠费 | current_month_outstanding_fee | 本期欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本期欠费（元） | current_month_outstanding_fee | 本期欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本年欠费 | current_year_outstanding_fee | 本年欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本年欠费（元） | current_year_outstanding_fee | 本年欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 入网人证件类型 | customer_card_type | 入网人证件类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 证件首次入网时间(年) | customer_first_activation_date_time | 证件首次入网时间(年)；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 客户分群_归属 | customer_group_id | 客户分群_归属 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 客户编号 | customer_id | 客户编号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 清单客户名称 | customer_list_name | 清单客户名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 客户经理二级部门 | customer_manager_department_level2_name | 客户经理二级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 客户经理三级部门 | customer_manager_department_level3_name | 客户经理三级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 客户经理四级部门 | customer_manager_department_level4_name | 客户经理四级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 客户经理六级部门 | customer_manager_department_name | 客户经理六级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 客户经理 | customer_manager_id | 客户经理 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 客户名称 | customer_name | 客户名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 客户名称(全) | customer_name | 客户名称(全) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 客户名称（全） | customer_name | 客户名称（全） | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 入网人号码 | customer_phone_id | 入网人号码 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 入网人号码(文件导入) | customer_phone_id | 入网人号码(文件导入) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 客户转移部门 | customer_transfer_department_name | 客户转移部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 入网人姓名 | customername_name | 入网人姓名 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 每月最高使用额度 | cycle_upper_name | 每月最高使用额度；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 每月最高使用额度（元） | cycle_upper_name | 每月最高使用额度（元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日计价时长 | daily_base_bill_dura_duration | 本日计价时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日计价流量 | daily_base_bill_usage_mb | 本日计价流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日基本计费时长 | daily_base_duration | 本日基本计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日基本计费时长(秒) | daily_base_duration | 本日基本计费时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日计价短信条数 | daily_bill_sms_count | 本日计价短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日无线上网总下行流量 | daily_downlink_usage_mb | >本日无线上网总下行流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日彩信SP上行条数 | daily_dz_mo_mms_count | >本日彩信SP上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日SP上行条数 | daily_dz_mo_sms_count | >本日SP上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日彩信SP下行条数 | daily_dz_mt_mms_count | >本日彩信SP下行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日SP下行条数 | daily_dz_mt_sms_count | >本日SP下行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日呼转通话次数 | daily_for_count | >本日呼转通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日呼转通话时长 | daily_for_usage_min | >本日呼转通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日呼转通话时长(秒) | daily_for_usage_min | >本日呼转通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日3G上网时长 | daily_g3_dura_duration | 本日3G上网时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日3G上网流量 | daily_g3_flux_usage_mb | 本日3G上网流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 当日4G上网时长 | daily_g4_dura_duration | 当日4G上网时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 当日4G上网流量 | daily_g4_flux_usage_mb | 当日4G上网流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 当日5G上网流量 | daily_g5_flux_usage_mb | 当日5G上网流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日港澳台漫游计费时长 | daily_gat_roam_bill_dura_duration | 本日港澳台漫游计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日港澳台漫游数据流量 | daily_gat_roam_ix_flux_usage_mb | 本日港澳台漫游数据流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日国际漫游计费时长(含港澳台) | daily_gj_base_duration | 本日国际漫游计费时长(含港澳台)；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日国际长途计费时长 | daily_gj_bill_dura_duration | 本日国际长途计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日被叫通话次数 | daily_inbound_call_count | >本日被叫通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日被叫通话时长 | daily_inbound_call_usage_min | >本日被叫通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日被叫通话时长(秒) | daily_inbound_call_usage_min | >本日被叫通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日无线上网时长_本地 | daily_ix_base_duration | >本日无线上网时长_本地；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日无线上网总时长 | daily_ix_duration | 本日无线上网总时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日无线上网总上行流量_本地 | daily_ix_mo_base_usage_mb | >>本日无线上网总上行流量_本地；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日无线上网总上行流量_漫游 | daily_ix_mo_roam_usage_mb | >>本日无线上网总上行流量_漫游；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日无线上网总下行流量_本地 | daily_ix_mt_base_usage_mb | >>本日无线上网总下行流量_本地；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日无线上网总下行流量_漫游 | daily_ix_mt_roam_usage_mb | >>本日无线上网总下行流量_漫游；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日无线上网_时长_漫游 | daily_ix_roam_duration | >本日无线上网_时长_漫游；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日移动客服通话次数 | daily_kefu_cmc_count | >>本日移动客服通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日总客服通话次数 | daily_kefu_count | >本日总客服通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日电信客服通话次数 | daily_kefu_ctc_count | >>本日电信客服通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日联通客服通话次数 | daily_kefu_cuc_count | >>本日联通客服通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日本地拨本地通话时长 | daily_loacl_notoll_bill_dur_usage_min | 本日本地拨本地通话时长 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日本地拨本地通话时长（秒） | daily_loacl_notoll_bill_dur_usage_min | 本日本地拨本地通话时长（秒）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日本地本地计费时长（非漫游非长途） | daily_loacl_notoll_duration | 本日本地本地计费时长（非漫游非长途）；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日本地主叫计费时长（非漫游主叫） | daily_loacl_outbound_call_duration | 本日本地主叫计费时长（非漫游主叫）；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日彩信条数 | daily_mms_count | 本日彩信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日呼转移动次数 | daily_mobile_h_count | >本日呼转移动次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日无线上网总流量 | daily_mobile_usage_mb | 本日无线上网总流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日主叫移动通话次数 | daily_outbound_call_cmc_count | >>本日主叫移动通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日主叫移动通话时长 | daily_outbound_call_cmc_usage_min | >>本日主叫移动通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日主叫移动通话时长(秒) | daily_outbound_call_cmc_usage_min | >>本日主叫移动通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日主叫通话次数 | daily_outbound_call_count | >本日主叫通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日主叫电信通话次数 | daily_outbound_call_ctc_count | >>本日主叫电信通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日主叫电信通话时长 | daily_outbound_call_ctc_usage_min | >>本日主叫电信通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日主叫电信通话时长(秒) | daily_outbound_call_ctc_usage_min | >>本日主叫电信通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日主叫联通通话次数 | daily_outbound_call_cuc_count | >>本日主叫联通通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日主叫联通通话时长 | daily_outbound_call_cuc_usage_min | >>本日主叫联通通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日主叫联通通话时长(秒) | daily_outbound_call_cuc_usage_min | >>本日主叫联通通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | volte视频本日主叫通话时长 | daily_outbound_call_dura_video_volte_usage_min | volte视频本日主叫通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | volte语音本日主叫通话时长 | daily_outbound_call_dura_voice_volte_usage_min | volte语音本日主叫通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日主叫通话时长 | daily_outbound_call_usage_min | >本日主叫通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日主叫通话时长(秒) | daily_outbound_call_usage_min | >本日主叫通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日点对点移动上行条数 | daily_p2p_mo_cmc_count | >>本日点对点移动上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日点对点电信上行条数 | daily_p2p_mo_ctc_count | >>本日点对点电信上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日点对点联通上行条数 | daily_p2p_mo_cuc_count | >>本日点对点联通上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日彩信点对点上行条数 | daily_p2p_mo_mms_count | >本日彩信点对点上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本日点对点其他上行条数 | daily_p2p_mo_oth_count | >>本日点对点其他上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日点对点上行条数 | daily_p2p_mo_sms_count | >本日点对点上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日彩信点对点下行条数 | daily_p2p_mt_mms_count | >本日彩信点对点下行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日点对点下行条数 | daily_p2p_mt_sms_count | >本日点对点下行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 前日充值金额（元） | daily_recharge_amt_amount | 前日充值金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 前日充值次数 | daily_recharge_count | 前日充值次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_本日总费用 | daily_revenue_fee | 主卡_本日总费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_本日总费用（元） | daily_revenue_fee | 主卡_本日总费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 副卡_本日总费用 | daily_revenue_fee | 副卡_本日总费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日总费用 | daily_revenue_fee | 本日总费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日总费用（元） | daily_revenue_fee | 本日总费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日短信条数 | daily_sms_count | 本日短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日呼转电信次数 | daily_telecom_h_count | >本日呼转电信次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日呼转联通次数 | daily_unicom_h_count | >本日呼转联通次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本日上网总上行流量 | daily_uplink_usage_mb | >本日上网总上行流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日通话次数 | daily_voice_call_count | 本日通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日通话时长 | daily_voice_call_usage_min | 本日通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日通话时长(秒) | daily_voice_call_usage_min | 本日通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 数据日期 | data_time | 数据日期 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 性别 | decimal_count | 性别；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 订单配送方式 | delivery_method_code | 订单配送方式 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 配送时间 | delivery_time | 配送时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户发展积分 | dev_point_name | 用户发展积分 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 日新增用户发展积分 | dev_points_name | 日新增用户发展积分 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 月累计用户发展积分 | dev_points_name | 月累计用户发展积分 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月新增发展积分 | dev_points_name | 本月新增发展积分 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 手机品牌 | device_brand_id | 手机品牌 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 手机型号 | device_model_id | 手机型号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 手机型号ID | device_model_id | 手机型号ID | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 终端出现次数 | device_reg_found_count | 终端出现次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 实交购机款（元） | device_reg_found_count_fee | 实交购机款（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 实交预存（元） | device_reg_found_seq_name | 实交预存（元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 终端出现次序 | device_reg_found_seq_name | 终端出现次序；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 终端出现组号 | device_reg_previous_accnbr_name | 终端出现组号；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 关联电子渠道发展人 | digital_channel_acquisition_staff_id | 关联电子渠道发展人 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 电子渠道用户类型 | digital_channel_user_type | 电子渠道用户类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 订单编码 | digital_order_code | 订单编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 订单编码(文件导入) | digital_order_code | 订单编码(文件导入) | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 订单状态 | digital_order_status | 订单状态 | varchar(64) | customer_user | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 订单类型 | digital_order_type | 订单类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 号码转入前运营商 | divert_operator_id | 号码转入前运营商 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 双计人六级部门 | double_cal_department_id | 双计人六级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 双计人二级部门 | double_cal_department_level2_id | 双计人二级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 双计人三级部门 | double_cal_department_level3_id | 双计人三级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 双计人四级部门 | double_cal_department_level4_id | 双计人四级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 双计人 | double_cal_staff_id | 双计人 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 一卡双芯关联用户ID | double_user_id | 一卡双芯关联用户ID | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-一级分类 | dvlp_chnl_1_type | 渠道视图-一级分类 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-二级分类 | dvlp_chnl_2_type | 渠道视图-二级分类 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-细分属性 | dvlp_chnl_3_type | 渠道视图-细分属性 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月累计彩信SP条数 | dz_mms_count | >本月累计彩信SP条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >彩信SP上行条数 | dz_mo_mms_count | >彩信SP上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >SP上行条数 | dz_mo_sms_count | >SP上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >彩信SP下行条数 | dz_mt_mms_count | >彩信SP下行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >SP下行条数 | dz_mt_sms_count | >SP下行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月累计短信定制短信条数 | dz_sms_count | >本月累计短信定制短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 教育校园发展人 | edu_staff_id | 教育校园发展人 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 生效类型 | eff_time_type | 生效类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 政企行业类型 | ent_industry_id_type | 政企行业类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 政企_价值等级 | ent_value_class_id | 政企_价值等级 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 交换区 | exch_dir_id | 交换区 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 免催停失效日期 | exp_date | 免催停失效日期 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 有效时间数值 | exp_month_time | 有效时间数值 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 补差款 | extra_dev_fee | 补差款；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 补差款（元） | extra_dev_fee | 补差款（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-账单费用 | fc_bill_fee | 预估-账单费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-不计收回收 | fc_bjshs_name | 预估-不计收回收；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-减掉一卡双芯语音部分 | fc_double_fee | 预估-减掉一卡双芯语音部分；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-加回一卡双芯无线宽带部分 | fc_double_wir_fee | 预估-加回一卡双芯无线宽带部分；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-当月递延加回的收入 | fc_dy_amount | 预估-当月递延加回的收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-当月产生的递延收入 | fc_dydy_amount | 预估-当月产生的递延收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-考核收入 | fc_fee | 预估-考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-历史递延加回的收入 | fc_lsdy_amount | 预估-历史递延加回的收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-ocs现金流 | fc_ocs_fee | 预估-ocs现金流；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-欠费不计收 | fc_qfbjs_amount | 预估-欠费不计收；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预测离网月份 | fc_remove_date | 预测离网月份 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-调账费用 | fc_tz_fee | 预估-调账费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-信用度减收 | fc_xydjs_name | 预估-信用度减收；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-赠送 | fc_zs_fee | 预估-赠送；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-专线摊出 | fc_zxtc_name | 预估-专线摊出；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-专线摊入 | fc_zxtr_name | 预估-专线摊入；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 日激活用户数 | first_active_date | 日激活用户数；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 月激活用户数 | first_active_date | 月激活用户数；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 首次激活时间（固网起租时间） | first_active_date_time | 首次激活时间（固网起租时间）；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-渠道初始合作时间 | first_coop_time | 渠道视图-渠道初始合作时间 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最早欠费月份 | first_outstanding_month_date | 最早欠费月份 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 副卡数 | fk_count | 副卡数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计3G上网时长 | g3_dura_duration | 本月累计3G上网时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计3G上网流量 | g3_flux_usage_mb | 本月累计3G上网流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标签-本月3G流量大于5GB | g3_flux_usage_mb | 标签-本月3G流量大于5GB；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 月累计4G上网时长 | g4_dura_duration | 月累计4G上网时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 月累计4G上网流量 | g4_flux_usage_mb | 月累计4G上网流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 月累计5G上网流量 | g5_flux_usage_mb | 月累计5G上网流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月港澳台漫游计费时长 | gat_roam_bill_dura_duration | 本月港澳台漫游计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月港澳台漫游数据流量 | gat_roam_ix_flux_usage_mb | 本月港澳台漫游数据流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月国际漫游计费时长(含港澳台) | gj_base_duration | 本月国际漫游计费时长(含港澳台)；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月国际长途计费时长 | gj_bill_dura_duration | 本月国际长途计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月国际漫游被叫计费时长 | gj_roam_inbound_call_bill_dur_duration | 本月国际漫游被叫计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月国际漫游数据流量 | gj_roam_ix_flux_usage_mb | 本月国际漫游数据流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月国际漫游主叫计费时长 | gj_roam_outbound_call_bill_dur_duration | 本月国际漫游主叫计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月国际漫游短信条数 | gj_roam_sms_tims_count | 本月国际漫游短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最低管控价 | gk_value_id_usage_min | 最低管控价 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 集团编码 | group_id_code | 集团编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-HB预用户实收 | hb_pre_fee | 预估-HB预用户实收；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 数字中心名称 | idc_center_name | 数字中心名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 机架电力要求(含单位) | idc_ele_req_name | 机架电力要求(含单位) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 互联网带宽出租计费方式 | idc_net_lease_fee_type | 互联网带宽出租计费方式 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 互联网带宽出租接入类型 | idc_net_lease_service_type | 互联网带宽出租接入类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 互联网带宽速率 | idc_net_rate | 互联网带宽速率 | decimal(9,6) | customer_user | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | IMSI | imsi_count | IMSI | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月被叫通话时长 | inbound_call_usage_min | >本月被叫通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月被叫通话时长(秒) | inbound_call_usage_min | >本月被叫通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 号码初始运营商 | initial_operator_id | 号码初始运营商 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_楼宇区县(仅限移固融合关联查询) | int_name | 宽带_楼宇区县(仅限移固融合关联查询) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 智能机操作系统 | intel_phone_system_name | 智能机操作系统 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 智能机操作系统版本 | intel_phone_version_name | 智能机操作系统版本 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 智能机版本 | intel_phone_version_name | 智能机版本 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | iPhone发展六级部门 | ip_develop_department_id | iPhone发展六级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | iPhone发展四级部门 | ip_develop_department_level4_id | iPhone发展四级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | iPhone发展五级部门 | ip_develop_department_level5_id | iPhone发展五级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G用户数 | is_4g | 4G用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G用户标志 | is_4g | 4G用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否4G用户标志 | is_4g | 是否4G用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G流量包用户数 | is_4g_flux_pkg | 4G流量包用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G流量包用户标志 | is_4g_flux_pkg | 4G流量包用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否4G流量包用户标志 | is_4g_flux_pkg | 是否4G流量包用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G功能用户数 | is_4g_func | 4G功能用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G功能用户标志 | is_4g_func | 4G功能用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否4G功能用户标志 | is_4g_func | 是否4G功能用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G手机用户数 | is_4g_imei | 4G手机用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G手机用户标志 | is_4g_imei | 4G手机用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否4G手机用户标志(自注册) | is_4g_imei | 是否4G手机用户标志(自注册) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G终端用户数 | is_4g_lease_price_plan | 4G终端用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G终端用户标志 | is_4g_lease_price_plan | 4G终端用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否4G终端用户标志(合约捆绑) | is_4g_lease_price_plan | 是否4G终端用户标志(合约捆绑) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G非套餐用户数 | is_4g_none_price_plan | 4G非套餐用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G非套餐用户标志 | is_4g_none_price_plan | 4G非套餐用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否4G非套餐用户标志 | is_4g_none_price_plan | 是否4G非套餐用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G语音套餐用户标志 | is_4g_phone_user | 4G语音套餐用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G主套餐用户数 | is_4g_primary_price_plan | 4G主套餐用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G主套餐用户标志 | is_4g_primary_price_plan | 4G主套餐用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否4G主套餐用户标志 | is_4g_primary_price_plan | 是否4G主套餐用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G卡用户数 | is_4g_sim | 4G卡用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G卡用户标志 | is_4g_sim | 4G卡用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否4G卡用户标志 | is_4g_sim | 是否4G卡用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否开通5G功能 | is_5g | 是否开通5G功能 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否5G预约用户 | is_5g_appointment | 是否5G预约用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否预约5G用户 | is_5g_appointment | 是否预约5G用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_在网状态 | is_active_subscriber | 主卡_在网状态 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_在网用户数 | is_active_subscriber | 主卡_在网用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 副卡_在网用户数 | is_active_subscriber | 副卡_在网用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 在网用户数 | is_active_subscriber | 在网用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_在网状态(仅限移固融合关联查询) | is_active_subscriber | 宽带_在网状态(仅限移固融合关联查询) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_在网用户数(仅限移固融合关联查询) | is_active_subscriber | 宽带_在网用户数(仅限移固融合关联查询) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_当日用户在网 | is_active_subscriber | 标志_当日用户在网 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 离网用户数 | is_active_subscriber | 离网用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 月活跃用户数 | is_active_usage | 月活跃用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 月零次用户数 | is_active_usage | 月零次用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 月非活跃用户数 | is_active_usage | 月非活跃用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月是否活跃 | is_active_usage | 本月是否活跃 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 月出账用户数(A口径) | is_bill_a | 月出账用户数(A口径) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月是否出账(预估A口径) | is_bill_a | 本月是否出账(预估A口径) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月是否出账（预估A口径） | is_bill_a | 本月是否出账（预估A口径）；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否屏蔽营销类短信 | is_block_campaign_sms | 是否屏蔽营销类短信 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇分类 | is_building | 楼宇分类 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 2G/3G/4G标志 | is_c_user_type | 2G/3G/4G标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 双模卡类型 | is_card | 双模卡类型 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_是否双模卡 | is_card | 标志_是否双模卡 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 云计算服务 | is_cloud | 云计算服务 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 机型是否一致 | is_confer | 机型是否一致 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 赠送标志 | is_confer | 赠送标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_城市农村 | is_country | 标志_城市农村 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否清单客户 | is_customer_list | 是否清单客户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 日活跃用户数 | is_daily_active | 日活跃用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日是否活跃 | is_daily_active | 本日是否活跃 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_日出账用户数 | is_daily_bill | 主卡_日出账用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 副卡_日出账用户数 | is_daily_bill | 副卡_日出账用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 日出账用户数 | is_daily_bill | 日出账用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否日出账 | is_daily_bill | 是否日出账 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 日通话用户数 | is_daily_zcall | 日通话用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日零次通话 | is_daily_zcall | 本日零次通话 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 日呼转用户数 | is_daily_zh | 日呼转用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日零次呼转 | is_daily_zh | 本日零次呼转 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日零次无线上网 | is_daily_zix | 本日零次无线上网 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本日零次短信 | is_daily_zsms | 本日零次短信 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_日新增用户数 | is_day_new | 主卡_日新增用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 副卡_日新增用户数 | is_day_new | 副卡_日新增用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_当日新增用户标志(仅限移固融合关联查询) | is_day_new | 宽带_当日新增用户标志(仅限移固融合关联查询) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_日新增用户数(仅限移固融合关联查询) | is_day_new | 宽带_日新增用户数(仅限移固融合关联查询) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 日新增用户数 | is_day_new | 日新增用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_当日新增用户 | is_day_new | 标志_当日新增用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 日新增异网标识 | is_day_new_ot_opera | 日新增异网标识；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_日离网用户数 | is_day_off | 主卡_日离网用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 副卡_日离网用户数 | is_day_off | 副卡_日离网用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_当日离网用户标志(仅限移固融合关联查询) | is_day_off | 宽带_当日离网用户标志(仅限移固融合关联查询) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_日离网用户数(仅限移固融合关联查询) | is_day_off | 宽带_日离网用户数(仅限移固融合关联查询) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 日离网用户数 | is_day_off | 日离网用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_当日离网用户 | is_day_off | 标志_当日离网用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 手机终端标志(自注册) | is_device_g3 | 手机终端标志(自注册) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 电渠条线标识 | is_digital_channel_line | 电渠条线标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否双待机器 | is_double_net_phone | 是否双待机器 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_是一卡双芯 | is_double_user_id | 标志_是一卡双芯 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_非一卡双芯 | is_double_user_id | 标志_非一卡双芯 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否校园组织 | is_edu_org | 是否校园组织 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否教育校园 | is_education_school | 是否教育校园；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 政企_聚类标志 | is_ent_cluster | 政企_聚类标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 政企_国内国际标志 | is_ent_gngj | 政企_国内国际标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否 服务-普通号码防诈骗承诺 | is_fraud_number | 是否 服务-普通号码防诈骗承诺；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否 服务-商话防诈骗承诺 | is_fraud_shnbr | 是否 服务-商话防诈骗承诺；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 公免测试类型 | is_free | 公免测试类型 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G 终端且开卡用户标志 | is_g4_device_sim | 4G 终端且开卡用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 4G终端且开卡用户标志 | is_g4_device_sim | 4G终端且开卡用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否A级楼宇 | is_if_class_a | 是否A级楼宇 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否有责任人 | is_if_duty | 是否有责任人 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否接入IDC机房 | is_if_idc_machine_room | 是否接入IDC机房 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否携转离网 | is_if_out_net | 是否携转离网 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否有使用人 | is_if_user_party | 是否有使用人 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否智能机 | is_intel_phone | 是否智能机 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否智能机_当天 | is_intel_phone | 是否智能机_当天 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否智能机_前一天 | is_intel_phone_previousday | 是否智能机_前一天 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_是否集团管控 | is_jt_gk | 标志_是否集团管控；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 捆绑机型象限 | is_kb_xx | 捆绑机型象限 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否5G融合 | is_kd_5g | 是否5G融合 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否在到期月前3月内订购宽带续约 | is_kd_year_end_renew | 是否在到期月前3月内订购宽带续约 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否在到期当月订购宽带续约 | is_kd_year_end_renew_1m | 是否在到期当月订购宽带续约 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_是否租机 | is_lease | 标志_是否租机 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | UIM卡类型标签 | is_model | UIM卡类型标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_当月新增用户标志(仅限移固融合关联查询) | is_month_new | 宽带_当月新增用户标志(仅限移固融合关联查询) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_月新增用户数(仅限移固融合关联查询) | is_month_new | 宽带_月新增用户数(仅限移固融合关联查询) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 月新增用户数 | is_month_new | 月新增用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_当月新增用户 | is_month_new | 标志_当月新增用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 月离网用户数 | is_month_off | 月离网用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_当月离网用户 | is_month_off | 标志_当月离网用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 迁转5G目标客户分值标签 | is_moving_5g_customer | 迁转5G目标客户分值标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_新老用户 | is_new_user | 标志_新老用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否高校 | is_not | 是否高校 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_计费欠费 | is_outstanding | 标志_计费欠费 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 前一天是否出账（预估A口径) | is_p1d_bill_a | 前一天是否出账（预估A口径) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 前一天是否出账（预估A口径） | is_p1d_bill_a | 前一天是否出账（预估A口径） | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_预付后付 | is_prepaid_subscriber | 标志_预付后付 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预付后付 | is_prepaid_subscriber | 预付后付 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月是否出账（A口径） | is_previous_1_month_bill | 上月是否出账（A口径） | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否智能机_上月底最后一天 | is_previous_1_month_intel_phone | 是否智能机_上月底最后一天 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 免催停用户分类 | is_previous_1_month_number_double_stop | 免催停用户分类 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 免催停业务类型 | is_previous_1_month_number_single_stop | 免催停业务类型 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 免催停生效日期 | is_previous_1_month_number_urge | 免催停生效日期 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月宽带融合标志 | is_previous_1_month_ronghe | 上月宽带融合标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_维挽拍照用户 | is_previous_1_month_ww_photo | 标志_维挽拍照用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带融合标志 | is_ronghe | 宽带融合标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 销渠条线标识 | is_sale_chnl_line | 销渠条线标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否校园标志 | is_school | 是否校园标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标识_是否开通3G功能 | is_service_g3 | 标识_是否开通3G功能 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_移动固网 | is_service_network | 标志_移动固网 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 移动固网 | is_service_network | 移动固网 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否超级SIM卡支持终端 | is_super_sim_supported | 是否超级SIM卡支持终端 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否一般纳税人 | is_taxpayer | 是否一般纳税人 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月3g用户活跃标志(流量大于0M) | is_user_3g_type | 本月3g用户活跃标志(流量大于0M) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_本月3G活跃用户标志(流量大于0M) | is_user_3g_type | 标志_本月3G活跃用户标志(流量大于0M) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 5G升级包销售品用户标签 | is_user_5g_sjb | 5G升级包销售品用户标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 5G套餐用户标签 | is_user_5g_tc | 5G套餐用户标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 圈集团标志 | is_vir_grp | 圈集团标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否VOLTE | is_volte | 是否VOLTE | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_无线宽带 | is_wireless | 标志_无线宽带 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 融合产品 | is_yd_kd_label | 融合产品 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_当年新增用户 | is_year_new | 标志_当年新增用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_当年离网用户 | is_year_off | 标志_当年离网用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 月通话用户数 | is_zcall | 月通话用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 月零通话用户数 | is_zcall | 月零通话用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月零次通话 | is_zcall | 本月零次通话 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 标志_本月是否零次通话 | is_zcall | 标志_本月是否零次通话 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否三无副卡 | is_zero3_fk | 是否三无副卡 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 是否副卡标识 | is_zero_fk | 是否副卡标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主副卡标识 | is_zf_card_id | 主副卡标识；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月零次无线宽带 | is_zix | 本月零次无线宽带 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月零次短信 | is_zsms | 本月零次短信 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 自注册机型象限 | is_zzc_xx | 自注册机型象限 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月累计无线宽带时长_本地时长 | ix_base_duration | >本月累计无线宽带时长_本地时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计无线宽带流量_本地 | ix_base_usage_mb | 本月累计无线宽带流量_本地；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计无线宽带总时长 | ix_duration | 本月累计无线宽带总时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月累计无线宽带总上行流量_本地 | ix_mo_base_usage_mb | >>本月累计无线宽带总上行流量_本地；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月累计无线宽带总上行流量_本地(KB) | ix_mo_base_usage_mb | >>本月累计无线宽带总上行流量_本地(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月累计无线宽带总上行流量_漫游 | ix_mo_roam_usage_mb | >>本月累计无线宽带总上行流量_漫游；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月累计无线宽带总上行流量_漫游(KB) | ix_mo_roam_usage_mb | >>本月累计无线宽带总上行流量_漫游(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月累计无线宽带总下行流量_本地 | ix_mt_base_usage_mb | >>本月累计无线宽带总下行流量_本地；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月累计无线宽带总下行流量_本地(KB) | ix_mt_base_usage_mb | >>本月累计无线宽带总下行流量_本地(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月累计无线宽带总下行流量_漫游 | ix_mt_roam_usage_mb | >>本月累计无线宽带总下行流量_漫游；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月累计无线宽带总下行流量_漫游(KB) | ix_mt_roam_usage_mb | >>本月累计无线宽带总下行流量_漫游(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月累计无线宽带时长_漫游 | ix_roam_duration | >本月累计无线宽带时长_漫游；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计无线宽带流量_漫游 | ix_roam_usage_mb | 本月累计无线宽带流量_漫游；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户类型（集团） | jt_customer_id_type | 用户类型（集团） | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 政企行业类型（大类） | jt_ent_industry_id_level1_type | 政企行业类型（大类）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 集团ICT-合同号 | jt_ict_contract_number_name | 集团ICT-合同号 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 集团ICT-项目号 | jt_ict_project_number_name | 集团ICT-项目号 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 集团集约IDC-合同号 | jt_idc_contract_number_name | 集团集约IDC-合同号 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 集团集约IDC-群号 | jt_idc_group_number_name | 集团集约IDC-群号 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 集团IDC--月租费 | jt_idc_month_fee_date | 集团IDC--月租费 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 集团集约IDC-项目号 | jt_idc_project_number_name | 集团集约IDC-项目号 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 集团流水号 | jt_number_id | 集团流水号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_本月融合在网智慧产品数 | kd_rh_iptv_count | 宽带_本月融合在网智慧产品数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月融合在网智慧产品数 | kd_rh_iptv_count | 本月融合在网智慧产品数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_本月融合在网移动+副卡数 | kd_rh_yd_count | 宽带_本月融合在网移动+副卡数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_融合在网移动+副卡数 | kd_rh_yd_count | 宽带_融合在网移动+副卡数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月融合在网移动+副卡数 | kd_rh_yd_count | 本月融合在网移动+副卡数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月移动客服通话次数 | kefu_cmc_count | >本月移动客服通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月总客服通话次数 | kefu_count | 本月总客服通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月电信客服通话次数 | kefu_ctc_count | >本月电信客服通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月联通客服通话次数 | kefu_cuc_count | >本月联通客服通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 离网扣罚积分 | kf_point_name | 离网扣罚积分 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 日新增离网扣罚积分 | kf_points_name | 日新增离网扣罚积分 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 月累计离网扣罚积分 | kf_points_name | 月累计离网扣罚积分 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月离网扣罚积分 | kf_points_name | 本月离网扣罚积分 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_本月实收上期费用(元) | lastmonth_real_time_fee | 主卡_本月实收上期费用(元)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 副卡_本月实收上期费用(元) | lastmonth_real_time_fee | 副卡_本月实收上期费用(元)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_本月实收上期费用 | lastmonth_wrt_fee | 主卡_本月实收上期费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月实收上期费用 | lastmonth_wrt_fee | 本月实收上期费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月实收上期费用（元） | lastmonth_wrt_fee | 本月实收上期费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月销账上期费用（元） | lastmonth_wrt_fee | 本月销账上期费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 协议在网月份数 | lease_active_subscriber_months_date | 协议在网月份数 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 协议在网月份数（PPM） | lease_active_subscriber_months_date | 协议在网月份数（PPM） | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_租机计划 | lease_plan_id | 主卡_租机计划 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 租机计划 | lease_plan_id | 租机计划；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 租机计划生效时间 | lease_price_plan_eff_date_time | 租机计划生效时间 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 租机计划失效时间 | lease_price_plan_exp_date_time | 租机计划失效时间 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 租机计划订购时间 | lease_price_plan_order_date_time | 租机计划订购时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 租机计划发展六级部门 | lease_price_plan_staff_department_id | 租机计划发展六级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 租机计划发展二级部门 | lease_price_plan_staff_department_level2_id | 租机计划发展二级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 租机计划发展三级部门 | lease_price_plan_staff_department_level3_id | 租机计划发展三级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 租机计划发展四级部门 | lease_price_plan_staff_department_level4_id | 租机计划发展四级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 租机计划发展五级部门 | lease_price_plan_staff_department_level5_id | 租机计划发展五级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 合约发展人 | lease_price_plan_staff_id | 合约发展人 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 租机计划发展人 | lease_price_plan_staff_id | 租机计划发展人 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 捆绑机型发生时间 | lease_term_dt_time | 捆绑机型发生时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 合约类型 | lease_type | 合约类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 剩余返款月份数 | left_refund_months_date | 剩余返款月份数；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本端地址 | line_bd_address_name | 本端地址 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 对端地址 | line_dd_address_name | 对端地址 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 专线汇率 | line_money_rate | 专线汇率 | decimal(9,6) | customer_user | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 专线币种 | line_money_type | 专线币种 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 当月实际月租 | line_rule_level2_fee | 当月实际月租；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 一次性费用 | line_rule_level4_fee | 一次性费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计本地计费时长（非漫游） | loacl_duration | 本月累计本地计费时长（非漫游）；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计本地拨本地通话时长 | loacl_notoll_bill_dur_usage_min | 本月累计本地拨本地通话时长 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计本地拨本地通话时长（秒） | loacl_notoll_bill_dur_usage_min | 本月累计本地拨本地通话时长（秒）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计本地本地计费时长（非漫游非长途） | loacl_notoll_duration | 本月累计本地本地计费时长（非漫游非长途）；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计本地主叫计费时长（非漫游主叫） | loacl_outbound_call_duration | 本月累计本地主叫计费时长（非漫游主叫）；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本地行业大类 | local_industry_id_level1_type | 本地行业大类 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本地行业小类 | local_industry_id_type | 本地行业小类 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 流失风险用户 | loss_risk_probability_name | 流失风险用户 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 当前星级失效时间 | membership_exp_date_time | 当前星级失效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 客户当前星级值 | membership_level_name | 客户当前星级值 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 客户当前星级等级 | membership_level_name | 客户当前星级等级 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 云讯通门数 | menshu_value_name | 云讯通门数 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 客户评级方式 | method_rate | 客户评级方式 | decimal(9,6) | customer_user | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 捆绑终端2,3,4G标识 | mkt_res_234g_id | 捆绑终端2,3,4G标识 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | UIM卡类型生效时间 | model_start_dt_type | UIM卡类型生效时间 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月累计无线宽带总下行流量 | monthly_downlink_usage_mb | >本月累计无线宽带总下行流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月累计无线宽带总下行流量(KB) | monthly_downlink_usage_mb | >本月累计无线宽带总下行流量(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月被叫通话次数 | monthly_inbound_call_count | >本月被叫通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月彩信条数 | monthly_mms_count | 本月彩信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计无线宽带总流量 | monthly_mobile_usage_mb | 本月累计无线宽带总流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月主叫通话次数 | monthly_outbound_call_count | >本月主叫通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 当月充值次数 | monthly_recharge_count | 当月充值次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计短信条数 | monthly_sms_count | 本月累计短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月累计无线宽带总上行流量 | monthly_uplink_usage_mb | >本月累计无线宽带总上行流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月累计无线宽带总上行流量(KB) | monthly_uplink_usage_mb | >本月累计无线宽带总上行流量(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计通话次数 | monthly_voice_call_count | 本月累计通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 终端成本发生日期 | need_refund_account_cycle_date | 终端成本发生日期 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 需返款月份数 | need_refund_account_cycle_date | 需返款月份数 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 流量包创建时间 | net_create_date_usage_mb | 流量包创建时间；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 流量包失效时间 | net_end_dt_usage_mb | 流量包失效时间；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 流量包生效时间 | net_start_dt_usage_mb | 流量包生效时间；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 携号转入运营商名称 | network_id_in_name | 携号转入运营商名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 考核部门 | new_user_perf_department_id | 考核部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 租机计划生效时间（待生效） | next_lease_price_plan_eff_date_time | 租机计划生效时间（待生效）；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 租机计划失效时间（待生效） | next_lease_price_plan_exp_date_time | 租机计划失效时间（待生效）；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_租机计划将生效 | next_lease_price_plan_id | 主卡_租机计划将生效 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 租机计划（待生效） | next_lease_price_plan_id | 租机计划（待生效）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 下月的主销售品 | next_price_plan_4g_id | 下月的主销售品 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 一证办理多号数量 | number_cnt_count | 一证办理多号数量；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 一证五号核验状态 | number_value_status | 一证五号核验状态 | varchar(64) | customer_user | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 单产品销售品细类 | offer_id | 单产品销售品细类 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 单产品销售品一级 | offer_level1_id | 单产品销售品一级 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 单产品销售品二级 | offer_level2_id | 单产品销售品二级 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 销售品一级目录 | offer_serv_type_level1_name | 销售品一级目录 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 销售品二级目录 | offer_serv_type_level2_name | 销售品二级目录 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 销售品三级目录 | offer_serv_type_level3_name | 销售品三级目录 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 2021年双节营销拍照清单-清单4-老旧网关升级 | old_gateway_up_name | 2021年双节营销拍照清单-清单4-老旧网关升级 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 当日集中起租金额（元） | once_rent_fee | 当日集中起租金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月集中起租金额（元） | once_rent_fee | 本月集中起租金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 订单AB类型 | order_abtype_type | 订单AB类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 订单创建时间 | order_created_time | 订单创建时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 订单渠道 | order_data_channel_code | 订单渠道 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 订单金额(实际支付金额) | order_paid_amount | 订单金额(实际支付金额) | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 订单来源 | order_source_code | 订单来源 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 原始端口数 | ori_port_cnt_name | 原始端口数 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月主叫移动通话次数 | outbound_call_cmc_count | >>本月主叫移动通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月主叫移动通话时长 | outbound_call_cmc_usage_min | >>本月主叫移动通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月主叫移动通话时长(秒) | outbound_call_cmc_usage_min | >>本月主叫移动通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月主叫电信通话次数 | outbound_call_ctc_count | >>本月主叫电信通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月主叫电信通话时长 | outbound_call_ctc_usage_min | >>本月主叫电信通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月主叫电信通话时长(秒) | outbound_call_ctc_usage_min | >>本月主叫电信通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月主叫联通通话次数 | outbound_call_cuc_count | >>本月主叫联通通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月主叫联通通话时长 | outbound_call_cuc_usage_min | >>本月主叫联通通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月主叫联通通话时长(秒) | outbound_call_cuc_usage_min | >>本月主叫联通通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | volte视频本月主叫通话时长 | outbound_call_dura_video_volte_usage_min | volte视频本月主叫通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | volte语音本月主叫通话时长 | outbound_call_dura_voice_volte_usage_min | volte语音本月主叫通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月主叫通话时长 | outbound_call_usage_min | >本月主叫通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月主叫通话时长(秒) | outbound_call_usage_min | >本月主叫通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 已透支信用额度 | overdraft_credit_daily_name | 已透支信用额度 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月累彩信计点对点短信 | p2p_mms_count | >本月累彩信计点对点短信；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月点对点移动上行条数 | p2p_mo_cmc_count | >>本月点对点移动上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月点对点电信上行条数 | p2p_mo_ctc_count | >>本月点对点电信上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月点对点联通上行条数 | p2p_mo_cuc_count | >>本月点对点联通上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >彩信点对点上行条数 | p2p_mo_mms_count | >彩信点对点上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >>本月点对点其他上行条数 | p2p_mo_oth_count | >>本月点对点其他上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >点对点上行条数 | p2p_mo_sms_count | >点对点上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >彩信点对点下行条数 | p2p_mt_mms_count | >彩信点对点下行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >点对点下行条数 | p2p_mt_sms_count | >点对点下行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月累计点对点短信 | p2p_sms_count | >本月累计点对点短信；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 年龄 | p_age_name | 年龄 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 三个月平均收入（融合摊分前） | p_avg_3_rhtf_before_fee | 三个月平均收入（融合摊分前）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 个人所属政企客户标识 | p_ent_customer_id | 个人所属政企客户标识 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 个人所属政企客户名称 | p_ent_customer_name | 个人所属政企客户名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 订单支付方式 | payment_method_code | 订单支付方式 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 支付时间 | payment_time | 支付时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 支付流水号 | payment_transaction_id | 支付流水号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 支付流水号(文件导入) | payment_transaction_id | 支付流水号(文件导入) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 终端厂家 | phone_maker_name | 终端厂家 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 服务号码靓号级别 | pn_level_id | 服务号码靓号级别 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 合同编号 | po_number_id | 合同编号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 端口数 | port_cnt_name | 端口数 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 日预销用户数 | pre_termination_date | 日预销用户数；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 月预销用户数 | pre_termination_date | 月预销用户数；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预销号时间 | pre_termination_date_time | 预销号时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 当月调整积分 | previous_1_month_adjust_score_value_name | 当月调整积分；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月调整积分 | previous_1_month_adjust_score_value_name | 本月调整积分；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 累计积分 | previous_1_month_agg_score_value_name | 累计积分；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第1月计费时长 | previous_1_month_bill_dura_duration | 最近第1月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第1月收入(账单) | previous_1_month_billed_revenue_fee | 最近第1月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第1月收入(账单)（元） | previous_1_month_billed_revenue_fee | 最近第1月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月_组合产品细类 | previous_1_month_combo_product_id | 上月_组合产品细类 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月_组合产品实例 | previous_1_month_combo_product_inst_id | 上月_组合产品实例 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月_组合销售品细类 | previous_1_month_combo_product_offer_id | 上月_组合销售品细类 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 当月消费积分 | previous_1_month_consume_score_value_name | 当月消费积分；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月消费积分 | previous_1_month_consume_score_value_name | 本月消费积分；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 将作废积分 | previous_1_month_expire_score_value_name | 将作废积分；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第一个月3G流量 | previous_1_month_g3_flux_usage_mb | 最近第一个月3G流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 不可兑积分 | previous_1_month_invalid_score_value_name | 不可兑积分；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 无效积分 | previous_1_month_invalid_score_value_name | 无效积分 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月融合在网智慧产品数 | previous_1_month_kd_rh_iptv_count | 上月融合在网智慧产品数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月融合在网移动+副卡数 | previous_1_month_kd_rh_yd_active_subscriber_count | 上月融合在网移动+副卡数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月融合在网移动+副卡数_x000D_ | previous_1_month_kd_rh_yd_active_subscriber_count | 上月融合在网移动+副卡数_x000D_ | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 当月新增积分 | previous_1_month_new_score_value_date | 当月新增积分；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月新增积分 | previous_1_month_new_score_value_date | 本月新增积分；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 连续沉默月份数 | previous_1_month_noactive_months_date | 连续沉默月份数；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 免催停申请部门 | previous_1_month_number_urge_department_name | 免催停申请部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月_单产品销售品细类 | previous_1_month_offer_id | 上月_单产品销售品细类 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月_销售品生效时间 | previous_1_month_primary_price_plan_eff_date_time | 上月_销售品生效时间 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月_销售品失效时间 | previous_1_month_primary_price_plan_exp_date_time | 上月_销售品失效时间 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月_销售品名称 | previous_1_month_primary_price_plan_id_name | 上月_销售品名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月_销售品订购时间 | previous_1_month_primary_price_plan_order_date_time | 上月_销售品订购时间 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月_主产品细类 | previous_1_month_primary_product_id | 上月_主产品细类 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月底实际北京端月租 | previous_1_month_sum_res_fee | 上月底实际北京端月租 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第1月收入(总账) | previous_1_month_total_revenue_fee | 最近第1月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第1月收入(总账)（元） | previous_1_month_total_revenue_fee | 最近第1月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 可兑积分 | previous_1_month_valid_score_value_name | 可兑积分；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 有效积分 | previous_1_month_valid_score_value_name | 有效积分 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第1月通话时长 | previous_1_month_voice_call_dura_usage_min | 最近第1月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 累计wifi活跃月份 | previous_1_month_wlan_active_month_date | 累计wifi活跃月份；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第2月计费时长 | previous_2_month_bill_dura_duration | 最近第2月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第2月收入(账单) | previous_2_month_billed_revenue_fee | 最近第2月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第2月收入(账单)（元） | previous_2_month_billed_revenue_fee | 最近第2月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第二个月3G流量 | previous_2_month_g3_flux_usage_mb | 最近第二个月3G流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第2月收入(总账) | previous_2_month_total_revenue_fee | 最近第2月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第2月收入(总账)（元） | previous_2_month_total_revenue_fee | 最近第2月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第2月通话时长 | previous_2_month_voice_call_dura_usage_min | 最近第2月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第3月计费时长 | previous_3_month_bill_dura_duration | 最近第3月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第3月收入(账单) | previous_3_month_billed_revenue_fee | 最近第3月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第3月收入(账单)（元） | previous_3_month_billed_revenue_fee | 最近第3月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第三个月3G流量 | previous_3_month_g3_flux_usage_mb | 最近第三个月3G流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第3月收入(总账) | previous_3_month_total_revenue_fee | 最近第3月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第3月收入(总账)（元） | previous_3_month_total_revenue_fee | 最近第3月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第3月通话时长 | previous_3_month_voice_call_dura_usage_min | 最近第3月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第4月计费时长 | previous_4_month_bill_dura_duration | 最近第4月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第4月收入(账单) | previous_4_month_billed_revenue_fee | 最近第4月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第4月收入(账单)（元） | previous_4_month_billed_revenue_fee | 最近第4月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第4月收入(总账) | previous_4_month_total_revenue_fee | 最近第4月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第4月收入(总账)（元） | previous_4_month_total_revenue_fee | 最近第4月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第4月通话时长 | previous_4_month_voice_call_dura_usage_min | 最近第4月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第5月计费时长 | previous_5_month_bill_dura_duration | 最近第5月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第5月收入(账单) | previous_5_month_billed_revenue_fee | 最近第5月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第5月收入(账单)（元） | previous_5_month_billed_revenue_fee | 最近第5月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第5月收入(总账) | previous_5_month_total_revenue_fee | 最近第5月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第5月收入(总账)（元） | previous_5_month_total_revenue_fee | 最近第5月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第5月通话时长 | previous_5_month_voice_call_dura_usage_min | 最近第5月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第6月计费时长 | previous_6_month_bill_dura_duration | 最近第6月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第6月收入(账单) | previous_6_month_billed_revenue_fee | 最近第6月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第6月收入(账单)（元） | previous_6_month_billed_revenue_fee | 最近第6月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第6月收入(总账) | previous_6_month_total_revenue_fee | 最近第6月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第6月收入(总账)（元） | previous_6_month_total_revenue_fee | 最近第6月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近第6月通话时长 | previous_6_month_voice_call_dura_usage_min | 最近第6月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近活跃日期 | previous_a_date | 最近活跃日期 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近一次停机时间 | previous_block_date_time | 最近一次停机时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近通话日期 | previous_c_date | 最近通话日期 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月_套餐积分 | previous_dinner_integral_name | 上月_套餐积分 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月套餐积分 | previous_dinner_integral_name | 上月套餐积分；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近呼转日期 | previous_h_date | 最近呼转日期 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月_欠费不计收 | previous_invalid_post_bill_fee | 上月_欠费不计收 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月_租机计划 | previous_lease_plan_id | 上月_租机计划 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 上月实际月租 | previous_line_rule_level1_fee | 上月实际月租；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近一次停机原因 | previous_oper_reason_name | 最近一次停机原因 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最后一次终端注册日期 | previous_reg_date | 最后一次终端注册日期；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 日停机用户数 | previous_stop_date | 日停机用户数；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近停机日期 | previous_stop_date | 最近停机日期 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 月停机用户数 | previous_stop_date | 月停机用户数；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 最近停机时间 | previous_stop_date_time | 最近停机时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 销售品分类 | price_label_id_amount | 销售品分类 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主销售品档位 | price_level_fee | 主销售品档位 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 销售品档位（PPM） | price_level_fee | 销售品档位（PPM） | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 合约低消 | price_payment_least_amount | 合约低消 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 合约低消（PPM） | price_payment_least_amount | 合约低消（PPM） | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户分产品标签-跟踪 | price_plan_tag_amount | 用户分产品标签-跟踪 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户分产品标签-拍照 | price_plan_tag_init_amount | 用户分产品标签-拍照 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 销售品生效时间 | primary_price_plan_eff_date_time | 销售品生效时间 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 销售品失效时间 | primary_price_plan_exp_date_time | 销售品失效时间 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_销售品名称 | primary_price_plan_name | 主卡_销售品名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_销售品名称(仅限移固融合关联查询) | primary_price_plan_name | 宽带_销售品名称(仅限移固融合关联查询) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 销售品名称 | primary_price_plan_name | 销售品名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主销售品订购时间 | primary_price_plan_order_date_time | 主销售品订购时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 销售品订购时间 | primary_price_plan_order_date_time | 销售品订购时间 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主销售品发展人 | primary_price_plan_staff_id | 主销售品发展人 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主产品细类 | primary_product_id | 主产品细类 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_主产品细类(仅限移固融合关联查询) | primary_product_id | 宽带_主产品细类(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主产品细类一级 | primary_product_level1_id | 主产品细类一级 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主产品细类二级 | primary_product_level2_id | 主产品细类二级 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 融合成员角色标识 | product_component_relationship_role_id | 融合成员角色标识 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 融合成员角色标识(仅限移固融合关联查询) | product_component_relationship_role_id | 融合成员角色标识(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 推广渠道 | promotion_channel_name | 推广渠道 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 收货省份 | provicecode_name | 收货省份 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-固网账单收入 | pstn_fc_amount | 预估-固网账单收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估_固网账单收入 | pstn_fc_amount | 预估_固网账单收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 实时结余 | real_time_balance_amount | 实时结余；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月可用余额 | real_time_balance_amount | 本月可用余额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 单位用户实名制行业类型 | real_time_industry_id_type | 单位用户实名制行业类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 实名制时间 | realname_date_time | 实名制时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 收货人姓名 | receiver_name | 收货人姓名 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 收货人联系电话 | receiver_phone_name | 收货人联系电话 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 收货人联系电话(文件导入) | receiver_phone_name | 收货人联系电话(文件导入) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 当月充值金额 | recharge_amt_amount | 当月充值金额 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 当月充值金额（元） | recharge_amt_amount | 当月充值金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 订单推荐人 | recommend_user_name | 订单推荐人 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 红黑名单生效时间 | red_black_eff_date_time | 红黑名单生效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 红黑名单类型 | red_black_list_type | 红黑名单类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 翼支付红包金新资费减收费用 | redenvelope_fee | 翼支付红包金新资费减收费用 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 翼支付红包金老资费减收费用 | redenvelope_oldpp_fee | 翼支付红包金老资费减收费用 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 返款额 | refund_fee | 返款额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 返款额（元） | refund_fee | 返款额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_接入方式(仅限移固融合关联查询) | refund_rule_id | 宽带_接入方式(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 接入方式 | refund_rule_id | 接入方式 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 返还规则标识 | refund_rule_id | 返还规则标识 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 剩余返款额 | refunded_left_fee | 剩余返款额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 剩余返款额（元） | refunded_left_fee | 剩余返款额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 已返款金额 | refunded_sum_fee | 已返款金额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 已返款金额（元） | refunded_sum_fee | 已返款金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 潜在4升5终端换机用户 | reserv335_name | 潜在4升5终端换机用户 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_累计费用 | revenue_fee | 主卡_累计费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_累计费用（元） | revenue_fee | 主卡_累计费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 副卡_累计费用 | revenue_fee | 副卡_累计费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 累计费用 | revenue_fee | 累计费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 累计费用（元） | revenue_fee | 累计费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带融合壳子销售品(及单产品主销售品) | rh_comprod_price_plan_id | 宽带融合壳子销售品(及单产品主销售品) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带主用户编码 | rh_user_code | 宽带主用户编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-融合摊分后费用 | rhtf_after_fee | 预估-融合摊分后费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-融合摊分后费用（元） | rhtf_after_fee | 预估-融合摊分后费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估_融合摊分后费用(元） | rhtf_after_fee | 预估_融合摊分后费用(元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-融合摊分前费用 | rhtf_before_fee | 预估-融合摊分前费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-融合摊分前费用（元） | rhtf_before_fee | 预估-融合摊分前费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估_融合摊分前费用(元） | rhtf_before_fee | 预估_融合摊分前费用(元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-总账_融合摊分差值（元） | rhtf_cz_name | 预估-总账_融合摊分差值（元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-融合摊分差值 | rhtf_cz_name | 预估-融合摊分差值；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估_融合摊分差值(元） | rhtf_cz_name | 预估_融合摊分差值(元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 2021年双节营销拍照清单-清单5-211升5G | rise_211_5g_customer_name | 2021年双节营销拍照清单-清单5-211升5G | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 2021年双节营销拍照清单-清单2-升211 | rise_211_customer_name | 2021年双节营销拍照清单-清单2-升211 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月漫游通话时长 | roam_usage_min | >本月漫游通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >本月漫游通话时长(秒) | roam_usage_min | >本月漫游通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 促销人员 | sale_name | 促销人员 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-直销渠道人员细分 | sales_dsell_code | 渠道视图-直销渠道人员细分 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 销售品ID | sales_product_id | 销售品ID | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 销售品名称(电渠订单类) | sales_product_name | 销售品名称(电渠订单类) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 渠道视图-销售人员岗位 | sales_value_code | 渠道视图-销售人员岗位 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡号码 | service_number_id | 主卡号码 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡号码(全) | service_number_id | 主卡号码(全) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡号码(文件导入) | service_number_id | 主卡号码(文件导入) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 副卡号码 | service_number_id | 副卡号码 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 副卡号码(全) | service_number_id | 副卡号码(全) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 副卡号码(文件导入) | service_number_id | 副卡号码(文件导入) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 宽带_服务号码(仅限移固融合关联查询) | service_number_id | 宽带_服务号码(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 服务号码 | service_number_id | 服务号码 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 服务号码(全) | service_number_id | 服务号码(全) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 号段 | service_number_seg_type | 号段 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇区局（摊分前） | settlement_allocation_building_bureau_id | 楼宇区局（摊分前） | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 楼宇区局细类（摊分前） | settlement_allocation_building_bureau_level2_id | 楼宇区局细类（摊分前） | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 连续呼转开始日 | start_h_date | 连续呼转开始日 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 零话单开始日 | start_zcall_date | 零话单开始日；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 停租时间 | stop_rent_date_time | 停租时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 子品牌 | sub_brand_id | 子品牌 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 话费补贴金额（PPM） | subsidy_callfee_amount | 话费补贴金额（PPM）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 终端补贴金额（PPM） | subsidy_terminal_amount | 终端补贴金额（PPM）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 补贴类型 | subsidy_type | 补贴类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 补贴类型（PPM） | subsidy_type | 补贴类型（PPM） | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 终端补贴不含税冲减（元） | subtract_n_tax_fee | 终端补贴不含税冲减（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-终端补贴不含税冲减 | subtract_n_tax_fee | 预估-终端补贴不含税冲减 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-翼支付红包返费减收（元） | subtract_rebate_amt_name | 预估-翼支付红包返费减收（元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 翼支付一次性返费递延冲减（元） | subtract_rebate_ycx_name | 翼支付一次性返费递延冲减（元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-终端补贴税冲减 | subtract_rebate_ycx_name | 预估-终端补贴税冲减；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-翼支付一次性返费递延冲减 | subtract_rebate_ycx_name | 预估-翼支付一次性返费递延冲减；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 终端补贴 税 冲减（元） | subtract_tax_fee | 终端补贴 税 冲减（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 当日实际北京端月租 | sum_res_fee | 当日实际北京端月租 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 当月月租净增 | sum_res_jingzeng_fee | 当月月租净增 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 税务客户名称 | taxpayer_name | 税务客户名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 终端成本发生时间 | terminal_cost_date_time | 终端成本发生时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | IMEI号 | terminal_imei_count | IMEI号 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | UIM卡类型 | terminal_model_type | UIM卡类型；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 终端成本 | terminal_real_time_fee | 终端成本；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 离网时间 | termination_time | 离网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 测试电路标识 | test_circuit_tag_id | 测试电路标识 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估_摊分后费用 | tf_after_fee | 预估_摊分后费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估_摊分前费用 | tf_before_fee | 预估_摊分前费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估_总账_摊分前后的差额 | tf_cz_name | 预估_总账_摊分前后的差额；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-主副卡摊分后费用 | tf_fee | 预估-主副卡摊分后费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户即将欠费金额 | to_be_outstanding_fee | 用户即将欠费金额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户即将欠费金额（元） | to_be_outstanding_fee | 用户即将欠费金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 总余额 | total_balance_amount | 总余额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_本月实收总费用(元） | total_real_time_fee | 主卡_本月实收总费用(元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 副卡_本月实收总费用(元） | total_real_time_fee | 副卡_本月实收总费用(元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_本月实收总费用 | total_wrt_fee | 主卡_本月实收总费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月实收总费用 | total_wrt_fee | 本月实收总费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月实收总费用(元） | total_wrt_fee | 本月实收总费用(元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月实收欠费 | total_wrt_fee | 本月实收欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月销账总费用（元） | total_wrt_fee | 本月销账总费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 计费余额帐本类型ID | university_id_type | 计费余额帐本类型ID | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 所属高校 | university_name | 所属高校 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 计费余额帐本名称 | university_name_amount | 计费余额帐本名称 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 使用人ID | use_customer_id | 使用人ID | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 使用人姓名 | use_customer_name | 使用人姓名 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 使用人姓名(全) | use_customer_name | 使用人姓名(全) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月3G活跃用户数(流量大于0) | user_3g_type | 本月3G活跃用户数(流量大于0)；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户当前余额 | user_balance_amount | 用户当前余额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户信用度 | user_credit_value_name | 用户信用度 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 当前状态开始时间 | user_date_status | 当前状态开始时间；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 客户群类别 | user_group_kind_id_type | 客户群类别 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡_用户数 | user_id | 主卡_用户数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 是 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 副卡_用户数 | user_id | 副卡_用户数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 是 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户编号 | user_id | 用户编号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户编码 | user_id | 用户编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户编码(文件导入) | user_id | 用户编码(文件导入) | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 统计用户数 | user_id | 统计用户数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 是 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 自定义DPI | user_id | 自定义DPI | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 自定义销售品订购 | user_id | 自定义销售品订购 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户状态 | user_id_status | 用户状态 | varchar(64) | customer_user | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户建档员工六级部门 | user_in_department_id | 用户建档员工六级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户建档员工二级部门 | user_in_department_level2_id | 用户建档员工二级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户建档员工三级部门 | user_in_department_level3_id | 用户建档员工三级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户建档员工四级部门 | user_in_department_level4_id | 用户建档员工四级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户建档员工 | user_in_staff_id | 用户建档员工 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 权益平台新用户等级标准（主套餐档位（计费）） | user_levl_fee | 权益平台新用户等级标准（主套餐档位（计费）） | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户在网时长 | user_online_dura_duration | 用户在网时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户在网时长（月） | user_online_dura_duration | 用户在网时长（月） | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 用户停机时长 | user_stop_dura_duration | 用户停机时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 圈集团客户经理六级部门 | vir_grp_customer_manager_department_id | 圈集团客户经理六级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 圈集团客户经理二级部门 | vir_grp_customer_manager_department_level2_id | 圈集团客户经理二级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 圈集团客户经理三级部门 | vir_grp_customer_manager_department_level3_id | 圈集团客户经理三级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 圈集团客户经理四级部门 | vir_grp_customer_manager_department_level4_id | 圈集团客户经理四级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 圈集团客户经理五级部门 | vir_grp_customer_manager_department_level5_id | 圈集团客户经理五级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 圈集团客户经理 | vir_grp_customer_manager_id | 圈集团客户经理 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 圈集团客户名称 | vir_grp_customer_name | 圈集团客户名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 圈集团日期 | vir_grp_date | 圈集团日期；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | volte高清视频时长（秒） | voice_call_dura_video_volte_duration | volte高清视频时长（秒）；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | volte高清语音时长（秒） | voice_call_dura_voice_volte_duration | volte高清语音时长（秒）；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计通话时长 | voice_call_usage_min | 本月累计通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 本月累计通话时长123 | voice_call_usage_min | 本月累计通话时长123；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 维挽服务经理二级部门 | ww_svc_manager_department_level2_id | 维挽服务经理二级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 维挽服务经理三级部门 | ww_svc_manager_department_level3_id | 维挽服务经理三级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 维挽服务经理四级部门 | ww_svc_manager_department_level4_id | 维挽服务经理四级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 2021年双节营销拍照清单-清单1-有机无套 | youjiwutao_user_name | 2021年双节营销拍照清单-清单1-有机无套 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 2021年双节营销拍照清单-清单3-有套无机 | youtaowuji_user_name | 2021年双节营销拍照清单-清单3-有套无机 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 年付销售品 | ypay_primary_price_plan_id | 年付销售品 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 年付销售品名称 | ypay_primary_price_plan_id_name | 年付销售品名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | >固网一次性费用 | z_pstn_once_fee | >固网一次性费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-终端直降减收(不含税) | zdzj_n_tax_fee | 预估-终端直降减收(不含税)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-终端直降减收（不含税） | zdzj_n_tax_fee | 预估-终端直降减收（不含税）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-终端直降减收(税) | zdzj_tax_fee | 预估-终端直降减收(税)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-终端直降减收（税） | zdzj_tax_fee | 预估-终端直降减收（税）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主转副类型 | zf_card_change_id_type | 主转副类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-总账_主副卡摊分前费用 | zfk_tf_before_fee | 预估-总账_主副卡摊分前费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-总账_主副卡摊分前费用（元） | zfk_tf_before_fee | 预估-总账_主副卡摊分前费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估_总账_主副卡摊分前费用(元） | zfk_tf_before_fee | 预估_总账_主副卡摊分前费用(元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-主副卡摊分差值（元） | zfk_tf_cz_name | 预估-主副卡摊分差值（元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估-总账_主副卡摊分差值 | zfk_tf_cz_name | 预估-总账_主副卡摊分差值；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 预估_总账_主副卡摊分差值(元） | zfk_tf_cz_name | 预估_总账_主副卡摊分差值(元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 主卡用户编码 | zk_user_code | 主卡用户编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 专线客户费用 | zx_kh_fee | 专线客户费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询日视图_3.0 | DA.a_u_360_all_view_d | 专线摊分费用 | zx_tf_fee | 专线摊分费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 新装受理渠道ID | accept_channel_id | 新装受理渠道ID | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 新装受理渠道名称 | accept_channel_name | 新装受理渠道名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 帐户数 | account_code | 帐户数；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 帐户编码 | account_code | 帐户编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 账户编码 | account_code | 账户编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 账户编号 | account_id | 账户编号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 账户经理二级部门 | account_manager_department_level2_name | 账户经理二级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 账户经理三级部门 | account_manager_department_level3_name | 账户经理三级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 账户经理四级部门 | account_manager_department_level4_name | 账户经理四级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 账户经理六级部门 | account_manager_department_name | 账户经理六级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 账户经理 | account_manager_id | 账户经理 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 帐户名称 | account_name | 帐户名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 帐户名称（全） | account_name | 帐户名称（全） | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 账户名称 | account_name | 账户名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 账户名称(全) | account_name | 账户名称(全) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费用户数 | accumulated_outstanding_fee | 欠费用户数；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 累计欠费 | accumulated_outstanding_fee | 累计欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 累计欠费（元） | accumulated_outstanding_fee | 累计欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户发展六级部门编码 | acquisition_department_code | 用户发展六级部门编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户发展六级部门编码(文件导入) | acquisition_department_code | 用户发展六级部门编码(文件导入)；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_用户发展六级部门(仅限移固融合关联查询) | acquisition_department_id | 宽带_用户发展六级部门(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户发展六级部门 | acquisition_department_id | 用户发展六级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_用户发展二级部门(仅限移固融合关联查询) | acquisition_department_level2_id | 宽带_用户发展二级部门(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户发展二级部门 | acquisition_department_level2_id | 用户发展二级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_用户发展三级部门(仅限移固融合关联查询) | acquisition_department_level3_id | 宽带_用户发展三级部门(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户发展三级部门 | acquisition_department_level3_id | 用户发展三级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_用户发展四级部门(仅限移固融合关联查询) | acquisition_department_level4_id | 宽带_用户发展四级部门(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户发展四级部门 | acquisition_department_level4_id | 用户发展四级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_用户发展五级部门(仅限移固融合关联查询) | acquisition_department_level5_id | 宽带_用户发展五级部门(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户发展五级部门 | acquisition_department_level5_id | 用户发展五级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_用户发展员工(仅限移固融合关联查询) | acquisition_staff_id | 宽带_用户发展员工(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户发展员工 | acquisition_staff_id | 用户发展员工 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户发展员工ID | acquisition_staff_id | 用户发展员工ID | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户发展员工工号 | acquisition_staff_id | 用户发展员工工号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 入网日期 | activation_date | 入网日期；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主卡_用户入网时间 | activation_time | 主卡_用户入网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 入网时间 | activation_time | 入网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_入网时间(仅限移固融合关联查询) | activation_time | 宽带_入网时间(仅限移固融合关联查询)；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月累计活跃基站数 | active_cell_count | 本月累计活跃基站数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月累计活跃天数 | active_day_count | 本月累计活跃天数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 翼支付红包金到期未消费明细加回收入 | add_redenvelope_fee | 翼支付红包金到期未消费明细加回收入 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月增值费（元） | addval_fee | >本月增值费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_调账（元） | adjust_fee | 总账_调账（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 年龄分段 | age_split_name | 年龄分段 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 代理商编码 | agent_code | 代理商编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 发展人所属代理商 | agent_id | 发展人所属代理商 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 发展人所属代理商编码 | agent_id_code | 发展人所属代理商编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 发展人所属门店 | agent_point_id | 发展人所属门店 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 门店 | agent_point_id | 门店 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 累计缴费金额 | agg_amount | 累计缴费金额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 累计缴费金额（元） | agg_amount | 累计缴费金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 割接前调账费用（元） | agg_gjqtz_other_fee | 割接前调账费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 历史欠费（元） | agg_hisowe_other_fee | 历史欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 累计实收总费用 | agg_wrt_fee | 累计实收总费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 累计实收总费用(元） | agg_wrt_fee | 累计实收总费用(元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄10月欠费 | aging_10_month_outstanding_fee | 欠费帐龄10月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄10月欠费（元） | aging_10_month_outstanding_fee | 欠费帐龄10月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄11月欠费 | aging_11_month_outstanding_fee | 欠费帐龄11月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄11月欠费（元） | aging_11_month_outstanding_fee | 欠费帐龄11月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄12月欠费 | aging_12_month_outstanding_fee | 欠费帐龄12月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄12月欠费（元） | aging_12_month_outstanding_fee | 欠费帐龄12月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄1月欠费 | aging_1_month_outstanding_fee | 欠费帐龄1月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄1月欠费（元） | aging_1_month_outstanding_fee | 欠费帐龄1月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄2月欠费 | aging_2_month_outstanding_fee | 欠费帐龄2月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄2月欠费（元） | aging_2_month_outstanding_fee | 欠费帐龄2月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄3月欠费 | aging_3_month_outstanding_fee | 欠费帐龄3月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄3月欠费（元） | aging_3_month_outstanding_fee | 欠费帐龄3月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄4月欠费 | aging_4_month_outstanding_fee | 欠费帐龄4月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄4月欠费（元） | aging_4_month_outstanding_fee | 欠费帐龄4月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄5月欠费 | aging_5_month_outstanding_fee | 欠费帐龄5月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄5月欠费（元） | aging_5_month_outstanding_fee | 欠费帐龄5月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄6月欠费 | aging_6_month_outstanding_fee | 欠费帐龄6月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄6月欠费（元） | aging_6_month_outstanding_fee | 欠费帐龄6月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄7月欠费 | aging_7_month_outstanding_fee | 欠费帐龄7月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄7月欠费（元） | aging_7_month_outstanding_fee | 欠费帐龄7月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄8月欠费 | aging_8_month_outstanding_fee | 欠费帐龄8月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄8月欠费（元） | aging_8_month_outstanding_fee | 欠费帐龄8月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄9月欠费 | aging_9_month_outstanding_fee | 欠费帐龄9月欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费帐龄9月欠费（元） | aging_9_month_outstanding_fee | 欠费帐龄9月欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 公交卡一卡通卡号 | all_purpose_card_id | 公交卡一卡通卡号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本年累计考核收入 | all_year_fee | 本年累计考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 地区编码 | area_id_code | 地区编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 基站所属区域 | area_name | 基站所属区域 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 当前星级生效时间 | assess_date_time | 当前星级生效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 考核二级部门 | assessment_department_level2_id | 考核二级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 考核三级部门 | assessment_department_level3_id | 考核三级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-实体渠道类型 | attr_value_type | 渠道视图-实体渠道类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 三个月平均收入（融合摊分前） | avg_3_rhtf_before_fee | 三个月平均收入（融合摊分前）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本年累计欠费罚收 | badowe_all_year_amount | 本年累计欠费罚收；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本年累计欠费罚收(调整后) | badowe_all_year_tz_amount | 本年累计欠费罚收(调整后)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月本地通话次数 | base_count | >本月本地通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月基本计费时长 | base_duration | 本月基本计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 翼支付注册时间 | bestpay_reg_date_time | 翼支付注册时间 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月收入(账单) | bill_fee | 本月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月收入(账单)（元） | bill_fee | 本月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 入网月份 | billing_date | 入网月份；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 离网月份 | billing_date | 离网月份；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 租机计划订购日期 | billing_date | 租机计划订购日期；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 证件首次入网时间 | billing_time | 证件首次入网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 证件首次入网时间(月) | billing_time | 证件首次入网时间(月)；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 捆绑机型 | binding_device_model_name | 捆绑机型 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 租机协议名称 | binding_device_model_name | 租机协议名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-商圈状态 | biz_zone_code_status | 渠道视图-商圈状态 | varchar(64) | customer_user | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-商圈类型 | biz_zone_code_type | 渠道视图-商圈类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-商圈级别 | biz_zone_level_name | 渠道视图-商圈级别 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-商圈名称 | biz_zone_name | 渠道视图-商圈名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-商圈编码 | biz_zone_number_code | 渠道视图-商圈编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 品牌 | brand_id | 品牌 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_宽带速率(仅限移固融合关联查询) | brd_line_rate | 宽带_宽带速率(仅限移固融合关联查询) | decimal(9,6) | customer_user | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带速率 | brd_line_rate | 宽带速率 | decimal(9,6) | customer_user | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇区县 | building_area_id | 楼宇区县 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_楼宇区局(仅限移固融合关联查询) | building_bureau_id | 宽带_楼宇区局(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇区局 | building_bureau_id | 楼宇区局 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇编号 | building_code | 楼宇编号 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇编码 | building_code | 楼宇编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_楼宇区局二级(仅限移固融合关联查询) | building_district_id | 宽带_楼宇区局二级(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇区局二级 | building_district_id | 楼宇区局二级 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇区局细类（摊分后) | building_district_id | 楼宇区局细类（摊分后) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 所属组别 | building_group_name | 所属组别 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_楼宇编号(仅限移固融合关联查询) | building_id | 宽带_楼宇编号(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇编号 | building_id | 楼宇编号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_楼宇性质(仅限移固融合关联查询) | building_kind_id | 宽带_楼宇性质(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇性质 | building_kind_id | 楼宇性质 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇等级 | building_levels_name | 楼宇等级 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇经理六级部门 | building_manager_department_id | 楼宇经理六级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇经理二级部门 | building_manager_department_level2_id | 楼宇经理二级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇经理三级部门 | building_manager_department_level3_id | 楼宇经理三级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇经理四级部门 | building_manager_department_level4_id | 楼宇经理四级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇经理 | building_manager_id | 楼宇经理 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_楼宇名称(仅限移固融合关联查询) | building_name | 宽带_楼宇名称(仅限移固融合关联查询) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇名称 | building_name | 楼宇名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_楼宇类型(仅限移固融合关联查询) | building_type | 宽带_楼宇类型(仅限移固融合关联查询) | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇类型 | building_type | 楼宇类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 基站所属区局 | bureau_name | 基站所属区局 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月累计其他流量 | busi_type_level16_usage_mb | 月累计其他流量 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 商机编码 | business_code | 商机编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月C网增值业务费（元） | c_addval_fee | >>本月C网增值业务费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月C网套餐基本费（元） | c_dnnr_rent_fee | >>本月C网套餐基本费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月C网_港澳台长途通话费（元） | c_gattoll_voice_call_fee | >>本月C网_港澳台长途通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月C网_国际长途通话费（元） | c_gj_voice_call_fee | >>本月C网_国际长途通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月C网_国内长途通话费（元） | c_gn_voice_call_fee | >>本月C网_国内长途通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月C网_本地通话费（元） | c_loc_voice_call_fee | >>本月C网_本地通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月C网_手机上网使用费（元） | c_mobile_data_fee | >>本月C网_手机上网使用费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月C网_一次性费用（元） | c_once_fee | >>本月C网_一次性费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月C网其他费（元） | c_other_fee | >>本月C网其他费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月C网月租费（元） | c_rent_fee | >>本月C网月租费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月C网_漫游通话费（元） | c_roam_voice_call_fee | >>本月C网_漫游通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月C网短信通信费（元） | c_sms_addval_fee | >>本月C网短信通信费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月C网_无线宽带使用费（元） | c_wibro_data_fee | >>本月C网_无线宽带使用费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 订单证件类型 | card_code_type | 订单证件类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 出生年份 | certificate_count | 出生年份；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户证件号码非空 | certificate_count | 客户证件号码非空 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户证件类型 | certificate_id_type | 客户证件类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 终端换机概率 | change_probaby_rate | 终端换机概率 | decimal(9,6) | customer_user | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-销售点区域 | channel_area_id | 渠道视图-销售点区域 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-销售点业务排他 | channel_busi_pt_id | 渠道视图-销售点业务排他 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-销售点业务范围 | channel_busi_scope_id | 渠道视图-销售点业务范围 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-渠道类别 | channel_class_type | 渠道视图-渠道类别 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-渠道类型 | channel_code_type | 渠道视图-渠道类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道归属 | channel_eda_type | 渠道归属 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-销售点功能类型 | channel_gn_id_type | 渠道视图-销售点功能类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-连锁经营主体类型 | channel_lsjy_id_type | 渠道视图-连锁经营主体类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道经理二级部门 | channel_manager_department_level2_name | 渠道经理二级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道经理三级部门 | channel_manager_department_level3_name | 渠道经理三级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道经理四级部门 | channel_manager_department_level4_name | 渠道经理四级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道经理六级部门 | channel_manager_department_name | 渠道经理六级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道经理 | channel_manager_name | 渠道经理 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图- 销售点卖场类型 | channel_mc_id_type | 渠道视图- 销售点卖场类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-销售点卖场类型 | channel_mc_id_type | 渠道视图-销售点卖场类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-销售点名称 | channel_name | 渠道视图-销售点名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-销售点编码 | channel_number_code | 渠道视图-销售点编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-渠道状态 | channel_number_status | 渠道视图-渠道状态 | varchar(64) | customer_user | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-授权门店级别 | channel_sq_class_id | 渠道视图-授权门店级别 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-渠道子类型 | channel_subtype_code_type | 渠道视图-渠道子类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-专营门店类别 | channel_zyd_class_id_type | 渠道视图-专营门店类别 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-自有厅级别 | channel_zyt_class_id | 渠道视图-自有厅级别 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 测试电路结束日期 | circuit_end_date | 测试电路结束日期 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 测试电路开始日期 | circuit_start_date | 测试电路开始日期 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 收货地市 | citycode_name | 收货地市 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 移动移动关联用户数 | cmc_cuser_amt_count | 移动移动关联用户数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 移动固网关联用户数 | cmc_guser_amt_count | 移动固网关联用户数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 融合宽带壳子id | combo_brand_product_inst_id | 融合宽带壳子id | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 组合产品细类 | combo_product_id | 组合产品细类 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 组合产品实例 | combo_product_instance_id | 组合产品实例；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 组合销售品细类 | combo_product_offer_id | 组合销售品细类 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 组合销售品成员角色 | combo_product_relationship_role_name | 组合销售品成员角色 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 追溯佣金 | commission_append_recharge_agg_name | 追溯佣金 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 奖励佣金 | commission_award_recharge_agg_name | 奖励佣金 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 当月奖励佣金 | commission_award_recharge_tm_name | 当月奖励佣金；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 基础佣金 | commission_base_recharge_agg_name | 基础佣金 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 当月基础佣金 | commission_base_recharge_tm_name | 当月基础佣金；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇代理费 | commission_build_recharge_name | 楼宇代理费；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月佣金 | commission_fee | 本月佣金；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 补扣其他 | commission_other_recharge_agg_name | 补扣其他 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 当月其他佣金 | commission_other_recharge_tm_name | 当月其他佣金；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 业务代理费 | commission_serv_recharge_name | 业务代理费；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 固网分成费 | commission_tel_fc_name | 固网分成费；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 投诉次数 | complain_count | 投诉次数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 机房位置 | computer_plant_position_name | 机房位置 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 接应经理二级部门 | con_manager_department_level2_name | 接应经理二级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 接应经理三级部门 | con_manager_department_level3_name | 接应经理三级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 接应经理四级部门 | con_manager_department_level4_name | 接应经理四级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 接应经理六级部门 | con_manager_department_name | 接应经理六级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 接应经理（服务账户经理） | con_manager_name | 接应经理（服务账户经理） | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 合作渠道（发展代理商） | coop_channel_name | 合作渠道（发展代理商） | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 关联合作渠道单元 | cooperation_channel_unit_name | 关联合作渠道单元 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 收货区县 | countycode_count | 收货区县 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 建档时间 | create_date_time | 建档时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 联通移动关联用户数 | cuc_cuser_amt_count | 联通移动关联用户数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 联通固网关联用户数 | cuc_guser_amt_count | 联通固网关联用户数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月新增欠费用户数 | current_month_outstanding_fee | 月新增欠费用户数；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本期欠费 | current_month_outstanding_fee | 本期欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本期欠费（元） | current_month_outstanding_fee | 本期欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本年欠费 | current_year_outstanding_fee | 本年欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本年欠费（元） | current_year_outstanding_fee | 本年欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 入网人证件类型 | customer_card_type | 入网人证件类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户主要联系人姓名 | customer_contact_name | 客户主要联系人姓名 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户主要联系人电话 | customer_contact_phone_name | 客户主要联系人电话 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 证件首次入网时间(年) | customer_first_activation_date_time | 证件首次入网时间(年)；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户分群_归属 | customer_group_id | 客户分群_归属 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户数 | customer_id | 客户数 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户编号 | customer_id | 客户编号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 清单客户名称 | customer_list_name | 清单客户名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户经理二级部门 | customer_manager_department_level2_name | 客户经理二级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户经理三级部门 | customer_manager_department_level3_name | 客户经理三级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户经理四级部门 | customer_manager_department_level4_name | 客户经理四级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户经理六级部门 | customer_manager_department_name | 客户经理六级部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户经理 | customer_manager_id | 客户经理 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户名称 | customer_name | 客户名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户名称(全) | customer_name | 客户名称(全) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户名称（全） | customer_name | 客户名称（全） | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 入网人号码 | customer_phone_id | 入网人号码 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 入网人号码(文件导入) | customer_phone_id | 入网人号码(文件导入) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户转移部门 | customer_transfer_department_name | 客户转移部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月缴费金额 | customer_user_amount | 本月缴费金额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月缴费金额（元） | customer_user_amount | 本月缴费金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 入网人姓名 | customername_name | 入网人姓名 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月数据费（元） | data_fee | >本月数据费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 数据日期 | data_time | 数据日期 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 性别 | decimal_count | 性别；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 订单配送方式 | delivery_method_code | 订单配送方式 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 配送时间 | delivery_time | 配送时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道类型 | department_type | 渠道类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 手机品牌 | device_brand_id | 手机品牌 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 机损金额（总欠费口径） | device_cost_all_outstanding_amount | 机损金额（总欠费口径）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 手机成本 | device_cost_name | 手机成本 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 手机成本（元） | device_cost_name | 手机成本（元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 终端成本 | device_cost_name | 终端成本；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 手机型号 | device_model_id | 手机型号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 终端出现次数 | device_reg_found_count | 终端出现次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 实交购机款（元） | device_reg_found_count_fee | 实交购机款（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 实交预存（元） | device_reg_found_seq_name | 实交预存（元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 终端出现次序 | device_reg_found_seq_name | 终端出现次序；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 实交押金（元） | device_reg_previous_accnbr_name | 实交押金（元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 终端出现组号 | device_reg_previous_accnbr_name | 终端出现组号；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 存量迁转价值 | diff_fee | 存量迁转价值 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 电子渠道用户类型 | digital_channel_user_type | 电子渠道用户类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 订单编码 | digital_order_code | 订单编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 订单编码(文件导入) | digital_order_code | 订单编码(文件导入) | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 订单状态 | digital_order_status | 订单状态 | varchar(64) | customer_user | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 订单类型 | digital_order_type | 订单类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 号码转入前运营商 | divert_operator_id | 号码转入前运营商 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 双计人六级部门 | double_cal_department_id | 双计人六级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 双计人二级部门 | double_cal_department_level2_id | 双计人二级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 双计人三级部门 | double_cal_department_level3_id | 双计人三级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 双计人四级部门 | double_cal_department_level4_id | 双计人四级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 双计人 | double_cal_staff_id | 双计人 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 一卡双芯关联用户ID | double_user_id | 一卡双芯关联用户ID | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_减掉一卡双芯语音部分（元） | double_voice_call_fee | 总账_减掉一卡双芯语音部分（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_加回一卡双芯无线宽带部分（元） | double_wire_fee | 总账_加回一卡双芯无线宽带部分（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-一级分类 | dvlp_chnl_1_type | 渠道视图-一级分类 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-二级分类 | dvlp_chnl_2_type | 渠道视图-二级分类 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-细分属性 | dvlp_chnl_3_type | 渠道视图-细分属性 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >彩信SP上行条数 | dz_mo_mms_count | >彩信SP上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >SP上行条数 | dz_mo_sms_count | >SP上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >彩信SP下行条数 | dz_mt_mms_count | >彩信SP下行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >SP下行条数 | dz_mt_sms_count | >SP下行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 教育校园发展人 | edu_staff_id | 教育校园发展人 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 政企行业类型 | ent_industry_id_type | 政企行业类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 政企_价值等级 | ent_value_class_id | 政企_价值等级 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 交换区 | exch_dir_id | 交换区 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 免催停失效日期 | exp_date | 免催停失效日期 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 免催停失效时期 | exp_date | 免催停失效时期 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 有效时间数值 | exp_month_time | 有效时间数值 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 补差款（元） | extra_dev_fee | 补差款（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月激活用户数 | first_active_date | 月激活用户数；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 首次激活时间（固网起租时间） | first_active_date_time | 首次激活时间（固网起租时间）；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户主用基站(3个月) | first_cell_3_count | 用户主用基站(3个月) | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户主用基站 | first_cell_count | 用户主用基站 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 通话时长第一多的基站的通话时长 | first_cell_voice_call_dura_usage_min | 通话时长第一多的基站的通话时长 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 通话时长第一多的基站的通话时长(秒) | first_cell_voice_call_dura_usage_min | 通话时长第一多的基站的通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-渠道初始合作时间 | first_coop_time | 渠道视图-渠道初始合作时间 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带流量上网流量第一多的无线宽带流量 | first_ix_cell_flux_usage_mb | 无线宽带流量上网流量第一多的无线宽带流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带流量上网流量第一多的流量 | first_ix_cell_flux_usage_mb | 无线宽带流量上网流量第一多的流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带流量上网流量第一多的流量(KB) | first_ix_cell_flux_usage_mb | 无线宽带流量上网流量第一多的流量(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带流量第一多的基站 | first_ix_flux_cell_usage_mb | 无线宽带流量第一多的基站 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 流量第一多的基站 | first_ix_flux_cell_usage_mb | 流量第一多的基站 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带时长第一多的基站 | first_ix_msc_cellid_duration | 无线宽带时长第一多的基站 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最早欠费月份 | first_outstanding_month_date | 最早欠费月份 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 通话时长第一多的基站 | first_voice_call_msc_cellid_usage_min | 通话时长第一多的基站 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月累计固网宽带时长 | fix_brd_dura_duration | 本月累计固网宽带时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月累计固网宽带流量(KB) | fix_brd_flux_usage_mb | 本月累计固网宽带流量(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 固网上网次数 | fix_count | 固网上网次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 副卡数 | fk_count | 副卡数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 流量区间 | flux_level_usage_mb | 流量区间；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 流量区间(MB) | flux_level_usage_mb | 流量区间(MB) | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 流量饱和度 | fluxuserate_usage_mb | 流量饱和度 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带流量第一多的基站的无线宽带流量的占比 | fm9990_ratio | 无线宽带流量第一多的基站的无线宽带流量的占比；由源表达式进行空值处理、截取或单位换算后形成 | decimal(9,6) | customer_user | 按比例字段规范命名为 xxx_ratio | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带流量第三多的基站的无线宽带流量的占比 | fm9990_ratio | 无线宽带流量第三多的基站的无线宽带流量的占比；由源表达式进行空值处理、截取或单位换算后形成 | decimal(9,6) | customer_user | 按比例字段规范命名为 xxx_ratio | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带流量第二多的基站的无线宽带流量的占比 | fm9990_ratio | 无线宽带流量第二多的基站的无线宽带流量的占比；由源表达式进行空值处理、截取或单位换算后形成 | decimal(9,6) | customer_user | 按比例字段规范命名为 xxx_ratio | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 通话时长第一多的基站的通话时长的占比 | fm9990_ratio | 通话时长第一多的基站的通话时长的占比；由源表达式进行空值处理、截取或单位换算后形成 | decimal(9,6) | customer_user | 按比例字段规范命名为 xxx_ratio | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 通话时长第三多的基站的通话时长的占比 | fm9990_ratio | 通话时长第三多的基站的通话时长的占比；由源表达式进行空值处理、截取或单位换算后形成 | decimal(9,6) | customer_user | 按比例字段规范命名为 xxx_ratio | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 通话时长第二多的基站的通话时长的占比 | fm9990_ratio | 通话时长第二多的基站的通话时长的占比；由源表达式进行空值处理、截取或单位换算后形成 | decimal(9,6) | customer_user | 按比例字段规范命名为 xxx_ratio | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月免费3G总时长 | free_g3_dura_duration | 本月免费3G总时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月免费3G总流量(KB) | free_g3_flux_usage_mb | 本月免费3G总流量(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月免费无线宽带总时长 | free_ix_duration | 本月免费无线宽带总时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月免费无线宽带总流量(KB) | free_ix_usage_mb | 本月免费无线宽带总流量(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月免费主叫计费时长 | free_outbound_call_billing_duration | 本月免费主叫计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月免费短信条数 | free_sms_count | 本月免费短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月2G上网流量 | g2_flux_usage_mb | 本月2G上网流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月3G上网时长 | g3_dura_duration | 本月3G上网时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月3G上网流量 | g3_flux_usage_mb | 本月3G上网流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标签-本月3G流量大于5GB | g3_flux_usage_mb | 标签-本月3G流量大于5GB；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 3转4 | g3_to_g4_name | 3转4；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月累计4G上网时长 | g4_dura_duration | 月累计4G上网时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月累计4G上网流量 | g4_flux_usage_mb | 月累计4G上网流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月累计5G上网流量 | g5_flux_usage_mb | 月累计5G上网流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月固网_宽带上网使用费（元） | g_ad_data_fee | >>本月固网_宽带上网使用费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月固网宽带月租（元） | g_ad_rent_fee | >>本月固网宽带月租（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月固网_专线接入互联网增值业务使用费（元） | g_ddn_data_fee | >>本月固网_专线接入互联网增值业务使用费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月固网专线月租（元） | g_ddn_rent_fee | >>本月固网专线月租（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 固网港澳台长途费（元） | g_gat_voice_call_fee | 固网港澳台长途费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 固网国际长途费（元） | g_gj_voice_call_fee | 固网国际长途费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 固网国内长途费（元） | g_gn_voice_call_fee | 固网国内长途费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 固网本地通话费（元） | g_loc_voice_call_fee | 固网本地通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月固网_一次性费用（元） | g_once_fee | >>本月固网_一次性费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月固网其他费（元） | g_other_fee | >>本月固网其他费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月固网_预付费宽带业务使用费（元） | g_ppcad_data_fee | >>本月固网_预付费宽带业务使用费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 固网长途费（元） | g_toll_voice_call_fee | 固网长途费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月固网语音使用费（元） | g_voice_call_fee | >>本月固网语音使用费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月固网语音月租（元） | g_voice_call_rent_fee | >>本月固网语音月租（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月港澳台漫游计费时长 | gat_roam_bill_dura_duration | 本月港澳台漫游计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月港澳台漫游数据流量 | gat_roam_ix_flux_usage_mb | 本月港澳台漫游数据流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | GIS目标用户单月在小区天数-本月 | gis_live_day_count | GIS目标用户单月在小区天数-本月 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月国际长途计费时长 | gj_bill_dura_duration | 本月国际长途计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月国际漫游被叫计费时长 | gj_roam_inbound_call_bill_dur_duration | 本月国际漫游被叫计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月国际漫游数据流量 | gj_roam_ix_flux_usage_mb | 本月国际漫游数据流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月国际漫游主叫计费时长 | gj_roam_outbound_call_bill_dur_duration | 本月国际漫游主叫计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月国际漫游短信条数 | gj_roam_sms_tims_count | 本月国际漫游短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最低管控价 | gk_value_id_usage_min | 最低管控价 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 集团编码 | group_id_code | 集团编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | HB预用户实收 | hb_pre_fee | HB预用户实收；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 行短彩结算支出（95/12/11）（经分测算） | hdc_js_95_12_11_fee | 行短彩结算支出（95/12/11）（经分测算） | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 行短彩结算支出（经分测算） | hdc_js_fee | 行短彩结算支出（经分测算） | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | ICT收入 | ict_income_fee | ICT收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | ICT收入（元） | ict_income_fee | ICT收入（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 数字中心名称 | idc_center_name | 数字中心名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 机架电力要求(含单位) | idc_ele_req_name | 机架电力要求(含单位) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 互联网带宽出租计费方式 | idc_net_lease_fee_type | 互联网带宽出租计费方式 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 互联网带宽出租接入类型 | idc_net_lease_service_type | 互联网带宽出租接入类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 互联网带宽速率 | idc_net_rate | 互联网带宽速率 | decimal(9,6) | customer_user | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 2016年合约到期用户拍照标识 | if_lease_exp_2016_snap_id | 2016年合约到期用户拍照标识 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 21年合约到期用户到期标识 | if_lease_exp_2016_snap_id | 21年合约到期用户到期标识 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | IMSI | imsi_count | IMSI | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月被叫通话时长 | inbound_call_usage_min | >本月被叫通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月被叫通话时长(秒) | inbound_call_usage_min | >本月被叫通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 号码初始运营商 | initial_operator_id | 号码初始运营商 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 入网时主销售品 | initial_primary_price_plan_id | 入网时主销售品 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 装机地址 | install_address_name | 装机地址 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_楼宇区县(仅限移固融合关联查询) | int_name | 宽带_楼宇区县(仅限移固融合关联查询) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月综合信息月租（元） | inteinfo1_rent_fee | >>本月综合信息月租（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月综合信息月租费（元） | inteinfo2_rent_fee | >>本月综合信息月租费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月综合信息业务使用费（元） | inteinfo_addval_fee | >>本月综合信息业务使用费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 智能机操作系统 | intel_phone_system_name | 智能机操作系统 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 智能机操作系统版本 | intel_phone_version_name | 智能机操作系统版本 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 累计无效欠费 | invalid_agg_outstanding_fee | 累计无效欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本期无效欠费 | invalid_cur_month_outstanding_fee | 本期无效欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本年无效欠费 | invalid_cur_year_outstanding_fee | 本年无效欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无效欠费账期数 | invalid_cycle_count_date | 无效欠费账期数；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_后付费帐单无效减收（元） | invalid_post_bill_fee | 总账_后付费帐单无效减收（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_欠费不记收（元） | invalid_post_bill_fee | 总账_欠费不记收（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | IPTV对应宽带账号 | iptv_kd_service_number_id | IPTV对应宽带账号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 4G用户标志 | is_4g | 4G用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否4G用户标志 | is_4g | 是否4G用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 4G流量包用户标志 | is_4g_flux_pkg | 4G流量包用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否4G流量包用户标志 | is_4g_flux_pkg | 是否4G流量包用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 4G功能用户标志 | is_4g_func | 4G功能用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否4G功能用户标志 | is_4g_func | 是否4G功能用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 4G手机用户标志 | is_4g_imei | 4G手机用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否4G手机用户标志(自注册) | is_4g_imei | 是否4G手机用户标志(自注册) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 4G终端用户标志 | is_4g_lease_price_plan | 4G终端用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否4G终端用户标志(合约捆绑) | is_4g_lease_price_plan | 是否4G终端用户标志(合约捆绑) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 4G非套餐用户标志 | is_4g_none_price_plan | 4G非套餐用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否4G非套餐用户标志 | is_4g_none_price_plan | 是否4G非套餐用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 4G语音套餐用户标志 | is_4g_phone_user | 4G语音套餐用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否4G语音套餐用户标志 | is_4g_phone_user | 是否4G语音套餐用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 4G主套餐用户标志 | is_4g_primary_price_plan | 4G主套餐用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否4G主套餐用户标志 | is_4g_primary_price_plan | 是否4G主套餐用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 4G卡用户标志 | is_4g_sim | 4G卡用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否4G卡用户标志 | is_4g_sim | 是否4G卡用户标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 4G终端且开卡（集团口径） | is_4g_trml_flux_name | 4G终端且开卡（集团口径） | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否开通5G功能 | is_5g | 是否开通5G功能 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否5G预约用户 | is_5g_appointment | 是否5G预约用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否预约5G用户 | is_5g_appointment | 是否预约5G用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否呼通 | is_accept | 是否呼通 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 在网用户数 | is_active_subscriber | 在网用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_在网状态(仅限移固融合关联查询) | is_active_subscriber | 宽带_在网状态(仅限移固融合关联查询) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_在网用户数(仅限移固融合关联查询) | is_active_subscriber | 宽带_在网用户数(仅限移固融合关联查询) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_当月用户在网 | is_active_subscriber | 标志_当月用户在网 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 离网用户数 | is_active_subscriber | 离网用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月活跃用户数 | is_active_usage | 月活跃用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月零次用户数 | is_active_usage | 月零次用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月非活跃用户数 | is_active_usage | 月非活跃用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月是否活跃 | is_active_usage | 本月是否活跃 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否代理商合约异常用户 | is_agnt_leas_abnm_user | 是否代理商合约异常用户；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否翼支付用户标识 | is_best_payment | 是否翼支付用户标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 翼支付月活跃标识 | is_bestpay_active | 翼支付月活跃标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 翼支付月消费活跃标识 | is_bestpay_consume | 翼支付月消费活跃标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 翼支付月充值活跃标识 | is_bestpay_payment | 翼支付月充值活跃标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月是否出账（测试） | is_bill | 上月是否出账（测试） | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月出账用户数(A口径) | is_bill | 月出账用户数(A口径) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月是否出账(A口径) | is_bill | 本月是否出账(A口径) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月出账用户数(本地) | is_bill_local | 月出账用户数(本地)；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月是否出账(本地) | is_bill_local | 本月是否出账(本地) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 存量用户标识 | is_bill_user_snap | 存量用户标识；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否宽带到期 | is_billing | 是否宽带到期；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否捆绑机型 | is_binding_device_model | 是否捆绑机型；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否屏蔽营销类短信 | is_block_campaign_sms | 是否屏蔽营销类短信 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带极致融合标志 | is_brd_ultra_component | 宽带极致融合标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇分类 | is_building | 楼宇分类 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 移动出账用户数（A口径）(当月) | is_c_bill_a | 移动出账用户数（A口径）(当月) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 移动出账用户数（B口径）(当月) | is_c_bill_b | 移动出账用户数（B口径）(当月) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 移动出账用户数（C口径）(当月) | is_c_bill_c | 移动出账用户数（C口径）(当月) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 2G/3G/4G标志 | is_c_user_type | 2G/3G/4G标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 有车一族 | is_car_user | 有车一族 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 双模卡类型 | is_card | 双模卡类型 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_是否双模卡 | is_card | 标志_是否双模卡 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 双模卡(imsi)标志 | is_card_imsi | 双模卡(imsi)标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否集团下发橙分期目标用户 | is_chengfenqi_target | 是否集团下发橙分期目标用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 云计算服务 | is_cloud | 云计算服务 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否托收用户 | is_collection | 是否托收用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 佣金业务类型 | is_commission | 佣金业务类型 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 机型是否一致 | is_confer | 机型是否一致 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 赠送标志 | is_confer | 赠送标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_城市农村 | is_country | 标志_城市农村 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 电信当月新增标识 | is_ctc_add | 电信当月新增标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否过网 | is_ctc_guser_amt | 是否过网；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 电信当月流失标识 | is_ctc_lost | 电信当月流失标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否清单客户 | is_customer_list | 是否清单客户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否一卡双芯 | is_customer_user | 是否一卡双芯 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志-终端成本是否已发生 | is_customer_user | 标志-终端成本是否已发生 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_是否一卡双芯 | is_customer_user | 标志_是否一卡双芯 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标签-终端成本是否已发生 | is_customer_user | 标签-终端成本是否已发生 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_当日新增用户 | is_day_new | 标志_当日新增用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_当日离网用户 | is_day_off | 标志_当日离网用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 2019宽带异常离网 | is_del_product_inst | 2019宽带异常离网 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 手机终端标志(自注册) | is_device_g3 | 手机终端标志(自注册) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 电渠条线标识 | is_digital_channel_line | 电渠条线标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否双待机器 | is_double_net_phone | 是否双待机器 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_是一卡双芯 | is_double_user_id | 标志_是一卡双芯 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_非一卡双芯 | is_double_user_id | 标志_非一卡双芯 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否校园组织 | is_edu_org | 是否校园组织 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否教育校园 | is_education_school | 是否教育校园；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 政企_聚类标志 | is_ent_cluster | 政企_聚类标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 政企_国内国际标志 | is_ent_gngj | 政企_国内国际标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否有银行等平台交互短信 | is_exchange | 是否有银行等平台交互短信 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否公众号粉丝 | is_fans | 是否公众号粉丝 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 公免测试类型 | is_free | 公免测试类型 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 3G租机类别 | is_g3 | 3G租机类别 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否本月4G终端且开卡 | is_g4_device_sim | 是否本月4G终端且开卡 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月4G终端且开卡 | is_g4_device_sim | 本月4G终端且开卡 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 4G用户质量异常标签（卡） | is_g4_yichang_esn | 4G用户质量异常标签（卡） | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 4G用户质量异常标签（号码） | is_g4_yichang_serv | 4G用户质量异常标签（号码） | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 固话计费到达用户数(当月) | is_gh_arrive | 固话计费到达用户数(当月) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否可免费加宽带-本月 | is_gis_add_kd | 是否可免费加宽带-本月 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否GIS目标用户-本月 | is_gis_goal | 是否GIS目标用户-本月 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 移动语音高值用户标签 | is_hcall_value_name | 移动语音高值用户标签；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带高值用户标签 | is_hkd_value_name | 宽带高值用户标签；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否A级楼宇 | is_if_class_a | 是否A级楼宇 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否有责任人 | is_if_duty | 是否有责任人 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否ICT用户 | is_if_ict_user | 是否ICT用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否接入IDC机房 | is_if_idc_machine_room | 是否接入IDC机房 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 21年合约到期用户到期标志 | is_if_lease_exp_2016_snap | 21年合约到期用户到期标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否携转离网 | is_if_out_net | 是否携转离网 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否营业厅实名 | is_if_realname | 是否营业厅实名 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否拍照楼宇 | is_if_snap_build | 是否拍照楼宇 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否APP实名 | is_if_upload | 是否APP实名 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否提交APP实名 | is_if_upload | 是否提交APP实名 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否有使用人 | is_if_user_party | 是否有使用人 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否智能机 | is_intel_phone | 是否智能机 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | IPTV计费到达用户标识 | is_iptv_billing | IPTV计费到达用户标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否IPTV本月新装用户 | is_iptv_new | 是否IPTV本月新装用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否宽带上网活跃 | is_ix_fix_active | 是否宽带上网活跃 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_是否集团管控 | is_jt_gk | 标志_是否集团管控；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 捆绑机型象限 | is_kb_xx | 捆绑机型象限 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否5G融合 | is_kd_5g | 是否5G融合 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否5G融合-拍照 | is_kd_5g_snap | 是否5G融合-拍照 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带计费到达用户数 | is_kd_arrive | 宽带计费到达用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带计费到达用户标识 | is_kd_billing | 宽带计费到达用户标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带到期时间 | is_kd_year_end_dt | 宽带到期时间 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带到期类型 | is_kd_year_end_dt_type | 宽带到期类型 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否在到期月前3月内订购宽带续约 | is_kd_year_end_renew | 是否在到期月前3月内订购宽带续约 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否在到期当月订购宽带续约 | is_kd_year_end_renew_1m | 是否在到期当月订购宽带续约 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_是否租机 | is_lease | 标志_是否租机 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 新增低零用户标签 | is_low_zero_new | 新增低零用户标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 离网低零用户标签 | is_low_zero_off | 离网低零用户标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 新增机补用户机卡分离标签 | is_mach_card_new | 新增机补用户机卡分离标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 离网机补用户机卡分离标签 | is_mach_card_off | 离网机补用户机卡分离标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | UIM卡类型标签 | is_model | UIM卡类型标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_当月新增用户标志(仅限移固融合关联查询) | is_month_new | 宽带_当月新增用户标志(仅限移固融合关联查询) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_月新增用户数(仅限移固融合关联查询) | is_month_new | 宽带_月新增用户数(仅限移固融合关联查询) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月新增用户数 | is_month_new | 月新增用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_当月新增用户 | is_month_new | 标志_当月新增用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月新增异网标识 | is_month_new_ot_opera | 月新增异网标识；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_月离网用户数(仅限移固融合关联查询) | is_month_off | 宽带_月离网用户数(仅限移固融合关联查询) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月离网用户数 | is_month_off | 月离网用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_当月离网用户 | is_month_off | 标志_当月离网用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 迁转5G目标客户分值标签 | is_moving_5g_customer | 迁转5G目标客户分值标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_新老用户 | is_new_user | 标志_新老用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标签_新老用户 | is_new_user | 标签_新老用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否高校 | is_not | 是否高校 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 免催停用户分类 | is_number_double_stop | 免催停用户分类 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 免催停业务类型 | is_number_single_stop | 免催停业务类型 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 免催停生效日期 | is_number_urge | 免催停生效日期 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_计费欠费 | is_outstanding | 标志_计费欠费 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否流量溢出用户 | is_overflow | 是否流量溢出用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 去年12月是否出账（集团A口径） | is_p1y_bill | 去年12月是否出账（集团A口径） | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 机补用户协议未到期离网标签 | is_pre_mach_card_off | 机补用户协议未到期离网标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_预付后付 | is_prepaid_subscriber | 标志_预付后付 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 预付后付 | is_prepaid_subscriber | 预付后付 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月是否活跃 | is_previous_1_month_active | 上月是否活跃 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月是否出账(A口径) | is_previous_1_month_bill | 上月是否出账(A口径) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 移动存量政企类重点用户 | is_previous_1_month_c_gov | 移动存量政企类重点用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月4G终端且开卡 | is_previous_1_month_g4_device_sim | 上月4G终端且开卡 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否上月4G终端且开卡 | is_previous_1_month_g4_device_sim | 是否上月4G终端且开卡 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月宽带融合标志 | is_previous_1_month_ronghe | 上月宽带融合标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 星级拍照客户标识 | is_previous_1_month_star_level_snap | 星级拍照客户标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月是否5G套餐（含包）用户 | is_previous_1_month_user_5g | 上月是否5G套餐（含包）用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月是否出账（A口径） | is_previous_bill | 上月是否出账（A口径） | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上次宽带到期时间 | is_previous_kd_year_end_dt | 上次宽带到期时间 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月是否智能机 | is_previous_month_intel_phone | 上月是否智能机 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上次融合产品 | is_previous_yd_kd_label | 上次融合产品 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 去年12月是否在网 | is_previous_year_active_subscriber | 去年12月是否在网 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否打印发票 | is_print_invoice | 是否打印发票 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 新增疑似养卡用户标签 | is_raise_card_new | 新增疑似养卡用户标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 离网疑似养卡用户标签 | is_raise_card_off | 离网疑似养卡用户标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 新增重入网用户标签 | is_reentry_new | 新增重入网用户标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 离网重入网用户标签 | is_reentry_off | 离网重入网用户标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带融合标志 | is_ronghe | 宽带融合标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 翼支付季度活跃标识 | is_s_bestpay_active | 翼支付季度活跃标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 翼支付季度消费活跃标识 | is_s_bestpay_consume | 翼支付季度消费活跃标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 翼支付季度充值活跃标识 | is_s_bestpay_payment | 翼支付季度充值活跃标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 销渠条线标识 | is_sale_chnl_line | 销渠条线标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否校园标志 | is_school | 是否校园标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_移动固网 | is_service_network | 标志_移动固网 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 移动固网 | is_service_network | 移动固网 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否北京串码 | is_sf_bjimsi | 是否北京串码 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 中小企业标志 | is_smes | 中小企业标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 套餐升档标识 | is_suit_improve | 套餐升档标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否超级SIM卡支持终端 | is_super_sim_supported | 是否超级SIM卡支持终端 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否一般纳税人 | is_taxpayer | 是否一般纳税人 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否一拆一装 | is_termination_activation | 是否一拆一装 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 天翼高清计费到达用户数 | is_ty_arrive | 天翼高清计费到达用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否产生过5G话单 | is_used_5g_flux | 是否产生过5G话单 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月3g用户活跃标志(流量大于0M) | is_user_3g_type | 本月3g用户活跃标志(流量大于0M) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_本月3G活跃用户标志(流量大于0M) | is_user_3g_type | 标志_本月3G活跃用户标志(流量大于0M) | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 5G升级包销售品用户标签 | is_user_5g_sjb | 5G升级包销售品用户标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 5G套餐用户标签 | is_user_5g_tc | 5G套餐用户标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 圈集团标志 | is_vir_grp | 圈集团标志 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否VOLTE | is_volte | 是否VOLTE | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_无线宽带 | is_wireless | 标志_无线宽带 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 翼支付年活跃标识 | is_y_bestpay_active | 翼支付年活跃标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 翼支付年消费活跃标识 | is_y_bestpay_consume | 翼支付年消费活跃标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 翼支付年充值活跃标识 | is_y_bestpay_payment | 翼支付年充值活跃标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 融合产品 | is_yd_kd_label | 融合产品 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 融合产品-拍照 | is_yd_kd_label_snap | 融合产品-拍照 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 移动融合标签 | is_yd_label | 移动融合标签 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_当年新增用户 | is_year_new | 标志_当年新增用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 标志_当年离网用户 | is_year_off | 标志_当年离网用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月通话用户数 | is_zcall | 月通话用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月零通话用户数 | is_zcall | 月零通话用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月零次通话 | is_zcall | 本月零次通话；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否三无副卡用户标识 | is_zero3_fk | 是否三无副卡用户标识；由源表达式进行空值处理、截取或单位换算后形成 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 零信用度用户标识（CRM） | is_zero_credit | 零信用度用户标识（CRM） | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 是否副卡标识 | is_zero_fk | 是否副卡标识 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 0元送宽带目标用户 | is_zero_kd | 0元送宽带目标用户 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主副卡标识 | is_zf_card_id | 主副卡标识；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月无线宽带用户数 | is_zix | 月无线宽带用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月零次无线宽带用户数 | is_zix | 月零次无线宽带用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月零次无线宽带 | is_zix | 本月零次无线宽带 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月短信用户数 | is_zsms | 月短信用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月零次短信用户数 | is_zsms | 月零次短信用户数 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月零次短信 | is_zsms | 本月零次短信 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 自注册机型象限 | is_zzc_xx | 自注册机型象限 | boolean | customer_user | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月无线宽带时长_本地时长 | ix_base_duration | >本月无线宽带时长_本地时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月无线宽带流量_本地 | ix_base_usage_mb | 本月无线宽带流量_本地；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带上网次数 | ix_count | 无线宽带上网次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月无线宽带总时长 | ix_duration | 本月无线宽带总时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月无线宽带总上行流量_本地 | ix_mo_base_usage_mb | >>本月无线宽带总上行流量_本地；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月无线宽带总上行流量_本地(KB) | ix_mo_base_usage_mb | >>本月无线宽带总上行流量_本地(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月无线宽带总上行流量_漫游 | ix_mo_roam_usage_mb | >>本月无线宽带总上行流量_漫游；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月无线宽带总上行流量_漫游(KB) | ix_mo_roam_usage_mb | >>本月无线宽带总上行流量_漫游(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月无线宽带总下行流量_本地 | ix_mt_base_usage_mb | >>本月无线宽带总下行流量_本地；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月无线宽带总下行流量_本地(KB) | ix_mt_base_usage_mb | >>本月无线宽带总下行流量_本地(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月无线宽带总下行流量_漫游 | ix_mt_roam_usage_mb | >>本月无线宽带总下行流量_漫游；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月无线宽带总下行流量_漫游(KB) | ix_mt_roam_usage_mb | >>本月无线宽带总下行流量_漫游(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月无线宽带时长_漫游 | ix_roam_duration | >本月无线宽带时长_漫游；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月无线宽带流量_漫游 | ix_roam_usage_mb | 本月无线宽带流量_漫游；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 机损金额 | js_cost_amount | 机损金额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 机损金额（元） | js_cost_amount | 机损金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户类型（集团） | jt_customer_id_type | 用户类型（集团） | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 政企行业类型（大类） | jt_ent_industry_id_level1_type | 政企行业类型（大类）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 集团ICT-合同号 | jt_ict_contract_number_name | 集团ICT-合同号 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 集团ICT-项目号 | jt_ict_project_number_name | 集团ICT-项目号 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 集团集约IDC-合同号 | jt_idc_contract_number_name | 集团集约IDC-合同号 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 集团集约IDC-群号 | jt_idc_group_number_name | 集团集约IDC-群号 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 集团IDC--月租费 | jt_idc_month_fee_date | 集团IDC--月租费 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 集团集约IDC-月租费 | jt_idc_month_fee_date | 集团集约IDC-月租费 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 集团集约IDC-项目号 | jt_idc_project_number_name | 集团集约IDC-项目号 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 集团流水号 | jt_number_id | 集团流水号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 集团产品类型 | jt_product_type | 集团产品类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 专线集团摊出（元） | jttc_fee | 专线集团摊出（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 专线集团摊入（元） | jttr_fee | 专线集团摊入（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 专线境外摊出（元） | jwtc_fee | 专线境外摊出（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 专线境外摊入（元） | jwtr_fee | 专线境外摊入（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_融合活跃IPTV数 | kd_rh_iptv_count | 宽带_融合活跃IPTV数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月融合在网智慧产品数 | kd_rh_iptv_count | 本月融合在网智慧产品数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 融合在网智慧产品数-拍照 | kd_rh_iptv_snap_count | 融合在网智慧产品数-拍照 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月融合在网移动+副卡数 | kd_rh_yd_active_subscriber_count | 本月融合在网移动+副卡数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月融合在网移动+副卡数_x000D_ | kd_rh_yd_active_subscriber_count | 本月融合在网移动+副卡数_x000D_ | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_融合活跃移动+副卡数 | kd_rh_yd_count | 宽带_融合活跃移动+副卡数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月融合活跃移动+副卡数 | kd_rh_yd_count | 本月融合活跃移动+副卡数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 融合活跃移动+副卡数-拍照 | kd_rh_yd_snap_count | 融合活跃移动+副卡数-拍照 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月移动客服通话次数 | kefu_cmc_count | >本月移动客服通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月总客服通话次数 | kefu_count | 本月总客服通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月电信客服通话次数 | kefu_ctc_count | >本月电信客服通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月联通客服通话次数 | kefu_cuc_count | >本月联通客服通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 被叫移动客服次数 | kefu_inbound_call_cmc_count | 被叫移动客服次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 被叫电信客服次数 | kefu_inbound_call_ctc_count | 被叫电信客服次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 被叫联通客服次数 | kefu_inbound_call_cuc_count | 被叫联通客服次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主叫移动客服次数 | kefu_outbound_call_cmc_count | 主叫移动客服次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主叫电信客服次数 | kefu_outbound_call_ctc_count | 主叫电信客服次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主叫联通客服次数 | kefu_outbound_call_cuc_count | 主叫联通客服次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月实收上期费用 | lastmonth_wrt_fee | 本月实收上期费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月实收上期费用（元） | lastmonth_wrt_fee | 本月实收上期费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月销账上期费用（元） | lastmonth_wrt_fee | 本月销账上期费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 小区名称 | latn_name | 小区名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 协议在网月份数 | lease_active_subscriber_months_date | 协议在网月份数 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 协议在网月份数（PPM） | lease_active_subscriber_months_date | 协议在网月份数（PPM） | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 租机计划 | lease_plan_id | 租机计划；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 租机计划生效时间 | lease_price_plan_eff_date_time | 租机计划生效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 租机计划失效时间 | lease_price_plan_exp_date_time | 租机计划失效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 租机计划订购时间 | lease_price_plan_order_date_time | 租机计划订购时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 租机计划发展六级部门 | lease_price_plan_staff_department_id | 租机计划发展六级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 租机计划发展二级部门 | lease_price_plan_staff_department_level2_id | 租机计划发展二级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 租机计划发展三级部门 | lease_price_plan_staff_department_level3_id | 租机计划发展三级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 租机计划发展四级部门 | lease_price_plan_staff_department_level4_id | 租机计划发展四级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 租机计划发展五级部门 | lease_price_plan_staff_department_level5_id | 租机计划发展五级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 合约发展人 | lease_price_plan_staff_id | 合约发展人 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 租机计划发展人 | lease_price_plan_staff_id | 租机计划发展人 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 捆绑机型发生时间 | lease_term_dt_time | 捆绑机型发生时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 合约类型 | lease_type | 合约类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本端地址 | line_bd_address_name | 本端地址 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 对端地址 | line_dd_address_name | 对端地址 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 当月实际月租 | line_rule_level2_fee | 当月实际月租；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月本地计费时长（非漫游） | loacl_duration | 本月本地计费时长（非漫游）；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月本地拨本地通话时长 | loacl_notoll_bill_dur_usage_min | 本月本地拨本地通话时长 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月本地拨本地通话时长（秒） | loacl_notoll_bill_dur_usage_min | 本月本地拨本地通话时长（秒） | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月本地本地计费时长（非漫游非长途） | loacl_notoll_duration | 本月本地本地计费时长（非漫游非长途）；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月本地主叫计费时长（非漫游主叫） | loacl_outbound_call_duration | 本月本地主叫计费时长（非漫游主叫）；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本地行业大类 | local_industry_id_level1_type | 本地行业大类 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本地行业小类 | local_industry_id_type | 本地行业小类 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 流失风险用户 | loss_risk_probability_name | 流失风险用户 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 低效用户 | low_value_bil_user_name | 低效用户；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 当前星级失效时间 | membership_exp_date_time | 当前星级失效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户当前星级值 | membership_level_name | 客户当前星级值 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户当前星级等级 | membership_level_name | 客户当前星级等级 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 云讯通门数 | menshu_value_name | 云讯通门数 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户评级方式 | method_rate | 客户评级方式 | decimal(9,6) | customer_user | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 捆绑终端2,3,4G标识 | mkt_res_234g_id | 捆绑终端2,3,4G标识 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | UIM卡类型生效时间 | model_start_dt_type | UIM卡类型生效时间 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月无线宽带总下行流量 | monthly_downlink_usage_mb | >本月无线宽带总下行流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月无线宽带总下行流量(KB) | monthly_downlink_usage_mb | >本月无线宽带总下行流量(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月被叫通话次数 | monthly_inbound_call_count | >本月被叫通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月彩信条数 | monthly_mms_count | 本月彩信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月无线宽带总流量 | monthly_mobile_usage_mb | 本月无线宽带总流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月主叫通话次数 | monthly_outbound_call_count | >本月主叫通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月充值次数 | monthly_recharge_count | 本月充值次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月短信条数 | monthly_sms_count | 本月短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月无线宽带总上行流量 | monthly_uplink_usage_mb | >本月无线宽带总上行流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月无线宽带总上行流量(KB) | monthly_uplink_usage_mb | >本月无线宽带总上行流量(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月通话次数 | monthly_voice_call_count | 本月通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 存量迁转方向 | move_dir_name | 存量迁转方向 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 终端成本发生日期 | need_refund_account_cycle_date | 终端成本发生日期 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 需返款月份数 | need_refund_account_cycle_date | 需返款月份数；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 流量包创建时间 | net_create_date_usage_mb | 流量包创建时间；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 流量包失效时间 | net_end_dt_usage_mb | 流量包失效时间；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 流量包生效时间 | net_start_dt_usage_mb | 流量包生效时间；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 携号转入运营商名称 | network_id_in_name | 携号转入运营商名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-销售人员岗位 | new_sales_value_code | 渠道视图-销售人员岗位 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 考核部门 | new_user_perf_department_id | 考核部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 租机计划生效时间（待生效） | next_lease_price_plan_eff_date_time | 租机计划生效时间（待生效）；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 租机计划失效时间（待生效） | next_lease_price_plan_exp_date_time | 租机计划失效时间（待生效）；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主卡_租机计划将生效 | next_lease_price_plan_id | 主卡_租机计划将生效 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 租机计划（待生效） | next_lease_price_plan_id | 租机计划（待生效）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 下月的主销售品 | next_price_plan_4g_id | 下月的主销售品 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 连续沉默月份数 | noactive_months_date | 连续沉默月份数；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月累计活跃天数（不含拨打客服电话） | nokf_active_day_count | 本月累计活跃天数（不含拨打客服电话） | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 免催停申请部门 | number_urge_department_name | 免催停申请部门 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 单产品销售品细类 | offer_id | 单产品销售品细类 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 单产品销售品一级 | offer_level1_id | 单产品销售品一级 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 单产品销售品二级 | offer_level2_id | 单产品销售品二级 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 销售品一级目录 | offer_serv_type_level1_name | 销售品一级目录 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 销售品二级目录 | offer_serv_type_level2_name | 销售品二级目录 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 销售品三级目录 | offer_serv_type_level3_name | 销售品三级目录 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 2021年双节营销拍照清单-清单4-老旧网关升级 | old_gateway_up_name | 2021年双节营销拍照清单-清单4-老旧网关升级 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月一次性费用（元） | once_fee | >本月一次性费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月集中起租金额（元） | once_rent_fee | 本月集中起租金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上网行为类型 | online_behavior_id_type | 上网行为类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 订单AB类型 | order_abtype_type | 订单AB类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 订单创建时间 | order_created_time | 订单创建时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 订单渠道 | order_data_channel_code | 订单渠道 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 订单金额(实际支付金额) | order_paid_amount | 订单金额(实际支付金额) | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 订单来源 | order_source_code | 订单来源 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 原始端口数 | ori_port_cnt_name | 原始端口数 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月其他费（元） | other_fee | >本月其他费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月主叫计费时长 | outbound_call_billing_duration | 本月主叫计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月主叫移动通话次数 | outbound_call_cmc_count | >>本月主叫移动通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月主叫移动通话时长 | outbound_call_cmc_usage_min | >>本月主叫移动通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月主叫移动通话时长(秒) | outbound_call_cmc_usage_min | >>本月主叫移动通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月主叫电信通话次数 | outbound_call_ctc_count | >>本月主叫电信通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月主叫电信通话时长 | outbound_call_ctc_usage_min | >>本月主叫电信通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月主叫电信通话时长(秒) | outbound_call_ctc_usage_min | >>本月主叫电信通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月主叫联通通话次数 | outbound_call_cuc_count | >>本月主叫联通通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月主叫联通通话时长 | outbound_call_cuc_usage_min | >>本月主叫联通通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月主叫联通通话时长(秒) | outbound_call_cuc_usage_min | >>本月主叫联通通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | volte视频本月主叫通话时长 | outbound_call_dura_video_volte_usage_min | volte视频本月主叫通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | volte语音本月主叫通话时长 | outbound_call_dura_voice_volte_usage_min | volte语音本月主叫通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月主叫通话时长 | outbound_call_usage_min | >本月主叫通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月主叫通话时长(秒) | outbound_call_usage_min | >本月主叫通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户欠费次数（自2019年1月） | outstanding_count_fee | 用户欠费次数（自2019年1月）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 机损金额（无效欠费口径） | outstanding_cycle_count_amount | 机损金额（无效欠费口径）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总欠费账期数 | outstanding_cycle_count_date | 总欠费账期数；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 欠费月份数 | outstanding_months_date | 欠费月份数；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 流量溢出费用 | overflow_fee_usage_mb | 流量溢出费用 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 覆盖地址id | overlay_address_id | 覆盖地址id | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_不记收回收（元） | oweback_fee | 总账_不记收回收（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_往月不计收回收（元） | oweback_fee | 总账_往月不计收回收（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月累彩信计点对点短信 | p2p_mms_count | >本月累彩信计点对点短信；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月点对点移动上行条数 | p2p_mo_cmc_count | >>本月点对点移动上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月点对点电信上行条数 | p2p_mo_ctc_count | >>本月点对点电信上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月点对点联通上行条数 | p2p_mo_cuc_count | >>本月点对点联通上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >彩信点对点上行条数 | p2p_mo_mms_count | >彩信点对点上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>本月点对点其他上行条数 | p2p_mo_oth_count | >>本月点对点其他上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >点对点上行条数 | p2p_mo_sms_count | >点对点上行条数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 点对点上行条数 | p2p_mo_sms_count | 点对点上行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >彩信点对点下行条数 | p2p_mt_mms_count | >彩信点对点下行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >点对点下行条数 | p2p_mt_sms_count | >点对点下行条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月点对点短信 | p2p_sms_count | >本月点对点短信；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 年龄 | p_age_name | 年龄 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 个人所属政企客户ID | p_ent_customer_id | 个人所属政企客户ID | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 个人所属政企客户名称 | p_ent_customer_name | 个人所属政企客户名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 订单支付方式 | payment_method_code | 订单支付方式 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 支付时间 | payment_time | 支付时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_预付费实收应收差值（元） | payment_timing_dif_fee | 总账_预付费实收应收差值（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 预付费实收（元） | payment_timing_fee | 预付费实收（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 支付流水号 | payment_transaction_id | 支付流水号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 支付流水号(文件导入) | payment_transaction_id | 支付流水号(文件导入) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 服务号码靓号级别 | pn_level_id | 服务号码靓号级别 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 合同编号 | po_number_id | 合同编号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 端口数 | port_cnt_name | 端口数；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 摊分前费用 | pre_fee | 摊分前费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月预销用户数 | pre_termination_date | 月预销用户数；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 预销号时间 | pre_termination_date_time | 预销号时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_赠送冲减（元） | present_fee | 总账_赠送冲减（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第10月增值费（元） | previous_10_addval_fee | 最近第10月增值费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第10月数据费（元） | previous_10_data_fee | 最近第10月数据费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第10月计费时长 | previous_10_month_bill_dura_duration | 最近第10月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近10月收入(账单) | previous_10_month_bill_fee | 最近10月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近10月收入(账单)（元） | previous_10_month_bill_fee | 最近10月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第10月收入(账单)（元） | previous_10_month_bill_fee | 最近第10月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第10月收入(总账) | previous_10_month_fee | 最近第10月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第10月收入(总账)（元） | previous_10_month_fee | 最近第10月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第10月无线宽带时长 | previous_10_month_ix_dura_duration | 最近第10月无线宽带时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第10月无线宽带流量 | previous_10_month_ix_usage_mb | 最近第10月无线宽带流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第10月彩信条数 | previous_10_month_mms_count | 最近第10月彩信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第10月短信条数 | previous_10_month_sms_count | 最近第10月短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第10月通话次数 | previous_10_month_voice_call_count | 最近第10月通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第10月通话时长 | previous_10_month_voice_call_dura_usage_min | 最近第10月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第10月一次性费（元） | previous_10_once_fee | 最近第10月一次性费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第10月其它费（元） | previous_10_other_fee | 最近第10月其它费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第10月月租费（元） | previous_10_rent_fee | 最近第10月月租费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第10月通话费（元） | previous_10_voice_call_fee | 最近第10月通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第11月增值费（元） | previous_11_addval_fee | 最近第11月增值费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第11月数据费（元） | previous_11_data_fee | 最近第11月数据费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第11月计费时长 | previous_11_month_bill_dura_duration | 最近第11月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近11月收入(账单) | previous_11_month_bill_fee | 最近11月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近11月收入(账单)（元） | previous_11_month_bill_fee | 最近11月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第11月收入(账单)（元） | previous_11_month_bill_fee | 最近第11月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第11月收入(总账) | previous_11_month_fee | 最近第11月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第11月收入(总账)（元） | previous_11_month_fee | 最近第11月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第11月无线宽带时长 | previous_11_month_ix_dura_duration | 最近第11月无线宽带时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第11月无线宽带流量 | previous_11_month_ix_usage_mb | 最近第11月无线宽带流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第11月彩信条数 | previous_11_month_mms_count | 最近第11月彩信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第11月短信条数 | previous_11_month_sms_count | 最近第11月短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第11月通话次数 | previous_11_month_voice_call_count | 最近第11月通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第11月通话时长 | previous_11_month_voice_call_dura_usage_min | 最近第11月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第11月一次性费（元） | previous_11_once_fee | 最近第11月一次性费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第11月其它费（元） | previous_11_other_fee | 最近第11月其它费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第11月月租费（元） | previous_11_rent_fee | 最近第11月月租费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第11月通话费（元） | previous_11_voice_call_fee | 最近第11月通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第12月增值费（元） | previous_12_addval_fee | 最近第12月增值费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第12月数据费（元） | previous_12_data_fee | 最近第12月数据费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第12月计费时长 | previous_12_month_bill_dura_duration | 最近第12月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近12月收入(账单) | previous_12_month_bill_fee | 最近12月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近12月收入(账单)（元） | previous_12_month_bill_fee | 最近12月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第12月收入(账单)（元） | previous_12_month_bill_fee | 最近第12月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第12月收入(总账) | previous_12_month_fee | 最近第12月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第12月收入(总账)（元） | previous_12_month_fee | 最近第12月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第12月无线宽带时长 | previous_12_month_ix_dura_duration | 最近第12月无线宽带时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第12月无线宽带流量 | previous_12_month_ix_usage_mb | 最近第12月无线宽带流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第12月彩信条数 | previous_12_month_mms_count | 最近第12月彩信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第12月短信条数 | previous_12_month_sms_count | 最近第12月短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第12月通话次数 | previous_12_month_voice_call_count | 最近第12月通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第12月通话时长 | previous_12_month_voice_call_dura_usage_min | 最近第12月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第12月一次性费（元） | previous_12_once_fee | 最近第12月一次性费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第12月其它费（元） | previous_12_other_fee | 最近第12月其它费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第12月月租费（元） | previous_12_rent_fee | 最近第12月月租费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第12月通话费（元） | previous_12_voice_call_fee | 最近第12月通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第13月收入(账单)（元） | previous_13_month_bill_fee | 最近第13月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第13月收入(总账) | previous_13_month_fee | 最近第13月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第13月收入(总账)（元） | previous_13_month_fee | 最近第13月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第14月收入(账单)（元） | previous_14_month_bill_fee | 最近第14月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第14月收入(总账) | previous_14_month_fee | 最近第14月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第14月收入(总账)（元） | previous_14_month_fee | 最近第14月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第15月收入(账单)（元） | previous_15_month_bill_fee | 最近第15月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第15月收入(总账) | previous_15_month_fee | 最近第15月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第15月收入(总账)（元） | previous_15_month_fee | 最近第15月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第16月收入(账单)（元） | previous_16_month_bill_fee | 最近第16月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第16月收入(总账) | previous_16_month_fee | 最近第16月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第16月收入(总账)（元） | previous_16_month_fee | 最近第16月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第17月收入(账单)（元） | previous_17_month_bill_fee | 最近第17月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第17月收入(总账) | previous_17_month_fee | 最近第17月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第17月收入(总账)（元） | previous_17_month_fee | 最近第17月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第18月收入(账单)（元） | previous_18_month_bill_fee | 最近第18月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第18月收入(总账) | previous_18_month_fee | 最近第18月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第18月收入(总账)（元） | previous_18_month_fee | 最近第18月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月增值费（元） | previous_1_addval_fee | 最近第1月增值费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月数据费（元） | previous_1_data_fee | 最近第1月数据费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月计费时长 | previous_1_month_bill_dura_duration | 最近第1月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月收入(账单) | previous_1_month_billed_revenue_fee | 最近第1月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月收入(账单)（元） | previous_1_month_billed_revenue_fee | 最近第1月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月宽带速率 | previous_1_month_brd_line_count_rate | 上月宽带速率 | decimal(9,6) | customer_user | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月_组合产品细类 | previous_1_month_combo_product_id | 上月_组合产品细类 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月_组合产品实例 | previous_1_month_combo_product_inst_id | 上月_组合产品实例 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月_组合销售品细类 | previous_1_month_combo_product_offer_id | 上月_组合销售品细类 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第一个月3G流量 | previous_1_month_g3_flux_usage_mb | 最近第一个月3G流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月调账无效减收（元） | previous_1_month_invalid_adjust_fee | 上月调账无效减收（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月欠费不记收（元） | previous_1_month_invalid_post_bill_fee | 上月欠费不记收（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月4G终端且开卡（集团口径） | previous_1_month_is_4g_trml_flux_name | 上月4G终端且开卡（集团口径） | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月无线宽带时长 | previous_1_month_ix_dura_duration | 最近第1月无线宽带时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月无线宽带流量 | previous_1_month_ix_usage_mb | 最近第1月无线宽带流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月融合在网智慧产品数 | previous_1_month_kd_rh_iptv_count | 上月融合在网智慧产品数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月融合在网智慧产品数_x000D_ | previous_1_month_kd_rh_iptv_count | 上月融合在网智慧产品数_x000D_ | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月融合在网移动+副卡数 | previous_1_month_kd_rh_yd_active_subscriber_count | 上月融合在网移动+副卡数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月融合在网移动+副卡数_x000D_ | previous_1_month_kd_rh_yd_active_subscriber_count | 上月融合在网移动+副卡数_x000D_ | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月融合活跃移动+副卡数 | previous_1_month_kd_rh_yd_count | 上月融合活跃移动+副卡数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月融合活跃移动+副卡数_x000D_ | previous_1_month_kd_rh_yd_count | 上月融合活跃移动+副卡数_x000D_ | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 21年合约到期用户到期月 | previous_1_month_lease_exp_end_date | 21年合约到期用户到期月 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月彩信条数 | previous_1_month_mms_count | 最近第1月彩信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月新增积分 | previous_1_month_new_score_value_date | 本月新增积分；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月_单产品销售品细类 | previous_1_month_offer_id | 上月_单产品销售品细类 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月集中起租金额（元） | previous_1_month_once_rent_fee | 最近第1月集中起租金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月欠费不记收回收（元） | previous_1_month_oweback_fee | 上月欠费不记收回收（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月_销售品生效时间 | previous_1_month_primary_price_plan_eff_date_time | 上月_销售品生效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月_销售品失效时间 | previous_1_month_primary_price_plan_exp_date_time | 上月_销售品失效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月_销售品名称 | previous_1_month_primary_price_plan_id_name | 上月_销售品名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月_销售品订购时间 | previous_1_month_primary_price_plan_order_date_time | 上月_销售品订购时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月_单产品细类 | previous_1_month_primary_product_id | 上月_单产品细类 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月短信条数 | previous_1_month_sms_count | 最近第1月短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月实际北京端月租 | previous_1_month_sum_res_fee | 上月实际北京端月租 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月收入(总账) | previous_1_month_total_revenue_fee | 最近第1月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月收入(总账)（元） | previous_1_month_total_revenue_fee | 最近第1月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月用户状态 | previous_1_month_user_id_status | 上月用户状态 | varchar(64) | customer_user | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月通话次数 | previous_1_month_voice_call_count | 最近第1月通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月通话时长 | previous_1_month_voice_call_dura_usage_min | 最近第1月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本年累计税金 | previous_1_month_z_tax_agg_y_fee | 本年累计税金 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月一次性费（元） | previous_1_once_fee | 最近第1月一次性费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月其它费（元） | previous_1_other_fee | 最近第1月其它费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月月租费（元） | previous_1_rent_fee | 最近第1月月租费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第1月通话费（元） | previous_1_voice_call_fee | 最近第1月通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月增值费（元） | previous_2_addval_fee | 最近第2月增值费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月数据费（元） | previous_2_data_fee | 最近第2月数据费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月计费时长 | previous_2_month_bill_dura_duration | 最近第2月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月收入(账单) | previous_2_month_billed_revenue_fee | 最近第2月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月收入(账单)（元） | previous_2_month_billed_revenue_fee | 最近第2月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第二个月3G流量 | previous_2_month_g3_flux_usage_mb | 最近第二个月3G流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月无线宽带时长 | previous_2_month_ix_dura_duration | 最近第2月无线宽带时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月无线宽带流量 | previous_2_month_ix_usage_mb | 最近第2月无线宽带流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月彩信条数 | previous_2_month_mms_count | 最近第2月彩信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月短信条数 | previous_2_month_sms_count | 最近第2月短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月收入(总账) | previous_2_month_total_revenue_fee | 最近第2月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月收入(总账)（元） | previous_2_month_total_revenue_fee | 最近第2月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月通话次数 | previous_2_month_voice_call_count | 最近第2月通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月通话时长 | previous_2_month_voice_call_dura_usage_min | 最近第2月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月一次性费（元） | previous_2_once_fee | 最近第2月一次性费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月其它费（元） | previous_2_other_fee | 最近第2月其它费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月月租费（元） | previous_2_rent_fee | 最近第2月月租费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第2月通话费（元） | previous_2_voice_call_fee | 最近第2月通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月增值费（元） | previous_3_addval_fee | 最近第3月增值费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月数据费（元） | previous_3_data_fee | 最近第3月数据费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月计费时长 | previous_3_month_bill_dura_duration | 最近第3月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月收入(账单) | previous_3_month_billed_revenue_fee | 最近第3月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月收入(账单)（元） | previous_3_month_billed_revenue_fee | 最近第3月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第三个月3G流量 | previous_3_month_g3_flux_usage_mb | 最近第三个月3G流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月无线宽带时长 | previous_3_month_ix_dura_duration | 最近第3月无线宽带时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月无线宽带流量 | previous_3_month_ix_usage_mb | 最近第3月无线宽带流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月彩信条数 | previous_3_month_mms_count | 最近第3月彩信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月短信条数 | previous_3_month_sms_count | 最近第3月短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月收入(总账) | previous_3_month_total_revenue_fee | 最近第3月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月收入(总账)（元） | previous_3_month_total_revenue_fee | 最近第3月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月通话次数 | previous_3_month_voice_call_count | 最近第3月通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月通话时长 | previous_3_month_voice_call_dura_usage_min | 最近第3月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月一次性费（元） | previous_3_once_fee | 最近第3月一次性费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月其它费（元） | previous_3_other_fee | 最近第3月其它费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月月租费（元） | previous_3_rent_fee | 最近第3月月租费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第3月通话费（元） | previous_3_voice_call_fee | 最近第3月通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月增值费（元） | previous_4_addval_fee | 最近第4月增值费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月数据费（元） | previous_4_data_fee | 最近第4月数据费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月计费时长 | previous_4_month_bill_dura_duration | 最近第4月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月收入(账单) | previous_4_month_billed_revenue_fee | 最近第4月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月收入(账单)（元） | previous_4_month_billed_revenue_fee | 最近第4月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月无线宽带时长 | previous_4_month_ix_dura_duration | 最近第4月无线宽带时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月无线宽带流量 | previous_4_month_ix_usage_mb | 最近第4月无线宽带流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月彩信条数 | previous_4_month_mms_count | 最近第4月彩信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月短信条数 | previous_4_month_sms_count | 最近第4月短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月收入(总账) | previous_4_month_total_revenue_fee | 最近第4月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月收入(总账)（元） | previous_4_month_total_revenue_fee | 最近第4月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月通话次数 | previous_4_month_voice_call_count | 最近第4月通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月通话时长 | previous_4_month_voice_call_dura_usage_min | 最近第4月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月一次性费（元） | previous_4_once_fee | 最近第4月一次性费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月其它费（元） | previous_4_other_fee | 最近第4月其它费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月月租费（元） | previous_4_rent_fee | 最近第4月月租费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第4月通话费（元） | previous_4_voice_call_fee | 最近第4月通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月增值费（元） | previous_5_addval_fee | 最近第5月增值费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月数据费（元） | previous_5_data_fee | 最近第5月数据费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月计费时长 | previous_5_month_bill_dura_duration | 最近第5月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月收入(账单) | previous_5_month_billed_revenue_fee | 最近第5月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月收入(账单)（元） | previous_5_month_billed_revenue_fee | 最近第5月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月无线宽带时长 | previous_5_month_ix_dura_duration | 最近第5月无线宽带时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月无线宽带流量 | previous_5_month_ix_usage_mb | 最近第5月无线宽带流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月彩信条数 | previous_5_month_mms_count | 最近第5月彩信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月短信条数 | previous_5_month_sms_count | 最近第5月短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月收入(总账) | previous_5_month_total_revenue_fee | 最近第5月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月收入(总账)（元） | previous_5_month_total_revenue_fee | 最近第5月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月通话次数 | previous_5_month_voice_call_count | 最近第5月通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月通话时长 | previous_5_month_voice_call_dura_usage_min | 最近第5月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月一次性费（元） | previous_5_once_fee | 最近第5月一次性费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月其它费（元） | previous_5_other_fee | 最近第5月其它费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月月租费（元） | previous_5_rent_fee | 最近第5月月租费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第5月通话费（元） | previous_5_voice_call_fee | 最近第5月通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月增值费（元） | previous_6_addval_fee | 最近第6月增值费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月数据费（元） | previous_6_data_fee | 最近第6月数据费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月计费时长 | previous_6_month_bill_dura_duration | 最近第6月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月收入(账单) | previous_6_month_billed_revenue_fee | 最近第6月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月收入(账单)（元） | previous_6_month_billed_revenue_fee | 最近第6月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月无线宽带时长 | previous_6_month_ix_dura_duration | 最近第6月无线宽带时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月无线宽带流量 | previous_6_month_ix_usage_mb | 最近第6月无线宽带流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月彩信条数 | previous_6_month_mms_count | 最近第6月彩信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月短信条数 | previous_6_month_sms_count | 最近第6月短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月收入(总账) | previous_6_month_total_revenue_fee | 最近第6月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月收入(总账)（元） | previous_6_month_total_revenue_fee | 最近第6月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月通话次数 | previous_6_month_voice_call_count | 最近第6月通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月通话时长 | previous_6_month_voice_call_dura_usage_min | 最近第6月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月一次性费（元） | previous_6_once_fee | 最近第6月一次性费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月其它费（元） | previous_6_other_fee | 最近第6月其它费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月月租费（元） | previous_6_rent_fee | 最近第6月月租费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第6月通话费（元） | previous_6_voice_call_fee | 最近第6月通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第7月增值费（元） | previous_7_addval_fee | 最近第7月增值费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第7月数据费（元） | previous_7_data_fee | 最近第7月数据费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第7月计费时长 | previous_7_month_bill_dura_duration | 最近第7月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近7月收入(账单) | previous_7_month_bill_fee | 最近7月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近7月收入(账单)（元） | previous_7_month_bill_fee | 最近7月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第7月收入(账单)（元） | previous_7_month_bill_fee | 最近第7月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第7月收入(总账) | previous_7_month_fee | 最近第7月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第7月收入(总账)（元） | previous_7_month_fee | 最近第7月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第7月无线宽带时长 | previous_7_month_ix_dura_duration | 最近第7月无线宽带时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第7月无线宽带流量 | previous_7_month_ix_usage_mb | 最近第7月无线宽带流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第7月彩信条数 | previous_7_month_mms_count | 最近第7月彩信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第7月短信条数 | previous_7_month_sms_count | 最近第7月短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第7月通话次数 | previous_7_month_voice_call_count | 最近第7月通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第7月通话时长 | previous_7_month_voice_call_dura_usage_min | 最近第7月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第7月一次性费（元） | previous_7_once_fee | 最近第7月一次性费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第7月其它费（元） | previous_7_other_fee | 最近第7月其它费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第7月月租费（元） | previous_7_rent_fee | 最近第7月月租费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第7月通话费（元） | previous_7_voice_call_fee | 最近第7月通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第8月增值费（元） | previous_8_addval_fee | 最近第8月增值费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第8月数据费（元） | previous_8_data_fee | 最近第8月数据费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第8月计费时长 | previous_8_month_bill_dura_duration | 最近第8月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近8月收入(账单) | previous_8_month_bill_fee | 最近8月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近8月收入(账单)（元） | previous_8_month_bill_fee | 最近8月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第8月收入(账单)（元） | previous_8_month_bill_fee | 最近第8月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第8月收入(总账) | previous_8_month_fee | 最近第8月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第8月收入(总账)（元） | previous_8_month_fee | 最近第8月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第8月无线宽带时长 | previous_8_month_ix_dura_duration | 最近第8月无线宽带时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第8月无线宽带流量 | previous_8_month_ix_usage_mb | 最近第8月无线宽带流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第8月彩信条数 | previous_8_month_mms_count | 最近第8月彩信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第8月短信条数 | previous_8_month_sms_count | 最近第8月短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第8月通话次数 | previous_8_month_voice_call_count | 最近第8月通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第8月通话时长 | previous_8_month_voice_call_dura_usage_min | 最近第8月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第8月一次性费（元） | previous_8_once_fee | 最近第8月一次性费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第8月其它费（元） | previous_8_other_fee | 最近第8月其它费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第8月月租费（元） | previous_8_rent_fee | 最近第8月月租费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第8月通话费（元） | previous_8_voice_call_fee | 最近第8月通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第9月增值费（元） | previous_9_addval_fee | 最近第9月增值费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第9月数据费（元） | previous_9_data_fee | 最近第9月数据费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第9月计费时长 | previous_9_month_bill_dura_duration | 最近第9月计费时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近9月收入(账单) | previous_9_month_bill_fee | 最近9月收入(账单)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近9月收入(账单)（元） | previous_9_month_bill_fee | 最近9月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第9月收入(账单)（元） | previous_9_month_bill_fee | 最近第9月收入(账单)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第9月收入(总账) | previous_9_month_fee | 最近第9月收入(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第9月收入(总账)（元） | previous_9_month_fee | 最近第9月收入(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第9月无线宽带时长 | previous_9_month_ix_dura_duration | 最近第9月无线宽带时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第9月无线宽带流量 | previous_9_month_ix_usage_mb | 最近第9月无线宽带流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第9月彩信条数 | previous_9_month_mms_count | 最近第9月彩信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第9月短信条数 | previous_9_month_sms_count | 最近第9月短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第9月通话次数 | previous_9_month_voice_call_count | 最近第9月通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第9月通话时长 | previous_9_month_voice_call_dura_usage_min | 最近第9月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第9月一次性费（元） | previous_9_once_fee | 最近第9月一次性费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第9月其它费（元） | previous_9_other_fee | 最近第9月其它费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第9月月租费（元） | previous_9_rent_fee | 最近第9月月租费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近第9月通话费（元） | previous_9_voice_call_fee | 最近第9月通话费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近一次停机时间 | previous_block_date_time | 最近一次停机时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月_套餐积分 | previous_dinner_integral_name | 上月_套餐积分；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月套餐积分 | previous_dinner_integral_name | 上月套餐积分 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上次宽带续约渠道 | previous_kd_year_end_renew_channel_id | 上次宽带续约渠道 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上月_租机计划 | previous_lease_plan_id | 上月_租机计划 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近一次停机原因 | previous_oper_reason_name | 最近一次停机原因 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最后一次终端注册日期 | previous_reg_date | 最后一次终端注册日期；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月停机用户数 | previous_stop_date | 月停机用户数；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 最近停机时间 | previous_stop_date_time | 最近停机时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 销售品分类 | price_label_id_amount | 销售品分类 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主销售品档位 | price_level_fee | 主销售品档位 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 销售品档位（PPM） | price_level_fee | 销售品档位（PPM） | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 合约低消 | price_payment_least_amount | 合约低消 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 合约低消（PPM） | price_payment_least_amount | 合约低消（PPM） | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 组合套餐推荐名称 | price_plan_code_amount | 组合套餐推荐名称 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户分产品标签-跟踪 | price_plan_tag_amount | 用户分产品标签-跟踪 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户分产品标签-拍照 | price_plan_tag_init_amount | 用户分产品标签-拍照 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 组合套餐推荐类型 | price_plan_type | 组合套餐推荐类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 销售品生效时间 | primary_price_plan_eff_date_time | 销售品生效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 销售品失效时间 | primary_price_plan_exp_date_time | 销售品失效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_销售品名称(仅限移固融合关联查询) | primary_price_plan_name | 宽带_销售品名称(仅限移固融合关联查询) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 销售品名称 | primary_price_plan_name | 销售品名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主销售品订购时间 | primary_price_plan_order_date_time | 主销售品订购时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 销售品订购时间 | primary_price_plan_order_date_time | 销售品订购时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主销售品发展人 | primary_price_plan_staff_id | 主销售品发展人 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主产品细类 | primary_product_id | 主产品细类；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_主产品细类(仅限移固融合关联查询) | primary_product_id | 宽带_主产品细类(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主产品细类一级 | primary_product_level1_id | 主产品细类一级 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主产品细类二级 | primary_product_level2_id | 主产品细类二级；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 加装副卡概率 | prob_fk_rate | 加装副卡概率 | decimal(9,6) | customer_user | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 不限量流量包迁转概率 | prob_unlimit_flux_rate | 不限量流量包迁转概率 | decimal(9,6) | customer_user | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 不限量主套餐迁转概率 | prob_unlimit_primary_rate | 不限量主套餐迁转概率 | decimal(9,6) | customer_user | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 融合成员角色标识 | product_component_relationship_role_id | 融合成员角色标识 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 行业短信条数 | prof_sms_count | 行业短信条数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 国政通校验未通过 | profile_value_name | 国政通校验未通过；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 推广渠道 | promotion_channel_name | 推广渠道 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 收货省份 | provicecode_name | 收货省份 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户发展积分 | qdjf_dev_points_name | 用户发展积分 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月租费 | qdjf_monthly_fee | 月租费 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 离网扣罚积分 | qdjf_off_kf_points_name | 离网扣罚积分 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 赠金返费 | qdjf_refund_name | 赠金返费 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 赠金返费（剔除本金返费） | qdjf_refund_name | 赠金返费（剔除本金返费）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 价值贡献积分 | qdjf_value_points_name | 价值贡献积分 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月可用余额 | real_time_balance_amount | 本月可用余额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 单位用户实名制行业类型 | real_time_industry_id_type | 单位用户实名制行业类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 实名制时间 | realname_date_time | 实名制时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 收货人姓名 | receiver_name | 收货人姓名 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 收货人联系电话 | receiver_phone_name | 收货人联系电话 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 收货人联系电话(文件导入) | receiver_phone_name | 收货人联系电话(文件导入) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 计费收入（含增值税）(当月)（含赠费） | recharge_amount | 计费收入（含增值税）(当月)（含赠费） | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月充值金额 | recharge_amt_amount | 本月充值金额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月充值金额（元） | recharge_amt_amount | 本月充值金额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 计费收入（含增值税）(当月)（不含赠费） | recharge_noshui_amount | 计费收入（含增值税）(当月)（不含赠费） | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 计费收入（不含增值税）(当月)（不含赠费） | recharge_noshui_number_level23_amount | 计费收入（不含增值税）(当月)（不含赠费） | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 计费收入（不含增值税）(当月)（含赠费） | recharge_number_level23_amount | 计费收入（不含增值税）(当月)（含赠费） | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 订单推荐人 | recommend_user_name | 订单推荐人 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 红黑名单生效时间 | red_black_eff_date_time | 红黑名单生效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 红黑名单类型 | red_black_list_type | 红黑名单类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 翼支付红包金新资费减收费用 | redenvelope_fee | 翼支付红包金新资费减收费用 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 翼支付红包金老资费减收费用 | redenvelope_oldpp_fee | 翼支付红包金老资费减收费用 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_接入方式(仅限移固融合关联查询) | refund_rule_id | 宽带_接入方式(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 接入方式 | refund_rule_id | 接入方式 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 返还规则标识 | refund_rule_id | 返还规则标识 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 终端成本类型 | refunded_fee_left_type | 终端成本类型；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 剩余返款额（元） | refunded_left_fee | 剩余返款额（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月租费（元） | rent_fee | >本月租费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_历史递延加回的收入（元） | rent_hisdefer_fee | 总账_历史递延加回的收入（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_当月递延加回的收入（元） | rent_instdefer_fee | 总账_当月递延加回的收入（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_当月产生的递延收入（元） | rent_monthoccur_fee | 总账_当月产生的递延收入（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 潜在4升5终端换机用户 | reserv335_name | 潜在4升5终端换机用户 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 2020年存存量/存增量用户标识 | reserve_label_2020_id | 2020年存存量/存增量用户标识 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 2019年存存量/存增量用户标识 | reserve_label_id | 2019年存存量/存增量用户标识 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_本月实际应收(总账)(仅限移固融合关联查询) | revenue_fee | 宽带_本月实际应收(总账)(仅限移固融合关联查询)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月实际应收(总账) | revenue_fee | 本月实际应收(总账)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月实际应收(总账)（元） | revenue_fee | 本月实际应收(总账)（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带融合月总账收入 | rh_all_fee | 宽带融合月总账收入 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带融合壳子销售品(及单产品主销售品) | rh_comprod_price_plan_id | 宽带融合壳子销售品(及单产品主销售品) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带主用户编码 | rh_user_code | 宽带主用户编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_融合摊分后费用 | rhtf_after_fee | 总账_融合摊分后费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_融合摊分后费用（元） | rhtf_after_fee | 总账_融合摊分后费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_融合摊分前费用 | rhtf_before_fee | 总账_融合摊分前费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_融合摊分前费用（元） | rhtf_before_fee | 总账_融合摊分前费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_ 融合摊分差值（元） | rhtf_cz_name | 总账_ 融合摊分差值（元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_融合摊分差值 | rhtf_cz_name | 总账_融合摊分差值；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_融合摊分差值（元） | rhtf_cz_name | 总账_融合摊分差值（元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 2021年双节营销拍照清单-清单5-211升5G | rise_211_5g_customer_name | 2021年双节营销拍照清单-清单5-211升5G | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 2021年双节营销拍照清单-清单2-升211 | rise_211_customer_name | 2021年双节营销拍照清单-清单2-升211 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月漫游通话时长 | roam_usage_min | >本月漫游通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月漫游通话时长(秒) | roam_usage_min | >本月漫游通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 渠道视图-直销渠道人员细分 | sales_dsell_code | 渠道视图-直销渠道人员细分 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 销售品ID | sales_product_id | 销售品ID | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 销售品名称(电渠订单类) | sales_product_name | 销售品名称(电渠订单类) | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 通话时长第二多的基站的通话时长 | second_cell_voice_call_dura_usage_min | 通话时长第二多的基站的通话时长 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 通话时长第二多的基站的通话时长(秒) | second_cell_voice_call_dura_usage_min | 通话时长第二多的基站的通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带流量上网流量第二多的无线宽带流量 | second_ix_cell_flux_usage_mb | 无线宽带流量上网流量第二多的无线宽带流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带流量上网流量第二多的流量 | second_ix_cell_flux_usage_mb | 无线宽带流量上网流量第二多的流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带流量上网流量第二多的流量(KB) | second_ix_cell_flux_usage_mb | 无线宽带流量上网流量第二多的流量(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带流量第二多的基站 | second_ix_flux_cell_usage_mb | 无线宽带流量第二多的基站 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 流量第二多的基站 | second_ix_flux_cell_usage_mb | 流量第二多的基站 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带时长第二多的基站 | second_ix_msc_cellid_duration | 无线宽带时长第二多的基站 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 通话时长第二多的基站 | second_voice_call_msc_cellid_usage_min | 通话时长第二多的基站 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主卡号码 | service_number_id | 主卡号码 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主卡号码(全) | service_number_id | 主卡号码(全) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主卡号码(文件导入) | service_number_id | 主卡号码(文件导入) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 副卡号码 | service_number_id | 副卡号码 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 副卡号码(全) | service_number_id | 副卡号码(全) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 副卡号码(文件导入) | service_number_id | 副卡号码(文件导入) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 宽带_服务号码(仅限移固融合关联查询) | service_number_id | 宽带_服务号码(仅限移固融合关联查询) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 服务号码 | service_number_id | 服务号码 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 服务号码(全) | service_number_id | 服务号码(全) | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 号段 | service_number_seg_type | 号段 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇区局（摊分前） | settlement_allocation_building_bureau_id | 楼宇区局（摊分前） | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 楼宇区局细类（摊分前） | settlement_allocation_building_bureau_level2_id | 楼宇区局细类（摊分前） | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_摊分前后的差额（元） | share_dif_name | 总账_摊分前后的差额（元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月接收银行短信条数 | sms_mt_count | 本月接收银行短信条数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 缴费期累计欠费 | spec_agg_outstanding_fee | 缴费期累计欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 缴费期累计欠费（元） | spec_agg_outstanding_fee | 缴费期累计欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 缴费期本期欠费 | spec_cur_month_outstanding_fee | 缴费期本期欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 缴费期本期欠费（元） | spec_cur_month_outstanding_fee | 缴费期本期欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 缴费期本年欠费 | spec_cur_year_outstanding_fee | 缴费期本年欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 缴费期本年欠费（元） | spec_cur_year_outstanding_fee | 缴费期本年欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 缴费期累计有效欠费（元） | spec_valid_agg_fee | 缴费期累计有效欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 缴费期本期有效欠费（元） | spec_valid_outstanding_fee | 缴费期本期有效欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 缴费期本年有效欠费（元） | spec_valid_year_fee | 缴费期本年有效欠费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 停租时间 | stop_rent_date_time | 停租时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 子品牌 | sub_brand_id | 子品牌 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 话费补贴金额（PPM） | subsidy_callfee_amount | 话费补贴金额（PPM）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 终端补贴金额（PPM） | subsidy_terminal_amount | 终端补贴金额（PPM）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 补贴类型 | subsidy_type | 补贴类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 补贴类型（PPM） | subsidy_type | 补贴类型（PPM） | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_信用度减收（元） | subtract_fee | 总账_信用度减收（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 终端补贴 不含税 冲减 | subtract_n_tax_fee | 终端补贴 不含税 冲减；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 终端补贴不含税冲减 | subtract_n_tax_fee | 终端补贴不含税冲减；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_翼支付红包返费减收(元) | subtract_rebate_amt_name | 总账_翼支付红包返费减收(元)；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_翼支付红包返费减收（元） | subtract_rebate_amt_name | 总账_翼支付红包返费减收（元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 翼支付一次性返费递延冲减 | subtract_rebate_ycx_name | 翼支付一次性返费递延冲减；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 翼支付一次性返费递延冲减(元) | subtract_rebate_ycx_name | 翼支付一次性返费递延冲减(元)；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 翼支付一次性返费递延冲减（元） | subtract_rebate_ycx_name | 翼支付一次性返费递延冲减（元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 终端补贴税冲减 | subtract_tax_fee | 终端补贴税冲减；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 当月实际北京端月租 | sum_res_fee | 当月实际北京端月租 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 月租净增 | sum_res_jingzeng_fee | 月租净增 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 税金 | tax_fee | 税金；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 税务客户名称 | taxpayer_name | 税务客户名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 专线摊出（元） | tc_fee | 专线摊出（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_专线摊出（元） | tc_fee | 总账_专线摊出（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 套餐外收入 | tc_out_fee | 套餐外收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 套餐外收入(单位：分) | tc_out_fee | 套餐外收入(单位：分) | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 套餐内摊分流量收入 | tc_tf_fee_usage_mb | 套餐内摊分流量收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 套餐内摊分流量收入(单位：分) | tc_tf_fee_usage_mb | 套餐内摊分流量收入(单位：分) | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 离网概率 | td_off_net_rate | 离网概率 | decimal(9,6) | customer_user | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 合约到期续约概率 | td_resume_lease_rate | 合约到期续约概率 | decimal(9,6) | customer_user | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | IMEI号 | terminal_imei_count | IMEI号 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | UIM卡类型 | terminal_model_type | UIM卡类型；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 离网时间 | termination_time | 离网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | customer_user | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 终端使用参考时长 | ternl_user_months_duration | 终端使用参考时长 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 测试电路标识 | test_circuit_tag_id | 测试电路标识 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 通话时长第三多的基站的通话时长 | third_cell_voice_call_dura_usage_min | 通话时长第三多的基站的通话时长 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 通话时长第三多的基站的通话时长(秒) | third_cell_voice_call_dura_usage_min | 通话时长第三多的基站的通话时长(秒)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带流量上网流量第三多的无线宽带流量 | third_ix_cell_flux_usage_mb | 无线宽带流量上网流量第三多的无线宽带流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带流量上网流量第三多的流量 | third_ix_cell_flux_usage_mb | 无线宽带流量上网流量第三多的流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带流量上网流量第三多的流量(KB) | third_ix_cell_flux_usage_mb | 无线宽带流量上网流量第三多的流量(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 无线宽带流量第三多的基站 | third_ix_flux_cell_usage_mb | 无线宽带流量第三多的基站 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 通话时长第三多的基站 | third_voice_call_msc_cellid_usage_min | 通话时长第三多的基站 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 天翼视讯定向流量 | tianyi_usage_mb | 天翼视讯定向流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总余额 | total_balance_amount | 总余额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月实收总费用 | total_wrt_fee | 本月实收总费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月实收总费用(元） | total_wrt_fee | 本月实收总费用(元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月销账总费用（元） | total_wrt_fee | 本月销账总费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 专线摊入（元） | tr_fee | 专线摊入（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_专线摊入（元） | tr_fee | 总账_专线摊入（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 调账（2010年6月底之前使用）（元） | tz_fee | 调账（2010年6月底之前使用）（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 计费余额帐本类型ID | university_id_type | 计费余额帐本类型ID | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 所属高校 | university_name | 所属高校 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 计费余额帐本名称 | university_name_amount | 计费余额帐本名称 | decimal(18,2) | customer_user | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 产生5G话单天数 | used_5gflux_days_count | 产生5G话单天数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月3G活跃用户数(流量大于0) | user_3g_type | 本月3G活跃用户数(流量大于0)；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户主要联系人姓名 | user_contact_name | 用户主要联系人姓名 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户主要联系人电话 | user_contact_phone_name | 用户主要联系人电话 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户信用度 | user_credit_value_name | 用户信用度；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 当前状态开始时间 | user_date_status | 当前状态开始时间；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 客户群类别 | user_group_kind_id_type | 客户群类别 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户编号 | user_id | 用户编号 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户编码 | user_id | 用户编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户编码(文件导入) | user_id | 用户编码(文件导入) | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 统计用户数 | user_id | 统计用户数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 是 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 统计用户数(去重) | user_id | 统计用户数(去重) | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 是 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户状态 | user_id_status | 用户状态 | varchar(64) | customer_user | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户建档员工六级部门 | user_in_department_id | 用户建档员工六级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户建档员工二级部门 | user_in_department_level2_id | 用户建档员工二级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户建档员工三级部门 | user_in_department_level3_id | 用户建档员工三级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户建档员工四级部门 | user_in_department_level4_id | 用户建档员工四级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户建档员工 | user_in_staff_id | 用户建档员工 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 权益平台新用户等级标准（主套餐档位（计费）） | user_levl_fee | 权益平台新用户等级标准（主套餐档位（计费）） | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户在网时长 | user_online_dura_duration | 用户在网时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户在网时长（月） | user_online_dura_duration | 用户在网时长（月） | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户停机时长 | user_stop_dura_duration | 用户停机时长；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 累计有效欠费 | valid_agg_outstanding_fee | 累计有效欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本期有效欠费 | valid_cur_month_outstanding_fee | 本期有效欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本年有效欠费 | valid_cur_year_outstanding_fee | 本年有效欠费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 圈集团客户经理六级部门 | vir_grp_customer_manager_department_id | 圈集团客户经理六级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 圈集团客户经理二级部门 | vir_grp_customer_manager_department_level2_id | 圈集团客户经理二级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 圈集团客户经理三级部门 | vir_grp_customer_manager_department_level3_id | 圈集团客户经理三级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 圈集团客户经理四级部门 | vir_grp_customer_manager_department_level4_id | 圈集团客户经理四级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 圈集团客户经理五级部门 | vir_grp_customer_manager_department_level5_id | 圈集团客户经理五级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 圈集团客户经理 | vir_grp_customer_manager_id | 圈集团客户经理 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 圈集团客户名称 | vir_grp_customer_name | 圈集团客户名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 圈集团日期 | vir_grp_date | 圈集团日期；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 访问APP个数 | visit_application_count | 访问APP个数 | integer | customer_user | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | volte高清视频时长（秒） | voice_call_dura_video_volte_duration | volte高清视频时长（秒）；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | volte高清语音时长（秒） | voice_call_dura_voice_volte_duration | volte高清语音时长（秒）；由源表达式进行空值处理、截取或单位换算后形成 | integer | customer_user | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >本月语音费（元） | voice_call_fee | >本月语音费（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 本月通话时长 | voice_call_usage_min | 本月通话时长；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按分钟字段规范命名为 xxx_usage_min | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 累计wifi活跃月份 | wlan_active_month_date | 累计wifi活跃月份；由源表达式进行空值处理、截取或单位换算后形成 | date | customer_user | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 专线外省摊出（元） | wstc_fee | 专线外省摊出（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 专线外省摊入（元） | wstr_fee | 专线外省摊入（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 维挽服务经理二级部门 | ww_svc_manager_department_level2_id | 维挽服务经理二级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 维挽服务经理三级部门 | ww_svc_manager_department_level3_id | 维挽服务经理三级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 维挽服务经理四级部门 | ww_svc_manager_department_level4_id | 维挽服务经理四级部门 | varchar(64) | customer_user | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 用户本月漫游情况 | yfxt_roam_type | 用户本月漫游情况 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 2021年双节营销拍照清单-清单1-有机无套 | youjiwutao_user_name | 2021年双节营销拍照清单-清单1-有机无套 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 2021年双节营销拍照清单-清单3-有套无机 | youtaowuji_user_name | 2021年双节营销拍照清单-清单3-有套无机 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 年付销售品名称 | ypay_primary_price_plan_id_name | 年付销售品名称 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >C网_应用 | z_c_addval_fee | >C网_应用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >>爱音乐 | z_c_music_fee | >>爱音乐；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >C网_语音 | z_c_voice_call_fee | >C网_语音；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | ICT服务收入 | z_ict_serv_fee | ICT服务收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | IDC收入 | z_idc_fee | IDC收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 互联网应用收入 | z_internet_application_fee | 互联网应用收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 需要计税的费用 | z_need_tax_fee | 需要计税的费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 上网流量收入 | z_net_flux_fee_usage_mb | 上网流量收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | customer_user | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >固网宽带使用费 | z_pstn_ad_fee | >固网宽带使用费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >固网宽带月租 | z_pstn_ad_rent_fee | >固网宽带月租；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >固网增值 | z_pstn_addval_fee | >固网增值；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >固网专线月租 | z_pstn_ddn_rent_fee | >固网专线月租；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >固网一次性费用 | z_pstn_once_fee | >固网一次性费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >固网代收费 | z_pstn_proxy_fee | >固网代收费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >固网语音月租 | z_pstn_rent_fee | >固网语音月租；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | >固网语音使用费 | z_pstn_voice_call_fee | >固网语音使用费；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_终端直降减收（不含税） | zdzj_n_tax_fee | 总账_终端直降减收（不含税）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_终端直降减收（税） | zdzj_tax_fee | 总账_终端直降减收（税）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主转副类型 | zf_card_change_id_type | 主转副类型 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_主副卡摊分前费用(元) | zfk_tf_before_fee | 总账_主副卡摊分前费用(元)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_主副卡摊分前费用（元） | zfk_tf_before_fee | 总账_主副卡摊分前费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 总账_主副卡摊分差值（元） | zfk_tf_cz_name | 总账_主副卡摊分差值（元）；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | customer_user | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 合同编码 | zhetno_code | 合同编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 智慧宽带调试收入（不含税） | zhkdts_n_tax_fee | 智慧宽带调试收入（不含税） | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 智慧宽带调试收入（含税） | zhkdts_tax_fee | 智慧宽带调试收入（含税） | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主副卡异常用户标签 | zhufuka_comprod_abnm_type | 主副卡异常用户标签 | varchar(64) | customer_user | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 项目编码 | zictno_code | 项目编码 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 主卡用户编码 | zk_user_code | 主卡用户编码；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | customer_user | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 赠送费用（元） | zs_fee | 赠送费用（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 专线客户费用 | zx_kh_fee | 专线客户费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新即席查询月视图_3.0 | DA.a_u_360_all_view_m | 专线摊分费用 | zx_tf_fee | 专线摊分费用；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | customer_user | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 订单证件类型 | card_code_type | 订单证件类型 | varchar(64) | digital_channel_order | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 收货地市 | citycode_name | 收货地市 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 收货区县 | countycode_count | 收货区县 | integer | digital_channel_order | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 入网人证件类型 | customer_card_type | 入网人证件类型 | varchar(64) | digital_channel_order | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 入网人号码 | customer_phone_id | 入网人号码 | varchar(64) | digital_channel_order | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 入网人号码(文件导入) | customer_phone_id | 入网人号码(文件导入) | varchar(64) | digital_channel_order | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 入网人姓名 | customername_name | 入网人姓名 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 数据账期 | data_time | 数据账期 | datetime | digital_channel_order | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 订单配送方式 | delivery_method_code | 订单配送方式 | varchar(64) | digital_channel_order | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 配送时间 | delivery_time | 配送时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | digital_channel_order | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 订单编码 | digital_order_code | 订单编码 | varchar(64) | digital_channel_order | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 订单编码(文件导入) | digital_order_code | 订单编码(文件导入) | varchar(64) | digital_channel_order | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 订单状态 | digital_order_status | 订单状态 | varchar(64) | digital_channel_order | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 订单类型 | digital_order_type | 订单类型 | varchar(64) | digital_channel_order | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 订单AB类型 | order_abtype_type | 订单AB类型 | varchar(64) | digital_channel_order | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 订单创建时间 | order_created_time | 订单创建时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | digital_channel_order | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 订单渠道 | order_data_channel_code | 订单渠道 | varchar(64) | digital_channel_order | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 订单金额(实际支付金额) | order_paid_amount | 订单金额(实际支付金额) | decimal(18,2) | digital_channel_order | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 订单金额(实际支付金额)_x000D_ | order_paid_amount | 订单金额(实际支付金额)_x000D_ | decimal(18,2) | digital_channel_order | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 订单来源 | order_source_code | 订单来源 | varchar(64) | digital_channel_order | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 订单支付方式 | payment_method_code | 订单支付方式 | varchar(64) | digital_channel_order | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 支付时间 | payment_time | 支付时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | digital_channel_order | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 支付流水号 | payment_transaction_id | 支付流水号 | varchar(64) | digital_channel_order | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 支付流水号(文件导入) | payment_transaction_id | 支付流水号(文件导入) | varchar(64) | digital_channel_order | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 推广渠道 | promotion_channel_name | 推广渠道 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 收货省份 | provicecode_name | 收货省份 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 收货人姓名 | receiver_name | 收货人姓名 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 收货人联系电话 | receiver_phone_name | 收货人联系电话 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 收货人联系电话(文件导入) | receiver_phone_name | 收货人联系电话(文件导入) | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 订单推荐人 | recommend_user_name | 订单推荐人 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 销售品ID | sales_product_id | 销售品ID | varchar(64) | digital_channel_order | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 销售品名称 | sales_product_name | 销售品名称 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 用户编码 | user_id | 用户编码 | varchar(64) | digital_channel_order | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 用户编码(文件导入) | user_id | 用户编码(文件导入) | varchar(64) | digital_channel_order | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 电渠订单即席日视图 | da.a_channel_order_jixi_d | 统计用户数_x000D_ | user_id | 统计用户数_x000D_ | integer | digital_channel_order | 按次数字段规范命名为 xxx_count | 否 | 是 | 是 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 订单证件类型 | card_code_type | 订单证件类型 | varchar(64) | digital_channel_order | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 收货地市 | citycode_name | 收货地市 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 收货区县 | countycode_count | 收货区县 | integer | digital_channel_order | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 入网人证件类型 | customer_card_type | 入网人证件类型 | varchar(64) | digital_channel_order | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 入网人号码 | customer_phone_id | 入网人号码 | varchar(64) | digital_channel_order | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 入网人号码(文件导入) | customer_phone_id | 入网人号码(文件导入) | varchar(64) | digital_channel_order | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 入网人姓名 | customername_name | 入网人姓名 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 数据账期 | data_time | 数据账期 | datetime | digital_channel_order | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 订单配送方式 | delivery_method_code | 订单配送方式 | varchar(64) | digital_channel_order | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 配送时间 | delivery_time | 配送时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | digital_channel_order | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 订单编码 | digital_order_code | 订单编码 | varchar(64) | digital_channel_order | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 订单编码(文件导入) | digital_order_code | 订单编码(文件导入) | varchar(64) | digital_channel_order | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 订单状态 | digital_order_status | 订单状态 | varchar(64) | digital_channel_order | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 订单类型 | digital_order_type | 订单类型 | varchar(64) | digital_channel_order | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 收货人姓名 | end_x000d_name | 收货人姓名 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 订单AB类型 | order_abtype_type | 订单AB类型 | varchar(64) | digital_channel_order | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 订单创建时间 | order_created_time | 订单创建时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | digital_channel_order | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 订单渠道 | order_data_channel_code | 订单渠道 | varchar(64) | digital_channel_order | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 订单金额(实际支付金额) | order_paid_amount | 订单金额(实际支付金额) | decimal(18,2) | digital_channel_order | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 订单来源 | order_source_code | 订单来源 | varchar(64) | digital_channel_order | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 订单支付方式 | payment_method_code | 订单支付方式 | varchar(64) | digital_channel_order | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 支付时间 | payment_time | 支付时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | digital_channel_order | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 支付流水号 | payment_transaction_id | 支付流水号 | varchar(64) | digital_channel_order | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 支付流水号(文件导入) | payment_transaction_id | 支付流水号(文件导入) | varchar(64) | digital_channel_order | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 推广渠道 | promotion_channel_name | 推广渠道 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 收货省份 | provicecode_name | 收货省份 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 收货人姓名 | receiver_name | 收货人姓名 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 收货人联系电话 | receiver_phone_name | 收货人联系电话 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 收货人联系电话(文件导入) | receiver_phone_name | 收货人联系电话(文件导入) | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 订单推荐人 | recommend_user_name | 订单推荐人 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 销售品ID | sales_product_id | 销售品ID | varchar(64) | digital_channel_order | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 销售品名称 | sales_product_name | 销售品名称 | varchar(255) | digital_channel_order | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 用户编码 | user_id | 用户编码 | varchar(64) | digital_channel_order | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 用户编码(文件导入) | user_id | 用户编码(文件导入) | varchar(64) | digital_channel_order | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 电渠订单即席月视图 | da.a_channel_order_jixi_m | 统计用户数 | user_id | 统计用户数 | integer | digital_channel_order | 按次数字段规范命名为 xxx_count | 否 | 是 | 是 | 否 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 应用一级 | application_level1_type | 应用一级 | varchar(64) | network_application_usage | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 应用二级 | application_level2_type | 应用二级 | varchar(64) | network_application_usage | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 应用三级 | application_level3_type | 应用三级 | varchar(64) | network_application_usage | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 流量 | application_usage_mb | 流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | network_application_usage | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 流量(KB) | application_usage_mb | 流量(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | network_application_usage | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 分类 | application_visit_type | 分类 | varchar(64) | network_application_usage | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 类别 | application_visit_type | 类别 | varchar(64) | network_application_usage | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 数据日期 | data_time | 数据日期 | datetime | network_application_usage | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 维挽拍照标识 | is_ww_photo | 维挽拍照标识 | boolean | network_application_usage | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 搜索关键字 | keyword_name | 搜索关键字 | varchar(255) | network_application_usage | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 累计到本日流量 | month_to_date_application_usage_mb | 累计到本日流量；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | network_application_usage | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 累计到本日流量(KB) | month_to_date_application_usage_mb | 累计到本日流量(KB)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | network_application_usage | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 累计到本日点击次数 | month_to_date_page_view_count | 累计到本日点击次数 | integer | network_application_usage | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 一级分类 | name_level1_type | 一级分类 | varchar(64) | network_application_usage | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 二级分类 | name_level2_type | 二级分类 | varchar(64) | network_application_usage | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 三级分类 | name_level3_type | 三级分类 | varchar(64) | network_application_usage | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 四级分类 | name_level4_type | 四级分类 | varchar(64) | network_application_usage | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 五级分类 | name_level5_type | 五级分类 | varchar(64) | network_application_usage | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 六级分类 | name_level6_type | 六级分类 | varchar(64) | network_application_usage | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 点击次数 | page_view_count | 点击次数 | integer | network_application_usage | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 服务号码 | phone_id | 服务号码 | varchar(64) | network_application_usage | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 用户ID | user_id | 用户ID | varchar(64) | network_application_usage | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 用户编号 | user_id | 用户编号 | varchar(64) | network_application_usage | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| DPI即席查询_3.0 | dm.m_E_DPI_CDR_JT_D | 统计用户数 | user_id | 统计用户数 | integer | network_application_usage | 按次数字段规范命名为 xxx_count | 否 | 是 | 是 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 客户订单受理部门 | accept_channel_name | 客户订单受理部门 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 订单操作日期 | accept_date | 订单操作日期；由源表达式进行空值处理、截取或单位换算后形成 | date | order_channel | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 客户订单受理时间 | accept_date_time | 客户订单受理时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | order_channel | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 客户订单受理员工 | accept_staff_name | 客户订单受理员工 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 接入号码 | access_number_count | 接入号码 | integer | order_channel | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 接入号码(文件导入) | access_number_count | 接入号码(文件导入) | integer | order_channel | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 产品类型 | account_id | 产品类型 | varchar(64) | order_channel | 按类型字段规范命名为 xxx_type | 是 | 否 | 是 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 计费账户编码 | account_id | 计费账户编码 | varchar(64) | order_channel | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 账户经理所属二级部门 | account_manager_department_level2_name | 账户经理所属二级部门 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 账户经理所属三级部门 | account_manager_department_level3_name | 账户经理所属三级部门 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 账户经理所属四级部门 | account_manager_department_level4_name | 账户经理所属四级部门 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 账户经理所属五级部门 | account_manager_department_level5_name | 账户经理所属五级部门 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 帐户经理所属六级部门 | account_manager_department_name | 帐户经理所属六级部门 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 帐户经理 | account_manager_id | 帐户经理 | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 发展六级部门 | acquisition_department_id | 发展六级部门 | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 用户发展二级部门 | acquisition_department_level2_id | 用户发展二级部门 | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 用户发展三级部门 | acquisition_department_level3_id | 用户发展三级部门 | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 用户发展四级部门 | acquisition_department_level4_id | 用户发展四级部门 | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 用户发展五级部门 | acquisition_department_level5_id | 用户发展五级部门 | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 业务发展人 | acquisition_staff_id | 业务发展人 | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 产品类型 | apply_obj_spec_name_type | 产品类型 | varchar(64) | order_channel | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 北京端一次性费用 | bj_one_fee_time | 北京端一次性费用 | datetime | order_channel | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 本端楼宇编码 | building_code | 本端楼宇编码 | varchar(64) | order_channel | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 楼宇等级 | building_levels_name | 楼宇等级 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 本端楼宇名称 | building_name | 本端楼宇名称 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 竣工日期 | completion_date | 竣工日期；由源表达式进行空值处理、截取或单位换算后形成 | date | order_channel | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 集团电路代号 | condition1_name | 集团电路代号 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 竣工操作日期 | condition2_date | 竣工操作日期；由源表达式进行空值处理、截取或单位换算后形成 | date | order_channel | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 需求单编号 | condition6_id | 需求单编号 | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 订单操作人 | create_staff_name | 订单操作人 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 客户经理 | customer_manager_id | 客户经理 | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 客户名称 | customer_name | 客户名称 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 客户订单编码 | customer_order_code | 客户订单编码 | varchar(64) | order_channel | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 客户订单状态时间 | customer_order_date_status | 客户订单状态时间；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | order_channel | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 订单数 | customer_order_id | 订单数 | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 购物车流水号 | customer_order_id | 购物车流水号 | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 客户订单状态 | customer_order_status | 客户订单状态 | varchar(64) | order_channel | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 客户订单类型 | customer_order_type | 客户订单类型 | varchar(64) | order_channel | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 账期 | data_time | 账期 | datetime | order_channel | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 关联代理商 | dev_staff_name | 关联代理商 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 集团订单号 | grp_order_number_id | 集团订单号 | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 集团ICT项目号 | ict_items_number_name | 集团ICT项目号 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 集团ICT合同号 | ict_po_number_name | 集团ICT合同号 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 是否拍照楼宇 | is_if_snap | 是否拍照楼宇 | boolean | order_channel | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 集团流水号是否为空 | is_jt_serial_number | 集团流水号是否为空 | boolean | order_channel | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 是否集团订单 | is_order_channel | 是否集团订单 | boolean | order_channel | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 集团流水号 | jt_serial_number_id | 集团流水号 | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 当月月租净增 | monthly_rent_add_fee | 当月月租净增 | decimal(18,2) | order_channel | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 当月月租 | monthly_rent_fee | 当月月租 | decimal(18,2) | order_channel | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 资费状态 | offer_status | 资费状态 | varchar(64) | order_channel | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 2.0在途标签 | on_the_way_label_20_name | 2.0在途标签 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 一次性费用 | one_fee_time | 一次性费用 | datetime | order_channel | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 速率 | ord_brd_line_rate | 速率 | decimal(9,6) | order_channel | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 订单项开通时间 | order_item_activation_date_time | 订单项开通时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | order_channel | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 订单项状态 | order_item_code_status | 订单项状态 | varchar(64) | order_channel | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 订单项状态时间 | order_item_date_status | 订单项状态时间；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | order_channel | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 订单项编码 | order_item_number_code | 订单项编码 | varchar(64) | order_channel | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 订单项的操作类型 | order_item_oper_type | 订单项的操作类型 | varchar(64) | order_channel | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 订单备注 | order_mark_name | 订单备注 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 合同编号 | po_number_id | 合同编号 | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 销售品规格ID(对应经分的资费) | primary_price_plan_id | 销售品规格ID(对应经分的资费) | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 主产品细类 | primary_product_id | 主产品细类 | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 主产品细类二级 | primary_product_level2_id | 主产品细类二级 | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 要求服务日期 | service_date | 要求服务日期；由源表达式进行空值处理、截取或单位换算后形成 | date | order_channel | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 业务处理类型 | service_offer_id_type | 业务处理类型 | varchar(64) | order_channel | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 服务提供名称 | service_offer_nameaaa_name | 服务提供名称 | varchar(255) | order_channel | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 产品实例ID（用户ID） | service_product_inst_id | 产品实例ID（用户ID） | varchar(64) | order_channel | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 起租操作日期 | start_date | 起租操作日期；由源表达式进行空值处理、截取或单位换算后形成 | date | order_channel | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新购物车即席日视图_3.0 | DA.A_E_CUST_ORDER_D | 起租日期 | start_date | 起租日期；由源表达式进行空值处理、截取或单位换算后形成 | date | order_channel | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户发展六级部门 | acquisition_department_id | 用户发展六级部门 | varchar(64) | payment_recharge | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户发展二级部门 | acquisition_department_level2_id | 用户发展二级部门 | varchar(64) | payment_recharge | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户发展三级部门 | acquisition_department_level3_id | 用户发展三级部门 | varchar(64) | payment_recharge | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户发展四级部门 | acquisition_department_level4_id | 用户发展四级部门 | varchar(64) | payment_recharge | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户发展五级部门 | acquisition_department_level5_id | 用户发展五级部门 | varchar(64) | payment_recharge | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户发展员工 | acquisition_staff_id | 用户发展员工 | varchar(64) | payment_recharge | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 入网时间 | activation_time | 入网时间 | datetime | payment_recharge | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 本月累计基本计费时长 | base_duration | 本月累计基本计费时长 | integer | payment_recharge | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 本月累计基本计费时长（秒） | base_duration | 本月累计基本计费时长（秒）；由源表达式进行空值处理、截取或单位换算后形成 | integer | payment_recharge | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 客户名称 | customer_name | 客户名称 | varchar(255) | payment_recharge | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 客户名称(全) | customer_name | 客户名称(全) | varchar(255) | payment_recharge | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 数据日期 | data_time | 数据日期 | datetime | payment_recharge | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 首次激活时间 | first_active_date_time | 首次激活时间 | datetime | payment_recharge | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 标志_当日用户在网 | is_active_subscriber | 标志_当日用户在网 | boolean | payment_recharge | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 本月是否活跃 | is_active_usage | 本月是否活跃 | boolean | payment_recharge | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 标志_预付后付 | is_prepaid_subscriber | 标志_预付后付 | boolean | payment_recharge | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 标志_移动固网 | is_service_network | 标志_移动固网 | boolean | payment_recharge | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 租机计划 | lease_plan_id | 租机计划 | varchar(64) | payment_recharge | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 租机计划生效时间 | lease_price_plan_eff_date_time | 租机计划生效时间 | datetime | payment_recharge | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 租机计划失效时间 | lease_price_plan_exp_date_time | 租机计划失效时间 | datetime | payment_recharge | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 租机计划订购时间 | lease_price_plan_order_date_time | 租机计划订购时间 | datetime | payment_recharge | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 本月累计无线宽带总流量 | monthly_mobile_usage_mb | 本月累计无线宽带总流量 | decimal(18,3) | payment_recharge | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 本月累计无线宽带总流量（KB） | monthly_mobile_usage_mb | 本月累计无线宽带总流量（KB）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | payment_recharge | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 本月累计短信条数 | monthly_sms_count | 本月累计短信条数；由源表达式进行空值处理、截取或单位换算后形成 | integer | payment_recharge | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 本月累计通话次数 | monthly_voice_call_count | 本月累计通话次数；由源表达式进行空值处理、截取或单位换算后形成 | integer | payment_recharge | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 单产品销售品细类 | offer_id | 单产品销售品细类 | varchar(64) | payment_recharge | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户最近一个月账单收入 | previous_1_bill_fee | 用户最近一个月账单收入 | decimal(18,2) | payment_recharge | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户最近一个月账单收入（元） | previous_1_bill_fee | 用户最近一个月账单收入（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | payment_recharge | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户最近两个月账单收入 | previous_2_bill_fee | 用户最近两个月账单收入 | decimal(18,2) | payment_recharge | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户最近两个月账单收入（元） | previous_2_bill_fee | 用户最近两个月账单收入（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | payment_recharge | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户最近三个月账单收入 | previous_3_bill_fee | 用户最近三个月账单收入 | decimal(18,2) | payment_recharge | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户最近三个月账单收入（元） | previous_3_bill_fee | 用户最近三个月账单收入（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | payment_recharge | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户最近四个月账单收入 | previous_4_bill_fee | 用户最近四个月账单收入 | decimal(18,2) | payment_recharge | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户最近四个月账单收入（元） | previous_4_bill_fee | 用户最近四个月账单收入（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | payment_recharge | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户最近五个月账单收入 | previous_5_bill_fee | 用户最近五个月账单收入 | decimal(18,2) | payment_recharge | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户最近五个月账单收入（元） | previous_5_bill_fee | 用户最近五个月账单收入（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | payment_recharge | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户最近六个月账单收入 | previous_6_bill_fee | 用户最近六个月账单收入 | decimal(18,2) | payment_recharge | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户最近六个月账单收入（元） | previous_6_bill_fee | 用户最近六个月账单收入（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | payment_recharge | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 最近停机时间 | previous_stop_date_time | 最近停机时间 | datetime | payment_recharge | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 资费生效时间 | primary_price_plan_eff_date_time | 资费生效时间 | datetime | payment_recharge | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 资费失效时间 | primary_price_plan_exp_date_time | 资费失效时间 | datetime | payment_recharge | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 资费名称 | primary_price_plan_name | 资费名称 | varchar(255) | payment_recharge | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 资费订购时间 | primary_price_plan_order_date_time | 资费订购时间 | datetime | payment_recharge | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 主产品细类 | primary_product_id | 主产品细类 | varchar(64) | payment_recharge | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 主产品细类一级 | primary_product_level1_id | 主产品细类一级 | varchar(64) | payment_recharge | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 主产品细类二级 | primary_product_level2_id | 主产品细类二级 | varchar(64) | payment_recharge | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 充值金额 | recharge_amount | 充值金额 | decimal(18,2) | payment_recharge | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 充值金额(元) | recharge_amount | 充值金额(元) | decimal(18,2) | payment_recharge | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 充值金额（元） | recharge_amount | 充值金额（元） | decimal(18,2) | payment_recharge | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 充值日期 | recharge_date | 充值日期 | date | payment_recharge | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 充值日期（截止前日90天内） | recharge_date | 充值日期（截止前日90天内） | date | payment_recharge | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 充值方式 | recharge_method_type | 充值方式 | varchar(64) | payment_recharge | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 服务号码 | recharge_service_number_id | 服务号码 | varchar(64) | payment_recharge | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 本月累计收入 | revenue_fee | 本月累计收入 | decimal(18,2) | payment_recharge | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 本月累计收入（元） | revenue_fee | 本月累计收入（元）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | payment_recharge | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 子品牌 | sub_brand_id | 子品牌 | varchar(64) | payment_recharge | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 离网时间 | termination_time | 离网时间 | datetime | payment_recharge | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户状态时间 | user_date_status | 用户状态时间 | varchar(64) | payment_recharge | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 充值次数 | user_id | 充值次数 | integer | payment_recharge | 按次数字段规范命名为 xxx_count | 否 | 是 | 是 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 充值用户数 | user_id | 充值用户数 | integer | payment_recharge | 按次数字段规范命名为 xxx_count | 否 | 是 | 是 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户编号 | user_id | 用户编号 | varchar(64) | payment_recharge | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户编码 | user_id | 用户编码 | varchar(64) | payment_recharge | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 新充值日视图_3.0 | DA.A_U_CHARGE_INFO_CUR | 用户状态 | user_id_status | 用户状态 | varchar(64) | payment_recharge | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 交易后余额 | after_balance_amount | 交易后余额 | decimal(18,2) | payment_transaction | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 交易后余额(元) | after_balance_amount | 交易后余额(元) | decimal(18,2) | payment_transaction | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 交易前余额 | before_balance_amount | 交易前余额 | decimal(18,2) | payment_transaction | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 交易前余额(元) | before_balance_amount | 交易前余额(元) | decimal(18,2) | payment_transaction | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 商户 品牌 | brand_name | 商户 品牌 | varchar(255) | payment_transaction | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 数据日期 | data_time | 数据日期 | datetime | payment_transaction | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 交易出单机构 | invoices_org_name | 交易出单机构 | varchar(255) | payment_transaction | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 出单机构手续费金额 | invoices_recharge_amount | 出单机构手续费金额 | decimal(18,2) | payment_transaction | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 出单机构手续费金额(元) | invoices_recharge_amount | 出单机构手续费金额(元) | decimal(18,2) | payment_transaction | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 外部交易类型 | out_transaction_type | 外部交易类型 | varchar(64) | payment_transaction | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 受理渠道 | payment_acceptance_channel_name | 受理渠道 | varchar(255) | payment_transaction | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 交易支付机构 | payment_org_name | 交易支付机构 | varchar(255) | payment_transaction | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 交易金额 | payment_transaction_amount | 交易金额 | decimal(18,2) | payment_transaction | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 交易金额(元) | payment_transaction_amount | 交易金额(元) | decimal(18,2) | payment_transaction | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 总退货金额 | refund_amount | 总退货金额 | decimal(18,2) | payment_transaction | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 总退货金额(元) | refund_amount | 总退货金额(元) | decimal(18,2) | payment_transaction | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 交易笔数 | service_number_id | 交易笔数 | varchar(64) | payment_transaction | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 手机号码(全) | service_number_id | 手机号码(全) | varchar(64) | payment_transaction | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 服务号码 | service_number_id | 服务号码 | varchar(64) | payment_transaction | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 中心平台清算日期 | settlement_date | 中心平台清算日期 | date | payment_transaction | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 门店 店铺名称 | store_name | 门店 店铺名称 | varchar(255) | payment_transaction | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 终端设备编号 | terminal_id | 终端设备编号 | varchar(64) | payment_transaction | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 交易摘要 | transaction_abstract_name | 交易摘要 | varchar(255) | payment_transaction | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 受理渠道大类 | transaction_channel_level1_name | 受理渠道大类 | varchar(255) | payment_transaction | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 中心平台交易日期时间 | transaction_data_time | 中心平台交易日期时间 | datetime | payment_transaction | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 交易类型大类 | transaction_level1_type | 交易类型大类 | varchar(64) | payment_transaction | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 受理机构交易日期 | transaction_org_date | 受理机构交易日期 | date | payment_transaction | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 交易受理机构 | transaction_org_name | 交易受理机构 | varchar(255) | payment_transaction | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 交易流水类型 | transaction_status | 交易流水类型 | varchar(64) | payment_transaction | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 翼支付交易明细即席视图_3.0 | INTEG.I_PAY_DEAL_M | 交易类型 | transaction_type | 交易类型 | varchar(64) | payment_transaction | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 账户编码 | account_code | 账户编码 | varchar(64) | product_subscription | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 账户编号 | account_id | 账户编号 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 账户名称 | account_name | 账户名称 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 账户名称(全) | account_name | 账户名称(全) | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 发展六级部门 | acquisition_department_id | 发展六级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 发展部门 | acquisition_department_id | 发展部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 用户发展部门 | acquisition_department_id | 用户发展部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 发展五级部门 | acquisition_department_level5_id | 发展五级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 用户发展五级部门 | acquisition_department_level5_id | 用户发展五级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 发展员工 | acquisition_staff_id | 发展员工 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 发展员工工号(文件导入) | acquisition_staff_id | 发展员工工号(文件导入) | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 入网日期 | activation_date | 入网日期；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 用户分群 | bi_u_group_id | 用户分群 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 用户分群_统计 | bi_u_group_id | 用户分群_统计 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 入网月份 | billing_date | 入网月份；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费创建日期 | billing_date | 资费创建日期；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费失效日期 | billing_date | 资费失效日期；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费生效日期 | billing_date | 资费生效日期；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 宽带速率 | brd_line_rate | 宽带速率 | decimal(9,6) | product_subscription | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 楼宇区县 | building_area_id | 楼宇区县 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 楼宇区局 | building_bureau_id | 楼宇区局 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 楼宇编号 | building_code | 楼宇编号 | varchar(64) | product_subscription | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 楼宇编码 | building_code | 楼宇编码 | varchar(64) | product_subscription | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 楼宇经理二级部门 | building_department_2_name | 楼宇经理二级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 楼宇经理三级部门 | building_department_3_name | 楼宇经理三级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 楼宇经理四级部门 | building_department_4_name | 楼宇经理四级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 楼宇区局二级 | building_district_id | 楼宇区局二级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 楼宇 | building_id | 楼宇 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 楼宇性质 | building_kind_id | 楼宇性质 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 楼宇经理六级部门 | building_manager_department_id | 楼宇经理六级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 楼宇经理 | building_manager_id | 楼宇经理 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 楼宇名称 | building_name | 楼宇名称 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 楼宇类型 | building_type | 楼宇类型 | varchar(64) | product_subscription | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 受理渠道一级分类 | channel_type_level1_name | 受理渠道一级分类 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 组合产品壳子入网时间 | combo_activation_date_time | 组合产品壳子入网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 组合产品壳子资费生效时间 | combo_primary_price_plan_eff_date_time | 组合产品壳子资费生效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 组合产品壳子资费失效时间 | combo_primary_price_plan_exp_date_time | 组合产品壳子资费失效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 组合产品壳子主资费 | combo_primary_price_plan_id | 组合产品壳子主资费 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 组合产品壳子资费订购时间 | combo_primary_price_plan_order_date_time | 组合产品壳子资费订购时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 组合产品壳子ID | combo_product_instance_id | 组合产品壳子ID | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 组合产品壳子ID(文件导入) | combo_product_instance_id | 组合产品壳子ID(文件导入)；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 组合产品壳子号码 | combo_service_number_id | 组合产品壳子号码 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费属性 | coupon_id | 资费属性 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费创建日期 | create_dt_date | 资费创建日期；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费创建日期(天) | create_dt_date | 资费创建日期(天)；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 客户编号 | customer_id | 客户编号；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 客户名称 | customer_name | 客户名称 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 客户名称(全) | customer_name | 客户名称(全) | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 数据日期 | data_time | 数据日期 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 受理二级部门 | department_level2_id | 受理二级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 受理三级部门 | department_level3_id | 受理三级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 受理四级部门 | department_level4_id | 受理四级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 自注册终端机型 | device_model_id | 自注册终端机型 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 折扣数 | discount_count | 折扣数 | integer | product_subscription | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 折扣率 | discount_rate | 折扣率 | decimal(9,6) | product_subscription | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费失效日期 | end_dt_date | 资费失效日期；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 激活日期 | first_active_date | 激活日期；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 后向流量采购折扣率 | flux_discount_rate | 后向流量采购折扣率 | decimal(9,6) | product_subscription | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 后向流量活动名称 | flux_price_plan_name_usage_mb | 后向流量活动名称 | decimal(18,3) | product_subscription | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 后向流量合作伙伴虚拟号码 | flux_vir_number_usage_mb | 后向流量合作伙伴虚拟号码 | decimal(18,3) | product_subscription | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 2020年合约到期用户 | if_lease_exp_2016_snap_name | 2020年合约到期用户 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 在网标识 | is_active_subscriber | 在网标识 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 标志_当日用户在网 | is_active_subscriber | 标志_当日用户在网 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 存量用户标识 | is_bill_user_snap | 存量用户标识；由源表达式进行空值处理、截取或单位换算后形成 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 机型是否一致 | is_confer | 机型是否一致 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 手机终端标志(自注册) | is_device_g3 | 手机终端标志(自注册) | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 电渠条线标识 | is_digital_channel_line | 电渠条线标识 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 3G租机类别 | is_g3 | 3G租机类别 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 是否合约计划 | is_lease | 是否合约计划 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 标志_当月新增用户 | is_month_new | 标志_当月新增用户 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 昨日是否5G套餐（含包）用户 | is_p1d_user_5g | 昨日是否5G套餐（含包）用户 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 标志_预付后付 | is_prepaid_subscriber | 标志_预付后付 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 预付后付 | is_prepaid_subscriber | 预付后付 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 上月是否5G套餐（含包）用户 | is_previous_1_month_user_5g | 上月是否5G套餐（含包）用户 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 销渠条线标识 | is_sale_chnl_line | 销渠条线标识 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 移动固网 | is_service_network | 移动固网 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 移固标识 | is_service_network | 移固标识 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 维挽拍照标识 | is_ww_photo | 维挽拍照标识 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 是否年付资费 | is_ypay_primary_price_plan | 是否年付资费 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 主副卡标识 | is_zf_card_id | 主副卡标识；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费订购状态 | isvalid_status | 资费订购状态 | varchar(64) | product_subscription | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 协议在网月份数 | lease_active_subscriber_months_date | 协议在网月份数 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 协议在网月份数（PPM） | lease_active_subscriber_months_date | 协议在网月份数（PPM）；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费发展人部门二级 | offer_staff_department_level2_id | 资费发展人部门二级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费发展人部门三级 | offer_staff_department_level3_id | 资费发展人部门三级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费发展人部门四级 | offer_staff_department_level4_id | 资费发展人部门四级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费发展人部门五级 | offer_staff_department_level5_id | 资费发展人部门五级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费发展人部门六级 | offer_staff_department_level6_id | 资费发展人部门六级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费发展人 | offer_staff_id | 资费发展人 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 电子渠道用户类型 | previous_refund_account_cycle_type | 电子渠道用户类型 | varchar(64) | product_subscription | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 销售品分类 | price_label_id_amount | 销售品分类 | decimal(18,2) | product_subscription | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费ID(文件导入） | price_plan_code_amount | 资费ID(文件导入）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | product_subscription | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费id | price_plan_code_amount | 资费id | decimal(18,2) | product_subscription | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费名称 | price_plan_code_amount | 资费名称 | decimal(18,2) | product_subscription | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费订购数 | price_plan_code_amount | 资费订购数 | decimal(18,2) | product_subscription | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | X元预存充值档位 | price_plan_param_value_name | X元预存充值档位；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 主产品细类 | primary_product_id | 主产品细类 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 主产品细类二级 | primary_product_level2_id | 主产品细类二级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | YM红包流量(M) | red_envelope_flux_usage_mb | YM红包流量(M)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | product_subscription | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 接入方式 | refund_rule_id | 接入方式 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 受理渠道 | sales_channel_id | 受理渠道 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 服务号码 | service_number_id | 服务号码 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 服务号码(全) | service_number_id | 服务号码(全) | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 受理员工六级部门 | staff_department_id | 受理员工六级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 受理员工二级部门 | staff_department_level2_id | 受理员工二级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 受理员工三级部门 | staff_department_level3_id | 受理员工三级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 受理员工四级部门 | staff_department_level4_id | 受理员工四级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 受理员工五级部门 | staff_department_level5_id | 受理员工五级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 受理员工 | staff_id | 受理员工；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费生效日期 | start_dt_date | 资费生效日期；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 话费补贴金额（PPM） | subsidy_callfee_amount | 话费补贴金额（PPM）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | product_subscription | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 终端补贴金额（PPM） | subsidy_terminal_amount | 终端补贴金额（PPM）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | product_subscription | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 补贴类型 | subsidy_type | 补贴类型 | varchar(64) | product_subscription | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 补贴类型（PPM） | subsidy_type | 补贴类型（PPM） | varchar(64) | product_subscription | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 离网日期 | termination_date | 离网日期；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 发展二级部门 | user_develop_department_2_name | 发展二级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 用户发展二级部门 | user_develop_department_2_name | 用户发展二级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 发展三级部门 | user_develop_department_3_name | 发展三级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 用户发展三级部门 | user_develop_department_3_name | 用户发展三级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 发展四级部门 | user_develop_department_4_name | 发展四级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 用户发展四级部门 | user_develop_department_4_name | 用户发展四级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 用户编号 | user_id | 用户编号 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 资费订购用户数 | user_id | 资费订购用户数 | integer | product_subscription | 按次数字段规范命名为 xxx_count | 否 | 是 | 是 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 用户状态 | user_id_status | 用户状态 | varchar(64) | product_subscription | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 库存物品 | wp_coupon_id | 库存物品 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购日视图_3.0 | da.a_U_USER_PRICE_D | 主转副类型 | zf_card_change_id_type | 主转副类型 | varchar(64) | product_subscription | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 账户编码 | account_code | 账户编码 | varchar(64) | product_subscription | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 账户编号 | account_id | 账户编号 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 账户名称 | account_name | 账户名称 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 账户名称(全) | account_name | 账户名称(全) | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 账户名称(文件导入) | account_name | 账户名称(文件导入) | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 发展六级部门 | acquisition_department_id | 发展六级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 发展部门 | acquisition_department_id | 发展部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 用户发展部门 | acquisition_department_id | 用户发展部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 发展员工 | acquisition_staff_id | 发展员工 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 发展员工工号(文件导入) | acquisition_staff_id | 发展员工工号(文件导入) | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 入网日期 | activation_date | 入网日期；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 用户分群 | bi_u_group_id | 用户分群 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 用户分群_统计 | bi_u_group_id | 用户分群_统计 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 入网月份 | billing_date | 入网月份；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费创建日期 | billing_date | 资费创建日期；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 宽带速率 | brd_line_rate | 宽带速率 | decimal(9,6) | product_subscription | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 楼宇区县 | building_area_id | 楼宇区县 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 楼宇区局 | building_bureau_id | 楼宇区局 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 楼宇编号 | building_code | 楼宇编号 | varchar(64) | product_subscription | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 楼宇编码 | building_code | 楼宇编码 | varchar(64) | product_subscription | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 楼宇经理二级部门 | building_department_2_name | 楼宇经理二级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 楼宇经理三级部门 | building_department_3_name | 楼宇经理三级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 楼宇经理四级部门 | building_department_4_name | 楼宇经理四级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 楼宇区局二级 | building_district_id | 楼宇区局二级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 楼宇 | building_id | 楼宇 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 楼宇性质 | building_kind_id | 楼宇性质 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 楼宇经理六级部门 | building_manager_department_id | 楼宇经理六级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 楼宇经理 | building_manager_id | 楼宇经理 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 楼宇名称 | building_name | 楼宇名称 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 楼宇类型 | building_type | 楼宇类型 | varchar(64) | product_subscription | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 受理渠道一级分类 | channel_type_level1_name | 受理渠道一级分类 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 组合产品壳子入网时间 | combo_activation_date_time | 组合产品壳子入网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 组合产品壳子资费生效时间 | combo_primary_price_plan_eff_date_time | 组合产品壳子资费生效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 组合产品壳子资费失效时间 | combo_primary_price_plan_exp_date_time | 组合产品壳子资费失效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 组合产品壳子主资费 | combo_primary_price_plan_id | 组合产品壳子主资费 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 组合产品壳子资费订购时间 | combo_primary_price_plan_order_date_time | 组合产品壳子资费订购时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 组合产品壳子ID | combo_product_instance_id | 组合产品壳子ID | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 组合产品壳子ID(文件导入) | combo_product_instance_id | 组合产品壳子ID(文件导入)；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 组合产品壳子号码 | combo_service_number_id | 组合产品壳子号码 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费创建日期 | create_dt_date | 资费创建日期；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费创建日期(天) | create_dt_date | 资费创建日期(天)；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 客户编号 | customer_id | 客户编号；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 客户名称 | customer_name | 客户名称 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 客户名称(全) | customer_name | 客户名称(全) | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 数据日期 | data_time | 数据日期 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 自注册终端机型 | device_model_id | 自注册终端机型 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 折扣数 | discount_count | 折扣数 | integer | product_subscription | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 折扣率 | discount_rate | 折扣率 | decimal(9,6) | product_subscription | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费失效日期 | end_dt_date | 资费失效日期；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 激活日期 | first_active_date | 激活日期；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 2020年合约到期用户 | if_lease_exp_2016_snap_name | 2020年合约到期用户 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 标志_当月是否在网 | is_active_subscriber | 标志_当月是否在网 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 标志_当月用户在网 | is_active_subscriber | 标志_当月用户在网 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 本月是否出账(A口径) | is_bill | 本月是否出账(A口径) | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 2019年12月移动后预出账用户 | is_bill_201912 | 2019年12月移动后预出账用户 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 存量用户标识 | is_bill_user_snap | 存量用户标识；由源表达式进行空值处理、截取或单位换算后形成 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 机型是否一致 | is_confer | 机型是否一致 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 手机终端标志(自注册) | is_device_g3 | 手机终端标志(自注册) | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 电渠条线标识 | is_digital_channel_line | 电渠条线标识 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 3G租机类别 | is_g3 | 3G租机类别 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 是否合约计划 | is_lease | 是否合约计划 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 标志_预付后付 | is_prepaid_subscriber | 标志_预付后付 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 预付后付 | is_prepaid_subscriber | 预付后付 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 预后标识 | is_prepaid_subscriber | 预后标识 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 销渠条线标识 | is_sale_chnl_line | 销渠条线标识 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 移动固网 | is_service_network | 移动固网 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 移固标识 | is_service_network | 移固标识 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 维挽拍照标识 | is_ww_photo | 维挽拍照标识 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 是否年付资费 | is_ypay_primary_price_plan | 是否年付资费；由源表达式进行空值处理、截取或单位换算后形成 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 是否年付宽带续约 | is_ypay_xy | 是否年付宽带续约；由源表达式进行空值处理、截取或单位换算后形成 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 主副卡标识 | is_zf_card_id | 主副卡标识；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费订购状态 | isvalid_status | 资费订购状态 | varchar(64) | product_subscription | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 协议在网月份数 | lease_active_subscriber_months_date | 协议在网月份数 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 协议在网月份数（PPM） | lease_active_subscriber_months_date | 协议在网月份数（PPM）；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费发展人部门二级 | offer_staff_department_level2_id | 资费发展人部门二级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费发展人部门三级 | offer_staff_department_level3_id | 资费发展人部门三级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费发展人部门四级 | offer_staff_department_level4_id | 资费发展人部门四级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费发展人部门五级 | offer_staff_department_level5_id | 资费发展人部门五级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费发展人部门六级 | offer_staff_department_level6_id | 资费发展人部门六级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费发展人 | offer_staff_id | 资费发展人 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 电子渠道用户类型 | previous_refund_account_cycle_type | 电子渠道用户类型 | varchar(64) | product_subscription | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 销售品分类 | price_label_id_amount | 销售品分类 | decimal(18,2) | product_subscription | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费ID(文件导入） | price_plan_code_amount | 资费ID(文件导入）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | product_subscription | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费名称 | price_plan_code_amount | 资费名称 | decimal(18,2) | product_subscription | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费订购数 | price_plan_code_amount | 资费订购数 | decimal(18,2) | product_subscription | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | X元预存充值档位 | price_plan_param_value_name | X元预存充值档位；由源表达式进行空值处理、截取或单位换算后形成 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 主产品细类 | primary_product_id | 主产品细类 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 主产品细类二级 | primary_product_level2_id | 主产品细类二级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | YM红包流量(M) | red_envelope_flux_usage_mb | YM红包流量(M)；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,3) | product_subscription | 按流量字段规范命名为 xxx_usage_mb | 否 | 是 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 接入方式 | refund_rule_id | 接入方式 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 受理渠道 | sales_channel_id | 受理渠道 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 服务号码 | service_number_id | 服务号码 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 服务号码(全) | service_number_id | 服务号码(全) | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 受理员工六级部门 | staff_department_id | 受理员工六级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 受理员工二级部门 | staff_department_level2_id | 受理员工二级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 受理员工三级部门 | staff_department_level3_id | 受理员工三级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 受理员工四级部门 | staff_department_level4_id | 受理员工四级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 受理员工五级部门 | staff_department_level5_id | 受理员工五级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 受理员工 | staff_id | 受理员工；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费生效日期 | start_dt_date | 资费生效日期；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 话费补贴金额（PPM） | subsidy_callfee_amount | 话费补贴金额（PPM）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | product_subscription | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 终端补贴金额（PPM） | subsidy_terminal_amount | 终端补贴金额（PPM）；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | product_subscription | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 补贴类型 | subsidy_type | 补贴类型 | varchar(64) | product_subscription | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 补贴类型（PPM） | subsidy_type | 补贴类型（PPM） | varchar(64) | product_subscription | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 离网日期 | termination_date | 离网日期；由源表达式进行空值处理、截取或单位换算后形成 | date | product_subscription | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 发展二级部门 | user_develop_department_2_name | 发展二级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 用户发展二级部门 | user_develop_department_2_name | 用户发展二级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 发展三级部门 | user_develop_department_3_name | 发展三级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 用户发展三级部门 | user_develop_department_3_name | 用户发展三级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 发展四级部门 | user_develop_department_4_name | 发展四级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 用户发展四级部门 | user_develop_department_4_name | 用户发展四级部门 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 用户编号 | user_id | 用户编号 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费订购客户数 | user_id | 资费订购客户数 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 资费订购用户数 | user_id | 资费订购用户数 | integer | product_subscription | 按次数字段规范命名为 xxx_count | 否 | 是 | 是 | 否 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 用户状态 | user_id_status | 用户状态 | varchar(64) | product_subscription | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新用户资费订购月视图_3.0 | da.a_u_user_price_m | 主转副类型 | zf_card_change_id_type | 主转副类型 | varchar(64) | product_subscription | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 成员账户编码 | account_code | 成员账户编码 | varchar(64) | product_subscription | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 成员账户编号 | account_id | 成员账户编号 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 成员账户名称 | account_name | 成员账户名称 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 用户发展部门 | acquisition_department_id | 用户发展部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 用户发展二级部门 | acquisition_department_level2_id | 用户发展二级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 用户发展三级部门 | acquisition_department_level3_id | 用户发展三级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 用户发展四级部门 | acquisition_department_level4_id | 用户发展四级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 用户发展五级部门 | acquisition_department_level5_id | 用户发展五级部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 用户发展员工 | acquisition_staff_id | 用户发展员工 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子成员入网时间 | activation_time | 子成员入网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户开户时间 | activation_time | 子用户开户时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户楼宇区局 | building_bureau_id | 子用户楼宇区局 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户楼宇性质 | building_kind_id | 子用户楼宇性质 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户楼宇经理 | building_manager_id | 子用户楼宇经理 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户楼宇名称 | building_name | 子用户楼宇名称 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户楼宇类型 | building_type | 子用户楼宇类型 | varchar(64) | product_subscription | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子账户编码 | combo_account_code | 壳子账户编码 | varchar(64) | product_subscription | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子账户编号 | combo_account_id | 壳子账户编号 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子账户名称 | combo_account_name | 壳子账户名称 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户入网时间 | combo_activation_date_time | 壳子用户入网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户资费覆盖标识 | combo_component_offer_id | 壳子用户资费覆盖标识 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子客户编码 | combo_customer_id_code | 壳子客户编码 | varchar(64) | product_subscription | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子客户名称 | combo_customer_name | 壳子客户名称 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户发展部门 | combo_develop_department_id | 壳子用户发展部门 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户发展人 | combo_develop_staff_id | 壳子用户发展人 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 角色名称 | combo_member_role_name | 角色名称 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户销售品 | combo_offer_id | 壳子用户销售品 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户销售品id | combo_offer_id | 壳子用户销售品id | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户销售品名称 | combo_offer_id_name | 壳子用户销售品名称 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户产品覆盖级别 | combo_price_plan_cover_rank_name | 壳子用户产品覆盖级别 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户主资费生效时间 | combo_primary_price_plan_eff_date_time | 壳子用户主资费生效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户主资费失效时间 | combo_primary_price_plan_exp_date_time | 壳子用户主资费失效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户主资费 | combo_primary_price_plan_id | 壳子用户主资费 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户主资费订购时间 | combo_primary_price_plan_order_date_time | 壳子用户主资费订购时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户主产品 | combo_primary_product_id | 壳子用户主产品 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户主产品细类二级 | combo_primary_product_level2_id | 壳子用户主产品细类二级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户产品编码 | combo_product_code | 壳子用户产品编码；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | product_subscription | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户编码 | combo_product_instance_code | 壳子用户编码 | varchar(64) | product_subscription | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户数 | combo_product_instance_count | 壳子用户数 | integer | product_subscription | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户id | combo_product_instance_id | 壳子用户id | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户编号 | combo_product_instance_id | 壳子用户编号；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户产品名称 | combo_product_name | 壳子用户产品名称 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户服务号码 | combo_service_number_id | 壳子用户服务号码 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户服务号码(文件导入) | combo_service_number_id | 壳子用户服务号码(文件导入) | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 壳子用户离网时间 | combo_termination_date_time | 壳子用户离网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 成员创建时间 | create_dt_time | 成员创建时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 成员客户编码 | customer_id | 成员客户编码 | varchar(64) | product_subscription | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 成员客户名称 | customer_name | 成员客户名称 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 数据日期 | data_time | 数据日期 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 成员状态变更时间 | dt_status | 成员状态变更时间；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | product_subscription | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 成员失效时间 | end_dt_time | 成员失效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户在网标识 | is_active_subscriber | 子用户在网标识 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户出账标识 | is_bill | 子用户出账标识 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户月新增标识 | is_month_new | 子用户月新增标识 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 标志_上月是否壳子用户 | is_not | 标志_上月是否壳子用户 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 标志_是否壳子用户 | is_not | 标志_是否壳子用户 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户预后付 | is_prepaid_subscriber | 子用户预后付 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户c固标识 | is_service_network | 子用户c固标识 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户年新增标识 | is_year_new | 子用户年新增标识 | boolean | product_subscription | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户租机计划 | lease_plan_id | 子用户租机计划 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户主资费名称 | member_primary_price_plan_name | 子用户主资费名称 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 成员状态 | member_status | 成员状态 | varchar(64) | product_subscription | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户销售品 | offer_id | 子用户销售品 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户销售品id | offer_id | 子用户销售品id | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户销售品名称 | offer_name | 子用户销售品名称 | varchar(255) | product_subscription | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 上月成员状态 | previous_code_status | 上月成员状态 | varchar(64) | product_subscription | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 上月壳子用户主资费 | previous_combo_primary_price_plan_id | 上月壳子用户主资费 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 上月壳子用户id | previous_combo_product_inst_id | 上月壳子用户id | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 上月壳子用户编码 | previous_combo_product_inst_id_code | 上月壳子用户编码 | varchar(64) | product_subscription | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 上月用户主资费 | previous_primary_price_plan_id | 上月用户主资费 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 上月成员角色 | previous_product_component_relationship_role_code | 上月成员角色 | varchar(64) | product_subscription | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 上月成员id | previous_user_id | 上月成员id | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 上月成员编码 | previous_user_id_code | 上月成员编码 | varchar(64) | product_subscription | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户主资费生效时间 | primary_price_plan_eff_date_time | 子用户主资费生效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户主资费失效时间 | primary_price_plan_exp_date_time | 子用户主资费失效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户覆盖后的主资费 | primary_price_plan_id | 子用户覆盖后的主资费 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户主资费订购时间 | primary_price_plan_order_date_time | 子用户主资费订购时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户主产品 | primary_product_id | 子用户主产品 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户主产品二级 | primary_product_level2_id | 子用户主产品二级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户主产品细类二级 | primary_product_level2_id | 子用户主产品细类二级 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 统计数 | product_subscription_count | 统计数 | integer | product_subscription | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户服务号码 | service_number_id | 子用户服务号码 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户服务号码(全) | service_number_id | 子用户服务号码(全) | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户服务号码(文件导入) | service_number_id | 子用户服务号码(文件导入) | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 成员生效时间 | start_dt_time | 成员生效时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户离网时间 | termination_time | 子用户离网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | product_subscription | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 用户数 | user_count | 用户数 | integer | product_subscription | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 成员id | user_id | 成员id | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 成员用户编号 | user_id | 成员用户编号；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 用户编号 | user_id | 用户编号 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 用户状态 | user_id_status | 用户状态 | varchar(64) | product_subscription | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新组合产品月视图_3.0 | da.a_U_COM_PROD_M | 子用户年付资费 | ypay_primary_price_plan_id | 子用户年付资费 | varchar(64) | product_subscription | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 发展人ID | acquisition_staff_id | 发展人ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 发展人 | acquisition_staff_name | 发展人 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 入网时间 | activation_time | 入网时间 | datetime | product_value_change | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 迁转前3月的增值业务类账目项平均收入 | addval_yuan_avg_before_fee | 迁转前3月的增值业务类账目项平均收入 | decimal(18,2) | product_value_change | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 证件类型 | certificate_split_type | 证件类型 | varchar(64) | product_value_change | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 迁转原因 | change_reason_name | 迁转原因 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 账期 | data_time | 账期 | datetime | product_value_change | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 副卡数 | fk_count | 副卡数 | integer | product_value_change | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 迁转前3月的High会员类账目项平均收入 | highclub_yuan_avg_before_fee | 迁转前3月的High会员类账目项平均收入 | decimal(18,2) | product_value_change | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 包办理2级部门 | if_order_add_pkg_department_level2_name | 包办理2级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 包办理2级部门ID | if_order_add_pkg_department_level2_name | 包办理2级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 包办理3级部门 | if_order_add_pkg_department_level3_name | 包办理3级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 包办理3级部门ID | if_order_add_pkg_department_level3_name | 包办理3级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 包办理4级部门 | if_order_add_pkg_department_level4_name | 包办理4级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 包办理4级部门ID | if_order_add_pkg_department_level4_name | 包办理4级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 包办理5级部门 | if_order_add_pkg_department_level5_name | 包办理5级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 包办理5级部门ID | if_order_add_pkg_department_level5_name | 包办理5级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 包办理6级部门 | if_order_add_pkg_department_name | 包办理6级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 包办理6级部门ID | if_order_add_pkg_department_name | 包办理6级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 包办理人ID | if_order_add_pkg_staff_id | 包办理人ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 包办理人 | if_order_add_pkg_staff_name | 包办理人 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 合约办理2级部门 | if_order_lease_price_plan_department_level2_name | 合约办理2级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 合约办理2级部门ID | if_order_lease_price_plan_department_level2_name | 合约办理2级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 合约办理3级部门 | if_order_lease_price_plan_department_level3_name | 合约办理3级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 合约办理3级部门ID | if_order_lease_price_plan_department_level3_name | 合约办理3级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 合约办理4级部门 | if_order_lease_price_plan_department_level4_name | 合约办理4级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 合约办理4级部门ID | if_order_lease_price_plan_department_level4_name | 合约办理4级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 合约办理5级部门 | if_order_lease_price_plan_department_level5_name | 合约办理5级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 合约办理5级部门ID | if_order_lease_price_plan_department_level5_name | 合约办理5级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 合约办理6级部门 | if_order_lease_price_plan_department_name | 合约办理6级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 合约办理6级部门ID | if_order_lease_price_plan_department_name | 合约办理6级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 合约办理人ID | if_order_lease_price_plan_staff_id | 合约办理人ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 合约办理人 | if_order_lease_price_plan_staff_name | 合约办理人 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 套餐办理2级部门 | if_order_primary_price_plan_department_level2_name | 套餐办理2级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 套餐办理2级部门ID | if_order_primary_price_plan_department_level2_name | 套餐办理2级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 套餐办理3级部门 | if_order_primary_price_plan_department_level3_name | 套餐办理3级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 套餐办理3级部门ID | if_order_primary_price_plan_department_level3_name | 套餐办理3级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 套餐办理4级部门 | if_order_primary_price_plan_department_level4_name | 套餐办理4级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 套餐办理4级部门ID | if_order_primary_price_plan_department_level4_name | 套餐办理4级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 套餐办理5级部门 | if_order_primary_price_plan_department_level5_name | 套餐办理5级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 套餐办理5级部门ID | if_order_primary_price_plan_department_level5_name | 套餐办理5级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 套餐办理6级部门 | if_order_primary_price_plan_department_name | 套餐办理6级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 套餐办理6级部门ID | if_order_primary_price_plan_department_name | 套餐办理6级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 套餐办理人ID | if_order_primary_price_plan_staff_id | 套餐办理人ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 套餐办理人 | if_order_primary_price_plan_staff_name | 套餐办理人 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 迁转后宽带融合标志ID | is_ronghe_after_change | 迁转后宽带融合标志ID | boolean | product_value_change | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 迁转前1月宽带融合标志ID | is_ronghe_before_change | 迁转前1月宽带融合标志ID | boolean | product_value_change | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 迁转后宽带融合标志 | is_ronghe_name_after_change | 迁转后宽带融合标志 | boolean | product_value_change | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 办理前1月宽带融合标志 | is_ronghe_name_before_change | 办理前1月宽带融合标志 | boolean | product_value_change | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 办理前的合约ID | lease_plan_before_change_id | 办理前的合约ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 办理前的合约 | lease_plan_before_change_name | 办理前的合约 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 星级等级 | membership_level_name | 星级等级 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 星级等级ID | membership_level_name | 星级等级ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 迁转前3月的彩信类账目项平均收入 | mms_yuan_avg_before_fee | 迁转前3月的彩信类账目项平均收入 | decimal(18,2) | product_value_change | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 办理的增值包 | order_add_pkg_name | 办理的增值包 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 办理的增值包ID | order_add_pkg_name | 办理的增值包ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 办理后的合约 | order_lease_price_plan_name | 办理后的合约 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 办理后的合约ID | order_lease_price_plan_name | 办理后的合约ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 办理后的套餐 | order_primary_price_plan_name | 办理后的套餐 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 办理后的套餐ID | order_primary_price_plan_name | 办理后的套餐ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 办理前的套餐ID | primary_price_plan_before_change_id | 办理前的套餐ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 办理前的套餐 | primary_price_plan_before_change_name | 办理前的套餐 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 迁转前3月的固网类账目项平均收入 | pstn_yuan_avg_before_fee | 迁转前3月的固网类账目项平均收入 | decimal(18,2) | product_value_change | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 服务号码 | service_number_id | 服务号码 | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 迁转前3月的短信类账目项平均收入 | sms_yuan_avg_before_fee | 迁转前3月的短信类账目项平均收入 | decimal(18,2) | product_value_change | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 离网概率 | td_off_net_rate | 离网概率 | decimal(9,6) | product_value_change | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 用户4升5类型 | user_4upd5_ype_type | 用户4升5类型 | varchar(64) | product_value_change | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 发展2级部门ID | user_devlop_department_level2_id | 发展2级部门ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 发展2级部门 | user_devlop_department_level2_name | 发展2级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 发展3级部门ID | user_devlop_department_level3_id | 发展3级部门ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 发展3级部门 | user_devlop_department_level3_name | 发展3级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 发展4级部门ID | user_devlop_department_level4_id | 发展4级部门ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 发展4级部门 | user_devlop_department_level4_name | 发展4级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 发展5级部门ID | user_devlop_department_level5_id | 发展5级部门ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 发展5级部门 | user_devlop_department_level5_name | 发展5级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 发展6级部门ID | user_devlop_department_level6_id | 发展6级部门ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 发展6级部门 | user_devlop_department_level6_name | 发展6级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 用户数 | user_id | 用户数 | integer | product_value_change | 按次数字段规范命名为 xxx_count | 否 | 是 | 是 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 用户编码 | user_id | 用户编码 | varchar(64) | product_value_change | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 办理后预计T+1月摊分前总账收入 | val_after_amount | 办理后预计T+1月摊分前总账收入 | decimal(18,2) | product_value_change | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 办理前3个月的融合摊分前平均收入（剔除后） | val_before_amount | 办理前3个月的融合摊分前平均收入（剔除后） | decimal(18,2) | product_value_change | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 办理前3个月的融合摊分前平均收入（剔除前） | val_before_ori_amount | 办理前3个月的融合摊分前平均收入（剔除前） | decimal(18,2) | product_value_change | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 迁转收入差异（迁转后-迁转前） | val_change_amount | 迁转收入差异（迁转后-迁转前） | decimal(18,2) | product_value_change | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 高低迁即系查询日_3.0 | dm.m_rpt_usrval_chg_d | 迁转类型（高低平） | val_change_direction_type | 迁转类型（高低平） | varchar(64) | product_value_change | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 发展人ID | acquisition_staff_id | 发展人ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 发展人 | acquisition_staff_name | 发展人 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 入网时间 | activation_time | 入网时间 | datetime | product_value_change | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 迁转前3月的增值业务类账目项平均收入 | addval_yuan_avg_before_fee | 迁转前3月的增值业务类账目项平均收入 | decimal(18,2) | product_value_change | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 证件类型 | certificate_split_type | 证件类型 | varchar(64) | product_value_change | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 迁转原因 | change_reason_name | 迁转原因 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 账期 | data_time | 账期 | datetime | product_value_change | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 副卡数 | fk_count | 副卡数 | integer | product_value_change | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 迁转前3月的High会员类账目项平均收入 | highclub_yuan_avg_before_fee | 迁转前3月的High会员类账目项平均收入 | decimal(18,2) | product_value_change | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 包办理2级部门 | if_order_add_pkg_department_level2_name | 包办理2级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 包办理2级部门ID | if_order_add_pkg_department_level2_name | 包办理2级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 包办理3级部门 | if_order_add_pkg_department_level3_name | 包办理3级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 包办理3级部门ID | if_order_add_pkg_department_level3_name | 包办理3级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 包办理4级部门 | if_order_add_pkg_department_level4_name | 包办理4级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 包办理4级部门ID | if_order_add_pkg_department_level4_name | 包办理4级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 包办理5级部门 | if_order_add_pkg_department_level5_name | 包办理5级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 包办理5级部门ID | if_order_add_pkg_department_level5_name | 包办理5级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 包办理6级部门 | if_order_add_pkg_department_name | 包办理6级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 包办理6级部门ID | if_order_add_pkg_department_name | 包办理6级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 包办理人ID | if_order_add_pkg_staff_id | 包办理人ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 包办理人 | if_order_add_pkg_staff_name | 包办理人 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 合约办理2级部门 | if_order_lease_price_plan_department_level2_name | 合约办理2级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 合约办理2级部门ID | if_order_lease_price_plan_department_level2_name | 合约办理2级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 合约办理3级部门 | if_order_lease_price_plan_department_level3_name | 合约办理3级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 合约办理3级部门ID | if_order_lease_price_plan_department_level3_name | 合约办理3级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 合约办理4级部门 | if_order_lease_price_plan_department_level4_name | 合约办理4级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 合约办理4级部门ID | if_order_lease_price_plan_department_level4_name | 合约办理4级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 合约办理5级部门 | if_order_lease_price_plan_department_level5_name | 合约办理5级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 合约办理5级部门ID | if_order_lease_price_plan_department_level5_name | 合约办理5级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 合约办理6级部门 | if_order_lease_price_plan_department_name | 合约办理6级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 合约办理6级部门ID | if_order_lease_price_plan_department_name | 合约办理6级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 合约办理人ID | if_order_lease_price_plan_staff_id | 合约办理人ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 合约办理人 | if_order_lease_price_plan_staff_name | 合约办理人 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 套餐办理2级部门 | if_order_primary_price_plan_department_level2_name | 套餐办理2级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 套餐办理2级部门ID | if_order_primary_price_plan_department_level2_name | 套餐办理2级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 套餐办理3级部门 | if_order_primary_price_plan_department_level3_name | 套餐办理3级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 套餐办理3级部门ID | if_order_primary_price_plan_department_level3_name | 套餐办理3级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 套餐办理4级部门 | if_order_primary_price_plan_department_level4_name | 套餐办理4级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 套餐办理4级部门ID | if_order_primary_price_plan_department_level4_name | 套餐办理4级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 套餐办理5级部门 | if_order_primary_price_plan_department_level5_name | 套餐办理5级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 套餐办理5级部门ID | if_order_primary_price_plan_department_level5_name | 套餐办理5级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 套餐办理6级部门 | if_order_primary_price_plan_department_name | 套餐办理6级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 套餐办理6级部门ID | if_order_primary_price_plan_department_name | 套餐办理6级部门ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 套餐办理人ID | if_order_primary_price_plan_staff_id | 套餐办理人ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 套餐办理人 | if_order_primary_price_plan_staff_name | 套餐办理人 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 迁转后宽带融合标志ID | is_ronghe_after_change | 迁转后宽带融合标志ID | boolean | product_value_change | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 迁转前1月宽带融合标志ID | is_ronghe_before_change | 迁转前1月宽带融合标志ID | boolean | product_value_change | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 迁转后宽带融合标志 | is_ronghe_name_after_change | 迁转后宽带融合标志 | boolean | product_value_change | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 办理前1月宽带融合标志 | is_ronghe_name_before_change | 办理前1月宽带融合标志 | boolean | product_value_change | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 办理前的合约ID | lease_plan_before_change_id | 办理前的合约ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 办理前的合约 | lease_plan_before_change_name | 办理前的合约 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 星级等级 | membership_level_name | 星级等级 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 星级等级ID | membership_level_name | 星级等级ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 迁转前3月的彩信类账目项平均收入 | mms_yuan_avg_before_fee | 迁转前3月的彩信类账目项平均收入 | decimal(18,2) | product_value_change | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 办理的增值包 | order_add_pkg_name | 办理的增值包 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 办理的增值包ID | order_add_pkg_name | 办理的增值包ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 办理后的合约 | order_lease_price_plan_name | 办理后的合约 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 办理后的合约ID | order_lease_price_plan_name | 办理后的合约ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 办理后的套餐 | order_primary_price_plan_name | 办理后的套餐 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 办理后的套餐ID | order_primary_price_plan_name | 办理后的套餐ID | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 办理前的套餐ID | primary_price_plan_before_change_id | 办理前的套餐ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 办理前的套餐 | primary_price_plan_before_change_name | 办理前的套餐 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 迁转前3月的固网类账目项平均收入 | pstn_yuan_avg_before_fee | 迁转前3月的固网类账目项平均收入 | decimal(18,2) | product_value_change | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 服务号码 | service_number_id | 服务号码 | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 迁转前3月的短信类账目项平均收入 | sms_yuan_avg_before_fee | 迁转前3月的短信类账目项平均收入 | decimal(18,2) | product_value_change | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 离网概率 | td_off_net_rate | 离网概率 | decimal(9,6) | product_value_change | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 用户4升5类型 | user_4upd5_type | 用户4升5类型 | varchar(64) | product_value_change | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 用户4升5类型 | user_4upd5_ype_type | 用户4升5类型 | varchar(64) | product_value_change | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 发展2级部门ID | user_devlop_department_level2_id | 发展2级部门ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 发展2级部门 | user_devlop_department_level2_name | 发展2级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 发展3级部门ID | user_devlop_department_level3_id | 发展3级部门ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 发展3级部门 | user_devlop_department_level3_name | 发展3级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 发展4级部门ID | user_devlop_department_level4_id | 发展4级部门ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 发展4级部门 | user_devlop_department_level4_name | 发展4级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 发展5级部门ID | user_devlop_department_level5_id | 发展5级部门ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 发展5级部门 | user_devlop_department_level5_name | 发展5级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 发展6级部门ID | user_devlop_department_level6_id | 发展6级部门ID | varchar(64) | product_value_change | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 发展6级部门 | user_devlop_department_level6_name | 发展6级部门 | varchar(255) | product_value_change | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 用户数 | user_id | 用户数 | integer | product_value_change | 按次数字段规范命名为 xxx_count | 否 | 是 | 是 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 用户编码 | user_id | 用户编码 | varchar(64) | product_value_change | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 办理后预计T+1月摊分前总账收入 | val_after_amount | 办理后预计T+1月摊分前总账收入 | decimal(18,2) | product_value_change | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 办理前3个月的融合摊分前平均收入（剔除后） | val_before_amount | 办理前3个月的融合摊分前平均收入（剔除后） | decimal(18,2) | product_value_change | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 办理前3个月的融合摊分前平均收入（剔除前） | val_before_ori_amount | 办理前3个月的融合摊分前平均收入（剔除前） | decimal(18,2) | product_value_change | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 迁转收入差异（迁转后-迁转前） | val_change_amount | 迁转收入差异（迁转后-迁转前） | decimal(18,2) | product_value_change | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 高低迁即系查询月_3.0 | dm.m_rpt_usrval_chg_m | 迁转类型（高低平） | val_change_direction_type | 迁转类型（高低平） | varchar(64) | product_value_change | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 发展部门 | acquisition_department_id | 发展部门 | varchar(64) | real_name_compliance | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 发展部门6级 | acquisition_department_id | 发展部门6级 | varchar(64) | real_name_compliance | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 发展二级部门 | acquisition_department_level2_id | 发展二级部门 | varchar(64) | real_name_compliance | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 发展部门2级 | acquisition_department_level2_id | 发展部门2级 | varchar(64) | real_name_compliance | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 发展三级部门 | acquisition_department_level3_id | 发展三级部门 | varchar(64) | real_name_compliance | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 发展部门3级 | acquisition_department_level3_id | 发展部门3级 | varchar(64) | real_name_compliance | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 发展四级部门 | acquisition_department_level4_id | 发展四级部门 | varchar(64) | real_name_compliance | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 发展部门4级 | acquisition_department_level4_id | 发展部门4级 | varchar(64) | real_name_compliance | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 发展五级部门 | acquisition_department_level5_id | 发展五级部门 | varchar(64) | real_name_compliance | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 发展部门5级 | acquisition_department_level5_id | 发展部门5级 | varchar(64) | real_name_compliance | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 发展人工号 | acquisition_staff_id | 发展人工号 | varchar(64) | real_name_compliance | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 入网时间 | activation_time | 入网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | real_name_compliance | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 证件类型 | certificate_id_type | 证件类型 | varchar(64) | real_name_compliance | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 客户数 | customer_id | 客户数 | varchar(64) | real_name_compliance | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 客户编号 | customer_id | 客户编号 | varchar(64) | real_name_compliance | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 客户名称 | customer_name | 客户名称 | varchar(255) | real_name_compliance | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 客户名称（全） | customer_name | 客户名称（全） | varchar(255) | real_name_compliance | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 数据日期 | data_time | 数据日期 | datetime | real_name_compliance | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 标志_当日用户在网 | is_active_subscriber | 标志_当日用户在网 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 用户数 | is_active_subscriber | 用户数 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 是否月出账 | is_bill | 是否月出账 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 上月是否出账 | is_bill_sy | 上月是否出账 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 地址是否合规 | is_customer_address | 地址是否合规 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 证件是否合规 | is_customer_certificate | 证件是否合规 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 姓名是否合规 | is_customer_name | 姓名是否合规 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 电渠条线标识 | is_digital_channel_line | 电渠条线标识 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 标志_责任人非实名 | is_duty | 标志_责任人非实名 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 是否 服务-普通号码防诈骗承诺 | is_fraud_number | 是否 服务-普通号码防诈骗承诺 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 是否 服务-商话防诈骗承诺 | is_fraud_shnbr | 是否 服务-商话防诈骗承诺 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 标志_个人非实名 | is_if_realname | 标志_个人非实名 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 标志_经办人非实名 | is_operator | 标志_经办人非实名 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 标志_国政通校验结果 | is_profile_value | 标志_国政通校验结果 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 销渠条线标识 | is_sale_chnl_line | 销渠条线标识 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 标志_移动固网 | is_service_network | 标志_移动固网 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 是否实名制停机 | is_stop | 是否实名制停机 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 标志_单位客户非实名 | is_unit_customer | 标志_单位客户非实名 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 标志_使用人非实名 | is_user_party | 标志_使用人非实名 | boolean | real_name_compliance | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 沉默月份数 | noactive_months_date | 沉默月份数 | date | real_name_compliance | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 主资费名称 | primary_price_plan_name | 主资费名称 | varchar(255) | real_name_compliance | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 主产品细类二级 | primary_product_level2_id | 主产品细类二级 | varchar(64) | real_name_compliance | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 移动号码 | service_number_id | 移动号码 | varchar(64) | real_name_compliance | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 停机时间 | stop_date_time | 停机时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | real_name_compliance | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 用户编号 | user_id | 用户编号 | varchar(64) | real_name_compliance | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 实名制即席查询3.0 | da.a_u_user_realname_d | 用户状态 | user_id_status | 用户状态 | varchar(64) | real_name_compliance | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 受理渠道 | accept_channel_code | 受理渠道 | varchar(64) | service_complaint | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 受理时间 | accept_date_time | 受理时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | service_complaint | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 业务内容 | accept_desc_name | 业务内容 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 受理员工 | accept_staff_name | 受理员工 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 业务分类 | blend_type | 业务分类 | varchar(64) | service_complaint | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 办结原因类型 | cmplnt_casue_code_type | 办结原因类型 | varchar(64) | service_complaint | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 投诉号码 | cmplnt_number_count | 投诉号码 | integer | service_complaint | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 投诉号码(全) | cmplnt_number_count | 投诉号码(全) | integer | service_complaint | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 投诉咨询类型 | cmplnt_service_code_type | 投诉咨询类型 | varchar(64) | service_complaint | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 审核不通过次数 | complaint_review_reject_count | 审核不通过次数 | integer | service_complaint | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 审核不通过原因 | complaint_review_reject_name | 审核不通过原因 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 赔付金额 | comps_money_amount | 赔付金额；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | service_complaint | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 工单创建时间 | create_date_time | 工单创建时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | service_complaint | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 当天值班工作组 | current_workgroup_name | 当天值班工作组 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 客户联系人 | customer_contact_people_name | 客户联系人 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 客户联系电话 | customer_contact_phone_name | 客户联系电话 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 客户联系电话(全) | customer_contact_phone_name | 客户联系电话(全) | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 回访结单工单量 | customer_satisfy_code | 回访结单工单量 | varchar(64) | service_complaint | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 回访结束有升级倾向工单量 | customer_satisfy_code | 回访结束有升级倾向工单量 | varchar(64) | service_complaint | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 多次联系不成功归档工单量 | customer_satisfy_code | 多次联系不成功归档工单量 | varchar(64) | service_complaint | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 客户满意工单量 | customer_satisfy_code | 客户满意工单量 | varchar(64) | service_complaint | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 客户认可工单量 | customer_satisfy_code | 客户认可工单量 | varchar(64) | service_complaint | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 工单完成情况 | customer_satisfy_code | 工单完成情况 | varchar(64) | service_complaint | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 无需回复归档工单量 | customer_satisfy_code | 无需回复归档工单量 | varchar(64) | service_complaint | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 短信回复完成工单量 | customer_satisfy_code | 短信回复完成工单量 | varchar(64) | service_complaint | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 错单并结单工单量 | customer_satisfy_code | 错单并结单工单量 | varchar(64) | service_complaint | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 数据日期 | data_time | 数据日期 | datetime | service_complaint | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 接单部门 | duty_department_id | 接单部门 | varchar(64) | service_complaint | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 定责部门（2级） | dz_department_level2_name | 定责部门（2级） | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 定责部门（3级） | dz_department_level3_name | 定责部门（3级） | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 到期时间 | expire_date_time | 到期时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | service_complaint | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 工单到期时间 | expire_date_time | 工单到期时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | service_complaint | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 完成时间 | finish_date_time | 完成时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | service_complaint | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 首派单部门（2级） | first_accpt_department_level2_name | 首派单部门（2级） | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 首派单部门（3级） | first_accpt_department_level3_name | 首派单部门（3级） | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 首派单部门（细级） | first_dispatch_department_name | 首派单部门（细级） | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 分单永久所属工作组 | forever_owner_group_name | 分单永久所属工作组 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 分单永久处理人 | forever_owner_staff_name | 分单永久处理人 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 活动处理意见 | handle_comment_name | 活动处理意见 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 处理提交部门 | handle_commit_group_name | 处理提交部门 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 活动完成时间 | handle_complete_date_time | 活动完成时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | service_complaint | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 活动创建时间 | handle_create_date_time | 活动创建时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | service_complaint | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 创建工单部门 | handle_create_group_name | 创建工单部门 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 活动处理员工 | handle_staff_id | 活动处理员工 | varchar(64) | service_complaint | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 活动处理工作组 | handle_work_group_name | 活动处理工作组 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 活动处理部门 | handle_work_group_name | 活动处理部门 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 突发标识 | identity_state_id | 突发标识 | varchar(64) | service_complaint | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 重要程度 | important_level_name | 重要程度 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 是否申诉 | is_apeeal_cpn | 是否申诉 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 是否审核通过 | is_complaint_review_passed | 是否审核通过 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 是否成立 | is_establish | 是否成立 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 是否催单 | is_express | 是否催单 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 工单是否一次派单成功 | is_first_dispatch_success | 工单是否一次派单成功 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 是否越级投诉 | is_leapfrog_cpn | 是否越级投诉 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 回访及时率 | is_limit_revisit | 回访及时率 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 时限内回访工单量 | is_limit_revisit | 时限内回访工单量 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 是否时限内回访 | is_limit_revisit | 是否时限内回访 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 是否回访成功 | is_re_visits_success | 是否回访成功 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 是否重复投诉 | is_repeat | 是否重复投诉 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 是否超时 | is_time_out | 是否超时 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 是否转办 | is_trans_cpn | 是否转办 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 是否首次回应 | is_transparent_sms | 是否首次回应；由源表达式进行空值处理、截取或单位换算后形成 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 首次回应及时率 | is_transparent_sms | 首次回应及时率 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 首次回应工单量 | is_transparent_sms | 首次回应工单量 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 是否紧急投诉 | is_urgent | 是否紧急投诉 | boolean | service_complaint | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 最后一次回访时间 | lre_visits_date_time | 最后一次回访时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | service_complaint | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 最后处理时间 | lre_visits_date_time | 最后处理时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | service_complaint | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 未联时间间隔(小时) | nocontact_legnth_time | 未联时间间隔(小时) | datetime | service_complaint | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 配合部门一（2级） | op1_department_level2_name | 配合部门一（2级） | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 配合部门一（3级） | op1_department_level3_name | 配合部门一（3级） | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 配合部门一（细级） | op1_department_name | 配合部门一（细级） | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 配合部门二（2级） | op2_department_level2_name | 配合部门二（2级） | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 配合部门二（3级） | op2_department_level3_name | 配合部门二（3级） | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 配合部门二（细级） | op2_department_name | 配合部门二（细级） | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 活动操作类型 | operate_type | 活动操作类型 | varchar(64) | service_complaint | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 工单来源 | order_origin_name | 工单来源 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 工单来源对应级别 | order_origin_name | 工单来源对应级别 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 最后处理部门 | previous_transaction_org_name | 最后处理部门 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 最后处理员工 | previous_transaction_staff_name | 最后处理员工 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 活动回执内容 | reply_comment_name | 活动回执内容 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 责任部门 | responsibility_org_name | 责任部门 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 定责部门（细级） | responsible_department_name | 定责部门（细级） | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 工单类型 | rh_sub_work_type | 工单类型 | varchar(64) | service_complaint | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 派单次数 | send_cnt_count | 派单次数 | integer | service_complaint | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 工单派发次数 | send_count | 工单派发次数 | integer | service_complaint | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 派单量 | send_count | 派单量 | integer | service_complaint | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 派发次数 | send_count | 派发次数 | integer | service_complaint | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 派发人姓名 | send_staff_id_name | 派发人姓名 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 派发工作组 | send_work_group_name | 派发工作组 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 工单等级 | serial_level_name | 工单等级 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 工单显示流水 | show_serial_number_name | 工单显示流水 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 投诉咨询类型一级分类 | sr_id_level1_name_type | 投诉咨询类型一级分类 | varchar(64) | service_complaint | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 投诉咨询类型二级分类 | sr_id_level2_name_type | 投诉咨询类型二级分类 | varchar(64) | service_complaint | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 投诉咨询类型三级分类 | sr_id_level3_name_type | 投诉咨询类型三级分类 | varchar(64) | service_complaint | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 工单状态 | state_status | 工单状态 | varchar(64) | service_complaint | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 活动处理历时(小时) | sub_transaction_time_legnth_duration | 活动处理历时(小时) | integer | service_complaint | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 星级 | subs_level_new_name | 星级 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 分单临时所属工作组 | temporary_owner_group_name | 分单临时所属工作组 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 分单临时处理人 | temporary_owner_staff_name | 分单临时处理人 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 派达人姓名 | toward_staff_id_name | 派达人姓名 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 派达工作组 | toward_work_group_name | 派达工作组 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 工单处理次数 | transaction_count | 工单处理次数 | integer | service_complaint | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 处理时限(小时) | transaction_limit_time | 处理时限(小时) | datetime | service_complaint | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 工单处理历时(小时) | transaction_time_legnth_duration | 工单处理历时(小时) | integer | service_complaint | 按时长字段规范命名为 xxx_duration | 否 | 是 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 总活动量 | complaint_total_activity_name | 总活动量 | varchar(255) | service_complaint | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 用户编码 | user_id | 用户编码 | varchar(64) | service_complaint | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 一次回访办结工单量 | visit_count | 一次回访办结工单量 | integer | service_complaint | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 回访次数 | visit_count | 回访次数 | integer | service_complaint | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 工单一次回访结单率 | visit_count_rate | 工单一次回访结单率 | decimal(9,6) | service_complaint | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 总工单量 | voice_call_appeal_number_count | 总工单量 | integer | service_complaint | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 来电号码 | voice_call_appeal_number_count | 来电号码 | integer | service_complaint | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 投诉即席日视图_3.0 | DI.I_E_CUST_CMPLNT_EVENT_D | 来电号码(全) | voice_call_appeal_number_count | 来电号码(全) | integer | service_complaint | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 发展六级部门 | acquisition_department_id | 发展六级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 发展二级部门 | acquisition_department_level2_id | 发展二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 发展三级部门 | acquisition_department_level3_id | 发展三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 发展四级部门 | acquisition_department_level4_id | 发展四级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 发展五级部门 | acquisition_department_level5_id | 发展五级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 发展人 | acquisition_staff_id | 发展人 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 新考核一级部门 | assessment_department_level1_id | 新考核一级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 新考核二级部门 | assessment_department_level2_id | 新考核二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 新考核三级部门 | assessment_department_level3_id | 新考核三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 考核二级部门 | building_bureau_id | 考核二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 考核三级部门名称 | building_bureau_level2_name | 考核三级部门名称 | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 考核二级部门名称 | building_bureau_name | 考核二级部门名称 | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 考核三级部门 | building_district_id | 考核三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 楼宇 | building_id | 楼宇 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 客户ID | customer_id | 客户ID | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 客户名称 | customer_name | 客户名称 | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 客户名称(全) | customer_name | 客户名称(全) | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 客户名称（全） | customer_name | 客户名称（全） | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 账期 | data_time | 账期 | datetime | settlement_allocation | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 摊分标识 | is_settlement_allocation | 摊分标识 | boolean | settlement_allocation | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 摊分前税金 | pre_allocation_tax_fee | 摊分前税金；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 最近10月考核收入 | previous_10_fee | 最近10月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 最近11月考核收入 | previous_11_fee | 最近11月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 最近12月考核收入 | previous_12_fee | 最近12月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 最近1月考核收入 | previous_1_fee | 最近1月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 最近2月考核收入 | previous_2_fee | 最近2月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 最近3月考核收入 | previous_3_fee | 最近3月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 最近4月考核收入 | previous_4_fee | 最近4月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 最近5月考核收入 | previous_5_fee | 最近5月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 最近6月考核收入 | previous_6_fee | 最近6月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 最近7月考核收入 | previous_7_fee | 最近7月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 最近8月考核收入 | previous_8_fee | 最近8月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 最近9月考核收入 | previous_9_fee | 最近9月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 考核收入 | revenue_fee | 考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 服务号码 | service_number_id | 服务号码 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 服务号码（脱） | service_number_id | 服务号码（脱） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 摊分前楼宇区局 | settlement_allocation_building_bureau_id | 摊分前楼宇区局 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 摊分前楼宇区县 | settlement_allocation_building_bureau_level2_id | 摊分前楼宇区县 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 摊分前楼宇区县名称 | settlement_allocation_building_bureau_level2_name | 摊分前楼宇区县名称 | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 摊分前楼宇区局名称 | settlement_allocation_building_bureau_name | 摊分前楼宇区局名称 | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 摊分前发展人 | settlement_allocation_develop_staff_id | 摊分前发展人 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 摊分前收入 | settlement_allocation_fee | 摊分前收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 摊分前新考核二级部门 | settlement_allocation_nkh_department_level2_id | 摊分前新考核二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 摊分比率 | settlement_allocation_rate | 摊分比率 | decimal(9,6) | settlement_allocation | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 结算摊分(后)日即席视图_3.0 | da.a_u_user_360_repart_d | 税金 | tax_fee | 税金；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 发展六级部门 | acquisition_department_id | 发展六级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 发展二级部门 | acquisition_department_level2_id | 发展二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 发展三级部门 | acquisition_department_level3_id | 发展三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 发展四级部门 | acquisition_department_level4_id | 发展四级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 发展五级部门 | acquisition_department_level5_id | 发展五级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 发展人 | acquisition_staff_id | 发展人 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 新考核一级部门 | assessment_department_level1_id | 新考核一级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 新考核二级部门 | assessment_department_level2_id | 新考核二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 新考核三级部门 | assessment_department_level3_id | 新考核三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 考核二级部门 | building_bureau_id | 考核二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 考核三级部门名称 | building_bureau_level2_name | 考核三级部门名称 | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 考核二级部门名称 | building_bureau_name | 考核二级部门名称 | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 考核三级部门 | building_district_id | 考核三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 楼宇 | building_id | 楼宇 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 客户ID | customer_id | 客户ID | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 客户名称 | customer_name | 客户名称 | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 客户名称(全) | customer_name | 客户名称(全) | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 客户名称（全） | customer_name | 客户名称（全） | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 账期 | data_time | 账期 | datetime | settlement_allocation | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 摊分标识 | is_settlement_allocation | 摊分标识 | boolean | settlement_allocation | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 摊分前税金 | pre_allocation_tax_fee | 摊分前税金；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 最近10月考核收入 | previous_10_fee | 最近10月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 最近11月考核收入 | previous_11_fee | 最近11月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 最近12月考核收入 | previous_12_fee | 最近12月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 最近1月考核收入 | previous_1_fee | 最近1月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 最近2月考核收入 | previous_2_fee | 最近2月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 最近3月考核收入 | previous_3_fee | 最近3月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 最近4月考核收入 | previous_4_fee | 最近4月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 最近5月考核收入 | previous_5_fee | 最近5月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 最近6月考核收入 | previous_6_fee | 最近6月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 最近7月考核收入 | previous_7_fee | 最近7月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 最近8月考核收入 | previous_8_fee | 最近8月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 最近9月考核收入 | previous_9_fee | 最近9月考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 考核收入 | revenue_fee | 考核收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 服务号码 | service_number_id | 服务号码 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 服务号码(脱) | service_number_id | 服务号码(脱) | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 服务号码（脱） | service_number_id | 服务号码（脱） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 摊分前楼宇区局 | settlement_allocation_building_bureau_id | 摊分前楼宇区局 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 摊分前楼宇区县 | settlement_allocation_building_bureau_level2_id | 摊分前楼宇区县 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 摊分前楼宇区县名称 | settlement_allocation_building_bureau_level2_name | 摊分前楼宇区县名称 | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 摊分前楼宇区局名称 | settlement_allocation_building_bureau_name | 摊分前楼宇区局名称 | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 摊分前发展人 | settlement_allocation_develop_staff_id | 摊分前发展人 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 摊分前收入 | settlement_allocation_fee | 摊分前收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 摊分前新考核二级部门 | settlement_allocation_nkh_department_level2_id | 摊分前新考核二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 摊分比率 | settlement_allocation_rate | 摊分比率 | decimal(9,6) | settlement_allocation | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 结算摊分(后)月即席视图_3.0 | da.a_u_user_360_repart_m | 税金 | tax_fee | 税金；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 用户发展员工部门 | acquisition_department_id | 用户发展员工部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 用户发展二级部门 | acquisition_department_level2_id | 用户发展二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 用户发展员工二级部门 | acquisition_department_level2_id | 用户发展员工二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 用户发展三级部门 | acquisition_department_level3_id | 用户发展三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 用户发展员工三级部门 | acquisition_department_level3_id | 用户发展员工三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 用户发展员工四级部门 | acquisition_department_level4_id | 用户发展员工四级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 用户发展四级部门 | acquisition_department_level4_id | 用户发展四级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 用户发展五级部门 | acquisition_department_level5_id | 用户发展五级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 用户发展员工五级部门 | acquisition_department_level5_id | 用户发展员工五级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 用户发展员工 | acquisition_staff_id | 用户发展员工 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 新考核一级部门 | assessment_department_level1_id | 新考核一级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 新考核部门一级部门 | assessment_department_level1_id | 新考核部门一级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 新考核二级部门 | assessment_department_level2_id | 新考核二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 新考核部门二级部门 | assessment_department_level2_id | 新考核部门二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 新考核三级部门 | assessment_department_level3_id | 新考核三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 新考核部门三级部门 | assessment_department_level3_id | 新考核部门三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 楼宇区局（摊分后） | building_bureau_id | 楼宇区局（摊分后） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 楼宇区局细类（摊分后） | building_district_id | 楼宇区局细类（摊分后） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 客户编号 | customer_id | 客户编号 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 客户名称 | customer_name | 客户名称 | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 客户名称(全) | customer_name | 客户名称(全) | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 客户名称（全） | customer_name | 客户名称（全） | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 数据日期 | data_time | 数据日期 | datetime | settlement_allocation | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 摊分前收入 | revenue_fee | 摊分前收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 摊分后收入 | revenue_fee | 摊分后收入 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 服务号码 | service_number_id | 服务号码 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 服务号码(全) | service_number_id | 服务号码(全) | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 摊分标识 | settlement_allocation_blag_id | 摊分标识 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 楼宇区局（摊分前） | settlement_allocation_building_bureau_id | 楼宇区局（摊分前） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 楼宇区局细类（摊分前） | settlement_allocation_building_bureau_level2_id | 楼宇区局细类（摊分前） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 摊出方用户发展员工部门 | settlement_allocation_develop_department_id | 摊出方用户发展员工部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 摊出方用户发展二级部门 | settlement_allocation_develop_department_level2_id | 摊出方用户发展二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 摊出方用户发展三级部门 | settlement_allocation_develop_department_level3_id | 摊出方用户发展三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 摊出方用户发展四级部门 | settlement_allocation_develop_department_level4_id | 摊出方用户发展四级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 摊出方用户发展五级部门 | settlement_allocation_develop_department_level5_id | 摊出方用户发展五级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 摊出方用户发展员工 | settlement_allocation_develop_staff_id | 摊出方用户发展员工 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 摊出方新考核一级部门 | settlement_allocation_nkh_department_level1_id | 摊出方新考核一级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 摊出方新考核部门一级部门 | settlement_allocation_nkh_department_level1_id | 摊出方新考核部门一级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 摊出方新考核二级部门 | settlement_allocation_nkh_department_level2_id | 摊出方新考核二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 摊出方新考核三级部门 | settlement_allocation_nkh_department_level3_id | 摊出方新考核三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 摊出方新考核部门三级部门 | settlement_allocation_nkh_department_level3_id | 摊出方新考核部门三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 摊分比例 | settlement_allocation_rate | 摊分比例 | decimal(9,6) | settlement_allocation | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 摊分比率 | settlement_allocation_rate | 摊分比率 | decimal(9,6) | settlement_allocation | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 结算摊分日即席视图_3.0 | da.a_SET_REPART_D | 用户编号 | user_id | 用户编号 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户发展员工部门 | acquisition_department_id | 用户发展员工部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户发展二级部门 | acquisition_department_level2_id | 用户发展二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户发展员工二级部门 | acquisition_department_level2_id | 用户发展员工二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户发展三级部门 | acquisition_department_level3_id | 用户发展三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户发展员工三级部门 | acquisition_department_level3_id | 用户发展员工三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户发展员工四级部门 | acquisition_department_level4_id | 用户发展员工四级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户发展四级部门 | acquisition_department_level4_id | 用户发展四级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户发展五级部门 | acquisition_department_level5_id | 用户发展五级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户发展员工五级部门 | acquisition_department_level5_id | 用户发展员工五级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户发展员工 | acquisition_staff_id | 用户发展员工 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 新考核一级部门 | assessment_department_level1_id | 新考核一级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 新考核部门一级部门 | assessment_department_level1_id | 新考核部门一级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 新考核二级部门 | assessment_department_level2_id | 新考核二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 新考核部门二级部门 | assessment_department_level2_id | 新考核部门二级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 新考核三级部门 | assessment_department_level3_id | 新考核三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 新考核部门三级部门 | assessment_department_level3_id | 新考核部门三级部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 楼宇区局 | building_bureau_id | 楼宇区局 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 楼宇区局细类 | building_district_id | 楼宇区局细类 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 楼宇名称 | building_name | 楼宇名称 | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 客户编号 | customer_id | 客户编号 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 客户名称 | customer_name | 客户名称 | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 客户名称(全) | customer_name | 客户名称(全) | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 客户名称（全） | customer_name | 客户名称（全） | varchar(255) | settlement_allocation | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 数据日期 | data_time | 数据日期 | datetime | settlement_allocation | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 摊分前税金 | pre_allocation_tax_fee | 摊分前税金；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 摊分前收入 | revenue_fee | 摊分前收入；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 服务号码 | service_number_id | 服务号码 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 服务号码(脱) | service_number_id | 服务号码(脱) | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 服务号码（脱） | service_number_id | 服务号码（脱） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 摊分标识 | settlement_allocation_blag_id | 摊分标识 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 楼宇归属部门 | settlement_allocation_building_bureau_id | 楼宇归属部门 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 楼宇区局细类（摊分后） | settlement_allocation_building_bureau_level2_id | 楼宇区局细类（摊分后） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户发展员工部门（摊分后） | settlement_allocation_develop_department_id | 用户发展员工部门（摊分后） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户发展二级部门（摊分后） | settlement_allocation_develop_department_level2_id | 用户发展二级部门（摊分后） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户发展三级部门（摊分后） | settlement_allocation_develop_department_level3_id | 用户发展三级部门（摊分后） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户发展四级部门（摊分后） | settlement_allocation_develop_department_level4_id | 用户发展四级部门（摊分后） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户发展五级部门（摊分后） | settlement_allocation_develop_department_level5_id | 用户发展五级部门（摊分后） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 摊出方用户发展员工 | settlement_allocation_develop_staff_id | 摊出方用户发展员工 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户发展员工（摊分后） | settlement_allocation_develop_staff_id | 用户发展员工（摊分后） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 摊分前税金 | settlement_allocation_fee | 摊分前税金；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 新考核一级部门（摊分后） | settlement_allocation_nkh_department_level1_id | 新考核一级部门（摊分后） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 新考核部门一级部门（摊分后） | settlement_allocation_nkh_department_level1_id | 新考核部门一级部门（摊分后） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 新考核二级部门（摊分后） | settlement_allocation_nkh_department_level2_id | 新考核二级部门（摊分后） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 新考核三级部门（摊分后） | settlement_allocation_nkh_department_level3_id | 新考核三级部门（摊分后） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 新考核部门三级部门（摊分后） | settlement_allocation_nkh_department_level3_id | 新考核部门三级部门（摊分后） | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 摊分比例 | settlement_allocation_rate | 摊分比例 | decimal(9,6) | settlement_allocation | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 摊分比率 | settlement_allocation_rate | 摊分比率 | decimal(9,6) | settlement_allocation | 按比率字段规范命名为 xxx_rate | 否 | 是 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 税金 | tax_fee | 税金；由源表达式进行空值处理、截取或单位换算后形成 | decimal(18,2) | settlement_allocation | 按费用字段规范命名为 xxx_fee | 否 | 是 | 否 | 否 |
| 结算摊分月即席视图_3.0 | da.a_SET_REPART_M | 用户编号 | user_id | 用户编号 | varchar(64) | settlement_allocation | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 租机用户入网时间 | activation_time | 租机用户入网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | terminal_device | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 数据日期 | data_time | 数据日期 | datetime | terminal_device | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 标签_实际与租机是否匹配 | is_bq | 标签_实际与租机是否匹配 | boolean | terminal_device | 按标志字段规范命名为 is_xxx | 是 | 否 | 否 | 是 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 标签_注册用户为空 | is_name | 标签_注册用户为空 | varchar(255) | terminal_device | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 租机办理时间 | lease_price_plan_order_date_time | 租机办理时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | terminal_device | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 租机计划 | price_plan_code_amount | 租机计划 | decimal(18,2) | terminal_device | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 租机用户主套餐 | primary_price_plan_id | 租机用户主套餐 | varchar(64) | terminal_device | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 销售渠道 | sales_channel_id | 销售渠道 | varchar(64) | terminal_device | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 销售渠道二级部门 | sales_channel_level2_id | 销售渠道二级部门 | varchar(64) | terminal_device | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 销售渠道三级部门 | sales_channel_level3_id | 销售渠道三级部门 | varchar(64) | terminal_device | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 销售渠道四级部门 | sales_channel_level4_id | 销售渠道四级部门 | varchar(64) | terminal_device | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 销售渠道五级部门 | sales_channel_level5_id | 销售渠道五级部门 | varchar(64) | terminal_device | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 租机用户号码 | service_number_id | 租机用户号码 | varchar(64) | terminal_device | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 租机用户号码(全) | service_number_id | 租机用户号码(全) | varchar(64) | terminal_device | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 实际用户入网时间 | sj_activation_date_time | 实际用户入网时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | terminal_device | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 实际用户租机办理时间 | sj_lease_price_plan_order_date_time | 实际用户租机办理时间；由源表达式进行空值处理、截取或单位换算后形成 | datetime | terminal_device | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 实际用户租机 | sj_price_plan_code_amount | 实际用户租机 | decimal(18,2) | terminal_device | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 实际用户主套餐 | sj_primary_price_plan_id | 实际用户主套餐 | varchar(64) | terminal_device | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 实际用户号码 | sj_service_number_id | 实际用户号码 | varchar(64) | terminal_device | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 实际用户user_id | sj_user_id | 实际用户user_id | varchar(64) | terminal_device | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 销售状态 | state_status | 销售状态 | varchar(64) | terminal_device | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 当月累计终端数 | state_time | 当月累计终端数 | datetime | terminal_device | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 日新增终端数 | state_time | 日新增终端数 | datetime | terminal_device | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 累计终端数 | state_time | 累计终端数 | datetime | terminal_device | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 销售日期 | state_time | 销售日期；由源表达式进行空值处理、截取或单位换算后形成 | datetime | terminal_device | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 终端串码_id | terminal_goods_id | 终端串码_id | varchar(64) | terminal_device | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 终端型号 | terminal_model_id | 终端型号 | varchar(64) | terminal_device | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 终端串码 | terminal_serial_code | 终端串码 | varchar(64) | terminal_device | 按编码字段规范命名为 xxx_code | 是 | 否 | 否 | 是 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 用户编码 | user_id | 用户编码 | varchar(64) | terminal_device | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
| 新iphone终端销售即席查询_3.0 | INTEG.G_ODS_TERMINAL_iPhone5S5C_D | 租机用户user_id | user_id | 租机用户user_id | varchar(64) | terminal_device | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 是 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预约门店发展六级部门 | acquisition_department_id | 预约门店发展六级部门 | varchar(64) | terminal_presale | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预约门店发展二级部门 | acquisition_department_level2_id | 预约门店发展二级部门 | varchar(64) | terminal_presale | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预约门店发展三级部门 | acquisition_department_level3_id | 预约门店发展三级部门 | varchar(64) | terminal_presale | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预约门店发展四级部门 | acquisition_department_level4_id | 预约门店发展四级部门 | varchar(64) | terminal_presale | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预约门店发展五级部门 | acquisition_department_level5_id | 预约门店发展五级部门 | varchar(64) | terminal_presale | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 业务类型 | busi_type | 业务类型 | varchar(64) | terminal_presale | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 客户名称 | customer_name | 客户名称 | varchar(255) | terminal_presale | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 客户名称(全) | customer_name | 客户名称(全) | varchar(255) | terminal_presale | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 客户数 | customer_name | 客户数 | varchar(255) | terminal_presale | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 数据日期 | data_time | 数据日期 | datetime | terminal_presale | 按时间字段规范命名为 xxx_time | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预定订单ID | dragon_id | 预定订单ID | varchar(64) | terminal_presale | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预定订单id | dragon_id | 预定订单id | varchar(64) | terminal_presale | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预定流水号 | dragon_number_id | 预定流水号 | varchar(64) | terminal_presale | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 证件类型 | ident_code_type | 证件类型 | varchar(64) | terminal_presale | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 证件号码 | ident_name_type | 证件号码 | varchar(64) | terminal_presale | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预约门店考核一级部门 | kh_department_level1_id | 预约门店考核一级部门 | varchar(64) | terminal_presale | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预约门店考核三级部门 | kh_department_level3_id | 预约门店考核三级部门 | varchar(64) | terminal_presale | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 客户联系电话 | link_count | 客户联系电话 | integer | terminal_presale | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预约状态 | member_status | 预约状态 | varchar(64) | terminal_presale | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预约种类 | order_type | 预约种类 | varchar(64) | terminal_presale | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预约日期 | pre_date | 预约日期；由源表达式进行空值处理、截取或单位换算后形成 | date | terminal_presale | 按日期字段规范命名为 xxx_date | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预约工号 | pre_staff_id | 预约工号 | varchar(64) | terminal_presale | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 合约计划 | price_plan_code_amount | 合约计划 | decimal(18,2) | terminal_presale | 按金额字段规范命名为 xxx_amount | 否 | 是 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 新老用户 | product_type | 新老用户 | varchar(64) | terminal_presale | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 撤单、转正时关联预售订单流水 | relationship_dragon_id | 撤单、转正时关联预售订单流水 | varchar(64) | terminal_presale | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预约号 | reservation_order_id | 预约号 | varchar(64) | terminal_presale | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预约门店 | sales_channel_id | 预约门店 | varchar(64) | terminal_presale | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 受理渠道 | so_channel_id | 受理渠道 | varchar(64) | terminal_presale | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 受理渠道发展二级部门名称 | so_department_level2_name | 受理渠道发展二级部门名称 | varchar(255) | terminal_presale | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 受理渠道发展三级部门名称 | so_department_level3_name | 受理渠道发展三级部门名称 | varchar(255) | terminal_presale | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 受理渠道发展四级部门名称 | so_department_level4_name | 受理渠道发展四级部门名称 | varchar(255) | terminal_presale | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 受理渠道发展五级部门名称 | so_department_level5_name | 受理渠道发展五级部门名称 | varchar(255) | terminal_presale | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 受理渠道发展六级部门名称 | so_department_level6_name | 受理渠道发展六级部门名称 | varchar(255) | terminal_presale | 按名称字段规范命名为 xxx_name | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 状态时间 | state_date_status | 状态时间；由源表达式进行空值处理、截取或单位换算后形成 | varchar(64) | terminal_presale | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 受理系统 | system_id | 受理系统 | varchar(64) | terminal_presale | 按 ID 字段规范命名为 xxx_id | 是 | 否 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预定终端数量 | terminal_count | 预定终端数量 | integer | terminal_presale | 按次数字段规范命名为 xxx_count | 否 | 是 | 否 | 否 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 终端型号 | terminal_type | 终端型号 | varchar(64) | terminal_presale | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 预定终端型号 | terminal_type | 预定终端型号 | varchar(64) | terminal_presale | 按类型字段规范命名为 xxx_type | 是 | 否 | 否 | 是 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 处理状态 | transaction_status | 处理状态 | varchar(64) | terminal_presale | 按状态字段规范命名为 xxx_status | 是 | 否 | 否 | 是 |
| IPHONE 5S5C 预售视图_3.0 | INTEG.G_ODS_DRAGON_ORDER_D | 用户编码 | user_id | 用户编码 | varchar(64) | terminal_presale | 按编码字段规范命名为 xxx_code | 是 | 否 | 是 | 是 |
