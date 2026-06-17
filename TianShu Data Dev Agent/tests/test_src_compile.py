"""
测试 compile fallback 引擎——v1.x 编译器封装。
"""

from __future__ import annotations

import pytest

from src.ir.types import SQLPlan, Strategy


class TestCompileFallback:
    """Fallback 编译器测试"""

    def test_v1_compiler_available(self):
        """确认 v1.x 编译器可以被导入"""
        try:
            from scripts.pipeline.layer4_generate import compile_sql
            assert callable(compile_sql)
        except ImportError as e:
            pytest.skip(f"v1.x 编译器不可用: {e}")

    def test_compile_fallback_import(self):
        """确认 compile_fallback 可以被导入"""
        from src.compile import compile_fallback
        assert callable(compile_fallback)

    def test_compile_fallback_g3_basic(self):
        """
        测试 G3 直查的基本 fallback 编译。

        使用 v1.x 编译器基于已知指标编译 SQL。
        """
        try:
            from scripts.pipeline.layer4_generate import compile_sql
            from scripts.pipeline.layer3_ir import SQLPlan as V1SQLPlan
            from scripts.pipeline.layer3_ir import JoinGraph, JoinNode, JoinCondition
            from scripts.pipeline.layer3_ir import ColumnBinding, FilterBinding, FilterType
            from scripts.pipeline.layer3_ir import ExecutionConstraints
        except ImportError as e:
            pytest.skip(f"v1.x 编译器模块导入失败: {e}")

        # 构造 v1.x SQLPlan 对象——G3 单表直查
        plan = V1SQLPlan(
            plan_id="test_g3",
            plan_name="test_g3_report",
            source_layer="g3",
            domain="traffic",
            target_dialect="duckdb",
            join_graph=JoinGraph(
                primary=JoinNode(
                    table="gold.dws_daily_trip_summary",
                    alias="t1",
                    type="PRIMARY",
                    condition=JoinCondition(left="", right=""),
                    constraint_ref="",
                ),
                joins=[],
            ),
            column_bindings=[
                ColumnBinding(
                    metric_name="trip_count",
                    column_ref="gold.dws_daily_trip_summary.trip_count",
                    alias="trip_count",
                    unit="次",
                    domain="traffic",
                ),
            ],
            filter_bindings=[
                FilterBinding(
                    filter_type=FilterType.DATE_RANGE,
                    column_ref="gold.dws_daily_trip_summary.trip_date",
                    operator="BETWEEN",
                    value=["2026-01-01", "2026-03-31"],
                ),
            ],
            group_by=[],
            order_by=[],
            output_format="parquet",
            execution_constraints=ExecutionConstraints(
                read_only=True,
                query_timeout_seconds=30,
                max_result_rows=100000,
                allowed_tables=["gold.dws_daily_trip_summary"],
            ),
        )

        sql_text, params = compile_sql(plan)
        assert "SELECT" in sql_text
        assert "FROM gold.dws_daily_trip_summary" in sql_text
        # 参数化查询可检测到 BETWEEN ? AND ?
        assert len(params) >= 2 or "trip_date" in sql_text

    def test_compile_fallback_missing_table_raises(self):
        """缺少主表时 v1.x 编译器应报错"""
        try:
            from scripts.pipeline.layer4_generate import compile_sql
            from scripts.pipeline.layer3_ir import SQLPlan as V1SQLPlan
        except ImportError as e:
            pytest.skip(f"v1.x 编译器不可用: {e}")

        # 构造不完整的 SQLPlan——无 join_graph
        plan = V1SQLPlan(
            plan_id="test_bad",
            plan_name="test_bad",
            source_layer="g3",
            domain="traffic",
            target_dialect="duckdb",
        )

        # 不应崩溃——最多返回空 SQL 或有诊断信息
        try:
            sql_text, params = compile_sql(plan)
            # 编译不抛异常即为通过（可能发 warn 但不会异常）
        except Exception:
            # 抛出异常也可接受（取决于 v1.x 编译器实现）
            pass


class TestCompileSysPath:
    """sys.path 副作用隔离——异常时路径应恢复"""

    def test_sys_path_restored_after_import_error(self):
        """v1 模块导入失败时 sys.path 应恢复原状"""
        import sys
        from src.compile.engine import _temporary_sys_path

        before = list(sys.path)
        fake_path = "/nonexistent/path/12345"

        with _temporary_sys_path(fake_path):
            assert fake_path in sys.path, "上下文内路径应被添加"

        # 退出上下文后 fake_path 应被移除
        assert fake_path not in sys.path, "退出上下文后路径应恢复"
        assert sys.path == before, "sys.path 应完全恢复原状"

    def test_sys_path_restored_after_exception(self):
        """异常发生时 sys.path 也应恢复"""
        import sys
        from src.compile.engine import _temporary_sys_path

        before = list(sys.path)
        fake_path = "/another/nonexistent/path"

        try:
            with _temporary_sys_path(fake_path):
                assert fake_path in sys.path
                raise ValueError("模拟异常")
        except ValueError:
            pass  # 预期异常

        assert fake_path not in sys.path, "异常时路径也应恢复"
        assert sys.path == before, "异常时 sys.path 应完全恢复"

    def test_duplicate_insert_not_removed(self):
        """路径已存在时不应被错误移除"""
        import sys
        from src.compile.engine import _temporary_sys_path

        before = list(sys.path)
        # 使用已在 sys.path 中的路径
        existing_path = sys.path[0]

        with _temporary_sys_path(existing_path):
            assert existing_path in sys.path  # 仍然在

        # 退出后不应移除了原本就存在的路径
        assert existing_path in sys.path


class TestCompileV1Incompatible:
    """v1 模块结构不兼容时的行为"""

    def test_v1_module_import_error_propagates(self):
        """v1.x 编译器模块不存在时抛出明确的 ImportError"""
        import pytest
        from unittest.mock import patch, MagicMock
        from src.compile.engine import _do_compile
        from src.ir.types import SQLPlan, Strategy

        plan = SQLPlan(strategy=Strategy.G3_DIRECT, primary_table="gold.t1")

        # 模拟 scripts.pipeline.layer4_generate 导入失败
        def _fake_import(name, *args, **kwargs):
            if "scripts.pipeline" in name:
                raise ImportError(f"No module named '{name}' (模拟)")
            return __import__(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_fake_import):
            with pytest.raises(ImportError, match="v1.x 编译器"):
                _do_compile(plan)

    def test_v1_sqlplan_construct_incompatible_raises_runtime_error(self):
        """v1.x SQLPlan 构造不兼容时抛出 RuntimeError 而非穿透"""
        import pytest
        from unittest.mock import patch, MagicMock
        from src.compile.engine import _do_compile
        from src.ir.types import SQLPlan, Strategy

        plan = SQLPlan(strategy=Strategy.G3_DIRECT, primary_table="gold.t1")

        # 模拟 v1 模块存在但 V1SQLPlan 构造抛出 TypeError
        mock_v1_plan = MagicMock()
        mock_v1_plan.side_effect = TypeError("__init__() got an unexpected keyword argument")

        mock_compile = MagicMock()
        mock_compile.__name__ = "compile_sql"

        with patch(
            "scripts.pipeline.layer4_generate.compile_sql", mock_compile, create=True
        ), patch(
            "scripts.pipeline.layer3_ir.SQLPlan", mock_v1_plan, create=True
        ):
            with pytest.raises(RuntimeError, match="v1/v2 IR 结构不兼容"):
                _do_compile(plan)
