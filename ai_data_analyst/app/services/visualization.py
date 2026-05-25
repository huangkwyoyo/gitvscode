from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.models import AnalysisState


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

    for col in numeric_cols[:4]:
        chart_specs.append(
            {
                "id": f"hist-{len(chart_specs)}",
                "type": "histogram",
                "title": f"{col} 分布",
                "field": col,
                "data": _histogram(df[col]),
            }
        )

    for col in categorical_cols[:4]:
        counts = df[col].astype(str).value_counts(dropna=False).head(10)
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

    state.chart_specs = chart_specs
    return state

