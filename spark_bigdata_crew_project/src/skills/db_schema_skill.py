"""
跨库表结构解析技能
MCP写入：table_schema_info
能力：四大数据源统一拉取表名、字段名、字段类型、注释、主键、表结构元数据
"""
import logging

import pymysql

from src.mcp.context_protocol import mcp
from src.skills.data_source_skill import DataSourceSkill

logger = logging.getLogger(__name__)


class DBSchemaSkill:

    @staticmethod
    def get_table_schema(table_name: str, ds_type: str) -> dict:
        ds_type = ds_type.lower()
        ds_config = DataSourceSkill.get_ds_config(ds_type)
        schema_info = {
            "table_name": table_name,
            "fields": [],
            "primary_key": "",
            "table_comment": ""
        }

        if ds_type == "mysql":
            DBSchemaSkill._mysql_schema(table_name, ds_config, schema_info)
        elif ds_type == "sqlserver":
            DBSchemaSkill._sqlserver_schema(table_name, ds_config, schema_info)
        elif ds_type == "oracle":
            DBSchemaSkill._oracle_schema(table_name, ds_config, schema_info)
        elif ds_type == "hive":
            DBSchemaSkill._hive_schema(table_name, ds_config, schema_info)

        mcp.set("table_schema_info", schema_info)
        return schema_info

    @staticmethod
    def _mysql_schema(table_name: str, config: dict, schema_info: dict):
        conn = pymysql.connect(
            host=config["host"],
            port=int(config["port"]),
            user=config["user"],
            password=config["password"],
            database=config["database"]
        )
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE, COLUMN_COMMENT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{table_name}' AND TABLE_SCHEMA = '{config["database"]}'
        """)
        for field_name, field_type, field_comment in cursor.fetchall():
            schema_info["fields"].append({
                "field_name": field_name,
                "field_type": field_type,
                "comment": field_comment
            })
        cursor.execute(f"""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_NAME = '{table_name}' AND CONSTRAINT_NAME = 'PRIMARY'
        """)
        pk = cursor.fetchone()
        schema_info["primary_key"] = pk[0] if pk else ""
        cursor.execute(f"""
            SELECT TABLE_COMMENT FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = '{table_name}' AND TABLE_SCHEMA = '{config["database"]}'
        """)
        tc = cursor.fetchone()
        schema_info["table_comment"] = tc[0] if tc else ""
        cursor.close()
        conn.close()

    @staticmethod
    def _sqlserver_schema(table_name: str, config: dict, schema_info: dict):
        try:
            import pyodbc
        except ImportError:
            logger.warning("pyodbc未安装，跳过SQLServer表结构读取")
            return
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={config['host']},{config['port']};"
            f"DATABASE={config['database']};"
            f"UID={config['user']};PWD={config['password']}"
        )
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE, ISNULL(cast(ep.value as nvarchar(256)), '')
            FROM INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN sys.extended_properties ep
                ON ep.major_id = OBJECT_ID(c.TABLE_SCHEMA + '.' + c.TABLE_NAME)
                AND ep.minor_id = c.ORDINAL_POSITION AND ep.name = 'MS_Description'
            WHERE c.TABLE_NAME = '{table_name}'
        """)
        for field_name, field_type, field_comment in cursor.fetchall():
            schema_info["fields"].append({
                "field_name": field_name,
                "field_type": field_type,
                "comment": field_comment or ""
            })
        cursor.execute(f"""
            SELECT COL_NAME(ic.object_id, ic.column_id) AS pk_col
            FROM sys.indexes i
            JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            WHERE i.is_primary_key = 1 AND OBJECT_NAME(i.object_id) = '{table_name}'
        """)
        pk = cursor.fetchone()
        schema_info["primary_key"] = pk[0] if pk else ""
        cursor.close()
        conn.close()

    @staticmethod
    def _oracle_schema(table_name: str, config: dict, schema_info: dict):
        try:
            import cx_Oracle
        except ImportError:
            logger.warning("cx_Oracle未安装，跳过Oracle表结构读取")
            return
        dsn = cx_Oracle.makedsn(config["host"], config["port"], service_name=config.get("service", ""))
        conn = cx_Oracle.connect(user=config["user"], password=config["password"], dsn=dsn)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE, COMMENTS
            FROM ALL_COL_COMMENTS
            WHERE TABLE_NAME = UPPER('{table_name}') AND OWNER = UPPER('{config["user"]}')
        """)
        for field_name, field_type, field_comment in cursor.fetchall():
            schema_info["fields"].append({
                "field_name": field_name,
                "field_type": field_type,
                "comment": field_comment or ""
            })
        cursor.execute(f"""
            SELECT COLUMN_NAME FROM ALL_CONS_COLUMNS
            WHERE TABLE_NAME = UPPER('{table_name}') AND CONSTRAINT_NAME IN (
                SELECT CONSTRAINT_NAME FROM ALL_CONSTRAINTS
                WHERE TABLE_NAME = UPPER('{table_name}') AND CONSTRAINT_TYPE = 'P'
            )
        """)
        pk = cursor.fetchone()
        schema_info["primary_key"] = pk[0] if pk else ""
        cursor.close()
        conn.close()

    @staticmethod
    def _hive_schema(table_name: str, config: dict, schema_info: dict):
        try:
            from pyhive import hive
        except ImportError:
            logger.warning("pyhive未安装，跳过Hive表结构读取")
            return
        conn = hive.Connection(
            host=config["host"],
            port=int(config["port"]),
            database=config["database"]
        )
        cursor = conn.cursor()
        cursor.execute(f"DESCRIBE FORMATTED {table_name}")
        rows = cursor.fetchall()
        in_column_section = False
        for row in rows:
            col_name = str(row[0]).strip() if row[0] else ""
            col_type = str(row[1]).strip() if row[1] else ""
            if col_name.startswith("#") or col_name == "":
                continue
            if "col_name" in col_name.lower():
                in_column_section = True
                continue
            if in_column_section and not col_name:
                in_column_section = False
                continue
            if in_column_section:
                schema_info["fields"].append({
                    "field_name": col_name,
                    "field_type": col_type,
                    "comment": str(row[2]).strip() if len(row) > 2 and row[2] else ""
                })
        cursor.close()
        conn.close()
