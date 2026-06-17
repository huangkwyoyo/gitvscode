"""
检查 ResultSummary 结构摘要安全门禁。

验证 src/result_summary.py 的安全约束：
    1. 模块可正常导入
    2. 不调用 LLM —— 源码中不含 LLM/API 相关 import
    3. 不访问 DuckDB —— 源码中不含 duckdb import
    4. grain 检测为纯规则 —— _detect_grain() 不含动态执行
    5. 输出字段不推断因果 —— ResultSummary 不含 cause/because 等因果字段
    6. 数据提取只读 —— summarize_sql_result() 不执行 SQL

用法：
    python harness/checks/check_result_summary_safety.py
"""

from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def check_module_importable() -> dict[str, Any]:
    """验证 result_summary 模块可正常导入"""
    checks: list[dict[str, Any]] = []

    try:
        from src.result_summary import ResultSummary  # noqa: F401
        checks.append({
            "name": "result_summary 模块导入",
            "status": "PASS",
            "detail": "模块导入成功",
        })
    except ImportError as e:
        checks.append({
            "name": "result_summary 模块导入",
            "status": "FAIL",
            "detail": str(e),
        })
        return {
            "checks": checks,
            "pass_count": 0, "fail_count": 1,
        }

    return {
        "checks": checks,
        "pass_count": 1, "fail_count": 0,
    }


def check_no_llm_no_duckdb_imports() -> dict[str, Any]:
    """验证 result_summary.py 不 import LLM 或 DuckDB 模块"""
    checks: list[dict[str, Any]] = []

    src_path = Path(__file__).resolve().parent.parent.parent / "src" / "result_summary.py"
    if not src_path.exists():
        return {
            "checks": [{"name": "result_summary.py 路径", "status": "FAIL", "detail": "文件不存在"}],
            "pass_count": 0, "fail_count": 1,
        }

    source = src_path.read_text(encoding="utf-8")

    # 只检查实际的 import 语句行（排除中文注释中出现的词汇）
    import_lines = [
        line.strip().lower()
        for line in source.split("\n")
        if line.strip().startswith(("import ", "from "))  # 只检查实际的 import 行
    ]
    import_text = "\n".join(import_lines)

    # 不应导入 LLM 相关模块
    llm_imports = ["openai", "anthropic", "httpx", "requests", "llm", "api_key"]
    llm_found = [kw for kw in llm_imports if kw in import_text]
    checks.append({
        "name": "result_summary.py 不 import LLM/API 模块",
        "status": "FAIL" if llm_found else "PASS",
        "detail": f"发现: {llm_found}" if llm_found else "未发现 LLM/API import",
    })

    # 不应导入 DuckDB
    has_duckdb = "duckdb" in import_text
    checks.append({
        "name": "result_summary.py 不 import DuckDB",
        "status": "FAIL" if has_duckdb else "PASS",
        "detail": "发现 duckdb import" if has_duckdb else "未发现 DuckDB import",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_grain_detection_is_rule_based() -> dict[str, Any]:
    """验证 _detect_grain() 是纯规则函数，不包含动态执行"""
    checks: list[dict[str, Any]] = []

    try:
        from src.result_summary import _detect_grain
    except ImportError as e:
        return {
            "checks": [{"name": "_detect_grain 导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    source = inspect.getsource(_detect_grain)
    source_lower = source.lower()

    # 不应包含 import 语句（纯规则函数不应动态导入）
    has_import = "import " in source_lower
    checks.append({
        "name": "_detect_grain() 不含 import 语句",
        "status": "FAIL" if has_import else "PASS",
        "detail": "含 import 语句" if has_import else "纯规则函数",
    })

    # 不应包含 exec/eval
    has_exec = "exec(" in source or "eval(" in source
    checks.append({
        "name": "_detect_grain() 不含 exec/eval",
        "status": "FAIL" if has_exec else "PASS",
        "detail": "含 exec/eval" if has_exec else "无动态执行",
    })

    # 验证返回值为 grain 字符串（daily/unknown）
    has_return_daily = '"daily"' in source or "'daily'" in source
    has_return_unknown = '"unknown"' in source or "'unknown'" in source
    checks.append({
        "name": "_detect_grain() 返回值含 daily/unknown",
        "status": "PASS" if (has_return_daily and has_return_unknown) else "FAIL",
        "detail": "返回 daily/unknown" if (has_return_daily and has_return_unknown) else "返回值不完整",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_no_causal_fields_in_output() -> dict[str, Any]:
    """验证 ResultSummary 输出字段不含因果推断相关字段"""
    checks: list[dict[str, Any]] = []

    try:
        from src.ir import ResultSummary
    except ImportError as e:
        return {
            "checks": [{"name": "ResultSummary 导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    # 获取 ResultSummary 的所有字段名
    if hasattr(ResultSummary, '__dataclass_fields__'):
        fields = list(ResultSummary.__dataclass_fields__.keys())
    elif hasattr(ResultSummary, '__annotations__'):
        fields = list(ResultSummary.__annotations__.keys())
    else:
        checks.append({
            "name": "ResultSummary 字段检测",
            "status": "WARN",
            "detail": "无法获取字段列表",
        })
        return {"checks": checks, "pass_count": 0, "fail_count": 0}

    # 不应包含因果推断相关字段
    causal_keywords = ["cause", "because", "therefore", "causal", "infer", "explain", "reasoning"]
    causal_found = [kw for kw in causal_keywords if any(kw in f.lower() for f in fields)]
    checks.append({
        "name": "ResultSummary 不含因果字段",
        "status": "FAIL" if causal_found else "PASS",
        "detail": f"含因果字段: {causal_found}" if causal_found else f"字段: {fields}",
    })

    # 应包含预期的结构化字段
    expected_fields = ["source_plan_index", "metrics", "columns", "row_count", "grain"]
    missing_expected = [f for f in expected_fields if f not in fields]
    checks.append({
        "name": "ResultSummary 含预期结构字段",
        "status": "WARN" if missing_expected else "PASS",
        "detail": f"缺少: {missing_expected}" if missing_expected else f"全部包含: {expected_fields}",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_summarize_does_not_execute_sql() -> dict[str, Any]:
    """验证 summarize_sql_result() 不包含 SQL 执行调用"""
    checks: list[dict[str, Any]] = []

    try:
        from src.result_summary import summarize_sql_result
    except ImportError as e:
        return {
            "checks": [{"name": "summarize_sql_result 导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    source = inspect.getsource(summarize_sql_result)
    source_lower = source.lower()

    # 不应包含 execute / cursor / sql 调用
    sql_indicators = [".execute(", ".executemany(", "cursor(", "duckdb.sql", "duckdb.execute"]
    sql_found = [ind for ind in sql_indicators if ind in source_lower]
    checks.append({
        "name": "summarize_sql_result() 不执行 SQL",
        "status": "FAIL" if sql_found else "PASS",
        "detail": f"含 SQL 执行: {sql_found}" if sql_found else "无 SQL 执行调用",
    })

    # 不调用 LLM 相关函数
    llm_calls = ["llm_client", "chat(", "completion", "generate(", "openai."]
    llm_found = [ind for ind in llm_calls if ind in source_lower]
    checks.append({
        "name": "summarize_sql_result() 不调用 LLM",
        "status": "FAIL" if llm_found else "PASS",
        "detail": f"含 LLM 调用: {llm_found}" if llm_found else "无 LLM 调用",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def print_report(result: dict[str, Any]) -> None:
    """输出检查报告"""
    print("\n── ResultSummary 安全门禁 ──")
    for c in result["checks"]:
        tag = "PASS" if c["status"] == "PASS" else ("WARN" if c["status"] == "WARN" else "FAIL")
        print(f"  [{tag}] {c['name']}")
        if c["detail"]:
            print(f"         {c['detail']}")
    print(f"\n  检查完成 — 通过: {result['pass_count']}, 失败: {result['fail_count']}")


def main() -> int:
    """运行所有 ResultSummary 安全检查"""
    parser = argparse.ArgumentParser(description="ResultSummary 安全门禁")
    parser.add_argument("--config", default="config/tianshu_target.yml", help="配置文件路径（保留兼容，未使用）")
    args = parser.parse_args()

    all_checks: list[dict[str, Any]] = []
    total_pass = 0
    total_fail = 0

    for check_fn in [
        check_module_importable,
        check_no_llm_no_duckdb_imports,
        check_grain_detection_is_rule_based,
        check_no_causal_fields_in_output,
        check_summarize_does_not_execute_sql,
    ]:
        result = check_fn()
        all_checks.extend(result["checks"])
        total_pass += result["pass_count"]
        total_fail += result["fail_count"]

    merged = {
        "checks": all_checks,
        "pass_count": total_pass,
        "fail_count": total_fail,
    }
    print_report(merged)

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
