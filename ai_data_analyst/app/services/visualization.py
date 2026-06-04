from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.models import AnalysisState
from app.settings import MAX_VIS_BAR_COLS, MAX_VIS_HISTOGRAM_COLS


def _histogram(series: pd.Series, bins: int = 12):
    values = pd.to_numeric(series, errors="coerce").dropna().to_numpy()
    if len(values) == 0:
        return []
    counts, edges = np.histogram(values, bins=min(bins, max(3, int(math.sqrt(len(values))))))
    return [
        {
            "label": f"{edges[i]:.3g} - {edges[i + 1]:.3g}",
            "value": int(counts[i]),
        }
        for i in range(len(counts))
    ]


def build_chart_specs(state: AnalysisState) -> AnalysisState:
    if state.clean_df is None:
        raise ValueError("缺少清洗后的数据")

    df = state.clean_df
    chart_specs: list[dict] = []
    numeric_cols = state.exploration.get("numeric_columns", [])
    categorical_cols = state.exploration.get("categorical_columns", [])

    for col in numeric_cols[:MAX_VIS_HISTOGRAM_COLS]:
        chart_specs.append(
            {
                "id": f"hist-{len(chart_specs)}",
                "type": "histogram",
                "title": f"{col} 分布",
                "field": col,
                "data": _histogram(df[col]),
            }
        )

    for col in categorical_cols[:MAX_VIS_BAR_COLS]:
        counts = df[col].astype(str).value_counts(dropna=False).head(MAX_CATEGORY_VALUES)
        chart_specs.append(
            {
                "id": f"bar-{len(chart_specs)}",
                "type": "bar",
                "title": f"{col} Top 分类",
                "field": col,
                "data": [{"label": str(k), "value": int(v)} for k, v in counts.items()],
            }
        )

    if state.exploration.get("top_correlations"):
        chart_specs.append(
            {
                "id": "correlation-top",
                "type": "correlation",
                "title": "高相关字段",
                "data": state.exploration["top_correlations"][:8],
            }
        )

    if state.finance_metrics:
        chart_specs += _finance_charts(state.finance_metrics)

    state.chart_specs = chart_specs
    return state


def _finance_charts(metrics: dict) -> list[dict]:
    """为每个净值字段生成金融专属图表规格。"""
    charts = []
    for field_name, m in metrics.items():
        field_label = m.get("field", field_name)

        if m.get("cumulative_curve"):
            charts.append({
                "id": f"cumret-{field_name}",
                "type": "line",
                "title": f"{field_label} 累计收益曲线",
                "data": m["cumulative_curve"],
                "format": "pct",
            })

        if m.get("drawdown_curve"):
            charts.append({
                "id": f"drawdown-{field_name}",
                "type": "area",
                "title": f"{field_label} 回撤曲线",
                "data": m["drawdown_curve"],
                "format": "pct",
            })

        rolling = m.get("rolling_returns", {})
        if rolling:
            charts.append({
                "id": f"rolling-{field_name}",
                "type": "multiline",
                "title": f"{field_label} 滚动收益率",
                "data": rolling,
                "format": "pct",
            })

    return charts

