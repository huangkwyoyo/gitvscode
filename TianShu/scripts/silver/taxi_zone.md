# silver.taxi_zone（出租车区域标准维表）

## 表概览

| 属性 | 值 |
|---|---|
| 英文表名 | `silver.taxi_zone` |
| 中文表名 | 出租车区域标准维表 |
| 数据域 | 空间地理域 |
| 数据角色 | 维表（Dimension） |
| 批次 | P0（第一批） |
| 来源 | `bronze.taxi_zone_lookup` |
| 预计行数 | 265 |
| 主键 | `location_id`（INTEGER） |

## 设计理由

### 为什么 P0 第一批就建

- `taxi_zone` 是**所有行程表的空间维度锚点**。四类行程表的 `PULocationID`/`DOLocationID` 都引用 `LocationID`，没有这张维表就无法做任何空间分析。
- 265 行的小表，构建成本极低，但下游依赖极广。

### 为什么新增 `is_unknown_zone`

- Bronze 源表中有 `LocationID=264`（Unknown）和 `LocationID=265`（NA）两个特殊值。在空间分析中必须过滤或标注这些无效区域。
- `is_unknown_zone` 预计算比每次查询时写 `WHERE borough != 'Unknown'` 更清晰，Agent 查询时可直接引用此标记。

### 为什么字段名从 `LocationID` 改为 `location_id`

- 统一小写蛇形命名（snake_case），与 `trip_detail` 中的 `pickup_location_id`/`dropoff_location_id` 保持一致。
- DuckDB 对大小写敏感的表名/字段名需要引号包裹，统一小写避免引号问题。

### 为什么 `borough`、`zone_name`、`service_zone` 保留英文原值

- 这些是 NYC TLC 官方定义的名称（如"Upper East Side"、"Yellow Zone"），属于行业标准术语。
- 翻译成中文反而会丢失与官方文档的对应关系。
- 中文字段名（如"行政区"）已提供语义，英文值保留供精确匹配和排序。

## 字段设计

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `location_id` | 出租车区域编号 | INTEGER | `LocationID` | PK，区域唯一编号 1-265 |
| `borough` | 行政区 | VARCHAR | `Borough` | Manhattan / Queens / Brooklyn / Bronx / Staten Island / EWR / Unknown |
| `zone_name` | 区域名称 | VARCHAR | `Zone` | 261 个唯一区域名称 |
| `service_zone` | 服务区域 | VARCHAR | `service_zone` | Yellow Zone / Boro Zone / Airports / EWR |
| `is_unknown_zone` | 是否未知区域 | BOOLEAN | 派生 | `borough = 'Unknown'` 时为 TRUE |

## 生成 SQL

```sql
CREATE OR REPLACE TABLE silver.taxi_zone AS
SELECT
    LocationID AS location_id,
    Borough AS borough,
    Zone AS zone_name,
    service_zone,
    Borough = 'Unknown' AS is_unknown_zone
FROM bronze.taxi_zone_lookup;
```

## 质量规则

- `location_id` 不允许为空，必须唯一（265 行，Bronze 层已校验唯一）。
- `borough`、`zone_name`、`service_zone` 保留英文原值，不做中文翻译。
- `is_unknown_zone` 不能为 NULL。

## 字段来源分类

| 字段 | 来源类型 | 来源字段 |
|---|---|---|
| `location_id` | standardized | `LocationID`（重命名） |
| `borough` | standardized | `Borough`（重命名） |
| `zone_name` | standardized | `Zone`（重命名） |
| `service_zone` | direct | `service_zone` |
| `is_unknown_zone` | derived | `Borough = 'Unknown'` |
