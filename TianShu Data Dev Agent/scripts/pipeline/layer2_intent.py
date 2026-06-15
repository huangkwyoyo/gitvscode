"""
Layer 2：意图理解层

职责：
  1. 接收 Layer 1 的 Requirement 对象
  2. 验证所有指标名是否在注册表中
  3. 对未匹配的指标进行模糊匹配（调用 LLM 消歧）
  4. 验证维度和过滤条件的合法性
  5. 输出 Intent 对象（WHAT 而非 HOW）

LLM 角色：
  - 指标名模糊匹配（用户写"行程数"而非"trip_count"）
  - 指标歧义消解（用户写"金额"→ 从 3 个金额指标中确定意图）
  - 只能输出 Intent JSON，不能推荐表名/字段名/JOIN

输入：Requirement 对象
输出：Intent 对象
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Any

from .column_binding import (
    get_binding_by_metric_name,
    validate_metric_exists,
    METRIC_BINDINGS,
)
from .layer1_requirement import Requirement, MetricSpec, DimensionSpec


@dataclass
class ResolvedMetric:
    """已解析的指标——确认存在于注册表中"""
    registered_name: str    # 注册表中的精确名称，如 "trip_count"
    zh_name: str            # 中文名，如 "行程量"
    domain: str             # 所属业务域
    user_name: str          # 用户在 YAML 中写的原始名称（可能不精确）
    fuzzy_matched: bool = False  # 是否通过模糊匹配找到的


@dataclass
class ResolvedDimension:
    """已解析的维度"""
    name: str               # 用户声明的维度名
    alias: Optional[str] = None


@dataclass
class Intent:
    """
    意图对象 —— Layer 2 的输出，LLM 的最终产出

    关键约束：
    - 不包含任何表名
    - 不包含任何字段名（column）
    - 不包含任何 JOIN 信息
    - 只表达"用户想要什么"（WHAT），不表达"如何获取"（HOW）
    """
    description: str
    metrics_requested: list[ResolvedMetric] = field(default_factory=list)
    dimensions: list[ResolvedDimension] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    group_by: list[str] = field(default_factory=list)
    domain: str = ""  # traffic | violation | safety | supply | cross_domain

    # 置信度
    confidence: dict[str, str] = field(default_factory=lambda: {
        "metric_match": "high",     # high | medium | low | ambiguous
        "dimension_match": "high",
    })

    # 诊断
    unresolved_metrics: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    is_valid: bool = True
    block_reason: str = ""


def _resolve_metric(metric_spec: MetricSpec) -> tuple[Optional[ResolvedMetric], Optional[str]]:
    """
    将用户声明的指标名解析为注册表中的精确名称

    返回：(ResolvedMetric, None) 成功 / (None, 错误消息) 失败
    """
    name = metric_spec.name.strip()

    # ── 步骤 1：精确匹配 ──
    valid, err = validate_metric_exists(name)
    if valid:
        binding = get_binding_by_metric_name(name)
        return ResolvedMetric(
            registered_name=name,
            zh_name=binding.zh_name,
            domain=binding.domain,
            user_name=name,
            fuzzy_matched=False,
        ), None

    # ── 步骤 2：模糊匹配（容忍用户写中文名或变体）──
    # 这个映射表是硬编码的——不应该由 LLM 做（保证确定性）
    FUZZY_MAP: dict[str, str] = {
        # 中文名 → 英文 registered_name
        "行程量": "trip_count",
        "行程数": "trip_count",
        "总车费": "total_fare_amount",
        "车费": "total_fare_amount",
        "总小费": "total_tip_amount",
        "小费": "total_tip_amount",
        "总行驶距离": "total_distance_miles",
        "行驶距离": "total_distance_miles",
        "里程": "total_distance_miles",
        "停车罚单数量": "parking_violation_count",
        "罚单量": "parking_violation_count",
        "违章量": "parking_violation_count",
        "标准罚款总额": "standard_fine_total",
        "罚款总额": "standard_fine_total",
        "事故数量": "crash_count",
        "事故量": "crash_count",
        "死亡人数": "persons_killed",
        "受伤人数": "persons_injured",
        "TIF支付": "tif_payment_amount",
        "TIF金额": "tif_payment_amount",
    }

    fuzzy_name = FUZZY_MAP.get(name)
    if fuzzy_name:
        valid2, _ = validate_metric_exists(fuzzy_name)
        if valid2:
            binding = get_binding_by_metric_name(fuzzy_name)
            return ResolvedMetric(
                registered_name=fuzzy_name,
                zh_name=binding.zh_name,
                domain=binding.domain,
                user_name=name,
                fuzzy_matched=True,
            ), None

    # ── 步骤 3：完全匹配失败 → 标记为未解析 ──
    # 调用方可以决定是否使用 LLM 做更智能的匹配
    registered_names = [e.metric_name for e in METRIC_BINDINGS]
    return None, f"指标 '{name}' 未在注册表中找到。已注册指标: {registered_names}"


def _resolve_domain(metrics: list[ResolvedMetric]) -> str:
    """根据已解析指标确定业务域"""
    domains = set(m.domain for m in metrics)
    if len(domains) == 1:
        return list(domains)[0]
    return "cross_domain"


def build_intent(requirement: Requirement) -> Intent:
    """
    从 Requirement 构造 Intent 对象

    核心流程：
    1. 逐个解析用户声明的指标名 → 匹配注册表
    2. 解析维度和过滤条件
    3. 确定业务域
    4. 构建 Intent 对象

    注意：此函数不调用 LLM。LLM 调用由上层（run_pipeline.py）在
    Intent 构造后发现有 unresolved_metrics 或低置信度时触发。
    """
    warnings: list[str] = []
    unresolved: list[str] = []

    # ── 解析指标 ──
    resolved_metrics: list[ResolvedMetric] = []
    for metric_spec in requirement.metrics:
        resolved, error = _resolve_metric(metric_spec)
        if resolved:
            resolved_metrics.append(resolved)
            if resolved.fuzzy_matched:
                warnings.append(f"指标 '{metric_spec.name}' 通过模糊匹配映射到 '{resolved.registered_name}'（{resolved.zh_name}）")
        else:
            unresolved.append(metric_spec.name)
            if error:
                warnings.append(error)

    # ── 解析维度 ──
    dimensions: list[ResolvedDimension] = []
    for dim_spec in requirement.dimensions:
        dimensions.append(ResolvedDimension(
            name=dim_spec.name,
            alias=dim_spec.alias,
        ))

    # ── 提取过滤条件 ──
    filters: dict[str, Any] = {}
    if requirement.filters.date_range:
        filters["date_range"] = requirement.filters.date_range
    if requirement.filters.dimension_filters:
        filters["dimension_filters"] = requirement.filters.dimension_filters

    # ── 确定业务域 ──
    domain = _resolve_domain(resolved_metrics) if resolved_metrics else ""

    # ── 置信度评估 ──
    metric_confidence = "high"
    fuzzy_count = sum(1 for m in resolved_metrics if m.fuzzy_matched)
    if fuzzy_count > 0:
        metric_confidence = "medium"
    if unresolved:
        metric_confidence = "low"
    if not resolved_metrics:
        metric_confidence = "ambiguous"

    dim_confidence = "high" if dimensions else "medium"

    # ── 组装 Intent ──
    is_valid = len(resolved_metrics) > 0

    intent = Intent(
        description=requirement.description or requirement.name,
        metrics_requested=resolved_metrics,
        dimensions=dimensions,
        filters=filters,
        group_by=requirement.group_by,
        domain=domain,
        confidence={
            "metric_match": metric_confidence,
            "dimension_match": dim_confidence,
        },
        unresolved_metrics=unresolved,
        warnings=warnings,
        is_valid=is_valid,
        block_reason="" if is_valid else f"无法解析任何指标。未解析: {unresolved}",
    )

    return intent
