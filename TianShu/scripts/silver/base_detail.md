# silver.base_detail（基地月度明细标准表）

## 表概览

| 属性 | 值 |
|---|---|
| 英文表名 | `silver.base_detail` |
| 中文表名 | 基地月度明细标准表 |
| 数据域 | 供给域 |
| 数据角色 | 事实表（Fact） |
| 批次 | P1（第二批） |
| 来源 | `bronze.fhv_base_aggregate_report`（58,923 行，9 列，全部 VARCHAR） |
| 预计行数 | ~5.9 万 |
| 主键 | `base_detail_id`（BIGINT，代理键），`composite_key`（候选键） |
| 字段数 | 12 |

## 设计理由

### 为什么必须用代理键而非自然键

Bronze 表有两个严重问题：

1. **`Base License Number` 不唯一**：1,117 个唯一值 vs 58,923 行。同一基地每月都有多行，甚至同月也可能有多行（数据发布时可能有修订版本混入）。
2. **全部字段为 VARCHAR**：`Total Dispatched Trips` 是数字但存在 VARCHAR 中，无法直接 SUM。

因此必须生成代理键 `base_detail_id`，并用 `Base License Number + Year + Month` 做复合键来去重。

### 为什么新增 `dba`（经营别名）

- `DBA`（Doing Business As）是 Bronze 源表的原生字段，但缺失率 80.7%。
- 即使缺失率高，也要保留，因为：
  1. **Agent 模糊匹配**：用户可能用经营别名（如"Uber NYC"）而非官方基地名来提问，Agent 需要搜索 `dba` 字段。
  2. 17.3% 的非空数据对部分基地是有效的补充信息。
  3. NULL 在列式存储中不占额外空间。

### 为什么新增 `month_name`（月份名称）

- Bronze 源表中已有 `Month Name`（如"January"），保留它而非丢弃，因为：
  1. BI 图表中直接用英文月份名做横轴标签，省去应用层 `CASE WHEN month=1 THEN 'January'` 的映射。
  2. 按月份名称排序可用 `month`（INTEGER）字段，不受字母序影响。

### 为什么所有数字字段强制 VARCHAR → BIGINT

Bronze 层 CSV 导入时 DuckDB 将所有列推断为 VARCHAR（因为 CSV 无类型信息）。Silver 层必须做类型转换：

| 字段 | 原类型 | 新类型 | 转换风险 |
|---|---|---|---|
| `Total Dispatched Trips` | VARCHAR | BIGINT | 低，全为整数 |
| `Total Dispatched Shared Trips` | VARCHAR | BIGINT | 低 |
| `Unique Dispatched Vehicles` | VARCHAR | BIGINT | 低 |
| `Year` | VARCHAR | INTEGER | 低 |
| `Month` | VARCHAR | INTEGER | 低 |

## 字段设计

| 英文字段名 | 中文字段名 | 新类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `base_detail_id` | 基地明细代理主键 | BIGINT | 生成 | PK，自增 |
| `base_license_number` | 基地牌照号 | VARCHAR | `Base License Number` | 1,117 个唯一值 |
| `base_name` | 基地名称 | VARCHAR | `Base Name` | 基地官方名称 |
| `dba` | 经营别名 | VARCHAR | `DBA` | Doing Business As，缺失率 80.7%，Agent 模糊匹配用 |
| `year` | 年份 | INTEGER | `Year` | VARCHAR→INTEGER |
| `month` | 月份 | INTEGER | `Month` | VARCHAR→INTEGER，1-12 |
| `month_name` | 月份名称 | VARCHAR | `Month Name` | January-December，BI 图表直接使用 |
| `total_dispatched_trips` | 调度行程总数 | BIGINT | `Total Dispatched Trips` | VARCHAR→BIGINT |
| `total_dispatched_shared_trips` | 共享行程数 | BIGINT | `Total Dispatched Shared Trips` | VARCHAR→BIGINT |
| `unique_dispatched_vehicles` | 去重调度车辆数 | BIGINT | `Unique Dispatched Vehicles` | VARCHAR→BIGINT |
| `composite_key` | 复合键 | VARCHAR | 生成 | `base_license_number + _ + year + _ + month` |
| `is_duplicate_key` | 是否复合键重复 | BOOLEAN | 生成 | 复合键出现 > 1 次时为 TRUE |

## 质量规则

- `composite_key` 出现重复时保留所有行，标记 `is_duplicate_key = TRUE`，由下游决定去重策略。
- 类型转换失败的行写入日志但不中断整体流程。
- `total_dispatched_trips < 0` 时标记异常。

## 字段来源分类

| 字段 | 来源类型 | 来源字段/逻辑 |
|---|---|---|
| `base_detail_id` | derived | 自增代理键 |
| `base_license_number` | direct | `Base License Number` |
| `base_name` | direct | `Base Name` |
| `dba` | direct | `DBA` |
| `year` | standardized | `Year`（VARCHAR→INTEGER） |
| `month` | standardized | `Month`（VARCHAR→INTEGER） |
| `month_name` | direct | `Month Name` |
| `total_dispatched_trips` | standardized | `Total Dispatched Trips`（VARCHAR→BIGINT） |
| `total_dispatched_shared_trips` | standardized | `Total Dispatched Shared Trips`（VARCHAR→BIGINT） |
| `unique_dispatched_vehicles` | standardized | `Unique Dispatched Vehicles`（VARCHAR→BIGINT） |
| `composite_key` | derived | `base_license_number + '_' + year + '_' + month` |
| `is_duplicate_key` | derived | 复合键重复检查 |
