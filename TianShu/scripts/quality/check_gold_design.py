"""
Gold 层数据库设计门禁检查。

建表前先检查 Gold 设计文档是否满足可落库条件：
1. 表清单和字段清单必须同时包含英文名与中文名。
2. 字段类型必须使用英文数据库类型。
3. 直接引用的 Silver 来源字段必须真实存在。
4. 正式字段表格不得出现翻译草稿或待确认中文名。
"""
import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from harness_config import load_harness_config

try:
    import duckdb
except ImportError:
    duckdb = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DESIGN = PROJECT_ROOT / "docs" / "warehouse" / "database_design" / "gold_database_design.md"

SILVER_FIELD_PATTERN = re.compile(r"`?silver\.([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)`?")
BRONZE_REFERENCE_PATTERN = re.compile(r"\bbronze\.", re.IGNORECASE)
ENGLISH_TYPE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*(\(\d+(,\d+)?\))?$")
PLACEHOLDER_PATTERN = re.compile(r"(待确认中文名|TODO|TBD|Google\s*翻译|LLM\s*翻译)", re.IGNORECASE)


@dataclass(frozen=True)
class MarkdownTable:
    """保存一个 Markdown 表格块"""

    line_no: int
    headers: list[str]
    rows: list[tuple[int, list[str]]]


def clean_cell(cell: str) -> str:
    """清理 Markdown 表格单元格中的格式符号"""
    return cell.strip().strip("`").strip()


def split_row(line: str) -> list[str]:
    """解析简单 Markdown 表格行"""
    return [clean_cell(cell) for cell in line.strip().strip("|").split("|")]


def is_separator(line: str) -> bool:
    """判断是否为 Markdown 表格分隔行"""
    stripped = line.strip().strip("|").strip()
    return bool(stripped) and all(set(part.strip()) <= {"-", ":"} for part in stripped.split("|"))


def parse_markdown_tables(content: str) -> list[MarkdownTable]:
    """解析文档中的连续 Markdown 表格块"""
    tables: list[MarkdownTable] = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if line.startswith("|") and next_line.startswith("|") and is_separator(next_line):
            headers = split_row(line)
            rows: list[tuple[int, list[str]]] = []
            table_start = i + 1
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                if not is_separator(lines[i]):
                    rows.append((i + 1, split_row(lines[i])))
                i += 1
            tables.append(MarkdownTable(table_start, headers, rows))
            continue
        i += 1
    return tables


def header_index(headers: list[str], name: str) -> int | None:
    """返回表头位置，缺失时返回 None"""
    try:
        return headers.index(name)
    except ValueError:
        return None


def load_silver_columns(db_path: Path) -> set[tuple[str, str]]:
    """读取 DuckDB 中 Silver 实表字段"""
    if duckdb is None:
        raise RuntimeError("duckdb 未安装，无法检查 Silver 来源字段")
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'silver'
            """
        ).fetchall()
        return {(str(table), str(column)) for table, column in rows}
    finally:
        conn.close()


def check_table_catalog(tables: list[MarkdownTable]) -> list[str]:
    """检查 Gold 表清单必须有中英文并列信息"""
    violations: list[str] = []
    for table in tables:
        english_idx = header_index(table.headers, "英文表名")
        chinese_idx = header_index(table.headers, "中文表名")
        if english_idx is None or chinese_idx is None:
            continue
        for line_no, cells in table.rows:
            if len(cells) <= max(english_idx, chinese_idx):
                continue
            english_name = cells[english_idx]
            chinese_name = cells[chinese_idx]
            if english_name.startswith("gold.") and not chinese_name:
                violations.append(f"第 {line_no} 行 Gold 表 `{english_name}` 缺少中文表名")
    return violations


def check_field_tables(tables: list[MarkdownTable], silver_columns: set[tuple[str, str]]) -> list[str]:
    """检查 Gold 字段表格的中文名、类型和来源字段"""
    violations: list[str] = []
    for table in tables:
        field_idx = header_index(table.headers, "英文字段名")
        chinese_idx = header_index(table.headers, "中文字段名")
        type_idx = header_index(table.headers, "类型")
        source_idx = header_index(table.headers, "来源字段")
        if field_idx is None:
            continue

        missing_headers = [
            name
            for name, idx in [("中文字段名", chinese_idx), ("类型", type_idx), ("来源字段", source_idx)]
            if idx is None
        ]
        if missing_headers:
            # 原则章节可能包含仅展示中英文名的示例表，不属于正式 Gold 字段设计。
            continue

        required_max_idx = max(field_idx, chinese_idx or 0, type_idx or 0, source_idx or 0)
        for line_no, cells in table.rows:
            if len(cells) <= required_max_idx:
                violations.append(f"第 {line_no} 行字段表列数不足")
                continue

            field_name = cells[field_idx]
            chinese_name = cells[chinese_idx]  # type: ignore[index]
            data_type = cells[type_idx]  # type: ignore[index]
            source_field = cells[source_idx]  # type: ignore[index]

            if not field_name:
                violations.append(f"第 {line_no} 行缺少英文字段名")
            if not chinese_name:
                violations.append(f"第 {line_no} 行 `{field_name}` 缺少中文字段名")
            elif PLACEHOLDER_PATTERN.search(chinese_name):
                violations.append(f"第 {line_no} 行 `{field_name}` 中文字段名仍是草稿或待确认")

            if not data_type or not ENGLISH_TYPE_PATTERN.fullmatch(data_type):
                violations.append(f"第 {line_no} 行 `{field_name}` 类型不是规范英文数据库类型: {data_type}")

            if BRONZE_REFERENCE_PATTERN.search(source_field):
                violations.append(f"第 {line_no} 行 `{field_name}` 来源字段直接引用 Bronze，Gold 必须基于 Silver")

            for table_name, column_name in SILVER_FIELD_PATTERN.findall(source_field):
                if (table_name, column_name) not in silver_columns:
                    violations.append(
                        f"第 {line_no} 行 `{field_name}` Silver 来源字段不存在: "
                        f"silver.{table_name}.{column_name}"
                    )
    return violations


def check_gold_design(design_path: Path, db_path: Path) -> list[str]:
    """运行 Gold 设计文档全部检查"""
    if not design_path.exists():
        return [f"Gold 设计文档不存在: {design_path}"]
    content = design_path.read_text(encoding="utf-8")
    tables = parse_markdown_tables(content)
    silver_columns = load_silver_columns(db_path)

    violations: list[str] = []
    violations.extend(check_table_catalog(tables))
    violations.extend(check_field_tables(tables, silver_columns))
    return violations


def main() -> int:
    """命令行入口"""
    config = load_harness_config()
    parser = argparse.ArgumentParser(description="Gold 层数据库设计门禁检查")
    parser.add_argument("--design", type=Path, default=DEFAULT_DESIGN, help="Gold 数据库设计文档路径")
    parser.add_argument("--db", type=Path, default=config.duckdb_path, help="DuckDB 数据库路径")
    args = parser.parse_args()

    try:
        violations = check_gold_design(args.design, args.db)
    except Exception as exc:
        print(f"[FAIL] Gold 设计门禁执行失败: {exc}")
        return 1

    if violations:
        print("[FAIL] Gold 设计门禁发现问题：")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("[OK] Gold 设计门禁检查通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
