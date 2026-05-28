from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class AnalysisState:
    job_id: str
    original_filename: str
    analysis_goal: str
    upload_path: Path
    output_dir: Path
    analysis_type: str = "general"
    raw_df: pd.DataFrame | None = None
    clean_df: pd.DataFrame | None = None
    schema: dict[str, Any] = field(default_factory=dict)
    cleaning_log: list[dict[str, Any]] = field(default_factory=list)
    quality: dict[str, Any] = field(default_factory=dict)
    exploration: dict[str, Any] = field(default_factory=dict)
    chart_specs: list[dict[str, Any]] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    finance_metrics: dict[str, Any] = field(default_factory=dict)
    report_path: Path | None = None
    preview_rows: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def public_payload(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "filename": self.original_filename,
            "goal": self.analysis_goal,
            "analysis_type": self.analysis_type,
            "schema": self.schema,
            "cleaning_log": self.cleaning_log,
            "quality": self.quality,
            "exploration": self.exploration,
            "chart_specs": self.chart_specs,
            "insights": self.insights,
            "finance_metrics": self.finance_metrics,
            "preview_rows": self.preview_rows,
            "report_url": f"/api/report/{self.job_id}" if self.report_path else None,
            "errors": self.errors,
        }
