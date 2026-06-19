#!/usr/bin/env python3
"""
M5b-1 CLI：验证 DuckDB CTAS 物化。

在一次性 DuckDB Sandbox 中执行部署 CTAS 并验证结果。
不连接生产库、不自动上线、不修改人审状态。

使用示例:
  python scripts/dev_agent/verify_duckdb_ctas.py ^
    -p generated/review_packages/trip_daily_report_m2 ^
    --sample-db fixtures/sandbox/sample.duckdb

  # 或假设 sample 数据已用别的方式提供（通过 Python API）
  python scripts/dev_agent/verify_duckdb_ctas.py ^
    -p generated/review_packages/trip_daily_report_m2 ^
    --inline-sample fixtures/sandbox/sample_data.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.materialization_verification_engine import (  # noqa: E402
    verify_materialization,
)


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="M5b-1：验证 DuckDB CTAS 物化——一次性可写 Sandbox"
    )
    parser.add_argument(
        "-p", "--package",
        required=True,
        help="Review Package 路径",
    )
    parser.add_argument(
        "--sample-db",
        default="",
        help="sample DuckDB 数据库路径（只读打开，从中加载测试数据）",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="CTAS 执行超时时间（秒），默认 60",
    )
    return parser.parse_args()


def main() -> int:
    """CLI 主入口。"""
    args = parse_args()
    package_dir = Path(args.package)

    if not package_dir.is_dir():
        print(f"[FAIL] Review Package 路径不存在: {package_dir}", file=sys.stderr)
        return 1

    result = verify_materialization(
        package_dir=package_dir,
        sample_db_path=args.sample_db or None,
        timeout_seconds=args.timeout,
    )

    print(f"Verification ID: {result.verification_id}")
    print(f"Request ID: {result.request_id}")
    print(f"Sandbox ID: {result.sandbox_id}")
    print(f"Sandbox 目标: {result.sandbox_target}")
    print(f"静态校验: {result.static_validation_status}")
    print(f"CTAS 执行: {result.execution_status}")
    print(f"输出 Schema: {result.output_schema_status}")
    print(f"行数: {result.row_count_status} ({result.output_row_count})")
    print(f"幂等性: {result.idempotency_status}")
    print(f"清理: {result.cleanup_status}")
    print(f"总体状态: {result.overall_status}")

    if result.warnings:
        print(f"\n⚠️ 警告 ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"  - {w}")

    if result.failures:
        print(f"\n❌ 失败 ({len(result.failures)}):")
        for f in result.failures:
            print(f"  - {f}")

    if result.overall_status == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
