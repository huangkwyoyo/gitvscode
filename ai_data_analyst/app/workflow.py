from __future__ import annotations

from collections.abc import Callable

from app.models import AnalysisState
from app.services.cleaning import clean_data
from app.services.exploration import explore_data
from app.services.insights import generate_insights
from app.services.loader import load_data
from app.services.reporting import generate_report
from app.services.visualization import build_chart_specs


WorkflowNode = Callable[[AnalysisState], AnalysisState]


class AnalysisWorkflow:
    """确定性图运行器。
    状态对象沿命名节点推进，每个节点负责一个业务能力。
    后续若替换为 LangGraph，服务层代码无需改动。
    """

    # 依赖关系：每个节点需要的上游字段
    REQUIREMENTS = {
        "load_data": [],
        "clean_data": ["raw_df"],
        "explore_data": ["clean_df"],
        "visualize": ["exploration"],
        "generate_insights": ["exploration"],
        "generate_report": ["insights"],
    }

    def __init__(self) -> None:
        self.nodes: list[tuple[str, WorkflowNode]] = [
            ("load_data", load_data),
            ("clean_data", clean_data),
            ("explore_data", explore_data),
            ("visualize", build_chart_specs),
            ("generate_insights", generate_insights),
            ("generate_report", generate_report),
        ]

    def run(self, state: AnalysisState) -> AnalysisState:
        for node_name, node in self.nodes:
            required = self.REQUIREMENTS[node_name]
            missing = [key for key in required if getattr(state, key) is None and not getattr(state, key, {})]
            if missing:
                state.errors.append(f"{node_name}: skipped — upstream dependency missing ({', '.join(missing)})")
                continue
            try:
                state = node(state)
            except Exception as exc:
                state.errors.append(f"{node_name}: {exc}")
        return state

