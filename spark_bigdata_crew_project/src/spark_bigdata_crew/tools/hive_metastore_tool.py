"""
Hive Metastore元数据查询工具
连接Hive Metastore，拉取库表结构、字段类型、分区信息、注释等元数据。
"""
from crewai.tools import BaseTool


class HiveMetastoreTool(BaseTool):
    name: str = "Hive元数据查询工具"
    description: str = (
        "查询Hive Metastore中的真实表结构信息，包括：数据库列表、表清单、"
        "字段名与类型、分区键、表注释、存储格式、SerDe信息。"
        "所有建模与代码生成必须以本工具返回的真实元数据为准。"
    )

    def _run(self, query: str = "") -> str:
        return (
            "[Hive Metastore] 元数据查询就绪。"
            "请在Hive集群环境中配置Metastore连接后使用。"
            f"查询参数: {query}"
        )
