"""
TianShu Resolver 测试。

覆盖：契约加载、DuckDB 连接、表/指标发现、SQL 执行封装。
"""

from src.ir import SQLResult
from src.resolver import TianShuResolver


class _FakeResult:
    def __init__(self, rows, description=None):
        self._rows = rows
        self.description = description or []

    def fetchall(self):
        return self._rows


class _FakeConnection:
    """模拟 DuckDB 连接，用于 discover_metrics 测试"""
    def execute(self, sql):
        assert "meta.metric_definitions" in sql
        rows = [
            (
                "parking_violation_count",
                "罚单量",
                "gold.dws_daily_parking_summary",
                "sum(violation_count)",
                "date_key",
                "统计停车违章罚单数量",
                "approved",
            )
        ]
        description = [
            ("metric_name",),
            ("metric_name_zh",),
            ("source_table",),
            ("calculation_sql",),
            ("time_key",),
            ("business_meaning",),
            ("audit_status",),
        ]
        return _FakeResult(rows, description)


class _ExecuteFakeConnection:
    """
    模拟 DuckDB 连接，用于 execute_sql 测试。

    记录执行的 SQL 和查询结果，不依赖真实 DuckDB。
    """
    def __init__(self, rows=None, columns=None, column_types=None):
        self._rows = rows or []
        self._columns = columns or []
        self._column_types = column_types or []
        self.last_sql = ""

    def execute(self, sql):
        self.last_sql = sql
        return _ExecResult(self._rows, self._columns, self._column_types)


class _ExecResult:
    """模拟 DuckDB 查询结果"""
    def __init__(self, rows, columns, column_types):
        self.description = [
            (col, typ) for col, typ in zip(columns, column_types)
        ]
        self._rows = rows

    def fetchall(self):
        return self._rows


# ═══════════════════════════════════════════════════════════════
# 指标发现
# ═══════════════════════════════════════════════════════════════


def test_discover_metrics_parses_runtime_metric_table_shape():
    """运行库指标表应按列名解析，不依赖旧列顺序"""
    resolver = TianShuResolver()
    resolver._conn = _FakeConnection()

    metrics = resolver.discover_metrics()

    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.name == "parking_violation_count"
    assert metric.zh_name == "罚单量"
    assert metric.base_table == "gold.dws_daily_parking_summary"
    assert metric.aggregation == "sum(violation_count)"
    assert metric.domain == "violation"
    assert metric.g3_available is True


# ═══════════════════════════════════════════════════════════════
# A-2：execute_sql() 封装 _conn
# ═══════════════════════════════════════════════════════════════


class TestResolverExecuteSQL:
    """A-2：Resolver.execute_sql() 封装 DuckDB 连接"""

    def test_returns_error_result_when_no_connection(self):
        """_conn 为 None 时，返回带错误信息的 SQLResult，不抛异常"""
        resolver = TianShuResolver()
        resolver._conn = None

        result = resolver.execute_sql("SELECT 1")

        assert isinstance(result, SQLResult)
        assert result.error is not None
        assert "未连接" in result.error
        assert result.sql == "SELECT 1"
        # 连接不可用时不应抛异常，应优雅降级
        assert result.row_count == 0
        assert result.columns == []

    def test_delegates_to_executor_when_connected(self):
        """_conn 可用时，委托给 executor.execute_sql() 执行查询"""
        resolver = TianShuResolver()
        fake_conn = _ExecuteFakeConnection(
            rows=[(1,)],
            columns=["result"],
            column_types=["INTEGER"],
        )
        resolver._conn = fake_conn

        result = resolver.execute_sql(
            "SELECT 1 AS result",
            timeout_seconds=10,
            source_table="gold.test",
        )

        assert isinstance(result, SQLResult)
        assert result.error is None
        assert result.row_count == 1
        assert result.columns == ["result"]
        assert result.column_types == ["INTEGER"]
        assert result.sql == "SELECT 1 AS result"
        # 验证 SQL 确实被传递到连接层
        assert fake_conn.last_sql == "SELECT 1 AS result"

    def test_agent_no_longer_accesses_conn_directly(self):
        """agent.py 不再直接访问 _resolver._conn（封装验证）"""
        from pathlib import Path

        agent_path = Path(__file__).parent.parent / "src" / "agent.py"
        source = agent_path.read_text(encoding="utf-8")

        # agent.py 不应包含直接访问 _conn 的代码
        assert "._conn" not in source, (
            "A-2 修复后 agent.py 不应直接访问 resolver._conn，"
            "应通过 resolver.execute_sql() 执行查询"
        )

    def test_execute_sql_preserves_source_table(self):
        """source_table 参数应正确传递到结果中"""
        resolver = TianShuResolver()
        fake_conn = _ExecuteFakeConnection(
            rows=[(100,)],
            columns=["cnt"],
            column_types=["BIGINT"],
        )
        resolver._conn = fake_conn

        result = resolver.execute_sql(
            "SELECT COUNT(*) AS cnt FROM gold.dws_daily_trip_summary",
            source_table="gold.dws_daily_trip_summary",
        )

        assert result.source_table == "gold.dws_daily_trip_summary"

    def test_execute_sql_handles_executor_errors_gracefully(self):
        """executor 层的异常应被正确处理，不向上传播"""
        resolver = TianShuResolver()

        class _ErrorConnection:
            def execute(self, sql):
                raise RuntimeError("DuckDB 内部错误：磁盘空间不足")

        resolver._conn = _ErrorConnection()

        # 不应抛出异常，应返回带 error 的 SQLResult
        result = resolver.execute_sql("SELECT * FROM huge_table")
        assert isinstance(result, SQLResult)
        assert result.error is not None
        assert "DuckDB 内部错误" in result.error


# ═══════════════════════════════════════════════════════════════
# Agent 级别的 A-2 集成测试
# ═══════════════════════════════════════════════════════════════


class TestAgentUsesResolverExecuteSQL:
    """A-2：Agent.ask() 通过 resolver.execute_sql() 执行查询"""

    def test_rule_mode_agent_executes_via_resolver(self):
        """规则模式下 Agent 应通过 resolver 层执行 SQL"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天有多少行程？")

        # 正常回答：全链路通过
        assert response.clarification_needed is False
        assert response.refusal is False
        assert response.result is not None
        assert response.result.sql.startswith("SELECT")
        # source_table 应被正确设置为 plan 的主表
        assert response.result.source_table is not None

