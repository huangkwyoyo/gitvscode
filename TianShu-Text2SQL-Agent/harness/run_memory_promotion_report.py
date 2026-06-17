"""生成 Memory Rule 晋升候选 snapshot 报告。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.memory_promotion import (  # noqa: E402
    analyze_promotion_candidates,
    load_rules_from_registry,
    write_memory_promotion_snapshot,
)


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "harness" / "reports" / "memory_promotion_candidates"
DEFAULT_REGISTRY = PROJECT_ROOT / "docs" / "memory" / "memory_rules.yml"


def main() -> int:
    """CLI 入口：只生成报告，不修改规则状态。"""
    parser = argparse.ArgumentParser(description="生成 Memory Rule 晋升候选报告")
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help="memory_rules.yml 路径",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="用于校验 required_* 路径存在性的项目根目录",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="snapshot 报告输出目录",
    )
    args = parser.parse_args()

    try:
        rules = load_rules_from_registry(args.registry)
        result = analyze_promotion_candidates(
            rules,
            project_root=args.project_root,
            source_registry=_relative_or_absolute(args.registry, args.project_root),
        )
        paths = write_memory_promotion_snapshot(result, args.output_dir)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("Memory Rule Promotion Candidate Report")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['markdown']}")
    print(f"ready_for_human_review: {summary['ready_for_human_review']}")
    print(f"missing_coverage: {summary['missing_coverage']}")
    print(f"invalid_references: {summary['invalid_references']}")
    print(f"not_recommended: {summary['not_recommended']}")
    return 0


def _relative_or_absolute(path: Path, root: Path) -> str:
    """优先返回相对路径，避免报告依赖本机绝对路径。"""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
