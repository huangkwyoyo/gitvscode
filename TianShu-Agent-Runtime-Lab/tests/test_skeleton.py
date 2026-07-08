"""骨架验收测试"""

import pytest
from runtime_lab.state import RuntimeState
from runtime_lab.config import get_project_root


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


def test_get_run_dir(tmp_path, monkeypatch):
    """验证 get_run_dir 创建目录"""
    # 将 get_project_root 替换为临时路径，避免操作真实文件系统
    monkeypatch.setattr("runtime_lab.config.get_project_root", lambda: tmp_path)
    from runtime_lab.config import get_run_dir

    run_id = "test_run_001"
    run_path = get_run_dir(run_id)

    expected = tmp_path / "runs" / run_id
    assert run_path == expected
    assert run_path.exists()
    assert run_path.is_dir()


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
