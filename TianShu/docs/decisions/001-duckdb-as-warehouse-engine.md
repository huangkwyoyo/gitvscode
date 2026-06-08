# 001 — 选择 DuckDB 作为数仓引擎

## Status（状态）

Accepted

## Context（背景）

TianShu 项目启动时需要选择一个数据仓库引擎来承载纽约市城市交通开放数据。项目背景如下：

- **数据规模**：Bronze 层约 16 张表，总量约 9,500 万行（最大单表 6,287 万行），总存储约数个 GB
- **使用场景**：单机分析、Agent 辅助建模、Text2SQL 查询、本地开发与验证
- **团队规模**：个人项目，无多用户并发需求
- **技术栈偏好**：Python 生态，希望 SQL  dialect 简洁
- **部署约束**：数据存储在本地 Windows 机器的 `D:\ProgramData\` 下，不希望搭建和运维服务器

核心需求排序：
1. 零运维成本（不需要启动服务、不需要配置用户权限）
2. SQL 兼容性好（支持标准 SQL，方便后续迁移）
3. 分析性能足够（单机百万~千万行级别的聚合查询在秒级完成）
4. 与 Python 生态无缝集成
5. 文件级可移植（数据库就是一个文件，拷贝即备份）

## Decision（决策）

**选择 DuckDB 作为唯一数仓引擎。**

数据库文件位置：
```text
D:/ProgramData/Datawarehouse/纽约市城市交通/nyc_transport.duckdb
```

具体用法：
- Bronze 层以 DuckDB VIEW + TABLE 混合模式存储原始数据
- Silver 和 Gold 层以 DuckDB TABLE 存储标准化和主题数据
- Meta 元数据以 DuckDB TABLE + VIEW 存储中文语义层
- 所有 SQL 脚本针对 DuckDB 方言编写

## Alternatives（替代方案）

| 方案 | 优势 | 劣势 | 排除原因 |
|---|---|---|---|
| **SQLite** | 零运维，单文件，Python 内置 | OLAP 性能差，无列式存储，无窗口函数完整支持 | 分析性能不满足千万级聚合需求 |
| **PostgreSQL** | SQL 标准兼容最好，生态成熟 | 需要安装和运维服务，不适合"拷贝即备份"的场景 | 运维成本高于项目可接受范围 |
| **ClickHouse** | OLAP 性能极强 | 需要服务进程，配置复杂，Windows 支持一般 | 过度设计，运维成本高 |
| **Pandas/Parquet** | 纯 Python，无外部依赖 | 无 SQL 界面，Agent 生成代码比 SQL 更容易出错 | SQL 是 Agent 更可靠的交互语言 |
| **DuckDB** ✅ | 零运维，单文件，列式存储，OLAP 性能好，Python 原生集成，SQL 方言接近 PostgreSQL | 生态较新，部分语法不兼容 PostgreSQL（如 `DATE::INT` 不支持） | — |

## Consequences（后果）

### 正面影响

- 数据库即文件，备份和迁移只需复制 `.duckdb` 文件
- 不需要启动服务，Agent 脚本 `import duckdb` 即可开始工作
- 列式存储 + 向量化执行，千万级聚合在秒级完成
- Python 集成极其简洁：`duckdb.sql("SELECT ...").df()` 直接转 DataFrame

### 负面影响 / 代价

- DuckDB 方言与 PostgreSQL 存在差异，已踩坑包括：
  - `DATE::INT` 不支持 → 需用 `strftime(d, '%Y%m%d')::INTEGER`
  - 部分 PostgreSQL 生态工具（如 Sqlfluff 的某些规则）不完全兼容
- 不支持多用户并发写入（对当前项目不构成实际问题）
- 社区生态较 PostgreSQL 年轻，遇到冷门问题参考资料较少
- 如果未来数据量增长到数百 GB 级别，单机 DuckDB 可能遇到瓶颈

### 重新评估条件

以下任一条件触发时，应重新评估此决策：

1. **数据总量超过 100 GB**：DuckDB 单文件模式可能开始出现性能下降
2. **需要多用户并发写入**：例如团队协作场景，多人同时建表
3. **需要生产级 Text2SQL 服务**：需要长时间运行的查询服务，而非本地脚本
4. **需要接入 BI 工具**：如 Metabase/Superset 等需要标准 PostgreSQL 协议

重新评估时的首选替代方案是 PostgreSQL（兼容性最好，迁移成本最低）。
