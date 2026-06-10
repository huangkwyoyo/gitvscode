"""
检查指标注册合规门禁。

验证 evals/ 中问题集使用的指标是否在 contracts/metric_contract.yml 中注册。

检查逻辑：
    1. 从 contracts/metric_contract.yml 加载已注册指标列表
    2. 扫描问题集中的 metric_names 字段
    3. 报告未注册的指标名称

注意：
    - metric_names 为空（纯维度查询）是合法的，不报错
    - 未注册的指标标记为 FAIL

用法：
    python harness/checks/check_metric_registered.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from harness.config import load_harness_config


def load_registered_metrics(contracts_path: Path) -> set[str]:
    """从 metric_contract.yml 加载已注册的指标名称集合"""
    metric_file = contracts_path / "metric_contract.yml"
    if not metric_file.exists():
        return set()

    with open(metric_file, "r", encoding="utf-8") as f:
        metric_contract = yaml.safe_load(f)

    return {m["name"].lower() for m in metric_contract.get("metrics", [])}


def check_metrics(
    evals_path: Path,
    registered_metrics: set[str],
) -> dict[str, Any]:
    """
    检查所有问题集使用的指标是否已注册。

    Returns:
        {violations: [...], checks: [...]}
    """
    violations: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    if not evals_path.exists():
        return {"violations": violations, "checks": [{
            "name": "evals 目录", "status": "SKIP", "detail": "不存在"
        }]}

    for yaml_file in sorted(evals_path.glob("*.yml")):
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        questions = data if isinstance(data, list) else data.get("questions", [])
        for q in questions:
            if not isinstance(q, dict):
                continue

            qid = q.get("id", "unknown")
            metric_names = q.get("metric_names", [])
            question_zh = q.get("question_zh", "")

            if not metric_names:
                # 纯维度查询，合法
                checks.append({
                    "name": f"{yaml_file.name} / {qid}",
                    "status": "PASS",
                    "detail": "纯维度/列表查询（metric_names 为空），无需指标检查",
                })
                continue

            # 检查每个指标
            unregistered = [
                m for m in metric_names
                if m.lower() not in registered_metrics
            ]

            if unregistered:
                violations.append({
                    "file": yaml_file.name,
                    "question_id": qid,
                    "question_zh": question_zh,
                    "unregistered_metrics": unregistered,
                })
                checks.append({
                    "name": f"{yaml_file.name} / {qid}",
                    "status": "FAIL",
                    "detail": f"未注册指标: {unregistered}（已注册: {registered_metrics}）",
                })
            else:
                checks.append({
                    "name": f"{yaml_file.name} / {qid}",
                    "status": "PASS",
                    "detail": f"指标全部已注册: {metric_names}",
                })

    return {"violations": violations, "checks": checks}


def print_report(results: dict[str, Any], registered_count: int) -> int:
    """打印检查报告，返回退出码"""
    print("=" * 60)
    print("指标注册合规门禁")
    print(f"已注册指标数: {registered_count}")
    print("=" * 60)

    violations = results["violations"]
    checks = results["checks"]

    # 未注册指标违规
    if violations:
        print("\n── 违规项 ──")
        for v in violations:
            print(f"  [FAIL] {v['file']} / {v['question_id']}")
            print(f"         问题: {v.get('question_zh', '')}")
            print(f"         未注册指标: {v['unregistered_metrics']}")

    # 逐题检查
    print(f"\n── 逐题检查 ({len(checks)} 题) ──")
    for c in checks:
        tag = c["status"]
        print(f"  [{tag}] {c['name']}")
        if c.get("detail"):
            print(f"         {c['detail']}")

    fail_count = len(violations)
    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    skip_count = sum(1 for c in checks if c["status"] == "SKIP")

    print(f"\n  检查完成 — 通过: {pass_count}, 失败: {fail_count}, 跳过: {skip_count}")

    if fail_count > 0:
        print(f"\n[FAIL] 发现 {fail_count} 个问题使用了未注册的指标！")
        print("       请在 contracts/metric_contract.yml 中注册这些指标。")
        return 1
    elif not checks:
        print("\n[OK] 无待检查的问题。")
        return 0
    else:
        print("\n[OK] 指标注册合规检查通过。")
        return 0


def main() -> int:
    """命令行入口"""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="指标注册合规门禁")
    parser.add_argument("--config", default="config/tianshu_target.yml")
    parser.add_argument("--evals", type=Path, help="evals 目录路径")
    args = parser.parse_args()

    try:
        harness_config = load_harness_config(args.config)
    except FileNotFoundError as e:
        print(f"[SKIP] {e}")
        return 0

    evals_path = args.evals or harness_config.evals_path
    registered_metrics = load_registered_metrics(harness_config.contracts_path)

    results = check_metrics(evals_path, registered_metrics)
    return print_report(results, len(registered_metrics))


if __name__ == "__main__":
    sys.exit(main())
