# 数据开发 Agent 规则

> 从属于根 `AGENTS.md` §13 变更传播规则。本文件将根规则转化为场景化的可执行清单。
>
> 数据开发 Agent 是"建表/改表/增字段/改指标"的 Agent，不是查询 Agent。它负责执行受控的数据仓库变更，确保每一步都有事实源支撑、有门禁验证。

## 1. 变更前置条件

开始任何变更前，必须完成以下三步：

1. **读取强制前置文档**：对照根 `AGENTS.md` 路由表"修改任何数据库 Schema 前"的全部文件，逐份阅读
2. **运行基线检查**：`python scripts/quality/run_all_checks.py`，确认当前基线全部通过
3. **基线不通过的处理**：如果基线有失败项，先修复或记录，再开始新操作（根 §13.6 操作前基线检查）

## 2. 场景化执行清单

### 场景 A：新增一张表

按顺序执行，不得跳过：

1. 在 `docs/warehouse/database_design/{layer}_database_design.md` 中增加表定义表格
2. 确保中英文表名、字段名、主键、类型、来源字段全部填写
3. 字段类型使用英文原生类型名（`VARCHAR`、`BIGINT`、`DECIMAL(12,2)` 等），金额字段必须用 `DECIMAL`
4. 运行对应设计门禁：Gold 层用 `check_gold_design.py`，Silver 层用 `check_silver_dictionary.py`
5. 在 `scripts/{layer}/build_{layer}_duckdb.py` 中实现建表函数，SQL 注释使用中文
6. 建表完成后运行全量 Harness：`python scripts/quality/run_all_checks.py`
7. 同步更新 `scripts/{layer}/README.md` 表清单
8. 同步更新 `PROJECT_STATUS.md`（如阶段有变化）
9. 判断是否触发记忆写入条件：若满足根 §13.4 中任一条件 → 写入 `docs/memory/经验复盘.md`；若不满足 → 输出"本次无踩坑，跳过记忆写入"
10. 如新增 G3 汇总表或语义层表，同步扩充 `harness/questions/gold_standard_questions.yml`（至少 1 道题）

### 场景 B：修改已有表字段

1. 在 `docs/warehouse/database_design/{layer}_database_design.md` 中找到对应表，修改字段定义
2. 运行对应设计门禁，确认设计文档与约束一致
3. 修改 `scripts/{layer}/build_{layer}_duckdb.py` 中的建表 SQL
4. 重新构建该表（及所有依赖该表的汇总表/语义层表）
5. 运行全量 Harness：`python scripts/quality/run_all_checks.py`
6. 如果字段名或含义变化，同步更新字段字典 `docs/warehouse/data_dictionary/`
7. 如果字段被删除，同步更新 `scripts/{layer}/README.md` 中的字段数
8. 如果影响到 G3 汇总表或语义层指标，优先重建受影响的汇总表/语义层
9. 同步更新 `harness/questions/gold_standard_questions.yml` 中引用该表的问题（如有）

### 场景 C：新增指标

1. 在 `docs/warehouse/database_design/gold_database_design.md` §7 指标设计草案中增加指标定义
2. 在 `scripts/gold/build_gold_duckdb.py` 的语义层写入函数中注册新指标（`meta.metric_definitions`）
3. 如果新指标需要 G3 汇总表支持，先扩建汇总表（走场景 A）
4. 运行 `python scripts/quality/check_semantic_layer.py` 确认指标注册成功
5. 在 `harness/questions/gold_standard_questions.yml` 中增加至少 1 道引用新指标的测试题
6. 运行 `python scripts/quality/check_text2sql.py` 确认新问题通过五维评测

### 场景 D：修改语义层（metric_definitions / semantic_dimensions / business_terms）

1. 在 `build_gold_duckdb.py` 中修改语义层写入逻辑（DELETE + INSERT 模式，参考经验 R010）
2. 运行 `python scripts/quality/check_semantic_layer.py` 确认语义层一致性
3. 同步更新 `harness/questions/gold_standard_questions.yml` 中引用了被修改指标/维度的问题
4. 运行 `python scripts/quality/check_text2sql.py` 确认受影响问题仍通过

## 3. 同步更新传播清单

变更完成后必须逐项检查是否需要更新以下文件：

| 文件 | 何时必须更新 |
|------|-------------|
| `docs/warehouse/database_design/` | 表结构、字段数、主键变更时（**必查**） |
| `docs/warehouse/data_dictionary/` | 字段名、含义、枚举值变更时 |
| `scripts/{layer}/README.md` | 表清单、行数、构建方式变更时 |
| `PROJECT_STATUS.md` | 阶段完成或重大变更时 |
| `harness/questions/gold_standard_questions.yml` | 新增表/指标/语义层时 |
| `docs/memory/经验复盘.md` | 有踩坑时（根 §13.4 触发条件） |
| `docs/memory/风险清单.md` | 发现新风险或防线变更时 |

## 4. 校验标准

变更完成后，必须全部确认：

- [ ] `python scripts/quality/run_all_checks.py` 全部步骤通过
- [ ] 新表/新字段有中英文双语名称
- [ ] 新指标在 `meta.metric_definitions` 注册
- [ ] 标准问题集覆盖了新表/新指标的核心查询路径
- [ ] 数据库设计文档与 DuckDB 实表字段一致
- [ ] 未出现根 `AGENTS.md` §13 禁止的行为（虚构字段、跳过门禁、基线失败继续建表等）

## 5. 禁止行为

- 禁止在数据库设计文档更新前开始写 SQL
- 禁止在 Harness 检查失败后直接进入下一张表的构建
- 禁止用"先建表，后补文档"的方式操作
- 禁止在检查失败后只报告不修复（根 §13.6）
- 禁止编造 Bronze 中不存在的字段或金额
- 禁止使用 Google 翻译或 LLM 翻译结果作为正式中文名
