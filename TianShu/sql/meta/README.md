# Meta 元数据 SQL

用途：维护 `meta` schema 的元数据对象。

Meta 不属于业务事实数据层，它服务于数据治理、中文语义、Agent 理解和自动化校验。

建议对象：

- `meta.source_tables`：源表目录。
- `meta.source_columns`：源字段目录。
- `meta.table_comments`：英文表名与中文表名、中文说明。
- `meta.column_comments`：英文字段名与中文字段名、中文说明。
- `meta.metric_definitions`：指标口径。
- `meta.table_relationships`：表关系、强弱关联说明。
- `meta.question_templates`：中文问数模板。
- `meta.quality_rules`：质量规则。
- `meta.quality_results`：质量检查结果。
