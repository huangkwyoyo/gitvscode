"""
双代码草案生成器。

M2 阶段使用确定性 stub，不接真实 LLM，不执行 SQL/Spark。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.ir.types import CodeDraft

from .design_planner import DevPlan


FORBIDDEN_SQL_KEYWORDS = {
    "CREATE",
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "MERGE",
}

FORBIDDEN_SPARK_PATTERNS = [
    ".write",
    ".save",
    ".saveAsTable",
    ".insertInto",
    "overwrite",
]


@dataclass
class DualCodeDrafts:
    """SQL 与 Spark 两份代码草案"""
    sql: CodeDraft
    spark: CodeDraft
    pending_items: list[str] = field(default_factory=list)
    human_review_points: list[str] = field(default_factory=list)


def _strip_sql_comments(sql: str) -> str:
    """去除注释后再扫描 SQL 关键字"""
    without_line = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    return re.sub(r"/\*.*?\*/", "", without_line, flags=re.DOTALL)


def validate_sql_draft(sql: str) -> list[str]:
    """校验 SQL 草案只包含只读 SELECT 查询"""
    body = _strip_sql_comments(sql).strip()
    upper = body.upper()
    errors: list[str] = []

    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        errors.append("SQL 草案必须以 SELECT 或 WITH 开头")

    for keyword in FORBIDDEN_SQL_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper):
            errors.append(f"SQL 草案包含禁止关键字: {keyword}")

    return errors


def validate_spark_draft(code: str) -> list[str]:
    """校验 Spark 草案不包含写入动作"""
    lowered = code.lower()
    errors: list[str] = []
    for pattern in FORBIDDEN_SPARK_PATTERNS:
        if pattern.lower() in lowered:
            errors.append(f"Spark 草案包含禁止写入模式: {pattern}")
    return errors


def _field_expr(field: dict) -> str:
    """生成 SQL 字段表达式，严格使用 fixture 字段名"""
    name = field["name"]
    alias = field.get("alias") or name
    return f"    {name} AS {alias}"


def _metric_expr(metric: dict) -> str:
    """生成 SQL 指标表达式，严格使用 fixture 字段名"""
    field = metric["field"]
    alias = metric.get("alias") or metric["name"]
    aggregation = str(metric.get("aggregation", "SUM")).upper()
    return f"    {aggregation}({field}) AS {alias}"


def generate_dual_code(plan: DevPlan) -> DualCodeDrafts:
    """
    生成 DuckDB SQL 与 PySpark DSL 草案。

    生成逻辑只使用 fixture 明示的表、字段和指标。
    """
    if len(plan.source_tables) != 1:
        raise ValueError("M2 只支持单表草案生成，多表 JOIN 需要 Human Review")

    table = plan.source_tables[0]["name"]
    date_range = plan.filters.get("date_range", [])
    grain = list(plan.grain)
    select_parts = [_field_expr(f) for f in plan.required_fields]
    select_parts.extend(_metric_expr(m) for m in plan.metrics)

    where_parts: list[str] = []
    if len(date_range) == 2 and grain:
        where_parts.append(f"{grain[0]} BETWEEN '{date_range[0]}' AND '{date_range[1]}'")
    else:
        plan.pending_items.append("Human Review: 日期过滤或 grain 缺失，SQL 未生成日期 WHERE")

    group_by = ", ".join(grain)
    order_by = ", ".join(grain)
    sql_lines = [
        "-- 草案：未经验证，未经人审，不得上线。",
        "-- M2 阶段未执行 SQL，未连接生产库。",
        "SELECT",
        ",\n".join(select_parts),
        f"FROM {table}",
    ]
    if where_parts:
        sql_lines.append("WHERE " + " AND ".join(where_parts))
    if group_by:
        sql_lines.append(f"GROUP BY {group_by}")
        sql_lines.append(f"ORDER BY {order_by}")
    sql = "\n".join(sql_lines) + ";\n"

    spark_select_fields = [f'"{f["name"]}"' for f in plan.required_fields]
    metric_lines = []
    for metric in plan.metrics:
        aggregation = str(metric.get("aggregation", "sum")).lower()
        metric_lines.append(
            f'        F.{aggregation}("{metric["field"]}").alias("{metric.get("alias") or metric["name"]}")'
        )

    group_expr = ", ".join(f'"{g}"' for g in grain)
    where_expr = ""
    if len(date_range) == 2 and grain:
        where_expr = f'.where((F.col("{grain[0]}") >= "{date_range[0]}") & (F.col("{grain[0]}") <= "{date_range[1]}"))'

    spark = "\n".join([
        "# 草案：未经验证，未经人审，不得上线。",
        "# M2 阶段未执行 Spark，未连接生产环境。",
        "from pyspark.sql import functions as F",
        "",
        "def build_dataframe(spark):",
        f'    df = spark.table("{table}")',
        f"    df = df{where_expr}" if where_expr else "    # Human Review: 未生成日期过滤",
        f"    result = df.groupBy({group_expr}).agg(" if group_expr else "    result = df.agg(",
        ",\n".join(metric_lines),
        "    )",
        f"    return result.select({', '.join(spark_select_fields + [repr(m.get('alias') or m['name']) for m in plan.metrics])})",
        "",
    ])

    sql_errors = validate_sql_draft(sql)
    spark_errors = validate_spark_draft(spark)
    if sql_errors or spark_errors:
        raise ValueError("; ".join(sql_errors + spark_errors))

    source_refs = {}
    for field in plan.required_fields:
        source_refs[field["name"]] = field.get("source", "Human Review")
    for metric in plan.metrics:
        source_refs[metric["name"]] = metric.get("definition_source", "Human Review")

    pending = list(plan.pending_items)
    pending.extend([item for item in source_refs.values() if item == "Human Review"])

    return DualCodeDrafts(
        sql=CodeDraft(
            kind="sql",
            path="sql/main.sql",
            content=sql,
            language="duckdb_sql",
            source_refs=source_refs,
            pending_items=pending,
        ),
        spark=CodeDraft(
            kind="spark",
            path="spark/main.py",
            content=spark,
            language="pyspark",
            source_refs=source_refs,
            pending_items=pending,
        ),
        pending_items=pending,
        human_review_points=list(plan.human_review_points),
    )
