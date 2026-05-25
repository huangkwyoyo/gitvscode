from __future__ import annotations

from typing import Any

import pandas as pd

from src.cleaning.missing import fill_missing_values
from src.cleaning.outliers import detect_outliers
from src.cleaning.standardize import normalize_column_names, trim_string_columns


def clean_dataframe(dataframe: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
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

