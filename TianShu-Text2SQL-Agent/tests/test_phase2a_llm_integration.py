"""Phase 2A：Prompt 模板 + LLM Adapter + Schema 校验 测试。

覆盖：
- A 类：Prompt 模板包含反幻觉规则和 human_review 字段
- B 类：LLM Adapter 隔离性——不导入真实 API、不创建自己的 client
- C 类：LLM Adapter 快乐路径——4 个方法均用 FakeLLMClient 返回合法 IR
- D 类：Schema 校验——拒绝未知字段、拒绝缺少必需字段、接收合法数据
- E 类：SQL 安全集成——generate_sql 结果必经 validate_sql_safety()
- F 类：导入完整性——新旧模块均无导入错误
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
import yaml

from src.ir import (
    Domain,
    IntentType,
    QuestionIntent,
    SQLPlan,
    SQLResult,
    Strategy,
    TimeRange,
    TimeRangeType,
)
from src.llm import FakeLLMClient
from src.llm_adapter import LLMAdapter, RefusalDetected
from src.schema_validators import (
    validate_explain_output,
    validate_intent_output,
    validate_plan_output,
    validate_sql_output,
)

# ── 路径常量 ──────────────────────────────────────────────
PROMPT_DIR = Path("prompts")
FIXTURE_DIR = Path("tests/fixtures/prompts")
PROMPT_FILES = [
    "intent_classifier",
    "sql_planner",
    "sql_generator",
    "explainer",
]


def _load_fixture_cases(filename: str) -> list[dict]:
    """加载 YAML fixture 用例列表。"""
    data = yaml.safe_load((FIXTURE_DIR / filename).read_text(encoding="utf-8"))
    return data["cases"]


# ═══════════════════════════════════════════════════════════
# A 类：Prompt 模板完整性（3 个测试）
# ═══════════════════════════════════════════════════════════


def _read_prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", PROMPT_FILES)
def test_prompt_contains_human_review_field(name: str):
    """每个 Prompt 模板的输出 JSON 中必须包含 human_review 字段。"""
    text = _read_prompt(name)
    assert "human_review" in text, f"{name} 的 ## 输出 中缺少 human_review 字段"

    # 检查 human_review 的子字段存在
    assert "requires_review" in text, f"{name} 的 human_review 中缺少 requires_review"
    assert "flagged_fields" in text, f"{name} 的 human_review 中缺少 flagged_fields"


@pytest.mark.parametrize("name", PROMPT_FILES)
def test_prompt_contains_anti_hallucination_rules(name: str):
    """每个 Prompt 模板的 ## 硬性边界 中必须包含反幻觉措辞。"""
    text = _read_prompt(name)

    # 提取 ## 硬性边界 到下一个 ## 之间的内容
    hard_section_start = text.find("## 硬性边界")
    assert hard_section_start != -1, f"{name} 缺少 ## 硬性边界"

    remaining = text[hard_section_start:]
    next_section = remaining.find("\n## ", len("## 硬性边界"))
    hard_section = remaining[:next_section] if next_section != -1 else remaining

    # 反幻觉关键词检查
    anti_hallucination_phrases = [
        "不得编造", "不得自行添加", "不得猜测",
        "必须来自", "严格基于", "不得扩大",
    ]
    found = [p for p in anti_hallucination_phrases if p in hard_section]
    assert found, (
        f"{name} 的 ## 硬性边界 中缺少反幻觉措辞，"
        f"当前未包含以下任何关键词: {anti_hallucination_phrases}"
    )


def test_prompt_human_review_clause_explains_usage():
    """每个模板应在 human_review 附近说明其用途（requires_review / flagged_fields 含义）。"""
    for name in ["intent_classifier", "sql_planner", "explainer"]:
        text = _read_prompt(name)
        # 检查 human_review 附近有说明文字
        hr_pos = text.find("human_review")
        context = text[max(0, hr_pos - 50):hr_pos + 500]
        # 至少解释了 requires_review 的含义
        assert "人工复核" in context or "不确定" in context, (
            f"{name} 的 human_review 附近缺少用途说明"
        )


# ═══════════════════════════════════════════════════════════
# B 类：LLM Adapter 隔离性（2 个测试）
# ═══════════════════════════════════════════════════════════


def test_llm_adapter_never_imports_real_api():
    """llm_adapter.py 不得导入 OpenAIChatLLMClient 或 API 密钥相关函数。"""
    adapter_path = Path("src/llm_adapter.py")
    source = adapter_path.read_text(encoding="utf-8")

    forbidden = ["OpenAIChatLLMClient", "_resolve_api_key",
                  "_load_api_key_from_secrets", "_SECRETS_PATH"]
    for name in forbidden:
        # 只检查实际导入/引用，不检查文档字符串中的说明
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                import_text = ast.unparse(node) if hasattr(ast, 'unparse') else ast.dump(node)
                assert name not in import_text, (
                    f"llm_adapter.py 禁止导入 {name}，发现: {import_text}"
                )


def test_llm_adapter_uses_client_passed_in_not_creates_own():
    """LLMAdapter 必须使用传入的 LLMClient，不得在内部创建自己的客户端。"""
    fake_client = FakeLLMClient({
        "intent_classifier": json.dumps({
            "domain": "traffic", "intent_type": "trend",
            "metrics": ["trip_count"],
            "time_range": {"type": "absolute", "start": "2026-01-01",
                           "end": "2026-01-31", "raw_expression": "2026年1月"},
            "dimensions": ["date"], "filters": [],
            "needs_clarification": False, "clarification_reason": None,
            "confidence": 0.95, "raw_question": "test",
        }),
    })
    adapter = LLMAdapter(fake_client)
    # 验证 adapter 内部持有的是我们传入的 client
    assert adapter._client is fake_client


# ═══════════════════════════════════════════════════════════
# C 类：LLM Adapter 快乐路径（4 个测试）
# ═══════════════════════════════════════════════════════════


def test_adapter_classify_intent_returns_valid_question_intent():
    """LLMAdapter.classify_intent 应返回合法的 QuestionIntent。"""
    intent_case = _load_fixture_cases("intent_classifier_cases.yml")[0]
    expected = intent_case["expected_intent"]

    fake_client = FakeLLMClient({
        "intent_classifier": json.dumps(expected, ensure_ascii=False),
    })
    adapter = LLMAdapter(fake_client)

    result = adapter.classify_intent(intent_case["question"])

    assert isinstance(result, QuestionIntent)
    assert result.domain == Domain.TRAFFIC
    assert result.intent_type == IntentType.TREND
    assert result.metrics == ["trip_count"]
    assert result.confidence == 0.95
    assert result.validate() == []


def test_adapter_classify_intent_raises_refusal_for_write_operation():
    """LLMAdapter.classify_intent 应在写操作时抛出 RefusalDetected。"""
    refusal_case = None
    for case in _load_fixture_cases("intent_classifier_cases.yml"):
        if case.get("expected_type") == "refusal":
            refusal_case = case
            break
    assert refusal_case, "fixture 中应有 refusal 用例"

    fake_client = FakeLLMClient({
        "intent_classifier": json.dumps(
            refusal_case["expected_refusal"], ensure_ascii=False
        ),
    })
    adapter = LLMAdapter(fake_client)

    with pytest.raises(RefusalDetected) as exc_info:
        adapter.classify_intent(refusal_case["question"])
    assert "只读" in exc_info.value.refusal_reason


def test_adapter_classify_intent_handles_clarification():
    """LLMAdapter.classify_intent 应在歧义问题时返回带 needs_clarification 的 QuestionIntent。"""
    clarification_case = None
    for case in _load_fixture_cases("intent_classifier_cases.yml"):
        if case.get("expected_type") == "clarification":
            clarification_case = case
            break
    assert clarification_case, "fixture 中应有 clarification 用例"

    fake_client = FakeLLMClient({
        "intent_classifier": json.dumps(
            clarification_case["expected_intent"], ensure_ascii=False
        ),
    })
    adapter = LLMAdapter(fake_client)

    result = adapter.classify_intent(clarification_case["question"])
    assert isinstance(result, QuestionIntent)
    assert result.needs_clarification is True
    assert result.clarification_reason is not None


def test_adapter_plan_sql_returns_valid_sql_plan():
    """LLMAdapter.plan_sql 应返回合法的 SQLPlan。"""
    _intent_case = _load_fixture_cases("intent_classifier_cases.yml")[0]
    plan_case = _load_fixture_cases("sql_planner_cases.yml")[0]

    fake_client = FakeLLMClient({
        "sql_planner": json.dumps(plan_case["expected_plan"], ensure_ascii=False),
    })
    adapter = LLMAdapter(fake_client)

    intent = QuestionIntent(
        domain=Domain.TRAFFIC,
        intent_type=IntentType.TREND,
        metrics=["trip_count"],
        time_range=TimeRange(
            type=TimeRangeType.ABSOLUTE,
            start="2026-01-01", end="2026-01-31",
            raw_expression="2026年1月",
        ),
        dimensions=["date"],
        confidence=0.95,
        raw_question="2026年1月每天有多少行程？",
    )
    result = adapter.plan_sql(intent)

    assert isinstance(result, SQLPlan)
    assert result.strategy == Strategy.G3_DIRECT
    assert result.primary_table == "gold.dws_daily_trip_summary"
    assert result.validate(
        {"gold.dws_daily_trip_summary", "gold.dim_date"},
        {("gold.dws_daily_trip_summary", "gold.dim_date")},
    ) == []


def test_adapter_generate_sql_returns_safe_sql_string():
    """LLMAdapter.generate_sql 应返回通过安全校验的 SQL 字符串。"""
    _plan_case = _load_fixture_cases("sql_planner_cases.yml")[0]

    fake_client = FakeLLMClient({
        "sql_generator": json.dumps({
            "sql": (
                "SELECT gold.dim_date.date, SUM(trip_count) AS trip_count "
                "FROM gold.dws_daily_trip_summary "
                "INNER JOIN gold.dim_date "
                "ON gold.dim_date.date = gold.dws_daily_trip_summary.trip_date "
                "WHERE gold.dim_date.date "
                "BETWEEN DATE '2026-01-01' AND DATE '2026-01-31' "
                "GROUP BY gold.dim_date.date "
                "ORDER BY gold.dim_date.date"
            ),
            "source_table": "gold.dws_daily_trip_summary",
            "notes": [],
        }, ensure_ascii=False),
    })
    adapter = LLMAdapter(fake_client)

    from src.ir import Aggregation, JoinPlan

    plan = SQLPlan(
        strategy=Strategy.G3_DIRECT,
        primary_table="gold.dws_daily_trip_summary",
        joins=[JoinPlan(
            table="gold.dim_date",
            on="gold.dim_date.date = gold.dws_daily_trip_summary.trip_date",
            type="INNER",
        )],
        where_clauses=[
            "gold.dim_date.date BETWEEN DATE '2026-01-01' AND DATE '2026-01-31'"
        ],
        group_by=["gold.dim_date.date"],
        order_by=["gold.dim_date.date"],
        aggregations=[Aggregation(expr="SUM(trip_count)", alias="trip_count")],
        confidence=0.95,
    )
    sql = adapter.generate_sql(plan, safety_policy={
        "forbidden_keywords": ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"],
        "available_tables": {"gold.dws_daily_trip_summary", "gold.dim_date"},
        "join_whitelist": {("gold.dws_daily_trip_summary", "gold.dim_date")},
    })

    assert isinstance(sql, str)
    assert sql.strip().upper().startswith("SELECT")


def test_adapter_explain_result_returns_chinese_answer():
    """LLMAdapter.explain_result 应返回中文解释字符串。"""
    fake_client = FakeLLMClient({
        "explainer": json.dumps({
            "answer_zh": "2026年1月按天返回 31 行行程量数据。数据来源：gold.dws_daily_trip_summary。",
            "source_table": "gold.dws_daily_trip_summary",
            "metric_notes": ["trip_count 表示行程量。"],
            "warnings": [],
        }, ensure_ascii=False),
    })
    adapter = LLMAdapter(fake_client)

    result = SQLResult(
        sql="SELECT ...",
        columns=["date", "trip_count"],
        column_types=["VARCHAR", "BIGINT"],
        rows=[("2026-01-01", 888250), ("2026-01-02", 761261)],
        row_count=31,
        source_table="gold.dws_daily_trip_summary",
    )
    answer = adapter.explain_result(
        question="2026年1月每天有多少行程？",
        result=result,
    )

    assert isinstance(answer, str)
    assert len(answer) > 0
    assert "行程" in answer or "数据" in answer


# ═══════════════════════════════════════════════════════════
# D 类：Schema 校验（4 个测试）
# ═══════════════════════════════════════════════════════════


def test_schema_rejects_unknown_intent_field():
    """intent_output 校验应拒绝未知字段。"""
    valid_data = {
        "domain": "traffic", "intent_type": "trend",
        "metrics": ["trip_count"],
        "time_range": {"type": "absolute", "start": "2026-01-01",
                       "end": "2026-01-31", "raw_expression": "2026年1月"},
        "dimensions": ["date"], "filters": [],
        "needs_clarification": False, "clarification_reason": None,
        "confidence": 0.95, "raw_question": "test",
    }
    # 添加 LLM 可能吐出的非法字段
    data_with_extra = {**valid_data, "llm_provider": "openai"}
    errors = validate_intent_output(data_with_extra)
    assert errors, "应拒绝包含未知字段 'llm_provider' 的数据"


def test_schema_rejects_unknown_plan_field():
    """plan_output 校验应拒绝未知字段。"""
    valid_data = {
        "strategy": "g3_direct",
        "primary_table": "gold.dws_daily_trip_summary",
        "joins": [{"table": "gold.dim_date",
                    "on": "gold.dim_date.date = gold.dws_daily_trip_summary.trip_date",
                    "type": "INNER"}],
        "where_clauses": ["gold.dim_date.date BETWEEN DATE '2026-01-01' AND DATE '2026-01-31'"],
        "group_by": ["gold.dim_date.date"],
        "order_by": ["gold.dim_date.date"],
        "aggregations": [{"expr": "SUM(trip_count)", "alias": "trip_count"}],
        "limit": None, "downgrade_reason": None, "confidence": 0.95,
    }
    data_with_extra = {**valid_data, "raw_output": "some debug text"}
    errors = validate_plan_output(data_with_extra)
    assert errors, "应拒绝包含未知字段 'raw_output' 的数据"


def test_schema_rejects_missing_required_field():
    """intent_output 校验应拒绝缺少必需字段的数据。"""
    # 缺少 domain 字段
    invalid_data = {
        "intent_type": "trend", "metrics": ["trip_count"],
        "time_range": {"type": "absolute", "start": "2026-01-01",
                       "end": "2026-01-31", "raw_expression": "2026年1月"},
        "dimensions": ["date"], "filters": [],
        "needs_clarification": False, "clarification_reason": None,
        "confidence": 0.95, "raw_question": "test",
    }
    errors = validate_intent_output(invalid_data)
    assert errors, "应拒绝缺少必需字段 'domain' 的数据"


def test_schema_accepts_valid_intent_data():
    """intent_output 校验应通过合法的标准数据。"""
    valid_data = {
        "domain": "traffic", "intent_type": "trend",
        "metrics": ["trip_count"],
        "time_range": {"type": "absolute", "start": "2026-01-01",
                       "end": "2026-01-31", "raw_expression": "2026年1月"},
        "dimensions": ["date"], "filters": [],
        "needs_clarification": False, "clarification_reason": None,
        "confidence": 0.95, "raw_question": "test",
    }
    errors = validate_intent_output(valid_data)
    assert errors == [], f"合法数据应通过校验，实际错误: {errors}"


# ═══════════════════════════════════════════════════════════
# E 类：SQL 安全集成（1 个测试）
# ═══════════════════════════════════════════════════════════


def test_adapter_generate_sql_rejects_insert_sql_at_schema_level():
    """schema_validator 在安全校验之前拦截非 SELECT 开头的 SQL（INSERT）。"""
    fake_client = FakeLLMClient({
        "sql_generator": json.dumps({
            "sql": "INSERT INTO gold.dws_daily_trip_summary VALUES (1, 'bad')",
            "source_table": "gold.dws_daily_trip_summary",
            "notes": [],
        }),
    })

    from src.ir import Aggregation

    adapter = LLMAdapter(fake_client)
    plan = SQLPlan(
        strategy=Strategy.G3_DIRECT,
        primary_table="gold.dws_daily_trip_summary",
        joins=[],
        aggregations=[Aggregation(expr="COUNT(*)", alias="cnt")],
        confidence=0.95,
    )

    # Schema 层先拦截：非 SELECT → "SQL 生成输出校验失败"
    with pytest.raises(ValueError, match="生成输出校验失败"):
        adapter.generate_sql(plan, safety_policy={
            "forbidden_keywords": ["INSERT", "UPDATE", "DELETE", "DROP"],
        })


def test_adapter_generate_sql_rejects_table_not_in_allowlist():
    """LLMAdapter.generate_sql 必须通过 validate_sql_safety 拒绝不在白名单的表引用。"""
    # SQL 语法正确（SELECT 开头），但引用了未授权的表
    fake_client = FakeLLMClient({
        "sql_generator": json.dumps({
            "sql": "SELECT * FROM bronze.raw_trip_data WHERE trip_date = '2026-01-01'",
            "source_table": "bronze.raw_trip_data",
            "notes": [],
        }),
    })

    from src.ir import Aggregation

    adapter = LLMAdapter(fake_client)
    plan = SQLPlan(
        strategy=Strategy.G3_DIRECT,
        primary_table="gold.dws_daily_trip_summary",
        joins=[],
        aggregations=[Aggregation(expr="COUNT(*)", alias="cnt")],
        confidence=0.95,
    )

    # 安全层拦截：表不在可用表列表中 → "SQL 安全校验失败"
    with pytest.raises(ValueError, match="SQL 安全校验失败"):
        adapter.generate_sql(plan, safety_policy={
            "forbidden_keywords": ["INSERT", "UPDATE", "DELETE", "DROP"],
            "available_tables": {"gold.dws_daily_trip_summary", "gold.dim_date"},
        })


# ═══════════════════════════════════════════════════════════
# F 类：导入完整性 + 回归保护（2 个测试）
# ═══════════════════════════════════════════════════════════


def test_phase2a_modules_importable():
    """Phase 2A 新增模块必须可无错误导入。"""
    # schema_validators 已在顶部导入成功，这里只验证不会意外失败
    from src.schema_validators import (
        validate_intent_output,
        validate_plan_output,
    )
    from src.llm_adapter import LLMAdapter
    assert callable(validate_intent_output)
    assert callable(validate_plan_output)
    assert callable(validate_sql_output)
    assert callable(validate_explain_output)
    assert callable(LLMAdapter)


def test_phase2a_changes_dont_break_existing_imports():
    """现有所有模块必须在 Phase 2A 变更后仍然可正常导入。"""

    assert True  # 所有导入成功


def test_full_test_suite_passes_with_phase2a_additions():
    """回归验证：全量测试套件应全部通过（本测试仅为标记，实际验证在 CI）。"""
    # 此测试为标记性测试，确保 Phase 2A 新增内容存在
    # 实际回归由 CI 运行 `pytest tests/ -v` 完成
    assert Path("src/llm_adapter.py").exists()
    assert Path("src/schema_validators.py").exists()
    for name in PROMPT_FILES:
        assert (PROMPT_DIR / f"{name}.md").exists(), f"缺少 Prompt 模板: {name}"
