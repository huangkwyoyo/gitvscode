#!/usr/bin/env python3
"""
M2 Review Package 构建入口。

只生成审查材料包，不接 LLM、不执行 SQL/Spark、不连接生产库。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.workflow import build_review_package


def main() -> int:
    """解析命令行参数并生成 Review Package"""
    parser = argparse.ArgumentParser(
        description="生成 Data Dev Agent v2.0 M2 Review Package",
    )
    parser.add_argument(
        "-r",
        "--requirement",
        required=True,
        help="需求 YAML fixture 路径",
    )
    parser.add_argument(
        "--output-root",
        default=str(PROJECT_ROOT / "generated" / "review_packages"),
        help="Review Package 输出根目录",
    )
    args = parser.parse_args()

    try:
        manifest = build_review_package(args.requirement, output_root=args.output_root)
    except Exception as exc:
        print(f"[FAIL] Review Package 生成失败: {exc}", file=sys.stderr)
        return 1

    print(f"Review Package: {manifest.package_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
