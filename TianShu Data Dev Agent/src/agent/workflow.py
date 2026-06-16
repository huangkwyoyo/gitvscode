"""
v2.0 M2 主工作流。

只编排 Review Package 生成，不接 LLM，不执行 SQL/Spark。
"""

from __future__ import annotations

from pathlib import Path

from src.ir.types import ReviewPackageManifest

from .design_planner import build_design_plan
from .dual_code_generator import generate_dual_code
from .requirement_analyzer import analyze_requirement
from .review_publisher import publish_review_package


def build_review_package(
    requirement_path: str | Path,
    output_root: str | Path = "generated/review_packages",
) -> ReviewPackageManifest:
    """
    生成 Review Package。

    M2 明确不连接数据库、不执行 SQL、不执行 Spark、不接真实 LLM。
    """
    requirement = analyze_requirement(requirement_path)
    plan = build_design_plan(requirement)
    drafts = generate_dual_code(plan)
    return publish_review_package(
        requirement=requirement,
        plan=plan,
        drafts=drafts,
        output_root=output_root,
    )
