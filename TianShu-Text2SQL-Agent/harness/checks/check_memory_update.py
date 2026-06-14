"""
Memory Gate —— 检测关键路径变更后记忆文件是否同步更新。

验证以下内容：
    1. 当前 git diff 中是否有涉及关键路径的变更
    2. 如有，docs/memory/经验复盘.md 是否存在且包含对应条目
    3. docs/memory/ 下四个文件的存在性和基本结构
    4. （可选 --content-only）已有记忆条目的内容质量

本检查是 Phase 3 的核心组件——确保"改了代码就写记忆"不是靠人记，而是靠门禁拦。

用法：
    python harness/checks/check_memory_update.py              # 完整检查
    python harness/checks/check_memory_update.py --content-only  # 仅内容质量
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
    "src/ir.py",
    "src/sql_gen.py",
    "src/agent.py",
    "src/ambiguity.py",
    "src/schema_validators.py",
    "src/executor.py",
    "prompts/intent_classifier.md",
    "prompts/sql_planner.md",
    "prompts/sql_generator.md",
    "prompts/explainer.md",
    "harness/checks/",
    "harness/baselines/",
    "evals/",
    "config/agent_config.yml",
]

# 记忆文件清单
MEMORY_FILES = [
    "docs/memory/经验复盘.md",
    "docs/memory/变更复盘模板.md",
    "docs/memory/风险清单.md",
    "docs/memory/规则来源索引.md",
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
    "src/ir.py": "IR 数据结构变更 → 需在经验复盘.md 中记录：变更原因、向下兼容性、对已有评测的影响",
    "src/sql_gen.py": "SQL 生成/安全规则变更 → 需在经验复盘.md 中记录：为什么改规则、阻止了什么风险",
    "src/agent.py": "主循环逻辑变更 → 需在经验复盘.md 中记录：对 Agent 行为边界的改变",
    "src/ambiguity.py": "歧义检测/反问策略变更 → 需在经验复盘.md 中记录：阈值调整原因、预期效果",
    "src/schema_validators.py": "Schema 校验规则变更 → 需在经验复盘.md 中记录：新增/修改的校验项及原因",
    "prompts/": "Prompt 模板变更 → 需在经验复盘.md 中记录：改了什么、为什么改、需同步的回归用例",
    "harness/checks/": "门禁规则变更 → 需在经验复盘.md 中记录：为什么加/改/撤检查项",
    "harness/baselines/": "基线逻辑变更 → 需在经验复盘.md 中记录：对基线判定标准的影响",
    "evals/": "评测用例变更 → 需在风险清单.md 中评估：是否引入新的失败模式",
    "config/agent_config.yml": "Agent 配置变更 → 需在经验复盘.md 中记录：模型/阈值/超时变更的原因和预期效果",
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
    rule_count = content.count("| R")

    checks.append({
        "name": "规则来源索引条目数",
        "status": "PASS" if rule_count >= 5 else "WARN",
        "detail": f"共 {rule_count} 条规则索引",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def print_report(
    existence_result: dict[str, Any],
    coverage_result: dict[str, Any],
    quality_result: dict[str, Any],
    risk_result: dict[str, Any],
    index_result: dict[str, Any],
    changed_files: list[str],
) -> int:
    """打印检查报告，返回退出码"""
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

    # 汇总
    total_fail = (
        existence_result.get("fail_count", 0)
        + coverage_result.get("fail_count", 0)
        + quality_result.get("fail_count", 0)
        + risk_result.get("fail_count", 0)
        + index_result.get("fail_count", 0)
    )
    total_pass = (
        existence_result.get("pass_count", 0)
        + coverage_result.get("pass_count", 0)
        + quality_result.get("pass_count", 0)
        + risk_result.get("pass_count", 0)
        + index_result.get("pass_count", 0)
    )
    total_warn = sum(
        1 for result in [existence_result, coverage_result, quality_result, risk_result, index_result]
        for c in result.get("checks", [])
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
        "--config",
        default=None,
        help="Harness 配置文件路径（Memory Gate 不使用此参数，仅为兼容 run_harness.py 接口保留）",
    )
    args = parser.parse_args()

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
    )


if __name__ == "__main__":
    sys.exit(main())
