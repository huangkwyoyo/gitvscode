"""
请求安全预检查（Step 0.5）。

在进入意图分类之前，对所有用户请求执行写操作和禁用层检测。
rule 和 llm 模式共享同一检测路径，确保安全门禁不可绕过。

B-6 修复：统一写操作检测，覆盖中英文常见变体。
"""

from __future__ import annotations

# ── 写操作关键词（中英文全覆盖） ──
_WRITE_KEYWORDS_CN = [
    "删除", "删掉", "清空", "移除", "去掉",
    "更新", "修改", "改成", "改为", "变更",
    "插入", "写入", "新增", "添加", "追加",
    "覆盖", "替换", "改掉",
    "建表", "创建表", "删表", "drop表",
    "导入", "导出", "加载",
]

_WRITE_KEYWORDS_EN = [
    "delete", "drop", "truncate",
    "update", "insert", "merge", "replace",
    "alter", "create table", "create index",
    "grant", "revoke",
]

# ── 禁用层关键词 ──
_FORBIDDEN_LAYER_KEYWORDS = [
    "bronze", "silver",
    "原始表", "原始数据",
    "bronze层", "silver层",
    "ods", "staging",
]


def is_write_request(question: str) -> bool:
    """
    检测是否为写操作请求（中英文全覆盖）。

    在 Step 0.5 调用，命中后直接返回 refusal，
    不进入意图分类和 SQL 规划。

    Args:
        question: 用户的中文问题

    Returns:
        True 表示检测到写操作意图
    """
    lowered = question.lower()
    for word in _WRITE_KEYWORDS_CN:
        if word in question:
            return True
    for word in _WRITE_KEYWORDS_EN:
        if word in lowered:
            return True
    return False


def is_forbidden_layer_request(question: str) -> bool:
    """
    检测是否直接查询 Bronze/Silver 等禁用层。

    Args:
        question: 用户的中文问题

    Returns:
        True 表示检测到禁用层直接查询
    """
    lowered = question.lower()
    return any(kw in lowered for kw in _FORBIDDEN_LAYER_KEYWORDS)
