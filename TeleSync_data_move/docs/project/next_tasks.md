# 下一步任务

## 优先级 P0

1. 对 `business_processes/` 下 10 个业务过程做静态检查。
2. 检查 SQL 是否满足：禁止 `SELECT *`、字段显式、CTE 分层、Join 条件完整、业务日期明确、除零保护存在。
3. 检查校验 SQL 是否输出标准字段：`check_name`、`check_type`、`check_result`、`expected_value`、`actual_value`、`diff_value`、`remark`。

## 优先级 P1

1. 完善 `metadata/mysql_profile/` 标准画像文档。
2. 建立 `migration_rules/` 初版规则文件。
3. 建立批次配置模板。

## 暂不执行

- 暂不执行建表。
- 暂不执行业务 SQL 写入。
- 暂不执行 Doris 转换。
- 暂不提交 WebSQL 任务。
