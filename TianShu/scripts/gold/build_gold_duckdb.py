"""
构建 DuckDB Gold G0/G1 维表。

本脚本只建设 Gold 第一批维表，不建设事实表和汇总表。
所有字段必须来自 Silver 或已明确标记的派生规则，并同步写入中文语义元数据。

dim_violation_type 的罚款金额来源于官方数据字典 Excel：
  - standard_fine_amount → Manhattan 96th St. & below 标准罚款
  - penalty_amount → 当前无数据源（Excel 不含滞纳金数据），保持 NULL
"""
import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUALITY_DIR = PROJECT_ROOT / "scripts" / "quality"
sys.path.insert(0, str(QUALITY_DIR))

from harness_config import load_harness_config  # noqa: E402

try:
    import duckdb
except ImportError:
    duckdb = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

# 官方违章代码字典 Excel 路径
VIOLATION_DICT_XLSX = Path(
    r"D:\ProgramData\Datawarehouse\纽约市城市交通"
    r"\2026财年纽约停车违章罚单开具情况"
    r"\Parking_Violations_Issued_Data_Dictionary.xlsx"
)


GOLD_DIMENSIONS = {
    "dim_date": {
        "zh": "日期维表",
        "columns": {
            "date_key": ("日期键", "主键"),
            "date": ("日期", "时间字段"),
            "year": ("年", "维度属性"),
            "quarter": ("季度", "维度属性"),
            "month": ("月", "维度属性"),
            "week": ("ISO周号", "维度属性"),
            "day_of_week": ("星期序号", "维度属性"),
            "day_of_week_name": ("星期名称", "维度属性"),
            "is_weekend": ("是否周末", "质量/分类标记"),
            "fiscal_year": ("NYC财年", "维度属性"),
        },
    },
    "dim_taxi_zone": {
        "zh": "出租车区域维表",
        "columns": {
            "location_id": ("出租车区域编号", "主键"),
            "borough": ("行政区", "维度属性"),
            "zone_name": ("区域名称", "维度属性"),
            "service_zone": ("服务区域", "维度属性"),
            "is_unknown_zone": ("是否未知区域", "质量标记"),
        },
    },
    "dim_vehicle": {
        "zh": "车辆维表",
        "columns": {
            "vehicle_key": ("车辆维表代理键", "主键"),
            "license_number": ("牌照编号", "业务键"),
            "license_type": ("牌照类型", "维度属性"),
            "license_status": ("牌照状态", "维度属性"),
            "owner_name": ("车主姓名或公司名", "维度属性"),
            "expiration_date": ("牌照到期日期", "时间字段"),
            "dmv_plate_number": ("DMV车牌号", "维度属性"),
            "vin": ("车辆识别码", "维度属性"),
            "vehicle_make": ("车辆品牌", "维度属性"),
            "vehicle_model": ("车辆型号", "维度属性"),
            "vehicle_year": ("车辆年份", "维度属性"),
            "fuel_type": ("燃料类型", "维度属性"),
            "wav_flag": ("无障碍车辆标志", "维度属性"),
            "stretch_limo": ("是否加长豪华轿车", "维度属性"),
            "medallion_type": ("Medallion类型", "维度属性"),
            "base_number": ("基地编号", "弱关联键"),
            "base_name": ("基地名称", "维度属性"),
            "base_type": ("基地类型", "维度属性"),
            "base_address": ("基地地址", "维度属性"),
            "agent_number": ("代理编号", "维度属性"),
            "agent_name": ("代理名称", "维度属性"),
            "insurance_carrier": ("保险公司名称", "维度属性"),
            "insurance_policy_number": ("保险单号", "维度属性"),
            "last_date_updated": ("最后更新日期", "时间字段"),
        },
    },
    "dim_driver": {
        "zh": "司机维表",
        "columns": {
            "driver_key": ("司机维表代理键", "主键"),
            "license_number": ("司机牌照号", "业务键"),
            "driver_name": ("司机姓名", "维度属性"),
            "driver_type": ("司机类型", "维度属性"),
            "status_code": ("状态码", "维度属性"),
            "status_description": ("状态描述", "维度属性"),
            "expiration_date": ("牌照到期日期", "时间字段"),
            "wav_trained": ("是否WAV培训", "维度属性"),
            "last_date_updated": ("最后更新日期", "时间字段"),
        },
    },
    "dim_base": {
        "zh": "基地维表",
        "columns": {
            "base_key": ("基地维表代理键", "主键"),
            "base_license_number": ("基地牌照号", "业务键"),
            "base_name": ("基地名称", "维度属性"),
            "dba": ("经营别名", "维度属性"),
            "base_type": ("基地类型", "维度属性"),
            "base_address": ("基地地址", "维度属性"),
        },
    },
    "dim_violation_type": {
        "zh": "违章类型维表",
        "columns": {
            "violation_code": ("违章代码", "主键"),
            "violation_description": ("违章描述", "维度属性"),
            "standard_fine_amount": ("标准罚款金额（曼哈顿核心区）", "金额字段"),
            "penalty_amount": ("滞纳金金额（当前无数据源）", "金额字段"),
            "source_status": ("金额数据来源", "审核状态"),
        },
    },
}


def connect_duckdb(db_path: Path):
    """连接 DuckDB，失败时给出明确错误"""
    if duckdb is None:
        raise RuntimeError("duckdb 未安装，无法构建 Gold 表")
    return duckdb.connect(str(db_path), read_only=False)


def ensure_meta_tables(conn) -> None:
    """确保中文语义元数据表存在"""
    conn.execute("CREATE SCHEMA IF NOT EXISTS meta")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta.table_comments (
            table_schema VARCHAR,
            table_name VARCHAR,
            table_name_zh VARCHAR,
            updated_at VARCHAR
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta.column_comments (
            table_schema VARCHAR,
            table_name VARCHAR,
            column_name VARCHAR,
            column_name_zh VARCHAR,
            column_role_zh VARCHAR,
            updated_at VARCHAR
        )
        """
    )


def load_violation_fines(conn) -> None:
    """将官方违章代码 Excel 加载到 DuckDB 临时表，供 dim_violation_type 建表使用"""
    if openpyxl is None:
        print("[WARN] openpyxl 未安装，dim_violation_type 罚款金额将保持 NULL")
        return

    if not VIOLATION_DICT_XLSX.exists():
        print(f"[WARN] 违章代码字典 Excel 不存在: {VIOLATION_DICT_XLSX}")
        return

    wb = openpyxl.load_workbook(VIOLATION_DICT_XLSX, data_only=True)
    ws = wb["Parking Violation Codes"]

    rows: list[tuple[int, str, int, int]] = []
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
        code = row[0]
        desc = row[1]
        manhattan_fine = row[2]
        other_fine = row[3]
        if code is None or str(code).strip() == "":
            continue
        try:
            code_int = int(code)
        except (ValueError, TypeError):
            continue
        rows.append((
            code_int,
            str(desc).strip() if desc else "",
            int(manhattan_fine) if manhattan_fine is not None else 0,
            int(other_fine) if other_fine is not None else 0,
        ))

    wb.close()

    conn.execute("DROP TABLE IF EXISTS tmp_violation_fines")
    conn.execute(
        """
        CREATE TEMP TABLE tmp_violation_fines (
            violation_code_int INTEGER,
            violation_description_from_dict VARCHAR,
            manhattan_fine INTEGER,
            other_areas_fine INTEGER
        )
        """
    )
    conn.executemany(
        "INSERT INTO tmp_violation_fines VALUES (?, ?, ?, ?)", rows
    )
    print(f"已加载 {len(rows)} 条违章代码罚款标准（来源：官方数据字典 Excel）")


def replace_gold_comments(conn, table_names: list[str]) -> None:
    """重建本批 Gold 表对应的中文注释，避免残留旧字段"""
    placeholders = ", ".join(["?"] * len(table_names))
    conn.execute(
        f"DELETE FROM meta.table_comments WHERE table_schema = 'gold' AND table_name IN ({placeholders})",
        table_names,
    )
    conn.execute(
        f"DELETE FROM meta.column_comments WHERE table_schema = 'gold' AND table_name IN ({placeholders})",
        table_names,
    )


def write_gold_comments(conn, table_names: list[str]) -> None:
    """写入 Gold 表和字段中文注释"""
    timestamp_sql = "strftime(now(), '%Y-%m-%d %H:%M:%S')"
    for table_name in table_names:
        definition = GOLD_DIMENSIONS[table_name]
        conn.execute(
            f"""
            INSERT INTO meta.table_comments
            SELECT 'gold', ?, ?, {timestamp_sql}
            """,
            [table_name, definition["zh"]],
        )
        for column_name, (column_name_zh, column_role_zh) in definition["columns"].items():
            conn.execute(
                f"""
                INSERT INTO meta.column_comments
                SELECT 'gold', ?, ?, ?, ?, {timestamp_sql}
                """,
                [table_name, column_name, column_name_zh, column_role_zh],
            )


def build_g0(conn) -> list[str]:
    """构建 G0 公共维表"""
    conn.execute("CREATE SCHEMA IF NOT EXISTS gold")
    conn.execute("DROP TABLE IF EXISTS gold.dim_date")
    conn.execute(
        """
        CREATE TABLE gold.dim_date AS
        SELECT
            date_key,
            CAST(date AS DATE) AS date,
            year,
            quarter,
            month,
            week,
            day_of_week,
            day_of_week_name,
            is_weekend,
            fiscal_year
        FROM silver.dim_date
        """
    )

    conn.execute("DROP TABLE IF EXISTS gold.dim_taxi_zone")
    conn.execute(
        """
        CREATE TABLE gold.dim_taxi_zone AS
        SELECT
            location_id,
            borough,
            zone_name,
            service_zone,
            is_unknown_zone
        FROM silver.taxi_zone
        """
    )
    return ["dim_date", "dim_taxi_zone"]


def build_g1(conn) -> list[str]:
    """构建 G1 业务维表"""
    conn.execute("DROP TABLE IF EXISTS gold.dim_vehicle")
    conn.execute(
        """
        CREATE TABLE gold.dim_vehicle AS
        SELECT
            vehicle_id AS vehicle_key,
            license_number,
            license_type,
            license_status,
            owner_name,
            expiration_date,
            dmv_plate_number,
            vin,
            vehicle_make,
            vehicle_model,
            vehicle_year,
            fuel_type,
            wav_flag,
            stretch_limo,
            medallion_type,
            base_number,
            base_name,
            base_type,
            base_address,
            agent_number,
            agent_name,
            insurance_carrier,
            insurance_policy_number,
            last_date_updated
        FROM silver.vehicle_detail
        """
    )

    conn.execute("DROP TABLE IF EXISTS gold.dim_driver")
    conn.execute(
        """
        CREATE TABLE gold.dim_driver AS
        SELECT
            driver_id AS driver_key,
            license_number,
            driver_name,
            driver_type,
            status_code,
            status_description,
            expiration_date,
            wav_trained,
            last_date_updated
        FROM silver.driver_detail
        """
    )

    conn.execute("DROP TABLE IF EXISTS gold.dim_base")
    conn.execute(
        """
        CREATE TABLE gold.dim_base AS
        WITH latest_base AS (
            SELECT
                base_license_number,
                base_name,
                dba,
                row_number() OVER (
                    PARTITION BY base_license_number
                    ORDER BY year DESC NULLS LAST, month DESC NULLS LAST, base_detail_id DESC
                ) AS rn
            FROM silver.base_detail
            WHERE base_license_number IS NOT NULL
        ),
        vehicle_base AS (
            SELECT
                base_number,
                max(base_type) AS base_type,
                max(base_address) AS base_address
            FROM silver.vehicle_detail
            WHERE base_number IS NOT NULL
            GROUP BY base_number
        ),
        base_one_row AS (
            SELECT
                lb.base_license_number,
                lb.base_name,
                lb.dba,
                vb.base_type,
                vb.base_address
            FROM latest_base lb
            LEFT JOIN vehicle_base vb
              ON vb.base_number = lb.base_license_number
            WHERE lb.rn = 1
        )
        SELECT
            row_number() OVER (ORDER BY base_license_number) AS base_key,
            base_license_number,
            base_name,
            dba,
            base_type,
            base_address
        FROM base_one_row
        """
    )

    conn.execute("DROP TABLE IF EXISTS gold.dim_violation_type")

    # 从官方 Excel 加载违章代码罚款标准
    load_violation_fines(conn)

    conn.execute(
        """
        CREATE TABLE gold.dim_violation_type AS
        WITH silver_codes AS (
            SELECT
                violation_code,
                max(violation_description) AS violation_description
            FROM silver.parking_violation_detail
            WHERE violation_code IS NOT NULL
            GROUP BY violation_code
        )
        SELECT
            s.violation_code,
            COALESCE(d.violation_description_from_dict, s.violation_description)
                AS violation_description,
            CAST(d.manhattan_fine AS DECIMAL(12,2)) AS standard_fine_amount,
            CAST(NULL AS DECIMAL(12,2)) AS penalty_amount,
            CASE
                WHEN d.violation_code_int IS NOT NULL THEN 'from_official_dictionary'
                ELSE 'missing_from_dictionary'
            END AS source_status
        FROM silver_codes s
        LEFT JOIN tmp_violation_fines d
          ON TRY_CAST(s.violation_code AS INTEGER) = d.violation_code_int
        """
    )
    return ["dim_vehicle", "dim_driver", "dim_base", "dim_violation_type"]


def parse_batches(value: str) -> set[str]:
    """解析构建批次参数"""
    batches = {item.strip().upper() for item in value.split(",") if item.strip()}
    invalid = batches - {"G0", "G1"}
    if invalid:
        raise ValueError(f"当前脚本只支持 G0/G1，收到无效批次: {', '.join(sorted(invalid))}")
    return batches


def build_gold(db_path: Path, batches: set[str]) -> list[str]:
    """按批次构建 Gold 维表"""
    conn = connect_duckdb(db_path)
    built_tables: list[str] = []
    try:
        ensure_meta_tables(conn)
        if "G0" in batches:
            built_tables.extend(build_g0(conn))
        if "G1" in batches:
            built_tables.extend(build_g1(conn))
        replace_gold_comments(conn, built_tables)
        write_gold_comments(conn, built_tables)
        return built_tables
    finally:
        conn.close()


def main() -> int:
    """命令行入口"""
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    config = load_harness_config()
    parser = argparse.ArgumentParser(description="构建 DuckDB Gold G0/G1 维表")
    parser.add_argument("--db", type=Path, default=config.duckdb_path, help="DuckDB 数据库路径")
    parser.add_argument("--batches", default="G0,G1", help="构建批次，支持 G0,G1")
    args = parser.parse_args()

    try:
        batches = parse_batches(args.batches)
        built_tables = build_gold(args.db, batches)
    except Exception as exc:
        print(f"[FAIL] Gold G0/G1 构建失败: {exc}")
        return 1

    print("[OK] Gold G0/G1 构建完成。")
    for table_name in built_tables:
        print(f"- gold.{table_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
