"""
Layer 1：需求解析层

职责：
  1. 读取 YAML 需求说明书
  2. 校验必填字段（name, metrics, filters.date_range）
  3. 输出结构化的 Requirement 对象

LLM 角色：
  - 如果 YAML 完整且校验通过 → 无需 LLM
  - 如果 YAML 解析失败或字段不完整 → 可调用 LLM 辅助解析
  - LLM 只能输出 Requirement JSON，不能推荐表名或 SQL

输入：YAML 文件路径
输出：Requirement 对象
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
    dimension_filters: dict[str, list[str]] = field(default_factory=dict)  # {dim: [values]}


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
    """结构化需求对象 —— Layer 1 的输出"""
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
    解析 YAML 需求说明书为 Requirement 对象

    先尝试规则解析；规则解析失败时返回带 validation_errors 的对象，
    由调用方决定是否调用 LLM 辅助修复。
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

    # ── 解析 name（必填）──
    name = raw.get("name", "")
    if not name:
        errors.append("缺少必填字段: name")

    # ── 解析 metrics（必填）──
    metrics_raw = raw.get("metrics", [])
    metrics: list[MetricSpec] = []
    if not metrics_raw:
        errors.append("缺少必填字段: metrics（至少需要一个已注册指标）")
    else:
        for m in metrics_raw:
            if isinstance(m, str):
                # 简洁写法："trip_count"
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

    # ── 解析 dimensions（可选）──
    dimensions: list[DimensionSpec] = []
    for d in raw.get("dimensions", []) or []:
        if isinstance(d, str):
            dimensions.append(DimensionSpec(name=d))
        elif isinstance(d, dict):
            dimensions.append(DimensionSpec(
                name=d.get("name", ""),
                alias=d.get("alias"),
            ))

    # ── 解析 filters（date_range 必填）──
    filters_raw = raw.get("filters", {}) or {}
    date_range = filters_raw.get("date_range", [])
    if not date_range or len(date_range) != 2:
        errors.append("缺少必填字段: filters.date_range（格式: [开始日期, 结束日期]）")

    filter_spec = FilterSpec(
        date_range=tuple(date_range) if len(date_range) == 2 else None,
        dimension_filters=filters_raw.get("dimension_filters", {}) or {},
    )

    # ── 解析 group_by（可选）──
    group_by = raw.get("group_by", []) or []

    # ── 解析 order_by（可选）──
    order_by: list[OrderBySpec] = []
    for o in raw.get("order_by", []) or []:
        if isinstance(o, dict):
            order_by.append(OrderBySpec(
                column=o.get("column", ""),
                direction=o.get("direction", "asc"),
            ))
        elif isinstance(o, str):
            order_by.append(OrderBySpec(column=o))

    # ── 解析 output（可选）──
    output_raw = raw.get("output", {}) or {}
    output_spec = OutputSpec(
        format=output_raw.get("format", "parquet"),
        include_report=output_raw.get("include_report", True),
        include_task_config=output_raw.get("include_task_config", False),
        custom_path=output_raw.get("path"),
    )

    # ── 解析其他字段 ──
    description = raw.get("description", "")
    notes = raw.get("notes", "")
    version = raw.get("version", "1.0")

    return Requirement(
        name=name,
        description=description,
        version=version,
        metrics=metrics,
        dimensions=dimensions,
        filters=filter_spec,
        group_by=group_by,
        order_by=order_by,
        output=output_spec,
        notes=notes,
        is_valid=len(errors) == 0,
        validation_errors=errors,
    )
