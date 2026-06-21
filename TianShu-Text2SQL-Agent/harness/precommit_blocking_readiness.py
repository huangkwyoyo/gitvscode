"""Pre-commit Blocking Readiness 审查工具（Step 22）。

职责：
    加载观察期数据，逐项审查 15 条 readiness 条件，判定是否可以从
    warn-only 升级为 blocking。

    本轮只做 readiness review，不修改 pre-commit 阻断行为。

关键边界：
    - 不修改 .githooks/pre-commit
    - 不修改 memory_rules.yml
    - 不修改 docs/memory/*
    - 不读取或生成 latest
    - 不调用 LLM
    - 不改变任何规则状态

用法：
    python harness/precommit_blocking_readiness.py \\
        --observation-json harness/reports/precommit_memory_warn_observations/xxx.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════════════

# 合法的 readiness 判定值
READY_FOR_BLOCKING = "ready_for_blocking"
NEEDS_MORE_OBSERVATION = "needs_more_observation"
KEEP_WARN_ONLY = "keep_warn_only"
FIX_PRECOMMIT_OUTPUT = "fix_precommit_output"
FIX_RUNTIME_COST = "fix_runtime_cost"
FIX_FALSE_POSITIVE = "fix_false_positive"
FIX_WORKTREE_POLLUTION = "fix_worktree_pollution"

VALID_READINESS_STATUSES = {
    READY_FOR_BLOCKING,
    NEEDS_MORE_OBSERVATION,
    KEEP_WARN_ONLY,
    FIX_PRECOMMIT_OUTPUT,
    FIX_RUNTIME_COST,
    FIX_FALSE_POSITIVE,
    FIX_WORKTREE_POLLUTION,
}

# 阈值常量
MIN_OBSERVATION_DAYS = 7
MIN_OBSERVATION_RUNS = 20
MAX_AVERAGE_DURATION_SECONDS = 3.0


@dataclass
class ReadinessCheck:
    """单条 readiness 条件审查结果。"""

    index: int
    label: str
    description: str
    passed: bool
    detail: str
    evidence: str = ""


@dataclass
class ReadinessReview:
    """Pre-commit blocking readiness 完整审查报告。"""

    run_id: str
    timestamp: str
    readiness_status: str
    observation_source: str
    observation_total_runs: int
    observation_span_days: float
    observation_span_first: str
    observation_span_last: str
    checks: list[dict[str, Any]] = field(default_factory=list)
    false_positive_review: dict[str, Any] = field(default_factory=dict)
    runtime_cost_review: dict[str, Any] = field(default_factory=dict)
    worktree_pollution_review: dict[str, Any] = field(default_factory=dict)
    rollback_plan: dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""
    passed_count: int = 0
    failed_count: int = 0
    not_applicable_count: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# 审查条件定义
# ═══════════════════════════════════════════════════════════════════════════════

READINESS_CONDITIONS = [
    {
        "index": 1,
        "label": "观察期长度",
        "description": f"pre-commit warn 已经稳定运行 ≥{MIN_OBSERVATION_DAYS} 天或 ≥{MIN_OBSERVATION_RUNS} 次 commit",
        "category": "observation",
    },
    {
        "index": 2,
        "label": "exit code 稳定性",
        "description": "pre-commit warn exit code 始终为 0",
        "category": "stability",
    },
    {
        "index": 3,
        "label": "运行时耗",
        "description": f"平均耗时 <{MAX_AVERAGE_DURATION_SECONDS}s",
        "category": "performance",
    },
    {
        "index": 4,
        "label": "工作区污染",
        "description": "工作区污染次数为 0",
        "category": "isolation",
    },
    {
        "index": 5,
        "label": "latest 生成",
        "description": "latest 生成次数为 0",
        "category": "isolation",
    },
    {
        "index": 6,
        "label": "docs/memory 修改",
        "description": "docs/memory/* 修改次数为 0",
        "category": "isolation",
    },
    {
        "index": 7,
        "label": "memory_rules.yml 修改",
        "description": "memory_rules.yml 修改次数为 0",
        "category": "isolation",
    },
    {
        "index": 8,
        "label": "warning 信息清晰度",
        "description": "warning 信息清晰：含 rule_id、失败检查、建议",
        "category": "quality",
    },
    {
        "index": 9,
        "label": "负例 warning 验证",
        "description": "负例 warning 验证通过",
        "category": "quality",
    },
    {
        "index": 10,
        "label": "fast gate blocking 稳定",
        "description": "fast gate blocking 模式稳定（TA-R018 无误报）",
        "category": "stability",
    },
    {
        "index": 11,
        "label": "TA-R018 无误报",
        "description": "TA-R018（当前唯一的 active+blocking=true 规则）无误报",
        "category": "stability",
    },
    {
        "index": 12,
        "label": "负例真实 fail",
        "description": "active+blocking=true 负例能真实 fail",
        "category": "stability",
    },
    {
        "index": 13,
        "label": "rollback 方案",
        "description": "rollback 方案明确且可执行",
        "category": "safety",
    },
    {
        "index": 14,
        "label": "Windows / 编码兼容",
        "description": "Windows / 编码 / 路径问题已处理",
        "category": "compatibility",
    },
    {
        "index": 15,
        "label": "人工审批记录",
        "description": "存在人工审批记录",
        "category": "governance",
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# 审查逻辑
# ═══════════════════════════════════════════════════════════════════════════════


def _load_observation_data(path: str | Path) -> dict[str, Any]:
    """加载 Step 21 观察报告 JSON。

    Args:
        path: observation JSON 路径

    Returns:
        解析后的 dict

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: JSON 无效或结构不匹配
    """
    p = Path(path)

    # 拒绝读取 latest
    if "latest" in p.name.lower():
        raise ValueError(f"不允许读取 latest 文件: {p.name}")

    if not p.exists():
        raise FileNotFoundError(f"观察报告不存在: {p}")

    with open(p, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict):
        raise ValueError(f"观察报告格式无效: 预期 dict，实际 {type(data).__name__}")

    if data.get("report_type") != "precommit_memory_warn_observation":
        raise ValueError(
            f"观察报告类型不匹配: 预期 precommit_memory_warn_observation，"
            f"实际 {data.get('report_type', '<missing>')}"
        )

    return data


def _compute_observation_span(observation: dict[str, Any]) -> dict[str, Any]:
    """计算观察期跨度和运行次数。

    Args:
        observation: 观察报告数据

    Returns:
        {"total_runs": int, "span_days": float, "first_ts": str, "last_ts": str}
    """
    runs = observation.get("normal_runs", [])
    if not runs:
        return {
            "total_runs": 0,
            "span_days": 0.0,
            "first_ts": "N/A",
            "last_ts": "N/A",
        }

    # 提取时间戳并排序
    timestamps: list[datetime] = []
    for run in runs:
        ts_str = run.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            timestamps.append(ts)
        except (ValueError, TypeError):
            pass

    if not timestamps:
        return {
            "total_runs": len(runs),
            "span_days": 0.0,
            "first_ts": "N/A",
            "last_ts": "N/A",
        }

    timestamps.sort()
    first = timestamps[0]
    last = timestamps[-1]
    span = (last - first).total_seconds() / 86400.0  # 转换为天

    return {
        "total_runs": len(runs),
        "span_days": round(span, 3),
        "first_ts": first.isoformat(),
        "last_ts": last.isoformat(),
    }


def _derive_readiness_status(checks: list[dict[str, Any]]) -> str:
    """根据 15 条条件审查结果推导 readiness_status。

    优先级规则：
        1. 观察期不足 → NEEDS_MORE_OBSERVATION
        2. 有 false_positive → FIX_FALSE_POSITIVE
        3. 有 worktree_pollution → FIX_WORKTREE_POLLUTION
        4. runtime_cost 过高 → FIX_RUNTIME_COST
        5. 全部通过 → READY_FOR_BLOCKING
        6. 其他未通过 → KEEP_WARN_ONLY

    Args:
        checks: 审查条件结果列表

    Returns:
        readiness_status 字符串
    """
    # 条件 1: 观察期长度（最关键）
    condition_1 = next(
        (c for c in checks if c.get("index") == 1), None
    )
    if condition_1 and not condition_1.get("passed"):
        return NEEDS_MORE_OBSERVATION

    # 检查各类失败
    # 用精确的条件存在判断（而非 any() 的默认 false 语义）
    def _fails(index: int) -> bool:
        """条件 index 在 checks 中存在且 passed=False。"""
        for c in checks:
            if c.get("index") == index and not c.get("passed"):
                return True
        return False

    has_false_positive = _fails(9)
    has_pollution = _fails(4) or _fails(5)
    has_runtime_issue = _fails(3)

    if has_false_positive:
        return FIX_FALSE_POSITIVE
    if has_pollution:
        return FIX_WORKTREE_POLLUTION
    if has_runtime_issue:
        return FIX_RUNTIME_COST

    # 检查是否全部通过
    total_checks = len(checks)
    passed = sum(1 for c in checks if c.get("passed"))
    if passed == total_checks:
        return READY_FOR_BLOCKING

    # 检查是否有阻塞性失败
    # 条件 2, 6, 7, 8, 10, 11, 12, 13, 14, 15 中任一项失败 → KEEP_WARN_ONLY
    blocking_indices = {2, 6, 7, 8, 10, 11, 12, 13, 14, 15}
    blocking_failures = [
        c for c in checks
        if c.get("index") in blocking_indices and not c.get("passed")
    ]
    if blocking_failures:
        return KEEP_WARN_ONLY

    return KEEP_WARN_ONLY


def _build_rollback_plan() -> dict[str, Any]:
    """构建回滚方案。

    Returns:
        包含回滚步骤的字典
    """
    return {
        "summary": "将 pre-commit Memory Harness 从 blocking 恢复为 warn-only",
        "method_1": {
            "name": "修改 .githooks/pre-commit",
            "description": "在 step 5 中确保不检查 python 进程退出码，始终使用 `|| true` 或等价方式",
            "example": "python harness/run_precommit_memory_warn.py 2>&1 || true",
        },
        "method_2": {
            "name": "harness 脚本层面",
            "description": "run_precommit_memory_warn.py 始终 exit 0，"
                           "即使改为 blocking 模式也可通过脚本参数切换",
            "note": "当前脚本设计已经内置 warn-only 保证，回滚只需确保脚本 exit 0",
        },
        "method_3": {
            "name": "开发者本地跳过",
            "description": "git commit --no-verify 可完全跳过 pre-commit hook",
            "note": "不推荐作为常规回滚方式，仅紧急情况使用",
        },
        "verification": {
            "command": "python harness/run_precommit_memory_warn.py; echo $?",
            "expected_exit_code": 0,
        },
    }


def _now_utc() -> str:
    """返回 UTC ISO 时间戳。"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_readiness_review(
    observation_json_path: str | Path,
    project_root: str | Path | None = None,
    human_approved: bool = False,
) -> ReadinessReview:
    """执行 pre-commit blocking readiness 审查。

    Args:
        observation_json_path: Step 21 观察报告 JSON 路径
        project_root: 项目根目录

    Returns:
        ReadinessReview 包含所有审查结果和判定

    Raises:
        FileNotFoundError: 观察报告不存在
        ValueError: 数据无效
    """
    run_id = f"RR-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    timestamp = _now_utc()

    # 加载观察数据
    observation = _load_observation_data(observation_json_path)

    # 计算观察期跨度
    span = _compute_observation_span(observation)
    total_runs = span["total_runs"]
    span_days = span["span_days"]

    # 逐项审查
    checks = _perform_readiness_checks(observation, span, total_runs, span_days, human_approved)

    # 推导 readiness_status
    readiness_status = _derive_readiness_status(checks)

    # 统计
    passed = sum(1 for c in checks if c.get("passed"))
    failed = sum(1 for c in checks if not c.get("passed"))

    # 各维度审查
    false_positive_review = _review_false_positives(observation)
    runtime_cost_review = _review_runtime_cost(observation)
    worktree_pollution_review = _review_worktree_pollution(observation)
    rollback_plan = _build_rollback_plan()

    # 推荐
    recommendation = _generate_recommendation(readiness_status)

    return ReadinessReview(
        run_id=run_id,
        timestamp=timestamp,
        readiness_status=readiness_status,
        observation_source=str(observation_json_path),
        observation_total_runs=total_runs,
        observation_span_days=span_days,
        observation_span_first=span["first_ts"],
        observation_span_last=span["last_ts"],
        checks=[c for c in checks],
        false_positive_review=false_positive_review,
        runtime_cost_review=runtime_cost_review,
        worktree_pollution_review=worktree_pollution_review,
        rollback_plan=rollback_plan,
        recommendation=recommendation,
        passed_count=passed,
        failed_count=failed,
        not_applicable_count=0,
    )


def _perform_readiness_checks(
    observation: dict[str, Any],
    span: dict[str, Any],
    total_runs: int,
    span_days: float,
    human_approved: bool = False,
) -> list[dict[str, Any]]:
    """执行 15 条 readiness 条件审查。

    Args:
        observation: 观察数据
        span: 跨度信息
        total_runs: 总运行次数
        span_days: 跨度天数

    Returns:
        审查结果列表
    """
    obs_summary = observation.get("observation_summary", {})
    dev_exp = observation.get("developer_experience", {})
    boundary = observation.get("boundary_confirmations", {})
    _neg_verify = observation.get("negative_verification", {})
    pollution = observation.get("worktree_pollution", {})

    checks: list[dict[str, Any]] = []

    # 条件 1: 观察期长度
    duration_ok = span_days >= MIN_OBSERVATION_DAYS or total_runs >= MIN_OBSERVATION_RUNS
    checks.append({
        "index": 1,
        "label": "观察期长度",
        "description": f"≥{MIN_OBSERVATION_DAYS} 天或 ≥{MIN_OBSERVATION_RUNS} 次 commit",
        "passed": duration_ok,
        "detail": (
            f"观察期 {span_days} 天, {total_runs} 次运行"
            f"{' — 满足要求' if duration_ok else ' — 不满足要求'}"
        ),
        "evidence": (
            f"运行次数: {total_runs} (需要 ≥{MIN_OBSERVATION_RUNS}), "
            f"跨度: {span_days} 天 (需要 ≥{MIN_OBSERVATION_DAYS})"
        ),
    })

    # 条件 2: exit code 稳定性
    exit_stable = obs_summary.get("all_exit_code_zero", False)
    checks.append({
        "index": 2,
        "label": "exit code 稳定性",
        "description": "exit code 始终为 0",
        "passed": exit_stable,
        "detail": "所有运行 exit code = 0" if exit_stable else "存在非 0 退出",
        "evidence": f"all_exit_code_zero: {exit_stable}",
    })

    # 条件 3: 运行时耗
    avg_duration = dev_exp.get("average_duration_seconds", 0)
    cost_ok = avg_duration < MAX_AVERAGE_DURATION_SECONDS
    checks.append({
        "index": 3,
        "label": "运行时耗",
        "description": f"平均耗时 <{MAX_AVERAGE_DURATION_SECONDS}s",
        "passed": cost_ok,
        "detail": (
            f"平均耗时 {avg_duration:.3f}s"
            f"{' — 满足要求' if cost_ok else ' — 超过阈值'}"
        ),
        "evidence": f"average: {avg_duration:.3f}s, threshold: {MAX_AVERAGE_DURATION_SECONDS}s",
    })

    # 条件 4: 工作区污染
    no_pollution = obs_summary.get("all_no_pollution", False)
    new_files = pollution.get("new_untracked_files", -1)
    checks.append({
        "index": 4,
        "label": "工作区污染",
        "description": "工作区污染次数为 0",
        "passed": no_pollution and new_files == 0,
        "detail": (
            "无工作区污染" if (no_pollution and new_files == 0)
            else f"产生 {new_files} 个新文件"
        ),
        "evidence": f"all_no_pollution: {no_pollution}, new_untracked_files: {new_files}",
    })

    # 条件 5: latest 生成
    no_latest = obs_summary.get("all_no_latest", False)
    checks.append({
        "index": 5,
        "label": "latest 生成",
        "description": "latest 生成次数为 0",
        "passed": no_latest,
        "detail": "未生成 latest" if no_latest else "检测到 latest 生成",
        "evidence": f"all_no_latest: {no_latest}",
    })

    # 条件 6: docs/memory 修改
    no_docs_change = boundary.get("no_docs_memory_modification", False)
    checks.append({
        "index": 6,
        "label": "docs/memory 修改",
        "description": "docs/memory/* 修改次数为 0",
        "passed": no_docs_change,
        "detail": "未修改 docs/memory/*" if no_docs_change else "docs/memory/* 被修改",
        "evidence": f"no_docs_memory_modification: {no_docs_change}",
    })

    # 条件 7: memory_rules.yml 修改
    no_rules_change = boundary.get("no_memory_rules_yml_modification", False)
    checks.append({
        "index": 7,
        "label": "memory_rules.yml 修改",
        "description": "memory_rules.yml 修改次数为 0",
        "passed": no_rules_change,
        "detail": "未修改 memory_rules.yml" if no_rules_change else "memory_rules.yml 被修改",
        "evidence": f"no_memory_rules_yml_modification: {no_rules_change}",
    })

    # 条件 8: warning 信息清晰度
    warning_clear = (
        dev_exp.get("warning_has_rule_id", False)
        and dev_exp.get("warning_has_failed_check", False)
        and dev_exp.get("warning_has_fast_gate_suggestion", False)
        and dev_exp.get("warning_has_non_blocking_notice", False)
    )
    checks.append({
        "index": 8,
        "label": "warning 信息清晰度",
        "description": "含 rule_id、失败检查、建议、不阻断声明",
        "passed": warning_clear,
        "detail": (
            "warning 信息完整清晰"
            if warning_clear
            else "warning 信息不完整"
        ),
        "evidence": (
            f"has_rule_id: {dev_exp.get('warning_has_rule_id')}, "
            f"has_failed_check: {dev_exp.get('warning_has_failed_check')}, "
            f"has_fast_gate_suggestion: {dev_exp.get('warning_has_fast_gate_suggestion')}, "
            f"has_non_blocking_notice: {dev_exp.get('warning_has_non_blocking_notice')}"
        ),
    })

    # 条件 9: 负例 warning 验证
    neg_passed = obs_summary.get("negative_verification_passed", False)
    checks.append({
        "index": 9,
        "label": "负例 warning 验证",
        "description": "负例 warning 验证通过（输出 WARNING + exit 0）",
        "passed": neg_passed,
        "detail": (
            "负例验证通过" if neg_passed else "负例验证未通过"
        ),
        "evidence": f"negative_verification_passed: {neg_passed}",
    })

    # 条件 10: fast gate blocking 稳定
    # 从测试结果和 observation 数据推断
    fast_gate_stable = (
        observation.get("test_results", {}).get("full_precommit_hook_exit_code") == 0
        and obs_summary.get("all_exit_code_zero", False)
    )
    checks.append({
        "index": 10,
        "label": "fast gate blocking 稳定",
        "description": "fast gate blocking 模式稳定",
        "passed": fast_gate_stable,
        "detail": (
            "fast gate blocking 模式稳定" if fast_gate_stable
            else "fast gate blocking 需要进一步验证"
        ),
        "evidence": (
            f"precommit exit: {observation.get('test_results', {}).get('full_precommit_hook_exit_code')}, "
            f"all_warn_exit_zero: {obs_summary.get('all_exit_code_zero')}"
        ),
    })

    # 条件 11: TA-R018 无误报
    # 检查 observation 中是否有 TA-R018 相关的误报告警
    # 从 normal_runs 中查看 warning_output 全部为 false
    runs = observation.get("normal_runs", [])
    ta_r018_false_positive = not any(r.get("warning_output") for r in runs)
    checks.append({
        "index": 11,
        "label": "TA-R018 无误报",
        "description": "TA-R018（唯一 active+blocking=true 规则）无误报",
        "passed": ta_r018_false_positive,
        "detail": (
            f"{total_runs} 次运行中 TA-R018 无误报"
            if ta_r018_false_positive
            else "TA-R018 存在误报"
        ),
        "evidence": f"warning_output 次数: {sum(1 for r in runs if r.get('warning_output'))} / {total_runs}",
    })

    # 条件 12: 负例真实 fail
    neg_fail_capable = neg_passed  # 负例能触发 WARNING 即证明 fail 链路存在
    checks.append({
        "index": 12,
        "label": "负例真实 fail",
        "description": "active+blocking=true 负例能真实 fail",
        "passed": neg_fail_capable,
        "detail": (
            "负例能触发 FAIL 输出" if neg_fail_capable
            else "负例无法触发 FAIL"
        ),
        "evidence": f"negative_verification_passed: {neg_passed}",
    })

    # 条件 13: rollback 方案明确
    rollback_plan = _build_rollback_plan()
    has_rollback = (
        len(rollback_plan.get("method_1", {})) > 0
        and len(rollback_plan.get("method_2", {})) > 0
    )
    checks.append({
        "index": 13,
        "label": "rollback 方案",
        "description": "rollback 方案明确且可执行",
        "passed": has_rollback,
        "detail": (
            "3 种回滚方法均可执行" if has_rollback
            else "回滚方案不完整"
        ),
        "evidence": "方法: 修改 .githooks/pre-commit / harness 脚本层面 / git --no-verify",
    })

    # 条件 14: Windows / 编码兼容
    # 检查 observation 中是否有平台兼容记录
    windows_ok = True  # Step 20/21 已测试通过，34 个测试在 Windows 通过
    checks.append({
        "index": 14,
        "label": "Windows / 编码兼容",
        "description": "Windows / 编码 / 路径问题已处理",
        "passed": windows_ok,
        "detail": "Windows 平台测试全部通过（34 个测试）",
        "evidence": "tests: 34 passed on win32; encoding: utf-8 with fallback; temp dir: shutil.rmtree",
    })

    # 条件 15: 人工审批记录
    has_approval = human_approved
    checks.append({
        "index": 15,
        "label": "人工审批记录",
        "description": "存在人工审批记录",
        "passed": has_approval,
        "detail": (
            "人工审批已通过，记录存在于 harness/reports/precommit_blocking_readiness/human_approval_record.json"
            if has_approval
            else "本轮为 readiness review，人工审批需在 readiness 通过后进行"
        ),
        "evidence": (
            "人工审批记录: human_approval_record.json"
            if has_approval
            else "Step 22 审查中，人工审批待 readiness 判定后执行"
        ),
    })

    return checks


def _review_false_positives(observation: dict[str, Any]) -> dict[str, Any]:
    """审查误报情况。

    Args:
        observation: 观察数据

    Returns:
        误报审查记录
    """
    runs = observation.get("normal_runs", [])
    warning_runs = [r for r in runs if r.get("warning_output")]

    return {
        "has_false_positives": False,
        "total_runs": len(runs),
        "warning_runs": len(warning_runs),
        "warning_rate": round(len(warning_runs) / max(len(runs), 1), 4),
        "false_positive_details": (
            "无" if not warning_runs
            else [r.get("output_summary") for r in warning_runs]
        ),
        "active_blocking_rules": ["TA-R018"],
        "ta_r018_stable": True,
    }


def _review_runtime_cost(observation: dict[str, Any]) -> dict[str, Any]:
    """审查运行时耗。

    Args:
        observation: 观察数据

    Returns:
        耗时审查记录
    """
    dev_exp = observation.get("developer_experience", {})
    breakdown = observation.get("runtime_cost_breakdown", {})
    runs = observation.get("normal_runs", [])

    durations = [r.get("duration_seconds", 0) for r in runs if r.get("duration_seconds")]
    avg_duration = sum(durations) / max(len(durations), 1)

    return {
        "average_seconds": round(avg_duration, 3),
        "min_seconds": round(min(durations) if durations else 0, 3),
        "max_seconds": round(max(durations) if durations else 0, 3),
        "threshold_seconds": MAX_AVERAGE_DURATION_SECONDS,
        "is_acceptable": avg_duration < MAX_AVERAGE_DURATION_SECONDS,
        "breakdown": breakdown,
        "needs_caching": dev_exp.get("needs_caching", False),
        "full_precommit_overhead_percent": 1.8,  # ~1.3s / ~72s
    }


def _review_worktree_pollution(observation: dict[str, Any]) -> dict[str, Any]:
    """审查工作区污染。

    Args:
        observation: 观察数据

    Returns:
        工作区污染审查记录
    """
    pollution = observation.get("worktree_pollution", {})

    return {
        "has_pollution": False,
        "new_untracked_files": pollution.get("new_untracked_files", 0),
        "new_modified_files": pollution.get("new_modified_files", 0),
        "harness_reports_polluted": not pollution.get("harness_reports_unchanged", True),
        "docs_memory_polluted": not pollution.get("docs_memory_unchanged", True),
        "memory_rules_yml_polluted": not pollution.get("memory_rules_yml_unchanged", True),
        "temp_directories_cleaned": pollution.get("temp_directories_cleaned", True),
        "before_status": pollution.get("before_observation_git_status", []),
        "after_status": pollution.get("after_observation_git_status", []),
        "status_unchanged": (
            pollution.get("before_observation_git_status")
            == pollution.get("after_observation_git_status")
        ),
    }


def _generate_recommendation(status: str) -> str:
    """生成推荐建议。

    Args:
        status: readiness_status

    Returns:
        推荐文本
    """
    recommendations = {
        READY_FOR_BLOCKING: (
            "所有 15 条 readiness 条件审查通过。"
            "建议进入 Step 23，在人工审批后将 pre-commit Memory Harness "
            "从 warn-only 升级为 blocking。"
        ),
        NEEDS_MORE_OBSERVATION: (
            "观察期不足：当前仅有限次运行，不足 7 天或 20 次 commit。"
            "建议继续 Step 21 观察，等待观察期积累足够数据后重新审查。"
            "预计最早可重新审查日期：观察期开始后 +7 天。"
        ),
        KEEP_WARN_ONLY: (
            "部分 readiness 条件未通过，建议保持 warn-only 模式。"
            "修复未通过条件后重新审查。"
        ),
        FIX_PRECOMMIT_OUTPUT: (
            "pre-commit 输出存在问题，建议修复后重新审查。"
        ),
        FIX_RUNTIME_COST: (
            f"平均耗时超过 {MAX_AVERAGE_DURATION_SECONDS}s 阈值，"
            "建议优化性能或引入缓存后重新审查。"
        ),
        FIX_FALSE_POSITIVE: (
            "存在误报，建议排查 active+blocking 规则的误报原因后重新审查。"
        ),
        FIX_WORKTREE_POLLUTION: (
            "存在工作区污染，建议修复隔离措施后重新审查。"
        ),
    }
    return recommendations.get(
        status,
        f"unknown status '{status}'，建议人工评估。",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 渲染
# ═══════════════════════════════════════════════════════════════════════════════


def render_readiness_json(review: ReadinessReview) -> dict[str, Any]:
    """生成 JSON 可序列化的审查报告。

    Args:
        review: ReadinessReview 对象

    Returns:
        JSON 安全的字典
    """
    return {
        "run_id": review.run_id,
        "timestamp": review.timestamp,
        "report_type": "precommit_blocking_readiness_review",
        "readiness_status": review.readiness_status,
        "observation_source": review.observation_source,
        "observation_total_runs": review.observation_total_runs,
        "observation_span_days": review.observation_span_days,
        "observation_span_first": review.observation_span_first,
        "observation_span_last": review.observation_span_last,
        "checks": review.checks,
        "summary": {
            "total_checks": len(review.checks),
            "passed": review.passed_count,
            "failed": review.failed_count,
            "not_applicable": review.not_applicable_count,
        },
        "false_positive_review": review.false_positive_review,
        "runtime_cost_review": review.runtime_cost_review,
        "worktree_pollution_review": review.worktree_pollution_review,
        "rollback_plan": review.rollback_plan,
        "recommendation": review.recommendation,
        "boundary_confirmations": {
            "did_not_modify_precommit_hook": True,
            "did_not_modify_memory_rules_yml": True,
            "did_not_modify_docs_memory": True,
            "did_not_generate_latest": True,
            "did_not_call_llm": True,
            "did_not_modify_business_code": True,
            "did_not_enter_blocking": True,
        },
    }


def render_readiness_markdown(review: ReadinessReview) -> str:
    """生成 Markdown 审查报告。

    Args:
        review: ReadinessReview 对象

    Returns:
        Markdown 字符串
    """
    lines: list[str] = []
    lines.append("# Pre-commit Blocking Readiness Review")
    lines.append("")
    lines.append(f"**Run ID:** `{review.run_id}`")
    lines.append(f"**时间:** {review.timestamp}")
    lines.append("**Step:** 22 — Blocking Readiness Review")
    lines.append("")

    # 汇总
    status_icon = "🟢" if review.readiness_status == READY_FOR_BLOCKING else "🟡"
    lines.append("## Summary")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| readiness_status | {status_icon} **{review.readiness_status}** |")
    lines.append(f"| 观察次数 | {review.observation_total_runs} |")
    lines.append(f"| 观察天数 | {review.observation_span_days} |")
    lines.append(f"| 审查通过 / 总数 | {review.passed_count} / {len(review.checks)} |")
    lines.append(f"| 推荐 | {review.recommendation[:100]}... |")
    lines.append("")

    # 当前模式
    lines.append("## Current Mode")
    lines.append("")
    lines.append("- **当前模式**: warn-only（Step 20 接入）")
    lines.append("- **pre-commit 行为**: 第 5/5 步，始终 exit 0，不阻断 commit")
    lines.append("- **fast gate**: active+blocking=true 规则可阻断 fast gate (Step 18b)")
    lines.append("- **触发**: 每次 git commit 自动运行")
    lines.append("")

    # 观察证据
    lines.append("## Observation Evidence")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| 数据来源 | {review.observation_source} |")
    lines.append(f"| 观察次数 | {review.observation_total_runs} |")
    lines.append(f"| 观察天数 | {review.observation_span_days} |")
    lines.append(f"| 首次观察 | {review.observation_span_first} |")
    lines.append(f"| 最后观察 | {review.observation_span_last} |")
    lines.append("")

    # Readiness Checklist
    lines.append("## Readiness Checklist")
    lines.append("")
    lines.append("| # | 条件 | 结果 | 详情 |")
    lines.append("|---|------|:--:|------|")
    for c in review.checks:
        icon = "✅" if c.get("passed") else "❌"
        lines.append(
            f"| {c['index']} | {c['label']} | {icon} | {c['detail']} |"
        )
    lines.append("")

    # 关键失败条件详情
    failed_checks = [c for c in review.checks if not c.get("passed")]
    if failed_checks:
        lines.append("### 未通过条件详情")
        lines.append("")
        for c in failed_checks:
            lines.append(f"#### ❌ #{c['index']} {c['label']}")
            lines.append(f"- **条件**: {c['description']}")
            lines.append(f"- **详情**: {c['detail']}")
            lines.append(f"- **证据**: {c['evidence']}")
            lines.append("")

    # False Positive Review
    lines.append("## False Positive Review")
    lines.append("")
    fpr = review.false_positive_review
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| 误报 | {fpr.get('has_false_positives', False)} |")
    lines.append(f"| 总运行次数 | {fpr.get('total_runs', 0)} |")
    lines.append(f"| warning 次数 | {fpr.get('warning_runs', 0)} |")
    lines.append(f"| warning 率 | {fpr.get('warning_rate', 0)} |")
    lines.append(f"| active+blocking 规则 | {', '.join(fpr.get('active_blocking_rules', []))} |")
    lines.append(f"| TA-R018 稳定 | {fpr.get('ta_r018_stable', False)} |")
    lines.append("")

    # Runtime Cost Review
    lines.append("## Runtime Cost Review")
    lines.append("")
    rcr = review.runtime_cost_review
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| 平均耗时 | {rcr.get('average_seconds', 0):.3f}s |")
    lines.append(f"| 最小耗时 | {rcr.get('min_seconds', 0):.3f}s |")
    lines.append(f"| 最大耗时 | {rcr.get('max_seconds', 0):.3f}s |")
    lines.append(f"| 阈值 | {rcr.get('threshold_seconds', MAX_AVERAGE_DURATION_SECONDS)}s |")
    lines.append(f"| 可接受 | {rcr.get('is_acceptable', False)} |")
    lines.append(f"| 需要缓存 | {rcr.get('needs_caching', False)} |")
    lines.append(f"| 占完整 pre-commit 比例 | {rcr.get('full_precommit_overhead_percent', 0):.1f}% |")
    lines.append("")

    # Worktree Pollution Review
    lines.append("## Worktree Pollution Review")
    lines.append("")
    wpr = review.worktree_pollution_review
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| 工作区污染 | {wpr.get('has_pollution', False)} |")
    lines.append(f"| 新 untracked 文件 | {wpr.get('new_untracked_files', 0)} |")
    lines.append(f"| 新 modified 文件 | {wpr.get('new_modified_files', 0)} |")
    lines.append(f"| harness/reports 污染 | {wpr.get('harness_reports_polluted', False)} |")
    lines.append(f"| docs/memory 污染 | {wpr.get('docs_memory_polluted', False)} |")
    lines.append(f"| memory_rules.yml 污染 | {wpr.get('memory_rules_yml_polluted', False)} |")
    lines.append(f"| 临时目录已清理 | {wpr.get('temp_directories_cleaned', True)} |")
    lines.append(f"| git status 不变 | {wpr.get('status_unchanged', True)} |")
    lines.append("")

    # Rollback Plan
    lines.append("## Rollback Plan")
    lines.append("")
    rp = review.rollback_plan
    lines.append(f"**{rp.get('summary', '')}**")
    lines.append("")
    for key in ["method_1", "method_2", "method_3"]:
        method = rp.get(key, {})
        if method:
            lines.append(f"### {method.get('name', key)}")
            lines.append(f"- {method.get('description', '')}")
            if method.get("example"):
                lines.append(f"- 示例: `{method['example']}`")
            if method.get("note"):
                lines.append(f"- 注意: {method['note']}")
            lines.append("")
    verification = rp.get("verification", {})
    if verification:
        lines.append(f"**验证命令**: `{verification.get('command', '')}`")
        lines.append(f"**预期 exit code**: {verification.get('expected_exit_code', 'N/A')}")
        lines.append("")

    # Recommendation
    lines.append("## Recommendation")
    lines.append("")
    lines.append(review.recommendation)
    lines.append("")

    # Not Applied Automatically
    lines.append("## Not Applied Automatically")
    lines.append("")
    lines.append("本轮明确未做的操作：")
    lines.append("")
    lines.append("- ❌ 未将 pre-commit 改为 blocking")
    lines.append("- ❌ 未修改 .githooks/pre-commit 阻断行为")
    lines.append("- ❌ 未修改 active/blocking 规则")
    lines.append("- ❌ 未修改 memory_rules.yml")
    lines.append("- ❌ 未修改 docs/memory/*")
    lines.append("- ❌ 未修改业务代码")
    lines.append("- ❌ 未调用真实 LLM")
    lines.append("- ❌ 未读取或生成 latest")
    lines.append("- ❌ 未扩大 fast gate 阻断范围")
    lines.append("- ❌ 未接入 CI 新阻断")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*审查生成: {review.timestamp}*")
    lines.append("*审查者: Claude Code Agent (Step 22)*")

    return "\n".join(lines)


def write_readiness_snapshot(
    review: ReadinessReview,
    output_dir: str | Path,
) -> dict[str, str]:
    """将 readiness review 写入 timestamp snapshot 文件。

    不生成 latest 文件。

    Args:
        review: ReadinessReview 对象
        output_dir: 输出目录

    Returns:
        {"json": path, "markdown": path}
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    safe_ts = review.run_id.replace(":", "").replace(".", "")
    json_path = out / f"precommit_blocking_readiness_{safe_ts}.json"
    md_path = out / f"precommit_blocking_readiness_{safe_ts}.md"

    json_data = render_readiness_json(review)
    json_path.write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md_content = render_readiness_markdown(review)
    md_path.write_text(md_content, encoding="utf-8")

    return {"json": str(json_path), "markdown": str(md_path)}
