"""CLI 入口：从失败 case JSON 生成 memory suggestions snapshot 报告。

用法：
    python harness/run_memory_suggestions.py --input failed_cases.json
    python harness/run_memory_suggestions.py --input llm_e2e_eval_latest.json --source llm_e2e_eval
    python harness/run_memory_suggestions.py --input prompt_regression_latest.json --source prompt_regression

关键边界：
    - 只生成 timestamp snapshot，不写 latest。
    - 不修改 docs/memory/memory_rules.yml。
    - 不调用 LLM。
    - 不自动晋升 active。
    - 不设置 blocking=true。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.memory_suggestions import (  # noqa: E402
    build_memory_suggestions_from_e2e_report,
    build_memory_suggestions_from_prompt_regression,
    build_memory_suggestions_report,
    render_memory_suggestions_json,
    write_memory_suggestions_snapshot,
)

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "harness" / "reports" / "memory_suggestions"


def main() -> int:
    """CLI 入口：只生成报告，不修改规则状态。"""
    parser = argparse.ArgumentParser(
        description="从失败 case JSON 生成 memory suggestions snapshot 报告"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="失败 case JSON 文件路径",
    )
    parser.add_argument(
        "--source",
        choices=["runtime_baseline", "llm_e2e_eval", "prompt_regression"],
        default="runtime_baseline",
        help="数据来源类型（默认 runtime_baseline）",
    )
    parser.add_argument(
        "--source-run-id",
        default="",
        help="来源运行的 run_id（可选）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="snapshot 报告输出目录",
    )
    args = parser.parse_args()

    input_path = args.input.resolve()

    try:
        report = _load_and_build(
            input_path=input_path,
            source=args.source,
            source_run_id=args.source_run_id,
        )
        paths = write_memory_suggestions_snapshot(report, args.output_dir)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = report["summary"]
    print("Failure Triage Memory Suggestions Report")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['markdown']}")
    print(f"total_failed_cases: {summary['total_failed_cases']}")
    print(f"suggestions: {summary['suggestions']}")
    print(f"regression_candidates: {summary['regression_candidates']}")
    print(f"asset_dependencies: {summary['asset_dependencies']}")
    print(f"manual_review_required: {summary.get('manual_review_required', 0)}")
    return 0


def _load_and_build(
    input_path: Path,
    source: str,
    source_run_id: str,
) -> dict:
    """根据 source 类型加载输入文件并构造报告。

    - runtime_baseline: 通用失败 case 列表 JSON
    - llm_e2e_eval: E2E 评测报告 JSON
    - prompt_regression: Prompt regression 报告 JSON
    """
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    data = json.loads(input_path.read_text(encoding="utf-8"))

    if source == "llm_e2e_eval":
        return build_memory_suggestions_from_e2e_report(data, source=source)
    if source == "prompt_regression":
        return build_memory_suggestions_from_prompt_regression(data, source=source)

    # runtime_baseline / 通用格式
    # 输入可以是：
    #   1. 直接的失败 case 列表: [{"question_id": ..., "failure_type": ...}, ...]
    #   2. 带 cases 字段的结构: {"cases": [...], "run_id": "..."}
    if isinstance(data, list):
        failed_cases = data
    elif isinstance(data, dict):
        cases = data.get("cases") or data.get("failed_cases") or []
        failed_cases = [c for c in cases if not c.get("passed", True)]
        if not source_run_id:
            source_run_id = data.get("run_id", "")
    else:
        raise ValueError("输入 JSON 格式不支持：必须是 list 或 dict")

    return build_memory_suggestions_report(
        failed_cases,
        source=source,
        source_run_id=source_run_id,
    )


if __name__ == "__main__":
    raise SystemExit(main())
