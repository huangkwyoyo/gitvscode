"""
SQL 安全策略统一加载器。

职责：
    从权威契约文件 contracts/sql_safety_policy.yml 加载禁止的 SQL 关键字，
    合并 config/agent_config.yml 中的 extra_forbidden_keywords，
    确保所有消费者使用同一份关键字列表，消除硬编码不一致。

C-2 修复的核心：契约是唯一权威源，契约缺失时 fail-closed（抛出异常而非静默回退）。

用法：
    from src.safety_policy_loader import load_forbidden_keywords

    keywords = load_forbidden_keywords()                        # 自动定位契约
    keywords = load_forbidden_keywords(contracts_path="...")    # 指定契约目录
    keywords = load_forbidden_keywords(strict=False)            # 测试模式（契约缺失时用内置回退）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# 契约定义的完整 19 个禁止关键字（与 contracts/sql_safety_policy.yml 保持同步）
# 用作 strict=False 时的回退值，以及验证契约加载完整性的基准
_EXPECTED_CONTRACT_KEYWORDS = sorted([
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
])


def _resolve_contracts_path(contracts_path: str | Path | None) -> Path:
    """
    解析 contracts/ 目录的绝对路径。

    优先级：
        1. 显式传入的 contracts_path
        2. 从 config/tianshu_target.yml 推断
    """
    if contracts_path is not None:
        return Path(contracts_path).resolve()

    # 从 config/tianshu_target.yml 读取 TianShu 项目路径
    agent_root = Path(__file__).resolve().parent.parent  # 项目根目录
    config_file = agent_root / "config" / "tianshu_target.yml"

    if not config_file.exists():
        raise FileNotFoundError(
            f"无法定位 TianShu 配置: {config_file}，"
            f"请显式传入 contracts_path 参数"
        )

    with open(config_file, "r", encoding="utf-8") as f:
        tianshu_config = yaml.safe_load(f)

    tianshu_rel = tianshu_config.get("tianshu", {}).get("project_root", "../TianShu")
    tianshu_root = (config_file.parent.parent / tianshu_rel).resolve()
    contracts_rel = tianshu_config.get("tianshu", {}).get("contracts_path", "contracts")

    return (tianshu_root / contracts_rel).resolve()


def _load_agent_config() -> dict[str, Any]:
    """加载 Agent 运行时配置（用于读取 extra_forbidden_keywords）"""
    agent_root = Path(__file__).resolve().parent.parent
    config_file = agent_root / "config" / "agent_config.yml"
    if not config_file.exists():
        return {}
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_forbidden_keywords(
    contracts_path: str | Path | None = None,
    agent_config: dict[str, Any] | None = None,
    strict: bool = True,
) -> list[str]:
    """
    从权威契约文件加载禁止的 SQL 关键字列表。

    加载来源（按优先级合并）：
        1. contracts/sql_safety_policy.yml → forbidden_operations[].keywords
        2. config/agent_config.yml → safety.extra_forbidden_keywords

    Args:
        contracts_path: contracts/ 目录路径，None 时自动从 config/tianshu_target.yml 推断
        agent_config: Agent 运行时配置字典，None 时自动加载 config/agent_config.yml
        strict: True = 契约缺失时抛出 FileNotFoundError（fail-closed）
                False = 契约缺失时使用 _EXPECTED_CONTRACT_KEYWORDS 作为回退（仅限测试环境）

    Returns:
        去重后的大写禁止关键字列表（按字母排序）

    Raises:
        FileNotFoundError: strict=True 且安全策略契约文件不存在
    """
    keywords: list[str] = []

    # ── 1. 从安全策略契约加载（权威源）──
    contracts_dir = _resolve_contracts_path(contracts_path)
    safety_file = contracts_dir / "sql_safety_policy.yml"

    if safety_file.exists():
        with open(safety_file, "r", encoding="utf-8") as f:
            safety_policy = yaml.safe_load(f)
        forbidden_ops = safety_policy.get("forbidden_operations", [])
        for op in forbidden_ops:
            keywords.extend(op.get("keywords", []))
    elif strict:
        raise FileNotFoundError(
            f"安全策略契约文件不存在: {safety_file}\n"
            f"C-2 安全约束：禁止在未加载契约的情况下运行。\n"
            f"请确认 TianShu 项目中的 contracts/sql_safety_policy.yml 文件存在。"
        )
    else:
        # 非严格模式：使用内置的完整 19 关键字列表作为回退
        # 注意：这不是"静默回退到不完整列表"，而是回退到与契约等价的完整列表
        keywords = list(_EXPECTED_CONTRACT_KEYWORDS)

    # ── 2. 合并 Agent 配置中的额外关键字 ──
    if agent_config is None:
        agent_config = _load_agent_config()
    extra = agent_config.get("safety", {}).get("extra_forbidden_keywords", [])
    keywords.extend(extra)

    # ── 3. 规范化：去重 + 大写 + 排序 ──
    seen: set[str] = set()
    unique: list[str] = []
    for kw in keywords:
        kw_upper = kw.upper().strip()
        if kw_upper and kw_upper not in seen:
            seen.add(kw_upper)
            unique.append(kw_upper)

    return sorted(unique)


def load_sql_safety_policy(
    contracts_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    加载完整的 SQL 安全策略契约（供需要更多策略细节的消费者使用）。

    Args:
        contracts_path: contracts/ 目录路径，None 时自动推断

    Returns:
        完整的 sql_safety_policy.yml 字典

    Raises:
        FileNotFoundError: 契约文件不存在
    """
    contracts_dir = _resolve_contracts_path(contracts_path)
    safety_file = contracts_dir / "sql_safety_policy.yml"

    if not safety_file.exists():
        raise FileNotFoundError(
            f"安全策略契约文件不存在: {safety_file}"
        )

    with open(safety_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ── JOIN 条目结构化表示 ──

@dataclass
class JoinEntry:
    """一条 JOIN 白名单规则的结构化表示。

    从 sql_safety_policy.yml 的 allowed_joins 文本条目解析而来。
    """
    left_table: str          # 左表完全限定名，如 "gold.fact_trips"
    right_table: str         # 右表完全限定名，如 "gold.dim_date"
    join_keys: list[str] = field(default_factory=list)  # JOIN 键列表，如 ["pickup_date_key"]
    raw: str = ""            # 原始契约文本行（用于错误报告）


@dataclass
class JoinWhitelist:
    """JOIN 白名单完整结构。

    包含允许的 JOIN 路径和禁止的 JOIN 模式。
    """
    allowed: list[tuple[str, str]] = field(default_factory=list)
    """允许的 JOIN 路径，每项为 (table_a, table_b) 元组（双向对称）"""
    entries: list[JoinEntry] = field(default_factory=list)
    """允许的 JOIN 结构化条目（含 JOIN 键信息）"""
    forbidden_patterns: list[str] = field(default_factory=list)
    """禁止的 JOIN 模式（从 forbidden_joins 规则解析）"""
    contract_missing: bool = False
    """契约文件是否缺失"""


def load_join_whitelist(
    contracts_path: str | Path | None = None,
    strict: bool = True,
) -> JoinWhitelist:
    """
    从权威契约文件加载 JOIN 白名单和禁止 JOIN 模式。

    仅从 contracts/sql_safety_policy.yml 的 table_reference_rules 段加载：
        - join_whitelist 规则 → allowed_joins 字段
        - forbidden_joins 规则 → forbidden 字段

    Args:
        contracts_path: contracts/ 目录路径，None 时自动从 config/tianshu_target.yml 推断
        strict: True = 契约缺失/格式非法时抛出异常（fail-closed）
                False = 契约缺失时返回空白名单（仅限测试环境）

    Returns:
        JoinWhitelist 包含 allowed、entries、forbidden_patterns 字段

    Raises:
        FileNotFoundError: strict=True 且契约文件不存在
        ValueError: allowed_joins 格式非法且 strict=True
    """
    contracts_dir = _resolve_contracts_path(contracts_path)
    safety_file = contracts_dir / "sql_safety_policy.yml"

    if not safety_file.exists():
        if strict:
            raise FileNotFoundError(
                f"安全策略契约文件不存在: {safety_file}\n"
                f"JOIN 白名单加载失败，无法验证 SQL 安全边界。\n"
                f"请确认 TianShu 项目中的 contracts/sql_safety_policy.yml 文件存在。"
            )
        return JoinWhitelist(contract_missing=True)

    with open(safety_file, "r", encoding="utf-8") as f:
        policy = yaml.safe_load(f) or {}

    allowed: list[tuple[str, str]] = []
    entries: list[JoinEntry] = []
    forbidden_patterns: list[str] = []

    for rule in policy.get("table_reference_rules", []):
        rule_name = rule.get("rule", "")

        if rule_name == "join_whitelist":
            for join_str in rule.get("allowed_joins", []):
                entry = _parse_join_entry(join_str)
                if entry is None:
                    if strict:
                        raise ValueError(
                            f"allowed_joins 格式非法，无法解析: '{join_str}'\n"
                            f"期望格式: 'schema.table_a ↔ schema.table_b (join_key)'\n"
                            f"契约文件: {safety_file}"
                        )
                    continue
                entries.append(entry)
                # 双向添加：允许 (a,b) 和 (b,a)
                pair = (entry.left_table, entry.right_table)
                allowed.append(pair)
                allowed.append((entry.right_table, entry.left_table))

        elif rule_name == "forbidden_joins":
            for fb_text in rule.get("forbidden", []):
                if fb_text and isinstance(fb_text, str):
                    forbidden_patterns.append(fb_text.strip())

    return JoinWhitelist(
        allowed=allowed,
        entries=entries,
        forbidden_patterns=forbidden_patterns,
    )


def _parse_join_entry(join_str: str) -> JoinEntry | None:
    """
    解析一条 JOIN 白名单文本条目为结构化 JoinEntry。

    支持格式：
        "gold.fact_trips ↔ gold.dim_date (pickup_date_key / dropoff_date_key)"
        "gold.fact_trips ↔ gold.dim_date (pickup_date_key)"
        "gold.dws_daily_trip_summary ↔ gold.dws_daily_crash_summary (trip_date = crash_date)"

    Args:
        join_str: 契约中的原始 JOIN 文本行

    Returns:
        JoinEntry 或 None（解析失败时）
    """
    if not join_str or not isinstance(join_str, str):
        return None

    join_str = join_str.strip()

    # 按 ↔ 分割
    parts = join_str.split("↔")
    if len(parts) != 2:
        return None

    left_part = parts[0].strip()
    right_part = parts[1].strip()

    # 提取表名和 JOIN 键
    left_table = _extract_table_name(left_part)
    right_table = _extract_table_name(right_part)
    join_keys = _extract_join_keys(join_str)

    if not left_table or not right_table:
        return None

    return JoinEntry(
        left_table=left_table,
        right_table=right_table,
        join_keys=join_keys,
        raw=join_str,
    )


def _extract_table_name(text: str) -> str:
    """从 'gold.fact_trips (pickup_date_key)' 中提取表名 'gold.fact_trips'"""
    text = text.strip()
    # 去掉括号内的 JOIN 键说明
    if "(" in text:
        text = text.split("(")[0].strip()
    return text


def _extract_join_keys(join_str: str) -> list[str]:
    """从 JOIN 文本中提取 JOIN 键列表"""
    keys: list[str] = []
    # 匹配括号中的内容
    import re
    match = re.search(r'\(([^)]+)\)', join_str)
    if match:
        content = match.group(1)
        # 按 / 或 = 分割
        for part in re.split(r'[/=]', content):
            key = part.strip()
            if key and not key.startswith("gold."):
                keys.append(key)
    return keys


def load_available_tables_from_contracts(
    contracts_path: str | Path | None = None,
    strict: bool = True,
) -> set[str]:
    """
    从语义契约加载可用表名集合（用于 SQL 安全校验中的表引用验证）。

    从 contracts/semantic_contract.yml 的 g3_summary、g2_facts、dimensions 段提取。

    Args:
        contracts_path: contracts/ 目录路径，None 时自动推断
        strict: True = 契约缺失时抛出异常

    Returns:
        完全限定表名的集合，如 {"gold.dws_daily_trip_summary", "gold.dim_date", ...}

    Raises:
        FileNotFoundError: strict=True 且契约文件不存在
    """
    contracts_dir = _resolve_contracts_path(contracts_path)
    semantic_file = contracts_dir / "semantic_contract.yml"

    if not semantic_file.exists():
        if strict:
            raise FileNotFoundError(
                f"语义契约文件不存在: {semantic_file}\n"
                f"无法加载可用表列表，拒绝执行。"
            )
        return set()

    with open(semantic_file, "r", encoding="utf-8") as f:
        semantic = yaml.safe_load(f) or {}

    tables: set[str] = set()
    for section in ("g3_summary", "g2_facts", "dimensions", "views", "meta"):
        for entry in semantic.get(section, []):
            table_name = entry.get("table", "")
            if table_name and "." in table_name:
                tables.add(table_name)

    return tables
