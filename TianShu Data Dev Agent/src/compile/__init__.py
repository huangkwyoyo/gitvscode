"""
SQL 模板编译器——fallback 降级路径。

LLM 不可用或生成失败时的确定性编译路径。
封装 v1.x scripts/pipeline/layer4_generate.py 的 compile_sql()。
"""

from .engine import compile_fallback

__all__ = ["compile_fallback"]
