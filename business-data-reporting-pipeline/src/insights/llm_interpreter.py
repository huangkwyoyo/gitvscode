from __future__ import annotations

from typing import Any
import json

import pandas as pd

from src.utils.env import get_env_value


def extract_insights(
    dataframe: pd.DataFrame,
    analysis_result: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """提取业务洞察：若 LLM 启用则调用大模型，否则回退到规则引擎。

    Args:
        dataframe: 已清洗的数据框。
        analysis_result: EDA 分析结果字典。
        config: 管道配置字典。

    Returns:
        包含 summary、highlights、risks、recommended_actions 的洞察字典。
    """
    if not config["llm"].get("enabled", False):
        return _rule_based_insights(dataframe, analysis_result)

    if config["llm"].get("provider") != "openai":
        raise ValueError(f"不支持的 LLM 提供商: {config['llm'].get('provider')}")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("安装 llm 依赖以启用 OpenAI 洞察: pip install -e .[llm]") from exc

    client = OpenAI(api_key=get_env_value(config["llm"].get("api_key_env", "OPENAI_API_KEY")))
    context = _build_llm_context(dataframe, analysis_result, config)
    response = client.responses.create(
        model=config["llm"].get("model", "gpt-4.1-mini"),
        temperature=config["llm"].get("temperature", 0.2),
        input=[
            {
                "role": "system",
                "content": (
                    "你是资深业务数据分析师。请基于数据统计结果输出简洁、可执行的中文洞察。"
                    "必须返回 JSON，字段为 summary、highlights、risks、recommended_actions。"
                ),
            },
            {"role": "user", "content": json.dumps(context, ensure_ascii=False, default=str)},
        ],
    )
    text = response.output_text
    return {
        **_safe_parse_json(text),
        "raw_response": text,
    }


def _rule_based_insights(dataframe: pd.DataFrame, analysis_result: dict[str, Any]) -> dict[str, Any]:
    """基于规则的轻量洞察引擎：从业务指标和异常值标志中提取关键信息。"""
    metrics = analysis_result.get("business_metrics", {})
    highlights: list[str] = []
    risks: list[str] = []
    actions: list[str] = []

    if "total_revenue" in metrics:
        highlights.append(f"总收入为 {metrics['total_revenue']:,.0f}，利润率为 {metrics['profit_margin']:.1%}。")

    revenue_by_region = metrics.get("revenue_by_region", {})
    if revenue_by_region:
        top_region = max(revenue_by_region, key=revenue_by_region.get)
        highlights.append(f"{top_region} 区域贡献收入最高，收入为 {revenue_by_region[top_region]:,.0f}。")
        actions.append(f"复盘 {top_region} 区域的渠道和客户结构，沉淀可复制打法。")

    outlier_flags = dataframe.attrs.get("outlier_flags")
    if isinstance(outlier_flags, pd.DataFrame) and outlier_flags.any().any():
        outlier_columns = [column for column in outlier_flags.columns if outlier_flags[column].any()]
        risks.append(f"检测到异常值字段：{', '.join(outlier_columns)}，建议结合业务事件核验。")

    if not highlights:
        highlights.append("数据已完成清洗和基础统计，可开启 LLM 以生成更深入的业务解读。")

    return {
        "summary": "；".join(highlights),
        "highlights": highlights,
        "risks": risks,
        "recommended_actions": actions,
    }


def _build_llm_context(
    dataframe: pd.DataFrame,
    analysis_result: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """构造发送给 LLM 的上下文摘要，避免暴露全部原始数据。"""
    max_sample_rows = config["llm"].get("max_sample_rows", 8)
    descriptive = analysis_result["descriptive_statistics"]
    return {
        "shape": analysis_result["shape"],
        "columns": analysis_result["columns"],
        "business_metrics": analysis_result.get("business_metrics", {}),
        "numeric_statistics": descriptive["numeric"].round(4).to_dict(),
        "missing_statistics": descriptive["missing"].to_dict(),
        "sample_rows": dataframe.head(max_sample_rows).to_dict(orient="records"),
    }


def _safe_parse_json(text: str) -> dict[str, Any]:
    """安全解析 LLM 返回的 JSON 文本，解析失败时返回结构化默认值。"""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {
            "summary": text,
            "highlights": [],
            "risks": [],
            "recommended_actions": [],
        }
    return {
        "summary": parsed.get("summary", ""),
        "highlights": parsed.get("highlights", []),
        "risks": parsed.get("risks", []),
        "recommended_actions": parsed.get("recommended_actions", []),
    }
