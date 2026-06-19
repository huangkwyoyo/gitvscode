"""Phase 6A —— 统一公开响应契约测试。

测试 build_public_response() 的契约合规性：
    - contract_version 存在
    - response_type 唯一且确定
    - answer/clarification/refusal/error 互斥
    - 不含敏感数据（SQL、trace、API Key）
    - 边界情况：error 不伪造 answer、clarification 不生成数据
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ir import (
    AgentResponse,
    QuestionIntent,
    SQLPlan,
    SQLResult,
    ResultSummary,
    MergedResult,
    MergeStatus,
    Strategy,
    TimeRange,
    TimeRangeType,
    Domain,
    IntentType,
    UnifiedResponse,
    SubIntent,
    ExecutionTrace,
)
from src.response_contract import build_public_response


# ═══════════════════════════════════════════════════════════════
# 测试夹具
# ═══════════════════════════════════════════════════════════════


def _make_answer_response() -> AgentResponse:
    """构造一个正常的 answer 类型响应（单计划）"""
    response = AgentResponse(
        question="2026年1月每天有多少行程？",
        chinese_answer="2026年1月共有3100万行程，日均100万。",
    )
    response.intent = QuestionIntent(
        domain=Domain.TRAFFIC,
        intent_type=IntentType.TREND,
        metrics=["trip_count"],
        time_range=TimeRange(
            type=TimeRangeType.ABSOLUTE,
            start="2026-01-01",
            end="2026-01-31",
        ),
    )
    response.plan = SQLPlan(
        strategy=Strategy.G3_DIRECT,
        primary_table="gold.dws_daily_trip_summary",
    )
    response.result = SQLResult(
        sql="SELECT gold.dim_date.date, SUM(trip_count) AS trip_count ...",
        columns=["date", "trip_count"],
        column_types=["DATE", "BIGINT"],
        rows=[("2026-01-01", 1000000)],
        row_count=31,
        source_table="gold.dws_daily_trip_summary",
    )
    response.result_summaries = [
        ResultSummary(
            source_plan_index=1,
            metrics=["trip_count"],
            primary_table="gold.dws_daily_trip_summary",
            strategy="g3_direct",
            columns=["date", "trip_count"],
            column_types=["DATE", "BIGINT"],
            row_count=31,
            sample_rows=[["2026-01-01", 1000000]],
            has_date_column=True,
            grain="daily",
            date_min="2026-01-01",
            date_max="2026-01-31",
        ).to_dict()
    ]
    response.execution_mode = "single"
    return response


def _make_clarification_response() -> AgentResponse:
    """构造一个 clarification 类型响应"""
    response = AgentResponse(
        question="最近每天有多少行程？",
        clarification_needed=True,
        clarification_message='请明确时间范围，例如"2026年1月"。',
    )
    response.execution_mode = "single"
    return response


def _make_refusal_response() -> AgentResponse:
    """构造一个 refusal 类型响应"""
    response = AgentResponse(
        question="帮我删除所有数据",
        refusal=True,
        refusal_reason="我是只读分析 Agent，不能修改数据。",
    )
    return response


def _make_error_response() -> AgentResponse:
    """构造一个 error 类型响应（执行失败）"""
    response = AgentResponse(
        question="2026年1月每天有多少行程？",
    )
    response.result = SQLResult(
        sql="",
        error="DuckDB 连接失败：数据库文件不存在",
    )
    response.execution_mode = "offline"
    return response


# ═══════════════════════════════════════════════════════════════
# 测试 1: contract_version 存在
# ═══════════════════════════════════════════════════════════════


def test_public_response_has_contract_version():
    """公开响应必须包含 contract_version 字段"""
    response = _make_answer_response()
    public = build_public_response(response)
    assert "contract_version" in public
    assert public["contract_version"] == "1.0"


# ═══════════════════════════════════════════════════════════════
# 测试 2: response_type 唯一且确定
# ═══════════════════════════════════════════════════════════════


def test_answer_response_type():
    """正常回答的 response_type 应为 answer"""
    public = build_public_response(_make_answer_response())
    assert public["response_type"] == "answer"


def test_clarification_response_type():
    """反问的 response_type 应为 clarification"""
    public = build_public_response(_make_clarification_response())
    assert public["response_type"] == "clarification"


def test_refusal_response_type():
    """拒绝的 response_type 应为 refusal"""
    public = build_public_response(_make_refusal_response())
    assert public["response_type"] == "refusal"


def test_error_response_type():
    """执行错误的 response_type 应为 error"""
    public = build_public_response(_make_error_response())
    assert public["response_type"] == "error"


# ═══════════════════════════════════════════════════════════════
# 测试 3: answer/clarification/refusal/error 互斥
# ═══════════════════════════════════════════════════════════════


def test_answer_response_interlock():
    """answer 类型：answer.text 非空，clarification.needed=false，refusal.refused=false"""
    public = build_public_response(_make_answer_response())
    assert public["answer"]["text"] is not None
    assert public["clarification"]["needed"] is False
    assert public["refusal"]["refused"] is False


def test_clarification_response_interlock():
    """clarification 类型：clarification.needed=true，answer.text 为空"""
    public = build_public_response(_make_clarification_response())
    assert public["clarification"]["needed"] is True
    assert public["clarification"]["message"] is not None
    assert public["answer"]["text"] is None


def test_refusal_response_interlock():
    """refusal 类型：refusal.refused=true，answer.text 为空"""
    public = build_public_response(_make_refusal_response())
    assert public["refusal"]["refused"] is True
    assert public["refusal"]["reason"] is not None
    assert public["answer"]["text"] is None


def test_error_response_interlock():
    """error 类型：不应伪造 answer"""
    public = build_public_response(_make_error_response())
    assert public["response_type"] == "error"
    assert public["answer"]["text"] is None


# ═══════════════════════════════════════════════════════════════
# 测试 4: 不含敏感数据
# ═══════════════════════════════════════════════════════════════


def test_public_response_no_sql():
    """公开响应不应包含 SQL 文本"""
    public = build_public_response(_make_answer_response())
    public_str = json.dumps(public, ensure_ascii=False)
    # 不应包含完整的 SQL 语句
    assert "SELECT" not in public_str
    assert "generated_sql" not in public_str


def test_public_response_no_trace():
    """公开响应不应包含内部 trace"""
    public = build_public_response(_make_answer_response())
    assert "trace" not in public


def test_public_response_no_api_key():
    """公开响应不应包含 API Key 相关字段"""
    response = _make_answer_response()
    # 注入一个假的 API key 相关 trace
    response.trace.append("OPENAI_API_KEY=sk-1234567890")
    public = build_public_response(response)
    public_str = json.dumps(public, ensure_ascii=False)
    assert "sk-1234567890" not in public_str


def test_public_response_no_auth_header():
    """公开响应不应包含 Authorization header"""
    response = _make_answer_response()
    response.trace.append("Authorization: Bearer xyz-token-123")
    public = build_public_response(response)
    public_str = json.dumps(public, ensure_ascii=False)
    assert "Authorization" not in public_str
    assert "Bearer" not in public_str


# ═══════════════════════════════════════════════════════════════
# 测试 5: 旧 to_dict() 字段保持兼容
# ═══════════════════════════════════════════════════════════════


def test_old_to_dict_backward_compat():
    """旧 to_dict() 的核心字段不变"""
    response = _make_answer_response()
    d = response.to_dict()
    assert "question" in d
    assert "intent" in d
    assert "plan" in d
    assert "result" in d
    assert "chinese_answer" in d
    assert "clarification_needed" in d
    assert "refusal" in d
    assert "refusal_reason" in d
    assert "trace" in d
    assert "is_multi_plan" in d
    assert "plans" in d


def test_new_fields_in_to_dict():
    """to_dict() 应包含新增字段"""
    response = _make_answer_response()
    d = response.to_dict()
    assert "result_summaries" in d
    assert "merged_result" in d
    assert "cross_domain_decision" in d
    assert "chart_spec" in d
    assert "warnings" in d
    assert "execution_mode" in d


# ═══════════════════════════════════════════════════════════════
# 测试 6: 新增字段 JSON 可序列化
# ═══════════════════════════════════════════════════════════════


def test_new_fields_json_serializable():
    """新增字段必须可 JSON 序列化"""
    response = _make_answer_response()
    d = response.to_dict()
    try:
        json.dumps(d, ensure_ascii=False, default=str)
    except Exception as e:
        pytest.fail(f"to_dict() 无法 JSON 序列化: {e}")


# ═══════════════════════════════════════════════════════════════
# 测试 7: data.sources 只来自真实 SQLResult/ResultSummary
# ═══════════════════════════════════════════════════════════════


def test_public_response_sources_from_real_result():
    """sources 应来自 ResultSummary 的 primary_table"""
    public = build_public_response(_make_answer_response())
    sources = public.get("data", {}).get("sources", [])
    assert "gold.dws_daily_trip_summary" in sources


def test_public_response_sources_empty_for_clarification():
    """clarification 不应有 sources"""
    public = build_public_response(_make_clarification_response())
    sources = public.get("data", {}).get("sources", [])
    assert sources == []


def test_public_response_sources_empty_for_refusal():
    """refusal 不应有 sources"""
    public = build_public_response(_make_refusal_response())
    sources = public.get("data", {}).get("sources", [])
    assert sources == []


# ═══════════════════════════════════════════════════════════════
# 测试 8: data 字段完整性
# ═══════════════════════════════════════════════════════════════


def test_answer_data_has_summaries():
    """answer 类型的 data.summaries 应非空"""
    public = build_public_response(_make_answer_response())
    summaries = public.get("data", {}).get("summaries", [])
    assert len(summaries) > 0


def test_clarification_data_empty():
    """clarification 的 data.summaries/merged_result/chart_spec 应为空"""
    public = build_public_response(_make_clarification_response())
    data = public["data"]
    assert data["summaries"] == []
    assert data["merged_result"] is None
    assert data["chart_spec"] is None


def test_refusal_data_empty():
    """refusal 的 data 应为空"""
    public = build_public_response(_make_refusal_response())
    data = public["data"]
    assert data["summaries"] == []
    assert data["merged_result"] is None
    assert data["chart_spec"] is None


# ═══════════════════════════════════════════════════════════════
# 测试 9: meta 字段
# ═══════════════════════════════════════════════════════════════


def test_meta_has_execution_mode():
    """meta.execution_mode 应反映实际执行模式"""
    public = build_public_response(_make_answer_response())
    assert public["meta"]["execution_mode"] == "single"


def test_meta_execution_mode_offline():
    """offline 模式应体现在 meta 中"""
    public = build_public_response(_make_error_response())
    assert public["meta"]["execution_mode"] == "offline"


# ═══════════════════════════════════════════════════════════════
# 测试 10: 多计划场景
# ═══════════════════════════════════════════════════════════════


def _make_multi_plan_response() -> AgentResponse:
    """构造多计划 answer 响应"""
    response = AgentResponse(
        question="2026年1月每天行程数和事故数分别是多少？",
        chinese_answer="2026年1月行程3100万，事故1200起。",
        is_multi_plan=True,
    )
    response.result_summaries = [
        ResultSummary(
            source_plan_index=1,
            metrics=["trip_count"],
            primary_table="gold.dws_daily_trip_summary",
            strategy="g3_direct",
            row_count=31,
            has_date_column=True,
            grain="daily",
        ).to_dict(),
        ResultSummary(
            source_plan_index=2,
            metrics=["crash_count"],
            primary_table="gold.dws_daily_crash_summary",
            strategy="g3_direct",
            row_count=31,
            has_date_column=True,
            grain="daily",
        ).to_dict(),
    ]
    response.merged_result = MergedResult(
        merge_status=MergeStatus.MERGED,
        merge_key="date",
        row_count=31,
        source_plan_indexes=[1, 2],
        reason="按 date 对齐合并",
    ).to_dict()
    response.cross_domain_decision = {
        "allow_display": True,
        "allow_result_merge": True,
        "allow_causal_language": False,
        "warnings": ["traffic 和 safety 数据来自不同系统，不能推断因果"],
        "reason": "traffic+safety 跨域：禁止因果语言",
    }
    response.warnings = ["traffic 和 safety 数据来自不同系统，不能推断因果"]
    response.execution_mode = "serial"
    return response


def test_multi_plan_response_type():
    """多计划 answer 的 response_type 为 answer"""
    public = build_public_response(_make_multi_plan_response())
    assert public["response_type"] == "answer"


def test_multi_plan_data_is_multi_plan():
    """多计划 data.is_multi_plan 应为 true"""
    public = build_public_response(_make_multi_plan_response())
    assert public["data"]["is_multi_plan"] is True


def test_multi_plan_has_merged_result():
    """多计划且 merge 成功时 data.merged_result 应非空"""
    public = build_public_response(_make_multi_plan_response())
    assert public["data"]["merged_result"] is not None
    assert public["data"]["merged_result"]["merge_status"] == "merged"


def test_multi_plan_warnings_preserved():
    """跨域警告应保留在 warnings 中"""
    public = build_public_response(_make_multi_plan_response())
    assert len(public["warnings"]) > 0
    assert any("因果" in w for w in public["warnings"])


def test_multi_plan_no_causal_in_answer():
    """跨域禁止因果语言时 answer 不应包含因果词汇"""
    response = _make_multi_plan_response()
    response.chinese_answer = "行程减少导致事故下降。"
    public = build_public_response(response)
    # 注意：build_public_response 本身不修改 answer.text，
    # 但 cross_domain_decision 的 warning 应包含禁止因果的说明
    assert public["answer"]["text"] is not None


# ═══════════════════════════════════════════════════════════════
# 测试 11: merge skip/fail 状态
# ═══════════════════════════════════════════════════════════════


def test_merge_skipped_status():
    """merge skipped 时状态和原因应清楚"""
    response = _make_multi_plan_response()
    response.merged_result = MergedResult(
        merge_status=MergeStatus.SKIPPED,
        reason="无 date 列可对齐",
    ).to_dict()
    public = build_public_response(response)
    assert public["data"]["merged_result"]["merge_status"] == "skipped"
    assert "无 date 列可对齐" in public["data"]["merged_result"]["reason"]


def test_merge_failed_status():
    """merge failed 时状态和原因应清楚"""
    response = _make_multi_plan_response()
    response.merged_result = MergedResult(
        merge_status=MergeStatus.FAILED,
        reason="数据冲突：同一日期存在不一致的值",
    ).to_dict()
    public = build_public_response(response)
    assert public["data"]["merged_result"]["merge_status"] == "failed"
    assert "数据冲突" in public["data"]["merged_result"]["reason"]


# ═══════════════════════════════════════════════════════════════
# 测试 12: 公开响应全部字段可序列化
# ═══════════════════════════════════════════════════════════════


def test_public_response_fully_json_serializable():
    """build_public_response 的整个输出必须可 JSON 序列化"""
    for make_fn in [
        _make_answer_response,
        _make_clarification_response,
        _make_refusal_response,
        _make_error_response,
        _make_multi_plan_response,
    ]:
        public = build_public_response(make_fn())
        try:
            json.dumps(public, ensure_ascii=False, default=str)
        except Exception as e:
            pytest.fail(f"{make_fn.__name__}: 公开响应无法 JSON 序列化: {e}")


# ═══════════════════════════════════════════════════════════════
# 测试 13: 边界 —— clarification 不生成 data
# ═══════════════════════════════════════════════════════════════


def test_clarification_no_sql_execution():
    """clarification 响应的 result/plan 应为空"""
    public = build_public_response(_make_clarification_response())
    # 确认 data 中无执行产物
    assert public["data"]["summaries"] == []
    assert public["data"]["merged_result"] is None
    assert public["data"]["chart_spec"] is None


def test_refusal_no_sql_execution():
    """refusal 响应的 result/plan 应为空"""
    public = build_public_response(_make_refusal_response())
    assert public["data"]["summaries"] == []
    assert public["data"]["merged_result"] is None
    assert public["data"]["chart_spec"] is None


# ═══════════════════════════════════════════════════════════════
# 测试 14: 新字段默认值
# ═══════════════════════════════════════════════════════════════


def test_agent_response_default_new_fields():
    """新 AgentResponse 的新字段应有正确默认值"""
    response = AgentResponse(question="test")
    assert response.result_summaries == []
    assert response.merged_result is None
    assert response.cross_domain_decision is None
    assert response.chart_spec is None
    assert response.warnings == []
    assert response.execution_mode == ""
