# Phase B2：Date Merge 实现报告

> 日期：2026-06-16 | 测试：159/159 通过，零回归

## 修改文件

| 文件 | 变更类型 | 说明 |
|------|:------:|------|
| `src/result_merge.py` | **新建** | `can_merge_on_date()` + `merge_results_on_date()` + 内部辅助函数 |
| `src/agent.py` | 修改 | 多计划路径集成 date merge（11 行新增），chinese_answer 根据 merge_status 调整 |
| `tests/test_result_merge.py` | **新建** | 23 个测试，覆盖成功 merge、skip 场景、范围不一致、无因果语言 |

## Merge 条件（7 项必须全部满足）

| # | 条件 | 不满足时的行为 |
|---|------|-------------|
| 1 | 所有子结果都有 date 列 | skipped，reason 含 "缺少 date 列" |
| 2 | 所有子结果 grain 都是 daily | skipped，reason 含 "grain=" |
| 3 | 每个子结果中每个 date 最多一行 | skipped，reason 含 "重复 date" |
| 4 | merge key 只能是 date | 硬约束，不检查其他 key |
| 5 | 至少有 2 个结果 | skipped |
| 6 | 所有结果来自已执行完成的 SQLResult | 检查 row_count > 0 |
| 7 | 每个 source result 可追溯到 source_plan_index | 所有 MergedResult 保留 source_summaries |

### date 范围不一致

不是硬阻断条件。不一致时执行 **outer merge**：
- 缺失日期填 None
- `merge_warnings` 记录缺失详情（>10 条时压缩为摘要）
- 范围完全一致时不产生警告

## Merge 跳过原因

| 跳过原因 | 触发条件 |
|---------|---------|
| `缺少 date 列` | 任一来源的 has_date_column=False |
| `grain 不一致` | 任一来源 grain ≠ "daily" |
| `重复 date` | 任一来源中同一 date 出现多行 |
| `结果为空` | 任一来源 row_count=0 |
| `结果不足` | 少于 2 个来源 |

## 合并策略细节

### 成功 merge 时

- `merge_status = merged`
- `merge_key = "date"`
- `columns = ["date"] + 各来源的指标列`（同名自动加 plan_index 后缀）
- `rows` 按日期排序，缺失日期填 None
- `source_plan_indexes` / `source_summaries` 完整保留

### agent.py 模板回答

**merged**:
> 多个查询结果已按 date 对齐合并展示。共 N 天的数据，包含指标：A、B。

**skipped**:
> 由于 {原因}，未进行自动合并，以下为并列结果。

**禁止的因果语言**: "导致" "造成" "引起" "因为" "所以" "因此" "从而"

## 测试覆盖

| 测试类 | 测试数 | 覆盖内容 |
|--------|:-----:|---------|
| `TestSuccessfulMerge` | 6 | E2E merge 验证、merge_status、columns 包含所有指标、row_count=唯一日期数、source_summaries 可追溯、按 date 对齐值正确 |
| `TestMissingDateSkip` | 3 | 一个无 date → skipped、两个都无 → skipped、skip 后仍有 source_summaries |
| `TestDifferentGrainSkip` | 2 | grain=unknown → skipped、单行 unknown → skipped |
| `TestDuplicateDateSkip` | 2 | 一个有重复 → skipped、两个都有重复 → skipped |
| `TestDateRangeMismatch` | 3 | 部分重叠 → merged + warning、完全不重叠 → outer merge、完全一致 → 无 warning |
| `TestCanMergeOnDate` | 4 | 全部满足 → True、单结果 → False、缺 date → False、不同 grain → False |
| `TestNoCausalLanguage` | 3 | merged 回答无因果词、无跨指标因果模式、skipped reason 也无因果词 |

### 回归套件

```bash
pytest tests/test_result_merge.py tests/test_result_summary.py \
      tests/test_plan_executor.py tests/test_mvp_agent.py \
      tests/test_ir.py tests/test_metric_resolver.py \
      tests/test_metric_catalog.py -v
# 159 passed in 4.44s
```

## 明确未实现

| 功能 | 状态 | 目标 |
|------|:----:|------|
| SQL 层跨表 JOIN | ❌ | 永不——安全红线 |
| LLM 融合 | ❌ | Phase 3B |
| 因果解释 | ❌ | Phase 4（需 explicit causal policy） |
| 图表生成 | ❌ | Phase 5 |
| 并发执行 | ❌ | Phase 3A |
| 多 key merge | ❌ | 永不——安全约束 |
| 不同 grain 强制合并 | ❌ | 永不——数据正确性 |
| pandas 任意 join 暴露 | ❌ | 永不——封装边界 |
