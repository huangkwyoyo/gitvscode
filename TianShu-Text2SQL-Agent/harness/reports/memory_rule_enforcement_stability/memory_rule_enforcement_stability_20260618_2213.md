# Memory Rule Enforcement Stability Report

## Summary

Step 19 按 C 类边界执行。当前 `main` 的实际观察提交为 `d78166c`，任务给定的 Step 18b 提交 `0c7f609` 是其祖先。三次完整离线 fast gate 全部 PASS；TA-R018 三次均为 `passed`，未出现误报，blocking failures 均为 0。

负例测试证明：`active + blocking=true + required_check failed` 会产生 `blocking_failures=1`、`exit_code_should_fail=true`，将原本全通过的 fast gate 改为 FAIL，CLI 返回 1。

错误信息已补齐可操作字段，不改变规则语义、分类或 exit code 判定。观察到一项与 TA-R018 无关的稳定非阻断 warning：TA-R021 的 `harness/checks/check_result_summary_safety.py` 未匹配到 check result。

## Baseline

- branch: `main`
- observed commit: `d78166c`
- Step 18b commit: `0c7f609`（当前 HEAD 的祖先）
- fast gate mode: 完整离线检查，5 项
- active blocking rules: 1（TA-R018）

## Normal Run Stability

| run | timestamp | exit_code | TA-R018 result | blocking_failures | warnings | passed |
|---|---|---:|---|---:|---:|---|
| 1 | 2026-06-18T14:07:54.797115Z | 0 | passed | 0 | 1 | yes |
| 2 | 2026-06-18T14:09:09.176956Z | 0 | passed | 0 | 1 | yes |
| 3 | 2026-06-18T14:10:24.153564Z | 0 | passed | 0 | 1 | yes |

三次运行的 commit、规则级别、TA-R018 结果、blocking failures 和 warnings 完全一致。TA-R018 未误报，enforcement 未影响正常路径 exit code。

## Negative Blocking Verification

测试 fixture 仅模拟 TA-R018 的 `harness/checks/check_result_fusion_safety.py` 返回 FAIL/exit code 1，不修改真实 TA-R018 或真实检查脚本。结果如下：

```text
active + blocking=true + required_check failed
  -> enforcement_level=blocking_error
  -> rule result=FAIL
  -> blocking_failures=1
  -> exit_code_should_fail=true
  -> fast gate overall=FAIL
  -> CLI exit code=1
```

集成证据：`tests/test_fast_gate.py::test_active_blocking_failure_makes_fast_gate_exit_nonzero`。

## Failure Message Quality

阻断结果及控制台/Markdown 输出已验证包含：

- rule_id: TA-R018
- title
- failed required_check
- failure message（check name、FAIL、exit code）
- rollback plan
- suggested fix
- `enforcement_level=blocking_error`

本轮仅增强错误诊断，不修改 enforcement 分类、规则状态、blocking 值或 fast gate 判定范围。

## Rollback Readiness

Rollback plan：将 `memory_rules.yml` 中 TA-R018 的 `blocking` 从 `true` 人工改回 `false`，即可恢复非阻断模式。该操作只涉及规则注册表，不需要修改业务代码。本轮未实际执行 rollback，也未修改 `memory_rules.yml`。

## False Positive Risk

三次正常运行均未发现 TA-R018 假阳性，说明当前提交和当前环境下结果稳定。风险仍有限：观察窗口只有三次、单一 commit、单一 Windows/Python 环境，不能外推为长期或跨环境稳定性。

TA-R021 的 warning 连续三次出现，但它是 proposed 规则且不影响 exit code；应作为后续独立观察项，不应在 Step 19 扩大阻断范围。

## Boundaries

- 未修改 `docs/memory/*`
- 未修改 `docs/memory/memory_rules.yml`
- 未修改 TA-R018
- 未修改或接入 pre-commit
- 未调用真实 LLM
- 未修改业务代码
- 未生成 stability `latest`
- 未新增 active/blocking 规则

边界例外：执行要求的完整 fast gate 时，现有测试子进程调用 `run_fast_gate.py` 未传 `--report-dir`，因此改写了被 git ignore 的 `harness/reports/fast_gate_latest.json` 和 `.md`。顶层三次运行均使用独立临时目录并已删除，但运行前未保存原文件字节，无法按原 SHA-256 恢复。这是既有测试隔离问题，本轮未扩大范围修复。

## Test Results

- `python -m pytest tests/test_memory_rule_enforcement.py tests/test_fast_gate.py -q`: 92 passed
- `python -m pytest tests -k "memory_rule_enforcement or fast_gate" -q`: 141 passed, 1 skipped, 1111 deselected
- `python -m pytest tests -k "memory or fast_gate" -q`: 501 passed, 1 skipped, 751 deselected
- 负例 fast gate exit 测试：1 passed
- 完整 fast gate：3/3 PASS

## Recommendation

进入 Step 20：只设计 pre-commit warn 模式，不进入 blocking。将现有测试对子进程 report-dir 隔离不足的问题作为独立项跟踪，不在 Step 19 扩大修改范围。
