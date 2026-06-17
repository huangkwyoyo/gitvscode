"""
测试 v2.0 M2 Review Package 生成能力。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from src.agent.dual_code_generator import (
    FORBIDDEN_SPARK_PATTERNS,
    FORBIDDEN_SQL_KEYWORDS,
    validate_spark_draft,
    validate_sql_draft,
)
from src.agent.requirement_analyzer import analyze_requirement
from src.agent.workflow import build_review_package


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
CLI = PROJECT_ROOT / "scripts" / "dev_agent" / "build_review_package.py"


def _assert_package_complete(package_dir: Path) -> None:
    """校验审查材料包的目录和文件完整性。"""
    assert (package_dir / "sql").is_dir()
    assert (package_dir / "spark").is_dir()
    assert (package_dir / "tests").is_dir()
    assert (package_dir / "reports").is_dir()
    assert (package_dir / "lineage").is_dir()
    assert (package_dir / "decision.md").is_file()

    assert (package_dir / "sql" / "main.sql").is_file()
    assert (package_dir / "spark" / "main.py").is_file()
    assert (package_dir / "tests" / "test_generated.py").is_file()
    assert (package_dir / "reports" / "verification.md").is_file()
    assert (package_dir / "reports" / "cross_validation.md").is_file()
    assert (package_dir / "lineage" / "source_refs.yml").is_file()


def test_workflow_generates_complete_review_package(tmp_path):
    """主流程只生成完整 Review Package，不执行 SQL/Spark。"""
    manifest = build_review_package(FIXTURE, output_root=tmp_path)
    package_dir = Path(manifest.package_path)

    _assert_package_complete(package_dir)
    assert manifest.request_id == "trip_daily_report_m2"
    assert manifest.status == "PENDING_REVIEW"


def test_cli_generates_review_package(tmp_path):
    """CLI 成功后输出 Review Package 路径。"""
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "-r",
            str(FIXTURE),
            "--output-root",
            str(tmp_path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    match = re.search(r"Review Package:\s*(.+)", result.stdout)
    assert match, result.stdout
    package_dir = Path(match.group(1).strip())
    _assert_package_complete(package_dir)


def test_decision_contains_required_options(tmp_path):
    """decision.md 必须包含三种人审决策，默认状态为 PENDING_REVIEW。"""
    manifest = build_review_package(FIXTURE, output_root=tmp_path)
    decision = Path(manifest.package_path, "decision.md").read_text(encoding="utf-8")

    assert "APPROVE" in decision
    assert "REQUEST_CHANGES" in decision
    assert "REJECT" in decision
    assert "当前状态：PENDING_REVIEW" in decision
    assert "当前状态：APPROVED" not in decision


def test_package_marks_drafts_unverified_unreviewed_not_for_release(tmp_path):
    """核心产物必须明确草案、未经验证、未经人审、不得上线。"""
    manifest = build_review_package(FIXTURE, output_root=tmp_path)
    package_dir = Path(manifest.package_path)
    combined = "\n".join(
        [
            (package_dir / "sql" / "main.sql").read_text(encoding="utf-8"),
            (package_dir / "spark" / "main.py").read_text(encoding="utf-8"),
            (package_dir / "decision.md").read_text(encoding="utf-8"),
        ]
    )

    for text in ["草案", "未经验证", "未经人审", "不得上线"]:
        assert text in combined


def test_m2_reports_do_not_claim_pass(tmp_path):
    """M2 报告只能是 PENDING/SKIPPED，不能伪装 PASS。"""
    manifest = build_review_package(FIXTURE, output_root=tmp_path)
    package_dir = Path(manifest.package_path)
    verification = (package_dir / "reports" / "verification.md").read_text(encoding="utf-8")
    cross_validation = (package_dir / "reports" / "cross_validation.md").read_text(encoding="utf-8")

    assert "PENDING" in verification or "SKIPPED" in verification
    assert "PENDING" in cross_validation or "SKIPPED" in cross_validation
    assert "PASS" not in verification.upper()
    assert "PASS" not in cross_validation.upper()


def test_lineage_records_sources_and_human_review(tmp_path):
    """source_refs.yml 必须记录来源，缺少内容标记 Human Review。"""
    manifest = build_review_package(FIXTURE, output_root=tmp_path)
    lineage = yaml.safe_load(
        Path(manifest.package_path, "lineage", "source_refs.yml").read_text(encoding="utf-8")
    )

    assert lineage["request_id"] == "trip_daily_report_m2"
    assert lineage["source_tables"]
    assert lineage["source_fields"]
    assert lineage["metric_sources"]
    assert lineage["human_review_points"]


def test_missing_request_id_fails(tmp_path):
    """缺少 request_id 必须失败，不能自动编造。"""
    bad = tmp_path / "missing_request_id.yml"
    bad.write_text(
        yaml.safe_dump(
            {
                "title": "bad",
                "business_goal": "bad",
                "source_tables": [{"name": "gold.dws_daily_trip_summary"}],
                "required_fields": [{"name": "trip_date", "table": "gold.dws_daily_trip_summary"}],
                "metrics": [{"name": "trip_count", "field": "trip_count"}],
                "filters": {"date_range": ["2026-01-01", "2026-01-02"]},
                "grain": ["trip_date"],
                "output_expectation": "review only",
                "human_notes": [],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="request_id"):
        analyze_requirement(bad)


def test_sql_draft_rejects_dml_ddl():
    """SQL 草案只允许 SELECT，不允许 DDL/DML 关键字。"""
    assert validate_sql_draft("SELECT trip_count FROM gold.dws_daily_trip_summary") == []
    for keyword in FORBIDDEN_SQL_KEYWORDS:
        errors = validate_sql_draft(f"{keyword} TABLE gold.dws_daily_trip_summary")
        assert errors, keyword


def test_spark_draft_rejects_write_patterns():
    """Spark 草案不能包含写入相关模式。"""
    assert validate_spark_draft("df = spark.table('gold.t').select('trip_count')") == []
    for pattern in FORBIDDEN_SPARK_PATTERNS:
        errors = validate_spark_draft(f"df{pattern}('gold.t')")
        assert errors, pattern


def test_generated_code_uses_only_fixture_tables_and_fields(tmp_path):
    """生成的 SQL/Spark 只能引用 fixture 声明的表和字段。"""
    requirement = analyze_requirement(FIXTURE)
    manifest = build_review_package(FIXTURE, output_root=tmp_path)
    package_dir = Path(manifest.package_path)

    allowed_tables = {table["name"] for table in requirement.source_tables}
    allowed_fields = {field["name"] for field in requirement.required_fields}
    allowed_fields.update(metric["field"] for metric in requirement.metrics)
    allowed_fields.update(requirement.grain)

    sql = (package_dir / "sql" / "main.sql").read_text(encoding="utf-8")
    spark = (package_dir / "spark" / "main.py").read_text(encoding="utf-8")

    for table in allowed_tables:
        assert table in sql
        assert table in spark

    suspicious_identifiers = {
        "total_tip_amount",
        "fare_amount",
        "pickup_datetime",
        "dropoff_datetime",
    }
    for identifier in suspicious_identifiers - allowed_fields:
        assert not re.search(rf"\b{identifier}\b", sql)
        assert not re.search(rf"\b{identifier}\b", spark)
