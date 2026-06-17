"""
测试 sandbox 执行器——DuckDB 只读执行、PySpark 桩。
"""

from __future__ import annotations

import pytest

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="duckdb 未安装")
class TestDuckDBExecutor:
    """DuckDB 只读执行器测试——使用 :memory: 模式"""

    @pytest.fixture
    def conn(self):
        """创建内存 DuckDB 连接并准备测试数据"""
        con = duckdb.connect(":memory:", read_only=False)
        con.execute("CREATE TABLE test_table (id INTEGER, name VARCHAR, value DOUBLE)")
        con.execute("INSERT INTO test_table VALUES (1, 'alpha', 10.5)")
        con.execute("INSERT INTO test_table VALUES (2, 'beta', 20.3)")
        con.execute("INSERT INTO test_table VALUES (3, 'gamma', 30.7)")
        yield con
        con.close()

    def test_execute_select(self, conn):
        from src.sandbox.executor import execute_sql
        result = execute_sql(conn, "SELECT * FROM test_table", source_table="test_table")
        assert result.row_count == 3
        assert result.columns == ["id", "name", "value"]
        assert result.error is None
        assert result.execution_time_ms > 0
        assert result.source_table == "test_table"

    def test_execute_with_where(self, conn):
        from src.sandbox.executor import execute_sql
        result = execute_sql(conn, "SELECT * FROM test_table WHERE id = 1")
        assert result.row_count == 1

    def test_execute_syntax_error(self, conn):
        from src.sandbox.executor import execute_sql
        result = execute_sql(conn, "SELECT * FROM nonexistent_table")
        assert result.error is not None
        assert result.row_count == 0

    def test_execute_result_signature(self, conn):
        from src.sandbox.executor import execute_sql
        r1 = execute_sql(conn, "SELECT * FROM test_table")
        r2 = execute_sql(conn, "SELECT * FROM test_table")
        # 结果签名应基于结构和行数一致
        assert r1.row_count == r2.row_count
        assert r1.columns == r2.columns
        # column_types 可能因 DuckDB 版本不同返回不同格式，但同版本应一致
        assert r1.column_types == r2.column_types

    def test_execute_empty_result(self, conn):
        from src.sandbox.executor import execute_sql
        result = execute_sql(conn, "SELECT * FROM test_table WHERE id = 999")
        assert result.row_count == 0
        assert result.error is None

    def test_execute_count(self, conn):
        from src.sandbox.executor import execute_sql
        result = execute_sql(conn, "SELECT COUNT(*) AS cnt FROM test_table")
        assert result.row_count == 1
        assert result.rows[0][0] == 3

    def test_timeout_disabled(self, conn):
        """timeout_seconds=0 时禁用超时"""
        from src.sandbox.executor import execute_sql
        result = execute_sql(conn, "SELECT * FROM test_table", timeout_seconds=0)
        assert result.error is None
        assert result.row_count == 3


class TestSparkExecutor:
    """PySpark 执行器桩测试"""

    def test_no_spark_session_returns_skipped(self):
        from src.sandbox.spark_executor import execute_spark_dsl
        result = execute_spark_dsl("spark.table('t')")
        assert result.error is not None
        assert "尚未实现" in result.error

    def test_with_spark_session_returns_not_implemented(self):
        """即使传入 spark session，Phase 1 也应返回 not implemented"""
        from src.sandbox.spark_executor import execute_spark_dsl
        # 使用任意非 None 对象模拟 spark session
        result = execute_spark_dsl("spark.table('t')", spark_session=object())
        assert result.error is not None
        assert "尚未实现" in result.error


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="duckdb 未安装")
class TestSandboxForbiddenKeywords:
    """统一禁止关键字来源——确保沙箱拦截所有 19 个危险关键字"""

    @pytest.fixture
    def conn(self):
        con = duckdb.connect(":memory:", read_only=False)
        con.execute("CREATE TABLE t (id INTEGER)")
        yield con
        con.close()

    # ── execute_sql_sample（安全入口）测试 ──

    def test_sample_replace_rejected(self, conn):
        """REPLACE 被沙箱 sample run 拦截"""
        from src.sandbox.executor import execute_sql_sample
        result = execute_sql_sample(conn, "REPLACE INTO t VALUES (1)")
        assert result.error is not None
        assert "REPLACE" in result.error

    def test_sample_rename_rejected(self, conn):
        """RENAME 被沙箱 sample run 拦截（前缀或关键字检查任一命中即拦截）"""
        from src.sandbox.executor import execute_sql_sample
        result = execute_sql_sample(conn, "ALTER TABLE t RENAME TO t2")
        assert result.error is not None
        # ALTER 被 ALLOWED_PREFIXES 拦截在前，或 RENAME 被 FORBIDDEN_KEYWORDS 拦截在后
        assert "RENAME" in result.error or "ALTER" in result.error

    def test_sample_grant_rejected(self, conn):
        """GRANT 被沙箱 sample run 拦截"""
        from src.sandbox.executor import execute_sql_sample
        result = execute_sql_sample(conn, "GRANT SELECT ON t TO user1")
        assert result.error is not None
        assert "GRANT" in result.error

    def test_sample_revoke_rejected(self, conn):
        """REVOKE 被沙箱 sample run 拦截"""
        from src.sandbox.executor import execute_sql_sample
        result = execute_sql_sample(conn, "REVOKE SELECT ON t FROM user1")
        assert result.error is not None
        assert "REVOKE" in result.error

    def test_sample_detach_rejected(self, conn):
        """DETACH 被沙箱 sample run 拦截"""
        from src.sandbox.executor import execute_sql_sample
        result = execute_sql_sample(conn, "DETACH DATABASE mydb")
        assert result.error is not None
        assert "DETACH" in result.error

    def test_sample_import_rejected(self, conn):
        """IMPORT 被沙箱 sample run 拦截"""
        from src.sandbox.executor import execute_sql_sample
        result = execute_sql_sample(conn, "IMPORT DATABASE 'backup'")
        assert result.error is not None
        assert "IMPORT" in result.error

    def test_sample_valid_select_passes(self, conn):
        """正常 SELECT 仍可执行"""
        from src.sandbox.executor import execute_sql_sample
        result = execute_sql_sample(conn, "SELECT * FROM t")
        assert result.error is None
        assert result.row_count == 0

    # ── execute_sql（防御纵深）测试 ──

    def test_raw_execute_replace_rejected(self, conn):
        """直接调用 execute_sql 也拦截 REPLACE（防御纵深）"""
        from src.sandbox.executor import execute_sql
        result = execute_sql(conn, "REPLACE INTO t VALUES (1)")
        assert result.error is not None
        assert "REPLACE" in result.error

    def test_raw_execute_grant_rejected(self, conn):
        """直接调用 execute_sql 也拦截 GRANT（防御纵深）"""
        from src.sandbox.executor import execute_sql
        result = execute_sql(conn, "GRANT SELECT ON t TO user1")
        assert result.error is not None
        assert "GRANT" in result.error

    def test_raw_execute_detach_rejected(self, conn):
        """直接调用 execute_sql 也拦截 DETACH（防御纵深）"""
        from src.sandbox.executor import execute_sql
        result = execute_sql(conn, "DETACH DATABASE mydb")
        assert result.error is not None
        assert "DETACH" in result.error

    def test_raw_execute_select_passes(self, conn):
        """直接调用 execute_sql 正常 SELECT 仍可执行"""
        from src.sandbox.executor import execute_sql
        result = execute_sql(conn, "SELECT * FROM t")
        assert result.error is None
        assert result.row_count == 0
