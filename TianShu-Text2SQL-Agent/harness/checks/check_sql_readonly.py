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
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# 添加项目根目录到路径，以便导入 harness.config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from harness.config import load_harness_config


def load_forbidden_keywords(contracts_path: Path, agent_config: dict[str, Any]) -> list[str]:
    """
    从契约文件和 Agent 配置中加载禁止的 SQL 关键字列表。

    Args:
        contracts_path: TianShu contracts/ 目录路径
        agent_config: Agent 运行时配置

    Returns:
        禁止的关键字列表（大写）
    """
    keywords: list[str] = []

    # 从 sql_safety_policy.yml 加载
    safety_file = contracts_path / "sql_safety_policy.yml"
    if safety_file.exists():
        with open(safety_file, "r", encoding="utf-8") as f:
            safety = yaml.safe_load(f)
        forbidden_ops = safety.get("forbidden_operations", [])
        for op in forbidden_ops:
            keywords.extend(op.get("keywords", []))

    # 从 agent_config.yml 加载额外关键字
    extra = agent_config.get("safety", {}).get("extra_forbidden_keywords", [])
    keywords.extend(extra)

    return [kw.upper() for kw in keywords]


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
        sql_upper = entry["sql"].upper()
        for keyword in forbidden_keywords:
            # 使用词边界匹配，避免误匹配列名中的子串
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, sql_upper):
                violations.append({
                    **entry,
                    "keyword": keyword,
                })
                break  # 每条 SQL 只报告一次

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
        print(f"         SQL 包含禁止关键字: {v['keyword']}")
        print(f"         问题: {v.get('question_zh', '')}")

    if not violations:
        print(f"  [PASS] 全部 {results['clean_count']} 条 SQL 通过只读检查")

    print()
    if violations:
        print(f"[FAIL] 发现 {len(violations)} 条 SQL 包含禁止的写操作关键字！")
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
        print(f"[SKIP] {e}")
        return 0

    evals_path = args.evals or harness_config.evals_path

    # 加载 Agent 配置
    agent_config: dict[str, Any] = {}
    agent_config_file = Path("config/agent_config.yml")
    if agent_config_file.exists():
        with open(agent_config_file, "r", encoding="utf-8") as f:
            agent_config = yaml.safe_load(f) or {}

    # 加载禁止关键字
    forbidden_keywords = load_forbidden_keywords(
        harness_config.contracts_path, agent_config
    )

    results = check_sql_readonly(evals_path, forbidden_keywords)
    return print_report(results, forbidden_keywords)


if __name__ == "__main__":
    sys.exit(main())
