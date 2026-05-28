from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
from src.skills.db_schema_skill import DBSchemaSkill

class SchemaInput(BaseModel):
    table_name: str = Field(description="待查询数据表名")
    ds_type: str = Field(description="数据源类型")

class TableSchemaTool(BaseTool):
    name = "表结构查询工具"
    description = "跨库查询数据表字段、类型、注释、主键完整元数据"
    args_schema: Type[SchemaInput] = SchemaInput

    def _run(self, table_name: str, ds_type: str):
        """查询指定表的完整字段元数据（表名、字段、类型、注释、主键）"""
        try:
            schema = DBSchemaSkill.get_table_schema(table_name, ds_type)
            return f"✅ 表结构查询成功：\n{str(schema)}"
        except Exception as e:
            return f"❌ 表结构查询失败：{str(e)}"