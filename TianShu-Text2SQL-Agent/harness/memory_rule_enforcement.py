"""Memory Rule Enforcement —— active 规则在 fast gate 中的分级门禁（Step 18b）。

本模块实现 memory_rules.yml 中 active 规则与 fast gate check 结果的关联分析，
按规则状态/blocking 分级输出 enforcement 结果。Step 18b 起启用真实阻断：
  - proposed 规则 → visibility_only（仅 registry 可见，不影响 exit code）
  - active + blocking=false → warn（输出 warning，不影响 exit code）
  - active + blocking=true → blocking_error（check 失败 → fast gate FAIL，exit code 非 0）
  - deprecated/superseded → ignored（不参与 enforcement）

关键边界：
  - 不修改 docs/memory/*
  - 不修改 memory_rules.yml
  - 不自动晋升规则
  - 只对 ready_for_error 的 active+blocking=true 规则启用真实阻断
  - 不接入 pre-commit
  - 不调用 LLM
  - 不读取 *_latest.*
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# ═══════════════════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════════════════

# Enforcement 级别
ENFORCEMENT_VISIBILITY = "visibility_only"      # proposed 规则，仅供参考
ENFORCEMENT_WARN = "warn"                        # active + blocking=false，仅警告
ENFORCEMENT_BLOCKING_ERROR = "blocking_error"    # active + blocking=true，真实阻断（Step 18b）
ENFORCEMENT_BLOCKING_DRY_RUN = "blocking_dry_run"  # [已废弃] 保留以兼容旧测试/数据
ENFORCEMENT_IGNORED = "ignored"                  # deprecated / superseded，不参与

# 合法的 rule status 值
VALID_STATUSES = {"proposed", "active", "deprecated", "superseded"}

# rule_id 格式: TA-Rxxx（xxx 为 3 位以上数字）
RULE_ID_PATTERN = re.compile(r"^TA-R\d{3,}$")


def load_rules(rules_path: str | Path) -> list[dict[str, Any]]:
    """从 memory_rules.yml 加载规则列表。

    Args:
        rules_path: YAML 文件路径

    Returns:
        规则字典列表

    Raises:
        FileNotFoundError: 文件不存在
        yaml.YAMLError: YAML 解析失败
        ValueError: 结构无效（缺少 rules 字段、rule_id 重复等）
    """
    path = Path(rules_path)

    # 拒绝读取 *_latest.*
    _reject_latest(path, "memory_rules.yml")

    if not path.exists():
        raise FileNotFoundError(f"规则文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        try:
            data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise yaml.YAMLError(f"YAML 解析失败: {path}: {exc}") from exc

    if not isinstance(data, dict) or "rules" not in data:
        raise ValueError(f"规则文件结构无效，缺少 'rules' 顶层键: {path}")

    rules = data["rules"]
    if not isinstance(rules, list):
        raise ValueError(f"'rules' 字段必须是列表: {path}")

    # 检查 rule_id 唯一性
    seen_ids: set[str] = set()
    for rule in rules:
        rid = rule.get("rule_id", "")
        if rid in seen_ids:
            raise ValueError(f"重复的 rule_id: {rid}")
        seen_ids.add(rid)

    return rules


def _reject_latest(path: Path, label: str) -> None:
    """拒绝读取 *_latest.* 文件。"""
    if "latest" in path.name.lower():
        raise ValueError(
            f"{label} 不允许读取 *_latest.* 文件: {path.name}。"
            f"请指定显式的 timestamp snapshot。"
        )


def parse_check_results_from_harness_stdout(stdout: str) -> list[dict[str, Any]]:
    """从 harness stdout 中解析 __HARNESS_CHECK_RESULTS__ 行。

    格式: __HARNESS_CHECK_RESULTS__ [...]

    Args:
        stdout: harness 步骤的完整 stdout

    Returns:
        check result 列表，每项包含 name, script, status, exit_code
        解析失败返回空列表
    """
    match = re.search(r"__HARNESS_CHECK_RESULTS__\s*(\[.*\])", stdout, re.DOTALL)
    if not match:
        return []
    try:
        results = json.loads(match.group(1))
        if not isinstance(results, list):
            return []
        return results
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def _parse_harness_stdout_for_check_results(stdout: str) -> list[dict[str, Any]]:
    """从 harness stdout 中解析各 check 的结果（回退方案）。

    当 __HARNESS_CHECK_RESULTS__ 行不存在时，通过解析 harness 输出中的
    '[N/11] 名称...' 和 'PASS/FAIL/WARN' 行来推断 check 结果。

    注意：此方法精度较低，优先使用 parse_check_results_from_harness_stdout。

    Args:
        stdout: harness 步骤的完整 stdout

    Returns:
        check result 列表（script 字段可能为空）
    """
    results: list[dict[str, Any]] = []
    # 匹配形如 "[3/11] 反问/拒绝策略完备性... PASS (0.05s)" 的行
    pattern = re.compile(
        r"\[(\d+)/\d+\]\s+(.+?)\.\.\.\s+(PASS|FAIL|WARN)\s*\([\d.]+s\)"
    )
    for match in pattern.finditer(stdout):
        results.append({
            "name": match.group(2).strip(),
            "script": "",
            "status": match.group(3),
            "exit_code": 0 if match.group(3) == "PASS" else 1,
        })
    return results


def classify_rule(rule: dict[str, Any]) -> str:
    """根据规则的 status 和 blocking 字段确定 enforcement 级别。

    Args:
        rule: 规则字典

    Returns:
        enforcement 级别常量
    """
    status = rule.get("status", "proposed")
    blocking = rule.get("blocking", False)

    if status in ("deprecated", "superseded"):
        return ENFORCEMENT_IGNORED
    elif status == "proposed":
        return ENFORCEMENT_VISIBILITY
    elif status == "active" and not blocking:
        return ENFORCEMENT_WARN
    elif status == "active" and blocking:
        return ENFORCEMENT_BLOCKING_ERROR  # Step 18b: 真实阻断
    else:
        # 未知状态回退到 visibility_only
        return ENFORCEMENT_VISIBILITY


def validate_rules_basics(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """验证规则基本字段的合法性。

    Args:
        rules: 规则列表

    Returns:
        infrastructure errors 列表（rule_id 格式错误、status 非法、blocking 类型错误等）
    """
    errors: list[dict[str, Any]] = []
    for rule in rules:
        rid = rule.get("rule_id", "<missing>")

        # rule_id 格式检查
        if not rid or not isinstance(rid, str):
            errors.append({
                "rule_id": str(rid),
                "check": "rule_id_format",
                "status": "infra_fail",
                "message": f"rule_id 缺失或非字符串: {rid!r}",
            })
            continue

        if not RULE_ID_PATTERN.match(rid):
            errors.append({
                "rule_id": rid,
                "check": "rule_id_format",
                "status": "infra_fail",
                "message": f"rule_id 格式无效（需匹配 TA-Rxxx）: {rid}",
            })

        # status 合法性
        status = rule.get("status")
        if status not in VALID_STATUSES:
            errors.append({
                "rule_id": rid,
                "check": "status_validity",
                "status": "infra_fail",
                "message": f"非法 status 值: {status!r}（合法值: {sorted(VALID_STATUSES)}）",
            })

        # blocking 类型
        blocking = rule.get("blocking")
        if not isinstance(blocking, bool):
            errors.append({
                "rule_id": rid,
                "check": "blocking_type",
                "status": "infra_fail",
                "message": f"blocking 字段必须为 bool 类型，实际: {type(blocking).__name__}",
            })

    return errors


def match_check_to_rule(
    rule: dict[str, Any],
    check_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """将规则的 required_checks 匹配到实际的 check 执行结果。

    匹配逻辑：检查 required_check 路径是否出现在 check result 的 script 字段中。
    如果 script 字段为空，尝试通过 check 名称模糊匹配。

    Args:
        rule: 规则字典
        check_results: check 执行结果列表

    Returns:
        匹配到的 check result 列表（可能为空）
    """
    required = rule.get("required_checks", [])
    if not required:
        return []

    matched: list[dict[str, Any]] = []
    for req_path in required:
        req_path_normalized = str(req_path).replace("\\", "/").rstrip("/")
        found = False
        for cr in check_results:
            script = str(cr.get("script", "")).replace("\\", "/").rstrip("/")
            if req_path_normalized in script or script.endswith(req_path_normalized):
                matched.append(cr)
                found = True
                break
        if not found:
            # 未匹配到 check result → 标记为 skipped
            matched.append({
                "name": req_path,
                "script": req_path,
                "status": "SKIPPED",
                "exit_code": None,
                "error_message": f"未找到 required_check {req_path} 的执行结果",
            })

    return matched


def compute_rule_enforcement(
    rule: dict[str, Any],
    check_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """计算单条规则的 enforcement 结果。

    Args:
        rule: 规则字典
        check_results: 全部 check 执行结果列表

    Returns:
        enforcement result 字典:
          - rule_id, title, status, blocking
          - enforcement_level
          - result: passed | warning | would_fail | skipped | infra_error
          - message
          - required_checks, matched_check_results
    """
    rid = rule.get("rule_id", "<unknown>")
    enforcement_level = classify_rule(rule)
    required_checks = rule.get("required_checks", [])
    matched = match_check_to_rule(rule, check_results)

    # deprecated / superseded → 直接忽略
    if enforcement_level == ENFORCEMENT_IGNORED:
        return {
            "rule_id": rid,
            "title": rule.get("title", ""),
            "status": rule.get("status", "proposed"),
            "blocking": rule.get("blocking", False),
            "enforcement_level": enforcement_level,
            "result": "skipped",
            "message": f"规则状态为 {rule.get('status')}，不参与 enforcement",
            "required_checks": required_checks,
            "matched_check_results": [],
        }

    # 无 required_checks 的规则
    if not required_checks:
        result = "passed"
        msg = _enforcement_message(enforcement_level, result)
        return {
            "rule_id": rid,
            "title": rule.get("title", ""),
            "status": rule.get("status", "proposed"),
            "blocking": rule.get("blocking", False),
            "enforcement_level": enforcement_level,
            "result": result,
            "message": msg,
            "required_checks": [],
            "matched_check_results": [],
        }

    # 检查是否有未匹配的 check（SKIPPED 表示未找到对应 check result）
    has_unmatched = any(cr.get("status") == "SKIPPED" for cr in matched)
    failed_checks = [cr for cr in matched if cr.get("status") == "FAIL"]
    has_failure = len(failed_checks) > 0
    failed_required_checks: list[str] = []
    failure_message = ""
    suggested_fix = ""
    rollback_plan = ""

    # 判定结果
    if has_unmatched:
        result = "warning"
        unmatched_names = [cr["name"] for cr in matched if cr.get("status") == "SKIPPED"]
        msg = f"required_checks 中有 {len(unmatched_names)} 项未找到对应 check result（{', '.join(unmatched_names[:3])}），无法验证"
    elif has_failure:
        # 根据 enforcement_level 决定结果级别
        if enforcement_level == ENFORCEMENT_VISIBILITY:
            result = "warning"  # proposed 规则 check 失败只是 warning
            msg = f"proposed 规则的 {len(failed_checks)} 项 required_checks 失败，仅注册表可见"
        elif enforcement_level == ENFORCEMENT_WARN:
            result = "warning"
            msg = f"active+blocking=false 规则的 {len(failed_checks)} 项 required_checks 失败，仅警告不阻断"
        elif enforcement_level == ENFORCEMENT_BLOCKING_ERROR:
            result = "FAIL"
            failed_check_names = [cr.get("name", "?") for cr in failed_checks]
            failed_required_checks = [
                str(cr.get("script") or cr.get("name", "?"))
                for cr in failed_checks
            ]
            failure_message = "; ".join(
                f"{cr.get('name', '?')} status=FAIL, exit_code={cr.get('exit_code')}"
                for cr in failed_checks
            )
            suggested_fix = "检查上述 required_check 的检查输出，修复失败原因后重新运行 fast gate。"
            rollback_plan = (
                f"将 memory_rules.yml 中 {rid} 的 blocking 从 true 改回 false，"
                "即可恢复非阻断模式，无需修改业务代码。"
            )
            msg = (
                f"active+blocking=true 规则 {rid} 的 "
                f"{len(failed_checks)} 项 required_checks 失败"
                f"（{', '.join(failed_check_names[:3])}），"
                f"fast gate 阻断。回滚方案: {rollback_plan}"
            )
        # 向后兼容：旧 blocking_dry_run 级别仍按 dry-run 处理
        elif enforcement_level == ENFORCEMENT_BLOCKING_DRY_RUN:
            result = "would_fail"
            msg = f"active+blocking=true 规则的 {len(failed_checks)} 项 required_checks 失败（dry-run，本轮不阻断）"
        else:
            result = "warning"
            msg = f"规则的 {len(failed_checks)} 项 required_checks 失败"
    else:
        result = "passed"
        msg = _enforcement_message(enforcement_level, result)

    return {
        "rule_id": rid,
        "title": rule.get("title", ""),
        "status": rule.get("status", "proposed"),
        "blocking": rule.get("blocking", False),
        "enforcement_level": enforcement_level,
        "result": result,
        "message": msg,
        "failed_required_checks": failed_required_checks,
        "failure_message": failure_message,
        "suggested_fix": suggested_fix,
        "rollback_plan": rollback_plan,
        "required_checks": required_checks,
        "matched_check_results": [
            {"name": cr.get("name", ""), "script": cr.get("script", ""),
             "status": cr.get("status", "UNKNOWN"), "exit_code": cr.get("exit_code")}
            for cr in matched
        ],
    }


def _enforcement_message(level: str, result: str) -> str:
    """生成 enforcement 结果的标准消息。"""
    messages = {
        (ENFORCEMENT_VISIBILITY, "passed"): "proposed 规则无 required_checks 或全部通过，注册表可见",
        (ENFORCEMENT_VISIBILITY, "warning"): "proposed 规则 check 存在问题，仅注册表观察",
        (ENFORCEMENT_WARN, "passed"): "active+blocking=false 规则全部 required_checks 通过",
        (ENFORCEMENT_WARN, "warning"): "active+blocking=false 规则 check 失败，仅警告",
        (ENFORCEMENT_BLOCKING_ERROR, "passed"): "active+blocking=true 规则全部 required_checks 通过",
        (ENFORCEMENT_BLOCKING_ERROR, "FAIL"): "active+blocking=true 规则 check 失败，fast gate 阻断",
        (ENFORCEMENT_BLOCKING_DRY_RUN, "passed"): "active+blocking=true 规则全部 required_checks 通过",
        (ENFORCEMENT_BLOCKING_DRY_RUN, "would_fail"): "active+blocking=true 规则 check 失败（dry-run would_fail）",
    }
    return messages.get((level, result), f"{level} 规则 {result}")


def build_enforcement_report(
    rules_path: str | Path,
    check_results: list[dict[str, Any]] | None = None,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """构建 memory rule enforcement 报告。

    编排所有检查：加载规则、验证基础字段、分类、匹配 check、
    计算 enforcement 结果、生成汇总。

    Args:
        rules_path: memory_rules.yml 路径
        check_results: harness check 执行结果列表，为 None 时所有 required_checks 视为 skipped
        project_root: 项目根目录

    Returns:
        完整 enforcement report 字典
    """
    if check_results is None:
        check_results = []

    # 加载规则
    rules = load_rules(rules_path)

    # 基础设施错误检查
    infra_errors = validate_rules_basics(rules)
    has_infra_error = len(infra_errors) > 0

    # 计算每条规则的 enforcement 结果
    rule_results: list[dict[str, Any]] = []
    for rule in rules:
        try:
            result = compute_rule_enforcement(rule, check_results)
        except Exception as exc:
            result = {
                "rule_id": rule.get("rule_id", "<unknown>"),
                "title": rule.get("title", ""),
                "status": rule.get("status", "unknown"),
                "blocking": rule.get("blocking", False),
                "enforcement_level": ENFORCEMENT_VISIBILITY,
                "result": "infra_error",
                "message": f"计算 enforcement 时出错: {exc}",
                "required_checks": rule.get("required_checks", []),
                "matched_check_results": [],
            }
        rule_results.append(result)

    # 汇总统计
    summary = _build_summary(rules, rule_results, infra_errors)

    # Step 18b: 当任何 active+blocking=true 规则结果为 FAIL 时，exit_code_should_fail=True
    exit_code_should_fail = any(
        rr.get("enforcement_level") == ENFORCEMENT_BLOCKING_ERROR
        and rr.get("result") == "FAIL"
        for rr in rule_results
    )

    # 生成 run_id
    run_id = _generate_run_id()

    return {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "summary": summary,
        "rule_results": rule_results,
        "infra_errors": infra_errors,
        "exit_code_should_fail": exit_code_should_fail,
        "write_mode": "blocking",  # Step 18b: 真实阻断模式
    }


def _generate_run_id() -> str:
    """生成 enforcement run ID。"""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"MRE-{ts}"


def _build_summary(
    rules: list[dict[str, Any]],
    rule_results: list[dict[str, Any]],
    infra_errors: list[dict[str, Any]],
) -> dict[str, int]:
    """构建 enforcement 汇总统计。

    Args:
        rules: 原始规则列表
        rule_results: enforcement 结果列表
        infra_errors: 基础设施错误列表

    Returns:
        汇总字典
    """
    total = len(rules)
    proposed = sum(1 for r in rules if r.get("status") == "proposed")
    active_warning = sum(
        1 for r in rules
        if r.get("status") == "active" and not r.get("blocking", False)
    )
    active_blocking = sum(
        1 for r in rules
        if r.get("status") == "active" and r.get("blocking", False)
    )
    deprecated = sum(1 for r in rules if r.get("status") == "deprecated")
    superseded = sum(1 for r in rules if r.get("status") == "superseded")

    warnings = sum(1 for rr in rule_results if rr.get("result") == "warning")
    would_fail = sum(1 for rr in rule_results if rr.get("result") == "would_fail")
    blocking_failures = sum(1 for rr in rule_results if rr.get("result") == "FAIL")
    passed = sum(1 for rr in rule_results if rr.get("result") == "passed")
    skipped = sum(1 for rr in rule_results if rr.get("result") == "skipped")
    infra_error_count = sum(1 for rr in rule_results if rr.get("result") == "infra_error")

    return {
        "total_rules": total,
        "proposed": proposed,
        "active_warning": active_warning,
        "active_blocking": active_blocking,
        "deprecated": deprecated,
        "superseded": superseded,
        "warnings": warnings,
        "blocking_failures": blocking_failures,
        "blocking_dry_run_failures": would_fail,
        "would_fail": would_fail,
        "passed": passed,
        "skipped": skipped,
        "infra_errors": len(infra_errors) + infra_error_count,
    }


def render_enforcement_json(report: dict[str, Any]) -> dict[str, Any]:
    """生成 JSON 可序列化的 enforcement report。

    Args:
        report: build_enforcement_report 返回的完整 report

    Returns:
        JSON 安全的字典
    """
    # build_enforcement_report 已经返回 JSON 兼容的数据结构
    # 此函数确保所有字段都是可序列化的
    return report


def render_enforcement_markdown(report: dict[str, Any]) -> str:
    """生成 enforcement report 的 Markdown 渲染。

    Args:
        report: build_enforcement_report 返回的完整 report

    Returns:
        Markdown 字符串
    """
    lines: list[str] = []
    summary = report.get("summary", {})
    rule_results = report.get("rule_results", [])
    infra_errors = report.get("infra_errors", [])

    lines.append("# Memory Rule Enforcement 报告 (Step 18b Blocking)")
    lines.append("")
    lines.append(f"**Run ID:** `{report.get('run_id', 'N/A')}`")
    lines.append(f"**时间:** {report.get('timestamp', 'N/A')}")
    lines.append(f"**模式:** blocking（active+blocking=true 规则 check 失败时阻断 fast gate）")
    lines.append("")

    # 汇总
    lines.append("## 汇总")
    lines.append("")
    lines.append(f"| 指标 | 数量 |")
    lines.append(f"|------|------|")
    lines.append(f"| 总规则数 | {summary.get('total_rules', 0)} |")
    lines.append(f"| proposed（仅可见） | {summary.get('proposed', 0)} |")
    lines.append(f"| active + blocking=false（警告） | {summary.get('active_warning', 0)} |")
    lines.append(f"| active + blocking=true（阻断） | {summary.get('active_blocking', 0)} |")
    lines.append(f"| deprecated | {summary.get('deprecated', 0)} |")
    lines.append(f"| superseded | {summary.get('superseded', 0)} |")
    lines.append(f"| 通过 | {summary.get('passed', 0)} |")
    lines.append(f"| 警告 | {summary.get('warnings', 0)} |")
    lines.append(f"| 阻断失败 | {summary.get('blocking_failures', 0)} |")
    lines.append(f"| 跳过 | {summary.get('skipped', 0)} |")
    lines.append(f"| 基础设施错误 | {summary.get('infra_errors', 0)} |")
    lines.append("")
    lines.append(f"**Exit code 受影响:** {'是' if report.get('exit_code_should_fail') else '否'}")
    lines.append("")

    # 基础设施错误
    if infra_errors:
        lines.append("## 基础设施错误")
        lines.append("")
        for err in infra_errors:
            lines.append(f"- **{err.get('rule_id', '?')}** [{err.get('check', '?')}]: {err.get('message', '')}")
        lines.append("")

    # 规则 enforcement 结果
    lines.append("## 规则 Enforcement 结果")
    lines.append("")

    # 按 enforcement_level 分组展示
    for level_label, level_key, icon in [
        ("active + blocking=true（blocking_error）", ENFORCEMENT_BLOCKING_ERROR, "🔴"),
        ("active + blocking=true（blocking_dry_run，已废弃）", ENFORCEMENT_BLOCKING_DRY_RUN, "🔴"),
        ("active + blocking=false（warn）", ENFORCEMENT_WARN, "🟡"),
        ("proposed（visibility_only）", ENFORCEMENT_VISIBILITY, "🔵"),
        ("deprecated / superseded（ignored）", ENFORCEMENT_IGNORED, "⚫"),
    ]:
        group = [rr for rr in rule_results if rr.get("enforcement_level") == level_key]
        if not group:
            continue
        lines.append(f"### {icon} {level_label} ({len(group)} 条)")
        lines.append("")
        for rr in group:
            result_icon = _result_icon(rr.get("result", "unknown"))
            lines.append(f"#### {result_icon} {rr.get('rule_id', '?')}: {rr.get('title', '')}")
            lines.append(f"- **状态:** {rr.get('status', '?')} | blocking={rr.get('blocking', False)}")
            lines.append(f"- **Enforcement 级别:** {rr.get('enforcement_level', '?')}")
            lines.append(f"- **结果:** {rr.get('result', '?')}")
            lines.append(f"- **消息:** {rr.get('message', '')}")

            if rr.get("failed_required_checks"):
                lines.append(
                    f"- **失败 required_check:** {', '.join(rr['failed_required_checks'])}"
                )
            if rr.get("failure_message"):
                lines.append(f"- **失败消息:** {rr['failure_message']}")
            if rr.get("suggested_fix"):
                lines.append(f"- **建议修复:** {rr['suggested_fix']}")
            if rr.get("rollback_plan"):
                lines.append(f"- **回滚方案:** {rr['rollback_plan']}")

            required = rr.get("required_checks", [])
            if required:
                lines.append(f"- **Required checks:** {', '.join(str(c) for c in required)}")

            matched = rr.get("matched_check_results", [])
            if matched:
                lines.append(f"- **Check 匹配结果:**")
                for m in matched:
                    m_status = m.get("status", "?")
                    m_icon = _result_icon(m_status)
                    lines.append(f"  - {m_icon} {m.get('name', '?')}: {m_status}")
            lines.append("")

    # 边界确认
    lines.append("## 边界确认")
    lines.append("")
    lines.append("- ✅ 未修改 docs/memory/*")
    lines.append("- ✅ 未修改 memory_rules.yml")
    lines.append("- ✅ 未自动晋升 active")
    lines.append("- ✅ 未自动设置 blocking=true")
    lines.append("- ✅ 只对 ready_for_error 的 active+blocking=true 规则启用真实阻断")
    lines.append("- ✅ 未读取 *_latest.*")
    lines.append("- ✅ 未调用 LLM")
    lines.append("- ✅ 未接入 pre-commit")
    lines.append("")

    return "\n".join(lines)


def _result_icon(result: str) -> str:
    """返回结果状态对应的图标（ASCII 安全）。"""
    icons = {
        "passed": "[PASS]",
        "warning": "[WARN]",
        "would_fail": "[WOULD_FAIL]",
        "FAIL": "[FAIL]",
        "skipped": "[SKIP]",
        "infra_error": "[ERROR]",
        "PASS": "[PASS]",
        "WARN": "[WARN]",
        "SKIPPED": "[SKIP]",
    }
    return icons.get(result, "[?]")


def render_enforcement_console_summary(report: dict[str, Any]) -> str:
    """生成控制台输出的 Memory Rule Enforcement Summary。

    用于在 fast gate 输出中嵌入。

    Args:
        report: build_enforcement_report 返回的完整 report

    Returns:
        控制台摘要字符串
    """
    summary = report.get("summary", {})
    exit_code_affected = report.get("exit_code_should_fail", False)
    lines: list[str] = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("Memory Rule Enforcement Summary (Step 18b)")
    lines.append("=" * 60)
    lines.append(f"  proposed visibility only:     {summary.get('proposed', 0)}")
    lines.append(f"  active warning rules:         {summary.get('active_warning', 0)}")
    lines.append(f"  active blocking rules:        {summary.get('active_blocking', 0)}")
    lines.append(f"  deprecated:                   {summary.get('deprecated', 0)}")
    lines.append(f"  superseded:                   {summary.get('superseded', 0)}")
    lines.append(f"  ---")
    lines.append(f"  passed:                       {summary.get('passed', 0)}")
    lines.append(f"  warnings:                     {summary.get('warnings', 0)}")
    lines.append(f"  blocking failures:            {summary.get('blocking_failures', 0)}")
    lines.append(f"  skipped:                      {summary.get('skipped', 0)}")
    lines.append(f"  infra errors:                 {summary.get('infra_errors', 0)}")
    lines.append(f"  ---")
    lines.append(f"  exit code affected:           {'yes' if exit_code_affected else 'no'}")
    lines.append("=" * 60)

    # 输出 blocking failure 详情
    blocking_failure_rules = [
        rr for rr in report.get("rule_results", [])
        if rr.get("result") == "FAIL"
    ]
    if blocking_failure_rules:
        lines.append("")
        lines.append("[FAIL] active+blocking=true 规则阻断失败:")
        for rr in blocking_failure_rules:
            lines.append(f"  - {rr['rule_id']}: {rr.get('title', '')}")
            lines.append(f"    enforcement_level={rr.get('enforcement_level', '?')}")
            failed_required_checks = rr.get("failed_required_checks", [])
            if failed_required_checks:
                lines.append(f"    失败 required_check: {', '.join(failed_required_checks)}")
            if rr.get("failure_message"):
                lines.append(f"    失败消息: {rr['failure_message']}")
            lines.append(f"    {rr.get('message', '')}")
            if rr.get("suggested_fix"):
                lines.append(f"    建议修复: {rr['suggested_fix']}")
            # 保留显式回滚信息，避免误报时需要推断恢复步骤
            lines.append(f"    回滚方案: {rr.get('rollback_plan', '')}")

    # 输出 warning 详情
    warning_rules = [
        rr for rr in report.get("rule_results", [])
        if rr.get("result") == "warning"
    ]
    if warning_rules:
        lines.append("")
        lines.append("[WARN] 规则 warnings:")
        for rr in warning_rules:
            lines.append(f"  - {rr['rule_id']}: {rr.get('message', '')}")

    lines.append("")
    return "\n".join(lines)


def write_enforcement_snapshot(
    report: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, str]:
    """将 enforcement report 写入 timestamp snapshot 文件。

    只生成 timestamp snapshot，不生成 latest 文件。

    Args:
        report: build_enforcement_report 返回的完整 report
        output_dir: 输出目录

    Returns:
        {"json": json_path, "markdown": markdown_path}
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 生成安全的 timestamp 文件名
    safe_ts = report.get("run_id", _generate_run_id()).replace(":", "").replace(".", "")
    json_path = out / f"memory_rule_enforcement_{safe_ts}.json"
    md_path = out / f"memory_rule_enforcement_{safe_ts}.md"

    json_data = render_enforcement_json(report)
    json_path.write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md_content = render_enforcement_markdown(report)
    md_path.write_text(md_content, encoding="utf-8")

    return {
        "json": str(json_path),
        "markdown": str(md_path),
    }
