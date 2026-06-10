"""
TianShu Text2SQL Agent 质量门禁入口。

依次运行所有门禁检查，汇总结果并输出 Markdown 报告。

检查列表：
    1. SQL 只读安全门禁  —— 扫描 SQL 禁止写操作关键字
    2. IR 数据结构完整性  —— 验证三层 IR 定义 + evals 文件结构
    3. 反问/拒绝策略完备性 —— 验证 question_policy.yml + 相关 eval 文件
    4. 层级合规门禁      —— G3 > G2 > Silver > Bronze
    5. 指标注册合规门禁  —— 指标必须在 metric_contract.yml 中注册

用法：
    python harness/run_harness.py
    python harness/run_harness.py --config <path>
"""

from __future__ import annotations

import argparse
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
]


def run_step(name: str, cmd: list[str]) -> dict[str, Any]:
    """
    运行单步检查。

    Args:
        name: 检查名称
        cmd: 命令行列表

    Returns:
        {name, status, exit_code, stdout, elapsed}
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

    status = "PASS" if exit_code == 0 else "FAIL"

    return {
        "name": name,
        "status": status,
        "exit_code": exit_code,
        "stdout": stdout,
        "elapsed": round(elapsed, 2),
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
    fail_count = sum(1 for r in results if r["status"] != "PASS")
    lines.append("## 汇总")
    lines.append("")
    lines.append(f"| 状态 | 数量 |")
    lines.append(f"|------|------|")
    lines.append(f"| PASS | {pass_count} |")
    lines.append(f"| FAIL | {fail_count} |")
    lines.append(f"| **总计** | **{len(results)}** |")
    lines.append("")

    # 逐步详情
    lines.append("## 逐步详情")
    lines.append("")
    for r in results:
        tag = "✅" if r["status"] == "PASS" else "❌"
        lines.append(f"### {tag} {r['name']}")
        lines.append(f"- 状态: {r['status']}")
        lines.append(f"- 耗时: {r['elapsed']}s")
        lines.append(f"- 退出码: {r['exit_code']}")
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
    parser.add_argument("--step", type=int, help="只运行指定步骤（1-5）")
    args = parser.parse_args()

    steps_to_run = STEPS
    if args.step:
        if 1 <= args.step <= len(STEPS):
            steps_to_run = [STEPS[args.step - 1]]
        else:
            print(f"[FAIL] 步骤编号超出范围 (1-{len(STEPS)}): {args.step}")
            return 1

    print("=" * 60)
    print("TianShu Text2SQL Agent Harness")
    print(f"检查项: {len(steps_to_run)} 步")
    print("=" * 60)
    print()

    results: list[dict[str, Any]] = []
    for i, (name, cmd) in enumerate(steps_to_run, 1):
        # 传递 --config 参数到每个检查脚本
        cmd_with_config = cmd + ["--config", args.config]

        print(f"[{i}/{len(steps_to_run)}] {name}...", end=" ", flush=True)
        result = run_step(name, cmd_with_config)
        results.append(result)

        tag = "PASS" if result["status"] == "PASS" else "FAIL"
        print(f"{tag} ({result['elapsed']}s)")

    # 汇总
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] != "PASS")

    print(f"\n{'=' * 60}")
    print(f"Harness 完成: {pass_count} PASS, {fail_count} FAIL (共 {len(results)} 步)")
    print(f"{'=' * 60}")

    # 生成报告
    report_path = Path(args.report)
    write_report(results, report_path)
    print(f"\n报告已保存: {report_path}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
