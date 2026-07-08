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
