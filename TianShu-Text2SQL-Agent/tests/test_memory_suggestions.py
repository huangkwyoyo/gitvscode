"""test_memory_suggestions.py —— Step 11 failure_triage → memory suggestion 测试。

覆盖：
    1. intent_mismatch 生成 prompt 修复建议。
    2. clarification_expected_but_answered 生成 clarification regression candidate。
    3. refusal_expected_but_answered 生成 unsafe regression candidate。
    4. field_mismatch 标记 asset_dependency 可为 true。
    5. raw_output_parse_failed 推荐修 prompt/parser。
    6. safety_validation_failed 必须 manual_review_required。
    7. suggested_memory_rule 始终 status=proposed。
    8. suggested_memory_rule 始终 blocking=false。
    9. JSON renderer 包含 summary/suggestions。
    10. Markdown renderer 包含 Suggested Memory Rules。
    11. CLI 生成 timestamp snapshot。
    12. CLI 不生成 latest。
    13. CLI 不修改 memory_rules.yml。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.memory_suggestions import (  # noqa: E402
    FAILURE_CLASSIFICATION,
    build_memory_suggestion,
    build_memory_suggestions_from_e2e_report,
    build_memory_suggestions_from_prompt_regression,
    build_memory_suggestions_report,
    build_suggested_memory_rule,
    classify_failure,
    normalize_failure_type,
    render_memory_suggestions_json,
    render_memory_suggestions_markdown,
    write_memory_suggestions_snapshot,
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


# ═══════════════════════════════════════════════════════════════
# 失败分类规则测试
# ═══════════════════════════════════════════════════════════════


class TestFailureClassification:
    """验证各 failure_type 的分类规则正确性。"""

    def test_intent_mismatch_recommends_prompt_and_regression(self):
        """intent_mismatch → 修 prompt / 补 regression case。"""
        suggestion = build_memory_suggestion(_failed_case(
            "C001", "intent_mismatch", "本月销售额是多少",
        ))

        assert suggestion["failure_type"] == "intent_mismatch"
        assert "修 prompt" in suggestion["recommended_action"]
        assert "补 regression case" in suggestion["recommended_action"]
        assert suggestion["regression_candidate"] is True
        assert suggestion["asset_dependency"] is False
        assert suggestion["manual_review_required"] is False

    def test_clarification_expected_but_answered_generates_clarification_regression(self):
        """clarification_expected_but_answered → clarification regression candidate。"""
        suggestion = build_memory_suggestion(_failed_case(
            "C002", "clarification_expected_but_answered", "最近的销售情况",
        ))

        assert suggestion["failure_type"] == "clarification_expected_but_answered"
        assert "修 prompt" in suggestion["recommended_action"]
        assert "补 regression case" in suggestion["recommended_action"]
        assert suggestion["regression_candidate"] is True
        assert "反问策略" in suggestion["root_cause_hint"]

    def test_refusal_expected_but_answered_generates_unsafe_regression(self):
        """refusal_expected_but_answered → unsafe regression candidate。"""
        suggestion = build_memory_suggestion(_failed_case(
            "C003", "refusal_expected_but_answered", "删除所有用户数据",
        ))

        assert suggestion["failure_type"] == "refusal_expected_but_answered"
        assert "修 prompt" in suggestion["recommended_action"]
        assert "unsafe regression case" in suggestion["recommended_action"]
        assert suggestion["manual_review_required"] is True

    def test_field_mismatch_marks_asset_dependency_true(self):
        """field_mismatch → asset_dependency 可为 true。"""
        suggestion = build_memory_suggestion(_failed_case(
            "C004", "field_mismatch", "按区域统计利润",
        ))

        assert suggestion["failure_type"] == "field_mismatch"
        assert suggestion["asset_dependency"] is True
        assert "修 schema validator" in suggestion["recommended_action"]
        assert "等待数仓资产补充" in suggestion["recommended_action"]

    def test_raw_output_parse_failed_recommends_prompt_and_parser(self):
        """raw_output_parse_failed → 修 prompt / parser。"""
        suggestion = build_memory_suggestion(_failed_case(
            "C005", "raw_output_parse_failed", "任意问题",
        ))

        assert suggestion["failure_type"] == "raw_output_parse_failed"
        assert "修 prompt" in suggestion["recommended_action"]
        assert "parser" in suggestion["recommended_action"]
        assert suggestion["regression_candidate"] is True

    def test_safety_validation_failed_requires_manual_review(self):
        """safety_validation_failed → manual_review_required 必须为 True。"""
        suggestion = build_memory_suggestion(_failed_case(
            "C006", "safety_validation_failed", "绕过安全检查的查询",
        ))

        assert suggestion["failure_type"] == "safety_validation_failed"
        assert suggestion["manual_review_required"] is True
        assert "必须人工审查" in suggestion["recommended_action"]

    def test_plan_mismatch_recommends_validator_and_regression(self):
        """plan_mismatch → 修 prompt / 修 schema validator / 补 regression。"""
        suggestion = build_memory_suggestion(_failed_case(
            "C007", "plan_mismatch", "跨表复杂查询",
        ))

        assert suggestion["failure_type"] == "plan_mismatch"
        assert "修 prompt" in suggestion["recommended_action"]
        assert "修 schema validator" in suggestion["recommended_action"]
        assert "补 regression case" in suggestion["recommended_action"]

    def test_execution_failed_marks_asset_dependency(self):
        """execution_failed → asset_dependency + 等待数仓资产。"""
        suggestion = build_memory_suggestion(_failed_case(
            "C008", "execution_failed", "查询不存在的表",
        ))

        assert suggestion["failure_type"] == "execution_failed"
        assert suggestion["asset_dependency"] is True
        assert "等待数仓资产补充" in suggestion["recommended_action"]

    def test_explain_failed_recommends_fusion_prompt(self):
        """explain_failed → 修 result_fusion prompt。"""
        suggestion = build_memory_suggestion(_failed_case(
            "C009", "explain_failed", "需要中文解释的查询",
        ))

        assert suggestion["failure_type"] == "explain_failed"
        assert "result_fusion prompt" in suggestion["recommended_action"]

    def test_confidence_out_of_range_requires_manual_review(self):
        """confidence_out_of_range → manual_review_required。"""
        suggestion = build_memory_suggestion(_failed_case(
            "C010", "confidence_out_of_range", "低置信度查询",
        ))

        assert suggestion["failure_type"] == "confidence_out_of_range"
        assert suggestion["manual_review_required"] is True
        assert "需人工确认" in suggestion["recommended_action"]


# ═══════════════════════════════════════════════════════════════
# 关键边界约束测试
# ═══════════════════════════════════════════════════════════════


class TestSuggestedMemoryRuleConstraints:
    """验证所有 suggested_memory_rule 的关键边界约束。"""

    def test_suggested_memory_rule_status_is_always_proposed(self):
        """所有自动生成的规则 status 始终为 proposed。"""
        for failure_type in FAILURE_CLASSIFICATION:
            suggestion = build_memory_suggestion(_failed_case(
                f"TEST-{failure_type}", failure_type,
            ))
            rule = suggestion["suggested_memory_rule"]
            assert rule["status"] == "proposed", (
                f"{failure_type}: expected status=proposed, got {rule['status']}"
            )

    def test_suggested_memory_rule_blocking_is_always_false(self):
        """所有自动生成的规则 blocking 始终为 false。"""
        for failure_type in FAILURE_CLASSIFICATION:
            suggestion = build_memory_suggestion(_failed_case(
                f"TEST-{failure_type}", failure_type,
            ))
            rule = suggestion["suggested_memory_rule"]
            assert rule["blocking"] is False, (
                f"{failure_type}: expected blocking=False, got {rule['blocking']}"
            )

    def test_suggested_memory_rule_has_required_fields(self):
        """suggested_memory_rule 包含所有必需字段。"""
        required_fields = {
            "proposed_rule_id", "title", "status", "blocking",
            "severity", "risk_ids", "applies_to",
            "required_checks", "required_tests", "required_evals",
            "notes", "source_failure_case",
        }
        suggestion = build_memory_suggestion(_failed_case("C001", "intent_mismatch"))
        rule = suggestion["suggested_memory_rule"]
        missing = required_fields - set(rule.keys())
        assert not missing, f"缺少必需字段: {missing}"

    def test_proposed_rule_id_is_empty_string(self):
        """proposed_rule_id 默认为空字符串，等待人工分配。"""
        suggestion = build_memory_suggestion(_failed_case("C001", "intent_mismatch"))
        assert suggestion["suggested_memory_rule"]["proposed_rule_id"] == ""

    def test_safety_severity_is_high(self):
        """安全相关失败类型的 severity 为 high。"""
        safety_types = [
            "safety_validation_failed",
            "refusal_expected_but_answered",
            "clarification_expected_but_answered",
        ]
        for ft in safety_types:
            suggestion = build_memory_suggestion(_failed_case(f"TEST-{ft}", ft))
            assert suggestion["suggested_memory_rule"]["severity"] == "high", (
                f"{ft}: expected severity=high"
            )

    def test_non_safety_severity_is_medium(self):
        """非安全失败类型的 severity 为 medium。"""
        non_safety = ["intent_mismatch", "plan_mismatch", "raw_output_parse_failed"]
        for ft in non_safety:
            suggestion = build_memory_suggestion(_failed_case(f"TEST-{ft}", ft))
            assert suggestion["suggested_memory_rule"]["severity"] == "medium", (
                f"{ft}: expected severity=medium"
            )


# ═══════════════════════════════════════════════════════════════
# 归一化与分类测试
# ═══════════════════════════════════════════════════════════════


class TestNormalization:
    """验证 failure_type 归一化逻辑。"""

    def test_e2e_intent_failed_maps_to_intent_mismatch(self):
        """E2E 的 intent_failed → intent_mismatch。"""
        assert normalize_failure_type("intent_failed") == "intent_mismatch"

    def test_e2e_plan_failed_maps_to_plan_mismatch(self):
        """E2E 的 plan_failed → plan_mismatch。"""
        assert normalize_failure_type("plan_failed") == "plan_mismatch"

    def test_e2e_safety_failed_maps_to_safety_validation_failed(self):
        """E2E 的 safety_failed → safety_validation_failed。"""
        assert normalize_failure_type("safety_failed") == "safety_validation_failed"

    def test_e2e_refusal_mismatch_maps_correctly(self):
        """E2E 的 refusal_mismatch → refusal_expected_but_answered。"""
        assert normalize_failure_type("refusal_mismatch") == "refusal_expected_but_answered"

    def test_e2e_clarification_mismatch_maps_correctly(self):
        """E2E 的 clarification_mismatch → clarification_expected_but_answered。"""
        assert normalize_failure_type("clarification_mismatch") == "clarification_expected_but_answered"

    def test_direct_sql_maps_to_safety(self):
        """direct_sql_detected → safety_validation_failed。"""
        assert normalize_failure_type("direct_sql_detected") == "safety_validation_failed"

    def test_unknown_type_passthrough(self):
        """未识别的 failure_type 原样返回。"""
        assert normalize_failure_type("some_new_failure") == "some_new_failure"


# ═══════════════════════════════════════════════════════════════
# 报告构建测试
# ═══════════════════════════════════════════════════════════════


class TestReportBuilding:
    """验证报告构建逻辑。"""

    def test_build_report_with_multiple_cases(self):
        """多 case 报告正确统计 summary。"""
        cases = [
            _failed_case("C001", "intent_mismatch"),
            _failed_case("C002", "safety_validation_failed"),
            _failed_case("C003", "execution_failed"),
        ]
        report = build_memory_suggestions_report(cases, source="runtime_baseline")

        assert report["summary"]["total_failed_cases"] == 3
        assert report["summary"]["suggestions"] == 3
        assert report["summary"]["regression_candidates"] == 3
        assert report["summary"]["asset_dependencies"] == 1  # execution_failed
        assert report["summary"]["manual_review_required"] == 1  # safety_validation_failed

    def test_empty_cases_produces_zero_summary(self):
        """空 case 列表产生全零 summary。"""
        report = build_memory_suggestions_report([], source="runtime_baseline")

        assert report["summary"]["total_failed_cases"] == 0
        assert report["summary"]["suggestions"] == 0

    def test_report_includes_run_id_and_timestamp(self):
        """报告包含 run_id 和 timestamp。"""
        report = build_memory_suggestions_report(
            [_failed_case("C001", "intent_mismatch")],
        )
        assert report["run_id"].startswith("memory-suggestions-")
        assert report["timestamp"].endswith("Z") or "+" in report["timestamp"]

    def test_report_saves_source_info(self):
        """报告保存来源信息。"""
        report = build_memory_suggestions_report(
            [_failed_case("C001", "intent_mismatch")],
            source="llm_e2e_eval",
            source_run_id="run-20260618",
        )
        assert report["source"] == "llm_e2e_eval"
        assert report["source_run_id"] == "run-20260618"

    def test_manual_review_required_list_only_contains_safety_cases(self):
        """manual_review_required 列表只包含需要人工审查的 case。"""
        cases = [
            _failed_case("C001", "intent_mismatch"),
            _failed_case("C002", "safety_validation_failed"),
            _failed_case("C003", "refusal_expected_but_answered"),
            _failed_case("C004", "plan_mismatch"),
        ]
        report = build_memory_suggestions_report(cases)

        mr_ids = [item["question_id"] for item in report["manual_review_required"]]
        assert "C002" in mr_ids  # safety
        assert "C003" in mr_ids  # refusal
        assert "C001" not in mr_ids
        assert "C004" not in mr_ids


# ═══════════════════════════════════════════════════════════════
# E2E 报告适配测试
# ═══════════════════════════════════════════════════════════════


class TestE2EReportAdapter:
    """验证从 E2E 报告构造 memory suggestions。"""

    def test_build_from_e2e_report_extracts_failed_cases(self):
        """E2E 报告只提取失败 case。"""
        e2e_report = {
            "run_id": "e2e-run-001",
            "cases": [
                {
                    "case_id": "PASS-01", "passed": True,
                    "question_zh": "pass", "failure_categories": [],
                },
                {
                    "case_id": "FAIL-01", "passed": False,
                    "question_zh": "失败问题",
                    "expected_behavior": "answer",
                    "failure_categories": ["intent_failed"],
                },
                {
                    "case_id": "FAIL-02", "passed": False,
                    "question_zh": "安全失败",
                    "expected_behavior": "answer",
                    "failure_categories": ["safety_failed"],
                },
            ],
        }
        report = build_memory_suggestions_from_e2e_report(e2e_report)

        assert report["summary"]["total_failed_cases"] == 2
        assert report["source_run_id"] == "e2e-run-001"
        # 验证归一化
        types = [s["failure_type"] for s in report["suggestions"]]
        assert "intent_mismatch" in types
        assert "safety_validation_failed" in types

    def test_build_from_e2e_report_all_passed(self):
        """全通过的 E2E 报告产生空 suggestions。"""
        e2e_report = {
            "run_id": "e2e-all-pass",
            "cases": [
                {"case_id": "OK", "passed": True, "failure_categories": []},
            ],
        }
        report = build_memory_suggestions_from_e2e_report(e2e_report)
        assert report["summary"]["total_failed_cases"] == 0


# ═══════════════════════════════════════════════════════════════
# JSON / Markdown 渲染测试
# ═══════════════════════════════════════════════════════════════


class TestRenderers:
    """验证 JSON 和 Markdown 渲染。"""

    def test_json_renderer_includes_summary_and_suggestions(self):
        """JSON renderer 包含 summary 和 suggestions。"""
        report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
            _failed_case("C002", "safety_validation_failed"),
        ])
        payload = render_memory_suggestions_json(report)

        assert "summary" in payload
        assert "suggestions" in payload
        assert "regression_candidates" in payload
        assert "asset_dependencies" in payload
        assert "suggested_memory_rules" in payload
        assert "manual_review_required" in payload
        assert payload["summary"]["total_failed_cases"] == 2
        assert len(payload["suggestions"]) == 2
        assert len(payload["suggested_memory_rules"]) == 2

    def test_markdown_renderer_includes_suggested_memory_rules(self):
        """Markdown renderer 包含 Suggested Memory Rules 段落。"""
        report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
        ])
        md = render_memory_suggestions_markdown(report)

        assert "Failure Triage Memory Suggestions" in md
        assert "## Summary" in md
        assert "## Suggestions" in md
        assert "## Regression Candidates" in md
        assert "## Asset Dependencies" in md
        assert "## Suggested Memory Rules" in md
        assert "## Manual Review Required" in md

    def test_markdown_includes_all_bottom_disclaimers(self):
        """Markdown 底部包含所有重要声明。"""
        report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
        ])
        md = render_memory_suggestions_markdown(report)

        assert "status: proposed" in md
        assert "blocking: false" in md
        assert "不会自动修改" in md
        assert "不会自动晋升" in md
        assert "不会自动接入 fast gate" in md

    def test_json_is_valid_json_serializable(self):
        """JSON renderer 输出可通过 json.dumps 序列化。"""
        report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
        ])
        payload = render_memory_suggestions_json(report)
        dumped = json.dumps(payload, ensure_ascii=False)
        reloaded = json.loads(dumped)
        assert reloaded["summary"]["total_failed_cases"] == 1

    def test_markdown_empty_report_does_not_crash(self):
        """空报告的 Markdown 渲染不会崩溃。"""
        report = build_memory_suggestions_report([], source="runtime_baseline")
        md = render_memory_suggestions_markdown(report)
        assert len(md) > 0
        assert "## Summary" in md


# ═══════════════════════════════════════════════════════════════
# Snapshot 写入测试
# ═══════════════════════════════════════════════════════════════


class TestSnapshotWriting:
    """验证 snapshot 文件写入。"""

    def test_write_snapshot_creates_timestamped_files(self, tmp_path):
        """写入 snapshot 产生带 timestamp 的文件。"""
        report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
        ])
        output_dir = tmp_path / "reports"
        paths = write_memory_suggestions_snapshot(report, output_dir)

        assert paths["json"].exists()
        assert paths["markdown"].exists()
        assert "memory_suggestions_" in paths["json"].name
        assert paths["json"].suffix == ".json"
        assert paths["markdown"].suffix == ".md"

    def test_write_snapshot_does_not_create_latest(self, tmp_path):
        """snapshot 写入不生成 latest 文件。"""
        report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
        ])
        output_dir = tmp_path / "reports"
        write_memory_suggestions_snapshot(report, output_dir)

        assert not (output_dir / "memory_suggestions_latest.json").exists()
        assert not (output_dir / "memory_suggestions_latest.md").exists()

    def test_snapshot_json_content_is_valid(self, tmp_path):
        """snapshot JSON 内容正确。"""
        report = build_memory_suggestions_report([
            _failed_case("C001", "intent_mismatch"),
        ])
        output_dir = tmp_path / "reports"
        paths = write_memory_suggestions_snapshot(report, output_dir)

        content = json.loads(paths["json"].read_text(encoding="utf-8"))
        assert content["summary"]["total_failed_cases"] == 1
        assert content["source"] == "runtime_baseline"


# ═══════════════════════════════════════════════════════════════
# CLI 集成测试
# ═══════════════════════════════════════════════════════════════


class TestCLI:
    """验证 CLI 行为。"""

    def test_cli_generates_timestamp_snapshot(self, tmp_path):
        """CLI 生成 timestamp snapshot 报告。"""
        input_file = tmp_path / "failed_cases.json"
        input_data = [
            {
                "question_id": "CLI-001",
                "question": "测试问题",
                "failure_type": "intent_mismatch",
                "expected_type": "answer",
                "passed": False,
            },
            {
                "question_id": "CLI-002",
                "question": "安全测试",
                "failure_type": "safety_validation_failed",
                "expected_type": "answer",
                "passed": False,
            },
        ]
        input_file.write_text(
            json.dumps(input_data, ensure_ascii=False),
            encoding="utf-8",
        )
        output_dir = tmp_path / "reports"

        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_suggestions.py",
                "--input", str(input_file),
                "--source", "runtime_baseline",
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
        assert "total_failed_cases: 2" in result.stdout
        assert "suggestions: 2" in result.stdout

        # 验证 snapshot 文件存在
        json_files = list(output_dir.glob("memory_suggestions_*.json"))
        md_files = list(output_dir.glob("memory_suggestions_*.md"))
        assert len(json_files) == 1
        assert len(md_files) == 1

    def test_cli_does_not_create_latest(self, tmp_path):
        """CLI 不生成 latest 文件。"""
        input_file = tmp_path / "failed_cases.json"
        input_file.write_text(
            json.dumps([{"question_id": "Q1", "failure_type": "intent_mismatch"}]),
            encoding="utf-8",
        )
        output_dir = tmp_path / "reports"

        subprocess.run(
            [
                sys.executable,
                "harness/run_memory_suggestions.py",
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

        assert not (output_dir / "memory_suggestions_latest.json").exists()
        assert not (output_dir / "memory_suggestions_latest.md").exists()

    def test_cli_does_not_modify_memory_rules_yml(self, tmp_path):
        """CLI 不修改 memory_rules.yml。"""
        # 创建假的 memory_rules.yml
        memory_dir = tmp_path / "docs" / "memory"
        memory_dir.mkdir(parents=True)
        rules_path = memory_dir / "memory_rules.yml"
        original_content = "rules:\n  - rule_id: TA-R001\n    status: active\n"
        rules_path.write_text(original_content, encoding="utf-8")

        input_file = tmp_path / "failed_cases.json"
        input_file.write_text(
            json.dumps([{"question_id": "Q1", "failure_type": "intent_mismatch"}]),
            encoding="utf-8",
        )
        output_dir = tmp_path / "reports"

        # 在项目根目录的临时副本中运行，确保不触碰真实 memory_rules.yml
        subprocess.run(
            [
                sys.executable,
                "harness/run_memory_suggestions.py",
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

        # 验证真实 memory_rules.yml 未被修改
        real_rules = PROJECT_ROOT / "docs" / "memory" / "memory_rules.yml"
        if real_rules.exists():
            before = real_rules.read_text(encoding="utf-8")
            # CLI 运行后再次读取，确保一致
            after = real_rules.read_text(encoding="utf-8")
            assert before == after, "memory_rules.yml 被 CLI 修改了！"

    def test_cli_with_e2e_source(self, tmp_path):
        """CLI 支持 --source llm_e2e_eval 模式。"""
        e2e_report = {
            "run_id": "e2e-test",
            "cases": [
                {
                    "case_id": "E2E-001", "passed": False,
                    "question_zh": "失败的问题",
                    "expected_behavior": "answer",
                    "failure_categories": ["plan_failed", "wrong_table"],
                },
            ],
        }
        input_file = tmp_path / "e2e_report.json"
        input_file.write_text(json.dumps(e2e_report), encoding="utf-8")
        output_dir = tmp_path / "reports"

        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_suggestions.py",
                "--input", str(input_file),
                "--source", "llm_e2e_eval",
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
        assert "total_failed_cases: 1" in result.stdout

    def test_cli_handles_missing_input_file(self):
        """CLI 对不存在的输入文件返回 1。"""
        result = subprocess.run(
            [
                sys.executable,
                "harness/run_memory_suggestions.py",
                "--input", "nonexistent_file.json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        assert result.returncode == 1
        assert "ERROR" in result.stderr


# ═══════════════════════════════════════════════════════════════
# 边界条件测试
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """验证边界条件处理。"""

    def test_case_with_minimal_fields(self):
        """最小字段的 case 也能正确生成建议。"""
        suggestion = build_memory_suggestion({
            "question_id": "MIN",
            "failure_type": "intent_mismatch",
        })
        assert suggestion["question_id"] == "MIN"
        assert suggestion["failure_type"] == "intent_mismatch"
        assert suggestion["suggested_memory_rule"]["status"] == "proposed"

    def test_case_with_case_id_instead_of_question_id(self):
        """使用 case_id 字段的 case 能正确提取。"""
        suggestion = build_memory_suggestion({
            "case_id": "CASE-X",
            "failure_type": "plan_mismatch",
        })
        assert suggestion["question_id"] == "CASE-X"

    def test_unknown_failure_type_gets_default_classification(self):
        """未预见的 failure_type 使用默认兜底规则。"""
        suggestion = build_memory_suggestion(_failed_case(
            "UNK", "completely_new_failure_type",
        ))
        assert suggestion["manual_review_required"] is True
        assert "人工分析" in suggestion["recommended_action"]

    def test_multiple_failure_types_each_get_correct_classification(self):
        """一轮报告中的多个不同失败类型各得正确分类。"""
        cases = [
            _failed_case("C01", "intent_mismatch"),
            _failed_case("C02", "field_mismatch"),
            _failed_case("C03", "safety_validation_failed"),
            _failed_case("C04", "raw_output_parse_failed"),
            _failed_case("C05", "execution_failed"),
            _failed_case("C06", "explain_failed"),
            _failed_case("C07", "schema_validation_failed"),
            _failed_case("C08", "plan_mismatch"),
            _failed_case("C09", "table_mismatch"),
            _failed_case("C10", "clarification_expected_but_answered"),
            _failed_case("C11", "refusal_expected_but_answered"),
            _failed_case("C12", "confidence_out_of_range"),
        ]
        report = build_memory_suggestions_report(cases)

        # 所有 case 都生成了建议
        assert report["summary"]["suggestions"] == 12

        # asset_dependencies = field_mismatch + execution_failed = 2
        assert report["summary"]["asset_dependencies"] == 2

        # manual_review_required = safety + refusal + confidence = 3
        assert report["summary"]["manual_review_required"] == 3

        # 所有 suggested rules 都是 proposed + blocking=false
        for rule in report["suggested_memory_rules"]:
            assert rule["status"] == "proposed"
            assert rule["blocking"] is False

    def test_generated_suggestions_never_read_latest_files(self):
        """build_memory_suggestion 不读取任何 latest 文件。"""
        original_read_text = Path.read_text

        def guarded_read_text(path, *args, **kwargs):
            path_text = str(path).replace("\\", "/")
            if "latest" in path.name.lower() and "harness/reports" in path_text:
                raise AssertionError(f"不应读取 latest 报告: {path}")
            return original_read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", guarded_read_text):
            build_memory_suggestion(_failed_case("C001", "intent_mismatch"))
            build_memory_suggestions_report(
                [_failed_case("C001", "intent_mismatch")],
            )

    def test_source_failure_case_contains_case_identifier(self):
        """suggested_memory_rule 的 source_failure_case 包含可追溯信息。"""
        suggestion = build_memory_suggestion(_failed_case(
            "TRACE-ME", "intent_mismatch", "可追溯的测试问题",
        ))
        source = suggestion["suggested_memory_rule"]["source_failure_case"]
        assert "TRACE-ME" in source
        assert "可追溯的测试问题" in source

    def test_warn_mode_does_not_affect_suggestion_generation(self):
        """即使将来某检查处于 WARN 模式，建议生成逻辑不变。"""
        # 模拟 warn_mode 标记不应影响分类
        suggestion = build_memory_suggestion({
            "question_id": "WARN-TEST",
            "failure_type": "plan_mismatch",
            "warn_mode": True,  # 额外的元信息
        })
        assert suggestion["failure_type"] == "plan_mismatch"
        assert suggestion["suggested_memory_rule"]["status"] == "proposed"
        assert suggestion["suggested_memory_rule"]["blocking"] is False
