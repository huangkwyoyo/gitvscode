"""
Harness 配置加载工具

集中读取 harness_targets.yml，避免质量脚本散落硬编码路径。
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class HarnessConfig:
    """保存 Harness 运行所需的核心路径"""

    project_root: Path
    stage: str
    duckdb_path: Path
    silver_dictionary_xlsx: Path
    official_dictionary_dir: Path
    database_design_dir: Path
    data_dictionary_dir: Path
    memory_dir: Path
    standards_index_dir: Path


def _resolve_path(project_root: Path, value: str) -> Path:
    """把配置中的相对路径解析到项目根目录"""
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def load_harness_config(config_path: Path | None = None) -> HarnessConfig:
    """读取 Harness 目标配置"""
    if config_path is None:
        project_root = Path(__file__).resolve().parents[2]
        config_path = project_root / "harness" / "config" / "harness_targets.yml"

    data: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    project_root = Path(data["project"]["root"]).resolve()
    stage = data["project"].get("stage", "pre_silver_build")
    warehouse = data["warehouse"]
    facts = data["facts"]

    return HarnessConfig(
        project_root=project_root,
        stage=stage,
        duckdb_path=_resolve_path(project_root, warehouse["duckdb_path"]),
        silver_dictionary_xlsx=_resolve_path(project_root, warehouse["silver_dictionary_xlsx"]),
        official_dictionary_dir=_resolve_path(project_root, warehouse["official_dictionary_dir"]),
        database_design_dir=_resolve_path(project_root, facts["database_design_dir"]),
        data_dictionary_dir=_resolve_path(project_root, facts["data_dictionary_dir"]),
        memory_dir=_resolve_path(project_root, facts["memory_dir"]),
        standards_index_dir=_resolve_path(project_root, facts["standards_index_dir"]),
    )
