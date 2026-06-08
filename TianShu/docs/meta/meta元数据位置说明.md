# Meta 元数据位置说明

## 结论

本项目采用“双位置 Meta”设计：

```text
DuckDB 内部 meta schema  # 运行时可查询元数据
项目目录 docs/meta 和 sql/meta  # 可版本管理的元数据设计和建表脚本
```

不要把 Meta 理解成单独的文件夹数据层。Meta 是“描述数据的数据”，它需要同时存在于数据库和项目代码中。

## DuckDB 中的 Meta

DuckDB 文件位置：

```text
D:\ProgramData\Datawarehouse\纽约市城市交通\nyc_transport.duckdb
```

DuckDB 内部已有：

```text
meta.source_tables  # 源表目录，记录表名、来源路径、行数、字段数、数据域
meta.source_columns  # 字段目录，记录字段名、类型、顺序、来源表
meta.bronze_missing_matrix  # Bronze 缺失率矩阵
meta.bronze_key_checks  # Bronze 候选键校验
meta.bronze_quality_summary  # Bronze 质量汇总
meta.v_bronze_tables  # Bronze 表目录视图
meta.v_bronze_columns  # Bronze 字段目录视图
meta.v_bronze_quality_issues  # Bronze 质量问题视图
```

这些对象用于 Agent 查询、质量校验、自动建模和后续 Silver/Gold 生成。

## 项目目录中的 Meta

项目目录：

```text
D:\Program Files\gitvscode\TianShu
```

建议结构：

```text
docs/meta
├─ meta元数据位置说明.md  # 本文档
├─ 中文语义层设计.md  # 后续维护中文表名、字段名、指标口径
├─ 指标口径设计.md  # 后续维护指标定义
└─ Agent问数模板.md  # 后续维护中文问数模板

sql/meta
├─ README.md
├─ 001_create_meta_tables.sql  # 后续创建 meta 表结构
└─ 002_load_meta_comments.sql  # 后续写入中文注释和语义元数据
```

项目目录中的 Meta 文件用于版本管理和人工审查；DuckDB 中的 Meta 表用于运行时查询。

## 建表注释规范

项目强制要求：

- 英文表名后一列必须有中文表名。
- 英文字段名后一列必须有中文字段名。
- 主键、外键、候选键、指标名必须有中文说明。
- 建表后必须同步写入中文表注释和字段中文注释。

DuckDB 如果无法稳定使用原生 `COMMENT ON TABLE` / `COMMENT ON COLUMN`，则必须使用以下元数据表维护中文语义：

```text
meta.table_comments
meta.column_comments
```

建议字段：

```text
meta.table_comments
├─ table_schema  # 英文 schema 名
├─ table_name  # 英文表名
├─ table_name_zh  # 中文表名
├─ table_comment_zh  # 中文表说明
├─ data_domain_zh  # 中文数据域
└─ updated_at  # 更新时间

meta.column_comments
├─ table_schema  # 英文 schema 名
├─ table_name  # 英文表名
├─ column_name  # 英文字段名
├─ column_name_zh  # 中文字段名
├─ column_comment_zh  # 中文字段说明
├─ data_type  # 字段类型
├─ column_role_zh  # 字段角色，如主键、关联键、时间字段、金额字段
└─ updated_at  # 更新时间
```

## 与数仓分层的关系

```text
bronze  # 原始数据
silver  # 标准明细
gold    # 主题模型
meta    # 描述以上所有层的元数据和中文语义
```

Meta 不替代 Bronze/Silver/Gold。Meta 负责让人和 Agent 明白：

- 有哪些表。
- 表是什么意思。
- 字段是什么意思。
- 哪些字段是主键或关联键。
- 哪些表可以关联。
- 指标怎么算。
- 哪些问题不能直接回答。

