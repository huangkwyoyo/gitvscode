# DashVault Scanner 详细规范

> doc_id: dashvault.spec.scanner
> spec_version: 1.0.0
> review_status: draft
> publication_status: unpublished

## 1. 概述

Scanner 是 DashVault 的文件采集子系统，负责在严格的安全边界内从注册项目中采集文件内容、Git 历史和工作区状态。

## 2. 采集流程

```
开始
  ├─ 1. 读取项目注册信息
  ├─ 2. 获取当前 HEAD commit（git rev-parse HEAD）
  ├─ 3. 计算变更范围
  │     ├─ last_observed_commit 为空 → 全量
  │     └─ 否则 → git diff --name-only last_observed..HEAD -- {pathspec}
  ├─ 4. 获取文件列表（git ls-files 或 os.walk）
  ├─ 5. 应用排除规则
  ├─ 6. 计算每个候选文件的内容哈希
  ├─ 7. 与上次 evidence_manifest 对比
  ├─ 8. 按需读取变更文件正文
  ├─ 9. 生成 evidence_manifest
  └─ 10. 更新 last_observed_commit 和 last_scan_time
```

## 3. Git 扫描器接口

```python
class GitScanner:
    """Git 仓库项目的文件扫描器"""

    def __init__(self, project: RegisteredProject): ...
    def get_head_commit(self) -> str:
        """返回当前 HEAD 完整 40 位 SHA"""
    def get_changed_files(self, since_commit: str | None) -> list[FileChange]: ...
    def get_all_tracked_files(self) -> list[str]:
        """返回 git ls-files 中 pathspec 限定下的所有受控文件"""
    def read_file(self, relative_path: str) -> FileContent: ...
    def get_worktree_state(self) -> WorktreeState: ...
    def scan(self, evidence_scope: EvidenceScope | None = None) -> ScanResult:
        """执行完整扫描流程（步骤 1-10）"""
```

### 3.1 增量扫描

```python
def compute_diff(last_observed: str | None, current_head: str, pathspec: str) -> list[str]:
    if not last_observed:
        return run_git(f"ls-files --full-name {pathspec}")
    return run_git(f"diff --name-only {last_observed}..{current_head} -- {pathspec}")
```

## 4. 目录扫描器接口

```python
class DirectoryScanner:
    """非 Git 项目的文件系统扫描器"""
    def __init__(self, project: RegisteredProject): ...
    def get_all_files(self) -> list[str]: ...
    def read_file(self, relative_path: str) -> FileContent: ...
    def get_directory_hash(self) -> str: ...
    def scan(self) -> ScanResult: ...
```

## 5. 文件过滤引擎

```python
class FileFilter:
    GLOBAL_EXCLUDE = [
        ".env", ".env.*", ".venv/", ".pytest_cache/", ".pytest_tmp/",
        ".ruff_cache/", "__pycache__/", "*.pyc", "logs/",
        "llm_responses/", "llm_reports/", "generated/", ".git/",
        "node_modules/",
    ]

    def should_include(self, path: str, project: RegisteredProject) -> bool:
        """优先级：全局排除 → 项目 exclude → 项目 include → 默认包含"""
```

### 5.1 大小和类型限制

| 限制 | 默认值 |
|------|--------|
| 单文件最大 | 1 MB |
| 单次最大文件数 | 500 |
| 禁止二进制 | 基于文件头魔数：.pyc .pkl .zip .tar .exe .dll |

## 6. 快照数据结构

```python
@dataclass
class ScanResult:
    project_id: str
    head_commit: str
    worktree_state: WorktreeState
    files: list[FileContent]
    files_skipped: list[SkippedFile]
    files_excluded: list[ExcludedFile]
    manifest: EvidenceManifest
    scan_time: str

@dataclass
class FileContent:
    path: str
    content: str
    content_hash: str            # sha256:...
    size_bytes: int
    line_count: int
    change_type: str             # new | changed | unchanged | deleted
    reason: str

@dataclass
class EvidenceManifest:
    manifest_id: str             # ULID
    run_id: str
    generated_at: str
    project_id: str
    git_commit: str
    git_root: str
    git_pathspec: str
    worktree_state: str
    worktree_hash: str | None
    files_read: list[ManifestFileEntry]
    files_excluded: list[ManifestExcludedEntry]

@dataclass
class ManifestFileEntry:
    path: str
    content_hash: str
    lines_read: str | None
    reason: str

@dataclass
class ManifestExcludedEntry:
    path: str
    reason: str
```

## 7. 安全约束

### 7.1 路径遍历防护

```python
def validate_path(relative_path: str, project_root: str) -> str:
    resolved = os.path.normpath(os.path.join(project_root, relative_path))
    if not resolved.startswith(os.path.normpath(project_root)):
        raise PathTraversalError(f"Path traversal: {relative_path}")
    return resolved
```

- 默认不跟随符号链接
- 符号链接记录但标记 `is_symlink: true`

## 8. 错误处理

| 场景 | 处理 |
|------|------|
| Git 仓库损坏 | ScannerError，提示修复 |
| 文件被进程删除 | 跳过，"file_vanished" |
| 非 UTF-8 编码 | latin-1 回退，失败则跳过 |
| 磁盘 IO 错误 | 重试 2 次，仍失败则中止 |
