"""共享工具函数。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def normalize_preview_value(value) -> object:
    """将 DataFrame 单元格值转为 JSON 安全类型。"""
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def safe_float(value, decimals: int = 6) -> float | None:
    """安全转换为 float，NaN 或 None 时返回 None。"""
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    return round(float(value), decimals)


def build_preview(df: pd.DataFrame, max_rows: int = 25) -> list[dict]:
    """将 DataFrame 前 N 行转换为 JSON 安全格式的预览列表。

    消除 loader.py 和 cleaning.py 中的重复代码。
    """
    return [
        {k: normalize_preview_value(v) for k, v in row.items()}
        for row in df.head(max_rows).to_dict(orient="records")
    ]
