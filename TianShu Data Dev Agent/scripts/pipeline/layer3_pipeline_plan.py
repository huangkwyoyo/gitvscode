"""
Layer 3 扩展：PipelinePlan 数据类（Phase 2）

职责：
  1. 定义 PipelinePlan 和 PipelineStep 数据结构
  2. PipelinePlan 是 SQLPlan 的上层容器——SQLPlan 描述一条 SQL，
     PipelinePlan 描述包含多条 SQL 的 DAG

LLM 角色：
  **完全禁止**。此层是纯确定性代码。
  PipelinePlan 由 Layer 3 规划器根据 Intent 构造，
  或从 YAML 契约文件加载。

IR 分层原则（v2.1 修正）：
  - PipelinePlan 只保留**跨步骤**的概念（DAG 依赖、操作类型、输出目标、增量意图）
  - 所有**语句级**的概念（窗口函数、表达式、CTE）属于 SQLPlan
  - 所有**列级**的概念（ColumnRef、ExpressionOperand）属于 SQLPlan
  - 列引用使用统一的 ColumnRef(table_ref, column_name) 结构
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any

from .layer3_ir import SQLPlan


# ═══════════════════════════════════════════════════════════
# Phase 2：PipelinePlan 数据结构
# ═══════════════════════════════════════════════════════════

# ── Step 操作类型枚举 ──

class StepOperation(str, Enum):
    """
    步骤操作类型——定义 IR 级别的操作语义

    使用 str+Enum 继承：既能像字符串一样比较，又有类型安全保证。
    """
    SELECT_ONLY = "SELECT_ONLY"
    CREATE_TABLE_AS_SELECT = "CREATE_TABLE_AS_SELECT"
    INSERT_OVERWRITE_PARTITION = "INSERT_OVERWRITE_PARTITION"
    INSERT_INTO_PARTITION = "INSERT_INTO_PARTITION"
    CREATE_VIEW = "CREATE_VIEW"

    @classmethod
    def read_only_operations(cls) -> set["StepOperation"]:
        """只读操作集合"""
        return {cls.SELECT_ONLY}

    @classmethod
    def write_operations(cls) -> set["StepOperation"]:
        """写操作集合"""
        return {
            cls.CREATE_TABLE_AS_SELECT,
            cls.INSERT_OVERWRITE_PARTITION,
            cls.INSERT_INTO_PARTITION,
            cls.CREATE_VIEW,
        }


@dataclass
class IncrementalIntent:
    """
    增量意图——IR 只描述"要不要增量"和"以什么键去重"

    注意：不包含执行策略（merge/append/overwrite）。
    编译器根据此意图 + 目标表结构决定具体执行策略。
    """
    incremental: bool = False
    key_columns: list[str] = field(default_factory=list)      # 业务主键——用于去重/合并
    watermark_column: str = ""                                  # 水位线列名
    partition_column: str = ""                                  # 分区列名
    dedup_scope: str = "partition"                              # 去重范围：partition | full_table | key_merge


@dataclass
class PipelineStep:
    """
    管道步骤——DAG 的一个节点

    Pipeline IR 只保留跨步骤的概念：
      - step_id / step_name：步骤标识
      - depends_on[]：DAG 依赖边（跨步骤引用）
      - operation + target_table：这个步骤做什么、输出到哪里
      - sql_plan：嵌套的 SQLPlan（包含此步骤的全部语句级 IR）
      - incremental_intent：增量意图（步骤的输出如何在批次间维护）
    """
    # ── 步骤标识 ──
    step_id: str                       # 步骤唯一标识（用于依赖引用 $step.xxx）
    step_name: str                     # 步骤人类可读名称

    # ── 操作类型 ──
    operation: StepOperation           # 步骤操作类型枚举

    # ── 输出目标 ──
    target_table: str                  # 步骤输出的目标表名（schema.table 格式）

    # ── DAG 依赖（唯一跨步骤引用）──
    depends_on: list[str] = field(default_factory=list)  # 依赖的 step_id 列表

    # ── 核心 SQLPlan（包含窗口函数、表达式、CTE——全部在此）──
    sql_plan: Optional[SQLPlan] = None

    # ── 增量意图 ──
    incremental_intent: Optional[IncrementalIntent] = None


@dataclass
class PipelinePlan:
    """
    PipelinePlan —— Phase 2 的核心 IR

    SQLPlan 描述一条 SQL，PipelinePlan 描述一个包含多条 SQL 的 DAG。
    这是 Layer 3 在 Phase 2 的输出。

    层次关系：
      PipelinePlan (DAG)
        ├── steps[] (节点)
        │   ├── depends_on[] (边——跨步骤)
        │   ├── operation + target_table (步骤属性)
        │   ├── incremental_intent (增量意图)
        │   └── sql_plan: SQLPlan (单条 SQL 的完整 IR)
        │       ├── join_graph (表结构)
        │       ├── column_bindings (SELECT 列)
        │       ├── filter_bindings (WHERE 条件)
        │       ├── window_functions[] (窗口函数——语句级)
        │       ├── expression_refs[] (表达式——列级)
        │       └── cte_definitions[] (CTE——语句级 WITH 子句)
    """
    # ── 管道标识 ──
    pipeline_id: str
    pipeline_name: str
    version: str = "1.0.0"
    target_dialect: str = "duckdb"     # duckdb | hive | spark_sql | postgresql
    description: str = ""

    # ── DAG：步骤列表（按拓扑序排列）──
    steps: list[PipelineStep] = field(default_factory=list)

    # ── 管道级参数 ──
    parameters: dict[str, Any] = field(default_factory=dict)

    # ── 诊断 ──
    is_valid: bool = True
    validation_errors: list[str] = field(default_factory=list)

    # ── 元数据 ──
    created_at: str = ""
    created_by: str = ""
