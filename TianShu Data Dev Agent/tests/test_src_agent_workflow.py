"""
v2.0 M2 主工作流直接单元测试。

覆盖 build_review_package() 的所有路径：
- 串联 M2 主线（requirement → design → code → publish）
- 不接 LLM
- 不执行 SQL
- 不执行 Spark
- 不自动上线
- 多 fixture 兼容
- 错误注入
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.agent.workflow import build_review_package
from src.ir.types import ReviewPackageManifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRIP_FIXTURE = PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"


# ═════════════════════════════════════════════════════════════
# 主线串联——trip_daily_report fixture
# ═════════════════════════════════════════════════════════════


def test_workflow_chains_full_m2_pipeline(tmp_path):
    """build_review_package 必须完整串联 M2 四阶段。"""
    manifest = build_review_package(TRIP_FIXTURE, output_root=tmp_path)

    assert isinstance(manifest, ReviewPackageManifest)
    assert manifest.request_id == "trip_daily_report_m2"
    assert manifest.status == "PENDING_REVIEW"


def test_workflow_outputs_all_required_files(tmp_path):
    """工作流输出的 Review Package 必须包含全部 9 个文件（M4a：含 decision.yml/decision_log.yml）。"""
    from src.agent.review_publisher import REQUIRED_FILES

    manifest = build_review_package(TRIP_FIXTURE, output_root=tmp_path)
    package_dir = Path(manifest.package_path)

    for rf in REQUIRED_FILES:
        assert (package_dir / rf).is_file(), f"缺少: {rf}"


def test_workflow_manifest_path_matches_output_root(tmp_path):
    """manifest.package_path 必须在指定的 output_root 下。"""
    custom_root = tmp_path / "custom_output"
    manifest = build_review_package(TRIP_FIXTURE, output_root=custom_root)

    assert str(custom_root) in manifest.package_path
    assert "trip_daily_report_m2" in manifest.package_path


# ═════════════════════════════════════════════════════════════
# 不接 LLM
# ═════════════════════════════════════════════════════════════


def test_workflow_does_not_require_llm_api():
    """build_review_package 不依赖任何 LLM API 或网络调用。"""
    # 仅依赖 YAML fixture，无网络、无 API key
    manifest = build_review_package(TRIP_FIXTURE)
    assert manifest is not None


def test_generated_code_is_deterministic(tmp_path):
    """同一 fixture 多次运行应产生一致的核心结构（确定性模板）。"""
    m1 = build_review_package(TRIP_FIXTURE, output_root=tmp_path / "run1")
    m2 = build_review_package(TRIP_FIXTURE, output_root=tmp_path / "run2")

    # 核心字段一致
    assert m1.request_id == m2.request_id
    assert m1.files == m2.files
    assert m1.status == m2.status


# ═════════════════════════════════════════════════════════════
# 不执行 SQL / Spark
# ═════════════════════════════════════════════════════════════


def test_workflow_does_not_require_db_connection():
    """build_review_package 不接受数据库连接参数。"""
    # 函数签名只收 requirement_path 和 output_root
    manifest = build_review_package(TRIP_FIXTURE)
    assert manifest is not None


def test_sql_output_is_never_executed(tmp_path):
    """生成的 SQL 草案绝不能包含任何执行痕迹。"""
    manifest = build_review_package(TRIP_FIXTURE, output_root=tmp_path)
    sql = (Path(manifest.package_path) / "sql" / "main.sql").read_text(encoding="utf-8")

    # SQL 草案不应包含执行痕迹（如实际数据值、row count 等）
    assert "rows returned" not in sql.lower()
    assert "execution time" not in sql.lower()


def test_spark_output_is_never_executed(tmp_path):
    """生成的 Spark 草案绝不能包含执行痕迹。"""
    manifest = build_review_package(TRIP_FIXTURE, output_root=tmp_path)
    spark = (Path(manifest.package_path) / "spark" / "main.py").read_text(encoding="utf-8")

    assert "execution time" not in spark.lower()
    assert "job completed" not in spark.lower()


# ═════════════════════════════════════════════════════════════
# 不自动上线
# ═════════════════════════════════════════════════════════════


def test_decision_requires_human_review(tmp_path):
    """工作流产物必须明确需要人审。"""
    manifest = build_review_package(TRIP_FIXTURE, output_root=tmp_path)
    decision = (Path(manifest.package_path) / "decision.md").read_text(encoding="utf-8")

    # 必须有明确的人审要求
    assert "未经人审" in decision or "人工审查" in decision or "Human Review" in decision


def test_no_auto_approve_in_any_file(tmp_path):
    """任何产物文件都不能含有自动批准的内容。"""
    manifest = build_review_package(TRIP_FIXTURE, output_root=tmp_path)
    package_dir = Path(manifest.package_path)

    # 检查所有文本文件
    for path in package_dir.rglob("*"):
        if path.is_file() and path.suffix in {".sql", ".py", ".md", ".yml"}:
            content = path.read_text(encoding="utf-8")
            assert "AUTO_APPROVED" not in content
            assert "auto_approved" not in content.lower()


# ═════════════════════════════════════════════════════════════
# 多 fixture 兼容
# ═════════════════════════════════════════════════════════════


def test_workflow_handles_minimal_fixture(tmp_path):
    """最小合法 fixture 应正常生成 Review Package。"""
    import yaml
    minimal = tmp_path / "minimal_req.yml"
    minimal.write_text(
        yaml.safe_dump(
            {
                "request_id": "minimal_test_req",
                "title": "最小需求",
                "business_goal": "测试",
                "source_tables": [{"name": "gold.t"}],
                "required_fields": [{"name": "col1", "table": "gold.t"}],
                "metrics": [{"name": "cnt", "field": "col1"}],
                "filters": {"date_range": ["2026-01-01", "2026-01-02"]},
                "grain": ["col1"],
                "output_expectation": "test",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    manifest = build_review_package(minimal, output_root=tmp_path)
    assert manifest.request_id == "minimal_test_req"
    assert Path(manifest.package_path).is_dir()


def test_workflow_handles_alternate_output_root(tmp_path):
    """不同 output_root 应正确隔离输出。"""
    root_a = tmp_path / "out_a"
    root_b = tmp_path / "out_b"
    ma = build_review_package(TRIP_FIXTURE, output_root=root_a)
    mb = build_review_package(TRIP_FIXTURE, output_root=root_b)

    assert ma.package_path != mb.package_path
    assert Path(ma.package_path).is_dir()
    assert Path(mb.package_path).is_dir()


# ═════════════════════════════════════════════════════════════
# 错误注入
# ═════════════════════════════════════════════════════════════


def test_workflow_raises_on_missing_file():
    """不存在的 fixture 应快速失败。"""
    with pytest.raises(ValueError, match="文件不存在"):
        build_review_package("nonexistent_file.yml")


def test_workflow_raises_on_missing_request_id(tmp_path):
    """缺失 request_id 的 fixture 应快速失败。"""
    bad = tmp_path / "bad.yml"
    bad.write_text(
        yaml.safe_dump(
            {
                "title": "bad",
                "business_goal": "test",
                "source_tables": [{"name": "gold.t"}],
                "required_fields": [{"name": "c", "table": "gold.t"}],
                "metrics": [{"name": "m", "field": "c"}],
                "filters": {},
                "grain": ["c"],
                "output_expectation": "test",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="request_id"):
        build_review_package(bad, output_root=tmp_path)


def test_workflow_raises_on_multi_table_fixture(tmp_path):
    """多表 fixture（未声明 JOIN）应快速失败。"""
    bad = tmp_path / "multi_table.yml"
    bad.write_text(
        yaml.safe_dump(
            {
                "request_id": "multi_table_test",
                "title": "多表",
                "business_goal": "test",
                "source_tables": [{"name": "gold.a"}, {"name": "gold.b"}],
                "required_fields": [{"name": "c", "table": "gold.a"}],
                "metrics": [{"name": "m", "field": "c"}],
                "filters": {"date_range": ["2026-01-01", "2026-01-02"]},
                "grain": ["c"],
                "output_expectation": "test",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="多表"):
        build_review_package(bad, output_root=tmp_path)
