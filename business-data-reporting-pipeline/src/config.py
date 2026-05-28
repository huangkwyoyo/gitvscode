from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: Path) -> dict[str, Any]:
    """加载并解析 YAML 配置文件。

    Args:
        path: YAML 配置文件的路径。

    Returns:
        配置字典。
    """
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)

