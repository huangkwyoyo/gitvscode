"""
B-5 回归测试：validate() 与 detect_ambiguity() 职责拆分。

修复前：validate() 同时检查结构 + 歧义（FUZZY 时间、低置信度、反问标记）
修复后：validate() 仅做结构性校验，歧义检测统一由 detect_ambiguity() 处理

验证要点：
    1. validate() 只拦截"domain=None 且 metrics=[]"的结构性错误
    2. validate() 不拦截 FUZZY 时间、低置信度、needs_clarification
    3. detect_ambiguity() 覆盖所有歧义路径
"""
import pytest

from src.ambiguity import detect_ambiguity, ClarificationRule
from src.ir import (
    Domain,
    IntentType,
    QuestionIntent,
    TimeRange,
    TimeRangeType,
)


# ═══════════════════════════════════════════════════════════════
# 第一部分：validate() 仅做结构性校验
# ═══════════════════════════════════════════════════════════════


class TestValidateStructuralOnly:
    """B-5：validate() 只检查 IR 结构完整性（domain + metrics）"""

    def test_clean_intent_passes(self):
        """完整的 domain + metrics → validate() 通过"""
        intent = QuestionIntent(
            domain=Domain.TRAFFIC,
            intent_type=IntentType.AGGREGATION,
            metrics=["trip_count"],
            time_range=TimeRange(
                type=TimeRangeType.ABSOLUTE,
                start="2026-01-01",
                end="2026-03-31",
            ),
            confidence=0.95,
        )
        errors = intent.validate()
        assert errors == [], f"完整意图应通过结构性校验，实际: {errors}"

    def test_no_domain_no_metrics_fails(self):
        """domain=None 且 metrics=[] → validate() 报结构错误"""
        intent = QuestionIntent()
        errors = intent.validate()
        assert len(errors) > 0
        assert any("无法识别查询领域和指标" in e for e in errors)

    def test_no_domain_but_has_metrics_passes(self):
        """有指标但无 domain → validate() 通过（domain 可选）"""
        intent = QuestionIntent(
            metrics=["trip_count"],
            time_range=TimeRange(type=TimeRangeType.ABSOLUTE, start="2026-01-01", end="2026-01-31"),
            confidence=0.8,
        )
        errors = intent.validate()
        assert errors == [], (
            f"有指标时结构应完整，实际: {errors}"
        )

    def test_has_domain_no_metrics_passes(self):
        """有 domain 但无 metrics → validate() 通过（如纯维度查询）"""
        intent = QuestionIntent(
            domain=Domain.SPATIAL,
            dimensions=["zone_name"],
            confidence=0.9,
        )
        errors = intent.validate()
        assert errors == [], (
            f"有 domain 时结构应完整，实际: {errors}"
        )


class TestValidateDoesNotDetectAmbiguity:
    """B-5：validate() 不再检查歧义相关内容"""

    def test_fuzzy_time_passes_validation(self):
        """FUZZY 时间 → validate() 通过（歧义由 detect_ambiguity 处理）"""
        intent = QuestionIntent(
            metrics=["trip_count"],
            time_range=TimeRange(type=TimeRangeType.FUZZY, raw_expression="最近"),
            confidence=0.6,
        )
        errors = intent.validate()
        assert errors == [], (
            f"FUZZY 时间应由 detect_ambiguity 处理，validate() 应返回空，实际: {errors}"
        )

    def test_low_confidence_passes_validation(self):
        """低置信度 → validate() 通过（歧义由 detect_ambiguity 处理）"""
        intent = QuestionIntent(
            domain=Domain.TRAFFIC,
            intent_type=IntentType.AGGREGATION,
            metrics=["trip_count"],
            time_range=TimeRange(
                type=TimeRangeType.ABSOLUTE,
                start="2026-01-01",
                end="2026-03-31",
            ),
            confidence=0.3,  # 远低于阈值
        )
        errors = intent.validate()
        assert errors == [], (
            f"低置信度应由 detect_ambiguity 处理，validate() 应返回空，实际: {errors}"
        )

    def test_needs_clarification_flag_passes_validation(self):
        """needs_clarification=True → validate() 通过（由 agent ask() Step 1.5 处理）"""
        intent = QuestionIntent(
            metrics=["trip_count"],
            needs_clarification=True,
            clarification_reason="时间范围模糊",
            confidence=0.3,
        )
        errors = intent.validate()
        # 有 metrics → 结构完整，validate() 通过
        assert errors == [], (
            f"needs_clarification 应由 ask() Step 1.5 处理，validate() 应返回空，实际: {errors}"
        )

    def test_needs_clarification_no_metrics_no_domain_fails_structural(self):
        """needs_clarification=True 但 domain=None 且 metrics=[] → validate() 报结构错误"""
        intent = QuestionIntent(
            needs_clarification=True,
            clarification_reason="金额口径不明确",
            confidence=1.0,
        )
        errors = intent.validate()
        # 虽然 needs_clarification=True，但结构上 domain=None + metrics=[]
        # validate() 应检测到这个结构问题
        assert len(errors) > 0
        assert any("无法识别查询领域和指标" in e for e in errors)


# ═══════════════════════════════════════════════════════════════
# 第二部分：detect_ambiguity() 覆盖所有歧义路径
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def sample_rules():
    """构造测试用的反问规则"""
    return [
        ClarificationRule(
            trigger="amount_ambiguous",
            description="金额歧义",
            keywords=["金额", "多少钱"],
            clarification_template="金额存在多种口径，请明确要查询哪一种。",
        ),
    ]


class TestDetectAmbiguityCoverage:
    """B-5：detect_ambiguity() 统一覆盖所有歧义检测路径"""

    def test_needs_clarification_flag_triggered(self, sample_rules):
        """intent.needs_clarification=True → 触发反问"""
        intent = QuestionIntent(
            metrics=["trip_count"],
            needs_clarification=True,
            clarification_reason="需要确认时间范围",
            confidence=0.95,
        )
        needs, msg = detect_ambiguity(
            intent, "最近每天多少行程", sample_rules, ambiguity_threshold=0.85,
        )
        assert needs is True
        assert "需要确认时间范围" in msg

    def test_low_confidence_triggers(self, sample_rules):
        """置信度低于阈值 → 触发反问"""
        intent = QuestionIntent(
            domain=Domain.TRAFFIC,
            metrics=["trip_count"],
            time_range=TimeRange(
                type=TimeRangeType.ABSOLUTE,
                start="2026-01-01",
                end="2026-03-31",
            ),
            confidence=0.3,  # < 0.85
        )
        needs, msg = detect_ambiguity(
            intent, "2026年Q1每天多少行程", sample_rules, ambiguity_threshold=0.85,
        )
        assert needs is True
        assert "30%" in msg or "0.3" in msg  # 置信度百分比或小数

    def test_fuzzy_time_triggers(self, sample_rules):
        """FUZZY 时间且有指标 → 触发反问"""
        intent = QuestionIntent(
            metrics=["trip_count"],
            time_range=TimeRange(type=TimeRangeType.FUZZY, raw_expression="最近"),
            confidence=0.9,  # 高于阈值
        )
        needs, msg = detect_ambiguity(
            intent, "最近每天多少行程", sample_rules, ambiguity_threshold=0.85,
        )
        assert needs is True
        assert "时间范围" in msg

    def test_keyword_rule_triggers(self, sample_rules):
        """关键词匹配反问规则 → 触发反问"""
        intent = QuestionIntent(
            domain=Domain.TRAFFIC,
            metrics=["trip_count"],
            time_range=TimeRange(
                type=TimeRangeType.ABSOLUTE,
                start="2026-01-01",
                end="2026-03-31",
            ),
            confidence=0.95,
        )
        needs, msg = detect_ambiguity(
            intent, "2026年Q1每天金额是多少", sample_rules, ambiguity_threshold=0.85,
        )
        assert needs is True
        assert "金额" in msg

    def test_clean_intent_not_ambiguous(self, sample_rules):
        """干净的意图不触发反问"""
        intent = QuestionIntent(
            domain=Domain.TRAFFIC,
            metrics=["trip_count"],
            time_range=TimeRange(
                type=TimeRangeType.ABSOLUTE,
                start="2026-01-01",
                end="2026-03-31",
            ),
            confidence=0.95,
        )
        needs, msg = detect_ambiguity(
            intent, "2026年Q1每天多少行程", sample_rules, ambiguity_threshold=0.85,
        )
        assert needs is False
        assert msg is None

    def test_no_false_positive_on_high_confidence(self, sample_rules):
        """高置信度 + 无歧义关键词 + 明确时间 → 不触发反问"""
        intent = QuestionIntent(
            domain=Domain.TRAFFIC,
            metrics=["trip_count"],
            time_range=TimeRange(
                type=TimeRangeType.ABSOLUTE,
                start="2026-01-01",
                end="2026-01-31",
            ),
            confidence=0.98,
        )
        needs, msg = detect_ambiguity(
            intent, "2026年1月每天有多少行程？", sample_rules, ambiguity_threshold=0.85,
        )
        assert needs is False

    def test_fuzzy_time_no_metrics_no_trigger(self, sample_rules):
        """FUZZY 时间但无指标 → 不触发（无意义反问）"""
        intent = QuestionIntent(
            time_range=TimeRange(type=TimeRangeType.FUZZY, raw_expression="最近"),
            confidence=0.5,
        )
        needs, msg = detect_ambiguity(
            intent, "最近", sample_rules, ambiguity_threshold=0.85,
        )
        # 低置信度会触发（0.5 < 0.85），但不是因为 FUZZY 时间
        assert needs is True
        # 这是因为低置信度触发的
        assert "不够确定" in msg


class TestDetectAmbiguityPriority:
    """B-5：歧义检测的优先级顺序"""

    def test_needs_clarification_has_highest_priority(self, sample_rules):
        """intent.needs_clarification=True 应最先被检测"""
        intent = QuestionIntent(
            domain=Domain.TRAFFIC,
            metrics=["trip_count"],
            needs_clarification=True,
            clarification_reason="需要确认指标口径",
            time_range=TimeRange(
                type=TimeRangeType.ABSOLUTE,
                start="2026-01-01",
                end="2026-03-31",
            ),
            confidence=0.95,  # 高置信度
        )
        needs, msg = detect_ambiguity(
            intent, "2026年Q1每天多少行程", sample_rules, ambiguity_threshold=0.85,
        )
        assert needs is True
        # 应使用 intent 自带的 reason，而非置信度的通用消息
        assert "需要确认指标口径" in msg
        assert "不够确定" not in msg

    def test_confidence_before_fuzzy_time(self, sample_rules):
        """低置信度检测在 FUZZY 时间之前（代码顺序）"""
        intent = QuestionIntent(
            metrics=["trip_count"],
            time_range=TimeRange(type=TimeRangeType.FUZZY, raw_expression="最近"),
            confidence=0.55,  # 低于阈值
        )
        needs, msg = detect_ambiguity(
            intent, "最近多少行程", sample_rules, ambiguity_threshold=0.85,
        )
        assert needs is True
        # 因为置信度检查在 FUZZY 之前，消息应来自置信度分支
        assert "不够确定" in msg


# ═══════════════════════════════════════════════════════════════
# 第三部分：B-5 与 Agent.ask() 集成测试
# ═══════════════════════════════════════════════════════════════


class TestB5AgentIntegration:
    """B-5：Agent.ask() 中 validate() 与 detect_ambiguity() 协同工作"""

    def test_fuzzy_time_goes_through_validate_then_caught_by_ambiguity(self):
        """模糊时间 → validate() 通过 → detect_ambiguity() 捕获"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("最近每天有多少行程？")

        # 应触发反问（由 detect_ambiguity 在 Step 2 捕获）
        assert response.clarification_needed is True
        assert "时间" in (response.clarification_message or "")
        # 不应是结构错误
        assert "无法识别查询领域和指标" not in (response.clarification_message or "")

    def test_ambiguous_amount_has_friendly_clarification(self):
        """金额歧义 → validate() 通过 → intent.needs_clarification 在 Step 1.5 使用友好消息"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天金额是多少？")

        assert response.clarification_needed is True
        # intent 自带友好消息，不是 validate() 的结构错误
        assert "金额" in (response.clarification_message or "")
        assert "无法识别查询领域和指标" not in (response.clarification_message or "")

    def test_clean_question_passes_both_validate_and_ambiguity(self):
        """干净问题 → validate() 通过 → detect_ambiguity() 通过 → 正常回答"""
        from src.agent import Text2SQLAgent

        agent = Text2SQLAgent()
        response = agent.ask("2026年1月每天有多少行程？")

        assert response.clarification_needed is False
        assert response.refusal is False
        assert response.intent is not None
        assert response.plan is not None
        assert response.result is not None
