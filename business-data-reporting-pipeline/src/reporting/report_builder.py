from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape


def build_report(
    dataframe: pd.DataFrame,
    analysis_result: dict[str, Any],
    chart_result: dict[str, Path],
    insight_result: dict[str, Any],
    config: dict[str, Any],
) -> Path:
    """使用 Jinja2 模板生成包含分析结果、图表和洞察的 HTML 报告。

    Args:
        dataframe: 已清洗的数据框。
        analysis_result: EDA 分析结果。
        chart_result: 图表输出路径字典。
        insight_result: LLM 或规则生成的洞察。
        config: 管道配置。

    Returns:
        生成的 HTML 报告文件路径。
    """
    output_dir = Path(config["report"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html.j2")
    html = template.render(
        title=config["report"]["title"],
        shape=analysis_result["shape"],
        metrics=analysis_result.get("business_metrics", {}),
        insights=insight_result,
        charts=chart_result,
        numeric_statistics=_to_html(analysis_result["descriptive_statistics"]["numeric"]),
        missing_statistics=_to_html(analysis_result["descriptive_statistics"]["missing"]),
    )

    output_path = output_dir / "report.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _to_html(dataframe: pd.DataFrame) -> str:
    """将 DataFrame 渲染为 HTML 表格字符串；空表返回提示语。"""
    if dataframe.empty:
        return "<p>No data available.</p>"
    return dataframe.to_html(classes="data-table", border=0)
