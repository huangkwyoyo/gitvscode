"""
LLM 输出结构化 Schema 校验器。

为四个 Prompt 模板的 JSON 输出提供独立校验函数。
每个函数返回错误列表（空列表 = 校验通过），供 LLMAdapter 在 IR 转换前调用。

依赖 jsonschema（已在 pyproject.toml 中声明），无 LLM 运行时依赖。
"""

from __future__ import annotations

from typing import Any

import jsonschema


# ═══════════════════════════════════════════════════════════
# 共享定义
# ═══════════════════════════════════════════════════════════

# human_review 子结构 —— 所有四个模板共用
_HUMAN_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "requires_review": {"type": "boolean"},
        "flagged_fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["field", "reason"],
                "additionalProperties": False,
            },
        },
        "reason": {"type": ["string", "null"]},
    },
    "required": ["requires_review", "flagged_fields"],
    "additionalProperties": False,
}

# 允许的 domain 枚举值
_ALLOWED_DOMAINS = [
    "traffic", "safety", "violation", "supply", "asset", "spatial", None,
]

# 允许的 intent_type 枚举值
_ALLOWED_INTENT_TYPES = [
    "aggregation", "ranking", "trend", "comparison", "listing", None,
]

# 允许的 time_range type 枚举值
_ALLOWED_TIME_TYPES = ["absolute", "relative", "fuzzy"]

# 允许的 strategy 枚举值
_ALLOWED_STRATEGIES = [
    "g3_direct", "g3_cross", "g2_fact", "g2_fact_join",
    "g0_dim_direct", "need_clarification",
]


# ═══════════════════════════════════════════════════════════
# 1. 意图分类器输出校验
# ═══════════════════════════════════════════════════════════

INTENT_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "domain": {
            "anyOf": [
                {"type": "string", "enum": [d for d in _ALLOWED_DOMAINS if d]},
                {"type": "null"},
            ],
        },
        "intent_type": {
            "anyOf": [
                {"type": "string", "enum": [t for t in _ALLOWED_INTENT_TYPES if t]},
                {"type": "null"},
            ],
        },
        "metrics": {
            "type": "array",
            "items": {"type": "string"},
        },
        "time_range": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": _ALLOWED_TIME_TYPES},
                "start": {"type": ["string", "null"]},
                "end": {"type": ["string", "null"]},
                "raw_expression": {"type": ["string", "null"]},
            },
            "required": ["type", "start", "end", "raw_expression"],
            "additionalProperties": False,
        },
        "dimensions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "filters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "op": {"type": "string"},
                    "value": {"type": "string"},
                    "value_type": {"type": "string"},
                },
                "required": ["field", "op", "value"],
                "additionalProperties": False,
            },
        },
        "needs_clarification": {"type": "boolean"},
        "clarification_reason": {"type": ["string", "null"]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "raw_question": {"type": ["string", "null"]},
        "human_review": _HUMAN_REVIEW_SCHEMA,
    },
    "required": [
        "domain", "intent_type", "metrics", "time_range", "dimensions",
        "filters", "needs_clarification", "clarification_reason",
        "confidence", "raw_question",
    ],
    "additionalProperties": False,
}


# ── Refusal 输出格式（拒绝回答） ──

REFUSAL_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "refusal": {"type": "boolean", "const": True},
        "refusal_reason": {"type": "string", "minLength": 1},
    },
    "required": ["refusal", "refusal_reason"],
    "additionalProperties": False,
}


def is_refusal_output(data: dict[str, Any]) -> bool:
    """判断 LLM 输出是否为拒绝回答。

    Args:
        data: LLM 返回的 JSON 字典。

    Returns:
        True 表示这是一个拒绝回答。
    """
    return data.get("refusal") is True and isinstance(data.get("refusal_reason"), str)


def _validate_refusal(data: dict[str, Any]) -> list[str]:
    """校验 refusal 输出格式（内部使用，由 validate_intent_output 调用）。"""
    errors: list[str] = []
    try:
        jsonschema.validate(data, REFUSAL_OUTPUT_SCHEMA)
    except jsonschema.ValidationError as exc:
        errors.append(f"refusal_output 结构校验失败: {exc.message}")
    return errors


def validate_intent_output(data: dict[str, Any]) -> list[str]:
    """校验意图分类器输出的 JSON 结构。

    同时兼容 QuestionIntent 和 Refusal 两种输出格式：
        - 包含 refusal=true 的字典走 refusal 校验路径
        - 其他走 QuestionIntent 校验路径

    Args:
        data: LLM 返回的 JSON 字典。

    Returns:
        错误列表。空列表表示校验通过。
    """
    # 优先判断是否为 refusal 输出
    if data.get("refusal") is True:
        return _validate_refusal(data)

    errors: list[str] = []

    try:
        jsonschema.validate(data, INTENT_OUTPUT_SCHEMA)
    except jsonschema.ValidationError as exc:
        errors.append(f"intent_output 结构校验失败: {exc.message}")
        return errors

    # 语义级交叉校验：needs_clarification 为 true 时必须填写原因
    if data.get("needs_clarification") and not data.get("clarification_reason"):
        errors.append(
            "needs_clarification 为 true，但 clarification_reason 为空"
        )

    # 语义级交叉校验：低置信度 + 未标记 needs_clarification → 警告
    confidence = data.get("confidence", 1.0)
    if confidence < 0.65 and not data.get("needs_clarification"):
        human = data.get("human_review", {})
        if not human.get("requires_review"):
            errors.append(
                f"confidence ({confidence}) < 0.65 但未设置 needs_clarification "
                f"且 human_review.requires_review 为 false"
            )

    return errors


# ═══════════════════════════════════════════════════════════
# 2. SQL 规划器输出校验
# ═══════════════════════════════════════════════════════════

PLAN_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "strategy": {"type": "string", "enum": _ALLOWED_STRATEGIES},
        "primary_table": {"type": ["string", "null"]},
        "joins": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "table": {"type": "string"},
                    "on": {"type": "string"},
                    "type": {"type": "string"},
                },
                "required": ["table", "on", "type"],
                "additionalProperties": False,
            },
        },
        "where_clauses": {
            "type": "array",
            "items": {"type": "string"},
        },
        "group_by": {
            "type": "array",
            "items": {"type": "string"},
        },
        "order_by": {
            "type": "array",
            "items": {"type": "string"},
        },
        "aggregations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "expr": {"type": "string"},
                    "alias": {"type": "string"},
                },
                "required": ["expr", "alias"],
                "additionalProperties": False,
            },
        },
        "limit": {"type": ["integer", "null"]},
        "downgrade_reason": {"type": ["string", "null"]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "human_review": _HUMAN_REVIEW_SCHEMA,
    },
    "required": [
        "strategy", "primary_table", "joins", "where_clauses", "group_by",
        "order_by", "aggregations", "limit", "downgrade_reason", "confidence",
    ],
    "additionalProperties": False,
}


def validate_plan_output(data: dict[str, Any]) -> list[str]:
    """校验 SQL 规划器输出的 JSON 结构。

    Args:
        data: LLM 返回的 SQLPlan JSON 字典。

    Returns:
        错误列表。空列表表示校验通过。
    """
    errors: list[str] = []

    try:
        jsonschema.validate(data, PLAN_OUTPUT_SCHEMA)
    except jsonschema.ValidationError as exc:
        errors.append(f"plan_output 结构校验失败: {exc.message}")
        return errors

    # 语义级交叉校验：非 G3_DIRECT 策略必须填写降级原因
    strategy = data.get("strategy", "")
    if strategy not in ("g3_direct", "g0_dim_direct", "need_clarification"):
        if not data.get("downgrade_reason"):
            errors.append(
                f"策略 {strategy} 非最优路径，但 downgrade_reason 为空"
            )

    # 语义级交叉校验：非 need_clarification 策略必须指定主表
    if strategy != "need_clarification" and not data.get("primary_table"):
        errors.append(
            f"策略 {strategy} 不是 need_clarification，"
            f"但 primary_table 为空"
        )

    return errors


# ═══════════════════════════════════════════════════════════
# 3. SQL 生成器输出校验
# ═══════════════════════════════════════════════════════════

SQL_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "sql": {"type": "string", "minLength": 1},
        "source_table": {"type": "string"},
        "notes": {
            "type": "array",
            "items": {"type": "string"},
        },
        "human_review": _HUMAN_REVIEW_SCHEMA,
    },
    "required": ["sql", "source_table"],
    "additionalProperties": False,
}


def validate_sql_output(data: dict[str, Any]) -> list[str]:
    """校验 SQL 生成器输出的 JSON 结构。

    Args:
        data: LLM 返回的 SQL JSON 字典。

    Returns:
        错误列表。空列表表示校验通过。
    """
    errors: list[str] = []

    try:
        jsonschema.validate(data, SQL_OUTPUT_SCHEMA)
    except jsonschema.ValidationError as exc:
        errors.append(f"sql_output 结构校验失败: {exc.message}")
        return errors

    # 语义级交叉校验：SQL 必须以 SELECT 开头（忽略前导空白）
    sql = data.get("sql", "")
    if not sql.strip().upper().startswith("SELECT"):
        errors.append(
            "生成的 SQL 必须以 SELECT 开头，不允许其他语句类型"
        )

    return errors


# ═══════════════════════════════════════════════════════════
# 4. 结果解释器输出校验
# ═══════════════════════════════════════════════════════════

EXPLAIN_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "answer_zh": {"type": "string", "minLength": 1},
        "source_table": {"type": "string"},
        "metric_notes": {
            "type": "array",
            "items": {"type": "string"},
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
        },
        "human_review": _HUMAN_REVIEW_SCHEMA,
    },
    "required": ["answer_zh", "source_table"],
    "additionalProperties": False,
}


def validate_explain_output(data: dict[str, Any]) -> list[str]:
    """校验结果解释器输出的 JSON 结构。

    Args:
        data: LLM 返回的解释 JSON 字典。

    Returns:
        错误列表。空列表表示校验通过。
    """
    errors: list[str] = []

    try:
        jsonschema.validate(data, EXPLAIN_OUTPUT_SCHEMA)
    except jsonschema.ValidationError as exc:
        errors.append(f"explain_output 结构校验失败: {exc.message}")

    return errors
