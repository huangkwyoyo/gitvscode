# silver.dim_date（日期维表）

## 表概览

| 属性 | 值 |
|---|---|
| 英文表名 | `silver.dim_date` |
| 中文表名 | 日期维表 |
| 数据域 | 通用 |
| 数据角色 | 维表（Dimension） |
| 批次 | P0（第一批） |
| 来源 | 从 `silver.trip_detail.pickup_at` 的日期范围自动生成 |
| 预计行数 | ~90（2026-01-01 至 2026-03-31） |
| 主键 | `date_key`（INTEGER，YYYYMMDD 格式） |

## 设计理由

### 为什么 Silver 层需要日期维表

1. **Gold 层所有汇总表都需要时间维度**。日期维表是公共基础，放在 Silver 层供所有下游表复用，避免每张 Gold 汇总表重复生成日期逻辑。
2. **NYC 财年不是自然年**。NYC 财年从 7 月 1 日到次年 6 月 30 日，这个逻辑需要在维表中预计算，不能靠 SQL 临时算。
3. **构建顺序**：`dim_date` 应在 `trip_detail` 之前构建，这样 `trip_detail` 可以通过 `pickup_date = dim_date.date` 建立外键关联。

### 为什么用 INTEGER 而非 DATE 做主键

- `YYYYMMDD` 整数格式（如 `20260115`）在 DuckDB 中比 DATE 类型更高效的 JOIN，且方便做范围过滤（`date_key BETWEEN 20260101 AND 20260131`）。
- `date` 字段保留标准 DATE 类型，兼容 DuckDB 的日期函数。

### 为什么保留 `day_of_week_name` 英文名

- 直接用于 BI 图表横轴标签（Monday-Sunday），避免应用层再做映射。
- 中文字段名已说明含义，英文值保留便于国际化和排序（按 `day_of_week` 数字排序）。

## 字段设计

| 英文字段名 | 中文字段名 | 类型 | 字段层级 | 说明 |
|---|---|---|---|---|
| `date_key` | 日期键 | INTEGER | 主键 | YYYYMMDD 格式整数，如 `20260115` |
| `date` | 日期 | DATE | 维度属性 | 标准日期类型 |
| `year` | 年 | INTEGER | 维度属性 | 如 2026 |
| `quarter` | 季度 | INTEGER | 维度属性 | 1-4 |
| `month` | 月 | INTEGER | 维度属性 | 1-12 |
| `week` | 周 | INTEGER | 维度属性 | ISO 周号 1-53 |
| `day_of_week` | 星期几 | INTEGER | 维度属性 | 1=周一，7=周日 |
| `day_of_week_name` | 星期名称 | VARCHAR | 维度属性 | Monday-Sunday 英文名 |
| `is_weekend` | 是否周末 | BOOLEAN | 维度属性 | 周六/周日为 TRUE |
| `fiscal_year` | NYC财年 | INTEGER | 维度属性 | NYC 财年：7月1日-6月30日。2026年1-3月属于 FY2026 |

## 生成逻辑

```sql
-- 从 trip_detail 的日期范围动态生成
WITH date_range AS (
    SELECT
        MIN(pickup_at::DATE) AS start_date,
        MAX(pickup_at::DATE) AS end_date
    FROM silver.trip_detail
)
INSERT INTO silver.dim_date
SELECT
    strftime(d, '%Y%m%d')::INTEGER AS date_key,        -- DuckDB 中 DATE::INT 不可用，必须用 strftime
    d::DATE AS date,
    EXTRACT(YEAR FROM d) AS year,
    EXTRACT(QUARTER FROM d) AS quarter,
    EXTRACT(MONTH FROM d) AS month,
    EXTRACT(WEEK FROM d) AS week,
    EXTRACT(ISODOW FROM d) AS day_of_week,              -- ISODOW: 1=周一, 7=周日
    DAYNAME(d) AS day_of_week_name,
    EXTRACT(ISODOW FROM d) IN (6, 7) AS is_weekend,    -- ISODOW 中周六=6, 周日=7
    CASE WHEN EXTRACT(MONTH FROM d) >= 7
         THEN EXTRACT(YEAR FROM d) + 1
         ELSE EXTRACT(YEAR FROM d)
    END AS fiscal_year
FROM date_range, LATERAL (
    SELECT (start_date + INTERVAL (n - 1) DAY) AS d
    FROM generate_series(
        1,
        (end_date - start_date)::INTEGER + 1
    ) AS t(n)
);
```

## 质量规则

- `date_key` 不允许为空，必须唯一。
- `date` 范围覆盖 `trip_detail` 中所有 `pickup_date`。
- `fiscal_year` 不能为 NULL。

## 字段来源分类

| 字段 | 来源类型 | 说明 |
|---|---|---|
| `date_key` | derived | `strftime(d, '%Y%m%d')::INTEGER` |
| `date` | derived | `d::DATE` |
| `year` | derived | `EXTRACT(YEAR FROM d)` |
| `quarter` | derived | `EXTRACT(QUARTER FROM d)` |
| `month` | derived | `EXTRACT(MONTH FROM d)` |
| `week` | derived | `EXTRACT(WEEK FROM d)` |
| `day_of_week` | derived | `EXTRACT(ISODOW FROM d)` |
| `day_of_week_name` | derived | `DAYNAME(d)` |
| `is_weekend` | derived | `EXTRACT(ISODOW FROM d) IN (6,7)` |
| `fiscal_year` | derived | NYC财年计算逻辑 |
