from __future__ import annotations

from typing import Any

import pandas as pd


def compute_correlation(dataframe: pd.DataFrame, correlation_config: dict[str, Any]) -> pd.DataFrame:
    """计算数值列之间的相关系数矩阵。

    Args:
        dataframe: 输入数据框。
        correlation_config: 相关分析配置，包含 enabled、method 等字段。

    Returns:
        相关系数 DataFrame；若未启用或无数值列则返回空 DataFrame。
    """
    if not correlation_config.get("enabled", True):
        return pd.DataFrame()

    numeric = dataframe.select_dtypes(include="number")
    if numeric.empty:
        return pd.DataFrame()

    return numeric.corr(method=correlation_config.get("method", "pearson"))

