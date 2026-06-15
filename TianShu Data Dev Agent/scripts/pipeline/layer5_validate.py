"""
Layer 5：SQL 校验层

职责：
  1. 安全策略黑名单检查（禁止 DML/DDL/DCL 等操作）
  2. 表引用合法性检查（禁止 bronze/silver 表）
  3. JOIN 白名单检查
  4. 日期过滤合规检查（必须通过 dim_date 或 G3 表内置日期列）
  5. 完全限定名检查（所有表名必须是 schema.table 格式）

LLM 角色：
  **完全禁止**。此层是纯规则引擎。

输入：SQL 文本 + SQLPlan
输出：校验报告 {passed, issues[], warnings[]}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .layer3_ir import SQLPlan
from .column_binding import is_table_forbidden, JOIN_WHITELIST, FORBIDDEN_TABLE_PATTERNS


# ═══════════════════════════════════════════════════════════
# 安全策略黑名单（从 sql_safety_policy.yml 衍生）
# ═══════════════════════════════════════════════════════════

# 禁止的 SQL 关键字（不区分大小写）
FORBIDDEN_KEYWORDS: dict[str, str] = {
    # DML
    "INSERT": "禁止数据插入操作",
    "UPDATE": "禁止数据更新操作",
    "DELETE": "禁止数据删除操作",
    "MERGE": "禁止数据合并操作",
    "REPLACE": "禁止数据替换操作",
    "TRUNCATE": "禁止表截断操作",
    # DDL
    "CREATE": "禁止数据定义操作",
    "ALTER": "禁止表结构变更操作",
    "DROP": "禁止表删除操作",
    "RENAME": "禁止重命名操作",
    # DCL
    "GRANT": "禁止权限授予操作",
    "REVOKE": "禁止权限回收操作",
    # 危险操作
    "ATTACH": "禁止数据库附加操作",
    "DETACH": "禁止数据库分离操作",
    "EXPORT": "禁止数据导出操作",
    "IMPORT": "禁止数据导入操作",
    # 系统操作
    "COPY": "禁止系统级复制操作",
    "INSTALL": "禁止扩展安装操作",
    "LOAD": "禁止扩展加载操作",
}

# 允许的 SQL 前缀（只读操作）
ALLOWED_PREFIXES = ["SELECT", "WITH", "EXPLAIN", "DESCRIBE", "SHOW"]


@dataclass
class ValidationCheck:
    """单个校验检查项"""
    name: str
    passed: bool
    detail: str


@dataclass
class ValidationReport:
    """校验报告"""
    passed: bool
    safety_checks: list[ValidationCheck] = field(default_factory=list)
    table_reference_checks: list[ValidationCheck] = field(default_factory=list)
    join_checks: list[ValidationCheck] = field(default_factory=list)
    date_compliance: list[ValidationCheck] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _check_forbidden_keywords(sql: str) -> ValidationCheck:
    """
    检查 SQL 中是否包含禁止的关键字

    策略：标准化 SQL（去除字符串字面量和注释），然后扫描关键字。
    用词边界匹配防止误报（如 'created_at' 不应匹配 'CREATE'）。
    """
    # 移除单引号字符串字面量（避免字符串内容误匹配）
    cleaned = re.sub(r"'[^']*'", "''", sql)
    # 移除双引号标识符
    cleaned = re.sub(r'"[^"]*"', '""', cleaned)
    # 移除单行注释
    cleaned = re.sub(r"--.*$", "", cleaned, flags=re.MULTILINE)
    # 移除多行注释
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)

    # 标准化为全大写
    upper = cleaned.upper()

    found: list[str] = []
    for keyword, reason in FORBIDDEN_KEYWORDS.items():
        # 用词边界匹配（\b 匹配单词边界）
        if re.search(rf"\b{keyword}\b", upper):
            found.append(f"{keyword} ({reason})")

    if found:
        return ValidationCheck(
            name="禁止操作关键词检查",
            passed=False,
            detail=f"检测到禁止的 SQL 操作: {', '.join(found)}",
        )
    return ValidationCheck(
        name="禁止操作关键词检查",
        passed=True,
        detail="未检测到禁止的 SQL 操作",
    )


def _check_allowed_prefix(sql: str) -> ValidationCheck:
    """检查 SQL 是否以只读操作开头"""
    stripped = sql.strip().upper()
    for prefix in ALLOWED_PREFIXES:
        if stripped.startswith(prefix):
            return ValidationCheck(
                name="只读前缀检查",
                passed=True,
                detail=f"SQL 以 '{prefix}' 开头，允许执行",
            )
    return ValidationCheck(
        name="只读前缀检查",
        passed=False,
        detail=f"SQL 未以允许的前缀开头。允许的前缀: {ALLOWED_PREFIXES}",
    )


def _check_table_references(sql: str, plan: SQLPlan) -> ValidationCheck:
    """检查 SQL 中引用的表是否在允许列表中"""
    if plan.join_graph is None:
        return ValidationCheck(
            name="表引用检查",
            passed=False,
            detail="SQLPlan 缺少 join_graph，无法验证表引用",
        )

    # 从 JoinGraph 提取所有表
    tables = [plan.join_graph.primary.table]
    for join_node in plan.join_graph.joins:
        tables.append(join_node.table)

    forbidden_found: list[str] = []
    for table in tables:
        is_bad, reason = is_table_forbidden(table)
        if is_bad:
            forbidden_found.append(reason)

    if forbidden_found:
        return ValidationCheck(
            name="表引用检查",
            passed=False,
            detail=f"检测到禁止的表访问: {', '.join(forbidden_found)}",
        )

    return ValidationCheck(
        name="表引用检查",
        passed=True,
        detail=f"所有引用的表 ({', '.join(tables)}) 合法",
    )


def _check_join_whitelist(plan: SQLPlan) -> ValidationCheck:
    """检查 JOIN 是否在核准的白名单中"""
    if plan.join_graph is None:
        return ValidationCheck(
            name="JOIN 白名单检查",
            passed=False,
            detail="SQLPlan 缺少 join_graph",
        )

    joins = plan.join_graph.joins
    if not joins:
        return ValidationCheck(
            name="JOIN 白名单检查",
            passed=True,
            detail="单表查询，无 JOIN 需检查",
        )

    for join_node in joins:
        primary_table = plan.join_graph.primary.table
        # 在白名单中查找
        found = False
        for whitelist_path in JOIN_WHITELIST:
            if (
                whitelist_path.left_table == primary_table
                and whitelist_path.right_table == join_node.table
            ) or (
                whitelist_path.left_table == join_node.table
                and whitelist_path.right_table == primary_table
            ):
                found = True
                break

        if not found:
            return ValidationCheck(
                name="JOIN 白名单检查",
                passed=False,
                detail=f"JOIN '{primary_table} ↔ {join_node.table}' 不在白名单中，禁止执行",
            )

    return ValidationCheck(
        name="JOIN 白名单检查",
        passed=True,
        detail="所有 JOIN 路径在白名单中",
    )


def _check_date_compliance(plan: SQLPlan) -> ValidationCheck:
    """检查日期过滤是否符合规范"""
    has_date_filter = False
    for fb in plan.filter_bindings:
        if fb.filter_type == "date_range":
            has_date_filter = True
            # G3 汇总表直接含日期列 → 合规
            # G2 表需要确认是否通过 dim_date
            if plan.source_layer == "g2" and plan.execution_constraints:
                if plan.execution_constraints.requires_date_dim:
                    # 检查是否实际 JOIN 了 dim_date
                    dim_date_joined = any(
                        "dim_date" in j.table
                        for j in (plan.join_graph.joins if plan.join_graph else [])
                    )
                    if not dim_date_joined:
                        return ValidationCheck(
                            name="日期合规检查",
                            passed=False,
                            detail="G2 层查询需要通过 gold.dim_date 过滤日期，但 JOIN 中未找到 dim_date",
                        )
            break

    if has_date_filter:
        return ValidationCheck(
            name="日期合规检查",
            passed=True,
            detail="日期过滤合规",
        )

    return ValidationCheck(
        name="日期合规检查",
        passed=True,
        detail="无日期过滤要求",
    )


def _check_fully_qualified_names(sql: str, plan: SQLPlan) -> ValidationCheck:
    """
    检查 SQL 中的表名是否使用全限定格式（schema.table）

    对于 G3 汇总表，直接有日期列，不需要通过 dim_date；
    对于 G2 fact 表，需要确认日期过滤合规。
    """
    if plan.join_graph is None:
        return ValidationCheck(
            name="全限定名检查",
            passed=True,
            detail="跳过（无 join_graph）",
        )

    tables = [plan.join_graph.primary.table]
    for jn in plan.join_graph.joins:
        tables.append(jn.table)

    for table in tables:
        if "." not in table:
            return ValidationCheck(
                name="全限定名检查",
                passed=False,
                detail=f"表名 '{table}' 未使用全限定格式（需要 schema.table）",
            )

    return ValidationCheck(
        name="全限定名检查",
        passed=True,
        detail="所有表名使用全限定格式",
    )


def validate_sql(sql: str, plan: SQLPlan) -> ValidationReport:
    """
    对 SQL 执行全部安全与语义校验

    这是管道的第 5 层——Layer 4 的输出必须先通过此层的所有检查，
    才能进入 Layer 6 执行。
    """
    report = ValidationReport(passed=True)

    # ── 安全黑名单检查 ──
    kw_check = _check_forbidden_keywords(sql)
    report.safety_checks.append(kw_check)

    prefix_check = _check_allowed_prefix(sql)
    report.safety_checks.append(prefix_check)

    # ── 表引用检查 ──
    table_check = _check_table_references(sql, plan)
    report.table_reference_checks.append(table_check)

    fq_check = _check_fully_qualified_names(sql, plan)
    report.table_reference_checks.append(fq_check)

    # ── JOIN 白名单检查 ──
    join_check = _check_join_whitelist(plan)
    report.join_checks.append(join_check)

    # ── 日期合规检查 ──
    date_check = _check_date_compliance(plan)
    report.date_compliance.append(date_check)

    # ── 汇总结果 ──
    all_checks = (
        report.safety_checks
        + report.table_reference_checks
        + report.join_checks
        + report.date_compliance
    )

    for check in all_checks:
        if not check.passed:
            report.issues.append(f"[{check.name}] {check.detail}")
            report.passed = False

    # ── 非阻塞警告 ──
    if plan.source_layer == "g2":
        report.warnings.append(
            f"查询使用 G2 层 ({plan.join_graph.primary.table if plan.join_graph else 'unknown'})，"
            f"G3 汇总表不可用。建议确认是否需要新建 G3 汇总表。"
        )

    return report
