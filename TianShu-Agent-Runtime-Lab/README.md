# TianShu-Agent-Runtime-Lab

面向数据工程 Agent 的单 Agent Runtime 实操训练项目。

## 定位

用 TianShu 数仓语境，训练以下 Runtime 核心能力：

- State：运行状态管理
- Tool Calling：受控工具调用
- Structured Output：结构化输出
- Checkpoint / Interrupt / Resume：检查点与中断恢复
- Human Approval：人工审批
- Replay / Fork：回放与分叉
- Fail-Closed：失败封闭
- Trace / Audit：追踪与审计

## 五周学习路线

| 周次 | 主题 | 交付物 |
|------|------|--------|
| W1 | Runtime 骨架 | state, graph, CLI, trace |
| W2 | SQL Review Runtime | SQL 审查工具 + 风险判断 + fail-closed |
| W3 | Contract Inspector Runtime | 契约工具 + answer/clarification/refusal |
| W4 | Join Approval Runtime | 人工审批 + interrupt/resume |
| W5 | DataDev Plan Replay Runtime | checkpoint/replay/fork + plan diff |

## 快速开始

```bash
# 第 1 周后可用
python -m runtime_lab greet
```

## 项目结构

```
src/runtime_lab/
  app.py          # CLI 入口
  graph.py        # LangGraph 主图
  state.py        # RuntimeState
  config.py       # 配置
  nodes/          # 图节点
  tools/          # 受控工具
  models/         # Pydantic 结构化模型
  storage/        # 存储层
  policies/       # 策略层
  reports/        # 运行报告生成

fixtures/         # 学习用假数据
tests/            # 测试
runs/             # 运行产物
```

## 设计文档

见 `docs/superpowers/specs/`。
