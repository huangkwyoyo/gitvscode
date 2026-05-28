from __future__ import annotations

from typing import Any

import pandas as pd

from src.io.type_inference import infer_dataframe_types
from src.utils.env import get_env_value


def load_dataset(config: dict[str, Any]) -> pd.DataFrame:
    """根据配置加载数据源（CSV / Excel / 数据库），并自动推断列类型。

    Args:
        config: 包含 input.source_type 和相应路径/连接信息的配置字典。

    Returns:
        加载后的 DataFrame。
    """
    input_config = config["input"]
    source_type = input_config["source_type"]

    if source_type == "csv":
        return infer_dataframe_types(pd.read_csv(input_config["path"]), config)
    if source_type == "excel":
        return infer_dataframe_types(
            pd.read_excel(input_config["path"], sheet_name=input_config.get("sheet_name")),
            config,
        )
    if source_type == "database":
        try:
            from sqlalchemy import create_engine
        except ImportError as exc:
            raise RuntimeError("安装 sqlalchemy 以支持数据库数据源。") from exc

        database_url = get_env_value(input_config["database_url_env"])
        query = input_config["query"]
        engine = create_engine(database_url)
        return infer_dataframe_types(pd.read_sql(query, engine), config)

    raise ValueError(f"不支持的数据源类型: {source_type}")
