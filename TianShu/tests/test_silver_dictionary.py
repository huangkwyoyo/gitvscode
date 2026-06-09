"""
Silver 数据字典回归测试

每个测试对应一条经验复盘，确保同类错误不再出现。

用法：pytest tests/test_silver_dictionary.py -v
"""
import sys
from pathlib import Path

import pytest

# 添加 scripts/quality 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "quality"))

from check_silver_dictionary import (
    load_bronze_columns,
    load_silver_xlsx,
    check_source_fields,
    check_dangerous_patterns,
    FORBIDDEN_DIRECT_FIELDS,
)
from harness_config import load_harness_config

# 路径配置来自 Harness，避免测试和脚本各自硬编码
HARNESS_CONFIG = load_harness_config()
BRONZE_DB = str(HARNESS_CONFIG.duckdb_path)
SILVER_XLSX = str(HARNESS_CONFIG.silver_dictionary_xlsx)

TABLE_BRONZE_MAP = {
    "trip_detail": [
        "yellow_tripdata_2026q1",
        "green_tripdata_2026q1",
        "fhv_tripdata_2026q1",
        "fhvhv_tripdata_2026q1",
    ],
    "taxi_zone": "taxi_zone_lookup",
    "vehicle_detail": [
        "active_vehicles",
        "fhv_active_vehicles",
        "medallion_authorized_vehicles",
    ],
    "driver_detail": [
        "fhv_active_drivers",
        "shl_active_drivers",
    ],
    "base_detail": "fhv_base_aggregate_report",
    "driver_application_detail": "new_driver_applications",
    "parking_violation_detail": "parking_violations_all",
    "tif_payment_detail": "tif_medallion_payments",
    "crash_detail": "crash_merged",
    "crash_person_detail": "crash_person_all",
}


@pytest.fixture(scope="module")
def bronze_cols():
    """加载 Bronze 层字段"""
    return load_bronze_columns(BRONZE_DB)


@pytest.fixture(scope="module")
def silver_dict():
    """加载 Silver 数据字典"""
    if not Path(SILVER_XLSX).exists():
        pytest.skip(f"xlsx 文件不存在: {SILVER_XLSX}")
    return load_silver_xlsx(SILVER_XLSX)


# ============================================================
# 经验复盘 2026-06-07-1：停车罚单不得有虚构金额字段
# ============================================================
def test_parking_violation_no_fake_amount_fields(silver_dict):
    """
    经验复盘 2026-06-07：
    parking_violation_detail 不得包含 Bronze 中不存在的金额字段。
    如果此测试失败，说明有人新增了无来源的金额字段。
    """
    table = "parking_violation_detail"
    if table not in silver_dict:
        pytest.skip(f"{table} 不在 xlsx 中")
    fields = silver_dict[table]
    forbidden = FORBIDDEN_DIRECT_FIELDS.get(table, set())

    for f in fields:
        field_en = f.get("英文字段名", "")
        if field_en in forbidden:
            source_type = f.get("字段来源类型", f.get("source_type", ""))
            derivation = f.get("派生逻辑", "")
            assert source_type == "derived" and derivation, (
                f"[{table}] 字段 '{field_en}' 在 Bronze 中不存在。"
                f"如果确实需要，必须标注为 derived 且填写完整的派生逻辑和可信等级。"
            )


# ============================================================
# 经验复盘 2026-06-07-2：所有 Silver 字段必须有三类来源标注
# ============================================================
def test_all_fields_have_source_type(silver_dict):
    """
    经验复盘 2026-06-07：
    每个 Silver 字段必须标注来源类型（direct/standardized/derived）。
    xlsx 必须包含字段来源类型，避免 Silver 字段不可追溯。
    """
    valid_types = {"direct", "standardized", "derived"}
    violations: list[str] = []
    for table_name, fields in silver_dict.items():
        for f in fields:
            field_en = f.get("英文字段名", "")
            source_type = f.get("字段来源类型", "")
            if source_type not in valid_types:
                violations.append(
                    f"[{table_name}] {field_en}: 字段来源类型={source_type or '空'}"
                )
    if violations:
        pytest.fail(
            "以下字段缺少有效字段来源类型:\n" + "\n".join(violations[:30])
        )


# ============================================================
# 经验复盘 2026-06-07-3：字段数一致性
# ============================================================
def test_field_count_matches_plan(silver_dict):
    """
    经验复盘 2026-06-07：
    xlsx 字段数与 Markdown 规划文档声明的字段数必须一致。
    """
    plan_dir = Path(__file__).parent.parent / "scripts" / "silver"

    expected_counts = {
        "dim_date": 10,
        "taxi_zone": 5,
        "trip_detail": 39,
        "vehicle_detail": 25,
        "driver_detail": 11,
        "base_detail": 12,
        "driver_application_detail": 14,
        "parking_violation_detail": 33,
        "tif_payment_detail": 12,
        "crash_detail": 26,
        "crash_person_detail": 24,
    }

    for table_name, expected in expected_counts.items():
        if table_name not in silver_dict:
            continue
        actual = len(silver_dict[table_name])
        assert actual == expected, (
            f"[{table_name}] 字段数不一致: xlsx={actual}, 期望={expected}。"
            f"请检查 _gen_xlsx.py 是否与规划 MD 文档同步。"
        )


# ============================================================
# 经验复盘 2026-06-07-4：直接来源字段必须存在于 Bronze
# ============================================================
def test_direct_fields_exist_in_bronze(silver_dict, bronze_cols):
    """
    经验复盘 2026-06-07：
    标注为 direct/standardized 的字段，其来源字段必须存在于 Bronze DESCRIBE 结果。
    """
    violations = check_source_fields(silver_dict, bronze_cols, TABLE_BRONZE_MAP)
    if violations:
        pytest.fail(
            "以下字段的来源在 Bronze 中不存在:\n" + "\n".join(violations[:20])
        )


# ============================================================
# 经验复盘 2026-06-07-5：金额字段必须使用 DECIMAL
# ============================================================
def test_amount_fields_use_decimal(silver_dict):
    """
    金额字段必须使用 DECIMAL 类型，不得使用 DOUBLE 或 FLOAT。
    """
    amount_keywords = ["fare", "toll", "tip", "tax", "surcharge",
                       "fee", "payment", "fine", "penalty", "amount",
                       "driver_pay", "bcf"]
    exceptions = {
        "rate_code_id", "payment_type",   # 代码/ID，非金额
        "feet_from_curb",                  # 距离，非金额（curb 不含 fee）
        "payment_id",                      # 代理键，非金额
        "payment_date",                    # 日期，非金额
        "ehail_fee",                       # 已确认100%为空，保留但非活跃金额
        "airport_fee",                     # 机场费
    }
    violations: list[str] = []
    for table_name, fields in silver_dict.items():
        for f in fields:
            field_en = f.get("英文字段名", "")
            field_type = f.get("数据类型", "")
            if field_en in exceptions:
                continue
            is_amount = any(kw in field_en.lower() for kw in amount_keywords)
            if is_amount:
                if field_type not in ("DECIMAL", "DECIMAL(12,2)"):
                    violations.append(
                        f"[{table_name}] {field_en}: 类型={field_type}，"
                        f"金额字段应为 DECIMAL(12,2)"
                    )
    if violations:
        pytest.fail(
            "以下金额字段未使用 DECIMAL 类型:\n" + "\n".join(violations)
        )


# ============================================================
# 经验复盘 2026-06-07-6：危险模式不应出现在正式设计文档中
# ============================================================
def test_no_dangerous_patterns_in_silver_docs(silver_dict):
    """
    经验复盘 2026-06-07：
    Silver 字典中的字段不应匹配已知危险模式（如无来源的 amount 字段）。
    """
    violations = check_dangerous_patterns(silver_dict)
    if violations:
        pytest.fail(
            "Silver 字典中有未解决的危险模式:\n" + "\n".join(violations[:10])
        )
