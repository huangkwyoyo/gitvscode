"""
LangGraph工作流状态定义
基于 run_id + state manifest + artifact store 的生产级状态管理
"""
from typing import TypedDict, Optional, Annotated
from datetime import datetime
import operator


class GateStatus(TypedDict):
    gate_id: str
    name: str
    approved: bool
    approver: str
    timestamp: str
    comment: str


class TaskResult(TypedDict):
    task_name: str
    status: str  # pending | running | completed | failed | blocked
    output: str
    error: Optional[str]
    started_at: str
    completed_at: str


class PipelineState(TypedDict):
    """全局流水线状态，贯穿所有LangGraph节点"""
    # 运行标识
    run_id: str
    started_at: str

    # 输入
    user_prd: str

    # 任务产出（按task_name索引）
    results: Annotated[dict, operator.ior]

    # 审批Gate状态
    gates: Annotated[dict, operator.ior]

    # 当前进度
    current_step: str
    step_index: int
    total_steps: int

    # 阻断状态
    blocked: bool
    block_reason: str

    # 错误信息
    error: Optional[str]

    # 人工审批交互（外部系统注入）
    pending_approval: Optional[str]


def create_initial_state(user_prd: str = "") -> PipelineState:
    return PipelineState(
        run_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
        started_at=datetime.now().isoformat(),
        user_prd=user_prd,
        results={},
        gates={},
        current_step="task_1_requirement_analysis",
        step_index=0,
        total_steps=11,  # 8 tasks + 3 gates
        blocked=False,
        block_reason="",
        error=None,
        pending_approval=None,
    )
