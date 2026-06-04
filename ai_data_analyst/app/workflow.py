from __future__ import annotations

from collections.abc import Callable

from app.models import AnalysisState
from app.services.cleaning import clean_data
from app.services.exploration import explore_data
from app.services.insights import generate_insights
from app.services.loader import load_data
from app.services.reporting import generate_report
from app.services.visualization import build_chart_specs
from app.services.logger import get_logger

logger = get_logger(__name__)


WorkflowNode = Callable[[AnalysisState], AnalysisState]


class AnalysisWorkflow:
    """确定性图运行器。
    状态对象沿命名节点推进，每个节点负责一个业务能力。
    后续若替换为 LangGraph，服务层代码无需改动。
    """

    # 依赖关系：每个节点需要的上游字段
    # 关键节点失败时应提前终止整个流程
    CRITICAL_NODES = {"load_data", "clean_data", "explore_data"}

    REQUIREMENTS = {
        "load_data": [],
        "clean_data": ["raw_df"],
        "explore_data": ["clean_df"],
        "visualize": ["exploration"],
        "generate_insights": ["exploration"],
        "generate_report": ["insights"],
    }

    # 各节点的中文标签，用于前端进度展示
    STEP_LABELS = {
        "load_data": "加载数据",
        "clean_data": "清洗数据",
        "explore_data": "探索分析",
        "visualize": "生成图表",
        "generate_insights": "提取洞察",
        "generate_report": "生成报告",
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
        failed_nodes: set[str] = set()
        step_percent = 100 // max(len(self.nodes), 1)  # 每个节点的进度增量
        completed = 0
        for node_name, node in self.nodes:
            logger.info("执行节点: %s", node_name)
            state.current_step = self.STEP_LABELS.get(node_name, node_name)
            required = self.REQUIREMENTS[node_name]
            missing = [key for key in required if getattr(state, key) is None and not getattr(state, key, {})]
            # 检查上游依赖节点是否失败
            upstream_failed = self._upstream_failed(node_name, failed_nodes)
            if upstream_failed:
                state.errors.append(f"{node_name}: skipped — upstream node(s) failed")
                continue
            if missing:
                state.errors.append(f"{node_name}: skipped — upstream dependency missing ({', '.join(missing)})")
                failed_nodes.add(node_name)
                continue
            try:
                state = node(state)
                logger.info("节点完成: %s", node_name)
            except Exception as exc:
                state.errors.append(f"{node_name}: {exc}")
                failed_nodes.add(node_name)
                if node_name in self.CRITICAL_NODES:
                    state.errors.append("分析流程因关键节点失败而终止")
                    break
            completed += 1
            state.progress = min(completed * step_percent, 100)
        state.progress = 100
        state.current_step = "完成"
        # 释放 DataFrame 内存，后续仅需 preview_rows 和 exploration 等聚合数据
        state.release_dataframes()
        return state

    @staticmethod
    def _upstream_failed(node_name: str, failed_nodes: set[str]) -> bool:
        """检查节点的上游依赖节点是否有失败的。"""
        deps = AnalysisWorkflow.REQUIREMENTS.get(node_name, [])
        # 根据依赖字段反推上游节点
        field_to_node = {
            "raw_df": "load_data",
            "clean_df": "clean_data",
            "exploration": "explore_data",
            "insights": "generate_insights",
        }
        for dep_field in deps:
            upstream_node = field_to_node.get(dep_field)
            if upstream_node and upstream_node in failed_nodes:
                return True
        return False

