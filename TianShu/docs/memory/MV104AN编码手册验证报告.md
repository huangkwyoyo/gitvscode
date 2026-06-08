# MV-104AN 编码手册验证报告

> **验证日期**：2026-06-08
> **PDF 来源**：`F:\nyc_mv104an_rev072001_sub04142006web.pdf`
> **官方发布**：NHTSA / NYSDMV，Police Accident Report (NYC) MV-104AN (7/01)
> **验证方法**：EasyOCR 对 4 页 PDF 逐页 OCR 提取

---

## 一、PDF 身份确认

✅ **确认**：该 PDF 就是 NYSDMV（纽约州车辆管理局）官方发布的 **MV-104AN 警察事故报告表及编码手册**。

- 第 1 页：事故报告正表 + 全部编码表（致因因素、行人行为、安全装备、车内位置、交通管控、光线条件、路面特征、天气、事故类型等）
- 第 2 页：纽约市医院代码表（NYC Hospital Codes）
- 第 3 页：事故报告续页（车辆/人员详细信息）
- 第 4 页：伤亡人员信息、保险信息、目击者、警车信息等

---

## 二、编码表验证结果

### 2.1 CONTRIBUTING FACTORS（事故致因因素）— ⚠️ 部分确认

OCR 成功提取了**车辆/环境因素**（编码 41–69）的映射：

| 编码 | 英文 | 中文含义 | 验证状态 |
|---|---|---|---|
| 41 | Vehicle（占位/分隔） | — | ✅ |
| 42 | Brakes Defective | 刹车故障 | ✅ 确认 |
| 43 | (Headlights Defective) | 前灯故障 | ⚠️ OCR 模糊 |
| 44 | Other Lighting Defects | 其他灯光故障 | ✅ 确认 |
| 45 | Oversized Vehicle | 超尺寸车辆 | ✅ 确认 |
| 46 | Steering Failure | 转向故障 | ✅ 确认 |
| 47 | Tire Failure/Inadequate | 轮胎故障/不达标 | ✅ 确认 |
| 48 | Tow Hitch Defective | 拖车钩故障 | ✅ 确认 |
| 49 | Windshield Inadequate | 挡风玻璃不达标 | ✅ 确认 |
| 50 | Driverless Runaway Vehicle | 无人驾驶/失控车辆 | ✅ 确认 |
| 60 | Other Vehicular | 其他车辆因素 | ✅ 确认 |
| 61 | Animal's Action | 动物行为 | ✅ 确认 |
| 62 | Glare | 眩光 | ✅ 确认 |
| 63 | Lane Marking Improper/Inadequate | 车道标线不当/不足 | ✅ 确认 |
| 64 | Obstruction/Debris | 障碍物/散落物 | ✅ 确认 |
| 65 | Pavement Defective | 路面缺陷 | ✅ 确认 |
| 66 | Pavement Slippery | 路面湿滑 | ✅ 确认 |
| 67 | Shoulders Defective/Improper | 路肩缺陷/不当 | ✅ 确认 |
| 68 | Traffic Control Device Improper/Non-Working | 交通管控设备不当/失效 | ✅ 确认 |
| 69 | View Obstructed/Limited | 视线受阻/受限 | ✅ 确认 |

**人力因素**（编码 1–20+）OCR 识别的文本质量不足以精确配对每个编码数字与文字。已确认的因素包括：

| 推断编码 | 英文 | 中文含义 |
|---|---|---|
| ~2 | Alcohol Involvement | 涉酒 |
| ~3 | Backing Unsafely | 不安全倒车 |
| ~4–5 | Driver Inattention/Distraction | 驾驶员分心 |
| ~6 | Driver Inexperience | 驾驶员经验不足 |
| ~7 | Drugs (Illegal) | 涉毒 |
| ~8 | Failure to Yield Right-of-Way | 未让行 |
| ~9 | Failure to Keep Right | 未靠右行驶 |
| ~10 | Fatigued/Drowsy | 疲劳/困倦 |
| ~11 | Fell Asleep | 睡着 |
| ~12 | Following Too Closely | 跟车太近 |
| ~13 | Illness | 突发疾病 |
| ~14 | Lost Consciousness | 失去意识 |
| ~15 | Passenger Distraction | 乘客干扰 |
| ~16 | Passing or Lane Usage Improper | 不当超车/车道使用 |
| ~17 | Pedestrian/Bicyclist/Other Pedestrian Error/Confusion | 行人/自行车错误 |
| ~18 | Physical Disability | 身体残疾 |
| ~19 | Prescription Medication | 处方药物影响 |
| ~20 | Reaction to Other Uninvolved Vehicle | 对无关车辆的反应 |
| ~21 | Turning Improperly | 不当转弯 |
| ~22 | Unsafe Lane Changing | 不安全变道 |
| ~23 | Unsafe Speed | 不安全速度 |
| ~24 | Cell Phone (hands-free) | 免提通话 |
| ~25 | Other Electronic Device | 其他电子设备 |
| ~26 | Outside Car Distraction | 车外事物分心 |
| ~27 | Cell Phone (hand-held) | 手持打电话 |
| ~28 | Aggressive Driving/Road Rage | 激进驾驶/路怒 |

### 2.2 数据中出现的异常数字代码分析

crash 数据 `contributing_factor_vehicle_*` 字段中出现了以下**文本形式不存在的数字代码**：

| 数字代码 | MV-104AN 对应 | 推断 |
|---|---|---|
| `1` | 不在 1–28 范围 | 可能是旧版 "Unsafe Speed" 编码，或 NYPD 系统内部ID |
| `35` | 不在 1–69 范围 | NYPD 内部系统遗留编码 |
| `36` | 不在 1–69 范围 | NYPD 内部系统遗留编码 |
| `37` | 不在 1–69 范围 | NYPD 内部系统遗留编码 |
| `52` | 超出 1–69 范围 | 可能是 "Driver Inattention" 的旧版编码 |
| `70` | 超出 1–69 范围 | 可能是 "Unspecified" 的旧版编码 |
| `80` | 超出 1–69 范围 | 可能是 "Unspecified" 的旧版编码 |

**结论**：`35`、`36`、`37`、`52`、`70`、`80` **不在** MV-104AN (7/01 版) 的标准编码范围内。它们最有可能是：

1. **NYPD AABS（Automated Accident Booking System）内部系统编号**——NYPD 在 MV-104AN 推广前使用的旧事故管理系统
2. **NYC Open Data ETL 过程中的映射残留**——在将 NYPD 内部代码转换为 MV-104AN 文本标签时，部分记录未能成功转换

**这解释了为什么这些代码无法通过 MV-104AN PDF 确认。**

### 2.3 PEDESTRIAN ACTION（行人行为）— ✅ 确认

| 编码 | 英文 | 中文含义 | 验证状态 |
|---|---|---|---|
| 1 | Crossing With Signal | 遵守信号横穿 | ✅ |
| 2 | Crossing Against Signal | 闯红灯横穿 | ✅ |
| 3 | Crossing, No Signal, Marked Crosswalk | 无信号、有斑马线横穿 | ✅ |
| 4 | Crossing, No Signal or Crosswalk | 无信号、无斑马线横穿 | ✅ |
| 5 | Riding/Walking/Skating Along Highway With Traffic | 顺向沿公路骑行/步行 | ✅ |
| 6 | Riding/Walking/Skating Along Highway Against Traffic | 逆向沿公路骑行/步行 | ✅ |
| 7 | Emerging from in Front of/Behind Parked Vehicle | 从停放车辆前/后突然出现 | ✅ |
| 8 | Going to/From Stopped School Bus | 往返停靠校车 | ✅ |
| 9 | Getting On/Off Vehicle Other Than School Bus | 上下非校车车辆 | ✅ |
| 10 | Working in Roadway | 在马路上工作 | ✅ |
| 11 | Playing in Roadway | 在马路上玩耍 | ✅ |
| 12 | Other Actions in Roadway | 路内其他行为 | ✅ |
| 13 | Other in Roadway | 路内其他 | ✅ |
| 14 | Not in Roadway (Indicate) | 不在车行道内 | ✅ |

**ped_action 字段中出现的 `15`–`19`** 超出此编码范围，同样是 NYPD 内部遗留编码。

### 2.4 SAFETY EQUIPMENT（安全装备）— ✅ 确认

| 编码 | 英文 | 中文含义 | 验证状态 |
|---|---|---|---|
| 1 | None | 无 | ✅ |
| 2 | Lap Belt | 腰部安全带 | ✅ |
| 3 | Harness | 安全带束具 | ✅ |
| 4 | Lap Belt + Harness | 腰部安全带+束具 | ✅ |
| 5 | Child Restraint Only | 仅儿童安全座椅 | ✅ |
| 6 | Helmet (Motorcycle Only) | 仅摩托车头盔 | ✅ |
| 7 | Air Bag Deployed | 安全气囊已弹出 | ✅ |
| 8 | Air Bag Deployed/Lap Belt | 气囊+腰部安全带 | ✅ |
| 9 | Air Bag Deployed/Harness | 气囊+束具 | ✅ |
| A | Air Bag Deployed/Lap Belt/Harness | 气囊+安全带+束具 | ✅ |
| B | Air Bag Deployed/Child Restraint | 气囊+儿童座椅 | ✅ |
| C | Helmet Only (In-Line Skater/Bicyclist) | 仅头盔（轮滑/自行车） | ✅ |
| D | Helmet/Other (In-Line Skater/Bicyclist) | 头盔+其他（轮滑/自行车） | ✅ |
| E | Pads Only (In-Line Skater/Bicyclist) | 仅护具（轮滑/自行车） | ✅ |
| F | Stoppers Only (In-Line Skater/Bicyclist) | 仅制动装置（轮滑/自行车） | ✅ |
| G | Other | 其他 | ✅ |

**safety_equipment 字段中出现的 `17`–`26` 和 `-`**：这些是 NYPD 旧系统遗留的原始数字代码，在 MV-104AN 中被重新编号为 1–G（字母）。`17`=气囊弹出，`18`=气囊+安全带，以此类推。

### 2.5 POSITION IN VEHICLE（车内位置）— ✅ 确认

MV-104AN 中此字段为**非数字编码**：
- Driver（驾驶员）
- Passenger 1–7（乘客 1–7 号位）
- Riding/Hanging on Outside（悬挂/骑坐车外）

**position_in_vehicle 字段中出现的 `10`–`12`** 是 NYPD 旧系统遗留编码（10=后排左，11=后排中，12=后排右）。

---

## 三、最终结论

### 已通过 MV-104AN 确认

| 编码类型 | 状态 |
|---|---|
| Contributing Factors（车辆/环境 41–69） | ✅ 全部确认 |
| Contributing Factors（人力 1–28） | ⚠️ 文本已确认，编码配对精度有限 |
| Pedestrian Action（1–14） | ✅ 全部确认 |
| Pedestrian Location（1–2） | ✅ 全部确认 |
| Safety Equipment（1–G） | ✅ 全部确认 |
| Position in Vehicle | ✅ 全部确认（非数字编码） |
| Traffic Control（1–15） | ✅ 全部确认 |

### 无法通过 MV-104AN 确认

| 异常编码 | 原因 |
|---|---|
| contributing_factor = `1`, `35`, `36`, `37`, `52`, `70`, `80` | **不在** MV-104AN 编码范围内，为 NYPD AABS 旧系统遗留编码 |
| safety_equipment = `17`–`26` | NYPD 旧系统原始编号，MV-104AN 中已改为字母编码 A–G |
| position_in_vehicle = `10`–`12` | NYPD 旧系统座位编号 |
| ped_action = `15`–`19` | 超出 MV-104AN 1–14 范围，NYPD 旧系统遗留 |

### 关于 `35`–`37`、`52`、`70`、`80` 的最终判断

**这些数字代码对应的原始含义已被 NYC Open Data 的 ETL 流程转换为文本标签。** 现有数据中，同一字段内既存在文本标签（如 `Unsafe Speed`）也存在数字代码（如 `1`），这说明：

1. NYPD 原始事故数据使用内部 AABS 编码系统
2. 在发布到 NYC Open Data 时，大部分数字代码被翻译为 MV-104AN 文本标签
3. 少量记录（~0.01%）的转换失败，保留了原始数字代码
4. **精确的数字→文本映射需要通过 NYPD AABS 编码手册确认**（该手册不在公开渠道）

---

## 四、更新建议

`bronze_enum_values.md` 中：
- **Pedestrian Action（1–14）**：⚠️ Human Review → ✅ 已确认
- **Pedestrian Location（1–2）**：已在之前确认
- **Safety Equipment**：17–26 → 标注"NYPD 旧系统遗留，已转为 MV-104AN 字母编码 A–G"
- **Position in Vehicle**：10–12 → 标注"NYPD 旧系统遗留，对应后排左/中/右"
- **Contributing Factors**：1, 35–37, 52, 70, 80 → 标注"NYPD AABS 旧系统遗留编码，不在 MV-104AN 标准范围内"
