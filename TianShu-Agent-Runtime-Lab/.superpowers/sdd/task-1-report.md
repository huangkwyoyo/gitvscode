# Task 1 修复报告 — RuntimeState + Config

## 修复内容

### 1. 移除未使用的 import

**文件**: `src/runtime_lab/config.py`
**改动**: 移除了第3行 `import os`，该导入在文件中未被使用（代码仅依赖 `pathlib.Path`）。

### 2. 新增 `test_get_run_dir` 测试

**文件**: `tests/test_skeleton.py`
**改动**: 
- 在文件顶部添加了 `from runtime_lab.config import get_project_root` 导入
- 新增 `test_get_run_dir` 测试函数，使用 `tmp_path` 和 `monkeypatch` fixture：
  - 通过 `monkeypatch.setattr` 将 `get_project_root` 替换为返回 `tmp_path` 的 lambda
  - 调用 `get_run_dir("test_run_001")`，验证返回路径正确
  - 验证目录已被创建（`exists()`、`is_dir()`）

## 测试结果

```
tests/test_skeleton.py::test_state_default_values PASSED
tests/test_skeleton.py::test_state_with_values PASSED
tests/test_skeleton.py::test_config_paths PASSED
tests/test_skeleton.py::test_get_run_dir PASSED

============================== 4 passed in 0.09s ==============================
```

所有 4 个测试全部通过。
