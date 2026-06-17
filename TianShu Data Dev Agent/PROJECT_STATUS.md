# TianShu Data Dev Agent — 项目状态

> 版本：v2.0 | 日期：2026-06-17 | 作者：Agent Team
>
> ⚠️ **架构方向变更（2026-06-16）**：项目已从 v1.x（确定性数据生产管道）转向 v2.0（AI 辅助数据开发工具）。详见 `docs/superpowers/specs/架构方向变更记录_20260616_2230.md`。
>
> 本文档记录项目的整体状态。v1.x Phase 1-7 编译器代码在 v2.0 中保留为自动验证（防线 2）的确定性规则引擎和 fallback 编译器。v2.0 M2/M3 工作流是当前开发主线。

---

## 一、项目定位

TianShu Data Dev Agent 是一个**确定性的数据生产管道系统**。接收 YAML 需求说明书 → 经过 8 层管道处理 → 产出数据文件 + 验证报告 + 调度任务配置。

**核心原则**：
- SQL 不是"写"出来的，是"编译"出来的
- LLM 只在 Layer 1-2 参与（需求解析 + 指标消歧），Layer 3-8 是纯确定性代码
- IR 冻结后所有字段类型已知，编译器不做"猜测"

---

## 二、当前里程碑

```
Phase 0 ──── 项目骨架 + 契约层                    ✅ 已完成（2026-05）
Phase 1 ──── MVP：单条 SQL 管道（Layer 1-8）       ✅ 已完成（2026-06-10）
Phase 2 ──── DAG 运行时代码（PipelinePlan + 校验）  ✅ 已完成（2026-06-12）
  ├─ IR Freeze（C1-C6 修正）                       ✅ 已完成（2026-06-14）
  └─ P3 表达式编译器（10类型 × 3方言）              ✅ 已完成（2026-06-14）
Phase 3 ──── 记忆系统 + 变更传播闭环                ✅ 已完成（2026-06-14）
Phase 4 ──── 窗口函数编译器（12类型 × 3方言）         ✅ 已完成（2026-06-14）
Phase 5 ──── CTE 编译器（WITH 子句）                 ✅ 已完成（2026-06-14）
Phase 6 ──── 操作编译器（CTAS/INSERT/CREATE VIEW）   ✅ 已完成（2026-06-14）
Phase 7 ──── 增量意图 → 执行策略                     ✅ 已完成（2026-06-14）
```

---

## 三、实现进度矩阵

### 3.1 管道层

| 层 | 名称 | 状态 | LLM 参与 | 关键文件 |
|----|------|------|---------|---------|
| L1 | 需求解析 | ✅ 完成 | 仅 fallback | `layer1_requirement.py` |
| L2 | 意图理解 | ✅ 完成 | 模糊匹配 | `layer2_intent.py` |
| L3 | 规划层 | ✅ 完成 | 禁止 | `layer3_plan.py`、`layer3_pipeline_plan.py` |
| L4 | 编译层 | ✅ 核心完成 | 禁止 | `layer4_generate.py`、`layer4_expression.py` |
| L5 | 校验层 | ✅ 完成 | 禁止 | `layer5_validate.py`、`layer5_validate_pipeline.py` |
| L6 | 执行层 | ✅ 完成 | 禁止 | `layer6_execute.py` |
| L7 | 评估层 | ✅ 完成 | 禁止 | `layer7_evaluate.py` |
| L8 | 产出层 | ✅ 完成 | 禁止 | `layer8_product.py` |

### 3.2 编译器能力矩阵

| 组件 | 状态 | 覆盖范围 |
|------|------|---------|
| SQL 编译（SELECT/FROM/WHERE/GROUP BY/ORDER BY/LIMIT） | ✅ | L4 核心——6 个编译 Pass |
| 表达式编译器（10 类型 × 3 方言） | ✅ | DuckDB/Hive/PostgreSQL |
| 窗口函数编译器（12 类型 × 3 方言） | ✅ | LEAD/LAG/ROW_NUMBER/RANK/SUM/AVG/COUNT 等 |
| CTE 编译器（WITH 子句 + C4 约束） | ✅ | 链式 CTE + 递归深度硬限制 + 参数传播 |
| 操作编译器（P6——5种操作 × 3方言） | ✅ | CTAS/INSERT OVERWRITE/INSERT INTO/CREATE VIEW + 方言差异 |
| 增量策略解析器（P7） | ✅ | PipelineStep → ExecutionStrategy 纯函数解析 |

### 3.3 IR 成熟度

| IR 类型 | 状态 | 冻结 |
|---------|------|------|
| Intent IR | ✅ 稳定 | 字段结构已锁定 |
| SQLPlan IR | ✅ 已冻结 | C1-C6 修正完成 |
| PipelinePlan IR | ✅ 稳定 | DAG 结构确定 |
| ExpressionRef IR | ✅ 已冻结 | 10 类型 + 3 方言 |

### 3.4 安全体系

| 防线 | 状态 | 检查项 |
|------|------|--------|
| 门禁 1：L2 指标校验 | ✅ | 所有指标名必须在已注册列表中 |
| 门禁 2：L5 SQL 校验 | ✅ | 6 项检查（只读前缀 SELECT+WITH / 黑名单 / 表引用 / 全限定名 / JOIN白名单 / 日期合规） |
| 门禁 3：L5 DAG 校验 | ✅ | 环检测/依赖完整性/拓扑序/safety_tier合规 |

### 3.5 IR 层级与信息隔离

#### 信息隔离链

每个 IR 只暴露下一层需要的信息——这是"信息防火墙"设计：

```
Requirement IR     → 隔离 YAML 语法细节（下层不需要知道输入是 YAML）
Intent IR          → 隔离用户原始措辞（LLM 防火墙在此——下层不接触 LLM 输出）
SQLPlan IR         → 隔离指标→列的映射逻辑（下层不关心 G3 vs G2 决策）
ExpressionRef IR   → 隔离表达式树结构（嵌入 SQLPlan，编译器只看到标准化 IR）
WindowFunctionDef  → 隔离窗口函数语义（嵌入 SQLPlan，方言无关）
CTEDefinition      → 隔离 CTE 链结构（嵌入 SQLPlan，递归深度可静态检查）
SQL 文本            → 隔离方言特定语法（执行层不关心 SQL 怎么生成的）
ExecutionResult    → 隔离数据库连接细节（评估层不关心用什么引擎执行）
Product 文件        → 隔离 Parquet/CSV 内部格式（消费者只拿到文件）
```

#### 每个 IR 为什么存在

| IR 类型 | 解决什么问题 | 没有它会怎样 |
|--------|-------------|-------------|
| Requirement | YAML 解析和 Schema 校验分离 | L2 需要直接处理 YAML，LLM 边界被污染 |
| Intent | LLM 输出和工程代码之间的防火墙 | LLM 可能输出表名，安全边界消失 |
| SQLPlan | 规划决策（G3/G2/JOIN）的标准化表达 | L4 编译器需要自己做规划决策，耦合 |
| ExpressionRef | 表达式从字符串变为结构化 IR | 编译器需要解析字符串表达式，易出错 |
| WindowFunctionDef | 窗口函数的方言无关表达 | 每种方言需要自己解析窗口函数语义 |
| CTEDefinition | CTE 链的显式建模 | WITH 子句的递归引用无法校验 |

---

## 四、测试覆盖

```
总测试数：529 passed（0 failed）  ← v2.0 M2/M3/M4a + src/agent/ 直接单元测试 + SQL 安全口径收紧已纳入
执行时间：< 5s（全部测试）

v1.x 测试：143 passed（scripts/pipeline/ 确定性编译器）
v2.0 测试：386 passed（src/verify/、src/sandbox/、src/ir/、src/compile/、src/agent/）
```

### 4.0 v2.0 新增测试明细

| 测试类 | 文件 | 数量 | 覆盖范围 |
|--------|------|------|---------|
| TestValidator + TestChecksWithDB | `test_src_verify.py` | ~40 | 7 项检查 + Validator 编排 + 安全压实 |
| TestDuckDBExecutor + TestSandboxForbiddenKeywords | `test_src_sandbox.py` | ~18 | 只读执行 + 超时保护 + 19 关键字拦截 |
| TestTimerRaceCondition | `test_src_sandbox.py` | 3 | Timer 竞态修复 |
| TestV1BridgeWarnings + TestSQLPlanCaseNormalization | `test_src_ir.py` | ~10 | IR bridge + 大小写规范化 |
| TestCompileSysPath + TestCompileV1Incompatible | `test_src_compile.py` | 5 | sys.path 隔离 + 不兼容处理 |
| TestDAGEndToEnd + 集成测试 | `test_pipeline_dag_e2e.py` | ~46 | DAG 编译 + 安全关键字 + 执行语义 |
| M2 Review Package 集成测试 | `test_src_agent_m2.py` | ~10 | workflow + review_publisher + dual_code_generator 集成 |
| M3 Verification Engine 集成测试 | `test_src_agent_m3.py` | ~12 | verification_engine + checker + cross_validation 集成 |
| **src/agent/ 直接单元测试（新增）** | `test_src_agent_*.py`（6 文件） | **142** | requirement_analyzer / design_planner / dual_code_generator / review_publisher / workflow / verification_engine |
| **M4a 人审状态机** | `test_src_agent_review_publisher.py` + `test_src_agent_verification_engine.py` | +8 | decision.yml / decision_log.yml / verification_summary.yml |
| v1.x 编译器测试 | `test_pipeline.py` | ~110 | 表达式/窗口/CTE/操作编译器 |
| v1.x Phase 2 测试 | `test_pipeline_phase2.py` | 25 | DAG 环检测 + 安全层级 |

### 4.1 按 v2.0 价值分类

| 类别 | 数量 | 占比 | v2.0 对应 |
|------|------|------|----------|
| **防线 2 直接相关** | 42 | 29% | 安全黑名单、表权限、JOIN 白名单、DAG 校验、安全层级——阶段 4 自动验证核心 |
| **ColumnBindingTable** | 3 | 2% | LLM 参考数据源 + 验证基准 |
| **操作/策略编译** | 25 | 18% | LLM 设计方案时的参考实现 |
| **模板编译器（fallback）** | 73 | 51% | 表达式/窗口/CTE/SQL 编译器——LLM 直接生成 SQL 后降级为安全 fallback |
| **合计** | **143** | **100%** | |

### 4.2 测试明细

| 测试类 | 文件 | 数量 | v2.0 价值 |
|--------|------|------|----------|
| TestLayer5Validation | `test_pipeline.py` | 2 | **防线 2**——安全黑名单 |
| TestLayer4SQLCompile | `test_pipeline.py` | 2 | Fallback——SQL 编译 |
| TestColumnBindingTable | `test_pipeline.py` | 3 | **核心**——指标注册完整性 |
| P3 表达式编译器 | `test_pipeline.py` | 31 | Fallback——10 类型 × 3 方言 |
| P4 窗口函数编译器 | `test_pipeline.py` | 25 | Fallback——12 类型 + OVER |
| P5 CTE 编译器 | `test_pipeline.py` | 11 | Fallback——链式 CTE |
| P6+P7 操作编译器+增量策略 | `test_pipeline.py` | 24 | **参考实现**——策略/操作方言 |
| TestDAGCycleDetection | `test_pipeline_phase2.py` | 6 | **防线 2**——DAG 环检测 |
| TestDAGDependencyReferences | `test_pipeline_phase2.py` | 3 | **防线 2**——依赖完整性 |
| TestDAGTopologicalOrder | `test_pipeline_phase2.py` | 3 | **防线 2**——拓扑序 |
| TestSafetyTierOperationCompliance | `test_pipeline_phase2.py` | 10 | **防线 2**——安全层级合规 |
| TestValidatePipeline | `test_pipeline_phase2.py` | 3 | **防线 2**——综合校验 |
| TestSQLStructureValidation | `test_pipeline_dag_e2e.py` | 13 | **防线 2**——SQL 结构 + 安全关键字 |
| TestDAGValidationIntegration | `test_pipeline_dag_e2e.py` | 4 | **防线 2**——DAG + 安全集成 |
| TestTableRefMap | `test_pipeline.py` | 2 | Fallback——表引用映射 |
| TestExpressionSelectIntegration | `test_pipeline.py` | 3 | Fallback——表达式 SELECT 集成 |
| TestCompileExpressionsBatch | `test_pipeline.py` | 3 | Fallback——批量表达式编译 |
| Window/CTE Select 集成 | `test_pipeline.py` | 10 | Fallback——窗口/CTE SELECT 集成 |
| **合计** | | **143** | |

---

## 五、文件清单

### 5.1 核心代码（17 个文件）

| 文件 | 行数（约） | 说明 |
|------|-----------|------|
| `scripts/pipeline/run_pipeline.py` | ~120 | 入口——8 层全链路编排 |
| `scripts/pipeline/layer1_requirement.py` | ~80 | YAML → Requirement 对象 |
| `scripts/pipeline/layer2_intent.py` | ~150 | Requirement → Intent（LLM 最后出现） |
| `scripts/pipeline/layer3_plan.py` | ~500 | Intent → SQLPlan IR + IR dataclass 定义 |
| `scripts/pipeline/layer3_pipeline_plan.py` | ~280 | Intent → PipelinePlan IR + StepOperation 枚举 |
| `scripts/pipeline/layer4_generate.py` | ~320 | SQLPlan IR → SQL 文本（6 个编译 Pass） |
| `scripts/pipeline/layer4_expression.py` | ~460 | ExpressionRef IR → SQL 表达式（注册表模式） |
| `scripts/pipeline/layer4_window.py` | ~280 | WindowFunctionDef IR → SQL 窗口函数 |
| `scripts/pipeline/layer4_cte.py` | ~130 | CTEDefinition IR → WITH 子句 |
| `scripts/pipeline/layer4_operation.py` | ~380 | P6 操作编译 + P7 增量策略解析 |
| `scripts/pipeline/layer5_validate.py` | ~200 | SQL 安全校验（6 项检查） |
| `scripts/pipeline/layer5_validate_pipeline.py` | ~200 | DAG + 安全层级校验 |
| `scripts/pipeline/layer6_execute.py` | ~100 | DuckDB 执行 |
| `scripts/pipeline/layer7_evaluate.py` | ~80 | 结果统计评估 |
| `scripts/pipeline/layer8_product.py` | ~80 | 产出文件写入 |
| `scripts/pipeline/column_binding.py` | ~180 | ColumnBindingTable——中枢映射表 |
| `scripts/pipeline/__init__.py` | ~10 | 包初始化 |

### 5.2 契约文件（6 个）

| 文件 | 说明 |
|------|------|
| `contracts/requirement_schema.yml` | 需求说明书格式 |
| `contracts/sqlplan_schema.yml` | SQLPlan IR 格式 |
| `contracts/pipeline_plan_schema.yml` | PipelinePlan IR 格式 |
| `contracts/pipeline_execution_config_schema.yml` | 执行层配置（safety_tier 等） |
| `contracts/validation_schema.yml` | 校验报告格式 |
| `contracts/result_schema.yml` | 结果文件格式 |

### 5.3 测试文件（2 个）

| 文件 | 测试数 | 说明 |
|------|--------|------|
| `tests/test_pipeline.py` | 110 | Phase 1（19）+ P3（31）+ P4（25）+ P5（11）+ P6+P7（24） |
| `tests/test_pipeline_phase2.py` | 25 | Phase 2 DAG + 安全层级 |

### 5.4 评测文件（2 个）

| 文件 | 说明 |
|------|------|
| `evals/e2e_cases.yml` | 5 个端到端评测用例 |
| `evals/regression_baseline.yml` | Prompt 回归基线（尚未实际运行） |

### 5.5 文档文件（4 个）

| 文件 | 说明 |
|------|------|
| `CLAUDE.md` | 项目级代码规范 |
| `PROJECT_STATUS.md` | 本文档——项目整体状态 |
| `docs/text2sql_engineering_glossary.md` | 工程词典——所有术语定义（v1.1） |
| `docs/text2sql_current_pipeline.md` | 管道工作流详解（v1.0） |

### 5.6 基础设施文件（1 个）

| 文件 | 说明 |
|------|------|
| `.gitignore` | Git 忽略规则——`generated/` 产物、`__pycache__/` 等不纳入版本管理 |

### 5.7 需求样例（3 个）

| 文件 | 业务域 |
|------|--------|
| `fixtures/requirements/trip_daily_report.yml` | traffic——每日行程 |
| `fixtures/requirements/parking_daily_report.yml` | violation——每日违章 |
| `fixtures/requirements/crash_daily_report.yml` | safety——每日事故 |

---

## 六、关键技术决策记录

### 决策 1：LLM 边界（2026-05）
- **决策**：LLM 只能在 Layer 1-2 参与，输出必须是结构化 JSON，不得包含表名/字段名/SQL 片段
- **原因**：防止 LLM 幻觉污染编译器，保证确定性

### 决策 2：编译器优先设计（2026-05）
- **决策**：SQL 不通过 LLM 生成，而是从 SQLPlan IR 确定性编译
- **原因**：可回归测试、可审计、可重现

### 决策 3：IR 中介架构（2026-05）
- **决策**：在 Layer 2（Intent）和 Layer 4（SQL 编译）之间插入 IR 层
- **原因**：解耦方言差异、字段映射、JOIN 构造——每层独立演进

### 决策 4：IR Freeze（2026-06-14）
- **决策**：编译器实现前，先完成 C1-C6 修正，冻结 IR 类型系统
- **原因**：编译器是 IR 的消费者——IR 不冻结，编译器无法安全构建

### 决策 5：注册表模式（2026-06-14）
- **决策**：表达式编译器使用 `{方言: {表达式类型: 编译函数}}` 二级字典分发
- **原因**：O(1) 分发，新方言只需注册差异函数，自动 fallback 到 DuckDB

### 决策 6：两遍编译（2026-06-14）
- **决策**：递归嵌套表达式（EXPR_REF）通过两遍编译处理——先建索引、再递归展开
- **原因**：避免循环引用，深度上限 10 防止无限递归

### 决策 7：为什么 8 层而非 3 层（2026-06-15）
- **决策**：Data Dev Agent 使用 8 层管道而非 Text2SQL Agent 的 3 层 IR 架构
- **原因**：两个系统定位不同——批量数据生产需要每层独立可审计、可重试、可观测。

#### 每层的不可合并理由

| 层 | 职责 | 为什么不能合并 |
|----|------|--------------|
| L1 需求解析 | YAML Schema 校验 | L1 是规则解析 YAML，L2 可能调用 LLM。合并后 LLM 边界模糊 |
| L2 意图理解 | 指标消歧 + LLM 翻译 | LLM 的最后一个接触点——后续全部确定性 |
| L3 SQLPlan 规划 | 查表 + JOIN 构造 | LLM 防火墙——合并到 L2 会让 LLM 接触物理层 |
| L4 SQL 编译 | 多方言模板编译 | 与 L3 分离可独立测试方言——不影响规划决策 |
| L5 SQL 校验 | 6 项安全检查 | 独立审计——校验失败需追溯到 L3 的 SQLPlan，不能混在编译层 |
| L6 SQL 执行 | 只读执行 + 重试 | 与 L7 分离——评估可能标记 DIRTY 但仍需输出产物 |
| L7 结果评估 | 统计质量检查 | 生产独有——交互查询不需要空值率/行数范围检查 |
| L8 产物发布 | 文件输出 + 审计报告 | 生产独有——交互查询输出自然语言，不需要 Parquet |

#### 与 Text2SQL Agent 3 层 IR 的对比

| | Text2SQL Agent（3 IR） | Data Dev Agent（8 层） |
|---|---|---|
| 场景 | 用户问 → 几秒内回答 | YAML → 定时批量产出文件 |
| 输出 | 中文自然语言回答 | Parquet/CSV + 审计报告 + 调度配置 |
| 失败处理 | 反问/拒绝即可 | 需定位到具体哪一层失败 |
| LLM 接触面 | 每次查询都经过 LLM（L1 + L2） | LLM 仅首次解析时参与（L1-L2） |
| 审计要求 | 中等 | 高——每层独立校验记录 |

**结论**：8 层是批量生产管道的最小必要层数。Text2SQL 的 3 层对交互查询正确，但它若做批量生产也需补上校验/评估/发布层。

---

## 七、下一步计划

### v2.0 已完成

| 里程碑 | 状态 | 说明 |
|--------|------|------|
| M2 Review Package 完整生成 | ✅ | `src/agent/workflow.py` → 7 文件审查材料包 |
| M2 双份代码草案（SQL + Spark DSL） | ✅ | `dual_code_generator.py` 确定性生成 |
| M3 静态检查（5 项） | ✅ | `checker.py` + `checks.py` 完整实现 |
| M3 SQL 样本执行 + 安全压实 | ✅ | `sandbox/executor.py`，529 测试零回归 |
| M3 验证引擎串联 | ✅ | `verification_engine.py` 串起 checker + executor + cross_validation |
| 3 批次修复 + 安全压实 | ✅ | Batch 1-3 + G1/G2/G3 防御纵深缺口闭合 |
| `src/agent/` 模块直接单元测试 | ✅ | 6 文件、142 测试覆盖 6 个 M2/M3 核心模块 |
| **M4a 人审状态机最小实现** | ✅ | DecisionStatus enum + decision.yml + decision_log.yml + verification_summary.yml，529 测试零回归 |

### v2.0 短期（P0——文档对齐）

- ✅ 状态对账——README 待办 vs 代码真实状态（本次）
- ✅ 文档同步——README / AGENTS.md / PROJECT_STATUS.md（本次）

### v2.0 中期（P1——质量加固）

- ✅ `src/agent/` 模块直接单元测试——142 个测试，475 总测试零回归
- 完整 DAG 端到端测试——5 步管道 + 中间表管理
- Prompt 回归系统正式运行（`regression_baseline.yml` 基线，需 LLM API）

### v2.0 长期（P2——功能补全）

- Spark 真实只读样本执行（`spark_executor.py` 去桩）
- 真实 SQL/Spark 双结果交叉验证（需 Spark 环境）
- 人审状态机
- LLM 接入 M2 代码生成
- KEY_MERGE 增量策略
- 多环境部署（开发/测试/生产 DuckDB 路径切换）
- CI/CD 门禁接入——pre-commit hook + GitHub Actions

### v1.x 保留

- v1 pipeline 不删除、不重构——保留为确定性验证底座

---

## 八、已知问题与风险

| # | 问题 | 严重度 | 状态 |
|----|------|--------|------|
| 1 | **Prompt 回归系统未运行**——`regression_baseline.yml` 基线仍为 pending，真实 LLM 回归未执行 | 🟡 中 | 已规划，待 LLM API 就绪 |
| 2 | **ColumnBindingTable 依赖静态 backup**——指标注册依赖数据库 `meta.metric_definitions` + fallback 静态列表。已添加 `get_load_status()` 诊断函数 | 🟡 中 | 已缓解 |
| 3 | **KEY_MERGE 策略暂未实现**——需数据库 MERGE/UPSERT 支持 | 🟢 低 | 未来里程碑 |
| 4 | **DuckDB 分区覆盖降级为全量覆盖**——DuckDB 不支持 Hive 风格分区语法 | 🟢 低 | 设计如此——通过不同表名模拟分区 |
| 5 | **无完整 DAG 端到端测试**——PipelinePlan 单步测试覆盖，多步 DAG 执行未测试 | 🟡 中 | v2.0 中期 |
| 6 | `gold.fact_tif_payments` 缺少 dim_date JOIN 路径 | 🔴 已修复 | 2026-06-14：已添加白名单路径 |
| 7 | **Spark executor 是桩**——`spark_executor.py` 始终返回 SKIPPED/PENDING，交叉验证永远无法真实执行 | 🟡 中 | 待 Spark 环境就绪 |
| 8 | **`src/agent/` 直接单元测试已补齐**——6 文件、142 测试覆盖 6 个 M2/M3 核心模块 | 🟢 已修复 | 2026-06-17：6 个测试文件已提交 |

### 已修复的安全问题（2026-06-14 安全审计）

| # | 问题 | 严重度 | 修复措施 |
|----|------|--------|---------|
| P0-1 | G2 降级日期过滤违规——`_is_date_key_column` 启发式不可靠 | 🔴 已修复 | 改为硬门禁：G2+日期过滤→强制 requires_dim_date=True，缺少 dim_date JOIN 路径时拒绝编译 |
| P0-2 | 跨域 JOIN 表集合顺序不稳定——`set()` 迭代非确定性 | 🔴 已修复 | `set()` → `sorted(tables)` 保证字母序确定性 |
| P0-3 | 多表 JOIN 别名列引用不一致——`_resolve_column_ref` 缺少防御性校验 | 🔴 已修复 | 添加残留全限定表名检测，不匹配时抛出 SQLCompileError |
| P1-1 | ColumnBindingTable 硬编码——10 个指标静态写入 | 🟡 已缓解 | 添加 `get_load_status()` 诊断函数，追踪加载来源（tianShu/static_fallback/not_attempted） |
| P1-2 | CLI Windows GBK 控制台 UnicodeEncodeError | 🟡 已修复 | 模块加载时执行 `_wrap_stdio_utf8()`，同时包装 stdout/stderr 为 UTF-8 |
| P2 | Quality check 覆盖太浅 + 无 .gitignore | 🟡 已修复 | 新增 5 项检查（G2 dim_date 覆盖/JOIN 白名单/合约结构/SQL 编译/加载状态）；创建 `.gitignore` |

---

## 九、快速命令

| 操作 | 命令 |
|------|------|
| 运行全部测试 | `python -m pytest tests/ -v` |
| 运行 quality check（12 项检查） | `python scripts/quality/check_pipeline.py --verbose` |
| 运行 dry-run（不执行 SQL） | `python scripts/pipeline/run_pipeline.py -r fixtures/requirements/trip_daily_report.yml --dry-run` |
| 查看最近提交 | `git log --oneline -10` |
| 查看当前分支 | `git branch` |
| 查看事实源加载状态 | `python -c "from scripts.pipeline.column_binding import get_load_status; print(get_load_status())"` |

---

## 十、Git 信息

| 字段 | 值 |
|------|-----|
| 当前分支 | `main` |
| 最近提交 | `0667714` — Phase 3 记忆系统 + 变更传播闭环 |
| 未提交变更 | 有（`layer3_plan.py`、`layer4_generate.py`、`layer4_expression.py` 等修改未 commit） |
