from __future__ import annotations

import pandas as pd


def describe_dataframe(dataframe: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "numeric": _describe_or_empty(dataframe, ["number"]),
        "categorical": _describe_or_empty(dataframe, ["object", "string", "category", "bool"]),
        "datetime": _describe_or_empty(dataframe, ["datetime"]),
        "missing": dataframe.isna().sum().to_frame("missing_count"),
    }


def _describe_or_empty(dataframe: pd.DataFrame, include: list[str]) -> pd.DataFrame:
    try:
        return dataframe.describe(include=include).transpose()
    except ValueError:
        return pd.DataFrame()
