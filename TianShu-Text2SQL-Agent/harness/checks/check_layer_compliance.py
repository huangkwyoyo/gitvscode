"""
检查层级合规门禁。

验证 evals/ 中问题集 SQL 是否遵循 G3 > G2 > Silver > Bronze 的层级优先级。

检查逻辑：
    1. 从 contracts/semantic_contract.yml 加载表优先级定义
    2. 扫描 SQL 中引用的所有表
    3. 判断是否存在"可用的 G3 表但用了 G2"的降级遗漏
    4. 判断是否引用了禁止的表（Bronze/Silver）

用法：
    python harness/checks/check_layer_compliance.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from harness.config import load_harness_config


def load_table_hierarchy(contracts_path: Path) -> dict[str, Any]:
    """
    从 semantic_contract.yml 加载表层级定义。

    Returns:
        {
            g3_tables: [{table, zh_name, key_dimensions, key_metrics}],
            g2_tables: [{table, zh_name, note}],
            dim_tables: [{table, zh_name}],
            forbidden_patterns: ["bronze.*", "silver.*"]
        }
    """
    semantic_file = contracts_path / "semantic_contract.yml"
    if not semantic_file.exists():
        return {}

    with open(semantic_file, "r", encoding="utf-8") as f:
        semantic = yaml.safe_load(f)

    return {
        "g3_tables": [
            {"table": t["table"], "zh_name": t.get("zh_name", ""),
             "key_dimensions": t.get("key_dimensions", []),
             "key_metrics": t.get("key_metrics", [])}
            for t in semantic.get("g3_summary", [])
        ],
        "g2_tables": [
            {"table": t["table"], "zh_name": t.get("zh_name", ""),
             "note": t.get("note", "")}
            for t in semantic.get("g2_facts", [])
        ],
        "dim_tables": [
            {"table": t["table"], "zh_name": t.get("zh_name", "")}
            for t in semantic.get("dimensions", [])
        ],
        "views": [
            {"table": v["table"], "zh_name": v.get("zh_name", "")}
            for v in semantic.get("views", [])
        ],
        "forbidden_patterns": [
            fb.get("pattern", "") for fb in semantic.get("forbidden", [])
        ],
    }


def extract_table_references(sql: str) -> list[str]:
    """
    从 SQL 中提取所有表引用（schema.table 格式）。

    解析 FROM / JOIN 子句中的完全限定表名。
    """
    tables: list[str] = []

    # 匹配 schema.table 格式（允许在 FROM, JOIN, ON 后面出现）
    pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*)'
    matches = re.findall(pattern, sql, re.IGNORECASE)

    # 去重，保持顺序
    seen = set()
    for t in matches:
        if t.lower() not in seen:
            tables.append(t.lower())
            seen.add(t.lower())

    return tables


def check_layer_compliance(
    evals_path: Path,
    hierarchy: dict[str, Any],
) -> dict[str, Any]:
    """
    检查所有问题集 SQL 的层级合规性。

    Returns:
        {violations: [...], checks: [...]}
    """
    violations: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    if not evals_path.exists():
        return {"violations": violations, "checks": [{
            "name": "evals 目录", "status": "SKIP", "detail": "不存在"
        }]}

    g3_table_names = {t["table"].lower() for t in hierarchy.get("g3_tables", [])}
    g2_table_names = {t["table"].lower() for t in hierarchy.get("g2_tables", [])}
    dim_table_names = {t["table"].lower() for t in hierarchy.get("dim_tables", [])}
    view_names = {v["table"].lower() for v in hierarchy.get("views", [])}
    all_allowed = g3_table_names | g2_table_names | dim_table_names | view_names
    forbidden_patterns = hierarchy.get("forbidden_patterns", [])

    for yaml_file in sorted(evals_path.glob("*.yml")):
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        questions = data if isinstance(data, list) else data.get("questions", [])
        for q in questions:
            if not isinstance(q, dict) or "sql" not in q:
                continue

            qid = q.get("id", "unknown")
            sql = q["sql"]
            tables = extract_table_references(sql)

            if not tables:
                checks.append({
                    "name": f"{yaml_file.name} / {qid}",
                    "status": "WARN",
                    "detail": "SQL 中未检测到表引用",
                })
                continue

            # 检查是否引用了禁止的表
            for table in tables:
                for pattern in forbidden_patterns:
                    # 将 glob 模式转为正则
                    regex_pattern = pattern.replace(".", r"\.").replace("*", ".*")
                    if re.match(regex_pattern, table):
                        violations.append({
                            "file": yaml_file.name,
                            "question_id": qid,
                            "table": table,
                            "reason": f"引用了禁止的表（匹配规则: {pattern}）",
                        })

            # 检查 G3 可用性（简单规则：如果是日度聚合且用了 G2，标记为降级）
            tables_set = set(tables)
            has_g3 = bool(tables_set & g3_table_names)
            has_g2 = bool(tables_set & g2_table_names)
            has_unknown = bool(tables_set - all_allowed)

            if has_unknown:
                unknown_tables = tables_set - all_allowed
                checks.append({
                    "name": f"{yaml_file.name} / {qid}",
                    "status": "WARN",
                    "detail": f"引用了未在 semantic_contract.yml 中注册的表: {unknown_tables}",
                })
            elif has_g3 and not has_g2:
                checks.append({
                    "name": f"{yaml_file.name} / {qid}",
                    "status": "PASS",
                    "detail": f"使用 G3 表: {tables_set & g3_table_names}",
                })
            elif has_g2 and not has_g3:
                # G2 降级 —— 不一定是错误，但需要标注原因
                expect_downgrade_note = q.get("caution", "").lower()
                has_downgrade_kw = any(
                    kw in expect_downgrade_note
                    for kw in ["降级", "回退", "g3 不含", "汇总表不", "无对应"]
                )
                checks.append({
                    "name": f"{yaml_file.name} / {qid}",
                    "status": "PASS" if has_downgrade_kw else "WARN",
                    "detail": (
                        f"使用 G2 表: {tables_set & g2_table_names}，"
                        f"{'已标注降级原因' if has_downgrade_kw else '未标注降级原因'}"
                    ),
                })
            else:
                checks.append({
                    "name": f"{yaml_file.name} / {qid}",
                    "status": "PASS",
                    "detail": f"使用维表/视图: {tables_set}",
                })

    return {"violations": violations, "checks": checks}


def print_report(results: dict[str, Any]) -> int:
    """打印检查报告，返回退出码"""
    print("=" * 60)
    print("层级合规门禁")
    print("规则: G3 > G2 > Silver > Bronze")
    print("=" * 60)

    violations = results["violations"]
    checks = results["checks"]

    # 违规项
    if violations:
        print("\n── 违规项 ──")
        for v in violations:
            print(f"  [FAIL] {v['file']} / {v['question_id']}")
            print(f"         {v['reason']}")
            print(f"         表: {v['table']}")

    # 逐题检查
    print(f"\n── 逐题检查 ({len(checks)} 题) ──")
    for c in checks:
        tag = c["status"]
        print(f"  [{tag}] {c['name']}")
        if c.get("detail"):
            print(f"         {c['detail']}")

    fail_count = len(violations)
    warn_count = sum(1 for c in checks if c["status"] == "WARN")
    pass_count = sum(1 for c in checks if c["status"] == "PASS")

    print(f"\n  检查完成 — 通过: {pass_count}, 警告: {warn_count}, 失败: {fail_count}")

    if fail_count > 0:
        print(f"\n[FAIL] 发现 {fail_count} 项层级违规！")
        return 1
    elif not checks:
        print("\n[OK] 无待检查的 SQL 语句。")
        return 0
    else:
        print(f"\n[OK] 层级合规检查通过（{warn_count} 项警告，不阻断）。")
        return 0


def main() -> int:
    """命令行入口"""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="层级合规门禁")
    parser.add_argument("--config", default="config/tianshu_target.yml")
    parser.add_argument("--evals", type=Path, help="evals 目录路径")
    args = parser.parse_args()

    try:
        harness_config = load_harness_config(args.config)
    except FileNotFoundError as e:
        print(f"[SKIP] {e}")
        return 0

    evals_path = args.evals or harness_config.evals_path
    hierarchy = load_table_hierarchy(harness_config.contracts_path)

    results = check_layer_compliance(evals_path, hierarchy)
    return print_report(results)


if __name__ == "__main__":
    sys.exit(main())
