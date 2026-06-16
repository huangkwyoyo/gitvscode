"""
统一 IR 类型系统。

聚合 Text2SQL Agent 和 v1.x 管道的 IR 类型定义，
新增 v2.0 专有类型（交叉验证、双层边界、审查材料包）。
"""

from .types import (
    # ── 业务枚举 ──
    Domain, IntentType, TimeRangeType, Strategy, MergeStatus,
    # ── v2.0 枚举 ──
    ExecutionMode, ValidationStatus, CrossValidateStatus,
    # ── Layer 1: 需求与意图 ──
    TimeRange, Filter, QuestionIntent, SubIntent,
    # ── Layer 2: SQL 执行计划 ──
    JoinPlan, Aggregation, SQLPlan,
    # ── Layer 3: 执行结果 ──
    SQLResult, ExecutionTrace,
    # ── 结果摘要与合并 ──
    ResultSummary, MergedResult,
    # ── 多计划结构 ──
    UnifiedResponse, AgentResponse,
    # ── v2.0 代码生成 ──
    CodeGenerationRequest, CodeGenerationResult, CodeDraft,
    # ── v2.0 验证与交叉验证 ──
    CheckResult, ValidationReport, CrossValidationResult,
    # ── v2.0 审查材料 ──
    ReviewMaterial, ReviewPackage, ReviewPackageManifest, DecisionRecord,
)

from .contracts import (
    MetricSpec, DimensionSpec, FilterSpec,
    OrderBySpec, OutputSpec, Requirement,
    parse_requirement,
)

from .v1_bridge import to_v1_plan, from_v1_plan

__all__ = [
    # 业务枚举
    "Domain", "IntentType", "TimeRangeType", "Strategy", "MergeStatus",
    # v2.0 枚举
    "ExecutionMode", "ValidationStatus", "CrossValidateStatus",
    # Layer 1
    "TimeRange", "Filter", "QuestionIntent", "SubIntent",
    # Layer 2
    "JoinPlan", "Aggregation", "SQLPlan",
    # Layer 3
    "SQLResult", "ExecutionTrace",
    # 结果摘要
    "ResultSummary", "MergedResult",
    # 多计划
    "UnifiedResponse", "AgentResponse",
    # 代码生成
    "CodeGenerationRequest", "CodeGenerationResult", "CodeDraft",
    # 验证
    "CheckResult", "ValidationReport", "CrossValidationResult",
    # 审查材料
    "ReviewMaterial", "ReviewPackage", "ReviewPackageManifest", "DecisionRecord",
    # 契约
    "MetricSpec", "DimensionSpec", "FilterSpec",
    "OrderBySpec", "OutputSpec", "Requirement",
    "parse_requirement",
    # 桥接
    "to_v1_plan", "from_v1_plan",
]
