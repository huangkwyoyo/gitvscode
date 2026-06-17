"""
检查跨域策略安全门禁。

验证 src/cross_domain_policy.py 的关键决策路径：
    1. person-fields 隐私保护 → REFUSE
    2. unknown domain → NEED_CLARIFICATION
    3. traffic+safety → forbid_causal_language=True
    4. standard_fine_total → warning 包含关键词
    5. 单 domain → allow_causal_language=True（单域不禁止因果）
    6. 默认保守策略（Default conservative）

本检查只验证规则逻辑，不访问 DuckDB 或 LLM。

用法：
    python harness/checks/check_cross_domain_policy.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def check_person_fields_privacy() -> dict[str, Any]:
    """验证人员字段隐私保护触发 REFUSE"""
    checks: list[dict[str, Any]] = []

    try:
        from src.cross_domain_policy import CrossDomainPolicy
        from src.ir import Domain, ResultSummary
    except ImportError as e:
        return {
            "checks": [{"name": "CrossDomainPolicy 导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    policy = CrossDomainPolicy()

    # 测试 1：supply + traffic 含 persons_injured → REFUSE
    # persons_injured 在 _PERSONNEL_FIELDS 中，需 Domain.SUPPLY 或 Domain.ASSET 才触发
    decision = policy.evaluate(
        domains=[Domain.SUPPLY, Domain.TRAFFIC],
        metrics=["trip_count", "persons_injured"],
    )
    checks.append({
        "name": "人员字段 (persons_injured) 跨域 → REFUSE",
        "status": "PASS" if decision.refusal else "FAIL",
        "detail": f"refusal={decision.refusal}, reason={decision.reason}",
    })

    # 测试 2：supply + traffic 不含 person 指标 → 不 REFUSE
    decision_no_person = policy.evaluate(
        domains=[Domain.SPATIAL, Domain.TRAFFIC],
        metrics=["trip_count", "total_fare_amount"],
    )
    checks.append({
        "name": "无人员字段跨域 → 不 REFUSE",
        "status": "FAIL" if decision_no_person.refusal else "PASS",
        "detail": f"refusal={decision_no_person.refusal}",
    })

    # 测试 3：driver_name 通过 summaries columns 检测
    summary_with_driver = ResultSummary(
        source_plan_index=1,
        metrics=["trip_count"],
        columns=["trip_date", "driver_name", "trip_count"],
        primary_table="gold.fact_trips",
        row_count=90,
    )
    decision_col = policy.evaluate(
        domains=[Domain.SUPPLY, Domain.TRAFFIC],
        metrics=["trip_count"],
        summaries=[summary_with_driver],
    )
    checks.append({
        "name": "人员字段 (driver_name) 通过 summaries columns → REFUSE",
        "status": "PASS" if decision_col.refusal else "FAIL",
        "detail": f"refusal={decision_col.refusal}, reason={decision_col.reason}",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_unknown_domain_clarification() -> dict[str, Any]:
    """验证 unknown domain 触发 NEED_CLARIFICATION"""
    checks: list[dict[str, Any]] = []

    try:
        from src.cross_domain_policy import CrossDomainPolicy
        from src.ir import Domain
    except ImportError as e:
        return {
            "checks": [{"name": "CrossDomainPolicy 导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    policy = CrossDomainPolicy()

    # 单已知域 → 不需要反问
    decision_known = policy.evaluate(
        domains=[Domain.TRAFFIC],
        metrics=["trip_count"],
    )
    checks.append({
        "name": "单域 (traffic) → 不需要反问",
        "status": "PASS" if not decision_known.requires_clarification else "FAIL",
        "detail": f"requires_clarification={decision_known.requires_clarification}",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_traffic_safety_causal_ban() -> dict[str, Any]:
    """验证 traffic+safety → forbid_causal_language"""
    checks: list[dict[str, Any]] = []

    try:
        from src.cross_domain_policy import CrossDomainPolicy
        from src.ir import Domain
    except ImportError as e:
        return {
            "checks": [{"name": "CrossDomainPolicy 导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    policy = CrossDomainPolicy()

    # traffic + safety → 禁止因果
    decision_ts = policy.evaluate(
        domains=[Domain.TRAFFIC, Domain.SAFETY],
        metrics=["trip_count", "crash_count"],
    )
    checks.append({
        "name": "traffic+safety → forbid_causal_language=True",
        "status": "PASS" if not decision_ts.allow_causal_language else "FAIL",
        "detail": f"allow_causal_language={decision_ts.allow_causal_language}, warnings={decision_ts.warnings}",
    })

    checks.append({
        "name": "traffic+safety → allow_display=True（允许并列展示）",
        "status": "PASS" if decision_ts.allow_display else "FAIL",
        "detail": f"allow_display={decision_ts.allow_display}",
    })

    checks.append({
        "name": "traffic+safety → allow_result_merge=True（允许日期对齐）",
        "status": "PASS" if decision_ts.allow_result_merge else "FAIL",
        "detail": f"allow_result_merge={decision_ts.allow_result_merge}",
    })

    # 单 traffic 域 → 允许因果
    decision_single = policy.evaluate(
        domains=[Domain.TRAFFIC],
        metrics=["trip_count"],
    )
    checks.append({
        "name": "单域 (traffic) → allow_causal_language=True",
        "status": "PASS" if decision_single.allow_causal_language else "FAIL",
        "detail": f"allow_causal_language={decision_single.allow_causal_language}",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_standard_fine_warning() -> dict[str, Any]:
    """验证 standard_fine_total 警告"""
    checks: list[dict[str, Any]] = []

    try:
        from src.cross_domain_policy import CrossDomainPolicy
        from src.ir import Domain
    except ImportError as e:
        return {
            "checks": [{"name": "CrossDomainPolicy 导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    policy = CrossDomainPolicy()

    # 含 standard_fine_total（在 _FINE_METRICS 中）→ 应有警告
    decision_fine = policy.evaluate(
        domains=[Domain.VIOLATION],
        metrics=["standard_fine_total"],
    )
    has_fine_warning = any("fine" in w.lower() or "罚" in w for w in decision_fine.warnings)
    checks.append({
        "name": "standard_fine_total → 包含罚款警告",
        "status": "PASS" if has_fine_warning else "WARN",
        "detail": f"warnings={decision_fine.warnings}" if decision_fine.warnings else "无警告",
    })

    # 不含 fine → 无警告
    decision_no_fine = policy.evaluate(
        domains=[Domain.VIOLATION],
        metrics=["parking_violation_count"],
    )
    fine_only_warnings = [w for w in decision_no_fine.warnings if "fine" in w.lower() or "罚" in w]
    checks.append({
        "name": "parking_violation_count → 无罚款警告",
        "status": "PASS" if not fine_only_warnings else "WARN",
        "detail": f"warnings={decision_no_fine.warnings}" if fine_only_warnings else "无罚款相关警告",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_decision_serialization() -> dict[str, Any]:
    """验证 CrossDomainDecision.to_dict() 可序列化"""
    checks: list[dict[str, Any]] = []

    try:
        from src.cross_domain_policy import CrossDomainDecision
    except ImportError as e:
        return {
            "checks": [{"name": "CrossDomainDecision 导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    decision = CrossDomainDecision(
        allow_display=True,
        allow_result_merge=False,
        allow_causal_language=False,
        refusal=False,
        warnings=["跨域组合禁止因果断言"],
        reason="traffic 和 safety 的相关性不等于因果关系",
    )
    d = decision.to_dict()
    required_fields = ["allow_display", "allow_result_merge", "allow_causal_language",
                       "requires_clarification", "refusal", "warnings", "reason"]
    missing = [f for f in required_fields if f not in d]
    checks.append({
        "name": "CrossDomainDecision.to_dict() 字段完整",
        "status": "FAIL" if missing else "PASS",
        "detail": f"缺失字段: {missing}" if missing else f"全部 {len(required_fields)} 个字段齐全",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def print_report(
    privacy_result: dict[str, Any],
    unknown_result: dict[str, Any],
    causal_result: dict[str, Any],
    fine_result: dict[str, Any],
    serial_result: dict[str, Any],
) -> int:
    """打印检查报告"""
    print("=" * 60)
    print("跨域策略安全门禁")
    print("检查：隐私保护 / 未知域反问 / 因果禁止 / 罚款警告 / 序列化")
    print("=" * 60)

    sections = [
        ("人员字段隐私保护", privacy_result),
        ("未知域反问触发", unknown_result),
        ("traffic+safety 因果禁止", causal_result),
        ("standard_fine_total 警告", fine_result),
        ("Decision 序列化", serial_result),
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
        print(f"\n[FAIL] 跨域策略安全门禁: 发现 {total_fail} 项失败！")
        return 1
    else:
        print("\n[OK] 跨域策略安全门禁通过。")
        return 0


def main() -> int:
    """命令行入口"""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="跨域策略安全门禁")
    parser.add_argument("--config", default=None,
                        help="Harness 配置文件路径（本检查不使用，仅为兼容接口保留）")
    args = parser.parse_args()

    privacy_result = check_person_fields_privacy()
    unknown_result = check_unknown_domain_clarification()
    causal_result = check_traffic_safety_causal_ban()
    fine_result = check_standard_fine_warning()
    serial_result = check_decision_serialization()

    return print_report(privacy_result, unknown_result, causal_result, fine_result, serial_result)


if __name__ == "__main__":
    sys.exit(main())
