from __future__ import annotations

import pandas as pd

from app.models import AnalysisState


def _safe_float(value):
    if pd.isna(value):
        return None
    return round(float(value), 4)


def explore_data(state: AnalysisState) -> AnalysisState:
    if state.clean_df is None:
        raise ValueError("缺少清洗后的数据")

    df = state.clean_df
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    categorical_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]

    numeric_summary = {}
    for col in numeric_cols:
        s = pd.to_numeric(df[col], errors="coerce")
        numeric_summary[col] = {
            "mean": _safe_float(s.mean()),
            "median": _safe_float(s.median()),
            "std": _safe_float(s.std()),
            "min": _safe_float(s.min()),
            "max": _safe_float(s.max()),
            "q1": _safe_float(s.quantile(0.25)),
            "q3": _safe_float(s.quantile(0.75)),
        }

    categorical_summary = {}
    for col in categorical_cols[:12]:
        counts = df[col].astype(str).value_counts(dropna=False).head(8)
        categorical_summary[col] = [{"label": str(k), "value": int(v)} for k, v in counts.items()]

    correlations = []
    if len(numeric_cols) >= 2:
        corr = df[numeric_cols].corr(numeric_only=True)
        for row in corr.index:
            for col in corr.columns:
                if row < col:
                    value = corr.loc[row, col]
                    if pd.notna(value):
                        correlations.append({"x": row, "y": col, "value": round(float(value), 4)})
        correlations.sort(key=lambda item: abs(item["value"]), reverse=True)

    state.exploration = {
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "numeric_summary": numeric_summary,
        "categorical_summary": categorical_summary,
        "top_correlations": correlations[:10],
    }
    return state

