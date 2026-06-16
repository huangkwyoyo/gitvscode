"""
设计方案规划器。

M2 阶段只产生设计草案，不连接数据库，不执行查询。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .requirement_analyzer import RequirementSpec


@dataclass
class DevPlan:
    """数据开发设计草案"""
    request_id: str
    title: str
    business_goal: str
    source_tables: list[dict[str, Any]]
    required_fields: list[dict[str, Any]]
    metrics: list[dict[str, Any]]
    filters: dict[str, Any]
    grain: list[str]
    output_expectation: str
    human_review_points: list[str] = field(default_factory=list)
    pending_items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "request_id": self.request_id,
            "title": self.title,
            "business_goal": self.business_goal,
            "source_tables": self.source_tables,
            "required_fields": self.required_fields,
            "metrics": self.metrics,
            "filters": self.filters,
            "grain": self.grain,
            "output_expectation": self.output_expectation,
            "human_review_points": self.human_review_points,
            "pending_items": self.pending_items,
        }


def build_design_plan(requirement: RequirementSpec) -> DevPlan:
    """
    根据需求生成设计草案。

    只使用 requirement 中显式声明的信息，不推断 JOIN 关系。
    """
    pending_items: list[str] = []
    human_review_points = list(requirement.human_review_points)

    if len(requirement.source_tables) > 1:
        pending_items.append("TODO: 多表需求未声明 JOIN 关系，M2 不自动生成 JOIN")
        human_review_points.append("Human Review: 多表 JOIN 路径需要人工确认")

    for metric in requirement.metrics:
        if not metric.get("definition_source"):
            pending_items.append(f"Human Review: 指标 {metric.get('name')} 缺少 metric 口径来源")

    for field in requirement.required_fields:
        if not field.get("source"):
            pending_items.append(f"Human Review: 字段 {field.get('name')} 缺少字段来源说明")

    return DevPlan(
        request_id=requirement.request_id,
        title=requirement.title,
        business_goal=requirement.business_goal,
        source_tables=requirement.source_tables,
        required_fields=requirement.required_fields,
        metrics=requirement.metrics,
        filters=requirement.filters,
        grain=requirement.grain,
        output_expectation=requirement.output_expectation,
        human_review_points=human_review_points,
        pending_items=pending_items,
    )
