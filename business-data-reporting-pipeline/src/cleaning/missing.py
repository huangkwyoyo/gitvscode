from __future__ import annotations

from typing import Any

import pandas as pd


def fill_missing_values(dataframe: pd.DataFrame, missing_config: dict[str, Any]) -> pd.DataFrame:
    """按策略填充分数值和类别列的缺失值：数值用均值/中位数，类别用众数。

    Args:
        dataframe: 输入数据框。
        missing_config: 缺失值处理配置，包含 numeric_strategy 和 categorical_strategy。

    Returns:
        缺失值已填充的数据框副本。
    """
    result = dataframe.copy()
    numeric_columns = result.select_dtypes(include="number").columns
    categorical_columns = result.select_dtypes(include=["object", "string", "category", "bool"]).columns

    # 数值列：优先使用中位数，也可配置为均值
    if missing_config.get("numeric_strategy") == "median":
        result[numeric_columns] = result[numeric_columns].fillna(result[numeric_columns].median())
    elif missing_config.get("numeric_strategy") == "mean":
        result[numeric_columns] = result[numeric_columns].fillna(result[numeric_columns].mean())

    # 类别列：使用出现频率最高的值填充
    if missing_config.get("categorical_strategy") == "mode":
        for column in categorical_columns:
            mode = result[column].mode(dropna=True)
            if not mode.empty:
                result[column] = result[column].fillna(mode.iloc[0])

    return result
