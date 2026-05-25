from __future__ import annotations

from typing import Any

import pandas as pd


def detect_outliers(dataframe: pd.DataFrame, outlier_config: dict[str, Any]) -> pd.DataFrame:
    method = outlier_config.get("method", "iqr")
    if method != "iqr":
        raise ValueError(f"Unsupported outlier method: {method}")

    numeric = dataframe.select_dtypes(include="number")
    flags = pd.DataFrame(False, index=dataframe.index, columns=numeric.columns)
    multiplier = outlier_config.get("iqr_multiplier", 1.5)

    for column in numeric.columns:
        q1 = numeric[column].quantile(0.25)
        q3 = numeric[column].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr
        flags[column] = (numeric[column] < lower) | (numeric[column] > upper)

    return flags

