"""
全场景数据质量校验技能【根治幻觉/空执行/参数失效】
MCP写入：data_verify_result
适配：Hive表、Parquet/CSV文件 | 双层参数兜底 | 精细化异常捕获
"""
import os
import logging
from src.mcp.context_protocol import mcp

logger = logging.getLogger(__name__)

OUTPUT_ROOT = "./output"
os.makedirs(OUTPUT_ROOT, exist_ok=True)


class MultiDataVerifySkill:
    @staticmethod
    def get_spark_session():
        try:
            from pyspark.sql import SparkSession
        except ImportError as e:
            raise ImportError(
                "PySpark未安装或未正确配置。请执行: pip install pyspark 或配置 SPARK_HOME 环境变量"
            ) from e
        return (
            SparkSession.builder
            .appName("Production_Data_Verify")
            .enableHiveSupport()
            .master("local[*]")
            .config("spark.sql.adaptive.enabled", "true")
            .getOrCreate()
        )

    @staticmethod
    def verify_by_output_param(
        input_output_type: str = None,
        input_table_name: str = None,
        sample_limit: int = 100,
        check_empty: bool = True,
        check_duplicate: bool = True
    ) -> str:
        # 双层参数兜底：手动入参优先
        output_param = mcp.get("spark_output_param") or {}
        output_type = input_output_type if input_output_type else output_param.get("output_type", "")
        table_name = input_table_name if input_table_name else output_param.get("table_name", "")

        if not output_type or not table_name:
            return "❌ 校验失败：缺失核心参数，请先执行Spark代码生成与落地"

        file_path = f"{OUTPUT_ROOT}/{table_name}"
        spark = None
        final_report = ""

        try:
            spark = MultiDataVerifySkill.get_spark_session()
            status = "✅ 数据校验正常"
            total_count = 0
            empty_res = "未校验"
            duplicate_res = "未校验"
            sample_data = ""

            # Hive表校验
            if output_type == "hive_table":
                if not spark.catalog.tableExists(table_name):
                    final_report = f"❌ 校验失败：Hive表【{table_name}】不存在"
                    mcp.set("data_verify_result", final_report)
                    return final_report
                df = spark.sql(f"SELECT * FROM {table_name}")
                total_count = df.count()

                if check_empty:
                    empty_res = "✅ 数据非空" if total_count > 0 else "❌ 空数据异常"
                    if total_count == 0:
                        status = "❌ 数据异常"

                if check_duplicate and total_count > 0:
                    diff_count = total_count - df.distinct().count()
                    duplicate_res = f"❌ 存在重复数据{diff_count}行" if diff_count > 0 else "✅ 无重复数据"
                    if diff_count > 0:
                        status = "❌ 数据异常"

                sample_data = df.limit(sample_limit).toPandas().to_string()

            # 数据文件校验
            elif output_type == "file":
                if not os.path.exists(file_path):
                    final_report = f"❌ 校验失败：文件路径不存在【{file_path}】"
                    mcp.set("data_verify_result", final_report)
                    return final_report
                df = spark.read.load(file_path)
                total_count = df.count()

                if check_empty:
                    empty_res = "✅ 数据非空" if total_count > 0 else "❌ 空数据异常"
                if check_duplicate and total_count > 0:
                    diff_count = total_count - df.distinct().count()
                    duplicate_res = f"❌ 重复数据{diff_count}行" if diff_count > 0 else "✅ 无重复数据"

                sample_data = df.limit(sample_limit).toPandas().to_string()

            else:
                final_report = f"❌ 不支持的输出类型：{output_type}"
                mcp.set("data_verify_result", final_report)
                return final_report

            report = f"""
【📊 生产级数据质量校验报告】
校验状态：{status}
数据总行数：{total_count}
空值校验：{empty_res}
重复值校验：{duplicate_res}
样本数据（前{sample_limit}行）：
{sample_data}
"""
            final_report = report.strip()
            # MCP写入：缓存最终校验报告
            mcp.set("data_verify_result", final_report)
            return final_report

        except Exception as e:
            err_msg = f"❌ 校验异常：{str(e)}"
            logger.error("数据校验失败: %s", str(e), exc_info=True)
            mcp.set("data_verify_result", err_msg)
            return err_msg
        finally:
            if spark:
                try:
                    spark.stop()
                except Exception:
                    pass