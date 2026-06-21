"""
C-1 安全回归测试：异常降级路径导致安全校验静默绕过。

验证 C-1 修复的四层防线：
    1. AgentContext.offline 标志正确设置
    2. ir.py 中 available_tables/join_whitelist 的 is not None 判断
    3. sql_gen.py 中 validate_sql_safety 的 is not None 判断
    4. agent.py ask() 中离线模式执行阻断

关键设计原则：
    - None = "未提供白名单，跳过检查"（向后兼容）
    - set() = "白名单为空，拒绝一切"（fail-closed，离线模式的安全默认值）
    - 离线模式下 SQL 执行必须被阻断（防御深度）
"""


from src.ir import (
    SQLPlan,
    Strategy,
    JoinPlan,
)
from src.resolver import AgentContext
from src.sql_gen import validate_sql_safety


# ═══════════════════════════════════════════════════════════
# T1-T5: ir.py SQLPlan.validate() 的 None vs set() 区分
# ═══════════════════════════════════════════════════════════


class TestPlanValidateNoneVsEmptySet:
    """SQLPlan.validate() 中 available_tables/join_whitelist 的语义区分"""

    # ── T1: set() 应该触发检查（fail-closed）──

    def test_available_tables_empty_set_rejects_all_tables(self):
        """T2: available_tables=set() 时，任何表都应被拒绝（空集合不含任何表）"""
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
            confidence=0.95,
        )
        errors = plan.validate(available_tables=set())
        assert len(errors) > 0
        assert any("不在可用表列表中" in e for e in errors)

    def test_join_whitelist_empty_set_rejects_all_joins(self):
        """T4: join_whitelist=set() 时，任何 JOIN 都应被拒绝"""
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
            joins=[JoinPlan(table="gold.dim_date", on="gold.dim_date.date = gold.dws_daily_trip_summary.trip_date")],
            confidence=0.95,
        )
        errors = plan.validate(
            available_tables={"gold.dws_daily_trip_summary", "gold.dim_date"},
            join_whitelist=set(),  # 空白名单 → 拒绝所有 JOIN
        )
        assert len(errors) > 0
        assert any("不在核准白名单中" in e for e in errors)

    def test_available_tables_empty_set_blocks_even_valid_table(self):
        """T2 强化：即使表名真实存在，空白名单也应拒绝"""
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
            confidence=0.95,
        )
        # 空集合 → 任何表都不在白名单中
        errors = plan.validate(available_tables=set())
        assert len(errors) > 0

    # ── T3/T5: None 应该跳过检查（向后兼容）──

    def test_available_tables_none_skips_check(self):
        """T3: available_tables=None 时跳过表存在性检查（未提供白名单）"""
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.nonexistent_table_xyz",
            confidence=0.95,
        )
        # None 表示"无白名单可用"，不应拦截任何表
        errors = plan.validate(available_tables=None)
        # 不应包含表不在白名单的错误（因为根本没检查）
        assert not any("不在可用表列表中" in e for e in errors)

    def test_join_whitelist_none_skips_check(self):
        """T5: join_whitelist=None 时跳过 JOIN 检查（未提供白名单）"""
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.fact_trips",
            joins=[JoinPlan(table="gold.unknown_table", on="id = id")],
            confidence=0.95,
        )
        errors = plan.validate(
            available_tables={"gold.fact_trips", "gold.unknown_table"},
            join_whitelist=None,  # 无白名单 → 跳过检查
        )
        assert not any("不在核准白名单中" in e for e in errors)

    # ── 正常白名单（非空 set）仍正确工作 ──

    def test_available_tables_with_valid_entries_allows_listed_table(self):
        """正常白名单应允许已注册的表通过"""
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
            confidence=0.95,
        )
        errors = plan.validate(
            available_tables={"gold.dws_daily_trip_summary", "gold.dim_date"},
        )
        # 表在白名单中，应通过
        assert not any("不在可用表列表中" in e for e in errors)

    def test_join_whitelist_with_valid_entries_allows_listed_join(self):
        """正常 JOIN 白名单应允许已注册的 JOIN 通过"""
        plan = SQLPlan(
            strategy=Strategy.G3_DIRECT,
            primary_table="gold.dws_daily_trip_summary",
            joins=[JoinPlan(table="gold.dim_date", on="gold.dim_date.date = gold.dws_daily_trip_summary.trip_date")],
            confidence=0.95,
        )
        errors = plan.validate(
            available_tables={"gold.dws_daily_trip_summary", "gold.dim_date"},
            join_whitelist={("gold.dws_daily_trip_summary", "gold.dim_date")},
        )
        assert not any("不在核准白名单中" in e for e in errors)


# ═══════════════════════════════════════════════════════════
# T6-T10: sql_gen.py validate_sql_safety() 的 None vs set() 区分
# ═══════════════════════════════════════════════════════════


class TestSQLSafetyNoneVsEmptySet:
    """validate_sql_safety() 中 available_tables/join_whitelist 的语义区分"""

    # ── T8: set() 触发检查（fail-closed）──

    def test_available_tables_empty_set_rejects_all_tables(self):
        """T8: available_tables=set() 时，所有表引用都应被拒绝"""
        sql = "SELECT * FROM gold.dws_daily_trip_summary"
        violations = validate_sql_safety(
            sql,
            forbidden_keywords=["INSERT", "UPDATE", "DELETE"],
            available_tables=set(),  # 空白名单 → 拒绝一切
        )
        assert len(violations) > 0
        assert any("不在可用表白名单中" in v for v in violations)

    def test_join_whitelist_empty_set_rejects_all_joins(self):
        """T10: join_whitelist=set() 时，任何 JOIN 都应被拒绝"""
        sql = (
            "SELECT * FROM gold.fact_trips "
            "INNER JOIN gold.dim_date ON gold.fact_trips.pickup_date_key = gold.dim_date.date_key"
        )
        violations = validate_sql_safety(
            sql,
            forbidden_keywords=["INSERT", "UPDATE", "DELETE"],
            available_tables={"gold.fact_trips", "gold.dim_date"},
            join_whitelist=set(),  # 空白名单 → 拒绝一切 JOIN
        )
        assert len(violations) > 0
        assert any("不在核准白名单中" in v for v in violations)

    def test_empty_keyword_list_still_runs_check(self):
        """即使 forbidden_keywords 为空，表/JOIN 白名单检查仍应生效"""
        sql = "SELECT * FROM gold.fact_trips INNER JOIN gold.dim_date ON id = id"
        violations = validate_sql_safety(
            sql,
            forbidden_keywords=[],  # 空关键字列表
            available_tables=set(),  # 空表白名单 → 拒绝
        )
        # 表白名单检查应生效（fail-closed）
        table_violations = [v for v in violations if "不在可用表白名单中" in v]
        assert len(table_violations) > 0

    # ── T9/T11: None 跳过检查（向后兼容）──

    def test_available_tables_none_skips_table_whitelist(self):
        """T9: available_tables=None 时跳过表白名单检查"""
        sql = "SELECT * FROM gold.nonexistent_table"
        violations = validate_sql_safety(
            sql,
            forbidden_keywords=["INSERT"],
            available_tables=None,  # 无白名单 → 跳过
        )
        # 不应包含表白名单相关违规
        assert not any("不在可用表白名单中" in v for v in violations)

    def test_join_whitelist_none_skips_join_check(self):
        """T11: join_whitelist=None 时跳过 JOIN 白名单检查"""
        sql = (
            "SELECT * FROM gold.fact_trips "
            "INNER JOIN gold.unknown_table ON id = id"
        )
        violations = validate_sql_safety(
            sql,
            forbidden_keywords=["INSERT"],
            available_tables={"gold.fact_trips", "gold.unknown_table"},
            join_whitelist=None,  # 无 JOIN 白名单 → 跳过
        )
        assert not any("不在核准白名单中" in v for v in violations)

    # ── 正常情况 ──

    def test_valid_table_in_whitelist_passes(self):
        """表在白名单中应通过检查"""
        sql = "SELECT trip_count FROM gold.dws_daily_trip_summary"
        violations = validate_sql_safety(
            sql,
            forbidden_keywords=["INSERT", "UPDATE", "DELETE"],
            available_tables={"gold.dws_daily_trip_summary"},
        )
        assert len(violations) == 0

    def test_forbidden_keyword_still_detected_with_empty_available_tables(self):
        """即使 available_tables=set()，禁止关键字检查仍应生效"""
        sql = "DELETE FROM gold.fact_trips"
        violations = validate_sql_safety(
            sql,
            forbidden_keywords=["DELETE"],
            available_tables=set(),
        )
        # 应检测到 DELETE 关键字
        assert any("DELETE" in v for v in violations)


# ═══════════════════════════════════════════════════════════
# T6-T7, T12: Agent 级别的离线模式阻断
# ═══════════════════════════════════════════════════════════


class TestAgentOfflineBlocking:
    """Agent ask() 离线模式下的执行阻断和端到端行为"""

    def test_offline_agent_refuses_sql_execution(self):
        """T6: 离线模式下 Agent 必须阻断 SQL 执行"""
        from src.agent import Text2SQLAgent

        # 使用不存在的配置路径强制进入离线模式
        agent = Text2SQLAgent(
            tianshu_config_path="config/nonexistent_target.yml",
        )
        # 确认进入离线模式
        assert agent._context is not None
        assert agent._context.offline is True
        assert agent._resolver is None

        # 离线模式下 ask 应正确处理（不崩溃，且不执行 SQL）
        response = agent.ask("2026年1月每天有多少行程？")
        # C-1 修复后，plan 校验阶段（Step 3.5）就因空白名单而拦截，
        # 不会到达 Step 5（SQL 执行），因此 result 为 None 是正确的
        assert response.refusal or response.clarification_needed, (
            f"离线模式应阻断回答，实际: refusal={response.refusal}, "
            f"clarification={response.clarification_needed}"
        )
        # 确认阻断原因是安全校验（表不在可用列表中）
        if response.refusal:
            assert "校验失败" in (response.refusal_reason or "")
        # result 为 None 表示 SQL 未被生成或执行（安全行为）
        assert response.result is None, (
            "离线模式下 SQL 不应被执行，result 应为 None"
        )

    def test_offline_context_blocks_execution_even_with_rule_based_path(self):
        """T12: 完整离线模式端到端流程——安全校验必须生效"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent(
            tianshu_config_path="config/nonexistent_target.yml",
        )
        assert agent._context.offline is True

        response = agent.ask("2026年1月每天有多少行程？")

        # 核心断言：不应产生正常执行结果（row_count > 0 且无错误）
        if response.result and not response.result.error:
            # 如果结果无错误，说明 SQL 被执行了——这是安全漏洞
            assert response.result.row_count == 0, (
                "离线模式下不应执行 SQL 并返回数据"
            )

        # 验证 trace 中包含阻断信息
        trace_text = " ".join(response.trace)
        is_blocked = (
            "BLOCKED" in trace_text
            or "离线" in trace_text
            or response.refusal
            or response.clarification_needed
        )
        assert is_blocked, (
            f"离线模式应被阻断，trace: {response.trace}"
        )

    def test_offline_agent_context_has_empty_lists_not_none(self):
        """T1: 验证离线 AgentContext 的字段为 [] 而非 None（保留数据结构）"""
        ctx = AgentContext(offline=True)
        assert ctx.offline is True
        # 字段默认为空列表（非 None），但 offline 标志区分了含义
        assert ctx.available_tables == []
        assert ctx.forbidden_sql_keywords == []
        assert ctx.join_whitelist == []
        # 空列表转为 set() 后是 falsy，配合 is not None 检查实现 fail-closed

    def test_resolver_is_none_after_failed_init(self):
        """T7: 初始化失败后 self._resolver 必须为 None，防止部分初始化绕过"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent(
            tianshu_config_path="config/nonexistent_target.yml",
        )
        # C-1 修复关键点：_init_resolver 异常时 self._resolver 必须置为 None
        assert agent._resolver is None, (
            "Resolver 初始化失败后 _resolver 必须为 None，"
            "防止部分初始化的连接被用于执行未校验 SQL"
        )

    def test_normal_agent_still_works_with_valid_config(self):
        """健全性检查：正常配置的 Agent 应仍能工作（非离线模式）"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        # 如果配置有效且数据库存在，应不在离线模式
        if agent._context and not agent._context.offline:
            response = agent.ask("2026年1月每天有多少行程？")
            assert response is not None
            # 正常模式下的响应应包含结果
            assert response.result is not None
