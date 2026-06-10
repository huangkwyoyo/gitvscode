"""
Gold 物理表门禁检查。

用于 Gold 建表后确认 DuckDB 实表、中文表注释和字段注释没有漂移。
"""
import argparse
import sys
from pathlib import Path

from harness_config import load_harness_config

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "gold"))

from build_gold_duckdb import GOLD_DIMENSIONS, parse_batches  # noqa: E402

try:
    import duckdb
except ImportError:
    duckdb = None


BATCH_TABLES = {
    "G0": ["dim_date", "dim_taxi_zone"],
    "G1": ["dim_vehicle", "dim_driver", "dim_base", "dim_violation_type"],
    "G2": [
        "fact_trips",
        "fact_parking_violations",
        "fact_tif_payments",
        "fact_driver_applications",
        "fact_crashes",
        "fact_crash_persons",
    ],
}


def expected_tables(batches: set[str]) -> list[str]:
    """根据批次返回应检查的 Gold 表"""
    tables: list[str] = []
    for batch in ["G0", "G1", "G2"]:
        if batch in batches:
            tables.extend(BATCH_TABLES[batch])
    return tables


def check_gold_physical(db_path: Path, table_names: list[str]) -> list[str]:
    """检查 Gold 物理表和中文注释"""
    if duckdb is None:
        return ["duckdb 未安装，无法检查 Gold 物理表"]

    conn = duckdb.connect(str(db_path), read_only=True)
    violations: list[str] = []
    try:
        existing_tables = {
            row[0]
            for row in conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'gold'
                """
            ).fetchall()
        }
        for table_name in table_names:
            if table_name not in existing_tables:
                violations.append(f"缺少 Gold 表: gold.{table_name}")
                continue

            row_count = conn.execute(f"SELECT count(*) FROM gold.{table_name}").fetchone()[0]
            if row_count <= 0:
                violations.append(f"Gold 表为空: gold.{table_name}")

            actual_columns = [
                row[0]
                for row in conn.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'gold'
                      AND table_name = ?
                    ORDER BY ordinal_position
                    """,
                    [table_name],
                ).fetchall()
            ]
            expected_columns = list(GOLD_DIMENSIONS[table_name]["columns"].keys())
            if actual_columns != expected_columns:
                violations.append(
                    f"gold.{table_name} 字段顺序或字段集合与构建规范不一致: "
                    f"actual={actual_columns}, expected={expected_columns}"
                )

            table_comment = conn.execute(
                """
                SELECT table_name_zh
                FROM meta.table_comments
                WHERE table_schema = 'gold'
                  AND table_name = ?
                """,
                [table_name],
            ).fetchall()
            if not table_comment or not table_comment[0][0]:
                violations.append(f"gold.{table_name} 缺少中文表注释")

            missing_comments = conn.execute(
                """
                SELECT c.column_name
                FROM information_schema.columns c
                LEFT JOIN meta.column_comments m
                  ON m.table_schema = c.table_schema
                 AND m.table_name = c.table_name
                 AND m.column_name = c.column_name
                WHERE c.table_schema = 'gold'
                  AND c.table_name = ?
                  AND m.column_name_zh IS NULL
                ORDER BY c.ordinal_position
                """,
                [table_name],
            ).fetchall()
            for (column_name,) in missing_comments:
                violations.append(f"gold.{table_name}.{column_name} 缺少中文字段注释")
    finally:
        conn.close()
    return violations


def main() -> int:
    """命令行入口"""
    config = load_harness_config()
    parser = argparse.ArgumentParser(description="Gold 物理表门禁检查")
    parser.add_argument("--db", type=Path, default=config.duckdb_path, help="DuckDB 数据库路径")
    parser.add_argument("--batches", default="G0,G1", help="检查批次，支持 G0,G1,G2")
    args = parser.parse_args()

    try:
        batches = parse_batches(args.batches)
    except ValueError as exc:
        print(f"[FAIL] {exc}")
        return 1

    violations = check_gold_physical(args.db, expected_tables(batches))
    if violations:
        print("[FAIL] Gold 物理表门禁发现问题：")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("[OK] Gold 物理表门禁检查通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
