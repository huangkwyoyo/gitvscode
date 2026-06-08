# 字段字典

本目录存放字段字典规范和 Bronze 层枚举值说明。Silver/Gold 层字典待补充。

## 文档清单

| 文档 | 说明 |
|---|---|
| `枚举值识别方法论.md` | 如何识别需要中文含义的枚举值字段（状态码/标志位/分类代码） |
| `bronze_enum_values.md` | Bronze 层 16 张表的枚举值中文含义（核心产物） |

> 分析报告（MV-104AN 编码验证、VEH 字段映射分析）见 [`docs/memory/`](../../memory/)。

---

## Bronze 层字段字典

- **枚举值说明**：`bronze_enum_values.md` — 16 张表，95 项 ✅ 已确认
- **完整字段字典**：`D:/ProgramData/Datawarehouse/纽约市城市交通/分析报告/纽约市城市交通_全表数据字典.md`（15 张 Bronze 表 + Meta 层 8 个对象，264 个字段）
- **更新方式**：基于构建脚本 `scripts/build_nyc_transport_duckdb_bronze.py` 自动生成 `meta.source_columns`

## Silver 层字段字典

- **XLSX**：`D:/ProgramData/Datawarehouse/纽约市城市交通/分析报告/Silver层数据字典.xlsx`
- **Sheet 数**：12（1 总览 + 11 张表各一个 Sheet）
- **生成脚本**：`scripts/silver/_gen_xlsx.py`

## 官方数据字典

官方原始 xlsx 不放入 Git 仓库。文件位置：

```text
D:\ProgramData\Datawarehouse\纽约市城市交通\官方数据字典\纽约市城市交通_全域数据规范.xlsx
```

不放入的原因：
- xlsx 是二进制文件，不利于代码审查
- Excel 打开时生成的 `~$` 临时锁文件容易误提交
- 根目录 `.gitignore` 已忽略 `*.xlsx`，避免误提交本地分析产物

项目仓库内维护 Markdown 格式的字段解释、枚举值说明和指标口径。

---

## 字段字典必须包含

- 英文表名、中文表名
- 英文字段名、中文字段名
- 数据类型
- 字段层级（主键/时间/空间/金额/维度属性/度量/质量标记/溯源）
- 业务含义
- 治理备注
- 来源类型（direct / standardized / derived）
- 来源 Bronze 字段（direct/standardized 必填）
- 派生逻辑（derived 必填）
- **枚举值说明**（含代码、缩写、状态码、标志位时必填）

## 枚举值说明

> 识别规则详见 [`枚举值识别方法论.md`](./枚举值识别方法论.md)。

字段值如果是代码、缩写、状态码或标志位，必须补充中文含义。例如：

| 英文表名 | 英文字段名 | 枚举值 | 中文含义 | 审核状态 |
|---|---|---|---|---|
| `new_driver_applications` | `Type` | `HDR` | 租用车辆驾驶员执照 (For-Hire Vehicle Driver) | ✅ 已确认 |
| `new_driver_applications` | `Type` | `PDR` | 辅助公交驾驶员执照 (Paratransit Driver) | ✅ 已确认 |
| `new_driver_applications` | `Type` | `VDR` | 通勤面包车驾驶员执照 (Commuter Van Driver) | ✅ 已确认 |

不能确认官方含义时，标记 `Human Review`，绝不凭经验翻译。

## 变更流程

每次 schema 变更：
1. 更新对应层的 database_design 文档
2. 更新字段字典和枚举值说明
3. 运行 `python scripts/quality/run_all_checks.py` 通过检查
4. PR Review 后才能合入
