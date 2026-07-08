"""本地路径配置"""

from pathlib import Path


def get_project_root() -> Path:
    """返回项目根目录"""
    # 当前文件在 src/runtime_lab/config.py，上三层到项目根
    return Path(__file__).resolve().parent.parent.parent


def get_runs_dir() -> Path:
    """返回 runs/ 目录路径"""
    return get_project_root() / "runs"


def get_run_dir(run_id: str) -> Path:
    """返回指定 run_id 的输出目录"""
    path = get_runs_dir() / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path
