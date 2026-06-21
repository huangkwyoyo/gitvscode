"""
C-2 安全回归测试：禁止关键字硬编码绕过契约权威源。

验证 C-2 修复的三层保障：
    1. 统一加载器从契约正确加载 19 个禁止关键字
    2. 所有消费者使用统一加载器（无硬编码残留）
    3. 契约缺失时 fail-closed（strict=True 抛出异常）

19 个契约关键字（来自 contracts/sql_safety_policy.yml）：
    DML (6): INSERT, UPDATE, DELETE, MERGE, REPLACE, TRUNCATE
    DDL (4): CREATE, ALTER, DROP, RENAME
    DCL (2): GRANT, REVOKE
    危险 (4): ATTACH, DETACH, EXPORT, IMPORT
    系统 (3): COPY, INSTALL, LOAD
    + agent_config extras (2): PRAGMA, CHECKPOINT
    = 21 个（含 extras）
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from src.safety_policy_loader import (
    load_forbidden_keywords,
    load_sql_safety_policy,
    _EXPECTED_CONTRACT_KEYWORDS,
)


# ═══════════════════════════════════════════════════════════
# 常量定义
# ═══════════════════════════════════════════════════════════

# 契约定义的 19 个关键字（5 类）
CONTRACT_19_KEYWORDS = {
    # DML（6 个）
    "INSERT", "UPDATE", "DELETE", "MERGE", "REPLACE", "TRUNCATE",
    # DDL（4 个）
    "CREATE", "ALTER", "DROP", "RENAME",
    # DCL（2 个）
    "GRANT", "REVOKE",
    # 危险操作（4 个）
    "ATTACH", "DETACH", "EXPORT", "IMPORT",
    # 系统调用（3 个）
    "COPY", "INSTALL", "LOAD",
}

# agent_config.yml extras
AGENT_CONFIG_EXTRAS = {"PRAGMA", "CHECKPOINT"}

# 旧硬编码列表（仅用于验证它们已被消除）
OLD_LLM_PIPELINE_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE"}
OLD_E2E_EVAL_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "PRAGMA", "ATTACH", "DETACH"}


# ═══════════════════════════════════════════════════════════
# 测试辅助函数
# ═══════════════════════════════════════════════════════════


def _make_temp_contracts_dir(keywords: list[str] | None = None) -> Path:
    """创建临时 contracts 目录，包含 sql_safety_policy.yml"""
    tmpdir = Path(tempfile.mkdtemp(prefix="c2_test_"))
    if keywords is not None:
        policy = {
            "forbidden_operations": [
                {"category": "test", "keywords": keywords, "description": "测试"}
            ]
        }
        with open(tmpdir / "sql_safety_policy.yml", "w", encoding="utf-8") as f:
            yaml.dump(policy, f)
    return tmpdir


# ═══════════════════════════════════════════════════════════
# T1-T5: 统一加载器正确性
# ═══════════════════════════════════════════════════════════


class TestLoaderCorrectness:
    """load_forbidden_keywords() 的基本正确性"""

    def test_loads_all_19_contract_keywords(self):
        """T1: 从契约加载应包含全部 19 个关键字"""
        tmpdir = _make_temp_contracts_dir(sorted(CONTRACT_19_KEYWORDS))
        try:
            keywords = load_forbidden_keywords(
                contracts_path=tmpdir,
                agent_config={},  # 无 extras
            )
            loaded_set = set(keywords)
            # 验证所有 19 个关键字都在
            missing = CONTRACT_19_KEYWORDS - loaded_set
            assert not missing, f"缺失关键字: {sorted(missing)}"
            # 验证没有多余的关键字
            extra = loaded_set - CONTRACT_19_KEYWORDS
            assert not extra, f"多余关键字: {sorted(extra)}"
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_merges_extra_keywords_from_agent_config(self):
        """T2: agent_config extras 应被正确合并"""
        tmpdir = _make_temp_contracts_dir(sorted(CONTRACT_19_KEYWORDS))
        try:
            agent_config = {
                "safety": {
                    "extra_forbidden_keywords": ["CUSTOM_EXTRA", "ANOTHER_ONE"]
                }
            }
            keywords = load_forbidden_keywords(
                contracts_path=tmpdir,
                agent_config=agent_config,
            )
            assert "CUSTOM_EXTRA" in keywords
            assert "ANOTHER_ONE" in keywords
            # 原有 19 个应仍然在
            for kw in CONTRACT_19_KEYWORDS:
                assert kw in keywords, f"缺少关键字: {kw}"
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_keywords_are_uppercase_and_sorted(self):
        """T3: 返回的关键字应大写且字母排序"""
        tmpdir = _make_temp_contracts_dir(["insert", "Select", "DELETE", "create"])
        try:
            keywords = load_forbidden_keywords(
                contracts_path=tmpdir,
                agent_config={},
            )
            # 应去重并大写（INSERT 和 SELECT 已在契约中，但 SELECT 不在禁止列表中）
            # 实际上这里只验证格式
            for kw in keywords:
                assert kw == kw.upper(), f"关键字 {kw} 应大写"
            assert keywords == sorted(keywords), f"关键字应排序: {keywords}"
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_deduplicates_keywords(self):
        """T4: 重复关键字应被去重"""
        tmpdir = _make_temp_contracts_dir(["INSERT", "INSERT", "UPDATE"])
        try:
            keywords = load_forbidden_keywords(
                contracts_path=tmpdir,
                agent_config={"safety": {"extra_forbidden_keywords": ["INSERT"]}},
            )
            # INSERT 出现两次（contract + extra），应去重
            assert keywords.count("INSERT") == 1
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_empty_contract_returns_empty_or_extras_only(self):
        """T5: 空契约 + 空 extras → 空列表"""
        tmpdir = _make_temp_contracts_dir([])
        try:
            keywords = load_forbidden_keywords(
                contracts_path=tmpdir,
                agent_config={},
            )
            assert keywords == []
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════
# T6-T8: Fail-closed 行为
# ═══════════════════════════════════════════════════════════


class TestFailClosed:
    """契约缺失时的 fail-closed 行为"""

    def test_strict_mode_raises_when_contract_missing(self):
        """T6: strict=True 时，契约缺失必须抛出异常"""
        nonexistent = Path("/nonexistent/contracts/path")
        with pytest.raises(FileNotFoundError, match="安全策略契约文件不存在"):
            load_forbidden_keywords(contracts_path=nonexistent, strict=True)

    def test_non_strict_mode_returns_fallback_when_contract_missing(self):
        """T7: strict=False 时，契约缺失返回完整 19 关键字回退列表"""
        nonexistent = Path("/nonexistent/contracts/path")
        keywords = load_forbidden_keywords(contracts_path=nonexistent, strict=False)
        loaded_set = set(keywords)
        # 回退列表应包含全部 19 个关键字
        missing = CONTRACT_19_KEYWORDS - loaded_set
        assert not missing, f"回退列表缺失: {sorted(missing)}"

    def test_load_sql_safety_policy_always_strict(self):
        """T8: load_sql_safety_policy() 总是 fail-closed"""
        nonexistent = Path("/nonexistent/contracts/path")
        with pytest.raises(FileNotFoundError):
            load_sql_safety_policy(contracts_path=nonexistent)


# ═══════════════════════════════════════════════════════════
# T9-T10: 旧硬编码列表已被消除
# ═══════════════════════════════════════════════════════════


class TestNoHardcodedKeywords:
    """验证旧硬编码列表已被统一加载器替代"""

    def test_llm_pipeline_no_hardcoded_keywords(self):
        """T9: llm_pipeline 不再包含旧的 7 关键字硬编码常量"""
        import src.llm_pipeline as lp

        # 旧常量 FORBIDDEN_KEYWORDS 不应存在
        assert not hasattr(lp, "FORBIDDEN_KEYWORDS"), (
            "llm_pipeline 中不应存在硬编码的 FORBIDDEN_KEYWORDS 常量"
        )
        # 新函数 _get_forbidden_keywords 应存在
        assert hasattr(lp, "_get_forbidden_keywords"), (
            "llm_pipeline 应有 _get_forbidden_keywords 函数"
        )

    def test_e2e_eval_no_hardcoded_keywords(self):
        """T10: run_llm_e2e_eval 不再包含旧的 11 关键字硬编码常量"""
        from harness.run_llm_e2e_eval import E2ERunner

        # 旧常量 DEFAULT_FORBIDDEN_KEYWORDS 不应存在
        assert not hasattr(E2ERunner, "DEFAULT_FORBIDDEN_KEYWORDS"), (
            "E2ERunner 中不应存在硬编码的 DEFAULT_FORBIDDEN_KEYWORDS 常量"
        )
        # 新方法 _get_forbidden_keywords 应存在
        assert hasattr(E2ERunner, "_get_forbidden_keywords"), (
            "E2ERunner 应有 _get_forbidden_keywords 方法"
        )

    def test_llm_pipeline_loads_full_19_keywords(self):
        """T9 强化：llm_pipeline 加载的关键字应包含全部 19 个（不少于旧列表）"""
        import src.llm_pipeline as lp

        # 清理缓存以确保从契约重新加载
        lp._clear_forbidden_keywords_cache()
        keywords = lp._get_forbidden_keywords()
        keyword_set = set(keywords)

        # 旧列表的 7 个关键字应全部包含
        for kw in OLD_LLM_PIPELINE_KEYWORDS:
            assert kw in keyword_set, f"缺少旧列表中的关键字: {kw}"

        # 全部 19 个契约关键字应包含
        missing = CONTRACT_19_KEYWORDS - keyword_set
        assert not missing, f"缺失契约关键字: {sorted(missing)}"

    def test_e2e_eval_loads_full_19_keywords(self):
        """T10 强化：e2e_eval 加载的关键字应包含全部 19 个"""
        from harness.run_llm_e2e_eval import E2ERunner

        E2ERunner._clear_forbidden_keywords_cache()
        keywords = E2ERunner._get_forbidden_keywords()
        keyword_set = set(keywords)

        # 旧列表的 11 个关键字应全部包含
        for kw in OLD_E2E_EVAL_KEYWORDS:
            # PRAGMA 不在契约主体中，但在 extras 中
            if kw == "PRAGMA":
                assert kw in keyword_set, f"缺少 extras 中的关键字: {kw}"
            else:
                assert kw in keyword_set, f"缺少旧列表中的关键字: {kw}"

        # 全部 19 个契约关键字应包含
        missing = CONTRACT_19_KEYWORDS - keyword_set
        assert not missing, f"缺失契约关键字: {sorted(missing)}"


# ═══════════════════════════════════════════════════════════
# T11: 缓存机制
# ═══════════════════════════════════════════════════════════


class TestCaching:
    """加载器缓存行为"""

    def test_llm_pipeline_cache_returns_same_list(self):
        """两次调用应返回相同列表（缓存命中）"""
        import src.llm_pipeline as lp

        lp._clear_forbidden_keywords_cache()
        k1 = lp._get_forbidden_keywords()
        k2 = lp._get_forbidden_keywords()
        # 同一对象（缓存命中）
        assert k1 is k2

    def test_e2e_eval_cache_returns_same_list(self):
        """E2E 缓存行为"""
        from harness.run_llm_e2e_eval import E2ERunner

        E2ERunner._clear_forbidden_keywords_cache()
        k1 = E2ERunner._get_forbidden_keywords()
        k2 = E2ERunner._get_forbidden_keywords()
        assert k1 is k2


# ═══════════════════════════════════════════════════════════
# T12: _EXPECTED_CONTRACT_KEYWORDS 基准正确性
# ═══════════════════════════════════════════════════════════


class TestExpectedKeywordsBenchmark:
    """内置基准列表的完整性"""

    def test_expected_keywords_contains_19_items(self):
        """基准列表应包含恰好 19 个关键字"""
        assert len(_EXPECTED_CONTRACT_KEYWORDS) == 19, (
            f"基准列表应有 19 个关键字，实际 {len(_EXPECTED_CONTRACT_KEYWORDS)} 个"
        )

    def test_expected_keywords_matches_contract_set(self):
        """基准列表应与 CONTRACT_19_KEYWORDS 完全一致"""
        assert set(_EXPECTED_CONTRACT_KEYWORDS) == CONTRACT_19_KEYWORDS, (
            f"基准列表与契约不一致\n"
            f"  多余: {set(_EXPECTED_CONTRACT_KEYWORDS) - CONTRACT_19_KEYWORDS}\n"
            f"  缺失: {CONTRACT_19_KEYWORDS - set(_EXPECTED_CONTRACT_KEYWORDS)}"
        )
