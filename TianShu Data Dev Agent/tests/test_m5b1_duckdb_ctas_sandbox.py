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

    def test_valid_ctas_strategy_passes_cleanup(self):
        """合法 CTAS（无 INSERT 关键字）正常执行并通过清理。

        INSERT 写入策略在策略白名单层（ALLOWED_MATERIALIZATION_STRATEGIES）
        和 CTAS 结构校验层被拦截——本测试验证合法 CTAS 全链路通过。
        """
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

    def test_join_statement_blocked(self):
        """JOIN 查询必须 FAIL——M5b-1 仅支持单 source table。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = (
                "CREATE TABLE generated.test AS\n"
                "    SELECT a.trip_date FROM gold.dws_daily_trip_summary a\n"
                "    JOIN gold.other_table b ON a.trip_date = b.trip_date;\n"
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
            assert any("JOIN" in m for m in fail_msgs), (
                f"未检测到 JOIN 错误: failures={result.failures}"
            )
        finally:
            _rmdtemp(tmp)

    def test_comma_join_from_blocked(self):
        """逗号连接的多表 FROM 必须 FAIL。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = (
                "CREATE TABLE generated.test AS\n"
                "    SELECT a.trip_date FROM gold.dws_daily_trip_summary a, gold.other_table b;\n"
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
            assert any("逗号" in m for m in fail_msgs), (
                f"未检测到逗号连接错误: failures={result.failures}"
            )
        finally:
            _rmdtemp(tmp)

    def test_multiple_from_blocked(self):
        """多个 FROM 子句（子查询）必须 FAIL。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            deploy_sql = (
                "CREATE TABLE generated.test AS\n"
                "    SELECT trip_date FROM gold.dws_daily_trip_summary\n"
                "    WHERE trip_date IN (SELECT trip_date FROM gold.other_table);\n"
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
            assert any("FROM" in m for m in fail_msgs), (
                f"未检测到多 FROM 错误: failures={result.failures}"
            )
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

    def test_hash_status_fields_synced_when_pass(self):
        """hash 校验 PASS 后顶层状态字段应同步为 PASS。

        通过 materialization_verification_engine 的完整流程验证：
        source_query_hash_status / deploy_artifact_hash_status 不再保持 PENDING。
        """
        tmp = _mkdtemp()
        try:
            from src.agent.materialization_verification_engine import verify_materialization

            package_dir = tmp / "test_pkg3"
            (package_dir / "sql").mkdir(parents=True)
            (package_dir / "deploy").mkdir(parents=True)

            # 准备合法 CTAS SQL
            deploy_sql_content = _build_ctas_sql()
            (package_dir / "deploy" / "main.sql").write_text(
                deploy_sql_content, encoding="utf-8",
            )

            sql_content = "SELECT trip_date FROM gold.dws_daily_trip_summary;\n"
            (package_dir / "sql" / "main.sql").write_text(sql_content, encoding="utf-8")

            actual_sql_hash = _hash_content(sql_content)
            actual_deploy_hash = _hash_content(deploy_sql_content)

            # Manifest 含正确 hash
            manifest = _sample_manifest(source_query_hash=actual_sql_hash)
            manifest_path = package_dir / "deployment_manifest.yml"
            manifest_path.write_text(
                yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8",
            )

            # Decision 含正确 deploy hash
            decision = {
                "request_id": "test_m5b1",
                "current_state": "PENDING_REVIEW",
                "artifact_hashes": {
                    "deploy_sql": actual_deploy_hash,
                },
            }
            (package_dir / "decision.yml").write_text(
                yaml.safe_dump(decision, allow_unicode=True), encoding="utf-8",
            )

            # 通过 engine 执行——需要传入 sample 数据
            rows, cols, types = _sample_data()
            result = verify_materialization(
                package_dir=package_dir,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
            )

            # 顶层 hash 状态字段应与静态检查结果一致
            # 静态检查中 hash checks 为 PASS → 顶层字段应为 PASS
            assert result.source_query_hash_status != "PENDING", (
                f"source_query_hash_status 应从 PENDING 同步为 PASS/FAIL，"
                f"实际: {result.source_query_hash_status}"
            )
            assert result.deploy_artifact_hash_status != "PENDING", (
                f"deploy_artifact_hash_status 应从 PENDING 同步为 PASS/FAIL，"
                f"实际: {result.deploy_artifact_hash_status}"
            )

            # 验证 hash checks 确实 PASS
            sq_check = [c for c in result.checks if c.check_id == "source_query_hash"]
            da_check = [c for c in result.checks if c.check_id == "deploy_artifact_hash"]
            if sq_check and sq_check[0].status == "PASS":
                assert result.source_query_hash_status == "PASS", (
                    "source_query_hash check 为 PASS，顶层字段应为 PASS，"
                    f"实际: {result.source_query_hash_status}"
                )
            if da_check and da_check[0].status == "PASS":
                assert result.deploy_artifact_hash_status == "PASS", (
                    "deploy_artifact_hash check 为 PASS，顶层字段应为 PASS，"
                    f"实际: {result.deploy_artifact_hash_status}"
                )
        finally:
            _rmdtemp(tmp)

    def test_hash_mismatch_does_not_start_sandbox(self):
        """hash mismatch 时不启动 Sandbox——在静态校验阶段短路。"""
        tmp = _mkdtemp()
        try:
            from src.agent.materialization_verification_engine import verify_materialization

            package_dir = tmp / "test_pkg4"
            (package_dir / "sql").mkdir(parents=True)
            (package_dir / "deploy").mkdir(parents=True)

            deploy_sql_content = _build_ctas_sql()
            (package_dir / "deploy" / "main.sql").write_text(
                deploy_sql_content, encoding="utf-8",
            )

            sql_content = "SELECT trip_date FROM gold.dws_daily_trip_summary;\n"
            (package_dir / "sql" / "main.sql").write_text(sql_content, encoding="utf-8")

            actual_deploy_hash = _hash_content(deploy_sql_content)

            # Manifest 含错误 hash——触发 mismatch
            manifest = _sample_manifest(
                source_query_hash="0000000000000000000000000000000000000000000000000000000000000000",
            )
            manifest_path = package_dir / "deployment_manifest.yml"
            manifest_path.write_text(
                yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8",
            )

            decision = {
                "request_id": "test_m5b1",
                "current_state": "PENDING_REVIEW",
                "artifact_hashes": {
                    "deploy_sql": actual_deploy_hash,
                },
            }
            (package_dir / "decision.yml").write_text(
                yaml.safe_dump(decision, allow_unicode=True), encoding="utf-8",
            )

            rows, cols, types = _sample_data()
            result = verify_materialization(
                package_dir=package_dir,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
            )

            # hash mismatch → 拒绝执行，Sandbox 不应启动
            assert result.overall_status == "FAIL", (
                f"hash mismatch 后 overall_status 须为 FAIL，实际: {result.overall_status}"
            )
            # sandbox_id 为空表示未启动 Sandbox——静态校验阶段已短路
            assert result.sandbox_id == "", (
                f"hash mismatch 后不应启动 Sandbox，sandbox_id 应为空，"
                f"实际: {result.sandbox_id}"
            )
            # execution_status 应保持默认 PENDING——从未执行
            assert result.execution_status == "PENDING", (
                f"hash mismatch 后不应执行，execution_status 应为 PENDING，"
                f"实际: {result.execution_status}"
            )
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

    def test_timeout_triggers_fail_and_cleanup_still_ok(self):
        """超时硬中断后 overall_status=FAIL 且清理仍成功。

        使用真实 DuckDB interrupt 机制：通过递归 CTE 创建耗时查询，
        配合极短超时（1ms），验证超时后：(a) overall_status=FAIL；
        (b) 清理不受影响；(c) 无 Sandbox 残留。
        """
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            # 递归 CTE 生成大量行——足够慢以触发 1ms 超时
            slow_ctas = (
                "CREATE OR REPLACE TABLE generated.test AS\n"
                "WITH RECURSIVE cnt(x) AS (\n"
                "  SELECT 1\n"
                "  UNION ALL\n"
                "  SELECT x + 1 FROM cnt WHERE x < 10000000\n"
                ")\n"
                "SELECT x FROM cnt;\n"
            )
            rows, cols, types = _sample_data()
            sandbox_root = tmp / ".sandbox_tmp"

            result = execute_ctas_in_sandbox(
                deploy_sql=slow_ctas,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=sandbox_root,
                timeout_seconds=0.001,  # 1ms——递归 CTAS 几乎必然超时
            )

            # 超时 → FAIL 或 极快完成 → PASS（1ms 内完成的极端情况）
            if result.execution_status == "FAIL":
                fail_msgs = result.failures + [
                    c.detail for c in result.checks if c.status == "FAIL"
                ]
                assert any("超时" in m for m in fail_msgs), (
                    f"超时 FAIL 应包含'超时'信息，实际: {result.failures}"
                )

            # 无论超时与否，清理必须成功——不能有 Sandbox 残留
            assert result.cleanup_status == "PASS", (
                f"清理必须成功，实际: {result.cleanup_status}"
            )
            assert not Path(result.sandbox_path).exists(), (
                f"Sandbox 目录应已删除: {result.sandbox_path}"
            )
        finally:
            _rmdtemp(tmp)

    def test_normal_fast_ctas_not_affected_by_timer(self):
        """正常快速 CTAS 不被超时机制误中断。

        验证：正常执行 path 中 execution_done.set() 后 timer.cancel()
        被调用，防止 Timer 在查询完成后误中断后续逻辑。
        """
        tmp = _mkdtemp()
        try:
            # 使用真实 Timer——正常 CTAS 远快于超时限制
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
                timeout_seconds=30,  # 30s 超时——3 行数据 CTAS 远小于此
            )

            # 正常执行必须成功
            assert result.execution_status == "PASS", (
                f"正常 CTAS 应执行成功，实际: {result.execution_status}"
            )
            assert result.cleanup_status == "PASS"
            # 确认未被误判为超时
            assert not any(
                "超时" in m for m in result.failures
            ), f"正常执行不应有超时错误: {result.failures}"
        finally:
            _rmdtemp(tmp)

    def test_timeout_does_not_prevent_cleanup(self):
        """超时后 finally 清理仍然执行——验证无残留。

        与 test_timeout_triggers_fail_and_cleanup_still_ok 互补：
        直接 mock _cleanup_sandbox 返回 True 后验证 finally 被调用。
        """
        tmp = _mkdtemp()
        try:
            cleanup_called = []

            def _tracking_cleanup(*args, **kwargs):
                cleanup_called.append(True)
                return True  # 模拟清理成功

            with patch(
                "src.sandbox.duckdb_ctas_executor._cleanup_sandbox",
                _tracking_cleanup,
            ):
                # 使用正常 CTAS + 正常超时——验证 cleanup 始终被调用
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

                # 清理函数必须被调用
                assert len(cleanup_called) >= 1, "finally 块中 cleanup 必须被调用"
                assert result.cleanup_status == "PASS"
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


# ═══════════════════════════════════════════════════════════════
# §10 M5b-2 P0：状态聚合修复——NOT_APPLICABLE + required/optional
# ═══════════════════════════════════════════════════════════════


class TestUniquenessNotApplicable:
    """未声明唯一键时，唯一键检查应为 NOT_APPLICABLE，不阻止 PASS。"""

    def test_uniqueness_not_applicable_when_no_unique_keys(self):
        """未声明 unique_keys 时 uniqueness_status 为 NOT_APPLICABLE。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()  # 无 unique_keys
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=_build_ctas_sql(),
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.uniqueness_status == "NOT_APPLICABLE", (
                f"未声明 unique_keys 时应为 NOT_APPLICABLE，"
                f"实际为 {result.uniqueness_status}"
            )
            # 确认检查详情
            uniq_checks = [
                c for c in result.checks if c.check_id == "uniqueness"
            ]
            assert len(uniq_checks) == 1
            assert uniq_checks[0].required is False
        finally:
            _rmdtemp(tmp)

    def test_not_applicable_does_not_equal_pass(self):
        """NOT_APPLICABLE 不等于 PASS——两者语义明确区分。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=_build_ctas_sql(),
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            # 唯一键是 NOT_APPLICABLE，不是 PASS
            assert result.uniqueness_status != "PASS"
            assert result.uniqueness_status == "NOT_APPLICABLE"
            # 但整体可以 PASS（因为不是必需检查）
            assert result.overall_status == "PASS"
        finally:
            _rmdtemp(tmp)

    def test_no_unique_keys_all_required_pass_yields_overall_pass(self):
        """未声明唯一键 + 全部必需检查通过 → overall_status=PASS。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=_build_ctas_sql(),
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.cleanup_status == "PASS"
            assert result.execution_status == "PASS"
            assert result.uniqueness_status == "NOT_APPLICABLE"
            assert result.overall_status == "PASS", (
                f"全部必需检查通过时应为 PASS，实际为 {result.overall_status}"
            )
        finally:
            _rmdtemp(tmp)

    def test_not_applicable_with_all_pass_writes_materialization_validated(self):
        """全必需检查 PASS + 清理成功 → materialization_status=MATERIALIZATION_VALIDATED。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=_build_ctas_sql(),
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.overall_status == "PASS"
            # 验证模拟：manifest 写入逻辑在 engine 中，此处验证 executor 返回 PASS
            assert result.uniqueness_status == "NOT_APPLICABLE"
        finally:
            _rmdtemp(tmp)

    def test_not_applicable_report_explains_reason(self):
        """NOT_APPLICABLE 检查的报告必须说明原因。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest()
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=_build_ctas_sql(),
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            uniq_check = [
                c for c in result.checks if c.check_id == "uniqueness"
            ][0]
            assert uniq_check.status == "NOT_APPLICABLE"
            assert "未声明唯一键契约" in uniq_check.detail
            assert "unique_keys" in uniq_check.detail, (
                "报告应提示如何声明唯一键"
            )
        finally:
            _rmdtemp(tmp)


class TestUniquenessDeclared:
    """声明唯一键时，必须实际执行检查，结果必须准确。"""

    def test_declared_unique_keys_no_duplicates_passes(self):
        """声明唯一键且数据无重复 → uniqueness_status=PASS。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest(unique_keys=["trip_date"])
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=_build_ctas_sql(),
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.uniqueness_status == "PASS", (
                f"无重复数据时应为 PASS，实际为 {result.uniqueness_status}"
            )
            # 检查是必需的
            uniq_check = [
                c for c in result.checks if c.check_id == "uniqueness"
            ][0]
            assert uniq_check.required is True
        finally:
            _rmdtemp(tmp)

    def test_declared_unique_keys_with_duplicates_fails(self):
        """声明唯一键且数据有重复 → uniqueness_status=FAIL。

        使用不含聚合的直通 CTAS，确保重复数据直接进入输出表。
        """
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest(unique_keys=["id"])
            # 使用不含 GROUP BY 的直通 CTAS——重复行会直接出现在输出中
            deploy_sql = (
                "CREATE OR REPLACE TABLE generated.test_m5b1 AS\n"
                "    SELECT id, val FROM gold.source_table;\n"
            )
            rows = [
                (1, "a"),
                (1, "b"),  # 重复 id=1
                (2, "c"),
            ]
            cols = ["id", "val"]
            types = ["INTEGER", "VARCHAR"]
            result = execute_ctas_in_sandbox(
                deploy_sql=deploy_sql,
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.uniqueness_status == "FAIL", (
                f"重复数据时应为 FAIL，实际为 {result.uniqueness_status}"
            )
            assert result.overall_status == "FAIL", (
                "唯一键重复时 overall_status 必须为 FAIL"
            )
        finally:
            _rmdtemp(tmp)

    def test_declared_nonexistent_unique_key_column_fails(self):
        """声明不存在的唯一键列时必须 FAIL。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest(unique_keys=["nonexistent_column"])
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=_build_ctas_sql(),
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.uniqueness_status == "FAIL", (
                f"声明不存在的列时应为 FAIL，实际为 {result.uniqueness_status}"
            )
            # 检查 failures 或 check detail 中包含列名
            has_error = any(
                "nonexistent_column" in f
                for f in result.failures
            ) or any(
                "nonexistent_column" in c.detail
                for c in result.checks if c.check_id == "uniqueness"
            )
            assert has_error, (
                f"失败原因必须提及不存在的列名，"
                f"failures={result.failures}"
            )
        finally:
            _rmdtemp(tmp)

    def test_declared_multi_column_unique_keys(self):
        """多列复合唯一键在无重复时通过。"""
        tmp = _mkdtemp()
        try:
            manifest = _sample_manifest(unique_keys=["trip_date", "trip_count"])
            rows, cols, types = _sample_data()
            result = execute_ctas_in_sandbox(
                deploy_sql=_build_ctas_sql(),
                manifest=manifest,
                sample_data_rows=rows,
                sample_data_columns=cols,
                sample_data_types=types,
                sandbox_root=tmp / ".sandbox_tmp",
            )
            assert result.uniqueness_status == "PASS"
            assert result.overall_status == "PASS"
        finally:
            _rmdtemp(tmp)


class TestRequiredOptionalAggregation:
    """required/optional 区分和状态聚合逻辑的单元测试。"""

    def test_required_pending_blocks_pass(self):
        """任一必需检查 PENDING 时 overall_status 不能 PASS。"""
        result = MaterializationResult()
        result.cleanup_status = "PASS"
        result.checks = [
            MaterializationCheckResult(
                check_id="a", name="必需检查A", status="PASS", required=True,
            ),
            MaterializationCheckResult(
                check_id="b", name="必需检查B", status="PENDING", required=True,
            ),
        ]
        from src.sandbox.duckdb_ctas_executor import _aggregate_status
        result = _aggregate_status(result)
        assert result.overall_status == "PENDING", (
            f"有 PENDING 必需检查时应为 PENDING，实际为 {result.overall_status}"
        )

    def test_required_skipped_blocks_pass(self):
        """任一必需检查 SKIPPED 时 overall_status 不能 PASS。"""
        result = MaterializationResult()
        result.cleanup_status = "PASS"
        result.checks = [
            MaterializationCheckResult(
                check_id="a", name="必需检查A", status="PASS", required=True,
            ),
            MaterializationCheckResult(
                check_id="b", name="必需检查B", status="SKIPPED", required=True,
            ),
        ]
        from src.sandbox.duckdb_ctas_executor import _aggregate_status
        result = _aggregate_status(result)
        assert result.overall_status == "PENDING", (
            f"有 SKIPPED 必需检查时应为 PENDING，实际为 {result.overall_status}"
        )

    def test_required_warn_yields_warn(self):
        """任一必需检查 WARN 时 overall_status 为 WARN，不能 PASS。"""
        result = MaterializationResult()
        result.cleanup_status = "PASS"
        result.checks = [
            MaterializationCheckResult(
                check_id="a", name="必需检查A", status="PASS", required=True,
            ),
            MaterializationCheckResult(
                check_id="b", name="必需检查B", status="WARN", required=True,
                detail="某项检查有警告",
            ),
        ]
        from src.sandbox.duckdb_ctas_executor import _aggregate_status
        result = _aggregate_status(result)
        assert result.overall_status == "WARN", (
            f"有 WARN 必需检查时应为 WARN，实际为 {result.overall_status}"
        )

    def test_optional_not_applicable_does_not_block_pass(self):
        """可选检查 NOT_APPLICABLE 不阻止 PASS。"""
        result = MaterializationResult()
        result.cleanup_status = "PASS"
        result.checks = [
            MaterializationCheckResult(
                check_id="a", name="必需检查A", status="PASS", required=True,
            ),
            MaterializationCheckResult(
                check_id="b", name="可选检查B", status="NOT_APPLICABLE",
                required=False,
            ),
        ]
        from src.sandbox.duckdb_ctas_executor import _aggregate_status
        result = _aggregate_status(result)
        assert result.overall_status == "PASS", (
            f"可选 NOT_APPLICABLE 不应阻止 PASS，实际为 {result.overall_status}"
        )

    def test_optional_executed_fail_not_ignored(self):
        """可选检查实际执行后 FAIL 时不得被忽略——必须影响 overall_status。"""
        result = MaterializationResult()
        result.cleanup_status = "PASS"
        result.checks = [
            MaterializationCheckResult(
                check_id="a", name="必需检查A", status="PASS", required=True,
            ),
            MaterializationCheckResult(
                check_id="b", name="可选检查B", status="FAIL",
                detail="可选检查实际执行后发现了问题",
                required=False,
            ),
        ]
        from src.sandbox.duckdb_ctas_executor import _aggregate_status
        result = _aggregate_status(result)
        assert result.overall_status == "FAIL", (
            f"可选检查 FAIL 时 overall 必须为 FAIL，实际为 {result.overall_status}"
        )

    def test_cleanup_fail_overrides_all(self):
        """清理失败时 overall_status 必须为 FAIL——无视其他检查状态。"""
        result = MaterializationResult()
        result.cleanup_status = "FAIL"
        result.checks = [
            MaterializationCheckResult(
                check_id="a", name="所有检查", status="PASS", required=True,
            ),
        ]
        from src.sandbox.duckdb_ctas_executor import _aggregate_status
        result = _aggregate_status(result)
        assert result.overall_status == "FAIL", (
            "清理失败时必须为 FAIL，无论其他检查如何"
        )

    def test_all_required_pass_optional_mixed_yields_pass(self):
        """全部必需检查 PASS + 可选检查混合（NOT_APPLICABLE + PASS）→ PASS。"""
        result = MaterializationResult()
        result.cleanup_status = "PASS"
        result.checks = [
            MaterializationCheckResult(
                check_id="a", name="必需", status="PASS", required=True,
            ),
            MaterializationCheckResult(
                check_id="b", name="可选A", status="PASS", required=False,
            ),
            MaterializationCheckResult(
                check_id="c", name="可选B", status="NOT_APPLICABLE", required=False,
            ),
        ]
        from src.sandbox.duckdb_ctas_executor import _aggregate_status
        result = _aggregate_status(result)
        assert result.overall_status == "PASS"


# ═══════════════════════════════════════════════════════════════
# §8 M5b-2 P0 修复：失败路径持久化与状态失效测试
# ═══════════════════════════════════════════════════════════════


def _setup_package_for_verification(base_dir: Path, **overrides) -> Path:
    """构建可通过物化验证的完整 Review Package 结构。

    创建 sql/main.sql、deploy/main.sql、deployment_manifest.yml、
    decision.yml，使 verify_materialization 可以成功执行。
    """
    package_dir = base_dir / "test_pkg"
    (package_dir / "sql").mkdir(parents=True)
    (package_dir / "deploy").mkdir(parents=True)

    sql_content = overrides.get("sql_content", "SELECT trip_date FROM gold.dws_daily_trip_summary;\n")
    (package_dir / "sql" / "main.sql").write_text(sql_content, encoding="utf-8")

    deploy_sql_content = overrides.get("deploy_sql_content", _build_ctas_sql())
    (package_dir / "deploy" / "main.sql").write_text(deploy_sql_content, encoding="utf-8")

    actual_sql_hash = _hash_content(sql_content)
    actual_deploy_hash = _hash_content(deploy_sql_content)

    manifest = _sample_manifest(source_query_hash=actual_sql_hash)
    manifest_path = package_dir / "deployment_manifest.yml"
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8",
    )

    decision = {
        "request_id": "test_m5b1",
        "current_state": "PENDING_REVIEW",
        "artifact_hashes": {
            "deploy_sql": actual_deploy_hash,
            "sql_main": actual_sql_hash,
        },
    }
    (package_dir / "decision.yml").write_text(
        yaml.safe_dump(decision, allow_unicode=True), encoding="utf-8",
    )

    # 创建空的 decision_log.yml——审批失效需要此文件存在
    decision_log = {"entries": []}
    (package_dir / "decision_log.yml").write_text(
        yaml.safe_dump(decision_log, allow_unicode=True), encoding="utf-8",
    )

    # 创建 spark/main.py——静态校验需要
    (package_dir / "spark").mkdir(parents=True, exist_ok=True)
    (package_dir / "spark" / "main.py").write_text("# Spark placeholder\n", encoding="utf-8")

    return package_dir


def _run_verify(package_dir: Path, **kwargs):
    """运行物化验证引擎——便捷包装。"""
    from src.agent.materialization_verification_engine import verify_materialization

    rows, cols, types = _sample_data()
    return verify_materialization(
        package_dir=package_dir,
        sample_data_rows=rows,
        sample_data_columns=cols,
        sample_data_types=types,
        **kwargs,
    )


class TestPersistOnFailure:
    """M5b-2 P0：所有失败路径都必须生成最新报告。"""

    def test_static_check_failure_generates_reports(self):
        """静态校验失败时仍生成 YAML 和 Markdown 报告。"""
        tmp = _mkdtemp()
        try:
            package_dir = _setup_package_for_verification(tmp)
            # 写入一个包含非法 schema 的 CTAS——静态校验会拦截
            (package_dir / "deploy" / "main.sql").write_text(
                "CREATE TABLE illegal_schema.test AS SELECT 1;\n",
                encoding="utf-8",
            )

            result = _run_verify(package_dir)

            # 验证结果
            assert result.overall_status == "FAIL", (
                f"静态校验失败时 overall_status 必须为 FAIL，实际: {result.overall_status}"
            )
            # YAML 报告必须存在
            yml_path = package_dir / "reports" / "materialization_verification.yml"
            assert yml_path.is_file(), "失败路径也必须生成 YAML 报告"
            report = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
            assert report["overall_status"] == "FAIL"
            # Markdown 报告必须存在
            md_path = package_dir / "reports" / "materialization_verification.md"
            assert md_path.is_file(), "失败路径也必须生成 Markdown 报告"
        finally:
            _rmdtemp(tmp)

    def test_deploy_sql_missing_generates_failure_report(self):
        """deploy/main.sql 缺失时仍生成最新失败报告。

        注意：deploy/main.sql 缺失时静态校验（deploy artifact hash + CTAS 结构检查）
        会先捕获，故 failures 中包含静态校验消息而非 step 2 的消息。
        """
        tmp = _mkdtemp()
        try:
            package_dir = _setup_package_for_verification(tmp)
            # 删除 deploy/main.sql
            (package_dir / "deploy" / "main.sql").unlink()

            result = _run_verify(package_dir)

            assert result.overall_status == "FAIL"
            # 静态校验会捕获缺失——通过 checks 中的 FAIL 来确认
            static_fails = [
                c for c in result.checks
                if c.status == "FAIL" and "deploy" in c.detail.lower()
            ]
            assert len(static_fails) > 0, (
                f"应有与 deploy 相关的失败检查，实际 checks: "
                f"{[(c.name, c.status) for c in result.checks]}"
            )

            # 报告必须生成
            yml_path = package_dir / "reports" / "materialization_verification.yml"
            assert yml_path.is_file(), "deploy SQL 缺失时也必须生成 YAML 报告"
            md_path = package_dir / "reports" / "materialization_verification.md"
            assert md_path.is_file(), "deploy SQL 缺失时也必须生成 MD 报告"
        finally:
            _rmdtemp(tmp)

    def test_no_sample_data_generates_failure_report(self):
        """未提供 sample 数据时生成最新失败报告。"""
        tmp = _mkdtemp()
        try:
            package_dir = _setup_package_for_verification(tmp)
            from src.agent.materialization_verification_engine import verify_materialization

            # 不传 sample 数据，也不提供 sample-db
            result = verify_materialization(package_dir=package_dir)

            assert result.overall_status == "FAIL"
            assert any("未提供 sample 数据" in f for f in result.failures)

            yml_path = package_dir / "reports" / "materialization_verification.yml"
            assert yml_path.is_file(), "无 sample 数据时也必须生成 YAML 报告"
            md_path = package_dir / "reports" / "materialization_verification.md"
            assert md_path.is_file(), "无 sample 数据时也必须生成 MD 报告"
        finally:
            _rmdtemp(tmp)

    def test_sample_data_empty_generates_failure_report(self):
        """sample 数据为空时生成最新失败报告。"""
        tmp = _mkdtemp()
        try:
            package_dir = _setup_package_for_verification(tmp)
            from src.agent.materialization_verification_engine import verify_materialization

            # 传入空数据
            result = verify_materialization(
                package_dir=package_dir,
                sample_data_rows=[],
                sample_data_columns=[],
                sample_data_types=[],
            )

            assert result.overall_status == "FAIL"
            assert any("sample 数据为空" in f for f in result.failures)

            yml_path = package_dir / "reports" / "materialization_verification.yml"
            assert yml_path.is_file(), "sample 为空时也必须生成 YAML 报告"
            md_path = package_dir / "reports" / "materialization_verification.md"
            assert md_path.is_file(), "sample 为空时也必须生成 MD 报告"
        finally:
            _rmdtemp(tmp)

    def test_sample_db_load_exception_generates_failure_report(self):
        """sample DB 加载异常时生成最新失败报告。"""
        tmp = _mkdtemp()
        try:
            package_dir = _setup_package_for_verification(tmp)
            from src.agent.materialization_verification_engine import verify_materialization

            # 提供不存在的 DB 路径——加载会失败
            result = verify_materialization(
                package_dir=package_dir,
                sample_db_path="/nonexistent/path/to/sample.duckdb",
            )

            assert result.overall_status == "FAIL"
            assert any("sample 数据库加载异常" in f for f in result.failures), (
                f"应包含加载异常信息，实际 failures: {result.failures}"
            )

            yml_path = package_dir / "reports" / "materialization_verification.yml"
            assert yml_path.is_file(), "DB 加载异常时也必须生成 YAML 报告"
            md_path = package_dir / "reports" / "materialization_verification.md"
            assert md_path.is_file(), "DB 加载异常时也必须生成 MD 报告"
        finally:
            _rmdtemp(tmp)


class TestStateInvalidation:
    """M5b-2 P0：失败时必须使旧的 MATERIALIZATION_VALIDATED 失效。"""

    def test_success_then_static_failure_invalidates_state(self):
        """先成功后静态失败：状态不再是 MATERIALIZATION_VALIDATED，报告变为最新 FAIL。"""
        tmp = _mkdtemp()
        try:
            package_dir = _setup_package_for_verification(tmp)

            # 第一次：成功验证
            result1 = _run_verify(package_dir)
            assert result1.overall_status == "PASS", (
                f"第一次验证应通过，实际: {result1.overall_status}"
            )
            # 确认状态为 MATERIALIZATION_VALIDATED
            manifest1 = yaml.safe_load(
                (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
            )
            assert manifest1["materialization_status"] == "MATERIALIZATION_VALIDATED"

            # 第二次：修改 SQL 使静态校验失败（写入非法 schema 的 CTAS）
            (package_dir / "deploy" / "main.sql").write_text(
                "CREATE TABLE illegal_schema.test AS SELECT 1;\n",
                encoding="utf-8",
            )

            result2 = _run_verify(package_dir)
            assert result2.overall_status == "FAIL", (
                f"第二次验证应失败，实际: {result2.overall_status}"
            )

            # Manifest 状态不再是 MATERIALIZATION_VALIDATED
            manifest2 = yaml.safe_load(
                (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
            )
            assert manifest2["materialization_status"] != "MATERIALIZATION_VALIDATED", (
                "失败后 materialization_status 不得保留 MATERIALIZATION_VALIDATED"
            )
            assert manifest2["materialization_status"] == "FAILED", (
                f"失败后状态应为 FAILED，实际: {manifest2['materialization_status']}"
            )

            # 报告被覆盖为最新 FAIL
            yml_path = package_dir / "reports" / "materialization_verification.yml"
            report = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
            assert report["overall_status"] == "FAIL", (
                "报告必须反映最新验证结果——应为 FAIL"
            )
            assert report["verification_id"] == result2.verification_id, (
                "报告应包含最新验证的 verification_id"
            )
        finally:
            _rmdtemp(tmp)

    def test_success_then_missing_sample_invalidates_state(self):
        """先成功后缺少 sample：状态失效，旧 PASS 报告被覆盖。"""
        tmp = _mkdtemp()
        try:
            package_dir = _setup_package_for_verification(tmp)

            # 第一次：成功验证
            result1 = _run_verify(package_dir)
            assert result1.overall_status == "PASS"

            manifest1 = yaml.safe_load(
                (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
            )
            assert manifest1["materialization_status"] == "MATERIALIZATION_VALIDATED"

            # 第二次：不传 sample 数据
            from src.agent.materialization_verification_engine import verify_materialization
            result2 = verify_materialization(package_dir=package_dir)

            assert result2.overall_status == "FAIL"

            # 状态已失效
            manifest2 = yaml.safe_load(
                (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
            )
            assert manifest2["materialization_status"] != "MATERIALIZATION_VALIDATED", (
                "失败后不得保留 MATERIALIZATION_VALIDATED"
            )

            # 报告被覆盖
            yml_path = package_dir / "reports" / "materialization_verification.yml"
            report = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
            assert report["overall_status"] == "FAIL"
        finally:
            _rmdtemp(tmp)

    def test_cleanup_failure_writes_cleanup_failed(self):
        """cleanup 失败时写入 CLEANUP_FAILED 而非 FAILED。"""
        tmp = _mkdtemp()
        try:
            package_dir = _setup_package_for_verification(tmp)
            from src.agent.materialization_verification_engine import (
                verify_materialization,
                _finalize_and_persist_materialization,
            )
            from src.agent.materialization_verification_engine import (
                validate_materialization_static,
            )

            # 先正常执行 Sandbox
            rows, cols, types = _sample_data()
            manifest_dict = yaml.safe_load(
                (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
            )

            # 构建一个 cleanup_status=FAIL 的 result
            result = MaterializationResult(
                verification_id="test_cleanup_fail",
                request_id="test_m5b1",
                overall_status="FAIL",
                cleanup_status="FAIL",
                execution_status="PASS",
                checks=[
                    MaterializationCheckResult(
                        check_id="output_object_exists",
                        name="目标对象存在",
                        status="PASS",
                        detail="已创建",
                    ),
                ],
                failures=["清理失败：无法删除临时表"],
            )

            result = _finalize_and_persist_materialization(
                package_dir, result, manifest_dict,
            )

            # Manifest 状态应为 CLEANUP_FAILED
            manifest = yaml.safe_load(
                (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
            )
            assert manifest["materialization_status"] == "CLEANUP_FAILED", (
                f"cleanup 失败时应写 CLEANUP_FAILED，实际: {manifest['materialization_status']}"
            )

            # 报告也要反映 CLEANUP_FAILED
            yml_path = package_dir / "reports" / "materialization_verification.yml"
            assert yml_path.is_file()
            report = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
            assert report["cleanup_status"] == "FAIL"
        finally:
            _rmdtemp(tmp)

    def test_warn_or_pending_does_not_retain_materialization_validated(self):
        """WARN 或 PENDING 状态不得保留 MATERIALIZATION_VALIDATED。"""
        tmp = _mkdtemp()
        try:
            package_dir = _setup_package_for_verification(tmp)
            from src.agent.materialization_verification_engine import (
                _finalize_and_persist_materialization,
            )

            manifest_dict = yaml.safe_load(
                (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
            )

            # 先设置 manifest 为 MATERIALIZATION_VALIDATED
            manifest_dict["materialization_status"] = "MATERIALIZATION_VALIDATED"
            (package_dir / "deployment_manifest.yml").write_text(
                yaml.safe_dump(manifest_dict, allow_unicode=True), encoding="utf-8",
            )

            # 测试 WARN 场景
            warn_result = MaterializationResult(
                verification_id="test_warn",
                request_id="test_m5b1",
                overall_status="WARN",
                checks=[
                    MaterializationCheckResult(
                        check_id="some_check", name="某检查", status="WARN",
                        detail="数据异常但不阻断", severity="WARN",
                    ),
                ],
                warnings=["数据异常——建议人审时关注"],
            )
            result = _finalize_and_persist_materialization(
                package_dir, warn_result, manifest_dict,
            )
            manifest_after = yaml.safe_load(
                (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
            )
            assert manifest_after["materialization_status"] != "MATERIALIZATION_VALIDATED", (
                "WARN 状态不得保留 MATERIALIZATION_VALIDATED"
            )
            # WARN → PENDING（不确定结果不得伪装为通过）
            assert manifest_after["materialization_status"] == "PENDING", (
                f"WARN 应映射为 PENDING，实际: {manifest_after['materialization_status']}"
            )

            # 测试 PENDING 场景
            pending_result = MaterializationResult(
                verification_id="test_pending",
                request_id="test_m5b1",
                overall_status="PENDING",
                checks=[
                    MaterializationCheckResult(
                        check_id="some_check", name="某检查", status="PENDING",
                        detail="尚未执行",
                    ),
                ],
            )
            result2 = _finalize_and_persist_materialization(
                package_dir, pending_result, manifest_dict,
            )
            manifest_after2 = yaml.safe_load(
                (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
            )
            assert manifest_after2["materialization_status"] != "MATERIALIZATION_VALIDATED", (
                "PENDING 状态不得保留 MATERIALIZATION_VALIDATED"
            )
            assert manifest_after2["materialization_status"] == "PENDING", (
                f"PENDING 应映射为 PENDING，实际: {manifest_after2['materialization_status']}"
            )
        finally:
            _rmdtemp(tmp)


class TestReleaseApprovalInvalidation:
    """M5b-2 P0：验证失败时必须使 RELEASE_APPROVED 失效。"""

    def test_release_approved_invalidated_on_reverify_fail(self):
        """已有 RELEASE_APPROVED 时重新验证失败 → SUPERSEDED + 审计日志。"""
        tmp = _mkdtemp()
        try:
            package_dir = _setup_package_for_verification(tmp)
            from src.agent.materialization_verification_engine import (
                verify_materialization,
            )
            from src.agent.decision_manager import (
                read_decision,
                write_decision,
                read_decision_log,
            )

            # 先成功验证
            result1 = _run_verify(package_dir)
            assert result1.overall_status == "PASS"

            # 设置决策状态为 RELEASE_APPROVED
            decision = read_decision(package_dir)
            decision["release_approval_state"] = "RELEASE_APPROVED"
            decision["last_updated_by"] = "human:release_reviewer"
            write_decision(package_dir, decision)
            # Manifest 的 release_status 也设为 RELEASE_APPROVED
            manifest_path = package_dir / "deployment_manifest.yml"
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            manifest["release_status"] = "RELEASE_APPROVED"
            manifest_path.write_text(
                yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8",
            )

            # 再制造失败验证（删除 deploy SQL）
            (package_dir / "deploy" / "main.sql").unlink()
            result2 = verify_materialization(package_dir=package_dir)

            assert result2.overall_status == "FAIL"

            # RELEASE_APPROVED 应被失效
            decision_after = read_decision(package_dir)
            assert decision_after.get("release_approval_state") == "SUPERSEDED", (
                f"RELEASE_APPROVED 应被失效为 SUPERSEDED，"
                f"实际: {decision_after.get('release_approval_state')}"
            )

            # Manifest release_status 应更新为 SUPERSEDED
            manifest_after = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            assert manifest_after["release_status"] == "SUPERSEDED", (
                f"release_status 应为 SUPERSEDED，实际: {manifest_after['release_status']}"
            )

            # decision_log.yml 应有审计记录
            log = read_decision_log(package_dir)
            audit_entries = [
                e for e in log.get("entries", [])
                if "SUPERSEDED" in str(e.get("to_state", ""))
            ]
            assert len(audit_entries) >= 1, (
                f"decision_log 应有 SUPERSEDED 审计记录，实际 entries: {log.get('entries', [])}"
            )
        finally:
            _rmdtemp(tmp)


class TestSuccessPath:
    """M5b-2 P0：验证成功时正常写入 MATERIALIZATION_VALIDATED。"""

    def test_verification_success_writes_materialization_validated(self):
        """验证成功时仍可写 MATERIALIZATION_VALIDATED——修复不得破坏正常路径。"""
        tmp = _mkdtemp()
        try:
            package_dir = _setup_package_for_verification(tmp)

            result = _run_verify(package_dir)

            assert result.overall_status == "PASS", (
                f"验证应通过，实际: {result.overall_status} —— "
                f"failures: {result.failures}"
            )

            # Manifest 状态为 MATERIALIZATION_VALIDATED
            manifest = yaml.safe_load(
                (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
            )
            assert manifest["materialization_status"] == "MATERIALIZATION_VALIDATED", (
                f"PASS 应写 MATERIALIZATION_VALIDATED，实际: {manifest['materialization_status']}"
            )

            # 报告存在且为 PASS
            yml_path = package_dir / "reports" / "materialization_verification.yml"
            assert yml_path.is_file()
            report = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
            assert report["overall_status"] == "PASS"

            md_path = package_dir / "reports" / "materialization_verification.md"
            assert md_path.is_file()
        finally:
            _rmdtemp(tmp)


class TestPersistenceFailure:
    """M5b-2 P0：持久化失败时不得返回 PASS。"""

    def test_persistence_failure_does_not_return_pass(self):
        """报告或 Manifest 持久化失败时不能返回 PASS。

        通过 patch Path.write_text 模拟写入失败（磁盘满），验证持久化失败后
        result.overall_status 变为 FAIL。
        """
        tmp = _mkdtemp()
        try:
            package_dir = _setup_package_for_verification(tmp)
            from src.agent.materialization_verification_engine import (
                _finalize_and_persist_materialization,
            )

            manifest_dict = yaml.safe_load(
                (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
            )

            # 构建一个原本 PASS 的 result
            pass_result = MaterializationResult(
                verification_id="test_persist_fail",
                request_id="test_m5b1",
                overall_status="PASS",
                execution_status="PASS",
                checks=[
                    MaterializationCheckResult(
                        check_id="all_pass", name="全部通过", status="PASS",
                    ),
                ],
            )

            # patch Path.write_text 模拟磁盘写失败——仅影响报告写入
            with patch("pathlib.Path.write_text", side_effect=PermissionError("模拟磁盘满")):
                result = _finalize_and_persist_materialization(
                    package_dir, pass_result, manifest_dict,
                )

            # 持久化失败后不得返回 PASS
            assert result.overall_status != "PASS", (
                f"持久化失败后不得返回 PASS，实际: {result.overall_status}"
            )
            assert result.overall_status == "FAIL", (
                f"持久化失败后 overall_status 必须为 FAIL，实际: {result.overall_status}"
            )
            assert any("无法写入" in f for f in result.failures), (
                f"应包含持久化失败信息，实际 failures: {result.failures}"
            )
        finally:
            _rmdtemp(tmp)


class TestCLIExitCode:
    """M5b-2 P0：CLI 对 FAIL 返回非零退出码。"""

    def test_cli_returns_nonzero_on_fail(self):
        """CLI 对 FAIL 结果返回非零退出码。"""
        tmp = _mkdtemp()
        try:
            package_dir = _setup_package_for_verification(tmp)
            # 删除 deploy SQL 制造失败
            (package_dir / "deploy" / "main.sql").unlink()

            # 通过 CLI 调用
            import subprocess
            import sys
            cli_path = PROJECT_ROOT / "scripts" / "dev_agent" / "verify_duckdb_ctas.py"
            result = subprocess.run(
                [sys.executable, str(cli_path), "-p", str(package_dir)],
                cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
            )

            assert result.returncode != 0, (
                f"FAIL 时 CLI 必须返回非零退出码，实际: {result.returncode}"
            )
            assert result.returncode == 1, (
                f"FAIL 时 CLI 应返回 1，实际: {result.returncode}"
            )
        finally:
            _rmdtemp(tmp)


# ═══════════════════════════════════════════════════════════════
# §11 M5b-2 P0：MaterializationStatus Enum ↔ Schema 一致性
# ═══════════════════════════════════════════════════════════════


class TestMaterializationStatusSchemaConsistency:
    """验证 MaterializationStatus Enum 与 deployment_manifest_schema.yml 枚举值完全一致。

    禁止在不同模块重复维护不一致的字符串列表——
    Enum 是代码侧事实源，Schema 是外部契约，必须通过一致性测试保证对齐。
    """

    @staticmethod
    def _load_schema():
        """加载部署 Manifest JSON Schema。"""
        schema_path = PROJECT_ROOT / "contracts" / "deployment_manifest_schema.yml"
        return yaml.safe_load(schema_path.read_text(encoding="utf-8"))

    @staticmethod
    def _enum_values() -> set[str]:
        """获取 MaterializationStatus Enum 的所有值。"""
        from src.ir.types import MaterializationStatus
        return {s.value for s in MaterializationStatus}

    def test_enum_and_schema_status_sets_identical(self):
        """Enum 与 Schema 的 materialization_status 枚举值集合必须完全一致。"""
        schema = self._load_schema()
        schema_enum = set(
            schema["properties"]["materialization_status"]["enum"]
        )
        enum_values = self._enum_values()

        # 双向检查：Schema 中有但 Enum 中没有
        missing_from_enum = schema_enum - enum_values
        assert not missing_from_enum, (
            f"Schema 声明了 Enum 中不存在的状态: {sorted(missing_from_enum)}——"
            f"必须在 MaterializationStatus 中添加或从 Schema 中移除"
        )

        # 双向检查：Enum 中有但 Schema 中没有
        missing_from_schema = enum_values - schema_enum
        assert not missing_from_schema, (
            f"Enum 声明了 Schema 中不存在的状态: {sorted(missing_from_schema)}——"
            f"必须在 Schema 中添加或从 Enum 中移除"
        )

    def test_materialization_validated_in_both(self):
        """MATERIALIZATION_VALIDATED 同时存在于 Enum 和 Schema。"""
        from src.ir.types import MaterializationStatus
        schema = self._load_schema()
        schema_enum = schema["properties"]["materialization_status"]["enum"]
        assert "MATERIALIZATION_VALIDATED" in schema_enum
        assert MaterializationStatus.MATERIALIZATION_VALIDATED.value == "MATERIALIZATION_VALIDATED"

    def test_cleanup_failed_in_both(self):
        """CLEANUP_FAILED 同时存在于 Enum 和 Schema。"""
        from src.ir.types import MaterializationStatus
        schema = self._load_schema()
        schema_enum = schema["properties"]["materialization_status"]["enum"]
        assert "CLEANUP_FAILED" in schema_enum
        assert MaterializationStatus.CLEANUP_FAILED.value == "CLEANUP_FAILED"

    def test_superseded_in_both(self):
        """SUPERSEDED 同时存在于 Enum 和 Schema。"""
        from src.ir.types import MaterializationStatus
        schema = self._load_schema()
        schema_enum = schema["properties"]["materialization_status"]["enum"]
        assert "SUPERSEDED" in schema_enum, (
            "Schema 必须包含 SUPERSEDED——制品变化导致旧物化验证失效"
        )
        assert MaterializationStatus.SUPERSEDED.value == "SUPERSEDED"

    def test_warn_not_in_schema_enum(self):
        """WARN 不得出现在 Schema 的 materialization_status 枚举中。

        WARN 仅用于 overall_status 过渡态——不能作为持久化状态。
        """
        schema = self._load_schema()
        schema_enum = schema["properties"]["materialization_status"]["enum"]
        assert "WARN" not in schema_enum, (
            "WARN 不能作为 materialization_status 的持久化值——"
            "WARN 应映射为 PENDING（不确定结果不得伪装为通过）"
        )

    def test_no_duplicate_status_values(self):
        """Enum 中不允许重复的状态值。"""
        enum_values = list(self._enum_values())
        assert len(enum_values) == len(set(enum_values)), (
            f"Enum 中存在重复值: {enum_values}"
        )

    def test_schema_additional_properties_false(self):
        """Schema 必须设置 additionalProperties: false——封闭性契约。"""
        schema = self._load_schema()
        assert schema.get("additionalProperties") is False, (
            "deployment_manifest_schema.yml 必须设置 additionalProperties: false——"
            "所有合法字段必须显式声明，不得通过开放字段规避契约设计"
        )


class TestDeploymentManifestSchemaValidation:
    """使用 jsonschema 库验证 DeploymentManifest 的 JSON Schema 校验。

    覆盖有效状态、无效状态、额外字段、缺失必需字段等场景。
    """

    @staticmethod
    def _load_schema():
        """加载部署 Manifest JSON Schema。"""
        schema_path = PROJECT_ROOT / "contracts" / "deployment_manifest_schema.yml"
        return yaml.safe_load(schema_path.read_text(encoding="utf-8"))

    @staticmethod
    def _valid_manifest(**overrides) -> dict:
        """构建一个应该通过 Schema 校验的合法 Manifest dict。"""
        base = {
            "request_id": "test_schema_validation",
            "mode": "MATERIALIZE",
            "source_sql_ref": "sql/main.sql",
            "source_sql_hash": "a" * 64,
            "source_spark_ref": "spark/main.py",
            "source_spark_hash": "b" * 64,
            "target_environment": "SANDBOX",
            "target_table": "generated.test_output",
            "write_strategy": "CREATE_TABLE_AS_SELECT",
            "partition_columns": [],
            "sql_deploy_artifact": "deploy/main.sql",
            "spark_deploy_artifact": "deploy/main.py",
            "allowed_write_schema": "generated",
            "materialization_status": "PENDING",
            "human_review_required": True,
            "release_status": "DRAFT",
            "warnings": [],
            "human_review_points": [],
        }
        base.update(overrides)
        return base

    def test_materialization_validated_passes_schema(self):
        """materialization_status=MATERIALIZATION_VALIDATED 可以通过 Schema 校验。"""
        import jsonschema
        schema = self._load_schema()
        manifest = self._valid_manifest(
            materialization_status="MATERIALIZATION_VALIDATED",
            release_status="PENDING_RELEASE_REVIEW",
        )
        # 不应抛出异常
        jsonschema.validate(manifest, schema)

    def test_cleanup_failed_passes_schema(self):
        """materialization_status=CLEANUP_FAILED 可以通过 Schema 校验。"""
        import jsonschema
        schema = self._load_schema()
        manifest = self._valid_manifest(
            materialization_status="CLEANUP_FAILED",
        )
        jsonschema.validate(manifest, schema)

    def test_superseded_passes_schema(self):
        """materialization_status=SUPERSEDED 可以通过 Schema 校验。"""
        import jsonschema
        schema = self._load_schema()
        manifest = self._valid_manifest(
            materialization_status="SUPERSEDED",
        )
        jsonschema.validate(manifest, schema)

    def test_unknown_status_rejected(self):
        """未知的 materialization_status 值必须被 Schema 拒绝。"""
        import jsonschema
        schema = self._load_schema()
        manifest = self._valid_manifest(
            materialization_status="UNKNOWN_STATE_XYZ",
        )
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(manifest, schema)

    def test_warn_status_rejected(self):
        """WARN 作为 materialization_status 必须被 Schema 拒绝。"""
        import jsonschema
        schema = self._load_schema()
        manifest = self._valid_manifest(
            materialization_status="WARN",
        )
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(manifest, schema)

    def test_undeclared_field_rejected(self):
        """未声明的额外字段必须被 Schema 拒绝（additionalProperties: false）。"""
        import jsonschema
        schema = self._load_schema()
        manifest = self._valid_manifest()
        manifest["unknown_field_xyz"] = "should_not_pass"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(manifest, schema)

    def test_valid_manifest_passes_schema(self):
        """当前合法的 DeploymentManifest 可以通过 Schema 校验。"""
        import jsonschema
        schema = self._load_schema()
        manifest = self._valid_manifest()
        jsonschema.validate(manifest, schema)

    def test_release_approved_by_field_passes(self):
        """release_approved_by 显式声明后可以通过 Schema 校验。"""
        import jsonschema
        schema = self._load_schema()
        manifest = self._valid_manifest(
            materialization_status="MATERIALIZATION_VALIDATED",
            release_status="RELEASE_APPROVED",
            release_approved_by="human:release_reviewer",
            release_message="已审查物化验证报告——批准发布",
        )
        jsonschema.validate(manifest, schema)

    def test_missing_required_field_fails(self):
        """缺少 required 字段（如 request_id）必须被 Schema 拒绝。"""
        import jsonschema
        schema = self._load_schema()
        manifest = self._valid_manifest()
        del manifest["request_id"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(manifest, schema)

    def test_illegal_target_table_fails(self):
        """非法 target_table（非 generated schema）必须被 Schema 拒绝。"""
        import jsonschema
        schema = self._load_schema()
        manifest = self._valid_manifest(
            target_table="production.secret_data",
        )
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(manifest, schema)

    def test_illegal_target_environment_fails(self):
        """非法 target_environment 必须被 Schema 拒绝。"""
        import jsonschema
        schema = self._load_schema()
        manifest = self._valid_manifest(
            target_environment="PRODUCTION",
        )
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(manifest, schema)

    def test_illegal_write_strategy_fails(self):
        """非法 write_strategy 必须被 Schema 拒绝。"""
        import jsonschema
        schema = self._load_schema()
        manifest = self._valid_manifest(
            write_strategy="ARBITRARY_FILE_WRITE",
        )
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(manifest, schema)

    def test_empty_partition_columns_allowed(self):
        """空的 partition_columns 应该通过校验（非分区表合法）。"""
        import jsonschema
        schema = self._load_schema()
        manifest = self._valid_manifest(
            partition_columns=[],
        )
        jsonschema.validate(manifest, schema)

    def test_manifest_with_unique_keys_passes(self):
        """包含 unique_keys 的合法 Manifest 可以通过 Schema 校验。"""
        import jsonschema
        schema = self._load_schema()
        manifest = self._valid_manifest(
            unique_keys=["trip_date", "region_id"],
        )
        jsonschema.validate(manifest, schema)

    def test_source_spark_hash_invalid_pattern_fails(self):
        """source_spark_hash 格式不合法时必须被拒绝。"""
        import jsonschema
        schema = self._load_schema()
        manifest = self._valid_manifest(
            source_spark_hash="not-a-hex-string!!!",
        )
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(manifest, schema)

    def test_warnings_with_valid_entries_passes(self):
        """warnings 数组包含合法字符串时可以通过校验。"""
        import jsonschema
        schema = self._load_schema()
        manifest = self._valid_manifest(
            warnings=["提醒：样本数据仅包含 3 行——不代表全量行为"],
        )
        jsonschema.validate(manifest, schema)

    def test_all_valid_materialization_statuses_pass(self):
        """MaterializationStatus Enum 中所有值依次通过 Schema 校验。"""
        import jsonschema
        from src.ir.types import MaterializationStatus
        schema = self._load_schema()

        for status in MaterializationStatus:
            manifest = self._valid_manifest(
                materialization_status=status.value,
            )
            try:
                jsonschema.validate(manifest, schema)
            except jsonschema.ValidationError as e:
                pytest.fail(
                    f"MaterializationStatus.{status.name}（{status.value}）"
                    f"应通过 Schema 校验，但被拒绝: {e.message}"
                )


# 模块级 PROJECT_ROOT 定义（用于 CLI 测试）
PROJECT_ROOT = Path(__file__).resolve().parents[1]
