# silver.parking_violation_detail（停车罚单明细标准表）

## 表概览

| 属性 | 值 |
|---|---|
| 英文表名 | `silver.parking_violation_detail` |
| 中文表名 | 停车罚单明细标准表 |
| 数据域 | 监管合规域 |
| 数据角色 | 事实表（Fact） |
| 批次 | P2（第三批） |
| 来源 | `bronze.parking_violations_all`（9,582,412 行，29 列，全部 VARCHAR） |
| 预计行数 | 958 万 |
| 主键 | `violation_id`（BIGINT，代理键），`summons_number`（候选键） |
| 字段数 | 32（29 源字段 + 1 代理键 + 2 质量标记） |

## 设计理由

### 为什么保留全部 29 个源字段（而非精简）

停车罚单数据的使用场景多样：
- **地理分析**：`street_name`、`violation_county`、`violation_precinct`、`feet_from_curb`
- **法律分析**：`law_section`、`sub_division`、`violation_legal_code`
- **执法分析**：`issuing_agency`、`issuer_code`、`issuer_precinct`
- **车辆分析**：`plate_id`、`plate_type`、`vehicle_body_type`、`vehicle_color`

这些字段在 Bronze 层全部为 VARCHAR，在 Silver 层转为标准类型（`issue_date`→DATE、`vehicle_year`→INTEGER、`fiscal_year`→INTEGER）。没有理由丢弃任何一个。

### 为什么没有金额字段

**Bronze 层 `parking_violations_all` 不包含任何金额字段**。实际 29 列中无 `fine_amount`、`penalty_amount`、`interest_amount` 等罚款金额数据。

金额数据的获取方式：

```text
Silver 层：保留 violation_code（违章代码）
    ↓
Gold 层：JOIN dim_violation_type（违章类型维表）
    ↓
dim_violation_type 的金额信息来源于：
  D:\ProgramData\Datawarehouse\纽约市城市交通\2026财年纽约停车违章罚单开具情况\Parking_Violations_Issued_Data_Dictionary.xlsx
  → Violation Codes sheet（含每种违章代码的标准罚款金额）
```

这是典型的"代码+字典"分离模式——事实表存代码，维表存代码对应的属性（包括金额）。

### 为什么 `violation_time` 保留 VARCHAR

Bronze 层的 `violation_time` 格式不统一（有的带 AM/PM，有的用 24h 制，有的只有时没有分）。强制转为 TIME 类型会导致大量转换失败。保留 VARCHAR 比丢失数据更安全。

### 为什么 `feet_from_curb` 保留 VARCHAR

该字段虽然语义上是数字（英尺），但 Bronze 层数据包含非数字值（如"0 FT"、"AT CURB"等文字描述）。强制转为 INTEGER 会丢失这些信息。

## 类型转换清单

| 字段 | 原类型 | 新类型 | 说明 |
|---|---|---|---|
| `issue_date` | VARCHAR | DATE | 开票日期 |
| `vehicle_year` | VARCHAR | INTEGER | 违章车辆年份 |
| `fiscal_year` | VARCHAR | INTEGER | NYC 财年 |
| `vehicle_expiration_date` | VARCHAR | DATE | 车辆注册到期日 |
| 其余 25 个字段 | VARCHAR | VARCHAR | 保留文本类型 |

## 质量规则

- `summons_number` 需验证唯一性（Bronze 层已初步校验唯一，Silver 层二次确认）。
- `issue_date` 不在 2025-07-01 ~ 2026-06-30（2026 财年）范围内时标记。
- `violation_code` 不允许为空（否则无法关联到 Gold 层的违章类型维表获取金额）。
- `is_duplicate_summons = TRUE` 的行不丢弃，由下游决定去重策略。

## 字段来源分类

| 字段 | 来源类型 | 来源字段/逻辑 |
|---|---|---|
| `violation_id` | derived | 自增代理键 |
| `summons_number` | direct | `summons_number` |
| `plate_id` | direct | `plate_id` |
| `registration_state` | direct | `registration_state` |
| `plate_type` | direct | `plate_type` |
| `issue_date` | standardized | `issue_date`（VARCHAR→DATE） |
| `violation_code` | direct | `violation_code`（金额需在Gold层通过此代码关联dim_violation_type） |
| `vehicle_body_type` | direct | `vehicle_body_type` |
| `vehicle_make` | direct | `vehicle_make` |
| `issuing_agency` | direct | `issuing_agency` |
| `street_code1` | direct | `street_code1` |
| `street_code2` | direct | `street_code2` |
| `street_code3` | direct | `street_code3` |
| `vehicle_expiration_date` | standardized | `vehicle_expiration_date`（VARCHAR→DATE） |
| `violation_precinct` | direct | `violation_precinct` |
| `issuer_precinct` | direct | `issuer_precinct` |
| `issuer_code` | direct | `issuer_code` |
| `violation_time` | direct | `violation_time`（保留VARCHAR，格式不统一） |
| `violation_county` | direct | `violation_county` |
| `street_name` | direct | `street_name` |
| `intersecting_street` | direct | `intersecting_street` |
| `date_first_observed` | direct | `date_first_observed` |
| `law_section` | direct | `law_section` |
| `sub_division` | direct | `sub_division` |
| `violation_legal_code` | direct | `violation_legal_code` |
| `vehicle_color` | direct | `vehicle_color` |
| `vehicle_year` | standardized | `vehicle_year`（VARCHAR→INTEGER） |
| `feet_from_curb` | direct | `feet_from_curb`（保留VARCHAR，含非数字值） |
| `violation_description` | direct | `violation_description` |
| `fiscal_year` | standardized | `fiscal_year`（VARCHAR→INTEGER） |
| `is_duplicate_summons` | derived | summons_number重复检查 |
| `source_row_hash` | derived | MD5溯源 |

> **重要**：Bronze 层 parking_violations_all 无金额字段。本表不含 fine_amount、penalty_amount 等来源型金额。罚款金额需在 Gold 层通过 violation_code 关联 dim_violation_type（数据来源：官方 xlsx Violation Codes sheet）获取。
