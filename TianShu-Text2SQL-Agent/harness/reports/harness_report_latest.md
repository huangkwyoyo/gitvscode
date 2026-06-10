# TianShu Text2SQL Agent Harness 报告

生成时间：2026-06-10 22:20:40

## 汇总

| 状态 | 数量 |
|------|------|
| PASS | 5 |
| FAIL | 0 |
| **总计** | **5** |

## 逐步详情

### ✅ SQL 只读安全门禁
- 状态: PASS
- 耗时: 0.06s
- 退出码: 0

```
============================================================
SQL 只读安全门禁
禁止关键字 (21): ALTER, ATTACH, CHECKPOINT, COPY, CREATE, DELETE, DETACH, DROP, EXPORT, GRANT, IMPORT, INSERT, INSTALL, LOAD, MERGE, PRAGMA, RENAME, REPLACE, REVOKE, TRUNCATE, UPDATE
============================================================
  [SKIP] 未找到包含 SQL 的评测问题文件

[OK] 只读安全检查通过（无待检查的 SQL）。

```

### ✅ IR 数据结构完整性
- 状态: PASS
- 耗时: 0.07s
- 退出码: 0

```
============================================================
IR 三层数据结构完整性门禁
============================================================

── src/ir.py 数据类检查 ──
  [PASS] QuestionIntent 实例化 + 序列化
         字段数=9, 包含 keys=['domain', 'intent_type', 'metrics', 'time_range', 'dimensions']...
  [PASS] QuestionIntent.validate()
         通过
  [PASS] QuestionIntent 歧义检测（needs_clarification=true）
         检测到 1 个问题
  [PASS] SQLPlan 实例化 + 序列化
         策略=g3_direct, 主表=gold.dws_daily_trip_summary
  [PASS] SQLPlan 降级原因检查（缺失 downgrade_reason）
         检测到 1 个问题
  [PASS] SQLResult 签名计算
         MD5=84ff789f34d8a324...
  [PASS] AgentResponse 完整链路序列化
         包含 keys=['question', 'intent', 'plan', 'result', 'chinese_answer', 'clarification_needed', 'clarification_message', 'refusal', 'refusal_reason', 'trace']

── evals/ 文件结构检查 ──
  [SKIP] evals 目录
         evals/ 目录中尚无 YAML 文件

  检查完成 — 通过: 7, 失败: 0

[OK] IR 数据结构完整性检查通过。

```

### ✅ 反问/拒绝策略完备性
- 状态: PASS
- 耗时: 0.06s
- 退出码: 0

```
============================================================
反问/拒绝策略完备性门禁
============================================================

── contracts/question_policy.yml 检查 ──
  [PASS] 可回答的问题域定义
         已定义 6 个问题域: ['traffic', 'violation', 'safety', 'supply', 'asset', 'spatial']
  [PASS] 必须反问的场景数
         已定义 5 种反问场景: {'ambiguous_region', 'missing_dimension', 'unregistered_metric', 'fuzzy_time', 'ambiguous_amount'}
  [PASS] 反问模板完备性
         全部反问规则都有模板
  [PASS] 必须拒绝的场景数
         已定义 4 种拒绝场景: {'bronze_direct', 'write_operation', 'metric_invention', 'out_of_scope'}
  [PASS] 拒绝模板完备性
         全部拒绝规则都有模板

── evals/ 策略评测文件检查 ──
  [SKIP] ambiguous_questions.yml
         文件尚未创建（待 Agent 实现后补充）
  [SKIP] unsafe_questions.yml
         文件尚未创建（待 Agent 实现后补充）

  检查完成 — 通过: 5, 失败: 0, 跳过: 2

[OK] 反问/拒绝策略完备性检查通过。

```

### ✅ 层级合规门禁
- 状态: PASS
- 耗时: 0.06s
- 退出码: 0

```
============================================================
层级合规门禁
规则: G3 > G2 > Silver > Bronze
============================================================

── 逐题检查 (0 题) ──

  检查完成 — 通过: 0, 警告: 0, 失败: 0

[OK] 无待检查的 SQL 语句。

```

### ✅ 指标注册合规门禁
- 状态: PASS
- 耗时: 0.06s
- 退出码: 0

```
============================================================
指标注册合规门禁
已注册指标数: 10
============================================================

── 逐题检查 (0 题) ──

  检查完成 — 通过: 0, 失败: 0, 跳过: 0

[OK] 无待检查的问题。

```
