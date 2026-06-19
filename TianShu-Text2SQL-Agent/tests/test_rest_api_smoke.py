"""Phase 6B —— REST API Smoke Runner 测试（不依赖真实 DuckDB）。

覆盖：
    - run_id 生成不含 latest
    - JSON 报告结构
    - MD 报告结构
    - 检查逻辑（==, in, 非空）
    - 安全响应检查
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_rest_api_smoke import (
    generate_run_id,
    render_json_report,
    render_markdown_report,
    resolve_field,
    execute_check,
    _run_security_check,
    SECURITY_CHECKS,
)


# ═══════════════════════════════════════════════════════════════
# 测试组 1: run_id 生成
# ═══════════════════════════════════════════════════════════════


def test_generate_run_id_no_latest():
    """run_id 不应包含 latest"""
    run_id = generate_run_id()
    assert "latest" not in run_id.lower()
    assert run_id.startswith("REST_API_SMOKE_")


def test_generate_run_id_unique():
    """连续生成的 run_id 应不同"""
    ids = {generate_run_id() for _ in range(5)}
    assert len(ids) == 5


# ═══════════════════════════════════════════════════════════════
# 测试组 2: 字段解析
# ═══════════════════════════════════════════════════════════════


def test_resolve_field_simple():
    """简单字段解析"""
    data = {"status": "alive"}
    assert resolve_field("status", data) == "alive"


def test_resolve_field_nested():
    """嵌套字段解析"""
    data = {"data": {"summaries": [1, 2, 3]}}
    assert resolve_field("data.summaries", data) == [1, 2, 3]


def test_resolve_field_missing():
    """缺失字段返回 None"""
    data = {"a": 1}
    assert resolve_field("b", data) is None


def test_resolve_field_deep_nested():
    """多层嵌套解析"""
    data = {"a": {"b": {"c": "value"}}}
    assert resolve_field("a.b.c", data) == "value"


# ═══════════════════════════════════════════════════════════════
# 测试组 3: 检查逻辑
# ═══════════════════════════════════════════════════════════════


def test_execute_check_equals_pass():
    """== 检查通过"""
    passed, _ = execute_check(
        {"field": "status", "op": "==", "value": "alive"},
        {"status": "alive"},
    )
    assert passed is True


def test_execute_check_equals_fail():
    """== 检查失败"""
    passed, _ = execute_check(
        {"field": "status", "op": "==", "value": "alive"},
        {"status": "not_ready"},
    )
    assert passed is False


def test_execute_check_in_pass():
    """in 检查通过"""
    passed, _ = execute_check(
        {"field": "type", "op": "in", "value": ["a", "b"]},
        {"type": "a"},
    )
    assert passed is True


def test_execute_check_in_fail():
    """in 检查失败"""
    passed, _ = execute_check(
        {"field": "type", "op": "in", "value": ["a", "b"]},
        {"type": "c"},
    )
    assert passed is False


def test_execute_check_non_empty_pass():
    """非空检查通过"""
    passed, _ = execute_check(
        {"field": "items", "op": "non_empty"},
        {"items": [1, 2]},
    )
    assert passed is True


def test_execute_check_non_empty_fail_empty_list():
    """空列表 → 非空检查失败"""
    passed, _ = execute_check(
        {"field": "items", "op": "non_empty"},
        {"items": []},
    )
    assert passed is False


def test_execute_check_non_empty_fail_none():
    """None → 非空检查失败"""
    passed, _ = execute_check(
        {"field": "items", "op": "non_empty"},
        {"items": None},
    )
    assert passed is False


# ═══════════════════════════════════════════════════════════════
# 测试组 4: 安全响应检查
# ═══════════════════════════════════════════════════════════════


def test_security_check_no_select():
    """check: 不含 SELECT"""
    assert _run_security_check("public_response 不含 SELECT", {"answer": {"text": "结果"}}) is True
    assert _run_security_check("public_response 不含 SELECT", {"answer": {"text": "SELECT 1"}}) is False


def test_security_check_no_generated_sql():
    """check: 不含 generated_sql"""
    assert _run_security_check("public_response 不含 generated_sql", {}) is True
    assert _run_security_check("public_response 不含 generated_sql", {"generated_sql": "..."}) is False


def test_security_check_no_trace():
    """check: 不含 trace"""
    assert _run_security_check("public_response 不含 trace", {}) is True
    assert _run_security_check("public_response 不含 trace", {"trace": ["debug"]}) is False


def test_security_check_no_api_key():
    """check: 不含 API Key"""
    assert _run_security_check("public_response 不含 API Key (sk-)", {}) is True
    assert _run_security_check("public_response 不含 API Key (sk-)", {"key": "sk-abc123"}) is False


def test_security_check_no_duckdb_path():
    """check: 不含 DuckDB 路径"""
    assert _run_security_check("public_response 不含 DuckDB 路径", {}) is True
    assert _run_security_check("public_response 不含 DuckDB 路径", {"db": "data.duckdb"}) is False


# ═══════════════════════════════════════════════════════════════
# 测试组 5: 报告渲染
# ═══════════════════════════════════════════════════════════════


def test_render_json_report_structure():
    """JSON 报告应包含所有必要字段"""
    preflight = {"duckdb_exists": True, "read_only": True, "contracts_exist": True}
    case_results = [
        {"case_id": "test", "name": "Test", "passed": True, "details": []}
    ]
    report = render_json_report("TEST_ID", "main", "abc123", preflight, case_results)
    assert report["report_type"] == "rest_api_smoke"
    assert report["run_id"] == "TEST_ID"
    assert report["summary"]["total_cases"] == 1
    assert report["summary"]["passed"] == 1
    assert report["summary"]["failed"] == 0
    assert "security_checks" in report
    assert "boundaries" in report
    assert report["boundaries"]["no_latest_generated"] is True


def test_render_json_report_no_latest():
    """JSON 报告的 run_id 不应包含 latest"""
    preflight = {"duckdb_exists": True, "read_only": True, "contracts_exist": True}
    report = render_json_report("REST_API_SMOKE_20260619T120000Z", "main", "abc", preflight, [])
    assert "latest" not in report["run_id"].lower()


def test_render_markdown_report():
    """MD 报告应包含关键章节"""
    preflight = {"duckdb_exists": True, "read_only": True, "contracts_exist": True}
    md = render_markdown_report("TEST_ID", "main", "abc", preflight, [])
    assert "Phase 6B" in md
    assert "Preflight" in md
    assert "Summary" in md
    assert "Smoke Cases" in md
    assert "Security Checks" in md
    assert "Boundaries" in md


def test_render_markdown_report_no_latest():
    """MD 报告中不应将文件路径标记为 latest"""
    preflight = {"duckdb_exists": True, "read_only": True, "contracts_exist": True}
    md = render_markdown_report("REST_API_SMOKE_20260619T120000Z", "main", "abc", preflight, [])
    # 不应包含 latest 文件名（如 _latest.md, _latest.json）
    assert "_latest" not in md.lower()
    # 不应建议使用 latest 文件
    assert "*_latest.*" not in md


def test_json_report_serializable():
    """JSON 报告应可序列化"""
    preflight = {"duckdb_exists": True, "read_only": True, "contracts_exist": True}
    case_results = [
        {"case_id": "test", "name": "Test", "passed": True, "details": [
            {"check": "check1", "passed": True, "detail": "ok"}
        ]}
    ]
    report = render_json_report("TEST_ID", "main", "abc", preflight, case_results)
    try:
        json.dumps(report, ensure_ascii=False)
    except Exception as e:
        pytest.fail(f"JSON 报告无法序列化: {e}")


# ═══════════════════════════════════════════════════════════════
# 测试组 6: 边界确认
# ═══════════════════════════════════════════════════════════════


def test_security_checks_list_complete():
    """安全检查列表应包含 5 项"""
    assert len(SECURITY_CHECKS) >= 5


def test_smoke_cases_exist():
    """smoke 用例应存在"""
    from scripts.run_rest_api_smoke import SMOKE_CASES
    assert len(SMOKE_CASES) >= 4  # health/live, health/ready, ask, clarification, refusal


def test_smoke_cases_have_required_fields():
    """每个 smoke 用例应有 id, name, method, path"""
    from scripts.run_rest_api_smoke import SMOKE_CASES
    for case in SMOKE_CASES:
        assert "id" in case
        assert "name" in case
        assert "method" in case
        assert "path" in case
        assert "expected_status" in case
        assert case["method"] in ("GET", "POST")
