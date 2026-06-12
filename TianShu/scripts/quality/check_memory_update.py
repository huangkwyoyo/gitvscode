"""
检查关键变更是否同步写入项目记忆层，并提供内容质量校验。

该脚本把 AGENTS.md 中的"变更传播规则"变成可执行门禁：
- 基础模式：检查关键变更是否伴随记忆文件更新（有没有写）
- 内容质量模式（--check-content）：检查记忆条目是否包含必填字段、达到最低长度、无复制粘贴（写得好不好）
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_DIR_NAME = PROJECT_ROOT.name

CRITICAL_PREFIXES = (
    "scripts/silver/",
    "sql/silver/",
    "scripts/quality/",
    "harness/",
    "docs/warehouse/database_design/",
    "docs/warehouse/data_dictionary/",
    "docs/warehouse/silver/",
    "docs/silver/",
    "docs/standards/",
)

MEMORY_PREFIX = "docs/memory/"
CORE_MEMORY_FILES = (
    "docs/memory/经验复盘.md",
    "docs/memory/风险清单.md",
    "docs/memory/规则来源索引.md",
)

# 每个复盘条目必须包含的字段（对应 AGENTS.md §13.4 的要求）
REQUIRED_FIELDS = [
    "日期",
    "来源问题",
    "根因",
    "风险",
    "规则",
]

# 治理体系新增的必填字段（置信等级、版本、状态）
GOVERNANCE_REQUIRED_FIELDS = [
    "置信等级",
    "版本",
    "状态",
]

# 结构化来源字段（至少填写 1 项）
STRUCTURED_SOURCE_FIELDS = [
    "来源文档",
    "来源 PR",
    "来源 Commit",
    "来源数据",
    "来源人工确认",
]

# 内容质量校验：每个条目最少行数（含新增的治理字段）
MIN_ENTRY_LINES = 8

# 来源追溯模式：条目中至少出现以下关键词之一，视为有来源标记
SOURCE_TRACE_KEYWORDS = [
    "git commit",
    "commit:",
    "ADR",
    "RISK-",
    "来源于",
    "来源：",
    "来自",
    "事故：",
    "问题发现于",
]

# 记忆复盘中常见的代码、状态、方法论术语，不属于数据库表字段。
NON_SCHEMA_IDENTIFIERS = {
    "try_cast",
    "try_strptime",
    "human_review",
    "post_silver_build",
    "build_crash_detail",
    "write_meta_comments",
    "alias_name",
    "review_status",
    "source_type",
}

# 历史复盘中作为"禁止凭空新增"的反例字段，不要求出现在 database_design 中。
EXAMPLE_ONLY_IDENTIFIERS = {
    "fine_amount",
    "payment_amount",
    "amount_due",
    "paid_amount",
    "revenue_amount",
}

# Bronze 原始字段：在记忆条目中被引用，但因 bronze_database_design.md 仅有表级概述、
# 缺少字段级清单而无法被交叉验证自动识别的已知字段。
# TODO: 长期方案是在 bronze_database_design 中补全 crash_merged 等常用表的字段清单，
#       或让交叉验证逻辑读取 DuckDB meta.source_columns 作为补充事实源。
BRONZE_RAW_IDENTIFIERS = {
    "crash_time",       # bronze.crash_merged 原始字段，格式为 "H:MM"（如 "2:39"）
}

# 数据库设计文档路径（用于交叉验证记忆条目中引用的表名和字段名）
DATABASE_DESIGN_FILES = (
    "docs/warehouse/database_design/bronze_database_design.md",
    "docs/warehouse/database_design/silver_database_design.md",
    "docs/warehouse/database_design/gold_database_design.md",
)

# 记忆条目中可能引用表名/字段名的模式
# 匹配反引号包裹的 schema.table 或 table 格式
SCHEMA_TABLE_PATTERN = re.compile(r"`([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)`")
# 匹配 "表名.字段名" 或 "schema.表名.字段名" 格式的自由文本引用
DOT_REF_PATTERN = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\b")


def load_database_design_schemas(project_root: Path) -> dict[str, set[str]]:
    """
    从所有数据库设计文档中提取已知的表名和字段名。

    返回字典：
    - "tables": 所有已知表名的集合（含 schema 前缀，如 silver.trip_detail）
    - "fields": 所有已知字段名的集合（如 trip_id, pickup_at, fare_amount）
    - "schemas": 所有已知 schema 名的集合（如 bronze, silver, gold）
    """
    known_tables: set[str] = set()
    known_fields: set[str] = set()
    known_schemas: set[str] = {"bronze", "silver", "gold", "meta"}  # 项目预定义

    for design_file in DATABASE_DESIGN_FILES:
        file_path = project_root / design_file
        if not file_path.exists():
            continue

        content = file_path.read_text(encoding="utf-8")

        # 提取当前文件对应的 schema（从内容或路径推断）
        if "bronze" in design_file:
            schema = "bronze"
        elif "silver" in design_file:
            schema = "silver"
        elif "gold" in design_file:
            schema = "gold"
        else:
            schema = None

        # 从表格行中提取英文表名（格式：| `schema.table_name` | ...）
        for match in re.finditer(r"\|\s*`([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)`\s*\|", content):
            name = match.group(1)
            if "." in name:
                known_tables.add(name)
                # 同时添加不含 schema 前缀的短表名
                short_name = name.split(".", 1)[1]
                known_tables.add(short_name)
            else:
                known_tables.add(name)
                if schema:
                    known_tables.add(f"{schema}.{name}")

        # 从正文说明和目录树中提取反引号包裹的表名，例如 `gold.dws_daily_trip_summary` 或 `dws_daily_trip_summary`。
        for match in re.finditer(r"`([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)`", content):
            name = match.group(1)
            short_name = name.split(".")[-1]
            if "." in name and name.split(".")[0] in known_schemas:
                known_tables.add(name)
                known_tables.add(short_name)
            elif short_name.startswith(("dim_", "fact_", "dws_", "ads_", "v_")):
                known_tables.add(short_name)
                if schema:
                    known_tables.add(f"{schema}.{short_name}")

        # 从文本中提取反引号包裹的标识符（可能是表名或字段名）
        for match in re.finditer(r"`([a-zA-Z_][a-zA-Z0-9_]*)`", content):
            name = match.group(1)
            # 跳过已知的 schema 名和 SQL 关键字
            if name.lower() in {"bronze", "silver", "gold", "meta", "select", "from", "where",
                                "join", "on", "and", "or", "not", "null", "as", "in",
                                "varchar", "integer", "bigint", "decimal", "double", "float",
                                "date", "timestamp", "boolean", "int", "text"}:
                continue
            # 如果看起来像字段名（snake_case，非全大写缩写），加入字段集合
            if re.match(r"^[a-z][a-z0-9_]*$", name) and "_" in name:
                known_fields.add(name)

        # 从表格标题行提取字段名（如 "英文字段名" 列或表头中的字段名）
        for match in re.finditer(r"\|\s*`?([a-z][a-z0-9_]*)`?\s*\|", content):
            name = match.group(1)
            if re.match(r"^[a-z][a-z0-9_]*$", name) and "_" in name:
                if name.lower() not in {"schema", "name", "type", "key", "source", "status"}:
                    known_fields.add(name)

    return {
        "tables": known_tables,
        "fields": known_fields,
        "schemas": known_schemas,
    }


def check_schema_cross_validation(
    entries: list[dict], project_root: Path
) -> tuple[list[str], list[str]]:
    """
    检查记忆条目中引用的表名和字段名是否在数据库设计文档中真实存在。

    返回 (cross_errors, cross_warnings)。
    - cross_errors: 引用了明确不存在的表名
    - cross_warnings: 引用了无法在 database_design 中找到的疑似字段名
    """
    schemas = load_database_design_schemas(project_root)
    cross_errors: list[str] = []
    cross_warnings: list[str] = []

    for entry in entries:
        rid = entry["rule_id"]
        full_text = entry["full_text"]

        # 提取反引号中看起来像 "schema.table" 或 "table" 的引用
        refs = SCHEMA_TABLE_PATTERN.findall(full_text)

        for ref in refs:
            # 跳过 SQL 关键字、数据类型等
            ref_lower = ref.lower()
            if ref_lower in {"bronze", "silver", "gold", "meta", "varchar", "integer",
                            "bigint", "decimal", "double", "float", "date", "timestamp",
                            "boolean", "int", "text", "select", "from", "where", "join",
                            "null", "as", "on", "and", "or", "not", "create", "table",
                            "insert", "delete", "update", "into", "values", "set",
                            "row_number", "over", "group", "by", "order", "limit",
                            "count", "sum", "avg", "min", "max", "having", "union"}:
                continue

            if ref_lower in NON_SCHEMA_IDENTIFIERS or ref_lower in EXAMPLE_ONLY_IDENTIFIERS or ref_lower in BRONZE_RAW_IDENTIFIERS:
                continue

            # 跳过明显的文件路径（含扩展名和路径分隔符）
            if any(ext in ref_lower for ext in (".py", ".md", ".yml", ".yaml", ".sql", ".xlsx", ".csv", ".duckdb", ".json", ".sh", ".txt")):
                continue

            # 跳过包含路径分隔符的引用（如 "scripts/quality/check_xxx.py"）
            if "/" in ref or "\\" in ref:
                continue

            # 检查是否是已知的表名
            if ref not in schemas["tables"]:
                # 检查是否是 "schema.table" 格式
                if "." in ref:
                    parts = ref.split(".")
                    schema_name = parts[0]
                    table_name = parts[-1]

                    # meta schema 下的表是 DuckDB 内置表，database_design 中没有单独文档，不报错
                    if schema_name == "meta":
                        continue

                    if schema_name in schemas["schemas"]:
                        # 是有效的 schema，检查表名
                        if table_name not in schemas["tables"] and ref not in schemas["tables"]:
                            cross_warnings.append(
                                f"[{rid}] 引用了疑似不存在的表：`{ref}`（未在 database_design 中找到）"
                            )
                    # 非标准 schema 前缀：可能是普通英文句子中的点号，不告警
                else:
                    # 短标识符（不含点号）：可能是字段名也可能是普通英文词
                    # 仅对看起来像明确的 schema.table 模式的引用告警
                    if ref not in schemas["fields"] and "_" in ref:
                        cross_warnings.append(
                            f"[{rid}] 引用的标识符未在 database_design 中找到：`{ref}`（如为字段名，请确认其来源）"
                        )

    return cross_errors, cross_warnings


def normalize_path(raw_path: str) -> str:
    """统一 git 输出路径，兼容仓库根目录和项目根目录两种相对路径"""
    path = raw_path.strip().strip('"').replace("\\", "/")
    if path.startswith(f"{PROJECT_DIR_NAME}/"):
        path = path[len(PROJECT_DIR_NAME) + 1 :]
    return path


def parse_porcelain_line(line: str) -> tuple[str, str] | None:
    """解析 git status --porcelain 的单行输出"""
    if not line.strip():
        return None
    status = line[:2]
    raw_path = line[3:].strip()
    if " -> " in raw_path:
        raw_path = raw_path.split(" -> ", 1)[1]
    return status, normalize_path(raw_path)


def load_changed_files(project_root: Path) -> list[tuple[str, str]]:
    """读取当前工作树中项目范围内的变更文件"""
    completed = subprocess.run(
        ["git", "status", "--porcelain", "-z", "--", "."],
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or "无法读取 git status")
    parsed: list[tuple[str, str]] = []
    entries = [item for item in completed.stdout.decode("utf-8", errors="replace").split("\0") if item]
    index = 0
    while index < len(entries):
        entry = entries[index]
        status = entry[:2]
        raw_path = entry[3:].strip()
        if status.startswith("R") or status.startswith("C"):
            index += 1
            if index < len(entries):
                raw_path = entries[index]
        parsed.append((status, normalize_path(raw_path)))
        index += 1
    return parsed


def parse_changed_file_args(values: list[str]) -> list[tuple[str, str]]:
    """为测试和 CI 显式传入变更文件清单"""
    parsed: list[tuple[str, str]] = []
    for value in values:
        if "::" in value:
            status, path = value.split("::", 1)
        else:
            status, path = "M", value
        parsed.append((status, normalize_path(path)))
    return parsed


def is_critical_path(path: str) -> bool:
    """判断路径是否属于需要写入记忆层的关键变更"""
    return any(path.startswith(prefix) for prefix in CRITICAL_PREFIXES)


def is_core_memory_update(status: str, path: str) -> bool:
    """只把核心 memory 文件的新增或修改视为有效复盘更新"""
    if path not in CORE_MEMORY_FILES:
        return False
    return "D" not in status


def check_memory_update(changed_files: list[tuple[str, str]]) -> tuple[bool, list[str], list[str]]:
    """检查关键变更是否伴随核心记忆文件更新"""
    critical = [path for _status, path in changed_files if is_critical_path(path)]
    memory_updates = [path for status, path in changed_files if is_core_memory_update(status, path)]
    return bool(critical and not memory_updates), critical, memory_updates


def parse_memory_entries(content: str) -> list[dict]:
    """从经验复盘文件中解析所有 RXXX 条目，返回条目列表"""
    entries: list[dict] = []
    # 按 "## R" 开头的标题切分条目
    parts = re.split(r"\n(?=## R\d+)", content)
    for part in parts:
        header_match = re.match(r"## (R\d+)[：:]\s*(.*)", part)
        if not header_match:
            continue
        rule_id = header_match.group(1)
        title = header_match.group(2).strip()
        body = part[header_match.end():].strip()
        # 提取字段列表项（以 "- 字段名：" 或 "- 字段名:" 开头）
        fields_found: dict[str, str] = {}
        all_check_fields = REQUIRED_FIELDS + GOVERNANCE_REQUIRED_FIELDS + STRUCTURED_SOURCE_FIELDS + ["验证记录", "废弃原因"]
        for field in all_check_fields:
            pattern = rf"- {field}[：:]\s*(.+)"
            match = re.search(pattern, body)
            if match:
                fields_found[field] = match.group(1).strip()
        entries.append({
            "rule_id": rule_id,
            "title": title,
            "body": body,
            "full_text": part.strip(),
            "found_fields": fields_found,
            "line_count": part.strip().count("\n") + 1,
        })
    return entries


def check_entry_quality(entries: list[dict]) -> tuple[list[str], list[str], list[str]]:
    """
    对解析出的记忆条目进行内容质量校验。

    返回三个列表：
    - errors: 必须修复的问题（缺少必填字段、内容过短、缺少治理字段、结构化来源为空）
    - warnings: 建议修复的问题（缺少来源追溯、置信等级过高）
    - duplicates: 疑似重复的条目对
    """
    errors: list[str] = []
    warnings: list[str] = []
    duplicates: list[str] = []

    for entry in entries:
        rid = entry["rule_id"]
        title = entry["title"]

        # 检查基础必填字段
        missing = [f for f in REQUIRED_FIELDS if f not in entry["found_fields"]]
        if missing:
            errors.append(
                f"[{rid}] {title}\n  → 缺少必填字段：{', '.join(missing)}"
            )

        # 检查治理必填字段（置信等级、版本、状态）
        missing_gov = [f for f in GOVERNANCE_REQUIRED_FIELDS if f not in entry["found_fields"]]
        if missing_gov:
            # 区分："完全没有任何治理字段"= 旧条目待迁移（warning）；
            #       "有部分治理字段但缺少某些"= 新条目填写不完整（error）
            has_any_gov = any(f in entry["found_fields"] for f in GOVERNANCE_REQUIRED_FIELDS)
            if has_any_gov:
                errors.append(
                    f"[{rid}] {title}\n  → 缺少治理必填字段：{', '.join(missing_gov)}（置信等级/版本/状态为必填，详见 变更复盘模板.md）"
                )
            else:
                warnings.append(
                    f"[{rid}] {title}\n  → [待迁移] 条目尚未适配新治理模板——建议补充：置信等级、版本、状态、结构化来源字段（详见 变更复盘模板.md）"
                )

        # 检查结构化来源字段（至少填写 1 项）
        source_fields_found = [
            f for f in STRUCTURED_SOURCE_FIELDS if f in entry["found_fields"]
        ]
        if not source_fields_found:
            has_any_gov = any(f in entry["found_fields"] for f in GOVERNANCE_REQUIRED_FIELDS)
            if has_any_gov:
                # 已适配新模板但缺少结构化来源 → error
                errors.append(
                    f"[{rid}] {title}\n  → 缺少结构化来源：至少需填写 1 项（{'/'.join(STRUCTURED_SOURCE_FIELDS)}）"
                )
            # 否则已在上一条件中输出"待迁移"warning，此处不再重复

        # 检查置信等级：初始写入时不得高于 L3（除非有交叉验证记录）
        confidence = entry["found_fields"].get("置信等级", "").strip()
        if confidence.startswith("L4") or confidence.startswith("L5"):
            # 检查验证记录字段是否有多源交叉验证
            verification = entry["found_fields"].get("验证记录", "")
            if "交叉验证" not in verification and "人工审核" not in verification:
                warnings.append(
                    f"[{rid}] {title}\n  → 置信等级为 {confidence}，但验证记录中未发现交叉验证或人工审核证据。初始写入时置信等级建议不超过 L3"
                )

        # 检查最低行数
        if entry["line_count"] < MIN_ENTRY_LINES:
            errors.append(
                f"[{rid}] {title}\n  → 内容过短（{entry['line_count']} 行，最低要求 {MIN_ENTRY_LINES} 行，含新增的治理字段）"
            )

        # 检查是否有来源追溯（来源问题字段内容太少视为不可追溯）
        source_text = entry["found_fields"].get("来源问题", "")
        has_source = (
            len(source_text) >= 20  # 来源问题描述足够详细
            or any(kw.lower() in entry["full_text"].lower() for kw in SOURCE_TRACE_KEYWORDS)
        )
        if not has_source:
            warnings.append(
                f"[{rid}] {title}\n  → 建议补充来源追溯（来源问题描述过短或缺少 ADR 编号/git commit/具体事故）"
            )

    # 检查重复（基于条目正文的相似度——完全相同即为重复）
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            if entries[i]["body"] and entries[j]["body"]:
                # 去除空白后对比
                if entries[i]["body"].strip() == entries[j]["body"].strip():
                    duplicates.append(
                        f"[{entries[i]['rule_id']}] 与 [{entries[j]['rule_id']}] 正文完全相同，疑似复制粘贴"
                    )

    return errors, warnings, duplicates


def load_memory_content(project_root: Path, memory_file: str) -> str | None:
    """读取指定记忆文件的完整内容"""
    file_path = project_root / memory_file
    if not file_path.exists():
        return None
    return file_path.read_text(encoding="utf-8")


def run_content_quality_check(project_root: Path) -> tuple[bool, list[str], list[str], list[str]]:
    """
    对所有核心记忆文件执行内容质量校验。

    返回 (失败, errors, warnings, duplicates)。
    """
    all_errors: list[str] = []
    all_warnings: list[str] = []
    all_duplicates: list[str] = []

    for memory_file in CORE_MEMORY_FILES:
        # 规则来源索引是表格格式，不适合条目解析，跳过
        if "规则来源索引" in memory_file:
            continue

        content = load_memory_content(project_root, memory_file)
        if content is None:
            all_errors.append(f"核心记忆文件不存在：{memory_file}")
            continue

        entries = parse_memory_entries(content)
        if not entries:
            # 文件存在但无条目（风险清单是表格格式，也跳过）
            if "风险清单" in memory_file:
                continue
            all_warnings.append(f"{memory_file} 中未找到任何 RXXX 条目")
            continue

        errors, warnings, duplicates = check_entry_quality(entries)

        # 交叉验证：检查条目中引用的表名/字段名是否在 database_design 中存在
        cross_errors, cross_warnings = check_schema_cross_validation(entries, project_root)

        for e in errors + cross_errors:
            all_errors.append(f"{memory_file}: {e}")
        for w in warnings + cross_warnings:
            all_warnings.append(f"{memory_file}: {w}")
        for d in duplicates:
            all_duplicates.append(f"{memory_file}: {d}")

    failed = len(all_errors) > 0
    return failed, all_errors, all_warnings, all_duplicates


def main() -> int:
    """运行 Memory Gate 检查"""
    parser = argparse.ArgumentParser(description="检查关键变更是否同步写入 docs/memory")
    parser.add_argument(
        "--check-content",
        action="store_true",
        help="同时校验记忆条目的内容质量（必填字段、最低长度、来源追溯、重复检测）",
    )
    parser.add_argument(
        "--content-only",
        action="store_true",
        help="仅运行内容质量校验，跳过变更关联检查（适用于定期巡检）",
    )
    parser.add_argument("--project-root", default=str(PROJECT_ROOT), help="项目根目录")
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="显式传入变更文件，格式为 path 或 STATUS::path，可重复传入",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root)
    exit_code = 0

    # ── 阶段一：变更关联检查（传统 Memory Gate）──
    if not args.content_only:
        changed_files = parse_changed_file_args(args.changed_file) if args.changed_file else load_changed_files(project_root)
        change_failed, critical, memory_updates = check_memory_update(changed_files)

        print("=" * 60)
        print("Memory Gate 检查 — 变更关联")
        print("=" * 60)
        if not critical:
            print("[OK] 未发现需要写入 docs/memory 的关键变更。")
        else:
            print("关键变更:")
            for path in critical:
                print(f"  - {path}")
            if memory_updates:
                print("已同步核心记忆文件:")
                for path in memory_updates:
                    print(f"  - {path}")
                print("[OK] 变更关联检查通过。")
            else:
                print("[FAIL] 关键变更未同步更新核心记忆文件。")
                print("请更新以下任一文件:")
                for path in CORE_MEMORY_FILES:
                    print(f"  - {path}")
                print()
                print("─" * 60)
                print("[*] 下一步操作（二选一）：")
                print()
                print("  A) 如果本次变更涉及新发现的问题/经验/规则：")
                print("     在对话中说「把这次经验写入记忆」，让 Agent 帮你更新记忆文件。")
                print("     更新完成后重新 git commit。")
                print()
                print("  B) 如果本次变更不涉及新经验（如纯重构、格式修正、注释调整）：")
                print("     在 commit message 中注明「无新增经验」，然后重新提交。")
                print()
                print("[!] Memory Gate 不会自动生成复盘内容——它只检测记忆文件是否被更新。")
                print("    Harness 的自动化在执行层（检查做了没），不在创建层（帮你写）。")
                print("    参考：AGENTS.md §13.4 记忆写入强制要求。")
                print("─" * 60)
                exit_code = 1

    # ── 阶段二：内容质量校验（可选，通过 --check-content 或 --content-only 触发）──
    if args.check_content or args.content_only:
        print()
        print("=" * 60)
        print("Memory Gate 检查 — 内容质量")
        print("=" * 60)

        content_failed, errors, warnings, duplicates = run_content_quality_check(project_root)

        if errors:
            print(f"\n[ERROR] 发现 {len(errors)} 个必须修复的问题：")
            for e in errors:
                print(f"  {e}")
            exit_code = 1
        else:
            print("\n[OK] 所有条目必填字段完整，内容长度达标。")

        if duplicates:
            print(f"\n[WARN] 发现 {len(duplicates)} 处疑似复制粘贴：")
            for d in duplicates:
                print(f"  {d}")

        if warnings:
            print(f"\n[INFO] {len(warnings)} 条改进建议：")
            for w in warnings:
                print(f"  {w}")

        if not errors and not duplicates and not warnings:
            print("[OK] 内容质量校验全部通过。")

    return exit_code


if __name__ == "__main__":
    # Windows 终端编码兼容：确保中文输出不乱码
    import io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
