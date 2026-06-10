"""
Harness 门禁集成测试。

验证 harness/ 下的检查脚本可以被导入和调用。
"""

import sys
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestHarnessConfig:
    """Harness 配置加载测试"""

    def test_load_config(self):
        """测试加载 Harness 配置"""
        from harness.config import load_harness_config, HarnessConfig

        config = load_harness_config("config/tianshu_target.yml")
        assert isinstance(config, HarnessConfig)
        assert config.tianshu_root.exists()


class TestSQLReadonlyCheck:
    """SQL 只读检查测试"""

    def test_forbidden_keywords_loaded(self):
        """测试禁止关键字已加载"""
        from harness.config import load_harness_config
        from harness.checks.check_sql_readonly import load_forbidden_keywords

        harness_config = load_harness_config("config/tianshu_target.yml")
        keywords = load_forbidden_keywords(harness_config.contracts_path, {})

        # 应该至少包含基本的 DML/DDL 关键字
        assert "INSERT" in keywords
        assert "DELETE" in keywords
        assert "DROP" in keywords

    def test_sql_extraction_from_evals(self):
        """测试从 evals/ 提取 SQL"""
        from harness.checks.check_sql_readonly import scan_yaml_for_sql
        from pathlib import Path

        # 当前 evals/ 目录为空，应该返回空列表
        entries = scan_yaml_for_sql(Path("evals"))
        assert isinstance(entries, list)

    def test_clean_sql_passes(self):
        """测试干净的 SELECT 通过检查"""
        from harness.checks.check_sql_readonly import check_sql_readonly

        # 由于 evals/ 为空，应该返回空结果
        results = check_sql_readonly(Path("evals"), ["INSERT", "DELETE", "DROP"])
        assert results["total_count"] == 0
        assert len(results["violations"]) == 0


class TestIRSchemaCheck:
    """IR 数据结构检查测试"""

    def test_ir_dataclasses_valid(self):
        """测试 IR 数据类检查通过"""
        from harness.checks.check_ir_schema import check_ir_dataclasses

        results = check_ir_dataclasses()
        assert results["fail_count"] == 0
        assert results["pass_count"] > 0


class TestLayerComplianceCheck:
    """层级合规检查测试"""

    def test_table_extraction(self):
        """测试 SQL 表引用提取"""
        from harness.checks.check_layer_compliance import extract_table_references

        sql = "SELECT * FROM gold.dws_daily_trip_summary WHERE trip_date >= DATE '2026-01-01'"
        tables = extract_table_references(sql)
        assert "gold.dws_daily_trip_summary" in tables
        assert len(tables) == 1

    def test_table_extraction_with_join(self):
        """测试 JOIN 语句中的表提取"""
        from harness.checks.check_layer_compliance import extract_table_references

        sql = (
            "SELECT t.*, d.date "
            "FROM gold.fact_trips t "
            "INNER JOIN gold.dim_date d ON d.date_key = t.pickup_date_key"
        )
        tables = extract_table_references(sql)
        assert "gold.fact_trips" in tables
        assert "gold.dim_date" in tables


class TestMetricCheck:
    """指标注册检查测试"""

    def test_registered_metrics_loaded(self):
        """测试已注册指标加载"""
        from harness.config import load_harness_config
        from harness.checks.check_metric_registered import load_registered_metrics

        harness_config = load_harness_config("config/tianshu_target.yml")
        metrics = load_registered_metrics(harness_config.contracts_path)

        # 应至少包含基本指标
        assert "trip_count" in metrics
        assert "total_fare_amount" in metrics
        assert "parking_violation_count" in metrics
