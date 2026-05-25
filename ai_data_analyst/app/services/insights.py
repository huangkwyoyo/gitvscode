from __future__ import annotations

import os

from app.models import AnalysisState


def _rule_based_insights(state: AnalysisState) -> list[str]:
    insights: list[str] = []
    schema = state.schema
    quality = state.quality
    exploration = state.exploration

    insights.append(f"数据集包含 {schema.get('rows', 0)} 行、{schema.get('columns', 0)} 列，清洗后保留 {quality.get('rows_after', 0)} 行。")

    if quality.get("missing_before", 0):
        insights.append(f"原始数据存在 {quality['missing_before']} 个缺失值，已按字段类型自动填补，当前完整度 {quality.get('completeness', 0) * 100:.1f}%。")
    else:
        insights.append("原始数据未发现缺失值，整体字段完整度较好。")

    if quality.get("outliers"):
        fields = ", ".join(f"{k}({v})" for k, v in quality["outliers"].items())
        insights.append(f"检测到数值异常字段：{fields}。建议结合业务含义判断是否为真实极端表现或录入问题。")

    correlations = exploration.get("top_correlations", [])
    if correlations:
        top = correlations[0]
        insights.append(f"最高相关关系是 {top['x']} 与 {top['y']}，相关系数 {top['value']}，可优先作为联动分析入口。")

    numeric_summary = exploration.get("numeric_summary", {})
    for field, stats in list(numeric_summary.items())[:3]:
        if stats.get("mean") is not None and stats.get("median") is not None:
            gap = abs(stats["mean"] - stats["median"])
            spread = abs(stats.get("max", 0) - stats.get("min", 0)) or 1
            if gap / spread > 0.15:
                insights.append(f"{field} 的均值和中位数差异较明显，分布可能存在偏态或极端值影响。")

    if state.analysis_goal:
        insights.append(f"围绕你的分析需求：{state.analysis_goal[:120]}，建议重点查看高相关字段、异常字段和主要分类分布。")

    return insights


def _llm_insights(state: AnalysisState, base_insights: list[str]) -> list[str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return base_insights

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=os.getenv("OPENAI_BASE_URL") or None)
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        prompt = {
            "goal": state.analysis_goal,
            "schema": state.schema,
            "quality": state.quality,
            "exploration": {
                "numeric_summary": state.exploration.get("numeric_summary", {}),
                "top_correlations": state.exploration.get("top_correlations", [])[:5],
            },
            "local_insights": base_insights,
        }
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是严谨的业务数据分析师。用中文输出5条可执行洞察，避免夸大因果。"},
                {"role": "user", "content": str(prompt)},
            ],
            temperature=0.2,
        )
        text = response.choices[0].message.content or ""
        llm_lines = [line.strip(" -0123456789.、") for line in text.splitlines() if line.strip()]
        return llm_lines[:8] or base_insights
    except Exception as exc:
        base_insights.append(f"LLM 洞察调用失败，已保留本地规则洞察：{exc}")
        return base_insights


def generate_insights(state: AnalysisState) -> AnalysisState:
    base = _rule_based_insights(state)
    state.insights = _llm_insights(state, base)
    return state

