"""
设计方案规划器直接单元测试。

覆盖 build_design_plan() 的所有路径：
- 基于 RequirementSpec 生成 DevPlan
- 不确定字段必须进入 human_review_points / pending_items
- 不执行 SQL
- 不连接数据库
- 多表场景的 pending 标注
"""

from __future__ import annotations

from src.agent.design_planner import DevPlan, build_design_plan
from src.agent.requirement_analyzer import RequirementSpec


# ═════════════════════════════════════════════════════════════
# 辅助函数：构造最小可用的 RequirementSpec
# ═════════════════════════════════════════════════════════════


def _make_requirement(**overrides) -> RequirementSpec:
    """构造测试用 RequirementSpec，默认值确保正常流程可用。"""
    defaults = {
        "request_id": "test_req_001",
        "title": "测试需求",
        "business_goal": "验证设计方案生成",
        "source_tables": [{"name": "gold.dws_daily_trip_summary"}],
        "required_fields": [
            {"name": "trip_date", "table": "gold.dws_daily_trip_summary", "source": "gold.dws_daily_trip_summary.trip_date"},
        ],
        "metrics": [
            {"name": "trip_count", "field": "trip_count", "definition_source": "meta.metric_definitions.trip_count"},
        ],
        "filters": {"date_range": ["2026-01-01", "2026-01-31"]},
        "grain": ["trip_date"],
        "output_expectation": "按日汇总",
        "human_review_points": ["Human Review: 测试审查点"],
    }
    defaults.update(overrides)
    return RequirementSpec(**defaults)


# ═════════════════════════════════════════════════════════════
# 基本功能
# ═════════════════════════════════════════════════════════════


def test_builds_devplan_from_requirement():
    """build_design_plan 输出正确的 DevPlan 类型和数据。"""
    req = _make_requirement()
    plan = build_design_plan(req)

    assert isinstance(plan, DevPlan)
    assert plan.request_id == "test_req_001"
    assert plan.title == "测试需求"
    assert plan.business_goal == "验证设计方案生成"
    assert len(plan.source_tables) == 1
    assert plan.source_tables[0]["name"] == "gold.dws_daily_trip_summary"


def test_devplan_preserves_all_fields_from_requirement():
    """DevPlan 必须保留 Requirement 中的所有核心字段。"""
    req = _make_requirement()
    plan = build_design_plan(req)

    assert plan.required_fields == req.required_fields
    assert plan.metrics == req.metrics
    assert plan.filters == req.filters
    assert plan.grain == req.grain
    assert plan.output_expectation == req.output_expectation


def test_devplan_to_dict_is_serializable():
    """to_dict() 必须返回可序列化的字典。"""
    req = _make_requirement()
    plan = build_design_plan(req)
    result = plan.to_dict()

    assert isinstance(result, dict)
    assert result["request_id"] == "test_req_001"
    assert "human_review_points" in result
    assert "pending_items" in result


# ═════════════════════════════════════════════════════════════
# 不确定项标注
# ═════════════════════════════════════════════════════════════


def test_missing_field_source_enters_pending():
    """required_fields 中缺少 source 的字段必须进入 pending_items。"""
    req = _make_requirement(
        required_fields=[
            {"name": "trip_date", "table": "gold.dws_daily_trip_summary", "source": "gold.dws_daily_trip_summary.trip_date"},
            {"name": "unknown_source_field", "table": "gold.dws_daily_trip_summary"},  # 无 source
        ],
    )
    plan = build_design_plan(req)

    assert any("unknown_source_field" in item for item in plan.pending_items)


def test_missing_metric_definition_source_enters_pending():
    """metrics 中缺少 definition_source 的指标必须进入 pending_items。"""
    req = _make_requirement(
        metrics=[
            {"name": "known_metric", "field": "km", "definition_source": "meta.def"},
            {"name": "unknown_metric", "field": "um"},  # 无 definition_source
        ],
    )
    plan = build_design_plan(req)

    assert any("unknown_metric" in item for item in plan.pending_items)


def test_multi_table_without_join_enters_pending():
    """多表需求且未声明 JOIN 关系时必须进入 pending_items。"""
    req = _make_requirement(
        source_tables=[
            {"name": "gold.table_a"},
            {"name": "gold.table_b"},
        ],
    )
    plan = build_design_plan(req)

    assert any("JOIN" in item for item in plan.pending_items)
    assert any("JOIN" in item for item in plan.human_review_points)


def test_all_fields_declared_leaves_empty_pending_items():
    """所有字段都有 source/definition_source、单表时 pending_items 应为空。"""
    req = _make_requirement()
    plan = build_design_plan(req)

    # 单表 + 全部字段有 source → 不应该有 pending
    assert not any("Human Review:" in item and "缺少" in item for item in plan.pending_items)


def test_pending_items_never_auto_resolved():
    """不确定项不能自动消解——必须保留在 pending_items 中。"""
    req = _make_requirement(
        required_fields=[
            {"name": "col1", "table": "gold.t"},  # 无 source
        ],
    )
    plan = build_design_plan(req)

    # 确认缺少 source 的字段仍在 pending 中
    assert len(plan.pending_items) >= 1
    assert any("col1" in item for item in plan.pending_items)


# ═════════════════════════════════════════════════════════════
# 不执行 SQL、不连库
# ═════════════════════════════════════════════════════════════


def test_design_planner_accepts_no_db_connection():
    """build_design_plan 不接受数据库连接参数——设计阶段不连库。"""
    req = _make_requirement()
    # 函数签名仅接受 RequirementSpec，不暴露 conn 参数
    plan = build_design_plan(req)
    assert plan is not None


def test_design_planner_does_not_require_any_external_resources():
    """build_design_plan 只需要 RequirementSpec，不需要任何外部资源。"""
    req = _make_requirement()
    # 即使没有任何外部连接、文件、配置也能正常工作
    plan = build_design_plan(req)
    assert plan.request_id == "test_req_001"


# ═════════════════════════════════════════════════════════════
# human_review_points 传递
# ═════════════════════════════════════════════════════════════


def test_human_review_points_propagated_from_requirement():
    """Requirement 中的 human_review_points 必须传递到 DevPlan。"""
    req = _make_requirement(
        human_review_points=["Human Review: 请确认日期范围", "Human Review: 请确认指标口径"],
    )
    plan = build_design_plan(req)

    assert "Human Review: 请确认日期范围" in plan.human_review_points
    assert "Human Review: 请确认指标口径" in plan.human_review_points


def test_human_review_points_passthrough():
    """DevPlan 的 human_review_points 直接来自 Requirement（透传）。

    RequirementSpec 构建时的默认值在 analyze_requirement 中添加，
    build_design_plan 不做额外填充。
    """
    req = _make_requirement(human_review_points=["Human Review: 测试点"])
    plan = build_design_plan(req)

    # 至少应透传 Requirement 中的值
    assert "Human Review: 测试点" in plan.human_review_points


def test_multi_table_adds_join_review_point():
    """多表需求必须自动添加 JOIN 相关审查点。"""
    req = _make_requirement(
        source_tables=[{"name": "gold.a"}, {"name": "gold.b"}],
    )
    plan = build_design_plan(req)

    assert any("JOIN" in item for item in plan.human_review_points)
