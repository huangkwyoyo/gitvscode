# M5b：一次性可写 DuckDB Sandbox——设计与威胁模型

> **文档状态**：M5b-0 设计阶段
> **最后更新**：2026-06-19
> **基线提交**：`c3d460b`（M5a）+ `66bf295`（测试覆盖补充）
> **分类**：C 类系统级风险——需先设计方案，不允许直接实现

---

## 1. 背景与目标

### 1.1 当前状态

M5a 已完成以下静态闭环：

- `sql/main.sql` 与 `spark/main.py` 是唯一权威转换内核。
- `deploy/main.sql` 与 `deploy/main.py` 由确定性生成器封装，不重新生成业务逻辑。
- `deployment_manifest.yml` 绑定双内核哈希、目标表、写入策略、分区列和 `generated` 写入边界。
- `APPROVED` 仅表示 `LOGIC_APPROVED`；只有人工 `RELEASE_APPROVED` 才表示部署制品可以进入外部发布流程。
- 发布审批绑定七类 artifact 的 SHA-256 快照，篡改自动使旧批准失效。
- 部署外壳的确定性编译结果已纳入静态验证（check #208/#209）。

### 1.2 当前局限

- `materialization_status` 仍是 `PENDING`——从未执行过真实物化。
- **当前没有真实验证 CTAS、INSERT 或 Spark Writer 的运行行为。**
- 部署外壳的正确性仅通过静态确定性比较判断——比较 `generate_deploy_sql(verified_sql, manifest)` 的输出是否与落盘的 `deploy/main.sql` 一致。
- 输出表结构、数据质量、幂等性和失败清理行为均未验证。
- `M5a 不执行任何写操作` 既是一项安全保证，也是一个验证盲区。

### 1.3 M5b 目标

**验证部署制品在一次性 Sandbox 中的真实物化行为。**

具体而言：

1. 在完全隔离的一次性 DuckDB 数据库中执行 `deploy/main.sql`。
2. 验证输出表/视图的 schema、行数、空值率和幂等性。
3. 确认执行后 artifact hash 不变。
4. 确认原开发库未被修改。
5. 强制销毁 Sandbox，不留残留。
6. 全部通过后写入 `MATERIALIZATION_VALIDATED`，作为 `RELEASE_APPROVED` 的必要前置条件。

### 1.4 M5b 不是什么

- **不是生产发布。** Sandbox 是完全隔离的一次性临时环境。
- **不是 LLM 接入。** 物化验证是确定性规则引擎。
- **不是完整 Spark Sandbox。** 本阶段只设计 DuckDB 侧。
- **不是自动上线。** `RELEASE_APPROVED` 仍然只能由人设置。
- **不是现有只读 executor 的替代。** `src/sandbox/executor.py` 保持不变。

---

## 2. 范围

### 2.1 本阶段设计对象

| 设计项 | 说明 |
|--------|------|
| DuckDB 一次性 Sandbox | 独立 DuckDB 数据库文件，运行后强制销毁 |
| 受控 sample snapshot | 从开发库只读导出的固定样本数据集 |
| `CREATE_TABLE_AS_SELECT` | M5b 首期支持的核心写入策略 |
| `CREATE_VIEW` | M5b 首期支持的视图创建策略 |
| 物化验证报告 | `reports/materialization_validation.md` + `.yml` |
| 失败清理 | 任何失败路径都必须清理 Sandbox 残留 |
| artifact hash 再校验 | 执行前后验证 Review Package 未被篡改 |
| RELEASE_APPROVED 前置条件 | `MATERIALIZATION_VALIDATED` 成为必需条件 |

### 2.2 首期允许的写入策略

- `CREATE_TABLE_AS_SELECT`（CTAS 全量覆盖建表）
- `CREATE_VIEW`（创建视图）

### 2.3 明确暂缓

| 暂缓项 | 原因 | 目标里程碑 |
|--------|------|-----------|
| `INSERT_OVERWRITE_PARTITION` | 需要分区元数据和更复杂的状态管理 | M5c |
| `INSERT_INTO_PARTITION` | 同上 | M5c |
| Spark Writer | `sandbox/spark_executor.py` 当前是桩 | M5c |
| MERGE | 跨表复杂操作，安全风险高 | M5c+ |
| 生产调度 | 当前不接 CI/CD | M7 |
| 真实 LLM API | 项目边界 | M6 |
| 外部 CI/CD 发布闸门 | 项目边界 | M7 |

---

## 3. 非目标

以下行为**明确排除**，设计中的每一项机制都旨在确保这些行为不可能发生：

- ❌ 不写生产库。
- ❌ 不连接生产环境。
- ❌ 不 ATTACH 生产库。
- ❌ 不访问任意外部路径（read_csv、read_parquet、read_json 等外部文件读取函数被禁止）。
- ❌ 不访问网络（DuckDB 的 httpfs 扩展被禁止）。
- ❌ 不自动上线。
- ❌ 不自动 RELEASE_APPROVED。
- ❌ 不修改现有只读 `src/sandbox/executor.py` 的安全语义。
- ❌ 不放宽现有 Validator（`src/verify/checker.py`）的任何检查。
- ❌ 不实现 Spark Sandbox。

---

## 4. Sandbox 生命周期设计

### 4.1 完整生命周期

```
┌─────────────────────────────────────────────────────────┐
│                  M5b Sandbox 生命周期                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. 前置校验                                              │
│     ├─ artifact hash 全部一致（7 类文件）                   │
│     ├─ logic_approval_state == LOGIC_APPROVED            │
│     └─ materialization_status ∈ {PENDING, FAILED}        │
│                    ↓ 通过                                 │
│  2. 创建受控临时目录                                       │
│     ├─ 路径：{PROJECT_ROOT}/.sandbox_tmp/{sandbox_id}/   │
│     ├─ 禁止位于系统临时目录（防持久化）                      │
│     └─ 禁止位于开发库同级目录（防误连）                      │
│                    ↓                                      │
│  3. materialization_status → RUNNING                     │
│                    ↓                                      │
│  4. 创建一次性 DuckDB 数据库文件                           │
│     ├─ 路径：{sandbox_dir}/sandbox.db                    │
│     ├─ 不 ATTACH 任何外部数据库                            │
│     └─ 禁用 httpfs 扩展（通过 DuckDB SQL 拦截）             │
│                    ↓                                      │
│  5. 初始化 generated schema                              │
│     └─ CREATE SCHEMA IF NOT EXISTS generated              │
│                    ↓                                      │
│  6. 装载受控 sample snapshot                             │
│     ├─ 来源：fixture 或开发库只读导出                        │
│     ├─ snapshot 完整性验证（hash 检查）                     │
│     └─ 只复制表结构和数据，不 ATTACH                        │
│                    ↓                                      │
│  7. 执行 deploy/main.sql                                 │
│     ├─ 操作白名单校验（仅 CTAS/CREATE VIEW）               │
│     ├─ 关键字黑名单校验                                    │
│     ├─ schema 白名单校验（仅 generated）                   │
│     └─ 超时保护（默认 60s）                                │
│                    ↓                                      │
│  8. 物化验证                                              │
│     ├─ 目标表/视图确实存在                                  │
│     ├─ 输出 schema 符合预期                                │
│     ├─ 行数检查                                            │
│     ├─ 空值率检查                                          │
│     ├─ 唯一键检查                                          │
│     └─ 幂等性检查（连续运行两次结果一致）                     │
│                    ↓ 全部通过                              │
│  9. 验证原库未被修改                                       │
│     ├─ 开发库文件 hash 不变                                │
│     └─ 开发库文件 mtime 不变                               │
│                    ↓                                      │
│  10. 清理 Sandbox                                         │
│      ├─ 关闭 DuckDB 连接                                   │
│      ├─ 删除 sandbox.db                                    │
│      ├─ 删除 sandbox 临时目录                              │
│      └─ 确认清理完成                                       │
│                    ↓ 清理成功                              │
│  11. 写入物化验证报告                                      │
│      ├─ reports/materialization_validation.md             │
│      └─ reports/materialization_validation.yml            │
│                    ↓                                      │
│  12. materialization_status → MATERIALIZATION_VALIDATED   │
│                                                         │
│  任一验证失败 → 执行清理 → materialization_status = FAILED │
│  清理本身失败 → materialization_status = CLEANUP_FAILED   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Sandbox 路径约束

```
项目根目录
├── .sandbox_tmp/                    ← M5b 唯一允许的 Sandbox 根目录
│   └── {sandbox_id}/                ← 每次运行独立子目录
│       ├── sandbox.db               ← 一次性 DuckDB 数据库
│       └── snapshot/                ← 受控 sample snapshot
│           └── snapshot.db          ← 只读 snapshot 数据库
```

**硬约束**：

- Sandbox 路径必须位于 `{PROJECT_ROOT}/.sandbox_tmp/` 下。
- 每次运行必须使用新的 `sandbox_id`（UUID v4），不可复用旧目录。
- 运行后必须删除整个 `{sandbox_id}` 目录。
- `sandbox_id` 不得包含 `..`、绝对路径或符号链接。
- 任何路径越界（如 `../../etc/passwd`）立即 FAIL，不执行任何 SQL。

### 4.3 清理策略

- **正常路径**：验证通过后 → 正常清理 → `MATERIALIZATION_VALIDATED`。
- **执行失败**：验证未通过 → 尽力清理 → `FAILED`。
- **清理失败**：清理步骤本身失败 → `CLEANUP_FAILED`。
- **CLEANUP_FAILED 优先级高于普通 FAILED**。
- 清理逻辑必须置于 `finally` 块中，确保异常路径也会执行。
- 如果清理失败，必须在报告中标注残留文件的完整路径，供人工处理。

---

## 5. 独立执行器设计

### 5.1 与现有只读执行器的边界

```
src/sandbox/
├── executor.py                     ← 现有只读执行器（保持不变）
│   ├── read_only=True
│   ├── 仅允许 SELECT / WITH SELECT
│   ├── 安全前缀检查
│   ├── 关键字黑名单
│   └── 超时保护
│
└── materialization_executor.py     ← M5b 新增（本轮不实现）
    ├── write_enabled=True（仅限 Sandbox 内）
    ├── 仅允许 CTAS / CREATE VIEW
    ├── 仅允许写入 generated schema
    ├── 禁止 ATTACH / COPY / EXPORT
    ├── 禁止外部文件读取
    └── 强制清理
```

### 5.2 边界规则

| 规则 | 说明 |
|------|------|
| `executor.py` 不可修改 | 其只读语义是安全信任边界，M5b 不得放宽 |
| `materialization_executor.py` 只在 Sandbox 内写 | 不授予开发库或生产库写入权限 |
| 两套执行器永不混用 | Sandbox 内的写操作绝不通过 `executor.py` 执行 |
| 不允许复用生产连接 | Sandbox 的 DuckDB 连接是临时内存/文件实例 |
| 不允许绕过 artifact hash 校验 | 执行前必须通过 `check_required_artifact_integrity` |

### 5.3 未来 `materialization_executor.py` 核心接口草案

```python
def execute_materialization(
    package_dir: Path,
    deploy_sql: str,
    manifest: DeploymentManifest,
    snapshot: SampleSnapshot,
    sandbox_root: Path,
    timeout_seconds: int = 60,
) -> MaterializationResult:
    """
    在一次性 DuckDB Sandbox 中执行部署 SQL 并返回物化结果。

    Args:
        package_dir: Review Package 目录（用于 artifact hash 校验）
        deploy_sql: deploy/main.sql 内容
        manifest: 已校验的 DeploymentManifest
        snapshot: 受控 sample snapshot
        sandbox_root: Sandbox 临时根目录（如 .sandbox_tmp）
        timeout_seconds: 超时时间（默认 60s）

    Returns:
        MaterializationResult 包含输出表信息、验证结果和清理状态

    Raises:
        SandboxPathViolation: 路径越界
        SandboxCleanupFailed: 清理失败（CLEANUP_FAILED 状态）
        MaterializationFailed: 执行失败（FAILED 状态）
    """
```

---

## 6. 数据来源契约

### 6.1 Sandbox 输入来源

Sandbox 只能接受以下两种输入：

1. **Fixture 文件**：项目 `fixtures/` 目录下的手工测试数据集。
2. **开发库只读导出的固定 sample snapshot**：通过现有只读 `executor.py` 导出，哈希锁定，不可变。

### 6.2 禁止的输入来源

- ❌ 直接写开发库。
- ❌ ATTACH 生产库。
- ❌ 使用生产路径（任何指向生产环境的文件路径）。
- ❌ 任意外部文件路径（`/tmp/`、`~/`、`C:\` 等）。
- ❌ 网络访问（DuckDB `httpfs` 扩展被拦截）。
- ❌ 隐式读取用户本地任意路径。
- ❌ 动态下载数据。

### 6.3 Sample Snapshot 最小契约

```yaml
# snapshot_manifest.yml —— sample snapshot 自描述文件
snapshot_id: "snap_20260619_a1b2c3d4"       # 唯一标识（UUID v4）
source_kind: "fixture"                       # fixture | dev_export
source_tables:                               # 来源表列表
  - "gold.dws_daily_trip_summary"
source_hash: "e3b0c44298fc..."               # 来源表数据的 SHA-256
row_count: 90                                # snapshot 总行数
schema:                                      # 列定义
  - name: trip_date
    type: DATE
  - name: trip_count
    type: INTEGER
created_at: "2026-06-19T14:30:00+00:00"     # 创建时间（ISO8601）
read_only_origin: "fixtures/snapshots/trip_q1_2026.parquet"
allowed_use: "materialization_sandbox_only"  # 唯一允许用途
```

**约束**：

- `allowed_use` 必须为 `materialization_sandbox_only`。
- snapshot 必须包含 `snapshot_manifest.yml`，且 hash 与清单一致。
- snapshot 创建后不可修改（mtime 检查）。
- Sandbox 只能使用与 Review Package 来源表匹配的 snapshot。

---

## 7. 操作白名单

### 7.1 M5b 首期允许的操作

| 操作 | SQL 模式 | 说明 |
|------|---------|------|
| CTAS | `CREATE TABLE generated.<name> AS SELECT ...` | 全量覆盖建表 |
| CTAS（OR REPLACE） | `CREATE OR REPLACE TABLE generated.<name> AS SELECT ...` | 幂等建表 |
| CREATE VIEW | `CREATE VIEW generated.<name> AS SELECT ...` | 创建视图 |
| CREATE SCHEMA | `CREATE SCHEMA IF NOT EXISTS generated` | 初始化 Sandbox schema |

### 7.2 禁止的操作

| 类别 | 关键字/模式 | 拦截方式 |
|------|-----------|---------|
| 数据修改 | INSERT, UPDATE, DELETE, MERGE, REPLACE（非 CTAS 上下文） | FORBIDDEN_DEPLOY_KEYWORDS |
| DDL 破坏 | DROP, ALTER, TRUNCATE | FORBIDDEN_DEPLOY_KEYWORDS |
| 权限操作 | GRANT, REVOKE | FORBIDDEN_DEPLOY_KEYWORDS |
| 数据库操控 | ATTACH, DETACH | FORBIDDEN_DEPLOY_KEYWORDS |
| 数据导出 | COPY, EXPORT, IMPORT | FORBIDDEN_DEPLOY_KEYWORDS |
| 扩展加载 | INSTALL, LOAD | FORBIDDEN_DEPLOY_KEYWORDS |
| 非 generated schema 写入 | `CREATE TABLE gold./bronze./silver.` | schema 白名单校验 |
| 外部文件读写 | `read_csv`, `read_parquet`, `read_json` 等 | SQL 文本模式匹配 |
| 网络访问 | `httpfs` 扩展 | DuckDB 配置拦截 |
| 生产路径 | 任何匹配生产路径模式的字符串 | 路径模式匹配 |

### 7.3 失败策略

- 未知写入策略 → 立即 FAIL，不执行任何 SQL。
- 非法目标 schema → 立即 FAIL，不执行任何 SQL。
- 任何禁止关键字 → 立即 FAIL，不执行任何 SQL。
- **任何失败都不能自动修复部署代码。** Agent 只能报告失败，不能改写 `deploy/main.sql`。

---

## 8. 验证项目

M5b 物化验证必须包含以下 15 项检查：

| # | 验证项 | 通过条件 | 失败等级 |
|---|--------|---------|---------|
| 1 | 目标对象存在 | `generated.<table/view>` 在 Sandbox 中存在 | FAIL |
| 2 | 输出 Schema 符合契约 | 列名、类型与 Manifest 声明一致 | FAIL |
| 3 | 行数符合预期 | 行数在 snapshot 源行数的合理范围内 | WARN |
| 4 | 空值率符合预期 | 每列空值率不超过阈值（默认 30%） | WARN |
| 5 | 唯一键符合预期 | 声明的唯一键列无重复值 | FAIL |
| 6 | 幂等性 | 连续运行两次 deploy/main.sql，输出行数不变 | FAIL |
| 7 | 非法 schema 阻断 | 尝试写入非 generated schema → FAIL | FAIL |
| 8 | 超时中断 | 查询超过 60s 被中断 | FAIL |
| 9 | 失败不残留 | 执行 SQL 语法错误后 Sandbox 目录被清理 | FAIL |
| 10 | Sandbox 路径约束 | 路径始终在 `.sandbox_tmp/` 下 | FAIL |
| 11 | artifact hash 不变 | 执行前后 Review Package 所有文件 hash 一致 | FAIL |
| 12 | 原开发库不变 | 开发库文件 hash 和 mtime 不变 | FAIL |
| 13 | 清理成功写状态 | 只有清理成功后 `materialization_status` 才变为 `MATERIALIZATION_VALIDATED` | FAIL |
| 14 | 清理失败写状态 | 清理失败必须写入 `CLEANUP_FAILED` | FAIL |
| 15 | 无生产环境连接 | 整个过程不出现任何生产路径/连接字符串 | FAIL |

---

## 9. 状态机设计

### 9.1 MaterializationStatus enum（新增到 `src/ir/types.py`）

```python
class MaterializationStatus(str, Enum):
    """物化验证状态——M5b 新增。
    
    M5a 的 materialization_status 字段当前仅使用 PENDING。
    M5b 扩展为完整的状态机。
    """
    PENDING = "PENDING"                           # 尚未执行物化验证
    RUNNING = "RUNNING"                           # 正在执行物化验证
    MATERIALIZATION_VALIDATED = "MATERIALIZATION_VALIDATED"  # 物化验证通过
    FAILED = "FAILED"                             # 物化验证失败
    CLEANUP_FAILED = "CLEANUP_FAILED"             # 清理失败（优先级高于 FAILED）
```

### 9.2 状态转换图

```
                    ┌──────────┐
                    │ PENDING  │  ← M2 build 后的初始状态
                    └────┬─────┘
                         │ 开始物化验证
                         ↓
                    ┌──────────┐
                    │ RUNNING  │
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
        全部验证通过   执行失败    清理失败
              │          │          │
              ↓          ↓          ↓
   ┌──────────────────┐ ┌────────┐ ┌────────────────┐
   │ MATERIALIZATION  │ │ FAILED │ │ CLEANUP_FAILED │
   │   _VALIDATED     │ └────────┘ └────────────────┘
   └──────────────────┘
```

### 9.3 转换规则

| 当前状态 | 触发事件 | 新状态 | 触发者 |
|---------|---------|--------|--------|
| PENDING | 开始物化验证 | RUNNING | agent |
| RUNNING | 全部验证通过 + 清理成功 | MATERIALIZATION_VALIDATED | agent |
| RUNNING | 任一验证失败 | FAILED | agent |
| RUNNING / 任意状态 | 清理步骤失败 | CLEANUP_FAILED | agent |
| CLEANUP_FAILED | 人工清理残留后重新验证 | RUNNING | human（触发重新验证） |
| FAILED | 人工修复后重新验证 | RUNNING | human（触发重新验证） |
| MATERIALIZATION_VALIDATED | Review Package 被修改 | PENDING | agent（自动失效） |

**关键规则**：

- 初始状态为 `PENDING`。
- 开始执行进入 `RUNNING`。
- 全部验证通过**且清理成功**，才能进入 `MATERIALIZATION_VALIDATED`。
- 执行失败进入 `FAILED`。
- 清理失败进入 `CLEANUP_FAILED`，优先级高于 `FAILED`。
- artifact hash 变化 → 拒绝执行 → `FAILED`。
- 路径越界 → 立即 `FAILED`，不执行任何 SQL。
- 检测到生产环境 → 立即 `FAILED`，不执行任何 SQL。
- 未知写入策略 → 立即 `FAILED`，不执行任何 SQL。
- 任何失败都不能自动修复部署代码。

---

## 10. RELEASE_APPROVED 前置条件

### 10.1 完整前置条件链

```
LOGIC_APPROVED
    AND
MATERIALIZATION_VALIDATED
    AND
artifact hashes 全部一致（7 类：sql_main, spark_main, lineage_source_refs,
  verification_summary, deployment_manifest, deploy_sql, deploy_spark）
    AND
Review Package 未被篡改（所有文件 hash 与 approval snapshot 一致）
    AND
deployment artifact 与 approval hash 绑定一致
    AND
人工显式执行 release 子命令
    ↓
RELEASE_APPROVED
```

### 10.2 阻断条件

以下任一条件不满足时，`RELEASE_APPROVED` 被拒绝：

| 条件 | 错误信息 | 返回码 |
|------|---------|--------|
| `logic_approval_state != LOGIC_APPROVED` | RELEASE_APPROVED 前必须完成人工 LOGIC_APPROVED | EXIT_INVALID_STATE |
| `materialization_status != MATERIALIZATION_VALIDATED` | 物化验证未通过，不得 RELEASE_APPROVED | EXIT_INVALID_STATE |
| artifact hashes 不一致 | 审批制品哈希不一致: {key} ({file}) | EXIT_INVALID_STATE |
| Review Package 文件缺失 | 审批制品缺失: {file} | EXIT_MISSING_FILE |
| 部署静态检查非 PASS | 部署静态检查必须为 PASS 才能 RELEASE_APPROVED | EXIT_INVALID_STATE |

### 10.3 不允许自动 RELEASE_APPROVED

- `RELEASE_APPROVED` 只能通过 `review_decision.py release --state RELEASE_APPROVED` 人工设置。
- Agent 不能自动将 `materialization_status` 变为 `RELEASE_APPROVED`。
- 即使所有验证通过，也需要人显式确认。

---

## 11. 报告设计

### 11.1 报告文件

M5b 物化验证产生两份报告：

- `reports/materialization_validation.md`——人类可读的验证报告（Markdown）
- `reports/materialization_validation.yml`——机读验证报告（YAML）

### 11.2 报告字段定义

```yaml
# reports/materialization_validation.yml
request_id: "trip_daily_report_m2"              # Review Package 标识
package_path: "generated/review_packages/trip_daily_report_m2"
sandbox_id: "sand_20260619_1430_a1b2c3d4"      # Sandbox 唯一标识
sandbox_path: ".sandbox_tmp/sand_20260619_1430_a1b2c3d4/"
started_at: "2026-06-19T14:30:00+00:00"         # 开始时间（ISO8601）
finished_at: "2026-06-19T14:30:05+00:00"        # 结束时间
materialization_status: "MATERIALIZATION_VALIDATED"  # 物化状态
allowed_strategy: "CREATE_TABLE_AS_SELECT"       # 执行的写入策略

# ── artifact 哈希（执行前后对比）──
artifact_hash_before:                            # 执行前的哈希快照
  sql_main: "5d0669db8d34eebb..."
  spark_main: "caaa44fcc813c4de..."
  lineage_source_refs: "636eb2b08e0318b..."
  verification_summary: "cc935cf8ec3d3c..."
  deploy_sql: "e08bff4d3ff891d..."
  deploy_spark: "8f8eddfca4839e..."
  deployment_manifest: "871c35bd4488ad..."
artifact_hash_after:                             # 执行后的哈希快照（应与 before 完全一致）
  # ... 同 artifact_hash_before

source_snapshot_hash: "e3b0c44298fc..."          # 输入 snapshot 的 SHA-256

# ── 输出对象 ──
output_objects:
  - object_type: "table"
    object_name: "generated.trip_daily_report_m2"
    row_count: 90
    column_count: 4

# ── 验证结果 ──
schema_check:                                    # 列名与类型验证
  status: "PASS"
  detail: "4 列全部匹配"
row_count_check:                                 # 行数验证
  status: "PASS"
  detail: "90 行，符合预期"
null_rate_check:                                 # 空值率验证
  status: "PASS"
  detail: "trip_date 空值率 0.0%，trip_count 空值率 0.0%"
unique_key_check:                                # 唯一键验证
  status: "PASS"
  detail: "trip_date 无重复"
idempotency_check:                               # 幂等性验证
  status: "PASS"
  detail: "连续两次执行，行数不变（90 == 90）"
timeout_check:                                   # 超时检查
  status: "PASS"
  detail: "执行耗时 1.23s，未超时"
cleanup_check:                                   # 清理检查
  status: "PASS"
  detail: "Sandbox 目录已删除"

# ── 原开发库完整性证明 ──
original_dev_db_hash_before: "abc123..."         # 开发库文件执行前 hash
original_dev_db_hash_after: "abc123..."           # 开发库文件执行后 hash
original_dev_db_mtime_before: 1718800000.0        # 开发库文件执行前 mtime（Unix 时间戳）
original_dev_db_mtime_after: 1718800000.0         # 开发库文件执行后 mtime

# ── 人审信息 ──
warnings: []
errors: []
human_review_notes: ""                            # 人工审查备注
```

---

## 12. 威胁模型

### 威胁清单

| # | 威胁 | 影响 | 缓解措施 | 测试思路 |
|---|------|------|---------|---------|
| T1 | **部署 SQL 被审批后篡改** | 已批准的 deploy SQL 被替换为恶意代码 | artifact hash 执行前再校验；篡改自动使 RELEASE_APPROVED 失效（SUPERSEDED） | 修改 deploy/main.sql 后尝试物化验证→拒绝 |
| T2 | **Review Package 被篡改** | 已验证的查询逻辑被替换 | 七类 artifact hash 全部校验；任何文件变化均检测 | 修改 sql/main.sql 后物化→hash 不一致→拒绝 |
| T3 | **Sandbox 路径越界** | 写入系统文件或覆盖其他项目数据 | Sandbox 路径仅限 `.sandbox_tmp/{sandbox_id}/`；sandbox_id 仅允许 UUID 格式；禁止 `..` | 注入 `../../` 路径→FAIL |
| T4 | **SQL ATTACH 生产库** | Sandbox 中 ATTACH 生产库，执行破坏性操作 | FORBIDDEN_DEPLOY_KEYWORDS 拦截 ATTACH；deploy SQL 静态检查（check #204） | 在 deploy SQL 中嵌入 `ATTACH 'prod.db'`→FAIL |
| T5 | **SQL 写入非 generated schema** | 写入 gold/bronze/silver schema 破坏数据 | schema 白名单校验（仅 generated）；validate_write_boundary 检查 | 目标表设为 `gold.test`→FAIL |
| T6 | **SQL 读取任意外部文件** | 通过 read_csv/read_parquet 读取本地文件 | SQL 文本模式匹配拦截外部文件读取函数；DuckDB 配置禁止文件系统扩展 | deploy SQL 含 `read_csv('/etc/passwd')`→FAIL |
| T7 | **SQL 通过 COPY/EXPORT 写文件** | 将数据导出到外部文件 | FORBIDDEN_DEPLOY_KEYWORDS 拦截 COPY/EXPORT | deploy SQL 含 `COPY ... TO '/tmp/out.csv'`→FAIL |
| T8 | **执行失败后残留数据库被复用** | 上次失败的 Sandbox 被下次运行复用 | 每次运行生成新 sandbox_id；执行前检查并清理旧目录；finally 块强制清理 | 模拟执行失败→确认 Sandbox 目录被删除 |
| T9 | **清理失败被忽略** | 残留数据库留在磁盘，可能被误用 | CLEANUP_FAILED 是显式状态；清理失败记录残留路径供人工处理；报告标注清理状态 | 模拟清理失败→状态为 CLEANUP_FAILED |
| T10 | **开发库被误写** | Sandbox 执行期间误写入开发库 | Sandbox 是完全独立的 DuckDB 文件，不 ATTACH 开发库；原库 hash + mtime 验证 | 执行前后对比开发库文件 hash 和 mtime |
| T11 | **生产库被误连** | Sandbox 连接生产环境 | target_environment 检查（≠ PRODUCTION）；Sandbox 路径不包含生产连接信息；不加载任何环境配置 | target_environment=PRODUCTION→FAIL |
| T12 | **Spark Writer 被误当作已验证** | M5b 只验证 DuckDB，Spark 侧未验证却被视为已通过 | materialization 报告显式标注 `spark: NOT_VALIDATED`；RELEASE_APPROVED 前置条件检查 | 确认报告中 spark 状态为 NOT_VALIDATED |
| T13 | **materialization_status 被伪造** | 攻击者直接修改 decision.yml 中的状态字段 | 状态变化只能通过 agent 的确定性验证流程；手动修改会被 artifact hash 校验检测 | 手动修改 status→下次验证时 hash 不一致→检测 |
| T14 | **RELEASE_APPROVED 绕过 materialization** | 跳过物化验证直接发布 | RELEASE_APPROVED 前置条件在 review_decision.py 中硬编码检查；materialization_status != VALIDATED 时拒绝 | materialization_status=PENDING 时尝试 release→拒绝 |
| T15 | **LLM 生成的部署代码被直接执行** | LLM 生成的恶意 SQL 绕过静态检查 | M5b 不接 LLM；所有 deploy SQL 必须通过 Validator（checks 201-209）；确定性外壳校验 | 不适用（M5b 不接 LLM） |

---

## 13. 测试计划

### 13.1 测试文件规划

```
tests/
├── test_src_sandbox_materialization_executor.py   ← M5b-1 新增
└── test_m5b_materialization_validation.py         ← M5b-2 新增
```

### 13.2 M5b-1 测试用例

| # | 测试用例 | 覆盖威胁 | 预期结果 |
|---|---------|---------|---------|
| 1 | `test_ctas_success` | 基线 | CTAS 执行成功，目标表存在，schema 正确，MATERIALIZATION_VALIDATED |
| 2 | `test_create_view_success` | 基线 | CREATE VIEW 执行成功，视图存在，MATERIALIZATION_VALIDATED |
| 3 | `test_non_generated_schema_blocked` | T5 | 目标表为 `gold.test`→FAIL，不执行任何 SQL |
| 4 | `test_insert_strategy_blocked` | — | write_strategy=INSERT → FAIL，首期不支持 |
| 5 | `test_merge_strategy_blocked` | — | write_strategy=MERGE → FAIL |
| 6 | `test_attach_blocked` | T4 | deploy SQL 含 `ATTACH`→FAIL |
| 7 | `test_copy_export_blocked` | T7 | deploy SQL 含 `COPY ... TO`→FAIL |
| 8 | `test_external_file_read_blocked` | T6 | deploy SQL 含 `read_csv('/tmp/x.csv')`→FAIL |
| 9 | `test_artifact_hash_mismatch_blocks_execution` | T1, T2 | 修改 deploy SQL 后 hash 不一致→拒绝执行 |
| 10 | `test_sandbox_path_traversal_blocked` | T3 | sandbox_id=`../../etc`→FAIL |
| 11 | `test_timeout_interrupts_query` | — | 超时 1s 的慢查询被中断→FAIL |
| 12 | `test_failed_execution_cleanup_success` | T8 | SQL 语法错误→执行失败→Sandbox 目录被清理→FAILED |
| 13 | `test_cleanup_failure_results_in_cleanup_failed` | T9 | 模拟清理失败→CLEANUP_FAILED |
| 14 | `test_idempotency_same_result_twice` | — | 连续两次执行，输出行数相同 |
| 15 | `test_original_dev_db_unchanged` | T10 | 执行前后开发库文件 hash 和 mtime 不变 |
| 16 | `test_only_cleanup_success_writes_validated` | — | 清理失败时不写入 MATERIALIZATION_VALIDATED |
| 17 | `test_release_approved_blocked_without_validation` | T14 | materialization_status=PENDING 时 release→拒绝 |
| 18 | `test_production_environment_blocked` | T11 | target_environment=PRODUCTION→FAIL |

### 13.3 测试约束

- 所有测试使用临时目录（`tmp_path` fixture）。
- 不依赖真实 DuckDB 开发库文件。
- 不创建持久化 Sandbox 残留。
- 测试本身也会清理其创建的任何 Sandbox 目录。

---

## 14. 分阶段实施计划

### M5b-0：设计与威胁模型（本轮）

- ✅ 编写本设计文档。
- ✅ 明确范围、非目标和威胁模型。
- ✅ 定义状态机、前置条件和报告格式。
- ✅ 更新 AGENTS.md 和 README 添加 M5b-0 状态说明。
- ❌ 不写任何执行代码。

### M5b-1：DuckDB CTAS Sandbox（下一阶段）

**实现内容**：

1. 新增 `src/ir/types.py`：`MaterializationStatus` enum。
2. 新增 `src/sandbox/materialization_executor.py`：一次性 DuckDB Sandbox 执行器。
3. 扩展 `scripts/dev_agent/verify_review_package.py`：添加 `--materialize` 选项。
4. 新增 `reports/materialization_validation.md` 和 `.yml` 生成逻辑。
5. 扩展 `scripts/dev_agent/review_decision.py`：release 命令增加 materialization 前置检查。
6. 实现 18 个测试用例（见 §13.2）。

**首期支持策略**：

- `CREATE_TABLE_AS_SELECT`
- `CREATE_VIEW`

### M5b-2：可靠性验证

**实现内容**：

1. 重复运行幂等性测试。
2. 失败注入测试（SQL 语法错误、超时、清理失败）。
3. 原库未修改证明（hash + mtime 对比）。
4. 清理失败路径测试。

### 后续里程碑

| 里程碑 | 内容 | 阻塞条件 |
|--------|------|---------|
| M5c | 隔离 Spark Sandbox + INSERT 策略 | Spark 环境就绪 |
| M6 | 真实 LLM 接入代码生成 | LLM API 可用 |
| M7 | 外部 CI/CD 发布闸门 | 生产基础设施就绪 |

---

## A. 附录

### A.1 与现有代码的交互点

| 现有模块 | M5b 交互方式 | 修改 |
|---------|-------------|------|
| `src/sandbox/executor.py` | 用于导出 sample snapshot（只读） | 不修改 |
| `src/agent/deploy_generator.py` | 复用 `FORBIDDEN_DEPLOY_KEYWORDS` | 不修改 |
| `src/verify/checker.py` | 复用 `validate_deploy_static()`（checks 201-209） | 不修改 |
| `src/agent/decision_manager.py` | 复用 `check_required_artifact_integrity()` | 不修改 |
| `src/ir/types.py` | 新增 `MaterializationStatus` enum | 新增 |
| `scripts/dev_agent/verify_review_package.py` | 新增 `--materialize` CLI 选项 | 扩展 |
| `scripts/dev_agent/review_decision.py` | release 命令新增 materialization 前置检查 | 扩展 |
| `contracts/deployment_manifest_schema.yml` | materialization_status enum 扩展 | 更新 |

### A.2 术语对照

| 术语 | 定义 | 来源 |
|------|------|------|
| Sandbox | 一次性隔离 DuckDB 临时数据库 | M5b 新增 |
| Sample Snapshot | 从开发库只读导出的固定样本数据集 | M5b 新增 |
| MATERIALIZATION_VALIDATED | 物化验证通过，输出符合预期 | M5b 新增 |
| CLEANUP_FAILED | Sandbox 清理失败，残留需人工处理 | M5b 新增 |
