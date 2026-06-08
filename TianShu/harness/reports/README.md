# Harness 报告目录

本目录用于说明 Harness 检查报告的存放策略。

当前 `run_all_checks.py` 直接输出到终端，尚未生成持久化报告文件。

后续如果需要保存报告，建议：

- 本地临时报告放在 `harness/reports/local/`，并加入 `.gitignore`。
- 需要提交的审计报告使用 Markdown，文件名包含日期和检查范围。
- 报告只记录检查结果，不复制数据库设计事实源。
