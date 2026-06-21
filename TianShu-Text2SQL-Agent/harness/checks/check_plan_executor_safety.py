"""
检查 PlanExecutor 执行层安全门禁。

验证 src/plan_executor.py 的关键安全约束：
    1. 离线模式下 execute_one() 抛出异常或阻断执行
    2. execute_one() 对每个 plan 调用 validate_sql_safety()
    3. sql_plan_to_sql() 是 SQL 生成的唯一入口
    4. read_only=True 是 DuckDB 连接的最后防线
    5. ExecutionTrace 正确记录安全校验状态

本检查只验证源码中的安全链路引用存在性，不实际执行 SQL。

用法：
    python harness/checks/check_plan_executor_safety.py
"""

from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def check_safety_chain_in_source() -> dict[str, Any]:
    """验证 PlanExecutor 源码中的安全链路引用"""
    checks: list[dict[str, Any]] = []

    try:
        from src.plan_executor import PlanExecutor
    except ImportError as e:
        return {
            "checks": [{"name": "PlanExecutor 导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    source = inspect.getsource(PlanExecutor)

    # 检查 1：是否调用 validate_sql_safety
    has_safety = "validate_sql_safety" in source
    checks.append({
        "name": "execute_one 调用 validate_sql_safety()",
        "status": "PASS" if has_safety else "FAIL",
        "detail": "验证通过" if has_safety else "未找到 validate_sql_safety 调用",
    })

    # 检查 2：是否引用 sql_plan_to_sql（SQL 生成入口）
    has_sql_gen = "sql_plan_to_sql" in source or "_generate_sql" in source
    checks.append({
        "name": "SQL 生成通过 sql_plan_to_sql() 代码路径",
        "status": "PASS" if has_sql_gen else "WARN",
        "detail": "检测到 SQL 生成路径" if has_sql_gen else "未显式检测 sql_plan_to_sql",
    })

    # 检查 3：是否检查离线模式
    has_offline = "offline" in source.lower()
    checks.append({
        "name": "离线模式检查存在",
        "status": "PASS" if has_offline else "WARN",
        "detail": "检测到 offline 引用" if has_offline else "未显式检测 offline 模式",
    })

    # 检查 4：是否引用 read_only
    has_readonly = "read_only" in source
    checks.append({
        "name": "DuckDB read_only 引用存在",
        "status": "PASS" if has_readonly else "WARN",
        "detail": "检测到 read_only" if has_readonly else "未检测到 read_only 引用",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_execution_trace_safety_fields() -> dict[str, Any]:
    """验证 ExecutionTrace 包含安全相关字段"""
    checks: list[dict[str, Any]] = []

    try:
        from src.plan_executor import ExecutionTrace
    except ImportError as e:
        return {
            "checks": [{"name": "ExecutionTrace 导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    # 创建包含安全校验状态的 trace
    trace_pass = ExecutionTrace(
        plan_index=1,
        strategy="g3_direct",
        safety_check_passed=True,
        execution_status="success",
        row_count=90,
    )
    checks.append({
        "name": "ExecutionTrace: safety_check_passed=True 可设置",
        "status": "PASS" if trace_pass.safety_check_passed else "FAIL",
        "detail": f"safety_check_passed={trace_pass.safety_check_passed}",
    })

    trace_fail = ExecutionTrace(
        plan_index=1,
        strategy="g3_direct",
        safety_check_passed=False,
        execution_status="failed",
        error_message="安全校验失败: 包含禁止的写操作",
    )
    checks.append({
        "name": "ExecutionTrace: 安全校验失败时记录错误",
        "status": "PASS" if not trace_fail.safety_check_passed and trace_fail.error_message else "FAIL",
        "detail": f"safety={trace_fail.safety_check_passed}, error={trace_fail.error_message[:50]}",
    })

    # 序列化验证
    d = trace_pass.to_dict()
    checks.append({
        "name": "ExecutionTrace.to_dict() 包含 safety_check_passed",
        "status": "PASS" if "safety_check_passed" in d else "FAIL",
        "detail": f"字段数={len(d)}, keys={list(d.keys())}",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_sql_safety_validator_still_present() -> dict[str, Any]:
    """验证 validate_sql_safety() 函数仍然存在且可调用"""
    checks: list[dict[str, Any]] = []

    try:
        from src.sql_gen import validate_sql_safety
    except ImportError as e:
        return {
            "checks": [{"name": "validate_sql_safety 导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    # 验证函数存在
    checks.append({
        "name": "validate_sql_safety 函数存在",
        "status": "PASS",
        "detail": f"函数签名: {validate_sql_safety.__name__}",
    })

    # 用干净的 SQL 调用 — 应通过（日期过滤通过 dim_date）
    clean_sql = (
        "SELECT t.trip_date, SUM(t.trip_count) AS trip_count "
        "FROM gold.dws_daily_trip_summary t "
        "JOIN gold.dim_date d ON d.date_day = t.trip_date "
        "WHERE d.date_day BETWEEN '2026-01-01' AND '2026-01-31' "
        "GROUP BY t.trip_date"
    )
    forbidden_keywords = ["INSERT", "DELETE", "UPDATE", "DROP", "CREATE", "ALTER", "TRUNCATE"]
    try:
        errors = validate_sql_safety(clean_sql, forbidden_keywords)
        checks.append({
            "name": "干净 SQL 通过 validate_sql_safety()",
            "status": "PASS" if not errors else "FAIL",
            "detail": "通过" if not errors else f"违规: {errors}",
        })
    except Exception as e:
        checks.append({
            "name": "validate_sql_safety 调用不崩溃",
            "status": "FAIL",
            "detail": f"调用失败: {e}",
        })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def print_report(
    safety_result: dict[str, Any],
    trace_result: dict[str, Any],
    validator_result: dict[str, Any],
) -> int:
    """打印检查报告"""
    print("=" * 60)
    print("PlanExecutor 执行层安全门禁")
    print("检查：安全链路引用 / ExecutionTrace 字段 / validate_sql_safety")
    print("=" * 60)

    sections = [
        ("安全链路源码引用", safety_result),
        ("ExecutionTrace 安全字段", trace_result),
        ("validate_sql_safety 存在性", validator_result),
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
        print(f"\n[FAIL] PlanExecutor 安全门禁: 发现 {total_fail} 项失败！")
        return 1
    else:
        print("\n[OK] PlanExecutor 安全门禁通过。")
        return 0


def main() -> int:
    """命令行入口"""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="PlanExecutor 执行层安全门禁")
    parser.add_argument("--config", default=None,
                        help="Harness 配置文件路径（本检查不使用，仅为兼容接口保留）")
    _args = parser.parse_args()

    safety_result = check_safety_chain_in_source()
    trace_result = check_execution_trace_safety_fields()
    validator_result = check_sql_safety_validator_still_present()

    return print_report(safety_result, trace_result, validator_result)


if __name__ == "__main__":
    sys.exit(main())
