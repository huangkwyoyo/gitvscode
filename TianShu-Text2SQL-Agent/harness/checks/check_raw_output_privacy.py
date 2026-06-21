"""Harness 检查：raw_output 失败记录的隐私安全。

验证：
- _save_raw_output_on_failure 默认不保存问题原文
- _safe_question_id 文件名不含问题文本
- _redact_pii 脱敏覆盖手机号/邮箱/身份证/车牌/API Key
- 写入失败不影响主查询（try/except 包围）
- 不提供 include_question: full 选项
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _get_source_lines(filepath: str) -> str:
    """读取源文件全部文本。"""
    return (PROJECT_ROOT / filepath).read_text(encoding="utf-8")


def check_question_not_saved_by_default() -> dict:
    """检查 _save_raw_output_on_failure 默认不保存完整问题文本。"""
    src = _get_source_lines("src/agent.py")

    # 应包含默认模式（never）的逻辑
    has_include_mode = 'include_mode = raw_cfg.get("include_question", "never")' in src
    has_never_branch = 'include_mode == "redacted"' in src
    has_structure_only = "length" in src and "char_categories" in src

    passed = has_include_mode and has_never_branch and has_structure_only
    violations = []
    if not has_include_mode:
        violations.append("缺少 include_question 配置读取")
    if not has_never_branch:
        violations.append("缺少 redacted/never 分支判断")
    if not has_structure_only:
        violations.append("默认模式未保存结构特征（length/char_categories）")

    return {
        "name": "默认不保存问题原文",
        "status": "PASS" if passed else "FAIL",
        "detail": "通过" if passed else "; ".join(violations),
    }


def check_filename_no_question_text() -> dict:
    """检查 _safe_question_id 文件名不含问题文本片段。"""
    src = _get_source_lines("src/agent.py")

    # 新实现：仅使用 SHA-256 哈希
    has_sha256 = "sha256" in src
    # 不应包含旧实现的文本截取逻辑
    has_old_text_slice = "question.strip())[:30]" in src

    passed = has_sha256 and not has_old_text_slice
    return {
        "name": "文件名不含问题文本",
        "status": "PASS" if passed else "FAIL",
        "detail": "仅使用 SHA-256 哈希" if has_sha256 else "文件名仍包含问题文本片段",
    }


def check_pii_redaction_completeness() -> dict:
    """检查 PII 脱敏覆盖手机号/邮箱/身份证/车牌/API Key。"""
    src = _get_source_lines("src/agent.py")

    required_patterns = {
        "手机号": r"1\[3-9\].*\\d\{9\}" if "1[3-9]" in src else False,
        "邮箱": "@" in src and "邮箱" in src,
        "身份证号": "身份证号" in src,
        "车牌号": "车牌号" in src,
        "API Key": "API_KEY" in src,
    }

    missing = [k for k, v in required_patterns.items() if not v]
    passed = len(missing) == 0
    return {
        "name": "PII 脱敏覆盖完整性",
        "status": "PASS" if passed else "FAIL",
        "detail": "全部覆盖" if passed else f"缺少脱敏规则: {', '.join(missing)}",
    }


def check_write_failure_isolated() -> dict:
    """检查写入失败被 try/except 隔离，不抛出异常。"""
    src = _get_source_lines("src/agent.py")

    # 定位 _save_raw_output_on_failure 方法
    method_start = src.find("def _save_raw_output_on_failure(")
    if method_start == -1:
        return {"name": "写入失败隔离", "status": "FAIL", "detail": "找不到方法"}

    # 取方法体（到下一个 def 或文件末尾）
    next_def = src.find("\n    def ", method_start + 1)
    method_body = src[method_start:next_def] if next_def != -1 else src[method_start:]

    has_try = "try:" in method_body
    has_except = "except Exception:" in method_body
    has_return_none = "return None" in method_body

    passed = has_try and has_except and has_return_none
    return {
        "name": "写入失败隔离",
        "status": "PASS" if passed else "FAIL",
        "detail": "try/except 包围" if passed else "缺少异常处理",
    }


def check_no_full_question_opt_in() -> dict:
    """检查不提供 include_question: full 选项。"""
    src = _get_source_lines("src/agent.py")

    # 源码中不应有 "full" 作为 include_question 的有效值
    has_full_option = 'include_question", "full"' in src or "include_question == 'full'" in src

    return {
        "name": "禁止全文保存问题",
        "status": "FAIL" if has_full_option else "PASS",
        "detail": "不存在 full 选项" if not has_full_option else "存在 full 选项（安全风险）",
    }


def run_checks() -> dict:
    """运行全部 raw_output 隐私检查。"""
    results = [
        check_question_not_saved_by_default(),
        check_filename_no_question_text(),
        check_pii_redaction_completeness(),
        check_write_failure_isolated(),
        check_no_full_question_opt_in(),
    ]
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    return {
        "checks": results,
        "pass_count": passed,
        "fail_count": failed,
    }


def main():
    """CLI 入口（兼容 Harness 框架）。"""
    results = run_checks()
    for check in results["checks"]:
        status_icon = "PASS" if check["status"] == "PASS" else "FAIL"
        print(f"[{status_icon}] {check['name']}: {check['detail']}")
    print(f"\n{results['pass_count']}/{len(results['checks'])} 通过")
    return 0 if results["fail_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
