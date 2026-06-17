"""
双代码草案生成器直接单元测试。

覆盖 generate_dual_code() 及校验函数：
- SQL 草案生成，只允许 SELECT/WITH
- Spark DSL 草案生成
- 禁止 CREATE/INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/MERGE
- 禁止 Spark .write / saveAsTable / overwrite
- 生成的代码只能引用 fixture 声明的字段
- 多表报错
- 缺失日期过滤时的 pending 标注
"""

from __future__ import annotations

import pytest

from src.agent.design_planner import DevPlan
from src.agent.dual_code_generator import (
    DualCodeDrafts,
    FORBIDDEN_SQL_KEYWORDS,
    FORBIDDEN_SPARK_PATTERNS,
    generate_dual_code,
    validate_sql_draft,
    validate_spark_draft,
)
from src.ir.types import CodeDraft


# ═════════════════════════════════════════════════════════════
# 辅助函数
# ═════════════════════════════════════════════════════════════


def _make_plan(**overrides) -> DevPlan:
    """构造单表测试 DevPlan。"""
    defaults = {
        "request_id": "test_dual_001",
        "title": "测试双代码生成",
        "business_goal": "验证代码生成",
        "source_tables": [{"name": "gold.dws_daily_trip_summary"}],
        "required_fields": [
            {"name": "trip_date", "table": "gold.dws_daily_trip_summary", "alias": "trip_date", "source": "gold.dws_daily_trip_summary.trip_date"},
        ],
        "metrics": [
            {"name": "trip_count", "field": "trip_count", "aggregation": "SUM", "alias": "trip_count", "definition_source": "meta.metric_definitions.trip_count"},
        ],
        "filters": {"date_range": ["2026-01-01", "2026-01-31"]},
        "grain": ["trip_date"],
        "output_expectation": "按日汇总",
        "human_review_points": [],
    }
    defaults.update(overrides)
    return DevPlan(**defaults)


# ═════════════════════════════════════════════════════════════
# SQL / Spark 草案生成
# ═════════════════════════════════════════════════════════════


def test_generates_sql_draft():
    """generate_dual_code 必须生成有效的 SQL 草案。"""
    plan = _make_plan()
    drafts = generate_dual_code(plan)

    assert isinstance(drafts.sql, CodeDraft)
    assert drafts.sql.kind == "sql"
    assert drafts.sql.path == "sql/main.sql"
    assert drafts.sql.content
    assert "SELECT" in drafts.sql.content.upper()
    assert "FROM gold.dws_daily_trip_summary" in drafts.sql.content


def test_generates_spark_draft():
    """generate_dual_code 必须生成有效的 Spark DSL 草案。"""
    plan = _make_plan()
    drafts = generate_dual_code(plan)

    assert isinstance(drafts.spark, CodeDraft)
    assert drafts.spark.kind == "spark"
    assert drafts.spark.path == "spark/main.py"
    assert drafts.spark.content
    assert "def build_dataframe" in drafts.spark.content
    assert "gold.dws_daily_trip_summary" in drafts.spark.content


def test_sql_draft_contains_draft_disclaimer():
    """SQL 草案必须包含草案免责声明。"""
    plan = _make_plan()
    drafts = generate_dual_code(plan)

    assert "草案" in drafts.sql.content
    assert "不得上线" in drafts.sql.content


def test_spark_draft_contains_draft_disclaimer():
    """Spark 草案必须包含草案免责声明。"""
    plan = _make_plan()
    drafts = generate_dual_code(plan)

    assert "草案" in drafts.spark.content
    assert "不得上线" in drafts.spark.content


def test_sql_uses_select_with_group_by():
    """SQL 草案应包含 GROUP BY 子句。"""
    plan = _make_plan()
    drafts = generate_dual_code(plan)

    assert "GROUP BY" in drafts.sql.content.upper()


def test_spark_uses_groupBy_and_agg():
    """Spark 草案应包含 groupBy 和 agg 调用。"""
    plan = _make_plan()
    drafts = generate_dual_code(plan)

    assert "groupBy" in drafts.spark.content
    assert "agg" in drafts.spark.content.lower()


# ═════════════════════════════════════════════════════════════
# SQL 只允许 SELECT / WITH
# ═════════════════════════════════════════════════════════════


def test_sql_generated_starts_with_select_or_with():
    """生成的 SQL 必须以 SELECT 或 WITH 开头。"""
    plan = _make_plan()
    drafts = generate_dual_code(plan)

    # 清理注释后检查
    upper_start = drafts.sql.content.strip().split("\n")[0].upper()
    # 跳过注释行
    for line in drafts.sql.content.split("\n"):
        stripped = line.strip().upper()
        if stripped and not stripped.startswith("--"):
            assert stripped.startswith("SELECT")
            break


def test_validate_sql_rejects_create():
    """CREATE 必须被 validate_sql_draft 拒绝。"""
    errors = validate_sql_draft("CREATE TABLE t AS SELECT 1")
    assert errors


def test_validate_sql_rejects_insert():
    """INSERT 必须被拒绝。"""
    errors = validate_sql_draft("INSERT INTO t VALUES (1)")
    assert errors


def test_validate_sql_rejects_update():
    """UPDATE 必须被拒绝。"""
    errors = validate_sql_draft("UPDATE t SET col = 1")
    assert errors


def test_validate_sql_rejects_delete():
    """DELETE 必须被拒绝。"""
    errors = validate_sql_draft("DELETE FROM t")
    assert errors


def test_validate_sql_rejects_drop():
    """DROP 必须被拒绝。"""
    errors = validate_sql_draft("DROP TABLE t")
    assert errors


def test_validate_sql_rejects_alter():
    """ALTER 必须被拒绝。"""
    errors = validate_sql_draft("ALTER TABLE t ADD COLUMN c INT")
    assert errors


def test_validate_sql_rejects_truncate():
    """TRUNCATE 必须被拒绝。"""
    errors = validate_sql_draft("TRUNCATE TABLE t")
    assert errors


def test_validate_sql_rejects_merge():
    """MERGE 必须被拒绝。"""
    errors = validate_sql_draft("MERGE INTO t USING s ON t.id = s.id")
    assert errors


def test_validate_sql_accepts_select():
    """合法 SELECT 应通过校验。"""
    errors = validate_sql_draft("SELECT trip_count FROM gold.dws_daily_trip_summary")
    assert not errors


def test_validate_sql_accepts_with_cte():
    """合法 WITH CTE 应通过校验。"""
    errors = validate_sql_draft("WITH cte AS (SELECT 1) SELECT * FROM cte")
    assert not errors


def test_validate_sql_rejects_non_select_prefix():
    """不以 SELECT 或 WITH 开头时必须报错。"""
    errors = validate_sql_draft("EXECUTE some_procedure()")
    assert errors


# ═════════════════════════════════════════════════════════════
# Spark 禁止写入模式
# ═════════════════════════════════════════════════════════════


def test_validate_spark_rejects_write():
    """.write 必须被拒绝。"""
    errors = validate_spark_draft("df.write.mode('overwrite').saveAsTable('t')")
    assert errors
    assert any(".write" in e for e in errors)


def test_validate_spark_rejects_saveastable():
    """saveAsTable 必须被拒绝。"""
    errors = validate_spark_draft("df.saveAsTable('gold.t')")
    assert errors
    assert any("saveAsTable" in e for e in errors)


def test_validate_spark_rejects_overwrite():
    """overwrite 模式必须被拒绝。"""
    errors = validate_spark_draft("df.mode('overwrite')")
    assert errors


def test_validate_spark_rejects_insertinto():
    """insertInto 必须被拒绝。"""
    errors = validate_spark_draft("df.write.insertInto('gold.t')")
    # insertInto 包含 .write，所以必然被拦截
    assert errors


def test_validate_spark_accepts_read_only_code():
    """只读 Spark 代码应通过校验。"""
    errors = validate_spark_draft("df = spark.table('gold.t').select('col1')")
    assert not errors


def test_generated_spark_is_read_only():
    """生成的 Spark 草案不能包含任何写入操作。"""
    plan = _make_plan()
    drafts = generate_dual_code(plan)

    lowered = drafts.spark.content.lower()
    for pattern in FORBIDDEN_SPARK_PATTERNS:
        assert pattern.lower() not in lowered, f"Spark 草案包含禁止模式: {pattern}"


# ═════════════════════════════════════════════════════════════
# 代码只能引用 fixture 声明的字段
# ═════════════════════════════════════════════════════════════


def test_sql_only_references_declared_fields():
    """SQL 草案中的字段只能来自 fixture 的 required_fields/metris/grain。"""
    plan = _make_plan(
        required_fields=[
            {"name": "trip_date", "table": "gold.dws_daily_trip_summary", "alias": "trip_date", "source": "gold.dws_daily_trip_summary.trip_date"},
        ],
        metrics=[
            {"name": "trip_count", "field": "trip_count", "aggregation": "SUM", "alias": "trip_count", "definition_source": "meta.metric_definitions.trip_count"},
        ],
    )
    drafts = generate_dual_code(plan)

    # 确认生成的 SQL 包含了声明的字段
    assert "trip_date" in drafts.sql.content
    assert "trip_count" in drafts.sql.content
    # 未声明的字段不应出现在 SQL 中（非表名形式）
    assert "total_fare_amount" not in drafts.sql.content
    assert "total_tip_amount" not in drafts.sql.content


def test_source_refs_records_all_fields():
    """source_refs 必须记录所有字段的来源。"""
    plan = _make_plan()
    drafts = generate_dual_code(plan)

    assert "trip_date" in drafts.sql.source_refs
    assert "trip_count" in drafts.sql.source_refs


def test_source_refs_default_to_human_review_when_missing():
    """缺少 source 的字段，source_refs 标注为 Human Review。"""
    plan = _make_plan(
        required_fields=[
            {"name": "trip_date", "table": "gold.dws_daily_trip_summary"},  # 无 source
        ],
    )
    drafts = generate_dual_code(plan)

    assert drafts.sql.source_refs["trip_date"] == "Human Review"


# ═════════════════════════════════════════════════════════════
# 多表报错
# ═════════════════════════════════════════════════════════════


def test_multi_table_raises_value_error():
    """多表需求必须报错——M2 只支持单表草案生成。"""
    plan = _make_plan(
        source_tables=[
            {"name": "gold.table_a"},
            {"name": "gold.table_b"},
        ],
    )

    with pytest.raises(ValueError, match="多表"):
        generate_dual_code(plan)


def test_zero_tables_raises_value_error():
    """零表需求必须报错。"""
    plan = _make_plan(source_tables=[])

    with pytest.raises(ValueError, match="单表"):
        generate_dual_code(plan)


# ═════════════════════════════════════════════════════════════
# 日期过滤 / grain 缺失 → pending
# ═════════════════════════════════════════════════════════════


def test_missing_date_range_adds_pending():
    """缺少 date_range 时必须向 plan.pending_items 追加提示。"""
    plan = _make_plan(filters={})
    # 注意：generate_dual_code 会直接修改 plan.pending_items
    generate_dual_code(plan)
    assert any("日期" in item for item in plan.pending_items)


def test_missing_grain_adds_pending():
    """缺少 grain 时必须追加 pending 提示。"""
    plan = _make_plan(grain=[])
    generate_dual_code(plan)
    assert any("日期" in item or "grain" in item for item in plan.pending_items)


# ═════════════════════════════════════════════════════════════
# 返回值结构
# ═════════════════════════════════════════════════════════════


def test_dual_code_drafts_has_pending_items():
    """DualCodeDrafts 必须包含 pending_items 和 human_review_points。"""
    plan = _make_plan()
    drafts = generate_dual_code(plan)

    assert isinstance(drafts.pending_items, list)
    assert isinstance(drafts.human_review_points, list)


def test_code_drafts_are_draft_unverified():
    """生成的代码草案默认状态为 draft_unverified。"""
    plan = _make_plan()
    drafts = generate_dual_code(plan)

    assert drafts.sql.status == "draft_unverified"
    assert drafts.spark.status == "draft_unverified"


# ═════════════════════════════════════════════════════════════
# 禁止关键字清单完整性
# ═════════════════════════════════════════════════════════════


def test_forbidden_sql_keywords_exhaustive():
    """FORBIDDEN_SQL_KEYWORDS 必须覆盖全部 8 种 DDL/DML 危险操作。"""
    expected = {"CREATE", "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "MERGE"}
    assert FORBIDDEN_SQL_KEYWORDS == expected


def test_forbidden_spark_patterns_exhaustive():
    """FORBIDDEN_SPARK_PATTERNS 必须覆盖全部 5 种写入模式。"""
    expected = {".write", ".save", ".saveAsTable", ".insertInto", "overwrite"}
    assert set(FORBIDDEN_SPARK_PATTERNS) == expected
