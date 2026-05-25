from __future__ import annotations

from typing import Any

import pandas as pd


def infer_dataframe_types(dataframe: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    if not config.get("schema", {}).get("infer_types", True):
        return dataframe

    result = dataframe.copy()
    datetime_formats = config.get("schema", {}).get("datetime_formats", [])

    for column in result.select_dtypes(include=["object", "string"]).columns:
        result[column] = _try_numeric(result[column])
        if not pd.api.types.is_object_dtype(result[column]) and not pd.api.types.is_string_dtype(result[column]):
            continue
        if _looks_like_datetime_column(column):
            result[column] = _try_datetime(result[column], datetime_formats)

    return result


def _try_numeric(series: pd.Series) -> pd.Series:
    converted = pd.to_numeric(series, errors="coerce")
    if converted.notna().sum() >= series.notna().sum() * 0.9:
        return converted
    return series


def _try_datetime(series: pd.Series, datetime_formats: list[str]) -> pd.Series:
    for datetime_format in datetime_formats:
        converted = pd.to_datetime(series, format=datetime_format, errors="coerce")
        if converted.notna().sum() >= series.notna().sum() * 0.9:
            return converted

    return series


def _looks_like_datetime_column(column: str) -> bool:
    normalized = column.lower()
    return any(token in normalized for token in ("date", "time", "dt", "日期", "时间"))
