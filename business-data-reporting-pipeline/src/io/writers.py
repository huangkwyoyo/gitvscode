from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_dataframe(dataframe: pd.DataFrame, path: Path) -> None:
    """将 DataFrame 写入本地文件，支持 CSV 和 Excel 格式。

    Args:
        dataframe: 待写出的数据框。
        path: 输出文件路径（根据后缀自动选择格式）。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".csv":
        dataframe.to_csv(path, index=False)
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        dataframe.to_excel(path, index=False)
    else:
        raise ValueError(f"不支持的输出格式: {path.suffix}")

