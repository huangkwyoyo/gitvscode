# Phase B1：ResultSummary / MergedResult 实现报告

> 日期：2026-06-16 | 测试：136/136 通过，零回归

## 修改文件

| 文件 | 变更类型 | 说明 |
|------|:------:|------|
| `src/ir.py` | 修改 | 新增 `MergeStatus` 枚举、`ResultSummary` dataclass（13 字段）、`MergedResult` dataclass（10 字段） |
| `src/result_summary.py` | **新建** | `summarize_sql_result()` + `make_merged_result()` + 6 个辅助函数 |
| `tests/test_result_summary.py` | **新建** | 37 个测试，覆盖单/多计划摘要、date 识别、MergedResult 初始状态、辅助函数 |

## 新增结构

### MergeStatus（枚举）

| 值 | 含义 |
|----|------|
| `not_attempted` | 未尝试合并（默认） |
| `merged` | 已合并成功（Phase 3C 使用） |
| `skipped` | 已跳过（grain 不一致 / 无 date 列） |
| `failed` | 合并失败（数据冲突等） |

### ResultSummary（13 字段）

SQLResult 的结构化摘要，所有字段均来自已有数据，不做业务解释：

| 字段 | 类型 | 来源 |
|------|------|------|
| `source_plan_index` | int | 调用方传入（plan_index） |
| `metrics` | list[str] | SubIntent.metrics |
| `dimensions` | list[str] | SubIntent.dimensions |
| `primary_table` | str | SQLPlan.primary_table |
| `strategy` | str | SQLPlan.strategy.value |
| `columns` | list[str] | SQLResult.columns |
| `column_types` | list[str] | SQLResult.column_types |
| `row_count` | int | SQLResult.row_count |
| `sample_rows` | list[list] | SQLResult.rows[:5]，值已序列化 |
| `has_date_column` | bool | 按类型 + 列名检测 |
| `grain` | str | daily / unknown |
| `date_min` | str | 最早日期（ISO 格式） |
| `date_max` | str | 最晚日期（ISO 格式） |
| `warnings` | list[str] | 结果为空 / 无效日期等 |

### MergedResult（10 字段）

多结果合并的容器结构，Phase B1 只定义骨架：

| 字段 | 类型 | Phase B1 默认值 |
|------|------|:---:|
| `merge_status` | MergeStatus | NOT_ATTEMPTED |
| `merge_key` | str | "" |
| `columns` | list[str] | [] |
| `rows` | list[list] | [] |
| `row_count` | int | 各来源行数之和 |
| `source_plan_indexes` | list[int] | 来源序号列表 |
| `source_summaries` | list[ResultSummary] | 完整摘要列表 |
| `merge_warnings` | list[str] | [] |
| `reason` | str | "Phase B1：未执行合并" |

## 摘要规则

### `summarize_sql_result(ur, plan_index) → ResultSummary`

只读取 SQLResult 已有数据，不访问数据库、不执行新 SQL、不推断因果。

**日期列识别**（`_find_date_column`）：
1. 按类型匹配：TIMESTAMP / DATE / DATETIME（兼容 DuckDB DuckDBPyType）
2. 按列名回退：列名含 "date" 或 "time"

**粒度检测**（`_detect_grain`）：
- 相邻日期差全为 1 天 → `daily`
- 仅 1 行或有间隔 → `unknown`

**样本行**（`_extract_sample_rows`）：
- 前 5 行，datetime → ISO 字符串，其他基本类型保持原值

### `make_merged_result(summaries, status, reason) → MergedResult`

Phase B1 只构建结构，不做真正合并。默认 `NOT_ATTEMPTED`。

## 明确未实现

| 功能 | 状态 | 目标阶段 |
|------|:----:|:---:|
| pandas date merge | ❌ | Phase 3C |
| LLM 结果融合 | ❌ | Phase 3B |
| 图表生成 | ❌ | Phase 5 |
| 因果解释 | ❌ | Phase 4 |
| SQLResult 结构修改 | ❌ | —（永不修改） |
| 现有模板回答行为修改 | ❌ | —（永不修改） |

## 测试覆盖

| 测试类 | 测试数 | 覆盖内容 |
|--------|:-----:|---------|
| `TestSingleResultSummary` | 8 | row_count、columns、metrics、primary_table、sample_rows、null result、zero rows |
| `TestDateColumnDetection` | 8 | has_date_column、date_min/max、grain daily(31天/7天)、grain unknown(单行/间隔)、列名回退、TIMESTAMP 类型 |
| `TestNoDateColumn` | 3 | has_date=False、纯指标列、空结果 |
| `TestMultiPlanSummary` | 4 | 每计划生成摘要、plan_index 稳定、不同表 primary_table 不同、date 列均有 |
| `TestMergedResultInitialState` | 5 | 默认 NOT_ATTEMPTED、source_summaries 可追溯、E2E 构造、SKIPPED 显式、FAILED 骨架 |
| `TestHelperFunctions` | 9 | _find_date_column(4)、_detect_grain(3)、_extract_date_values(2) |

### 回归套件

```bash
pytest tests/test_result_summary.py tests/test_plan_executor.py \
      tests/test_mvp_agent.py tests/test_ir.py \
      tests/test_metric_resolver.py tests/test_metric_catalog.py -v
# 136 passed in 3.97s
```
