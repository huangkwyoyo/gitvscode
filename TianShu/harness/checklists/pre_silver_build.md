# Silver 建表前检查清单

在生成或执行 Silver 建表 SQL 前，必须完成本清单。

## 文档检查

- [ ] `docs/warehouse/database_design/silver_database_design.md` 已更新。
- [ ] `docs/warehouse/data_dictionary/README.md` 中的字段字典要求已满足。
- [ ] `D:\ProgramData\Datawarehouse\纽约市城市交通\分析报告\Silver层数据字典.xlsx` 已重新生成。
- [ ] 每个 Silver 字段都有英文名、中文名、数据类型、字段来源类型、来源字段或派生逻辑。
- [ ] 枚举值、缩写值、状态码已补中文含义；无法确认的标记 `Human Review`。

## 数据检查

- [ ] Bronze 表已入库。
- [ ] `meta.source_columns` 可查询。
- [ ] DuckDB 文件未被 DBeaver 等桌面工具占用。
- [ ] `parking_violations_all` 未被新增虚构金额字段。

## Harness 检查

```powershell
python scripts\quality\run_all_checks.py
```

通过后才能进入 Silver 建表 SQL 生成。

Silver 实表创建后，必须追加执行强校验：

```powershell
python scripts\quality\check_schema_consistency.py --require-silver-tables
```
