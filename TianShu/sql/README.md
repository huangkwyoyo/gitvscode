# SQL 目录说明

本目录存放 DuckDB 数据仓库的 SQL 脚本。

```text
sql
├─ bronze  # Bronze 原始层对象定义和重建脚本
├─ silver  # Silver 标准层建表、清洗、去重、标准化脚本
├─ gold    # Gold 星型模型和事故 ER 子模型脚本
└─ meta    # 元数据表、中文注释、指标口径、关系说明脚本
```

注意：本目录只放可版本管理的 SQL，不放 `.duckdb` 数据库文件。
