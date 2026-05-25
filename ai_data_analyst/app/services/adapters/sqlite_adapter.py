from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from app.services.adapters.base import DataSourceAdapter


class SQLiteDataSourceAdapter(DataSourceAdapter):
    """Optional adapter example for future database mode.

    It expects a local SQLite file and reads the first user table. A production
    database adapter should receive an explicit connection profile and table or
    SQL query from a secured backend configuration, not directly from the UI.
    """

    supported_suffixes = {".db", ".sqlite", ".sqlite3"}

    def can_load(self, source: Path) -> bool:
        return source.suffix.lower() in self.supported_suffixes

    def load(self, source: Path) -> pd.DataFrame:
        with sqlite3.connect(source) as conn:
            tables = pd.read_sql_query(
                "select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name",
                conn,
            )
            if tables.empty:
                raise ValueError("SQLite 数据库中没有可读取的数据表")
            table = tables.iloc[0]["name"]
            return pd.read_sql_query(f'select * from "{table}"', conn)

