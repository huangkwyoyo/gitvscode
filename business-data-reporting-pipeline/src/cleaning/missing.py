from __future__ import annotations

from typing import Any

import pandas as pd


def fill_missing_values(dataframe: pd.DataFrame, missing_config: dict[str, Any]) -> pd.DataFrame:
    result = dataframe.copy()
    numeric_columns = result.select_dtypes(include="number").columns
    categorical_columns = result.select_dtypes(include=["object", "string", "category", "bool"]).columns

    if missing_config.get("numeric_strategy") == "median":
        result[numeric_columns] = result[numeric_columns].fillna(result[numeric_columns].median())
    elif missing_config.get("numeric_strategy") == "mean":
        result[numeric_columns] = result[numeric_columns].fillna(result[numeric_columns].mean())

    if missing_config.get("categorical_strategy") == "mode":
        for column in categorical_columns:
            mode = result[column].mode(dropna=True)
            if not mode.empty:
                result[column] = result[column].fillna(mode.iloc[0])

    return result
