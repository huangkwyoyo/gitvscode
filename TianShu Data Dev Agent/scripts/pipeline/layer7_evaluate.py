"""
Layer 7：结果评估层

职责：
  1. 接收 Layer 6 的执行结果
  2. 执行数据质量检查：
     - 行数范围检查
     - 空值率检查
     - 期望列存在性检查
     - 指标数量一致性检查
  3. 输出评估报告

LLM 角色：
  **完全禁止**。此层是纯统计检查。

输入：ExecutionResult + SQLPlan
输出：评估报告
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .layer3_ir import SQLPlan
from .layer6_execute import ExecutionResult


@dataclass
class EvalCheck:
    """单个评估检查项"""
    name: str
    passed: bool
    detail: str
    threshold: str
    actual: str


@dataclass
class EvaluationReport:
    """结果评估报告"""
    passed: bool
    checks: list[EvalCheck] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=lambda: {
        "total_checks": 0,
        "passed_checks": 0,
        "failed_checks": 0,
    })
    status: str = "clean"  # clean | dirty
    warnings: list[str] = field(default_factory=list)


def _check_row_count(result: ExecutionResult, plan: SQLPlan) -> EvalCheck:
    """检查行数是否在合理范围"""
    row_count = result.row_count
    # 基础检查：至少有 0 行（0 行 = 空数据集，可能是 DIRTY 但非失败）
    if row_count == 0:
        return EvalCheck(
            name="行数检查",
            passed=True,  # 0 行不是失败，是 DIRTY
            detail=f"查询返回 0 行。表 {plan.join_graph.primary.table if plan.join_graph else 'unknown'} 在指定时间范围内可能无数据",
            threshold="行数 ≥ 0",
            actual=f"{row_count} 行",
        )

    if row_count > 100000:
        return EvalCheck(
            name="行数检查",
            passed=False,
            detail=f"行数 ({row_count}) 超过限制 ({100000})",
            threshold="行数 ≤ 100000",
            actual=f"{row_count} 行",
        )

    return EvalCheck(
        name="行数检查",
        passed=True,
        detail=f"行数在合理范围内",
        threshold="行数 ≤ 100000",
        actual=f"{row_count} 行",
    )


def _check_null_rate(result: ExecutionResult) -> EvalCheck:
    """检查总体空值率"""
    df = result.dataframe
    if df is None or len(df) == 0:
        return EvalCheck(
            name="空值率检查",
            passed=True,
            detail="无数据，跳过空值率检查",
            threshold="空值率 < 30%",
            actual="N/A",
        )

    total_cells = df.size
    null_cells = df.isna().sum().sum()
    null_rate = null_cells / total_cells if total_cells > 0 else 0.0

    if null_rate > 0.30:
        return EvalCheck(
            name="空值率检查",
            passed=False,
            detail=f"整体空值率 ({null_rate:.1%}) 超过阈值 (30%)",
            threshold="空值率 < 30%",
            actual=f"{null_rate:.1%}",
        )

    return EvalCheck(
        name="空值率检查",
        passed=True,
        detail=f"空值率在可接受范围",
        threshold="空值率 < 30%",
        actual=f"{null_rate:.1%}",
    )


def _check_expected_columns(result: ExecutionResult, plan: SQLPlan) -> EvalCheck:
    """检查预期列是否在结果中"""
    expected_aliases = [b.alias for b in plan.column_bindings]
    for dim in plan.dimension_bindings:
        expected_aliases.append(dim.alias)

    df = result.dataframe
    if df is None:
        return EvalCheck(
            name="列完整性检查",
            passed=False,
            detail="无法检查：DataFrame 为空",
            threshold=f"包含 {len(expected_aliases)} 个预期列",
            actual="DataFrame 为 None",
        )

    actual_cols = list(df.columns)
    missing = [c for c in expected_aliases if c not in actual_cols]

    if missing:
        return EvalCheck(
            name="列完整性检查",
            passed=False,
            detail=f"缺少预期列: {missing}。实际列: {actual_cols}",
            threshold=f"包含所有预期列: {expected_aliases}",
            actual=f"实际列: {actual_cols}",
        )

    return EvalCheck(
        name="列完整性检查",
        passed=True,
        detail="所有预期列都在结果中",
        threshold=f"包含 {len(expected_aliases)} 个预期列",
        actual=f"实际包含 {len(actual_cols)} 列",
    )


def _check_metric_consistency(result: ExecutionResult, plan: SQLPlan) -> EvalCheck:
    """检查指标数量是否一致"""
    expected_count = len(plan.column_bindings)
    actual_count = result.column_count

    # 粗略检查（列数至少包含指标数）
    if actual_count < expected_count:
        return EvalCheck(
            name="指标一致性检查",
            passed=False,
            detail=f"结果列数 ({actual_count}) 少于预期指标数 ({expected_count})",
            threshold=f"列数 ≥ {expected_count}",
            actual=f"{actual_count} 列",
        )

    return EvalCheck(
        name="指标一致性检查",
        passed=True,
        detail="结果列数满足预期指标数",
        threshold=f"列数 ≥ {expected_count}",
        actual=f"{actual_count} 列",
    )


def evaluate_results(result: ExecutionResult, plan: SQLPlan) -> EvaluationReport:
    """
    对 SQL 执行结果进行质量评估

    检查项：
    1. 行数范围检查
    2. 空值率检查
    3. 列完整性检查
    4. 指标一致性检查
    """
    if not result.success:
        return EvaluationReport(
            passed=False,
            status="dirty",
            warnings=[f"SQL 执行失败，无法评估: {result.error_message}"],
        )

    checks = [
        _check_row_count(result, plan),
        _check_null_rate(result),
        _check_expected_columns(result, plan),
        _check_metric_consistency(result, plan),
    ]

    total = len(checks)
    passed_count = sum(1 for c in checks if c.passed)
    failed_count = total - passed_count

    # 状态判断
    # 有 FAIL → dirty
    # 全部通过 → clean
    status = "dirty" if failed_count > 0 else "clean"

    # 零行数据是特殊情况
    warnings: list[str] = []
    if result.row_count == 0:
        warnings.append(
            f"查询返回 0 行。请确认时间范围 {plan.filter_bindings[0].value if plan.filter_bindings else 'unknown'} 内有数据。"
        )

    return EvaluationReport(
        passed=failed_count == 0,
        checks=checks,
        summary={
            "total_checks": total,
            "passed_checks": passed_count,
            "failed_checks": failed_count,
        },
        status=status,
        warnings=warnings,
    )
