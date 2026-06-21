"""为 pytest 分配项目内唯一临时目录。"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTEST_TEMP_ROOT = PROJECT_ROOT / "harness" / "reports" / "test_tmp"
STALE_SECONDS = 7 * 24 * 60 * 60


def build_basetemp() -> Path:
    """生成当前 pytest 进程独占的临时目录。"""
    return PYTEST_TEMP_ROOT / f"pytest_{os.getpid()}_{uuid4().hex[:12]}"


def cleanup_stale_basetemps(
    root: Path = PYTEST_TEMP_ROOT,
    max_age_seconds: int = STALE_SECONDS,
    excluded: set[Path] | None = None,
) -> None:
    """清理过期 pytest 目录，不触碰其他运行时数据。"""
    if not root.exists():
        return
    excluded_paths = {path.resolve() for path in (excluded or set())}
    cutoff = time.time() - max_age_seconds
    for candidate in root.glob("pytest_*"):
        resolved = candidate.resolve()
        if resolved in excluded_paths or not candidate.is_dir():
            continue
        try:
            if candidate.stat().st_mtime <= cutoff:
                shutil.rmtree(candidate)
        except OSError:
            continue


def pytest_configure(config) -> None:
    """未显式指定 basetemp 时注入唯一项目内目录。"""
    if config.option.basetemp:
        return
    basetemp = build_basetemp()
    basetemp.parent.mkdir(parents=True, exist_ok=True)
    cleanup_stale_basetemps(excluded={basetemp})
    config.option.basetemp = str(basetemp)
    config._tianshu_basetemp = basetemp


def pytest_unconfigure(config) -> None:
    """会话结束后尽力清理自动创建的目录。"""
    basetemp = getattr(config, "_tianshu_basetemp", None)
    if basetemp is not None:
        shutil.rmtree(basetemp, ignore_errors=True)

