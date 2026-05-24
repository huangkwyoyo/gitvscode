"""
多源数据源适配生产技能
MCP写入：current_ds_config
能力：自动识别Hive/MySQL/SQLServer/Oracle数据源、参数校验、连接适配、数据源类型统一封装
"""
import os
from dotenv import load_dotenv
from src.mcp.context_protocol import mcp

load_dotenv()

class DataSourceSkill:
    @staticmethod
    def get_ds_config(ds_type: str) -> dict:
        """根据数据源类型读取对应环境配置并写入全局上下文"""
        config_map = {
            "hive": {
                "host": os.getenv("HIVE_HOST"),
                "port": os.getenv("HIVE_PORT"),
                "database": os.getenv("HIVE_DATABASE"),
                "type": "hive"
            },
            "mysql": {
                "host": os.getenv("MYSQL_HOST"),
                "port": os.getenv("MYSQL_PORT"),
                "user": os.getenv("MYSQL_USER"),
                "password": os.getenv("MYSQL_PASSWORD"),
                "database": os.getenv("MYSQL_DATABASE"),
                "type": "mysql"
            },
            "sqlserver": {
                "host": os.getenv("SQLSERVER_HOST"),
                "port": os.getenv("SQLSERVER_PORT"),
                "user": os.getenv("SQLSERVER_USER"),
                "password": os.getenv("SQLSERVER_PASSWORD"),
                "database": os.getenv("SQLSERVER_DATABASE"),
                "type": "sqlserver"
            },
            "oracle": {
                "host": os.getenv("ORACLE_HOST"),
                "port": os.getenv("ORACLE_PORT"),
                "service": os.getenv("ORACLE_SERVICE"),
                "user": os.getenv("ORACLE_USER"),
                "password": os.getenv("ORACLE_PASSWORD"),
                "type": "oracle"
            }
        }
        config = config_map.get(ds_type.lower())
        if not config:
            raise Exception(f"不支持的数据源类型：{ds_type}")
        
        # MCP全局上下文写入：缓存当前数据源配置
        mcp.set("current_ds_config", config)
        return config

    @staticmethod
    def parse_prd_ds(prd_content: str) -> str:
        """从PRD文本自动识别数据源类型"""
        if "hive" in prd_content.lower() or "数仓" in prd_content:
            return "hive"
        elif "mysql" in prd_content.lower() or "数据库" in prd_content:
            return "mysql"
        elif "sqlserver" in prd_content.lower() or "sql server" in prd_content.lower():
            return "sqlserver"
        elif "oracle" in prd_content.lower():
            return "oracle"
        return "hive"