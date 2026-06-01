# 表关系分析

| 左表 | 关联字段 | 右表 | 用途 |
|---|---|---|---|
| `dwd.fact_usage_daily` | `user_id` | `dwd.dim_user` | 用户日行为补充用户维度 |
| `dwd.fact_dpi_usage_daily` | `application_id` | `dwd.dim_application` | DPI 应用分类补全 |
| `dwd.fact_order_daily` | `channel_id` | `dwd.dim_channel` | 订单渠道分析 |
| `dwd.fact_order_daily` | `product_id` | `dwd.dim_product` | 订单产品分析 |
| `dwd.fact_billing_monthly` | `user_id` | `dwd.dim_user` | 账单用户属性补全 |
| `dwd.fact_complaint_daily` | `responsible_department_id` | `dwd.dim_org` | 投诉责任部门分析 |
| `ods.ods_terminal_sales_daily` | `terminal_id` | `dwd.dim_terminal` | 终端履约分析 |
