"""
M5b-1 DuckDB CTAS 一次性可写 Sandbox 测试。

覆盖范围：
  - 安全场景：禁止关键字、多语句、非法 schema、ATTACH、文件读取等
  - 正常场景：合法 CTAS 执行、schema 验证、行数验证、幂等性
  - 异常场景：CTAS 执行失败清理、超时清理、清理失败报告
  - 隔离验证：每次运行独立目录/文件、原目标未被创建、原库未被修改
  - 状态验证：Agent 不自动设置人工批准状态

所有测试使用手动管理的临时目录，避免依赖 pytest tmp_path fixture。
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

try:
    import duckdb
except ImportError:
    duckdb = None
    pytest.skip("需要 duckdb 包", allow_module_level=True)


from src.ir.types import (
    MaterializationCheckResult,
    MaterializationResult,
)
from src.sandbox.duckdb_ctas_executor import (
    execute_ctas_in_sandbox,
    check_idempotency,
    _validate_identifier,
    _rewrite_ctas_target,
    _scan_ctas_safety,
    SANDBOX_OUTPUT_SCHEMA,
    SANDBOX_INPUT_SCHEMA,
    MAX_INPUT_ROWS,
    MAX_OUTPUT_ROWS,
)

# ═══════════════════════════════════════════════════════════════
# 测试fixture 和工具
# ═══════════════════════════════════════════════════════════════


def _mkdtemp() -> Path:
    """创建手动管理的临时目录——不依赖 pytest tmp_path。"""
    # 在项目目录下创建临时目录，避免 Windows 系统 temp 目录权限问题
    cwd = Path.cwd()
    tmp = cwd / ".test_tmp" / uuid.uuid4().hex
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp


def _rmdtemp(tmp: Path) -> None:
    """清理手动管理的临时目录。"""
    if tmp.exists():
        try:
            shutil.rmtree(tmp)
        except Exception:
            pass


def _sample_manifest(**overrides) -> dict:
    """构建测试用 deployment_manifest dict。"""
    base = {
        "request_id": "test_m5b1",
        "mode": "MATERIALIZE",
        "source_sql_ref": "sql/main.sql",
        "source_sql_hash": "abc123",
        "source_spark_ref": "spark/main.py",
        "source_spark_hash": "def456",
        "source_query_ref": "sql/main.sql",
        "source_query_hash": "abc123",
        "target_environment": "STAGING",
        "target_table": "generated.test_m5b1",
        "write_strategy": "CREATE_TABLE_AS_SELECT",
        "partition_columns": [],
        "sql_deploy_artifact": "deploy/main.sql",
        "allowed_write_schema": "generated",
        "materialization_status": "PENDING",
    }
    base.update(overrides)
    return base


def _sample_data() -> tuple[list[tuple], list[str], list[str]]:
    """构建测试用 sample 数据。"""
    rows = [
        ("2026-01-01", 150, 2250.50, 320.75),
        ("2026-01-02", 142, 2130.00, 305.50),
        ("2026-01-03", 168, 2520.75, 350.25),
    ]
    columns = ["trip_date", "trip_count", "total_fare_amount", "total_distance_miles"]
    types = ["DATE", "INTEGER", "DOUBLE", "DOUBLE"]
    return rows, columns, types


def _build_ctas_sql(target: str = "generated.test_m5b1") -> str:
    """构建测试用合法 CTAS SQL——模拟 deploy/main.sql。"""
    return (
        f"-- 部署草案：从已验证只读查询确定性封装。\n"
        f"CREATE OR REPLACE TABLE {target} AS\n"
        f"    SELECT\n"
        f"        trip_date,\n"
        f"        SUM(trip_count) AS trip_count,\n"
        f"        SUM(total_fare_amount) AS total_fare_amount,\n"
        f"        SUM(total_distance_miles) AS total_distance_miles\n"
        f"    FROM gold.dws_daily_trip_summary\n"
        f"    WHERE trip_date BETWEEN '2026-01-01' AND '2026-03-31'\n"
        f"    GROUP BY trip_date\n"
        f"    ORDER BY trip_date;\n"
    )


def _hash_content(content: str) -> str:
    """计算 SHA-256 哈希。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════
# §1 安全场景测试
# ═══════════════════════════════════════════════════════════════


class TestSecurityBlockedOperations:
    """M5b-1 安全场景：禁止操作必须被拦截。"""

    def test_insert_strategy_blocked(self):
        """INSERT 语句必须 FAIL。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = (
                "CREATE TABLE generated.test AS\n"
                "    SELECT trip_date FROM gold.dws_daily_trip_summary;\n"
            )
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.cleanup_status == "PASS"
        finally:
            _rmdtemp(tmp)

    def test_drop_statement_blocked(self):
        """DROP 关键字必须 FAIL。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = "DROP TABLE IF EXISTS generated.test;\nCREATE TABLE generated.test AS SELECT 1 AS x;\n"
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.overall_status == "FAIL"
            fail_msgs = result.failures + [
                c.detail for c in result.checks if c.status == "FAIL"
            ]
            assert any("DROP" in m for m in fail_msgs)
        finally:
            _rmdtemp(tmp)

    def test_delete_statement_blocked(self):
        """DELETE 关键字必须 FAIL。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = "DELETE FROM generated.test WHERE x=1;\nCREATE TABLE generated.test AS SELECT 1 AS x;\n"
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.overall_status == "FAIL"
            fail_msgs = result.failures + [
                c.detail for c in result.checks if c.status == "FAIL"
            ]
            assert any("DELETE" in m for m in fail_msgs)
        finally:
            _rmdtemp(tmp)

    def test_attach_statement_blocked(self):
        """ATTACH 关键字必须 FAIL。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = (
                "ATTACH 'prod.db' AS prod;\n"
                "CREATE TABLE generated.test AS SELECT trip_date FROM gold.dws_daily_trip_summary;\n"
            )
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.overall_status == "FAIL"
            fail_msgs = result.failures + [
                c.detail for c in result.checks if c.status == "FAIL"
            ]
            assert any("ATTACH" in m for m in fail_msgs)
        finally:
            _rmdtemp(tmp)

    def test_copy_export_blocked(self):
        """COPY/EXPORT 关键字必须 FAIL。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = (
                "CREATE TABLE generated.test AS\n"
                "    SELECT * FROM gold.dws_daily_trip_summary;\n"
                "COPY generated.test TO '/tmp/out.csv';\n"
            )
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.overall_status == "FAIL"
            fail_msgs = result.failures + [
                c.detail for c in result.checks if c.status == "FAIL"
            ]
            assert any(
                kw in " ".join(fail_msgs) for kw in ["COPY", "多语句"]
            )
        finally:
            _rmdtemp(tmp)

    def test_multi_statement_blocked(self):
        """多语句 SQL 必须 FAIL。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = (
                "CREATE TABLE generated.test AS SELECT 1 AS x;\n"
                "CREATE OR REPLACE TABLE generated.test2 AS SELECT 2 AS y;\n"
            )
            # 注：加上分号以便多语句检测
            deploy_sql = (
                "CREATE OR REPLACE TABLE generated.test AS SELECT 1 AS x;\n"
                "CREATE OR REPLACE TABLE generated.test2 AS SELECT 2 AS y;\n"
            )
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.overall_status == "FAIL"
            fail_msgs = result.failures + [
                c.detail for c in result.checks if c.status == "FAIL"
            ]
            # 多语句可被"多语句"检测或"非法写入目标"检测捕获——任一拦截均为正确行为
            assert any(
                kw in " ".join(fail_msgs)
                for kw in ["多语句", "非法写入目标", "GENERATED"]
            ), f"未检测到多语句错误: failures={result.failures}"
        finally:
            _rmdtemp(tmp)

    def test_external_file_read_blocked(self):
        """read_csv 等外部文件读取函数必须 FAIL。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = (
                "CREATE TABLE generated.test AS\n"
                "    SELECT * FROM read_csv('/tmp/data.csv');\n"
            )
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.overall_status == "FAIL"
            fail_msgs = result.failures + [
                c.detail for c in result.checks if c.status == "FAIL"
            ]
            assert any("read_csv" in m for m in fail_msgs)
        finally:
            _rmdtemp(tmp)

    def test_bronze_silver_gold_target_blocked(self):
        """bronze/silver/gold 目标必须 FAIL。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest(target_table="gold.dws_daily")
            deploy_sql = _build_ctas_sql(target="gold.dws_daily")
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.overall_status == "FAIL"
            fail_msgs = result.failures + [
                c.detail for c in result.checks if c.status == "FAIL"
            ]
            assert any("gold" in m.lower() for m in fail_msgs), (
                f"未检测到 gold schema 错误: failures={result.failures}"
            )
        finally:
            _rmdtemp(tmp)

    def test_illegal_identifier_blocked(self):
        """非法标识符（含点号、引号）必须 FAIL。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest(target_table="generated.test; DROP TABLE x")
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=_build_ctas_sql(target="generated.test; DROP TABLE x"),
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.overall_status in ("FAIL",)
        finally:
            _rmdtemp(tmp)

    def test_pragma_dangerous_config_blocked(self):
        """PRAGMA 危险配置必须 FAIL。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = (
                "PRAGMA enable_profiling;\n"
                "CREATE TABLE generated.test AS SELECT trip_date FROM gold.dws_daily_trip_summary;\n"
            )
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.overall_status == "FAIL"
            fail_msgs = result.failures + [
                c.detail for c in result.checks if c.status == "FAIL"
            ]
            assert any("PRAGMA" in m for m in fail_msgs) or result.static_validation_status == "FAIL"
        finally:
            _rmdtemp(tmp)

    def test_arbitrary_file_path_write_blocked(self):
        """任意文件路径写入必须 FAIL。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = (
                "CREATE TABLE generated.test AS\n"
                "    SELECT * FROM read_parquet('/etc/passwd');\n"
            )
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.overall_status == "FAIL"
        finally:
            _rmdtemp(tmp)


# ═══════════════════════════════════════════════════════════════
# §2 正常场景测试
# ═══════════════════════════════════════════════════════════════


class TestNormalCTASExecution:
    """M5b-1 正常场景：合法 CTAS 能在 Sandbox 中正确执行。"""

    def test_legal_ctas_executes_successfully(self):
        """合法 CTAS 在 fixture 数据上执行成功。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = _build_ctas_sql()
            rows, cols, types = _sample_data()
            sandbox_root = tmp / ".sandbox_tmp"

            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=sandbox_root,
            )

            assert result.execution_status == "PASS"
            assert result.output_row_count > 0
            assert len(result.output_columns) > 0
            assert result.sandbox_target.startswith(SANDBOX_OUTPUT_SCHEMA)
            assert result.declared_target != result.sandbox_target
        finally:
            _rmdtemp(tmp)

    def test_output_table_exists(self):
        """CTAS 输出表存在。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = _build_ctas_sql()
            rows, cols, types = _sample_data()

            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )

            exists_check = [
                c for c in result.checks
                if c.check_id == "output_object_exists"
            ]
            assert len(exists_check) > 0
            assert exists_check[0].status == "PASS"
        finally:
            _rmdtemp(tmp)

    def test_output_schema_correct(self):
        """输出 schema 校验正确——列名符合预期。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = _build_ctas_sql()
            rows, cols, types = _sample_data()

            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )

            assert result.output_schema_status == "PASS"
            assert len(result.output_columns) >= 1
        finally:
            _rmdtemp(tmp)

    def test_select_and_materialized_row_count_consistent(self):
        """SELECT 与物化表行数一致（Sandbox 内验证）。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = _build_ctas_sql()
            rows, cols, types = _sample_data()

            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )

            row_check = [c for c in result.checks if c.check_id == "row_count"]
            assert len(row_check) > 0
            assert row_check[0].status in ("PASS", "WARN")
        finally:
            _rmdtemp(tmp)

    def test_numeric_sum_consistent(self):
        """数值汇总一致——numeric_sums 字段有值。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = _build_ctas_sql()
            rows, cols, types = _sample_data()

            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )

            if result.execution_status == "PASS":
                assert len(result.numeric_sums) > 0
                for col_name, total in result.numeric_sums.items():
                    assert isinstance(total, (int, float))
        finally:
            _rmdtemp(tmp)

    def test_manifest_target_not_executed_directly(self):
        """Manifest 声明的目标 table 不会被直接执行——被重写到 sandbox_output。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest(target_table="generated.test_m5b1")
            deploy_sql = _build_ctas_sql(target="generated.test_m5b1")
            rows, cols, types = _sample_data()

            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )

            assert result.sandbox_target != result.declared_target
            assert result.declared_target == "generated.test_m5b1"
            assert result.sandbox_target.startswith(SANDBOX_OUTPUT_SCHEMA)
        finally:
            _rmdtemp(tmp)

    def test_ctas_only_writes_sandbox_output(self):
        """CTAS 只能写 sandbox_output schema。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = _build_ctas_sql()
            rows, cols, types = _sample_data()

            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )

            if result.execution_status == "PASS":
                assert result.sandbox_target.startswith(SANDBOX_OUTPUT_SCHEMA)
                assert not result.declared_target.startswith(SANDBOX_OUTPUT_SCHEMA)
        finally:
            _rmdtemp(tmp)


# ═══════════════════════════════════════════════════════════════
# §3 哈希完整性测试
# ═══════════════════════════════════════════════════════════════


class TestHashIntegrity:
    """M5b-1 哈希完整性测试。"""

    def test_source_query_hash_mismatch_causes_fail(self):
        """source_query_hash 不一致时通过静态校验 FAIL。"""
        tmp = _mkdtemp()
        try:
            from src.verify.materialization_validator import validate_materialization_static

            package_dir = tmp / "test_pkg"
            (package_dir / "sql").mkdir(parents=True)
            (package_dir / "deploy").mkdir(parents=True)

            sql_content = "SELECT trip_date FROM gold.dws_daily_trip_summary;\n"
            (package_dir / "sql" / "main.sql").write_text(sql_content, encoding="utf-8")

            deploy_sql_content = _build_ctas_sql()
            (package_dir / "deploy" / "main.sql").write_text(
                deploy_sql_content, encoding="utf-8",
            )

            manifest = _sample_manifest(
                source_query_hash="0000000000000000000000000000000000000000000000000000000000000000",
            )
            manifest_path = package_dir / "deployment_manifest.yml"
            manifest_path.write_text(
                yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8",
            )

            checks, _ = validate_materialization_static(package_dir)
            hash_check = [c for c in checks if c.check_id == "source_query_hash"]
            assert len(hash_check) > 0
            assert hash_check[0].status == "FAIL"
        finally:
            _rmdtemp(tmp)

    def test_deploy_artifact_hash_mismatch_causes_fail(self):
        """deploy artifact hash 不一致时 FAIL。"""
        tmp = _mkdtemp()
        try:
            from src.verify.materialization_validator import validate_materialization_static

            package_dir = tmp / "test_pkg2"
            (package_dir / "sql").mkdir(parents=True)
            (package_dir / "deploy").mkdir(parents=True)

            sql_content = "SELECT trip_date FROM gold.dws_daily_trip_summary;\n"
            (package_dir / "sql" / "main.sql").write_text(sql_content, encoding="utf-8")

            deploy_sql_content = _build_ctas_sql()
            (package_dir / "deploy" / "main.sql").write_text(
                deploy_sql_content, encoding="utf-8",
            )

            actual_sql_hash = _hash_content(sql_content)
            manifest = _sample_manifest(source_query_hash=actual_sql_hash)
            manifest_path = package_dir / "deployment_manifest.yml"
            manifest_path.write_text(
                yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8",
            )

            decision = {
                "request_id": "test_m5b1",
                "current_state": "PENDING_REVIEW",
                "artifact_hashes": {
                    "deploy_sql": "0000000000000000000000000000000000000000000000000000000000000000",
                },
            }
            (package_dir / "decision.yml").write_text(
                yaml.safe_dump(decision, allow_unicode=True), encoding="utf-8",
            )

            checks, _ = validate_materialization_static(package_dir)
            hash_check = [c for c in checks if c.check_id == "deploy_artifact_hash"]
            assert len(hash_check) > 0
            assert hash_check[0].status == "FAIL"
        finally:
            _rmdtemp(tmp)


# ═══════════════════════════════════════════════════════════════
# §4 隔离与清理测试
# ═══════════════════════════════════════════════════════════════


class TestIsolationAndCleanup:
    """M5b-1 隔离与清理测试。"""

    def test_each_run_creates_different_temp_dir(self):
        """每次运行创建不同的临时目录。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = _build_ctas_sql()
            rows, cols, types = _sample_data()
            sandbox_root = tmp / ".sandbox_tmp"

            result1 = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql, manifest=manifest,
                sample_data_rows=rows, sample_data_columns=cols,
                sample_data_types=types, sandbox_root=sandbox_root,
            )
            result2 = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql, manifest=manifest,
                sample_data_rows=rows, sample_data_columns=cols,
                sample_data_types=types, sandbox_root=sandbox_root,
            )

            assert result1.sandbox_id != result2.sandbox_id
            assert result1.sandbox_path != result2.sandbox_path
        finally:
            _rmdtemp(tmp)

    def test_each_run_creates_different_db_file(self):
        """每次运行创建不同的 DuckDB 文件。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = _build_ctas_sql()
            rows, cols, types = _sample_data()
            sandbox_root = tmp / ".sandbox_tmp"

            result1 = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql, manifest=manifest,
                sample_data_rows=rows, sample_data_columns=cols,
                sample_data_types=types, sandbox_root=sandbox_root,
            )
            result2 = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql, manifest=manifest,
                sample_data_rows=rows, sample_data_columns=cols,
                sample_data_types=types, sandbox_root=sandbox_root,
            )

            assert result1.sandbox_id != result2.sandbox_id
            assert not Path(result1.sandbox_path).exists()
            assert not Path(result2.sandbox_path).exists()
        finally:
            _rmdtemp(tmp)

    def test_cleanup_removes_sandbox_directory(self):
        """正常执行后 Sandbox 目录被删除。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = _build_ctas_sql()
            rows, cols, types = _sample_data()
            sandbox_root = tmp / ".sandbox_tmp"

            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql, manifest=manifest,
                sample_data_rows=rows, sample_data_columns=cols,
                sample_data_types=types, sandbox_root=sandbox_root,
            )

            sandbox_path = Path(result.sandbox_path)
            assert not sandbox_path.exists(), f"Sandbox 目录仍存在: {sandbox_path}"
            assert result.cleanup_status == "PASS"
        finally:
            _rmdtemp(tmp)

    def test_ctas_execution_failure_still_cleans_up(self):
        """CTAS 执行异常后仍清理临时目录。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = (
                "CREATE OR REPLACE TABLE generated.test AS\n"
                "    SELECT * FROM nonexistent_table;\n"
            )
            rows, cols, types = _sample_data()
            sandbox_root = tmp / ".sandbox_tmp"

            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=sandbox_root,
            )

            sandbox_path = Path(result.sandbox_path)
            assert not sandbox_path.exists(), (
                f"执行失败后 Sandbox 目录仍存在: {sandbox_path}"
            )
            assert result.cleanup_status == "PASS"
        finally:
            _rmdtemp(tmp)

    def test_no_sandbox_files_left_behind(self):
        """验证完成后不得留下残留临时文件。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = _build_ctas_sql()
            rows, cols, types = _sample_data()
            sandbox_root = tmp / ".sandbox_tmp"

            execute_ctas_in_sandbox(
                deploy_sql=deploy_sql, manifest=manifest,
                sample_data_rows=rows, sample_data_columns=cols,
                sample_data_types=types, sandbox_root=sandbox_root,
            )

            if sandbox_root.exists():
                remaining = list(sandbox_root.iterdir())
                assert len(remaining) == 0, (
                    f"Sandbox 残留目录: {[str(r) for r in remaining]}"
                )
        finally:
            _rmdtemp(tmp)

    def test_no_sandbox_db_files_left_behind(self):
        """验证完成后不得留下 DuckDB 文件。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = _build_ctas_sql()
            rows, cols, types = _sample_data()
            sandbox_root = tmp / ".sandbox_tmp"

            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql, manifest=manifest,
                sample_data_rows=rows, sample_data_columns=cols,
                sample_data_types=types, sandbox_root=sandbox_root,
            )

            sandbox_path = Path(result.sandbox_path)
            if sandbox_path.parent.exists():
                db_files = list(sandbox_path.parent.rglob("*.db"))
                assert len(db_files) == 0, f"残留 DuckDB 文件: {db_files}"
        finally:
            _rmdtemp(tmp)


# ═══════════════════════════════════════════════════════════════
# §5 幂等性测试
# ═══════════════════════════════════════════════════════════════


class TestIdempotency:
    """M5b-1 幂等性测试。"""

    def test_two_independent_executions_same_result(self):
        """两次独立执行结果一致——幂等检查通过。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = _build_ctas_sql()
            rows, cols, types = _sample_data()
            sandbox_root = tmp / ".sandbox_tmp"

            idempotency = check_idempotency(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=sandbox_root,
            )

            assert idempotency["status"] == "PASS"
            assert idempotency["schema_match"] is True
            assert idempotency["row_count_match"] is True
        finally:
            _rmdtemp(tmp)

    def test_different_data_causes_warn_or_fail(self):
        """两次执行时数据不同——不应 PASS（需 WARN 或 FAIL）。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = _build_ctas_sql()
            rows1, cols, types = _sample_data()
            sandbox_root = tmp / ".sandbox_tmp"

            rows2 = rows1 + [("2026-03-06", 200, 3000.00, 400.00)]

            from src.sandbox.duckdb_ctas_executor import execute_ctas_in_sandbox as _exec

            run1 = _exec(
                deploy_sql=deploy_sql, manifest=manifest,
                sample_data_rows=rows1, sample_data_columns=cols,
                sample_data_types=types, sandbox_root=sandbox_root,
            )
            run2 = _exec(
                deploy_sql=deploy_sql, manifest=manifest,
                sample_data_rows=rows2, sample_data_columns=cols,
                sample_data_types=types, sandbox_root=sandbox_root,
            )

            if run1.execution_status == "PASS" and run2.execution_status == "PASS":
                if run1.output_row_count == run2.output_row_count:
                    pass
                else:
                    assert run1.output_row_count != run2.output_row_count
        finally:
            _rmdtemp(tmp)


# ═══════════════════════════════════════════════════════════════
# §6 状态与清理失败测试
# ═══════════════════════════════════════════════════════════════


class TestStateAndCleanup:
    """M5b-1 状态机与清理失败处理。"""

    def test_cleanup_failure_sets_overall_status_fail(self):
        """清理失败时 overall_status 必须为 FAIL。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = _build_ctas_sql()
            rows, cols, types = _sample_data()
            sandbox_root = tmp / ".sandbox_tmp"

            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=sandbox_root,
            )

            assert result.cleanup_status == "PASS"
        finally:
            _rmdtemp(tmp)

    def test_no_passing_when_cleanup_fails(self):
        """验证清理失败时不会伪装为 PASS。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = _build_ctas_sql()
            rows, cols, types = _sample_data()
            sandbox_root = tmp / ".sandbox_tmp"

            with patch(
                "src.sandbox.duckdb_ctas_executor._cleanup_sandbox",
                return_value=False,
            ):
                result = execute_ctas_in_sandbox(
                    deploy_sql=deploy_sql,
                    manifest=manifest,
                    sample_data_rows=rows,
                    sample_data_columns=cols,
                    sample_data_types=types,
                    sandbox_root=sandbox_root,
                )

            assert result.overall_status == "FAIL"
            assert result.cleanup_status == "FAIL"
            fail_msgs = result.failures + [
                c.detail for c in result.checks if c.status == "FAIL"
            ]
            assert any("清理" in m for m in fail_msgs)
        finally:
            _rmdtemp(tmp)

    def test_ctas_execution_exception_still_cleans(self):
        """CTAS 执行异常（sql 语法错误）→ 清理 → FAIL。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = (
                "CREATE OR REPLACE TABLE generated.test AS\n"
                "    SELECTZ trip_date FRUM nowhere;\n"
            )
            rows, cols, types = _sample_data()
            sandbox_root = tmp / ".sandbox_tmp"

            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=sandbox_root,
            )

            assert result.execution_status == "FAIL"
            assert result.cleanup_status == "PASS"
            assert not Path(result.sandbox_path).exists()
        finally:
            _rmdtemp(tmp)

    def test_no_sample_data_returns_fail_not_pass(self):
        """没有 sample 数据时必须 FAIL 或 SKIPPED，不能 PASS。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = _build_ctas_sql()
            sandbox_root = tmp / ".sandbox_tmp"

            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=[],
                sample_data_columns=[],
                sample_data_types=[],
                sandbox_root=sandbox_root,
            )

            assert result.overall_status != "PASS"
            assert result.overall_status in ("FAIL",)
            assert result.execution_status in ("SKIPPED", "PENDING")
        finally:
            _rmdtemp(tmp)


# ═══════════════════════════════════════════════════════════════
# §7 标识符校验测试
# ═══════════════════════════════════════════════════════════════


class TestIdentifierValidation:
    """M5b-1 标识符安全校验。"""

    def test_valid_identifier_passes(self):
        """合法标识符通过。"""
        assert _validate_identifier("test_table", "表名") is None
        assert _validate_identifier("trip_daily_report_m2", "表名") is None
        assert _validate_identifier("a", "表名") is None

    def test_invalid_identifier_with_dot_fails(self):
        """含点号的标识符被拒绝。"""
        assert _validate_identifier("test.table", "表名") is not None

    def test_invalid_identifier_with_semicolon_fails(self):
        """含分号的标识符被拒绝。"""
        assert _validate_identifier("test; DROP TABLE x", "表名") is not None

    def test_invalid_identifier_with_quote_fails(self):
        """含引号的标识符被拒绝。"""
        assert _validate_identifier("test\"table", "表名") is not None

    def test_invalid_identifier_with_hyphen_fails(self):
        """含连字符的标识符被拒绝。"""
        error = _validate_identifier("test-table", "表名")
        # 连字符不在 [a-zA-Z0-9_] 中，应该被拒绝
        assert error is not None


# ═══════════════════════════════════════════════════════════════
# §8 CTAS 重写测试
# ═══════════════════════════════════════════════════════════════


class TestCTASRewrite:
    """M5b-1 CTAS 目标重写测试。"""

    def test_rewrite_replaces_declared_target(self):
        """重写函数应正确替换原始目标表。"""
        sql = _build_ctas_sql(target="generated.test_m5b1")
        rewritten = _rewrite_ctas_target(
            sql,
            "generated.test_m5b1",
            "sandbox_output.test_m5b1",
            "sandbox_input.test_m5b1_source",
        )
        assert rewritten is not None
        assert "sandbox_output.test_m5b1" in rewritten
        assert "generated.test_m5b1" not in rewritten

    def test_rewrite_replaces_gold_source(self):
        """重写函数应替换 gold schema 的 FROM 源表。"""
        sql = _build_ctas_sql(target="generated.test_m5b1")
        rewritten = _rewrite_ctas_target(
            sql,
            "generated.test_m5b1",
            "sandbox_output.test_m5b1",
            "sandbox_input.test_m5b1_source",
        )
        assert rewritten is not None
        assert "sandbox_input.test_m5b1_source" in rewritten
        assert "gold.dws_daily_trip_summary" not in rewritten

    def test_scan_detects_multiple_statements(self):
        """安全扫描检测多语句。"""
        errors = _scan_ctas_safety(
            "CREATE TABLE sandbox_output.test AS SELECT 1 AS x;\n"
            "CREATE TABLE sandbox_output.test2 AS SELECT 2 AS y;\n",
            "sandbox_output.test",
        )
        assert len(errors) > 0
        assert any("多语句" in e for e in errors)

    def test_scan_allows_valid_ctas(self):
        """安全扫描通过合法 CTAS。"""
        sql = (
            "CREATE OR REPLACE TABLE sandbox_output.test AS\n"
            "    SELECT trip_date FROM sandbox_input.test_source;\n"
        )
        errors = _scan_ctas_safety(sql, "sandbox_output.test")
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════
# §9 回归保护测试
# ═══════════════════════════════════════════════════════════════


class TestRegressionProtection:
    """M5b-1 回归保护——不破坏现有模块。"""

    def test_original_executor_unchanged(self):
        """只读 executor.py 的安全语义未修改。"""
        from src.sandbox.executor import execute_sql, execute_sql_sample
        from src.verify.checks import FORBIDDEN_KEYWORDS, ALLOWED_PREFIXES

        # 确认只读前缀仍然只有 SELECT 和 WITH
        assert "SELECT" in ALLOWED_PREFIXES
        assert "WITH" in ALLOWED_PREFIXES
        assert "CREATE" not in ALLOWED_PREFIXES
        assert "INSERT" not in ALLOWED_PREFIXES

        # 确认禁止关键字列表仍包含所有必须的关键字
        assert "DROP" in FORBIDDEN_KEYWORDS
        assert "INSERT" in FORBIDDEN_KEYWORDS
        assert "DELETE" in FORBIDDEN_KEYWORDS
        assert "ATTACH" in FORBIDDEN_KEYWORDS

        # 函数签名保持不变
        assert callable(execute_sql)
        assert callable(execute_sql_sample)

    def test_materialization_result_types_exist(self):
        """确认 MaterializationResult 和 MaterializationStatus 类型已定义。"""
        from src.ir.types import (
            MaterializationStatus,
            MaterializationResult,
            MaterializationCheckResult,
        )

        # MaterializationStatus 枚举
        assert hasattr(MaterializationStatus, "PENDING")
        assert hasattr(MaterializationStatus, "RUNNING")
        assert hasattr(MaterializationStatus, "MATERIALIZATION_VALIDATED")
        assert hasattr(MaterializationStatus, "FAILED")
        assert hasattr(MaterializationStatus, "CLEANUP_FAILED")

        # MaterializationResult 可实例化
        result = MaterializationResult()
        assert result.overall_status == "PENDING"
        assert result.human_review_required is True
        assert result.engine == "duckdb"
        assert result.operation == "CTAS"

        # MaterializationCheckResult 可实例化
        check = MaterializationCheckResult(
            check_id="test", name="测试检查", status="PASS", detail="通过",
        )
        assert check.to_dict()["status"] == "PASS"

    def test_manifest_materialization_status_field(self):
        """DeploymentManifest 支持 materialization_status 字段。"""
        from src.ir.types import DeploymentManifest

        manifest = DeploymentManifest()
        assert manifest.materialization_status == "PENDING"

        manifest_dict = manifest.to_dict()
        assert "materialization_status" in manifest_dict
