"""总结节点——生成最终输出"""


def summarize_node(state) -> dict:
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
