#!/usr/bin/env python3
"""
构建 M5b-1 测试用 sample DuckDB 数据库。

在 fixtures/sandbox/ 下创建一个小的 DuckDB 数据库，
包含 gold.dws_daily_trip_summary 表的 sample 数据。

用法:
    python fixtures/sandbox/build_sample_db.py

产出:
    fixtures/sandbox/sample.duckdb
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import duckdb
except ImportError:
    print("需要 duckdb 包: pip install duckdb")
    raise SystemExit(1)


def build_sample_db(output_path: Path) -> Path:
    """构建包含 NYC 出行模拟数据的 sample DuckDB 数据库。

    Args:
        output_path: 输出数据库文件路径

    Returns:
        Path——创建的数据库文件路径
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    conn = duckdb.connect(str(output_path))

    try:
        conn.execute("CREATE SCHEMA IF NOT EXISTS gold")

        conn.execute("""
            CREATE TABLE gold.dws_daily_trip_summary AS
            SELECT *
            FROM (
                VALUES
                    ('2026-01-01'::DATE, 150, 2250.50, 320.75, 375.00, 25.00),
                    ('2026-01-02'::DATE, 142, 2130.00, 305.50, 355.00, 28.50),
                    ('2026-01-03'::DATE, 168, 2520.75, 350.25, 420.00, 33.75),
                    ('2026-01-04'::DATE, 155, 2325.00, 330.00, 387.50, 31.00),
                    ('2026-01-05'::DATE, 160, 2400.00, 345.50, 400.00, 32.00),
                    ('2026-01-06'::DATE, 148, 2220.00, 315.25, 370.00, 29.50),
                    ('2026-01-07'::DATE, 172, 2580.00, 360.00, 430.00, 34.50),
                    ('2026-01-08'::DATE, 165, 2475.50, 348.75, 412.50, 33.00),
                    ('2026-01-09'::DATE, 158, 2370.00, 338.00, 395.00, 31.50),
                    ('2026-01-10'::DATE, 145, 2175.75, 310.50, 362.50, 29.00),
                    ('2026-02-01'::DATE, 152, 2280.00, 325.00, 380.00, 30.50),
                    ('2026-02-02'::DATE, 140, 2100.50, 300.00, 350.00, 28.00),
                    ('2026-02-03'::DATE, 175, 2625.00, 365.75, 437.50, 35.00),
                    ('2026-02-04'::DATE, 162, 2430.25, 340.50, 405.00, 32.50),
                    ('2026-02-05'::DATE, 155, 2325.00, 332.00, 387.50, 31.00),
                    ('2026-03-01'::DATE, 180, 2700.00, 375.00, 450.00, 36.00),
                    ('2026-03-02'::DATE, 170, 2550.75, 358.50, 425.00, 34.00),
                    ('2026-03-03'::DATE, 185, 2775.00, 385.25, 462.50, 37.00),
                    ('2026-03-04'::DATE, 178, 2670.50, 370.00, 445.00, 35.50),
                    ('2026-03-05'::DATE, 190, 2850.00, 395.50, 475.00, 38.00)
            ) AS t(
                trip_date,
                trip_count,
                total_fare_amount,
                total_distance_miles,
                total_tip_amount,
                parking_violation_count
            )
        """)
    finally:
        conn.close()

    return output_path


if __name__ == "__main__":
    output = PROJECT_ROOT / "fixtures" / "sandbox" / "sample.duckdb"
    result_path = build_sample_db(output)
    print(f"Sample 数据库已创建: {result_path}")
    print(f"  大小: {result_path.stat().st_size} bytes")
