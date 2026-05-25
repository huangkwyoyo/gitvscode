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
    """Small deterministic graph runner.

    This is intentionally LangGraph-shaped: a state object moves through named
    nodes, and each node owns one business capability. Replacing this with
    LangGraph later should not require changing the service layer.
    """

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
            try:
                state = node(state)
            except Exception as exc:  # keep jobs inspectable rather than opaque
                state.errors.append(f"{node_name}: {exc}")
                break
        return state

