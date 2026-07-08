"""任务分类节点——判断运行哪个 Demo"""


def classify_node(state) -> dict:
    """根据用户输入判断 Demo 类型"""
    text = state.user_input.lower() if isinstance(state.user_input, str) else ""

    if "sql" in text or "review" in text:
        demo_type = "sql_review"
    elif "contract" in text:
        demo_type = "contract"
    elif "join" in text:
        demo_type = "join"
    elif "datadev" in text or "plan" in text:
        demo_type = "datadev"
    else:
        demo_type = "greet"

    return {
        "demo_type": demo_type,
        "current_step": "classify",
        "next_action": "summarize" if demo_type == "greet" else "plan",
    }
