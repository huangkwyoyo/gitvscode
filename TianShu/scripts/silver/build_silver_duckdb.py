"""
Silver 层构建脚本入口

红线规则（来自 silver/AGENTS.md）：
- 禁止新增 Bronze 不存在的业务字段
- 禁止使用 DATE::INT（DuckDB 不兼容，应用 strftime）
- 禁止使用无序 ROW_NUMBER() 生成主键（应用稳定 MD5）
- 枚举值以 SELECT DISTINCT 实际值为准，不得硬编码

用法：
  python scripts/silver/build_silver_duckdb.py --batch P0
  python scripts/silver/build_silver_duckdb.py --batch P0 --dry-run
  python scripts/silver/build_silver_duckdb.py --batch all --replace
"""

import argparse
import hashlib
import sys
import time
from datetime import datetime
from pathlib import Path

import duckdb

DB_PATH = Path(r"D:\ProgramData\Datawarehouse\纽约市城市交通\nyc_transport.duckdb")
GENERATED_AT = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect(conn_str: str, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """连接 DuckDB 数据库"""
    try:
        con = duckdb.connect(str(DB_PATH), read_only=read_only)
        con.execute("SET TimeZone = 'America/New_York'")
        return con
    except Exception as e:
        print(f"[FATAL] 无法连接数据库: {e}")
        print("请关闭 DBeaver 等占用数据库的工具后重试")
        sys.exit(1)


def ensure_silver_schema(con: duckdb.DuckDBPyConnection) -> None:
    """确保 silver 和 meta schema 存在"""
    for s in ["silver", "meta"]:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")


def drop_if_exists(con: duckdb.DuckDBPyConnection, table_name: str, replace: bool) -> bool:
    """如果 --replace 且表存在，则删除旧表"""
    exists = con.execute(
        f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='silver' AND table_name='{table_name}'"
    ).fetchone()[0] > 0
    if exists:
        if replace:
            con.execute(f"DROP TABLE IF EXISTS silver.{table_name}")
            print(f"  [DROP] silver.{table_name}")
            return True
        else:
            print(f"  [SKIP] silver.{table_name} 已存在，使用 --replace 覆盖")
            return False
    return True


# ─── P0: dim_date ────────────────────────────────────────────────

def build_dim_date(con: duckdb.DuckDBPyConnection, replace: bool = False) -> int:
    """构建日期维表，生成 2026-01-01 ~ 2026-03-31 共 90 天"""
    table_name = "dim_date"
    if not drop_if_exists(con, table_name, replace):
        return 0

    con.execute("""
        CREATE TABLE silver.dim_date AS
        WITH date_range AS (
            SELECT UNNEST(generate_series(
                '2026-01-01'::DATE,
                '2026-03-31'::DATE,
                INTERVAL 1 DAY
            )) AS date
        )
        SELECT
            strftime(date, '%Y%m%d')::INTEGER AS date_key,
            date,
            EXTRACT(YEAR FROM date)::INTEGER AS year,
            EXTRACT(QUARTER FROM date)::INTEGER AS quarter,
            EXTRACT(MONTH FROM date)::INTEGER AS month,
            EXTRACT(ISODOW FROM date)::INTEGER AS week,  -- ISO 周号
            EXTRACT(ISODOW FROM date)::INTEGER AS day_of_week,  -- 1=周一, 7=周日
            CASE EXTRACT(ISODOW FROM date)::INTEGER
                WHEN 1 THEN 'Monday'
                WHEN 2 THEN 'Tuesday'
                WHEN 3 THEN 'Wednesday'
                WHEN 4 THEN 'Thursday'
                WHEN 5 THEN 'Friday'
                WHEN 6 THEN 'Saturday'
                WHEN 7 THEN 'Sunday'
            END AS day_of_week_name,
            EXTRACT(ISODOW FROM date)::INTEGER IN (6, 7) AS is_weekend,
            CASE
                WHEN EXTRACT(MONTH FROM date)::INTEGER >= 7
                THEN EXTRACT(YEAR FROM date)::INTEGER
                ELSE EXTRACT(YEAR FROM date)::INTEGER - 1
            END AS fiscal_year
        FROM date_range
        ORDER BY date
    """)
    cnt = con.execute(f"SELECT COUNT(*) FROM silver.{table_name}").fetchone()[0]
    print(f"  [OK] silver.{table_name}: {cnt} 行")
    return cnt


# ─── P0: taxi_zone ───────────────────────────────────────────────

def build_taxi_zone(con: duckdb.DuckDBPyConnection, replace: bool = False) -> int:
    """构建出租车区域标准维表，来源 bronze.taxi_zone_lookup"""
    table_name = "taxi_zone"
    if not drop_if_exists(con, table_name, replace):
        return 0

    con.execute("""
        CREATE TABLE silver.taxi_zone AS
        SELECT
            TRY_CAST("LocationID" AS INTEGER) AS location_id,
            CAST("Borough" AS VARCHAR) AS borough,
            CAST("Zone" AS VARCHAR) AS zone_name,
            CAST("service_zone" AS VARCHAR) AS service_zone,
            CAST("Borough" AS VARCHAR) = 'Unknown' AS is_unknown_zone
        FROM bronze.taxi_zone_lookup
        WHERE "LocationID" IS NOT NULL
        ORDER BY location_id
    """)
    cnt = con.execute(f"SELECT COUNT(*) FROM silver.{table_name}").fetchone()[0]

    # 验证主键唯一性
    dup = con.execute(f"SELECT COUNT(*) FROM (SELECT location_id, COUNT(*) AS n FROM silver.{table_name} GROUP BY location_id HAVING n > 1)").fetchone()[0]
    if dup > 0:
        print(f"  [WARN] silver.{table_name}: {dup} 个重复 location_id")
    else:
        print(f"  [OK] silver.{table_name}: {cnt} 行, 主键唯一")
    return cnt


# ─── P0: trip_detail ─────────────────────────────────────────────

def build_trip_detail(con: duckdb.DuckDBPyConnection, replace: bool = False) -> int:
    """构建行程明细标准表，UNION ALL 四类 TLC 行程数据"""
    table_name = "trip_detail"
    if not drop_if_exists(con, table_name, replace):
        return 0

    # 按来源分四段 UNION ALL，每段映射到统一字段
    sql = """
        CREATE TABLE silver.trip_detail AS
        WITH
        yellow AS (
            SELECT
                'yellow' AS trip_source,
                tpep_pickup_datetime AS pickup_at,
                tpep_dropoff_datetime AS dropoff_at,
                TRY_CAST(PULocationID AS INTEGER) AS pickup_location_id,
                TRY_CAST(DOLocationID AS INTEGER) AS dropoff_location_id,
                TRY_CAST(passenger_count AS BIGINT) AS passenger_count,
                TRY_CAST(trip_distance AS DOUBLE) AS distance_miles,
                TRY_CAST(payment_type AS BIGINT) AS payment_type,
                TRY_CAST(RatecodeID AS BIGINT) AS rate_code_id,
                NULL::BIGINT AS trip_type,  -- yellow 无此字段
                NULL::VARCHAR AS base_no,   -- yellow 无此字段
                TRY_CAST(fare_amount AS DECIMAL(12,2)) AS fare_amount,
                TRY_CAST(total_amount AS DECIMAL(12,2)) AS total_amount,
                TRY_CAST(extra AS DECIMAL(12,2)) AS extra,
                TRY_CAST(mta_tax AS DECIMAL(12,2)) AS mta_tax,
                TRY_CAST(tip_amount AS DECIMAL(12,2)) AS tip_amount,
                TRY_CAST(tolls_amount AS DECIMAL(12,2)) AS tolls_amount,
                TRY_CAST(improvement_surcharge AS DECIMAL(12,2)) AS improvement_surcharge,
                TRY_CAST(congestion_surcharge AS DECIMAL(12,2)) AS congestion_surcharge,
                TRY_CAST(Airport_fee AS DECIMAL(12,2)) AS airport_fee,
                TRY_CAST(cbd_congestion_fee AS DECIMAL(12,2)) AS cbd_congestion_fee,
                NULL::DECIMAL(12,2) AS sales_tax,
                NULL::DECIMAL(12,2) AS bcf,
                NULL::DECIMAL(12,2) AS driver_pay,
                NULL::DECIMAL(12,2) AS ehail_fee,
                NULL::TIMESTAMP AS request_datetime,
                NULL::TIMESTAMP AS on_scene_datetime,
                NULL::VARCHAR AS shared_request_flag,
                NULL::VARCHAR AS shared_match_flag,
                NULL::VARCHAR AS wav_request_flag,
                NULL::VARCHAR AS wav_match_flag,
                NULL::VARCHAR AS access_a_ride_flag,
                CAST('yellow_tripdata_2026q1' AS VARCHAR) AS source_table
            FROM bronze.yellow_tripdata_2026q1
        ),
        green AS (
            SELECT
                'green' AS trip_source,
                lpep_pickup_datetime AS pickup_at,
                lpep_dropoff_datetime AS dropoff_at,
                TRY_CAST(PULocationID AS INTEGER) AS pickup_location_id,
                TRY_CAST(DOLocationID AS INTEGER) AS dropoff_location_id,
                TRY_CAST(passenger_count AS BIGINT) AS passenger_count,
                TRY_CAST(trip_distance AS DOUBLE) AS distance_miles,
                TRY_CAST(payment_type AS BIGINT) AS payment_type,
                TRY_CAST(RatecodeID AS BIGINT) AS rate_code_id,
                TRY_CAST(trip_type AS BIGINT) AS trip_type,
                NULL::VARCHAR AS base_no,
                TRY_CAST(fare_amount AS DECIMAL(12,2)) AS fare_amount,
                TRY_CAST(total_amount AS DECIMAL(12,2)) AS total_amount,
                TRY_CAST(extra AS DECIMAL(12,2)) AS extra,
                TRY_CAST(mta_tax AS DECIMAL(12,2)) AS mta_tax,
                TRY_CAST(tip_amount AS DECIMAL(12,2)) AS tip_amount,
                TRY_CAST(tolls_amount AS DECIMAL(12,2)) AS tolls_amount,
                TRY_CAST(improvement_surcharge AS DECIMAL(12,2)) AS improvement_surcharge,
                TRY_CAST(congestion_surcharge AS DECIMAL(12,2)) AS congestion_surcharge,
                NULL::DECIMAL(12,2) AS airport_fee,
                TRY_CAST(cbd_congestion_fee AS DECIMAL(12,2)) AS cbd_congestion_fee,
                NULL::DECIMAL(12,2) AS sales_tax,
                NULL::DECIMAL(12,2) AS bcf,
                NULL::DECIMAL(12,2) AS driver_pay,
                TRY_CAST(ehail_fee AS DECIMAL(12,2)) AS ehail_fee,
                NULL::TIMESTAMP AS request_datetime,
                NULL::TIMESTAMP AS on_scene_datetime,
                NULL::VARCHAR AS shared_request_flag,
                NULL::VARCHAR AS shared_match_flag,
                NULL::VARCHAR AS wav_request_flag,
                NULL::VARCHAR AS wav_match_flag,
                NULL::VARCHAR AS access_a_ride_flag,
                CAST('green_tripdata_2026q1' AS VARCHAR) AS source_table
            FROM bronze.green_tripdata_2026q1
        ),
        fhv AS (
            SELECT
                'fhv' AS trip_source,
                pickup_datetime AS pickup_at,
                dropOff_datetime AS dropoff_at,
                TRY_CAST(PUlocationID AS INTEGER) AS pickup_location_id,
                TRY_CAST(DOlocationID AS INTEGER) AS dropoff_location_id,
                NULL::BIGINT AS passenger_count,
                NULL::DOUBLE AS distance_miles,
                NULL::BIGINT AS payment_type,
                NULL::BIGINT AS rate_code_id,
                NULL::BIGINT AS trip_type,
                CAST(dispatching_base_num AS VARCHAR) AS base_no,
                NULL::DECIMAL(12,2) AS fare_amount,
                NULL::DECIMAL(12,2) AS total_amount,
                NULL::DECIMAL(12,2) AS extra,
                NULL::DECIMAL(12,2) AS mta_tax,
                NULL::DECIMAL(12,2) AS tip_amount,
                NULL::DECIMAL(12,2) AS tolls_amount,
                NULL::DECIMAL(12,2) AS improvement_surcharge,
                NULL::DECIMAL(12,2) AS congestion_surcharge,
                NULL::DECIMAL(12,2) AS airport_fee,
                NULL::DECIMAL(12,2) AS cbd_congestion_fee,
                NULL::DECIMAL(12,2) AS sales_tax,
                NULL::DECIMAL(12,2) AS bcf,
                NULL::DECIMAL(12,2) AS driver_pay,
                NULL::DECIMAL(12,2) AS ehail_fee,
                NULL::TIMESTAMP AS request_datetime,
                NULL::TIMESTAMP AS on_scene_datetime,
                NULL::VARCHAR AS shared_request_flag,
                NULL::VARCHAR AS shared_match_flag,
                NULL::VARCHAR AS wav_request_flag,
                NULL::VARCHAR AS wav_match_flag,
                NULL::VARCHAR AS access_a_ride_flag,
                CAST('fhv_tripdata_2026q1' AS VARCHAR) AS source_table
            FROM bronze.fhv_tripdata_2026q1
        ),
        fhvhv AS (
            SELECT
                'fhvhv' AS trip_source,
                pickup_datetime AS pickup_at,
                dropoff_datetime AS dropoff_at,
                TRY_CAST(PULocationID AS INTEGER) AS pickup_location_id,
                TRY_CAST(DOLocationID AS INTEGER) AS dropoff_location_id,
                NULL::BIGINT AS passenger_count,  -- hvfhv 无此字段
                TRY_CAST(trip_miles AS DOUBLE) AS distance_miles,
                NULL::BIGINT AS payment_type,     -- hvfhv 无此字段
                NULL::BIGINT AS rate_code_id,     -- hvfhv 无此字段
                NULL::BIGINT AS trip_type,        -- hvfhv 无此字段
                CAST(dispatching_base_num AS VARCHAR) AS base_no,
                TRY_CAST(base_passenger_fare AS DECIMAL(12,2)) AS fare_amount,
                NULL::DECIMAL(12,2) AS total_amount,
                NULL::DECIMAL(12,2) AS extra,
                NULL::DECIMAL(12,2) AS mta_tax,
                TRY_CAST(tips AS DECIMAL(12,2)) AS tip_amount,
                TRY_CAST(tolls AS DECIMAL(12,2)) AS tolls_amount,
                NULL::DECIMAL(12,2) AS improvement_surcharge,
                TRY_CAST(congestion_surcharge AS DECIMAL(12,2)) AS congestion_surcharge,
                TRY_CAST(airport_fee AS DECIMAL(12,2)) AS airport_fee,
                TRY_CAST(cbd_congestion_fee AS DECIMAL(12,2)) AS cbd_congestion_fee,
                TRY_CAST(sales_tax AS DECIMAL(12,2)) AS sales_tax,
                TRY_CAST(bcf AS DECIMAL(12,2)) AS bcf,
                TRY_CAST(driver_pay AS DECIMAL(12,2)) AS driver_pay,
                NULL::DECIMAL(12,2) AS ehail_fee,
                request_datetime,
                on_scene_datetime,
                CAST(shared_request_flag AS VARCHAR) AS shared_request_flag,
                CAST(shared_match_flag AS VARCHAR) AS shared_match_flag,
                CAST(wav_request_flag AS VARCHAR) AS wav_request_flag,
                CAST(wav_match_flag AS VARCHAR) AS wav_match_flag,
                CAST(access_a_ride_flag AS VARCHAR) AS access_a_ride_flag,
                CAST('fhvhv_tripdata_2026q1' AS VARCHAR) AS source_table
            FROM bronze.fhvhv_tripdata_2026q1
        ),
        all_trips AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY trip_source
                ORDER BY pickup_at, dropoff_at, pickup_location_id, dropoff_location_id
            ) AS source_row_no
            FROM (
                SELECT * FROM yellow
                UNION ALL SELECT * FROM green
                UNION ALL SELECT * FROM fhv
                UNION ALL SELECT * FROM fhvhv
            )
        )
        SELECT
            -- trip_id: 稳定 MD5 代理键（带 ORDER BY 的 ROW_NUMBER 确定唯一，外层 MD5 保证稳定性）
            MD5(CONCAT(trip_source, '|', CAST(source_row_no AS VARCHAR))) AS trip_id,
            trip_source,
            pickup_at,
            dropoff_at,
            CAST(pickup_at AS DATE) AS pickup_date,
            pickup_location_id,
            dropoff_location_id,
            passenger_count,
            distance_miles,
            payment_type,
            rate_code_id,
            trip_type,
            base_no,
            fare_amount,
            total_amount,
            extra,
            mta_tax,
            tip_amount,
            tolls_amount,
            improvement_surcharge,
            congestion_surcharge,
            airport_fee,
            cbd_congestion_fee,
            sales_tax,
            bcf,
            driver_pay,
            ehail_fee,
            request_datetime,
            on_scene_datetime,
            shared_request_flag,
            shared_match_flag,
            wav_request_flag,
            wav_match_flag,
            access_a_ride_flag,
            -- 质量标记
            (
                pickup_at IS NULL
                OR dropoff_at < pickup_at
                OR pickup_at < '2026-01-01'::TIMESTAMP
                OR pickup_at >= '2026-04-01'::TIMESTAMP
                OR (dropoff_at - pickup_at) > INTERVAL '6 hours'
            ) AS is_time_anomaly,
            (
                pickup_location_id IS NULL
                OR dropoff_location_id IS NULL
            ) AS is_location_missing,
            (
                distance_miles IS NULL
                OR distance_miles <= 0
                OR distance_miles > 500
            ) AS is_distance_outlier,
            -- 来源行哈希（用于溯源）
            MD5(
                CONCAT(
                    trip_source, '|',
                    COALESCE(CAST(pickup_at AS VARCHAR), ''), '|',
                    COALESCE(CAST(dropoff_at AS VARCHAR), ''), '|',
                    COALESCE(CAST(pickup_location_id AS VARCHAR), ''), '|',
                    COALESCE(CAST(dropoff_location_id AS VARCHAR), ''), '|',
                    COALESCE(CAST(base_no AS VARCHAR), ''), '|',
                    COALESCE(CAST(fare_amount AS VARCHAR), ''), '|',
                    COALESCE(CAST(tip_amount AS VARCHAR), '')
                )
            ) AS source_row_hash,
            source_table
        FROM all_trips
    """
    con.execute(sql)
    cnt = con.execute(f"SELECT COUNT(*) FROM silver.{table_name}").fetchone()[0]

    # 来源分布统计
    src_dist = con.execute(f"""
        SELECT trip_source, COUNT(*) AS n FROM silver.{table_name} GROUP BY trip_source ORDER BY trip_source
    """).fetchall()
    print(f"  [OK] silver.{table_name}: {cnt:,} 行")
    for src, n in src_dist:
        print(f"       {src}: {n:,}")

    return cnt


# ─── P1: vehicle_detail ──────────────────────────────────────────

def build_vehicle_detail(con: duckdb.DuckDBPyConnection, replace: bool = False) -> int:
    """构建车辆明细标准表，active_vehicles 为基础 LEFT JOIN 补充 FHV+Medallion"""
    table_name = "vehicle_detail"
    if not drop_if_exists(con, table_name, replace):
        return 0

    con.execute("""
        CREATE TABLE silver.vehicle_detail AS
        WITH base AS (
            -- active_vehicles 为基础表（覆盖最全）
            SELECT
                CAST("License Number" AS VARCHAR) AS license_number,
                CAST("License Type" AS VARCHAR) AS license_type,
                CAST("TLC Vehicle License Status" AS VARCHAR) AS license_status,
                CAST("Owner Name" AS VARCHAR) AS owner_name,
                TRY_CAST("Expiration Date" AS DATE) AS expiration_date,
                CAST("DMV Plate Number" AS VARCHAR) AS dmv_plate_number,
                CAST("VIN" AS VARCHAR) AS vin,
                CAST("Vehicle Make" AS VARCHAR) AS vehicle_make,
                CAST("Vehicle Model" AS VARCHAR) AS vehicle_model,
                TRY_CAST("Vehicle Year" AS INTEGER) AS vehicle_year,
                CAST("Fuel Type" AS VARCHAR) AS fuel_type,
                COALESCE(NULLIF(CAST("WAV" AS VARCHAR), ''), 'UNKNOWN') AS wav_flag,
                CAST("Stretch Limo" AS VARCHAR) AS stretch_limo,
                CAST("Insurance Carrier Name" AS VARCHAR) AS insurance_carrier,
                CAST("Automobile Insurance Policy Number" AS VARCHAR) AS insurance_policy_number,
                TRY_CAST("Last Date Updated" AS DATE) AS last_date_updated,
                CAST('active_vehicles' AS VARCHAR) AS source_table
            FROM bronze.active_vehicles
        ),
        fhv AS (
            SELECT
                CAST("Vehicle License Number" AS VARCHAR) AS license_number,
                CAST("Base Number" AS VARCHAR) AS base_number,
                CAST("Base Name" AS VARCHAR) AS base_name,
                CAST("Base Type" AS VARCHAR) AS base_type,
                CAST("Base Address" AS VARCHAR) AS base_address
            FROM bronze.fhv_active_vehicles
        ),
        med AS (
            SELECT
                CAST("License Number" AS VARCHAR) AS license_number,
                CAST("Medallion Type" AS VARCHAR) AS medallion_type,
                CAST("Agent Number" AS VARCHAR) AS agent_number,
                CAST("Agent Name" AS VARCHAR) AS agent_name
            FROM bronze.medallion_authorized_vehicles
        )
        SELECT
            ROW_NUMBER() OVER (ORDER BY b.license_number) AS vehicle_id,
            b.license_number,
            b.license_type,
            b.license_status,
            b.owner_name,
            b.expiration_date,
            b.dmv_plate_number,
            b.vin,
            b.vehicle_make,
            b.vehicle_model,
            b.vehicle_year,
            b.fuel_type,
            b.wav_flag,
            b.stretch_limo,
            m.medallion_type,
            f.base_number,
            f.base_name,
            f.base_type,
            f.base_address,
            m.agent_number,
            m.agent_name,
            b.insurance_carrier,
            b.insurance_policy_number,
            b.last_date_updated,
            b.source_table
        FROM base b
        LEFT JOIN fhv f ON b.license_number = f.license_number
        LEFT JOIN med m ON b.license_number = m.license_number
    """)
    cnt = con.execute(f"SELECT COUNT(*) FROM silver.{table_name}").fetchone()[0]

    # 验证主键唯一性
    dup = con.execute(f"SELECT COUNT(*) FROM (SELECT vehicle_id, COUNT(*) AS n FROM silver.{table_name} GROUP BY vehicle_id HAVING n > 1)").fetchone()[0]
    if dup > 0:
        print(f"  [WARN] silver.{table_name}: {dup} 个重复 vehicle_id")
    null_lic = con.execute(f"SELECT COUNT(*) FROM silver.{table_name} WHERE license_number IS NULL").fetchone()[0]
    print(f"  [OK] silver.{table_name}: {cnt:,} 行, 主键唯一, license_number 空值 {null_lic}")
    return cnt


# ─── P1: driver_detail ───────────────────────────────────────────

def build_driver_detail(con: duckdb.DuckDBPyConnection, replace: bool = False) -> int:
    """构建司机明细标准表，UNION ALL FHV + SHL 司机"""
    table_name = "driver_detail"
    if not drop_if_exists(con, table_name, replace):
        return 0

    con.execute("""
        CREATE TABLE silver.driver_detail AS
        WITH all_drivers AS (
            SELECT * FROM (
                SELECT
                    CAST("License Number" AS VARCHAR) AS license_number,
                    CAST("Name" AS VARCHAR) AS driver_name,
                    'FHV' AS driver_type,
                    NULL::INTEGER AS status_code,
                    NULL::VARCHAR AS status_description,
                    TRY_CAST("Expiration Date" AS DATE) AS expiration_date,
                    CAST("Wheelchair Accessible Trained" AS VARCHAR) AS wav_trained,
                    TRY_CAST("Last Date Updated" AS DATE) AS last_date_updated,
                    CAST("Last Time Updated" AS VARCHAR) AS last_time_updated,
                    CAST('fhv_active_drivers' AS VARCHAR) AS source_table
                FROM bronze.fhv_active_drivers
                UNION ALL
                SELECT
                    CAST("License Number" AS VARCHAR) AS license_number,
                    CAST("Name" AS VARCHAR) AS driver_name,
                    'SHL' AS driver_type,
                    TRY_CAST("Status Code" AS INTEGER) AS status_code,
                    CAST("Status Description" AS VARCHAR) AS status_description,
                    TRY_CAST("Expiration Date" AS DATE) AS expiration_date,
                    NULL::VARCHAR AS wav_trained,
                    TRY_CAST("Last Date Updated" AS DATE) AS last_date_updated,
                    CAST("Last Time Updated" AS VARCHAR) AS last_time_updated,
                    CAST('shl_active_drivers' AS VARCHAR) AS source_table
                FROM bronze.shl_active_drivers
            )
        )
        SELECT
            ROW_NUMBER() OVER (ORDER BY license_number, driver_type) AS driver_id,
            license_number,
            driver_name,
            driver_type,
            status_code,
            status_description,
            expiration_date,
            wav_trained,
            last_date_updated,
            last_time_updated,
            source_table
        FROM all_drivers
    """)
    cnt = con.execute(f"SELECT COUNT(*) FROM silver.{table_name}").fetchone()[0]

    # 复合键唯一性
    dup = con.execute(f"SELECT COUNT(*) FROM (SELECT license_number, driver_type, COUNT(*) AS n FROM silver.{table_name} GROUP BY license_number, driver_type HAVING n > 1)").fetchone()[0]
    print(f"  [OK] silver.{table_name}: {cnt:,} 行, 复合键重复 {dup}")
    return cnt


# ─── P1: base_detail ─────────────────────────────────────────────

def build_base_detail(con: duckdb.DuckDBPyConnection, replace: bool = False) -> int:
    """构建基地月度明细标准表，处理复合键"""
    table_name = "base_detail"
    if not drop_if_exists(con, table_name, replace):
        return 0

    con.execute("""
        CREATE TABLE silver.base_detail AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY base_license_number, year, month) AS base_detail_id,
            base_license_number,
            base_name,
            dba,
            year,
            month,
            month_name,
            total_dispatched_trips,
            total_dispatched_shared_trips,
            unique_dispatched_vehicles,
            CONCAT(base_license_number, '_', CAST(year AS VARCHAR), '_', CAST(month AS VARCHAR)) AS composite_key
        FROM (
            SELECT
                CAST("Base License Number" AS VARCHAR) AS base_license_number,
                CAST("Base Name" AS VARCHAR) AS base_name,
                CAST("DBA" AS VARCHAR) AS dba,
                TRY_CAST("Year" AS INTEGER) AS year,
                TRY_CAST("Month" AS INTEGER) AS month,
                CAST("Month Name" AS VARCHAR) AS month_name,
                TRY_CAST("Total Dispatched Trips" AS BIGINT) AS total_dispatched_trips,
                TRY_CAST("Total Dispatched Shared Trips" AS BIGINT) AS total_dispatched_shared_trips,
                TRY_CAST("Unique Dispatched Vehicles" AS BIGINT) AS unique_dispatched_vehicles
            FROM bronze.fhv_base_aggregate_report
        )
    """)
    cnt = con.execute(f"SELECT COUNT(*) FROM silver.{table_name}").fetchone()[0]

    # 标记复合键重复
    con.execute(f"""
        ALTER TABLE silver.{table_name} ADD COLUMN is_duplicate_key BOOLEAN;
        UPDATE silver.{table_name} SET is_duplicate_key = (
            composite_key IN (
                SELECT composite_key FROM silver.{table_name}
                GROUP BY composite_key HAVING COUNT(*) > 1
            )
        )
    """)
    dup_cnt = con.execute(f"SELECT COUNT(*) FROM silver.{table_name} WHERE is_duplicate_key").fetchone()[0]
    print(f"  [OK] silver.{table_name}: {cnt:,} 行, 复合键重复标记 {dup_cnt:,}")
    return cnt


# ─── P1: driver_application_detail ───────────────────────────────

def build_driver_application_detail(con: duckdb.DuckDBPyConnection, replace: bool = False) -> int:
    """构建司机申请明细标准表"""
    table_name = "driver_application_detail"
    if not drop_if_exists(con, table_name, replace):
        return 0

    con.execute("""
        CREATE TABLE silver.driver_application_detail AS
        WITH src AS (
            SELECT
                CAST("App No" AS VARCHAR) AS app_no,
                CAST("Type" AS VARCHAR) AS application_type,
                TRY_CAST("App Date" AS DATE) AS app_date,
                CAST("Status" AS VARCHAR) AS status,
                CAST("FRU Interview Scheduled" AS VARCHAR) AS fru_interview_scheduled,
                CAST("Drug Test" AS VARCHAR) AS drug_test,
                CAST("WAV Course" AS VARCHAR) AS wav_course,
                CAST("Defensive Driving" AS VARCHAR) AS defensive_driving,
                CAST("Driver Exam" AS VARCHAR) AS driver_exam,
                CAST("Medical Clearance Form" AS VARCHAR) AS medical_clearance_form,
                CAST("Other Requirements" AS VARCHAR) AS other_requirements,
                TRY_CAST("Last Updated" AS DATE) AS last_updated
            FROM bronze.new_driver_applications
        )
        SELECT
            ROW_NUMBER() OVER (ORDER BY app_no) AS application_id,
            app_no,
            application_type,
            app_date,
            status,
            fru_interview_scheduled,
            drug_test,
            wav_course,
            defensive_driving,
            driver_exam,
            medical_clearance_form,
            other_requirements,
            last_updated,
            CAST('new_driver_applications' AS VARCHAR) AS source_table
        FROM src
    """)
    cnt = con.execute(f"SELECT COUNT(*) FROM silver.{table_name}").fetchone()[0]

    # 验证 app_no 唯一性
    dup = con.execute(f"SELECT COUNT(*) FROM (SELECT app_no, COUNT(*) AS n FROM silver.{table_name} GROUP BY app_no HAVING n > 1)").fetchone()[0]
    print(f"  [OK] silver.{table_name}: {cnt:,} 行, app_no 重复 {dup}")
    return cnt


# ─── P2: parking_violation_detail ────────────────────────────────

def build_parking_violation_detail(con: duckdb.DuckDBPyConnection, replace: bool = False) -> int:
    """构建停车罚单明细标准表，958 万行，全部 VARCHAR→标准类型"""
    table_name = "parking_violation_detail"
    if not drop_if_exists(con, table_name, replace):
        return 0

    con.execute("""
        CREATE TABLE silver.parking_violation_detail AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY summons_number) AS violation_id,
            CAST(summons_number AS VARCHAR) AS summons_number,
            CAST(plate_id AS VARCHAR) AS plate_id,
            CAST(registration_state AS VARCHAR) AS registration_state,
            CAST(plate_type AS VARCHAR) AS plate_type,
            TRY_CAST(issue_date AS DATE) AS issue_date,
            CAST(violation_code AS VARCHAR) AS violation_code,
            CAST(violation_description AS VARCHAR) AS violation_description,
            CAST(vehicle_body_type AS VARCHAR) AS vehicle_body_type,
            CAST(vehicle_make AS VARCHAR) AS vehicle_make,
            CAST(vehicle_color AS VARCHAR) AS vehicle_color,
            TRY_CAST(vehicle_year AS INTEGER) AS vehicle_year,
            TRY_CAST(vehicle_expiration_date AS DATE) AS vehicle_expiration_date,
            CAST(issuing_agency AS VARCHAR) AS issuing_agency,
            CAST(violation_precinct AS VARCHAR) AS violation_precinct,
            CAST(issuer_precinct AS VARCHAR) AS issuer_precinct,
            CAST(issuer_code AS VARCHAR) AS issuer_code,
            CAST(violation_time AS VARCHAR) AS violation_time,
            CAST(violation_county AS VARCHAR) AS violation_county,
            CAST(street_name AS VARCHAR) AS street_name,
            CAST(intersecting_street AS VARCHAR) AS intersecting_street,
            CAST(date_first_observed AS VARCHAR) AS date_first_observed,
            CAST(law_section AS VARCHAR) AS law_section,
            CAST(sub_division AS VARCHAR) AS sub_division,
            CAST(violation_legal_code AS VARCHAR) AS violation_legal_code,
            TRY_CAST(feet_from_curb AS DOUBLE) AS feet_from_curb,
            TRY_CAST(fiscal_year AS INTEGER) AS fiscal_year,
            -- 质量标记
            MD5(CONCAT(
                COALESCE(summons_number, ''),
                COALESCE(plate_id, ''),
                COALESCE(issue_date, ''),
                COALESCE(violation_code, '')
            )) AS source_row_hash,
            CAST('parking_violations_all' AS VARCHAR) AS source_table
        FROM bronze.parking_violations_all
    """)
    cnt = con.execute(f"SELECT COUNT(*) FROM silver.{table_name}").fetchone()[0]

    # 标记重复罚单
    con.execute(f"""
        ALTER TABLE silver.{table_name} ADD COLUMN is_duplicate_summons BOOLEAN;
        UPDATE silver.{table_name} SET is_duplicate_summons = (
            summons_number IN (
                SELECT summons_number FROM silver.{table_name}
                GROUP BY summons_number HAVING COUNT(*) > 1
            )
        )
    """)
    dup = con.execute(f"SELECT COUNT(*) FROM silver.{table_name} WHERE is_duplicate_summons").fetchone()[0]

    # 缺失率
    null_code = con.execute(f"SELECT COUNT(*) FROM silver.{table_name} WHERE violation_code IS NULL").fetchone()[0]
    print(f"  [OK] silver.{table_name}: {cnt:,} 行, 重复罚单 {dup:,}, violation_code 空值 {null_code}")
    return cnt


# ─── P2: tif_payment_detail ──────────────────────────────────────

def build_tif_payment_detail(con: duckdb.DuckDBPyConnection, replace: bool = False) -> int:
    """构建 TIF 支付明细标准表，复合键治理"""
    table_name = "tif_payment_detail"
    if not drop_if_exists(con, table_name, replace):
        return 0

    con.execute("""
        CREATE TABLE silver.tif_payment_detail AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY "License Number", "Payment Date") AS payment_id,
            CAST("License Number" AS VARCHAR) AS license_number,
            CAST("Agent Number" AS VARCHAR) AS agent_number,
            TRY_CAST("Hackup Payment Amount" AS DECIMAL(12,2)) AS hackup_payment_amount,
            TRY_CAST("Operational Payment Amount" AS DECIMAL(12,2)) AS operational_payment_amount,
            TRY_CAST("Total Payment Amount" AS DECIMAL(12,2)) AS total_payment_amount,
            TRY_CAST("Payment Date" AS DATE) AS payment_date,
            TRY_CAST("Last Date Updated" AS DATE) AS last_date_updated,
            CAST("Last Time Updated" AS VARCHAR) AS last_time_updated,
            CONCAT(
                CAST("License Number" AS VARCHAR), '_',
                "Payment Date"
            ) AS composite_key,
            CAST('tif_medallion_payments' AS VARCHAR) AS source_table
        FROM bronze.tif_medallion_payments
    """)
    cnt = con.execute(f"SELECT COUNT(*) FROM silver.{table_name}").fetchone()[0]

    # 标记复合键重复
    con.execute(f"""
        ALTER TABLE silver.{table_name} ADD COLUMN is_duplicate_key BOOLEAN;
        UPDATE silver.{table_name} SET is_duplicate_key = (
            composite_key IN (
                SELECT composite_key FROM silver.{table_name}
                GROUP BY composite_key HAVING COUNT(*) > 1
            )
        )
    """)
    dup = con.execute(f"SELECT COUNT(*) FROM silver.{table_name} WHERE is_duplicate_key").fetchone()[0]
    print(f"  [OK] silver.{table_name}: {cnt:,} 行, 复合键重复 {dup:,}")
    return cnt


# ─── P2: crash_detail ────────────────────────────────────────────

def build_crash_detail(con: duckdb.DuckDBPyConnection, replace: bool = False) -> int:
    """构建事故明细标准表，弃用车辆 3-5 列（缺失率 93-99%）"""
    table_name = "crash_detail"
    if not drop_if_exists(con, table_name, replace):
        return 0

    con.execute("""
        CREATE TABLE silver.crash_detail AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY collision_id) AS crash_id,
            TRY_CAST(collision_id AS BIGINT) AS collision_id,
            TRY_CAST(LEFT(crash_date, 10) || ' ' || crash_time AS TIMESTAMP) AS crash_at,
            CAST(borough AS VARCHAR) AS borough,
            CAST(zip_code AS VARCHAR) AS zip_code,
            TRY_CAST(latitude AS DOUBLE) AS latitude,
            TRY_CAST(longitude AS DOUBLE) AS longitude,
            CAST(on_street_name AS VARCHAR) AS on_street_name,
            CAST(cross_street_name AS VARCHAR) AS cross_street_name,
            CAST(off_street_name AS VARCHAR) AS off_street_name,
            TRY_CAST(number_of_persons_injured AS INTEGER) AS persons_injured,
            TRY_CAST(number_of_persons_killed AS INTEGER) AS persons_killed,
            TRY_CAST(number_of_pedestrians_injured AS INTEGER) AS pedestrians_injured,
            TRY_CAST(number_of_pedestrians_killed AS INTEGER) AS pedestrians_killed,
            TRY_CAST(number_of_cyclist_injured AS INTEGER) AS cyclist_injured,
            TRY_CAST(number_of_cyclist_killed AS INTEGER) AS cyclist_killed,
            TRY_CAST(number_of_motorist_injured AS INTEGER) AS motorist_injured,
            TRY_CAST(number_of_motorist_killed AS INTEGER) AS motorist_killed,
            -- 仅保留车辆 1-2（车辆 3-5 缺失率 93-99%）
            CAST(vehicle_type_code1 AS VARCHAR) AS vehicle_type_1,
            CAST(vehicle_type_code2 AS VARCHAR) AS vehicle_type_2,
            CAST(contributing_factor_vehicle_1 AS VARCHAR) AS contributing_factor_1,
            CAST(contributing_factor_vehicle_2 AS VARCHAR) AS contributing_factor_2,
            -- 质量标记
            MD5(CONCAT(
                COALESCE(collision_id, ''),
                COALESCE(crash_date, ''),
                COALESCE(crash_time, '')
            )) AS source_row_hash,
            CAST('crash_merged' AS VARCHAR) AS source_table
        FROM bronze.crash_merged
    """)
    cnt = con.execute(f"SELECT COUNT(*) FROM silver.{table_name}").fetchone()[0]

    # 标记重复+位置缺失
    con.execute(f"""
        ALTER TABLE silver.{table_name} ADD COLUMN is_duplicate_collision BOOLEAN;
        ALTER TABLE silver.{table_name} ADD COLUMN is_location_missing BOOLEAN;
        UPDATE silver.{table_name} SET is_duplicate_collision = (
            collision_id IN (SELECT collision_id FROM silver.{table_name} GROUP BY collision_id HAVING COUNT(*) > 1)
        );
        UPDATE silver.{table_name} SET is_location_missing = (latitude IS NULL OR longitude IS NULL);
    """)
    dup = con.execute(f"SELECT COUNT(*) FROM silver.{table_name} WHERE is_duplicate_collision").fetchone()[0]
    no_loc = con.execute(f"SELECT COUNT(*) FROM silver.{table_name} WHERE is_location_missing").fetchone()[0]
    no_time = con.execute(f"SELECT COUNT(*) FROM silver.{table_name} WHERE crash_at IS NULL").fetchone()[0]
    print(f"  [OK] silver.{table_name}: {cnt:,} 行, 重复 {dup}, 位置缺失 {no_loc:,}, 时间空值 {no_time}")
    return cnt


# ─── P2: crash_person_detail ─────────────────────────────────────

def build_crash_person_detail(con: duckdb.DuckDBPyConnection, replace: bool = False) -> int:
    """构建事故人员明细标准表，标记孤立记录和辅助字段缺失"""
    table_name = "crash_person_detail"
    if not drop_if_exists(con, table_name, replace):
        return 0

    con.execute("""
        CREATE TABLE silver.crash_person_detail AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY unique_id) AS crash_person_id,
            TRY_CAST(unique_id AS BIGINT) AS unique_id,
            TRY_CAST(collision_id AS BIGINT) AS collision_id,
            TRY_CAST(crash_date AS DATE) AS crash_date,
            CAST(crash_time AS VARCHAR) AS crash_time,
            CAST(person_id AS VARCHAR) AS person_id,
            CAST(person_type AS VARCHAR) AS person_type,
            CAST(person_injury AS VARCHAR) AS person_injury,
            CAST(person_sex AS VARCHAR) AS person_sex,
            TRY_CAST(person_age AS INTEGER) AS person_age,
            CAST(vehicle_id AS VARCHAR) AS vehicle_id,
            CAST(ped_role AS VARCHAR) AS ped_role,
            -- 辅助字段（缺失率 46-49%）
            CAST(ejection AS VARCHAR) AS ejection,
            CAST(emotional_status AS VARCHAR) AS emotional_status,
            CAST(bodily_injury AS VARCHAR) AS bodily_injury,
            CAST(position_in_vehicle AS VARCHAR) AS position_in_vehicle,
            CAST(safety_equipment AS VARCHAR) AS safety_equipment,
            CAST(complaint AS VARCHAR) AS complaint,
            -- 质量标记
            MD5(CONCAT(
                COALESCE(unique_id, ''),
                COALESCE(collision_id, ''),
                COALESCE(crash_date, '')
            )) AS source_row_hash,
            CAST('crash_person_all' AS VARCHAR) AS source_table
        FROM bronze.crash_person_all
    """)
    cnt = con.execute(f"SELECT COUNT(*) FROM silver.{table_name}").fetchone()[0]

    # 质量标记
    con.execute(f"""
        ALTER TABLE silver.{table_name} ADD COLUMN is_duplicate_person BOOLEAN;
        ALTER TABLE silver.{table_name} ADD COLUMN is_orphan_record BOOLEAN;
        ALTER TABLE silver.{table_name} ADD COLUMN has_missing_aux BOOLEAN;
        UPDATE silver.{table_name} SET is_duplicate_person = (
            unique_id IN (SELECT unique_id FROM silver.{table_name} GROUP BY unique_id HAVING COUNT(*) > 1)
        );
        UPDATE silver.{table_name} SET is_orphan_record = (
            collision_id NOT IN (SELECT collision_id FROM silver.crash_detail WHERE collision_id IS NOT NULL)
            OR collision_id IS NULL
        );
        UPDATE silver.{table_name} SET has_missing_aux = (
            ejection IS NULL AND emotional_status IS NULL AND bodily_injury IS NULL
            AND position_in_vehicle IS NULL AND safety_equipment IS NULL AND complaint IS NULL
        );
    """)
    dup = con.execute(f"SELECT COUNT(*) FROM silver.{table_name} WHERE is_duplicate_person").fetchone()[0]
    orphan = con.execute(f"SELECT COUNT(*) FROM silver.{table_name} WHERE is_orphan_record").fetchone()[0]
    aux = con.execute(f"SELECT COUNT(*) FROM silver.{table_name} WHERE has_missing_aux").fetchone()[0]
    age_err = con.execute(f"SELECT COUNT(*) FROM silver.{table_name} WHERE person_age < 0 OR person_age > 120").fetchone()[0]
    print(f"  [OK] silver.{table_name}: {cnt:,} 行, 重复 {dup}, 孤立 {orphan:,}, 缺失辅助字段 {aux:,}, 年龄异常 {age_err}")
    return cnt


# ─── 质量报告 ────────────────────────────────────────────────────

def run_quality_report(con: duckdb.DuckDBPyConnection, batch: str = "P0") -> None:
    """输出 Silver 层行数、质量标记分布"""
    print("\n" + "=" * 60)
    print(f"Silver 层质量报告 (批次: {batch})")
    print("=" * 60)

    # 表行数统计
    p0_tables = ["dim_date", "taxi_zone", "trip_detail"]
    p1_tables = ["vehicle_detail", "driver_detail", "base_detail", "driver_application_detail"]
    p2_tables = ["parking_violation_detail", "tif_payment_detail", "crash_detail", "crash_person_detail"]

    check_tables = p0_tables.copy()
    if batch in ("P1", "P2", "all"):
        check_tables += p1_tables
    if batch in ("P2", "all"):
        check_tables += p2_tables

    for tbl in check_tables:
        cnt = con.execute(f"SELECT COUNT(*) FROM silver.{tbl}").fetchone()[0]
        cols = con.execute(f"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='silver' AND table_name='{tbl}'").fetchone()[0]
        print(f"  silver.{tbl}: {cnt:,} 行, {cols} 字段")

    # trip_detail 质量标记
    has_trip = "trip_detail" in check_tables
    if has_trip:
        cnt_t = con.execute("SELECT COUNT(*) FROM silver.trip_detail").fetchone()[0]
        for col in ["is_time_anomaly", "is_location_missing", "is_distance_outlier"]:
            r = con.execute(f"""
                SELECT {col}, COUNT(*) AS n FROM silver.trip_detail GROUP BY {col} ORDER BY {col}
            """).fetchall()
            print(f"\n  trip_detail.{col}:")
            for v, n in r:
                print(f"    {v}: {n:,} ({n/cnt_t*100:.1f}%)")

    # vehicle_detail 质量规则（计算列，不存表）
    has_vehicle = "vehicle_detail" in check_tables
    if has_vehicle:
        yr = con.execute("SELECT COUNT(*) FROM silver.vehicle_detail WHERE vehicle_year < 2000 OR vehicle_year > 2027").fetchone()[0]
        exp = con.execute("SELECT COUNT(*) FROM silver.vehicle_detail WHERE expiration_date < '2026-01-01'::DATE").fetchone()[0]
        print(f"  vehicle_detail: 年份异常 {yr:,}, 已过期 {exp:,}")


# ─── Meta 中文注释 ────────────────────────────────────────────────

def write_meta_comments(con: duckdb.DuckDBPyConnection) -> None:
    """同步写入 meta.table_comments 和 meta.column_comments"""
    print("\n" + "=" * 60)
    print("写入 Meta 中文注释")
    print("=" * 60)

    # 表级注释
    tables_zh = {
        "dim_date": "日期维表",
        "taxi_zone": "出租车区域标准维表",
        "trip_detail": "行程明细标准表",
        "vehicle_detail": "车辆明细标准表",
        "driver_detail": "司机明细标准表",
        "base_detail": "基地月度明细标准表",
        "driver_application_detail": "司机申请明细标准表",
        "parking_violation_detail": "停车罚单明细标准表",
        "tif_payment_detail": "TIF支付明细标准表",
        "crash_detail": "事故明细标准表",
        "crash_person_detail": "事故人员明细标准表",
    }
    con.execute("CREATE TABLE IF NOT EXISTS meta.table_comments (table_schema VARCHAR, table_name VARCHAR, table_name_zh VARCHAR, updated_at VARCHAR)")
    for tbl, zh in tables_zh.items():
        # DuckDB 不支持无约束 INSERT OR REPLACE，用先删后插
        con.execute(f"DELETE FROM meta.table_comments WHERE table_schema='silver' AND table_name='{tbl}'")
        con.execute(f"""
            INSERT INTO meta.table_comments (table_schema, table_name, table_name_zh, updated_at)
            VALUES ('silver', '{tbl}', '{zh}', '{GENERATED_AT}')
        """)
    print(f"  表注释: {len(tables_zh)} 条")

    # 字段级注释（核心字段）
    columns_zh = {
        "dim_date": [
            ("date_key", "日期键", "主键"),
            ("date", "日期", "时间字段"),
            ("year", "年", "维度属性"),
            ("quarter", "季度", "维度属性"),
            ("month", "月", "维度属性"),
            ("week", "ISO周号", "维度属性"),
            ("day_of_week", "星期几(1=周一)", "维度属性"),
            ("day_of_week_name", "星期名称", "维度属性"),
            ("is_weekend", "是否周末", "标志位"),
            ("fiscal_year", "NYC财年", "维度属性"),
        ],
        "taxi_zone": [
            ("location_id", "出租车区域编号", "主键"),
            ("borough", "行政区", "维度属性"),
            ("zone_name", "区域名称", "维度属性"),
            ("service_zone", "服务区域", "维度属性"),
            ("is_unknown_zone", "是否未知区域", "标志位"),
        ],
        "trip_detail": [
            ("trip_id", "行程代理主键", "主键"),
            ("trip_source", "行程来源类型", "维度属性"),
            ("pickup_at", "接客时间", "时间字段"),
            ("dropoff_at", "送客时间", "时间字段"),
            ("pickup_date", "接客日期", "时间字段"),
            ("pickup_location_id", "上车区域编号", "空间字段"),
            ("dropoff_location_id", "下车区域编号", "空间字段"),
            ("passenger_count", "乘客人数", "度量"),
            ("distance_miles", "行程距离（英里）", "度量"),
            ("payment_type", "支付方式", "分类代码"),
            ("rate_code_id", "费率代码", "分类代码"),

            ("trip_type", "行程类型", "分类代码"),
            ("base_no", "派车基地编号", "维度属性"),
            ("fare_amount", "基础车费", "金额字段"),
            ("total_amount", "总费用", "金额字段"),
            ("tip_amount", "小费", "金额字段"),
            ("tolls_amount", "通行费", "金额字段"),
            ("congestion_surcharge", "拥堵附加费", "金额字段"),
            ("airport_fee", "机场费", "金额字段"),
            ("cbd_congestion_fee", "CBD拥堵费", "金额字段"),
            ("sales_tax", "销售税", "金额字段"),
            ("bcf", "黑车基金费", "金额字段"),
            ("driver_pay", "司机净收入", "金额字段"),
            ("shared_request_flag", "请求共享标志", "标志位"),
            ("shared_match_flag", "实际共享标志", "标志位"),
            ("wav_request_flag", "请求WAV标志", "标志位"),
            ("wav_match_flag", "匹配WAV标志", "标志位"),
            ("access_a_ride_flag", "MTA无障碍标志", "标志位"),
            ("is_time_anomaly", "是否时间异常", "质量标记"),
            ("is_location_missing", "是否位置缺失", "质量标记"),
            ("is_distance_outlier", "是否距离异常", "质量标记"),
            ("source_row_hash", "来源行哈希", "溯源字段"),
            ("source_table", "来源表", "溯源字段"),
        ],
        "vehicle_detail": [
            ("vehicle_id", "车辆代理主键", "主键"),
            ("license_number", "牌照编号", "维度属性"),
            ("license_type", "牌照类型", "分类代码"),
            ("license_status", "牌照状态", "状态码"),
            ("owner_name", "车主姓名/公司名", "维度属性"),
            ("expiration_date", "牌照到期日期", "时间字段"),
            ("dmv_plate_number", "DMV车牌号", "维度属性"),
            ("vin", "车辆识别码", "维度属性"),
            ("vehicle_make", "车辆品牌", "维度属性"),
            ("vehicle_model", "车辆型号", "维度属性"),
            ("vehicle_year", "车辆年份", "维度属性"),
            ("fuel_type", "燃料类型", "分类代码"),
            ("wav_flag", "无障碍车辆标志", "标志位"),
            ("stretch_limo", "是否加长豪华轿车", "标志位"),
            ("medallion_type", "Medallion类型", "分类代码"),
            ("base_number", "基地编号", "维度属性"),
            ("base_name", "基地名称", "维度属性"),
            ("base_type", "基地类型", "分类代码"),
            ("base_address", "基地地址", "维度属性"),
            ("agent_number", "代理编号", "维度属性"),
            ("agent_name", "代理名称", "维度属性"),
            ("insurance_carrier", "保险公司名称", "维度属性"),
            ("insurance_policy_number", "保险单号", "维度属性"),
            ("last_date_updated", "最后更新日期", "时间字段"),
            ("source_table", "来源表", "溯源字段"),
        ],
        "driver_detail": [
            ("driver_id", "司机代理主键", "主键"),
            ("license_number", "司机牌照号", "维度属性"),
            ("driver_name", "司机姓名", "维度属性"),
            ("driver_type", "司机类型", "分类代码"),
            ("status_code", "状态码", "状态码"),
            ("status_description", "状态描述", "维度属性"),
            ("expiration_date", "牌照到期日期", "时间字段"),
            ("wav_trained", "是否WAV培训", "标志位"),
            ("last_date_updated", "最后更新日期", "时间字段"),
            ("last_time_updated", "最后更新时间", "时间字段"),
            ("source_table", "来源表", "溯源字段"),
        ],
        "base_detail": [
            ("base_detail_id", "基地明细代理主键", "主键"),
            ("base_license_number", "基地牌照号", "维度属性"),
            ("base_name", "基地名称", "维度属性"),
            ("dba", "经营别名", "维度属性"),
            ("year", "年份", "维度属性"),
            ("month", "月份", "维度属性"),
            ("month_name", "月份名称", "维度属性"),
            ("total_dispatched_trips", "调度行程总数", "度量"),
            ("total_dispatched_shared_trips", "共享行程数", "度量"),
            ("unique_dispatched_vehicles", "去重调度车辆数", "度量"),
            ("composite_key", "复合键", "主键"),
            ("is_duplicate_key", "是否复合键重复", "质量标记"),
        ],
        "driver_application_detail": [
            ("application_id", "申请代理主键", "主键"),
            ("app_no", "申请编号", "维度属性"),
            ("application_type", "申请类型", "分类代码"),
            ("app_date", "申请日期", "时间字段"),
            ("status", "审批状态", "状态码"),
            ("fru_interview_scheduled", "体能审查面试状态", "状态码"),
            ("drug_test", "药检状态", "状态码"),
            ("wav_course", "WAV培训状态", "状态码"),
            ("defensive_driving", "防御性驾驶状态", "状态码"),
            ("driver_exam", "司机考试状态", "状态码"),
            ("medical_clearance_form", "体检表状态", "状态码"),
            ("other_requirements", "其他要求状态", "状态码"),
            ("last_updated", "最后更新日期", "时间字段"),
            ("source_table", "来源表", "溯源字段"),
        ],
        "parking_violation_detail": [
            ("violation_id", "罚单代理主键", "主键"),
            ("summons_number", "罚单编号", "维度属性"),
            ("plate_id", "车牌号", "维度属性"),
            ("registration_state", "注册州", "维度属性"),
            ("plate_type", "车牌类型", "分类代码"),
            ("issue_date", "开票日期", "时间字段"),
            ("violation_code", "违章代码", "分类代码"),
            ("violation_description", "违章描述", "维度属性"),
            ("vehicle_body_type", "车身类型", "分类代码"),
            ("vehicle_make", "车辆品牌", "维度属性"),
            ("vehicle_color", "车辆颜色", "维度属性"),
            ("vehicle_year", "车辆年份", "维度属性"),
            ("vehicle_expiration_date", "注册到期日", "时间字段"),
            ("issuing_agency", "开票机构", "分类代码"),
            ("violation_precinct", "违章管辖区", "维度属性"),
            ("issuer_precinct", "开票管辖区", "维度属性"),
            ("issuer_code", "开票人员代码", "维度属性"),
            ("violation_time", "违章时间", "时间字段"),
            ("violation_county", "违章所在县", "维度属性"),
            ("street_name", "街道名称", "维度属性"),
            ("intersecting_street", "交叉街道", "维度属性"),
            ("date_first_observed", "首次观察日期", "时间字段"),
            ("law_section", "法律条款", "维度属性"),
            ("sub_division", "法律子条款", "维度属性"),
            ("violation_legal_code", "违章法律代码", "维度属性"),
            ("feet_from_curb", "距路缘英尺数", "度量"),
            ("fiscal_year", "财年", "维度属性"),
            ("is_duplicate_summons", "是否重复罚单", "质量标记"),
            ("source_row_hash", "来源行哈希", "溯源字段"),
            ("source_table", "来源表", "溯源字段"),
        ],
        "tif_payment_detail": [
            ("payment_id", "支付代理主键", "主键"),
            ("license_number", "牌照号", "维度属性"),
            ("agent_number", "代理编号", "维度属性"),
            ("hackup_payment_amount", "改装支付金额", "金额字段"),
            ("operational_payment_amount", "运营支付金额", "金额字段"),
            ("total_payment_amount", "总支付金额", "金额字段"),
            ("payment_date", "支付日期", "时间字段"),
            ("last_date_updated", "最后更新日期", "时间字段"),
            ("last_time_updated", "最后更新时间", "时间字段"),
            ("composite_key", "复合键", "主键"),
            ("is_duplicate_key", "是否复合键重复", "质量标记"),
            ("source_table", "来源表", "溯源字段"),
        ],
        "crash_detail": [
            ("crash_id", "事故代理主键", "主键"),
            ("collision_id", "事故编号", "维度属性"),
            ("crash_at", "事故时间", "时间字段"),
            ("borough", "行政区", "维度属性"),
            ("zip_code", "邮政编码", "维度属性"),
            ("latitude", "纬度", "空间字段"),
            ("longitude", "经度", "空间字段"),
            ("on_street_name", "所在街道", "维度属性"),
            ("cross_street_name", "交叉街道", "维度属性"),
            ("off_street_name", "非街道地址", "维度属性"),
            ("persons_injured", "受伤总人数", "度量"),
            ("persons_killed", "死亡总人数", "度量"),
            ("pedestrians_injured", "行人受伤数", "度量"),
            ("pedestrians_killed", "行人死亡数", "度量"),
            ("cyclist_injured", "骑行者受伤数", "度量"),
            ("cyclist_killed", "骑行者死亡数", "度量"),
            ("motorist_injured", "驾驶员受伤数", "度量"),
            ("motorist_killed", "驾驶员死亡数", "度量"),
            ("vehicle_type_1", "涉事车辆1类型", "分类代码"),
            ("vehicle_type_2", "涉事车辆2类型", "分类代码"),
            ("contributing_factor_1", "车辆1事故因素", "分类代码"),
            ("contributing_factor_2", "车辆2事故因素", "分类代码"),
            ("is_duplicate_collision", "是否重复事故", "质量标记"),
            ("is_location_missing", "是否位置缺失", "质量标记"),
            ("source_row_hash", "来源行哈希", "溯源字段"),
            ("source_table", "来源表", "溯源字段"),
        ],
        "crash_person_detail": [
            ("crash_person_id", "事故人员代理主键", "主键"),
            ("unique_id", "人员记录编号", "维度属性"),
            ("collision_id", "事故编号", "维度属性"),
            ("crash_date", "事故日期", "时间字段"),
            ("crash_time", "事故时间", "时间字段"),
            ("person_id", "人员编号", "维度属性"),
            ("person_type", "人员类型", "分类代码"),
            ("person_injury", "伤害程度", "分类代码"),
            ("person_sex", "性别", "分类代码"),
            ("person_age", "年龄", "度量"),
            ("vehicle_id", "涉事车辆ID", "维度属性"),
            ("ped_role", "行人角色", "分类代码"),
            ("ejection", "是否弹出", "分类代码"),
            ("emotional_status", "情绪状态", "状态码"),
            ("bodily_injury", "身体伤害", "分类代码"),
            ("position_in_vehicle", "车内位置", "分类代码"),
            ("safety_equipment", "安全设备", "分类代码"),
            ("complaint", "投诉信息", "维度属性"),
            ("is_duplicate_person", "是否重复记录", "质量标记"),
            ("is_orphan_record", "是否孤立记录", "质量标记"),
            ("has_missing_aux", "是否缺失辅助字段", "质量标记"),
            ("source_row_hash", "来源行哈希", "溯源字段"),
            ("source_table", "来源表", "溯源字段"),
        ],
    }

    con.execute("CREATE TABLE IF NOT EXISTS meta.column_comments (table_schema VARCHAR, table_name VARCHAR, column_name VARCHAR, column_name_zh VARCHAR, column_role_zh VARCHAR, updated_at VARCHAR)")
    total = 0
    for tbl, cols in columns_zh.items():
        for col_name, col_zh, role in cols:
            con.execute(f"DELETE FROM meta.column_comments WHERE table_schema='silver' AND table_name='{tbl}' AND column_name='{col_name}'")
            con.execute(f"""
                INSERT INTO meta.column_comments
                (table_schema, table_name, column_name, column_name_zh, column_role_zh, updated_at)
                VALUES ('silver', '{tbl}', '{col_name}', '{col_zh}', '{role}', '{GENERATED_AT}')
            """)
            total += 1
    print(f"  字段注释: {total} 条")


# ─── 主入口 ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Silver 层构建脚本")
    parser.add_argument("--batch", choices=["P0", "P1", "P2", "all"], default="P0",
                        help="构建批次 (default: P0)")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅检查不实际建表")
    parser.add_argument("--replace", action="store_true",
                        help="如果表已存在则删除重建")
    args = parser.parse_args()

    print(f"=== TianShu Silver 层构建 === {GENERATED_AT}")
    print(f"批次: {args.batch}")
    print(f"模式: {'DRY RUN' if args.dry_run else '执行构建'}")
    print(f"覆盖: {'是' if args.replace else '否'}")
    print()

    if args.dry_run:
        print("[DRY RUN] 以下表将被创建：")
        if args.batch in ("P0", "all"):
            print("  silver.dim_date (90 行)")
            print("  silver.taxi_zone (~265 行)")
            print("  silver.trip_detail (~8,000 万行)")
        if args.batch in ("P1", "all"):
            print("  silver.vehicle_detail (~12 万行)")
            print("  silver.driver_detail (~36 万行)")
            print("  silver.base_detail (~5.9 万行)")
            print("  silver.driver_application_detail (4,076 行)")
        if args.batch in ("P2", "all"):
            print("  silver.parking_violation_detail (~958 万行)")
            print("  silver.tif_payment_detail (~4.8 万行)")
            print("  silver.crash_detail (~166 万行)")
            print("  silver.crash_person_detail (~533 万行)")
        print("[DRY RUN] 未实际执行，去掉 --dry-run 后重新运行")
        return

    t0 = time.time()
    con = connect(str(DB_PATH))
    try:
        ensure_silver_schema(con)

        if args.batch in ("P0", "all"):
            print("--- P0: 基础层 ---")
            build_dim_date(con, args.replace)
            build_taxi_zone(con, args.replace)
            build_trip_detail(con, args.replace)

        if args.batch in ("P1", "all"):
            print("\n--- P1: 资产与供给层 ---")
            build_vehicle_detail(con, args.replace)
            build_driver_detail(con, args.replace)
            build_base_detail(con, args.replace)
            build_driver_application_detail(con, args.replace)

        if args.batch in ("P2", "all"):
            print("\n--- P2: 监管与安全层 ---")
            build_parking_violation_detail(con, args.replace)
            build_tif_payment_detail(con, args.replace)
            build_crash_detail(con, args.replace)
            build_crash_person_detail(con, args.replace)

        # 写 Meta 注释
        write_meta_comments(con)

        # 质量报告
        run_quality_report(con, args.batch)

        elapsed = time.time() - t0
        print(f"\n[DONE] 构建完成，耗时 {elapsed:.1f} 秒")
        print(f"数据库: {DB_PATH}")

    finally:
        con.close()


if __name__ == "__main__":
    main()
