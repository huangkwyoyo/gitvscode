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
