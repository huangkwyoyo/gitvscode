# TianShu 权威契约变更建议：G3 日汇总表 → dim_date JOIN

**生成方**：TianShu-Text2SQL-Agent（只读消费方）
**接收方**：TianShu Dev Agent（契约权威修改方）
**日期**：2026-06-21
**状态**：待 TianShu Dev Agent 审批和修改

---

## 一、变更摘要

在 `contracts/sql_safety_policy.yml` 的 `allowed_joins` 中新增三条 G3 日汇总表到 dim_date 的 JOIN 路径。

当前契约缺失这些 JOIN，导致 Text2SQL Agent 在执行所有日汇总查询时被安全门禁拦截（fail-closed），无法回答最基本的日报问题。

---

## 二、业务理由

### 2.1 查询路径完整性

TianShu 安全策略要求日期过滤必须通过 `gold.dim_date` 完成：

```
rule: "date_filter_via_dim_date"
correct: "INNER JOIN gold.dim_date d ON d.date_key = t.pickup_date_key WHERE d.date BETWEEN ..."
incorrect: "WHERE pickup_date_key BETWEEN 20260101 AND 20260331"
```

G3 汇总表按天预聚合，其日期字段（如 `trip_date`、`issue_date`、`crash_date`）需要与 `gold.dim_date` 关联以获取可读日期字符串和统一日期过滤语义。

### 2.2 高频查询覆盖

以下是最常见的用户查询模式（占问数量 60%+）：

| 用户问题 | 主表 | 所需 JOIN |
|----------|------|-----------|
| "2026年1月每天有多少行程？" | gold.dws_daily_trip_summary | ↔ gold.dim_date |
| "2026年2月每天的停车罚单数量？" | gold.dws_daily_parking_summary | ↔ gold.dim_date |
| "2026年3月每天的事故数量？" | gold.dws_daily_crash_summary | ↔ gold.dim_date |

### 2.3 日期过滤统一性

G3 表的日期字段类型为整数 date_key（如 `20260101`），直接比较违反契约的 `date_filter_via_dim_date` 规则。通过 dim_date JOIN 转换为 `date BETWEEN '2026-01-01' AND '2026-01-31'` 是唯一合规路径。

---

## 三、JOIN 规范

### 3.1 建议新增条目

在 `sql_safety_policy.yml` → `table_reference_rules` → `join_whitelist` → `allowed_joins` 中新增：

```yaml
- "gold.dws_daily_trip_summary ↔ gold.dim_date (trip_date = date_key)"
- "gold.dws_daily_parking_summary ↔ gold.dim_date (issue_date = date_key)"
- "gold.dws_daily_crash_summary ↔ gold.dim_date (crash_date = date_key)"
```

### 3.2 JOIN 键映射

| G3 汇总表 | G3 日期列 | dim_date 键 | 基数 |
|-----------|----------|-------------|------|
| gold.dws_daily_trip_summary | trip_date | date_key | 1:1（每天一行） |
| gold.dws_daily_parking_summary | issue_date | date_key | 1:1（每天一行） |
| gold.dws_daily_crash_summary | crash_date | date_key | 1:1（每天一行） |

### 3.3 JOIN 类型

推荐 `INNER JOIN`：当 G3 表有数据时，对应的 dim_date 行必然存在（dim_date 覆盖 1997-2027）。

---

## 四、日期过滤语义

JOIN dim_date 后的标准 WHERE 子句：

```sql
-- 行程日汇总
SELECT d.date, SUM(t.trip_count) AS trip_count
FROM gold.dws_daily_trip_summary t
INNER JOIN gold.dim_date d ON d.date_key = t.trip_date
WHERE d.date BETWEEN '2026-01-01' AND '2026-01-31'
GROUP BY d.date ORDER BY d.date

-- 停车罚单日汇总
SELECT d.date, SUM(p.parking_violation_count) AS violation_count
FROM gold.dws_daily_parking_summary p
INNER JOIN gold.dim_date d ON d.date_key = p.issue_date
WHERE d.date BETWEEN '2026-02-01' AND '2026-02-28'
GROUP BY d.date ORDER BY d.date

-- 事故日汇总
SELECT d.date, SUM(c.crash_count) AS crash_count
FROM gold.dws_daily_crash_summary c
INNER JOIN gold.dim_date d ON d.date_key = c.crash_date
WHERE d.date BETWEEN '2026-03-01' AND '2026-03-31'
GROUP BY d.date ORDER BY d.date
```

---

## 五、风险评估

| 风险维度 | 评估 | 说明 |
|----------|------|------|
| 数据泄露 | 低 | dim_date 是公共维表，不含敏感数据 |
| 基数爆炸 | 低 | 三张表均为日粒度（每天一行），1:1 JOIN 不放大行数 |
| 性能 | 低 | dim_date 是小型维表（~11000 行），JOIN 成本极低 |
| 写操作 | 无 | 纯 SELECT 只读查询 |
| 跨层访问 | 无 | 三张表均为 Gold 层 |
| 事实表间 JOIN | 无 | 仅 G3 汇总表到 G0 公共维表 |

---

## 六、当前影响

在契约更新前，Text2SQL Agent 对以下场景 **fail-closed**（返回 clarification 而非执行）：

- 所有使用 G3 日汇总表的查询（约占查询量的 60%+）
- 具体包括：trip_count、parking_violation_count、crash_count、persons_killed、persons_injured 的日趋势查询

Agent 输出示例：
```
查询规划需要确认: [IR 主线] JOIN gold.dws_daily_trip_summary ↔ gold.dim_date 不在核准白名单中
```

---

## 七、契约变更后验证

契约更新后，Text2SQL Agent 将自动从更新后的契约加载白名单（无需代码修改），以下查询将恢复：

```bash
python -m pytest tests/test_mvp_agent.py -v -k "g3"
# 预期：全部 PASS
```

---

## 八、审批记录

| 角色 | 操作 | 日期 | 签名 |
|------|------|------|------|
| Text2SQL Agent | 提出变更建议 | 2026-06-21 | huangkwyoyo |
| TianShu Dev Agent | 待审批 | - | - |
| TianShu Dev Agent | 待修改 contracts/sql_safety_policy.yml | - | - |
| Harness | 待验证契约一致性 | - | - |

---

## 九、参考

- 权威契约：`../TianShu/contracts/sql_safety_policy.yml`
- 安全策略规则：`date_filter_via_dim_date`（必须通过 dim_date 做日期过滤）
- Text2SQL Agent 安全加载器：`src/safety_policy_loader.py`
- 相关修复 commit：移除 resolver.py 和 llm_pipeline.py 的硬编码 JOIN 白名单
