# Harness 报告目录

本目录存放 Harness 质量检查的持久化报告和基线文件。

## 文件说明

| 文件 | 用途 | 提交策略 |
|------|------|----------|
| `text2sql_report_latest.md` | Text2SQL 评测最新一次报告（自动覆盖） | **提交** — 作为当前问数能力的代表性快照 |
| `text2sql_report_*.md` | 每次运行生成的时间戳报告 | **不提交** — 已加入 `.gitignore`，仅本地保留 |
| `text2sql_signature_baseline.yml` | 结果签名基线（行数/列名/列类型） | **提交** — 数据变更后需同步更新 |

## Text2SQL 报告策略

- **时间戳报告**（`text2sql_report_YYYYMMDD_HHMMSS.md`）：每次 `run_all_checks.py` 或直接运行 `check_text2sql.py` 时自动生成，已加入 `.gitignore`，仅本地保留。
- **最新快照**（`text2sql_report_latest.md`）：每次运行同步覆盖写入，始终反映最新一次评测结果。提交到 Git 作为问数能力的代表快照。
- **签名基线**（`text2sql_signature_baseline.yml`）：记录每个标准问题的结果签名（行数、列名、列类型）。数据重建或标准 SQL 变更后签名发生变化时，需重新生成并提交。
- 如需重置基线，运行 `python scripts/quality/check_text2sql.py --reset-baseline`。
