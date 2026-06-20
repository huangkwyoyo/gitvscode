# 示例目录

本目录包含 TianShu Text2SQL Agent 的使用示例。

## 目录结构

```
examples/
├── README.md                    # 本文件
├── repl/                        # REPL 交互式使用示例
│   ├── basic_questions.md       # 基本问数（含预期输出）
│   └── edge_cases.md            # 反问与拒绝场景
└── api/                         # REST API 请求/响应示例
    ├── request_answer.json      # 正常查询请求
    ├── response_answer.json     # answer 类型响应
    ├── request_clarification.json   # 歧义问题请求
    ├── response_clarification.json  # clarification 类型响应
    ├── request_refusal.json     # 危险操作请求
    ├── response_refusal.json    # refusal 类型响应
    ├── response_error_401.json  # 认证失败错误响应
    ├── response_error_413.json  # 请求体过大错误响应
    └── response_error_429.json  # 限流错误响应
```

## 使用说明

### REPL 示例

[`repl/basic_questions.md`](repl/basic_questions.md) 展示了常见的问数交互，`repl/edge_cases.md` 展示了反问和拒绝场景。

### API 示例

所有 JSON 文件是手写模板，值具有代表性但不是真实查询结果。每个 API 示例可搭配 `curl` 命令测试：

```bash
# 启动 API 服务
make api

# 发送 answer 请求
curl -X POST http://127.0.0.1:8000/v1/ask \
  -H "Content-Type: application/json" \
  -H "X-TianShu-Token: $TIANSHU_LOCAL_API_TOKEN" \
  -d @examples/api/request_answer.json

# 预期的 JSON 响应结构与 examples/api/response_answer.json 一致
```

### 注意事项

- 所有示例不包含真实的 API Key、数据库路径或认证令牌
- JSON 示例中的 `data.summaries` 和 `data.chart_spec` 内容为代表性截断值
- 响应中的具体数值取决于实际数据库内容
