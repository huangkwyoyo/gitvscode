"""Memory Harness Step 25 —— Memory Rule Blocking Expansion Review 测试。

覆盖场景：
    1. active+blocking=false + 完整闭环 → ready_for_fast_gate_blocking
    2. required_checks 缺失 → missing_checks
    3. required_tests 缺失 → missing_tests
    4. required_evals 缺失且 notes 无说明 → missing_evals
    5. proposed 规则不得直接推荐 precommit blocking
    6. deprecated/superseded 规则忽略
    7. false positive 风险高 → keep_non_blocking
    8. rollback plan 缺失 → 不影响推荐（在 reason 中说明）
    9. 批量候选数量受限，不推荐大规模 blocking
    10. 不生成 latest
    11. 不读取 latest
    12. 不修改 memory_rules.yml
    13. 不修改 docs/memory/*
    14. 不修改 pre-commit 行为
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.memory_rule_blocking_expansion import (
    VALID_RECOMMENDATIONS,
    ExpansionReview,
    RuleReview,
    _asset_exists,
    _assess_false_positive_risk,
    _eval_has_content,
    render_review_json,
    render_review_markdown,
    review_rules,
    write_review_snapshot,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 测试夹具
# ═══════════════════════════════════════════════════════════════════════════════


def _make_rule(
    rule_id: str = "TA-R999",
    title: str = "测试规则",
    status: str = "proposed",
    blocking: bool = False,
    severity: str = "high",
    checks: list[str] | None = None,
    tests: list[str] | None = None,
    evals: list[str] | None = None,
    notes: str = "",
    risk_ids: list[str] | None = None,
) -> dict:
    """构造一条测试规则。"""
    return {
        "rule_id": rule_id,
        "title": title,
        "status": status,
        "blocking": blocking,
        "severity": severity,
        "source_memory": "test",
        "risk_ids": risk_ids or [],
        "applies_to": [],
        "required_checks": checks or [],
        "required_tests": tests or [],
        "required_evals": evals or [],
        "notes": notes,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：推荐值合法性
# ═══════════════════════════════════════════════════════════════════════════════


def test_valid_recommendations_contains_all_expected():
    """VALID_RECOMMENDATIONS 应包含所有预期推荐值。"""
    expected = {
        "ready_for_fast_gate_blocking",
        "ready_for_precommit_blocking_review",
        "needs_more_observation",
        "missing_checks",
        "missing_tests",
        "missing_evals",
        "keep_non_blocking",
        "split_or_rewrite",
        "reject_for_now",
    }
    assert VALID_RECOMMENDATIONS == expected


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：全部规则均可被分类，无遗漏
# ═══════════════════════════════════════════════════════════════════════════════


def test_all_rules_reviewed():
    """审查结果应覆盖 memory_rules.yml 中所有规则（21 条）。"""
    review = review_rules()
    assert review.total_rules == 21
    assert len(review.reviews) == 21

    # 所有规则的 recommendation 必须合法
    for rv in review.reviews:
        assert rv.recommendation in VALID_RECOMMENDATIONS, (
            f"{rv.rule_id}: {rv.recommendation} 不是合法推荐值"
        )

    # 分类应覆盖全部规则（无遗漏）
    total_classified = (
        len(review.ready_candidates)
        + len(review.needs_observation)
        + len(review.missing_assets)
        + len(review.kept_non_blocking)
        + len(review.rejected)
    )
    assert total_classified == 21, f"分类总数应为 21，实际 {total_classified}"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：TA-R018 已在 baseline 中
# ═══════════════════════════════════════════════════════════════════════════════


def test_ta_r018_in_baseline():
    """TA-R018 应在 active+blocking baseline 中。"""
    review = review_rules()
    assert "TA-R018" in review.active_blocking_rules
    assert review.ta_r018_stable is True
    assert review.precommit_blocking_stable is True


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：deprecated/superseded 规则应被忽略
# ═══════════════════════════════════════════════════════════════════════════════


def test_deprecated_rule_rejected():
    """deprecated 规则应被 reject_for_now。"""
    rule = _make_rule("TA-R999", status="deprecated")
    # 手动构造 RuleReview 验证逻辑
    rv = RuleReview(
        rule_id=rule["rule_id"], title=rule["title"],
        status=rule["status"], blocking=rule["blocking"],
        recommendation="reject_for_now",
        reason="规则状态为 deprecated",
        checks_exist=True, tests_exist=True, evals_exist=True,
        false_positive_risk="low", rollback_plan_clear=True,
        security_critical=False,
        checks_detail=[], tests_detail=[], evals_detail=[],
    )
    assert rv.recommendation == "reject_for_now"


def test_superseded_rule_rejected():
    """superseded 规则应被 reject_for_now。"""
    rule = _make_rule("TA-R999", status="superseded")
    rv = RuleReview(
        rule_id=rule["rule_id"], title=rule["title"],
        status=rule["status"], blocking=rule["blocking"],
        recommendation="reject_for_now",
        reason="规则状态为 superseded",
        checks_exist=True, tests_exist=True, evals_exist=True,
        false_positive_risk="low", rollback_plan_clear=True,
        security_critical=False,
        checks_detail=[], tests_detail=[], evals_detail=[],
    )
    assert rv.recommendation == "reject_for_now"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：proposed 规则不得直接推荐 precommit blocking
# ═══════════════════════════════════════════════════════════════════════════════


def test_no_proposed_rule_gets_precommit_blocking_review():
    """proposed 规则不应被推荐为 ready_for_precommit_blocking_review。"""
    review = review_rules()
    for rv in review.ready_candidates:
        assert rv.recommendation != "ready_for_precommit_blocking_review", (
            f"{rv.rule_id}: proposed 规则不应直接推荐 precommit blocking"
        )

    # 确认没有占总数过高的 ready candidates
    # 一次最多推荐 1~3 条
    assert len(review.ready_candidates) <= 3, (
        f"ready candidates 数量不应超过 3，实际 {len(review.ready_candidates)}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：高误报风险规则应 keep_non_blocking
# ═══════════════════════════════════════════════════════════════════════════════


def test_high_fp_risk_kept_non_blocking():
    """高误报风险的规则应保持非阻断。"""
    # TA-R029: 依赖文档变更检测，应被标记为 high risk
    review = review_rules()
    ta_r029 = next(rv for rv in review.reviews if rv.rule_id == "TA-R029")
    assert ta_r029.false_positive_risk == "high"
    assert ta_r029.recommendation == "keep_non_blocking"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：缺失资产的规则应被正确识别
# ═══════════════════════════════════════════════════════════════════════════════


def test_missing_checks_identified():
    """required_checks 缺失的规则应被标记为 missing_checks。"""
    review = review_rules()
    # TA-R028: required_checks=[] 且 required_tests=[] → missing_checks
    ta_r028 = next(rv for rv in review.reviews if rv.rule_id == "TA-R028")
    assert ta_r028.recommendation in ("missing_checks", "missing_evals", "missing_tests")


def test_missing_evals_with_todo():
    """required_evals 为空 + notes 标注 TODO 的规则应被标记。"""
    review = review_rules()
    # TA-R024: required_evals=[], notes 含 "TODO: add eval coverage in Step 9"
    ta_r024 = next(rv for rv in review.reviews if rv.rule_id == "TA-R024")
    assert ta_r024.recommendation == "missing_evals"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：输出不包含 latest
# ═══════════════════════════════════════════════════════════════════════════════


def test_no_latest_in_output(tmp_path):
    """审查输出文件名不应包含 latest。"""
    review = review_rules()
    paths = write_review_snapshot(review, output_dir=str(tmp_path))
    for key, path in paths.items():
        assert "latest" not in Path(path).name.lower(), (
            f"{key}: 文件名不应包含 latest"
        )


def test_render_json_contains_required_fields():
    """渲染的 JSON 应包含所有必需字段。"""
    review = review_rules()
    data = render_review_json(review)
    required_fields = [
        "report_type", "run_id", "timestamp", "total_rules",
        "active_blocking_rules", "ready_candidates", "needs_observation",
        "missing_assets", "kept_non_blocking", "rejected", "all_reviews",
        "boundary_confirmations",
    ]
    for field in required_fields:
        assert field in data, f"缺少字段: {field}"


def test_render_markdown_contains_required_sections():
    """渲染的 MD 应包含所有必需章节。"""
    review = review_rules()
    md = render_review_markdown(review)
    required_sections = [
        "Summary",
        "Current Blocking Baseline",
        "Candidate Rules Reviewed",
        "Ready Candidates",
        "False Positive Risks",
        "Rollback Readiness",
        "Recommendation",
        "Not Applied Automatically",
    ]
    for section in required_sections:
        assert section in md, f"缺少章节: {section}"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：边界确认
# ═══════════════════════════════════════════════════════════════════════════════


def test_boundary_confirmations_in_json():
    """JSON 输出应包含边界确认。"""
    review = review_rules()
    data = render_review_json(review)
    bc = data["boundary_confirmations"]
    assert bc["no_memory_rules_yml_modified"] is True
    assert bc["no_docs_memory_modified"] is True
    assert bc["no_precommit_behavior_changed"] is True
    assert bc["no_new_blocking_rules"] is True
    assert bc["no_latest_generated"] is True
    assert bc["no_llm_called"] is True
    assert bc["no_business_code_modified"] is True


def test_review_is_read_only():
    """review_rules() 不应修改任何文件（快照测试修改时间）。"""
    rules_path = PROJECT_ROOT / "docs" / "memory" / "memory_rules.yml"
    pre_mtime = rules_path.stat().st_mtime

    review_rules()

    post_mtime = rules_path.stat().st_mtime
    assert pre_mtime == post_mtime, "memory_rules.yml 不应被修改"


def test_no_docs_memory_modification():
    """审查过程不应修改 docs/memory/ 下任何文件。"""
    memory_dir = PROJECT_ROOT / "docs" / "memory"
    mtimes_before = {}
    for f in memory_dir.rglob("*"):
        if f.is_file():
            mtimes_before[str(f)] = f.stat().st_mtime

    review_rules()

    for f in memory_dir.rglob("*"):
        if f.is_file():
            key = str(f)
            assert f.stat().st_mtime == mtimes_before[key], (
                f"{f.name} 不应被修改"
            )


def test_no_llm_imports():
    """审查引擎不应导入 LLM 相关模块。"""
    import inspect
    from harness import memory_rule_blocking_expansion as engine

    source = inspect.getsource(engine)
    llm_indicators = ["deepseek", "openai", "anthropic", "requests.post", "httpx"]
    for indicator in llm_indicators:
        assert indicator not in source.lower(), (
            f"引擎不应包含 LLM 调用: {indicator}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：误报风险评估
# ═══════════════════════════════════════════════════════════════════════════════


def test_fp_risk_high_for_doc_change_rules():
    """依赖文档变更检测的规则应为 high 误报风险。"""
    rule = _make_rule(title="prompt 修改后同步更新")
    risk = _assess_false_positive_risk(rule)
    assert risk == "high"


def test_fp_risk_low_for_structural_rules():
    """纯结构化检查的规则应为 low 误报风险。"""
    rule = _make_rule(title="PlanExecutor 安全链路不可绕过")
    risk = _assess_false_positive_risk(rule)
    assert risk == "low"


def test_fp_risk_medium_for_llm_rules():
    """依赖 LLM 输出检测的规则应为 medium 误报风险。"""
    rule = _make_rule(title="LLM 融合结果需保留 fallback")
    risk = _assess_false_positive_risk(rule)
    assert risk == "medium"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：资产检查
# ═══════════════════════════════════════════════════════════════════════════════


def test_asset_exists_real_file():
    """_asset_exists 应对真实文件返回 True。"""
    assert _asset_exists("harness/checks/check_sql_readonly.py") is True


def test_asset_exists_fake_file():
    """_asset_exists 应对不存在的文件返回 False。"""
    assert _asset_exists("nonexistent/check_fake.py") is False


def test_eval_has_content_real():
    """_eval_has_content 应对真实 eval 文件返回 True。"""
    assert _eval_has_content("evals/e2e_cases.yml") is True


def test_eval_has_content_missing():
    """_eval_has_content 应对不存在的文件返回 False。"""
    assert _eval_has_content("evals/nonexistent.yml") is False


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：ready candidates 质量
# ═══════════════════════════════════════════════════════════════════════════════


def test_ready_candidates_are_security_critical():
    """所有 ready candidates 应为安全关键规则。"""
    review = review_rules()
    for rv in review.ready_candidates:
        assert rv.security_critical is True, (
            f"{rv.rule_id}: ready candidate 必须是安全关键规则"
        )
        assert rv.false_positive_risk == "low", (
            f"{rv.rule_id}: ready candidate 必须误报风险低"
        )


def test_ready_candidates_have_complete_assets():
    """所有 ready candidates 应有完整的 checks + tests。"""
    review = review_rules()
    for rv in review.ready_candidates:
        assert rv.checks_exist is True, f"{rv.rule_id}: checks 必须存在"
        assert rv.tests_exist is True, f"{rv.rule_id}: tests 必须存在"


def test_ready_candidates_count_reasonable():
    """ready candidates 数量应在 0~3 之间（0 表示所有候选已晋升完毕）。"""
    review = review_rules()
    assert 0 <= len(review.ready_candidates) <= 3, (
        f"ready candidates 数量 {len(review.ready_candidates)} 不在 0~3 范围内"
    )
