# silver.tif_payment_detail（TIF支付明细标准表）

## 表概览

| 属性 | 值 |
|---|---|
| 英文表名 | `silver.tif_payment_detail` |
| 中文表名 | TIF支付明细标准表 |
| 数据域 | 监管合规域 |
| 数据角色 | 事实表（Fact） |
| 批次 | P2（第三批） |
| 来源 | `bronze.tif_medallion_payments`（48,431 行，8 列，全部 VARCHAR） |
| 预计行数 | ~4.8 万 |
| 主键 | `payment_id`（BIGINT，代理键），`composite_key`（候选键） |
| 字段数 | 12 |

## 设计理由

### 为什么必须用代理键 + 复合键

Bronze 表的核心问题：**`License Number` 不唯一**（6,115 个唯一值 vs 48,431 行）。

原因分析：一个 Medallion 牌照（如 `5B50`）会收到多次 TIF 支付——每次三年检查通过后支付 $1,333（运营支付），以及可能的 WAV 改装支付（改装支付）。因此 `License Number` 是"一对多"而非"一对一"。

解决方案：
- 代理键 `payment_id`（BIGINT）作为主键
- `license_number + payment_date` 作为候选复合键（同一牌照同一天收到多笔支付的情况极其罕见）
- `is_duplicate_key` 标记复合键重复的异常行

### 为什么新增 `agent_number`

Bronze 源表有 `Agent Number` 字段，缺失率 47.6%。保留它的理由：
- 47.6% 缺失意味着 52.4% 有值——超过一半的数据可用
- Agent 是 Medallion 管理体系的关键实体，`agent_number` 是关联代理人/代理机构的唯一字段
- 缺失率高不代表字段无用，而是说明数据质量需要标记

### 为什么全部字段需要 VARCHAR→标准类型转换

与 `base_detail` 同理——CSV 导入的 Bronze 表全部字段为 VARCHAR：

| 字段 | 原类型 | 新类型 | 说明 |
|---|---|---|---|
| `License Number` | VARCHAR | VARCHAR | 保留文本 |
| `Agent Number` | VARCHAR | VARCHAR | 保留文本 |
| `Hackup Payment Amount` | VARCHAR | DECIMAL(12,2) | 金额 |
| `Operational Payment Amount` | VARCHAR | DECIMAL(12,2) | 金额 |
| `Total Payment Amount` | VARCHAR | DECIMAL(12,2) | 金额 |
| `Payment Date` | VARCHAR | DATE | 日期 |
| `Last Date Updated` | VARCHAR | DATE | 日期 |
| `Last Time Updated` | VARCHAR | VARCHAR | 保留文本 |

### 为什么 `last_time_updated` 保留 VARCHAR

与 `driver_detail` 同理——时间字段使用频率低，VARCHAR 不影响绝大多数查询。转换收益小而风险大（格式不统一可能导致转换失败）。

## 质量规则

- `composite_key` 出现重复时保留所有行，标记 `is_duplicate_key = TRUE`。
- `total_payment_amount` 应等于 `hackup_payment_amount + operational_payment_amount`（允许 ±$1 舍入误差）。
- `payment_date` 不能为 NULL。
- 金额字段 ≤ 0 时标记异常。

## 字段来源分类

| 字段 | 来源类型 | 来源字段/逻辑 |
|---|---|---|
| `payment_id` | derived | 自增代理键 |
| `license_number` | direct | `License Number` |
| `agent_number` | direct | `Agent Number` |
| `hackup_payment_amount` | standardized | `Hackup Payment Amount`（VARCHAR→DECIMAL(12,2)） |
| `operational_payment_amount` | standardized | `Operational Payment Amount`（VARCHAR→DECIMAL(12,2)） |
| `total_payment_amount` | standardized | `Total Payment Amount`（VARCHAR→DECIMAL(12,2)） |
| `payment_date` | standardized | `Payment Date`（VARCHAR→DATE） |
| `last_date_updated` | standardized | `Last Date Updated`（VARCHAR→DATE） |
| `last_time_updated` | direct | `Last Time Updated` |
| `composite_key` | derived | `license_number + '_' + payment_date` |
| `is_duplicate_key` | derived | 复合键重复检查 |
