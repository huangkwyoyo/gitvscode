from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import pyarrow.parquet as pq


BASE_DIR = Path("D:/ProgramData/Datawarehouse/" + "\u7ebd\u7ea6\u5e02\u57ce\u5e02\u4ea4\u901a")
DB_PATH = BASE_DIR / "nyc_transport.duckdb"
AUDIT_PATH = BASE_DIR / "\u7ebd\u7ea6\u5e02\u57ce\u5e02\u4ea4\u901a_Bronze\u5165\u5e93\u6821\u9a8c\u62a5\u544a.md"
GENERATED_AT = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


TABLE_NAME_OVERRIDES = {
    "fhv_tripdata_2026Q1": "fhv_tripdata_2026q1",
    "fhvhv_tripdata_2026Q1": "fhvhv_tripdata_2026q1",
    "green_tripdata_2026Q1": "green_tripdata_2026q1",
    "yellow_tripdata_2026Q1": "yellow_tripdata_2026q1",
    "FHV_Base_Aggregate_Report_20260606": "fhv_base_aggregate_report",
    "TLC_New_Driver_Application_Status_20260605": "new_driver_applications",
    "Taxi_Improvement_Fund_(TIF)_Medallion_Payments_20260605": "tif_medallion_payments",
    "For_Hire_Vehicles_(FHV)_-_Active_20260605": "fhv_active_vehicles",
    "For_Hire_Vehicles_(FHV)_-_Active_Drivers_20260605": "fhv_active_drivers",
    "Medallion__Vehicles_-_Authorized_20260605": "medallion_authorized_vehicles",
    "Street_Hail_Livery_(SHL)_Drivers_-_Active_20260605": "shl_active_drivers",
}


KEY_CANDIDATES = {
    "taxi_zone_lookup": ["LocationID"],
    "parking_violations_all": ["summons_number"],
    "new_driver_applications": ["App No"],
    "tif_medallion_payments": ["License Number"],
    "fhv_active_vehicles": ["Vehicle License Number"],
    "fhv_active_drivers": ["License Number"],
    "medallion_authorized_vehicles": ["License Number"],
    "crash_person_all": ["unique_id"],
    "crash_merged": ["collision_id"],
    "active_vehicles": ["License Number"],
    "shl_active_drivers": ["License Number"],
    "fhv_base_aggregate_report": ["Base License Number"],
}


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def qident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def table_name_for(path: Path) -> str:
    stem = path.stem
    if stem in TABLE_NAME_OVERRIDES:
        return TABLE_NAME_OVERRIDES[stem]
    name = stem.lower()
    name = re.sub(r"[^a-z0-9]+", "_", name).strip("_")
    return name or "unknown_table"


def domain_for(table_name: str, relative_path: str) -> str:
    text = f"{table_name} {relative_path}".lower()
    if "tripdata" in text:
        return "出行域"
    if "taxi_zone" in text or "zone_lookup" in text:
        return "空间地理域"
    if "crash" in text or "collision" in text or "事故" in text:
        return "安全域"
    if "parking" in text or "violation" in text or "tif" in text or "authorized" in text or "application" in text:
        return "监管合规域"
    if "driver" in text or "司机" in text:
        return "供给域"
    if "vehicle" in text or "vehicles" in text or "active_vehicles" in text:
        return "资产域"
    if "base" in text:
        return "供给域"
    return "待归类"


def role_for(table_name: str) -> str:
    if "tripdata" in table_name:
        return "行程事实源表"
    if table_name == "taxi_zone_lookup":
        return "空间维度源表"
    if table_name == "parking_violations_all":
        return "罚单事实源表"
    if table_name == "crash_merged":
        return "事故事实源表"
    if table_name == "crash_person_all":
        return "事故人员明细源表"
    if "driver" in table_name:
        return "司机快照源表"
    if "vehicle" in table_name:
        return "车辆快照源表"
    if "base" in table_name:
        return "基地汇总源表"
    return "业务快照源表"


def discover_sources() -> list[dict[str, Any]]:
    files = sorted(list(BASE_DIR.rglob("*.parquet")) + list(BASE_DIR.rglob("*.csv")))
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in files:
        if path.name == DB_PATH.name:
            continue
        table_name = table_name_for(path)
        if table_name in seen:
            raise ValueError(f"表名冲突：{table_name} <- {path}")
        seen.add(table_name)
        relative_path = str(path.relative_to(BASE_DIR))
        sources.append(
            {
                "table_name": table_name,
                "source_path": str(path),
                "relative_path": relative_path,
                "file_format": path.suffix.lower().lstrip("."),
                "file_size_bytes": path.stat().st_size,
                "domain": domain_for(table_name, relative_path),
                "role": role_for(table_name),
            }
        )
    return sources


def create_schemas(conn: duckdb.DuckDBPyConnection) -> None:
    for schema in ["bronze", "silver", "gold", "meta"]:
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {qident(schema)}")


def register_bronze_sources(conn: duckdb.DuckDBPyConnection, sources: list[dict[str, Any]]) -> None:
    for source in sources:
        table = qident(source["table_name"])
        path = sql_string(source["source_path"])
        if source["file_format"] == "parquet":
            conn.execute(f"CREATE OR REPLACE VIEW bronze.{table} AS SELECT * FROM read_parquet({path})")
            source["bronze_object_type"] = "VIEW"
            source["load_strategy"] = "read_parquet外部视图"
        else:
            conn.execute(f"DROP TABLE IF EXISTS bronze.{table}")
            conn.execute(
                f"""
                CREATE TABLE bronze.{table} AS
                SELECT *
                FROM read_csv_auto(
                    {path},
                    header = true,
                    all_varchar = true,
                    sample_size = -1,
                    ignore_errors = true
                )
                """
            )
            source["bronze_object_type"] = "TABLE"
            source["load_strategy"] = "read_csv_auto导入文本表"


def row_count(conn: duckdb.DuckDBPyConnection, table_name: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM bronze.{qident(table_name)}").fetchone()[0])


def table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT column_name, data_type, ordinal_position
        FROM information_schema.columns
        WHERE table_schema = 'bronze' AND table_name = ?
        ORDER BY ordinal_position
        """,
        [table_name],
    ).fetchall()
    return [{"column_name": row[0], "data_type": row[1], "ordinal_position": row[2]} for row in rows]


def build_source_catalog(conn: duckdb.DuckDBPyConnection, sources: list[dict[str, Any]]) -> None:
    records = []
    for source in sources:
        count = row_count(conn, source["table_name"])
        columns = table_columns(conn, source["table_name"])
        source["row_count"] = count
        source["column_count"] = len(columns)
        records.append(
            {
                **source,
                "row_count": count,
                "column_count": len(columns),
                "loaded_at": GENERATED_AT,
            }
        )
    conn.register("_source_catalog_df", pd.DataFrame(records))
    conn.execute("CREATE OR REPLACE TABLE meta.source_tables AS SELECT * FROM _source_catalog_df")
    conn.unregister("_source_catalog_df")


def build_column_catalog(conn: duckdb.DuckDBPyConnection, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for source in sources:
        for column in table_columns(conn, source["table_name"]):
            records.append(
                {
                    "table_schema": "bronze",
                    "table_name": source["table_name"],
                    "column_name": column["column_name"],
                    "ordinal_position": column["ordinal_position"],
                    "data_type": column["data_type"],
                    "source_path": source["source_path"],
                    "loaded_at": GENERATED_AT,
                }
            )
    conn.register("_column_catalog_df", pd.DataFrame(records))
    conn.execute("CREATE OR REPLACE TABLE meta.source_columns AS SELECT * FROM _column_catalog_df")
    conn.unregister("_column_catalog_df")
    return records


def count_missing(conn: duckdb.DuckDBPyConnection, table_name: str, column_name: str) -> int:
    column = qident(column_name)
    table = qident(table_name)
    return int(
        conn.execute(
            f"""
            SELECT SUM(
                CASE
                    WHEN {column} IS NULL THEN 1
                    WHEN TRY_CAST({column} AS VARCHAR) = '' THEN 1
                    ELSE 0
                END
            )
            FROM bronze.{table}
            """
        ).fetchone()[0]
        or 0
    )


def count_distinct(conn: duckdb.DuckDBPyConnection, table_name: str, column_name: str) -> int:
    return int(conn.execute(f"SELECT COUNT(DISTINCT {qident(column_name)}) FROM bronze.{qident(table_name)}").fetchone()[0])


def build_missing_matrix(conn: duckdb.DuckDBPyConnection, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for source in sources:
        table_name = source["table_name"]
        rows = source["row_count"]
        for column in table_columns(conn, table_name):
            missing = count_missing(conn, table_name, column["column_name"])
            missing_rate = missing / rows if rows else 0
            records.append(
                {
                    "table_schema": "bronze",
                    "table_name": table_name,
                    "column_name": column["column_name"],
                    "data_type": column["data_type"],
                    "row_count": rows,
                    "missing_count": missing,
                    "missing_rate": missing_rate,
                    "non_missing_count": rows - missing,
                    "quality_status": missing_status(missing_rate),
                    "checked_at": GENERATED_AT,
                }
            )
    conn.register("_missing_df", pd.DataFrame(records))
    conn.execute("CREATE OR REPLACE TABLE meta.bronze_missing_matrix AS SELECT * FROM _missing_df")
    conn.unregister("_missing_df")
    return records


def missing_status(rate: float) -> str:
    if rate == 0:
        return "良好"
    if rate < 0.3:
        return "轻微缺失"
    if rate < 0.8:
        return "缺失偏高"
    return "严重缺失"


def build_key_checks(conn: duckdb.DuckDBPyConnection, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for source in sources:
        table_name = source["table_name"]
        columns = {column["column_name"] for column in table_columns(conn, table_name)}
        for candidate in KEY_CANDIDATES.get(table_name, []):
            if candidate not in columns:
                records.append(
                    {
                        "table_schema": "bronze",
                        "table_name": table_name,
                        "candidate_key": candidate,
                        "row_count": source["row_count"],
                        "distinct_count": None,
                        "null_or_blank_count": None,
                        "duplicate_count": None,
                        "is_unique_key": False,
                        "status": "候选键字段不存在",
                        "checked_at": GENERATED_AT,
                    }
                )
                continue
            distinct_count = count_distinct(conn, table_name, candidate)
            missing = count_missing(conn, table_name, candidate)
            duplicate_count = source["row_count"] - distinct_count
            is_unique = duplicate_count == 0 and missing == 0
            records.append(
                {
                    "table_schema": "bronze",
                    "table_name": table_name,
                    "candidate_key": candidate,
                    "row_count": source["row_count"],
                    "distinct_count": distinct_count,
                    "null_or_blank_count": missing,
                    "duplicate_count": duplicate_count,
                    "is_unique_key": is_unique,
                    "status": "可作为主键" if is_unique else "需去重或生成代理键",
                    "checked_at": GENERATED_AT,
                }
            )
    conn.register("_key_checks_df", pd.DataFrame(records))
    conn.execute("CREATE OR REPLACE TABLE meta.bronze_key_checks AS SELECT * FROM _key_checks_df")
    conn.unregister("_key_checks_df")
    return records


def build_quality_summary(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE OR REPLACE TABLE meta.bronze_quality_summary AS
        SELECT
            s.table_name,
            s.domain,
            s.role,
            s.file_format,
            s.bronze_object_type,
            s.row_count,
            s.column_count,
            COALESCE(k.problem_key_count, 0) AS problem_key_count,
            COALESCE(m.high_missing_column_count, 0) AS high_missing_column_count,
            s.source_path,
            s.loaded_at
        FROM meta.source_tables s
        LEFT JOIN (
            SELECT table_name, COUNT(*) AS problem_key_count
            FROM meta.bronze_key_checks
            WHERE NOT is_unique_key
            GROUP BY table_name
        ) k USING (table_name)
        LEFT JOIN (
            SELECT table_name, COUNT(*) AS high_missing_column_count
            FROM meta.bronze_missing_matrix
            WHERE missing_rate >= 0.3
            GROUP BY table_name
        ) m USING (table_name)
        ORDER BY domain, table_name
        """
    )


def create_help_views(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("CREATE OR REPLACE VIEW meta.v_bronze_tables AS SELECT * FROM meta.source_tables ORDER BY domain, table_name")
    conn.execute("CREATE OR REPLACE VIEW meta.v_bronze_columns AS SELECT * FROM meta.source_columns ORDER BY table_name, ordinal_position")
    conn.execute(
        """
        CREATE OR REPLACE VIEW meta.v_bronze_quality_issues AS
        SELECT
            '候选键' AS issue_type,
            table_name,
            candidate_key AS column_name,
            status AS issue_detail,
            duplicate_count,
            null_or_blank_count,
            checked_at
        FROM meta.bronze_key_checks
        WHERE NOT is_unique_key
        UNION ALL
        SELECT
            '缺失率' AS issue_type,
            table_name,
            column_name,
            quality_status || '，缺失率=' || ROUND(missing_rate * 100, 2)::VARCHAR || '%' AS issue_detail,
            NULL AS duplicate_count,
            missing_count AS null_or_blank_count,
            checked_at
        FROM meta.bronze_missing_matrix
        WHERE missing_rate >= 0.3
        ORDER BY table_name, issue_type, column_name
        """
    )


def create_database() -> dict[str, Any]:
    sources = discover_sources()
    conn = duckdb.connect(str(DB_PATH))
    try:
        create_schemas(conn)
        register_bronze_sources(conn, sources)
        build_source_catalog(conn, sources)
        build_column_catalog(conn, sources)
        missing_records = build_missing_matrix(conn, sources)
        key_records = build_key_checks(conn, sources)
        build_quality_summary(conn)
        create_help_views(conn)
        conn.execute("CHECKPOINT")
        summary = {
            "db_path": str(DB_PATH),
            "source_count": len(sources),
            "total_rows": sum(source["row_count"] for source in sources),
            "total_columns": sum(source["column_count"] for source in sources),
            "missing_record_count": len(missing_records),
            "key_check_count": len(key_records),
            "sources": sources,
        }
        write_audit_report(conn, summary)
        return summary
    finally:
        conn.close()


def write_audit_report(conn: duckdb.DuckDBPyConnection, summary: dict[str, Any]) -> None:
    table_rows = conn.execute(
        """
        SELECT table_name, domain, role, file_format, bronze_object_type, row_count, column_count
        FROM meta.source_tables
        ORDER BY domain, table_name
        """
    ).fetchall()
    key_rows = conn.execute(
        """
        SELECT table_name, candidate_key, row_count, distinct_count, duplicate_count, null_or_blank_count, status
        FROM meta.bronze_key_checks
        ORDER BY table_name, candidate_key
        """
    ).fetchall()
    issue_rows = conn.execute(
        """
        SELECT issue_type, table_name, column_name, issue_detail
        FROM meta.v_bronze_quality_issues
        LIMIT 80
        """
    ).fetchall()
    table_md = "\n".join(
        f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]:,} | {row[6]} |"
        for row in table_rows
    )
    key_md = "\n".join(
        f"| {row[0]} | {row[1]} | {row[2]:,} | {row[3]:,} | {row[4]:,} | {row[5]:,} | {row[6]} |"
        for row in key_rows
    )
    issue_md = "\n".join(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |" for row in issue_rows)
    AUDIT_PATH.write_text(
        f"""# 纽约市城市交通 Bronze 入库校验报告

生成时间：{GENERATED_AT}

## 入库结论

DuckDB 文件：`{DB_PATH}`

本次已建立 `bronze`、`silver`、`gold`、`meta` 四个 schema。`bronze` 已注册或导入 {summary['source_count']} 张结构化源表，合计 {summary['total_rows']:,} 行、{summary['total_columns']:,} 个字段。

口径说明：

- parquet 大表使用 `read_parquet` 外部视图注册，避免重复复制原始大文件。
- CSV 快照表导入为 `bronze` 物理表，并尽量保留原始文本值。
- `meta` schema 已生成数据目录、字段目录、缺失率矩阵、候选键校验和质量汇总。

## Bronze 表清单

| 表名 | 数据域 | 角色 | 格式 | Bronze对象 | 行数 | 字段数 |
|---|---|---|---|---|---:|---:|
{table_md}

## 候选键校验

| 表名 | 候选键 | 行数 | 唯一值数 | 重复数 | 空/空白数 | 状态 |
|---|---|---:|---:|---:|---:|---|
{key_md}

## 主要质量问题

| 问题类型 | 表名 | 字段 | 说明 |
|---|---|---|---|
{issue_md}

## 后续建议

1. 先在 `silver` schema 建设 `trip_detail` 和 `taxi_zone`，因为出行域和空间域最稳定。
2. 对 `parking_violations_all`、`crash_merged`、`crash_person_all` 制定去重和代理键规则。
3. 在 `meta` 中继续沉淀中文字段说明、指标口径、表关系说明，作为 Agent 语义层基础。
""",
        encoding="utf-8",
    )


def main() -> None:
    summary = create_database()
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
