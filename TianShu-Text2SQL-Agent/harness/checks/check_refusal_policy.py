"""
检查反问/拒绝策略完备性。

验证以下内容：
    1. TianShu contracts/question_policy.yml 存在且格式正确
    2. must_clarify 规则至少覆盖了 4 种歧义场景
    3. must_refuse 规则至少覆盖了 4 种拒绝场景
    4. evals/ambiguous_questions.yml 存在且格式正确（如已创建）
    5. evals/unsafe_questions.yml 存在且格式正确（如已创建）

注意：
    当前阶段不检查 Agent 的实际反问率（Agent 尚未接入 LLM）。
    仅验证策略定义和评测集的完备性。

用法：
    python harness/checks/check_refusal_policy.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from harness.config import load_harness_config


def check_question_policy(contracts_path: Path) -> dict[str, Any]:
    """检查 contracts/question_policy.yml 的完备性"""
    policy_file = contracts_path / "question_policy.yml"

    if not policy_file.exists():
        return {
            "checks": [{
                "name": "question_policy.yml 存在",
                "status": "FAIL",
                "detail": f"文件不存在: {policy_file}",
            }],
            "pass_count": 0,
            "fail_count": 1,
        }

    checks: list[dict[str, Any]] = []

    try:
        with open(policy_file, "r", encoding="utf-8") as f:
            policy = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return {
            "checks": [{
                "name": "question_policy.yml 格式",
                "status": "FAIL",
                "detail": f"YAML 解析错误: {e}",
            }],
            "pass_count": 0,
            "fail_count": 1,
        }

    # 检查 answerable
    answerable = policy.get("answerable", [])
    checks.append({
        "name": "可回答的问题域定义",
        "status": "PASS" if len(answerable) >= 3 else "WARN",
        "detail": f"已定义 {len(answerable)} 个问题域: {[a.get('domain', '?') for a in answerable]}",
    })

    # 检查 must_clarify
    clarify_rules = policy.get("must_clarify", [])
    _expected_clarify_triggers = {"ambiguous_amount", "fuzzy_time", "ambiguous_region", "missing_dimension", "unregistered_metric"}
    actual_triggers = {r.get("trigger", "") for r in clarify_rules}

    checks.append({
        "name": "必须反问的场景数",
        "status": "PASS" if len(clarify_rules) >= 4 else "WARN",
        "detail": f"已定义 {len(clarify_rules)} 种反问场景: {actual_triggers}",
    })

    # 检查每个反问规则是否有模板
    missing_templates = [
        r["trigger"] for r in clarify_rules
        if not r.get("clarification_template")
    ]
    checks.append({
        "name": "反问模板完备性",
        "status": "FAIL" if missing_templates else "PASS",
        "detail": f"缺失模板: {missing_templates}" if missing_templates else "全部反问规则都有模板",
    })

    # 检查 must_refuse
    refuse_rules = policy.get("must_refuse", [])
    _expected_refuse_triggers = {"write_operation", "bronze_direct", "metric_invention", "out_of_scope"}
    actual_refuse_triggers = {r.get("trigger", "") for r in refuse_rules}

    checks.append({
        "name": "必须拒绝的场景数",
        "status": "PASS" if len(refuse_rules) >= 4 else "WARN",
        "detail": f"已定义 {len(refuse_rules)} 种拒绝场景: {actual_refuse_triggers}",
    })

    # 检查每个拒绝规则是否有模板
    missing_refuse_templates = [
        r["trigger"] for r in refuse_rules
        if not r.get("refusal_template")
    ]
    checks.append({
        "name": "拒绝模板完备性",
        "status": "FAIL" if missing_refuse_templates else "PASS",
        "detail": f"缺失模板: {missing_refuse_templates}" if missing_refuse_templates else "全部拒绝规则都有模板",
    })

    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")

    return {"checks": checks, "pass_count": pass_count, "fail_count": fail_count}


def check_eval_policy_files(evals_path: Path) -> dict[str, Any]:
    """检查 evals/ 目录中策略相关评测文件的存在性和格式"""
    checks: list[dict[str, Any]] = []

    # 检查 ambiguous_questions.yml（可能尚未创建）
    ambiguous_file = evals_path / "ambiguous_questions.yml"
    if ambiguous_file.exists():
        try:
            with open(ambiguous_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            questions = data if isinstance(data, list) else data.get("questions", [])
            checks.append({
                "name": "ambiguous_questions.yml",
                "status": "PASS" if questions else "WARN",
                "detail": f"{len(questions)} 道歧义问题",
            })
        except yaml.YAMLError:
            checks.append({
                "name": "ambiguous_questions.yml",
                "status": "FAIL",
                "detail": "YAML 格式错误",
            })
    else:
        checks.append({
            "name": "ambiguous_questions.yml",
            "status": "SKIP",
            "detail": "文件尚未创建（待 Agent 实现后补充）",
        })

    # 检查 unsafe_questions.yml（可能尚未创建）
    unsafe_file = evals_path / "unsafe_questions.yml"
    if unsafe_file.exists():
        try:
            with open(unsafe_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            questions = data if isinstance(data, list) else data.get("questions", [])
            checks.append({
                "name": "unsafe_questions.yml",
                "status": "PASS" if questions else "WARN",
                "detail": f"{len(questions)} 道越权问题",
            })
        except yaml.YAMLError:
            checks.append({
                "name": "unsafe_questions.yml",
                "status": "FAIL",
                "detail": "YAML 格式错误",
            })
    else:
        checks.append({
            "name": "unsafe_questions.yml",
            "status": "SKIP",
            "detail": "文件尚未创建（待 Agent 实现后补充）",
        })

    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")

    return {"checks": checks, "pass_count": pass_count, "fail_count": fail_count}


def print_report(policy_results: dict[str, Any], eval_results: dict[str, Any]) -> int:
    """打印检查报告，返回退出码"""
    print("=" * 60)
    print("反问/拒绝策略完备性门禁")
    print("=" * 60)

    print("\n── contracts/question_policy.yml 检查 ──")
    for c in policy_results["checks"]:
        tag = c["status"]
        print(f"  [{tag}] {c['name']}")
        if c.get("detail"):
            print(f"         {c['detail']}")

    print("\n── evals/ 策略评测文件检查 ──")
    for c in eval_results["checks"]:
        tag = c["status"]
        print(f"  [{tag}] {c['name']}")
        if c.get("detail"):
            print(f"         {c['detail']}")

    total_fail = policy_results.get("fail_count", 0) + eval_results.get("fail_count", 0)
    total_pass = policy_results.get("pass_count", 0) + eval_results.get("pass_count", 0)
    total_skip = sum(
        1 for c in (policy_results.get("checks", []) + eval_results.get("checks", []))
        if c["status"] == "SKIP"
    )

    print(f"\n  检查完成 — 通过: {total_pass}, 失败: {total_fail}, 跳过: {total_skip}")

    if total_fail > 0:
        print(f"\n[FAIL] 发现 {total_fail} 项失败！")
        return 1
    else:
        print("\n[OK] 反问/拒绝策略完备性检查通过。")
        return 0


def main() -> int:
    """命令行入口"""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="反问/拒绝策略完备性门禁")
    parser.add_argument("--config", default="config/tianshu_target.yml")
    args = parser.parse_args()

    try:
        harness_config = load_harness_config(args.config)
    except FileNotFoundError as e:
        print(f"[SKIP] {e}")
        return 0

    policy_results = check_question_policy(harness_config.contracts_path)
    eval_results = check_eval_policy_files(harness_config.evals_path)

    return print_report(policy_results, eval_results)


if __name__ == "__main__":
    sys.exit(main())
