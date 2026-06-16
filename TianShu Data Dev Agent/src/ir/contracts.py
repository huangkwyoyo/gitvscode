"""
YAML 契约数据类——需求解析层的类型定义。

从 v1.x scripts/pipeline/layer1_requirement.py 提取数据类，
保持与现有 YAML fixture 格式的兼容性。

v2.0 中，这些类型用于阶段 1（需求分析）的输入解析。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class MetricSpec:
    """指标声明"""
    name: str
    aggregation: Optional[str] = None  # daily / monthly / none
    alias: Optional[str] = None


@dataclass
class DimensionSpec:
    """维度声明"""
    name: str
    alias: Optional[str] = None


@dataclass
class FilterSpec:
    """过滤条件"""
    date_range: Optional[tuple[str, str]] = None  # [start, end]
    dimension_filters: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class OrderBySpec:
    """排序规格"""
    column: str
    direction: str = "asc"  # asc | desc


@dataclass
class OutputSpec:
    """输出配置"""
    format: str = "parquet"  # parquet | csv
    include_report: bool = True
    include_task_config: bool = False
    custom_path: Optional[str] = None


@dataclass
class Requirement:
    """
    结构化需求对象——阶段 1（需求分析）的核心输入。

    从 YAML 需求文件解析而来，支持 v1.x 的 fixtures/requirements/*.yml 格式。
    """
    name: str
    description: str = ""
    version: str = "1.0"
    metrics: list[MetricSpec] = field(default_factory=list)
    dimensions: list[DimensionSpec] = field(default_factory=list)
    filters: FilterSpec = field(default_factory=FilterSpec)
    group_by: list[str] = field(default_factory=list)
    order_by: list[OrderBySpec] = field(default_factory=list)
    output: OutputSpec = field(default_factory=OutputSpec)
    notes: str = ""
    # 解析状态
    is_valid: bool = True
    validation_errors: list[str] = field(default_factory=list)


def parse_requirement(yaml_path: str | Path) -> Requirement:
    """
    解析 YAML 需求说明书为 Requirement 对象。

    先尝试规则解析；规则解析失败时返回带 validation_errors 的对象，
    由调用方决定是否调用 LLM 辅助修复。

    Args:
        yaml_path: YAML 需求文件路径

    Returns:
        Requirement 对象——is_valid 为 True 表示解析成功
    """
    yaml_path = Path(yaml_path)
    errors: list[str] = []

    if not yaml_path.exists():
        return Requirement(
            name=yaml_path.stem,
            is_valid=False,
            validation_errors=[f"文件不存在: {yaml_path}"],
        )

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return Requirement(
            name=yaml_path.stem,
            is_valid=False,
            validation_errors=[f"YAML 解析失败: {e}"],
        )

    if raw is None:
        return Requirement(
            name=yaml_path.stem,
            is_valid=False,
            validation_errors=["YAML 文件为空"],
        )

    # 解析 name（必填）
    name = raw.get("name", "")
    if not name:
        errors.append("缺少必填字段: name")

    # 解析 metrics（必填）
    metrics_raw = raw.get("metrics", [])
    metrics: list[MetricSpec] = []
    if not metrics_raw:
        errors.append("缺少必填字段: metrics（至少需要一个已注册指标）")
    else:
        for m in metrics_raw:
            if isinstance(m, str):
                metrics.append(MetricSpec(name=m))
            elif isinstance(m, dict):
                if not m.get("name"):
                    errors.append("metrics[].name 为必填")
                metrics.append(MetricSpec(
                    name=m.get("name", ""),
                    aggregation=m.get("aggregation"),
                    alias=m.get("alias"),
                ))
            else:
                errors.append(f"metrics 条目格式无效: {m}")

    # 解析 dimensions（可选）
    dimensions: list[DimensionSpec] = []
    for d in raw.get("dimensions", []) or []:
        if isinstance(d, str):
            dimensions.append(DimensionSpec(name=d))
        elif isinstance(d, dict):
            dimensions.append(DimensionSpec(
                name=d.get("name", ""),
                alias=d.get("alias"),
            ))

    # 解析 filters（date_range 必填）
    filters_raw = raw.get("filters", {}) or {}
    date_range = filters_raw.get("date_range", [])
    if not date_range or len(date_range) != 2:
        errors.append("缺少必填字段: filters.date_range（格式: [开始日期, 结束日期]）")

    filter_spec = FilterSpec(
        date_range=tuple(date_range) if len(date_range) == 2 else None,
        dimension_filters=filters_raw.get("dimension_filters", {}) or {},
    )

    # 解析其他字段
    group_by = raw.get("group_by", []) or []
    order_by: list[OrderBySpec] = []
    for o in raw.get("order_by", []) or []:
        if isinstance(o, dict):
            order_by.append(OrderBySpec(
                column=o.get("column", ""),
                direction=o.get("direction", "asc"),
            ))
        elif isinstance(o, str):
            order_by.append(OrderBySpec(column=o))

    output_raw = raw.get("output", {}) or {}
    output_spec = OutputSpec(
        format=output_raw.get("format", "parquet"),
        include_report=output_raw.get("include_report", True),
        include_task_config=output_raw.get("include_task_config", False),
        custom_path=output_raw.get("path"),
    )

    return Requirement(
        name=name,
        description=raw.get("description", ""),
        version=raw.get("version", "1.0"),
        metrics=metrics,
        dimensions=dimensions,
        filters=filter_spec,
        group_by=group_by,
        order_by=order_by,
        output=output_spec,
        notes=raw.get("notes", ""),
        is_valid=len(errors) == 0,
        validation_errors=errors,
    )
