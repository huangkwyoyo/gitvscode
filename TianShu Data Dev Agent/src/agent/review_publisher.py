"""
Review Package 发布器。

M2 阶段只写审查材料，不写生产数据。
M4a：新增 decision.yml（机读权威状态）和 decision_log.yml（审计日志）。
M4b：decision.yml 含 artifact_hashes；decision_log 含 actor_id。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.ir.types import ArtifactHashes, DecisionRecord, DecisionStatus, ReviewPackageManifest

from .decision_manager import compute_artifact_hashes
from .design_planner import DevPlan
from .dual_code_generator import DualCodeDrafts
from .requirement_analyzer import RequirementSpec


REQUIRED_FILES = [
    "sql/main.sql",
    "spark/main.py",
    "tests/test_generated.py",
    "reports/verification.md",
    "reports/cross_validation.md",
    "lineage/source_refs.yml",
    "decision.md",
    "decision.yml",
    "decision_log.yml",
]


def _write_text(path: Path, content: str) -> None:
    """统一写入 UTF-8 文本"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_test_stub(requirement: RequirementSpec) -> str:
    """生成供人审查的测试草案"""
    return "\n".join([
        '"""',
        "草案：未经验证，未经人审，不得上线。",
        "M2 阶段只生成测试草案，不执行生产 SQL 或 Spark 作业。",
        '"""',
        "",
        "",
        "def test_review_package_requires_human_decision():",
        f'    request_id = "{requirement.request_id}"',
        "    assert request_id",
        '    assert "APPROVE" != "DEFAULT"',
        "",
    ])


def _build_verification_report() -> str:
    """生成 M2 验证报告占位内容"""
    return "\n".join([
        "# Verification Report",
        "",
        "状态：PENDING",
        "",
        "- M2 仅生成 Review Package。",
        "- 尚未执行静态 Validator。",
        "- 尚未执行 SQL dry-run / sample run。",
        "- 尚未执行 Spark dry-run / sample run。",
        "- 草案未经验证，未经人审，不得上线。",
        "",
    ])


def _build_cross_validation_report() -> str:
    """生成 M2 交叉验证报告占位内容"""
    return "\n".join([
        "# Cross Validation Report",
        "",
        "状态：SKIPPED",
        "",
        "- M2 未执行 SQL。",
        "- M2 未执行 Spark。",
        "- SQL vs Spark 结果交叉验证尚未开始。",
        "- 草案未经验证，未经人审，不得上线。",
        "",
    ])


def _build_decision_md(decision: DecisionRecord, plan: DevPlan, drafts: DualCodeDrafts) -> str:
    """生成人审决策文件（人读 Markdown）"""
    pending = list(dict.fromkeys(plan.pending_items + drafts.pending_items))
    review_points = list(dict.fromkeys(plan.human_review_points + drafts.human_review_points))
    lines = [
        "# Human Decision",
        "",
        "草案：未经验证，未经人审，不得上线。",
        "",
        f"请求 ID：{plan.request_id}",
        f"当前状态：{decision.current_state.value}",
        "",
        "## 决策选项",
    ]
    lines.extend(f"- {option}" for option in decision.options)
    lines.extend([
        "",
        "## 当前结论",
        "",
        "- 当前不是 APPROVE。",
        "- 需要人工审查 SQL、Spark DSL、来源追溯和 PENDING 项。",
        "",
        "## Human Review Points",
    ])
    lines.extend(f"- {item}" for item in review_points or ["Human Review: 请人工确认业务口径"])
    lines.extend([
        "",
        "## Pending Items",
    ])
    lines.extend(f"- {item}" for item in pending or ["PENDING: M2 未执行自动验证"])
    lines.append("")
    return "\n".join(lines)


def _build_lineage(requirement: RequirementSpec, plan: DevPlan) -> dict[str, Any]:
    """构造来源追溯信息"""
    source_fields = []
    human_review_points = list(plan.human_review_points)

    for field in requirement.required_fields:
        entry = {
            "name": field.get("name"),
            "table": field.get("table"),
            "source": field.get("source") or "Human Review",
        }
        if entry["source"] == "Human Review":
            human_review_points.append(f"Human Review: 字段 {entry['name']} 缺少来源")
        source_fields.append(entry)

    metric_sources = []
    for metric in requirement.metrics:
        entry = {
            "name": metric.get("name"),
            "field": metric.get("field"),
            "definition_source": metric.get("definition_source") or "Human Review",
        }
        if entry["definition_source"] == "Human Review":
            human_review_points.append(f"Human Review: 指标 {entry['name']} 缺少口径来源")
        metric_sources.append(entry)

    return {
        "request_id": requirement.request_id,
        "source_tables": requirement.source_tables,
        "source_fields": source_fields,
        "metric_sources": metric_sources,
        "filters": requirement.filters,
        "grain": requirement.grain,
        "human_review_points": human_review_points,
    }


def _build_decision_yml(
    requirement: RequirementSpec,
    artifact_hashes: ArtifactHashes | None = None,
) -> dict[str, Any]:
    """构造 decision.yml——机读权威状态源（M4b）。

    Agent 只能写入 PENDING_REVIEW，绝不写入 APPROVED/REQUEST_CHANGES/REJECTED。
    verification_overall_status 初始为 PENDING——等 M3 运行后才更新。
    artifact_hashes 记录生成时的代码哈希——M4b 完整性校验基础。
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    result: dict[str, Any] = {
        "request_id": requirement.request_id,
        "current_state": DecisionStatus.PENDING_REVIEW.value,
        "human_review_required": True,
        "last_updated": now_iso,
        "last_updated_by": "agent",
        "verification_report_ref": "reports/verification.md",
        "verification_overall_status": "PENDING",
        "human_decision_note": "",
    }
    if artifact_hashes is not None:
        result["artifact_hashes"] = artifact_hashes.to_dict()
    return result


def _build_decision_log_yml(requirement: RequirementSpec) -> dict[str, Any]:
    """构造 decision_log.yml 初始审计日志（M4b）。

    记录 Review Package 创建事件——这是审计链的起点。
    actor_id 为 "agent"——M4b 新增字段。
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "request_id": requirement.request_id,
        "entries": [
            {
                "timestamp": now_iso,
                "from_state": None,
                "to_state": DecisionStatus.PENDING_REVIEW.value,
                "changed_by": "agent",
                "actor_id": "agent",
                "reason": "Review Package 创建，初始状态为 PENDING_REVIEW",
            },
        ],
    }


def publish_review_package(
    requirement: RequirementSpec,
    plan: DevPlan,
    drafts: DualCodeDrafts,
    output_root: str | Path = "generated/review_packages",
) -> ReviewPackageManifest:
    """写出完整 Review Package 并返回 manifest。

    M4b 变更：先写代码和报告文件，计算 artifact 哈希，
    再将哈希写入 decision.yml——保证哈希与文件一致。
    """
    root = Path(output_root)
    package_dir = root / requirement.request_id
    for rel in ["sql", "spark", "tests", "reports", "lineage"]:
        (package_dir / rel).mkdir(parents=True, exist_ok=True)

    # 阶段 1：写所有代码和报告文件（decision.yml/decision_log.yml 除外）
    _write_text(package_dir / "sql" / "main.sql", drafts.sql.content)
    _write_text(package_dir / "spark" / "main.py", drafts.spark.content)
    _write_text(package_dir / "tests" / "test_generated.py", _build_test_stub(requirement))
    _write_text(package_dir / "reports" / "verification.md", _build_verification_report())
    _write_text(package_dir / "reports" / "cross_validation.md", _build_cross_validation_report())
    _write_text(
        package_dir / "lineage" / "source_refs.yml",
        yaml.safe_dump(_build_lineage(requirement, plan), allow_unicode=True, sort_keys=False),
    )

    # M4b：计算 artifact 哈希（在 decision.yml 写入之前）
    artifact_hashes = compute_artifact_hashes(package_dir)

    # 阶段 2：写 decision 文件（含 artifact 哈希）
    decision = DecisionRecord(
        notes=plan.human_review_points + drafts.pending_items,
        artifact_hashes=artifact_hashes,
    )
    _write_text(package_dir / "decision.md", _build_decision_md(decision, plan, drafts))
    _write_text(
        package_dir / "decision.yml",
        yaml.safe_dump(
            _build_decision_yml(requirement, artifact_hashes=artifact_hashes),
            allow_unicode=True,
            sort_keys=False,
        ),
    )
    _write_text(
        package_dir / "decision_log.yml",
        yaml.safe_dump(
            _build_decision_log_yml(requirement),
            allow_unicode=True,
            sort_keys=False,
        ),
    )

    return ReviewPackageManifest(
        request_id=requirement.request_id,
        package_path=str(package_dir.resolve()),
        files=REQUIRED_FILES,
        pending_items=plan.pending_items + drafts.pending_items,
    )
