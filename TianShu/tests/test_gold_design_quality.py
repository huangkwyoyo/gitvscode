"""
Gold 设计门禁回归测试。

这些测试约束 Gold 建表前的设计审查，避免把不存在的字段、缺失中文名或翻译草稿带入落库。
"""
import os
import subprocess
import sys
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_temp_design(content: str) -> Path:
    """把临时设计文档写到项目内，避开系统临时目录权限差异"""
    temp_dir = PROJECT_ROOT / ".pytest_tmp"
    temp_dir.mkdir(exist_ok=True)
    path = temp_dir / f"gold_design_{uuid.uuid4().hex}.md"
    path.write_text(content, encoding="utf-8")
    return path


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


def test_gold_design_missing_chinese_name_fails():
    """Gold 字段缺少中文名时必须失败"""
    design = write_temp_design(
        """
# Gold 层数据库设计文档

### 5.1 `gold.dim_date` 日期维表

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `date_key` |  | INTEGER | `silver.dim_date.date_key` | 主键 |
""",
    )

    result = run_quality_command(["scripts/quality/check_gold_design.py", "--design", str(design)])

    assert result.returncode != 0
    assert "缺少中文字段名" in result.stdout


def test_gold_design_unknown_silver_source_fails():
    """Gold 来源字段不存在于 Silver 实表时必须失败"""
    design = write_temp_design(
        """
# Gold 层数据库设计文档

### 5.1 `gold.dim_date` 日期维表

| 英文字段名 | 中文字段名 | 类型 | 来源字段 | 说明 |
|---|---|---|---|---|
| `date_key` | 日期键 | INTEGER | `silver.dim_date.not_exists` | 主键 |
""",
    )

    result = run_quality_command(["scripts/quality/check_gold_design.py", "--design", str(design)])

    assert result.returncode != 0
    assert "Silver 来源字段不存在" in result.stdout


def test_current_gold_design_passes_quality_gate():
    """当前 Gold 正式设计文档必须通过建表前门禁"""
    result = run_quality_command(["scripts/quality/check_gold_design.py"])

    assert result.returncode == 0
    assert "Gold 设计门禁检查通过" in result.stdout
