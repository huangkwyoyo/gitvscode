#!/usr/bin/env python
"""Phase 6C —— 本地 API 安全闭环 runner。

一次性自动完成：
    设置临时令牌 → 启动 API 子进程 → 等待 live/ready
    → 验证未认证请求失败 → 验证认证 answer → 验证 clarification
    → 验证 refusal → 验证限流 → 验证审计内容
    → 验证无敏感信息 → 关闭服务 → 验证资源释放 → 生成报告

用法：
    python scripts/run_local_api_closure.py \
        --api-config config/api_config.yml \
        --tianshu-config config/tianshu_target.yml

安全：
    - 不调用真实 LLM（使用 rule 模式）
    - 不执行写 SQL
    - 数据库保持 read_only
    - 不生成 latest
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════

RUN_ID = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}"
REPORT_DIR = PROJECT_ROOT / "harness" / "reports" / "local_api_closure"
AUDIT_DIR = PROJECT_ROOT / "harness" / "reports" / "local_api_audit"

# 安全敏感模式（用于验证响应不含以下内容）
FORBIDDEN_PATTERNS = [
    b"SELECT", b"INSERT", b"DELETE", b"DROP",
    b"generated_sql", b"trace", b"Traceback",
    b"sk-",  # API Key 前缀
    b"duckdb",  # 数据库路径
]


def generate_run_id() -> str:
    """生成唯一运行 ID"""
    return f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}"


def check_preconditions(args) -> list[str]:
    """检查前置条件，返回错误列表"""
    errors = []

    # 检查 DuckDB 文件
    import yaml
    tianshu_cfg_path = Path(args.tianshu_config)
    if not tianshu_cfg_path.exists():
        errors.append(f"TianShu 配置文件不存在: {tianshu_cfg_path}")
    else:
        with open(tianshu_cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        db_path = cfg.get("database", {}).get("path", "")
        if db_path and not Path(db_path).exists():
            errors.append(f"DuckDB 文件不存在: {db_path}")

    # 检查 contracts 目录
    contracts_dir = cfg.get("database", {}).get("contracts_dir", "")
    if contracts_dir and not Path(contracts_dir).is_dir():
        errors.append(f"Contracts 目录不存在: {contracts_dir}")

    # 检查 token 环境变量
    token = os.environ.get("TIANSHU_LOCAL_API_TOKEN", "")
    if not token:
        errors.append("环境变量 TIANSHU_LOCAL_API_TOKEN 未设置")
    elif len(token) < 32:
        errors.append(f"TIANSHU_LOCAL_API_TOKEN 长度不足（需要 >= 32，当前 {len(token)}）")

    return errors


def start_api_server(api_config: str, host: str, port: int) -> subprocess.Popen:
    """启动 API 子进程"""
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "run_api.py"),
        "--config", api_config,
        "--host", host,
        "--port", str(port),
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(PROJECT_ROOT),
    )
    return proc


def wait_for_server(port: int, timeout: float = 30.0) -> bool:
    """等待服务器启动完成"""
    import urllib.request
    import urllib.error

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health/live",
                timeout=2,
            )
            if resp.status == 200:
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    return False


def wait_for_ready(port: int, timeout: float = 30.0) -> bool:
    """等待服务就绪"""
    import urllib.request
    import urllib.error

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health/ready",
                timeout=2,
            )
            if resp.status == 200:
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    return False


def http_request(port: int, method: str, path: str, body: dict | None = None,
                 headers: dict | None = None) -> tuple[int, dict, dict]:
    """发起 HTTP 请求，返回 (status_code, response_json, response_headers)"""
    import urllib.request
    import urllib.error

    url = f"http://127.0.0.1:{port}{path}"
    data = json.dumps(body).encode("utf-8") if body else None

    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_body = resp.read()
            resp_json = json.loads(resp_body) if resp_body else {}
            resp_headers = dict(resp.headers)
            return resp.status, resp_json, resp_headers
    except urllib.error.HTTPError as e:
        resp_body = e.read()
        try:
            resp_json = json.loads(resp_body)
        except json.JSONDecodeError:
            resp_json = {"raw": resp_body.decode("utf-8", errors="replace")}
        return e.code, resp_json, dict(e.headers)
    except urllib.error.URLError as e:
        return 0, {"error": str(e)}, {}


def run_smoke_case(name: str, port: int, token: str | None,
                   question: str | None = None,
                   expected_status: int = 200,
                   expected_type: str | None = None,
                   check_security: bool = True) -> dict[str, Any]:
    """运行单个验证用例，返回结果字典"""
    t_start = time.monotonic()
    headers = {}
    if token is not None:
        headers["X-TianShu-Token"] = token

    body = {"question": question} if question else None
    status, resp_json, resp_headers = http_request(
        port, "POST", "/v1/ask", body=body, headers=headers,
    )

    duration_ms = int((time.monotonic() - t_start) * 1000)

    result = {
        "case": name,
        "status_code": status,
        "expected_status": expected_status,
        "passed": status == expected_status,
        "duration_ms": duration_ms,
        "details": [],
    }

    # 检查 response_type
    if expected_type and status == 200:
        actual_type = resp_json.get("response_type", "")
        if actual_type != expected_type:
            result["passed"] = False
            result["details"].append(f"response_type 不匹配: 期望 {expected_type}，实际 {actual_type}")

    # 安全内容检查
    if check_security and status == 200:
        resp_str = json.dumps(resp_json, ensure_ascii=False)
        for pattern in FORBIDDEN_PATTERNS:
            if isinstance(pattern, bytes):
                if pattern.decode("ascii").lower() in resp_str.lower():
                    result["passed"] = False
                    result["details"].append(f"响应包含敏感内容: {pattern.decode('ascii')}")
            elif pattern in resp_str:
                result["passed"] = False
                result["details"].append(f"响应包含敏感内容: {pattern}")

    # Contract v1.0 检查
    if status == 200 and check_security:
        if "contract_version" not in resp_json:
            result["passed"] = False
            result["details"].append("缺少 contract_version")
        if "response_type" not in resp_json:
            result["passed"] = False
            result["details"].append("缺少 response_type")

    return result


def check_audit_file(directory: str) -> dict[str, Any]:
    """检查审计文件内容"""
    audit_path = Path(directory)
    result = {"found": False, "records": 0, "events": {}, "has_sensitive": False}

    if not audit_path.is_dir():
        return result

    jsonl_files = sorted(audit_path.glob("*.jsonl"))
    if not jsonl_files:
        return result

    latest_file = jsonl_files[-1]
    result["found"] = True
    result["file"] = str(latest_file)

    # 禁止的 JSON 键名（精确匹配，不用子串匹配避免误判 question_length 等安全键）
    forbidden_keys = {
        "token", "question", "answer", "sql", "generated_sql",
        "trace", "traceback", "key", "api_key", "db_path",
        "duckdb_path", "env", "environment", "contracts",
    }

    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    result["records"] += 1
                    event = record.get("event", "unknown")
                    result["events"][event] = result["events"].get(event, 0) + 1

                    # 检查敏感内容：检查 JSON 键名（而非值子串）
                    for forbidden_key in forbidden_keys:
                        if forbidden_key in record:
                            result["has_sensitive"] = True
                            break
                except json.JSONDecodeError:
                    result["records"] += 1
    except OSError:
        pass

    return result


def check_response_security(resp_json: dict) -> list[str]:
    """深度检查响应安全，返回问题列表"""
    issues = []
    resp_str = json.dumps(resp_json, ensure_ascii=False)

    # SQL 泄露
    sql_keywords = ["SELECT", "INSERT", "DELETE", "DROP", "UPDATE"]
    for kw in sql_keywords:
        if kw in resp_str:
            issues.append(f"响应包含 SQL 关键字: {kw}")

    # Trace 泄露
    if "trace" in resp_json or "traceback" in resp_json:
        issues.append("响应包含 trace 字段")

    # API Key 泄露
    if "sk-" in resp_str:
        issues.append("响应包含疑似 API Key (sk-)")

    # 路径泄露
    if ".duckdb" in resp_str.lower():
        issues.append("响应包含 DuckDB 路径")

    return issues


def render_json_report(results: list[dict], run_id: str, port: int) -> dict:
    """生成 JSON 报告"""
    passed = all(r.get("passed", False) for r in results)
    return {
        "report": "local_api_closure",
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "port": port,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.get("passed")),
            "failed": sum(1 for r in results if not r.get("passed")),
            "overall": "PASS" if passed else "FAIL",
        },
        "cases": results,
    }


def render_markdown_report(json_report: dict) -> str:
    """生成 Markdown 报告"""
    lines = [
        "# 本地 API 安全闭环报告",
        "",
        f"**Run ID**: {json_report['run_id']}",
        f"**时间**: {json_report['timestamp']}",
        f"**端口**: {json_report['port']}",
        "",
        "## 概要",
        "",
        "| 指标 | 值 |",
        "|------|----|",
        f"| 总计 | {json_report['summary']['total']} |",
        f"| 通过 | {json_report['summary']['passed']} |",
        f"| 失败 | {json_report['summary']['failed']} |",
        f"| 结果 | **{json_report['summary']['overall']}** |",
        "",
        "## 用例详情",
        "",
    ]

    for case in json_report["cases"]:
        status_icon = "✅" if case.get("passed") else "❌"
        lines.append(f"### {status_icon} {case['case']}")
        lines.append(f"- **HTTP 状态**: {case.get('status_code')} (期望 {case.get('expected_status')})")
        lines.append(f"- **耗时**: {case.get('duration_ms')} ms")
        if case.get("details"):
            lines.append("- **问题**:")
            for d in case["details"]:
                lines.append(f"  - {d}")
        lines.append("")

    if json_report["summary"]["failed"] > 0:
        lines.append("## ⚠️ 存在失败用例，请检查上述详情")
    else:
        lines.append("## ✅ 所有用例通过")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="TianShu 本地 API 安全闭环验证")
    parser.add_argument(
        "--api-config", default="config/api_config.yml",
        help="API 配置文件路径",
    )
    parser.add_argument(
        "--tianshu-config", default="config/tianshu_target.yml",
        help="TianShu 目标配置文件路径",
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="API 绑定主机（默认 127.0.0.1）",
    )
    parser.add_argument(
        "--port", type=int, default=8765,
        help="API 端口（默认 8765，避免与开发服务器冲突）",
    )
    args = parser.parse_args()

    run_id = generate_run_id()
    print("=== TianShu 本地 API 安全闭环 ===")
    print(f"Run ID: {run_id}")
    print()

    # ── 前置条件检查 ──
    print("[1/5] 前置条件检查...")
    errors = check_preconditions(args)
    if errors:
        print("❌ 前置条件失败:")
        for e in errors:
            print(f"   - {e}")
        sys.exit(1)
    print("   ✅ 前置条件通过")
    print()

    # ── 启动服务 ──
    print(f"[2/5] 启动 API 服务 ({args.host}:{args.port})...")
    proc = start_api_server(args.api_config, args.host, args.port)
    try:
        # 等待 live
        if not wait_for_server(args.port):
            print("❌ 服务启动超时")
            proc.kill()
            proc.wait()
            sys.exit(1)
        print("   ✅ 服务 live")

        # 等待 ready
        if not wait_for_ready(args.port):
            print("❌ 服务就绪超时（请检查 TIANSHU_LOCAL_API_TOKEN 和 DuckDB）")
            proc.kill()
            proc.wait()
            sys.exit(1)
        print("   ✅ 服务 ready")
        print()

        # ── 运行验证用例 ──
        print("[3/5] 运行验证用例...")
        token = os.environ.get("TIANSHU_LOCAL_API_TOKEN", "")
        results = []

        # Case 1: 无 token → 401
        r = run_smoke_case("no_token_rejected", args.port, token=None,
                           question="2026年1月每天有多少行程？",
                           expected_status=401)
        results.append(r)
        print(f"   {'✅' if r['passed'] else '❌'} {r['case']}: {r['status_code']}")

        # Case 2: 错误 token → 401
        r = run_smoke_case("wrong_token_rejected", args.port,
                           token="wrong-token-not-valid-32chars!",
                           question="2026年1月每天有多少行程？",
                           expected_status=401)
        results.append(r)
        print(f"   {'✅' if r['passed'] else '❌'} {r['case']}: {r['status_code']}")

        # Case 3: 正确 token → answer
        r = run_smoke_case("authenticated_answer", args.port, token=token,
                           question="2026年1月每天有多少行程？",
                           expected_status=200, expected_type="answer")
        results.append(r)
        print(f"   {'✅' if r['passed'] else '❌'} {r['case']}: {r['status_code']}")

        # Case 4: clarification（模糊时间）
        r = run_smoke_case("authenticated_clarification", args.port, token=token,
                           question="最近的行程有多少？",
                           expected_status=200, expected_type="clarification")
        results.append(r)
        print(f"   {'✅' if r['passed'] else '❌'} {r['case']}: {r['status_code']}")

        # Case 5: refusal（写操作）
        r = run_smoke_case("authenticated_refusal", args.port, token=token,
                           question="删除所有行程数据",
                           expected_status=200, expected_type="refusal")
        results.append(r)
        print(f"   {'✅' if r['passed'] else '❌'} {r['case']}: {r['status_code']}")

        # Case 6: 限流验证（快速连续请求）
        rate_limit_results = []
        for i in range(35):  # 超过 30/min 限制
            headers = {"X-TianShu-Token": token} if token else {}
            status, _, resp_headers = http_request(
                args.port, "POST", "/v1/ask",
                body={"question": f"测试问题{i}"},
                headers=headers,
            )
            rate_limit_results.append(status)
            if status == 429:
                break
        has_429 = 429 in rate_limit_results
        r = {
            "case": "rate_limit_enforced",
            "status_code": 429 if has_429 else rate_limit_results[-1] if rate_limit_results else 0,
            "expected_status": 429,
            "passed": has_429,
            "duration_ms": 0,
            "details": [] if has_429 else ["未触发限流（可能需要更多请求或检查配置）"],
        }
        results.append(r)
        print(f"   {'✅' if r['passed'] else '❌'} {r['case']}: 请求 {len(rate_limit_results)} 次后触发限流")

        # Case 7: 审计文件检查
        audit_result = check_audit_file(str(AUDIT_DIR))
        r = {
            "case": "audit_file_present",
            "status_code": 0,
            "expected_status": 0,
            "passed": audit_result["found"] and audit_result["records"] > 0,
            "duration_ms": 0,
            "details": [],
        }
        if not audit_result["found"]:
            r["details"].append("审计文件未找到")
        elif audit_result["records"] == 0:
            r["details"].append("审计文件为空")
        if audit_result["has_sensitive"]:
            r["passed"] = False
            r["details"].append("审计文件包含敏感内容")
        results.append(r)
        print(f"   {'✅' if r['passed'] else '❌'} {r['case']}: {audit_result['records']} 条记录")

        # Case 8: Contract v1.0 验证
        # 从 answer 响应中验证 contract 字段
        contract_pass = True
        contract_details = []
        for case_result in results:
            if case_result.get("case") == "authenticated_answer" and case_result.get("passed"):
                # 重新请求获取完整响应
                headers = {"X-TianShu-Token": token}
                status, resp_json, _ = http_request(
                    args.port, "POST", "/v1/ask",
                    body={"question": "2026年1月每天有多少行程？"},
                    headers=headers,
                )
                if status == 200:
                    issues = check_response_security(resp_json)
                    if issues:
                        contract_pass = False
                        contract_details = issues
                break
        r = {
            "case": "public_contract_v1.0",
            "status_code": 0,
            "expected_status": 0,
            "passed": contract_pass,
            "duration_ms": 0,
            "details": contract_details,
        }
        results.append(r)
        print(f"   {'✅' if r['passed'] else '❌'} {r['case']}")

        print()

    finally:
        # ── 关闭服务 ──
        print("[4/5] 关闭 API 服务...")
        try:
            proc.terminate()
            try:
                proc.wait(timeout=10)
                print("   ✅ 服务已正常关闭")
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                print("   ⚠️ 服务被强制终止")
        except Exception as exc:
            print(f"   ⚠️ 关闭异常: {exc}")

        # 验证子进程退出
        exit_code = proc.poll()
        print(f"   子进程退出码: {exit_code}")
        print()

    # ── 生成报告 ──
    print("[5/5] 生成报告...")

    # Ensure report directory
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # JSON 报告
    json_report = render_json_report(results, run_id, args.port)
    json_path = REPORT_DIR / f"local_api_closure_{run_id}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_report, f, ensure_ascii=False, indent=2)
    print(f"   ✅ JSON 报告: {json_path}")

    # Markdown 报告
    md_report = render_markdown_report(json_report)
    md_path = REPORT_DIR / f"local_api_closure_{run_id}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"   ✅ Markdown 报告: {md_path}")

    print()
    print(f"=== 闭环验证 {'通过' if json_report['summary']['overall'] == 'PASS' else '失败'} ===")

    # 返回非 0 退出码
    if json_report["summary"]["overall"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
