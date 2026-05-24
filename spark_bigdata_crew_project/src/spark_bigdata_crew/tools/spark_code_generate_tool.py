from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional
from src.skills.spark_dev_skill import SparkCodeDevSkill
from src.mcp.context_protocol import mcp


class SparkCodeGenInput(BaseModel):
    table_list: list = Field(default_factory=list, description="数据源表名列表")
    field_list: list = Field(default_factory=list, description="业务字段列表")
    logic_desc: str = Field(default="常规统计聚合计算", description="业务计算逻辑描述")
    output_type: Optional[str] = Field(None, description="输出类型：hive_table/file")
    table_name: Optional[str] = Field(None, description="输出表名/文件名")
    write_mode: Optional[str] = Field(None, description="写入模式：overwrite/append/ignore")
    file_format: Optional[str] = Field(None, description="文件格式：parquet/csv")


class SparkCodeGenerateTool(BaseTool):
    name: str = "Spark代码生成工具"
    description: str = "动态生成零硬编码PySpark生产代码，适配Hive表/Parquet/CSV多形态输出"
    args_schema: Type[SparkCodeGenInput] = SparkCodeGenInput

    def _run(self, table_list=None, field_list=None, logic_desc="常规统计聚合计算",
             output_type=None, table_name=None, write_mode=None, file_format=None):
        table_list = table_list or []
        field_list = field_list or []

        prd_content = mcp.get("user_prd", "")
        db_type = mcp.get("data_source_type", "hive")

        output_param = SparkCodeDevSkill.parse_output_param(prd_content, db_type)
        if output_type:
            output_param["output_type"] = output_type
        if table_name:
            output_param["table_name"] = table_name
        if write_mode:
            output_param["write_mode"] = write_mode
        if file_format:
            output_param["file_format"] = file_format

        code = SparkCodeDevSkill.generate_code(table_list, field_list, logic_desc, output_param)
        return f"✅ Spark代码动态生成完成：\n{code}"
