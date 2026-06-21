# LLM Raw Output 数据保留策略

> 适用于 `_save_raw_output_on_failure()` 写入的诊断数据。
> 最后更新：2026-06-21

## 默认不保存问题原文

| 配置 | 行为 |
|------|------|
| `raw_output.include_question: never`（默认） | 仅保存 question_id（SHA-256 哈希）、长度、字符类别 |
| `raw_output.include_question: redacted`（显式 opt-in） | 保存 PII 脱敏后的问题文本 |

**不存在** `include_question: full` 选项。问题原文永不会未经脱敏存入磁盘。

## 脱敏覆盖

递归应用于 `question`（如 opt-in）、`raw_output`、`parsed_output`、`error_message`：

| 类型 | 示例 | 脱敏后 |
|------|------|--------|
| 手机号 | `13812345678` | `[手机号]` |
| 邮箱 | `user@example.com` | `[邮箱]` |
| 身份证号 | `110101199001011234` | `[身份证号]` |
| 车牌号 | `京A12345` | `[车牌号]` |
| API Key | `sk-abc123def456ghi789jkl` | `[API_KEY]` |
| Authorization | `Authorization: Bearer xyz` | `Authorization: Bearer [已脱敏]` |

## 文件名规则

文件名格式：`q_{sha256[:16]}_{stage}_{uuid8}.json`

- 仅使用问题文本的 SHA-256 哈希前 16 位
- 不含问题原文片段
- 不含时间戳（时间戳在 payload 内）

## 文件权限

- 写入后设置 `os.chmod(path, 0o600)`（仅当前用户可读写）
- Windows 上设置失败静默忽略

## 保留期限

- 默认无限期保留（本地诊断用途）
- 建议手动清理超过 30 天的文件
- 未来可配置 `raw_output.max_age_days` 自动清理

## 写入失败处理

- 写入异常被 `try/except` 捕获
- 失败时返回 `None`，不抛出异常
- 不影响主查询流程
- 日志中不含原始异常消息

## 存储位置

- 默认路径：`harness/reports/llm_raw_outputs/{run_id}/`
- 通过 `agent_config.yml` 的 `raw_output.dir` 配置

## 审查记录

| 日期 | 变更 | 审查者 |
|------|------|--------|
| 2026-06-21 | 初始策略：PII 脱敏、文件名去原文化、写入故障隔离 | huangkwyoyo |
