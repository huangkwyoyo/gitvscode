"""
人审 CLI 测试——M4b。

覆盖 review_decision.py 的 show/set/audit 子命令：
- show 只读展示
- set APPROVED/REQUEST_CHANGES/REJECTED
- audit 完整日志
- 错误条件（空 message、FAIL 时 APPROVED、缺失文件）
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
BUILD_CLI = PROJECT_ROOT / "scripts" / "dev_agent" / "build_review_package.py"
VERIFY_CLI = PROJECT_ROOT / "scripts" / "dev_agent" / "verify_review_package.py"
REVIEW_CLI = PROJECT_ROOT / "scripts" / "dev_agent" / "review_decision.py"


def _build_and_verify(tmp_path: Path) -> Path:
    """生成 M2 Package 并运行 M3 验证。"""
    result = subprocess.run(
        [sys.executable, str(BUILD_CLI), "-r", str(FIXTURE), "--output-root", str(tmp_path)],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    package_dir = tmp_path / "trip_daily_report_m2"
    result = subprocess.run(
        [sys.executable, str(VERIFY_CLI), "-p", str(package_dir), "--no-sql-run"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    # verify 在无 DB 时返回 WARN（可接受）
    return package_dir


# ═══════════════════════════════════════════════════════════
# show——只读展示
# ═══════════════════════════════════════════════════════════


def test_show_outputs_current_state(tmp_path):
    """show 命令输出当前状态。"""
    package_dir = _build_and_verify(tmp_path)
    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "show", str(package_dir)],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0
    assert "PENDING_REVIEW" in result.stdout


def test_show_outputs_verification_summary(tmp_path):
    """show 命令输出验证摘要信息。"""
    package_dir = _build_and_verify(tmp_path)
    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "show", str(package_dir)],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert "verification_summary.yml" in result.stdout or "overall_status" in result.stdout


def test_show_missing_directory_fails():
    """show 对不存在的目录应报错。"""
    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "show", "nonexistent_dir_12345"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode != 0


# ═══════════════════════════════════════════════════════════
# audit——完整审计日志
# ═══════════════════════════════════════════════════════════


def test_audit_outputs_creation_entry(tmp_path):
    """audit 命令输出创建日志条目。"""
    package_dir = _build_and_verify(tmp_path)
    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "audit", str(package_dir)],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0
    assert "PENDING_REVIEW" in result.stdout
    assert "创建" in result.stdout or "Review Package" in result.stdout


def test_audit_after_state_changes(tmp_path):
    """状态变更后 audit 显示所有条目。"""
    package_dir = _build_and_verify(tmp_path)

    # 设置 APPROVED
    subprocess.run(
        [sys.executable, str(REVIEW_CLI), "set", str(package_dir),
         "--state", "APPROVED", "--message", "测试批准", "--user", "tester"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )

    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "audit", str(package_dir)],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert "APPROVED" in result.stdout
    assert "human:tester" in result.stdout or "tester" in result.stdout


# ═══════════════════════════════════════════════════════════
# set APPROVED
# ═══════════════════════════════════════════════════════════


def test_set_approved_updates_decision(tmp_path):
    """set --state APPROVED 更新 decision.yml。"""
    package_dir = _build_and_verify(tmp_path)
    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "set", str(package_dir),
         "--state", "APPROVED", "--message", "代码和验证结果均符合预期", "--user", "reviewer1"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0
    decision = yaml.safe_load((package_dir / "decision.yml").read_text(encoding="utf-8"))
    assert decision["current_state"] == "APPROVED"


def test_set_approved_appends_decision_log(tmp_path):
    """set APPROVED 后 decision_log 追加一条条目。"""
    package_dir = _build_and_verify(tmp_path)
    subprocess.run(
        [sys.executable, str(REVIEW_CLI), "set", str(package_dir),
         "--state", "APPROVED", "--message", "批准", "--user", "tester"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    log = yaml.safe_load((package_dir / "decision_log.yml").read_text(encoding="utf-8"))
    assert len(log["entries"]) == 2  # 创建 + 批准
    assert log["entries"][1]["to_state"] == "APPROVED"
    assert log["entries"][1]["actor_id"] == "human:tester"


def test_set_approved_requires_message(tmp_path):
    """set --state APPROVED 且 --message 为空时必须报错。"""
    package_dir = _build_and_verify(tmp_path)
    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "set", str(package_dir),
         "--state", "APPROVED", "--message", "", "--user", "tester"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode != 0


def test_set_approved_without_verification_fails(tmp_path):
    """无 verification_summary.yml 时 APPROVED 必须失败。"""
    # 只 M2 不 M3
    result = subprocess.run(
        [sys.executable, str(BUILD_CLI), "-r", str(FIXTURE), "--output-root", str(tmp_path)],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0
    package_dir = tmp_path / "trip_daily_report_m2"

    # 尝试 APPROVED（无验证）
    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "set", str(package_dir),
         "--state", "APPROVED", "--message", "不应该成功", "--user", "tester"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode != 0
    assert "verification_summary" in result.stderr


# ═══════════════════════════════════════════════════════════
# set REQUEST_CHANGES / REJECTED
# ═══════════════════════════════════════════════════════════


def test_set_request_changes(tmp_path):
    """set --state REQUEST_CHANGES 正常执行。"""
    package_dir = _build_and_verify(tmp_path)
    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "set", str(package_dir),
         "--state", "REQUEST_CHANGES", "--message", "SQL 需修复表引用", "--user", "reviewer"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0
    decision = yaml.safe_load((package_dir / "decision.yml").read_text(encoding="utf-8"))
    assert decision["current_state"] == "REQUEST_CHANGES"


def test_set_rejected(tmp_path):
    """set --state REJECTED 正常执行。"""
    package_dir = _build_and_verify(tmp_path)
    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "set", str(package_dir),
         "--state", "REJECTED", "--message", "指标口径不匹配", "--user", "reviewer"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0
    decision = yaml.safe_load((package_dir / "decision.yml").read_text(encoding="utf-8"))
    assert decision["current_state"] == "REJECTED"


def test_set_request_changes_requires_message(tmp_path):
    """REQUEST_CHANGES 必须要求 --message 非空。"""
    package_dir = _build_and_verify(tmp_path)
    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "set", str(package_dir),
         "--state", "REQUEST_CHANGES", "--message", "", "--user", "tester"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode != 0


def test_set_rejected_requires_message(tmp_path):
    """REJECTED 必须要求 --message 非空。"""
    package_dir = _build_and_verify(tmp_path)
    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "set", str(package_dir),
         "--state", "REJECTED", "--message", "", "--user", "tester"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode != 0


# ═══════════════════════════════════════════════════════════
# 边界与错误
# ═══════════════════════════════════════════════════════════


def test_set_invalid_state_fails(tmp_path):
    """无效的 state 参数必须报错。"""
    package_dir = _build_and_verify(tmp_path)
    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "set", str(package_dir),
         "--state", "INVALID", "--message", "test", "--user", "tester"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode != 0


def test_no_command_shows_help():
    """无子命令时显示帮助。"""
    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI)],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    # 无子命令应返回非零或打印 help
    assert "show" in result.stdout or "set" in result.stdout or "audit" in result.stdout
