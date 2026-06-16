"""MetricCatalog 单元测试。

覆盖：加载、校验、查询、导出、向后兼容。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.resolver import MetricInfo
from src.metric_catalog import MetricCatalog


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

def _sample_metrics() -> list[MetricInfo]:
    """构造覆盖全部 G3 域的指标目录（含同义词/关键词/别名）。"""
    return [
        MetricInfo(
            name="trip_count", zh_name="行程量", domain="traffic",
            aggregation="COUNT(*)", base_table="gold.dws_daily_trip_summary",
            unit="次", g3_available=True,
            synonyms=["行程数", "出行量", "订单数"],
            keyword_groups=[("行程",), ("出行",), ("订单",)],
            aliases=["trips"], description="行程总数", caution="",
            source="duckdb",
        ),
        MetricInfo(
            name="total_fare_amount", zh_name="基础车费总额", domain="traffic",
            aggregation="SUM(total_fare_amount)",
            base_table="gold.dws_daily_trip_summary",
            unit="美元", g3_available=True,
            synonyms=["车费总额", "车费收入", "车费金额"],
            keyword_groups=[("车费", "总额"), ("车费", "收入")],
            aliases=[], description="总车费收入", caution="不包含 FHV/HV",
            source="duckdb",
        ),
        MetricInfo(
            name="standard_fine_total", zh_name="标准罚款总额", domain="violation",
            aggregation="SUM(standard_fine_total)",
            base_table="gold.dws_daily_parking_summary",
            unit="美元", g3_available=True,
            synonyms=["罚款总额", "标准罚款", "罚单金额"],
            keyword_groups=[("罚款", "总额"), ("罚金", "总额")],
            aliases=[], description="标准罚款总额", caution="",
            source="duckdb",
        ),
        MetricInfo(
            name="persons_injured", zh_name="受伤人数", domain="safety",
            aggregation="SUM(persons_injured)",
            base_table="gold.dws_daily_crash_summary",
            unit="人", g3_available=True,
            synonyms=["受伤人口", "伤者人数"],
            keyword_groups=[("受伤",), ("伤者",)],
            aliases=[], description="受伤人数", caution="",
            source="duckdb",
        ),
        MetricInfo(
            name="driver_application_count", zh_name="司机申请量", domain="supply",
            aggregation="COUNT(*)", base_table="gold.fact_driver_applications",
            unit="次", g3_available=False,  # 非 G3 指标
            synonyms=[], keyword_groups=[], aliases=[],
            description="", caution="", source="duckdb",
        ),
    ]


@pytest.fixture
def sample_metrics() -> list[MetricInfo]:
    return _sample_metrics()


@pytest.fixture
def catalog(sample_metrics: list[MetricInfo]) -> MetricCatalog:
    return MetricCatalog(sample_metrics, _source="test")


# ═══════════════════════════════════════════════════════════════
# 加载测试
# ═══════════════════════════════════════════════════════════════

def test_from_duckdb_marks_source():
    """from_duckdb 方法应标记 source='duckdb'。"""
    cat = MetricCatalog.from_duckdb(_sample_metrics())
    assert cat._source == "duckdb"


def test_list_g3_only_returns_available(catalog: MetricCatalog):
    """list_g3_metrics 应仅返回 g3_available=True 的指标。"""
    g3 = catalog.list_g3_metrics()
    assert len(g3) == 4  # 4 个 G3，1 个非 G3
    assert all(m.g3_available for m in g3)
    assert not any(m.name == "driver_application_count" for m in g3)


def test_list_all_returns_all(catalog: MetricCatalog):
    """list_all 应返回全部指标（含非 G3）。"""
    assert len(catalog.list_all()) == 5


def test_get_metric_by_name(catalog: MetricCatalog):
    """按英文名精确查找。"""
    m = catalog.get_metric("trip_count")
    assert m is not None
    assert m.zh_name == "行程量"

    assert catalog.get_metric("nonexistent") is None


def test_list_by_domain(catalog: MetricCatalog):
    """按域过滤。"""
    traffic = catalog.list_by_domain("traffic")
    assert len(traffic) == 2
    assert {m.name for m in traffic} == {"trip_count", "total_fare_amount"}


def test_count(catalog: MetricCatalog):
    """__len__ 应返回总指标数。"""
    assert len(catalog) == 5


# ═══════════════════════════════════════════════════════════════
# 校验测试
# ═══════════════════════════════════════════════════════════════

def test_validate_clean_catalog_returns_empty(catalog: MetricCatalog):
    """合法目录应无校验错误。"""
    assert catalog.validate() == []


def test_validate_duplicate_names():
    """重复指标名应被检测。"""
    metrics = [
        MetricInfo("trip_count", "", "", "", "", "", True),
        MetricInfo("trip_count", "", "", "", "", "", True),
    ]
    cat = MetricCatalog(metrics)
    errors = cat.validate()
    assert any("重复" in e for e in errors)


def test_validate_g3_missing_base_table():
    """G3 可用但 base_table 为空应报错。"""
    metrics = [
        MetricInfo("bad_metric", "", "", "", "", "", True),
    ]
    cat = MetricCatalog(metrics)
    errors = cat.validate()
    assert any("base_table 为空" in e for e in errors)


def test_validate_synonym_contains_zh_name():
    """同义词包含中文名应报错（会导致优先级混乱）。"""
    metrics = [
        MetricInfo("trip_count", "行程量", "", "", "", "", True,
                   synonyms=["行程量"],  # zh_name == synonym
                   ),
    ]
    cat = MetricCatalog(metrics)
    errors = cat.validate()
    assert any("zh_name" in e for e in errors)


def test_validate_invalid_domain():
    """非法 domain 应被检测。"""
    metrics = [
        MetricInfo("test", "", "invalid_domain", "", "", "", True),
    ]
    cat = MetricCatalog(metrics)
    errors = cat.validate()
    assert any("domain" in e for e in errors)


def test_validate_g3_missing_aggregation():
    """G3 可用但 aggregation 为空应报错。"""
    metrics = [
        MetricInfo("bad_metric", "", "traffic", "", "gold.dws_test", "", True),
    ]
    cat = MetricCatalog(metrics)
    errors = cat.validate()
    assert any("aggregation 为空" in e for e in errors)


# ═══════════════════════════════════════════════════════════════
# 导出/快照测试
# ═══════════════════════════════════════════════════════════════

def test_export_snapshot_roundtrip(catalog: MetricCatalog):
    """导出快照后可重新导入，指标名应一致。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "snapshot.json"
        catalog.export_snapshot(str(path))

        assert path.exists()

        reloaded = MetricCatalog.from_snapshot(str(path))
        original_names = {m.name for m in catalog.list_g3_metrics()}
        reloaded_names = {m.name for m in reloaded.list_g3_metrics()}
        assert original_names == reloaded_names


def test_export_snapshot_contains_synonyms_and_keywords(catalog: MetricCatalog):
    """快照应包含同义词和关键词字段。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "snapshot.json"
        catalog.export_snapshot(str(path))

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        trip = next(item for item in data if item["metric_name"] == "trip_count")
        assert "行程数" in trip["synonyms"]
        assert ["行程"] in trip["keywords"]


def test_snapshot_loads_keyword_groups_as_tuples():
    """快照中的 keywords 列表应被加载为 keyword_groups。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "snapshot.json"
        catalog = MetricCatalog(_sample_metrics())
        catalog.export_snapshot(str(path))
        reloaded = MetricCatalog.from_snapshot(str(path))

        trip = reloaded.get_metric("trip_count")
        assert trip is not None
        assert len(trip.keyword_groups) > 0
        # 第一个关键词组应为 tuple
        assert isinstance(trip.keyword_groups[0], tuple)
        assert trip.keyword_groups[0] == ("行程",)


def test_snapshot_source_marked():
    """从快照加载的指标应标记 source='snapshot'。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "snapshot.json"
        catalog = MetricCatalog(_sample_metrics())
        catalog.export_snapshot(str(path))
        reloaded = MetricCatalog.from_snapshot(str(path))

        for m in reloaded.list_g3_metrics():
            assert m.source == "snapshot"


# ═══════════════════════════════════════════════════════════════
# 边界情况测试
# ═══════════════════════════════════════════════════════════════

def test_empty_catalog():
    """空指标目录应正常工作。"""
    cat = MetricCatalog([])
    assert len(cat) == 0
    assert cat.list_g3_metrics() == []
    assert cat.get_metric("anything") is None
    assert cat.validate() == []


def test_repr(catalog: MetricCatalog):
    """__repr__ 应包含关键信息。"""
    r = repr(catalog)
    assert "MetricCatalog" in r
    assert "g3=4" in r
    assert "test" in r
