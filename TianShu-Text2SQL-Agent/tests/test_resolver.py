from src.resolver import TianShuResolver


class _FakeResult:
    def __init__(self, rows, description=None):
        self._rows = rows
        self.description = description or []

    def fetchall(self):
        return self._rows


class _FakeConnection:
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
