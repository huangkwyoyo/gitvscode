# Silver 层规则

> 从属于 `docs/warehouse/AGENTS.md` 和根 `AGENTS.md`。

## 1. Silver 层职责

Silver 是标准化层，不是业务建模层。**唯一职责：把 Bronze 原始数据变成字段标准、类型标准、主键清晰的明细数据。**

## 2. Silver 层允许做

- 字段命名标准化（snake_case统一，如 tpep_pickup_datetime → pickup_at）
- 数据类型标准化（VARCHAR→DATE、VARCHAR→BIGINT、DOUBLE→DECIMAL）
- 时间字段标准化（统一为 TIMESTAMP 或 DATE）
- 空值标注（标记缺失字段，不丢弃数据）
- 异常值标注（标记时间异常、距离异常等，不丢弃数据）
- 枚举值清洗（以 SELECT DISTINCT 实际值为准）
- 去重规则定义（代理键 + 自然候选键 + 复合键）
- 数据质量规则定义（缺失率、唯一性、范围校验）
- 字段名统一映射（不同源表同义字段 → 同一字段名）

## 3. Silver 层禁止做

- **新增 Bronze 不存在的业务字段**（最高优先级红线）
- 删除 Bronze 字段（可以弃用但不能物理删除）
- 编造金额字段
- 编造地理字段
- 编造指标或 KPI
- 推断主键（必须以 Bronze 数据画像为准）
- 推断外键（必须有人工确认的关联关系）
- 推断 Join 关系
- 聚合统计（SUM/AVG/COUNT GROUP BY 属于Gold层）
- 业务结论分析

## 4. Silver 字段来源分类（必须标注）

每个 Silver 字段必须属于以下三类之一：

### 4.1 直接来源字段（source_type = 'direct'）
字段值直接来自 Bronze 表的某一列。必须标注：来源 Bronze 表名、来源字段名。
示例：`pickup_at ← yellow_tripdata_2026q1.tpep_pickup_datetime`

### 4.2 标准化字段（source_type = 'standardized'）
字段值来自 Bronze 字段但经过了格式/类型/命名标准化。必须标注：原始字段名、标准化规则。
示例：`pickup_location_id ← PULocationID（统一大小写和命名风格）`

### 4.3 派生字段（source_type = 'derived'）
字段值通过计算/组合得出，Bronze 中没有直接对应列。必须标注：
- 来源字段
- 计算逻辑
- 可信等级（高/中/低）
- 是否可用于正式分析
- 状态：TODO / Human Review

## 5. 类型转换规则

| Bronze 现状 | Silver 标准 | 典型场景 |
|---|---|---|
| VARCHAR 存储的数字 | BIGINT | 基地汇总的行程数 |
| VARCHAR 存储的金额 | DECIMAL(12,2) | 行程费用、支付金额 |
| VARCHAR 存储的日期 | DATE | 支付日期、到期日期 |
| DOUBLE 存储的金额 | DECIMAL(12,2) | 行程车费、小费 |
| DOUBLE 存储的 ID/代码 | BIGINT | PULocationID、RatecodeID |

## 6. 质量标记规则

质量标记用于标注问题，不用于丢弃数据：
- `is_time_anomaly`：时间不在合理范围或逻辑倒挂
- `is_location_missing`：空间字段为空
- `is_distance_outlier`：距离超出合理范围
- `is_duplicate_xxx`：候选键出现重复
- `source_row_hash`：MD5 溯源

## 7. 危险 SQL 模式（禁止使用）

以下写法在 DuckDB 中不可用或有语义错误，禁止出现在 Silver 建表 SQL 中：

- `DATE::INT` → 应使用 `strftime(date_col, '%Y%m%d')::INTEGER`
- `ROW_NUMBER() OVER ()` 用于生成主键 → 应使用 MD5 稳定哈希
- `EXTRACT(DOW FROM ...)` 用于周一=1 → 应使用 `EXTRACT(ISODOW FROM ...)`
