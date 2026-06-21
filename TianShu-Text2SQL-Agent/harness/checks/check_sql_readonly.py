"""
检查 SQL 只读安全门禁。

扫描 evals/ 目录下所有 YAML 问题集中的 SQL 语句，
检测是否包含禁止的写操作关键字（INSERT/UPDATE/DELETE/DDL）。

从以下来源加载禁止关键字：
    1. TianShu contracts/sql_safety_policy.yml（权威源）
    2. config/agent_config.yml 中的 extra_forbidden_keywords（补充）

用法：
    python harness/checks/check_sql_readonly.py
    python harness/checks/check_sql_readonly.py --evals <path>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

# 添加项目根目录到路径，以便导入 harness.config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from harness.config import load_harness_config
from src.safety_policy_loader import load_forbidden_keywords as load_policy_keywords
from src.sql_gen import validate_sql_safety


SECURITY_PROBES = [
    {"name": "multiple_statements", "sql": "SELECT 1; SELECT 2", "allowed": False},
    {"name": "read_blob", "sql": "SELECT read_blob('file')", "allowed": False},
    {
        "name": "read_csv_auto",
        "sql": "SELECT * FROM read_csv_auto('file.csv')",
        "allowed": False,
    },
    {
        "name": "read_parquet",
        "sql": "SELECT * FROM read_parquet('file.parquet')",
        "allowed": False,
    },
    {"name": "trailing_semicolon", "sql": "SELECT 1;", "allowed": True},
    {"name": "semicolon_literal", "sql": "SELECT ';' AS value", "allowed": True},
    {"name": "semicolon_comment", "sql": "SELECT 1 -- ;", "allowed": True},
    {
        "name": "select_cte",
        "sql": "WITH cte AS (SELECT 1 AS value) SELECT value FROM cte",
        "allowed": True,
    },
]


def load_forbidden_keywords(contracts_path: Path, agent_config: dict[str, Any]) -> list[str]:
    """
    从契约文件和 Agent 配置中加载禁止的 SQL 关键字列表。

    Args:
        contracts_path: TianShu contracts/ 目录路径
        agent_config: Agent 运行时配置

    Returns:
        禁止的关键字列表（大写）
    """
    return load_policy_keywords(
        contracts_path=contracts_path,
        agent_config=agent_config,
        strict=True,
    )


def run_security_probes(forbidden_keywords: list[str]) -> dict[str, Any]:
    """运行 AST 正反探针，确认生产安全器保持预期边界。"""
    failed: list[dict[str, Any]] = []

    for probe in SECURITY_PROBES:
        violations = validate_sql_safety(probe["sql"], forbidden_keywords)
        actual_allowed = not violations
        if actual_allowed != probe["allowed"]:
            failed.append({
                **probe,
                "violations": violations,
                "actual_allowed": actual_allowed,
            })

    return {
        "failed": failed,
        "passed_count": len(SECURITY_PROBES) - len(failed),
        "total_count": len(SECURITY_PROBES),
    }


def scan_yaml_for_sql(evals_path: Path) -> list[dict[str, Any]]:
    """
    扫描 evals/ 目录下所有 YAML 文件，提取其中的 SQL 语句。

    Returns:
        [{file, question_id, sql}, ...]
    """
    entries: list[dict[str, Any]] = []
    if not evals_path.exists():
        return entries

    for yaml_file in sorted(evals_path.glob("*.yml")):
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # 支持两种格式：顶层列表 或 questions 键下的列表
        questions = data if isinstance(data, list) else data.get("questions", [])
        for q in questions:
            if isinstance(q, dict) and "sql" in q:
                entries.append({
                    "file": yaml_file.name,
                    "question_id": q.get("id", "unknown"),
                    "question_zh": q.get("question_zh", ""),
                    "sql": q["sql"],
                })

    return entries


def check_sql_readonly(
    evals_path: Path,
    forbidden_keywords: list[str],
) -> dict[str, Any]:
    """
    扫描所有评测问题集中的 SQL，检查是否违反只读规则。

    Args:
        evals_path: evals/ 目录路径
        forbidden_keywords: 禁止的 SQL 关键字列表

    Returns:
        {violations: [...], clean_count: int, total_count: int}
    """
    entries = scan_yaml_for_sql(evals_path)
    violations: list[dict[str, Any]] = []

    for entry in entries:
        sql_violations = validate_sql_safety(entry["sql"], forbidden_keywords)
        if sql_violations:
            violations.append({
                **entry,
                "reason": "; ".join(sql_violations),
            })

    return {
        "violations": violations,
        "clean_count": len(entries) - len(violations),
        "total_count": len(entries),
    }


def print_report(results: dict[str, Any], forbidden_keywords: list[str]) -> int:
    """打印检查报告，返回退出码"""
    print("=" * 60)
    print("SQL 只读安全门禁")
    print(f"禁止关键字 ({len(forbidden_keywords)}): {', '.join(sorted(forbidden_keywords))}")
    print("=" * 60)

    violations = results["violations"]
    if not results["total_count"]:
        print("  [SKIP] 未找到包含 SQL 的评测问题文件")
        print("\n[OK] 只读安全检查通过（无待检查的 SQL）。")
        return 0

    for v in violations:
        print(f"  [FAIL] {v['file']} / {v['question_id']}")
        print(f"         安全违规: {v['reason']}")
        print(f"         问题: {v.get('question_zh', '')}")

    if not violations:
        print(f"  [PASS] 全部 {results['clean_count']} 条 SQL 通过只读检查")

    print()
    if violations:
        print(f"[FAIL] 发现 {len(violations)} 条 SQL 未通过生产安全校验！")
        return 1
    else:
        print(f"[OK] 全部 {results['total_count']} 条 SQL 通过只读安全检查。")
        return 0


def main() -> int:
    """命令行入口"""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="SQL 只读安全门禁")
    parser.add_argument("--config", default="config/tianshu_target.yml", help="TianShu 目标配置")
    parser.add_argument("--evals", type=Path, help="evals 目录路径（默认从配置读取）")
    args = parser.parse_args()

    # 加载配置
    try:
        harness_config = load_harness_config(args.config)
    except FileNotFoundError as e:
        print(f"[FAIL] {e}")
        return 1

    evals_path = args.evals or harness_config.evals_path

    # 加载 Agent 配置
    agent_config: dict[str, Any] = {}
    agent_config_file = Path("config/agent_config.yml")
    if agent_config_file.exists():
        with open(agent_config_file, "r", encoding="utf-8") as f:
            agent_config = yaml.safe_load(f) or {}

    # 加载禁止关键字
    try:
        forbidden_keywords = load_forbidden_keywords(
            harness_config.contracts_path, agent_config
        )
    except (FileNotFoundError, ValueError, TypeError) as exc:
        print(f"[FAIL] SQL 安全策略加载失败: {exc}")
        return 1

    probe_results = run_security_probes(forbidden_keywords)
    if probe_results["failed"]:
        print("[FAIL] SQL AST 安全探针失败:")
        for probe in probe_results["failed"]:
            print(f"  - {probe['name']}: {probe['violations']}")
        return 1

    results = check_sql_readonly(evals_path, forbidden_keywords)
    return print_report(results, forbidden_keywords)


if __name__ == "__main__":
    sys.exit(main())
