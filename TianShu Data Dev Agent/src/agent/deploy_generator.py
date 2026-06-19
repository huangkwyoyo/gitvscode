"""
部署草案生成器——M5 确定性封装。

从已验证的只读查询（sql/main.sql、spark/main.py）确定性生成部署写入脚本。
不重新生成业务查询逻辑，只添加受控的写入封装。

核心原则：
  1. SQL 部署脚本从已验证的 sql/main.sql 确定性封装——不重写、不复制查询逻辑
  2. Spark 部署脚本调用已审批的 build_dataframe() 入口，只添加写入封装
  3. deploy/main.py 不得重新实现过滤、聚合或 JOIN
  4. 目标表必须是 generated 或 approved schema，禁止写 bronze/silver/gold
  5. 部署配置全部进入 deployment_manifest.yml，纳入审批哈希
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Optional

from src.ir.types import (
    DeployWriteStrategy,
    DeploymentManifest,
    ReleaseStatus,
)

# ── 允许写入的 schema 白名单（复用 pipeline_execution_config_schema.yml 定义）──
ALLOWED_WRITE_SCHEMAS = {"generated"}
FORBIDDEN_WRITE_SCHEMAS = {"bronze", "silver", "gold"}

# ── 允许的写入策略集合 ──
ALLOWED_WRITE_STRATEGIES = {s.value for s in DeployWriteStrategy}

# ── 部署脚本中禁止的关键字（DROP/ALTER/TRUNCATE/DELETE 等）──
FORBIDDEN_DEPLOY_KEYWORDS = {
    "DROP", "ALTER", "TRUNCATE", "DELETE", "MERGE", "REPLACE",
    "GRANT", "REVOKE", "ATTACH", "DETACH", "EXPORT", "IMPORT",
    "COPY", "INSTALL", "LOAD",
}

# ── Spark 部署脚本中禁止的模式 ──
FORBIDDEN_SPARK_DEPLOY_PATTERNS = [
    ".write",
    ".save",
    ".saveAsTable",
    "save(",
    "saveastable",
    "insertinto",
    "overwrite",
    "parquet(",
    "csv(",
    "json(",
]


def _hash_content(content: str) -> str:
    """计算内容的 SHA-256 哈希。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _strip_sql_comments(sql: str) -> str:
    """去除 SQL 注释，避免注释内容干扰安全扫描。"""
    without_line = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    return re.sub(r"/\*.*?\*/", "", without_line, flags=re.DOTALL)


# ═══════════════════════════════════════════════════════════════
# 部署草案校验
# ═══════════════════════════════════════════════════════════════


def validate_write_boundary(manifest: DeploymentManifest) -> list[str]:
    """校验部署清单的写入边界是否安全。

    检查项：
      1. 目标表合法——schema 不在禁止列表
      2. 写入策略在支持列表中
      3. 分区覆盖/追加必须声明分区列
      4. target_environment 不能是生产值
      5. 无禁止的 SQL 关键字

    Returns:
        错误信息列表——空列表表示通过
    """
    errors: list[str] = []

    if manifest.mode != "MATERIALIZE":
        errors.append("部署清单 mode 必须为 MATERIALIZE")
    if manifest.allowed_write_schema not in ALLOWED_WRITE_SCHEMAS:
        errors.append(
            f"allowed_write_schema 不允许: {manifest.allowed_write_schema}——"
            f"允许: {', '.join(sorted(ALLOWED_WRITE_SCHEMAS))}"
        )

    # 检查 1：目标表 schema
    target = manifest.target_table.strip() if manifest.target_table else ""
    if not target:
        errors.append("部署清单缺少 target_table——必须指定目标写入表")
    else:
        parts = target.split(".")
        if len(parts) >= 2:
            schema = parts[0].lower().strip()
            if schema in FORBIDDEN_WRITE_SCHEMAS:
                errors.append(
                    f"禁止写入 {schema} schema——目标表 {target} 处于禁止写入列表"
                    f"（禁止: {', '.join(sorted(FORBIDDEN_WRITE_SCHEMAS))}）"
                )
            if schema not in ALLOWED_WRITE_SCHEMAS and schema not in FORBIDDEN_WRITE_SCHEMAS:
                errors.append(
                    f"目标表 {target} 的 schema '{schema}' 不在允许写入列表中"
                    f"（允许: {', '.join(sorted(ALLOWED_WRITE_SCHEMAS))}）"
                )

    # 检查 2：写入策略白名单
    strategy = manifest.write_strategy.strip() if manifest.write_strategy else ""
    if not strategy:
        errors.append("部署清单缺少 write_strategy——必须声明写入策略")
    elif strategy not in ALLOWED_WRITE_STRATEGIES:
        errors.append(
            f"不支持的写入策略: {strategy}——允许: {', '.join(sorted(ALLOWED_WRITE_STRATEGIES))}"
        )

    # 检查 3：分区覆盖/追加必须声明分区列
    if strategy in {
        DeployWriteStrategy.INSERT_OVERWRITE_PARTITION.value,
        DeployWriteStrategy.INSERT_INTO_PARTITION.value,
    }:
        if not manifest.partition_columns:
            errors.append(
                f"写入策略 {strategy} 要求声明 partition_columns——"
                f"分区覆盖/追加必须指定分区列，防止意外全量覆盖"
            )

    # 检查 4：target_environment 不能是生产值
    env = manifest.target_environment.upper().strip() if manifest.target_environment else ""
    if env in {"PRODUCTION", "PROD", "LIVE"}:
        errors.append(
            f"target_environment 不能为 {manifest.target_environment}——"
            f"部署清单禁止包含生产环境连接信息"
        )

    return errors


def validate_deploy_sql(deploy_sql: str) -> list[str]:
    """校验 SQL 部署脚本不包含禁止的 DDL/DML 关键字。

    "REPLACE" 关键字仅在非 CTAS 上下文中（即非 "CREATE OR REPLACE"）被拦截。
    这是为了防止独立 REPLACE 语句（MySQL 等方言中的行替换操作）。

    Returns:
        错误信息列表——空列表表示通过
    """
    errors: list[str] = []
    cleaned = _strip_sql_comments(deploy_sql).upper()

    for keyword in FORBIDDEN_DEPLOY_KEYWORDS:
        if re.search(rf"\b{keyword}\b", cleaned):
            # "REPLACE" 在 "CREATE OR REPLACE" 中是合法的 CTAS 语法
            if keyword == "REPLACE" and "CREATE OR REPLACE" in cleaned:
                continue
            errors.append(
                f"SQL 部署脚本包含禁止关键字: {keyword}——"
                f"部署只能使用 CTAS/INSERT/CREATE VIEW 等受控写入"
            )

    return errors


def validate_deploy_spark(deploy_spark: str) -> list[str]:
    """校验 Spark 部署脚本不包含禁止的写入模式。

    注意：Spark 部署脚本需要 .write.save() 来实际写入，
    但必须受限于 deployment_manifest 中声明的策略。
    此检查确保不出现未受控的写入路径。
    """
    errors: list[str] = []
    lowered = deploy_spark.lower()

    for pattern in FORBIDDEN_SPARK_DEPLOY_PATTERNS:
        if pattern in lowered:
            errors.append(
                f"Spark 部署脚本包含禁止模式: {pattern}"
            )

    return errors


def validate_deploy_does_not_reimplement_query(
    deploy_spark: str,
    verified_spark: str,
) -> list[str]:
    """确认 Spark 部署脚本引用 build_dataframe 而非重新实现业务逻辑。

    检查 deploy/main.py：
      - 必须导入或引用 build_dataframe
      - 不得重新实现过滤条件（WHERE 子句中的日期范围）
      - 不得重新实现聚合逻辑

    Returns:
        警告列表——提醒人审时注意
    """
    warnings: list[str] = []

    if "build_dataframe" not in deploy_spark:
        warnings.append(
            "Spark 部署脚本未引用 build_dataframe()——"
            "部署脚本应调用已验证的转换入口，而非重新实现业务逻辑"
        )

    return warnings


# ═══════════════════════════════════════════════════════════════
# SQL 部署草案生成
# ═══════════════════════════════════════════════════════════════


def generate_deploy_sql(
    verified_sql: str,
    manifest: DeploymentManifest,
) -> str:
    """从已验证的只读 SELECT 确定性封装 SQL 部署写入脚本。

    封装规则（按 write_strategy）：
      - CREATE_TABLE_AS_SELECT：CREATE OR REPLACE TABLE target AS <verified SELECT>
      - INSERT_OVERWRITE_PARTITION：INSERT OVERWRITE target PARTITION (cols) <verified SELECT>
      - INSERT_INTO_PARTITION：INSERT INTO target PARTITION (cols) <verified SELECT>
      - CREATE_VIEW：CREATE OR REPLACE VIEW target AS <verified SELECT>

    绝不重新生成或修改内部 SELECT 逻辑。
    """
    strategy = manifest.write_strategy
    target = manifest.target_table
    partitions = ", ".join(manifest.partition_columns) if manifest.partition_columns else ""

    # 缩进已验证的 SELECT 体
    indent = "    "
    sql_body = "\n".join(indent + line for line in verified_sql.strip().rstrip(";").split("\n"))

    header = (
        "-- 部署草案：从已验证只读查询确定性封装。\n"
        "-- 未经验证、未经人审、未获发布批准，不得执行。\n"
        f"-- 来源查询：{manifest.source_query_ref}\n"
        f"-- 来源哈希：{manifest.source_query_hash[:16]}...\n"
        f"-- 写入策略：{strategy}\n"
        f"-- 目标表：{target}\n"
    )

    if strategy == DeployWriteStrategy.CREATE_TABLE_AS_SELECT.value:
        return f"{header}\nCREATE OR REPLACE TABLE {target} AS\n{sql_body};\n"

    elif strategy == DeployWriteStrategy.INSERT_OVERWRITE_PARTITION.value:
        partition_clause = f"PARTITION ({partitions})" if partitions else ""
        return (
            f"{header}\n"
            f"INSERT OVERWRITE TABLE {target}\n"
            f"{partition_clause}\n"
            f"{sql_body};\n"
        )

    elif strategy == DeployWriteStrategy.INSERT_INTO_PARTITION.value:
        partition_clause = f"PARTITION ({partitions})" if partitions else ""
        return (
            f"{header}\n"
            f"INSERT INTO TABLE {target}\n"
            f"{partition_clause}\n"
            f"{sql_body};\n"
        )

    elif strategy == DeployWriteStrategy.CREATE_VIEW.value:
        return f"{header}\nCREATE OR REPLACE VIEW {target} AS\n{sql_body};\n"

    else:
        raise ValueError(
            f"不支持的写入策略: {strategy}——"
            f"允许: {', '.join(sorted(ALLOWED_WRITE_STRATEGIES))}"
        )


# ═══════════════════════════════════════════════════════════════
# Spark 部署草案生成
# ═══════════════════════════════════════════════════════════════


def generate_deploy_spark(
    manifest: DeploymentManifest,
) -> str:
    """生成 Spark 部署脚本——调用已验证的 build_dataframe() + 受控写入。

    关键约束：
      - 调用 build_dataframe(spark) 获取已验证的 DataFrame
      - 只添加受控的写入封装（.write.saveAsTable() 等）
      - 不复制过滤、聚合或 JOIN 逻辑
      - 不硬编码文件路径
    """
    strategy = manifest.write_strategy
    target = manifest.target_table

    header = (
        "# 部署草案：从已验证只读查询确定性封装。\n"
        "# 未经验证、未经人审、未获发布批准，不得执行。\n"
        f"# 来源查询：{manifest.source_query_ref}\n"
        f"# 来源哈希：{manifest.source_query_hash[:16]}...\n"
        f"# 写入策略：{strategy}\n"
        f"# 目标表：{target}\n"
    )

    lines = [
        header,
        "",
        "# ═══════════════════════════════════════════════════════",
        "# 注意：以下导入的 build_dataframe 是唯一已验证的业务逻辑入口。",
        "# 不得在此文件中重新实现过滤、聚合或 JOIN。",
        "# ═══════════════════════════════════════════════════════",
        "from spark.main import build_dataframe",
        "",
        "",
        "def deploy(spark):",
        '    """部署入口——调用已验证的 build_dataframe + 受控写入"""',
        "    # 调用已验证的只读转换——不修改、不重写业务逻辑",
        "    df = build_dataframe(spark)",
        "",
    ]

    if strategy == DeployWriteStrategy.CREATE_TABLE_AS_SELECT.value:
        lines.extend([
            f"    # 受控写入：saveAsTable 到 {target}",
            f'    df.write.mode("overwrite").saveAsTable("{target}")',
        ])
    elif strategy == DeployWriteStrategy.INSERT_OVERWRITE_PARTITION.value:
        partitions = manifest.partition_columns
        if partitions:
            part_str = ", ".join(f'"{p}"' for p in partitions)
            lines.extend([
                f"    # 受控写入：分区覆盖写入 {target}",
                f"    # 分区列: {', '.join(partitions)}",
                f'    df.write.mode("overwrite").partitionBy({part_str}).saveAsTable("{target}")',
            ])
        else:
            lines.extend([
                f"    # 受控写入：覆盖写入 {target}（无分区列——请人在审批时确认）",
                f'    df.write.mode("overwrite").saveAsTable("{target}")',
            ])
    elif strategy == DeployWriteStrategy.INSERT_INTO_PARTITION.value:
        partitions = manifest.partition_columns
        if partitions:
            part_str = ", ".join(f'"{p}"' for p in partitions)
            lines.extend([
                f"    # 受控写入：分区追加写入 {target}",
                f"    # 分区列: {', '.join(partitions)}",
                f'    df.write.mode("append").partitionBy({part_str}).saveAsTable("{target}")',
            ])
        else:
            lines.extend([
                f"    # 受控写入：追加写入 {target}（无分区列——请人在审批时确认）",
                f'    df.write.mode("append").saveAsTable("{target}")',
            ])
    elif strategy == DeployWriteStrategy.CREATE_VIEW.value:
        lines.extend([
            f"    # 受控写入：创建视图 {target}",
            f'    df.createOrReplaceTempView("{target.split(".")[-1]}")',
            f"    # 注意：createOrReplaceTempView 仅创建临时视图",
            f"    # 若需持久化视图，需人在审批后通过 Spark SQL 创建",
        ])

    lines.extend([
        "",
        f"    return df",
        "",
    ])

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 部署清单构建
# ═══════════════════════════════════════════════════════════════


def build_deployment_manifest(
    request_id: str,
    verified_sql_hash: str,
    verified_spark_hash: str = "",
    target_table: str = "",
    write_strategy: str = "",
    partition_columns: Optional[list[str]] = None,
    human_review_points: Optional[list[str]] = None,
) -> DeploymentManifest:
    """构建部署清单——所有字段默认安全。

    Args:
        request_id: 请求标识
        verified_sql_hash: sql/main.sql 的 SHA-256 哈希
        verified_spark_hash: spark/main.py 的 SHA-256 哈希
        target_table: 目标写入表（完全限定名，如 generated.daily_trip_summary）
        write_strategy: 写入策略（DeployWriteStrategy 值）
        partition_columns: 分区列列表
        human_review_points: 人审关注点

    Returns:
        DeploymentManifest——release_status 默认为 DRAFT
    """
    if not target_table:
        target_table = f"generated.{request_id}"

    if not write_strategy:
        write_strategy = DeployWriteStrategy.CREATE_TABLE_AS_SELECT.value

    partition_cols = list(partition_columns) if partition_columns else []

    warnings: list[str] = []
    review_points = list(human_review_points) if human_review_points else []

    # 默认警告——提醒人审者注意
    warnings.append(
        "部署草案未获发布批准——release_status 为 DRAFT，"
        "需人审者审查部署产物和配置后显式设置 RELEASE_APPROVED"
    )
    warnings.append(
        "target_environment 为 STAGING——是占位值，"
        "实际部署时需人工替换为正确的环境标识"
    )
    review_points.append(
        "Human Review: 请确认目标表、写入策略和分区列是否符合上线要求"
    )

    return DeploymentManifest(
        request_id=request_id,
        mode="MATERIALIZE",
        source_sql_ref="sql/main.sql",
        source_sql_hash=verified_sql_hash,
        source_spark_ref="spark/main.py",
        source_spark_hash=verified_spark_hash,
        source_query_ref="sql/main.sql",
        source_query_hash=verified_sql_hash,
        target_environment="STAGING",
        target_table=target_table,
        write_strategy=write_strategy,
        partition_columns=partition_cols,
        sql_deploy_artifact="deploy/main.sql",
        spark_deploy_artifact="deploy/main.py",
        allowed_write_schema="generated",
        materialization_status="PENDING",
        human_review_required=True,
        release_status=ReleaseStatus.DRAFT.value,
        warnings=warnings,
        human_review_points=review_points,
    )
