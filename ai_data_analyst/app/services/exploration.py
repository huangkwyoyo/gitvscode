from __future__ import annotations

import pandas as pd

from app.models import AnalysisState
from app.services.finance_metrics import compute_finance_metrics, detect_time_series
from app.services.utils import safe_float


def explore_data(state: AnalysisState) -> AnalysisState:
    if state.clean_df is None:
        raise ValueError("缺少清洗后的数据")

    df = state.clean_df
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    categorical_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]

    numeric_summary = {}
    for col in numeric_cols:
        s = df[col]  # cleaning.py 已完成类型转换，无需重复 to_numeric
        numeric_summary[col] = {
            "mean": safe_float(s.mean()),
            "median": safe_float(s.median()),
            "std": safe_float(s.std()),
            "min": safe_float(s.min()),
            "max": safe_float(s.max()),
            "q1": safe_float(s.quantile(0.25)),
            "q3": safe_float(s.quantile(0.75)),
        }

    categorical_summary = {}
    for col in categorical_cols[:12]:
        counts = df[col].astype(str).value_counts(dropna=False).head(8)
        categorical_summary[col] = [{"label": str(k), "value": int(v)} for k, v in counts.items()]

    correlations = []
    if len(numeric_cols) >= 2:
        # 数值列过多时限制计算规模，避免 O(n²) 性能问题
        MAX_CORR_COLS = 20
        corr_cols = numeric_cols[:MAX_CORR_COLS]
        corr = df[corr_cols].corr(numeric_only=True)
        for row in corr.index:
            for col in corr.columns:
                if row < col:
                    value = corr.loc[row, col]
                    if pd.notna(value):
                        correlations.append({"x": row, "y": col, "value": safe_float(value)})
        correlations.sort(key=lambda item: abs(item["value"]), reverse=True)

    date_col, nav_cols, benchmark_col = detect_time_series(df)
    finance_metrics = {}
    if state.analysis_type == "finance" and date_col and nav_cols:
        finance_metrics = compute_finance_metrics(df, date_col, nav_cols, benchmark_col, errors=state.errors)

    state.exploration = {
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "numeric_summary": numeric_summary,
        "categorical_summary": categorical_summary,
        "top_correlations": correlations[:10],
        "date_column": date_col,
        "nav_columns": nav_cols,
        "benchmark_column": benchmark_col,
    }
    state.finance_metrics = finance_metrics
    return state
