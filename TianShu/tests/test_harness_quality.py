"""
Harness 质量门禁回归测试

这些测试约束 Harness 自身的行为，避免门禁被静默跳过。
"""
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_quality_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    """使用统一环境运行质量脚本，避免中文输出编码干扰"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def test_silver_dictionary_missing_xlsx_fails():
    """Silver 字典文件缺失时，检查脚本必须失败而不是跳过"""
    missing_xlsx = PROJECT_ROOT / "__missing_silver_dictionary__.xlsx"
    result = run_quality_command(
        [
            "scripts/quality/check_silver_dictionary.py",
            "--xlsx",
            str(missing_xlsx),
        ]
    )

    assert result.returncode != 0
    assert "Silver xlsx 不存在" in result.stdout


def test_harness_config_loader_reads_targets():
    """质量脚本应从 Harness 配置读取路径，避免散落硬编码"""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "quality"))

    from harness_config import load_harness_config

    config = load_harness_config(PROJECT_ROOT / "harness" / "config" / "harness_targets.yml")

    assert config.project_root == PROJECT_ROOT
    assert config.duckdb_path.name == "nyc_transport.duckdb"
    assert config.silver_dictionary_xlsx.name == "Silver层数据字典.xlsx"


def test_schema_consistency_requires_silver_tables_when_enabled():
    """启用 Silver 实表强校验后，空 Silver schema 必须失败"""
    result = run_quality_command(
        [
            "scripts/quality/check_schema_consistency.py",
            "--require-silver-tables",
        ]
    )

    assert result.returncode != 0
    assert "Silver schema 缺少表" in result.stdout
