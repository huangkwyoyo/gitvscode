"""
歧义检测器和反问生成器。

职责：
    1. 检测 QuestionIntent 中的歧义（触发 contracts/question_policy.yml 中的 must_clarify 规则）
    2. 生成结构化的反问消息（提供 2-3 个具体选项，而非开放式问题）

检测规则来源：
    - TianShu contracts/question_policy.yml 中的 must_clarify 规则
    - 置信度阈值（config/agent_config.yml 中的 ambiguity_threshold）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .ir import QuestionIntent, TimeRangeType


@dataclass
class ClarificationRule:
    """反问规则"""
    trigger: str
    description: str
    keywords: list[str] = field(default_factory=list)
    ambiguity_between: list[str] = field(default_factory=list)
    clarification_template: str = ""


def load_clarification_rules(question_policy: dict[str, Any]) -> list[ClarificationRule]:
    """
    从 question_policy.yml 加载反问规则。

    Args:
        question_policy: contracts/question_policy.yml 的解析结果

    Returns:
        ClarificationRule 列表
    """
    rules: list[ClarificationRule] = []
    for rule_data in question_policy.get("must_clarify", []):
        rules.append(ClarificationRule(
            trigger=rule_data.get("trigger", ""),
            description=rule_data.get("description", ""),
            keywords=rule_data.get("keywords", []),
            ambiguity_between=rule_data.get("ambiguity_between", []),
            clarification_template=rule_data.get("clarification_template", ""),
        ))
    return rules


def detect_ambiguity(
    intent: QuestionIntent,
    raw_question: str,
    rules: list[ClarificationRule],
    ambiguity_threshold: float = 0.85,
) -> tuple[bool, Optional[str]]:
    """
    检测 QuestionIntent 中是否存在需要反问的歧义。

    Args:
        intent: Layer 1 的 QuestionIntent
        raw_question: 用户的原始问题文本
        rules: 反问规则列表
        ambiguity_threshold: 置信度阈值，低于此值视为有歧义

    Returns:
        (是否需要反问, 反问消息)
    """
    # 1. Intent 自身标记了需要反问
    if intent.needs_clarification:
        return True, intent.clarification_reason or "需要进一步确认您的需求"

    # 2. 置信度过低
    if intent.confidence < ambiguity_threshold:
        return True, f"对您的问题理解不够确定（置信度 {intent.confidence:.0%}），请重新描述或从以下选项中选择。"

    # 3. 模糊时间范围
    if intent.time_range.type == TimeRangeType.FUZZY and intent.metrics:
        return True, "请明确您要查询的时间范围，例如'2026年1月'或'2026年Q1（1-3月）'。"

    # 4. 基于关键词规则检测
    question_lower = raw_question.lower()
    for rule in rules:
        for keyword in rule.keywords:
            if keyword in question_lower:
                return True, rule.clarification_template

    return False, None


def generate_clarification(
    trigger: str,
    options: list[str],
) -> str:
    """
    生成结构化的反问消息。

    原则：提供 2-3 个具体选项让用户选择，而非问开放式问题。

    注意：
        当前反问流程中 detect_ambiguity() 直接返回规则模板中的消息，
        Agent.ask() Step 1.5 使用 intent.clarification_reason。
        此函数保留供未来增强反问交互时使用（如 REPL 中的选项式反问）。

    Args:
        trigger: 触发反问的原因
        options: 可选的具体选项（2-3 个）

    Returns:
        反问消息字符串
    """
    if not options:
        return f"需要确认：{trigger}"

    parts = [f"{trigger}"]
    for i, opt in enumerate(options, 1):
        parts.append(f"{i}. {opt}")
    parts.append("请选择一项（输入序号即可）。")

    return "\n".join(parts)
