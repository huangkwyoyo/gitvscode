from __future__ import annotations

import os

from dotenv import load_dotenv


def get_env_value(name: str) -> str:
    """从环境变量读取配置值，自动加载 .env 文件。

    Args:
        name: 环境变量名称。

    Returns:
        环境变量字符串值。

    Raises:
        ValueError: 当指定环境变量不存在时抛出。
    """
    load_dotenv()
    value = os.getenv(name)
    if not value:
        raise ValueError(f"缺少必需的环境变量: {name}")
    return value

