from __future__ import annotations

from typing import Any

import pandas as pd

from src.analysis.correlation import compute_correlation
from src.analysis.statistics import describe_dataframe


def run_eda(dataframe: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    """执行完整探索性数据分析：shape、列名、业务指标、描述统计、相关性。

    Args:
        dataframe: 已清洗的数据框。
        config: 管道配置字典。

    Returns:
        包含各分析结果的字典。
    """
    return {
        "shape": dataframe.shape,
        "columns": list(dataframe.columns),
        "business_metrics": compute_business_metrics(dataframe),
        "descriptive_statistics": describe_dataframe(dataframe),
        "correlation": compute_correlation(dataframe, config["analysis"]["correlation"]),
    }


def compute_business_metrics(dataframe: pd.DataFrame) -> dict[str, Any]:
    """从数据中抽取业务维度指标：总收入/成本/利润率、按月收入汇总、按区域/品类汇总。

    Args:
        dataframe: 已清洗的数据框。

    Returns:
        业务指标字典。
    """
    metrics: dict[str, Any] = {}
    if {"revenue", "cost"}.issubset(dataframe.columns):
        profit = dataframe["revenue"] - dataframe["cost"]
        metrics["total_revenue"] = float(dataframe["revenue"].sum())
        metrics["total_cost"] = float(dataframe["cost"].sum())
        metrics["total_profit"] = float(profit.sum())
        metrics["profit_margin"] = float(profit.sum() / dataframe["revenue"].sum())

    if "order_date" in dataframe.columns and "revenue" in dataframe.columns:
        revenue_by_date = dataframe.groupby(pd.Grouper(key="order_date", freq="ME"))["revenue"].sum()
        metrics["revenue_by_month"] = {
            index.strftime("%Y-%m"): float(value) for index, value in revenue_by_date.items()
        }

    if "region" in dataframe.columns and "revenue" in dataframe.columns:
        metrics["revenue_by_region"] = (
            dataframe.groupby("region")["revenue"].sum().sort_values(ascending=False).to_dict()
        )

    if "category" in dataframe.columns and "revenue" in dataframe.columns:
        metrics["revenue_by_category"] = (
            dataframe.groupby("category")["revenue"].sum().sort_values(ascending=False).to_dict()
        )

    return metrics
