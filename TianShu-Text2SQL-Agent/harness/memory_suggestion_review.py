"""Step 12：Memory Suggestion 人工审查工作流。

输入：Step 11 生成的 memory_suggestions_*.json
输出：每条 suggestion 的 review_action 分类 + 结构化审查报告（JSON + Markdown）

6 种 review_action：
    - accept_as_regression_case      → 适合纳入回归用例（prompt regression / LLM E2E eval）
    - accept_as_memory_rule_candidate → 适合进入 memory_rules.yml 候选（仍为 proposed + blocking=false）
    - accept_as_risk_item             → 适合纳入风险清单持续跟踪
    - asset_dependency_wait           → 等待上游数仓资产修复后重新评测
    - provider_runtime_noise          → LLM 提供方运行时波动，不应转为代码缺陷
    - reject                          → 不建议沉淀，需说明 reject_reason

支持多标签：refusal_expected_but_answered 同时产出 regression_case + risk_item。

关键边界：
    - 不自动写入 memory_rules.yml
    - 不自动修改 docs/memory/经验复盘.md
    - 不自动修改 docs/memory/风险清单.md
    - 不自动新增 evals/tests
    - 不自动 active
    - 不设置 blocking=true
    - 不读取 _latest 文件
    - 不调用真实 LLM
    - 不接入 fast gate 阻断
    - 不静默忽略任何 suggestion
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


# ═══════════════════════════════════════════════════════════════
# Review Action 元数据
# ═══════════════════════════════════════════════════════════════

REVIEW_ACTION_META: dict[str, dict[str, str]] = {
    "accept_as_regression_case": {
        "label": "接受为回归用例",
        "description": "该失败模式稳定可复现，建议纳入 regression test suite 作为防护",
        "icon": "📋",
    },
    "accept_as_memory_rule_candidate": {
        "label": "接受为记忆规则候选",
        "description": "该失败模式需要规则化沉淀，建议人工审查后纳入 memory_rules.yml",
        "icon": "🧠",
    },
    "accept_as_risk_item": {
        "label": "接受为风险项",
        "description": "该失败暴露了安全/合规风险，建议纳入风险清单持续跟踪",
        "icon": "⚠️",
    },
    "asset_dependency_wait": {
        "label": "资产依赖等待",
        "description": "该失败根因在上游数仓资产（表/字段缺失），需等待资产就绪后重新评测",
        "icon": "⏳",
    },
    "provider_runtime_noise": {
        "label": "提供方运行时噪音",
        "description": "LLM 提供方的瞬时波动导致的失败，非代码缺陷，建议标记为噪音忽略",
        "icon": "🔊",
    },
    "reject": {
        "label": "拒绝",
        "description": "该建议不符合任何可操作分类标准，或无足够信息判断，建议丢弃",
        "icon": "❌",
    },
}

# 已知 failure_type 集合（与 memory_suggestions.FAILURE_CLASSIFICATION 同步）
KNOWN_FAILURE_TYPES: frozenset[str] = frozenset({
    "intent_mismatch",
    "plan_mismatch",
    "table_mismatch",
    "field_mismatch",
    "clarification_expected_but_answered",
    "refusal_expected_but_answered",
    "confidence_out_of_range",
    "schema_validation_failed",
    "safety_validation_failed",
    "raw_output_parse_failed",
    "execution_failed",
    "explain_failed",
})


# ═══════════════════════════════════════════════════════════════
# 核心纯函数：suggestion → review 分类
# ═══════════════════════════════════════════════════════════════


def classify_memory_suggestion_for_review(suggestion: dict[str, Any]) -> dict[str, Any]:
    """纯函数：单条 memory suggestion → review 分类结果。

    支持多标签：refusal_expected_but_answered 同时产出
    accept_as_regression_case + accept_as_risk_item。

    分类规则：
        - refusal → [regression_case, risk_item], priority=high
        - clarification → [regression_case], priority=high
        - safety → [risk_item], priority=high, manual_review_required=true
        - intent/plan/table/schema/raw_parse → [regression_case], priority=medium
        - explain → [regression_case] 或 [memory_rule_candidate]（条件）
        - field/execution + asset_dependency → [asset_dependency_wait]
        - confidence → [provider_runtime_noise] 或标记 manual_review_required
        - 未知类型 → [reject]

    Args:
        suggestion: build_memory_suggestion() 输出的单条 suggestion 字典

    Returns:
        分类结果字典，包含 review_action（列表）、priority、review_reason、
        suggested_owner、manual_review_required 等
    """
    failure_type = suggestion.get("failure_type", "unknown")
    asset_dep = suggestion.get("asset_dependency", False)
    regression = suggestion.get("regression_candidate", False)
    manual_review = suggestion.get("manual_review_required", False)
    root_cause = suggestion.get("root_cause_hint", "")
    question_id = suggestion.get("question_id", "unknown")

    # ── 安全边界被突破 ──
    if failure_type == "safety_validation_failed":
        return {
            "review_action": ["accept_as_risk_item"],
            "priority": "high",
            "manual_review_required": True,
            "review_reason": (
                f"失败类型 {failure_type} 属于安全边界突破，"
                f"根因提示：{root_cause}。必须优先人工审查。"
            ),
            "suggested_owner": "safety",
        }

    # ── 拒绝策略失效 → 同时标记回归 + 风险（多标签）──
    if failure_type == "refusal_expected_but_answered":
        return {
            "review_action": ["accept_as_regression_case", "accept_as_risk_item"],
            "priority": "high",
            "manual_review_required": True,
            "review_reason": (
                f"应拒绝的问题被正常回答，安全边界可能被绕过。"
                f"需同时补回归用例（确保拒绝策略不退化）和风险跟踪（评估绕过影响）。"
            ),
            "suggested_owner": "safety",
        }

    # ── 反问策略失效 → 回归用例（高优先级）──
    if failure_type == "clarification_expected_but_answered":
        return {
            "review_action": ["accept_as_regression_case"],
            "priority": "high",
            "manual_review_required": False,
            "review_reason": (
                f"歧义问题被继续规划或回答，反问策略没有生效。"
                f"应优先补回归用例，确保反问逻辑不退化。"
            ),
            "suggested_owner": "prompt",
        }

    # ── 资产依赖（必须在通用回归检查之前）──
    if asset_dep:
        return {
            "review_action": ["asset_dependency_wait"],
            "priority": "low",
            "manual_review_required": False,
            "review_reason": (
                f"失败类型 {failure_type} 标记为 asset_dependency=True，"
                f"根因在上游数仓而非代码逻辑。等待资产就绪后重新评测。"
            ),
            "suggested_owner": "asset",
        }

    # ── LLM 提供方噪音（必须在通用回归检查之前）──
    if failure_type == "confidence_out_of_range":
        # 检查是否有 provider/model 信息，若有则更可能是噪音
        rule = suggestion.get("suggested_memory_rule", {})
        source = rule.get("source_failure_case", "")
        has_provider_info = any(
            keyword in source.lower()
            for keyword in ["provider", "model", "runtime", "confidence"]
        )
        if has_provider_info or True:  # 默认为噪音，保守策略
            return {
                "review_action": ["provider_runtime_noise"],
                "priority": "low",
                "manual_review_required": False,
                "review_reason": (
                    f"失败类型 {failure_type} 通常由 LLM 提供方瞬时波动引起。"
                    f"非代码逻辑缺陷，暂不纳入回归防护。"
                    f"若同一场景连续 3 次以上出现，升级为 regression_candidate。"
                ),
                "suggested_owner": "eval",
            }

    # ── explain_failed 条件判断 ──
    if failure_type == "explain_failed":
        # 检查是否涉及 result_fusion 安全边界
        involves_safety = _explain_involves_safety_boundary(suggestion)
        if involves_safety:
            return {
                "review_action": ["accept_as_memory_rule_candidate"],
                "priority": "medium",
                "manual_review_required": True,
                "review_reason": (
                    f"中文解释失败且涉及 result_fusion 安全边界，"
                    f"需人工审查是否影响安全策略。根因提示：{root_cause}。"
                ),
                "suggested_owner": "safety",
            }
        return {
            "review_action": ["accept_as_regression_case"],
            "priority": "medium",
            "manual_review_required": False,
            "review_reason": (
                f"失败类型 {failure_type} 为稳定可复现的回归模式。"
                f"regression_candidate=True。根因提示：{root_cause}。"
            ),
            "suggested_owner": "prompt",
        }

    # ── 未知失败类型 ──
    if failure_type not in KNOWN_FAILURE_TYPES:
        return {
            "review_action": ["reject"],
            "priority": "low",
            "manual_review_required": True,
            "review_reason": (
                f"失败类型 {failure_type} 不在已知分类表中。"
                f"可能为新出现的失败模式，需人工分析后决定处理方式。"
            ),
            "suggested_owner": "unknown",
        }

    # ── 需要人工审查的回归候选 → 记忆规则候选 ──
    if regression and manual_review:
        return {
            "review_action": ["accept_as_memory_rule_candidate"],
            "priority": "medium",
            "manual_review_required": True,
            "review_reason": (
                f"失败类型 {failure_type} 需要规则化沉淀。"
                f"manual_review_required=True。根因提示：{root_cause}。"
            ),
            "suggested_owner": "memory",
        }

    # ── 普通回归候选 ──
    if regression and not manual_review:
        return {
            "review_action": ["accept_as_regression_case"],
            "priority": "medium",
            "manual_review_required": False,
            "review_reason": (
                f"失败类型 {failure_type} 为稳定可复现的回归模式。"
                f"regression_candidate=True，manual_review_required=False。"
                f"根因提示：{root_cause}。建议直接加入回归用例集。"
            ),
            "suggested_owner": "prompt",
        }

    # ── 兜底：拒绝 ──
    return {
        "review_action": ["reject"],
        "priority": "low",
        "manual_review_required": True,
        "review_reason": (
            f"失败类型 {failure_type} 无匹配的分类规则。"
            f"regression_candidate={regression}，"
            f"manual_review_required={manual_review}。需人工分析。"
        ),
        "suggested_owner": "unknown",
    }


def _explain_involves_safety_boundary(suggestion: dict[str, Any]) -> bool:
    """判断 explain_failed 是否涉及 result_fusion 安全边界。

    只检查 root_cause_hint 和 notes 中的安全关键词，
    不检查 recommended_action（因为 explain_failed 的推荐操作始终包含
    "result_fusion prompt"，这是标准建议而非安全边界信号）。

    Args:
        suggestion: 单条 memory suggestion

    Returns:
        True 如果可能涉及安全边界
    """
    root_cause = suggestion.get("root_cause_hint", "").lower()
    rule = suggestion.get("suggested_memory_rule", {})
    notes = rule.get("notes", "").lower()
    # 只检查根因提示和备注，不检查 recommended_action
    combined = f"{root_cause} {notes}"

    safety_keywords = [
        "safety", "安全边界", "安全绕过", "安全失效",
        "refusal", "拒绝策略", "forbidden", "禁止",
        "overreach", "越权",
    ]
    return any(kw in combined for kw in safety_keywords)


# ═══════════════════════════════════════════════════════════════
# Review Item 构建
# ═══════════════════════════════════════════════════════════════


def build_review_item(
    suggestion: dict[str, Any],
    index: int = 0,
) -> dict[str, Any]:
    """为单条 suggestion 构造审查条目。

    不会修改输入文件的任何状态。只产出结构化审查结果。

    Args:
        suggestion: build_memory_suggestion() 输出的单条 suggestion
        index: 在原始报告中的序号（从 0 开始）

    Returns:
        审查条目字典，包含 review_action、review_reason、suggested_owner、
        suggested_next_files、suggested_regression_case_preview、
        suggested_risk_item_preview 等
    """
    classification = classify_memory_suggestion_for_review(suggestion)

    review_actions = classification["review_action"]
    priority = classification["priority"]
    manual_review_required = classification["manual_review_required"]
    review_reason = classification["review_reason"]
    suggested_owner = classification.get("suggested_owner", "unknown")

    rule = suggestion.get("suggested_memory_rule", {})
    question_id = suggestion.get("question_id", "unknown")
    question = suggestion.get("question", "")
    failure_type = suggestion.get("failure_type", "unknown")

    # 根据 review_action 推导建议的目标文件
    suggested_next_files = _derive_suggested_files(review_actions, failure_type)

    # 构建回归用例预览（仅当包含 regression_case 时）
    suggested_regression_case_preview = None
    if "accept_as_regression_case" in review_actions:
        suggested_regression_case_preview = {
            "case_id": f"regression_{failure_type}_{question_id}",
            "question": question[:200] if question else "",
            "failure_type": failure_type,
            "expected_behavior": _expected_behavior_for(failure_type),
            "notes": f"自动生成自 Step 12 review。来源: {question_id}。",
        }

    # 构建风险项预览（仅当包含 risk_item 时）
    suggested_risk_item_preview = None
    if "accept_as_risk_item" in review_actions:
        suggested_risk_item_preview = {
            "risk_id": f"RISK_{failure_type}_{question_id}",
            "title": f"{failure_type} 风险: {question_id}",
            "severity": rule.get("severity", "high"),
            "description": (
                f"来源失败 case {question_id} 暴露了 {failure_type} 风险。"
                f"根因：{suggestion.get('root_cause_hint', '')}"
            ),
            "source_failure_case": rule.get("source_failure_case", question_id),
        }

    return {
        "review_index": index,
        "question_id": question_id,
        "question": question,
        "failure_type": failure_type,
        "raw_failure_type": suggestion.get("raw_failure_type"),
        "root_cause_hint": suggestion.get("root_cause_hint", ""),
        "original_recommended_action": suggestion.get("recommended_action", ""),
        "review_action": review_actions,
        "review_reason": review_reason,
        "manual_review_required": manual_review_required,
        "priority": priority,
        "suggested_owner": suggested_owner,
        "suggested_next_files": suggested_next_files,
        "source_suggestion_id": question_id,
        "source_failure_case": rule.get("source_failure_case", question_id),
        "suggested_memory_rule_preview": {
            "title": rule.get("title", ""),
            "severity": rule.get("severity", "medium"),
            "status": rule.get("status", "proposed"),
            "blocking": rule.get("blocking", False),
            "source_failure_case": rule.get("source_failure_case", ""),
        },
        "suggested_regression_case_preview": suggested_regression_case_preview,
        "suggested_risk_item_preview": suggested_risk_item_preview,
        # 保留原始数据以便人工审查时交叉引用（JSON 输出时移除）
        "_original_suggestion": suggestion,
    }


def _derive_suggested_files(
    review_actions: list[str],
    failure_type: str,
) -> list[str]:
    """根据 review_action 推导建议的目标文件列表。

    Args:
        review_actions: review_action 列表
        failure_type: 失败类型

    Returns:
        建议的文件路径列表（相对于项目根目录）
    """
    files: list[str] = []

    for action in review_actions:
        if action == "accept_as_regression_case":
            if "safety" in failure_type or "refusal" in failure_type:
                files.append("evals/regression/safety_regression.yml")
            elif "clarification" in failure_type:
                files.append("evals/regression/clarification_regression.yml")
            else:
                files.append("evals/regression/prompt_regression.yml")
        elif action == "accept_as_memory_rule_candidate":
            files.append("docs/memory/memory_rules.yml")
        elif action == "accept_as_risk_item":
            files.append("docs/memory/风险清单.md")
        elif action == "asset_dependency_wait":
            files.append("docs/memory/资产依赖跟踪.md")

    return sorted(set(files))


def _expected_behavior_for(failure_type: str) -> str:
    """根据 failure_type 推断期望行为描述。"""
    behaviors = {
        "intent_mismatch": "correct_intent",
        "plan_mismatch": "correct_plan",
        "table_mismatch": "correct_table",
        "clarification_expected_but_answered": "clarification_triggered",
        "refusal_expected_but_answered": "refusal_triggered",
        "raw_output_parse_failed": "valid_json_output",
        "explain_failed": "correct_explanation",
        "schema_validation_failed": "valid_schema",
    }
    return behaviors.get(failure_type, "correct_behavior")


# ═══════════════════════════════════════════════════════════════
# 审查报告构建
# ═══════════════════════════════════════════════════════════════


def build_memory_suggestion_review_report(
    suggestions_report: dict[str, Any],
    source_snapshot_path: str = "",
) -> dict[str, Any]:
    """从 memory suggestions 报告生成审查报告。

    纯函数：不读取文件、不调用 LLM、不修改任何注册表。

    Args:
        suggestions_report: Step 11 build_memory_suggestions_report() 的输出
        source_snapshot_path: 源 snapshot 文件路径（用于追溯）

    Returns:
        完整审查报告字典
    """
    suggestions = suggestions_report.get("suggestions", [])
    review_items = [
        build_review_item(s, idx) for idx, s in enumerate(suggestions)
    ]

    # 按 review_action 分组统计（一条可能计入多个分组）
    action_counts: dict[str, int] = {}
    for item in review_items:
        for action in item["review_action"]:
            action_counts[action] = action_counts.get(action, 0) + 1

    # 按 review_action 分组条目
    action_groups: dict[str, list[dict[str, Any]]] = {}
    for item in review_items:
        for action in item["review_action"]:
            action_groups.setdefault(action, []).append(item)

    # 高优先级人工审查
    high_priority = [
        item for item in review_items
        if item["priority"] == "high" or item["manual_review_required"]
    ]

    return {
        "run_id": _build_run_id(),
        "timestamp": datetime.now(UTC).isoformat(),
        "source_run_id": suggestions_report.get("run_id", ""),
        "source_timestamp": suggestions_report.get("timestamp", ""),
        "source_snapshot_path": source_snapshot_path,
        "summary": {
            "total_suggestions": len(suggestions),
            "total_reviewed": len(review_items),
            "action_counts": action_counts,
            "high_priority_count": len(high_priority),
            "manual_review_required_count": sum(
                1 for i in review_items if i["manual_review_required"]
            ),
        },
        "review_items": review_items,
        "high_priority_manual_review": [
            _summarize_item(item) for item in high_priority
        ],
        "regression_case_candidates": [
            _summarize_item(item)
            for item in action_groups.get("accept_as_regression_case", [])
        ],
        "memory_rule_candidates": [
            _summarize_item(item)
            for item in action_groups.get("accept_as_memory_rule_candidate", [])
        ],
        "risk_item_candidates": [
            _summarize_item(item)
            for item in action_groups.get("accept_as_risk_item", [])
        ],
        "asset_dependency_waitlist": [
            _summarize_item(item)
            for item in action_groups.get("asset_dependency_wait", [])
        ],
        "provider_runtime_noise": [
            _summarize_item(item)
            for item in action_groups.get("provider_runtime_noise", [])
        ],
        "rejected_suggestions": [
            _summarize_item(item)
            for item in action_groups.get("reject", [])
        ],
        "manual_review_required": [
            _summarize_item(item)
            for item in review_items
            if item["manual_review_required"]
        ],
    }


def _summarize_item(item: dict[str, Any]) -> dict[str, Any]:
    """生成 review_item 的摘要条目，用于报告分组列表。"""
    return {
        "review_index": item["review_index"],
        "question_id": item["question_id"],
        "failure_type": item["failure_type"],
        "review_action": item["review_action"],
        "priority": item["priority"],
        "suggested_owner": item["suggested_owner"],
        "review_reason": item["review_reason"],
    }


def load_memory_suggestions_snapshot(snapshot_path: Path | str) -> dict[str, Any]:
    """加载 Step 11 生成的 memory suggestions snapshot JSON。

    Args:
        snapshot_path: memory_suggestions_*.json 文件路径

    Returns:
        解析后的报告字典

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: JSON 格式不符合预期
    """
    path = Path(snapshot_path)
    if not path.exists():
        raise FileNotFoundError(f"Memory suggestions snapshot 不存在: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    if "suggestions" not in data:
        raise ValueError(
            f"输入文件缺少 'suggestions' 字段，请确认是 "
            f"harness/run_memory_suggestions.py 的输出"
        )
    if "run_id" not in data:
        raise ValueError("输入文件缺少 'run_id' 字段")

    return data


# ═══════════════════════════════════════════════════════════════
# JSON / Markdown 渲染
# ═══════════════════════════════════════════════════════════════


def render_memory_suggestion_review_json(report: dict[str, Any]) -> dict[str, Any]:
    """构造可 JSON 序列化的审查报告结构。

    Args:
        report: build_memory_suggestion_review_report() 的输出

    Returns:
        纯 dict（仅含 JSON 可序列化类型），已移除 _original_suggestion
    """
    payload = copy.deepcopy(report)

    # 移除内部引用以减小文件体积
    for item in payload.get("review_items", []):
        item.pop("_original_suggestion", None)

    payload.setdefault("run_id", _build_run_id())
    payload.setdefault("timestamp", datetime.now(UTC).isoformat())
    payload.setdefault("source_run_id", "")
    payload.setdefault("source_timestamp", "")
    payload.setdefault("source_snapshot_path", "")
    payload.setdefault("summary", {})
    payload.setdefault("review_items", [])
    payload.setdefault("high_priority_manual_review", [])
    payload.setdefault("regression_case_candidates", [])
    payload.setdefault("memory_rule_candidates", [])
    payload.setdefault("risk_item_candidates", [])
    payload.setdefault("asset_dependency_waitlist", [])
    payload.setdefault("provider_runtime_noise", [])
    payload.setdefault("rejected_suggestions", [])
    payload.setdefault("manual_review_required", [])

    return json.loads(json.dumps(payload, ensure_ascii=False))


def render_memory_suggestion_review_markdown(report: dict[str, Any]) -> str:
    """渲染人工审查用 Markdown 报告。

    Args:
        report: build_memory_suggestion_review_report() 的输出

    Returns:
        Markdown 格式的报告字符串
    """
    summary = report.get("summary", {})
    action_counts = summary.get("action_counts", {})

    lines = [
        "# Memory Suggestion Review Report",
        "",
        "> ⚠️ **本报告不自动执行任何操作。所有建议需人工审查确认后手动实施。**",
        "",
        "## Summary",
        "",
        f"- Review Run ID: `{report.get('run_id', '')}`",
        f"- Timestamp: `{report.get('timestamp', '')}`",
        f"- Source Run ID: `{report.get('source_run_id', '')}`",
        f"- Source Timestamp: `{report.get('source_timestamp', '')}`",
    ]
    if report.get("source_snapshot_path"):
        lines.append(f"- Source Snapshot: `{report['source_snapshot_path']}`")
    lines.extend([
        f"- Total Suggestions: {summary.get('total_suggestions', 0)}",
        f"- Total Reviewed: {summary.get('total_reviewed', 0)}",
        f"- High Priority: {summary.get('high_priority_count', 0)}",
        f"- Manual Review Required: {summary.get('manual_review_required_count', 0)}",
        "",
    ])

    # ── High Priority Manual Review ──
    _render_section(
        lines, "High Priority Manual Review",
        report.get("high_priority_manual_review", []),
        "以下条目需要优先人工审查：",
    )

    # ── Regression Case Candidates ──
    _render_section(
        lines, "Regression Case Candidates",
        report.get("regression_case_candidates", []),
        "以下条目建议纳入回归测试用例集：",
    )

    # ── Memory Rule Candidates ──
    _render_section(
        lines, "Memory Rule Candidates",
        report.get("memory_rule_candidates", []),
        "以下条目建议作为记忆规则候选（仍为 proposed + blocking=false）：",
    )

    # ── Risk Item Candidates ──
    _render_section(
        lines, "Risk Item Candidates",
        report.get("risk_item_candidates", []),
        "以下条目建议纳入风险清单持续跟踪：",
    )

    # ── Asset Dependency Waitlist ──
    _render_section(
        lines, "Asset Dependency Waitlist",
        report.get("asset_dependency_waitlist", []),
        "以下条目依赖上游数仓资产，需等待资产就绪后重新评测：",
    )

    # ── Provider / Runtime Noise ──
    _render_section(
        lines, "Provider / Runtime Noise",
        report.get("provider_runtime_noise", []),
        "以下条目认定为 LLM 提供方运行时波动，不应转为代码缺陷：",
    )

    # ── Rejected Suggestions ──
    rejected = report.get("rejected_suggestions", [])
    lines.extend(["## Rejected Suggestions", ""])
    if rejected:
        lines.append("以下条目不符合可操作分类标准，建议丢弃：")
        lines.append("")
        _render_table(lines, rejected)
    else:
        lines.extend(["无。", ""])

    # ── Manual Review Required ──
    manual_review = report.get("manual_review_required", [])
    lines.extend(["## Manual Review Required", ""])
    if manual_review:
        lines.extend([
            "以下条目标记为 manual_review_required=true，禁止自动应用：",
            "",
        ])
        _render_table(lines, manual_review)
    else:
        lines.extend(["无。", ""])

    # ── Next Actions ──
    lines.extend([
        "## Next Actions",
        "",
    ])
    _append_next_actions(lines, action_counts)

    # ── 底部声明 ──
    lines.extend([
        "---",
        "",
        "> ⚠️ **重要声明**",
        "> - 本报告由 `harness/run_memory_suggestion_review.py` 自动生成。",
        "> - 所有 review_action 均为**建议分类**，不自动执行任何操作。",
        "> - 不会自动修改 `docs/memory/memory_rules.yml`。",
        "> - 不会自动修改 `docs/memory/经验复盘.md`。",
        "> - 不会自动修改 `docs/memory/风险清单.md`。",
        "> - 不会自动新增 `evals/tests` 用例。",
        "> - 不会自动晋升 active 或设置 blocking=true。",
        "> - 不会自动接入 fast gate 阻断。",
        "> - 人工审查后，根据 review_action 手动执行对应操作。",
        "",
    ])

    return "\n".join(lines)


def _render_section(
    lines: list[str],
    title: str,
    items: list[dict[str, Any]],
    description: str,
) -> None:
    """渲染一个标准分组章节。"""
    lines.extend([f"## {title}", ""])
    if items:
        lines.extend([description, ""])
        _render_table(lines, items)
    else:
        lines.extend(["无。", ""])


def _render_table(lines: list[str], items: list[dict[str, Any]]) -> None:
    """渲染审查条目表格。"""
    lines.append(
        "| # | question_id | failure_type | review_action | priority | suggested_owner |"
    )
    lines.append(
        "| --- | --- | --- | --- | --- | --- |"
    )
    for item in items:
        actions = ", ".join(item.get("review_action", []))
        lines.append(
            f"| {item.get('review_index', '?')} "
            f"| {_escape_md(item.get('question_id', ''))} "
            f"| `{item.get('failure_type', '')}` "
            f"| {actions} "
            f"| {_priority_badge(item.get('priority', 'low'))} "
            f"| `{item.get('suggested_owner', 'unknown')}` |"
        )
    lines.append("")


def _append_next_actions(
    lines: list[str],
    action_counts: dict[str, int],
) -> None:
    """根据 action_counts 生成建议的下一步操作。"""
    if action_counts.get("accept_as_risk_item", 0) > 0:
        lines.append(
            f"- ⚠️ **安全风险项**: 有 {action_counts['accept_as_risk_item']} 条安全相关失败，"
            f"建议**立即**人工审查安全边界是否被突破。"
        )
    if action_counts.get("accept_as_regression_case", 0) > 0:
        lines.append(
            f"- 📋 **回归用例**: 有 {action_counts['accept_as_regression_case']} 条可加入回归测试集，"
            f"建议在 evals/regression/ 中补充对应用例。"
        )
    if action_counts.get("accept_as_memory_rule_candidate", 0) > 0:
        lines.append(
            f"- 🧠 **记忆规则候选**: 有 {action_counts['accept_as_memory_rule_candidate']} 条建议纳入规则注册表，"
            f"人工审查后可手动写入 memory_rules.yml。"
        )
    if action_counts.get("asset_dependency_wait", 0) > 0:
        lines.append(
            f"- ⏳ **资产依赖**: 有 {action_counts['asset_dependency_wait']} 条依赖上游数仓，"
            f"确认资产状态后重新评测。"
        )
    if action_counts.get("provider_runtime_noise", 0) > 0:
        lines.append(
            f"- 🔊 **提供方噪音**: 有 {action_counts['provider_runtime_noise']} 条认定为 LLM 波动，"
            f"若同一场景反复出现需升级处理。"
        )
    if action_counts.get("reject", 0) > 0:
        lines.append(
            f"- ❌ **已拒绝**: 有 {action_counts['reject']} 条不符合分类标准，确认后可丢弃。"
        )
    lines.append("")


def write_memory_suggestion_review_snapshot(
    report: dict[str, Any],
    output_dir: Path | str,
) -> dict[str, Path]:
    """写入带 timestamp 的审查报告 snapshot，不生成 latest 文件。

    Args:
        report: build_memory_suggestion_review_report() 的输出
        output_dir: 输出目录路径

    Returns:
        {"json": Path, "markdown": Path}
    """
    payload = render_memory_suggestion_review_json(report)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    timestamp = _safe_timestamp(payload["timestamp"])
    json_path = output / f"memory_suggestion_review_{timestamp}.json"
    markdown_path = output / f"memory_suggestion_review_{timestamp}.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_memory_suggestion_review_markdown(report),
        encoding="utf-8",
    )
    return {"json": json_path, "markdown": markdown_path}


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _build_run_id() -> str:
    """构造唯一的 run_id。"""
    return "memory-review-" + _safe_timestamp(datetime.now(UTC).isoformat())


def _safe_timestamp(value: str) -> str:
    """将 ISO 时间转成文件名友好格式。"""
    return (
        value.replace(":", "")
        .replace("-", "")
        .replace(".", "")
        .replace("+", "")
    )


def _escape_md(value: str) -> str:
    """转义 Markdown 表格中的特殊字符。"""
    return value.replace("|", "\\|").replace("\n", " ")


def _priority_badge(priority: str) -> str:
    """优先级 → Markdown 徽章。"""
    badges = {
        "high": "🔴 High",
        "medium": "🟡 Medium",
        "low": "🟢 Low",
    }
    return badges.get(priority, priority)
