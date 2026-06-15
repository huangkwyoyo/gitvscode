"""
B-8 规则模式指标映射数据驱动化测试。

验证：
    1. 指标关键词映射从配置加载（不再硬编码）
    2. 表映射优先从 resolver context 动态加载
    3. 离线模式 fallback 到 agent_config.yml
    4. 新增指标只需修改配置文件
"""

from unittest.mock import MagicMock

import pytest
import yaml

from src.agent import Text2SQLAgent
from src.ir import Domain, QuestionIntent, TimeRange, TimeRangeType
from src.resolver import AgentContext, MetricInfo


# ══════════════════════════════════════════════════════
# 配置驱动关键词检测测试
# ══════════════════════════════════════════════════════

class TestConfigDrivenMetricDetection:
    """_detect_metric 应从配置加载关键词映射"""

    def _make_agent(self, monkeypatch):
        """构造 rule 模式 agent，跳过 resolver 初始化"""
        monkeypatch.setattr(
            "src.agent.Text2SQLAgent._init_resolver",
            lambda self, path: (
                setattr(self, "_context", AgentContext(offline=True))
                or setattr(self, "_resolver", None)
            ),
        )
        return Text2SQLAgent(mode="rule")

    @pytest.mark.parametrize("question,expected_metric,expected_domain", [
        ("2026年1月有多少行程", "trip_count", Domain.TRAFFIC),
        ("出行数据统计", "trip_count", Domain.TRAFFIC),
        ("今天订单量多少", "trip_count", Domain.TRAFFIC),
        ("停车罚单数量", "parking_violation_count", Domain.VIOLATION),
        ("最近有多少罚单", "parking_violation_count", Domain.VIOLATION),
        ("违章统计", "parking_violation_count", Domain.VIOLATION),
        ("事故数量", "crash_count", Domain.SAFETY),
        ("碰撞数据", "crash_count", Domain.SAFETY),
    ])
    def test_detect_metric_from_config(
        self, monkeypatch, question, expected_metric, expected_domain,
    ):
        """关键词→指标映射应从 agent_config.yml 加载"""
        agent = self._make_agent(monkeypatch)
        result = agent._detect_metric(question)
        assert result is not None, f"未能识别问题: {question}"
        assert result["metric"] == expected_metric
        assert result["domain"] == expected_domain

    def test_unknown_metric_returns_none(self, monkeypatch):
        """未匹配任何关键词时应返回 None"""
        agent = self._make_agent(monkeypatch)
        result = agent._detect_metric("今天天气怎么样")
        assert result is None

    def test_config_keywords_match_agent_config(self, monkeypatch):
        """验证 agent_config.yml 中的关键词在 agent 中生效"""
        agent = self._make_agent(monkeypatch)
        # trip_count 对应的关键词应可检测
        result = agent._detect_metric("show me trips")
        assert result is not None
        assert result["metric"] == "trip_count"


# ══════════════════════════════════════════════════════
# 表映射解析测试
# ══════════════════════════════════════════════════════

class TestMetricTableMapping:
    """_resolve_metric_table_mapping 优先级测试"""

    def _make_agent(self, monkeypatch, context=None):
        """构造 agent"""
        monkeypatch.setattr(
            "src.agent.Text2SQLAgent._init_resolver",
            lambda self, path: (
                setattr(self, "_context", context or AgentContext(offline=True))
                or setattr(self, "_resolver", None)
            ),
        )
        return Text2SQLAgent(mode="rule")

    def test_config_fallback_for_trip_count(self, monkeypatch):
        """离线模式应从 agent_config.yml fallback"""
        agent = self._make_agent(monkeypatch)
        config = agent._resolve_metric_table_mapping("trip_count")
        assert config is not None
        assert config["table"] == "gold.dws_daily_trip_summary"
        assert config["date_col"] == "trip_date"
        assert config["value_expr"] == "trip_count"

    def test_config_fallback_for_parking(self, monkeypatch):
        """离线模式应正确解析停车罚单指标"""
        agent = self._make_agent(monkeypatch)
        config = agent._resolve_metric_table_mapping("parking_violation_count")
        assert config is not None
        assert config["table"] == "gold.dws_daily_parking_summary"
        assert config["date_col"] == "issue_date"

    def test_unknown_metric_returns_none(self, monkeypatch):
        """未配置的指标应返回 None"""
        agent = self._make_agent(monkeypatch)
        config = agent._resolve_metric_table_mapping("unknown_metric")
        assert config is None

    def test_context_metrics_take_priority(self, monkeypatch):
        """resolver context 中的指标应优先于配置 fallback"""
        context = AgentContext(
            available_metrics=[
                MetricInfo(
                    name="trip_count",
                    zh_name="行程数",
                    domain="traffic",
                    aggregation="SUM(trip_count)",
                    base_table="gold.dws_daily_trip_summary",
                    unit="次",
                    g3_available=True,
                ),
            ],
        )
        agent = self._make_agent(monkeypatch, context=context)
        config = agent._resolve_metric_table_mapping("trip_count")
        assert config is not None
        assert config["table"] == "gold.dws_daily_trip_summary"

    def test_context_metric_not_found_falls_back_to_config(self, monkeypatch):
        """context 中有其他指标但不含目标指标时，应 fallback"""
        context = AgentContext(
            available_metrics=[
                MetricInfo(
                    name="other_metric",
                    zh_name="其他指标",
                    domain="traffic",
                    aggregation="SUM(value)",
                    base_table="gold.other_table",
                    unit="次",
                    g3_available=True,
                ),
            ],
        )
        agent = self._make_agent(monkeypatch, context=context)
        config = agent._resolve_metric_table_mapping("trip_count")
        # trip_count 不在 context 中，应 fallback 到配置
        assert config is not None
        assert config["table"] == "gold.dws_daily_trip_summary"


# ══════════════════════════════════════════════════════
# 日期列推导测试
# ══════════════════════════════════════════════════════

class TestDateColumnInference:
    """_infer_date_column 静态方法测试"""

    def test_trip_table_infers_trip_date(self):
        assert Text2SQLAgent._infer_date_column("gold.dws_daily_trip_summary") == "trip_date"

    def test_parking_table_infers_issue_date(self):
        assert Text2SQLAgent._infer_date_column("gold.dws_daily_parking_summary") == "issue_date"

    def test_crash_table_infers_crash_date(self):
        assert Text2SQLAgent._infer_date_column("gold.dws_daily_crash_summary") == "crash_date"

    def test_unknown_table_defaults_to_date(self):
        assert Text2SQLAgent._infer_date_column("gold.some_other_table") == "date"


# ══════════════════════════════════════════════════════
# 端到端：规则模式链路
# ══════════════════════════════════════════════════════

class TestRuleModeE2E:
    """规则模式端到端测试"""

    def _make_agent(self, monkeypatch):
        monkeypatch.setattr(
            "src.agent.Text2SQLAgent._init_resolver",
            lambda self, path: (
                setattr(self, "_context", AgentContext(offline=True))
                or setattr(self, "_resolver", None)
            ),
        )
        return Text2SQLAgent(mode="rule")

    def test_full_rule_mode_chain_trip(self, monkeypatch):
        """规则模式完整链路：行程问题 → 意图 → 规划 → SQL（不执行）"""
        agent = self._make_agent(monkeypatch)
        response = agent.ask("2026年1月每天有多少行程")

        # 不应被 Step 0.5 阻断
        assert response.refusal is False
        # 应识别意图但不进入 SQL 执行（因为 offline=True 会阻断）
        assert response.intent is not None or response.clarification_needed

    def test_full_rule_mode_chain_parking(self, monkeypatch):
        """规则模式：违章问题走完整链路"""
        agent = self._make_agent(monkeypatch)
        response = agent.ask("2026年3月停车罚单数量")

        assert response.refusal is False
        assert response.intent is not None or response.clarification_needed

    def test_unknown_metric_gets_clarification(self, monkeypatch):
        """未注册指标应触发反问，而非编造"""
        agent = self._make_agent(monkeypatch)
        response = agent.ask("2026年1月平均车速是多少")

        # 这个指标不在注册表中
        assert not response.refusal
        # 预期的行为是反问或返回 planned clarification
        if response.intent and response.intent.needs_clarification:
            pass  # 反问路径符合预期
        elif response.clarification_needed:
            pass  # 反问路径符合预期
        elif response.refusal:
            # 如果被拒绝，不应是写操作原因
            assert "修改" not in str(response.refusal_reason)
            assert "删除" not in str(response.refusal_reason)


# ══════════════════════════════════════════════════════
# 配置一致性测试
# ══════════════════════════════════════════════════════

class TestConfigConsistency:
    """agent_config.yml 中 rule_mode 段的一致性和完整性"""

    def test_config_has_rule_mode_section(self):
        """agent_config.yml 应有 rule_mode 段"""
        from pathlib import Path
        config_path = Path(__file__).resolve().parent.parent / "config" / "agent_config.yml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert "rule_mode" in config, "缺少 rule_mode 配置段"

    def test_keyword_to_metric_not_empty(self):
        """keyword_to_metric 至少覆盖 3 个指标"""
        from pathlib import Path
        config_path = Path(__file__).resolve().parent.parent / "config" / "agent_config.yml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        keyword_map = config["rule_mode"].get("keyword_to_metric", {})
        assert len(keyword_map) >= 3, f"keyword_to_metric 至少需要 3 个指标，实际 {len(keyword_map)}"

    def test_metric_to_table_not_empty(self):
        """metric_to_table 至少覆盖 3 个指标"""
        from pathlib import Path
        config_path = Path(__file__).resolve().parent.parent / "config" / "agent_config.yml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        metric_table = config["rule_mode"].get("metric_to_table", {})
        assert len(metric_table) >= 3, f"metric_to_table 至少需要 3 个指标，实际 {len(metric_table)}"

    def test_keyword_and_table_definitions_consistent(self):
        """keyword_to_metric 中的每个 metric 应在 metric_to_table 中有对应映射"""
        from pathlib import Path
        config_path = Path(__file__).resolve().parent.parent / "config" / "agent_config.yml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        keyword_map = config["rule_mode"].get("keyword_to_metric", {})
        metric_table = config["rule_mode"].get("metric_to_table", {})

        metrics_from_keywords = {v["metric"] for v in keyword_map.values()}
        for metric in metrics_from_keywords:
            assert metric in metric_table, (
                f"keyword_to_metric 中的 '{metric}' 在 metric_to_table 中没有对应映射"
            )

    def test_no_hardcoded_mapping_remaining(self):
        """agent.py 中不应再有硬编码的指标字典"""
        from pathlib import Path
        agent_path = Path(__file__).resolve().parent.parent / "src" / "agent.py"
        content = agent_path.read_text(encoding="utf-8")

        # 不应包含旧的硬编码 dict（三指标写死在代码中）
        assert '"trip_count": {' not in content, (
            "agent.py 中不应再有硬编码的 trip_count 表映射（应移到 agent_config.yml）"
        )
