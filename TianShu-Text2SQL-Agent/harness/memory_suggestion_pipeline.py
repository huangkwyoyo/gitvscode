"""Memory Harness Step 13：将 memory suggestions + review 集成到双基线失败流程。

当 Runtime LLM Baseline / LLM E2E eval / Prompt regression 出现 failed cases 时，
自动串联 Step 11 → Step 12 生成报告。只生成报告，不写入长期记忆、不阻断、不晋升规则。

关键边界：
    - 只生成 timestamp snapshot，不生成 *_latest.*
    - 不修改 docs/memory/*
    - 不写入 memory_rules.yml
    - 不自动晋升 active / blocking=true
    - 不调用真实 LLM
    - 不接入 fast gate 阻断
    - 不把 provider/runtime 波动反推为 source 代码失败
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ── 内部依赖（纯函数，无副作用） ──────────────────────────────
from harness.memory_suggestions import (  # noqa: E402
    build_memory_suggestions_from_e2e_report,
    build_memory_suggestions_from_prompt_regression,
    build_memory_suggestions_report,
    normalize_failure_type,
    write_memory_suggestions_snapshot,
)
from harness.memory_suggestion_review import (  # noqa: E402
    build_memory_suggestion_review_report,
    write_memory_suggestion_review_snapshot,
)

DEFAULT_SUGGESTIONS_DIR = PROJECT_ROOT / "harness" / "reports" / "memory_suggestions"
DEFAULT_REVIEWS_DIR = PROJECT_ROOT / "harness" / "reports" / "memory_reviews"


# ═══════════════════════════════════════════════════════════════
# 输入格式适配器：将不同来源的失败项统一为 Step 11 要求的格式
# ═══════════════════════════════════════════════════════════════


def _adapt_failed_cases_from_e2e_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    """从 LLM E2E eval JSON 报告中提取失败 case 列表。

    每个 case 至少包含 question_id / question / failure_type，
    缺失字段允许为空，不静默丢弃。
    """
    failed: list[dict[str, Any]] = []
    provider = report.get("provider", "")
    model_name = report.get("model_name", "")
    for case in report.get("cases", []):
        if case.get("passed", True):
            continue
        failure_categories = case.get("failure_categories", [])
        primary_failure = failure_categories[0] if failure_categories else "unknown"
        failed.append({
            "question_id": case.get("case_id") or case.get("id", "unknown"),
            "question": case.get("question_zh") or case.get("question", ""),
            "expected_type": case.get("expected_behavior", ""),
            "actual_type": "",
            "failure_type": primary_failure,
            "failure_categories": failure_categories,
            "failure_reason": ", ".join(failure_categories) if failure_categories else "",
            "expected": "",
            "actual": "",
            "provider": provider,
            "model_name": model_name,
            "stage": "llm_e2e_eval",
            "raw_output_file": "",
            "error": case.get("error"),
        })
    return failed


def _adapt_failed_cases_from_prompt_regression(report: dict[str, Any]) -> list[dict[str, Any]]:
    """从 Prompt Regression JSON 报告中提取失败 case 列表。

    每个 case 至少包含 question_id / question / failure_type，
    缺失字段允许为空，不静默丢弃。
    """
    failed: list[dict[str, Any]] = []
    model_name = report.get("model_name", "")
    for case in report.get("cases", []):
        if case.get("passed", True):
            continue
        error = case.get("error", "")
        failure_type = _infer_prompt_failure_type(case, error)
        failed.append({
            "question_id": case.get("case_id") or case.get("id", "unknown"),
            "question": case.get("task", ""),
            "expected_type": case.get("expected_type", "answer"),
            "actual_type": case.get("actual_type", "unknown"),
            "failure_type": failure_type,
            "failure_categories": [failure_type],
            "failure_reason": error or case.get("failure_reason", ""),
            "expected": case.get("expected"),
            "actual": case.get("actual"),
            "provider": "",
            "model_name": model_name,
            "stage": "prompt_regression",
            "raw_output_file": case.get("raw_output_file", ""),
            "error": error,
        })
    return failed


def _adapt_failed_cases_from_failure_triage(
    triage_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """从 failure_triage items 中提取失败 case 列表。

    用于 dual_baseline 内存中已有的 triage 数据，不重新读取磁盘文件。
    """
    failed: list[dict[str, Any]] = []
    for item in triage_items:
        raw_type = item.get("failure_type", "unknown")
        failure_type = normalize_failure_type(raw_type)
        failed.append({
            "question_id": item.get("case_id", "unknown"),
            "question": item.get("question", ""),
            "expected_type": item.get("expected_behavior", ""),
            "actual_type": "",
            "failure_type": failure_type,
            "failure_categories": item.get("failure_categories", [raw_type]),
            "failure_reason": item.get("root_cause_hint", ""),
            "expected": "",
            "actual": "",
            "provider": "",
            "model_name": "",
            "stage": "runtime_baseline",
            "raw_output_file": "",
        })
    return failed


def _adapt_failed_cases_from_generic_list(
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """从通用失败 case 列表中提取，确保每个 case 至少有必需字段。

    只过滤掉完全无法识别的条目（无 question_id 且无任何标识字段），
    不静默丢弃有效 case。
    """
    failed: list[dict[str, Any]] = []
    for case in cases:
        # 已标记为 passed 的跳过
        if case.get("passed", False):
            continue
        question_id = (
            case.get("question_id")
            or case.get("case_id")
            or case.get("id", "")
        )
        if not question_id:
            # 不静默丢弃：记录为 unknown 并继续
            question_id = "unknown"
        failure_type = case.get("failure_type") or case.get("failure_reason") or "unknown"
        failed.append({
            "question_id": question_id,
            "question": case.get("question") or case.get("question_zh") or "",
            "expected_type": case.get("expected_type") or case.get("expected_behavior", ""),
            "actual_type": case.get("actual_type", ""),
            "failure_type": normalize_failure_type(failure_type),
            "failure_categories": case.get("failure_categories", [failure_type]),
            "failure_reason": case.get("failure_reason", ""),
            "expected": case.get("expected", ""),
            "actual": case.get("actual", ""),
            "provider": case.get("provider", ""),
            "model_name": case.get("model_name", ""),
            "stage": case.get("stage", ""),
            "raw_output_file": case.get("raw_output_file", ""),
        })
    return failed


def _infer_prompt_failure_type(case: dict[str, Any], error: str) -> str:
    """从 prompt regression case 的错误信息推断标准 failure_type。"""
    error_lower = error.lower()
    if "parse" in error_lower or "json" in error_lower or "decode" in error_lower:
        return "raw_output_parse_failed"
    if "schema" in error_lower or "validation" in error_lower:
        return "schema_validation_failed"
    if "safety" in error_lower or "sql" in error_lower or "forbidden" in error_lower:
        return "safety_validation_failed"
    if "confidence" in error_lower:
        return "confidence_out_of_range"
    if "refusal" in error_lower:
        return "refusal_expected_but_answered"
    if "clarification" in error_lower or "ambiguity" in error_lower:
        return "clarification_expected_but_answered"
    task = case.get("task", "").lower()
    if "intent" in task:
        return "intent_mismatch"
    if "plan" in task or "sql_plan" in task:
        return "plan_mismatch"
    return "intent_mismatch"


# ═══════════════════════════════════════════════════════════════
# 核心管道函数
# ═══════════════════════════════════════════════════════════════


def _skipped_result(reason: str) -> dict[str, Any]:
    """构造"跳过"结果。"""
    return {
        "generated": False,
        "failed_cases": 0,
        "suggestions_report": None,
        "review_report": None,
        "warnings": [reason],
        "summary": f"Memory suggestion pipeline skipped: {reason}",
        "error": None,
    }


def _error_result(error_msg: str, warnings: list[str] | None = None) -> dict[str, Any]:
    """构造"错误"结果，不抛异常。"""
    return {
        "generated": False,
        "failed_cases": 0,
        "suggestions_report": None,
        "review_report": None,
        "warnings": (warnings or []) + [error_msg],
        "summary": f"Memory suggestion pipeline failed: {error_msg}",
        "error": error_msg,
    }


def run_pipeline_on_failure_triage(
    failure_triage: dict[str, Any],
    output_root: str | Path = "harness/reports",
) -> dict[str, Any]:
    """从内存中的 failure_triage 结果运行完整管道。

    供 dual_baseline / eval runner 在内存中直接调用，不读取任何磁盘文件。
    只在存在 failed cases 时生成报告；zero failure 时返回 skipped 结果。

    Args:
        failure_triage: load_failure_triage_from_report() 的输出，
            包含 items 列表，每项含 case_id / question / failure_type 等
        output_root: 报告输出根目录

    Returns:
        {
            "generated": bool,
            "failed_cases": int,
            "suggestions_report": {"json": path, "markdown": path} | None,
            "review_report": {"json": path, "markdown": path} | None,
            "warnings": [...],
            "summary": str,
            "error": str | None,
        }
    """
    output_root = Path(output_root)
    triage_items = failure_triage.get("items", [])

    # Zero failure → 不生成报告
    if not triage_items:
        return _skipped_result("no failed cases in failure_triage")

    warnings: list[str] = []
    if failure_triage.get("error"):
        warnings.append(f"failure_triage 包含错误: {failure_triage['error']}")

    try:
        # 适配 triage items → 标准 failed_cases 格式
        failed_cases = _adapt_failed_cases_from_failure_triage(triage_items)
        if not failed_cases:
            return _skipped_result("all triage items filtered out (unexpected)")

        source_run_id = failure_triage.get("run_id", "")
        source = failure_triage.get("source", "runtime_baseline")

        # ── Step 11: 生成 memory suggestions 报告 ──
        suggestions_report = build_memory_suggestions_report(
            failed_cases, source=source, source_run_id=source_run_id,
        )
        suggestions_paths = write_memory_suggestions_snapshot(
            suggestions_report,
            output_root / "memory_suggestions",
        )

        # ── Step 12: 生成 review 报告 ──
        review_report = build_memory_suggestion_review_report(
            suggestions_report,
            source_snapshot_path=str(suggestions_paths["json"]),
        )
        review_paths = write_memory_suggestion_review_snapshot(
            review_report,
            output_root / "memory_reviews",
        )

        return {
            "generated": True,
            "failed_cases": len(failed_cases),
            "suggestions_report": {k: str(v) for k, v in suggestions_paths.items()},
            "review_report": {k: str(v) for k, v in review_paths.items()},
            "warnings": warnings,
            "summary": _build_pipeline_summary(suggestions_report, review_report),
            "error": None,
        }
    except Exception as exc:
        # 管道失败不吞掉原始 baseline failure
        warnings.append(f"pipeline exception: {type(exc).__name__}: {exc}")
        return {
            "generated": False,
            "failed_cases": len(triage_items),
            "suggestions_report": None,
            "review_report": None,
            "warnings": warnings,
            "summary": f"Memory suggestion pipeline 异常: {exc}",
            "error": str(exc),
        }


def generate_memory_reports_for_failed_cases(
    failed_cases_path: str,
    source: str = "runtime_baseline",
    output_root: str = "harness/reports",
) -> dict[str, Any]:
    """从磁盘文件加载失败 case JSON 并运行完整管道。

    这是 Step 13 的主入口函数，支持三种输入格式：
        - runtime_baseline: baseline JSON 中的 failure_triage 或通用失败 case 列表
        - llm_e2e_eval: E2E 评测报告 JSON
        - prompt_regression: Prompt regression 报告 JSON

    只在存在 failed cases 时生成两份 report snapshot；
    zero failure 时不生成空报告。

    Args:
        failed_cases_path: 输入 JSON 文件路径（显式指定，不允许 latest）
        source: 数据来源类型（runtime_baseline / llm_e2e_eval / prompt_regression）
        output_root: 报告输出根目录

    Returns:
        {
            "generated": bool,
            "failed_cases": int,
            "suggestions_report": {"json": path, "markdown": path} | None,
            "review_report": {"json": path, "markdown": path} | None,
            "warnings": [...],
            "summary": str,
            "error": str | None,
        }
    """
    input_path = Path(failed_cases_path).resolve()
    output_root_path = Path(output_root)

    # 拒绝读取 *_latest.* 文件
    if "latest" in input_path.name.lower():
        return _error_result(
            f"不允许读取 *_latest.* 文件: {input_path.name}。请指定显式的 timestamp snapshot。"
        )

    if not input_path.exists():
        return _error_result(f"输入文件不存在: {input_path}")

    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _error_result(f"输入文件 JSON 解析失败: {exc}")

    try:
        # 根据 source 类型适配失败 case 格式
        if source == "llm_e2e_eval":
            failed_cases = _adapt_failed_cases_from_e2e_report(data)
            source_run_id = data.get("run_id", "")
        elif source == "prompt_regression":
            failed_cases = _adapt_failed_cases_from_prompt_regression(data)
            source_run_id = data.get("run_id", "")
        else:
            # runtime_baseline 或通用格式
            # 先判断类型（list 没有 .get 方法，必须优先检查）
            if isinstance(data, list):
                failed_cases = _adapt_failed_cases_from_generic_list(data)
                source_run_id = ""
            elif isinstance(data, dict):
                # 尝试从 failure_triage.items 中提取
                triage = data.get("failure_triage")
                if triage and triage.get("items"):
                    failed_cases = _adapt_failed_cases_from_failure_triage(triage["items"])
                    source_run_id = triage.get("run_id", data.get("run_id", ""))
                else:
                    cases = data.get("cases") or data.get("failed_cases") or []
                    if isinstance(cases, list):
                        failed_cases = _adapt_failed_cases_from_generic_list(cases)
                    else:
                        failed_cases = []
                    source_run_id = data.get("run_id", "")
            else:
                return _error_result("输入 JSON 格式不支持：必须是 list 或 dict")

        # Zero failure → 不生成报告
        if not failed_cases:
            return _skipped_result("输入中没有 failed cases")

        # ── Step 11: 生成 memory suggestions 报告 ──
        suggestions_report = build_memory_suggestions_report(
            failed_cases, source=source, source_run_id=source_run_id,
        )
        suggestions_paths = write_memory_suggestions_snapshot(
            suggestions_report,
            output_root_path / "memory_suggestions",
        )

        # ── Step 12: 生成 review 报告 ──
        review_report = build_memory_suggestion_review_report(
            suggestions_report,
            source_snapshot_path=str(suggestions_paths["json"]),
        )
        review_paths = write_memory_suggestion_review_snapshot(
            review_report,
            output_root_path / "memory_reviews",
        )

        return {
            "generated": True,
            "failed_cases": len(failed_cases),
            "suggestions_report": {k: str(v) for k, v in suggestions_paths.items()},
            "review_report": {k: str(v) for k, v in review_paths.items()},
            "warnings": [],
            "summary": _build_pipeline_summary(suggestions_report, review_report),
            "error": None,
        }
    except Exception as exc:
        return _error_result(f"管道执行异常: {type(exc).__name__}: {exc}")


# ═══════════════════════════════════════════════════════════════
# 摘要渲染
# ═══════════════════════════════════════════════════════════════


def _build_pipeline_summary(
    suggestions_report: dict[str, Any],
    review_report: dict[str, Any],
) -> str:
    """生成管道执行的文本摘要。"""
    s_sum = suggestions_report.get("summary", {})
    r_sum = review_report.get("summary", {})
    action_counts = r_sum.get("action_counts", {})
    lines = [
        "Memory Suggestions:",
        f"- generated: yes",
        f"- failed_cases: {s_sum.get('total_failed_cases', 0)}",
        f"- suggestions: {s_sum.get('suggestions', 0)}",
        f"- suggestions_report: (已生成)",
        f"- review_report: (已生成)",
        f"- regression_candidates: {s_sum.get('regression_candidates', 0)}",
        f"- asset_dependencies: {s_sum.get('asset_dependencies', 0)}",
        f"- manual_review_required: {r_sum.get('manual_review_required_count', 0)}",
        f"- high_priority: {r_sum.get('high_priority_count', 0)}",
    ]
    if action_counts:
        actions_str = ", ".join(f"{k}: {v}" for k, v in sorted(action_counts.items()))
        lines.append(f"- review_actions: {actions_str}")
    return "\n".join(lines)


def render_pipeline_summary_for_baseline(pipeline_result: dict[str, Any]) -> str:
    """为 baseline / eval 输出追加的 Memory Suggestion 摘要段落。

    用于嵌入 Markdown 报告或终端输出中。

    Args:
        pipeline_result: generate_memory_reports_for_failed_cases() 的返回值

    Returns:
        格式化的摘要文本
    """
    if not pipeline_result.get("generated"):
        reason = pipeline_result.get("summary", "未生成")
        return f"\n---\n## Memory Suggestion Pipeline\n\n- 状态: skipped\n- 原因: {reason}\n"

    sr = pipeline_result.get("suggestions_report", {}) or {}
    rr = pipeline_result.get("review_report", {}) or {}
    warnings = pipeline_result.get("warnings", [])

    lines = [
        "",
        "---",
        "",
        "## Memory Suggestion Pipeline (Step 13)",
        "",
        f"- 状态: generated",
        f"- failed_cases: {pipeline_result.get('failed_cases', 0)}",
        f"- suggestions JSON: `{sr.get('json', 'N/A')}`",
        f"- suggestions Markdown: `{sr.get('markdown', 'N/A')}`",
        f"- review JSON: `{rr.get('json', 'N/A')}`",
        f"- review Markdown: `{rr.get('markdown', 'N/A')}`",
    ]
    if warnings:
        lines.append(f"- warnings: {warnings}")
    if pipeline_result.get("error"):
        lines.append(f"- error: {pipeline_result['error']}")
    lines.extend([
        "",
        "> ⚠️ 以上为自动生成的 memory suggestion + review 报告。",
        "> 不会自动修改 `docs/memory/*` 或 `memory_rules.yml`。",
        "> 请人工审查 review report 后决定是否采纳。",
        "",
    ])
    return "\n".join(lines)
