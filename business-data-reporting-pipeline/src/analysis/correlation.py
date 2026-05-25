from __future__ import annotations

from typing import Any

import pandas as pd


def compute_correlation(dataframe: pd.DataFrame, correlation_config: dict[str, Any]) -> pd.DataFrame:
    if not correlation_config.get("enabled", True):
        return pd.DataFrame()

    numeric = dataframe.select_dtypes(include="number")
    if numeric.empty:
        return pd.DataFrame()

    return numeric.corr(method=correlation_config.get("method", "pearson"))

