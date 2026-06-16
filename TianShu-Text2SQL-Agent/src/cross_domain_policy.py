"""
跨域策略规则引擎 —— 明确跨域展示、合并、解释、因果边界。

职责：
    根据涉及的 Domain 组合和指标名，用纯规则（非 LLM、非 SQL）决定：
    - 是否允许并列展示
    - 是否允许 date merge
    - 是否允许因果语言
    - 是否需要反问
    - 是否应拒绝回答
    - 需要追加的警告信息

严格边界：
    1. 不允许 SQL 层跨表 JOIN
    2. 不允许修改 SQLPlan 生成逻辑
    3. 不允许 LLM 决定跨域策略
    4. 不允许自动因果解释
    5. 不允许把 traffic + safety 描述成因果关系
    6. 不允许把 standard_fine_total 说成实际收入
    7. 不允许访问未授权表字段
    8. 不允许改变 DuckDB read_only
    9. 不允许删除 result_merge 现有安全条件
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .ir import Domain, ResultSummary


# ═══════════════════════════════════════════════════════════
# CrossDomainDecision —— 策略评估结果
# ═══════════════════════════════════════════════════════════


@dataclass
class CrossDomainDecision:
    """
    跨域策略决策结果。

    由 CrossDomainPolicy.evaluate() 根据域组合和指标名生成，
    所有字段均为规则计算结果，不涉及 LLM 或数据库访问。
    """
    allow_display: bool = True
    """是否允许并列展示多个域的结果"""

    allow_result_merge: bool = True
    """是否允许对多域结果执行 date merge"""

    allow_causal_language: bool = False
    """是否允许在解释中使用因果措辞（跨域默认禁止）"""

    requires_clarification: bool = False
    """是否需要反问用户以澄清跨域意图"""

    refusal: bool = False
    """是否应拒绝回答（如涉及人员隐私字段）"""

    warnings: list[str] = field(default_factory=list)
    """需要追加到最终回答中的警告信息"""

    reason: str = ""
    """决策原因摘要（用于 trace 和调试）"""

    def to_dict(self) -> dict:
        """序列化为字典（供 trace / JSON 输出）"""
        return {
            "allow_display": self.allow_display,
            "allow_result_merge": self.allow_result_merge,
            "allow_causal_language": self.allow_causal_language,
            "requires_clarification": self.requires_clarification,
            "refusal": self.refusal,
            "warnings": list(self.warnings),
            "reason": self.reason,
        }


# ═══════════════════════════════════════════════════════════
# CrossDomainPolicy —— 规则引擎
# ═══════════════════════════════════════════════════════════


class CrossDomainPolicy:
    """
    跨域策略规则引擎。

    通过纯规则（非 LLM、非 SQL、非 DuckDB）评估跨域组合，
    决定展示、合并、解释、因果等方面的边界。

    用法：
        policy = CrossDomainPolicy()
        decision = policy.evaluate(
            domains=[Domain.TRAFFIC, Domain.SAFETY],
            metrics=["trip_count", "crash_count"],
        )
    """

    # ── 人员相关字段（涉及隐私，跨域出现时必须 refusal）──
    _PERSONNEL_FIELDS: set[str] = {
        "persons_injured",
        "persons_killed",
        "driver_id",
        "driver_name",
        "driver_license",
        "vehicle_owner",
        "plate_number",
    }

    # ── 罚款类指标（不是实际收入，必须加提示）──
    _FINE_METRICS: set[str] = {
        "standard_fine_total",
        "fine_amount",
        "penalty_amount",
        "parking_fine_total",
        "violation_fine_total",
    }

    def evaluate(
        self,
        domains: list[Domain],
        metrics: list[str] | None = None,
        summaries: list[ResultSummary] | None = None,
    ) -> CrossDomainDecision:
        """
        评估跨域组合的展示/合并/解释策略。

        Args:
            domains: 涉及的所有 Domain 枚举值（去重）
            metrics: 所有涉及的指标英文名（用于检测罚款/人员字段）
            summaries: ResultSummary 列表（可选，用于更深层的字段检查）

        Returns:
            CrossDomainDecision 包含所有策略决策和警告
        """
        unique_domains = list(set(domains))
        all_metrics = list(metrics) if metrics else []

        # ── 单域 → 宽松策略（无跨域风险）──
        if len(unique_domains) <= 1:
            return self._single_domain_decision(unique_domains, all_metrics)

        # ── 多域 → 交叉策略评估 ──
        return self._cross_domain_decision(unique_domains, all_metrics, summaries)

    # ═══════════════════════════════════════════════════════════
    # 单域策略
    # ═══════════════════════════════════════════════════════════

    def _single_domain_decision(
        self,
        domains: list[Domain],
        metrics: list[str],
    ) -> CrossDomainDecision:
        """单域场景：默认宽松，仅检查罚款类指标"""
        warnings: list[str] = []
        allow_causal = True  # 单域允许轻度因果

        # 罚款类指标提示（单域内也检查）
        fine_metrics_found = [m for m in metrics if m in self._FINE_METRICS]
        if fine_metrics_found:
            warnings.append(
                f"注意：{'、'.join(fine_metrics_found)} 为标准罚款金额，不是实际收入"
            )

        domain_str = domains[0].value if domains else "unknown"
        return CrossDomainDecision(
            allow_display=True,
            allow_result_merge=False,  # 单域无需 merge
            allow_causal_language=allow_causal,
            requires_clarification=False,
            refusal=False,
            warnings=warnings,
            reason=f"单域（{domain_str}），无跨域限制",
        )

    # ═══════════════════════════════════════════════════════════
    # 跨域策略
    # ═══════════════════════════════════════════════════════════

    def _cross_domain_decision(
        self,
        domains: list[Domain],
        metrics: list[str],
        summaries: list[ResultSummary] | None = None,
    ) -> CrossDomainDecision:
        """
        根据域组合匹配策略规则。

        规则优先级：
            1. 人员字段检测 → refusal
            2. unknown domain → clarification
            3. 特定域组合（traffic+safety, traffic+violation, violation+revenue）
            4. 默认保守策略
        """
        domain_set = set(domains)
        warnings: list[str] = []
        reasons: list[str] = []

        # ── 优先级 1: 人员字段检测 ──
        personnel_found = [m for m in metrics if m in self._PERSONNEL_FIELDS]
        if personnel_found:
            # 人员字段出现在跨域场景 → refusal
            if domain_set & {Domain.SUPPLY, Domain.ASSET}:
                return CrossDomainDecision(
                    allow_display=False,
                    allow_result_merge=False,
                    allow_causal_language=False,
                    requires_clarification=False,
                    refusal=True,
                    warnings=[],
                    reason=(
                        f"跨域查询涉及人员字段（{'、'.join(personnel_found)}），"
                        f"根据隐私保护策略拒绝回答"
                    ),
                )

        # 检查 summaries 中的 columns 是否有人员字段（更深层检测）
        if summaries and not personnel_found:
            for s in summaries:
                for col in s.columns:
                    col_lower = col.lower()
                    if any(pf in col_lower for pf in self._PERSONNEL_FIELDS):
                        personnel_found.append(col)
        if personnel_found and domain_set & {Domain.SUPPLY, Domain.ASSET}:
            return CrossDomainDecision(
                allow_display=False,
                allow_result_merge=False,
                allow_causal_language=False,
                requires_clarification=False,
                refusal=True,
                warnings=[],
                reason=(
                    f"跨域查询涉及人员字段（{'、'.join(personnel_found)}），"
                    f"根据隐私保护策略拒绝回答"
                ),
            )

        # ── 优先级 2: unknown domain → clarification ──
        has_unknown = any(
            d not in {Domain.TRAFFIC, Domain.SAFETY, Domain.VIOLATION,
                       Domain.SUPPLY, Domain.ASSET, Domain.SPATIAL}
            for d in domains
        )
        if has_unknown:
            return CrossDomainDecision(
                allow_display=False,
                allow_result_merge=False,
                allow_causal_language=False,
                requires_clarification=True,
                refusal=False,
                warnings=[],
                reason="存在未识别的业务域，需要反问用户确认查询意图",
            )

        # ── 优先级 3: 特定域组合策略 ──
        # traffic + safety
        if domain_set == {Domain.TRAFFIC, Domain.SAFETY}:
            warnings.append(
                "traffic 和 safety 数据来自不同业务系统，"
                "只能做同日期并列观察，不能推断因果关系（如『事故减少是因为出行减少』）"
            )
            reasons.append("traffic+safety 跨域：禁止因果语言，仅允许并列观察")
            return CrossDomainDecision(
                allow_display=True,
                allow_result_merge=True,  # 按 date daily 合并
                allow_causal_language=False,
                requires_clarification=False,
                refusal=False,
                warnings=warnings,
                reason="; ".join(reasons),
            )

        # traffic + violation
        if domain_set == {Domain.TRAFFIC, Domain.VIOLATION}:
            warnings.append(
                "traffic 和 violation 数据来自不同业务系统，"
                "只能做同日期并列观察，不能推断因果关系"
            )
            reasons.append("traffic+violation 跨域：禁止因果语言，仅允许并列观察")

            # 检查罚款类指标
            fine_found = [m for m in metrics if m in self._FINE_METRICS]
            if fine_found:
                warnings.append(
                    f"注意：{'、'.join(fine_found)} 是标准罚款金额，"
                    f"不是实际收入，不代表政府实际收到的罚款总额"
                )

            return CrossDomainDecision(
                allow_display=True,
                allow_result_merge=True,
                allow_causal_language=False,
                requires_clarification=False,
                refusal=False,
                warnings=warnings,
                reason="; ".join(reasons),
            )

        # safety + violation
        if domain_set == {Domain.SAFETY, Domain.VIOLATION}:
            warnings.append(
                "safety 和 violation 数据来自不同业务系统，"
                "只能做同日期并列观察，不能推断因果关系"
            )
            fine_found = [m for m in metrics if m in self._FINE_METRICS]
            if fine_found:
                warnings.append(
                    f"注意：{'、'.join(fine_found)} 是标准罚款金额，不是实际收入"
                )
            return CrossDomainDecision(
                allow_display=True,
                allow_result_merge=True,
                allow_causal_language=False,
                requires_clarification=False,
                refusal=False,
                warnings=warnings,
                reason="safety+violation 跨域：禁止因果语言",
            )

        # supply + trip (traffic)
        if domain_set & {Domain.SUPPLY, Domain.ASSET} and domain_set & {Domain.TRAFFIC}:
            # 涉及供给/资产 + 出行 → 检查是否有人员字段
            # 人员字段检查已在优先级 1 处理，此处作为兜底
            warnings.append(
                "供给/资产数据与出行数据来自不同系统，仅做并列展示"
            )
            return CrossDomainDecision(
                allow_display=True,
                allow_result_merge=True,
                allow_causal_language=False,
                requires_clarification=False,
                refusal=False,
                warnings=warnings,
                reason="supply/asset+traffic 跨域：允许展示，禁止因果，人员字段已检查",
            )

        # ── 优先级 4: 默认保守策略（未匹配的域组合）──
        # 对于未显式列出的域组合，采取保守策略：允许展示但禁止因果
        domain_names = [d.value for d in sorted(domains, key=lambda x: x.value)]
        return CrossDomainDecision(
            allow_display=True,
            allow_result_merge=True,
            allow_causal_language=False,  # 跨域默认禁止因果
            requires_clarification=False,
            refusal=False,
            warnings=[
                f"涉及多个业务域（{'、'.join(domain_names)}），"
                f"数据来自不同系统，仅做并列展示，不推断因果关系"
            ],
            reason=f"默认跨域策略（{'/'.join(domain_names)}）：允许展示，禁止因果",
        )

    # ═══════════════════════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def extract_domains_from_responses(
        unified_responses: list,
    ) -> list[Domain]:
        """
        从 UnifiedResponse 列表中提取所有涉及的 Domain。

        Args:
            unified_responses: UnifiedResponse 列表（含 sub_intent）

        Returns:
            去重后的 Domain 列表
        """
        domains: set[Domain] = set()
        for ur in unified_responses:
            if ur.sub_intent and ur.sub_intent.domain:
                domains.add(ur.sub_intent.domain)
        return list(domains)

    @staticmethod
    def extract_metrics_from_responses(
        unified_responses: list,
    ) -> list[str]:
        """
        从 UnifiedResponse 列表中提取所有涉及的指标名。

        Args:
            unified_responses: UnifiedResponse 列表（含 sub_intent）

        Returns:
            去重后的指标英文名列表
        """
        metrics: set[str] = set()
        for ur in unified_responses:
            if ur.sub_intent and ur.sub_intent.metrics:
                for m in ur.sub_intent.metrics:
                    metrics.add(m)
        return list(metrics)
