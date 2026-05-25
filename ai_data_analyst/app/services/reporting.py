from __future__ import annotations

import json

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models import AnalysisState
from app.settings import TEMPLATE_DIR


def generate_report(state: AnalysisState) -> AnalysisState:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html")
    html = template.render(
        title=f"{state.original_filename} 分析报告",
        state=state.public_payload(),
        state_json=json.dumps(state.public_payload(), ensure_ascii=False),
    )
    report_path = state.output_dir / "analysis_report.html"
    report_path.write_text(html, encoding="utf-8")
    state.report_path = report_path
    return state

