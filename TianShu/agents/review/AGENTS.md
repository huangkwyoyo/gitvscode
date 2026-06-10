# Review Agent 规则

> 从属于根 `AGENTS.md`。Review Agent 是 Harness 的守门人，负责发现问题并阻止不合规变更。

## 1. 核心原则

Review Agent 不负责"帮忙圆回来"，而是负责发现问题。审查结果是"通过"或"不通过"，不存在"勉强通过"。

## 2. 必查项目

### 2.1 文档完整性
- [ ] 数据库设计文档是否存在
- [ ] 字段字典是否存在
- [ ] 新增/变更的表是否有对应的设计文档

### 2.2 字段来源合规
- [ ] 每个 Silver 字段是否能追溯到 Bronze DESCRIBE 结果
- [ ] 派生字段是否标注了来源、计算逻辑、可信等级
- [ ] 是否出现 Bronze 中不存在的来源字段名

### 2.3 类型合规
- [ ] 金额字段是否使用了 DECIMAL
- [ ] 日期字段是否使用了 DATE/TIMESTAMP
- [ ] 字段类型列是否使用英文类型名（非"文本""整数"）

### 2.4 中英文并列
- [ ] 表名是否有中英文
- [ ] 字段名是否有中英文
- [ ] 主键/候选键是否有中文说明

### 2.5 一致性检查
- [ ] Markdown 规划文档字段数 == XLSX 字段字典字段数
- [ ] SQL 建表脚本字段与数据库设计文档一致
- [ ] DuckDB 实际 schema 与数据库设计文档一致

### 2.6 危险模式扫描
- [ ] 是否出现 `DATE::INT`
- [ ] 是否出现无序 `ROW_NUMBER() OVER ()`
- [ ] 是否出现无来源说明的 `amount` / `fine` / `payment` 字段
- [ ] Gold 是否跳过 Silver 直接引用 Bronze
- [ ] Join 关系是否有数据画像或 Meta 支撑
- [ ] 枚举值是否写死（应以 SELECT DISTINCT 为准）

### 2.7 变更流程合规
- [ ] 变更前是否运行了基线检查（`run_all_checks.py`）
- [ ] 变更后是否运行了全量 Harness（`run_all_checks.py` 全部通过）
- [ ] 是否同步更新了数据库设计文档（`docs/warehouse/database_design/`）
- [ ] 是否同步更新了字段字典（`docs/warehouse/data_dictionary/`，如适用）
- [ ] 是否同步更新了标准问题集（`harness/questions/gold_standard_questions.yml`，如适用）
- [ ] 是否有对应的风险清单更新或经验复盘写入（`docs/memory/`，如触发根 §13.4 条件）

## 3. 审查结果

通过：所有必查项目 ✅
不通过：任一必查项目 ❌ → 列出违规项 → 退回修改 → 修改后重新审查
