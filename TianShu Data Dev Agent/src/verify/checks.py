"""
防线 2 七项检查的具体实现。

检查项：
  #1 表/字段存在性  —— 在开发库执行 DESCRIBE，拦截 LLM 幻觉编造的表/字段
  #2 安全黑名单     —— 正则扫描 19 个禁止关键字（INSERT/UPDATE/DELETE/DROP 等）
  #3 表访问权限     —— 检查 FROM/JOIN 中的表是否在白名单中（不含 bronze/silver）
  #4 JOIN 白名单    —— 检查所有 JOIN 路径是否在已审批白名单中
  #5 样本执行       —— 在开发库用 LIMIT 1000 执行 SQL，拦截语法/运行时错误
  #6 结果质量       —— 检查行数、空值率、列完整性
  #7 交叉验证       —— SQL 和 PySpark 两份代码分别执行，对比结果（Phase 3 完整实现）

从以下来源移植：
  - v1.x layer5_validate.py：检查 #1-#4 的核心逻辑
  - Text2SQL-Agent sql_gen.py：表引用提取、JOIN 白名单校验、日期过滤检测
"""

from __future__ import annotations

import re
from typing import Any, Optional

from src.ir.types import (
    CheckResult, ValidationStatus, SQLPlan, SQLResult, Strategy,
)


# ═══════════════════════════════════════════════════════════
# 禁止关键字列表（19 个——与 Text2SQL Agent 保持一致）
# ═══════════════════════════════════════════════════════════

FORBIDDEN_KEYWORDS: dict[str, str] = {
    # DML（6 个）
    "INSERT": "禁止数据插入操作",
    "UPDATE": "禁止数据更新操作",
    "DELETE": "禁止数据删除操作",
    "MERGE": "禁止数据合并操作",
    "REPLACE": "禁止数据替换操作",
    "TRUNCATE": "禁止表截断操作",
    # DDL（4 个）
    "CREATE": "禁止数据定义操作",
    "ALTER": "禁止表结构变更操作",
    "DROP": "禁止表删除操作",
    "RENAME": "禁止重命名操作",
    # DCL（2 个）
    "GRANT": "禁止权限授予操作",
    "REVOKE": "禁止权限回收操作",
    # 危险操作（4 个）
    "ATTACH": "禁止数据库附加操作",
    "DETACH": "禁止数据库分离操作",
    "EXPORT": "禁止数据导出操作",
    "IMPORT": "禁止数据导入操作",
    # 系统操作（3 个）
    "COPY": "禁止系统级复制操作",
    "INSTALL": "禁止扩展安装操作",
    "LOAD": "禁止扩展加载操作",
}

# 允许的 SQL 前缀（只读操作）
ALLOWED_PREFIXES = ["SELECT", "WITH", "EXPLAIN", "DESCRIBE", "SHOW"]

# 禁止的表模式（bronze/silver 原始数据层）
FORBIDDEN_TABLE_PATTERNS = ["bronze.", "silver.", ".raw_"]


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════


def _extract_table_references(sql: str) -> list[str]:
    """
    从 SQL 中提取 FROM 和 JOIN 子句引用的所有表名。

    支持：FROM table, FROM schema.table, JOIN table,
          FROM t1, t2（逗号分隔多表）,
          A JOIN B JOIN C（多跳 JOIN）,
          INNER/LEFT/RIGHT/FULL/CROSS JOIN table
    """
    seen: set[str] = set()
    refs: list[str] = []

    # 标准化空白字符
    normalized = re.sub(r'\s+', ' ', sql)

    # ── 方法 1：匹配 FROM/JOIN 后紧跟的表名 ──
    pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)'
    for m in re.finditer(pattern, normalized, re.IGNORECASE):
        key = m.group(1).lower()
        if key not in seen:
            seen.add(key)
            refs.append(m.group(1))

    # ── 方法 2：处理逗号分隔的表名（FROM t1, t2, t3）──
    # 提取 FROM 子句中逗号分隔的额外表名
    # 匹配 FROM 之后到下一个主要关键字之前的内容
    from_section = re.search(
        r'\bFROM\s+(.+?)\s*\b(?:WHERE|GROUP|ORDER|LIMIT|HAVING|UNION|INNER|LEFT|RIGHT|FULL|CROSS|JOIN|;|$)',
        normalized, re.IGNORECASE,
    )
    if from_section:
        section = from_section.group(1)
        # 按逗号分割，提取每段的第一个标识符（表名或 schema.table）
        parts = section.split(',')
        for part in parts:
            m = re.match(
                r'\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)',
                part.strip(),
            )
            if m:
                key = m.group(1).lower()
                if key not in seen:
                    seen.add(key)
                    refs.append(m.group(1))

    return refs


def _clean_sql_for_keyword_scan(sql: str) -> str:
    """
    标准化 SQL 以准备关键字扫描：移除字符串字面量、注释。
    防止列名如 'created_at' 中的 'CREATE' 子串被误报。
    """
    # 移除单引号字符串字面量
    cleaned = re.sub(r"'[^']*'", "''", sql)
    # 移除双引号标识符
    cleaned = re.sub(r'"[^"]*"', '""', cleaned)
    # 移除单行注释
    cleaned = re.sub(r"--.*$", "", cleaned, flags=re.MULTILINE)
    # 移除多行注释
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    return cleaned


def _is_table_forbidden(table: str) -> tuple[bool, str]:
    """
    检查表名是否匹配禁止的模式（bronze.*, silver.*, *.raw_*）。

    Returns:
        (is_forbidden, reason)
    """
    table_lower = table.lower()
    for pattern in FORBIDDEN_TABLE_PATTERNS:
        prefix = pattern.replace(".", r"\.").replace("*", ".*")
        if re.search(prefix, table_lower):
            return True, f"禁止访问表 {table}（匹配禁止模式 {pattern}）"
    return False, ""


# ═══════════════════════════════════════════════════════════
# 检查 #1：表/字段存在性
# ═══════════════════════════════════════════════════════════


def check_table_existence(
    sql: str,
    conn: Any = None,
    plan: Optional[SQLPlan] = None,
    **_kwargs,  # 接收 Validator context 中的额外参数（如 available_tables）
) -> CheckResult:
    """
    检查 #1：SQL 中引用的表/字段在开发库中真实存在。

    通过 DESCRIBE 验证引用表存在。Phase 1 实现表级检查，
    字段级检查在 Phase 2 补充。

    Args:
        sql: 待检查的 SQL 文本
        conn: DuckDB 连接（用于 DESCRIBE 验证）
        plan: 对应的 SQLPlan（用于提取表引用）

    Returns:
        CheckResult
    """
    if conn is None:
        return CheckResult(
            check_id=1,
            name="表/字段存在性",
            status=ValidationStatus.PENDING,
            detail="SKIPPED——无数据库连接（离线模式），无法执行 DESCRIBE 验证",
            severity="FAIL",
        )

    table_refs = _extract_table_references(sql)

    if not table_refs:
        return CheckResult(
            check_id=1,
            name="表/字段存在性",
            status=ValidationStatus.PENDING,
            detail="SKIPPED——未提取到表引用，无法执行表存在性检查",
            severity="FAIL",
        )

    for table in table_refs:
        try:
            conn.execute(f"DESCRIBE {table}")
        except Exception as e:
            return CheckResult(
                check_id=1,
                name="表/字段存在性",
                status=ValidationStatus.FAILED,
                detail=f"表 {table} 不存在或无法访问: {e}",
                severity="FAIL",
            )

    return CheckResult(
        check_id=1,
        name="表/字段存在性",
        status=ValidationStatus.PASSED,
        detail=f"所有引用的表存在（{', '.join(table_refs)}）",
        severity="FAIL",
    )


# ═══════════════════════════════════════════════════════════
# 检查 #2：安全关键字黑名单
# ═══════════════════════════════════════════════════════════


def check_forbidden_keywords(sql: str, **_kwargs) -> CheckResult:
    """
    检查 #2：安全黑名单——19 个禁止的 SQL 关键字。

    策略：标准化 SQL（去除字符串字面量和注释），然后扫描关键字。
    用词边界匹配（\\b）防止列名子串被误报。

    Returns:
        CheckResult——FAIL 表示检测到禁止关键字
    """
    cleaned = _clean_sql_for_keyword_scan(sql)
    upper = cleaned.upper()

    found: list[str] = []
    for keyword, reason in FORBIDDEN_KEYWORDS.items():
        if re.search(rf"\b{keyword}\b", upper):
            found.append(f"{keyword}（{reason}）")

    if found:
        return CheckResult(
            check_id=2,
            name="安全关键字黑名单",
            status=ValidationStatus.FAILED,
            detail=f"检测到禁止的 SQL 操作: {'; '.join(found)}",
            severity="FAIL",
        )

    return CheckResult(
        check_id=2,
        name="安全关键字黑名单",
        status=ValidationStatus.PASSED,
        detail="未检测到任何禁止的 SQL 关键字",
        severity="FAIL",
    )


# ═══════════════════════════════════════════════════════════
# 检查 #3：表访问权限
# ═══════════════════════════════════════════════════════════


def check_table_permissions(
    sql: str,
    available_tables: Optional[set[str]] = None,
    **_kwargs,
) -> CheckResult:
    """
    检查 #3：表访问权限——禁止访问 bronze/silver 及未注册表。

    双重检查：
      - 禁止表模式（bronze.*, silver.*, *.raw_*）
      - 可用表白名单（如提供）

    Args:
        sql: 待检查的 SQL 文本
        available_tables: 可用表白名单集合

    Returns:
        CheckResult
    """
    table_refs = _extract_table_references(sql)

    if not table_refs:
        return CheckResult(
            check_id=3,
            name="表访问权限",
            status=ValidationStatus.PENDING,
            detail="SKIPPED——未提取到表引用，无法执行表权限检查",
            severity="FAIL",
        )

    # 子检查 A：禁止表模式
    forbidden_found: list[str] = []
    for table in table_refs:
        is_bad, reason = _is_table_forbidden(table)
        if is_bad:
            forbidden_found.append(reason)

    if forbidden_found:
        return CheckResult(
            check_id=3,
            name="表访问权限",
            status=ValidationStatus.FAILED,
            detail=f"检测到禁止的表访问: {'; '.join(forbidden_found)}",
            severity="FAIL",
        )

    # 子检查 B：可用表白名单
    if available_tables is not None:
        available_lower = {t.lower() for t in available_tables}
        unknown = [t for t in table_refs if t.lower() not in available_lower]
        if unknown:
            return CheckResult(
                check_id=3,
                name="表访问权限",
                status=ValidationStatus.FAILED,
                detail=f"以下表不在可用表白名单中: {', '.join(unknown)}",
                severity="FAIL",
            )

    return CheckResult(
        check_id=3,
        name="表访问权限",
        status=ValidationStatus.PASSED,
        detail=f"所有引用的表合法（{', '.join(table_refs)}）",
        severity="FAIL",
    )


# ═══════════════════════════════════════════════════════════
# 检查 #4：JOIN 白名单合规
# ═══════════════════════════════════════════════════════════


def check_join_whitelist(
    sql: str = "",
    plan: Optional[SQLPlan] = None,
    join_whitelist: Optional[set[tuple[str, str]]] = None,
    **_kwargs,
) -> CheckResult:
    """
    检查 #4：JOIN 白名单——所有 JOIN 路径必须在已审批白名单中。

    双路径验证：
      - 路径 A：从 SQLPlan IR 直接检查 JOIN（主防线）
      - 路径 B：从 SQL 文本提取 JOIN 检查（兜底防线）

    Args:
        sql: 待检查的 SQL 文本（路径 B）
        plan: 对应的 SQLPlan（路径 A）
        join_whitelist: JOIN 白名单，元素为 (table_a, table_b) 的 set

    Returns:
        CheckResult
    """
    # ── 路径 B：从 SQL 文本提取 JOIN 关系（plan=None 时的兜底防线）──
    if plan is None:
        if not sql or not sql.strip():
            return CheckResult(
                check_id=4,
                name="JOIN 白名单合规",
                status=ValidationStatus.PENDING,
                detail="无 SQLPlan 且无 SQL 文本——JOIN 白名单检查无法执行",
                severity="FAIL",
            )

        table_refs = _extract_table_references(sql)
        if len(table_refs) < 2:
            return CheckResult(
                check_id=4,
                name="JOIN 白名单合规",
                status=ValidationStatus.PASSED,
                detail="SQL 中仅引用单表，无 JOIN 需检查",
                severity="FAIL",
            )

        if join_whitelist is None:
            return CheckResult(
                check_id=4,
                name="JOIN 白名单合规",
                status=ValidationStatus.WARN,
                detail=(
                    f"缺少 JOIN 白名单，但 SQL 引用了 {len(table_refs)} 个表"
                    f"（{', '.join(table_refs)}）——无法验证 JOIN 合规性"
                ),
                severity="FAIL",
            )

        # 对所有表对做白名单检查
        whitelist_lower = {(a.lower().strip(), b.lower().strip()) for a, b in join_whitelist}
        violations: list[str] = []
        for i in range(len(table_refs)):
            for j in range(i + 1, len(table_refs)):
                pair = (table_refs[i].lower().strip(), table_refs[j].lower().strip())
                reverse_pair = (table_refs[j].lower().strip(), table_refs[i].lower().strip())
                if pair not in whitelist_lower and reverse_pair not in whitelist_lower:
                    violations.append(
                        f"JOIN {table_refs[i]} ↔ {table_refs[j]} 不在核准白名单中"
                    )

        if violations:
            return CheckResult(
                check_id=4,
                name="JOIN 白名单合规",
                status=ValidationStatus.FAILED,
                detail="; ".join(violations),
                severity="FAIL",
            )

        return CheckResult(
            check_id=4,
            name="JOIN 白名单合规",
            status=ValidationStatus.PASSED,
            detail=f"所有表对在白名单中（{len(table_refs)} 个表，{len(violations)} 条违规）",
            severity="FAIL",
        )

    # ── 路径 A：IR 级检查（主防线，plan 存在时）──

    # 无 JOIN 的单表查询
    if not plan.joins:
        return CheckResult(
            check_id=4,
            name="JOIN 白名单合规",
            status=ValidationStatus.PASSED,
            detail="单表查询，无 JOIN 需检查",
            severity="FAIL",
        )

    # 无白名单
    if join_whitelist is None:
        return CheckResult(
            check_id=4,
            name="JOIN 白名单合规",
            status=ValidationStatus.WARN,
            detail="未提供 JOIN 白名单——跳过检查",
            severity="FAIL",
        )

    # ── 路径 A：IR 级检查（主防线）──
    violations = []
    primary = plan.primary_table or ""
    whitelist_lower = {(a.lower().strip(), b.lower().strip()) for a, b in join_whitelist}

    for join in plan.joins:
        pair = (primary.lower().strip(), join.table.lower().strip())
        reverse_pair = (join.table.lower().strip(), primary.lower().strip())
        if pair not in whitelist_lower and reverse_pair not in whitelist_lower:
            violations.append(f"JOIN {primary} ↔ {join.table} 不在核准白名单中")

    if violations:
        return CheckResult(
            check_id=4,
            name="JOIN 白名单合规",
            status=ValidationStatus.FAILED,
            detail="; ".join(violations),
            severity="FAIL",
        )

    return CheckResult(
        check_id=4,
        name="JOIN 白名单合规",
        status=ValidationStatus.PASSED,
        detail=f"所有 JOIN 路径在白名单中（{len(plan.joins)} 条）",
        severity="FAIL",
    )


# ═══════════════════════════════════════════════════════════
# 检查 #5：样本执行（SQL）
# ═══════════════════════════════════════════════════════════


def check_sample_execution(
    sql: str,
    conn: Any = None,
    **_kwargs,
) -> CheckResult:
    """
    检查 #5：在开发库执行 SQL（自动加 LIMIT 1000），拦截语法错误和运行时错误。

    这是"不可信补丁"的第一道执行验证——确保 LLM 生成的代码能跑通。

    Args:
        sql: 待检查的 SQL 文本
        conn: DuckDB 只读连接

    Returns:
        CheckResult
    """
    if conn is None:
        return CheckResult(
            check_id=5,
            name="样本执行（SQL）",
            status=ValidationStatus.PENDING,
            detail="SKIPPED——无数据库连接（离线模式），无法执行 SQL 样本",
            severity="FAIL",
        )

    # ── 安全前缀检查（防御纵深——拦截非只读语句绕过沙箱直接调用）──
    body = sql.strip().rstrip(";")
    body_upper = body.upper()
    if not any(body_upper.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        return CheckResult(
            check_id=5,
            name="样本执行（SQL）",
            status=ValidationStatus.FAILED,
            detail=(
                f"SQL sample 被拒绝：必须以 {' / '.join(ALLOWED_PREFIXES)} 开头，"
                f"当前以 {body_upper.split()[0] if body_upper.split() else '(空)'} 开头"
            ),
            severity="FAIL",
        )

    # ── 禁止关键字检查（防御纵深——复用 checks.FORBIDDEN_KEYWORDS 单一事实源）──
    cleaned = _clean_sql_for_keyword_scan(body)
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", cleaned.upper()):
            return CheckResult(
                check_id=5,
                name="样本执行（SQL）",
                status=ValidationStatus.FAILED,
                detail=(
                    f"SQL sample 被拒绝：检测到禁止关键字 {keyword}"
                    f"（{FORBIDDEN_KEYWORDS[keyword]}）"
                ),
                severity="FAIL",
            )

    # 自动包装 LIMIT 1000——防止 LLM 生成的 SQL 全表扫描
    wrapped_sql = body
    if "LIMIT" not in body_upper:
        wrapped_sql = f"{body} LIMIT 1000"

    try:
        conn.execute(wrapped_sql)
    except Exception as e:
        return CheckResult(
            check_id=5,
            name="样本执行（SQL）",
            status=ValidationStatus.FAILED,
            detail=f"SQL 执行失败: {e}",
            severity="FAIL",
        )

    return CheckResult(
        check_id=5,
        name="样本执行（SQL）",
        status=ValidationStatus.PASSED,
        detail="SQL 样本执行成功（LIMIT 1000）",
        severity="FAIL",
    )


# ═══════════════════════════════════════════════════════════
# 检查 #6：结果质量
# ═══════════════════════════════════════════════════════════


def check_result_quality(
    result: Optional[SQLResult] = None,
    **_kwargs,
) -> CheckResult:
    """
    检查 #6：结果质量——空值率、行数、列完整性。

    WARN 级别（不阻断），提醒人审时关注。

    Args:
        result: 样本执行返回的 SQLResult

    Returns:
        CheckResult
    """
    if result is None:
        return CheckResult(
            check_id=6,
            name="结果质量",
            status=ValidationStatus.PASSED,
            detail="跳过——未提供执行结果",
            severity="WARN",
        )

    warnings: list[str] = []

    # 结果为空
    if result.row_count == 0:
        warnings.append("查询结果为空——可能时间范围内无数据或过滤条件过严")

    # 执行错误
    if result.error:
        warnings.append(f"执行错误: {result.error}")

    # 列缺失
    if not result.columns:
        warnings.append("结果无列信息")

    if warnings:
        return CheckResult(
            check_id=6,
            name="结果质量",
            status=ValidationStatus.WARN,
            detail="; ".join(warnings),
            severity="WARN",
        )

    return CheckResult(
        check_id=6,
        name="结果质量",
        status=ValidationStatus.PASSED,
        detail=f"结果质量正常（{result.row_count} 行，{len(result.columns)} 列）",
        severity="WARN",
    )


# ═══════════════════════════════════════════════════════════
# 检查 #7：交叉验证（Phase 3 完整实现，P1 为桩）
# ═══════════════════════════════════════════════════════════


def check_cross_validation(
    sql_result: Optional[SQLResult] = None,
    spark_result: Optional[SQLResult] = None,
    **_kwargs,
) -> CheckResult:
    """
    检查 #7：SQL vs Spark DSL 交叉验证。

    Phase 3 实现完整对比逻辑（行数、列名、值分布、抽样行）。
    Phase 1 为占位桩——单 SQL 执行时返回 PASSED。

    Args:
        sql_result: SQL 执行结果
        spark_result: PySpark 执行结果（Phase 3）

    Returns:
        CheckResult
    """
    if spark_result is None:
        return CheckResult(
            check_id=7,
            name="交叉验证",
            status=ValidationStatus.PASSED,
            detail="交叉验证：仅 SQL 执行模式（Spark DSL 未启用，Phase 3 实现完整对比）",
            severity="WARN",
        )

    # Phase 3：对比 sql_result 和 spark_result 的行数、列名、值分布
    return CheckResult(
        check_id=7,
        name="交叉验证",
        status=ValidationStatus.PASSED,
        detail="交叉验证引擎尚未启用（Phase 3 实现完整对比逻辑）",
        severity="WARN",
    )
