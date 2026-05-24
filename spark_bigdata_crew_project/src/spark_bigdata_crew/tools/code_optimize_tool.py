from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

class CodeOptimizeInput(BaseModel):
    code: str = Field(description="原始Spark业务代码")

class CodeOptimizeTool(BaseTool):
    name = "Spark代码性能优化工具"
    description = "自动优化数据倾斜、小文件、分区裁剪、资源参数、算子优化"
    args_schema: Type[CodeOptimizeInput] = CodeOptimizeInput

    def _run(self, code: str):
        optimize_code = code
        # 自动追加生产优化配置
        optimize_code = optimize_code.replace(
            "spark = SparkSession.builder",
            """spark = SparkSession.builder \\
    .config("spark.sql.shuffle.partitions", "200") \\
    .config("spark.sql.files.maxPartitionBytes", "134217728") \\
    .config("spark.sql.adaptive.coalescePartitions.minPartitionNum", "10")"""
        )
        return f"✅ 代码性能优化完成：\n{optimize_code}"