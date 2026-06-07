# silver.driver_application_detail（司机申请明细标准表）

## 表概览

| 属性 | 值 |
|---|---|
| 英文表名 | `silver.driver_application_detail` |
| 中文表名 | 司机申请明细标准表 |
| 数据域 | 监管合规域 |
| 数据角色 | 事实表（Fact） |
| 批次 | P1（第二批） |
| 来源 | `bronze.new_driver_applications`（4,076 行，12 列，全部 VARCHAR） |
| 预计行数 | 4,076 |
| 主键 | `application_id`（BIGINT，代理键），`app_no`（候选键） |
| 字段数 | 14 |

## 设计理由

### 为什么新增 `application_id` 代理键

- `App No` 虽是唯一自然键，但格式为 VARCHAR（如 `HDR001234`），JOIN 效率不如 BIGINT。
- 代理键统一了 Silver 层所有事实表的主键格式（全部 BIGINT），下游 Gold 表写法一致。
- `app_no` 保留为候选键，加唯一索引。

### 为什么展开全部 12 个审批步骤字段

Bronze 表的 12 个字段代表 TLC 司机审批流程的 12 个步骤。每个步骤都是独立的状态机：

```
App Date → Status → FRU Interview → Drug Test → WAV Course
→ Defensive Driving → Driver Exam → Medical Clearance
→ Other Requirements → Last Updated
```

这些字段**不是辅助信息**，而是核心业务数据：

- `status`（审批状态）：司机申请通过率分析的核心字段
- `drug_test`（药检）：合规监管的关键指标
- `wav_course`（WAV培训）：WAV 车辆供给的前置条件
- `driver_exam`（司机考试）：司机供给质量的衡量标准

如果只保留 `status` 而丢弃中间步骤，就无法分析"哪个环节卡住了最多申请人"。

### 为什么 `app_date` 和 `last_updated` 转为 DATE

- Bronze 层全部 VARCHAR，日期字段（`App Date`、`Last Updated`）需要转换为标准 DATE 类型，才能做时间序列分析（"每月有多少新申请"）。
- 14 个字段中只有 2 个需要类型转换，其余保留 VARCHAR（它们存储的是状态文本，不是数字或日期）。

### 为什么字段名做了简化

Bronze 层字段名包含空格（如 `App No`、`Drug Test`、`FRU Interview Scheduled`），在 SQL 中需要引号包裹。Silver 层统一为 snake_case 小写+下划线，提升可写性和可读性。

## 质量规则

- `app_no` 不允许为空，候选键唯一索引。
- `app_date` 不能为 NULL（每个申请必须有日期）。
- `status` 不预先写死枚举值。应以 Bronze 层实际 DISTINCT 值为准生成状态字典（当前实际为 5 种：`Incomplete`、`Approved - License Issued`、`Denied`、`Under Review`、`Pending Fitness Interview`）。后续若源数据新增状态，Silver 层不丢数据，仅标记为 `unexpected_status = TRUE`。

## 字段来源分类

| 字段 | 来源类型 | 来源字段/逻辑 |
|---|---|---|
| `application_id` | derived | 自增代理键 |
| `app_no` | direct | `App No` |
| `application_type` | direct | `Type` |
| `app_date` | standardized | `App Date`（VARCHAR→DATE） |
| `status` | direct | `Status`（以 SELECT DISTINCT 实际值为准，不硬编码） |
| `fru_interview_scheduled` | direct | `FRU Interview Scheduled` |
| `drug_test` | direct | `Drug Test` |
| `wav_course` | direct | `WAV Course` |
| `defensive_driving` | direct | `Defensive Driving` |
| `driver_exam` | direct | `Driver Exam` |
| `medical_clearance_form` | direct | `Medical Clearance Form` |
| `other_requirements` | direct | `Other Requirements` |
| `last_updated` | standardized | `Last Updated`（VARCHAR→DATE） |
| `source_table` | derived | 常量 'new_driver_applications' |
