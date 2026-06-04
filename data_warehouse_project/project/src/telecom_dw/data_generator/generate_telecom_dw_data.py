"""生成本地电信数仓模拟数据。"""

from __future__ import annotations

import csv
import json
import math
import os
import random
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path


MYSQL_EXE = r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = "123456"

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "data" / "generated" / "mysql_load"
LOG_PATH = ROOT / "data" / "logs" / "data_quality_report.md"
IDENTITY_CACHE_PATH = ROOT / "data" / "generated" / "user_identity_cache.json"

SEED = 20260531
BATCH_USER_COUNTS = [
    (date(2025, 5, 30), 16_000),
    (date(2025, 5, 31), 16_200),
    (date(2026, 4, 30), 19_000),
    (date(2026, 5, 30), 20_000),
    (date(2026, 5, 31), 20_300),
]
USER_COUNT = max(count for _, count in BATCH_USER_COUNTS)
ACCOUNT_COUNT = 100_000
TERMINAL_COUNT = 3_000
STAFF_COUNT = 1_200
ORG_COUNT = 300
CHANNEL_COUNT = 200
APPLICATION_COUNT = 300
ORDER_COUNT = 30_000
RECHARGE_COUNT = 120_000
USAGE_COUNT = 400_000
DPI_COUNT = 300_000
COMPLAINT_COUNT = 8_000
ODS_DEFAULT_ROWS = 10_000
ODS_TABLE_ROWS = {
    "ods_user_profile_daily": 90_000,
    "ods_user_profile_monthly": 90_000,
    "ods_account_income_monthly": 90_000,
    "ods_arrears_billing_monthly": 90_000,
    "ods_recharge_daily": 120_000,
    "ods_bestpay_transaction_monthly": 120_000,
    "ods_dpi_usage_daily": 300_000,
    "ods_digital_channel_order_daily": 30_000,
    "ods_digital_channel_order_monthly": 30_000,
    "ods_complaint_daily": 8_000,
    "ods_arrears_daily_part1": 60_000,
    "ods_arrears_daily_part2": 60_000,
    "ods_arrears_daily_part3": 60_000,
    "ods_combo_product_monthly_part1": 12_000,
    "ods_combo_product_monthly_part2": 12_000,
    "ods_combo_product_monthly_part3": 12_000,
    "ods_combo_product_monthly_part4": 12_000,
    "ods_combo_product_monthly_part5": 12_000,
}


random.seed(SEED)


PROVINCES = [
    ("北京", "北京", ["朝阳区", "海淀区", "西城区", "丰台区"], 1),
    ("上海", "上海", ["浦东新区", "徐汇区", "黄浦区", "闵行区"], 1),
    ("广东", "广州", ["天河区", "越秀区", "番禺区", "白云区"], 1),
    ("广东", "深圳", ["南山区", "福田区", "宝安区", "龙岗区"], 1),
    ("浙江", "杭州", ["西湖区", "滨江区", "余杭区", "萧山区"], 2),
    ("四川", "成都", ["武侯区", "锦江区", "高新区", "成华区"], 2),
    ("江苏", "南京", ["玄武区", "鼓楼区", "江宁区", "建邺区"], 2),
    ("湖北", "武汉", ["武昌区", "江汉区", "洪山区", "汉阳区"], 2),
    ("重庆", "重庆", ["渝中区", "江北区", "南岸区", "沙坪坝区"], 2),
    ("陕西", "西安", ["雁塔区", "碑林区", "莲湖区", "未央区"], 2),
    ("山东", "青岛", ["市南区", "市北区", "崂山区", "黄岛区"], 3),
    ("福建", "厦门", ["思明区", "湖里区", "集美区", "海沧区"], 3),
    ("河南", "郑州", ["金水区", "二七区", "中原区", "管城区"], 3),
    ("湖南", "长沙", ["岳麓区", "芙蓉区", "天心区", "开福区"], 3),
    ("安徽", "合肥", ["蜀山区", "包河区", "庐阳区", "瑶海区"], 3),
    ("河北", "石家庄", ["长安区", "桥西区", "新华区", "裕华区"], 4),
    ("广西", "南宁", ["青秀区", "兴宁区", "江南区", "良庆区"], 4),
    ("江西", "南昌", ["东湖区", "西湖区", "青山湖区", "红谷滩区"], 4),
    ("云南", "昆明", ["五华区", "盘龙区", "官渡区", "西山区"], 4),
    ("贵州", "贵阳", ["南明区", "云岩区", "观山湖区", "花溪区"], 4),
]

TOWN_SUFFIXES = ["人民路街道", "建设路街道", "新华街道", "东城街道", "西城街道", "高新街道", "中心镇", "新城镇"]
OUTLET_SUFFIXES = ["中心营业厅", "社区营业厅", "政企服务站", "旗舰厅", "客户服务网点", "综合网格站"]

SURNAMES = list("王李张刘陈杨赵黄周吴徐孙胡朱高林何郭马罗梁宋郑谢韩唐冯于董萧程曹袁邓许傅沈曾彭吕苏卢蒋蔡贾丁魏薛叶阎余潘杜戴夏钟汪田任姜范方石姚谭廖邹熊金陆郝孔白崔康毛邱秦江史顾侯邵孟龙万段雷钱汤尹黎易常武乔贺赖龚文")
GIVEN_CHARS = list("伟刚勇毅俊峰强军平保东文辉力明永健世广志义兴良海山仁波宁贵福生龙元全国胜学祥才发武新利清飞彬富顺信子杰涛昌成康星光天达安岩中茂进林有坚和彪博诚先敬震振壮会思群豪心邦承乐绍功松善厚庆磊民友裕河哲江超浩亮政谦亨奇固之轮翰朗伯宏言若鸣朋斌梁栋维启克伦翔旭鹏泽晨辰士以建家致树炎德行时泰盛雄琛钧冠策腾榕风航弘")
PHONE_PREFIXES = ["130", "131", "132", "155", "156", "166", "175", "176", "185", "186", "188", "189", "191", "193", "198", "199"]
ACTIVE_BATCH_DATE = BATCH_USER_COUNTS[-1][0]
ACTIVE_DATA_TIME = ACTIVE_BATCH_DATE
ACTIVE_BATCH_INDEX = len(BATCH_USER_COUNTS) - 1


def batch_months(batch_date: date) -> list[date]:
    """取批次日前十二个账期，支撑环比和同比分析。"""
    months = []
    year = batch_date.year
    month = batch_date.month
    for offset in range(11, -1, -1):
        m = month - offset
        y = year
        while m <= 0:
            m += 12
            y -= 1
        months.append(date(y, m, 1))
    return months


def batch_dates(batch_date: date) -> list[date]:
    """取批次日前一年业务日期，避免业务时间晚于批量日期。"""
    start = batch_date - timedelta(days=364)
    return [start + timedelta(days=i) for i in range(365)]


MONTHS = batch_months(ACTIVE_BATCH_DATE)
DATES = batch_dates(ACTIVE_BATCH_DATE)


def set_active_batch(batch_date: date) -> None:
    """切换当前批次，让生成器为每行写入一致的data_time。"""
    global ACTIVE_BATCH_DATE, ACTIVE_DATA_TIME, ACTIVE_BATCH_INDEX, MONTHS, DATES
    ACTIVE_BATCH_DATE = batch_date
    ACTIVE_DATA_TIME = batch_date
    ACTIVE_BATCH_INDEX = [d for d, _ in BATCH_USER_COUNTS].index(batch_date)
    MONTHS = batch_months(batch_date)
    DATES = batch_dates(batch_date)


def batch_user_count(batch_date: date) -> int:
    """返回批次全量用户规模，确保后一批总体大于前一批。"""
    return dict(BATCH_USER_COUNTS)[batch_date]


def scaled_count(base_count: int, user_count: int) -> int:
    """按批次用户规模等比例压缩明细数据量，控制个人电脑压力。"""
    return max(1, int(base_count * user_count / USER_COUNT))


def lifecycle_date(user: dict[str, object], candidate: date) -> date:
    """保证业务日期落在用户生命周期内。"""
    start = user["activation_date"]
    end = user["termination_date"] or ACTIVE_BATCH_DATE
    if candidate < start:
        return start
    if candidate > end:
        return end
    return candidate


def lifecycle_month(user: dict[str, object], candidate: date) -> date:
    """保证账期日期不早于入网且不晚于离网或批次日期。"""
    return lifecycle_date(user, candidate)


def lifecycle_datetime(user: dict[str, object], candidate: date) -> datetime:
    """生成落在用户生命周期内且精确到秒的业务时间。"""
    d = lifecycle_date(user, candidate)
    return datetime(d.year, d.month, d.day, random.randint(0, 23), random.randint(0, 59), random.randint(1, 59))


def business_date_value(col: str, user: dict[str, object]) -> date | None:
    """识别常见业务日期字段，并保证日期在用户生命周期内。"""
    if col == "data_time":
        return ACTIVE_BATCH_DATE
    if "activation" in col or "active" in col or "eff" in col or "start" in col or "create" in col:
        return user["activation_date"]
    if "termination" in col or "exp" in col or "end" in col:
        return user["termination_date"] or ACTIVE_BATCH_DATE
    if "billing" in col or "cycle" in col:
        return lifecycle_date(user, random.choice(MONTHS))
    if "month" in col:
        return lifecycle_month(user, random.choice(MONTHS))
    return lifecycle_date(user, random.choice(DATES))


def business_datetime_value(col: str, user: dict[str, object]) -> datetime:
    """识别常见业务时间字段，并保证时间在用户生命周期内。"""
    if col == "data_time":
        return ACTIVE_DATA_TIME
    if "activation" in col or "active" in col or "eff" in col or "start" in col or "create" in col:
        d = user["activation_date"]
        return datetime(d.year, d.month, d.day, random.randint(0, 23), random.randint(0, 59), random.randint(1, 59))
    if "termination" in col or "exp" in col or "end" in col:
        d = user["termination_date"] or ACTIVE_BATCH_DATE
        return datetime(d.year, d.month, d.day, random.randint(0, 23), random.randint(0, 59), random.randint(1, 59))
    return lifecycle_datetime(user, random.choice(DATES))


def payment_datetime(user: dict[str, object], created_time: datetime) -> datetime:
    """生成不早于创建时间且不晚于离网时间的支付时间。"""
    end_date = user["termination_date"] or ACTIVE_BATCH_DATE
    max_time = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)
    paid_time = created_time + timedelta(seconds=random.randint(1, 7200))
    if paid_time > max_time:
        paid_time = max_time
    if paid_time < created_time:
        paid_time = created_time + timedelta(seconds=1)
    return paid_time


def mysql_base_args(*extra: str) -> list[str]:
    return [
        MYSQL_EXE,
        "--default-character-set=utf8mb4",
        "--local-infile=1",
        "-h",
        MYSQL_HOST,
        "-u",
        MYSQL_USER,
        f"-p{MYSQL_PASSWORD}",
        *extra,
    ]


def run_sql(sql: str, *, batch: bool = False) -> str:
    args = mysql_base_args("-N", "-B") if batch else mysql_base_args()
    proc = subprocess.run(
        args,
        input=sql,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"MySQL执行失败：{proc.stderr.strip()}")
    return proc.stdout


def mysql_literal_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def get_columns() -> dict[tuple[str, str], list[tuple[str, str]]]:
    sql = """
    SELECT table_schema, table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema IN ('ods','dwd','dws','ads')
    ORDER BY table_schema, table_name, ordinal_position;
    """
    out = run_sql(sql, batch=True)
    result: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for line in out.splitlines():
        if not line.strip():
            continue
        schema, table, col, dtype = line.split("\t")
        result[(schema, table)].append((col, dtype))
    return dict(result)


def escape_field(value: object) -> str:
    if value is None:
        return r"\N"
    if isinstance(value, datetime):
        value = value.isoformat(sep=" ")
    elif isinstance(value, date):
        value = value.isoformat()
    text = str(value)
    return (
        text.replace("\\", "\\\\")
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def load_rows(schema: str, table: str, columns: list[str], rows, batch_size: int = 50_000) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    batch = []

    def flush(part: int, data: list[dict[str, object]]) -> None:
        if not data:
            return
        file_path = OUT_DIR / f"{schema}_{table}_{part}.tsv"
        with file_path.open("w", encoding="utf-8", newline="") as f:
            for row in data:
                f.write("\t".join(escape_field(row.get(c)) for c in columns) + "\n")
        col_sql = ", ".join(f"`{c}`" for c in columns)
        sql = f"""
        LOAD DATA LOCAL INFILE '{mysql_literal_path(file_path)}'
        INTO TABLE `{schema}`.`{table}`
        CHARACTER SET utf8mb4
        FIELDS TERMINATED BY '\\t' ESCAPED BY '\\\\'
        LINES TERMINATED BY '\\n'
        ({col_sql});
        """
        run_sql(sql)

    part = 1
    for row in rows:
        batch.append(row)
        total += 1
        if len(batch) >= batch_size:
            flush(part, batch)
            batch.clear()
            part += 1
    flush(part, batch)
    return total


def truncate_all(tables: dict[tuple[str, str], list[tuple[str, str]]]) -> None:
    lines = ["SET FOREIGN_KEY_CHECKS=0;"]
    for schema in ["ads", "dws", "dwd", "ods"]:
        for s, table in sorted(tables):
            if s == schema:
                lines.append(f"TRUNCATE TABLE `{s}`.`{table}`;")
    lines.append("SET FOREIGN_KEY_CHECKS=1;")
    run_sql("\n".join(lines))


def weighted_choice(items: list[tuple[object, float]]):
    total = sum(w for _, w in items)
    x = random.random() * total
    upto = 0.0
    for item, weight in items:
        upto += weight
        if upto >= x:
            return item
    return items[-1][0]


def chinese_name(gender: str) -> str:
    surname = random.choice(SURNAMES)
    length = 1 if random.random() < 0.35 else 2
    return surname + "".join(random.choice(GIVEN_CHARS) for _ in range(length))


def phone_number(i: int) -> str:
    return random.choice(PHONE_PREFIXES) + f"{random.randint(0, 99_999_999):08d}"


def numeric_id(prefix: int, i: int) -> str:
    """生成11位左右的业务ID，避免明显的人造前缀。"""
    return f"{prefix}{i:09d}"


def region_record(i: int | None = None) -> dict[str, object]:
    """生成省市区县镇网点一致的地域链路。"""
    province, city, districts, tier = PROVINCES[i % len(PROVINCES)] if i is not None else random.choice(PROVINCES)
    district = districts[(i // len(PROVINCES)) % len(districts)] if i is not None else random.choice(districts)
    town = f"{district}{random.choice(TOWN_SUFFIXES)}"
    outlet = f"{town}{random.choice(OUTLET_SUFFIXES)}"
    return {
        "province_name": province,
        "city_name": city,
        "district_name": district,
        "town_name": town,
        "outlet_name": outlet,
        "city_tier": tier,
    }


def make_products() -> list[dict[str, object]]:
    products = []
    specs = [
        ("basic_4g", "MOB4G", "移动4G套餐", "基础4G套餐", 39, 20, 100, 0.25),
        ("standard_5g", "MOB5G", "移动5G套餐", "标准5G套餐", 99, 80, 500, 0.40),
        ("premium_5g", "MOB5G", "移动5G套餐", "高价值5G套餐", 199, 180, 1200, 0.20),
        ("family_fusion", "FUSION", "融合套餐", "家庭融合套餐", 239, 220, 1000, 0.10),
        ("low_activity", "KEEP", "保号套餐", "低活跃保号套餐", 19, 5, 50, 0.05),
    ]
    idx = 1
    for typ, level2_id, level2_name, name, fee, gb, voice, weight in specs:
        for variant in range(1, 21):
            product_id = f"{level2_id}{variant:03d}"
            products.append(
                {
                    "product_id": product_id,
                    "product_code": f"{level2_id}-{variant:03d}",
                    "product_name": f"{name}{variant:02d}",
                    "product_type": typ,
                    "primary_product_id": product_id,
                    "primary_product_level1_id": "MOBILE" if level2_id in ("MOB4G", "MOB5G", "KEEP") else "FAMILY",
                    "primary_product_level2_id": level2_id,
                    "primary_product_level2_name": level2_name,
                    "price_plan_id": f"PLAN{idx:06d}",
                    "price_plan_name": f"{name}{variant:02d}",
                    "primary_price_plan_name": f"{name}{variant:02d}",
                    "monthly_fee": max(8, fee + random.choice([-20, -10, 0, 10, 20])),
                    "included_data_gb": max(1, gb + random.randint(-5, 20)),
                    "included_voice_min": max(20, voice + random.randint(-50, 200)),
                    "weight": weight,
                }
            )
            idx += 1
    return products


def load_identity_cache() -> dict[str, dict[str, object]]:
    """加载跨批次用户身份缓存，首次运行或缓存不存在时返回空字典。"""
    if IDENTITY_CACHE_PATH.exists():
        with IDENTITY_CACHE_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        # 将字符串日期恢复为date对象
        for uid, rec in raw.items():
            if rec.get("activation_date") and isinstance(rec["activation_date"], str):
                rec["activation_date"] = date.fromisoformat(rec["activation_date"])
            if rec.get("termination_date") and isinstance(rec["termination_date"], str):
                rec["termination_date"] = date.fromisoformat(rec["termination_date"])
        return raw
    return {}


def save_identity_cache(cache: dict[str, dict[str, object]]) -> None:
    """将跨批次用户身份缓存持久化到JSON文件。"""
    IDENTITY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    serializable: dict[str, dict[str, object]] = {}
    for uid, rec in cache.items():
        entry: dict[str, object] = {}
        for k, v in rec.items():
            if isinstance(v, (date, datetime)):
                entry[k] = v.isoformat()
            elif k == "product":
                continue  # product对象由每批次重新赋值，不持久化
            else:
                entry[k] = v
        serializable[uid] = entry
    with IDENTITY_CACHE_PATH.open("w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def apply_churn(cached_user: dict[str, object], batch_date: date, prev_batch_date: date) -> None:
    """跨批次离网逻辑：已离网用户保持状态，活跃用户按概率离网。"""
    if cached_user.get("is_active_subscriber") == 0:
        return  # 已离网，不可逆

    # 离网概率：基础2%，高风险+3%，低线城市+1%
    churn_prob = 0.02
    if cached_user.get("risk_score", 0.5) > 0.85:
        churn_prob += 0.03
    city_tier = cached_user.get("city_tier", 2)
    if isinstance(city_tier, int) and city_tier >= 3:
        churn_prob += 0.01

    if random.random() < churn_prob:
        days_between = max(1, (batch_date - prev_batch_date).days)
        offset = random.randint(30, max(31, days_between))
        termination = prev_batch_date + timedelta(days=offset)
        act_date = cached_user.get("activation_date", date(2020, 1, 1))
        if isinstance(act_date, str):
            act_date = date.fromisoformat(act_date)
        if termination < act_date + timedelta(days=90):
            termination = act_date + timedelta(days=90)
        if termination >= batch_date:
            termination = batch_date - timedelta(days=1)
        cached_user["termination_date"] = termination
        cached_user["is_active_subscriber"] = 0


def _pick_product_for_user(products: list[dict[str, object]], product_weights: list[tuple[dict[str, object], float]],
                            tier: int, age: int, existing_user: dict[str, object] | None = None) -> dict[str, object]:
    """为用户选择套餐，已有用户有30%概率更换套餐。"""
    product = weighted_choice(product_weights)
    # 高线城市倾向高端套餐
    if tier == 1 and random.random() < 0.25:
        product = random.choice([p for p in products if p["product_type"] in ("standard_5g", "premium_5g", "family_fusion")])
    # 年轻用户倾向5G
    if age <= 30 and random.random() < 0.20:
        product = random.choice([p for p in products if "5g" in p["product_type"]])
    # 已有用户：大概率保留原套餐或同级套餐
    if existing_user and random.random() < 0.70:
        old_type = existing_user.get("product_type", "")
        same_type = [p for p in products if p["product_type"] == old_type]
        if same_type:
            product = random.choice(same_type)
    return product


def build_master_data(products: list[dict[str, object]], user_count: int = USER_COUNT, batch_date: date | None = None):
    """按批次生成全量用户主数据。

    利用跨批次身份缓存保证同一用户的关键身份字段（姓名、手机号、入网日期等）
    在批次间保持稳定，并应用渐进式离网逻辑。
    """
    batch_date = batch_date or ACTIVE_BATCH_DATE
    cache = load_identity_cache()
    # 确定上一批次日期（用于计算离网窗口）
    prev_batches = [(d, c) for d, c in BATCH_USER_COUNTS if d < batch_date]
    prev_batch_date = prev_batches[-1][0] if prev_batches else batch_date - timedelta(days=365)

    product_weights = [(p, p["weight"]) for p in products]
    users = []
    used_phone: set[str] = set()
    # 从缓存恢复已存在的手机号（防止新用户重复）
    for rec in cache.values():
        phone = rec.get("service_number_id")
        if isinstance(phone, str):
            used_phone.add(phone)

    for i in range(1, user_count + 1):
        user_id = numeric_id(89, i)
        cached = cache.get(user_id)

        if cached is not None:
            # --- 已有用户：复用稳定身份，更新动态字段 ---
            gender = str(cached["gender_type"])
            age = int(cached["age_count"])
            region_data = {
                "province_name": str(cached["province_name"]),
                "city_name": str(cached["city_name"]),
                "district_name": str(cached["district_name"]),
                "town_name": str(cached["town_name"]),
                "outlet_name": str(cached["outlet_name"]),
                "city_tier": int(cached["city_tier"]),
            }
            tier = region_data["city_tier"]
            # 跨批次离网
            apply_churn(cached, batch_date, prev_batch_date)
            # 动态字段：套餐可能变更
            existing_product_info = {
                "product_type": str(cached.get("product_type", "")),
            }
            product = _pick_product_for_user(products, product_weights, tier, age, existing_product_info)
            active = bool(cached.get("is_active_subscriber", 1))
            termination = cached.get("termination_date")
            activation = cached.get("activation_date", date(2020, 1, 1))
            if isinstance(activation, str):
                activation = date.fromisoformat(activation)
            if isinstance(termination, str):
                termination = date.fromisoformat(termination)
            phone = str(cached["service_number_id"])

            user = {
                "user_id": user_id,
                "customer_id": str(cached["customer_id"]),
                "account_id": str(cached["account_id"]),
                "account_code": str(cached["account_code"]),
                "product_id": product["product_id"],
                "primary_product_id": product["primary_product_id"],
                "primary_product_level1_id": product["primary_product_level1_id"],
                "primary_product_level2_id": product["primary_product_level2_id"],
                "primary_price_plan_name": product["primary_price_plan_name"],
                "service_number_id": phone,
                "customer_name": str(cached["customer_name"]),
                "gender_type": gender,
                "age_count": age,
                "province_name": region_data["province_name"],
                "city_name": region_data["city_name"],
                "district_name": region_data["district_name"],
                "town_name": region_data["town_name"],
                "outlet_name": region_data["outlet_name"],
                "city_tier": tier,
                "activation_date": activation,
                "termination_date": termination,
                "is_active_subscriber": 1 if active else 0,
                "payment_timing_type": str(cached["payment_timing_type"]),
                "service_network_type": str(cached["service_network_type"]),
                "product": product,
                "risk_score": random.random(),
            }
            # 更新缓存中的动态字段
            cached["product_id"] = product["product_id"]
            cached["primary_product_id"] = product["primary_product_id"]
            cached["primary_product_level2_id"] = product["primary_product_level2_id"]
            cached["product_type"] = product["product_type"]
            cached["risk_score"] = user["risk_score"]
        else:
            # --- 新用户：全新生成身份并写入缓存 ---
            gender = "男" if random.random() < 0.51 else "女"
            age_band = weighted_choice(
                [((18, 25), 0.18), ((26, 35), 0.32), ((36, 45), 0.25), ((46, 60), 0.20), ((61, 78), 0.05)]
            )
            age = random.randint(*age_band)
            region = region_record()
            province = region["province_name"]
            city = region["city_name"]
            district = region["district_name"]
            tier = region["city_tier"]
            product = _pick_product_for_user(products, product_weights, tier, age)
            phone = phone_number(i)
            while phone in used_phone:
                phone = phone_number(i)
            used_phone.add(phone)
            activation_end = batch_date - timedelta(days=random.randint(1, 30))
            activation = date(2020, 1, 1) + timedelta(days=random.randint(0, max(1, (activation_end - date(2020, 1, 1)).days)))
            # 首批用户初始离网率约3-6%
            active = random.random() < (0.97 if tier <= 2 else 0.94)
            termination = None
            if not active:
                termination_start = max(activation + timedelta(days=30), batch_date - timedelta(days=180))
                if termination_start < batch_date:
                    termination = termination_start + timedelta(days=random.randint(0, (batch_date - termination_start).days))
            payment_type = "postpaid" if random.random() < 0.72 else "prepaid"
            user_name = chinese_name(gender)

            user = {
                "user_id": user_id,
                "customer_id": numeric_id(66, i),
                "account_id": numeric_id(76, i),
                "account_code": f"ACCT{activation:%Y%m}{i:08d}",
                "product_id": product["product_id"],
                "primary_product_id": product["primary_product_id"],
                "primary_product_level1_id": product["primary_product_level1_id"],
                "primary_product_level2_id": product["primary_product_level2_id"],
                "primary_price_plan_name": product["primary_price_plan_name"],
                "service_number_id": phone,
                "customer_name": user_name,
                "gender_type": gender,
                "age_count": age,
                "province_name": province,
                "city_name": city,
                "district_name": district,
                "town_name": region["town_name"],
                "outlet_name": region["outlet_name"],
                "city_tier": tier,
                "activation_date": activation,
                "termination_date": termination,
                "is_active_subscriber": 1 if active else 0,
                "payment_timing_type": payment_type,
                "service_network_type": "mobile",
                "product": product,
                "risk_score": random.random(),
            }
            # 写入缓存
            cache[user_id] = {
                "user_id": user_id,
                "customer_id": user["customer_id"],
                "account_id": user["account_id"],
                "account_code": user["account_code"],
                "service_number_id": phone,
                "customer_name": user_name,
                "gender_type": gender,
                "age_count": age,
                "province_name": province,
                "city_name": city,
                "district_name": district,
                "town_name": region["town_name"],
                "outlet_name": region["outlet_name"],
                "city_tier": tier,
                "activation_date": activation,
                "termination_date": termination,
                "is_active_subscriber": 1 if active else 0,
                "payment_timing_type": payment_type,
                "service_network_type": "mobile",
                "product_id": product["product_id"],
                "primary_product_id": product["primary_product_id"],
                "primary_product_level2_id": product["primary_product_level2_id"],
                "product_type": product["product_type"],
                "risk_score": user["risk_score"],
            }

        users.append(user)

    save_identity_cache(cache)
    return users


def row_for_columns(columns: list[str], values: dict[str, object]) -> dict[str, object]:
    return {c: (ACTIVE_DATA_TIME if c == "data_time" and c not in values else values.get(c)) for c in columns}


def account_item_id(user: dict[str, object], i: int) -> str:
    """账目编码必须区别于账户编码，便于模拟账务明细归集。"""
    return f"AI{user['activation_date']:%Y%m}{i + 1:010d}"


def contract_code(user: dict[str, object], i: int) -> str | None:
    """只有部分政企和融合用户有合同编码，避免人人都有合同。"""
    if user["product"]["product_type"] not in ("family_fusion", "premium_5g") and random.random() > 0.08:
        return None
    prefix = "ZQHT" if user["product"]["product_type"] == "family_fusion" else "HT"
    return f"{prefix}{user['activation_date']:%Y%m%d}{i + 1:08d}"


def project_code(user: dict[str, object], i: int) -> str | None:
    """项目编码主要用于政企、ICT和融合业务，不做通用CODE占位。"""
    if user["product"]["product_type"] != "family_fusion" and random.random() > 0.05:
        return None
    prefix = "ICTXM" if user["product"]["product_type"] == "family_fusion" else "XM"
    return f"{prefix}{user['activation_date']:%Y%m%d}{i + 1:08d}"


def org_value(col: str, i: int, orgs: list[dict[str, object]]) -> object:
    """按组织层级返回不同编码，避免多级部门字段全部相同。"""
    org = orgs[i % len(orgs)]
    if "level1" in col:
        return org["department_level1_id"]
    if "level2" in col:
        return org["department_level2_id"]
    if "level3" in col:
        return org["department_level3_id"]
    if "level4" in col:
        return org["department_level4_id"]
    if "level5" in col:
        return org["department_level5_id"]
    if "level6" in col:
        return org["department_level6_id"]
    return org["department_id"]


def region_value(col: str, user: dict[str, object]) -> object | None:
    """地域字段必须来自同一条省市区县镇网点链路。"""
    if "province" in col or "provice" in col:
        return user["province_name"]
    if "city" in col:
        return user["city_name"]
    if "district" in col or "county" in col:
        return user["district_name"]
    if "town" in col or "street" in col:
        return user["town_name"]
    if "outlet" in col or "point" in col or "store" in col:
        return user["outlet_name"]
    if "bureau" in col and col.endswith("_name"):
        return f"{user['city_name']}{user['district_name']}分局"
    if "area" in col and col.endswith("_name"):
        return f"{user['city_name']}{user['district_name']}片区"
    if "address" in col and col.endswith("_name"):
        return f"{user['city_name']}{user['town_name']}通信路{random.randint(1, 299)}号"
    if "building" in col and col.endswith("_name"):
        return f"{user['city_name']}{user['district_name']}通信楼宇{random.randint(1, 999):03d}"
    return None


def region_code_value(col: str, i: int, user: dict[str, object]) -> object | None:
    """地址类编码也必须绑定用户地域链路。"""
    city_seed = abs(hash((user["province_name"], user["city_name"]))) % 9000 + 1000
    district_seed = abs(hash((user["city_name"], user["district_name"]))) % 9000 + 1000
    if "bureau" in col:
        return f"BR{city_seed}{district_seed}"
    if "area" in col:
        return f"AR{city_seed}{district_seed}"
    if "address" in col:
        return f"ADDR{city_seed}{district_seed}{(i % 9999) + 1:04d}"
    if "building" in col:
        return f"BLD{city_seed}{district_seed}{(i % 9999) + 1:04d}"
    if "point" in col or "store" in col:
        return f"OUT{city_seed}{district_seed}{(i % 9999) + 1:04d}"
    return None


def code_value(col: str, i: int, user: dict[str, object], channels, orgs, staff) -> object:
    """按业务语义生成编码，避免无意义CODE前缀。"""
    region_code = region_code_value(col, i, user)
    if region_code is not None:
        return region_code
    if col == "account_code":
        return user["account_code"]
    if col in ("zhetno_code",):
        return contract_code(user, i)
    if col in ("zictno_code",):
        return project_code(user, i)
    if "channel" in col:
        return channels[i % len(channels)]["channel_code"]
    if "department" in col or "org" in col:
        return orgs[i % len(orgs)]["department_code"]
    if "staff" in col or "agent" in col:
        return staff[i % len(staff)]["staff_code"]
    if "order" in col:
        return f"ORD{date.today():%Y%m}{i + 1:010d}"
    if "building" in col:
        return f"BLD{(i % 999999) + 1:06d}"
    if "product" in col:
        return user["product"]["product_code"]
    if "user" in col:
        return user["user_id"]
    return f"BUS{(i % 99999999) + 1:08d}"


def rate_value(col: str) -> float:
    """按字段语义生成合理税率、利率、折扣率，避免大量0.000000。"""
    if "tax" in col:
        return random.choice([0.06, 0.09, 0.13])
    if "discount" in col:
        return round(random.uniform(0.70, 0.98), 6)
    if "arrears" in col or "outstanding" in col:
        return round(random.uniform(0.01, 0.12), 6)
    if "conversion" in col or "success" in col or "pass" in col:
        return round(random.uniform(0.35, 0.95), 6)
    if "churn" in col:
        return round(random.uniform(0.002, 0.035), 6)
    return round(random.uniform(0.01, 0.99), 6)


def name_value(col: str, i: int, user: dict[str, object], product: dict[str, object], channels, orgs, staff) -> object:
    """按字段语义生成中文名称，避免模拟占位文本。"""
    region = region_value(col, user)
    if region is not None:
        return region
    if "account" in col or "customer" in col:
        return user["customer_name"]
    if "price_plan" in col or "product" in col or "offer" in col:
        return product["price_plan_name"]
    if "channel" in col:
        return channels[i % len(channels)]["channel_name"]
    if "department" in col or "org" in col:
        return orgs[i % len(orgs)]["department_name"]
    if "staff" in col or "agent" in col or "manager" in col:
        return staff[i % len(staff)]["staff_name"]
    if "building" in col:
        return f"{user['city_name']}{user['district_name']}营业楼宇{(i % 5000) + 1:04d}"
    return random.choice(["标准", "普通", "高价值", "线上", "线下"])


def generic_value(col: str, i: int, users, products, channels, orgs, staff, apps) -> object:
    user = users[i % len(users)]
    product = user["product"]
    if col == "synthetic_row_id":
        return ACTIVE_BATCH_INDEX * 1_000_000_000 + i + 1
    if col == "data_time":
        return ACTIVE_DATA_TIME
    region = region_value(col, user)
    if region is not None:
        return region
    if col in user:
        return user[col]
    if col in product:
        return product[col]
    if col.endswith("_id"):
        if col == "account_item_id" or col.startswith("account_item_"):
            return account_item_id(user, i)
        if col in ("zhetno_code", "zictno_code"):
            return code_value(col, i, user, channels, orgs, staff)
        region_code = region_code_value(col, i, user)
        if region_code is not None:
            return region_code
        if "customer" in col:
            return user["customer_id"]
        if "account" in col:
            return user["account_id"]
        if "primary_product_level2" in col:
            return product["primary_product_level2_id"]
        if "primary_product_level1" in col:
            return product["primary_product_level1_id"]
        if "product" in col or "price_plan" in col or "offer" in col:
            return product["product_id"]
        if "channel" in col:
            return channels[i % len(channels)]["channel_id"]
        if "department" in col:
            return org_value(col, i, orgs)
        if "staff" in col:
            return staff[i % len(staff)]["staff_id"]
        if "application" in col:
            return apps[i % len(apps)]["application_id"]
        if "terminal" in col:
            return f"T{i % TERMINAL_COUNT + 1:012d}"
        return f"REF2025{i + 1:08d}"
    if col.startswith("is_"):
        return 1 if random.random() < 0.8 else 0
    if col.endswith("_date"):
        return business_date_value(col, user)
    if col.endswith("_time"):
        return business_datetime_value(col, user)
    if col.endswith("_amount") or col.endswith("_fee"):
        return round(max(0, random.gauss(product["monthly_fee"], product["monthly_fee"] * 0.35)), 2)
    if col.endswith("_rate") or col.endswith("_ratio"):
        return rate_value(col)
    if col.endswith("_count"):
        return max(0, int(random.expovariate(1 / 8)))
    if col.endswith("_usage_mb"):
        return round(max(0, random.gauss(product["included_data_gb"] * 1024 / 20, 500)), 3)
    if col.endswith("_usage_min"):
        return round(max(0, random.gauss(product["included_voice_min"] / 20, 20)), 3)
    if col.endswith("_status"):
        return random.choice(["正常", "已完成", "处理中", "已关闭"])
    if col.endswith("_type"):
        if "account_item" in col:
            return random.choice(["套餐月租", "国内语音", "国内流量", "短信彩信", "增值业务", "终端合约"])
        if "certificate" in col or "card" in col or "ident" in col:
            return random.choice(["居民身份证", "统一社会信用代码", "护照", "港澳台通行证"])
        if "channel" in col:
            return random.choice(["自有营业厅", "社会代理", "线上APP", "客服热线", "电商平台"])
        return random.choice(["移动业务", "5G套餐", "4G套餐", "线上渠道", "线下渠道"])
    if col.endswith("_code"):
        return code_value(col, i, user, channels, orgs, staff)
    if col.endswith("_name"):
        return name_value(col, i, user, product, channels, orgs, staff)
    return f"业务值{(i % 1000) + 1:04d}"


def _process_single_batch(batch_date: date, products: list[dict[str, object]], truncate: bool) -> tuple[int, dict[str, int]]:
    """处理单个批次的数据生成与入库，返回(用户数, 加载行数统计)。"""
    set_active_batch(batch_date)
    tables = get_columns()
    if truncate:
        truncate_all(tables)

    users = build_master_data(products, batch_user_count(batch_date), batch_date)
    batch_scale_count = len(users)
    channels = [
        {
            "channel_id": f"CHNL{i:06d}",
            "channel_code": f"QD{i:06d}",
            "channel_name": f"{random.choice(['线上APP', '旗舰厅', '社区营业厅', '代理网点', '客服热线'])}{i:04d}",
            "channel_type": random.choice(["APP", "营业厅", "代理商", "电商", "客服"]),
            "parent_channel_id": None if i <= 20 else f"CHNL{random.randint(1, 20):06d}",
        }
        for i in range(1, CHANNEL_COUNT + 1)
    ]
    orgs = [
        (
            lambda region: {
                "department_id": f"ORG{310000 + i:06d}",
                "department_code": f"ORGCODE{310000 + i:06d}",
                "department_level1_id": f"ORG{300000 + (i % 30) + 1:06d}",
                "department_level2_id": f"ORG{310000 + (i % 80) + 1:06d}",
                "department_level3_id": f"ORG{310100 + (i % 160) + 1:06d}",
                "department_level4_id": f"ORG{31010000 + (i % 800) + 1:08d}",
                "department_level5_id": f"GRID{(i % 3000) + 1:05d}",
                "department_level6_id": f"CELL{(i % 12000) + 1:06d}",
                "province_name": region["province_name"],
                "city_name": region["city_name"],
                "district_name": region["district_name"],
                "town_name": region["town_name"],
                "outlet_name": region["outlet_name"],
                "department_name": f"{region['city_name']}{region['district_name']}{random.choice(['中心营业厅', '客户服务部', '综合网格', '政企客户部', '渠道运营部'])}",
                "department_type": random.choice(["省公司", "市公司", "区县分公司", "网格"]),
                "parent_department_id": None if i <= 20 else f"ORG{310000 + random.randint(1, 20):06d}",
            }
        )(region_record(i))
        for i in range(1, ORG_COUNT + 1)
    ]
    staff = [
        {
            "staff_id": f"EMP{3100000000 + i:010d}",
            "staff_code": f"YG{3100000000 + i:010d}",
            "staff_name": chinese_name("男"),
            "department_id": orgs[i % ORG_COUNT]["department_id"],
            "staff_status": "active",
        }
        for i in range(1, STAFF_COUNT + 1)
    ]
    apps = [
        {
            "application_id": f"APP{i:05d}",
            "application_level1_name": random.choice(["短视频", "社交", "视频", "游戏", "音乐", "办公教育", "其他"]),
            "application_level2_name": f"应用二级{i % 50:02d}",
            "application_level3_name": f"应用三级{i % 200:03d}",
            "application_visit_type": random.choice(["内容访问", "消息通信", "文件下载", "直播"]),
        }
        for i in range(1, APPLICATION_COUNT + 1)
    ]

    loaded: dict[str, int] = {}

    def cols(schema: str, table: str) -> list[str]:
        return [c for c, _ in tables[(schema, table)]]

    # 维表
    loaded["dwd.dim_customer"] = load_rows(
        "dwd",
        "dim_customer",
        cols("dwd", "dim_customer"),
        (row_for_columns(cols("dwd", "dim_customer"), {
            "customer_id": u["customer_id"], "customer_name": u["customer_name"],
            "certificate_type": "居民身份证", "customer_level_type": "高价值" if u["product"]["monthly_fee"] >= 159 else "普通",
            "is_enterprise_customer": 1 if random.random() < 0.08 else 0,
        }) for u in users),
    )
    loaded["dwd.dim_account"] = load_rows(
        "dwd",
        "dim_account",
        cols("dwd", "dim_account"),
        (row_for_columns(cols("dwd", "dim_account"), {
            "account_id": u["account_id"], "customer_id": u["customer_id"], "account_code": u["account_code"],
            "account_name": u["customer_name"], "account_status": "active" if u["is_active_subscriber"] else "closed",
        }) for u in users),
    )
    loaded["dwd.dim_user"] = load_rows("dwd", "dim_user", cols("dwd", "dim_user"), (row_for_columns(cols("dwd", "dim_user"), u) for u in users))
    loaded["dwd.dim_product"] = load_rows("dwd", "dim_product", cols("dwd", "dim_product"), (row_for_columns(cols("dwd", "dim_product"), p) for p in products))
    loaded["dwd.dim_channel"] = load_rows("dwd", "dim_channel", cols("dwd", "dim_channel"), (row_for_columns(cols("dwd", "dim_channel"), c) for c in channels))
    loaded["dwd.dim_org"] = load_rows("dwd", "dim_org", cols("dwd", "dim_org"), (row_for_columns(cols("dwd", "dim_org"), o) for o in orgs))
    loaded["dwd.dim_staff"] = load_rows("dwd", "dim_staff", cols("dwd", "dim_staff"), (row_for_columns(cols("dwd", "dim_staff"), s) for s in staff))
    loaded["dwd.dim_terminal"] = load_rows(
        "dwd",
        "dim_terminal",
        cols("dwd", "dim_terminal"),
        (row_for_columns(cols("dwd", "dim_terminal"), {
            "terminal_id": f"T{i:012d}", "terminal_serial_id": f"SN{i:014d}", "terminal_imei_id": f"86{i:013d}",
            "terminal_model_id": f"MODEL{i % 120:03d}", "terminal_model_name": random.choice(["华为", "小米", "荣耀", "OPPO", "vivo", "苹果"]) + f"机型{i%120:03d}",
            "is_super_sim_supported": 1 if random.random() < 0.45 else 0,
        }) for i in range(1, TERMINAL_COUNT + 1)),
    )
    loaded["dwd.dim_date"] = load_rows(
        "dwd",
        "dim_date",
        cols("dwd", "dim_date"),
        (row_for_columns(cols("dwd", "dim_date"), {
            "date_id": d.strftime("%Y%m%d"), "calendar_date": d, "calendar_month_date": date(d.year, d.month, 1),
            "weekday_name": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][d.weekday()],
            "is_month_end": 1 if (d + timedelta(days=1)).month != d.month else 0,
        }) for d in DATES),
    )
    loaded["dwd.dim_application"] = load_rows("dwd", "dim_application", cols("dwd", "dim_application"), (row_for_columns(cols("dwd", "dim_application"), a) for a in apps))

    # 事实表
    def monthly_bill_rows():
        for u in users:
            fee_base = u["product"]["monthly_fee"]
            tier_factor = {1: 1.22, 2: 1.10, 3: 0.95, 4: 0.82}[u["city_tier"]]
            for m in MONTHS:
                bill_month = lifecycle_month(u, m)
                amount = max(0, random.gauss(fee_base * tier_factor, fee_base * 0.18))
                owe_prob = 0.04 + (0.06 if u["risk_score"] > 0.88 else 0) + (0.03 if u["city_tier"] == 4 else 0)
                outstanding = round(amount * random.uniform(0.2, 1.0), 2) if random.random() < owe_prob else 0
                yield row_for_columns(cols("dwd", "fact_billing_monthly"), {
                    "account_id": u["account_id"], "user_id": u["user_id"], "billing_month_date": bill_month,
                    "billed_revenue_fee": round(amount, 2), "outstanding_amount": outstanding, "valid_outstanding_amount": outstanding,
                })

    loaded["dwd.fact_billing_monthly"] = load_rows("dwd", "fact_billing_monthly", cols("dwd", "fact_billing_monthly"), monthly_bill_rows())

    def snapshot_rows():
        for u in users:
            for m in MONTHS:
                snapshot_date = lifecycle_date(u, date(m.year, m.month, 28))
                yield row_for_columns(cols("dwd", "fact_user_snapshot_daily"), {
                    "user_id": u["user_id"], "data_date": snapshot_date, "customer_id": u["customer_id"], "account_id": u["account_id"],
                    "is_active_subscriber": u["is_active_subscriber"], "daily_revenue_fee": round(u["product"]["monthly_fee"] / 30, 2),
                    "daily_sms_count": random.randint(0, 5), "daily_voice_call_count": random.randint(0, 12),
                    "daily_mobile_data_usage_mb": round(max(0, random.gauss(u["product"]["included_data_gb"] * 1024 / 30, 300)), 3),
                })

    loaded["dwd.fact_user_snapshot_daily"] = load_rows("dwd", "fact_user_snapshot_daily", cols("dwd", "fact_user_snapshot_daily"), snapshot_rows())

    def usage_rows():
        for i in range(scaled_count(USAGE_COUNT, batch_scale_count)):
            u = users[random.randrange(len(users))]
            p = u["product"]
            yield row_for_columns(cols("dwd", "fact_usage_daily"), {
                "user_id": u["user_id"], "data_date": lifecycle_date(u, random.choice(DATES)),
                "mobile_data_usage_mb": round(max(0, random.gauss(p["included_data_gb"] * 1024 / 28, p["included_data_gb"] * 35)), 3),
                "uplink_data_usage_mb": round(max(0, random.gauss(p["included_data_gb"] * 1024 / 90, 100)), 3),
                "downlink_data_usage_mb": round(max(0, random.gauss(p["included_data_gb"] * 1024 / 35, 300)), 3),
                "voice_usage_min": round(max(0, random.gauss(p["included_voice_min"] / 25, 12)), 3),
                "sms_count": random.randint(0, 4),
            })

    loaded["dwd.fact_usage_daily"] = load_rows("dwd", "fact_usage_daily", cols("dwd", "fact_usage_daily"), usage_rows())

    def recharge_rows():
        methods = ["APP", "微信", "支付宝", "银行", "营业厅"]
        for i in range(1, scaled_count(RECHARGE_COUNT, batch_scale_count) + 1):
            u = users[random.randrange(len(users))]
            amount = max(10, random.gauss(u["product"]["monthly_fee"], u["product"]["monthly_fee"] * 0.35))
            yield row_for_columns(cols("dwd", "fact_recharge_daily"), {
                "recharge_event_id": f"R{i:012d}", "user_id": u["user_id"], "recharge_date": lifecycle_date(u, random.choice(DATES)),
                "recharge_method_type": weighted_choice([(methods[0], 0.40), (methods[1], 0.30), (methods[2], 0.20), (methods[3], 0.06), (methods[4], 0.04)]),
                "recharge_amount": round(amount, 2),
            })

    loaded["dwd.fact_recharge_daily"] = load_rows("dwd", "fact_recharge_daily", cols("dwd", "fact_recharge_daily"), recharge_rows())

    def order_rows():
        for i in range(1, scaled_count(ORDER_COUNT, batch_scale_count) + 1):
            u = users[random.randrange(len(users))]
            ch = channels[random.randrange(CHANNEL_COUNT)]
            prod = random.choice(products)
            created_time = lifecycle_datetime(u, random.choice(DATES))
            paid = random.random() < (0.82 if u["risk_score"] < 0.9 else 0.65)
            pay_time = payment_datetime(u, created_time) if paid else None
            yield row_for_columns(cols("dwd", "fact_order_daily"), {
                "order_id": f"O{i:012d}", "user_id": u["user_id"], "channel_id": ch["channel_id"], "product_id": prod["product_id"],
                "order_created_time": created_time,
                "payment_time": pay_time,
                "business_time": created_time,
                "order_status": "paid" if paid else random.choice(["created", "cancelled"]),
                "order_amount": round(prod["monthly_fee"] * random.uniform(0.8, 1.2), 2),
            })

    loaded["dwd.fact_order_daily"] = load_rows("dwd", "fact_order_daily", cols("dwd", "fact_order_daily"), order_rows())

    def complaint_rows():
        for i in range(1, scaled_count(COMPLAINT_COUNT, batch_scale_count) + 1):
            u = users[random.randrange(len(users))]
            dep = orgs[random.randrange(ORG_COUNT)]
            d = lifecycle_date(u, random.choice(DATES))
            yield row_for_columns(cols("dwd", "fact_complaint_daily"), {
                "complaint_event_id": f"CP{i:012d}", "user_id": u["user_id"], "complaint_date": d,
                "responsible_department_id": dep["department_id"], "complaint_type": weighted_choice([("网络质量", .35), ("费用争议", .25), ("服务态度", .15), ("套餐规则", .15), ("终端合约", .10)]),
                "complaint_status": random.choice(["closed", "processing", "accepted"]),
                "is_first_dispatch_success": 1 if random.random() < .78 else 0,
                "complaint_handle_duration": random.randint(2, 96),
            })

    loaded["dwd.fact_complaint_daily"] = load_rows("dwd", "fact_complaint_daily", cols("dwd", "fact_complaint_daily"), complaint_rows())

    def dpi_rows():
        for _ in range(scaled_count(DPI_COUNT, batch_scale_count)):
            u = users[random.randrange(len(users))]
            app = apps[random.randrange(APPLICATION_COUNT)]
            weight = {"短视频": 1.8, "视频": 1.5, "游戏": 1.1, "社交": .8}.get(app["application_level1_name"], .5)
            yield row_for_columns(cols("dwd", "fact_dpi_usage_daily"), {
                "user_id": u["user_id"], "application_id": app["application_id"], "data_date": lifecycle_date(u, random.choice(DATES)),
                "page_view_count": max(1, int(random.expovariate(1 / 12))),
                "application_traffic_usage_mb": round(max(0, random.gauss(u["product"]["included_data_gb"] * weight * 6, 150)), 3),
            })

    loaded["dwd.fact_dpi_usage_daily"] = load_rows("dwd", "fact_dpi_usage_daily", cols("dwd", "fact_dpi_usage_daily"), dpi_rows())

    # ODS按源层规模写入，保证原始接入层数据量不小于DWD。
    for (schema, table), table_cols in tables.items():
        if schema != "ods":
            continue
        col_names = [c for c, _ in table_cols]
        row_count = scaled_count(ODS_TABLE_ROWS.get(table, ODS_DEFAULT_ROWS), batch_scale_count)
        loaded[f"{schema}.{table}"] = load_rows(
            schema,
            table,
            col_names,
            (row_for_columns(col_names, {c: generic_value(c, i, users, products, channels, orgs, staff, apps) for c in col_names}) for i in range(row_count)),
            batch_size=10_000,
        )

    # DWS/ADS从已生成主数据生成可用汇总样例。
    def user_month_summary_rows():
        for u in users:
            for m in MONTHS:
                data_month = lifecycle_month(u, m)
                yield row_for_columns(cols("dws", "dws_user_month_summary"), {
                    "user_id": u["user_id"], "data_month_date": data_month,
                    "monthly_revenue_fee": round(u["product"]["monthly_fee"] * random.uniform(.85, 1.25), 2),
                    "mobile_data_usage_mb": round(u["product"]["included_data_gb"] * 1024 * random.uniform(.45, 1.4), 3),
                    "voice_usage_min": round(u["product"]["included_voice_min"] * random.uniform(.3, 1.2), 3),
                    "recharge_amount": round(u["product"]["monthly_fee"] * random.uniform(.7, 1.2), 2),
                    "outstanding_amount": round(u["product"]["monthly_fee"] * random.random(), 2) if u["risk_score"] > .92 else 0,
                })

    loaded["dws.dws_user_month_summary"] = load_rows("dws", "dws_user_month_summary", cols("dws", "dws_user_month_summary"), user_month_summary_rows())

    # 其余DWS/ADS表写入足量汇总样例。
    for (schema, table), table_cols in tables.items():
        if schema not in ("dws", "ads") or f"{schema}.{table}" in loaded:
            continue
        col_names = [c for c, _ in table_cols]
        n = 12 if schema == "ads" else 365
        loaded[f"{schema}.{table}"] = load_rows(
            schema,
            table,
            col_names,
            (row_for_columns(col_names, {c: generic_value(c, i, users, products, channels, orgs, staff, apps) for c in col_names}) for i in range(n)),
            batch_size=10_000,
        )

    # 质量报告
    report = [
        "# 数据质量校验报告",
        "",
        f"- 随机种子：{SEED}",
        f"- 批次日期：{ACTIVE_DATA_TIME:%Y-%m-%d}",
        f"- 用户规模：{len(users)}",
        "",
    ]
    for full, count in sorted(loaded.items()):
        report.append(f"- `{full}`：{count} 行")
    report.append("")
    report.append("## MySQL表行数抽查")
    schema_counts = run_sql(
        """
        SELECT table_schema, COUNT(*) FROM information_schema.tables
        WHERE table_schema IN ('ods','dwd','dws','ads')
        GROUP BY table_schema ORDER BY table_schema;
        """,
        batch=True,
    )
    report.append("```text")
    report.append(schema_counts.strip())
    report.append("```")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"[{batch_date}] 数据生成完成，质量报告：{LOG_PATH} 用户数={len(users)}")
    return len(users), loaded


def main() -> None:
    """主入口：支持单批次（BATCH_DATE=yyyy-mm-dd）或全批次（BATCH_DATE=all）运行。

    全批次模式按时间顺序执行所有批次，首批建缓存，后续批次复用身份。
    如需从零重跑，先删除缓存文件: data/generated/user_identity_cache.json
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    run_sql("SET GLOBAL local_infile = 1;")
    products = make_products()

    batch_env = os.getenv("BATCH_DATE", "all")
    if batch_env.lower() == "all":
        # 全批次顺序执行：首批初始化，后续批次复用缓存
        batch_dates = [d for d, _ in BATCH_USER_COUNTS]
        total_users = 0
        total_loaded: dict[str, int] = {}
        for idx, batch_date in enumerate(batch_dates):
            truncate = (idx == 0)  # 仅首批清空数据
            n_users, loaded = _process_single_batch(batch_date, products, truncate)
            total_users = max(total_users, n_users)
            for k, v in loaded.items():
                total_loaded[k] = (total_loaded.get(k, 0) + v)
        print(f"\n全批次生成完成：{len(batch_dates)}个批次，最终用户={total_users}，"
              f"缓存文件={IDENTITY_CACHE_PATH}")
    else:
        batch_date = date.fromisoformat(batch_env)
        if batch_date not in dict(BATCH_USER_COUNTS):
            raise ValueError(f"不支持的批次日期：{batch_date}")
        truncate = os.getenv("TRUNCATE_BEFORE_LOAD", "1") == "1"
        _process_single_batch(batch_date, products, truncate)


if __name__ == "__main__":
    main()
