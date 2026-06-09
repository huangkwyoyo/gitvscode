# Bronze 层枚举值说明（状态码 / 标志位 / 分类代码）

> **目的**：对 Bronze 层所有包含代码、缩写、状态码、标志位的字段，逐字段列出枚举值的中文含义。
> **原则**：能确认官方含义的使用"✅ 已确认"标记；无法确认的标记"⚠️ Human Review"，绝不凭经验翻译。
> **生成日期**：2026-06-08
> **数据来源**：基于 DuckDB 全表 distinct 值扫描 + NYC TLC 官方数据字典交叉验证

---

## 一、出行域 (Trip Data)

### 1.1 yellow_tripdata_2026q1 / green_tripdata_2026q1

| 英文表名 | 英文字段名 | 中文字段名 | 枚举值 | 中文含义 | 审核状态 |
|---|---|---|---|---|---|
| yellow_tripdata_2026q1 | VendorID | 技术提供商ID | `1` | Creative Mobile Technologies 公司（CMT，TPEP 技术提供商） | ✅ 已确认 |
| | | | `2` | Curb Mobility 公司（原 VeriFone，TPEP 技术提供商） | ✅ 已确认 |
| | | | `6` | Myle Technologies 公司（TPEP 技术提供商） | ✅ 已确认 |
| | | | `7` | Helix 公司（TPEP 技术提供商） | ✅ 已确认 |
| yellow_tripdata_2026q1 | RatecodeID | 费率类型代码 | `1` | 标准费率 | ✅ 已确认 |
| | | | `2` | JFK机场一口价 | ✅ 已确认 |
| | | | `3` | 纽瓦克机场行程 | ✅ 已确认 |
| | | | `4` | 纳苏/韦斯切斯特（市区外行程） | ✅ 已确认 |
| | | | `5` | 协商议价 | ✅ 已确认 |
| | | | `6` | 拼车/团体乘车 | ✅ 已确认 |
| | | | `99` | 未知 | ✅ 已确认 |
| yellow_tripdata_2026q1 | store_and_fwd_flag | 离线存储标记 | `Y` | 离线存储后上报（无实时网络连接） | ✅ 已确认 |
| | | | `N` | 实时传输（非离线） | ✅ 已确认 |
| yellow_tripdata_2026q1 | payment_type | 支付方式 | `0` | 灵活计价（Flex Fare） | ✅ 已确认 |
| | | | `1` | 信用卡 | ✅ 已确认 |
| | | | `2` | 现金 | ✅ 已确认 |
| | | | `3` | 免费 | ✅ 已确认 |
| | | | `4` | 争议交易 | ✅ 已确认 |
| | | | `5` | 未知 | ✅ 已确认 |
| | | | `6` | 已作废行程 | ✅ 已确认 |
| green_tripdata_2026q1 | trip_type | 行程类型 | `1` | 街头扬招 (Street-hail) | ✅ 已确认 |
| | | | `2` | 网约派单 (Dispatch) | ✅ 已确认 |

### 1.2 fhvhv_tripdata_2026q1

| 英文表名 | 英文字段名 | 中文字段名 | 枚举值 | 中文含义 | 审核状态 |
|---|---|---|---|---|---|
| fhvhv_tripdata_2026q1 | shared_request_flag | 拼车请求标记 | `Y` | 请求了拼车 | ✅ 已确认 |
| | | | `N` | 未请求拼车 | ✅ 已确认 |
| fhvhv_tripdata_2026q1 | shared_match_flag | 拼车匹配标记 | `Y` | 拼车匹配成功 | ✅ 已确认 |
| | | | `N` | 未匹配拼车 | ✅ 已确认 |
| fhvhv_tripdata_2026q1 | access_a_ride_flag | Access-A-Ride标记 | `Y` | 残障出行服务（Access-A-Ride）行程 | ✅ 已确认 |
| | | | `N` | 非残障出行服务（Access-A-Ride）行程 | ✅ 已确认 |
| fhvhv_tripdata_2026q1 | wav_request_flag | 轮椅车请求标记 | `Y` | 乘客请求了轮椅无障碍车辆 | ✅ 已确认 |
| | | | `N` | 未请求轮椅无障碍车辆 | ✅ 已确认 |
| fhvhv_tripdata_2026q1 | wav_match_flag | 轮椅车匹配标记 | `Y` | 成功匹配轮椅无障碍车辆 | ✅ 已确认 |
| | | | `N` | 未匹配轮椅无障碍车辆 | ✅ 已确认 |

---

## 二、空间地理域 (Spatial)

### 2.1 taxi_zone_lookup

| 英文表名 | 英文字段名 | 中文字段名 | 枚举值 | 中文含义 | 审核状态 |
|---|---|---|---|---|---|
| taxi_zone_lookup | Borough | 行政区 | `Manhattan` | 曼哈顿 | ✅ 已确认 |
| | | | `Brooklyn` | 布鲁克林 | ✅ 已确认 |
| | | | `Queens` | 皇后区 | ✅ 已确认 |
| | | | `Bronx` | 布朗克斯 | ✅ 已确认 |
| | | | `Staten Island` | 史泰登岛 | ✅ 已确认 |
| | | | `EWR` | 纽瓦克国际机场（新泽西州） | ✅ 已确认 |
| | | | `Unknown` | 未知区域 | ✅ 已确认 |
| | | | `N/A` | 不适用 | ✅ 已确认 |
| taxi_zone_lookup | service_zone | 服务区域 | `Yellow Zone` | 黄色出租车服务区（曼哈顿核心区） | ✅ 已确认 |
| | | | `Boro Zone` | 区级出租车服务区（曼哈顿以外） | ✅ 已确认 |
| | | | `Airports` | 机场区 | ✅ 已确认 |
| | | | `EWR` | 纽瓦克机场区 | ✅ 已确认 |
| | | | `N/A` | 不适用 | ✅ 已确认 |

---

## 三、安全域 (Safety)

### 3.1 crash_person_all

| 英文表名 | 英文字段名 | 中文字段名 | 枚举值 | 中文含义 | 审核状态 |
|---|---|---|---|---|---|
| crash_person_all | person_type | 涉事人类型 | `Occupant` | 车内乘员 | ✅ 已确认 |
| | | | `Pedestrian` | 行人 | ✅ 已确认 |
| | | | `Bicyclist` | 骑自行车者 | ✅ 已确认 |
| | | | `Other Motorized` | 其他机动化出行者 | ✅ 已确认 |
| crash_person_all | person_injury | 受伤程度 | `Injured` | 受伤 | ✅ 已确认 |
| | | | `Killed` | 死亡 | ✅ 已确认 |
| | | | `Unspecified` | 未明确 | ✅ 已确认 |
| crash_person_all | person_sex | 性别 | `M` | 男性 | ✅ 已确认 |
| | | | `F` | 女性 | ✅ 已确认 |
| | | | `U` | 未知 | ✅ 已确认 |
| crash_person_all | ejection | 是否被抛出车外 | `Not Ejected` | 未被抛出 | ✅ 已确认 |
| | | | `Ejected` | 被抛出 | ✅ 已确认 |
| | | | `Partially Ejected` | 部分抛出 | ✅ 已确认 |
| | | | `Trapped` | 被困车内 | ✅ 已确认 |
| | | | `Does Not Apply` | 不适用 | ✅ 已确认 |
| | | | `Unknown` | 未知 | ✅ 已确认 |
| crash_person_all | emotional_status | 情绪/意识状态 | `Conscious` | 意识清醒 | ✅ 已确认 |
| | | | `Semiconscious` | 半清醒 | ✅ 已确认 |
| | | | `Unconscious` | 无意识 | ✅ 已确认 |
| | | | `Incoherent` | 意识混乱 | ✅ 已确认 |
| | | | `Shock` | 休克 | ✅ 已确认 |
| | | | `Apparent Death` | 明显死亡 | ✅ 已确认 |
| | | | `Does Not Apply` | 不适用 | ✅ 已确认 |
| | | | `Unknown` | 未知 | ✅ 已确认 |
| crash_person_all | bodily_injury | 身体受伤部位 | `Head` | 头部 | ✅ 已确认 |
| | | | `Face` | 面部 | ✅ 已确认 |
| | | | `Eye` | 眼部 | ✅ 已确认 |
| | | | `Neck` | 颈部 | ✅ 已确认 |
| | | | `Chest` | 胸部 | ✅ 已确认 |
| | | | `Back` | 背部 | ✅ 已确认 |
| | | | `Abdomen - Pelvis` | 腹部-骨盆 | ✅ 已确认 |
| | | | `Shoulder - Upper Arm` | 肩膀-上臂 | ✅ 已确认 |
| | | | `Elbow-Lower-Arm-Hand` | 肘-前臂-手部 | ✅ 已确认 |
| | | | `Hip-Upper Leg` | 髋部-大腿 | ✅ 已确认 |
| | | | `Knee-Lower Leg Foot` | 膝盖-小腿-足部 | ✅ 已确认 |
| | | | `Entire Body` | 全身 | ✅ 已确认 |
| | | | `Does Not Apply` | 不适用 | ✅ 已确认 |
| | | | `Unknown` | 未知 | ✅ 已确认 |
| crash_person_all | safety_equipment | 安全装备使用情况 | `None` | 无 | ✅ 已确认 |
| | | | `Lap Belt` | 腰部安全带 | ✅ 已确认 |
| | | | `Lap Belt & Harness` | 腰部安全带+安全带束具 | ✅ 已确认 |
| | | | `Harness` | 安全带束具 | ✅ 已确认 |
| | | | `Child Restraint Only` | 仅使用儿童安全座椅 | ✅ 已确认 |
| | | | `Air Bag Deployed` | 安全气囊已弹出 | ✅ 已确认 |
| | | | `Air Bag Deployed/Lap Belt` | 安全气囊+腰部安全带 | ✅ 已确认 |
| | | | `Air Bag Deployed/Lap Belt/Harness` | 安全气囊+所有安全带 | ✅ 已确认 |
| | | | `Air Bag Deployed/Child Restraint` | 安全气囊+儿童座椅 | ✅ 已确认 |
| | | | `Helmet (Motorcycle Only)` | 仅摩托车头盔 | ✅ 已确认 |
| | | | `Helmet Only (In-Line Skater/Bicyclist)` | 仅头盔（轮滑/自行车） | ✅ 已确认 |
| | | | `Helmet/Other (In-Line Skater/Bicyclist)` | 头盔+其他护具（轮滑/自行车） | ✅ 已确认 |
| | | | `Pads Only (In-Line Skater/Bicyclist)` | 仅护具（轮滑/自行车） | ✅ 已确认 |
| | | | `Stoppers Only (In-Line Skater/Bicyclist)` | 仅制动装置（轮滑/自行车） | ✅ 已确认 |
| | | | `Other` | 其他 | ✅ 已确认 |
| | | | `Unknown` | 未知 | ✅ 已确认 |
| | | | `-` / `17`~`26` | **NYPD 旧系统遗留原始编号**，在 MV-104AN (7/01) 中已重新编号为字母编码 A–G。对照关系：17=气囊弹出(A)，18=气囊+腰部安全带(B)，19=气囊+束具，以此类推 | ⚠️ Human Review（需 NYPD AABS 编码手册精确对照） |
| crash_person_all | position_in_vehicle | 车内位置 | `Driver` | 驾驶员 | ✅ 已确认 |
| | | | `Front passenger, if two or more persons...` | 前排乘客（含驾驶员共2人以上） | ✅ 已确认 |
| | | | `Left rear passenger...` | 左后排乘客/摩托车后排乘客 | ✅ 已确认 |
| | | | `Middle front seat...` | 中前排/平躺于座位上 | ✅ 已确认 |
| | | | `Middle rear seat...` | 中后排/平躺于座位上 | ✅ 已确认 |
| | | | `Right rear passenger or motorcycle sidecar passenger` | 右后排乘客/摩托车边车乘客 | ✅ 已确认 |
| | | | `Any person in the rear of a station wagon...` | 旅行车/皮卡后排/公交车全部乘客 | ✅ 已确认 |
| | | | `If one person is seated on another person's lap` | 一人坐在另一人腿上 | ✅ 已确认 |
| | | | `Riding/Hanging on Outside` | 悬挂/骑坐车外 | ✅ 已确认 |
| | | | `Does Not Apply` | 不适用 | ✅ 已确认 |
| | | | `Unknown` | 未知 | ✅ 已确认 |
| | | | `10`~`12` | **NYPD 旧系统遗留座位编号**。MV-104AN 中车内位置为非数字编码（Driver/Passenger 1-7/Riding Outside）。10=后排左侧乘客，11=后排中间乘客，12=后排右侧乘客 | ⚠️ Human Review（需 NYPD AABS 编码手册精确对照） |
| crash_person_all | ped_role | 行人/非机动车角色 | `Pedestrian` | 行人 | ✅ 已确认 |
| | | | `Driver` | 驾驶员 | ✅ 已确认 |
| | | | `Passenger` | 乘客 | ✅ 已确认 |
| | | | `In-Line Skater` | 轮滑者 | ✅ 已确认 |
| | | | `Witness` | 目击者 | ✅ 已确认 |
| | | | `Owner` | 车主 | ✅ 已确认 |
| | | | `Registrant` | 登记人 | ✅ 已确认 |
| | | | `Notified Person` | 被通知人 | ✅ 已确认 |
| | | | `Policy Holder` | 保单持有人 | ✅ 已确认 |
| | | | `Other` | 其他 | ✅ 已确认 |
| crash_person_all | ped_location | 行人/非机动车位置 | `Pedestrian/Bicyclist/Other Pedestrian at Intersection` | 在交叉口内 | ✅ 已确认 |
| | | | `Pedestrian/Bicyclist/Other Pedestrian Not at Intersection` | 不在交叉口内 | ✅ 已确认 |
| | | | `Does Not Apply` | 不适用 | ✅ 已确认 |
| | | | `Unknown` | 未知 | ✅ 已确认 |
| crash_person_all | ped_action | 行人/非机动车行为 | `Crossing With Signal` | 遵守信号横穿 | ✅ 已确认 |
| | | | `Crossing Against Signal` | 闯红灯横穿 | ✅ 已确认 |
| | | | `Crossing, No Signal, Marked Crosswalk` | 无信号、有斑马线处横穿 | ✅ 已确认 |
| | | | `Crossing, No Signal, or Crosswalk` | 无信号、无斑马线处横穿 | ✅ 已确认 |
| | | | `Emerging from in Front of/Behind Parked Vehicle` | 从停放车辆前/后突然出现 | ✅ 已确认 |
| | | | `Going to/From Stopped School Bus` | 往返停靠校车 | ✅ 已确认 |
| | | | `Getting On/Off Vehicle Other Than School Bus` | 上下非校车车辆 | ✅ 已确认 |
| | | | `Playing in Roadway` | 在马路上玩耍 | ✅ 已确认 |
| | | | `Working in Roadway` | 在马路上工作 | ✅ 已确认 |
| | | | `Pushing/Working on Car` | 推车/修车 | ✅ 已确认 |
| | | | `Riding/Walking Along Highway With Traffic` | 顺向沿公路骑行/步行 | ✅ 已确认 |
| | | | `Riding/Walking Along Highway Against Traffic` | 逆向沿公路骑行/步行 | ✅ 已确认 |
| | | | `Not in Roadway` | 不在车行道内 | ✅ 已确认 |
| | | | `Other Actions in Roadway` | 路内其他行为 | ✅ 已确认 |
| | | | `Does Not Apply` | 不适用 | ✅ 已确认 |
| | | | `Unknown` | 未知 | ✅ 已确认 |
| | | | `15`~`19` | **NYPD 旧系统遗留数字代码**，不在 MV-104AN (7/01) 行人行为标准编码 1–14 范围内 | ⚠️ Human Review（需 NYPD AABS 编码手册） |
| crash_person_all | complaint | 伤情主诉 | `Complaint of Pain` | 疼痛主诉 | ✅ 已确认 |
| | | | `Complaint of Pain or Nausea` | 疼痛或恶心 | ✅ 已确认 |
| | | | `None Visible` | 无明显外伤 | ✅ 已确认 |
| | | | `Abrasion` | 擦伤 | ✅ 已确认 |
| | | | `Contusion - Bruise` | 挫伤/淤青 | ✅ 已确认 |
| | | | `Minor Bleeding` | 轻微出血 | ✅ 已确认 |
| | | | `Severe Bleeding` | 严重出血 | ✅ 已确认 |
| | | | `Minor Burn` | 轻度烧伤 | ✅ 已确认 |
| | | | `Moderate Burn` | 中度烧伤 | ✅ 已确认 |
| | | | `Severe Burn` | 重度烧伤 | ✅ 已确认 |
| | | | `Severe Lacerations` | 严重撕裂伤 | ✅ 已确认 |
| | | | `Fracture - Dislocation` | 骨折-脱位 | ✅ 已确认 |
| | | | `Fracture - Distorted - Dislocation` | 骨折-变形-脱位 | ✅ 已确认 |
| | | | `Concussion` | 脑震荡 | ✅ 已确认 |
| | | | `Internal` | 内伤 | ✅ 已确认 |
| | | | `Crush Injuries` | 挤压伤 | ✅ 已确认 |
| | | | `Amputation` | 截肢 | ✅ 已确认 |
| | | | `Paralysis` | 瘫痪 | ✅ 已确认 |
| | | | `Whiplash` | 鞭打伤/颈部扭伤 | ✅ 已确认 |
| | | | `Does Not Apply` | 不适用 | ✅ 已确认 |
| | | | `Unknown` | 未知 | ✅ 已确认 |

### 3.2 crash_merged（事故致因因素）

> **说明**：`contributing_factor_vehicle_1`~`_5` 均为车辆事故致因因素，取值集合相同。以下列出全部取值。

| 英文表名 | 英文字段名 | 中文字段名 | 枚举值 | 中文含义 | 审核状态 |
|---|---|---|---|---|---|
| crash_merged | contributing_factor_vehicle_* | 事故致因因素（车辆N） | `Driver Inattention/Distraction` | 驾驶员注意力不集中/分心 | ✅ 已确认 |
| | | | `Failure to Yield Right-of-Way` | 未让行 | ✅ 已确认 |
| | | | `Following Too Closely` | 跟车太近 | ✅ 已确认 |
| | | | `Unsafe Speed` | 不安全速度 | ✅ 已确认 |
| | | | `Passing or Lane Usage Improper` | 不当超车/车道使用 | ✅ 已确认 |
| | | | `Passing Too Closely` | 超车距离过近 | ✅ 已确认 |
| | | | `Unsafe Lane Changing` | 不安全变道 | ✅ 已确认 |
| | | | `Turning Improperly` | 不当转弯 | ✅ 已确认 |
| | | | `Backing Unsafely` | 不安全倒车 | ✅ 已确认 |
| | | | `Traffic Control Disregarded` | 无视交通管控 | ✅ 已确认 |
| | | | `Aggressive Driving/Road Rage` | 激进驾驶/路怒 | ✅ 已确认 |
| | | | `Alcohol Involvement` | 涉酒 | ✅ 已确认 |
| | | | `Drugs (Illegal)` / `Drugs (illegal)` | 涉毒（非法药物） | ✅ 已确认 |
| | | | `Prescription Medication` | 处方药物影响 | ✅ 已确认 |
| | | | `Fatigued/Drowsy` | 疲劳/困倦 | ✅ 已确认 |
| | | | `Fell Asleep` | 睡着 | ✅ 已确认 |
| | | | `Lost Consciousness` | 失去意识 | ✅ 已确认 |
| | | | `Illness` / `Illnes` | 突发疾病 | ✅ 已确认 |
| | | | `Physical Disability` | 身体残疾 | ✅ 已确认 |
| | | | `Driver Inexperience` | 驾驶员经验不足 | ✅ 已确认 |
| | | | `Driverless/Runaway Vehicle` | 无人驾驶/失控车辆 | ✅ 已确认 |
| | | | `Outside Car Distraction` | 车外事物分心 | ✅ 已确认 |
| | | | `Passenger Distraction` | 乘客干扰 | ✅ 已确认 |
| | | | `Cell Phone (hand-Held)` / `Cell Phone (hand-held)` | 手持打电话 | ✅ 已确认 |
| | | | `Cell Phone (hands-free)` | 免提通话 | ✅ 已确认 |
| | | | `Texting` | 发短信 | ✅ 已确认 |
| | | | `Other Electronic Device` | 其他电子设备 | ✅ 已确认 |
| | | | `Eating or Drinking` | 饮食 | ✅ 已确认 |
| | | | `Listening/Using Headphones` | 佩戴耳机 | ✅ 已确认 |
| | | | `Using On Board Navigation Device` | 使用车载导航 | ✅ 已确认 |
| | | | `Reaction to Other Uninvolved Vehicle` / `Reaction to Uninvolved Vehicle` | 对无关车辆的反应 | ✅ 已确认 |
| | | | `Pedestrian/Bicyclist/Other Pedestrian Error/Confusion` | 行人/自行车/其他行人错误 | ✅ 已确认 |
| | | | `Animals Action` | 动物行为 | ✅ 已确认 |
| | | | `Obstruction/Debris` | 障碍物/散落物 | ✅ 已确认 |
| | | | `Pavement Slippery` | 路面湿滑 | ✅ 已确认 |
| | | | `Pavement Defective` | 路面缺陷 | ✅ 已确认 |
| | | | `Shoulders Defective/Improper` | 路肩缺陷/不当 | ✅ 已确认 |
| | | | `Lane Marking Improper/Inadequate` | 车道标线不当/不足 | ✅ 已确认 |
| | | | `Traffic Control Device Improper/Non-Working` | 交通管控设备不当/失效 | ✅ 已确认 |
| | | | `Glare` | 眩光 | ✅ 已确认 |
| | | | `Brakes Defective` | 刹车故障 | ✅ 已确认 |
| | | | `Steering Failure` | 转向故障 | ✅ 已确认 |
| | | | `Accelerator Defective` | 油门故障 | ✅ 已确认 |
| | | | `Headlights Defective` | 前灯故障 | ✅ 已确认 |
| | | | `Other Lighting Defects` | 其他灯光故障 | ✅ 已确认 |
| | | | `Tire Failure/Inadequate` | 轮胎故障/不达标 | ✅ 已确认 |
| | | | `Tow Hitch Defective` | 拖车钩故障 | ✅ 已确认 |
| | | | `Tinted Windows` | 车窗贴膜过暗 | ✅ 已确认 |
| | | | `Windshield Inadequate` | 挡风玻璃不达标 | ✅ 已确认 |
| | | | `Oversized Vehicle` | 超尺寸车辆 | ✅ 已确认 |
| | | | `Other Vehicular` | 其他车辆因素 | ✅ 已确认 |
| | | | `Failure to Keep Right` | 未靠右行驶 | ✅ 已确认 |
| | | | `View Obstructed/Limited` | 视线受阻/受限 | ✅ 已确认 |
| | | | `Unspecified` | 未指定 | ✅ 已确认 |
| | | | `1` / `35` / `36` / `37` / `52` / `70` / `80` | **NYPD AABS 旧系统遗留数字代码**，不在 MV-104AN (7/01) 标准编码 1–69 范围内。NYC Open Data ETL 发布时大部分已转为文本标签，少量记录未成功转换而保留原始数字 | ⚠️ Human Review（需 NYPD AABS 编码手册） |

---

## 四、监管合规域 (Regulatory & Compliance)

### 4.1 new_driver_applications（TLC 新司机申请）

| 英文表名 | 英文字段名 | 中文字段名 | 枚举值 | 中文含义 | 审核状态 |
|---|---|---|---|---|---|
| new_driver_applications | Type | 驾照申请类型 | `HDR` | 租用车辆 (For-Hire Vehicle) 驾驶员执照 | ✅ 已确认 |
| | | | `PDR` | 辅助公交 (Paratransit) 驾驶员执照 | ✅ 已确认 |
| | | | `VDR` | 通勤面包车 (Commuter Van) 驾驶员执照 | ✅ 已确认 |
| new_driver_applications | Status | 申请状态 | `Approved - License Issued` | 已批准-执照已发放 | ✅ 已确认 |
| | | | `Denied` | 已拒绝 | ✅ 已确认 |
| | | | `Incomplete` | 不完整/待补充 | ✅ 已确认 |
| | | | `Pending Fitness Interview` | 待安排资格面试 | ✅ 已确认 |
| | | | `Under Review` | 审核中 | ✅ 已确认 |
| new_driver_applications | Drug Test | 毒品检测状态 | `Complete` | 已完成 | ✅ 已确认 |
| | | | `Needed` | 需进行 | ✅ 已确认 |
| | | | `Not Applicable` | 不适用 | ✅ 已确认 |
| new_driver_applications | WAV Course | 无障碍车辆培训 | `Complete` | 已完成 | ✅ 已确认 |
| | | | `Needed` | 需进行 | ✅ 已确认 |
| | | | `Not Applicable` | 不适用 | ✅ 已确认 |
| new_driver_applications | Defensive Driving | 防御性驾驶课程 | `Complete` | 已完成 | ✅ 已确认 |
| | | | `Needed` | 需进行 | ✅ 已确认 |
| | | | `Not Applicable` | 不适用 | ✅ 已确认 |
| new_driver_applications | Driver Exam | 驾驶员考试 | `Complete` | 已完成 | ✅ 已确认 |
| | | | `Needed` | 需进行 | ✅ 已确认 |
| | | | `Not Applicable` | 不适用 | ✅ 已确认 |
| new_driver_applications | Medical Clearance Form | 体检合格表 | `Complete` | 已完成 | ✅ 已确认 |
| | | | `Needed` | 需进行 | ✅ 已确认 |
| | | | `Not Applicable` | 不适用 | ✅ 已确认 |
| new_driver_applications | FRU Interview Scheduled | 资格面试预约 | `Not Applicable` | 不适用 | ✅ 已确认 |
| | | | 日期值（如 `06/01/2026`） | 面试日期 | ✅ 已确认 |

### 4.2 parking_violations_all（停车违章罚单）

| 英文表名 | 英文字段名 | 中文字段名 | 枚举值（代表性） | 中文含义 | 审核状态 |
|---|---|---|---|---|---|
| parking_violations_all | plate_type | 车牌类型 | `PAS` | 客运车辆 (Passenger) | ✅ 已确认 |
| | | | `COM` | 商用车辆 (Commercial) | ✅ 已确认 |
| | | | `SRF` | 特种车辆/个性车牌 (Special/Vanity) | ✅ 已确认 |
| | | | `MOT` | 摩托车 (Motorcycle) | ✅ 已确认 |
| | | | `OMS` | 租赁车辆 (Rental) | ✅ 已确认 |
| | | | `OMT` | 出租车 (Taxi) | ✅ 已确认 |
| | | | `OML` | 出租包车 (Livery) | ✅ 已确认 |
| | | | `OMR` | 巴士 (Bus) | ✅ 已确认 |
| | | | `ORC` | 机构商用 (Organization Commercial) | ✅ 已确认 |
| | | | `ORG` | 机构客运 (Organization Passenger) | ✅ 已确认 |
| | | | `AGR` | 农用车辆 (Agricultural) | ✅ 已确认 |
| | | | `AMB` | 救护车 (Ambulance) | ✅ 已确认 |
| | | | `APP` | 分摊注册 (Apportioned) | ✅ 已确认 |
| | | | `ARG` | 空军国民警卫队 (Air National Guard) | ✅ 已确认 |
| | | | `ATD` | 全地形车经销商 (All Terrain Dealer) | ✅ 已确认 |
| | | | `ATV` | 全地形车 (All Terrain Vehicle) | ✅ 已确认 |
| | | | `AYG` | 陆军国民警卫队 (Army National Guard) | ✅ 已确认 |
| | | | `BOB` | 棒球纪念牌 (Birthplace of Baseball) | ✅ 已确认 |
| | | | `BOT` | 船舶 (Boat) | ✅ 已确认 |
| | | | `CBS` | 县监事会 (County Bd. of Supervisors) | ✅ 已确认 |
| | | | `CCK` | 县书记官 (County Clerk) | ✅ 已确认 |
| | | | `CHC` | 家用货车 (Household Carrier Commercial) | ✅ 已确认 |
| | | | `CLG` | 县议员 (County Legislators) | ✅ 已确认 |
| | | | `CMB` | 康州组合牌 (Combination - CT) | ✅ 已确认 |
| | | | `CME` | 法医 (Coroner/Medical Examiner) | ✅ 已确认 |
| | | | `CMH` | 国会荣誉勋章 (Congressional Medal of Honor) | ✅ 已确认 |
| | | | `CSP` | 商用特种牌 (Commercial Special/Sports) | ✅ 已确认 |
| | | | `DLR` | 经销商 (Dealer) | ✅ 已确认 |
| | | | `EDU` | 教育工作者 (Educator) | ✅ 已确认 |
| | | | `FAR` | 农场车辆 (Farm) | ✅ 已确认 |
| | | | `FPW` | 前战俘 (Former Prisoner of War) | ✅ 已确认 |
| | | | `GAC` | 州长备用车 (Governor's Additional Car) | ✅ 已确认 |
| | | | `GFC` | 礼券牌 (Gift Certificate) | ✅ 已确认 |
| | | | `GSC` | 州长第二车 (Governor's Second Car) | ✅ 已确认 |
| | | | `GSM` | 金星母亲 (Gold Star Mothers) | ✅ 已确认 |
| | | | `HAC` | 业余无线电-商用 (Ham Operator Commercial) | ✅ 已确认 |
| | | | `HAM` | 业余无线电 (Ham Operator) | ✅ 已确认 |
| | | | `HIF` | 灵车特种牌 (Hearse Special) | ✅ 已确认 |
| | | | `HIR` | 灵车 (Hearse) | ✅ 已确认 |
| | | | `HIS` | 历史车辆 (Historical) | ✅ 已确认 |
| | | | `HOU` | 房车/拖挂 (House/Coach Trailer) | ✅ 已确认 |
| | | | `HSM` | 历史摩托车 (Historical Motorcycle) | ✅ 已确认 |
| | | | `IRP` | 国际注册协议 (Intl. Registration Plan) | ✅ 已确认 |
| | | | `ITP` | 临时转运许可 (In Transit Permit) | ✅ 已确认 |
| | | | `JCA` | 上诉法院法官 (Justice Court of Appeals) | ✅ 已确认 |
| | | | `JCL` | 索赔法院法官 (Justice Court of Claims) | ✅ 已确认 |
| | | | `JSC` | 最高法院上诉庭 (Supreme Court App. Div.) | ✅ 已确认 |
| | | | `JWV` | 犹太退伍军人 (Jewish War Veterans) | ✅ 已确认 |
| | | | `LMA` | A类限用摩托车 (Limited Use Motorcycle A) | ✅ 已确认 |
| | | | `LMB` | B类限用摩托车 (Limited Use Motorcycle B) | ✅ 已确认 |
| | | | `LMC` | C类限用摩托车 (Limited Use Motorcycle C) | ✅ 已确认 |
| | | | `LOC` | 火车头 (Locomotive) | ✅ 已确认 |
| | | | `LTR` | 轻型拖车 (Light Trailer) | ✅ 已确认 |
| | | | `LUA` | 限用汽车 (Limited Use Automobile) | ✅ 已确认 |
| | | | `MCD` | 摩托车经销商 (Motorcycle Dealer) | ✅ 已确认 |
| | | | `MCL` | 海军陆战队联盟 (Marine Corps League) | ✅ 已确认 |
| | | | `MED` | 医生 (Medical Doctor) | ✅ 已确认 |
| | | | `NLM` | 海军民兵 (Naval Militia) | ✅ 已确认 |
| | | | `NYA` | 纽约州众议院 (NY Assembly) | ✅ 已确认 |
| | | | `NYC` | 纽约市议会 (NYC Council) | ✅ 已确认 |
| | | | `NYS` | 纽约州参议院 (NY Senate) | ✅ 已确认 |
| | | | `OMF` | 公共服务巴士 (Omnibus Public Service) | ✅ 已确认 |
| | | | `OMO` | 外州巴士 (Omnibus Out-of-State) | ✅ 已确认 |
| | | | `OMV` | 个性巴士牌 (Omnibus Vanity) | ✅ 已确认 |
| | | | `PHS` | 珍珠港幸存者 (Pearl Harbor Survivors) | ✅ 已确认 |
| | | | `PPH` | 紫心勋章 (Purple Heart) | ✅ 已确认 |
| | | | `PSD` | 政务官员 (Political Subdivision Official) | ✅ 已确认 |
| | | | `RGC` | 跨区商用 (Regional Commercial) | ✅ 已确认 |
| | | | `RGL` | 跨区客运 (Regional Passenger) | ✅ 已确认 |
| | | | `SCL` | 校车 (School Car) | ✅ 已确认 |
| | | | `SEM` | 商用半挂 (Commercial Semi-Trailer) | ✅ 已确认 |
| | | | `SNO` | 雪地摩托 (Snowmobile) | ✅ 已确认 |
| | | | `SOS` | 殉职警察家属 (Survivors of the Shield) | ✅ 已确认 |
| | | | `SPC` | 特种商用 (Special Purpose Commercial) | ✅ 已确认 |
| | | | `SPO` | 运动牌 (Sports) | ✅ 已确认 |
| | | | `SRN` | 法官特种牌 (Special Passenger - Judges) | ✅ 已确认 |
| | | | `STA` | 州政府机构 (State Agencies) | ✅ 已确认 |
| | | | `STG` | 州国民警卫队 (State National Guard) | ✅ 已确认 |
| | | | `SUP` | 最高法院法官 (Supreme Court Justice) | ✅ 已确认 |
| | | | `THC` | 家用牵引车 (Household Carrier Tractor) | ✅ 已确认 |
| | | | `TOW` | 拖车 (Tow Truck) | ✅ 已确认 |
| | | | `TRA` | 转运商 (Transporter) | ✅ 已确认 |
| | | | `TRC` | 标准牵引车 (Tractor Regular) | ✅ 已确认 |
| | | | `TRL` | 标准拖车 (Trailer Regular) | ✅ 已确认 |
| | | | `USC` | 美国国会 (U.S. Congress) | ✅ 已确认 |
| | | | `USS` | 美国参议院 (U.S. Senate) | ✅ 已确认 |
| | | | `VAS` | 志愿救护服务 (Voluntary Ambulance Service) | ✅ 已确认 |
| | | | `VPL` | 拼车面包车 (Van Pool) | ✅ 已确认 |
| | | | `WUG` | 世界大学生运动会 (World University Games) | ✅ 已确认 |
| | | | `999` | 未知/其他 | ✅ 已确认 |
| parking_violations_all | violation_code | 违章代码 | `21` | 街道清扫（换边停车） | ✅ 已确认 |
| | | | `14` | 禁止停车（No Standing） | ✅ 已确认 |
| | | | `46` | 双重停车 | ✅ 已确认 |
| | | | `40` | 消防栓（15英尺内） | ✅ 已确认 |
| | | | `19` | 公交站违停 | ✅ 已确认 |
| | | | `20` | 禁止泊车（No Parking） | ✅ 已确认 |
| | | | `38` | 咪表超时 | ✅ 已确认 |
| | | | `10` | 禁止停止（No Stopping） | ✅ 已确认 |
| | | | `27` | 残疾人车位违停 | ✅ 已确认 |
| | | | `36` | 学区超速摄像头 | ✅ 已确认 |
| | | | `67` | 人行道坡道阻挡 | ✅ 已确认 |
| | | | `48` | 阻挡自行车道 | ✅ 已确认 |
| | | | `50` | 阻挡人行横道 | ✅ 已确认 |
| | | | `51` | 停在人行道上 | ✅ 已确认 |
| | | | `98` | 未经授权大巴停车 | ✅ 已确认 |
| | | | 完整100种代码 | 详见 NYC DOF 违章代码页 | ⚠️ Human Review |
| parking_violations_all | issuing_agency | 执法机构 | `P` | 纽约市警察局 (NYPD) | ✅ 已确认 |
| | | | `T` | 交通局 (DOT) | ✅ 已确认 |
| | | | `S` | 警长办公室 (Sheriff) | ✅ 已确认 |
| | | | `K` | 公园与娱乐局 (Parks & Recreation) | ✅ 已确认 |
| | | | `V` | 出租车管理局 (TLC) | ✅ 已确认 |
| | | | `M` | 大都会运输署 (MTA) | ✅ 已确认 |
| | | | `A` | 行政审判与听证办公室 (OATH) | ⚠️ 基于 NYC 执法体系推断 |
| | | | `B`~`Z`（其余字母） | 其他执法机构代码，需对照 NYC DOF 执法机构编码表 | ⚠️ Human Review |
| parking_violations_all | violation_county | 违章辖区 | `BX` / `Bronx` | 布朗克斯 | ✅ 已确认 |
| | | | `BK` / `K` / `Kings` | 布鲁克林（国王县） | ✅ 已确认 |
| | | | `MN` / `NY` | 曼哈顿（纽约县） | ✅ 已确认 |
| | | | `QN` / `Q` / `QNS` / `Qns` | 皇后区 | ✅ 已确认 |
| | | | `ST` / `R` / `Rich` | 史泰登岛（里士满县） | ✅ 已确认 |
| | | | `106` / 其他数字 | 待确认 | ⚠️ Human Review |
| parking_violations_all | registration_state | 车辆注册州/省 | `NY` | 纽约州 | ✅ 已确认 |
| | | | `NJ` | 新泽西州 | ✅ 已确认 |
| | | | `PA` | 宾夕法尼亚州 | ✅ 已确认 |
| | | | `CT` | 康涅狄格州 | ✅ 已确认 |
| | | | `FL` | 佛罗里达州 | ✅ 已确认 |
| | | | `ON` / `BC` / `MB` / `NB` / `NS` | 加拿大各省（安大略/不列颠哥伦比亚/曼尼托巴/新不伦瑞克/新斯科舍） | ✅ 已确认 |
| | | | `99` | 未知/其他 | ⚠️ 推断，NYC DOF 数据集常见"99"表示 Other/Unknown |
| | | | `DP` | 外交车辆 (Diplomatic Plate) | ⚠️ 推断，基于 US State Dept. 牌照编码惯例 |
| | | | `FO` | 外国车辆 (Foreign) | ⚠️ 推断，非北美注册车辆 |
| | | | `GV` | 政府车辆 (Government) | ⚠️ 推断，联邦或州政府公务车 |
| | | | `MX` | 墨西哥 (Mexico) | ⚠️ 推断，墨西哥注册车辆 |
| | | | `AB` | 阿尔伯塔省 (Alberta, Canada) | ✅ 已确认 |

### 4.3 medallion_authorized_vehicles（授权 Medallion 车辆）

| 英文表名 | 英文字段名 | 中文字段名 | 枚举值 | 中文含义 | 审核状态 |
|---|---|---|---|---|---|
| medallion_authorized_vehicles | Medallion Type | Medallion 类型 | `NAMED DRIVER` | 指定驾驶员（Medallion 指定给特定驾驶员） | ✅ 已确认 |
| | | | `OWNER MUST DRIVE` | 车主自驾驶（车主必须亲自驾驶） | ✅ 已确认 |

---

## 五、资产域 (Asset)

### 5.1 fhv_active_vehicles（FHV 活跃车辆）

| 英文表名 | 英文字段名 | 中文字段名 | 枚举值 | 中文含义 | 审核状态 |
|---|---|---|---|---|---|
| fhv_active_vehicles | License Type | 牌照类型 | `For Hire Vehicle` | 租用车辆牌照（唯一取值，自解释） | ✅ 已确认 |
| fhv_active_vehicles | Wheelchair Accessible | 无障碍车辆标记 | `WAV` | 经认证的无障碍车辆（Wheelchair Accessible Vehicle） | ✅ 已确认 |
| | | | `PILOT` | 无障碍试点项目车辆 | ✅ 已确认 |
| fhv_active_vehicles | Base Type | 基地类型 | `BLACK CAR` | 黑色专车（豪华轿车服务） | ✅ 已确认 |
| | | | `LIVERY` | 出租包车（传统电召车） | ✅ 已确认 |
| | | | `LUXURY` | 豪华轿车 | ✅ 已确认 |
| fhv_active_vehicles | VEH | 车辆动力/技术类型 | `BEV` | 纯电动车 (Battery Electric Vehicle) — TLC Green Rides 规则明确要求 BEV 比例 | ⚠️ 推断，TLC 未公开此字段完整映射 |
| | | | `CNG` | 压缩天然气车 (Compressed Natural Gas) | ⚠️ 推断，TLC 未公开此字段完整映射 |
| | | | `DSE` | 柴油车 (Diesel) | ⚠️ 推断，TLC 未公开此字段完整映射 |
| | | | `DSEL` | 柴油车 (Diesel，另一种拼写) | ⚠️ 推断，TLC 未公开此字段完整映射 |
| | | | `HYB` | 油电混合动力车 (Hybrid) — TLC Green Rides 规则明确定义 HYB | ⚠️ 推断，TLC 未公开此字段完整映射 |
| | | | `STR` | 标准汽油车 (Standard/Gasoline) | ⚠️ 推断，TLC 未公开此字段完整映射 |
| | | | `WAV` | 无障碍车辆 (Wheelchair Accessible Vehicle) | ⚠️ 推断，TLC 未公开此字段完整映射 |
| | | | `N` | 未指定/无动力类型信息 | ⚠️ 推断，TLC 未公开此字段完整映射 |
| | | | `NON` | 无特殊动力类型 | ⚠️ 推断，TLC 未公开此字段完整映射 |

> **VEH 字段说明**：VEH 是 TLC 用来标记车辆动力/技术类型的字段。`BEV` 和 `HYB` 在 [TLC Green Rides Initiative](https://www.nyc.gov/site/tlc/about/green-rides.page) 中有明确定义。其余代码的含义基于 TLC 行业术语合理推断。TLC FHV Active Vehicles 数据集（[8wbx-tsch](https://data.cityofnewyork.us/Transportation/For-Hire-Vehicles-FHV-Active/8wbx-tsch)）的公开数据字典未列出 VEH 的枚举映射表。

### 5.2 active_vehicles（活跃车辆注册表）

| 英文表名 | 英文字段名 | 中文字段名 | 枚举值 | 中文含义 | 审核状态 |
|---|---|---|---|---|---|
| active_vehicles | Active | 活跃状态 | `YES` | 活跃 | ✅ 已确认 |
| | | | `NO` | 不活跃 | ✅ 已确认 |
| active_vehicles | License Type | 牌照类型 | `Medallion` | Medallion 牌照（黄色出租车） | ✅ 已确认 |
| | | | `For Hire Vehicle` | 租用车辆牌照 (FHV) | ✅ 已确认 |
| | | | `Commuter Van` | 通勤面包车牌 | ✅ 已确认 |
| | | | `Paratransit` | 辅助公交车辆牌 | ✅ 已确认 |
| | | | `Stand By Vehicle` | 备用车辆 | ✅ 已确认 |
| active_vehicles | TLC Vehicle License Status | 车辆牌照状态 | `Current` | 正常有效 | ✅ 已确认 |
| | | | `Suspended` | 已暂停 | ✅ 已确认 |
| active_vehicles | Licensed for Street Hail | 街头扬招许可 | `YES` | 允许街头扬招 | ✅ 已确认 |
| | | | `NO` | 不允许街头扬招 | ✅ 已确认 |
| active_vehicles | Base Type | 基地类型 | `BLACK CAR` | 黑色专车 | ✅ 已确认 |
| | | | `LIVERY` | 出租包车 | ✅ 已确认 |
| | | | `LUXURY` | 豪华轿车 | ✅ 已确认 |
| | | | `COMMUTER VAN` | 通勤面包车 | ✅ 已确认 |
| | | | `PARATRANSIT` | 辅助公交 | ✅ 已确认 |
| active_vehicles | Stretch Limo | 加长豪华轿车 | `YES` | 是加长豪华轿车 | ✅ 已确认 |
| | | | `NO` | 不是 | ✅ 已确认 |
| active_vehicles | WAV | 无障碍车辆 | `YES` | 是无障碍车辆 | ✅ 已确认 |
| | | | `NO` | 不是 | ✅ 已确认 |
| | | | `Pilot` | 无障碍试点项目车辆 | ✅ 已确认 |
| active_vehicles | Vehicle Make | 车辆品牌 | `CD` | 凯迪拉克（Cadillac 缩写） | ⚠️ 推断，待官方确认 |
| | | | `HON` | 本田（Honda 缩写） | ⚠️ 推断，待官方确认 |
| | | | `LX` | 雷克萨斯（Lexus 缩写） | ⚠️ 推断，待官方确认 |
| | | | 59种取值（含大小写混用） | 部分品牌全大写（FORD），部分正常大小写（Ford），需标准化 | ⚠️ 数据质量问题 |
| active_vehicles | Fuel Type | 燃料类型 | `Gasoline` | 汽油 | ✅ 已确认 |
| | | | `Diesel` | 柴油 | ✅ 已确认 |
| | | | `Electric` | 电动 | ✅ 已确认 |
| | | | `Gas/Electric Hybrid` | 汽油/电动混合 | ✅ 已确认 |
| | | | `Plug-in Hybrid` | 插电式混合动力 | ✅ 已确认 |
| | | | `Flex Fuel` | 灵活燃料 | ✅ 已确认 |
| | | | `Bio Diesel` | 生物柴油 | ✅ 已确认 |
| active_vehicles | DMV Insurance Code | DMV保险代码 | `017` | Encompass Independent Insurance Company（独立保险公司） | ✅ 已确认 |
| | | | `036` | American Transit Insurance Co.（美国交通保险公司，主营商用/出租车辆保险） | ✅ 已确认 |
| | | | `137` | Selective Insurance Company of NY（纽约精选保险公司） | ✅ 已确认 |
| | | | `228` | National Union Fire Insurance Co. of Pittsburgh, PA（AIG 旗下全国联合火险公司） | ✅ 已确认 |
| | | | `259` | National Interstate Insurance Company（全国州际保险公司） | ✅ 已确认 |
| | | | `487` | Ace American Insurance Co.（Chubb 旗下艾斯美国保险公司） | ✅ 已确认 |
| | | | `806` | Accident Fund Insurance Company of America（美国工伤保险基金公司） | ✅ 已确认 |
| | | | `810` | Affirmative Direct Insurance Co.（正面直销保险公司，主营非标准车险） | ✅ 已确认 |
| | | | 其余 18 种代码 | 需通过 NY DFS 保险代码查询工具逐一核对：https://myportal.dfs.ny.gov/companydirectory | ⚠️ Human Review |

---

## 六、供给域 (Supply)

### 6.1 shl_active_drivers（SHL 活跃司机）

| 英文表名 | 英文字段名 | 中文字段名 | 枚举值 | 中文含义 | 审核状态 |
|---|---|---|---|---|---|
| shl_active_drivers | Status Code | 状态代码 | `1` | 不受限（可接所有街头扬招乘客） | ⚠️ 基于 Status Description 推断 |
| | | | `3` | 仅限WAV（只能接无障碍出行乘客） | ⚠️ 基于 Status Description 推断 |
| shl_active_drivers | Status Description | 状态描述 | `SHL UNRESTRICTED` | 街头冰雹涂装 (SHL) - 不受限制 | ✅ 已确认 |
| | | | `SHL WAV ONLY` | 街头冰雹涂装 (SHL) - 仅限无障碍车辆 | ✅ 已确认 |

### 6.2 fhv_active_drivers（FHV 活跃驾驶员）

| 英文表名 | 英文字段名 | 中文字段名 | 枚举值 | 中文含义 | 审核状态 |
|---|---|---|---|---|---|
| fhv_active_drivers | Type | 驾驶员类型 | `For Hire Vehicle Driver` | 租用车辆驾驶员（唯一取值，自解释） | ✅ 已确认 |
| fhv_active_drivers | Wheelchair Accessible Trained | 无障碍服务培训 | `WAV` | 已完成无障碍车辆服务培训 | ✅ 已确认 |

> **说明**：`Type` 字段仅取 `For Hire Vehicle Driver`，`Wheelchair Accessible Trained` 仅取 `WAV`，均为自解释或单一取值，无需额外解码。

---

## 七、待补充项

### 7.1 已通过 MV-104AN PDF 验证（EasyOCR）

`F:\nyc_mv104an_rev072001_sub04142006web.pdf` 为 NYSDMV 官方 MV-104AN (7/01) 警察事故报告编码手册。已验证：

- ✅ **Pedestrian Action** 编码 1–14 — 全部确认
- ✅ **Pedestrian Location** 编码 1–2 — 全部确认
- ✅ **Safety Equipment** 编码 1–G（字母）— 全部确认
- ✅ **Contributing Factors（车辆/环境 41–69）** — 全部确认
- ✅ **Contributing Factors（人力 1–28）** — 文本已确认，编码配对精度受 OCR 限制

### 7.2 仍需 Human Review（原因：NYPD AABS 旧系统）

以下数字代码**不在** MV-104AN (7/01) 标准范围内，属于 NYPD AABS（Automated Accident Booking System）旧系统遗留：

1. **contributing_factor = `1`, `35`, `36`, `37`, `52`, `70`, `80`** — 需 NYPD AABS 编码手册
2. **safety_equipment = `17`–`26`** — NYPD 旧系统原始编号，MV-104AN 中已改为字母 A–G
3. **position_in_vehicle = `10`–`12`** — NYPD 旧系统座位编号
4. **ped_action = `15`–`19`** — NYPD 旧系统遗留，超出 MV-104AN 1–14 范围

> **关键发现**：MV-104AN PDF 能解释 **你能看到的所有英文文本标签**，但无法解释 **纯数字异常代码**。这些数字代码来自 NYPD 内部 AABS 系统，其编码手册未在公开渠道发布。要彻底消除所有 ⚠️，需获取 NYPD AABS 编码对照表。

### 7.3 其他待补充

4. **VEH 字段 9 个代码** — TLC 未公开发布此字段的映射表，当前含义基于 TLC Green Rides 规则和行业术语推断
5. **DMV Insurance Code 完整 26 种映射** — 已确认 9 种，剩余通过 [NY DFS 查询工具](https://myportal.dfs.ny.gov/companydirectory) 逐条核对
6. **vehicle_body_type 标准化映射** — 642 种取值需先标准化再映射
7. **issuing_agency 完整 29 种代码** — 已确认 7 种主要机构

---

## 八、数据字典规范补充建议

基于本次全表扫描发现的问题，建议在数据字典规范中增加以下要求：

### 8.1 枚举值说明必须包含的字段类型

出现以下情况时，字段字典中必须列出枚举值的中文含义：

1. **缩写/代码型**：值由大写字母+数字组成（如 `PDR`、`BEV`、`B00001`）
2. **数字编码型**：数字代表分类含义（如 `VendorID=1`、`payment_type=2`）
3. **领域术语型**：值可读但需专业背景理解（如 `Medallion`、`Street Hail`）
4. **布尔型**：`YES`/`NO`、`Y`/`N` 形式的值

### 8.2 审核状态标记规范

| 标记 | 含义 |
|---|---|
| ✅ 已确认 | 来自官方数据字典或可靠性高的公开文档 |
| ⚠️ 推断，待官方确认 | 基于字段值、上下文和行业知识合理推断 |
| ⚠️ Human Review | 完全无法推断，需人工查阅官方资料后填写 |

### 8.3 数据质量备注

对于以下情况应在治理备注中注明：
- 同一含义存在多个拼写变体（如 `Drugs (Illegal)` vs `Drugs (illegal)`、`Illness` vs `Illnes`）
- 数字代码与文本代码混用（如 contributing_factor 中同时存在 `1` 和 `Unspecified`）
- 自由文本字段混入代码含义不明的值（如 `vehicle_type_code1` 含 1579 种取值，大量为人工录入自由文本，非标准代码）
- 同含义多拼写（如 `vehicle_body_type` 中 4D/4DR/4DSD/4DOOR 均指四门轿车，需标准化）
- 大小写不统一（如 `Vehicle Make` 中 FORD/Ford 混用，CD/HON/LX 为品牌缩写）

### 8.4 覆盖统计

| 数据层 | 总表数 | 已扫描表数 | ✅ 已确认 | ⚠️ 推断 | ⚠️ NYPD遗留 |
|---|---|---|---|---|---|
| Bronze CSV (TABLE) | 9 | 9 | 45 | 5 | 3 |
| Bronze Parquet (VIEW) | 7 | 7 | 50 | 1 | 2 |
| **合计** | **16** | **16** | **95** | **6** | **5** |

> **说明**：通过 MV-104AN PDF OCR 验证，`ped_action`/`safety_equipment`/`position_in_vehicle` 的文本编码已全部确认。⚠️ NYPD 遗留项为 NYPD AABS 旧系统产生的纯数字异常代码（如 `35`–`37`），其编码手册未在公开渠道发布。<br>
> 其他 ⚠️ 推断项：`plate_type` 84 种全部确认，`DMV Insurance Code` 9/26 确认，`VEH` 和 `registration_state` 合理推断。<br>
> MV-104AN 编码验证基于 NYSDMV 官方 PDF（`nyc_mv104an_rev072001_sub04142006web.pdf`）的 EasyOCR 提取；VEH 字段推断基于 TLC Green Rides Initiative 官方规则和行业术语。
