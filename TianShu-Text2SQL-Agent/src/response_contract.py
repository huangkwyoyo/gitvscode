"""
Phase 6A —— 统一公开响应契约。

职责：
    将内部 AgentResponse 转换为安全、稳定、向后兼容的公开响应结构，
    明确区分公开数据与内部诊断信息的边界。

严格边界：
    1. 不含 SQL 文本（generated_sql）
    2. 不含内部 trace
    3. 不含 API Key / Authorization header / 环境变量
    4. answer / clarification / refusal / error 互斥
    5. sources 只来自真实 SQLResult / ResultSummary
    6. 不修改传入的 AgentResponse
    7. 输出必须是 JSON-native 类型（date/datetime/tuple 等已规范化）
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from .ir import AgentResponse

# ── 当前契约版本 ──
CONTRACT_VERSION = "1.0"

# ── 敏感信息检测正则（用于日志/脱敏，不修改传入数据）──
_SENSITIVE_PATTERNS: list[re.Pattern] = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)(OPENAI_API_KEY|DEEPSEEK_API_KEY|API_KEY)\s*[=:]\s*\S+"),
    re.compile(r"(?i)(Authorization|Bearer)\s*[=:]\s*\S+"),
    re.compile(r"(?i)(token|secret)\s*[=:]\s*\S+"),
]


def build_public_response(response: AgentResponse) -> dict[str, Any]:
    """
    从 AgentResponse 构建安全的公开响应结构。

    决策逻辑（按优先级）：
        1. clarification_needed=True 且非 refusal → response_type="clarification"
        2. refusal=True → response_type="refusal"
        3. result.error 非空 → response_type="error"
        4. 其他 → response_type="answer"

    Args:
        response: Agent 内部响应对象

    Returns:
        公开响应 dict，包含 contract_version、response_type、question、
        answer/clarification/refusal、data、warnings、meta
    """
    # ── 确定 response_type（互斥）──
    response_type = _determine_response_type(response)

    # ── 构建各部分 ──
    answer = _build_answer_section(response, response_type)
    clarification = _build_clarification_section(response, response_type)
    refusal = _build_refusal_section(response, response_type)
    data = _build_data_section(response, response_type)
    warnings = _build_warnings_section(response)
    meta = _build_meta_section(response)

    return _normalize_json_value({
        "contract_version": CONTRACT_VERSION,
        "response_type": response_type,
        "question": response.question,
        "answer": answer,
        "clarification": clarification,
        "refusal": refusal,
        "data": data,
        "warnings": warnings,
        "meta": meta,
    })


# ═══════════════════════════════════════════════════════════════
# JSON-native 类型规范化
# ═══════════════════════════════════════════════════════════════


def _normalize_json_value(obj: Any, _path: str = "$") -> Any:
    """
    递归将 Python 运行时类型转换为 JSON-native 类型。

    转换规则：
        - datetime.date       → ISO 字符串 "YYYY-MM-DD"
        - datetime.datetime   → ISO 字符串 "YYYY-MM-DDTHH:MM:SS"
        - tuple               → list
        - dict                → 递归处理所有 value
        - list                → 递归处理所有元素
        - str/int/float/bool/None → 原样返回（已是 JSON-native）

    不可转换的未知类型 → 抛出 TypeError（fail-loud 原则，避免静默丢失数据）。

    注意：Public response 不应包含 Decimal/numpy/DuckDB 特殊类型，
    这些类型应在更早的阶段（Agent 层）就转为 Python 标量。
    """
    # JSON-native 原子类型直通（不检查 bool/isinstance，因为 bool 是 int 的子类）
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    # int 检查必须在 float 之前（bool 也满足 isinstance(True, int) 但上面已处理）
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        return obj

    # Python 日期时间类型 → ISO 字符串
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()

    # tuple → list
    if isinstance(obj, tuple):
        return [_normalize_json_value(v, f"{_path}[{i}]") for i, v in enumerate(obj)]

    # 递归处理容器类型
    if isinstance(obj, dict):
        return {k: _normalize_json_value(v, f"{_path}.{k}") for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_json_value(v, f"{_path}[{i}]") for i, v in enumerate(obj)]

    # 未知类型：fail-loud，不在公开响应中静默丢弃数据
    raise TypeError(
        f"build_public_response 输出包含非 JSON-native 类型 "
        f"{type(obj).__module__}.{type(obj).__qualname__} "
        f"位于 {_path}。请在调用方提前规范化。"
    )


# ═══════════════════════════════════════════════════════════════
# 内部辅助函数
# ═══════════════════════════════════════════════════════════════


def _determine_response_type(response: AgentResponse) -> str:
    """
    确定唯一的 response_type。

    优先级：clarification > refusal > error > answer。
    这是互斥的——只返回优先级最高的一个类型。
    """
    # clarification 和 refusal 按响应本身的标记判断
    if response.clarification_needed and not response.refusal:
        return "clarification"

    if response.refusal:
        return "refusal"

    # 执行错误：result 存在且 error 非空
    if response.result is not None and response.result.error:
        return "error"

    return "answer"


def _build_answer_section(response: AgentResponse, response_type: str) -> dict[str, Any]:
    """构建 answer 段：只在 response_type=answer 时有内容"""
    if response_type == "answer":
        return {
            "text": response.chinese_answer or "",
        }
    return {"text": None}


def _build_clarification_section(response: AgentResponse, response_type: str) -> dict[str, Any]:
    """构建 clarification 段：只在 response_type=clarification 时有内容"""
    if response_type == "clarification":
        return {
            "needed": True,
            "message": response.clarification_message or "",
        }
    return {"needed": False, "message": None}


def _build_refusal_section(response: AgentResponse, response_type: str) -> dict[str, Any]:
    """构建 refusal 段：只在 response_type=refusal 时有内容"""
    if response_type == "refusal":
        return {
            "refused": True,
            "reason": response.refusal_reason or "",
        }
    return {"refused": False, "reason": None}


def _build_data_section(response: AgentResponse, response_type: str) -> dict[str, Any]:
    """
    构建 data 段：包含结构化执行产物。

    只在 response_type=answer 时填充真实数据，
    clarification/refusal/error 时保持空值。
    """
    if response_type != "answer":
        return {
            "is_multi_plan": False,
            "summaries": [],
            "merged_result": None,
            "chart_spec": None,
            "sources": [],
        }

    # ── 提取 sources（只来自 ResultSummary 的 primary_table）──
    sources = _extract_sources(response)

    return {
        "is_multi_plan": response.is_multi_plan,
        "summaries": list(response.result_summaries),
        "merged_result": response.merged_result,
        "chart_spec": response.chart_spec,
        "sources": sources,
    }


def _extract_sources(response: AgentResponse) -> list[str]:
    """从 ResultSummary 列表中提取数据来源表名（去重）"""
    sources: list[str] = []
    seen: set[str] = set()
    for summary_dict in response.result_summaries:
        table = summary_dict.get("primary_table", "") if isinstance(summary_dict, dict) else ""
        if table and table not in seen:
            sources.append(table)
            seen.add(table)
    return sources


def _build_warnings_section(response: AgentResponse) -> list[str]:
    """构建 warnings 段：直接从 response.warnings 安全复制"""
    return list(response.warnings) if response.warnings else []


def _build_meta_section(response: AgentResponse) -> dict[str, Any]:
    """构建 meta 段：元信息，不含敏感数据"""
    mode = response.execution_mode or ""
    if not mode:
        # 根据 context 推断
        if response.is_multi_plan:
            mode = "serial"  # 默认多计划为串行
        else:
            mode = "single"

    return {
        "execution_mode": mode,
    }
