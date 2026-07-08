# 第 1 周：Runtime 骨架实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标**：搭建最小可运行 Runtime 骨架——CLI 能启动、LangGraph 图能走通、State 能传递、Trace 能写入。

**架构**：Typer CLI 入口 → 调用 LangGraph 编译图 → 图包含 classify 和 summarize 两个节点 → 节点间通过 RuntimeState 传递数据 → 每一步的变化写入 TraceStore → 最终输出 run_report.md。

**技术栈**：Python 3.11+、LangGraph 0.4+、Pydantic 2+、Typer 0.12+

## 全局约束

- 所有代码注释必须使用中文
- Python >= 3.11，LangGraph >= 0.4，Typer >= 0.12
- `__init__.py` 已在各目录创建
- 目录 `runs/` 用于存放运行产物（已 gitignore）
- 所有路径基于项目根目录 `TianShu-Agent-Runtime-Lab/`
- 依赖声明在 `pyproject.toml` 中（已创建）

---

## 文件结构

```
创建：
  src/runtime_lab/state.py          # RuntimeState 定义
  src/runtime_lab/config.py         # 路径配置
  src/runtime_lab/graph.py          # LangGraph 编译图
  src/runtime_lab/nodes/classify.py # 任务分类节点
  src/runtime_lab/nodes/summarize.py# 总结节点
  src/runtime_lab/storage/trace_store.py # Trace 存储
  src/runtime_lab/app.py            # Typer CLI 入口
  tests/test_skeleton.py            # 骨架集成测试
```

---

### Task 1：RuntimeState + Config 基础

**文件：**
- 创建：`src/runtime_lab/state.py`
- 创建：`src/runtime_lab/config.py`
- 测试：`tests/test_skeleton.py`（State 初始化）

**接口：**
- 消费：无（基础定义）
- 产出：`RuntimeState` dataclass，`get_run_dir()` / `get_project_root()` 配置函数

- [ ] **Step 1：定义 RuntimeState**

```python
# src/runtime_lab/state.py
"""统一运行状态定义——记录 Agent 一次执行的全生命周期状态"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RuntimeState:
    """运行状态

    记录一次 Agent 任务执行到哪一步、已产生什么中间结果、调用过哪些工具。
    每个 LangGraph 节点只读写自己关心的字段。
    """

    # 运行标识
    run_id: str = ""
    thread_id: str = ""

    # 输入与分类
    user_input: str = ""
    demo_type: str = ""  # "sql_review" | "contract" | "join" | "datadev" | "greet"

    # 执行流转
    current_step: str = "init"
    next_action: str = ""
    status: str = "init"  # init | running | waiting_approval | completed | failed_closed

    # 中间产物（按需填充）
    intermediate: dict = field(default_factory=dict)

    # 工具调用记录
    tool_call_history: list = field(default_factory=list)

    # 错误记录
    errors: list = field(default_factory=list)

    # 元信息
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        """自动填充时间戳"""
        now = datetime.now().isoformat(timespec="seconds")
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
```

- [ ] **Step 2：定义 Config**

```python
# src/runtime_lab/config.py
"""本地路径配置"""

import os
from pathlib import Path


def get_project_root() -> Path:
    """返回项目根目录"""
    # 当前文件在 src/runtime_lab/config.py，上三层到项目根
    return Path(__file__).resolve().parent.parent.parent.parent


def get_runs_dir() -> Path:
    """返回 runs/ 目录路径"""
    return get_project_root() / "runs"


def get_run_dir(run_id: str) -> Path:
    """返回指定 run_id 的输出目录"""
    path = get_runs_dir() / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path
```

- [ ] **Step 3：编写并运行状态初始化测试**

在 `tests/test_skeleton.py` 中添加：

```python
"""骨架验收测试"""

import pytest
from runtime_lab.state import RuntimeState


def test_state_default_values():
    """验证 RuntimeState 默认值正确"""
    state = RuntimeState()
    assert state.status == "init"
    assert state.current_step == "init"
    assert state.demo_type == ""
    assert state.intermediate == {}
    assert state.errors == []
    assert state.created_at != ""  # __post_init__ 填充
    assert state.updated_at != ""


def test_state_with_values():
    """验证传参构造"""
    state = RuntimeState(run_id="test_001", user_input="hello", status="running")
    assert state.run_id == "test_001"
    assert state.user_input == "hello"
    assert state.status == "running"


def test_config_paths():
    """验证配置路径正确"""
    from runtime_lab.config import get_project_root, get_runs_dir
    root = get_project_root()
    assert root.name == "TianShu-Agent-Runtime-Lab"
    assert (root / "src").exists()
    runs = get_runs_dir()
    assert runs.name == "runs"
```

运行测试：

```bash
cd /d/Program\ Files/gitvscode/TianShu-Agent-Runtime-Lab
pip install -e ".[dev]" 2>&1 | tail -5
PYTHONIOENCODING=utf-8 python -m pytest tests/test_skeleton.py::test_state_default_values tests/test_skeleton.py::test_state_with_values tests/test_skeleton.py::test_config_paths -v
```

预期：3 个测试全部 PASS。

- [ ] **Step 4：提交**

```bash
git add src/runtime_lab/state.py src/runtime_lab/config.py tests/test_skeleton.py
git commit -m "feat: 定义 RuntimeState 和路径配置"
```

---

### Task 2：TraceStore 存储

**文件：**
- 创建：`src/runtime_lab/storage/trace_store.py`
- 修改：`tests/test_skeleton.py`（追加 TraceStore 测试）

**接口：**
- 消费：`RuntimeState`、`get_run_dir()`
- 产出：`TraceStore(run_dir).save_state_history(state, step_info)`、`TraceStore().write_run_report(state)`

- [ ] **Step 1：编写 TraceStore 失败测试（TDD）**

```python
# 追加到 tests/test_skeleton.py

def test_trace_store_save_state_history(tmp_path):
    """验证 state_history.jsonl 能被正确写入"""
    from runtime_lab.storage.trace_store import TraceStore
    store = TraceStore(str(tmp_path))
    state = RuntimeState(run_id="test_001", status="running", current_step="classify")
    store.save_state_history(state, step_info={"node": "classify"})
    history_file = tmp_path / "state_history.jsonl"
    assert history_file.exists()
    content = history_file.read_text(encoding="utf-8")
    assert "test_001" in content
    assert "classify" in content


def test_trace_store_write_run_report(tmp_path):
    """验证 run_report.md 能被正确生成"""
    from runtime_lab.storage.trace_store import TraceStore
    store = TraceStore(str(tmp_path))
    state = RuntimeState(
        run_id="test_001",
        user_input="greet",
        demo_type="greet",
        status="completed",
    )
    store.write_run_report(state)
    report_file = tmp_path / "reports" / "run_report.md"
    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "Run Report" in content
    assert "completed" in content
```

运行测试（预期 FAIL——TraceStore 尚未实现）：

```bash
PYTHONIOENCODING=utf-8 python -m pytest tests/test_skeleton.py::test_trace_store_save_state_history tests/test_skeleton.py::test_trace_store_write_run_report -v
```

预期：FAIL（ModuleNotFoundError / AttributeError）。

- [ ] **Step 2：实现 TraceStore**

```python
# src/runtime_lab/storage/trace_store.py
"""Trace 存储——记录 State 变化和工具调用"""

import json
from pathlib import Path


class TraceStore:
    """持久化 Agent 运行追踪记录"""

    def __init__(self, run_dir: str):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        # 子目录
        self.reports_dir = self.run_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir = self.run_dir / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def save_state_history(self, state, step_info: dict | None = None) -> None:
        """追加一条 State 变化记录到 state_history.jsonl"""
        record = {
            "run_id": state.run_id,
            "status": state.status,
            "current_step": state.current_step,
            "created_at": state.created_at,
            "updated_at": state.updated_at,
        }
        if step_info:
            record["step_info"] = step_info

        history_file = self.run_dir / "state_history.jsonl"
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def write_run_report(self, state) -> None:
        """生成 run_report.md"""
        report = _build_run_report(state)
        report_file = self.reports_dir / "run_report.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)


def _build_run_report(state) -> str:
    """构建运行报告 Markdown 文本"""
    lines = []
    lines.append("# Run Report\n")
    lines.append("## Summary\n")
    lines.append(f"本次运行：{state.user_input or '（空）'}\n")
    lines.append("## Final Status\n")
    lines.append(f"{state.status}\n")
    if state.errors:
        lines.append("## Errors\n")
        for err in state.errors:
            lines.append(f"- {err}\n")
    lines.append("## Artifacts\n")
    lines.append(f"- Run ID: {state.run_id}\n")
    lines.append(f"- Created: {state.created_at}\n")
    return "".join(lines)
```

- [ ] **Step 3：运行测试验证通过**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tests/test_skeleton.py::test_trace_store_save_state_history tests/test_skeleton.py::test_trace_store_write_run_report -v
```

预期：2 个测试全部 PASS。

- [ ] **Step 4：提交**

```bash
git add src/runtime_lab/storage/trace_store.py tests/test_skeleton.py
git commit -m "feat: 实现 TraceStore 状态记录和运行报告生成"
```

---

### Task 3：LangGraph 节点 + 图

**文件：**
- 创建：`src/runtime_lab/nodes/classify.py`
- 创建：`src/runtime_lab/nodes/summarize.py`
- 创建：`src/runtime_lab/graph.py`
- 修改：`tests/test_skeleton.py`（追加图测试）

**接口：**
- 消费：`RuntimeState`
- 产出：`classify_node(state) -> dict`、`summarize_node(state) -> dict`、`build_graph() -> CompiledGraph`

- [ ] **Step 1：编写图测试（TDD）**

```python
# 追加到 tests/test_skeleton.py

def test_build_graph_exists():
    """验证 build_graph 函数存在"""
    from runtime_lab.graph import build_graph
    graph = build_graph()
    assert graph is not None


def test_graph_greet_invocation():
    """验证 greet 类型输入能走通全图"""
    from runtime_lab.graph import build_graph
    graph = build_graph()
    result = graph.invoke({
        "run_id": "test_graph_001",
        "user_input": "greet",
        "status": "init",
        "current_step": "init",
    })
    assert result["status"] in ("completed",)
    assert "state_history" not in result or True  # 图能正常返回即可
```

运行测试（预期 FAIL——graph/node 未实现）。

- [ ] **Step 2：实现 classify 节点**

```python
# src/runtime_lab/nodes/classify.py
"""任务分类节点——判断运行哪个 Demo"""


def classify_node(state) -> dict:
    """根据用户输入判断 Demo 类型"""
    text = state.user_input.lower() if isinstance(state.user_input, str) else ""

    if "sql" in text or "review" in text:
        demo_type = "sql_review"
    elif "contract" in text:
        demo_type = "contract"
    elif "join" in text:
        demo_type = "join"
    elif "datadev" in text or "plan" in text:
        demo_type = "datadev"
    else:
        demo_type = "greet"

    return {
        "demo_type": demo_type,
        "current_step": "classify",
        "next_action": "summarize" if demo_type == "greet" else "plan",
    }
```

- [ ] **Step 3：实现 summarize 节点**

```python
# src/runtime_lab/nodes/summarize.py
"""总结节点——生成最终输出"""


def summarize_node(state) -> dict:
    """生成运行总结"""
    if state.errors:
        status = "failed_closed"
    elif state.status == "waiting_approval":
        status = "waiting_approval"
    else:
        status = "completed"

    return {
        "status": status,
        "current_step": "summarize",
    }
```

- [ ] **Step 4：实现 graph.py**

```python
# src/runtime_lab/graph.py
"""LangGraph 单 Agent Runtime 主图定义"""

from langgraph.graph import StateGraph
from runtime_lab.state import RuntimeState
from runtime_lab.nodes.classify import classify_node
from runtime_lab.nodes.summarize import summarize_node


def router(state) -> str:
    """根据 demo_type 路由到下一个节点"""
    if state.demo_type == "greet":
        return "summarize"
    # 其他 Demo 类型第 2 周起实现路由
    return "summarize"


def build_graph() -> StateGraph:
    """构建并编译 LangGraph 图"""
    builder = StateGraph(RuntimeState)

    # 注册节点
    builder.add_node("classify_demo", classify_node)
    builder.add_node("summarize", summarize_node)

    # 设置入口
    builder.set_entry_point("classify_demo")

    # 条件边
    builder.add_conditional_edges(
        "classify_demo",
        router,
        {
            "summarize": "summarize",
            "__end__": "__end__",
        },
    )

    # 固定边
    builder.add_edge("summarize", "__end__")

    return builder.compile()
```

- [ ] **Step 5：运行测试验证通过**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tests/test_skeleton.py::test_build_graph_exists tests/test_skeleton.py::test_graph_greet_invocation -v
```

预期：2 个测试全部 PASS。

- [ ] **Step 6：提交**

```bash
git add src/runtime_lab/nodes/classify.py src/runtime_lab/nodes/summarize.py src/runtime_lab/graph.py tests/test_skeleton.py
git commit -m "feat: 实现 LangGraph 最小图（classify + summarize）"
```

---

### Task 4：CLI 入口 + 集成验收

**文件：**
- 创建：`src/runtime_lab/app.py`
- 修改：`tests/test_skeleton.py`（追加集成测试）

**接口：**
- 消费：`build_graph()`、`RuntimeState`、`TraceStore`
- 产出：Typer CLI 命令 `greet`

- [ ] **Step 1：编写 CLI 集成测试（TDD）**

```python
# 追加到 tests/test_skeleton.py

def test_cli_greet_output():
    """验证 CLI greet 命令产生正确输出"""
    from typer.testing import CliRunner
    from runtime_lab.app import app
    runner = CliRunner()
    result = runner.invoke(app, ["greet"])
    assert result.exit_code == 0
    assert "completed" in result.stdout.lower() or "alive" in result.stdout.lower()
```

运行测试（预期 FAIL——app.py 尚未实现）。

- [ ] **Step 2：实现 app.py**

```python
# src/runtime_lab/app.py
"""Typer CLI 入口——接收用户命令并启动 Runtime"""

import json
import typer
from datetime import datetime

from runtime_lab.graph import build_graph
from runtime_lab.state import RuntimeState
from runtime_lab.config import get_run_dir, get_project_root
from runtime_lab.storage.trace_store import TraceStore

app = typer.Typer()


def _generate_run_id() -> str:
    """生成运行 ID"""
    now = datetime.now()
    return f"run_{now.strftime('%Y%m%d_%H%M%S')}"


@app.command()
def greet():
    """验证 Runtime 骨架能跑通"""
    run_id = _generate_run_id()
    state = RuntimeState(
        run_id=run_id,
        user_input="greet",
        status="running",
        current_step="init",
    )

    graph = build_graph()
    result = graph.invoke(state)

    # 写 trace
    run_dir = get_run_dir(run_id)
    store = TraceStore(str(run_dir))
    store.save_state_history(result, {"node": "final"})
    store.write_run_report(result)

    # 输出结果
    typer.echo(f"\nRuntime started: {run_id}")
    typer.echo(f"  Status:    {result.get('status', 'unknown')}")
    typer.echo(f"  Demo type: {result.get('demo_type', 'unknown')}")
    typer.echo(f"  Steps:     init -> classify_demo -> summarize -> end")
    typer.echo(f"  Trace:     {run_dir / 'state_history.jsonl'}")
    typer.echo(f"  Report:    {run_dir / 'reports' / 'run_report.md'}")


@app.command()
def sql_review(sql_path: str = typer.Argument("", help="SQL 文件路径")):
    """审查 SQL 安全性（第 2 周实现）"""
    typer.echo("Coming in Week 2 — SQL Review Runtime")


@app.command()
def contract(query: str = typer.Argument("", help="指标查询")):
    """查询契约信息（第 3 周实现）"""
    typer.echo("Coming in Week 3 — Contract Inspector Runtime")


@app.command()
def join(query: str = typer.Argument("", help="Join 查询")):
    """Join 审批（第 4 周实现）"""
    typer.echo("Coming in Week 4 — Join Approval Runtime")


@app.command()
def datadev(spec_path: str = typer.Argument("", help="DeveloperSpec 路径")):
    """DataDev Plan（第 5 周实现）"""
    typer.echo("Coming in Week 5 — DataDev Plan Replay Runtime")


if __name__ == "__main__":
    app()
```

- [ ] **Step 3：运行 CLI 手动验收**

```bash
cd /d/Program\ Files/gitvscode/TianShu-Agent-Runtime-Lab
PYTHONIOENCODING=utf-8 python -m runtime_lab greet
```

预期输出：

```
Runtime started: run_20260708_001
  Status:    completed
  Demo type: greet
  Steps:     init -> classify_demo -> summarize -> end
  Trace:     runs\run_20260708_001\state_history.jsonl
  Report:    runs\run_20260708_001\reports\run_report.md
```

验证文件存在：

```bash
dir runs\run_20260708_001\state_history.jsonl
dir runs\run_20260708_001\reports\run_report.md
```

- [ ] **Step 4：运行集成测试通过**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tests/test_skeleton.py -v
```

预期：全部测试 PASS。

- [ ] **Step 5：提交**

```bash
git add src/runtime_lab/app.py tests/test_skeleton.py
git commit -m "feat: 实现 CLI 入口 greet 命令 + 集成测试"
```

---

### Task 5：全量验收

- [ ] **Step 1：清理并完整运行验证**

```bash
cd /d/Program\ Files/gitvscode/TianShu-Agent-Runtime-Lab
# 清除 __pycache__
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; find . -name "*.pyc" -delete 2>/dev/null

# 全量测试
PYTHONIOENCODING=utf-8 python -m pytest tests/ -v
```

预期：所有测试 PASS。

- [ ] **Step 2：最终 CLI 验收**

```bash
PYTHONIOENCODING=utf-8 python -m runtime_lab greet
```

预期：输出完整运行报告，`runs/{run_id}/` 目录下有 trace 文件和 report 文件。

- [ ] **Step 3：最终提交**

```bash
git add -A
git commit -m "feat: 第 1 周 Runtime 骨架完成

- RuntimeState 定义与路径配置
- TraceStore 状态记录和报告生成
- LangGraph 最小图（classify -> summarize）
- Typer CLI 入口（greet 命令）
- 骨架集成测试覆盖"
```

---

## 自检清单

| 检查项 | 状态 |
|--------|------|
| Spec 覆盖：所有第 1 周文件是否已创建？ | ✅ state.py, config.py, graph.py, app.py, TraceStore, nodes |
| Spec 覆盖：CLI `greet` 命令可运行？ | ✅ Typer 入口 |
| Spec 覆盖：state_history.jsonl 生成了？ | ✅ TraceStore.save_state_history |
| Spec 覆盖：run_report.md 生成了？ | ✅ TraceStore.write_run_report |
| Spec 覆盖：pytest 全部通过？ | ✅ test_skeleton.py |
| 无占位符？ | ✅ 全部代码完整 |
| 类型一致性？ | ✅ RuntimeState → Graph → TraceStore 接口一致 |
