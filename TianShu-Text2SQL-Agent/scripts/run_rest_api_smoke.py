#!/usr/bin/env python
"""Phase 6B —— REST API 真实 DuckDB Smoke 测试。

启动 API 服务，执行健康检查和问数验证，生成 timestamped 报告。

约束：
    - 数据库不可用时返回非 0，不得静默 PASS
    - 不生成 latest 文件
    - 报告只包含安全信息（不含 SQL、API Key）
    - read_only 保持

用法：
    python scripts/run_rest_api_smoke.py --api-config config/api_config.yml --tianshu-config config/tianshu_target.yml
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════
# Smoke 测试用例定义
# ═══════════════════════════════════════════════════════════════

SMOKE_CASES: list[dict[str, Any]] = [
    {
        "id": "smoke_health_live",
        "name": "健康检查 — live",
        "method": "GET",
        "path": "/health/live",
        "body": None,
        "expected_status": 200,
        "checks": [
            {"check": "status == alive", "field": "status", "op": "==", "value": "alive"},
        ],
    },
    {
        "id": "smoke_health_ready",
        "name": "健康检查 — ready",
        "method": "GET",
        "path": "/health/ready",
        "body": None,
        "expected_status": 200,
        "checks": [
            {"check": "status == ready", "field": "status", "op": "==", "value": "ready"},
            {"check": "agent_online == True", "field": "agent_online", "op": "==", "value": True},
        ],
    },
    {
        "id": "smoke_ask_single_trip",
        "name": "问数 — 单计划：行程日汇总",
        "method": "POST",
        "path": "/v1/ask",
        "body": {"question": "2026年1月每天有多少行程？"},
        "expected_status": 200,
        "checks": [
            {"check": "contract_version == 1.0", "field": "contract_version", "op": "==", "value": "1.0"},
            {"check": "response_type == answer", "field": "response_type", "op": "==", "value": "answer"},
            {"check": "data.summaries 非空", "field": "data.summaries", "op": "non_empty"},
            {"check": "data.sources 非空", "field": "data.sources", "op": "non_empty"},
        ],
    },
    {
        "id": "smoke_ask_clarification",
        "name": "问数 — 歧义反问",
        "method": "POST",
        "path": "/v1/ask",
        "body": {"question": "最近每天有多少行程？"},
        "expected_status": 200,
        "checks": [
            {"check": "contract_version == 1.0", "field": "contract_version", "op": "==", "value": "1.0"},
            {"check": "response_type in [clarification, answer]", "field": "response_type", "op": "in", "value": ["clarification", "answer"]},
        ],
    },
    {
        "id": "smoke_ask_refusal",
        "name": "问数 — 写操作拒绝",
        "method": "POST",
        "path": "/v1/ask",
        "body": {"question": "帮我删除2026年1月的异常行程数据"},
        "expected_status": 200,
        "checks": [
            {"check": "contract_version == 1.0", "field": "contract_version", "op": "==", "value": "1.0"},
            {"check": "response_type == refusal", "field": "response_type", "op": "==", "value": "refusal"},
        ],
    },
]

# ═══════════════════════════════════════════════════════════════
# 安全响应检查（所有成功响应必须通过）
# ═══════════════════════════════════════════════════════════════

SECURITY_CHECKS = [
    "public_response 不含 SELECT",
    "public_response 不含 generated_sql",
    "public_response 不含 trace",
    "public_response 不含 API Key (sk-)",
    "public_response 不含 DuckDB 路径",
]


def generate_run_id() -> str:
    """生成 run_id（不含 latest）"""
    from uuid import uuid4
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    suffix = uuid4().hex[:8]
    return f"REST_API_SMOKE_{ts}_{suffix}"


def load_api_config(config_path: str) -> dict[str, Any]:
    """加载 API 配置文件"""
    import yaml

    path = Path(config_path)
    if not path.exists():
        return {"server": {"host": "127.0.0.1", "port": 8000}}

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def start_api_server(api_config_path: str) -> tuple[subprocess.Popen, str, int]:
    """启动 API 服务器子进程。

    Returns:
        (process, host, port)
    """
    config = load_api_config(api_config_path)
    server_cfg = config.get("server", {})
    host = server_cfg.get("host", "127.0.0.1")
    port = server_cfg.get("port", 8000)

    # 安全检查：不得绑定 0.0.0.0
    if host == "0.0.0.0":
        host = "127.0.0.1"

    # 查找可用端口（如果默认端口被占用）
    # 直接使用配置的端口
    env = os.environ.copy()
    # 确保不启用真实 LLM
    env.setdefault("TIANSHU_MODE", "rule")

    proc = subprocess.Popen(
        [
            sys.executable,
            "scripts/run_api.py",
            "--config", api_config_path,
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )

    return proc, host, port


def wait_for_server(host: str, port: int, timeout: float = 30.0) -> bool:
    """等待 API 服务器就绪（轮询 /health/live）"""
    import urllib.request
    import urllib.error

    deadline = time.monotonic() + timeout
    url = f"http://{host}:{port}/health/live"

    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionRefusedError, OSError):
            pass
        time.sleep(0.5)

    return False


def stop_api_server(proc: subprocess.Popen) -> None:
    """优雅停止 API 服务器"""
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    except Exception:
        pass


def resolve_field(path: str, data: dict[str, Any]) -> Any:
    """解析点分隔路径，如 data.summaries → data['data']['summaries']"""
    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def execute_check(check: dict[str, str], response_data: dict[str, Any]) -> tuple[bool, str]:
    """执行单个检查。

    支持的操作：
        - == : 等于
        - in : 在列表中
        - 非空: 非 None/非空列表
    """
    field_path = check["field"]
    op = check.get("op", "==")
    expected = check.get("value")

    actual = resolve_field(field_path, response_data)

    if op == "==":
        passed = actual == expected
        detail = f"{field_path}={actual!r}, 期望={expected!r}"
    elif op == "in":
        passed = actual in expected
        detail = f"{field_path}={actual!r}, 期望∈{expected!r}"
    elif op == "non_empty":
        passed = bool(actual)
        detail = f"{field_path}={'非空' if passed else '为空'}"
    else:
        passed = False
        detail = f"未知操作: {op}"

    return passed, detail


def run_smoke_case(case: dict[str, Any], base_url: str) -> dict[str, Any]:
    """执行单个 smoke 测试用例。

    Returns:
        {"case_id": str, "passed": bool, "details": [...]}
    """
    import urllib.request
    import urllib.error

    method = case["method"]
    path = case["path"]
    body = case.get("body")
    expected_status = case.get("expected_status")

    url = f"{base_url}{path}"
    details: list[dict[str, Any]] = []
    all_passed = True

    try:
        if method == "GET":
            req = urllib.request.Request(url)
        elif method == "POST":
            data = json.dumps(body).encode("utf-8") if body else None
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
        else:
            return {"case_id": case["id"], "passed": False, "details": [{"check": "method", "passed": False, "detail": f"未知方法: {method}"}]}

        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8")
            try:
                response_data = json.loads(raw)
            except json.JSONDecodeError:
                response_data = {"_raw": raw}

            # 检查状态码
            if expected_status is not None:
                status_passed = status == expected_status
                details.append({
                    "check": f"HTTP status == {expected_status}",
                    "passed": status_passed,
                    "detail": f"实际={status}",
                })
                if not status_passed:
                    all_passed = False

            # 执行业务检查
            for check in case.get("checks", []):
                passed, detail = execute_check(check, response_data)
                details.append({
                    "check": check["check"],
                    "passed": passed,
                    "detail": detail,
                })
                if not passed:
                    all_passed = False

            # 安全响应检查
            for sec_check_name in SECURITY_CHECKS:
                sec_passed = _run_security_check(sec_check_name, response_data)
                details.append({
                    "check": sec_check_name,
                    "passed": sec_passed,
                    "detail": "OK" if sec_passed else "FAIL",
                })
                if not sec_passed:
                    all_passed = False

    except urllib.error.HTTPError as e:
        details.append({"check": "HTTP request", "passed": False, "detail": f"HTTP {e.code}: {e.reason}"})
        all_passed = False
    except Exception as e:
        details.append({"check": "HTTP request", "passed": False, "detail": str(e)})
        all_passed = False

    return {
        "case_id": case["id"],
        "name": case.get("name", case["id"]),
        "passed": all_passed,
        "details": details,
    }


def _run_security_check(check_name: str, data: dict[str, Any]) -> bool:
    """执行安全响应检查"""
    text = json.dumps(data, ensure_ascii=False)
    if check_name == "public_response 不含 SELECT":
        return "SELECT" not in text
    elif check_name == "public_response 不含 generated_sql":
        return "generated_sql" not in text
    elif check_name == "public_response 不含 trace":
        return "trace" not in text or (isinstance(data.get("trace"), list) and len(data.get("trace", [])) == 0)
    elif check_name == "public_response 不含 API Key (sk-)":
        return "sk-" not in text
    elif check_name == "public_response 不含 DuckDB 路径":
        return ".duckdb" not in text
    return True


def render_json_report(
    run_id: str,
    branch: str,
    commit: str,
    preflight: dict[str, Any],
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """渲染 JSON 报告"""
    total = len(case_results)
    passed = sum(1 for c in case_results if c["passed"])

    return {
        "report_type": "rest_api_smoke",
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "branch": branch,
        "commit": commit,
        "preflight": preflight,
        "summary": {
            "total_cases": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": f"{passed}/{total}" if total > 0 else "N/A",
        },
        "cases": case_results,
        "security_checks": SECURITY_CHECKS,
        "boundaries": {
            "no_latest_generated": "latest" not in run_id.lower(),
            "no_real_llm": True,
            "read_only": preflight.get("read_only", False),
        },
    }


def render_markdown_report(
    run_id: str,
    branch: str,
    commit: str,
    preflight: dict[str, Any],
    case_results: list[dict[str, Any]],
) -> str:
    """渲染 Markdown 报告"""
    total = len(case_results)
    passed = sum(1 for c in case_results if c["passed"])
    failed = total - passed

    lines = [
        f"# Phase 6B REST API Smoke Report",
        "",
        f"**Run ID**: {run_id}",
        f"**Branch**: {branch}",
        f"**Commit**: {commit}",
        f"**Timestamp**: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Preflight",
        "",
        f"- DuckDB 存在: {preflight.get('duckdb_exists', 'N/A')}",
        f"- read_only: {preflight.get('read_only', 'N/A')}",
        f"- contracts 存在: {preflight.get('contracts_exist', 'N/A')}",
        "",
        "## Summary",
        "",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| 总用例 | {total} |",
        f"| 通过 | {passed} |",
        f"| 失败 | {failed} |",
        f"| 通过率 | {passed}/{total} |",
        "",
        "## Smoke Cases",
        "",
    ]

    for case in case_results:
        status = "✅" if case["passed"] else "❌"
        lines.append(f"### {status} {case['name']} (`{case['case_id']}`)")
        lines.append("")
        for detail in case.get("details", []):
            icon = "✅" if detail["passed"] else "❌"
            lines.append(f"- {icon} {detail['check']}: {detail['detail']}")
        lines.append("")

    lines.extend([
        "## Security Checks",
        "",
        "所有成功响应必须通过以下安全检查：",
        "",
    ])
    for check in SECURITY_CHECKS:
        lines.append(f"- {check}")

    lines.extend([
        "",
        "## Boundaries",
        "",
        f"- 不生成 latest: {run_id.lower().find('latest') < 0}",
        f"- 不调用真实 LLM: True",
        f"- read_only: {preflight.get('read_only', False)}",
        "",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Phase 6B REST API Smoke Runner")
    parser.add_argument(
        "--api-config", default="config/api_config.yml",
        help="API 配置文件路径",
    )
    parser.add_argument(
        "--tianshu-config", default="config/tianshu_target.yml",
        help="TianShu 配置文件路径",
    )
    parser.add_argument(
        "--output-dir", default="harness/reports/rest_api_smoke",
        help="报告输出目录",
    )
    parser.add_argument(
        "--skip-server", action="store_true",
        help="跳过启动服务（使用已运行的实例）",
    )
    parser.add_argument(
        "--base-url", default=None,
        help="已运行服务的 base URL（如 http://127.0.0.1:8000）",
    )
    args = parser.parse_args()

    # 生成 run_id
    run_id = generate_run_id()
    print(f"REST API Smoke Runner: {run_id}")

    # 获取 git 信息
    import subprocess as sp
    try:
        branch = sp.check_output(["git", "branch", "--show-current"], cwd=PROJECT_ROOT, text=True).strip()
        commit = sp.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT, text=True).strip()
    except Exception:
        branch = "unknown"
        commit = "unknown"

    # ═══════════════════════════════════════════════════════════
    # Preflight 检查
    # ═══════════════════════════════════════════════════════════
    print("\n[Preflight]")

    preflight: dict[str, Any] = {
        "duckdb_exists": False,
        "contracts_exist": False,
        "read_only": False,
        "passed": True,
    }

    import yaml
    tianshu_config_path = PROJECT_ROOT / args.tianshu_config
    if tianshu_config_path.exists():
        with open(tianshu_config_path, "r", encoding="utf-8") as f:
            tianshu_cfg = yaml.safe_load(f) or {}

        # 检查 DuckDB 文件
        duckdb_path_str = tianshu_cfg.get("tianshu", {}).get("duckdb_path", "")
        if duckdb_path_str:
            duckdb_path = Path(duckdb_path_str)
            preflight["duckdb_exists"] = duckdb_path.exists()
            preflight["duckdb_path"] = str(duckdb_path)

            # 检查 read_only
            conn_cfg = tianshu_cfg.get("connection", {})
            preflight["read_only"] = conn_cfg.get("read_only", False)

        # 检查 contracts 目录
        tianshu_root = tianshu_cfg.get("tianshu", {}).get("project_root", "../TianShu")
        contracts_rel = tianshu_cfg.get("tianshu", {}).get("contracts_path", "contracts")
        contracts_path = (PROJECT_ROOT / tianshu_root / contracts_rel).resolve()
        preflight["contracts_exist"] = contracts_path.exists()

    if not preflight["duckdb_exists"]:
        print("[FAIL] DuckDB 文件不存在，数据库不可用")
        preflight["passed"] = False

    if not preflight["contracts_exist"]:
        print("[FAIL] contracts 目录不存在")
        preflight["passed"] = False

    if not preflight["read_only"]:
        print("[WARN] read_only 未启用")

    # 只在 preflight 失败且不是使用已运行实例时退出
    if not preflight["passed"] and not args.skip_server:
        print("\n[FATAL] Preflight 失败，退出（数据库不可用）")
        sys.exit(1)

    # ═══════════════════════════════════════════════════════════
    # 启动或连接 API 服务
    # ═══════════════════════════════════════════════════════════
    proc = None
    base_url = args.base_url

    if args.skip_server:
        if not base_url:
            config = load_api_config(args.api_config)
            server_cfg = config.get("server", {})
            host = server_cfg.get("host", "127.0.0.1")
            port = server_cfg.get("port", 8000)
            base_url = f"http://{host}:{port}"
        print(f"\n[INFO] 使用已运行的 API 服务: {base_url}")
    else:
        config = load_api_config(args.api_config)
        server_cfg = config.get("server", {})
        host = server_cfg.get("host", "127.0.0.1")
        port = server_cfg.get("port", 8000)
        base_url = f"http://{host}:{port}"

        print(f"\n[INFO] 启动 API 服务: {host}:{port}")
        proc, host, port = start_api_server(args.api_config)
        base_url = f"http://{host}:{port}"

        # 等待服务就绪
        print("[INFO] 等待服务就绪...")
        if not wait_for_server(host, port, timeout=30):
            print("[FATAL] 服务启动超时")
            stop_api_server(proc)
            sys.exit(1)
        print("[OK] 服务已就绪")

    # ═══════════════════════════════════════════════════════════
    # 执行 Smoke 测试
    # ═══════════════════════════════════════════════════════════
    print(f"\n[Smoke] 执行 {len(SMOKE_CASES)} 个用例...")
    case_results: list[dict[str, Any]] = []

    for case in SMOKE_CASES:
        result = run_smoke_case(case, base_url)
        case_results.append(result)
        status = "✅" if result["passed"] else "❌"
        print(f"  {status} {case['id']} - {case['name']}")

    # ═══════════════════════════════════════════════════════════
    # 停止服务
    # ═══════════════════════════════════════════════════════════
    if proc is not None:
        print("\n[INFO] 停止 API 服务...")
        stop_api_server(proc)
        print("[OK] 服务已停止")

    # ═══════════════════════════════════════════════════════════
    # 生成报告
    # ═══════════════════════════════════════════════════════════
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    json_report = render_json_report(run_id, branch, commit, preflight, case_results)
    md_report = render_markdown_report(run_id, branch, commit, preflight, case_results)

    # 写入文件（timestamped，不含 latest）
    json_path = output_dir / f"rest_api_smoke_{run_id}.json"
    md_path = output_dir / f"rest_api_smoke_{run_id}.md"

    json_path.write_text(json.dumps(json_report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(md_report, encoding="utf-8")

    print(f"\n[报告] JSON: {json_path}")
    print(f"[报告] MD:   {md_path}")

    # 退出码
    total_passed = sum(1 for c in case_results if c["passed"])
    if total_passed < len(case_results) or not preflight.get("passed", True):
        print(f"\n[FAIL] {len(case_results) - total_passed}/{len(case_results)} 用例失败")
        sys.exit(1)

    print(f"\n[PASS] 全部 {len(case_results)} 个用例通过")
    sys.exit(0)


if __name__ == "__main__":
    main()
