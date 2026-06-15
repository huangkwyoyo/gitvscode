"""
通用工具函数。

提供跨模块共享的辅助功能，避免代码重复。
"""
from __future__ import annotations

import sys


def setup_console_encoding() -> None:
    """
    设置控制台编码为 UTF-8，解决 Windows GBK 控制台下 emoji 字符输出崩溃问题。

    仅在 Windows 平台执行。Python 3.7+ 支持 sys.stdout.reconfigure()。
    如 reconfigure 失败（极老的 Python 或非标准 stdout），静默跳过。
    """
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore[attr-defined]
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')  # type: ignore[attr-defined]
        except Exception:
            # reconfigure 不可用（Python < 3.7 或非标准 stdout），使用替代方案
            pass
