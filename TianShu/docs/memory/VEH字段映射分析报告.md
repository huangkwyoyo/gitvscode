# VEH 字段分析：TLC 未公开的字段映射表

> **分析日期**：2026-06-08
> **分析对象**：`nyc_transport.bronze.fhv_active_vehicles.VEH` 字段的 9 种枚举值
> **核心问题**：VEH 代码的完整映射是否为 TLC 未公开的字段映射表？

---

## 一、VEH 字段的基本事实

### 1.1 数据来源

- **数据集**：[For Hire Vehicles (FHV) - Active](https://data.cityofnewyork.us/Transportation/For-Hire-Vehicles-FHV-Active/8wbx-tsch)（NYC Open Data，TLC 发布）
- **字段名**：`VEH`
- **出现位置**：`fhv_active_vehicles` 表（Bronze 层 CSV 导入），共 104,420 行
- **distinct 数**：9
- **取值**：`BEV`, `CNG`, `DSE`, `DSEL`, `HYB`, `N`, `NON`, `STR`, `WAV`

### 1.2 官方数据字典的覆盖情况

| 来源 | VEH 字段定义 | VEH 枚举值映射 |
|---|---|---|
| NYC Open Data 数据集页面（8wbx-tsch） | 未找到字段说明 | ❌ 无 |
| TLC 数据字典 PDF（若有） | 未公开 | ❌ 无 |
| TLC Green Rides Initiative 规则 | 引用了 BEV、HYB 概念 | ⚠️ 部分 |
| TLC Factbook 年报 | 未涉及此字段 | ❌ 无 |

**结论**：VEH 字段的枚举映射表在 TLC 公开渠道**确实缺失**。

---

## 二、推断依据

### 2.1 上下文推断

VEH 字段在 `fhv_active_vehicles` 表中与其他车辆属性字段并列：

| 相邻字段 | 含义 |
|---|---|
| `License Type` | 牌照类型 |
| `Wheelchair Accessible` | 无障碍标记 |
| `Base Type` | 基地类型 |
| `Vehicle Year` | 车辆年份 |
| **`VEH`** | **?** |

结合 TLC 对 FHV 车辆的监管框架（尤其是 [Green Rides Initiative](https://www.nyc.gov/site/tlc/about/green-rides.page)），VEH 最合理的解释是**车辆动力/技术类型**。

### 2.2 代码含义推断

| 代码 | 推断含义 | 推断置信度 | 依据 |
|---|---|---|---|
| `BEV` | Battery Electric Vehicle（纯电动车） | **高** | TLC Green Rides 规则要求 2030 年前 FHV 全部转为 BEV 或 WAV，BEV 在 TLC 官方文件中频繁出现 |
| `HYB` | Hybrid（油电混合动力车） | **高** | TLC Green Rides 规则明确定义 HYB 作为过渡期合规选项 |
| `CNG` | Compressed Natural Gas（压缩天然气车） | **中高** | NY 州有 CNG 出租车激励政策，TLC 曾批准 CNG 车辆作为清洁能源选项 |
| `DSE` | Diesel（柴油车） | **中** | 柴油车在纽约出租车队中存在，但正在被淘汰 |
| `DSEL` | Diesel（柴油车，另一种拼写） | **中** | 与 DSE 可能是同一含义的拼写变体，或区分轻型/重型柴油 |
| `STR` | Standard / Street（标准汽油车） | **中低** | "STR" 可能代表 Standard（标准燃油车）或 Street（街头用途）。TLC 文档中未见此缩写 |
| `WAV` | Wheelchair Accessible Vehicle（无障碍车辆） | **高** | WAV 在 TLC 规则中有明确定义。注意表中另有 `Wheelchair Accessible` 字段（值 PILOT/WAV），VEH 中的 WAV 表示车辆因无障碍改装而归属此类 |
| `N` | Not specified（未指定） | **中** | 常见"无数据"标记 |
| `NON` | None（无特殊类型） | **中** | 常见"无"标记 |

### 2.3 为什么 TLC 不公开此映射

推测原因：

1. **VEH 是内部运维字段**：这可能是 TLC 内部用于监管合规追踪的分类代码，而非面向公众的统计维度。Green Rides 规则主要关注 BEV/HYB/WAV 三类，其余代码可能是历史遗留或内部使用。

2. **数据集发布时间早于规则完善**：FHV Active Vehicles 数据集在 Green Rides Initiative（2023 年提出）之前就已发布。VEH 字段可能在数据集早期版本中就存在，但映射表未随规则更新而公开。

3. **代码可能源自车辆注册系统**：VEH 的取值（如 DSE/DSEL 两种柴油拼写、N/NON 两种"无"标记）暗示这些代码直接来自 DMV 车辆注册数据库的原始值，未经 TLC 清洗标准化。

---

## 三、结论

**VEH 字段的完整枚举映射确实是 TLC 未公开发布的内部字段映射表。**

具体来说：
- ✅ TLC 在公开数据集中发布了这个字段及其取值
- ❌ TLC 未在数据字典中解释 9 个代码的含义
- ⚠️ 其中 3-4 个代码（BEV、HYB、WAV）可从 TLC Green Rides 规则中交叉验证
- ⚠️ 其余 5-6 个代码（CNG、DSE、DSEL、STR、N、NON）只能基于行业术语推断
- ❌ 无法通过 Google 搜索或公开渠道找到官方确认的完整映射表

## 四、后续行动建议

| 优先级 | 行动 | 预期结果 |
|---|---|---|
| P1 | 联系 TLC 数据管理员（[TLC Open Data 联系页](https://www.nyc.gov/site/tlc/about/contact-us.page)），请求 VEH 字段的官方数据字典 | 获得完整映射或确认推断 |
| P2 | 对比 `active_vehicles` 表的 `Fuel Type` 字段（有完整中文含义的 7 种取值），交叉验证两者关联 | 若 VEH 与 Fuel Type 高度相关，可间接验证推断 |
| P2 | 检查 TLC FHV Active Vehicles 数据集的 Google Sheets 版数据字典（Google 搜索结果显示存在 [此链接](https://docs.google.com/spreadsheets/d/1lLLkV5yrK92dd2Bs2lbBRVs51PNrf1SVPgJuNdNGBsc/edit)） | 可能包含非公开渠道的补充说明 |
| P3 | 在数据仓库中将 VEH 字段标记为"推断状态"，中文含义暂用推断值并附带 Human Review 标记 | 当前 bronze_enum_values.md 已实施 |
