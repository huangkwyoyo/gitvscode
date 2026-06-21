"""
检查 LLM 结果融合安全门禁。

验证 src/result_fusion.py 的 4 层后校验和 fallback 机制：
    1. SQL 关键词检测 —— 含 SELECT/INSERT/DROP 等 40+ 关键词的输出应被拒绝
    2. 因果语言检测 —— 含"导致""造成""因为…所以…"的输出应被拒绝
    3. 编造指标检测 —— 原始数据中不存在的指标名应被检测
    4. validate_fusion_output 集成 —— 4 层校验统合正常工作
    5. 模板 fallback —— LLM 异常时回退到模板融合

本检查不调用 LLM，仅验证后校验函数和 fallback 函数的输入/输出行为。

用法：
    python harness/checks/check_result_fusion_safety.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def check_sql_keyword_detection() -> dict[str, Any]:
    """验证 SQL 关键词检测功能（_check_sql_keywords）"""
    checks: list[dict[str, Any]] = []

    try:
        from src.result_fusion import _check_sql_keywords
    except ImportError as e:
        return {
            "checks": [{"name": "SQL 关键词检测导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    # 应被拒绝的输入（含 SQL 关键字）
    sql_positive_cases = [
        ("SELECT * FROM gold.dws_daily_trip_summary", "SELECT"),
        ("可以使用 INSERT INTO 插入数据", "INSERT"),
        ("建议先 DROP TABLE 再重建", "DROP"),
        ("执行 DELETE FROM fact_trips", "DELETE"),
        ("用 UPDATE 修改记录", "UPDATE"),
    ]
    for text, expected_kw in sql_positive_cases:
        found = _check_sql_keywords(text)
        checks.append({
            "name": f"SQL 检测: 应检出 '{expected_kw}'",
            "status": "PASS" if found else "FAIL",
            "detail": f"检测到: {found}" if found else f"未检测到 {expected_kw}",
        })

    # 应通过的输入（不含 SQL 关键字）
    sql_negative_cases = [
        "本月行程量约 300 万次，较上月增长 5%",
        "罚单总数为 1,234 条，主要来自咪表区域",
        "三个数据源（行程汇总表、违章汇总表）均显示增长趋势",
    ]
    for text in sql_negative_cases:
        found = _check_sql_keywords(text)
        checks.append({
            "name": f"SQL 检测: 正常文本应通过 ({text[:30]}...)",
            "status": "FAIL" if found else "PASS",
            "detail": f"误报: {found}" if found else "未误报",
        })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_causal_language_detection() -> dict[str, Any]:
    """验证因果语言检测功能（_check_causal_language）"""
    checks: list[dict[str, Any]] = []

    try:
        from src.result_fusion import _check_causal_language
    except ImportError as e:
        return {
            "checks": [{"name": "因果语言检测导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    # 应被拒绝：含因果措辞
    causal_positive = [
        "行程量下降导致事故数减少",
        "天气变差造成了出行需求下降",
        "因为罚单增加所以收入上升",
        "由于违章量增加，因此事故率上升",
    ]
    for text in causal_positive:
        found = _check_causal_language(text)
        checks.append({
            "name": f"因果检测: 应检出因果措辞 ({text[:25]}...)",
            "status": "PASS" if found else "FAIL",
            "detail": f"检测到: {found}" if found else "未检测到",
        })

    # 应通过：无因果措辞
    causal_negative = [
        "本月行程量 300 万次，事故数 50 起 —— 两组数据来自不同表",
        "罚单金额是 standard_fine_amount 的总和，不代表实际收入",
        "行程量和事故数均呈增长趋势，但二者可能受共同因素影响",
    ]
    for text in causal_negative:
        found = _check_causal_language(text)
        checks.append({
            "name": f"因果检测: 无因果文本应通过 ({text[:30]}...)",
            "status": "FAIL" if found else "PASS",
            "detail": f"误报: {found}" if found else "未误报",
        })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_fabricated_metric_detection() -> dict[str, Any]:
    """验证编造指标检测功能（_check_fabricated_metrics）"""
    checks: list[dict[str, Any]] = []

    try:
        from src.result_fusion import _check_fabricated_metrics
        from src.ir import ResultSummary
    except ImportError as e:
        return {
            "checks": [{"name": "编造指标检测导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    # 构建合法的 summary（含注册指标名和列名）
    summary = ResultSummary(
        source_plan_index=1,
        metrics=["trip_count", "total_fare_amount"],
        columns=["trip_date", "trip_count", "total_fare_amount"],
        primary_table="gold.dws_daily_trip_summary",
        row_count=90,
    )

    # 应被检测到编造
    fabricated_cases = [
        "本次查询到 average_speed 为 45 km/h",
        "revenue_growth_rate 达到了 12%",
    ]
    for text in fabricated_cases:
        found = _check_fabricated_metrics(text, [summary])
        checks.append({
            "name": f"编造检测: 应检出编造指标 ({text[:35]}...)",
            "status": "PASS" if found else "FAIL",
            "detail": f"检测到: {found}" if found else "未检测到",
        })

    # 应通过：全是合法指标和列名
    ok_cases = [
        "trip_count 在 1 月最高达到 110 万次",
        "total_fare_amount 合计为 500 万元",
    ]
    for text in ok_cases:
        found = _check_fabricated_metrics(text, [summary])
        checks.append({
            "name": f"编造检测: 注册指标应通过 ({text[:30]}...)",
            "status": "FAIL" if found else "PASS",
            "detail": f"误报: {found}" if found else "未误报",
        })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_validate_fusion_output_integration() -> dict[str, Any]:
    """验证 validate_fusion_output 集成所有 4 层校验"""
    checks: list[dict[str, Any]] = []

    try:
        from src.result_fusion import validate_fusion_output
        from src.ir import ResultSummary
    except ImportError as e:
        return {
            "checks": [{"name": "validate_fusion_output 导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    summary = ResultSummary(
        source_plan_index=1,
        metrics=["trip_count"],
        columns=["trip_date", "trip_count"],
        primary_table="gold.dws_daily_trip_summary",
        row_count=90,
        has_date_column=True,
        grain="daily",
        date_min="2026-01-01",
        date_max="2026-03-31",
    )

    # 测试 1：干净的输出应通过
    clean_text = (
        "根据行程汇总表（gold.dws_daily_trip_summary）的数据，"
        "2026年1月到3月期间，每日行程数在 76 万到 110 万之间波动。"
    )
    violations = validate_fusion_output(clean_text, [summary])
    checks.append({
        "name": "集成校验: 干净文本应通过",
        "status": "PASS" if not violations else "FAIL",
        "detail": "通过" if not violations else f"违规: {violations}",
    })

    # 测试 2：含 SQL 关键字应被拒绝
    sql_text = "SELECT * FROM gold.dws_daily_trip_summary 显示行程量为 300 万"
    violations_sql = validate_fusion_output(sql_text, [summary])
    checks.append({
        "name": "集成校验: 含 SQL 关键字应拒绝",
        "status": "PASS" if violations_sql else "FAIL",
        "detail": f"检测到违规: {violations_sql}" if violations_sql else "未检测到",
    })

    # 测试 3：含因果措辞应被拒绝
    causal_text = "行程量下降导致了收入减少 —— 来自行程汇总表"
    violations_causal = validate_fusion_output(causal_text, [summary])
    checks.append({
        "name": "集成校验: 含因果措辞应拒绝",
        "status": "PASS" if violations_causal else "FAIL",
        "detail": f"检测到违规: {violations_causal}" if violations_causal else "未检测到",
    })

    # 测试 4：不含来源提及应被检测
    no_source_text = "本月行程量约 300 万次，较上月增长 5%"
    violations_no_source = validate_fusion_output(no_source_text, [summary])
    checks.append({
        "name": "集成校验: 无来源提及应检测",
        "status": "PASS" if violations_no_source else "FAIL",
        "detail": f"检测到违规: {violations_no_source}" if violations_no_source else "未检测到",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_fallback_to_template() -> dict[str, Any]:
    """验证模板 fallback 机制（fallback_to_template 可导入且不崩溃）"""
    checks: list[dict[str, Any]] = []

    try:
        from src.result_fusion import fallback_to_template
        from src.ir import UnifiedResponse, ResultSummary, SQLPlan, SQLResult, SubIntent, ExecutionTrace
        from src.ir import Domain, Strategy
    except ImportError as e:
        return {
            "checks": [{"name": "模板 fallback 导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    # 构建最小可用的 UnifiedResponse
    _summary = ResultSummary(
        source_plan_index=1,
        metrics=["trip_count"],
        primary_table="gold.dws_daily_trip_summary",
        columns=["trip_date", "trip_count"],
        column_types=["DATE", "BIGINT"],
        row_count=90,
        sample_rows=[["2026-01-01", 300000]],
        has_date_column=True,
        grain="daily",
    )

    plan = SQLPlan(
        strategy=Strategy.G3_DIRECT,
        primary_table="gold.dws_daily_trip_summary",
    )

    result = SQLResult(
        sql="SELECT trip_date, trip_count FROM gold.dws_daily_trip_summary",
        columns=["trip_date", "trip_count"],
        column_types=["DATE", "BIGINT"],
        rows=[("2026-01-01", 300000)],
        row_count=1,
        source_table="gold.dws_daily_trip_summary",
    )

    trace = ExecutionTrace(
        plan_index=1,
        strategy="g3_direct",
        primary_table="gold.dws_daily_trip_summary",
        safety_check_passed=True,
        row_count=90,
        execution_status="success",
    )

    unified = UnifiedResponse(
        sub_intent=SubIntent(metrics=["trip_count"], domain=Domain.TRAFFIC, planning_table="gold.dws_daily_trip_summary"),
        plan=plan,
        result=result,
        execution_trace=trace,
    )

    # 测试 1：fallback_to_template 正常返回文本
    output = fallback_to_template("每天有多少行程", [unified])
    checks.append({
        "name": "Fallback: 正常输入返回有效文本",
        "status": "PASS" if isinstance(output, str) and len(output) > 20 else "FAIL",
        "detail": f"返回 {len(output)} 字符: {output[:80]}...",
    })

    # 测试 2：空列表不崩溃
    output_empty = fallback_to_template("测试", [])
    checks.append({
        "name": "Fallback: 空列表不崩溃",
        "status": "PASS" if isinstance(output_empty, str) else "FAIL",
        "detail": f"返回 {len(output_empty)} 字符" if output_empty else "返回空字符串",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def print_report(
    sql_result: dict[str, Any],
    causal_result: dict[str, Any],
    fabricated_result: dict[str, Any],
    integration_result: dict[str, Any],
    fallback_result: dict[str, Any],
) -> int:
    """打印检查报告"""
    print("=" * 60)
    print("LLM 结果融合安全门禁")
    print("检查：SQL 禁止 / 因果禁止 / 编造指标 / 集成校验 / 模板 fallback")
    print("=" * 60)

    sections = [
        ("SQL 关键词检测 (_check_sql_keywords)", sql_result),
        ("因果语言检测 (_check_causal_language)", causal_result),
        ("编造指标检测 (_check_fabricated_metrics)", fabricated_result),
        ("集成校验 (validate_fusion_output)", integration_result),
        ("模板 Fallback (fallback_to_template)", fallback_result),
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
        print(f"\n[FAIL] LLM 融合安全门禁: 发现 {total_fail} 项失败！")
        return 1
    else:
        print("\n[OK] LLM 融合安全门禁通过。")
        return 0


def main() -> int:
    """命令行入口"""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="LLM 结果融合安全门禁")
    parser.add_argument("--config", default=None,
                        help="Harness 配置文件路径（本检查不使用，仅为兼容接口保留）")
    _args = parser.parse_args()

    sql_result = check_sql_keyword_detection()
    causal_result = check_causal_language_detection()
    fabricated_result = check_fabricated_metric_detection()
    integration_result = check_validate_fusion_output_integration()
    fallback_result = check_fallback_to_template()

    return print_report(sql_result, causal_result, fabricated_result, integration_result, fallback_result)


if __name__ == "__main__":
    sys.exit(main())
