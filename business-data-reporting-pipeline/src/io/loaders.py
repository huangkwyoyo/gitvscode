from __future__ import annotations

from typing import Any

import pandas as pd

from src.io.type_inference import infer_dataframe_types
from src.utils.env import get_env_value


def load_dataset(config: dict[str, Any]) -> pd.DataFrame:
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
            raise RuntimeError("Install sqlalchemy to load database sources.") from exc

        database_url = get_env_value(input_config["database_url_env"])
        query = input_config["query"]
        engine = create_engine(database_url)
        return infer_dataframe_types(pd.read_sql(query, engine), config)

    raise ValueError(f"Unsupported source_type: {source_type}")
