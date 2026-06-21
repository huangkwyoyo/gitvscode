"""
检查 JOIN 白名单不存在硬编码绕过。

验证：
    1. resolver.py 的 build_context() 不包含 join_whitelist.extend()
    2. resolver.py 不包含硬编码的 G3→dim_date 表名字符串
    3. llm_pipeline.py 不包含模块级 JOIN_WHITELIST 常量
    4. llm_pipeline.py 不包含模块级 AVAILABLE_TABLES 常量
    5. 运行时 JOIN 白名单与权威契约完全一致
    6. 契约缺失时 safety_policy_loader 正确 fail-closed

用法：
    python harness/checks/check_join_whitelist_no_hardcode.py
"""

from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


# ═══════════════════════════════════════════════════════════════
# 检查 1: resolver.py 不含硬编码 JOIN 追加
# ═══════════════════════════════════════════════════════════════


def check_resolver_no_join_extend() -> dict[str, Any]:
    """验证 resolver.py 不包含 join_whitelist.extend() 调用"""
    from src.resolver import TianShuResolver

    src = inspect.getsource(TianShuResolver.build_context)
    violations: list[str] = []

    if "join_whitelist.extend" in src:
        violations.append("resolver.py 包含 join_whitelist.extend() 硬编码 JOIN 追加")

    # 三个 G3→dim_date 硬编码表名不应出现在 build_context 源码中
    hardcoded_g3_tables = [
        '"gold.dws_daily_trip_summary"',
        '"gold.dws_daily_parking_summary"',
        '"gold.dws_daily_crash_summary"',
    ]
    for table_name in hardcoded_g3_tables:
        if table_name in src:
            violations.append(f"resolver.py build_context() 包含硬编码表名: {table_name}")

    return {
        "name": "resolver.py 不含硬编码 JOIN 白名单",
        "status": "FAIL" if violations else "PASS",
        "detail": "; ".join(violations) if violations else "build_context() 无 join_whitelist.extend 和硬编码表名",
    }


# ═══════════════════════════════════════════════════════════════
# 检查 2: llm_pipeline.py 不含模块级硬编码常量
# ═══════════════════════════════════════════════════════════════


def check_llm_pipeline_no_module_constants() -> list[dict[str, Any]]:
    """验证 llm_pipeline.py 不含 AVAILABLE_TABLES 和 JOIN_WHITELIST 模块常量"""
    from src import llm_pipeline

    checks: list[dict[str, Any]] = []

    has_available_tables = hasattr(llm_pipeline, "AVAILABLE_TABLES")
    checks.append({
        "name": "llm_pipeline.py 不含模块级 AVAILABLE_TABLES",
        "status": "FAIL" if has_available_tables else "PASS",
        "detail": "存在模块级 AVAILABLE_TABLES 硬编码" if has_available_tables else "无硬编码常量",
    })

    has_join_whitelist = hasattr(llm_pipeline, "JOIN_WHITELIST")
    checks.append({
        "name": "llm_pipeline.py 不含模块级 JOIN_WHITELIST",
        "status": "FAIL" if has_join_whitelist else "PASS",
        "detail": "存在模块级 JOIN_WHITELIST 硬编码" if has_join_whitelist else "无硬编码常量",
    })

    return checks


# ═══════════════════════════════════════════════════════════════
# 检查 3: 运行时 JOIN 白名单与契约一致
# ═══════════════════════════════════════════════════════════════


def check_runtime_whitelist_matches_contract() -> dict[str, Any]:
    """验证 resolver 运行时 JOIN 白名单与契约完全一致（无额外条目）"""
    from src.resolver import TianShuResolver
    from src.safety_policy_loader import load_join_whitelist

    # 加载权威契约白名单
    contract_wl = load_join_whitelist(strict=True)
    contract_allowed = set(contract_wl.allowed)

    # 加载 resolver 的契约并解析 JOIN 白名单（模拟 build_context 中的逻辑）
    resolver = TianShuResolver()
    resolver.load_config()
    resolver.load_contracts()

    sql_safety = resolver._contracts.get("sql_safety_policy", {})
    resolver_pairs: list[tuple[str, str]] = []
    for rule in sql_safety.get("table_reference_rules", []):
        if rule.get("rule") == "join_whitelist":
            for join_str in rule.get("allowed_joins", []):
                parts = join_str.split("↔")
                if len(parts) == 2:
                    left = parts[0].strip().split("(")[0].strip()
                    right = parts[1].strip().split("(")[0].strip()
                    resolver_pairs.append((left, right))
                    resolver_pairs.append((right, left))

    resolver_set = set(resolver_pairs)

    extra = resolver_set - contract_allowed
    missing = contract_allowed - resolver_set

    violations: list[str] = []
    if extra:
        violations.append(f"Resolver 白名单包含契约之外的条目: {extra}")
    if missing:
        violations.append(f"Resolver 白名单缺少契约中的条目: {missing}")

    return {
        "name": "运行时 JOIN 白名单与权威契约一致",
        "status": "FAIL" if violations else "PASS",
        "detail": "; ".join(violations) if violations else (
            f"白名单完全一致（{len(resolver_set)} 条双向 JOIN，{len(contract_wl.entries)} 条唯一 JOIN）"
        ),
    }


# ═══════════════════════════════════════════════════════════════
# 检查 4: 契约缺失时 fail-closed
# ═══════════════════════════════════════════════════════════════


def check_contract_missing_fail_closed() -> dict[str, Any]:
    """验证契约缺失时 load_join_whitelist 抛出异常（fail-closed）"""
    from src.safety_policy_loader import load_join_whitelist

    checks: list[dict[str, Any]] = []

    # 测试 strict=True → 契约缺失抛异常
    try:
        wl = load_join_whitelist(contracts_path="/nonexistent/path/contracts", strict=True)
        checks.append({
            "name": "strict=True 契约缺失 → 抛出 FileNotFoundError",
            "status": "FAIL",
            "detail": f"未抛出异常，返回了 {len(wl.allowed)} 条 JOIN",
        })
    except FileNotFoundError:
        checks.append({
            "name": "strict=True 契约缺失 → 抛出 FileNotFoundError",
            "status": "PASS",
            "detail": "正确抛出 FileNotFoundError（fail-closed）",
        })

    # 测试 strict=False → 返回空名单
    try:
        wl = load_join_whitelist(contracts_path="/nonexistent/path/contracts", strict=False)
        if wl.contract_missing and len(wl.allowed) == 0:
            checks.append({
                "name": "strict=False 契约缺失 → 返回空名单",
                "status": "PASS",
                "detail": f"返回空名单（contract_missing={wl.contract_missing}）",
            })
        else:
            checks.append({
                "name": "strict=False 契约缺失 → 返回空名单",
                "status": "FAIL",
                "detail": f"contract_missing={wl.contract_missing}, allowed={len(wl.allowed)}",
            })
    except Exception as e:
        checks.append({
            "name": "strict=False 契约缺失 → 返回空名单",
            "status": "FAIL",
            "detail": f"意外抛出异常: {e}",
        })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


# ═══════════════════════════════════════════════════════════════
# 检查 5: safety_policy_loader 格式非法 → fail-closed
# ═══════════════════════════════════════════════════════════════


def check_malformed_format_fail_closed(tmpdir: Path | None = None) -> list[dict[str, Any]]:
    """验证格式非法的 allowed_joins 在 strict 模式下抛出异常"""
    import tempfile
    from src.safety_policy_loader import load_join_whitelist

    checks: list[dict[str, Any]] = []
    test_cases = [
        ("空字符串", [""]),
        ("无分隔符", ["gold.table_a gold.table_b"]),
        ("非字符串", [12345]),
        ("缺失左表", [" ↔ gold.dim_date"]),
    ]

    for label, joins in test_cases:
        tmpdir = Path(tempfile.mkdtemp(prefix="harness_join_test_"))
        contracts_dir = tmpdir / "contracts"
        contracts_dir.mkdir(parents=True, exist_ok=True)
        policy = {
            "table_reference_rules": [{
                "rule": "join_whitelist",
                "allowed_joins": joins,
            }],
        }
        with open(contracts_dir / "sql_safety_policy.yml", "w", encoding="utf-8") as f:
            yaml.dump(policy, f)

        try:
            wl = load_join_whitelist(contracts_path=contracts_dir, strict=True)
            checks.append({
                "name": f"格式非法（{label}）→ 抛出 ValueError",
                "status": "FAIL",
                "detail": f"未抛出异常，返回了 {len(wl.allowed)} 条 JOIN",
            })
        except (ValueError, FileNotFoundError):
            checks.append({
                "name": f"格式非法（{label}）→ 抛出 ValueError",
                "status": "PASS",
                "detail": "正确抛出异常（fail-closed）",
            })

    return checks


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════


def run_all_checks() -> dict[str, Any]:
    """运行所有 JOIN 白名单安全检查"""
    all_checks: list[dict[str, Any]] = []

    # 检查 1: resolver.py 不含硬编码
    all_checks.append(check_resolver_no_join_extend())

    # 检查 2: llm_pipeline.py 不含模块常量
    all_checks.extend(check_llm_pipeline_no_module_constants())

    # 检查 3: 运行时白名单与契约一致
    all_checks.append(check_runtime_whitelist_matches_contract())

    # 检查 4: 契约缺失 fail-closed
    result_4 = check_contract_missing_fail_closed()
    all_checks.extend(result_4["checks"])

    # 检查 5: 格式非法 fail-closed
    all_checks.extend(check_malformed_format_fail_closed())

    pass_count = sum(1 for c in all_checks if c["status"] == "PASS")
    fail_count = sum(1 for c in all_checks if c["status"] == "FAIL")

    return {
        "title": "JOIN 白名单无硬编码绕过",
        "checks": all_checks,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "total": pass_count + fail_count,
    }


def main():
    parser = argparse.ArgumentParser(description="检查 JOIN 白名单是否存在硬编码绕过")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    args = parser.parse_args()

    result = run_all_checks()

    if args.json:
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"  {result['title']}")
        print(f"{'='*60}")
        for c in result["checks"]:
            icon = "PASS" if c["status"] == "PASS" else "FAIL"
            print(f"  [{icon}] {c['name']}")
            if c["status"] == "FAIL":
                print(f"       → {c['detail']}")
        print(f"\n  通过: {result['pass_count']}/{result['total']}, "
              f"失败: {result['fail_count']}/{result['total']}")

    return 0 if result["fail_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
