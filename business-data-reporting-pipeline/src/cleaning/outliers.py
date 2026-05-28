from __future__ import annotations

from typing import Any

import pandas as pd


def detect_outliers(dataframe: pd.DataFrame, outlier_config: dict[str, Any]) -> pd.DataFrame:
    """使用 IQR 方法检测每列的异常值，返回布尔型标志 DataFrame。

    Args:
        dataframe: 输入数据框。
        outlier_config: 异常值检测配置，支持 method 和 iqr_multiplier。

    Returns:
        与输入同索引、数值列为 bool 类型的标志表，True 表示该值为异常值。
    """
    method = outlier_config.get("method", "iqr")
    if method != "iqr":
        raise ValueError(f"不支持的异常值检测方法: {method}")

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

