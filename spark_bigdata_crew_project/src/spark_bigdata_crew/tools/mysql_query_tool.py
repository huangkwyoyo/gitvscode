from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
import pymysql
from src.skills.data_source_skill import DataSourceSkill

class MySQLQueryInput(BaseModel):
    sql: str = Field(description="待执行查询SQL")
    db_name: str = Field(default="test_db", description="数据库名称")

class MySQLQueryTool(BaseTool):
    name = "数据库查询兜底工具"
    description = "通用SQL查询执行工具，用于元数据校验、数据抽样查询"
    args_schema: Type[MySQLQueryInput] = MySQLQueryInput

    def _run(self, sql: str, db_name: str = "test_db"):
        try:
            config = DataSourceSkill.get_ds_config("mysql")
            conn = pymysql.connect(
                host=config["host"], port=int(config["port"]),
                user=config["user"], password=config["password"], database=db_name
            )
            cursor = conn.cursor()
            cursor.execute(sql)
            res = cursor.fetchall()
            cursor.close()
            conn.close()
            return f"✅ SQL执行成功，结果：{str(res)}"
        except Exception as e:
            return f"❌ SQL执行失败：{str(e)}"