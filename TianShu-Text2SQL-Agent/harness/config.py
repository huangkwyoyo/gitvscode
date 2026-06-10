"""
Harness 共享配置加载。

从 config/tianshu_target.yml 读取 TianShu 路径和契约文件位置。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class HarnessConfig:
    """Harness 运行时配置"""
    tianshu_root: Path = field(default_factory=Path)
    contracts_path: Path = field(default_factory=Path)
    evals_path: Path = field(default_factory=Path)
    duckdb_path: Path = field(default_factory=Path)
    config: dict[str, Any] = field(default_factory=dict)


def load_harness_config(
    config_path: str = "config/tianshu_target.yml"
) -> HarnessConfig:
    """
    加载 Harness 配置。

    从 config/tianshu_target.yml 读取 TianShu 路径，
    计算出契约文件、评测文件和 DuckDB 的绝对路径。

    Args:
        config_path: tianshu_target.yml 的路径

    Returns:
        HarnessConfig 包含所有必要路径
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_file}")

    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 解析 TianShu 根目录（相对于 Agent 项目根目录）
    agent_root = config_file.parent.parent  # config/ 的父目录 = Agent 根目录
    tianshu_rel = config.get("tianshu", {}).get("project_root", "../TianShu")
    tianshu_root = (agent_root / tianshu_rel).resolve()

    # 契约文件目录
    contracts_rel = config.get("tianshu", {}).get("contracts_path", "contracts")
    contracts_path = tianshu_root / contracts_rel

    # 评测文件目录（Agent 项目自己的）
    evals_path = agent_root / "evals"

    # DuckDB 路径
    duckdb_rel = config.get("tianshu", {}).get("duckdb_path", "data/tian_shu.duckdb")
    duckdb_path = tianshu_root / duckdb_rel

    return HarnessConfig(
        tianshu_root=tianshu_root,
        contracts_path=contracts_path,
        evals_path=evals_path,
        duckdb_path=duckdb_path,
        config=config,
    )
