# 电信业务背景

## 概述

本项目模拟了一个企业级电信数据仓库。

其目的是为以下场景构建真实的电信业务模型：

- 数据仓库开发
- KPI（关键绩效指标）分析
- SQL 生成
- AI 代理（Agent）开发

------

# 业务域

## 客户域 (Customer Domain)

代表用户/订户信息。

示例字段：

- customer_id（客户ID）
- user_id（用户ID）
- phone_no（手机号）
- gender（性别）
- age（年龄）
- city（城市）
- province（省份）
- customer_level（客户等级）

------

## 产品域 (Product Domain)

代表电信产品。

示例字段：

- package_id（套餐ID）
- package_name（套餐名称）
- package_fee（套餐费用）
- package_type（套餐类型）

示例产品类型：

- 5G 套餐
- 流量包
- 家庭融合套餐

------

## 订购域 (Subscription Domain)

代表用户的订购关系。

示例字段：

- subscribe_date（订购日期）
- unsubscribe_date（退订日期）
- package_id（套餐ID）

说明：一个用户可以同时订购多个产品。

------

## 计费域 (Billing Domain)

代表账单和收费情况。

示例字段：

- monthly_fee（月费）
- package_fee（套餐费）
- extra_fee（增值/额外费用）
- discount_fee（优惠减免金额）

计算公式：
账单金额 = 套餐费 + 额外费用 - 优惠减免金额

------

## 支付域 (Payment Domain)

代表支付活动。

示例字段：

- payment_date（支付日期）
- payment_amount（支付金额）
- payment_channel（支付渠道）

支付渠道包括：

- APP
- 微信 (WeChat)
- 支付宝 (Alipay)
- 银行卡 (Bank)

------

## 用量域 (Usage Domain)

代表电信资源的使用情况。

示例字段：

- data_usage_mb（数据流量使用量，单位MB）
- voice_usage_min（语音通话时长，单位分钟）
- sms_count（短信发送条数）

------

## 营销域 (Marketing Domain)

代表营销活动。

示例字段：

- campaign_id（活动ID）
- campaign_name（活动名称）
- channel（投放渠道）
- conversion_flag（转化标识）

------

# 核心指标

## 在网用户数 (Subscriber Count)

定义：
活跃订户的数量。

计算公式：
count(distinct user_id)

------

## ARPU（每用户平均收入）

计算公式：
总收入 / 活跃用户数

单位：
元 / 用户 (CNY / user)

------

## DOU（每用户平均数据流量使用量）

计算公式：
总数据流量使用量(MB) / 活跃用户数

单位：
MB / 用户

------

## MOU（每用户平均语音通话时长）

计算公式：
总语音通话时长(分钟) / 活跃用户数

单位：
分钟 / 用户

------

## 离网率 (Churn Rate)

定义：
流失用户所占的百分比。

计算公式：
流失用户数 / 活跃用户数

单位：
%

------

## 转化率 (Conversion Rate)

定义：
营销活动的转化率。

计算公式：
转化用户数 / 目标触达用户数

单位：
%

------

# 数据仓库层级

ODS（操作数据层）：原始源数据。
DWD（明细数据层）：清洗后的明细数据。
DWS（汇总数据层）：按业务主题聚合的数据。
ADS（应用数据层）：面向具体业务分析的指标数据。

------

# 命名规范

维度表：dim_xxx
事实表：fact_xxx
ODS 表：ods_xxx
DWD 表：dwd_xxx
DWS 表：dws_xxx
ADS 表：ads_xxx

------

# 重要规则

1. 严禁凭空捏造业务含义。
2. 严禁擅自假设指标的定义。

如果缺少明确的指标定义，必须遵循以下步骤：

1. 解释你的假设条件；
2. 明确标记出该假设为“推测”；
3. 请求确认。

注意：正式的业务指标定义永远优先于任何假设。