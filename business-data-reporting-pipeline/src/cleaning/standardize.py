from __future__ import annotations

import re

import pandas as pd


def normalize_column_names(dataframe: pd.DataFrame) -> pd.DataFrame:
    """统一列名为小写英文+下划线格式，去除多余分隔符和前缀空格。

    例如 "Customer Name" -> "customer_name"。
    """
    result = dataframe.copy()
    result.columns = [
        re.sub(r"_+", "_", re.sub(r"[^0-9a-zA-Z]+", "_", column.strip().lower())).strip("_")
        for column in result.columns
    ]
    return result


def trim_string_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """对字符串类型列去除首尾空白字符。"""
    result = dataframe.copy()
    for column in result.select_dtypes(include=["object", "string"]).columns:
        result[column] = result[column].astype("string").str.strip()
    return result

