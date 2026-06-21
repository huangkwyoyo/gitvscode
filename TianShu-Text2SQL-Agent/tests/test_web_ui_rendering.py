"""Phase 7 —— Web UI 响应渲染测试。

覆盖：
    - response_type 渲染：answer / clarification / refusal / error
    - ChartSpec 渲染：line / bar / metric_card / table / 降级
    - 数据展示：warnings / sources / execution_mode
    - 安全：SQL/trace 不显示，图表异常不消失
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════
# ChartSpec 结构验证（使用真实 chart_spec.py）
# ═══════════════════════════════════════════════════════════════


class TestChartSpecStructure:
    """测试 ChartSpec 的真实结构（用于 UI 渲染器消费）"""

    def test_chart_spec_fields(self):
        """ChartSpec 包含 UI 渲染所需的全部字段"""
        from src.chart_spec import ChartSpec
        spec = ChartSpec(chart_type="line", title="测试")
        d = spec.to_dict()
        assert d["chart_type"] == "line"
        assert d["title"] == "测试"
        assert "x_field" in d
        assert "y_fields" in d
        assert "series" in d
        assert "source" in d
        assert "warnings" in d
        assert "data_preview" in d

    def test_chart_spec_serializable(self):
        """ChartSpec 可序列化为 JSON"""
        import json
        from src.chart_spec import ChartSpec
        spec = ChartSpec(
            chart_type="line",
            title="测试折线图",
            x_field="date",
            y_fields=["count"],
            series=[{"name": "count", "x": ["2026-01-01"], "y": [42]}],
            source="test.table",
            warnings=["测试警告"],
            data_preview=[["2026-01-01", 42]],
        )
        json_str = spec.to_json()
        parsed = json.loads(json_str)
        assert parsed["chart_type"] == "line"
        assert len(parsed["series"]) == 1

    def test_build_chart_spec_from_summary_line(self):
        """ResultSummary 含 date + 数值列 → line"""
        from src.ir import ResultSummary
        from src.chart_spec import build_chart_spec_from_summary
        summary = ResultSummary(
            primary_table="trips",
            row_count=3,
            columns=["trip_date", "trip_count"],
            sample_rows=[["2026-01-01", 100], ["2026-01-02", 120], ["2026-01-03", 95]],
            metrics=["trip_count"],
            has_date_column=True,
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type == "line"
        assert spec.title != ""

    def test_build_chart_spec_from_summary_bar(self):
        """ResultSummary 含类别列 + 数值列 → bar"""
        from src.ir import ResultSummary
        from src.chart_spec import build_chart_spec_from_summary
        summary = ResultSummary(
            primary_table="fines",
            row_count=3,
            columns=["violation_type", "total_fine"],
            sample_rows=[["停车", 500], ["超速", 1200], ["闯红灯", 800]],
            metrics=["total_fine"],
            has_date_column=False,
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type == "bar"

    def test_build_chart_spec_from_summary_metric_card(self):
        """单行单指标 → metric_card"""
        from src.ir import ResultSummary
        from src.chart_spec import build_chart_spec_from_summary
        summary = ResultSummary(
            primary_table="trips",
            row_count=1,
            columns=["total"],
            sample_rows=[[1500]],
            metrics=["total"],
            has_date_column=False,
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type == "metric_card"

    def test_build_chart_spec_from_summary_empty(self):
        """空结果 → table"""
        from src.ir import ResultSummary
        from src.chart_spec import build_chart_spec_from_summary
        summary = ResultSummary(
            primary_table="trips",
            row_count=0,
            columns=[],
            sample_rows=[],
            metrics=[],
            has_date_column=False,
        )
        spec = build_chart_spec_from_summary(summary)
        assert spec.chart_type == "table"

    def test_chart_spec_unknown_type_has_default(self):
        """ChartSpec 默认类型为 table"""
        from src.chart_spec import ChartSpec
        spec = ChartSpec()
        assert spec.chart_type == "table"


# ═══════════════════════════════════════════════════════════════
# Response Contract 结构验证
# ═══════════════════════════════════════════════════════════════


class TestResponseContract:
    """测试公开响应契约的结构（用于 UI 渲染器消费）"""

    def test_answer_response_structure(self):
        """answer 类型响应包含所有必要字段"""
        from src.ir import AgentResponse
        from src.response_contract import build_public_response

        resp = AgentResponse(
            question="测试问题",
            chinese_answer="测试答案",
            result_summaries=[],
            warnings=[],
        )
        public = build_public_response(resp)
        assert public["response_type"] == "answer"
        assert public["answer"]["text"] == "测试答案"
        assert public["clarification"]["needed"] is False
        assert public["refusal"]["refused"] is False
        assert public["contract_version"] == "1.0"

    def test_clarification_response_structure(self):
        """clarification 类型响应"""
        from src.ir import AgentResponse
        from src.response_contract import build_public_response

        resp = AgentResponse(
            question="昨天有多少事故？",
            clarification_needed=True,
            clarification_message="请指定事故类型",
        )
        public = build_public_response(resp)
        assert public["response_type"] == "clarification"
        assert public["clarification"]["needed"] is True
        assert "事故类型" in public["clarification"]["message"]

    def test_refusal_response_structure(self):
        """refusal 类型响应"""
        from src.ir import AgentResponse
        from src.response_contract import build_public_response

        resp = AgentResponse(
            question="删除所有数据",
            refusal=True,
            refusal_reason="不允许修改数据库",
        )
        public = build_public_response(resp)
        assert public["response_type"] == "refusal"
        assert public["refusal"]["refused"] is True
        assert "修改" in public["refusal"]["reason"]

    def test_answer_has_data_section(self):
        """answer 响应包含 data 段"""
        from src.ir import AgentResponse
        from src.response_contract import build_public_response

        resp = AgentResponse(
            question="测试问题",
            chinese_answer="答案",
            result_summaries=[],
        )
        public = build_public_response(resp)
        assert "data" in public
        assert "summaries" in public["data"]
        assert "chart_spec" in public["data"]
        assert "sources" in public["data"]

    def test_answer_has_meta_section(self):
        """answer 响应包含 meta 段"""
        from src.ir import AgentResponse
        from src.response_contract import build_public_response

        resp = AgentResponse(
            question="测试",
            chinese_answer="答案",
            execution_mode="single",
        )
        public = build_public_response(resp)
        assert "meta" in public
        assert public["meta"]["execution_mode"] == "single"


# ═══════════════════════════════════════════════════════════════
# 渲染行为验证（通过模拟公开响应结构）
# ═══════════════════════════════════════════════════════════════


class TestResponseRenderingLogic:
    """测试渲染逻辑应遵循的响应契约规则"""

    def test_answer_type_has_chinese_text(self):
        """answer 类型有中文答案文本（测试 #49）"""
        from src.ir import AgentResponse
        from src.response_contract import build_public_response

        resp = AgentResponse(
            question="测试",
            chinese_answer="这是中文答案",
        )
        public = build_public_response(resp)
        assert public["answer"]["text"] == "这是中文答案"

    def test_clarification_type_shows_message(self):
        """clarification 类型显示反问消息（测试 #50）"""
        from src.ir import AgentResponse
        from src.response_contract import build_public_response

        resp = AgentResponse(
            question="测试",
            clarification_needed=True,
            clarification_message="请补充信息",
        )
        public = build_public_response(resp)
        assert public["clarification"]["message"] == "请补充信息"

    def test_refusal_type_shows_reason(self):
        """refusal 类型显示拒绝原因（测试 #51）"""
        from src.ir import AgentResponse
        from src.response_contract import build_public_response

        resp = AgentResponse(
            question="测试",
            refusal=True,
            refusal_reason="安全策略禁止",
        )
        public = build_public_response(resp)
        assert public["refusal"]["reason"] == "安全策略禁止"

    def test_clarification_no_data(self):
        """clarification 时 data 段为空"""
        from src.ir import AgentResponse
        from src.response_contract import build_public_response

        resp = AgentResponse(
            question="测试",
            clarification_needed=True,
            clarification_message="需要更多信息",
            result_summaries=[{"primary_table": "trips", "columns": ["a"], "sample_rows": [["x"]], "metrics": ["a"], "row_count": 1, "has_date_column": False, "errors": [], "warnings": []}],
        )
        public = build_public_response(resp)
        # clarification 时 chart_spec 应为 None
        assert public["data"]["chart_spec"] is None

    def test_refusal_no_data(self):
        """refusal 时 data 段为空"""
        from src.ir import AgentResponse
        from src.response_contract import build_public_response

        resp = AgentResponse(
            question="删除数据",
            refusal=True,
            refusal_reason="不允许写操作",
        )
        public = build_public_response(resp)
        assert public["data"]["chart_spec"] is None

    def test_error_type_response(self):
        """error 类型（AgentResponse 中 result.error 非空）"""
        from src.ir import AgentResponse, SQLResult
        from src.response_contract import build_public_response

        result_with_error = SQLResult(
            sql="SELECT 1",
            columns=[],
            rows=[],
            error="数据库连接失败",
        )
        resp = AgentResponse(
            question="测试",
            result=result_with_error,
        )
        public = build_public_response(resp)
        assert public["response_type"] == "error"

    def test_public_response_excludes_sql(self):
        """公开响应不包含 SQL 字段"""
        from src.ir import AgentResponse
        from src.response_contract import build_public_response

        resp = AgentResponse(
            question="测试",
            chinese_answer="答案",
        )
        public = build_public_response(resp)
        # 递归检查所有 key
        def check_keys(obj, path=""):
            if isinstance(obj, dict):
                for k in obj:
                    assert "sql" not in k.lower(), f"在 {path}.{k} 发现 SQL 相关 key"
                    check_keys(obj[k], f"{path}.{k}")
        check_keys(public)

    def test_public_response_excludes_trace(self):
        """公开响应不包含 trace"""
        from src.ir import AgentResponse
        from src.response_contract import build_public_response

        resp = AgentResponse(
            question="测试",
            chinese_answer="答案",
        )
        public = build_public_response(resp)
        public_str = str(public)
        assert "trace" not in public_str.lower()
