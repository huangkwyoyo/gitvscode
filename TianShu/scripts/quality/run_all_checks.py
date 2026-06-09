"""
运行 TianShu Agent Memory + Warehouse Harness 全部检查

该脚本作为本地门禁入口，后续可接入 PR 检查。
"""
import os
import subprocess
import sys
from pathlib import Path

from harness_config import load_harness_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_step(name: str, command: list[str]) -> int:
    """运行单个检查步骤"""
    print("\n" + "=" * 60)
    print(f"[RUN] {name}")
    print("=" * 60)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(command, cwd=PROJECT_ROOT, env=env)
    if completed.returncode == 0:
        print(f"[OK] {name}")
    else:
        print(f"[FAIL] {name}，退出码 {completed.returncode}")
    return completed.returncode


def main() -> int:
    """运行全部 Harness 检查"""
    config = load_harness_config()
    python = sys.executable
    schema_command = [
        python,
        "scripts/quality/check_schema_consistency.py",
        "--project-root",
        str(config.project_root),
        "--db",
        str(config.duckdb_path),
        "--silver-xlsx",
        str(config.silver_dictionary_xlsx),
    ]
    if config.stage in ("post_silver_build", "pre_gold_build") or config.stage.startswith("gold"):
        schema_command.append("--require-silver-tables")

    steps = [
        (
            "Silver 数据字典一致性",
            [
                python,
                "scripts/quality/check_silver_dictionary.py",
                "--xlsx",
                str(config.silver_dictionary_xlsx),
                "--bronze-db",
                str(config.duckdb_path),
                "--plan-dir",
                str(config.project_root / "scripts" / "silver"),
            ],
        ),
        ("危险模式扫描", [python, "scripts/quality/check_dangerous_patterns.py", "--dir", str(config.project_root)]),
        (
            "schema 一致性",
            schema_command,
        ),
        ("Silver 空值画像", [
            python,
            "scripts/quality/check_silver_null.py",
            "--baseline",
            str(config.project_root / "harness" / "config" / "silver_sparsity_baseline.yml"),
        ]),
        ("Gold 设计门禁", [python, "scripts/quality/check_gold_design.py"]),
        ("Gold 物理表门禁", [python, "scripts/quality/check_gold_physical.py", "--batches", "G0,G1"]),
        ("Gold 空值画像", [
            python,
            "scripts/quality/check_gold_null.py",
            "--baseline",
            str(config.project_root / "harness" / "config" / "gold_sparsity_baseline.yml"),
        ]),
        ("Memory Gate", [python, "scripts/quality/check_memory_update.py"]),
        ("Silver 数据字典回归测试", [python, "-m", "pytest", "tests/test_silver_dictionary.py", "-v"]),
        ("Harness 自检回归测试", [python, "-m", "pytest", "tests/test_harness_quality.py", "-v"]),
        ("Gold 设计门禁回归测试", [python, "-m", "pytest", "tests/test_gold_design_quality.py", "-v"]),
        ("Gold 构建回归测试", [python, "-m", "pytest", "tests/test_gold_build_quality.py", "-v"]),
    ]

    failed = 0
    for name, command in steps:
        failed += 1 if run_step(name, command) != 0 else 0

    print("\n" + "=" * 60)
    if failed:
        print(f"[FAIL] Harness 检查完成，失败步骤数: {failed}")
        return 1
    print("[OK] Harness 全部检查通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
