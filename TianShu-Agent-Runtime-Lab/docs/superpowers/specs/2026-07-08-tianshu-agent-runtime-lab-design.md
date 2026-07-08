# TianShu-Agent-Runtime-Lab 设计规格

> 基于 TianShu-Agent-Runtime-Lab实操学习项目方案书_20260627_2245.md 的设计实现规格
> 生成时间：2026-07-08
> 状态：定稿

---

## 1. 项目定位

面向数据工程 Agent 的单 Agent Runtime 实操训练项目。用 TianShu 数仓语境训练 Runtime 核心能力，不接真实数据库，全部使用手写 fixture 文件。

## 2. 项目位置

`D:\Program Files\gitvscode\TianShu-Agent-Runtime-Lab\`

与 TianShu-DataDev-Agent-v3、TianShu-Text2SQL-Lite 等平级，位于同一个 Git 根仓库下。

## 3. 开发方式

- **五周分步迭代**（方案 A：骨架先行，Demo 逐周叠加）
- **LangGraph 从零学起**，每周聚焦有限的新概念
- **手写 fixture 完全与生产隔离**
- **目录结构按方案书框架，实现过程灵活调整**

## 4. 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 主开发语言 |
| LangGraph | 0.4+ | 单 Agent Runtime 编排 |
| Pydantic | 2+ | State、IR、工具输入输出模型 |
| SQLite | 内置 | 本地保存 checkpoint、trace、approval |
| Typer | 0.12+ | CLI 入口 |
| pytest | 8+ | 自动化测试 |
| PyYAML | 6+ | 读取 fixture 契约 |

第一版不引入：FastAPI、Web 前端、真实 DuckDB、真实生产契约、多 Agent、长期 Memory。

## 5. 目录结构

```
TianShu-Agent-Runtime-Lab/
├── pyproject.toml                  # 项目配置与依赖
├── README.md                       # 项目说明
├── .gitignore

├── src/runtime_lab/
│   ├── __init__.py
│   ├── app.py                      # Typer CLI 入口
│   ├── graph.py                    # LangGraph 主图
│   ├── state.py                    # RuntimeState 定义
│   ├── config.py                   # 本地路径配置
│   │
│   ├── nodes/                      # LangGraph 节点（按周增量添加）
│   │   ├── __init__.py
│   │   ├── classify.py             # [W1] 任务分类
│   │   ├── plan.py                 # [W2] 规划节点
│   │   ├── validate.py             # [W2] 校验节点
│   │   ├── execute_tool.py         # [W2] 工具执行节点
│   │   ├── interrupt.py            # [W4] 中断节点
│   │   ├── summarize.py            # [W1] 总结节点
│   │   └── replay.py               # [W5] 回放与分叉节点
│   │
│   ├── tools/                      # 受控工具集（按 Demo 分文件）
│   │   ├── __init__.py
│   │   ├── sql_review_tools.py     # [W2] SQL 审查工具
│   │   ├── contract_tools.py       # [W3] 契约工具
│   │   ├── join_tools.py           # [W4] Join 工具
│   │   └── datadev_tools.py        # [W5] DataDev 工具
│   │
│   ├── models/                     # Pydantic 结构化模型
│   │   ├── __init__.py
│   │   ├── common.py               # [W1] 通用模型（RiskLevel, Finding 等）
│   │   ├── sql_review.py           # [W2] SQL Review 模型
│   │   ├── contracts.py            # [W3] 契约检查模型
│   │   ├── joins.py                # [W4] Join 审批模型
│   │   └── datadev_plan.py         # [W5] DataDev Plan 模型
│   │
│   ├── storage/                    # 持久化存储层
│   │   ├── __init__.py
│   │   ├── checkpoints.py          # [W4/W5] Checkpoint 存储
│   │   ├── trace_store.py          # [W1] Trace 与审计存储
│   │   ├── approval_store.py       # [W4] 审批记录存储
│   │   └── artifact_store.py       # [W5] 产物 hash 存储
│   │
│   ├── policies/                   # 策略层
│   │   ├── __init__.py
│   │   ├── risk_policy.py          # [W2] 风险等级判断
│   │   ├── fail_closed.py          # [W2] 失败封闭策略
│   │   └── approval_policy.py      # [W4] 审批策略
│   │
│   └── reports/                    # 报告生成
│       ├── __init__.py
│       ├── run_report.py           # [W2] 运行报告生成
│       └── plan_diff.py            # [W5] Plan Diff 生成
│
├── fixtures/                       # 学习用假数据（与生产隔离）
│   ├── contracts/
│   │   ├── semantic_contract.yml   # [W3] 语义契约
│   │   ├── metric_contract.yml     # [W3] 指标契约
│   │   └── sql_safety_policy.yml   # [W2] SQL 安全策略
│   ├── sql/
│   │   ├── safe_query.sql          # [W2] 安全 SQL 示例
│   │   ├── unsafe_query.sql        # [W2] 含 DDL/DML 的 SQL
│   │   ├── missing_partition.sql   # [W2] 缺少分区条件的 SQL
│   │   └── ambiguous_join.sql      # [W2] Join 关系不明确的 SQL
│   └── datadev/
│       ├── developer_spec_valid.md         # [W5] 正常 Plan 规约
│       └── developer_spec_missing_join.md  # [W5] 缺少 Join 的规约
│
├── runs/                           # 本地运行产物（gitignore）
│   └── .gitkeep
│
├── tests/                          # 自动化测试
│   ├── __init__.py
│   ├── test_skeleton.py            # [W1] 骨架验收
│   ├── test_sql_review_runtime.py  # [W2]
│   ├── test_contract_inspector_runtime.py # [W3]
│   ├── test_join_approval_runtime.py      # [W4]
│   ├── test_datadev_replay_runtime.py     # [W5]
│   ├── test_checkpoint_resume.py   # [W4]
│   └── test_trace_audit.py         # [W1]
│
└── docs/
    └── superpowers/
        └── specs/
            └── (本文件)
```

## 6. 通用 Runtime 流程

四个 Demo 共用一套 Runtime 图：

```
用户输入
  ↓
初始化 RuntimeState
  ↓
classify_task：识别 Demo 类型
  ↓
plan_next_step：决定下一步动作
  ↓
call_tool：调用受控工具
  ↓
validate_result：校验工具结果和结构化输出
  ↓
risk_gate：风险判断
  ├─ 可自动继续 → 下一节点
  ├─ 需要人工审批 → interrupt
  └─ 不可恢复风险 → failed_closed
  ↓
summarize：生成最终报告
  ↓
write_trace：写入审计记录
```

## 7. RuntimeState 设计

```python
@dataclass
class RuntimeState:
    # 运行标识
    run_id: str
    thread_id: str

    # 输入与分类
    user_input: str
    demo_type: str              # "sql_review" | "contract" | "join" | "datadev"

    # 执行流转
    current_step: str           # 当前执行步骤
    next_action: str            # 下一步动作
    status: str                 # init | running | waiting_approval | completed | failed_closed

    # 中间产物（按需扩展）
    intermediate: dict

    # 工具调用历史
    tool_call_history: list

    # 错误记录
    errors: list

    # 元信息
    created_at: str
    updated_at: str
```

关键原则：
- 每个节点只读写明确字段
- 每一步状态变化都保存到 state_history.jsonl
- 不可变历史：已完成的状态不允许回退修改

## 8. 五周交付计划

### 第 1 周：Runtime 骨架

**目标**：最小化可运行 Runtime，验证框架从 CLI 启动 → 走通图 → 写 trace 的完整链路。

**新增文件**：
- `src/runtime_lab/app.py` — Typer CLI（支持 `greet` 命令）
- `src/runtime_lab/graph.py` — 最小 2 节点 LangGraph（classify → summarize）
- `src/runtime_lab/state.py` — RuntimeState 基础定义
- `src/runtime_lab/config.py` — 路径配置
- `src/runtime_lab/storage/trace_store.py` — 最小 trace 存储
- `src/runtime_lab/nodes/classify.py` — 仅支持 greet 的分类
- `src/runtime_lab/nodes/summarize.py` — 简单总结
- `tests/test_skeleton.py` — 骨架验收测试

**验收**：
```bash
python -m runtime_lab greet
# 输出包含 Status: completed, Trace 路径, Report 路径
pytest tests/test_skeleton.py -v  # 全部通过
```

### 第 2 周：SQL Review Runtime（Demo 1）

**目标**：完整的工具调用 + 结构化输出 + 风险判断 + fail-closed。

**新概念**：工具 schema 定义、结构化输出校验、risk_gate 条件边、生成 run_report.md。

**新增文件**：
- `tools/sql_review_tools.py` — 6 个 SQL 审查工具
- `models/common.py` — RiskLevel、Finding、Decision
- `models/sql_review.py` — SQLReviewResult
- `nodes/plan.py` — 规划下一步
- `nodes/validate.py` — 结构化校验
- `nodes/execute_tool.py` — 统一工具调用
- `policies/risk_policy.py` — 风险判断
- `policies/fail_closed.py` — 失败封闭
- `reports/run_report.py` — 报告生成
- `fixtures/sql/` — 4 个示例 SQL
- `fixtures/contracts/sql_safety_policy.yml`
- `tests/test_sql_review_runtime.py`

**验收**：
```bash
python -m runtime_lab sql-review fixtures/sql/unsafe_query.sql
# → Final Status: failed_closed, Reason: SQL contains forbidden operation
python -m runtime_lab sql-review fixtures/sql/safe_query.sql
# → Final Status: completed
```

### 第 3 周：Contract Inspector Runtime（Demo 2）

**目标**：Agent 依赖契约文件作为事实源，不凭 LLM 编造。实现三种输出：answer / clarification / refusal。

**新概念**：契约读取与解析、G3/G2 路径判断、多路由输出。

**新增文件**：
- `tools/contract_tools.py` — 5 个契约检查工具
- `models/contracts.py` — 契约模型
- `fixtures/contracts/semantic_contract.yml`
- `fixtures/contracts/metric_contract.yml`
- `tests/test_contract_inspector_runtime.py`

**验收**：
- 未注册指标 → clarification 或 refusal
- 维度不明确 → clarification
- G3 不覆盖但 G2 有安全路径 → answer + downgrade_reason
- 契约文件缺失 → failed_closed

### 第 4 周：Join Approval Runtime（Demo 3）

**目标**：Human-in-the-Loop，低置信 Join 不能自动放行。

**新概念**：interrupt/resume、checkpoint 保存与恢复、审批记录。

**新增文件**：
- `tools/join_tools.py` — 证据收集与等级分类
- `models/joins.py` — JoinCandidate、EvidenceLevel、ApprovalRecord
- `storage/checkpoints.py` — checkpoint 保存与读取
- `storage/approval_store.py` — 审批记录
- `nodes/interrupt.py` — 中断节点
- `policies/approval_policy.py` — 审批触发策略
- `tests/test_join_approval_runtime.py`
- `tests/test_checkpoint_resume.py`

**证据等级**：
| 等级 | 条件 | 行为 |
|------|------|------|
| STRONG | 契约显式声明或外键明确 | 自动继续 |
| MEDIUM | 字段名归一化匹配，无显式声明 | 中断等审批 |
| WEAK | 仅字段名相似 | failed_closed |
| NONE | 无任何证据 | failed_closed |

**验收**：
- MEDIUM 必须进入 waiting_approval
- 未审批不能继续
- 审批后仅从 checkpoint 恢复
- WEAK/NONE 不能被 LLM 自动放行

### 第 5 周：DataDev Plan Replay Runtime（Demo 4）

**目标**：checkpoint、replay、fork 和 artifact lineage。

**新概念**：Plan 生成、多条运行路径、Fork 不覆盖原运行、plan diff。

**新增文件**：
- `tools/datadev_tools.py` — Plan 生成与编译工具
- `models/datadev_plan.py` — Plan 模型
- `storage/artifact_store.py` — 产物 hash 与 provenance
- `nodes/replay.py` — 回放与分叉
- `reports/plan_diff.py` — Plan 差异报告
- `fixtures/datadev/` — 2 个 DeveloperSpec
- `tests/test_datadev_replay_runtime.py`

**三条运行路径**：
- **Path A**：首次运行，Join 校验失败，checkpoint 保存
- **Path B**：人工补充 Join 后从 checkpoint resume
- **Path C**：从历史 checkpoint fork，新 run_id，生成 plan_diff.md

## 9. 统一运行输出

每次运行生成目录：

```
runs/{run_id}/
  state_history.jsonl             # 每一步 State 变化
  tool_calls.jsonl                # 工具调用记录
  approvals.jsonl                 # 人工审批记录
  errors.jsonl                    # 错误与失败封闭原因

  artifacts/
    input.json                    # 规范化输入
    output.json                   # 最终结构化输出
    plan.json                     # 中间 Plan
    provenance.yml                # 产物来源与 hash

  reports/
    run_report.md                 # 本次运行总结
    trace.md                      # 可读追踪记录
    plan_diff.md                  # Replay/Fork 方案差异
```

## 10. 设计原则

| 原则 | 说明 |
|------|------|
| 增量开发 | 每周只加该周需要的文件，不提前建空文件 |
| 测试同步 | 功能代码与测试代码同一周写 |
| CLI 入口 | 每完成一个 Demo，app.py 加对应命令 |
| LangGraph 渐进 | 第 1 周 2 节点 → 第 2 周 5 节点 → 第 4 周加入 interrupt |
| 统一输出 | 所有 Demo 输出到 runs/{run_id}/ 统一格式 |
| 不接真实库 | 全部使用本地 fixture 文件 |
| 失败封闭 | 安全问题时停止执行，不猜测继续 |
