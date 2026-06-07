# 纽约市城市交通 DuckDB 基础知识与操作

生成日期：2026-06-07

适用数据库：

```text
D:/ProgramData/Datawarehouse/纽约市城市交通/nyc_transport.duckdb
```

本文把你当前的 `nyc_transport.duckdb` 当作学习案例，说明 DuckDB 数据库文件、Schema、表、视图、Parquet 文件之间的关系，并给出常用操作 SQL。

## 先回答你的几个问题

### 1. `nyc_transport.duckdb` 存储的是什么信息？

这个文件是 DuckDB 的数据库文件。它至少存储了这些内容：

| 存储内容 | 英文技术名 | 中文说明 | 是否一定在 `.duckdb` 文件内 |
|---|---|---|---|
| 数据库目录 | catalog | 记录有哪些 schema、表、视图、字段等对象 | 是 |
| Schema 定义 | schema metadata | 当前项目建立了 `bronze`、`silver`、`gold`、`meta` 四个 schema | 是 |
| 视图定义 | view definition | 例如 `bronze` 下的 Parquet 大表视图，保存的是 SQL 定义 | 是 |
| 物理表数据 | physical table data | CSV 快照表被导入后，数据会写进 DuckDB 文件 | 是 |
| 元数据表 | metadata tables | `meta.source_tables`、`meta.source_columns`、质量检查结果等 | 是 |
| 外部 Parquet 明细数据 | external parquet data | 通过 `read_parquet` 读取的大表实际仍在原始 Parquet 文件中 | 否 |

你这个库的构建脚本是：

```text
D:/Program Files/gitvscode/TianShu/scripts/build_nyc_transport_duckdb_bronze.py
```

脚本里有一个关键逻辑：

```sql
CREATE OR REPLACE VIEW bronze.<表名> AS
SELECT *
FROM read_parquet('<原始 parquet 文件路径>');
```

这说明 Parquet 大表不是复制进 DuckDB 文件，而是被注册成外部视图。

### 2. 实际数据还是在原来的 Parquet 文件里吗？

对 Parquet 大表来说，是的。

当前目录下 Parquet 文件合计约 2.44GB，而 `nyc_transport.duckdb` 约 20MB。再结合构建脚本中的 `read_parquet` 外部视图逻辑，可以判断：

| 数据来源 | Bronze 对象类型 | 实际明细数据在哪里 | 说明 |
|---|---|---|---|
| Parquet 大表 | VIEW / 视图 | 原始 `.parquet` 文件 | DuckDB 只保存视图定义和路径 |
| CSV 快照表 | TABLE / 物理表 | `nyc_transport.duckdb` 内 | CSV 已被 `read_csv_auto` 导入 |
| `meta` 质量检查表 | TABLE / 物理表 | `nyc_transport.duckdb` 内 | 保存数据目录、字段目录、缺失率、候选键等结果 |

也就是说：

```text
Parquet 大表：数据在 parquet，DuckDB 保存入口和查询定义。
CSV 小表：数据已导入 DuckDB，原 CSV 更多是来源文件和可重建依据。
meta 元数据表：数据在 DuckDB。
```

### 3. `D:/ProgramData/Datawarehouse/纽约市城市交通` 里的 Parquet 文件还能移动吗？

如果你还想让当前 `nyc_transport.duckdb` 里的 `bronze` Parquet 视图继续可用，不建议直接移动。

原因是当前构建脚本使用的是绝对路径：

```text
D:/ProgramData/Datawarehouse/纽约市城市交通/...
```

如果移动或重命名 Parquet 文件、上级目录、中文数据集目录，视图里的 `read_parquet('<旧路径>')` 就会找不到文件。

移动后的典型报错会类似：

```text
IO Error: No files found that match the pattern ...
```

如果必须移动，有三种处理方式：

| 方式 | 英文技术名 | 中文说明 | 推荐程度 |
|---|---|---|---|
| 重建 DuckDB 视图 | recreate views | 修改脚本里的 `BASE_DIR` 后重新执行构建脚本 | 推荐 |
| 修改视图路径 | replace view path | 对每个 Parquet 视图执行 `CREATE OR REPLACE VIEW` | 推荐 |
| 导入成物理表 | materialize tables | 用 `CREATE TABLE AS SELECT * FROM read_parquet(...)` 把数据复制进 DuckDB | 只在需要脱离 Parquet 时使用 |

如果把 Parquet 全部导入成 DuckDB 物理表，数据库文件会显著变大，可能从 20MB 变成数 GB 级别。

### 4. 为什么 `SHOW DATABASES` 只显示 `nyc_transport`？

因为 `SHOW DATABASES` 显示的是当前连接中已打开或已附加的数据库 catalog，不是显示 schema。

在 DuckDB 中，层级可以这样理解：

```text
Database / 数据库
└─ Schema / 模式
   └─ Table 或 View / 表或视图
      └─ Column / 字段
```

你连接的是：

```text
nyc_transport.duckdb
```

所以 `SHOW DATABASES` 只显示：

```text
nyc_transport
```

这并不代表只有一个 schema。schema 要用其他命令查看。

## Database 和 Schema 的区别

### Database / 数据库

Database 是一个数据库文件或数据库 catalog。

在 DuckDB 里，一个 `.duckdb` 文件通常就是一个数据库。例如：

```text
nyc_transport.duckdb
```

连接这个文件后，DuckDB 会把它作为一个数据库 catalog。你可以把它理解成“一个数据项目的大容器”。

查看当前数据库：

```sql
SHOW DATABASES;
```

### Schema / 模式

Schema 是数据库内部的命名空间，用来组织表和视图。

你的项目采用的是湖仓 Medallion 分层：

| Schema 英文名 | Schema 中文名 | 作用 |
|---|---|---|
| `bronze` | 原始层 | 保存原始数据入口，尽量贴近源文件 |
| `silver` | 标准层 | 后续用于清洗、统一字段、治理明细数据 |
| `gold` | 主题层 | 后续用于星型模型、指标表、分析主题 |
| `meta` | 元数据层 | 保存表目录、字段目录、质量检查、中文语义说明 |

查看 schema：

```sql
SELECT catalog_name, schema_name
FROM information_schema.schemata
ORDER BY catalog_name, schema_name;
```

## 如何查看特定 Schema 下的表

### 方法一：快速查看某个 schema 下的对象

查看 `bronze` 下的表和视图：

```sql
SHOW TABLES FROM bronze;
```

查看 `meta` 下的表和视图：

```sql
SHOW TABLES FROM meta;
```

注意：`SHOW TABLES FROM bronze` 会列出表和视图，但不会告诉你对象类型。

### 方法二：查看表、视图和对象类型

推荐新手优先使用这个查询：

```sql
SELECT
    table_schema AS schema_英文名,
    table_name AS table_英文名,
    table_type AS object_类型
FROM information_schema.tables
WHERE table_schema = 'bronze'
ORDER BY table_name;
```

常见 `table_type`：

| table_type | 中文说明 |
|---|---|
| `BASE TABLE` | 物理表，数据存储在 DuckDB 文件中 |
| `VIEW` | 视图，保存 SQL 查询定义 |

### 方法三：查看所有 schema 下的表

```sql
SHOW ALL TABLES;
```

这个命令会显示数据库、schema、对象名和字段列表。

### 方法四：只查看视图定义

这个命令很适合判断视图是否引用了外部 Parquet：

```sql
SELECT
    schema_name AS schema_英文名,
    view_name AS view_英文名,
    sql AS view_SQL定义
FROM duckdb_views()
WHERE schema_name = 'bronze'
ORDER BY view_name;
```

如果 `view_SQL定义` 里出现：

```sql
read_parquet('D:/ProgramData/Datawarehouse/纽约市城市交通/...')
```

就说明这个对象依赖外部 Parquet 文件。

## 当前项目的 Bronze 对象

根据 `纽约市城市交通_Bronze入库校验报告.md` 和构建脚本，当前 `bronze` 已注册或导入 16 张结构化源表。

| 英文表名 | 中文表名 | 数据域 | 文件格式 | Bronze 对象类型 | 数据位置 |
|---|---|---|---|---|---|
| `fhv_tripdata_2026q1` | FHV 行程记录表 | 出行域 | Parquet | VIEW | 原 Parquet 文件 |
| `fhvhv_tripdata_2026q1` | 高容量 FHV 行程记录表 | 出行域 | Parquet | VIEW | 原 Parquet 文件 |
| `green_tripdata_2026q1` | 绿色出租车行程记录表 | 出行域 | Parquet | VIEW | 原 Parquet 文件 |
| `yellow_tripdata_2026q1` | 黄色出租车行程记录表 | 出行域 | Parquet | VIEW | 原 Parquet 文件 |
| `parking_violations_all` | 停车违章罚单表 | 监管合规域 | Parquet | VIEW | 原 Parquet 文件 |
| `crash_merged` | 机动车碰撞事故事实表 | 安全域 | Parquet | VIEW | 原 Parquet 文件 |
| `crash_person_all` | 机动车碰撞事故人员表 | 安全域 | Parquet | VIEW | 原 Parquet 文件 |
| `taxi_zone_lookup` | 出租车区域查询表 | 空间地理域 | CSV | TABLE | DuckDB 文件内 |
| `fhv_base_aggregate_report` | FHV 基地汇总报告表 | 供给域 | CSV | TABLE | DuckDB 文件内 |
| `new_driver_applications` | TLC 新司机申请状态表 | 监管合规域 | CSV | TABLE | DuckDB 文件内 |
| `tif_medallion_payments` | 出租车改善基金牌照费表 | 监管合规域 | CSV | TABLE | DuckDB 文件内 |
| `fhv_active_vehicles` | FHV 活跃车辆表 | 资产域 | CSV | TABLE | DuckDB 文件内 |
| `fhv_active_drivers` | FHV 活跃驾驶员表 | 供给域 | CSV | TABLE | DuckDB 文件内 |
| `medallion_authorized_vehicles` | 授权牌照车辆表 | 监管合规域 | CSV | TABLE | DuckDB 文件内 |
| `shl_active_drivers` | 街头扬招车活跃司机表 | 供给域 | CSV | TABLE | DuckDB 文件内 |
| `active_vehicles` | 活跃车辆注册表 | 资产域 | CSV | TABLE | DuckDB 文件内 |

## DuckDB 基本操作

### 连接数据库

Python 方式：

```python
import duckdb

# 连接本地 DuckDB 文件
conn = duckdb.connect(r"D:/ProgramData/Datawarehouse/纽约市城市交通/nyc_transport.duckdb")
```

如果只是查看，不想写入：

```python
import duckdb

# 只读连接可以避免误写数据
conn = duckdb.connect(
    r"D:/ProgramData/Datawarehouse/纽约市城市交通/nyc_transport.duckdb",
    read_only=True,
)
```

命令行方式：

```powershell
D:\ProgramData\node_global\duckdb.exe D:\ProgramData\Datawarehouse\纽约市城市交通\nyc_transport.duckdb
```

### 退出 DuckDB

在 DuckDB 命令行里输入：

```sql
.quit
```

或者：

```sql
.exit
```

### 查看数据库

```sql
SHOW DATABASES;
```

### 查看 schema

```sql
SELECT schema_name
FROM information_schema.schemata
ORDER BY schema_name;
```

### 查看某个 schema 下的表和视图

```sql
SELECT
    table_schema AS schema_英文名,
    table_name AS table_英文名,
    table_type AS object_类型
FROM information_schema.tables
WHERE table_schema = 'bronze'
ORDER BY table_name;
```

### 查看字段

查看某张表的字段：

```sql
DESCRIBE bronze.crash_merged;
```

或使用标准信息表：

```sql
SELECT
    column_name AS column_英文名,
    data_type AS 数据类型,
    ordinal_position AS 字段顺序
FROM information_schema.columns
WHERE table_schema = 'bronze'
  AND table_name = 'crash_merged'
ORDER BY ordinal_position;
```

### 查询前 10 行

```sql
SELECT *
FROM bronze.crash_merged
LIMIT 10;
```

### 统计行数

```sql
SELECT COUNT(*) AS 行数
FROM bronze.crash_merged;
```

### 按 schema 和表名完整引用对象

推荐始终写成：

```sql
SELECT *
FROM bronze.crash_merged
LIMIT 10;
```

不推荐只写：

```sql
SELECT *
FROM crash_merged
LIMIT 10;
```

因为只写表名时，DuckDB 需要依赖当前 search path，新手容易查错 schema。

## 如何判断一张表是物理表还是外部 Parquet 视图

第一步，看对象类型：

```sql
SELECT
    table_schema,
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'bronze'
ORDER BY table_name;
```

第二步，看视图定义：

```sql
SELECT
    view_name,
    sql
FROM duckdb_views()
WHERE schema_name = 'bronze'
ORDER BY view_name;
```

判断规则：

| 看到的情况 | 说明 |
|---|---|
| `table_type = 'BASE TABLE'` | 物理表，数据在 DuckDB 文件内 |
| `table_type = 'VIEW'` 且 SQL 包含 `read_parquet` | 外部 Parquet 视图，数据在 Parquet 文件里 |
| `table_type = 'VIEW'` 且 SQL 查询其他表 | 普通逻辑视图，数据来自它引用的表或视图 |

## 如何修复移动 Parquet 后的视图

假设你把：

```text
D:/ProgramData/Datawarehouse/纽约市城市交通/机动车碰撞事故 - 事件/crash_merged.parquet
```

移动到了：

```text
E:/Datawarehouse/纽约市城市交通/机动车碰撞事故 - 事件/crash_merged.parquet
```

你需要重建视图：

```sql
CREATE OR REPLACE VIEW bronze.crash_merged AS
SELECT *
FROM read_parquet('E:/Datawarehouse/纽约市城市交通/机动车碰撞事故 - 事件/crash_merged.parquet');
```

如果有多张 Parquet 视图，建议修改构建脚本里的 `BASE_DIR` 后整体重跑，而不是手工一张张改。

## 如果想把 Parquet 真正导入 DuckDB

可以这样做：

```sql
CREATE OR REPLACE TABLE bronze.crash_merged_physical AS
SELECT *
FROM read_parquet('D:/ProgramData/Datawarehouse/纽约市城市交通/机动车碰撞事故 - 事件/crash_merged.parquet');
```

这样 `bronze.crash_merged_physical` 就是物理表，数据进入 DuckDB 文件。

但要注意：

| 优点 | 缺点 |
|---|---|
| 脱离原 Parquet 文件也能查询 | DuckDB 文件会变大 |
| 移动项目时只带 `.duckdb` 文件更方便 | 数据重复存储 |
| 查询小表可能更方便 | 大表导入耗时，更新也要重新导入 |

对你当前 2.44GB 的 Parquet 数据来说，继续使用外部视图是合理选择。

## 常见错误和原因

### 错误一：数据库文件被占用

现象：

```text
Cannot open file ".../nyc_transport.duckdb": 另一个程序正在使用此文件
```

原因：

```text
已有 duckdb.exe 或 Python 进程正在打开这个数据库文件。
```

处理方式：

```text
先退出正在运行的 DuckDB 命令行，或关闭占用该文件的 Python 程序。
```

当前检查时发现占用进程为：

```text
D:/ProgramData/node_global/duckdb.exe
```

### 错误二：移动 Parquet 后查不到数据

现象：

```text
IO Error: No files found that match the pattern ...
```

原因：

```text
bronze 视图里保存的是旧的 Parquet 绝对路径。
```

处理方式：

```text
重建视图，或修改构建脚本后重新生成 DuckDB。
```

### 错误三：`SHOW DATABASES` 看不到 `bronze`

这是正常现象。

`bronze` 是 schema，不是 database。

查看 schema 应该用：

```sql
SELECT schema_name
FROM information_schema.schemata
ORDER BY schema_name;
```

查看 `bronze` 下的表应该用：

```sql
SHOW TABLES FROM bronze;
```

## 推荐的新手学习顺序

### 第一步：先理解层级

```text
nyc_transport.duckdb
└─ bronze
   ├─ crash_merged
   ├─ crash_person_all
   └─ yellow_tripdata_2026q1
```

读法是：

```text
数据库 nyc_transport 里面，有 bronze 这个 schema；
bronze 里面，有 crash_merged 这张表或视图。
```

### 第二步：先查 catalog，不急着查大表

```sql
SHOW DATABASES;

SELECT schema_name
FROM information_schema.schemata
ORDER BY schema_name;

SELECT table_schema, table_name, table_type
FROM information_schema.tables
ORDER BY table_schema, table_name;
```

### 第三步：确认对象是否依赖外部文件

```sql
SELECT view_name, sql
FROM duckdb_views()
WHERE sql ILIKE '%read_parquet%'
ORDER BY view_name;
```

### 第四步：再查少量数据

```sql
SELECT *
FROM bronze.crash_merged
LIMIT 10;
```

### 第五步：再做统计

```sql
SELECT
    borough AS 行政区,
    COUNT(*) AS 事故数
FROM bronze.crash_merged
GROUP BY borough
ORDER BY 事故数 DESC;
```

## 和 Medallion 分层的关系

你当前项目不是传统 `ODS / DWD / DWS / ADS` 命名，而是更接近：

```text
Bronze 原始层
↓
Silver 标准层
↓
Gold 主题星型模型
↓
中文语义层
```

在 DuckDB 里可以落成：

| 层级 | DuckDB schema | 中文说明 |
|---|---|---|
| Bronze | `bronze` | 原始数据入口，Parquet 用外部视图，CSV 可导入物理表 |
| Silver | `silver` | 清洗标准层，后续建设标准明细表 |
| Gold | `gold` | 主题星型模型层，后续建设事实表和维度表 |
| 中文语义层 | `meta` 或单独语义配置 | 保存中文表名、中文字段名、指标口径、业务解释 |

事故域可以保留 ER 子模型：

| 英文表名 | 中文表名 | 关系 |
|---|---|---|
| `crash_merged` | 机动车碰撞事故事实表 | 一起事故一行 |
| `crash_person_all` | 机动车碰撞事故人员表 | 一个事故人员一行 |
| `collision_id` | 事故编号 | 连接事故表和事故人员表 |

后续进入 Gold 层时，可以再建设：

| Gold 英文对象 | Gold 中文对象 | 说明 |
|---|---|---|
| `fact_crashes` | 事故事实表 | 面向事故统计分析 |
| `fact_crash_persons` | 事故人员事实表 | 面向人员伤害分析 |
| `dim_date` | 日期维度表 | 支持按日、月、季度、年分析 |
| `dim_location` | 地点维度表 | 支持按行政区、区域、经纬度分析 |
| `dim_vehicle_type` | 车辆类型维度表 | 支持按车辆类型分析 |

## 一句话记忆

```text
Database 是数据库文件，Schema 是数据库里的分区；
Table 可能真的存数据，View 可能只是查询入口；
你这个库里的 Parquet 大表实际还在原 Parquet 文件里；
如果移动 Parquet，要重建 DuckDB 里的 read_parquet 视图。
```
