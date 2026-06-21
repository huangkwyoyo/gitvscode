# TianShu Data Dev Agent

基于 TianShu 数据仓库（DuckDB + NYC 城市交通数据）的 **AI 辅助数据开发工具**。它不是直接生产数据的 Agent，而是生成代码、验证代码、输出 Review Package（审查材料包）的开发辅助系统。

## 定位

- **AI 辅助数据开发**：Agent 生成代码、验证代码、输出 Review Package
- **最终产物不是生产数据**：Agent 的最终产物是 Review Package（审查材料包）
- **人是最终决策者**：人审查 SQL、Spark DSL、测试结果和不确定项后决定是否上线
- **LLM 可生成代码草案**：SQL、Spark DSL、Python 测试、配置、文档都属于不可信草案
- **数据执行必须过 Validator**：v2 主链路任何 SQL/Spark 代码执行前都必须通过安全校验，只允许 SELECT 和 WITH SELECT（CTE 查询），只能连接开发环境，只读、限行、限时。v1 pipeline 保留写操作编译和静态校验能力，但当前未接入可写执行器（`read_only=True`）
- **Agent 不越权**：Agent 不能上线、不能写生产库、不能绕过人审
- **代码可追溯**：所有表/字段引用标注来源
- **禁止查询 Bronze/Silver 层**

## 快速开始

### 1. 环境要求

- Python 3.10+
- duckdb, pandas, pyarrow, pyyaml
- TianShu DuckDB 数据库文件（`nyc_transport.duckdb`）

### 2. 安装依赖

```powershell
pip install duckdb pandas pyarrow pyyaml
```

### 3. 运行当前验证工具

```powershell
# Windows 控制台：推荐先设置 UTF-8 编码（避免 GBK 字符集报错）
set PYTHONIOENCODING=utf-8

# 当前可用：对示例需求执行 SQL 编译和校验 dry-run
python scripts\pipeline\run_pipeline.py -r fixtures\requirements\trip_daily_report.yml --dry-run

# 详细日志
python scripts\pipeline\run_pipeline.py -r fixtures\requirements\trip_daily_report.yml --dry-run -v
```

> **Windows 兼容性说明**：管道自动尝试将 stdout 重配为 UTF-8 编码。若仍遇到 `UnicodeEncodeError`，请在运行前执行 `set PYTHONIOENCODING=utf-8`，或在 PowerShell 中使用 `$env:PYTHONIOENCODING="utf-8"`。

### 4. 运行质量检查

```powershell
python scripts\quality\check_pipeline.py
```

### 5. 运行测试

```powershell
python -m pytest tests\test_pipeline.py -v
```

## 架构

```
需求输入（YAML 或自然语言）
  → [阶段 1] 需求分析
  → [阶段 2] 方案设计
  → [阶段 3] 代码生成（SQL + Spark DSL + 测试 + 配置）
  ═══════════ 不可信草案边界 ═══════════
  → [阶段 4] 自动验证（Validator + 只读样本执行 + 交叉验证）
  → [阶段 5] Review Package 输出
  ═══════════════ 人审闸门 ═══════════════
  → [阶段 6] 人审决策（人决定：批准 / 修改 / 拒绝）
```

核心边界：

- **代码生成边界**：LLM 可以写 SQL、Spark DSL、Python 测试、配置和文档，但全部是不可信草案。
- **数据执行边界**：v2 主链路任何 SQL/Spark 代码执行前必须过 Validator，只允许 SELECT 和 WITH SELECT（CTE 查询），只能连接开发环境，只读、限行、限时。Agent 不能上线、不能写生产库、不能绕过人审。v1 pipeline 保留写操作（CTAS/INSERT/VIEW）编译和静态校验能力，但当前未接入可写执行器（Layer 6 `read_only=True`）。

## 目录结构

```
TianShu Data Dev Agent/
├── AGENTS.md                    # 核心规则（10 部分）
├── contracts/                   # 数据契约层
├── fixtures/requirements/       # 示例需求（3 个）
├── evals/                       # 评测用例
├── harness/                     # 工程执行入口
├── src/
│   ├── ir/                      # v2.0 中间表示和审查材料类型
│   ├── agent/                   # v2.0 代码生成编排（M2/M3 workflow）
│   ├── verify/                  # Validator 与交叉验证
│   ├── sandbox/                 # 开发环境只读执行器
│   └── compile/                 # 确定性编译组件
├── scripts/
│   ├── pipeline/               # v1.x 确定性管道，保留为验证底座（legacy）
│   ├── dev_agent/               # v2.0 CLI 入口（build + verify review package）
│   └── quality/                # 质量检查入口
├── generated/                   # Review Package 和验证产物
│   └── review_packages/         # M2 审查材料包
├── tests/                       # 测试（669 passed）
└── docs/                        # 设计文档
```

## ColumnBindingTable

系统的中枢神经——维护所有已注册指标到物理列的确定性映射。

**启动时从 TianShu DuckDB 的 `meta.metric_definitions` 动态加载**已审批指标定义，静态绑定作为 fallback。支持通过 `reload_bindings()` 热重载。

| 指标 | G3 列 | G2 表达式 |
|------|-------|----------|
| trip_count | gold.dws_daily_trip_summary.trip_count | COUNT(*) |
| total_fare_amount | gold.dws_daily_trip_summary.total_fare_amount | SUM(fare_amount) |
| ... | ... | ... |

LLM 可以在生成草案时引用绑定结果，但不得修改绑定表。绑定表只能由事实源加载器和受控配置更新。

### G2 日期过滤契约

G2 fact 表的日期列是整数代理键（如 `pickup_date_key`），**不能直接与字符串日期比较**。管道自动检测并在 G2 降级时：
1. 自动 JOIN `gold.dim_date`
2. 通过 `dim_date.date`（实际 DATE 类型）过滤，而非 `fact_table._date_key`（整数）
3. Layer 5 校验 **requires_date_dim** 确保 dim_date 已正确 JOIN

## 注册指标

当前注册 10 个指标，覆盖 4 个业务域：

| 域 | 指标 |
|----|------|
| traffic（行程） | trip_count, total_fare_amount, total_tip_amount, total_distance_miles |
| violation（违章） | parking_violation_count, standard_fine_total |
| safety（安全） | crash_count, persons_killed, persons_injured |
| supply（供给） | tif_payment_amount |

## 当前实现状态

### M5a 部署绑定

- `sql/main.sql`、`spark/main.py`：唯一权威转换内核，继续只读验证。
- `deploy/main.sql`、`deploy/main.py`：由确定性生成器创建的写入外壳，不重新生成业务逻辑。
- `deployment_manifest.yml`：绑定双内核哈希、目标表、写入策略、分区和 `generated` 写入边界。
- `APPROVED`：仅表示查询逻辑已由人审查，不代表可以发布。
- `RELEASE_APPROVED`：仅人可设置，必须通过部署静态检查和七类 artifact 严格哈希校验。
- M5a 不执行任何写操作；一次性可写 Sandbox 留到 M5b。

### M5b-0 设计与威胁模型

- ✅ 一次性可写 DuckDB Sandbox 设计文档：`docs/m5b_duckdb_sandbox_design_20260619_2230.md`
- 定义了完整生命周期、操作白名单、15 项物化验证、materialization 状态机、RELEASE_APPROVED 前置条件链和 15 项威胁模型。
- 暂缓：INSERT 策略、Spark Sandbox、LLM、CI/CD。

### M5b-1 DuckDB CTAS Sandbox

- ✅ `src/sandbox/duckdb_ctas_executor.py`——一次性可写 Sandbox，12 步生命周期 + 操作白名单 + 物化验证
- ✅ `src/verify/materialization_validator.py`——15 项物化静态检查 + 物化状态机
- ✅ `tests/test_m5b1_duckdb_ctas_sandbox.py`——120 测试覆盖安全、执行、幂等、隔离、清理、状态机

### ✅ 已完成

- [x] **M2 Review Package 完整生成**——`src/agent/workflow.py` → `build_review_package()` 输出 9 文件审查材料包
- [x] **SQL + Spark DSL 双份草案确定性生成**——`src/agent/dual_code_generator.py` 根据 fixture 生成两份独立实现
- [x] **M3 Verification Engine 完整串联**——静态检查 + SQL 样本执行 + Spark 受控执行 + 7 维度交叉验证
- [x] **Spark 只读样本执行**——`src/sandbox/spark_executor.py` 12 层防御受控执行（PySpark 不可用时 SKIPPED）
- [x] **SQL/Spark 交叉验证**——`src/verify/cross_validation.py` 7 维度比较（列名/类型/行数/抽样行/空值/数值合计/快照哈希）
- [x] **M4 人审状态机**——DecisionStatus enum + decision.yml + decision_log.yml + CLI + SUPERSEDED 自动转换
- [x] **M5a 部署绑定**——双内核 Manifest、确定性部署外壳、双审批快照、篡改失效
- [x] **M5b-1 CTAS Sandbox**——一次性可写执行器 + 物化验证 + 幂等检查
- [x] **3 批次修复 + 安全压实**——669 测试零回归

### ⚠️ 部分完成

- [ ] **Spark 交叉验证**——Spark 可用时产出 CONSISTENT_SAMPLE，PySpark 不可用时 NOT_EXECUTED
- [ ] **物化验证**——单表 CTAS 已实现，多表 JOIN / INSERT 策略延后

### ❌ 待完成

- [ ] LLM 接入 M2 代码生成（当前为确定性模板）
- [ ] Prompt 回归系统
- [ ] ColumnBindingTable 动态加载增强
- [ ] 完整 DAG 端到端测试
- [ ] KEY_MERGE 增量策略

## v2 CLI 入口

```powershell
# M2：生成 Review Package（确定性，不接 LLM、不执行 SQL）
python scripts/dev_agent/build_review_package.py -r fixtures/requirements/trip_daily_report.yml

# M3：验证 Review Package（静态检查 + SQL 样本执行 + 交叉验证）
python scripts/dev_agent/verify_review_package.py -p generated/review_packages/trip_daily_report_m2

# v1 legacy pipeline（保留为验证底座，不是 v2 主入口）
python scripts/pipeline/run_pipeline.py -r fixtures/requirements/trip_daily_report.yml --dry-run
```

## 已知局限

- **不接真实 LLM API**——M2 代码生成使用确定性模板，不调 LLM
- **不自动上线**——Agent 没有部署权限，所有上线由人执行
- **不写生产库**——Agent 只能连开发库，只读、限行、限时
- **Spark 不可用时为 SKIPPED/PENDING**——不能说 Spark 已完整验证
- **`decision.md` 是人审模板**，不是完整审批系统
- **交叉验证始终 SKIPPED**——因 Spark executor 是桩
- **`scripts/pipeline/run_pipeline.py` 是 v1 legacy pipeline**，不是 v2 主入口

## 当前不做

- 不删除 `scripts/pipeline/`。
- 不改变当前运行入口。
- 不接入真实 LLM API。
- 不触发发布或部署。
- 不写生产库。
