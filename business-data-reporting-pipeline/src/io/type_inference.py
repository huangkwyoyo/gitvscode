from __future__ import annotations

from typing import Any

import pandas as pd


def infer_dataframe_types(dataframe: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """自动推断字符串列的类型：优先转换为数值，其次尝试日期时间。

    转换规则：90% 以上能成功解析的值会被整体转换。
    """
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
    """将字符串序列尝试转为数值类型，成功率低于 90% 则保持原样。"""
    converted = pd.to_numeric(series, errors="coerce")
    if converted.notna().sum() >= series.notna().sum() * 0.9:
        return converted
    return series


def _try_datetime(series: pd.Series, datetime_formats: list[str]) -> pd.Series:
    """使用给定格式列表尝试解析日期时间，全部失败则回退原始系列。"""
    for datetime_format in datetime_formats:
        converted = pd.to_datetime(series, format=datetime_format, errors="coerce")
        if converted.notna().sum() >= series.notna().sum() * 0.9:
            return converted

    return series


def _looks_like_datetime_column(column: str) -> bool:
    """通过列名关键词快速判断是否可能是日期时间列。"""
    normalized = column.lower()
    return any(token in normalized for token in ("date", "time", "dt", "日期", "时间"))
