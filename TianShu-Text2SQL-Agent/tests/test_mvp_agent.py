from src.agent import Text2SQLAgent
from src.ir import Domain, Strategy, TimeRangeType, IntentType, QuestionIntent
from src.resolver import MetricInfo, AgentContext, G2FactInfo, G3SummaryInfo, TableInfo
from src.sql_gen import validate_sql_safety


class TestRuleBasedMVP:
    """规则版 MVP 的端到端行为测试"""

    def test_trip_count_question_builds_g3_sql(self):
        """行程量问题应解析为 G3 日汇总 SQL"""
        agent = Text2SQLAgent()

        response = agent.ask("2026年1月每天有多少行程？")

        assert response.clarification_needed is False
        assert response.refusal is False
        assert response.intent.domain == Domain.TRAFFIC
        assert response.intent.metrics == ["trip_count"]
        assert response.intent.time_range.type == TimeRangeType.ABSOLUTE
        assert response.intent.time_range.start == "2026-01-01"
        assert response.intent.time_range.end == "2026-01-31"
        assert response.plan.strategy == Strategy.G3_DIRECT
        assert response.plan.primary_table == "gold.dws_daily_trip_summary"
        assert response.result.sql.startswith("SELECT")
        assert "FROM gold.dws_daily_trip_summary" in response.result.sql
        assert "JOIN gold.dim_date" in response.result.sql
        assert "gold.dim_date.date BETWEEN DATE '2026-01-01' AND DATE '2026-01-31'" in response.result.sql

    def test_parking_and_crash_questions_use_g3_tables(self):
        """罚单和事故问题应优先选择对应 G3 汇总表"""
        agent = Text2SQLAgent()

        parking = agent.ask("2026年2月每天停车罚单数量是多少？")
        crash = agent.ask("2026年3月每天事故数是多少？")

        assert parking.intent.metrics == ["parking_violation_count"]
        assert parking.plan.primary_table == "gold.dws_daily_parking_summary"
        assert "SUM(violation_count)" in parking.result.sql
        assert "AS parking_violation_count" in parking.result.sql
        assert crash.intent.metrics == ["crash_count"]
        assert crash.plan.primary_table == "gold.dws_daily_crash_summary"
        assert "SUM(crash_count)" in crash.result.sql

    def test_registered_g3_metrics_are_resolved_without_hardcoded_if_chain(self):
        """规则版应通过注册指标目录支持更多 G3 日度指标。"""
        agent = Text2SQLAgent()

        cases = [
            ("2026年3月每天受伤人数是多少？", "persons_injured", "gold.dws_daily_crash_summary", "SUM(persons_injured)"),
            ("2026年3月每天死亡人数是多少？", "persons_killed", "gold.dws_daily_crash_summary", "SUM(persons_killed)"),
            ("2026年2月每天罚款总额是多少？", "standard_fine_total", "gold.dws_daily_parking_summary", "SUM(standard_fine_total)"),
            ("2026年1月每天平均距离是多少？", "avg_distance_miles", "gold.dws_daily_trip_summary", "AVG(avg_distance_miles)"),
            ("2026年1月每天车费总额是多少？", "total_fare_amount", "gold.dws_daily_trip_summary", "SUM(total_fare_amount)"),
        ]

        for question, metric, table, aggregation in cases:
            response = agent.ask(question)

            assert response.clarification_needed is False
            assert response.refusal is False
            assert response.intent.metrics == [metric]
            assert response.plan.primary_table == table
            assert aggregation in response.result.sql

    def test_fuzzy_time_and_amount_need_clarification(self):
        """模糊时间和金额歧义必须反问"""
        agent = Text2SQLAgent()

        fuzzy = agent.ask("最近每天有多少行程？")
        amount = agent.ask("2026年1月每天金额是多少？")

        assert fuzzy.clarification_needed is True
        assert "时间" in fuzzy.clarification_message
        assert amount.clarification_needed is True
        assert "金额" in amount.clarification_message

    def test_write_operation_is_refused(self):
        """写操作请求必须拒绝"""
        agent = Text2SQLAgent()

        response = agent.ask("帮我删除异常停车罚单数据")

        assert response.refusal is True
        assert "只读" in response.refusal_reason

    def test_bronze_or_silver_direct_query_is_refused(self):
        """直接查询 Bronze/Silver 必须拒绝"""
        agent = Text2SQLAgent()

        response = agent.ask("直接查 bronze 原始行程表看看2026年1月有多少数据")

        assert response.refusal is True
        assert "Bronze" in response.refusal_reason


class TestSQLSafetyMVP:
    """SQL 安全校验必须覆盖契约中的基础规则"""

    def test_rejects_non_select_and_bare_table(self):
        """非 SELECT 和裸表名不能通过安全校验"""
        assert validate_sql_safety("UPDATE gold.fact_trips SET fare_amount = 0", ["UPDATE"])
        assert validate_sql_safety("SELECT * FROM fact_trips", [])

    def test_requires_gold_tables_and_dim_date_for_date_filter(self):
        """业务表必须限定在 gold，日期过滤必须通过 dim_date"""
        assert validate_sql_safety("SELECT * FROM silver.fact_trips", [])
        assert validate_sql_safety(
            "SELECT * FROM gold.fact_trips WHERE pickup_date_key BETWEEN 20260101 AND 20260131",
            [],
        )


# ═══════════════════════════════════════════════════════════════
# G3 → G2 降级规划证据链测试
# ═══════════════════════════════════════════════════════════════

# ── 测试用 fixture 数据（模拟 semantic_contract.yml + metric_contract.yml）──

def _build_test_context() -> AgentContext:
    """构造测试用 AgentContext，包含 G2/G3 元数据。

    证据来源模拟：
        - g3_summaries ← semantic_contract.yml#/g3_summary
        - g2_facts ← semantic_contract.yml#/g2_facts
    """
    g3_summaries = {
        "gold.dws_daily_crash_summary": G3SummaryInfo(
            table="gold.dws_daily_crash_summary",
            key_dimensions=["crash_date"],
            note="不包含行政区维度，需要该维度时降级到 G2",
        ),
        "gold.dws_daily_parking_summary": G3SummaryInfo(
            table="gold.dws_daily_parking_summary",
            key_dimensions=["issue_date"],
            note="不包含违章类型维度，需要该维度时降级到 G2",
        ),
    }
    g2_facts = {
        "gold.fact_crashes": G2FactInfo(
            table="gold.fact_crashes",
            zh_name="事故明细事实表",
            join_keys={"crash_date_key": "gold.dim_date.date_key"},
            note="直接包含 borough 字段，无需 JOIN 维表获取行政区",
        ),
        "gold.fact_parking_violations": G2FactInfo(
            table="gold.fact_parking_violations",
            zh_name="停车罚单明细事实表",
            join_keys={
                "issue_date_key": "gold.dim_date.date_key",
                "violation_code": "gold.dim_violation_type.violation_code",
            },
            note="当 G3 不含违章类型维度时降级使用",
        ),
        "gold.fact_tif_payments": G2FactInfo(
            table="gold.fact_tif_payments",
            zh_name="TIF 支付明细事实表",
            join_keys={"payment_date_key": "gold.dim_date.date_key"},
            note="无对应 G3 汇总表，直接使用 G2",
        ),
        "gold.fact_driver_applications": G2FactInfo(
            table="gold.fact_driver_applications",
            zh_name="司机申请明细事实表",
            join_keys={"app_date_key": "gold.dim_date.date_key"},
            note="无对应 G3 汇总表，直接使用 G2",
        ),
    }
    # 构造可用表列表（供 SQLPlan.validate() 和表名校验）
    available_tables = [
        TableInfo(schema="gold", name=t.split(".")[1])
        for tables_dict in [g3_summaries, g2_facts]
        for t in tables_dict
    ]
    # 补充维表
    available_tables.extend([
        TableInfo(schema="gold", name="dim_date"),
        TableInfo(schema="gold", name="dim_violation_type"),
        TableInfo(schema="gold", name="dim_taxi_zone"),
        TableInfo(schema="gold", name="dim_vehicle"),
    ])
    # 去重
    seen = set()
    unique_tables = []
    for t in available_tables:
        key = f"{t.schema}.{t.name}"
        if key not in seen:
            seen.add(key)
            unique_tables.append(t)

    # 构造 JOIN 白名单
    join_whitelist = [
        ("gold.dws_daily_crash_summary", "gold.dim_date"),
        ("gold.dws_daily_parking_summary", "gold.dim_date"),
        ("gold.dws_daily_trip_summary", "gold.dim_date"),
        ("gold.fact_crashes", "gold.dim_date"),
        ("gold.fact_parking_violations", "gold.dim_date"),
        ("gold.fact_parking_violations", "gold.dim_violation_type"),
        ("gold.fact_tif_payments", "gold.dim_date"),
        ("gold.fact_driver_applications", "gold.dim_date"),
    ]

    return AgentContext(
        available_metrics=[],
        available_tables=unique_tables,
        join_whitelist=join_whitelist,
        g2_facts=g2_facts,
        g3_summaries=g3_summaries,
    )


def _make_metric(name, zh_name, domain, aggregation, base_table, unit, g3_available, g3_table=""):
    """快捷构造 MetricInfo（用于测试注入）。"""
    return MetricInfo(
        name=name,
        zh_name=zh_name,
        domain=domain,
        aggregation=aggregation,
        base_table=base_table,
        unit=unit,
        g3_available=g3_available,
        g3_table=g3_table,
        synonyms=[zh_name] if zh_name else [],
        keyword_groups=[(zh_name,)] if zh_name else [],
        aliases=[],
        description="",
        caution="",
        source="test",
    )


class TestG3ToG2Downgrade:
    """G3 → G2 降级规划 — 证据链闭环测试。

    每个测试断言：
        - plan.strategy（策略枚举）
        - plan.downgrade_reason（降级原因，非 G3_DIRECT 时必须非空）
        - plan.primary_table（事实表，须来自 metric_contract）
        - plan.group_by（分组字段）
        - plan.joins（JOIN 信息，须来自 semantic_contract）
    """

    @staticmethod
    def _inject_metrics(agent, metrics):
        """向 Agent 的 context 注入测试指标。"""
        agent._context.available_metrics = metrics

    # ── 样例 1: 每天受伤人数 → G3_DIRECT（不降级）──

    def test_g3_direct_no_downgrade(self, monkeypatch):
        """证据链：G3 覆盖 date 维度 → G3_DIRECT，无降级"""
        agent = Text2SQLAgent()
        ctx = _build_test_context()
        monkeypatch.setattr(agent, "_context", ctx)

        metric = _make_metric(
            "persons_injured", "受伤人数", "safety",
            "SUM(persons_injured)", "gold.fact_crashes", "人",
            g3_available=True, g3_table="gold.dws_daily_crash_summary",
        )
        self._inject_metrics(agent, [metric])

        response = agent.ask("2026年3月每天受伤人数是多少？")

        assert response.clarification_needed is False
        assert response.plan.strategy == Strategy.G3_DIRECT
        assert response.plan.primary_table == "gold.dws_daily_crash_summary"
        assert response.plan.downgrade_reason is None  # G3_DIRECT 不需要降级原因
        assert "gold.dim_date.date" in response.plan.group_by
        # 证据：G3 表来自 metric_contract.yml g3_table 字段
        assert response.intent.metrics == ["persons_injured"]
        assert response.intent.dimensions == ["date"]  # 仅 date 维度

    # ── 样例 2: 每个 borough 的受伤人数 → G2_FACT ──

    def test_borough_downgrade_g2_fact(self, monkeypatch):
        """证据链：G3 缺 borough → 降级 G2_FACT（fact_crashes 直接含 borough）"""
        agent = Text2SQLAgent()
        ctx = _build_test_context()
        monkeypatch.setattr(agent, "_context", ctx)

        metric = _make_metric(
            "persons_injured", "受伤人数", "safety",
            "SUM(persons_injured)", "gold.fact_crashes", "人",
            g3_available=True, g3_table="gold.dws_daily_crash_summary",
        )
        self._inject_metrics(agent, [metric])

        response = agent.ask("2026年3月每个 borough 的受伤人数是多少？")

        assert response.clarification_needed is False
        assert response.plan.strategy == Strategy.G2_FACT
        # 证据：fact_table = base_table（来自 metric_contract.yml）
        assert response.plan.primary_table == "gold.fact_crashes"
        # 证据：downgrade_reason 必须非空
        assert response.plan.downgrade_reason is not None
        assert "不包含 borough" in response.plan.downgrade_reason
        assert "key_dimensions=['crash_date']" in response.plan.downgrade_reason
        # 证据：group_by 含 borough（fact 直接包含，note 字段为证）
        assert "gold.fact_crashes.borough" in response.plan.group_by
        assert "gold.dim_date.date" in response.plan.group_by
        # 证据：仅 dim_date JOIN，无额外维表 JOIN
        dim_date_joins = [j for j in response.plan.joins if "dim_date" in j.table]
        assert len(dim_date_joins) == 1
        assert "crash_date_key" in dim_date_joins[0].on
        # 证据：dimensions 含 date + borough
        assert "borough" in response.intent.dimensions

    # ── 样例 3: 每种违章类型的停车罚单数 → G2_FACT_JOIN ──

    def test_violation_type_downgrade_g2_fact_join(self, monkeypatch):
        """证据链：G3 缺 violation_type → 降级 G2_FACT_JOIN（JOIN dim_violation_type）"""
        agent = Text2SQLAgent()
        ctx = _build_test_context()
        monkeypatch.setattr(agent, "_context", ctx)

        metric = _make_metric(
            "parking_violation_count", "停车罚单数量", "violation",
            "COUNT(*)", "gold.fact_parking_violations", "张",
            g3_available=True, g3_table="gold.dws_daily_parking_summary",
        )
        self._inject_metrics(agent, [metric])

        response = agent.ask("2026年2月每种违章类型的停车罚单数量是多少？")

        assert response.clarification_needed is False
        assert response.plan.strategy == Strategy.G2_FACT_JOIN
        # 证据：fact_table = base_table（来自 metric_contract.yml）
        assert response.plan.primary_table == "gold.fact_parking_violations"
        # 证据：downgrade_reason 必须非空
        assert response.plan.downgrade_reason is not None
        assert "不包含 violation_type" in response.plan.downgrade_reason
        # 证据：JOIN dim_violation_type（join_key 来自 semantic_contract.yml）
        dim_violation_joins = [j for j in response.plan.joins if "dim_violation_type" in j.table]
        assert len(dim_violation_joins) == 1
        assert "violation_code" in dim_violation_joins[0].on
        # 证据：group_by 含维表分组列
        assert any("dim_violation_type" in g for g in response.plan.group_by)
        # 证据：dimensions 含 date + violation_type
        assert "violation_type" in response.intent.dimensions

    # ── 样例 4: TIF 支付金额 → G2_FACT（无 G3 表）──

    def test_tif_no_g3_uses_g2_fact(self, monkeypatch):
        """证据链：g3_available=false → 直接 G2_FACT。

        绕过 ask() 的歧义检测（question_policy.yml 会拦截"金额"关键词），
        直接调用 _plan_query_rule 验证降级逻辑。
        """
        agent = Text2SQLAgent()
        ctx = _build_test_context()
        monkeypatch.setattr(agent, "_context", ctx)

        metric = _make_metric(
            "tif_payment_amount", "TIF 支付金额", "supply",
            "SUM(total_payment_amount)", "gold.fact_tif_payments", "美元",
            g3_available=False, g3_table="",
        )
        self._inject_metrics(agent, [metric])

        from src.ir import TimeRange
        intent = QuestionIntent(
            domain=Domain.SUPPLY,
            intent_type=IntentType.TREND,
            metrics=["tif_payment_amount"],
            time_range=TimeRange(
                type=TimeRangeType.ABSOLUTE,
                start="2026-01-01",
                end="2026-01-31",
            ),
            dimensions=["date"],
            confidence=0.95,
        )
        plan = agent._plan_query_rule(intent)

        assert plan.strategy == Strategy.G2_FACT
        # 证据：fact_table = base_table（来自 metric_contract.yml）
        assert plan.primary_table == "gold.fact_tif_payments"
        # 证据：downgrade_reason 说明无 G3
        assert plan.downgrade_reason is not None
        assert "g3_available=false" in plan.downgrade_reason
        # 证据：有 dim_date JOIN（join_key 来自 semantic_contract.yml）
        assert any("dim_date" in j.table for j in plan.joins)
        # 证据：group_by 含日期
        assert "gold.dim_date.date" in plan.group_by

    # ── 样例 5: 司机申请量 → G2_FACT（无 G3 表）──

    def test_driver_app_no_g3_uses_g2_fact(self, monkeypatch):
        """证据链：g3_available=false → 直接 G2_FACT（driver_application_count）"""
        agent = Text2SQLAgent()
        ctx = _build_test_context()
        monkeypatch.setattr(agent, "_context", ctx)

        metric = _make_metric(
            "driver_application_count", "司机申请量", "supply",
            "COUNT(*)", "gold.fact_driver_applications", "次",
            g3_available=False, g3_table="",
        )
        self._inject_metrics(agent, [metric])

        response = agent.ask("2026年1月司机申请量是多少？")

        assert response.clarification_needed is False
        assert response.plan.strategy == Strategy.G2_FACT
        # 证据：fact_table = base_table
        assert response.plan.primary_table == "gold.fact_driver_applications"
        # 证据：downgrade_reason 说明无 G3
        assert response.plan.downgrade_reason is not None
        assert "g3_available=false" in response.plan.downgrade_reason
        # 证据：dim_date JOIN
        assert any("dim_date" in j.table for j in response.plan.joins)
        assert "app_date_key" in response.plan.joins[0].on

    # ═══════════════════════════════════════════════════
    # 负例测试
    # ═══════════════════════════════════════════════════

    def test_missing_base_table_needs_clarification(self, monkeypatch):
        """负例：base_table 为空 → NEED_CLARIFICATION（不能猜表）"""
        agent = Text2SQLAgent()
        ctx = _build_test_context()
        monkeypatch.setattr(agent, "_context", ctx)

        metric = _make_metric(
            "unknown_metric", "未知指标", "traffic",
            "COUNT(*)", "", "次",  # base_table 为空！
            g3_available=False, g3_table="",
        )
        self._inject_metrics(agent, [metric])

        response = agent.ask("2026年1月未知指标是多少？")

        assert response.clarification_needed is True
        assert response.plan.strategy == Strategy.NEED_CLARIFICATION
        assert "base_table 为空" in response.plan.downgrade_reason

    def test_fact_not_in_g2_facts_needs_clarification(self, monkeypatch):
        """负例：G2 fact 未在 semantic_contract g2_facts 注册 → NEED_CLARIFICATION"""
        agent = Text2SQLAgent()
        ctx = _build_test_context()
        monkeypatch.setattr(agent, "_context", ctx)

        # base_table 指向一个不在 g2_facts 中的表
        metric = _make_metric(
            "some_metric", "某指标", "traffic",
            "COUNT(*)", "gold.fact_unknown_table", "次",
            g3_available=False, g3_table="",
        )
        self._inject_metrics(agent, [metric])

        response = agent.ask("2026年1月某指标是多少？")

        assert response.clarification_needed is True
        assert response.plan.strategy == Strategy.NEED_CLARIFICATION
        assert "未在 semantic_contract.yml" in response.plan.downgrade_reason

    def test_g3_missing_key_dimensions_still_downgrades(self, monkeypatch):
        """负例：G3 表在 g3_summaries 中无记录 → 降级（不猜字段）"""
        agent = Text2SQLAgent()
        ctx = _build_test_context()
        monkeypatch.setattr(agent, "_context", ctx)

        # g3_table 指向一个不在 g3_summaries 中的表（模拟配置缺失）
        metric = _make_metric(
            "persons_injured", "受伤人数", "safety",
            "SUM(persons_injured)", "gold.fact_crashes", "人",
            g3_available=True,
            g3_table="gold.dws_unknown_summary",  # 不在 g3_summaries 中
        )
        self._inject_metrics(agent, [metric])

        response = agent.ask("2026年3月每个 borough 的受伤人数是多少？")

        # 应降级到 G2（G3 元数据缺失时不猜字段）
        assert response.clarification_needed is False
        assert response.plan.strategy in (Strategy.G2_FACT, Strategy.G2_FACT_JOIN)
        assert response.plan.downgrade_reason is not None

    def test_unsupported_dimension_needs_clarification(self, monkeypatch):
        """负例：不支持的维度 → NEED_CLARIFICATION（不能编造 JOIN）"""
        agent = Text2SQLAgent()
        ctx = _build_test_context()
        monkeypatch.setattr(agent, "_context", ctx)

        metric = _make_metric(
            "persons_injured", "受伤人数", "safety",
            "SUM(persons_injured)", "gold.fact_crashes", "人",
            g3_available=False, g3_table="",  # 强制走 G2
        )
        self._inject_metrics(agent, [metric])

        # "颜色"不在 _DIMENSION_KEYWORDS 中，也不会被 _extract_dimensions_from_question 识别
        # 所以不会触发维度缺失逻辑，但 G2 也走 date 维度
        # 改用已知会触发 NEED_CLARIFICATION 的场景
        response = agent.ask("2026年3月每种车辆类型的受伤人数是多少？")

        # vehicle_type 不在 fact_crashes 的 fact_direct_columns/nor join_keys 中
        assert response.clarification_needed is True
        assert response.plan.strategy == Strategy.NEED_CLARIFICATION
        assert "无法从 G2 事实表" in response.plan.downgrade_reason


# ═══════════════════════════════════════════════════════════════
# Phase 1: 同表多指标测试
# ═══════════════════════════════════════════════════════════════


class TestMultiMetricSameTable:
    """同表多指标：检测 → 策略决策 → 合并校验 → 单 SQL 多 Aggregation"""

    def test_multi_metric_same_table_g3_crash(self):
        """测试 1: 每天受伤人数和死亡人数 → G3_DIRECT，同表 2 aggregations"""
        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天受伤人数和死亡人数是多少？")

        assert not response.clarification_needed
        assert not response.refusal
        # 证据：两个 crash 指标共享 dws_daily_crash_summary
        assert response.plan.strategy == Strategy.G3_DIRECT
        assert response.plan.primary_table == "gold.dws_daily_crash_summary"
        assert len(response.plan.aggregations) == 2
        agg_aliases = [a.alias for a in response.plan.aggregations]
        assert "persons_injured" in agg_aliases
        assert "persons_killed" in agg_aliases
        # G3 全覆盖 → 无降级原因
        assert response.plan.downgrade_reason is None
        # SQL 包含两个聚合表达式
        assert "persons_injured" in response.result.sql
        assert "persons_killed" in response.result.sql

    def test_multi_metric_same_table_g3_trip(self):
        """测试 2: 每天行程数和车费收入 → G3_DIRECT，同表 2 aggregations"""
        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天行程数和车费总额是多少？")

        assert not response.clarification_needed
        assert not response.refusal
        # 证据：两个 trip 指标共享 dws_daily_trip_summary
        assert response.plan.strategy == Strategy.G3_DIRECT
        assert response.plan.primary_table == "gold.dws_daily_trip_summary"
        assert len(response.plan.aggregations) == 2
        agg_aliases = [a.alias for a in response.plan.aggregations]
        assert "trip_count" in agg_aliases
        assert "total_fare_amount" in agg_aliases
        # SQL 包含两个聚合表达式
        assert "trip_count" in response.result.sql
        assert "total_fare_amount" in response.result.sql

    def test_multi_metric_same_table_g2_downgrade(self):
        """测试 3: 每个 borough 的受伤人数和死亡人数 → G2_FACT，带 downgrade_reason"""
        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每个borough的受伤人数和死亡人数是多少？")

        assert not response.clarification_needed
        assert not response.refusal
        # 证据：G3 crash 表不覆盖 borough → 降级 G2
        assert response.plan.strategy in (Strategy.G2_FACT, Strategy.G2_FACT_JOIN)
        # 两个聚合
        assert len(response.plan.aggregations) == 2
        agg_aliases = [a.alias for a in response.plan.aggregations]
        assert "persons_injured" in agg_aliases
        assert "persons_killed" in agg_aliases
        # 降级原因必须存在
        assert response.plan.downgrade_reason is not None
        assert "borough" in response.plan.downgrade_reason.lower()

    def test_multi_metric_cross_table_unsupported(self):
        """测试 4: 每天行程数和受伤人数 → 跨表，返回 clarification"""
        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天行程数和受伤人数分别是多少？")

        # 跨表 → 必须反问，不允许静默只回答一个
        assert response.clarification_needed
        msg = response.clarification_message or ""
        assert "跨表" in msg or "UNSUPPORTED_MULTI_METRIC" in msg
        # 不允许只回答其中一个
        assert response.plan is None or response.plan.strategy == Strategy.NEED_CLARIFICATION
