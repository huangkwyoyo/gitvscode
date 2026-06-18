"""Memory Harness Step 15：人工应用 patch proposal 后的 validation workflow。

读取 Step 14 生成的 patch proposal，验证人工落地结果是否合格：
  1. Proposal 基础检查
  2. memory_rules.yml 结构检查
  3. rule index 同步检查
  4. 经验复盘 / 风险清单引用检查
  5. required paths 存在性检查
  6. 测试建议落点检查
  7. Harness 验证命令建议

关键边界：
    - 不自动修改 docs/memory/*
    - 不自动修改 memory_rules.yml
    - 不自动修改 经验复盘.md / 风险清单.md
    - 不自动新增 tests/evals/checks
    - 不自动运行 git commit
    - 不接入 pre-commit / fast gate
    - 不自动晋升 active / blocking=true
    - 不读取 *_latest.*
    - 不调用真实 LLM
    - 不修改业务代码
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 合法的 rule status 枚举
VALID_RULE_STATUSES = frozenset({"proposed", "active", "deprecated", "superseded"})

# rule_id 正则：TA-R + 3 位数字
RULE_ID_PATTERN = r"^TA-R\d{3}$"

# patch_type → target_file 映射
PATCH_TARGET_FILES: dict[str, str] = {
    "memory_rule_patch": "docs/memory/memory_rules.yml",
    "memory_recap_patch": "docs/memory/经验复盘.md",
    "risk_item_patch": "docs/memory/风险清单.md",
    "regression_case_patch": "evals/regression/prompt_regression.yml",
    "test_case_patch": "tests/（待定）",
    "harness_check_patch": "harness/checks/（待定）",
}


# ═══════════════════════════════════════════════════════════════
# 加载与基础校验
# ═══════════════════════════════════════════════════════════════


def load_patch_proposal(proposal_path: str | Path) -> dict[str, Any]:
    """加载并校验 patch proposal JSON 文件。

    Args:
        proposal_path: patch proposal JSON 文件路径

    Returns:
        解析后的 proposal dict

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: JSON 解析失败或格式错误
    """
    path = Path(proposal_path).resolve()

    if "latest" in path.name.lower():
        raise ValueError(
            f"不允许读取 *_latest.* 文件: {path.name}。请指定显式的 timestamp snapshot。"
        )

    if not path.exists():
        raise FileNotFoundError(f"patch proposal 文件不存在: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"patch proposal JSON 解析失败: {exc}") from exc

    patches = data.get("patches", data.get("patch_proposals", []))
    if not isinstance(patches, list):
        raise ValueError("patch proposal 中 patches 不是 list 类型")

    return {"path": str(path), "data": data, "patches": patches}


def _validate_proposal_basics(patches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """基础检查：每个 patch 是否包含必要字段且 write_mode 为 proposal_only。

    Returns:
        validation_items 列表
    """
    items: list[dict[str, Any]] = []

    if not patches:
        items.append({
            "patch_id": "N/A",
            "patch_type": "N/A",
            "target_file": "N/A",
            "status": "warning",
            "message": "proposal 中 patches 为空——这是一个 no-op proposal",
            "manual_action": None,
        })
        return items

    for i, patch in enumerate(patches):
        patch_id = patch.get("patch_id", f"PATCH-{i + 1:03d}")
        patch_type = patch.get("patch_type", "unknown")
        target_file = patch.get("target_file", patch.get("target", "unknown"))
        write_mode = patch.get("write_mode", patch.get("mode", ""))

        # write_mode 必须为 proposal_only
        if write_mode != "proposal_only":
            items.append({
                "patch_id": patch_id,
                "patch_type": patch_type,
                "target_file": target_file,
                "status": "failed",
                "message": f"write_mode 为 '{write_mode}'，必须为 'proposal_only'",
                "manual_action": "修正 patch 的 write_mode 为 proposal_only 后重新运行验证",
            })
        elif not patch_id or patch_id == f"PATCH-{i + 1:03d}":
            # patch_id 缺失或使用默认值
            items.append({
                "patch_id": patch_id,
                "patch_type": patch_type,
                "target_file": target_file,
                "status": "passed",
                "message": "write_mode=proposal_only ✓",
                "manual_action": None,
            })
        else:
            items.append({
                "patch_id": patch_id,
                "patch_type": patch_type,
                "target_file": target_file,
                "status": "passed",
                "message": "patch 基础字段完整，write_mode=proposal_only ✓",
                "manual_action": None,
            })

    return items


# ═══════════════════════════════════════════════════════════════
# memory_rules.yml 校验
# ═══════════════════════════════════════════════════════════════


def _load_memory_rules() -> dict[str, Any] | None:
    """加载 memory_rules.yml，返回 (rules_list, raw_text) 或 None。"""
    rules_path = PROJECT_ROOT / "docs" / "memory" / "memory_rules.yml"
    if not rules_path.exists():
        return None
    try:
        import yaml as _yaml
        raw = rules_path.read_text(encoding="utf-8")
        data = _yaml.safe_load(raw)
        if not isinstance(data, dict):
            return None
        rules_list = data.get("rules", [])
        if not isinstance(rules_list, list):
            return None
        return {"rules": rules_list, "raw": raw, "path": str(rules_path)}
    except Exception:
        return None


def _check_memory_rules(
    patches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """memory_rules.yml 结构校验。

    触发条件：proposal 中包含 memory_rule_patch。
    """
    items: list[dict[str, Any]] = []

    # 检查是否有 memory_rule_patch
    has_memory_rule_patch = any(
        p.get("patch_type") == "memory_rule_patch" for p in patches
    )

    rules_data = _load_memory_rules()

    if has_memory_rule_patch and rules_data is None:
        items.append({
            "patch_id": "ALL-memory_rule",
            "patch_type": "memory_rule_patch",
            "target_file": "docs/memory/memory_rules.yml",
            "status": "failed",
            "message": "proposal 中有 memory_rule_patch 但 docs/memory/memory_rules.yml 不存在或无法解析",
            "manual_action": "创建 docs/memory/memory_rules.yml 并合入 patch proposal 中的 YAML 片段",
        })
        return items

    if not has_memory_rule_patch:
        # 即使没有 memory_rule_patch，也检查 rules 文件的基础健康度
        if rules_data is not None:
            items.append({
                "patch_id": "N/A",
                "patch_type": "memory_rules_file",
                "target_file": "docs/memory/memory_rules.yml",
                "status": "passed",
                "message": (
                    f"memory_rules.yml 存在且可解析"
                    f"（{len(rules_data['rules'])} 条规则）"
                ),
                "manual_action": None,
            })
        return items

    # 逐规则检查
    rules = rules_data["rules"]
    rule_ids_seen: set[str] = set()
    for rule in rules:
        rule_id = rule.get("rule_id", "")

        # rule_id 必须存在且符合 TA-Rxxx
        if not rule_id:
            items.append({
                "patch_id": "N/A",
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "status": "failed",
                "message": "存在缺 rule_id 的规则条目",
                "manual_action": "为每一条规则补充 rule_id（格式 TA-Rxxx）",
            })
            continue

        # rule_id 唯一性
        if rule_id in rule_ids_seen:
            items.append({
                "patch_id": rule_id,
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "status": "failed",
                "message": f"rule_id '{rule_id}' 重复",
                "manual_action": f"确保 rule_id '{rule_id}' 在 memory_rules.yml 中唯一",
            })
        rule_ids_seen.add(rule_id)

        # rule_id 格式
        import re as _re
        if not _re.match(RULE_ID_PATTERN, rule_id):
            items.append({
                "patch_id": rule_id,
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "status": "failed",
                "message": f"rule_id '{rule_id}' 不符合 TA-Rxxx 格式",
                "manual_action": f"修正 rule_id '{rule_id}' 为 TA-Rxxx 格式",
            })

        # status 枚举
        status = rule.get("status", "")
        if status not in VALID_RULE_STATUSES:
            items.append({
                "patch_id": rule_id,
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "status": "failed",
                "message": (
                    f"rule_id '{rule_id}' 的 status '{status}'"
                    f" 不在合法枚举中：{sorted(VALID_RULE_STATUSES)}"
                ),
                "manual_action": f"修正 rule_id '{rule_id}' 的 status",
            })

        # blocking 必须为 bool
        blocking = rule.get("blocking")
        if not isinstance(blocking, bool):
            items.append({
                "patch_id": rule_id,
                "patch_type": "memory_rule_patch",
                "target_file": "docs/memory/memory_rules.yml",
                "status": "failed",
                "message": (
                    f"rule_id '{rule_id}' 的 blocking 字段"
                    f"类型为 {type(blocking).__name__}，必须为 bool"
                ),
                "manual_action": f"修正 rule_id '{rule_id}' 的 blocking 为 true 或 false",
            })

        # active + blocking=true → required_*/tests/evals 闭环
        if status == "active" and blocking is True:
            _check_required_closure(rule_id, rule, items)

        # proposed 规则允许缺 required_* 但需 notes 说明
        if status == "proposed":
            _check_proposed_required(rule_id, rule, items)

    return items


def _check_required_closure(
    rule_id: str, rule: dict[str, Any], items: list[dict[str, Any]],
) -> None:
    """检查 active + blocking=true 规则的 required_* 闭环。"""
    required_checks = rule.get("required_checks", []) or []
    required_tests = rule.get("required_tests", []) or []
    required_evals = rule.get("required_evals", []) or []

    missing = []
    if not required_checks:
        missing.append("required_checks")
    if not required_tests:
        missing.append("required_tests")
    if not required_evals:
        missing.append("required_evals")

    if missing:
        items.append({
            "patch_id": rule_id,
            "patch_type": "memory_rule_patch",
            "target_file": "docs/memory/memory_rules.yml",
            "status": "failed",
            "message": (
                f"active + blocking=true 规则 '{rule_id}' 缺少: {', '.join(missing)}"
            ),
            "manual_action": (
                f"补全 '{rule_id}' 的 {', '.join(missing)} 字段，"
                f"或降级为 proposed + blocking=false"
            ),
        })
    else:
        items.append({
            "patch_id": rule_id,
            "patch_type": "memory_rule_patch",
            "target_file": "docs/memory/memory_rules.yml",
            "status": "passed",
            "message": (
                f"active + blocking=true 规则 '{rule_id}'"
                f" 的 required_*/tests/evals 闭环完整 ✓"
            ),
            "manual_action": None,
        })


def _check_proposed_required(
    rule_id: str, rule: dict[str, Any], items: list[dict[str, Any]],
) -> None:
    """检查 proposed 规则的 required_* 和 notes TODO 标记。"""
    notes = rule.get("notes", "") or ""

    # 检查 required_checks
    required_checks = rule.get("required_checks", []) or []
    for check_path in required_checks:
        full_path = PROJECT_ROOT / check_path
        if not full_path.exists():
            if "TODO" in notes:
                items.append({
                    "patch_id": rule_id,
                    "patch_type": "memory_rule_patch",
                    "target_file": check_path,
                    "status": "warning",
                    "message": (
                        f"'{rule_id}' required_check '{check_path}' 不存在，"
                        f"但 notes 有 TODO 标记"
                    ),
                    "manual_action": "按 TODO 计划补齐检查文件",
                })
            else:
                items.append({
                    "patch_id": rule_id,
                    "patch_type": "memory_rule_patch",
                    "target_file": check_path,
                    "status": "warning",
                    "message": (
                        f"'{rule_id}' required_check '{check_path}' 不存在"
                    ),
                    "manual_action": "补齐检查文件或在 notes 中标注 TODO 及计划",
                })

    # 检查 required_tests
    required_tests = rule.get("required_tests", []) or []
    for test_path in required_tests:
        full_path = PROJECT_ROOT / test_path
        if not full_path.exists():
            if "TODO" in notes:
                items.append({
                    "patch_id": rule_id,
                    "patch_type": "memory_rule_patch",
                    "target_file": test_path,
                    "status": "warning",
                    "message": (
                        f"'{rule_id}' required_test '{test_path}' 不存在，"
                        f"但 notes 有 TODO 标记"
                    ),
                    "manual_action": "按 TODO 计划补齐测试文件",
                })
            else:
                items.append({
                    "patch_id": rule_id,
                    "patch_type": "memory_rule_patch",
                    "target_file": test_path,
                    "status": "warning",
                    "message": (
                        f"'{rule_id}' required_test '{test_path}' 不存在"
                    ),
                    "manual_action": "补齐测试文件或在 notes 中标注 TODO 及计划",
                })

    # 检查 required_evals
    required_evals = rule.get("required_evals", []) or []
    for eval_path in required_evals:
        full_path = PROJECT_ROOT / eval_path
        if not full_path.exists():
            if "TODO" in notes:
                items.append({
                    "patch_id": rule_id,
                    "patch_type": "memory_rule_patch",
                    "target_file": eval_path,
                    "status": "warning",
                    "message": (
                        f"'{rule_id}' required_eval '{eval_path}' 不存在，"
                        f"但 notes 有 TODO 标记"
                    ),
                    "manual_action": "按 TODO 计划补齐 eval 文件",
                })
            else:
                items.append({
                    "patch_id": rule_id,
                    "patch_type": "memory_rule_patch",
                    "target_file": eval_path,
                    "status": "warning",
                    "message": (
                        f"'{rule_id}' required_eval '{eval_path}' 不存在"
                    ),
                    "manual_action": "补齐 eval 文件或在 notes 中标注 TODO 及计划",
                })


# ═══════════════════════════════════════════════════════════════
# Rule Index 同步检查
# ═══════════════════════════════════════════════════════════════


def _check_rule_index() -> list[dict[str, Any]]:
    """检查 规则来源索引.md 是否与 memory_rules.yml 同步。"""
    items: list[dict[str, Any]] = []

    rules_data = _load_memory_rules()
    index_path = PROJECT_ROOT / "docs" / "memory" / "规则来源索引.md"

    if rules_data is None:
        return items  # memory_rules.yml 缺失已在其他地方报告

    rule_ids_from_yaml = sorted(
        r.get("rule_id", "") for r in rules_data["rules"] if r.get("rule_id")
    )

    if not index_path.exists():
        items.append({
            "patch_id": "N/A",
            "patch_type": "rule_index",
            "target_file": "docs/memory/规则来源索引.md",
            "status": "failed",
            "message": "规则来源索引.md 不存在",
            "manual_action": "运行 python scripts/generate_rule_index.py 生成索引",
        })
        return items

    # 读取索引中的 rule_id
    index_text = index_path.read_text(encoding="utf-8")
    import re as _re
    rule_ids_from_index = sorted(
        set(_re.findall(r"\|\s*\*\*(TA-R\d{3})\*\*", index_text))
    )

    # 比较
    missing_in_index = set(rule_ids_from_yaml) - set(rule_ids_from_index)
    extra_in_index = set(rule_ids_from_index) - set(rule_ids_from_yaml)

    if not missing_in_index and not extra_in_index:
        items.append({
            "patch_id": "N/A",
            "patch_type": "rule_index",
            "target_file": "docs/memory/规则来源索引.md",
            "status": "passed",
            "message": (
                f"规则来源索引与 memory_rules.yml 同步"
                f"（{len(rule_ids_from_yaml)} 条规则） ✓"
            ),
            "manual_action": None,
        })
    else:
        messages = []
        if missing_in_index:
            messages.append(
                f"索引中缺失: {', '.join(sorted(missing_in_index))}"
            )
        if extra_in_index:
            messages.append(
                f"索引中多余（不在 memory_rules.yml 中）: "
                f"{', '.join(sorted(extra_in_index))}"
            )
        items.append({
            "patch_id": "N/A",
            "patch_type": "rule_index",
            "target_file": "docs/memory/规则来源索引.md",
            "status": "warning",
            "message": "规则来源索引与 memory_rules.yml 不同步: " + "; ".join(messages),
            "manual_action": "运行 python scripts/generate_rule_index.py 重新生成索引",
        })

    # 检查 generate_rule_index.py 存在并可运行
    gen_script = PROJECT_ROOT / "scripts" / "generate_rule_index.py"
    if gen_script.exists():
        items.append({
            "patch_id": "N/A",
            "patch_type": "rule_index",
            "target_file": "scripts/generate_rule_index.py",
            "status": "passed",
            "message": "generate_rule_index.py 存在 ✓",
            "manual_action": None,
        })
    else:
        items.append({
            "patch_id": "N/A",
            "patch_type": "rule_index",
            "target_file": "scripts/generate_rule_index.py",
            "status": "warning",
            "message": "generate_rule_index.py 不存在",
            "manual_action": "创建 scripts/generate_rule_index.py 脚本",
        })

    return items


# ═══════════════════════════════════════════════════════════════
# 经验复盘 / 风险清单引用检查
# ═══════════════════════════════════════════════════════════════


def _check_recap_references(
    patches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """检查 memory_recap_patch 是否在经验复盘中找到引用。"""
    items: list[dict[str, Any]] = []

    recap_patches = [
        p for p in patches if p.get("patch_type") == "memory_recap_patch"
    ]
    if not recap_patches:
        return items

    recap_path = PROJECT_ROOT / "docs" / "memory" / "经验复盘.md"
    if not recap_path.exists():
        for p in recap_patches:
            items.append({
                "patch_id": p.get("patch_id", "unknown"),
                "patch_type": "memory_recap_patch",
                "target_file": "docs/memory/经验复盘.md",
                "status": "failed",
                "message": "经验复盘.md 不存在",
                "manual_action": "创建 docs/memory/经验复盘.md 并合入 patch 内容",
            })
        return items

    recap_text = recap_path.read_text(encoding="utf-8")

    for p in recap_patches:
        patch_id = p.get("patch_id", "unknown")
        # 尝试从 patch content 中提取 rule_id 或 source
        content = p.get("content", "")
        # 检查经验复盘是否引用了对应的 rule_id 或 failure case
        rule_ids_in_content = _extract_rule_ids(content)
        found = False
        for rid in rule_ids_in_content:
            if rid in recap_text:
                found = True
                break
        # 也检查 source_failure_case
        source_case = p.get("source_failure_case", p.get("source", ""))
        if source_case and source_case in recap_text:
            found = True

        if found:
            items.append({
                "patch_id": patch_id,
                "patch_type": "memory_recap_patch",
                "target_file": "docs/memory/经验复盘.md",
                "status": "passed",
                "message": f"经验复盘.md 中找到对应引用 ✓",
                "manual_action": None,
            })
        else:
            items.append({
                "patch_id": patch_id,
                "patch_type": "memory_recap_patch",
                "target_file": "docs/memory/经验复盘.md",
                "status": "warning",
                "message": (
                    f"未在 经验复盘.md 中找到 patch '{patch_id}' 的对应引用"
                ),
                "manual_action": "将 patch 内容合入 经验复盘.md 并确保包含 rule_id 或 failure_case 引用",
            })

    return items


def _check_risk_references(
    patches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """检查 risk_item_patch 是否在风险清单中找到引用。"""
    items: list[dict[str, Any]] = []

    risk_patches = [
        p for p in patches if p.get("patch_type") == "risk_item_patch"
    ]
    if not risk_patches:
        return items

    risk_path = PROJECT_ROOT / "docs" / "memory" / "风险清单.md"
    if not risk_path.exists():
        for p in risk_patches:
            items.append({
                "patch_id": p.get("patch_id", "unknown"),
                "patch_type": "risk_item_patch",
                "target_file": "docs/memory/风险清单.md",
                "status": "failed",
                "message": "风险清单.md 不存在",
                "manual_action": "创建 docs/memory/风险清单.md 并合入 patch 内容",
            })
        return items

    risk_text = risk_path.read_text(encoding="utf-8")

    for p in risk_patches:
        patch_id = p.get("patch_id", "unknown")
        content = p.get("content", "")
        # 提取可能的 risk_id
        import re as _re
        risk_ids = _re.findall(r"RISK-\d{3}", content)
        found = any(rid in risk_text for rid in risk_ids)

        if found:
            items.append({
                "patch_id": patch_id,
                "patch_type": "risk_item_patch",
                "target_file": "docs/memory/风险清单.md",
                "status": "passed",
                "message": f"风险清单.md 中找到对应 risk_id 引用 ✓",
                "manual_action": None,
            })
        else:
            # 检查是否通过 rule_id 引用
            rule_ids_in_content = _extract_rule_ids(content)
            found_via_rule = any(rid in risk_text for rid in rule_ids_in_content)
            if found_via_rule:
                items.append({
                    "patch_id": patch_id,
                    "patch_type": "risk_item_patch",
                    "target_file": "docs/memory/风险清单.md",
                    "status": "passed",
                    "message": "风险清单.md 中通过 rule_id 找到关联引用 ✓",
                    "manual_action": None,
                })
            else:
                items.append({
                    "patch_id": patch_id,
                    "patch_type": "risk_item_patch",
                    "target_file": "docs/memory/风险清单.md",
                    "status": "warning",
                    "message": (
                        f"未在 风险清单.md 中找到 patch '{patch_id}' 的对应引用"
                    ),
                    "manual_action": "将 patch 内容合入 风险清单.md 并确保包含 risk_id 引用",
                })

    return items


def _extract_rule_ids(text: str) -> list[str]:
    """从文本中提取 TA-Rxxx 格式的 rule_id。"""
    import re as _re
    return _re.findall(r"TA-R\d{3}", text)


# ═══════════════════════════════════════════════════════════════
# 测试建议落点检查
# ═══════════════════════════════════════════════════════════════


def _check_test_suggestions(
    patches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """检查 test_case_patch 和 regression_case_patch 的落地状态。

    - 如果人工已新增对应文件 → 验证可发现
    - 如果未新增 → pending_manual_action，不失败
    """
    items: list[dict[str, Any]] = []

    for p in patches:
        patch_type = p.get("patch_type", "")

        if patch_type == "test_case_patch":
            items.extend(_check_test_case_landing(p))
        elif patch_type == "regression_case_patch":
            items.extend(_check_regression_case_landing(p))

    return items


def _check_test_case_landing(patch: dict[str, Any]) -> list[dict[str, Any]]:
    """检查单个 test_case_patch 的落地状态。"""
    patch_id = patch.get("patch_id", "unknown")
    target_file = patch.get("target_file", patch.get("target", ""))
    content = patch.get("content", "")

    if not target_file or target_file == "tests/（待定）":
        return [{
            "patch_id": patch_id,
            "patch_type": "test_case_patch",
            "target_file": target_file or "tests/（待定）",
            "status": "pending",
            "message": "test_case_patch 的 target 路径尚未确定，等待人工指定",
            "manual_action": "确认测试文件目标路径后，创建对应的 pytest 文件",
        }]

    full_path = PROJECT_ROOT / target_file
    if full_path.exists():
        # 文件存在，验证 pytest 可发现
        file_text = full_path.read_text(encoding="utf-8")
        has_test_func = "def test_" in file_text or "class Test" in file_text
        if has_test_func:
            return [{
                "patch_id": patch_id,
                "patch_type": "test_case_patch",
                "target_file": target_file,
                "status": "passed",
                "message": f"测试文件 {target_file} 存在且包含可发现的测试用例 ✓",
                "manual_action": None,
            }]
        return [{
            "patch_id": patch_id,
            "patch_type": "test_case_patch",
            "target_file": target_file,
            "status": "warning",
            "message": f"测试文件 {target_file} 存在但未检测到 def test_ 或 class Test",
            "manual_action": "在文件中添加 pytest 可发现的测试函数或类",
        }]

    return [{
        "patch_id": patch_id,
        "patch_type": "test_case_patch",
        "target_file": target_file,
        "status": "pending",
        "message": f"测试文件 {target_file} 尚未创建",
        "manual_action": f"创建 {target_file} 并参考 patch content 编写 pytest 用例",
    }]


def _check_regression_case_landing(patch: dict[str, Any]) -> list[dict[str, Any]]:
    """检查单个 regression_case_patch 的落地状态。"""
    patch_id = patch.get("patch_id", "unknown")
    target_file = patch.get("target_file", patch.get("target", ""))

    # Step 14 中 regression_case_patch 的 target_file 默认指向 evals/regression/
    if not target_file or "待定" in target_file:
        # 尝试从 content 中提取可能的文件名
        return [{
            "patch_id": patch_id,
            "patch_type": "regression_case_patch",
            "target_file": target_file or "evals/regression/（待定）",
            "status": "pending",
            "message": "regression_case_patch 的 target 路径尚未确定，等待人工指定",
            "manual_action": "确认 eval 文件目标路径后，创建对应的 YAML 文件",
        }]

    full_path = PROJECT_ROOT / target_file
    if full_path.exists():
        try:
            import yaml as _yaml
            raw = full_path.read_text(encoding="utf-8")
            _yaml.safe_load(raw)
            return [{
                "patch_id": patch_id,
                "patch_type": "regression_case_patch",
                "target_file": target_file,
                "status": "passed",
                "message": f"eval 文件 {target_file} 存在且 YAML 可解析 ✓",
                "manual_action": None,
            }]
        except Exception:
            return [{
                "patch_id": patch_id,
                "patch_type": "regression_case_patch",
                "target_file": target_file,
                "status": "failed",
                "message": f"eval 文件 {target_file} 存在但 YAML 解析失败",
                "manual_action": "修正 YAML 语法错误",
            }]

    return [{
        "patch_id": patch_id,
        "patch_type": "regression_case_patch",
        "target_file": target_file,
        "status": "pending",
        "message": f"eval 文件 {target_file} 尚未创建",
        "manual_action": f"创建 {target_file} 并参考 patch content 编写 YAML 用例",
    }]


# ═══════════════════════════════════════════════════════════════
# 推荐命令
# ═══════════════════════════════════════════════════════════════


def _build_recommended_commands(patches: list[dict[str, Any]]) -> list[str]:
    """根据 patch 类型生成推荐运行命令列表。"""
    commands: list[str] = []

    patch_types = {p.get("patch_type", "") for p in patches}

    # 始终推荐
    commands.append("python scripts/generate_rule_index.py")
    commands.append("python harness/checks/check_memory_update.py --registry")
    commands.append("python harness/run_harness.py")

    # 有 test/memory 类 patch 时推荐 pytest
    if patch_types & {"test_case_patch", "memory_rule_patch", "regression_case_patch"}:
        commands.append('python -m pytest tests -k "memory"')

    return commands


# ═══════════════════════════════════════════════════════════════
# 主报告构建
# ═══════════════════════════════════════════════════════════════


def build_validation_report(
    proposal_path: str | Path,
    run_checks: bool = False,
) -> dict[str, Any]:
    """构建 patch validation 报告。

    Args:
        proposal_path: Step 14 生成的 patch proposal JSON 文件路径
        run_checks: 是否实际运行重型命令（默认 False）

    Returns:
        validation report dict，包含 summary / validation_items / recommended_commands
    """
    now = datetime.now(UTC)
    run_id = now.strftime("PV%Y%m%dT%H%M%SZ")

    # 加载 proposal
    try:
        proposal = load_patch_proposal(proposal_path)
    except (FileNotFoundError, ValueError) as exc:
        return {
            "run_id": run_id,
            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_proposal": str(proposal_path),
            "summary": {
                "patches_checked": 0,
                "passed": 0,
                "warnings": 0,
                "failures": 0,
                "pending_manual_actions": 0,
            },
            "validation_items": [{
                "patch_id": "N/A",
                "patch_type": "N/A",
                "target_file": "N/A",
                "status": "failed",
                "message": f"无法加载 proposal: {exc}",
                "manual_action": "检查 proposal 文件路径和格式",
            }],
            "recommended_commands": _build_recommended_commands([]),
            "error": str(exc),
        }

    patches = proposal["patches"]

    # ── 1. Proposal 基础检查 ──
    validation_items: list[dict[str, Any]] = []
    validation_items.extend(_validate_proposal_basics(patches))

    # ── 2. memory_rules.yml 结构检查 ──
    validation_items.extend(_check_memory_rules(patches))

    # ── 3. rule index 同步检查 ──
    validation_items.extend(_check_rule_index())

    # ── 4. 经验复盘 / 风险清单引用检查 ──
    validation_items.extend(_check_recap_references(patches))
    validation_items.extend(_check_risk_references(patches))

    # ── 5. 测试建议落点检查 ──
    validation_items.extend(_check_test_suggestions(patches))

    # ── 6. 推荐命令 ──
    recommended = _build_recommended_commands(patches)

    # ── 统计 ──
    passed = sum(1 for v in validation_items if v["status"] == "passed")
    warnings = sum(1 for v in validation_items if v["status"] == "warning")
    failed = sum(1 for v in validation_items if v["status"] == "failed")
    pending = sum(1 for v in validation_items if v["status"] == "pending")

    summary = {
        "patches_checked": len(patches),
        "passed": passed,
        "warnings": warnings,
        "failures": failed,
        "pending_manual_actions": pending,
    }

    return {
        "run_id": run_id,
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_proposal": proposal["path"],
        "summary": summary,
        "validation_items": validation_items,
        "recommended_commands": recommended,
        "run_checks": run_checks,
    }


# ═══════════════════════════════════════════════════════════════
# JSON / Markdown 渲染
# ═══════════════════════════════════════════════════════════════


def render_validation_json(report: dict[str, Any]) -> dict[str, Any]:
    """构建 JSON 可序列化的报告 dict。"""
    return {
        "run_id": report["run_id"],
        "timestamp": report["timestamp"],
        "source_proposal": report["source_proposal"],
        "summary": report["summary"],
        "validation_items": [
            {
                "patch_id": v["patch_id"],
                "patch_type": v["patch_type"],
                "target_file": v["target_file"],
                "status": v["status"],
                "message": v["message"],
                "manual_action": v.get("manual_action"),
            }
            for v in report["validation_items"]
        ],
        "recommended_commands": report["recommended_commands"],
    }


def render_validation_markdown(report: dict[str, Any]) -> str:
    """生成 Markdown 格式的验证报告。"""
    summary = report["summary"]
    items = report["validation_items"]

    # 按 status 分组
    failed_items = [v for v in items if v["status"] == "failed"]
    warn_items = [v for v in items if v["status"] == "warning"]
    pending_items = [v for v in items if v["status"] == "pending"]
    passed_items = [v for v in items if v["status"] == "passed"]

    lines = [
        "# Memory Patch Validation Report",
        "",
        f"**Run ID**: `{report['run_id']}`",
        f"**Timestamp**: {report['timestamp']}",
        f"**Source Proposal**: `{report['source_proposal']}`",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| 指标 | 值 |",
        f"|------|----|",
        f"| Patches Checked | {summary['patches_checked']} |",
        f"| ✅ Passed | {summary['passed']} |",
        f"| ⚠️ Warnings | {summary['warnings']} |",
        f"| ❌ Failures | {summary['failures']} |",
        f"| ⏳ Pending Manual | {summary['pending_manual_actions']} |",
        "",
        "---",
        "",
    ]

    # Failures
    if failed_items:
        lines.extend([
            "## ❌ Failures",
            "",
            "以下项目必须修复后才能通过验证：",
            "",
            "| Patch | Type | Target | Message | Action |",
            "|-------|------|--------|---------|--------|",
        ])
        for v in failed_items:
            lines.append(
                f"| `{v['patch_id']}` | {v['patch_type']} "
                f"| `{v['target_file']}` "
                f"| {v['message']} "
                f"| {v.get('manual_action', '-')} |"
            )
        lines.append("")

    # Warnings
    if warn_items:
        lines.extend([
            "## ⚠️ Warnings",
            "",
            "以下项目需要关注，但不阻断：",
            "",
            "| Patch | Type | Target | Message | Action |",
            "|-------|------|--------|---------|--------|",
        ])
        for v in warn_items:
            lines.append(
                f"| `{v['patch_id']}` | {v['patch_type']} "
                f"| `{v['target_file']}` "
                f"| {v['message']} "
                f"| {v.get('manual_action', '-')} |"
            )
        lines.append("")

    # Pending
    if pending_items:
        lines.extend([
            "## ⏳ Pending Manual Actions",
            "",
            "以下项目需要人工操作：",
            "",
            "| Patch | Type | Target | Message | Action |",
            "|-------|------|--------|---------|--------|",
        ])
        for v in pending_items:
            lines.append(
                f"| `{v['patch_id']}` | {v['patch_type']} "
                f"| `{v['target_file']}` "
                f"| {v['message']} "
                f"| {v.get('manual_action', '-')} |"
            )
        lines.append("")

    # All results table
    lines.extend([
        "## All Validation Results",
        "",
        "| Patch | Type | Target | Status | Message |",
        "|-------|------|--------|--------|---------|",
    ])
    status_icon = {"passed": "✅", "warning": "⚠️", "failed": "❌", "pending": "⏳"}
    for v in items:
        icon = status_icon.get(v["status"], "❓")
        lines.append(
            f"| `{v['patch_id']}` | {v['patch_type']} "
            f"| `{v['target_file']}` "
            f"| {icon} {v['status']} "
            f"| {v['message']} |"
        )
    lines.append("")

    # Recommended commands
    if report["recommended_commands"]:
        lines.extend([
            "---",
            "",
            "## Recommended Commands",
            "",
            "以下命令建议运行以确保全面验证：",
            "",
        ])
        for cmd in report["recommended_commands"]:
            lines.append(f"- `{cmd}`")
        lines.append("")

    # Safety boundaries
    lines.extend([
        "---",
        "",
        "## Safety Boundaries",
        "",
        "- ✅ 未自动修改 `docs/memory/*`",
        "- ✅ 未自动修改 `memory_rules.yml`",
        "- ✅ 未自动运行 `generate_rule_index.py`（除非显式 `--run-checks`）",
        "- ✅ 未读取 `*_latest.*`",
        "- ✅ 未自动晋升 `active` / `blocking=true`",
        "- ✅ 未接入 pre-commit",
        "- ✅ 未修改业务代码",
        "",
        "---",
        "",
        "## Not Applied Automatically",
        "",
        "> 本验证工作流只执行检查，不做任何自动修改。",
        "> 所有 failed/warning/pending 项需人工确认后手动修复。",
        "> patch proposal 的 write_mode 始终为 `proposal_only`。",
        "",
    ])

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 快照写入
# ═══════════════════════════════════════════════════════════════


def write_validation_snapshot(
    report: dict[str, Any],
    output_dir: str | Path = "harness/reports/memory_patch_validations",
) -> dict[str, str]:
    """将验证报告写入 timestamp snapshot 文件。

    Args:
        report: build_validation_report() 的返回结果
        output_dir: 输出目录

    Returns:
        {"json": path, "markdown": path}
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    run_id = report["run_id"]
    safe_id = run_id.replace(":", "").replace("/", "")

    json_data = render_validation_json(report)
    json_path = output_path / f"memory_patch_validation_{safe_id}.json"
    json_path.write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md_content = render_validation_markdown(report)
    md_path = output_path / f"memory_patch_validation_{safe_id}.md"
    md_path.write_text(md_content, encoding="utf-8")

    return {"json": str(json_path), "markdown": str(md_path)}
