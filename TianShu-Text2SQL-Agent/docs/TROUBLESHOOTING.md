# TianShu Text2SQL Agent 本地故障排查

本文件收录本地开发和使用中的常见问题及解决方案。

## 环境问题

### Q1: `tianshu-ask` 或 `tianshu-api` 命令未找到

**现象**：终端提示 `command not found` 或 `'tianshu-ask' 不是内部或外部命令`。

**原因**：Python 的 Scripts 目录不在 PATH 中，或未安装项目。

**解决**：

```bash
# 确认已安装
pip install -e ".[api,dev]"

# 检查 Python Scripts 目录
python -c "import sysconfig; print(sysconfig.get_path('scripts'))"

# 将该目录添加到 PATH（Windows Git Bash）
echo 'export PATH="$PATH:$(python -c "import sysconfig; print(sysconfig.get_path(\"scripts\"))")"' >> ~/.bashrc
```

### Q2: `ModuleNotFoundError: No module named 'yaml'`

**现象**：运行脚本时报 `ModuleNotFoundError: No module named 'yaml'` 或类似缺失模块错误。

**原因**：依赖未安装或安装在错误的 Python 环境中。

**解决**：

```bash
# 重新安装全部依赖
pip install -e ".[api,dev]"

# 确认当前 Python 环境
which python
pip list | grep -E "yaml|duckdb|fastapi"
```

### Q3: Windows 控制台输出乱码（GBK 编码）

**现象**：终端输出包含 `□□□□` 或难以辨认的中文字符。

**原因**：Windows 控制台默认使用 GBK（cp936）编码，而项目文件使用 UTF-8。

**解决**：

```bash
# 方案一：设置环境变量（推荐）
export PYTHONIOENCODING=utf-8

# 方案二：在 .env 文件中永久设置
echo "PYTHONIOENCODING=utf-8" >> .env

# 方案三：使用 Git Bash 或 Windows Terminal
# Git Bash 默认使用 UTF-8，无需额外配置
```

> Harness 和所有脚本入口已内置 `sys.stdout.reconfigure(encoding='utf-8')` 兜底，在大多数情况下会自动修复。

## 数据库连接

### Q4: DuckDB 数据库文件不存在

**现象**：启动 Agent 或 API 后 `/health/ready` 返回 `agent_online: false`。

**原因**：`config/tianshu_target.yml` 中的 `duckdb_path` 指向的文件不存在。

**解决**：

```bash
# 检查配置中的路径
grep duckdb_path config/tianshu_target.yml

# 确认文件是否存在
ls -la ../TianShu/data/tianShu.duckdb

# 如路径不正确，编辑 config/tianshu_target.yml
# duckdb_path: "正确的绝对路径/tianShu.duckdb"
```

### Q5: DuckDB 数据库权限错误

**现象**：DuckDB 报 `Permission denied` 或 `Cannot open database file`。

**原因**：
- 文件被其他进程锁定（DuckDB 同一时间只允许一个写连接）
- 文件所在目录无读写权限（Windows 系统保护目录如 `Program Files`）
- 数据库文件为只读属性

**解决**：

```bash
# 确认没有其他进程在使用该文件
# Windows: 关闭所有可能打开该文件的程序（DuckDB CLI、DB Browser 等）

# 检查文件权限
ls -la ../TianShu/data/tianShu.duckdb

# 避免将数据库放在系统保护目录
# 推荐放在用户目录下，如 ~/tianshu-data/tianShu.duckdb
```

## API 服务

### Q6: `/health/ready` 返回 503

**现象**：

```json
{"status": "not_ready", "agent_online": false, "auth_ready": false}
```

**原因**：
- `local_secure_mode: true` 但 `TIANSHU_LOCAL_API_TOKEN` 未设置或长度不足 32 字符
- DuckDB 数据库文件不存在或不可读
- 契约文件路径错误

**解决**：

```bash
# 检查令牌
make env

# 设置令牌
export TIANSHU_LOCAL_API_TOKEN="your-secure-token-at-least-32-characters-long"

# 检查 DuckDB 和契约路径
grep -E "duckdb_path|contracts_path" config/tianshu_target.yml
```

### Q7: API 返回 401（认证失败）

**现象**：

```json
{"error": {"code": "AUTH_FAILED", "message": "认证失败"}}
```

**原因**：
- 请求未携带 `X-TianShu-Token` 头
- 令牌值与 `TIANSHU_LOCAL_API_TOKEN` 环境变量不一致
- 令牌长度不足 32 字符

**解决**：

```bash
# 确认环境变量已设置
echo $TIANSHU_LOCAL_API_TOKEN | wc -c  # 应 >= 33（含换行符）

# curl 示例（正确携带 Token）
curl -X POST http://127.0.0.1:8000/v1/ask \
  -H "Content-Type: application/json" \
  -H "X-TianShu-Token: $TIANSHU_LOCAL_API_TOKEN" \
  -d '{"question": "2026年1月每天有多少行程？"}'
```

### Q8: API 返回 429（请求频率超限）

**现象**：

```json
{"error": {"code": "SERVICE_BUSY", "message": "当前问数请求较多，请稍后再试"}}
```

响应头包含 `Retry-After: N`（N 为建议等待秒数）。

**原因**：请求频率超过限流阈值（默认 30 req/min + 3 burst）。

**解决**：

```bash
# 等待 60 秒后重试（等窗口清空）
sleep 60

# 或调整限流参数（不推荐用于生产）
# 编辑 config/api_config.yml:
#   local_security.rate_limit.requests_per_minute: 60
#   local_security.rate_limit.burst: 10
```

### Q9: API 端口 8000 已被占用

**现象**：启动 API 时报 `Address already in use` 或 `端口已被占用`。

**解决**：

```bash
# 方案一：查找并终止占用进程
# Windows PowerShell:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# 方案二：使用其他端口
# 编辑 config/api_config.yml:
#   server.port: 8001

# 或通过命令行指定端口
tianshu-api --port 8001
```

## LLM 调用

### Q10: DeepSeek API 调用失败

**现象**：Agent 始终返回 refusal，或日志中出现 API 连接错误。

**原因**：
- `config/secrets.yml` 中的 API Key 无效或过期
- 网络无法连接到 DeepSeek API
- API 配额耗尽

**解决**：

```bash
# 检查 secrets.yml
cat config/secrets.yml

# 测试 API 连通性
curl -X POST https://api.deepseek.com/v1/chat/completions \
  -H "Authorization: Bearer $(grep deepseek_api_key config/secrets.yml | cut -d'"' -f2)" \
  -H "Content-Type: application/json" \
  -d '{"model": "deepseek-chat", "messages": [{"role": "user", "content": "你好"}], "max_tokens": 10}'

# 如 API 不可用，可使用离线 rule 模式：
# 编辑 config/agent_config.yml:
#   rule_mode.enabled: true
```

### Q11: Agent 始终返回 refusal（即使问题合法）

**原因**：
- LLM API 不可用但 rule_mode 未启用
- 契约文件不完整（缺少 `question_policy.yml` 或 `metric_contract.yml`）
- Agent 处于 offline 状态

**解决**：

```bash
# 检查 Agent 是否 online
curl http://127.0.0.1:8000/health/ready

# 检查契约文件完整性
ls -la ../TianShu/contracts/

# 尝试使用 rule 模式
# 编辑 config/agent_config.yml:
#   rule_mode.enabled: true
```

## 测试与门禁

### Q12: pytest 测试报错

**现象**：`make test` 失败，部分测试报错。

**解决**：

```bash
# 确认测试依赖已安装
pip install -e ".[dev]"

# 仅运行测试（显示详细错误）
python -m pytest -q --tb=long

# 跳过已知的 Windows 问题测试
python -m pytest -q --tb=short -k "not real_duckdb"

# 指定临时目录（避免 Windows tmp_path 权限问题）
python -m pytest -q --basetemp=harness/reports/test_tmp
```

### Q13: Harness 安全检查失败

**现象**：`make harness` 或 pre-commit hook 中某项检查 FAIL。

**解决**：

```bash
# 运行完整 Harness 查看详细输出
python harness/run_harness.py

# 单项检查示例
python harness/checks/check_sql_readonly.py
python harness/checks/check_ir_schema.py

# 检查报告
cat harness/reports/harness_report_latest.md
```

### Q14: pre-commit hook 阻断提交

**现象**：`git commit` 被 hook 拦截，显示失败步骤。

**解决**：

```bash
# 按 hook 输出中的修复建议逐项处理
# 每步失败都会展示具体原因和修复指导

# 确认所有步骤通过后再提交
python -m compileall -q src harness tests
python -m pytest -q
python harness/run_harness.py --step 1..5
python harness/run_precommit_memory_warn.py --mode blocking

# 紧急情况下的绕过（不推荐）
git commit --no-verify -m "..."
```

## 其他

### Q15: Windows tmp_path 权限错误

**现象**：pytest 报 `PermissionError` 且错误路径在临时目录。

**原因**：已知的 pytest-asyncio 在 Windows 上与 `tmp_path` fixture 的兼容性问题。

**状态**：Phase 6B 已记录，Phase 6C 的 closure 测试已使用 `tempfile.mkdtemp()` 规避。不影响核心功能。

**解决**：

```bash
# 使用自定义临时目录
python -m pytest -q --basetemp=harness/reports/test_tmp

# 如果个别测试持续失败，可跳过
python -m pytest -q -k "not test_local_api_closure"
```

### Q16: 日志文件不生成

**现象**：`logs/` 目录为空，或日志未写入。

**原因**：
- `config/agent_config.yml` 中 `logging.file` 路径不可写
- 日志目录权限不足
- 日志级别设置过高（`logging.level: ERROR` 只记录错误）

**解决**：

```bash
# 检查日志配置
grep -A5 "logging:" config/agent_config.yml

# 创建日志目录
mkdir -p logs

# 降低日志级别以查看更多信息
# 编辑 config/agent_config.yml:
#   logging.level: DEBUG
```

### Q17: Web UI 页面无法打开

**现象**：浏览器访问 `http://127.0.0.1:8000/` 返回 404 或无法连接。

**原因**：
- API 服务未启动
- `config/api_config.yml` 中 `ui.enabled: false`
- `src/web/index.html` 文件缺失

**解决**：

```bash
# 检查 UI 配置
grep -A3 "ui:" config/api_config.yml
# 应显示: enabled: true

# 检查文件存在
ls src/web/index.html src/web/styles.css src/web/app.js

# 启动 API 服务
make api
# 浏览器访问 http://127.0.0.1:8000/
```

### Q18: Web UI 始终显示"认证失败"（401）

**现象**：输入 Token 后问数始终返回 401 错误。

**原因**：
- 输入的 Token 与环境变量 `TIANSHU_LOCAL_API_TOKEN` 不匹配
- `local_secure_mode: true` 但 Token 未设置
- Token 长度不足 32 字符

**解决**：

```bash
# 1. 生成新 Token
export TIANSHU_LOCAL_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# 2. 检查 Token 长度
echo ${#TIANSHU_LOCAL_API_TOKEN}  # 应 >= 32

# 3. 用新 Token 重启 API
make api

# 4. 在 Web UI 中输入相同的 Token
```

> ⚠️ Token 仅保存在当前页面内存中，页面刷新后需重新输入。Web UI 不提供"记住我"功能。

---

## 获取更多帮助

- **文档索引**：[`docs/README.md`](README.md)
- **当前工作流**：[`docs/text2sql_current_pipeline.md`](text2sql_current_pipeline.md)
- **工程术语表**：[`docs/text2sql_engineering_glossary.md`](text2sql_engineering_glossary.md)
- **风险清单**：[`docs/memory/风险清单.md`](memory/风险清单.md)

如问题不在本文范围内，请查阅对应阶段的规划报告（`docs/planning/`）。
