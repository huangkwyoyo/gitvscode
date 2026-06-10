"""
Gold 构建回归测试。

测试目标不是替代业务验收，而是确保 Gold 表落库后具备基本可用性和中文语义元数据。
"""
import os
import subprocess
import sys
from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(r"D:\ProgramData\Datawarehouse\纽约市城市交通\nyc_transport.duckdb")

EXPECTED_DIMENSIONS = {
    "dim_date",
    "dim_taxi_zone",
    "dim_vehicle",
    "dim_driver",
    "dim_base",
    "dim_violation_type",
}

EXPECTED_FACTS = {
    "fact_trips": "trip_detail",
    "fact_parking_violations": "parking_violation_detail",
    "fact_tif_payments": "tif_payment_detail",
    "fact_driver_applications": "driver_application_detail",
    "fact_crashes": "crash_detail",
    "fact_crash_persons": "crash_person_detail",
}


def run_quality_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    """使用统一环境运行构建脚本，避免中文输出编码干扰"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def test_gold_g0_g1_build_creates_dimension_tables():
    """Gold G0/G1 构建后必须生成 6 张维表和中文注释"""
    result = run_quality_command(["scripts/gold/build_gold_duckdb.py", "--batches", "G0,G1"])

    assert result.returncode == 0, result.stdout

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        tables = {
            row[0]
            for row in con.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'gold'
                """
            ).fetchall()
        }
        assert EXPECTED_DIMENSIONS <= tables

        for table_name in EXPECTED_DIMENSIONS:
            count = con.execute(f"SELECT count(*) FROM gold.{table_name}").fetchone()[0]
            assert count > 0, table_name

        table_comment_count = con.execute(
            """
            SELECT count(*)
            FROM meta.table_comments
            WHERE table_schema = 'gold'
              AND table_name IN (
                  'dim_date', 'dim_taxi_zone', 'dim_vehicle',
                  'dim_driver', 'dim_base', 'dim_violation_type'
              )
            """
        ).fetchone()[0]
        assert table_comment_count == len(EXPECTED_DIMENSIONS)

        missing_column_comments = con.execute(
            """
            SELECT c.table_name, c.column_name
            FROM information_schema.columns c
            LEFT JOIN meta.column_comments m
              ON m.table_schema = c.table_schema
             AND m.table_name = c.table_name
             AND m.column_name = c.column_name
            WHERE c.table_schema = 'gold'
              AND c.table_name IN (
                  'dim_date', 'dim_taxi_zone', 'dim_vehicle',
                  'dim_driver', 'dim_base', 'dim_violation_type'
              )
              AND m.column_name_zh IS NULL
            """
        ).fetchall()
        assert missing_column_comments == []
    finally:
        con.close()


def test_gold_physical_gate_passes_after_g0_g1_build():
    """Gold G0/G1 建成后，物理门禁必须能独立校验落库结果"""
    result = run_quality_command(["scripts/quality/check_gold_physical.py", "--batches", "G0,G1"])

    assert result.returncode == 0, result.stdout
    assert "Gold 物理表门禁检查通过" in result.stdout


def test_gold_g2_build_creates_fact_tables():
    """Gold G2 构建后必须生成 6 张事实表，且行数与 Silver 明细表一致"""
    result = run_quality_command(["scripts/gold/build_gold_duckdb.py", "--batches", "G2"])

    assert result.returncode == 0, result.stdout

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        tables = {
            row[0]
            for row in con.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'gold'
                """
            ).fetchall()
        }
        assert set(EXPECTED_FACTS) <= tables

        for gold_table, silver_table in EXPECTED_FACTS.items():
            gold_count = con.execute(f"SELECT count(*) FROM gold.{gold_table}").fetchone()[0]
            silver_count = con.execute(f"SELECT count(*) FROM silver.{silver_table}").fetchone()[0]
            assert gold_count == silver_count, gold_table

        fine_coverage = con.execute(
            """
            SELECT
                count(*) AS total_rows,
                count(standard_fine_amount) AS rows_with_standard_fine
            FROM gold.fact_parking_violations
            """
        ).fetchone()
        assert fine_coverage[0] > 0
        assert fine_coverage[1] > 0
    finally:
        con.close()


def test_gold_physical_gate_passes_after_g2_build():
    """Gold G2 建成后，物理门禁必须覆盖事实表"""
    result = run_quality_command(["scripts/quality/check_gold_physical.py", "--batches", "G0,G1,G2"])

    assert result.returncode == 0, result.stdout
    assert "Gold 物理表门禁检查通过" in result.stdout
