SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DELIMITER $$

DROP PROCEDURE IF EXISTS patch_add_data_time $$
CREATE PROCEDURE patch_add_data_time()
BEGIN
    DECLARE done INT DEFAULT 0;
    DECLARE v_schema VARCHAR(64);
    DECLARE v_table VARCHAR(128);
    DECLARE cur CURSOR FOR
        SELECT t.table_schema, t.table_name
        FROM information_schema.tables t
        LEFT JOIN information_schema.columns c
          ON c.table_schema = t.table_schema
         AND c.table_name = t.table_name
         AND c.column_name = 'data_time'
        WHERE t.table_schema IN ('ods', 'dwd', 'dws', 'ads')
          AND t.table_type = 'BASE TABLE'
          AND c.column_name IS NULL
        ORDER BY t.table_schema, t.table_name;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;

    OPEN cur;
    read_loop: LOOP
        FETCH cur INTO v_schema, v_table;
        IF done = 1 THEN
            LEAVE read_loop;
        END IF;
        SET @sql = CONCAT(
            'ALTER TABLE `', v_schema, '`.`', v_table,
            '` ADD COLUMN `data_time` DATE NOT NULL DEFAULT ''1970-01-01'' COMMENT ''??????'''
        );
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END LOOP;
    CLOSE cur;
END $$

DROP PROCEDURE IF EXISTS patch_add_ods_primary_key $$
CREATE PROCEDURE patch_add_ods_primary_key()
BEGIN
    DECLARE done INT DEFAULT 0;
    DECLARE v_table VARCHAR(128);
    DECLARE cur CURSOR FOR
        SELECT t.table_name
        FROM information_schema.tables t
        LEFT JOIN information_schema.table_constraints tc
          ON tc.table_schema = t.table_schema
         AND tc.table_name = t.table_name
         AND tc.constraint_type = 'PRIMARY KEY'
        WHERE t.table_schema = 'ods'
          AND t.table_type = 'BASE TABLE'
          AND tc.constraint_name IS NULL
        ORDER BY t.table_name;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;

    OPEN cur;
    read_loop: LOOP
        FETCH cur INTO v_table;
        IF done = 1 THEN
            LEAVE read_loop;
        END IF;
        SET @sql = CONCAT(
            'ALTER TABLE `ods`.`', v_table,
            '` ADD COLUMN `synthetic_row_id` BIGINT NOT NULL AUTO_INCREMENT COMMENT ''ODS批次内技术主键'' FIRST, ',
            'ADD PRIMARY KEY (`synthetic_row_id`)'
        );
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END LOOP;
    CLOSE cur;
END $$

DROP PROCEDURE IF EXISTS patch_fix_ods_user_id_type $$
CREATE PROCEDURE patch_fix_ods_user_id_type()
BEGIN
    DECLARE done INT DEFAULT 0;
    DECLARE v_table VARCHAR(128);
    DECLARE cur CURSOR FOR
        SELECT table_name
        FROM information_schema.columns
        WHERE table_schema = 'ods'
          AND column_name = 'user_id'
          AND data_type NOT IN ('varchar', 'text', 'char')
        ORDER BY table_name;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;

    OPEN cur;
    read_loop: LOOP
        FETCH cur INTO v_table;
        IF done = 1 THEN
            LEAVE read_loop;
        END IF;
        SET @sql = CONCAT(
            'ALTER TABLE `ods`.`', v_table,
            '` MODIFY COLUMN `user_id` VARCHAR(32) NULL COMMENT ''用户ID'''
        );
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END LOOP;
    CLOSE cur;
END $$

DELIMITER ;

CALL patch_add_data_time();
CALL patch_fix_ods_user_id_type();
CALL patch_add_ods_primary_key();

DROP PROCEDURE IF EXISTS patch_add_data_time;
DROP PROCEDURE IF EXISTS patch_add_ods_primary_key;
DROP PROCEDURE IF EXISTS patch_fix_ods_user_id_type;

ALTER TABLE dwd.fact_order_daily
    ADD COLUMN business_time DATETIME NULL COMMENT '业务时间' AFTER payment_time;

ALTER TABLE dwd.dim_user
    ADD COLUMN product_id VARCHAR(64) NULL COMMENT '主产品ID' AFTER account_id,
    ADD COLUMN province_name VARCHAR(64) NULL COMMENT '省份名称' AFTER customer_name,
    ADD COLUMN city_name VARCHAR(64) NULL COMMENT '城市名称' AFTER province_name,
    ADD COLUMN district_name VARCHAR(64) NULL COMMENT '区县名称' AFTER city_name,
    ADD COLUMN town_name VARCHAR(128) NULL COMMENT '镇街名称' AFTER district_name,
    ADD COLUMN outlet_name VARCHAR(255) NULL COMMENT '归属网点名称' AFTER town_name,
    ADD COLUMN gender_type VARCHAR(32) NULL COMMENT '性别类型' AFTER outlet_name,
    ADD COLUMN age_count INT NULL COMMENT '年龄' AFTER gender_type;

ALTER TABLE dwd.dim_user DROP PRIMARY KEY, ADD PRIMARY KEY (data_time, user_id);
ALTER TABLE dwd.dim_customer DROP PRIMARY KEY, ADD PRIMARY KEY (data_time, customer_id);
ALTER TABLE dwd.dim_account DROP PRIMARY KEY, ADD PRIMARY KEY (data_time, account_id);
ALTER TABLE dwd.dim_product DROP PRIMARY KEY, ADD PRIMARY KEY (data_time, product_id);
ALTER TABLE dwd.dim_channel DROP PRIMARY KEY, ADD PRIMARY KEY (data_time, channel_id);
ALTER TABLE dwd.dim_org DROP PRIMARY KEY, ADD PRIMARY KEY (data_time, department_id);
ALTER TABLE dwd.dim_staff DROP PRIMARY KEY, ADD PRIMARY KEY (data_time, staff_id);
ALTER TABLE dwd.dim_terminal DROP PRIMARY KEY, ADD PRIMARY KEY (data_time, terminal_id);
ALTER TABLE dwd.dim_date DROP PRIMARY KEY, ADD PRIMARY KEY (data_time, date_id);
ALTER TABLE dwd.dim_application DROP PRIMARY KEY, ADD PRIMARY KEY (data_time, application_id);

ALTER TABLE dwd.fact_billing_monthly ADD COLUMN synthetic_row_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '事实表技术主键' FIRST, ADD PRIMARY KEY (synthetic_row_id);
ALTER TABLE dwd.fact_user_snapshot_daily ADD COLUMN synthetic_row_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '事实表技术主键' FIRST, ADD PRIMARY KEY (synthetic_row_id);
ALTER TABLE dwd.fact_usage_daily ADD COLUMN synthetic_row_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '事实表技术主键' FIRST, ADD PRIMARY KEY (synthetic_row_id);
ALTER TABLE dwd.fact_recharge_daily DROP PRIMARY KEY, ADD PRIMARY KEY (data_time, recharge_event_id);
ALTER TABLE dwd.fact_order_daily DROP PRIMARY KEY, ADD PRIMARY KEY (data_time, order_id);
ALTER TABLE dwd.fact_complaint_daily DROP PRIMARY KEY, ADD PRIMARY KEY (data_time, complaint_event_id);
ALTER TABLE dwd.fact_dpi_usage_daily ADD COLUMN synthetic_row_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '事实表技术主键' FIRST, ADD PRIMARY KEY (synthetic_row_id);

ALTER TABLE dws.dws_user_day_summary ADD PRIMARY KEY (data_time, user_id, data_date);
ALTER TABLE dws.dws_user_month_summary ADD PRIMARY KEY (data_time, user_id, data_month_date);
ALTER TABLE dws.dws_product_month_summary ADD PRIMARY KEY (data_time, product_id, data_month_date);
ALTER TABLE dws.dws_channel_day_summary ADD PRIMARY KEY (data_time, channel_id, data_date);
ALTER TABLE dws.dws_org_month_summary ADD PRIMARY KEY (data_time, department_id, data_month_date);
ALTER TABLE dws.dws_arrears_month_summary ADD PRIMARY KEY (data_time, account_id, data_month_date);
ALTER TABLE dws.dws_complaint_day_summary ADD PRIMARY KEY (data_time, department_id, data_date);
ALTER TABLE dws.dws_dpi_app_day_summary ADD PRIMARY KEY (data_time, application_id, data_date);

ALTER TABLE ads.ads_kpi_user_overview_monthly ADD PRIMARY KEY (data_time, data_month_date);
ALTER TABLE ads.ads_kpi_revenue_monthly ADD PRIMARY KEY (data_time, data_month_date);
ALTER TABLE ads.ads_kpi_arrears_monthly ADD PRIMARY KEY (data_time, data_month_date);
ALTER TABLE ads.ads_kpi_channel_monthly ADD PRIMARY KEY (data_time, channel_id, data_month_date);
ALTER TABLE ads.ads_kpi_product_monthly ADD PRIMARY KEY (data_time, product_id, data_month_date);
ALTER TABLE ads.ads_kpi_complaint_daily ADD PRIMARY KEY (data_time, department_id, data_date);
ALTER TABLE ads.ads_agent_metric_catalog DROP PRIMARY KEY, ADD PRIMARY KEY (data_time, metric_id);
ALTER TABLE ads.ads_agent_field_catalog DROP PRIMARY KEY, ADD PRIMARY KEY (data_time, field_id);
ALTER TABLE ads.ads_agent_semantic_join DROP PRIMARY KEY, ADD PRIMARY KEY (data_time, join_relation_id);

CREATE INDEX ix_dim_user_data_time ON dwd.dim_user (data_time);
CREATE INDEX ix_dim_account_data_time ON dwd.dim_account (data_time);
CREATE INDEX ix_dim_customer_data_time ON dwd.dim_customer (data_time);
CREATE INDEX ix_dim_product_data_time ON dwd.dim_product (data_time);

CREATE INDEX ix_fact_billing_user_month ON dwd.fact_billing_monthly (data_time, user_id, billing_month_date);
CREATE INDEX ix_fact_snapshot_user_date ON dwd.fact_user_snapshot_daily (data_time, user_id, data_date);
CREATE INDEX ix_fact_usage_user_date ON dwd.fact_usage_daily (data_time, user_id, data_date);
CREATE INDEX ix_fact_recharge_user_date ON dwd.fact_recharge_daily (data_time, user_id, recharge_date);
CREATE INDEX ix_fact_order_user_time ON dwd.fact_order_daily (data_time, user_id, business_time);
CREATE INDEX ix_fact_complaint_user_date ON dwd.fact_complaint_daily (data_time, user_id, complaint_date);
CREATE INDEX ix_fact_dpi_user_app_date ON dwd.fact_dpi_usage_daily (data_time, user_id, application_id, data_date);

CREATE INDEX ix_dws_user_day_batch ON dws.dws_user_day_summary (data_time, user_id);
CREATE INDEX ix_dws_user_month_batch ON dws.dws_user_month_summary (data_time, user_id);
CREATE INDEX ix_dws_product_month_batch ON dws.dws_product_month_summary (data_time, product_id);
CREATE INDEX ix_dws_channel_day_batch ON dws.dws_channel_day_summary (data_time, channel_id);

CREATE INDEX ix_ads_user_overview_batch ON ads.ads_kpi_user_overview_monthly (data_time);
CREATE INDEX ix_ads_revenue_batch ON ads.ads_kpi_revenue_monthly (data_time);
CREATE INDEX ix_ads_arrears_batch ON ads.ads_kpi_arrears_monthly (data_time);

SET FOREIGN_KEY_CHECKS = 1;

