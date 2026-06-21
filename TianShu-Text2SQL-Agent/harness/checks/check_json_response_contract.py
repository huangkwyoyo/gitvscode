"""
检查公开响应契约中 JSON 序列化的严格性。

验证：
    1. tests/test_response_contract.py 中不存在 json.dumps(..., default=str) 掩码
    2. build_public_response() 输出可被 json.dumps 原生序列化（不依赖 default=str）
    3. build_public_response() 能正确处理 datetime.date/datetime.datetime/tuple 类型

用法：
    python harness/checks/check_json_response_contract.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def check_no_default_str_in_tests() -> dict[str, Any]:
    """
    扫描 response contract 测试文件，禁止 json.dumps(..., default=str) 掩码。

    限定范围：tests/test_response_contract.py
    不全局扫描（避免误伤日志/调试代码中的 default=str）。
    """
    checks: list[dict[str, Any]] = []
    root = Path(__file__).resolve().parent.parent.parent

    target_files = [
        root / "tests" / "test_response_contract.py",
    ]

    for file_path in target_files:
        if not file_path.exists():
            checks.append({
                "name": f"文件存在: {file_path.name}",
                "status": "FAIL",
                "detail": f"文件不存在: {file_path}",
            })
            continue

        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # 检测模式：json.dumps(..., default=str) 在同一行中
        violations: list[dict[str, Any]] = []
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            # 跳过注释行
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            # 检测 json.dumps 调用中是否包含 default=str
            # 匹配 json.dumps(... default=str ...) 模式
            if "json.dumps" in stripped and "default=str" in stripped:
                violations.append({"line": i, "content": stripped[:120]})

        if violations:
            detail_lines = [f"第 {v['line']} 行: {v['content']}" for v in violations]
            checks.append({
                "name": f"{file_path.name}: 禁止 json.dumps(default=str) 掩码",
                "status": "FAIL",
                "detail": f"发现 {len(violations)} 处违规:\n    " + "\n    ".join(detail_lines),
            })
        else:
            checks.append({
                "name": f"{file_path.name}: 禁止 json.dumps(default=str) 掩码",
                "status": "PASS",
                "detail": "未发现 default=str 掩码",
            })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_build_public_response_json_native() -> dict[str, Any]:
    """
    验证 build_public_response() 输出可被 json.dumps 原生序列化。

    使用真实的 datetime.date/datetime.datetime/tuple 构造 AgentResponse，
    确保 build_public_response() → json.dumps(ensure_ascii=False) 不抛 TypeError。
    """
    checks: list[dict[str, Any]] = []

    try:
        from src.ir import AgentResponse, SQLResult, ResultSummary
        from src.response_contract import build_public_response
    except ImportError as e:
        return {
            "checks": [{
                "name": "导入 build_public_response",
                "status": "FAIL",
                "detail": f"导入失败: {e}",
            }],
            "pass_count": 0,
            "fail_count": 1,
        }

    tests_passed = 0
    tests_failed = 0

    # ── 测试 1: datetime.date 在 rows 中 ──
    try:
        resp = AgentResponse(
            question="测试 date 序列化",
            chinese_answer="测试回答",
        )
        resp.result = SQLResult(
            sql="SELECT d FROM test",
            columns=["d"],
            column_types=["DATE"],
            rows=[(date(2026, 1, 15), 100)],
            row_count=1,
            source_table="test",
        )
        resp.result_summaries = [
            ResultSummary(
                source_plan_index=1,
                primary_table="test",
                columns=["d", "v"],
                column_types=["DATE", "BIGINT"],
                row_count=1,
                sample_rows=[[date(2026, 1, 15), 100]],
                has_date_column=True,
                grain="daily",
                date_min="2026-01-15",
                date_max="2026-01-15",
            ).to_dict()
        ]
        public = build_public_response(resp)
        json.dumps(public, ensure_ascii=False)  # 不带 default=str
        # 验证 date 转为字符串
        assert public["data"]["summaries"][0]["sample_rows"][0][0] == "2026-01-15"
        tests_passed += 1
    except Exception as e:
        tests_failed += 1
        checks.append({
            "name": "datetime.date 序列化",
            "status": "FAIL",
            "detail": str(e),
        })

    # ── 测试 2: datetime.datetime 在 rows 中 ──
    try:
        resp = AgentResponse(
            question="测试 datetime 序列化",
            chinese_answer="测试回答",
        )
        resp.result = SQLResult(
            sql="SELECT ts FROM test",
            columns=["ts"],
            column_types=["TIMESTAMP"],
            rows=[(datetime(2026, 1, 15, 12, 30, 0),)],
            row_count=1,
            source_table="test",
        )
        resp.result_summaries = [
            ResultSummary(
                source_plan_index=1,
                primary_table="test",
                columns=["ts"],
                column_types=["TIMESTAMP"],
                row_count=1,
                sample_rows=[[datetime(2026, 1, 15, 12, 30, 0)]],
                has_date_column=False,
                grain="unknown",
            ).to_dict()
        ]
        public = build_public_response(resp)
        json.dumps(public, ensure_ascii=False)  # 不带 default=str
        assert "T" in public["data"]["summaries"][0]["sample_rows"][0][0]
        tests_passed += 1
    except Exception as e:
        tests_failed += 1
        checks.append({
            "name": "datetime.datetime 序列化",
            "status": "FAIL",
            "detail": str(e),
        })

    # ── 测试 3: tuple 在 rows 中 ──
    try:
        resp = AgentResponse(
            question="测试 tuple 序列化",
            chinese_answer="测试回答",
        )
        resp.result = SQLResult(
            sql="SELECT city, cnt FROM test",
            columns=["city", "cnt"],
            column_types=["VARCHAR", "BIGINT"],
            rows=[("北京", 100)],
            row_count=1,
            source_table="test",
        )
        resp.result_summaries = [
            ResultSummary(
                source_plan_index=1,
                primary_table="test",
                columns=["city", "cnt"],
                column_types=["VARCHAR", "BIGINT"],
                row_count=1,
                sample_rows=[("北京", 100)],  # tuple
                has_date_column=False,
                grain="unknown",
            ).to_dict()
        ]
        public = build_public_response(resp)
        json.dumps(public, ensure_ascii=False)  # 不带 default=str
        # tuple 应转为 list
        sample = public["data"]["summaries"][0]["sample_rows"][0]
        assert isinstance(sample, list)
        tests_passed += 1
    except Exception as e:
        tests_failed += 1
        checks.append({
            "name": "tuple 序列化",
            "status": "FAIL",
            "detail": str(e),
        })

    # ── 测试 4: clarification/refusal/error 类型也可序列化 ──
    for resp_type in ["clarification", "refusal", "error"]:
        try:
            if resp_type == "clarification":
                resp = AgentResponse(
                    question="test",
                    clarification_needed=True,
                    clarification_message="请明确时间。",
                )
            elif resp_type == "refusal":
                resp = AgentResponse(
                    question="test",
                    refusal=True,
                    refusal_reason="不能执行。",
                )
            else:
                resp = AgentResponse(question="test")
                resp.result = SQLResult(sql="", error="连接失败")

            public = build_public_response(resp)
            json.dumps(public, ensure_ascii=False)  # 不带 default=str
            assert public["response_type"] == resp_type
            tests_passed += 1
        except Exception as e:
            tests_failed += 1
            checks.append({
                "name": f"{resp_type} 类型序列化",
                "status": "FAIL",
                "detail": str(e),
            })

    # ── 汇总 ──
    if tests_passed > 0 and tests_failed == 0:
        checks.append({
            "name": "build_public_response() JSON-native 验证",
            "status": "PASS",
            "detail": f"全部 {tests_passed} 项通过（date/datetime/tuple/clarification/refusal/error）",
        })
    elif tests_failed > 0:
        checks.append({
            "name": "build_public_response() JSON-native 验证",
            "status": "FAIL",
            "detail": f"通过 {tests_passed} 项，失败 {tests_failed} 项",
        })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def print_report(
    default_str_result: dict[str, Any],
    json_native_result: dict[str, Any],
) -> int:
    """打印检查报告"""
    print("=" * 60)
    print("公开响应 JSON 契约序列化严格性检查")
    print("检查：禁止 default=str 掩码 / build_public_response() JSON-native")
    print("=" * 60)

    sections = [
        ("default=str 掩码检测", default_str_result),
        ("build_public_response() JSON-native 验证", json_native_result),
    ]

    total_fail = 0
    total_pass = 0

    for title, result in sections:
        print(f"\n── {title} ──")
        for c in result["checks"]:
            tag = c["status"]
            print(f"  [{tag}] {c['name']}")
            if c.get("detail"):
                print(f"         {c['detail']}")
        total_fail += result.get("fail_count", 0)
        total_pass += result.get("pass_count", 0)

    print(f"\n  检查完成 — 通过: {total_pass}, 失败: {total_fail}")

    if total_fail > 0:
        print(f"\n[FAIL] JSON 响应契约序列化严格性检查: 发现 {total_fail} 项失败！")
        return 1
    else:
        print("\n[OK] JSON 响应契约序列化严格性检查通过。")
        return 0


def main() -> int:
    """命令行入口"""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="公开响应 JSON 契约序列化严格性检查")
    parser.add_argument("--config", default=None,
                        help="Harness 配置文件路径（本检查不使用，仅为兼容接口保留）")
    _args = parser.parse_args()

    default_str_result = check_no_default_str_in_tests()
    json_native_result = check_build_public_response_json_native()

    return print_report(default_str_result, json_native_result)


if __name__ == "__main__":
    sys.exit(main())
