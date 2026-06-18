# Review Package Golden Fixtures

M4b 测试用基准数据。所有时间戳使用固定值确保 diff 确定性。

## 目录说明

| 目录 | 状态 | 用途 |
|------|------|------|
| `golden_m2_package/` | PENDING_REVIEW，刚生成 | 测试 M2 产物结构 + artifact hashes |
| `golden_m3_verified_package/` | PENDING_REVIEW，M3 已验证 | 测试 verification_summary.yml 字段完整性 |
| `golden_approved_package/` | APPROVED，人审已通过 | 测试 SUPERSEDED 触发条件 + 人审 CLI |
| `golden_superseded_package/` | SUPERSEDED，旧批准已失效 | 测试 SUPERSEDED 终态行为 |

## 使用方式

测试中通过 `shutil.copytree` 复制到 `tmp_path` 后操作，避免污染 fixture 源文件。
