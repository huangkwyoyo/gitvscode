from src.agent import Text2SQLAgent
from src.ir import Domain, Strategy, TimeRangeType
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
