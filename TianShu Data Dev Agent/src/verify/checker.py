"""
v2 Validator 编排入口。

checker.py 是 Data Dev Agent v2 的唯一 Validator 编排入口：
- validate_static()：M3 主工作流使用，只做 SQL/Spark 草案静态检查。
- validate()：保留旧七项检查兼容路径，供 v1/v2 既有测试继续使用。

旧的 scripts/pipeline/layer5_validate.py 属于 v1 legacy validator，不作为 v2 主入口。
"""

from __future__ import annotations

import re
from typing import Any, Callable, Optional

from src.ir.types import CheckResult, SQLPlan, SQLResult, ValidationReport, ValidationStatus

from .checks import (
    ALLOWED_PREFIXES,
    FORBIDDEN_KEYWORDS,
    _clean_sql_for_keyword_scan,
    _extract_table_references,
    check_cross_validation,
    check_forbidden_keywords,
    check_join_whitelist,
    check_result_quality,
    check_sample_execution,
    check_table_existence,
    check_table_permissions,
)


CheckFn = Callable[..., CheckResult]

SQL_KEYWORDS = {
    "select", "from", "where", "group", "by", "order", "as", "and", "or",
    "between", "in", "not", "null", "is", "on", "join", "left", "right",
    "inner", "outer", "full", "cross", "limit", "offset", "sum", "count",
    "avg", "min", "max", "date", "cast", "distinct", "case", "when", "then",
    "else", "end", "desc", "asc",
}

SPARK_FORBIDDEN_PATTERNS = [
    ".write",
    ".save",
    "save(",
    "saveastable",
    "insertinto",
    "overwrite",
    "parquet(",
    "csv(",
    "json(",
]


class Validator:
    """v2 验证器，统一编排静态检查与兼容检查。"""

    def __init__(self, context: Optional[dict[str, Any]] = None):
        """初始化验证器上下文。"""
        self._context = context or {}
        self._checks: list[tuple[int, str, str, CheckFn]] = [
            (1, "表/字段存在性", "FAIL", check_table_existence),
            (2, "安全关键字黑名单", "FAIL", check_forbidden_keywords),
            (3, "表访问权限", "FAIL", check_table_permissions),
            (4, "JOIN 白名单合规", "FAIL", check_join_whitelist),
            (5, "样本执行（SQL）", "FAIL", check_sample_execution),
            (6, "结果质量", "WARN", check_result_quality),
            (7, "交叉验证（SQL vs Spark DSL）", "WARN", check_cross_validation),
        ]

    def validate_context(self) -> list[CheckResult]:
        """
        前置检查：验证上下文完整性，报告缺失的关键上下文。

        检查项：
          - 数据库连接（conn）：表存在性 #1、样本执行 #5 依赖
          - 可用表列表（available_tables）：表权限 #3 依赖
          - JOIN 白名单（join_whitelist）：JOIN 合规 #4 依赖

        Returns:
            CheckResult 列表，每一项描述缺失的上下文及其影响（空列表 = 上下文完整）
        """
        issues: list[CheckResult] = []
        ctx = self._context

        if ctx.get("conn") is None:
            issues.append(CheckResult(
                check_id=0,
                name="上下文检查",
                status=ValidationStatus.WARN,
                detail=(
                    "SKIPPED 原因：缺少数据库连接（conn）——"
                    "表存在性检查（#1）和样本执行检查（#5）将无法执行，"
                    "返回 PENDING 状态"
                ),
                severity="WARN",
            ))

        if ctx.get("available_tables") is None:
            issues.append(CheckResult(
                check_id=0,
                name="上下文检查",
                status=ValidationStatus.WARN,
                detail=(
                    "SKIPPED 原因：缺少可用表列表（available_tables）——"
                    "表访问权限检查（#3）将跳过白名单验证，仅检查禁止表模式"
                ),
                severity="WARN",
            ))

        if ctx.get("join_whitelist") is None:
            issues.append(CheckResult(
                check_id=0,
                name="上下文检查",
                status=ValidationStatus.WARN,
                detail=(
                    "SKIPPED 原因：缺少 JOIN 白名单（join_whitelist）——"
                    "JOIN 白名单合规检查（#4）将跳过，多表 JOIN 无法验证"
                ),
                severity="WARN",
            ))

        return issues

    def validate_static(
        self,
        sql: str = "",
        spark_code: str = "",
        lineage: Optional[dict[str, Any]] = None,
    ) -> ValidationReport:
        """统一静态检查 SQL 草案和 Spark 草案。"""
        lineage = lineage or {}
        allowed_tables, allowed_fields = _allowed_refs(lineage)
        checks = [
            self._check_sql_select_only(sql),
            self._check_sql_forbidden_keywords(sql),
            self._check_sql_lineage(sql, allowed_tables, allowed_fields),
            self._check_spark_forbidden_patterns(spark_code),
            self._check_spark_lineage(spark_code, allowed_tables, allowed_fields),
        ]
        return ValidationReport(overall_status=self._aggregate(checks), checks=checks)

    def validate(
        self,
        sql: str = "",
        spark_code: str = "",
        plan: Optional[SQLPlan] = None,
        sql_result: Optional[SQLResult] = None,
        spark_result: Optional[SQLResult] = None,
    ) -> ValidationReport:
        """执行旧七项检查兼容路径（自动前置上下文检查）。"""
        # 前置上下文检查——缺失关键上下文时自动写入报告
        checks: list[CheckResult] = list(self.validate_context())

        shared = dict(self._context)
        shared["sql"] = sql
        shared["spark_code"] = spark_code
        shared["plan"] = plan
        shared["sql_result"] = sql_result
        shared["result"] = sql_result
        shared["spark_result"] = spark_result

        for check_id, name, severity, check_fn in self._checks:
            try:
                result = check_fn(**shared)
                if result.check_id == 0:
                    result.check_id = check_id
                if not result.name:
                    result.name = name
                if not result.severity:
                    result.severity = severity
                checks.append(result)
            except Exception as exc:
                checks.append(CheckResult(
                    check_id=check_id,
                    name=name,
                    status=ValidationStatus.FAILED,
                    detail=f"检查项执行异常: {exc}",
                    severity=severity,
                ))

        return ValidationReport(overall_status=self._aggregate(checks), checks=checks)

    def _check_sql_select_only(self, sql: str) -> CheckResult:
        """确认 SQL 草案以只读业务查询开头（SELECT / WITH）。"""
        cleaned = _clean_sql_for_keyword_scan(sql).strip().lstrip("(")
        if not cleaned:
            return CheckResult(
                101, "SQL 只读语句", ValidationStatus.WARN,
                "SQL 为空，需要人工审查", "WARN",
            )
        upper = cleaned.upper()
        for prefix in ALLOWED_PREFIXES:
            if upper.startswith(prefix):
                return CheckResult(
                    101, "SQL 只读语句", ValidationStatus.PASSED,
                    f"SQL 以 {prefix} 开始（只读安全前缀）", "FAIL",
                )
        return CheckResult(
            101, "SQL 只读语句", ValidationStatus.FAILED,
            f"SQL 草案必须以 {' / '.join(ALLOWED_PREFIXES)} 开头，当前以 {upper.split()[0] if upper.split() else '(空)'} 开头",
            "FAIL",
        )

    def _check_sql_forbidden_keywords(self, sql: str) -> CheckResult:
        """拦截 DDL/DML 与 DuckDB 危险操作。"""
        cleaned = _clean_sql_for_keyword_scan(sql).upper()
        found = [
            keyword
            for keyword in FORBIDDEN_KEYWORDS
            if re.search(rf"\b{keyword}\b", cleaned)
        ]
        if found:
            return CheckResult(
                102,
                "SQL 禁止关键字",
                ValidationStatus.FAILED,
                f"检测到禁止关键字: {', '.join(sorted(found))}",
                "FAIL",
            )
        return CheckResult(102, "SQL 禁止关键字", ValidationStatus.PASSED, "未检测到 DDL/DML/危险操作", "FAIL")

    def _check_sql_lineage(
        self,
        sql: str,
        allowed_tables: set[str],
        allowed_fields: set[str],
    ) -> CheckResult:
        """检查 SQL 表和字段是否来自 lineage。"""
        table_refs = _extract_table_references(sql)
        unknown_tables = [
            table for table in table_refs
            if _normalize_ref(table) not in allowed_tables
        ]
        if unknown_tables:
            return CheckResult(
                103,
                "SQL lineage 表引用",
                ValidationStatus.FAILED,
                f"SQL 引用未声明表: {', '.join(unknown_tables)}",
                "FAIL",
            )

        unknown_fields = _unknown_sql_fields(sql, allowed_fields, allowed_tables)
        if unknown_fields:
            return CheckResult(
                104,
                "SQL lineage 字段引用",
                ValidationStatus.WARN,
                f"SQL 引用未声明字段，需 Human Review: {', '.join(sorted(unknown_fields))}",
                "WARN",
            )
        return CheckResult(104, "SQL lineage 字段引用", ValidationStatus.PASSED, "SQL 字段来自 lineage", "WARN")

    def _check_spark_forbidden_patterns(self, spark_code: str) -> CheckResult:
        """拦截 Spark 写入动作。"""
        lowered = spark_code.lower()
        found = [pattern for pattern in SPARK_FORBIDDEN_PATTERNS if pattern in lowered]
        if found:
            return CheckResult(
                105,
                "Spark 禁止写入动作",
                ValidationStatus.FAILED,
                f"Spark 草案包含写入或落盘动作: {', '.join(found)}",
                "FAIL",
            )
        return CheckResult(105, "Spark 禁止写入动作", ValidationStatus.PASSED, "未检测到 Spark 写入动作", "FAIL")

    def _check_spark_lineage(
        self,
        spark_code: str,
        allowed_tables: set[str],
        allowed_fields: set[str],
    ) -> CheckResult:
        """检查 Spark 表和字段是否来自 lineage。"""
        table_refs = re.findall(r"spark\.table\(\s*['\"]([^'\"]+)['\"]\s*\)", spark_code, re.IGNORECASE)
        unknown_tables = [
            table for table in table_refs
            if _normalize_ref(table) not in allowed_tables
        ]
        if unknown_tables:
            return CheckResult(
                106,
                "Spark lineage 表引用",
                ValidationStatus.FAILED,
                f"Spark 引用未声明表: {', '.join(unknown_tables)}",
                "FAIL",
            )

        unknown_fields = _unknown_spark_fields(spark_code, allowed_fields)
        if unknown_fields:
            return CheckResult(
                107,
                "Spark lineage 字段引用",
                ValidationStatus.WARN,
                f"Spark 引用未声明字段，需 Human Review: {', '.join(sorted(unknown_fields))}",
                "WARN",
            )
        return CheckResult(107, "Spark lineage 字段引用", ValidationStatus.PASSED, "Spark 字段来自 lineage", "WARN")

    def _aggregate(self, checks: list[CheckResult]) -> ValidationStatus:
        """聚合检查结果。"""
        if any(check.status == ValidationStatus.FAILED for check in checks):
            return ValidationStatus.FAILED
        if any(check.status == ValidationStatus.WARN for check in checks):
            return ValidationStatus.WARN
        if any(check.status == ValidationStatus.PENDING for check in checks):
            return ValidationStatus.PENDING
        return ValidationStatus.PASSED


def _allowed_refs(lineage: dict[str, Any]) -> tuple[set[str], set[str]]:
    """从 lineage/source_refs.yml 提取允许的表和字段。"""
    tables: set[str] = set()
    fields: set[str] = set()

    for table in lineage.get("source_tables", []) or []:
        name = table.get("name") if isinstance(table, dict) else table
        if name:
            tables.add(_normalize_ref(str(name)))

    for field in lineage.get("source_fields", []) or []:
        if not isinstance(field, dict):
            continue
        for key in ("name", "field", "alias"):
            value = field.get(key)
            if value:
                fields.add(_normalize_ref(str(value)))
        table = field.get("table")
        if table:
            tables.add(_normalize_ref(str(table)))

    for metric in lineage.get("metric_sources", []) or []:
        if not isinstance(metric, dict):
            continue
        for key in ("name", "field", "alias"):
            value = metric.get(key)
            if value:
                fields.add(_normalize_ref(str(value)))

    for grain in lineage.get("grain", []) or []:
        fields.add(_normalize_ref(str(grain)))

    filters = lineage.get("filters", {}) or {}
    if isinstance(filters, dict):
        for key in filters:
            if key != "date_range":
                fields.add(_normalize_ref(str(key)))

    return tables, fields


def _normalize_ref(value: str) -> str:
    """规范化表名或字段名，便于大小写无关比较。"""
    return value.strip().strip("`").strip('"').lower()


def _unknown_sql_fields(sql: str, allowed_fields: set[str], allowed_tables: set[str]) -> set[str]:
    """用保守 token 扫描识别明显未声明字段。"""
    cleaned = _clean_sql_for_keyword_scan(sql)
    cleaned = re.sub(r"\b\d+(?:\.\d+)?\b", " ", cleaned)
    tokens = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", cleaned)
    table_parts = {
        part
        for table in allowed_tables
        for part in table.split(".")
    }
    unknown: set[str] = set()
    for token in tokens:
        norm = _normalize_ref(token)
        if norm in SQL_KEYWORDS or norm in table_parts or norm in allowed_fields:
            continue
        if norm in {"true", "false"}:
            continue
        unknown.add(token)
    return unknown


def _unknown_spark_fields(spark_code: str, allowed_fields: set[str]) -> set[str]:
    """从 Spark 常见字段调用中提取字段名。"""
    candidates: set[str] = set()
    patterns = [
        r"F\.col\(\s*['\"]([^'\"]+)['\"]\s*\)",
        r"F\.(?:sum|count|avg|min|max)\(\s*['\"]([^'\"]+)['\"]\s*\)",
        r"\.groupBy\(([^)]*)\)",
        r"\.select\(([^)]*)\)",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, spark_code, flags=re.IGNORECASE | re.DOTALL):
            candidates.update(re.findall(r"['\"]([^'\"]+)['\"]", match))

    return {
        candidate for candidate in candidates
        if _normalize_ref(candidate) not in allowed_fields
    }
