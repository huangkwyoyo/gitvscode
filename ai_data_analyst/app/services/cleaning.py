from __future__ import annotations

import numpy as np
import pandas as pd

from app.models import AnalysisState
from app.services.utils import normalize_preview_value


def _try_datetime(column: str, series: pd.Series) -> pd.Series:
    if series.dtype.name not in {"string", "object"}:
        return series
    date_hints = ("date", "time", "日期", "时间", "day", "month", "year")
    sample = series.dropna().astype(str).head(20)
    looks_like_date = sample.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}").mean() >= 0.6 if len(sample) else False
    if not looks_like_date and not any(hint in column.lower() for hint in date_hints):
        return series
    parsed = pd.to_datetime(series, errors="coerce")
    if parsed.notna().mean() >= 0.8:
        return parsed
    return series


def _try_numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return series
    cleaned = series.astype("string").str.replace(",", "", regex=False).str.replace("%", "", regex=False)
    parsed = pd.to_numeric(cleaned, errors="coerce")
    if parsed.notna().mean() >= 0.85:
        return parsed
    return series


def clean_data(state: AnalysisState) -> AnalysisState:
    if state.raw_df is None:
        raise ValueError("缺少原始数据")

    df = state.raw_df.copy()
    log: list[dict] = []

    before_rows = len(df)
    df = df.drop_duplicates()
    removed = before_rows - len(df)
    if removed:
        log.append({"type": "deduplicate", "message": f"删除重复行 {removed} 条"})

    for col in df.columns:
        original_dtype = str(df[col].dtype)
        df[col] = _try_datetime(col, df[col])
        df[col] = _try_numeric(df[col])
        new_dtype = str(df[col].dtype)
        if new_dtype != original_dtype:
            log.append({"type": "standardize", "field": col, "message": f"{col} 类型从 {original_dtype} 标准化为 {new_dtype}"})

    missing_before = int(df.isna().sum().sum())
    for col in df.columns:
        missing = int(df[col].isna().sum())
        if not missing:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            fill_value = df[col].median()
            df[col] = df[col].fillna(fill_value)
            strategy = f"中位数 {fill_value:.4g}" if pd.notna(fill_value) else "0"
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].ffill().bfill()
            strategy = "前后填充"
        else:
            mode = df[col].mode(dropna=True)
            fill_value = mode.iloc[0] if not mode.empty else "Unknown"
            df[col] = df[col].fillna(fill_value)
            strategy = f"众数 {fill_value}"
        log.append({"type": "missing", "field": col, "message": f"{col} 缺失 {missing} 个，使用{strategy}"})

    outliers: dict[str, int] = {}
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    for col in numeric_cols:
        series = pd.to_numeric(df[col], errors="coerce")
        std = series.std()
        if not np.isnan(std):
            z = ((series - series.mean()) / std).abs()
            count = int((z > 3).sum())
            if count:
                outliers[col] = count
                log.append({"type": "outlier", "field": col, "message": f"{col} 检测到 {count} 个 3-sigma 异常值"})

    missing_after = int(df.isna().sum().sum())
    completeness = 1 - (missing_after / max(df.size, 1))
    state.clean_df = df
    state.cleaning_log = log
    state.quality = {
        "rows_before": before_rows,
        "rows_after": int(len(df)),
        "missing_before": missing_before,
        "missing_after": missing_after,
        "completeness": round(completeness, 4),
        "outliers": outliers,
    }
    state.preview_rows = [
        {k: normalize_preview_value(v) for k, v in row.items()}
        for row in df.head(25).to_dict(orient="records")
    ]

    clean_path = state.output_dir / "cleaned_data.csv"
    df.to_csv(clean_path, index=False, encoding="utf-8-sig")
    return state
