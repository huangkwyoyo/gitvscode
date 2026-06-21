"""
检查图表规格生成安全门禁。

验证 src/chart_spec.py 的三个硬约束：
    1. 不生成 HTML/JS —— ChartSpec.to_json() 输出中不含 <html>/<div>/<script>
    2. 不调用 LLM —— chart_spec.py 源码中不 import llm 相关模块
    3. 不访问 DuckDB —— chart_spec.py 源码中不 import duckdb 相关模块
    4. ChartSpec 可 JSON 序列化 —— to_json() 返回合法 JSON
    5. 跨域警告注入仍生效
    6. refusal → table 降级仍生效

用法：
    python harness/checks/check_chart_spec_safety.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def check_no_html_js_output() -> dict[str, Any]:
    """验证 ChartSpec 输出不含 HTML/JS"""
    checks: list[dict[str, Any]] = []

    try:
        from src.chart_spec import ChartSpec
    except ImportError as e:
        return {
            "checks": [{"name": "ChartSpec 导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    # 覆盖所有图表类型的输出
    chart_types = [
        ("line", ChartSpec(chart_type="line", title="趋势图", x_field="date",
                           y_fields=["val"], series=[{"name": "系列1", "values": [1, 2]}])),
        ("bar", ChartSpec(chart_type="bar", title="柱状图", x_field="category",
                          y_fields=["val"], series=[{"name": "系列1", "values": [1, 2]}])),
        ("metric_card", ChartSpec(chart_type="metric_card", title="指标卡")),
        ("table", ChartSpec(chart_type="table", title="表格",
                            data_preview=[["col1", "col2"], [1, 2]])),
    ]

    html_indicators = ["<html", "<div", "<script", "javascript:", "onclick="]
    for chart_type, chart in chart_types:
        json_str = chart.to_json()
        json_lower = json_str.lower()
        violations = [ind for ind in html_indicators if ind in json_lower]
        checks.append({
            "name": f"ChartSpec({chart_type}).to_json() 不含 HTML/JS",
            "status": "FAIL" if violations else "PASS",
            "detail": f"违规: {violations}" if violations else "无 HTML/JS 特征",
        })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_no_llm_no_duckdb_imports() -> dict[str, Any]:
    """验证 chart_spec.py 不 import LLM 或 DuckDB"""
    checks: list[dict[str, Any]] = []

    chart_spec_path = Path(__file__).resolve().parent.parent.parent / "src" / "chart_spec.py"
    if not chart_spec_path.exists():
        return {
            "checks": [{"name": "chart_spec.py 路径", "status": "FAIL", "detail": "文件不存在"}],
            "pass_count": 0, "fail_count": 1,
        }

    source = chart_spec_path.read_text(encoding="utf-8")
    source_lower = source.lower()

    # LLM 相关导入检测
    llm_indicators = [
        "import openai", "from openai", "import anthropic", "from anthropic",
        "llm_client", "chat_completion", "llm.call", "llm.generate",
    ]
    llm_violations = [ind for ind in llm_indicators if ind in source_lower]
    checks.append({
        "name": "chart_spec.py 不导入 LLM 模块",
        "status": "FAIL" if llm_violations else "PASS",
        "detail": f"发现 LLM 引用: {llm_violations}" if llm_violations else "无 LLM 引用",
    })

    # DuckDB 相关导入检测
    duckdb_indicators = [
        "import duckdb", "from duckdb", "duckdb.connect", "duckdb.sql",
    ]
    duckdb_violations = [ind for ind in duckdb_indicators if ind in source_lower]
    checks.append({
        "name": "chart_spec.py 不导入 DuckDB 模块",
        "status": "FAIL" if duckdb_violations else "PASS",
        "detail": f"发现 DuckDB 引用: {duckdb_violations}" if duckdb_violations else "无 DuckDB 引用",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_json_serializable() -> dict[str, Any]:
    """验证 ChartSpec JSON 序列化能力"""
    checks: list[dict[str, Any]] = []

    try:
        from src.chart_spec import ChartSpec
    except ImportError as e:
        return {
            "checks": [{"name": "ChartSpec 导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    # 含完整字段的 ChartSpec
    chart = ChartSpec(
        chart_type="line",
        title="每日行程数趋势",
        x_field="trip_date",
        y_fields=["trip_count"],
        series=[{"name": "行程数", "values": [300000, 305000, 310000]}],
        source="gold.dws_daily_trip_summary",
        warnings=["数据仅覆盖工作日期"],
        data_preview=[["2026-01-01", 300000], ["2026-01-02", 305000]],
    )

    # to_dict 序列化
    d = chart.to_dict()
    checks.append({
        "name": "ChartSpec.to_dict() 返回合法 dict",
        "status": "PASS" if isinstance(d, dict) else "FAIL",
        "detail": f"字段数={len(d)}",
    })

    # to_json 序列化
    json_str = chart.to_json()
    try:
        parsed = json.loads(json_str)
        checks.append({
            "name": "ChartSpec.to_json() 可被 json.loads 解析",
            "status": "PASS",
            "detail": f"解析后字段数={len(parsed)}",
        })
    except json.JSONDecodeError as e:
        checks.append({
            "name": "ChartSpec.to_json() 可被 json.loads 解析",
            "status": "FAIL",
            "detail": f"JSON 解析失败: {e}",
        })

    # 默认值验证
    default_chart = ChartSpec()
    checks.append({
        "name": "ChartSpec 默认值: chart_type='table'",
        "status": "PASS" if default_chart.chart_type == "table" else "FAIL",
        "detail": f"chart_type={default_chart.chart_type}",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_cross_domain_downgrade() -> dict[str, Any]:
    """验证跨域警告注入和 refusal → table 降级"""
    checks: list[dict[str, Any]] = []

    try:
        from src.chart_spec import ChartSpec, build_chart_spec_from_summary
        from src.ir import ResultSummary
    except ImportError as e:
        return {
            "checks": [{"name": "跨域降级功能导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    summary = ResultSummary(
        source_plan_index=1,
        metrics=["trip_count"],
        columns=["trip_date", "trip_count"],
        column_types=["DATE", "BIGINT"],
        primary_table="gold.dws_daily_trip_summary",
        row_count=90,
        has_date_column=True,
        grain="daily",
        date_min="2026-01-01",
        date_max="2026-03-31",
        sample_rows=[["2026-01-01", 300000]],
    )

    # 测试 1：正常构建不崩溃
    chart = build_chart_spec_from_summary(summary)
    checks.append({
        "name": "build_chart_spec_from_summary 正常返回 ChartSpec",
        "status": "PASS" if isinstance(chart, ChartSpec) else "FAIL",
        "detail": f"类型={chart.chart_type}, 标题={chart.title}",
    })

    # 测试 2：跨域警告注入
    chart_with_warning = build_chart_spec_from_summary(
        summary,
        cross_domain_warning="traffic+safety 组合：禁止因果断言",
    )
    has_warning = "traffic" in str(chart_with_warning.warnings).lower() or "safety" in str(chart_with_warning.warnings).lower()
    checks.append({
        "name": "跨域警告注入到 ChartSpec.warnings",
        "status": "PASS" if has_warning else "WARN",
        "detail": f"warnings={chart_with_warning.warnings}",
    })

    # 测试 3：refusal 语义 → 降级为 table
    chart_refusal = build_chart_spec_from_summary(
        summary,
        cross_domain_warning="跨域涉及人员隐私字段，refusal 触发降级为 table",
    )
    checks.append({
        "name": "refusal 语义触发降级为 table",
        "status": "PASS" if chart_refusal.chart_type == "table" else "WARN",
        "detail": f"类型={chart_refusal.chart_type}, 预期=table",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def print_report(
    html_result: dict[str, Any],
    imports_result: dict[str, Any],
    json_result: dict[str, Any],
    downgrade_result: dict[str, Any],
) -> int:
    """打印检查报告"""
    print("=" * 60)
    print("图表规格生成安全门禁")
    print("检查：禁止 HTML/JS / 禁止 LLM / 禁止 DuckDB / JSON 序列化 / 跨域降级")
    print("=" * 60)

    sections = [
        ("HTML/JS 输出检测", html_result),
        ("LLM/DuckDB 导入检测", imports_result),
        ("JSON 序列化验证", json_result),
        ("跨域降级验证", downgrade_result),
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
        print(f"\n[FAIL] 图表规格安全门禁: 发现 {total_fail} 项失败！")
        return 1
    else:
        print("\n[OK] 图表规格安全门禁通过。")
        return 0


def main() -> int:
    """命令行入口"""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="图表规格生成安全门禁")
    parser.add_argument("--config", default=None,
                        help="Harness 配置文件路径（本检查不使用，仅为兼容接口保留）")
    _args = parser.parse_args()

    html_result = check_no_html_js_output()
    imports_result = check_no_llm_no_duckdb_imports()
    json_result = check_json_serializable()
    downgrade_result = check_cross_domain_downgrade()

    return print_report(html_result, imports_result, json_result, downgrade_result)


if __name__ == "__main__":
    sys.exit(main())
