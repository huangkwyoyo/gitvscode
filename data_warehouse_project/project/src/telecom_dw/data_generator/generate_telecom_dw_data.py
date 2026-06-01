"""生成本地电信数仓模拟数据。"""

from __future__ import annotations

import csv
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

SEED = 20260531
USER_COUNT = 100_000
ACCOUNT_COUNT = 100_000
TERMINAL_COUNT = 20_000
STAFF_COUNT = 8_000
ORG_COUNT = 800
CHANNEL_COUNT = 500
APPLICATION_COUNT = 300
ORDER_COUNT = 200_000
RECHARGE_COUNT = 900_000
USAGE_COUNT = 3_600_000
DPI_COUNT = 3_000_000
COMPLAINT_COUNT = 30_000
ODS_DEFAULT_ROWS = 50_000
ODS_TABLE_ROWS = {
    "ods_user_profile_daily": 1_200_000,
    "ods_user_profile_monthly": 1_200_000,
    "ods_account_income_monthly": 1_200_000,
    "ods_arrears_billing_monthly": 1_200_000,
    "ods_recharge_daily": 900_000,
    "ods_bestpay_transaction_monthly": 900_000,
    "ods_dpi_usage_daily": 3_000_000,
    "ods_digital_channel_order_daily": 200_000,
    "ods_digital_channel_order_monthly": 200_000,
    "ods_complaint_daily": 30_000,
    "ods_arrears_daily_part1": 400_000,
    "ods_arrears_daily_part2": 400_000,
    "ods_arrears_daily_part3": 400_000,
    "ods_combo_product_monthly_part1": 40_000,
    "ods_combo_product_monthly_part2": 40_000,
    "ods_combo_product_monthly_part3": 40_000,
    "ods_combo_product_monthly_part4": 40_000,
    "ods_combo_product_monthly_part5": 40_000,
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

SURNAMES = list("王李张刘陈杨赵黄周吴徐孙胡朱高林何郭马罗梁宋郑谢韩唐冯于董萧程曹袁邓许傅沈曾彭吕苏卢蒋蔡贾丁魏薛叶阎余潘杜戴夏钟汪田任姜范方石姚谭廖邹熊金陆郝孔白崔康毛邱秦江史顾侯邵孟龙万段雷钱汤尹黎易常武乔贺赖龚文")
GIVEN_CHARS = list("伟刚勇毅俊峰强军平保东文辉力明永健世广志义兴良海山仁波宁贵福生龙元全国胜学祥才发武新利清飞彬富顺信子杰涛昌成康星光天达安岩中茂进林有坚和彪博诚先敬震振壮会思群豪心邦承乐绍功松善厚庆磊民友裕河哲江超浩亮政谦亨奇固之轮翰朗伯宏言若鸣朋斌梁栋维启克伦翔旭鹏泽晨辰士以建家致树炎德行时泰盛雄琛钧冠策腾榕风航弘")
PHONE_PREFIXES = ["130", "131", "132", "155", "156", "166", "175", "176", "185", "186", "188", "189", "191", "193", "198", "199"]
MONTHS = [date(2025, m, 1) for m in range(1, 13)]
DATES = [date(2025, 1, 1) + timedelta(days=i) for i in range(365)]


def lifecycle_date(user: dict[str, object], candidate: date) -> date:
    """保证业务日期落在用户生命周期内。"""
    start = user["activation_date"]
    end = user["termination_date"] or date(2025, 12, 31)
    if candidate < start:
        return start
    if candidate > end:
        return end
    return candidate


def lifecycle_month(user: dict[str, object], candidate: date) -> date:
    """保证账期月份落在用户生命周期月份内。"""
    d = lifecycle_date(user, candidate)
    return date(d.year, d.month, 1)


def lifecycle_datetime(user: dict[str, object], candidate: date) -> datetime:
    """生成落在用户生命周期内且精确到秒的业务时间。"""
    d = lifecycle_date(user, candidate)
    return datetime(d.year, d.month, d.day, random.randint(0, 23), random.randint(0, 59), random.randint(1, 59))


def payment_datetime(user: dict[str, object], created_time: datetime) -> datetime:
    """生成不早于创建时间且不晚于离网时间的支付时间。"""
    end_date = user["termination_date"] or date(2025, 12, 31)
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


def make_products() -> list[dict[str, object]]:
    products = []
    specs = [
        ("basic_4g", "基础4G套餐", 39, 20, 100, 0.25),
        ("standard_5g", "标准5G套餐", 99, 80, 500, 0.40),
        ("premium_5g", "高价值5G套餐", 199, 180, 1200, 0.20),
        ("family_fusion", "家庭融合套餐", 239, 220, 1000, 0.10),
        ("low_activity", "低活跃保号套餐", 19, 5, 50, 0.05),
    ]
    idx = 1
    for typ, name, fee, gb, voice, weight in specs:
        for variant in range(1, 21):
            products.append(
                {
                    "product_id": f"P{idx:05d}",
                    "product_code": f"{typ.upper()}_{variant:02d}",
                    "product_name": f"{name}{variant:02d}",
                    "product_type": typ,
                    "price_plan_id": f"PP{idx:05d}",
                    "price_plan_name": f"{name}{variant:02d}",
                    "monthly_fee": max(8, fee + random.choice([-20, -10, 0, 10, 20])),
                    "included_data_gb": max(1, gb + random.randint(-5, 20)),
                    "included_voice_min": max(20, voice + random.randint(-50, 200)),
                    "weight": weight,
                }
            )
            idx += 1
    return products


def build_master_data(products: list[dict[str, object]]):
    product_weights = [(p, p["weight"]) for p in products]
    users = []
    used_phone = set()
    for i in range(1, USER_COUNT + 1):
        gender = "男" if random.random() < 0.51 else "女"
        age_band = weighted_choice(
            [((18, 25), 0.18), ((26, 35), 0.32), ((36, 45), 0.25), ((46, 60), 0.20), ((61, 78), 0.05)]
        )
        age = random.randint(*age_band)
        province, city, districts, tier = random.choice(PROVINCES)
        district = random.choice(districts)
        product = weighted_choice(product_weights)
        if tier == 1 and random.random() < 0.25:
            product = random.choice([p for p in products if p["product_type"] in ("standard_5g", "premium_5g", "family_fusion")])
        if age <= 30 and random.random() < 0.20:
            product = random.choice([p for p in products if "5g" in p["product_type"]])
        phone = phone_number(i)
        while phone in used_phone:
            phone = phone_number(i)
        used_phone.add(phone)
        active = random.random() < (0.97 if tier <= 2 else 0.94)
        activation = date(2020, 1, 1) + timedelta(days=random.randint(0, 1825))
        users.append(
            {
                "user_id": f"U{i:012d}",
                "customer_id": f"C{i:012d}",
                "account_id": f"A{i:012d}",
                "product_id": product["product_id"],
                "service_number_id": phone,
                "customer_name": chinese_name(gender),
                "gender_type": gender,
                "age_count": age,
                "province_name": province,
                "city_name": city,
                "district_name": district,
                "city_tier": tier,
                "activation_date": activation,
                "termination_date": None if active else date(2025, random.randint(1, 12), random.randint(1, 28)),
                "is_active_subscriber": 1 if active else 0,
                "payment_timing_type": "postpaid" if random.random() < 0.72 else "prepaid",
                "service_network_type": "mobile",
                "product": product,
                "risk_score": random.random(),
            }
        )
    return users


def row_for_columns(columns: list[str], values: dict[str, object]) -> dict[str, object]:
    return {c: values.get(c) for c in columns}


def generic_value(col: str, i: int, users, products, channels, orgs, staff, apps) -> object:
    user = users[i % len(users)]
    product = user["product"]
    if col == "synthetic_row_id":
        return i + 1
    if col in user:
        return user[col]
    if col in product:
        return product[col]
    if col.endswith("_id"):
        if "customer" in col:
            return user["customer_id"]
        if "account" in col:
            return user["account_id"]
        if "product" in col or "price_plan" in col or "offer" in col:
            return product["product_id"]
        if "channel" in col:
            return channels[i % len(channels)]["channel_id"]
        if "department" in col:
            return orgs[i % len(orgs)]["department_id"]
        if "staff" in col:
            return staff[i % len(staff)]["staff_id"]
        if "application" in col:
            return apps[i % len(apps)]["application_id"]
        if "terminal" in col:
            return f"T{i % TERMINAL_COUNT + 1:012d}"
        return f"ID{i+1:012d}"
    if col.startswith("is_"):
        return 1 if random.random() < 0.8 else 0
    if col.endswith("_date"):
        return random.choice(DATES)
    if col.endswith("_time"):
        d = random.choice(DATES)
        return datetime(d.year, d.month, d.day, random.randint(0, 23), random.randint(0, 59), random.randint(0, 59))
    if col.endswith("_amount") or col.endswith("_fee"):
        return round(max(0, random.gauss(product["monthly_fee"], product["monthly_fee"] * 0.35)), 2)
    if col.endswith("_count"):
        return max(0, int(random.expovariate(1 / 8)))
    if col.endswith("_usage_mb"):
        return round(max(0, random.gauss(product["included_data_gb"] * 1024 / 20, 500)), 3)
    if col.endswith("_usage_min"):
        return round(max(0, random.gauss(product["included_voice_min"] / 20, 20)), 3)
    if col.endswith("_status"):
        return random.choice(["active", "completed", "pending", "closed"])
    if col.endswith("_type"):
        return random.choice(["mobile", "5g", "4g", "online", "offline"])
    if col.endswith("_code"):
        return f"CODE_{random.randint(1, 999):03d}"
    if col.endswith("_name"):
        return f"模拟{col}"
    return f"模拟值{i % 1000}"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    run_sql("SET GLOBAL local_infile = 1;")
    tables = get_columns()
    truncate_all(tables)

    products = make_products()
    users = build_master_data(products)
    channels = [
        {
            "channel_id": f"CH{i:05d}",
            "channel_code": f"CH_CODE_{i:05d}",
            "channel_name": f"渠道{i:05d}",
            "channel_type": random.choice(["APP", "营业厅", "代理商", "电商", "客服"]),
            "parent_channel_id": None if i <= 20 else f"CH{random.randint(1, 20):05d}",
        }
        for i in range(1, CHANNEL_COUNT + 1)
    ]
    orgs = [
        {
            "department_id": f"D{i:05d}",
            "department_code": f"DEPT_{i:05d}",
            "department_name": f"组织部门{i:05d}",
            "department_type": random.choice(["省公司", "市公司", "区县分公司", "网格"]),
            "parent_department_id": None if i <= 20 else f"D{random.randint(1, 20):05d}",
        }
        for i in range(1, ORG_COUNT + 1)
    ]
    staff = [
        {
            "staff_id": f"S{i:06d}",
            "staff_code": f"STAFF_{i:06d}",
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
            "account_id": u["account_id"], "customer_id": u["customer_id"], "account_code": u["account_id"],
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
        for i in range(USAGE_COUNT):
            u = users[random.randrange(USER_COUNT)]
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
        for i in range(1, RECHARGE_COUNT + 1):
            u = users[random.randrange(USER_COUNT)]
            amount = max(10, random.gauss(u["product"]["monthly_fee"], u["product"]["monthly_fee"] * 0.35))
            yield row_for_columns(cols("dwd", "fact_recharge_daily"), {
                "recharge_event_id": f"R{i:012d}", "user_id": u["user_id"], "recharge_date": lifecycle_date(u, random.choice(DATES)),
                "recharge_method_type": weighted_choice([(methods[0], 0.40), (methods[1], 0.30), (methods[2], 0.20), (methods[3], 0.06), (methods[4], 0.04)]),
                "recharge_amount": round(amount, 2),
            })

    loaded["dwd.fact_recharge_daily"] = load_rows("dwd", "fact_recharge_daily", cols("dwd", "fact_recharge_daily"), recharge_rows())

    def order_rows():
        for i in range(1, ORDER_COUNT + 1):
            u = users[random.randrange(USER_COUNT)]
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
        for i in range(1, COMPLAINT_COUNT + 1):
            u = users[random.randrange(USER_COUNT)]
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
        for _ in range(DPI_COUNT):
            u = users[random.randrange(USER_COUNT)]
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
        row_count = ODS_TABLE_ROWS.get(table, ODS_DEFAULT_ROWS)
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
    report = ["# 数据质量校验报告", "", f"- 随机种子：{SEED}", f"- 用户规模：{USER_COUNT}", ""]
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
    print(f"数据生成完成，质量报告：{LOG_PATH}")


if __name__ == "__main__":
    main()
