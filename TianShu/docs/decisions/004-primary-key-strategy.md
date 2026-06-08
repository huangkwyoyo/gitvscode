# 004 — 主键策略：代理键、复合键与哈希键的选择

## Status（状态）

Accepted

## Context（背景）

Silver 层 11 张表各自有不同的来源特征，不能使用统一的主键策略。具体差异如下：

| 表 | 来源主键状态 | 挑战 |
|---|---|---|
| `dim_date` | 无来源表（生成表） | 需要生成稳定的日期键 |
| `taxi_zone` | `LocationID` 265 个唯一值 | 天然主键，无需生成 |
| `trip_detail` | 四表 UNION ALL，各表无全局唯一键 | 8,032 万行，需要生成稳定的代理键 |
| `vehicle_detail` | 三表合并，`License Number` 为基础 | 多源同名字段合并 |
| `driver_detail` | 两表 UNION ALL，同一人可能同时持有 FHV 和 SHL 牌照 | 单字段不唯一，需要复合键 |
| `base_detail` | `Base License Number` 不唯一（1,117 vs 58,923 行） | 需要复合键治理 |
| `driver_application_detail` | `App No` 当前唯一 | 候选自然键 |
| `parking_violation_detail` | `summons_number` 当前唯一（958 万行） | 需要验证唯一性后确认 |
| `tif_payment_detail` | `License Number` 不唯一（6,115 vs 48,431 行） | 需要复合键治理 |
| `crash_detail` | `collision_id` 当前唯一（166 万行） | 候选自然键 |
| `crash_person_detail` | `unique_id` 当前唯一（533 万行） | 候选自然键 |

核心问题：**面对三种不同场景（自然键可用 / 需要复合键 / 需要生成代理键），Silver 层应该采用什么统一的主键策略？**

## Decision（决策）

**采用分级主键策略，根据来源表特征选择不同方案，并在项目中明确记录每张表的选择理由。具体落库主键以 `docs/warehouse/database_design/silver_database_design.md` 为唯一事实源；本文只解释策略依据。**

### 策略一：自然键直接使用（Natural Key）

适用条件：来源字段唯一、稳定、有业务含义。

| 表 | 主键 | 验证方式 |
|---|---|---|
| `taxi_zone` | `location_id`（INTEGER） | `SELECT COUNT(*) = COUNT(DISTINCT location_id)` |
| `driver_application_detail` | `app_no`（VARCHAR） | 同上 |
| `crash_detail` | `collision_id`（BIGINT） | 同上 |
| `crash_person_detail` | `unique_id`（BIGINT） | 同上 |

规则：
- 自然键不能为空
- 必须通过唯一性验证（Bronze 层已做校验）
- 字段类型可标准化（如 VARCHAR→INTEGER），但值不变

### 策略二：复合键（Composite Key）

适用条件：单字段不唯一，但多字段组合唯一。

| 表 | 复合键 | 组成 |
|---|---|---|
| `driver_detail` | `license_number` + `driver_type` | 同一人可同时持有 FHV 和 SHL 牌照 |
| `base_detail` | `base_license_number` + `year` + `month` | 基地按月上报 |
| `tif_payment_detail` | `license_number` + `payment_date` | 牌照按日支付 |

规则：
- 生成一个额外的 `composite_key` 字段（字符串拼接，如 `B00123_2026_01`），方便单字段引用
- 同时保留原始组成字段，不合并
- 如果复合键出现重复（`is_duplicate_key = TRUE`），标记质量问题但不丢弃数据

### 策略三：代理键（Surrogate Key）

适用条件：无可用自然键，或多源合并后无法保证唯一性。

| 表 | 代理键 | 生成方式 |
|---|---|---|
| `dim_date` | `date_key`（INTEGER） | `strftime(date, '%Y%m%d')::INTEGER`，确定性生成 |
| `trip_detail` | `trip_id`（VARCHAR） | `MD5(trip_source + 原始行所有字段拼接)`，确定性哈希 |
| `vehicle_detail` | `vehicle_id`（BIGINT） | 自增序列（单表场景，行数 ~12 万） |
| `parking_violation_detail` | `violation_id`（BIGINT） | 自增序列（单表场景） |

关键规则（从踩坑中提炼）：
- **禁止使用 `ROW_NUMBER() OVER ()`** 作为代理键生成方式——该写法无序，重跑后主键不稳定
- **多源合并场景用 MD5 哈希**——`trip_detail` 四表 UNION ALL，无法用自增序列，用 MD5 保证确定性
- **单表场景用自增序列**——简单高效，DuckDB 支持 `ROW_NUMBER() OVER (ORDER BY ...)` 稳定排序

## Alternatives（替代方案）

| 方案 | 优势 | 劣势 | 应用场景 |
|---|---|---|---|
| **全部用自增 BIGINT** | 统一，简单 | 多源 UNION ALL 场景不稳定；无法从主键反推数据来源 | ❌ 不适用 trip_detail |
| **全部用 UUID** | 全局唯一，分布式友好 | DuckDB 不原生支持 UUID 类型；存储空间大；不可读 | ❌ DuckDB 不支持 |
| **全部用 MD5 哈希** | 确定性，可溯源 | 存储和比较开销大于 BIGINT；不可排序 | ✅ 仅用于 trip_detail |
| **分级策略** ✅ | 按场景选择最优方案 | 不统一，需要文档记录每张表的策略 | ✅ 已通过本文档记录 |

## Consequences（后果）

### 正面影响

- 避免了"一刀切"带来的问题（如 trip_detail 如果用自增序列，重跑后 ID 全变）
- `ROW_NUMBER() OVER ()` 禁令已写入 `AGENTS.md` + `check_dangerous_patterns.py` 自动扫描
- 复合键表保留了 `composite_key` + 原始字段的双模式，查询灵活

### 负面影响 / 代价

- 主键策略不统一，新表需要显式决策（但这也是好事——强制思考每张表的主键合理性）
- MD5 哈希主键不可排序，无法从 `trip_id` 推断插入顺序
- 自增序列在单表重跑时需要 DELETE + INSERT（不能用 UPSERT），否则 ID 会变化

### 重新评估条件

1. **DuckDB 原生支持 UUID 类型**：重新评估 trip_detail 的哈希策略
2. **数据源切换到支持主键的数据库（如 PostgreSQL）**：自增序列可以改为 `SERIAL` / `IDENTITY`
3. **出现新的多源合并表**：沿用 MD5 哈希策略
