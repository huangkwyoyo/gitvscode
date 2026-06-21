"""
TianShu Text2SQL Agent 质量门禁入口。

依次运行所有门禁检查，汇总结果并输出 Markdown 报告。

检查列表：
    1. SQL 只读安全门禁  —— 扫描 SQL 禁止写操作关键字
    2. IR 数据结构完整性  —— 验证三层 IR 定义 + Phase 2-5 数据类 + evals 文件结构
    3. 反问/拒绝策略完备性 —— 验证 question_policy.yml + 相关 eval 文件
    4. 层级合规门禁      —— G3 > G2 > Silver > Bronze
    5. 指标注册合规门禁  —— 指标必须在 metric_contract.yml 中注册
    6. Memory Gate      —— 关键路径变更后记忆文件是否同步更新
    7. 执行策略安全门禁  —— 验证默认串行、线程隔离、安全链路
    8. LLM 融合安全门禁  —— 验证 SQL/因果/编造检测 + fallback
    9. 跨域策略安全门禁  —— 验证隐私保护、因果禁止、罚款警告
   10. 图表规格安全门禁  —— 验证 HTML/JS/LLM/DuckDB 禁止 + 跨域降级
   11. PlanExecutor 安全门禁 —— 验证安全链路引用、离线阻断、read_only
   12. JSON 响应契约序列化门禁 —— 验证 build_public_response() 输出 JSON-native + 禁止 default=str 掩码

warn 模式（--warn-steps）：
    - 指定步骤以 WARN 模式运行：发现问题时打印 WARNING，但不导致非零退出码
    - 只有基础设施错误（脚本不存在、语法错误、超时）才会使 WARN 步骤真正失败
    - 适用于新接入的检查，处于观察期，不阻断开发

用法：
    python harness/run_harness.py
    python harness/run_harness.py --config <path>
    python harness/run_harness.py --warn-steps 7,8,9,10,11           # 观察期模式
    python harness/run_harness.py --warn-steps 7,8,9,10,11 --json-summary  # CI 模式
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


# 门禁步骤定义（与 TianShu run_all_checks.py 模式一致）
# 格式: (名称, [命令列表])
STEPS: list[tuple[str, list[str]]] = [
    ("SQL 只读安全门禁", [sys.executable, "harness/checks/check_sql_readonly.py"]),
    ("IR 数据结构完整性", [sys.executable, "harness/checks/check_ir_schema.py"]),
    ("反问/拒绝策略完备性", [sys.executable, "harness/checks/check_refusal_policy.py"]),
    ("层级合规门禁", [sys.executable, "harness/checks/check_layer_compliance.py"]),
    ("指标注册合规门禁", [sys.executable, "harness/checks/check_metric_registered.py"]),
    ("Memory Gate", [sys.executable, "harness/checks/check_memory_update.py", "--registry"]),
    # Step 2 新增: 执行层/结果层/融合层/图表层安全门禁
    ("执行策略安全门禁", [sys.executable, "harness/checks/check_execution_strategy_safety.py"]),
    ("LLM 融合安全门禁", [sys.executable, "harness/checks/check_result_fusion_safety.py"]),
    ("跨域策略安全门禁", [sys.executable, "harness/checks/check_cross_domain_policy.py"]),
    ("图表规格安全门禁", [sys.executable, "harness/checks/check_chart_spec_safety.py"]),
    ("PlanExecutor 安全门禁", [sys.executable, "harness/checks/check_plan_executor_safety.py"]),
    # JSON-P1: 公开响应 JSON 契约序列化严格性检查（TA-R031 proposed 观察期）
    ("JSON 响应契约序列化门禁", [sys.executable, "harness/checks/check_json_response_contract.py"]),
]


def run_step(name: str, cmd: list[str], warn_mode: bool = False,
             script: str = "") -> dict[str, Any]:
    """
    运行单步检查。

    Args:
        name: 检查名称
        cmd: 命令行列表
        warn_mode: True 时，检查发现规则问题不阻塞（状态 WARN），仅基础设施错误阻塞
        script: 对应的检查脚本路径（用于结构化输出）

    Returns:
        {name, status, exit_code, stdout, elapsed, script}
        状态值: PASS / WARN / FAIL / SKIPPED
    """
    start = time.perf_counter()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",  # 避免 Windows GBK 编码中文乱码
            timeout=60,
            cwd=Path(__file__).resolve().parent.parent,  # 项目根目录
            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
        )
        exit_code = result.returncode
        stdout = result.stdout
    except subprocess.TimeoutExpired:
        exit_code = -1
        stdout = "检查超时（60s）"
    except FileNotFoundError:
        exit_code = -2
        stdout = f"命令未找到: {cmd}"
    elapsed = time.perf_counter() - start

    # 状态判定逻辑：
    # - exit_code == 0: 检查通过 → PASS
    # - exit_code > 0: 检查发现规则问题
    #     - warn_mode: 仅警告 → WARN
    #     - 非 warn_mode: 阻断 → FAIL
    # - exit_code < 0: 基础设施错误（超时=-1，文件未找到=-2）→ 始终 FAIL
    if exit_code == 0:
        status = "PASS"
    elif exit_code < 0:
        status = "FAIL"  # 基础设施错误始终阻断
    elif warn_mode:
        status = "WARN"  # 规则问题 + 观察期 → 仅警告
    else:
        status = "FAIL"

    return {
        "name": name,
        "status": status,
        "exit_code": exit_code,
        "stdout": stdout,
        "elapsed": round(elapsed, 2),
        "warn_mode": warn_mode,
        "script": script,
    }


def write_report(results: list[dict[str, Any]], report_path: Path) -> None:
    """生成 Markdown 报告"""
    lines: list[str] = []
    lines.append("# TianShu Text2SQL Agent Harness 报告")
    lines.append("")
    lines.append(f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # 汇总表
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    warn_count = sum(1 for r in results if r["status"] == "WARN")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    lines.append("## 汇总")
    lines.append("")
    lines.append("| 状态 | 数量 |")
    lines.append("|------|------|")
    lines.append(f"| PASS | {pass_count} |")
    if warn_count:
        lines.append(f"| WARN | {warn_count} |")
    lines.append(f"| FAIL | {fail_count} |")
    lines.append(f"| **总计** | **{len(results)}** |")
    lines.append("")

    # 逐步详情
    lines.append("## 逐步详情")
    lines.append("")
    for r in results:
        status = r["status"]
        if status == "PASS":
            tag = "✅"
        elif status == "WARN":
            tag = "⚠️"
        else:
            tag = "❌"
        lines.append(f"### {tag} {r['name']}")
        lines.append(f"- 状态: {r['status']}")
        lines.append(f"- 耗时: {r['elapsed']}s")
        lines.append(f"- 退出码: {r['exit_code']}")
        if r.get("warn_mode"):
            lines.append("- 模式: 观察期（warn-only），不阻断")
        lines.append("")
        lines.append("```")
        stdout_text = r.get("stdout") or "(无输出)"
        lines.append(stdout_text[:3000])  # 截断过长输出
        lines.append("```")
        lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    """运行全部门禁检查"""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="TianShu Text2SQL Agent Harness")
    parser.add_argument("--config", default="config/tianshu_target.yml", help="TianShu 目标配置")
    parser.add_argument("--report", type=Path, default=Path("harness/reports/harness_report_latest.md"),
                       help="报告输出路径")
    parser.add_argument("--step", type=int, help="只运行指定步骤（1-based）")
    parser.add_argument(
        "--warn-steps",
        type=str,
        default=None,
        metavar="INDICES",
        help="以 WARN 模式运行的步骤编号，逗号分隔（如 7,8,9,10,11）。"
             "WARN 模式下，检查发现规则问题仅打印 WARNING，不导致非零退出码。"
             "仅基础设施错误（脚本不存在、超时）会真正失败。"
             "适用于新接入的检查，处于观察期。",
    )
    parser.add_argument(
        "--json-summary",
        action="store_true",
        help="在输出末尾打印机器可读的 JSON 摘要行（__HARNESS_JSON_SUMMARY__ {...}）",
    )
    args = parser.parse_args()

    # 解析 warn 步骤索引
    warn_step_indices: set[int] = set()
    if args.warn_steps:
        for part in args.warn_steps.split(","):
            part = part.strip()
            if part:
                try:
                    idx = int(part)
                    if 1 <= idx <= len(STEPS):
                        warn_step_indices.add(idx)
                    else:
                        print(f"[WARN] 忽略超出范围的 warn 步骤索引: {idx} (范围 1-{len(STEPS)})")
                except ValueError:
                    print(f"[WARN] 忽略无效的 warn 步骤索引: '{part}'")

    steps_to_run = STEPS
    if args.step:
        if 1 <= args.step <= len(STEPS):
            steps_to_run = [STEPS[args.step - 1]]
        else:
            print(f"[FAIL] 步骤编号超出范围 (1-{len(STEPS)}): {args.step}")
            return 1

    if warn_step_indices:
        warn_names = [STEPS[i - 1][0] for i in sorted(warn_step_indices)]
        print("=" * 60)
        print("TianShu Text2SQL Agent Harness")
        print(f"检查项: {len(steps_to_run)} 步")
        print(f"WARN 观察期步骤: {', '.join(warn_names)}")
        print("=" * 60)
    else:
        print("=" * 60)
        print("TianShu Text2SQL Agent Harness")
        print(f"检查项: {len(steps_to_run)} 步")
        print("=" * 60)
    print()

    results: list[dict[str, Any]] = []
    for i, (name, cmd) in enumerate(steps_to_run, 1):
        # 传递 --config 参数到每个检查脚本
        cmd_with_config = cmd + ["--config", args.config]

        # 判断当前步骤是否为 warn 模式
        # 当 --step 指定了单步时，用原始 STEPS 索引；否则用当前枚举序号
        step_index = args.step if args.step else i
        is_warn = step_index in warn_step_indices

        # 提取脚本路径（命令列表中 python 后的第一个非选项参数）
        script_path = ""
        for arg in cmd:
            if arg != sys.executable and not arg.startswith("-"):
                script_path = arg
                break

        mode_label = " [WARN-ONLY]" if is_warn else ""
        print(f"[{i}/{len(steps_to_run)}] {name}{mode_label}...", end=" ", flush=True)
        result = run_step(name, cmd_with_config, warn_mode=is_warn, script=script_path)
        results.append(result)

        # 根据状态输出标签
        status = result["status"]
        if status == "PASS":
            print(f"PASS ({result['elapsed']}s)")
        elif status == "WARN":
            print(f"⚠️ WARN ({result['elapsed']}s)")
            print("     检查发现规则问题，但处于观察期不阻断。")
        elif status == "FAIL":
            print(f"❌ FAIL ({result['elapsed']}s)")

    # 汇总
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    warn_count = sum(1 for r in results if r["status"] == "WARN")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")

    # 按类型细分
    blocking_results = [r for r in results if not r.get("warn_mode")]
    warn_results = [r for r in results if r.get("warn_mode")]
    blocking_pass = sum(1 for r in blocking_results if r["status"] == "PASS")
    blocking_fail = sum(1 for r in blocking_results if r["status"] == "FAIL")
    warn_pass = sum(1 for r in warn_results if r["status"] == "PASS")
    warn_warn = sum(1 for r in warn_results if r["status"] == "WARN")
    # 基础设施错误即使在 warn 模式下也是 FAIL
    warn_infra_fail = sum(1 for r in warn_results if r["status"] == "FAIL")

    print(f"\n{'=' * 60}")
    print(f"Harness 完成: {pass_count} PASS", end="")
    if warn_count:
        print(f", {warn_count} WARN", end="")
    print(f", {fail_count} FAIL (共 {len(results)} 步)")
    if warn_results:
        print(f"  观察期检查: {warn_pass} 通过, {warn_warn} 警告, {warn_infra_fail} 基础设施失败")
    print(f"{'=' * 60}")

    # 生成报告
    report_path = Path(args.report)
    write_report(results, report_path)
    print(f"\n报告已保存: {report_path}")

    # JSON 摘要输出（供 CI / fast_gate 解析）
    if args.json_summary:
        summary = {
            "blocking_pass": blocking_pass,
            "blocking_fail": blocking_fail,
            "warn_pass": warn_pass,
            "warn_warn": warn_warn,
            "warn_infra_fail": warn_infra_fail,
            "total_pass": pass_count,
            "total_warn": warn_count,
            "total_fail": fail_count,
            "total_steps": len(results),
        }
        print(f"\n__HARNESS_JSON_SUMMARY__ {json.dumps(summary, ensure_ascii=False)}")

        # 结构化 check results 输出（供 memory rule enforcement 解析）
        check_results = [
            {
                "name": r["name"],
                "script": r.get("script", ""),
                "status": r["status"],
                "exit_code": r["exit_code"],
            }
            for r in results
        ]
        print(f"__HARNESS_CHECK_RESULTS__ {json.dumps(check_results, ensure_ascii=False)}")

    # 退出码逻辑：
    # - 阻断检查或基础设施失败 → exit 1
    # - 仅 warn 模式检查发现规则问题 → exit 0（不阻断）
    # - 全部通过 → exit 0
    if blocking_fail > 0 or warn_infra_fail > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
