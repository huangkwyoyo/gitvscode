"""
TianShu Text2SQL Agent 版本信息。

版本读取策略（优先级从高到低）：
1. pyproject.toml 文件 —— 开发场景权威源
2. importlib.metadata —— 已安装包的生产环境回退
3. "0.0.0" —— 不可恢复错误时的兜底值

用法：
    from src.version import VERSION, get_version

    print(VERSION)        # "1.0.0"
    print(get_version())  # "1.0.0"
"""

from __future__ import annotations

import re
from pathlib import Path

VERSION: str = "0.0.0"  # 兜底默认值


def _resolve_version() -> str:
    """按优先级解析版本号。"""
    # 优先级 1: pyproject.toml（开发场景权威源）
    _pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if _pyproject_path.exists():
        try:
            _text = _pyproject_path.read_text(encoding="utf-8")
            _match = re.search(r'^version\s*=\s*"([^"]+)"', _text, re.MULTILINE)
            if _match:
                return _match.group(1)
        except Exception:
            pass  # 文件读取失败，继续下一优先级

    # 优先级 2: importlib.metadata（pip install 后的生产环境回退）
    try:
        from importlib.metadata import PackageNotFoundError, version as _metadata_version

        return _metadata_version("tianshu-text2sql-agent")
    except (PackageNotFoundError, ModuleNotFoundError):
        pass

    # 优先级 3: 兜底
    return "0.0.0"


VERSION = _resolve_version()


def get_version() -> str:
    """返回当前版本号字符串。

    Returns:
        版本号，格式为 "major.minor.patch"（如 "1.0.0"）
    """
    return VERSION
