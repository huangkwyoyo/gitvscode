"""
Column Binding Table —— 数据开发 Agent 的中枢神经

职责：
  1. 维护 metric_name → fully_qualified_column 的确定性映射
  2. 维护 dimension_name → 各表对应列名的确定性映射
  3. 维护 JOIN 白名单（从 sql_safety_policy.yml 衍生）
  4. 启动时从 TianShu DuckDB + Contracts 加载，运行时不可变

LLM 不允许访问此模块。SQL 编译器（Layer 4）是此模块的唯一消费者。

数据来源（按优先级）：
  1. TianShu DuckDB meta.metric_definitions 表（运行时加载）
  2. TianShu contracts/metric_contract.yml（静态快照）
  3. TianShu contracts/semantic_contract.yml（表结构）
  4. TianShu contracts/sql_safety_policy.yml（JOIN 白名单）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BindingEntry:
    """指标绑定条目——将已注册指标映射到物理列"""

    metric_name: str
    zh_name: str
    domain: str  # traffic | violation | safety | supply
    unit: str
    # G3 汇总表绑定（优先使用）
    g3: Optional[str]  # fully qualified，如 "gold.dws_daily_trip_summary.trip_count"
    g3_table: Optional[str]  # 如 "gold.dws_daily_trip_summary"
    g3_available: bool
    # G2 降级绑定（G3 不可用时使用）
    g2: Optional[str]  # 始终为 None（G2 需要聚合表达式，不直接映射列）
    g2_expression: Optional[str]  # 如 "COUNT(*)", "SUM(fare_amount)"
    g2_table: Optional[str]  # 如 "gold.fact_trips"


@dataclass
class DimensionBinding:
    """维度绑定——将维度名映射到各表的具体列"""

    dim_name: str
    default_source: str  # 默认来源，如 "gold.dim_date.date"
    mappings: dict[str, str]  # table → column，如 {"gold.dws_daily_trip_summary": "trip_date"}


@dataclass
class JoinPath:
    """已核准的 JOIN 路径"""

    left_table: str
    right_table: str
    left_key: str
    right_key: str
    join_type: str  # "LEFT JOIN" | "INNER JOIN"
    constraint_ref: str  # 约束来源


# ═══════════════════════════════════════════════════════════
# 静态绑定表（编译时确定，与 meta.metric_definitions 对齐）
# ═══════════════════════════════════════════════════════════

METRIC_BINDINGS: list[BindingEntry] = [
    # ── 行程域（Traffic）──
    BindingEntry(
        metric_name="trip_count",
        zh_name="行程量",
        domain="traffic",
        unit="次",
        g3="gold.dws_daily_trip_summary.trip_count",
        g3_table="gold.dws_daily_trip_summary",
        g3_available=True,
        g2=None,
        g2_expression="COUNT(*)",
        g2_table="gold.fact_trips",
    ),
    BindingEntry(
        metric_name="total_fare_amount",
        zh_name="总车费收入",
        domain="traffic",
        unit="美元",
        g3="gold.dws_daily_trip_summary.total_fare_amount",
        g3_table="gold.dws_daily_trip_summary",
        g3_available=True,
        g2=None,
        g2_expression="SUM(gold.fact_trips.fare_amount)",
        g2_table="gold.fact_trips",
    ),
    BindingEntry(
        metric_name="total_tip_amount",
        zh_name="总小费金额",
        domain="traffic",
        unit="美元",
        g3=None,  # G3 汇总表不含小费列，需降级到 G2
        g3_table=None,
        g3_available=False,
        g2=None,
        g2_expression="SUM(gold.fact_trips.tip_amount)",
        g2_table="gold.fact_trips",
    ),
    BindingEntry(
        metric_name="total_distance_miles",
        zh_name="总行驶距离",
        domain="traffic",
        unit="英里",
        g3="gold.dws_daily_trip_summary.total_distance_miles",
        g3_table="gold.dws_daily_trip_summary",
        g3_available=True,
        g2=None,
        g2_expression="SUM(gold.fact_trips.trip_miles)",
        g2_table="gold.fact_trips",
    ),
    # ── 违章域（Violation）──
    BindingEntry(
        metric_name="parking_violation_count",
        zh_name="停车罚单数量",
        domain="violation",
        unit="张",
        g3="gold.dws_daily_parking_summary.violation_count",
        g3_table="gold.dws_daily_parking_summary",
        g3_available=True,
        g2=None,
        g2_expression="COUNT(*)",
        g2_table="gold.fact_parking_violations",
    ),
    BindingEntry(
        metric_name="standard_fine_total",
        zh_name="标准罚款总额",
        domain="violation",
        unit="美元",
        g3="gold.dws_daily_parking_summary.standard_fine_total",
        g3_table="gold.dws_daily_parking_summary",
        g3_available=True,
        g2=None,
        g2_expression="SUM(gold.dim_violation_type.standard_fine_amount)",
        g2_table="gold.dim_violation_type",
    ),
    # ── 安全域（Safety）──
    BindingEntry(
        metric_name="crash_count",
        zh_name="事故数量",
        domain="safety",
        unit="起",
        g3="gold.dws_daily_crash_summary.crash_count",
        g3_table="gold.dws_daily_crash_summary",
        g3_available=True,
        g2=None,
        g2_expression="COUNT(*)",
        g2_table="gold.fact_crashes",
    ),
    BindingEntry(
        metric_name="persons_killed",
        zh_name="死亡人数",
        domain="safety",
        unit="人",
        g3="gold.dws_daily_crash_summary.persons_killed",
        g3_table="gold.dws_daily_crash_summary",
        g3_available=True,
        g2=None,
        g2_expression="SUM(gold.fact_crashes.persons_killed)",
        g2_table="gold.fact_crashes",
    ),
    BindingEntry(
        metric_name="persons_injured",
        zh_name="受伤人数",
        domain="safety",
        unit="人",
        g3="gold.dws_daily_crash_summary.persons_injured",
        g3_table="gold.dws_daily_crash_summary",
        g3_available=True,
        g2=None,
        g2_expression="SUM(gold.fact_crashes.persons_injured)",
        g2_table="gold.fact_crashes",
    ),
    # ── 供给域（Supply）──
    BindingEntry(
        metric_name="tif_payment_amount",
        zh_name="TIF支付金额",
        domain="supply",
        unit="美元",
        g3=None,  # 无 G3 汇总表
        g3_table=None,
        g3_available=False,
        g2=None,
        g2_expression="SUM(gold.fact_tif_payments.total_payment_amount)",
        g2_table="gold.fact_tif_payments",
    ),
]

# ═══════════════════════════════════════════════════════════
# 维度绑定表
# ═══════════════════════════════════════════════════════════

DIMENSION_BINDINGS: list[DimensionBinding] = [
    DimensionBinding(
        dim_name="date",
        default_source="gold.dim_date.date",
        mappings={
            "gold.dws_daily_trip_summary": "trip_date",
            "gold.dws_zone_trip_summary": "zone_name",  # 此表不直接含 date
            "gold.dws_daily_parking_summary": "issue_date",
            "gold.dws_daily_crash_summary": "crash_date",
            "gold.fact_trips": "pickup_date_key",  # 需 JOIN dim_date
            "gold.fact_parking_violations": "issue_date_key",
            "gold.fact_crashes": "crash_date_key",
            "gold.fact_tif_payments": "payment_date_key",
            "gold.fact_driver_applications": "app_date_key",
        },
    ),
    DimensionBinding(
        dim_name="borough",
        default_source="gold.dim_taxi_zone.borough",
        mappings={
            "gold.dim_taxi_zone": "borough",
            "gold.fact_crashes": "borough",
            "gold.fact_parking_violations": "borough",
        },
    ),
]

# ═══════════════════════════════════════════════════════════
# JOIN 白名单（从 sql_safety_policy.yml 衍生）
# ═══════════════════════════════════════════════════════════

JOIN_WHITELIST: list[JoinPath] = [
    # 事实表 ↔ 日期维表
    JoinPath(
        left_table="gold.fact_trips",
        right_table="gold.dim_date",
        left_key="pickup_date_key",
        right_key="date_key",
        join_type="INNER JOIN",
        constraint_ref="sql_safety_policy.yml#join_whitelist",
    ),
    JoinPath(
        left_table="gold.fact_parking_violations",
        right_table="gold.dim_date",
        left_key="issue_date_key",
        right_key="date_key",
        join_type="INNER JOIN",
        constraint_ref="sql_safety_policy.yml#join_whitelist",
    ),
    JoinPath(
        left_table="gold.fact_crashes",
        right_table="gold.dim_date",
        left_key="crash_date_key",
        right_key="date_key",
        join_type="INNER JOIN",
        constraint_ref="sql_safety_policy.yml#join_whitelist",
    ),
    JoinPath(
        left_table="gold.fact_tif_payments",
        right_table="gold.dim_date",
        left_key="payment_date_key",
        right_key="date_key",
        join_type="INNER JOIN",
        constraint_ref="sql_safety_policy.yml#join_whitelist",
    ),
    # 事实表 ↔ 维表
    JoinPath(
        left_table="gold.fact_trips",
        right_table="gold.dim_vehicle",
        left_key="base_no",
        right_key="license_number",
        join_type="LEFT JOIN",
        constraint_ref="sql_safety_policy.yml#join_whitelist",
    ),
    JoinPath(
        left_table="gold.fact_parking_violations",
        right_table="gold.dim_violation_type",
        left_key="violation_code",
        right_key="violation_code",
        join_type="LEFT JOIN",
        constraint_ref="sql_safety_policy.yml#join_whitelist",
    ),
    # G3 跨主题汇总（仅允许 trip ↔ crash 通过日期）
    JoinPath(
        left_table="gold.dws_daily_trip_summary",
        right_table="gold.dws_daily_crash_summary",
        left_key="trip_date",
        right_key="crash_date",
        join_type="LEFT JOIN",
        constraint_ref="sql_safety_policy.yml#join_whitelist",
    ),
]

# ═══════════════════════════════════════════════════════════
# 禁止的表（从 semantic_contract.yml 衍生）
# ═══════════════════════════════════════════════════════════

FORBIDDEN_TABLE_PATTERNS: list[str] = [
    "bronze.*",
    "silver.*",
    "*.raw_*",
]

# ═══════════════════════════════════════════════════════════
# 动态加载缓存
# ═══════════════════════════════════════════════════════════

_loaded_metric_bindings: list[BindingEntry] | None = None
_loaded_dimension_bindings: list[DimensionBinding] | None = None
_load_attempted: bool = False

# P1-1 修复：加载状态追踪——用于诊断事实源漂移
_load_source: str = "not_attempted"  # "tianShu" | "static_fallback" | "not_attempted"


def load_from_tianShu(duckdb_path: str) -> dict[str, list]:
    """
    从 TianShu DuckDB 动态加载事实源

    读取 meta.metric_definitions（已审批指标）和 meta.semantic_dimensions，
    构建 BindingEntry 和 DimensionBinding 对象。

    加载策略：
    1. TianShu 中 audit_status='approved' 的指标优先使用
    2. 静态 METRIC_BINDINGS 作为 fallback（TianShu 未覆盖的指标）
    3. 对 TianShu 返回的每个 Gold 表执行 DESCRIBE，获取真实列名
    4. 检测 G3 表是否实际包含该指标列（g3_available）

    返回：{"metrics": [...], "dimensions": [...]}
    """
    global _loaded_metric_bindings, _loaded_dimension_bindings, _load_attempted, _load_source

    if _load_attempted:
        return {
            "metrics": _loaded_metric_bindings or METRIC_BINDINGS,
            "dimensions": _loaded_dimension_bindings or DIMENSION_BINDINGS,
        }

    _load_attempted = True

    try:
        import duckdb

        con = duckdb.connect(duckdb_path, read_only=True)

        # ── 加载指标定义 ──
        try:
            rows = con.execute(
                "SELECT metric_name, metric_name_zh, source_table, calculation_sql "
                "FROM meta.metric_definitions WHERE audit_status = 'approved'"
            ).fetchall()
        except Exception:
            rows = []

        if rows:
            # 收集所有 Gold 表，批量获取列名用于 g3_available 检测
            gold_tables: set[str] = set()
            for row in rows:
                table = row[2]  # source_table
                if table and table.startswith("gold."):
                    gold_tables.add(table)

            # 批量 DESCRIBE 获取真实列名
            table_columns: dict[str, set[str]] = {}
            for table in sorted(gold_tables):
                try:
                    cols = con.execute(f"DESCRIBE {table}").fetchall()
                    table_columns[table] = {c[0].lower() for c in cols}
                except Exception:
                    table_columns[table] = set()

            # 构建域映射（从指标名推断域）
            domain_map = {
                "trip": "traffic", "fare": "traffic", "distance": "traffic",
                "tip": "traffic",
                "parking": "violation", "violation": "violation", "fine": "violation",
                "crash": "safety", "killed": "safety", "injured": "safety",
                "tif": "supply", "payment": "supply",
            }

            tianShu_entries: list[BindingEntry] = []
            for row in rows:
                metric_name = row[0]
                zh_name = row[1] or metric_name
                source_table = row[2]
                calc_sql = row[3] or ""

                # 推断域
                domain = "traffic"
                for keyword, d in domain_map.items():
                    if keyword in (metric_name or "").lower():
                        domain = d
                        break

                # 检测 G3 可用性
                g3_available = False
                g3_column = None
                if source_table and source_table in table_columns:
                    cols = table_columns[source_table]
                    # 从 calculation_sql 提取列名（如 "sum(trip_count)" → "trip_count"）
                    import re
                    col_match = re.search(r'(\w+)\s*\)', calc_sql) if calc_sql else None
                    if not col_match:
                        col_match = re.search(r'(\w+)$', calc_sql.strip()) if calc_sql else None
                    col_name = col_match.group(1).lower() if col_match else metric_name.lower()
                    if col_name in cols:
                        g3_available = True
                        g3_column = f"{source_table}.{col_name}"

                # 推断 G2 fallback
                g2_table = source_table.replace("dws_daily_", "fact_").replace("_summary", "s") if source_table else None
                # 部分 G3 表名映射到 G2 表需要特殊处理
                g2_table_map = {
                    "gold.dws_daily_trip_summary": "gold.fact_trips",
                    "gold.dws_daily_parking_summary": "gold.fact_parking_violations",
                    "gold.dws_daily_crash_summary": "gold.fact_crashes",
                }
                if source_table in g2_table_map:
                    g2_table = g2_table_map[source_table]

                tianShu_entries.append(BindingEntry(
                    metric_name=metric_name,
                    zh_name=zh_name,
                    domain=domain,
                    unit="",
                    g3=g3_column,
                    g3_table=source_table if g3_available else None,
                    g3_available=g3_available,
                    g2=None,
                    g2_expression=calc_sql if calc_sql and not g3_available else None,
                    g2_table=g2_table,
                ))

            # 合并：TianShu 覆盖同 metric_name 的静态条目
            static_by_name = {e.metric_name: e for e in METRIC_BINDINGS}
            tianShu_by_name = {e.metric_name: e for e in tianShu_entries}

            merged: list[BindingEntry] = []
            for entry in METRIC_BINDINGS:
                if entry.metric_name in tianShu_by_name:
                    ts = tianShu_by_name[entry.metric_name]
                    # TianShu 发现 G3 可用 → 使用 TianShu 的 G3 信息
                    if ts.g3_available and ts.g3:
                        merged.append(BindingEntry(
                            metric_name=entry.metric_name,
                            zh_name=entry.zh_name or ts.zh_name,
                            domain=entry.domain,
                            unit=entry.unit,
                            g3=ts.g3,
                            g3_table=ts.g3_table,
                            g3_available=True,
                            g2=entry.g2,
                            g2_expression=entry.g2_expression,
                            g2_table=entry.g2_table,
                        ))
                    else:
                        merged.append(entry)
                else:
                    merged.append(entry)

            # 追加 TianShu 独有的指标
            for ts in tianShu_entries:
                if ts.metric_name not in static_by_name:
                    merged.append(ts)

            _loaded_metric_bindings = merged
            _load_source = "tianShu"
        else:
            _loaded_metric_bindings = METRIC_BINDINGS
            _load_source = "static_fallback"
        try:
            dim_rows = con.execute(
                "SELECT dimension_name, dimension_name_zh, source_table, source_column "
                "FROM meta.semantic_dimensions"
            ).fetchall()
        except Exception:
            dim_rows = []

        if dim_rows:
            merged_dims: list[DimensionBinding] = []
            static_dims_by_name = {d.dim_name: d for d in DIMENSION_BINDINGS}
            new_mappings: dict[str, dict[str, str]] = {}

            for row in dim_rows:
                dim_name = row[0]
                source_table = row[2]
                source_column = row[3]

                if dim_name not in new_mappings:
                    new_mappings[dim_name] = {}
                if source_table and source_column:
                    new_mappings[dim_name][source_table] = source_column

            for dim_name, mappings in new_mappings.items():
                if dim_name in static_dims_by_name:
                    # 合并：TianShu 映射覆盖静态映射中同 table 的条目
                    static_dim = static_dims_by_name[dim_name]
                    merged_mappings = dict(static_dim.mappings)
                    merged_mappings.update(mappings)
                    merged_dims.append(DimensionBinding(
                        dim_name=dim_name,
                        default_source=static_dim.default_source,
                        mappings=merged_mappings,
                    ))
                else:
                    # TianShu 独有的维度
                    default_source = list(mappings.values())[0] if mappings else ""
                    if mappings:
                        first_table = list(mappings.keys())[0]
                        default_source = f"{first_table}.{mappings[first_table]}"
                    merged_dims.append(DimensionBinding(
                        dim_name=dim_name,
                        default_source=default_source,
                        mappings=mappings,
                    ))

            # 追加静态独有的维度
            for dim_name, static_dim in static_dims_by_name.items():
                if dim_name not in new_mappings:
                    merged_dims.append(static_dim)

            _loaded_dimension_bindings = merged_dims
        else:
            _loaded_dimension_bindings = DIMENSION_BINDINGS

        con.close()

    except Exception:
        # DuckDB 连接失败或查询出错 → 使用静态绑定
        _load_source = "static_fallback"
        if _loaded_metric_bindings is None:
            _loaded_metric_bindings = METRIC_BINDINGS
        if _loaded_dimension_bindings is None:
            _loaded_dimension_bindings = DIMENSION_BINDINGS

    return {
        "metrics": _loaded_metric_bindings,
        "dimensions": _loaded_dimension_bindings,
    }


def get_binding_by_metric_name(metric_name: str) -> Optional[BindingEntry]:
    """按指标名查绑定（优先使用 TianShu 动态加载数据）"""
    source = _loaded_metric_bindings if _loaded_metric_bindings is not None else METRIC_BINDINGS
    for entry in source:
        if entry.metric_name == metric_name:
            return entry
    return None


def get_dimension_binding(dim_name: str) -> Optional[DimensionBinding]:
    """按维度名查绑定（优先使用 TianShu 动态加载数据）"""
    source = _loaded_dimension_bindings if _loaded_dimension_bindings is not None else DIMENSION_BINDINGS
    for entry in source:
        if entry.dim_name == dim_name:
            return entry
    return None


def get_join_path(left_table: str, right_table: str) -> Optional[JoinPath]:
    """查找两个表之间的白名单 JOIN 路径"""
    # 尝试双向匹配
    for path in JOIN_WHITELIST:
        if (path.left_table == left_table and path.right_table == right_table) or \
           (path.left_table == right_table and path.right_table == left_table):
            return path
    return None


def get_metrics_by_domain(domain: str) -> list[BindingEntry]:
    """按业务域获取所有指标（优先使用 TianShu 动态加载数据）"""
    source = _loaded_metric_bindings if _loaded_metric_bindings is not None else METRIC_BINDINGS
    return [e for e in source if e.domain == domain]


def get_all_metric_names() -> list[str]:
    """获取所有已注册指标名（用于 Layer 2 模糊匹配和校验）"""
    source = _loaded_metric_bindings if _loaded_metric_bindings is not None else METRIC_BINDINGS
    return [e.metric_name for e in source]


def reload_bindings():
    """重置加载状态，强制下次访问时重新从 TianShu 加载"""
    global _loaded_metric_bindings, _loaded_dimension_bindings, _load_attempted, _load_source
    _loaded_metric_bindings = None
    _loaded_dimension_bindings = None
    _load_attempted = False
    _load_source = "not_attempted"


def get_load_status() -> dict[str, object]:
    """
    P1-1 修复：返回事实源加载状态，用于诊断漂移问题

    返回字典包含：
      - source: "tianShu" | "static_fallback" | "not_attempted"
      - attempted: 是否已尝试加载
      - metric_count: 当前活跃的指标数量
      - metric_names: 当前活跃的指标名列表
    """
    source = _loaded_metric_bindings if _loaded_metric_bindings is not None else METRIC_BINDINGS
    return {
        "source": _load_source,
        "attempted": _load_attempted,
        "metric_count": len(source),
        "metric_names": [e.metric_name for e in source],
    }


def is_table_forbidden(table_name: str) -> tuple[bool, str]:
    """检查表名是否命中禁止模式"""
    import fnmatch
    for pattern in FORBIDDEN_TABLE_PATTERNS:
        if fnmatch.fnmatch(table_name, pattern):
            return True, f"表 '{table_name}' 命中禁止模式 '{pattern}'"
    # 同时检查裸露的 bronze/silver schema
    if table_name.startswith("bronze.") or table_name.startswith("silver."):
        return True, f"禁止查询 '{table_name}'：Bronze/Silver 层不对外开放"
    return False, ""


def validate_metric_exists(metric_name: str) -> tuple[bool, str]:
    """校验指标名是否在绑定表中（使用动态或静态绑定）"""
    entry = get_binding_by_metric_name(metric_name)
    if entry is None:
        registered = get_all_metric_names()
        return False, f"指标 '{metric_name}' 未注册。已注册指标: {registered}"
    return True, ""
