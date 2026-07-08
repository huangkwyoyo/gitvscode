"""统一运行状态定义——记录 Agent 一次执行的全生命周期状态"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RuntimeState:
    """运行状态

    记录一次 Agent 任务执行到哪一步、已产生什么中间结果、调用过哪些工具。
    每个 LangGraph 节点只读写自己关心的字段。
    """

    # 运行标识
    run_id: str = ""
    thread_id: str = ""

    # 输入与分类
    user_input: str = ""
    demo_type: str = ""  # "sql_review" | "contract" | "join" | "datadev" | "greet"

    # 执行流转
    current_step: str = "init"
    next_action: str = ""
    status: str = "init"  # init | running | waiting_approval | completed | failed_closed

    # 中间产物（按需填充）
    intermediate: dict = field(default_factory=dict)

    # 工具调用记录
    tool_call_history: list = field(default_factory=list)

    # 错误记录
    errors: list = field(default_factory=list)

    # 元信息
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        """自动填充时间戳"""
        now = datetime.now().isoformat(timespec="seconds")
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
