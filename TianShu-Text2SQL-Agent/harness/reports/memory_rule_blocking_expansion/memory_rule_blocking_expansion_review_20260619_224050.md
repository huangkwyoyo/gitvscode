# Memory Rule Blocking Expansion Readiness Review

**Run ID:** `BRE-20260619T144049`
**时间:** 2026-06-19T14:40:50.005004+00:00
**规则文件:** D:\Program Files\gitvscode\TianShu-Text2SQL-Agent\docs\memory\memory_rules.yml

## Summary

| 指标 | 值 |
|------|-----|
| 总规则数 | 21 |
| 当前 active+blocking | 1 (TA-R018) |
| TA-R018 稳定 | ✅ |
| pre-commit blocking 稳定 | ✅ |
| ready_for_fast_gate_blocking | 3 |
| needs_more_observation | 7 |
| missing_assets | 9 |
| keep_non_blocking | 2 |
| rejected | 0 |

## Current Blocking Baseline

- **active+blocking 规则:** TA-R018
- **TA-R018 稳定性:** Step 24 验证 — 11 次 blocking 模式观察，全部 exit 0，误报 0
- **pre-commit blocking 状态:** Step 23 已启用，Step 24 稳定运行

## Candidate Rules Reviewed

| rule_id | status | blocking | recommendation | reason |
|---------|--------|----------|----------------|--------|
| TA-R010 | proposed | False | 🔵 needs_more_observation | 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking |
| TA-R011 | proposed | False | 🔵 needs_more_observation | 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking |
| TA-R012 | proposed | False | 🔵 needs_more_observation | 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking |
| TA-R013 | proposed | False | 🔵 needs_more_observation | 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking |
| TA-R014 | proposed | False | 🔵 needs_more_observation | 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking |
| TA-R015 | proposed | False | 🔵 needs_more_observation | 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking |
| TA-R016 | proposed | False | 🔴 missing_evals | required_evals 为空，notes 标注待补: UNSTABLE 不触发任何阻断。Provider 稳定性指... |
| TA-R017 | proposed | False | 🔵 needs_more_observation | 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking |
| TA-R018 | active | True | ⚪ keep_non_blocking | 已是 active+blocking=true，当前 baseline，无需变更 |
| TA-R019 | proposed | False | 🟢 ready_for_fast_gate_blocking | 资产齐全（checks+tests+evals），安全关键，误报风险低。建议先进入 fast gate blocking... |
| TA-R020 | proposed | False | 🟢 ready_for_fast_gate_blocking | 资产齐全（checks+tests+evals），安全关键，误报风险低。建议先进入 fast gate blocking... |
| TA-R021 | proposed | False | 🔴 missing_evals | required_evals 为空，notes 标注待补: ResultSummary 字段变更需评估对 result_... |
| TA-R022 | proposed | False | 🔴 missing_evals | required_evals 为空，notes 标注待补: merge 条件仅限于 date 列对齐 + grain 一... |
| TA-R023 | proposed | False | 🟢 ready_for_fast_gate_blocking | 资产齐全（checks+tests+evals），安全关键，误报风险低。建议先进入 fast gate blocking... |
| TA-R024 | proposed | False | 🔴 missing_evals | required_evals 为空，notes 标注待补: ChartSpec 仅生成 JSON 可序列化的规则图表规格... |
| TA-R025 | proposed | False | 🔴 missing_evals | required_evals 为空，notes 标注待补: 旧版 executor.py 仅用于兼容历史路径，新功能必须... |
| TA-R026 | proposed | False | 🔴 missing_evals | required_evals 为空，notes 标注待补: Meta 规则：新增 check 脚本时必须同步更新对应规则... |
| TA-R027 | proposed | False | 🔴 missing_evals | required_evals 为空，notes 标注待补: 基线变更需评估对 UNSTABLE 与 FAIL 判定边界的... |
| TA-R028 | proposed | False | 🔴 missing_evals | required_evals 为空，notes 标注待补: Meta 规则：新增 eval 用例时必须同步更新对应规则的... |
| TA-R029 | proposed | False | ⚪ keep_non_blocking | 误报风险为 high（规则依赖文档/注释/注册表变更检测），不适合进入 blocking |
| TA-R030 | proposed | False | 🔴 missing_evals | required_evals 为空，notes 标注待补: 修改生成脚本后必须验证输出 Markdown 结构不退化、r... |

## Ready Candidates

### TA-R019: PlanExecutor 安全链路不可绕过——read_only、离线阻断、validate_sql_safety、execution trace

- **推荐:** ready_for_fast_gate_blocking
- **原因:** 资产齐全（checks+tests+evals），安全关键，误报风险低。建议先进入 fast gate blocking 观察，稳定后晋升 active+blocking=true
- **checks:** harness/checks/check_plan_executor_safety.py
- **tests:** tests/test_plan_executor.py
- **evals:** evals/e2e_cases.yml
- **误报风险:** low
- **安全关键:** ✅

### TA-R020: ExecutionStrategy 并发安全边界——默认串行、DuckDB 连接不跨线程共享、每个 plan 独立安全校验

- **推荐:** ready_for_fast_gate_blocking
- **原因:** 资产齐全（checks+tests+evals），安全关键，误报风险低。建议先进入 fast gate blocking 观察，稳定后晋升 active+blocking=true
- **checks:** harness/checks/check_execution_strategy_safety.py
- **tests:** tests/test_execution_strategy.py
- **evals:** evals/e2e_cases.yml
- **误报风险:** low
- **安全关键:** ✅

### TA-R023: CrossDomainPolicy 不得削弱跨域拒绝和因果边界——unknown 反问、traffic+safety 禁止因果、standard_fine_total 非实际收入

- **推荐:** ready_for_fast_gate_blocking
- **原因:** 资产齐全（checks+tests+evals），安全关键，误报风险低。建议先进入 fast gate blocking 观察，稳定后晋升 active+blocking=true
- **checks:** harness/checks/check_cross_domain_policy.py
- **tests:** tests/test_cross_domain_policy.py
- **evals:** evals/e2e_cases.yml
- **误报风险:** low
- **安全关键:** ✅

## Needs More Observation

- **TA-R010**: 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking
- **TA-R011**: 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking
- **TA-R012**: 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking
- **TA-R013**: 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking
- **TA-R014**: 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking
- **TA-R015**: 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking
- **TA-R017**: 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking

## Missing Assets

| rule_id | 缺失 |
|---------|------|
| TA-R016 | evals |
| TA-R021 | evals |
| TA-R022 | evals |
| TA-R024 | evals |
| TA-R025 | evals |
| TA-R026 | evals |
| TA-R027 | evals |
| TA-R028 | evals |
| TA-R030 | evals |

## False Positive Risks

| rule_id | risk | note |
|---------|------|------|
| TA-R010 | medium | 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking |
| TA-R011 | medium | 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking |
| TA-R012 | medium | 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking |
| TA-R013 | medium | 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking |
| TA-R014 | medium | 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking |
| TA-R015 | medium | 资产齐全，但需要先晋升 active 并经过 fast gate 观察期后才能考虑 blocking |
| TA-R016 | medium | required_evals 为空，notes 标注待补: UNSTABLE 不触发任何阻断。Pro |
| TA-R018 | medium | 已是 active+blocking=true，当前 baseline，无需变更 |
| TA-R024 | medium | required_evals 为空，notes 标注待补: ChartSpec 仅生成 JSON 可 |
| TA-R026 | high | required_evals 为空，notes 标注待补: Meta 规则：新增 check 脚本时 |
| TA-R027 | high | required_evals 为空，notes 标注待补: 基线变更需评估对 UNSTABLE 与  |
| TA-R028 | high | required_evals 为空，notes 标注待补: Meta 规则：新增 eval 用例时必 |
| TA-R029 | high | 误报风险为 high（规则依赖文档/注释/注册表变更检测），不适合进入 blocking |
| TA-R030 | high | required_evals 为空，notes 标注待补: 修改生成脚本后必须验证输出 Markdo |

## Rollback Readiness

- **TA-R019**: rollback plan 缺失 ❌
- **TA-R020**: rollback plan 缺失 ❌
- **TA-R023**: rollback plan 缺失 ❌

通用回滚方式：将对应规则的 blocking 从 true 改回 false，无需修改业务代码。

## Recommendation

共 3 条规则可进入 fast gate blocking 观察：
1. **TA-R019** — PlanExecutor 安全链路不可绕过——read_only、离线阻断、validate_sql_safety、execution trace
1. **TA-R020** — ExecutionStrategy 并发安全边界——默认串行、DuckDB 连接不跨线程共享、每个 plan 独立安全校验
1. **TA-R023** — CrossDomainPolicy 不得削弱跨域拒绝和因果边界——unknown 反问、traffic+safety 禁止因果、standard_fine_total 非实际收入

建议进入 Step 26：针对上述候选规则做人工审批和 fast gate blocking apply。
在 fast gate blocking 稳定观察 ≥7 天后，再评估 pre-commit blocking。

## Not Applied Automatically

本轮明确未做的操作：

- ❌ 未修改 memory_rules.yml
- ❌ 未将任何规则 blocking 改为 true
- ❌ 未将 proposed 改为 active
- ❌ 未修改 docs/memory/*
- ❌ 未修改 TA-R018
- ❌ 未修改 .githooks/pre-commit
- ❌ 未修改 pre-commit blocking 行为
- ❌ 未新增 CI 阻断
- ❌ 未修改业务代码
- ❌ 未调用真实 LLM
- ❌ 未生成 latest
- ❌ 未批量扩大阻断范围

---
*Step 25 自动审查 — 2026-06-19T14:40:50.005004+00:00*