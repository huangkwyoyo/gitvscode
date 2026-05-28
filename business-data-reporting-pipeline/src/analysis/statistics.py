from __future__ import annotations

import pandas as pd


def describe_dataframe(dataframe: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """按类型（数值/类别/日期）分别生成描述性统计，并附带缺失计数。

    Args:
        dataframe: 输入数据框。

    Returns:
        包含 "numeric"、"categorical"、"datetime"、"missing" 四个键的字典。
    """
    return {
        "numeric": _describe_or_empty(dataframe, ["number"]),
        "categorical": _describe_or_empty(dataframe, ["object", "string", "category", "bool"]),
        "datetime": _describe_or_empty(dataframe, ["datetime"]),
        "missing": dataframe.isna().sum().to_frame("missing_count"),
    }


def _describe_or_empty(dataframe: pd.DataFrame, include: list[str]) -> pd.DataFrame:
    """调用 Pandas describe 并在无可匹配列时安全返回空 DataFrame。"""
    try:
        return dataframe.describe(include=include).transpose()
    except ValueError:
        return pd.DataFrame()
