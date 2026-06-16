"""
防线 2 验证器——7 项检查的编排调度器。

Validator 类是数据执行边界（边界 2）的唯一入口：
所有代码（LLM 生成 / 编译器生成 / 人手写）在进入沙箱执行前，
必须通过此类的 validate() 方法。

聚合规则：
  - 任一检查 FAIL → overall_status = FAILED（阻断）
  - 全 PASSED 但有 WARN → overall_status = WARN
  - 全 PASSED → overall_status = PASSED

从 v1.x layer5_validate.py 的 validate_sql() 编排模式移植。
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from src.ir.types import (
    CheckResult, ValidationReport, ValidationStatus,
    SQLPlan, SQLResult, CrossValidationResult,
)

from .checks import (
    check_table_existence,
    check_forbidden_keywords,
    check_table_permissions,
    check_join_whitelist,
    check_sample_execution,
    check_result_quality,
    check_cross_validation,
)

# 检查项类型：接受关键字参数，返回 CheckResult
CheckFn = Callable[..., CheckResult]


class Validator:
    """
    防线 2 验证器——7 项自动检查的编排引擎。

    用法：
        validator = Validator(context={...})
        report = validator.validate(sql="SELECT ...", plan=sqlplan, conn=duckdb_conn)

    context 可包含：
      - conn: DuckDB 只读连接
      - available_tables: 可用表白名单
      - join_whitelist: JOIN 白名单
      - spark_result: PySpark 执行结果（Phase 3）
    """

    def __init__(self, context: Optional[dict[str, Any]] = None):
        """
        初始化验证器。

        Args:
            context: 运行时上下文——conn, available_tables, join_whitelist 等。
                     这些值在 validate() 调用时被注入到各检查项。
        """
        self._context = context or {}

        # 7 项检查按序号排列
        self._checks: list[tuple[int, str, str, CheckFn]] = [
            (1, "表/字段存在性", "FAIL", check_table_existence),
            (2, "安全关键字黑名单", "FAIL", check_forbidden_keywords),
            (3, "表访问权限", "FAIL", check_table_permissions),
            (4, "JOIN 白名单合规", "FAIL", check_join_whitelist),
            (5, "样本执行（SQL）", "FAIL", check_sample_execution),
            (6, "结果质量", "WARN", check_result_quality),
            (7, "交叉验证（SQL vs Spark DSL）", "WARN", check_cross_validation),
        ]

    def validate(
        self,
        sql: str = "",
        spark_code: str = "",
        plan: Optional[SQLPlan] = None,
        sql_result: Optional[SQLResult] = None,
        spark_result: Optional[SQLResult] = None,
    ) -> ValidationReport:
        """
        执行全部 7 项检查，返回聚合后的验证报告。

        Args:
            sql: 待验证的 SQL 草案
            spark_code: 待验证的 PySpark DSL 草案（可选）
            plan: 对应的 SQLPlan——为检查 #1/#4 提供表引用和 JOIN 信息
            sql_result: SQL 样本执行结果——为检查 #6/#7 提供原始数据
            spark_result: PySpark 执行结果——为检查 #7 提供对比数据

        Returns:
            ValidationReport 包含所有 7 项检查结果和聚合状态
        """
        checks: list[CheckResult] = []

        # 构建检查项的共享参数
        shared = dict(self._context)
        shared["sql"] = sql
        shared["spark_code"] = spark_code
        shared["plan"] = plan
        shared["sql_result"] = sql_result
        shared["result"] = sql_result  # 兼容 checks.py 中 check_result_quality 的参数名
        shared["spark_result"] = spark_result

        for check_id, name, severity, check_fn in self._checks:
            try:
                result = check_fn(**shared)
                # 确保 check_id 和 name 正确（防止检查函数内部写错）
                if result.check_id == 0:
                    result.check_id = check_id
                if not result.name:
                    result.name = name
                if not result.severity:
                    result.severity = severity
                checks.append(result)
            except Exception as exc:
                # 检查函数自身异常——记录为 FAIL
                checks.append(CheckResult(
                    check_id=check_id,
                    name=name,
                    status=ValidationStatus.FAILED,
                    detail=f"检查项执行异常: {exc}",
                    severity=severity,
                ))

        # 聚合结果
        overall = self._aggregate(checks)

        return ValidationReport(
            overall_status=overall,
            checks=checks,
        )

    def _aggregate(self, checks: list[CheckResult]) -> ValidationStatus:
        """
        聚合 7 项检查结果。

        规则：
          - 任一 FAIL → FAILED
          - 全通过但有 WARN → WARN
          - 全 PASSED → PASSED
        """
        has_fail = any(c.status == ValidationStatus.FAILED for c in checks)
        if has_fail:
            return ValidationStatus.FAILED

        has_warn = any(c.status == ValidationStatus.WARN for c in checks)
        if has_warn:
            return ValidationStatus.WARN

        return ValidationStatus.PASSED
