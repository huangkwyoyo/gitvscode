# silver.crash_detail（事故明细标准表）

## 表概览

| 属性 | 值 |
|---|---|
| 英文表名 | `silver.crash_detail` |
| 中文表名 | 事故明细标准表 |
| 数据域 | 安全域 |
| 数据角色 | 事实表（Fact） |
| 批次 | P2（第三批） |
| 来源 | `bronze.crash_merged`（1,655,065 行，29 列，全部 VARCHAR） |
| 预计行数 | 166 万 |
| 主键 | `crash_id`（BIGINT，代理键），`collision_id`（候选键） |
| 字段数 | 25 |

## 设计理由

### 为什么弃用车辆 3-5 的字段（29 列 → 25 列，共弃用 7 个字段）

Bronze 层 `crash_merged` 有 5 组涉事车辆字段（每组含 `vehicle_type_code_N` 和 `contributing_factor_vehicle_N`），加上 1 个 `location` 结构字段：

| 弃用字段 | 类型 | 缺失率 | 弃用原因 |
|---|---|---|---|
| `vehicle_type_code_3` | VARCHAR | 93.0% | 涉及 3 辆车事故极少 |
| `contributing_factor_vehicle_3` | VARCHAR | 92.7% | 同上 |
| `vehicle_type_code_4` | VARCHAR | 98.4% | 涉及 4 辆车事故极罕见 |
| `contributing_factor_vehicle_4` | VARCHAR | 98.3% | 同上 |
| `vehicle_type_code_5` | VARCHAR | 99.6% | 涉及 5 辆车事故几乎不存在 |
| `contributing_factor_vehicle_5` | VARCHAR | 99.5% | 同上 |
| `location` | STRUCT | 79.5% | DuckDB STRUCT 类型难以直接查询，且经纬度字段已保留 |

保留的车辆 1-2 字段（4 个）：`vehicle_type_code1`、`contributing_factor_vehicle_1`、`vehicle_type_code2`、`contributing_factor_vehicle_2`。

绝大多数事故只涉及 1-2 辆车（如两车相撞、单车事故）。涉及 3 辆及以上的事故极其罕见，且数据质量极差。保留这 6 个低覆盖字段不仅浪费存储，还会误导分析（Agent 可能基于 2% 的非空数据做结论）。

### 为什么 `crash_date` + `crash_time` 合并为 `crash_at`

- 事故时间是分析的**核心维度**（"某月事故量""高峰时段事故率"）。
- 分离的日期+时间无法直接做时间范围查询（`WHERE crash_date BETWEEN ... AND crash_time > ...` 很繁琐）。
- 合并为 TIMESTAMP 后，一个 `WHERE crash_at BETWEEN ...` 即可。

### 为什么保留 8 个伤亡统计字段而非仅 `persons_injured` + `persons_killed`

Bronze 层有按人员类型细分的伤亡统计：

| 字段 | 含义 |
|---|---|
| `persons_injured` / `persons_killed` | 总计 |
| `pedestrians_injured` / `pedestrians_killed` | 行人 |
| `cyclist_injured` / `cyclist_killed` | 骑行者 |
| `motorist_injured` / `motorist_killed` | 机动车驾驶员 |

保留细分字段的理由：**政策分析需要知道"谁在受伤"**。例如：
- Vision Zero（零死亡愿景）政策关注行人和骑行者安全
- 机动车驾驶员伤亡 vs 行人伤亡的比率反映道路安全状况

如果只保留总计，Gold 层就无法做事故类型细分。

### 为什么 `borough` 缺失率 30.4% 仍保留

- 这是**唯一**的行政区字段，没有替代来源。
- 30.4% 缺失意味着 69.6% 有值——超过 115 万行有 borough 信息。
- 用经纬度反查 borough 是 Gold 层的增强逻辑，Silver 层只负责保留原始数据。

## 质量规则

- `collision_id` 需验证唯一性。
- `crash_at` 不能为 NULL（日期+时间缺一不可）。
- `persons_injured < 0` 或 `> 100` 标记异常。
- `latitude = 0 AND longitude = 0` 标记 `is_location_missing`（非法的坐标原点）。

## 字段来源分类

| 字段 | 来源类型 | 来源字段/逻辑 |
|---|---|---|
| `crash_id` | derived | 自增代理键 |
| `collision_id` | standardized | `collision_id`（VARCHAR→BIGINT） |
| `crash_at` | derived | `crash_date + ' ' + crash_time`（VARCHAR合并→TIMESTAMP） |
| `borough` | direct | `borough` |
| `zip_code` | direct | `zip_code` |
| `latitude` | standardized | `latitude`（VARCHAR→DOUBLE） |
| `longitude` | standardized | `longitude`（VARCHAR→DOUBLE） |
| `on_street_name` | direct | `on_street_name` |
| `cross_street_name` | direct | `cross_street_name` |
| `off_street_name` | direct | `off_street_name` |
| `persons_injured` | standardized | `number_of_persons_injured`（VARCHAR→INTEGER） |
| `persons_killed` | standardized | `number_of_persons_killed`（VARCHAR→INTEGER） |
| `pedestrians_injured` | standardized | `number_of_pedestrians_injured`（VARCHAR→INTEGER） |
| `pedestrians_killed` | standardized | `number_of_pedestrians_killed`（VARCHAR→INTEGER） |
| `cyclist_injured` | standardized | `number_of_cyclist_injured`（VARCHAR→INTEGER） |
| `cyclist_killed` | standardized | `number_of_cyclist_killed`（VARCHAR→INTEGER） |
| `motorist_injured` | standardized | `number_of_motorist_injured`（VARCHAR→INTEGER） |
| `motorist_killed` | standardized | `number_of_motorist_killed`（VARCHAR→INTEGER） |
| `vehicle_type_1` | direct | `vehicle_type_code1`（重命名） |
| `vehicle_type_2` | direct | `vehicle_type_code2`（重命名） |
| `contributing_factor_1` | direct | `contributing_factor_vehicle_1`（重命名） |
| `contributing_factor_2` | direct | `contributing_factor_vehicle_2`（重命名） |
| `is_duplicate_collision` | derived | collision_id重复检查 |
| `is_location_missing` | derived | latitude/longitude为NULL检查 |
| `source_row_hash` | derived | MD5溯源 |
