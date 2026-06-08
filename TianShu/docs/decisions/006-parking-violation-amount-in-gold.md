# 006 — 停车罚单金额字段放在 Gold 层而非 Silver 层

## Status（状态）

Accepted

## Context（背景）

在 Silver 层规划初期，`parking_violation_detail` 的字段设计中出现了以下金额字段：

- `fine_amount`（罚款金额）
- `penalty_amount`（滞纳金）
- `interest_amount`（利息）
- `reduction_amount`（减免金额）
- `payment_amount`（支付金额）
- `amount_due`（欠款金额）

这些字段的出现是基于"停车罚单应该有罚款金额"的业务直觉。

然而，通过 `DESCRIBE bronze.parking_violations_all` 验证后发现：**Bronze 表 `parking_violations_all` 共 29 列，全部为 VARCHAR 类型，没有任何金额字段。** 这 6 个金额字段完全是 AI 根据业务常识"合理推断"出来的。

这是一个典型的**数据仓库 AI 合理幻觉**——从业务上看完全合理，从数据工程上看完全没有事实依据。

核心问题：**停车罚单的金额数据客观存在（官方数据字典 `Parking_Violations_Issued_Data_Dictionary.xlsx` 的 Violation Codes sheet 中有各违章代码对应的罚款标准），但它不在 Bronze 表中。这个金额数据应该放在哪一层？**

## Decision（决策）

**Silver 层 `parking_violation_detail` 不包含任何金额字段。金额数据在 Gold 层通过 `violation_code` 关联 `dim_violation_type`（来自官方 xlsx）获取。**

### 具体方案

```text
Silver 层（silver.parking_violation_detail）：
  - 仅保留 Bronze 中实际存在的 29 列（标准化后）
  - 不新增任何金额字段
  - 保留 violation_code（违章代码，VARCHAR），作为关联键

Gold 层（gold.dim_violation_type）：
  - 来源：官方数据字典 xlsx 的 Violation Codes sheet
  - 字段：violation_code, violation_description, fine_amount, penalty_amount, ...
  - 这是一个标准的维表，存储违章代码对应的罚款标准

Gold 层（gold.fact_parking_violation）：
  - 通过 silver.parking_violation_detail.violation_code
    JOIN gold.dim_violation_type.violation_code
  - 获取每次违章对应的标准罚款金额
```

### 决策依据

1. **Silver 的铁律**："Silver 字段必须能追溯到 Bronze 字段"。Bronze 没有金额字段，Silver 就不能凭空出现金额字段
2. **金额数据的性质**：官方 xlsx 中的罚款标准是"违章代码 → 标准罚款金额"的映射关系，这是**参考数据（Reference Data）**，不是 Bronze 原始数据
3. **Gold 层的职责**：Gold 层负责业务建模和指标计算，关联外部参考数据是 Gold 的合法操作
4. **可追溯性**：如果金额在 Gold 层，下游用户能明确知道"这个金额来自官方违章代码字典，不是原始罚单数据"——这是正确的语义

## Alternatives（替代方案）

| 方案 | 优势 | 劣势 | 排除原因 |
|---|---|---|---|
| **Silver 层直接加金额字段** | 查询方便，一张表搞定 | Silver 字段无法追溯到 Bronze，违反了零幻觉原则 | 违反 Silver 层铁律 |
| **金额字段放在 Silver 但标记为"派生"** | 留在 Silver，用标记区分 | 派生字段的定义模糊——罚款标准是外部参考数据，不是从 Bronze 字段计算出来的 | "派生"的前提是有来源字段，这里没有 |
| **完全不用官方 xlsx 的金额** | 最保守，零风险 | 放弃可用的参考数据，罚单分析缺少核心指标 | 过度保守——外部参考数据在 Gold 层使用是合理的 |
| **金额放在 Gold 层通过 violation_code JOIN** ✅ | 层级语义正确，可追溯，不违反零幻觉原则 | 查询时需要 JOIN，但 Gold 层的星型模型设计本身就需要 JOIN | — |

## Consequences（后果）

### 正面影响

- 这个决策直接催生了"Silver 字段来源标注"规范——每个字段必须标注 `来源类型`（Bronze 字段 / 派生 / 外部参考 / 常量）
- 构成了 `check_silver_dictionary.py` 的核心检查逻辑——无来源的金额字段直接报错
- 成为"合理幻觉"的典型案例，写入 `docs/memory/经验复盘.md`，用于教育后续 Agent

### 负面影响 / 代价

- 查询罚单金额时需要通过 Gold 层 JOIN，不能直接从 Silver 获取
- 如果官方 xlsx 的 Violation Codes 发生变更，需要重新生成 `dim_violation_type`
- 官方 xlsx 的罚款标准是"标准金额"，实际罚单可能有减免、滞纳金等调整——这些调整数据在 Bronze 中不存在，当前无法获取。这意味着 Gold 层的金额只是"标准罚款金额"而非"实际支付金额"，需要在指标定义中明确标注

### 重新评估条件

1. **NYC Open Data 发布了包含实际罚单金额的数据集**：将其导入 Bronze，然后在 Silver 层新增标准化的金额字段
2. **业务需求强烈要求 Silver 层有金额**：重新评估是否将 `dim_violation_type` 作为 Silver 维表（而非 Gold 维表），但这仍不改变"金额不在 parking_violation_detail 的 Bronze 来源字段中"的事实
3. **发现停车罚单数据中有隐藏的金额字段**（如从其他字段解析）：需经过 `DESCRIBE` 验证后才能加入 Silver

---

## 附：此决策触发的 Harness 规则

此决策直接生成了以下可执行检查：

```text
scripts/quality/check_silver_dictionary.py：
  - 扫描所有 Silver 字段，检查是否有来源字段
  - 如果字段名包含 amount/fine/payment/penalty/fee，必须有来源和口径说明
  - 如果 Silver 数据字典出现无来源金额字段，检查必须失败

docs/warehouse/silver/AGENTS.md：
  - "parking_violations_all 当前没有金额字段，不得在 silver.parking_violation_detail
     中直接新增实收、应收、罚款、滞纳金等来源型金额字段"

tests/test_silver_dictionary.py：
  - test_no_orphan_amount_fields：验证所有金额字段都有来源
```
