"""
需求分析器。

M2 阶段只读取显式声明的 YAML 字段，不补造业务含义。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class RequirementSpec:
    """标准化需求说明"""
    request_id: str
    title: str
    business_goal: str
    source_tables: list[dict[str, Any]] = field(default_factory=list)
    required_fields: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, Any]] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    grain: list[str] = field(default_factory=list)
    output_expectation: str = ""
    human_notes: list[str] = field(default_factory=list)
    human_review_points: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def allowed_tables(self) -> set[str]:
        """返回 fixture 显式声明的表"""
        return {str(t.get("name", "")).strip() for t in self.source_tables if t.get("name")}

    def allowed_fields(self) -> set[str]:
        """返回 fixture 显式声明的字段"""
        fields = {str(f.get("name", "")).strip() for f in self.required_fields if f.get("name")}
        fields.update(str(m.get("field", "")).strip() for m in self.metrics if m.get("field"))
        fields.update(str(g).strip() for g in self.grain if g)
        return {f for f in fields if f}


def _require_list(data: dict[str, Any], key: str) -> list[Any]:
    """读取必填列表字段，缺失时失败"""
    value = data.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{key} 必须是非空列表")
    return value


def analyze_requirement(requirement_path: str | Path) -> RequirementSpec:
    """
    读取 YAML fixture 并输出标准化需求。

    request_id 必须由用户显式提供，缺失时直接失败。
    """
    path = Path(requirement_path)
    if not path.exists():
        raise ValueError(f"需求文件不存在: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise ValueError("需求文件必须是非空 YAML 对象")

    request_id = str(data.get("request_id", "")).strip()
    if not request_id:
        raise ValueError("缺少必填字段 request_id，不能自动编造")

    human_review_points = list(data.get("human_review_points") or [])
    if not human_review_points:
        human_review_points.append("Human Review: M2 仅生成草案，所有口径和字段来源需人工复核")

    return RequirementSpec(
        request_id=request_id,
        title=str(data.get("title", "")).strip(),
        business_goal=str(data.get("business_goal", "")).strip(),
        source_tables=_require_list(data, "source_tables"),
        required_fields=_require_list(data, "required_fields"),
        metrics=_require_list(data, "metrics"),
        filters=dict(data.get("filters") or {}),
        grain=[str(g) for g in data.get("grain", [])],
        output_expectation=str(data.get("output_expectation", "")).strip(),
        human_notes=[str(n) for n in data.get("human_notes", [])],
        human_review_points=[str(p) for p in human_review_points],
        raw=data,
    )
