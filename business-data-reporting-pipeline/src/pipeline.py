from __future__ import annotations

from pathlib import Path

from src.analysis.eda import run_eda
from src.cleaning.cleaner import clean_dataframe
from src.config import load_config
from src.insights.llm_interpreter import extract_insights
from src.io.loaders import load_dataset
from src.reporting.report_builder import build_report
from src.reporting.table_exports import export_analysis_tables
from src.visualization.charts import create_charts


def run_pipeline(config_path: Path) -> Path:
    """按顺序执行完整的数据分析管道: 加载 -> 清洗 -> EDA -> 导出表格/图表 -> LLM洞察 -> 组装报告。

    Args:
        config_path: 配置文件路径。

    Returns:
        生成的 HTML 报告文件路径。
    """
    config = load_config(config_path)
    dataframe = load_dataset(config)
    cleaned = clean_dataframe(dataframe, config)
    analysis_result = run_eda(cleaned, config)
    export_analysis_tables(cleaned, analysis_result, config)
    chart_result = create_charts(cleaned, analysis_result, config)
    insight_result = extract_insights(cleaned, analysis_result, config)
    return build_report(cleaned, analysis_result, chart_result, insight_result, config)
