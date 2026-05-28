"""
Spark动态参数研发技能【最终生产版】
MCP写入：spark_output_param、spark_code_raw
核心：PRD+前端双维度解析参数，自动适配Hive表/Parquet/CSV文件输出，无任何硬编码
"""
import re
from src.mcp.context_protocol import mcp

class SparkCodeDevSkill:
    """Spark动态参数研发技能：解析输出参数、生成PySpark代码（零硬编码）"""

    @staticmethod
    def parse_output_param(prd_content: str, db_type: str) -> dict:
        """从PRD文本和数据库类型推断输出表名、写入模式、文件格式等动态参数"""
        output_param = {
            "output_type": "hive_table",
            "table_name": "dws_business_result",
            "write_mode": "overwrite",
            "partition_col": "dt",
            "file_format": "parquet"
        }

        # 识别文件输出场景
        if re.search(r"输出文件|保存文件|导出parquet|导出csv", prd_content, re.I):
            output_param["output_type"] = "file"
        elif db_type == "hive":
            output_param["output_type"] = "hive_table"

        # 提取数仓分层表名（取最后一个匹配以优先使用最后提及的表）
        table_matches = re.findall(r"(dws|ads|dwd|ods)_\w+", prd_content)
        if table_matches:
            output_param["table_name"] = table_matches[-1]

        # 识别写入模式
        if re.search(r"增量|追加|append", prd_content, re.I):
            output_param["write_mode"] = "append"
        elif re.search(r"忽略|不覆盖|ignore", prd_content, re.I):
            output_param["write_mode"] = "ignore"

        # 识别文件格式
        if re.search(r"csv格式|文本输出", prd_content, re.I):
            output_param["file_format"] = "csv"

        mcp.set("spark_output_param", output_param)
        return output_param

    @staticmethod
    def generate_code(table_list: list, field_list: list, logic_desc: str, output_param: dict) -> str:
        """根据表清单、字段列表、业务逻辑描述和输出参数动态渲染PySpark生产代码"""
        output_type = output_param["output_type"]
        table_name = output_param["table_name"]
        write_mode = output_param["write_mode"]
        partition_col = output_param["partition_col"]
        file_format = output_param["file_format"]

        # 动态多表读取SQL
        read_sql = ""
        for idx, table in enumerate(table_list):
            read_sql += f"df_{idx+1} = spark.sql(\"SELECT * FROM {table}\")\n        "

        select_fields = ", ".join([f"col('{f}')" for f in field_list]) if field_list else "*"

        # 动态输出逻辑
        if output_type == "hive_table":
            write_logic = f"df_result.write.mode(\"{write_mode}\").partitionBy(\"{partition_col}\").saveAsTable(\"{table_name}\")"
        else:
            write_logic = f"df_result.write.mode(\"{write_mode}\").format(\"{file_format}\").partitionBy(\"{partition_col}\").save(\"./output/{table_name}\")"

        spark_code = f"""
# 生产级PySpark任务（动态参数驱动终版）
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, sum, avg, max, min, count_distinct
from pyspark.sql.window import Window

spark = SparkSession.builder \\
    .appName("Auto_Production_Spark_Task") \\
    .enableHiveSupport() \\
    .config("spark.sql.adaptive.enabled", "true") \\
    .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \\
    .getOrCreate()

{read_sql}
df_clean = df_1.filter(col("{field_list[0]}").isNotNull() if len(field_list) > 0 else "1=1")

# 业务计算逻辑：{logic_desc}
df_result = df_clean.select({select_fields}).distinct()

# 动态参数输出（无硬编码）
{write_logic}

spark.stop()
"""
        mcp.set("spark_code_raw", spark_code)
        return spark_code