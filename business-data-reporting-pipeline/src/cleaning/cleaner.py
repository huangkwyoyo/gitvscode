from __future__ import annotations

from typing import Any

import pandas as pd

from src.cleaning.missing import fill_missing_values
from src.cleaning.outliers import detect_outliers
from src.cleaning.standardize import normalize_column_names, trim_string_columns


def clean_dataframe(dataframe: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """执行完整的数据清洗流程：标准化列名 -> 去重 -> 填充缺失值 -> 异常值检测。

    Args:
        dataframe: 原始数据框。
        config: 清洗配置字典。

    Returns:
        清洗后的数据框，attrs 中附带异常值标志。
    """
    cleaning_config = config["cleaning"]
    cleaned = dataframe.copy()

    if cleaning_config["standardize"].get("normalize_column_names", True):
        cleaned = normalize_column_names(cleaned)
    if cleaning_config["standardize"].get("trim_strings", True):
        cleaned = trim_string_columns(cleaned)
    if cleaning_config.get("drop_duplicates", True):
        cleaned = cleaned.drop_duplicates()

    cleaned = fill_missing_values(cleaned, cleaning_config["missing"])

    if cleaning_config["outliers"].get("enabled", True):
        outlier_flags = detect_outliers(cleaned, cleaning_config["outliers"])
        cleaned.attrs["outlier_flags"] = outlier_flags

    return cleaned

