"""分析表格导出模块 — 输出清洗数据、描述统计和相关性矩阵到 CSV。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def export_analysis_tables(
    dataframe: pd.DataFrame,
    analysis_result: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Path]:
    """导出清洗后的数据和各项统计结果为 CSV 文件到指定目录。

    包括：cleaned_data、各类描述性统计、相关性矩阵。

    Args:
        dataframe: 已清洗的数据框。
        analysis_result: EDA 分析结果。
        config: 管道配置，包含 report.tables_dir。

    Returns:
        文件名到路径的映射字典。
    """
    tables_dir = Path(config["report"]["tables_dir"])
    tables_dir.mkdir(parents=True, exist_ok=True)

    outputs: dict[str, Path] = {}
    cleaned_path = tables_dir / "cleaned_data.csv"
    dataframe.to_csv(cleaned_path, index=False)
    outputs["cleaned_data"] = cleaned_path

    for name, table in analysis_result["descriptive_statistics"].items():
        path = tables_dir / f"{name}_statistics.csv"
        table.to_csv(path)
        outputs[f"{name}_statistics"] = path

    correlation = analysis_result.get("correlation")
    if isinstance(correlation, pd.DataFrame) and not correlation.empty:
        path = tables_dir / "correlation.csv"
        correlation.to_csv(path)
        outputs["correlation"] = path

    return outputs
