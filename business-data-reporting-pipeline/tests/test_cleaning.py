import pandas as pd

from src.cleaning.cleaner import clean_dataframe


def test_clean_dataframe_normalizes_names_and_fills_missing_values() -> None:
    dataframe = pd.DataFrame(
        {
            " Customer Name ": [" Alice ", "Alice", None],
            "Revenue Amount": [100.0, 100.0, None],
        }
    )
    config = {
        "cleaning": {
            "drop_duplicates": True,
            "standardize": {"normalize_column_names": True, "trim_strings": True},
            "missing": {"numeric_strategy": "median", "categorical_strategy": "mode"},
            "outliers": {"enabled": True, "method": "iqr", "iqr_multiplier": 1.5},
        }
    }

    cleaned = clean_dataframe(dataframe, config)

    assert list(cleaned.columns) == ["customer_name", "revenue_amount"]
    assert cleaned["revenue_amount"].isna().sum() == 0
    assert cleaned["customer_name"].isna().sum() == 0

