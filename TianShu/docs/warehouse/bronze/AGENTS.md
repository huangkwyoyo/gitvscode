# Bronze 层规则

> 从属于 `docs/warehouse/AGENTS.md` 和根 `AGENTS.md`。

## 1. Bronze 层职责

Bronze 是原始层。**唯一职责：把源数据接进来，保持原貌。**

## 2. Bronze 层允许做

- 注册外部 Parquet 为 VIEW（`CREATE OR REPLACE VIEW bronze.xxx AS SELECT * FROM read_parquet(...)`）
- 导入 CSV 为物理 TABLE（`CREATE OR REPLACE TABLE bronze.xxx AS SELECT * FROM read_csv_auto(...)`）
- 保留原始字段名（不重命名）
- 保留原始字段类型（DuckDB 自动推断）
- 生成 meta 元数据（source_tables、source_columns、missing_matrix、key_checks）

## 3. Bronze 层禁止做

- 修改字段名
- 修改字段类型
- 删除字段
- 新增业务字段
- 数据清洗（去重、去空、格式标准化属于 Silver 层）
- 业务改造
- 生成指标或 KPI
- 修改字段含义

## 4. 字段来源确认规则

确认 Bronze 表有哪些字段的唯一正确方式：

```sql
DESCRIBE bronze.<表名>;
-- 或
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'bronze' AND table_name = '<表名>'
ORDER BY ordinal_position;
```

禁止通过以下方式确认字段存在性：
- 阅读官方 xlsx 数据字典
- 阅读 Markdown 规划文档
- 根据业务常识推断
- 根据 Agent 训练数据猜测

## 5. Bronze 表清单

当前已注册 16 张 Bronze 表（7 VIEW + 9 TABLE），详见 `meta.source_tables`。

## 6. 质量监控

Bronze 层的质量监控由构建脚本自动完成：
- `meta.source_tables`：表级目录
- `meta.source_columns`：字段级目录
- `meta.bronze_missing_matrix`：缺失率矩阵
- `meta.bronze_key_checks`：候选键校验
- `meta.bronze_quality_summary`：质量汇总
