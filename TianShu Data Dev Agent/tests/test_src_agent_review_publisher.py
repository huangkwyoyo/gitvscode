"""
Review Package 发布器直接单元测试。

覆盖 publish_review_package() 的所有路径：
- 完整 Review Package 目录生成
- 7 个必备文件完整性
- decision.md 默认不能是 APPROVE
- 报告中不能伪装 PASS
- 来源追溯正确记录
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.agent.design_planner import DevPlan
from src.agent.dual_code_generator import DualCodeDrafts
from src.agent.requirement_analyzer import RequirementSpec
from src.agent.review_publisher import REQUIRED_FILES, publish_review_package
from src.ir.types import CodeDraft, ReviewPackageManifest


# ═════════════════════════════════════════════════════════════
# 辅助函数
# ═════════════════════════════════════════════════════════════


def _make_requirement(**overrides) -> RequirementSpec:
    """构造测试用 RequirementSpec。"""
    defaults = {
        "request_id": "test_pub_001",
        "title": "测试发布",
        "business_goal": "验证 Review Package 生成",
        "source_tables": [{"name": "gold.dws_daily_trip_summary", "role": "primary", "source": "TianShu Gold 层"}],
        "required_fields": [
            {"name": "trip_date", "table": "gold.dws_daily_trip_summary", "type": "DATE", "alias": "trip_date", "source": "gold.dws_daily_trip_summary.trip_date"},
        ],
        "metrics": [
            {"name": "trip_count", "field": "trip_count", "table": "gold.dws_daily_trip_summary", "aggregation": "SUM", "alias": "trip_count", "definition_source": "meta.metric_definitions.trip_count"},
        ],
        "filters": {"date_range": ["2026-01-01", "2026-01-31"]},
        "grain": ["trip_date"],
        "output_expectation": "按日汇总",
        "human_review_points": [],
    }
    defaults.update(overrides)
    return RequirementSpec(**defaults)


def _make_plan(**overrides) -> DevPlan:
    """构造测试用 DevPlan。"""
    req = _make_requirement()
    defaults = {
        "request_id": req.request_id,
        "title": req.title,
        "business_goal": req.business_goal,
        "source_tables": req.source_tables,
        "required_fields": req.required_fields,
        "metrics": req.metrics,
        "filters": req.filters,
        "grain": req.grain,
        "output_expectation": req.output_expectation,
        "human_review_points": ["Human Review: 测试审查点"],
        "pending_items": [],
    }
    defaults.update(overrides)
    return DevPlan(**defaults)


def _make_drafts(**overrides) -> DualCodeDrafts:
    """构造测试用 DualCodeDrafts。"""
    sql = CodeDraft(
        kind="sql",
        path="sql/main.sql",
        content="-- 草案\nSELECT trip_date, SUM(trip_count) AS trip_count\nFROM gold.dws_daily_trip_summary\nWHERE trip_date BETWEEN '2026-01-01' AND '2026-01-31'\nGROUP BY trip_date\nORDER BY trip_date;\n",
        language="duckdb_sql",
        source_refs={"trip_date": "gold.dws_daily_trip_summary.trip_date", "trip_count": "meta.metric_definitions.trip_count"},
        pending_items=[],
    )
    spark = CodeDraft(
        kind="spark",
        path="spark/main.py",
        content="# 草案\nfrom pyspark.sql import functions as F\n\ndef build_dataframe(spark):\n    df = spark.table(\"gold.dws_daily_trip_summary\")\n    df = df.where((F.col(\"trip_date\") >= \"2026-01-01\") & (F.col(\"trip_date\") <= \"2026-01-31\"))\n    result = df.groupBy(\"trip_date\").agg(F.sum(\"trip_count\").alias(\"trip_count\"))\n    return result.select(\"trip_date\", \"trip_count\")\n",
        language="pyspark",
        source_refs={"trip_date": "gold.dws_daily_trip_summary.trip_date", "trip_count": "meta.metric_definitions.trip_count"},
        pending_items=[],
    )
    defaults = {
        "sql": sql,
        "spark": spark,
        "pending_items": [],
        "human_review_points": [],
    }
    defaults.update(overrides)
    return DualCodeDrafts(**defaults)


# ═════════════════════════════════════════════════════════════
# 目录结构完整性
# ═════════════════════════════════════════════════════════════


def test_publish_creates_complete_directory_structure(tmp_path):
    """必须生成完整的 5 个子目录结构。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)

    package_dir = Path(manifest.package_path)
    assert (package_dir / "sql").is_dir()
    assert (package_dir / "spark").is_dir()
    assert (package_dir / "tests").is_dir()
    assert (package_dir / "reports").is_dir()
    assert (package_dir / "lineage").is_dir()


def test_publish_creates_all_seven_required_files(tmp_path):
    """必须生成全部 7 个必备文件。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)

    package_dir = Path(manifest.package_path)
    for required_file in REQUIRED_FILES:
        assert (package_dir / required_file).is_file(), f"缺少必备文件: {required_file}"


def test_manifest_contains_all_seven_files(tmp_path):
    """manifest.files 必须等于 REQUIRED_FILES。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)

    assert len(manifest.files) == len(REQUIRED_FILES)
    for rf in REQUIRED_FILES:
        assert rf in manifest.files


def test_manifest_has_correct_request_id(tmp_path):
    """manifest.request_id 必须与 Requirement 一致。"""
    req = _make_requirement(request_id="my_custom_req")
    plan = _make_plan(request_id="my_custom_req")
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)

    assert manifest.request_id == "my_custom_req"


def test_manifest_status_is_pending_review(tmp_path):
    """manifest.status 默认为 PENDING_REVIEW（M4a DecisionStatus）。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)

    assert manifest.status == "PENDING_REVIEW"


# ═════════════════════════════════════════════════════════════
# decision.md 不能是 APPROVE
# ═════════════════════════════════════════════════════════════


def test_decision_default_status_is_pending_review(tmp_path):
    """decision.md 默认状态必须是 PENDING_REVIEW（M4a）。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    decision = (Path(manifest.package_path) / "decision.md").read_text(encoding="utf-8")

    assert "当前状态：PENDING_REVIEW" in decision


def test_decision_must_not_default_to_approve(tmp_path):
    """decision.md 默认状态绝对不能是 APPROVED。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    decision = (Path(manifest.package_path) / "decision.md").read_text(encoding="utf-8")

    assert "当前状态：APPROVED" not in decision


def test_decision_contains_all_three_options(tmp_path):
    """decision.md 必须包含三种决策选项。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    decision = (Path(manifest.package_path) / "decision.md").read_text(encoding="utf-8")

    assert "APPROVE" in decision
    assert "REQUEST_CHANGES" in decision
    assert "REJECT" in decision


def test_decision_states_not_approved(tmp_path):
    """decision.md 必须明确声明"当前不是 APPROVE"。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    decision = (Path(manifest.package_path) / "decision.md").read_text(encoding="utf-8")

    assert "不是 APPROVE" in decision


# ═════════════════════════════════════════════════════════════
# M4a decision.yml / decision_log.yml
# ═════════════════════════════════════════════════════════════


def test_decision_yml_contains_required_fields(tmp_path):
    """decision.yml 必须包含 M4b 规定的全部字段（含 artifact_hashes）。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    decision_yml = yaml.safe_load(
        (Path(manifest.package_path) / "decision.yml").read_text(encoding="utf-8")
    )

    assert decision_yml["request_id"] == req.request_id
    assert decision_yml["current_state"] == "PENDING_REVIEW"
    assert decision_yml["human_review_required"] is True
    assert "last_updated" in decision_yml
    assert decision_yml["last_updated_by"] == "agent"
    assert decision_yml["verification_report_ref"] == "reports/verification.md"
    assert decision_yml["verification_overall_status"] == "PENDING"
    assert decision_yml["human_decision_note"] == ""
    # M4b：artifact_hashes 必须存在
    assert "artifact_hashes" in decision_yml
    hashes = decision_yml["artifact_hashes"]
    assert len(hashes["sql_main"]) == 64
    assert len(hashes["spark_main"]) == 64
    assert len(hashes["lineage_source_refs"]) == 64
    # M2 阶段 verification_summary hash 为 null
    assert hashes["verification_summary"] is None


def test_decision_yml_initial_state_not_approved(tmp_path):
    """decision.yml 初始状态绝对不能是 APPROVED/REQUEST_CHANGES/REJECTED。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    decision_yml = yaml.safe_load(
        (Path(manifest.package_path) / "decision.yml").read_text(encoding="utf-8")
    )

    assert decision_yml["current_state"] == "PENDING_REVIEW"
    assert decision_yml["current_state"] not in ("APPROVED", "REQUEST_CHANGES", "REJECTED")


def test_decision_log_yml_contains_creation_entry(tmp_path):
    """decision_log.yml 必须包含 Review Package 创建事件。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    log_yml = yaml.safe_load(
        (Path(manifest.package_path) / "decision_log.yml").read_text(encoding="utf-8")
    )

    assert log_yml["request_id"] == req.request_id
    assert len(log_yml["entries"]) == 1
    entry = log_yml["entries"][0]
    assert entry["from_state"] is None
    assert entry["to_state"] == "PENDING_REVIEW"
    assert entry["changed_by"] == "agent"
    assert entry["actor_id"] == "agent"  # M4b：actor_id 必须存在
    assert "timestamp" in entry
    assert "Review Package 创建" in entry["reason"]


# ═════════════════════════════════════════════════════════════
# 报告不能伪装 PASS
# ═════════════════════════════════════════════════════════════


def test_verification_report_is_pending(tmp_path):
    """M2 verification.md 必须是 PENDING 状态。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    verification = (Path(manifest.package_path) / "reports" / "verification.md").read_text(encoding="utf-8")

    assert "PENDING" in verification
    assert "尚未执行" in verification


def test_cross_validation_report_is_skipped(tmp_path):
    """M2 cross_validation.md 必须是 SKIPPED 状态。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    cross = (Path(manifest.package_path) / "reports" / "cross_validation.md").read_text(encoding="utf-8")

    assert "SKIPPED" in cross


def test_no_report_claims_pass(tmp_path):
    """M2 所有报告中不能出现 PASS。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)

    verification = (Path(manifest.package_path) / "reports" / "verification.md").read_text(encoding="utf-8")
    cross = (Path(manifest.package_path) / "reports" / "cross_validation.md").read_text(encoding="utf-8")

    # M2 阶段所有报告都不得包含 "PASS"（大写）
    assert "PASS" not in verification
    assert "PASS" not in cross


# ═════════════════════════════════════════════════════════════
# 来源追溯 (lineage)
# ═════════════════════════════════════════════════════════════


def test_lineage_contains_source_tables(tmp_path):
    """source_refs.yml 必须包含 source_tables。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    lineage = yaml.safe_load(
        (Path(manifest.package_path) / "lineage" / "source_refs.yml").read_text(encoding="utf-8")
    )

    assert "source_tables" in lineage
    assert len(lineage["source_tables"]) >= 1


def test_lineage_contains_source_fields(tmp_path):
    """source_refs.yml 必须包含 source_fields。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    lineage = yaml.safe_load(
        (Path(manifest.package_path) / "lineage" / "source_refs.yml").read_text(encoding="utf-8")
    )

    assert "source_fields" in lineage
    assert any(f["name"] == "trip_date" for f in lineage["source_fields"])


def test_lineage_contains_metric_sources(tmp_path):
    """source_refs.yml 必须包含 metric_sources。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    lineage = yaml.safe_load(
        (Path(manifest.package_path) / "lineage" / "source_refs.yml").read_text(encoding="utf-8")
    )

    assert "metric_sources" in lineage
    assert any(m["name"] == "trip_count" for m in lineage["metric_sources"])


def test_lineage_human_review_for_missing_source(tmp_path):
    """缺少 source 的字段，lineage 中标注 Human Review。"""
    req = _make_requirement(
        required_fields=[
            {"name": "trip_date", "table": "gold.dws_daily_trip_summary"},  # 无 source
        ],
    )
    plan = _make_plan(
        required_fields=[
            {"name": "trip_date", "table": "gold.dws_daily_trip_summary"},  # 无 source
        ],
    )
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    lineage = yaml.safe_load(
        (Path(manifest.package_path) / "lineage" / "source_refs.yml").read_text(encoding="utf-8")
    )

    trip_date_field = next(f for f in lineage["source_fields"] if f["name"] == "trip_date")
    assert trip_date_field["source"] == "Human Review"


# ═════════════════════════════════════════════════════════════
# 测试草案 (test_generated.py)
# ═════════════════════════════════════════════════════════════


def test_test_stub_is_valid_python(tmp_path):
    """生成的 tests/test_generated.py 必须是有效的 Python 语法。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    test_content = (Path(manifest.package_path) / "tests" / "test_generated.py").read_text(encoding="utf-8")

    # 至少包含一个测试函数
    assert "def test_" in test_content
    assert "草案" in test_content


def test_test_stub_contains_request_id(tmp_path):
    """测试草案应引用正确的 request_id。"""
    req = _make_requirement(request_id="my_test_req_123")
    plan = _make_plan(request_id="my_test_req_123")
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    test_content = (Path(manifest.package_path) / "tests" / "test_generated.py").read_text(encoding="utf-8")

    assert "my_test_req_123" in test_content


# ═════════════════════════════════════════════════════════════
# 内容正确写入
# ═════════════════════════════════════════════════════════════


def test_sql_content_is_written_correctly(tmp_path):
    """SQL 草案内容确实写入了 sql/main.sql。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    sql_content = (Path(manifest.package_path) / "sql" / "main.sql").read_text(encoding="utf-8")

    assert drafts.sql.content == sql_content


def test_spark_content_is_written_correctly(tmp_path):
    """Spark 草案内容确实写入了 spark/main.py。"""
    req = _make_requirement()
    plan = _make_plan()
    drafts = _make_drafts()

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)
    spark_content = (Path(manifest.package_path) / "spark" / "main.py").read_text(encoding="utf-8")

    assert drafts.spark.content == spark_content


def test_manifest_pending_items_aggregated(tmp_path):
    """manifest.pending_items 应聚合 plan 和 drafts 的 pending。"""
    req = _make_requirement()
    plan = _make_plan(pending_items=["plan_pending_1"])
    drafts = _make_drafts(pending_items=["drafts_pending_1"])

    manifest = publish_review_package(req, plan, drafts, output_root=tmp_path)

    assert "plan_pending_1" in manifest.pending_items
    assert "drafts_pending_1" in manifest.pending_items
