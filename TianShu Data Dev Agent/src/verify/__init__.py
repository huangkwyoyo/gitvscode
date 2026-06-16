"""
防线 2 规则引擎——7 项自动检查 + 交叉验证。

纯确定性代码，不调 LLM。从以下来源移植并扩展：
  - scripts/pipeline/layer5_validate.py：6 项检查逻辑
  - TianShu-Text2SQL-Agent/src/sql_gen.py：SQL 安全校验

检查项：
  #1 表/字段存在性  #2 安全黑名单  #3 表访问权限
  #4 JOIN 白名单    #5 样本执行    #6 结果质量
  #7 交叉验证（Phase 3 完整实现）
"""

from .checker import Validator
from .checks import (
    FORBIDDEN_KEYWORDS,
    check_table_existence,
    check_forbidden_keywords,
    check_table_permissions,
    check_join_whitelist,
    check_sample_execution,
    check_result_quality,
    check_cross_validation,
)
from .cross_validation import compare_results
from .report import make_success_report, make_fail_report

__all__ = [
    "Validator",
    "FORBIDDEN_KEYWORDS",
    "check_table_existence",
    "check_forbidden_keywords",
    "check_table_permissions",
    "check_join_whitelist",
    "check_sample_execution",
    "check_result_quality",
    "check_cross_validation",
    "compare_results",
    "make_success_report",
    "make_fail_report",
]
