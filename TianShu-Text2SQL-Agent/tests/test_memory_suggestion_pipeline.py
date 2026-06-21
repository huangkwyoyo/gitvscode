"""test_memory_suggestion_pipeline.py —— Step 13 管道集成测试。

覆盖：
    1. 有 failed cases 时生成 suggestions + review 双报告
    2. 无 failed cases 时不生成报告（skipped summary）
    3. Runtime baseline triage items → suggestion 输入转换
    4. LLM E2E eval failed cases → suggestion 输入转换
    5. Prompt regression failed cases → suggestion 输入转换
    6. 生成文件全部是 timestamp snapshot（无 latest）
    7. 不写 docs/memory/*
    8. 不写 memory_rules.yml
    9. pipeline 异常时不吞掉原始 baseline failure
    10. provider/runtime 字段只作 metadata，不自动判定 source 代码失败
    11. 每个 failed case 都进入 suggestion/review（不静默忽略）
    12. 通用 failed case 列表可转换
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.memory_suggestion_pipeline import (  # noqa: E402
    _adapt_failed_cases_from_e2e_report,
    _adapt_failed_cases_from_failure_triage,
    _adapt_failed_cases_from_generic_list,
    _adapt_failed_cases_from_prompt_regression,
    _error_result,
    _skipped_result,
    generate_memory_reports_for_failed_cases,
    render_pipeline_summary_for_baseline,
    run_pipeline_on_failure_triage,
)


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _make_triage_item(
    case_id: str = "C001",
    failure_type: str = "intent_mismatch",
    question: str = "测试问题",
) -> dict:
    """构造最小 failure_triage item。"""
    return {
        "case_id": case_id,
        "question": question,
        "failure_type": failure_type,
        "root_cause_hint": "测试根因",
        "recommended_action": "测试建议",
        "regression_candidate": True,
        "asset_dependency": "none",
        "failure_categories": [failure_type],
    }


def _make_triage_result(items: list[dict] | None = None) -> dict:
    """构造 failure_triage 完整结果。"""
    return {
        "source": "e2e_eval_report",
        "run_id": "test-run-001",
        "total_failed": len(items or []),
        "items": items or [],
        "category_counts": {},
        "error": None,
    }


def _make_e2e_report(cases: list[dict]) -> dict:
    """构造 LLM E2E eval 报告。"""
    return {
        "run_id": "e2e-test-001",
        "timestamp": "2026-06-18T12:00:00Z",
        "provider": "deepseek",
        "model_name": "deepseek-v4-pro",
        "cases": cases,
    }


def _make_e2e_case(
    case_id: str = "C001",
    passed: bool = False,
    failure_categories: list[str] | None = None,
    expected_behavior: str = "answer",
) -> dict:
    """构造单个 E2E case。"""
    return {
        "case_id": case_id,
        "question_zh": f"测试问题_{case_id}",
        "expected_behavior": expected_behavior,
        "passed": passed,
        "failure_categories": failure_categories or [],
        "error": None,
    }


def _make_pr_report(cases: list[dict]) -> dict:
    """构造 Prompt Regression 报告。"""
    return {
        "run_id": "pr-test-001",
        "timestamp": "2026-06-18T12:00:00Z",
        "model_name": "deepseek-v4-pro",
        "cases": cases,
    }


def _make_pr_case(
    case_id: str = "C001",
    passed: bool = False,
    error: str = "",
    task: str = "intent_classifier",
    expected_type: str = "answer",
) -> dict:
    """构造单个 Prompt Regression case。"""
    return {
        "case_id": case_id,
        "task": task,
        "passed": passed,
        "error": error,
        "expected_type": expected_type,
    }


# ═══════════════════════════════════════════════════════════════
# 测试 1: 适配器 —— Runtime baseline triage items
# ═══════════════════════════════════════════════════════════════


class TestAdaptFromFailureTriage:
    """Runtime baseline failure_triage items → 标准 failed case 格式。"""

    def test_basic_triage_item(self):
        """基本 triage item 包含必需字段。"""
        items = [_make_triage_item("C001", "intent_mismatch", "测试")]
        result = _adapt_failed_cases_from_failure_triage(items)
        assert len(result) == 1
        assert result[0]["question_id"] == "C001"
        assert result[0]["question"] == "测试"
        assert result[0]["failure_type"] == "intent_mismatch"
        assert result[0]["stage"] == "runtime_baseline"

    def test_multiple_triage_items(self):
        """多个 triage items 全部转换。"""
        items = [
            _make_triage_item("C001", "intent_mismatch"),
            _make_triage_item("C002", "plan_mismatch"),
            _make_triage_item("C003", "safety_validation_failed"),
        ]
        result = _adapt_failed_cases_from_failure_triage(items)
        assert len(result) == 3
        assert {r["question_id"] for r in result} == {"C001", "C002", "C003"}

    def test_triage_failure_type_normalized(self):
        """triage 中的原始 failure_type 被归一化。"""
        items = [_make_triage_item("C001", "refusal_mismatch")]
        result = _adapt_failed_cases_from_failure_triage(items)
        assert result[0]["failure_type"] == "refusal_expected_but_answered"

    def test_empty_triage_items(self):
        """空 triage items 返回空列表。"""
        result = _adapt_failed_cases_from_failure_triage([])
        assert result == []

    def test_provider_runtime_only_metadata(self):
        """provider/runtime 字段只作为 metadata，不自动判定 source 代码失败。"""
        items = [_make_triage_item("C001", "execution_failed")]
        result = _adapt_failed_cases_from_failure_triage(items)
        # provider/model_name 为空（triage 未提供），failure_type 保持原值
        assert result[0]["provider"] == ""
        assert result[0]["model_name"] == ""
        # 不因 provider 异常而改变 failure_type
        assert result[0]["failure_type"] == "execution_failed"


# ═══════════════════════════════════════════════════════════════
# 测试 2: 适配器 —— LLM E2E eval
# ═══════════════════════════════════════════════════════════════


class TestAdaptFromE2EReport:
    """LLM E2E eval JSON → 标准 failed case 格式。"""

    def test_e2e_single_failed_case(self):
        """单个 E2E 失败 case 正确转换。"""
        report = _make_e2e_report([
            _make_e2e_case("E001", passed=False, failure_categories=["intent_failed"]),
            _make_e2e_case("E002", passed=True),
        ])
        result = _adapt_failed_cases_from_e2e_report(report)
        assert len(result) == 1
        assert result[0]["question_id"] == "E001"
        assert result[0]["failure_type"] == "intent_failed"
        assert result[0]["stage"] == "llm_e2e_eval"
        assert result[0]["provider"] == "deepseek"
        assert result[0]["model_name"] == "deepseek-v4-pro"

    def test_e2e_all_passed(self):
        """全部通过时不产生 failed cases。"""
        report = _make_e2e_report([
            _make_e2e_case("E001", passed=True),
            _make_e2e_case("E002", passed=True),
        ])
        result = _adapt_failed_cases_from_e2e_report(report)
        assert len(result) == 0

    def test_e2e_multiple_failure_categories(self):
        """多个 failure_categories 全部保留，第一个用于 failure_type。"""
        report = _make_e2e_report([
            _make_e2e_case("E001", passed=False,
                           failure_categories=["intent_failed", "wrong_metric"]),
        ])
        result = _adapt_failed_cases_from_e2e_report(report)
        assert result[0]["failure_type"] == "intent_failed"
        assert "wrong_metric" in result[0]["failure_categories"]

    def test_e2e_no_silent_drop(self):
        """每个失败 case 都进入结果，不允许静默忽略。"""
        cases = [
            _make_e2e_case(f"C{i:03d}", passed=(i % 3 != 0),
                           failure_categories=["intent_failed"] if i % 3 == 0 else [])
            for i in range(1, 11)
        ]
        report = _make_e2e_report(cases)
        # 10 cases, 1/3 fail → ~3-4 failures
        result = _adapt_failed_cases_from_e2e_report(report)
        expected_fails = sum(1 for c in cases if not c["passed"])
        assert len(result) == expected_fails


# ═══════════════════════════════════════════════════════════════
# 测试 3: 适配器 —— Prompt Regression
# ═══════════════════════════════════════════════════════════════


class TestAdaptFromPromptRegression:
    """Prompt Regression JSON → 标准 failed case 格式。"""

    def test_pr_parse_error(self):
        """parse 错误推断为 raw_output_parse_failed。"""
        report = _make_pr_report([
            _make_pr_case("P001", passed=False, error="JSON parse error in response"),
        ])
        result = _adapt_failed_cases_from_prompt_regression(report)
        assert len(result) == 1
        assert result[0]["failure_type"] == "raw_output_parse_failed"
        assert result[0]["stage"] == "prompt_regression"

    def test_pr_safety_error(self):
        """safety 错误推断为 safety_validation_failed。"""
        report = _make_pr_report([
            _make_pr_case("P001", passed=False, error="SQL safety check failed"),
        ])
        result = _adapt_failed_cases_from_prompt_regression(report)
        assert result[0]["failure_type"] == "safety_validation_failed"

    def test_pr_schema_error(self):
        """schema 错误推断为 schema_validation_failed。"""
        report = _make_pr_report([
            _make_pr_case("P001", passed=False, error="schema validation error"),
        ])
        result = _adapt_failed_cases_from_prompt_regression(report)
        assert result[0]["failure_type"] == "schema_validation_failed"

    def test_pr_confidence_error(self):
        """confidence 错误推断为 confidence_out_of_range。"""
        report = _make_pr_report([
            _make_pr_case("P001", passed=False, error="confidence value out of range"),
        ])
        result = _adapt_failed_cases_from_prompt_regression(report)
        assert result[0]["failure_type"] == "confidence_out_of_range"

    def test_pr_all_passed(self):
        """全部通过时不产生 failed cases。"""
        report = _make_pr_report([
            _make_pr_case("P001", passed=True),
            _make_pr_case("P002", passed=True),
        ])
        result = _adapt_failed_cases_from_prompt_regression(report)
        assert len(result) == 0

    def test_pr_refusal_error(self):
        """refusal 错误推断为 refusal_expected_but_answered。"""
        report = _make_pr_report([
            _make_pr_case("P001", passed=False, error="refusal mismatch detected"),
        ])
        result = _adapt_failed_cases_from_prompt_regression(report)
        assert result[0]["failure_type"] == "refusal_expected_but_answered"


# ═══════════════════════════════════════════════════════════════
# 测试 4: 通用 failed case 列表适配器
# ═══════════════════════════════════════════════════════════════


class TestAdaptFromGenericList:
    """通用 failed case 列表 → 标准格式。"""

    def test_basic_list(self):
        """基本列表转换正常。"""
        cases = [
            {"question_id": "G001", "failure_type": "intent_mismatch", "passed": False},
            {"question_id": "G002", "failure_type": "plan_mismatch", "passed": False},
        ]
        result = _adapt_failed_cases_from_generic_list(cases)
        assert len(result) == 2

    def test_skips_passed_cases(self):
        """跳过 passed=True 的 case。"""
        cases = [
            {"question_id": "G001", "failure_type": "intent_mismatch", "passed": False},
            {"question_id": "G002", "failure_type": "plan_mismatch", "passed": True},
        ]
        result = _adapt_failed_cases_from_generic_list(cases)
        assert len(result) == 1
        assert result[0]["question_id"] == "G001"

    def test_no_question_id_not_dropped(self):
        """无 question_id 的 case 不静默丢弃，标记为 unknown。"""
        cases = [
            {"failure_type": "intent_mismatch", "passed": False},
        ]
        result = _adapt_failed_cases_from_generic_list(cases)
        assert len(result) == 1
        assert result[0]["question_id"] == "unknown"

    def test_missing_fields_defaulted(self):
        """缺失字段使用空默认值，不抛异常。"""
        cases = [
            {"question_id": "G001", "passed": False},
        ]
        result = _adapt_failed_cases_from_generic_list(cases)
        assert len(result) == 1
        assert result[0]["failure_type"] == "unknown"
        assert result[0]["question"] == ""

    def test_failure_type_normalized(self):
        """failure_type 被归一化。"""
        cases = [
            {"question_id": "G001", "failure_type": "wrong_table", "passed": False},
        ]
        result = _adapt_failed_cases_from_generic_list(cases)
        assert result[0]["failure_type"] == "table_mismatch"


# ═══════════════════════════════════════════════════════════════
# 测试 5: 管道核心 —— run_pipeline_on_failure_triage
# ═══════════════════════════════════════════════════════════════


class TestRunPipelineOnFailureTriage:
    """从内存 triage 运行完整管道。"""

    def test_generates_both_reports(self, tmp_path):
        """有 failed cases 时生成 suggestions + review 双报告。"""
        triage = _make_triage_result([
            _make_triage_item("C001", "intent_mismatch"),
        ])
        result = run_pipeline_on_failure_triage(triage, output_root=tmp_path)

        assert result["generated"] is True
        assert result["failed_cases"] == 1
        assert result["error"] is None

        # 两份报告都已生成
        sr = result["suggestions_report"]
        assert sr is not None
        assert "json" in sr
        assert "markdown" in sr
        assert Path(sr["json"]).exists()
        assert Path(sr["markdown"]).exists()

        rr = result["review_report"]
        assert rr is not None
        assert "json" in rr
        assert "markdown" in rr
        assert Path(rr["json"]).exists()
        assert Path(rr["markdown"]).exists()

    def test_no_failed_cases_skipped(self, tmp_path):
        """zero failure 时返回 skipped 结果，不生成文件。"""
        triage = _make_triage_result([])
        result = run_pipeline_on_failure_triage(triage, output_root=tmp_path)

        assert result["generated"] is False
        assert result["suggestions_report"] is None
        assert result["review_report"] is None
        assert "no failed cases" in result["warnings"][0]

    def test_all_timestamp_snapshots(self, tmp_path):
        """所有生成文件都是 timestamp snapshot，无 latest。"""
        triage = _make_triage_result([
            _make_triage_item("C001", "intent_mismatch"),
        ])
        result = run_pipeline_on_failure_triage(triage, output_root=tmp_path)

        sr_json = Path(result["suggestions_report"]["json"])
        sr_md = Path(result["suggestions_report"]["markdown"])
        rr_json = Path(result["review_report"]["json"])
        rr_md = Path(result["review_report"]["markdown"])

        # 文件名包含 memory_suggestions_ / memory_suggestion_review_ 前缀
        assert sr_json.name.startswith("memory_suggestions_")
        assert sr_md.name.startswith("memory_suggestions_")
        assert rr_json.name.startswith("memory_suggestion_review_")
        assert rr_md.name.startswith("memory_suggestion_review_")

        # 不含 latest
        for p in [sr_json, sr_md, rr_json, rr_md]:
            assert "latest" not in p.name.lower()

    def test_no_docs_memory_written(self, tmp_path):
        """不修改 docs/memory/*。"""
        docs_memory = tmp_path / "docs" / "memory"
        docs_memory.mkdir(parents=True, exist_ok=True)

        triage = _make_triage_result([
            _make_triage_item("C001", "intent_mismatch"),
        ])
        run_pipeline_on_failure_triage(triage, output_root=tmp_path)

        # docs/memory/ 下不应生成任何文件
        memory_files = list(docs_memory.rglob("*"))
        assert len(memory_files) == 0

    def test_no_memory_rules_yml_written(self, tmp_path):
        """不写入 memory_rules.yml。"""
        triage = _make_triage_result([
            _make_triage_item("C001", "intent_mismatch"),
        ])
        run_pipeline_on_failure_triage(triage, output_root=tmp_path)

        # 整个 tmp_path 下不应有 memory_rules.yml
        all_yml = list(tmp_path.rglob("memory_rules.yml"))
        assert len(all_yml) == 0

    def test_pipeline_failure_does_not_swallow(self):
        """管道内部异常不吞掉：返回错误结果但保留 failed_cases 计数。"""
        triage = _make_triage_result([
            _make_triage_item("C001", "intent_mismatch"),
        ])
        # 模拟一个会触发异常的场景（output_root 为只读路径）
        with patch(
            "harness.memory_suggestion_pipeline.build_memory_suggestions_report",
            side_effect=RuntimeError("模拟内部错误"),
        ):
            result = run_pipeline_on_failure_triage(triage, output_root="/nonexistent/path")

        assert result["generated"] is False
        assert result["failed_cases"] == 1  # 保留原始失败计数
        assert "模拟内部错误" in str(result["error"])
        # 不抛异常，返回结构化错误

    def test_provider_runtime_not_source_failure(self, tmp_path):
        """provider/runtime 波动不自动判定为 source 代码失败。"""
        triage = _make_triage_result([
            _make_triage_item("C001", "execution_failed"),
        ])
        result = run_pipeline_on_failure_triage(triage, output_root=tmp_path)
        assert result["generated"] is True
        # execution_failed 的 failure_type 保持不变，不转为 source 类
        sr_json = Path(result["suggestions_report"]["json"])
        content = json.loads(sr_json.read_text(encoding="utf-8"))
        suggestion = content["suggestions"][0]
        # asset_dependency 应为 true（execution_failed 依赖数仓资产）
        assert suggestion["asset_dependency"] is True


# ═══════════════════════════════════════════════════════════════
# 测试 6: 管道核心 —— generate_memory_reports_for_failed_cases
# ═══════════════════════════════════════════════════════════════


class TestGenerateMemoryReportsForFailedCases:
    """从磁盘文件运行管道（file-based entry point）。"""

    def test_rejects_latest_filename(self, tmp_path):
        """拒绝 *_latest.* 文件名。"""
        latest_file = tmp_path / "my_latest.json"
        latest_file.write_text('{"cases": []}', encoding="utf-8")

        result = generate_memory_reports_for_failed_cases(
            str(latest_file), source="runtime_baseline", output_root=str(tmp_path),
        )
        assert result["generated"] is False
        assert "latest" in str(result["error"]).lower()

    def test_missing_file(self, tmp_path):
        """文件不存在时返回错误。"""
        result = generate_memory_reports_for_failed_cases(
            str(tmp_path / "nonexistent.json"), source="runtime_baseline", output_root=str(tmp_path),
        )
        assert result["generated"] is False
        assert "不存在" in str(result["error"])

    def test_e2e_source_generates_reports(self, tmp_path):
        """source=llm_e2e_eval 时正确识别 E2E 格式。"""
        e2e_file = tmp_path / "e2e_input.json"
        e2e_file.write_text(json.dumps(_make_e2e_report([
            _make_e2e_case("E001", passed=False, failure_categories=["intent_failed"]),
        ])), encoding="utf-8")

        result = generate_memory_reports_for_failed_cases(
            str(e2e_file), source="llm_e2e_eval", output_root=str(tmp_path),
        )
        assert result["generated"] is True
        assert result["failed_cases"] == 1

    def test_pr_source_generates_reports(self, tmp_path):
        """source=prompt_regression 时正确识别 PR 格式。"""
        pr_file = tmp_path / "pr_input.json"
        pr_file.write_text(json.dumps(_make_pr_report([
            _make_pr_case("P001", passed=False, error="JSON parse error"),
        ])), encoding="utf-8")

        result = generate_memory_reports_for_failed_cases(
            str(pr_file), source="prompt_regression", output_root=str(tmp_path),
        )
        assert result["generated"] is True
        assert result["failed_cases"] == 1

    def test_runtime_baseline_with_triage(self, tmp_path):
        """source=runtime_baseline + failure_triage 数据。"""
        triage = _make_triage_result([
            _make_triage_item("C001", "intent_mismatch"),
        ])
        baseline_file = tmp_path / "baseline_input.json"
        baseline_file.write_text(json.dumps({
            "run_id": "bl-001",
            "status": "FAIL",
            "failure_triage": triage,
        }), encoding="utf-8")

        result = generate_memory_reports_for_failed_cases(
            str(baseline_file), source="runtime_baseline", output_root=str(tmp_path),
        )
        assert result["generated"] is True
        assert result["failed_cases"] == 1

    def test_generic_case_list(self, tmp_path):
        """通用 case 列表格式。"""
        cases_file = tmp_path / "cases_input.json"
        cases_file.write_text(json.dumps([
            {"question_id": "G001", "failure_type": "intent_mismatch", "passed": False},
            {"question_id": "G002", "failure_type": "plan_mismatch", "passed": False},
        ]), encoding="utf-8")

        result = generate_memory_reports_for_failed_cases(
            str(cases_file), source="runtime_baseline", output_root=str(tmp_path),
        )
        assert result["generated"] is True
        assert result["failed_cases"] == 2

    def test_zero_failure_skipped(self, tmp_path):
        """输入中无失败 case 时返回 skipped。"""
        empty_file = tmp_path / "empty_input.json"
        empty_file.write_text(json.dumps({"cases": []}), encoding="utf-8")

        result = generate_memory_reports_for_failed_cases(
            str(empty_file), source="runtime_baseline", output_root=str(tmp_path),
        )
        assert result["generated"] is False
        assert len(result["warnings"]) >= 1
        assert "failed cases" in str(result["warnings"]).lower() or "failed" in result.get("summary", "").lower()

    def test_no_latest_files_generated(self, tmp_path):
        """即使成功也不生成任何 latest 文件。"""
        e2e_file = tmp_path / "e2e_input.json"
        e2e_file.write_text(json.dumps(_make_e2e_report([
            _make_e2e_case("E001", passed=False, failure_categories=["intent_failed"]),
        ])), encoding="utf-8")

        generate_memory_reports_for_failed_cases(
            str(e2e_file), source="llm_e2e_eval", output_root=str(tmp_path),
        )

        all_latest = list(tmp_path.rglob("*latest*"))
        assert len(all_latest) == 0

    def test_json_parse_error_handled(self, tmp_path):
        """无效 JSON 输入返回错误但不抛异常。"""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json{{{{", encoding="utf-8")

        result = generate_memory_reports_for_failed_cases(
            str(bad_file), source="runtime_baseline", output_root=str(tmp_path),
        )
        assert result["generated"] is False
        assert "JSON" in str(result["error"])


# ═══════════════════════════════════════════════════════════════
# 测试 7: 辅助函数
# ═══════════════════════════════════════════════════════════════


class TestHelperFunctions:
    """_skipped_result / _error_result / render_pipeline_summary 等。"""

    def test_skipped_result_structure(self):
        """_skipped_result 返回完整结构。"""
        result = _skipped_result("没有失败用例")
        assert result["generated"] is False
        assert result["failed_cases"] == 0
        assert result["suggestions_report"] is None
        assert result["review_report"] is None
        assert len(result["warnings"]) == 1
        assert result["error"] is None

    def test_error_result_structure(self):
        """_error_result 返回完整结构。"""
        result = _error_result("输入文件不存在")
        assert result["generated"] is False
        assert result["failed_cases"] == 0
        assert result["suggestions_report"] is None
        assert result["review_report"] is None
        assert "输入文件不存在" in result["warnings"][0]
        assert result["error"] == "输入文件不存在"

    def test_render_summary_generated(self):
        """generated=True 时渲染完整摘要。"""
        result = {
            "generated": True,
            "failed_cases": 3,
            "suggestions_report": {"json": "/tmp/s.json", "markdown": "/tmp/s.md"},
            "review_report": {"json": "/tmp/r.json", "markdown": "/tmp/r.md"},
            "warnings": [],
            "error": None,
        }
        text = render_pipeline_summary_for_baseline(result)
        assert "generated" in text
        assert "3" in text
        assert "memory_suggestions" in text.lower() or "/tmp/s.json" in text

    def test_render_summary_skipped(self):
        """generated=False 时渲染 skipped 信息。"""
        result = _skipped_result("没有失败用例")
        text = render_pipeline_summary_for_baseline(result)
        assert "skipped" in text.lower()

    def test_render_summary_with_warnings(self):
        """有 warnings 时包含在摘要中。"""
        result = {
            "generated": True,
            "failed_cases": 1,
            "suggestions_report": {"json": "/tmp/s.json", "markdown": "/tmp/s.md"},
            "review_report": {"json": "/tmp/r.json", "markdown": "/tmp/r.md"},
            "warnings": ["测试警告"],
            "error": None,
        }
        text = render_pipeline_summary_for_baseline(result)
        assert "测试警告" in text


# ═══════════════════════════════════════════════════════════════
# 测试 8: 回归测试 —— 与 dual_baseline 集成
# ═══════════════════════════════════════════════════════════════


class TestDualBaselineIntegration:
    """验证管道集成到 dual_baseline 后的行为。"""

    def test_runtime_baseline_fail_triggers_pipeline(self, tmp_path):
        """Runtime baseline FAIL 时自动生成 memory suggestion summary。"""
        from harness.baselines.dual_baseline import (
            GitState,
            FileDiff,
            build_snapshot,
        )

        # 模拟一个包含 failure_triage 的 FAIL snapshot
        triage = _make_triage_result([
            _make_triage_item("C001", "intent_mismatch"),
        ])
        snapshot = build_snapshot(
            baseline_type="runtime_llm",
            status=_make_status("FAIL", "test fail"),
            commands=[],
            before_git=GitState(head="abc", status_porcelain="", dirty=False),
            after_git=GitState(head="abc", status_porcelain="", dirty=False),
            file_diff=FileDiff(before_status="", after_status="", diff_stat="",
                               summary={"added": 0, "modified": 0, "deleted": 0, "renamed": 0, "untracked": 0}),
            timestamp="2026-06-18T12:00:00Z",
        )
        snapshot["failure_triage"] = triage

        # 通过 pipeline 函数处理
        pipeline_result = run_pipeline_on_failure_triage(
            triage, output_root=tmp_path,
        )
        snapshot["memory_suggestion_pipeline"] = pipeline_result

        assert snapshot["status"] == "FAIL"
        assert pipeline_result["generated"] is True
        assert pipeline_result["failed_cases"] == 1

    def test_runtime_baseline_pass_no_pipeline(self, tmp_path):
        """Runtime baseline PASS 时不生成 unnecessary report。"""
        triage = _make_triage_result([])  # zero failures
        result = run_pipeline_on_failure_triage(triage, output_root=tmp_path)
        assert result["generated"] is False
        assert "no failed cases" in str(result["warnings"])

    def test_e2e_eval_fail_generates_report(self, tmp_path):
        """E2E eval FAIL 时可生成 report。"""
        e2e_file = tmp_path / "e2e.json"
        e2e_file.write_text(json.dumps(_make_e2e_report([
            _make_e2e_case("E001", passed=False, failure_categories=["plan_failed"]),
        ])), encoding="utf-8")

        result = generate_memory_reports_for_failed_cases(
            str(e2e_file), source="llm_e2e_eval", output_root=str(tmp_path),
        )
        assert result["generated"] is True

    def test_prompt_regression_fail_generates_report(self, tmp_path):
        """prompt regression FAIL 时可生成 report。"""
        pr_file = tmp_path / "pr.json"
        pr_file.write_text(json.dumps(_make_pr_report([
            _make_pr_case("P001", passed=False, error="JSON parse error"),
        ])), encoding="utf-8")

        result = generate_memory_reports_for_failed_cases(
            str(pr_file), source="prompt_regression", output_root=str(tmp_path),
        )
        assert result["generated"] is True

    def test_pipeline_failure_preserves_baseline_status(self, tmp_path):
        """管道失败不改变 baseline 的 FAIL/PASS 状态。"""
        triage = _make_triage_result([
            _make_triage_item("C001", "intent_mismatch"),
        ])
        # 管道异常
        with patch(
            "harness.memory_suggestion_pipeline.write_memory_suggestions_snapshot",
            side_effect=OSError("磁盘满"),
        ):
            result = run_pipeline_on_failure_triage(triage, output_root=tmp_path)

        # 管道失败，但原始 failed_cases 计数保留
        assert result["generated"] is False
        assert result["failed_cases"] == 1
        assert result["error"] is not None


# ═══════════════════════════════════════════════════════════════
# 测试 9: 边界测试
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """各种边界情况。"""

    def test_triage_with_error_field(self, tmp_path):
        """failure_triage 带 error 字段时仍能处理 items。"""
        triage = {
            "source": "e2e_eval_report",
            "run_id": "test",
            "total_failed": 2,
            "items": [
                _make_triage_item("C001", "intent_mismatch"),
                _make_triage_item("C002", "plan_mismatch"),
            ],
            "error": "部分报告缺失",
        }
        result = run_pipeline_on_failure_triage(triage, output_root=tmp_path)
        assert result["generated"] is True
        assert result["failed_cases"] == 2
        assert len(result["warnings"]) >= 1  # triage error 作为 warning

    def test_all_12_failure_types(self, tmp_path):
        """12 种标准 failure_type 全部可以走通管道。"""
        all_types = [
            "intent_mismatch", "plan_mismatch", "table_mismatch",
            "field_mismatch", "clarification_expected_but_answered",
            "refusal_expected_but_answered", "confidence_out_of_range",
            "schema_validation_failed", "safety_validation_failed",
            "raw_output_parse_failed", "execution_failed", "explain_failed",
        ]
        items = [_make_triage_item(f"C{i:03d}", ft) for i, ft in enumerate(all_types, 1)]
        triage = _make_triage_result(items)

        result = run_pipeline_on_failure_triage(triage, output_root=tmp_path)
        assert result["generated"] is True
        assert result["failed_cases"] == 12

        # 验证 review report 包含所有 12 个 items
        rr_json = Path(result["review_report"]["json"])
        review = json.loads(rr_json.read_text(encoding="utf-8"))
        assert review["summary"]["total_reviewed"] == 12

    def test_suggestions_report_structure(self, tmp_path):
        """生成的 suggestions report JSON 结构完整。"""
        triage = _make_triage_result([
            _make_triage_item("C001", "intent_mismatch"),
        ])
        result = run_pipeline_on_failure_triage(triage, output_root=tmp_path)

        sr_json = Path(result["suggestions_report"]["json"])
        content = json.loads(sr_json.read_text(encoding="utf-8"))
        # 必需字段
        assert "run_id" in content
        assert "timestamp" in content
        assert "source" in content
        assert "summary" in content
        assert "suggestions" in content
        assert "regression_candidates" in content
        assert "asset_dependencies" in content
        assert "suggested_memory_rules" in content

    def test_review_report_structure(self, tmp_path):
        """生成的 review report JSON 结构完整。"""
        triage = _make_triage_result([
            _make_triage_item("C001", "intent_mismatch"),
        ])
        result = run_pipeline_on_failure_triage(triage, output_root=tmp_path)

        rr_json = Path(result["review_report"]["json"])
        content = json.loads(rr_json.read_text(encoding="utf-8"))
        # 必需字段
        assert "run_id" in content
        assert "timestamp" in content
        assert "source_snapshot_path" in content
        assert "summary" in content
        assert "review_items" in content
        assert "regression_case_candidates" in content
        assert "high_priority_manual_review" in content

    def test_suggested_rules_all_proposed_blocking_false(self, tmp_path):
        """所有 suggested_memory_rule 的 status=proposed, blocking=false。"""
        triage = _make_triage_result([
            _make_triage_item("C001", "safety_validation_failed"),
        ])
        result = run_pipeline_on_failure_triage(triage, output_root=tmp_path)

        sr_json = Path(result["suggestions_report"]["json"])
        content = json.loads(sr_json.read_text(encoding="utf-8"))
        for rule in content.get("suggested_memory_rules", []):
            assert rule["status"] == "proposed"
            assert rule["blocking"] is False

    def test_output_dirs_created(self, tmp_path):
        """memory_suggestions 和 memory_reviews 目录自动创建。"""
        triage = _make_triage_result([
            _make_triage_item("C001", "intent_mismatch"),
        ])
        run_pipeline_on_failure_triage(triage, output_root=tmp_path)

        assert (tmp_path / "memory_suggestions").is_dir()
        assert (tmp_path / "memory_reviews").is_dir()


# ═══════════════════════════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════════════════════════


def _make_status(status: str, reason: str):
    """构造 BaselineStatus 兼容对象。"""
    from harness.baselines.dual_baseline import BaselineStatus
    return BaselineStatus(status, reason)
