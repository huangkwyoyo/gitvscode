from __future__ import annotations

import argparse
from pathlib import Path

from src.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the business data reporting pipeline.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the full data pipeline.")
    run_parser.add_argument(
        "--config",
        default="configs/default.yaml",
        help="Path to the YAML config file.",
    )

    web_parser = subparsers.add_parser("web", help="Start the web reporting app.")
    web_parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    web_parser.add_argument("--port", type=int, default=8000, help="Port to bind.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run":
        report_path = run_pipeline(Path(args.config))
        print(f"Report generated: {report_path}")
    elif args.command == "web":
        from src.web.app import run_web_app

        run_web_app(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
