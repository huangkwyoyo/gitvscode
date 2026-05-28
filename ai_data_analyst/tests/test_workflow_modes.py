from pathlib import Path

import pandas as pd

from app.models import AnalysisState
from app.services.cleaning import clean_data
from app.workflow import AnalysisWorkflow


def test_percent_string_columns_are_scaled_to_decimal(tmp_path):
    state = AnalysisState(
        job_id="pct",
        original_filename="inline.csv",
        analysis_goal="",
        upload_path=Path("inline.csv"),
        output_dir=tmp_path,
    )
    state.raw_df = pd.DataFrame({"fee_rate": ["5%", "10%", "15%"]})

    result = clean_data(state)

    assert result.clean_df["fee_rate"].tolist() == [0.05, 0.10, 0.15]


def test_general_mode_does_not_run_finance_metrics(tmp_path):
    state = AnalysisState(
        job_id="general",
        original_filename="sales_sample.csv",
        analysis_goal="sales analysis",
        analysis_type="general",
        upload_path=Path("samples/sales_sample.csv"),
        output_dir=tmp_path,
    )

    result = AnalysisWorkflow().run(state)

    assert result.errors == []
    assert result.finance_metrics == {}


def test_finance_mode_runs_finance_metrics(tmp_path):
    state = AnalysisState(
        job_id="finance",
        original_filename="pe_fund_sample.csv",
        analysis_goal="fund analysis",
        analysis_type="finance",
        upload_path=Path("samples/pe_fund_sample.csv"),
        output_dir=tmp_path,
    )

    result = AnalysisWorkflow().run(state)

    assert result.errors == []
    assert "fund_a_nav" in result.finance_metrics
    assert result.finance_metrics["fund_a_nav"]["annualized_return"] is not None
