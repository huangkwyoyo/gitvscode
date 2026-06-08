# Bronze 原始层 SQL

用途：维护 `bronze` schema 的原始层对象。

当前约定：

- parquet 大表优先注册为外部视图，避免复制大文件。
- CSV 快照表导入为 DuckDB 物理表。
- Bronze 保留原始字段名和原始粒度，不做业务清洗。
- Bronze 表必须同步进入 `meta.source_tables` 和 `meta.source_columns`。
