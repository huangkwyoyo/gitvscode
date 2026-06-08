# 架构决策记录（ADR）

本目录存放 TianShu 项目的关键架构决策记录（Architecture Decision Records）。

## 什么是 ADR

ADR 记录的是**重要的架构决策**——不是所有决定都值得写 ADR，只有那些影响项目方向、难以逆转、或存在多个合理替代方案的决定才需要。

每份 ADR 回答四个问题：
- 我们决定了什么？
- 为什么这样决定？
- 考虑过哪些替代方案？
- 这个决定带来了什么后果？

## 决策索引

| 编号 | 标题 | 状态 | 日期 |
|---|---|---|---|
| [001](001-duckdb-as-warehouse-engine.md) | 选择 DuckDB 作为数仓引擎 | Accepted | 2026-06-07 |
| [002](002-bronze-silver-gold-layering.md) | Bronze→Silver→Gold 三层分层架构 | Accepted | 2026-06-07 |
| [003](003-silver-three-batch-strategy.md) | Silver 层分三批建设策略 | Accepted | 2026-06-07 |
| [004](004-primary-key-strategy.md) | 主键策略：代理键、复合键与哈希键的选择 | Accepted | 2026-06-07 |
| [005](005-agent-memory-harness-system.md) | Agent Memory + Warehouse Harness 统一治理体系 | Accepted | 2026-06-07 |
| [006](006-parking-violation-amount-in-gold.md) | 停车罚单金额字段放在 Gold 层而非 Silver 层 | Accepted | 2026-06-07 |

## ADR 模板

新建 ADR 时，复制以下模板：

```markdown
# NNN-简短标题

## Status（状态）

Proposed / Accepted / Deprecated / Superseded by [ADR-NNN](NNN-xxx.md)

## Context（背景）

当时面临什么问题？有什么约束条件？谁参与了决策？

## Decision（决策）

我们决定怎么做？具体方案是什么？

## Alternatives（替代方案）

考虑过哪些其他方案？各自优劣是什么？为什么最终没选？

## Consequences（后果）

### 正面影响

这个决定带来了什么好处？

### 负面影响 / 代价

这个决定带来了什么限制、成本或技术债务？

### 重新评估条件

什么情况下应该重新审视这个决定？（数据量达到多少？出现什么新需求？什么工具成熟了？）
```

## 状态说明

| 状态 | 含义 |
|---|---|
| Proposed | 提案中，尚未最终决定 |
| Accepted | 已采纳，当前正在执行 |
| Deprecated | 已废弃，不再适用 |
| Superseded | 被新的 ADR 取代（需标注取代者） |

## 使用原则

1. **只记录真正重要的决策**——不要为每个小选择写 ADR
2. **决策当时写**——不要事后补写（会丢失当时的上下文和替代方案考量）
3. **可以标记为 Proposed**——不必所有 ADR 都是 Accepted，提案阶段的 ADR 也有价值
4. **可以废弃和取代**——ADR 不是永恒真理，项目演进了就应该更新
5. **写清楚重新评估条件**——这是 ADR 最有价值的部分之一，告诉后来者"什么情况下这个决定应该重新考虑"
