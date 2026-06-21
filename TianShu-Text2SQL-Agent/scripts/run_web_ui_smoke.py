#!/usr/bin/env python
"""Phase 7 —— Web UI Smoke Runner。

一次性自动完成：
    设置临时令牌 → 启动 API 子进程 → 等待 live/ready
    → 验证 / 返回 200 → 验证静态资源
    → 验证未认证返回 401 → 验证认证 ask 成功
    → 验证 clarification / refusal 结构
    → 验证 response contract 1.0 → 验证 ChartSpec
    → 检查 Token 泄露 → 关闭服务 → 生成报告

用法：
    python scripts/run_web_ui_smoke.py \
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

from src.version import VERSION

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════

RUN_ID = ""
REPORT_DIR = PROJECT_ROOT / "harness" / "reports" / "web_ui_smoke"


def generate_run_id() -> str:
    """生成唯一运行 ID"""
    return f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}"


def log(msg: str) -> None:
    """带时间戳的日志"""
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def check_result(label: str, passed: bool, detail: str = "") -> dict:
    """生成检查结果"""
    status = "PASS" if passed else "FAIL"
    line = f"  [{status}] {label}"
    if detail and not passed:
        line += f" — {detail}"
    print(line, flush=True)
    return {"label": label, "status": status, "detail": detail if not passed else ""}


# ═══════════════════════════════════════════════════════════════
# 主逻辑
# ═══════════════════════════════════════════════════════════════


def main():
    global RUN_ID
    parser = argparse.ArgumentParser(description="TianShu Web UI Smoke Runner")
    parser.add_argument("--api-config", default="config/api_config.yml", help="API 配置文件路径")
    parser.add_argument("--tianshu-config", default="config/tianshu_target.yml", help="TianShu 目标配置文件")
    parser.add_argument("--host", default="127.0.0.1", help="API 监听地址")
    parser.add_argument("--port", type=int, default=8000, help="API 监听端口")
    args = parser.parse_args()

    RUN_ID = generate_run_id()
    report_dir = REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    start_time = time.monotonic()

    print("=" * 60)
    print("  TianShu Web UI Smoke Runner (Phase 7)")
    print("=" * 60)
    print(f"  Run ID: {RUN_ID}")
    print(f"  API Config: {args.api_config}")
    print(f"  Target: {args.host}:{args.port}")
    print()

    # ── 1. 生成临时 Token ──
    log("生成临时令牌…")
    temp_token = secrets.token_urlsafe(32)
    os.environ["TIANSHU_LOCAL_API_TOKEN"] = temp_token
    log(f"令牌已设置 (长度={len(temp_token)})")

    # ── 2. 启动 API 子进程 ──
    log("启动 API 服务…")
    api_proc = subprocess.Popen(
        [
            sys.executable, "scripts/run_api.py",
            "--config", args.api_config,
            "--host", args.host,
            "--port", str(args.port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ.copy(),
    )

    base_url = f"http://{args.host}:{args.port}"

    try:
        # ── 3. 等待 live ──
        log("等待服务上线…")
        import urllib.request
        import urllib.error

        max_wait = 20
        live_ok = False
        for i in range(max_wait):
            time.sleep(1)
            try:
                resp = urllib.request.urlopen(f"{base_url}/health/live", timeout=3)
                if resp.status == 200:
                    live_ok = True
                    break
            except Exception:
                pass
            log(f"  等待中… ({i+1}/{max_wait})")

        results.append(check_result("服务上线 (/health/live)", live_ok))
        if not live_ok:
            log("服务无法上线，终止 smoke")
            api_proc.terminate()
            return 1

        # ── 4. 等待 ready ──
        log("等待服务就绪…")
        ready_ok = False
        for i in range(max_wait):
            time.sleep(1)
            try:
                resp = urllib.request.urlopen(f"{base_url}/health/ready", timeout=3)
                data = json.loads(resp.read().decode())
                if data.get("status") == "ready":
                    ready_ok = True
                    break
            except Exception:
                pass
        results.append(check_result("服务就绪 (/health/ready)", ready_ok))
        if not ready_ok:
            log("服务未就绪")
            api_proc.terminate()
            return 1

        # ── 5. GET / 返回 200 ──
        log("检查 UI 根路由…")
        try:
            resp = urllib.request.urlopen(f"{base_url}/", timeout=5)
            html = resp.read().decode("utf-8")
            root_ok = resp.status == 200 and "TianShu" in html
            results.append(check_result("GET / 返回 200 + 含标题", root_ok))
        except Exception as e:
            results.append(check_result("GET / 返回 200 + 含标题", False, str(e)))

        # ── 6. 静态资源 ──
        log("检查静态资源…")
        asset_files = [
            "/assets/styles.css",
            "/assets/app.js",
            "/assets/api-client.js",
            "/assets/renderers.js",
            "/assets/chart-renderer.js",
        ]
        all_assets_ok = True
        for af in asset_files:
            try:
                resp = urllib.request.urlopen(f"{base_url}{af}", timeout=5)
                ok = resp.status == 200
                if not ok:
                    all_assets_ok = False
                results.append(check_result(f"静态资源 {af}", ok))
            except Exception as e:
                all_assets_ok = False
                results.append(check_result(f"静态资源 {af}", False, str(e)))
        results.append(check_result("全部静态资源 200", all_assets_ok))

        # ── 7. 页面不引用外部资源 ──
        log("检查外部依赖…")
        has_external = "http://" in html or "https://" in html
        has_cdn = "cdn." in html.lower() or "googleapis" in html.lower() or "unpkg" in html.lower()
        no_external = not has_external and not has_cdn
        results.append(check_result("页面不引用外部资源", no_external,
                                    "发现外部引用" if not no_external else ""))

        # ── 8. HTML 无内联 script/style ──
        log("检查 HTML 安全性…")
        has_inline_style = "<style>" in html.lower()
        results.append(check_result("HTML 无内联 <style>", not has_inline_style))

        # ── 9. 未认证 ask 返回 401 ──
        log("检查认证…")
        try:
            req = urllib.request.Request(
                f"{base_url}/v1/ask",
                data=json.dumps({"question": "测试"}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=10)
            results.append(check_result("未认证 ask 返回 401", False, f"实际状态码: {resp.status}"))
        except urllib.error.HTTPError as e:
            auth_401 = e.code == 401
            results.append(check_result("未认证 ask 返回 401", auth_401, f"状态码: {e.code}"))

        # ── 10. 带 Token 的 answer ──
        log("检查认证问数…")
        try:
            req = urllib.request.Request(
                f"{base_url}/v1/ask",
                data=json.dumps({"question": "2026年1月每天有多少行程？"}).encode(),
                headers={
                    "Content-Type": "application/json",
                    "X-TianShu-Token": temp_token,
                },
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=30)
            data = json.loads(resp.read().decode())
            ask_ok = resp.status == 200 and "response_type" in data
            results.append(check_result("认证问数返回 200", ask_ok))

            resp_type = data.get("response_type", "")
            results.append(check_result("response_type 有效", resp_type in ("answer", "clarification", "refusal", "error"),
                                        f"类型: {resp_type}"))

            # ── 11. Response contract 1.0 ──
            contract_ok = data.get("contract_version") == "1.0"
            results.append(check_result("contract_version = 1.0", contract_ok,
                                        f"版本: {data.get('contract_version')}"))

            # ── 12. 响应不含 SQL/trace ──
            body_str = json.dumps(data)
            no_sql = "SELECT" not in body_str
            results.append(check_result("响应不含 SQL", no_sql))
            no_trace = "trace" not in body_str.lower()
            results.append(check_result("响应不含 trace", no_trace))

            # ── 13. ChartSpec 结构 ──
            chart_spec = data.get("data", {}).get("chart_spec")
            if chart_spec:
                chart_type = chart_spec.get("chart_type", "")
                valid_types = ("line", "bar", "table", "metric_card")
                chart_ok = chart_type in valid_types
                results.append(check_result("ChartSpec chart_type 有效", chart_ok,
                                            f"类型: {chart_type}"))
            else:
                results.append(check_result("ChartSpec 存在（可为 null）", True, "为 null（非 answer 或无图表数据）"))

        except Exception as e:
            results.append(check_result("认证问数流程", False, str(e)))

        # ── 14. clarification / refusal 结构验证 ──
        log("检查响应结构…")
        struct_checks = [
            ("answer.text", "answer" in data and "text" in data.get("answer", {})),
            ("clarification.needed", "needed" in data.get("clarification", {})),
            ("refusal.refused", "refused" in data.get("refusal", {})),
            ("data.sources", "sources" in data.get("data", {})),
            ("meta.execution_mode", "execution_mode" in data.get("meta", {})),
            ("warnings", "warnings" in data),
        ]
        for label, ok in struct_checks:
            results.append(check_result(f"响应字段: {label}", ok))

        # ── 15. HTML/JS/CSS 不含 Token ──
        log("检查 Token 泄露…")
        web_dir = PROJECT_ROOT / "src" / "web"
        token_leak_ok = True
        for f in web_dir.glob("*"):
            content = f.read_text(encoding="utf-8")
            if temp_token in content:
                token_leak_ok = False
                results.append(check_result(f"Token 泄露: {f.name}", False))
                break
        if token_leak_ok:
            results.append(check_result("静态文件无 Token 泄露", True))

        # ── 16. 无 latest ──
        log("检查 latest 文件…")
        latest_files = list(report_dir.glob("*latest*"))
        no_latest = len(latest_files) == 0
        results.append(check_result("不生成 latest", no_latest,
                                    f"发现: {[f.name for f in latest_files]}" if not no_latest else ""))

    finally:
        # ── 关闭服务 ──
        log("关闭 API 服务…")
        api_proc.terminate()
        try:
            api_proc.wait(timeout=10)
            results.append(check_result("服务正常关闭", True))
        except subprocess.TimeoutExpired:
            api_proc.kill()
            results.append(check_result("服务正常关闭", False, "超时强制终止"))

    # ── 汇总 ──
    duration_s = int(time.monotonic() - start_time)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    total = len(results)

    print()
    print("=" * 60)
    print(f"  Smoke 完成: {passed}/{total} PASS, {failed} FAIL ({duration_s}s)")
    print("=" * 60)

    # ── 生成 JSON 报告 ──
    json_path = report_dir / f"web_ui_smoke_{RUN_ID}.json"
    report = {
        "run_id": RUN_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_s": duration_s,
        "passed": passed,
        "failed": failed,
        "total": total,
        "results": results,
        "version": VERSION,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log(f"JSON 报告: {json_path}")

    # ── 生成 Markdown 报告 ──
    md_path = report_dir / f"web_ui_smoke_{RUN_ID}.md"
    md_lines = [
        "# Web UI Smoke Report",
        "",
        f"**Run ID:** {RUN_ID}",
        f"**时间:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"**耗时:** {duration_s}s",
        f"**结果:** {passed}/{total} PASS, {failed} FAIL",
        "",
        "## 检查明细",
        "",
        "| # | 检查项 | 状态 | 详情 |",
        "|---|--------|------|------|",
    ]
    for i, r in enumerate(results, 1):
        status_icon = "✅" if r["status"] == "PASS" else "❌"
        detail = r.get("detail", "") or ""
        md_lines.append(f"| {i} | {r['label']} | {status_icon} {r['status']} | {detail} |")

    md_lines.append("")
    md_lines.append("## 摘要")
    md_lines.append(f"- 总计: {total}")
    md_lines.append(f"- 通过: {passed}")
    md_lines.append(f"- 失败: {failed}")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    log(f"Markdown 报告: {md_path}")

    # ── 清理环境变量 ──
    if "TIANSHU_LOCAL_API_TOKEN" in os.environ:
        del os.environ["TIANSHU_LOCAL_API_TOKEN"]

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
