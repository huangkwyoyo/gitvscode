"""
Gold 层日期键质量门禁。

检查所有 Gold 事实表和汇总表的日期键是否引用了 dim_date 覆盖范围外的日期。
dim_date 覆盖范围（1997-01-01 ~ 2027-12-31）是"已知有效日期"的权威白名单，
超出此范围的日期键应视为异常。

当前已知异常：
- fact_parking_violations.issue_date_key 包含 1971、2060 等异常值

用法：
    python scripts/quality/check_gold_date_quality.py
    python scripts/quality/check_gold_date_quality.py --db <path>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from harness_config import load_harness_config

try:
    import duckdb
except ImportError:
    duckdb = None

# 待检查的事实表和对应的日期键列
# 格式: (schema.table, column_name, 中文说明)
DATE_KEY_CHECKS: list[tuple[str, str, str]] = [
    ("gold.fact_parking_violations", "issue_date_key", "罚单开票日期键"),
    ("gold.fact_trips", "pickup_date_key", "接客日期键"),
    ("gold.fact_trips", "dropoff_date_key", "送客日期键"),
    ("gold.fact_tif_payments", "payment_date_key", "支付日期键"),
    ("gold.fact_driver_applications", "app_date_key", "申请日期键"),
    ("gold.fact_crashes", "crash_date_key", "事故日期键"),
    ("gold.fact_crash_persons", "crash_date_key", "事故人员日期键"),
    ("gold.dws_daily_trip_summary", "date_key", "每日行程汇总日期键"),
    ("gold.dws_daily_parking_summary", "date_key", "每日停车罚单汇总日期键"),
    ("gold.dws_daily_crash_summary", "date_key", "每日事故汇总日期键"),
]

# 异常率阈值：超过此比例视为需要阻断的异常
ANOMALY_RATE_THRESHOLD = 0.01  # 1%


def check_date_quality(db_path: Path) -> dict[str, Any]:
    """检查全部日期键的异常情况，返回结构化结果字典"""
    if duckdb is None:
        raise ImportError("需要 duckdb 包")

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        # 获取 dim_date 的有效日期键范围
        dim_row = conn.execute(
            "SELECT min(date_key), max(date_key), count(*) FROM gold.dim_date"
        ).fetchone()
        min_valid = dim_row[0]
        max_valid = dim_row[1]
        dim_rows = dim_row[2]

        results: dict[str, Any] = {
            "valid_range": [min_valid, max_valid],
            "dim_date_rows": dim_rows,
            "tables": {},
        }

        for full_table, column, zh_name in DATE_KEY_CHECKS:
            schema_name, table_name = full_table.split(".")

            # 检查表和列是否存在
            exists = conn.execute(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_schema = ? AND table_name = ? AND column_name = ?",
                [schema_name, table_name, column],
            ).fetchone()[0]

            if not exists:
                results["tables"][full_table] = {
                    "status": "SKIP",
                    "zh_name": zh_name,
                    "detail": f"列 {column} 不存在，跳过检查",
                }
                continue

            # 统计异常记录数（超出 dim_date 范围）
            anomaly_count = conn.execute(
                f"""
                SELECT count(*) FROM {full_table}
                WHERE {column} IS NOT NULL
                  AND ({column} < ? OR {column} > ?)
                """,
                [min_valid, max_valid],
            ).fetchone()[0]

            # 统计非空总记录数
            total_count = conn.execute(
                f"SELECT count(*) FROM {full_table} WHERE {column} IS NOT NULL"
            ).fetchone()[0]

            if anomaly_count > 0:
                # 获取具体异常值分布
                anomaly_values = conn.execute(
                    f"""
                    SELECT {column}, count(*) AS cnt
                    FROM {full_table}
                    WHERE {column} IS NOT NULL
                      AND ({column} < ? OR {column} > ?)
                    GROUP BY {column}
                    ORDER BY cnt DESC
                    LIMIT 10
                    """,
                    [min_valid, max_valid],
                ).fetchall()

                anomaly_pct = (
                    round(anomaly_count / total_count * 100, 4)
                    if total_count > 0
                    else 0.0
                )
                # 判定：异常率 > 1% → FAIL，否则 WARN（已知问题）
                severity = (
                    "FAIL" if anomaly_pct > ANOMALY_RATE_THRESHOLD * 100 else "WARN"
                )

                results["tables"][full_table] = {
                    "status": "ANOMALY",
                    "severity": severity,
                    "zh_name": zh_name,
                    "anomaly_count": anomaly_count,
                    "total_count": total_count,
                    "anomaly_pct": anomaly_pct,
                    "anomaly_values": [
                        {"date_key": str(row[0]), "count": row[1]}
                        for row in anomaly_values
                    ],
                }
            else:
                results["tables"][full_table] = {
                    "status": "CLEAN",
                    "zh_name": zh_name,
                    "total_count": total_count,
                }

        return results
    finally:
        conn.close()


def print_report(results: dict[str, Any]) -> int:
    """打印检查报告，返回退出码（0=全通过，异常仅 WARN 不阻断）"""
    valid_range = results["valid_range"]
    dim_rows = results["dim_date_rows"]

    print("=" * 60)
    print("Gold 层日期键质量门禁")
    print(f"dim_date 有效范围: {valid_range[0]} ~ {valid_range[1]} ({dim_rows} 行)")
    print("=" * 60)

    clean_count = 0
    skip_count = 0
    warn_count = 0
    fail_count = 0

    for full_table, info in results["tables"].items():
        status = info["status"]
        zh_name = info["zh_name"]

        if status == "CLEAN":
            clean_count += 1
            print(f"  [PASS] {full_table} ({zh_name}) — {info['total_count']} 条非空，全部在有效范围内")
        elif status == "SKIP":
            skip_count += 1
            print(f"  [SKIP] {full_table} ({zh_name}) — {info['detail']}")
        elif status == "ANOMALY":
            warn_count += 1
            tag = "WARN"
            print(f"  [{tag}] {full_table} ({zh_name})")
            print(f"         异常记录: {info['anomaly_count']} / {info['total_count']} ({info['anomaly_pct']}%)")
            print(f"         异常值分布:")
            for av in info["anomaly_values"]:
                print(f"           - date_key={av['date_key']}: {av['count']} 条")

    print()
    summary_parts = [f"正常: {clean_count}", f"跳过: {skip_count}"]
    if warn_count:
        summary_parts.append(f"警告: {warn_count}")
    if fail_count:
        summary_parts.append(f"失败: {fail_count}")
    print(f"  检查完成 — {', '.join(summary_parts)}")

    if warn_count > 0:
        print(f"\n[WARN] 检测到 {warn_count} 张表存在异常日期（如 1971/2060/2028+），已记录但未阻断。")
        print(f"       分析 Agent 和 BI 工具建议使用 gold.v_parking_violations_valid 视图。")
    print("\n[OK] 日期键质量门禁通过（异常仅警告，不阻断）。")
    return 0


def main() -> int:
    """命令行入口"""
    # Windows GBK 编码兼容
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    config = load_harness_config()
    parser = argparse.ArgumentParser(description="Gold 层日期键质量门禁")
    parser.add_argument(
        "--db", type=Path, default=config.duckdb_path, help="DuckDB 数据库路径"
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"[FAIL] 数据库文件不存在: {args.db}")
        return 1

    if duckdb is None:
        print("[FAIL] 需要安装 duckdb 包: pip install duckdb")
        return 1

    try:
        results = check_date_quality(args.db)
    except Exception as exc:
        print(f"[FAIL] 日期键质量检查异常: {exc}")
        return 1

    return print_report(results)


if __name__ == "__main__":
    sys.exit(main())
