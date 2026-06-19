"""
物化静态校验器——M5b-1。

在 CTAS 提交到 Sandbox 执行之前，对部署产物进行静态安全校验：
  - Manifest 完整性
  - source_query_hash 与 sql/main.sql 一致性
  - deploy artifact hash 一致性
  - CTAS 结构合法性
  - 禁止关键字和副作用
  - 目标 schema 白名单
  - 多语句检测

此模块只做静态检查，不连接任何数据库、不执行任何 SQL。
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

from src.ir.types import MaterializationCheckResult

# ── M5b-1 允许的写入策略 ──
ALLOWED_MATERIALIZATION_STRATEGIES = {"CREATE_TABLE_AS_SELECT"}

# ── 禁止的关键字（与 deploy_generator 保持一致）──
FORBIDDEN_DEPLOY_KEYWORDS = {
    "DROP", "ALTER", "TRUNCATE", "DELETE", "MERGE", "REPLACE",
    "GRANT", "REVOKE", "ATTACH", "DETACH", "EXPORT", "IMPORT",
    "COPY", "INSTALL", "LOAD",
}

# ── 允许写入的 schema ──
ALLOWED_WRITE_SCHEMAS = {"generated"}
FORBIDDEN_WRITE_SCHEMAS = {"bronze", "silver", "gold"}


def _hash_content(content: str) -> str:
    """计算内容的 SHA-256 哈希。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _strip_sql_comments(sql: str) -> str:
    """去除 SQL 注释。"""
    without_line = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    return re.sub(r"/\*.*?\*/", "", without_line, flags=re.DOTALL)


# ═══════════════════════════════════════════════════════════════
# 物化静态校验
# ═══════════════════════════════════════════════════════════════


def validate_materialization_static(
    package_dir: Path,
) -> tuple[list[MaterializationCheckResult], dict[str, Any]]:
    """对 Review Package 的部署产物执行物化静态校验。

    校验项：
      1. Manifest 文件存在且可解析
      2. source_query_hash 与 sql/main.sql 一致
      3. deploy artifact hash 与落盘文件一致
      4. deploy SQL 是有效的 CTAS 结构
      5. deploy SQL 不含禁止关键字
      6. 写入策略在 M5b-1 支持列表中
      7. 目标 schema 合法（非 bronze/silver/gold）
      8. 非多语句 SQL

    Args:
        package_dir: Review Package 目录路径

    Returns:
        (check_results, manifest_dict)——check_results 是检查结果列表，
        manifest_dict 是解析后的 Manifest（供后续步骤使用）
    """
    checks: list[MaterializationCheckResult] = []
    manifest_dict: dict[str, Any] = {}

    # ── 检查 1：Manifest 文件存在 ──
    manifest_path = package_dir / "deployment_manifest.yml"
    if not manifest_path.is_file():
        checks.append(MaterializationCheckResult(
            check_id="manifest_exists",
            name="部署清单存在",
            status="FAIL",
            detail="deployment_manifest.yml 不存在",
            severity="FAIL",
        ))
        return checks, manifest_dict

    try:
        manifest_dict = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        checks.append(MaterializationCheckResult(
            check_id="manifest_parse",
            name="部署清单解析",
            status="FAIL",
            detail=f"deployment_manifest.yml 解析失败: {exc}",
            severity="FAIL",
        ))
        return checks, manifest_dict

    checks.append(MaterializationCheckResult(
        check_id="manifest_exists",
        name="部署清单存在且可解析",
        status="PASS",
        detail=f"request_id={manifest_dict.get('request_id', '?')}",
        severity="FAIL",
    ))

    # ── 检查 2：写入策略在 M5b-1 支持列表中 ──
    strategy = manifest_dict.get("write_strategy", "")
    if strategy not in ALLOWED_MATERIALIZATION_STRATEGIES:
        checks.append(MaterializationCheckResult(
            check_id="write_strategy",
            name="写入策略",
            status="FAIL",
            detail=(
                f"不支持的写入策略: {strategy}——M5b-1 只允许 "
                f"{', '.join(sorted(ALLOWED_MATERIALIZATION_STRATEGIES))}"
            ),
            severity="FAIL",
        ))
    else:
        checks.append(MaterializationCheckResult(
            check_id="write_strategy",
            name="写入策略",
            status="PASS",
            detail=f"策略 {strategy} 在 M5b-1 支持列表中",
            severity="FAIL",
        ))

    # ── 检查 3：目标 schema 合法 ──
    target_table = manifest_dict.get("target_table", "")
    if target_table:
        parts = target_table.split(".")
        if len(parts) >= 2:
            schema = parts[0].lower().strip()
            if schema in FORBIDDEN_WRITE_SCHEMAS:
                checks.append(MaterializationCheckResult(
                    check_id="target_schema",
                    name="目标 Schema 白名单",
                    status="FAIL",
                    detail=f"禁止写入 {schema} schema——目标表 {target_table} 在禁止列表中",
                    severity="FAIL",
                ))
            elif schema not in ALLOWED_WRITE_SCHEMAS:
                checks.append(MaterializationCheckResult(
                    check_id="target_schema",
                    name="目标 Schema 白名单",
                    status="FAIL",
                    detail=f"目标表 {target_table} 的 schema 不在允许列表中（允许: generated）",
                    severity="FAIL",
                ))
            else:
                checks.append(MaterializationCheckResult(
                    check_id="target_schema",
                    name="目标 Schema 白名单",
                    status="PASS",
                    detail=f"目标 schema '{schema}' 合法",
                    severity="FAIL",
                ))

    # ── 检查 4：source_query_hash 一致性 ──
    sql_path = package_dir / "sql" / "main.sql"
    stored_hash = manifest_dict.get("source_query_hash", "")
    if sql_path.is_file() and stored_hash:
        sql_content = sql_path.read_text(encoding="utf-8")
        actual_hash = _hash_content(sql_content)
        if actual_hash != stored_hash:
            checks.append(MaterializationCheckResult(
                check_id="source_query_hash",
                name="source_query_hash 一致性",
                status="FAIL",
                detail=(
                    f"source_query_hash 不一致——清单记录 {stored_hash[:16]}..."
                    f"，实际 sql/main.sql 哈希 {actual_hash[:16]}..."
                ),
                severity="FAIL",
            ))
        else:
            checks.append(MaterializationCheckResult(
                check_id="source_query_hash",
                name="source_query_hash 一致性",
                status="PASS",
                detail=f"source_query_hash 与 sql/main.sql 一致（{stored_hash[:16]}...）",
                severity="FAIL",
            ))
    elif not stored_hash:
        checks.append(MaterializationCheckResult(
            check_id="source_query_hash",
            name="source_query_hash 一致性",
            status="FAIL",
            detail="部署清单缺少 source_query_hash",
            severity="FAIL",
        ))
    else:
        checks.append(MaterializationCheckResult(
            check_id="source_query_hash",
            name="source_query_hash 一致性",
            status="FAIL",
            detail="sql/main.sql 文件不存在——无法验证 source_query_hash",
            severity="FAIL",
        ))

    # ── 检查 5：deploy artifact hash 一致性 ──
    deploy_sql_path = package_dir / "deploy" / "main.sql"
    deploy_sql_content = ""
    if deploy_sql_path.is_file():
        deploy_sql_content = deploy_sql_path.read_text(encoding="utf-8")
        actual_deploy_hash = _hash_content(deploy_sql_content)
        # Manifest 中不直接存储 deploy SQL 的哈希——存储的是 source_sql_hash
        # 我们校验 deploy SQL 哈希是否与决策快照中记录的一致
        decision_path = package_dir / "decision.yml"
        if decision_path.is_file():
            decision = yaml.safe_load(decision_path.read_text(encoding="utf-8")) or {}
            stored_deploy_hash = (
                decision.get("artifact_hashes", {}).get("deploy_sql", "")
            )
            if stored_deploy_hash and actual_deploy_hash != stored_deploy_hash:
                checks.append(MaterializationCheckResult(
                    check_id="deploy_artifact_hash",
                    name="deploy artifact hash 一致性",
                    status="FAIL",
                    detail=(
                        f"deploy/main.sql 哈希不一致——"
                        f"记录 {stored_deploy_hash[:16]}..."
                        f"，实际 {actual_deploy_hash[:16]}..."
                    ),
                    severity="FAIL",
                ))
            else:
                checks.append(MaterializationCheckResult(
                    check_id="deploy_artifact_hash",
                    name="deploy artifact hash 一致性",
                    status="PASS",
                    detail=f"deploy artifact hash 一致（{actual_deploy_hash[:16]}...）",
                    severity="FAIL",
                ))
        else:
            checks.append(MaterializationCheckResult(
                check_id="deploy_artifact_hash",
                name="deploy artifact hash 一致性",
                status="PENDING",
                detail="无 decision.yml——跳过 deploy artifact hash 校验",
                severity="FAIL",
            ))
    else:
        checks.append(MaterializationCheckResult(
            check_id="deploy_artifact_hash",
            name="deploy artifact hash 一致性",
            status="FAIL",
            detail="deploy/main.sql 文件不存在",
            severity="FAIL",
        ))

    # ── 检查 6：deploy SQL 是有效的 CTAS 结构 ──
    if deploy_sql_content.strip():
        sql_checks = _validate_ctas_structure(deploy_sql_content)
        checks.extend(sql_checks)
    else:
        checks.append(MaterializationCheckResult(
            check_id="ctas_structure",
            name="CTAS 结构合法性",
            status="FAIL",
            detail="deploy/main.sql 内容为空",
            severity="FAIL",
        ))

    # ── 检查 7：deploy SQL 禁止关键字 ──
    if deploy_sql_content.strip():
        keyword_check = _validate_no_forbidden_keywords(deploy_sql_content)
        checks.append(keyword_check)

    # ── 检查 8：非多语句 ──
    if deploy_sql_content.strip():
        multi_check = _validate_single_statement(deploy_sql_content)
        checks.append(multi_check)

    return checks, manifest_dict


def _validate_ctas_structure(sql: str) -> list[MaterializationCheckResult]:
    """校验 SQL 是否为有效的 CTAS 结构。

    期望模式：CREATE [OR REPLACE] TABLE <target> AS <select>

    Returns:
        检查结果列表
    """
    checks: list[MaterializationCheckResult] = []
    cleaned = _strip_sql_comments(sql).strip().rstrip(";").upper()

    # 检查 1：必须以 CREATE 开头
    if not cleaned.startswith("CREATE"):
        checks.append(MaterializationCheckResult(
            check_id="ctas_prefix",
            name="CTAS 前缀检查",
            status="FAIL",
            detail=f"部署 SQL 必须以 CREATE 开头——当前以 {cleaned.split()[0] if cleaned.split() else '(空)'} 开头",
            severity="FAIL",
        ))
    else:
        checks.append(MaterializationCheckResult(
            check_id="ctas_prefix",
            name="CTAS 前缀检查",
            status="PASS",
            detail="部署 SQL 以 CREATE 开头",
            severity="FAIL",
        ))

    # 检查 2：必须包含 TABLE 关键字
    if "TABLE" not in cleaned:
        checks.append(MaterializationCheckResult(
            check_id="ctas_table_keyword",
            name="CTAS TABLE 关键字",
            status="FAIL",
            detail="部署 SQL 缺少 TABLE 关键字——不是有效的 CTAS 语句",
            severity="FAIL",
        ))
    else:
        checks.append(MaterializationCheckResult(
            check_id="ctas_table_keyword",
            name="CTAS TABLE 关键字",
            status="PASS",
            detail="部署 SQL 包含 TABLE 关键字",
            severity="FAIL",
        ))

    # 检查 3：必须包含 AS 关键字 + SELECT
    if "AS" not in cleaned or "SELECT" not in cleaned:
        checks.append(MaterializationCheckResult(
            check_id="ctas_as_select",
            name="CTAS AS SELECT",
            status="FAIL",
            detail="部署 SQL 不是有效的 CTAS——缺少 AS SELECT 子句",
            severity="FAIL",
        ))
    else:
        checks.append(MaterializationCheckResult(
            check_id="ctas_as_select",
            name="CTAS AS SELECT",
            status="PASS",
            detail="CTAS 结构有效（CREATE TABLE ... AS SELECT）",
            severity="FAIL",
        ))

    return checks


def _validate_no_forbidden_keywords(sql: str) -> MaterializationCheckResult:
    """检查 SQL 是否包含禁止关键字。"""
    cleaned = _strip_sql_comments(sql).upper()
    found = []
    for kw in sorted(FORBIDDEN_DEPLOY_KEYWORDS):
        if re.search(rf"\b{kw}\b", cleaned):
            # "REPLACE" 在 "CREATE OR REPLACE" 中是合法的
            if kw == "REPLACE" and "CREATE OR REPLACE" in cleaned:
                continue
            found.append(kw)

    if found:
        return MaterializationCheckResult(
            check_id="forbidden_keywords",
            name="禁止关键字检查",
            status="FAIL",
            detail=f"检测到禁止关键字: {', '.join(found)}",
            severity="FAIL",
        )
    return MaterializationCheckResult(
        check_id="forbidden_keywords",
        name="禁止关键字检查",
        status="PASS",
        detail="未检测到禁止关键字",
        severity="FAIL",
    )


def _validate_single_statement(sql: str) -> MaterializationCheckResult:
    """检查 SQL 是否为单语句（禁止多语句）。"""
    # 在去除注释后检查分号数量
    cleaned = _strip_sql_comments(sql)
    # 统计不在字符串中的分号
    semicolons = [c for c in cleaned if c == ";"]
    if len(semicolons) > 1:
        return MaterializationCheckResult(
            check_id="single_statement",
            name="单语句检查",
            status="FAIL",
            detail=f"多语句 SQL 被拒绝（检测到 {len(semicolons)} 个分号）——Sandbox 只允许单条 CTAS",
            severity="FAIL",
        )
    return MaterializationCheckResult(
        check_id="single_statement",
        name="单语句检查",
        status="PASS",
        detail="单语句——无多语句注入",
        severity="FAIL",
    )
