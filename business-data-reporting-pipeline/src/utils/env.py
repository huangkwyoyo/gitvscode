from __future__ import annotations

import os

from dotenv import load_dotenv


def get_env_value(name: str) -> str:
    load_dotenv()
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value

