# 字段字典

本目录存放正式字段字典。当前字段字典文件位置：

## Bronze 层字段字典

- **XLSX**：`D:/ProgramData/Datawarehouse/纽约市城市交通/分析报告/纽约市城市交通_全表数据字典.md`
- **覆盖**：15 张 Bronze 表 + Meta 层 8 个对象，共 264 个字段
- **更新方式**：基于构建脚本 `scripts/bronze/build_nyc_transport_duckdb_bronze.py` 自动生成 meta.source_columns

## Silver 层字段字典

- **XLSX**：`D:/ProgramData/Datawarehouse/纽约市城市交通/分析报告/Silver层数据字典.xlsx`
- **Sheet 数**：12（1 总览 + 11 张表各一个 Sheet）
- **生成脚本**：`scripts/silver/_gen_xlsx.py`
- **更新方式**：修改 `_gen_xlsx.py` 后重新运行生成

## 字段字典必须包含

- 英文表名
- 中文表名
- 英文字段名
- 中文字段名
- 数据类型（英文类型名）
- 字段层级（主键/时间字段/空间字段/金额字段/维度属性/度量/质量标记/溯源字段）
- 业务含义
- 治理备注
- 字段来源类型（direct / standardized / derived）
- 来源 Bronze 字段（direct/standardized 必填）
- 派生逻辑（derived 必填）

## 变更流程

每次 schema 变更：
1. 更新 `_gen_xlsx.py` 中的字段定义
2. 运行 `python scripts/silver/_gen_xlsx.py` 重新生成 xlsx
3. 确认 xlsx 与 Markdown 规划文档的字段数一致
4. 通过 `check_schema_consistency.py` 检查
