# silver.driver_detail（司机明细标准表）

## 表概览

| 属性 | 值 |
|---|---|
| 英文表名 | `silver.driver_detail` |
| 中文表名 | 司机明细标准表 |
| 数据域 | 供给域 |
| 数据角色 | 维表（Dimension） |
| 批次 | P1（第二批） |
| 来源 | `bronze.fhv_active_drivers`（179,773 行）+ `bronze.shl_active_drivers`（180,236 行） |
| 预计行数 | ~36 万（UNION ALL 合并） |
| 主键 | `license_number` + `driver_type`（复合候选键），`driver_id`（代理键） |
| 字段数 | 11 |

## 设计理由

### 为什么用 UNION ALL 而非去重合并

- 同一人可能同时持有 FHV 和 SHL 牌照（两套不同的许可体系），各自有独立的到期日期和状态。
- 如果强行合并为一行，就丢失了"此人同时持有两种牌照"这一重要业务信息。
- 因此用 `license_number + driver_type` 作为复合候选键，UNION ALL 保留两套记录。

### 为什么新增 `driver_id` 代理键

- 复合自然键 `license_number + driver_type` 在 JOIN 时需要双字段关联，增加查询复杂度。
- `driver_id` BIGINT 代理键让下游 Gold 表只需单字段 JOIN，性能更好。

### 为什么 `status_code` 在 FHV 司机中为 NULL

- `Status Code`（1/2/3 许可级别）是 SHL（Street Hail Livery）独有的字段。
- FHV 司机表没有此字段，所以填 NULL。
- 在文档中明确标注"SHL 独有"，避免下游误以为数据缺失。

### 为什么 `last_time_updated` 保留 VARCHAR 而非 TIME 类型

- Bronze 层 CSV 导入后为 VARCHAR（如 `14:00:37`），格式统一但 DuckDB 的 TIME 类型不支持部分操作。
- 时间字段在分析中使用频率低（通常只看日期），保留 VARCHAR 不影响绝大多数查询。
- 如果未来有精确时间对比需求，再用 `TRY_CAST` 转换。

## 合并策略

```sql
SELECT ... FROM bronze.fhv_active_drivers  -- FHV 司机
UNION ALL
SELECT ... FROM bronze.shl_active_drivers  -- SHL 司机
```

无去重，因为同一个 `License Number` 在 FHV 和 SHL 中代表不同许可。

## 质量规则

- `license_number + driver_type` 复合键不允许重复。
- `expiration_date` 早于 `2026-01-01` 标记为已过期。
- `status_code` 在 FHV 类型中必须为 NULL。

## 字段来源分类

| 字段 | 来源类型 | 来源字段/逻辑 |
|---|---|---|
| `driver_id` | derived | 自增代理键 |
| `license_number` | direct | `License Number` |
| `driver_name` | direct | `Name` |
| `driver_type` | derived | FHV来自常量'FOR HIRE VEHICLE DRIVER'，SHL来自常量'SHL DRIVER' |
| `status_code` | standardized | `Status Code`（VARCHAR→INTEGER，SHL独有） |
| `status_description` | direct | `Status Description`（SHL独有） |
| `expiration_date` | standardized | `Expiration Date`（VARCHAR→DATE） |
| `wav_trained` | direct | `Wheelchair Accessible Trained`（FHV独有） |
| `last_date_updated` | standardized | `Last Date Updated`（VARCHAR→DATE） |
| `last_time_updated` | direct | `Last Time Updated` |
| `source_table` | derived | 常量 |
