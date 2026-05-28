from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from app.services.adapters.base import DataSourceAdapter


class SQLiteDataSourceAdapter(DataSourceAdapter):
    """SQLite 数据源适配器：从本地 .db/.sqlite 文件读取第一个用户表。
    生产环境应通过安全后端配置传入连接信息和表名/SQL 查询，而非直接从 UI 获取。
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
            # 白名单校验：表名仅允许字母、数字、下划线，防止 SQL 注入
            if not table.replace("_", "").isalnum():
                raise ValueError(f"表名包含非法字符: {table}")
            if table not in tables["name"].values:
                raise ValueError(f"表不存在: {table}")
            return pd.read_sql_query(f'select * from "{table}"', conn)

