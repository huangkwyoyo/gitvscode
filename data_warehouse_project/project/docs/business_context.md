# Telecom Business Context

## Overview

This project simulates an enterprise telecom data warehouse.

The purpose is to model realistic telecom business scenarios for:

- Data warehouse development
- KPI analysis
- SQL generation
- AI Agent development

------

# Business Domains

## Customer Domain

Represents subscriber information.

Examples:

- customer_id
- user_id
- phone_no
- gender
- age
- city
- province
- customer_level

------

## Product Domain

Represents telecom products.

Examples:

- package_id
- package_name
- package_fee
- package_type

Examples:

- 5G Package
- Data Package
- Family Package

------

## Subscription Domain

Represents user subscriptions.

Examples:

- subscribe_date
- unsubscribe_date
- package_id

A user may subscribe to multiple products.

------

## Billing Domain

Represents billing and charging.

Examples:

- monthly_fee
- package_fee
- extra_fee
- discount_fee

Formula:

bill_amount =
package_fee

- extra_fee

- discount_fee

------

## Payment Domain

Represents payment activities.

Examples:

- payment_date
- payment_amount
- payment_channel

Channels:

- APP
- WeChat
- Alipay
- Bank

------

## Usage Domain

Represents telecom usage.

Examples:

- data_usage_mb
- voice_usage_min
- sms_count

------

## Marketing Domain

Represents marketing activities.

Examples:

- campaign_id
- campaign_name
- channel
- conversion_flag

------

# Core Metrics

## Subscriber Count

Definition:

Number of active subscribers.

Formula:

count(distinct user_id)

------

## ARPU

Average Revenue Per User

Formula:

total_revenue / active_users

Unit:

CNY / user

------

## DOU

Data Usage Per User

Formula:

total_data_usage_mb / active_users

Unit:

MB / user

------

## MOU

Minutes Of Usage

Formula:

total_voice_minutes / active_users

Unit:

minutes / user

------

## Churn Rate

Definition:

Percentage of users who leave.

Formula:

lost_users / active_users

Unit:

%

------

## Conversion Rate

Definition:

Marketing conversion rate.

Formula:

converted_users / targeted_users

Unit:

%

------

# Data Warehouse Layers

ODS

Raw source data.

------

DWD

Cleaned detailed data.

------

DWS

Aggregated business subject data.

------

ADS

Business-oriented analytical data.

------

# Naming Convention

Dimension Table:

dim_xxx

Fact Table:

fact_xxx

ODS Table:

ods_xxx

DWD Table:

dwd_xxx

DWS Table:

dws_xxx

ADS Table:

ads_xxx

------

# Important Rules

Do not invent business meanings.

Do not assume metric definitions.

If metric definitions are missing:

1. Explain assumption
2. Mark assumption explicitly
3. Ask for confirmation

Metric definitions always override assumptions.