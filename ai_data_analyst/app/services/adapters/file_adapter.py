from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.services.adapters.base import DataSourceAdapter


class FileDataSourceAdapter(DataSourceAdapter):
    supported_suffixes = {".csv", ".xlsx", ".xls"}

    # CSV 编码尝试顺序：utf-8-sig > utf-8 > gbk（中文 Windows）> gb2312
    _CSV_ENCODINGS = ["utf-8-sig", "utf-8", "gbk", "gb2312"]

    def can_load(self, source: Path) -> bool:
        return source.suffix.lower() in self.supported_suffixes

    def load(self, source: Path) -> pd.DataFrame:
        suffix = source.suffix.lower()
        if suffix == ".csv":
            for encoding in self._CSV_ENCODINGS:
                try:
                    return pd.read_csv(source, encoding=encoding)
                except (UnicodeDecodeError, UnicodeError):
                    continue
            # 所有编码都失败时回退到 utf-8-sig，让异常自然抛出
            return pd.read_csv(source, encoding="utf-8-sig")
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(source)
        raise ValueError("仅支持 CSV、XLSX、XLS 文件")

