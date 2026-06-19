"""
测试 v2.0 M3 Verification Engine。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

from src.agent.verification_engine import verify_review_package
from src.verify.checker import Validator
from src.verify.cross_validation import compare_results
from src.ir.types import CrossValidateStatus, SQLResult, ValidationStatus


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
BUILD_CLI = PROJECT_ROOT / "scripts" / "dev_agent" / "build_review_package.py"
VERIFY_CLI = PROJECT_ROOT / "scripts" / "dev_agent" / "verify_review_package.py"


def _build_package(tmp_path: Path) -> Path:
    """先运行 M2，生成待验证的 Review Package。"""
    result = subprocess.run(
        [
            sys.executable,
            str(BUILD_CLI),
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
    return tmp_path / "trip_daily_report_m2"


@pytest.fixture
def sample_conn():
    """构造只用于测试的内存 sample 数据源。"""
    if not DUCKDB_AVAILABLE:
        pytest.skip("duckdb 未安装")
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE gold_dws_daily_trip_summary (
            trip_date DATE,
            trip_count INTEGER,
            total_fare_amount DOUBLE,
            total_distance_miles DOUBLE
        )
        """
    )
    conn.execute(
        """
        INSERT INTO gold_dws_daily_trip_summary VALUES
        ('2026-01-01', 10, 100.0, 30.5),
        ('2026-01-02', 20, 250.0, 70.0)
        """
    )
    yield conn
    conn.close()


def test_sql_static_must_run_before_sample_run(tmp_path):
    """SQL 含 CREATE 时必须静态 FAIL，不能进入 sample run 并伪装通过。"""
    package_dir = _build_package(tmp_path)
    sql_path = package_dir / "sql" / "main.sql"
    sql_path.write_text("CREATE TABLE bad AS SELECT 1", encoding="utf-8")

    result = verify_review_package(package_dir, no_sql_run=False)

    assert result.sql_static_status == "FAIL"
    assert result.sql_sample_status in {"SKIPPED", "PENDING"}
    assert result.overall_status == "FAIL"


def test_sql_forbidden_keywords_fail():
    """CREATE/INSERT/DROP 都必须被 Validator 拦截。"""
    validator = Validator()
    for sql in [
        "CREATE TABLE t AS SELECT 1",
        "INSERT INTO t VALUES (1)",
        "DROP TABLE t",
    ]:
        report = validator.validate_static(sql=sql, spark_code="", lineage={})
        assert report.overall_status == ValidationStatus.FAILED


def test_unknown_sql_field_warn_or_fail(tmp_path):
    """SQL 引用 lineage 未声明字段不能静默 PASS。"""
    package_dir = _build_package(tmp_path)
    sql_path = package_dir / "sql" / "main.sql"
    sql_path.write_text(
        "SELECT trip_date, unknown_metric FROM gold.dws_daily_trip_summary",
        encoding="utf-8",
    )

    result = verify_review_package(package_dir, no_sql_run=True)

    assert result.sql_static_status in {"WARN", "FAIL"}
    assert result.sql_static_status != "PASS"


def test_legal_select_can_sample_run_with_sample_data(tmp_path, sample_conn):
    """合法 SELECT 在有 sample 数据时可以 sample run。"""
    package_dir = _build_package(tmp_path)
    # 测试库不支持 schema 名，这里只替换 Review Package 草案中的表名。
    sql_path = package_dir / "sql" / "main.sql"
    sql_path.write_text(
        sql_path.read_text(encoding="utf-8").replace(
            "gold.dws_daily_trip_summary",
            "gold_dws_daily_trip_summary",
        ),
        encoding="utf-8",
    )
    lineage_path = package_dir / "lineage" / "source_refs.yml"
    lineage_path.write_text(
        lineage_path.read_text(encoding="utf-8").replace(
            "gold.dws_daily_trip_summary",
            "gold_dws_daily_trip_summary",
        ),
        encoding="utf-8",
    )

    result = verify_review_package(package_dir, conn=sample_conn)

    assert result.sql_static_status in {"PASS", "WARN"}
    assert result.sql_sample_status == "PASS"


def test_no_sample_data_is_skipped_or_pending(tmp_path):
    """没有 sample 数据源时 SQL sample run 不能 PASS。"""
    package_dir = _build_package(tmp_path)
    result = verify_review_package(package_dir)

    assert result.sql_sample_status in {"SKIPPED", "PENDING"}
    assert result.sql_sample_status != "PASS"


def test_spark_unavailable_is_skipped_or_pending(tmp_path):
    """Spark 不可用时不能伪装 PASS。"""
    package_dir = _build_package(tmp_path)
    result = verify_review_package(package_dir)

    assert result.spark_sample_status in {"SKIPPED", "PENDING"}
    assert result.spark_sample_status != "PASS"


def test_spark_forbidden_patterns_fail():
    """Spark 写入动作必须 FAIL——AST 分析器准确识别真实写入操作。"""
    validator = Validator()
    # 真实写入操作必须 FAIL
    for spark_code in [
        "df.write.mode('overwrite').save('gold.t')",
        "df.saveAsTable('gold.t')",
        "df.write.insertInto('gold.t')",
        "df.write.save('path')",
        "df.write.parquet('path')",
        "df.write.csv('path')",
    ]:
        report = validator.validate_static(sql="SELECT 1", spark_code=spark_code, lineage={})
        assert report.overall_status == ValidationStatus.FAILED, f"应拒绝: {spark_code}"
    # mode('overwrite') 仅设置写入模式，不含实际写入调用——不应误报
    # （AST 分析器正确处理字符串字面量）
    for safe_code in [
        "df.mode('overwrite')",
    ]:
        report = validator.validate_static(sql="SELECT 1", spark_code=safe_code, lineage={})
        assert report.overall_status != ValidationStatus.FAILED, f"不应拒绝: {safe_code}"


def test_cross_validation_passes_for_matching_results():
    """SQL/Spark 列名、行数、抽样行一致时可通过。"""
    sql_result = SQLResult(
        sql="SELECT 1",
        columns=["trip_date", "trip_count"],
        rows=[("2026-01-01", 10)],
        row_count=1,
    )
    spark_result = SQLResult(
        sql="spark",
        columns=["trip_date", "trip_count"],
        rows=[("2026-01-01", 10)],
        row_count=1,
    )
    result = compare_results(sql_result, spark_result)
    assert result.status == CrossValidateStatus.CONSISTENT_SAMPLE


def test_cross_validation_warns_for_column_row_or_sample_diff():
    """列名、行数、抽样行不一致都应进入 WARN/INCONSISTENT。"""
    base = SQLResult(sql="sql", columns=["a"], rows=[(1,)], row_count=1)
    cases = [
        SQLResult(sql="spark", columns=["b"], rows=[(1,)], row_count=1),
        SQLResult(sql="spark", columns=["a"], rows=[(1,), (2,)], row_count=2),
        SQLResult(sql="spark", columns=["a"], rows=[(2,)], row_count=1),
    ]
    for spark_result in cases:
        result = compare_results(base, spark_result)
        assert result.status == CrossValidateStatus.INCONSISTENT


def test_cross_validation_skips_when_spark_missing_or_sql_failed():
    """Spark 缺失或 SQL 失败时交叉验证不能 PASS。"""
    missing_spark = compare_results(SQLResult(sql="SELECT 1", row_count=1), None)
    failed_sql = compare_results(
        SQLResult(sql="SELECT bad", error="binder error"),
        SQLResult(sql="spark", row_count=1),
    )

    assert missing_spark.status == CrossValidateStatus.NOT_EXECUTED
    assert failed_sql.status == CrossValidateStatus.NOT_EXECUTED


def test_verification_reports_written_and_decision_not_approved(tmp_path):
    """M3 必须写报告，decision.md 当前状态仍待人审。"""
    package_dir = _build_package(tmp_path)
    result = verify_review_package(package_dir)

    assert Path(result.verification_report_path).is_file()
    assert Path(result.cross_validation_report_path).is_file()
    decision = (package_dir / "decision.md").read_text(encoding="utf-8")
    assert "当前状态：PENDING_REVIEW" in decision
    assert "当前状态：APPROVED" not in decision


def test_verify_cli_outputs_report_paths(tmp_path):
    """验证 CLI 只做验证并输出两个报告路径。"""
    package_dir = _build_package(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(VERIFY_CLI),
            "-p",
            str(package_dir),
            "--no-sql-run",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "verification.md" in result.stdout
    assert "cross_validation.md" in result.stdout
    assert "Overall Status:" in result.stdout
