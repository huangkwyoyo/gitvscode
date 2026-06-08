# Meta 元数据 SQL

用途：维护 `meta` schema 的元数据对象。

Meta 不属于业务事实数据层，它服务于数据治理、中文语义、Agent 理解和自动化校验。

## 当前 Meta 对象

| 对象 | 类型 | 说明 | 状态 |
|---|---|---|---|
| `meta.source_tables` | TABLE | 源表目录（16 张 Bronze 表） | ✅ 已有，构建脚本自动生成 |
| `meta.source_columns` | TABLE | 源字段目录（264 个 Bronze 字段） | ✅ 已有，构建脚本自动生成 |
| `meta.bronze_missing_matrix` | TABLE | Bronze 缺失率矩阵 | ✅ 已有 |
| `meta.bronze_key_checks` | TABLE | Bronze 候选键校验 | ✅ 已有 |
| `meta.bronze_quality_summary` | TABLE | Bronze 质量汇总 | ✅ 已有 |
| `meta.v_bronze_tables` | VIEW | Bronze 表信息视图 | ✅ 已有 |
| `meta.v_bronze_columns` | VIEW | Bronze 字段信息视图 | ✅ 已有 |
| `meta.v_bronze_quality_issues` | VIEW | Bronze 质量问题视图 | ✅ 已有 |
| `meta.table_comments` | TABLE | 表级中文注释（11 条 Silver） | ✅ 已写入，`build_silver_duckdb.py` 生成 |
| `meta.column_comments` | TABLE | 字段级中文注释（201 条 Silver） | ✅ 已写入，`build_silver_duckdb.py` 生成 |

## 待建对象

- `meta.metric_definitions`：指标口径。
- `meta.table_relationships`：表关系、强弱关联说明。
- `meta.question_templates`：中文问数模板。
- `meta.quality_rules`：质量规则。
- `meta.quality_results`：质量检查结果。

## 写入方式

Silver 层表建好后，`build_silver_duckdb.py` 自动同步写入 `meta.table_comments` 和 `meta.column_comments`。

查询示例：

```sql
-- 查看所有 Silver 表的中文名
SELECT * FROM meta.table_comments WHERE table_schema = 'silver';

-- 查看某表的中文字段
SELECT * FROM meta.column_comments WHERE table_name = 'trip_detail' ORDER BY column_name;
```
