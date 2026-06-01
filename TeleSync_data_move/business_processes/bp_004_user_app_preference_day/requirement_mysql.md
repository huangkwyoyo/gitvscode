# 04 DPI 应用流量偏好需求说明书

## 业务目标

按日识别用户应用访问偏好，统计视频、社交、游戏、办公教育等应用类别流量占比，识别重度视频用户、游戏高频用户、低访问高流量异常用户。

## 源表清单

| 层级 | 表名 | 用途 |
|---|---|---|
| DWD | `dwd.fact_dpi_usage_daily` | DPI 应用访问明细 |
| DWD | `dwd.dim_application` | 应用分类 |
| DWD | `dwd.fact_usage_daily` | 用户总流量 |
| DWD | `dwd.dim_user` | 用户城市、状态 |

## 结果表

`dws.dws_user_app_preference_day`

## 调度周期

每日运行一次，业务日期参数为 `@biz_date`。

## 业务规则

1. 以 `fact_dpi_usage_daily.data_date = @biz_date` 为处理范围。
2. 按用户和应用一级分类汇总访问次数、应用流量。
3. 计算每个用户应用流量占总 DPI 流量比例。
4. 用窗口函数选出用户当日 Top1 应用类别。
5. 视频类占比超过 60% 且总流量超过 2GB 标记为 `HEAVY_VIDEO`。
6. 页面访问少于 5 次但应用流量超过 1GB 标记为 `LOW_PV_HIGH_TRAFFIC`。

## 字段口径

| 字段 | 口径 |
|---|---|
| `top_app_category` | 当日流量最高的应用一级分类 |
| `top_app_usage_mb` | Top 应用分类流量 |
| `top_app_usage_ratio` | Top 应用流量占比 |
| `total_page_view_count` | 当日总访问次数 |
| `preference_tag` | 偏好标签 |

## 迁移测试价值

覆盖大表聚合、窗口 TopN、比例计算、分类维表关联、异常识别。



## 标准目录信息

- 业务过程 ID：`bp_004_user_app_preference_day`
- MySQL 结果表：`dws.dws_user_app_preference_day`
- 标准化日期：2026-06-01
