# Data Dev Agent Harness

本目录是 Data Dev Agent 的工程执行入口，管理配置、报告和质量门禁。

## 职责边界

| 内容 | 维护位置 | Harness 中的角色 |
|------|---------|-----------------|
| 管道各层代码 | `scripts/pipeline/` | 调度执行 |
| 质量检查 | `scripts/quality/` | 执行 |
| 数据契约 | `contracts/` | 读取和校验 |
| Column Binding Table | `scripts/pipeline/column_binding.py` | 提供绑定数据 |
| 运行配置 | `harness/config/agent_targets.yml` | 配置源 |
| 执行报告 | `harness/reports/` | 输出 |

## 运行管道

```powershell
# 完整管道（8 层全链路）
python scripts\pipeline\run_pipeline.py --requirement fixtures\requirements\trip_daily_report.yml

# 仅校验（不执行 SQL）
python scripts\pipeline\run_pipeline.py --requirement fixtures\requirements\trip_daily_report.yml --dry-run

# 运行管道自检
python scripts\quality\check_pipeline.py
```

## 运行前提

1. TianShu DuckDB 文件存在：`D:\ProgramData\Datawarehouse\纽约市城市交通\nyc_transport.duckdb`
2. 关闭占用 DuckDB 文件的桌面工具（如 DBeaver）
3. Python 3.10+ 且已安装 duckdb、pyarrow、pandas、pyyaml

## 配置

编辑 `harness/config/agent_targets.yml` 修改：
- TianShu 连接路径
- LLM 模型和参数
- 执行超时和重试策略
- 输出格式和路径

## 子目录

```
harness
├── README.md
├── config
│   └── agent_targets.yml
└── reports
    └── README.md
```
