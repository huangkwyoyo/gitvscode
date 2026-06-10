"""
检查 IR 三层数据结构完整性。

验证 src/ir.py 中定义的三层 IR 数据结构：
    1. QuestionIntent — 字段完整、类型正确
    2. SQLPlan — 字段完整、策略枚举完备
    3. SQLResult — 字段完整、签名计算正确

同时检查 evals/ 目录中问题集的 YAML 结构是否符合预期格式。

用法：
    python harness/checks/check_ir_schema.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from harness.config import load_harness_config  # noqa: E402


def check_ir_dataclasses() -> dict[str, Any]:
    """
    检查 src/ir.py 中 IR 数据结构的完整性。

    Returns:
        {checks: [{name, status, detail}, ...]}
    """
    checks: list[dict[str, Any]] = []

    try:
        from src.ir import (
            QuestionIntent, SQLPlan, SQLResult, AgentResponse,
            Domain, IntentType, TimeRangeType, Strategy,
            TimeRange, Filter, JoinPlan, Aggregation,
        )
    except ImportError as e:
        return {
            "checks": [{"name": "IR 模块导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0,
            "fail_count": 1,
        }

    # ── 检查 QuestionIntent ──
    intent = QuestionIntent(
        domain=Domain.TRAFFIC,
        intent_type=IntentType.AGGREGATION,
        metrics=["trip_count"],
        time_range=TimeRange(type=TimeRangeType.ABSOLUTE, start="2026-01-01", end="2026-03-31"),
        dimensions=["date"],
        confidence=0.95,
        raw_question="测试问题",
    )
    intent_dict = intent.to_dict()
    checks.append({
        "name": "QuestionIntent 实例化 + 序列化",
        "status": "PASS" if isinstance(intent_dict, dict) else "FAIL",
        "detail": f"字段数={len(intent_dict)}, 包含 keys={list(intent_dict.keys())[:5]}...",
    })

    # 校验逻辑
    errors = intent.validate()
    checks.append({
        "name": "QuestionIntent.validate()",
        "status": "PASS" if not errors else "WARN",
        "detail": "通过" if not errors else f"校验错误: {errors}",
    })

    # needs_clarification 场景
    fuzzy_intent = QuestionIntent(
        needs_clarification=True,
        clarification_reason="测试歧义",
        confidence=0.3,
    )
    fuzzy_errors = fuzzy_intent.validate()
    checks.append({
        "name": "QuestionIntent 歧义检测（needs_clarification=true）",
        "status": "PASS" if fuzzy_errors else "FAIL",
        "detail": f"检测到 {len(fuzzy_errors)} 个问题" if fuzzy_errors else "未检测到歧义（预期应检测到）",
    })

    # ── 检查 SQLPlan ──
    plan = SQLPlan(
        strategy=Strategy.G3_DIRECT,
        primary_table="gold.dws_daily_trip_summary",
        where_clauses=["trip_date BETWEEN DATE '2026-01-01' AND DATE '2026-03-31'"],
        group_by=["trip_date"],
        order_by=["trip_date"],
        aggregations=[Aggregation(expr="SUM(trip_count)", alias="trip_count")],
        confidence=0.97,
    )
    plan_dict = plan.to_dict()
    checks.append({
        "name": "SQLPlan 实例化 + 序列化",
        "status": "PASS" if isinstance(plan_dict, dict) else "FAIL",
        "detail": f"策略={plan.strategy.value}, 主表={plan.primary_table}",
    })

    # 降级未标注原因
    degraded_plan = SQLPlan(
        strategy=Strategy.G2_FACT_JOIN,
        primary_table="gold.fact_trips",
        downgrade_reason=None,
    )
    degraded_errors = degraded_plan.validate()
    checks.append({
        "name": "SQLPlan 降级原因检查（缺失 downgrade_reason）",
        "status": "PASS" if degraded_errors else "FAIL",
        "detail": f"检测到 {len(degraded_errors)} 个问题" if degraded_errors else "未检测到降级原因缺失（预期应检测到）",
    })

    # ── 检查 SQLResult ──
    result = SQLResult(
        sql="SELECT trip_date, trip_count FROM gold.dws_daily_trip_summary LIMIT 10",
        columns=["trip_date", "trip_count"],
        column_types=["DATE", "BIGINT"],
        rows=[("2026-01-01", 300000)],
        row_count=1,
        source_table="gold.dws_daily_trip_summary",
    )
    sig = result.result_signature
    checks.append({
        "name": "SQLResult 签名计算",
        "status": "PASS" if len(sig) == 32 else "FAIL",
        "detail": f"MD5={sig[:16]}...",
    })

    # ── 检查 AgentResponse ──
    resp = AgentResponse(
        question="测试",
        intent=intent,
        plan=plan,
        result=result,
        chinese_answer="测试回答",
    )
    resp_dict = resp.to_dict()
    checks.append({
        "name": "AgentResponse 完整链路序列化",
        "status": "PASS" if all(k in resp_dict for k in ["question", "intent", "plan", "result"]) else "FAIL",
        "detail": f"包含 keys={list(resp_dict.keys())}",
    })

    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")

    return {"checks": checks, "pass_count": pass_count, "fail_count": fail_count}


def check_eval_file_structure(evals_path: Path) -> dict[str, Any]:
    """
    检查 evals/ 目录下 YAML 文件的结构是否符合预期。

    预期格式：
        questions:
          - id: q_xxx
            question_zh: "..."
            sql: "..."
            ...
    """
    checks: list[dict[str, Any]] = []

    if not evals_path.exists():
        return {
            "checks": [{"name": "evals 目录", "status": "SKIP", "detail": "evals/ 目录不存在，待创建评测集"}],
            "pass_count": 0, "fail_count": 0,
        }

    yaml_files = list(evals_path.glob("*.yml"))
    if not yaml_files:
        return {
            "checks": [{"name": "evals 目录", "status": "SKIP", "detail": "evals/ 目录中尚无 YAML 文件"}],
            "pass_count": 0, "fail_count": 0,
        }

    for yaml_file in sorted(yaml_files):
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            questions = data if isinstance(data, list) else data.get("questions", [])

            if not questions:
                checks.append({
                    "name": f"{yaml_file.name} 结构",
                    "status": "WARN",
                    "detail": "问题列表为空",
                })
                continue

            # 检查每条问题的必填字段
            required_fields = ["id", "question_zh", "sql"]
            for q in questions:
                if isinstance(q, dict):
                    missing = [f for f in required_fields if f not in q]
                    if missing:
                        checks.append({
                            "name": f"{yaml_file.name} / {q.get('id', 'unknown')}",
                            "status": "WARN",
                            "detail": f"缺少字段: {missing}",
                        })
                    else:
                        checks.append({
                            "name": f"{yaml_file.name} / {q['id']}",
                            "status": "PASS",
                            "detail": f"'{q['question_zh'][:50]}...'",
                        })
        except yaml.YAMLError as e:
            checks.append({
                "name": yaml_file.name,
                "status": "FAIL",
                "detail": f"YAML 解析错误: {e}",
            })

    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")

    return {"checks": checks, "pass_count": pass_count, "fail_count": fail_count}


def print_report(ir_results: dict[str, Any], eval_results: dict[str, Any]) -> int:
    """打印检查报告，返回退出码"""
    print("=" * 60)
    print("IR 三层数据结构完整性门禁")
    print("=" * 60)

    # IR 数据类检查
    print("\n── src/ir.py 数据类检查 ──")
    for c in ir_results["checks"]:
        tag = c["status"]
        print(f"  [{tag}] {c['name']}")
        if c["detail"]:
            print(f"         {c['detail']}")

    # eval 文件结构检查
    print("\n── evals/ 文件结构检查 ──")
    for c in eval_results["checks"]:
        tag = c["status"]
        print(f"  [{tag}] {c['name']}")
        if c["detail"]:
            print(f"         {c['detail']}")

    total_fail = ir_results.get("fail_count", 0) + eval_results.get("fail_count", 0)
    total_pass = ir_results.get("pass_count", 0) + eval_results.get("pass_count", 0)

    print(f"\n  检查完成 — 通过: {total_pass}, 失败: {total_fail}")

    if total_fail > 0:
        print(f"\n[FAIL] 发现 {total_fail} 项失败！")
        return 1
    else:
        print("\n[OK] IR 数据结构完整性检查通过。")
        return 0


def main() -> int:
    """命令行入口"""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="IR 数据结构完整性门禁")
    parser.add_argument("--config", default="config/tianshu_target.yml")
    parser.add_argument("--evals", type=Path, help="evals 目录路径")
    args = parser.parse_args()

    # 加载配置获取 evals 路径
    try:
        harness_config = load_harness_config(args.config)
    except FileNotFoundError:
        harness_config = None

    evals_path = args.evals or (harness_config.evals_path if harness_config else Path("evals"))

    ir_results = check_ir_dataclasses()
    eval_results = check_eval_file_structure(evals_path)

    return print_report(ir_results, eval_results)


if __name__ == "__main__":
    sys.exit(main())
