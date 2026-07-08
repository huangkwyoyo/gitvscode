#!/usr/bin/env python3
"""
工程术语表自动更新脚本

功能：
  扫描 src/runtime_lab/ 中的 Python 代码，提取类名、函数名和模块名，
  与现有的工程术语文档交叉比对，报告未登记的术语。

用法：
  python scripts/update_glossary.py                      # 只报告缺失项
  python scripts/update_glossary.py --auto-add           # 自动追加模板条目
  python scripts/update_glossary.py --check              # CI 模式：有缺失则 exit 1
  python scripts/update_glossary.py --glossary <路径>    # 指定术语文档路径

设计原则：
  - 确定性扫描：相同代码始终产生相同结果
  - 渐进式更新：只报告新增项，不修改已有条目
  - 与生产隔离：不修改产品代码，只读取
"""

import ast
import os
import re
import sys
from pathlib import Path
from typing import Optional

# ── 路径配置 ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = PROJECT_ROOT / "src" / "runtime_lab"
DEFAULT_GLOSSARY = (
    PROJECT_ROOT
    / "docs"
    / "agent_runtime_engineering_glossary_20260708_1600.md"
)

# 不需要登记的代码元素（内部/私有/测试辅组）
SKIP_PATTERNS = re.compile(
    r"^(test_|_|__)|(_test|_pb2)$"
)

# 需要特别关注的 Python 语义关键字——这些通常代表核心概念
CONCEPT_PATTERNS = re.compile(
    r"(Node|State|Tool|Model|Policy|Store|Runtime|Graph|"
    r"CLI|App|Config|Report|Diff|Result|Gateway|Adapter|"
    r"Step|Plan|Contract|Validator|Executor|Pipeline)$"
)


def extract_glossary_terms(glossary_path: Path) -> set[str]:
    """解析术语文档，提取所有已登记的术语名称。

    格式：## N. TermName
    """
    if not glossary_path.exists():
        print(f"[WARN] 术语文档不存在: {glossary_path}")
        return set()

    terms: set[str] = set()
    term_pattern = re.compile(r"^##\s+\d+\.\s+(.+)$")

    with open(glossary_path, encoding="utf-8") as f:
        for line in f:
            m = term_pattern.match(line)
            if m:
                term_name = m.group(1).strip()
                # 跳过缩写表和标题行
                if term_name not in ("缩写速查",):
                    terms.add(term_name)

    return terms


def extract_code_elements(src_path: Path) -> dict[str, list[dict]]:
    """扫描源码目录，提取类名、函数名和模块名。

    返回：
        {
            "module_names": [{"name": "...", "file": "..."}, ...],
            "class_names": [{"name": "...", "file": "...", "bases": [...]}, ...],
            "function_names": [{"name": "...", "file": "..."}, ...],
            "concept_names": [{"name": "...", "file": "...", "kind": "class"}, ...],
        }
    """
    elements: dict[str, list[dict]] = {
        "module_names": [],
        "class_names": [],
        "function_names": [],
        "concept_names": [],
    }

    if not src_path.exists():
        print(f"[ERROR] 源码目录不存在: {src_path}")
        return elements

    for py_file in sorted(src_path.rglob("*.py")):
        # 跳过 __init__.py 和空的模块
        if py_file.name == "__init__.py":
            continue

        rel_path = py_file.relative_to(PROJECT_ROOT)

        try:
            with open(py_file, encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(py_file))
        except SyntaxError as e:
            print(f"[WARN] 文件语法错误 (跳过): {rel_path} — {e}")
            continue

        # 模块名（文件名去 .py，转驼峰为术语名）
        module_name = _filename_to_term(py_file.stem)
        if module_name and not SKIP_PATTERNS.match(py_file.stem):
            elements["module_names"].append({
                "name": module_name,
                "file": str(rel_path),
                "source": py_file.stem,
            })

        # 扫描 AST
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and not SKIP_PATTERNS.match(node.name):
                bases = [ _get_name(b) for b in node.bases if isinstance(b, ast.Name) ]
                entry = {"name": node.name, "file": str(rel_path), "bases": bases}
                elements["class_names"].append(entry)

                # 如果类名含概念关键词，记入 concept_names
                if CONCEPT_PATTERNS.search(node.name):
                    elements["concept_names"].append({
                        "name": node.name, "file": str(rel_path), "kind": "class",
                    })

            elif isinstance(node, ast.FunctionDef) and not SKIP_PATTERNS.match(node.name):
                entry = {"name": node.name, "file": str(rel_path)}
                elements["function_names"].append(entry)

                # 顶层函数（非方法，已在 ast.iter_child_nodes 过滤）中的概念函数
                if CONCEPT_PATTERNS.search(node.name):
                    elements["concept_names"].append({
                        "name": node.name, "file": str(rel_path), "kind": "function",
                    })

    return elements


def _filename_to_term(stem: str) -> str:
    """将 snake_case 文件名转换为术语名。

    sql_review_tools -> SQL Review Tools
    trace_store -> Trace Store
    """
    parts = stem.split("_")
    # 全大写缩写保持大写
    result = []
    for p in parts:
        if p.isupper() or (len(p) <= 3 and p.isalpha()):
            result.append(p.upper())
        else:
            result.append(p.capitalize())
    return " ".join(result)


def _get_name(node: ast.expr) -> str:
    """从 AST 节点提取名称"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return f"{_get_name(node.value)}[{_get_name(node.slice)}]"
    return "<expr>"


def detect_new_terms(
    glossary_terms: set[str],
    code_elements: dict,
    min_confidence: str = "medium",
) -> list[dict]:
    """检测代码中有但术语文档中未登记的术语。

    返回缺失术语列表（按置信度降序）：
        [
            {
                "term": "SQLReviewTools",
                "confidence": "high",
                "source_type": "module",
                "file": "src/runtime_lab/tools/sql_review_tools.py",
                "matched_code": "sql_review_tools",
            },
            ...
        ]
    """
    detected: list[dict] = []

    def _is_registered(term_name: str) -> bool:
        """判断术语是否已在文档中登记（模糊匹配）"""
        term_lower = term_name.lower()
        for gt in glossary_terms:
            # 精确匹配
            if gt.lower() == term_lower:
                return True
            # 核心词匹配（如 "Trace Store" 匹配 "追踪（Trace / Audit）"）
            gt_clean = re.sub(r"[（(].*?[）)]", "", gt).strip().lower()
            if gt_clean == term_lower or term_lower in gt_clean or gt_clean in term_lower:
                return True
            # 缩写匹配
            term_short = "".join(w[0] for w in term_name.split() if w[0].isalpha()).lower()
            gt_short = "".join(w[0] for w in gt_clean.split() if w[0].isalpha()).lower()
            if term_short and term_short == gt_short and len(term_short) >= 2:
                return True
        return False

    # 1. 高置信度：模块名 + 类名组合
    seen = set()
    for mod in code_elements.get("module_names", []):
        if _is_registered(mod["name"]):
            continue
        key = f"module:{mod['name']}"
        if key not in seen:
            seen.add(key)
            detected.append({
                "term": mod["name"],
                "confidence": "high",
                "source_type": "module",
                "file": mod["file"],
                "matched_code": mod["source"],
            })

    # 2. 中置信度：概念类名
    for cls in code_elements.get("concept_names", []):
        if _is_registered(cls["name"]):
            continue
        key = f"class:{cls['name']}"
        if key not in seen:
            seen.add(key)
            detected.append({
                "term": cls["name"],
                "confidence": "medium",
                "source_type": "class",
                "file": cls["file"],
                "matched_code": cls["name"],
            })

    return detected


def generate_template_entry(term: str, file_path: str) -> str:
    """为未登记的术语生成模板条目。"""
    # 从文件名推测术语描述
    file_stem = Path(file_path).stem
    term_lower = term.lower()
    safe_term = term.replace("_", " ")

    return f"""
## TBD. {safe_term}

**一句话解释**：（待补充——请根据 {file_path} 的实际功能填写）

**是什么**

（待补充——该术语在项目中的定义和用途）

**解决什么问题**

（待补充）

**在当前项目中的位置**

- `{file_path}` — TODO: 补充具体类的行号

**输入是什么**

（待补充）

**输出是什么**

（待补充）

**出错会导致什么风险**

（待补充）

**简单例子**

（待补充）

**Owner 审查时应该问什么**

（待补充）
"""


def update_glossary(
    glossary_path: Path,
    detected: list[dict],
    auto_add: bool = False,
) -> int:
    """输出检测结果，可选自动追加模板条目。

    返回：新增术语数量
    """
    if not detected:
        print("[OK] 未发现未登记的新术语，术语文档是最新的。")
        return 0

    print(f"\n{'='*60}")
    print(f"[!] 发现 {len(detected)} 个可能未登记的术语：")
    print(f"{'='*60}\n")

    for i, d in enumerate(detected, 1):
        confidence_tag = {
            "high": "[HIGH]",
            "medium": "[MED]",
            "low": "[LOW]",
        }.get(d["confidence"], "[LOW]")
        print(f"  {i}. {confidence_tag} {d['term']}")
        print(f"      类型: {d['source_type']}, 文件: {d['file']}")
        print()

    if auto_add:
        print(f"{'='*60}")
        print("[WRITE] 自动追加模板条目到术语文档...")
        print(f"{'='*60}\n")

        with open(glossary_path, "a", encoding="utf-8") as f:
            for d in detected:
                template = generate_template_entry(d["term"], d["file"])
                f.write(template)
                f.write("\n---\n")

        print(f"[OK] 已追加 {len(detected)} 个模板条目到 {glossary_path}")
        print("[WARN] 请手动填写每个模板的 **是什么** / **解决什么问题** 等字段。\n")

    return len(detected)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="工程术语表自动更新脚本 — 扫描代码并比对术语文档",
    )
    parser.add_argument(
        "--glossary",
        default=str(DEFAULT_GLOSSARY),
        help=f"术语文档路径（默认: {DEFAULT_GLOSSARY}）",
    )
    parser.add_argument(
        "--src",
        default=str(DEFAULT_SRC),
        help=f"源码目录路径（默认: {DEFAULT_SRC}）",
    )
    parser.add_argument(
        "--auto-add",
        action="store_true",
        help="自动追加未登记术语的模板条目到术语文档",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="CI 模式：有未登记术语时 exit 1",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示详细扫描信息",
    )

    args = parser.parse_args()

    glossary_path = Path(args.glossary)
    src_path = Path(args.src)

    # 解析术语文档
    glossary_terms = extract_glossary_terms(glossary_path)
    if args.verbose:
        print(f"术语文档中已登记 {len(glossary_terms)} 个术语：")
        for t in sorted(glossary_terms):
            print(f"  - {t}")
        print()

    # 扫描源码
    code_elements = extract_code_elements(src_path)
    if args.verbose:
        for category, items in code_elements.items():
            print(f"代码中发现 {len(items)} 个 {category}：")
            for item in items:
                print(f"  - {item['name']} ({item['file']})")
        print()

    # 检测新术语
    detected = detect_new_terms(glossary_terms, code_elements)
    count = update_glossary(glossary_path, detected, auto_add=args.auto_add)

    if args.check and count > 0:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
