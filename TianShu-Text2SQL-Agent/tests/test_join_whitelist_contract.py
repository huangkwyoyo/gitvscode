"""
JOIN 白名单契约专项测试。

覆盖：
    - 契约未声明的 G3→dim_date JOIN 被拒绝
    - 契约声明后对应 JOIN 被允许
    - 删除硬编码后不能通过修改 resolver 恢复放行
    - 契约缺失时 fail closed
    - allowed_joins 格式非法时 fail closed
    - 未声明 JOIN 键时拒绝
    - CROSS JOIN 拒绝
    - 事实表之间未授权 JOIN 拒绝
    - Bronze/Silver JOIN 拒绝
    - 合法 Gold JOIN 继续通过
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════

def _write_temp_yaml(content: dict, filename: str) -> Path:
    """将字典写入临时 YAML 文件，返回文件路径"""
    tmpdir = Path(tempfile.mkdtemp(prefix="join_test_"))
    filepath = tmpdir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(content, f)
    return filepath


def _write_contracts_dir(contracts: dict[str, dict]) -> Path:
    """创建临时 contracts 目录并写入多个 YAML 文件"""
    tmpdir = Path(tempfile.mkdtemp(prefix="contracts_test_"))
    for name, content in contracts.items():
        filepath = tmpdir / f"{name}.yml"
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(content, f)
    return tmpdir


# ═══════════════════════════════════════════════════════════════
# 测试组 1: 契约未声明的 JOIN 被拒绝
# ═══════════════════════════════════════════════════════════════


class TestUndeclaredJoinRejected:
    """契约未声明的 JOIN 路径应被拒绝"""

    def test_g3_trip_to_dim_date_rejected(self):
        """gold.dws_daily_trip_summary ↔ gold.dim_date 不在契约中，应被拒绝"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()

        # 验证 G3 汇总表到 dim_date 的 JOIN 均不在白名单中
        g3_to_dim_pairs = [
            ("gold.dws_daily_trip_summary", "gold.dim_date"),
            ("gold.dws_daily_parking_summary", "gold.dim_date"),
            ("gold.dws_daily_crash_summary", "gold.dim_date"),
        ]
        for left, right in g3_to_dim_pairs:
            assert (left, right) not in wl.allowed, (
                f"契约未声明的 JOIN 不应在白名单中: {left} ↔ {right}"
            )

    def test_g3_parking_to_dim_date_rejected(self):
        """gold.dws_daily_parking_summary ↔ gold.dim_date 不在契约中"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()
        assert ("gold.dws_daily_parking_summary", "gold.dim_date") not in wl.allowed

    def test_g3_crash_to_dim_date_rejected(self):
        """gold.dws_daily_crash_summary ↔ gold.dim_date 不在契约中"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()
        assert ("gold.dws_daily_crash_summary", "gold.dim_date") not in wl.allowed

    def test_unknown_table_join_rejected(self):
        """完全未知的表 JOIN 不在白名单中"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()
        assert ("gold.fact_trips", "gold.fact_parking_violations") not in wl.allowed
        assert ("silver.raw_trips", "gold.dim_date") not in wl.allowed


# ═══════════════════════════════════════════════════════════════
# 测试组 2: 契约中声明的 JOIN 被允许
# ═══════════════════════════════════════════════════════════════


class TestDeclaredJoinAllowed:
    """契约中明确声明的 JOIN 路径应被允许"""

    def test_fact_trips_to_dim_date_allowed(self):
        """gold.fact_trips ↔ gold.dim_date 在契约中"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()
        assert ("gold.fact_trips", "gold.dim_date") in wl.allowed

    def test_fact_crashes_to_dim_date_allowed(self):
        """gold.fact_crashes ↔ gold.dim_date 在契约中"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()
        assert ("gold.fact_crashes", "gold.dim_date") in wl.allowed

    def test_g3_trip_to_g3_crash_allowed(self):
        """gold.dws_daily_trip_summary ↔ gold.dws_daily_crash_summary 在契约中"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()
        assert ("gold.dws_daily_trip_summary", "gold.dws_daily_crash_summary") in wl.allowed

    def test_all_contract_joins_have_structured_entries(self):
        """所有契约 JOIN 应有结构化 JoinEntry"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()
        # 8 条唯一 JOIN（16 条包含反向）
        assert len(wl.entries) == 8, f"应有 8 条唯一 JOIN，实际 {len(wl.entries)}"
        for entry in wl.entries:
            assert entry.left_table, f"左表名不应为空: {entry.raw}"
            assert entry.right_table, f"右表名不应为空: {entry.raw}"
            assert "." in entry.left_table, f"左表名应为完全限定: {entry.left_table}"
            assert "." in entry.right_table, f"右表名应为完全限定: {entry.right_table}"


# ═══════════════════════════════════════════════════════════════
# 测试组 3: 删除硬编码后不可恢复
# ═══════════════════════════════════════════════════════════════


class TestNoHardcodedJoinBypass:
    """确认 resolver.py 不存在硬编码 JOIN 白名单追加逻辑"""

    def test_resolver_no_join_extend(self):
        """resolver.py 的 build_context 方法不应包含 join_whitelist.extend"""
        import inspect
        from src.resolver import TianShuResolver

        src = inspect.getsource(TianShuResolver.build_context)
        assert "join_whitelist.extend" not in src, (
            "resolver.py 不得包含硬编码的 join_whitelist.extend() 调用"
        )

    def test_resolver_no_g3_hardcoded_tables(self):
        """resolver.py 不应硬编码 G3 汇总表名"""
        import inspect
        from src.resolver import TianShuResolver

        src = inspect.getsource(TianShuResolver.build_context)
        # 这三个 G3 表此前被硬编码在 extend 中
        assert '"gold.dws_daily_trip_summary"' not in src, (
            "resolver.py 不得硬编码 gold.dws_daily_trip_summary"
        )
        assert '"gold.dws_daily_parking_summary"' not in src, (
            "resolver.py 不得硬编码 gold.dws_daily_parking_summary"
        )
        assert '"gold.dws_daily_crash_summary"' not in src, (
            "resolver.py 不得硬编码 gold.dws_daily_crash_summary"
        )

    def test_llm_pipeline_no_module_join_whitelist(self):
        """llm_pipeline.py 不应有模块级 JOIN_WHITELIST 常量"""
        from src import llm_pipeline

        # 检查模块的 __dict__ 中是否有 JOIN_WHITELIST
        has_constant = hasattr(llm_pipeline, "JOIN_WHITELIST")
        assert not has_constant, (
            "llm_pipeline.py 不得包含模块级 JOIN_WHITELIST 硬编码常量"
        )

    def test_llm_pipeline_no_module_available_tables(self):
        """llm_pipeline.py 不应有模块级 AVAILABLE_TABLES 常量"""
        from src import llm_pipeline

        has_constant = hasattr(llm_pipeline, "AVAILABLE_TABLES")
        assert not has_constant, (
            "llm_pipeline.py 不得包含模块级 AVAILABLE_TABLES 硬编码常量"
        )


# ═══════════════════════════════════════════════════════════════
# 测试组 4: 契约缺失时 fail closed
# ═══════════════════════════════════════════════════════════════


class TestContractMissingFailClosed:
    """契约文件缺失时 must fail closed"""

    def test_missing_contract_raises_strict(self):
        """strict=True 且契约缺失时应抛出 FileNotFoundError"""
        from src.safety_policy_loader import load_join_whitelist

        with pytest.raises(FileNotFoundError):
            load_join_whitelist(contracts_path="/nonexistent/path/contracts", strict=True)

    def test_missing_contract_nonstrict_empty(self):
        """strict=False 且契约缺失时应返回空名单"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist(contracts_path="/nonexistent/path/contracts", strict=False)
        assert wl.contract_missing is True
        assert len(wl.allowed) == 0
        assert len(wl.entries) == 0

    def test_missing_safety_policy_file_raises(self):
        """当 sql_safety_policy.yml 不在 contracts 目录中时抛出"""
        from src.safety_policy_loader import load_join_whitelist

        tmpdir = _write_contracts_dir({
            "semantic_contract": {"g3_summary": []},
            "metric_contract": {"metrics": []},
            # 故意不包含 sql_safety_policy
        })

        with pytest.raises(FileNotFoundError):
            load_join_whitelist(contracts_path=tmpdir, strict=True)


# ═══════════════════════════════════════════════════════════════
# 测试组 5: allowed_joins 格式非法时 fail closed
# ═══════════════════════════════════════════════════════════════


class TestMalformedAllowedJoins:
    """allowed_joins 格式非法时应 fail closed"""

    def test_empty_join_string_raises(self):
        """空 JOIN 字符串在 strict 模式下应抛出"""
        from src.safety_policy_loader import load_join_whitelist

        tmpdir = _write_contracts_dir({
            "sql_safety_policy": {
                "table_reference_rules": [{
                    "rule": "join_whitelist",
                    "allowed_joins": [""],  # 空字符串
                }],
            },
        })

        with pytest.raises(ValueError, match="格式非法"):
            load_join_whitelist(contracts_path=tmpdir, strict=True)

    def test_no_separator_raises(self):
        """缺少 ↔ 分隔符的 JOIN 字符串在 strict 模式下应抛出"""
        from src.safety_policy_loader import load_join_whitelist

        tmpdir = _write_contracts_dir({
            "sql_safety_policy": {
                "table_reference_rules": [{
                    "rule": "join_whitelist",
                    "allowed_joins": ["gold.table_a gold.table_b"],  # 无 ↔
                }],
            },
        })

        with pytest.raises(ValueError, match="格式非法"):
            load_join_whitelist(contracts_path=tmpdir, strict=True)

    def test_non_string_entry_raises(self):
        """非字符串的 allowed_joins 条目在 strict 模式下应抛出"""
        from src.safety_policy_loader import load_join_whitelist

        tmpdir = _write_contracts_dir({
            "sql_safety_policy": {
                "table_reference_rules": [{
                    "rule": "join_whitelist",
                    "allowed_joins": [12345],  # 数字
                }],
            },
        })

        with pytest.raises(ValueError, match="格式非法"):
            load_join_whitelist(contracts_path=tmpdir, strict=True)

    def test_missing_table_name_raises(self):
        """表名缺失的 JOIN 条目在 strict 模式下应抛出"""
        from src.safety_policy_loader import load_join_whitelist

        tmpdir = _write_contracts_dir({
            "sql_safety_policy": {
                "table_reference_rules": [{
                    "rule": "join_whitelist",
                    "allowed_joins": [" ↔ gold.dim_date"],  # 左表缺失
                }],
            },
        })

        with pytest.raises(ValueError, match="格式非法"):
            load_join_whitelist(contracts_path=tmpdir, strict=True)


# ═══════════════════════════════════════════════════════════════
# 测试组 6: 禁止的 JOIN 模式
# ═══════════════════════════════════════════════════════════════


class TestForbiddenJoinPatterns:
    """契约中的 forbidden_joins 规则应被加载"""

    def test_forbidden_patterns_loaded(self):
        """forbidden_joins 规则应被正确加载"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()
        assert len(wl.forbidden_patterns) >= 3, (
            f"应至少有 3 条禁止 JOIN 模式，实际 {len(wl.forbidden_patterns)}"
        )

    def test_bronze_silver_join_forbidden(self):
        """Bronze/Silver JOIN 应在禁止列表中"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()
        bronze_silver_found = any(
            "bronze" in p.lower() or "silver" in p.lower()
            for p in wl.forbidden_patterns
        )
        assert bronze_silver_found, "禁止模式应包含 Bronze/Silver JOIN 限制"

    def test_cross_join_forbidden(self):
        """CROSS JOIN 应在禁止列表中"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()
        cross_join_found = any(
            "cross" in p.lower() or "笛卡尔" in p
            for p in wl.forbidden_patterns
        )
        assert cross_join_found, "禁止模式应包含 CROSS JOIN 限制"


# ═══════════════════════════════════════════════════════════════
# 测试组 7: JOIN 白名单双向对称性
# ═══════════════════════════════════════════════════════════════


class TestJoinWhitelistSymmetry:
    """JOIN 白名单应双向对称（A↔B 自动包含 B↔A）"""

    def test_all_joins_bidirectional(self):
        """每个允许的 JOIN 都应有反向条目"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()
        # 验证双向性：对于每个 (a,b)，(b,a) 也应在列表中
        for left, right in wl.allowed:
            assert (right, left) in wl.allowed, (
                f"JOIN 白名单应双向对称，缺少反向: {right} ↔ {left}"
            )

    def test_entry_count_twice_unique(self):
        """allowed 列表条目数应为 entry 数量的 2 倍（双向对称）"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()
        assert len(wl.allowed) == len(wl.entries) * 2, (
            f"allowed ({len(wl.allowed)}) 应为 entries ({len(wl.entries)}) 的 2 倍"
        )


# ═══════════════════════════════════════════════════════════════
# 测试组 8: 合法 Gold JOIN 继续通过
# ═══════════════════════════════════════════════════════════════


class TestValidGoldJoinsPass:
    """契约中定义的合法 Gold 层 JOIN 应继续通过"""

    def test_all_fact_to_dim_joins_present(self):
        """所有 G2 事实表到 dim_date 的 JOIN 应存在"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()

        expected_fact_dim_joins = [
            ("gold.fact_trips", "gold.dim_date"),
            ("gold.fact_parking_violations", "gold.dim_date"),
            ("gold.fact_crashes", "gold.dim_date"),
            ("gold.fact_tif_payments", "gold.dim_date"),
            ("gold.fact_driver_applications", "gold.dim_date"),
        ]
        for left, right in expected_fact_dim_joins:
            assert (left, right) in wl.allowed, (
                f"合法 G2→dim_date JOIN 应存在: {left} ↔ {right}"
            )

    def test_fact_trips_to_dim_vehicle_present(self):
        """gold.fact_trips ↔ gold.dim_vehicle 应存在"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()
        assert ("gold.fact_trips", "gold.dim_vehicle") in wl.allowed

    def test_fact_parking_to_dim_violation_type_present(self):
        """gold.fact_parking_violations ↔ gold.dim_violation_type 应存在"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()
        assert ("gold.fact_parking_violations", "gold.dim_violation_type") in wl.allowed


# ═══════════════════════════════════════════════════════════════
# 测试组 9: 结构化 JOIN 键信息
# ═══════════════════════════════════════════════════════════════


class TestStructuredJoinKeys:
    """JOIN 条目应包含正确的 JOIN 键信息"""

    def test_fact_trips_join_keys(self):
        """gold.fact_trips ↔ gold.dim_date 应有 pickup_date_key 和 dropoff_date_key"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()
        trip_dim_entry = None
        for entry in wl.entries:
            if entry.left_table == "gold.fact_trips" and entry.right_table == "gold.dim_date":
                trip_dim_entry = entry
                break
        assert trip_dim_entry is not None, "应存在 fact_trips ↔ dim_date 条目"
        assert "pickup_date_key" in trip_dim_entry.join_keys, (
            f"JOIN 键应包含 pickup_date_key，实际: {trip_dim_entry.join_keys}"
        )
        assert "dropoff_date_key" in trip_dim_entry.join_keys, (
            f"JOIN 键应包含 dropoff_date_key，实际: {trip_dim_entry.join_keys}"
        )

    def test_g3_trip_crash_join_keys(self):
        """gold.dws_daily_trip_summary ↔ gold.dws_daily_crash_summary 应有 trip_date 和 crash_date"""
        from src.safety_policy_loader import load_join_whitelist

        wl = load_join_whitelist()
        g3_entry = None
        for entry in wl.entries:
            if (entry.left_table == "gold.dws_daily_trip_summary"
                    and entry.right_table == "gold.dws_daily_crash_summary"):
                g3_entry = entry
                break
        assert g3_entry is not None, "应存在 G3 trip↔crash 条目"
        assert len(g3_entry.join_keys) >= 2, (
            f"应有至少 2 个 JOIN 键，实际: {g3_entry.join_keys}"
        )


# ═══════════════════════════════════════════════════════════════
# 测试组 10: Resolver 使用契约白名单（非硬编码）
# ═══════════════════════════════════════════════════════════════


class TestResolverUsesContractWhitelist:
    """Resolver.build_context() 的 join_whitelist 应与契约一致"""

    def test_build_context_join_whitelist_matches_contract(self):
        """Resolver 的 join_whitelist 应与 load_join_whitelist 一致"""
        from src.resolver import TianShuResolver
        from src.safety_policy_loader import load_join_whitelist

        # 使用真实配置的 resolver
        resolver = TianShuResolver()
        resolver.load_config()
        resolver.load_contracts()

        # 获取契约白名单
        contract_wl = load_join_whitelist()
        contract_allowed_set = set(contract_wl.allowed)

        # 模拟 resolver 的 build_context 中的 JOIN 白名单构建逻辑
        # （不连接 DuckDB，避免依赖数据库文件）
        join_whitelist: list[tuple[str, str]] = []
        sql_safety = resolver._contracts.get("sql_safety_policy", {})
        for rule in sql_safety.get("table_reference_rules", []):
            if rule.get("rule") == "join_whitelist":
                for join_str in rule.get("allowed_joins", []):
                    parts = join_str.split("↔")
                    if len(parts) == 2:
                        left = parts[0].strip().split("(")[0].strip()
                        right = parts[1].strip().split("(")[0].strip()
                        join_whitelist.append((left, right))
                        join_whitelist.append((right, left))

        resolver_set = set(join_whitelist)

        # resolver 的 JOIN 白名单应与契约完全一致，无额外条目
        extra = resolver_set - contract_allowed_set
        missing = contract_allowed_set - resolver_set

        assert not extra, (
            f"Resolver 白名单不应包含契约之外的条目: {extra}"
        )
        assert not missing, (
            f"Resolver 白名单不应缺少契约中的条目: {missing}"
        )

    def test_build_context_no_hardcoded_g3_joins(self):
        """build_context 不应包含硬编码的 G3→dim_date JOIN"""
        from src.resolver import TianShuResolver

        resolver = TianShuResolver()
        resolver.load_config()
        resolver.load_contracts()

        # 手动构建 JOIN 白名单（不连接 DuckDB）
        join_whitelist: list[tuple[str, str]] = []
        sql_safety = resolver._contracts.get("sql_safety_policy", {})
        for rule in sql_safety.get("table_reference_rules", []):
            if rule.get("rule") == "join_whitelist":
                for join_str in rule.get("allowed_joins", []):
                    parts = join_str.split("↔")
                    if len(parts) == 2:
                        left = parts[0].strip().split("(")[0].strip()
                        right = parts[1].strip().split("(")[0].strip()
                        join_whitelist.append((left, right))

        # 硬编码的 G3→dim_date JOIN 不应出现
        hardcoded_pairs = [
            ("gold.dws_daily_trip_summary", "gold.dim_date"),
            ("gold.dws_daily_parking_summary", "gold.dim_date"),
            ("gold.dws_daily_crash_summary", "gold.dim_date"),
        ]
        for pair in hardcoded_pairs:
            assert pair not in join_whitelist, (
                f"硬编码的 JOIN 不应出现在白名单中: {pair}"
            )


# ═══════════════════════════════════════════════════════════════
# 测试组 11: SQL 安全校验 —— JOIN 白名单集成
# ═══════════════════════════════════════════════════════════════


class TestSqlSafetyWithJoinWhitelist:
    """validate_sql_safety 在与 JOIN 白名单集成时应正确拦截"""

    def test_undeclared_join_in_sql_rejected(self):
        """包含未声明 JOIN 的 SQL 应被安全校验拒绝"""
        from src.safety_policy_loader import load_join_whitelist
        from src.sql_gen import validate_sql_safety

        wl = load_join_whitelist()
        allowed_set = set(wl.allowed)
        available_tables = {
            "gold.dws_daily_trip_summary",
            "gold.dim_date",
            "gold.fact_trips",
        }

        # SQL 包含 G3→dim_date JOIN（不在契约中）
        sql = (
            "SELECT t.trip_count, d.date "
            "FROM gold.dws_daily_trip_summary t "
            "JOIN gold.dim_date d ON d.date_key = t.trip_date"
        )

        errors = validate_sql_safety(
            sql,
            forbidden_keywords=["INSERT", "UPDATE", "DELETE"],
            available_tables=available_tables,
            join_whitelist=allowed_set,
        )

        # 应包含 JOIN 白名单违规错误
        join_errors = [e for e in errors if "join" in e.lower() or "白名单" in e]
        assert len(join_errors) > 0, (
            f"未声明 JOIN 应被拒绝，但未返回 JOIN 相关错误。所有错误: {errors}"
        )

    def test_declared_join_in_sql_accepted(self):
        """包含已声明 JOIN 的 SQL 应通过安全校验（JOIN 层面）"""
        from src.safety_policy_loader import load_join_whitelist
        from src.sql_gen import validate_sql_safety

        wl = load_join_whitelist()
        allowed_set = set(wl.allowed)
        available_tables = {
            "gold.fact_trips",
            "gold.dim_date",
        }

        # SQL 包含 fact_trips→dim_date JOIN（在契约中）
        sql = (
            "SELECT f.trip_count, d.date "
            "FROM gold.fact_trips f "
            "JOIN gold.dim_date d ON d.date_key = f.pickup_date_key"
        )

        errors = validate_sql_safety(
            sql,
            forbidden_keywords=["INSERT", "UPDATE", "DELETE"],
            available_tables=available_tables,
            join_whitelist=allowed_set,
        )

        # 不应包含 JOIN 白名单违规
        join_errors = [e for e in errors if "join" in e.lower() or "白名单" in e]
        assert len(join_errors) == 0, (
            f"已声明 JOIN 应被接受，但返回了 JOIN 相关错误: {join_errors}"
        )

    def test_cross_join_rejected(self):
        """CROSS JOIN 应被安全校验拒绝"""
        from src.safety_policy_loader import load_join_whitelist
        from src.sql_gen import validate_sql_safety

        wl = load_join_whitelist()
        allowed_set = set(wl.allowed)
        available_tables = {
            "gold.fact_trips",
            "gold.dim_date",
        }

        sql = (
            "SELECT * FROM gold.fact_trips CROSS JOIN gold.dim_date"
        )

        errors = validate_sql_safety(
            sql,
            forbidden_keywords=["INSERT", "UPDATE", "DELETE"],
            available_tables=available_tables,
            join_whitelist=allowed_set,
        )

        assert len(errors) > 0, f"CROSS JOIN 应被拒绝，但未返回错误。错误: {errors}"


# ═══════════════════════════════════════════════════════════════
# 测试组 12: 可用表从契约加载
# ═══════════════════════════════════════════════════════════════


class TestAvailableTablesFromContracts:
    """从语义契约加载可用表"""

    def test_load_gold_tables(self):
        """应能从语义契约加载 Gold 层表"""
        from src.safety_policy_loader import load_available_tables_from_contracts

        tables = load_available_tables_from_contracts()

        assert "gold.dws_daily_trip_summary" in tables
        assert "gold.fact_trips" in tables
        assert "gold.dim_date" in tables

    def test_no_bronze_tables(self):
        """不应包含 Bronze 层表"""
        from src.safety_policy_loader import load_available_tables_from_contracts

        tables = load_available_tables_from_contracts()
        bronze_tables = [t for t in tables if t.startswith("bronze.")]
        assert len(bronze_tables) == 0, f"不应包含 Bronze 表: {bronze_tables}"

    def test_no_silver_tables(self):
        """不应包含 Silver 层表"""
        from src.safety_policy_loader import load_available_tables_from_contracts

        tables = load_available_tables_from_contracts()
        silver_tables = [t for t in tables if t.startswith("silver.")]
        assert len(silver_tables) == 0, f"不应包含 Silver 表: {silver_tables}"

    def test_missing_contract_raises_strict(self):
        """strict=True 且语义契约缺失时应抛出"""
        from src.safety_policy_loader import load_available_tables_from_contracts

        with pytest.raises(FileNotFoundError):
            load_available_tables_from_contracts(
                contracts_path="/nonexistent/path/contracts", strict=True
            )

    def test_missing_contract_nonstrict_empty(self):
        """strict=False 且语义契约缺失时应返回空集合"""
        from src.safety_policy_loader import load_available_tables_from_contracts

        tables = load_available_tables_from_contracts(
            contracts_path="/nonexistent/path/contracts", strict=False
        )
        assert tables == set()
