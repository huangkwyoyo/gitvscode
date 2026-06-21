from pathlib import Path

from harness.pytest_runtime import build_basetemp, cleanup_stale_basetemps


def test_build_basetemp_is_project_local_and_unique():
    """自动临时目录必须位于项目内且每次运行唯一。"""
    first = build_basetemp()
    second = build_basetemp()
    root = Path("harness/reports/test_tmp").resolve()

    assert first.parent == root
    assert second.parent == root
    assert first != second


def test_cleanup_only_removes_expired_pytest_directories(tmp_path):
    """遗留清理不得删除非 pytest 目录。"""
    expired = tmp_path / "pytest_100_old"
    current = tmp_path / "pytest_200_current"
    unrelated = tmp_path / "manual_data"
    expired.mkdir()
    current.mkdir()
    unrelated.mkdir()

    cleanup_stale_basetemps(tmp_path, max_age_seconds=0, excluded={current})

    assert not expired.exists()
    assert current.exists()
    assert unrelated.exists()

