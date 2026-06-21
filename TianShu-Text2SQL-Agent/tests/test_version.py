"""src/version.py 版本一致性测试。

验证：
- 版本号可从 importlib.metadata 或 pyproject.toml 正确读取
- 版本号符合 semver 格式
- 所有版本入口一致（无硬编码漂移）
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


class TestVersionModule:
    """src.version 模块正确读取版本号。"""

    def test_version_is_non_empty_string(self):
        """版本号应为非空字符串。"""
        from src.version import VERSION

        assert isinstance(VERSION, str)
        assert len(VERSION) > 0

    def test_version_matches_semver_format(self):
        """版本号应符合 major.minor.patch 格式。"""
        from src.version import VERSION

        assert re.match(r"^\d+\.\d+\.\d+$", VERSION), f"版本格式不符: {VERSION}"

    def test_get_version_returns_same_as_constant(self):
        """get_version() 应与 VERSION 常量一致。"""
        from src.version import VERSION, get_version

        assert get_version() == VERSION

    def test_version_matches_pyproject_toml(self):
        """版本号应与 pyproject.toml 中的值一致。"""
        from src.version import VERSION

        pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        content = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        assert match, "无法从 pyproject.toml 解析版本号"
        assert VERSION == match.group(1), (
            f"src/version.py 返回 {VERSION}，但 pyproject.toml 声明 {match.group(1)}"
        )


class TestVersionNoHardcode:
    """版本号不得硬编码在入口文件中。"""

    @pytest.mark.parametrize(
        "filepath,field_pattern",
        [
            ("src/api/app.py", 'version="1.'),
            ("scripts/run_web_ui_smoke.py", '"version": "1.'),
        ],
    )
    def test_no_hardcoded_version_in_entry_points(
        self, filepath, field_pattern
    ):
        """入口文件中不得硬编码版本号字符串。"""
        full_path = Path(__file__).resolve().parents[1] / filepath
        content = full_path.read_text(encoding="utf-8")

        # 排除 import/from 行（如 from src.version import VERSION）
        lines_with_hardcode = [
            line.strip()
            for line in content.splitlines()
            if field_pattern in line
            and "import" not in line
            and "from " not in line
            and "VERSION" not in line  # VERSION 是变量名而非字面量
        ]

        assert not lines_with_hardcode, (
            f"{filepath} 中发现硬编码版本号:\n"
            + "\n".join(f"  {line}" for line in lines_with_hardcode)
        )

    def test_fastapi_app_uses_version_constant(self):
        """FastAPI 应用应使用 VERSION 常量而非硬编码。"""
        app_path = (
            Path(__file__).resolve().parents[1] / "src" / "api" / "app.py"
        )
        content = app_path.read_text(encoding="utf-8")
        assert "from src.version import VERSION" in content
        assert "version=VERSION" in content or "version = VERSION" in content
