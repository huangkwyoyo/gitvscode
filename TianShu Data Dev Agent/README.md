# TianShu Data Dev Agent

基于 TianShu 数据仓库（DuckDB + NYC 城市交通数据）的**确定性数据生产管道系统**。

## 定位

- **不是聊天机器人**，是数据生产管道
- **LLM 不允许生成 SQL**——SQL 由 ColumnBindingTable + 模板编译器确定性生成
- **优先使用 Gold G3 汇总表**，G3 不可用时降级到 G2 fact 表
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

### 3. 运行管道

```powershell
# Windows 控制台：推荐先设置 UTF-8 编码（避免 GBK 字符集报错）
set PYTHONIOENCODING=utf-8

# 完整管道（8层全链路，从需求到结果文件）
python scripts\pipeline\run_pipeline.py -r fixtures\requirements\trip_daily_report.yml

# 仅校验不执行（dry-run）
python scripts\pipeline\run_pipeline.py -r fixtures\requirements\trip_daily_report.yml --dry-run

# 详细日志
python scripts\pipeline\run_pipeline.py -r fixtures\requirements\trip_daily_report.yml -v
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
YAML需求说明书
  → [Layer 1] 需求解析（规则解析器）
  → [Layer 2] 意图理解（LLM 辅助，仅输出 JSON）
  ═══════════ LLM 边界 ═══════════
  → [Layer 3] SQLPlan 构造（确定性，查 ColumnBindingTable）
  → [Layer 4] SQL 编译（模板编译器，零 LLM）
  → [Layer 5] SQL 校验（规则引擎，安全+语义）
  → [Layer 6] SQL 执行（DuckDB 只读）
  → [Layer 7] 结果评估（统计检查）
  → [Layer 8] 产物输出（结果文件 + 报告 + 任务配置）
```

## 目录结构

```
TianShu Data Dev Agent/
├── AGENTS.md                    # 核心规则（5部分）
├── contracts/                   # 数据契约层
├── fixtures/requirements/       # 示例需求（3个）
├── evals/                       # 评测用例
├── harness/                     # 工程执行入口
├── scripts/
│   ├── pipeline/               # 8层管道实现
│   │   ├── run_pipeline.py     # 管道主入口
│   │   └── column_binding.py   # ColumnBindingTable
│   └── quality/                # 质量检查
├── generated/                   # 产出目录
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

**LLM 不允许读取或修改此表**。它是 Layer 3（规划层）和 Layer 4（SQL编译层）的专用数据源。

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

- [ ] Phase 2：DAG 多步依赖（JoinGraph 扩展至 N 表）
- [ ] Phase 2：调度平台任务配置自动生成
- [ ] Phase 2：自动回归测试生成
- [ ] Phase 2：LLM 消歧对话集成（Layer 2 反问机制）
