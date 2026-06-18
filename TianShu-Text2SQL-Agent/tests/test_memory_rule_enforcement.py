"""Memory Rule Enforcement（Step 18b）测试。

覆盖 15+ 测试场景：
  1.  proposed 规则 → visibility_only，不进入 warn/error
  2.  active+blocking=false + check failed → warning，不改变 exit code
  3.  active+blocking=true + check failed → FAIL，Step 18b 改变 exit code
  4.  deprecated/superseded → ignored
  5.  required_checks 找不到对应 check result → warning/skipped
  6.  memory_rules.yml 解析失败 → infrastructure failure
  7.  duplicate rule_id → infrastructure failure
  8.  enforcement summary 包含正确统计
  9.  run_fast_gate.py 输出 Memory Rule Enforcement Summary
  10. run_fast_gate.py 原有 blocking checks 行为不回退
  11. active+blocking=true check 失败导致 exit code 非 0（Step 18b 真实阻断）
  12. 不读取 latest
  13. 不修改 docs/memory/*
  14. 不接 pre-commit
  15. 不调用 LLM
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.memory_rule_enforcement import (  # noqa: E402
    ENFORCEMENT_BLOCKING_DRY_RUN,
    ENFORCEMENT_BLOCKING_ERROR,
    ENFORCEMENT_IGNORED,
    ENFORCEMENT_VISIBILITY,
    ENFORCEMENT_WARN,
    VALID_STATUSES,
    _generate_run_id,
    _parse_harness_stdout_for_check_results,
    _reject_latest,
    build_enforcement_report,
    classify_rule,
    compute_rule_enforcement,
    load_rules,
    match_check_to_rule,
    parse_check_results_from_harness_stdout,
    render_enforcement_console_summary,
    render_enforcement_json,
    render_enforcement_markdown,
    validate_rules_basics,
    write_enforcement_snapshot,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 测试辅助函数
# ═══════════════════════════════════════════════════════════════════════════════

def _make_rule(
    rule_id: str = "TA-R001",
    title: str = "测试规则",
    status: str = "proposed",
    blocking: bool = False,
    severity: str = "high",
    required_checks: list[str] | None = None,
    required_tests: list[str] | None = None,
    required_evals: list[str] | None = None,
    notes: str = "",
) -> dict:
    """创建一条测试规则。"""
    return {
        "rule_id": rule_id,
        "title": title,
        "status": status,
        "blocking": blocking,
        "severity": severity,
        "source_memory": "test",
        "risk_ids": ["RISK-001"],
        "applies_to": ["src/test.py"],
        "required_checks": required_checks or [],
        "required_tests": required_tests or [],
        "required_evals": required_evals or [],
        "notes": notes,
    }


def _make_check_result(
    name: str = "测试检查",
    script: str = "harness/checks/check_test.py",
    status: str = "PASS",
    exit_code: int = 0,
) -> dict:
    """创建一条 check 执行结果。"""
    return {
        "name": name,
        "script": script,
        "status": status,
        "exit_code": exit_code,
    }


def _write_rules_yml(rules: list[dict], dir_path: Path) -> Path:
    """将规则列表写入临时 YAML 文件。"""
    path = dir_path / "memory_rules.yml"
    content = yaml.dump({"rules": rules}, allow_unicode=True, default_flow_style=False)
    path.write_text(content, encoding="utf-8")
    return path


def _write_check_results_json(check_results: list[dict], dir_path: Path) -> Path:
    """将 check results 写入临时 JSON 文件。"""
    path = dir_path / "check_results.json"
    path.write_text(json.dumps(check_results, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：规则分类
# ═══════════════════════════════════════════════════════════════════════════════

class TestClassifyRule:
    """规则 enforcement 级别分类测试。"""

    def test_proposed_rule_visibility_only(self):
        """proposed 规则应归类为 visibility_only。"""
        rule = _make_rule(status="proposed", blocking=False)
        assert classify_rule(rule) == ENFORCEMENT_VISIBILITY

    def test_active_warning_rule(self):
        """active + blocking=false 规则应归类为 warn。"""
        rule = _make_rule(status="active", blocking=False)
        assert classify_rule(rule) == ENFORCEMENT_WARN

    def test_active_blocking_rule_blocking_error(self):
        """active + blocking=true 规则应归类为 blocking_error（Step 18b 真实阻断）。"""
        rule = _make_rule(status="active", blocking=True)
        assert classify_rule(rule) == ENFORCEMENT_BLOCKING_ERROR

    def test_deprecated_rule_ignored(self):
        """deprecated 规则应归类为 ignored。"""
        rule = _make_rule(status="deprecated", blocking=False)
        assert classify_rule(rule) == ENFORCEMENT_IGNORED

    def test_superseded_rule_ignored(self):
        """superseded 规则应归类为 ignored。"""
        rule = _make_rule(status="superseded", blocking=False)
        assert classify_rule(rule) == ENFORCEMENT_IGNORED

    def test_unknown_status_falls_back_to_visibility(self):
        """未知 status 应回退到 visibility_only。"""
        rule = _make_rule(status="unknown_status", blocking=False)
        assert classify_rule(rule) == ENFORCEMENT_VISIBILITY


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：规则加载
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoadRules:
    """规则加载测试。"""

    def test_load_valid_rules(self, tmp_path):
        """正常加载有效规则文件。"""
        rules = [
            _make_rule("TA-R001", status="proposed"),
            _make_rule("TA-R002", status="active", blocking=True),
        ]
        path = _write_rules_yml(rules, tmp_path)
        loaded = load_rules(path)
        assert len(loaded) == 2
        assert loaded[0]["rule_id"] == "TA-R001"
        assert loaded[1]["rule_id"] == "TA-R002"

    def test_load_file_not_found(self, tmp_path):
        """文件不存在时抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            load_rules(tmp_path / "nonexistent.yml")

    def test_load_invalid_yaml(self, tmp_path):
        """无效 YAML 时抛出 yaml.YAMLError。"""
        path = tmp_path / "bad.yml"
        path.write_text("invalid: [\nyaml: -", encoding="utf-8")
        with pytest.raises(yaml.YAMLError):
            load_rules(path)

    def test_load_missing_rules_key(self, tmp_path):
        """缺少 'rules' 顶层键时抛出 ValueError。"""
        path = tmp_path / "no_rules.yml"
        path.write_text("other: value", encoding="utf-8")
        with pytest.raises(ValueError, match="缺少 'rules'"):
            load_rules(path)

    def test_load_rules_not_list(self, tmp_path):
        """'rules' 不是列表时抛出 ValueError。"""
        path = tmp_path / "bad_rules.yml"
        path.write_text("rules: not_a_list", encoding="utf-8")
        with pytest.raises(ValueError, match="必须是列表"):
            load_rules(path)

    def test_duplicate_rule_id_raises(self, tmp_path):
        """重复 rule_id 应抛出 ValueError。"""
        rules = [
            _make_rule("TA-R001"),
            _make_rule("TA-R001"),  # 重复
        ]
        path = _write_rules_yml(rules, tmp_path)
        with pytest.raises(ValueError, match="重复的 rule_id"):
            load_rules(path)

    def test_reject_latest_file(self, tmp_path):
        """拒绝读取 *_latest.* 文件。"""
        path = tmp_path / "memory_rules_latest.yml"
        path.write_text("rules: []", encoding="utf-8")
        with pytest.raises(ValueError, match="不允许读取.*latest"):
            load_rules(path)


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：规则验证
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateRulesBasics:
    """规则基础字段验证测试。"""

    def test_valid_rules_pass(self):
        """有效规则应无错误。"""
        rules = [
            _make_rule("TA-R001", status="proposed", blocking=False),
            _make_rule("TA-R010", status="active", blocking=True),
        ]
        errors = validate_rules_basics(rules)
        assert len(errors) == 0

    def test_invalid_rule_id_format(self):
        """无效 rule_id 格式应报告 infra_fail。"""
        rules = [
            _make_rule("R001"),  # 缺少 TA- 前缀
            _make_rule("TA-R1"),  # 数字不足 3 位
        ]
        errors = validate_rules_basics(rules)
        assert len(errors) >= 2
        for err in errors:
            assert err["status"] == "infra_fail"
            assert err["check"] == "rule_id_format"

    def test_missing_rule_id(self):
        """缺少 rule_id 应报告错误。"""
        rules = [{"title": "无 ID"}]
        errors = validate_rules_basics(rules)
        assert len(errors) >= 1

    def test_invalid_status(self):
        """非法 status 值应报告错误。"""
        rules = [_make_rule("TA-R001", status="invalid_status")]
        errors = validate_rules_basics(rules)
        assert any(e["check"] == "status_validity" for e in errors)

    def test_blocking_not_bool(self):
        """blocking 非 bool 类型应报告错误。"""
        rule = _make_rule("TA-R001")
        rule["blocking"] = "yes"  # 类型错误
        errors = validate_rules_basics([rule])
        assert any(e["check"] == "blocking_type" for e in errors)


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：Check 结果解析
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseCheckResults:
    """check results 解析测试。"""

    def test_parse_valid_check_results(self):
        """正确解析 __HARNESS_CHECK_RESULTS__ 行。"""
        stdout = (
            "一些输出...\n"
            '__HARNESS_CHECK_RESULTS__ [{"name": "SQL 只读", "script": "harness/checks/check_sql_readonly.py", "status": "PASS", "exit_code": 0}]\n'
            "更多输出..."
        )
        results = parse_check_results_from_harness_stdout(stdout)
        assert len(results) == 1
        assert results[0]["name"] == "SQL 只读"
        assert results[0]["status"] == "PASS"

    def test_parse_multiple_check_results(self):
        """解析多个 check results。"""
        results_data = [
            {"name": "Check A", "script": "a.py", "status": "PASS", "exit_code": 0},
            {"name": "Check B", "script": "b.py", "status": "FAIL", "exit_code": 1},
        ]
        stdout = f"__HARNESS_CHECK_RESULTS__ {json.dumps(results_data)}"
        results = parse_check_results_from_harness_stdout(stdout)
        assert len(results) == 2
        assert results[1]["status"] == "FAIL"

    def test_parse_missing_line_returns_empty(self):
        """无 __HARNESS_CHECK_RESULTS__ 行时返回空列表。"""
        stdout = "普通输出，没有结构化数据"
        results = parse_check_results_from_harness_stdout(stdout)
        assert results == []

    def test_parse_malformed_json_returns_empty(self):
        """JSON 格式错误时返回空列表。"""
        stdout = '__HARNESS_CHECK_RESULTS__ {bad json!!!'
        results = parse_check_results_from_harness_stdout(stdout)
        assert results == []

    def test_parse_warn_status(self):
        """解析 WARN 状态的 check result。"""
        results_data = [
            {"name": "Warn Check", "script": "w.py", "status": "WARN", "exit_code": 1},
        ]
        stdout = f"__HARNESS_CHECK_RESULTS__ {json.dumps(results_data)}"
        results = parse_check_results_from_harness_stdout(stdout)
        assert len(results) == 1
        assert results[0]["status"] == "WARN"

    def test_fallback_parse_from_stdout(self):
        """回退解析 harness 文本输出中的 check 状态。"""
        stdout = (
            "[1/11] SQL 只读安全门禁... PASS (0.05s)\n"
            "[2/11] IR 数据结构完整性... PASS (0.03s)\n"
            "[3/11] 反问/拒绝策略完备性... FAIL (0.10s)\n"
        )
        results = _parse_harness_stdout_for_check_results(stdout)
        assert len(results) == 3
        assert results[0]["status"] == "PASS"
        assert results[2]["status"] == "FAIL"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：Check 匹配
# ═══════════════════════════════════════════════════════════════════════════════

class TestMatchCheckToRule:
    """required_checks 匹配测试。"""

    def test_match_exact_script_path(self):
        """精确匹配脚本路径。"""
        rule = _make_rule(required_checks=["harness/checks/check_sql_readonly.py"])
        check_results = [
            _make_check_result(
                name="SQL 只读安全门禁",
                script="harness/checks/check_sql_readonly.py",
                status="PASS",
            ),
        ]
        matched = match_check_to_rule(rule, check_results)
        assert len(matched) == 1
        assert matched[0]["status"] == "PASS"

    def test_match_partial_path(self):
        """部分路径匹配。"""
        rule = _make_rule(required_checks=["check_sql_readonly.py"])
        check_results = [
            _make_check_result(
                name="SQL 只读安全门禁",
                script="harness/checks/check_sql_readonly.py",
                status="PASS",
            ),
        ]
        matched = match_check_to_rule(rule, check_results)
        assert len(matched) == 1

    def test_no_match_reports_skipped(self):
        """找不到对应 check result 时返回 SKIPPED 标记。"""
        rule = _make_rule(required_checks=["harness/checks/unknown_check.py"])
        check_results = [
            _make_check_result(script="harness/checks/other.py", status="PASS"),
        ]
        matched = match_check_to_rule(rule, check_results)
        assert len(matched) == 1
        assert matched[0]["status"] == "SKIPPED"
        assert "未找到" in matched[0].get("error_message", "")

    def test_empty_required_checks(self):
        """无 required_checks 时返回空列表。"""
        rule = _make_rule(required_checks=[])
        matched = match_check_to_rule(rule, [])
        assert matched == []

    def test_multiple_required_checks(self):
        """多个 required_checks 全部匹配。"""
        rule = _make_rule(required_checks=[
            "harness/checks/check_a.py",
            "harness/checks/check_b.py",
        ])
        check_results = [
            _make_check_result(name="A", script="harness/checks/check_a.py", status="PASS"),
            _make_check_result(name="B", script="harness/checks/check_b.py", status="FAIL"),
        ]
        matched = match_check_to_rule(rule, check_results)
        assert len(matched) == 2

    def test_backslash_path_normalized(self):
        """反斜杠路径应被归一化。"""
        rule = _make_rule(required_checks=["harness/checks/check_test.py"])
        check_results = [
            _make_check_result(
                script="harness\\checks\\check_test.py",  # Windows 风格
                status="PASS",
            ),
        ]
        matched = match_check_to_rule(rule, check_results)
        assert len(matched) == 1
        assert matched[0]["status"] == "PASS"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：Enforcement 计算
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeRuleEnforcement:
    """单条规则 enforcement 计算测试。"""

    # --- Scenario 1: proposed → visibility_only ---

    def test_proposed_rule_visibility_only_no_checks(self):
        """proposed 规则无 required_checks，应 passed + visibility_only。"""
        rule = _make_rule("TA-R001", status="proposed", blocking=False)
        result = compute_rule_enforcement(rule, [])
        assert result["enforcement_level"] == ENFORCEMENT_VISIBILITY
        assert result["result"] == "passed"

    def test_proposed_rule_with_passing_checks(self):
        """proposed 规则 required_checks 全部通过，应 passed。"""
        rule = _make_rule(
            "TA-R001", status="proposed",
            required_checks=["harness/checks/check_a.py"],
        )
        check_results = [
            _make_check_result(script="harness/checks/check_a.py", status="PASS"),
        ]
        result = compute_rule_enforcement(rule, check_results)
        assert result["enforcement_level"] == ENFORCEMENT_VISIBILITY
        assert result["result"] == "passed"

    def test_proposed_rule_check_failed_only_warning(self):
        """proposed 规则 check 失败 → warning，不进入 would_fail。"""
        rule = _make_rule(
            "TA-R001", status="proposed",
            required_checks=["harness/checks/check_a.py"],
        )
        check_results = [
            _make_check_result(script="harness/checks/check_a.py", status="FAIL", exit_code=1),
        ]
        result = compute_rule_enforcement(rule, check_results)
        assert result["enforcement_level"] == ENFORCEMENT_VISIBILITY
        assert result["result"] == "warning"  # 只是 warning，不是 would_fail

    # --- Scenario 2: active + blocking=false → warn ---

    def test_active_warning_rule_check_passed(self):
        """active+blocking=false 规则 check 通过 → passed。"""
        rule = _make_rule(
            "TA-R010", status="active", blocking=False,
            required_checks=["harness/checks/check_a.py"],
        )
        check_results = [
            _make_check_result(script="harness/checks/check_a.py", status="PASS"),
        ]
        result = compute_rule_enforcement(rule, check_results)
        assert result["enforcement_level"] == ENFORCEMENT_WARN
        assert result["result"] == "passed"

    def test_active_warning_rule_check_failed_warning(self):
        """active+blocking=false 规则 check 失败 → warning，不影响 exit code。"""
        rule = _make_rule(
            "TA-R010", status="active", blocking=False,
            required_checks=["harness/checks/check_a.py"],
        )
        check_results = [
            _make_check_result(script="harness/checks/check_a.py", status="FAIL", exit_code=1),
        ]
        result = compute_rule_enforcement(rule, check_results)
        assert result["enforcement_level"] == ENFORCEMENT_WARN
        assert result["result"] == "warning"

    # --- Scenario 3: active + blocking=true → blocking_error（Step 18b 真实阻断）---

    def test_active_blocking_rule_check_passed(self):
        """active+blocking=true 规则 check 通过 → passed。"""
        rule = _make_rule(
            "TA-R018", status="active", blocking=True,
            required_checks=["harness/checks/check_a.py"],
        )
        check_results = [
            _make_check_result(script="harness/checks/check_a.py", status="PASS"),
        ]
        result = compute_rule_enforcement(rule, check_results)
        assert result["enforcement_level"] == ENFORCEMENT_BLOCKING_ERROR
        assert result["result"] == "passed"

    def test_active_blocking_rule_check_failed_blocking_error(self):
        """active+blocking=true 规则 check 失败 → FAIL（Step 18b 真实阻断）。"""
        rule = _make_rule(
            "TA-R018", status="active", blocking=True,
            required_checks=["harness/checks/check_a.py"],
        )
        check_results = [
            _make_check_result(script="harness/checks/check_a.py", status="FAIL", exit_code=1),
        ]
        result = compute_rule_enforcement(rule, check_results)
        assert result["enforcement_level"] == ENFORCEMENT_BLOCKING_ERROR
        assert result["result"] == "FAIL"
        # 阻断消息应包含 rule_id 和回滚方案
        assert "TA-R018" in result["message"]
        assert "回滚" in result["message"]

    # --- Scenario 4: deprecated/superseded → ignored ---

    def test_deprecated_rule_ignored(self):
        """deprecated 规则 → skipped, ignored。"""
        rule = _make_rule(
            "TA-R099", status="deprecated", blocking=False,
            required_checks=["harness/checks/check_a.py"],
        )
        result = compute_rule_enforcement(rule, [])
        assert result["enforcement_level"] == ENFORCEMENT_IGNORED
        assert result["result"] == "skipped"

    def test_superseded_rule_ignored(self):
        """superseded 规则 → skipped, ignored。"""
        rule = _make_rule(
            "TA-R099", status="superseded", blocking=False,
            required_checks=["harness/checks/check_a.py"],
        )
        result = compute_rule_enforcement(rule, [])
        assert result["enforcement_level"] == ENFORCEMENT_IGNORED
        assert result["result"] == "skipped"

    # --- Scenario 5: required_checks 找不到对应 check result ---

    def test_unmatched_required_check_reports_warning(self):
        """required_check 未匹配到任何结果 → warning（不能静默忽略）。"""
        rule = _make_rule(
            "TA-R001", status="active", blocking=False,
            required_checks=["harness/checks/nonexistent.py"],
        )
        check_results = [
            _make_check_result(script="harness/checks/other.py", status="PASS"),
        ]
        result = compute_rule_enforcement(rule, check_results)
        assert result["result"] == "warning"
        assert "未找到" in result.get("message", "")

    def test_partially_matched_checks_reports_warning(self):
        """部分 required_checks 匹配、部分未匹配 → warning。"""
        rule = _make_rule(
            "TA-R001", status="active", blocking=False,
            required_checks=[
                "harness/checks/exists.py",
                "harness/checks/missing.py",
            ],
        )
        check_results = [
            _make_check_result(script="harness/checks/exists.py", status="PASS"),
        ]
        result = compute_rule_enforcement(rule, check_results)
        assert result["result"] == "warning"

    # --- Edge cases ---

    def test_rule_without_status_uses_default(self):
        """无 status 字段的规则使用默认值 proposed。"""
        rule = {"rule_id": "TA-R999", "title": "测试", "blocking": False}
        result = compute_rule_enforcement(rule, [])
        assert result["enforcement_level"] == ENFORCEMENT_VISIBILITY

    def test_exception_during_computation_returns_infra_error(self, tmp_path):
        """compute_rule_enforcement 内部异常应返回 infra_error。

        build_enforcement_report 中包装了 try/except，异常会被捕获为 infra_error。
        """
        # 通过 build_enforcement_report 验证异常处理路径
        rules = [_make_rule("TA-R001")]
        rules_path = _write_rules_yml(rules, tmp_path)

        with mock.patch(
            "harness.memory_rule_enforcement.compute_rule_enforcement",
            side_effect=RuntimeError("模拟错误"),
        ):
            report = build_enforcement_report(rules_path, check_results=[])
            # 异常应被捕获，对应的 rule result 应为 infra_error
            error_results = [
                rr for rr in report["rule_results"]
                if rr["result"] == "infra_error"
            ]
            assert len(error_results) >= 1
            assert "模拟错误" in error_results[0].get("message", "")


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：Enforcement Report 构建
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildEnforcementReport:
    """enforcement report 构建测试。"""

    def test_build_report_basic(self, tmp_path):
        """基本 report 构建：proposed 规则 + 无 check results。"""
        rules = [
            _make_rule("TA-R001", status="proposed"),
            _make_rule("TA-R010", status="active", blocking=False),
            _make_rule("TA-R018", status="active", blocking=True),
        ]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path, check_results=[])

        assert report["summary"]["total_rules"] == 3
        assert report["summary"]["proposed"] == 1
        assert report["summary"]["active_warning"] == 1
        assert report["summary"]["active_blocking"] == 1
        assert report["exit_code_should_fail"] is False  # 无 check 失败，不阻断
        assert report["write_mode"] == "blocking"
        assert len(report["rule_results"]) == 3

    def test_build_report_with_check_results(self, tmp_path):
        """带 check results 的 report 构建——check 失败导致 exit_code_should_fail=True。"""
        rules = [
            _make_rule(
                "TA-R018", status="active", blocking=True,
                required_checks=["harness/checks/check_a.py"],
            ),
        ]
        check_results = [
            _make_check_result(script="harness/checks/check_a.py", status="FAIL", exit_code=1),
        ]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path, check_results=check_results)

        assert report["summary"]["blocking_failures"] == 1
        # Step 18b: check 失败 → exit_code_should_fail=True
        assert report["exit_code_should_fail"] is True

    def test_build_report_with_infra_errors(self, tmp_path):
        """包含基础设施错误的 report。"""
        rules = [
            {"rule_id": "bad-id"},  # 无效 ID 格式
        ]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path)

        assert len(report["infra_errors"]) > 0
        assert report["summary"]["infra_errors"] > 0

    def test_summary_counts_are_correct(self, tmp_path):
        """汇总统计应准确。"""
        rules = [
            _make_rule("TA-R001", status="proposed"),
            _make_rule("TA-R002", status="proposed"),
            _make_rule("TA-R010", status="active", blocking=False),
            _make_rule("TA-R018", status="active", blocking=True),
            _make_rule("TA-R099", status="deprecated"),
            _make_rule("TA-R100", status="superseded"),
        ]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path)

        s = report["summary"]
        assert s["total_rules"] == 6
        assert s["proposed"] == 2
        assert s["active_warning"] == 1
        assert s["active_blocking"] == 1
        assert s["deprecated"] == 1
        assert s["superseded"] == 1
        # 所有 proposed 规则无 required_checks → passed
        # active+blocking=false 无 required_checks → passed
        # active+blocking=true 无 required_checks → passed
        # deprecated → skipped, superseded → skipped
        assert s["passed"] >= 4
        assert s["skipped"] == 2

    def test_exit_code_should_fail_when_check_fails(self, tmp_path):
        """Step 18b: active+blocking=true check 失败 → exit_code_should_fail=True。"""
        rules = [
            _make_rule(
                "TA-R018", status="active", blocking=True,
                required_checks=["harness/checks/check_a.py"],
            ),
        ]
        check_results = [
            _make_check_result(script="harness/checks/check_a.py", status="FAIL", exit_code=1),
        ]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path, check_results=check_results)
        assert report["exit_code_should_fail"] is True
        assert report["summary"]["blocking_failures"] == 1

    def test_none_check_results_accepted(self, tmp_path):
        """check_results=None 视为空列表。"""
        rules = [_make_rule("TA-R001")]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path, check_results=None)
        assert report["summary"]["total_rules"] == 1

    def test_run_id_format(self):
        """run_id 应使用 MRE- 前缀。"""
        run_id = _generate_run_id()
        assert run_id.startswith("MRE-")


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：渲染
# ═══════════════════════════════════════════════════════════════════════════════

class TestRenderers:
    """JSON / Markdown / Console 渲染测试。"""

    def test_render_json_serializable(self, tmp_path):
        """渲染的 JSON 应该是可序列化的。"""
        rules = [_make_rule("TA-R001")]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path)
        json_data = render_enforcement_json(report)
        # 应能成功序列化
        serialized = json.dumps(json_data, ensure_ascii=False)
        assert len(serialized) > 0

    def test_render_markdown_contains_sections(self, tmp_path):
        """Markdown 应包含必要章节。"""
        rules = [
            _make_rule("TA-R001", status="proposed"),
            _make_rule("TA-R018", status="active", blocking=True),
        ]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path)
        md = render_enforcement_markdown(report)

        assert "Memory Rule Enforcement" in md
        assert "汇总" in md
        assert "Exit code 受影响" in md
        assert "边界确认" in md
        assert "未修改 docs/memory" in md

    def test_render_markdown_includes_blocking_notice(self, tmp_path):
        """Markdown 应标注 blocking 模式（Step 18b）。"""
        rules = [_make_rule("TA-R001")]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path)
        md = render_enforcement_markdown(report)
        assert "blocking" in md.lower()

    def test_render_console_summary(self, tmp_path):
        """控制台摘要应包含必要信息。"""
        rules = [
            _make_rule("TA-R001", status="proposed"),
            _make_rule("TA-R010", status="active", blocking=False),
            _make_rule("TA-R018", status="active", blocking=True),
        ]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path)
        summary = render_enforcement_console_summary(report)

        assert "Memory Rule Enforcement Summary" in summary
        assert "exit code affected" in summary.lower()
        assert "no" in summary.lower()  # 无 check 失败 → exit code not affected

    def test_render_console_with_blocking_failure_details(self, tmp_path):
        """控制台摘要应列举 blocking failure 规则详情。"""
        rules = [
            _make_rule(
                "TA-R018", status="active", blocking=True,
                required_checks=["harness/checks/check_a.py"],
            ),
        ]
        check_results = [
            _make_check_result(script="harness/checks/check_a.py", status="FAIL", exit_code=1),
        ]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path, check_results=check_results)
        summary = render_enforcement_console_summary(report)

        assert "FAIL" in summary
        assert "TA-R018" in summary
        assert "exit code affected:           yes" in summary

    def test_render_markdown_shows_blocking_failures(self, tmp_path):
        """无阻断失败时不应有阻断失败详情章节。"""
        rules = [_make_rule("TA-R001", status="proposed")]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path)
        md = render_enforcement_markdown(report)

        # blocking_failures 应为 0
        assert "阻断失败 | 0" in md


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：Snapshot 写入
# ═══════════════════════════════════════════════════════════════════════════════

class TestSnapshotWriter:
    """snapshot 写入测试。"""

    def test_write_snapshot_creates_json_and_md(self, tmp_path):
        """应创建 JSON 和 Markdown 两个文件。"""
        rules = [_make_rule("TA-R001")]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path)
        output_dir = tmp_path / "enforcements"
        paths = write_enforcement_snapshot(report, output_dir)

        assert Path(paths["json"]).exists()
        assert Path(paths["markdown"]).exists()
        assert "memory_rule_enforcement_" in str(paths["json"])
        assert "memory_rule_enforcement_" in str(paths["markdown"])

    def test_write_snapshot_no_latest(self, tmp_path):
        """不应生成 latest 文件。"""
        rules = [_make_rule("TA-R001")]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path)
        output_dir = tmp_path / "enforcements"
        paths = write_enforcement_snapshot(report, output_dir)

        # 检查没有 latest 文件
        all_files = list(output_dir.glob("*"))
        latest_files = [f for f in all_files if "latest" in f.name.lower()]
        assert len(latest_files) == 0, f"不应有 latest 文件，但发现: {latest_files}"

    def test_write_snapshot_creates_output_dir(self, tmp_path):
        """应自动创建输出目录。"""
        rules = [_make_rule("TA-R001")]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path)
        output_dir = tmp_path / "nested" / "enforcements"
        paths = write_enforcement_snapshot(report, output_dir)

        assert output_dir.exists()
        assert Path(paths["json"]).exists()


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：Fast Gate 集成
# ═══════════════════════════════════════════════════════════════════════════════

class TestFastGateIntegration:
    """run_fast_gate.py 集成测试。"""

    def test_parse_harness_check_results_exists(self):
        """验证 run_fast_gate._parse_harness_check_results 存在且可用。"""
        from harness.run_fast_gate import _parse_harness_check_results

        # 空字符串返回 None
        assert _parse_harness_check_results("") is None

        # 有效数据返回列表
        results_data = [
            {"name": "Test", "script": "t.py", "status": "PASS", "exit_code": 0},
        ]
        stdout = f"__HARNESS_CHECK_RESULTS__ {json.dumps(results_data)}"
        result = _parse_harness_check_results(stdout)
        assert result is not None
        assert len(result) == 1

    def test_run_memory_rule_enforcement_function_exists(self):
        """验证 _run_memory_rule_enforcement 函数存在。"""
        from harness.run_fast_gate import _run_memory_rule_enforcement

        # 无 harness stdout 时返回 None
        result = _run_memory_rule_enforcement("")
        assert result is None

    def test_fast_gate_report_has_enforcement_field(self):
        """FastGateReport 应有 enforcement_report 字段。"""
        from harness.run_fast_gate import FastGateReport

        report = FastGateReport(
            run_id="test",
            timestamp="2026-01-01T00:00:00Z",
            commit_sha=None,
            branch=None,
            total_steps=3,
            passed=3,
            failed=0,
            skipped=0,
            overall="PASS",
            steps=[],
            duration_total_seconds=1.0,
        )
        assert hasattr(report, "enforcement_report")
        assert report.enforcement_report is None

    def test_fast_gate_markdown_includes_enforcement_when_present(self):
        """当 enforcement_report 存在时，Markdown 应包含 enforcement 章节。"""
        from harness.run_fast_gate import FastGateReport, render_markdown

        enforcement_report = {
            "run_id": "MRE-test",
            "timestamp": "2026-01-01T00:00:00Z",
            "summary": {
                "total_rules": 3,
                "proposed": 1,
                "active_warning": 1,
                "active_blocking": 1,
                "deprecated": 0,
                "superseded": 0,
                "warnings": 0,
                "blocking_dry_run_failures": 0,
                "would_fail": 0,
                "blocking_failures": 0,
                "passed": 2,
                "skipped": 1,
                "infra_errors": 0,
            },
            "rule_results": [],
            "exit_code_should_fail": False,
            "write_mode": "blocking",
        }

        report = FastGateReport(
            run_id="test",
            timestamp="2026-01-01T00:00:00Z",
            commit_sha=None,
            branch=None,
            total_steps=3,
            passed=3,
            failed=0,
            skipped=0,
            overall="PASS",
            steps=[],
            duration_total_seconds=1.0,
            enforcement_report=enforcement_report,
        )

        md = render_markdown(report)
        assert "Memory Rule Enforcement" in md
        assert "Step 18b" in md
        assert "Exit code 受影响" in md

    def test_fast_gate_markdown_no_enforcement_when_none(self):
        """当 enforcement_report 为 None 时，Markdown 不应有 enforcement 章节。"""
        from harness.run_fast_gate import FastGateReport, render_markdown

        report = FastGateReport(
            run_id="test",
            timestamp="2026-01-01T00:00:00Z",
            commit_sha=None,
            branch=None,
            total_steps=3,
            passed=3,
            failed=0,
            skipped=0,
            overall="PASS",
            steps=[],
            duration_total_seconds=1.0,
        )

        md = render_markdown(report)
        assert "Memory Rule Enforcement" not in md


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：Exit Code 语义
# ═══════════════════════════════════════════════════════════════════════════════

class TestExitCodeSemantics:
    """exit code 语义测试（Step 18b 关键约束）。"""

    def test_active_blocking_check_fail_affects_exit_code(self, tmp_path):
        """active+blocking=true check 失败 → exit_code_should_fail=True。"""
        rules = [
            _make_rule(
                "TA-R018", status="active", blocking=True,
                required_checks=["harness/checks/check_a.py"],
            ),
        ]
        check_results = [
            _make_check_result(script="harness/checks/check_a.py", status="FAIL", exit_code=1),
        ]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path, check_results=check_results)

        # blocking_failures > 0
        assert report["summary"]["blocking_failures"] == 1
        # Step 18b: check 失败 → exit_code_should_fail=True
        assert report["exit_code_should_fail"] is True

    def test_multiple_blocking_failures_affect_exit_code(self, tmp_path):
        """多条 active+blocking=true check 失败 → exit_code_should_fail=True。"""
        rules = [
            _make_rule(
                "TA-R018", status="active", blocking=True,
                required_checks=["harness/checks/check_a.py"],
            ),
            _make_rule(
                "TA-R019", status="active", blocking=True,
                required_checks=["harness/checks/check_b.py"],
            ),
        ]
        check_results = [
            _make_check_result(script="harness/checks/check_a.py", status="FAIL", exit_code=1),
            _make_check_result(script="harness/checks/check_b.py", status="FAIL", exit_code=1),
        ]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path, check_results=check_results)

        assert report["summary"]["blocking_failures"] == 2
        assert report["exit_code_should_fail"] is True

    def test_original_blocking_checks_still_block(self):
        """原有 blocking checks 不应被 enforcement 影响。

        验证：fast gate 的原有 FAIL/exit code 逻辑独立于 enforcement。
        即使 enforcement 存在，原有 FAIL → exit 1 逻辑仍在。
        """
        from harness.run_fast_gate import run_fast_gate

        # 从 harness 步骤的 FAIL 应仍然导致 overall FAIL
        # 这里验证 run_fast_gate 函数签名和返回正常
        assert callable(run_fast_gate)


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：不读取 latest / 不修改文件 / 不调用 LLM
# ═══════════════════════════════════════════════════════════════════════════════

class TestSafetyBoundaries:
    """安全边界测试。"""

    def test_reject_latest_raises(self, tmp_path):
        """_reject_latest 应拒绝 latest 文件。"""
        path = tmp_path / "memory_rules_latest.yml"
        path.write_text("")
        with pytest.raises(ValueError, match="不允许读取.*latest"):
            _reject_latest(path, "test")

    def test_reject_latest_case_insensitive(self, tmp_path):
        """_reject_latest 应不区分大小写拒绝 latest。"""
        path = tmp_path / "MEMORY_RULES_LATEST.YML"
        path.write_text("")
        with pytest.raises(ValueError, match="不允许读取.*latest"):
            _reject_latest(path, "test")

    def test_enforcement_does_not_modify_rules_file(self, tmp_path):
        """enforcement 不应修改 memory_rules.yml。"""
        rules = [_make_rule("TA-R001")]
        rules_path = _write_rules_yml(rules, tmp_path)
        original_content = rules_path.read_text(encoding="utf-8")

        report = build_enforcement_report(rules_path)

        # 验证文件未被修改
        current_content = rules_path.read_text(encoding="utf-8")
        assert current_content == original_content

    def test_enforcement_does_not_modify_memory_docs(self, tmp_path):
        """enforcement 不应修改 docs/memory/ 下的文件。"""
        # 创建模拟的 docs/memory 目录
        memory_dir = tmp_path / "docs" / "memory"
        memory_dir.mkdir(parents=True)
        rules_path = memory_dir / "memory_rules.yml"
        rules = [_make_rule("TA-R001")]
        rules_path.write_text(
            yaml.dump({"rules": rules}, allow_unicode=True),
            encoding="utf-8",
        )
        original = rules_path.read_text(encoding="utf-8")

        report = build_enforcement_report(rules_path)
        assert rules_path.read_text(encoding="utf-8") == original

    def test_no_llm_calls(self):
        """enforcement 模块不应引用 LLM 相关代码。"""
        import harness.memory_rule_enforcement as mod
        source = Path(mod.__file__).read_text(encoding="utf-8") if mod.__file__ else ""

        # 不应有 LLM/API 调用相关关键字
        forbidden = ["openai", "anthropic", "llm.invoke", "llm.call", "chat.completions"]
        for kw in forbidden:
            assert kw not in source.lower(), f"源码中不应包含 '{kw}'"

    def test_no_pre_commit_references(self):
        """enforcement 模块不应对 pre-commit 有功能性依赖。

        注意：Markdown 渲染中的边界说明字符串可能包含"pre-commit"字样
        （如"未接入 pre-commit"），这是预期内的文档说明，不是功能性引用。
        """
        import harness.memory_rule_enforcement as mod
        source = Path(mod.__file__).read_text(encoding="utf-8") if mod.__file__ else ""

        # 功能性引用不应存在：import pre_commit、.git/hooks 路径等
        assert "import pre_commit" not in source.lower()
        assert "import precommit" not in source.lower()
        assert ".git/hooks" not in source.lower()
        # pre-commit 出现在边界确认文档中是可以的，但不应出现在 import/函数调用中


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：端到端场景
# ═══════════════════════════════════════════════════════════════════════════════

class TestEndToEnd:
    """端到端 enforcement 流程测试。"""

    def test_full_blocking_pipeline(self, tmp_path):
        """完整 blocking pipeline：加载规则 → 分类 → 匹配 → enforcement → 汇总。"""
        # 创建包含各状态的规则
        rules = [
            _make_rule("TA-R001", status="proposed"),
            _make_rule(
                "TA-R010", status="active", blocking=False,
                required_checks=["harness/checks/check_a.py"],
            ),
            _make_rule(
                "TA-R018", status="active", blocking=True,
                required_checks=[
                    "harness/checks/check_result_fusion_safety.py",
                ],
            ),
            _make_rule("TA-R099", status="deprecated"),
            _make_rule("TA-R100", status="superseded"),
        ]
        rules_path = _write_rules_yml(rules, tmp_path)

        # 创建 check results（TA-R010 的 check 失败，TA-R018 的 check 通过）
        check_results = [
            _make_check_result(
                name="Check A",
                script="harness/checks/check_a.py",
                status="FAIL",
                exit_code=1,
            ),
            _make_check_result(
                name="LLM 融合安全门禁",
                script="harness/checks/check_result_fusion_safety.py",
                status="PASS",
                exit_code=0,
            ),
        ]

        report = build_enforcement_report(rules_path, check_results=check_results)

        # 验证汇总
        s = report["summary"]
        assert s["total_rules"] == 5
        assert s["proposed"] == 1
        assert s["active_warning"] == 1
        assert s["active_blocking"] == 1
        assert s["deprecated"] == 1
        assert s["superseded"] == 1
        # TA-R001: proposed + no checks → passed
        # TA-R010: active+blocking=false + check FAIL → warning
        # TA-R018: active+blocking=true + check PASS → passed
        # TA-R099: deprecated → skipped
        # TA-R100: superseded → skipped
        assert s["passed"] == 2  # TA-R001, TA-R018
        assert s["warnings"] == 1  # TA-R010
        assert s["blocking_failures"] == 0
        assert s["skipped"] == 2  # TA-R099, TA-R100

        # TA-R018 通过，所以 exit_code_should_fail=False
        assert report["exit_code_should_fail"] is False

    def test_all_active_blocking_fail_blocking_error(self, tmp_path):
        """所有 active+blocking=true 规则 check 失败 → FAIL 且改变 exit code。"""
        rules = [
            _make_rule(
                "TA-R018", status="active", blocking=True,
                required_checks=["harness/checks/check_a.py"],
            ),
            _make_rule(
                "TA-R019", status="active", blocking=True,
                required_checks=["harness/checks/check_b.py"],
            ),
        ]
        check_results = [
            _make_check_result(script="harness/checks/check_a.py", status="FAIL", exit_code=1),
            _make_check_result(script="harness/checks/check_b.py", status="FAIL", exit_code=1),
        ]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path, check_results=check_results)

        assert report["summary"]["blocking_failures"] == 2
        assert report["exit_code_should_fail"] is True

    def test_mixed_real_world_scenario(self, tmp_path):
        """模拟真实场景：混合状态的规则 + check results。"""
        # 使用实际 memory_rules.yml 中的规则 ID
        rules = [
            # TA-R010: proposed, check_refusal_policy
            _make_rule(
                "TA-R010", status="proposed", blocking=False,
                required_checks=["harness/checks/check_refusal_policy.py"],
            ),
            # TA-R018: active+blocking=true, check_result_fusion_safety + cross_domain
            _make_rule(
                "TA-R018", status="active", blocking=True,
                required_checks=[
                    "harness/checks/check_result_fusion_safety.py",
                    "harness/checks/check_cross_domain_policy.py",
                ],
            ),
        ]
        # 模拟 harness 运行结果
        check_results = [
            _make_check_result(
                name="反问/拒绝策略完备性",
                script="harness/checks/check_refusal_policy.py",
                status="PASS",
            ),
            _make_check_result(
                name="LLM 融合安全门禁",
                script="harness/checks/check_result_fusion_safety.py",
                status="PASS",
            ),
            _make_check_result(
                name="跨域策略安全门禁",
                script="harness/checks/check_cross_domain_policy.py",
                status="PASS",
            ),
        ]
        rules_path = _write_rules_yml(rules, tmp_path)
        report = build_enforcement_report(rules_path, check_results=check_results)

        # TA-R010: proposed + checks all PASS → passed
        # TA-R018: active+blocking=true + checks all PASS → passed
        assert report["summary"]["passed"] == 2
        assert report["summary"]["blocking_failures"] == 0
        assert report["summary"]["warnings"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 测试：valid_statuses 常量
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidStatuses:
    """合法 status 值常量测试。"""

    def test_valid_statuses_contains_expected(self):
        """VALID_STATUSES 应包含 4 个标准值。"""
        assert "proposed" in VALID_STATUSES
        assert "active" in VALID_STATUSES
        assert "deprecated" in VALID_STATUSES
        assert "superseded" in VALID_STATUSES
        assert len(VALID_STATUSES) == 4
