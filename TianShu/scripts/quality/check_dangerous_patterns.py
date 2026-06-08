"""
危险模式扫描

扫描 Markdown 规划文档和 SQL 脚本中的已知危险写法。

规则来源：
- R002: DuckDB 禁用 DATE::INT（经验复盘 2026-06-07）
- R003: 主键禁用无序 ROW_NUMBER() OVER ()（经验复盘 2026-06-07）
- R004: 枚举值不得硬编码（经验复盘 2026-06-07）
- R006: 金额字段必须 DECIMAL

用法：python check_dangerous_patterns.py [--dir <扫描目录>]
"""
import argparse
import re
import sys
from pathlib import Path

from harness_config import load_harness_config


# (模式, 严重度, 消息, 来源经验)
DANGEROUS_PATTERNS: list[dict] = [
    {
        "id": "DP001",
        "pattern": re.compile(r"DATE::INT\b"),
        "severity": "ERROR",
        "message": "DuckDB 不支持 DATE::INT。请使用 strftime(date_col, '%Y%m%d')::INTEGER",
        "lesson": "经验复盘 2026-06-07：dim_date 的 DuckDB 日期转换",
        "files": ["*.md", "*.sql"],
    },
    {
        "id": "DP002",
        "pattern": re.compile(r"ROW_NUMBER\s*\(\s*\)\s*OVER\s*\(\s*\)"),
        "severity": "WARNING",
        "message": "ROW_NUMBER() OVER () 没有 ORDER BY，可能导致主键不稳定。"
                   "如果是生成代理主键，请使用 MD5 哈希替代。",
        "lesson": "经验复盘 2026-06-07：trip_id 无序ROW_NUMBER",
        "files": ["*.md", "*.sql"],
    },
    {
        "id": "DP003",
        "pattern": re.compile(
            r"\b(fine_amount|penalty_amount|interest_amount|"
            r"reduction_amount|payment_amount|amount_due)\b"
        ),
        "severity": "WARNING",
        "message": "检测到金额字段名。Bronze 的 parking_violations_all 中无金额字段。"
                   "请确认：(1) 此字段是否存在于 Bronze DESCRIBE？"
                   "(2) 如果不存在，是否标注为 derived？(3) 派生逻辑是否填写？",
        "lesson": "经验复盘 2026-06-07：parking_violation 虚构金额字段",
        "files": ["*.md"],
    },
    {
        "id": "DP004",
        "pattern": re.compile(r"EXTRACT\s*\(\s*DOW\s+FROM"),
        "severity": "WARNING",
        "message": "EXTRACT(DOW FROM ...) 在 DuckDB 中周日=0。"
                   "如果需要周一=1 的 ISO 标准，请使用 EXTRACT(ISODOW FROM ...)。",
        "lesson": "经验复盘 2026-06-07：dim_date 星期计算",
        "files": ["*.md", "*.sql"],
    },
    {
        "id": "DP005",
        "pattern": re.compile(r"FROM\s+bronze\.\w+", re.IGNORECASE),
        "severity": "WARNING",
        "message": "Gold 层 SQL 中检测到直接引用 Bronze 表。"
                   "根据 AGENTS.md 第6节：Gold 禁止跳过 Silver 直接引用 Bronze。",
        "lesson": "Gold 层规则：必须通过 Silver 引用数据",
        "files": ["*.sql"],
        "scopes": ["gold"],  # 仅在 gold 目录中检查
    },
]

DEFAULT_SCAN_DIRS = [
    "docs/silver",
    "scripts/silver",
    "sql",
    "docs/warehouse/database_design",
]

EXCLUDED_DIR_PARTS = {
    ".git",
    ".claude",
    ".pytest_cache",
    "__pycache__",
    "docs/memory",
}

EXCLUDED_FILES = {
    "Agent Memory + Warehouse Harness统一体系方案.md",
    "AGENTS.md",
    "PROJECT_STATUS.md",
}

NEGATIVE_CONTEXT_KEYWORDS = [
    "禁用",
    "禁止",
    "不得",
    "不支持",
    "不可用",
    "避免",
    "危险",
    "反例",
    "经验复盘",
    "已修复",
    "不包含",
    "不含",
    "无金额字段",
]


def scan_file(filepath: Path, pattern_def: dict) -> list[dict]:
    """扫描单个文件中的危险模式"""
    hits: list[dict] = []
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return hits

    for i, line in enumerate(content.split("\n"), 1):
        if should_ignore_line(line):
            continue
        match = pattern_def["pattern"].search(line)
        if match:
            hits.append({
                "file": str(filepath),
                "line": i,
                "content": line.strip()[:120],
                "match": match.group(),
                "pattern_id": pattern_def["id"],
                "severity": pattern_def["severity"],
                "message": pattern_def["message"],
                "lesson": pattern_def["lesson"],
            })
    return hits


def should_ignore_line(line: str) -> bool:
    """跳过规则说明、反例说明和已知禁止项说明"""
    stripped = line.strip()
    return any(keyword in stripped for keyword in NEGATIVE_CONTEXT_KEYWORDS)


def should_scan(filepath: Path, pattern_def: dict) -> bool:
    """判断此文件是否应被此模式扫描"""
    # 检查文件扩展名
    ext = filepath.suffix
    allowed = pattern_def.get("files", ["*.md"])
    if f"*{ext}" not in allowed:
        return False
    # 检查 scope 限制
    scopes = pattern_def.get("scopes", [])
    if scopes:
        path_str = str(filepath).lower()
        if not any(s in path_str for s in scopes):
            return False
    return True


def collect_scan_files(root: Path) -> list[Path]:
    """收集正式设计和实现目录中的 Markdown / SQL 文件"""
    files: list[Path] = []
    for rel_dir in DEFAULT_SCAN_DIRS:
        scan_root = root / rel_dir
        if not scan_root.exists():
            continue
        files.extend(scan_root.rglob("*.md"))
        files.extend(scan_root.rglob("*.sql"))

    result: list[Path] = []
    for f in files:
        path_text = str(f).replace("\\", "/")
        if any(part in path_text for part in EXCLUDED_DIR_PARTS):
            continue
        if f.name in EXCLUDED_FILES:
            continue
        result.append(f)
    return result


def main():
    config = load_harness_config()
    parser = argparse.ArgumentParser(description="危险模式扫描")
    parser.add_argument(
        "--dir",
        default=str(config.project_root),
        help="扫描根目录",
    )
    parser.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="输出格式",
    )
    args = parser.parse_args()

    root = Path(args.dir)
    all_hits: list[dict] = []

    # 只扫描正式设计与实现目录，避免规则说明文档中的反例造成误报
    all_files = collect_scan_files(root)

    for pattern_def in DANGEROUS_PATTERNS:
        for filepath in all_files:
            if should_scan(filepath, pattern_def):
                hits = scan_file(filepath, pattern_def)
                all_hits.extend(hits)

    # 按严重度分组
    errors = [h for h in all_hits if h["severity"] == "ERROR"]
    warnings = [h for h in all_hits if h["severity"] == "WARNING"]

    print("=" * 60)
    print("危险模式扫描")
    print("=" * 60)

    if errors:
        print(f"\n[ERROR] 错误 ({len(errors)} 个)：")
        for h in errors:
            print(f"  [{h['pattern_id']}] {h['file']}:{h['line']}")
            print(f"    {h['message']}")
            print(f"    来源: {h['lesson']}")

    if warnings:
        print(f"\n[WARN] 警告 ({len(warnings)} 个)：")
        for h in warnings:
            print(f"  [{h['pattern_id']}] {h['file']}:{h['line']}")
            print(f"    {h['message']}")

    if not all_hits:
        print("\n[OK] 未发现危险模式。")

    print(f"\n{'=' * 60}")
    print(f"总计: {len(errors)} 个错误, {len(warnings)} 个警告")

    if errors:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
