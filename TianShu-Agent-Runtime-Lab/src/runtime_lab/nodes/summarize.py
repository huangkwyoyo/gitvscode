"""总结节点——生成最终输出"""

from runtime_lab.state import RuntimeState


def summarize_node(state: RuntimeState) -> dict:
    """生成运行总结"""
    if state.errors:
        status = "failed_closed"
    elif state.status == "waiting_approval":
        status = "waiting_approval"
    else:
        status = "completed"

    return {
        "status": status,
        "current_step": "summarize",
    }
