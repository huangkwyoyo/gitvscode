"""
Harness 质量门禁回归测试。

这些测试约束 Harness 自身的行为，避免门禁被静默跳过。
"""
import os
import subprocess
import sys
from pathlib import Path

import yaml


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


def test_warehouse_connection_contract_points_to_existing_duckdb():
    """对外连接契约必须指向真实 DuckDB 文件，避免独立 Agent 拿到失效路径"""
    contract_path = PROJECT_ROOT / "contracts" / "warehouse_connection.yml"
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))

    duckdb_config = contract["duckdb"]
    db_path = Path(duckdb_config["absolute_path"])

    assert duckdb_config["read_only"] is True
    assert db_path.name == "nyc_transport.duckdb"
    assert db_path.exists()


def test_schema_consistency_requires_silver_tables_after_build():
    """Silver 建成后，实表强校验必须通过，不能继续按空 schema 逻辑跳过"""
    result = run_quality_command(
        [
            "scripts/quality/check_schema_consistency.py",
            "--require-silver-tables",
        ]
    )

    assert result.returncode == 0
    assert "Silver 实表尚未建设" not in result.stdout


def test_memory_gate_fails_when_critical_change_has_no_memory_update():
    """关键变更没有同步核心记忆文件时必须失败"""
    result = run_quality_command(
        [
            "scripts/quality/check_memory_update.py",
            "--changed-file",
            "M::scripts/silver/build_silver_duckdb.py",
        ]
    )

    assert result.returncode != 0
    assert "关键变更未同步更新核心记忆文件" in result.stdout


def test_memory_gate_passes_when_core_memory_updated():
    """关键变更同步更新核心记忆文件时应通过"""
    result = run_quality_command(
        [
            "scripts/quality/check_memory_update.py",
            "--changed-file",
            "M::scripts/silver/build_silver_duckdb.py",
            "--changed-file",
            "M::docs/memory/经验复盘.md",
        ]
    )

    assert result.returncode == 0
    assert "变更关联检查通过" in result.stdout


def test_content_quality_passes_for_valid_entries():
    """
    内容质量校验：现有条目应通过（exit 0，无 ERROR 级问题）

    注意：现有 22 条条目尚未适配新的治理模板（缺少置信等级/版本/状态字段），
    版本升级后这些条目会产生 [待迁移] 和交叉验证 INFO 级建议，
    但不影响 exit code。
    """
    result = run_quality_command(
        [
            "scripts/quality/check_memory_update.py",
            "--content-only",
        ]
    )

    assert result.returncode == 0
    assert "[ERROR]" not in result.stdout


def test_content_quality_detects_missing_required_fields():
    """内容质量校验：缺少必填字段的条目必须失败"""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "quality"))
    from check_memory_update import parse_memory_entries, check_entry_quality

    # 构造一个缺少"根因"和"风险"字段的条目
    bad_entry = """## R999：测试条目

- 日期：2026-01-01
- 来源问题：这是一个测试问题描述，足够详细，满足字数要求
- 规则：测试规则内容
- 已落地检查：none
"""

    entries = parse_memory_entries(bad_entry)
    assert len(entries) == 1
    assert entries[0]["rule_id"] == "R999"

    errors, warnings, duplicates = check_entry_quality(entries)
    assert len(errors) > 0
    assert any("根因" in e for e in errors)
    assert any("风险" in e for e in errors)


def test_content_quality_detects_short_entries():
    """内容质量校验：内容过短的条目必须报错"""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "quality"))
    from check_memory_update import parse_memory_entries, check_entry_quality

    # 构造一个不足 6 行的条目
    short_entry = """## R998：太短的条目
- 日期：2026-01-01
"""

    entries = parse_memory_entries(short_entry)
    assert len(entries) == 1
    assert entries[0]["line_count"] < 6

    errors, warnings, duplicates = check_entry_quality(entries)
    assert len(errors) > 0
    assert any("内容过短" in e for e in errors)


def test_content_quality_detects_duplicates():
    """内容质量校验：正文重复的条目应被检测"""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "quality"))
    from check_memory_update import parse_memory_entries, check_entry_quality

    # 构造两个正文完全相同的条目
    body_text = """
- 日期：2026-01-01
- 来源问题：这是一个重复的测试问题描述，需要足够详细以满足字数要求
- 根因：测试重复
- 风险：测试重复
- 规则：测试重复
"""

    dup_content = f"""## R997：第一个条目{body_text}

## R996：第二个条目{body_text}"""

    entries = parse_memory_entries(dup_content)
    assert len(entries) == 2

    errors, warnings, duplicates = check_entry_quality(entries)
    assert len(duplicates) > 0
    assert "R997" in duplicates[0] and "R996" in duplicates[0]


def test_content_quality_warns_for_missing_source_trace():
    """内容质量校验：来源追溯不足的条目应产生警告"""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "quality"))
    from check_memory_update import parse_memory_entries, check_entry_quality

    # 构造一个来源问题描述过短的条目（少于 20 字）
    vague_entry = """## R995：来源模糊的条目

- 日期：2026-01-01
- 来源问题：修了个bug
- 根因：不知道
- 风险：不清楚
- 规则：以后注意
"""

    entries = parse_memory_entries(vague_entry)
    assert len(entries) == 1

    errors, warnings, duplicates = check_entry_quality(entries)
    # 来源问题只有 4 个字，应触发警告
    assert len(warnings) > 0
    assert any("来源追溯" in w for w in warnings)
