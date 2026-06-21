"""
物化验证编排引擎——M5b-1。

串联部署产物静态校验、CTAS Sandbox 执行和结果验证。
写入 machine-readable 报告（materialization_verification.yml + .md），
不修改人工批准状态。

职责：
  - 编排部署静态检查（materialization_validator）
  - 调用一次性 DuckDB CTAS Sandbox（duckdb_ctas_executor）
  - 执行幂等性检查
  - 写入物化验证报告（.yml + .md）
  - 更新 deployment_manifest.yml 的 materialization_status 字段
  - 不修改 decision.yml 的人工批准状态
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from src.ir.types import MaterializationCheckResult, MaterializationResult
from src.sandbox.duckdb_ctas_executor import (
    execute_ctas_in_sandbox,
    check_idempotency,
)
from src.verify.materialization_validator import (
    validate_materialization_static,
)


def _iso_now() -> str:
    """返回当前 UTC ISO8601 时间戳。"""
    return datetime.now(timezone.utc).isoformat()


def _generate_verification_id() -> str:
    """生成本次物化验证的唯一标识。"""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short = secrets.token_hex(4)
    return f"mat_{ts}_{short}"


def _map_overall_to_materialization_status(result: MaterializationResult) -> str:
    """将 overall_status 映射为 MaterializationStatus 枚举值。

    映射规则（fail-closed）：
      - cleanup_status=FAIL → CLEANUP_FAILED（最高优先级——系统处于不干净状态）
      - overall_status=PASS → MATERIALIZATION_VALIDATED（唯一通过状态）
      - overall_status=FAIL → FAILED
      - overall_status=WARN → FAILED（WARN 绝对不能映射为 MATERIALIZATION_VALIDATED）
      - overall_status=PENDING → PENDING
      - 其他未知状态 → FAILED（安全侧——宁可误拒也不漏过）
    """
    if result.cleanup_status == "FAIL":
        return "CLEANUP_FAILED"
    status = result.overall_status
    if status == "PASS":
        return "MATERIALIZATION_VALIDATED"
    elif status in ("FAIL", "WARN"):
        return "FAILED"
    elif status == "PENDING":
        return "PENDING"
    else:
        # 未知状态——fail-closed：从不假设通过
        return "FAILED"


def _finalize_and_persist_materialization(
    package_dir: Path,
    result: MaterializationResult,
    manifest: dict[str, Any],
) -> MaterializationResult:
    """统一收尾路径——所有验证出口必须经过此函数。

    职责（严格按顺序执行）：
      1. 聚合最终状态（_finalize_status）
      2. 设置 generated_at / finished_at 时间戳
      3. 原子写入 YAML 报告（tmp + replace）
      4. 原子写入 Markdown 报告（tmp + replace）
      5. 更新 Manifest materialization_status
      6. 必要时使 RELEASE_APPROVED 失效（写审计日志）
      7. 同步制品哈希到 decision.yml

    报告或 Manifest 持久化失败时：
      - 记录到 result.failures
      - overall_status 变为 FAIL
      - 不抛出异常——返回带失败信息的 result

    Args:
        package_dir: Review Package 目录路径
        result: 待持久化的验证结果
        manifest: deployment_manifest.yml 解析后的 dict

    Returns:
        最终 MaterializationResult（可能因持久化失败而改变状态）
    """
    # ── 1. 聚合最终状态 ──
    result = _finalize_status(result)

    # ── 2. 设置时间戳 ──
    now = _iso_now()
    result.generated_at = now
    if not result.finished_at:
        result.finished_at = now

    # ── 3. 原子写入 YAML 报告 ──
    reports_dir = package_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    yml_path = reports_dir / "materialization_verification.yml"
    try:
        yml_content = yaml.safe_dump(
            result.to_dict(), allow_unicode=True, sort_keys=False
        )
        yml_tmp = yml_path.with_suffix(".tmp")
        yml_tmp.write_text(yml_content, encoding="utf-8")
        yml_tmp.replace(yml_path)
    except Exception as e:
        result.overall_status = "FAIL"
        result.failures.append(f"无法写入 YAML 报告: {e}")

    # ── 4. 原子写入 Markdown 报告 ──
    md_path = reports_dir / "materialization_verification.md"
    try:
        md_content = _build_materialization_report_md(result)
        md_tmp = md_path.with_suffix(".tmp")
        md_tmp.write_text(md_content, encoding="utf-8")
        md_tmp.replace(md_path)
    except Exception as e:
        result.overall_status = "FAIL"
        result.failures.append(f"无法写入 Markdown 报告: {e}")

    # ── 5. 更新 Manifest materialization_status ──
    manifest_path = package_dir / "deployment_manifest.yml"
    new_mat_status = _map_overall_to_materialization_status(result)

    if manifest_path.is_file():
        try:
            manifest_data = (
                yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
            )
            manifest_data["materialization_status"] = new_mat_status
            tmp_path = manifest_path.with_suffix(".tmp")
            tmp_path.write_text(
                yaml.safe_dump(manifest_data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            tmp_path.replace(manifest_path)
        except Exception as e:
            result.overall_status = "FAIL"
            result.failures.append(f"Manifest 更新失败: {e}")
    else:
        # Manifest 文件缺失——防御性处理
        result.overall_status = "FAIL"
        result.failures.append(
            "deployment_manifest.yml 缺失——无法更新 materialization_status"
        )

    # ── 6. 必要时使 RELEASE_APPROVED 失效 ──
    # 当前验证非 PASS 时，如果存在 RELEASE_APPROVED，必须将其失效为 SUPERSEDED
    if result.overall_status != "PASS":
        try:
            from src.agent.decision_manager import invalidate_release_approval
            superseded = invalidate_release_approval(
                package_dir,
                f"物化验证未通过（overall_status={result.overall_status}，"
                f"verification_id={result.verification_id}）——"
                f"旧 RELEASE_APPROVED 不再有效",
            )
            if superseded:
                result.warnings.append(
                    "已将旧的 RELEASE_APPROVED 失效为 SUPERSEDED——"
                    "请重新运行物化验证并通过后再次审批。"
                )
        except Exception:
            # 审批失效失败不阻塞验证结果——但记录警告
            result.warnings.append(
                "检查 RELEASE_APPROVED 失效时发生异常——请手动确认发布审批状态"
            )

    # ── 7. 同步制品哈希到 decision.yml ──
    decision_path = package_dir / "decision.yml"
    if decision_path.is_file():
        try:
            from src.agent.decision_manager import (
                compute_artifact_hashes,
                update_artifact_hashes_in_decision,
            )
            hashes = compute_artifact_hashes(package_dir)
            update_artifact_hashes_in_decision(package_dir, hashes)
        except Exception:
            # 哈希更新失败不影响物化验证结果
            pass

    return result


# ═══════════════════════════════════════════════════════════════
# 编排出入口
# ═══════════════════════════════════════════════════════════════


def verify_materialization(
    package_dir: Path,
    sample_db_path: Optional[str] = None,
    sample_data_rows: Optional[list[tuple]] = None,
    sample_data_columns: Optional[list[str]] = None,
    sample_data_types: Optional[list[str]] = None,
    timeout_seconds: int = 60,
) -> MaterializationResult:
    """执行完整的物化验证流程。

    所有出口均通过 _finalize_and_persist_materialization() 收尾，
    确保每次验证都写入最新报告、更新 Manifest 状态、必要时使旧审批失效。

    流程：
      1. 静态校验部署产物
      2. 加载 sample 数据（从 DB 或直接传入的行数据）
      3. 在一次性 DuckDB Sandbox 中执行 CTAS
      4. 执行幂等性检查
      5. 统一收尾——聚合、持久化、审批失效

    Args:
        package_dir: Review Package 目录路径
        sample_db_path: 可选的 sample DuckDB 路径（只读打开）
        sample_data_rows: 直接传入的 sample 数据行（优先级高于 sample_db_path）
        sample_data_columns: sample 数据列名
        sample_data_types: sample 数据列类型
        timeout_seconds: CTAS 执行超时

    Returns:
        MaterializationResult——包含所有验证结果
    """
    verification_id = _generate_verification_id()

    # ── 步骤 1：静态校验 ──
    static_checks, manifest_dict = validate_materialization_static(package_dir)
    static_failures = [c for c in static_checks if c.status == "FAIL"]

    if static_failures:
        # 静态校验失败——不执行 Sandbox，通过统一收尾路径返回
        result = MaterializationResult(
            verification_id=verification_id,
            request_id=manifest_dict.get("request_id", ""),
            overall_status="FAIL",
            static_validation_status="FAIL",
            checks=static_checks,
            failures=[
                f"[静态校验] {c.name}: {c.detail}" for c in static_failures
            ],
            human_review_required=True,
        )
        return _finalize_and_persist_materialization(
            package_dir, result, manifest_dict,
        )

    static_passed = all(
        c.status in {"PASS", "PENDING"} for c in static_checks
    )

    # ── 步骤 2：读取部署 SQL ──
    deploy_sql_path = package_dir / "deploy" / "main.sql"
    if not deploy_sql_path.is_file():
        result = MaterializationResult(
            verification_id=verification_id,
            request_id=manifest_dict.get("request_id", ""),
            overall_status="FAIL",
            static_validation_status="PASS" if static_passed else "FAIL",
            checks=static_checks,
            failures=["deploy/main.sql 不存在——无法执行物化验证"],
            human_review_required=True,
        )
        return _finalize_and_persist_materialization(
            package_dir, result, manifest_dict,
        )
    deploy_sql = deploy_sql_path.read_text(encoding="utf-8")

    # ── 步骤 3：加载 sample 数据 ──
    if sample_data_rows is None and sample_data_columns is None:
        # 尝试从 sample_db_path 加载
        if sample_db_path:
            try:
                rows, cols, types = _load_sample_from_db(
                    sample_db_path, manifest_dict,
                )
                sample_data_rows = rows
                sample_data_columns = cols
                sample_data_types = types
            except Exception as e:
                # sample DB 加载异常——通过统一收尾路径返回
                result = MaterializationResult(
                    verification_id=verification_id,
                    request_id=manifest_dict.get("request_id", ""),
                    overall_status="FAIL",
                    checks=static_checks,
                    failures=[f"sample 数据库加载异常: {e}"],
                    human_review_required=True,
                )
                return _finalize_and_persist_materialization(
                    package_dir, result, manifest_dict,
                )
        else:
            result = MaterializationResult(
                verification_id=verification_id,
                request_id=manifest_dict.get("request_id", ""),
                overall_status="FAIL",
                checks=static_checks,
                failures=[
                    "未提供 sample 数据——需要 --sample-db 或直接传入数据"
                ],
                human_review_required=True,
            )
            return _finalize_and_persist_materialization(
                package_dir, result, manifest_dict,
            )

    if not sample_data_rows or not sample_data_columns:
        result = MaterializationResult(
            verification_id=verification_id,
            request_id=manifest_dict.get("request_id", ""),
            overall_status="FAIL",
            checks=static_checks,
            failures=["sample 数据为空——无法执行物化验证"],
            human_review_required=True,
        )
        return _finalize_and_persist_materialization(
            package_dir, result, manifest_dict,
        )

    # ── 步骤 4：执行一次性 Sandbox CTAS ──
    result = execute_ctas_in_sandbox(
        deploy_sql=deploy_sql,
        manifest=manifest_dict,
        sample_data_rows=sample_data_rows,
        sample_data_columns=sample_data_columns,
        sample_data_types=sample_data_types,
        source_query_hash=manifest_dict.get("source_query_hash", ""),
        timeout_seconds=timeout_seconds,
    )
    result.verification_id = verification_id

    # ── 合并静态检查结果 ──
    result.checks = static_checks + result.checks
    if static_passed:
        result.static_validation_status = "PASS"
    else:
        result.static_validation_status = "WARN"
        result.warnings.extend([
            f"[静态校验] {c.name}: {c.detail}"
            for c in static_checks if c.status not in {"PASS", "PENDING"}
        ])

    # ── 同步 hash 状态字段到顶层（修复 M5b-1a #2）──
    for check in static_checks:
        if check.check_id == "source_query_hash":
            result.source_query_hash_status = check.status
        elif check.check_id == "deploy_artifact_hash":
            result.deploy_artifact_hash_status = check.status

    # ── 步骤 5：幂等性检查 ──
    if result.execution_status == "PASS":
        idempotency = check_idempotency(
            deploy_sql=deploy_sql,
            manifest=manifest_dict,
            sample_data_rows=sample_data_rows,
            sample_data_columns=sample_data_columns,
            sample_data_types=sample_data_types,
            timeout_seconds=timeout_seconds,
        )
        result.idempotency_status = idempotency["status"]
        result.checks.append(MaterializationCheckResult(
            check_id="idempotency",
            name="幂等性检查",
            status=idempotency["status"],
            detail=idempotency["detail"],
            severity="FAIL" if idempotency["status"] == "FAIL" else "WARN",
        ))
        if idempotency["status"] != "PASS":
            result.warnings.append(idempotency["detail"])

    # ── 统一收尾：聚合、持久化、审批失效 ──
    return _finalize_and_persist_materialization(
        package_dir, result, manifest_dict,
    )


# ═══════════════════════════════════════════════════════════════
# 内部辅助函数
# ═══════════════════════════════════════════════════════════════


def _load_sample_from_db(
    db_path: str,
    manifest: dict[str, Any],
) -> tuple[list[tuple], list[str], list[str]]:
    """从只读 sample 数据库加载输入数据。

    使用 read_only=True 打开连接，只读取 Manifest/lineage 声明的表。
    限制行数，避免加载全部数据。

    Args:
        db_path: sample DuckDB 数据库路径
        manifest: deployment_manifest.yml 解析后的 dict

    Returns:
        (rows, columns, types)——数据行、列名、列类型
    """
    import duckdb as ddb

    conn = ddb.connect(db_path, read_only=True)
    try:
        # 查找数据源表——优先 gold schema 下的表
        tables_result = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='gold' ORDER BY table_name"
        ).fetchall()

        if not tables_result:
            # 尝试任何 schema
            tables_result = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema NOT IN ('information_schema', 'pg_catalog') "
                "ORDER BY table_name"
            ).fetchall()

        if not tables_result:
            return [], [], []

        source_table = f"gold.{tables_result[0][0]}" if tables_result else ""

        # 读取 schema
        desc = conn.execute(f"DESCRIBE {source_table}").fetchall()
        columns = [row[0] for row in desc]
        types = [row[1] for row in desc]

        # 读取数据（限制 1000 行）
        rows_result = conn.execute(
            f"SELECT * FROM {source_table} LIMIT 1000"
        ).fetchall()
        rows = [tuple(row) for row in rows_result]

        return rows, columns, types
    finally:
        conn.close()


def _finalize_status(result: MaterializationResult) -> MaterializationResult:
    """最终聚合所有检查项状态。

    M5b-2 P0 修复：区分必需检查和可选检查。
      - 清理失败 → FAIL（最高优先级）
      - 任一必需检查 FAIL → FAIL
      - 可选检查实际执行后 FAIL → FAIL（不得被忽略）
      - 任一必需检查 WARN → WARN
      - 任一必需检查 PENDING/SKIPPED → PENDING
      - 所有必需检查 PASS，可选 NOT_APPLICABLE 不阻止 → PASS
    """
    if result.cleanup_status == "FAIL":
        result.overall_status = "FAIL"
        return result

    # 区分必需和可选检查
    required_statuses = [
        c.status for c in result.checks
        if getattr(c, "required", True)
    ]
    # 可选检查中实际执行过的（排除 NOT_APPLICABLE）
    executed_optional = [
        c.status for c in result.checks
        if not getattr(c, "required", True) and c.status != "NOT_APPLICABLE"
    ]

    # 聚合：必需检查 + 实际执行的可选检查
    actionable = required_statuses + executed_optional

    if "FAIL" in actionable or result.failures:
        result.overall_status = "FAIL"
    elif "WARN" in actionable or result.warnings:
        result.overall_status = "WARN"
    elif "PENDING" in required_statuses or "SKIPPED" in required_statuses:
        result.overall_status = "PENDING"
    elif all(s == "PASS" for s in required_statuses):
        result.overall_status = "PASS"
    else:
        result.overall_status = "PENDING"

    return result


def _build_materialization_report_md(result: MaterializationResult) -> str:
    """生成人类可读的物化验证报告（Markdown）。"""
    lines = [
        "# 物化验证报告 (M5b-1)",
        "",
        f"- **verification_id**: {result.verification_id}",
        f"- **request_id**: {result.request_id}",
        f"- **sandbox_id**: {result.sandbox_id}",
        f"- **引擎**: {result.engine}",
        f"- **操作**: {result.operation}",
        f"- **声明目标**: {result.declared_target}",
        f"- **Sandbox 目标**: {result.sandbox_target}",
        f"- **开始时间**: {result.started_at}",
        f"- **结束时间**: {result.finished_at}",
        f"- **总体状态**: {result.overall_status}",
        f"- **清理状态**: {result.cleanup_status}",
        "",
        "## 状态摘要",
        "",
        f"| 维度 | 状态 |",
        f"|------|------|",
        f"| 静态校验 | {result.static_validation_status} |",
        f"| source_query_hash | {result.source_query_hash_status} |",
        f"| deploy artifact hash | {result.deploy_artifact_hash_status} |",
        f"| CTAS 执行 | {result.execution_status} |",
        f"| 输出 Schema | {result.output_schema_status} |",
        f"| 输出行数 | {result.row_count_status} |",
        f"| 空值率 | {result.null_check_status} |",
        f"| 唯一键 | {result.uniqueness_status} |",
        f"| 幂等性 | {result.idempotency_status} |",
        f"| 清理 | {result.cleanup_status} |",
        "",
        f"- 输出行数: {result.output_row_count}",
        f"- 输出列: {', '.join(result.output_columns) if result.output_columns else 'N/A'}",
        "",
    ]

    if result.null_rates:
        lines.append("## 空值率")
        lines.append("")
        lines.append("| 列 | 空值率 |")
        lines.append("|------|------|")
        for col, rate in result.null_rates.items():
            lines.append(f"| {col} | {rate:.1%} |")
        lines.append("")

    if result.numeric_sums:
        lines.append("## 数值汇总")
        lines.append("")
        lines.append("| 列 | 合计 |")
        lines.append("|------|------|")
        for col, s in result.numeric_sums.items():
            lines.append(f"| {col} | {s} |")
        lines.append("")

    lines.extend([
        "## 检查明细",
        "",
        "| # | 检查项 | 必需 | 状态 | 详情 |",
        "|------|------|------|------|------|",
    ])
    for i, check in enumerate(result.checks):
        status_icon = {
            "PASS": "✅", "FAIL": "❌", "WARN": "⚠️",
            "PENDING": "⏳", "SKIPPED": "⏭️",
            "NOT_APPLICABLE": "➖",
        }.get(check.status, "❓")
        required_label = "是" if getattr(check, "required", True) else "否"
        lines.append(
            f"| {i + 1} | {check.name} | {required_label} | "
            f"{status_icon} {check.status} | {check.detail} |"
        )
    lines.append("")

    # 未提供的验证背书
    not_applicable_checks = [
        c for c in result.checks
        if c.status == "NOT_APPLICABLE"
    ]
    if not_applicable_checks:
        lines.extend([
            "## ⚠️ 当前验证未提供以下背书",
            "",
        ])
        for c in not_applicable_checks:
            lines.append(f"- **{c.name}**：{c.detail}")
        lines.append("")
        lines.append(
            "上述项不阻止物化验证通过，但表示当前验证范围有限——"
            "人审时需根据业务需求判断是否可接受。"
        )
        lines.append("")

    if result.warnings:
        lines.extend([
            "## ⚠️ 警告",
            "",
        ])
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    if result.failures:
        lines.extend([
            "## ❌ 失败",
            "",
        ])
        for f in result.failures:
            lines.append(f"- {f}")
        lines.append("")

    lines.extend([
        "## 人审提示",
        "",
        "- **本报告不代表可以上线。** 物化验证仅是 RELEASE_APPROVED 的必要前提之一。",
        "- 物化验证只覆盖 CTAS 写入行为——不覆盖 INSERT/UPDATE/DELETE/分区/MERGE。",
        "- 样本数据不代表生产全量数据——全量行为需在预发布环境独立验证。",
        "- **MATERIALIZATION_VALIDATED ≠ RELEASE_APPROVED**——最终发布审批仅人可设置。",
        "- Spark Writer 在本阶段未被验证——交叉验证状态会在 M5b-3 补充。",
        f"- **人审前请确认**：本报告的 overall_status 为 **{result.overall_status}**。",
        "",
    ])

    return "\n".join(lines)
