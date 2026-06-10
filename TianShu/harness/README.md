# TianShu Harness

本目录是 TianShu 项目的 **Agent Memory + Warehouse Harness 工程入口**。

Harness 负责把规则、记忆、字段字典、数据库设计文档和质量检查串成可执行流程。它不保存数据库设计事实源，也不重复维护字段字典。

## 职责边界

| 内容 | 维护位置 | Harness 中的角色 |
|---|---|---|
| 表结构、字段、主键、类型 | `docs/warehouse/database_design/` | 读取和校验 |
| 字段字典、枚举值（状态码/标志位/分类代码） | `docs/warehouse/data_dictionary/` | 读取和校验 |
| 经验复盘、风险清单、规则来源 | `docs/memory/` | 引用和追踪 |
| 规范索引 | `docs/standards/` | 引用 |
| 质量检查脚本 | `scripts/quality/` | 执行 |
| 回归测试 | `tests/` | 执行 |
| 检查清单、运行说明、配置 | `harness/` | 维护 |

## 一键检查

运行完整 Harness：

```powershell
python scripts\quality\run_all_checks.py
```

运行前提：

- 关闭正在占用 `nyc_transport.duckdb` 的桌面工具，例如 DBeaver。
- 确认 `D:\ProgramData\Datawarehouse\纽约市城市交通\nyc_transport.duckdb` 存在。
- 确认 `D:\ProgramData\Datawarehouse\纽约市城市交通\分析报告\Silver层数据字典.xlsx` 已生成。

## 当前检查范围

| 检查 | 脚本 | 说明 |
|---|---|---|
| Silver 字典一致性 | `scripts/quality/check_silver_dictionary.py` | 字段来源、危险字段、字段数 |
| 危险模式扫描 | `scripts/quality/check_dangerous_patterns.py` | `DATE::INT`、无序 `ROW_NUMBER()` 等 |
| Schema 一致性 | `scripts/quality/check_schema_consistency.py` | 设计文档、xlsx、DuckDB Bronze schema |
| 回归测试 | `tests/test_silver_dictionary.py` | 已发生问题的自动回归 |
| Harness 自检 | `tests/test_harness_quality.py` | 配置读取、关键输入缺失、Silver 实表强校验 |
| Gold 设计门禁 | `scripts/quality/check_gold_design.py` | 检查 Gold 设计文档的中文名、字段来源和类型口径 |
| Gold 物理表门禁 | `scripts/quality/check_gold_physical.py` | 检查 Gold G0/G1/G2/G3 表存在、字段集合和中文注释 |
| 中文语义层门禁 | `scripts/quality/check_semantic_layer.py` | 检查语义元数据、标准中文问题集和模板 SQL 可执行性 |
| Gold 日期键质量门禁 | `scripts/quality/check_gold_date_quality.py` | 检查 Gold 事实表日期键是否在 dim_date 有效范围内，标记异常日期（如 1971/2060） |
| Text2SQL 问数能力评测 | `scripts/quality/check_text2sql.py` | 基于标准问题集，五维评测表选择、指标、SQL 可执行性、结果一致性和层级合规 |

Silver 实表建成后，启用强校验：

```powershell
python scripts\quality\check_schema_consistency.py --require-silver-tables
```

## 子目录

```text
harness
├─ README.md
├─ checklists
│  ├─ pre_silver_build.md
│  ├─ schema_change_review.md
│  └─ pr_review.md
├─ config
│  └─ harness_targets.yml
├─ questions
│  └─ gold_standard_questions.yml
├─ reports
│  └─ README.md
└─ lessons
   └─ README.md
```

## 维护原则

- Harness 只组织执行，不定义正式 schema。
- Harness 可以引用事实源，但不能复制事实源。
- 新增经验后，先写入 `docs/memory/`，再决定是否新增检查脚本和测试。
- 新增检查脚本后，必须更新本目录的检查清单或配置说明。
