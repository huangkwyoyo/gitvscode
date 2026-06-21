"""
一次性可写 DuckDB CTAS Sandbox 执行器——M5b-1。

在完全隔离的临时 DuckDB 数据库中执行受控 CTAS 写入，
验证输出结果后强制销毁所有临时资源。

安全模型：
  - 每次验证创建全新的临时目录和 DuckDB 数据库文件
  - 数据库路径由系统内部生成，不由部署脚本指定
  - 目标表名被重写为 Sandbox 内部目标，不直接执行 Manifest 声明的目标
  - 只允许 CTAS 写入 sandbox_output schema
  - 禁止 ATTACH/DETACH/COPY/EXPORT 等危险操作
  - 所有连接在 finally 中关闭，所有临时文件在 finally 中删除
  - 清理失败必须报告 FAIL，不能静默忽略

当前限制（M5b-1）：
  - 仅支持单 source table CTAS——不支持 JOIN、多 FROM、逗号连接的多表查询
  - 多表/JOIN 支持留到后续阶段（M5b-2 或 M5b-3）
  - 超时使用 threading.Timer + conn.interrupt() 硬中断
"""
from __future__ import annotations

import hashlib
import re
import secrets
import shutil
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import duckdb
except ImportError:
    duckdb = None  # 类型检查时可用，运行时报 ImportError

from src.ir.types import MaterializationCheckResult, MaterializationResult

# ── M5b-1 只允许 CTAS 写入 sandbox_output schema ──
SANDBOX_OUTPUT_SCHEMA = "sandbox_output"
SANDBOX_INPUT_SCHEMA = "sandbox_input"

# ── 部署 SQL 禁止关键字（复用 M5 定义，额外增加 Sandbox 特有项）──
FORBIDDEN_DEPLOY_KEYWORDS = {
    "DROP", "ALTER", "TRUNCATE", "DELETE", "MERGE", "REPLACE",
    "GRANT", "REVOKE", "ATTACH", "DETACH", "EXPORT", "IMPORT",
    "COPY", "INSTALL", "LOAD",
}

# ── 额外的 Sandbox 特定禁止关键字/模式 ──
FORBIDDEN_SANDBOX_PATTERNS = [
    "read_csv", "read_parquet", "read_json", "read_csv_auto",
    "PRAGMA", "SET ", "USE ", "SHOW ",
]

# ── 最大超时时间（秒）──
DEFAULT_CTAS_TIMEOUT_SECONDS = 60

# ── 输入/输出行数上限（防止资源耗尽）──
MAX_INPUT_ROWS = 50_000
MAX_OUTPUT_ROWS = 10_000


def _iso_now() -> str:
    """返回当前 UTC ISO8601 时间戳。"""
    return datetime.now(timezone.utc).isoformat()


def _hash_content(content: str) -> str:
    """计算内容的 SHA-256 哈希。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _validate_identifier(name: str, label: str = "标识符") -> str | None:
    """校验 SQL 标识符——只允许字母数字和下划线，禁止注入。

    Args:
        name: 要校验的标识符
        label: 人类可读标签（用于错误信息）

    Returns:
        错误信息字符串；通过则返回 None
    """
    if not name or not name.strip():
        return f"{label}为空——禁止点号、引号、分号等绕过"
    stripped = name.strip()
    # 只允许字母数字和下划线
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", stripped):
        return (
            f"{label}非法: {stripped}——只允许字母、数字和下划线，"
            f"禁止点号、引号、分号等绕过字符"
        )
    if len(stripped) > 128:
        return f"{label}过长: {len(stripped)} > 128 字符"
    return None


def _strip_sql_comments(sql: str) -> str:
    """去除 SQL 注释，防止注释内容干扰安全扫描。"""
    without_line = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    return re.sub(r"/\*.*?\*/", "", without_line, flags=re.DOTALL)


# ═══════════════════════════════════════════════════════════════
# Sandbox 执行器核心
# ═══════════════════════════════════════════════════════════════


def execute_ctas_in_sandbox(
    deploy_sql: str,
    manifest: dict[str, Any],
    sample_data_rows: list[tuple],
    sample_data_columns: list[str],
    sample_data_types: list[str],
    source_query_hash: str = "",
    sandbox_root: Optional[Path] = None,
    timeout_seconds: int = DEFAULT_CTAS_TIMEOUT_SECONDS,
    declared_table_name: str = "",
) -> MaterializationResult:
    """在一次性 DuckDB Sandbox 中执行 CTAS 并验证结果。

    这是 M5b-1 的唯一执行入口。内部执行完整的 12 步生命周期。

    Args:
        deploy_sql: deploy/main.sql 内容（CTAS 语句）
        manifest: deployment_manifest.yml 解析后的 dict
        sample_data_rows: 输入样本数据行列表
        sample_data_columns: 输入样本数据列名
        sample_data_types: 输入样本数据列类型
        source_query_hash: sql/main.sql 的 SHA-256 哈希（供校验）
        sandbox_root: Sandbox 根目录（默认项目 .sandbox_tmp/）
        timeout_seconds: CTAS 执行超时（默认 60s）
        declared_table_name: 从部署 SQL 中提取的原始目标表名

    Returns:
        MaterializationResult 包含所有验证结果和清理状态
    """
    if duckdb is None:
        raise ImportError("需要 duckdb 包: pip install duckdb")

    sandbox_id = uuid.uuid4().hex
    if sandbox_root is None:
        sandbox_root = Path.cwd() / ".sandbox_tmp"
    sandbox_dir = sandbox_root / sandbox_id
    sandbox_db_path = sandbox_dir / "sandbox.db"

    result = MaterializationResult(
        verification_id=f"mat_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}",
        request_id=manifest.get("request_id", ""),
        sandbox_id=sandbox_id,
        sandbox_path=str(sandbox_dir.resolve()),
        declared_target=manifest.get("target_table", ""),
        sandbox_target="",
        engine="duckdb",
        operation="CTAS",
        started_at=_iso_now(),
        overall_status="PENDING",
        human_review_required=True,
    )

    # ── 提取原始目标表名，重写为 Sandbox 内部目标 ──
    declared = manifest.get("target_table", "").strip()
    table_name = declared
    if "." in declared:
        table_name = declared.split(".")[-1]
    if not table_name:
        table_name = manifest.get("request_id", "sandbox_output")

    # ── 检查目标表 schema 是否在禁止列表中（在重写之前检查）──
    if "." in declared:
        declared_schema = declared.split(".")[0].lower().strip()
        if declared_schema in {"bronze", "silver", "gold"}:
            result.overall_status = "FAIL"
            result.failures.append(
                f"禁止写入 {declared_schema} schema——"
                f"目标表 {declared} 的 schema 在禁止列表中"
            )
            result.finished_at = _iso_now()
            return result

    # 校验表名标识符安全
    id_error = _validate_identifier(table_name, "目标表名")
    if id_error:
        result.overall_status = "FAIL"
        result.failures.append(f"目标表名非法: {id_error}")
        result.finished_at = _iso_now()
        return result

    sandbox_target = f"{SANDBOX_OUTPUT_SCHEMA}.{table_name}"
    result.sandbox_target = sandbox_target

    conn = None
    try:
        # ── 步骤 1-2：创建隔离临时目录 ──
        sandbox_dir.mkdir(parents=True, exist_ok=False)

        # ── 步骤 3：创建一次性 DuckDB 数据库 ──
        conn = duckdb.connect(str(sandbox_db_path))
        # 禁用 httpfs 扩展，防止网络访问
        try:
            conn.execute("SET enable_httpfs=false;")
        except Exception:
            pass  # httpfs 可能不可用，忽略

        # ── 步骤 4：初始化 schema ──
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {SANDBOX_INPUT_SCHEMA}")
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {SANDBOX_OUTPUT_SCHEMA}")

        # ── 步骤 5：装载受控 sample 数据 ──
        if not sample_data_rows or not sample_data_columns:
            result.overall_status = "FAIL"
            result.failures.append(
                "无可用的 sample 数据——Sandbox 需要显式提供的测试输入数据"
            )
            result.execution_status = "SKIPPED"
            return result

        source_table_name = _load_sample_data(
            conn, sample_data_rows, sample_data_columns,
            sample_data_types, declared_table_name,
        )
        # 安全起见，截断到上限
        conn.execute(f"SELECT COUNT(*) FROM {source_table_name}")
        actual_count = conn.fetchone()[0]
        if actual_count > MAX_INPUT_ROWS:
            result.failures.append(
                f"输入数据行数 {actual_count} 超过上限 {MAX_INPUT_ROWS}"
            )
            result.overall_status = "FAIL"
            return result

        # ── 步骤 6：重写 CTAS 目标表 ──
        rewritten_sql = _rewrite_ctas_target(
            deploy_sql, declared, sandbox_target, source_table_name,
        )
        if rewritten_sql is None:
            result.overall_status = "FAIL"
            result.failures.append("无法重写 CTAS 目标表——部署 SQL 格式不符合预期")
            result.static_validation_status = "FAIL"
            return result

        # ── 步骤 7：安全扫描重写后的 SQL ──
        scan_errors = _scan_ctas_safety(rewritten_sql, sandbox_target)
        if scan_errors:
            result.overall_status = "FAIL"
            result.failures.extend(scan_errors)
            result.static_validation_status = "FAIL"
            return result

        # ── 步骤 8：执行重写后的 CTAS（带硬超时中断）──
        # 使用 threading.Timer + conn.interrupt() 实现硬超时，
        # 避免长时间运行的 CTAS 无法被中断。
        # 参照只读 executor.py 的超时模式，但独立实现以保持 Sandbox 隔离。
        execution_start = time.perf_counter()
        execution_done = threading.Event()
        _timed_out = False

        def _interrupt_query() -> None:
            """超时回调：中断正在执行的 DuckDB 查询。"""
            nonlocal _timed_out
            if not execution_done.is_set():
                _timed_out = True
                try:
                    conn.interrupt()
                except Exception:
                    pass  # 中断操作本身失败不影响主流程

        timer = threading.Timer(timeout_seconds, _interrupt_query)
        timer.start()

        try:
            conn.execute(rewritten_sql)
            elapsed = (time.perf_counter() - execution_start) * 1000
        except Exception as exc:
            elapsed = (time.perf_counter() - execution_start) * 1000
            if _timed_out:
                # 超时中断——进入 FAIL
                result.execution_status = "FAIL"
                result.failures.append(
                    f"CTAS 执行超时（>{timeout_seconds}s，耗时 {elapsed:.0f}ms）——已被硬中断"
                )
                result.overall_status = "FAIL"
                result.finished_at = _iso_now()
                return result
            # 非超时错误——SQL 语法/执行错误
            result.execution_status = "FAIL"
            result.failures.append(f"CTAS 执行失败（{elapsed:.0f}ms）: {exc}")
            result.overall_status = "FAIL"
            result.finished_at = _iso_now()
            return result
        finally:
            # 确保 Timer 在任何路径下都被取消，防止误中断后续逻辑
            execution_done.set()
            timer.cancel()

        if elapsed / 1000 > timeout_seconds:
            # 查询完成但接近超时——仅提醒，不视为失败
            result.warnings.append(
                f"CTAS 执行耗时 {elapsed:.0f}ms 接近超时限制 {timeout_seconds}s"
            )

        result.execution_status = "PASS"
        result.checks.append(MaterializationCheckResult(
            check_id="ctas_execution",
            name="CTAS 执行",
            status="PASS",
            detail=f"CTAS 执行成功（{elapsed:.0f}ms）",
            severity="FAIL",
        ))

        # ── 步骤 9：验证输出结果 ──
        _verify_output(conn, sandbox_target, result, manifest)

        # ── 步骤 10：检查源表数据未被修改 ──
        try:
            conn.execute(f"SELECT COUNT(*) FROM {source_table_name}")
            post_count = conn.fetchone()[0]
            if post_count != actual_count:
                result.warnings.append(
                    f"输入表 {source_table_name} 行数在执行前后不一致"
                    f"（{actual_count} → {post_count}）"
                )
        except Exception:
            pass  # 表不存在则跳过

        # ── 聚合状态 ──
        result.finished_at = _iso_now()
        result = _aggregate_status(result)

    finally:
        # ── 步骤 11：强制清理（finally 保证任何路径都执行）──
        cleanup_success = _cleanup_sandbox(conn, sandbox_dir)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        result.cleanup_status = "PASS" if cleanup_success else "FAIL"
        if not cleanup_success:
            result.overall_status = "FAIL"
            result.failures.append(
                f"Sandbox 清理失败——残留路径: {sandbox_dir}"
            )
            result.checks.append(MaterializationCheckResult(
                check_id="cleanup",
                name="Sandbox 清理",
                status="FAIL",
                detail=f"清理失败，残留路径: {sandbox_dir}——需人工处理",
                severity="FAIL",
            ))
        else:
            result.checks.append(MaterializationCheckResult(
                check_id="cleanup",
                name="Sandbox 清理",
                status="PASS",
                detail="Sandbox 临时目录已销毁",
                severity="FAIL",
            ))
        # 清理失败时 finalize overall_status——优先级最高
        if not cleanup_success and result.overall_status != "FAIL":
            result.overall_status = "FAIL"
        elif not cleanup_success:
            pass  # 已是 FAIL

    result.generated_at = _iso_now()
    return result


# ═══════════════════════════════════════════════════════════════
# 内部辅助函数
# ═══════════════════════════════════════════════════════════════


def _load_sample_data(
    conn: Any,
    rows: list[tuple],
    columns: list[str],
    types: list[str],
    declared_table: str,
) -> str:
    """将 sample 数据加载到 Sandbox 输入 schema 中。

    Args:
        conn: DuckDB 连接
        rows: 数据行列表
        columns: 列名列表
        types: 列类型列表（如 ['DATE', 'INTEGER', 'DOUBLE']）
        declared_table: 原始声明目标表名

    Returns:
        Sandbox 内输入表的完全限定名
    """
    # 从原始目标表名推导输入表名
    base = declared_table.split(".")[-1] if "." in declared_table else declared_table
    if not base or not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", base):
        base = "source_data"
    source_table = f"{SANDBOX_INPUT_SCHEMA}.{base}_source"

    # 建表
    col_defs = ", ".join(
        f'"{c}" {t}' for c, t in zip(columns, types)
    )
    conn.execute(f"CREATE TABLE {source_table} ({col_defs})")

    # 插入数据
    if rows:
        placeholders = ", ".join(["?" for _ in columns])
        conn.executemany(f"INSERT INTO {source_table} VALUES ({placeholders})", rows)

    return source_table


def _rewrite_ctas_target(
    deploy_sql: str,
    declared_target: str,
    sandbox_target: str,
    source_table: str,
) -> str | None:
    """将 CTAS 的目标表重写为 Sandbox 内部目标，同时重写 FROM 子句中的源表。

    策略：
      1. 将 "CREATE OR REPLACE TABLE <declared>" 替换为
         "CREATE OR REPLACE TABLE <sandbox_target>"
      2. 将 "FROM <original_source>" 替换为 "FROM <source_table>"
         （如果检测到 gold./bronze./silver. 开头的源表引用）

    Args:
        deploy_sql: 原始部署 SQL（CTAS 语句）
        declared_target: 原始声明目标表（如 generated.trip_daily_report_m2）
        sandbox_target: Sandbox 内部目标表（如 sandbox_output.trip_daily_report_m2）
        source_table: Sandbox 内部源表

    Returns:
        重写后的 SQL；解析失败返回 None
    """
    cleaned = _strip_sql_comments(deploy_sql).strip().rstrip(";")

    # 模式匹配：CREATE [OR REPLACE] TABLE <target> AS <select>
    pattern = re.compile(
        r"(CREATE\s+(?:OR\s+REPLACE\s+)?TABLE\s+)([a-zA-Z_][a-zA-Z0-9_.]*)(\s+AS\s+)",
        re.IGNORECASE,
    )
    match = pattern.search(cleaned)
    if not match:
        return None

    # 替换目标表
    rewritten = pattern.sub(
        rf"\1{sandbox_target}\3",
        cleaned,
        count=1,
    )

    # 替换 FROM 子句中的源表——将 gold.xxx / bronze.xxx / silver.xxx
    # 替换为 sandbox_input.xxx_source
    # 识别原始 SQL 中 FROM 后的表名
    from_pattern = re.compile(
        r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)',
        re.IGNORECASE,
    )
    from_match = from_pattern.search(rewritten)
    if from_match:
        original_from = from_match.group(1)
        # 只替换 gold/bronze/silver schema 的表引用
        if "." in original_from:
            schema = original_from.split(".")[0].lower()
            if schema in {"gold", "bronze", "silver"}:
                rewritten = from_pattern.sub(
                    f"FROM {source_table}",
                    rewritten,
                    count=1,
                )

    return rewritten


def _scan_ctas_safety(sql: str, allowed_target: str) -> list[str]:
    """安全扫描重写后的 CTAS SQL。

    检查项：
      - 禁止多语句（分号分割）
      - 多表/JOIN 检测（M5b-1 仅支持单 source table）
      - 禁止关键字（ATTACH/DROP/ALTER/COPY/EXPORT …）
      - 禁止文件读取函数（read_csv/read_parquet …）
      - 目标 schema 必须在 sandbox_output
      - 禁止 PRAGMA / SET / USE 等危险配置

    Args:
        sql: 重写后的 CTAS SQL
        allowed_target: 允许的目标表（如 sandbox_output.xxx）

    Returns:
        错误列表——空列表表示通过
    """
    errors: list[str] = []
    cleaned = _strip_sql_comments(sql).upper()

    # ── 禁止多语句 ──
    semicolons = [i for i, c in enumerate(sql) if c == ";"]
    if len(semicolons) > 1:
        errors.append("多语句 SQL 被拒绝——Sandbox 只允许单条 CTAS")

    # ── 多表/JOIN 检测（M5b-1 仅支持单 source table CTAS）──
    # 在去除注释后检查——必须在关键字检查之前执行，
    # 确保多表场景被显式拒绝，而非静默不完整执行。
    from_matches = re.findall(r"\bFROM\s+", cleaned)
    if len(from_matches) > 1:
        errors.append(
            f"检测到 {len(from_matches)} 个 FROM 子句——"
            f"M5b-1 仅支持单 source table CTAS，多表/JOIN 支持留到后续阶段"
        )
    if re.search(r"\bJOIN\b", cleaned):
        errors.append(
            "检测到 JOIN——M5b-1 仅支持单 source table CTAS，"
            "JOIN/多表支持留到后续阶段"
        )
    # 检测逗号连接的多表 FROM（如 FROM a, b 或 FROM a alias, b）
    if re.search(r"\bFROM\s+\w+\.?\w*(?:\s+\w+)?\s*,\s*\w+", cleaned):
        errors.append(
            "检测到逗号连接的多表 FROM——M5b-1 仅支持单 source table CTAS，"
            "多表/JOIN 支持留到后续阶段"
        )

    # ── 禁止关键字 ──
    for keyword in FORBIDDEN_DEPLOY_KEYWORDS:
        if re.search(rf"\b{keyword}\b", cleaned):
            # "REPLACE" 在 "CREATE OR REPLACE" 中是合法的
            if keyword == "REPLACE" and "CREATE OR REPLACE" in cleaned:
                continue
            errors.append(
                f"检测到禁止关键字: {keyword}——Sandbox 只允许受控 CTAS"
            )

    # ── 禁止文件读取函数 ──
    for pattern in FORBIDDEN_SANDBOX_PATTERNS:
        if re.search(rf"\b{pattern}\b", cleaned):
            errors.append(
                f"检测到禁止模式: {pattern}——"
                f"Sandbox 不允许外部文件读取、网络访问或危险配置"
            )

    # ── 禁止写入非 sandbox_output schema ──
    # 提取所有 CREATE TABLE 的目标
    create_targets = re.findall(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?TABLE\s+([a-zA-Z_][a-zA-Z0-9_.]*)",
        cleaned,
    )
    for target in create_targets:
        target_lower = target.lower()
        if not target_lower.startswith(SANDBOX_OUTPUT_SCHEMA.lower() + "."):
            errors.append(
                f"非法写入目标: {target}——Sandbox 只允许写入 "
                f"{SANDBOX_OUTPUT_SCHEMA} schema"
            )

    return errors


def _verify_output(
    conn: Any,
    sandbox_target: str,
    result: MaterializationResult,
    manifest: dict[str, Any] | None = None,
) -> None:
    """验证 CTAS 输出结果——表存在、schema、行数、空值率、唯一键。

    所有检查结果写入 result.checks 列表。

    唯一键检查：
      - 如果 manifest 中声明了 unique_keys（非空列表）→ 实际执行检查（required=True）
      - 如果未声明 → NOT_APPLICABLE（required=False），不阻止 PASS
    """
    if manifest is None:
        manifest = {}
    # ── 检查 1：目标表存在 ──
    try:
        desc_result = conn.execute(f"DESCRIBE {sandbox_target}").fetchall()
    except Exception as exc:
        result.checks.append(MaterializationCheckResult(
            check_id="output_object_exists",
            name="目标对象存在",
            status="FAIL",
            detail=f"目标表 {sandbox_target} 不存在: {exc}",
            severity="FAIL",
        ))
        result.output_schema_status = "FAIL"
        return

    result.checks.append(MaterializationCheckResult(
        check_id="output_object_exists",
        name="目标对象存在",
        status="PASS",
        detail=f"目标表 {sandbox_target} 存在",
        severity="FAIL",
    ))

    # ── 检查 2：输出 schema ──
    # desc_result: [(name, type, null, key, default, extra)]
    output_columns = [row[0] for row in desc_result]
    output_types = [row[1] for row in desc_result]
    result.output_columns = output_columns
    result.output_column_types = output_types

    if output_columns:
        result.checks.append(MaterializationCheckResult(
            check_id="output_schema",
            name="输出 Schema",
            status="PASS",
            detail=f"{len(output_columns)} 列: {', '.join(output_columns)}",
            severity="FAIL",
        ))
        result.output_schema_status = "PASS"
    else:
        result.checks.append(MaterializationCheckResult(
            check_id="output_schema",
            name="输出 Schema",
            status="FAIL",
            detail="输出表无列定义",
            severity="FAIL",
        ))
        result.output_schema_status = "FAIL"

    # ── 检查 3：行数 ──
    try:
        row_count_result = conn.execute(
            f"SELECT COUNT(*) FROM {sandbox_target}"
        ).fetchone()
        output_row_count = row_count_result[0] if row_count_result else 0
        result.output_row_count = output_row_count

        if output_row_count > MAX_OUTPUT_ROWS:
            result.checks.append(MaterializationCheckResult(
                check_id="row_count",
                name="输出行数",
                status="FAIL",
                detail=f"输出 {output_row_count} 行超过上限 {MAX_OUTPUT_ROWS}",
                severity="FAIL",
            ))
            result.row_count_status = "FAIL"
        elif output_row_count == 0:
            result.checks.append(MaterializationCheckResult(
                check_id="row_count",
                name="输出行数",
                status="WARN",
                detail="输出 0 行——可能输入数据为空或过滤条件过严",
                severity="WARN",
            ))
            result.row_count_status = "WARN"
            result.warnings.append("输出表为空——请确认输入 sample 数据是否有效")
        else:
            result.checks.append(MaterializationCheckResult(
                check_id="row_count",
                name="输出行数",
                status="PASS",
                detail=f"输出 {output_row_count} 行",
                severity="FAIL",
            ))
            result.row_count_status = "PASS"
    except Exception as exc:
        result.checks.append(MaterializationCheckResult(
            check_id="row_count",
            name="输出行数",
            status="FAIL",
            detail=f"行数查询失败: {exc}",
            severity="FAIL",
        ))
        result.row_count_status = "FAIL"

    # ── 检查 4：空值率（每列）──
    null_rates: dict[str, float] = {}
    for col in output_columns:
        try:
            count_result = conn.execute(
                f"SELECT COUNT(*) FROM {sandbox_target} WHERE \"{col}\" IS NULL"
            ).fetchone()
            null_count = count_result[0] if count_result else 0
            rate = null_count / max(output_row_count, 1)
            null_rates[col] = rate
        except Exception:
            null_rates[col] = -1.0  # 查询失败标记
    result.null_rates = null_rates

    high_null_cols = [
        f"{col} ({rate:.1%})"
        for col, rate in null_rates.items()
        if rate > 0.3
    ]
    if high_null_cols:
        result.checks.append(MaterializationCheckResult(
            check_id="null_rate",
            name="空值率",
            status="WARN",
            detail=f"高空值率列: {', '.join(high_null_cols)}——阈值 30%",
            severity="WARN",
        ))
        result.null_check_status = "WARN"
    else:
        result.checks.append(MaterializationCheckResult(
            check_id="null_rate",
            name="空值率",
            status="PASS",
            detail="所有列空值率在阈值内",
            severity="WARN",
        ))
        result.null_check_status = "PASS"

    # ── 检查 5：数值列汇总（确认 CTAS 未丢失或篡改数据）──
    numeric_sums: dict[str, float] = {}
    # DuckDB 数值类型: INTEGER, BIGINT, HUGEINT, SMALLINT, TINYINT,
    #                   FLOAT, DOUBLE, DECIMAL, NUMERIC, REAL
    # DuckDB 可能返回带精度的类型如 DECIMAL(38,2)——提取基础类型名比较
    _numeric_base_types = {
        "INTEGER", "BIGINT", "HUGEINT", "SMALLINT", "TINYINT",
        "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "REAL",
    }
    numeric_cols = [
        col for col, t in zip(output_columns, output_types)
        if t.upper().split("(")[0] in _numeric_base_types
    ]
    for col in numeric_cols:
        try:
            sum_result = conn.execute(
                f"SELECT SUM(\"{col}\") FROM {sandbox_target}"
            ).fetchone()
            numeric_sums[col] = float(sum_result[0]) if sum_result[0] is not None else 0.0
        except Exception:
            numeric_sums[col] = 0.0
    result.numeric_sums = numeric_sums

    # ── 规范化行内容哈希——供幂等性检查比较实际数据内容 ──
    # 将输出表的所有行按全部列排序后计算 SHA-256，确保内容级比较而非仅元数据比较
    _compute_canonical_hash(conn, sandbox_target, output_columns, result)

    # ── 检查 6：唯一键（根据契约决定是否必需）──
    # M5b-2 P0 修复：未声明唯一键时 NOT_APPLICABLE，不阻塞 PASS。
    # 已声明唯一键时执行实际 GROUP BY/HAVING 检查，required=True。
    unique_keys: list[str] = (
        manifest.get("unique_keys", []) or []
    )
    if unique_keys:
        # 已声明唯一键——执行实际检查
        _check_uniqueness(conn, sandbox_target, unique_keys, result)
    else:
        # 未声明唯一键——NOT_APPLICABLE，不提供唯一性背书
        result.checks.append(MaterializationCheckResult(
            check_id="uniqueness",
            name="唯一键检查",
            status="NOT_APPLICABLE",
            detail="未声明唯一键契约——当前验证不提供唯一性背书。如需唯一性保证，请在 deployment_manifest.yml 中声明 unique_keys。",
            severity="WARN",
            required=False,
        ))
        result.uniqueness_status = "NOT_APPLICABLE"


def _compute_canonical_hash(
    conn: Any,
    sandbox_target: str,
    output_columns: list[str],
    result: MaterializationResult,
) -> None:
    """计算输出表规范化排序行的 SHA-256 哈希——供幂等内容比较。

    查询所有行按全部列排序，对每个值做规范化处理后计算哈希。
    规范化规则：
      - NULL → 哨兵字符串 "__NULL__"
      - float → 6 位小数格式（消除浮点表示差异）
      - 其他 → str(value)
    """
    if not output_columns:
        result.canonical_hash = ""
        return

    try:
        # 构建 ORDER BY 子句——按所有列排序确保确定性
        order_clause = ", ".join(f'"{col}"' for col in output_columns)
        select_clause = ", ".join(f'"{col}"' for col in output_columns)
        query = (
            f'SELECT {select_clause} FROM {sandbox_target} '
            f'ORDER BY {order_clause}'
        )
        rows = conn.execute(query).fetchall()

        # 规范化每行每列的值并计算 SHA-256
        hasher = hashlib.sha256()
        for row in rows:
            normalized_parts: list[str] = []
            for value in row:
                if value is None:
                    normalized_parts.append("__NULL__")
                elif isinstance(value, float):
                    normalized_parts.append(f"{value:.6f}")
                elif isinstance(value, bool):
                    # bool 要先检测（bool 是 int 的子类）
                    normalized_parts.append("true" if value else "false")
                else:
                    normalized_parts.append(str(value))
            # 用不可见分隔符拼接各列值，避免跨列碰撞
            hasher.update("\x1f".join(normalized_parts).encode("utf-8"))
            hasher.update(b"\x1e")  # 行分隔符

        result.canonical_hash = hasher.hexdigest()
    except Exception:
        # 哈希计算失败不影响主验证流程——留空标记为不可比较
        result.canonical_hash = ""
        result.warnings.append("规范化行哈希计算失败——幂等内容比较将不可用")


def _check_uniqueness(
    conn: Any,
    sandbox_target: str,
    unique_keys: list[str],
    result: MaterializationResult,
) -> None:
    """执行唯一键检查——GROUP BY + HAVING COUNT(*) > 1。

    检查指定的唯一键列组合是否存在重复行。
    列名不存在或检查失败均报告 FAIL。

    Args:
        conn: DuckDB 连接
        sandbox_target: Sandbox 内部目标表名
        unique_keys: 唯一键列名列表（来自 manifest.unique_keys）
        result: 物化验证结果（原地修改）
    """
    # 验证列名存在
    output_columns = result.output_columns
    missing_cols = [col for col in unique_keys if col not in output_columns]
    if missing_cols:
        result.checks.append(MaterializationCheckResult(
            check_id="uniqueness",
            name="唯一键检查",
            status="FAIL",
            detail=(
                f"声明的唯一键列不存在: {', '.join(missing_cols)}。"
                f"输出列为: {', '.join(output_columns)}"
            ),
            severity="FAIL",
            required=True,
        ))
        result.uniqueness_status = "FAIL"
        result.failures.append(
            f"唯一键检查失败——声明的列 {missing_cols} 不在输出中"
        )
        return

    # 执行唯一性检查
    key_cols = ", ".join(f'"{col}"' for col in unique_keys)
    try:
        dup_result = conn.execute(
            f"SELECT COUNT(*) FROM ("
            f"  SELECT {key_cols}, COUNT(*) AS _cnt "
            f"  FROM {sandbox_target} "
            f"  GROUP BY {key_cols} "
            f"  HAVING COUNT(*) > 1"
            f") AS _dup_check"
        ).fetchone()
        dup_count = dup_result[0] if dup_result else 0
    except Exception as exc:
        result.checks.append(MaterializationCheckResult(
            check_id="uniqueness",
            name="唯一键检查",
            status="FAIL",
            detail=f"唯一键检查执行失败: {exc}",
            severity="FAIL",
            required=True,
        ))
        result.uniqueness_status = "FAIL"
        result.failures.append(f"唯一键检查执行失败: {exc}")
        return

    if dup_count == 0:
        result.checks.append(MaterializationCheckResult(
            check_id="uniqueness",
            name="唯一键检查",
            status="PASS",
            detail=f"唯一键 ({', '.join(unique_keys)}) 无重复——{result.output_row_count} 行全部唯一",
            severity="FAIL",
            required=True,
        ))
        result.uniqueness_status = "PASS"
    else:
        result.checks.append(MaterializationCheckResult(
            check_id="uniqueness",
            name="唯一键检查",
            status="FAIL",
            detail=(
                f"唯一键 ({', '.join(unique_keys)}) 存在 {dup_count} 组重复——"
                f"数据不符合唯一约束"
            ),
            severity="FAIL",
            required=True,
        ))
        result.uniqueness_status = "FAIL"
        result.failures.append(
            f"唯一键检查失败——{dup_count} 组重复行（键: {unique_keys}）"
        )


def _aggregate_status(result: MaterializationResult) -> MaterializationResult:
    """聚合所有检查项的状态到 overall_status。

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


def _cleanup_sandbox(conn: Any, sandbox_dir: Path) -> bool:
    """清理 Sandbox 临时资源和目录。

    先关闭连接，再删除目录树。删除失败返回 False。

    Args:
        conn: DuckDB 连接（可能已关闭或为 None）
        sandbox_dir: Sandbox 临时目录路径

    Returns:
        True 表示清理成功
    """
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass

    if sandbox_dir.exists():
        try:
            shutil.rmtree(sandbox_dir)
        except Exception:
            return False

    # 验证目录确实不存在
    if sandbox_dir.exists():
        return False
    return True


# ═══════════════════════════════════════════════════════════════
# 幂等性检查
# ═══════════════════════════════════════════════════════════════


def check_idempotency(
    deploy_sql: str,
    manifest: dict[str, Any],
    sample_data_rows: list[tuple],
    sample_data_columns: list[str],
    sample_data_types: list[str],
    sandbox_root: Optional[Path] = None,
    timeout_seconds: int = DEFAULT_CTAS_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """在两个独立 Sandbox 中分别执行同一 CTAS，比较输出一致性。

    三层比较（B1 增强）：
      L0（已有）：列名 + 行数——快速筛除明显不一致
      L1（新增）：规范化排序行 SHA-256 哈希——检测内容差异
      L2（新增）：数值列合计 + 空值计数——补充摘要级检测

    这是 M5b-1 的幂等验证——不是 INSERT OVERWRITE 幂等。

    Args:
        参数同 execute_ctas_in_sandbox

    Returns:
        dict: {
            "status": "PASS" | "WARN" | "FAIL",
            "detail": "...",
            "run1_row_count": int,
            "run2_row_count": int,
            "run1_columns": [...],
            "run2_columns": [...],
            "schema_match": bool,
            "row_count_match": bool,
            "content_hash_match": bool | None,
            "numeric_sums_match": bool | None,
            "null_counts_match": bool | None,
        }
    """
    run1 = execute_ctas_in_sandbox(
        deploy_sql=deploy_sql,
        manifest=manifest,
        sample_data_rows=sample_data_rows,
        sample_data_columns=sample_data_columns,
        sample_data_types=sample_data_types,
        sandbox_root=sandbox_root,
        timeout_seconds=timeout_seconds,
    )

    run2 = execute_ctas_in_sandbox(
        deploy_sql=deploy_sql,
        manifest=manifest,
        sample_data_rows=sample_data_rows,
        sample_data_columns=sample_data_columns,
        sample_data_types=sample_data_types,
        sandbox_root=sandbox_root,
        timeout_seconds=timeout_seconds,
    )

    # ── L0：列名 + 行数（已有逻辑）──
    schema_match = run1.output_columns == run2.output_columns
    row_count_match = run1.output_row_count == run2.output_row_count

    # ── L1：规范化行内容哈希 ──
    content_hash_match: bool | None = None
    if run1.canonical_hash and run2.canonical_hash:
        content_hash_match = run1.canonical_hash == run2.canonical_hash

    # ── L2：数值列合计比较（使用 0.1% 容差）──
    numeric_sums_match: bool | None = None
    if run1.numeric_sums or run2.numeric_sums:
        all_cols = set(run1.numeric_sums.keys()) | set(run2.numeric_sums.keys())
        if all_cols:
            tolerance = 0.001
            diffs = []
            for col in sorted(all_cols):
                v1 = run1.numeric_sums.get(col, 0.0)
                v2 = run2.numeric_sums.get(col, 0.0)
                allowed = max(abs(v1), abs(v2), 1.0) * tolerance
                if abs(v1 - v2) > allowed:
                    diffs.append(col)
            numeric_sums_match = len(diffs) == 0

    # ── L2：空值计数比较 ──
    null_counts_match: bool | None = None
    if run1.null_rates or run2.null_rates:
        all_cols = set(run1.null_rates.keys()) | set(run2.null_rates.keys())
        if all_cols:
            diffs = []
            for col in sorted(all_cols):
                n1 = run1.null_rates.get(col, 0.0)
                n2 = run2.null_rates.get(col, 0.0)
                if abs(n1 - n2) > 0.001:  # 空值率需精确匹配
                    diffs.append(col)
            null_counts_match = len(diffs) == 0

    # ── 综合判定 ──
    if not schema_match:
        status = "FAIL"
        detail = (
            f"两次执行输出 schema 不一致"
            f"（{run1.output_columns} vs {run2.output_columns}）——"
            f"CTAS 行为不确定"
        )
    elif not row_count_match:
        status = "WARN"
        detail = (
            f"两次执行 schema 一致但行数不同"
            f"（{run1.output_row_count} vs {run2.output_row_count}）——"
            f"CTAS 行为不一致，需人工审查"
        )
    elif content_hash_match is False:
        # 行数和列名相同但内容不同——确定性 CTAS 不应出现
        status = "FAIL"
        detail = (
            f"两次执行列名和行数一致但规范化内容哈希不同"
            f"（{run1.output_row_count} 行）——"
            f"CTAS 输出内容不一致，确定性假设不成立"
        )
    elif numeric_sums_match is False:
        status = "FAIL"
        detail = (
            f"两次执行数值列合计不一致——"
            f"CTAS 在相同输入上产生了不同的汇总值"
        )
    elif null_counts_match is False:
        status = "WARN"
        detail = (
            f"两次执行空值计数不一致——"
            f"可能存在 NULL 处理差异，需人工审查"
        )
    elif row_count_match and schema_match:
        content_detail = (
            "内容哈希一致" if content_hash_match
            else "内容哈希不可用" if content_hash_match is None
            else ""
        )
        status = "PASS"
        detail = (
            f"两次独立执行结果一致"
            f"（{run1.output_row_count} == {run2.output_row_count} 行，"
            f"schema 匹配"
            f"{'，' + content_detail if content_detail else ''}"
            f"）"
        )
    else:
        status = "FAIL"
        detail = "两次执行结果存在未分类的差异"

    return {
        "status": status,
        "detail": detail,
        "run1_row_count": run1.output_row_count,
        "run2_row_count": run2.output_row_count,
        "run1_columns": run1.output_columns,
        "run2_columns": run2.output_columns,
        "schema_match": schema_match,
        "row_count_match": row_count_match,
        "content_hash_match": content_hash_match,
        "numeric_sums_match": numeric_sums_match,
        "null_counts_match": null_counts_match,
    }
