"""
B-6 写操作检测统一 Step 0.5 测试。

验证 request_guard 模块的中英文全覆盖检测能力，
以及 Agent 层的 refusal 行为。
"""

import pytest

from src.request_guard import is_write_request, is_forbidden_layer_request
from src.agent import Text2SQLAgent


# ══════════════════════════════════════════════════════
# 写操作检测：中文覆盖
# ══════════════════════════════════════════════════════

_CHINESE_WRITE_CASES = [
    ("删除所有数据", True),
    ("删掉这条记录", True),
    ("清空表格内容", True),
    ("移除违规记录", True),
    ("去掉无效数据", True),
    ("更新行程状态", True),
    ("修改数据字段", True),
    ("改成新值", True),
    ("改为手动输入", True),
    ("变更数据源", True),
    ("插入一条记录", True),
    ("写入新数据", True),
    ("新增一行", True),
    ("添加指标", True),
    ("追加数据", True),
    ("覆盖已有数据", True),
    ("替换表中内容", True),
    ("改掉错误字段", True),
    ("建表", True),
    ("创建表结构", True),
    ("删表", True),
    ("drop表", True),
    ("导入外部数据", True),
    ("导出结果", True),
    ("加载数据到表中", True),
]

_CHINESE_NON_WRITE_CASES = [
    ("2026年1月有多少行程", False),
    ("曼哈顿停车罚单数量", False),
    ("查询事故统计", False),
    ("显示每天的收入趋势", False),
    ("帮我看看数据", False),
]


class TestWriteDetectionChinese:
    """写操作检测：中文关键词全覆盖"""

    @pytest.mark.parametrize("question,expected", _CHINESE_WRITE_CASES)
    def test_detects_write_request(self, question, expected):
        """验证中英文写操作关键词能否被正确识别"""
        assert is_write_request(question) == expected

    @pytest.mark.parametrize("question,expected", _CHINESE_NON_WRITE_CASES)
    def test_normal_questions_not_detected(self, question, expected):
        """普通查询不应被误判为写操作"""
        assert is_write_request(question) == expected


# ══════════════════════════════════════════════════════
# 写操作检测：英文覆盖
# ══════════════════════════════════════════════════════

_ENGLISH_WRITE_CASES = [
    ("delete all rows", True),
    ("DROP TABLE gold.dws_trip", True),
    ("truncate the table", True),
    ("UPDATE gold.fact SET col=1", True),
    ("INSERT INTO gold VALUES (1)", True),
    ("MERGE INTO target", True),
    ("REPLACE data in table", True),
    ("ALTER TABLE gold ADD COLUMN", True),
    ("create table new_one", True),
    ("create index on trip_date", True),
    ("GRANT SELECT TO user", True),
    ("revoke privileges", True),
]

_ENGLISH_NON_WRITE_CASES = [
    ("show me trip counts for january", False),
    ("what is the average fare", False),
    ("select count of violations", False),
]


class TestWriteDetectionEnglish:
    """写操作检测：英文关键词全覆盖"""

    @pytest.mark.parametrize("question,expected", _ENGLISH_WRITE_CASES)
    def test_detects_english_write_request(self, question, expected):
        assert is_write_request(question) == expected

    @pytest.mark.parametrize("question,expected", _ENGLISH_NON_WRITE_CASES)
    def test_normal_english_not_detected(self, question, expected):
        assert is_write_request(question) == expected


# ══════════════════════════════════════════════════════
# 禁用层检测
# ══════════════════════════════════════════════════════

_FORBIDDEN_LAYER_CASES = [
    ("查询 bronze 层数据", True),
    ("直接查 silver", True),
    ("select from bronze.table", True),
    ("silver.fact 数据", True),
    ("查看原始表数据", True),
    ("读取原始数据", True),
    ("bronze层的数据", True),
    ("silver层查询", True),
    ("从 ods 加载", True),
    ("staging 表", True),
]

_NORMAL_LAYER_CASES = [
    ("查询 gold 层数据", False),
    ("2026年行程统计", False),
]


class TestForbiddenLayerDetection:
    """禁用层检测"""

    @pytest.mark.parametrize("question,expected", _FORBIDDEN_LAYER_CASES)
    def test_detects_forbidden_layer(self, question, expected):
        assert is_forbidden_layer_request(question) == expected

    @pytest.mark.parametrize("question,expected", _NORMAL_LAYER_CASES)
    def test_normal_layers_not_blocked(self, question, expected):
        assert is_forbidden_layer_request(question) == expected


# ══════════════════════════════════════════════════════
# Agent 层集成测试：refusal 行为
# ══════════════════════════════════════════════════════

_REFUSAL_WRITE_CASES = [
    "删除所有行程数据",
    "DELETE FROM gold.fact_trips",
    "更新违章记录",
    "DROP TABLE gold.dws_daily_trip_summary",
    "插入新指标到 meta 表",
]

_REFUSAL_LAYER_CASES = [
    "直接查 bronze 层 trip 数据",
    "select from silver.fact_payments",
    "用原始表的数据做分析",
]


class TestAgentStep05Refusal:
    """
    Agent 层集成测试：验证 Step 0.5 的 refusal 行为。

    使用 rule 模式 + mock resolver 避免需要真实的 TianShu 连接。
    """

    @pytest.mark.parametrize("question", _REFUSAL_WRITE_CASES)
    def test_write_request_triggers_refusal(self, monkeypatch, question):
        """写操作请求应触发 refusal，不进入后续步骤"""
        # 模拟 resolver 初始化（不真的连接数据库）
        monkeypatch.setattr(
            "src.agent.Text2SQLAgent._init_resolver",
            lambda self, path: setattr(self, "_context", None) or setattr(self, "_resolver", None),
        )
        agent = Text2SQLAgent(mode="rule")
        agent._context = None
        response = agent.ask(question)

        assert response.refusal is True
        assert response.refusal_reason is not None
        # 写操作不应进入意图分类
        assert response.intent is None

    @pytest.mark.parametrize("question", _REFUSAL_LAYER_CASES)
    def test_forbidden_layer_triggers_refusal(self, monkeypatch, question):
        """禁用层请求应触发 refusal"""
        monkeypatch.setattr(
            "src.agent.Text2SQLAgent._init_resolver",
            lambda self, path: setattr(self, "_context", None) or setattr(self, "_resolver", None),
        )
        agent = Text2SQLAgent(mode="rule")
        agent._context = None
        response = agent.ask(question)

        assert response.refusal is True
        assert "Bronze/Silver" in response.refusal_reason
        assert response.intent is None

    def test_normal_question_passes_step05(self, monkeypatch):
        """普通查询应通过 Step 0.5，进入后续步骤"""
        from src.resolver import AgentContext

        context = AgentContext(
            available_tables=[],
            available_metrics=[],
        )

        monkeypatch.setattr(
            "src.agent.Text2SQLAgent._init_resolver",
            lambda self, path: (
                setattr(self, "_context", context) or setattr(self, "_resolver", None)
            ),
        )
        agent = Text2SQLAgent(mode="rule")
        response = agent.ask("2026年1月每天多少行程")

        # 不应被 Step 0.5 拦截为 refusal
        assert response.refusal is False
        # 规则版应进入后续链路（可能是 clarification 而非 refusal）
        # 验证没有触发写操作/禁用层的 refusal
        if response.refusal:
            assert "修改" not in response.refusal_reason
            assert "删除" not in response.refusal_reason
            assert "Bronze" not in response.refusal_reason
