"""Memory Harness Step 14：人工批准后的半自动 patch proposal generator。

读取 Step 12 生成的 memory_suggestion_review_*.json，结合人工审批决策文件，
为每个 approved 的 review item 生成 1~3 种 patch proposal 草案。

6 种 patch 类型：
    - memory_rule_patch       → YAML 片段，建议追加到 docs/memory/memory_rules.yml
    - memory_recap_patch      → Markdown 条目，建议追加到 docs/memory/经验复盘.md
    - risk_item_patch         → Markdown 条目，建议追加到 docs/memory/风险清单.md
    - regression_case_patch   → YAML 草案，建议新增或更新 regression eval case
    - test_case_patch         → Python 草案，建议新增 pytest case
    - harness_check_patch     → Python 草案，建议新增 harness/check_*.py

关键边界：
    - 不自动修改 docs/memory/*
    - 不写入 memory_rules.yml
    - 不自动新增 tests / evals / harness/checks
    - 所有 patch write_mode = "proposal_only"
    - 不自动 active / blocking=true
    - 不调用真实 LLM
    - 不读取 *_latest.*
    - 不接入 fast gate / pre-commit
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ═══════════════════════════════════════════════════════════════
# Review action → patch type 映射
# ═══════════════════════════════════════════════════════════════

# 每个 review_action 触发的 patch 类型
ACTION_PATCH_MAP: dict[str, list[str]] = {
    "accept_as_regression_case": [
        "regression_case_patch",
        "test_case_patch",
    ],
    "accept_as_memory_rule_candidate": [
        "memory_rule_patch",
        "memory_recap_patch",
    ],
    "accept_as_risk_item": [
        "risk_item_patch",
        "harness_check_patch",
    ],
    # 以下 action 不生成 patch（等待或拒绝）
    "asset_dependency_wait": [],
    "provider_runtime_noise": [],
    "reject": [],
}

# patch 类型元数据
PATCH_TYPE_META: dict[str, dict[str, str]] = {
    "memory_rule_patch": {
        "label": "记忆规则补丁",
        "description": "建议追加到 docs/memory/memory_rules.yml 的 YAML 片段",
        "target_file": "docs/memory/memory_rules.yml",
        "format": "yaml",
    },
    "memory_recap_patch": {
        "label": "经验复盘补丁",
        "description": "建议追加到 docs/memory/经验复盘.md 的 Markdown 条目",
        "target_file": "docs/memory/经验复盘.md",
        "format": "markdown",
    },
    "risk_item_patch": {
        "label": "风险清单补丁",
        "description": "建议追加到 docs/memory/风险清单.md 的 Markdown 条目",
        "target_file": "docs/memory/风险清单.md",
        "format": "markdown",
    },
    "regression_case_patch": {
        "label": "回归用例补丁",
        "description": "建议新增或更新 evals/regression/ 下的 prompt regression / E2E eval 用例",
        "target_file": "evals/regression/prompt_regression.yml",
        "format": "yaml",
    },
    "test_case_patch": {
        "label": "测试用例补丁",
        "description": "建议新增 pytest case 的 Python 草案",
        "target_file": "tests/（待定）",
        "format": "python",
    },
    "harness_check_patch": {
        "label": "Harness 检查补丁",
        "description": "建议新增 harness/check_*.py 的草案说明",
        "target_file": "harness/checks/（待定）",
        "format": "python",
    },
}


# ═══════════════════════════════════════════════════════════════
# 审批决策文件加载
# ═══════════════════════════════════════════════════════════════


def load_approved_decisions(approved_path: Path | str) -> dict[str, Any]:
    """加载人工审批决策文件。

    支持两种格式：
        1. 简明格式: {"approved_indices": [0, 2, 5], "approved_by": "...", ...}
        2. 详细格式: {"decisions": [{"review_index": 0, "approved": true}, ...]}

    Args:
        approved_path: 审批决策 JSON 文件路径

    Returns:
        标准化后的审批决策字典:
        {
            "approved_indices": set[int],
            "approved_by": str,
            "approved_at": str,
            "decisions_by_index": {int: dict},
        }

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 格式不正确
    """
    path = Path(approved_path)
    if not path.exists():
        raise FileNotFoundError(f"审批决策文件不存在: {approved_path}")

    if "latest" in path.name.lower():
        raise ValueError(f"不允许读取 *_latest.* 文件: {path.name}")

    data = json.loads(path.read_text(encoding="utf-8"))
    approved_indices: set[int] = set()
    decisions_by_index: dict[int, dict[str, Any]] = {}

    if "decisions" in data and isinstance(data["decisions"], list):
        # 详细格式
        for dec in data["decisions"]:
            idx = dec.get("review_index", -1)
            if idx >= 0 and dec.get("approved", False):
                approved_indices.add(idx)
                decisions_by_index[idx] = dec
    elif "approved_indices" in data and isinstance(data["approved_indices"], list):
        # 简明格式
        for idx in data["approved_indices"]:
            if isinstance(idx, int) and idx >= 0:
                approved_indices.add(idx)
                decisions_by_index[idx] = {
                    "review_index": idx,
                    "approved": True,
                    "approved_by": data.get("approved_by", "unknown"),
                    "approved_at": data.get("approved_at", ""),
                    "notes": data.get("notes", ""),
                }
    else:
        raise ValueError(
            "审批决策文件格式不正确。需要 'approved_indices' 列表或 'decisions' 列表。"
        )

    return {
        "approved_indices": approved_indices,
        "approved_by": data.get("approved_by", "unknown"),
        "approved_at": data.get("approved_at", ""),
        "notes": data.get("notes", ""),
        "decisions_by_index": decisions_by_index,
    }


def load_review_report(report_path: Path | str) -> dict[str, Any]:
    """加载 Step 12 审查报告。

    Args:
        report_path: memory_suggestion_review_*.json 文件路径

    Returns:
        审查报告字典

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: latest 文件名或格式不正确
    """
    path = Path(report_path)
    if not path.exists():
        raise FileNotFoundError(f"审查报告文件不存在: {report_path}")

    if "latest" in path.name.lower():
        raise ValueError(f"不允许读取 *_latest.* 文件: {path.name}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if "review_items" not in data:
        raise ValueError("审查报告格式不正确：缺少 review_items 字段")
    return data


# ═══════════════════════════════════════════════════════════════
# Patch 内容生成器
# ═══════════════════════════════════════════════════════════════


def _patch_counter() -> int:
    """简单的自增计数器（模块级）。"""
    if not hasattr(_patch_counter, "_value"):
        _patch_counter._value = 0  # type: ignore[attr-defined]
    _patch_counter._value += 1  # type: ignore[attr-defined]
    return _patch_counter._value  # type: ignore[attr-defined]


def _reset_patch_counter() -> None:
    """重置计数器（测试用）。"""
    _patch_counter._value = 0  # type: ignore[attr-defined]


def build_memory_rule_patch(item: dict[str, Any], patch_id: str) -> dict[str, Any]:
    """为 memory_rule_candidate 生成 YAML 补丁草案。

    status 始终 proposed，blocking 始终 false。
    """
    rule_preview = item.get("suggested_memory_rule_preview", {})
    question_id = item.get("question_id", "unknown")
    failure_type = item.get("failure_type", "unknown")
    root_cause = item.get("root_cause_hint", "")

    # 构造 YAML 片段
    yaml_lines = [
        "# ═══════════════════════════════════════════════════════════",
        f"# Patch Proposal {patch_id}",
        f"# 来源: review item #{item.get('review_index', '?')} ({question_id})",
        f"# 类型: {failure_type}",
        "# ═══════════════════════════════════════════════════════════",
        "# 请人工审查后复制到 docs/memory/memory_rules.yml",
        "",
        f"- rule_id: {_safe_rule_id(question_id, failure_type)}",
        f"  title: \"{rule_preview.get('title', f'{failure_type} 防护规则')}\"",
        f"  severity: {rule_preview.get('severity', 'medium')}",
        "  status: proposed  # ← 始终保持 proposed",
        "  blocking: false   # ← 始终保持 false",
        f"  description: >",
        f"    自动生成自 Step 14 patch proposal。",
        f"    失败类型: {failure_type}。",
        f"    根因: {root_cause}。",
        f"  applies_to:",
        f"    - {failure_type}",
        "  required_checks: []",
        "  required_tests: []",
        "  required_evals: []",
        f"  source_review_item: {question_id}",
        "",
    ]

    return {
        "patch_id": patch_id,
        "patch_type": "memory_rule_patch",
        "target_file": "docs/memory/memory_rules.yml",
        "write_mode": "proposal_only",
        "format": "yaml",
        "content": "\n".join(yaml_lines),
        "source_review_item": f"#{item.get('review_index', '?')} ({question_id})",
        "manual_steps": [
            "审查 YAML 片段内容是否正确",
            "手动复制到 docs/memory/memory_rules.yml 的合适位置",
            "运行 generate_rule_index.py 更新索引",
            "运行 memory registry 测试确保无回归",
        ],
        "safety_notes": [
            "status 必须保持 proposed",
            "blocking 必须保持 false",
            "不要直接复制粘贴——先审查内容是否正确",
        ],
    }


def build_memory_recap_patch(item: dict[str, Any], patch_id: str) -> dict[str, Any]:
    """为 memory_rule_candidate 生成经验复盘 Markdown 条目。"""
    question_id = item.get("question_id", "unknown")
    question = item.get("question", "")
    failure_type = item.get("failure_type", "unknown")
    root_cause = item.get("root_cause_hint", "")
    review_reason = item.get("review_reason", "")

    md_lines = [
        f"### {failure_type}: {question_id}",
        "",
        f"- **日期**: （填写复盘日期）",
        f"- **来源**: review item #{item.get('review_index', '?')} ({question_id})",
        f"- **原始问题**: {question[:200]}",
        f"- **失败类型**: {failure_type}",
        f"- **根因**: {root_cause}",
        f"- **审查结论**: {review_reason}",
        f"- **处置**: （人工填写: 修复 prompt / 修复 validator / 补充 fixture / 其他）",
        f"- **经验**: （人工填写）",
        "",
        f"> 自动生成自 Step 14 patch proposal ({patch_id})。请人工补充经验内容后复制到 docs/memory/经验复盘.md。",
        "",
    ]

    return {
        "patch_id": patch_id,
        "patch_type": "memory_recap_patch",
        "target_file": "docs/memory/经验复盘.md",
        "write_mode": "proposal_only",
        "format": "markdown",
        "content": "\n".join(md_lines),
        "source_review_item": f"#{item.get('review_index', '?')} ({question_id})",
        "manual_steps": [
            "补充日期、处置措施和经验总结",
            "手动复制到 docs/memory/经验复盘.md",
        ],
        "safety_notes": [
            "仅为模板，必须人工补充后才能使用",
        ],
    }


def build_risk_item_patch(item: dict[str, Any], patch_id: str) -> dict[str, Any]:
    """为 risk_item 生成风险清单 Markdown 条目。"""
    risk_preview = item.get("suggested_risk_item_preview", {}) or {}
    question_id = item.get("question_id", "unknown")
    failure_type = item.get("failure_type", "unknown")
    root_cause = item.get("root_cause_hint", "")
    rule_preview = item.get("suggested_memory_rule_preview", {})

    risk_id = risk_preview.get("risk_id", f"RISK_{failure_type}_{question_id}")
    severity = risk_preview.get("severity", rule_preview.get("severity", "high"))

    md_lines = [
        f"### {risk_id}",
        "",
        f"- **风险等级**: {severity}",
        f"- **来源**: review item #{item.get('review_index', '?')} ({question_id})",
        f"- **失败类型**: {failure_type}",
        f"- **描述**: {risk_preview.get('description', root_cause)}",
        f"- **影响范围**: （人工评估）",
        f"- **缓解措施**: （人工填写）",
        f"- **责任人**: {item.get('suggested_owner', '待定')}",
        f"- **状态**: 待处理",
        "",
        f"> 自动生成自 Step 14 patch proposal ({patch_id})。请人工补充后复制到 docs/memory/风险清单.md。",
        "",
    ]

    return {
        "patch_id": patch_id,
        "patch_type": "risk_item_patch",
        "target_file": "docs/memory/风险清单.md",
        "write_mode": "proposal_only",
        "format": "markdown",
        "content": "\n".join(md_lines),
        "source_review_item": f"#{item.get('review_index', '?')} ({question_id})",
        "manual_steps": [
            "评估风险影响范围和缓解措施",
            "手动复制到 docs/memory/风险清单.md",
        ],
        "safety_notes": [
            "高严重性风险项应优先处理",
            "涉及安全边界的风险必须小时内响应",
        ],
    }


def build_regression_case_patch(item: dict[str, Any], patch_id: str) -> dict[str, Any]:
    """为 regression_candidate 生成回归用例 YAML 草案。"""
    reg_preview = item.get("suggested_regression_case_preview", {}) or {}
    question_id = item.get("question_id", "unknown")
    question = item.get("question", "")
    failure_type = item.get("failure_type", "unknown")
    expected_behavior = reg_preview.get("expected_behavior", "correct_behavior")

    yaml_lines = [
        "# ═══════════════════════════════════════════════════════════",
        f"# Patch Proposal {patch_id}",
        f"# 来源: review item #{item.get('review_index', '?')} ({question_id})",
        f"# 建议: 新增到 evals/regression/ 对应文件中",
        "# ═══════════════════════════════════════════════════════════",
        "",
        f"- id: {reg_preview.get('case_id', f'regression_{failure_type}_{question_id}')}",
        f"  question_zh: \"{question[:200]}\"",
        f"  expected_behavior: {expected_behavior}",
        f"  failure_type: {failure_type}",
        f"  notes: \"自动生成自 Step 14 patch proposal。来源: {question_id}。\"",
        "",
    ]

    return {
        "patch_id": patch_id,
        "patch_type": "regression_case_patch",
        "target_file": f"evals/regression/{_regression_file_for(failure_type)}",
        "write_mode": "proposal_only",
        "format": "yaml",
        "content": "\n".join(yaml_lines),
        "source_review_item": f"#{item.get('review_index', '?')} ({question_id})",
        "manual_steps": [
            "审查回归用例的 expected_behavior 是否正确",
            "手动复制到对应 evals/regression/*.yml 文件",
            "运行 prompt regression 验证新用例生效",
        ],
        "safety_notes": [
            "回归用例不应包含真实 API key 或敏感数据",
        ],
    }


def build_test_case_patch(item: dict[str, Any], patch_id: str) -> dict[str, Any]:
    """为 regression_candidate 生成 pytest case 草案。"""
    question_id = item.get("question_id", "unknown")
    failure_type = item.get("failure_type", "unknown")
    root_cause = item.get("root_cause_hint", "")
    rule_preview = item.get("suggested_memory_rule_preview", {})

    test_func_name = f"test_{failure_type}_{_safe_func_name(question_id)}"

    py_lines = [
        "# ═══════════════════════════════════════════════════════════",
        f"# Patch Proposal {patch_id}",
        f"# 来源: review item #{item.get('review_index', '?')} ({question_id})",
        f"# 建议: 新增到 tests/ 对应测试文件中",
        "# ═══════════════════════════════════════════════════════════",
        "",
        f"def {test_func_name}():",
        f"    \"\"\"{failure_type}: {root_cause[:80]}\"\"\"",
        f"    # 自动生成自 Step 14 patch proposal",
        f"    # 来源: {question_id}",
        f"    # 失败类型: {failure_type}",
        f"    #",
        f"    # TODO: 人工编写以下内容——",
        f"    #   1. 构造 MockLLMClient 或 fixture 数据",
        f"    #   2. 调用被测函数/方法",
        f"    #   3. 断言预期行为",
        f"    pass  # TODO: 实现测试逻辑",
        "",
    ]

    return {
        "patch_id": patch_id,
        "patch_type": "test_case_patch",
        "target_file": f"tests/test_{failure_type}.py",
        "write_mode": "proposal_only",
        "format": "python",
        "content": "\n".join(py_lines),
        "source_review_item": f"#{item.get('review_index', '?')} ({question_id})",
        "manual_steps": [
            "编写实际的测试逻辑（构造输入、调用函数、断言结果）",
            "手动复制到 tests/ 目录对应测试文件",
            "运行 pytest 确保新测试通过",
        ],
        "safety_notes": [
            "测试必须是 Mock 模式，不调用真实 LLM",
            "不要包含 API key 或真实凭证",
        ],
    }


def build_harness_check_patch(item: dict[str, Any], patch_id: str) -> dict[str, Any]:
    """为 risk_item（安全相关）生成 harness check 草案。"""
    question_id = item.get("question_id", "unknown")
    failure_type = item.get("failure_type", "unknown")
    root_cause = item.get("root_cause_hint", "")

    check_func_name = f"check_{failure_type}_{_safe_func_name(question_id)}"

    py_lines = [
        "# ═══════════════════════════════════════════════════════════",
        f"# Patch Proposal {patch_id}",
        f"# 来源: review item #{item.get('review_index', '?')} ({question_id})",
        f"# 建议: 新增到 harness/checks/ 对应文件中",
        "# ═══════════════════════════════════════════════════════════",
        "",
        f"def {check_func_name}() -> dict:",
        f"    \"\"\"安全检查: {failure_type}。",
        f"",
        f"    根因: {root_cause}",
        f"    来源: {question_id}",
        f"    \"\"\"",
        f"    # 自动生成自 Step 14 patch proposal",
        f"    # TODO: 人工编写以下内容——",
        f"    #   1. 定义检查逻辑（读取配置/代码/数据）",
        f"    #   2. 发现违规时返回 {{'status': 'FAIL', 'reason': '...'}}",
        f"    #   3. 合规时返回 {{'status': 'PASS'}}",
        f"    return {{",
        f"        'status': 'NOT_IMPLEMENTED',",
        f"        'reason': '检查逻辑待实现',",
        f"        'check_name': '{check_func_name}',",
        f"        'failure_type': '{failure_type}',",
        f"        'source': '{question_id}',",
        f"    }}",
        "",
    ]

    return {
        "patch_id": patch_id,
        "patch_type": "harness_check_patch",
        "target_file": f"harness/checks/check_{failure_type}.py",
        "write_mode": "proposal_only",
        "format": "python",
        "content": "\n".join(py_lines),
        "source_review_item": f"#{item.get('review_index', '?')} ({question_id})",
        "manual_steps": [
            "实现实际的检查逻辑",
            "手动复制到 harness/checks/ 目录",
            "在 harness/run_harness.py 中注册新检查",
            "运行 harness 测试确保新检查正确工作",
        ],
        "safety_notes": [
            "安全检查不能产生误报（false positive）",
            "优先级规则: 安全 > 正确性 > 性能",
        ],
    }


# ═══════════════════════════════════════════════════════════════
# Patch 生成调度
# ═══════════════════════════════════════════════════════════════


# patch 类型 → 构建函数映射
_PATCH_BUILDERS: dict[str, Any] = {
    "memory_rule_patch": build_memory_rule_patch,
    "memory_recap_patch": build_memory_recap_patch,
    "risk_item_patch": build_risk_item_patch,
    "regression_case_patch": build_regression_case_patch,
    "test_case_patch": build_test_case_patch,
    "harness_check_patch": build_harness_check_patch,
}


def generate_patches_for_item(item: dict[str, Any]) -> list[dict[str, Any]]:
    """为单个 approved review item 生成所有适用的 patch proposal。

    Args:
        item: review_item 字典（来自 Step 12 审查报告）

    Returns:
        patch proposal 列表（可能为空，如被 reject 或 noise）
    """
    review_actions = item.get("review_action", [])
    patches: list[dict[str, Any]] = []

    for action in review_actions:
        patch_types = ACTION_PATCH_MAP.get(action, [])
        for pt in patch_types:
            builder = _PATCH_BUILDERS.get(pt)
            if builder is None:
                continue
            patch_id = f"PATCH-{_patch_counter():03d}"
            patch = builder(item, patch_id)
            patches.append(patch)

    return patches


# ═══════════════════════════════════════════════════════════════
# 报告构建
# ═══════════════════════════════════════════════════════════════


def build_patch_proposal_report(
    review_report: dict[str, Any],
    approved_decisions: dict[str, Any],
    source_review_path: str = "",
) -> dict[str, Any]:
    """从审查报告和审批决策生成 patch proposal 报告。

    只处理 approved_indices 中的 review item，未审批的不生成 patch。

    Args:
        review_report: Step 12 审查报告字典
        approved_decisions: load_approved_decisions() 的输出
        source_review_path: 源审查报告文件路径（用于追溯）

    Returns:
        完整 patch proposal 报告字典
    """
    _reset_patch_counter()
    approved_indices = approved_decisions.get("approved_indices", set())
    review_items = review_report.get("review_items", [])
    decisions_by_index = approved_decisions.get("decisions_by_index", {})

    all_patches: list[dict[str, Any]] = []
    # 同时记录 "已审批但跳过" 的 item（如 reject / noise，不在 action_map 中或映射为空）
    skipped_items: list[dict[str, Any]] = []
    # 未在 approved_indices 中的 item（不处理）
    unapproved_items: list[dict[str, Any]] = []

    for item in review_items:
        idx = item.get("review_index", -1)
        if idx in approved_indices:
            patches = generate_patches_for_item(item)
            if patches:
                for p in patches:
                    # 附加审批元数据
                    dec = decisions_by_index.get(idx, {})
                    p["approved_by"] = dec.get("approved_by", approved_decisions.get("approved_by", "unknown"))
                    p["approved_at"] = dec.get("approved_at", approved_decisions.get("approved_at", ""))
                    p["approval_notes"] = dec.get("notes", approved_decisions.get("notes", ""))
                    all_patches.append(p)
            else:
                skipped_items.append({
                    "review_index": idx,
                    "question_id": item.get("question_id", "unknown"),
                    "review_action": item.get("review_action", []),
                    "skip_reason": "review_action 不生成 patch（reject / noise / asset_dependency_wait 等）",
                })
        else:
            unapproved_items.append({
                "review_index": idx,
                "question_id": item.get("question_id", "unknown"),
                "review_action": item.get("review_action", []),
            })

    # 按类型统计
    patch_type_counts: dict[str, int] = {}
    for p in all_patches:
        pt = p["patch_type"]
        patch_type_counts[pt] = patch_type_counts.get(pt, 0) + 1

    return {
        "run_id": _build_run_id(),
        "timestamp": datetime.now(UTC).isoformat(),
        "source_review_report": source_review_path,
        "source_review_run_id": review_report.get("run_id", ""),
        "source_review_timestamp": review_report.get("timestamp", ""),
        "approved_by": approved_decisions.get("approved_by", "unknown"),
        "approved_at": approved_decisions.get("approved_at", ""),
        "approval_notes": approved_decisions.get("notes", ""),
        "summary": {
            "total_review_items": len(review_items),
            "approved_items": len(approved_indices),
            "unapproved_items": len(unapproved_items),
            "approved_but_skipped": len(skipped_items),
            "total_patches": len(all_patches),
            "patch_type_counts": patch_type_counts,
        },
        "patches": all_patches,
        "skipped_items": skipped_items,
        "unapproved_items": unapproved_items,
    }


# ═══════════════════════════════════════════════════════════════
# JSON / Markdown 渲染
# ═══════════════════════════════════════════════════════════════


def render_patch_proposal_json(report: dict[str, Any]) -> dict[str, Any]:
    """构造可 JSON 序列化的 patch proposal 报告。

    Args:
        report: build_patch_proposal_report() 的输出

    Returns:
        纯 dict（仅含 JSON 可序列化类型）
    """
    payload = copy.deepcopy(report)
    payload.setdefault("run_id", _build_run_id())
    payload.setdefault("timestamp", datetime.now(UTC).isoformat())
    payload.setdefault("source_review_report", "")
    payload.setdefault("source_review_run_id", "")
    payload.setdefault("source_review_timestamp", "")
    payload.setdefault("approved_by", "")
    payload.setdefault("approved_at", "")
    payload.setdefault("approval_notes", "")
    payload.setdefault("summary", {})
    payload.setdefault("patches", [])
    payload.setdefault("skipped_items", [])
    payload.setdefault("unapproved_items", [])

    return json.loads(json.dumps(payload, ensure_ascii=False))


def render_patch_proposal_markdown(report: dict[str, Any]) -> str:
    """渲染人工审查用 Markdown 报告。

    Args:
        report: build_patch_proposal_report() 的输出

    Returns:
        Markdown 格式的报告字符串
    """
    payload = render_patch_proposal_json(report)
    summary = payload["summary"]

    lines = [
        "# Memory Patch Proposal Report",
        "",
        "## Summary",
        "",
        f"- run_id: `{payload['run_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- source_review_report: `{payload['source_review_report']}`",
        f"- approved_by: {payload['approved_by']}",
        f"- approved_at: {payload['approved_at']}",
        f"- total_review_items: {summary['total_review_items']}",
        f"- approved_items: {summary['approved_items']}",
        f"- unapproved_items: {summary['unapproved_items']}",
        f"- approved_but_skipped: {summary['approved_but_skipped']}",
        f"- total_patches: {summary['total_patches']}",
        "",
    ]

    # Patch 类型分布
    counts = summary.get("patch_type_counts", {})
    if counts:
        lines.extend([
            "### Patch 类型分布",
            "",
            "| 类型 | 数量 |",
            "|------|------|",
        ])
        for pt, count in sorted(counts.items()):
            meta = PATCH_TYPE_META.get(pt, {})
            label = meta.get("label", pt)
            lines.append(f"| {label} ({pt}) | {count} |")
        lines.append("")

    # 源审查报告信息
    lines.extend([
        "## Source Review Report",
        "",
        f"- source_review_run_id: `{payload.get('source_review_run_id', '')}`",
        f"- source_review_timestamp: `{payload.get('source_review_timestamp', '')}`",
        "",
    ])

    # 已审批 items
    lines.extend([
        "## Approved Items",
        "",
        f"共 {summary['approved_items']} 个 item 被审批通过。",
        "",
    ])
    patches = payload["patches"]
    approved_ids = sorted(set(p.get("source_review_item", "") for p in patches))
    for sid in approved_ids:
        lines.append(f"- {sid}")
    lines.append("")

    # 按类型分组渲染 patches
    patch_groups: dict[str, list[dict[str, Any]]] = {}
    for p in patches:
        pt = p["patch_type"]
        patch_groups.setdefault(pt, []).append(p)

    section_map = {
        "memory_rule_patch": "Proposed memory_rules.yml Patches",
        "memory_recap_patch": "Proposed 经验复盘.md Entries",
        "risk_item_patch": "Proposed 风险清单.md Entries",
        "regression_case_patch": "Proposed Regression / Eval Cases",
        "test_case_patch": "Proposed Pytest Cases",
        "harness_check_patch": "Proposed Harness Checks",
    }

    for pt, title in section_map.items():
        lines.extend(_render_patch_group(title, patch_groups.get(pt, [])))

    # Skipped items
    skipped = payload.get("skipped_items", [])
    if skipped:
        lines.extend([
            "## Approved but Skipped (No Patch Generated)",
            "",
            "以下 item 已审批但其 review_action 不生成 patch（如 reject / noise / asset_dependency_wait）：",
            "",
            "| review_index | question_id | review_action | skip_reason |",
            "| --- | --- | --- | --- |",
        ])
        for s in skipped:
            lines.append(
                f"| {s['review_index']} "
                f"| {_escape_md(s['question_id'])} "
                f"| {', '.join(s['review_action'])} "
                f"| {_escape_md(s.get('skip_reason', ''))} |"
            )
        lines.append("")

    # Unapproved items
    unapproved = payload.get("unapproved_items", [])
    if unapproved:
        lines.extend([
            "## Unapproved Items (Not Processed)",
            "",
            "以下 item 未出现在 approved_indices 中，本轮不生成 patch：",
            "",
            "| review_index | question_id | review_action |",
            "| --- | --- | --- |",
        ])
        for u in unapproved:
            lines.append(
                f"| {u['review_index']} "
                f"| {_escape_md(u['question_id'])} "
                f"| {', '.join(u['review_action'])} |"
            )
        lines.append("")

    # Manual application steps
    lines.extend([
        "## Manual Application Steps",
        "",
        "所有 patch 均为 proposal_only 模式，须按以下步骤手动应用：",
        "",
        "1. 逐条审查每个 patch 的 `content` 字段",
        "2. 按 `manual_steps` 指示操作",
        "3. 按 `safety_notes` 确认安全边界",
        "4. 手动复制到对应目标文件",
        "5. 运行相关测试套件验证",
        "6. 提交 PR 并标注关联的 review report",
        "",
    ])

    # Safety boundaries
    lines.extend([
        "## Safety Boundaries",
        "",
        "- 所有 memory_rule_patch 的 status 均为 `proposed`",
        "- 所有 memory_rule_patch 的 blocking 均为 `false`",
        "- 不自动修改 `docs/memory/*`",
        "- 不自动写入 `memory_rules.yml`",
        "- 不自动新增 `tests/`",
        "- 不自动新增 `evals/`",
        "- 不自动新增 `harness/checks/`",
        "- 不自动运行 `generate_rule_index.py`",
        "- 不接入 fast gate / pre-commit",
        "",
    ])

    # Footer
    lines.extend([
        "## Not Applied Automatically",
        "",
        "> ⚠️ **重要声明**",
        "> - 本报告由 `harness/memory_patch_proposals.py` 自动生成。",
        "> - **所有 patch 均未自动应用到任何目标文件。**",
        "> - 每个 patch 的 `write_mode` 均为 `proposal_only`。",
        "> - 必须经人工逐条审查后手动应用。",
        "> - 不修改 `docs/memory/*`、不写 `memory_rules.yml`、不新增 tests/evals/checks。",
        "",
    ])

    return "\n".join(lines)


def _render_patch_group(title: str, patches: list[dict[str, Any]]) -> list[str]:
    """渲染一组同类型 patch。"""
    lines: list[str] = []
    if not patches:
        return lines

    lines.extend([f"## {title}", ""])
    for p in patches:
        lines.extend([
            f"### {p['patch_id']}: {p.get('source_review_item', '')}",
            "",
            f"- **类型**: {p['patch_type']}",
            f"- **目标文件**: `{p['target_file']}`",
            f"- **写入模式**: `{p['write_mode']}`",
            f"- **审批人**: {p.get('approved_by', 'unknown')}",
            "",
            "**内容预览:**",
            "",
            "```" + (p.get("format", "")),
            p["content"],
            "```",
            "",
            "**手动步骤:**",
            "",
        ])
        for step in p.get("manual_steps", []):
            lines.append(f"- {step}")
        lines.append("")

        if p.get("safety_notes"):
            lines.append("**安全提示:**")
            lines.append("")
            for note in p["safety_notes"]:
                lines.append(f"- ⚠️ {note}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return lines


# ═══════════════════════════════════════════════════════════════
# 快照写入
# ═══════════════════════════════════════════════════════════════


def write_patch_proposal_snapshot(
    report: dict[str, Any],
    output_dir: Path | str,
) -> dict[str, Path]:
    """写入带 timestamp 的 patch proposal 快照，不生成 latest 文件。

    Args:
        report: build_patch_proposal_report() 的输出
        output_dir: 输出目录路径

    Returns:
        {"json": Path, "markdown": Path}
    """
    payload = render_patch_proposal_json(report)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    timestamp = _safe_timestamp(payload["timestamp"])
    json_path = output / f"memory_patch_proposal_{timestamp}.json"
    markdown_path = output / f"memory_patch_proposal_{timestamp}.md"

    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_patch_proposal_markdown(report),
        encoding="utf-8",
    )
    return {"json": json_path, "markdown": markdown_path}


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _build_run_id() -> str:
    """构造唯一的 run_id。"""
    return "patch-proposal-" + _safe_timestamp(datetime.now(UTC).isoformat())


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


def _safe_rule_id(question_id: str, failure_type: str) -> str:
    """生成安全的 rule_id。"""
    clean = question_id.replace("-", "_").replace(".", "_").replace(" ", "_")
    return f"rule_{failure_type}_{clean}"[:80]


def _safe_func_name(question_id: str) -> str:
    """生成安全的函数名片段。"""
    return question_id.replace("-", "_").replace(".", "_").replace(" ", "_").lower()[:40]


def _regression_file_for(failure_type: str) -> str:
    """根据失败类型推断回归文件。"""
    if "safety" in failure_type or "refusal" in failure_type:
        return "safety_regression.yml"
    if "clarification" in failure_type:
        return "clarification_regression.yml"
    return "prompt_regression.yml"
