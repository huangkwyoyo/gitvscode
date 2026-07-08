"""Trace 存储——记录 State 变化和工具调用"""

import json
from pathlib import Path


class TraceStore:
    """持久化 Agent 运行追踪记录"""

    def __init__(self, run_dir: str):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        # 子目录
        self.reports_dir = self.run_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir = self.run_dir / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def save_state_history(self, state, step_info: dict | None = None) -> None:
        """追加一条 State 变化记录到 state_history.jsonl"""
        record = {
            "run_id": state.run_id,
            "status": state.status,
            "current_step": state.current_step,
            "created_at": state.created_at,
            "updated_at": state.updated_at,
        }
        if step_info:
            record["step_info"] = step_info

        history_file = self.run_dir / "state_history.jsonl"
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def write_run_report(self, state) -> None:
        """生成 run_report.md"""
        report = _build_run_report(state)
        report_file = self.reports_dir / "run_report.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)


def _build_run_report(state) -> str:
    """构建运行报告 Markdown 文本"""
    lines = []
    lines.append("# Run Report\n")
    lines.append("## Summary\n")
    lines.append(f"本次运行：{state.user_input or '（空）'}\n")
    lines.append("## Final Status\n")
    lines.append(f"{state.status}\n")
    if state.errors:
        lines.append("## Errors\n")
        for err in state.errors:
            lines.append(f"- {err}\n")
    lines.append("## Artifacts\n")
    lines.append(f"- Run ID: {state.run_id}\n")
    lines.append(f"- Created: {state.created_at}\n")
    return "".join(lines)
