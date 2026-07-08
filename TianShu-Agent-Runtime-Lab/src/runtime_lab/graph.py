"""LangGraph 单 Agent Runtime 主图定义"""

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from runtime_lab.state import RuntimeState
from runtime_lab.nodes.classify import classify_node
from runtime_lab.nodes.summarize import summarize_node


def router(state: RuntimeState) -> str:
    """根据 demo_type 路由到下一个节点"""
    if state.demo_type == "greet":
        return "summarize"
    # 其他 Demo 类型第 2 周起实现路由
    return "summarize"


def build_graph() -> CompiledStateGraph:
    """构建并编译 LangGraph 图"""
    builder = StateGraph(RuntimeState)

    # 注册节点
    builder.add_node("classify_demo", classify_node)
    builder.add_node("summarize", summarize_node)

    # 设置入口
    builder.set_entry_point("classify_demo")

    # 条件边
    builder.add_conditional_edges(
        "classify_demo",
        router,
        {
            "summarize": "summarize",
            "__end__": "__end__",
        },
    )

    # 固定边
    builder.add_edge("summarize", "__end__")

    return builder.compile()
