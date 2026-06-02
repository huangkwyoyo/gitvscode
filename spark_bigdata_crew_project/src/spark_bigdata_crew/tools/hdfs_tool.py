"""
HDFS数据目录探查工具
连接HDFS NameNode，探查数据目录结构、文件大小、分区目录、数据文件格式。
"""
from crewai.tools import BaseTool


class HDFSTool(BaseTool):
    name: str = "HDFS目录探查工具"
    description: str = (
        "探查HDFS上的数据目录结构，包括：目录列表、文件数量与大小、"
        "分区目录完整性、数据文件格式（Parquet/ORC/CSV等）、数据更新时间。"
        "用于校验PRD中引用的数据路径是否真实存在。"
    )

    def _run(self, path: str = "/user/hive/warehouse") -> str:
        return (
            "[HDFS] 目录探查就绪。"
            "请在Hadoop集群环境中配置NameNode连接后使用。"
            f"探查路径: {path}"
        )
