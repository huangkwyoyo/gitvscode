from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.services.adapters.base import DataSourceAdapter


class FileDataSourceAdapter(DataSourceAdapter):
    supported_suffixes = {".csv", ".xlsx", ".xls"}

    def can_load(self, source: Path) -> bool:
        return source.suffix.lower() in self.supported_suffixes

    def load(self, source: Path) -> pd.DataFrame:
        suffix = source.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(source, encoding="utf-8-sig")
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(source)
        raise ValueError("仅支持 CSV、XLSX、XLS 文件")

