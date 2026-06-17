"""
三层中间表示（IR）的数据结构定义。

三层架构：
    Layer 1: QuestionIntent  —— 用户要什么（语义层）
    Layer 2: SQLPlan         —— 怎么回答（策略层）
    Layer 3: SQLResult       —— 执行结果（执行层）

每层有独立的 validate() 方法，校验失败时：
    - Layer 1 失败 → 反问用户
    - Layer 2 失败 → 降级或反问
    - Layer 3 失败 → 标注原因但不阻断
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════
# 枚举定义
# ═══════════════════════════════════════════════════════════


class Domain(str, Enum):
    """业务领域枚举"""
    TRAFFIC = "traffic"        # 出行
    SAFETY = "safety"           # 安全/事故
    VIOLATION = "violation"     # 违章
    SUPPLY = "supply"           # 供给（TIF、司机申请）
    ASSET = "asset"             # 资产（车辆、司机）
    SPATIAL = "spatial"         # 空间（区域、行政区）


class IntentType(str, Enum):
    """查询意图类型枚举"""
    AGGREGATION = "aggregation"   # 聚合查询（求和、计数）
    RANKING = "ranking"           # 排序查询（TOP N）
    TREND = "trend"               # 趋势查询（按时间序列）
    COMPARISON = "comparison"     # 对比查询（跨维度对比）
    LISTING = "listing"           # 列表查询（维度枚举）


class TimeRangeType(str, Enum):
    """时间范围类型枚举"""
    ABSOLUTE = "absolute"   # 明确时间范围（"2026年Q1"）
    RELATIVE = "relative"   # 相对时间范围（"最近7天"）
    FUZZY = "fuzzy"         # 模糊时间（"最近"、"上个月"）→ 必须反问


class Strategy(str, Enum):
    """SQL 执行策略枚举"""
    G3_DIRECT = "g3_direct"           # G3 汇总表直查
    G3_CROSS = "g3_cross"             # G3 跨表 JOIN
    G2_FACT = "g2_fact"               # G2 单事实表
    G2_FACT_JOIN = "g2_fact_join"     # G2 事实表 + JOIN 维表
    G0_DIM_DIRECT = "g0_dim_direct"   # 纯维度查询
    NEED_CLARIFICATION = "need_clarification"      # 需要反问
    UNSUPPORTED_MULTI_PLAN = "unsupported_multi_plan"  # 跨表多指标（Phase 2A：识别但暂不执行）


# ═══════════════════════════════════════════════════════════
# Layer 1: QuestionIntent —— 用户要什么
# ═══════════════════════════════════════════════════════════


@dataclass
class TimeRange:
    """时间范围描述"""
    type: TimeRangeType
    start: Optional[str] = None   # YYYY-MM-DD
    end: Optional[str] = None     # YYYY-MM-DD
    raw_expression: Optional[str] = None  # 用户的原始时间表达


@dataclass
class Filter:
    """过滤条件"""
    field: str          # 字段名
    op: str             # 操作符 =, >, <, IN, BETWEEN
    value: str          # 过滤值
    value_type: str = "string"  # string, number, date


@dataclass
class QuestionIntent:
    """
    Layer 1：用户查询意图的结构化表示。

    从自然语言中提取：主题域、指标、时间范围、分组维度、过滤条件。
    校验关注：指标是否注册？时间是否在有效范围？是否有歧义？
    """
    domain: Optional[Domain] = None
    intent_type: Optional[IntentType] = None
    metrics: list[str] = field(default_factory=list)
    time_range: TimeRange = field(default_factory=lambda: TimeRange(type=TimeRangeType.FUZZY))
    dimensions: list[str] = field(default_factory=list)
    filters: list[Filter] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_reason: Optional[str] = None
    confidence: float = 0.0
    raw_question: Optional[str] = None

    def validate(self) -> list[str]:
        """
        校验 QuestionIntent 的结构完整性（仅结构性校验）。

        B-5 职责拆分：本方法只检查 IR 结构是否完整可解析。
        歧义检测（置信度、模糊时间、反问标记）统一由
        src/ambiguity.py 的 detect_ambiguity() 处理。

        Returns:
            错误列表。空列表表示结构完整。
            有错误时表明 LLM 输出无法构成有效的 QuestionIntent。
        """
        errors: list[str] = []

        # 结构性校验：领域未知且无指标 → LLM 完全未能解析意图
        if self.domain is None and not self.metrics:
            errors.append("无法识别查询领域和指标，请重新表述问题")

        return errors

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（供 Prompt 上下文使用）"""
        return {
            "domain": self.domain.value if self.domain else None,
            "intent_type": self.intent_type.value if self.intent_type else None,
            "metrics": self.metrics,
            "time_range": {
                "type": self.time_range.type.value,
                "start": self.time_range.start,
                "end": self.time_range.end,
            },
            "dimensions": self.dimensions,
            "filters": [
                {"field": f.field, "op": f.op, "value": f.value}
                for f in self.filters
            ],
            "needs_clarification": self.needs_clarification,
            "clarification_reason": self.clarification_reason,
            "confidence": self.confidence,
        }


# ═══════════════════════════════════════════════════════════
# Layer 1.5: SubIntent —— 跨表多指标的子意图（Phase 2B）
# ═══════════════════════════════════════════════════════════


@dataclass
class SubIntent:
    """
    子意图：将跨表多指标按 planning_table 分组后的独立查询单元。

    每个 SubIntent 只包含同一 planning_table 下的指标，
    复用父级 QuestionIntent 的 time_range、dimensions、filters 等上下文。
    """
    metrics: list[str] = field(default_factory=list)      # 该子意图涉及的指标英文名
    domain: Optional[Domain] = None                         # 该组指标的业务域
    planning_table: str = ""                                # 合并后的最终表名
    time_range: Optional[TimeRange] = None                  # 继承父意图的时间范围
    dimensions: list[str] = field(default_factory=list)     # 继承父意图的分组维度

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "metrics": self.metrics,
            "domain": self.domain.value if self.domain else None,
            "planning_table": self.planning_table,
            "time_range": {
                "type": self.time_range.type.value,
                "start": self.time_range.start,
                "end": self.time_range.end,
            } if self.time_range else None,
            "dimensions": self.dimensions,
        }


# ═══════════════════════════════════════════════════════════
# Layer 2: SQLPlan —— 怎么回答
# ═══════════════════════════════════════════════════════════


@dataclass
class JoinPlan:
    """JOIN 计划"""
    table: str          # 完全限定表名
    on: str             # JOIN 条件
    type: str = "INNER" # INNER / LEFT


@dataclass
class Aggregation:
    """聚合表达式"""
    expr: str           # 聚合表达式（如 "COUNT(*)"）
    alias: str          # 别名


@dataclass
class SQLPlan:
    """
    Layer 2：SQL 执行计划。

    从 QuestionIntent 生成：选表策略、表引用、JOIN、过滤、分组、聚合。
    校验关注：表/列是否存在？JOIN 是否在白名单？层级是否合规？
    """
    strategy: Strategy = Strategy.NEED_CLARIFICATION
    primary_table: Optional[str] = None       # 完全限定表名
    joins: list[JoinPlan] = field(default_factory=list)
    where_clauses: list[str] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    order_by: list[str] = field(default_factory=list)
    aggregations: list[Aggregation] = field(default_factory=list)
    limit: Optional[int] = None
    downgrade_reason: Optional[str] = None    # 为什么降级（非 G3_DIRECT 时必须填写）
    confidence: float = 0.0

    def validate(self, available_tables: Optional[set[str]] = None,
                 join_whitelist: Optional[set[tuple[str, str]]] = None) -> list[str]:
        """
        校验 SQLPlan 的表选择正确性。

        Args:
            available_tables: 可用表集合（从 information_schema 或 contracts 加载）
            join_whitelist: JOIN 白名单，元素为 (table_a, table_b) 的集合

        Returns:
            错误列表。空列表表示校验通过。
            有错误时，调用方应降级策略或反问用户。
        """
        errors: list[str] = []

        # 需要反问
        if self.strategy == Strategy.NEED_CLARIFICATION:
            errors.append("SQLPlan 策略为 NEED_CLARIFICATION，不应生成 SQL")
            return errors

        # Phase 4：跨表多指标占位符，由 Agent 运行时拆分为 SubIntent，
        # 不在此处校验表/JOIN（primary_table 为 null 是合法的）
        if self.strategy == Strategy.UNSUPPORTED_MULTI_PLAN:
            return errors

        # 降级必须说明原因
        if self.strategy not in (Strategy.G3_DIRECT, Strategy.G0_DIM_DIRECT):
            if not self.downgrade_reason:
                errors.append(
                    f"策略 {self.strategy.value} 不是最优路径，"
                    f"但 downgrade_reason 为空，必须说明降级原因"
                )

        # 主表必须指定
        if not self.primary_table:
            errors.append("primary_table 不能为空")
        # C-1 修复：用 is not None 代替 falsy 检查，区分"未提供白名单"与"白名单为空"
        elif available_tables is not None and self.primary_table not in available_tables:
            errors.append(
                f"表 {self.primary_table} 不在可用表列表中，"
                f"请检查表名或 contracts/semantic_contract.yml"
            )

        # ── JOIN 白名单校验（主防线）──
        # B-7：IR 级 JOIN 检查是主防线，在规划阶段即拦截不合规 JOIN。
        # SQL 级 validate_sql_safety() 保留兜底检查，防止 sql_plan_to_sql()
        # 生成阶段引入计划外的 JOIN（防御深度）。
        # C-1 修复：用 is not None 代替 falsy 检查
        if self.joins and join_whitelist is not None and self.primary_table:
            for join in self.joins:
                join_pair = (self.primary_table, join.table)
                reverse_pair = (join.table, self.primary_table)
                if join_pair not in join_whitelist and reverse_pair not in join_whitelist:
                    errors.append(
                        f"[IR 主防线] JOIN {self.primary_table} ↔ {join.table} "
                        f"不在核准白名单中"
                    )

        return errors

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（供 Prompt 上下文和 JSON 输出使用）"""
        return {
            "strategy": self.strategy.value,
            "primary_table": self.primary_table,
            "joins": [
                {"table": j.table, "on": j.on, "type": j.type}
                for j in self.joins
            ],
            "where_clauses": self.where_clauses,
            "group_by": self.group_by,
            "order_by": self.order_by,
            "aggregations": [
                {"expr": a.expr, "alias": a.alias}
                for a in self.aggregations
            ],
            "limit": self.limit,
            "downgrade_reason": self.downgrade_reason,
            "confidence": self.confidence,
        }


# ═══════════════════════════════════════════════════════════
# Layer 3: SQLResult —— 执行结果
# ═══════════════════════════════════════════════════════════


@dataclass
class SQLResult:
    """
    Layer 3：SQL 执行结果。

    包含执行的 SQL、返回的数据、元信息。
    校验关注：SQL 是否只读？结果签名是否稳定？
    """
    sql: str                              # 执行的 SQL
    columns: list[str] = field(default_factory=list)     # 列名列表
    column_types: list[str] = field(default_factory=list) # 列类型列表
    rows: list[tuple] = field(default_factory=list)       # 数据行
    row_count: int = 0
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    source_table: Optional[str] = None   # 主数据来源表

    @property
    def result_signature(self) -> str:
        """
        计算结果签名（MD5）。

        签名 = MD5(行数 + 列名列表 + 列类型列表)
        用于结果稳定性检测——签名变化意味着数据结构发生了变更。
        """
        content = f"{self.row_count}|{','.join(self.columns)}|{','.join(self.column_types)}"
        return hashlib.md5(content.encode()).hexdigest()

    def validate(self) -> list[str]:
        """
        校验 SQLResult 的执行正确性。

        Returns:
            警告列表（不阻断，仅提醒）。空列表表示无异常。
        """
        warnings: list[str] = []

        if self.error:
            warnings.append(f"SQL 执行错误: {self.error}")

        if self.row_count == 0 and not self.error:
            warnings.append("查询结果为空，可能时间范围内无数据或过滤条件过严")

        return warnings

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "sql": self.sql,
            "columns": self.columns,
            "column_types": self.column_types,
            "row_count": self.row_count,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
            "source_table": self.source_table,
            "signature": self.result_signature,
        }


# ═══════════════════════════════════════════════════════════
# ExecutionTrace：单次 SQL 执行的轻量追踪（Phase A）
# ═══════════════════════════════════════════════════════════


@dataclass
class ExecutionTrace:
    """
    单次 SQL 计划执行的轻量追踪记录。

    每个 SQLPlan 执行后生成一条 trace，记录生成、校验、执行全链路的关键状态。
    不做过度的字段设计——仅记录对调试和回归有用的信息。
    """
    plan_index: int = 0                     # 计划序号（从 1 开始）
    strategy: str = ""                      # 执行策略（Strategy.value）
    primary_table: str = ""                 # 主数据来源表
    generated_sql: str = ""                 # 生成的 SQL 文本
    safety_check_passed: bool = False       # 安全校验是否通过
    row_count: int = 0                      # 返回行数
    error_message: str = ""                 # 错误信息（空字符串表示无错误）
    execution_status: str = "pending"       # 执行状态：pending / success / failed
    execution_time_ms: float = 0.0          # 执行耗时（毫秒）

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "plan_index": self.plan_index,
            "strategy": self.strategy,
            "primary_table": self.primary_table,
            "generated_sql": self.generated_sql,
            "safety_check_passed": self.safety_check_passed,
            "row_count": self.row_count,
            "error_message": self.error_message,
            "execution_status": self.execution_status,
            "execution_time_ms": self.execution_time_ms,
        }


# ═══════════════════════════════════════════════════════════
# Phase B1：结果摘要与合并结构
# ═══════════════════════════════════════════════════════════


class MergeStatus(str, Enum):
    """多结果合并状态枚举"""
    NOT_ATTEMPTED = "not_attempted"   # 未尝试合并（默认）
    MERGED = "merged"                  # 已合并成功
    SKIPPED = "skipped"                # 已跳过（无 date 列 / grain 不一致等）
    FAILED = "failed"                  # 合并失败（数据冲突等）


@dataclass
class ResultSummary:
    """
    SQLResult 的结构化摘要 —— 为 date merge / LLM 融合 / 图表生成提供稳定输入。

    只做结构化提取，不做业务解释、不推断因果、不补造数据。
    所有字段值都来自 SQLResult 的已有数据。

    对应关系：
        - 一个 UnifiedResponse → 一个 ResultSummary
        - 一个 MergedResult.source_summaries → 多个 ResultSummary
    """
    source_plan_index: int = 0                  # 来源计划序号（从 1 开始）
    metrics: list[str] = field(default_factory=list)        # 指标英文名列表
    dimensions: list[str] = field(default_factory=list)     # 分组维度列表
    primary_table: str = ""                     # 主数据来源表
    strategy: str = ""                          # 执行策略（Strategy.value）
    columns: list[str] = field(default_factory=list)        # 列名列表
    column_types: list[str] = field(default_factory=list)   # 列类型列表
    row_count: int = 0                          # 数据行数
    sample_rows: list[list] = field(default_factory=list)   # 前 5 行样本数据
    has_date_column: bool = False               # 结果是否包含日期列
    grain: str = "unknown"                      # 时间粒度：daily / unknown / other
    date_min: str = ""                          # 最早日期（ISO 格式，如 "2026-01-01"）
    date_max: str = ""                          # 最晚日期（ISO 格式，如 "2026-01-31"）
    warnings: list[str] = field(default_factory=list)      # 摘要过程中产生的警告

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "source_plan_index": self.source_plan_index,
            "metrics": self.metrics,
            "dimensions": self.dimensions,
            "primary_table": self.primary_table,
            "strategy": self.strategy,
            "columns": self.columns,
            "column_types": self.column_types,
            "row_count": self.row_count,
            "sample_rows": self.sample_rows,
            "has_date_column": self.has_date_column,
            "grain": self.grain,
            "date_min": self.date_min,
            "date_max": self.date_max,
            "warnings": self.warnings,
        }


@dataclass
class MergedResult:
    """
    多结果合并的容器结构。

    Phase B1 先定义结构，不做真正合并。
    默认 merge_status = NOT_ATTEMPTED 或 SKIPPED。

    后续 Phase 3B（LLM 融合）/ 3C（date merge）/ 5（图表生成）将使用此结构。
    """
    merge_status: MergeStatus = MergeStatus.NOT_ATTEMPTED  # 合并状态
    merge_key: str = ""                         # 合并键（如 "date"）
    columns: list[str] = field(default_factory=list)        # 合并后的列名列表
    rows: list[list] = field(default_factory=list)          # 合并后的数据行
    row_count: int = 0                          # 合并后行数
    source_plan_indexes: list[int] = field(default_factory=list)   # 来源计划序号列表
    source_summaries: list[ResultSummary] = field(default_factory=list)  # 来源摘要列表
    merge_warnings: list[str] = field(default_factory=list)   # 合并过程中的警告
    reason: str = ""                            # 合并状态的原因说明

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "merge_status": self.merge_status.value,
            "merge_key": self.merge_key,
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "source_plan_indexes": self.source_plan_indexes,
            "source_summaries": [s.to_dict() for s in self.source_summaries],
            "merge_warnings": self.merge_warnings,
            "reason": self.reason,
        }


# ═══════════════════════════════════════════════════════════
# 多计划结构：跨表多指标的统一响应（Phase 2B）
# ═══════════════════════════════════════════════════════════


@dataclass
class UnifiedResponse:
    """
    多计划中每个子计划的统一响应。

    包含：子意图（SubIntent）→ 查询计划（SQLPlan）→ 执行结果（SQLResult）。
    多个 UnifiedResponse 组成 AgentResponse.plans。
    """
    sub_intent: Optional[SubIntent] = None   # 该子计划的意图
    plan: Optional[SQLPlan] = None           # 该子计划的 SQL 执行计划
    result: Optional[SQLResult] = None       # 该子计划的执行结果
    execution_trace: Optional[ExecutionTrace] = None  # Phase A：执行追踪记录

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "sub_intent": self.sub_intent.to_dict() if self.sub_intent else None,
            "plan": self.plan.to_dict() if self.plan else None,
            "result": self.result.to_dict() if self.result else None,
            "execution_trace": self.execution_trace.to_dict() if self.execution_trace else None,
        }


# ═══════════════════════════════════════════════════════════
# 顶层结构：一次完整的问答
# ═══════════════════════════════════════════════════════════


@dataclass
class AgentResponse:
    """
    Agent 一次完整问答的顶层结构。

    包含三层 IR 的完整链路 + 中文解释。

    单计划场景（向后兼容）：
        - plan / result 填充单计划内容
        - is_multi_plan = False

    多计划场景（Phase 2B+）：
        - plans 包含多个 UnifiedResponse
        - is_multi_plan = True
        - plan / result 仍填充第一个计划（兼容旧调用方）
    """
    question: str                                    # 原始用户问题
    intent: Optional[QuestionIntent] = None           # Layer 1
    plan: Optional[SQLPlan] = None                    # Layer 2（单计划，向后兼容）
    result: Optional[SQLResult] = None                # Layer 3（单结果，向后兼容）
    chinese_answer: Optional[str] = None              # 中文解释
    clarification_needed: bool = False                # 是否需要反问
    clarification_message: Optional[str] = None       # 反问内容
    refusal: bool = False                             # 是否拒绝回答
    refusal_reason: Optional[str] = None              # 拒绝原因
    trace: list[str] = field(default_factory=list)    # 执行追踪日志
    # ── Phase 2B：多计划支持 ──
    is_multi_plan: bool = False                       # 是否为多计划响应
    plans: list[UnifiedResponse] = field(default_factory=list)  # 子计划列表

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "question": self.question,
            "intent": self.intent.to_dict() if self.intent else None,
            "plan": self.plan.to_dict() if self.plan else None,
            "result": self.result.to_dict() if self.result else None,
            "chinese_answer": self.chinese_answer,
            "clarification_needed": self.clarification_needed,
            "clarification_message": self.clarification_message,
            "refusal": self.refusal,
            "refusal_reason": self.refusal_reason,
            "trace": self.trace,
            "is_multi_plan": self.is_multi_plan,
            "plans": [p.to_dict() for p in self.plans],
        }
