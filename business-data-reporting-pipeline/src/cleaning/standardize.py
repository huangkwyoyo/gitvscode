from __future__ import annotations

import re

import pandas as pd


def normalize_column_names(dataframe: pd.DataFrame) -> pd.DataFrame:
    result = dataframe.copy()
    result.columns = [
        re.sub(r"_+", "_", re.sub(r"[^0-9a-zA-Z]+", "_", column.strip().lower())).strip("_")
        for column in result.columns
    ]
    return result


def trim_string_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    result = dataframe.copy()
    for column in result.select_dtypes(include=["object", "string"]).columns:
        result[column] = result[column].astype("string").str.strip()
    return result

