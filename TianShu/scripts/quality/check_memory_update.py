"""
检查关键变更是否同步写入项目记忆层。

该脚本把 AGENTS.md 中的“变更传播规则”变成可执行门禁：
只要本次变更触及 Silver 构建、质量脚本、数据库设计或字段字典，就必须同步更新 docs/memory。
"""
from __future__ import annotations

import argparse
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


def main() -> int:
    """运行 Memory Gate 检查"""
    parser = argparse.ArgumentParser(description="检查关键变更是否同步写入 docs/memory")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT), help="项目根目录")
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="显式传入变更文件，格式为 path 或 STATUS::path，可重复传入",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root)
    changed_files = parse_changed_file_args(args.changed_file) if args.changed_file else load_changed_files(project_root)
    failed, critical, memory_updates = check_memory_update(changed_files)

    print("=" * 60)
    print("Memory Gate 检查")
    print("=" * 60)
    if not critical:
        print("[OK] 未发现需要写入 docs/memory 的关键变更。")
        return 0
    print("关键变更:")
    for path in critical:
        print(f"  - {path}")
    if memory_updates:
        print("已同步核心记忆文件:")
        for path in memory_updates:
            print(f"  - {path}")
        print("[OK] Memory Gate 检查通过。")
        return 0

    print("[FAIL] 关键变更未同步更新核心记忆文件。")
    print("请更新以下任一文件:")
    for path in CORE_MEMORY_FILES:
        print(f"  - {path}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
