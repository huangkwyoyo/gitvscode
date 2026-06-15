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
