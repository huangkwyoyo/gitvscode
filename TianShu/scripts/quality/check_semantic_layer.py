"""
中文语义层门禁检查

检查 Gold G3 后的指标口径、语义维度、问数模板和标准问题集是否可用。
"""
import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from harness_config import load_harness_config

try:
    import duckdb
except ImportError:
    duckdb = None


REQUIRED_META_TABLES = {
    "metric_definitions",
    "semantic_dimensions",
    "semantic_query_templates",
    "business_terms",
}


def load_questions(path: Path) -> list[dict[str, Any]]:
    """读取标准中文问数集"""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    questions = data.get("questions", [])
    if not isinstance(questions, list):
        raise ValueError("questions 必须是列表")
    return questions


def check_semantic_layer(db_path: Path, questions_path: Path) -> list[str]:
    """检查语义层表、指标和标准问题集"""
    if duckdb is None:
        return ["duckdb 未安装，无法检查语义层"]
    if not questions_path.exists():
        return [f"标准中文问数集不存在: {questions_path}"]

    questions = load_questions(questions_path)
    violations: list[str] = []
    if len(questions) < 6:
        violations.append("标准中文问数集至少需要 6 个问题")

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        meta_tables = {
            row[0]
            for row in con.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'meta'
                """
            ).fetchall()
        }
        missing_meta = REQUIRED_META_TABLES - meta_tables
        for table_name in sorted(missing_meta):
            violations.append(f"缺少语义层表: meta.{table_name}")

        if not missing_meta:
            metric_names = {
                row[0]
                for row in con.execute("SELECT metric_name FROM meta.metric_definitions").fetchall()
            }
            template_count = con.execute("SELECT count(*) FROM meta.semantic_query_templates").fetchone()[0]
            if len(metric_names) < 8:
                violations.append("meta.metric_definitions 至少需要 8 个指标")
            if template_count < 6:
                violations.append("meta.semantic_query_templates 至少需要 6 个问数模板")

            for item in questions:
                question_id = item.get("id", "")
                for field in ["question_zh", "recommended_table", "metric_names", "sql", "caution"]:
                    if not item.get(field):
                        violations.append(f"{question_id or '未命名问题'} 缺少字段: {field}")
                for metric_name in item.get("metric_names", []):
                    if metric_name not in metric_names:
                        violations.append(f"{question_id} 引用未登记指标: {metric_name}")
                sql = item.get("sql")
                if sql:
                    try:
                        con.execute(f"SELECT * FROM ({sql}) AS q LIMIT 1").fetchall()
                    except Exception as exc:
                        violations.append(f"{question_id} SQL 无法执行: {exc}")
    finally:
        con.close()

    return violations


def main() -> int:
    """命令行入口"""
    config = load_harness_config()
    parser = argparse.ArgumentParser(description="中文语义层门禁检查")
    parser.add_argument("--db", type=Path, default=config.duckdb_path, help="DuckDB 数据库路径")
    parser.add_argument(
        "--questions",
        type=Path,
        default=config.project_root / "harness" / "questions" / "gold_standard_questions.yml",
        help="标准中文问数集路径",
    )
    args = parser.parse_args()

    try:
        violations = check_semantic_layer(args.db, args.questions)
    except Exception as exc:
        print(f"[FAIL] 中文语义层门禁执行失败: {exc}")
        return 1

    if violations:
        print("[FAIL] 中文语义层门禁发现问题：")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("[OK] 中文语义层门禁检查通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
