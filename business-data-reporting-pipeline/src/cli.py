#!/usr/bin/env python3
"""命令行入口 — 提供 run 和 web 两个子命令。"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="运行业务数据报表管道。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="运行完整数据分析管道。")
    run_parser.add_argument(
        "--config",
        default="configs/default.yaml",
        help="YAML 配置文件路径。",
    )

    web_parser = subparsers.add_parser("web", help="启动 Web 报表应用。")
    web_parser.add_argument("--host", default="127.0.0.1", help="监听地址。")
    web_parser.add_argument("--port", type=int, default=8000, help="监听端口。")
    return parser


def main() -> None:
    """CLI 主入口：根据子命令执行管道或启动 Web 服务。"""
    args = build_parser().parse_args()
    if args.command == "run":
        report_path = run_pipeline(Path(args.config))
        print(f"报告已生成: {report_path}")
    elif args.command == "web":
        from src.web.app import run_web_app

        run_web_app(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
