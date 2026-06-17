"""
Memory Gate —— 检测关键路径变更后记忆文件是否同步更新。

验证以下内容：
    1. 当前 git diff 中是否有涉及关键路径的变更
    2. 如有，docs/memory/经验复盘.md 是否存在且包含对应条目
    3. docs/memory/ 下记忆文件的存在性和基本结构
    4. （可选 --content-only）已有记忆条目的内容质量
    5. （可选 --registry）Step 6 Rule Closure：读取 memory_rules.yml，
       检查关键路径变更是否被至少一条规则覆盖（孤儿文件检测），
       以及 check/test/eval 变更是否与规则的 required_* 字段一致

本检查是 Phase 3 的核心组件——确保"改了代码就写记忆"不是靠人记，而是靠门禁拦。

用法：
    python harness/checks/check_memory_update.py              # 完整检查
    python harness/checks/check_memory_update.py --content-only  # 仅内容质量
    python harness/checks/check_memory_update.py --registry   # Step 6 规则闭环检查
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 关键路径定义 —— 修改这些文件时必须更新记忆
CRITICAL_PATHS = [
    # 核心 IR / 生成 / Agent 主循环
    "src/ir.py",
    "src/sql_gen.py",
    "src/agent.py",
    "src/ambiguity.py",
    "src/schema_validators.py",
    "src/executor.py",
    # Phase 3: 执行层
    "src/plan_executor.py",
    "src/execution_strategy.py",
    # Phase 3B/3C: 结果层
    "src/result_summary.py",
    "src/result_merge.py",
    # Phase 3B/3D: LLM 融合 + 跨域策略
    "src/result_fusion.py",
    "src/cross_domain_policy.py",
    # Phase 5: 图表规格
    "src/chart_spec.py",
    # Prompt 模板
    "prompts/intent_classifier.md",
    "prompts/sql_planner.md",
    "prompts/sql_generator.md",
    "prompts/explainer.md",
    "prompts/result_fusion.md",
    # Harness 基础设施
    "harness/checks/",
    "harness/baselines/",
    "evals/",
    "config/agent_config.yml",
    # Step 5-6: Memory Rule Registry
    "docs/memory/memory_rules.yml",
    "scripts/generate_rule_index.py",
]

# 记忆文件清单
MEMORY_FILES = [
    "docs/memory/经验复盘.md",
    "docs/memory/变更复盘模板.md",
    "docs/memory/风险清单.md",
    "docs/memory/规则来源索引.md",
    "docs/memory/memory_rules.yml",
]

# 经验条目的必填字段
REQUIRED_FIELDS = [
    "日期", "状态", "置信等级", "版本", "来源问题",
    "根因", "风险", "规则", "验证记录",
]

# 记忆条目最低行数
MIN_ENTRY_LINES = 8

# 来源问题最低字数
MIN_SOURCE_DESC_CHARS = 20

# 变更类型 → 记忆覆盖提示
CHANGE_MEMORY_HINTS = {
    # 核心模块
    "src/ir.py": "IR 数据结构变更 → 需在经验复盘.md 中记录：变更原因、向下兼容性、对已有评测的影响",
    "src/sql_gen.py": "SQL 生成/安全规则变更 → 需在经验复盘.md 中记录：为什么改规则、阻止了什么风险",
    "src/agent.py": "主循环逻辑变更 → 需在经验复盘.md 中记录：对 Agent 行为边界的改变",
    "src/ambiguity.py": "歧义检测/反问策略变更 → 需在经验复盘.md 中记录：阈值调整原因、预期效果",
    "src/schema_validators.py": "Schema 校验规则变更 → 需在经验复盘.md 中记录：新增/修改的校验项及原因",
    # Phase 3: 执行层
    "src/plan_executor.py": (
        "执行层边界变更 → 需在经验复盘.md 中记录：SQL 生成/安全校验/SQLResult 回填/execution trace 的改动；"
        "同步检查：① sql_plan_to_sql() 是否仍是 SQL 唯一入口 ② validate_sql_safety() 是否每次执行前调用 "
        "③ 离线模式是否仍阻断执行 ④ DuckDB read_only 是否未被破坏"
    ),
    "src/execution_strategy.py": (
        "执行策略变更 → 需在经验复盘.md 中记录：串行/并发策略调整原因、线程安全措施；"
        "同步检查：① 并发是否默认关闭 ② DuckDB connection 是否不跨线程共享 "
        "③ 每个 plan 是否仍走 validate_sql_safety() ④ read_only 是否未被破坏"
    ),
    # Phase 3B/3C: 结果层
    "src/result_summary.py": (
        "结果摘要结构变更 → 需在经验复盘.md 中记录：字段增删原因、下游兼容性影响；"
        "同步检查：① ResultSummary 字段是否与 result_fusion/result_merge/chart_spec 的输入预期一致 "
        "② _detect_grain() 逻辑变更是否影响 merge 对齐"
    ),
    "src/result_merge.py": (
        "结果 merge 逻辑变更 → 需在经验复盘.md 中记录：merge 条件/策略调整原因、日期对齐规则变更；"
        "同步检查：① can_merge_on_date() 的条件是否仍然正确 ② grain 不一致时如何处理 "
        "③ 非因果解释边界是否未被突破 ④ _check_range_consistency() 是否仍然有效"
    ),
    # Phase 3B/3D: LLM 融合 + 跨域策略
    "src/result_fusion.py": (
        "LLM 融合变更 → 需在经验复盘.md 和 风险清单.md 中记录：融合策略调整原因、安全约束变更；"
        "同步检查：① LLM 是否仍不能生成 SQL ② payload 是否不包含 SQL/API key/env "
        "③ 是否存在模板 fallback ④ 是否有因果词后校验（_check_causal_language） "
        "⑤ 数值一致性后校验是否仍然执行 ⑥ validate_fusion_output() 4 层校验是否完整"
    ),
    "src/cross_domain_policy.py": (
        "跨域策略变更 → 需在经验复盘.md 和 风险清单.md 中记录：新增/修改的跨域组合规则、决策优先级调整；"
        "同步检查：① person-fields 隐私保护是否未被削弱 ② unknown domain 是否仍触发反问 "
        "③ traffic+safety 因果禁止是否仍然生效 ④ standard_fine_total 警告是否仍然生效 "
        "⑤ decision.reason 是否仍清晰可追溯"
    ),
    # Phase 5: 图表规格
    "src/chart_spec.py": (
        "图表规格变更 → 需在经验复盘.md 中记录：新增图表类型/规则调整原因、选择逻辑变更；"
        "同步检查：① 是否不生成 HTML/JS ② 是否不调用 LLM ③ 是否不访问 DuckDB "
        "④ ChartSpec.to_json() 是否可序列化 ⑤ 跨域警告注入是否仍然生效 ⑥ refusal → table 降级是否仍然生效"
    ),
    # Prompt 模板
    "prompts/": "Prompt 模板变更 → 需在经验复盘.md 中记录：改了什么、为什么改、需同步的回归用例",
    "prompts/result_fusion.md": (
        "LLM 融合 Prompt 变更 → 需在经验复盘.md 和 风险清单.md 中记录：Prompt 修改原因、新增/修改的反例约束；"
        "同步检查：① 是否仍明确禁止生成 SQL ② 是否仍禁止使用因果语言 ③ 是否仍禁止编造指标 "
        "④ 是否仍禁止修改数值 ⑤ 反例是否覆盖常见绕过模式 "
        "⑥ src/result_fusion.py 的 validate_fusion_output() 后校验规则是否需要同步更新"
    ),
    # Harness 基础设施
    "harness/checks/": "门禁规则变更 → 需在经验复盘.md 中记录：为什么加/改/撤检查项",
    "harness/baselines/": "基线逻辑变更 → 需在经验复盘.md 中记录：对基线判定标准的影响",
    "evals/": "评测用例变更 → 需在风险清单.md 中评估：是否引入新的失败模式",
    "config/agent_config.yml": "Agent 配置变更 → 需在经验复盘.md 中记录：模型/阈值/超时变更的原因和预期效果",
    # Step 5-6: Memory Rule Registry
    "docs/memory/memory_rules.yml": (
        "规则注册表变更 → 需同步运行 scripts/generate_rule_index.py 重新生成索引；"
        "如果新增规则，确认 required_checks/required_tests/required_evals 覆盖完整"
    ),
    "scripts/generate_rule_index.py": (
        "索引生成脚本变更 → 需确保生成的 docs/memory/规则来源索引.md 结构仍然正确；"
        "运行 python scripts/generate_rule_index.py 验证"
    ),
}


def git_diff_staged() -> list[str]:
    """获取暂存区变更的文件列表"""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.TimeoutExpired, OSError):
        return []


def git_diff_unstaged() -> list[str]:
    """获取工作区未暂存的变更文件列表"""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.TimeoutExpired, OSError):
        return []


def get_all_changed_files() -> list[str]:
    """获取所有变更文件（暂存 + 未暂存）"""
    staged = git_diff_staged()
    unstaged = git_diff_unstaged()
    return list(set(staged + unstaged))


def classify_changes(changed_files: list[str]) -> dict[str, list[str]]:
    """把变更文件按触发规则分类"""
    classified: dict[str, list[str]] = {}
    for path in changed_files:
        for critical in CRITICAL_PATHS:
            if path.startswith(critical.rstrip("/")) or path == critical:
                hint_key = critical if critical in CHANGE_MEMORY_HINTS else _find_hint_key(path)
                if hint_key not in classified:
                    classified[hint_key] = []
                classified[hint_key].append(path)
                break
    return classified


def _find_hint_key(path: str) -> str:
    """根据路径找最匹配的提示键"""
    for key in sorted(CHANGE_MEMORY_HINTS.keys(), key=len, reverse=True):
        if path.startswith(key.rstrip("/")) or path == key:
            return key
    return path


def check_memory_files_exist() -> dict[str, Any]:
    """检查四个记忆文件是否存在"""
    checks: list[dict[str, Any]] = []
    for mf in MEMORY_FILES:
        full_path = PROJECT_ROOT / mf
        if full_path.exists():
            checks.append({
                "name": f"{mf} 存在",
                "status": "PASS",
                "detail": f"文件已创建 ({full_path.stat().st_size} bytes)",
            })
        else:
            checks.append({
                "name": f"{mf} 存在",
                "status": "FAIL",
                "detail": f"文件不存在: {full_path}",
            })
    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")
    return {"checks": checks, "pass_count": pass_count, "fail_count": fail_count}


def check_memory_coverage(classified_changes: dict[str, list[str]]) -> dict[str, Any]:
    """检查关键路径变更是否有对应的记忆覆盖"""
    checks: list[dict[str, Any]] = []
    experience_path = PROJECT_ROOT / "docs/memory/经验复盘.md"

    if not classified_changes:
        checks.append({
            "name": "关键路径变更检测",
            "status": "PASS",
            "detail": "未检测到关键路径变更，跳过记忆覆盖检查",
        })
        return {
            "checks": checks,
            "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
            "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
        }

    # 有关键路径变更 → 检查经验复盘文件是否存在且有内容
    if not experience_path.exists():
        checks.append({
            "name": "经验复盘覆盖——文件存在",
            "status": "FAIL",
            "detail": f"检测到关键路径变更，但经验复盘文件不存在",
        })
        return {"checks": checks, "pass_count": 0, "fail_count": 1}

    experience_content = experience_path.read_text(encoding="utf-8")
    entry_count = experience_content.count("\n## R")

    if entry_count == 0:
        checks.append({
            "name": "经验复盘覆盖——条目数量",
            "status": "FAIL",
            "detail": "检测到关键路径变更，但经验复盘.md 中无任何经验条目",
        })
        return {"checks": checks, "pass_count": 0, "fail_count": 1}

    checks.append({
        "name": "经验复盘覆盖——条目数量",
        "status": "PASS",
        "detail": f"经验复盘.md 包含 {entry_count} 条经验",
    })

    # 对每类变更给出记忆覆盖提示
    for hint_key, files in classified_changes.items():
        hint = CHANGE_MEMORY_HINTS.get(hint_key)
        if hint:
            checks.append({
                "name": f"变更覆盖提示: {hint_key}",
                "status": "WARN",
                "detail": f"{hint}\n  涉及文件: {', '.join(files)}",
            })

    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")
    return {"checks": checks, "pass_count": pass_count, "fail_count": fail_count}


def check_entry_quality() -> dict[str, Any]:
    """检查经验复盘.md 中已有条目的内容质量"""
    checks: list[dict[str, Any]] = []
    experience_path = PROJECT_ROOT / "docs/memory/经验复盘.md"

    if not experience_path.exists():
        checks.append({
            "name": "内容质量检查",
            "status": "SKIP",
            "detail": "经验复盘.md 不存在，跳过内容质量检查",
        })
        return {"checks": checks, "pass_count": 0, "fail_count": 0}

    content = experience_path.read_text(encoding="utf-8")

    # 提取每个 R 条目
    entries = re.split(r"\n## R\d+", content)
    entries = [e.strip() for e in entries if e.strip() and not e.startswith("#")]

    if not entries:
        checks.append({
            "name": "条目提取",
            "status": "WARN",
            "detail": "经验复盘.md 中未检测到任何 R 编号条目",
        })
        return {"checks": checks, "pass_count": 0, "fail_count": 0}

    quality_issues: list[dict[str, Any]] = []
    duplicate_check: dict[str, str] = {}

    for i, entry in enumerate(entries):
        lines = entry.split("\n")
        entry_text = "\n".join(lines)
        entry_id = f"R{i + 1}"

        # 检查最低行数
        if len(lines) < MIN_ENTRY_LINES:
            quality_issues.append({
                "entry": entry_id,
                "issue": f"条目过短（{len(lines)} 行，最低要求 {MIN_ENTRY_LINES} 行）",
            })

        # 检查必填字段
        for field in REQUIRED_FIELDS:
            if field == "验证记录":
                if "- 验证记录：" not in entry_text and "验证记录" not in entry_text:
                    quality_issues.append({
                        "entry": entry_id,
                        "issue": f"缺失必填字段: {field}",
                    })
            elif f"- {field}：" not in entry_text:
                quality_issues.append({
                    "entry": entry_id,
                    "issue": f"缺失必填字段: {field}",
                })

        # 检查来源问题字数
        source_match = re.search(r"- 来源问题：(.+?)(?:\n|$)", entry_text)
        if source_match:
            source_text = source_match.group(1).strip()
            if len(source_text) < MIN_SOURCE_DESC_CHARS:
                quality_issues.append({
                    "entry": entry_id,
                    "issue": f"来源问题过短（{len(source_text)} 字，最低要求 {MIN_SOURCE_DESC_CHARS} 字）",
                })

        # 重复检测
        entry_hash = entry_text[:100]
        if entry_hash in duplicate_check:
            quality_issues.append({
                "entry": entry_id,
                "issue": f"与 {duplicate_check[entry_hash]} 高度重复（前 100 字符完全一致）",
            })
        else:
            duplicate_check[entry_hash] = entry_id

    for issue in quality_issues:
        checks.append({
            "name": f"{issue['entry']} 质量",
            "status": "WARN",
            "detail": issue["issue"],
        })

    if not quality_issues:
        checks.append({
            "name": "内容质量检查",
            "status": "PASS",
            "detail": f"{len(entries)} 条经验全部通过质量门禁",
        })

    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")
    return {"checks": checks, "pass_count": pass_count, "fail_count": fail_count}


def check_risk_list() -> dict[str, Any]:
    """检查风险清单的基本结构"""
    checks: list[dict[str, Any]] = []
    risk_path = PROJECT_ROOT / "docs/memory/风险清单.md"

    if not risk_path.exists():
        checks.append({
            "name": "风险清单",
            "status": "SKIP",
            "detail": "风险清单.md 不存在",
        })
        return {"checks": checks, "pass_count": 0, "fail_count": 0}

    content = risk_path.read_text(encoding="utf-8")
    risk_count = content.count("RISK-")

    checks.append({
        "name": "风险清单条目数",
        "status": "PASS" if risk_count >= 5 else "WARN",
        "detail": f"共 {risk_count} 条风险记录",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_rule_index() -> dict[str, Any]:
    """检查规则来源索引的基本结构"""
    checks: list[dict[str, Any]] = []
    index_path = PROJECT_ROOT / "docs/memory/规则来源索引.md"

    if not index_path.exists():
        checks.append({
            "name": "规则来源索引",
            "status": "SKIP",
            "detail": "规则来源索引.md 不存在",
        })
        return {"checks": checks, "pass_count": 0, "fail_count": 0}

    content = index_path.read_text(encoding="utf-8")
    # 同时支持旧格式（R001-R0XX）和新格式（TA-R010+）
    rule_count_r = content.count("| R")
    rule_count_ta = content.count("| **TA-R")
    rule_count = max(rule_count_r, rule_count_ta)

    checks.append({
        "name": "规则来源索引条目数",
        "status": "PASS" if rule_count >= 5 else "WARN",
        "detail": f"共 {rule_count} 条规则索引（R=前缀: {rule_count_r}, TA-R=前缀: {rule_count_ta}）",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Step 6: Registry Closure（规则闭环检查）
# ═══════════════════════════════════════════════════════════════════════════════


def load_memory_rules_registry() -> dict[str, Any] | None:
    """加载 memory_rules.yml 并返回规则列表和解析状态。

    Returns:
        {"rules": [...], "path": Path} 或 None（文件不存在/解析失败）
    """
    registry_path = PROJECT_ROOT / "docs/memory/memory_rules.yml"

    if not registry_path.exists():
        return None

    try:
        import yaml
    except ImportError:
        return None

    try:
        with open(registry_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError:
        return None

    if not data or "rules" not in data:
        return None

    return {"rules": data["rules"], "path": registry_path}


def build_registry_reverse_index(rules: list[dict[str, Any]]) -> dict[str, list[str]]:
    """构建 文件路径→规则编号 的反向索引。

    从每条规则的 applies_to / required_checks / required_tests / required_evals
    字段提取文件路径，构建从文件到规则的映射。

    Args:
        rules: memory_rules.yml 中的规则列表

    Returns:
        {file_path: [rule_id, ...]}
    """
    index: dict[str, list[str]] = {}

    for rule in rules:
        rid = rule.get("rule_id", "?")
        # 合并所有文件引用字段
        all_files = (
            rule.get("applies_to", [])
            + rule.get("required_checks", [])
            + rule.get("required_tests", [])
            + rule.get("required_evals", [])
        )
        for f in all_files:
            if f not in index:
                index[f] = []
            if rid not in index[f]:
                index[f].append(rid)

    return index


def _match_critical_path(file_path: str) -> str | None:
    """检查文件是否匹配任一关键路径。

    Args:
        file_path: 变更的文件路径

    Returns:
        匹配的关键路径模式，或 None
    """
    for cp in CRITICAL_PATHS:
        cp_clean = cp.rstrip("/")
        if file_path == cp_clean or file_path.startswith(cp_clean + "/") or file_path.startswith(cp):
            return cp
    return None


def _find_covering_rules(file_path: str, reverse_index: dict[str, list[str]]) -> list[str]:
    """查找覆盖指定文件的所有规则。

    支持精确匹配和目录前缀匹配（如 harness/checks/ 匹配 harness/checks/check_xxx.py）。

    Args:
        file_path: 文件路径
        reverse_index: 文件→规则反向索引

    Returns:
        覆盖该文件的规则编号列表
    """
    # 精确匹配
    if file_path in reverse_index:
        return reverse_index[file_path]

    # 目录前缀匹配
    for indexed_path, rule_ids in reverse_index.items():
        if indexed_path.endswith("/") and file_path.startswith(indexed_path):
            return rule_ids
        # 检查文件是否在索引路径的目录下
        indexed_dir = indexed_path if indexed_path.endswith("/") else indexed_path + "/"
        if file_path.startswith(indexed_dir):
            return rule_ids

    return []


def check_registry_closure(
    changed_files: list[str],
    rules: list[dict[str, Any]],
    reverse_index: dict[str, list[str]],
) -> dict[str, Any]:
    """Step 6 Rule Closure：检查关键路径变更是否被规则注册表覆盖。

    对每个关键路径变更文件：
        1. 查找覆盖该文件的规则（通过反向索引）
        2. 如果无规则覆盖 → WARN: 孤儿文件
        3. 如果是 check 文件变更 → 验证规则的 required_checks 是否包含该 check
        4. 如果是 test 文件变更 → 验证规则的 required_tests 是否包含该 test
        5. 如果是 eval 文件变更 → 验证规则的 required_evals 是否包含该 eval

    Args:
        changed_files: 变更文件列表
        rules: 规则列表
        reverse_index: 文件→规则反向索引

    Returns:
        {checks, pass_count, fail_count, coverage_matrix}
    """
    checks: list[dict[str, Any]] = []
    coverage_matrix: dict[str, dict[str, Any]] = {}

    if not rules:
        checks.append({
            "name": "注册表加载",
            "status": "FAIL",
            "detail": "memory_rules.yml 为空或无法解析，跳过闭环检查",
        })
        return {"checks": checks, "pass_count": 0, "fail_count": 1, "coverage_matrix": {}}

    # 筛选关键路径变更
    critical_changes: list[tuple[str, str]] = []  # [(file_path, critical_pattern)]
    for f in changed_files:
        cp = _match_critical_path(f)
        if cp:
            critical_changes.append((f, cp))

    if not critical_changes:
        checks.append({
            "name": "注册表闭环检查",
            "status": "PASS",
            "detail": "未检测到关键路径变更，跳过闭环检查",
        })
        return {"checks": checks, "pass_count": 1, "fail_count": 0, "coverage_matrix": {}}

    orphan_files: list[str] = []
    metadata_mismatches: list[dict[str, Any]] = []
    covered_files: list[str] = []

    for file_path, _cp in critical_changes:
        covering_rules = _find_covering_rules(file_path, reverse_index)

        coverage_matrix[file_path] = {
            "covered_by": covering_rules,
            "is_orphan": len(covering_rules) == 0,
        }

        if not covering_rules:
            orphan_files.append(file_path)
            continue

        covered_files.append(file_path)

        # 传播检测：check/test/eval 变更 → 验证规则的 required_* 字段
        for rid in covering_rules:
            rule = next((r for r in rules if r.get("rule_id") == rid), None)
            if not rule:
                continue

            # check 文件 → 验证 required_checks
            if "harness/checks/" in file_path or "scripts/" in file_path:
                req_checks = rule.get("required_checks", [])
                if file_path not in req_checks:
                    metadata_mismatches.append({
                        "file": file_path,
                        "rule": rid,
                        "field": "required_checks",
                        "detail": (
                            f"{file_path} 变更但未被 {rid} 的 required_checks 包含，"
                            f"可能需要更新规则注册表"
                        ),
                    })

            # test 文件 → 验证 required_tests
            if "tests/" in file_path and file_path.endswith(".py"):
                req_tests = rule.get("required_tests", [])
                if file_path not in req_tests:
                    metadata_mismatches.append({
                        "file": file_path,
                        "rule": rid,
                        "field": "required_tests",
                        "detail": (
                            f"{file_path} 变更但未被 {rid} 的 required_tests 包含，"
                            f"可能需要更新规则注册表"
                        ),
                    })

            # eval 文件 → 验证 required_evals
            if "evals/" in file_path and file_path.endswith(".yml"):
                req_evals = rule.get("required_evals", [])
                if file_path not in req_evals:
                    metadata_mismatches.append({
                        "file": file_path,
                        "rule": rid,
                        "field": "required_evals",
                        "detail": (
                            f"{file_path} 变更但未被 {rid} 的 required_evals 包含，"
                            f"可能需要更新规则注册表"
                        ),
                    })

    # 构建输出
    checks.append({
        "name": "注册表闭环——覆盖文件",
        "status": "PASS" if covered_files else "WARN",
        "detail": (
            f"{len(covered_files)}/{len(critical_changes)} 个关键路径文件被规则覆盖"
            if critical_changes else "无关键路径变更"
        ),
    })

    if orphan_files:
        checks.append({
            "name": "注册表闭环——孤儿文件",
            "status": "WARN",
            "detail": (
                f"{len(orphan_files)} 个文件未被任何规则覆盖:\n    "
                + "\n    ".join(orphan_files)
                + "\n  建议: 在 memory_rules.yml 中新增或更新规则的 applies_to 字段"
            ),
        })
    else:
        checks.append({
            "name": "注册表闭环——孤儿文件",
            "status": "PASS",
            "detail": "所有关键路径变更均被规则覆盖",
        })

    for mm in metadata_mismatches:
        checks.append({
            "name": f"传播检测: {mm['file']} → {mm['rule']}.{mm['field']}",
            "status": "WARN",
            "detail": mm["detail"],
        })

    if not metadata_mismatches:
        checks.append({
            "name": "注册表闭环——传播一致性",
            "status": "PASS",
            "detail": (
                f"{len(covered_files)} 个覆盖文件的 check/test/eval 引用一致"
                if covered_files else "无覆盖文件"
            ),
        })

    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")
    return {
        "checks": checks,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "coverage_matrix": coverage_matrix,
    }


def check_registry_coverage(
    rules: list[dict[str, Any]],
    reverse_index: dict[str, list[str]],
) -> dict[str, Any]:
    """检查规则注册表对全部关键路径的静态覆盖率。

    不依赖 git diff，而是检查 CRITICAL_PATHS 中的每个文件/目录
    是否至少被一条规则的 applies_to 覆盖。

    Args:
        rules: 规则列表
        reverse_index: 文件→规则反向索引

    Returns:
        {checks, pass_count, fail_count}
    """
    checks: list[dict[str, Any]] = []

    if not rules:
        checks.append({
            "name": "静态覆盖率检查",
            "status": "SKIP",
            "detail": "规则注册表为空，跳过静态覆盖率检查",
        })
        return {"checks": checks, "pass_count": 0, "fail_count": 0}

    uncovered: list[str] = []
    covered: list[tuple[str, list[str]]] = []

    for cp in CRITICAL_PATHS:
        covering = _find_covering_rules(cp, reverse_index)
        if covering:
            covered.append((cp, covering))
        else:
            uncovered.append(cp)

    if uncovered:
        checks.append({
            "name": "静态覆盖率——未覆盖关键路径",
            "status": "WARN",
            "detail": (
                f"{len(uncovered)}/{len(CRITICAL_PATHS)} 个关键路径未被任何规则覆盖:\n    "
                + "\n    ".join(uncovered)
                + "\n  建议: 在 memory_rules.yml 中为这些路径创建规则或更新 applies_to"
            ),
        })
    else:
        checks.append({
            "name": "静态覆盖率——全部覆盖",
            "status": "PASS",
            "detail": f"全部 {len(CRITICAL_PATHS)} 个关键路径均有规则覆盖",
        })

    checks.append({
        "name": "静态覆盖率——覆盖矩阵",
        "status": "PASS",
        "detail": (
            f"{len(covered)} 已覆盖, {len(uncovered)} 未覆盖 "
            f"（总计 {len(CRITICAL_PATHS)} 个关键路径）"
        ),
    })

    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")
    return {"checks": checks, "pass_count": pass_count, "fail_count": fail_count}


def print_report(
    existence_result: dict[str, Any],
    coverage_result: dict[str, Any],
    quality_result: dict[str, Any],
    risk_result: dict[str, Any],
    index_result: dict[str, Any],
    changed_files: list[str],
    registry_closure_result: dict[str, Any] | None = None,
    registry_coverage_result: dict[str, Any] | None = None,
) -> int:
    """打印检查报告，返回退出码。

    Args:
        existence_result: 记忆文件存在性检查结果
        coverage_result: 记忆覆盖度检查结果
        quality_result: 内容质量检查结果
        risk_result: 风险清单检查结果
        index_result: 规则来源索引检查结果
        changed_files: 变更文件列表
        registry_closure_result: （可选）--registry 模式下的闭环检查结果
        registry_coverage_result: （可选）--registry 模式下的静态覆盖率结果
    """
    print("=" * 60)
    print("Memory Gate —— 记忆更新检查")
    print("=" * 60)

    # 显示检测到的变更
    critical_files = [f for f in changed_files if any(
        f.startswith(cp.rstrip("/")) or f == cp for cp in CRITICAL_PATHS
    )]
    if critical_files:
        print(f"\n[*] 检测到关键路径变更 ({len(critical_files)} 个文件):")
        for f in critical_files:
            print(f"    - {f}")
    else:
        print("\n[*] 未检测到关键路径变更")

    # 记忆文件存在性
    print("\n── 记忆文件存在性 ──")
    for c in existence_result["checks"]:
        tag = c["status"]
        print(f"  [{tag}] {c['name']}")
        if c.get("detail"):
            print(f"         {c['detail']}")

    # 记忆覆盖度
    print("\n── 记忆覆盖度 ──")
    for c in coverage_result["checks"]:
        tag = c["status"]
        print(f"  [{tag}] {c['name']}")
        if c.get("detail"):
            print(f"         {c['detail']}")

    # 内容质量
    print("\n── 内容质量 ──")
    for c in quality_result["checks"]:
        tag = c["status"]
        print(f"  [{tag}] {c['name']}")
        if c.get("detail"):
            print(f"         {c['detail']}")

    # 风险清单
    print("\n── 风险清单 ──")
    for c in risk_result["checks"]:
        tag = c["status"]
        print(f"  [{tag}] {c['name']}")
        if c.get("detail"):
            print(f"         {c['detail']}")

    # 规则索引
    print("\n── 规则来源索引 ──")
    for c in index_result["checks"]:
        tag = c["status"]
        print(f"  [{tag}] {c['name']}")
        if c.get("detail"):
            print(f"         {c['detail']}")

    # Step 6: Registry Closure（--registry 模式）
    if registry_closure_result is not None:
        print("\n── Step 6 规则闭环（Registry Closure）──")
        for c in registry_closure_result["checks"]:
            tag = c["status"]
            print(f"  [{tag}] {c['name']}")
            if c.get("detail"):
                print(f"         {c['detail']}")

        # 显示覆盖矩阵
        cm = registry_closure_result.get("coverage_matrix", {})
        if cm:
            print("\n  覆盖矩阵:")
            for fpath, info in cm.items():
                rules_list = ", ".join(info["covered_by"]) if info["covered_by"] else "无"
                flag = "[孤儿]" if info["is_orphan"] else "[OK]"
                print(f"    {flag} {fpath} → {rules_list}")

    if registry_coverage_result is not None:
        print("\n── Step 6 静态覆盖率（Registry Coverage）──")
        for c in registry_coverage_result["checks"]:
            tag = c["status"]
            print(f"  [{tag}] {c['name']}")
            if c.get("detail"):
                print(f"         {c['detail']}")

    # 汇总（包含 registry 结果）
    all_results = [
        existence_result, coverage_result, quality_result,
        risk_result, index_result,
    ]
    if registry_closure_result is not None:
        all_results.append(registry_closure_result)
    if registry_coverage_result is not None:
        all_results.append(registry_coverage_result)

    total_fail = sum(r.get("fail_count", 0) for r in all_results)
    total_pass = sum(r.get("pass_count", 0) for r in all_results)
    total_warn = sum(
        1 for r in all_results
        for c in r.get("checks", [])
        if c["status"] == "WARN"
    )

    print(f"\n  检查完成 — 通过: {total_pass}, 失败: {total_fail}, 提醒: {total_warn}")

    if total_fail > 0:
        print(f"\n[FAIL] Memory Gate: 发现 {total_fail} 项失败！")
        print("")
        print("  修复指引：")
        print("  1. 在 docs/memory/经验复盘.md 中补写经验条目")
        print("  2. 模板参考：docs/memory/变更复盘模板.md")
        print("  3. 已检测到的关键路径变更：")
        for f in critical_files:
            for hint_key, hint in CHANGE_MEMORY_HINTS.items():
                if f.startswith(hint_key.rstrip("/")) or f == hint_key:
                    print(f"     - {f} → {hint.split(chr(8594))[1].strip() if chr(8594) in hint else hint}")
                    break
        print("  4. 重新运行: python harness/checks/check_memory_update.py")
        return 1
    else:
        print("\n[OK] Memory Gate 通过。")
        return 0


def main() -> int:
    """命令行入口"""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Memory Gate —— 记忆更新检查")
    parser.add_argument(
        "--content-only",
        action="store_true",
        help="仅运行内容质量检查（不检查 git diff）",
    )
    parser.add_argument(
        "--registry",
        action="store_true",
        help="启用 Step 6 规则闭环检查（读取 memory_rules.yml 构建反向索引）",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Harness 配置文件路径（Memory Gate 不使用此参数，仅为兼容 run_harness.py 接口保留）",
    )
    args = parser.parse_args()

    # ── 注册表闭环检查（可在 content-only 或完整模式下启用） ──
    registry_closure_result: dict[str, Any] | None = None
    registry_coverage_result: dict[str, Any] | None = None

    if args.registry:
        registry = load_memory_rules_registry()
        if registry:
            rules = registry["rules"]
            reverse_index = build_registry_reverse_index(rules)

            # 静态覆盖率（始终运行）
            registry_coverage_result = check_registry_coverage(rules, reverse_index)

            # 动态闭环（需要 git diff）
            if not args.content_only:
                changed_files_all = get_all_changed_files()
                registry_closure_result = check_registry_closure(
                    changed_files_all, rules, reverse_index
                )
        else:
            # 注册表加载失败
            registry_coverage_result = {
                "checks": [{
                    "name": "注册表加载",
                    "status": "FAIL",
                    "detail": (
                        "无法加载 docs/memory/memory_rules.yml。"
                        "请确认文件存在且 YAML 语法正确。"
                    ),
                }],
                "pass_count": 0,
                "fail_count": 1,
            }

    if args.content_only:
        quality_result = check_entry_quality()
        risk_result = check_risk_list()
        index_result = check_rule_index()
        existence_result = check_memory_files_exist()

        return print_report(
            existence_result,
            {"checks": [], "pass_count": 0, "fail_count": 0},
            quality_result,
            risk_result,
            index_result,
            [],
            registry_closure_result=registry_closure_result,
            registry_coverage_result=registry_coverage_result,
        )

    # 完整模式
    changed_files = get_all_changed_files()
    classified = classify_changes(changed_files)

    existence_result = check_memory_files_exist()
    coverage_result = check_memory_coverage(classified)
    quality_result = check_entry_quality()
    risk_result = check_risk_list()
    index_result = check_rule_index()

    return print_report(
        existence_result,
        coverage_result,
        quality_result,
        risk_result,
        index_result,
        changed_files,
        registry_closure_result=registry_closure_result,
        registry_coverage_result=registry_coverage_result,
    )


if __name__ == "__main__":
    sys.exit(main())
