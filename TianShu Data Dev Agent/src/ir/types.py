"""
统一 IR 类型定义——v2.0 的类型中枢。

合并来源：
  - TianShu-Text2SQL-Agent/src/ir.py：QuestionIntent / SQLPlan / SQLResult 等
  - scripts/pipeline/layer3_ir.py：v1.x 枚举（Layer 等）
  - v2.0 新增：ExecutionMode / ValidationStatus / CrossValidateStatus /
    CodeGenerationRequest / CodeGenerationResult / CheckResult /
    ValidationReport / CrossValidationResult / ReviewMaterial / ReviewPackage

三层架构（继承 Text2SQL Agent 设计）：
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
# §1 业务枚举（从 Text2SQL Agent 复用）
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
    UNSUPPORTED_MULTI_PLAN = "unsupported_multi_plan"  # 跨表多指标


class MergeStatus(str, Enum):
    """多结果合并状态枚举"""
    NOT_ATTEMPTED = "not_attempted"   # 未尝试合并（默认）
    MERGED = "merged"                  # 已合并成功
    SKIPPED = "skipped"                # 已跳过
    FAILED = "failed"                  # 合并失败


# ═══════════════════════════════════════════════════════════
# §2 v2.0 新增枚举
# ═══════════════════════════════════════════════════════════


class ExecutionMode(str, Enum):
    """代码执行模式——决定哪些代码被执行和交叉验证"""
    SQL_ONLY = "sql_only"              # 仅 SQL 执行（Spark DSL 未启用）
    DUAL = "dual"                      # SQL + Spark DSL 双份执行（完整交叉验证）


class ValidationStatus(str, Enum):
    """单条验证检查的状态"""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    WARN = "warn"


class CrossValidateStatus(str, Enum):
    """交叉验证状态"""
    CONSISTENT = "consistent"          # SQL 和 PySpark 结果一致
    INCONSISTENT = "inconsistent"      # 结果不一致——至少一份代码有逻辑错误
    SKIPPED = "skipped"               # 跳过（如 Spark 不可用）
    NOT_ATTEMPTED = "not_attempted"   # 未尝试


class DecisionStatus(str, Enum):
    """人审决策状态——M4b 状态机完整实现。

    Agent 只能写入 PENDING_REVIEW。
    APPROVED / REQUEST_CHANGES / REJECTED 只能由人通过 CLI 设置。
    SUPERSEDED 由 M3 重新验证且旧状态为 APPROVED 时自动触发。

    语义区分（M5 部署绑定）：
      - APPROVED 仅表示 QUERY_LOGIC_APPROVED（只读查询逻辑已审查）
      - RELEASE_APPROVED 才表示部署产物及配置已审查，可以上线
      - 没有 RELEASE_APPROVED 时禁止声明"可上线"
    """
    PENDING_REVIEW = "PENDING_REVIEW"       # 等待人审（Agent 初始写入）
    APPROVED = "APPROVED"                   # 人审通过（仅人可设置）
    REQUEST_CHANGES = "REQUEST_CHANGES"     # 人审要求修改（仅人可设置）
    REJECTED = "REJECTED"                   # 人审拒绝（仅人可设置）
    SUPERSEDED = "SUPERSEDED"               # 被新验证替代（M4b 自动过渡）

class DeployWriteStrategy(str, Enum):
    """部署写入策略——M5 部署产物确定性封装。

    复用现有 contract 和 operation compiler 已支持的写入策略。
    禁止任意文件路径写入和未声明分区列的分区覆盖。
    """
    CREATE_TABLE_AS_SELECT = "CREATE_TABLE_AS_SELECT"       # CTAS 全量覆盖建表
    INSERT_OVERWRITE_PARTITION = "INSERT_OVERWRITE_PARTITION" # 分区覆盖写入
    INSERT_INTO_PARTITION = "INSERT_INTO_PARTITION"           # 分区追加写入
    CREATE_VIEW = "CREATE_VIEW"                               # 创建视图


class ReleaseStatus(str, Enum):
    """发布审批状态——M5 部署绑定。

    与 DecisionStatus 互补而非替代：
      - DecisionStatus.APPROVED → 查询逻辑已审查
      - ReleaseStatus.RELEASE_APPROVED → 部署产物已审查，可以上线

    Agent 只能设置 DRAFT。
    RELEASE_APPROVED / RELEASE_REJECTED 只能由人通过 CLI 设置。
    """
    DRAFT = "DRAFT"                         # 部署草案，尚未进入审批
    PENDING_RELEASE_REVIEW = "PENDING_RELEASE_REVIEW"  # 等待发布审批
    RELEASE_APPROVED = "RELEASE_APPROVED"   # 发布已批准（仅人可设置）
    RELEASE_REJECTED = "RELEASE_REJECTED"   # 发布被拒绝（仅人可设置）



@dataclass
class ArtifactHashes:
    """artifact SHA-256 哈希集合——M4b 完整性校验基础。

    记录 Review Package 中关键文件的 SHA-256 哈希，
    用于检测批准后代码是否被修改，以及验证是否针对当前代码执行。
    verification_summary 在 M2 阶段为 None，M3 运行后填充。
    """
    sql_main: str = ""
    spark_main: str = ""
    lineage_source_refs: str = ""
    verification_summary: Optional[str] = None
    deploy_sql: str = ""                # M5：deploy/main.sql 哈希
    deploy_spark: str = ""              # M5：deploy/main.py 哈希
    deployment_manifest: str = ""       # M5：deployment_manifest.yml 哈希

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "sql_main": self.sql_main,
            "spark_main": self.spark_main,
            "lineage_source_refs": self.lineage_source_refs,
            "verification_summary": self.verification_summary,
            "deploy_sql": self.deploy_sql,
            "deploy_spark": self.deploy_spark,
            "deployment_manifest": self.deployment_manifest,
        }


@dataclass
class DeploymentManifest:
    """部署清单——M5 部署产物确定性封装的结构化配置。

    描述如何从已验证的只读查询生成部署写入脚本。
    所有字段默认为空或 DRAFT——不包含任何生产连接信息。
    """
    request_id: str = ""
    source_query_ref: str = "sql/main.sql"      # 已验证查询的路径引用
    source_query_hash: str = ""                  # sql/main.sql 的 SHA-256
    target_environment: str = "STAGING"          # 目标环境（占位值，非生产）
    target_table: str = ""                       # 目标写入表（完全限定名）
    write_strategy: str = ""                     # 写入策略（DeployWriteStrategy 值）
    partition_columns: list[str] = field(default_factory=list)  # 分区列列表
    sql_deploy_artifact: str = "deploy/main.sql"  # SQL 部署脚本路径
    spark_deploy_artifact: str = "deploy/main.py"  # Spark 部署脚本路径
    human_review_required: bool = True           # 必须人审
    release_status: str = "DRAFT"                # ReleaseStatus 值——默认 DRAFT
    warnings: list[str] = field(default_factory=list)  # 人审提醒
    human_review_points: list[str] = field(default_factory=list)  # 人审关注点

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "request_id": self.request_id,
            "source_query_ref": self.source_query_ref,
            "source_query_hash": self.source_query_hash,
            "target_environment": self.target_environment,
            "target_table": self.target_table,
            "write_strategy": self.write_strategy,
            "partition_columns": self.partition_columns,
            "sql_deploy_artifact": self.sql_deploy_artifact,
            "spark_deploy_artifact": self.spark_deploy_artifact,
            "human_review_required": self.human_review_required,
            "release_status": self.release_status,
            "warnings": self.warnings,
            "human_review_points": self.human_review_points,
        }



# ═══════════════════════════════════════════════════════════
# §3 Layer 1: QuestionIntent —— 用户要什么
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

        Returns:
            错误列表。空列表表示结构完整。
        """
        errors: list[str] = []
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
# §4 Layer 1.5: SubIntent —— 跨表多指标的子意图
# ═══════════════════════════════════════════════════════════


@dataclass
class SubIntent:
    """
    子意图：将跨表多指标按 planning_table 分组后的独立查询单元。

    每个 SubIntent 只包含同一 planning_table 下的指标，
    复用父级 QuestionIntent 的 time_range、dimensions、filters 等上下文。
    """
    metrics: list[str] = field(default_factory=list)
    domain: Optional[Domain] = None
    planning_table: str = ""
    time_range: Optional[TimeRange] = None
    dimensions: list[str] = field(default_factory=list)

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
# §5 Layer 2: SQLPlan —— 怎么回答
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
            available_tables: 可用表集合
            join_whitelist: JOIN 白名单，元素为 (table_a, table_b) 的集合

        Returns:
            错误列表。空列表表示校验通过。
        """
        errors: list[str] = []

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
        elif available_tables is not None:
            # 规范化比较：lower().strip() 避免大小写/空白导致误判
            pt_normalized = self.primary_table.lower().strip()
            available_normalized = {t.lower().strip() for t in available_tables}
            if pt_normalized not in available_normalized:
                errors.append(
                    f"表 {self.primary_table} 不在可用表列表中，"
                    f"请检查表名或契约定义"
                )

        # JOIN 白名单校验（主防线——IR 级）
        if self.joins and join_whitelist is not None and self.primary_table:
            # 规范化 JOIN 白名单比较（与 checks.py 保持一致）
            pt_normalized = self.primary_table.lower().strip()
            whitelist_normalized = {
                (a.lower().strip(), b.lower().strip())
                for a, b in join_whitelist
            }
            for join in self.joins:
                join_normalized = join.table.lower().strip()
                join_pair = (pt_normalized, join_normalized)
                reverse_pair = (join_normalized, pt_normalized)
                if join_pair not in whitelist_normalized and reverse_pair not in whitelist_normalized:
                    errors.append(
                        f"[IR 主防线] JOIN {self.primary_table} ↔ {join.table} "
                        f"不在核准白名单中"
                    )

        return errors

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
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
# §6 Layer 3: SQLResult —— 执行结果
# ═══════════════════════════════════════════════════════════


@dataclass
class SQLResult:
    """
    Layer 3：SQL 执行结果。

    包含执行的 SQL、返回的数据、元信息。
    校验关注：SQL 是否只读？结果签名是否稳定？
    """
    sql: str
    columns: list[str] = field(default_factory=list)
    column_types: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    source_table: Optional[str] = None

    @property
    def result_signature(self) -> str:
        """
        计算结果签名（MD5）。

        签名 = MD5(行数 + 列名列表 + 列类型列表)
        用于结果稳定性检测——签名变化意味着数据结构发生了变更。
        """
        content = f"{self.row_count}|{','.join(self.columns)}|{','.join(self.column_types)}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def validate(self) -> list[str]:
        """
        校验 SQLResult 的执行正确性。

        Returns:
            警告列表（不阻断，仅提醒）。
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
# §7 ExecutionTrace：单次 SQL 执行的轻量追踪
# ═══════════════════════════════════════════════════════════


@dataclass
class ExecutionTrace:
    """
    单次 SQL 计划执行的轻量追踪记录。

    每个 SQLPlan 执行后生成一条 trace，记录生成、校验、执行全链路的关键状态。
    """
    plan_index: int = 0
    strategy: str = ""
    primary_table: str = ""
    generated_sql: str = ""
    safety_check_passed: bool = False
    row_count: int = 0
    error_message: str = ""
    execution_status: str = "pending"  # pending / success / failed
    execution_time_ms: float = 0.0

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
# §8 结果摘要与合并结构
# ═══════════════════════════════════════════════════════════


@dataclass
class ResultSummary:
    """
    SQLResult 的结构化摘要——为 date merge / LLM 融合 / 图表生成提供稳定输入。

    只做结构化提取，不做业务解释、不推断因果、不补造数据。
    """
    source_plan_index: int = 0
    metrics: list[str] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)
    primary_table: str = ""
    strategy: str = ""
    columns: list[str] = field(default_factory=list)
    column_types: list[str] = field(default_factory=list)
    row_count: int = 0
    sample_rows: list[list] = field(default_factory=list)
    has_date_column: bool = False
    grain: str = "unknown"
    date_min: str = ""
    date_max: str = ""
    warnings: list[str] = field(default_factory=list)

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

    默认 merge_status = NOT_ATTEMPTED 或 SKIPPED。
    后续 Phase 将使用此结构做 LLM 融合 / date merge / 图表生成。
    """
    merge_status: MergeStatus = MergeStatus.NOT_ATTEMPTED
    merge_key: str = ""
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)
    row_count: int = 0
    source_plan_indexes: list[int] = field(default_factory=list)
    source_summaries: list[ResultSummary] = field(default_factory=list)
    merge_warnings: list[str] = field(default_factory=list)
    reason: str = ""

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
# §9 多计划结构：跨表多指标的统一响应
# ═══════════════════════════════════════════════════════════


@dataclass
class UnifiedResponse:
    """
    多计划中每个子计划的统一响应。

    包含：子意图（SubIntent）→ 查询计划（SQLPlan）→ 执行结果（SQLResult）。
    """
    sub_intent: Optional[SubIntent] = None
    plan: Optional[SQLPlan] = None
    result: Optional[SQLResult] = None
    execution_trace: Optional[ExecutionTrace] = None

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "sub_intent": self.sub_intent.to_dict() if self.sub_intent else None,
            "plan": self.plan.to_dict() if self.plan else None,
            "result": self.result.to_dict() if self.result else None,
            "execution_trace": self.execution_trace.to_dict() if self.execution_trace else None,
        }


@dataclass
class AgentResponse:
    """
    Agent 一次完整问答的顶层结构。

    包含三层 IR 的完整链路 + 中文解释。

    单计划场景（向后兼容）：
        - plan / result 填充单计划内容
        - is_multi_plan = False

    多计划场景：
        - plans 包含多个 UnifiedResponse
        - is_multi_plan = True
        - plan / result 仍填充第一个计划（兼容旧调用方）
    """
    question: str = ""
    intent: Optional[QuestionIntent] = None
    plan: Optional[SQLPlan] = None
    result: Optional[SQLResult] = None
    chinese_answer: Optional[str] = None
    clarification_needed: bool = False
    clarification_message: Optional[str] = None
    refusal: bool = False
    refusal_reason: Optional[str] = None
    trace: list[str] = field(default_factory=list)
    is_multi_plan: bool = False
    plans: list[UnifiedResponse] = field(default_factory=list)

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


# ═══════════════════════════════════════════════════════════
# §10 v2.0 代码生成类型
# ═══════════════════════════════════════════════════════════


@dataclass
class CodeGenerationRequest:
    """
    代码生成请求——阶段 3（代码生成）的输入。

    包含阶段 2 产出的设计方案和运行时上下文。
    所有 LLM 生成的代码初始状态为"不可信补丁"。
    """
    design: dict = field(default_factory=dict)    # 设计方案（阶段 2 输出）
    context: dict = field(default_factory=dict)    # 运行时上下文（可用表、JOIN白名单等）
    target_dialect: str = "duckdb"                 # SQL 方言
    include_spark: bool = True                     # 是否同时生成 Spark DSL


@dataclass
class CodeGenerationResult:
    """
    代码生成结果——阶段 3（代码生成）的输出。

    包含独立生成的 SQL 草案和 PySpark DSL 草案。
    两份代码均为"不可信补丁"——必须经过防线 2 验证才能执行。
    """
    sql_code: str = ""                              # SQL 草案（DuckDB）
    spark_dsl_code: str = ""                        # Spark DSL 草案（PySpark）
    sql_source_refs: dict[str, str] = field(default_factory=dict)    # SQL 来源标注
    spark_source_refs: dict[str, str] = field(default_factory=dict)  # Spark 来源标注
    uncertain_annotations: list[str] = field(default_factory=list)   # 不确定项标注
    generation_mode: ExecutionMode = ExecutionMode.SQL_ONLY  # 实际生成模式


@dataclass
class CodeDraft:
    """单份代码草案，进入验证前一律不可信"""
    kind: str
    path: str
    content: str
    language: str
    status: str = "draft_unverified"
    source_refs: dict[str, str] = field(default_factory=dict)
    pending_items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "kind": self.kind,
            "path": self.path,
            "language": self.language,
            "status": self.status,
            "source_refs": self.source_refs,
            "pending_items": self.pending_items,
        }


@dataclass
class DecisionRecord:
    """人审决策记录——M4b 状态机核心。

    current_state 为机读权威状态源（decision.yml）。
    Agent 只能写入 PENDING_REVIEW；APPROVED/REQUEST_CHANGES/REJECTED 仅人可设置。
    artifact_hashes 记录生成时的代码哈希——M4b 完整性校验基础。
    """
    current_state: DecisionStatus = DecisionStatus.PENDING_REVIEW
    options: list[str] = field(default_factory=lambda: [
        "APPROVE",
        "REQUEST_CHANGES",
        "REJECT",
    ])
    human_review_required: bool = True
    notes: list[str] = field(default_factory=list)
    artifact_hashes: Optional[ArtifactHashes] = None

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        result: dict[str, Any] = {
            "current_state": self.current_state.value,
            "options": self.options,
            "human_review_required": self.human_review_required,
            "notes": self.notes,
        }
        if self.artifact_hashes is not None:
            result["artifact_hashes"] = self.artifact_hashes.to_dict()
        return result


@dataclass
class ReviewPackageManifest:
    """Review Package 的落盘清单——M5 扩展部署产物和发布审批"""
    request_id: str
    package_path: str
    files: list[str] = field(default_factory=list)
    deploy_files: list[str] = field(default_factory=list)  # M5：部署产物文件列表
    status: DecisionStatus = DecisionStatus.PENDING_REVIEW
    release_status: str = "DRAFT"           # M5：发布审批状态（ReleaseStatus 值）
    pending_items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "request_id": self.request_id,
            "package_path": self.package_path,
            "files": self.files,
            "deploy_files": self.deploy_files,
            "status": self.status.value,
            "release_status": self.release_status,
            "pending_items": self.pending_items,
        }


# ═══════════════════════════════════════════════════════════
# §11 v2.0 验证与交叉验证类型
# ═══════════════════════════════════════════════════════════


@dataclass
class CheckResult:
    """
    单条检查项结果——防线 2 七项检查的输出原子。

    severity 区分：
      - FAIL：阻断级——不通过则不能进入执行/审查
      - WARN：提醒级——通过但标注，由人审时关注
    """
    check_id: int                           # 检查项编号 1-7
    name: str                               # 检查项名称
    status: ValidationStatus                # 结果状态
    detail: str = ""                        # 详细信息
    severity: str = "FAIL"                  # FAIL | WARN

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
            "severity": self.severity,
        }


@dataclass
class ValidationReport:
    """
    防线 2 完整验证报告——7 项规则引擎检查 + 交叉验证的结果。

    overall_status 聚合规则：
      - 任一 FAIL → FAILED
      - 全 PASSED 但有 WARN → WARN
      - 全 PASSED → PASSED
    """
    overall_status: ValidationStatus = ValidationStatus.PENDING
    checks: list[CheckResult] = field(default_factory=list)
    execution_id: str = ""

    @property
    def passed(self) -> bool:
        """便捷属性：是否通过（无 FAIL）"""
        return self.overall_status != ValidationStatus.FAILED

    @property
    def has_warnings(self) -> bool:
        """是否有警告"""
        return any(c.status == ValidationStatus.WARN for c in self.checks)

    @property
    def fail_count(self) -> int:
        """失败检查项数量"""
        return sum(1 for c in self.checks if c.status == ValidationStatus.FAILED)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status.value,
            "checks": [c.to_dict() for c in self.checks],
            "execution_id": self.execution_id,
        }


@dataclass
class CrossValidationResult:
    """
    交叉验证结果——防线 2 检查项 #7 的详细输出。

    SQL 和 PySpark 两份代码独立执行后，对比行数、列名、值分布、抽样行。
    三种可能结果：
      - CONSISTENT：一致——置信度大幅提高
      - INCONSISTENT：不一致——人审时必须调查
      - SKIPPED：跳过——Spark 环境不可用
    """
    status: CrossValidateStatus = CrossValidateStatus.NOT_ATTEMPTED
    sql_row_count: int = 0
    spark_row_count: int = 0
    column_match: bool = False
    value_diffs: list[dict] = field(default_factory=list)  # 值差异详情
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "sql_row_count": self.sql_row_count,
            "spark_row_count": self.spark_row_count,
            "column_match": self.column_match,
            "value_diffs": self.value_diffs,
            "detail": self.detail,
        }


# ═══════════════════════════════════════════════════════════
# §12 v2.0 审查材料类型
# ═══════════════════════════════════════════════════════════


@dataclass
class ReviewMaterial:
    """单个审查材料项"""
    file_path: str
    content: str
    mime_type: str = "text/plain"


@dataclass
class ReviewPackage:
    """
    完整人审材料包——阶段 5（材料输出）的产出。

    包含从需求分析到交叉验证的完整链路信息，
    是人审闸门（阶段 6）的唯一输入。
    """
    requirement: dict = field(default_factory=dict)            # 需求分析报告（阶段 1）
    design: dict = field(default_factory=dict)                 # 设计方案（阶段 2）
    codes: list[ReviewMaterial] = field(default_factory=list)  # 双份代码（阶段 3）
    validation: Optional[ValidationReport] = None              # 验证报告（阶段 4）
    cross_validation: Optional[CrossValidationResult] = None   # 交叉验证（阶段 4 #7）
    uncertainties: list[str] = field(default_factory=list)     # 不确定项清单
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement,
            "design": self.design,
            "codes": [
                {"file_path": c.file_path, "mime_type": c.mime_type}
                for c in self.codes
            ],
            "validation": self.validation.to_dict() if self.validation else None,
            "cross_validation": self.cross_validation.to_dict() if self.cross_validation else None,
            "uncertainties": self.uncertainties,
            "created_at": self.created_at,
        }
