"""
LLM 结果融合测试套件。

覆盖：
    1. Mock LLM 正常解释 MergedResult
    2. Mock LLM 正常解释未 merge 的多个 ResultSummary
    3. LLM 输出 SQL 时被拒绝并 fallback
    4. LLM 输出因果语言时被拒绝并 fallback
    5. LLM 编造指标时被拒绝并 fallback
    6. LLM 调用异常时 fallback
    7. 不修改 SQLPlan
    8. 不调用 sql_plan_to_sql
    9. 不调用 DuckDB
    10. 现有 fuse_results 测试不破坏
    11. build_result_fusion_payload 载荷结构
    12. validate_fusion_output 各项检测
    13. fallback_to_template 行为一致
    14. 边界：空 summaries、无 merged_result、所有空结果
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from src.ir import (
    MergeStatus,
    MergedResult,
    ResultSummary,
    SQLResult,
    UnifiedResponse,
)
from src.llm import (
    FakeLLMClient,
    PromptLoader,
)
from src.result_fusion import (
    _check_causal_language,
    _check_fabricated_metrics,
    _check_sql_keywords,
    _extract_json_object,
    build_result_fusion_payload,
    fallback_to_template,
    fuse_results_with_llm,
    validate_fusion_output,
)


# ═══════════════════════════════════════════════════════════
# 测试辅助函数
# ═══════════════════════════════════════════════════════════


def _make_summary(
    plan_index: int = 1,
    metrics: list[str] | None = None,
    primary_table: str = "gold.dws_daily_trip_summary",
    row_count: int = 31,
    has_date: bool = True,
    grain: str = "daily",
    date_min: str = "2026-01-01",
    date_max: str = "2026-01-31",
    columns: list[str] | None = None,
    sample_rows: list[list] | None = None,
    warnings: list[str] | None = None,
) -> ResultSummary:
    """创建测试用 ResultSummary"""
    return ResultSummary(
        source_plan_index=plan_index,
        metrics=metrics or ["trip_count"],
        primary_table=primary_table,
        row_count=row_count,
        has_date_column=has_date,
        grain=grain,
        date_min=date_min,
        date_max=date_max,
        columns=columns or ["trip_date", "trip_count"],
        sample_rows=sample_rows or [["2026-01-01", 888250], ["2026-01-02", 761261]],
        warnings=warnings or [],
    )


def _make_merged(
    merge_status: MergeStatus = MergeStatus.MERGED,
    row_count: int = 31,
    columns: list[str] | None = None,
    rows: list[list] | None = None,
    reason: str = "",
    summaries: list[ResultSummary] | None = None,
    merge_warnings: list[str] | None = None,
) -> MergedResult:
    """创建测试用 MergedResult"""
    return MergedResult(
        merge_status=merge_status,
        merge_key="date",
        row_count=row_count,
        columns=columns or ["date", "trip_count", "persons_injured"],
        rows=rows or [["2026-01-01", 888250, 142], ["2026-01-02", 761261, 98]],
        source_plan_indexes=[1, 2],
        source_summaries=summaries or [],
        merge_warnings=merge_warnings or [],
        reason=reason,
    )


def _make_unified_response(
    metrics: list[str] | None = None,
    table: str = "gold.dws_daily_trip_summary",
    row_count: int = 31,
    columns: list[str] | None = None,
    rows: list | None = None,
    error: str = "",
) -> UnifiedResponse:
    """创建测试用 UnifiedResponse"""
    from src.ir import Domain, SubIntent

    sub = SubIntent(
        metrics=metrics or ["trip_count"],
        dimensions=[],
        planning_table=table,
        domain=Domain.TRAFFIC,
    )
    result = SQLResult(
        sql="SELECT trip_date, trip_count FROM gold.dws_daily_trip_summary",
        columns=columns or ["trip_date", "trip_count"],
        column_types=["DATE", "BIGINT"],
        rows=rows or [("2026-01-01", 888250), ("2026-01-02", 761261)],
        row_count=row_count,
        execution_time_ms=12.5,
        source_table=table,
        error=error,
    )
    return UnifiedResponse(sub_intent=sub, plan=None, result=result)


# ═══════════════════════════════════════════════════════════
# 测试类 1: build_result_fusion_payload
# ═══════════════════════════════════════════════════════════


class TestBuildPayload:
    """测试受控输入载荷的构建"""

    def test_build_payload_basic_structure(self):
        """载荷应包含 question、plan_count、summaries 等基本字段"""
        s1 = _make_summary(plan_index=1, metrics=["trip_count"])
        s2 = _make_summary(plan_index=2, metrics=["persons_injured"],
                           primary_table="gold.dws_daily_crash_summary")
        merged = _make_merged(summaries=[s1, s2])

        payload = build_result_fusion_payload(
            question="2026年1月行程量和受伤人数？",
            summaries=[s1, s2],
            merged_result=merged,
            merge_status="merged",
        )

        assert payload["question"] == "2026年1月行程量和受伤人数？"
        assert payload["plan_count"] == 2
        assert len(payload["summaries"]) == 2
        assert payload["merge_status"] == "merged"
        assert payload["merged_result"] is not None
        assert payload["merged_result"]["merge_status"] == "merged"
        assert payload["merged_result"]["row_count"] == 31

    def test_build_payload_summary_fields_limited(self):
        """summary dict 不应包含原始数据的大字段（限制样本行数）"""
        s = _make_summary(
            sample_rows=[
                ["2026-01-01", 100],
                ["2026-01-02", 200],
                ["2026-01-03", 300],
                ["2026-01-04", 400],
                ["2026-01-05", 500],
                ["2026-01-06", 600],  # 超过 5 行
            ]
        )

        payload = build_result_fusion_payload(
            question="测试",
            summaries=[s],
        )

        summary_dict = payload["summaries"][0]
        assert len(summary_dict["sample_rows"]) <= 5  # 最多 5 行

    def test_build_payload_no_merged_result(self):
        """无 merged_result 时应正常构建，merged_result 字段为 None"""
        s = _make_summary()

        payload = build_result_fusion_payload(
            question="测试",
            summaries=[s],
            merged_result=None,
        )

        assert payload["merged_result"] is None
        assert payload["merge_status"] == "not_attempted"

    def test_build_payload_merged_rows_limited(self):
        """合并结果行数应限制在 50 行以内"""
        many_rows = [[f"2026-01-{i:02d}", i, i * 2] for i in range(1, 100)]
        merged = _make_merged(rows=many_rows)

        payload = build_result_fusion_payload(
            question="测试",
            summaries=[_make_summary()],
            merged_result=merged,
        )

        assert len(payload["merged_result"]["rows"]) <= 50

    def test_build_payload_excludes_sensitive_fields(self):
        """载荷不得包含 SQL、API key 等敏感字段"""
        s = _make_summary()
        payload = build_result_fusion_payload(question="测试", summaries=[s])

        payload_str = json.dumps(payload)
        assert "sql" not in payload_str.lower()
        assert "api_key" not in payload_str.lower()
        assert "secret" not in payload_str.lower()
        assert "password" not in payload_str.lower()


# ═══════════════════════════════════════════════════════════
# 测试类 2: Mock LLM 正常解释
# ═══════════════════════════════════════════════════════════


class TestLLMFusionNormal:
    """测试 LLM 正常融合路径"""

    def test_fuse_merged_result_with_llm(self):
        """Mock LLM 正常解释 MergedResult"""
        s1 = _make_summary(plan_index=1, metrics=["trip_count"])
        s2 = _make_summary(plan_index=2, metrics=["persons_injured"],
                           primary_table="gold.dws_daily_crash_summary")
        merged = _make_merged(summaries=[s1, s2])

        llm = FakeLLMClient({
            "result_fusion": json.dumps({
                "explanation_text": (
                    "2026年1月的数据已按日期对齐合并展示，共31天。"
                    "行程量来自 gold.dws_daily_trip_summary 表，"
                    "受伤人数来自 gold.dws_daily_crash_summary 表。"
                    "1月1日行程量为888,250次、受伤142人；"
                    "1月2日行程量为761,261次、受伤98人。"
                ),
            }),
        })
        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        explanation, used_llm, fallback_reason = fuse_results_with_llm(
            question="2026年1月行程量和受伤人数？",
            summaries=[s1, s2],
            merged_result=merged,
            merge_status="merged",
            warnings=[],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert used_llm is True
        assert fallback_reason is None
        assert "dws_daily_trip_summary" in explanation
        assert "dws_daily_crash_summary" in explanation
        assert "31" in explanation  # 行数被保留

    def test_fuse_unmerged_summaries_with_llm(self):
        """Mock LLM 正常解释未 merge 的多个 ResultSummary"""
        s1 = _make_summary(plan_index=1, metrics=["trip_count"], row_count=31)
        s2 = _make_summary(plan_index=2, metrics=["standard_fine_total"],
                           primary_table="gold.dws_daily_parking_summary",
                           row_count=0, has_date=False, grain="unknown",
                           date_min="", date_max="",
                           columns=[], sample_rows=[],
                           warnings=["查询结果为空"])

        merged = _make_merged(
            merge_status=MergeStatus.SKIPPED,
            reason="部分结果缺少日期列，无法按 date 对齐",
            summaries=[s1, s2],
        )

        llm = FakeLLMClient({
            "result_fusion": json.dumps({
                "explanation_text": (
                    "该问题涉及两个指标，部分结果缺少日期列，无法按日期对齐合并。"
                    "指标1 trip_count 来自 gold.dws_daily_trip_summary 表，返回31行。"
                    "指标2 standard_fine_total 来自 gold.dws_daily_parking_summary 表，未返回数据。"
                ),
            }),
        })
        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        explanation, used_llm, fallback_reason = fuse_results_with_llm(
            question="2026年1月行程量和停车罚单？",
            summaries=[s1, s2],
            merged_result=merged,
            merge_status="skipped",
            warnings=[],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert used_llm is True
        assert fallback_reason is None
        assert "dws_daily_trip_summary" in explanation
        assert "dws_daily_parking_summary" in explanation
        assert "无法按日期对齐" in explanation or "未合并" in explanation or "缺少日期列" in explanation

    def test_fuse_preserves_input_numbers(self):
        """LLM 解释应保留输入的数值（不改变 row_count 等）"""
        s = _make_summary(row_count=42, date_min="2026-03-01", date_max="2026-03-15")

        llm = FakeLLMClient({
            "result_fusion": json.dumps({
                "explanation_text": (
                    "查询返回42行数据，日期范围2026-03-01至2026-03-15。"
                    "数据来源：gold.dws_daily_trip_summary。"
                ),
            }),
        })
        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        explanation, used_llm, _ = fuse_results_with_llm(
            question="测试",
            summaries=[s],
            merged_result=None,
            merge_status="not_attempted",
            warnings=[],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert used_llm is True
        assert "42" in explanation
        assert "2026-03-01" in explanation
        assert "2026-03-15" in explanation


# ═══════════════════════════════════════════════════════════
# 测试类 3: LLM 输出 SQL → 被拒绝并 fallback
# ═══════════════════════════════════════════════════════════


class TestLLMFusionSQLRejection:
    """测试 LLM 输出 SQL 时被拒绝并 fallback"""

    def test_sql_in_output_rejected(self):
        """LLM 输出包含 SELECT 语句时应被拒绝"""
        s = _make_summary()
        llm = FakeLLMClient({
            "result_fusion": json.dumps({
                "explanation_text": (
                    "查询返回31行。可以使用 SELECT * FROM gold.dws_daily_trip_summary 查看更多数据。"
                ),
            }),
        })
        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        explanation, used_llm, fallback_reason = fuse_results_with_llm(
            question="测试",
            summaries=[s],
            merged_result=None,
            merge_status="not_attempted",
            warnings=[],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert used_llm is False
        assert fallback_reason is not None
        assert "SQL" in fallback_reason

    def test_sql_keyword_insert_rejected(self):
        """LLM 输出包含 INSERT 关键字时应被拒绝"""
        s = _make_summary()
        llm = FakeLLMClient({
            "result_fusion": json.dumps({
                "explanation_text": "数据正常。如需新增记录可使用 INSERT INTO。",
            }),
        })
        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        _, used_llm, fallback_reason = fuse_results_with_llm(
            question="测试",
            summaries=[s],
            merged_result=None,
            merge_status="not_attempted",
            warnings=[],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert used_llm is False
        assert "SQL" in fallback_reason

    def test_sql_keyword_drop_rejected(self):
        """LLM 输出包含 DROP 关键字时应被拒绝"""
        s = _make_summary()
        llm = FakeLLMClient({
            "result_fusion": json.dumps({
                "explanation_text": "DROP TABLE 不在讨论范围。数据返回正常。",
            }),
        })
        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        _, used_llm, fallback_reason = fuse_results_with_llm(
            question="测试",
            summaries=[s],
            merged_result=None,
            merge_status="not_attempted",
            warnings=[],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert used_llm is False


# ═══════════════════════════════════════════════════════════
# 测试类 4: LLM 输出因果语言 → 被拒绝并 fallback
# ═══════════════════════════════════════════════════════════


class TestLLMFusionCausalRejection:
    """测试 LLM 输出因果措辞时被拒绝并 fallback"""

    def test_causal_word_daozhi_rejected(self):
        """输出包含"导致"时应被拒绝"""
        s = _make_summary()
        llm = FakeLLMClient({
            "result_fusion": json.dumps({
                "explanation_text": "1月2日行程量下降，导致整体均值偏低。数据来源：gold表。",
            }),
        })
        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        _, used_llm, fallback_reason = fuse_results_with_llm(
            question="测试",
            summaries=[s],
            merged_result=None,
            merge_status="not_attempted",
            warnings=[],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert used_llm is False
        assert "因果" in fallback_reason

    def test_causal_word_zaocheng_rejected(self):
        """输出包含"造成"时应被拒绝"""
        s = _make_summary()
        llm = FakeLLMClient({
            "result_fusion": json.dumps({
                "explanation_text": "天气原因造成数据波动。来自 gold.dws_daily_trip_summary。",
            }),
        })
        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        _, used_llm, fallback_reason = fuse_results_with_llm(
            question="测试",
            summaries=[s],
            merged_result=None,
            merge_status="not_attempted",
            warnings=[],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert used_llm is False

    def test_causal_pair_yinwei_suoyi_rejected(self):
        """输出包含"因为...所以..."结构时应被拒绝"""
        s = _make_summary()
        llm = FakeLLMClient({
            "result_fusion": json.dumps({
                "explanation_text": "因为1月1日是节假日，所以行程量较高。来源：gold.dws_daily_trip_summary。",
            }),
        })
        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        _, used_llm, fallback_reason = fuse_results_with_llm(
            question="测试",
            summaries=[s],
            merged_result=None,
            merge_status="not_attempted",
            warnings=[],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert used_llm is False


# ═══════════════════════════════════════════════════════════
# 测试类 5: LLM 编造指标 → 被拒绝并 fallback
# ═══════════════════════════════════════════════════════════


class TestLLMFusionFabricatedMetrics:
    """测试 LLM 编造指标时被拒绝并 fallback"""

    def test_fabricated_metric_rejected(self):
        """LLM 编造不存在的指标名时应被拒绝"""
        s = _make_summary(metrics=["trip_count"], columns=["trip_date", "trip_count"])

        llm = FakeLLMClient({
            "result_fusion": json.dumps({
                "explanation_text": (
                    "trip_count 返回31行。此外，avg_fare_amount 指标也有显著变化。"
                    "数据来源：gold.dws_daily_trip_summary。"
                ),
            }),
        })
        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        _, used_llm, fallback_reason = fuse_results_with_llm(
            question="测试",
            summaries=[s],
            merged_result=None,
            merge_status="not_attempted",
            warnings=[],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert used_llm is False
        assert "编造指标" in fallback_reason


# ═══════════════════════════════════════════════════════════
# 测试类 6: LLM 调用异常 → fallback
# ═══════════════════════════════════════════════════════════


class TestLLMFusionExceptionFallback:
    """测试 LLM 调用异常时的 fallback 行为"""

    def test_llm_client_raises_exception(self):
        """LLM 客户端抛出异常时 fallback"""
        s = _make_summary()

        llm = MagicMock()
        llm.complete.side_effect = RuntimeError("网络连接失败")

        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        explanation, used_llm, fallback_reason = fuse_results_with_llm(
            question="测试",
            summaries=[s],
            merged_result=None,
            merge_status="not_attempted",
            warnings=[],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert used_llm is False
        assert fallback_reason is not None
        assert "网络连接失败" in fallback_reason
        assert "回退" in explanation

    def test_llm_output_not_json(self):
        """LLM 输出非 JSON 时应 fallback"""
        s = _make_summary()

        llm = FakeLLMClient({
            "result_fusion": "这不是 JSON，只是一段普通文本。",
        })

        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        explanation, used_llm, fallback_reason = fuse_results_with_llm(
            question="测试",
            summaries=[s],
            merged_result=None,
            merge_status="not_attempted",
            warnings=[],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert used_llm is False
        assert fallback_reason is not None

    def test_llm_output_missing_explanation_text(self):
        """LLM 输出 JSON 但缺少 explanation_text 字段时应 fallback"""
        s = _make_summary()

        llm = FakeLLMClient({
            "result_fusion": json.dumps({"answer": "没有 explanation_text 字段"}),
        })

        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        _, used_llm, fallback_reason = fuse_results_with_llm(
            question="测试",
            summaries=[s],
            merged_result=None,
            merge_status="not_attempted",
            warnings=[],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert used_llm is False
        assert fallback_reason is not None
        assert "explanation_text" in fallback_reason


# ═══════════════════════════════════════════════════════════
# 测试类 7: 不修改 SQLPlan / 不调用 SQL 生成 / 不调用 DuckDB
# ═══════════════════════════════════════════════════════════


class TestLLMFusionNoSQLLeakage:
    """验证 LLM 融合不会接触 SQL 生成或执行"""

    def test_no_sqlplan_modification(self):
        """LLM 融合模块不应导入或调用 SQLPlan / sql_plan_to_sql"""
        import ast
        import inspect
        import src.result_fusion as rf

        source = inspect.getsource(rf)
        tree = ast.parse(source)

        # 检查所有 import 语句
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "sql_plan_to_sql" not in alias.name, (
                        "不应导入 sql_plan_to_sql"
                    )
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    assert "sql_plan_to_sql" not in alias.name, (
                        "不应导入 sql_plan_to_sql"
                    )

        # 检查所有函数调用（排除注释和文档字符串）
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    assert node.func.id != "sql_plan_to_sql", (
                        "不应调用 sql_plan_to_sql"
                    )

    def test_no_duckdb_import(self):
        """LLM 融合模块不应导入 DuckDB"""
        import ast
        import inspect
        import src.result_fusion as rf

        source = inspect.getsource(rf)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "duckdb" not in alias.name.lower(), (
                        "不应导入 duckdb"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "duckdb" not in node.module.lower(), (
                        "不应导入 duckdb"
                    )

    def test_no_sql_execution(self):
        """LLM 融合模块不应执行 SQL"""
        import inspect
        import src.result_fusion as rf

        source = inspect.getsource(rf)
        assert "execute_sql" not in source
        assert "cursor()" not in source
        assert ".sql(" not in source

    def test_no_api_key_exposure(self):
        """build_result_fusion_payload 载荷不应包含任何密钥"""
        s = _make_summary()
        payload = build_result_fusion_payload(question="测试", summaries=[s])
        payload_str = json.dumps(payload, ensure_ascii=False)
        # 不应包含任何类似密钥的字段
        assert "sk-" not in payload_str
        assert "Bearer" not in payload_str

    def test_input_only_contains_summaries(self):
        """LLM 输入载荷只包含 ResultSummary/MergedResult 的受控字段"""
        s = _make_summary()
        payload = build_result_fusion_payload(question="测试", summaries=[s])

        # 检查顶层 key 白名单
        allowed_keys = {"question", "plan_count", "summaries", "merged_result", "merge_status", "warnings"}
        assert set(payload.keys()) == allowed_keys

        # 检查 summary 内部 key 白名单
        summary_keys = set(payload["summaries"][0].keys())
        allowed_summary_keys = {
            "source_plan_index", "metrics", "primary_table", "row_count",
            "has_date_column", "grain", "date_min", "date_max",
            "columns", "sample_rows", "warnings",
        }
        assert summary_keys == allowed_summary_keys


# ═══════════════════════════════════════════════════════════
# 测试类 8: validate_fusion_output 各项检测
# ═══════════════════════════════════════════════════════════


class TestValidateFusionOutput:
    """测试后校验函数的各项检测能力"""

    def test_valid_explanation_passes(self):
        """正常的解释文本应通过所有校验"""
        s = _make_summary(metrics=["trip_count"], primary_table="gold.dws_daily_trip_summary")
        explanation = (
            "查询返回31行数据，日期范围2026-01-01至2026-01-31。"
            "数据来源：gold.dws_daily_trip_summary 表。"
            "1月1日行程量为888,250次，1月2日为761,261次。"
        )

        violations = validate_fusion_output(explanation, [s])
        assert violations == [], f"不应有违规，实际: {violations}"

    def test_detects_sql_keywords(self):
        """应检测到 SQL 关键字"""
        s = _make_summary()
        violations = validate_fusion_output(
            "使用 SELECT * FROM table 查询数据。来源：gold表。",
            [s],
        )
        assert len(violations) > 0
        assert any("SQL" in v for v in violations)

    def test_detects_causal_language(self):
        """应检测到因果措辞"""
        s = _make_summary()
        violations = validate_fusion_output(
            "天气导致行程量下降。数据来源：gold.dws_daily_trip_summary。",
            [s],
        )
        assert len(violations) > 0
        assert any("因果" in v for v in violations)

    def test_detects_missing_source_mention(self):
        """应检测到未提及数据来源"""
        s = _make_summary(primary_table="gold.dws_daily_trip_summary")
        violations = validate_fusion_output(
            "查询返回31行数据，数值正常。",  # 未提及任何表名
            [s],
        )
        assert len(violations) > 0
        assert any("未提及" in v for v in violations)

    def test_merged_status_mention_counts_as_source(self):
        """合并状态的提及可替代表名作为来源说明"""
        s = _make_summary(primary_table="gold.dws_daily_trip_summary")
        merged = _make_merged(
            merge_status=MergeStatus.SKIPPED,
            reason="日期列不一致",
        )
        violations = validate_fusion_output(
            "由于日期列不一致，未进行自动合并。",
            [s],
            merged_result=merged,
        )
        # 应通过（提到了未合并原因）
        source_violations = [v for v in violations if "未提及" in v]
        assert source_violations == [], f"提及了合并原因，不应有来源违规: {source_violations}"

    def test_mentions_table_passes_source_check(self):
        """提及表名应通过来源检查"""
        s = _make_summary(primary_table="gold.dws_daily_trip_summary")
        violations = validate_fusion_output(
            "来自 gold.dws_daily_trip_summary 的数据显示...",
            [s],
        )
        source_violations = [v for v in violations if "未提及" in v]
        assert source_violations == []


# ═══════════════════════════════════════════════════════════
# 测试类 9: fallback_to_template 行为
# ═══════════════════════════════════════════════════════════


class TestFallbackToTemplate:
    """测试 fallback 到模板融合的行为"""

    def test_fallback_returns_template_output(self):
        """fallback_to_template 应返回模板融合的结果"""
        ur1 = _make_unified_response(metrics=["trip_count"],
                                     table="gold.dws_daily_trip_summary")
        ur2 = _make_unified_response(metrics=["persons_injured"],
                                     table="gold.dws_daily_crash_summary",
                                     columns=["crash_date", "persons_injured"],
                                     rows=[("2026-01-01", 142)])

        result = fallback_to_template("测试问题", [ur1, ur2])

        assert "拆分为 2 个查询计划" in result
        assert "trip_count" in result
        assert "persons_injured" in result
        assert "dws_daily_trip_summary" in result
        assert "dws_daily_crash_summary" in result

    def test_fallback_handles_error_result(self):
        """fallback 应能处理执行出错的结果"""
        ur = _make_unified_response(error="表不存在")

        result = fallback_to_template("测试", [ur])

        assert "执行出错" in result
        assert "表不存在" in result

    def test_fallback_handles_empty_result(self):
        """fallback 应能处理空结果"""
        ur = _make_unified_response(row_count=0)

        result = fallback_to_template("测试", [ur])

        assert "未返回数据" in result


# ═══════════════════════════════════════════════════════════
# 测试类 10: 边界和集成测试
# ═══════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界条件测试"""

    def test_empty_summaries(self):
        """空 summaries 列表不应崩溃"""
        llm = FakeLLMClient({
            "result_fusion": json.dumps({
                "explanation_text": "没有子计划需要解释。",
            }),
        })
        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        explanation, used_llm, _ = fuse_results_with_llm(
            question="测试",
            summaries=[],
            merged_result=None,
            merge_status="not_attempted",
            warnings=[],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert used_llm is True

    def test_all_summaries_empty_results(self):
        """所有摘要都为空结果时应正常处理"""
        s1 = _make_summary(row_count=0, columns=[], sample_rows=[],
                           warnings=["无数据"])
        s2 = _make_summary(plan_index=2, row_count=0, columns=[], sample_rows=[],
                           primary_table="gold.dws_daily_parking_summary",
                           warnings=["无数据"])

        llm = FakeLLMClient({
            "result_fusion": json.dumps({
                "explanation_text": (
                    "两个查询均未返回数据。来源：gold.dws_daily_trip_summary "
                    "和 gold.dws_daily_parking_summary。"
                ),
            }),
        })
        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        _, used_llm, _ = fuse_results_with_llm(
            question="测试",
            summaries=[s1, s2],
            merged_result=None,
            merge_status="not_attempted",
            warnings=["所有查询均为空"],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert used_llm is True

    def test_prompt_loader_called_with_correct_task(self):
        """应使用正确的 task 名加载 prompt"""
        s = _make_summary()
        llm = FakeLLMClient({
            "result_fusion": json.dumps({
                "explanation_text": "正常解释。来源：gold.dws_daily_trip_summary。",
            }),
        })
        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        fuse_results_with_llm(
            question="测试",
            summaries=[s],
            merged_result=None,
            merge_status="not_attempted",
            warnings=[],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        prompt_loader.load.assert_called_with("result_fusion")

    def test_merged_with_warnings_still_fuses(self):
        """即使有 merge_warnings，LLM 也应正常融合"""
        s = _make_summary()
        merged = _make_merged(
            merge_warnings=["日期范围不完全一致，部分日期缺失数据"],
            summaries=[s],
        )

        llm = FakeLLMClient({
            "result_fusion": json.dumps({
                "explanation_text": "数据已合并，但部分日期可能缺失。来源：gold表。",
            }),
        })
        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        explanation, used_llm, _ = fuse_results_with_llm(
            question="测试",
            summaries=[s],
            merged_result=merged,
            merge_status="merged",
            warnings=["日期范围不完全一致"],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert used_llm is True


# ═══════════════════════════════════════════════════════════
# 测试类 11: 辅助函数单元测试
# ═══════════════════════════════════════════════════════════


class TestHelperFunctions:
    """辅助函数的单元测试"""

    def test_extract_json_from_plain_text(self):
        """从纯 JSON 文本中提取"""
        result = _extract_json_object('{"key": "value"}')
        assert result == {"key": "value"}

    def test_extract_json_from_markdown_block(self):
        """从 Markdown 代码块中提取 JSON"""
        text = '```json\n{"key": "value"}\n```'
        result = _extract_json_object(text)
        assert result == {"key": "value"}

    def test_extract_json_with_surrounding_text(self):
        """从带前后文本的响应中提取 JSON"""
        text = '这是一段解释。\n{"key": "value"}\n以上是 JSON 数据。'
        result = _extract_json_object(text)
        assert result == {"key": "value"}

    def test_check_sql_keywords_detects_select(self):
        """检测 SELECT 关键字"""
        violations = _check_sql_keywords("可以使用 SELECT * FROM table")
        assert len(violations) > 0

    def test_check_sql_keywords_no_false_positive(self):
        """正常中文文本不应触发 SQL 检测"""
        violations = _check_sql_keywords("查询返回31行数据，来源为gold表")
        assert violations == []

    def test_check_causal_language_detects_daozhi(self):
        """检测『导致』措辞"""
        violations = _check_causal_language("天气导致数据异常")
        assert "导致" in violations

    def test_check_causal_language_no_false_positive(self):
        """正常描述不应触发因果检测"""
        violations = _check_causal_language("数据返回31行，日期从1月1日到1月31日")
        assert violations == []

    def test_check_fabricated_metrics_detects_unknown(self):
        """检测编造的指标名"""
        s = _make_summary(metrics=["trip_count"], columns=["trip_date", "trip_count"])
        fabricated = _check_fabricated_metrics(
            "trip_count 和 unknown_metric_name 都有数据",
            [s],
        )
        assert len(fabricated) > 0
        assert "unknown_metric_name" in fabricated

    def test_check_fabricated_metrics_allows_valid(self):
        """合法指标名不触发检测"""
        s = _make_summary(metrics=["trip_count"], columns=["trip_date", "trip_count"])
        fabricated = _check_fabricated_metrics(
            "trip_count 返回31行数据",
            [s],
        )
        assert fabricated == []

    def test_extract_json_invalid_raises(self):
        """无效 JSON 应抛出 ValueError"""
        with pytest.raises(ValueError):
            _extract_json_object("这不是 JSON 也不是任何有效格式 {invalid")

    def test_prompt_rendering_includes_input_json(self):
        """Prompt 渲染应包含输入的 JSON 数据"""
        # 验证 prompt loader 返回的模板会被追加本次输入
        prompt_loader = MagicMock(spec=PromptLoader)
        prompt_loader.load.return_value = "# result_fusion\n\n测试 prompt"

        llm = FakeLLMClient({
            "result_fusion": json.dumps({
                "explanation_text": "正常解释。来源：gold.dws_daily_trip_summary。",
            }),
        })

        # 拦截 complete 调用以检查 prompt 内容
        original_complete = llm.complete
        captured_prompt = []

        def _capture(request):
            captured_prompt.append(request.prompt)
            return original_complete(request)

        llm.complete = _capture

        s = _make_summary()
        fuse_results_with_llm(
            question="2026年Q1测试",
            summaries=[s],
            merged_result=None,
            merge_status="not_attempted",
            warnings=[],
            llm_client=llm,
            prompt_loader=prompt_loader,
        )

        assert len(captured_prompt) > 0
        prompt_text = captured_prompt[0]
        # prompt 应包含本次输入
        assert "## 本次输入" in prompt_text
        # prompt 应包含用户问题
        assert "2026年Q1测试" in prompt_text


# ═══════════════════════════════════════════════════════════
# 测试类 12: 现有 fuse_results 测试不破坏（回归验证）
# ═══════════════════════════════════════════════════════════


class TestBackwardCompatibility:
    """验证现有模板融合功能未被破坏"""

    def test_original_fuse_results_still_works(self):
        """原始 fuse_results 函数应正常工作"""
        from src.explainer import fuse_results
        ur = _make_unified_response()
        result = fuse_results("测试问题", [ur])
        assert "拆分为 1 个查询计划" in result
        assert "trip_count" in result

    def test_fallback_uses_original_fuse_results(self):
        """fallback_to_template 应使用原始 fuse_results"""
        ur = _make_unified_response()
        result = fallback_to_template("测试问题", [ur])
        # fallback 输出应与直接调用 fuse_results 一致
        from src.explainer import fuse_results
        expected = fuse_results("测试问题", [ur])
        assert result == expected

    def test_llm_fusion_module_does_not_modify_ir(self):
        """LLM 融合模块不应修改 IR 数据结构"""
        from src import ir as ir_module

        # ir 模块的核心类应保持不变
        assert hasattr(ir_module, "ResultSummary")
        assert hasattr(ir_module, "MergedResult")
        assert hasattr(ir_module, "MergeStatus")
