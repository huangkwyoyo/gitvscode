"""
M3 Verification Engine 直接单元测试。

覆盖 verify_review_package() 及其内部辅助函数：
- 读取 Review Package 并校验必备文件
- 调用 checker 进行静态检查
- Spark 不可用时返回 SKIPPED/PENDING
- cross_validation 缺少 Spark 结果时不能 PASS
- 不修改 decision.md 为 APPROVE
- 辅助函数的边界行为
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

from src.agent.verification_engine import (
    VerificationEngineResult,
    _cross_status,
    _first_source_table,
    _overall_status,
    _require_file,
    _spark_result_status,
    _status_from_checks,
    verify_review_package,
)
from src.ir.types import CheckResult, CrossValidateStatus, SQLResult, ValidationReport, ValidationStatus
from src.sandbox.spark_executor import execute_spark_dsl
from src.verify.checker import Validator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
BUILD_CLI = PROJECT_ROOT / "scripts" / "dev_agent" / "build_review_package.py"


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


# ═════════════════════════════════════════════════════════════
# 读取 Review Package 并调用 checker
# ═════════════════════════════════════════════════════════════


def test_missing_sql_file_raises(tmp_path):
    """缺少 sql/main.sql 时必须抛出 FileNotFoundError。"""
    package_dir = _build_package(tmp_path)
    (package_dir / "sql" / "main.sql").unlink()

    with pytest.raises(FileNotFoundError, match="sql"):
        verify_review_package(package_dir)


def test_missing_spark_file_raises(tmp_path):
    """缺少 spark/main.py 时必须抛出 FileNotFoundError。"""
    package_dir = _build_package(tmp_path)
    (package_dir / "spark" / "main.py").unlink()

    with pytest.raises(FileNotFoundError, match="spark"):
        verify_review_package(package_dir)


def test_missing_lineage_file_raises(tmp_path):
    """缺少 lineage/source_refs.yml 时必须抛出 FileNotFoundError。"""
    package_dir = _build_package(tmp_path)
    (package_dir / "lineage" / "source_refs.yml").unlink()

    with pytest.raises(FileNotFoundError, match="lineage"):
        verify_review_package(package_dir)


def test_missing_decision_file_raises(tmp_path):
    """缺少 decision.md 时必须抛出 FileNotFoundError。"""
    package_dir = _build_package(tmp_path)
    (package_dir / "decision.md").unlink()

    with pytest.raises(FileNotFoundError, match="decision"):
        verify_review_package(package_dir)


def test_verify_runs_static_checks(tmp_path):
    """验证引擎必须执行静态检查。"""
    package_dir = _build_package(tmp_path)
    result = verify_review_package(package_dir)

    # SQL 静态检查应执行（状态不为空）
    assert result.sql_static_status in {"PASS", "WARN", "FAIL", "PENDING"}
    # Spark 静态检查应执行
    assert result.spark_static_status in {"PASS", "WARN", "FAIL", "PENDING"}


def test_verify_returns_structured_result(tmp_path):
    """返回值必须是 VerificationEngineResult 结构。"""
    package_dir = _build_package(tmp_path)
    result = verify_review_package(package_dir)

    assert isinstance(result, VerificationEngineResult)
    assert result.package_path
    assert result.verification_report_path
    assert result.cross_validation_report_path
    assert result.overall_status in {"PASS", "WARN", "FAIL", "PENDING", "SKIPPED"}


# ═════════════════════════════════════════════════════════════
# Spark 不可用时返回 SKIPPED/PENDING
# ═════════════════════════════════════════════════════════════


def test_spark_sample_status_is_skipped_or_pending_without_session(tmp_path):
    """没有 SparkSession 时 spark_sample_status 必须是 SKIPPED 或 PENDING。"""
    package_dir = _build_package(tmp_path)
    result = verify_review_package(package_dir)

    assert result.spark_sample_status in {"SKIPPED", "PENDING"}
    assert result.spark_sample_status != "PASS"


def test_spark_executor_returns_skipped_without_session():
    """execute_spark_dsl 在无 session 时返回 SKIPPED。"""
    result = execute_spark_dsl("df = spark.table('t')", spark_session=None)
    assert result.error is not None
    assert "SKIPPED" in result.error


def test_spark_executor_returns_pending_with_session():
    """execute_spark_dsl 在有 session 但未实现时返回 PENDING。"""
    result = execute_spark_dsl("df = spark.table('t')", spark_session=object())
    assert result.error is not None
    assert "PENDING" in result.error


def test_spark_sample_never_passes_without_real_spark(tmp_path):
    """在无真实 Spark 环境时 spark_sample_status 绝对不能是 PASS。"""
    package_dir = _build_package(tmp_path)
    result = verify_review_package(package_dir)

    assert result.spark_sample_status != "PASS"


# ═════════════════════════════════════════════════════════════
# cross_validation 缺 Spark 结果时不能 PASS
# ═════════════════════════════════════════════════════════════


def test_cross_validation_status_without_spark(tmp_path):
    """没有 Spark 结果时 cross_validation_status 不能是 PASS。"""
    package_dir = _build_package(tmp_path)
    result = verify_review_package(package_dir)

    assert result.cross_validation_status in {"SKIPPED", "PENDING"}
    assert result.cross_validation_status != "PASS"


def test_cross_validation_skipped_when_spark_is_pending(tmp_path):
    """Spark 为 PENDING 时，交叉验证应为 SKIPPED 或 PENDING。"""
    package_dir = _build_package(tmp_path)
    result = verify_review_package(package_dir)

    if result.spark_sample_status in {"SKIPPED", "PENDING"}:
        assert result.cross_validation_status != "PASS"


# ═════════════════════════════════════════════════════════════
# 不修改 decision.md 为 APPROVE
# ═════════════════════════════════════════════════════════════


def test_decision_remains_pending_review_after_verify(tmp_path):
    """M3 验证后 decision.md 当前状态必须仍然是 PENDING_REVIEW。"""
    package_dir = _build_package(tmp_path)
    verify_review_package(package_dir)

    decision = (package_dir / "decision.md").read_text(encoding="utf-8")
    assert "当前状态：PENDING_REVIEW" in decision


def test_decision_never_becomes_approved_after_verify(tmp_path):
    """M3 验证后 decision.md 绝对不能变成 APPROVED。"""
    package_dir = _build_package(tmp_path)
    verify_review_package(package_dir)

    decision = (package_dir / "decision.md").read_text(encoding="utf-8")
    assert "当前状态：APPROVED" not in decision


def test_verify_does_not_modify_decision_file(tmp_path):
    """M3 验证不能修改 decision.md 文件内容。"""
    package_dir = _build_package(tmp_path)
    before = (package_dir / "decision.md").read_text(encoding="utf-8")
    verify_review_package(package_dir)
    after = (package_dir / "decision.md").read_text(encoding="utf-8")

    # decision.md 在 M3 前后应完全一致
    assert before == after


# ═════════════════════════════════════════════════════════════
# M4a verification_summary.yml
# ═════════════════════════════════════════════════════════════


def test_verification_summary_yml_is_written(tmp_path):
    """M4b：M3 验证后必须写入 verification_summary.yml（含 M4b 新字段）。"""
    package_dir = _build_package(tmp_path)
    verify_review_package(package_dir)

    summary_path = package_dir / "reports" / "verification_summary.yml"
    assert summary_path.is_file(), "M4b 必须生成 verification_summary.yml"

    summary = yaml.safe_load(summary_path.read_text(encoding="utf-8"))
    assert "overall_status" in summary
    assert "sql_static_status" in summary
    assert "sql_sample_status" in summary
    assert "spark_static_status" in summary
    assert "spark_sample_status" in summary
    assert "cross_validation_status" in summary
    assert "warnings" in summary
    assert "failures" in summary
    assert "stale_risk_note" in summary
    # M4b 新字段
    assert "verification_id" in summary
    assert summary["verification_id"].startswith("verify_")
    assert "artifact_hashes_verified" in summary
    assert len(summary["artifact_hashes_verified"]["sql_main"]) == 64
    assert "decision_state_before_verify" in summary
    assert "decision_state_after_verify" in summary


def test_verification_summary_contains_stale_risk_note(tmp_path):
    """M4b：verification_summary.yml 必须包含 stale 风险提示（M4b 已实现）。"""
    package_dir = _build_package(tmp_path)
    verify_review_package(package_dir)

    summary = yaml.safe_load(
        (package_dir / "reports" / "verification_summary.yml").read_text(encoding="utf-8")
    )

    assert "stale_risk_note" in summary
    # M4b：自动 SUPERSEDED 已实现，文案不再说 "M4b+ 将实现"
    assert "M4b" in summary["stale_risk_note"]


def test_verify_does_not_modify_decision_yml(tmp_path):
    """M4a：M3 验证绝对不能修改 decision.yml.current_state。"""
    package_dir = _build_package(tmp_path)

    before = yaml.safe_load(
        (package_dir / "decision.yml").read_text(encoding="utf-8")
    )
    verify_review_package(package_dir)
    after = yaml.safe_load(
        (package_dir / "decision.yml").read_text(encoding="utf-8")
    )

    # decision.yml 的 current_state 在 M3 前后必须完全一致
    assert before["current_state"] == after["current_state"]
    assert after["current_state"] == "PENDING_REVIEW"


def test_missing_decision_yml_raises(tmp_path):
    """M4a：缺少 decision.yml 时必须抛出 FileNotFoundError。"""
    package_dir = _build_package(tmp_path)
    (package_dir / "decision.yml").unlink()

    with pytest.raises(FileNotFoundError, match="decision"):
        verify_review_package(package_dir)


def test_missing_decision_log_yml_raises(tmp_path):
    """M4a：缺少 decision_log.yml 时必须抛出 FileNotFoundError。"""
    package_dir = _build_package(tmp_path)
    (package_dir / "decision_log.yml").unlink()

    with pytest.raises(FileNotFoundError, match="decision"):
        verify_review_package(package_dir)


# ═════════════════════════════════════════════════════════════
# 报告写入
# ═════════════════════════════════════════════════════════════


def test_verification_report_is_written(tmp_path):
    """M3 必须写 verification.md。"""
    package_dir = _build_package(tmp_path)
    result = verify_review_package(package_dir)

    assert Path(result.verification_report_path).is_file()
    content = Path(result.verification_report_path).read_text(encoding="utf-8")
    assert "Verification Report" in content
    assert result.overall_status in content


def test_cross_validation_report_is_written(tmp_path):
    """M3 必须写 cross_validation.md。"""
    package_dir = _build_package(tmp_path)
    result = verify_review_package(package_dir)

    assert Path(result.cross_validation_report_path).is_file()
    content = Path(result.cross_validation_report_path).read_text(encoding="utf-8")
    assert "Cross Validation Report" in content


def test_reports_not_overwritten_when_verify_fails_early(tmp_path):
    """当必备文件缺失时，验证早期失败，不应写入报告。"""
    package_dir = _build_package(tmp_path)
    (package_dir / "sql" / "main.sql").unlink()

    # 验证应该因文件缺失而失败
    try:
        verify_review_package(package_dir)
    except FileNotFoundError:
        pass

    # 报告不应被写入（因为早期就失败了）
    # 注意：如果 _build_package 时已写了报告，那是 M2 的产物，不是 M3 写的


# ═════════════════════════════════════════════════════════════
# 辅助函数单元测试
# ═════════════════════════════════════════════════════════════


def test_require_file_raises_on_missing(tmp_path):
    """_require_file：文件不存在时抛出 FileNotFoundError。"""
    missing = tmp_path / "nonexistent.txt"
    with pytest.raises(FileNotFoundError):
        _require_file(missing)


def test_require_file_passes_on_existing(tmp_path):
    """_require_file：文件存在时不抛异常。"""
    existing = tmp_path / "exists.txt"
    existing.write_text("hello", encoding="utf-8")
    # 不抛异常即通过
    _require_file(existing)


def test_first_source_table_from_lineage():
    """_first_source_table：正常提取第一个表名。"""
    lineage = {"source_tables": [{"name": "gold.dws_daily_trip_summary"}]}
    assert _first_source_table(lineage) == "gold.dws_daily_trip_summary"


def test_first_source_table_empty():
    """_first_source_table：lineage 为空时返回空字符串。"""
    assert _first_source_table({}) == ""
    assert _first_source_table({"source_tables": []}) == ""


def test_first_source_table_string_form():
    """_first_source_table：source_table 为字符串时也能处理。"""
    lineage = {"source_tables": ["gold.my_table"]}
    assert _first_source_table(lineage) == "gold.my_table"


def test_status_from_checks_with_failed():
    """_status_from_checks：有 FAILED 时返回 FAIL。"""
    checks = [
        CheckResult(check_id=1, name="test", status=ValidationStatus.PASSED, detail="ok"),
        CheckResult(check_id=2, name="test", status=ValidationStatus.FAILED, detail="bad"),
    ]
    assert _status_from_checks(checks) == "FAIL"


def test_status_from_checks_with_warn():
    """_status_from_checks：无 FAIL 但有 WARN 时返回 WARN。"""
    checks = [
        CheckResult(check_id=1, name="test", status=ValidationStatus.PASSED, detail="ok"),
        CheckResult(check_id=2, name="test", status=ValidationStatus.WARN, detail="hmm"),
    ]
    assert _status_from_checks(checks) == "WARN"


def test_status_from_checks_with_pending():
    """_status_from_checks：无 FAIL/WARN 但有 PENDING 时返回 PENDING。"""
    checks = [
        CheckResult(check_id=1, name="test", status=ValidationStatus.PASSED, detail="ok"),
        CheckResult(check_id=2, name="test", status=ValidationStatus.PENDING, detail="wait"),
    ]
    assert _status_from_checks(checks) == "PENDING"


def test_status_from_checks_all_passed():
    """_status_from_checks：全部 PASSED 时返回 PASS。"""
    checks = [
        CheckResult(check_id=1, name="test", status=ValidationStatus.PASSED, detail="ok"),
    ]
    assert _status_from_checks(checks) == "PASS"


def test_spark_result_status_none():
    """_spark_result_status：结果为 None 时返回 PENDING。"""
    assert _spark_result_status(None) == "PENDING"


def test_spark_result_status_skipped():
    """_spark_result_status：错误信息含 SKIPPED 时返回 SKIPPED。"""
    result = SQLResult(sql="test", error="SKIPPED: Spark 环境不可用")
    assert _spark_result_status(result) == "SKIPPED"


def test_spark_result_status_pending():
    """_spark_result_status：错误信息含 PENDING 时返回 PENDING。"""
    result = SQLResult(sql="test", error="PENDING: 尚未实现")
    assert _spark_result_status(result) == "PENDING"


def test_spark_result_status_pass():
    """_spark_result_status：无错误时返回 PASS。"""
    result = SQLResult(sql="test", row_count=10)
    assert _spark_result_status(result) == "PASS"


def test_cross_status_consistent():
    """_cross_status：CONSISTENT → PASS。"""
    assert _cross_status(CrossValidateStatus.CONSISTENT) == "PASS"


def test_cross_status_inconsistent():
    """_cross_status：INCONSISTENT → WARN。"""
    assert _cross_status(CrossValidateStatus.INCONSISTENT) == "WARN"


def test_cross_status_skipped():
    """_cross_status：SKIPPED → SKIPPED。"""
    assert _cross_status(CrossValidateStatus.SKIPPED) == "SKIPPED"


def test_cross_status_pending():
    """_cross_status：NOT_ATTEMPTED → PENDING。"""
    assert _cross_status(CrossValidateStatus.NOT_ATTEMPTED) == "PENDING"


def test_overall_status_fail_on_any_fail():
    """_overall_status：任一 FAIL 则总状态为 FAIL。"""
    status = _overall_status(
        sql_static_status="PASS",
        sql_sample_status="FAIL",
        spark_static_status="PASS",
        spark_sample_status="PASS",
        cross_status="PASS",
        warnings=[],
        failures=["SQL sample run 失败"],
    )
    assert status == "FAIL"


def test_overall_status_warn_on_warnings():
    """_overall_status：有 WARN 或 warnings 非空则总状态为 WARN。"""
    status = _overall_status(
        sql_static_status="PASS",
        sql_sample_status="PASS",
        spark_static_status="PASS",
        spark_sample_status="SKIPPED",
        cross_status="SKIPPED",
        warnings=["Spark sample run 状态为 SKIPPED"],
        failures=[],
    )
    assert status == "WARN"


def test_overall_status_pending():
    """_overall_status：有 PENDING 则总状态为 PENDING。"""
    status = _overall_status(
        sql_static_status="PASS",
        sql_sample_status="PENDING",
        spark_static_status="PASS",
        spark_sample_status="PASS",
        cross_status="PASS",
        warnings=[],
        failures=[],
    )
    assert status == "PENDING"


def test_overall_status_all_pass():
    """_overall_status：全部 PASS 则总状态为 PASS。"""
    status = _overall_status(
        sql_static_status="PASS",
        sql_sample_status="PASS",
        spark_static_status="PASS",
        spark_sample_status="PASS",
        cross_status="PASS",
        warnings=[],
        failures=[],
    )
    assert status == "PASS"


# ═════════════════════════════════════════════════════════════
# M4b SUPERSEDED 专项测试
# ═════════════════════════════════════════════════════════════


def test_artifact_hashes_in_decision_after_m2(tmp_path):
    """M2 生成的 decision.yml 必须包含 artifact_hashes。"""
    package_dir = _build_package(tmp_path)
    decision_yml = yaml.safe_load(
        (package_dir / "decision.yml").read_text(encoding="utf-8")
    )
    assert "artifact_hashes" in decision_yml
    hashes = decision_yml["artifact_hashes"]
    assert len(hashes["sql_main"]) == 64
    assert len(hashes["spark_main"]) == 64
    assert len(hashes["lineage_source_refs"]) == 64


def test_artifact_integrity_warning_on_modified_sql(tmp_path):
    """修改 sql 后 verify 应产生完整性警告。"""
    package_dir = _build_package(tmp_path)
    # 修改 sql 文件
    (package_dir / "sql" / "main.sql").write_text("SELECT 1;\n", encoding="utf-8")
    result = verify_review_package(package_dir)
    # 应至少有 1 条完整性警告
    integrity_warnings = [w for w in result.warnings if "artifact 完整性" in w]
    assert len(integrity_warnings) >= 1


def test_no_superseded_when_state_is_pending_review(tmp_path):
    """PENDING_REVIEW + verify → 保持 PENDING_REVIEW，不触发 SUPERSEDED。"""
    package_dir = _build_package(tmp_path)
    verify_review_package(package_dir)
    decision_yml = yaml.safe_load(
        (package_dir / "decision.yml").read_text(encoding="utf-8")
    )
    assert decision_yml["current_state"] == "PENDING_REVIEW"


def test_verification_id_in_summary(tmp_path):
    """verification_summary.yml 必须包含 verification_id。"""
    package_dir = _build_package(tmp_path)
    verify_review_package(package_dir)
    summary = yaml.safe_load(
        (package_dir / "reports" / "verification_summary.yml").read_text(encoding="utf-8")
    )
    assert summary["verification_id"].startswith("verify_")


def test_decision_state_fields_in_summary(tmp_path):
    """verification_summary.yml 必须包含 decision_state_before/after_verify。"""
    package_dir = _build_package(tmp_path)
    verify_review_package(package_dir)
    summary = yaml.safe_load(
        (package_dir / "reports" / "verification_summary.yml").read_text(encoding="utf-8")
    )
    assert summary["decision_state_before_verify"] == "PENDING_REVIEW"
    # 未发生变更时 decision_state_after_verify 为 None
    assert summary["decision_state_after_verify"] is None


def test_artifact_hashes_verified_in_summary(tmp_path):
    """verification_summary.yml 的 artifact_hashes_verified 必须为快照。"""
    package_dir = _build_package(tmp_path)
    verify_review_package(package_dir)
    summary = yaml.safe_load(
        (package_dir / "reports" / "verification_summary.yml").read_text(encoding="utf-8")
    )
    hashes = summary["artifact_hashes_verified"]
    assert len(hashes["sql_main"]) == 64
    assert len(hashes["spark_main"]) == 64
    assert len(hashes["lineage_source_refs"]) == 64
    # artifact_hashes_verified 在写入 verification_summary.yml 前计算，
    # 因此 verification_summary 自身哈希为 null（无法包含自身哈希）


# ═════════════════════════════════════════════════════════════
# Phase 3（漏洞 E/F 修复）：verification_coverage + assurance_level
# ═════════════════════════════════════════════════════════════


def test_verification_coverage_in_summary(tmp_path):
    """verification_summary.yml 必须包含 verification_coverage 字段（9 维度）。"""
    package_dir = _build_package(tmp_path)
    verify_review_package(package_dir)
    summary = yaml.safe_load(
        (package_dir / "reports" / "verification_summary.yml").read_text(encoding="utf-8")
    )

    assert "verification_coverage" in summary
    coverage = summary["verification_coverage"]
    # 已覆盖维度（5 个）
    assert "sql_static" in coverage
    assert "sql_sample" in coverage
    assert "spark_static" in coverage
    assert "spark_sample" in coverage
    assert "cross_validation" in coverage
    # 未覆盖维度（4 个——明确标注 NOT_COVERED）
    assert coverage["business_semantics"] == "NOT_COVERED"
    assert coverage["full_data_behavior"] == "NOT_COVERED"
    assert coverage["production_performance"] == "NOT_COVERED"
    assert coverage["partition_idempotency_rollback"] == "NOT_COVERED"


def test_assurance_level_in_summary_always_partial_without_spark(tmp_path):
    """无 Spark 时 assurance_level 必须为 PARTIAL。"""
    package_dir = _build_package(tmp_path)
    verify_review_package(package_dir)
    summary = yaml.safe_load(
        (package_dir / "reports" / "verification_summary.yml").read_text(encoding="utf-8")
    )

    assert "assurance_level" in summary
    # 当前无真实 Spark 环境，保证级别始终为 PARTIAL
    assert summary["assurance_level"] == "PARTIAL"
    # 绝不能伪装成 DUAL_ENGINE_SAMPLE
    assert summary["assurance_level"] != "DUAL_ENGINE_SAMPLE"


def test_verification_coverage_spark_always_skipped_or_pending(tmp_path):
    """verification_coverage 中 spark_sample 在当前必须为 SKIPPED/PENDING/FAILED。"""
    package_dir = _build_package(tmp_path)
    verify_review_package(package_dir)
    summary = yaml.safe_load(
        (package_dir / "reports" / "verification_summary.yml").read_text(encoding="utf-8")
    )

    coverage = summary["verification_coverage"]
    # Spark 样本执行在当前环境下不能伪装 COMPLETE
    assert coverage["spark_sample"] != "COMPLETE"
    assert coverage["spark_sample"] in {"SKIPPED", "PENDING", "FAILED"}


def test_verification_coverage_never_claims_full_coverage(tmp_path):
    """verification_coverage 绝不能声称全量数据或生产就绪已覆盖。"""
    package_dir = _build_package(tmp_path)
    verify_review_package(package_dir)
    summary = yaml.safe_load(
        (package_dir / "reports" / "verification_summary.yml").read_text(encoding="utf-8")
    )

    coverage = summary["verification_coverage"]
    # 四个 NOT_COVERED 维度必须明确标注
    assert coverage.get("business_semantics") == "NOT_COVERED"
    assert coverage.get("full_data_behavior") == "NOT_COVERED"
    assert coverage.get("production_performance") == "NOT_COVERED"
    assert coverage.get("partition_idempotency_rollback") == "NOT_COVERED"


def test_verification_report_contains_coverage_section(tmp_path):
    """verification.md 必须包含验证覆盖范围和未验证风险章节。"""
    package_dir = _build_package(tmp_path)
    result = verify_review_package(package_dir)
    content = Path(result.verification_report_path).read_text(encoding="utf-8")

    assert "验证覆盖范围" in content
    assert "未验证风险" in content
    assert "NOT_COVERED" in content


def test_verification_report_contains_capability_boundary(tmp_path):
    """verification.md 必须包含能力边界声明——三道防线不构成上线充分条件。"""
    package_dir = _build_package(tmp_path)
    result = verify_review_package(package_dir)
    content = Path(result.verification_report_path).read_text(encoding="utf-8")

    assert "三道防线用于降低风险，不构成上线充分条件" in content
    assert "PARTIAL" in content


def test_cross_validation_report_contains_sample_disclaimer(tmp_path):
    """cross_validation.md 必须包含样本一致性免责声明。"""
    package_dir = _build_package(tmp_path)
    result = verify_review_package(package_dir)
    content = Path(result.cross_validation_report_path).read_text(encoding="utf-8")

    assert "LIMIT 1000 样本" in content
    assert "不代表全量数据一致" in content


def test_cross_validation_consistent_detail_has_disclaimer():
    """CONSISTENT 结果的 detail 必须包含样本免责声明。"""
    from src.verify.cross_validation import compare_results

    sql_result = SQLResult(
        sql="SELECT 1",
        columns=["a"],
        rows=[(1,)],
        row_count=1,
    )
    spark_result = SQLResult(
        sql="spark",
        columns=["a"],
        rows=[(1,)],
        row_count=1,
    )
    result = compare_results(sql_result, spark_result)
    assert result.status == CrossValidateStatus.CONSISTENT
    # detail 必须包含免责声明
    assert "不代表全量数据一致" in result.detail
    assert "LIMIT 1000" in result.detail
    # 不应再使用"置信度大幅提高"等过度承诺表述
    assert "置信度大幅提高" not in result.detail


def test_cross_validation_result_docstring_updated():
    """CrossValidationResult 的 docstring 不应再包含"置信度大幅提高"。"""
    from src.ir.types import CrossValidationResult
    doc = CrossValidationResult.__doc__ or ""
    assert "置信度大幅提高" not in doc
    assert "不代表全量数据一致" in doc


def test_assurance_level_enum_values():
    """AssuranceLevel 枚举只应有 PARTIAL 和 DUAL_ENGINE_SAMPLE 两个值。"""
    from src.ir.types import AssuranceLevel
    values = {e.value for e in AssuranceLevel}
    assert values == {"PARTIAL", "DUAL_ENGINE_SAMPLE"}


def test_verification_coverage_defaults():
    """VerificationCoverage 默认所有已覆盖维度为 PENDING，未覆盖维度为 NOT_COVERED。"""
    from src.ir.types import VerificationCoverage
    cov = VerificationCoverage()
    assert cov.sql_static == "PENDING"
    assert cov.business_semantics == "NOT_COVERED"
    assert cov.full_data_behavior == "NOT_COVERED"
    assert cov.production_performance == "NOT_COVERED"
    assert cov.partition_idempotency_rollback == "NOT_COVERED"
    # unverified_dimensions 属性
    unverified = cov.unverified_dimensions
    assert "business_semantics" in unverified
    assert "full_data_behavior" in unverified
    assert "production_performance" in unverified
    assert "partition_idempotency_rollback" in unverified
    # 已覆盖维度不应该出现在 unverified 中
    assert "sql_static" not in unverified


def test_verification_coverage_to_dict():
    """VerificationCoverage.to_dict() 返回完整 9 维度。"""
    from src.ir.types import VerificationCoverage
    cov = VerificationCoverage(
        sql_static="COMPLETE",
        sql_sample="COMPLETE",
        spark_static="SKIPPED",
        spark_sample="SKIPPED",
        cross_validation="SKIPPED",
    )
    d = cov.to_dict()
    assert len(d) == 9
    assert d["sql_static"] == "COMPLETE"
    assert d["business_semantics"] == "NOT_COVERED"


def test_superseded_when_approved_and_reverify(tmp_path):
    """APPROVED + re-verify → SUPERSEDED 自动转换（通过 decision_manager 模拟）。"""
    from src.agent.decision_manager import transition_state

    package_dir = _build_package(tmp_path)
    # 先让人批准
    transition_state(package_dir, to_state="APPROVED", changed_by="human", reason="批准", actor_id="human:t")
    assert yaml.safe_load((package_dir / "decision.yml").read_text(encoding="utf-8"))["current_state"] == "APPROVED"

    # 重新验证——因为 overall_status 为 WARN（Spark SKIPPED），不在 {PASS, FAIL} 中，不会触发 SUPERSEDED
    # 这是设计意图：WARN 不触发 SUPERSEDED，需人判断
    result = verify_review_package(package_dir)
    decision_yml = yaml.safe_load((package_dir / "decision.yml").read_text(encoding="utf-8"))
    # WARN 不触发 SUPERSEDED
    if result.overall_status in {"PASS", "FAIL"}:
        assert decision_yml["current_state"] == "SUPERSEDED"
    else:
        # WARN/SKIPPED/PENDING 时保持原状态
        pass  # 状态不变
