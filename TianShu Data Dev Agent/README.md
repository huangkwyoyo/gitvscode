# TianShu Data Dev Agent

基于 TianShu 数据仓库（DuckDB + NYC 城市交通数据）的 **AI 辅助数据开发工具**。它不是直接生产数据的 Agent，而是生成代码、验证代码、输出 Review Package（审查材料包）的开发辅助系统。

## 定位

- **AI 辅助数据开发**：Agent 生成代码、验证代码、输出 Review Package
- **最终产物不是生产数据**：Agent 的最终产物是 Review Package（审查材料包）
- **人是最终决策者**：人审查 SQL、Spark DSL、测试结果和不确定项后决定是否上线
- **LLM 可生成代码草案**：SQL、Spark DSL、Python 测试、配置、文档都属于不可信草案
- **数据执行必须过 Validator**：任何 SQL/Spark 代码执行前都必须通过安全校验，只能连接开发环境，只读、限行、限时
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
- **数据执行边界**：任何 SQL/Spark 代码执行前必须过 Validator，只能连接开发环境，只读、限行、限时。Agent 不能上线、不能写生产库、不能绕过人审。

## 目录结构

```
TianShu Data Dev Agent/
├── AGENTS.md                    # 核心规则（5部分）
├── contracts/                   # 数据契约层
├── fixtures/requirements/       # 示例需求（3个）
├── evals/                       # 评测用例
├── harness/                     # 工程执行入口
├── src/
│   ├── ir/                      # v2.0 中间表示和审查材料类型
│   ├── verify/                  # Validator 与交叉验证
│   ├── sandbox/                 # 开发环境只读执行器
│   └── compile/                 # 确定性编译组件
├── scripts/
│   ├── pipeline/               # v1.x 确定性管道，保留为验证底座
│   └── quality/                # 质量检查入口
├── generated/                   # Review Package 和验证产物
├── tests/                       # 测试
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

## 下一步

- [ ] 建立 `generated/review_packages/{request_id}/` 审查材料包结构
- [ ] 生成 SQL + Spark DSL 双份代码草案
- [ ] 实现 SQL/Spark 静态校验和只读样本执行
- [ ] 输出交叉验证报告和 `decision.md`
- [ ] 接入人审状态：批准 / 修改后重审 / 拒绝

## 当前不做

- 不删除 `scripts/pipeline/`。
- 不改变当前运行入口。
- 不接入真实 LLM API。
- 不触发发布或部署。
- 不写生产库。
