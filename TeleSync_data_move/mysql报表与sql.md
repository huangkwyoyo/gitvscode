### 10组电信数据迁移测试材料

#### 1. 用户基础信息 (User Info)

- 源表 (MySQL):

  sql

  

  ```sql
  1CREATE TABLE `ods_user_info` (
  2  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  3  `user_id` VARCHAR(20) NOT NULL COMMENT '用户唯一标识',
  4  `phone_number` VARCHAR(20) NOT NULL COMMENT '手机号码',
  5  `user_name` VARCHAR(64) COMMENT '客户姓名',
  6  `id_card` VARCHAR(18) COMMENT '身份证号',
  7  `register_time` DATETIME COMMENT '入网时间',
  8  `package_type` VARCHAR(50) COMMENT '当前套餐',
  9  `status` TINYINT COMMENT '0:停机, 1:正常, 2:销户',
  10  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  11  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  12) COMMENT='电信用户基础信息表';
  ```

- 结果表 (Doris):

  sql

  

  ```sql
  1CREATE TABLE `dwd_user_info` (
  2  `id` BIGINT,
  3  `user_id` VARCHAR(20),
  4  `phone_number` VARCHAR(20),
  5  `user_name` VARCHAR(64),
  6  `id_card` VARCHAR(18),
  7  `register_time` DATETIME,
  8  `package_type` VARCHAR(50),
  9  `status` TINYINT,
  10  `create_time` DATETIME,
  11  `update_time` DATETIME
  12) UNIQUE KEY(`id`)
  13DISTRIBUTED BY HASH(`user_id`) BUCKETS 10
  14PROPERTIES ("replication_num" = "1");
  ```

- 业务过程代码 (SQL - 用户画像清洗与脱敏):

  sql

  

  ```sql
  1-- 需求：每日定时抽取活跃用户，对身份证进行脱敏，并计算在网时长
  2INSERT INTO dwd_user_info (id, user_id, phone_number, user_name, id_card, register_time, package_type, status, create_time, update_time)
  3SELECT 
  4    id,
  5    user_id,
  6    phone_number,
  7    user_name,
  8    CONCAT(SUBSTRING(id_card, 1, 6), '********', SUBSTRING(id_card, 15)) AS masked_id_card, -- 身份证脱敏
  9    register_time,
  10    CASE 
  11        WHEN package_type LIKE '%5G%' THEN '5G专属套餐'
  12        ELSE '普通套餐'
  13    END AS package_category,
  14    status,
  15    create_time,
  16    NOW() AS etl_time
  17FROM ods_user_info
  18WHERE status = 1 -- 仅抽取正常在网用户
  19  AND DATEDIFF(NOW(), register_time) > 30; -- 排除刚入网不足30天的测试用户
  ```

#### 2. 语音通话详单 (Voice CDR)

- 源表 (MySQL):

  sql

  

  ```
  1CREATE TABLE `ods_voice_cdr` (
  2  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  3  `call_id` VARCHAR(64) NOT NULL COMMENT '通话流水号',
  4  `caller` VARCHAR(20) COMMENT '主叫号码',
  5  `callee` VARCHAR(20) COMMENT '被叫号码',
  6  `start_time` DATETIME COMMENT '通话开始时间',
  7  `duration` INT COMMENT '通话时长(秒)',
  8  `call_type` TINYINT COMMENT '1:本地, 2:长途, 3:漫游',
  9  `area_code` VARCHAR(10) COMMENT '归属地编码',
  10  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  11  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  12) COMMENT='语音通话详单表';
  ```

- 结果表 (Doris):

  sql

  

  ```sql
  1CREATE TABLE `dwd_voice_cdr` (
  2  `id` BIGINT,
  3  `call_id` VARCHAR(64),
  4  `caller` VARCHAR(20),
  5  `callee` VARCHAR(20),
  6  `start_time` DATETIME,
  7  `duration` INT,
  8  `call_type` TINYINT,
  9  `area_code` VARCHAR(10),
  10  `create_time` DATETIME,
  11  `update_time` DATETIME
  12) UNIQUE KEY(`id`)
  13DISTRIBUTED BY HASH(`caller`) BUCKETS 10
  14PROPERTIES ("replication_num" = "1");
  ```

- 业务过程代码 (SQL - 话单费用预估与异常过滤):

  sql

  

  ```sql
  1-- 需求：清洗无效话单（时长为0），并根据通话类型计算预估费用
  2INSERT INTO dwd_voice_cdr (id, call_id, caller, callee, start_time, duration, call_type, area_code, create_time, update_time)
  3SELECT 
  4    id,
  5    call_id,
  6    caller,
  7    callee,
  8    start_time,
  9    duration,
  10    call_type,
  11    area_code,
  12    create_time,
  13    update_time
  14FROM (
  15    SELECT *,
  16           ROW_NUMBER() OVER(PARTITION BY call_id ORDER BY update_time DESC) as rn -- 防止重复话单
  17    FROM ods_voice_cdr
  18    WHERE duration > 0 -- 过滤掉未接通的无效记录
  19      AND start_time >= DATE_SUB(NOW(), INTERVAL 1 DAY) -- 仅处理昨日至今的话单
  20) t
  21WHERE t.rn = 1;
  ```

#### 3. 手机上网流量日志 (Data Usage)

- 源表 (MySQL):

  sql

  

  ```sql
  1CREATE TABLE `ods_data_usage` (
  2  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  3  `user_id` VARCHAR(20) COMMENT '用户标识',
  4  `base_station_id` VARCHAR(32) COMMENT '基站编号',
  5  `upload_bytes` BIGINT COMMENT '上行流量(字节)',
  6  `download_bytes` BIGINT COMMENT '下行流量(字节)',
  7  `access_time` DATETIME COMMENT '访问时间',
  8  `app_type` VARCHAR(50) COMMENT '应用类型(video/social/web)',
  9  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  10  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  11) COMMENT='手机上网流量日志表';
  ```

- 结果表 (Doris):

  sql

  

  ```sql
  1CREATE TABLE `dwd_data_usage` (
  2  `id` BIGINT,
  3  `user_id` VARCHAR(20),
  4  `base_station_id` VARCHAR(32),
  5  `upload_bytes` BIGINT,
  6  `download_bytes` BIGINT,
  7  `access_time` DATETIME,
  8  `app_type` VARCHAR(50),
  9  `create_time` DATETIME,
  10  `update_time` DATETIME
  11) UNIQUE KEY(`id`)
  12DISTRIBUTED BY HASH(`user_id`) BUCKETS 10
  13PROPERTIES ("replication_num" = "1");
  ```

- 业务过程代码 (SQL - 流量单位换算与应用归类):

  sql

  

  ```sql
  1-- 需求：将字节转换为MB，并将细粒度APP归类为大类，过滤异常极值流量
  2INSERT INTO dwd_data_usage (id, user_id, base_station_id, upload_bytes, download_bytes, access_time, app_type, create_time, update_time)
  3SELECT 
  4    id,
  5    user_id,
  6    base_station_id,
  7    ROUND(upload_bytes / 1024.0 / 1024.0, 2) AS up_mb,
  8    ROUND(download_bytes / 1024.0 / 1024.0, 2) AS down_mb,
  9    access_time,
  10    CASE 
  11        WHEN app_type IN ('douyin', 'kuaishou', 'bilibili') THEN 'video_streaming'
  12        WHEN app_type IN ('wechat', 'qq', 'weibo') THEN 'social_media'
  13        ELSE 'other_traffic'
  14    END AS final_app_type,
  15    create_time,
  16    update_time
  17FROM ods_data_usage
  18WHERE (upload_bytes + download_bytes) < 10737418240; -- 过滤单次超过10GB的异常日志
  ```

#### 4. 短信收发记录 (SMS Record)

- 源表 (MySQL):

  sql

  

  ```sql
  1CREATE TABLE `ods_sms_record` (
  2  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  3  `sender` VARCHAR(20) COMMENT '发送方',
  4  `receiver` VARCHAR(20) COMMENT '接收方',
  5  `send_time` DATETIME COMMENT '发送时间',
  6  `sms_type` TINYINT COMMENT '1:普通, 2:验证码, 3:营销',
  7  `length` INT COMMENT '短信字数',
  8  `status` TINYINT COMMENT '0:失败, 1:成功',
  9  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  10  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  11) COMMENT='短信收发记录表';
  ```

- 结果表 (Doris):

  sql

  

  ```sql
  1CREATE TABLE `dwd_sms_record` (
  2  `id` BIGINT,
  3  `sender` VARCHAR(20),
  4  `receiver` VARCHAR(20),
  5  `send_time` DATETIME,
  6  `sms_type` TINYINT,
  7  `length` INT,
  8  `status` TINYINT,
  9  `create_time` DATETIME,
  10  `update_time` DATETIME
  11) UNIQUE KEY(`id`)
  12DISTRIBUTED BY HASH(`receiver`) BUCKETS 10
  13PROPERTIES ("replication_num" = "1");
  ```

- 业务过程代码 (SQL - 营销短信成功率分析与拦截):

  sql

  

  ```sql
  1-- 需求：提取营销短信发送情况，标记高频发送（疑似骚扰）的记录
  2INSERT INTO dwd_sms_record (id, sender, receiver, send_time, sms_type, length, status, create_time, update_time)
  3SELECT 
  4    s.id, s.sender, s.receiver, s.send_time, s.sms_type, s.length, s.status, s.create_time, s.update_time
  5FROM ods_sms_record s
  6JOIN (
  7    -- 找出单日发送超过100条的发信人（黑名单逻辑）
  8    SELECT sender
  9    FROM ods_sms_record
  10    WHERE sms_type = 3 AND DATE(send_time) = CURDATE()
  11    GROUP BY sender
  12    HAVING COUNT(*) > 100
  13) spam_filter ON s.sender = spam_filter.sender
  14WHERE s.sms_type = 3 -- 仅处理营销短信
  15  AND s.status = 1;  -- 仅统计发送成功的
  ```

#### 5. 话费充值订单 (Recharge Order)

- 源表 (MySQL):

  sql

  

  ```sql
  1CREATE TABLE `ods_recharge_order` (
  2  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  3  `order_no` VARCHAR(64) NOT NULL COMMENT '订单号',
  4  `user_id` VARCHAR(20) COMMENT '充值用户',
  5  `amount` DECIMAL(10,2) COMMENT '充值金额',
  6  `pay_channel` VARCHAR(30) COMMENT '支付渠道(wechat/alipay)',
  7  `order_status` TINYINT COMMENT '0:失败, 1:成功, 2:处理中',
  8  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  9  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  10) COMMENT='话费充值订单表';
  ```

- 结果表 (Doris):

  sql

  

  ```sql
  1CREATE TABLE `dwd_recharge_order` (
  2  `id` BIGINT,
  3  `order_no` VARCHAR(64),
  4  `user_id` VARCHAR(20),
  5  `amount` DECIMAL(10,2),
  6  `pay_channel` VARCHAR(30),
  7  `order_status` TINYINT,
  8  `create_time` DATETIME,
  9  `update_time` DATETIME
  10) UNIQUE KEY(`id`)
  11DISTRIBUTED BY HASH(`order_no`) BUCKETS 10
  12PROPERTIES ("replication_num" = "1");
  ```

- 业务过程代码 (SQL - 营收对账与渠道汇总):

  sql

  

  ```sql
  1-- 需求：只同步已完成的充值订单，并增加渠道中文名称映射
  2INSERT INTO dwd_recharge_order (id, order_no, user_id, amount, pay_channel, order_status, create_time, update_time)
  3SELECT 
  4    id,
  5    order_no,
  6    user_id,
  7    amount,
  8    CASE pay_channel
  9        WHEN 'wx_pay' THEN 'WeChat Pay'
  10        WHEN 'ali_pay' THEN 'Alipay'
  11        WHEN 'apple_pay' THEN 'Apple Pay'
  12        ELSE 'Unknown'
  13    END AS channel_name,
  14    order_status,
  15    create_time,
  16    update_time
  17FROM ods_recharge_order
  18WHERE order_status = 1 -- 只要成功的订单
  19  AND amount > 0       -- 排除金额为0的测试单
  20  AND create_time >= DATE_SUB(NOW(), INTERVAL 7 DAY); -- 近一周的数据做T+1对账
  ```

#### 6. 套餐订购与变更 (Package Subscription)

- 源表 (MySQL):

  sql

  

  ```sql
  1CREATE TABLE `ods_package_sub` (
  2  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  3  `sub_id` VARCHAR(64) NOT NULL COMMENT '订购实例ID',
  4  `user_id` VARCHAR(20) COMMENT '用户标识',
  5  `package_id` VARCHAR(32) COMMENT '套餐ID',
  6  `package_name` VARCHAR(100) COMMENT '套餐名称',
  7  `monthly_fee` DECIMAL(8,2) COMMENT '月费',
  8  `effective_date` DATE COMMENT '生效日期',
  9  `expire_date` DATE COMMENT '失效日期',
  10  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  11  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  12) COMMENT='套餐订购与变更表';
  ```

- 结果表 (Doris):

  sql

  

  ```sql
  1CREATE TABLE `dwd_package_sub` (
  2  `id` BIGINT,
  3  `sub_id` VARCHAR(64),
  4  `user_id` VARCHAR(20),
  5  `package_id` VARCHAR(32),
  6  `package_name` VARCHAR(100),
  7  `monthly_fee` DECIMAL(8,2),
  8  `effective_date` DATE,
  9  `expire_date` DATE,
  10  `create_time` DATETIME,
  11  `update_time` DATETIME
  12) UNIQUE KEY(`id`)
  13DISTRIBUTED BY HASH(`user_id`) BUCKETS 10
  14PROPERTIES ("replication_num" = "1");
  ```

- 业务过程代码 (SQL - 有效套餐快照提取):

  sql

  

  ```sql
  1-- 需求：提取当前仍在有效期内的所有用户套餐，计算剩余天数
  2INSERT INTO dwd_package_sub (id, sub_id, user_id, package_id, package_name, monthly_fee, effective_date, expire_date, create_time, update_time)
  3SELECT 
  4    id,
  5    sub_id,
  6    user_id,
  7    package_id,
  8    TRIM(package_name) AS clean_name, -- 去除名称前后空格
  9    monthly_fee,
  10    effective_date,
  11    expire_date,
  12    create_time,
  13    update_time
  14FROM ods_package_sub
  15WHERE effective_date <= CURDATE() 
  16  AND expire_date >= CURDATE() -- 筛选出今天依然有效的合约
  17  AND monthly_fee >= 19.00;    -- 只分析19元以上的主流套餐
  ```

#### 7. 基站设备状态 (Base Station)

- 源表 (MySQL):

  sql

  

  ```sql
  1CREATE TABLE `ods_base_station` (
  2  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  3  `station_id` VARCHAR(32) NOT NULL COMMENT '基站编号',
  4  `station_name` VARCHAR(100) COMMENT '基站名称',
  5  `longitude` DECIMAL(10,6) COMMENT '经度',
  6  `latitude` DECIMAL(10,6) COMMENT '纬度',
  7  `coverage_area` VARCHAR(100) COMMENT '覆盖区域',
  8  `status` TINYINT COMMENT '0:故障, 1:正常运行',
  9  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  10  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  11) COMMENT='基站设备状态表';
  ```

- 结果表 (Doris):

  sql

  

  ```sql
  1CREATE TABLE `dwd_base_station` (
  2  `id` BIGINT,
  3  `station_id` VARCHAR(32),
  4  `station_name` VARCHAR(100),
  5  `longitude` DECIMAL(10,6),
  6  `latitude` DECIMAL(10,6),
  7  `coverage_area` VARCHAR(100),
  8  `status` TINYINT,
  9  `create_time` DATETIME,
  10  `update_time` DATETIME
  11) UNIQUE KEY(`id`)
  12DISTRIBUTED BY HASH(`station_id`) BUCKETS 10
  13PROPERTIES ("replication_num" = "1");
  ```

- 业务过程代码 (SQL - 故障基站告警提取):

  sql

  

  ```sql
  1-- 需求：实时提取状态变更为“故障”的基站，并拼接经纬度坐标用于地图打点
  2INSERT INTO dwd_base_station (id, station_id, station_name, longitude, latitude, coverage_area, status, create_time, update_time)
  3SELECT 
  4    id,
  5    station_id,
  6    station_name,
  7    longitude,
  8    latitude,
  9    CONCAT(longitude, ',', latitude) AS geo_point, -- 生成地理坐标字符串
  10    coverage_area,
  11    status,
  12    create_time,
  13    update_time
  14FROM ods_base_station
  15WHERE status = 0 -- 0代表故障
  16  AND update_time >= DATE_SUB(NOW(), INTERVAL 1 HOUR); -- 最近一小时内发生状态变更的
  ```

#### 8. 客服投诉工单 (Complaint Ticket)

- 源表 (MySQL):

  sql

  

  ```sql
  1CREATE TABLE `ods_complaint` (
  2  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  3  `ticket_no` VARCHAR(64) NOT NULL COMMENT '工单编号',
  4  `user_id` VARCHAR(20) COMMENT '投诉用户',
  5  `complaint_type` VARCHAR(50) COMMENT '投诉类型(信号差/乱扣费)',
  6  `description` TEXT COMMENT '问题描述',
  7  `handle_status` TINYINT COMMENT '0:待处理, 1:处理中, 2:已结单',
  8  `satisfaction_score` TINYINT COMMENT '满意度评分',
  9  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  10  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  11) COMMENT='客服投诉工单表';
  ```

- sql结果表 (Doris):

  sql

  

  ```sql
  1CREATE TABLE `dwd_complaint` (
  2  `id` BIGINT,
  3  `ticket_no` VARCHAR(64),
  4  `user_id` VARCHAR(20),
  5  `complaint_type` VARCHAR(50),
  6  `description` STRING,
  7  `handle_status` TINYINT,
  8  `satisfaction_score` TINYINT,
  9  `create_time` DATETIME,
  10  `update_time` DATETIME
  11) UNIQUE KEY(`id`)
  12DISTRIBUTED BY HASH(`ticket_no`) BUCKETS 10
  13PROPERTIES ("replication_num" = "1");
  ```

- 业务过程代码 (SQL - 重点投诉工单分级):

  sql

  

  ```sql
  1-- 需求：提取未结单的投诉，并根据关键词标记紧急程度
  2INSERT INTO dwd_complaint (id, ticket_no, user_id, complaint_type, description, handle_status, satisfaction_score, create_time, update_time)
  3SELECT 
  4    id,
  5    ticket_no,
  6    user_id,
  7    complaint_type,
  8    description,
  9    handle_status,
  10    satisfaction_score,
  11    create_time,
  12    update_time
  13FROM ods_complaint
  14WHERE handle_status IN (0, 1) -- 待处理或处理中
  15  AND (
  16      description LIKE '%工信部%' OR 
  17      description LIKE '%起诉%' OR 
  18      complaint_type = '乱扣费'
  19  ); -- 筛选包含敏感词或敏感类型的升级投诉
  ```



#### 9. 宽带业务安装 (Broadband)

- 源表 (MySQL):

  sql

  

  ```sql
  1CREATE TABLE `ods_broadband` (
  2  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  3  `broadband_no` VARCHAR(64) NOT NULL COMMENT '宽带账号',
  4  `user_id` VARCHAR(20) COMMENT '关联用户',
  5  `install_address` VARCHAR(255) COMMENT '安装地址',
  6  `bandwidth` INT COMMENT '签约带宽(M)',
  7  `install_date` DATE COMMENT '安装日期',
  8  `device_sn` VARCHAR(64) COMMENT '光猫设备序列号',
  9  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  10  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  11) COMMENT='宽带业务安装表';
  ```

- 结果表 (Doris):

  sql

  

  ```sql
  1CREATE TABLE `dwd_broadband` (
  2  `id` BIGINT,
  3  `broadband_no` VARCHAR(64),
  4  `user_id` VARCHAR(20),
  5  `install_address` VARCHAR(255),
  6  `bandwidth` INT,
  7  `install_date` DATE,
  8  `device_sn` VARCHAR(64),
  9  `create_time` DATETIME,
  10  `update_time` DATETIME
  11) UNIQUE KEY(`id`)
  12DISTRIBUTED BY HASH(`broadband_no`) BUCKETS 10
  13PROPERTIES ("replication_num" = "1");
  ```

- 业务过程代码 (SQL - 高价值千兆宽带提取与地址标准化):

  sql

  

  ```sql
  1-- 需求：筛选出本月新装的千兆/五百兆高端宽带用户，并对地址中的特殊符号进行清洗
  2INSERT INTO dwd_broadband (id, broadband_no, user_id, install_address, bandwidth, install_date, device_sn, create_time, update_time)
  3SELECT 
  4    id,
  5    broadband_no,
  6    user_id,
  7    REPLACE(REPLACE(install_address, '#', '-'), '栋', '幢') AS clean_address, -- 统一地址格式
  8    bandwidth,
  9    install_date,
  10    UPPER(device_sn) AS sn_upper, -- 设备序列号转大写
  11    create_time,
  12    update_time
  13FROM ods_broadband
  14WHERE bandwidth >= 500 -- 仅提取500M及以上的高端宽带
  15  AND install_date >= DATE_FORMAT(NOW(), '%Y-%m-01') -- 仅限本月新装数据
  16  AND device_sn IS NOT NULL; -- 确保光猫设备已录入
  ```

#### 10. 国际漫游服务 (Roaming Service)

- 源表 (MySQL):

  sql

  

  ```sql
  1CREATE TABLE `ods_roaming` (
  2  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  3  `roaming_no` VARCHAR(64) NOT NULL COMMENT '漫游流水号',
  4  `user_id` VARCHAR(20) COMMENT '用户标识',
  5  `country_code` VARCHAR(10) COMMENT '国家代码',
  6  `operator_name` VARCHAR(100) COMMENT '当地运营商',
  7  `start_date` DATE COMMENT '开始日期',
  8  `end_date` DATE COMMENT '结束日期',
  9  `data_used_mb` DECIMAL(10,2) COMMENT '使用流量(MB)',
  10  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  11  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  12) COMMENT='国际漫游服务表';
  ```

- 结果表 (Doris):

  sql

  

  ```sql
  1CREATE TABLE `dwd_roaming` (
  2  `id` BIGINT,
  3  `roaming_no` VARCHAR(64),
  4  `user_id` VARCHAR(20),
  5  `country_code` VARCHAR(10),
  6  `operator_name` VARCHAR(100),
  7  `start_date` DATE,
  8  `end_date` DATE,
  9  `data_used_mb` DECIMAL(10,2),
  10  `create_time` DATETIME,
  11  `update_time` DATETIME
  12) UNIQUE KEY(`id`)
  13DISTRIBUTED BY HASH(`user_id`) BUCKETS 10
  14PROPERTIES ("replication_num" = "1");
  ```

- 业务过程代码 (SQL - 跨国结算流量统计与异常高额账单预警):

  sql

  

  ```sql
  1-- 需求：计算单次漫游的总流量费用（假设每MB固定费率），并标记出费用超过500元的高风险记录
  2INSERT INTO dwd_roaming (id, roaming_no, user_id, country_code, operator_name, start_date, end_date, data_used_mb, create_time, update_time)
  3SELECT 
  4    id,
  5    roaming_no,
  6    user_id,
  7    country_code,
  8    operator_name,
  9    start_date,
  10    end_date,
  11    data_used_mb,
  12    create_time,
  13    update_time
  14FROM (
  15    SELECT *,
  16           -- 模拟跨国结算计费逻辑：不同国家费率不同（这里简单用CASE演示）
  17           CASE 
  18               WHEN country_code IN ('US', 'JP', 'KR') THEN data_used_mb * 0.05
  19               WHEN country_code IN ('HK', 'MO', 'TW') THEN data_used_mb * 0.02
  20               ELSE data_used_mb * 0.08
  21           END AS estimated_cost
  22    FROM ods_roaming
  23    WHERE end_date IS NOT NULL -- 漫游行程已结束
  24) t
  25WHERE t.estimated_cost > 100.00; -- 仅同步预估费用大于100元的详单用于财务稽核
  ```