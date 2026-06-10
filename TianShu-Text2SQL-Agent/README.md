# TianShu Text2SQL Agent

以 TianShu NYC 交通数据仓库为数据源的中文问数分析 Agent。

## 核心思路

```
中文问题 → QuestionIntent → SQLPlan → SQL → 执行 → 中文解释
              ↑ 反问        ↑ 降级      ↑ 安全检查
```

三层 IR（中间表示）每层独立校验，在错误传播前拦截。

## 项目结构

```
├─ AGENTS.md                  # Agent 入口规则
├─ config/
│  ├─ agent_config.yml        # 运行时配置
│  └─ tianshu_target.yml      # TianShu 连接配置
├─ src/
│  ├─ ir.py                   # 三层 IR 数据结构
│  ├─ resolver.py             # TianShu DuckDB + 契约加载
│  ├─ sql_gen.py              # SQLPlan → SQL
│  ├─ executor.py             # 只读执行器
│  ├─ explainer.py            # 结果 → 中文解释
│  ├─ ambiguity.py            # 歧义检测 + 反问
│  └─ agent.py                # 主循环
├─ prompts/                   # LLM 提示词模板
├─ evals/                     # 评测问题集（4 类）
├─ harness/                   # 质量门禁
│  ├─ checks/                 # 5 个检查脚本
│  └─ run_harness.py          # 门禁入口
└─ tests/                     # 单元测试
```

## 依赖

- Python >= 3.10
- DuckDB >= 0.10.0
- PyYAML >= 6.0

## 安装

```bash
pip install -e .
```

## 使用

```bash
# 交互式问数
tianshu-ask

# 或 Python API
from src.agent import Text2SQLAgent
agent = Text2SQLAgent()
agent.ask("2026年Q1曼哈顿每天多少行程？")
```

## 运行 Harness

```bash
python harness/run_harness.py
```

## 契约来源

所有契约文件在 TianShu 项目中维护（`../TianShu/contracts/`），Agent 启动时动态读取。

---

🤖 与 TianShu 数仓变更 Agent 配合使用，形成"分析 → 发现不足 → 变更提案 → 合入 → 分析受益"的闭环。
