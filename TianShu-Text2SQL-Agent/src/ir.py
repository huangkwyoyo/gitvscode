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
    NEED_CLARIFICATION = "need_clarification"  # 需要反问


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

        # JOIN 必须在白名单中
        # C-1 修复：用 is not None 代替 falsy 检查
        if self.joins and join_whitelist is not None and self.primary_table:
            for join in self.joins:
                join_pair = (self.primary_table, join.table)
                reverse_pair = (join.table, self.primary_table)
                if join_pair not in join_whitelist and reverse_pair not in join_whitelist:
                    errors.append(
                        f"JOIN {self.primary_table} ↔ {join.table} "
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
# 顶层结构：一次完整的问答
# ═══════════════════════════════════════════════════════════


@dataclass
class AgentResponse:
    """
    Agent 一次完整问答的顶层结构。

    包含三层 IR 的完整链路 + 中文解释。
    """
    question: str                                    # 原始用户问题
    intent: Optional[QuestionIntent] = None           # Layer 1
    plan: Optional[SQLPlan] = None                    # Layer 2
    result: Optional[SQLResult] = None                # Layer 3
    chinese_answer: Optional[str] = None              # 中文解释
    clarification_needed: bool = False                # 是否需要反问
    clarification_message: Optional[str] = None       # 反问内容
    refusal: bool = False                             # 是否拒绝回答
    refusal_reason: Optional[str] = None              # 拒绝原因
    trace: list[str] = field(default_factory=list)    # 执行追踪日志

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
        }
