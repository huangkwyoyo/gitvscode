"""
v2 Verification Engine 编排入口。

输入 M2 生成的 Review Package，执行静态检查、SQL sample run、
Spark sample run 或跳过、SQL vs Spark 交叉验证，并写回审查报告。

M4a：新增 verification_summary.yml——结构化验证摘要。
      绝不修改 decision.yml.current_state（SUPERSEDED 为 M4b+）。
M4b：实现 SUPERSEDED 自动转换——重新验证且旧状态为 APPROVED 时自动过渡。
      新增 artifact 完整性检查、verification_id。
M4c：SUPERSEDED 后自动传播至下游 APPROVED package + 同步注册表。
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.ir.types import (
    AssuranceLevel,
    CrossValidateStatus,
    DecisionStatus,
    SQLResult,
    ValidationReport,
    ValidationStatus,
    VerificationCoverage,
)
from src.sandbox.executor import execute_sql_sample
from src.sandbox.spark_executor import execute_spark_dsl
from src.verify.checker import Validator
from src.verify.cross_validation import compare_results

from .decision_manager import (
    check_artifact_integrity,
    compute_artifact_hashes,
    read_decision,
    transition_state,
    update_artifact_hashes_in_decision,
)
from .package_registry import (
    propagate_superseded,
    update_registry_state,
)


@dataclass
class VerificationEngineResult:
    """M3 验证引擎的结构化结果。"""

    package_path: str
    verification_report_path: str
    cross_validation_report_path: str
    overall_status: str
    sql_static_status: str
    sql_sample_status: str
    spark_static_status: str
    spark_sample_status: str
    cross_validation_status: str
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def verify_review_package(
    package_path: str | Path,
    conn: Any = None,
    spark_session: Any = None,
    no_sql_run: bool = False,
    limit: int = 1000,
    timeout_seconds: int = 30,
) -> VerificationEngineResult:
    """验证 Review Package，并写入 verification/cross_validation 报告。"""
    package_dir = Path(package_path)
    sql_path = package_dir / "sql" / "main.sql"
    spark_path = package_dir / "spark" / "main.py"
    lineage_path = package_dir / "lineage" / "source_refs.yml"
    decision_path = package_dir / "decision.md"
    decision_yml_path = package_dir / "decision.yml"
    decision_log_path = package_dir / "decision_log.yml"
    verification_path = package_dir / "reports" / "verification.md"
    cross_path = package_dir / "reports" / "cross_validation.md"

    _require_file(sql_path)
    _require_file(spark_path)
    _require_file(lineage_path)
    _require_file(decision_path)
    _require_file(decision_yml_path)
    _require_file(decision_log_path)

    sql = sql_path.read_text(encoding="utf-8")
    spark_code = spark_path.read_text(encoding="utf-8")
    lineage = yaml.safe_load(lineage_path.read_text(encoding="utf-8")) or {}
    source_table = _first_source_table(lineage)

    # M4b：读取 decision.yml——获取当前状态和 artifact 哈希
    decision = read_decision(package_dir)
    decision_state_before = decision.get("current_state", "PENDING_REVIEW")
    stored_hashes = decision.get("artifact_hashes", {})

    # M4b：生成本次验证的唯一标识
    now_iso = datetime.now(timezone.utc).isoformat()
    short_id = secrets.token_hex(4)
    verification_id = (
        f"verify_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{short_id}"
    )

    # M4b：artifact 完整性检查
    integrity_warnings = check_artifact_integrity(package_dir, stored_hashes)

    validator = Validator()
    static_report = validator.validate_static(sql=sql, spark_code=spark_code, lineage=lineage)
    sql_static_status = _sql_static_status(static_report)
    spark_static_status = _spark_static_status(static_report)

    # M5：部署产物静态检查
    deploy_sql = ""
    deploy_spark_code = ""
    deploy_manifest_dict: dict[str, Any] = {}
    deploy_static_status = "PENDING"
    deploy_static_report: ValidationReport | None = None

    deploy_sql_path = package_dir / "deploy" / "main.sql"
    deploy_spark_path = package_dir / "deploy" / "main.py"
    deploy_manifest_path = package_dir / "deployment_manifest.yml"

    if deploy_sql_path.is_file():
        deploy_sql = deploy_sql_path.read_text(encoding="utf-8")
    if deploy_spark_path.is_file():
        deploy_spark_code = deploy_spark_path.read_text(encoding="utf-8")
    if deploy_manifest_path.is_file():
        deploy_manifest_dict = (
            yaml.safe_load(deploy_manifest_path.read_text(encoding="utf-8")) or {}
        )

    has_deploy_artifacts = deploy_sql_path.is_file() and deploy_manifest_path.is_file()
    if has_deploy_artifacts:
        deploy_static_report = validator.validate_deploy_static(
            deploy_sql=deploy_sql,
            deploy_spark=deploy_spark_code,
            deployment_manifest=deploy_manifest_dict,
            verified_sql=sql,
            verified_spark=spark_code,
        )
        deploy_static_status = _status_from_checks(deploy_static_report.checks)
    else:
        deploy_static_status = "SKIPPED"

    sql_result: SQLResult | None = None
    sql_sample_status = "PENDING"
    if sql_static_status == "FAIL":
        sql_sample_status = "SKIPPED"
    elif no_sql_run:
        sql_sample_status = "SKIPPED"
    elif conn is None:
        sql_sample_status = "SKIPPED"
    else:
        sql_result = execute_sql_sample(
            conn=conn,
            sql=sql,
            limit=limit,
            timeout_seconds=timeout_seconds,
            source_table=source_table,
        )
        sql_sample_status = "FAIL" if sql_result.error else "PASS"

    spark_result: SQLResult | None = None
    spark_sample_status = "PENDING"
    if spark_static_status == "FAIL":
        spark_sample_status = "SKIPPED"
    else:
        spark_result = execute_spark_dsl(
            code=spark_code,
            spark_session=spark_session,
            timeout_seconds=timeout_seconds,
            source_table=source_table,
        )
        spark_sample_status = _spark_result_status(spark_result)

    if sql_sample_status != "PASS":
        cross_result = compare_results(sql_result, spark_result if spark_sample_status == "PASS" else None)
    elif spark_sample_status != "PASS":
        cross_result = compare_results(sql_result, None)
    else:
        cross_result = compare_results(sql_result, spark_result)
    cross_status = _cross_status(cross_result.status)

    warnings, failures = _collect_findings(
        static_report=static_report,
        sql_result=sql_result,
        spark_result=spark_result,
        sql_sample_status=sql_sample_status,
        spark_sample_status=spark_sample_status,
        cross_status=cross_status,
        cross_detail=cross_result.detail,
    )

    # M5：收集部署检查发现
    deploy_warnings: list[str] = []
    deploy_failures: list[str] = []
    if deploy_static_report is not None:
        for check in deploy_static_report.checks:
            if check.status == ValidationStatus.FAILED:
                deploy_failures.append(f"[部署] {check.name}: {check.detail}")
            elif check.status == ValidationStatus.WARN:
                deploy_warnings.append(f"[部署] {check.name}: {check.detail}")

    warnings.extend(deploy_warnings)
    failures.extend(deploy_failures)

    # M4b：合并 artifact 完整性警告
    warnings.extend(integrity_warnings)

    overall_status = _overall_status(
        sql_static_status=sql_static_status,
        sql_sample_status=sql_sample_status,
        spark_static_status=spark_static_status,
        spark_sample_status=spark_sample_status,
        cross_status=cross_status,
        deploy_static_status=deploy_static_status,
        warnings=warnings,
        failures=failures,
    )

    # M4b：SUPERSEDED 自动转换逻辑
    # 仅在旧状态为 APPROVED 且验证实际执行（PASS 或 FAIL）时触发
    # SKIPPED/PENDING 不触发——环境抖动不应导致批准失效
    decision_state_after = decision_state_before
    if (
        decision_state_before == "APPROVED"
        and overall_status in {"PASS", "FAIL"}
    ):
        try:
            transition_state(
                package_dir,
                to_state="SUPERSEDED",
                changed_by="agent",
                reason=(
                    f"重新验证（{verification_id}）检测到旧批准已过期，"
                    f"overall_status={overall_status}，自动过渡至 SUPERSEDED"
                ),
                verification_id=verification_id,
                actor_id="agent",
            )
            decision_state_after = "SUPERSEDED"
            warnings.append(
                f"M4b SUPERSEDED：旧 APPROVED 已自动过渡至 SUPERSEDED"
                f"（verification_id={verification_id}，overall_status={overall_status}）"
            )

            # M4c：SUPERSEDED 传播——通知下游 package
            package_id = package_dir.name
            try:
                update_registry_state(package_id, "SUPERSEDED")
                affected = propagate_superseded(
                    package_id=package_id,
                    reason=f"重新验证触发 SUPERSEDED（{overall_status}）",
                    verification_id=verification_id,
                    _transition_fn=transition_state,
                )
                if affected:
                    warnings.append(
                        f"M4c 传播：下游 {len(affected)} 个 package 受影响"
                        f"（{', '.join(affected)}）"
                    )
            except Exception as exc:
                warnings.append(
                    f"M4c SUPERSEDED 传播失败（不阻断验证）: {exc}"
                )
        except ValueError as exc:
            # SUPERSEDED 转换失败不阻断验证流程
            warnings.append(f"M4b SUPERSEDED 转换失败（不阻断验证）: {exc}")

    verification_path.parent.mkdir(parents=True, exist_ok=True)
    verification_path.write_text(
        _build_verification_report(
            package_dir=package_dir,
            static_report=static_report,
            sql_sample_status=sql_sample_status,
            spark_sample_status=spark_sample_status,
            sql_result=sql_result,
            spark_result=spark_result,
            overall_status=overall_status,
            warnings=warnings,
            failures=failures,
            no_sql_run=no_sql_run,
            conn_provided=conn is not None,
            deploy_static_status=deploy_static_status,
            deploy_static_checks=(
                deploy_static_report.checks if deploy_static_report else []
            ),
        ),
        encoding="utf-8",
    )
    cross_path.write_text(
        _build_cross_validation_report(
            sql_result=sql_result,
            spark_result=spark_result,
            cross_status=cross_status,
            detail=cross_result.detail,
            value_diffs=cross_result.value_diffs,
        ),
        encoding="utf-8",
    )

    # M4b：写入结构化验证摘要——含 verification_id、完整性快照、状态变更记录
    summary_path = package_dir / "reports" / "verification_summary.yml"
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    # 计算当前 artifact 哈希快照（用于 verification_summary）
    current_hashes = compute_artifact_hashes(package_dir)

    summary_path.write_text(
        yaml.safe_dump(
            _build_verification_summary_yml(
                package_dir=package_dir,
                overall_status=overall_status,
                sql_static_status=sql_static_status,
                sql_sample_status=sql_sample_status,
                spark_static_status=spark_static_status,
                spark_sample_status=spark_sample_status,
                cross_status=cross_status,
                deploy_static_status=deploy_static_status,
                warnings=warnings,
                failures=failures,
                verification_id=verification_id,
                artifact_hashes_verified=current_hashes.to_dict(),
                decision_state_before_verify=decision_state_before,
                decision_state_after_verify=(
                    decision_state_after
                    if decision_state_after != decision_state_before
                    else None
                ),
            ),
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    # M4b：更新 decision.yml 中的 verification_summary 哈希
    new_hashes = compute_artifact_hashes(package_dir)
    update_artifact_hashes_in_decision(package_dir, new_hashes)

    return VerificationEngineResult(
        package_path=str(package_dir.resolve()),
        verification_report_path=str(verification_path.resolve()),
        cross_validation_report_path=str(cross_path.resolve()),
        overall_status=overall_status,
        sql_static_status=sql_static_status,
        sql_sample_status=sql_sample_status,
        spark_static_status=spark_static_status,
        spark_sample_status=spark_sample_status,
        cross_validation_status=cross_status,
        warnings=warnings,
        failures=failures,
    )


def _require_file(path: Path) -> None:
    """确保 Review Package 必备文件存在。"""
    if not path.is_file():
        raise FileNotFoundError(f"Review Package 缺少文件: {path}")


def _build_verification_summary_yml(
    package_dir: Path,
    overall_status: str,
    sql_static_status: str,
    sql_sample_status: str,
    spark_static_status: str,
    spark_sample_status: str,
    cross_status: str,
    warnings: list[str],
    failures: list[str],
    verification_id: str = "",
    artifact_hashes_verified: dict[str, Any] | None = None,
    decision_state_before_verify: str = "",
    decision_state_after_verify: str | None = None,
    deploy_static_status: str = "PENDING",
) -> dict[str, Any]:
    """构造 verification_summary.yml——结构化验证摘要（M4b）。

    M4b 新增：
      - verification_id：本次验证的唯一标识
      - artifact_hashes_verified：验证时的 artifact 哈希快照
      - decision_state_before_verify：验证前决策状态
      - decision_state_after_verify：验证后决策状态（若有变更）
      - stale_risk_note 更新为 M4b 已实现

    Phase 3（漏洞 E/F 修复）新增：
      - verification_coverage：9 维验证覆盖状态
      - assurance_level：当前保证级别（PARTIAL / DUAL_ENGINE_SAMPLE）
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # 构造验证覆盖范围
    coverage = VerificationCoverage(
        sql_static=sql_static_status,
        sql_sample=sql_sample_status,
        spark_static=spark_static_status,
        spark_sample=spark_sample_status,
        cross_validation=cross_status,
    )

    # 计算保证级别：当前始终为 PARTIAL（Spark 不可用）
    # 未来当 sql_sample==PASS 且 spark_sample==PASS 且 cross_status==CONSISTENT 时为 DUAL_ENGINE_SAMPLE
    assurance = AssuranceLevel.PARTIAL
    if (
        sql_sample_status == "PASS"
        and spark_sample_status == "PASS"
        and cross_status == "PASS"  # CONSISTENT → _cross_status → "PASS"
    ):
        assurance = AssuranceLevel.DUAL_ENGINE_SAMPLE

    result: dict[str, Any] = {
        "generated_at": now_iso,
        "verification_id": verification_id,
        "package_path": str(package_dir.resolve()),
        "overall_status": overall_status,
        "assurance_level": assurance.value,
        "verification_coverage": coverage.to_dict(),
        "sql_static_status": sql_static_status,
        "sql_sample_status": sql_sample_status,
        "spark_static_status": spark_static_status,
        "spark_sample_status": spark_sample_status,
        "cross_validation_status": cross_status,
        "deploy_static_status": deploy_static_status,
        "warnings": warnings,
        "failures": failures,
    }

    if artifact_hashes_verified:
        result["artifact_hashes_verified"] = artifact_hashes_verified

    result["decision_state_before_verify"] = decision_state_before_verify
    result["decision_state_after_verify"] = decision_state_after_verify

    # M4b：更新 stale 风险提示——自动 SUPERSEDED 已实现
    if decision_state_after_verify == "SUPERSEDED":
        result["stale_risk_note"] = (
            f"M4b：本次验证前 decision.yml.current_state 为 APPROVED，"
            f"验证 overall_status={overall_status}，已自动过渡至 SUPERSEDED。"
            f"旧批准不再有效——请人审者重新审查本次验证结果并做出新决策。"
        )
    else:
        result["stale_risk_note"] = (
            "M4b：本文件记录了最新验证结果。"
            "若 decision.yml.current_state 为 APPROVED 且本次验证实际执行（PASS/FAIL），"
            "旧批准已自动过渡至 SUPERSEDED。"
            "若本次验证为 SKIPPED/PENDING，旧批准保留不变——人审时需注意。"
        )

    return result


def _first_source_table(lineage: dict[str, Any]) -> str:
    """从 lineage 中提取首个来源表名。"""
    tables = lineage.get("source_tables") or []
    if not tables:
        return ""
    first = tables[0]
    if isinstance(first, dict):
        return str(first.get("name") or "")
    return str(first)


def _sql_static_status(report: ValidationReport) -> str:
    """聚合 SQL 静态检查状态。"""
    sql_checks = [
        check for check in report.checks
        if check.name.startswith("SQL")
    ]
    return _status_from_checks(sql_checks)


def _spark_static_status(report: ValidationReport) -> str:
    """聚合 Spark 静态检查状态。"""
    spark_checks = [
        check for check in report.checks
        if check.name.startswith("Spark")
    ]
    return _status_from_checks(spark_checks)


def _status_from_checks(checks: list) -> str:
    """把 ValidationStatus 转成报告使用的大写状态。"""
    if any(check.status == ValidationStatus.FAILED for check in checks):
        return "FAIL"
    if any(check.status == ValidationStatus.WARN for check in checks):
        return "WARN"
    if any(check.status == ValidationStatus.PENDING for check in checks):
        return "PENDING"
    return "PASS"


def _spark_result_status(result: SQLResult | None) -> str:
    """把 Spark sample run 结果转成 M3 状态。"""
    if result is None:
        return "PENDING"
    if not result.error:
        return "PASS"
    if "SKIPPED" in result.error.upper():
        return "SKIPPED"
    if "PENDING" in result.error.upper():
        return "PENDING"
    return "FAIL"


def _cross_status(status: CrossValidateStatus) -> str:
    """把交叉验证枚举转成报告状态。"""
    if status == CrossValidateStatus.CONSISTENT:
        return "PASS"
    if status == CrossValidateStatus.INCONSISTENT:
        return "WARN"
    if status == CrossValidateStatus.SKIPPED:
        return "SKIPPED"
    return "PENDING"


def _collect_findings(
    static_report: ValidationReport,
    sql_result: SQLResult | None,
    spark_result: SQLResult | None,
    sql_sample_status: str,
    spark_sample_status: str,
    cross_status: str,
    cross_detail: str,
) -> tuple[list[str], list[str]]:
    """汇总 WARN 和 FAIL 明细。"""
    warnings: list[str] = []
    failures: list[str] = []

    for check in static_report.checks:
        if check.status == ValidationStatus.FAILED:
            failures.append(f"{check.name}: {check.detail}")
        elif check.status == ValidationStatus.WARN:
            warnings.append(f"{check.name}: {check.detail}")

    if sql_sample_status == "FAIL" and sql_result and sql_result.error:
        failures.append(f"SQL sample run 失败: {sql_result.error}")
    if sql_sample_status in {"SKIPPED", "PENDING"}:
        warnings.append(f"SQL sample run 状态为 {sql_sample_status}")
    if spark_sample_status in {"SKIPPED", "PENDING"}:
        warnings.append(f"Spark sample run 状态为 {spark_sample_status}")
    if spark_sample_status == "FAIL" and spark_result and spark_result.error:
        failures.append(f"Spark sample run 失败: {spark_result.error}")
    if cross_status in {"WARN", "SKIPPED", "PENDING"}:
        warnings.append(f"交叉验证状态为 {cross_status}: {cross_detail}")

    return warnings, failures


def _overall_status(
    sql_static_status: str,
    sql_sample_status: str,
    spark_static_status: str,
    spark_sample_status: str,
    cross_status: str,
    warnings: list[str],
    failures: list[str],
    deploy_static_status: str = "PENDING",
) -> str:
    """计算总体状态，任何跳过或待定都不能伪装 PASS。"""
    statuses = {
        sql_static_status,
        sql_sample_status,
        spark_static_status,
        spark_sample_status,
        cross_status,
    }
    # M5：部署状态仅在 FAIL/WARN/SKIPPED 时纳入聚合（PASS 保持向后兼容）
    if deploy_static_status in {"FAIL", "WARN", "SKIPPED"}:
        statuses.add(deploy_static_status)
    if failures or "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses or warnings:
        return "WARN"
    if "PENDING" in statuses:
        return "PENDING"
    if "SKIPPED" in statuses:
        return "SKIPPED"
    return "PASS"


def _build_verification_report(
    package_dir: Path,
    static_report: ValidationReport,
    sql_sample_status: str,
    spark_sample_status: str,
    sql_result: SQLResult | None,
    spark_result: SQLResult | None,
    overall_status: str,
    warnings: list[str],
    failures: list[str],
    no_sql_run: bool,
    conn_provided: bool,
    deploy_static_status: str = "PENDING",
    deploy_static_checks: list = None,
) -> str:
    """生成 verification.md——含验证覆盖范围和未验证风险。"""
    sql_static_status = _sql_static_status(static_report)
    spark_static_status = _spark_static_status(static_report)

    # 构造验证覆盖范围
    coverage = VerificationCoverage(
        sql_static=sql_static_status,
        sql_sample=sql_sample_status,
        spark_static=spark_static_status,
        spark_sample=spark_sample_status,
        cross_validation="PENDING",  # 交叉验证状态由 cross_status 单独覆盖
    )

    lines = [
        "# Verification Report",
        "",
        f"Review Package 路径：{package_dir}",
        f"总体状态：{overall_status}",
        "",
        "## 状态摘要",
        "",
        f"- SQL 静态检查状态：{sql_static_status}",
        f"- SQL sample run 状态：{sql_sample_status}",
        f"- Spark 静态检查状态：{spark_static_status}",
        f"- Spark sample run 状态：{spark_sample_status}",
        f"- 部署静态检查状态：{deploy_static_status}",
        "",
        "## 验证覆盖范围",
        "",
        "当前验证能力仅覆盖静态检查和单引擎样本执行。以下维度明确标注为 NOT_COVERED：",
        "",
    ]

    # 已覆盖维度
    for key, val in coverage.all_covered_dimensions.items():
        label = {
            "sql_static": "SQL 静态检查（安全黑名单、表/字段存在性、JOIN 白名单）",
            "sql_sample": "SQL 样本执行（只读、LIMIT 1000、超时 30s）",
            "spark_static": "Spark 静态检查（AST 安全分析）",
            "spark_sample": "Spark 样本执行",
            "cross_validation": "SQL/Spark 交叉验证",
            "business_semantics": "业务语义正确性（JOIN 基数、指标口径）",
            "full_data_behavior": "全量数据行为（非 LIMIT 约束下的行为）",
            "production_performance": "生产性能（执行计划、资源消耗）",
            "partition_idempotency_rollback": "分区/幂等/回滚正确性",
        }.get(key, key)
        status_icon = "✅" if val not in ("NOT_COVERED", "SKIPPED", "PENDING", "FAILED") else "⚠️"
        lines.append(f"- {status_icon} **{label}**：{val}")

    lines.append("")

    # 未验证风险
    unverified = coverage.unverified_dimensions
    if unverified:
        lines.extend([
            "## 未验证风险",
            "",
            "以下维度当前验证不覆盖，人审时需特别注意：",
            "",
        ])
        for key in unverified:
            detail = {
                "business_semantics": "JOIN 基数正确性、指标口径准确性、业务逻辑等价性——需要业务专家审查",
                "full_data_behavior": "LIMIT 1000 样本不代表全量数据行为——全量 JOIN 可能产生不同结果",
                "production_performance": "执行计划、内存消耗、分区剪枝——需在类生产环境独立评估",
                "partition_idempotency_rollback": "分区覆盖正确性、幂等性、回滚安全性——需独立测试",
            }.get(key, "当前不验证")
            lines.append(f"- **{key}**：{detail}")
        lines.append("")

    lines.extend([
        "## PENDING / SKIPPED 原因",
    ])

    if no_sql_run:
        lines.append("- SQL sample run: SKIPPED，CLI 指定 --no-sql-run。")
    elif not conn_provided:
        lines.append("- SQL sample run: SKIPPED，未提供开发库或 sample 数据源。")
    if spark_result and spark_result.error:
        lines.append(f"- Spark sample run: {spark_result.error}")
    if sql_result and sql_result.error:
        lines.append(f"- SQL sample run: {sql_result.error}")
    if not any("SKIPPED" in line or "PENDING" in line for line in lines[-4:]):
        lines.append("- 无。")

    lines.extend([
        "",
        "## 静态检查明细",
    ])
    for check in static_report.checks:
        lines.append(f"- {check.name}: {_status_text(check.status)}，{check.detail}")

    # M5：部署静态检查明细
    deploy_checks = deploy_static_checks or []
    if deploy_checks:
        lines.extend([
            "",
            "## 部署静态检查明细",
        ])
        for check in deploy_checks:
            lines.append(f"- {check.name}: {_status_text(check.status)}，{check.detail}")

    lines.extend([
        "",
        "## WARN / FAIL 明细",
    ])
    lines.extend(f"- FAIL: {item}" for item in failures)
    lines.extend(f"- WARN: {item}" for item in warnings)
    if not failures and not warnings:
        lines.append("- 无。")

    lines.extend([
        "",
        "## 人审提示",
        "",
        "- SQL/Spark 均为草案。",
        "- 未经人审不得上线。",
        "- Agent 不写生产库，不自动上线，不替代人工审批。",
        "- **三道防线用于降低风险，不构成上线充分条件。**",
        "- **当前验证为 PARTIAL 级别——仅 SQL 单引擎样本执行，不证明业务正确或生产就绪。**",
        "",
    ])
    return "\n".join(lines)


def _build_cross_validation_report(
    sql_result: SQLResult | None,
    spark_result: SQLResult | None,
    cross_status: str,
    detail: str,
    value_diffs: list[dict],
) -> str:
    """生成 cross_validation.md。"""
    lines = [
        "# Cross Validation Report",
        "",
        f"SQL 结果状态：{_result_state(sql_result)}",
        f"Spark 结果状态：{_result_state(spark_result)}",
        f"cross_validation_status：{cross_status}",
        "",
        "## 比较项",
        "",
        f"- 行数比较：{_row_count_compare(sql_result, spark_result)}",
        f"- 列名比较：{_columns_compare(sql_result, spark_result)}",
        f"- 抽样行比较：{_sample_compare(sql_result, spark_result)}",
        f"- 数值指标比较：{_numeric_compare(value_diffs, sql_result, spark_result)}",
        "",
        "## 差异摘要",
        "",
    ]
    if value_diffs:
        for diff in value_diffs:
            lines.append(f"- {diff}")
    else:
        lines.append(f"- {detail}")

    lines.extend([
        "",
        "## 人审建议",
        "",
        "- 交叉验证结果不能替代人工审批。",
        "- WARN/SKIPPED/PENDING 均需要人工确认是否可继续。",
        "- CONSISTENT 仅代表两份代码的 LIMIT 1000 样本结果一致，不代表全量数据一致、业务正确或生产就绪。",
        "- 当前 Spark 不可用时交叉验证始终 SKIPPED——无法提供双引擎背书。",
        "- 未经人审不得上线。",
        "",
    ])
    return "\n".join(lines)


def _status_text(status: ValidationStatus) -> str:
    """转换静态检查状态。"""
    mapping = {
        ValidationStatus.PASSED: "PASS",
        ValidationStatus.WARN: "WARN",
        ValidationStatus.FAILED: "FAIL",
        ValidationStatus.PENDING: "PENDING",
    }
    return mapping[status]


def _result_state(result: SQLResult | None) -> str:
    """描述 sample run 结果状态。"""
    if result is None:
        return "SKIPPED/PENDING"
    if result.error:
        return result.error
    return f"PASS，{result.row_count} 行"


def _row_count_compare(sql_result: SQLResult | None, spark_result: SQLResult | None) -> str:
    """描述行数比较。"""
    if not sql_result or not spark_result or sql_result.error or spark_result.error:
        return "SKIPPED"
    return "PASS" if sql_result.row_count == spark_result.row_count else "WARN"


def _columns_compare(sql_result: SQLResult | None, spark_result: SQLResult | None) -> str:
    """描述列名比较。"""
    if not sql_result or not spark_result or sql_result.error or spark_result.error:
        return "SKIPPED"
    return "PASS" if sql_result.columns == spark_result.columns else "WARN"


def _sample_compare(sql_result: SQLResult | None, spark_result: SQLResult | None) -> str:
    """描述抽样行比较。"""
    if not sql_result or not spark_result or sql_result.error or spark_result.error:
        return "SKIPPED"
    return "PASS" if sql_result.rows[:5] == spark_result.rows[:5] else "WARN"


def _numeric_compare(
    value_diffs: list[dict],
    sql_result: SQLResult | None,
    spark_result: SQLResult | None,
) -> str:
    """描述数值指标比较。"""
    if not sql_result or not spark_result or sql_result.error or spark_result.error:
        return "SKIPPED"
    if not value_diffs:
        return "PASS"
    if any(diff.get("type") == "numeric_sum" for diff in value_diffs):
        return "WARN"
    return "PASS"
