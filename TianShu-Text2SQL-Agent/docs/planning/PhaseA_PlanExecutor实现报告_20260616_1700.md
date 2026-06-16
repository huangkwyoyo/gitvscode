# Phase A：PlanExecutor 实现报告

> 日期：2026-06-16 | 测试：99/99 通过，零回归

## 修改文件

| 文件 | 变更类型 | 说明 |
|------|:------:|------|
| `src/ir.py` | 修改 | 新增 `ExecutionTrace` dataclass（10 字段）；`UnifiedResponse` 新增可选 `execution_trace` 字段 |
| `src/plan_executor.py` | **新建** | PlanExecutor 类，含 `execute_one()` 和 `execute_many_serial()` |
| `src/agent.py` | 修改 | 执行逻辑抽离到 PlanExecutor；移除 `sql_plan_to_sql`/`validate_sql_safety` 直接导入；移除 `forbidden_kw` 变量 |
| `tests/test_plan_executor.py` | **新建** | 20 个测试，覆盖单计划/多计划/安全独立性/序列化/E2E 回归 |

## 新增执行边界

### PlanExecutor（`src/plan_executor.py`）

稳定的执行边界，将 SQL 生成、安全校验、数据库执行封装在单一类中：

```
输入: SQLPlan 或 list[UnifiedResponse]
  → sql_plan_to_sql(plan)
  → validate_sql_safety(sql)
  → resolver.execute_sql(sql)
输出: SQLResult 或 list[UnifiedResponse]（已回填 result + execution_trace）
```

#### `execute_one(plan: SQLPlan, plan_index: int = 1) -> SQLResult`

- 单计划完整执行链路
- 安全校验失败 → 返回带 error 的 SQLResult，不抛异常
- 离线模式 / 无 resolver → 阻断执行，记录 trace
- 每次调用更新 `executor.last_trace`

#### `execute_many_serial(responses: list[UnifiedResponse]) -> list[UnifiedResponse]`

- 按 index 顺序逐个执行，不做重排
- 每个 UnifiedResponse 的 `result` 和 `execution_trace` 原地回填
- `plan=None` 或 `strategy=NEED_CLARIFICATION` → 跳过但记录 trace
- 一个 plan 失败不影响后续 plan 执行

### ExecutionTrace（`src/ir.py`）

每个子计划执行后产生的轻量追踪记录：

| 字段 | 类型 | 说明 |
|------|------|------|
| `plan_index` | int | 计划序号（从 1 开始） |
| `strategy` | str | 执行策略（如 "g3_direct"） |
| `primary_table` | str | 主数据来源表 |
| `generated_sql` | str | 生成的 SQL 文本 |
| `safety_check_passed` | bool | 安全校验是否通过 |
| `row_count` | int | 返回行数 |
| `error_message` | str | 错误信息（空字符串表示无错误） |
| `execution_status` | str | pending / success / failed |
| `execution_time_ms` | float | 执行耗时（毫秒） |

## 保持不变（确认无回归）

- ✅ SQL 生成链路：`sql_plan_to_sql()` 未被修改
- ✅ SQL 安全校验：`validate_sql_safety()` 未被修改，仍在 PlanExecutor 中调用
- ✅ DuckDB read_only：连接模式未被修改
- ✅ 单计划响应结构：`AgentResponse.plan` / `result` / `chinese_answer` 行为不变
- ✅ 多计划响应结构：`AgentResponse.plans` / `is_multi_plan` 行为不变
- ✅ G3/G2 规划逻辑：`_plan_query_rule()` / `_build_g2_plan()` 未被修改
- ✅ 单指标路径：`ask()` 中单指标行为不变
- ✅ 同表多指标路径：合并为单 SQL 的逻辑不变
- ✅ 跨表多计划路径：SubIntent 拆分 + 多计划生成逻辑不变

## 测试覆盖

### PlanExecutor 单元测试（15 个）

| 测试类 | 测试数 | 覆盖内容 |
|--------|:-----:|---------|
| `TestSinglePlanExecution` | 6 | 单计划执行、trace 记录、安全失败、离线阻断、无 resolver 阻断、plan_index 传递 |
| `TestMultiPlanSerialExecution` | 5 | 结果回填、trace 回填、顺序保持、跳过空 plan、跳过 NEED_CLARIFICATION |
| `TestSafetyCheckIndependence` | 2 | 第二个 plan 失败不影响第一个 trace、两个 plan 生成不同 SQL |
| `TestExecutionTraceSerialization` | 2 | to_dict 序列化、默认值 |

### E2E 回归测试（5 个）

| 测试 | 覆盖内容 |
|------|---------|
| `test_single_metric_path_uses_executor` | 单指标 → PlanExecutor 参与 → 结果正常 |
| `test_same_table_multi_metric_path_uses_executor` | 同表多指标 → PlanExecutor → 合并 SQL 正常 |
| `test_cross_table_multi_plan_uses_executor` | 跨表多计划 → execute_many_serial → 每个 result 不为空 |
| `test_cross_table_multi_plan_trace_fields` | 每个子计划的 ExecutionTrace 字段完整 |
| `test_all_existing_tests_still_pass` | 单指标/同表多指标/跨表多计划/反问/拒绝 全路径验证 |

### 回归测试套件（99 个全部通过）

```bash
pytest tests/test_mvp_agent.py tests/test_metric_resolver.py \
      tests/test_metric_catalog.py tests/test_ir.py \
      tests/test_plan_executor.py -v
# 99 passed in 3.84s
```

## 未实现内容（按 Phase A 约束）

| 功能 | 状态 | 说明 |
|------|:----:|------|
| ThreadPoolExecutor 并行 | ❌ 不实现 | Phase A 明确排除，留待 Phase 3A |
| DuckDB 多连接并发 | ❌ 不实现 | Phase A 明确排除 |
| LLM 结果融合 | ❌ 不实现 | Phase A 明确排除，留待 Phase 3B |
| date merge | ❌ 不实现 | Phase A 明确排除，留待 Phase 3C |
| 图表生成 | ❌ 不实现 | Phase A 明确排除 |
| 跨域因果解释 | ❌ 不实现 | Phase A 明确排除 |

## agent.py 改造摘要

**删除的代码**（约 60 行）：
- 单计划路径的 `sql_plan_to_sql()` → `validate_sql_safety()` → `resolver.execute_sql()` 内联逻辑
- 多计划路径的 for 循环执行逻辑（SQL 生成、安全校验、离线检查、数据库执行）
- `forbidden_kw` 预加载变量

**新增的代码**（约 15 行）：
- `_get_executor()` 懒初始化方法
- 单计划路径：`executor.execute_one(plan)` + trace 检查
- 多计划路径：`executor.execute_many_serial(unified_responses)` + trace 日志

**净减少 ~45 行**，agent.py 主循环更简洁，执行细节完全封装在 PlanExecutor 中。
