from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_dataframe(dataframe: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".csv":
        dataframe.to_csv(path, index=False)
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        dataframe.to_excel(path, index=False)
    else:
        raise ValueError(f"Unsupported output format: {path.suffix}")

