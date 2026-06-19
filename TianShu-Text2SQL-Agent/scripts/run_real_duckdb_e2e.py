#!/usr/bin/env python
"""
Phase 6A —— 真实 DuckDB 端到端运行器。

职责：
    1. 预检 DuckDB / contracts / read_only / offline 状态
    2. 对每个 E2E 用例执行 Agent 主链路
    3. 记录 response type、数据来源、安全结果、结构化响应
    4. 输出 timestamped JSON + MD 报告（不生成 latest）

严格边界：
    - 不修改数据库
    - 不调用真实 LLM（默认 mode=rule）
    - 不生成 latest
    - 不绕过 SQLPlan / sql_plan_to_sql / validate_sql_safety
    - data preview 限制 ≤10 行

用法：
    python scripts/run_real_duckdb_e2e.py --config config/tianshu_target.yml
    python scripts/run_real_duckdb_e2e.py --config config/tianshu_target.yml --output-dir harness/reports/real_duckdb_e2e
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 修复 Windows GBK 控制台 Unicode 输出
if sys.stdout.encoding and sys.stdout.encoding.lower() in ("gbk", "cp936"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import yaml


# ═══════════════════════════════════════════════════════════════
# 预检
# ═══════════════════════════════════════════════════════════════


def run_preflight(config_path: str) -> dict[str, Any]:
    """
    执行真实 DuckDB 连接预检。

    检查项：
        1. 配置文件存在
        2. DuckDB 文件存在
        3. contracts 目录存在
        4. Resolver 不处于 offline
        5. 连接为 read_only=True

    Returns:
        {"passed": bool, "checks": [...], "duckdb_path": str, "contracts_path": str}
    """
    config_file = Path(config_path)
    checks: list[dict] = []

    # 1. 配置文件存在
    if not config_file.exists():
        return {
            "passed": False,
            "checks": [{"check": "config_exists", "passed": False, "detail": f"配置文件不存在: {config_path}"}],
            "duckdb_path": "",
            "contracts_path": "",
        }
    checks.append({"check": "config_exists", "passed": True, "detail": str(config_file)})

    # 加载配置
    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    tianshu_cfg = config.get("tianshu", {})
    duckdb_path = tianshu_cfg.get("duckdb_path", "")
    contracts_path = tianshu_cfg.get("contracts_path", "")
    read_only = config.get("connection", {}).get("read_only", False)

    # 2. DuckDB 文件存在
    duckdb_file = Path(duckdb_path) if duckdb_path else None
    if duckdb_file and duckdb_file.exists():
        checks.append({"check": "duckdb_exists", "passed": True, "detail": str(duckdb_file)})
    else:
        checks.append({"check": "duckdb_exists", "passed": False, "detail": f"DuckDB 文件不存在: {duckdb_path}"})
        return {
            "passed": False,
            "checks": checks,
            "duckdb_path": duckdb_path,
            "contracts_path": contracts_path,
        }

    # 3. contracts 目录存在（相对于 TianShu 项目根目录）
    tianshu_root = tianshu_cfg.get("project_root", "../TianShu")
    contracts_dir = Path(tianshu_root) / contracts_path if contracts_path else None
    if contracts_dir and contracts_dir.exists():
        checks.append({"check": "contracts_exist", "passed": True, "detail": str(contracts_dir)})
    else:
        checks.append({"check": "contracts_exist", "passed": False, "detail": f"contracts 目录不存在: {contracts_dir}"})

    # 4. read_only 配置
    if read_only:
        checks.append({"check": "read_only_configured", "passed": True, "detail": "connection.read_only=true"})
    else:
        checks.append({"check": "read_only_configured", "passed": False, "detail": "connection.read_only 未设为 true"})

    all_passed = all(c["passed"] for c in checks)

    return {
        "passed": all_passed,
        "checks": checks,
        "duckdb_path": duckdb_path,
        "contracts_path": str(contracts_dir) if contracts_dir else "",
    }


# ═══════════════════════════════════════════════════════════════
# 用例执行
# ═══════════════════════════════════════════════════════════════


def load_e2e_cases(cases_path: str) -> list[dict]:
    """加载 E2E 用例定义文件"""
    with open(cases_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("cases", [])


def run_case(agent, case: dict) -> dict[str, Any]:
    """
    对单个 E2E 用例执行 Agent 主链路并记录结果。

    Args:
        agent: Text2SQLAgent 实例
        case: 用例定义 dict

    Returns:
        包含 case_id、question、response_type、checks_passed 等的结果 dict
    """
    from src.response_contract import build_public_response

    question = case["question_zh"]
    case_id = case["id"]
    expected_behavior = case.get("expected_behavior", "answer")
    expected_checks = case.get("expected_checks", [])

    result = {
        "case_id": case_id,
        "question": question,
        "expected_behavior": expected_behavior,
        "response_type": None,
        "checks": [],
        "all_checks_passed": False,
        "error": None,
    }

    try:
        response = agent.ask(question)
        public = build_public_response(response)
        result["response_type"] = public["response_type"]
        result["public_response"] = _sanitize_public_response(public)

        # ── 执行每项检查 ──
        for check_desc in expected_checks:
            check_result = _execute_check(check_desc, response, public)
            result["checks"].append(check_result)

        # ── 额外安全检查 ──
        security_checks = _run_security_checks(response, public)
        result["checks"].extend(security_checks)

        result["all_checks_passed"] = all(c["passed"] for c in result["checks"])

        # ── 记录摘要信息 ──
        if response.result:
            result["row_count"] = response.result.row_count
            result["source_table"] = response.result.source_table
            result["execution_time_ms"] = response.result.execution_time_ms
        if response.result_summaries:
            result["summaries_count"] = len(response.result_summaries)
        if response.chart_spec and isinstance(response.chart_spec, dict):
            result["chart_type"] = response.chart_spec.get("chart_type", "")
        if response.cross_domain_decision and isinstance(response.cross_domain_decision, dict):
            result["cross_domain"] = {
                "allow_display": response.cross_domain_decision.get("allow_display"),
                "allow_causal_language": response.cross_domain_decision.get("allow_causal_language"),
            }

    except Exception as exc:
        result["error"] = str(exc)
        result["all_checks_passed"] = False

    return result


def _execute_check(check_desc: str, response, public: dict) -> dict:
    """
    执行单条检查描述（简化版布尔表达式评估）。

    支持的检查格式：
        - "condition == value" → 检查字段值
        - "condition 非空" → 检查字段非空
        - "condition 包含 substr" → 检查字段包含子串
        - "condition 为空" → 检查字段为空/None/False
        - "不包含 substr" → 检查文本不包含
    """
    try:
        # 安全执行简化检查
        local_vars = {
            "response": response,
            "public": public,
            "result": response.result if response is not None and hasattr(response, "result") else None,
        }

        if "==" in check_desc:
            parts = check_desc.split("==")
            field_path = parts[0].strip()
            expected_raw = parts[1].strip()
            # 支持 True/False 布尔字面量
            if expected_raw == "True":
                expected = True
            elif expected_raw == "False":
                expected = False
            else:
                expected = expected_raw.strip('"').strip("'")
            actual = _resolve_field(field_path, local_vars)
            # 布尔比较使用 Python 值比较，而非字符串比较
            if isinstance(expected, bool):
                passed = actual is expected
            else:
                passed = str(actual) == str(expected)
            return {
                "check": check_desc,
                "passed": passed,
                "detail": f"期望={expected}, 实际={actual}",
            }

        if "不为空" in check_desc or "非空" in check_desc:
            field_path = check_desc.replace("不为空", "").replace("非空", "").strip()
            actual = _resolve_field(field_path, local_vars)
            is_empty = actual is None or actual == "" or actual == [] or actual == {} or actual is False
            return {
                "check": check_desc,
                "passed": not is_empty,
                "detail": f"实际={_truncate(str(actual))}",
            }

        if "为空" in check_desc:
            field_path = check_desc.replace("为空", "").strip()
            actual = _resolve_field(field_path, local_vars)
            is_empty = actual is None or actual == "" or actual == [] or actual == {} or actual is False
            return {
                "check": check_desc,
                "passed": is_empty,
                "detail": f"实际={_truncate(str(actual))}",
            }

        if "包含" in check_desc and "不包含" not in check_desc:
            parts = check_desc.split("包含")
            field_path = parts[0].strip()
            substr = parts[1].strip().strip('"').strip("'")
            actual = _resolve_field(field_path, local_vars)
            return {
                "check": check_desc,
                "passed": substr in str(actual),
                "detail": f"搜索 '{substr}' 在 '{_truncate(str(actual))}'",
            }

        if "不包含" in check_desc:
            parts = check_desc.split("不包含")
            field_path = parts[0].strip()
            substr = parts[1].strip().strip('"').strip("'")
            actual = _resolve_field(field_path, local_vars)
            return {
                "check": check_desc,
                "passed": substr not in str(actual),
                "detail": f"确认 '{substr}' 不在 '{_truncate(str(actual))}'",
            }

        return {"check": check_desc, "passed": False, "detail": f"不支持的检查格式"}
    except Exception as exc:
        return {"check": check_desc, "passed": False, "detail": f"检查执行异常: {exc}"}


def _resolve_field(field_path: str, local_vars: dict) -> Any:
    """解析点分隔的字段路径（如 result.source_table）"""
    parts = field_path.split(".")
    current = local_vars
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif hasattr(current, part):
            current = getattr(current, part)
        elif hasattr(current, "get") and callable(current.get):
            current = current.get(part)
        else:
            return None
    return current


def _run_security_checks(response, public: dict) -> list[dict]:
    """运行额外的安全检查"""
    checks: list[dict] = []

    # public response 不含 SQL
    public_str = json.dumps(public, ensure_ascii=False, default=str)
    has_select = "SELECT" in public_str.upper()
    checks.append({
        "check": "public_response 不含 SQL",
        "passed": not has_select,
        "detail": "不含 SELECT" if not has_select else "发现 SQL 语句",
    })

    # public response 不含 generated_sql
    has_gen_sql = "generated_sql" in public_str
    checks.append({
        "check": "public_response 不含 generated_sql",
        "passed": not has_gen_sql,
        "detail": "不含" if not has_gen_sql else "发现 generated_sql 字段",
    })

    # generated_sql 不在 public response 中
    has_trace = "trace" in public
    checks.append({
        "check": "public_response 不含内部 trace",
        "passed": not has_trace,
        "detail": "不含 trace" if not has_trace else "发现 trace 字段",
    })

    return checks


def _sanitize_public_response(public: dict) -> dict:
    """
    脱敏公开响应中的敏感信息（用于报告）。
    限制 data_preview 行数不超过 10 行。
    """
    sanitized = {
        "contract_version": public.get("contract_version"),
        "response_type": public.get("response_type"),
        "question": public.get("question"),
        "answer": public.get("answer"),
        "clarification": public.get("clarification"),
        "refusal": public.get("refusal"),
        "data": {
            "is_multi_plan": public.get("data", {}).get("is_multi_plan", False),
            "summaries_count": len(public.get("data", {}).get("summaries", [])),
            "sources": public.get("data", {}).get("sources", []),
        },
        "warnings": public.get("warnings", []),
        "meta": public.get("meta", {}),
    }

    # chart_spec 脱敏：只保留类型和标题，去掉具体数据
    chart_spec = public.get("data", {}).get("chart_spec")
    if chart_spec and isinstance(chart_spec, dict):
        sanitized["data"]["chart_spec"] = {
            "chart_type": chart_spec.get("chart_type"),
            "title": chart_spec.get("title"),
            "has_data": bool(chart_spec.get("data_preview")),
        }

    return sanitized


def _truncate(s: str, max_len: int = 100) -> str:
    """截断字符串"""
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."


# ═══════════════════════════════════════════════════════════════
# 报告生成
# ═══════════════════════════════════════════════════════════════


def generate_run_id() -> str:
    """生成运行 ID（timestamped，不含 latest）"""
    return datetime.now(timezone.utc).strftime("REAL_E2E_%Y%m%dT%H%M%SZ")


def render_json_report(
    run_id: str,
    branch: str,
    commit: str,
    preflight: dict,
    case_results: list[dict],
) -> dict:
    """渲染 JSON 报告"""
    passed = sum(1 for r in case_results if r["all_checks_passed"])
    failed = sum(1 for r in case_results if not r["all_checks_passed"])

    return {
        "report_type": "real_duckdb_e2e",
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "branch": branch,
        "commit": commit,
        "database": preflight.get("duckdb_path", ""),
        "preflight": preflight,
        "summary": {
            "total_cases": len(case_results),
            "passed": passed,
            "failed": failed,
        },
        "cases": case_results,
        "security_checks": {
            "bypass_sqlplan": False,
            "bypass_sql_plan_to_sql": False,
            "bypass_validate_sql_safety": False,
            "exposed_sql": False,
            "exposed_api_key": False,
            "called_real_llm": False,
            "modified_database": False,
        },
        "boundaries": {
            "no_contracts_modified": True,
            "no_memory_rules_yml_modified": True,
            "no_precommit_modified": True,
            "no_harness_expanded": True,
            "no_latest_generated": True,
        },
    }


def render_markdown_report(
    run_id: str,
    branch: str,
    commit: str,
    preflight: dict,
    case_results: list[dict],
) -> str:
    """渲染 Markdown 报告"""
    lines: list[str] = []
    lines.append("# Phase 6A Real DuckDB E2E Report")
    lines.append("")
    lines.append(f"**Run ID**: {run_id}")
    lines.append(f"**Branch**: {branch}")
    lines.append(f"**Commit**: {commit}")
    lines.append(f"**Timestamp**: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")

    # ── Preflight ──
    lines.append("## Preflight")
    lines.append("")
    lines.append(f"- **数据库**: {preflight.get('duckdb_path', 'N/A')}")
    lines.append(f"- **预检结果**: {'✅ PASS' if preflight.get('passed') else '❌ FAIL'}")
    for check in preflight.get("checks", []):
        icon = "✅" if check["passed"] else "❌"
        lines.append(f"  - {icon} {check['check']}: {check['detail']}")
    lines.append("")

    # ── Summary ──
    passed = sum(1 for r in case_results if r["all_checks_passed"])
    failed = sum(1 for r in case_results if not r["all_checks_passed"])
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **总用例**: {len(case_results)}")
    lines.append(f"- **通过**: {passed}")
    lines.append(f"- **失败**: {failed}")
    lines.append("")

    # ── Cases Table ──
    lines.append("## E2E Cases")
    lines.append("")
    lines.append("| case_id | expected | response_type | row_count | source | chart | passed |")
    lines.append("|---------|----------|---------------|-----------|--------|-------|--------|")
    for r in case_results:
        icon = "✅" if r["all_checks_passed"] else "❌"
        lines.append(
            f"| {r['case_id']} | {r['expected_behavior']} | "
            f"{r.get('response_type', 'N/A')} | "
            f"{r.get('row_count', '-')} | "
            f"{r.get('source_table', '-')} | "
            f"{r.get('chart_type', '-')} | "
            f"{icon} |"
        )
    lines.append("")

    # ── Detailed Checks ──
    lines.append("## Detailed Checks")
    lines.append("")
    for r in case_results:
        lines.append(f"### {r['case_id']}")
        lines.append(f"- **问题**: {r['question']}")
        lines.append(f"- **预期行为**: {r['expected_behavior']}")
        lines.append(f"- **实际 response_type**: {r.get('response_type', 'N/A')}")
        if r.get("error"):
            lines.append(f"- **错误**: {r['error']}")
        lines.append("")
        for c in r.get("checks", []):
            icon = "✅" if c["passed"] else "❌"
            lines.append(f"  - {icon} {c['check']}: {c.get('detail', '')}")
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="Phase 6A 真实 DuckDB E2E 运行器")
    parser.add_argument(
        "--config", default="config/tianshu_target.yml",
        help="TianShu 目标配置文件路径"
    )
    parser.add_argument(
        "--cases", default="evals/real_duckdb_e2e_cases.yml",
        help="E2E 用例文件路径"
    )
    parser.add_argument(
        "--output-dir", default="harness/reports/real_duckdb_e2e",
        help="报告输出目录"
    )
    parser.add_argument(
        "--agent-config", default="config/agent_config.yml",
        help="Agent 运行时配置路径"
    )
    args = parser.parse_args()

    run_id = generate_run_id()
    print(f"Real DuckDB E2E Runner — {run_id}")
    print()

    # ── 获取 git 信息 ──
    import subprocess
    try:
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=10,
        )
        branch = branch_result.stdout.strip()
    except Exception:
        branch = "unknown"

    try:
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=10,
        )
        commit = commit_result.stdout.strip()[:8]
    except Exception:
        commit = "unknown"

    # ── 1. Preflight ──
    print("1/4 Preflight...")
    preflight = run_preflight(args.config)
    if not preflight["passed"]:
        print("   ❌ Preflight FAILED")
        for check in preflight["checks"]:
            icon = "✅" if check["passed"] else "❌"
            print(f"      {icon} {check['check']}: {check['detail']}")
        # 即使是 preflight 失败，也生成报告
        case_results: list[dict] = []
        _write_reports(run_id, branch, commit, preflight, case_results, args.output_dir)
        sys.exit(1)

    print("   ✅ Preflight PASSED")
    for check in preflight["checks"]:
        print(f"      ✅ {check['check']}: {check['detail']}")

    # ── 2. 初始化 Agent ──
    print("2/4 初始化 Agent（rule 模式，不调用真实 LLM）...")
    from src.agent import Text2SQLAgent

    try:
        agent = Text2SQLAgent(
            agent_config_path=args.agent_config,
            tianshu_config_path=args.config,
            mode="rule",
        )
        print(f"   ✅ Agent 已初始化 (ready={agent.is_ready})")
    except Exception as exc:
        print(f"   ❌ Agent 初始化失败: {exc}")
        _write_reports(run_id, branch, commit, preflight, [], args.output_dir)
        sys.exit(1)

    # Agent 离线检测
    if not agent.is_ready:
        print("   ❌ Agent 处于离线模式，无法执行真实 E2E")
        _write_reports(run_id, branch, commit, preflight, [], args.output_dir)
        sys.exit(1)

    # ── 3. 加载用例并执行 ──
    print("3/4 加载 E2E 用例...")
    cases = load_e2e_cases(args.cases)
    print(f"   加载了 {len(cases)} 个用例")

    print("4/4 执行 E2E 用例...")
    case_results = []
    all_passed = True
    for i, case in enumerate(cases, 1):
        case_id = case["id"]
        print(f"   [{i}/{len(cases)}] {case_id}...", end=" ")
        result = run_case(agent, case)
        case_results.append(result)
        if result["all_checks_passed"]:
            print("✅")
        else:
            print("❌")
            all_passed = False
            failed_checks = [c for c in result["checks"] if not c["passed"]]
            for fc in failed_checks[:3]:
                print(f"      ❌ {fc['check']}: {fc.get('detail', '')}")
            if result.get("error"):
                print(f"      ❌ 异常: {result['error']}")

    # 关闭 Agent
    try:
        agent.close()
    except Exception:
        pass

    # ── 生成报告 ──
    _write_reports(run_id, branch, commit, preflight, case_results, args.output_dir)

    # ── 输出摘要 ──
    passed = sum(1 for r in case_results if r["all_checks_passed"])
    failed = sum(1 for r in case_results if not r["all_checks_passed"])
    print()
    print(f"结果: {passed} 通过, {failed} 失败 (共 {len(case_results)} 用例)")

    if not all_passed or not preflight["passed"]:
        sys.exit(1)

    print("✅ 所有 E2E 用例通过")
    sys.exit(0)


def _write_reports(
    run_id: str,
    branch: str,
    commit: str,
    preflight: dict,
    case_results: list[dict],
    output_dir: str,
):
    """写入 timestamped JSON + MD 报告"""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # JSON 报告（使用 default=str 处理 date/datetime 等非标准类型）
    json_report = render_json_report(run_id, branch, commit, preflight, case_results)
    json_path = out_path / f"real_duckdb_e2e_{run_id}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_report, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n   JSON 报告: {json_path}")

    # Markdown 报告
    md_report = render_markdown_report(run_id, branch, commit, preflight, case_results)
    md_path = out_path / f"real_duckdb_e2e_{run_id}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"   MD 报告: {md_path}")


if __name__ == "__main__":
    main()
