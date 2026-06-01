"""重组业务过程材料，生成标准目录。"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-06-01"


PROCESSES = [
    {
        "num": "01",
        "id": "bp_001_user_daily_value_tag",
        "name": "用户日价值分层",
        "target": "ads.ads_user_daily_value_tag",
        "pk": ["biz_date", "user_id"],
        "date_col": "biz_date",
        "metrics": ["daily_revenue_fee", "month_billed_revenue_fee", "month_outstanding_amount", "last_30d_recharge_amount", "value_score"],
        "sources": ["dwd.fact_user_snapshot_daily", "dwd.fact_usage_daily", "dwd.fact_recharge_daily", "dwd.fact_billing_monthly", "dwd.dim_user", "dwd.dim_product"],
        "source_count": "SELECT COUNT(*) FROM dwd.fact_user_snapshot_daily WHERE data_date = @biz_date",
        "old_sql": "01_ads_user_daily_value_tag.sql",
    },
    {
        "num": "02",
        "id": "bp_002_user_month_lifecycle",
        "name": "用户月生命周期分析",
        "target": "dws.dws_user_month_lifecycle",
        "pk": ["data_month_date", "user_id"],
        "date_col": "data_month_date",
        "metrics": ["monthly_revenue_fee", "previous_month_revenue_fee", "mobile_data_usage_mb", "recharge_amount", "outstanding_amount"],
        "sources": ["dws.dws_user_month_summary", "dwd.dim_user"],
        "source_count": "SELECT COUNT(*) FROM dws.dws_user_month_summary WHERE data_month_date = @month_start",
        "old_sql": "02_dws_user_month_lifecycle.sql",
    },
    {
        "num": "03",
        "id": "bp_003_user_voice_sms_day_profile",
        "name": "语音短信行为日画像",
        "target": "dws.dws_user_voice_sms_day_profile",
        "pk": ["biz_date", "user_id"],
        "date_col": "biz_date",
        "metrics": ["voice_usage_min", "sms_count", "mobile_data_usage_mb", "voice_rank_in_group", "group_user_count"],
        "sources": ["dwd.fact_usage_daily", "dwd.dim_user", "dwd.dim_product"],
        "source_count": "SELECT COUNT(*) FROM dwd.fact_usage_daily WHERE data_date = @biz_date",
        "old_sql": "03_dws_user_voice_sms_day_profile.sql",
    },
    {
        "num": "04",
        "id": "bp_004_user_app_preference_day",
        "name": "DPI应用流量偏好",
        "target": "dws.dws_user_app_preference_day",
        "pk": ["biz_date", "user_id"],
        "date_col": "biz_date",
        "metrics": ["top_app_usage_mb", "total_app_usage_mb", "top_app_usage_ratio", "total_page_view_count"],
        "sources": ["dwd.fact_dpi_usage_daily", "dwd.dim_application", "dwd.fact_usage_daily", "dwd.dim_user"],
        "source_count": "SELECT COUNT(DISTINCT user_id) FROM dwd.fact_dpi_usage_daily WHERE data_date = @biz_date",
        "old_sql": "04_dws_user_app_preference_day.sql",
    },
    {
        "num": "05",
        "id": "bp_005_channel_order_conversion_day",
        "name": "渠道订单转化日分析",
        "target": "dws.dws_channel_order_conversion_day",
        "pk": ["biz_date", "channel_id", "product_type"],
        "date_col": "biz_date",
        "metrics": ["order_count", "paid_order_count", "cancelled_order_count", "payment_amount", "conversion_rate", "cancel_rate", "avg_pay_minutes"],
        "sources": ["dwd.fact_order_daily", "dwd.dim_channel", "dwd.dim_product"],
        "source_count": "SELECT COUNT(*) FROM dwd.fact_order_daily WHERE DATE(order_created_time) = @biz_date",
        "old_sql": "05_dws_channel_order_conversion_day.sql",
    },
    {
        "num": "06",
        "id": "bp_006_user_recharge_billing_reconcile_day",
        "name": "充值账单对账日分析",
        "target": "ads.ads_user_recharge_billing_reconcile_day",
        "pk": ["biz_date", "user_id"],
        "date_col": "biz_date",
        "metrics": ["daily_recharge_amount", "last_7d_recharge_amount", "billed_revenue_fee", "valid_outstanding_amount", "recharge_cover_rate"],
        "sources": ["dwd.fact_recharge_daily", "dwd.fact_billing_monthly", "dwd.dim_user", "dwd.dim_product"],
        "source_count": "SELECT COUNT(DISTINCT user_id) FROM dwd.fact_billing_monthly WHERE billing_month_date = @month_start",
        "old_sql": "06_ads_user_recharge_billing_reconcile_day.sql",
    },
    {
        "num": "07",
        "id": "bp_007_user_arrears_risk_day",
        "name": "欠费风险用户识别",
        "target": "ads.ads_user_arrears_risk_day",
        "pk": ["biz_date", "user_id"],
        "date_col": "biz_date",
        "metrics": ["arrears_month_count", "max_outstanding_amount", "valid_outstanding_amount", "last_30d_recharge_amount", "risk_score"],
        "sources": ["dwd.fact_billing_monthly", "dwd.fact_recharge_daily", "dwd.fact_usage_daily", "dwd.dim_user", "dwd.dim_product"],
        "source_count": "SELECT COUNT(DISTINCT user_id) FROM dwd.fact_billing_monthly WHERE billing_month_date BETWEEN DATE_SUB(@month_start, INTERVAL 2 MONTH) AND @month_start AND valid_outstanding_amount > 0",
        "old_sql": "07_ads_user_arrears_risk_day.sql",
    },
    {
        "num": "08",
        "id": "bp_008_complaint_sla_escalation_day",
        "name": "投诉SLA升级分析",
        "target": "ads.ads_complaint_sla_escalation_day",
        "pk": ["biz_date", "complaint_event_id"],
        "date_col": "biz_date",
        "metrics": ["complaint_handle_duration", "sla_limit_hour", "is_sla_timeout", "last_30d_complaint_count", "month_billed_revenue_fee"],
        "sources": ["dwd.fact_complaint_daily", "dwd.dim_user", "dwd.dim_product", "dwd.dim_org", "dwd.fact_billing_monthly"],
        "source_count": "SELECT COUNT(*) FROM dwd.fact_complaint_daily WHERE complaint_date = @biz_date",
        "old_sql": "08_ads_complaint_sla_escalation_day.sql",
    },
    {
        "num": "09",
        "id": "bp_009_terminal_contract_fulfillment_day",
        "name": "终端合约履约分析",
        "target": "dws.dws_terminal_contract_fulfillment_day",
        "pk": ["biz_date", "user_id", "terminal_id"],
        "date_col": "biz_date",
        "metrics": ["payment_transaction_amount", "refund_amount", "monthly_mobile_usage_mb", "monthly_voice_call_count", "monthly_sms_count", "fulfillment_score"],
        "sources": ["ods.ods_terminal_sales_daily", "ods.ods_terminal_presale_daily", "dwd.dim_user", "dwd.dim_terminal"],
        "source_count": "SELECT COUNT(*) FROM ods.ods_terminal_sales_daily WHERE DATE(data_time) = @biz_date",
        "old_sql": "09_dws_terminal_contract_fulfillment_day.sql",
    },
    {
        "num": "10",
        "id": "bp_010_enterprise_revenue_settlement_audit_day",
        "name": "政企收入与结算稽核",
        "target": "ads.ads_enterprise_revenue_settlement_audit_day",
        "pk": ["biz_date", "account_id", "department_id"],
        "date_col": "biz_date",
        "metrics": ["revenue_fee", "settlement_fee", "post_settlement_fee", "tax_fee", "revenue_settlement_diff"],
        "sources": ["ods.ods_account_income_monthly", "ods.ods_settlement_allocation_daily", "ods.ods_post_settlement_allocation_daily", "dwd.dim_account", "dwd.dim_org"],
        "source_count": "SELECT COUNT(*) FROM ods.ods_account_income_monthly WHERE DATE(data_time) = @biz_date",
        "old_sql": "10_ads_enterprise_revenue_settlement_audit_day.sql",
    },
]


def write(path: Path, content: str) -> None:
    """统一写入 UTF-8 文本，避免中文材料编码漂移。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def read_requirement(process: dict[str, object]) -> str:
    """按编号读取已有需求说明书，避免依赖中文文件名。"""
    pattern = f"{process['num']}_*.md"
    matches = sorted((ROOT / "docs" / "业务需求说明书").glob(pattern))
    if not matches:
        raise FileNotFoundError(f"未找到需求说明书：{pattern}")
    return matches[0].read_text(encoding="utf-8")


def split_sql(text: str) -> tuple[str, str, str]:
    """把集中版 SQL 拆成参数、建表、业务写入三部分。"""
    normalized = text.replace("\r\n", "\n")
    normalized = normalized.replace(
        "SELECT *\n  FROM month_seq",
        "SELECT data_month_date, user_id, monthly_revenue_fee, mobile_data_usage_mb, voice_usage_min, recharge_amount, outstanding_amount, previous_month_revenue_fee, previous_month_usage_mb, previous_month_recharge_amount\n  FROM month_seq",
    )
    create_match = re.search(r"CREATE TABLE IF NOT EXISTS[\s\S]*?\n\) COMMENT='[^']+';", normalized)
    insert_match = re.search(r"INSERT INTO[\s\S]*?(?=\n\n-- 校验：|\Z)", normalized)
    if create_match is None or insert_match is None:
        raise ValueError("SQL 文件结构不符合预期，无法拆分")
    preamble = normalized[: create_match.start()].strip()
    return preamble, create_match.group(0).strip(), insert_match.group(0).strip()


def sql_header(process: dict[str, object], sql_type: str) -> str:
    """生成标准 SQL 文件头。"""
    sources = "、".join(process["sources"])
    return f"""/*
业务过程：{process['name']}
SQL类型：{sql_type}
SQL口径：MySQL
输入表：{sources}
输出表：{process['target']}
时间口径：WebSQL 日批参数 @biz_date，月度逻辑使用 @month_start
生成日期：{NOW}
说明：本文件为迁移测试材料，未在数据库中执行。
*/"""


def build_check_sql(process: dict[str, object]) -> str:
    """生成符合 AGENTS.md 标准的校验 SQL。"""
    target = process["target"]
    date_col = process["date_col"]
    date_value = "@month_start" if date_col == "data_month_date" else "@biz_date"
    pk_cols = process["pk"]
    pk_expr = ", ".join(pk_cols)
    null_cond = " OR ".join(f"{col} IS NULL" for col in pk_cols)
    metric_cond = " OR ".join(f"{col} < 0" for col in process["metrics"])
    dim_cond = " OR ".join(f"{col} IS NULL" for col in pk_cols[1:]) if len(pk_cols) > 1 else "1 = 0"
    return f"""{sql_header(process, '校验SQL')}
SET @biz_date = '2025-12-31';
SET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');

-- 校验1：结果表行数校验
SELECT '结果表行数校验' AS check_name,
       'ROW_COUNT' AS check_type,
       CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'FAIL' END AS check_result,
       '> 0' AS expected_value,
       CAST(COUNT(*) AS CHAR) AS actual_value,
       NULL AS diff_value,
       '结果表在当前业务周期应生成数据' AS remark
FROM {target}
WHERE {date_col} = {date_value};

-- 校验2：主键唯一性校验
SELECT '主键唯一性校验' AS check_name,
       'PRIMARY_KEY_UNIQUE' AS check_type,
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS check_result,
       '0' AS expected_value,
       CAST(COUNT(*) AS CHAR) AS actual_value,
       CAST(COUNT(*) AS CHAR) AS diff_value,
       '业务主键不允许重复' AS remark
FROM (
  SELECT {pk_expr}, COUNT(*) AS duplicate_count
  FROM {target}
  WHERE {date_col} = {date_value}
  GROUP BY {pk_expr}
  HAVING COUNT(*) > 1
) duplicated_keys;

-- 校验3：核心字段非空校验
SELECT '核心字段非空校验' AS check_name,
       'NOT_NULL' AS check_type,
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS check_result,
       '0' AS expected_value,
       CAST(COUNT(*) AS CHAR) AS actual_value,
       CAST(COUNT(*) AS CHAR) AS diff_value,
       '业务主键和周期字段不允许为空' AS remark
FROM {target}
WHERE {date_col} = {date_value}
  AND ({null_cond});

-- 校验4：指标范围校验
SELECT '指标范围校验' AS check_name,
       'METRIC_RANGE' AS check_type,
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'WARN' END AS check_result,
       '0' AS expected_value,
       CAST(COUNT(*) AS CHAR) AS actual_value,
       CAST(COUNT(*) AS CHAR) AS diff_value,
       '金额、流量、时长、次数等核心指标原则上不应为负' AS remark
FROM {target}
WHERE {date_col} = {date_value}
  AND ({metric_cond});

-- 校验5：源表到结果表数量一致性校验
SELECT '源表到结果表数量一致性校验' AS check_name,
       'SOURCE_TARGET_COUNT' AS check_type,
       CASE WHEN ABS(source_count - target_count) = 0 THEN 'PASS' ELSE 'WARN' END AS check_result,
       CAST(source_count AS CHAR) AS expected_value,
       CAST(target_count AS CHAR) AS actual_value,
       CAST(target_count - source_count AS CHAR) AS diff_value,
       '不同业务过程存在过滤和聚合时允许 WARN 后人工复核' AS remark
FROM (
  SELECT ({process['source_count']}) AS source_count,
         (SELECT COUNT(*) FROM {target} WHERE {date_col} = {date_value}) AS target_count
) counts;

-- 校验6：维表关联丢失校验
SELECT '维表关联丢失校验' AS check_name,
       'DIM_JOIN_LOSS' AS check_type,
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'WARN' END AS check_result,
       '0' AS expected_value,
       CAST(COUNT(*) AS CHAR) AS actual_value,
       CAST(COUNT(*) AS CHAR) AS diff_value,
       '维度字段为空可能代表维表关联丢失，需要人工复核' AS remark
FROM {target}
WHERE {date_col} = {date_value}
  AND ({dim_cond});"""


def build_test_cases(process: dict[str, object]) -> str:
    """生成测试样例文档。"""
    return f"""# 测试样例

## 测试参数

| 参数 | 示例值 | 说明 |
|---|---|---|
| `@biz_date` | `2025-12-31` | WebSQL 日批业务日期 |
| `@month_start` | `2025-12-01` | 由业务日期推导出的月初日期 |

## 正常场景

1. 源表在业务日期有数据。
2. 维表关联字段能够正常匹配。
3. 指标金额、流量、时长、次数为非负值。
4. 结果表主键 `{', '.join(process['pk'])}` 不重复。

## 边界场景

1. 源事实表存在数据，但部分维表字段缺失。
2. 可选事实表无匹配记录时，业务 SQL 应使用默认值或空值处理。
3. 指标分母为 0 时，应返回默认值或空值，不能报错。
4. 聚合后结果行数与源表行数不一致时，校验 SQL 输出 `WARN` 并进入人工复核。

## 验收标准

- `check_mysql.sql` 至少返回 6 类校验结果。
- 主键唯一性校验必须为 `PASS`。
- 核心字段非空校验必须为 `PASS`。
- 指标范围校验如果为 `WARN`，必须在报告中说明原因。"""


def build_lineage(process: dict[str, object]) -> str:
    """生成表级血缘说明。"""
    source_rows = "\n".join(f"| `{table}` | 输入 | 参与 {process['name']} 计算 |" for table in process["sources"])
    return f"""# 血缘说明

## 业务过程

- 业务过程 ID：`{process['id']}`
- 业务过程名称：{process['name']}
- MySQL 结果表：`{process['target']}`

## 表级血缘

| 表名 | 类型 | 说明 |
|---|---|---|
{source_rows}
| `{process['target']}` | 输出 | MySQL 口径结果表 |

## 字段级血缘原则

1. 主键字段来自业务过程的周期字段和业务实体字段。
2. 维度字段来自对应维表或 ODS 宽表中的稳定字段。
3. 指标字段来自事实表聚合、窗口计算或业务规则计算。
4. 标签字段由 `CASE WHEN` 业务规则生成。
5. `created_at` 记录材料执行时的生成时间。

## 可追溯要求

后续 Doris 转换必须保留本目录 MySQL 原始材料，并输出到 `doris_outputs/{process['id']}/`。"""


def write_project_docs() -> None:
    """补齐项目治理文档。"""
    project_dir = ROOT / "docs" / "project"
    write(project_dir / "project_goal.md", """# 项目目标

## 项目定位

TeleSync Data Move 是一个 MySQL 到 Doris 数据迁移 Agent 工程。当前不直接迁移生产数据，而是基于本机电信模拟数仓，沉淀一套可生成、可转换、可调度、可校验、可追溯的数据迁移流程。

## 总体目标

1. 读取 MySQL 数仓画像，识别表结构、数据量、时间范围、样本数据和表关系。
2. 基于真实字段设计 10 个复杂电信业务过程。
3. 生成 MySQL 口径需求、结果表 DDL、业务 SQL、校验 SQL、测试样例和血缘说明。
4. 后续通过规则文件和 LangGraph Agent 转换为 Doris DDL/SQL。
5. 通过 WebSQL 以单批次方式调度执行。
6. 每批执行后输出转换报告、执行报告、校验报告和异常报告。

## 非目标

本项目不是 BI 大屏、OLTP 系统或通用数据库平台。所有设计必须围绕业务过程生成、SQL 生成、SQL 转换、批次迁移、结果校验和报告生成这条主链路展开。""")
    write(project_dir / "phase_plan.md", """# 阶段计划

## 阶段 1：MySQL 数仓画像

目标：只读分析 `ods`、`dwd`、`dws`、`ads` 四个库，输出表清单、字段画像、样本摘要和表关系分析。

## 阶段 2：MySQL 口径业务过程材料生成

目标：按 `business_processes/bp_xxx/` 组织 10 个业务过程，每个过程包含需求、DDL、业务 SQL、校验 SQL、测试样例、血缘说明。

## 阶段 3：MySQL 到 Doris 迁移转换

目标：基于 `migration_rules/` 规则文件生成 Doris 版本 DDL/SQL 和转换报告，不覆盖 MySQL 原始材料。

## 阶段 4：WebSQL 调度集成

目标：WebSQL 只作为 SQL 执行入口和调度入口，复杂逻辑由 FastAPI/LangGraph 承载。

## 阶段 5：批次校验和报告生成

目标：每批输出执行报告、校验报告、异常报告，历史记录不得覆盖。""")
    write(project_dir / "current_status.md", f"""# 当前状态

## 当前阶段

阶段 2：MySQL 口径业务过程材料标准化。

## 已完成

- 已创建根级 `AGENTS.md`。
- 已创建标准项目骨架。
- 已读取本机 MySQL 项目库画像。
- 已确认项目数据库范围：`ods`、`dwd`、`dws`、`ads`。
- 已确认 WebSQL 环境：容器名 `websql`，项目目录挂载到 `/app/data`，支持 SQL 脚本。
- 已生成 10 个业务需求说明书。
- 已生成 10 个 MySQL 口径 SQL 集中版文件。
- 已按 `business_processes/bp_xxx/` 重组业务过程材料。
- 已拆分 DDL、业务 SQL、校验 SQL。
- 已补齐测试样例和血缘说明。

## 未执行事项

- 未执行任何建表 SQL。
- 未执行任何业务写入 SQL。
- 未执行 WebSQL 调度。
- 未进行 Doris 转换。

## 更新时间

{NOW}""")
    write(project_dir / "next_tasks.md", """# 下一步任务

## 优先级 P0

1. 对 `business_processes/` 下 10 个业务过程做静态检查。
2. 检查 SQL 是否满足：禁止 `SELECT *`、字段显式、CTE 分层、Join 条件完整、业务日期明确、除零保护存在。
3. 检查校验 SQL 是否输出标准字段：`check_name`、`check_type`、`check_result`、`expected_value`、`actual_value`、`diff_value`、`remark`。

## 优先级 P1

1. 完善 `metadata/mysql_profile/` 标准画像文档。
2. 建立 `migration_rules/` 初版规则文件。
3. 建立批次配置模板。

## 暂不执行

- 暂不执行建表。
- 暂不执行业务 SQL 写入。
- 暂不执行 Doris 转换。
- 暂不提交 WebSQL 任务。""")
    rows = "\n".join(
        f"| {p['num']} | `{p['id']}` | {p['name']} | `{p['target']}` | `{', '.join(p['sources'])}` |"
        for p in PROCESSES
    )
    write(project_dir / "business_process_index.md", f"""# 业务过程索引

| 编号 | 业务过程ID | 业务过程名称 | 结果表 | 主要输入表 |
|---|---|---|---|---|
{rows}""")


def write_profile_docs() -> None:
    """补齐画像和规则入口文档。"""
    profile_dir = ROOT / "metadata" / "mysql_profile"
    write(profile_dir / "table_inventory.md", """# 表清单画像

## 项目库范围

仅纳入 `ods`、`dwd`、`dws`、`ads` 四个库。

## 核心表规模摘要

| 表名 | 数据量级别 | 说明 |
|---|---:|---|
| `dwd.fact_usage_daily` | 360 万 | 用户日流量、语音、短信行为 |
| `dwd.fact_dpi_usage_daily` | 300 万 | DPI 应用访问行为 |
| `dwd.fact_user_snapshot_daily` | 120 万 | 用户日快照和日收入 |
| `dwd.fact_billing_monthly` | 120 万 | 用户月账单和欠费 |
| `dwd.fact_recharge_daily` | 90 万 | 用户充值明细 |
| `dwd.fact_order_daily` | 20 万 | 渠道订单明细 |
| `dwd.fact_complaint_daily` | 3 万 | 投诉工单明细 |""")
    write(profile_dir / "column_profile.md", """# 字段画像

## 关键关联字段

- 用户：`user_id`
- 客户：`customer_id`
- 账户：`account_id`
- 产品：`product_id`
- 渠道：`channel_id`
- 应用：`application_id`
- 部门：`department_id`、`responsible_department_id`
- 终端：`terminal_id`

## 关键时间字段

- 日行为：`data_date`
- 月账单：`billing_month_date`
- 充值：`recharge_date`
- 订单：`order_created_time`、`payment_time`
- 投诉：`complaint_date`
- ODS 宽表：`data_time`""")
    write(profile_dir / "sample_data_summary.md", """# 样本数据摘要

## 已观察样本特征

- 用户维表覆盖移动用户、预付费和后付费类型。
- 产品维表包含 `basic_4g`、`standard_5g`、`premium_5g`、`family_fusion`、`low_activity` 等类型。
- 渠道维表包含 APP、营业厅、代理商、电商、客服等渠道类型。
- 应用维表包含视频、社交、办公教育、游戏、音乐、短视频等分类。
- 事实表覆盖 2025 年全年日批数据和 12 个账期月批数据。""")
    write(profile_dir / "relationship_analysis.md", """# 表关系分析

| 左表 | 关联字段 | 右表 | 用途 |
|---|---|---|---|
| `dwd.fact_usage_daily` | `user_id` | `dwd.dim_user` | 用户日行为补充用户维度 |
| `dwd.fact_dpi_usage_daily` | `application_id` | `dwd.dim_application` | DPI 应用分类补全 |
| `dwd.fact_order_daily` | `channel_id` | `dwd.dim_channel` | 订单渠道分析 |
| `dwd.fact_order_daily` | `product_id` | `dwd.dim_product` | 订单产品分析 |
| `dwd.fact_billing_monthly` | `user_id` | `dwd.dim_user` | 账单用户属性补全 |
| `dwd.fact_complaint_daily` | `responsible_department_id` | `dwd.dim_org` | 投诉责任部门分析 |
| `ods.ods_terminal_sales_daily` | `terminal_id` | `dwd.dim_terminal` | 终端履约分析 |""")
    write(ROOT / "migration_rules" / "mysql_sql_standards.md", """# MySQL SQL 生成规范

## 强制要求

- SQL 文件必须包含中文文件头。
- 禁止 `SELECT *`。
- 字段必须显式列出。
- 复杂 SQL 必须使用 CTE 分层。
- Join 条件必须完整。
- 业务 SQL 必须包含业务日期或批次范围。
- 除法必须处理除零风险。
- 空值必须显式处理。
- 每个业务过程必须提供标准校验 SQL。""")
    write(ROOT / "migration_rules" / "risk_patterns.md", """# 风险模式

## MySQL 阶段风险

- 结果表无主键或唯一业务键。
- 业务 SQL 未限制业务日期。
- 使用 `SELECT *`。
- Join 条件缺失或不完整。
- 指标除法未处理除零。
- 校验 SQL 不输出标准校验字段。

## Doris 转换阶段风险

- MySQL 特有函数无法直接映射。
- `TEXT` 等类型需要转换。
- 宽表字段过多导致建表策略需要人工确认。
- 大表导入和聚合可能触发资源风险。""")


def write_business_processes() -> None:
    """重组 10 个业务过程目录。"""
    for process in PROCESSES:
        bp_dir = ROOT / "business_processes" / str(process["id"])
        requirement = read_requirement(process)
        write(bp_dir / "requirement_mysql.md", requirement + f"""

## 标准目录信息

- 业务过程 ID：`{process['id']}`
- MySQL 结果表：`{process['target']}`
- 标准化日期：{NOW}
""")
        old_sql = (ROOT / "generated" / "mysql" / str(process["old_sql"])).read_text(encoding="utf-8")
        preamble, create_sql, insert_sql = split_sql(old_sql)
        set_lines = "\n".join(line for line in preamble.splitlines() if line.strip().upper().startswith("SET "))
        if "@month_start" not in set_lines:
            set_lines = set_lines.rstrip() + "\nSET @month_start = DATE_FORMAT(@biz_date, '%Y-%m-01');"
        business_sql = f"{sql_header(process, '业务SQL')}\n{set_lines.strip()}\n\n{insert_sql}"
        business_sql = business_sql.replace("WITH ", "WITH\n-- 按业务口径拆分中间结果，便于后续迁移转换和静态检查\n", 1)
        write(bp_dir / "result_table_mysql.sql", f"{sql_header(process, '结果表DDL')}\n\n{create_sql}")
        write(bp_dir / "business_mysql.sql", business_sql)
        write(bp_dir / "check_mysql.sql", build_check_sql(process))
        write(bp_dir / "test_cases.md", build_test_cases(process))
        write(bp_dir / "lineage.md", build_lineage(process))


def update_existing_docs() -> None:
    """更新已有说明，指向标准目录。"""
    readme_path = ROOT / "README.md"
    if readme_path.exists():
        readme = readme_path.read_text(encoding="utf-8")
        readme = readme.replace(
            "- 10 个业务需求说明书：`docs/业务需求说明书/`\n- 10 个 MySQL 业务 SQL：`generated/mysql/`\n- 项目上下文：`docs/business_context.md`\n- 项目状态：`docs/project_status.md`",
            "- 项目治理文档：`docs/project/`\n- 标准业务过程材料：`business_processes/bp_xxx/`\n- 历史集中版需求说明书：`docs/业务需求说明书/`\n- 历史集中版 MySQL SQL：`generated/mysql/`\n- MySQL 画像入口：`metadata/mysql_profile/`\n- 项目上下文：`docs/business_context.md`",
        )
        readme = readme.replace(
            "1. 创建 FastAPI 基础服务。\n2. 创建 LangGraph 迁移状态机。\n3. 抽象批次配置。\n4. 接入 MySQL 只读元数据服务。\n5. 接入 SQL 静态校验服务。",
            "1. 对 `business_processes/` 执行静态检查。\n2. 补齐 `migration_rules/` 初版 MySQL 到 Doris 映射规则。\n3. 创建 FastAPI 基础服务。\n4. 创建 LangGraph 迁移状态机。\n5. 建立 SQL 静态校验服务。",
        )
        write(readme_path, readme)
    status_path = ROOT / "docs" / "project_status.md"
    if status_path.exists():
        status = status_path.read_text(encoding="utf-8")
        status = status.replace("项目处于骨架和文档初始化阶段。", "项目处于 MySQL 业务过程材料标准化阶段。")
        if "已补齐 `docs/project/` 五个项目治理文档。" not in status:
            status = status.replace(
                "- 已创建 `docs/project_status.md`。",
                "- 已创建 `docs/project_status.md`。\n- 已补齐 `docs/project/` 五个项目治理文档。\n- 已按 `business_processes/bp_xxx/` 重组 10 个业务过程。\n- 已拆分每个业务过程的 DDL、业务 SQL、校验 SQL。",
            )
        write(status_path, status)


def main() -> None:
    """执行材料重组。"""
    write_project_docs()
    write_profile_docs()
    write_business_processes()
    update_existing_docs()
    print(f"已重组业务过程数量：{len(PROCESSES)}")


if __name__ == "__main__":
    main()
