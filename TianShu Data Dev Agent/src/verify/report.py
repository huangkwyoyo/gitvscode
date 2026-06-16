"""
验证报告工厂函数。

提供便捷方法快速构建常见的 ValidationReport 和 CheckResult。
"""

from __future__ import annotations

from src.ir.types import (
    CheckResult, ValidationReport, ValidationStatus,
)


def make_success_report() -> ValidationReport:
    """生成全通过的默认验证报告"""
    return ValidationReport(
        overall_status=ValidationStatus.PASSED,
        checks=[],
    )


def make_fail_report(errors: list[str]) -> ValidationReport:
    """
    生成失败报告——用于内部异常场景。

    Args:
        errors: 错误描述列表

    Returns:
        ValidationReport（overall_status = FAILED）
    """
    check_results = [
        CheckResult(
            check_id=0,
            name="内部错误",
            status=ValidationStatus.FAILED,
            detail=err,
            severity="FAIL",
        )
        for err in errors
    ]

    return ValidationReport(
        overall_status=ValidationStatus.FAILED,
        checks=check_results,
    )


def make_pending_report() -> ValidationReport:
    """生成待验证报告——用于初始化状态"""
    return ValidationReport(
        overall_status=ValidationStatus.PENDING,
        checks=[],
    )
