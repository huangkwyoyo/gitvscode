# Data Dev Agent 文档导航

> 版本：v2.0 | 日期：2026-06-16

---

## 核心思想

**Agent 从"生产执行者"变成"代码生成者 + 自测者"，人从"旁观者"变成"最终决策者"。**

所有文档围绕同一条逻辑链展开：

```
数据开发的现实：最终上线决定始终在人
  → 旧架构的"无人审查"假设是错的
  → Agent 角色应从"生产执行者"变为"代码生成者 + 自测者"
  → 人的角色应从"旁观者"变为"最终决策者"
  → 安全模型应从"隔离 LLM"变为"双层边界 + 三道防线"
      边界 1：代码生成（LLM 自由发挥，产物 = 不可信补丁）
      边界 2：数据执行（唯一校验通道，约束在执行端而非生成端）
  → 四个关键机制支撑这个模型：
      来源追溯（降低人审成本）
      自动验证 7 项检查（Agent 自测，拦截低级错误）
      SQL + PySpark 交叉验证（双份独立代码相互校验，发现逻辑不一致）
      人审闸门（人的判断力，处理复杂决策）
```

---

## 文档体系

```
AGENTS.md                                   ← 入口：核心规则
  §1  核心思想：角色转变
  §2  工作流
  §3  Agent 的权限边界：双层边界 ★
       边界 1：代码生成边界（LLM 可以生成代码，产物 = 不可信补丁）
       边界 2：数据执行边界（唯一通道：Validator → Executor）
  §4  安全模型：三道防线 + 交叉验证 ★
  §5  数据契约（含双份代码输出）
  §6  失败处理
  §7  开发规范
  §8  禁止事项
  §9  架构决策记录（含双层边界、双份代码交叉验证）

docs/
├── README.md                               ← 你正在看的：文档导航
├── 数据开发Agent工作流_20260616_2230.md      ← 工作流详解 ★ 已更新
│   §一 角色分工：一条线分两边（Agent工作区 vs 人决策区）
│   §二 逐阶段详解：
│       阶段 3：双轨代码生成（SQL + PySpark）
│       阶段 4：7 项自动验证 + 交叉验证
│       阶段 5：材料输出（含交叉验证报告）
│       阶段 6：人审上线（交叉验证如何影响决策）
│   §三 Agent的"自测"能力（含交叉验证的补充作用）
├── 数据开发Agent工程词典_20260616_2230.md    ← 术语定义 ★ 已更新
│   §1 核心概念：角色转变 + 双层边界（7 个术语★）
│   §2 来源追溯
│   §3 Agent生成代码的参考数据源
│   §4 自动验证（Agent的自测能力）——7 项检查 + 交叉验证 + Spark DSL（5 个术语★）
│   §5 人审闸门（含交叉验证如何辅助人审）
│   §6 废弃概念
└── superpowers/specs/
    ├── 数据开发Agent设计文档v2_20260616_2230.md  ← 设计文档
    │   §1 设计动机：为什么角色要变
    │   §2 架构总览
    │   §3 安全模型：三道防线
    │   §4 关键设计决策
    └── 架构方向变更记录_20260616_2230.md         ← 变更记录
        §一 为什么变
        §二 变了什么
        §三 保留了什么
        §四 废弃了什么

Obsidian/
└── 两种Agent架构对比_IR边界与LLM角色_20260616_2230.md  ← 架构对比
    §一 三种助手比喻（即时应答 vs 捆住手 vs 研发助手）
    §二 角色转变是理解一切的关键
    §三 新架构的关键机制
    §四 核心知识点
```

> ★ 标记项为 2026-06-16 更新的内容：双层边界框架、双份代码生成、SQL + PySpark 交叉验证。

---

## 按读者导航

### 我想快速了解这个项目
→ `AGENTS.md` §1-§3（10 分钟）
→ `docs/数据开发Agent工作流_20260616_2230.md` §一-§二（15 分钟）

### 我想理解为什么从 v1.x 变成 v2.0
→ `docs/superpowers/specs/架构方向变更记录_20260616_2230.md`（10 分钟）
→ `AGENTS.md` §1（5 分钟）

### 我想理解双层边界是什么
→ `AGENTS.md` §3（10 分钟）——完整的双层边界框架
→ `docs/数据开发Agent工程词典_20260616_2230.md` §1 术语 4-7（10 分钟）

### 我想理解为什么 Agent 要生成两份代码
→ `docs/数据开发Agent工作流_20260616_2230.md` §二 阶段 3-4（15 分钟）——双轨生成 + 交叉验证流程
→ `docs/数据开发Agent工程词典_20260616_2230.md` §4 术语 15-16（10 分钟）——交叉验证 + Spark DSL

### 我是数据工程师，想知道 Agent 怎么生成代码
→ `docs/数据开发Agent工作流_20260616_2230.md` §二 阶段 1-3
→ `AGENTS.md` §3 双层边界
→ `docs/数据开发Agent工程词典_20260616_2230.md` §3

### 我是架构师，想审查安全模型
→ `AGENTS.md` §3（双层边界）+ §4（三道防线 + 交叉验证）
→ `docs/数据开发Agent工程词典_20260616_2230.md` §4-§5
→ `docs/superpowers/specs/数据开发Agent设计文档v2_20260616_2230.md` §3-§4

### 我想了解 Data Dev Agent 和 Text2SQL Agent 的区别
→ `Obsidian/两种Agent架构对比_IR边界与LLM角色_20260616_2230.md`（全文 15 分钟）

### 我想查某个术语的定义
→ `docs/数据开发Agent工程词典_20260616_2230.md`（按 § 索引用，共 19 个术语）

---

## 当前实现状态 / Implementation Status

> **权威事实源：项目根目录 `AGENTS.md` §10。** 本节为摘要索引，详细状态以 AGENTS.md 为准。
>
> 最近验收：2026-06-21，`pytest tests/ -q` → 674 passed，零回归。

### ✅ DONE（已完成）

| 模块 | 状态 | 说明 |
|------|------|------|
| M2 Review Package 完整生成 | ✅ | `src/agent/workflow.py` → `build_review_package()` 输出 9 文件审查材料包 |
| M3 静态检查 + SQL 样本执行 | ✅ | 5 项静态检查 + 只读 DuckDB 执行 + LIMIT 1000 + 超时保护 |
| M3 安全压实（3 缺口闭合） | ✅ | G1/G2/G3 修复 |
| **M4a/b/c 人审状态机** | ✅ | DecisionStatus enum + decision.yml + CLI + SUPERSEDED 自动转换 + 跨包注册表 |
| **M5a 查询内核与写入外壳分离** | ✅ | 双内核 Manifest、确定性部署外壳、双审批快照、篡改失效 |
| **M5b-1 DuckDB CTAS Sandbox** | ✅ | `duckdb_ctas_executor.py`——一次性可写 Sandbox，12 步生命周期 + 白名单 + 物化验证 |
| **Spark 只读样本执行** | ✅ | `spark_executor.py`——12 层防御受控执行（PySpark 不可用时 SKIPPED） |
| **SQL/Spark 交叉验证** | ✅ | `cross_validation.py`——7 维度比较（列名/类型/行数/抽样行/空值/数值合计/快照哈希） |
| 测试 | ✅ | 674 passed，零回归 |

### ⚠️ PARTIAL（部分完成）

| 模块 | 状态 | 说明 |
|------|------|------|
| Spark 交叉验证 | ⚠️ | Spark 可用时产出 CONSISTENT_SAMPLE，PySpark 不可用时 NOT_EXECUTED |
| 物化验证 | ⚠️ | 单表 CTAS 已实现，多表 JOIN / INSERT 策略延后 |

### ❌ TODO（待完成）

| 模块 | 阻塞原因 |
|------|---------|
| LLM 接入代码生成 | 项目边界：当前不接真实 LLM API |
| Prompt 回归系统 | 需 LLM API |

### Legacy boundary（v1 / v2 边界）

| 组件 | 定位 |
|------|------|
| `scripts/pipeline/run_pipeline.py` | v1 legacy：8 层确定性管道，保留为验证底座 + fallback 编译器。只调用 `compile_sql()`（SELECT），Layer 6 `read_only=True` |
| `scripts/pipeline/layer4_operation.py` | v1 写操作编译器：`compile_operation()` 可编译 CTAS/INSERT/VIEW，3 方言。**可编译、可静态校验，但当前未接入可写执行器** |
| `scripts/pipeline/layer5_validate_pipeline.py` | v1 DAG + safety_tier 静态校验：`validate_pipeline()` 允许 pipeline tier 写操作通过编译时校验。**safety_tier 不是运行时写权限** |
| `scripts/dev_agent/build_review_package.py` | v2 主入口：M2 Review Package 生成 |
| `scripts/dev_agent/verify_review_package.py` | v2 主入口：M3 验证引擎 |

### Known limitations（已知局限）

- **不接真实 LLM API**——M2 代码生成使用确定性模板
- **不自动上线、不写生产库**——Agent 只连开发库，只读、限行、限时
- **Spark 不可用时为 SKIPPED/NOT_EXECUTED**——不能说 Spark 已完整验证
- **物化验证仅支持单表 CTAS**——多表 JOIN / INSERT 策略延后
- **交叉验证仅证明样本一致**——不证明全量或生产行为一致

---

## 旧架构参考

以下内容属于 v1.x，保留供参考：

| 文件 | 说明 |
|------|------|
| `docs/superpowers/specs/DAG端到端编译测试_20260615_2024.md` | DAG 编译测试设计（v1.x 上下文，测试概念在 v2.0 防线 2 中仍适用） |
| `PROJECT_STATUS.md` | 项目历史状态（Phase 1-7 编译器交付记录） |
| `scripts/pipeline/` | v1.x 管道代码（保留为 v2.0 防线 2 的规则引擎 + fallback 编译器） |
