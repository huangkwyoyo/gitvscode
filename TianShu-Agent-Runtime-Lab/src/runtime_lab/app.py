"""Typer CLI 入口——接收用户命令并启动 Runtime"""

import typer
from datetime import datetime

from runtime_lab.graph import build_graph
from runtime_lab.state import RuntimeState
from runtime_lab.config import get_run_dir
from runtime_lab.storage.trace_store import TraceStore

app = typer.Typer()


def _generate_run_id() -> str:
    """生成运行 ID"""
    now = datetime.now()
    return f"run_{now.strftime('%Y%m%d_%H%M%S')}"


@app.command()
def greet():
    """验证 Runtime 骨架能跑通"""
    try:
        run_id = _generate_run_id()
        state = RuntimeState(
            run_id=run_id,
            user_input="greet",
            status="running",
            current_step="init",
        )

        graph = build_graph()
        result = graph.invoke(state)

        # 合并 result 回 state（LangGraph 返回的是 dict）
        for key, value in result.items():
            if hasattr(state, key):
                setattr(state, key, value)

        # 写 trace
        run_dir = get_run_dir(run_id)
        store = TraceStore(str(run_dir))
        store.save_state_history(state, {"node": "final"})
        store.write_run_report(state)

        # 输出结果
        typer.echo(f"\nRuntime started: {run_id}")
        typer.echo(f"  Status:    {state.status}")
        typer.echo(f"  Demo type: {state.demo_type}")
        typer.echo(f"  Steps:     init -> classify_demo -> summarize -> end")
        typer.echo(f"  Trace:     {run_dir / 'state_history.jsonl'}")
        typer.echo(f"  Report:    {run_dir / 'reports' / 'run_report.md'}")
    except Exception as e:
        typer.echo(f"\nRuntime 执行失败：{e}", err=True)
        raise typer.Exit(code=1)


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
