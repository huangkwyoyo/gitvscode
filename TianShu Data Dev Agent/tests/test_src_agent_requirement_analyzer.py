"""
需求分析器直接单元测试。

覆盖 analyze_requirement() 的所有输入路径：
- 合法 fixture 的完整读取
- 缺失 request_id 的快速失败
- 不允许自动编造 request_id
- 不允许自动补充未声明字段
- 各种边界输入（空文件、缺失必填列表、文件不存在）
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.agent.requirement_analyzer import RequirementSpec, analyze_requirement


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"


# ═════════════════════════════════════════════════════════════
# 合法 fixture 读取
# ═════════════════════════════════════════════════════════════


def test_reads_valid_fixture_all_fields_present():
    """合法 fixture 应正确读取所有显式声明字段。"""
    spec = analyze_requirement(FIXTURE)

    assert spec.request_id == "trip_daily_report_m2"
    assert "2026年Q1" in spec.title
    assert spec.source_tables
    assert spec.required_fields
    assert spec.metrics
    assert spec.filters
    assert spec.grain
    assert spec.output_expectation

    # request_id 必须来自 fixture，不能是编造的
    assert spec.request_id != "auto_generated"


def test_reads_valid_fixture_returns_requirementspec():
    """返回值类型必须是 RequirementSpec。"""
    spec = analyze_requirement(FIXTURE)
    assert isinstance(spec, RequirementSpec)


def test_allowed_tables_matches_fixture_declarations():
    """allowed_tables() 只返回 fixture source_tables 中声明的表。"""
    spec = analyze_requirement(FIXTURE)
    allowed = spec.allowed_tables()
    assert "gold.dws_daily_trip_summary" in allowed
    # 不允许出现 fixture 未声明的表
    assert "bronze.raw_trips" not in allowed


def test_allowed_fields_matches_fixture_declarations():
    """allowed_fields() 只返回 fixture 中显式声明的字段。"""
    spec = analyze_requirement(FIXTURE)
    allowed = spec.allowed_fields()

    # required_fields 中的字段
    assert "trip_date" in allowed
    # metrics 中的字段
    assert "trip_count" in allowed
    assert "total_fare_amount" in allowed
    assert "total_distance_miles" in allowed

    # fixture 未声明的字段绝不能出现
    assert "fare_amount" not in allowed
    assert "pickup_datetime" not in allowed
    assert "total_tip_amount" not in allowed


def test_raw_preserves_original_yaml_data():
    """raw 字段应保留原始 YAML 数据。"""
    spec = analyze_requirement(FIXTURE)
    assert isinstance(spec.raw, dict)
    assert spec.raw["request_id"] == "trip_daily_report_m2"


def test_human_review_points_always_present():
    """human_review_points 不能为空——即使 fixture 未声明也应有默认值。"""
    spec = analyze_requirement(FIXTURE)
    assert len(spec.human_review_points) > 0
    # fixture 显式声明了 human_review_points，内容包含 "Human Review"
    assert any("Human Review" in point for point in spec.human_review_points)


# ═════════════════════════════════════════════════════════════
# 缺失 request_id——必须失败，不能自动编造
# ═════════════════════════════════════════════════════════════


def test_missing_request_id_raises_value_error(tmp_path):
    """request_id 缺失时必须抛出 ValueError，不能自动编造。"""
    bad = tmp_path / "no_request_id.yml"
    bad.write_text(
        yaml.safe_dump(
            {
                "title": "无 request_id 的需求",
                "business_goal": "测试",
                "source_tables": [{"name": "gold.t"}],
                "required_fields": [{"name": "col1", "table": "gold.t"}],
                "metrics": [{"name": "cnt", "field": "col1"}],
                "filters": {},
                "grain": ["col1"],
                "output_expectation": "test",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="request_id"):
        analyze_requirement(bad)


def test_empty_request_id_raises_value_error(tmp_path):
    """request_id 为空字符串时必须失败。"""
    bad = tmp_path / "empty_request_id.yml"
    bad.write_text(
        yaml.safe_dump(
            {
                "request_id": "",
                "title": "空 ID",
                "business_goal": "测试",
                "source_tables": [{"name": "gold.t"}],
                "required_fields": [{"name": "col1", "table": "gold.t"}],
                "metrics": [{"name": "cnt", "field": "col1"}],
                "filters": {},
                "grain": ["col1"],
                "output_expectation": "test",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="request_id"):
        analyze_requirement(bad)


def test_whitespace_only_request_id_raises_value_error(tmp_path):
    """request_id 为纯空格时必须失败。"""
    bad = tmp_path / "whitespace_id.yml"
    bad.write_text(
        yaml.safe_dump(
            {
                "request_id": "   ",
                "title": "空格 ID",
                "business_goal": "测试",
                "source_tables": [{"name": "gold.t"}],
                "required_fields": [{"name": "col1", "table": "gold.t"}],
                "metrics": [{"name": "cnt", "field": "col1"}],
                "filters": {},
                "grain": ["col1"],
                "output_expectation": "test",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="request_id"):
        analyze_requirement(bad)


# ═════════════════════════════════════════════════════════════
# 不允许自动补充未声明字段
# ═════════════════════════════════════════════════════════════


def test_does_not_invent_missing_source_tables(tmp_path):
    """不能自动编造 source_tables——缺失时必须失败。"""
    bad = tmp_path / "no_tables.yml"
    bad.write_text(
        yaml.safe_dump(
            {
                "request_id": "no_tables_test",
                "title": "无表",
                "business_goal": "测试",
                "required_fields": [{"name": "col1", "table": "gold.t"}],
                "metrics": [{"name": "cnt", "field": "col1"}],
                "filters": {},
                "grain": ["col1"],
                "output_expectation": "test",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source_tables"):
        analyze_requirement(bad)


def test_does_not_invent_missing_required_fields(tmp_path):
    """不能自动编造 required_fields——缺失时必须失败。"""
    bad = tmp_path / "no_fields.yml"
    bad.write_text(
        yaml.safe_dump(
            {
                "request_id": "no_fields_test",
                "title": "无字段",
                "business_goal": "测试",
                "source_tables": [{"name": "gold.t"}],
                "metrics": [{"name": "cnt", "field": "col1"}],
                "filters": {},
                "grain": ["col1"],
                "output_expectation": "test",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="required_fields"):
        analyze_requirement(bad)


def test_does_not_invent_missing_metrics(tmp_path):
    """不能自动编造 metrics——缺失时必须失败。"""
    bad = tmp_path / "no_metrics.yml"
    bad.write_text(
        yaml.safe_dump(
            {
                "request_id": "no_metrics_test",
                "title": "无指标",
                "business_goal": "测试",
                "source_tables": [{"name": "gold.t"}],
                "required_fields": [{"name": "col1", "table": "gold.t"}],
                "filters": {},
                "grain": ["col1"],
                "output_expectation": "test",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="metrics"):
        analyze_requirement(bad)


def test_does_not_invent_empty_source_tables(tmp_path):
    """source_tables 为空列表时必须失败。"""
    bad = tmp_path / "empty_tables.yml"
    bad.write_text(
        yaml.safe_dump(
            {
                "request_id": "empty_tables_test",
                "title": "空表",
                "business_goal": "测试",
                "source_tables": [],
                "required_fields": [{"name": "col1", "table": "gold.t"}],
                "metrics": [{"name": "cnt", "field": "col1"}],
                "filters": {},
                "grain": ["col1"],
                "output_expectation": "test",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source_tables"):
        analyze_requirement(bad)


# ═════════════════════════════════════════════════════════════
# 边界输入
# ═════════════════════════════════════════════════════════════


def test_file_not_found_raises_value_error():
    """文件不存在时必须抛出明确的 ValueError。"""
    with pytest.raises(ValueError, match="文件不存在"):
        analyze_requirement("nonexistent_fixture.yml")


def test_empty_yaml_file_raises_value_error(tmp_path):
    """空 YAML 文件必须失败。"""
    empty = tmp_path / "empty.yml"
    empty.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="非空"):
        analyze_requirement(empty)


def test_yaml_with_only_scalar_raises_value_error(tmp_path):
    """YAML 不是对象结构时必须失败。"""
    scalar = tmp_path / "scalar.yml"
    scalar.write_text("just a string", encoding="utf-8")

    with pytest.raises(ValueError, match="非空"):
        analyze_requirement(scalar)


def test_optional_fields_default_to_empty(tmp_path):
    """可选字段（grain、output_expectation）缺失时应使用合理默认值。"""
    minimal = tmp_path / "minimal.yml"
    minimal.write_text(
        yaml.safe_dump(
            {
                "request_id": "minimal_test",
                "title": "最小",
                "business_goal": "测试",
                "source_tables": [{"name": "gold.t"}],
                "required_fields": [{"name": "col1", "table": "gold.t"}],
                "metrics": [{"name": "cnt", "field": "col1"}],
                "filters": {},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    spec = analyze_requirement(minimal)
    assert spec.grain == []
    assert spec.output_expectation == ""
    assert spec.human_notes == []
    # human_review_points 即使未声明也应有默认值
    assert len(spec.human_review_points) >= 1


def test_allowed_tables_handles_missing_name_field(tmp_path):
    """source_tables 中表缺少 name 字段时不崩溃（防御性处理）。"""
    fixture = tmp_path / "missing_name.yml"
    fixture.write_text(
        yaml.safe_dump(
            {
                "request_id": "missing_name_test",
                "title": "缺表名",
                "business_goal": "测试",
                "source_tables": [
                    {"name": "gold.t"},
                    {"role": "secondary"},  # 缺少 name 字段
                ],
                "required_fields": [{"name": "col1", "table": "gold.t"}],
                "metrics": [{"name": "cnt", "field": "col1"}],
                "filters": {},
                "grain": ["col1"],
                "output_expectation": "test",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    spec = analyze_requirement(fixture)
    allowed = spec.allowed_tables()
    assert "gold.t" in allowed
    # 缺少 name 的表不应出现在 allowed_tables 中
    assert len(allowed) == 1


def test_allowed_fields_handles_missing_name_field(tmp_path):
    """required_fields 中字段缺少 name 时不崩溃。"""
    fixture = tmp_path / "missing_field_name.yml"
    fixture.write_text(
        yaml.safe_dump(
            {
                "request_id": "missing_field_test",
                "title": "缺字段名",
                "business_goal": "测试",
                "source_tables": [{"name": "gold.t"}],
                "required_fields": [
                    {"name": "col1", "table": "gold.t"},
                    {"table": "gold.t"},  # 缺少 name
                ],
                "metrics": [{"name": "cnt", "field": "cnt_field"}],
                "filters": {},
                "grain": [],
                "output_expectation": "test",
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    spec = analyze_requirement(fixture)
    allowed = spec.allowed_fields()
    assert "col1" in allowed
    assert "cnt_field" in allowed
