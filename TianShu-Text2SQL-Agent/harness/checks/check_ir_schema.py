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
            TimeRange, Aggregation,
            # Phase 2B/3/3B/3C 新增结构
            SubIntent, ExecutionTrace, ResultSummary, MergedResult, UnifiedResponse,
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

    # ── Phase 2B+ 数据结构检查 ──

    # SubIntent（UnifiedResponse 的组成部件）
    sub_intent = SubIntent(
        metrics=["trip_count", "total_fare_amount"],
        domain=Domain.TRAFFIC,
        planning_table="gold.dws_daily_trip_summary",
        time_range=TimeRange(type=TimeRangeType.ABSOLUTE, start="2026-01-01", end="2026-03-31"),
        dimensions=["date"],
    )
    sub_dict = sub_intent.to_dict()
    checks.append({
        "name": "SubIntent 实例化 + 序列化（Phase 2B）",
        "status": "PASS" if isinstance(sub_dict, dict) and "metrics" in sub_dict else "FAIL",
        "detail": f"指标={sub_intent.metrics}, 域={sub_intent.domain.value}, 表={sub_intent.planning_table}",
    })

    # ExecutionTrace（PlanExecutor 执行追踪）
    trace = ExecutionTrace(
        plan_index=1,
        strategy="g3_direct",
        primary_table="gold.dws_daily_trip_summary",
        generated_sql="SELECT trip_date, trip_count FROM gold.dws_daily_trip_summary",
        safety_check_passed=True,
        row_count=90,
        error_message="",
        execution_status="success",
        execution_time_ms=12.5,
    )
    trace_dict = trace.to_dict()
    checks.append({
        "name": "ExecutionTrace 实例化 + 序列化（Phase 3）",
        "status": "PASS" if isinstance(trace_dict, dict) and trace_dict.get("execution_status") == "success" else "FAIL",
        "detail": f"plan_index={trace.plan_index}, safety={trace.safety_check_passed}, rows={trace.row_count}",
    })

    # UnifiedResponse（跨表多计划容器）
    unified = UnifiedResponse(
        sub_intent=sub_intent,
        plan=plan,
        result=result,
        execution_trace=trace,
    )
    unified_dict = unified.to_dict()
    checks.append({
        "name": "UnifiedResponse 实例化 + 序列化（Phase 2B）",
        "status": "PASS" if all(k in unified_dict for k in ["sub_intent", "plan", "result", "execution_trace"]) else "FAIL",
        "detail": "sub_intent/plan/result/execution_trace 四字段齐全",
    })

    # ResultSummary（结构化摘要）
    from src.ir import MergeStatus
    summary = ResultSummary(
        source_plan_index=1,
        metrics=["trip_count"],
        dimensions=["trip_date"],
        primary_table="gold.dws_daily_trip_summary",
        strategy="g3_direct",
        columns=["trip_date", "trip_count"],
        column_types=["DATE", "BIGINT"],
        row_count=90,
        sample_rows=[["2026-01-01", 300000], ["2026-01-02", 305000]],
        has_date_column=True,
        grain="daily",
        date_min="2026-01-01",
        date_max="2026-03-31",
        warnings=[],
    )
    summary_dict = summary.to_dict()
    checks.append({
        "name": "ResultSummary 实例化 + 序列化（Phase 3B）",
        "status": "PASS" if isinstance(summary_dict, dict) and summary_dict.get("grain") == "daily" else "FAIL",
        "detail": f"指标={summary.metrics}, 行={summary.row_count}, grain={summary.grain}, has_date={summary.has_date_column}",
    })

    # MergedResult（多结果 merge 容器）
    merged = MergedResult(
        merge_status=MergeStatus.MERGED,
        merge_key="date",
        columns=["trip_date", "trip_count", "crash_count"],
        rows=[["2026-01-01", 300000, 5], ["2026-01-02", 305000, 3]],
        row_count=2,
        source_plan_indexes=[1, 2],
        source_summaries=[summary],
        merge_warnings=["日期范围部分重叠"],
        reason="按日期 FULL OUTER JOIN 合并",
    )
    merged_dict = merged.to_dict()
    checks.append({
        "name": "MergedResult 实例化 + 序列化（Phase 3C）",
        "status": "PASS" if isinstance(merged_dict, dict) and merged_dict.get("merge_status") == "merged" else "FAIL",
        "detail": f"状态={merged.merge_status.value}, 键={merged.merge_key}, 行={merged.row_count}, 来源数={len(merged.source_plan_indexes)}",
    })

    # ── Phase 3D: CrossDomainDecision ──
    try:
        from src.cross_domain_policy import CrossDomainDecision

        cdd = CrossDomainDecision(
            allow_display=True,
            allow_result_merge=True,
            allow_causal_language=False,
            requires_clarification=False,
            refusal=False,
            warnings=["跨域组合 traffic+safety：禁止因果断言"],
            reason="traffic 和 safety 的相关性不等于因果关系",
        )
        cdd_dict = cdd.to_dict()
        checks.append({
            "name": "CrossDomainDecision 实例化 + 序列化（Phase 3D）",
            "status": "PASS" if isinstance(cdd_dict, dict) and cdd_dict.get("allow_causal_language") is False else "FAIL",
            "detail": f"allow_display={cdd.allow_display}, allow_causal={cdd.allow_causal_language}, refusal={cdd.refusal}, warnings={len(cdd.warnings)}",
        })
    except ImportError as e:
        checks.append({
            "name": "CrossDomainDecision 导入（Phase 3D）",
            "status": "FAIL",
            "detail": f"无法导入 CrossDomainDecision: {e}",
        })

    # ── Phase 5: ChartSpec ──
    try:
        from src.chart_spec import ChartSpec

        chart = ChartSpec(
            chart_type="line",
            title="每日行程数趋势",
            x_field="trip_date",
            y_fields=["trip_count"],
            series=[{"name": "行程数", "values": [300000, 305000]}],
            source="gold.dws_daily_trip_summary",
            warnings=[],
            data_preview=[["2026-01-01", 300000]],
        )
        chart_dict = chart.to_dict()
        json_str = chart.to_json()
        checks.append({
            "name": "ChartSpec 实例化 + 序列化（Phase 5）",
            "status": "PASS" if isinstance(chart_dict, dict) and isinstance(json_str, str) and len(json_str) > 0 else "FAIL",
            "detail": f"类型={chart.chart_type}, 标题={chart.title}, x={chart.x_field}, y={chart.y_fields}",
        })
        # ChartSpec 硬约束：不生成 HTML/JS
        json_lower = json_str.lower()
        has_html = "<html" in json_lower or "<div" in json_lower or "<script" in json_lower
        checks.append({
            "name": "ChartSpec JSON 不含 HTML/JS（Phase 5 硬约束）",
            "status": "FAIL" if has_html else "PASS",
            "detail": "输出包含 HTML/JS" if has_html else "JSON 序列化输出不含 HTML/JS",
        })
    except ImportError as e:
        checks.append({
            "name": "ChartSpec 导入（Phase 5）",
            "status": "FAIL",
            "detail": f"无法导入 ChartSpec: {e}",
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
