from __future__ import annotations

import pandas as pd

from app.models import AnalysisState
from app.services.adapters.file_adapter import FileDataSourceAdapter
from app.services.adapters.sqlite_adapter import SQLiteDataSourceAdapter
from app.services.utils import build_preview


def load_data(state: AnalysisState) -> AnalysisState:
    adapters = [FileDataSourceAdapter(), SQLiteDataSourceAdapter()]
    adapter = next((item for item in adapters if item.can_load(state.upload_path)), None)
    if adapter is None:
        raise ValueError("仅支持 CSV、XLSX、XLS、SQLite 文件")
    df = adapter.load(state.upload_path)

    if df.empty:
        raise ValueError("数据文件为空")

    df.columns = [str(col).strip() for col in df.columns]
    df = df.convert_dtypes()

    schema_columns = []
    for col in df.columns:
        series = df[col]
        schema_columns.append(
            {
                "name": col,
                "dtype": str(series.dtype),
                "non_null": int(series.notna().sum()),
                "missing": int(series.isna().sum()),
                "unique": int(series.nunique(dropna=True)),
            }
        )

    state.raw_df = df
    state.schema = {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "fields": schema_columns,
    }
    state.preview_rows = build_preview(df)
    return state
