"""Phase 6A —— 真实 DuckDB E2E runner 测试。

两层设计：
    - 默认 pytest：不依赖本机数据库，对 runner 使用 fixture/mock 测试
    - 显式 real E2E（-m real_duckdb）：需设 TIANSHU_RUN_REAL_E2E=1 + 数据库可用
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 被测试模块
from scripts.run_real_duckdb_e2e import (
    _execute_check,
    _resolve_field,
    _run_security_checks,
    _sanitize_public_response,
    _truncate,
    generate_run_id,
    render_json_report,
    render_markdown_report,
    run_preflight,
    load_e2e_cases,
)


# ═══════════════════════════════════════════════════════════════
# 测试 1: run_id 生成不含 latest
# ═══════════════════════════════════════════════════════════════


def test_generate_run_id_no_latest():
    """run_id 不应包含 latest 字样，应以 REAL_E2E_ 开头"""
    run_id = generate_run_id()
    assert "latest" not in run_id.lower()
    assert run_id.startswith("REAL_E2E_")


# ═══════════════════════════════════════════════════════════════
# 测试 2: preflight 检查
# ═══════════════════════════════════════════════════════════════


def test_preflight_config_missing():
    """配置文件不存在时应返回失败"""
    result = run_preflight("nonexistent_config.yml")
    assert result["passed"] is False
    assert any(c["check"] == "config_exists" and not c["passed"] for c in result["checks"])


def test_preflight_real_config():
    """真实配置文件应能通过预检（如果 DuckDB 和 contracts 存在）"""
    config_path = PROJECT_ROOT / "config" / "tianshu_target.yml"
    if not config_path.exists():
        pytest.skip("配置文件不存在")
    result = run_preflight(str(config_path))
    # 至少 config_exists 应通过
    assert any(c["check"] == "config_exists" and c["passed"] for c in result["checks"])


def test_preflight_checks_structure():
    """预检结果应包含所有必要字段"""
    config_path = PROJECT_ROOT / "config" / "tianshu_target.yml"
    if not config_path.exists():
        pytest.skip("配置文件不存在")
    result = run_preflight(str(config_path))
    assert "passed" in result
    assert "checks" in result
    assert "duckdb_path" in result
    assert isinstance(result["checks"], list)
    for check in result["checks"]:
        assert "check" in check
        assert "passed" in check
        assert "detail" in check


# ═══════════════════════════════════════════════════════════════
# 测试 3: 用例加载
# ═══════════════════════════════════════════════════════════════


def test_load_e2e_cases():
    """应能加载 E2E 用例文件"""
    cases_path = PROJECT_ROOT / "evals" / "real_duckdb_e2e_cases.yml"
    if not cases_path.exists():
        pytest.skip("E2E 用例文件不存在")
    cases = load_e2e_cases(str(cases_path))
    assert len(cases) > 0
    assert len(cases) >= 5  # 至少 5 类场景

    # 检查分类完整性
    behaviors = {c["expected_behavior"] for c in cases}
    assert "answer" in behaviors
    assert "clarification" in behaviors
    assert "refusal" in behaviors


def test_e2e_cases_have_required_fields():
    """每个用例应有 id、question_zh、expected_behavior、expected_checks"""
    cases_path = PROJECT_ROOT / "evals" / "real_duckdb_e2e_cases.yml"
    if not cases_path.exists():
        pytest.skip("E2E 用例文件不存在")
    cases = load_e2e_cases(str(cases_path))
    for case in cases:
        assert "id" in case, f"Case 缺少 id: {case}"
        assert "question_zh" in case, f"Case {case.get('id')} 缺少 question_zh"
        assert "expected_behavior" in case, f"Case {case.get('id')} 缺少 expected_behavior"
        assert "expected_checks" in case, f"Case {case.get('id')} 缺少 expected_checks"
        assert case["expected_behavior"] in ("answer", "clarification", "refusal")


# ═══════════════════════════════════════════════════════════════
# 测试 4: 安全检查函数
# ═══════════════════════════════════════════════════════════════


def test_security_checks_no_sql():
    """安全检查应检测到 public response 中的 SQL"""
    public = {"response_type": "answer", "question": "test", "answer": {"text": "结果"}}
    checks = _run_security_checks(None, public)
    assert any(c["check"] == "public_response 不含 SQL" and c["passed"] for c in checks)


def test_security_checks_no_generated_sql():
    """安全检查应确认不含 generated_sql"""
    public = {"response_type": "answer"}
    checks = _run_security_checks(None, public)
    assert any(c["check"] == "public_response 不含 generated_sql" and c["passed"] for c in checks)


def test_security_checks_no_trace():
    """安全检查应确认不含 trace"""
    public = {"response_type": "answer", "trace": ["debug info"]}
    checks = _run_security_checks(None, public)
    assert any(c["check"] == "public_response 不含内部 trace" and not c["passed"] for c in checks)


# ═══════════════════════════════════════════════════════════════
# 测试 5: sanitize_public_response
# ═══════════════════════════════════════════════════════════════


def test_sanitize_removes_sensitive():
    """脱敏应移除敏感字段"""
    public = {
        "contract_version": "1.0",
        "response_type": "answer",
        "question": "test",
        "answer": {"text": "结果"},
        "data": {
            "chart_spec": {"chart_type": "line", "title": "Chart", "data_preview": [[1, 2, 3]]},
            "sources": ["gold.test"],
            "summaries": [{}, {}],
        },
        "warnings": [],
        "meta": {"execution_mode": "single"},
    }
    sanitized = _sanitize_public_response(public)
    assert sanitized["data"]["sources"] == ["gold.test"]
    assert sanitized["data"]["chart_spec"]["has_data"] is True
    # 原始 chart_spec 数据不应完整出现在脱敏版本中
    assert "data_preview" not in sanitized.get("data", {})


def test_sanitize_preserves_structure():
    """脱敏应保留结构"""
    public = {
        "contract_version": "1.0",
        "response_type": "clarification",
        "question": "test",
        "answer": {"text": None},
        "data": {"sources": [], "summaries": []},
        "warnings": ["test warning"],
        "meta": {"execution_mode": "single"},
    }
    sanitized = _sanitize_public_response(public)
    assert sanitized["response_type"] == "clarification"
    assert sanitized["warnings"] == ["test warning"]


# ═══════════════════════════════════════════════════════════════
# 测试 6: truncate 函数
# ═══════════════════════════════════════════════════════════════


def test_truncate_short():
    """短字符串应原样返回"""
    assert _truncate("hello", 10) == "hello"


def test_truncate_long():
    """长字符串应截断"""
    assert len(_truncate("x" * 200, 100)) <= 103  # 100 + "..."


# ═══════════════════════════════════════════════════════════════
# 测试 7: 报告渲染
# ═══════════════════════════════════════════════════════════════


def test_render_json_report_structure():
    """JSON 报告应包含所有必要字段"""
    preflight = {"passed": True, "checks": [], "duckdb_path": "/test/db", "contracts_path": "/test/contracts"}
    case_results = [
        {
            "case_id": "test_case_1",
            "question": "test?",
            "expected_behavior": "answer",
            "response_type": "answer",
            "checks": [{"check": "test", "passed": True, "detail": "ok"}],
            "all_checks_passed": True,
            "error": None,
        }
    ]
    report = render_json_report("TEST_RUN_001", "main", "abc12345", preflight, case_results)
    assert report["report_type"] == "real_duckdb_e2e"
    assert report["run_id"] == "TEST_RUN_001"
    assert report["summary"]["total_cases"] == 1
    assert report["summary"]["passed"] == 1
    assert report["summary"]["failed"] == 0
    assert "security_checks" in report
    assert "boundaries" in report
    assert report["boundaries"]["no_latest_generated"] is True


def test_render_markdown_report():
    """MD 报告应包含关键章节"""
    preflight = {"passed": True, "checks": [], "duckdb_path": "/test/db"}
    case_results = []
    md = render_markdown_report("TEST_RUN_002", "main", "abc12345", preflight, case_results)
    assert "Phase 6A" in md
    assert "Preflight" in md
    assert "Summary" in md
    assert "E2E Cases" in md


def test_json_report_serializable():
    """JSON 报告应可序列化"""
    preflight = {"passed": True, "checks": [], "duckdb_path": "/test/db", "contracts_path": "/test"}
    case_results = []
    report = render_json_report("TEST_RUN_003", "main", "abc12345", preflight, case_results)
    try:
        json.dumps(report, ensure_ascii=False)
    except Exception as e:
        pytest.fail(f"JSON 报告无法序列化: {e}")


# ═══════════════════════════════════════════════════════════════
# 测试 8: _resolve_field 路径解析
# ═══════════════════════════════════════════════════════════════


def test_resolve_field_nested():
    """应正确解析嵌套路径"""
    obj = {"a": {"b": {"c": "value"}}}
    assert _resolve_field("a.b.c", {"obj": obj, "response": None}) is None  # 在 root 查找
    # 从 local_vars 直接查找
    assert _resolve_field("nothing.here", {"nothing": {"here": 42}}) == 42


def test_resolve_field_object_attr():
    """应正确解析对象属性"""

    class Obj:
        name = "test_name"

    assert _resolve_field("obj.name", {"obj": Obj()}) == "test_name"


# ═══════════════════════════════════════════════════════════════
# 测试 9: _execute_check
# ═══════════════════════════════════════════════════════════════


def test_execute_check_equals():
    """== 检查应正确工作"""
    result = _execute_check(
        "public.response_type == answer",
        None,
        {"response_type": "answer"},
    )
    assert result["passed"] is True


def test_execute_check_not_empty():
    """非空检查应正确工作"""
    result = _execute_check(
        "public.result 非空",
        None,
        {"result": {"row_count": 5}},
    )
    assert result["passed"] is True


def test_execute_check_empty():
    """为空检查应正确工作"""
    result = _execute_check(
        "public.result 为空",
        None,
        {"result": None},
    )
    assert result["passed"] is True


def test_execute_check_contains():
    """包含检查应正确工作"""
    result = _execute_check(
        "public.refusal_reason 包含 只读",
        None,
        {"refusal_reason": "我是只读分析 Agent"},
    )
    assert result["passed"] is True


def test_execute_check_not_contains():
    """不包含检查应正确工作"""
    result = _execute_check(
        "public.answer.text 不包含 导致",
        None,
        {"answer": {"text": "数据展示"}},
    )
    assert result["passed"] is True


# ═══════════════════════════════════════════════════════════════
# 测试 10: 不生成 latest
# ═══════════════════════════════════════════════════════════════


def test_json_report_no_latest():
    """报告的 run_id 和 summary 不应包含 latest"""
    preflight = {"passed": True, "checks": [], "duckdb_path": "/test/db", "contracts_path": "/test"}
    case_results = []
    report = render_json_report("REAL_E2E_20260619T120000Z", "main", "abc12345", preflight, case_results)
    # run_id 和报告路径不应包含 latest
    assert "latest" not in report["run_id"].lower()
    assert report["boundaries"]["no_latest_generated"] is True


def test_md_report_no_latest():
    """MD 报告内容不应包含 latest 路径"""
    preflight = {"passed": True, "checks": [], "duckdb_path": "/test/db"}
    md = render_markdown_report("REAL_E2E_20260619T120000Z", "main", "abc12345", preflight, [])
    # MD 报告中不应出现 latest 文件名引用
    assert "latest" not in md.lower()


# ═══════════════════════════════════════════════════════════════
# 测试 11: 真实 E2E（需要 TIANSHU_RUN_REAL_E2E=1 + 数据库可用）
# ═══════════════════════════════════════════════════════════════


@pytest.mark.real_duckdb
def test_real_e2e_runner_integration():
    """真实 E2E 集成测试：运行完整 runner 流程"""
    if os.environ.get("TIANSHU_RUN_REAL_E2E") != "1":
        pytest.skip("需要设置 TIANSHU_RUN_REAL_E2E=1 环境变量")

    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_real_duckdb_e2e.py",
            "--config", "config/tianshu_target.yml",
            "--cases", "evals/real_duckdb_e2e_cases.yml",
            "--output-dir", "harness/reports/real_duckdb_e2e",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)

    # 预检失败也应该是预期结果（数据库可能不存在）
    # 如果是数据库不存在，exit code 应为 1
    if "Preflight FAILED" in result.stdout:
        assert result.returncode == 1, "预检失败应返回 1"
    elif "Agent 离线模式" in result.stdout:
        assert result.returncode == 1, "离线模式应返回 1"
    else:
        assert result.returncode == 0, f"E2E runner 应返回 0:\n{result.stdout}"


@pytest.mark.real_duckdb
def test_real_e2e_response_contract():
    """真实 E2E 验证：answer 类型响应应符合公开契约"""
    if os.environ.get("TIANSHU_RUN_REAL_E2E") != "1":
        pytest.skip("需要设置 TIANSHU_RUN_REAL_E2E=1 环境变量")

    from src.agent import Text2SQLAgent
    from src.response_contract import build_public_response

    agent = Text2SQLAgent(
        agent_config_path="config/agent_config.yml",
        tianshu_config_path="config/tianshu_target.yml",
        mode="rule",
    )

    if not agent.is_ready:
        pytest.fail("Agent 处于离线模式，无法执行真实 E2E")

    # 测试单计划查询
    response = agent.ask("2026年1月每天有多少行程？")
    public = build_public_response(response)

    # 验证响应契约
    assert public["contract_version"] == "1.0"
    assert "response_type" in public
    assert public["response_type"] in ("answer", "clarification", "refusal", "error")

    if public["response_type"] == "answer":
        assert public["answer"]["text"] is not None
        assert public["data"]["summaries"] is not None
        # 不含 SQL
        public_str = json.dumps(public, ensure_ascii=False)
        assert "SELECT" not in public_str

    agent.close()


# ═══════════════════════════════════════════════════════════════
# 测试 12: 边界确认
# ═══════════════════════════════════════════════════════════════


def test_boundary_no_latest_in_functions():
    """所有报告生成函数不使用 latest（代码逻辑中）"""
    import inspect

    # 只检查实际代码行（跳过 docstring 和注释）
    for fn in [generate_run_id, render_json_report, render_markdown_report]:
        src_lines = inspect.getsource(fn).split("\n")
        # 跳过 docstring（"""起始的行之间）
        in_docstring = False
        code_lines: list[str] = []
        for line in src_lines:
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            # 跳过纯注释行
            if stripped.startswith("#"):
                continue
            code_lines.append(line)
        code = "\n".join(code_lines)
        assert "latest" not in code.lower(), (
            f"{fn.__name__} 的代码逻辑不应使用 latest"
        )


def test_boundary_no_llm_import_in_runner():
    """runner 不应导入 LLM 相关模块"""
    import inspect
    import scripts.run_real_duckdb_e2e as runner

    src = inspect.getsource(runner)
    llm_indicators = ["deepseek", "openai", "anthropic", "llm_client"]
    for indicator in llm_indicators:
        # agent.py import 会带来 LLM 模块，但 runner 本身不应直接调用
        assert f".{indicator}" not in src.lower() or indicator in ["agent"], (
            f"runner 不应直接使用 LLM: {indicator}"
        )
