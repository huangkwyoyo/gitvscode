"""test_memory_suggestion_review.py —— Step 12 memory suggestion review 工作流测试。

覆盖：
    1.  refusal_expected_but_answered → regression + risk，high priority
    2.  clarification_expected_but_answered → regression candidate
    3.  safety_validation_failed → risk item + manual_review_required
    4.  field_mismatch + asset_dependency=true → asset_dependency_wait
    5.  execution_failed + asset_dependency=true → asset_dependency_wait
    6.  confidence_out_of_range + provider/model → provider_runtime_noise 或 manual_review_required
    7.  raw_output_parse_failed → regression candidate
    8.  suggested rule preview 保持 status=proposed
    9.  suggested rule preview 保持 blocking=false
    10. JSON renderer 包含 summary 和 review_items
    11. Markdown renderer 包含 Memory Rule Candidates
    12. CLI 只生成 timestamp snapshot
    13. CLI 不生成 latest
    14. CLI 不修改 docs/memory/*
    15. CLI 不读取 *_latest.*
    16. 所有 suggestion 都必须产生 review item，不允许静默忽略
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.memory_suggestion_review import (  # noqa: E402
    REVIEW_ACTION_META,
    classify_memory_suggestion_for_review,
    build_memory_suggestion_review_report,
    build_review_item,
    load_memory_suggestions_snapshot,
    render_memory_suggestion_review_json,
    render_memory_suggestion_review_markdown,
    write_memory_suggestion_review_snapshot,
)
from harness.memory_suggestions import (  # noqa: E402
    build_memory_suggestion,
    build_memory_suggestions_report,
)


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _failed_case(
    question_id: str = "C001",
    failure_type: str = "intent_mismatch",
    question: str = "测试问题",
    **kwargs,
) -> dict:
    """构造最小失败 case 字典。"""
    base = {
        "question_id": question_id,
        "question": question,
        "failure_type": failure_type,
    }
    base.update(kwargs)
    return base


def _make_suggestion(failure_type: str, question_id: str = "TEST") -> dict:
    """快捷构造单条 memory suggestion。"""
    return build_memory_suggestion(_failed_case(question_id, failure_type))


# ═══════════════════════════════════════════════════════════════
# 测试 1-7: 分类规则正确性
# ═══════════════════════════════════════════════════════════════


class TestClassificationRules:
    """验证各 failure_type 的 review_action 分类正确性。"""

    def test_refusal_is_regression_plus_risk_high_priority(self):
        """测试 1: refusal_expected_but_answered → regression + risk，high priority。"""
        suggestion = _make_suggestion("refusal_expected_but_answered", "C001")
        result = classify_memory_suggestion_for_review(suggestion)

        assert "accept_as_regression_case" in result["review_action"]
        assert "accept_as_risk_item" in result["review_action"]
        assert len(result["review_action"]) == 2  # 多标签
        assert result["priority"] == "high"
        assert result["manual_review_required"] is True
        assert result["suggested_owner"] == "safety"

    def test_clarification_is_regression_candidate(self):
        """测试 2: clarification_expected_but_answered → regression candidate。"""
        suggestion = _make_suggestion("clarification_expected_but_answered", "C002")
        result = classify_memory_suggestion_for_review(suggestion)

        assert result["review_action"] == ["accept_as_regression_case"]
        assert result["priority"] == "high"
        assert result["suggested_owner"] == "prompt"

    def test_safety_is_risk_item_manual_review_required(self):
        """测试 3: safety_validation_failed → risk item + manual_review_required。"""
        suggestion = _make_suggestion("safety_validation_failed", "C003")
        result = classify_memory_suggestion_for_review(suggestion)

        assert result["review_action"] == ["accept_as_risk_item"]
        assert result["priority"] == "high"
        assert result["manual_review_required"] is True
        assert result["suggested_owner"] == "safety"

    def test_field_mismatch_asset_dependency_is_wait(self):
        """测试 4: field_mismatch + asset_dependency=true → asset_dependency_wait。"""
        suggestion = _make_suggestion("field_mismatch", "C004")
        # field_mismatch 在 FAILURE_CLASSIFICATION 中 asset_dependency=True
        assert suggestion["asset_dependency"] is True

        result = classify_memory_suggestion_for_review(suggestion)
        assert result["review_action"] == ["asset_dependency_wait"]
        assert result["priority"] == "low"
        assert result["suggested_owner"] == "asset"

    def test_execution_failed_asset_dependency_is_wait(self):
        """测试 5: execution_failed + asset_dependency=true → asset_dependency_wait。"""
        suggestion = _make_suggestion("execution_failed", "C005")
        assert suggestion["asset_dependency"] is True

        result = classify_memory_suggestion_for_review(suggestion)
        assert result["review_action"] == ["asset_dependency_wait"]
        assert result["priority"] == "low"
        assert result["suggested_owner"] == "asset"

    def test_confidence_out_of_range_is_provider_noise(self):
        """测试 6: confidence_out_of_range → provider_runtime_noise。"""
        suggestion = _make_suggestion("confidence_out_of_range", "C006")
        result = classify_memory_suggestion_for_review(suggestion)

        assert result["review_action"] == ["provider_runtime_noise"]
        assert result["priority"] == "low"
        assert result["suggested_owner"] == "eval"

    def test_raw_output_parse_failed_is_regression_candidate(self):
        """测试 7: raw_output_parse_failed → regression candidate。"""
        suggestion = _make_suggestion("raw_output_parse_failed", "C007")
        result = classify_memory_suggestion_for_review(suggestion)

        assert result["review_action"] == ["accept_as_regression_case"]
        assert result["priority"] == "medium"


# ═══════════════════════════════════════════════════════════════
# 测试 8-9: 规则预览约束
# ═══════════════════════════════════════════════════════════════


class TestSuggestedRulePreviewConstraints:
    """验证 suggested_memory_rule_preview 的关键边界约束。"""

    def test_suggested_rule_preview_status_is_always_proposed(self):
        """测试 8: suggested rule preview 保持 status=proposed。"""
        for failure_type in [
            "intent_mismatch",
            "safety_validation_failed",
            "refusal_expected_but_answered",
            "field_mismatch",
            "confidence_out_of_range",
        ]:
            suggestion = _make_suggestion(failure_type)
            item = build_review_item(suggestion)

            preview = item["suggested_memory_rule_preview"]
            assert preview["status"] == "proposed", (
                f"{failure_type}: expected status=proposed, got {preview['status']}"
            )

    def test_suggested_rule_preview_blocking_is_always_false(self):
        """测试 9: suggested rule preview 保持 blocking=false。"""
        for failure_type in [
            "intent_mismatch",
            "safety_validation_failed",
            "refusal_expected_but_answered",
            "field_mismatch",
            "confidence_out_of_range",
        ]:
            suggestion = _make_suggestion(failure_type)
            item = build_review_item(suggestion)

            preview = item["suggested_memory_rule_preview"]
            assert preview["blocking"] is False, (
                f"{failure_type}: expected blocking=False, got {preview['blocking']}"
            )


# ═══════════════════════════════════════════════════════════════
# Review Item 字段完整性
# ═══════════════════════════════════════════════════════════════


class TestReviewItemFields:
    """验证 review_item 包含所有必需字段。"""

    def test_review_item_has_all_required_fields(self):
        """review_item 包含规范要求的全部字段。"""
        suggestion = _make_suggestion("intent_mismatch", "C001")
        item = build_review_item(suggestion)

        required_fields = {
            "review_index",
            "question_id",
            "failure_type",
            "original_recommended_action",
            "review_action",
            "review_reason",
            "manual_review_required",
            "priority",
            "suggested_owner",
            "suggested_next_files",
            "source_suggestion_id",
            "source_failure_case",
            "suggested_memory_rule_preview",
            "suggested_regression_case_preview",
            "suggested_risk_item_preview",
        }
        missing = required_fields - set(item.keys())
        assert not missing, f"review_item 缺少必需字段: {missing}"

    def test_regression_case_preview_is_present_for_regression_action(self):
        """包含 regression_case action 时，regression_case_preview 不为 None。"""
        suggestion = _make_suggestion("intent_mismatch", "C001")
        item = build_review_item(suggestion)

        assert "accept_as_regression_case" in item["review_action"]
        assert item["suggested_regression_case_preview"] is not None
        preview = item["suggested_regression_case_preview"]
        assert "case_id" in preview
        assert "question" in preview
        assert "failure_type" in preview

    def test_risk_item_preview_is_present_for_risk_action(self):
        """包含 risk_item action 时，risk_item_preview 不为 None。"""
        suggestion = _make_suggestion("safety_validation_failed", "C002")
        item = build_review_item(suggestion)

        assert "accept_as_risk_item" in item["review_action"]
        assert item["suggested_risk_item_preview"] is not None
        preview = item["suggested_risk_item_preview"]
        assert "risk_id" in preview
        assert "title" in preview
        assert "severity" in preview

    def test_risk_item_preview_is_none_for_non_risk_action(self):
        """不包含 risk_item action 时，risk_item_preview 为 None。"""
        suggestion = _make_suggestion("intent_mismatch", "C001")
        item = build_review_item(suggestion)

        assert "accept_as_risk_item" not in item["review_action"]
        assert item["suggested_risk_item_preview"] is None

    def test_suggested_owner_is_meaningful(self):
        """suggested_owner 根据 failure_type 有实际值，而非固定空字符串。"""
        owners = {
            "safety_validation_failed": "safety",
            "refusal_expected_but_answered": "safety",
            "clarification_expected_but_answered": "prompt",
            "intent_mismatch": "prompt",
            "field_mismatch": "asset",
            "execution_failed": "asset",
            "confidence_out_of_range": "eval",
        }
        for ft, expected_owner in owners.items():
            suggestion = _make_suggestion(ft)
            result = classify_memory_suggestion_for_review(suggestion)
            assert result["suggested_owner"] == expected_owner, (
                f"{ft}: expected owner={expected_owner}, got {result['suggested_owner']}"
            )

    def test_suggested_next_files_is_not_empty(self):
        """suggested_next_files 至少包含一个建议文件。"""
        suggestion = _make_suggestion("intent_mismatch", "C001")
        item = build_review_item(suggestion)
        assert len(item["suggested_next_files"]) > 0, (
            f"suggested_next_files 不应为空: {item['suggested_next_files']}"
        )

    def test_refusal_produces_both_regression_and_risk_preview(self):
        """refusal_expected_but_answered 同时产出 regression 和 risk 预览。"""
        suggestion = _make_suggestion("refusal_expected_but_answered", "C001")
        item = build_review_item(suggestion)

        assert item["suggested_regression_case_preview"] is not None
        assert item["suggested_risk_item_preview"] is not None


# ═══════════════════════════════════════════════════════════════
# 测试 10: JSON renderer
# ═══════════════════════════════════════════════════════════════


class TestJSONRenderer:
    """验证 JSON 渲染。"""

    def test_json_renderer_includes_summary_and_review_items(self):
        """测试 10: JSON renderer 包含 summary 和 review_items。"""
        suggestions_report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
            _failed_case("C002", "safety_validation_failed"),
        ])
        review = build_memory_suggestion_review_report(suggestions_report)
        payload = render_memory_suggestion_review_json(review)

        assert "summary" in payload
        assert "review_items" in payload
        assert "high_priority_manual_review" in payload
        assert "regression_case_candidates" in payload
        assert "memory_rule_candidates" in payload
        assert "risk_item_candidates" in payload
        assert "asset_dependency_waitlist" in payload
        assert "provider_runtime_noise" in payload
        assert "rejected_suggestions" in payload
        assert "manual_review_required" in payload
        assert payload["summary"]["total_suggestions"] == 2
        assert len(payload["review_items"]) == 2

    def test_json_excludes_original_suggestion(self):
        """JSON 输出不包含 _original_suggestion（体积优化）。"""
        suggestions_report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
        ])
        review = build_memory_suggestion_review_report(suggestions_report)
        payload = render_memory_suggestion_review_json(review)

        for item in payload["review_items"]:
            assert "_original_suggestion" not in item

    def test_json_is_valid_json_serializable(self):
        """JSON renderer 输出可通过 json.dumps 序列化。"""
        suggestions_report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
        ])
        review = build_memory_suggestion_review_report(suggestions_report)
        payload = render_memory_suggestion_review_json(review)

        dumped = json.dumps(payload, ensure_ascii=False)
        reloaded = json.loads(dumped)
        assert reloaded["summary"]["total_suggestions"] == 1


# ═══════════════════════════════════════════════════════════════
# 测试 11: Markdown renderer
# ═══════════════════════════════════════════════════════════════


class TestMarkdownRenderer:
    """验证 Markdown 渲染。"""

    def test_markdown_includes_memory_rule_candidates(self):
        """测试 11: Markdown renderer 包含 Memory Rule Candidates 章节。"""
        suggestions_report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
            _failed_case("C002", "safety_validation_failed"),
            _failed_case("C003", "refusal_expected_but_answered"),
        ])
        review = build_memory_suggestion_review_report(suggestions_report)
        md = render_memory_suggestion_review_markdown(review)

        # 规范要求的 10 个章节
        required_sections = [
            "## Summary",
            "## High Priority Manual Review",
            "## Regression Case Candidates",
            "## Memory Rule Candidates",
            "## Risk Item Candidates",
            "## Asset Dependency Waitlist",
            "## Provider / Runtime Noise",
            "## Rejected Suggestions",
            "## Manual Review Required",
            "## Next Actions",
        ]
        for section in required_sections:
            assert section in md, f"Markdown 缺少章节: {section}"

    def test_markdown_includes_bottom_disclaimers(self):
        """Markdown 底部包含所有重要声明。"""
        suggestions_report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
        ])
        review = build_memory_suggestion_review_report(suggestions_report)
        md = render_memory_suggestion_review_markdown(review)

        for keyword in [
            "不自动执行任何操作",
            "不会自动修改",
            "不会自动晋升",
            "不会自动接入 fast gate",
        ]:
            assert keyword in md, f"Markdown 底部缺少声明: {keyword}"

    def test_markdown_empty_report_does_not_crash(self):
        """空报告的 Markdown 渲染不会崩溃。"""
        suggestions_report = build_memory_suggestions_report([])
        review = build_memory_suggestion_review_report(suggestions_report)
        md = render_memory_suggestion_review_markdown(review)
        assert len(md) > 0
        assert "## Summary" in md

    def test_markdown_table_includes_suggested_owner_column(self):
        """Markdown 表格包含 suggested_owner 列。"""
        suggestions_report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
        ])
        review = build_memory_suggestion_review_report(suggestions_report)
        md = render_memory_suggestion_review_markdown(review)
        assert "suggested_owner" in md

    def test_refusal_appears_in_both_regression_and_risk_sections(self):
        """refusal_expected_but_answered 出现在回归和风险两个章节中。"""
        suggestions_report = build_memory_suggestions_report([
            _failed_case("C001", "refusal_expected_but_answered", "DROP TABLE"),
        ])
        review = build_memory_suggestion_review_report(suggestions_report)
        md = render_memory_suggestion_review_markdown(review)

        # 应同时出现在 Regression Case Candidates 和 Risk Item Candidates
        regression_section = md.split("## Regression Case Candidates")[1].split("## ")[0]
        risk_section = md.split("## Risk Item Candidates")[1].split("## ")[0]

        assert "C001" in regression_section, "refusal 应出现在 Regression Case Candidates"
        assert "C001" in risk_section, "refusal 应出现在 Risk Item Candidates"


# ═══════════════════════════════════════════════════════════════
# 测试 16: 不允许静默忽略
# ═══════════════════════════════════════════════════════════════


class TestNoSilentIgnore:
    """验证所有 suggestion 都必须产生 review item。"""

    def test_all_suggestions_produce_review_item(self):
        """测试 16: 所有 suggestion 都必须产生 review item。"""
        cases = [
            _failed_case("C01", "intent_mismatch"),
            _failed_case("C02", "plan_mismatch"),
            _failed_case("C03", "table_mismatch"),
            _failed_case("C04", "field_mismatch"),
            _failed_case("C05", "clarification_expected_but_answered"),
            _failed_case("C06", "refusal_expected_but_answered"),
            _failed_case("C07", "confidence_out_of_range"),
            _failed_case("C08", "schema_validation_failed"),
            _failed_case("C09", "safety_validation_failed"),
            _failed_case("C10", "raw_output_parse_failed"),
            _failed_case("C11", "execution_failed"),
            _failed_case("C12", "explain_failed"),
            _failed_case("C13", "completely_unknown_type"),
        ]
        suggestions_report = build_memory_suggestions_report(cases)
        review = build_memory_suggestion_review_report(suggestions_report)

        assert review["summary"]["total_suggestions"] == 13
        assert review["summary"]["total_reviewed"] == 13
        assert len(review["review_items"]) == 13

        # 每条都有非空的 review_action
        for item in review["review_items"]:
            assert len(item["review_action"]) > 0, (
                f"{item['question_id']}: review_action 不应为空列表"
            )

    def test_unknown_type_gets_reject_not_silent_ignore(self):
        """未知类型被分类为 reject，而非静默忽略。"""
        suggestion = _make_suggestion("completely_new_failure_type", "UNK")
        result = classify_memory_suggestion_for_review(suggestion)

        assert result["review_action"] == ["reject"]
        assert result["manual_review_required"] is True
        assert result["suggested_owner"] == "unknown"


# ═══════════════════════════════════════════════════════════════
# 报告构建测试
# ═══════════════════════════════════════════════════════════════


class TestReportBuilding:
    """验证 build_memory_suggestion_review_report 逻辑。"""

    def test_build_report_with_multiple_cases(self):
        """多 case 报告正确统计 summary。"""
        cases = [
            _failed_case("C001", "intent_mismatch"),
            _failed_case("C002", "safety_validation_failed"),
            _failed_case("C003", "execution_failed"),
            _failed_case("C004", "refusal_expected_but_answered"),
            _failed_case("C005", "confidence_out_of_range"),
        ]
        suggestions_report = build_memory_suggestions_report(cases)
        review = build_memory_suggestion_review_report(suggestions_report)

        assert review["summary"]["total_suggestions"] == 5
        assert review["summary"]["total_reviewed"] == 5

        counts = review["summary"]["action_counts"]
        # refusal 产生 2 个 action，其余各 1 个 → 总计 6
        total_actions = sum(counts.values())
        assert total_actions == 6, f"action 总数应为 6，实际: {total_actions}"

    def test_empty_suggestions_report(self):
        """空 suggestions 报告产生空审查报告。"""
        suggestions_report = build_memory_suggestions_report([])
        review = build_memory_suggestion_review_report(suggestions_report)

        assert review["summary"]["total_suggestions"] == 0
        assert review["summary"]["total_reviewed"] == 0
        assert len(review["review_items"]) == 0

    def test_report_includes_run_id_and_timestamp(self):
        """报告包含 run_id 和 timestamp。"""
        suggestions_report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
        ])
        review = build_memory_suggestion_review_report(suggestions_report)

        assert review["run_id"].startswith("memory-review-")
        assert review["timestamp"].endswith("Z") or "+" in review["timestamp"]

    def test_high_priority_manual_review_contains_correct_items(self):
        """High Priority Manual Review 包含 priority=high 或 manual_review_required 的条目。"""
        suggestions_report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),        # medium, not manual
            _failed_case("C002", "safety_validation_failed"),  # high + manual
            _failed_case("C003", "refusal_expected_but_answered"),  # high + manual
            _failed_case("C004", "clarification_expected_but_answered"),  # high
        ])
        review = build_memory_suggestion_review_report(suggestions_report)

        high_priority_ids = [
            item["question_id"] for item in review["high_priority_manual_review"]
        ]
        assert "C002" in high_priority_ids
        assert "C003" in high_priority_ids
        assert "C004" in high_priority_ids
        assert "C001" not in high_priority_ids


# ═══════════════════════════════════════════════════════════════
# 加载 & 校验测试
# ═══════════════════════════════════════════════════════════════


class TestLoadSnapshot:
    """验证 load_memory_suggestions_snapshot 的校验逻辑。"""

    def test_load_valid_snapshot(self, tmp_path):
        """正常加载有效的 snapshot 文件。"""
        suggestions_report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
        ])
        from harness.memory_suggestions import render_memory_suggestions_json
        payload = render_memory_suggestions_json(suggestions_report)
        snapshot = tmp_path / "test_snapshot.json"
        snapshot.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        loaded = load_memory_suggestions_snapshot(snapshot)
        assert loaded["run_id"] == suggestions_report["run_id"]
        assert len(loaded["suggestions"]) == 1

    def test_load_missing_file_raises(self):
        """不存在的文件抛出 FileNotFoundError。"""
        try:
            load_memory_suggestions_snapshot(Path("/nonexistent/path.json"))
            assert False, "应该抛出异常"
        except FileNotFoundError:
            pass

    def test_load_file_without_suggestions_field_raises(self, tmp_path):
        """缺少 suggestions 字段的文件抛出 ValueError。"""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text('{"run_id": "test", "not_suggestions": []}', encoding="utf-8")
        try:
            load_memory_suggestions_snapshot(bad_file)
            assert False, "应该抛出异常"
        except ValueError as exc:
            assert "suggestions" in str(exc)


# ═══════════════════════════════════════════════════════════════
# Snapshot 写入测试
# ═══════════════════════════════════════════════════════════════


class TestSnapshotWriting:
    """验证 snapshot 文件写入。"""

    def test_write_snapshot_creates_timestamped_files(self, tmp_path):
        """写入 snapshot 产生带 timestamp 的文件。"""
        suggestions_report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
        ])
        review = build_memory_suggestion_review_report(suggestions_report)
        output_dir = tmp_path / "reviews"
        paths = write_memory_suggestion_review_snapshot(review, output_dir)

        assert paths["json"].exists()
        assert paths["markdown"].exists()
        assert "memory_suggestion_review_" in paths["json"].name
        assert paths["json"].suffix == ".json"
        assert paths["markdown"].suffix == ".md"

    def test_write_snapshot_does_not_create_latest(self, tmp_path):
        """snapshot 写入不生成 latest 文件。"""
        suggestions_report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
        ])
        review = build_memory_suggestion_review_report(suggestions_report)
        output_dir = tmp_path / "reviews"
        write_memory_suggestion_review_snapshot(review, output_dir)

        assert not (output_dir / "memory_suggestion_review_latest.json").exists()
        assert not (output_dir / "memory_suggestion_review_latest.md").exists()

    def test_snapshot_json_content_is_valid(self, tmp_path):
        """snapshot JSON 内容正确。"""
        suggestions_report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
        ])
        review = build_memory_suggestion_review_report(suggestions_report)
        output_dir = tmp_path / "reviews"
        paths = write_memory_suggestion_review_snapshot(review, output_dir)

        content = json.loads(paths["json"].read_text(encoding="utf-8"))
        assert content["summary"]["total_suggestions"] == 1
        assert len(content["review_items"]) == 1


# ═══════════════════════════════════════════════════════════════
# CLI 集成测试（测试 12-15）
# ═══════════════════════════════════════════════════════════════


class TestCLI:
    """验证 CLI 行为。"""

    def _create_suggestions_snapshot(self, tmp_path: Path) -> Path:
        """在临时目录中创建 memory suggestions snapshot JSON。"""
        from harness.memory_suggestions import (
            render_memory_suggestions_json,
            build_memory_suggestions_report,
        )
        suggestions_report = build_memory_suggestions_report([
            _failed_case("CLI-001", "intent_mismatch", "测试意图错误"),
            _failed_case("CLI-002", "safety_validation_failed", "安全测试"),
            _failed_case("CLI-003", "execution_failed", "执行失败"),
            _failed_case("CLI-004", "refusal_expected_but_answered", "DROP TABLE"),
            _failed_case("CLI-005", "confidence_out_of_range", "置信度超出范围"),
        ])
        payload = render_memory_suggestions_json(suggestions_report)
        snapshot = tmp_path / "memory_suggestions_test.json"
        snapshot.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return snapshot

    def test_cli_generates_timestamp_snapshot(self, tmp_path):
        """测试 12: CLI 只生成 timestamp snapshot。"""
        input_file = self._create_suggestions_snapshot(tmp_path)
        output_dir = tmp_path / "reviews"

        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_suggestion_review.py",
                "--input", str(input_file),
                "--output-dir", str(output_dir),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "total_suggestions: 5" in result.stdout

        json_files = list(output_dir.glob("memory_suggestion_review_*.json"))
        md_files = list(output_dir.glob("memory_suggestion_review_*.md"))
        assert len(json_files) == 1
        assert len(md_files) == 1

    def test_cli_does_not_create_latest(self, tmp_path):
        """测试 13: CLI 不生成 latest 文件。"""
        input_file = self._create_suggestions_snapshot(tmp_path)
        output_dir = tmp_path / "reviews"

        subprocess.run(
            [
                sys.executable,
                "harness/run_memory_suggestion_review.py",
                "--input", str(input_file),
                "--output-dir", str(output_dir),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert not (output_dir / "memory_suggestion_review_latest.json").exists()
        assert not (output_dir / "memory_suggestion_review_latest.md").exists()

    def test_cli_does_not_modify_docs_memory(self, tmp_path):
        """测试 14: CLI 不修改 docs/memory/*。"""
        input_file = self._create_suggestions_snapshot(tmp_path)
        output_dir = tmp_path / "reviews"

        real_rules = PROJECT_ROOT / "docs" / "memory" / "memory_rules.yml"
        if real_rules.exists():
            before = real_rules.read_text(encoding="utf-8")

        subprocess.run(
            [
                sys.executable,
                "harness/run_memory_suggestion_review.py",
                "--input", str(input_file),
                "--output-dir", str(output_dir),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if real_rules.exists():
            after = real_rules.read_text(encoding="utf-8")
            assert before == after, "memory_rules.yml 被 CLI 修改了！"

    def test_cli_rejects_latest_input(self, tmp_path):
        """测试 15: CLI 拒绝读取 *_latest.* 文件。"""
        # 创建一个名为 latest 的文件
        input_file = tmp_path / "memory_suggestions_latest.json"
        from harness.memory_suggestions import (
            render_memory_suggestions_json,
            build_memory_suggestions_report,
        )
        suggestions_report = build_memory_suggestions_report([
            _failed_case("CLI-001", "intent_mismatch"),
        ])
        payload = render_memory_suggestions_json(suggestions_report)
        input_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_suggestion_review.py",
                "--input", str(input_file),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 1
        assert "latest" in result.stderr.lower()

    def test_cli_handles_missing_input_file(self):
        """CLI 对不存在的输入文件返回 1。"""
        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_suggestion_review.py",
                "--input", "nonexistent_file.json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 1
        assert "ERROR" in result.stderr

    def test_cli_output_includes_action_counts(self, tmp_path):
        """CLI 输出包含 review action 分布统计。"""
        input_file = self._create_suggestions_snapshot(tmp_path)
        output_dir = tmp_path / "reviews"

        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_suggestion_review.py",
                "--input", str(input_file),
                "--output-dir", str(output_dir),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Review Action" in result.stdout
        assert "accept_as_regression_case" in result.stdout
        assert "accept_as_risk_item" in result.stdout

    def test_cli_handles_bad_json_input(self, tmp_path):
        """CLI 对格式不正确的 JSON 返回 1。"""
        bad_file = tmp_path / "bad_input.json"
        bad_file.write_text('{"not_valid": true}', encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_suggestion_review.py",
                "--input", str(bad_file),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 1
        assert "ERROR" in result.stderr


# ═══════════════════════════════════════════════════════════════
# 边界条件测试
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """验证边界条件处理。"""

    def test_mixed_failure_types_all_classified(self):
        """混合多种失败类型的 report 中每条都有有效的 review_action。"""
        suggestions_report = build_memory_suggestions_report([
            _failed_case(f"C{i:02d}", ft)
            for i, ft in enumerate([
                "intent_mismatch",
                "plan_mismatch",
                "table_mismatch",
                "field_mismatch",
                "clarification_expected_but_answered",
                "refusal_expected_but_answered",
                "confidence_out_of_range",
                "schema_validation_failed",
                "safety_validation_failed",
                "raw_output_parse_failed",
                "execution_failed",
                "explain_failed",
            ])
        ])
        review = build_memory_suggestion_review_report(suggestions_report)

        assert review["summary"]["total_reviewed"] == 12

        # 没有 review_item 被遗漏
        valid_actions = set(REVIEW_ACTION_META.keys())
        for item in review["review_items"]:
            for action in item["review_action"]:
                assert action in valid_actions, (
                    f"{item['question_id']}: 无效的 review_action: {action}"
                )

    def test_review_never_reads_latest_files(self):
        """审查生成过程不读取任何 latest 文件。"""
        from unittest.mock import patch

        original_read_text = Path.read_text

        def guarded_read_text(path, *args, **kwargs):
            path_text = str(path).replace("\\", "/")
            if "latest" in path.name.lower():
                raise AssertionError(f"不应读取 latest 文件: {path}")
            return original_read_text(path, *args, **kwargs)

        suggestions_report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
        ])
        with patch.object(Path, "read_text", guarded_read_text):
            build_memory_suggestion_review_report(suggestions_report)

    def test_all_review_actions_have_meta_entries(self):
        """所有 6 种 review_action 在 REVIEW_ACTION_META 中都有定义。"""
        expected = {
            "accept_as_regression_case",
            "accept_as_memory_rule_candidate",
            "accept_as_risk_item",
            "asset_dependency_wait",
            "provider_runtime_noise",
            "reject",
        }
        assert set(REVIEW_ACTION_META.keys()) == expected

    def test_explain_failed_safety_boundary_detection(self):
        """explain_failed 在涉及安全边界时被分类为 memory_rule_candidate。"""
        # 构造一个涉及 result_fusion 安全边界的 explain_failed suggestion
        from harness.memory_suggestions import build_suggested_memory_rule
        suggestion = {
            "question_id": "EXP-001",
            "question": "测试安全越权解释",
            "failure_type": "explain_failed",
            "raw_failure_type": None,
            "root_cause_hint": "result_fusion 安全边界被越过",
            "recommended_action": "修 result_fusion prompt 或 explanation validator",
            "regression_candidate": True,
            "asset_dependency": False,
            "manual_review_required": False,
            "suggested_memory_rule": build_suggested_memory_rule(
                title="测试规则",
                failure_type="explain_failed",
                root_cause_hint="result_fusion 安全边界被越过",
                source_failure_case="EXP-001: 测试安全越权解释",
                notes="涉及 safety boundary",
            ),
        }

        result = classify_memory_suggestion_for_review(suggestion)
        assert result["review_action"] == ["accept_as_memory_rule_candidate"]
        assert result["suggested_owner"] == "safety"
        assert result["manual_review_required"] is True

    def test_explain_failed_without_safety_is_regression(self):
        """explain_failed 不涉及安全边界时被分类为 regression_case。"""
        suggestion = _make_suggestion("explain_failed", "EXP-002")
        result = classify_memory_suggestion_for_review(suggestion)

        assert result["review_action"] == ["accept_as_regression_case"]
        assert result["suggested_owner"] == "prompt"
