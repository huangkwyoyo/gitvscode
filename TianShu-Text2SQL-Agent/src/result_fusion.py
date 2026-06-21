"""
LLM 结果融合解释器。

职责：
    将多个 ResultSummary / MergedResult 的结构化摘要输入 LLM，
    生成自然的中文解释文本。LLM 只接触受控摘要，不接触 SQL、
    DuckDB、API 密钥或原始大表数据。

设计约束（Phase 3B）：
    - LLM 不允许生成 SQL
    - LLM 不允许修改 SQLPlan
    - LLM 不允许决定是否 merge
    - LLM 不允许访问 DuckDB
    - LLM 不允许看到 API Key、环境变量、原始大表
    - LLM 输入只能是 ResultSummary / MergedResult 的受控摘要
    - LLM 输出只能是中文解释文本
    - LLM 不允许输出因果解释
    - LLM 失败时必须 fallback 到现有模板 fuse_results()
    - 不允许删除现有模板融合
"""

from __future__ import annotations

import json
import re
from typing import Any

from .explainer import fuse_results as _template_fuse_results
from .ir import (
    MergeStatus,
    MergedResult,
    ResultSummary,
    UnifiedResponse,
)
from .cross_domain_policy import CrossDomainDecision
from .llm import LLMClient, LLMRequest, PromptLoader


# ═══════════════════════════════════════════════════════════
# 公开接口
# ═══════════════════════════════════════════════════════════


def build_result_fusion_payload(
    question: str,
    summaries: list[ResultSummary],
    merged_result: MergedResult | None = None,
    merge_status: str = "",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """
    构建发送给 LLM 的受控输入载荷。

    只包含 ResultSummary / MergedResult 的结构化摘要数据，
    绝不包含原始 SQL、API 密钥、环境变量或大表数据。

    Args:
        question: 用户原始中文问题
        summaries: 每个子计划的 ResultSummary 列表
        merged_result: 合并结果（可能为 None）
        merge_status: 合并状态字符串（便捷字段）
        warnings: 全局警告信息

    Returns:
        JSON 可序列化的 dict，作为 LLM prompt 的输入部分
    """
    payload: dict[str, Any] = {
        "question": question,
        "plan_count": len(summaries),
        "summaries": [_summary_to_dict(s) for s in summaries],
        "merged_result": _merged_to_dict(merged_result) if merged_result else None,
        "merge_status": merge_status or (
            merged_result.merge_status.value if merged_result else "not_attempted"
        ),
        "warnings": list(warnings) if warnings else [],
    }
    return payload


def fuse_results_with_llm(
    question: str,
    summaries: list[ResultSummary],
    merged_result: MergedResult | None,
    merge_status: str,
    warnings: list[str] | None,
    llm_client: LLMClient,
    prompt_loader: PromptLoader,
    cross_domain_decision: CrossDomainDecision | None = None,
) -> tuple[str, bool, str | None]:
    """
    调用 LLM 进行结果融合解释。

    完整流程：
        1. build_result_fusion_payload() → 受控输入
        2. LLMClient.complete() → LLM 输出
        3. 从 LLM 输出中提取 explanation_text
        4. validate_fusion_output() → 后校验（含跨域策略合规检查）
        5. 校验通过 → 返回解释文本
        6. 校验失败 / 异常 → 返回 fallback 结果

    Args:
        question: 用户原始中文问题
        summaries: 每个子计划的 ResultSummary 列表
        merged_result: 合并结果（可能为 None）
        merge_status: 合并状态字符串
        warnings: 全局警告信息
        llm_client: LLM 客户端（需实现 LLMClient 协议）
        prompt_loader: Prompt 模板加载器
        cross_domain_decision: 跨域策略决策（可选，用于策略合规后校验）

    Returns:
        (explanation_text, used_llm, fallback_reason) 三元组：
        - explanation_text: 最终解释文本
        - used_llm: 是否使用了 LLM 输出
        - fallback_reason: 如果使用了 fallback，记录原因；否则为 None
    """
    # ── Step 1: 构建受控输入 ──
    try:
        payload = build_result_fusion_payload(
            question=question,
            summaries=summaries,
            merged_result=merged_result,
            merge_status=merge_status,
            warnings=warnings,
        )
    except Exception as exc:
        return (
            f"[LLM 融合输入构建失败，回退模板解释: {exc}]",
            False,
            f"build_payload 异常: {exc}",
        )

    # ── Step 2: 调用 LLM ──
    try:
        # 渲染 prompt
        template = prompt_loader.load("result_fusion")
        prompt = (
            f"{template}\n\n"
            "## 本次输入\n"
            "```json\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
            "```"
        )

        response = llm_client.complete(
            LLMRequest(
                task="result_fusion",
                prompt=prompt,
                metadata={"question": question},
            )
        )
        raw_output = response.content
    except Exception as exc:
        return (
            "[LLM 调用失败，回退模板解释]",
            False,
            f"LLM 调用异常: {exc}",
        )

    # ── Step 3: 提取 JSON 中的 explanation_text ──
    try:
        parsed = _extract_json_object(raw_output)
        explanation = parsed.get("explanation_text", "")
        if not explanation or not isinstance(explanation, str):
            return (
                "[LLM 输出缺少 explanation_text，回退模板解释]",
                False,
                "LLM 输出中未找到 explanation_text 字段",
            )
    except Exception as exc:
        return (
            "[LLM 输出 JSON 解析失败，回退模板解释]",
            False,
            f"JSON 解析异常: {exc}",
        )

    # ── Step 4: 后校验 ──
    violations = validate_fusion_output(
        explanation=explanation,
        summaries=summaries,
        merged_result=merged_result,
        cross_domain_decision=cross_domain_decision,
    )
    if violations:
        return (
            "[LLM 解释校验未通过，回退模板解释]",
            False,
            f"校验违规: {'; '.join(violations)}",
        )

    # ── Step 5: 校验通过 ──
    return (explanation, True, None)


def validate_fusion_output(
    explanation: str,
    summaries: list[ResultSummary],
    merged_result: MergedResult | None = None,
    cross_domain_decision: CrossDomainDecision | None = None,
) -> list[str]:
    """
    后校验 LLM 输出的中文解释文本。

    检查项：
        1. 不得包含 SQL 语句关键字
        2. 不得包含因果措辞（跨域策略禁止时严格执行）
        3. 不得编造未出现在输入中的指标名
        4. 必须提及数据来源表或未合并原因
        5. 不得违反跨域策略（如将罚款金额说成实际收入）

    Args:
        explanation: LLM 生成的中文解释文本
        summaries: 输入的 ResultSummary 列表（用于提取合法指标名/表名）
        merged_result: 合并结果（可选，用于检查是否提及合并原因）
        cross_domain_decision: 跨域策略决策（可选，用于策略合规校验）

    Returns:
        违规描述列表。空列表表示校验通过。
    """
    violations: list[str] = []

    # ── 校验 1: 禁止 SQL 关键字 ──
    sql_violations = _check_sql_keywords(explanation)
    if sql_violations:
        violations.append(f"包含 SQL 关键字: {', '.join(sql_violations)}")

    # ── 校验 2: 禁止因果措辞 ──
    causal_violations = _check_causal_language(explanation)
    if causal_violations:
        violations.append(f"包含因果措辞: {', '.join(causal_violations)}")

    # ── 校验 3: 禁止编造指标名 ──
    fabricated = _check_fabricated_metrics(explanation, summaries)
    if fabricated:
        violations.append(f"编造指标名: {', '.join(fabricated)}")

    # ── 校验 4: 必须提及数据来源或合并原因 ──
    if not _mentions_source_or_reason(explanation, summaries, merged_result):
        violations.append("未提及任何数据来源表或未合并原因")

    # ── 校验 5: 跨域策略合规检查 ──
    if cross_domain_decision is not None:
        policy_violations = _check_policy_compliance(
            explanation=explanation,
            decision=cross_domain_decision,
        )
        violations.extend(policy_violations)

    return violations


def fallback_to_template(
    question: str,
    unified_responses: list[UnifiedResponse],
) -> str:
    """
    回退到现有模板融合（explainer.fuse_results）。

    这是 LLM 融合失败时的安全兜底，保证用户始终能看到
    基于模板的结构化中文解释。

    Args:
        question: 用户原始中文问题
        unified_responses: 统一响应列表

    Returns:
        模板融合的中文解释文本
    """
    return _template_fuse_results(question, unified_responses)


# ═══════════════════════════════════════════════════════════
# 内部辅助函数
# ═══════════════════════════════════════════════════════════


def _summary_to_dict(s: ResultSummary) -> dict[str, Any]:
    """将 ResultSummary 转为 LLM 安全的 dict（精简版，只传必要字段）"""
    return {
        "source_plan_index": s.source_plan_index,
        "metrics": s.metrics,
        "primary_table": s.primary_table,
        "row_count": s.row_count,
        "has_date_column": s.has_date_column,
        "grain": s.grain,
        "date_min": s.date_min,
        "date_max": s.date_max,
        "columns": s.columns,
        "sample_rows": s.sample_rows[:5],  # 最多 5 行样本
        "warnings": s.warnings,
    }


def _merged_to_dict(m: MergedResult) -> dict[str, Any]:
    """将 MergedResult 转为 LLM 安全的 dict（精简版）"""
    return {
        "merge_status": m.merge_status.value,
        "merge_key": m.merge_key,
        "row_count": m.row_count,
        "columns": m.columns,
        "rows": m.rows[:50],  # 最多 50 行
        "reason": m.reason,
        "merge_warnings": m.merge_warnings,
    }


def _extract_json_object(text: str) -> dict[str, Any]:
    """
    从 LLM 输出中提取 JSON 对象。

    兼容以下格式：
        - 纯 JSON 文本
        - Markdown 代码块包裹的 JSON
        - 前后有其他文本的 JSON

    Raises:
        ValueError: 无法提取有效 JSON
    """
    # 尝试 1: 去除 Markdown 代码块标记
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # 找到第一个换行后的内容，去掉结尾的 ```
        lines = cleaned.split("\n")
        # 去掉开头的 ```json 或 ```
        if lines[0].startswith("```"):
            lines = lines[1:]
        # 去掉结尾的 ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    # 尝试 2: 直接解析
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 尝试 3: 在文本中查找 JSON 对象（从第一个 { 到最后一个 }）
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从 LLM 输出中提取 JSON: {text[:200]}...")


# ── SQL 关键字检测 ──

# 需要检测的 SQL 关键字（大小写不敏感）
_SQL_KEYWORDS_PATTERN = re.compile(
    r'\b(SELECT|FROM|WHERE|JOIN|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|'
    r'TRUNCATE|UNION|INTO|VALUES|SET|GRANT|REVOKE|EXECUTE|EXEC|'
    r'LEFT\s+JOIN|RIGHT\s+JOIN|INNER\s+JOIN|OUTER\s+JOIN|CROSS\s+JOIN|'
    r'GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|OFFSET|DISTINCT|'
    r'CREATE\s+TABLE|DROP\s+TABLE|ALTER\s+TABLE|'
    r'BEGIN|COMMIT|ROLLBACK)\b',
    re.IGNORECASE,
)


def _check_sql_keywords(text: str) -> list[str]:
    """检查文本中是否包含 SQL 关键字。返回匹配到的关键字列表。"""
    matches = _SQL_KEYWORDS_PATTERN.findall(text)
    # 去重并保持大小写原样
    seen: set[str] = set()
    result: list[str] = []
    for m in matches:
        upper = m.upper()
        if upper not in seen:
            seen.add(upper)
            result.append(m)
    return result


# ── 因果措辞检测 ──

# 因果措辞模式（中文）
_CAUSAL_PATTERNS = [
    "导致",
    "造成",
    "引起",
    "引发",
    "所致",
    "致使",
    "使得",
    "因而",
    "因此",
    "从而",
    "因果",
    "缘故",
    "归因",
    "诱因",
    "因为",
    "由于",
    "所以",
    "于是",
    "后果",
    "效应",
]

# 复合因果模式（需要两个词同时出现才算）
_CAUSAL_PAIRS = [
    ("因为", "所以"),
    ("由于", "因此"),
    ("由于", "所以"),
    ("之所以", "是因为"),
]


def _check_causal_language(text: str) -> list[str]:
    """检查文本中是否包含因果措辞。返回匹配到的措辞列表。"""
    violations: list[str] = []

    # 检查单个因果词
    for pattern in _CAUSAL_PATTERNS:
        if pattern in text:
            violations.append(pattern)

    # 检查因果词组（如"因为A所以B"）
    # 这个用正则匹配跨句子的因果结构
    causal_pair_pattern = re.compile(
        r'(因为|由于|之所以).*?(所以|因此|于是|因而)',
        re.DOTALL,
    )
    pair_matches = causal_pair_pattern.findall(text)
    for m in pair_matches:
        phrase = f"{m[0]}...{m[1]}"
        if phrase not in violations:
            violations.append(phrase)

    return violations


# ── 指标编造检测 ──

def _check_fabricated_metrics(
    text: str,
    summaries: list[ResultSummary],
) -> list[str]:
    """
    检查 LLM 输出中是否编造了未出现在输入中的指标名。

    从所有 ResultSummary 中收集合法的指标名和列名，
    然后检查文本中出现的疑似指标名是否都在合法集合中。

    注意：不做精确的 NLP 分析，只检查以英文单词形式出现的
    疑似指标名（snake_case 或 camelCase 格式）。
    """
    # 收集所有合法的指标名和列名
    valid_names: set[str] = set()
    for s in summaries:
        for m in s.metrics:
            valid_names.add(m.lower())
        for c in s.columns:
            valid_names.add(c.lower())
        # 也加入表名及其点分隔的各段
        if s.primary_table:
            table_lower = s.primary_table.lower()
            valid_names.add(table_lower)
            # 例如 "gold.dws_daily_trip_summary" → 也加入 "dws_daily_trip_summary"
            for part in table_lower.split("."):
                if part:
                    valid_names.add(part)

    # 在文本中提取疑似英文标识符（snake_case 或包含下划线的词）
    # 这是对指标名的粗略检测
    identifier_pattern = re.compile(r'\b([a-z][a-z0-9_]*[a-z0-9])\b', re.IGNORECASE)
    found = identifier_pattern.findall(text)

    fabricated: list[str] = []
    for word in found:
        word_lower = word.lower()
        # 只检查看起来像指标名的词（包含下划线且长度 > 5）
        if "_" in word_lower and len(word_lower) > 5:
            if word_lower not in valid_names:
                fabricated.append(word)

    return fabricated


# ── 来源提及检测 ──

def _mentions_source_or_reason(
    text: str,
    summaries: list[ResultSummary],
    merged_result: MergedResult | None,
) -> bool:
    """
    检查解释文本是否提及了数据来源表或未合并原因。

    要求：解释文本中至少出现一个来源表名，或提及合并/未合并的原因。

    边界：如果所有摘要都无数据（row_count==0 且无 primary_table），
    则宽松处理——只需提及"无数据"或"空"即可。
    """
    # 收集所有来源表名
    table_names: set[str] = set()
    has_any_data = False
    for s in summaries:
        if s.primary_table:
            has_any_data = True
            # 提取表名的简短形式
            table_names.add(s.primary_table.lower())
            parts = s.primary_table.split(".")
            if len(parts) > 1:
                table_names.add(parts[-1].lower())
        if s.row_count > 0:
            has_any_data = True

    # 边界：所有摘要都无有效数据 → 跳过来源检查
    if not has_any_data and not table_names:
        return True

    text_lower = text.lower()

    # 检查是否提到了表名
    for name in table_names:
        if name in text_lower:
            return True

    # 检查是否提到了合并/未合并原因
    if merged_result is not None:
        if merged_result.reason and merged_result.reason in text:
            return True
        if merged_result.merge_status == MergeStatus.MERGED:
            if "合并" in text or "对齐" in text or "merge" in text_lower:
                return True
        elif merged_result.merge_status in (MergeStatus.SKIPPED, MergeStatus.FAILED):
            if "未合并" in text or "未对齐" in text or "跳过" in text or "无法" in text:
                return True

    # 如果没有任何表名也没有提到合并原因，检查是否至少提到了"表"或"数据来源"
    if "表" in text or "数据来源" in text or "来自" in text:
        return True

    return False


# ── 跨域策略合规检测 ──

def _check_policy_compliance(
    explanation: str,
    decision: CrossDomainDecision,
) -> list[str]:
    """
    检查 LLM 输出是否违反跨域策略决策。

    检查项：
        1. 若 allow_causal_language=False，检查是否出现因果措辞（强化检测）
        2. 若 warnings 中含"标准罚款金额"，检查输出是否将其说成"收入"/"营收"
        3. 若 refusal=True，不应产生解释（调用方应已提前拦截）

    Args:
        explanation: LLM 生成的中文解释文本
        decision: 跨域策略决策

    Returns:
        违规描述列表。空列表表示合规。
    """
    violations: list[str] = []

    # ── 因果措辞强化检查 ──
    if not decision.allow_causal_language:
        causal = _check_causal_language(explanation)
        if causal:
            violations.append(
                f"跨域策略禁止因果语言，但输出包含: {', '.join(causal)}"
            )

    # ── 罚款金额不得说成实际收入 ──
    for warning in decision.warnings:
        if "不是实际收入" in warning or "标准罚款金额" in warning:
            # 检查输出是否将其描述为收入
            revenue_patterns = [
                "实际收入", "财政收入", "政府收入", "营收",
                "罚款收入", "罚没收入",
            ]
            for pattern in revenue_patterns:
                if pattern in explanation:
                    violations.append(
                        f"违反策略警告：将罚款金额描述为『{pattern}』，"
                        f"但 standard_fine_total 不是实际收入"
                    )
                    break
            # 只检查第一个罚款相关的 warning
            break

    return violations
