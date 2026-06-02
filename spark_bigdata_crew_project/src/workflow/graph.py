"""
LangGraph生产级工作流状态图
8步任务 + 3道人工审批Gate + 校验失败阻断 + 条件路由

流程图:
  task_1 → task_2 → [Gate_1: 审批?] ──驳回→ 回task_1
                      │ 通过
                      ▼
  task_3 → task_4 → [Gate_2: 审批?] ──驳回→ 回task_3
                      │ 通过
                      ▼
  task_5 → task_6 → [Gate_3: 审批?] ──驳回→ 回task_5
                      │ 通过
                      ▼
  task_7 → task_8 → END
"""
import logging
from typing import Literal
from datetime import datetime

from .state import PipelineState, create_initial_state, GateStatus
from .checkpoints import save_state, save_gate_approval

logger = logging.getLogger(__name__)

# 任务顺序定义
WORKFLOW_STEPS = [
    "task_1_requirement_analysis",
    "task_2_metadata_validation",
    "gate_1_requirement_data_confirm",
    "task_3_field_mapping",
    "task_4_data_modeling",
    "gate_2_model_confirm",
    "task_5_spark_development",
    "task_6_code_quality_check",
    "gate_3_code_approval",
    "task_7_quality_report",
    "task_8_delivery_archive",
]

GATE_STEPS = {
    "gate_1_requirement_data_confirm": {
        "id": "gate_1",
        "name": "需求与数据源确认",
        "blocked_on_reject": "task_1_requirement_analysis",
    },
    "gate_2_model_confirm": {
        "id": "gate_2",
        "name": "模型与字段映射确认",
        "blocked_on_reject": "task_3_field_mapping",
    },
    "gate_3_code_approval": {
        "id": "gate_3",
        "name": "代码执行前确认",
        "blocked_on_reject": "task_5_spark_development",
    },
}


def create_workflow_graph():
    """构建LangGraph工作流状态图"""
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        logger.warning("LangGraph未安装，无法构建工作流图。安装: pip install langgraph")
        return None

    workflow = StateGraph(PipelineState)

    # 注册所有任务节点
    for step in WORKFLOW_STEPS:
        if step.startswith("gate_"):
            workflow.add_node(step, _gate_node)
        else:
            workflow.add_node(step, _task_node)

    # 设置入口
    workflow.set_entry_point(WORKFLOW_STEPS[0])

    # 连接节点：每个步骤完成后路由到下一步
    for i, step in enumerate(WORKFLOW_STEPS):
        if step in GATE_STEPS:
            # Gate节点：条件路由（通过→下一步，驳回→回退）
            workflow.add_conditional_edges(
                step,
                _gate_router,
                {
                    "approved": WORKFLOW_STEPS[i + 1] if i + 1 < len(WORKFLOW_STEPS) else END,
                    "rejected": GATE_STEPS[step]["blocked_on_reject"],
                }
            )
        else:
            # 普通任务节点：直接进入下一步
            next_step = WORKFLOW_STEPS[i + 1] if i + 1 < len(WORKFLOW_STEPS) else END
            workflow.add_edge(step, next_step)

    return workflow.compile(
        checkpointer=None,  # 使用自定义checkpoint（src/workflow/checkpoints.py）
        interrupt_before=list(GATE_STEPS.keys()),  # Gate前自动中断，等待人工审批
    )


def _task_node(state: PipelineState) -> PipelineState:
    """通用任务执行节点（实际执行委托给CrewAI）"""
    step = state["current_step"]
    logger.info("执行任务: %s", step)

    state["results"][step] = {
        "task_name": step,
        "status": "completed",
        "output": f"[{step}] 任务执行完成",
        "error": None,
        "started_at": datetime.now().isoformat(),
        "completed_at": datetime.now().isoformat(),
    }

    # 自动推进到下一步
    current_idx = WORKFLOW_STEPS.index(step)
    if current_idx + 1 < len(WORKFLOW_STEPS):
        state["current_step"] = WORKFLOW_STEPS[current_idx + 1]
        state["step_index"] = current_idx + 1

    save_state(state["run_id"], state)
    return state


def _gate_node(state: PipelineState) -> PipelineState:
    """Gate审批节点"""
    step = state["current_step"]
    gate_info = GATE_STEPS.get(step, {})
    gate_id = gate_info.get("id", step)
    gate_name = gate_info.get("name", step)

    logger.info("到达审批Gate: %s (%s)", gate_name, gate_id)

    state["pending_approval"] = gate_id
    state["gates"][gate_id] = {
        "gate_id": gate_id,
        "name": gate_name,
        "approved": False,
        "approver": "",
        "timestamp": "",
        "comment": "",
    }

    save_state(state["run_id"], state)
    return state


def _gate_router(state: PipelineState) -> Literal["approved", "rejected"]:
    """Gate条件路由：根据审批状态决定下一跳"""
    pending = state.get("pending_approval", "")
    if pending and pending in state.get("gates", {}):
        gate_status = state["gates"][pending]
        if gate_status.get("approved", False):
            logger.info("Gate [%s] 审批通过", pending)
            state["pending_approval"] = None
            return "approved"

    logger.info("Gate [%s] 审批驳回或等待中", pending)
    state["blocked"] = True
    state["block_reason"] = f"Gate {pending} 审批未通过"
    return "rejected"


def approve_gate(state: PipelineState, gate_id: str, approver: str = "", comment: str = "") -> PipelineState:
    """外部调用：审批通过指定Gate"""
    if gate_id in state.get("gates", {}):
        state["gates"][gate_id]["approved"] = True
        state["gates"][gate_id]["approver"] = approver
        state["gates"][gate_id]["comment"] = comment
        state["gates"][gate_id]["timestamp"] = datetime.now().isoformat()
        state["blocked"] = False
        state["block_reason"] = ""
        state["pending_approval"] = None
        save_gate_approval(state["run_id"], gate_id, True, approver, comment)
        save_state(state["run_id"], state)
    return state


def reject_gate(state: PipelineState, gate_id: str, approver: str = "", comment: str = "") -> PipelineState:
    """外部调用：驳回指定Gate"""
    if gate_id in state.get("gates", {}):
        state["gates"][gate_id]["approved"] = False
        state["gates"][gate_id]["approver"] = approver
        state["gates"][gate_id]["comment"] = comment
        state["gates"][gate_id]["timestamp"] = datetime.now().isoformat()
        state["blocked"] = True
        state["block_reason"] = f"Gate {gate_id} 被驳回: {comment}"
        save_gate_approval(state["run_id"], gate_id, False, approver, comment)
        save_state(state["run_id"], state)
    return state
