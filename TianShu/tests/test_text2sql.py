"""
Text2SQL 问数能力评测回归测试

验证 check_text2sql.py 评测脚本本身的正确性：
- 标准问题集应全部通过
- 问题文件缺失应报错
- 评测报告应生成
- 低层级表误用应被检测
- 结果签名基线应能自动创建
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(r"D:\ProgramData\Datawarehouse\纽约市城市交通\nyc_transport.duckdb")
QUESTIONS_PATH = PROJECT_ROOT / "harness" / "questions" / "gold_standard_questions.yml"
BASELINE_PATH = PROJECT_ROOT / "harness" / "reports" / "text2sql_signature_baseline.yml"
REPORTS_DIR = PROJECT_ROOT / "harness" / "reports"


def run_quality_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    """使用统一环境运行评测脚本，避免中文输出编码干扰"""
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


def test_text2sql_all_pass():
    """标准问题集应全部通过"""
    result = run_quality_command(["scripts/quality/check_text2sql.py"])
    assert result.returncode == 0, (
        f"预期标准问题集全通过，但返回非零退出码:\n{result.stdout}"
    )
    assert "通过" in result.stdout


def test_text2sql_missing_questions():
    """问题文件不存在时应报错"""
    result = run_quality_command([
        "scripts/quality/check_text2sql.py",
        "--questions", "nonexistent/questions.yml",
    ])
    assert result.returncode != 0, "问题文件不存在时应该返回非零退出码"
    assert "不存在" in result.stdout


def test_text2sql_report_created():
    """运行评测后应生成 Markdown 报告"""
    # 先运行一次评测
    run_quality_command(["scripts/quality/check_text2sql.py"])

    # 检查 reports 目录下有报告文件
    reports = list(REPORTS_DIR.glob("text2sql_report_*.md"))
    assert len(reports) > 0, "应在 reports 目录下生成 text2sql_report_*.md 文件"

    # 验证报告内容结构
    latest_report = sorted(reports)[-1]
    content = latest_report.read_text(encoding="utf-8")
    assert "Text2SQL 中文问数能力评测报告" in content
    assert "评测汇总" in content
    assert "逐题详情" in content
    assert "统计" in content


def test_text2sql_low_layer_detected():
    """SQL 误用 Silver 表时应被层级合规检查检测"""
    temp_dir = Path(tempfile.mkdtemp(prefix="text2sql_test_"))
    questions_path = temp_dir / "test_low_layer.yml"

    # 构造一个故意使用 Silver 表的问题
    test_questions = {
        "questions": [
            {
                "id": "q_test_silver_misuse",
                "question_zh": "测试误用 Silver 明细表",
                "recommended_table": "gold.dws_daily_trip_summary",
                "metric_names": ["trip_count"],
                "sql": "SELECT count(*) AS trip_count FROM silver.trip_detail WHERE pickup_date BETWEEN '2026-01-01' AND '2026-01-31'",
                "caution": "这是一个测试，故意使用 Silver 表",
                "expected_tables": ["gold.dws_daily_trip_summary"],
            }
        ]
    }
    questions_path.write_text(
        yaml.dump(test_questions, allow_unicode=True), encoding="utf-8",
    )

    try:
        result = run_quality_command([
            "scripts/quality/check_text2sql.py",
            "--questions", str(questions_path),
            "--baseline", str(temp_dir / "temp_baseline.yml"),
            "--report-dir", str(temp_dir),
        ])

        # 应该检测到层级违规（使用了 Silver 表）
        stdout = result.stdout
        # 层级合规应该报 FAIL 或 WARN（引用了 Silver）
        assert ("Silver" in stdout) or ("silver" in stdout.lower()), (
            f"应检测到 Silver 表误用:\n{stdout}"
        )
    finally:
        # 清理临时文件
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_text2sql_baseline_creates():
    """删除基线后运行评测应自动重建"""
    # 清理可能的残留备份
    backup_path = BASELINE_PATH.with_suffix(".yml.bak")
    if backup_path.exists():
        backup_path.unlink()

    # 备份当前基线
    if BASELINE_PATH.exists():
        BASELINE_PATH.rename(backup_path)

    try:
        # 运行评测（无基线）
        result = run_quality_command(["scripts/quality/check_text2sql.py"])
        # 应该重建基线
        assert BASELINE_PATH.exists(), "运行后应自动创建基线文件"

        content = BASELINE_PATH.read_text(encoding="utf-8")
        assert "signatures:" in content
        assert "q_daily_trip_count" in content
    finally:
        # 恢复备份（需先删除当前文件，因为 rename 不允许覆盖已存在的 target）
        if backup_path.exists():
            if BASELINE_PATH.exists():
                BASELINE_PATH.unlink()
            backup_path.rename(BASELINE_PATH)


def test_results_signature_stable():
    """连续两次运行结果签名应一致（稳定性验证）"""
    # 第一次运行
    run_quality_command(["scripts/quality/check_text2sql.py", "--reset-baseline"])
    sig1 = yaml.safe_load(BASELINE_PATH.read_text(encoding="utf-8"))

    # 第二次运行（不应重建基线）
    run_quality_command(["scripts/quality/check_text2sql.py"])
    sig2 = yaml.safe_load(BASELINE_PATH.read_text(encoding="utf-8"))

    # 签名应一致
    sigs1 = sig1["signatures"]
    sigs2 = sig2["signatures"]
    assert sigs1.keys() == sigs2.keys(), "两次运行的问题集应相同"

    for qid in sigs1:
        assert sigs1[qid]["md5"] == sigs2[qid]["md5"], (
            f"{qid} 的签名在两次运行间不一致"
        )
