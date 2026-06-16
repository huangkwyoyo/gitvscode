"""
M3 CLI：验证 Review Package。

此入口只做验证，不接 LLM、不自动上线、不写生产库。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.verification_engine import verify_review_package  # noqa: E402


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="验证 v2 Review Package")
    parser.add_argument("-p", "--package", required=True, help="Review Package 路径")
    parser.add_argument("--no-sql-run", action="store_true", help="跳过 SQL sample run")
    parser.add_argument("--duckdb-path", default="", help="可选开发库 DuckDB 路径，只读打开")
    parser.add_argument("--limit", type=int, default=1000, help="SQL sample run 最大行数")
    parser.add_argument("--timeout", type=int, default=30, help="sample run 超时时间（秒）")
    return parser.parse_args()


def _open_dev_connection(path: str):
    """只读打开显式传入的开发库。"""
    if not path:
        return None
    import duckdb

    return duckdb.connect(path, read_only=True)


def main() -> int:
    """CLI 主入口。"""
    args = parse_args()
    conn = None
    try:
        conn = _open_dev_connection(args.duckdb_path)
        result = verify_review_package(
            package_path=args.package,
            conn=conn,
            no_sql_run=args.no_sql_run,
            limit=args.limit,
            timeout_seconds=args.timeout,
        )
    finally:
        if conn is not None:
            conn.close()

    print(f"Verification Report: {result.verification_report_path}")
    print(f"Cross Validation Report: {result.cross_validation_report_path}")
    print(f"Overall Status: {result.overall_status}")
    print(f"SQL Static: {result.sql_static_status}")
    print(f"SQL Sample: {result.sql_sample_status}")
    print(f"Spark Static: {result.spark_static_status}")
    print(f"Spark Sample: {result.spark_sample_status}")
    print(f"Cross Validation: {result.cross_validation_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
